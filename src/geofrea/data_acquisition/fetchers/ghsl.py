"""GHS-SMOD R2023A, the GHS settlement model (Degree of Urbanisation applied to GHS-POP and GHS-BUILT-S), epoch 2020, 1 km, Mollweide (Group 6, COMMAND 97).

One global file, the same for every country, pinned by content: the SHA-256 of the archive and of the raster are recorded here and checked on every read
(`verify`), and the content hash of the raster enters the key of the aligned layer, so a replaced file recomputes the layer and is recorded in the manifest.
The file lives under `GEOFREA_DATA_DIR/external/ghsl/` (never in the shared raw directory). `scripts/acquire_ghsl_smod.py` downloads and extracts it.

Classes of the raster (L2): 30 urban centre, 23 dense urban cluster, 22 semi-dense urban cluster, 21 suburban or peri-urban, 13 rural cluster (village),
12 low density rural, 11 very low density rural, 10 water; nodata -200. A settlement is class 13 or above (`land_availability.settlements.min_class`).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from geofrea.core import paths as core_paths

PRODUCT = "GHS_SMOD_E2020_GLOBE_R2023A_54009_1000_V2_0"
URL = (
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_SMOD_GLOBE_R2023A/"
    "GHS_SMOD_E2020_GLOBE_R2023A_54009_1000/V2-0/GHS_SMOD_E2020_GLOBE_R2023A_54009_1000_V2_0.zip"
)
ARCHIVE_SHA256 = "a02f4741f4ff37143ea0b53179d834eb2caa522e7e34b39b51ddcc3011d0a251"
RASTER_SHA256 = "1e2d7d7a6994b0458fc5d6ff985fb872f27841162b1808a3d52e32ae1a4953a0"
NODATA = -200
MIN_SETTLEMENT_CLASS = 13  # documented default; the value in force is `land_availability.settlements.min_class`


class SmodNotAcquiredError(FileNotFoundError):
    """The GHS-SMOD raster is not under `GEOFREA_DATA_DIR/external/ghsl`; run `python scripts/acquire_ghsl_smod.py` (A-09: never assumed absent of settlements)."""


def directory() -> Path:
    """`GEOFREA_DATA_DIR/external/ghsl`."""
    return core_paths.data_root() / "external" / "ghsl"


def raster_path() -> Path:
    """The extracted raster of the product, or raise `SmodNotAcquiredError`."""
    path = directory() / PRODUCT / f"{PRODUCT}.tif"
    if not path.is_file():
        raise SmodNotAcquiredError(f"{path} is absent: run `python scripts/acquire_ghsl_smod.py`")
    return path


def sha256(path: Path, chunk: int = 1 << 24) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while block := handle.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def verify_archive(path: Path) -> None:
    """Raise `ValueError` if the archive is not the pinned one."""
    found = sha256(path)
    if found != ARCHIVE_SHA256:
        raise ValueError(f"{path.name}: SHA-256 {found} is not the pinned {ARCHIVE_SHA256}")


def verify_raster(path: Path) -> None:
    """Raise `ValueError` if the extracted raster is not the pinned one (the layer key also holds its content hash)."""
    found = sha256(path)
    if found != RASTER_SHA256:
        raise ValueError(f"{path.name}: SHA-256 {found} is not the pinned {RASTER_SHA256}")
