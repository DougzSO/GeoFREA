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

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from geofrea.core.schemas import GeometryRepairSummary


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


LayerSummary = Annotated[RasterLayerSummary | VectorLayerSummary, Field(discriminator="kind")]


class AuditSummary(BaseModel):
    """Concise cross-section of the full audit, used for the report footer.

    `layers` replaced the flat per-raster-layer fields (layers_ok,
    layers_missing, n_wind_files, solar_range, elev_range, slope_range,
    pop_range) 2026-08-24 (see DECISIONS.md same date,
    "AuditSummary refactor to layer-keyed dict") — one dict, keyed by
    layer name, covering the same 12 names as AuditResult.rasters
    (5) + AuditResult.vectors (7) combined (confirmed disjoint — no
    name collision between the two namespaces). land_cover
    deliberately stays OUT of `layers`, as its own dedicated field below — it is an aggregate over many files,
    not a single-file "layer" in the same sense as the other 12, and AuditResult itself already keeps it as a
    separate top-level field rather than folding it into `rasters`/`vectors` — `layers` mirrors that same
    structural split, not a new one.
    """

    model_config = ConfigDict(extra="forbid")

    layers: dict[str, LayerSummary]
    lc_tiles_used: int
    lc_tiles_total: int
    lc_total_area_km2: float
    lc_classes: int
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
    vectors: dict[str, VectorLayerInspection]
    alerts: list[str]
    slope_threshold_check: dict[str, SlopeThresholdCheck]
    summary: AuditSummary
    timings: dict[str, float]
    skipped: list[str]
    not_audited: dict[str, str]
    elapsed_total: float
    report_path: str | None = None
