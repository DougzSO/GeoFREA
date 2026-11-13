"""Raster I/O context managers shared across phases.

Ported from geoworld_framework's src/utils/utils.py
(safe_raster_open/safe_raster_write) and src/utils/logging_utils.py
(gdal_quiet) for grid_alignment (see docs/_archive/2026-09/DECISIONS.md 2026-09-08,
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

from geofrea.core.cog_write import open_for_write, write_cog

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
def safe_raster_write(
    file_path: str | Path, **kwargs: Any
) -> Generator[rasterio.DatasetWriter, None, None]:
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
    dst = open_for_write(tmp_path, kwargs)
    try:
        yield dst
    except BaseException:
        dst.close()
        tmp_path.unlink(missing_ok=True)
        raise
    dst.close()
    write_cog(tmp_path, file_path, kwargs)


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


class RasterStream:
    """A raster written window by window whose result can still be thrown away (COMMAND 88: nothing the size of the whole raster is held).

    Opened by `open_raster_stream`. `dataset` takes windowed writes and tags like any rasterio writer; `commit()` closes it and converts it to a
    Cloud Optimized GeoTIFF at the destination exactly as `safe_raster_write` does on exit (A-07), `discard()` closes it and removes the partial
    file. Leaving the `with` block without `commit()` discards, so an error leaves nothing at the destination.
    """

    def __init__(self, file_path: str | Path, **kwargs: Any) -> None:
        kwargs.setdefault("compress", "lzw")
        kwargs.setdefault("tiled", True)
        self._final = Path(file_path)
        self._final.parent.mkdir(parents=True, exist_ok=True)
        self._tmp = self._final.with_name(f"{self._final.stem}.writing.tif")
        self._kwargs = kwargs
        self.dataset = open_for_write(self._tmp, kwargs)
        self._done = False

    def commit(self) -> Path:
        self.dataset.close()
        write_cog(self._tmp, self._final, self._kwargs)
        self._done = True
        return self._final

    def discard(self) -> None:
        if not self._done:
            self.dataset.close()
            self._tmp.unlink(missing_ok=True)
            self._done = True

    def __enter__(self) -> RasterStream:  # noqa: PYI034 - kept as is: a code change would alter the phase fingerprints (L-072); remove it, returning `Self`, the next time F2a is recomputed for another reason
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.discard()


def open_raster_stream(file_path: str | Path, **kwargs: Any) -> RasterStream:
    """Open `file_path` for windowed writing; see `RasterStream`."""
    return RasterStream(file_path, **kwargs)
