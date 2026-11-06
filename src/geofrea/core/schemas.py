"""Pydantic schemas for GeoFREA's parameters.json and settings.yaml.

"biomass", "solar", and "wind" are all modeled and populated in
config/parameters.json (see docs/_archive/2026-09/DECISIONS.md 2026-08-20 entries).
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
        distribution: Distribution type: 'uniform', 'triangular', or 'discrete_uniform' (the integers from min to max with equal
            probability, for a count of whole years such as the lifetime; min and max are integers).
        source: Citation for where the range comes from.
        tier: Evidence tier (1, 2, 3, or null) for the range itself
            (may differ from the nominal value's tier).
    """

    model_config = ConfigDict(extra="forbid")

    min: float
    max: float
    distribution: Literal["uniform", "triangular", "discrete_uniform"]
    source: str
    tier: Literal[1, 2, 3] | None = None

    @model_validator(mode="after")
    def _min_max_ordered(self) -> ParameterRange:
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) must be <= max ({self.max}).")
        if self.distribution == "discrete_uniform" and (
            self.min != int(self.min) or self.max != int(self.max)
        ):
            raise ValueError("a discrete_uniform range has integer min and max.")
        return self


class ScenarioValues(BaseModel):
    """The three values of a parameter that is paired with the F3 land-availability scenarios and is not sampled (U-06, M-F5-01).

    Args:
        restrictive: Value in the restrictive scenario.
        central: Value in the central scenario; it equals the parameter's `value` (the one deterministic runs use).
        permissive: Value in the permissive scenario.
    """

    model_config = ConfigDict(extra="forbid")

    restrictive: float
    central: float
    permissive: float

    def for_scenario(self, scenario: str) -> float:
        """The value of the named land scenario; an unknown name raises."""
        try:
            return float(getattr(self, scenario))
        except AttributeError:
            raise ValueError(
                f"unknown land scenario {scenario!r} (known: restrictive, central, permissive)"
            ) from None


class VerifiedValue(BaseModel, Generic[T]):
    """A parameter value with verification provenance metadata and uncertainty range.

    Mirrors the block defined in METHODOLOGY U-05 and docs/CONVENTIONS.md,
    "Parameter verification metadata". A value with verified=False is not
    blocked from use by this schema — it only requires the provenance fields
    to be present and readable.

    Args:
        value: The parameter value itself. May be None for parameters
            that have no researched value (e.g. an unpopulated
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
        scenario_values: The restrictive, central and permissive values of a parameter paired with the F3 land scenarios instead of
            sampled (LUF and power density, U-06); `value` equals the central one. Null for every other parameter, whose value
            then applies in all three scenarios.
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
    scenario_values: ScenarioValues | None = None
    price_year: int | None = None

    @model_validator(mode="after")
    def _scenario_values_central_is_the_value(self) -> VerifiedValue:
        """The central scenario value is the parameter value, so a deterministic run and the central scenario agree."""
        if (
            self.scenario_values is not None
            and self.value is not None
            and self.scenario_values.central != self.value
        ):
            raise ValueError(
                f"scenario_values.central ({self.scenario_values.central}) must equal value ({self.value})."
            )
        return self

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


CostStatus = Literal["sourced", "verify", "proxy", "provisional", "to_be_sourced"]
GROUP3_RENAMED_KEYS = {
    "grid_cost_usd_per_mw_km": "line_cost_per_km (countries.<ISO3>.connection, per project in the currency of the source)",
    "substation_cost_usd_per_mw": "bay_cost (countries.<ISO3>.connection, per bay)",
    "road_cost_usd_per_km": "road_cost_per_km (countries.<ISO3>.connection)",
}


class UnitCost(BaseModel):
    """A per-project unit cost of the external connection in the currency and price year of its source (Group 3, U-05).

    The value is never stored in USD: F6 converts it to constant 2024 USD with the national GDP deflator and the 2024 average exchange rate
    (`lcoe_modeling/connection.py`). A cost with `status = "to_be_sourced"` has no value (F6 refuses to run until it has one).

    Args:
        value: Central value in `unit`, or null while the cost is to be sourced.
        low: Lower bound of the sampling range, in `unit`.
        high: Upper bound of the sampling range, in `unit`.
        unit: Human-readable unit of the source (for example `INR crore/km`, `MEUR`).
        currency: ISO 4217 code of the source currency.
        scale: Currency units in one `unit` of the source (10,000,000 for crore, 1,000,000 for a million).
        per: What the cost is incurred per: `km` of line or road, or `bay` (a connection at the receiving substation).
        price_year: Price base year of the source, or null while it is unconfirmed (status `verify`).
        source: BibTeX key or citation of the source.
        status: `sourced`, `verify` (value present, a detail such as the base year to be confirmed), `proxy` (a regulator's figure of another
        nature stands in for the cost, COMMAND 86), `provisional` (a benchmark of another region or period, Tier 3) or `to_be_sourced` (no value).
        tier: Evidence tier (U-07).
        note: Free-text caveat (voltage class, whether right of way is included).
        open_question: Open question that tracks a missing value (for example `OQ-001`).
        synthetic: True for a test value of the synthetic country.
    """

    model_config = ConfigDict(extra="forbid")

    value: float | None = None
    low: float | None = None
    high: float | None = None
    unit: str
    currency: str
    scale: PositiveFloat = 1.0
    per: Literal["km", "bay"]
    price_year: int | None = None
    source: str | None = None
    status: CostStatus
    tier: Literal[1, 2, 3] | None = None
    note: str | None = None
    open_question: str | None = None
    synthetic: bool = False  # a test value of the synthetic country (A-06), never a sourced cost

    @model_validator(mode="after")
    def _consistent(self) -> UnitCost:
        """A to_be_sourced cost has no number; a sourced one has the value inside its range."""
        numbers = (self.value, self.low, self.high)
        if self.status == "to_be_sourced":
            if any(v is not None for v in numbers):
                raise ValueError("a cost with status to_be_sourced must have null value, low and high.")
            return self
        if any(v is None for v in numbers):
            raise ValueError(f"a cost with status {self.status!r} needs value, low and high.")
        if not self.low <= self.value <= self.high:
            raise ValueError(f"value ({self.value}) must be within [{self.low}, {self.high}].")
        if min(numbers) < 0:
            raise ValueError("a cost must not be negative.")
        return self


class ZoneRate(BaseModel):
    """The annual PV degradation of one thermal zone computed from the fleet data (fractions per year, positive).

    Args:
        n: Systems behind the rate (after the filter, and after merging when `merged_with` is set).
        median: Zone median, the central value.
        mean: Zone mean, the upper end of the sampling range when it exceeds the median.
        merged_with: The zone whose systems were pooled with this one because the zone had fewer than `min_systems`.
    """

    model_config = ConfigDict(extra="forbid")

    n: int
    median: NonNegativeFloat
    mean: NonNegativeFloat
    merged_with: str | None = None


class HotZoneSensitivity(BaseModel):
    """The deterministic sensitivity `pv_hot_zone_degradation`: one rate for every cell of thermal zone `applies_from_zone` or above (not sampled).

    Args:
        rate: Annual degradation (fraction per year) replacing the zone rate of those cells, both bounds.
        applies_from_zone: First zone number the rate applies to (7 = T7 and hotter).
        source: Where the rate comes from.
    """

    model_config = ConfigDict(extra="forbid")

    rate: PositiveFloat
    applies_from_zone: PositiveInt
    source: str


class PvDegradationByZone(BaseModel):
    """PV degradation rates by thermal zone T1 to T7, derived from the public fleet data (Group 3; `scripts/derive_pv_degradation_by_zone.py`).

    The central rate of a cell is the median of its zone; the sampling range runs from the median to the mean when the mean is higher
    (the sample is skewed toward faster degradation). Cells of a zone hotter than T7 take the T7 rate.
    """

    model_config = ConfigDict(extra="forbid")

    source: str
    tier: Literal[1, 2, 3] | None = None
    filter: str
    min_systems: PositiveInt
    generated_date: str | None = None
    synthetic: bool = False
    zones: dict[str, ZoneRate]
    hot_zone_sensitivity: HotZoneSensitivity | None = None

    @model_validator(mode="after")
    def _zones_are_t1_to_t7(self) -> PvDegradationByZone:
        expected = {f"T{i}" for i in range(1, 8)}
        if self.zones and set(self.zones) != expected:
            raise ValueError(f"zones must be exactly {sorted(expected)}, got {sorted(self.zones)}.")
        return self


class ConnectionParams(BaseModel):
    """Group 3 parameters of one country: point of interconnection, reference project, lengths, unit costs and losses.

    Values match `docs/thesis/methods/group3_connection_degradation.tex`. The costs are per project (a line, a bay, a road) and are spread
    over `reference_project_mw` by F6. `transmission_loss_per_km` is 0 in the central case; `transmission_loss_per_km_sensitivity` carries the
    range of the named scenario `transmission_losses`.

    `road_cost_excluded` (COMMAND 85) is the central scenario of a country whose access-road cost has no source: the road term is zero, F6 warns that
    the LCOE is a lower bound, and `road_cost_per_km_high` (when it has a value) is the named sensitivity `road_cost_high` that bills a road.
    """

    model_config = ConfigDict(extra="forbid")

    poi_voltage_threshold_kv: VerifiedValue[PositiveFloat]
    poi_sensitivity_threshold_kv: VerifiedValue[PositiveFloat] | None = None  # sensitivity layer `poi_sensitivity` (IND 132 kV)
    reference_project_mw: VerifiedValue[PositiveFloat]
    tortuosity_grid: VerifiedValue[PositiveFloat]
    tortuosity_road: VerifiedValue[PositiveFloat]
    long_distance_flag_km: VerifiedValue[PositiveFloat]
    transmission_loss_per_km: VerifiedValue[NonNegativeFloat]
    transmission_loss_per_km_sensitivity: VerifiedValue[NonNegativeFloat]
    line_cost_per_km: UnitCost
    bay_cost: UnitCost
    road_cost_per_km: UnitCost
    road_cost_excluded: bool = False
    road_cost_per_km_high: UnitCost | None = None
    conversion_indices_path: str  # relative to GEOFREA_DATA_DIR: World Bank NY.GDP.DEFL.ZS and PA.NUS.FCRF with source and access date


class _RejectsRenamedKeys(BaseModel):
    """Refuses the pre-Group-3 cost names, whose unit (USD per MW and km) differs from the new ones, with the migration in the message."""

    @model_validator(mode="before")
    @classmethod
    def _old_names(cls, data):
        if isinstance(data, dict):
            old = [k for k in GROUP3_RENAMED_KEYS if k in data]
            if old:
                listing = "; ".join(f"{k} -> {GROUP3_RENAMED_KEYS[k]}" for k in old)
                raise ValueError(
                    f"parameters.json uses pre-Group-3 cost names with a different unit (USD per MW and km): {listing}. "
                    "Rename, do not reuse (COMMAND 83)."
                )
        return data


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
    discount_rate: VerifiedValue[NonNegativeFloat | None]  # null where the rate has no source; a production run refuses it
    discount_rate_increment: VerifiedValue[float | None]
    commissioning_year: VerifiedValue[PositiveInt] | None = None  # t_ref of the technology vintage (OQ-018); not read by the kernel


class _TechnologySitingParams(BaseModel):
    """Shared shape for per-technology physical siting-constraint parameters.

    Kept separate from _TechnologyEconomicParams deliberately: these
    values feed suitability/audit checks (e.g. the slope-inactivity
    diagnostic in data_quality_audit), not LCOE — a different domain
    that happens to also be per-technology-per-country. Splitting the
    base keeps _TechnologyEconomicParams's name accurate and lets more
    siting constraints be added later (e.g. a wind setback distance)
    without touching the economic base. See docs/_archive/2026-09/DECISIONS.md
    2026-08-20 - slope_threshold_deg moved to parameters.json.

    The slope maximum used to live here (a per-technology, per-country value for the audit's slope-inactivity diagnostic). It
    now comes from `land_availability` in `config/experiments.yaml`, a range shared by every country (2026-10-08, Douglas), so
    this base carries no field at present.
    """

    model_config = ConfigDict(extra="forbid")


class SolarParams(_RejectsRenamedKeys, _TechnologyEconomicParams, _TechnologySitingParams):
    """Solar PV technology parameters for a single country.

    See docs/_archive/2026-09/DECISIONS.md 2026-08-20 - solar and wind parameters
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
    degradation_by_zone: PvDegradationByZone | None  # Group 3: rates by thermal zone T1-T7 (the PV zone of the cell picks the rate)
    cf_min: VerifiedValue[UnitInterval | None]  # M-F7-01 (OQ-008), fraction
    tau_lcoe_usd_per_mwh: VerifiedValue[NonNegativeFloat | None]  # M-F7-04 (OQ-008), 2024 USD
    top_k_percent: VerifiedValue[PositiveFloat | None]  # M-F7-05 (OQ-021), 0 < p_k <= 100


class WindParams(_RejectsRenamedKeys, _TechnologyEconomicParams, _TechnologySitingParams):
    """Onshore wind technology parameters for a single country.

    See docs/_archive/2026-09/DECISIONS.md 2026-08-20 - solar and wind parameters
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
    degradation_rate: VerifiedValue[UnitInterval | None]  # Group 3: central = newer vintages, range up to older vintages, fraction per year
    wind_degradation_complex_terrain: VerifiedValue[UnitInterval | None]  # Group 3: deterministic sensitivity, not sampled
    cf_min: VerifiedValue[UnitInterval | None]  # M-F7-01 (OQ-008), fraction
    tau_lcoe_usd_per_mwh: VerifiedValue[NonNegativeFloat | None]  # M-F7-04 (OQ-008), 2024 USD
    top_k_percent: VerifiedValue[PositiveFloat | None]  # M-F7-05 (OQ-021), 0 < p_k <= 100


class TechnologyParams(BaseModel):
    """Per-technology parameters for a single country.

    Args:
        solar: Solar PV technology parameters.
        wind: Onshore wind technology parameters.

    Note: biomass technology parameters were removed per METHODOLOGY A-04
    and Section 9 (S-02 scope: only solar and wind).
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
    connection: ConnectionParams | None = None  # Group 3 (F6 refuses a country without it)


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


class RoadClasses(BaseModel):
    """Road classes that count for the distance to the road (Group 3: primary and secondary roads, their higher classes kept).

    Args:
        grip4_gp_rtp: Values of the GRIP4 `GP_RTP` road-type field to keep (1 highways, 2 primary, 3 secondary, 4 tertiary, 5 local).
        osm_highway: Values of the OSM `highway` tag to keep.
    """

    model_config = ConfigDict(extra="forbid")

    grip4_gp_rtp: list[int]
    osm_highway: list[str]


class GeospatialConfig(BaseModel):
    """geospatial section of settings.yaml.

    Args:
        resolutions: grid_alignment's target-resolution configuration.
        distance_cap_km: Threshold (km) of the `distance_capped` QC flag written beside the
            distance-to-grid/roads/rivers rasters (M-F2a-03). It never truncates a distance:
            the connection-cost model bills the real one (OQ-040, METHODOLOGY 1.4.0).
            The value lives only in settings.yaml (no default here, CONVENTIONS).
        poi_line_tolerance_m: Distance (m) within which an OSM line reaches a substation, for the voltage a substation without a tag inherits
            (Group 3, `poi.py`); recorded in the manifest through the fingerprint of the configuration.
        road_classes: The road classes that count for the distance to the road (Group 3).
        poi_substations_geojson: Path pattern, relative to GEOFREA_DATA_DIR, of the substations of a country as nodes, ways and relations
            (`{iso}` is replaced; `scripts/fetch_osm_substations.py`).
        pvcz_csv: Path, relative to GEOFREA_DATA_DIR, of the PVCZ-2019 land points (Karin et al. 2019) with the thermal zone of each.
        pvcz_max_distance_km: Largest distance from a cell centre to the nearest PVCZ land point for the cell to take its zone (a coastal
            cell takes the nearest land point); beyond it the cell has no zone (Tier 3).
        gdal_cachemax_mb: Size (MB) of the GDAL block cache, set as `GDAL_CACHEMAX` for the process and for every layer child (COMMAND 88). Fixed, so
            that the cache does not grow with the physical memory of the machine.
        warp_mem_limit_mb: Working memory (MB) GDAL may use for one warp chunk in `reproject_to_grid` (rasterio `warp_mem_limit`). The warp of a
            sum (population) held 1.7 GB for a 49 MB window at the GDAL default and about 0.5 GB at 16 MB (docs/_audit/population_memory_87.md).
    """

    model_config = ConfigDict(extra="forbid")

    resolutions: ResolutionsConfig
    distance_cap_km: PositiveFloat
    poi_line_tolerance_m: NonNegativeFloat
    road_classes: RoadClasses
    poi_substations_geojson: str
    pvcz_csv: str
    pvcz_max_distance_km: PositiveFloat
    gdal_cachemax_mb: PositiveInt = 256
    warp_mem_limit_mb: PositiveInt = 16


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
        keep_awake: Whether `main.py` asks the operating system not to suspend the computer while the run goes on (V-T, D-core-027; Windows only,
            `core/power.py`). False when the key is absent.
        wind_cf_integral: How F5 evaluates the wind capacity factor integral `I(A, k)` (D-F5-039): `table` (the exact integral on a fixed
            grid, cubic spline, error below 1e-5 in the capacity factor; the setting of the runs) or `exact` (the closed form, the validation mode).
        checkpoint_max_gb: Bound, in GB, of the disk that the checkpoints of one piece of work may use (COMMAND 98, `core/checkpoint.py`); `main.py`
            passes it to every layer child as `GEOFREA_CHECKPOINT_MAX_GB`. Past it the units are not stored and the work goes on unprotected.
    """

    model_config = ConfigDict(extra="forbid")

    run: RunConfig
    geospatial: GeospatialConfig
    memory: MemoryConfig
    figures: Literal["all", "summary", "none"]
    wind_cf_integral: Literal["table", "exact"] = "exact"
    keep_awake: bool = False
    checkpoint_max_gb: PositiveFloat = 20.0


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
