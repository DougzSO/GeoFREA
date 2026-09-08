"""Raster I/O context managers shared across phases.

Ported from geoworld_framework's src/utils/utils.py
(safe_raster_open/safe_raster_write) and src/utils/logging_utils.py
(gdal_quiet) for grid_alignment (see docs/DECISIONS.md 2026-09-08,
grid_alignment Passo 3). data_quality_audit does not use these: it
only ever reads rasters (plain rasterio.open() in raster_inspection.py)
and never writes one, so there was nothing to port before now.
Generic raster I/O, not audit- or alignment-specific — lives in core/
for the same reason get_mainland_gdf()/detect_island_nation() do (see
geo_utils.py's module docstring).
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import rasterio

logger = logging.getLogger(__name__)

try:
    from osgeo import gdal as _gdal

    _HAS_GDAL_BINDINGS = True
except ImportError:
    _HAS_GDAL_BINDINGS = False


@contextmanager
def safe_raster_open(file_path: str | Path) -> Generator[rasterio.DatasetReader, None, None]:
    """Open a raster file for reading, with a clear error if it is missing.

    Args:
        file_path: Path to the raster file.

    Yields:
        Open rasterio DatasetReader, closed automatically on exit.

    Raises:
        FileNotFoundError: If the raster file does not exist.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Raster not found: {file_path}")

    src = rasterio.open(str(file_path))
    try:
        yield src
    finally:
        src.close()


@contextmanager
def safe_raster_write(file_path: str | Path, **kwargs: Any) -> Generator[rasterio.DatasetWriter, None, None]:
    """Open a raster file for writing, creating parent directories as needed.

    Applies LZW compression and tiling by default (overridable via kwargs).

    Args:
        file_path: Destination path for the raster file.
        **kwargs: Additional keyword arguments passed to rasterio.open().

    Yields:
        Open rasterio DatasetWriter, closed automatically on exit.
    """
    kwargs.setdefault("compress", "lzw")
    kwargs.setdefault("tiled", True)

    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    dst = rasterio.open(str(file_path), "w", **kwargs)
    try:
        yield dst
    finally:
        dst.close()


@contextmanager
def gdal_quiet() -> Generator[None, None, None]:
    """Suppress GDAL/CPL log output for the duration of the `with` block only.

    A no-op if the osgeo Python bindings are not installed (rasterio
    does not require them; GDAL_DATA/reproject still work without this
    suppression, just noisier). Thread-safety: GDAL maintains its error
    handler stack per thread, so this does not leak across threads.
    """
    if _HAS_GDAL_BINDINGS:
        _gdal.PushErrorHandler("CPLQuietErrorHandler")
        try:
            yield
        finally:
            _gdal.PopErrorHandler()
    else:
        yield
