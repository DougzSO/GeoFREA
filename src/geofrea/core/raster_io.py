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
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import rasterio
import rasterio.shutil
from rasterio._err import CPLE_BaseError

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


_WRITE_RETRY_WAITS_S = (2.0, 5.0, 10.0, 20.0)


def _open_for_write(file_path: Path, kwargs: dict[str, Any]):
    """rasterio.open(..., "w") that retries when Windows holds the file it must overwrite.

    GDAL deletes an existing file before creating it; a search indexer or antivirus scanning a file written
    moments earlier makes that delete fail with "Permission denied" (observed 2026-10-06 on the BRA wind layers,
    D:). The lock clears by itself, so wait and retry a bounded number of times, then raise the original error.
    """
    for wait in (*_WRITE_RETRY_WAITS_S, None):
        try:
            return rasterio.open(str(file_path), "w", **kwargs)
        except (rasterio.errors.RasterioIOError, CPLE_BaseError) as exc:
            if wait is None or "Permission denied" not in str(exc):
                raise
            logger.warning("%s is locked (%s); retrying in %.0fs", file_path.name, exc, wait)
            time.sleep(wait)
    raise AssertionError("unreachable")  # pragma: no cover


def _cog_options(kwargs: dict[str, Any]) -> dict[str, str]:
    """GDAL COG creation options equivalent to the writer's profile (same compression, same predictor, 256 pixel blocks)."""
    options = {
        "COMPRESS": str(kwargs.get("compress", "lzw")).upper(),
        "BLOCKSIZE": str(kwargs.get("blockxsize", 256)),
        "OVERVIEW_RESAMPLING": "NEAREST",  # overviews never invent values: classes and counts stay valid
    }
    if kwargs.get("predictor") is not None:
        options["PREDICTOR"] = str(kwargs["predictor"])
    return options


def _write_cog(tmp_path: Path, final_path: Path, kwargs: dict[str, Any]) -> None:
    """Convert the finished GeoTIFF at `tmp_path` into a Cloud Optimized GeoTIFF at `final_path` (lossless), then drop it.

    Implements: A-07.
    """
    options = _cog_options(kwargs)
    for wait in (*_WRITE_RETRY_WAITS_S, None):
        try:
            if final_path.exists():
                final_path.unlink()
            rasterio.shutil.copy(str(tmp_path), str(final_path), driver="COG", **options)
            break
        except (rasterio.errors.RasterioIOError, CPLE_BaseError, PermissionError) as exc:
            if wait is None or "ermission" not in str(exc):
                raise
            logger.warning("%s is locked (%s); retrying in %.0fs", final_path.name, exc, wait)
            time.sleep(wait)
    tmp_path.unlink(missing_ok=True)


@contextmanager
def safe_raster_write(file_path: str | Path, **kwargs: Any) -> Generator[rasterio.DatasetWriter, None, None]:
    """Open a raster file for writing, creating parent directories as needed; the file ends up as a COG (A-07).

    The raster is written as a tiled GeoTIFF next to the destination (LZW and tiling by default, overridable via kwargs, so
    windowed writes and tags work as with any rasterio dataset) and converted on exit to a Cloud Optimized GeoTIFF at
    `file_path` with the same compression, predictor and nodata; values and tags are unchanged. If the `with` body raises,
    the partial file is removed and nothing is written to `file_path`.

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
    tmp_path = file_path.with_name(f"{file_path.stem}.writing.tif")
    dst = _open_for_write(tmp_path, kwargs)
    try:
        yield dst
    except BaseException:
        dst.close()
        tmp_path.unlink(missing_ok=True)
        raise
    dst.close()
    _write_cog(tmp_path, file_path, kwargs)


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
