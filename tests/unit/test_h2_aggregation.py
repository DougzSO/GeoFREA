"""H2, spatial aggregation bias, on hand-made cells (M-F7-07; thesis text docs/thesis/hypotheses/H2_spatial_aggregation_bias.tex)."""

from __future__ import annotations

import numpy as np
import pytest

from geofrea.robustness_analysis.h2_aggregation import (
    GAMMA_PROFILE,
    MEDIAN,
    NOT_SUPPORTED,
    NOT_TESTABLE,
    SUPPORTED,
    H2Error,
    H2Inputs,
    decision_profile,
    evaluate_variant,
    select_cells,
    select_regions,
    sensitivity_variants,
    smallest_supporting_gamma,
    verdict_of,
)


def _inputs(
    cells: list[tuple[str, float, float]],
    *,
    ranked: list[bool] | None = None,
    p90: np.ndarray | None = None,
    gcms: tuple[str, ...] = ("G",),
) -> H2Inputs:
    """`cells` are `(region, capacity MW, z)`; with one member whose P90 is `z` unless `p90` is given."""
    z = np.array([c[2] for c in cells], dtype=float)
    mask = np.ones(len(cells), dtype=bool) if ranked is None else np.array(ranked)
    return H2Inputs(
        z=np.where(mask, z, np.nan),
        q=np.array([c[1] for c in cells], dtype=float),
        region=np.array([c[0] for c in cells], dtype=object),
        ranked=mask,
        sr=None,
        p90=z[:, None] if p90 is None else p90,
        gcms=gcms,
    )


def _evaluate(inputs: H2Inputs, **kwargs):
    settings = {"variant": "primary", "gamma": 0.30, "top_k_percent": 10.0}
    return evaluate_variant(inputs, **{**settings, **kwargs})


def _worked_example() -> H2Inputs:
    """Section 8 of the thesis text: three states, Q_max = 1000 MW, T = 100 MW in the top-k set (1 MW cells, k = 100 of 1000)."""
    cells = (
        [("A", 1.0, 0.1)] * 60 + [("A", 1.0, 2.0)] * 300  # A: 60 MW of top cells, 300 MW of poor ones
        + [("B", 1.0, 1.0)] * 400  # B: 400 MW of intermediate cells, no top cell
        + [("C", 1.0, 0.1)] * 40 + [("C", 1.0, 2.0)] * 200  # C: 40 MW of top cells, 200 MW of poor ones
    )  # fmt: skip
    return _inputs(cells)


@pytest.mark.unit
def test_the_worked_example_of_the_thesis_text_gives_o_zero_y_025_and_supported():
    result, detail = _evaluate(_worked_example())
    assert (result.target_mw, result.q_max_mw) == (100.0, 1000.0)
    assert result.overlap == 0.0 and result.overlap_ref == pytest.approx(0.10)
    assert result.testable and result.verdict == SUPPORTED == "supported"
    by_region = {r.region: r for r in detail.regions}
    assert detail.regions[0].region == "B"  # the best mean: 1.0 against 1.68 for A and C
    assert by_region["B"].fraction_taken == pytest.approx(0.25)  # y_B = 100 / 400
    assert by_region["A"].fraction_taken == 0.0 and by_region["C"].fraction_taken == 0.0
    assert by_region["A"].selected_cell_mw == 60.0 and by_region["C"].selected_cell_mw == 40.0
    assert by_region["A"].mean_z == pytest.approx((60 * 0.1 + 300 * 2.0) / 360)
    # both selections total T, the diagnostics are those of the example
    assert detail.x_cell @ _worked_example().q == pytest.approx(100.0)
    assert detail.x_admin @ _worked_example().q == pytest.approx(100.0)
    assert result.robustness_penalty == pytest.approx((100 * 1.0 - (100 * 0.1)) / 100)  # 0.9
    assert result.tv_distance == pytest.approx(1.0)  # shares (0.6, 0, 0.4) against (0, 1, 0)


def _overlap_042() -> H2Inputs:
    """The variant of the text: 42 MW of the selected capacity are common (state B is small enough to be taken whole)."""
    cells = (
        [("B", 1.0, 0.1)] * 42 + [("B", 1.0, 1.0)] * 58  # B: 100 MW, 42 of them top cells
        + [("A", 1.0, 0.1)] * 58 + [("A", 1.0, 2.0)] * 400  # A: 458 MW
        + [("C", 1.0, 2.0)] * 442  # C: 442 MW
    )  # fmt: skip
    return _inputs(cells)


@pytest.mark.unit
def test_with_042_common_capacity_h2_is_not_supported_at_gamma_030_and_supported_at_the_majority_benchmark():
    result, _ = _evaluate(_overlap_042())
    assert result.overlap == pytest.approx(0.42) and result.overlap_ref == pytest.approx(0.10)
    assert result.verdict == NOT_SUPPORTED == "not_supported"
    profile = {v.variant: v for v in decision_profile(result)}
    assert profile["gamma_0.50"].verdict == SUPPORTED  # the majority benchmark
    assert profile["gamma_0.30"].verdict == NOT_SUPPORTED
    assert result.smallest_supporting_gamma == pytest.approx(
        0.45
    )  # the smallest grid threshold above 0.42
    assert [v.gamma for v in profile.values()] == list(GAMMA_PROFILE) and len(GAMMA_PROFILE) == 13
    assert GAMMA_PROFILE[0] == 0.10 and GAMMA_PROFILE[-1] == 0.70


@pytest.mark.unit
def test_an_overlap_equal_to_gamma_does_not_support_h2_and_a_large_target_is_not_testable():
    assert verdict_of(0.30, 0.10, 0.30) == NOT_SUPPORTED  # the strict inequality
    assert verdict_of(0.2999, 0.10, 0.30) == SUPPORTED
    assert verdict_of(0.0, 0.30, 0.30) == NOT_TESTABLE  # O_ref = gamma is not informative
    result, _ = _evaluate(_worked_example(), top_k_percent=40.0)  # T / Q_max = 0.40
    assert result.overlap_ref == pytest.approx(0.40) and result.testable is False
    assert result.verdict == NOT_TESTABLE == "not_testable"
    assert smallest_supporting_gamma(0.0, 0.40) == 0.45  # the first grid threshold above both


@pytest.mark.unit
def test_the_robustness_penalty_is_never_negative():
    rng = np.random.default_rng(7)
    for trial in range(40):
        n = int(rng.integers(12, 60))
        regions = rng.choice(list("ABCDE"), size=n)
        cells = [
            (str(r), float(c), float(z))
            for r, c, z in zip(regions, rng.uniform(1, 30, n), rng.uniform(0, 3, n), strict=True)
        ]
        result, detail = _evaluate(_inputs(cells), top_k_percent=float(rng.choice([5, 10, 20, 30])))
        q = _inputs(cells).q
        assert result.robustness_penalty >= -1e-12, trial
        assert detail.x_cell @ q == pytest.approx(result.target_mw)  # both selections total T
        assert detail.x_admin @ q == pytest.approx(result.target_mw)
        assert 0.0 <= result.overlap <= 1.0 + 1e-12 and 0.0 <= result.tv_distance <= 1.0 + 1e-12


@pytest.mark.unit
def test_the_total_variation_distance_and_the_overlap_of_a_small_case_by_hand():
    # A: (1 MW, z 0.1) (1 MW, z 0.5); B: (1 MW, z 0.2) (1 MW, z 0.9). k = 2 of 4: the cell set is {A1, B1}, T = 2.
    # Region means: A 0.3, B 0.55; A is taken whole (2 MW), B not at all.
    inputs = _inputs([("A", 1, 0.1), ("A", 1, 0.5), ("B", 1, 0.2), ("B", 1, 0.9)])
    result, detail = _evaluate(inputs, top_k_percent=50.0)
    assert result.overlap == pytest.approx(0.5)  # only A1 is common: 1 MW of 2
    assert result.tv_distance == pytest.approx(0.5)  # shares (0.5, 0.5) against (1, 0)
    assert result.robustness_penalty == pytest.approx(((0.1 + 0.5) - (0.1 + 0.2)) / 2)  # 0.15
    assert result.overlap_ref == pytest.approx(0.5) and result.verdict == NOT_TESTABLE
    assert [r.region for r in detail.regions] == ["A", "B"]


@pytest.mark.unit
def test_the_last_region_enters_with_a_fraction_and_regions_without_capacity_do_not_enter():
    z = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
    q = np.array([10.0, 10.0, 20.0, 10.0, 0.0])
    region = np.array(["A", "A", "B", "C", "D"], dtype=object)
    ranked = np.ones(5, dtype=bool)
    x_cell, target, _ = select_cells(z, q, ranked, k=1)
    assert target == 10.0 and x_cell.tolist() == [1, 0, 0, 0, 0]
    x_admin, rows = select_regions(z, q, region, ranked, 30.0, x_cell)
    assert [r.region for r in rows] == ["A", "B", "C"]  # D has no capacity
    assert x_admin.tolist() == pytest.approx(
        [1.0, 1.0, 0.5, 0.0, 0.0]
    )  # A whole, B with 10 of its 20 MW
    with pytest.raises(H2Error):
        select_regions(z, q, region, ranked, 51.0, x_cell)


@pytest.mark.unit
def test_ties_between_regions_are_broken_by_region_identifier():
    z = np.array([1.0, 1.0])
    q = np.array([10.0, 10.0])
    region = np.array(["B", "A"], dtype=object)
    x_admin, rows = select_regions(z, q, region, np.ones(2, dtype=bool), 10.0, np.array([1.0, 0.0]))
    assert [r.region for r in rows] == ["A", "B"] and x_admin.tolist() == [0.0, 1.0]


@pytest.mark.unit
def test_a_national_target_takes_cells_with_a_fractional_last_cell_and_is_capped_at_the_candidate_capacity():
    z = np.array([0.3, 0.1, 0.2])
    q = np.array([10.0, 10.0, 10.0])
    ranked = np.ones(3, dtype=bool)
    x, target, unreachable = select_cells(z, q, ranked, target_mw=15.0)
    assert x.tolist() == pytest.approx([0.0, 1.0, 0.5]) and target == 15.0 and not unreachable
    x, target, unreachable = select_cells(z, q, ranked, target_mw=100.0)
    assert target == 30.0 and unreachable and x.tolist() == pytest.approx([1.0, 1.0, 1.0])
    with pytest.raises(H2Error):
        select_cells(z, q, ranked)  # neither a k nor a target
    result, _ = _evaluate(_worked_example(), target_mw=150.0, top_k_percent=None)
    assert result.target_mw == 150.0 and result.k is None and not result.target_unreachable


@pytest.mark.unit
def test_climate_fragile_cells_are_outside_the_ranked_set_and_an_empty_one_is_refused():
    cells = [("A", 10.0, 0.1), ("A", 10.0, 0.2), ("B", 10.0, 0.3), ("B", 10.0, 0.4)]
    result, detail = _evaluate(_inputs(cells, ranked=[False, True, True, True]), top_k_percent=50.0)
    assert (
        result.n_ranked == 3 and result.q_max_mw == 30.0
    )  # the fragile cell is neither ranked nor counted in Q_max
    assert detail.x_cell[0] == 0.0 and detail.x_admin[0] == 0.0
    with pytest.raises(H2Error, match="ranked set is empty"):
        _evaluate(_inputs(cells, ranked=[False] * 4))


@pytest.mark.unit
def test_the_median_variant_ranks_regions_by_the_capacity_weighted_median():
    # A: one cheap cell of 1 MW and a dear one of 9 MW: mean 0.91, weighted median 1.0; B: a steady 0.95.
    cells = [("A", 1.0, 0.0), ("A", 9.0, 1.0), ("B", 10.0, 0.95)]
    inputs = _inputs(cells)
    _, by_mean = _evaluate(inputs, top_k_percent=34.0)
    _, by_median = _evaluate(inputs, top_k_percent=34.0, statistic=MEDIAN)
    assert [r.region for r in by_mean.regions] == ["A", "B"]
    assert [r.region for r in by_median.regions] == ["B", "A"]


@pytest.mark.unit
def test_sensitivities_cover_the_profile_p_k_the_target_the_median_and_the_gcm_exception():
    cells = [(r, 1.0, 0.01 * i + 0.1 * j) for j, r in enumerate("ABCD") for i in range(25)]
    base = _inputs(cells)
    p90 = np.column_stack(
        [base.z, base.z + np.where(base.region == "A", 5.0, 0.0)]
    )  # the second GCM hurts region A
    inputs = H2Inputs(base.z, base.q, base.region, base.ranked, None, p90, ("GCM-A", "GCM-X"))
    primary, _ = _evaluate(inputs, gamma=0.30)
    variants = sensitivity_variants(
        inputs, primary, k=10, national_target_mw=20.0, tcr_exception_gcms=["GCM-X"]
    )
    names = [v.variant for v in variants]
    assert names[:13] == [f"gamma_{g:.2f}" for g in GAMMA_PROFILE]
    assert names[13:] == [
        "top_k_percent_5",
        "top_k_percent_10",
        "top_k_percent_20",
        "national_target",
        "median_statistic",
        "without_GCM-X",
    ]
    by = {v.variant: v for v in variants}
    assert [by[f"top_k_percent_{p}"].k for p in (5, 10, 20)] == [5, 10, 20]
    assert by["national_target"].target_mw == 20.0
    assert by["without_GCM-X"].excluded_gcms == ("GCM-X",)
    assert (
        by["gamma_0.30"].verdict == primary.verdict and by["gamma_0.30"].overlap == primary.overlap
    )
    assert (
        len(
            sensitivity_variants(
                inputs, primary, k=10, national_target_mw=None, tcr_exception_gcms=[]
            )
        )
        == 13 + 3 + 1
    )
