"""The sample-major pass of H1 and H3, T-R10 and T-R12 against hand-made cases (M-F7-07, M-F7-08, D-F7-019, D-F7-020)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from test_robustness_evaluator import _samples, _world

from geofrea.lcoe_modeling.kernel import lcoe_block
from geofrea.robustness_analysis.futures import FuturesError, MemberLabel, futures_pass, slug
from geofrea.robustness_analysis.thesis_tables import (
    UNION,
    HazardMember,
    ThesisTableError,
    exposed_flags,
    exposure_rows,
    potential_below_tau_nominal,
)

LABELS = [
    MemberLabel("m1", "GCM-A", "SSP1-2.6"),
    MemberLabel("m2", "GCM-A", "SSP3-7.0"),
    MemberLabel("m3", "GCM-B", "SSP1-2.6"),
]


def _ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="stable")
    position = np.empty(values.size)
    position[order] = np.arange(values.size)
    return position


def _setup(seed=5, n_cells=40, k=8):
    rng = np.random.default_rng(seed)
    reference, worlds = _world(rng, n_cells=n_cells, n_core=3)
    samples = _samples(rng, 30)
    nominal = lcoe_block(reference.cells, samples.take(slice(0, 1)))[:, 0]
    top = np.zeros(n_cells, dtype=bool)
    top[np.argsort(nominal, kind="stable")[:k]] = True
    return worlds, samples, top, k


@pytest.mark.unit
def test_the_sample_major_pass_equals_the_brute_force_definition():
    worlds, samples, nominal_top, k = _setup()
    result = futures_pass(worlds, LABELS, samples, nominal_top, k, max_batch_gb=1.0)
    block = [lcoe_block(w.cells, samples, min_energy_mwh=w.floor) for w in worlds]
    for s in (0, 1, 17, 30):
        tops = []
        for j in range(3):
            order = np.argsort(block[j][:, s], kind="stable")
            top = np.zeros(40, dtype=bool)
            top[order[:k]] = True
            tops.append(top)
            leaving = (nominal_top & ~top).sum() / nominal_top.sum()
            assert result.share_leaving[j, s] == pytest.approx(leaving)
            union = (nominal_top | top).sum()
            assert result.jaccard_nominal[j, s] == pytest.approx((nominal_top & top).sum() / union)
        any_leaving = (nominal_top & ~np.logical_and.reduce(tops)).sum() / nominal_top.sum()
        assert result.draw_statistics["h1_leaving_any_member_share"][s] == pytest.approx(
            any_leaving
        )
        rho = np.corrcoef(_ranks(block[0][:, s]), _ranks(block[1][:, s]))[0, 1]
        key = f"h1_spearman_gcm__{slug('GCM-A')}__{slug('SSP1-2.6')}_vs_{slug('SSP3-7.0')}"
        assert result.draw_statistics[key][s] == pytest.approx(rho)


@pytest.mark.unit
def test_the_sample_major_pass_does_not_depend_on_the_batch_size():
    worlds, samples, nominal_top, k = _setup()
    big = futures_pass(worlds, LABELS, samples, nominal_top, k, max_batch_gb=1.0)
    small = futures_pass(worlds, LABELS, samples, nominal_top, k, max_batch_gb=1e-5)
    np.testing.assert_array_equal(big.share_leaving, small.share_leaving)
    for name, values in big.draw_statistics.items():
        np.testing.assert_array_equal(values, small.draw_statistics[name])


@pytest.mark.unit
def test_labels_that_do_not_match_the_members_or_an_empty_nominal_top_k_are_refused():
    worlds, samples, nominal_top, k = _setup()
    with pytest.raises(FuturesError):
        futures_pass(worlds, LABELS[:2], samples, nominal_top, k, max_batch_gb=1.0)
    with pytest.raises(FuturesError):
        futures_pass(worlds, LABELS, samples, np.zeros_like(nominal_top), k, max_batch_gb=1.0)


def _potential(rows):
    return pd.DataFrame(rows, columns=["cell_id", "member", "P_MW", "CF", "E_MWh"])


@pytest.mark.unit
def test_potential_below_tau_counts_feasible_cheap_cells_by_hand():
    # cells 1..3, m0 and one member; tau = 50, cf_min = 0.3
    potential = _potential(
        [
            (1, "m0", 100.0, 0.40, 350400.0),
            (2, "m0", 200.0, 0.35, 613200.0),
            (3, "m0", 300.0, 0.20, 525600.0),  # below cf_min
            (1, "mA", 100.0, 0.38, 332880.0),
            (2, "mA", 200.0, 0.34, 595680.0),
            # cell 3 absent in mA
        ]
    )
    lcoe = pd.DataFrame(
        {
            "cell_id": [1, 2, 3, 1, 2],
            "member": ["m0", "m0", "m0", "mA", "mA"],
            "lcoe_nominal": [40.0, 60.0, 30.0, 45.0, 49.0],
        }
    )
    rows = potential_below_tau_nominal(potential, lcoe, ["mA"], "m0", 0.3, 50.0, 0.25, "central")
    got = {(r["member"], r["series"]): r for r in rows}
    assert got[("m0", "all_present")]["potential_gw"] == pytest.approx(0.1)  # cell 1 only
    assert got[("mA", "all_present")]["potential_gw"] == pytest.approx(0.3)  # cells 1 and 2
    assert got[("mA", "like_for_like")]["potential_gw"] == pytest.approx(0.3)
    assert got[("m0", "like_for_like")]["potential_gw"] == pytest.approx(0.1)
    assert got[("m0", "like_for_like")]["gap_to_target_gw"] == pytest.approx(0.15)
    assert got[("mA", "like_for_like")]["potential_twh"] == pytest.approx(
        (332880.0 + 595680.0) / 1e6
    )


@pytest.mark.unit
def test_potential_below_tau_refuses_f5_rows_without_an_f6_nominal_lcoe():
    potential = _potential([(1, "m0", 100.0, 0.4, 350400.0)])
    lcoe = pd.DataFrame({"cell_id": [2], "member": ["m0"], "lcoe_nominal": [40.0]})
    with pytest.raises(ThesisTableError):
        potential_below_tau_nominal(potential, lcoe, [], "m0", 0.3, 50.0, None, "central")


@pytest.mark.unit
def test_exposure_sums_the_potential_above_the_threshold_by_group_and_skips_null_thresholds():
    ids = np.array([10, 11, 12, 13])
    hazard = pd.DataFrame(
        {
            "cell_id": ids,
            "member": "h1",
            "tx35_days": [5.0, 40.0, 41.0, 2.0],
            "tx35_days_ref": [1.0, 1.0, 50.0, 1.0],
            "rx5day_mm": [1.0, 1.0, 1.0, 1.0],
        }
    )
    member = HazardMember(
        "h1", "GCM-A", "SSP3-7.0", np.array([100.0, 200.0, 300.0, 400.0]), np.array([1e6] * 4)
    )
    groups = {
        "f7_set": np.ones(4, dtype=bool),
        "robust_top_k": np.array([False, True, True, False]),
    }
    rows, shares = exposure_rows(
        hazard, [member], {"tx35_days": 30.0, "rx5day_mm": None}, ids, groups
    )
    got = {(r["group"], r["basis"]): r for r in rows}
    assert {r["hazard"] for r in rows} == {
        "tx35_days",
        "any_channel",
    }  # the null threshold is skipped; the union of one channel is that channel
    assert got[("f7_set", "absolute")]["potential_gw"] == pytest.approx(0.5)  # cells 11, 12
    assert got[("f7_set", "absolute")]["potential_gw"] == pytest.approx(0.5)  # cells 11, 12
    assert got[("robust_top_k", "absolute")]["n_cells"] == 2
    assert got[("f7_set", "reference")]["potential_gw"] == pytest.approx(
        0.3
    )  # the reference column above 30: cell 12
    assert shares["tx35_days"] == pytest.approx(500.0 / 1000.0)


@pytest.mark.unit
def test_exposure_refuses_a_hazard_member_without_rows_for_the_f7_set():
    hazard = pd.DataFrame({"cell_id": [10], "member": "h1", "tx35_days": [1.0]})
    member = HazardMember("h1", "G", "S", np.array([1.0, 1.0]), np.array([1.0, 1.0]))
    with pytest.raises(ThesisTableError):
        exposure_rows(hazard, [member], {"tx35_days": 0.0}, np.array([10, 11]), {})


@pytest.mark.unit
def test_a_cell_exactly_at_the_threshold_is_exposed_because_the_comparison_is_at_least():
    ids = np.array([10, 11, 12])
    rows = pd.DataFrame({"tx35_days": [29.9, 30.0, 30.1]}, index=pd.Index(ids, name="cell_id"))
    flags = exposed_flags(rows, ids, "tx35_days", 30.0, "absolute", "h1")
    assert flags.tolist() == [False, True, True]
    nan = pd.DataFrame({"tx35_days": [np.nan, 31.0, 2.0]}, index=pd.Index(ids, name="cell_id"))
    assert exposed_flags(nan, ids, "tx35_days", 30.0, "absolute", "h1").tolist() == [
        False,
        True,
        False,
    ]
    with pytest.raises(ThesisTableError, match="reference value of the same quantity"):
        exposed_flags(rows, ids, "wet_p95_exceed_freq", 0.1, "reference", "h1")
    with pytest.raises(ThesisTableError, match="lack cells"):
        exposed_flags(rows, np.array([10, 99]), "tx35_days", 30.0, "absolute", "h1")


@pytest.mark.unit
def test_the_any_channel_rows_count_a_cell_once_and_the_gust_is_its_own_reference():
    ids = np.array([10, 11, 12, 13])
    hazard = pd.DataFrame(
        {
            "cell_id": ids,
            "member": "h1",
            "tx35_days": [40.0, 40.0, 1.0, 1.0],  # cells 10 and 11
            "tx35_days_ref": [1.0, 1.0, 1.0, 1.0],
            "rx5day_mm": [90.0, 1.0, 90.0, 1.0],  # cells 10 and 12
            "rx5day_mm_ref": [1.0, 1.0, 1.0, 1.0],
            "gust_mean_annual_max_ms": [1.0, 1.0, 1.0, 50.0],  # cell 13
        }
    )
    member = HazardMember(
        "h1",
        "GCM-A",
        "SSP3-7.0",
        np.array([100.0, 200.0, 300.0, 400.0]),
        np.array([1e6, 2e6, 3e6, 4e6]),
    )
    thresholds = {"tx35_days": 30.0, "rx5day_mm": 50.0, "gust_mean_annual_max_ms": 30.0}
    rows, _ = exposure_rows(hazard, [member], thresholds, ids, {"f7_set": np.ones(4, dtype=bool)})
    got = {(r["hazard"], r["basis"]): r for r in rows}
    union = got[(UNION, "absolute")]
    assert (
        union["n_cells"] == 4
    )  # cells 10, 11, 12 and 13, cell 10 counted once although it is in two channels
    assert union["potential_twh"] == pytest.approx(10.0)
    assert (
        got[("tx35_days", "absolute")]["n_cells"] == 2
        and got[("rx5day_mm", "absolute")]["n_cells"] == 2
    )
    # the reference values: none of the heat or rain cells reach the thresholds; the gust is its own reference
    assert got[(UNION, "reference")]["n_cells"] == 1 and got[(UNION, "reference")][
        "potential_twh"
    ] == pytest.approx(4.0)
    assert got[("gust_mean_annual_max_ms", "reference")]["n_cells"] == 1


@pytest.mark.unit
def test_the_fixed_domain_series_is_the_energy_of_the_cells_below_tau_at_the_reference_in_every_member():
    # cell 1 is cheap at m0 and dear in mA; cell 2 is dear at m0 and cheap in mA; cell 3 is below cf_min at m0
    potential = _potential(
        [
            (1, "m0", 100.0, 0.40, 350400.0),
            (2, "m0", 200.0, 0.35, 613200.0),
            (3, "m0", 300.0, 0.20, 525600.0),
            (1, "mA", 100.0, 0.30, 262800.0),
            (2, "mA", 200.0, 0.34, 595680.0),
            (3, "mA", 300.0, 0.20, 525600.0),
        ]
    )
    lcoe = pd.DataFrame(
        {
            "cell_id": [1, 2, 3, 1, 2, 3],
            "member": ["m0", "m0", "m0", "mA", "mA", "mA"],
            "lcoe_nominal": [40.0, 60.0, 30.0, 70.0, 45.0, 30.0],
        }
    )
    rows = potential_below_tau_nominal(potential, lcoe, ["mA"], "m0", 0.3, 50.0, None, "central")
    got = {(r["member"], r["series"]): r for r in rows}
    # the domain is cell 1 only (cheap at the reference, feasible there), kept in mA although dearer than tau there
    assert got[("m0", "fixed_domain")]["potential_twh"] == pytest.approx(350400.0 / 1e6)
    assert got[("mA", "fixed_domain")]["potential_twh"] == pytest.approx(262800.0 / 1e6)
    assert got[("mA", "fixed_domain")]["potential_gw"] == pytest.approx(0.1)
    assert got[("mA", "like_for_like")]["potential_gw"] == pytest.approx(
        0.2
    )  # the dynamic domain of mA is cell 2 alone, not cell 1
