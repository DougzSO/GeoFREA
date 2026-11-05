"""Land-eligibility parameters of Stage F3 (Group 6, COMMAND 97; M-F2b-01, M-F3-02, M-F3-04).

Every scenario-dependent parameter is declared with its three values (`restrictive`, `central`, `permissive`), its unit, source, tier and status, as in
`docs/thesis/methods/group6_land_eligibility.tex`. A value that is null means "no such limit" in that scenario. A parameter that the specification marks
`% verify` has `status: verify`. Categorical parameters (excluded land-cover classes, IUCN categories) are named `levels` with one nominal level.
`ParameterSet` is one concrete choice for one technology and one country; the eligibility engine is a pure function of it.

The values live in `config/experiments.yaml` under `land_availability`; nothing here carries a number.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

ELEVATION_COLUMN = "elevation_m"  # eligible-area-weighted mean of the aligned DEM, a column of the F3 cell tables (OQ-058)
SCENARIOS = ("restrictive", "central", "permissive")
PROJECT_AREA = "project_area"  # a minimum cluster of P_ref / PD: the area of the reference project (Group 3 and Group 1 parameters)


class LandAvailabilityError(ValueError):
    """The land-eligibility configuration is missing, incomplete or inconsistent (A-09: fail loud)."""


class ScenarioValue(BaseModel):
    """A parameter with one value per land scenario; null is "no limit"."""

    model_config = ConfigDict(extra="forbid")

    restrictive: float | Literal["project_area"] | None
    central: float | Literal["project_area"] | None
    permissive: float | Literal["project_area"] | None
    unit: str
    source: str | None = None
    tier: Literal[1, 2, 3] | None = None
    status: str  # "sourced" | "verify" | "author_judgment"
    note: str | None = None
    sensitivity: float | None = None  # a value reported beside the scenarios, never a scenario (OQ-058)

    @model_validator(mode="after")
    def _unsourced_values_are_declared(self) -> ScenarioValue:
        has_value = any(v is not None for v in (self.restrictive, self.central, self.permissive))
        if has_value and self.source is None and self.tier != 3:
            raise ValueError("a value without a source must be declared Tier 3")
        if self.status == "sourced" and self.source is None:
            raise ValueError("a value without a source cannot have status sourced")
        return self

    def value(self, scenario: str) -> float | str | None:
        return getattr(self, scenario)


class WidthBuffer(BaseModel):
    """One step of a riparian buffer rule: reaches narrower than `below_width_m` (null: every wider reach) get `buffer_m` beyond the channel edge."""

    model_config = ConfigDict(extra="forbid")

    below_width_m: float | None
    buffer_m: float


class CountryRiparian(BaseModel):
    """The riparian buffer B_c of one country in each scenario, as steps over the estimated channel width W (m)."""

    model_config = ConfigDict(extra="forbid")

    restrictive: list[WidthBuffer]
    central: list[WidthBuffer]
    permissive: list[WidthBuffer]
    source: str | None = None
    tier: Literal[1, 2, 3] | None = None
    status: str
    note: str | None = None
    synthetic: bool = False

    @model_validator(mode="after")
    def _steps_are_ordered(self) -> CountryRiparian:
        for scenario in SCENARIOS:
            steps = getattr(self, scenario)
            if not steps or steps[-1].below_width_m is not None:
                raise ValueError(f"{scenario}: the last step must have below_width_m null (every wider reach)")
            widths = [s.below_width_m for s in steps[:-1]]
            if any(w is None for w in widths) or widths != sorted(widths):
                raise ValueError(f"{scenario}: below_width_m must increase and only the last step may be null")
        return self

class Riparian(BaseModel):
    """Rivers (E3): channel width from the long-term mean discharge and the buffer of each country (Group 6, `eq:g6_width`)."""

    model_config = ConfigDict(extra="forbid")

    width_coefficient: float  # a of W = a Q^b
    width_exponent: ScenarioValue  # b per scenario
    discharge_column: str = "DIS_AV_CMS"
    countries: dict[str, CountryRiparian]
    source: str
    note: str | None = None


class Settlements(BaseModel):
    """The settlement mask (E6): GHS-SMOD classes at or above `min_class` (rural cluster and denser), at 1 km."""

    model_config = ConfigDict(extra="forbid")

    min_class: int
    source: str
    note: str | None = None


class Sensitivity(BaseModel):
    """A named sensitivity that is defined and kept, but not run (`run: false`)."""

    model_config = ConfigDict(extra="forbid")

    pop_density_max_per_km2: float
    run: bool = False
    unit: str
    source: str | None = None
    tier: Literal[1, 2, 3] | None = None
    status: str
    note: str | None = None


class Levels(BaseModel):
    """A categorical parameter: named alternatives, one of which is nominal."""

    model_config = ConfigDict(extra="forbid")

    nominal: str
    levels: dict[str, list[int] | list[str]]
    source: str
    status: str
    note: str | None = None

    @model_validator(mode="after")
    def _check(self) -> Levels:
        if self.nominal not in self.levels:
            raise ValueError(f"nominal level {self.nominal!r} is not among {sorted(self.levels)}")
        return self


class MinArea(BaseModel):
    """The minimum eligible area of a technology: of a cluster of 8-connected pixels and of one pixel (`subsec:g6_minarea`)."""

    model_config = ConfigDict(extra="forbid")

    cluster_km2: ScenarioValue
    pixel_fraction: ScenarioValue


class TechParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slope_max_pct: ScenarioValue
    settlement_setback_m: ScenarioValue
    min_area: MinArea
    elevation_max_m: ScenarioValue | None = None
    excluded_classes: Levels
    iucn_categories: Levels


class LandAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # a cell with no elevation is not a candidate (OQ-060); the only rule, written in the configuration so that it is explicit and fingerprinted
    missing_elevation: Literal["ineligible"] = "ineligible"
    water_classes: list[int]  # land-cover classes whose share the river corridor is merged with (union, not sum; C1 of docs/_audit/group6_audit_97.md)
    riparian: Riparian
    settlements: Settlements
    sensitivities: dict[str, Sensitivity] = {}
    technologies: dict[str, TechParameters]


@dataclass(frozen=True)
class ParameterSet:
    """One concrete choice of every land-eligibility parameter for one technology in one country and one scenario."""

    slope_max_pct: float
    settlement_setback_m: float
    river_width_coefficient: float
    river_width_exponent: float
    river_buffer_steps: tuple[tuple[float | None, float], ...]  # (below_width_m or None, buffer_m)
    excluded_classes: tuple[int, ...]
    iucn_categories: tuple[str, ...]
    river_width_exponent_range: tuple[float, float] | None = None  # (b_low, b_high) of the scenarios: the width is taken at the extreme of the range
    water_classes: tuple[int, ...] = ()
    min_cluster_km2: float | None = None  # a cluster of eligible pixels below this eligible area is dropped; None: no minimum
    min_pixel_fraction: float | None = None  # a pixel with a smaller eligible fraction is dropped; None: no minimum
    elevation_max_m: float | None = None
    pop_density_max_per_km2: float | None = None  # only the named sensitivity `population_density_200` sets it; no scenario does
    label: str = "central"

    @property
    def slope_max_deg(self) -> float:
        """The slope maximum in degrees: a percent slope is a tangent, `atan(p / 100)`."""
        import math

        return math.degrees(math.atan(self.slope_max_pct / 100.0))


def load_land_availability(experiments_yaml: Path) -> LandAvailability:
    """Read `land_availability` from experiments.yaml; fail loud if it is absent or malformed."""
    raw = yaml.safe_load(Path(experiments_yaml).read_text(encoding="utf-8")) or {}
    block = raw.get("land_availability")
    if not block:
        raise LandAvailabilityError(f"{experiments_yaml}: no `land_availability` block")
    try:
        return LandAvailability.model_validate(block)
    except ValueError as exc:
        raise LandAvailabilityError(f"{experiments_yaml}: invalid `land_availability`: {exc}") from exc


def default_experiments_yaml() -> Path:
    """`config/experiments.yaml` of this repository (for consumers outside F3 that need the land-eligibility parameters)."""
    return Path(__file__).resolve().parents[3] / "config" / "experiments.yaml"


def strictest_slope_max_deg(la: LandAvailability, technology: str) -> float:
    """The lowest slope maximum (degrees) any scenario of the technology uses.

    Used by the audit to ask whether the slope exclusion could bite at all: if even the strictest maximum is above every observed slope,
    the exclusion is inactive for any scenario.
    """
    import math

    q = la.technologies[technology].slope_max_pct
    return math.degrees(math.atan(min(float(v) for v in (q.restrictive, q.central, q.permissive) if v is not None) / 100.0))


def elevation_sensitivity_m(la: LandAvailability, technology: str) -> float | None:
    """The altitude (m) above which F5 to F8 report the sensitivity without the cells, or None when the technology has none (OQ-058)."""
    cap = la.technologies[technology].elevation_max_m
    return cap.sensitivity if cap else None


def elevation_role(elevation_m: float) -> str:
    """The F7 window role of the core-window run without the candidates above `elevation_m` (OQ-058), for example `core_below_3000m`."""
    return f"core_below_{elevation_m:.0f}m"
