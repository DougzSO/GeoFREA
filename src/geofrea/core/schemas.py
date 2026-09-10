"""Pydantic schemas for GeoFREA's parameters.json and settings.yaml.

"biomass", "solar", and "wind" are all modeled and populated in
config/parameters.json (see docs/DECISIONS.md 2026-08-20 entries).
Everything lives in one module because the three technology models
share one common shape; splitting by domain is deferred until that
stops being true, per docs/CONVENTIONS.md "Parameters" (no schemas
against data that doesn't exist yet).

All models forbid extra fields (model_config = ConfigDict(extra=
"forbid")): an unexpected or misspelled key in parameters.json must
raise ValidationError, not be silently dropped.

discount_rate lives on each technology's params model, not on
CountryParams: IRENA's benchmark tool gives genuinely different rates
per technology for the same country (e.g. PRT: biomass=5%, solar=4.2%,
wind=3.7%), so a single country-level field cannot represent it. See
DECISIONS.md 2026-08-20 - discount_rate architecture fix.

SettingsFile (settings.yaml) is a separate, much simpler schema: plain
operational values (which countries/phases to run), no verification-
metadata wrapper — that wrapper exists for scientific parameters.json
values with a citable source, which operational toggles aren't. See
DECISIONS.md 2026-08-20 - settings.yaml phase toggles.
"""

from __future__ import annotations

from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

T = TypeVar("T")

VerificationMethod = Literal["manual_cross_check", "automated", "unverified"]

# Named constrained-type aliases, used as generic parameters of
# VerifiedValue[...] below, so the constraint travels with the field
# that actually needs it rather than being forced onto every value the
# generic wrapper holds (e.g. capex_usd_per_kw has no [0, 1] bound).
UnitInterval = Annotated[float, Field(ge=0, le=1)]
PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]
PositiveFloat = Annotated[float, Field(gt=0)]
Percentile = Annotated[float, Field(ge=0, le=100)]
SlopeDegrees = Annotated[float, Field(ge=0, le=90)]


class VerifiedValue(BaseModel, Generic[T]):
    """A parameter value with verification provenance metadata.

    Mirrors the block defined in docs/CONVENTIONS.md, "Parameter
    verification metadata". A value with verified=False is not blocked
    from use by this schema — it only requires the provenance fields to
    be present and readable.

    Args:
        value: The parameter value itself. May be None for parameters
            that are pending research (e.g. an unpopulated
            opex_variable_usd_per_kwh for a technology whose source
            doesn't split fixed/variable O&M).
        source: Citation for where the value comes from (e.g.
            "IRENA 2025"), or None if unverified.
        verified: Whether the value has been independently confirmed
            against its cited source.
        verified_by: Name of the person who verified the value, or
            None if verified is False.
        verified_date: ISO date string (YYYY-MM-DD) of verification, or
            None if verified is False.
        verification_method: How the value was verified.
        note: Optional free-text caveat (e.g. "chosen midpoint of a
            reported range, not a directly reported single figure").
        status: Optional free-text status for values that are not yet
            resolved (e.g. "pending_research").
    """

    model_config = ConfigDict(extra="forbid")

    value: T
    source: str | None = None
    verified: bool
    verified_by: str | None = None
    verified_date: str | None = None
    verification_method: VerificationMethod
    note: str | None = None
    status: str | None = None


class _TechnologyEconomicParams(BaseModel):
    """Shared shape for per-technology economic/performance parameters.

    Args:
        capex_usd_per_kw: Capital expenditure, USD per kW installed.
        opex_fixed_pct_of_capex: O&M cost as a fraction of total
            installed cost. For biomass this is genuinely the fixed-
            only component (source splits fixed/variable); for solar
            and wind, the source reports only a combined/total O&M
            figure, so this field holds that total instead — see the
            "note" on each concrete technology's field for the exact
            caveat. Constrained to [0, 1].
        opex_variable_usd_per_kwh: Variable O&M cost, USD per kWh
            generated. Populated (float) for biomass; left as an
            unverified/null placeholder for solar and wind, whose
            source doesn't split fixed/variable O&M.
        capacity_factor: Dimensionless ratio of actual to nameplate
            generation, country-specific. Constrained to [0, 1].
        lifetime_years: Asset operational lifetime, in years. Must be
            positive.
        discount_rate: Technology-specific discount rate for this
            country (IRENA benchmark tool output, or the OECD/non-OECD
            default for technologies the benchmark tool doesn't cover).
            Constrained to >= 0.
        discount_rate_increment: Optional additional risk premium on
            top of discount_rate. Meaning differs by technology — see
            each concrete class's docstring.
    """

    model_config = ConfigDict(extra="forbid")

    capex_usd_per_kw: VerifiedValue[float]
    opex_fixed_pct_of_capex: VerifiedValue[UnitInterval]
    opex_variable_usd_per_kwh: VerifiedValue[float]
    capacity_factor: VerifiedValue[UnitInterval]
    lifetime_years: VerifiedValue[PositiveInt]
    discount_rate: VerifiedValue[NonNegativeFloat]
    discount_rate_increment: VerifiedValue[float | None]


class _TechnologySitingParams(BaseModel):
    """Shared shape for per-technology physical siting-constraint parameters.

    Kept separate from _TechnologyEconomicParams deliberately: these
    values feed suitability/audit checks (e.g. the slope-inactivity
    diagnostic in data_quality_audit), not LCOE — a different domain
    that happens to also be per-technology-per-country. Splitting the
    base keeps _TechnologyEconomicParams's name accurate and lets more
    siting constraints be added later (e.g. a wind setback distance)
    without touching the economic base. See docs/DECISIONS.md
    2026-08-20 - slope_threshold_deg moved to parameters.json.

    Args:
        slope_threshold_deg: Maximum terrain slope, in degrees, for this
            technology, as used by data_quality_audit's slope-inactivity
            diagnostic heuristic. Constrained to >= 0.

            NOT unified with suitability_criteria's siting exclusion
            gate: Fase 2b/3 uses its own fixed cross-country thresholds
            (CriteriaParams.slope_threshold_deg_{solar,wind,biomass} =
            5/25/15 deg), a deliberately separate value with a different
            purpose and different numbers. This per-technology per-
            country field stays as-is for the audit diagnostic, which is
            already in production and validated (see docs/DECISIONS.md
            2026-08-20 - slope_threshold_deg moved to parameters.json).
            The two are not merged by design — merging would change a
            live diagnostic's behavior only for schema tidiness, exactly
            the kind of cross-phase coupling this project avoids
            (PhaseContext.prior_results read-only). See docs/DECISIONS.md
            2026-09-10 - suitability_criteria parameter calibration.
            FUTURE: revisit unification when data_quality_audit is next
            worked on, not before.
    """

    model_config = ConfigDict(extra="forbid")

    slope_threshold_deg: VerifiedValue[NonNegativeFloat]


class BiomassParams(_TechnologyEconomicParams, _TechnologySitingParams):
    """Biomass technology parameters for a single country.

    See docs/DECISIONS.md 2026-08-20 - biomass parameters restructure
    (IRENA 2025), - biomass discount_rate and discount_rate_increment
    - resolucao das pendencias, and - slope_threshold_deg moved to
    parameters.json, for provenance of every field's value.

    discount_rate_increment here is 0.0 because bioenergy is NOT
    covered by IRENA's technology-specific WACC benchmark tool (which
    only differentiates onshore wind/offshore wind/solar PV) — it uses
    the flat OECD/non-OECD default directly, with no separate
    technology premium layered on top.
    """


class SolarParams(_TechnologyEconomicParams, _TechnologySitingParams):
    """Solar PV technology parameters for a single country.

    See docs/DECISIONS.md 2026-08-20 - solar and wind parameters
    populated (IRENA 2024/2025) and - slope_threshold_deg moved to
    parameters.json, for provenance of every field's value.

    opex_variable_usd_per_kwh is an unpopulated placeholder (value=
    None, verified=False, status="pending_research"): IRENA's source
    data reports only a combined/total O&M figure for solar, not split
    into fixed+variable components like biomass — opex_fixed_pct_of_capex
    actually carries the full O&M burden here despite its name.

    discount_rate_increment is 0.0 because discount_rate above is
    already the final technology-specific value from IRENA's benchmark
    tool, not a base+premium construction — kept at 0.0 for schema
    symmetry with biomass, not because a premium was computed and found
    to be zero.
    """

    opex_variable_usd_per_kwh: VerifiedValue[float | None]


class WindParams(_TechnologyEconomicParams, _TechnologySitingParams):
    """Onshore wind technology parameters for a single country.

    See docs/DECISIONS.md 2026-08-20 - solar and wind parameters
    populated (IRENA 2024/2025) and - slope_threshold_deg moved to
    parameters.json, for provenance of every field's value. Same
    opex_variable_usd_per_kwh and discount_rate_increment caveats as
    SolarParams apply here.
    """

    opex_variable_usd_per_kwh: VerifiedValue[float | None]


class TechnologyParams(BaseModel):
    """Per-technology parameters for a single country.

    Args:
        biomass: Biomass technology parameters.
        solar: Solar PV technology parameters.
        wind: Onshore wind technology parameters.
    """

    model_config = ConfigDict(extra="forbid")

    biomass: BiomassParams
    solar: SolarParams
    wind: WindParams


class CountryCriteriaParams(BaseModel):
    """Per-country inputs to suitability_criteria (Fase 2b).

    The parallel of ParametersFile.criteria (CriteriaParams, cross-
    country) for the criterion inputs that genuinely DO vary by country.
    The audit (docs/architecture/suitability_criteria_audit.md sec 8a)
    reserved the name CountryParams.criteria for "when a second per-
    country criterion parameter appears" — implementing terrain_score
    revealed it (terrain_slope_threshold_deg), so this sub-model now
    exists. Each field carries a whole-table / whole-value verification
    block (not per cell).

    Args:
        yield_by_land_cover: Biomass yield (dimensionless, legacy's own
            unit) per ESA WorldCover class code. Biomass availability
            differs by biome/climate, so values diverge across countries
            (legacy config: PRT/BRA/EGY/IND/RUS all different). Feeds the
            biomass_resource criterion. The cross-country ESA-class ->
            suitability-score table is separate and global
            (CriteriaParams.land_suitability). Ported verbatim from
            legacy geoworld_framework @ fc7b43d.
        terrain_slope_threshold_deg: Denominator (degrees) for
            terrain_score's continuous slope sub-score
            (clip(1 - slope/threshold, 0, 1)). NOT an exclusion gate —
            that is CriteriaParams.slope_threshold_deg_{tech}, fixed
            cross-country. This one is per-country in the legacy
            (PRT=10, BRA=12) and is the FOURTH distinct slope-threshold
            use in the pipeline (see docs/DECISIONS.md 2026-09-10 -
            suitability_criteria: terrain_score denominator is per-
            country). Ported verbatim from the legacy's country-level
            `slope_threshold_deg` field @ fc7b43d.
    """

    model_config = ConfigDict(extra="forbid")

    yield_by_land_cover: VerifiedValue[dict[int, float]]
    terrain_slope_threshold_deg: VerifiedValue[SlopeDegrees]


class CountryParams(BaseModel):
    """Top-level parameters for a single country.

    Args:
        technologies: Per-technology parameter sets for this country.
            There is no country-level discount_rate: each technology
            carries its own (see _TechnologyEconomicParams).
        criteria: Per-country suitability_criteria (Fase 2b) inputs —
            see CountryCriteriaParams. Distinct from
            ParametersFile.criteria (cross-country calibration).
    """

    model_config = ConfigDict(extra="forbid")

    technologies: TechnologyParams
    criteria: CountryCriteriaParams


class LandCoverSuitability(BaseModel):
    """Per-technology siting-suitability scores for one ESA WorldCover class.

    One row of CriteriaParams.land_suitability. The table is a single
    GLOBAL mapping: the ESA-class -> suitability logic ("grassland is
    good for biomass, built-up is excluded") is the same reasoning in
    every country, so it is not keyed per country (see docs/architecture/
    suitability_criteria_audit.md sec 8a, "Tabelas de criterio", and the
    per-country/global verdict in docs/DECISIONS.md 2026-09-10).
    Real per-country biomass availability is a separate table,
    CountryParams.yield_by_land_cover.

    In suitability_criteria (Fase 2b) only the `biomass` column is read
    (the `lc_biomass` criterion); `solar`/`wind` are consumed later in
    suitability_builder (Fase 3). Ported verbatim from legacy
    geoworld_framework @ fc7b43d (configs/parameters.json land_suitability).

    Args:
        solar: Solar-PV siting suitability for this land-cover class, [0, 1].
        wind: Onshore-wind siting suitability for this land-cover class, [0, 1].
        biomass: Biomass siting suitability for this land-cover class, [0, 1].
        description: Human-readable ESA class name, verbatim from the
            legacy table (redundant with core.constants.ESA_CLASS_NAMES,
            kept for a faithful port). Optional.
    """

    model_config = ConfigDict(extra="forbid")

    solar: UnitInterval
    wind: UnitInterval
    biomass: UnitInterval
    description: str | None = None


class CriteriaParams(BaseModel):
    """Cross-country calibration parameters for suitability_criteria (Fase 2b).

    A single top-level `criteria` block in config/parameters.json,
    parallel to `countries` (see ParametersFile) — NOT nested per
    country. Every field carries a VerifiedValue provenance block, same
    as the technology parameters; STRUCTURAL_PRESERVE values inherited
    from the legacy with no external source are still wrapped, marked
    verified=False / verification_method="unverified", for uniform
    traceability (see docs/architecture/suitability_criteria_audit.md
    sec 8a and docs/DECISIONS.md 2026-09-10 - suitability_criteria
    parameter calibration).

    slope_threshold_deg_{solar,wind,biomass}: the Fase 2b/3 siting
    exclusion thresholds (pixel excluded when slope exceeds the value).
    Fixed cross-country, replacing the legacy's uncited additive offset
    (country base + 5/10/20 deg). DISTINCT from
    _TechnologySitingParams.slope_threshold_deg (the audit diagnostic
    heuristic) — see that field's docstring; the two are not unified by
    design.

    road_max_dist_km / river_max_dist_biomass_km: confirmed by pixel-
    exact regression against outputs_baseline_fc7b43d/PRT (2026-09-10)
    to be the values that generated the frozen baseline — the legacy
    function-signature fallbacks (5.0 / 10.0) are dead code, not ported.

    Args:
        slope_threshold_deg_solar: Max slope (deg) for solar siting.
        slope_threshold_deg_wind: Max slope (deg) for wind siting.
        slope_threshold_deg_biomass: Max slope (deg) for biomass siting.
        river_safety_buffer_km: Riparian setback (km) — pixels closer
            than this to a river are excluded for solar/wind (a real
            hard exclusion in Fase 3, not a soft preference).
        pop_density_threshold: Population density (persons/km2) at which
            the log-penalty saturates for pop_suitability.
        road_max_dist_km: Distance (km) at which road-proximity
            suitability decays to 0 before percentile normalization.
        river_max_dist_biomass_km: Distance (km) at which river-access
            suitability decays to 0 for the biomass river criterion.
        grid_max_dist_km: Distance (km) at which power-grid proximity
            suitability decays to 0 before percentile normalization.
        normalization_min_percentile / normalization_max_percentile:
            Percentile clip bounds for the resource criteria
            (solar/wind/biomass resource).
        seismic_percentile_low / seismic_percentile_high: Percentile
            clip bounds for seismic normalization (narrower than the
            resource bounds in the legacy; kept as-is).
        linear_proximity_percentile_low / linear_proximity_percentile_high:
            Percentile clip bounds applied after the linear decay for
            roads / grid / proximity_plants.
        terrain_slope_weight / terrain_tri_weight: Convex-combination
            weights for terrain_score (slope component vs. TRI
            component); must sum to 1.
        tri_threshold_m: Denominator (metres) for the TRI roughness
            sub-score.
        proximity_decay_sigma_km: Exponential decay length (km) for
            proximity_plants.
        proximity_smooth_sigma_px: Gaussian smoothing sigma (pixels,
            resolution-scaled at runtime) for proximity_plants.
        proximity_plants_neutral_score: Score assigned to all land
            pixels when a country has no recorded power plants.
        biomass_smooth_sigma: Gaussian smoothing sigma for
            biomass_resource (0 disables smoothing).
        solar_pvout_weight: Optional multiplier applied to the
            normalized solar resource score (1.0 = no-op).
        renewable_fuel_labels: Fuel-name substrings classifying an
            existing plant as "renewable" in proximity_plants.
        protected_as_exclusion: When True, IUCN strict-category polygons
            are scored 0.0 (hard exclusion) in protected_areas.
        iucn_strict_categories: IUCN category codes (lowercased) scored
            0.0 when protected_as_exclusion is True. Ratified author
            decision, 2026-08-19 (no external citation).
        land_suitability: Global ESA-class -> {solar, wind, biomass}
            suitability table (see LandCoverSuitability). One
            verification block for the whole table.
    """

    model_config = ConfigDict(extra="forbid")

    slope_threshold_deg_solar: VerifiedValue[SlopeDegrees]
    slope_threshold_deg_wind: VerifiedValue[SlopeDegrees]
    slope_threshold_deg_biomass: VerifiedValue[SlopeDegrees]
    river_safety_buffer_km: VerifiedValue[NonNegativeFloat]
    pop_density_threshold: VerifiedValue[PositiveFloat]
    road_max_dist_km: VerifiedValue[PositiveFloat]
    river_max_dist_biomass_km: VerifiedValue[PositiveFloat]
    grid_max_dist_km: VerifiedValue[PositiveFloat]
    normalization_min_percentile: VerifiedValue[Percentile]
    normalization_max_percentile: VerifiedValue[Percentile]
    seismic_percentile_low: VerifiedValue[Percentile]
    seismic_percentile_high: VerifiedValue[Percentile]
    linear_proximity_percentile_low: VerifiedValue[Percentile]
    linear_proximity_percentile_high: VerifiedValue[Percentile]
    terrain_slope_weight: VerifiedValue[UnitInterval]
    terrain_tri_weight: VerifiedValue[UnitInterval]
    tri_threshold_m: VerifiedValue[PositiveFloat]
    proximity_decay_sigma_km: VerifiedValue[PositiveFloat]
    proximity_smooth_sigma_px: VerifiedValue[PositiveFloat]
    proximity_plants_neutral_score: VerifiedValue[UnitInterval]
    biomass_smooth_sigma: VerifiedValue[NonNegativeFloat]
    solar_pvout_weight: VerifiedValue[PositiveFloat]
    renewable_fuel_labels: VerifiedValue[list[str]]
    protected_as_exclusion: VerifiedValue[bool]
    iucn_strict_categories: VerifiedValue[list[str]]
    land_suitability: VerifiedValue[dict[int, LandCoverSuitability]]

    @model_validator(mode="after")
    def _percentile_bounds_ordered(self) -> CriteriaParams:
        pairs = (
            ("normalization_min_percentile", "normalization_max_percentile"),
            ("seismic_percentile_low", "seismic_percentile_high"),
            ("linear_proximity_percentile_low", "linear_proximity_percentile_high"),
        )
        for lo_name, hi_name in pairs:
            lo = getattr(self, lo_name).value
            hi = getattr(self, hi_name).value
            if lo >= hi:
                raise ValueError(
                    f"{lo_name} ({lo}) must be strictly less than {hi_name} ({hi})."
                )
        return self

    @model_validator(mode="after")
    def _terrain_weights_sum_to_one(self) -> CriteriaParams:
        total = self.terrain_slope_weight.value + self.terrain_tri_weight.value
        if abs(total - 1.0) > 1e-9:
            raise ValueError(
                f"terrain_slope_weight + terrain_tri_weight must sum to 1.0, got {total}."
            )
        return self


class ParametersFile(BaseModel):
    """Root schema for config/parameters.json.

    Args:
        countries: Mapping of ISO-3166-alpha-3 country code to that
            country's parameters. Currently PRT and BRA.
        criteria: Cross-country calibration parameters for
            suitability_criteria (Fase 2b). Required — absence of a
            config block is treated as a bug class in this project, not
            a "use defaults" signal (see docs/CONVENTIONS.md,
            "Parameters").
    """

    model_config = ConfigDict(extra="forbid")

    countries: dict[str, CountryParams]
    criteria: CriteriaParams


class RunConfig(BaseModel):
    """Which countries/phases a pipeline execution should cover.

    Args:
        countries: ISO-3166-alpha-3 codes to run. Empty list means "run
            every country present in parameters.json's 'countries' key"
            — resolved dynamically by the (future) phase runner, not
            hardcoded here. See config_loader.py::load_settings().
        phases: One flag per pipeline module, keyed by the same names
            used in docs/PROGRESS.json's "modulos" array and the
            src/geofrea/<name>/ package layout. True = phase runs for
            this execution, False = disabled (mirrors the legacy
            geoworld_framework's skip_* toggles, inverted for a
            non-double-negative reading).
    """

    model_config = ConfigDict(extra="forbid")

    countries: list[str]
    phases: dict[str, bool]


class AdaptiveResolutionConfig(BaseModel):
    """Fallback knobs for grid_alignment's adaptive-resolution mode.

    Only consulted when ResolutionsConfig.suitability == "adaptive".
    Ported as-is from legacy's own fallback dict (grid_aligner.py's
    `adaptive_cfg` default) — see docs/DECISIONS.md 2026-09-09,
    grid_alignment Passo 4 item 3: this mode is NOT what generated the
    frozen PRT/BRA baseline (that used a fixed 0.01 degrees, see
    ResolutionsConfig.suitability's own docstring), and `target_pixels`
    has no found calibration basis anywhere in legacy — confirmed to
    have ZERO effect on large countries in practice (BRA's unclamped
    ideal resolution would be ~0.175 deg, so it always saturates at
    `max_deg` regardless of `target_pixels`). Kept available as an
    explicit opt-in for whoever needs it, not the default.

    Args:
        target_pixels: Target total grid pixel count the adaptive
            formula solves for. Uncalibrated (no documented basis —
            processing time, minimum siting resolution, or otherwise).
        min_deg: Lower clamp on the computed resolution, in degrees.
        max_deg: Upper clamp on the computed resolution, in degrees —
            the value that actually controls large-country output in
            practice (see class docstring).
    """

    model_config = ConfigDict(extra="forbid")

    target_pixels: PositiveInt = 50000
    min_deg: PositiveFloat = 0.001
    max_deg: PositiveFloat = 0.05


class ResolutionsConfig(BaseModel):
    """geospatial.resolutions section — grid_alignment's target grid resolution.

    Args:
        suitability: Either a fixed resolution in decimal degrees, or
            the literal string "adaptive" to compute it dynamically
            from country area (see AdaptiveResolutionConfig). Default
            0.01 (~1km) matches legacy's own actual configured value
            ("~1 km — consistent with global climate datasets",
            configs/settings.yaml) — the one that generated the frozen
            PRT/BRA baseline (docs/architecture/baseline-manifest.md).
            Legacy's "adaptive" code path existed but was never the
            configured value in the run that produced that baseline —
            see docs/DECISIONS.md 2026-09-09, grid_alignment Passo 4
            item 3, for the measured divergence (BRA: baseline
            3920x3902px @ 0.01deg vs. adaptive's 785x781px @ 0.05deg,
            ~25x fewer pixels).
        adaptive: Fallback knobs used only when suitability=="adaptive".
    """

    model_config = ConfigDict(extra="forbid")

    suitability: PositiveFloat | Literal["adaptive"] = 0.01
    adaptive: AdaptiveResolutionConfig = AdaptiveResolutionConfig()


class GeospatialConfig(BaseModel):
    """geospatial section of settings.yaml.

    Args:
        resolutions: grid_alignment's target-resolution configuration.
    """

    model_config = ConfigDict(extra="forbid")

    resolutions: ResolutionsConfig = ResolutionsConfig()


class SettingsFile(BaseModel):
    """Root schema for config/settings.yaml.

    No VerifiedValue wrapper here: that metadata block exists for
    scientific parameters.json values with a citable source (see
    docs/CONVENTIONS.md, "Parameter verification metadata") — it
    doesn't apply to operational settings like phase toggles.

    Args:
        run: Country/phase selection for a pipeline execution.
        geospatial: Spatial processing configuration (currently just
            grid_alignment's target resolution).
    """

    model_config = ConfigDict(extra="forbid")

    run: RunConfig
    geospatial: GeospatialConfig = GeospatialConfig()
