"""FABDEM V1-2 tiles (30 m, forests and buildings removed) for the slope shares of F2a (COMMAND 101, D-F2a-028).

FABDEM (Hawker et al. 2022, University of Bristol) is Copernicus GLO-30 with a machine-learning correction of the height of trees and buildings. It is published as
zips of 10 x 10 degrees (0.9 to 2.5 GB), each holding one 3600 x 3600 GeoTIFF per 1 degree tile named by its south-west corner (`N18W051_FABDEM_V1-2.tif`). The server
answers HTTP Range requests, so the zip directory and the member wanted are read and the rest of the zip is not: a country costs the size of its tiles, not of its zips.

Licence: CC BY-NC-SA 4.0 (non-commercial, share-alike). The text published with the dataset is kept beside the tiles and its SHA-256 is in the manifest.

Files go to `<data root>/external/fabdem/`. A tile is written to `<name>.part`, flushed and renamed whole, and the manifest (`fabdem_manifest.json`: source URL, size
and ETag of the zip, size and SHA-256 of the tile, date) is rewritten atomically after each tile, so an interruption costs at most the tile in transfer. A block that the
server drops is asked for again. A tile the zip does not hold (open sea) is recorded as absent; F2a then uses GLO-30 for that tile and records it.
"""

from __future__ import annotations

import hashlib
import http.client
import io
import json
import logging
import os
import re
import threading
import time
import urllib.request
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd

from geofrea.core import paths
from geofrea.core.atomic_io import write_text_atomic
from geofrea.data_acquisition.fetchers import copernicus_dem30

logger = logging.getLogger("geofrea.data_acquisition.fetchers.fabdem")

BASE_URL = "https://data.bris.ac.uk/datasets/s5hqmjcdj8yo2ibzi9b4ew3sn"
LICENSE_URL = f"{BASE_URL}/license.txt"
LICENSE_NAME = "CC BY-NC-SA 4.0"
SOURCE = "FABDEM V1-2 (Hawker et al. 2022, University of Bristol), Copernicus GLO-30 with forests and buildings removed"
MANIFEST = "fabdem_manifest.json"
LICENSE_FILE = "fabdem_license.txt"
_GLO30_NAME = re.compile(r"_([NS])(\d{2})_00_([EW])(\d{3})_00_DEM")
_BLOCK = 4 * 1024 * 1024
_ATTEMPTS = 6


class FabdemDownloadError(RuntimeError):
    """A tile could not be read for a reason other than being absent from its zip."""


def tile_name(lat0: int, lon0: int) -> str:
    """Tile id of the 1 degree tile whose south-west corner is (lat0, lon0): `N18W051`."""
    return f"{'N' if lat0 >= 0 else 'S'}{abs(lat0):02d}{'E' if lon0 >= 0 else 'W'}{abs(lon0):03d}"


def zip_name(tile: str) -> str:
    """The 10 degree zip that holds a tile: its south-west and north-east corners on multiples of 10 (`S20W060-S10W050_FABDEM_V1-2.zip`)."""
    lat = int(tile[1:3]) * (1 if tile[0] == "N" else -1)
    lon = int(tile[4:7]) * (1 if tile[3] == "E" else -1)
    lat0, lon0 = (lat // 10) * 10, (lon // 10) * 10
    return f"{tile_name(lat0, lon0)}-{tile_name(lat0 + 10, lon0 + 10)}_FABDEM_V1-2.zip"


def fabdem_dir() -> Path:
    return paths.data_root() / "external" / "fabdem"


def tiles_for(boundary: gpd.GeoDataFrame) -> list[str]:
    """The 1 degree tiles whose footprint intersects the country polygon (by geometry, not bounding box), the set GLO-30 uses for the same country."""
    names = []
    for glo in copernicus_dem30.tiles_for(boundary):
        m = _GLO30_NAME.search(glo)
        names.append(f"{m[1]}{m[2]}{m[3]}{m[4]}")
    return names


class RangeFile(io.RawIOBase):
    """A read-only seekable file over an HTTP URL that serves Range requests; one block of 4 MB is cached, a block the server drops is asked for again."""

    def __init__(self, url: str, timeout: float = 120.0):
        self.url, self.timeout = url, timeout
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60) as r:
            self.size = int(r.headers["Content-Length"])
            self.etag = r.headers.get("ETag", "")
        self.pos = 0
        self._start = -1
        self._block = b""
        self.bytes_read = 0

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def _fetch(self, start: int, end: int) -> bytes:
        request = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{end}"})
        for attempt in range(1, _ATTEMPTS + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as r:
                    if r.status != 206:
                        raise FabdemDownloadError(f"{self.url}: the server did not answer the Range request with 206 ({r.status})")
                    data = r.read()
                if len(data) != end - start + 1:
                    raise OSError(f"short block: {len(data)} of {end - start + 1} bytes")
                self.bytes_read += len(data)
                return data
            except (OSError, http.client.HTTPException) as exc:
                if attempt == _ATTEMPTS:
                    raise FabdemDownloadError(f"{self.url}: bytes {start}-{end} failed {_ATTEMPTS} times ({exc})") from exc
                logger.warning("%s: block %d-%d failed (%s); trying again in %d s", Path(self.url).name, start, end, exc, 2 * attempt)
                time.sleep(2 * attempt)
        raise AssertionError("unreachable")

    def read(self, n: int = -1) -> bytes:
        if self.pos >= self.size:
            return b""
        n = self.size - self.pos if n < 0 else min(n, self.size - self.pos)
        out = bytearray()
        while n > 0:
            if not (self._start <= self.pos < self._start + len(self._block)):
                start = self.pos - (self.pos % _BLOCK)
                self._block = self._fetch(start, min(start + _BLOCK, self.size) - 1)
                self._start = start
            offset = self.pos - self._start
            piece = self._block[offset : offset + n]
            out += piece
            self.pos += len(piece)
            n -= len(piece)
        return bytes(out)

    def readinto(self, buffer) -> int:
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_manifest(dest: Path) -> dict:
    try:
        manifest = json.loads((dest / MANIFEST).read_text(encoding="utf-8"))
        manifest.setdefault("tiles", {})
        manifest.setdefault("absent_tiles", {})
        return manifest
    except (OSError, ValueError):
        return {"tiles": {}, "absent_tiles": {}}


def estimate_bytes(tiles: list[str], dest: Path | None = None) -> dict:
    """The bytes the missing tiles cost (the compressed size of their members, read from the zip directories by Range), without fetching any tile.

    Returns `{"bytes": total, "missing_tiles": [...], "absent": [tiles no zip holds], "tiles": n_to_fetch}`.
    """
    dest = dest or fabdem_dir()
    manifest = read_manifest(dest)
    todo = [t for t in tiles if not _is_current(dest, manifest, t) and t not in manifest["absent_tiles"]]
    by_zip: dict[str, list[str]] = defaultdict(list)
    for t in todo:
        by_zip[zip_name(t)].append(t)
    total, absent = 0, []
    for name, group in by_zip.items():
        remote = RangeFile(f"{BASE_URL}/{name}")
        with zipfile.ZipFile(remote) as z:
            sizes = {Path(i.filename).name.split("_")[0]: i.compress_size for i in z.infolist() if i.filename.endswith(".tif")}
        total += sum(sizes[t] for t in group if t in sizes)
        absent += [t for t in group if t not in sizes]
    return {"bytes": total, "tiles": len(todo) - len(absent), "absent": absent}


def _is_current(dest: Path, manifest: dict, tile: str) -> bool:
    """The tile is at its name with the size the manifest recorded for it (the hash was checked when it was written)."""
    entry = manifest["tiles"].get(tile)
    path = dest / f"{tile}_FABDEM_V1-2.tif"
    return bool(entry) and path.is_file() and path.stat().st_size == entry.get("bytes")


def _save_manifest(dest: Path, manifest: dict, lock: threading.Lock) -> None:
    with lock:
        manifest.update({"source": SOURCE, "base_url": BASE_URL, "license": LICENSE_NAME, "license_url": LICENSE_URL, "license_file": LICENSE_FILE})
        write_text_atomic(dest / MANIFEST, json.dumps(manifest, indent=1) + "\n")


def fetch_license(dest: Path) -> Path:
    """The licence text published with the dataset, kept beside the tiles; its SHA-256 goes to the manifest."""
    target = dest / LICENSE_FILE
    if not target.exists() or target.stat().st_size == 0:
        with urllib.request.urlopen(LICENSE_URL, timeout=60) as r:
            text = r.read()
        write_text_atomic(target, text.decode("utf-8"))
    return target


def _fetch_zip(name: str, group: list[str], dest: Path, manifest: dict, lock: threading.Lock) -> list[str]:
    remote = RangeFile(f"{BASE_URL}/{name}")
    absent = []
    with zipfile.ZipFile(remote) as z:
        members = {Path(i.filename).name.split("_")[0]: i for i in z.infolist() if i.filename.endswith(".tif")}
        for tile in group:
            member = members.get(tile)
            if member is None:
                absent.append(tile)
                with lock:
                    manifest["absent_tiles"][tile] = {"zip": name, "checked_at": datetime.now(UTC).isoformat(timespec="seconds")}
                _save_manifest(dest, manifest, lock)
                logger.info("%s: not in %s (open sea): GLO-30 is used for it", tile, name)
                continue
            target = dest / f"{tile}_FABDEM_V1-2.tif"
            part = target.with_suffix(".part")
            digest = hashlib.sha256()
            before = remote.bytes_read
            with z.open(member) as src, open(part, "wb") as out:  # zipfile checks the CRC of the member while it is read
                for chunk in iter(lambda: src.read(1 << 20), b""):
                    out.write(chunk)
                    digest.update(chunk)
                out.flush()
                os.fsync(out.fileno())
            if part.stat().st_size != member.file_size:
                part.unlink()
                raise FabdemDownloadError(f"{tile}: {part.name} has {part.stat().st_size} bytes, the zip says {member.file_size}")
            os.replace(part, target)
            with lock:
                manifest["tiles"][tile] = {
                    "file": target.name,
                    "bytes": target.stat().st_size,
                    "sha256": digest.hexdigest(),
                    "zip": name,
                    "zip_url": f"{BASE_URL}/{name}",
                    "zip_bytes": remote.size,
                    "zip_etag": remote.etag,
                    "member": member.filename,
                    "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
                    "range_bytes_read": remote.bytes_read - before,
                }
                manifest["absent_tiles"].pop(tile, None)
            _save_manifest(dest, manifest, lock)
            logger.info("%s: fetched (%.1f MB)", tile, target.stat().st_size / 1e6)
    return absent


def fetch_tiles(tiles: list[str], workers: int = 3) -> Path:
    """Fetch the missing tiles of `tiles` (one task per 10 degree zip, `workers` zips at once) and keep the manifest; returns the tile directory.

    A tile at its name with the recorded size is kept. A failure of one zip is raised after the others finish, so a rerun continues from the manifest.
    """
    dest = fabdem_dir()
    dest.mkdir(parents=True, exist_ok=True)
    license_path = fetch_license(dest)
    manifest = read_manifest(dest)
    manifest["license_sha256"] = sha256_file(license_path)
    lock = threading.Lock()
    todo = [t for t in dict.fromkeys(tiles) if not _is_current(dest, manifest, t)]
    by_zip: dict[str, list[str]] = defaultdict(list)
    for t in todo:
        by_zip[zip_name(t)].append(t)
    logger.info("%d of %d tiles to fetch from %d zips", len(todo), len(set(tiles)), len(by_zip))
    errors: list[str] = []

    def run(item):
        try:
            return _fetch_zip(item[0], item[1], dest, manifest, lock)
        except (FabdemDownloadError, OSError, zipfile.BadZipFile) as exc:
            errors.append(f"{item[0]}: {exc}")
            return []

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        list(pool.map(run, sorted(by_zip.items())))
    _save_manifest(dest, manifest, lock)
    if errors:
        raise FabdemDownloadError("; ".join(errors))
    return dest


def tile_path(tile: str, dest: Path | None = None) -> Path:
    return (dest or fabdem_dir()) / f"{tile}_FABDEM_V1-2.tif"


def load_tiles(tiles: list[str]) -> tuple[list[Path], list[str]]:
    """(the FABDEM files of `tiles` that are pinned in the manifest, the names of the tiles with none).

    A tile is present when the manifest lists it and the file has the recorded size. A tile the manifest records as absent from the dataset, or that was never fetched,
    is in the second list: F2a takes GLO-30 for it and says so.
    """
    dest = fabdem_dir()
    manifest = read_manifest(dest)
    have, lacking = [], []
    for t in tiles:
        if _is_current(dest, manifest, t):
            have.append(tile_path(t, dest))
        else:
            lacking.append(t)
    return have, lacking


def tile_corner(tile: str) -> tuple[int, int]:
    return int(tile[1:3]) * (1 if tile[0] == "N" else -1), int(tile[4:7]) * (1 if tile[3] == "E" else -1)


__all__ = [
    "FabdemDownloadError",
    "RangeFile",
    "estimate_bytes",
    "fabdem_dir",
    "fetch_tiles",
    "load_tiles",
    "tile_corner",
    "tile_name",
    "tiles_for",
    "zip_name",
]
