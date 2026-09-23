"""Pydantic schemas for the data_quality_audit phase.

Replaces geoworld_framework's DataAuditor.run(), which returned an ad
hoc dict (see docs/architecture/data_quality_audit.md sec a). AuditResult
is this phase's output_model, validated by the orchestrator like every
other phase — see DECISIONS.md 2026-08-20 - orchestrator + data_quality_audit
phase.

All models forbid extra fields, matching the convention already used in
core/schemas.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import geopandas as gpd
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from geofrea.core.schemas import GeometryRepairSummary


class AuditLayerConfig(BaseModel):
    """One layer's diagnostic-gate expectations from config/audit.yaml (M-F1b-01).

    `expected_resolution_deg` and `source` are both null together, never
    one without the other — a value with no primary source is not
    configuration, it's a guess (see CLAUDE.md, "A methodological value
    without a documented primary source is never assumed"). A null pair
    means the layer is reported `not_audited` for the resolution check
    rather than silently skipped or defaulted.
    """

    model_config = ConfigDict(extra="forbid")

    expected_resolution_deg: float | None = None
    source: str | None = None
    unit: str | None = None
    sanity_range: tuple[float, float] | None = None


class AuditConfig(BaseModel):
    """Root schema for config/audit.yaml.

    `layers` is keyed by the same layer names AuditResult.rasters uses
    for simple layers (land_cover, solar, elevation) plus entries with
    no corresponding AuditInputs field yet — `wind` holds a nested dict
    of GWA product name -> AuditLayerConfig (only `wind-speed` has a
    fetched file today; the rest are OQ-pending), and
    `cmip6`/`era5_gust`/`gem_existing_plants` are flat AuditLayerConfig
    entries with no file to inspect yet at all, reported `not_audited`
    unconditionally. No `slope` key: slope is not an F1b layer at all
    (derived later, in grid_alignment) — see docs/phases/
    F1b_data_quality_audit.md D-F1b-003.
    """

    model_config = ConfigDict(extra="forbid")

    resolution_tolerance: float
    layers: dict[str, AuditLayerConfig | dict[str, AuditLayerConfig]]


class AuditInputs(BaseModel):
    """Raw, already-resolved geodata paths/objects the audit phase inspects.

    Mirrors DataAuditor.run()'s parameter list exactly (see
    docs/architecture/data_quality_audit.md sec a). GeoFREA has no data
    acquisition layer yet (legacy's DataFetcher/DataManager/DataOrchestrator
    are not ported — out of scope for this stage), so main.py currently
    has no way to populate these with real values; every field left at
    its default produces the same "file not found" reporting the legacy
    auditor already does for missing inputs. This is not fabricated
    behavior — it is the existing defensive path, just with nothing to
    find yet.

    Args:
        solar_path: PVOUT raster path.
        elevation_path: DEM raster path.
        slope_path: Slope raster path, if one exists yet. Usually None:
            GeoFREA derives slope only later, inside grid_alignment
            (raster_alignment.derive_slope_from_dem(), 2026-09-11), so at
            audit time there is normally nothing to inspect and the
            slope checks are skipped.
        population_path: Population raster path.
        wind_paths: Wind speed/power-density raster paths (only the
            first, if any, is inspected — matches legacy's wind_files[0]).
        land_cover_tiles: ESA WorldCover tile paths.
        lakes_path: HydroLAKES vector path (global — clipped to
            country_gdf during inspection, see vector_inspection.py).
        rivers_path: HydroRIVERS vector path (global — clipped, same
            as lakes_path).
        protected_path: WDPA protected-areas vector path (global —
            clipped, same as lakes_path). Added 2026-08-24 — see
            DECISIONS.md same date, "vector layer audit depth". Note
            this is a NEW AuditInputs field with no AuditResult
            consumer beyond `vectors["protected"]`'s own inspection —
            it does not feed a suitability/exclusion calculation here
            (see DECISIONS.md 2026-08-24 "protected (WDPA): decisão de
            onde entra no GeoFREA fica pendente").
        borders_path: Raw country-boundary vector path (all polygons —
            mainland, islands, enclaves), inspected as-is, NOT clipped
            (already scoped to one country at the source). Distinct
            from `country_gdf` below, which is the mainland-only
            polygon DERIVED from this same file and used purely as a
            clip mask for every other layer.
        admin1_path: Admin level-1 boundaries vector path (same GADM
            download as borders_path in legacy — not clipped).
        grid_path: Power-grid (transmission lines) vector path, from
            OSM Overpass — country-scoped at the source, not clipped.
        roads_path: Road network vector path. Since 2026-09-08 (see
            DECISIONS.md same date, "wire das 5 camadas restantes a
            partir do banco local, Fase 2 - roads") this is a GRIP4
            regional shapefile spanning many countries, clipped by
            data_quality_audit at inspection time (clip=True) — no
            longer the country-scoped, unclipped OSM Overpass file the
            original skeleton assumed.
        plants_df: Existing power-plant records.
        country_gdf: Country polygon (mainland-filtered) used to mask
            every raster to the real country boundary, not a bounding box.
        skip_land_cover: If True, skip ESA tile analysis (the slowest step).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    solar_path: Path | None = None
    elevation_path: Path | None = None
    slope_path: Path | None = None
    population_path: Path | None = None
    wind_paths: list[Path] = []
    land_cover_tiles: list[Path] = []
    lakes_path: Path | None = None
    rivers_path: Path | None = None
    protected_path: Path | None = None
    borders_path: Path | None = None
    admin1_path: Path | None = None
    grid_path: Path | None = None
    roads_path: Path | None = None
    plants_df: pd.DataFrame | None = None
    country_gdf: gpd.GeoDataFrame | None = None
    skip_land_cover: bool = False


class RasterInspection(BaseModel):
    """Metadata and statistics for a single inspected raster layer.

    See docs/architecture/data_quality_audit.md sec b for the geodetic
    area formula and sec c for the PVOUT unit sanity-check bounds.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    size_mb: float | None = None
    crs: str | None = None
    resolution: float | None = None
    global_shape: tuple[int, int] | None = None
    analysis_shape: tuple[int, int] | None = None
    masked_by: str | None = None
    nodata: float | None = None
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    valid_pct: float | None = None
    area_km2: float | None = None
    error: str | None = None


class LandCoverClassStat(BaseModel):
    """Area/percentage for one ESA WorldCover class within the country."""

    model_config = ConfigDict(extra="forbid")

    name: str
    area_km2: float
    pct: float


class LandCoverInspection(BaseModel):
    """Aggregated ESA WorldCover statistics across all overlapping tiles."""

    model_config = ConfigDict(extra="forbid")

    skipped: bool = False
    error: str | None = None
    n_tiles: int = 0
    tiles_used: int = 0
    tiles_skipped: int = 0
    crs_set: list[str] = []
    res_set: list[float] = []
    class_stats: dict[int, LandCoverClassStat] = {}
    total_area_km2: float = 0.0
    errors: list[str] = []


class VectorAttributeStat(BaseModel):
    """Count/area and percentage for one categorical value within a
    vector layer's attribute breakdown (e.g. one IUCN category).

    `area_km2` is populated only for polygon layers where an area
    breakdown makes sense (protected areas by IUCN category); left None
    for layers where it wasn't computed (see VectorLayerInspection's
    `attribute_breakdown` — currently populated only for `protected`).
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    count: int
    area_km2: float | None = None
    pct: float


class VectorLayerInspection(BaseModel):
    """Structural/geometric inspection for a single vector layer.

    Extended 2026-08-24 (see DECISIONS.md same date, "vector layer
    audit depth") from a presence/size-only check (the original
    lakes/rivers behavior) to the same inspection depth rasters already
    get via RasterInspection — CRS, feature count, geometry types,
    bbox, area/length, and (for `protected` only) an IUCN-category
    attribute breakdown. `found=False` covers both "no path resolved"
    and "file does not exist" (unchanged meaning); a resolved-but-
    unopenable file is captured via `error`, mirroring RasterInspection
    (inspect_vector_layer() catches broadly, like inspect_raster()) —
    a deliberate choice to keep a single corrupt vector file from
    failing the whole audit phase, even though the analogous loaders in
    data_acquisition/adapter.py are NOT (yet) defensive this way (see
    that module's "THIRD KNOWN GAP" docstring note) — the two live in
    different places for different reasons: adapter.py has nowhere
    in AuditInputs to put an error today, this schema does.
    """

    model_config = ConfigDict(extra="forbid")

    found: bool
    name: str | None = None
    size_mb: float | None = None
    crs: str | None = None
    n_features: int | None = None
    geometry_types: list[str] = []
    bbox: tuple[float, float, float, float] | None = None
    total_area_km2: float | None = None
    total_length_km: float | None = None
    clipped_to_country: bool = False
    attribute_breakdown: dict[str, VectorAttributeStat] | None = None
    geometry_repair: GeometryRepairSummary | None = None
    error: str | None = None
    error_type: Literal["read_error", "processing_error"] | None = None


class PowerPlantsInspection(BaseModel):
    """Aggregated statistics from existing power-generation plants."""

    model_config = ConfigDict(extra="forbid")

    total_plants: int = 0
    total_capacity_mw: float = 0.0
    by_fuel: dict[str, float] = {}
    error: str | None = None


class RasterLayerSummary(BaseModel):
    """Concise per-layer status for one audited raster (see AuditSummary.layers).

    `value_range` mirrors the pre-2026-08-24 flat `*_range` fields
    (solar_range, elev_range, slope_range, pop_range) —
    populated only for those 4 layers, same as before. `wind` never got
    a range in the flat schema either (its own `range_map` in
    audit.py's `_build_summary()` never included "wind") — that
    asymmetry is preserved here, not fixed, since fixing it was out of
    scope for this refactor. `file_count` is the direct replacement for
    the old standalone `n_wind_files` field — populated only for `wind`
    (AuditInputs.wind_paths' length; only the first path is ever
    inspected, see AuditInputs' own docstring), None for every other
    raster layer.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["raster"] = "raster"
    status: Literal["ok", "missing"]
    error: str | None = None
    value_range: tuple[float, float] | None = None
    file_count: int | None = None


class VectorLayerSummary(BaseModel):
    """Concise per-layer status for one audited vector layer (see AuditSummary.layers).

    Mirrors _format_report()'s own pre-existing tri-state distinction
    for vector layers (missing / error / ok) — VectorLayerInspection
    already separates "not found" from "found but failed to open"
    (`found` + `error` fields), unlike RasterInspection's raster
    counterpart, which only distinguishes ok/missing in the flat schema
    this replaces. Not invented here — replicates behavior
    _format_report()'s VECTOR LAYERS section already had.

    The single generic "error" status was split into "read_error"/
    "processing_error" 2026-09-21 (see docs/phases/F1b_data_quality_audit.md):
    VectorLayerInspection.error_type now distinguishes a failure opening
    or clipping the file from a failure computing statistics on an
    already-open GeoDataFrame — this mirrors that distinction rather
    than collapsing it back into one bucket.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["vector"] = "vector"
    status: Literal["ok", "missing", "read_error", "processing_error"]
    error: str | None = None
    n_features: int | None = None


LayerSummary = Annotated[
    RasterLayerSummary | VectorLayerSummary, Field(discriminator="kind")
]


class AuditSummary(BaseModel):
    """Concise cross-section of the full audit, used for the report footer.

    `layers` replaced the flat per-raster-layer fields (layers_ok,
    layers_missing, n_wind_files, solar_range, elev_range, slope_range,
    pop_range) 2026-08-24 (see DECISIONS.md same date,
    "AuditSummary refactor to layer-keyed dict") — one dict, keyed by
    layer name, covering the same 12 names as AuditResult.rasters
    (5) + AuditResult.vectors (7) combined (confirmed disjoint — no
    name collision between the two namespaces). land_cover and
    power_plants deliberately stay OUT of `layers`, as their own
    dedicated fields below — they are aggregates over many files/
    records, not a single-file "layer" in the same sense as the other
    12, and AuditResult itself already keeps them as separate top-level
    fields rather than folding them into `rasters`/`vectors` — `layers`
    mirrors that same structural split, not a new one.
    """

    model_config = ConfigDict(extra="forbid")

    layers: dict[str, LayerSummary]
    lc_tiles_used: int
    lc_tiles_total: int
    lc_total_area_km2: float
    lc_classes: int
    total_plants: int
    total_cap_mw: float
    n_alerts: int
    n_not_audited: int


class SlopeThresholdCheck(BaseModel):
    """Slope-inactivity check result for one technology.

    Each technology now carries its own slope_threshold_deg
    (CountryParams.technologies.<tech>.slope_threshold_deg, see
    docs/DECISIONS.md 2026-08-20 - slope_threshold_deg moved to
    parameters.json) — there is no single per-country threshold
    anymore, so this check runs once per technology, not once per
    country.

    Args:
        threshold_deg: The technology's slope_threshold_deg.value used
            for this check.
        max_observed_deg: The max slope observed in the country's slope
            raster, or None if the slope raster was unavailable/errored.
        inactive: True if max_observed_deg is not None and below
            threshold_deg — the slope criterion would exclude no pixels
            for this technology.
    """

    model_config = ConfigDict(extra="forbid")

    threshold_deg: float
    max_observed_deg: float | None
    inactive: bool


class AuditResult(BaseModel):
    """Root output model for the data_quality_audit phase.

    Replaces the legacy `audit` dict (docs/architecture/data_quality_audit.md
    sec a). `land_cover` is always present as a structured
    LandCoverInspection (skipped=True when skip_land_cover was set),
    unlike legacy's dict which sometimes held just {"skipped": True}.

    Args:
        country_code: ISO-3166-alpha-3 code audited.
        timestamp: ISO-8601 UTC timestamp when the audit started.
        rasters: One RasterInspection per inspected raster layer
            (solar, elevation, slope, population, wind).
        land_cover: ESA WorldCover aggregate statistics.
        power_plants: Existing power-plant aggregate statistics.
        vectors: One VectorLayerInspection per inspected vector layer
            (borders, admin1, grid, roads, protected, lakes, rivers —
            see DECISIONS.md 2026-08-24 "vector layer audit depth").
            Follows the same dict-keyed-by-layer-name pattern already
            used by `rasters`, replacing the earlier flat `lakes`/
            `rivers` top-level fields.
        alerts: Consistency/quality warnings raised during the audit
            (divergent CRS, unexpected resolution, PVOUT unit mismatch,
            inactive slope criterion per technology, island-nation
            detection).
        slope_threshold_check: One SlopeThresholdCheck per technology
            ("biomass", "solar", "wind") — see SlopeThresholdCheck.
        summary: Concise cross-section for the report footer.
        timings: Elapsed seconds per audit step.
        skipped: Step names that were explicitly skipped (e.g.
            "land_cover" when skip_land_cover=True).
        not_audited: Layer name -> reason, for every layer whose
            resolution expectation is null in config/audit.yaml (M-F1b-01:
            never silently skipped, never falls back to a hardcoded
            value). Distinct from `skipped` (an operator choice) and
            from a raster reporting "File not found" (the file itself
            is missing, independent of whether its expectation is
            configured).
        elapsed_total: Total audit wall-clock time, in seconds.
        report_path: Path to the saved human-readable .txt report, or
            None if it could not be written.
    """

    model_config = ConfigDict(extra="forbid")

    country_code: str
    timestamp: str
    rasters: dict[str, RasterInspection]
    land_cover: LandCoverInspection
    power_plants: PowerPlantsInspection
    vectors: dict[str, VectorLayerInspection]
    alerts: list[str]
    slope_threshold_check: dict[str, SlopeThresholdCheck]
    summary: AuditSummary
    timings: dict[str, float]
    skipped: list[str]
    not_audited: dict[str, str]
    elapsed_total: float
    report_path: str | None = None
