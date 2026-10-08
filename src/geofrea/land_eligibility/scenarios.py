"""The three named land-availability scenarios and the candidate-set stability table (U-06, M-F3-02, M-F3-04; V1, V2).

`central` uses every nominal value and feeds F4-F7. `restrictive` takes every continuous parameter whose range has status
`sourced` at its restrictive end, `permissive` at its permissive end. A parameter without a sourced range (status other than
`sourced`, or no range at all) and every categorical parameter stays central in all three scenarios and is listed as held; it joins
the scenarios when a source is recorded. The values live in `config/experiments.yaml`; nothing here carries a number.
"""

from __future__ import annotations

import dataclasses
from typing import NamedTuple

import pandas as pd

from geofrea.land_eligibility.parameters import ParameterSet, Ranged, TechParameters, nominal_set

LAND_SCENARIOS = ("central", "restrictive", "permissive")

# continuous parameters that can move between scenarios -> True when a HIGHER value is the permissive end
_PERMISSIVE_IS_HIGH = {
    "slope_max_deg": True,
    "pop_density_max_per_km2": True,
    "riparian_setback_km": False,
    "riparian_min_discharge_m3s": True,
}
SOURCED = "sourced"


class ScenarioComposition(NamedTuple):
    """What each scenario varies and what it holds at the central value (recorded in the F3 output and phase record)."""

    varied: dict[str, dict[str, float]]  # parameter -> {"central", "restrictive", "permissive"}
    held: dict[str, str]  # parameter -> why it stays central


class LandScenarioError(RuntimeError):
    """The scenarios violate their ordering or are malformed (A-09, V-03)."""


def scenario_composition(params: TechParameters) -> ScenarioComposition:
    """Which parameters vary across the three scenarios of one technology, and which are held central, with the reason."""
    varied: dict[str, dict[str, float]] = {}
    held: dict[str, str] = {}
    for name, permissive_high in _PERMISSIVE_IS_HIGH.items():
        ranged: Ranged = getattr(params, name)
        if ranged.has_range and ranged.status == SOURCED:
            restrictive, permissive = (
                (ranged.low, ranged.high) if permissive_high else (ranged.high, ranged.low)
            )
            varied[name] = {
                "central": ranged.nominal,
                "restrictive": restrictive,
                "permissive": permissive,
            }
        elif ranged.has_range:
            held[name] = f"range not sourced (status {ranged.status})"
        else:
            held[name] = "no range"
    held["min_eligible_area_km2"] = (
        "no range" if not params.min_eligible_area_km2.has_range else "range not used"
    )
    held["excluded_classes"] = "categorical: one central level"
    held["iucn_categories"] = "categorical: one central level"
    return ScenarioComposition(varied, held)


def scenario_sets(params: TechParameters) -> dict[str, ParameterSet]:
    """The `central`, `restrictive` and `permissive` parameter sets of one technology (V2)."""
    central = nominal_set(params)
    composition = scenario_composition(params)
    sets = {"central": dataclasses.replace(central, label="central")}
    for scenario in ("restrictive", "permissive"):
        values = {name: v[scenario] for name, v in composition.varied.items()}
        sets[scenario] = dataclasses.replace(central, label=scenario, **values)
    return sets


def check_scenario_order(
    technology: str, cells_by_scenario: dict[str, pd.DataFrame], tolerance_km2: float = 1e-6
) -> None:
    """Eligible area per cell: restrictive <= central <= permissive (V-03 for the scenarios).

    Raises:
        LandScenarioError: a cell violates the order, or the scenarios do not hold the same cells.
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
    low, mid, high = area["restrictive"], area["central"], area["permissive"]
    bad = ((low > mid + tolerance_km2) | (mid > high + tolerance_km2)).sum()
    if bad:
        raise LandScenarioError(
            f"{technology}: {int(bad)} cells violate restrictive <= central <= permissive eligible area"
        )


def candidate_stability(
    cells_by_scenario: dict[str, pd.DataFrame], min_eligible_area_km2: float
) -> pd.DataFrame:
    """Per cell that is a candidate in at least one scenario: eligible area per scenario and how often it is a candidate.

    Columns: `cell_id`, `area_km2_<scenario>`, `candidate_<scenario>` (bool), `n_scenarios` (scenarios in which the cell is a
    candidate), `share_of_scenarios` (`n_scenarios` over the number of scenarios; V1 stability of the candidate set).
    """
    scenarios = list(cells_by_scenario)
    table = None
    for scenario, df in cells_by_scenario.items():
        part = df[["cell_id", "eligible_area_km2"]].rename(
            columns={"eligible_area_km2": f"area_km2_{scenario}"}
        )
        table = part if table is None else table.merge(part, on="cell_id", how="outer")
    assert table is not None
    for scenario in scenarios:
        table[f"candidate_{scenario}"] = (
            table[f"area_km2_{scenario}"].fillna(0.0) >= min_eligible_area_km2
        )
    flags = [f"candidate_{s}" for s in scenarios]
    table["n_scenarios"] = table[flags].sum(axis=1).astype("int64")
    table["share_of_scenarios"] = table["n_scenarios"] / len(scenarios)
    return table[table["n_scenarios"] > 0].sort_values("cell_id").reset_index(drop=True)
