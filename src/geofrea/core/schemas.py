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


class ParameterRange(BaseModel):
    """Uncertainty range for a scientific parameter.

    Used by U-05 (METHODOLOGY) to specify the range for uncertain parameters
    in F6/F7 ensembles. The range is null for non-uncertain parameters;
    every parameter listed in experiments.yaml uncertain_parameters must
    have a non-null range, enforced at config load.

    Args:
        min: Minimum value in the range.
        max: Maximum value in the range. Must be >= min.
        distribution: Distribution type ('uniform' or 'triangular').
        source: Citation for where the range comes from.
        tier: Evidence tier (1, 2, 3, or null) for the range itself
            (may differ from the nominal value's tier).
    """

    model_config = ConfigDict(extra="forbid")

    min: float
    max: float
    distribution: Literal["uniform", "triangular"]
    source: str
    tier: Literal[1, 2, 3] | None = None

    @model_validator(mode="after")
    def _min_max_ordered(self) -> ParameterRange:
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) must be <= max ({self.max}).")
        return self


class VerifiedValue(BaseModel, Generic[T]):
    """A parameter value with verification provenance metadata and uncertainty range.

    Mirrors the block defined in METHODOLOGY U-05 and docs/CONVENTIONS.md,
    "Parameter verification metadata". A value with verified=False is not
    blocked from use by this schema — it only requires the provenance fields
    to be present and readable.

    Args:
        value: The parameter value itself. May be None for parameters
            that are pending research (e.g. an unpopulated
            opex_var_usd_per_mwh for a technology whose source
            doesn't split fixed/variable O&M).
        unit: Physical unit of the parameter (e.g. "USD/kW", "fraction",
            "deg", "km"). Required for all parameters.
        source: Citation for where the value comes from (e.g.
            "IRENA 2025"), or None if unverified.
        tier: Evidence tier (1, 2, 3, or null) per METHODOLOGY U-07.
            Tier 1 = primary source specific to country+tech or physical
            standard; Tier 2 = primary source transferred from another
            region with recorded rationale; Tier 3 = author judgment/no
            source (must be listed in docs/LIMITATIONS.md). null = not
            yet assigned or not applicable (e.g. for non-uncertain
            parameters or parameters without a defined tier scheme).
        range: Uncertainty range for this parameter if it is uncertain
            (i.e. listed in experiments.yaml uncertain_parameters); null
            for non-uncertain parameters. Validation at config load ensures
            every uncertain parameter has range != null.
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
        synthetic: True marks this value as a TEST value belonging to a
            synthetic country fixture (METHODOLOGY A-06/V-08, OQ-032's
            verdict, docs/phases/core.md D-core-017/D-core-018) — chosen
            for what it exercises (e.g. a slope threshold picked so a
            known number of a fixture DEM's pixels fall on each side),
            never a real evidentiary claim, and never read into a thesis
            output. U-07's sourcing rule ("a methodological value without
            a documented primary source is never assumed") governs values
            that enter a result; it does not govern a fixture, but the
            two must never mix — enforced here by the validator below
            (synthetic and a real tier are mutually exclusive) and by
            tests/unit/test_synthetic_value_separation.py (no real
            country's parameters.json entry may set this True; ZZZ's
            entry must set it True on every VerifiedValue). Defaults
            False, so every existing real-country value is unaffected.
        proxy: True only when the value is of a different quantity or a different
            technology (U-05, V6; example: BRA and IND wind fixed O&M taken from solar
            O&M). Regional or global transfers of the same quantity and technology are
            Tier 2 (U-07), not proxies. A production run fails if a consumed parameter
            has proxy=True (`geofrea.core.production`).
        price_year: Price base year of a cost value in USD (S-07: constant 2024 USD).
            Null where the value is not a cost in USD or the year is not yet audited;
            F6 refuses a cost parameter whose year is null or not 2024 (D-F6-008).
    """

    model_config = ConfigDict(extra="forbid")

    value: T
    unit: str
    source: str | None = None
    tier: Literal[1, 2, 3] | None = None
    range: ParameterRange | None = None
    verified: bool
    verified_by: str | None = None
    verified_date: str | None = None
    verification_method: VerificationMethod
    note: str | None = None
    status: str | None = None
    synthetic: bool = False
    proxy: bool = False
    price_year: int | None = None

    @model_validator(mode="after")
    def _value_within_range_when_set(self) -> VerifiedValue:
        """Validate that value is within range bounds if range is set."""
        if (
            self.range is not None
            and self.value is not None
            and (self.value < self.range.min or self.value > self.range.max)
        ):
            raise ValueError(
                f"value ({self.value}) must be within range [{self.range.min}, {self.range.max}]."
            )
        return self

    @model_validator(mode="after")
    def _synthetic_never_carries_a_real_tier(self) -> VerifiedValue:
        """A test value's tier slot is never a real evidence tier (U-07), and vice versa.

        Enforces the mutual exclusion the fixture/sourced separation rule
        depends on: `synthetic=True` marks this as a test value, so
        `tier` (a real evidentiary claim of 1/2/3) must be None; a real
        tier, in turn, may only appear on a non-synthetic value.
        """
        if self.synthetic and self.tier is not None:
            raise ValueError(
                "VerifiedValue: synthetic=True values must not carry a real "
                "evidence tier (tier must be None) — a test value is never "
                "tiered evidence, per METHODOLOGY U-07/A-06."
            )
        return self


class _TechnologyEconomicParams(BaseModel):
    """Shared shape for per-technology economic/performance parameters.

    Args:
        capex_usd_per_kw: Capital expenditure, USD per kW installed.
        opex_fixed_frac: O&M cost as a fraction of total
            installed cost. For biomass this is genuinely the fixed-
            only component (source splits fixed/variable); for solar
            and wind, the source reports only a combined/total O&M
            figure, so this field holds that total instead — see the
            "note" on each concrete technology's field for the exact
            caveat. Constrained to [0, 1].
        opex_var_usd_per_mwh: Variable O&M cost, USD per MWh
            generated (M-F6-01). Populated (float) for biomass; left as an
            unverified/null placeholder for solar and wind, whose
            source doesn't split fixed/variable O&M.
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
    opex_fixed_frac: VerifiedValue[UnitInterval]
    opex_var_usd_per_mwh: VerifiedValue[float]
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

    The slope maximum used to live here (a per-technology, per-country value for the audit's slope-inactivity diagnostic). It
    now comes from `land_availability` in `config/experiments.yaml`, a range shared by every country (2026-10-08, Douglas), so
    this base carries no field at present.
    """

    model_config = ConfigDict(extra="forbid")


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

    opex_var_usd_per_mwh is an unpopulated placeholder (value=
    None, verified=False, status="pending_research"): IRENA's source
    data reports only a combined/total O&M figure for solar, not split
    into fixed+variable components like biomass — opex_fixed_frac
    actually carries the full O&M burden here despite its name.

    discount_rate_increment is 0.0 because discount_rate above is
    already the final technology-specific value from IRENA's benchmark
    tool, not a base+premium construction — kept at 0.0 for schema
    symmetry with biomass, not because a premium was computed and found
    to be zero.
    """

    opex_var_usd_per_mwh: VerifiedValue[float | None]
    luf: VerifiedValue[UnitInterval | None]  # M-F5-01 (OQ-004)
    power_density_mw_per_km2: VerifiedValue[NonNegativeFloat | None]  # M-F5-01 (OQ-004)
    gamma: VerifiedValue[float | None]  # M-F5-02 (OQ-023), 1/K, negative
    degradation_rate: VerifiedValue[UnitInterval | None]  # M-F6-01 (OQ-019), fraction per year
    grid_cost_usd_per_mw_km: VerifiedValue[NonNegativeFloat | None]  # M-F6-01 (OQ-001)
    substation_cost_usd_per_mw: VerifiedValue[NonNegativeFloat | None]  # M-F6-01 (OQ-001)
    road_cost_usd_per_km: VerifiedValue[NonNegativeFloat | None]  # M-F6-01 (OQ-001)


class WindParams(_TechnologyEconomicParams, _TechnologySitingParams):
    """Onshore wind technology parameters for a single country.

    See docs/DECISIONS.md 2026-08-20 - solar and wind parameters
    populated (IRENA 2024/2025) and - slope_threshold_deg moved to
    parameters.json, for provenance of every field's value. Same
    opex_var_usd_per_mwh and discount_rate_increment caveats as
    SolarParams apply here.

    The F5 parameters (M-F5-01, M-F5-03) are null with `status = "pending_research"` until OQ-004 and OQ-005 give a sourced
    value; `hub_height_m` replaces the former `hub_heights` of `technologies.yaml` (D-F5-012).
    """

    opex_var_usd_per_mwh: VerifiedValue[float | None]
    luf: VerifiedValue[UnitInterval | None]  # M-F5-01 (OQ-004)
    power_density_mw_per_km2: VerifiedValue[NonNegativeFloat | None]  # M-F5-01 (OQ-004)
    eta_loss: VerifiedValue[UnitInterval | None]  # M-F5-03 (OQ-005)
    hub_height_m: VerifiedValue[PositiveFloat | None]  # M-F5-03 (OQ-005), within 100 to 200 m
    degradation_rate: VerifiedValue[UnitInterval | None]  # M-F6-01 (OQ-019), fraction per year
    grid_cost_usd_per_mw_km: VerifiedValue[NonNegativeFloat | None]  # M-F6-01 (OQ-001)
    substation_cost_usd_per_mw: VerifiedValue[NonNegativeFloat | None]  # M-F6-01 (OQ-001)
    road_cost_usd_per_km: VerifiedValue[NonNegativeFloat | None]  # M-F6-01 (OQ-001)


class TechnologyParams(BaseModel):
    """Per-technology parameters for a single country.

    Args:
        solar: Solar PV technology parameters.
        wind: Onshore wind technology parameters.

    Note: biomass technology parameters were removed per METHODOLOGY A-04
    and Section 9 (S-02 scope: only solar and wind). BiomassParams class
    is retained in schemas.py for backward compatibility.
    """

    model_config = ConfigDict(extra="forbid")

    solar: SolarParams
    wind: WindParams


class CountryParams(BaseModel):
    """Top-level parameters for a single country.

    Args:
        technologies: Per-technology parameter sets for this country.
            There is no country-level discount_rate: each technology
            carries its own (see _TechnologyEconomicParams).
    """

    model_config = ConfigDict(extra="forbid")

    technologies: TechnologyParams


class ParametersFile(BaseModel):
    """Root schema for config/parameters.json.

    Args:
        countries: Mapping of ISO-3166-alpha-3 country code to that
            country's parameters. Currently PRT and BRA.
    """

    model_config = ConfigDict(extra="forbid")

    countries: dict[str, CountryParams]


class RunConfig(BaseModel):
    """Which countries/phases/technologies a pipeline execution should cover.

    Replaces the per-phase boolean toggle map (`phases: dict[str, bool]`)
    with explicit run targeting per METHODOLOGY A-03: the orchestrator
    resolves which phases actually execute from the requires/produces
    DAG (docs/phases/core.md D-core-001), not from a flat enabled/
    disabled map.

    Args:
        countries: ISO-3166-alpha-3 codes to run. Empty list means "run
            every country present in parameters.json's 'countries' key"
            — resolved dynamically by the (future) phase runner, not
            hardcoded here. See config_loader.py::load_settings().
        target_phases: Phase names to execute. Non-empty — the
            orchestrator also runs (or resumes) whatever these
            transitively require, so this need only name the phases the
            caller actually wants outputs for. Validated against the
            registered PhaseSpecs at run time (not by this schema,
            which does not know the registry).
        technologies: Technology keys (e.g. ["solar", "wind"]) to run.
            Non-empty, required per METHODOLOGY A-04. Validated against
            config/technologies.yaml keys at config load.
        rerun_phases: Phase names to re-execute even if already recorded
            as successful in the manifest — exactly these phases, never
            their dependents (see docs/phases/core.md's rerun_phases
            decision). Each name must be in the transitive dependency
            closure of target_phases; a name outside it is a validation
            error at run time (Orchestrator.run(), not this schema,
            which does not know the registered phase graph). Empty list
            (the default) means normal resume-from-manifest behavior —
            no phase is forced. A phase whose successful entry is marked
            stale_upstream by a rerun elsewhere in the DAG is recomputed
            automatically when this run needs it, whether or not it is
            named here.
    """

    model_config = ConfigDict(extra="forbid")

    countries: list[str]
    target_phases: list[str]
    technologies: list[str]
    rerun_phases: list[str] = []

    @model_validator(mode="after")
    def _target_phases_not_empty(self) -> RunConfig:
        if not self.target_phases:
            raise ValueError("run.target_phases must not be empty.")
        return self

    @model_validator(mode="after")
    def _technologies_not_empty(self) -> RunConfig:
        if not self.technologies:
            raise ValueError("run.technologies must not be empty.")
        return self


class ResolutionsConfig(BaseModel):
    """geospatial.resolutions section — grid_alignment's target grid resolution.

    Args:
        suitability: Fixed analysis-grid resolution in decimal degrees (M-F2a-01: 0.01, snapped so that
            0.05 degree cells nest 5 x 5). The value lives only in settings.yaml (no default here,
            CONVENTIONS). The legacy "adaptive" mode was removed in G-3 (2026-10-06): it was never the
            configured value and the method fixes the resolution.
    """

    model_config = ConfigDict(extra="forbid")

    suitability: PositiveFloat


class GeospatialConfig(BaseModel):
    """geospatial section of settings.yaml.

    Args:
        resolutions: grid_alignment's target-resolution configuration.
        distance_cap_km: Threshold (km) of the `distance_capped` QC flag written beside the
            distance-to-grid/roads/rivers rasters (M-F2a-03). It never truncates a distance:
            the connection-cost model bills the real one (OQ-040, METHODOLOGY 1.4.0).
            The value lives only in settings.yaml (no default here, CONVENTIONS).
    """

    model_config = ConfigDict(extra="forbid")

    resolutions: ResolutionsConfig
    distance_cap_km: PositiveFloat


class MemoryConfig(BaseModel):
    """memory section of settings.yaml (A-10).

    Args:
        max_batch_gb: Budget, in GB, of the largest cell-by-sample block F6 and F7 hold at once. The value lives only in
            settings.yaml (no default here, CONVENTIONS); F6 derives its cell-block size from it (D-F6-005).
    """

    model_config = ConfigDict(extra="forbid")

    max_batch_gb: PositiveFloat


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
        memory: Memory budget of the batch phases (A-10).
        figures: Which diagnostic figures a phase draws (A-08): `all`, `summary` (the figure the thesis output
            needs, not the member-level ones) or `none`. Rasters and tables are artifacts and are always written.
            Honoured by climate_maps, overview (with its per-layer maps) and potential_maps.
    """

    model_config = ConfigDict(extra="forbid")

    run: RunConfig
    geospatial: GeospatialConfig
    memory: MemoryConfig
    figures: Literal["all", "summary", "none"]


class GeometryRepairSummary(BaseModel):
    """Pydantic mirror of `geofrea.core.geo_utils.GeometryRepairReport`.

    A plain NamedTuple there (shared by every clip-path caller —
    data_quality_audit, siting_layers, and any future phase
    using `clip_vector_to_country()`/`read_clipped_to_country()`); this
    model exists only so a Pydantic phase-output schema can hold it
    with the same `extra="forbid"` validation every other field gets.
    Lives in core, not in either phase's own schemas module, since both
    need it and neither owns it. Field-for-field identical to the
    NamedTuple — see its docstring for what each one means.
    """

    model_config = ConfigDict(extra="forbid")

    n_total: int
    n_invalid: int
    n_repaired: int
    n_dropped_empty: int
    invalid_reasons: dict[str, int]
    country_polygon_repaired: bool
