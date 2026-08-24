"""Shared geometry helpers used across phases.

Ported from geoworld_framework's src/utils/utils.py (get_local_utm_crs)
and src/processors/data_auditor.py (get_mainland_gdf, detect_island_nation)
— generic geometry operations, not audit-specific, so they live in core/
rather than in data_quality_audit/ (grid_alignment and later phases will
also need mainland/UTM handling). See DECISIONS.md 2026-08-20 -
orchestrator + data_quality_audit phase.

clip_vector_to_country() was added 2026-08-24 (see DECISIONS.md same
date - vector layer audit depth). It is a fresh implementation, not a
literal extraction from raster_inspection.py::inspect_land_cover_tiles:
that function's bbox-prefilter + intersection is tightly coupled to
raster windowed reads and per-class pixel accounting, not reusable for
vector data as-is. What IS reused is the *pattern* — bbox prefilter
before an exact geometry intersection — which both
inspect_land_cover_tiles() and geoworld_framework's
criteria_builder.py::compute_protected_areas() already use independently
(the latter via gdf.intersects(mainland_union) then
geometry.intersection(mainland_union), without an explicit bbox
prefilter step). clip_vector_to_country() adds the bbox prefilter
(gdf.cx[]) as a fast first pass, matching inspect_land_cover_tiles()'s
two-step shape more closely than compute_protected_areas() does.
"""

from __future__ import annotations

from typing import Any

import geopandas as gpd


def get_local_utm_crs(geometry: Any) -> str:
    """Compute the local UTM EPSG code from the centroid of a geometry.

    Args:
        geometry: Shapely geometry, GeoSeries, or GeoDataFrame.

    Returns:
        EPSG code string for the local UTM zone (e.g. "EPSG:32629").
    """
    if isinstance(geometry, gpd.GeoDataFrame):
        geometry = (
            geometry.geometry.union_all()
            if hasattr(geometry.geometry, "union_all")
            else geometry.geometry.unary_union
        )

    if not isinstance(geometry, gpd.GeoSeries):
        geometry = gpd.GeoSeries([geometry], crs="EPSG:4326")

    centroid = (
        geometry.union_all().centroid
        if hasattr(geometry, "union_all")
        else geometry.unary_union.centroid
    )

    lon = centroid.x
    lat = centroid.y

    utm_zone = int((lon + 180) // 6) + 1
    hemisphere = 326 if lat >= 0 else 327

    return f"EPSG:{hemisphere}{utm_zone:02d}"


def get_mainland_gdf(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Return a GeoDataFrame containing only the largest polygon (mainland).

    Removes islands, enclaves, and fragments before any analysis.

    Args:
        gdf: Full country GeoDataFrame.

    Returns:
        Single-row GeoDataFrame with the largest polygon, in EPSG:4326.
    """
    union = (
        gdf.geometry.union_all()
        if hasattr(gdf.geometry, "union_all")
        else gdf.geometry.unary_union
    )

    utm_crs = get_local_utm_crs(union)
    exploded = gdf.to_crs(utm_crs).explode(index_parts=False).reset_index(drop=True)
    idx = exploded.geometry.area.idxmax()

    return exploded.iloc[[idx]].to_crs("EPSG:4326")


def detect_island_nation(gdf: gpd.GeoDataFrame, threshold_pct: float = 0.60) -> bool:
    """Detect whether get_mainland_gdf() would discard too much territory.

    Args:
        gdf: Country GeoDataFrame.
        threshold_pct: Fraction threshold above which the country is
            considered an island nation (default 0.60).

    Returns:
        True if the largest polygon represents less than (1 - threshold_pct)
        of total territory, indicating that mainland-only filtering would
        discard a large share of the country's actual territory.
    """
    try:
        union = (
            gdf.geometry.union_all()
            if hasattr(gdf.geometry, "union_all")
            else gdf.geometry.unary_union
        )
        utm_crs = get_local_utm_crs(union)
        gdf_proj = gdf.to_crs(utm_crs)
        exploded = gdf_proj.explode(index_parts=False).reset_index(drop=True)

        total_area = float(exploded.geometry.area.sum())
        largest_area = float(exploded.geometry.area.max())

        if total_area == 0:
            return False

        largest_pct = largest_area / total_area
        return largest_pct < (1.0 - threshold_pct)

    except Exception:  # noqa: BLE001 — diagnostic-only helper, never fatal (matches legacy)
        return False


def clip_vector_to_country(
    gdf: gpd.GeoDataFrame, country_gdf: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Clip a GeoDataFrame's geometries to a country polygon.

    Two-step strategy: a fast bounding-box prefilter (gdf.cx[]) before
    the exact geometry intersection, so a huge global file (HydroLAKES,
    HydroRIVERS, WDPA) is not intersected feature-by-feature against
    the full country geometry when most features are nowhere near it.
    See module docstring for how this relates to
    inspect_land_cover_tiles() and compute_protected_areas().

    Args:
        gdf: Vector layer to clip, any CRS.
        country_gdf: Country polygon(s) to clip against — reprojected
            to gdf's CRS internally if they differ.

    Returns:
        A new GeoDataFrame with geometries intersected against the
        country polygon; features with no overlap are dropped, and
        boundary-crossing features are cut to the country's extent.
    """
    country_in_gdf_crs = (
        country_gdf.to_crs(gdf.crs) if gdf.crs is not None else country_gdf
    )
    country_geom = (
        country_in_gdf_crs.geometry.union_all()
        if hasattr(country_in_gdf_crs.geometry, "union_all")
        else country_in_gdf_crs.geometry.unary_union
    )

    minx, miny, maxx, maxy = country_in_gdf_crs.total_bounds
    prefiltered = gdf.cx[minx:maxx, miny:maxy]

    clipped = prefiltered[prefiltered.intersects(country_geom)].copy()
    clipped["geometry"] = clipped.geometry.intersection(country_geom)
    return clipped[~clipped.geometry.is_empty]
