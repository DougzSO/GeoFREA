"""H3, robust versus nominal site selection, on hand-made cells (M-F7-07; thesis text docs/thesis/hypotheses/H3_robust_versus_nominal.tex)."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import spearmanr

from geofrea.robustness_analysis.h3_robust_vs_nominal import (
    NOT_SUPPORTED,
    NOT_TESTABLE,
    SUPPORTED,
    H3Error,
    H3Inputs,
    centroid_distance_km,
    evaluate_variant,
    sensitivity_variants,
    verdict_of,
)


def _inputs(
    cells: list[tuple[float, float, float]],
    *,
    ranked: list[bool] | None = None,
    region: list[str] | None = None,
    lat: list[float] | None = None,
    lon: list[float] | None = None,
    p90: np.ndarray | None = None,
    gcms: tuple[str, ...] = ("G",),
) -> H3Inputs:
    """`cells` are `(capacity MW, MR, LCOE at f0)`; with one member whose P90 is `MR` unless `p90` is given."""
    n = len(cells)
    z = np.array([c[1] for c in cells], dtype=float)
    mask = np.ones(n, dtype=bool) if ranked is None else np.array(ranked)
    return H3Inputs(
        cell_id=np.arange(n, dtype="int64"),
        z=np.where(mask, z, np.nan),
        lcoe=np.array([c[2] for c in cells], dtype=float),
        q=np.array([c[0] for c in cells], dtype=float),
        region=np.array(region or ["A"] * n, dtype=object),
        lat=np.array(lat or [0.0] * n, dtype=float),
        lon=np.array(lon or [0.0] * n, dtype=float),
        ranked=mask,
        sr=None,
        p90=z[:, None] if p90 is None else p90,
        gcms=gcms,
    )


def _evaluate(inputs: H3Inputs, **kwargs):
    settings = {
        "variant": "primary",
        "delta": 0.20,
        "tolerance_multiple": 1.0,
        "top_k_percent": 5.0,
    }
    return evaluate_variant(inputs, **{**settings, **kwargs})


def _worked_example() -> H3Inputs:
    """Section 8 of the thesis text: |I| = 1000, k = 50, m = 50, S_k of 500 MW with 300 MW in nominal ranks 1 to 50, 50 MW in 51 to 100
    and 150 MW beyond 100; the capacity-weighted LCOE is 40.8 for S_k and 40.0 for the nominal shortlist, the capacity-weighted MR 0.10 and
    0.25. Ties in a block are broken by position, which gives the nominal ranks below."""
    cells = (
        [(10.0, 0.10, 40.0)] * 30  # nominal ranks 1-30, in S_k
        + [(10.0, 0.475, 40.0)] * 20  # nominal ranks 31-50, not in S_k
        + [(10.0, 0.10, 42.0)] * 5  # nominal ranks 51-55, in S_k: inside the tolerance
        + [(1.0, 1.0, 42.0)] * 45  # nominal ranks 56-100, not in S_k
        + [(10.0, 0.10, 42.0)] * 15  # nominal ranks 101-115, in S_k: beyond the tolerance
        + [(1.0, 1.0, 42.0)] * 885
    )  # fmt: skip
    return _inputs(cells)


@pytest.mark.unit
def test_the_worked_example_of_the_thesis_text_gives_d_030_supported_pi_002_and_b_015():
    result, detail = _evaluate(_worked_example())
    assert (result.k, result.m, result.n_ranked) == (50, 50, 1000)
    assert result.robust_capacity_mw == 500.0 and result.nominal_capacity_mw == 500.0
    assert result.outside_capacity_mw == 150.0 and result.n_outside == 15
    assert result.d == pytest.approx(0.30)
    assert result.d_ref == pytest.approx(0.90)
    assert result.testable and result.verdict == SUPPORTED == "supported"
    assert result.robust_lcoe_mean == pytest.approx(40.8)
    assert result.nominal_lcoe_mean == pytest.approx(40.0)
    assert result.price_of_robustness == pytest.approx(0.02)
    assert result.robust_mr_mean == pytest.approx(0.10)
    assert result.nominal_mr_mean == pytest.approx(0.25)
    assert result.benefit_of_robustness == pytest.approx(0.15)
    # the three blocks of the example: 300 MW reached, 50 MW inside the tolerance (not counted), 150 MW beyond it
    assert detail.robust.sum() == 50 and detail.nominal.sum() == 50
    assert (detail.robust & detail.nominal).sum() == 30  # Jaccard 30 / 70
    assert result.jaccard == pytest.approx(30 / 70)
    assert detail.within_tolerance.sum() == 5 and detail.beyond.sum() == 15
    assert not (detail.within_tolerance & detail.beyond).any()


@pytest.mark.unit
def test_a_robust_cell_ranked_between_k_plus_1_and_k_plus_m_does_not_count():
    # 20 cells, k = 2 (10 percent), m = 2: S_k holds the two lowest MR; the nominal order is set by the LCOE
    def at_nominal_ranks(first: int, second: int):
        lcoe = np.arange(1.0, 21.0)  # the nominal rank of cell i is i + 1
        z = np.full(20, 5.0)
        z[first - 1], z[second - 1] = 0.1, 0.2
        return _inputs([(1.0, z[i], lcoe[i]) for i in range(20)])

    inside, _ = _evaluate(at_nominal_ranks(1, 4), top_k_percent=10.0)  # ranks 1 and k + m = 4
    assert (inside.k, inside.m) == (2, 2) and inside.d == 0.0
    edge, detail = _evaluate(
        at_nominal_ranks(1, 5), top_k_percent=10.0
    )  # rank k + m + 1 = 5 counts
    assert edge.d == pytest.approx(0.5) and detail.beyond.sum() == 1
    just_out, detail = _evaluate(
        at_nominal_ranks(3, 4), top_k_percent=10.0
    )  # ranks 3 and 4: not counted
    assert just_out.d == 0.0 and detail.within_tolerance.sum() == 2
    assert just_out.verdict == NOT_SUPPORTED


@pytest.mark.unit
def test_when_the_reference_is_below_delta_h3_is_not_testable():
    cells = [(1.0, float(i), float(10 - i)) for i in range(10)]  # the rankings are opposite
    result, _ = _evaluate(_inputs(cells), top_k_percent=50.0)  # k = 5, m = 5, D_ref = 0
    assert result.d_ref == 0.0 and not result.testable and result.verdict == NOT_TESTABLE
    assert result.d == 0.0  # D is still reported: no rank of 10 cells exceeds k + m = 10
    assert verdict_of(0.9, 0.19, 0.20) == NOT_TESTABLE
    assert verdict_of(0.20, 0.20, 0.20) == SUPPORTED  # D = delta is supported
    assert verdict_of(0.1999, 0.90, 0.20) == NOT_SUPPORTED


@pytest.mark.unit
def test_nominal_and_robust_rankings_that_coincide_give_d_zero_not_supported():
    cells = [(1.0 + i % 3, 0.1 * i, 30.0 + i) for i in range(40)]  # MR and LCOE increase together
    result, detail = _evaluate(_inputs(cells), top_k_percent=10.0)
    assert result.k == 4 and result.d == 0.0 and result.verdict == NOT_SUPPORTED
    assert result.testable and result.d_ref == pytest.approx(1 - 8 / 40)
    assert (detail.robust == detail.nominal).all() and result.jaccard == 1.0
    assert result.price_of_robustness == pytest.approx(0.0)
    assert result.benefit_of_robustness == pytest.approx(0.0)
    assert result.centroid_distance_km == pytest.approx(0.0)
    assert result.tv_distance == pytest.approx(0.0)
    assert result.spearman_lcoe_mr == pytest.approx(1.0)


@pytest.mark.unit
def test_both_rankings_are_over_the_ranked_set_and_k_comes_from_the_f7_set():
    # cell 0 has the lowest LCOE but is climate-fragile: it is outside I, so it is no nominal rank and no shortlist cell
    cells = [(1.0, 0.0, 1.0)] + [(1.0, 0.1 * i, 2.0 + i) for i in range(1, 10)]
    result, detail = _evaluate(_inputs(cells, ranked=[False] + [True] * 9), top_k_percent=20.0)
    assert result.n_cells == 10 and result.n_ranked == 9
    assert result.k == 2 and result.m == 2  # k = ceil(0.2 * 10): the size of the F7 set
    assert result.d_ref == pytest.approx(1 - 4 / 9)  # |I| = 9
    assert detail.nominal_rank[0] == 0 and detail.robust_rank[0] == 0
    assert not detail.robust[0] and not detail.nominal[0]
    assert list(np.flatnonzero(detail.nominal)) == [1, 2]
    with pytest.raises(H3Error, match="ranked set is empty"):
        _evaluate(_inputs(cells, ranked=[False] * 10))


@pytest.mark.unit
def test_the_statistic_is_capacity_weighted_and_equal_ties_follow_the_cell_order():
    # the robust shortlist is cells 0 and 1 (MR 0.1 and 0.2); cell 0 (1 MW) is nominal rank 1, cell 1 (9 MW) is nominal rank 5
    lcoe = [1.0, 5.0, 2.0, 3.0, 4.0] + [10.0] * 15
    z = [0.1, 0.2] + [1.0] * 18
    q = [1.0, 9.0] + [1.0] * 18
    result, detail = _evaluate(
        _inputs([(q[i], z[i], lcoe[i]) for i in range(20)]), top_k_percent=10.0
    )
    assert (result.k, result.m) == (2, 2)
    assert result.d == pytest.approx(0.9)  # 9 of the 10 MW, not 1 of the 2 cells
    # nominal ties (cells 5 to 19 share LCOE 10) are ranked by position
    assert list(detail.nominal_rank[5:8]) == [6, 7, 8]


@pytest.mark.unit
def test_a_larger_tolerance_never_counts_more_capacity_and_d_stays_in_the_unit_interval():
    rng = np.random.default_rng(7)
    for _ in range(20):
        n = 200
        cells = [
            (float(rng.uniform(1, 10)), float(rng.uniform(0, 1)), float(rng.uniform(30, 60)))
            for _ in range(n)
        ]
        inputs = _inputs(cells)
        previous = 1.0
        for multiple in (0.5, 1.0, 2.0):
            result, _ = _evaluate(inputs, tolerance_multiple=multiple, top_k_percent=10.0)
            assert 0.0 <= result.d <= previous + 1e-12
            previous = result.d
            assert result.d_ref == pytest.approx(1 - (result.k + result.m) / n)
            assert result.benefit_of_robustness is not None
            assert (
                result.benefit_of_robustness >= -1e-12
            )  # S_k is the lowest-MR set, so B is at least 0 up to capacity weights


@pytest.mark.unit
def test_diagnostics_by_hand_distance_total_variation_and_spearman():
    # two regions; S_k = cells 0 and 1, S^nom_k = cells 2 and 3 (k = 2 of 20 cells, 10 percent)
    cells = [(1.0, 0.1, 9.0), (1.0, 0.2, 9.5), (1.0, 0.8, 1.0), (1.0, 0.9, 2.0)] + [
        (1.0, 1.0 + i, 10.0 + i) for i in range(16)
    ]
    inputs = _inputs(
        cells,
        region=["A", "A", "B", "A"] + ["C"] * 16,
        lat=[0.0, 0.0, 0.0, 0.0] + [0.0] * 16,
        lon=[0.0, 2.0, 1.0, 1.0] + [0.0] * 16,
    )
    result, _ = _evaluate(inputs, top_k_percent=10.0)
    # centroids: robust at lon 1.0, nominal at lon 1.0: distance 0 along the equator
    assert result.centroid_distance_km == pytest.approx(0.0, abs=1e-6)
    # shares by region: S_k = (A 1.0), S^nom_k = (B 0.5, A 0.5): TV = 0.5 * (0.5 + 0.5) = 0.5
    assert result.tv_distance == pytest.approx(0.5)
    shifted = _inputs(cells, lon=[0.0, 0.0, 1.0, 1.0] + [0.0] * 16)
    far, _ = _evaluate(shifted, top_k_percent=10.0)
    assert far.centroid_distance_km == pytest.approx(111.319, abs=0.05)  # one degree on the equator
    mr = np.array([c[1] for c in cells])
    cost = np.array([c[2] for c in cells])
    assert far.spearman_lcoe_mr == pytest.approx(spearmanr(cost, mr).statistic)
    constant, _ = _evaluate(_inputs([(1.0, 0.5, 1.0 + i) for i in range(20)]), top_k_percent=10.0)
    assert constant.spearman_lcoe_mr is None  # MR is constant: no correlation


@pytest.mark.unit
def test_centroid_distance_is_none_for_a_set_without_capacity():
    lat = lon = np.zeros(3)
    weight = np.array([1.0, 1.0, 0.0])
    one = np.array([True, False, False])
    empty = np.array([False, False, True])
    assert centroid_distance_km(lat, lon, weight, one, empty) is None
    assert centroid_distance_km(lat, lon, weight, one, np.zeros(3, dtype=bool)) is None


@pytest.mark.unit
def test_the_sensitivities_are_p_k_and_m_and_the_tcr_gcm_and_leave_the_primary_alone():
    rng = np.random.default_rng(3)
    n = 100
    p90 = rng.uniform(0, 1, (n, 3))
    cells = [
        (float(rng.uniform(1, 5)), float(p90[i].max()), float(rng.uniform(30, 50)))
        for i in range(n)
    ]
    inputs = _inputs(cells, p90=p90, gcms=("A", "B", "B"))
    primary, _ = _evaluate(inputs, top_k_percent=10.0)
    variants = sensitivity_variants(inputs, primary, tcr_exception_gcms=["B", "NOT_A_MEMBER"])
    assert [v.variant for v in variants] == [
        "without_B",
        "top_k_percent_5",
        "top_k_percent_10",
        "top_k_percent_20",
        "tolerance_0.5k",
        "tolerance_2k",
    ]
    by_name = {v.variant: v for v in variants}
    assert by_name["top_k_percent_10"].d == pytest.approx(primary.d)  # the primary p_k again
    assert by_name["top_k_percent_5"].k == 5 and by_name["top_k_percent_20"].k == 20
    assert by_name["tolerance_0.5k"].m == 5 and by_name["tolerance_2k"].m == 20
    assert by_name["without_B"].excluded_gcms == ("B",)
    # MR without B is the maximum over member A alone
    _, detail = _evaluate(inputs, top_k_percent=10.0, exclude_gcms=["B"])
    assert np.allclose(detail.z, p90[:, 0])
    assert (
        sensitivity_variants(inputs, primary, tcr_exception_gcms=[])[0].variant == "top_k_percent_5"
    )
    with pytest.raises(H3Error, match="no member is left"):
        _evaluate(inputs, exclude_gcms=["A", "B"])
