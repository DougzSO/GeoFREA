"""Shared geometry helpers used across phases.

Ported from geoworld_framework's src/utils/utils.py (get_local_utm_crs)
and src/processors/data_auditor.py (get_mainland_gdf, detect_island_nation)
— generic geometry operations, not audit-specific, so they live in core/
rather than in data_quality_audit/ (grid_alignment and later phases will
also need mainland/UTM handling). See DECISIONS.md 2026-08-20 -
orchestrator + data_quality_audit phase.
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
