"""Scenario discovery in the F7 pipeline: the outcome `V_f` of every future, the tables `prim_box`, `prim_bootstrap` and `prim_boxes`, the seed and
the skips (M-F7-08; D-F7-054 to D-F7-057). Expected values are recomputed here from the F7 output tables, not from the pipeline code."""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
from test_robustness_pipeline import CORE, PROVENANCE_KEY, _country, _run, _with_prim

from geofrea.robustness_analysis.scenario_discovery import (
    BOX_FOUND,
    NO_CASES,
    derive_seed,
)


def _nominal_displacement(entry, member, k):
    """`V_f` of the nominal vector in `member`, from the F7 tables: the capacity share of the shortlist whose rank within the ranked set is beyond 2k."""
    tables = entry.windows["core"].tables
    robustness = pd.read_parquet(tables["robustness"])
    ranked = robustness[robustness["cell_class"] == "ranked"].sort_values("cell_id")
    nominal = pd.read_parquet(tables["nominal_lcoe_by_member"])
    in_member = nominal[nominal["member"].astype(str) == member].set_index("cell_id")[
        "lcoe_nominal"
    ]
    lcoe = in_member.reindex(ranked["cell_id"]).fillna(np.inf).to_numpy()
    f0 = ranked["lcoe_nominal"].to_numpy()
    shortlist = np.zeros(len(ranked), dtype=bool)
    shortlist[np.lexsort((np.arange(len(ranked)), f0))[:k]] = True
    position = np.empty(len(ranked))
    position[np.lexsort((np.arange(len(ranked)), lcoe))] = np.arange(len(ranked))
    q = ranked["p_mw"].to_numpy()
    return float(q[shortlist & (position >= 2 * k)].sum() / q[shortlist].sum())


@pytest.mark.unit
def test_the_outcome_of_the_nominal_vector_is_the_capacity_share_beyond_the_tolerance(tmp_path):
    entry, _, _ = _run(tmp_path, experiments=_with_prim())
    futures = pd.read_parquet(entry.windows["core"].tables["futures"])
    k = entry.windows["core"].k
    nominal = futures[futures["sample"] == 0].set_index("member")["displaced_capacity_share"]
    for member in CORE:
        assert nominal[member] == pytest.approx(_nominal_displacement(entry, member, k))
    shares = futures["displaced_capacity_share"]
    assert shares.between(0.0, 1.0).all() and shares.notna().all()
    late = pd.read_parquet(entry.windows["sensitivity"].tables["futures"])
    assert late["displaced_capacity_share"].isna().all()  # PRIM runs on the core window only


@pytest.mark.unit
def test_the_descriptors_are_the_capacity_weighted_means_over_the_nominal_shortlist(tmp_path):
    entry, _, dirs = _run(tmp_path, experiments=_with_prim())
    futures = pd.read_parquet(entry.windows["core"].tables["futures"])
    robustness = pd.read_parquet(entry.windows["core"].tables["robustness"])
    ranked = robustness[robustness["cell_class"] == "ranked"].sort_values("cell_id")
    k = entry.windows["core"].k
    short = ranked.iloc[np.lexsort((np.arange(len(ranked)), ranked["lcoe_nominal"].to_numpy()))[:k]]
    forcing = pd.read_parquet(dirs["climate_dir"] / "forcing.parquet")
    forcing["member"] = forcing["member"].astype(str)
    for member in CORE:
        rows = forcing[(forcing["member"] == member)].set_index("cell_id").loc[short["cell_id"]]
        weights = short["p_mw"].to_numpy()
        expected = (rows["dT"].to_numpy() * weights).sum() / weights.sum()
        got = futures[futures["member"] == member]["dT_mean"].iloc[0]
        assert got == pytest.approx(expected)
        assert futures[futures["member"] == member]["delta_wind_mean"].iloc[0] == pytest.approx(
            (rows["delta_wind"].to_numpy() * weights).sum() / weights.sum()
        )


def _gcm_b_displaces(monkeypatch):
    """The staged cells keep their order in every future, so the real outcome is 0 everywhere; here GCM-B displaces half of the shortlist and the
    others a twentieth, which makes the known box `gcm in {GCM-B}` (the real outcome is checked against its definition in the tests above)."""
    from dataclasses import replace

    from geofrea.robustness_analysis import pipeline

    real = pipeline.futures_pass

    def patched(worlds, labels, samples, top, k, **kwargs):
        result = real(worlds, labels, samples, top, k, **kwargs)
        shares = np.array([[0.5 if label.gcm == "GCM-B" else 0.05] for label in labels])
        return replace(
            result,
            displaced_capacity_share=np.broadcast_to(shares, result.share_leaving.shape).copy(),
        )

    monkeypatch.setattr(pipeline, "futures_pass", patched)


@pytest.mark.unit
def test_prim_finds_the_known_box_applies_the_rule_and_writes_the_primary_row_and_the_variants(
    tmp_path, monkeypatch
):
    _gcm_b_displaces(monkeypatch)
    entry, _, _ = _run(tmp_path, experiments=_with_prim())
    tables = entry.windows["core"].tables
    box = pd.read_parquet(tables["prim_box"])
    primary = box[box["primary"]].iloc[0]
    futures = pd.read_parquet(tables["futures"]).query("sample >= 1")
    assert box["primary"].sum() == 1 and primary["variant"] == "primary"
    assert primary["n_futures"] == len(futures)
    assert primary["n_cases"] == int(
        (futures["gcm"] == "GCM-B").sum()
    )  # theta 0.20: 0.5 counts, 0.05 does not
    assert primary["status"] == BOX_FOUND
    assert primary["density"] == pytest.approx(1.0) and primary["coverage"] == pytest.approx(1.0)
    assert "gcm" in primary["restricted"].split("|") and primary["gcm__in"] == "GCM-B"
    assert primary["n_restricted"] <= 3
    trajectory = pd.read_parquet(tables["prim_boxes"])
    assert trajectory["selected"].sum() == 1
    chosen = trajectory[trajectory["selected"]].iloc[0]
    eligible = trajectory[
        (trajectory["coverage"] >= 0.50) & trajectory["n_restricted"].between(1, 3)
    ]
    assert chosen["density"] == pytest.approx(eligible["density"].max())
    variants = box.set_index("variant")
    assert {
        "theta_0.10",
        "theta_0.30",
        "coverage_0.40",
        "coverage_0.60",
        "support_0.02",
        "support_0.10",
    } <= set(variants.index)
    assert variants.loc["theta_0.30", "n_cases"] == primary["n_cases"]  # 0.5 is above every theta
    assert variants.loc["theta_0.10", "n_cases"] == primary["n_cases"]  # and 0.05 below them
    assert variants.loc["coverage_0.60", "outcome_threshold"] == pytest.approx(0.20)
    assert {"gcm__in", "ssp__in", "dT_mean__min", "dT_mean__max"} <= set(box.columns)
    boot = pd.read_parquet(tables["prim_bootstrap"])
    restriction = boot[boot["kind"] == "restriction"].set_index("name")["frequency"]
    assert restriction["gcm"] >= 0.5


@pytest.mark.unit
def test_the_special_cases_are_written_with_their_status_and_no_trajectory(tmp_path):
    entry, _, _ = _run(tmp_path, experiments=_with_prim(outcome_threshold=1.0))
    box = pd.read_parquet(entry.windows["core"].tables["prim_box"])
    primary = box[box["primary"]].iloc[0]
    assert primary["status"] == NO_CASES  # no future displaces the whole shortlist
    assert pd.isna(primary["density"]) and primary["restricted"] == ""
    assert len(pd.read_parquet(entry.windows["core"].tables["prim_boxes"])) == 0
    boot = pd.read_parquet(entry.windows["core"].tables["prim_bootstrap"])
    status = boot[boot["kind"] == "status"].set_index("name")["frequency"]
    assert status[NO_CASES] == pytest.approx(1.0)


@pytest.mark.unit
def test_the_bootstrap_seed_is_derived_from_the_sampler_seed_and_the_replicates_are_reproducible(
    tmp_path,
):
    experiments = _with_prim(outcome_threshold=0.05)
    entry, _, _ = _run(tmp_path / "a", experiments=experiments)
    again, _, _ = _run(tmp_path / "b", experiments=experiments)
    path = entry.windows["core"].tables["prim_bootstrap"]
    provenance = json.loads(pq.read_schema(path).metadata[PROVENANCE_KEY.encode()])
    assert provenance["prim"]["bootstrap_seed"] == derive_seed(experiments.sampler.seed)
    assert provenance["prim"]["bootstrap_replicates"] == 6
    assert provenance["prim"]["source"] == "OQ-056, pre-registered 2026-10-14"
    first = pd.read_parquet(path)
    pd.testing.assert_frame_equal(
        first, pd.read_parquet(again.windows["core"].tables["prim_bootstrap"])
    )
    status = first[first["kind"] == "status"]["frequency"]
    assert math.isclose(status.sum(), 1.0)
    assert set(first["kind"]) >= {"status", "restriction"}


@pytest.mark.unit
def test_prim_is_skipped_for_the_sensitivity_window_and_when_the_top_k_is_null(tmp_path):
    entry, _, _ = _run(tmp_path / "a", experiments=_with_prim())
    for kind in ("prim_boxes", "prim_box", "prim_bootstrap"):
        path = entry.windows["sensitivity"].tables[kind]
        assert len(pd.read_parquet(path)) == 0
        note = json.loads(pq.read_schema(path).metadata[b"geofrea_robustness_skipped"])
        assert note["open_question"] == "M-F7-08" and "core window" in note["reason"]
    entry, _, _ = _run(tmp_path / "b", country=_country(top_k_percent=None))
    path = entry.windows["core"].tables["prim_box"]
    note = json.loads(pq.read_schema(path).metadata[b"geofrea_robustness_skipped"])
    assert note["open_question"] == "OQ-021"
