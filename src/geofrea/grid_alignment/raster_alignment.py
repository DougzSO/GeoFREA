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
    NODATA_FLOAT,
    NODATA_UINT8,
)
from geofrea.core.geodesy import wgs84_km_per_degree
from geofrea.core.raster_io import safe_raster_open, safe_raster_write
from geofrea.core.run_logging import PeriodicProgress
from geofrea.grid_alignment.reference_grid import GridContext

logger = logging.getLogger(__name__)


# Peak size of one source window read by reproject_to_grid(), in bytes of the source dtype. Bounds memory:
# BRA's population raster is (46814, 54172) float32 = 9.45 GiB, which a whole-raster read cannot allocate on
# a 6 GB machine (docs/phases/F2a_grid_alignment.md known issue, 2026-09-22).
_REPROJECT_WINDOW_BYTES = 400_000_000


class MissingSourceCrsError(ValueError):
    """A source raster has no CRS and the caller supplied none (A-09: never guess a projection)."""


def _source_window(src, grid: GridContext, row_start: int, row_end: int, pad_px: int, src_crs) -> Window | None:
    """Window of `src` covering destination rows [row_start, row_end) plus `pad_px` pixels, or None if disjoint."""
    left, top = grid.transform * (0, row_start)
    right, bottom = grid.transform * (grid.width, row_end)
    bounds = transform_bounds(grid.crs, src_crs, left, bottom, right, top, densify_pts=21)
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
    src_crs=None,
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
        src_crs: CRS to use when the source file declares none (the caller must have verified it; see
            alignment.py::_gwa_crs_for). A source with no CRS and no `src_crs` raises MissingSourceCrsError.

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
        crs_in = src.crs or src_crs
        if crs_in is None:
            raise MissingSourceCrsError(f"{src_path}: the raster declares no CRS and none was supplied")
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

        full = _source_window(src, grid, 0, grid.height, pad_px, crs_in)
        if full is not None:
            n_strips = max(1, int(np.ceil(full.width * full.height * itemsize / max_window_bytes)))
            strip_rows = int(np.ceil(grid.height / n_strips))
            nan_total = 0
            for row_start in range(0, grid.height, strip_rows):
                row_end = min(row_start + strip_rows, grid.height)
                win = _source_window(src, grid, row_start, row_end, pad_px, crs_in)
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
                    src_crs=crs_in,
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

    Method (STRUCTURAL_PRESERVE except the pixel spacing, see G-1 below):
      - central-difference gradient via numpy.gradient, NOT the Horn
        8-neighbour method gdaldem uses;
      - GEODESIC pixel spacing per row (M-F2a-02, G-1, 2026-10-06): the
        metres per degree of latitude and longitude at the row's latitude
        come from core.geodesy.wgs84_km_per_degree() (WGS84 ellipsoid), so
        dy = res_y * lat_m(lat) and dx = res_x * lon_m(lat). The legacy
        used one flat constant (111.32 km/deg) for dy and 111.32*cos(lat)
        for dx, a spherical approximation that the rest of F2a no longer
        uses;
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
                lat_km, lon_km = wgs84_km_per_degree(lat_grid)
                dx_block = res_x * lon_km * 1000.0  # metres per pixel, E-W, at each row's latitude
                dy_block = res_y * lat_km * 1000.0  # metres per pixel, N-S, at each row's latitude

                dz_drow, dz_dcol = np.gradient(work, 1.0, 1.0)
                dz_dx = dz_dcol / dx_block
                dz_dy = dz_drow / dy_block

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


SLOPE_BINS = 41  # 1 degree bins 0-1 ... 39-40 and a last one for 40 degrees and above
SLOPE_COUNT_NODATA = 65535
_GLO30_SAMPLES_PER_DEGREE = 3600
_GLO30_TILE_RE = re.compile(r"_([NS])(\d{2})_00_([EW])(\d{3})_00_DEM")
_SLOPE_STRIP_GRID_ROWS = 4


def _glo30_tile_index(tiles: list) -> dict[tuple[int, int], Path]:
    """South-west corner (lat0, lon0) -> path, from the Copernicus GLO-30 file names."""
    index = {}
    for tile in tiles:
        m = _GLO30_TILE_RE.search(Path(tile).name)
        if m is None:
            raise ValueError(f"{Path(tile).name!r} is not a Copernicus GLO-30 tile name")
        lat0 = int(m.group(2)) * (1 if m.group(1) == "N" else -1)
        lon0 = int(m.group(4)) * (1 if m.group(3) == "E" else -1)
        index[(lat0, lon0)] = Path(tile)
    return index


def _read_dem_block(index: dict[tuple[int, int], Path], g0: int, g1: int, c0: int, c1: int, sp: int) -> np.ndarray:
    """DEM samples for global rows g0..g1-1 and columns c0..c1-1 (NaN where no tile covers them).

    Global indices count samples from 90 N and 180 W: row G has its centre at latitude 90 - G/sp, column C at longitude
    C/sp - 180, which is how a GLO-30 tile lays out its samples (the first sample of a tile sits on its integer corner).
    """
    out = np.full((g1 - g0, c1 - c0), np.nan, dtype=np.float32)
    for lat0 in range(int(np.floor(90 - g1 / sp)), int(np.ceil(90 - g0 / sp)) + 1):
        for lon0 in range(int(np.floor(c0 / sp - 180)), int(np.ceil(c1 / sp - 180)) + 1):
            path = index.get((lat0, lon0))
            if path is None:
                continue
            tg0, tc0 = (90 - (lat0 + 1)) * sp, (lon0 + 180) * sp  # global index of the tile's first sample
            r0, r1 = max(g0, tg0), min(g1, tg0 + sp)
            q0, q1 = max(c0, tc0), min(c1, tc0 + sp)
            if r0 >= r1 or q0 >= q1:
                continue
            with rasterio.open(path) as src:
                if (src.height, src.width) != (sp, sp):
                    raise ValueError(f"{Path(path).name}: expected {sp} x {sp} samples, got {src.height} x {src.width}")
                block = src.read(1, window=Window(q0 - tc0, r0 - tg0, q1 - q0, r1 - r0)).astype(np.float32)
                if src.nodata is not None:
                    block[block == src.nodata] = np.nan
            out[r0 - g0 : r1 - g0, q0 - c0 : q1 - c0] = block
    return out


def slope_class_counts(
    dem_tiles: list, out_path, grid: GridContext, samples_per_degree: int = _GLO30_SAMPLES_PER_DEGREE
):
    """Per grid pixel, how many 30 m DEM samples have a slope in each 1 degree bin (D-F2a-016).

    Slope is computed on the native 30 m samples (central differences with WGS84 geodesic spacing per row, as in
    `derive_slope_from_dem`) and each sample is counted into the grid pixel that contains its centre; centres exactly on a pixel
    edge go to the pixel below and to the east. Band i holds the samples with slope in [i, i+1) degrees; the last band holds
    40 degrees and above. A sample whose stencil touches a missing value is counted in no band, so a pixel with no valid sample
    has all bands zero. Because the slope is kept as a distribution, the share above any threshold can be read later, which is
    what lets the slope maximum be a range. Pixels outside the country are SLOPE_COUNT_NODATA. Returns the output path, or
    None if no sample was valid.
    """
    index = _glo30_tile_index(dem_tiles)
    sp = samples_per_degree
    res = abs(grid.transform.a)
    g_left, g_top = grid.transform.c, grid.transform.f
    counts = np.zeros((SLOPE_BINS, grid.height, grid.width), dtype=np.uint16)
    progress = PeriodicProgress(logger, -(-grid.height // _SLOPE_STRIP_GRID_ROWS), "slope class counts")
    for r0 in range(0, grid.height, _SLOPE_STRIP_GRID_ROWS):
        progress.step()
        r1 = min(r0 + _SLOPE_STRIP_GRID_ROWS, grid.height)
        lat_hi, lat_lo = g_top - r0 * res, g_top - r1 * res
        g_lo = int(np.floor((90 - lat_hi) * sp)) - 1
        g_hi = int(np.ceil((90 - lat_lo) * sp)) + 1
        c_lo = int(np.floor((g_left + 180) * sp)) - 1
        c_hi = int(np.ceil((g_left + grid.width * res + 180) * sp)) + 1
        z = _read_dem_block(index, g_lo - 1, g_hi + 1, c_lo - 1, c_hi + 1, sp)  # one extra sample all round for the stencil
        if not np.isfinite(z).any():
            continue
        lat_c = 90 - np.arange(g_lo - 1, g_hi + 1) / sp
        lat_km, lon_km = wgs84_km_per_degree(lat_c.reshape(-1, 1))
        dz_drow, dz_dcol = np.gradient(z, 1.0, 1.0)
        dz_dy = -dz_drow / (lat_km * 1000.0 / sp)  # rows run southwards
        dz_dx = dz_dcol / (lon_km * 1000.0 / sp)
        slope = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy)))[1:-1, 1:-1]
        slope[~np.isfinite(z[1:-1, 1:-1])] = np.nan
        rows_c = 90 - np.arange(g_lo, g_hi) / sp
        cols_c = np.arange(c_lo, c_hi) / sp - 180
        grow = np.floor((g_top - rows_c) / res + 1e-6).astype(np.int64) - r0
        gcol = np.floor((cols_c - g_left) / res + 1e-6).astype(np.int64)
        keep_r, keep_c = (grow >= 0) & (grow < r1 - r0), (gcol >= 0) & (gcol < grid.width)
        sub = slope[np.ix_(keep_r, keep_c)]
        valid = np.isfinite(sub)
        if not valid.any():
            continue
        bins = np.clip(np.floor(np.where(valid, sub, 0)), 0, SLOPE_BINS - 1).astype(np.int32)
        key = (grow[keep_r][:, None] * grid.width + gcol[keep_c][None, :]) * SLOPE_BINS + bins
        flat = np.bincount(key[valid], minlength=(r1 - r0) * grid.width * SLOPE_BINS)
        counts[:, r0:r1, :] = flat.reshape(r1 - r0, grid.width, SLOPE_BINS).transpose(2, 0, 1).astype(np.uint16)
    if not counts.any():
        return None
    counts[:, ~grid.country_mask] = SLOPE_COUNT_NODATA
    profile = {
        "driver": "GTiff",
        "dtype": "uint16",
        "width": grid.width,
        "height": grid.height,
        "count": SLOPE_BINS,
        "crs": grid.crs,
        "transform": grid.transform,
        "nodata": SLOPE_COUNT_NODATA,
        "compress": "deflate",
        "predictor": 2,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with safe_raster_write(out_path, **profile) as dst:
        dst.write(counts)
        dst.update_tags(slope_bins_deg="1", last_bin_open="true", samples_per_degree=str(sp))
    return Path(out_path)


WORLDCOVER_CLASSES = (10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100)
LAND_COVER_COUNT_NODATA = 65535
_STRIP_GRID_ROWS = 8  # grid rows read at once from a tile (8 x 120 source rows)


def _exact_block_factor(src, grid: GridContext) -> int | None:
    """k if the grid pixel is k x k source pixels and the tile edges sit on grid pixel edges (exact block counting), else None."""
    grid_res = abs(grid.transform.a)
    t_res = abs(src.transform.a)
    k = round(grid_res / t_res)
    if k < 1 or abs(k * t_res - grid_res) > 1e-9 * grid_res or abs(abs(src.transform.e) - t_res) > 1e-12:
        return None
    off_c = (src.transform.c - grid.transform.c) / grid_res
    off_r = (grid.transform.f - src.transform.f) / grid_res
    if abs(off_c - round(off_c)) > 1e-6 or abs(off_r - round(off_r)) > 1e-6:
        return None
    return k


def _count_exact(src, counts: np.ndarray, grid: GridContext, k: int, lut: np.ndarray) -> bool:
    """Block-count one tile into `counts` (class bands only); False if the tile does not touch the grid."""
    n_classes = len(WORLDCOVER_CLASSES)
    c_t = round((src.transform.c - grid.transform.c) / abs(grid.transform.a))
    r_t = round((grid.transform.f - src.transform.f) / abs(grid.transform.a))
    t_cols, t_rows = src.width // k, src.height // k
    gr0, gr1 = max(r_t, 0), min(r_t + t_rows, grid.height)
    gc0, gc1 = max(c_t, 0), min(c_t + t_cols, grid.width)
    if gr0 >= gr1 or gc0 >= gc1:
        return False
    n_c = gc1 - gc0
    rb = (np.arange(_STRIP_GRID_ROWS * k) // k)[:, None]
    cb = (np.arange(n_c * k) // k)[None, :]
    base = ((rb * n_c + cb) * (n_classes + 1)).astype(np.int32)
    for r in range(gr0, gr1, _STRIP_GRID_ROWS):
        nr = min(_STRIP_GRID_ROWS, gr1 - r)
        win = Window((gc0 - c_t) * k, (r - r_t) * k, n_c * k, nr * k)
        key = lut[src.read(1, window=win)].astype(np.int32) + base[: nr * k]
        per = np.bincount(key.ravel(), minlength=nr * n_c * (n_classes + 1)).reshape(nr, n_c, n_classes + 1)
        for i in range(n_classes):
            counts[i, r : r + nr, gc0:gc1] = per[:, :, i + 1]
    return True


def _count_by_centre(src, counts: np.ndarray, grid: GridContext, lut: np.ndarray) -> bool:
    """Count one tile into `counts` (class bands plus a last band for samples of no class) by the grid pixel holding each
    sample's centre; used when the tile pixel is not a whole fraction of the grid pixel. Counts are then approximate at pixel
    edges (a sample belongs wholly to one pixel) and the number of samples per pixel varies slightly."""
    n_bands = counts.shape[0]
    res = abs(grid.transform.a)
    tr = src.transform
    cols_c = tr.c + (np.arange(src.width) + 0.5) * tr.a
    gcol = np.floor((cols_c - grid.transform.c) / res + 1e-9).astype(np.int64)
    col_ok = np.flatnonzero((gcol >= 0) & (gcol < grid.width))
    if col_ok.size == 0:
        return False
    c_lo, c_hi = int(col_ok[0]), int(col_ok[-1]) + 1
    touched = False
    for r0 in range(0, src.height, 256):
        r1 = min(r0 + 256, src.height)
        rows_c = tr.f + (np.arange(r0, r1) + 0.5) * tr.e
        grow = np.floor((grid.transform.f - rows_c) / res + 1e-9).astype(np.int64)
        row_ok = np.flatnonzero((grow >= 0) & (grow < grid.height))
        if row_ok.size == 0:
            continue
        a0, a1 = int(row_ok[0]), int(row_ok[-1]) + 1
        block = src.read(1, window=Window(c_lo, r0 + a0, c_hi - c_lo, a1 - a0))
        g_rows = grow[a0:a1]
        gr_min, gr_max = int(g_rows.min()), int(g_rows.max())
        nr = gr_max - gr_min + 1
        key = ((g_rows - gr_min)[:, None] * grid.width + gcol[c_lo:c_hi][None, :]) * n_bands + lut[block].astype(np.int64)
        per = np.bincount(key.ravel(), minlength=nr * grid.width * n_bands).reshape(nr, grid.width, n_bands)
        counts[:, gr_min : gr_max + 1, :] += per.transpose(2, 0, 1).astype(np.uint16)
        touched = True
    return touched


def land_cover_class_counts(lc_tiles: list, out_path, grid: GridContext, country_gdf):
    """Per grid pixel, how many ESA WorldCover samples fall in each class (D-F2a-015).

    The point-sample mosaic (`mosaic_land_cover`) labels a 1.1 km pixel with the class of the one source sample under
    its centre, which makes every cell share noisy (about +-10 percentage points at a 50 % share). Here the samples under each
    pixel are counted instead: band i holds the number of samples of class WORLDCOVER_CLASSES[i] (uint16).

    Two modes, chosen per country from the tile headers: when every in-country tile is an exact fraction of the grid pixel and on
    its edges (the 10 m global tiles on the 0.05 degree lattice: 120 x 120 samples per 0.01 degree pixel), the count is an exact
    block count and samples of no class (open sea) are in no band (the tag `samples_per_pixel` gives the full pixel). Otherwise
    (for IND the tiles hold about 100 m samples, 0.000898 degree) each sample is counted into the pixel containing its centre,
    and an extra last band counts samples of no class, so the bands of a pixel always sum to its sample count (tag
    `samples_per_pixel` is then 0). Pixels outside the country are LAND_COVER_COUNT_NODATA in every band. A tile that cannot be
    read but overlaps the country raises, as in `mosaic_land_cover`. Returns the output path, or None if no tile overlapped.
    """
    bounds_main = tuple(float(b) for b in country_gdf.total_bounds)
    n_classes = len(WORLDCOVER_CLASSES)
    in_country = []
    exact_k: set[int | None] = set()
    for tile in lc_tiles:
        tile_path = Path(tile)
        tile_bounds = None
        try:
            with rasterio.open(str(tile)) as src:
                tile_bounds = tuple(float(b) for b in src.bounds)
                if _bbox_overlaps(tile_bounds, bounds_main):
                    in_country.append(tile_path)
                    exact_k.add(_exact_block_factor(src, grid))
        except Exception as exc:
            footprint = tile_bounds or _esa_worldcover_tile_bounds(tile_path.name)
            if footprint is not None and _bbox_overlaps(footprint, bounds_main):
                raise RuntimeError(
                    f"land_cover_class_counts: tile {tile_path.name!r} could not be read ({type(exc).__name__}: {exc}) and its "
                    f"footprint {footprint} overlaps the country, which would leave a coverage gap."
                ) from exc
            logger.warning("    Land cover tile %s skipped (%s: %s).", tile_path.name, type(exc).__name__, exc)
    if not in_country:
        return None
    exact = None not in exact_k and len(exact_k) == 1
    n_bands = n_classes if exact else n_classes + 1
    counts = np.zeros((n_bands, grid.height, grid.width), dtype=np.uint16)
    lut = np.zeros(256, dtype=np.uint8)  # exact mode: 0 = no class, i + 1 = class i; centre mode: class i, no class = last band
    if exact:
        for i, cls in enumerate(WORLDCOVER_CLASSES):
            lut[cls] = i + 1
    else:
        lut[:] = n_classes
        for i, cls in enumerate(WORLDCOVER_CLASSES):
            lut[cls] = i
    progress = PeriodicProgress(logger, len(in_country), "land_cover class counts")
    used = 0
    for tile_path in in_country:
        progress.step()
        with rasterio.open(str(tile_path)) as src:
            if exact:
                touched = _count_exact(src, counts, grid, next(iter(exact_k)), lut)
            else:
                touched = _count_by_centre(src, counts, grid, lut)
        used += int(touched)
    logger.info("    Land cover class counts (%s): %d tiles used.", "exact blocks" if exact else "by sample centre", used)
    if used == 0:
        return None
    spp = next(iter(exact_k)) ** 2 if exact else 0
    counts[:, ~grid.country_mask] = LAND_COVER_COUNT_NODATA
    profile = {
        "driver": "GTiff",
        "dtype": "uint16",
        "width": grid.width,
        "height": grid.height,
        "count": n_bands,
        "crs": grid.crs,
        "transform": grid.transform,
        "nodata": LAND_COVER_COUNT_NODATA,
        "compress": "deflate",
        "predictor": 2,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with safe_raster_write(out_path, **profile) as dst:
        dst.write(counts)
        dst.update_tags(
            worldcover_classes=",".join(str(c) for c in [*WORLDCOVER_CLASSES, *([] if exact else [0])]), samples_per_pixel=str(spp)
        )
    return Path(out_path)



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
