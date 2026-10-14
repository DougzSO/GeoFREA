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
        assert 0 < params.cf_min.value < 1


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
    h1 = experiments.hypothesis_rules["H1"]  # pre-registered 2026-10-13 (OQ-050, H1)
    assert (h1.alpha, h1.beta, h1.tolerance_multiple_of_k, h1.rbo_p) == (0.60, 0.20, 1.0, "1 - 1/k")
    assert h1.source == "OQ-050 (H1), pre-registered 2026-10-13"
    h2 = experiments.hypothesis_rules["H2"]  # pre-registered 2026-10-13 (OQ-050, H2)
    assert (h2.gamma, h2.partition, h2.region_statistic, h2.target) == (
        0.30,
        "admin1",
        "capacity_weighted_mean",
        "top_k_capacity",
    )
    assert h2.source == "OQ-050 (H2), pre-registered 2026-10-13"
    h3 = experiments.hypothesis_rules["H3"]  # pre-registered 2026-10-13 (OQ-050, H3)
    assert (h3.delta, h3.tolerance_multiple_of_k, h3.domain, h3.weight) == (
        0.20,
        1.0,
        "I",
        "capacity",
    )
    assert h3.source == "OQ-050 (H3), pre-registered 2026-10-13"
    h4 = experiments.hypothesis_rules["H4"]  # pre-registered 2026-10-13 (OQ-050, H4)
    assert (h4.lower, h4.upper, h4.rule, h4.tolerance_multiple_of_k) == (
        0.40,
        0.60,
        "strict_per_technology",
        1.0,
    )
    assert h4.source == "OQ-050 (H4), pre-registered 2026-10-13"
    h5 = experiments.hypothesis_rules["H5"]  # pre-registered 2026-10-14 (OQ-050, H5)
    assert (h5.lambda_, h5.sensitivity_lambda, h5.domain, h5.members, h5.hazard_members) == (
        0.20,
        0.10,
        "fixed_at_f0",
        "core_window",
        "hazard_channel",
    )
    assert h5.source == "OQ-050 (H5), pre-registered 2026-10-14"
    assert set(experiments.national_targets) == {"BRA", "PRT", "IND"}  # OQ-010: no value yet
    for by_tech in experiments.national_targets.values():
        assert set(by_tech) == {"solar", "wind"}
        assert all(
            t.value is None
            and t.unit is None
            and t.source is None
            and t.horizon is None
            and t.alternatives == []
            for t in by_tech.values()
        )
    assert set(experiments.hazard_thresholds) == {
        "tx35_days",
        "tx40_days",
        "rx5day_mm",
        "wet_p95_exceed_freq",
        "gust_mean_annual_max_ms",
    }
    assert all(h.threshold is None for h in experiments.hazard_thresholds.values())
    prim = experiments.prim  # pre-registered 2026-10-14 (OQ-056)
    assert (
        prim.outcome_threshold,
        prim.tolerance_multiple_of_k,
        prim.peel_alpha,
        prim.mass_min,
    ) == (
        0.20,
        1.0,
        0.05,
        0.05,
    )
    assert (prim.max_restricted_descriptors, prim.box_choice, prim.min_coverage) == (
        3,
        "max_density_given_min_coverage",
        0.50,
    )
    assert (prim.bootstrap_replicates, prim.percentile_low, prim.percentile_high) == (200, 5, 95)
    assert prim.sensitivity.outcome_threshold == [0.10, 0.30]
    assert prim.sensitivity.min_coverage == [0.40, 0.60]
    assert prim.sensitivity.mass_min == [0.02, 0.10]
    assert prim.source == "OQ-056, pre-registered 2026-10-14"
    synthesis = experiments.synthesis  # pre-registered 2026-10-14 (OQ-050, T-R8)
    assert (
        synthesis.labels.consistent,
        synthesis.labels.context_dependent,
        synthesis.labels.not_assessable,
    ) == ("consistent", "context-dependent", "not assessable")
    assert (synthesis.min_testable_cases, synthesis.rule) == (2, "all_testable_same_verdict")
    assert synthesis.partial_classes_separate == ["H1", "H5"]
    assert synthesis.source == "OQ-050 (T-R8), pre-registered 2026-10-14"
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
    bad["hypothesis_rules"]["RQ4"] = [{"statistic": "x", "comparison": "approx", "threshold": 1}]
    with pytest.raises(ValueError):
        ExperimentsFile.model_validate(bad)
    ok = json.loads(json.dumps(raw))
    ok["hypothesis_rules"]["RQ4"] = [{"statistic": "x", "comparison": "ge", "threshold": 0.5}]
    assert ExperimentsFile.model_validate(ok).hypothesis_rules["RQ4"][0].threshold == 0.5


@pytest.mark.unit
def test_h1_has_its_own_form_and_no_other_form_is_accepted():
    raw = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    as_list = json.loads(json.dumps(raw))
    as_list["hypothesis_rules"]["H1"] = [{"statistic": "x", "comparison": "ge", "threshold": 0.5}]
    with pytest.raises(ValueError, match="H1Rule"):
        ExperimentsFile.model_validate(as_list)
    on_h2 = json.loads(json.dumps(raw))
    on_h2["hypothesis_rules"]["RQ4"] = raw["hypothesis_rules"]["H1"]
    with pytest.raises(ValueError, match="belongs to H1"):
        ExperimentsFile.model_validate(on_h2)
    other_rbo = json.loads(json.dumps(raw))
    other_rbo["hypothesis_rules"]["H1"]["rbo_p"] = "0.9"
    with pytest.raises(ValueError):
        ExperimentsFile.model_validate(other_rbo)
    missing_threshold = json.loads(json.dumps(raw))
    del missing_threshold["hypothesis_rules"]["H1"]["beta"]
    with pytest.raises(ValueError):
        ExperimentsFile.model_validate(missing_threshold)


@pytest.mark.unit
def test_h2_has_its_own_form_and_no_other_form_is_accepted():
    raw = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    as_list = json.loads(json.dumps(raw))
    as_list["hypothesis_rules"]["H2"] = [{"statistic": "x", "comparison": "ge", "threshold": 0.5}]
    with pytest.raises(ValueError, match="H2Rule"):
        ExperimentsFile.model_validate(as_list)
    on_h5 = json.loads(json.dumps(raw))
    on_h5["hypothesis_rules"]["RQ4"] = raw["hypothesis_rules"]["H2"]
    with pytest.raises(ValueError, match="belongs to H2"):
        ExperimentsFile.model_validate(on_h5)
    for key, value in (
        ("partition", "admin2"),
        ("region_statistic", "median"),
        ("target", "national"),
    ):
        other = json.loads(json.dumps(raw))
        other["hypothesis_rules"]["H2"][key] = value
        with pytest.raises(ValueError):
            ExperimentsFile.model_validate(other)
    missing = json.loads(json.dumps(raw))
    del missing["hypothesis_rules"]["H2"]["gamma"]
    with pytest.raises(ValueError):
        ExperimentsFile.model_validate(missing)


@pytest.mark.unit
def test_h3_has_its_own_form_and_no_other_form_is_accepted():
    raw = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    as_list = json.loads(json.dumps(raw))
    as_list["hypothesis_rules"]["H3"] = [{"statistic": "x", "comparison": "ge", "threshold": 0.5}]
    with pytest.raises(ValueError, match="H3Rule"):
        ExperimentsFile.model_validate(as_list)
    on_h5 = json.loads(json.dumps(raw))
    on_h5["hypothesis_rules"]["RQ4"] = raw["hypothesis_rules"]["H3"]
    with pytest.raises(ValueError, match="belongs to H3"):
        ExperimentsFile.model_validate(on_h5)
    on_h3 = json.loads(json.dumps(raw))
    on_h3["hypothesis_rules"]["H3"] = raw["hypothesis_rules"]["H2"]
    with pytest.raises(ValueError, match="H3Rule"):
        ExperimentsFile.model_validate(on_h3)
    for key, value in (("domain", "I_0"), ("weight", "cells")):
        other = json.loads(json.dumps(raw))
        other["hypothesis_rules"]["H3"][key] = value
        with pytest.raises(ValueError):
            ExperimentsFile.model_validate(other)
    for key in ("delta", "tolerance_multiple_of_k"):
        missing = json.loads(json.dumps(raw))
        del missing["hypothesis_rules"]["H3"][key]
        with pytest.raises(ValueError):
            ExperimentsFile.model_validate(missing)


@pytest.mark.unit
def test_h4_has_its_own_form_and_no_other_form_is_accepted():
    raw = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    as_list = json.loads(json.dumps(raw))
    as_list["hypothesis_rules"]["H4"] = [{"statistic": "x", "comparison": "ge", "threshold": 0.5}]
    with pytest.raises(ValueError, match="H4Rule"):
        ExperimentsFile.model_validate(as_list)
    on_h5 = json.loads(json.dumps(raw))
    on_h5["hypothesis_rules"]["RQ4"] = raw["hypothesis_rules"]["H4"]
    with pytest.raises(ValueError, match="belongs to H4"):
        ExperimentsFile.model_validate(on_h5)
    other_rule = json.loads(json.dumps(raw))
    other_rule["hypothesis_rules"]["H4"]["rule"] = "any_pair"
    with pytest.raises(ValueError):
        ExperimentsFile.model_validate(other_rule)
    crossed = json.loads(json.dumps(raw))
    crossed["hypothesis_rules"]["H4"]["lower"] = 0.7
    with pytest.raises(ValueError, match="below upper"):
        ExperimentsFile.model_validate(crossed)
    for key in ("lower", "upper", "tolerance_multiple_of_k"):
        missing = json.loads(json.dumps(raw))
        del missing["hypothesis_rules"]["H4"][key]
        with pytest.raises(ValueError):
            ExperimentsFile.model_validate(missing)


@pytest.mark.unit
def test_h5_has_its_own_form_and_no_other_form_is_accepted():
    raw = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    as_list = json.loads(json.dumps(raw))
    as_list["hypothesis_rules"]["H5"] = [{"statistic": "x", "comparison": "ge", "threshold": 0.5}]
    with pytest.raises(ValueError, match="H5Rule"):
        ExperimentsFile.model_validate(as_list)
    on_other = json.loads(json.dumps(raw))
    on_other["hypothesis_rules"]["RQ4"] = raw["hypothesis_rules"]["H5"]
    with pytest.raises(ValueError, match="belongs to H5"):
        ExperimentsFile.model_validate(on_other)
    for key, value in (
        ("domain", "dynamic"),
        ("members", "all_members"),
        ("hazard_members", "every_member"),
        ("lambda", 0.0),
        ("lambda", 1.5),
        ("unknown_key", 1),
    ):
        other = json.loads(json.dumps(raw))
        other["hypothesis_rules"]["H5"][key] = value
        with pytest.raises(ValueError):
            ExperimentsFile.model_validate(other)
    for key in ("lambda", "sensitivity_lambda", "domain", "members", "hazard_members", "source"):
        missing = json.loads(json.dumps(raw))
        del missing["hypothesis_rules"]["H5"][key]
        with pytest.raises(ValueError):
            ExperimentsFile.model_validate(missing)


@pytest.mark.unit
def test_a_national_target_value_needs_its_unit_source_and_horizon():
    raw = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    ok = json.loads(json.dumps(raw))
    ok["national_targets"]["PRT"]["solar"] = {
        "value": 8.0,
        "unit": "GW",
        "source": "test source",
        "horizon": 2030,
        "alternatives": [{"value": 2.5, "unit": "TWh/year", "source": "test", "horizon": 2035}],
    }
    target = ExperimentsFile.model_validate(ok).national_targets["PRT"]["solar"]
    assert (target.value, target.unit, target.horizon) == (8.0, "GW", 2030)
    assert target.alternatives[0].unit == "TWh/year"
    for missing in ("unit", "source", "horizon"):
        bad = json.loads(json.dumps(ok))
        bad["national_targets"]["PRT"]["solar"][missing] = None
        with pytest.raises(ValueError, match="unit, source and horizon"):
            ExperimentsFile.model_validate(bad)
    wrong_unit = json.loads(json.dumps(ok))
    wrong_unit["national_targets"]["PRT"]["solar"]["unit"] = "MW"
    with pytest.raises(ValueError):
        ExperimentsFile.model_validate(wrong_unit)
    negative = json.loads(json.dumps(ok))
    negative["national_targets"]["PRT"]["solar"]["value"] = -1.0
    with pytest.raises(ValueError):
        ExperimentsFile.model_validate(negative)


@pytest.mark.unit
def test_the_prim_block_needs_every_setting_and_refuses_values_outside_their_domain():
    raw = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    for key in (
        "outcome_threshold",
        "peel_alpha",
        "mass_min",
        "min_coverage",
        "source",
        "sensitivity",
    ):
        missing = json.loads(json.dumps(raw))
        del missing["prim"][key]
        with pytest.raises(ValueError):
            ExperimentsFile.model_validate(missing)
    for key, value in (
        ("outcome_threshold", 0.0),
        ("peel_alpha", 0.6),
        ("mass_min", 1.0),
        ("max_restricted_descriptors", 0),
        ("box_choice", "highest_coverage"),
        ("bootstrap_replicates", 0),
        ("unknown_key", 1),
    ):
        other = json.loads(json.dumps(raw))
        other["prim"][key] = value
        with pytest.raises(ValueError):
            ExperimentsFile.model_validate(other)
    shares = json.loads(json.dumps(raw))
    shares["prim"]["sensitivity"]["min_coverage"] = [0.4, 1.5]
    with pytest.raises(ValueError, match="shares"):
        ExperimentsFile.model_validate(shares)


@pytest.mark.unit
def test_the_synthesis_block_needs_its_labels_two_testable_cases_and_its_rule():
    raw = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    for key in ("labels", "min_testable_cases", "rule", "partial_classes_separate", "source"):
        missing = json.loads(json.dumps(raw))
        del missing["synthesis"][key]
        with pytest.raises(ValueError):
            ExperimentsFile.model_validate(missing)
    for key, value in (
        ("min_testable_cases", 1),
        ("rule", "majority"),
        ("partial_classes_separate", ["H2"]),
        ("unknown_key", 1),
    ):
        other = json.loads(json.dumps(raw))
        other["synthesis"][key] = value
        with pytest.raises(ValueError):
            ExperimentsFile.model_validate(other)
