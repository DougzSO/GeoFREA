"""Land-availability parameters for E1-E6 and the candidate filter, as ranges (M-F2b-01, M-F3-04; Douglas, 2026-10-07).

Every continuous parameter is declared as `nominal` plus an optional `low`-`high` range with its source; a parameter whose range
is not sourced yet has `low` and `high` null and is held at `nominal` (declared, never filled in). Categorical parameters
(excluded land-cover classes, IUCN categories) are declared as named `levels` with one `nominal` level. `nominal_set()` resolves
the central values that feed F4-F7; `ParameterSet` is one concrete choice, so a sampler can later draw many of them and the
eligibility engine stays a pure function of one set.

The values live in `config/experiments.yaml` under `land_availability`; nothing here carries a number.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, model_validator


class LandAvailabilityError(ValueError):
    """The land-availability configuration is missing, incomplete or inconsistent (A-09: fail loud)."""


class Ranged(BaseModel):
    """A continuous parameter: central value, optional sourced range, provenance."""

    model_config = ConfigDict(extra="forbid")

    nominal: float
    low: float | None = None
    high: float | None = None
    unit: str
    source: str
    status: str  # "sourced" | "unverified" | "range_pending"
    note: str | None = None

    @model_validator(mode="after")
    def _check(self) -> Ranged:
        if (self.low is None) != (self.high is None):
            raise ValueError("low and high must be given together or both left null")
        if self.low is not None and not (self.low <= self.nominal <= self.high):
            raise ValueError(f"nominal {self.nominal} lies outside [{self.low}, {self.high}]")
        return self

    @property
    def has_range(self) -> bool:
        return self.low is not None


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


class TechParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slope_max_deg: Ranged
    pop_density_max_per_km2: Ranged
    riparian_setback_km: Ranged
    riparian_min_discharge_m3s: Ranged
    min_eligible_area_km2: Ranged
    excluded_classes: Levels
    iucn_categories: Levels


class LandAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # discharge thresholds (m3/s) at which the riparian shares are computed; a draw between them is interpolated
    riparian_discharge_grid_m3s: list[float]
    technologies: dict[str, TechParameters]

    @model_validator(mode="after")
    def _grid_covers_ranges(self) -> LandAvailability:
        grid = sorted(self.riparian_discharge_grid_m3s)
        for tech, p in self.technologies.items():
            q = p.riparian_min_discharge_m3s
            lo, hi = (q.low, q.high) if q.has_range else (q.nominal, q.nominal)
            if lo < grid[0] or hi > grid[-1]:
                raise ValueError(f"{tech}: discharge range [{lo}, {hi}] is outside the grid {grid}")
        return self


@dataclass(frozen=True)
class ParameterSet:
    """One concrete choice of every land-availability parameter for one technology."""

    slope_max_deg: float
    pop_density_max_per_km2: float
    riparian_setback_km: float
    min_eligible_area_km2: float
    excluded_classes: tuple[int, ...]
    iucn_categories: tuple[str, ...]
    riparian_min_discharge_m3s: float = 0.0
    label: str = "nominal"


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


def nominal_set(params: TechParameters) -> ParameterSet:
    """The central parameter set (feeds F4-F7)."""
    return ParameterSet(
        slope_max_deg=params.slope_max_deg.nominal,
        pop_density_max_per_km2=params.pop_density_max_per_km2.nominal,
        riparian_setback_km=params.riparian_setback_km.nominal,
        riparian_min_discharge_m3s=params.riparian_min_discharge_m3s.nominal,
        min_eligible_area_km2=params.min_eligible_area_km2.nominal,
        excluded_classes=tuple(int(c) for c in params.excluded_classes.levels[params.excluded_classes.nominal]),
        iucn_categories=tuple(str(c).lower() for c in params.iucn_categories.levels[params.iucn_categories.nominal]),
        label="nominal",
    )


def riparian_thresholds_km(params: TechParameters) -> list[float]:
    """Setbacks the riparian fraction must be computed for: the nominal value and both ends of its range."""
    r = params.riparian_setback_km
    values = {r.nominal} | ({r.low, r.high} if r.has_range else set())
    return sorted(values)


def riparian_discharges_m3s(la: LandAvailability) -> list[float]:
    """Discharge thresholds the riparian fraction must be computed for: the configured grid plus every nominal and range end."""
    values = set(la.riparian_discharge_grid_m3s)
    for p in la.technologies.values():
        q = p.riparian_min_discharge_m3s
        values |= {q.nominal} | ({q.low, q.high} if q.has_range else set())
    return sorted(values)
