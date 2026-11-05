"""The Group 6 values of `config/experiments.yaml` against `docs/thesis/methods/group6_land_eligibility.tex` (COMMAND 97).

Every value of the specification tables is checked per country, technology and scenario, together with the rule that no value is without a source or a tier,
that the scenarios differ wherever the specification says they differ and that the area of the reference project is read from `parameters.json`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from geofrea.config_models.land_availability import PROJECT_AREA, SCENARIOS, load_land_availability
from geofrea.core.config_loader import load_parameters
from geofrea.land_eligibility.eligibility import corridor_key
from geofrea.land_eligibility.fractions import buffer_m, corridor_half_widths_m, river_widths_m
from geofrea.land_eligibility.scenarios import (
    LandScenarioError,
    check_scenario_order,
    scenario_composition,
    scenario_set,
    scenario_sets,
    sensitivity_set,
)

ROOT = Path(__file__).resolve().parents[2]
LA = load_land_availability(ROOT / "config" / "experiments.yaml")
PROJECT = {tech: {s: 100.0 / pd_ for s, pd_ in values.items()} for tech, values in {"solar": {"restrictive": 45.0, "central": 50.0, "permissive": 75.0}, "wind": {"restrictive": 3.32, "central": 4.99, "permissive": 7.12}}.items()}


def _steps(country: str, scenario: str):
    return [(w.below_width_m, w.buffer_m) for w in getattr(LA.riparian.countries[country], scenario)]


def test_the_width_relation_and_its_exponents_are_those_of_the_specification():
    assert LA.riparian.width_coefficient == 7.2
    assert [LA.riparian.width_exponent.value(s) for s in ("permissive", "central", "restrictive")] == [0.48, 0.50, 0.52]
    assert LA.riparian.discharge_column == "DIS_AV_CMS"
    assert LA.water_classes == [80]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_the_brazilian_buffer_is_the_forest_code_in_the_three_scenarios(scenario):
    steps = _steps("BRA", scenario)
    assert steps == [(10.0, 30.0), (50.0, 50.0), (200.0, 100.0), (600.0, 200.0), (None, 500.0)]
    for width, expected in ((9.99, 30.0), (10.0, 50.0), (49.99, 50.0), (50.0, 100.0), (199.9, 100.0), (200.0, 200.0), (599.9, 200.0), (600.0, 500.0), (5000.0, 500.0)):
        assert float(buffer_m(steps, width)) == expected


def test_the_portuguese_buffer_is_10_m_permissive_30_m_restrictive_and_a_navigability_proxy_in_the_central_scenario():
    assert _steps("PRT", "permissive") == [(None, 10.0)]
    assert _steps("PRT", "restrictive") == [(None, 30.0)]
    assert _steps("PRT", "central") == [(10.0, 10.0), (None, 30.0)]
    assert LA.riparian.countries["PRT"].tier == 3  # the central proxy is Tier 3


def test_the_indian_buffer_is_author_judgment_30_100_200_m():
    assert [_steps("IND", s) for s in ("permissive", "central", "restrictive")] == [[(None, 30.0)], [(None, 100.0)], [(None, 200.0)]]
    assert LA.riparian.countries["IND"].tier == 3 and LA.riparian.countries["IND"].source is None


@pytest.mark.parametrize(
    ("tech", "slope", "setback", "pixel", "cluster", "elevation"),
    [
        ("solar", (3.0, 5.0, 10.0), (1000.0, 500.0, 0.0), (None, None, None), ("project_area", 1.0, None), None),
        ("wind", (10.0, 20.0, 30.0), (1000.0, 800.0, 500.0), (0.10, 0.10, None), ("project_area", None, None), (2000.0, 3000.0, None)),
    ],
)
def test_slope_setback_minimum_area_and_elevation_follow_the_specification(tech, slope, setback, pixel, cluster, elevation):
    p = LA.technologies[tech]
    assert (p.slope_max_pct.restrictive, p.slope_max_pct.central, p.slope_max_pct.permissive) == slope
    assert (p.settlement_setback_m.restrictive, p.settlement_setback_m.central, p.settlement_setback_m.permissive) == setback
    assert (p.min_area.pixel_fraction.restrictive, p.min_area.pixel_fraction.central, p.min_area.pixel_fraction.permissive) == pixel
    assert (p.min_area.cluster_km2.restrictive, p.min_area.cluster_km2.central, p.min_area.cluster_km2.permissive) == cluster
    if elevation is None:
        assert p.elevation_max_m is None  # elevation limits apply only to wind
    else:
        assert (p.elevation_max_m.restrictive, p.elevation_max_m.central, p.elevation_max_m.permissive) == elevation
    assert p.settlement_setback_m.unit == "m" and p.slope_max_pct.unit == "%"


def test_the_settlement_mask_is_rural_cluster_and_denser_and_the_density_stays_a_named_sensitivity_that_is_not_run():
    assert LA.settlements.min_class == 13
    sensitivity = LA.sensitivities["population_density_200"]
    assert sensitivity.pop_density_max_per_km2 == 200.0 and sensitivity.run is False and sensitivity.status == "verify"
    for country in ("BRA", "PRT", "IND"):
        for tech in ("solar", "wind"):
            for scenario, params in scenario_sets(LA, tech, country, PROJECT[tech]).items():
                assert params.pop_density_max_per_km2 is None, (country, tech, scenario)  # no scenario carries the density threshold
    central = scenario_set(LA, "solar", "BRA", "central", PROJECT["solar"])
    assert sensitivity_set(LA, "population_density_200", central).pop_density_max_per_km2 == 200.0


@pytest.mark.parametrize("country", ["BRA", "PRT", "IND"])
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_the_three_scenarios_differ_in_every_parameter_the_specification_says_differs(country, tech):
    sets = scenario_sets(LA, tech, country, PROJECT[tech])
    assert set(sets) == set(SCENARIOS)
    assert len({sets[s].river_width_exponent for s in SCENARIOS}) == 3
    assert len({sets[s].slope_max_pct for s in SCENARIOS}) == 3
    assert len({sets[s].min_cluster_km2 for s in SCENARIOS}) == (3 if tech == "solar" else 2)  # wind: none, none, P_ref/PD
    if tech == "wind":
        assert len({sets[s].settlement_setback_m for s in SCENARIOS}) == 3
        assert len({sets[s].elevation_max_m for s in SCENARIOS}) == 3
    buffers = {s: tuple(sets[s].river_buffer_steps) for s in SCENARIOS}
    assert (len(set(buffers.values())) == 1) == (country == "BRA")  # the Brazilian rule is the same in the three scenarios, the others differ
    composition = scenario_composition(LA, tech, country, PROJECT[tech])
    assert ("river_buffer" in composition.held) == (country == "BRA")


def test_the_minimum_cluster_of_the_restrictive_scenario_is_the_area_of_the_reference_project_read_from_parameters_json():
    parameters = load_parameters(ROOT / "config" / "parameters.json")
    for country in ("BRA", "PRT", "IND"):
        entry = parameters.countries[country]
        p_ref = entry.connection.reference_project_mw.value
        for tech in ("solar", "wind"):
            pd_ = getattr(entry.technologies, tech).power_density_mw_per_km2.scenario_values
            area = {s: p_ref / pd_.for_scenario(s) for s in SCENARIOS}
            restrictive = scenario_set(LA, tech, country, "restrictive", {"restrictive": area["restrictive"]})
            assert restrictive.min_cluster_km2 == pytest.approx(area["restrictive"])
    assert LA.technologies["solar"].min_area.cluster_km2.restrictive == PROJECT_AREA
    with pytest.raises(Exception, match="reference project"):
        scenario_set(LA, "solar", "BRA", "restrictive")  # no project area given: an error, never a default


def test_every_value_has_a_source_or_is_declared_tier_3_and_what_the_tex_marks_verify_is_status_verify():
    values = [LA.riparian.width_exponent, LA.technologies["solar"].slope_max_pct, LA.technologies["wind"].slope_max_pct]
    for tech in ("solar", "wind"):
        p = LA.technologies[tech]
        values += [p.settlement_setback_m, p.min_area.cluster_km2, p.min_area.pixel_fraction]
    values.append(LA.technologies["wind"].elevation_max_m)
    for v in values:
        assert v.unit and (v.source is not None or v.tier == 3), v
        assert v.status in {"sourced", "verify", "author_judgment", "not_applicable"}
    for country, rule in LA.riparian.countries.items():
        assert rule.source is not None or rule.tier == 3, country
    assert LA.technologies["wind"].elevation_max_m.status == "verify" and LA.sensitivities["population_density_200"].status == "verify"
    assert LA.settlements.source and "schiavina2023smod" in LA.settlements.source


def test_the_scenario_order_check_has_no_tolerance_beyond_float_noise():
    def cells(area):
        return pd.DataFrame({"cell_id": [1, 2], "eligible_area_km2": area, "cell_area_km2": [24.0, 24.0]})

    ok = {"restrictive": cells([10.0, 12.0]), "central": cells([11.0, 12.0]), "permissive": cells([11.0, 13.0])}
    check_scenario_order("wind", ok)
    noise = {"restrictive": cells([10.0, 12.0]), "central": cells([11.0, 12.0]), "permissive": cells([11.0 - 1e-9, 13.0])}
    check_scenario_order("wind", noise)
    bad = {"restrictive": cells([10.0, 12.0]), "central": cells([11.0, 12.0]), "permissive": cells([11.0 - 0.02, 13.0])}  # 0.08 % of the cell
    with pytest.raises(LandScenarioError, match="1 cells"):
        check_scenario_order("wind", bad)


def test_the_channel_widths_of_the_scenarios_are_nested_on_every_reach_for_discharges_below_and_above_one():
    """Q^b falls as b grows below 1 m3/s and rises above it; the width at the extreme of the exponent range nests the corridors on both sides."""
    q = np.array([0.1, 0.5, 0.99, 1.0, 1.01, 5.0, 48.2, 771.6, 6944.0, 50000.0])
    width = {s: river_widths_m(q, 7.2, LA.riparian.width_exponent.value(s), (0.48, 0.52)) for s in SCENARIOS}
    assert (width["permissive"] <= width["central"]).all() and (width["central"] <= width["restrictive"]).all()
    np.testing.assert_allclose(width["permissive"], 7.2 * np.minimum(q**0.48, q**0.52))
    np.testing.assert_allclose(width["restrictive"], 7.2 * np.maximum(q**0.48, q**0.52))
    np.testing.assert_allclose(width["central"], 7.2 * q**0.50)
    below, above = q < 1.0, q > 1.0
    assert (width["permissive"][below] < width["central"][below]).all()  # the exponent alone would have put the permissive channel above the central one
    assert (width["permissive"][above] < width["central"][above]).all() and (width["central"][above] < width["restrictive"][above]).all()
    for country in ("BRA", "PRT", "IND"):
        half = {s: corridor_half_widths_m(q, 7.2, LA.riparian.width_exponent.value(s), _steps(country, s), (0.48, 0.52)) for s in SCENARIOS}
        assert (half["permissive"] <= half["central"]).all() and (half["central"] <= half["restrictive"]).all()


def test_the_scenario_sets_carry_the_exponent_range_and_their_corridor_keys_differ():
    sets = scenario_sets(LA, "wind", "BRA", PROJECT["wind"])
    assert {s.river_width_exponent_range for s in sets.values()} == {(0.48, 0.52)}
    assert len({corridor_key(s) for s in sets.values()}) == 3
