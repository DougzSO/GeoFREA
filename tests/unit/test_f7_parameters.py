"""The decision parameters F7 reads (M-F7-01, M-F7-04, M-F7-05, M-F7-07, M-F7-08; D-F7-029): keys, units, pending entries, the synthetic block."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from geofrea.core.config_loader import load_experiments
from geofrea.core.config_schemas import ExperimentsFile, TechnologiesFile
from geofrea.core.schemas import ParametersFile

REPO = Path(__file__).resolve().parents[2]
REAL_COUNTRIES = ("BRA", "PRT", "IND")
DECISION_KEYS = {
    "cf_min": "fraction",
    "tau_lcoe_usd_per_mwh": "USD/MWh",
    "capacity_target_gw": "GW",
    "top_k_percent": "percent",
    "prim_outcome_share": "fraction",
}


@pytest.fixture(scope="module")
def parameters() -> ParametersFile:
    raw = json.loads((REPO / "config" / "parameters.json").read_text(encoding="utf-8"))
    return ParametersFile.model_validate(raw)


def _entries(parameters: ParametersFile, countries):
    for iso in countries:
        for tech in ("solar", "wind"):
            yield iso, tech, getattr(parameters.countries[iso].technologies, tech)


@pytest.mark.unit
def test_real_countries_carry_the_decision_keys_pending_with_no_value(parameters):
    for iso, tech, params in _entries(parameters, REAL_COUNTRIES):
        for key, unit in DECISION_KEYS.items():
            entry = getattr(params, key)
            assert entry.value is None and entry.status == "pending_research", f"{iso} {tech} {key}"
            assert entry.unit == unit and not entry.synthetic and entry.range is None


@pytest.mark.unit
def test_the_synthetic_country_carries_test_values_flagged_synthetic(parameters):
    for _iso, tech, params in _entries(parameters, ("ZZZ",)):
        for key, unit in DECISION_KEYS.items():
            entry = getattr(params, key)
            assert entry.value is not None and entry.synthetic is True, f"{tech} {key}"
            assert entry.unit == unit and entry.tier is None
        assert params.tau_lcoe_usd_per_mwh.price_year == 2024  # S-07
        assert 0 < params.top_k_percent.value <= 100
        assert 0 < params.cf_min.value < 1 and 0 < params.prim_outcome_share.value <= 1


@pytest.mark.unit
def test_the_registry_requires_the_decision_keys_so_a_production_run_refuses_a_null():
    raw = yaml.safe_load((REPO / "config" / "technologies.yaml").read_text(encoding="utf-8"))
    registry = TechnologiesFile.model_validate({"technologies": raw})
    for tech, cfg in registry.technologies.items():
        for key in DECISION_KEYS:
            assert key in cfg.required_parameters, f"{tech} {key}"
            assert key not in cfg.uncertain_parameters


@pytest.mark.unit
def test_the_experiment_blocks_of_f7_are_null_in_the_shipped_file():
    experiments = load_experiments(REPO / "config" / "experiments.yaml")
    assert set(experiments.hypothesis_rules) == {"H1", "H2", "H3", "H4", "H5"}
    assert all(rules is None for rules in experiments.hypothesis_rules.values())
    assert set(experiments.hazard_thresholds) == {
        "tx35_days",
        "tx40_days",
        "rx5day_mm",
        "wet_p95_exceed_freq",
        "gust_mean_annual_max_ms",
    }
    assert all(h.threshold is None for h in experiments.hazard_thresholds.values())
    assert experiments.prim.peel_alpha is None and experiments.prim.mass_min is None
    assert experiments.external_validation.vintage_min_start_year is None
    assert experiments.thresholds["regret_quantile"] == 0


@pytest.mark.unit
def test_a_vintage_filter_needs_its_reason_and_a_rule_needs_a_known_comparison():
    raw = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    bad = json.loads(json.dumps(raw))
    bad["external_validation"]["vintage_min_start_year"] = 2015
    with pytest.raises(ValueError, match="vintage_reason"):
        ExperimentsFile.model_validate(bad)
    bad = json.loads(json.dumps(raw))
    bad["hypothesis_rules"]["H1"] = [{"statistic": "x", "comparison": "approx", "threshold": 1}]
    with pytest.raises(ValueError):
        ExperimentsFile.model_validate(bad)
    ok = json.loads(json.dumps(raw))
    ok["hypothesis_rules"]["H1"] = [{"statistic": "x", "comparison": "ge", "threshold": 0.5}]
    assert ExperimentsFile.model_validate(ok).hypothesis_rules["H1"][0].threshold == 0.5
