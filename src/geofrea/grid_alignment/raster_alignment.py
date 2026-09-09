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

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject

from geofrea.core.constants import (
    AHP_RANDOM_INDEX,
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
        reproject(
            source=rasterio.band(src, 1),
            destination=data_out,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=grid.transform,
            dst_crs=grid.crs,
            resampling=resampling,
            src_nodata=src.nodata,
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
