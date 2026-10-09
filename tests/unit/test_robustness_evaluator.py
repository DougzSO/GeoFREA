"""The two-pass evaluator against brute-force definitions on small worlds (M-F7-02 to M-F7-04, M-F7-06, V-02, V-03, A-10)."""

from __future__ import annotations

import tracemalloc

import numpy as np
import pytest

from geofrea.lcoe_modeling.kernel import CellInputs, SampleInputs, lcoe_block, lcoe_direct
from geofrea.robustness_analysis.evaluator import (
    EvaluationError,
    MemberWorld,
    evaluate,
    reference_levels,
)

N_DRAWS = 40


def _cells(rng, n, shift=0.0):
    p = rng.uniform(20.0, 300.0, n)
    cf = rng.uniform(0.15, 0.45, n) * (1.0 - shift)
    return CellInputs(
        p_mw=p,
        dist_grid_km=rng.uniform(0.0, 120.0, n),
        dist_road_km=rng.uniform(0.0, 30.0, n),
        energy_mwh=p * cf * 8760.0,
        energy_offset=np.full(n, 1.0),
        energy_slope=np.zeros(n),
    )


def _samples(rng, n_draws=N_DRAWS):
    n = n_draws + 1

    def column(low, high):
        v = rng.uniform(low, high, n)
        v[0] = (low + high) / 2.0
        return v

    life = np.round(column(15, 25))
    return SampleInputs(
        capex_usd_per_kw=column(800, 1200),
        opex_fixed_frac=column(0.03, 0.07),
        opex_var_usd_per_mwh=np.full(n, 2.0),
        lifetime_years=life,
        discount_rate=column(0.03, 0.08),
        degradation_rate=column(0.0, 0.01),
        grid_cost_usd_per_mw_km=column(500, 1500),
        substation_cost_usd_per_mw=column(1e4, 3e4),
        road_cost_usd_per_km=column(2.5e4, 7.5e4),
        energy_parameter=np.full(n, 0.9),
    )


def _world(rng, n_cells=60, n_core=3, fails=None):
    """The reference member and `n_core` members that scale the reference energy; `fails` is {member index: [cells below CF_min]}."""
    base = _cells(rng, n_cells)
    worlds = []
    for j in range(n_core):
        scale = 1.0 - 0.05 * j
        cells = CellInputs(
            p_mw=base.p_mw,
            dist_grid_km=base.dist_grid_km,
            dist_road_km=base.dist_road_km,
            energy_mwh=base.energy_mwh * scale,
            energy_offset=base.energy_offset,
            energy_slope=base.energy_slope,
        )
        floor = np.zeros(n_cells)
        floor[list((fails or {}).get(j, []))] = np.inf
        worlds.append(MemberWorld(member=f"m{j + 1}", cells=cells, floor=floor))
    reference = MemberWorld(member="m0", cells=base, floor=np.zeros(n_cells))
    return reference, worlds


def _brute_force(reference, worlds, samples, tau):
    """MR, SR, MR_clim, MR_tech and the variance parts from the definitions, one future at a time, with the kernel's textbook form."""
    stacks = {}
    for w in [reference, *worlds]:
        block = lcoe_direct(w.cells, samples)
        block[np.isposinf(w.floor), :] = np.inf
        stacks[w.member] = block
    n_cells = len(reference.cells)
    r = {}
    for member, block in stacks.items():
        low = block.min(axis=0)
        high = np.where(np.isfinite(block), block, -np.inf).max(axis=0)
        out = (block - low) / low
        out = np.where(np.isfinite(block), out, ((high - low) / low)[None, :])
        r[member] = out
    mr = np.max([np.quantile(r[w.member][:, 1:], 0.9, axis=1) for w in worlds], axis=0)
    mr_clim = np.max([r[w.member][:, 0] for w in worlds], axis=0)
    mr_tech = np.quantile(r[reference.member][:, 1:], 0.9, axis=1)
    sr = None
    if tau is not None:
        sr = np.mean(
            [
                (stacks[w.member][:, 1:] <= tau) & np.isfinite(stacks[w.member][:, 1:])
                for w in worlds
            ],
            axis=(0, 2),
        )
    pooled = np.concatenate(
        [
            np.where(np.isfinite(stacks[w.member][:, 1:]), r[w.member][:, 1:], np.nan)
            for w in worlds
        ],
        axis=1,
    )
    var_total = np.nanvar(pooled, axis=1)
    means = np.array(
        [
            np.nanmean(
                np.where(np.isfinite(stacks[w.member][:, 1:]), r[w.member][:, 1:], np.nan), axis=1
            )
            for w in worlds
        ]
    )
    var_between = means.var(axis=0)
    assert n_cells == len(mr)
    return mr, mr_clim, mr_tech, sr, var_total, var_between


@pytest.mark.unit
@pytest.mark.parametrize("block_cells", [7, 23, 60, 1000])
def test_the_streaming_evaluation_equals_the_brute_force_definition_whatever_the_block_size(
    block_cells,
):
    rng = np.random.default_rng(11)
    reference, worlds = _world(rng)
    samples = _samples(rng)
    tau = float(np.median(lcoe_block(reference.cells, samples)))
    got = evaluate(reference, worlds, samples, tau=tau, block_cells=block_cells)
    mr, mr_clim, mr_tech, sr, var_total, var_between = _brute_force(reference, worlds, samples, tau)
    np.testing.assert_allclose(got.mr, mr, rtol=1e-11)
    np.testing.assert_allclose(got.mr_clim, mr_clim, rtol=1e-11)
    np.testing.assert_allclose(got.mr_tech, mr_tech, rtol=1e-11)
    np.testing.assert_allclose(got.sr, sr, rtol=1e-13)
    np.testing.assert_allclose(got.var_total, var_total, rtol=1e-9)
    np.testing.assert_allclose(got.var_between, var_between, rtol=1e-8, atol=1e-14)
    np.testing.assert_allclose(got.var_within + got.var_between, got.var_total, rtol=1e-12)


@pytest.mark.unit
def test_one_cell_is_recomputed_by_hand_from_the_definitions():
    """MR of one cell: the regret in every future against the lowest LCOE of that future, P90 over the draws, maximum over members."""
    rng = np.random.default_rng(3)
    reference, worlds = _world(rng, n_cells=12, n_core=2)
    samples = _samples(rng, 20)
    got = evaluate(reference, worlds, samples, tau=None, block_cells=5)
    cell = 4
    per_member = []
    for w in worlds:
        block = lcoe_direct(w.cells, samples)
        regret = (block[cell, 1:] - block[:, 1:].min(axis=0)) / block[:, 1:].min(axis=0)
        per_member.append(np.quantile(regret, 0.9))
    assert got.mr[cell] == pytest.approx(max(per_member), rel=1e-12)
    assert got.sr is None and got.potential_gw is None


@pytest.mark.unit
def test_v03_invariants_hold():
    rng = np.random.default_rng(5)
    reference, worlds = _world(rng)
    samples = _samples(rng)
    tau = float(np.quantile(lcoe_block(reference.cells, samples), 0.4))
    got = evaluate(reference, worlds, samples, tau=tau, block_cells=17)
    assert (got.mr >= 0).all() and (got.mr_clim >= 0).all() and (got.mr_tech >= 0).all()
    assert ((got.sr >= 0) & (got.sr <= 1)).all()
    assert np.isfinite(got.mr).all()  # no ranked cell has an infinite MR
    # at least one cell has regret 0 in every future when q_ref = 0: the reference level is a cell's own LCOE
    for slot, world in enumerate([reference, *worlds]):
        block = lcoe_block(world.cells, samples, min_energy_mwh=world.floor)
        np.testing.assert_allclose(got.lowest[slot], block.min(axis=0), rtol=1e-14)
    assert (got.highest >= got.lowest).all()


@pytest.mark.unit
def test_a_cell_below_cf_min_in_a_member_is_fragile_has_no_mr_and_does_not_set_the_reference_level():
    rng = np.random.default_rng(8)
    reference, worlds = _world(rng, n_cells=30, n_core=3, fails={1: [4], 2: [4, 9]})
    samples = _samples(rng)
    got = evaluate(reference, worlds, samples, tau=None, block_cells=8)
    assert np.isnan(got.mr[[4, 9]]).all() and np.isfinite(np.delete(got.mr, [4, 9])).all()
    # in member 2 the cell 4 is infeasible, so its LCOE is infinite there and it is not the lowest of any sample
    block = lcoe_block(worlds[1].cells, samples, min_energy_mwh=worlds[1].floor)
    assert np.isposinf(block[4]).all()
    others = np.delete(block, 4, axis=0)
    np.testing.assert_allclose(got.lowest[2], others.min(axis=0), rtol=1e-14)


@pytest.mark.unit
def test_a_zero_energy_draw_takes_the_worst_case_regret_of_its_sample():
    rng = np.random.default_rng(9)
    reference, worlds = _world(rng, n_cells=10, n_core=1)
    samples = _samples(rng, 20)
    # a cell whose energy is zero in every sample through a zero energy slope term
    cells = worlds[0].cells
    energy = cells.energy_mwh.copy()
    energy[3] = 0.0
    broken = CellInputs(
        p_mw=cells.p_mw, dist_grid_km=cells.dist_grid_km, dist_road_km=cells.dist_road_km,
        energy_mwh=energy, energy_offset=cells.energy_offset, energy_slope=cells.energy_slope,
    )  # fmt: skip
    world = MemberWorld("m1", broken, np.zeros(10))
    got = evaluate(reference, [world], samples, tau=None, block_cells=4)
    block = lcoe_block(broken, samples)
    finite = np.where(np.isfinite(block), block, -np.inf)
    low, high = block.min(axis=0), finite.max(axis=0)
    worst = (high - low) / low
    assert got.mr[3] == pytest.approx(np.quantile(worst[1:], 0.9), rel=1e-12)
    assert np.isfinite(got.mr).all()


@pytest.mark.unit
def test_the_variance_decomposition_is_the_law_of_total_variance_on_an_explicit_two_way_table():
    rng = np.random.default_rng(12)
    reference, worlds = _world(rng, n_cells=15, n_core=4)
    samples = _samples(rng, 30)
    got = evaluate(reference, worlds, samples, tau=None, block_cells=6)
    blocks = np.array([lcoe_block(w.cells, samples)[:, 1:] for w in worlds])  # (M, C, N)
    low = np.array([lcoe_block(w.cells, samples)[:, 1:].min(axis=0) for w in worlds])  # (M, N)
    x = blocks / low[:, None, :] - 1.0
    for cell in range(15):
        table = x[:, cell, :]  # members x draws
        assert got.var_total[cell] == pytest.approx(table.var(), rel=1e-10)
        assert got.var_within[cell] == pytest.approx(table.var(axis=1).mean(), rel=1e-9)
        assert got.var_between[cell] == pytest.approx(table.mean(axis=1).var(), rel=1e-8)


@pytest.mark.unit
def test_the_potential_below_tau_counts_the_capacity_and_energy_of_the_cells_that_are_feasible_and_cheap_enough():
    rng = np.random.default_rng(14)
    reference, worlds = _world(rng, n_cells=25, n_core=2, fails={0: [2]})
    samples = _samples(rng, 12)
    tau = float(np.median(lcoe_block(reference.cells, samples)))
    got = evaluate(reference, worlds, samples, tau=tau, block_cells=9)
    for slot, world in enumerate([reference, *worlds]):
        block = lcoe_block(world.cells, samples, min_energy_mwh=world.floor)
        ok = np.isfinite(block) & (block <= tau)
        np.testing.assert_allclose(
            got.potential_gw[slot], world.cells.p_mw @ ok / 1000.0, rtol=1e-12
        )
        energy = world.cells.energy_mwh[:, None] * np.ones((1, len(samples)))
        np.testing.assert_allclose(
            got.potential_twh[slot], (energy * ok).sum(axis=0) / 1e6, rtol=1e-12
        )


@pytest.mark.unit
def test_reference_levels_refuse_a_sample_without_a_feasible_cell():
    rng = np.random.default_rng(1)
    reference, _ = _world(rng, n_cells=5, n_core=1)
    dead = MemberWorld("m1", reference.cells, np.full(5, np.inf))
    with pytest.raises(EvaluationError, match="no feasible cell"):
        reference_levels(dead, _samples(rng, 4), 3)


@pytest.mark.unit
def test_inputs_that_disagree_are_refused():
    rng = np.random.default_rng(2)
    reference, worlds = _world(rng, n_cells=8, n_core=2)
    short = MemberWorld("m3", worlds[0].cells.take(slice(0, 5)), np.zeros(5))
    with pytest.raises(EvaluationError, match="same cells"):
        evaluate(reference, [worlds[0], short], _samples(rng, 5), tau=None, block_cells=4)
    with pytest.raises(EvaluationError, match="at least two draws"):
        evaluate(reference, worlds, _samples(rng, 1), tau=None, block_cells=4)
    with pytest.raises(EvaluationError, match="no member"):
        evaluate(reference, [], _samples(rng, 5), tau=None, block_cells=4)
    with pytest.raises(EvaluationError, match="one floor per cell"):
        MemberWorld("x", reference.cells, np.zeros(3))


@pytest.mark.unit
def test_the_peak_memory_of_the_evaluation_stays_near_the_block_budget():
    """A-10: the largest arrays are the blocks of the block size; the rest is per cell."""
    rng = np.random.default_rng(4)
    reference, worlds = _world(rng, n_cells=4000, n_core=2)
    samples = _samples(rng, 200)
    block_cells = 500
    block_bytes = block_cells * len(samples) * 8
    tracemalloc.start()
    evaluate(reference, worlds, samples, tau=40.0, block_cells=block_cells)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert peak < 6.5 * block_bytes + 5_000_000, (peak, block_bytes)
