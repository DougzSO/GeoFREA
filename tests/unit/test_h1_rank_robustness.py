"""H1, climate robustness of the site ranking, on hand-made scores (M-F7-07; thesis text docs/thesis/hypotheses/H1_climate_rank_robustness.tex)."""

from __future__ import annotations

import numpy as np
import pytest

from geofrea.robustness_analysis.h1_rank_robustness import (
    NOT_SUPPORTED,
    PARTIALLY_SUPPORTED,
    SUPPORTED,
    H1Error,
    H1Inputs,
    descriptive,
    evaluate_variant,
    rbo,
    sensitivity_variants,
    tolerance_size,
    verdict_of,
)

SSPS = ("SSP1-2.6", "SSP3-7.0", "SSP5-8.5")


def _inputs(
    n: int,
    top_sets: list[list[int]],
    climate_orders: list[list[int]],
    *,
    ranked: np.ndarray | None = None,
    gcms: tuple[str, ...] | None = None,
) -> H1Inputs:
    """One member per SSP. Cell `i` has nominal rank `i + 1`. `top_sets[s]` are the cells that `MR` puts first in SSP `s`, in that order,
    the others follow by index; `climate_orders[s]` is the full climate-only ranking (cells in rank order) of SSP `s`."""
    p90 = np.empty((n, len(top_sets)))
    r_clim = np.empty((n, len(top_sets)))
    for s, top in enumerate(top_sets):
        rest = [i for i in range(n) if i not in set(top)]
        for position, cell in enumerate([*top, *rest]):
            p90[cell, s] = position * 1.0e-3
    for s, order in enumerate(climate_orders):
        assert sorted(order) == list(range(n))
        for position, cell in enumerate(order):
            r_clim[cell, s] = position * 1.0e-3
    members = len(top_sets)
    return H1Inputs(
        p90=p90,
        r_clim=r_clim,
        ssps=SSPS[:members],
        gcms=gcms or ("G",) * members,
        ranked=np.ones(n, dtype=bool) if ranked is None else ranked,
        nominal_order=np.arange(n),
        nominal_rank=np.arange(1, n + 1),
    )


def _move(order: list[int], cell: int, rank: int) -> None:
    """Put `cell` at 1-based `rank` of `order`, in place."""
    order.remove(cell)
    order.insert(rank - 1, cell)


def _worked_example() -> H1Inputs:
    """Section 9 of the thesis text: N = 1000, p_k = 0.05 (k = 50), m = 50; 36 cells in all three top-50 sets; 11 vulnerable nominal sites."""
    n = 1000
    shared = list(range(36))
    tops = [
        shared + list(range(100, 114)),
        shared + list(range(200, 214)),
        shared + list(range(300, 314)),
    ]
    orders = [list(range(n)) for _ in SSPS]
    _move(
        orders[2], 4, 78
    )  # the site ranked 5th falls to 78 in SSP5-8.5: inside k + m = 100, not vulnerable
    _move(orders[1], 11, 340)  # the site ranked 12th falls to 340 in SSP3-7.0: vulnerable
    for cell in range(20, 30):  # ten more nominal sites leave the top 100 in SSP1-2.6
        _move(orders[0], cell, 500 + cell)
    return _inputs(n, tops, orders)


def _evaluate(inputs: H1Inputs, **kwargs):
    settings = {
        "variant": "primary",
        "top_k_percent": 5.0,
        "tolerance_multiple": 1.0,
        "alpha": 0.60,
        "beta": 0.20,
    }
    return evaluate_variant(inputs, **{**settings, **kwargs})


@pytest.mark.unit
def test_the_worked_example_of_the_thesis_text_gives_c_072_v_022_and_supported():
    result, detail = _evaluate(_worked_example())
    assert (result.k, result.m, result.n_cells) == (50, 50, 1000)
    assert result.core_size == 36 and result.c_k == pytest.approx(0.72)
    assert result.n_vulnerable == 11 and result.v_k == pytest.approx(0.22)
    assert result.reference == pytest.approx(0.0025)  # "about 0.0025" under independence
    assert result.h1a_holds and result.h1b_holds
    assert result.verdict == SUPPORTED == "supported"
    # the two sites of the example
    ssps = detail.scores.ssps
    assert not detail.vulnerable[4] and detail.displacement[4] == 78 - 5
    assert ssps[detail.worst_ssp[4]] == "SSP5-8.5"
    assert detail.vulnerable[11] and detail.displacement[11] == 340 - 12
    assert ssps[detail.worst_ssp[11]] == "SSP3-7.0"
    assert set(np.flatnonzero(detail.vulnerable)) == {11, *range(20, 30)}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("core_shared", "vulnerable", "h1a", "h1b", "verdict"),
    [
        (True, False, True, False, PARTIALLY_SUPPORTED),
        (False, True, False, True, PARTIALLY_SUPPORTED),
        (True, True, True, True, SUPPORTED),
        (False, False, False, False, NOT_SUPPORTED),
    ],
)
def test_h1a_and_h1b_are_independent_and_all_four_combinations_occur(
    core_shared, vulnerable, h1a, h1b, verdict
):
    n = 100  # k = 10 at 10 percent, m = 10
    tops = [list(range(10))] + (
        [list(range(10))] * 2 if core_shared else [list(range(10, 20)), list(range(20, 30))]
    )
    orders = [list(range(n)) for _ in SSPS]
    if vulnerable:
        for cell in (0, 1, 2):  # three of the ten nominal sites leave the top 20: V = 0.3 >= 0.2
            _move(orders[0], cell, 50)
    result, _ = _evaluate(_inputs(n, tops, orders), top_k_percent=10.0)
    assert result.c_k == (1.0 if core_shared else 0.0)
    assert result.v_k == (0.3 if vulnerable else 0.0)
    assert (result.h1a_holds, result.h1b_holds, result.verdict) == (h1a, h1b, verdict)


@pytest.mark.unit
def test_the_verdict_function_covers_the_three_outcomes():
    assert verdict_of(True, True) == SUPPORTED
    assert verdict_of(True, False) == verdict_of(False, True) == PARTIALLY_SUPPORTED
    assert verdict_of(False, False) == NOT_SUPPORTED


@pytest.mark.unit
def test_a_site_at_exactly_k_plus_m_is_not_vulnerable_and_one_place_beyond_is():
    n = 100
    orders = [list(range(n)) for _ in SSPS]
    _move(orders[0], 0, 20)  # k + m = 20
    _move(orders[1], 1, 21)
    result, detail = _evaluate(_inputs(n, [list(range(10))] * 3, orders), top_k_percent=10.0)
    assert not detail.vulnerable[0] and detail.vulnerable[1] and result.n_vulnerable == 1


@pytest.mark.unit
def test_the_tolerance_is_a_multiple_of_k():
    assert [tolerance_size(x, 50) for x in (0.5, 1.0, 2.0)] == [25, 50, 100]
    assert tolerance_size(0.5, 1) == 1


@pytest.mark.unit
def test_a_climate_fragile_cell_has_no_rank_and_a_fragile_nominal_top_k_cell_is_vulnerable():
    n = 100
    ranked = np.ones(n, dtype=bool)
    ranked[3] = False  # climate-fragile: in the nominal top-k, not ranked by any climate score
    orders = [list(range(n)) for _ in SSPS]
    tops = [[i for i in range(10) if i != 3]] * 3
    result, detail = _evaluate(_inputs(n, tops, orders, ranked=ranked), top_k_percent=10.0)
    assert detail.vulnerable[3] and np.isnan(detail.displacement[3])
    assert detail.mr_rank[:, 3].tolist() == [0, 0, 0] and not detail.top_k[:, 3].any()
    assert result.n_vulnerable == 1 and result.n_ranked == 99
    assert result.v_k == pytest.approx(0.1)


@pytest.mark.unit
def test_an_empty_ranked_set_and_a_single_ssp_are_refused():
    n = 20
    orders = [list(range(n)) for _ in SSPS]
    inputs = _inputs(n, [list(range(5))] * 3, orders, ranked=np.zeros(n, dtype=bool))
    with pytest.raises(H1Error, match="ranked set is empty"):
        _evaluate(inputs, top_k_percent=25.0)
    one = _inputs(n, [list(range(5))], orders[:1])
    with pytest.raises(H1Error, match="SSPs"):
        _evaluate(one, top_k_percent=25.0)


# -- rank-biased overlap ---------------------------------------------------------------------------------------


def _rbo_direct(a: list[int], b: list[int], p: float) -> float:
    total = 0.0
    for d in range(1, len(a) + 1):
        agreement = len(set(a[:d]) & set(b[:d])) / d
        total += (1.0 - p) * p ** (d - 1) * agreement
    return total


@pytest.mark.unit
def test_rbo_with_p_one_minus_one_over_k_matches_the_direct_sum_on_a_small_list():
    a = [0, 1, 2, 3, 4, 5, 6, 7]
    b = [1, 0, 3, 2, 7, 4, 5, 6]
    for k in (1, 2, 3, 5):
        p = 1.0 - 1.0 / k
        value, residual = rbo(np.array(a), np.array(b), p)
        assert value == pytest.approx(_rbo_direct(a, b, p), abs=1e-12)
        assert residual == pytest.approx(p ** len(a))


@pytest.mark.unit
def test_rbo_of_a_ranking_with_itself_is_one_minus_the_residual_and_disjoint_prefixes_lower_it():
    order = np.arange(10)
    value, residual = rbo(order, order, 0.75)
    assert value + residual == pytest.approx(1.0)
    reversed_value, _ = rbo(order, order[::-1], 0.75)
    assert reversed_value < value
    first, _ = rbo(
        np.array([0, 1]), np.array([1, 0]), 0.0
    )  # p = 0 (k = 1): only the first position counts
    assert first == 0.0


@pytest.mark.unit
def test_rbo_refuses_lists_of_different_cells_and_a_persistence_outside_the_range():
    with pytest.raises(H1Error):
        rbo(np.array([0, 1]), np.array([0, 2]), 0.5)
    with pytest.raises(H1Error):
        rbo(np.array([0, 1]), np.array([1, 0]), 1.0)


# -- descriptive evidence and sensitivities --------------------------------------------------------------------


@pytest.mark.unit
def test_the_descriptive_metrics_use_p_one_minus_one_over_k_and_do_not_depend_on_the_thresholds():
    inputs = _worked_example()
    primary, detail = _evaluate(inputs)
    stricter, _ = _evaluate(inputs, alpha=0.99, beta=0.99)
    d = descriptive(inputs, primary, detail)
    assert d.rbo_p == pytest.approx(1.0 - 1.0 / 50)
    assert [(a, b) for a, b, *_ in d.pairs] == [
        (SSPS[0], SSPS[1]),
        (SSPS[0], SSPS[2]),
        (SSPS[1], SSPS[2]),
    ]
    jaccard = d.pairs[0][2]
    assert jaccard == pytest.approx(36 / 64)  # |S ∩ S'| = 36, |S ∪ S'| = 64
    assert all(0 < value < 1 for _, _, _, value, _ in d.pairs)
    assert d.displacement_median is not None and d.n_sites_with_rank == 50
    assert (
        stricter.verdict == NOT_SUPPORTED and stricter.c_k == primary.c_k
    )  # thresholds move the verdict only


def _two_gcms(n: int, top: list[int], orders: list[list[int]], names=("GCM-A", "GCM-B")):
    """Six members: the same scores under two GCMs, each with the three SSPs."""
    a = _inputs(n, [top] * 3, orders, gcms=(names[0],) * 3)
    b = _inputs(n, [top] * 3, orders, gcms=(names[1],) * 3)
    return (
        a,
        b,
        H1Inputs(
            p90=np.hstack([a.p90, b.p90]),
            r_clim=np.hstack([a.r_clim, b.r_clim]),
            ssps=a.ssps + b.ssps,
            gcms=a.gcms + b.gcms,
            ranked=a.ranked,
            nominal_order=a.nominal_order,
            nominal_rank=a.nominal_rank,
        ),
    )


@pytest.mark.unit
def test_sensitivities_cover_the_gcm_exception_p_k_and_m_and_leave_the_primary_alone():
    n = 200
    orders = [list(range(n)) for _ in SSPS]
    _, _, inputs = _two_gcms(n, list(range(20)), orders)
    primary, _ = _evaluate(inputs, top_k_percent=10.0)
    variants = sensitivity_variants(
        inputs, top_k_percent=10.0, tolerance_multiple=1.0, alpha=0.60, beta=0.20,
        tcr_exception_gcms=["GCM-B", "GCM-X"],
    )  # fmt: skip
    assert [v.variant for v in variants] == [
        "without_GCM-B",
        "top_k_percent_5",
        "top_k_percent_10",
        "top_k_percent_20",
        "tolerance_0.5k",
        "tolerance_1k",
        "tolerance_2k",
    ]
    by = {v.variant: v for v in variants}
    assert by["without_GCM-B"].excluded_gcms == ("GCM-B",)
    assert [by[f"top_k_percent_{p}"].k for p in (5, 10, 20)] == [10, 20, 40]
    assert [by[f"tolerance_{x}k"].m for x in ("0.5", "1", "2")] == [10, 20, 40]
    assert by["top_k_percent_10"].c_k == primary.c_k and by["tolerance_1k"].v_k == primary.v_k
    none = sensitivity_variants(
        inputs, top_k_percent=10.0, tolerance_multiple=1.0, alpha=0.60, beta=0.20,
        tcr_exception_gcms=[],
    )  # fmt: skip
    assert (
        len(none) == 6
    )  # no exception GCM among the members: that variant would equal the primary one


@pytest.mark.unit
def test_dropping_a_gcm_changes_the_scores_of_the_remaining_members_and_an_empty_ssp_is_refused():
    n = 60
    orders = [list(range(n)) for _ in SSPS]
    a = _inputs(n, [list(range(6))] * 3, orders, gcms=("A",) * 3)
    b = _inputs(n, [list(range(6))] * 3, orders, gcms=("B",) * 3)
    worse = a.p90.copy()
    worse[:6, 0] += (
        10.0  # GCM A, SSP1-2.6: the six nominal best cells are the worst case of the SSP
    )
    both = H1Inputs(
        p90=np.hstack([worse, b.p90]),
        r_clim=np.hstack([a.r_clim, b.r_clim]),
        ssps=a.ssps + b.ssps,
        gcms=a.gcms + b.gcms,
        ranked=a.ranked,
        nominal_order=a.nominal_order,
        nominal_rank=a.nominal_rank,
    )
    with_a, _ = _evaluate(both, top_k_percent=10.0)
    without_a, _ = _evaluate(both, top_k_percent=10.0, exclude_gcms=("A",), variant="x")
    assert with_a.core_size == 0  # SSP1-2.6 has none of the cells of the other SSPs in its top-6
    assert without_a.core_size == 6 and without_a.c_k == 1.0
    with pytest.raises(H1Error, match="no member"):
        _evaluate(both, top_k_percent=10.0, exclude_gcms=("A", "B"))
