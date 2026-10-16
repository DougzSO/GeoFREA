"""F7 on small hand-made tables: classes, rankings, truncation, null decision parameters, the `s0` invariant, failures (M-F7-01 to M-F7-11, V-03, A-09)."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
import yaml

from geofrea.core.config_loader import load_parameters, load_technologies
from geofrea.core.config_schemas import ExperimentsFile
from geofrea.core.tables import write_table
from geofrea.land_eligibility.scenarios import LAND_SCENARIOS
from geofrea.lcoe_modeling.pipeline import build_lcoe
from geofrea.robustness_analysis.decision import (
    RobustnessConfigError,
    RobustnessMissingInputError,
)
from geofrea.robustness_analysis.pipeline import (
    PROVENANCE_KEY,
    ROW_MODELS,
    build_robustness,
    robustness_dir,
)
from geofrea.technical_potential.pipeline import PROVENANCE_KEY as POTENTIAL_KEY
from geofrea.technical_potential.table_schemas import POTENTIAL_TABLE_SCHEMA_VERSION, PotentialRow

REPO = Path(__file__).resolve().parents[2]
CORE = ["m_a_ssp126_2041_2070", "m_a_ssp370_2041_2070", "m_b_ssp126_2041_2070"]
SENSITIVITY = ["m_a_ssp126_2071_2100", "m_b_ssp370_2071_2100"]
ALL_MEMBERS = ["m0", *CORE, *SENSITIVITY]
META = {
    CORE[0]: ("GCM-A", "SSP1-2.6", "2041-2070"),
    CORE[1]: ("GCM-A", "SSP3-7.0", "2041-2070"),
    CORE[2]: ("GCM-B", "SSP1-2.6", "2041-2070"),
    SENSITIVITY[0]: ("GCM-A", "SSP1-2.6", "2071-2100"),
    SENSITIVITY[1]: ("GCM-B", "SSP3-7.0", "2071-2100"),
}
N_CELLS = 20
IDS = np.arange(500, 500 + N_CELLS)


def _experiments(**sampler) -> ExperimentsFile:
    raw = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    raw["sampler"].update({"initial_size": 24, **sampler})
    # the real configuration excludes wind above 3000 m in F3 (OQ-058, COMMAND 46); these tests exercise the altitude-window machinery,
    # which a technology with a reporting sensitivity still has, so wind reports 3000 m as a sensitivity here
    raw["land_availability"]["technologies"]["wind"]["elevation_max_m"].update(
        {"nominal": None, "sensitivity": 3000.0}
    )
    raw["prim"]["bootstrap_replicates"] = (
        6  # the bootstrap of the pre-registered 200 replicates is tested apart
    )
    return ExperimentsFile.model_validate(raw)


def _target_of(experiments: ExperimentsFile, value, unit="GW", tech="wind") -> ExperimentsFile:
    """`experiments` with the national target of ZZZ (the one definition of the target, OQ-010) set for `tech`."""
    raw = experiments.model_dump(by_alias=True)
    empty = {"value": None, "unit": None, "source": None, "horizon": None, "alternatives": []}
    raw["national_targets"] = {
        "ZZZ": {
            "solar": empty,
            "wind": empty,
            tech: {
                "value": value,
                "unit": unit,
                "source": "test plan",
                "horizon": 2040,
                "alternatives": [],
            },
        }
    }
    return ExperimentsFile.model_validate(raw)


def _country(**decision):
    """The ZZZ parameters with the decision values replaced (None clears one)."""
    country = load_parameters(REPO / "config" / "parameters.json").countries["ZZZ"]
    techs = {}
    for tech in ("solar", "wind"):
        params = getattr(country.technologies, tech)
        updates = {
            key: getattr(params, key).model_copy(update={"value": value})
            for key, value in decision.items()
        }
        techs[tech] = params.model_copy(update=updates)
    return country.model_copy(
        update={"technologies": country.technologies.model_copy(update=techs)}
    )


CHANNELS = {"resource_rsds": True, "resource_tas": True, "resource_wind": True}
HAZARD_MEMBERS = (
    CORE[0],
    CORE[2],
)  # the members that carry the hazard channel when `hazard` is set


def _stage(
    tmp_path: Path,
    tech="wind",
    cf=None,
    absent=(),
    scenarios=LAND_SCENARIOS,
    hazard=False,
    no_wind=(),
):
    """F5-, F3- and F4-like inputs for 20 cells: `cf[(cell index, member)]` overrides a capacity factor, `absent` lists (cell index, member)."""
    cf = cf or {}
    rng = np.random.default_rng(21)
    registry = load_technologies(REPO / "config" / "technologies.yaml")
    zzz = getattr(
        load_parameters(REPO / "config" / "parameters.json").countries["ZZZ"].technologies, tech
    )
    energy_key = registry.technologies[tech].uncertain_parameters[
        -1
    ]  # the sampled parameter that scales the energy
    p_mw = rng.uniform(20.0, 300.0, N_CELLS)
    base_cf = rng.uniform(0.40, 0.55, N_CELLS)
    pieces, forcing = [], []
    for k, member in enumerate(ALL_MEMBERS):
        d_t = np.zeros(N_CELLS) if member == "m0" else rng.uniform(1.0, 3.0, N_CELLS)
        values = base_cf * (1.0 - 0.015 * k)
        for (index, name), value in cf.items():
            if name == member:
                values[index] = value
        keep = np.array([(i, member) not in absent for i in range(N_CELLS)])
        pieces.append(
            pd.DataFrame(
                {
                    "cell_id": IDS[keep].astype("int64"),
                    "member": pd.Categorical(
                        [member] * int(keep.sum()),
                        categories=[
                            m for m in ALL_MEMBERS if not (tech == "wind" and m in no_wind)
                        ],
                    ),  # F5 lists only the members of the technology
                    "P_MW": p_mw[keep],
                    "CF": values[keep],
                    "E_MWh": (p_mw * values * 8760.0)[keep],
                }
            )
        )
        forcing.append(
            pd.DataFrame(
                {
                    "cell_id": IDS[keep].astype("int64"),
                    "member": pd.Categorical([member] * int(keep.sum()), categories=ALL_MEMBERS),
                    "delta_rsds": np.ones(int(keep.sum())),
                    "dT": d_t[keep],
                    "delta_wind": np.full(int(keep.sum()), np.nan if member in no_wind else 1.0),
                }
            )
        )
    pdir, cdir, kdir = tmp_path / "potential", tmp_path / "candidates", tmp_path / "climate"
    for d in (pdir, cdir, kdir):
        d.mkdir(parents=True, exist_ok=True)
    meta = {
        POTENTIAL_KEY: json.dumps(
            {"parameters": {energy_key: float(getattr(zzz, energy_key).value)}}
        )
    }
    table = pd.concat(pieces, ignore_index=True)
    for scenario in scenarios:
        write_table(
            table,
            pdir / f"potential_{tech}__{scenario}.parquet",
            schema_version=POTENTIAL_TABLE_SCHEMA_VERSION,
            row_model=PotentialRow,
            extra_metadata=meta,
        )
        pd.DataFrame(
            {
                "cell_id": IDS,
                "lat_c": -5.0 + 0.05 * np.arange(N_CELLS),
                "lon_c": 20.0 + 0.05 * (np.arange(N_CELLS) % 4),
                "admin1_id": np.where(np.arange(N_CELLS) < 10, "A.1", "B.1"),
                "cell_area_km2": np.full(N_CELLS, 25.0),
                "dist_grid_km": rng.uniform(0.0, 120.0, N_CELLS),
                "dist_road_km": rng.uniform(0.0, 30.0, N_CELLS),
                "elevation_m": np.linspace(
                    100.0, 3600.0, N_CELLS
                ),  # the last cells lie above the 3000 m of the wind sensitivity (OQ-058)
            }
        ).to_parquet(cdir / f"candidates_{tech}__{scenario}.parquet")
    pd.concat(forcing, ignore_index=True).to_parquet(kdir / "forcing.parquet")
    if hazard:  # two members carry the hazard channel; the heat and rain indicators grow with the cell index, the gust is constant
        n = np.arange(N_CELLS, dtype="float64")
        pieces = []
        for member in HAZARD_MEMBERS:
            bump = 3.0 if member == CORE[2] else 0.0
            pieces.append(
                pd.DataFrame(
                    {
                        "cell_id": IDS.astype("int64"),
                        "member": member,
                        "tx35_days": 10.0 + n + bump,
                        "tx35_days_ref": 2.0 + n,
                        "tx40_days": np.zeros(N_CELLS),
                        "tx40_days_ref": np.zeros(N_CELLS),
                        "rx5day_mm": np.full(N_CELLS, 10.0),
                        "rx5day_mm_ref": np.full(N_CELLS, 10.0),
                        "wet_p95_exceed_freq": np.full(N_CELLS, 0.05),
                        "wet_days_per_year_ref": np.full(N_CELLS, 100.0),
                        "gust_mean_annual_max_ms": np.full(N_CELLS, 10.0),
                    }
                )
            )
        pd.concat(pieces, ignore_index=True).to_parquet(kdir / "hazard_context.parquet")
    else:
        pd.DataFrame(
            {"cell_id": pd.Series(dtype="int64"), "member": pd.Series(dtype="object")}
        ).to_parquet(
            kdir / "hazard_context.parquet"
        )  # no member of these tests carries the hazard channel
    members = [{"member": "m0", "window": "1995-2014", "channels": CHANNELS | {"hazard": False}}]
    for name, (gcm, ssp, window) in META.items():
        members.append(
            {
                "member": name,
                "gcm": gcm,
                "ssp": ssp,
                "window": window,
                "channels": CHANNELS
                | {
                    "resource_wind": name not in no_wind,
                    "hazard": hazard and name in HAZARD_MEMBERS,
                },
            }
        )
    (kdir / "members.yaml").write_text(yaml.safe_dump({"members": members}), encoding="utf-8")
    return {"potential_dir": pdir, "candidates_dir": cdir, "climate_dir": kdir}


def _run(tmp_path, tech="wind", country=None, experiments=None, gb=1.0, **stage):
    dirs = _stage(tmp_path / "in", tech, **stage)
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    f6 = build_lcoe(
        "ZZZ", load_technologies(REPO / "config" / "technologies.yaml"), country or _country(), [tech],
        sampler_seed=42, sampler_size=24, max_batch_gb=gb, out_dir=tmp_path / "f6", **dirs,
    )  # fmt: skip
    dirs["lcoe_dir"] = Path(f6.technologies[tech].lcoe_summary).parent
    result = build_robustness(
        "ZZZ",
        load_technologies(REPO / "config" / "technologies.yaml"),
        country or _country(),
        [tech],
        experiments or _experiments(),
        max_batch_gb=gb,
        scale_id="0p05deg",
        out_dir=out,
        **dirs,
    )
    return result.technologies[tech], out, dirs


def _table(entry, role="core") -> pd.DataFrame:
    return pd.read_parquet(entry.windows[role].tables["robustness"])


def _meta(path: Path) -> dict:
    return json.loads(pq.read_schema(path).metadata[PROVENANCE_KEY.encode()])


# -- the classes of the candidates ----------------------------------------------------------------------------


@pytest.mark.unit
def test_every_candidate_has_a_class_and_the_classes_follow_m_f7_01(tmp_path):
    cf_min = 0.30  # the ZZZ test value for wind
    cf = {(3, "m0"): 0.2, (5, CORE[1]): 0.2, (7, CORE[2]): 0.2}
    entry, _, _ = _run(tmp_path, cf=cf, absent=[(11, CORE[0])])
    table = _table(entry)
    assert len(table) == N_CELLS and table["cell_id"].is_unique
    by_id = table.set_index("cell_id")["cell_class"]
    assert (
        by_id[IDS[11]] == "climate_data_invalid"
    )  # a member of the window has no row for it (M-F4-07)
    assert by_id[IDS[3]] == "infeasible_at_f0"  # CF(m0) below CF_min
    assert by_id[IDS[5]] == "climate_fragile" and by_id[IDS[7]] == "climate_fragile"
    assert (by_id.drop([IDS[11], IDS[3], IDS[5], IDS[7]]) == "ranked").all()
    fragile = table.set_index("cell_id").loc[[IDS[5], IDS[7]]]
    assert fragile["failing_members"].map(list).tolist() == [[CORE[1]], [CORE[2]]]
    assert fragile["mr"].isna().all() and fragile["robust_rank"].isna().all()
    assert fragile["lcoe_nominal"].notna().all() and fragile["nominal_rank"].notna().all()
    window = entry.windows["core"]
    assert window.class_counts == {
        "ranked": 16, "climate_fragile": 2, "climate_data_invalid": 1, "infeasible_at_f0": 1,
    }  # fmt: skip
    assert window.n_f7_set == 18
    assert cf_min == 0.30


@pytest.mark.unit
def test_ranks_are_complete_orderings_of_their_sets_and_ties_are_broken_by_cell_id(tmp_path):
    entry, _, _ = _run(tmp_path, cf={(5, CORE[1]): 0.2})
    table = _table(entry).sort_values("cell_id")
    f7 = table[table["cell_class"].isin(["ranked", "climate_fragile"])]
    assert sorted(f7["nominal_rank"]) == list(range(1, len(f7) + 1))
    ranked = table[table["cell_class"] == "ranked"]
    for column in ("robust_rank", "climate_only_rank", "techno_only_rank"):
        assert sorted(ranked[column]) == list(range(1, len(ranked) + 1))
    # the robust rank is the order of MR, then SR high first, then cell_id
    order = ranked.sort_values(["mr", "sr", "cell_id"], ascending=[True, False, True])
    assert order["robust_rank"].tolist() == list(range(1, len(ranked) + 1))
    assert (ranked["mr"] >= 0).all() and ranked["sr"].between(0, 1).all()
    # V-03: every cell of the F7 set is ranked or climate-fragile, no ranked cell has an infinite MR
    assert np.isfinite(ranked["mr"]).all()


@pytest.mark.unit
def test_top_k_is_the_best_p_k_percent_of_the_f7_set_with_the_same_k_for_both_rankings(tmp_path):
    entry, _, _ = _run(tmp_path, cf={(5, CORE[1]): 0.2})  # p_k is 25 percent in the ZZZ block
    table = _table(entry)
    n_f7 = (table["cell_class"].isin(["ranked", "climate_fragile"])).sum()
    k = int(np.ceil(0.25 * n_f7))
    assert entry.windows["core"].k == k
    assert table["topk_nominal"].sum() == k and table["topk_robust"].sum() == k
    nominal = table[table["topk_nominal"].fillna(False).astype(bool)]
    assert nominal["nominal_rank"].max() == k
    robust = table[table["topk_robust"].fillna(False).astype(bool)]
    assert robust["robust_rank"].max() == k
    assert not entry.windows["core"].top_k_truncated


@pytest.mark.unit
def test_a_top_k_larger_than_the_ranked_set_takes_the_whole_set_and_says_so(tmp_path):
    country = _country(top_k_percent=100.0)
    entry, _, _ = _run(tmp_path, country=country, cf={(5, CORE[1]): 0.2, (6, CORE[0]): 0.2})
    window = entry.windows["core"]
    table = pd.read_parquet(window.tables["robustness"])
    assert window.top_k_truncated and window.k == 20
    assert table["topk_robust"].sum() == 18  # the two fragile cells are not ranked
    assert table["topk_nominal"].sum() == 20
    assert _meta(window.tables["robustness"])["top_k_truncated"] is True


@pytest.mark.unit
def test_the_capacity_target_takes_cells_along_the_robust_rank_until_it_is_met(tmp_path):
    entry, _, _ = _run(tmp_path, experiments=_target_of(_experiments(), 0.8))
    table = _table(entry)
    taken = table[table["topk_capacity_target"].fillna(False).astype(bool)].sort_values(
        "robust_rank"
    )
    assert taken["robust_rank"].tolist() == list(range(1, len(taken) + 1))
    assert taken["p_mw"].sum() / 1000.0 >= 0.8
    assert taken["p_mw"].iloc[:-1].sum() / 1000.0 < 0.8  # the fewest cells
    assert entry.windows["core"].target_unreachable is False
    huge = _run(tmp_path / "b", experiments=_target_of(_experiments(), 1e6))[0]
    assert huge.windows["core"].target_unreachable is True
    assert _table(huge)["topk_capacity_target"].sum() == 20  # all ranked cells


@pytest.mark.unit
def test_a_target_in_twh_per_year_has_no_capacity_target_top_k_and_says_why(tmp_path):
    entry, _, _ = _run(tmp_path, experiments=_target_of(_experiments(), 5.0, unit="TWh/year"))
    assert _table(entry)["topk_capacity_target"].isna().all()
    reasons = [s["reason"] for s in entry.skipped if s["open_question"] == "OQ-010"]
    assert any("TWh/year" in reason and "no registered conversion" in reason for reason in reasons)


@pytest.mark.unit
def test_the_target_has_one_definition_the_national_targets_of_experiments_yaml():
    """No parameter block of `parameters.json` carries `capacity_target_gw`, and `decision_values` derives it from `national_targets` only."""
    from geofrea.core.schemas import SolarParams, WindParams
    from geofrea.robustness_analysis.decision import capacity_target_gw

    raw = (REPO / "config" / "parameters.json").read_text(encoding="utf-8")
    assert "capacity_target_gw" not in raw
    assert "capacity_target_gw" not in SolarParams.model_fields  # nor does the schema admit it
    assert "capacity_target_gw" not in WindParams.model_fields
    for path in (REPO / "src").rglob("*.py"):
        if path.name == "decision.py":
            continue
        assert "tech_params.capacity_target_gw" not in path.read_text(encoding="utf-8"), path
    assert capacity_target_gw(None)[0] is None
    gw = _target_of(_experiments(), 0.8).national_targets["ZZZ"]["wind"]
    tw = _target_of(_experiments(), 3.0, unit="TWh/year").national_targets["ZZZ"]["wind"]
    assert capacity_target_gw(gw) == (0.8, None)
    value, why = capacity_target_gw(tw)
    assert value is None and "TWh/year" in why


# -- null decision parameters (D-F7-023) ------------------------------------------------------------------------


@pytest.mark.unit
def test_a_null_tau_skips_sr_and_a_null_p_k_skips_the_top_k_flags_and_both_are_listed(
    tmp_path, caplog
):
    country = _country(tau_lcoe_usd_per_mwh=None, top_k_percent=None)
    with caplog.at_level("WARNING"):
        entry, _, _ = _run(tmp_path, country=country)
    table = _table(entry)
    assert table["sr"].isna().all() and table["mr"].notna().any()
    for column in (
        "topk_nominal",
        "topk_robust",
        "topk_climate_only",
        "topk_techno_only",
        "topk_capacity_target",
    ):
        assert table[column].isna().all(), column
    assert entry.windows["core"].k is None
    skipped = {(s["open_question"]) for s in entry.skipped}
    assert {"OQ-008", "OQ-021", "OQ-010"} <= skipped
    assert all(s["reason"] for s in entry.skipped)
    assert any("skipped" in r.message and "OQ-021" in r.message for r in caplog.records)
    assert _meta(entry.windows["core"].tables["robustness"])["skipped_outputs"]
    assert table["robust_rank"].notna().any()  # the ranking by MR does not need p_k


@pytest.mark.unit
def test_without_cf_min_or_with_another_q_ref_f7_refuses_before_reading_anything(tmp_path):
    registry = load_technologies(REPO / "config" / "technologies.yaml")
    country = _country(cf_min=None)
    with pytest.raises(RobustnessMissingInputError) as info:
        build_robustness(
            "ZZZ", registry, country, ["solar", "wind"], _experiments(),
            max_batch_gb=1.0, scale_id="0p05deg",
            potential_dir=tmp_path / "none", candidates_dir=tmp_path / "none", climate_dir=tmp_path / "none",
        )  # fmt: skip
    assert len(info.value.missing) == 2
    assert all("cf_min" in m and "OQ-008" in m for m in info.value.missing)
    raw = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    raw["thresholds"]["regret_quantile"] = 0.01
    with pytest.raises(RobustnessConfigError, match="OQ-020"):
        build_robustness(
            "ZZZ", registry, _country(), ["wind"], ExperimentsFile.model_validate(raw),
            max_batch_gb=1.0, scale_id="0p05deg",
        )  # fmt: skip


@pytest.mark.unit
def test_the_real_countries_fail_loud_with_the_f6_items_and_cf_min(tmp_path):
    registry = load_technologies(REPO / "config" / "technologies.yaml")
    parameters = load_parameters(REPO / "config" / "parameters.json")
    for iso in ("BRA", "PRT", "IND"):
        with pytest.raises(RobustnessMissingInputError) as info:
            build_robustness(
                iso, registry, parameters.countries[iso], ["solar", "wind"], _experiments(),
                max_batch_gb=1.0, scale_id="0p05deg",
            )  # fmt: skip
        text = str(info.value)
        assert text.count("cf_min") == 2 and "OQ-008" in text
        # Groups 1 and 2 are recorded: what stays open is the Group 3 costs and the F7 thresholds (the discount rate is recorded)
        assert "grid_cost_usd_per_mw_km" in text
        assert "capex_usd_per_kw" not in text and len(info.value.missing) >= 18


# -- the s0 invariant, determinism, memory, windows ---------------------------------------------------------


@pytest.mark.unit
def test_the_nominal_lcoe_of_f7_equals_the_lcoe_nominal_of_f6_for_every_member_and_cell(tmp_path):
    entry, _, dirs = _run(tmp_path)
    summary = pd.read_parquet(dirs["lcoe_dir"] / "lcoe_summary_wind.parquet").astype(
        {"member": str}
    )
    nominal = pd.read_parquet(entry.windows["core"].tables["nominal_lcoe_by_member"]).astype(
        {"member": str}
    )
    merged = nominal.merge(
        summary, on=["cell_id", "member"], suffixes=("", "_f6"), validate="one_to_one"
    )
    assert len(merged) == len(nominal) == 20 * 4
    np.testing.assert_allclose(merged["lcoe_nominal"], merged["lcoe_nominal_f6"], rtol=1e-13)


@pytest.mark.unit
def test_the_results_do_not_depend_on_the_memory_budget(tmp_path):
    big, _, _ = _run(tmp_path / "a", gb=1.0)
    small, _, _ = _run(tmp_path / "b", gb=1e-5)  # a block of a few cells
    a, b = _table(big), _table(small)
    pd.testing.assert_frame_equal(
        a.drop(columns="failing_members"), b.drop(columns="failing_members"), rtol=1e-12
    )


@pytest.mark.unit
def test_wind_repeats_the_core_window_without_the_cells_above_the_altitude_sensitivity_and_solar_does_not(
    tmp_path,
):
    """OQ-058: the wind core window is run again on the candidates not above 3000 m (cells 16 to 19 of the fixture are), with the whole analysis."""
    entry, _, dirs = _run(tmp_path / "w")
    core, below = entry.windows["core"], entry.windows["core_below_3000m"]
    elevation = pd.read_parquet(
        dirs["candidates_dir"] / "candidates_wind__central.parquet"
    ).set_index("cell_id")["elevation_m"]
    kept = elevation.index[elevation <= 3000.0]
    assert (
        0 < len(kept) < N_CELLS and below.n_candidates == len(kept) and below.n_f7_set == len(kept)
    )
    assert core.n_candidates == N_CELLS
    table = pd.read_parquet(below.tables["robustness"])
    assert sorted(table["cell_id"]) == sorted(kept) and table["cell_class"].notna().all()
    meta = _meta(below.tables["robustness"])
    assert meta["window_role"] == "core_below_3000m" and meta["window"] == "2041-2070"
    # the rest of the analysis ran on the same cells: the nominal LCOE of a kept cell is the one of the full run
    full = pd.read_parquet(core.tables["robustness"]).set_index("cell_id")
    pd.testing.assert_series_equal(
        full.loc[kept, "lcoe_nominal"],
        table.set_index("cell_id")["lcoe_nominal"].loc[kept],
        check_names=False,
    )
    solar, _, _ = _run(tmp_path / "s", tech="solar")
    assert set(solar.windows) == {"core", "sensitivity"}


@pytest.mark.unit
def test_the_sensitivity_window_has_its_own_set_and_files(tmp_path):
    entry, out, _ = _run(tmp_path, absent=[(2, SENSITIVITY[0])])
    core, sens = entry.windows["core"], entry.windows["sensitivity"]
    assert core.n_f7_set == 20 and sens.n_f7_set == 19
    assert (
        sens.class_counts["climate_data_invalid"] == 1
        and core.class_counts["climate_data_invalid"] == 0
    )
    names = sorted(p.name for p in out.iterdir())
    assert names == sorted(
        f"{kind}_wind__{role}.parquet"
        for kind in ROW_MODELS
        for role in (
            "core",
            "sensitivity",
            "core_below_3000m",
        )  # the third is the altitude sensitivity of wind (OQ-058)
    )
    meta = _meta(core.tables["robustness"])
    assert (
        meta["provisional"] is False
        and meta["window"] == "2041-2070"
        and meta["n_core_members"] == 3
    )
    assert meta["statistics_over"].startswith("draws s >= 1")


@pytest.mark.unit
def test_an_empty_f7_set_writes_the_classes_only_and_warns(tmp_path, caplog):
    """No candidate is feasible at f0: every result column is null, the classes say why, and the log says so (A-09)."""
    country = _country(cf_min=0.99)  # no cell reaches it at m0
    with caplog.at_level("WARNING"):
        entry, _, _ = _run(tmp_path, country=country)
    window = entry.windows["core"]
    table = pd.read_parquet(window.tables["robustness"])
    assert window.n_f7_set == 0 and window.class_counts["infeasible_at_f0"] == N_CELLS
    assert (table["cell_class"] == "infeasible_at_f0").all() and len(table) == N_CELLS
    for column in ("lcoe_nominal", "mr", "sr", "nominal_rank", "robust_rank", "topk_robust"):
        assert table[column].isna().all(), column
    assert len(pd.read_parquet(window.tables["nominal_lcoe_by_member"])) == 0
    assert any("F7 set is empty" in r.message for r in caplog.records)
    assert _meta(window.tables["robustness"])["empty_f7_set"] is True


@pytest.mark.unit
def test_a_missing_input_raises_file_not_found_after_the_parameter_check(tmp_path):
    with pytest.raises(FileNotFoundError, match="F7 input missing"):
        build_robustness(
            "ZZZ", load_technologies(REPO / "config" / "technologies.yaml"), _country(), ["wind"],
            _experiments(), max_batch_gb=1.0, scale_id="0p05deg",
            potential_dir=tmp_path, candidates_dir=tmp_path, climate_dir=tmp_path,
        )  # fmt: skip


@pytest.mark.unit
def test_no_technology_name_appears_in_robustness_analysis():
    """A-04: F7 code contains no technology names."""
    registry = load_technologies(REPO / "config" / "technologies.yaml")
    names = set(registry.technologies)
    offenders = []
    for path in sorted((REPO / "src" / "geofrea" / "robustness_analysis").glob("*.py")):
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
def test_robustness_dir_is_under_the_phase_outputs(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    assert (
        robustness_dir("ZZZ") == tmp_path / "outputs" / "ZZZ" / "robustness_analysis" / "artifacts"
    )


# -- futures, hypotheses, T-R12 and T-R10 (F7-B) -------------------------------------------------------------


def _with_rules(**rules) -> ExperimentsFile:
    raw = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    raw["sampler"]["initial_size"] = 24
    raw["prim"]["bootstrap_replicates"] = 6
    raw["hypothesis_rules"] = {f"H{i}": rules.get(f"H{i}") for i in range(1, 6)} | {
        name: rule for name, rule in rules.items() if not re.fullmatch(r"H\d", name)
    }  # a test rule goes under another key, because every hypothesis has its own rule
    return ExperimentsFile.model_validate(raw)


@pytest.mark.unit
def test_the_futures_table_has_one_row_per_member_and_sample_with_sample_zero_nominal(tmp_path):
    entry, _, _ = _run(tmp_path)
    futures = pd.read_parquet(entry.windows["core"].tables["futures"])
    assert len(futures) == len(CORE) * (24 + 1)
    assert set(futures["member"].astype(str)) == set(CORE)
    assert (futures.groupby("member", observed=True)["sample"].min() == 0).all()


@pytest.mark.unit
def test_without_a_pre_registered_rule_every_statistic_has_no_verdict_and_a_warning_says_so(
    tmp_path, caplog
):
    entry, _, _ = _run(tmp_path, experiments=_with_rules())
    hypothesis = pd.read_parquet(entry.windows["core"].tables["hypothesis"])
    assert set(hypothesis["hypothesis"]) == {"H1", "H2", "H3", "H4", "H5", "RQ4"}
    assert hypothesis["verdict"].isna().all() and hypothesis["verdict_reason"].notna().all()
    assert sum("no pre-registered rule" in r.message for r in caplog.records) >= 5


@pytest.mark.unit
def test_a_pre_registered_rule_gives_met_or_not_met_and_never_for_the_other_statistics(tmp_path):
    rule = {"statistic": "mr_sr_kendall_tau_b", "comparison": "ge", "threshold": -2.0}
    entry, _, _ = _run(tmp_path, experiments=_with_rules(RQ4=[rule]))
    table = pd.read_parquet(entry.windows["core"].tables["hypothesis"])
    named = table[table["statistic"] == "mr_sr_kendall_tau_b"].iloc[0]
    assert named["verdict"] == "met" and named["rule"]
    assert (
        table[table["statistic"] != "mr_sr_kendall_tau_b"]
        .query("hypothesis == 'RQ4'")["verdict"]
        .isna()
        .all()
    )
    impossible = {"statistic": "mr_sr_kendall_tau_b", "comparison": "lt", "threshold": -2.0}
    other, _, _ = _run(tmp_path / "b", experiments=_with_rules(RQ4=[impossible]))
    again = pd.read_parquet(other.windows["core"].tables["hypothesis"])
    assert again.set_index("statistic").loc["mr_sr_kendall_tau_b", "verdict"] == "not_met"


@pytest.mark.unit
def test_a_rule_that_names_an_unknown_statistic_fails_loudly(tmp_path):
    from geofrea.robustness_analysis.hypotheses import HypothesisRuleError

    rule = {"statistic": "h9_nothing", "comparison": "ge", "threshold": 0.0}
    with pytest.raises(HypothesisRuleError):
        _run(tmp_path, experiments=_with_rules(RQ4=[rule]))


@pytest.mark.unit
def test_the_potential_below_tau_of_the_tables_matches_the_evaluation_and_covers_three_scenarios(
    tmp_path,
):
    entry, _, _ = _run(tmp_path)  # the run itself raises when the two disagree (V-03)
    table = pd.read_parquet(entry.windows["core"].tables["potential_below_tau"])
    nominal = table[table["basis"] == "nominal"]
    assert set(nominal["land_scenario"]) == set(LAND_SCENARIOS)
    assert set(table[table["basis"] != "nominal"]["basis"]) == {"p10", "p50", "p90"}
    draws = table[table["basis"].isin(["p10", "p50", "p90"])].pivot(
        index="member", columns="basis", values="potential_gw"
    )
    assert (draws["p10"] <= draws["p50"]).all() and (draws["p50"] <= draws["p90"]).all()


@pytest.mark.unit
def test_exposure_is_written_empty_and_flagged_when_no_member_carries_the_hazard_channel(tmp_path):
    entry, _, _ = _run(tmp_path)
    path = entry.windows["core"].tables["hazard_exposure"]
    assert len(pd.read_parquet(path)) == 0
    flag = json.loads(pq.read_schema(path).metadata[b"geofrea_robustness_skipped"])
    assert "hazard channel" in flag["reason"] and flag["open_question"] == "OQ-007"


# -- PRIM and the agreement of MR and SR (F7-C) -------------------------------------------------------------


def _with_prim(**prim) -> ExperimentsFile:
    """The shipped configuration with a bigger sample and the replicates of the bootstrap reduced (the pre-registered value is tested apart)."""
    raw = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    raw["sampler"]["initial_size"] = 60
    raw["prim"].update({"bootstrap_replicates": 6, **prim})
    return ExperimentsFile.model_validate(raw)


@pytest.mark.unit
def test_the_kendall_statistic_equals_scipy_on_the_ranked_cells_and_counts_the_tied_pairs(tmp_path):
    from scipy.stats import kendalltau

    entry, _, _ = _run(tmp_path)
    robustness = _table(entry)
    ranked = robustness[robustness["cell_class"] == "ranked"]
    expected = kendalltau(ranked["mr"], -ranked["sr"], variant="b").statistic
    hypothesis = pd.read_parquet(entry.windows["core"].tables["hypothesis"]).set_index("statistic")
    n = len(ranked)
    assert hypothesis.loc["mr_sr_kendall_tau_b", "value"] == pytest.approx(expected)
    assert hypothesis.loc["mr_sr_pairs", "value"] == n * (n - 1) / 2
    by_hand = sum(c * (c - 1) // 2 for c in ranked["mr"].value_counts())
    assert hypothesis.loc["mr_sr_tied_pairs_mr", "value"] == by_hand


# -- H1: the scores per SSP, C_k, V_k and the verdict (OQ-050, H1) ---------------------------------------------


def _skip_note(path: Path) -> dict:
    return json.loads(pq.read_schema(path).metadata[b"geofrea_robustness_skipped"])


@pytest.mark.unit
def test_the_scores_per_ssp_agree_with_the_member_level_results_and_the_h1_tables_carry_the_rule(
    tmp_path,
):
    entry, _, _ = _run(tmp_path)
    tables = entry.windows["core"].tables
    robustness = _table(entry).set_index("cell_id")
    scores = pd.read_parquet(tables["ssp_scores"])
    assert set(scores["ssp"]) == {"SSP1-2.6", "SSP3-7.0"}
    ranked = robustness[robustness["cell_class"] == "ranked"]
    best = scores.groupby("cell_id")[["mr_ssp", "r_clim_ssp"]].max().loc[ranked.index]
    assert np.allclose(best["mr_ssp"], ranked["mr"])  # the maximum of MR over the SSPs is MR
    assert np.allclose(best["r_clim_ssp"], ranked["mr_clim"])  # and of R^clim is MR_clim (M-F7-06)
    for _, one in scores.groupby("ssp"):  # a complete ordering of the ranked set in every SSP
        assert sorted(one["mr_ssp_rank"].dropna()) == list(range(1, len(ranked) + 1))
        assert sorted(one["r_clim_ssp_rank"].dropna()) == list(range(1, len(ranked) + 1))
    assert set(scores["r_clim_gcm"].dropna()) <= {"GCM-A", "GCM-B"}

    summary = pd.read_parquet(tables["h1_summary"])
    primary = summary[summary["primary"]].iloc[0]
    assert summary["primary"].sum() == 1 and primary["variant"] == "primary"
    assert primary["k"] == entry.windows["core"].k and primary["m"] == primary["k"]
    assert (primary["alpha"], primary["beta"]) == (0.60, 0.20)
    assert primary["reference"] == pytest.approx(
        (primary["k"] / entry.windows["core"].n_f7_set) ** 2
    )
    assert bool(primary["h1a_holds"]) == (primary["c_k"] >= 0.60)
    assert bool(primary["h1b_holds"]) == (primary["v_k"] >= 0.20)
    assert (
        primary["verdict"]
        == {2: "supported", 1: "partially_supported", 0: "not_supported"}[
            int(primary["h1a_holds"]) + int(primary["h1b_holds"])
        ]
    )
    assert {
        "top_k_percent_5", "top_k_percent_10", "top_k_percent_20",
        "tolerance_0.5k", "tolerance_1k", "tolerance_2k",
    } <= set(summary["variant"])  # fmt: skip

    sites = pd.read_parquet(tables["h1_sites"])
    assert len(sites) == primary["k"] and sites["vulnerable"].sum() == primary["n_vulnerable"]
    hypothesis = pd.read_parquet(tables["hypothesis"]).set_index("statistic")
    for name, holds in (("h1a_core_share", "h1a_holds"), ("h1b_vulnerable_share", "h1b_holds")):
        assert hypothesis.loc[name, "verdict"] == ("met" if primary[holds] else "not_met")
    assert hypothesis.loc["h1a_core_share", "value"] == pytest.approx(primary["c_k"])
    assert hypothesis.loc["h1b_vulnerable_share", "value"] == pytest.approx(primary["v_k"])
    descriptive_rows = hypothesis.filter(like="h1_ssp_", axis=0)
    assert len(descriptive_rows) == 2 and descriptive_rows["verdict"].isna().all()
    assert hypothesis.loc["h1_subhypotheses_holding", "note"] == f"verdict: {primary['verdict']}"


@pytest.mark.unit
def test_a_climate_fragile_cell_in_the_nominal_top_k_is_vulnerable_without_a_displacement(tmp_path):
    first, _, _ = _run(tmp_path / "a")
    best = _table(first).query("nominal_rank == 1").iloc[0]["cell_id"]
    entry, _, _ = _run(tmp_path / "b", cf={(int(best) - 500, CORE[1]): 0.2})
    sites = pd.read_parquet(entry.windows["core"].tables["h1_sites"]).set_index("cell_id")
    fragile = sites.loc[best]
    assert fragile["nominal_rank"] == 1 and bool(fragile["vulnerable"])
    assert fragile["reason"] == "climate_fragile" and pd.isna(fragile["displacement"])
    scores = pd.read_parquet(entry.windows["core"].tables["ssp_scores"])
    assert scores[scores["cell_id"] == best]["mr_ssp"].isna().all()


@pytest.mark.unit
def test_a_null_h1_rule_writes_the_h1_tables_empty_and_names_oq_050(tmp_path, caplog):
    entry, _, _ = _run(tmp_path, experiments=_with_rules())
    for kind in ("ssp_scores", "h1_sites", "h1_summary"):
        path = entry.windows["core"].tables[kind]
        assert len(pd.read_parquet(path)) == 0
        assert _skip_note(path)["open_question"] == "OQ-050"
    assert any(i["open_question"] == "OQ-050" for i in entry.skipped)


@pytest.mark.unit
def test_a_null_p_k_writes_the_h1_tables_empty_and_names_oq_021(tmp_path):
    entry, _, _ = _run(tmp_path, country=_country(top_k_percent=None))
    for kind in ("ssp_scores", "h1_sites", "h1_summary"):
        path = entry.windows["core"].tables[kind]
        assert len(pd.read_parquet(path)) == 0 and _skip_note(path)["open_question"] == "OQ-021"
    hypothesis = pd.read_parquet(entry.windows["core"].tables["hypothesis"])
    assert (
        not hypothesis["statistic"].str.startswith("h1").any()
    )  # no H1 row, so its rule names nothing


# -- H2: the cell and the Admin1 selections, O and the verdict (OQ-050, H2) -------------------------------------


@pytest.mark.unit
def test_the_h2_tables_agree_with_the_robust_top_k_and_carry_the_rule(tmp_path):
    entry, _, _ = _run(tmp_path)
    tables = entry.windows["core"].tables
    robustness = _table(entry)
    ranked = robustness[robustness["cell_class"] == "ranked"]
    summary = pd.read_parquet(tables["h2_summary"])
    primary = summary[summary["primary"]].iloc[0]
    assert summary["primary"].sum() == 1 and primary["variant"] == "primary"
    assert (primary["gamma"], primary["partition"]) == (0.30, "admin1")
    # T is the capacity of the robust top-k set of H1, Q_max the capacity of the ranked set
    assert primary["target_mw"] == pytest.approx(
        float(robustness[robustness["topk_robust"].fillna(False).astype(bool)]["p_mw"].sum())
    )
    assert primary["q_max_mw"] == pytest.approx(float(ranked["p_mw"].sum()))
    assert primary["overlap_ref"] == pytest.approx(primary["target_mw"] / primary["q_max_mw"])
    assert 0.0 <= primary["overlap"] <= 1.0 and primary["robustness_penalty"] >= -1e-12
    assert primary["verdict"] == (
        "not_testable"
        if primary["overlap_ref"] >= 0.30
        else ("supported" if primary["overlap"] < 0.30 else "not_supported")
    )
    assert {f"gamma_{g:.2f}" for g in (0.10, 0.50, 0.70)} <= set(summary["variant"])
    assert {"top_k_percent_5", "top_k_percent_10", "top_k_percent_20", "median_statistic"} <= set(
        summary["variant"]
    )
    regions = pd.read_parquet(tables["h2_regions"])
    assert regions["selected_cell_mw"].sum() == pytest.approx(primary["target_mw"])
    assert regions["selected_admin_mw"].sum() == pytest.approx(primary["target_mw"])
    assert regions["share_cell"].sum() == pytest.approx(1.0)
    assert sorted(regions["position"]) == list(range(1, len(regions) + 1))
    assert (regions["fraction_taken"].between(0, 1)).all()
    hypothesis = pd.read_parquet(tables["hypothesis"]).set_index("statistic")
    shown = hypothesis.loc["h2_overlap_index"]
    assert shown["value"] == pytest.approx(primary["overlap"])
    assert shown["verdict"] == {
        "supported": "met",
        "not_supported": "not_met",
        "not_testable": None,
    }[primary["verdict"]] or (pd.isna(shown["verdict"]) and primary["verdict"] == "not_testable")
    assert hypothesis.loc["h2_overlap_reference", "value"] == pytest.approx(primary["overlap_ref"])
    assert (
        "h2_mr_median" in hypothesis.index
    )  # the earlier dispersion statistics stay as descriptive rows
    assert "descriptive" in hypothesis.loc["h2_mr_median", "note"]
    assert pd.isna(hypothesis.loc["h2_mr_median", "verdict"])


@pytest.mark.unit
def test_a_null_h2_rule_or_a_null_p_k_writes_the_h2_tables_empty_and_names_the_question(tmp_path):
    entry, _, _ = _run(tmp_path / "a", experiments=_with_rules())
    for kind in ("h2_summary", "h2_regions"):
        path = entry.windows["core"].tables[kind]
        assert len(pd.read_parquet(path)) == 0 and _skip_note(path)["open_question"] == "OQ-050"
    other, _, _ = _run(tmp_path / "b", country=_country(top_k_percent=None))
    for kind in ("h2_summary", "h2_regions"):
        path = other.windows["core"].tables[kind]
        assert len(pd.read_parquet(path)) == 0 and _skip_note(path)["open_question"] == "OQ-021"
    hypothesis = pd.read_parquet(other.windows["core"].tables["hypothesis"])
    assert not hypothesis["statistic"].str.startswith("h2_overlap").any()


# -- H3: the robust and the nominal shortlists over the ranked set, D and the verdict (OQ-050, H3) ---------------


def _weighted(frame: pd.DataFrame, column: str) -> float:
    """The capacity-weighted mean of a column."""
    return float((frame["p_mw"] * frame[column]).sum() / frame["p_mw"].sum())


@pytest.mark.unit
def test_the_h3_tables_agree_with_the_shortlists_recomputed_from_the_robustness_table(tmp_path):
    entry, _, _ = _run(tmp_path)
    tables = entry.windows["core"].tables
    robustness = _table(entry)
    ranked = robustness[robustness["cell_class"] == "ranked"].copy()
    summary = pd.read_parquet(tables["h3_summary"])
    primary = summary[summary["primary"]].iloc[0]
    assert summary["primary"].sum() == 1 and primary["variant"] == "primary"
    assert (primary["delta"], primary["m"]) == (0.20, primary["k"])
    # the robust shortlist is the robust top-k set of H1 and H2; the nominal one is cut from the ranked set
    robust = ranked[ranked["topk_robust"].fillna(False).astype(bool)]
    assert primary["robust_capacity_mw"] == pytest.approx(float(robust["p_mw"].sum()))
    by_cost = ranked.sort_values(["lcoe_nominal", "cell_id"])["cell_id"]
    ranked["nominal_rank_in_i"] = ranked["cell_id"].map(
        pd.Series(range(1, len(by_cost) + 1), index=by_cost.to_numpy())
    )
    robust = ranked[ranked["topk_robust"].fillna(False).astype(bool)]
    nominal = ranked[ranked["nominal_rank_in_i"] <= primary["k"]]
    assert primary["nominal_capacity_mw"] == pytest.approx(float(nominal["p_mw"].sum()))
    beyond = robust[robust["nominal_rank_in_i"] > 2 * primary["k"]]
    assert primary["outside_capacity_mw"] == pytest.approx(float(beyond["p_mw"].sum()))
    assert primary["d"] == pytest.approx(float(beyond["p_mw"].sum() / robust["p_mw"].sum()))
    assert primary["n_ranked"] == len(ranked)
    assert primary["d_ref"] == pytest.approx(1 - 2 * primary["k"] / len(ranked))
    assert primary["verdict"] == (
        "not_testable"
        if primary["d_ref"] < 0.20
        else ("supported" if primary["d"] >= 0.20 else "not_supported")
    )
    expected_price = (
        _weighted(robust, "lcoe_nominal") - _weighted(nominal, "lcoe_nominal")
    ) / _weighted(nominal, "lcoe_nominal")
    assert primary["price_of_robustness"] == pytest.approx(expected_price)
    assert primary["benefit_of_robustness"] == pytest.approx(
        _weighted(nominal, "mr") - _weighted(robust, "mr")
    )
    assert {"top_k_percent_5", "top_k_percent_10", "top_k_percent_20"} <= set(summary["variant"])
    assert {"tolerance_0.5k", "tolerance_2k"} <= set(summary["variant"])
    sites = pd.read_parquet(tables["h3_sites"])
    union = set(robust["cell_id"]) | set(nominal["cell_id"])
    assert set(sites["cell_id"]) == union and sites["cell_id"].is_unique
    assert sites["counts_in_d"].sum() == len(beyond)
    assert not (sites["counts_in_d"] & sites["within_tolerance"]).any()
    assert sites.loc[sites["in_robust"], "capacity_mw"].sum() == pytest.approx(
        primary["robust_capacity_mw"]
    )
    hypothesis = pd.read_parquet(tables["hypothesis"]).set_index("statistic")
    shown = hypothesis.loc["h3_beyond_reach_share"]
    assert shown["value"] == pytest.approx(primary["d"])
    assert shown["verdict"] == {
        "supported": "met",
        "not_supported": "not_met",
        "not_testable": None,
    }[primary["verdict"]] or (pd.isna(shown["verdict"]) and primary["verdict"] == "not_testable")
    assert hypothesis.loc["h3_reference_share", "value"] == pytest.approx(primary["d_ref"])
    assert hypothesis.loc["h3_price_of_robustness", "value"] == pytest.approx(
        primary["price_of_robustness"]
    )
    # the statistics of the earlier H3 stay as descriptive rows without a verdict
    assert "descriptive" in hypothesis.loc["h3_jaccard_nominal_robust", "note"]
    assert pd.isna(hypothesis.loc["h3_jaccard_nominal_robust", "verdict"])
    assert pd.isna(hypothesis.loc["h3_price_of_robustness", "verdict"])


@pytest.mark.unit
def test_a_null_h3_rule_or_a_null_p_k_writes_the_h3_tables_empty_and_names_the_question(tmp_path):
    entry, _, _ = _run(tmp_path / "a", experiments=_with_rules())
    for kind in ("h3_summary", "h3_sites"):
        path = entry.windows["core"].tables[kind]
        assert len(pd.read_parquet(path)) == 0 and _skip_note(path)["open_question"] == "OQ-050"
    other, _, _ = _run(tmp_path / "b", country=_country(top_k_percent=None))
    for kind in ("h3_summary", "h3_sites"):
        path = other.windows["core"].tables[kind]
        assert len(pd.read_parquet(path)) == 0 and _skip_note(path)["open_question"] == "OQ-021"
    hypothesis = pd.read_parquet(other.windows["core"].tables["hypothesis"])
    assert not hypothesis["statistic"].str.startswith("h3_beyond").any()


# -- H4: the axis displacements, the dominance ratio and the profile of the country (OQ-050, H4) -------------------


def _share_beyond(ranked: pd.DataFrame, score: str, k: int, m: int) -> float:
    """The H3 statistic on the `k` lowest cells of `score` (ties by cell_id), against the nominal rank within the ranked set."""
    by_cost = ranked.sort_values(["lcoe_nominal", "cell_id"])["cell_id"]
    nominal_rank = ranked["cell_id"].map(
        pd.Series(range(1, len(by_cost) + 1), index=by_cost.to_numpy())
    )
    shortlist = ranked.assign(nominal_rank=nominal_rank).sort_values([score, "cell_id"]).head(k)
    return float(
        shortlist[shortlist["nominal_rank"] > k + m]["p_mw"].sum() / shortlist["p_mw"].sum()
    )


@pytest.mark.unit
def test_the_h4_country_table_recomputes_from_the_robustness_table_and_carries_the_profile(
    tmp_path,
):
    entry, _, _ = _run(tmp_path)
    tables = entry.windows["core"].tables
    robustness = _table(entry)
    ranked = robustness[robustness["cell_class"] == "ranked"]
    summary = pd.read_parquet(tables["h4_country"])
    primary = summary[summary["primary"]].iloc[0]
    assert summary["primary"].sum() == 1 and primary["variant"] == "primary"
    assert (primary["lower"], primary["upper"], primary["m"]) == (0.40, 0.60, primary["k"])
    k, m = int(primary["k"]), int(primary["m"])
    assert primary["d_clim"] == pytest.approx(_share_beyond(ranked, "mr_clim", k, m))
    assert primary["d_tec"] == pytest.approx(_share_beyond(ranked, "mr_tech", k, m))
    assert primary["d_joint"] == pytest.approx(
        pd.read_parquet(tables["h3_summary"]).query("primary")["d"].iloc[0]
    )
    assert primary["d_sum"] == pytest.approx(primary["d_clim"] + primary["d_tec"])
    if primary["d_sum"] == 0:
        assert pd.isna(primary["rho"]) and primary["profile"] == "no_displacement"
    else:
        assert primary["rho"] == pytest.approx(primary["d_clim"] / primary["d_sum"])
        expected = (
            "climate_dominated"
            if primary["rho"] > 0.60
            else "techno_economic_dominated"
            if primary["rho"] < 0.40
            else "mixed"
        )
        assert primary["profile"] == expected
    variants = set(summary["variant"])
    assert {"top_k_percent_5", "top_k_percent_20", "tolerance_0.5k", "tolerance_2k"} <= variants
    assert {"boundaries_0.30_0.70", "boundaries_0.45_0.55"} <= variants
    assert any(v.startswith("climate_ssp_") for v in variants)
    by_ssp = summary[summary["ssp"].notna()]
    assert len(by_ssp) >= 2 and (by_ssp["d_tec"] == primary["d_tec"]).all()
    hypothesis = pd.read_parquet(tables["hypothesis"]).set_index("statistic")
    assert hypothesis.loc["h4_displacement_climate", "value"] == pytest.approx(primary["d_clim"])
    assert hypothesis.loc["h4_displacement_techno", "value"] == pytest.approx(primary["d_tec"])
    assert pd.isna(
        hypothesis.loc["h4_displacement_climate", "verdict"]
    )  # the verdict is across countries
    # the earlier statistics of H4 stay as descriptive rows
    assert "descriptive" in hypothesis.loc["h4_jaccard_climate_only", "note"]
    assert "descriptive" in hypothesis.loc["h4_variance_share_climate", "note"]


@pytest.mark.unit
def test_a_null_h4_rule_or_a_null_p_k_writes_the_h4_table_empty_and_names_the_question(tmp_path):
    entry, _, _ = _run(tmp_path / "a", experiments=_with_rules())
    path = entry.windows["core"].tables["h4_country"]
    assert len(pd.read_parquet(path)) == 0 and _skip_note(path)["open_question"] == "OQ-050"
    other, _, _ = _run(tmp_path / "b", country=_country(top_k_percent=None))
    path = other.windows["core"].tables["h4_country"]
    assert len(pd.read_parquet(path)) == 0 and _skip_note(path)["open_question"] == "OQ-021"
    hypothesis = pd.read_parquet(other.windows["core"].tables["hypothesis"])
    assert not hypothesis["statistic"].str.startswith("h4_displacement").any()


# -- members by channel (M-F4-02 item 6, M-F4-06) -----------------------------------------------------------


@pytest.mark.unit
def test_wind_uses_the_members_that_carry_the_wind_channel_and_solar_uses_all_of_them(tmp_path):
    """A member without the wind channel (MIROC6) has no F5 wind rows: it is not a member of the wind analysis, so its cells are not
    `climate_data_invalid`; solar keeps it."""
    no_wind = CORE[2]  # the GCM-B member of SSP1-2.6; the others keep both SSPs for H1
    every_cell = [(i, no_wind) for i in range(N_CELLS)]  # F5 wrote no wind row of the member
    wind, _, _ = _run(tmp_path / "w", tech="wind", absent=every_cell, no_wind=(no_wind,))
    solar, _, _ = _run(tmp_path / "s", tech="solar", no_wind=(no_wind,))

    assert (
        wind.windows["core"].n_f7_set == N_CELLS
        and wind.windows["core"].class_counts["climate_data_invalid"] == 0
    )
    wind_members = set(
        pd.read_parquet(wind.windows["core"].tables["nominal_lcoe_by_member"])["member"]
    )
    solar_members = set(
        pd.read_parquet(solar.windows["core"].tables["nominal_lcoe_by_member"])["member"]
    )
    assert no_wind not in wind_members and no_wind in solar_members
    assert len(solar_members) == len(wind_members) + 1
    futures = pd.read_parquet(solar.windows["core"].tables["futures"])
    assert (
        futures["delta_wind_mean"].isna().any()
    )  # the MIROC6-like solar futures have no wind ratio
    assert pd.read_parquet(wind.windows["core"].tables["futures"])["delta_wind_mean"].notna().all()
    # undeclared, the same absence would make every cell invalid: the declaration is what removes the member
    undeclared, _, _ = _run(tmp_path / "u", tech="wind", absent=every_cell)
    assert undeclared.windows["core"].class_counts["climate_data_invalid"] == N_CELLS


@pytest.mark.unit
def test_prim_has_no_wind_descriptor_when_a_member_has_no_wind_ratio():
    from geofrea.robustness_analysis.assemble import prim_input

    futures = pd.DataFrame(
        {
            "sample": [1, 2, 1, 2],
            "member": ["a", "a", "b", "b"],
            "gcm": ["G1", "G1", "G2", "G2"],
            "ssp": ["SSP1-2.6"] * 4,
            "p": [1.0, 2.0, 3.0, 4.0],
            "delta_rsds_mean": 1.0,
            "dT_mean": 2.0,
            "delta_wind_mean": [1.0, 1.0, np.nan, np.nan],
            "displaced_capacity_share": [0.1, 0.2, 0.3, 0.4],
        }
    )

    x, _ = prim_input(futures, ["p"])
    assert "delta_wind_mean" not in x.columns and {"p", "delta_rsds_mean", "dT_mean"} <= set(
        x.columns
    )
    complete, _ = prim_input(futures.assign(delta_wind_mean=1.0), ["p"])
    assert "delta_wind_mean" in complete.columns


@pytest.mark.unit
def test_the_member_factor_means_of_a_member_without_wind_are_nan_not_zero(tmp_path):
    from geofrea.robustness_analysis.pipeline import member_factor_means

    forcing = pd.DataFrame(
        {
            "cell_id": [1, 2, 1, 2],
            "member": ["a", "a", "b", "b"],
            "delta_rsds": 1.0,
            "dT": 2.0,
            "delta_wind": [1.1, 1.3, np.nan, np.nan],
        }
    )
    path = tmp_path / "forcing.parquet"
    forcing.to_parquet(path)

    means = member_factor_means(path, np.array([1, 2]), ["a", "b"])

    assert means.loc["a", "delta_wind"] == pytest.approx(1.2) and np.isnan(
        means.loc["b", "delta_wind"]
    )
    assert means.loc["b", "delta_rsds"] == 1.0
