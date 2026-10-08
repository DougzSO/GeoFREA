"""ESA WorldCover 2020 v100 (10 m) tiles from the public AWS bucket, for countries whose local tiles are not 10 m (D-F2a-017).

The IND tiles held in `database/raw/land_cover/India` have 3340 x 3340 samples per 3 degrees (about 100 m), not the 36000 x 36000
of the global 10 m product, and nothing in them records where they came from. This fetches the 10 m tiles for the same tile names
into `GEOFREA_DATA_DIR/raw/esa_worldcover/<ISO3>/`, checks each file against its Content-Length, and writes a `manifest.json`
with sha256 per tile. A tile the bucket does not have (404, open sea) is recorded as absent; any other failure is an error.
"""

from __future__ import annotations

import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import requests

from geofrea.core import paths

logger = logging.getLogger("geofrea.data_acquisition.fetchers.esa_worldcover")

BASE_URL = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v100/2020/map"
SOURCE = "ESA WorldCover 2020 v100, 10 m, AWS Open Data bucket `esa-worldcover`"
MANIFEST = "manifest.json"
_TIMEOUT_S = 180


class WorldCoverDownloadError(RuntimeError):
    """A tile could not be fetched for a reason other than being absent."""


def tiles_dir(iso: str) -> Path:
    return paths.fetched_raw("esa_worldcover", iso)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _fetch(name: str, dest: Path) -> dict | None:
    target = dest / name
    if target.exists():
        return {"name": name, "bytes": target.stat().st_size, "sha256": _sha256(target)}
    part = target.with_suffix(".part")
    try:
        with requests.get(f"{BASE_URL}/{name}", stream=True, timeout=_TIMEOUT_S) as r:
            if r.status_code in (403, 404):
                return None
            r.raise_for_status()
            expected = int(r.headers["Content-Length"])
            with open(part, "wb") as f:
                f.writelines(r.iter_content(1 << 20))
    except requests.RequestException as exc:
        raise WorldCoverDownloadError(f"{name}: {exc}") from exc
    if part.stat().st_size != expected:
        part.unlink()
        raise WorldCoverDownloadError(
            f"{name}: got {part.stat().st_size} bytes, expected {expected}"
        )
    part.replace(target)
    return {"name": name, "bytes": expected, "sha256": _sha256(target)}


def fetch_country(iso: str, tile_names: list[str], workers: int = 4) -> Path:
    """Download the named 10 m tiles for the country and write the manifest; returns the tile directory."""
    dest = tiles_dir(iso)
    dest.mkdir(parents=True, exist_ok=True)
    logger.info("%s: %d tiles requested", iso, len(tile_names))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda n: _fetch(n, dest), tile_names))
    present = [r for r in results if r is not None]
    absent = [n for n, r in zip(tile_names, results, strict=True) if r is None]
    manifest = {
        "source": SOURCE,
        "base_url": BASE_URL,
        "country": iso,
        "downloaded_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "tiles": present,
        "absent_tiles": absent,
    }
    (dest / MANIFEST).write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    logger.info(
        "%s: %d tiles present (%.1f GB), %d absent",
        iso,
        len(present),
        sum(t["bytes"] for t in present) / 1e9,
        len(absent),
    )
    return dest


def load_tiles(iso: str) -> list[Path]:
    """The 10 m tiles pinned for the country, or an empty list if none were acquired; fails if a listed tile is missing."""
    dest = tiles_dir(iso)
    manifest = dest / MANIFEST
    if not manifest.exists():
        return []
    info = json.loads(manifest.read_text(encoding="utf-8"))
    files = [dest / t["name"] for t in info["tiles"]]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        raise FileNotFoundError(f"{iso}: tiles listed in {manifest} are missing: {missing[:5]}")
    return files
