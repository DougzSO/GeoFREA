"""Rankings, ties, top-k sizes, truncation and the capacity target; the classes of the candidates (M-F7-01, M-F7-05; D-F7-012, D-F7-013)."""

from __future__ import annotations

import numpy as np
import pytest

from geofrea.lcoe_modeling.inputs import MemberCells
from geofrea.lcoe_modeling.kernel import CellInputs
from geofrea.robustness_analysis.cell_set import (
    CLIMATE_DATA_INVALID,
    CLIMATE_FRAGILE,
    INFEASIBLE_AT_F0,
    RANKED,
    CellSetError,
    build_cell_set,
)
from geofrea.robustness_analysis.rankings import (
    RankingError,
    capacity_target_set,
    jaccard_masks,
    order_by,
    ranks_from_order,
    take_top_k,
    top_k_size,
)

# -- ordering -------------------------------------------------------------------------------------------------


@pytest.mark.unit
def test_exact_ties_go_to_the_higher_sr_then_to_the_smaller_index():
    mr = np.array([0.5, 0.2, 0.2, 0.2, 0.9])
    sr = np.array([0.1, 0.4, 0.8, 0.8, 0.0])
    order = order_by(mr, descending_tiebreak=sr)
    assert order.tolist() == [
        2,
        3,
        1,
        0,
        4,
    ]  # 2 and 3 tie on both keys: the smaller index (cell_id) first
    assert order_by(mr).tolist() == [1, 2, 3, 0, 4]  # without SR the ties go by index


@pytest.mark.unit
def test_no_tolerance_a_difference_in_the_last_bit_is_a_difference():
    a = np.array([1.0 + 2.0**-52, 1.0])
    assert order_by(a).tolist() == [1, 0]


@pytest.mark.unit
def test_cells_outside_the_candidate_mask_are_left_out_and_a_nan_key_is_refused():
    mr = np.array([0.3, np.nan, 0.1, 0.2])
    mask = np.array([True, False, True, True])
    order = order_by(mr, candidates=mask)
    assert order.tolist() == [2, 3, 0]
    assert ranks_from_order(order, 4).tolist() == [3, 0, 1, 2]
    with pytest.raises(RankingError, match="NaN"):
        order_by(mr)


# -- top-k --------------------------------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("percent", "n", "k"),
    [(25, 17, 5), (25, 16, 4), (10, 3, 1), (100, 7, 7), (0.1, 5, 1), (5, 172250, 8613)],
)
def test_k_is_the_ceiling_of_p_k_percent_of_the_set_and_at_least_one(percent, n, k):
    assert top_k_size(percent, n) == k


@pytest.mark.unit
def test_a_bad_p_k_or_an_empty_set_is_refused():
    for bad in (0, -5, 100.01):
        with pytest.raises(RankingError):
            top_k_size(bad, 10)
    with pytest.raises(RankingError, match="empty"):
        top_k_size(10, 0)


@pytest.mark.unit
def test_a_top_k_larger_than_the_ranked_set_is_the_whole_set_and_flagged():
    order = np.array([4, 1, 3])
    top = take_top_k(order, 5, 6)
    assert top.truncated and top.size == 3 and top.k == 5
    assert np.flatnonzero(top.mask).tolist() == [1, 3, 4]
    full = take_top_k(order, 2, 6)
    assert not full.truncated and np.flatnonzero(full.mask).tolist() == [1, 4]


# -- the capacity target ------------------------------------------------------------------------------------


@pytest.mark.unit
def test_the_capacity_target_takes_the_fewest_cells_along_the_order():
    p_mw = np.array([100.0, 300.0, 200.0, 400.0])
    order = np.array([2, 0, 3, 1])  # 200, 100, 400, 300 MW
    mask, reached = capacity_target_set(order, p_mw, 0.3)  # 300 MW is met exactly by the first two
    assert reached and np.flatnonzero(mask).tolist() == [0, 2]
    mask, reached = capacity_target_set(order, p_mw, 0.301)
    assert reached and np.flatnonzero(mask).tolist() == [0, 2, 3]
    mask, reached = capacity_target_set(order, p_mw, 5.0)
    assert not reached and mask.all()  # target above the ranked capacity: all of it, flagged
    mask, reached = capacity_target_set(order, p_mw, 0.0)
    assert reached and not mask.any()
    with pytest.raises(RankingError):
        capacity_target_set(order, p_mw, -1.0)


@pytest.mark.unit
def test_jaccard_of_masks():
    a = np.array([True, True, False, False])
    b = np.array([False, True, True, False])
    assert jaccard_masks(a, b) == pytest.approx(1 / 3)
    empty = np.zeros(3, dtype=bool)
    assert jaccard_masks(a, a) == 1.0 and jaccard_masks(empty, empty) == 1.0


# -- the classes of the candidates --------------------------------------------------------------------------


def _member(name, ids, cf):
    ids = np.asarray(ids, dtype="int64")
    cf = np.asarray(cf, dtype="float64")
    n = len(ids)
    p = np.full(n, 100.0)
    cells = CellInputs(
        p_mw=p,
        dist_grid_km=np.zeros(n),
        dist_road_km=np.zeros(n),
        energy_mwh=p * cf * 8760.0,
        energy_offset=np.ones(n),
        energy_slope=np.zeros(n),
    )
    return name, MemberCells(member=name, cell_id=ids, cells=cells, cf=cf)


@pytest.mark.unit
def test_the_four_classes_follow_the_definitions_of_m_f7_01():
    ids = [1, 2, 3, 4, 5]
    members = dict(
        [
            _member("m0", ids, [0.3, 0.3, 0.1, 0.3, 0.3]),  # cell 3 is below CF_min at f0
            _member(
                "a", [1, 2, 3, 5], [0.3, 0.2, 0.3, 0.3]
            ),  # cell 4 is masked here; cell 2 fails CF_min
            _member("b", ids, [0.3, 0.3, 0.3, 0.3, 0.25]),  # cell 5 is exactly at CF_min: feasible
        ]
    )
    cells = build_cell_set(np.array(ids), members, "m0", ["a", "b"], cf_min=0.25)
    classes = dict(zip(cells.candidate_ids.tolist(), cells.classes.tolist(), strict=True))
    assert classes == {
        1: RANKED,
        2: CLIMATE_FRAGILE,
        3: INFEASIBLE_AT_F0,
        4: CLIMATE_DATA_INVALID,
        5: RANKED,
    }
    assert cells.f7_ids.tolist() == [1, 2, 5] and cells.n_f7 == 3
    assert cells.fragile.tolist() == [False, True, False] and cells.ranked.tolist() == [
        True,
        False,
        True,
    ]
    assert cells.failing_members() == [[], ["a"], []]
    assert cells.counts() == {
        RANKED: 2,
        CLIMATE_FRAGILE: 1,
        CLIMATE_DATA_INVALID: 1,
        INFEASIBLE_AT_F0: 1,
    }
    # the floor handed to the kernel: +inf where the member fails CF_min, 0 elsewhere (D-F7-007)
    assert cells.core[0].floor.tolist() == [0.0, np.inf, 0.0] and (cells.core[1].floor == 0).all()
    assert (cells.reference.floor == 0).all()
    assert cells.p_mw.tolist() == [100.0, 100.0, 100.0]


@pytest.mark.unit
def test_a_member_without_rows_makes_every_cell_climate_data_invalid_and_bad_inputs_are_refused():
    ids = [1, 2]
    members = dict([_member("m0", ids, [0.3, 0.3])])
    cells = build_cell_set(np.array(ids), members, "m0", ["missing"], cf_min=0.1)
    assert cells.n_f7 == 0 and set(cells.classes.tolist()) == {CLIMATE_DATA_INVALID}
    with pytest.raises(CellSetError, match="reference"):
        build_cell_set(np.array(ids), {}, "m0", [], cf_min=0.1)
    with pytest.raises(CellSetError, match="twice"):
        build_cell_set(np.array(ids), members, "m0", ["a", "a"], cf_min=0.1)
    with pytest.raises(CellSetError, match="not candidates"):
        build_cell_set(np.array([1]), members, "m0", [], cf_min=0.1)
