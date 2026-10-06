"""Raster reprojection/combination logic for the grid_alignment phase.

Ported from geoworld_framework's src/processors/grid_aligner.py
(`_reproject_to_grid()` L196-261, `_mosaic_land_cover()` L458-543)
with no logic changes — see docs/DECISIONS.md 2026-09-08,
grid_alignment Passo 3.

Wind products are aligned per height by `reproject_to_grid()` (M-F2a-04); the legacy AHP combination across heights
(`compute_ahp_weights`, `combine_wind_layers`) was removed in G-2 (2026-10-06).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import Window, from_bounds

from geofrea.core.constants import (
    KM_PER_DEG_LAT,
    NODATA_FLOAT,
    NODATA_UINT8,
)
from geofrea.core.raster_io import safe_raster_open, safe_raster_write
from geofrea.core.run_logging import PeriodicProgress
from geofrea.grid_alignment.reference_grid import GridContext

logger = logging.getLogger(__name__)


# Peak size of one source window read by reproject_to_grid(), in bytes of the source dtype. Bounds memory:
# BRA's population raster is (46814, 54172) float32 = 9.45 GiB, which a whole-raster read cannot allocate on
# a 6 GB machine (docs/phases/F2a_grid_alignment.md known issue, 2026-09-22).
_REPROJECT_WINDOW_BYTES = 400_000_000


def _source_window(src, grid: GridContext, row_start: int, row_end: int, pad_px: int) -> Window | None:
    """Window of `src` covering destination rows [row_start, row_end) plus `pad_px` pixels, or None if disjoint."""
    left, top = grid.transform * (0, row_start)
    right, bottom = grid.transform * (grid.width, row_end)
    bounds = transform_bounds(grid.crs, src.crs, left, bottom, right, top, densify_pts=21)
    win = from_bounds(*bounds, transform=src.transform)
    col_off = max(int(np.floor(win.col_off)) - pad_px, 0)
    row_off = max(int(np.floor(win.row_off)) - pad_px, 0)
    col_end = min(int(np.ceil(win.col_off + win.width)) + pad_px, src.width)
    row_end_src = min(int(np.ceil(win.row_off + win.height)) + pad_px, src.height)
    if col_end <= col_off or row_end_src <= row_off:
        return None
    return Window(col_off, row_off, col_end - col_off, row_end_src - row_off)


def reproject_to_grid(
    src_path,
    out_path,
    grid: GridContext,
    resampling: Resampling = Resampling.bilinear,
    nodata_out: float = NODATA_FLOAT,
    dtype_out: str = "float32",
    max_window_bytes: int = _REPROJECT_WINDOW_BYTES,
):
    """Reproject a source raster into the GridContext reference frame.

    The source is read through windows, never whole: the destination is processed in horizontal
    strips, each strip reading only the source window it covers (plus a pad wide enough for the
    resampling kernel, so strip seams give the same values as a single pass), sized so one window
    stays under `max_window_bytes`. A source whose window for the whole grid already fits is read
    in one piece.

    Args:
        src_path: Path to the source raster.
        out_path: Path for the reprojected output raster.
        grid: Target GridContext.
        resampling: Rasterio resampling algorithm.
        nodata_out: NoData value for the output raster.
        dtype_out: Output data type ("float32" or "uint8").
        max_window_bytes: Upper bound on one source window read, in bytes.

    Returns:
        Path to the reprojected output raster.
    """
    if dtype_out == "uint8":
        data_out = np.zeros((grid.height, grid.width), dtype=np.uint8)
        nd_out = int(nodata_out) if nodata_out else 0
    else:
        data_out = np.full((grid.height, grid.width), nodata_out, dtype=np.float32)
        nd_out = nodata_out

    with safe_raster_open(src_path) as src:
        src_nodata = src.nodata
        itemsize = np.dtype(src.dtypes[0]).itemsize
        # Pad: the resampling footprint (destination pixel size in source pixels) plus a margin.
        src_res = max(abs(src.transform.a), 1e-12)
        pad_px = int(np.ceil(abs(grid.transform.a) / src_res)) + 4

        # Data-integrity guard (docs/DECISIONS.md 2026-09-11, "elevation
        # NaN leak"): some source rasters declare a finite nodata
        # sentinel (e.g. -9999) but actually encode nodata as literal
        # IEEE NaN cells instead -- a mismatch between the file's own
        # metadata and its own data, not something GeoFREA writes (e.g.
        # BRA's raw elevation raster: 0 cells equal -9999, but ~26% are
        # literal NaN). GDAL's warp only recognises `src_nodata`, so
        # those NaN cells are treated as real elevation and
        # bilinear-blended into neighbouring destination pixels,
        # leaking actual NaN -- not `nodata_out` -- into the aligned
        # output. Fixed at the source (this function, shared by every
        # float raster grid_alignment reprojects) instead of papering
        # over the symptom in each downstream consumer. Inert whenever
        # the source has no such mismatch, and left alone when the
        # source's OWN declared nodata is itself NaN (some DEM products
        # legitimately encode nodata that way, and GDAL already handles
        # that case correctly). Applied per window now (not on a whole-raster read).
        sanitize_nan = dtype_out != "uint8" and src_nodata is not None and not np.isnan(src_nodata)

        full = _source_window(src, grid, 0, grid.height, pad_px)
        if full is not None:
            n_strips = max(1, int(np.ceil(full.width * full.height * itemsize / max_window_bytes)))
            strip_rows = int(np.ceil(grid.height / n_strips))
            nan_total = 0
            for row_start in range(0, grid.height, strip_rows):
                row_end = min(row_start + strip_rows, grid.height)
                win = _source_window(src, grid, row_start, row_end, pad_px)
                if win is None:
                    continue
                block = src.read(1, window=win)
                if sanitize_nan:
                    nan_mask = np.isnan(block)
                    if nan_mask.any():
                        nan_total += int(nan_mask.sum())
                        block = np.where(nan_mask, src_nodata, block).astype(block.dtype)
                reproject(
                    source=block,
                    destination=data_out[row_start:row_end],
                    src_transform=src.window_transform(win),
                    src_crs=src.crs,
                    dst_transform=grid.transform * rasterio.Affine.translation(0, row_start),
                    dst_crs=grid.crs,
                    resampling=resampling,
                    src_nodata=src_nodata,
                    dst_nodata=nd_out,
                )
            if nan_total:
                logger.warning(
                    "    %s: %d source pixels are literal NaN despite a finite "
                    "declared nodata (%s) -- sanitized to nodata before reproject.",
                    Path(src_path).name,
                    nan_total,
                    src_nodata,
                )

    data_out[~grid.country_mask] = nd_out

    profile = {
        "driver": "GTiff",
        "dtype": dtype_out,
        "width": grid.width,
        "height": grid.height,
        "count": 1,
        "crs": grid.crs,
        "transform": grid.transform,
        "nodata": nd_out,
        "compress": "lzw",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with safe_raster_write(out_path, **profile) as dst:
        dst.write(data_out, 1)

    return out_path


_SLOPE_BLOCK_HEIGHT = 512


def derive_slope_from_dem(dem_path, out_path):
    """Compute a slope-in-degrees raster from a DEM, at the DEM's own resolution.

    Ported from legacy geoworld_framework's
    src/processors/raster_processor.py::RasterProcessor.calculate_slope
    (L27-95), called by legacy main.py L598-609 on the RAW downloaded DEM
    BEFORE any reprojection. grid_alignment then reprojects this native
    output onto the reference grid with bilinear resampling, exactly like
    elevation — see run_grid_alignment_phase(). Computing slope on the
    native DEM and then resampling (rather than resampling the DEM first
    and computing slope on the target grid) is the legacy's deliberate
    order; kept as STRUCTURAL_PRESERVE (docs/DECISIONS.md 2026-09-11).

    Method (verbatim from legacy, STRUCTURAL_PRESERVE):
      - central-difference gradient via numpy.gradient, NOT the Horn
        8-neighbour method gdaldem uses;
      - latitude-corrected pixel spacing: dy = res_y * KM_PER_DEG_LAT *
        1000 (constant, N-S); dx = res_x * KM_PER_DEG_LAT * 1000 *
        cos(lat) per row (E-W, shrinks toward the poles);
      - slope_deg = degrees(arctan(hypot(dz/dx, dz/dy))) — degrees, not
        percent or radians;
      - processed in 512-row blocks with +/-1 row of padding so the
        gradient is correct across block seams; padding discarded before
        writing.

    Data-integrity correction (DELIBERATE DIVERGENCE from legacy — same
    class of fix applied this session to solar_pvout_weight and
    biomass_resource's land_cover==255; see docs/DECISIONS.md 2026-09-11):
    the legacy fed the raw nodata sentinel (-9999) into numpy.gradient as
    if it were a real elevation, so every VALID pixel adjacent to a
    nodata pixel got a garbage-contaminated slope. Here the DEM's nodata
    cells are set to NaN BEFORE the gradient, so NaN propagates one cell
    and any slope pixel whose stencil touched nodata is written as nodata
    rather than a wrong number. The output is then masked in two places:
    (1) where the gradient came out non-finite (the adjacency
    contamination the legacy left in), and (2) at the original nodata
    cells themselves — numpy.gradient's central difference never reads
    the centre cell, so a nodata centre still gets a finite gradient from
    its neighbours and must be re-masked, exactly as the legacy's final
    `slope_deg[elev == nodata] = nodata` did.

    Args:
        dem_path: Path to the source DEM raster (native resolution).
        out_path: Path to write the slope raster to.

    Returns:
        Path to the written slope raster (float32, degrees, LZW, tiled),
        or None if the DEM has fewer than 2 rows/columns (numpy.gradient
        needs at least 2 samples per axis).
    """
    with safe_raster_open(dem_path) as src:
        if src.height < 2 or src.width < 2:
            logger.warning(
                "    slope: DEM %sx%s too small for a gradient, skipping.",
                src.height, src.width,
            )
            return None

        res_x, res_y = src.res
        nodata_val = float(src.nodata) if src.nodata is not None else NODATA_FLOAT
        dy = res_y * KM_PER_DEG_LAT * 1000.0  # metres per pixel, N-S (constant)

        profile = src.profile.copy()
        profile.update(
            dtype=rasterio.float32,
            count=1,
            nodata=nodata_val,
            compress="lzw",
            tiled=True,
            blockxsize=256,
            blockysize=256,
        )

        with safe_raster_write(out_path, **profile) as dst:
            for y in range(0, src.height, _SLOPE_BLOCK_HEIGHT):
                h = min(_SLOPE_BLOCK_HEIGHT, src.height - y)

                win_y_start = max(0, y - 1)
                win_y_end = min(src.height, y + h + 1)
                win_h = win_y_end - win_y_start

                elev_block = src.read(
                    1, window=Window(0, win_y_start, src.width, win_h)
                ).astype(np.float32)

                # Data-integrity correction: exclude nodata from the
                # gradient entirely (NaN propagates one cell), instead of
                # the legacy's "let -9999 act as an elevation, mask the
                # centre afterwards".
                finite_in = np.isfinite(elev_block) & (elev_block != nodata_val)
                work = np.where(finite_in, elev_block, np.nan)

                rows_idx = np.arange(win_y_start, win_y_end)
                _xs, y_coords = src.xy(rows_idx, np.zeros(len(rows_idx)))
                lat_grid = np.asarray(y_coords, dtype=np.float64).reshape(-1, 1)
                dx_block = res_x * KM_PER_DEG_LAT * 1000.0 * np.cos(np.radians(lat_grid))

                dz_drow, dz_dcol = np.gradient(work, 1.0, 1.0)
                dz_dx = dz_dcol / dx_block
                dz_dy = dz_drow / dy

                slope_deg = np.degrees(np.arctan(np.sqrt(dz_dx**2 + dz_dy**2)))
                # (1) non-finite gradient = stencil touched nodata; (2)
                # the nodata cells themselves (gradient never reads the
                # centre, so they'd otherwise keep a neighbour-derived
                # value) — same final mask the legacy applied.
                slope_deg = np.where(
                    np.isfinite(slope_deg) & finite_in, slope_deg, nodata_val
                ).astype(np.float32)

                offset_top = 1 if y > 0 else 0
                final_block = slope_deg[offset_top : offset_top + h, :]
                dst.write(final_block, 1, window=Window(0, y, src.width, h))

    return out_path


_ESA_WORLDCOVER_TILE_ID_RE = re.compile(r"([NS])(\d{2})([EW])(\d{3})")
_ESA_WORLDCOVER_TILE_SIZE_DEG = 3.0


def _esa_worldcover_tile_bounds(filename: str) -> tuple[float, float, float, float] | None:
    """Nominal (left, bottom, right, top) bbox for an ESA WorldCover tile filename.

    Used ONLY as a fallback when a tile can't be opened at all
    (corrupted file), so its REAL bounds can't be read from its own
    metadata. ESA WorldCover bakes the tile's SW corner into every
    filename (e.g. "S36W060" in
    ESA_WorldCover_10m_2020_v100_S36W060_Map.tif) on the product's fixed
    3x3 degree tiling grid. Returns None if the filename doesn't match
    the expected pattern — footprint genuinely unknown then, not assumed
    safe.
    """
    m = _ESA_WORLDCOVER_TILE_ID_RE.search(filename)
    if m is None:
        return None
    ns, lat_str, ew, lon_str = m.groups()
    lat0 = float(lat_str) * (-1.0 if ns == "S" else 1.0)
    lon0 = float(lon_str) * (-1.0 if ew == "W" else 1.0)
    return (
        lon0,
        lat0,
        lon0 + _ESA_WORLDCOVER_TILE_SIZE_DEG,
        lat0 + _ESA_WORLDCOVER_TILE_SIZE_DEG,
    )


def _bbox_overlaps(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> bool:
    """True if two (left, bottom, right, top) bboxes intersect."""
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def mosaic_land_cover(lc_tiles: list, out_path, grid: GridContext, country_gdf):
    """Build an ESA WorldCover mosaic from multiple tiles.

    Reprojects and merges tiles onto the reference grid (nearest-
    neighbour). Tiles whose (real, opened) bounds don't overlap the
    country are skipped without being opened for reprojection.

    A tile that fails to open/read/reproject (corrupted file) is a
    different matter (docs/DECISIONS.md 2026-09-11, "mosaic_land_cover
    fail-loud on in-country gaps" — same fail-loud policy as the WDPA
    data-integrity check): if its footprint overlaps the country being
    processed, this raises rather than silently leaving that area at
    the mosaic's zero-initialized fill value (which is NOT the output
    raster's declared nodata — see `run_grid_alignment_phase`, which
    nodata-masks everything outside the country afterward, but never
    touches gaps left INSIDE it). A skipped tile that is genuinely
    outside the country (the common case — e.g. the 6 corrupted BRA
    tiles this session, all outside Brazil's mainland) is not an error;
    it is logged for traceability instead. Since a file that won't even
    open has no readable bounds of its own, that overlap check falls
    back to the tile's NOMINAL bounds parsed from its ESA WorldCover
    filename (`_esa_worldcover_tile_bounds`) — if the filename doesn't
    match the expected pattern either, the footprint is genuinely
    unknown and this degrades to the same warn-and-skip as before,
    rather than guessing.

    Args:
        lc_tiles: ESA WorldCover tile paths.
        out_path: Output path for the mosaicked raster.
        grid: Target GridContext.
        country_gdf: Country GeoDataFrame, for the tile-overlap bounds check.

    Returns:
        Path to the mosaicked land-cover raster, or None if no tile was used.

    Raises:
        RuntimeError: If a tile can't be read AND its footprint (real or
            nominal) overlaps the country being processed — the gap
            would otherwise be silent and indistinguishable from
            legitimate "no data here" downstream.
    """
    lc_out = np.zeros((grid.height, grid.width), dtype=np.uint8)
    bounds_main = tuple(float(b) for b in country_gdf.total_bounds)
    used = skipped = 0

    # A periodic INFO line (COMMAND ADJ-7), not a progress bar: this loop
    # has taken up to ~66 minutes for BRA (155 tiles), and a bar's
    # carriage-return redraw is unreadable once the console is
    # redirected to a log file (CONVENTIONS.md "Long-running scripts").
    progress = PeriodicProgress(logger, len(lc_tiles), "land_cover mosaic")

    for tile in lc_tiles:
        progress.step()
        tile_path = Path(tile)
        tile_bounds: tuple[float, float, float, float] | None = None
        try:
            with rasterio.open(str(tile)) as src:
                tile_bounds = tuple(float(b) for b in src.bounds)
                if not _bbox_overlaps(tile_bounds, bounds_main):
                    skipped += 1
                    continue

                tile_reprojected = np.zeros((grid.height, grid.width), dtype=np.uint8)
                reproject(
                    source=rasterio.band(src, 1),
                    destination=tile_reprojected,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=grid.transform,
                    dst_crs=grid.crs,
                    resampling=Resampling.nearest,
                    src_nodata=0,
                    dst_nodata=0,
                    warp_mem_limit=1024,
                )
                mask_fill = (tile_reprojected > 0) & (lc_out == 0)
                lc_out[mask_fill] = tile_reprojected[mask_fill]
                used += 1
        except Exception as exc:
            footprint = tile_bounds or _esa_worldcover_tile_bounds(tile_path.name)
            if footprint is not None and _bbox_overlaps(footprint, bounds_main):
                raise RuntimeError(
                    f"mosaic_land_cover: tile {tile_path.name!r} could not be read "
                    f"({type(exc).__name__}: {exc}), and its {'real' if tile_bounds else 'nominal'} "
                    f"footprint {footprint} overlaps the country being mosaicked — this "
                    "would silently leave a land-cover coverage gap inside the study "
                    "area. Fix or remove the file."
                ) from exc
            skipped += 1
            logger.warning(
                "    Land cover tile %s could not be read (%s: %s) — skipped (%s).",
                tile_path.name,
                type(exc).__name__,
                exc,
                "no bbox overlap with the country"
                if footprint is not None
                else "footprint unknown, filename didn't match the expected tile pattern",
            )

    logger.info("    Land cover mosaic: %d tiles used, %d skipped.", used, skipped)

    if used == 0:
        return None

    lc_out[~grid.country_mask] = NODATA_UINT8

    profile = {
        "driver": "GTiff",
        "dtype": "uint8",
        "width": grid.width,
        "height": grid.height,
        "count": 1,
        "crs": grid.crs,
        "transform": grid.transform,
        "nodata": NODATA_UINT8,
        "compress": "lzw",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with safe_raster_write(out_path, **profile) as dst:
        dst.write(lc_out, 1)

    return out_path
