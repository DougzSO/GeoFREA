"""Vector layer inspection for the data_quality_audit phase.

Added 2026-08-24 (see DECISIONS.md same date, "vector layer audit
depth") to give borders/admin1/grid/roads/protected/lakes/rivers the
same inspection depth raster_inspection.py::inspect_raster() already
gives rasters — CRS, feature count, geometry types, bbox, area/length,
and (for `protected` only) an IUCN-category attribute breakdown.
Replaces the presence/size-only check audit.py previously ran inline
for lakes/rivers (Path.exists() + .stat().st_size, no file content ever
opened).

Mirrors inspect_raster()'s architecture on purpose:
  - Takes an unopened `path` and opens the file itself — AuditInputs'
    vector fields stay `Path | None`, the same "already-resolved Path"
    convention as solar_path/elevation_path, NOT pre-loaded
    GeoDataFrames. (An earlier version of this stage's instructions
    described adapter.py pre-loading GeoDataFrames, mirroring
    _load_mainland_boundary/plants_df — that would have meant this
    module took an already-open GeoDataFrame, not a path. The two
    ideas conflict: this module's own signature was specified
    elsewhere as inspect_vector_layer(path, country_gdf, clip=True).
    Resolved in favor of the path-based, lazy-open design, because (a)
    it's the literal function signature given, (b) it mirrors
    inspect_raster()'s proven pattern exactly, and (c) it avoids
    eagerly loading up to 6 large global vector files into memory in
    adapter.py regardless of whether the audit phase ever runs. Flagged
    here rather than silently picked — see DECISIONS.md 2026-08-24.)
  - Same broad try/except boundary as inspect_raster(): one bad vector
    file produces {"error": str(exc)} for that layer, not a phase-wide
    crash. This is DELIBERATELY more defensive than
    data_acquisition/adapter.py's two loaders (see that module's
    "THIRD KNOWN GAP" docstring note) — that gap concerns raw
    acquisition glue with no schema field to hold an error; here,
    VectorLayerInspection.error exists specifically for it.

Protected-areas IUCN category breakdown reuses the exact column-name
list and priority order geoworld_framework's
criteria_builder.py::compute_protected_areas() uses (IUCN_CAT/
iucn_cat/IUCN/DESIGNATION) — not reinvented. Only descriptive stats
(count/area/pct per category) are computed here; the IUCN_SCORES
suitability-score mapping itself belongs to a future suitability_criteria
phase, not this audit (see DECISIONS.md 2026-08-24 "protected (WDPA):
decisão de onde entra no GeoFREA fica pendente").
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import geopandas as gpd

from geofrea.core.geo_utils import clip_vector_to_country, get_local_utm_crs

logger = logging.getLogger("geofrea.data_quality_audit.vector_inspection")

# Same column names, same priority order, as geoworld_framework's
# criteria_builder.py::compute_protected_areas() — not reinvented.
_IUCN_CATEGORY_COLUMNS = ("IUCN_CAT", "iucn_cat", "IUCN", "DESIGNATION")


def inspect_vector_layer(
    path: Path | None,
    country_gdf: gpd.GeoDataFrame | None = None,
    *,
    clip: bool = True,
    iucn_breakdown: bool = False,
) -> dict[str, Any]:
    """Read metadata and structural statistics from a single vector file.

    Args:
        path: Path to the vector file, or None if unresolved.
        country_gdf: Country polygon (mainland-filtered) to clip
            against. Required for clip=True to actually clip (if None,
            the full file's statistics are reported instead, same
            defensive fallback inspect_raster() uses for its own
            country_gdf=None case).
        clip: True for layers that are a single global file spanning
            many countries (protected, lakes, rivers) — see module
            docstring and DECISIONS.md 2026-08-24 for why `protected`
            is clip=True despite data_acquisition's _LAYER_REGISTRY
            entry being corrected from country_specific=True to False
            this same stage. False for layers already scoped to one
            country at the acquisition source (borders, admin1, grid,
            roads — GADM/OSM downloads bounded to the target country).
        iucn_breakdown: If True, populate attribute_breakdown by
            grouping features on whichever IUCN category column is
            present. Only meaningful for `protected`.

    Returns:
        Dict matching VectorLayerInspection's fields.
    """
    result: dict[str, Any] = {
        "found": False,
        "name": None,
        "size_mb": None,
        "crs": None,
        "n_features": None,
        "geometry_types": [],
        "bbox": None,
        "total_area_km2": None,
        "total_length_km": None,
        "clipped_to_country": False,
        "attribute_breakdown": None,
        "error": None,
    }

    if not path or not Path(path).exists():
        return result

    path = Path(path)
    result["found"] = True
    result["name"] = path.name
    result["size_mb"] = round(path.stat().st_size / 1e6, 1)

    try:
        gdf = gpd.read_file(str(path))

        if clip and country_gdf is not None and not gdf.empty:
            gdf = clip_vector_to_country(gdf, country_gdf)
            result["clipped_to_country"] = True

        result["crs"] = str(gdf.crs) if gdf.crs else None
        result["n_features"] = len(gdf)
        result["geometry_types"] = sorted({str(g) for g in gdf.geom_type.unique()})

        if not gdf.empty:
            result["bbox"] = tuple(round(float(b), 6) for b in gdf.total_bounds)

            utm_crs = get_local_utm_crs(gdf)
            gdf_proj = gdf.to_crs(utm_crs)

            geom_types = set(gdf.geom_type.unique())
            is_polygonal = geom_types <= {"Polygon", "MultiPolygon"}
            is_lineal = geom_types <= {"LineString", "MultiLineString"}

            if is_polygonal:
                result["total_area_km2"] = round(
                    float(gdf_proj.geometry.area.sum()) / 1e6, 1
                )
            elif is_lineal:
                result["total_length_km"] = round(
                    float(gdf_proj.geometry.length.sum()) / 1e3, 1
                )

            if iucn_breakdown:
                result["attribute_breakdown"] = _iucn_category_breakdown(gdf, gdf_proj)

    except Exception as exc:  # noqa: BLE001 — one bad vector file must not abort the whole audit
        result["error"] = str(exc)
        logger.warning("Error inspecting %s: %s", path.name, exc)

    return result


def _iucn_category_breakdown(
    gdf: gpd.GeoDataFrame, gdf_proj: gpd.GeoDataFrame
) -> dict[str, dict] | None:
    """Group protected-area features by IUCN category: count, area, pct.

    Column detection mirrors geoworld_framework's
    criteria_builder.py::compute_protected_areas() exactly — this only
    computes descriptive stats, not the IUCN_SCORES suitability mapping.
    """
    iucn_col = next((c for c in _IUCN_CATEGORY_COLUMNS if c in gdf.columns), None)
    if iucn_col is None:
        return None

    categories = gdf[iucn_col].fillna("unknown").astype(str).str.strip()
    total_area = float(gdf_proj.geometry.area.sum())

    breakdown: dict[str, dict] = {}
    for category in sorted(categories.unique()):
        mask = categories == category
        area_m2 = float(gdf_proj.loc[mask, "geometry"].area.sum())
        area_km2 = round(area_m2 / 1e6, 1)
        pct = round(100.0 * area_m2 / total_area, 2) if total_area > 0 else 0.0
        breakdown[category] = {
            "name": category,
            "count": int(mask.sum()),
            "area_km2": area_km2,
            "pct": pct,
        }
    return breakdown
