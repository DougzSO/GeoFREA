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
decisão de onde entra no GeoFREA fica pendente"). Category values are
normalized with `.str.lower().str.strip()` before grouping, replicating
compute_protected_areas()'s own normalization — see
_iucn_category_breakdown()'s docstring for the "Not Reported"/"Not
Applicable"/"Not Assigned" and NaN-handling details (DECISIONS.md
2026-08-24 "IUCN category normalization fix").

`cache_path` (2026-08-25, see DECISIONS.md same date - data_acquisition
activation): added after a real-data validation run measured
gpd.read_file() on the real 820 MB HydroLAKES file as the actual
bottleneck for `clip=True` layers, independent of the clip step itself
— see core/geo_utils.py's read_clipped_to_country() for the read-time
bbox-filter half of the fix. `cache_path` is the second half: when
given (and `clip=True`, `country_gdf` is not None), the ALREADY-clipped
result is saved to (and, on a later call, loaded straight back from)
one on-disk file per country/layer, so a huge global source file is
read at most once per country ever, not once per audit run. Cache
invalidation is manual (delete the file) — the same convention
data_acquisition's own fetchers already use for their own idempotency
checks, not a new one invented here. A cache-WRITE failure is logged
and swallowed, not raised: caching is a pure optimization, so failing
to persist one must not turn an otherwise-successful inspection into an
error result. Only wired in for `clip=True` layers (protected/lakes/
rivers) by audit.py — `clip=False` layers are already country-scoped
small files at the source, nothing there is large enough to need it.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import geopandas as gpd

from geofrea.core.geo_utils import get_local_utm_crs, read_clipped_to_country

logger = logging.getLogger("geofrea.data_quality_audit.vector_inspection")

# Same column names, same priority order, as geoworld_framework's
# criteria_builder.py::compute_protected_areas() — not reinvented.
_IUCN_CATEGORY_COLUMNS = ("IUCN_CAT", "iucn_cat", "IUCN", "DESIGNATION")


class ClipRequiresCountryGdfError(ValueError):
    """Raised when clip=True is requested without a real country_gdf.

    Added 2026-08-26 after a real incident: running the actual wired
    data_acquisition -> data_quality_audit pipeline end-to-end for the
    first time (not the standalone-audit-with-empty-AuditInputs path
    every existing test used), country_gdf was None for both PRT and
    BRA — `borders` has no real fetcher yet, so adapter.py's
    _load_mainland_boundary() has nothing to build it from. Before this
    guard, `inspect_vector_layer()` silently fell back to
    `gpd.read_file(str(path))` on the WHOLE unclipped source file — for
    `lakes` that is HydroLAKES' global 1.1 GB .shp (every lake on
    Earth). Reprojecting and summing area over that drove free system
    RAM from several GB down to ~1 GB in well under an hour, before the
    run was killed. This is a configuration/wiring gap, not a
    per-file data problem — it must fail loudly (propagate out of this
    function), not degrade into result["error"] like a corrupt file
    would, so it cannot be silently ignored in a JSON blob. See
    docs/DECISIONS.md 2026-08-26 for the full incident writeup.
    """


def _read_clipped_with_cache(
    path: Path, country_gdf: gpd.GeoDataFrame, cache_path: Path | None
) -> gpd.GeoDataFrame:
    """read_clipped_to_country(), backed by an on-disk cache keyed by cache_path.

    See module docstring, "cache_path", for the full rationale. On a
    cache hit, `path` (the large source file) is never read at all.
    """
    if cache_path is not None and Path(cache_path).exists():
        return gpd.read_file(str(cache_path))

    clipped = read_clipped_to_country(path, country_gdf)

    if cache_path is not None:
        try:
            Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
            clipped.to_file(cache_path, driver="GPKG")
        except Exception as exc:  # noqa: BLE001 — caching is optional, must not fail the inspection
            logger.warning("Failed to write clip cache %s: %s", cache_path, exc)

    return clipped


def inspect_vector_layer(
    path: Path | None,
    country_gdf: gpd.GeoDataFrame | None = None,
    *,
    clip: bool = True,
    iucn_breakdown: bool = False,
    cache_path: Path | None = None,
) -> dict[str, Any]:
    """Read metadata and structural statistics from a single vector file.

    Args:
        path: Path to the vector file, or None if unresolved.
        country_gdf: Country polygon (mainland-filtered) to clip
            against. Required for clip=True — unlike inspect_raster()'s
            own country_gdf=None case, this does NOT fall back to
            reading the full file: see ClipRequiresCountryGdfError
            (raised instead, 2026-08-26). A raster's "full file" is one
            bounded per-country tile; a clip=True vector layer's "full
            file" is a global/continental source, so the same fallback
            that is harmless for rasters is what caused a real near-OOM
            incident here.
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
        cache_path: Where to persist/read back the already-clipped
            result, or None to skip caching entirely (always re-derive
            from `path`). Only consulted when clip=True and
            country_gdf is given — see module docstring, "cache_path".

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

    if clip and country_gdf is None:
        # Raised BEFORE the try/except below, deliberately — must
        # propagate, not degrade into result["error"] like the broad
        # except further down does for a bad file. See
        # ClipRequiresCountryGdfError's docstring for the incident this
        # guards against.
        raise ClipRequiresCountryGdfError(
            f"inspect_vector_layer({path.name!r}): clip=True but "
            "country_gdf is None. Refusing to fall back to reading the "
            "whole unclipped global/continental source file (see "
            "ClipRequiresCountryGdfError's docstring for why). Resolve "
            "a real country boundary before calling this layer, or "
            "pass clip=False if reading the full file is genuinely "
            "intended."
        )

    try:
        if clip and country_gdf is not None:
            gdf = _read_clipped_with_cache(path, country_gdf, cache_path)
            result["clipped_to_country"] = True
        else:
            gdf = gpd.read_file(str(path))

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

    Category normalization (`.str.lower().str.strip()`) replicates
    compute_protected_areas()'s own normalization before it looks values
    up in IUCN_SCORES, added 2026-08-24 (see DECISIONS.md same date,
    "IUCN category normalization fix") to fix a real gap: without it,
    "Not Reported" and "not reported" (or "II" and "ii") would land in
    separate buckets here even though the legacy scoring logic treats
    them as identical. Bucket keys/`name` values are therefore always
    lowercase, e.g. "ii", "not reported" — not the raw column casing.

    "Not Reported"/"Not Applicable"/"Not Assigned" are NOT special-cased
    here — confirmed against the legacy source (criteria_builder.py) that
    they are ordinary entries in IUCN_SCORES (own dedicated scores, not
    the IUCN_SCORE_DEFAULT fallback), not values legacy drops, groups
    into an "other" bucket, or errors on. They flow through this
    function like any other category string and get their own bucket.

    NaN/missing category values are labeled "unknown" here — a GeoFREA-
    only convention with no legacy equivalent: compute_protected_areas()
    never names a missing value at all, it just lets `.str` accessor
    calls produce NaN and IUCN_SCORES.get(nan, IUCN_SCORE_DEFAULT) fall
    through to the same default score used for any unrecognized string,
    silently and without a label. This function's "unknown" label exists
    only because it needs *some* dict key to group by — not a scoring
    decision, and not necessarily the label suitability_criteria (the
    future phase that will port IUCN_SCORES) should use. Left as-is,
    flagged for that future design, not decided here.
    """
    iucn_col = next((c for c in _IUCN_CATEGORY_COLUMNS if c in gdf.columns), None)
    if iucn_col is None:
        return None

    categories = gdf[iucn_col].fillna("unknown").astype(str).str.lower().str.strip()
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
