"""Pre-clip of a global or continental source raster to the bounding box of a country (COMMAND 88, item 2).

A source such as the PVOUT atlas covers the world; the aligned layer needs the few degrees around one country. The window is copied once, block by
block, to `<data dir>/cache/clipped/` under a name that holds the SHA-256 of the source and the window, and every later step reads the small file.
Nothing is written under `raw/` (read-only, CLAUDE.md).

The copy is pixel for pixel: the window is a whole number of source pixels, the data type, nodata and CRS are the source's, and the transform is the
source's shifted to the window. A warp that reads the clipped file therefore sees the same samples as one that reads the source, as long as the
margin covers the reach of the resampling kernel; the margin is at least `MIN_MARGIN_DEG` and at least twice the kernel footprint.

The bounding box is a read window, not a claim about the country: which pixels belong to the country is decided by the country polygon in the grid
(CLAUDE.md, "Geometry over bounding box").
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.windows import Window, from_bounds

from geofrea.core import paths as core_paths
from geofrea.core.cache_key import FileHashMemo

logger = logging.getLogger(__name__)

MIN_MARGIN_DEG = 0.1
SKIP_ABOVE_FRACTION = 0.9  # a window this close to the whole source is not worth a copy
_BLOCK_BYTES = 32_000_000


def cache_dir() -> Path:
    """`<data dir>/cache/clipped`."""
    return core_paths.data_root() / "cache" / "clipped"


def clipped_name(source: Path, source_sha256: str, window: Window) -> str:
    """File name of the clip: the source's stem, 12 characters of its SHA-256 and the window in source pixels."""
    return f"{source.stem}_{source_sha256[:12]}_c{window.col_off}_r{window.row_off}_w{window.width}_h{window.height}.tif"


def source_window(src: rasterio.DatasetReader, grid: Any, margin_deg: float) -> Window | None:
    """The window of `src` (whole pixels, outward) that holds the grid's extent plus `margin_deg`, or None when they do not overlap."""
    left, top = grid.transform * (0, 0)
    right, bottom = grid.transform * (grid.width, grid.height)
    win = from_bounds(left - margin_deg, bottom - margin_deg, right + margin_deg, top + margin_deg, transform=src.transform)
    col0, row0 = max(int(np.floor(win.col_off)), 0), max(int(np.floor(win.row_off)), 0)
    col1, row1 = min(int(np.ceil(win.col_off + win.width)), src.width), min(int(np.ceil(win.row_off + win.height)), src.height)
    if col1 <= col0 or row1 <= row0:
        return None
    return Window(col0, row0, col1 - col0, row1 - row0)


def clipped_source(
    source: Path,
    grid: Any,
    *,
    memo: FileHashMemo | None = None,
    directory: Path | None = None,
) -> Path:
    """Path of a raster that holds the part of `source` the grid needs: the clip in the cache, or `source` itself when a clip would save little.

    The source is returned unchanged when it is not in geographic coordinates (the window is computed in the grid's CRS, EPSG:4326), when it does
    not overlap the grid, or when the window is more than `SKIP_ABOVE_FRACTION` of it.
    """
    source = Path(source)
    with rasterio.open(source) as src:
        if src.crs is None or src.crs.to_epsg() != 4326 or grid.crs is None or rasterio.crs.CRS.from_user_input(grid.crs).to_epsg() != 4326:
            return source
        margin = max(MIN_MARGIN_DEG, 2 * abs(grid.transform.a), 2 * abs(src.transform.a) * 8)
        window = source_window(src, grid, margin)
        if window is None or window.width * window.height > SKIP_ABOVE_FRACTION * src.width * src.height:
            return source
        sha = (memo or FileHashMemo(None)).sha256(source)
        target = (directory or cache_dir()) / clipped_name(source, sha, window)
        if target.exists():
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f"{target.name}.{os.getpid()}.tmp")
        profile = {
            "driver": "GTiff",
            "dtype": src.dtypes[0],
            "width": int(window.width),
            "height": int(window.height),
            "count": 1,
            "crs": src.crs,
            "transform": src.window_transform(window),
            "nodata": src.nodata,
            "compress": "lzw",
            "tiled": True,
            "blockxsize": 256,
            "blockysize": 256,
        }
        rows_per_block = max(1, _BLOCK_BYTES // max(1, int(window.width) * np.dtype(src.dtypes[0]).itemsize))
        with rasterio.open(tmp, "w", **profile) as dst:
            for row in range(0, int(window.height), rows_per_block):
                height = min(rows_per_block, int(window.height) - row)
                read = Window(window.col_off, window.row_off + row, window.width, height)
                dst.write(src.read(1, window=read), 1, window=Window(0, row, int(window.width), height))
        tmp.replace(target)
        logger.info("    clipped %s to %dx%d px in the cache (%s).", source.name, window.width, window.height, target.name)
        return target
