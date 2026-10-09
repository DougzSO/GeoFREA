"""F7 on small hand-made tables: classes, rankings, truncation, null decision parameters, the `s0` invariant, failures (M-F7-01 to M-F7-11, V-03, A-09)."""

from __future__ import annotations

import ast
import json
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


def _stage(tmp_path: Path, tech="wind", cf=None, absent=(), scenarios=LAND_SCENARIOS):
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
                    "member": pd.Categorical([member] * int(keep.sum()), categories=ALL_MEMBERS),
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
                    "delta_wind": np.ones(int(keep.sum())),
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
            }
        ).to_parquet(cdir / f"candidates_{tech}__{scenario}.parquet")
    pd.concat(forcing, ignore_index=True).to_parquet(kdir / "forcing.parquet")
    pd.DataFrame(
        {"cell_id": pd.Series(dtype="int64"), "member": pd.Series(dtype="object")}
    ).to_parquet(
        kdir / "hazard_context.parquet"
    )  # no member of these tests carries the hazard channel
    members = [
        {"member": "m0", "window": "1995-2014", "channels": {"resource": True, "hazard": False}}
    ]
    for name, (gcm, ssp, window) in META.items():
        members.append(
            {
                "member": name,
                "gcm": gcm,
                "ssp": ssp,
                "window": window,
                "channels": {"resource": True, "hazard": False},
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
    country = _country(capacity_target_gw=0.8)
    entry, _, _ = _run(tmp_path, country=country)
    table = _table(entry)
    taken = table[table["topk_capacity_target"].fillna(False).astype(bool)].sort_values(
        "robust_rank"
    )
    assert taken["robust_rank"].tolist() == list(range(1, len(taken) + 1))
    assert taken["p_mw"].sum() / 1000.0 >= 0.8
    assert taken["p_mw"].iloc[:-1].sum() / 1000.0 < 0.8  # the fewest cells
    assert entry.windows["core"].target_unreachable is False
    huge = _run(tmp_path / "b", country=_country(capacity_target_gw=1e6))[0]
    assert huge.windows["core"].target_unreachable is True
    assert _table(huge)["topk_capacity_target"].sum() == 20  # all ranked cells


# -- null decision parameters (D-F7-023) ------------------------------------------------------------------------


@pytest.mark.unit
def test_a_null_tau_skips_sr_and_a_null_p_k_skips_the_top_k_flags_and_both_are_listed(
    tmp_path, caplog
):
    country = _country(tau_lcoe_usd_per_mwh=None, top_k_percent=None, capacity_target_gw=None)
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
    assert {"OQ-008", "OQ-021", "OQ-010", "OQ-056"} <= skipped
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
        assert "capex_usd_per_kw" in text and len(info.value.missing) >= 34


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
        f"{kind}_wind__{role}.parquet" for kind in ROW_MODELS for role in ("core", "sensitivity")
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
    raw["hypothesis_rules"] = {f"H{i}": rules.get(f"H{i}") for i in range(1, 6)}
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
    entry, _, _ = _run(tmp_path)
    hypothesis = pd.read_parquet(entry.windows["core"].tables["hypothesis"])
    assert set(hypothesis["hypothesis"]) == {"H1", "H2", "H3", "H4", "H5"}
    assert hypothesis["verdict"].isna().all() and hypothesis["verdict_reason"].notna().all()
    assert sum("no pre-registered rule" in r.message for r in caplog.records) >= 5


@pytest.mark.unit
def test_a_pre_registered_rule_gives_met_or_not_met_and_never_for_the_other_statistics(tmp_path):
    rule = {"statistic": "h2_mr_median", "comparison": "ge", "threshold": -1.0}
    entry, _, _ = _run(tmp_path, experiments=_with_rules(H2=[rule]))
    table = pd.read_parquet(entry.windows["core"].tables["hypothesis"])
    named = table[table["statistic"] == "h2_mr_median"].iloc[0]
    assert named["verdict"] == "met" and named["rule"]
    assert (
        table[table["statistic"] != "h2_mr_median"]
        .query("hypothesis == 'H2'")["verdict"]
        .isna()
        .all()
    )
    impossible = {"statistic": "h2_mr_median", "comparison": "lt", "threshold": -1.0}
    other, _, _ = _run(tmp_path / "b", experiments=_with_rules(H2=[impossible]))
    again = pd.read_parquet(other.windows["core"].tables["hypothesis"])
    assert again.set_index("statistic").loc["h2_mr_median", "verdict"] == "not_met"


@pytest.mark.unit
def test_a_rule_that_names_an_unknown_statistic_fails_loudly(tmp_path):
    from geofrea.robustness_analysis.hypotheses import HypothesisRuleError

    rule = {"statistic": "h9_nothing", "comparison": "ge", "threshold": 0.0}
    with pytest.raises(HypothesisRuleError):
        _run(tmp_path, experiments=_with_rules(H1=[rule]))


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
