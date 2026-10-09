"""The parameter keys F6 reads (M-F6-01, D-F6-009, D-F6-014, D-F6-016): names, units, pending entries and the synthetic block."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from geofrea.core.config_schemas import TechnologiesFile
from geofrea.core.schemas import ParametersFile

REPO = Path(__file__).resolve().parents[2]
REAL_COUNTRIES = ("BRA", "PRT", "IND")
NEW_KEYS = {
    "degradation_rate": "fraction/year",
    "grid_cost_usd_per_mw_km": "USD/(MW km)",
    "substation_cost_usd_per_mw": "USD/MW",
    "road_cost_usd_per_km": "USD/km",
}
COST_KEYS = (
    "capex_usd_per_kw",
    "opex_var_usd_per_mwh",
    "grid_cost_usd_per_mw_km",
    "substation_cost_usd_per_mw",
    "road_cost_usd_per_km",
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
def test_real_countries_carry_the_new_keys_pending_with_no_value(parameters):
    for iso, tech, params in _entries(parameters, REAL_COUNTRIES):
        for key, unit in NEW_KEYS.items():
            entry = getattr(params, key)
            assert entry.value is None and entry.status == "pending_research", f"{iso} {tech} {key}"
            assert entry.unit == unit and not entry.synthetic and entry.range is None
        assert params.opex_var_usd_per_mwh.value is None


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
                assert hasattr(params, key), f"{iso} {tech}: no schema field {key}"


@pytest.mark.unit
def test_zzz_has_a_value_and_a_range_for_every_uncertain_parameter_all_synthetic(
    parameters, technologies
):
    for tech, cfg in technologies.technologies.items():
        params = getattr(parameters.countries["ZZZ"].technologies, tech)
        for key in cfg.uncertain_parameters:
            entry = getattr(params, key)
            assert entry.synthetic and entry.value is not None, f"ZZZ {tech} {key}"
            assert entry.range is not None, f"ZZZ {tech} {key}: no range"
            assert entry.range.min <= entry.value <= entry.range.max
            assert entry.range.min < entry.range.max  # the sampler has a span to draw from
        assert params.opex_var_usd_per_mwh.value is not None


@pytest.mark.unit
def test_zzz_cost_parameters_carry_the_2024_price_year_and_real_ones_none_yet(parameters):
    for _iso, _tech, params in _entries(parameters, ("ZZZ",)):
        for key in COST_KEYS:
            assert getattr(params, key).price_year == 2024
    for _iso, _tech, params in _entries(parameters, REAL_COUNTRIES):
        for key in COST_KEYS:
            assert getattr(params, key).price_year is None  # to be audited by the author (OQ-054)


@pytest.mark.unit
def test_zzz_exercises_both_distributions(parameters):
    kinds = {
        getattr(params, key).range.distribution
        for _i, _t, params in _entries(parameters, ("ZZZ",))
        for key in ("capex_usd_per_kw", "opex_fixed_frac", "discount_rate")
    }
    assert kinds == {"uniform", "triangular"}
