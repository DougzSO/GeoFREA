"""Pydantic schemas for GeoFREA's parameters.json.

Only the "biomass" technology domain is modeled so far, reflecting the
current content of config/parameters.json (see docs/DECISIONS.md
2026-08-20 - biomass parameters restructure). Everything lives in one
module because there is currently only one populated domain; splitting
by domain (e.g. biomass.py, solar.py) is deferred until a second
technology is actually populated in parameters.json, per
docs/CONVENTIONS.md "Parameters" (no schemas against data that doesn't
exist yet).

All models forbid extra fields (model_config = ConfigDict(extra=
"forbid")): an unexpected or misspelled key in parameters.json must
raise ValidationError, not be silently dropped.
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
            that are pending research (e.g. discount_rate_increment).
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


class BiomassParams(BaseModel):
    """Biomass technology parameters for a single country.

    See docs/DECISIONS.md 2026-08-20 - biomass parameters restructure
    (IRENA 2025) for provenance of every field's current value.

    Args:
        capex_usd_per_kw: Capital expenditure, USD per kW installed.
        opex_fixed_pct_of_capex: Fixed O&M cost, as a fraction of total
            installed cost (e.g. 0.04 = 4% of CAPEX per year).
            Constrained to [0, 1].
        opex_variable_usd_per_kwh: Variable O&M cost, USD per kWh
            generated.
        capacity_factor: Dimensionless ratio of actual to nameplate
            generation, country-specific. Constrained to [0, 1].
        lifetime_years: Asset operational lifetime, in years. Must be
            positive.
        discount_rate_increment: Optional technology-specific risk
            premium added to the country's base discount_rate. May be
            None (pending_research) until a value is chosen. Left
            unconstrained on purpose: technology-specific risk premiums
            over a base discount rate vary widely across the literature
            (e.g. Steffen, B. (2020), "Estimating the cost of capital
            for renewable energy projects", Energy Economics) and no
            canonical range has been established for GeoFREA yet —
            adding a numeric bound now would be an arbitrary guess, not
            a documented decision. See DECISIONS.md 2026-08-20.
    """

    model_config = ConfigDict(extra="forbid")

    capex_usd_per_kw: VerifiedValue[float]
    opex_fixed_pct_of_capex: VerifiedValue[UnitInterval]
    opex_variable_usd_per_kwh: VerifiedValue[float]
    capacity_factor: VerifiedValue[UnitInterval]
    lifetime_years: VerifiedValue[PositiveInt]
    discount_rate_increment: VerifiedValue[float | None]


class TechnologyParams(BaseModel):
    """Per-technology parameters for a single country.

    Only "biomass" is populated in config/parameters.json today. Future
    technologies (solar, wind, ...) slot in here as additional fields
    once their parameters.json domains are actually populated — see
    docs/architecture/module-mapping.md for the legacy phases they'd
    correspond to. Not built speculatively ahead of that data existing.

    Args:
        biomass: Biomass technology parameters.
    """

    model_config = ConfigDict(extra="forbid")

    biomass: BiomassParams


class CountryParams(BaseModel):
    """Top-level parameters for a single country.

    Args:
        discount_rate: Country base discount rate (verification-
            wrapped). Currently a placeholder (verified=False) pending
            a country-specific source. Constrained to >= 0.
        technologies: Per-technology parameter sets for this country.
    """

    model_config = ConfigDict(extra="forbid")

    discount_rate: VerifiedValue[NonNegativeFloat]
    technologies: TechnologyParams


class ParametersFile(BaseModel):
    """Root schema for config/parameters.json.

    Args:
        countries: Mapping of ISO-3166-alpha-3 country code to that
            country's parameters. Currently PRT and BRA.
    """

    model_config = ConfigDict(extra="forbid")

    countries: dict[str, CountryParams]
