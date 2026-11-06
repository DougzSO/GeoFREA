"""The aligned slope and slope bins of F2a from FABDEM (COMMAND 101, D-F2a-028); the elevation stays on GLO-30.

Same method as `raster_alignment.glo30_aligned_outputs` (the slope and bin part of it, line by line the same arithmetic): central differences on the 30 m samples with the
WGS84 geodesic spacing of each row (`_glo30_strip_samples`), a sample counted in the pixel that holds its centre, 41 bins of 1 degree (the last open ended), the mean slope
of the samples of a pixel. Only the source changes: the FABDEM tile of each 1 degree square, and for a square FABDEM does not hold (open sea, or a tile not fetched) the
GLO-30 tile of the same square. The tiles that fall back, and the area of the country they cover, are written to `report_out` (and logged) so that the manifest says what the
slope of each country rests on.

This module is separate from `raster_alignment` on purpose: the elevation layer, whose key holds the code that computes it (`core.cache_code`), must not change when the slope
source does. The helpers are imported, not edited.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
from pathlib import Path

import numpy as np
from rasterio.windows import Window

from geofrea.core.atomic_io import write_text_atomic
from geofrea.core.checkpoint import CheckpointStore, make_key
from geofrea.core.constants import NODATA_FLOAT
from geofrea.core.geodesy import wgs84_km_per_degree
from geofrea.core.raster_io import RasterStream, open_raster_stream
from geofrea.core.run_logging import PeriodicProgress
from geofrea.grid_alignment.raster_alignment import (
    _CHECKPOINT_UNIT_ROWS,
    _GLO30_SAMPLES_PER_DEGREE,
    _OUTPUT_BLOCK_ROWS,
    _SLOPE_STRIP_GRID_ROWS,
    SLOPE_BINS,
    SLOPE_COUNT_NODATA,
    _glo30_strip_samples,
    _glo30_tile_index,
    _TileHandles,
)
from geofrea.grid_alignment.reference_grid import GridContext

logger = logging.getLogger(__name__)

_FABDEM_TILE_RE = re.compile(r"([NS])(\d{2})([EW])(\d{3})_FABDEM")
SOURCE_REPORT = "slope_dem_source.json"


def _fabdem_index(tiles: list) -> dict[tuple[int, int], Path]:
    index = {}
    for tile in tiles:
        m = _FABDEM_TILE_RE.search(Path(tile).name)
        if m is None:
            raise ValueError(f"{Path(tile).name!r} is not a FABDEM tile name")
        index[(int(m.group(2)) * (1 if m.group(1) == "N" else -1), int(m.group(4)) * (1 if m.group(3) == "E" else -1))] = Path(tile)
    return index


def slope_source_index(fabdem_tiles: list, glo30_tiles: list) -> tuple[dict[tuple[int, int], Path], list[tuple[int, int]]]:
    """(corner -> the file the slope of that square is read from, the corners that fall back to GLO-30).

    Every square of the GLO-30 list gets its FABDEM tile when there is one, its GLO-30 tile otherwise; a FABDEM tile of a square outside the GLO-30 list is not used.
    """
    fab, glo = _fabdem_index(fabdem_tiles), _glo30_tile_index(glo30_tiles)
    index, fallback = {}, []
    for corner, glo_path in glo.items():
        if corner in fab:
            index[corner] = fab[corner]
        else:
            index[corner] = glo_path
            fallback.append(corner)
    return index, sorted(fallback)


def _area_km2(grid: GridContext, rows: slice, cols: slice) -> float:
    """Geodesic area (km2) of the in-country pixels of a block of the grid (the pixel rule of `cells.pixel_row_area_km2`)."""
    res = abs(grid.transform.a)
    row_idx = np.arange(rows.start, rows.stop)
    lat_mid = grid.transform.f + (row_idx + 0.5) * grid.transform.e
    lat_km, lon_km = wgs84_km_per_degree(lat_mid)
    area_row = res * lon_km * abs(grid.transform.e) * lat_km
    return float((grid.country_mask[rows, cols] * area_row[:, None]).sum())


def fallback_report(grid: GridContext, fallback: list[tuple[int, int]], n_fabdem: int, source_index: dict) -> dict:
    """What the slope of a country rests on: the number of FABDEM squares, the squares that fall back to GLO-30 and the country area they cover (km2)."""
    res = abs(grid.transform.a)
    left, top = grid.transform.c, grid.transform.f
    fallback_km2 = 0.0
    for lat0, lon0 in fallback:
        r0 = max(0, int(np.floor((top - (lat0 + 1)) / res + 1e-9)))
        r1 = min(grid.height, int(np.ceil((top - lat0) / res - 1e-9)))
        c0 = max(0, int(np.floor((lon0 - left) / res + 1e-9)))
        c1 = min(grid.width, int(np.ceil((lon0 + 1 - left) / res - 1e-9)))
        if r1 > r0 and c1 > c0:
            fallback_km2 += _area_km2(grid, slice(r0, r1), slice(c0, c1))
    country_km2 = _area_km2(grid, slice(0, grid.height), slice(0, grid.width))
    return {
        "source": "FABDEM V1-2 slope, GLO-30 elevation",
        "squares": len(source_index),
        "squares_fabdem": n_fabdem,
        "squares_glo30_fallback": [f"{'N' if la >= 0 else 'S'}{abs(la):02d}{'E' if lo >= 0 else 'W'}{abs(lo):03d}" for la, lo in fallback],
        "fallback_area_km2": fallback_km2,
        "country_area_km2": country_km2,
        "fallback_share": fallback_km2 / country_km2 if country_km2 else 0.0,
    }


def fabdem_slope_outputs(
    fabdem_tiles: list,
    glo30_tiles: list,
    grid: GridContext,
    *,
    slope_out=None,
    counts_out=None,
    report_out=None,
    samples_per_degree: int | None = None,
    nodata_out: float = NODATA_FLOAT,
    checkpoint_dir: Path | None = None,
    checkpoint_key: str | None = None,
) -> dict[str, Path | None]:
    """The aligned mean slope and the slope bins of the grid from the FABDEM tiles (GLO-30 where a square has none), in one pass.

    Returns `{"slope": path or None, "slope_counts": path or None}`; None when that output was not asked for or no valid sample exists for it.
    With `checkpoint_dir` and `checkpoint_key` the finished result of every group of `_CHECKPOINT_UNIT_ROWS` grid rows is stored and taken again after an interruption
    (each row is a function of its own samples only, so the raster is the same, value for value, as in a run that was never stopped).

    Implements: M-F2a-07 (D-F2a-028).
    """
    index, fallback = slope_source_index(fabdem_tiles, glo30_tiles)
    n_fabdem = len(index) - len(fallback)
    report = fallback_report(grid, fallback, n_fabdem, index)
    if fallback:
        logger.warning(
            "slope: %d of %d 1 degree squares have no FABDEM tile and use GLO-30 (%.1f km2 of the country, %.2f %%): %s",
            len(fallback),
            len(index),
            report["fallback_area_km2"],
            100 * report["fallback_share"],
            ", ".join(report["squares_glo30_fallback"]),
        )
    if report_out is not None:
        write_text_atomic(Path(report_out), json.dumps(report, indent=1) + "\n")
    sp = samples_per_degree or _GLO30_SAMPLES_PER_DEGREE
    want_means, want_counts = slope_out is not None, counts_out is not None
    if not (want_means or want_counts):
        return {"slope": None, "slope_counts": None}

    width = grid.width
    block_rows = _OUTPUT_BLOCK_ROWS
    mean_profile = {
        "driver": "GTiff", "dtype": "float32", "width": width, "height": grid.height, "count": 1, "crs": grid.crs, "transform": grid.transform,
        "nodata": nodata_out, "compress": "lzw", "tiled": True, "blockxsize": 256, "blockysize": 256,
    }  # fmt: skip
    counts_profile = {
        "driver": "GTiff", "dtype": "uint16", "width": width, "height": grid.height, "count": SLOPE_BINS, "crs": grid.crs, "transform": grid.transform,
        "nodata": SLOPE_COUNT_NODATA, "compress": "deflate", "predictor": 2, "tiled": True, "blockxsize": 256, "blockysize": 256,
    }  # fmt: skip
    progress = PeriodicProgress(logger, -(-grid.height // _SLOPE_STRIP_GRID_ROWS), "slope and slope bins from FABDEM")
    streams: dict[str, RasterStream] = {}
    any_slope = any_counts = False
    written: dict[str, Path | None] = {"slope": None, "slope_counts": None}
    store = None
    if checkpoint_dir is not None and checkpoint_key is not None:
        store = CheckpointStore(
            checkpoint_dir,
            make_key(
                layer=checkpoint_key,
                outputs=[want_means, want_counts],
                block_rows=block_rows,
                unit_rows=_CHECKPOINT_UNIT_ROWS,
                strip_rows=_SLOPE_STRIP_GRID_ROWS,
                samples_per_degree=sp,
                nodata=nodata_out,
                shape=[grid.height, width],
            ),
            label="slope and slope bins from FABDEM",
        )

    def compute_unit(u0: int, u1: int, handles) -> tuple[dict[str, np.ndarray], dict[str, bool]]:
        """The final rows `u0:u1` of the mean slope and the bins."""
        rows_u = u1 - u0
        sums = np.zeros((rows_u, width)) if want_means else None
        n = np.zeros((rows_u, width), dtype=np.int64) if want_means else None
        counts = np.zeros((SLOPE_BINS, rows_u, width), dtype=np.uint16) if want_counts else None
        for r0 in range(u0, u1, _SLOPE_STRIP_GRID_ROWS):
            progress.step()
            r1 = min(r0 + _SLOPE_STRIP_GRID_ROWS, u1)
            strip = _glo30_strip_samples(index, grid, r0, r1, sp, handles)
            if strip is None:
                continue
            _, slope, grow, gcol = strip
            lo, hi = r0 - u0, r1 - u0
            if want_means:
                pixel = grow[:, None] * width + gcol[None, :]
                ok = np.isfinite(slope)
                if ok.any():
                    size = (r1 - r0) * width
                    total = np.bincount(pixel[ok], weights=slope[ok].astype(np.float64), minlength=size)
                    count = np.bincount(pixel[ok], minlength=size)
                    sums[lo:hi] = total.reshape(r1 - r0, width)
                    n[lo:hi] = count.reshape(r1 - r0, width)
            if want_counts:
                valid = np.isfinite(slope)
                if not valid.any():
                    continue
                bins = np.clip(np.floor(np.where(valid, slope, 0)), 0, SLOPE_BINS - 1).astype(np.int32)
                key = (grow[:, None] * width + gcol[None, :]) * SLOPE_BINS + bins
                flat = np.bincount(key[valid], minlength=(r1 - r0) * width * SLOPE_BINS)
                counts[:, lo:hi, :] = flat.reshape(r1 - r0, width, SLOPE_BINS).transpose(2, 0, 1).astype(np.uint16)
        outside = ~grid.country_mask[u0:u1]
        result: dict[str, np.ndarray] = {}
        flags = {"has_slope": False, "has_counts": False}
        if want_means:
            data = np.full((rows_u, width), nodata_out, dtype=np.float32)
            has = n > 0
            data[has] = (sums[has] / n[has]).astype(np.float32)
            data[outside] = nodata_out
            result["slope"] = data
            flags["has_slope"] = bool(n.any())
        if want_counts:
            flags["has_counts"] = bool(counts.any())
            counts[:, outside] = SLOPE_COUNT_NODATA
            result["counts"] = counts
        return result, flags

    resumed = 0
    with contextlib.ExitStack() as stack, contextlib.closing(_TileHandles()) as handles:
        if want_means:
            streams["slope"] = stack.enter_context(open_raster_stream(slope_out, **mean_profile))
        if want_counts:
            streams["slope_counts"] = stack.enter_context(open_raster_stream(counts_out, **counts_profile))
        for b0 in range(0, grid.height, block_rows):
            b1 = min(b0 + block_rows, grid.height)
            rows = b1 - b0
            block: dict[str, np.ndarray] = {}
            if want_means:
                block["slope"] = np.full((rows, width), nodata_out, dtype=np.float32)
            if want_counts:
                block["counts"] = np.zeros((SLOPE_BINS, rows, width), dtype=np.uint16)
            for u0 in range(b0, b1, _CHECKPOINT_UNIT_ROWS):
                u1 = min(u0 + _CHECKPOINT_UNIT_ROWS, b1)
                lo, hi = u0 - b0, u1 - b0
                unit = u0 // _CHECKPOINT_UNIT_ROWS
                stored = store.load_arrays(unit) if store is not None else None
                if stored is not None and all(stored[0].get(name) is not None and stored[0][name].shape[-2:] == (u1 - u0, width) for name in block):
                    result, flags = stored[0], stored[1]
                    resumed += 1
                    for _ in range(u1 - u0):
                        progress.step()
                else:
                    result, flags = compute_unit(u0, u1, handles)
                    if store is not None:
                        store.save_arrays(unit, result, flags)
                if want_means:
                    block["slope"][lo:hi] = result["slope"]
                    any_slope = any_slope or bool(flags["has_slope"])
                if want_counts:
                    block["counts"][:, lo:hi, :] = result["counts"]
                    any_counts = any_counts or bool(flags["has_counts"])
            window = Window(0, b0, width, rows)
            if want_means:
                streams["slope"].dataset.write(block["slope"], 1, window=window)
            if want_counts:
                streams["slope_counts"].dataset.write(block["counts"], window=window)
        if resumed:
            logger.info("slope and slope bins from FABDEM: %d groups of rows taken from the checkpoint.", resumed)
        if want_means and any_slope:
            streams["slope"].dataset.update_tags(source="FABDEM V1-2, mean of the 30 m samples per pixel (GLO-30 where a square has no tile)", samples_per_degree=str(sp))
            written["slope"] = streams["slope"].commit()
        if want_counts and any_counts:
            streams["slope_counts"].dataset.update_tags(
                slope_bins_deg="1", last_bin_open="true", samples_per_degree=str(sp), source="FABDEM V1-2 (GLO-30 where a square has no tile)"
            )
            written["slope_counts"] = streams["slope_counts"].commit()
    return written
