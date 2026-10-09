"""The U-04 sample-size protocol and its provisional max-regret (D-F6-004, M-F7-02, M-F7-03, V-03, V-05)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
import yaml
from test_lcoe_pipeline import MEMBERS, _stage

from geofrea.core.config_loader import load_experiments, load_parameters, load_technologies
from geofrea.lcoe_modeling import provisional_regret
from geofrea.lcoe_modeling.convergence import (
    PROVENANCE_KEY,
    ConvergenceConfigError,
    build_convergence,
    f7_set,
    jaccard,
    run_protocol,
    top_k_cells,
)
from geofrea.lcoe_modeling.kernel import CellInputs, SampleInputs, lcoe_direct
from geofrea.lcoe_modeling.pipeline import (
    LcoeInputError,
    LcoeMissingInputError,
    read_member_inputs,
    resolve_technology_costs,
)
from geofrea.lcoe_modeling.provisional_regret import (
    ProvisionalRegretError,
    provisional_max_regret,
)

REPO = Path(__file__).resolve().parents[2]
PARAMETERS = REPO / "config" / "parameters.json"
TECHNOLOGIES = REPO / "config" / "technologies.yaml"
EXPERIMENTS = REPO / "config" / "experiments.yaml"
THRESHOLDS = {"top_k_percent": 25, "regret_quantile": 0}


def _cells(rng, n=24, zero=()):
    e = rng.uniform(5e4, 6e5, n)
    e[list(zero)] = 0.0
    return CellInputs(
        p_mw=rng.uniform(20, 300, n),
        dist_grid_km=rng.uniform(0, 150, n),
        dist_road_km=rng.uniform(0, 30, n),
        energy_mwh=e,
        energy_offset=np.ones(n),
        energy_slope=np.zeros(n),
    )


def _draws(rng, n=40):
    return SampleInputs(
        capex_usd_per_kw=rng.uniform(800, 1200, n),
        opex_fixed_frac=rng.uniform(0.02, 0.06, n),
        opex_var_usd_per_mwh=np.full(n, 2.0),
        lifetime_years=rng.integers(15, 26, n).astype(float),
        discount_rate=rng.uniform(0.03, 0.08, n),
        degradation_rate=rng.uniform(0.0, 0.01, n),
        grid_cost_usd_per_mw_km=rng.uniform(500, 1500, n),
        substation_cost_usd_per_mw=rng.uniform(1e4, 3e4, n),
        road_cost_usd_per_km=rng.uniform(2.5e4, 7.5e4, n),
        energy_parameter=np.ones(n),
    )


def _brute_force_mr(members, draws):
    """M-F7-02 and M-F7-03 on the full cells-by-samples arrays with plain NumPy, no blocks."""
    mr = np.full(len(members[0]), -np.inf)
    for cells in members:
        lcoe = lcoe_direct(cells, draws)
        feasible = np.isfinite(lcoe)
        lowest = np.where(feasible, lcoe, np.inf).min(axis=0)
        highest = np.where(feasible, lcoe, -np.inf).max(axis=0)
        regret = np.where(
            feasible, (lcoe - lowest) / lowest, ((highest - lowest) / lowest)[None, :]
        )
        mr = np.maximum(mr, np.quantile(regret, 0.9, axis=1, method="linear"))
    return mr


# -- the provisional max-regret -------------------------------------------------------------------------------


@pytest.mark.unit
def test_provisional_marker_is_visible_in_the_module():
    assert provisional_regret.PROVISIONAL is True
    assert "PROVISIONAL" in provisional_regret.__doc__


@pytest.mark.unit
@pytest.mark.parametrize("block", [1, 5, 1000])
def test_provisional_max_regret_equals_the_brute_force_definition_whatever_the_block_size(block):
    rng = np.random.default_rng(2)
    members = [_cells(rng, zero=(3,)) for _ in range(3)]
    draws = _draws(rng)
    got = provisional_max_regret(members, draws, block)
    np.testing.assert_allclose(got, _brute_force_mr(members, draws), rtol=1e-10)


@pytest.mark.unit
def test_regret_invariants_nonnegative_and_the_cheapest_cell_of_each_future_has_zero_regret():
    """V-03: `MR >= 0`; with `q_ref = 0` some cell has regret 0 in every future, so the lowest P90 over samples is small."""
    rng = np.random.default_rng(4)
    members = [_cells(rng) for _ in range(2)]
    draws = _draws(rng, 60)
    mr = provisional_max_regret(members, draws, 7)
    assert (mr >= 0).all() and np.isfinite(mr).all()
    lcoe = lcoe_direct(members[0], draws)
    cheapest = lcoe.argmin(axis=0)
    regret_of_cheapest = [
        (lcoe[c, s] - lcoe[:, s].min()) / lcoe[:, s].min() for s, c in enumerate(cheapest)
    ]
    assert max(regret_of_cheapest) == 0.0


@pytest.mark.unit
def test_an_infeasible_cell_gets_the_regret_of_the_highest_feasible_cell():
    """M-F7-02: a cell with zero energy in a future takes the finite worst-case regret, never an infinite one."""
    rng = np.random.default_rng(6)
    members = [_cells(rng, n=10, zero=(0,))]
    draws = _draws(rng, 30)
    mr = provisional_max_regret(members, draws, 4)
    lcoe = lcoe_direct(members[0], draws)
    lowest, highest = lcoe[1:].min(axis=0), lcoe[1:].max(axis=0)
    assert np.isfinite(mr).all()
    assert mr[0] == pytest.approx(np.quantile((highest - lowest) / lowest, 0.9), rel=1e-10)


@pytest.mark.unit
def test_provisional_regret_refuses_empty_unequal_and_all_infeasible_inputs():
    rng = np.random.default_rng(1)
    with pytest.raises(ProvisionalRegretError, match="no member"):
        provisional_max_regret([], _draws(rng), 4)
    with pytest.raises(ProvisionalRegretError, match="same cells"):
        provisional_max_regret([_cells(rng, 5), _cells(rng, 6)], _draws(rng), 4)
    with pytest.raises(ProvisionalRegretError, match="no feasible cell"):
        provisional_max_regret([_cells(rng, 3, zero=(0, 1, 2))], _draws(rng), 4)


# -- sets and the top-k -----------------------------------------------------------------------------------------


@pytest.mark.unit
def test_jaccard_and_top_k_with_ties_broken_by_cell_id_and_at_least_one_cell():
    assert jaccard(np.array([1, 2, 3]), np.array([2, 3, 4])) == pytest.approx(0.5)
    assert jaccard(np.array([], dtype=int), np.array([], dtype=int)) == 1.0
    ids = np.array([10, 11, 12, 13, 14])
    mr = np.array([0.5, 0.1, 0.1, 0.9, 0.3])
    assert top_k_cells(mr, ids, 40).tolist() == [11, 12]  # ceil(0.4 * 5) = 2, tie by cell_id
    assert top_k_cells(mr, ids, 1).tolist() == [11]  # at least one
    assert top_k_cells(mr, ids, 100).size == 5
    with pytest.raises(ConvergenceConfigError):
        top_k_cells(mr, ids, 0)
    with pytest.raises(ConvergenceConfigError):
        top_k_cells(mr, ids, 101)


@pytest.mark.unit
def test_the_f7_set_keeps_cells_present_in_every_core_member_and_feasible_at_m0():
    rng = np.random.default_rng(1)
    cells = _cells(rng, 6)
    data = {
        "m0": (np.array([1, 2, 3, 4, 5, 6]), cells),
        "m_a": (np.array([1, 2, 3, 4, 6]), cells.take(slice(0, 5))),  # cell 5 masked in m_a
        "m_b": (np.array([1, 2, 3, 5, 6]), cells.take(slice(0, 5))),  # cell 4 masked in m_b
    }
    feasible = np.array([True, True, False, True, True, True])  # cell 3 has no energy at m0
    kept = f7_set(data, ["m_a", "m_b"], feasible, data["m0"][0])
    assert kept.tolist() == [1, 2, 6]


# -- the protocol ---------------------------------------------------------------------------------------------------


def _members_data(tmp_path, tech="wind", **kw):
    """The member inputs `build_convergence` would hand to the protocol, from the staged small tables."""
    dirs = _stage(tmp_path, tech, **kw)
    registry = load_technologies(TECHNOLOGIES)
    zzz = getattr(load_parameters(PARAMETERS).countries["ZZZ"].technologies, tech)
    resolved = resolve_technology_costs("ZZZ", tech, registry.technologies[tech], zzz)
    x = next(s for s in resolved.specs if s.name == resolved.energy_key)
    data = {
        item.member: (item.cell_id, item.cells)
        for item in read_member_inputs(
            resolved,
            potential_path=dirs["potential_dir"] / f"potential_{tech}__central.parquet",
            candidates_path=dirs["candidates_dir"] / f"candidates_{tech}__central.parquet",
            forcing_path=dirs["climate_dir"] / "forcing.parquet",
            members=MEMBERS,
            x_range=(x.low, x.high),
        )
    }
    return resolved, data, dirs


@pytest.mark.unit
def test_the_protocol_doubles_the_size_and_adopts_the_larger_of_the_first_pair_that_agrees(
    tmp_path,
):
    resolved, data, _ = _members_data(tmp_path, n_cells=40)
    rows, adopted, n_cells, ids = run_protocol(
        resolved, data, ["m_a", "m_b"],
        initial_size=8, max_size=64, seed=3, tolerance=0.01, top_k_percent=25, max_batch_gb=1.0,
    )  # fmt: skip
    sizes = [r.n_samples for r in rows]
    assert sizes[0] == 8 and sizes == [8 * 2**i for i in range(len(sizes))]
    assert rows[0].jaccard_with_previous is None and not rows[0].meets_tolerance
    assert n_cells == len(ids) == 40 and all(r.k == 10 for r in rows)  # ceil(0.25 * 40)
    for r in rows[1:]:
        assert r.jaccard_distance_with_previous == pytest.approx(1 - r.jaccard_with_previous)
        assert r.meets_tolerance == (r.jaccard_distance_with_previous < 0.01)
    if adopted is not None:
        assert (
            adopted == sizes[-1] and rows[-1].meets_tolerance
        )  # it stops at the first pair that agrees
        assert not any(r.meets_tolerance for r in rows[:-1])
    else:
        assert not any(r.meets_tolerance for r in rows) and sizes[-1] * 2 > 64


@pytest.mark.unit
def test_the_ceiling_stops_the_doubling_and_a_single_size_cannot_converge(tmp_path):
    resolved, data, _ = _members_data(tmp_path, n_cells=20)
    rows, adopted, _, _ = run_protocol(
        resolved, data, ["m_a", "m_b"],
        initial_size=8, max_size=8, seed=3, tolerance=0.01, top_k_percent=25, max_batch_gb=1.0,
    )  # fmt: skip
    assert [r.n_samples for r in rows] == [8] and adopted is None
    rows, _, _, _ = run_protocol(
        resolved, data, ["m_a", "m_b"],
        initial_size=8, max_size=20, seed=3, tolerance=1e-12, top_k_percent=25, max_batch_gb=1.0,
    )  # fmt: skip
    assert max(r.n_samples for r in rows) <= 20


@pytest.mark.unit
def test_a_ranking_that_does_not_depend_on_the_draws_converges_at_the_second_size(tmp_path):
    """A degenerate design (no parameter varies) gives the same MR at every size, so the sets agree exactly and 16 is adopted."""
    resolved, data, _ = _members_data(tmp_path, n_cells=30)
    flat = type(resolved)(
        technology=resolved.technology,
        cf_model_name=resolved.cf_model_name,
        model=resolved.model,
        energy_key=resolved.energy_key,
        nominal=resolved.nominal,
        specs=tuple(
            type(s)(s.name, s.nominal, s.nominal, s.nominal, "uniform") for s in resolved.specs
        ),
    )
    rows, adopted, _, _ = run_protocol(
        flat, data, ["m_a", "m_b"],
        initial_size=8, max_size=64, seed=3, tolerance=0.01, top_k_percent=25, max_batch_gb=1.0,
    )  # fmt: skip
    assert adopted == 16 and [r.n_samples for r in rows] == [8, 16]
    assert rows[1].jaccard_with_previous == 1.0 and rows[1].meets_tolerance


@pytest.mark.unit
def test_the_protocol_refuses_a_missing_reference_member_and_an_empty_f7_set(tmp_path):
    resolved, data, _ = _members_data(tmp_path, n_cells=12)
    without_m0 = {k: v for k, v in data.items() if k != "m0"}
    kwargs = {
        "initial_size": 8,
        "max_size": 16,
        "seed": 3,
        "tolerance": 0.01,
        "top_k_percent": 25,
        "max_batch_gb": 1.0,
    }
    with pytest.raises(LcoeInputError, match="m0"):
        run_protocol(resolved, without_m0, ["m_a", "m_b"], **kwargs)
    ids_a, cells_a = data["m_a"]
    ids_b, cells_b = data["m_b"]
    disjoint = {
        **data,
        "m_a": (ids_a[:6], cells_a.take(slice(0, 6))),
        "m_b": (ids_b[6:], cells_b.take(slice(6, None))),
    }
    with pytest.raises(LcoeInputError, match="F7 set is empty"):
        run_protocol(resolved, disjoint, ["m_a", "m_b"], **kwargs)


# -- the phase function ------------------------------------------------------------------------------------------------


def _with_windows(dirs):
    (dirs["climate_dir"] / "members.yaml").write_text(
        yaml.safe_dump(
            {
                "members": [
                    {"member": "m0", "window": "1995-2014"},
                    {"member": "m_a", "window": "2041-2070"},
                    {"member": "m_b", "window": "2041-2070"},
                ]
            }
        ),
        encoding="utf-8",
    )


def _sampler(**over):
    base = load_experiments(EXPERIMENTS).sampler
    return base.model_copy(update={"initial_size": 8, "max_size_for_convergence": 32, **over})


@pytest.mark.unit
def test_build_convergence_writes_the_table_with_the_provisional_flag_and_the_adopted_size(
    tmp_path,
):
    dirs = _stage(tmp_path, "wind", n_cells=30)
    _with_windows(dirs)
    result = build_convergence(
        "ZZZ", load_technologies(TECHNOLOGIES), load_parameters(PARAMETERS).countries["ZZZ"], ["wind"],
        sampler=_sampler(), thresholds=THRESHOLDS, core_window="2041-2070", max_batch_gb=1.0,
        out_dir=tmp_path / "out", **dirs,
    )  # fmt: skip
    entry = result.technologies["wind"]
    table = pq.read_table(entry.table)
    meta = json.loads(table.schema.metadata[PROVENANCE_KEY.encode()])
    assert meta["provisional"] is True and meta["mr_function"] == "provisional"
    assert meta["adopted_size"] == entry.adopted_size and meta["q_ref"] == 0
    frame = table.to_pandas()
    assert frame["n_samples"].tolist() == entry.sizes
    assert entry.n_members == 2 and entry.n_cells == 30 and entry.mr_function == "provisional"
    assert entry.converged == (entry.adopted_size is not None)


@pytest.mark.unit
def test_build_convergence_lists_the_values_only_the_author_can_set(tmp_path):
    with pytest.raises(ConvergenceConfigError) as caught:
        build_convergence(
            "ZZZ", load_technologies(TECHNOLOGIES), load_parameters(PARAMETERS).countries["ZZZ"], ["wind"],
            sampler=_sampler(max_size_for_convergence=None), thresholds={"top_k_percent": None, "regret_quantile": 0.01},
            core_window="2041-2070", max_batch_gb=1.0,
            potential_dir=tmp_path / "none", candidates_dir=tmp_path / "none", climate_dir=tmp_path / "none",
        )  # fmt: skip
    text = str(caught.value)
    assert "top_k_percent" in text and "OQ-021" in text
    assert "max_size_for_convergence" in text
    assert "regret_quantile" in text and len(caught.value.missing) == 3


@pytest.mark.unit
@pytest.mark.parametrize("iso", ["BRA", "PRT", "IND"])
def test_real_countries_do_not_run_the_protocol_until_their_parameters_have_ranges(iso, tmp_path):
    """The parameter check comes first and lists the absent ranges; no input is read and nothing is written."""
    with pytest.raises(LcoeMissingInputError, match="range"):
        build_convergence(
            iso, load_technologies(TECHNOLOGIES), load_parameters(PARAMETERS).countries[iso],
            ["solar", "wind"], sampler=_sampler(), thresholds=THRESHOLDS, core_window="2041-2070",
            max_batch_gb=1.0, potential_dir=tmp_path / "none", candidates_dir=tmp_path / "none",
            climate_dir=tmp_path / "none", out_dir=tmp_path / "out",
        )  # fmt: skip
    assert not (tmp_path / "out").exists()


@pytest.mark.unit
def test_the_real_experiments_file_has_no_ceiling_and_no_top_k_yet():
    """The two values are the author's: the shipped configuration refuses to run the protocol (OQ-021, D-F6-004)."""
    experiments = load_experiments(EXPERIMENTS)
    assert experiments.sampler.max_size_for_convergence is None
    assert experiments.sampler.convergence_tolerance == 0.01  # U-04
    assert experiments.thresholds["top_k_percent"] is None
    assert pd.notna(experiments.sampler.initial_size)
