"""Pydantic schemas for the suitability_criteria phase (Fase 2b).

Contract from docs/architecture/suitability_criteria_audit.md sec 8
(approved 2026-09-10), which is the read-only audit of legacy
geoworld_framework's src/processors/criteria_builder.py.

This phase converts the 12 aligned rasters grid_alignment produces
into 14 normalized suitability-criterion rasters in [0, 1] for the
AHP/TOPSIS aggregation in suitability_builder (Fase 3). It also emits
one cartographic PNG per criterion (isolated in this phase, not routed
through a generic renderer — see the audit sec 7 D7) and a bespoke text
summary report (GAP-004, still open — a generic build_phase_report()
is deferred until a second real consumer exists).

Design points carried from the audit:
  - Inputs come from TWO prior phases: grid_alignment (the 12 aligned
    rasters + GridMetadata) and data_acquisition (the optional WDPA
    path, the power-plants DataFrame, and the mainland boundary). This
    is a genuine two-phase dependency, declared here explicitly.
  - No `kind` discriminator on CriterionLayer, and the result carries
    only Paths + summary statistics, never in-memory numpy arrays / a
    pickle (audit D6): suitability_builder re-reads the .tif files.
  - river_safety_buffer_km is a real hard exclusion. This phase only
    PRODUCES river_solar / river_wind {0, 1} setback rasters; adding
    them to Fase 3's common_exclusions is suitability_builder's job
    (audit sec 8d) — flagged there, not implemented here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import geopandas as gpd
import pandas as pd
from pydantic import BaseModel, ConfigDict, model_validator

from geofrea.core.schemas import CriteriaParams, GeometryRepairSummary
from geofrea.grid_alignment.schemas import GridMetadata

# The 14 criterion rasters this phase is expected to produce, in the
# legacy's own completeness-check order (criteria_builder.py L1067-1072).
# slope_degrees is deliberately NOT in this set: the legacy writes it to
# disk for cartography only, and it never enters the criteria dict or
# the MCDA in Fase 3 (audit sec 2b).
CANONICAL_CRITERIA: tuple[str, ...] = (
    "solar_resource",
    "wind_resource",
    "terrain_score",
    "lc_biomass",
    "biomass_resource",
    "protected_areas",
    "pop_suitability",
    "road_suitability",
    "lakes_exclusion",
    "river_solar",
    "river_wind",
    "river_biomass",
    "seismic_suitability",
    "grid_suitability",
)

# Layers that must be present for the phase to run at all — the legacy's
# `required` list (criteria_builder.py L853). Every other aligned layer
# is optional: its criteria are simply skipped when it is missing.
REQUIRED_ALIGNED_LAYERS: tuple[str, ...] = ("elevation", "slope", "solar", "land_cover")


class SuitabilityCriteriaInputs(BaseModel):
    """Everything this phase needs, already resolved by the adapter/main.py.

    The 12 raster fields mirror GridAlignmentResult field-for-field
    (same names, same "None = layer absent" convention). Only elevation/
    slope/solar/land_cover are effectively required (see
    REQUIRED_ALIGNED_LAYERS) — the phase raises if one is missing, but
    the schema keeps them Optional so a partial GridAlignmentResult can
    still be fed in and fail with a clear phase-level error rather than
    a validation error far from the cause.

    Args:
        elevation/slope/solar/wind/land_cover/population/roads/grid/
        lakes/rivers/seismic/plants: Aligned raster paths from
            grid_alignment (GridAlignmentResult), or None if that layer
            was not produced.
        grid_metadata: The reference-grid parameters from grid_alignment
            — the single source of truth for CRS/transform/shape
            (audit D5: do not re-derive the grid from an arbitrary
            raster).
        criteria: The global CriteriaParams block from parameters.json.
        yield_by_land_cover: This country's biomass-yield-per-ESA-class
            table, unwrapped from its VerifiedValue by the adapter
            (CountryParams.criteria.yield_by_land_cover.value).
        terrain_slope_threshold_deg: This country's terrain_score slope
            denominator, unwrapped by the adapter
            (CountryParams.criteria.terrain_slope_threshold_deg.value).
            Per-country (PRT=10, BRA=12); distinct from the fixed
            cross-country exclusion gates in `criteria`.
        wdpa_path: WDPA protected-areas vector (shapefile or a directory
            of them), or None. Optional by contract: the layer is gated
            behind a manual Protected Planet token and is often absent
            — the legacy treats "no WDPA" as "all mainland unrestricted"
            (score 1.0), and this phase preserves that (audit sec 5).
        mainland_gdf: Mainland country polygon(s). Required — used to
            rasterize the protected-areas mainland mask and for every
            criterion map's basemap.
        context_gdf: Neighbouring-country polygons for map context only,
            or None.
        plants_df: Existing-power-plant records (WRI/GPPD), or None —
            used by proximity_plants for the renewable/thermal split and
            by the power-plants map.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    elevation: Path | None = None
    slope: Path | None = None
    solar: Path | None = None
    wind: Path | None = None
    land_cover: Path | None = None
    population: Path | None = None
    roads: Path | None = None
    grid: Path | None = None
    lakes: Path | None = None
    rivers: Path | None = None
    seismic: Path | None = None
    plants: Path | None = None

    grid_metadata: GridMetadata
    criteria: CriteriaParams
    yield_by_land_cover: dict[int, float]
    terrain_slope_threshold_deg: float

    wdpa_path: Path | None = None
    mainland_gdf: gpd.GeoDataFrame
    context_gdf: gpd.GeoDataFrame | None = None
    plants_df: pd.DataFrame | None = None


class CriterionLayer(BaseModel):
    """One produced criterion raster plus its summary statistics.

    No `kind` field (audit sec 8b, DECISIONS.md 2026-09-10 point 6): the
    continuous-vs-exclusion distinction lives in Fase 3's config
    (common_exclusions), not here.

    Args:
        name: One of CANONICAL_CRITERIA.
        tif_path: The written GeoTIFF
            (outputs/<ISO3>/suitability_criteria/tif/<name>.tif).
        figure_path: The written PNG, or None when map rendering was
            skipped.
        valid_pixels: Count of finite, in-range (>= 0) score pixels.
        mean/std/p10/p50/p90: Statistics over the valid pixels.
        frac_ge_0_6: Fraction of valid pixels with score >= 0.6 (the
            legacy's own console metric), in [0, 1].
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    tif_path: Path
    figure_path: Path | None = None
    valid_pixels: int
    mean: float
    std: float
    p10: float
    p50: float
    p90: float
    frac_ge_0_6: float

    @model_validator(mode="after")
    def _name_is_canonical(self) -> CriterionLayer:
        if self.name not in CANONICAL_CRITERIA:
            raise ValueError(
                f"{self.name!r} is not a canonical criterion name "
                f"(expected one of {CANONICAL_CRITERIA})."
            )
        return self


class SuitabilityCriteriaSummary(BaseModel):
    """Roll-up over all produced criteria.

    `missing_expected` and `not_implemented` are two distinct reasons a
    canonical criterion is absent, kept separate on purpose: the first
    is a data condition for THIS country/run (fix the pipeline inputs),
    the second is a permanent property of this GeoFREA build (the phase
    is built one criterion package at a time — see phase.py). Together
    with the produced-criteria keys they partition CANONICAL_CRITERIA.

    Args:
        n_criteria: Number of criteria actually produced (== len of the
            result's `criteria` dict).
        missing_expected: Canonical criteria whose compute IS wired in
            this build but whose required aligned input layer was absent
            for this run.
        not_implemented: Canonical criteria with no compute function in
            this build yet (a later package adds them).
        protected_source: "wdpa" if a WDPA file drove protected_areas,
            "assumed_free" if it fell back to all-mainland-unrestricted
            (audit sec 5).
        protected_wdpa_repair: The GeometryRepairReport
            compute_protected_areas got back from clip_vector_to_country()
            this run — all zeros when protected_source is "assumed_free"
            (no WDPA file at all). Repair itself now happens
            unconditionally inside the shared clip path (2026-09-21, see
            docs/phases/core.md, docs/phases/F2b_siting_layers.md), not
            duplicated here — this field only carries the report through
            to the result, structurally rather than only logged, so it
            is visible without reading logs.
        grid_metadata: Echoed from grid_alignment, so a consumer can
            confirm every criterion shares that grid without opening a
            raster.
    """

    model_config = ConfigDict(extra="forbid")

    n_criteria: int
    missing_expected: list[str]
    not_implemented: list[str]
    protected_source: Literal["wdpa", "assumed_free"]
    protected_wdpa_repair: GeometryRepairSummary
    grid_metadata: GridMetadata


class SuitabilityCriteriaResult(BaseModel):
    """Root output model for the suitability_criteria phase.

    Carries only paths and statistics — never numpy arrays (audit D6).
    Fase 3 (suitability_builder) re-reads the .tif files from tif_dir.

    Args:
        country_code: ISO-3166-alpha-3 code this run covers.
        timestamp: ISO-8601 UTC timestamp when the phase started.
        tif_dir: Directory holding the <name>.tif criterion rasters.
        figure_dir: Directory holding the <name>.png criterion maps.
        report_path: The bespoke text summary
            (reports/criteria_summary_<ISO3>.txt).
        criteria: Produced criteria, keyed by name (subset of
            CANONICAL_CRITERIA).
        slope_degrees_tif: The cartography-only absolute-slope raster,
            written but outside `criteria` (audit sec 2b), or None if
            slope was absent.
        slope_degrees_png: The cartography PNG for slope_degrees, or
            None if slope was absent. Kept alongside slope_degrees_tif
            rather than as a CriterionLayer, matching that field's own
            not-a-canonical-criterion status.
        summary: Roll-up (see SuitabilityCriteriaSummary).
    """

    model_config = ConfigDict(extra="forbid")

    country_code: str
    timestamp: str
    tif_dir: Path
    figure_dir: Path
    report_path: Path
    criteria: dict[str, CriterionLayer]
    slope_degrees_tif: Path | None = None
    slope_degrees_png: Path | None = None
    summary: SuitabilityCriteriaSummary

    @model_validator(mode="after")
    def _summary_consistent_with_criteria(self) -> SuitabilityCriteriaResult:
        if self.summary.n_criteria != len(self.criteria):
            raise ValueError(
                f"summary.n_criteria ({self.summary.n_criteria}) does not match "
                f"len(criteria) ({len(self.criteria)})."
            )
        unknown = set(self.criteria) - set(CANONICAL_CRITERIA)
        if unknown:
            raise ValueError(f"non-canonical criterion keys: {sorted(unknown)}.")
        mismatched = [k for k, v in self.criteria.items() if v.name != k]
        if mismatched:
            raise ValueError(f"criteria dict key != CriterionLayer.name for: {mismatched}.")

        produced = set(self.criteria)
        missing = set(self.summary.missing_expected)
        not_impl = set(self.summary.not_implemented)
        buckets = [("produced", produced), ("missing_expected", missing), ("not_implemented", not_impl)]
        for i, (name_a, a) in enumerate(buckets):
            for name_b, b in buckets[i + 1 :]:
                overlap = a & b
                if overlap:
                    raise ValueError(
                        f"{name_a} and {name_b} overlap: {sorted(overlap)}."
                    )
        union = produced | missing | not_impl
        if union != set(CANONICAL_CRITERIA):
            raise ValueError(
                "produced + missing_expected + not_implemented must partition "
                f"CANONICAL_CRITERIA; symmetric difference: "
                f"{sorted(union ^ set(CANONICAL_CRITERIA))}."
            )
        return self
