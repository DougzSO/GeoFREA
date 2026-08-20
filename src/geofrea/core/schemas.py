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

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

VerificationMethod = Literal["manual_cross_check", "automated", "unverified"]

# Named constrained-type aliases, used as generic parameters of
# VerifiedValue[...] below, so the constraint travels with the field
# that actually needs it rather than being forced onto every value the
# generic wrapper holds (e.g. capex_usd_per_kw has no [0, 1] bound).
UnitInterval = Annotated[float, Field(ge=0, le=1)]
PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]


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
        slope_threshold_deg: Maximum terrain slope, in degrees, above
            which a pixel is excluded as unsuitable for this
            technology. Used by data_quality_audit's slope-inactivity
            check and (in a later phase) suitability_criteria's hard
            exclusion. Constrained to >= 0.
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


class SettingsFile(BaseModel):
    """Root schema for config/settings.yaml.

    No VerifiedValue wrapper here: that metadata block exists for
    scientific parameters.json values with a citable source (see
    docs/CONVENTIONS.md, "Parameter verification metadata") — it
    doesn't apply to operational settings like phase toggles.

    Args:
        run: Country/phase selection for a pipeline execution.
    """

    model_config = ConfigDict(extra="forbid")

    run: RunConfig
