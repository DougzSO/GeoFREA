"""The parameter keys F6 reads (M-F6-01, D-F6-009, D-F6-014, D-F6-016): names, units, pending entries and the synthetic block."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from geofrea.core.config_schemas import TechnologiesFile
from geofrea.core.production import GROUP3_KERNEL_KEYS
from geofrea.core.schemas import ParametersFile

REPO = Path(__file__).resolve().parents[2]
REAL_COUNTRIES = ("BRA", "PRT", "IND")
GROUP3_UNIT_COSTS = ("line_cost_per_km", "bay_cost", "road_cost_per_km")
OLD_COST_NAMES = ("grid_cost_usd_per_mw_km", "substation_cost_usd_per_mw")
COST_KEYS = (
    "capex_usd_per_kw",
    "opex_var_usd_per_mwh",
)


@pytest.fixture(scope="module")
def parameters() -> ParametersFile:
    raw = json.loads((REPO / "config" / "parameters.json").read_text(encoding="utf-8"))
    return ParametersFile.model_validate(raw)


@pytest.fixture(scope="module")
def technologies() -> TechnologiesFile:
    raw = yaml.safe_load((REPO / "config" / "technologies.yaml").read_text(encoding="utf-8"))
    return TechnologiesFile.model_validate({"technologies": raw})


def _entries(parameters: ParametersFile, countries):
    for iso in countries:
        for tech in ("solar", "wind"):
            yield iso, tech, getattr(parameters.countries[iso].technologies, tech)


@pytest.mark.unit
def test_variable_om_name_and_unit_agree_and_the_old_name_is_gone(parameters):
    """A name that says kWh with a unit that says MWh invites a factor-1000 error (D9): the key says MWh and so does the unit."""
    for iso, tech, params in _entries(parameters, parameters.countries):
        assert params.opex_var_usd_per_mwh.unit == "USD/MWh", f"{iso} {tech}"
    text = (REPO / "config" / "parameters.json").read_text(encoding="utf-8")
    assert "opex_variable_usd_per_kwh" not in text


@pytest.mark.unit
def test_real_countries_carry_the_group3_blocks_and_the_old_names_are_gone(parameters):
    text = (REPO / "config" / "parameters.json").read_text(encoding="utf-8")
    for old in OLD_COST_NAMES:
        assert old not in text  # renamed, not reused: the unit changed from per MW and km to per project
    for iso in REAL_COUNTRIES:
        country = parameters.countries[iso]
        assert country.connection is not None, iso
        for name in GROUP3_UNIT_COSTS:
            cost = getattr(country.connection, name)
            assert not cost.synthetic
            # a cost has either a value with its range or the status to_be_sourced with none of them
            assert (cost.value is None) == (cost.status == "to_be_sourced"), f"{iso} {name}"
            if cost.value is None:
                assert cost.open_question == "OQ-001", f"{iso} {name}"
        for tech in ("solar", "wind"):
            assert getattr(country.technologies, tech).opex_var_usd_per_mwh.value == 0.0  # Group 2 (M-F6-07)
    # the values of the Group 3 table that have a source, and only those
    assert parameters.countries["IND"].connection.line_cost_per_km.value == 1.10
    assert parameters.countries["PRT"].connection.line_cost_per_km.value == 0.362
    assert parameters.countries["PRT"].connection.bay_cost.value == 2.789
    for name in ("line_cost_per_km", "bay_cost"):  # ACER 2023 report, p. 17: "2023 as the base year" (COMMAND 85, OQ-066 closed)
        assert getattr(parameters.countries["PRT"].connection, name).price_year == 2023
        assert getattr(parameters.countries["PRT"].connection, name).status == "sourced"
    # BRA bay: ANEEL BPR module Entrada de Linha 138 kV, arrangement BPT, with the other arrangements as the range
    bay = parameters.countries["BRA"].connection.bay_cost
    assert (bay.currency, bay.price_year, bay.status) == ("BRL", 2017, "verify")
    assert bay.low < bay.value < bay.high
    # COMMAND 86: the BRA line (median of seven ANEEL modular costs, deflated to 2024), the IND bay (a proxy) and the road (excluded)
    line = parameters.countries["BRA"].connection.line_cost_per_km
    assert (line.currency, line.price_year, line.status, line.tier) == ("BRL", 2024, "sourced", 2)
    assert line.low < line.value < line.high
    ind_bay = parameters.countries["IND"].connection.bay_cost
    assert (ind_bay.value, ind_bay.low, ind_bay.high, ind_bay.status, ind_bay.tier) == (3.0, 1.5, 6.0, "proxy", 3)
    for iso in REAL_COUNTRIES:
        connection = parameters.countries[iso].connection
        assert connection.road_cost_per_km.value is None and connection.road_cost_excluded
        high = connection.road_cost_per_km_high  # sensitivity road_cost_high, an upper bound for the three
        assert high.status == "proxy" and high.low <= high.value <= high.high
    thresholds = {
        iso: parameters.countries[iso].connection.poi_voltage_threshold_kv.value for iso in REAL_COUNTRIES
    }
    assert thresholds == {"BRA": 138.0, "IND": 220.0, "PRT": 150.0}
    for iso in REAL_COUNTRIES:  # COMMAND 86: an author's choice with the evidence of docs/_audit/vth_evidence_85.md in the note
        assert parameters.countries[iso].connection.poi_voltage_threshold_kv.status == "author_choice"
    ind = parameters.countries["IND"].connection
    assert ind.poi_sensitivity_threshold_kv.value == 132.0  # sensitivity layer poi_ind_132kv
    assert parameters.countries["BRA"].connection.poi_sensitivity_threshold_kv is None
    assert "ren-dados-tecnicos-2024.pdf" in parameters.countries["PRT"].connection.poi_voltage_threshold_kv.note
    for iso in REAL_COUNTRIES:
        c = parameters.countries[iso].connection
        assert c.reference_project_mw.value == 100.0 and c.long_distance_flag_km.value == 100.0
        assert c.tortuosity_grid.value == 1.25 and (c.tortuosity_grid.range.min, c.tortuosity_grid.range.max) == (1.2, 1.3)
        assert c.transmission_loss_per_km.value == 0.0
        assert (c.transmission_loss_per_km_sensitivity.range.min, c.transmission_loss_per_km_sensitivity.range.max) == (0.0003, 0.0005)
        wind = parameters.countries[iso].technologies.wind
        assert wind.degradation_rate.value == 0.0017 and wind.degradation_rate.range.max == 0.0053
        assert wind.wind_degradation_complex_terrain.value == 0.0072
        zones = parameters.countries[iso].technologies.solar.degradation_by_zone
        assert zones is not None and set(zones.zones) == {f"T{i}" for i in range(1, 8)}


@pytest.mark.unit
def test_registry_uncertain_parameters_all_exist_and_variable_om_is_required_not_uncertain(
    parameters, technologies
):
    for tech, cfg in technologies.technologies.items():
        assert "opex_var_usd_per_mwh" in cfg.required_parameters
        assert "opex_var_usd_per_mwh" not in cfg.uncertain_parameters
        for iso, _t, params in (
            e for e in _entries(parameters, parameters.countries) if e[1] == tech
        ):
            for key in cfg.uncertain_parameters:
                if key in GROUP3_KERNEL_KEYS:
                    continue  # provided by the connection block and the degradation table
                assert hasattr(params, key), f"{iso} {tech}: no schema field {key}"


@pytest.mark.unit
def test_zzz_has_a_value_and_a_range_for_every_uncertain_parameter_all_synthetic(
    parameters, technologies
):
    for tech, cfg in technologies.technologies.items():
        params = getattr(parameters.countries["ZZZ"].technologies, tech)
        for key in cfg.uncertain_parameters:
            if key in GROUP3_KERNEL_KEYS:
                continue  # the synthetic connection block is checked below
            entry = getattr(params, key)
            assert entry.synthetic and entry.value is not None, f"ZZZ {tech} {key}"
            assert entry.range is not None, f"ZZZ {tech} {key}: no range"
            assert entry.range.min <= entry.value <= entry.range.max
            assert entry.range.min < entry.range.max  # the sampler has a span to draw from
        assert params.opex_var_usd_per_mwh.value is not None


@pytest.mark.unit
def test_zzz_group3_block_is_synthetic_with_a_range_for_every_sampled_value(parameters):
    zzz = parameters.countries["ZZZ"]
    connection = zzz.connection
    for name in GROUP3_UNIT_COSTS:
        cost = getattr(connection, name)
        assert cost.synthetic and cost.price_year == 2024 and cost.currency == "USD"
        assert cost.low < cost.high
    for entry in (connection.tortuosity_grid, connection.tortuosity_road):
        assert entry.synthetic and entry.range.min < entry.range.max
    assert zzz.technologies.solar.degradation_by_zone.synthetic
    assert zzz.technologies.wind.degradation_rate.range.min < zzz.technologies.wind.degradation_rate.range.max


@pytest.mark.unit
def test_zzz_cost_parameters_carry_the_2024_price_year_and_real_ones_only_where_recorded(parameters):
    for _iso, _tech, params in _entries(parameters, ("ZZZ",)):
        for key in COST_KEYS:
            assert getattr(params, key).price_year == 2024
    for _iso, _tech, params in _entries(parameters, REAL_COUNTRIES):
        for key in COST_KEYS:
            entry = getattr(params, key)
            assert entry.price_year == 2024, key  # Group 2 costs of the IRENA 2024 cohort (M-F6-07)


@pytest.mark.unit
def test_zzz_exercises_both_distributions(parameters):
    kinds = {
        getattr(params, key).range.distribution
        for _i, _t, params in _entries(parameters, ("ZZZ",))
        for key in ("capex_usd_per_kw", "opex_fixed_frac", "discount_rate")
    }
    assert kinds == {"uniform", "triangular"}
