"""The exploratory phase (COMMAND 210; DEC-098): H5c, VUL, the V_f diagnostic and tau on the cell basis, on small cases with a result known by hand."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from geofrea.core.code_fingerprint import closure_modules
from geofrea.exploratory_analysis import h5c, vulnerability
from geofrea.exploratory_analysis.pipeline import PROVENANCE_KEY, build_exploratory

pytestmark = pytest.mark.unit


# ── H5c: the curve, MC and AC ────────────────────────────────────────────────────────────────────────────────────────────────────────────


def _curve(lcoe, energy, ids=None):
    ids = np.arange(len(lcoe)) if ids is None else ids
    return h5c.cost_curve(np.asarray(ids), np.asarray(lcoe, dtype=float), np.asarray(energy, dtype=float))


def test_mc_and_ac_with_a_fractional_last_cell():
    curve = _curve([10, 20, 30], [1, 2, 3])  # cumulative energy 1, 3, 6
    assert h5c.marginal_cost(curve, 2.0) == 20 and h5c.average_cost(curve, 2.0) == pytest.approx((10 * 1 + 20 * 1) / 2)
    assert h5c.marginal_cost(curve, 3.0) == 20 and h5c.average_cost(curve, 3.0) == pytest.approx((10 + 40) / 3)
    assert h5c.marginal_cost(curve, 6.0) == 30 and h5c.average_cost(curve, 6.0) == pytest.approx((10 + 40 + 90) / 6)
    assert h5c.marginal_cost(curve, 0.5) == 10 and h5c.average_cost(curve, 0.5) == pytest.approx(10)


def test_a_level_the_energy_does_not_reach_is_unreachable_and_nan():
    curve = _curve([10, 20], [1, 2])
    assert np.isnan(h5c.marginal_cost(curve, 3.5)) and np.isnan(h5c.average_cost(curve, 3.5))
    assert h5c.reached(curve, 3.0) and not h5c.reached(curve, 3.5)


def test_cells_without_a_finite_cost_or_without_energy_are_left_out_of_the_curve():
    curve = _curve([10, np.nan, np.inf, 20, 5], [1, 5, 5, 2, 0])
    assert list(curve.lcoe) == [10, 20] and curve.total_twh == 3


def test_ties_in_lcoe_are_ordered_by_cell_id():
    curve = _curve([10, 10, 10], [1, 1, 1], ids=[7, 3, 5])
    assert list(curve.cell_id) == [3, 5, 7]


def test_the_levels_are_the_target_when_there_is_one_and_the_shares_of_the_total_energy():
    assert h5c.levels(None, 100.0) == [("p05", 5.0), ("p10", 10.0), ("p25", 25.0)]
    assert h5c.levels(12.0, 100.0)[0] == ("target", 12.0)
    assert h5c.levels(0.0, 100.0)[0][0] == "p05"  # a target that converts to no energy is no level


def _members():
    curves = {
        "m0": _curve([10, 20, 30], [1, 2, 3]),
        "m_a1": _curve([11, 22, 33], [1, 2, 3]),  # +10%
        "m_a2": _curve([12, 24, 36], [1, 2, 3]),  # +20%
        "m_b1": _curve([10, 20, 30], [1, 2, 3]),  # equal to m0
        "m_c1": _curve([11, 15, 19], [1, 1, 1]),  # only 3 TWh in total, and cheaper at the margin
    }
    gcm = {"m_a1": "A", "m_a2": "A", "m_b1": "B", "m_c1": "C"}
    ssp = {"m_a1": "SSP1", "m_a2": "SSP2", "m_b1": "SSP1", "m_c1": "SSP2"}
    return curves, gcm, ssp


def test_delta_mc_is_the_maximum_over_members_with_the_member_the_ssp_the_median_and_the_value_per_ssp():
    curves, gcm, ssp = _members()
    rows = h5c.member_rows(curves, gcm, ssp, 3.0)
    mc = h5c.pressure(rows, "mc")
    assert mc["delta_mc_max"] == pytest.approx(0.2) and mc["delta_mc_member"] == "m_a2" and mc["delta_mc_ssp"] == "SSP2"
    assert mc["delta_mc_median"] == pytest.approx(0.05)  # members 0.1, 0.2, 0.0 and -0.05 (m_c1: MC 19 at its third cell)
    assert mc["delta_mc_by_ssp"] == {"SSP1": pytest.approx(0.1), "SSP2": pytest.approx(0.2)}  # the maximum over the GCMs of each SSP


def test_a_member_that_does_not_reach_the_level_is_flagged_and_left_out_of_the_statistics():
    curves, gcm, ssp = _members()
    rows = h5c.member_rows(curves, gcm, ssp, 4.0)  # m_c1 has 3 TWh
    flagged = rows.set_index("member")["level_unreachable"]
    assert flagged["m_c1"] and not flagged["m_a1"]
    mc = h5c.pressure(rows, "mc")
    assert mc["delta_mc_max"] == pytest.approx(0.2) and "SSP2" in mc["delta_mc_by_ssp"]


def test_a_reference_that_does_not_reach_the_level_gives_no_statistic():
    curves, gcm, ssp = _members()
    rows = h5c.member_rows(curves, gcm, ssp, 7.0)
    assert rows["level_unreachable"].all() and np.isnan(h5c.pressure(rows, "mc")["delta_mc_max"])


def test_the_label_is_material_from_a_delta_of_005_at_the_target_only():
    assert h5c.label_for("target", 0.05) == h5c.LABEL_MATERIAL
    assert h5c.label_for("target", 0.0499) == h5c.LABEL_NOT_MATERIAL
    assert h5c.label_for("target", float("nan")) == h5c.LABEL_UNREACHABLE
    assert h5c.label_for("p10", 0.9) is None


def test_the_reference_member_is_the_one_of_the_climate_package():
    from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID

    assert h5c.REFERENCE_MEMBER == REFERENCE_MEMBER_ID


# ── VUL ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


def test_vul_clim_is_zero_when_every_member_equals_the_reference():
    f0 = np.array([10.0, 20.0, 30.0])
    index = vulnerability.vul_indices(f0, np.tile(f0[:, None], (1, 3)), f0, np.tile(f0[:, None], (1, 3)))
    assert np.all(index["vul_clim"] == 0) and np.all(index["vul_tec"] == 0) and np.all(index["vul"] == 0)


def test_the_three_indices_on_a_case_known_by_hand():
    f0 = np.array([10.0, 20.0])
    nominal = np.array([[11.0, 12.0, 10.0], [22.0, 26.0, 20.0]])
    p90_ref = 1.5 * f0
    p90 = 1.5 * nominal
    index = vulnerability.vul_indices(f0, nominal, p90_ref, p90)
    assert index["vul_clim"] == pytest.approx([0.2, 0.3])
    assert index["vul_tec"] == pytest.approx([0.5, 0.5])
    assert index["vul"] == pytest.approx([0.8, 0.95])  # 1.5 x the worst member ratio minus 1


def test_a_cell_that_fails_in_a_member_has_no_index_not_an_infinite_one():
    f0 = np.array([10.0, 20.0])
    nominal = np.array([[11.0, np.nan], [22.0, 24.0]])
    index = vulnerability.vul_indices(f0, nominal, f0, nominal)
    assert np.isnan(index["vul_clim"][0]) and index["vul_clim"][1] == pytest.approx(0.2)


def test_spearman_the_upper_quartile_share_and_the_quadrants():
    a = np.array([1.0, 2.0, 3.0, 4.0])
    assert vulnerability.spearman(a, a * 2) == pytest.approx(1.0) and vulnerability.spearman(a, -a) == pytest.approx(-1.0)
    assert np.isnan(vulnerability.spearman(a, np.ones(4)))
    vul = np.array([0.1, 0.2, 0.3, 0.4])
    share, n = vulnerability.top_share_in_upper_quartile(vul, np.array([True, False, True, True]))
    assert n == 3 and share == pytest.approx(1 / 3)  # the 75th percentile is 0.325: only 0.4 is at or above it
    quadrants = vulnerability.quadrant_capacity(np.array([10.0, 20.0, 30.0, 40.0]), vul, np.array([1.0, 2.0, 4.0, 8.0]))
    assert quadrants["low_lcoe_low_vul"] == 1 + 2 and quadrants["high_lcoe_high_vul"] == 4 + 8
    assert quadrants["low_lcoe_high_vul"] == 0 and quadrants["high_lcoe_low_vul"] == 0


def test_the_vf_distribution_against_the_threshold():
    stats = vulnerability.vf_distribution(np.array([0.0, 0.1, 0.25, 0.3, np.nan]), 0.2)
    assert stats["n_futures"] == 5 and stats["n_finite"] == 4 and stats["max"] == 0.3
    assert stats["n_cases"] == 2 and stats["share_cases"] == 0.5 and stats["gap_max_to_theta"] == pytest.approx(-0.1)
    assert stats["median"] == pytest.approx(0.175)
    none = vulnerability.vf_distribution(np.zeros(5), 0.2)
    assert none["n_cases"] == 0 and none["gap_max_to_theta"] == pytest.approx(0.2)


# ── tau on the cell basis ───────────────────────────────────────────────────────────────────────────────────────────────────────────────


def test_the_annuity_factor_is_the_one_of_the_kernel():
    from geofrea.lcoe_modeling.kernel import annuity_factor

    for rate in (0.0, 0.02, 0.07, 0.12):
        for years in (20.0, 25.0, 30.0):
            assert vulnerability.annuity_factor(rate, years) == pytest.approx(float(annuity_factor(rate, years)), rel=1e-12)


def test_the_reference_plant_lcoe_by_hand():
    # a = (1 - 1.07^-25) / 0.07 = 11.6536; LCOE = (1000 / a + 20) x 1000 / (0.3 x 8760)
    assert vulnerability.reference_plant_lcoe(1000.0, 20.0, 25.0, 0.07, 0.3) == pytest.approx(40.2623, abs=1e-3)


def test_tau_on_the_cell_basis_changes_the_lifetime_and_the_om_and_nothing_else():
    v = vulnerability.tau_cell_basis(1000.0, 0.3, 20.0, 25.0, 800.0, 0.02, 30.0, 0.07)
    assert v["om_f6_usd_per_kw_yr"] == pytest.approx(16.0)
    assert v["tau_reference"] == pytest.approx(vulnerability.reference_plant_lcoe(1000.0, 20.0, 25.0, 0.07, 0.3))
    assert v["tau_cell_basis"] == pytest.approx(vulnerability.reference_plant_lcoe(1000.0, 16.0, 30.0, 0.07, 0.3))
    assert v["tau_life_only"] == pytest.approx(vulnerability.reference_plant_lcoe(1000.0, 20.0, 30.0, 0.07, 0.3))
    assert v["tau_om_only"] == pytest.approx(vulnerability.reference_plant_lcoe(1000.0, 16.0, 25.0, 0.07, 0.3))
    same = vulnerability.tau_cell_basis(1000.0, 0.3, 16.0, 30.0, 800.0, 0.02, 30.0, 0.07)
    assert same["tau_cell_basis"] == pytest.approx(same["tau_reference"])  # the same life and O&M: the same plant
    assert vulnerability.capacity_at_or_below(np.array([10.0, 20.0, 30.0]), np.array([1.0, 2.0, 4.0]), 20.0) == (2, 3.0)


# ── the phase, on a tree of artifacts written by hand ───────────────────────────────────────────────────────────────────────────────────────


def _write(path, frame, metadata=None):
    table = pa.Table.from_pandas(frame, preserve_index=False)
    if metadata:
        table = table.replace_schema_metadata({**(table.schema.metadata or {}), **{k.encode(): v.encode() for k, v in metadata.items()}})
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


MEMBERS = ["m0", "m_a1", "m_a2", "m_b1"]


def _tree(tmp_path):
    robustness, lcoe, potential = tmp_path / "rob", tmp_path / "lcoe", tmp_path / "pot"
    ids = [10, 11, 12, 13]
    classes = ["ranked", "ranked", "climate_fragile", "climate_data_invalid"]
    rob = pd.DataFrame(
        {
            "cell_id": ids,
            "cell_class": classes,
            "lat_c": [1.0, 1.0, 1.0, 1.0],
            "lon_c": [1.0, 2.0, 3.0, 4.0],
            "p_mw": [100.0, 200.0, 300.0, 400.0],
            "lcoe_nominal": [10.0, 20.0, 30.0, np.nan],
            "mr": [0.1, 0.2, np.nan, np.nan],
            "topk_nominal": [True, False, False, None],
            "n_failing_members": [0, 0, 1, 0],
        }
    )
    decision = {"decision": {"cf_min": 0.2, "tau_lcoe_usd_per_mwh": 25.0}}
    _write(robustness / "robustness_wind__core.parquet", rob, {"geofrea_robustness_provenance": json.dumps(decision)})
    _write(robustness / "robustness_wind__sensitivity.parquet", rob, {"geofrea_robustness_provenance": json.dumps(decision)})
    members = pd.DataFrame(
        {"member": MEMBERS[1:], "gcm": ["A", "A", "B"], "ssp": ["SSP1", "SSP2", "SSP1"], "window": ["w"] * 3}
    )
    nominal_by_member = {
        "m0": [10.0, 20.0, 30.0],
        "m_a1": [11.0, 22.0, 33.0],
        "m_a2": [12.0, 26.0, np.nan],
        "m_b1": [10.0, 20.0, 30.0],
    }
    nom = pd.DataFrame(
        [{"cell_id": c, "member": m, "lcoe_nominal": v} for m, vals in nominal_by_member.items() for c, v in zip(ids[:3], vals, strict=True)]
    )
    pot = pd.DataFrame(
        [
            {"cell_id": c, "member": m, "CF": 0.1 if (m == "m_a2" and c == 12) else 0.3, "E_MWh": e * 1.0e6}
            for m in MEMBERS
            for c, e in zip(ids[:3], (1.0, 2.0, 3.0), strict=True)
        ]
    )
    summary = pd.DataFrame(
        [{"cell_id": c, "member": m, "lcoe_p90": 1.5 * v if np.isfinite(v) else np.nan} for m, vals in nominal_by_member.items() for c, v in zip(ids[:3], vals, strict=True)]
    )
    futures = pd.DataFrame({"displaced_capacity_share": [0.0, 0.1, 0.25, 0.3, np.nan]})
    h5 = pd.DataFrame({"primary": [True, False], "g_twh": [9.0, 5.0], "target_value": [0.3, 0.3], "target_unit": ["GW", "GW"]})  # g_twh: the old conversion, not used
    for role in ("core", "sensitivity"):
        _write(robustness / f"h5_members_wind__{role}.parquet", members)
        _write(robustness / f"nominal_lcoe_by_member_wind__{role}.parquet", nom)
        _write(robustness / f"h5_summary_wind__{role}.parquet", h5)
    _write(robustness / "futures_wind__core.parquet", futures)
    _write(potential / "potential_wind__central.parquet", pot)
    _write(lcoe / "lcoe_summary_wind.parquet", summary)
    design = pd.DataFrame(
        {
            "sample": [0, 1],
            "capex_usd_per_kw": [800.0, 900.0],
            "opex_fixed_frac": [0.02, 0.03],
            "discount_rate": [0.07, 0.08],
            "lifetime_years": [30.0, 25.0],
        }
    )
    _write(lcoe / "design_matrix_wind.parquet", design)
    irena = {
        "editions": {
            "irena_rpgc_2024": {
                "life_years": {"value": 25},
                "pairs": {"ZZZ": {"wind": {"tic_usd_per_kw": {"value": 1000.0}, "cf": {"value": 0.3}, "om_usd_per_kw_yr": {"value": 20.0}}}},
            }
        }
    }
    (tmp_path / "irena.yaml").write_text(yaml.safe_dump(irena), encoding="utf-8")
    return {"potential_dir": potential, "lcoe_dir": lcoe, "robustness_dir": robustness, "out_dir": tmp_path / "out", "irena_reference_yaml": tmp_path / "irena.yaml"}


def _run(tmp_path, **over):
    dirs = _tree(tmp_path)
    return build_exploratory(
        "ZZZ", ["wind"], {"core": "2041-2070", "sensitivity": "2071-2100"}, outcome_threshold=0.2, **{**dirs, **over}
    ), dirs


def test_the_phase_writes_every_table_with_exploratory_true_in_the_provenance(tmp_path):
    summary, _ = _run(tmp_path)
    tables = summary.technologies["wind"].tables
    expected = {f"{k}__{r}" for k in ("h5c_curves", "h5c_summary", "vulnerability", "vulnerability_summary") for r in ("core", "sensitivity")}
    assert set(tables) == expected | {"prim_vf", "tau_cell_basis"} and summary.exploratory
    for path in tables.values():
        meta = pq.read_schema(path).metadata
        body = json.loads(meta[PROVENANCE_KEY.encode()])
        assert body["exploratory"] is True and body["decision"] == "DEC-098"


def test_h5c_on_the_hand_made_tree(tmp_path):
    summary, _ = _run(tmp_path)
    table = pd.read_parquet(summary.technologies["wind"].tables["h5c_summary__core"]).set_index(["basis", "level"])
    nominal = table.loc[("nominal", "target")]
    assert nominal["g_twh"] == 3.0 and nominal["g_share_of_total_m0"] == pytest.approx(0.5)  # 6 TWh at m0 in the F7 set (cells 10, 11, 12)
    assert nominal["mc_m0"] == 20 and nominal["ac_m0"] == pytest.approx((10 + 40) / 3)
    # m_a2: cell 12 is infeasible there (CF 0.1 < 0.2), the curve is cells 10 and 11 (3 TWh): MC 26, AC (12 + 52) / 3
    assert nominal["delta_mc_max"] == pytest.approx(0.3) and nominal["delta_mc_member"] == "m_a2" and nominal["delta_mc_ssp"] == "SSP2"
    assert nominal["delta_ac_max"] == pytest.approx((12 + 52) / 3 / ((10 + 40) / 3) - 1)
    assert nominal["label"] == h5c.LABEL_MATERIAL and nominal["n_unreachable_members"] == 0
    assert json.loads(nominal["delta_mc_by_ssp"]) == {"SSP1": pytest.approx(0.1), "SSP2": pytest.approx(0.3)}
    p25 = table.loc[("nominal", "p25")]
    assert p25["g_twh"] == pytest.approx(1.5) and p25["mc_m0"] == 20 and p25["ac_m0"] == pytest.approx((10 + 10) / 1.5)
    assert pd.isna(p25["label"])
    envelope = table.loc[("p90_envelope", "target")]  # P90 = 1.5 x nominal everywhere: the ratios are those of the nominal curves
    assert envelope["mc_m0"] == pytest.approx(30) and envelope["delta_mc_max"] == pytest.approx(0.3) and pd.isna(envelope["label"])


def test_the_target_conversion_does_not_depend_on_tau_and_the_old_one_is_kept_for_comparison(tmp_path):
    summary, _ = _run(tmp_path)
    row = pd.read_parquet(summary.technologies["wind"].tables["h5c_summary__core"]).set_index(["basis", "level"]).loc[("nominal", "target")]
    assert row["g_twh"] == 3.0 and row["g_target_h5_twh"] == 9.0 and not row["target_above_set_capacity"]
    # tau (25 in the provenance of F7) leaves the target alone: with tau 5, where Omega_econ is empty, or 1000, where it is the whole set, G is the same
    for tau, name in ((5.0, "low"), (1000.0, "high")):
        dirs = _tree(tmp_path / name)
        for role in ("core", "sensitivity"):
            path = dirs["robustness_dir"] / f"robustness_wind__{role}.parquet"
            table = pq.read_table(path)
            meta = json.loads(table.schema.metadata[b"geofrea_robustness_provenance"])
            meta["decision"]["tau_lcoe_usd_per_mwh"] = tau
            pq.write_table(table.replace_schema_metadata({"geofrea_robustness_provenance": json.dumps(meta)}), path)
        again = build_exploratory("ZZZ", ["wind"], {"core": "w", "sensitivity": "s"}, outcome_threshold=0.2, **dirs)
        other = pd.read_parquet(again.technologies["wind"].tables["h5c_summary__core"]).set_index(["basis", "level"]).loc[("nominal", "target")]
        assert other["g_twh"] == row["g_twh"] and other["mc_m0"] == row["mc_m0"]


def test_a_target_above_the_capacity_of_the_set_takes_the_whole_set_and_raises_the_flag(tmp_path):
    dirs = _tree(tmp_path)
    for role in ("core", "sensitivity"):
        _write(dirs["robustness_dir"] / f"h5_summary_wind__{role}.parquet", pd.DataFrame({"primary": [True], "g_twh": [99.0], "target_value": [5.0], "target_unit": ["GW"]}))
    summary = build_exploratory("ZZZ", ["wind"], {"core": "w", "sensitivity": "s"}, outcome_threshold=0.2, **dirs)
    row = pd.read_parquet(summary.technologies["wind"].tables["h5c_summary__core"]).set_index(["basis", "level"]).loc[("nominal", "target")]
    assert row["g_twh"] == 6.0 and row["target_above_set_capacity"] and row["g_target_h5_twh"] == 99.0 and row["g_share_of_total_m0"] == pytest.approx(1.0)


def test_target_energy_by_hand():
    ids, lcoe, e, p = np.array([3, 1, 2, 4]), np.array([20.0, 10.0, 10.0, np.nan]), np.array([4.0, 1.0, 2.0, 9.0]), np.array([200.0, 100.0, 100.0, 300.0])
    # order: 1 (10, 100 MW, 1 TWh), 2 (10, 100 MW, 2 TWh: the tie goes by cell_id), 3 (20, 200 MW, 4 TWh); cell 4 has no LCOE
    assert h5c.target_energy(ids, lcoe, e, p, 0.15) == (pytest.approx(1.0 + 0.5 * 2.0), False)
    assert h5c.target_energy(ids, lcoe, e, p, 0.2) == (pytest.approx(3.0), False)
    assert h5c.target_energy(ids, lcoe, e, p, 0.3) == (pytest.approx(1.0 + 2.0 + 0.5 * 4.0), False)
    assert h5c.target_energy(ids, lcoe, e, p, 0.4) == (pytest.approx(7.0), False)
    assert h5c.target_energy(ids, lcoe, e, p, 0.41) == (pytest.approx(7.0), True)
    assert h5c.target_energy(np.array([], dtype="int64"), np.array([]), np.array([]), np.array([]), 1.0) == (0.0, True)


def test_the_curves_table_holds_the_reference_member_and_the_unreachable_flag(tmp_path):
    summary, _ = _run(tmp_path)
    curves = pd.read_parquet(summary.technologies["wind"].tables["h5c_curves__core"])
    row = curves[(curves["basis"] == "nominal") & (curves["level"] == "target") & (curves["member"] == "m0")].iloc[0]
    assert row["mc"] == 20 and row["d_mc"] == 0 and not row["level_unreachable"]
    assert set(curves["member"]) == set(MEMBERS) and set(curves["level"]) == {"target", "p05", "p10", "p25"}


def test_without_a_target_there_is_no_target_level(tmp_path):
    dirs = _tree(tmp_path)
    for role in ("core", "sensitivity"):
        _write(dirs["robustness_dir"] / f"h5_summary_wind__{role}.parquet", pd.DataFrame({"primary": [True], "g_twh": [np.nan], "target_value": [np.nan], "target_unit": ["TWh"]}))
    summary = build_exploratory("ZZZ", ["wind"], {"core": "w", "sensitivity": "s"}, outcome_threshold=0.2, **dirs)
    table = pd.read_parquet(summary.technologies["wind"].tables["h5c_summary__core"])
    assert "target" not in set(table["level"]) and len(summary.technologies["wind"].skipped) == 2


def test_vulnerability_of_the_ranked_cells_and_the_fragile_cell_apart(tmp_path):
    summary, _ = _run(tmp_path)
    table = pd.read_parquet(summary.technologies["wind"].tables["vulnerability__core"]).set_index("cell_id")
    assert set(table.index) == {10, 11, 12}  # the climate-data-invalid cell is outside the F7 set
    assert table.loc[10, "vul_clim"] == pytest.approx(0.2) and table.loc[11, "vul_clim"] == pytest.approx(0.3)
    assert table.loc[10, "vul_tec"] == pytest.approx(0.5)
    assert table.loc[10, "vul"] == pytest.approx(0.8) and table.loc[11, "vul"] == pytest.approx(0.95)
    assert table.loc[12, "cell_class"] == "climate_fragile" and pd.isna(table.loc[12, "vul_clim"]) and pd.isna(table.loc[12, "vul"])
    stats = pd.read_parquet(summary.technologies["wind"].tables["vulnerability_summary__core"]).set_index(["group", "statistic"])["value"]
    assert stats[("spearman", "vul_clim_with_lcoe_f0")] == pytest.approx(1.0)
    assert stats[("climate_fragile", "n_cells")] == 1 and stats[("climate_fragile", "capacity_mw")] == 300
    assert stats[("top_k_nominal", "share_in_upper_quartile_of_vul_clim")] == 0.0  # cell 10 (0.2) is below the 75th percentile (0.275)
    assert stats[("distribution_vul_clim", "n")] == 2


def test_the_vf_diagnostic_and_the_tau_table(tmp_path):
    summary, _ = _run(tmp_path)
    prim = pd.read_parquet(summary.technologies["wind"].tables["prim_vf"]).set_index("statistic")["value"]
    assert prim["max"] == 0.3 and prim["n_cases"] == 2 and prim["theta"] == 0.2
    tau = pd.read_parquet(summary.technologies["wind"].tables["tau_cell_basis"]).iloc[0]
    assert tau["tau_registered"] == 25.0 and tau["life_f6_years"] == 30 and tau["om_f6_usd_per_kw_yr"] == pytest.approx(16.0)
    assert tau["tau_cell_basis"] == pytest.approx(vulnerability.reference_plant_lcoe(1000.0, 16.0, 30.0, 0.07, 0.3))
    assert tau["n_cells_f7_set"] == 3 and tau["capacity_gw_f7_set"] == pytest.approx(0.6)
    assert tau["n_cells_below_registered"] == 2 and tau["capacity_gw_below_registered"] == pytest.approx(0.3)  # LCOE 10 and 20 are at or below 25
    assert tau["n_cells_below_cell_basis"] == 3  # tau on the cell basis is 36.7: every cell is below it


def test_a_pair_without_an_irena_value_skips_the_tau_table_and_says_why(tmp_path):
    dirs = _tree(tmp_path)
    document = yaml.safe_load(dirs["irena_reference_yaml"].read_text(encoding="utf-8"))
    document["editions"]["irena_rpgc_2024"]["pairs"]["ZZZ"]["wind"]["cf"] = {"value": None}
    dirs["irena_reference_yaml"].write_text(yaml.safe_dump(document), encoding="utf-8")
    summary = build_exploratory("ZZZ", ["wind"], {"core": "w", "sensitivity": "s"}, outcome_threshold=0.2, **dirs)
    entry = summary.technologies["wind"]
    assert "tau_cell_basis" not in entry.tables and any(s.output == "tau_cell_basis" and "cf" in s.reason for s in entry.skipped)


def test_a_missing_input_artifact_is_an_error_that_names_it(tmp_path):
    dirs = _tree(tmp_path)
    (dirs["robustness_dir"] / "futures_wind__core.parquet").unlink()
    with pytest.raises(RuntimeError, match="futures_wind__core"):
        build_exploratory("ZZZ", ["wind"], {"core": "w", "sensitivity": "s"}, outcome_threshold=0.2, **dirs)


def test_the_phase_does_not_import_the_modules_of_f6_or_f7():
    modules = closure_modules(("exploratory_analysis.pipeline",))
    assert not [m for m in modules if m.startswith(("lcoe_modeling", "robustness_analysis"))], modules


# ── the exploratory phase is outside every pre-registered phase and output ──────────────────────────────────────────────────────────────────


def test_no_phase_before_f8_runs_a_module_of_the_exploratory_phase():
    from geofrea.core.code_fingerprint import PHASE_CODE_ROOTS, phase_modules

    for phase in PHASE_CODE_ROOTS:
        if phase in ("exploratory_analysis", "results_synthesis"):
            continue
        assert not [m for m in phase_modules(phase) if m.startswith("exploratory_analysis")], phase


def test_only_the_exploratory_outputs_module_of_f8_imports_the_exploratory_phase():
    import ast
    from pathlib import Path

    folder = Path(__file__).resolve().parents[2] / "src" / "geofrea" / "results_synthesis"
    importers = []
    for path in sorted(folder.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            if any("exploratory_analysis" in m for m in modules):
                importers.append(path.name)
    assert sorted(set(importers)) == ["exploratory_outputs.py"]


def test_the_exploratory_outputs_have_names_and_are_not_essential():
    from geofrea.results_synthesis import names
    from geofrea.results_synthesis.runner import SCRIPTS

    assert names.stem("T-X1", "h5c_cost_to_target", "BRA", "wind") == "T-X1_h5c_cost_to_target_BRA_wind"
    assert set(names.EXPLORATORY) == {"T-X1", "T-X2", "T-X3", "T-X4"} <= set(SCRIPTS)
    assert not set(names.EXPLORATORY) & set(names.THESIS_IDS)  # outside Section 10 and its Essential rule


# ── COMMAND 210C: the scale suffix and the O&M of tau on the cell basis ─────────────────────────────────────────────────────────────────────


def test_the_scale_suffix_of_the_phase_directory_is_the_one_of_core_scale_for_every_configured_scale():
    from geofrea.core.scale import SCALE_DEPENDENT_PHASES, SCALES, phase_directory_name, use_scale
    from geofrea.exploratory_analysis.pipeline import PHASE, exploratory_dir

    reference = next(iter(sorted(SCALE_DEPENDENT_PHASES)))  # a phase that core.scale suffixes
    for scale_id in SCALES:
        with use_scale(scale_id):
            suffix = phase_directory_name(reference).removeprefix(reference)
            assert exploratory_dir("ZZZ").parent.name == f"{PHASE}{suffix}", scale_id
    assert "exploratory_analysis" not in SCALE_DEPENDENT_PHASES  # the suffix is the phase's own: core/scale.py is not edited (it would move every fingerprint)


def _repo():
    from pathlib import Path

    return Path(__file__).resolve().parents[2]


def _real_data_dir():
    """The real data directory from the key of `.env` (the autouse fixture of conftest points the variable at a temporary directory)."""
    from pathlib import Path

    env = _repo() / ".env"
    values = dict(line.split("=", 1) for line in env.read_text(encoding="utf-8").splitlines() if line.startswith("GEOFREA_DATA_DIR=")) if env.is_file() else {}
    value = values.get("GEOFREA_DATA_DIR", "").strip().strip('"')
    return Path(value) if value else None


PAIRS = [(iso, tech) for iso in ("PRT", "IND", "BRA") for tech in ("solar", "wind")]


@pytest.mark.parametrize(("iso", "tech"), PAIRS)
def test_the_capex_of_the_model_is_the_irena_tic_so_the_om_of_f6_is_the_fraction_of_the_tic(iso, tech):
    """D1: the capex that F6 applies is the TIC of the IRENA plant, so `opex_fixed_frac x capex(s0)` is `opex_fixed_frac x TIC`. If it were not, the reading of tau on
    the cell basis (the O&M of F6 on the plant of IRENA) would have two answers and the command stops."""
    parameters = json.loads((_repo() / "config" / "parameters.json").read_text(encoding="utf-8"))["countries"][iso]["technologies"][tech]
    irena = yaml.safe_load((_repo() / "config" / "irena_reference.yaml").read_text(encoding="utf-8"))["editions"]["irena_rpgc_2024"]["pairs"][iso][tech]
    tic = float(irena["tic_usd_per_kw"]["value"])
    capex = float(parameters["capex_usd_per_kw"]["value"])
    fraction = float(parameters["opex_fixed_frac"]["value"])
    assert capex == pytest.approx(tic, rel=1e-12)
    assert fraction * capex == pytest.approx(fraction * tic, rel=1e-12)


@pytest.mark.requires_data
@pytest.mark.parametrize(("iso", "tech"), PAIRS)
def test_the_nominal_sample_of_f6_has_the_irena_tic_as_its_capex(iso, tech):
    root = _real_data_dir()
    path = None if root is None else root / "outputs" / iso / "lcoe_modeling" / "artifacts" / f"design_matrix_{tech}.parquet"
    if path is None or not path.is_file():
        pytest.skip("the design matrix of F6 is not in the real data directory (CI)")
    s0 = pd.read_parquet(path).query("sample == 0").iloc[0]
    irena = yaml.safe_load((_repo() / "config" / "irena_reference.yaml").read_text(encoding="utf-8"))["editions"]["irena_rpgc_2024"]["pairs"][iso][tech]
    tic = float(irena["tic_usd_per_kw"]["value"])
    assert float(s0["capex_usd_per_kw"]) == pytest.approx(tic, rel=1e-12)
    assert float(s0["opex_fixed_frac"]) * float(s0["capex_usd_per_kw"]) == pytest.approx(float(s0["opex_fixed_frac"]) * tic, rel=1e-12)
