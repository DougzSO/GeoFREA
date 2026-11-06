"""Fetch the FABDEM tiles of the slope-DEM test (COMMAND 100) by HTTP Range, without downloading the 10 x 10 degree zips.

    python scripts/acquire_fabdem_test_100.py [--list] [--tiles S18W051 ...]

FABDEM V1-2 (Hawker et al. 2022, University of Bristol; Copernicus GLO-30 with forests and buildings removed) is published as zips of 10 x 10 degrees
(0.9 to 2.3 GB). The server answers Range requests, so the zip directory and the one member wanted are read and nothing else. Files go to
`GEOFREA_DATA_DIR/external/fabdem/` with `fabdem_manifest.json` (source URL, size and ETag of the zip, SHA-256 of each tile, date) and the licence text
found inside the zip. Finished tiles are skipped. Nothing here is imported by the pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import io
import json
import os
import sys
import time
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASE = "https://data.bris.ac.uk/datasets/s5hqmjcdj8yo2ibzi9b4ew3sn"
TILES = ("S18W051", "S23W052", "S13W046", "N17E075", "N27E073", "N26E080", "N38W008")
BLOCK = 4 * 1024 * 1024


def _label(lat: int, lon: int) -> str:
    return f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}{'E' if lon >= 0 else 'W'}{abs(lon):03d}"


def zip_name(tile: str) -> str:
    """The 10 degree zip that holds a 1 degree tile: south-west corner and north-east corner, both on multiples of 10 (`S20W060-S10W050`)."""
    lat = int(tile[1:3]) * (1 if tile[0] == "N" else -1)
    lon = int(tile[4:7]) * (1 if tile[3] == "E" else -1)
    lat0, lon0 = (lat // 10) * 10, (lon // 10) * 10
    return f"{_label(lat0, lon0)}-{_label(lat0 + 10, lon0 + 10)}_FABDEM_V1-2.zip"


class RangeFile(io.RawIOBase):
    """A read-only seekable file over an HTTP URL that serves Range requests (blocks of 4 MB are cached one at a time)."""

    def __init__(self, url: str):
        self.url = url
        head = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(head, timeout=60) as r:
            self.size = int(r.headers["Content-Length"])
            self.etag = r.headers.get("ETag", "")
        self.pos = 0
        self._block_start = -1
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
        for attempt in range(1, 7):  # the server closes connections now and then: wait and ask for the same block again
            try:
                with urllib.request.urlopen(request, timeout=120) as r:
                    if r.status != 206:
                        raise RuntimeError(f"the server did not answer the Range request with 206 ({r.status})")
                    data = r.read()
                if len(data) != end - start + 1:
                    raise OSError(f"short block: {len(data)} of {end - start + 1} bytes")
                self.bytes_read += len(data)
                return data
            except (OSError, http.client.HTTPException):
                if attempt == 6:
                    raise
                time.sleep(2 * attempt)
        raise AssertionError("unreachable")

    def read(self, n: int = -1) -> bytes:
        if self.pos >= self.size:
            return b""
        n = self.size - self.pos if n < 0 else min(n, self.size - self.pos)
        out = bytearray()
        while n > 0:
            if not (self._block_start <= self.pos < self._block_start + len(self._block)):
                start = self.pos - (self.pos % BLOCK)
                self._block = self._fetch(start, min(start + BLOCK, self.size) - 1)
                self._block_start = start
            offset = self.pos - self._block_start
            piece = self._block[offset : offset + n]
            out += piece
            self.pos += len(piece)
            n -= len(piece)
        return bytes(out)

    def readinto(self, buffer) -> int:
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)


def out_dir() -> Path:
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("GEOFREA_DATA_DIR="):
            return Path(line.split("=", 1)[1].strip().strip('"')) / "external" / "fabdem"
    raise SystemExit("GEOFREA_DATA_DIR is not set in .env")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--tiles", nargs="*", default=list(TILES))
    parser.add_argument("--list", action="store_true", help="only list the members of each zip (licence and readme files included)")
    args = parser.parse_args(argv)
    out = out_dir()
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "fabdem_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"tiles": {}, "licence_files": {}}
    for tile in args.tiles:
        name = zip_name(tile)
        remote = RangeFile(f"{BASE}/{name}")
        with zipfile.ZipFile(remote) as z:
            members = z.namelist()
            if args.list:
                print(name, remote.size, [m for m in members if not m.endswith(".tif")][:10], sum(m.endswith(".tif") for m in members), "tifs")
                continue
            wanted = [m for m in members if m.endswith(".tif") and Path(m).name.startswith(tile + "_")]
            if len(wanted) != 1:
                raise SystemExit(f"{tile}: {len(wanted)} members match in {name}")
            target = out / Path(wanted[0]).name
            if not target.exists():
                tmp = target.with_suffix(".part")
                digest = hashlib.sha256()
                with z.open(wanted[0]) as src, open(tmp, "wb") as dst:
                    while chunk := src.read(1 << 20):
                        dst.write(chunk)
                        digest.update(chunk)
                    dst.flush()
                    os.fsync(dst.fileno())
                os.replace(tmp, target)
                manifest["tiles"][tile] = {
                    "file": target.name,
                    "bytes": target.stat().st_size,
                    "sha256": digest.hexdigest(),
                    "zip": name,
                    "zip_url": f"{BASE}/{name}",
                    "zip_bytes": remote.size,
                    "zip_etag": remote.etag,
                    "member": wanted[0],
                    "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
                    "range_bytes_read": remote.bytes_read,
                }
            for member in members:  # the licence and readme texts inside the zip
                if not member.endswith(".tif") and not member.endswith("/") and member not in manifest["licence_files"]:
                    text = z.read(member)
                    (out / f"{name[:-4]}__{Path(member).name}").write_bytes(text)
                    manifest["licence_files"][member] = {"zip": name, "bytes": len(text), "sha256": hashlib.sha256(text).hexdigest()}
        print(f"{tile}: {name}: {remote.bytes_read / 1e6:.1f} MB read of {remote.size / 1e6:.0f} MB")
        if not args.list:
            manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
