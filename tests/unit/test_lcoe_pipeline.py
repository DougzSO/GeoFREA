"""F6 pipeline on small tables built here: summaries, design matrix, supply curves, memory, failures (M-F6-01 to M-F6-06, V-03, A-09)."""

from __future__ import annotations

import ast
import json
import shutil
import tracemalloc
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
import yaml

from geofrea.core.config_loader import load_parameters, load_technologies
from geofrea.core.tables import TableSchemaError, TableWriter, write_table
from geofrea.lcoe_modeling.inputs import (
    LcoeInputError,
    LcoeMissingInputError,
    cells_per_block,
    resolve_technology_costs,
)
from geofrea.lcoe_modeling.kernel import CellInputs, SampleInputs
from geofrea.lcoe_modeling.pipeline import (
    PROVENANCE_KEY,
    build_lcoe,
    iter_member_summaries,
    lcoe_dir,
)
from geofrea.lcoe_modeling.summary import SummaryError, summarize_draws
from geofrea.lcoe_modeling.supply_curve import supply_curve
from geofrea.technical_potential.pipeline import PROVENANCE_KEY as POTENTIAL_KEY
from geofrea.technical_potential.rescale import (
    rescale_cf_solar,
    rescale_cf_wind,
    solar_rescale_terms,
    wind_rescale_terms,
)
from geofrea.technical_potential.table_schemas import POTENTIAL_TABLE_SCHEMA_VERSION, PotentialRow

REPO = Path(__file__).resolve().parents[2]
PARAMETERS = REPO / "config" / "parameters.json"
TECHNOLOGIES = REPO / "config" / "technologies.yaml"
MEMBERS = ["m0", "m_a", "m_b"]
TECHS = ["solar", "wind"]


@pytest.fixture(scope="module")
def registry():
    return load_technologies(TECHNOLOGIES)


@pytest.fixture(scope="module")
def parameters():
    return load_parameters(PARAMETERS)


def _tech_params(parameters, iso, tech):
    return getattr(parameters.countries[iso].technologies, tech)


# -- inputs ------------------------------------------------------------------------------------------


def _write_inputs(root: Path, resolved, n_cells=30, zero_energy_cell=None, drop=()):
    """F5-like potential table (with provenance), F3-like candidates and an F4-like forcing, for the cells 100..100+n."""
    rng = np.random.default_rng(5)
    ids = np.arange(100, 100 + n_cells)
    p_mw = rng.uniform(20.0, 300.0, n_cells)
    dist_grid = rng.uniform(0.0, 120.0, n_cells)
    dist_road = rng.uniform(0.0, 30.0, n_cells)
    cf0 = rng.uniform(0.15, 0.4, n_cells)
    pieces, forcing = [], []
    for k, member in enumerate(MEMBERS):
        d_t = np.zeros(n_cells) if member == "m0" else rng.uniform(1.0, 3.0, n_cells)
        cf = cf0 * (1.0 - 0.01 * k)
        keep = np.array([(int(c), member) not in drop for c in ids])
        e = p_mw * cf * 8760.0
        if zero_energy_cell is not None and member == "m_a":
            e[ids == zero_energy_cell] = 0.0
        pieces.append(
            pd.DataFrame(
                {
                    "cell_id": ids[keep].astype("int64"),
                    "member": pd.Categorical([member] * int(keep.sum()), categories=MEMBERS),
                    "P_MW": p_mw[keep],
                    "CF": cf[keep],
                    "E_MWh": e[keep],
                }
            )
        )
        forcing.append(
            pd.DataFrame(
                {
                    "cell_id": ids[keep].astype("int64"),
                    "member": pd.Categorical([member] * int(keep.sum()), categories=MEMBERS),
                    "delta_rsds": np.ones(int(keep.sum())),
                    "dT": d_t[keep],
                    "delta_wind": np.ones(int(keep.sum())),
                }
            )
        )
    root.mkdir(parents=True, exist_ok=True)
    meta = {
        POTENTIAL_KEY: json.dumps(
            {"parameters": {resolved.energy_key: resolved.nominal[resolved.energy_key]}}
        )
    }
    potential_path = root / "potential.parquet"
    write_table(
        pd.concat(pieces, ignore_index=True),
        potential_path,
        schema_version=POTENTIAL_TABLE_SCHEMA_VERSION,
        row_model=PotentialRow,
        extra_metadata=meta,
    )
    candidates_path = root / "candidates.parquet"
    pd.DataFrame({"cell_id": ids, "dist_grid_km": dist_grid, "dist_road_km": dist_road}).to_parquet(
        candidates_path
    )
    forcing_path = root / "forcing.parquet"
    pd.concat(forcing, ignore_index=True).to_parquet(forcing_path)
    return potential_path, candidates_path, forcing_path


def _stage(tmp_path, tech, restrictive_drop=(), **kw):
    """The directory layout `build_lcoe` reads, from small tables for the ZZZ values of `tech`."""
    registry = load_technologies(TECHNOLOGIES)
    zzz = getattr(load_parameters(PARAMETERS).countries["ZZZ"].technologies, tech)
    resolved = resolve_technology_costs("ZZZ", tech, registry.technologies[tech], zzz)
    potential, candidates, forcing = _write_inputs(tmp_path / "raw", resolved, **kw)
    pdir, cdir, kdir = tmp_path / "potential", tmp_path / "candidates", tmp_path / "climate"
    for d in (pdir, cdir, kdir):
        d.mkdir()
    potential.replace(pdir / f"potential_{tech}__central.parquet")
    candidates.replace(cdir / f"candidates_{tech}__central.parquet")
    # the other land scenarios: the same tables, the restrictive one without the cells in `restrictive_drop`
    central = pd.read_parquet(pdir / f"potential_{tech}__central.parquet")
    meta = pq.read_schema(pdir / f"potential_{tech}__central.parquet").metadata
    for scenario in ("restrictive", "permissive"):
        keep = ~central["cell_id"].isin(restrictive_drop if scenario == "restrictive" else ())
        write_table(
            central[keep].reset_index(drop=True),
            pdir / f"potential_{tech}__{scenario}.parquet",
            schema_version=POTENTIAL_TABLE_SCHEMA_VERSION,
            row_model=PotentialRow,
            extra_metadata={POTENTIAL_KEY: meta[POTENTIAL_KEY.encode()].decode()},
        )
        shutil.copy(
            cdir / f"candidates_{tech}__central.parquet",
            cdir / f"candidates_{tech}__{scenario}.parquet",
        )
    forcing.replace(kdir / "forcing.parquet")
    (kdir / "members.yaml").write_text(
        yaml.safe_dump({"members": [{"member": m} for m in MEMBERS]}), encoding="utf-8"
    )
    return {"potential_dir": pdir, "candidates_dir": cdir, "climate_dir": kdir}


def _run(tmp_path, tech, n=40, seed=7, gb=1.0, **kw):
    dirs = _stage(tmp_path, tech, **kw)
    registry = load_technologies(TECHNOLOGIES)
    zzz = load_parameters(PARAMETERS).countries["ZZZ"]
    out = tmp_path / "out"
    result = build_lcoe(
        "ZZZ", registry, zzz, [tech], sampler_seed=seed, sampler_size=n, max_batch_gb=gb,
        out_dir=out, **dirs,
    )  # fmt: skip
    return result.technologies[tech], out


def _hand_lcoe(p, dist_grid, dist_road, e_year1, s):
    """M-F6-01 written out year by year with plain floats, independent of the kernel module."""
    capex_total = (
        p * 1000 * s["capex_usd_per_kw"]
        + p * dist_grid * s["grid_cost_usd_per_mw_km"]
        + p * s["substation_cost_usd_per_mw"]
        + dist_road * s["road_cost_usd_per_km"]
    )
    cost, energy = capex_total, 0.0
    for t in range(1, int(s["lifetime_years"]) + 1):
        e_t = e_year1 * (1 - s["degradation_rate"]) ** (t - 1)
        opex_t = (
            s["opex_fixed_frac"] * p * 1000 * s["capex_usd_per_kw"]
            + s["opex_var_usd_per_mwh"] * e_t
        )
        cost += opex_t / (1 + s["discount_rate"]) ** t
        energy += e_t / (1 + s["discount_rate"]) ** t
    return cost / energy


# -- the nominal LCOE of the other land scenarios (D-F6-018) -----------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("tech", TECHS)
def test_the_other_land_scenarios_get_a_nominal_lcoe_table_with_no_draws(tmp_path, tech):
    """The restrictive and permissive scenarios carry `lcoe_nominal` only; for a cell they share with the central scenario it is the central nominal."""
    dropped = (101, 107)
    dirs = _stage(tmp_path, tech, restrictive_drop=dropped)
    registry = load_technologies(TECHNOLOGIES)
    zzz = load_parameters(PARAMETERS).countries["ZZZ"]
    out = tmp_path / "out"
    result = build_lcoe(
        "ZZZ", registry, zzz, [tech], sampler_seed=7, sampler_size=24, max_batch_gb=1.0,
        out_dir=out, **dirs,
    )  # fmt: skip
    entry = result.technologies[tech]
    assert set(entry.lcoe_nominal_scenarios) == {"restrictive", "permissive"}
    central = (
        pd.read_parquet(entry.lcoe_summary).astype({"member": str}).set_index(["cell_id", "member"])
    )
    for scenario, path in entry.lcoe_nominal_scenarios.items():
        assert path.name == f"lcoe_nominal_{tech}__{scenario}.parquet"
        table = pd.read_parquet(path).astype({"member": str})
        assert list(table.columns) == ["cell_id", "member", "lcoe_nominal"]  # no statistic, no draw
        expect = central.reset_index()
        if scenario == "restrictive":
            expect = expect[~expect["cell_id"].isin(dropped)]
        assert len(table) == len(expect)
        merged = table.merge(expect, on=["cell_id", "member"], suffixes=("", "_central"))
        assert len(merged) == len(table)
        np.testing.assert_allclose(
            merged["lcoe_nominal"], merged["lcoe_nominal_central"], rtol=1e-13
        )
    assert not (
        set(dropped) & set(pd.read_parquet(entry.lcoe_nominal_scenarios["restrictive"])["cell_id"])
    )


@pytest.mark.unit
def test_a_missing_table_of_another_land_scenario_is_refused_before_the_run(tmp_path):
    dirs = _stage(tmp_path, "wind")
    (dirs["potential_dir"] / "potential_wind__permissive.parquet").unlink()
    registry = load_technologies(TECHNOLOGIES)
    zzz = load_parameters(PARAMETERS).countries["ZZZ"]
    with pytest.raises(FileNotFoundError, match="permissive"):
        build_lcoe(
            "ZZZ", registry, zzz, ["wind"], sampler_seed=7, sampler_size=16, max_batch_gb=1.0,
            out_dir=tmp_path / "out", **dirs,
        )  # fmt: skip


# -- the summaries ------------------------------------------------------------------------------------


@pytest.mark.unit
def test_summary_equals_numpy_on_the_full_block():
    rng = np.random.default_rng(1)
    draws = rng.uniform(20.0, 90.0, (50, 201))
    reference = draws.copy()
    got = summarize_draws(draws)
    np.testing.assert_allclose(got.mean, reference.mean(axis=1), rtol=1e-12)
    np.testing.assert_allclose(got.var, reference.var(axis=1, ddof=1), rtol=1e-11)
    for name, q in (("p10", 0.1), ("p50", 0.5), ("p90", 0.9)):
        np.testing.assert_allclose(
            getattr(got, name), np.quantile(reference, q, axis=1, method="linear"), rtol=1e-13
        )
    assert (got.n_nonfinite == 0).all()


@pytest.mark.unit
def test_summary_with_infinite_draws_keeps_the_order_statistics_and_counts_them():
    """D-F6-007: mean and variance over the finite draws, quantiles over all draws, `+inf` counted."""
    draws = np.tile(np.arange(1.0, 11.0), (3, 1))  # 1..10 in every row
    draws[0, 3:] = np.inf  # 3 finite draws: 1, 2, 3
    draws[1, :] = np.inf  # no finite draw
    draws[2, 9] = np.inf  # one infinite draw
    got = summarize_draws(draws.copy())
    assert got.n_nonfinite.tolist() == [7, 10, 1]
    assert got.mean[0] == pytest.approx(2.0) and got.var[0] == pytest.approx(1.0)
    assert np.isnan(got.mean[1]) and np.isnan(got.var[1])
    assert np.isposinf([got.p10[1], got.p50[1], got.p90[1]]).all()  # inf, not NaN
    assert got.p50[0] == np.inf and got.p10[0] == pytest.approx(
        1.9
    )  # 10th percentile of [1,2,3,inf*7]
    assert got.mean[2] == pytest.approx(np.mean(np.arange(1.0, 10.0)))
    assert got.p90[2] == np.inf  # the position 8.1 interpolates towards the infinite last draw


@pytest.mark.unit
def test_summary_rejects_a_single_draw_a_nan_and_a_wrong_dtype():
    with pytest.raises(SummaryError):
        summarize_draws(np.ones((3, 1)))
    with pytest.raises(SummaryError, match="NaN"):
        summarize_draws(np.array([[1.0, np.nan, 2.0]]))
    with pytest.raises(SummaryError):
        summarize_draws(np.ones((3, 4), dtype="float32"))


def _random_cells_and_samples(n_cells, n_draws, seed=3):
    rng = np.random.default_rng(seed)
    cells = CellInputs(
        p_mw=rng.uniform(10, 300, n_cells),
        dist_grid_km=rng.uniform(0, 100, n_cells),
        dist_road_km=rng.uniform(0, 20, n_cells),
        energy_mwh=rng.uniform(1e4, 9e5, n_cells),
        energy_offset=np.ones(n_cells),
        energy_slope=np.zeros(n_cells),
    )
    n = n_draws + 1
    samples = SampleInputs(
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
    return cells, samples.take(slice(0, 1)), samples.take(slice(1, None))


@pytest.mark.unit
@pytest.mark.parametrize("block", [1, 7, 53, 10_000])
def test_the_summary_does_not_depend_on_the_block_size(block):
    """Exact quantiles: the cell block size changes the memory, never the numbers (D-F6-002)."""
    cells, nominal, draws = _random_cells_and_samples(53, 120)

    def collect(size):
        out = {k: np.empty(len(cells)) for k in ("nominal", "mean", "var", "p10", "p50", "p90")}
        for window, nom, stats in iter_member_summaries(cells, nominal, draws, size):
            out["nominal"][window] = nom
            for k in ("mean", "var", "p10", "p50", "p90"):
                out[k][window] = getattr(stats, k)
        return out

    whole, chunked = collect(10_000), collect(block)
    for key in whole:
        np.testing.assert_allclose(chunked[key], whole[key], rtol=1e-13)


@pytest.mark.unit
def test_the_peak_memory_of_the_summaries_respects_the_block_budget():
    """A-10, D-F6-005: with a 4 MB budget the allocations of the loop stay below it, far below the whole cells-by-samples array."""
    n_cells, n_draws = 20_000, 255
    cells, nominal, draws = _random_cells_and_samples(n_cells, n_draws)
    budget_gb = 0.004
    block = cells_per_block(budget_gb, n_draws)
    assert block == int(budget_gb * 1e9 // (4 * 8 * (n_draws + 1)))
    whole_bytes = n_cells * n_draws * 8
    tracemalloc.start()
    try:
        base = tracemalloc.get_traced_memory()[0]
        tracemalloc.reset_peak()
        for _ in iter_member_summaries(cells, nominal, draws, block):
            pass
        peak = tracemalloc.get_traced_memory()[1] - base
    finally:
        tracemalloc.stop()
    assert peak <= budget_gb * 1e9, f"peak {peak} B over the {budget_gb * 1e9:.0f} B budget"
    assert peak < whole_bytes / 5


@pytest.mark.unit
def test_cells_per_block_follows_the_budget_and_never_falls_below_one():
    assert cells_per_block(1.0, 500) == int(1e9 // (4 * 8 * 501))
    assert cells_per_block(1e-9, 500) == 1
    with pytest.raises(LcoeInputError):
        cells_per_block(0.0, 500)


# -- one summary row recomputed by hand (M-F6-01, V-03) ----------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("tech", TECHS)
def test_a_summary_row_is_reproduced_by_recomputing_the_kernel_by_hand(tmp_path, tech):
    result, _out = _run(tmp_path, tech, n=60)
    summary = pd.read_parquet(result.lcoe_summary)
    design = pd.read_parquet(result.design_matrix).set_index("sample")
    potential = pd.read_parquet(
        tmp_path / "potential" / f"potential_{tech}__central.parquet"
    ).astype({"member": str})
    candidates = pd.read_parquet(
        tmp_path / "candidates" / f"candidates_{tech}__central.parquet"
    ).set_index("cell_id")
    forcing = pd.read_parquet(tmp_path / "climate" / "forcing.parquet").astype({"member": str})
    registry = load_technologies(TECHNOLOGIES)
    zzz = _tech_params(load_parameters(PARAMETERS), "ZZZ", tech)
    resolved = resolve_technology_costs("ZZZ", tech, registry.technologies[tech], zzz)
    energy_key = resolved.energy_key
    x0 = resolved.nominal[energy_key]

    cell, member = 117, "m_b"
    prow = potential[(potential.cell_id == cell) & (potential.member == member)].iloc[0]
    d_t = float(forcing[(forcing.cell_id == cell) & (forcing.member == member)]["dT"].iloc[0])
    dg, dr = candidates.loc[cell, "dist_grid_km"], candidates.loc[cell, "dist_road_km"]

    def lcoe_of(sample):
        s = {
            k: float(design.loc[sample, k]) if k in design.columns else resolved.nominal[k]
            for k in resolved.nominal
        }
        x = s[energy_key]
        if tech == "solar":  # the energy rescale of M-F5-02 written out
            factor = (1 + x * d_t) / (1 + x0 * d_t)
        else:  # M-F5-03: eta_loss is a scalar factor
            factor = x / x0
        return _hand_lcoe(prow.P_MW, dg, dr, prow.E_MWh * factor, s)

    draws = np.array([lcoe_of(i) for i in range(1, 61)])
    row = summary[(summary.cell_id == cell) & (summary.member == member)].iloc[0]
    assert row.lcoe_nominal == pytest.approx(lcoe_of(0), rel=1e-11)
    assert row.lcoe_mean == pytest.approx(draws.mean(), rel=1e-11)
    assert row.lcoe_var == pytest.approx(draws.var(ddof=1), rel=1e-9)
    for column, q in (("lcoe_p10", 0.1), ("lcoe_p50", 0.5), ("lcoe_p90", 0.9)):
        assert row[column] == pytest.approx(np.quantile(draws, q), rel=1e-11)
    assert row.n_nonfinite == 0


@pytest.mark.unit
@pytest.mark.parametrize("tech", TECHS)
def test_nominal_lcoe_equals_the_direct_lcoe_of_the_f5_table_and_the_rescale_is_one_there(
    tmp_path, tech
):
    """V-03: at `s0` the rescale factor is 1, so `lcoe_nominal` is the LCOE of the stored F5 energy."""
    result, _ = _run(tmp_path, tech, n=10)
    summary = pd.read_parquet(result.lcoe_summary).astype({"member": str})
    potential = pd.read_parquet(
        tmp_path / "potential" / f"potential_{tech}__central.parquet"
    ).astype({"member": str})
    candidates = pd.read_parquet(
        tmp_path / "candidates" / f"candidates_{tech}__central.parquet"
    ).set_index("cell_id")
    registry = load_technologies(TECHNOLOGIES)
    resolved = resolve_technology_costs(
        "ZZZ",
        tech,
        registry.technologies[tech],
        _tech_params(load_parameters(PARAMETERS), "ZZZ", tech),
    )
    merged = summary.merge(potential, on=["cell_id", "member"], validate="one_to_one")
    for _, r in merged.sample(12, random_state=1).iterrows():
        direct = _hand_lcoe(
            r.P_MW,
            candidates.loc[r.cell_id, "dist_grid_km"],
            candidates.loc[r.cell_id, "dist_road_km"],
            r.E_MWh,
            dict(resolved.nominal),
        )
        assert r.lcoe_nominal == pytest.approx(direct, rel=1e-11)


@pytest.mark.unit
def test_rescale_terms_reproduce_the_f5_rescale_functions_and_are_one_at_the_nominal_value():
    d_t = np.array([0.0, 1.0, 2.5, 4.0])
    cf = np.array([0.2, 0.25, 0.3, 0.35])
    offset, slope = solar_rescale_terms(d_t, -0.005)
    for gamma in (-0.007, -0.005, -0.003):
        np.testing.assert_allclose(
            cf * (offset + slope * gamma), rescale_cf_solar(cf, d_t, -0.005, gamma), rtol=1e-14
        )
    np.testing.assert_allclose(offset + slope * -0.005, 1.0, rtol=1e-14)
    offset, slope = wind_rescale_terms(4, 0.9)
    for eta in (0.8, 0.9, 0.95):
        np.testing.assert_allclose(
            cf * (offset + slope * eta), rescale_cf_wind(cf, 0.9, eta), rtol=1e-14
        )
    np.testing.assert_allclose(offset + slope * 0.9, 1.0, rtol=1e-14)


# -- design matrix, determinism, what is persisted ----------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("tech", TECHS)
def test_the_design_matrix_is_nominal_first_in_range_integer_lifetime_and_reproducible(
    tmp_path, tech
):
    result, _ = _run(tmp_path / "a", tech, n=80, seed=11)
    design = pd.read_parquet(result.design_matrix)
    zzz = _tech_params(load_parameters(PARAMETERS), "ZZZ", tech)
    registry = load_technologies(TECHNOLOGIES)
    keys = registry.technologies[tech].uncertain_parameters
    assert design["sample"].tolist() == list(range(81))
    assert design.columns.tolist() == ["sample", *keys]
    for key in keys:
        entry = getattr(zzz, key)
        assert design.loc[0, key] == entry.value  # sample 0 is the nominal vector
        assert design[key].between(entry.range.min, entry.range.max).all()
    assert (design["lifetime_years"] == design["lifetime_years"].round()).all()
    again, _ = _run(tmp_path / "b", tech, n=80, seed=11)
    pd.testing.assert_frame_equal(design, pd.read_parquet(again.design_matrix))
    pd.testing.assert_frame_equal(
        pd.read_parquet(result.lcoe_summary), pd.read_parquet(again.lcoe_summary)
    )
    other, _ = _run(tmp_path / "c", tech, n=80, seed=12)
    assert not design.equals(pd.read_parquet(other.design_matrix))


@pytest.mark.unit
def test_no_sample_level_array_is_persisted_and_the_metadata_records_the_run(tmp_path):
    result, out = _run(tmp_path, "wind", n=64)
    assert sorted(p.name for p in out.iterdir()) == [
        "design_matrix_wind.parquet",
        "lcoe_nominal_wind__permissive.parquet",
        "lcoe_nominal_wind__restrictive.parquet",
        "lcoe_summary_wind.parquet",
        "supply_curve_wind.parquet",
    ]
    summary = pq.read_table(result.lcoe_summary)
    assert summary.column_names == [
        "cell_id",
        "member",
        "lcoe_nominal",
        "lcoe_mean",
        "lcoe_var",
        "lcoe_p10",
        "lcoe_p50",
        "lcoe_p90",
        "n_nonfinite",
    ]
    assert (
        summary.num_rows == 30 * len(MEMBERS) == result.n_rows
    )  # one row per cell-member, not per sample
    meta = json.loads(summary.schema.metadata[PROVENANCE_KEY.encode()])
    assert meta["n_samples"] == 64 and meta["seed"] == 7
    assert meta["c3_applied"] is False and meta["price_base_year_usd"] == 2024
    assert meta["variance_ddof"] == 1 and "s >= 1" in meta["summary_samples"]
    assert not list(out.glob("*.partial"))


@pytest.mark.unit
def test_a_masked_cell_member_has_no_row_in_any_f6_table(tmp_path):
    result, _ = _run(tmp_path, "solar", n=20, drop={(105, "m_a"), (110, "m_b")})
    summary = pd.read_parquet(result.lcoe_summary).astype({"member": str})
    assert len(summary) == 30 * 3 - 2
    assert summary[(summary.cell_id == 105) & (summary.member == "m_a")].empty
    supply = pd.read_parquet(result.supply_curve).astype({"member": str})
    assert (
        len(supply[supply.member == "m_a"]) == 29
        and 105 not in supply[supply.member == "m_a"].cell_id.tolist()
    )


@pytest.mark.unit
def test_zero_energy_gives_infinite_lcoe_a_persisted_count_and_leaves_other_cells_alone(tmp_path):
    """D-F6-007: the cell is not an error; its nominal and every draw are `+inf`, the mean and variance are NaN."""
    result, _ = _run(tmp_path, "wind", n=30, zero_energy_cell=104)
    summary = pd.read_parquet(result.lcoe_summary).astype({"member": str})
    row = summary[(summary.cell_id == 104) & (summary.member == "m_a")].iloc[0]
    assert np.isposinf([row.lcoe_nominal, row.lcoe_p10, row.lcoe_p50, row.lcoe_p90]).all()
    assert row.n_nonfinite == 30 and np.isnan(row.lcoe_mean) and np.isnan(row.lcoe_var)
    others = summary.drop(row.name)
    assert np.isfinite(others[["lcoe_nominal", "lcoe_mean", "lcoe_p90"]]).all().all()
    assert (others["n_nonfinite"] == 0).all()
    assert result.n_nonfinite_nominal == 1 and result.n_draw_nonfinite == 30


@pytest.mark.unit
def test_supply_curve_orders_cells_by_nominal_lcoe_with_cumulative_totals(tmp_path):
    result, _ = _run(tmp_path, "solar", n=10)
    supply = pd.read_parquet(result.supply_curve).astype({"member": str})
    summary = pd.read_parquet(result.lcoe_summary).astype({"member": str})
    potential = pd.read_parquet(tmp_path / "potential" / "potential_solar__central.parquet").astype(
        {"member": str}
    )
    for member, curve in supply.groupby("member"):
        assert curve["rank"].tolist() == list(range(1, 31))
        assert curve["lcoe_nominal"].is_monotonic_increasing
        nominal = summary[summary.member == member].set_index("cell_id")["lcoe_nominal"]
        pm = potential[potential.member == member].set_index("cell_id")
        np.testing.assert_allclose(curve["lcoe_nominal"], nominal.loc[curve.cell_id].to_numpy())
        np.testing.assert_allclose(curve["cum_P_GW"].iloc[-1] * 1e3, pm["P_MW"].sum(), rtol=1e-12)
        np.testing.assert_allclose(curve["cum_E_TWh"].iloc[-1] * 1e6, pm["E_MWh"].sum(), rtol=1e-12)
        assert (np.diff(curve["cum_P_GW"]) >= 0).all()


@pytest.mark.unit
def test_supply_curve_function_ties_by_cell_id_and_puts_infinite_last():
    curve = supply_curve(
        "m0",
        np.array([5, 3, 9, 4]),
        np.array([10.0, 10.0, np.inf, 8.0]),
        np.array([1000.0, 2000.0, 500.0, 100.0]),
        np.array([2e6, 1e6, 0.0, 3e6]),
    )
    assert curve["cell_id"].tolist() == [4, 3, 5, 9]
    assert curve["cum_P_GW"].tolist() == pytest.approx([0.1, 2.1, 3.1, 3.6])
    assert curve["cum_E_TWh"].tolist() == pytest.approx([3.0, 4.0, 6.0, 6.0])


# -- failures ---------------------------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("iso", ["BRA", "PRT", "IND"])
def test_real_countries_fail_loud_listing_the_missing_parameters_ranges_and_price_years(
    iso, registry, parameters, tmp_path
):
    """The parameters and ranges of the real countries are not entered yet; F6 says exactly which, before reading any input."""
    with pytest.raises(LcoeMissingInputError) as caught:
        build_lcoe(
            iso, registry, parameters.countries[iso], TECHS,
            sampler_seed=42, sampler_size=500, max_batch_gb=1.0,
            potential_dir=tmp_path / "none", candidates_dir=tmp_path / "none",
            climate_dir=tmp_path / "none", out_dir=tmp_path / "out",
        )  # fmt: skip
    message = str(caught.value)
    for tech in TECHS:
        for item in (
            f"{tech}: degradation_rate (pending_research)",
            f"{tech}: grid_cost_usd_per_mw_km (pending_research)",
            f"{tech}: substation_cost_usd_per_mw (pending_research)",
            f"{tech}: road_cost_usd_per_km (pending_research)",
            f"{tech}: opex_var_usd_per_mwh (pending_research)",
            f"{tech}: capex_usd_per_kw range (no range in parameters.json",
            f"{tech}: opex_fixed_frac range",
            f"{tech}: discount_rate range",
            f"{tech}: lifetime_years range",
            f"{tech}: capex_usd_per_kw price_year (is None, S-07 needs 2024)",
        ):
            assert item in message, item
    assert "gamma" in message and "eta_loss" in message
    assert not (tmp_path / "out").exists()
    assert caught.value.missing and all(m.split(":")[0] in TECHS for m in caught.value.missing)


@pytest.mark.unit
def test_a_cost_price_year_other_than_2024_is_refused_listing_the_parameter(registry, parameters):
    zzz = parameters.countries["ZZZ"].model_copy(deep=True)
    zzz.technologies.wind.road_cost_usd_per_km.price_year = 2020
    with pytest.raises(LcoeMissingInputError, match=r"road_cost_usd_per_km price_year \(is 2020"):
        resolve_technology_costs(
            "ZZZ", "wind", registry.technologies["wind"], zzz.technologies.wind
        )


@pytest.mark.unit
def test_a_range_outside_the_kernel_domain_is_refused_not_clipped(registry, parameters):
    zzz = parameters.countries["ZZZ"].model_copy(deep=True)
    zzz.technologies.wind.degradation_rate.range.max = 1.0
    zzz.technologies.wind.discount_rate.range.min = -0.01
    zzz.technologies.wind.lifetime_years.range.min = 0.0
    with pytest.raises(LcoeMissingInputError) as caught:
        resolve_technology_costs(
            "ZZZ", "wind", registry.technologies["wind"], zzz.technologies.wind
        )
    text = str(caught.value)
    assert "degradation outside [0, 1)" in text
    assert "negative discount rate" in text and "lifetime below one year" in text


@pytest.mark.unit
def test_a_stale_f5_table_is_refused(tmp_path):
    dirs = _stage(tmp_path, "solar")
    path = dirs["potential_dir"] / "potential_solar__central.parquet"
    table = pq.read_table(path)
    meta = dict(table.schema.metadata)
    meta[POTENTIAL_KEY.encode()] = json.dumps({"parameters": {"gamma": -0.0123}}).encode()
    pq.write_table(table.replace_schema_metadata(meta), path)
    registry = load_technologies(TECHNOLOGIES)
    with pytest.raises(LcoeInputError, match="rerun F5"):
        build_lcoe(
            "ZZZ", registry, load_parameters(PARAMETERS).countries["ZZZ"], ["solar"],
            sampler_seed=1, sampler_size=10, max_batch_gb=1.0, out_dir=tmp_path / "out", **dirs,
        )  # fmt: skip
    assert not list((tmp_path / "out").glob("*.parquet"))


@pytest.mark.unit
def test_a_cell_missing_from_the_candidates_or_the_forcing_is_refused(tmp_path):
    dirs = _stage(tmp_path, "wind")
    cpath = dirs["candidates_dir"] / "candidates_wind__central.parquet"
    pd.read_parquet(cpath).query("cell_id != 110").to_parquet(cpath)
    registry = load_technologies(TECHNOLOGIES)
    with pytest.raises(LcoeInputError, match="not in candidates_wind__central"):
        build_lcoe(
            "ZZZ", registry, load_parameters(PARAMETERS).countries["ZZZ"], ["wind"],
            sampler_seed=1, sampler_size=10, max_batch_gb=1.0, out_dir=tmp_path / "out", **dirs,
        )  # fmt: skip
    dirs = _stage(tmp_path / "again", "wind")
    fpath = dirs["climate_dir"] / "forcing.parquet"
    forcing = pd.read_parquet(fpath)
    forcing[~((forcing.cell_id == 111) & (forcing.member.astype(str) == "m_b"))].to_parquet(fpath)
    with pytest.raises(LcoeInputError, match="forcing.parquet lacks"):
        build_lcoe(
            "ZZZ", registry, load_parameters(PARAMETERS).countries["ZZZ"], ["wind"],
            sampler_seed=1, sampler_size=10, max_batch_gb=1.0, out_dir=tmp_path / "out2", **dirs,
        )  # fmt: skip


@pytest.mark.unit
def test_a_missing_f3_f4_or_f5_input_raises_file_not_found_after_the_parameter_check(
    tmp_path, registry, parameters
):
    with pytest.raises(FileNotFoundError, match="F6 input missing"):
        build_lcoe(
            "ZZZ", registry, parameters.countries["ZZZ"], ["wind"],
            sampler_seed=1, sampler_size=10, max_batch_gb=1.0,
            potential_dir=tmp_path / "x", candidates_dir=tmp_path / "x", climate_dir=tmp_path / "x",
            out_dir=tmp_path / "out",
        )  # fmt: skip


@pytest.mark.unit
def test_a_failed_run_leaves_no_table_that_looks_complete(tmp_path):
    """The writers drop their partial files on an error (A-09): a capacity factor above 1 under the sampled `eta_loss`."""
    dirs = _stage(tmp_path, "wind")
    path = dirs["potential_dir"] / "potential_wind__central.parquet"
    table = pd.read_parquet(path)
    table.loc[table.index[3], "CF"] = 0.999  # times eta_max / eta_nominal > 1
    meta = pq.read_schema(path).metadata
    write_table(
        table, path, schema_version=POTENTIAL_TABLE_SCHEMA_VERSION, row_model=PotentialRow,
        extra_metadata={POTENTIAL_KEY: meta[POTENTIAL_KEY.encode()].decode()},
    )  # fmt: skip
    registry = load_technologies(TECHNOLOGIES)
    out = tmp_path / "out"
    with pytest.raises(LcoeInputError, match="capacity factor above 1"):
        build_lcoe(
            "ZZZ", registry, load_parameters(PARAMETERS).countries["ZZZ"], ["wind"],
            sampler_seed=1, sampler_size=10, max_batch_gb=1.0, out_dir=out, **dirs,
        )  # fmt: skip
    assert not list(out.glob("*.parquet")) and not list(out.glob("*.partial"))


# -- the streaming writer ------------------------------------------------------------------------------------


@pytest.mark.unit
def test_table_writer_appends_chunks_validates_them_and_names_the_file_only_on_success(tmp_path):
    from geofrea.lcoe_modeling.table_schemas import LcoeSummaryRow

    frame = pd.DataFrame(
        {
            "cell_id": [1, 2],
            "member": ["m0", "m0"],
            "lcoe_nominal": [1.0, 2.0],
            "lcoe_mean": [1.0, 2.0],
            "lcoe_var": [0.0, 0.0],
            "lcoe_p10": [1.0, 2.0],
            "lcoe_p50": [1.0, 2.0],
            "lcoe_p90": [1.0, 2.0],
            "n_nonfinite": [0, 0],
        }
    )
    path = tmp_path / "t.parquet"
    with TableWriter(path, schema_version="9.9", row_model=LcoeSummaryRow) as writer:
        writer.write(frame)
        writer.write(frame.assign(cell_id=[3, 4]))
        assert not path.exists() and path.with_name("t.parquet.partial").exists()
    assert pq.read_table(path).num_rows == 4
    assert pq.read_schema(path).metadata[b"geofrea_schema_version"] == b"9.9"
    broken = tmp_path / "b.parquet"
    with (
        pytest.raises(RuntimeError, match="boom"),
        TableWriter(broken, schema_version="1", row_model=LcoeSummaryRow) as writer,
    ):
        writer.write(frame)
        raise RuntimeError("boom")
    assert not broken.exists() and not broken.with_name("b.parquet.partial").exists()
    with (
        pytest.raises(TableSchemaError),
        TableWriter(tmp_path / "c.parquet", schema_version="1", row_model=LcoeSummaryRow) as writer,
    ):
        writer.write(frame.drop(columns=["lcoe_p90"]))


@pytest.mark.unit
def test_table_writer_without_rows_needs_an_empty_frame(tmp_path):
    from geofrea.lcoe_modeling.pipeline import _empty_summary_frame
    from geofrea.lcoe_modeling.table_schemas import LcoeSummaryRow

    with (
        pytest.raises(TableSchemaError, match="no rows written"),
        TableWriter(tmp_path / "x.parquet", schema_version="1", row_model=LcoeSummaryRow),
    ):
        pass
    with TableWriter(
        tmp_path / "y.parquet",
        schema_version="1",
        row_model=LcoeSummaryRow,
        empty_frame=_empty_summary_frame(),
    ):
        pass
    assert pq.read_table(tmp_path / "y.parquet").num_rows == 0


# -- code hygiene ---------------------------------------------------------------------------------------------


@pytest.mark.unit
def test_no_technology_name_appears_in_lcoe_modeling(registry):
    """A-04: F6 code contains no technology names; a string literal or identifier equal to a registry key fails the test."""
    names = set(registry.technologies)
    offenders = []
    for path in sorted((REPO / "src" / "geofrea" / "lcoe_modeling").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.strip().lower() in names
            ):
                offenders.append((path.name, node.lineno, node.value))
            if isinstance(node, ast.Name | ast.Attribute):
                ident = node.id if isinstance(node, ast.Name) else node.attr
                if ident.lower() in names:
                    offenders.append((path.name, node.lineno, ident))
    assert not offenders, offenders


@pytest.mark.unit
def test_lcoe_dir_is_under_the_phase_outputs(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    assert lcoe_dir("ZZZ") == tmp_path / "outputs" / "ZZZ" / "lcoe_modeling" / "artifacts"
