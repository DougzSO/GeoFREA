"""The U-04 sample-size protocol on the definitive max-regret of F7 (D-F6-004, D-F7-027, M-F7-02, M-F7-03, V-05)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
import yaml
from test_lcoe_pipeline import MEMBERS, _stage
from test_robustness_pipeline import CORE, SENSITIVITY
from test_robustness_pipeline import _country as _robustness_country
from test_robustness_pipeline import _experiments as _robustness_experiments
from test_robustness_pipeline import _run as _run_robustness

from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID
from geofrea.core.config_loader import load_experiments, load_parameters, load_technologies
from geofrea.lcoe_modeling import convergence
from geofrea.lcoe_modeling.convergence import (
    PROVENANCE_KEY,
    ConvergenceConfigError,
    build_convergence,
    jaccard,
    run_protocol,
)
from geofrea.lcoe_modeling.inputs import (
    LcoeInputError,
    LcoeMissingInputError,
    read_member_inputs,
    resolve_technology_costs,
)
from geofrea.robustness_analysis.decision import decision_values

REPO = Path(__file__).resolve().parents[2]
PARAMETERS = REPO / "config" / "parameters.json"
TECHNOLOGIES = REPO / "config" / "technologies.yaml"
EXPERIMENTS = REPO / "config" / "experiments.yaml"
THRESHOLDS = {"regret_quantile": 0}


def _zzz():
    return load_parameters(PARAMETERS).countries["ZZZ"]


# -- sets --------------------------------------------------------------------------------------------------------


@pytest.mark.unit
def test_jaccard_of_two_sets_and_of_two_empty_sets():
    assert jaccard(np.array([1, 2, 3]), np.array([2, 3, 4])) == pytest.approx(0.5)
    assert jaccard(np.array([], dtype=int), np.array([], dtype=int)) == 1.0


@pytest.mark.unit
def test_the_provisional_regret_is_gone_and_the_protocol_uses_the_function_of_f7():
    assert importlib.util.find_spec("geofrea.lcoe_modeling.provisional_regret") is None
    assert convergence.MR_FUNCTION == "f7"
    from geofrea.robustness_analysis import evaluator

    assert convergence.evaluate is evaluator.evaluate


# -- the protocol ---------------------------------------------------------------------------------------------------


def _inputs(tmp_path, tech="wind", **kw):
    """The member inputs `build_convergence` would hand to the protocol, from the staged small tables."""
    dirs = _stage(tmp_path, tech, **kw)
    zzz = _zzz()
    resolved = resolve_technology_costs(
        "ZZZ",
        tech,
        load_technologies(TECHNOLOGIES).technologies[tech],
        getattr(zzz.technologies, tech),
    )
    x = next(s for s in resolved.specs if s.name == resolved.energy_key)
    members = {
        item.member: item
        for item in read_member_inputs(
            resolved,
            potential_path=dirs["potential_dir"] / f"potential_{tech}__central.parquet",
            candidates_path=dirs["candidates_dir"] / f"candidates_{tech}__central.parquet",
            forcing_path=dirs["climate_dir"] / "forcing.parquet",
            members=MEMBERS,
            x_range=(x.low, x.high),
        )
    }
    candidates = pd.read_parquet(
        dirs["candidates_dir"] / f"candidates_{tech}__central.parquet", columns=["cell_id"]
    )["cell_id"].to_numpy()
    decision = decision_values(getattr(zzz.technologies, tech), tech)
    return resolved, members, candidates, decision, dirs


@pytest.mark.unit
def test_the_protocol_doubles_the_size_and_adopts_the_larger_of_the_first_pair_that_agrees(
    tmp_path,
):
    resolved, members, candidates, decision, _ = _inputs(tmp_path, n_cells=40)
    rows, adopted, n_cells, ids, top = run_protocol(
        resolved, members, ["m_a", "m_b"], candidates, decision,
        initial_size=8, max_size=64, seed=3, tolerance=0.01, max_batch_gb=1.0,
    )  # fmt: skip
    sizes = [r.n_samples for r in rows]
    assert sizes[0] == 8 and sizes == [8 * 2**i for i in range(len(sizes))]
    assert rows[0].jaccard_with_previous is None and not rows[0].meets_tolerance
    k = int(np.ceil(decision.top_k_percent / 100.0 * n_cells))
    assert n_cells == len(ids) <= 40 and all(r.k == k for r in rows) and top.size == k
    for r in rows[1:]:
        assert r.jaccard_distance_with_previous == pytest.approx(1 - r.jaccard_with_previous)
        assert r.meets_tolerance == (r.jaccard_distance_with_previous < 0.01)
    if adopted is not None:
        assert adopted == sizes[-1] and rows[-1].meets_tolerance  # the first pair that agrees
        assert not any(r.meets_tolerance for r in rows[:-1])
    else:
        assert not any(r.meets_tolerance for r in rows) and sizes[-1] * 2 > 64


@pytest.mark.unit
def test_the_ceiling_stops_the_doubling_and_a_single_size_cannot_converge(tmp_path):
    resolved, members, candidates, decision, _ = _inputs(tmp_path, n_cells=20)
    rows, adopted, *_ = run_protocol(
        resolved, members, ["m_a", "m_b"], candidates, decision,
        initial_size=8, max_size=8, seed=3, tolerance=0.01, max_batch_gb=1.0,
    )  # fmt: skip
    assert [r.n_samples for r in rows] == [8] and adopted is None
    rows, *_ = run_protocol(
        resolved, members, ["m_a", "m_b"], candidates, decision,
        initial_size=8, max_size=20, seed=3, tolerance=1e-12, max_batch_gb=1.0,
    )  # fmt: skip
    assert max(r.n_samples for r in rows) <= 20


@pytest.mark.unit
def test_a_ranking_that_does_not_depend_on_the_draws_converges_at_the_second_size(tmp_path):
    """A degenerate design (no parameter varies) gives the same MR at every size, so the sets agree exactly and 16 is adopted."""
    resolved, members, candidates, decision, _ = _inputs(tmp_path, n_cells=30)
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
    rows, adopted, *_ = run_protocol(
        flat, members, ["m_a", "m_b"], candidates, decision,
        initial_size=8, max_size=64, seed=3, tolerance=0.01, max_batch_gb=1.0,
    )  # fmt: skip
    assert adopted == 16 and [r.n_samples for r in rows] == [8, 16]
    assert rows[1].jaccard_with_previous == 1.0 and rows[1].meets_tolerance


@pytest.mark.unit
def test_the_protocol_refuses_a_missing_reference_member_and_an_empty_f7_set(tmp_path):
    resolved, members, candidates, decision, _ = _inputs(tmp_path, n_cells=12)
    kwargs = {"initial_size": 8, "max_size": 16, "seed": 3, "tolerance": 0.01, "max_batch_gb": 1.0}
    without_m0 = {k: v for k, v in members.items() if k != REFERENCE_MEMBER_ID}
    with pytest.raises(LcoeInputError, match="m0"):
        run_protocol(resolved, without_m0, ["m_a", "m_b"], candidates, decision, **kwargs)
    a, b = members["m_a"], members["m_b"]
    disjoint = {
        **members,
        "m_a": type(a)(a.member, a.cell_id[:6], a.cells.take(slice(0, 6)), a.cf[:6]),
        "m_b": type(b)(b.member, b.cell_id[6:], b.cells.take(slice(6, None)), b.cf[6:]),
    }
    with pytest.raises(LcoeInputError, match="F7 set is empty"):
        run_protocol(resolved, disjoint, ["m_a", "m_b"], candidates, decision, **kwargs)


@pytest.mark.unit
def test_the_top_k_of_the_protocol_is_the_robust_top_k_that_f7_writes_at_the_same_size(tmp_path):
    """D-F7-027: one function for MR. The protocol at one size and F7 with the same draws select the same cells."""
    size = 24
    experiments = _robustness_experiments()
    entry, _, dirs = _run_robustness(tmp_path / "f7", experiments=experiments)
    table = pd.read_parquet(entry.windows["core"].tables["robustness"])
    f7_top = set(table.loc[table["topk_robust"].fillna(False).astype(bool), "cell_id"])
    country = _robustness_country()
    resolved = resolve_technology_costs(
        "ZZZ",
        "wind",
        load_technologies(TECHNOLOGIES).technologies["wind"],
        country.technologies.wind,
    )
    x = next(s for s in resolved.specs if s.name == resolved.energy_key)
    members = {
        item.member: item
        for item in read_member_inputs(
            resolved,
            potential_path=dirs["potential_dir"] / "potential_wind__central.parquet",
            candidates_path=dirs["candidates_dir"] / "candidates_wind__central.parquet",
            forcing_path=dirs["climate_dir"] / "forcing.parquet",
            members=["m0", *CORE],
            x_range=(x.low, x.high),
            known_members=["m0", *CORE, *SENSITIVITY],
        )
    }
    candidates = pd.read_parquet(dirs["candidates_dir"] / "candidates_wind__central.parquet")[
        "cell_id"
    ]
    decision = decision_values(country.technologies.wind, "wind")
    _, _, _, _, top = run_protocol(
        resolved, members, CORE, candidates.to_numpy(), decision,
        initial_size=size, max_size=size, seed=experiments.sampler.seed, tolerance=0.01, max_batch_gb=1.0,
    )  # fmt: skip
    assert set(top.tolist()) == f7_top and len(f7_top) > 0


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
def test_build_convergence_writes_the_table_with_the_f7_function_and_the_adopted_size(tmp_path):
    dirs = _stage(tmp_path, "wind", n_cells=30)
    _with_windows(dirs)
    result = build_convergence(
        "ZZZ", load_technologies(TECHNOLOGIES), _zzz(), ["wind"],
        sampler=_sampler(), thresholds=THRESHOLDS, core_window="2041-2070", max_batch_gb=1.0,
        out_dir=tmp_path / "out", **dirs,
    )  # fmt: skip
    entry = result.technologies["wind"]
    table = pq.read_table(entry.table)
    meta = json.loads(table.schema.metadata[PROVENANCE_KEY.encode()])
    assert meta["provisional"] is False and meta["mr_function"] == "f7"
    assert meta["adopted_size"] == entry.adopted_size and meta["q_ref"] == 0
    assert meta["cf_min"] == entry.cf_min == _zzz().technologies.wind.cf_min.value
    assert "cf_min" in meta["feasibility"]
    frame = table.to_pandas()
    assert frame["n_samples"].tolist() == entry.sizes
    assert entry.n_members == 2 and entry.mr_function == "f7"
    assert 0 < entry.n_cells <= 30
    assert entry.converged == (entry.adopted_size is not None)


@pytest.mark.unit
def test_build_convergence_lists_the_values_only_the_author_can_set(tmp_path):
    country = _robustness_country(cf_min=None, top_k_percent=None)
    with pytest.raises(ConvergenceConfigError) as caught:
        build_convergence(
            "ZZZ", load_technologies(TECHNOLOGIES), country, ["wind"],
            sampler=_sampler(max_size_for_convergence=None), thresholds={"regret_quantile": 0.01},
            core_window="2041-2070", max_batch_gb=1.0,
            potential_dir=tmp_path / "none", candidates_dir=tmp_path / "none", climate_dir=tmp_path / "none",
        )  # fmt: skip
    text = str(caught.value)
    assert "wind: cf_min" in text and "OQ-008" in text
    assert "wind: top_k_percent" in text and "OQ-021" in text
    assert "max_size_for_convergence" in text
    assert "regret_quantile" in text and len(caught.value.missing) == 4


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
def test_the_real_experiments_file_has_no_ceiling_and_the_top_k_lives_in_the_country_parameters():
    """The ceiling is the author's; `top_k_percent` moved from `thresholds` to each country and technology (D-F7-027)."""
    experiments = load_experiments(EXPERIMENTS)
    assert experiments.sampler.max_size_for_convergence is None
    assert experiments.sampler.convergence_tolerance == 0.01  # U-04
    assert "top_k_percent" not in experiments.thresholds
    assert pd.notna(experiments.sampler.initial_size)
