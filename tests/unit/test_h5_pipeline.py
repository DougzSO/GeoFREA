"""H5 in the F7 pipeline: the tables `h5_summary` and `h5_members`, the target, the exposure and the consistency with T-R10 and T-R12
(M-F7-07; D-F7-050 to D-F7-053). Every expected value is recomputed here from the staged F5 table and the F7 output, not from the H5 module."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
import yaml
from test_robustness_pipeline import (
    CORE,
    HAZARD_MEMBERS,
    SENSITIVITY,
    _country,
    _run,
)

from geofrea.core.config_schemas import ExperimentsFile

REPO = Path(__file__).resolve().parents[2]
TAU = 45.0  # the ZZZ test value of wind
THRESHOLDS = {  # heat reaches the threshold from the cell index 10 (7 in the member with the bump); the other channels never do
    "tx35_days": 20.0,
    "tx40_days": 5.0,
    "rx5day_mm": 50.0,
    "wet_p95_exceed_freq": 0.5,
    "gust_mean_annual_max_ms": 30.0,
}


def _experiments(target=None, thresholds=None, rule=True, alternatives=()) -> ExperimentsFile:
    raw = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    raw["sampler"]["initial_size"] = 24
    if target is not None:
        raw["national_targets"]["ZZZ"] = {
            "wind": {**target, "alternatives": list(alternatives)},
            "solar": {"value": None, "unit": None, "source": None, "horizon": None},
        }
    for name, value in (thresholds or {}).items():
        raw["hazard_thresholds"][name]["threshold"] = value
    if not rule:
        raw["hypothesis_rules"]["H5"] = None
    return ExperimentsFile.model_validate(raw)


def _target(value, unit="TWh/year"):
    return {"value": value, "unit": unit, "source": "test plan", "horizon": 2040}


def _summary(entry, role="core") -> pd.DataFrame:
    return pd.read_parquet(entry.windows[role].tables["h5_summary"])


def _primary(entry, role="core") -> pd.Series:
    table = _summary(entry, role)
    assert table["primary"].sum() == 1
    return table[table["primary"]].iloc[0]


def _expected(entry, dirs):
    """The fixed domain recomputed from the staged F5 table and the F7 output: cells of the F7 set with LCOE at f0 at most tau."""
    robustness = pd.read_parquet(entry.windows["core"].tables["robustness"])
    f7 = robustness[robustness["cell_class"].isin(["ranked", "climate_fragile"])]
    domain = f7[f7["lcoe_nominal"] <= TAU].set_index("cell_id")
    potential = pd.read_parquet(dirs["potential_dir"] / "potential_wind__central.parquet")
    potential["member"] = potential["member"].astype(str)
    energy = {
        member: potential[(potential["member"] == member)].set_index("cell_id").loc[domain.index]
        for member in ["m0", *CORE]
    }
    return domain, energy


@pytest.mark.unit
def test_without_a_target_h5_is_not_testable_and_reports_the_energies_without_ratios(tmp_path):
    entry, _, dirs = _run(tmp_path)
    primary = _primary(entry)
    domain, energy = _expected(entry, dirs)
    assert len(domain) > 0
    assert primary["status"] == "not_testable" and primary["verdict"] is None
    assert primary["e0_twh"] == pytest.approx(energy["m0"]["E_MWh"].sum() / 1e6)
    losses = [energy["m0"]["E_MWh"].sum() - energy[m]["E_MWh"].sum() for m in CORE]
    assert primary["delta_e_twh"] == pytest.approx(max(0.0, max(losses)) / 1e6)
    assert pd.isna(primary["r_loss"]) and pd.isna(primary["r_exp"]) and pd.isna(primary["g_twh"])
    assert primary["n_domain_cells"] == len(domain)
    assert primary["domain_capacity_gw"] == pytest.approx(energy["m0"]["P_MW"].sum() / 1000.0)


@pytest.mark.unit
def test_a_target_in_twh_gives_the_slack_and_the_ratios_and_no_verdict_without_hazard_members(
    tmp_path,
):
    # staged energies are a few TWh/year, so a target of 1 TWh/year leaves a positive slack
    entry, _, dirs = _run(tmp_path, experiments=_experiments(_target(1.0)))
    primary = _primary(entry)
    _, energy = _expected(entry, dirs)
    e0 = energy["m0"]["E_MWh"].sum() / 1e6
    assert primary["status"] == "tested" and primary["h0_twh"] == pytest.approx(e0 - 1.0)
    assert primary["r_loss"] == pytest.approx(primary["delta_e_twh"] / (e0 - 1.0))
    assert primary["h5a_holds"] == (primary["r_loss"] >= 0.20)
    assert not primary["exposure_available"] and pd.isna(primary["r_exp"])
    assert primary["verdict"] is None and "H5b is not available" in primary["verdict_reason"]
    assert (primary["target_value"], primary["target_unit"], primary["target_horizon"]) == (
        1.0,
        "TWh/year",
        2040,
    )
    assert primary["target_source"] == "test plan" and primary["conversion"].startswith("none")
    members = pd.read_parquet(entry.windows["core"].tables["h5_members"]).set_index("member")
    assert list(members.index) == CORE and members["e0_twh"].nunique() == 1
    for member in CORE:
        assert members.loc[member, "energy_twh"] == pytest.approx(
            energy[member]["E_MWh"].sum() / 1e6
        )
        assert members.loc[member, "change_twh"] == pytest.approx(
            members.loc[member, "energy_twh"] - e0
        )
    assert members["attains_min"].sum() == 1 and members["exposed_twh"].isna().all()
    assert not members["carries_hazard_channel"].any()
    hypothesis = pd.read_parquet(entry.windows["core"].tables["hypothesis"]).set_index("statistic")
    assert hypothesis.loc["h5a_resource_loss_ratio", "value"] == pytest.approx(primary["r_loss"])
    assert hypothesis.loc["h5a_resource_loss_ratio", "verdict"] in ("met", "not_met")
    assert pd.isna(hypothesis.loc["h5b_exposure_ratio", "verdict"])
    assert "not available" in hypothesis.loc["h5b_exposure_ratio", "verdict_reason"]
    descriptive = hypothesis[(hypothesis["hypothesis"] == "H5") & hypothesis["rule"].isna()]
    assert (
        len(descriptive) > 0 and descriptive["verdict_reason"].str.startswith("descriptive").all()
    )


@pytest.mark.unit
def test_a_target_in_gw_is_converted_with_the_capacity_factor_of_the_cheapest_cells(tmp_path):
    g_cap = 0.5  # GW
    entry, _, dirs = _run(tmp_path, experiments=_experiments(_target(g_cap, "GW")))
    primary = _primary(entry)
    domain, energy = _expected(entry, dirs)
    ordered = domain.sort_values(["lcoe_nominal"], kind="stable").index  # cell_id order breaks ties
    ordered = domain.reset_index().sort_values(["lcoe_nominal", "cell_id"])["cell_id"].to_numpy()
    reference = energy["m0"].loc[ordered]
    capacity_gw = reference["P_MW"].to_numpy() / 1000.0
    before = np.concatenate([[0.0], np.cumsum(capacity_gw)[:-1]])
    weights = np.clip(g_cap - before, 0.0, capacity_gw)
    cf_bar = float((weights * reference["CF"].to_numpy()).sum() / weights.sum())
    assert capacity_gw.sum() > g_cap  # the target does not exceed the domain
    assert primary["cf_bar"] == pytest.approx(cf_bar)
    assert primary["g_twh"] == pytest.approx(8.76 * g_cap * cf_bar)
    assert primary["conversion"] == "cheapest_cells_first" and not primary["target_exceeds_domain"]
    assert primary["target_unit"] == "GW" and primary["target_value"] == g_cap
    sensitivities = _summary(entry).set_index("variant")
    assert "conversion_whole_domain" in sensitivities.index
    whole = reference["CF"].to_numpy() @ capacity_gw / capacity_gw.sum()
    assert sensitivities.loc["conversion_whole_domain", "cf_bar"] == pytest.approx(whole)


@pytest.mark.unit
def test_a_target_above_the_baseline_is_not_met_at_reference_with_ratios_on_the_target(tmp_path):
    entry, _, _ = _run(tmp_path, experiments=_experiments(_target(1.0e6)))
    primary = _primary(entry)
    assert primary["status"] == "target_not_met_at_reference" and primary["verdict"] is None
    assert primary["h0_twh"] < 0 and pd.isna(primary["r_loss"]) and pd.isna(primary["r_exp"])
    assert primary["delta_e_over_g"] == pytest.approx(primary["delta_e_twh"] / 1.0e6)
    assert "target not met at reference" in primary["verdict_reason"]
    hypothesis = pd.read_parquet(entry.windows["core"].tables["hypothesis"]).set_index("statistic")
    assert pd.isna(hypothesis.loc["h5a_resource_loss_ratio", "verdict"])
    assert pd.notna(hypothesis.loc["h5_loss_over_target", "value"])


@pytest.mark.unit
def test_with_hazard_members_and_thresholds_h5b_is_the_largest_exposed_energy_of_the_domain(
    tmp_path,
):
    entry, _, dirs = _run(
        tmp_path,
        experiments=_experiments(_target(1.0), THRESHOLDS),
        hazard=True,
    )
    primary = _primary(entry)
    domain, energy = _expected(entry, dirs)
    n = domain.index.to_numpy() - 500  # the cell index of the staged hazard values
    exposed_energy = {}
    for member, bump in ((CORE[0], 0.0), (CORE[2], 3.0)):
        exposed = (10.0 + n + bump) >= 20.0
        exposed_energy[member] = energy[member]["E_MWh"].to_numpy()[exposed].sum() / 1e6
    reference_energy = {
        member: energy[member]["E_MWh"].to_numpy()[(2.0 + n) >= 20.0].sum() / 1e6
        for member in HAZARD_MEMBERS
    }
    e0 = energy["m0"]["E_MWh"].sum() / 1e6
    assert primary["exposure_available"]
    assert primary["e_exp_twh"] == pytest.approx(max(exposed_energy.values()))
    assert primary["member_exp_max"] == max(exposed_energy, key=exposed_energy.get)
    assert primary["r_exp"] == pytest.approx(max(exposed_energy.values()) / (e0 - 1.0))
    assert primary["e_exp_reference_twh"] == pytest.approx(max(reference_energy.values()))
    assert (
        primary["exposure_increment_twh"]
        == pytest.approx(max(exposed_energy.values()) - max(reference_energy.values()))
    )  # the other reference channels never reach their thresholds, so the absolute statistic is the heat alone
    assert set(primary["reference_channels"].split("|")) == {
        "tx35_days",
        "tx40_days",
        "rx5day_mm",
        "gust_mean_annual_max_ms",
    }
    assert primary["verdict"] in (
        "supported",
        "partially_supported_resource",
        "partially_supported_exposure",
        "not_supported",
    )
    assert (
        primary["verdict"]
        == {
            (True, True): "supported",
            (True, False): "partially_supported_resource",
            (False, True): "partially_supported_exposure",
            (False, False): "not_supported",
        }[(bool(primary["r_loss"] >= 0.20), bool(primary["r_exp"] >= 0.20))]
    )
    members = pd.read_parquet(entry.windows["core"].tables["h5_members"]).set_index("member")
    assert members["carries_hazard_channel"].to_dict() == {
        CORE[0]: True,
        CORE[1]: False,
        CORE[2]: True,
    }
    assert (
        members.loc[CORE[1], "exposed_twh"] != members.loc[CORE[1], "exposed_twh"]
    )  # null, never 0
    for member in HAZARD_MEMBERS:
        assert members.loc[member, "exposed_twh"] == pytest.approx(exposed_energy[member])
        assert members.loc[member, "exposed_reference_twh"] == pytest.approx(
            reference_energy[member]
        )
    assert members["attains_exposure_max"].sum() == 1
    # T-R10 counts the same cells: the any_channel rows over the economic domain, per hazard member (the run itself checks it, V-03)
    exposure = pd.read_parquet(entry.windows["core"].tables["hazard_exposure"])
    union = exposure[
        (exposure["hazard"] == "any_channel")
        & (exposure["group"] == "economic_domain")
        & (exposure["basis"] == "absolute")
    ].set_index("member")["potential_twh"]
    for member in HAZARD_MEMBERS:
        assert union[member] == pytest.approx(exposed_energy[member])
    # the channels one by one: only the heat channel is exposed here, so it equals the union
    by_channel = _summary(entry).set_index("variant")
    assert by_channel.loc["channel_tx35_days", "e_exp_twh"] == pytest.approx(primary["e_exp_twh"])
    assert by_channel.loc["channel_gust_mean_annual_max_ms", "e_exp_twh"] == pytest.approx(0.0)


@pytest.mark.unit
def test_a_channel_without_a_threshold_is_excluded_and_declared_and_the_others_are_used(tmp_path):
    partial = {k: v for k, v in THRESHOLDS.items() if k != "wet_p95_exceed_freq"}
    entry, _, _ = _run(tmp_path, experiments=_experiments(_target(1.0), partial), hazard=True)
    primary = _primary(entry)
    assert primary["exposure_available"] and primary["verdict"] is not None
    assert primary["excluded_channels"] == "wet_p95_exceed_freq"
    assert primary["channels"].split("|") == [k for k in THRESHOLDS if k != "wet_p95_exceed_freq"]
    assert pd.notna(primary["r_exp"])


@pytest.mark.unit
def test_h5b_is_not_testable_only_when_no_channel_has_a_threshold(tmp_path):
    entry, _, _ = _run(tmp_path, experiments=_experiments(_target(1.0), {}), hazard=True)
    primary = _primary(entry)
    assert not primary["exposure_available"] and "OQ-051" in primary["exposure_reason"]
    assert primary["channels"] == "" and primary["excluded_channels"].split("|") == list(THRESHOLDS)
    assert primary["verdict"] is None and pd.notna(primary["r_loss"])


@pytest.mark.unit
def test_the_sensitivities_cover_the_listed_settings_and_never_revise_the_primary_row(tmp_path):
    entry, _, _ = _run(
        tmp_path,
        experiments=_experiments(_target(1.0), THRESHOLDS, alternatives=[_target(1.5)]),
        hazard=True,
    )
    table = _summary(entry)
    primary = table[table["primary"]].iloc[0]
    by_variant = table.set_index("variant")
    expected = {
        "primary",
        "lambda_0.10",
        "dynamic_domain",
        "target_alternative_1",
        "land_restrictive",
        "land_permissive",
        *(f"channel_{c}" for c in THRESHOLDS),
    }
    assert expected <= set(by_variant.index)
    assert by_variant.loc["lambda_0.10", "lam"] == 0.10
    assert by_variant.loc["lambda_0.10", "r_loss"] == pytest.approx(primary["r_loss"])
    assert by_variant.loc["dynamic_domain", "domain"] == "dynamic"
    assert by_variant.loc["target_alternative_1", "g_twh"] == pytest.approx(1.5)
    assert by_variant.loc["land_restrictive", "land_scenario"] == "restrictive"
    assert table["primary"].tolist() == [True] + [False] * (len(table) - 1)
    assert (table[~table["primary"]]["variant"] != "primary").all()


@pytest.mark.unit
def test_the_sensitivity_window_has_h5a_and_no_exposure(tmp_path):
    entry, _, _ = _run(tmp_path, experiments=_experiments(_target(1.0), THRESHOLDS), hazard=True)
    late = _primary(entry, "sensitivity")
    assert late["window"] == "2071-2100"
    assert not late["exposure_available"] and "hazard channel" in late["exposure_reason"]
    assert late["verdict"] is None and pd.notna(late["r_loss"])
    members = pd.read_parquet(entry.windows["sensitivity"].tables["h5_members"])
    assert set(members["member"]) == set(SENSITIVITY) and members["exposed_twh"].isna().all()


@pytest.mark.unit
def test_h5_is_skipped_and_flagged_while_its_rule_or_tau_is_null(tmp_path):
    entry, _, _ = _run(tmp_path, experiments=_experiments(_target(1.0), rule=False))
    for kind in ("h5_summary", "h5_members"):
        path = entry.windows["core"].tables[kind]
        assert len(pd.read_parquet(path)) == 0
        note = json.loads(pq.read_schema(path).metadata[b"geofrea_robustness_skipped"])
        assert note["open_question"] == "OQ-050"
    entry, _, _ = _run(
        tmp_path / "no_tau",
        country=_country(tau_lcoe_usd_per_mwh=None),
        experiments=_experiments(_target(1.0)),
    )
    path = entry.windows["core"].tables["h5_summary"]
    assert len(pd.read_parquet(path)) == 0
    note = json.loads(pq.read_schema(path).metadata[b"geofrea_robustness_skipped"])
    assert note["open_question"] == "OQ-008"


@pytest.mark.unit
def test_the_fixed_domain_series_of_t_r12_is_the_energy_of_h5(tmp_path):
    entry, _, _ = _run(tmp_path, experiments=_experiments(_target(1.0)))
    primary = _primary(entry)
    members = pd.read_parquet(entry.windows["core"].tables["h5_members"]).set_index("member")
    table = pd.read_parquet(entry.windows["core"].tables["potential_below_tau"])
    fixed = table[
        (table["series"] == "fixed_domain")
        & (table["land_scenario"] == "central")
        & (table["basis"] == "nominal")
    ].set_index("member")
    assert set(fixed.index) == {"m0", *CORE}
    assert fixed.loc["m0", "potential_twh"] == pytest.approx(primary["e0_twh"])
    for member in CORE:
        assert fixed.loc[member, "potential_twh"] == pytest.approx(
            members.loc[member, "energy_twh"]
        )
    assert fixed.loc["m0", "potential_gw"] == pytest.approx(primary["domain_capacity_gw"])
