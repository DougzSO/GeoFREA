"""The three named land scenarios and the candidate-set stability table (U-06, M-F3-02, M-F3-04; Group 6, COMMAND 97).

`central` feeds F4-F7. Each scenario takes the value the specification gives it for every scenario-dependent parameter
(`config/experiments.yaml`, `land_availability`); a legal rule that is the same in the three scenarios (the Brazilian riparian classes)
carries the same steps in each. Categorical parameters (excluded land-cover classes, IUCN categories) have one nominal level in all three.
Nothing here carries a number.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import NamedTuple

import numpy as np
import pandas as pd

from geofrea.config_models.land_availability import (
    PROJECT_AREA,
    SCENARIOS,
    LandAvailability,
    LandAvailabilityError,
    ParameterSet,
    TechParameters,
)

LAND_SCENARIOS = ("central", "restrictive", "permissive")


class ScenarioComposition(NamedTuple):
    """What each scenario takes for the parameters that vary, and what is the same in all three (recorded in the F3 output and phase record)."""

    varied: dict[str, dict[str, float | None]]  # parameter -> {"central", "restrictive", "permissive"}
    held: dict[str, str]  # parameter -> why it is the same in the three scenarios


class LandScenarioError(RuntimeError):
    """The scenarios violate their ordering or are malformed (A-09, V-03)."""


def _project_area(
    project_area_km2: Mapping[str, float] | None, scenario: str, technology: str
) -> float:
    if project_area_km2 is None or scenario not in project_area_km2:
        raise LandAvailabilityError(
            f"{technology}/{scenario}: the minimum cluster is the area of the reference project (P_ref / PD), "
            "and no project area was given for this scenario"
        )
    return float(project_area_km2[scenario])


def _resolve(
    value, project_area_km2: Mapping[str, float] | None, scenario: str, technology: str
) -> float | None:
    if value == PROJECT_AREA:
        return _project_area(project_area_km2, scenario, technology)
    return None if value is None else float(value)


def scenario_composition(
    la: LandAvailability, technology: str, iso: str, project_area_km2: Mapping[str, float] | None = None
) -> ScenarioComposition:
    """The values of the parameters that differ between scenarios for one technology and country, and the ones that do not."""
    p: TechParameters = la.technologies[technology]
    varied: dict[str, dict[str, float | None]] = {
        "river_width_exponent": {s: la.riparian.width_exponent.value(s) for s in SCENARIOS},
        "slope_max_pct": {s: p.slope_max_pct.value(s) for s in SCENARIOS},
        "settlement_setback_m": {s: p.settlement_setback_m.value(s) for s in SCENARIOS},
        "min_cluster_km2": {
            s: _resolve(p.min_area.cluster_km2.value(s), project_area_km2, s, technology) for s in SCENARIOS
        },
        "min_pixel_fraction": {s: _resolve(p.min_area.pixel_fraction.value(s), None, s, technology) for s in SCENARIOS},
    }
    if p.elevation_max_m is not None:
        varied["elevation_max_m"] = {s: p.elevation_max_m.value(s) for s in SCENARIOS}
    riparian = la.riparian.countries.get(iso)
    held = {
        "excluded_classes": "categorical: one level in all scenarios",
        "iucn_categories": "categorical: one level in all scenarios",
        "settlement_mask": "the same classes in all scenarios; the scenarios vary the setback",
    }
    if riparian is not None:
        steps = {s: [(w.below_width_m, w.buffer_m) for w in getattr(riparian, s)] for s in SCENARIOS}
        if steps["restrictive"] == steps["central"] == steps["permissive"]:
            held["river_buffer"] = "the same in the three scenarios (a legal rule); the scenarios vary the width exponent"
    return ScenarioComposition(varied, held)


def _exponent_range(la: LandAvailability) -> tuple[float, float]:
    """The range of the width exponent over the scenarios: the permissive and restrictive values, whose extremes bound the channel width of a reach."""
    values = [float(la.riparian.width_exponent.value(s)) for s in SCENARIOS]
    return (min(values), max(values))


def scenario_set(
    la: LandAvailability,
    technology: str,
    iso: str,
    scenario: str,
    project_area_km2: Mapping[str, float] | None = None,
) -> ParameterSet:
    """The parameter set of one scenario of one technology in one country.

    Args:
        la: The land-eligibility configuration.
        technology: `solar` or `wind`.
        iso: Country code (picks the riparian buffer rule).
        scenario: `restrictive`, `central` or `permissive`.
        project_area_km2: The area of the reference project per scenario (`P_ref / PD`, from `parameters.json`), needed when the minimum cluster of
            `scenario` is the project area.

    Raises:
        LandAvailabilityError: no riparian rule for `iso`, or a missing project area.
    """
    p = la.technologies[technology]
    riparian = la.riparian.countries.get(iso)
    if riparian is None:
        raise LandAvailabilityError(
            f"land_availability.riparian.countries has no entry for {iso!r} (the buffer is a legal parameter of each country, never a default)"
        )
    elevation = None if p.elevation_max_m is None else p.elevation_max_m.value(scenario)
    return ParameterSet(
        slope_max_pct=float(p.slope_max_pct.value(scenario)),
        settlement_setback_m=float(p.settlement_setback_m.value(scenario)),
        river_width_coefficient=float(la.riparian.width_coefficient),
        river_width_exponent=float(la.riparian.width_exponent.value(scenario)),
        river_width_exponent_range=_exponent_range(la),
        river_buffer_steps=tuple((w.below_width_m, float(w.buffer_m)) for w in getattr(riparian, scenario)),
        excluded_classes=tuple(int(c) for c in p.excluded_classes.levels[p.excluded_classes.nominal]),
        iucn_categories=tuple(str(c).lower() for c in p.iucn_categories.levels[p.iucn_categories.nominal]),
        water_classes=tuple(int(c) for c in la.water_classes),
        min_cluster_km2=_resolve(p.min_area.cluster_km2.value(scenario), project_area_km2, scenario, technology),
        min_pixel_fraction=_resolve(p.min_area.pixel_fraction.value(scenario), None, scenario, technology),
        elevation_max_m=None if elevation is None else float(elevation),
        label=scenario,
    )


def scenario_sets(
    la: LandAvailability,
    technology: str,
    iso: str,
    project_area_km2: Mapping[str, float] | None = None,
) -> dict[str, ParameterSet]:
    """The `central`, `restrictive` and `permissive` parameter sets of one technology in one country (see `scenario_set`).

    Implements: M-F3-02, U-06.
    """
    return {s: scenario_set(la, technology, iso, s, project_area_km2) for s in LAND_SCENARIOS}

def sensitivity_set(la: LandAvailability, name: str, base: ParameterSet) -> ParameterSet:
    """The central set with the population-density threshold of the named sensitivity (`population_density_200`): defined, never part of a run."""
    if name not in la.sensitivities:
        raise LandAvailabilityError(f"no sensitivity {name!r} (have {sorted(la.sensitivities)})")
    return dataclasses.replace(base, pop_density_max_per_km2=la.sensitivities[name].pop_density_max_per_km2, label=name)


def check_scenario_order(
    technology: str,
    cells_by_scenario: dict[str, pd.DataFrame],
    tolerance_km2: float = 1e-6,
) -> None:
    """Eligible area per cell: restrictive <= central <= permissive (V-03 for the scenarios), within `tolerance_km2` (float noise only).

    Raises:
        LandScenarioError: a cell violates the order beyond the tolerance, or the scenarios do not hold the same cells as central.
    """
    area = {
        s: df.set_index("cell_id")["eligible_area_km2"].sort_index()
        for s, df in cells_by_scenario.items()
    }
    ref = area["central"].index
    for scenario, series in area.items():
        if not series.index.equals(ref):
            raise LandScenarioError(
                f"{technology}: scenario {scenario!r} does not hold the same cells as central"
            )
    tolerance = tolerance_km2
    low, mid, high = area["restrictive"], area["central"], area["permissive"]
    bad = ((low > mid + tolerance) | (mid > high + tolerance)).sum()
    if bad:
        raise LandScenarioError(
            f"{technology}: {int(bad)} cells violate restrictive <= central <= permissive eligible area"
        )


REASON_MISSING_ELEVATION = "missing_elevation"
REASON_ELEVATION_MAX = "elevation_max"


def candidate_exclusion_reasons(
    eligible_area_km2: pd.Series,
    elevation_m: pd.Series,
    elevation_max_m: float | None,
) -> pd.Series:
    """Why a cell with eligible area is not a candidate (M-F3-04, OQ-060); None for a candidate and for a cell with no eligible area.

    `missing_elevation`: the cell has no elevation (no eligible pixel has a DEM value), for every technology; `elevation_max`: the cell has
    an elevation above the limit of the technology in that scenario. The altitude limit is evaluated only on cells that have an elevation.
    A cell is a candidate if it has any eligible area: the minimum project size is applied to the pixels (clusters), not to the cell.
    """
    reason = pd.Series(
        np.full(len(eligible_area_km2), None, dtype=object), index=eligible_area_km2.index
    )
    enough = eligible_area_km2 > 0
    missing = elevation_m.isna()
    reason[enough & missing] = REASON_MISSING_ELEVATION
    if elevation_max_m is not None:
        reason[enough & ~missing & (elevation_m > elevation_max_m)] = REASON_ELEVATION_MAX
    return reason


def candidate_stability(
    cells_by_scenario: dict[str, pd.DataFrame],
    elevation_max_m_by_scenario: Mapping[str, float | None] | None = None,
) -> pd.DataFrame:
    """Per cell that is a candidate in at least one scenario: eligible area per scenario and how often it is a candidate.

    Columns: `cell_id`, `area_km2_<scenario>`, `candidate_<scenario>` (bool), `n_scenarios` (scenarios in which the cell is a
    candidate), `share_of_scenarios` (`n_scenarios` over the number of scenarios; V1 stability of the candidate set). A cell with no
    elevation, or above the altitude limit of that scenario, is not a candidate in it (OQ-058, OQ-060).
    """
    scenarios = list(cells_by_scenario)
    limits = elevation_max_m_by_scenario or {}
    table = None
    for scenario, df in cells_by_scenario.items():
        part = df[["cell_id", "eligible_area_km2"]].rename(
            columns={"eligible_area_km2": f"area_km2_{scenario}"}
        )
        if "elevation_m" in df.columns:
            elevation = df["elevation_m"].to_numpy()
            out = np.isnan(elevation)
            limit = limits.get(scenario)
            if limit is not None:
                out = out | (elevation > limit)
            part.loc[out, f"area_km2_{scenario}"] = 0.0
        table = part if table is None else table.merge(part, on="cell_id", how="outer")
    assert table is not None
    for scenario in scenarios:
        table[f"candidate_{scenario}"] = table[f"area_km2_{scenario}"].fillna(0.0) > 0
    flags = [f"candidate_{s}" for s in scenarios]
    table["n_scenarios"] = table[flags].sum(axis=1).astype("int64")
    table["share_of_scenarios"] = table["n_scenarios"] / len(scenarios)
    return table[table["n_scenarios"] > 0].sort_values("cell_id").reset_index(drop=True)
