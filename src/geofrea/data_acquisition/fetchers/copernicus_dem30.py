"""Copernicus DEM GLO-30 tiles (30 m) for the slope shares of F2a (D-F2a-016).

The DEM F1 holds for the country is a 0.005 degree resample (about 550 m), too coarse for the 30-100 m slopes behind the
literature thresholds. The GLO-30 COG tiles (1 x 1 degree, 3600 x 3600 samples, float32, EPSG:4326) are public on the AWS Open
Data bucket `copernicus-dem-30m`; no account is needed. Tiles are named by their south-west corner. A tile that does not
exist (open sea) answers 404 and is recorded as absent; any other failure is an error. Each file is checked against its
Content-Length and its sha256 is written to `manifest.json` beside the tiles (A-08: pinned inputs).
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

from geofrea.core import paths
from geofrea.core.atomic_io import write_text_atomic
from geofrea.core.resumable_download import DownloadError, download_resumable, existing_entry

logger = logging.getLogger("geofrea.data_acquisition.fetchers.copernicus_dem30")

BASE_URL = "https://copernicus-dem-30m.s3.amazonaws.com"
SOURCE = "Copernicus DEM GLO-30 (ESA/Airbus), AWS Open Data registry `copernicus-dem-30m`"
MANIFEST = "manifest.json"
_TIMEOUT_S = 120


class DemDownloadError(RuntimeError):
    """A tile could not be fetched for a reason other than being absent."""


def tile_name(lat0: int, lon0: int) -> str:
    """Tile id for the 1 degree tile whose south-west corner is (lat0, lon0)."""
    ns = "N" if lat0 >= 0 else "S"
    ew = "E" if lon0 >= 0 else "W"
    return f"Copernicus_DSM_COG_10_{ns}{abs(lat0):02d}_00_{ew}{abs(lon0):03d}_00_DEM"


def tiles_for(boundary: gpd.GeoDataFrame) -> list[str]:
    """Names of the 1 degree tiles whose footprint intersects the country polygon."""
    geom = boundary.to_crs("EPSG:4326").union_all()
    minx, miny, maxx, maxy = geom.bounds
    names = []
    for lat0 in range(math.floor(miny), math.ceil(maxy)):
        for lon0 in range(math.floor(minx), math.ceil(maxx)):
            if geom.intersects(box(lon0, lat0, lon0 + 1, lat0 + 1)):
                names.append(tile_name(lat0, lon0))
    return names


def dem_dir(iso: str) -> Path:
    return paths.fetched_raw("copernicus_dem30", iso)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _fetch(name: str, dest: Path, recorded: dict | None = None) -> dict | None:
    """Download one tile; None if the tile does not exist.

    A tile already at its name is kept only if it is the whole file: the size and SHA-256 of the manifest of an earlier run, or, with no record, a GeoTIFF
    that opens and gives its last block. One that is not is set aside as `<name>.corrupt` and fetched again. An interrupted download is continued from
    its `.part` (`core.resumable_download`).
    """
    target = dest / f"{name}.tif"
    url = f"{BASE_URL}/{name}/{name}.tif"
    if target.exists():
        entry = existing_entry(target, recorded)
        if entry is not None:
            return {"name": name, **entry}
        logger.warning("%s: the tile at its name is not the whole file; it is set aside and fetched again", name)
        target.replace(target.with_name(target.name + ".corrupt"))
    try:
        entry = download_resumable(url, target, timeout=_TIMEOUT_S, absent_statuses=(404,))
    except DownloadError as exc:
        raise DemDownloadError(f"{name}: {exc}") from exc
    return None if entry is None else {"name": name, **entry}


def _recorded_tiles(dest: Path) -> dict[str, dict]:
    """The entries of the manifest of an earlier run, by tile name (empty when there is none or it cannot be read)."""
    try:
        tiles = json.loads((dest / MANIFEST).read_text(encoding="utf-8"))["tiles"]
        return {t["name"]: t for t in tiles}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def fetch_country(
    iso: str, boundary: gpd.GeoDataFrame, workers: int = 6, names: Iterable[str] | None = None
) -> Path:
    """Download every GLO-30 tile that intersects the country and write the manifest; returns the tile directory."""
    dest = dem_dir(iso)
    dest.mkdir(parents=True, exist_ok=True)
    wanted = list(names) if names is not None else tiles_for(boundary)
    logger.info("%s: %d candidate tiles", iso, len(wanted))
    recorded = _recorded_tiles(dest)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda n: _fetch(n, dest, recorded.get(n)), wanted))
    present = [r for r in results if r is not None]
    absent = [n for n, r in zip(wanted, results, strict=True) if r is None]
    manifest = {
        "source": SOURCE,
        "base_url": BASE_URL,
        "country": iso,
        "downloaded_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "tiles": present,
        "absent_tiles": absent,
    }
    write_text_atomic(dest / MANIFEST, json.dumps(manifest, indent=1) + "\n")
    logger.info(
        "%s: %d tiles present (%.1f GB), %d absent",
        iso,
        len(present),
        sum(t["bytes"] for t in present) / 1e9,
        len(absent),
    )
    return dest


def load_tiles(iso: str) -> list[Path]:
    """The tiles pinned for the country; fails loudly if none were acquired or one listed in the manifest is gone."""
    dest = dem_dir(iso)
    manifest = dest / MANIFEST
    if not manifest.exists():
        raise FileNotFoundError(
            f"no Copernicus GLO-30 tiles for {iso}: run `python scripts/acquire_dem30.py` ({manifest} is missing)"
        )
    info = json.loads(manifest.read_text(encoding="utf-8"))
    files = [dest / f"{t['name']}.tif" for t in info["tiles"]]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        raise FileNotFoundError(f"{iso}: tiles listed in {manifest} are missing: {missing[:5]}")
    return files
