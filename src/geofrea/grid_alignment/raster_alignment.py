"""Raster reprojection/combination logic for the grid_alignment phase.

Ported from geoworld_framework's src/processors/grid_aligner.py
(`_reproject_to_grid()` L196-261, `_compute_ahp_weights()` L268-287,
`_combine_wind_layers()` L290-455, `_mosaic_land_cover()` L458-543)
with no logic changes — see docs/DECISIONS.md 2026-09-08,
grid_alignment Passo 3.

`_compute_ahp_weights()`/`_combine_wind_layers()` consume
WIND_AHP_MATRIX/AHP_RANDOM_INDEX (core/constants.py) as-is. Reviewed in
detail 2026-09-09 (see that module's own comment block and
docs/DECISIONS.md same date, grid_alignment Passo 4 item 4) — kept
STRUCTURAL_PRESERVE: the RC/0.10-threshold machinery is
literature-grounded (Saaty, 1980), the specific pairwise judgments are
unsourced but plausible, flagged as an open question for when
suitability_criteria (Phase 3) is designed, not a blocker here.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from rasterio.windows import Window

from geofrea.core.constants import (
    AHP_RANDOM_INDEX,
    KM_PER_DEG_LAT,
    NODATA_FLOAT,
    NODATA_UINT8,
    WIND_AHP_MATRIX,
    WIND_HEIGHT_KEYS,
)
from geofrea.core.raster_io import safe_raster_open, safe_raster_write
from geofrea.grid_alignment.reference_grid import GridContext

logger = logging.getLogger(__name__)


def reproject_to_grid(
    src_path,
    out_path,
    grid: GridContext,
    resampling: Resampling = Resampling.bilinear,
    nodata_out: float = NODATA_FLOAT,
    dtype_out: str = "float32",
):
    """Reproject a source raster into the GridContext reference frame.

    Args:
        src_path: Path to the source raster.
        out_path: Path for the reprojected output raster.
        grid: Target GridContext.
        resampling: Rasterio resampling algorithm.
        nodata_out: NoData value for the output raster.
        dtype_out: Output data type ("float32" or "uint8").

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
        source = rasterio.band(src, 1)

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
        # that case correctly).
        if dtype_out != "uint8" and src_nodata is not None and not np.isnan(src_nodata):
            src_array = src.read(1)
            nan_mask = np.isnan(src_array)
            if nan_mask.any():
                logger.warning(
                    "    %s: %d source pixels are literal NaN despite a finite "
                    "declared nodata (%s) -- sanitizing to nodata before reproject.",
                    Path(src_path).name,
                    int(nan_mask.sum()),
                    src_nodata,
                )
                source = np.where(nan_mask, src_nodata, src_array).astype(src_array.dtype)

        reproject(
            source=source,
            destination=data_out,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=grid.transform,
            dst_crs=grid.crs,
            resampling=resampling,
            src_nodata=src_nodata,
            dst_nodata=nd_out,
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


def compute_ahp_weights(matrix: np.ndarray) -> tuple[np.ndarray, float]:
    """Compute AHP weights via the Principal Eigenvector method.

    Args:
        matrix: Saaty pairwise comparison matrix (n x n).

    Returns:
        Tuple of (normalized weight vector, Consistency Ratio).
    """
    col_sum = matrix.sum(axis=0)
    weights = (matrix / col_sum).mean(axis=1)
    lam_max = float((matrix @ weights / weights).mean())
    n = matrix.shape[0]
    ci = (lam_max - n) / (n - 1)
    # AHP_RANDOM_INDEX (Saaty, 1980) confirmed literature-standard, not
    # arbitrary — see docs/DECISIONS.md 2026-09-09, grid_alignment
    # Passo 4 item 4.
    ri = AHP_RANDOM_INDEX.get(n, 1.12)
    rc = ci / ri if ri > 0 else 0.0
    return weights, rc


def combine_wind_layers(wind_paths: list, out_path, grid: GridContext):
    """Aggregate multiple wind-height rasters using AHP-derived weights.

    Handles flexible naming: each path's height is parsed from its
    filename (WIND_HEIGHT_KEYS), falling back to "100m" for the first
    unidentified file and discarding the rest.

    Args:
        wind_paths: Wind raster paths (50m/100m/200m variants).
        out_path: Output path for the aggregated wind raster.
        grid: Target GridContext.

    Returns:
        Path to the aggregated wind raster.

    Raises:
        ValueError: If wind_paths is empty or no file could be mapped
            to a recognized height key.
    """
    if not wind_paths:
        raise ValueError("No wind raster paths provided")

    mapped: dict[str, object] = {}

    for p in wind_paths:
        name_lower = p.name.lower()
        matched = False

        for key in WIND_HEIGHT_KEYS:
            if key in name_lower:
                mapped[key] = p
                matched = True
                logger.info("    Wind layer '%s' -> %s", p.name, key)
                break

        if not matched:
            if len(mapped) == 0:
                mapped["100m"] = p
                logger.warning(
                    "    Wind layer '%s' unidentified -> defaulting to 100m.", p.name
                )
            else:
                logger.warning(
                    "    Wind layer '%s' discarded (filename does not contain a "
                    "standard height key).",
                    p.name,
                )

    if not mapped:
        raise ValueError("No wind files were successfully mapped.")

    present = list(mapped.keys())

    # WIND_AHP_MATRIX reviewed 2026-09-09 (see core/constants.py's own
    # comment block) — kept as-is, STRUCTURAL_PRESERVE, pairwise
    # judgments unsourced but flagged as an open question, not a blocker.
    if len(present) == 3:
        matrix = np.array(WIND_AHP_MATRIX, dtype=np.float64)
        w_arr, rc = compute_ahp_weights(matrix)
        weight_map = dict(zip(WIND_HEIGHT_KEYS, w_arr))
        if rc > 0.10:
            logger.warning("    RC=%.3f > 0.10 -> falling back to uniform weights.", rc)
            weight_map = {k: 1.0 / len(present) for k in present}
    else:
        weight_map = {k: 1.0 / len(present) for k in present}

    logger.info("    Combining %d wind layers: %s", len(present), ", ".join(present))

    combined = np.zeros((grid.height, grid.width), dtype=np.float64)
    weight_acc = np.zeros((grid.height, grid.width), dtype=np.float64)

    for key in present:
        logger.info("    Reprojecting %s...", key)
        layer = np.full((grid.height, grid.width), NODATA_FLOAT, dtype=np.float32)

        with safe_raster_open(mapped[key]) as src:
            reproject(
                source=rasterio.band(src, 1),
                destination=layer,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=grid.transform,
                dst_crs=grid.crs,
                resampling=Resampling.bilinear,
                src_nodata=src.nodata,
                dst_nodata=NODATA_FLOAT,
            )

        valid = (layer != NODATA_FLOAT) & np.isfinite(layer) & (layer >= 0)

        w = weight_map[key]
        combined[valid] += layer[valid].astype(np.float64) * w
        weight_acc[valid] += w

    result = np.full((grid.height, grid.width), NODATA_FLOAT, dtype=np.float32)
    has = weight_acc > 0
    result[has] = (combined[has] / weight_acc[has]).astype(np.float32)
    result[~grid.country_mask] = NODATA_FLOAT

    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "width": grid.width,
        "height": grid.height,
        "count": 1,
        "crs": grid.crs,
        "transform": grid.transform,
        "nodata": NODATA_FLOAT,
        "compress": "lzw",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with safe_raster_write(out_path, **profile) as dst:
        dst.write(result, 1)

    return out_path


def mosaic_land_cover(lc_tiles: list, out_path, grid: GridContext, country_gdf):
    """Build an ESA WorldCover mosaic from multiple tiles.

    Reprojects and merges tiles onto the reference grid (nearest-
    neighbour). Tiles whose bounds don't overlap the country are
    skipped without being opened for reprojection; tiles that fail to
    open (corrupted file) are also skipped, not fatal to the mosaic —
    same defensive behavior data_quality_audit's
    inspect_land_cover_tiles() already has for the same known data gap
    (see docs/DECISIONS.md 2026-09-08, "wire das 5 camadas restantes",
    Fase 2, ACHADO REAL 3 — 6 corrupted BRA tiles).

    Args:
        lc_tiles: ESA WorldCover tile paths.
        out_path: Output path for the mosaicked raster.
        grid: Target GridContext.
        country_gdf: Country GeoDataFrame, for the tile-overlap bounds check.

    Returns:
        Path to the mosaicked land-cover raster, or None if no tile was used.
    """
    lc_out = np.zeros((grid.height, grid.width), dtype=np.uint8)
    bounds_main = tuple(float(b) for b in country_gdf.total_bounds)
    used = skipped = 0

    for tile in lc_tiles:
        try:
            with rasterio.open(str(tile)) as src:
                tile_bounds = tuple(src.bounds)
                if (
                    tile_bounds[2] < bounds_main[0]
                    or tile_bounds[0] > bounds_main[2]
                    or tile_bounds[3] < bounds_main[1]
                    or tile_bounds[1] > bounds_main[3]
                ):
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
        except Exception:  # noqa: BLE001 — one bad/corrupted tile must not abort the mosaic
            skipped += 1

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
