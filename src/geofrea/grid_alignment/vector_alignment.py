"""Vector rasterization/distance-transform logic for the grid_alignment phase.

Ported from geoworld_framework's src/processors/grid_aligner.py
(`_calculate_wgs84_isotropic_distance()` L550-594, `_align_linear_features()`
L597-681, `_align_lakes()` L684-739, `_align_rivers()` L742-800,
`_align_plants()` L803-879) — see docs/DECISIONS.md 2026-09-08,
grid_alignment Passo 3.

Load/clip split from legacy (per Passo 1's design correction, same
DECISIONS.md date): legacy's `_align_linear_features()`/`_align_lakes()`/
`_align_rivers()` each called `_load_and_clip_vector_data()` (a bbox
read + CRS reproject) internally before rasterizing. Here, that call is
moved OUT to the caller (alignment.py):
  - roads/lakes/rivers (global source files) arrive as an
    ALREADY-CLIPPED GeoDataFrame, produced by the caller via
    core.geo_utils.read_clipped_to_country() against the same on-disk
    cache_path convention data_quality_audit's audit.py uses — see
    schemas.py's module docstring for the full rationale.
  - grid (already country-scoped at the acquisition source) is loaded
    via load_vector_bbox() below, a near-verbatim port of legacy's
    `_load_and_clip_vector_data()` — a lightweight bbox prefilter with
    no exact-intersection clip and no cache, since the file is already
    small and single-country.

This means rasterize_linear_distance() below (used for both roads and
grid) receives an already-loaded GeoDataFrame, not a path — the one
legacy function it replaces (`_align_linear_features()`) has had its
own internal load call removed accordingly. Everything downstream of
the load (STRtree intersects filter, simplify, rasterize, distance
transform, clip, write) is otherwise unchanged from legacy.

`_align_rivers()`'s asymmetry vs. `_align_linear_features()` is
preserved AS-IS, not unified: legacy's rivers path has no STRtree
intersects-prefilter step (rasterizes every loaded feature directly)
and does NOT AND the rasterized mask with grid.country_mask before the
distance transform (roads/grid do both). At the FUNCTION level (what
is unit-tested here) this means a river feature outside grid.country_mask
still contributes to the distance transform, while a road/grid feature
outside it does not — a real, testable difference regardless of what
the caller passes in. Its practical impact on the full pipeline is
smaller than in legacy, though, precisely BECAUSE of Passo 1's
pre-clipping: rivers_gdf/roads_gdf arrive already cut to the country
polygon by read_clipped_to_country() before reaching align_rivers()/
rasterize_linear_distance(), so there is no longer a large "just
outside the country" feature population left to matter — what remains
is at most a sub-pixel sliver from clip_vector_to_country()'s geometry
simplification tolerance at the border (country_mask is rasterized
from the UNsimplified polygon; the vector clip uses a simplified one).
`grid` (load_vector_bbox(), no exact clip) is NOT pre-clipped this way
and still fully exhibits the original-scale asymmetry. This was true
in legacy before this port and is not a numeric parameter — it is a
structural difference between two functions that happened to diverge —
so it is called out here rather than silently ported without comment,
but NOT changed (out of scope for this stage; see docs/DECISIONS.md
2026-09-08, grid_alignment Passo 4, for the numerically-hardcoded parts
of this same asymmetry — the 50km vs. 100km distance cap — which ARE
flagged there as pending).
"""

from __future__ import annotations

import logging
import math

import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio.features import rasterize
from scipy import ndimage
from shapely.geometry import mapping
from shapely.strtree import STRtree

from geofrea.core.constants import NODATA_FLOAT, NODATA_UINT8
from geofrea.core.raster_io import safe_raster_write
from geofrea.grid_alignment.reference_grid import GridContext

logger = logging.getLogger(__name__)


def load_vector_bbox(
    path, country_gdf: gpd.GeoDataFrame, label: str, buffer_deg: float = 0.01
) -> gpd.GeoDataFrame | None:
    """Load a vector file, bbox-prefiltered to the country's extent.

    Lightweight port of legacy's `_load_and_clip_vector_data()` — a
    read-time bbox filter only, no exact-geometry clip, no cache. Used
    for `grid` only: unlike roads/lakes/rivers, the grid source file is
    already country-scoped at acquisition (small, single-country), so
    the heavier read_clipped_to_country() + cache machinery (used for
    the global-source layers, see module docstring) is not needed here.

    Args:
        path: Vector file to load.
        country_gdf: Country GeoDataFrame, for the bbox reference.
        label: Descriptive label for logging.
        buffer_deg: Bounding-box buffer, in degrees.

    Returns:
        Clipped GeoDataFrame in country_gdf's CRS, or None if the
        result is empty or the read failed.
    """
    try:
        minx, miny, maxx, maxy = country_gdf.total_bounds
        bbox = (minx - buffer_deg, miny - buffer_deg, maxx + buffer_deg, maxy + buffer_deg)

        vector_data = gpd.read_file(path, bbox=bbox)

        if vector_data.empty:
            return None

        if vector_data.crs != country_gdf.crs:
            vector_data = vector_data.to_crs(country_gdf.crs)

        logger.info("    [%s] %d features loaded.", label, len(vector_data))
        return vector_data
    except Exception as e:  # noqa: BLE001 — one bad vector source must not abort alignment
        logger.error("    [%s] Driver error during vector subsetting: %s", label, e)
        return None


def calculate_wgs84_isotropic_distance(feature_mask_inv: np.ndarray, grid: GridContext) -> np.ndarray:
    """Compute Euclidean distance with a WGS84 ellipsoid correction.

    Converts a pixel-space distance transform to kilometres using
    Bowring-series scale factors at the grid's centroid latitude.

    # TODO: pending Passo 4 methodological review — this is one of
    # three differently-truncated variants of the same geodesic
    # correction found across the legacy codebase (see
    # docs/architecture/grid_alignment.md sec b — this one keeps terms
    # up to cos(4*phi)/cos(5*phi)). Ported as-is, not centralized/
    # reconciled with the other two variants here.

    Args:
        feature_mask_inv: Binary array, 0=feature, 1=background.
        grid: GridContext for transform and dimensions.

    Returns:
        Float32 array of distances, in kilometres.
    """
    dist_pixels = ndimage.distance_transform_edt(feature_mask_inv)

    lat_center = grid.transform.f + grid.transform.e * (grid.height / 2)
    lat_rad = math.radians(lat_center)

    lat_km_deg = (
        111132.92 - 559.82 * math.cos(2 * lat_rad) + 1.175 * math.cos(4 * lat_rad)
    ) / 1000.0
    lon_km_deg = (
        111412.84 * math.cos(lat_rad) - 93.50 * math.cos(3 * lat_rad) + 0.118 * math.cos(5 * lat_rad)
    ) / 1000.0

    px_scale_km = math.sqrt(abs(grid.transform.a) * lon_km_deg * abs(grid.transform.e) * lat_km_deg)
    return (dist_pixels * px_scale_km).astype(np.float32)


def rasterize_linear_distance(
    gdf: gpd.GeoDataFrame | None,
    out_path,
    country_gdf: gpd.GeoDataFrame,
    grid: GridContext,
    label: str,
    max_dist_km: float,
) -> object | None:
    """Rasterize linear features and compute a geodesic distance-to-feature raster.

    Shared by both `roads` (gdf already clipped via
    read_clipped_to_country(), see module docstring) and `grid` (gdf
    from load_vector_bbox()) — legacy used one function
    (`_align_linear_features()`) for both, this preserves that.

    Args:
        gdf: Already-loaded vector data (roads: exactly clipped to the
            country polygon; grid: bbox-prefiltered only), or None.
        out_path: Output path for the distance raster.
        country_gdf: Country GeoDataFrame (for the STRtree intersects
            filter and the final country-mask mirrors legacy's use of
            `mainland_geometry`).
        grid: Target GridContext.
        label: Feature-type label for logging.
        max_dist_km: Maximum distance to encode, in kilometres.
            # TODO: pending Passo 4 methodological review — legacy
            # hardcodes 100.0 for both roads and grid
            # (_align_linear_features()'s own default), diverging from
            # rivers' separately-hardcoded 50.0 (see align_rivers()
            # below) with no documented justification for either value
            # or the difference between them (grid_alignment.md sec c
            # item 4). Callers must pass this explicitly (no default
            # here) so the pending value is visible at every call site.

    Returns:
        Path to the output distance raster, or None if gdf is empty/None
        or no feature intersects the country.
    """
    if gdf is None or gdf.empty:
        return None

    try:
        tree = STRtree(gdf.geometry.values)
        intersect_indices = tree.query(country_gdf.union_all(), predicate="intersects")
        if len(intersect_indices) == 0:
            return None

        gdf_intersect = gdf.iloc[intersect_indices]
        tolerance = abs(grid.transform.a) * 0.5
        shapes = [
            (mapping(g), 1) for g in gdf_intersect.geometry.simplify(tolerance) if not g.is_empty
        ]

        feature_mask = rasterize(
            shapes=shapes,
            out_shape=(grid.height, grid.width),
            transform=grid.transform,
            fill=0,
            all_touched=True,
            dtype=np.uint8,
        )
        feature_mask = feature_mask & grid.country_mask.astype(np.uint8)

        dist_km = calculate_wgs84_isotropic_distance((feature_mask == 0).astype(np.uint8), grid)
        dist_km = np.clip(dist_km, 0, max_dist_km)
        dist_km[~grid.country_mask] = NODATA_FLOAT

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
            dst.write(dist_km, 1)

        return out_path
    except Exception as e:  # noqa: BLE001 — one bad layer must not abort alignment
        logger.error("    [%s] Topology processing failed: %s", label, e)
        return None


def align_lakes(
    lakes_gdf: gpd.GeoDataFrame | None, out_path, grid: GridContext
) -> object | None:
    """Rasterize inland water bodies as a binary hard-exclusion mask.

    Args:
        lakes_gdf: Already-clipped lakes GeoDataFrame (via
            read_clipped_to_country(), see module docstring), or None.
        out_path: Output path for the lake mask raster.
        grid: Target GridContext.

    Returns:
        Path to the output mask raster, or None if no lakes were found.
    """
    if lakes_gdf is None or lakes_gdf.empty:
        return None

    shapes = [(mapping(g), 1) for g in lakes_gdf.geometry if g and not g.is_empty]
    if not shapes:
        return None

    lake_mask = rasterize(
        shapes=shapes,
        out_shape=(grid.height, grid.width),
        transform=grid.transform,
        fill=0,
        all_touched=True,
        dtype=np.uint8,
    )
    lake_mask[~grid.country_mask] = NODATA_UINT8

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
    }
    with safe_raster_write(out_path, **profile) as dst:
        dst.write(lake_mask, 1)
    return out_path


def align_rivers(
    rivers_gdf: gpd.GeoDataFrame | None, out_path, grid: GridContext
) -> object | None:
    """Rasterize river networks and compute a geodesic distance-to-river raster.

    Deliberately NOT unified with rasterize_linear_distance() — see
    module docstring for the structural asymmetry this preserves
    (no STRtree intersects-prefilter; the rasterized mask is not ANDed
    with grid.country_mask before the distance transform).

    Args:
        rivers_gdf: Already-clipped rivers GeoDataFrame (via
            read_clipped_to_country(), see module docstring), or None.
        out_path: Output path for the river distance raster.
        grid: Target GridContext.

    Returns:
        Path to the output distance raster, or None if no rivers were found.
    """
    if rivers_gdf is None or rivers_gdf.empty:
        return None

    tolerance = abs(grid.transform.a) * 0.5
    shapes = [
        (mapping(g), 1) for g in rivers_gdf.geometry.simplify(tolerance) if g and not g.is_empty
    ]
    if not shapes:
        return None

    river_mask = rasterize(
        shapes=shapes,
        out_shape=(grid.height, grid.width),
        transform=grid.transform,
        fill=0,
        all_touched=True,
        dtype=np.uint8,
    )

    dist_km = calculate_wgs84_isotropic_distance((river_mask == 0).astype(np.uint8), grid)
    # TODO: pending Passo 4 methodological review — hardcoded 50km cap,
    # undocumented, diverges from roads/grid's 100km default (see
    # rasterize_linear_distance()'s own TODO and grid_alignment.md sec
    # c item 4). Ported as-is from legacy.
    dist_km = np.clip(dist_km, 0, 50)
    dist_km[~grid.country_mask] = NODATA_FLOAT

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
    }
    with safe_raster_write(out_path, **profile) as dst:
        dst.write(dist_km, 1)
    return out_path


def align_plants(
    plants_df: pd.DataFrame | None, out_path, country_gdf: gpd.GeoDataFrame, grid: GridContext
) -> object | None:
    """Rasterize existing power-plant locations as a binary mask.

    Args:
        plants_df: DataFrame with 'latitude'/'longitude' columns (case-
            insensitive, some aliases accepted — see legacy behavior below).
        out_path: Output path for the raster.
        country_gdf: Country GeoDataFrame, for the intersects filter.
        grid: Target GridContext.

    Returns:
        Path to the output raster, or None if no plants were found.
    """
    if plants_df is None or plants_df.empty:
        logger.info("    [plants] No plants data available.")
        return None

    df = plants_df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    lat_col = next((c for c in ["latitude", "lat"] if c in df.columns), None)
    lon_col = next((c for c in ["longitude", "lon", "long"] if c in df.columns), None)

    if lat_col is None or lon_col is None:
        logger.warning("    [plants] Missing lat/lon columns.")
        return None

    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df[lon_col], df[lat_col]), crs="EPSG:4326"
    )
    country_union = (
        country_gdf.geometry.union_all()
        if hasattr(country_gdf.geometry, "union_all")
        else country_gdf.geometry.unary_union
    )
    gdf = gdf[gdf.intersects(country_union)]

    if gdf.empty:
        logger.info("    [plants] No plants intersect country geometry.")
        return None

    logger.info("    [plants] %d plants rasterized.", len(gdf))

    shapes = [(mapping(g), 1) for g in gdf.geometry]
    plant_mask = rasterize(
        shapes=shapes,
        out_shape=(grid.height, grid.width),
        transform=grid.transform,
        fill=0,
        all_touched=True,
        dtype=np.uint8,
    )
    plant_mask[~grid.country_mask] = NODATA_UINT8

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
        dst.write(plant_mask, 1)

    return out_path
