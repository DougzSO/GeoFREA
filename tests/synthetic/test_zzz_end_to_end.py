"""The synthetic country through F1 to F6 with no network (A-06, V-08, I-4, D13b, D-F6-014).

The ZZZ fixture and its miniature climate inputs are generated into a scratch data directory; the orchestrator then runs data_acquisition,
data_quality_audit, grid_alignment, siting_layers, land_eligibility (F3), external_inputs, climate_forcing (F4), technical_potential and
potential_maps (F5), lcoe_modeling and sample_size_convergence (F6) on them. The experiments file is copied with small sizes for
the sample-size protocol (initial size 16, ceiling 64, top-k 25 percent): the real values are the author's and are null there. Every socket connection is refused while the pipeline runs, so a hidden download fails the test.

The synthetic world must not depend on the real turbine file: this test copies the
registry and points the phase at the synthetic curve of `tests/fixtures/power_curves/`; the design-class flag of the real registry is kept.
The ZZZ land cover has three bands of whole decision cells: cropland (north, excluded for solar), grassland (middle, allowed for both) and
tree cover (south, excluded for both). Solar therefore has candidates only in the grassland band, where the population gradient and the
river's setback trim them; wind has candidates in the cropland and grassland bands. Both technologies run through every phase.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
import rasterio
import yaml

from geofrea.core.config_loader import load_audit_config, load_settings
from geofrea.land_eligibility.cells import pixel_row_area_km2

REPO = Path(__file__).resolve().parents[2]
CURVES = REPO / "tests" / "fixtures" / "power_curves"
PHASES = [
    "hazard_context",
    "technical_potential",
    "potential_maps",
    "lcoe_modeling",
    "sample_size_convergence",
    "robustness_analysis",
    "external_validation",
    "lcoe_maps",
    "robustness_maps",
    "results_synthesis",
]
INITIAL_SIZE, CEILING = 16, 64
SCENARIOS = ("central", "restrictive", "permissive")
MASKED_MEMBER = "m_cnrm_cm6_1_ssp370_2071_2100"
N_NO_WIND = 6  # the MIROC6 members: no wind channel (M-F4-02 item 6)
N_CELLS = 24  # 6 x 4 decision cells
N_MEMBERS = 37  # 36 and the reference member


class NetworkUsedError(AssertionError):
    pass


def _no_network(*_args, **_kwargs):
    raise NetworkUsedError("the ZZZ pipeline tried to open a network connection")


IPSL = "IPSL-CM6A-LR"  # the GCM that carries the TCR exception


def _the_ipsl_futures_displace_the_shortlist(patch):
    """The synthetic world keeps the order of its cells in every future, so the real outcome of the scenario discovery (the capacity share of the
    nominal shortlist that falls beyond the tolerance) is 0 everywhere and PRIM has nothing to find. In this run the outcome of a future is set by a
    rule on the climate model (half the shortlist when the GCM is IPSL, a twentieth otherwise), so that the box, its bootstrap and T-O1 are exercised end
    to end; the outcome itself is checked against its definition in `test_robustness_futures.py`."""
    from dataclasses import replace

    import numpy as np

    from geofrea.robustness_analysis import pipeline

    real = pipeline.futures_pass

    def rule(worlds, labels, samples, top, k, **kwargs):
        result = real(worlds, labels, samples, top, k, **kwargs)
        shares = np.array([[0.5 if label.gcm == IPSL else 0.05] for label in labels])
        shape = result.share_leaving.shape
        return replace(result, displaced_capacity_share=np.broadcast_to(shares, shape).copy())

    patch.setattr(pipeline, "futures_pass", rule)


@pytest.fixture(scope="module")
def zzz(tmp_path_factory):
    import main  # repo-root script

    data = tmp_path_factory.mktemp("zzz_data")
    registry = yaml.safe_load((REPO / "config" / "technologies.yaml").read_text(encoding="utf-8"))
    registry["wind"]["power_curve"] = "synthetic_curve"
    technologies = data / "technologies_with_synthetic_rule.yaml"
    technologies.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    experiments_text = (REPO / "config" / "experiments.yaml").read_text(encoding="utf-8")
    for old, new in (
        ("initial_size: 500", f"initial_size: {INITIAL_SIZE}"),
        ("max_size_for_convergence: null", f"max_size_for_convergence: {CEILING}"),
        # test values for the pre-registered settings, in this copy only (OQ-050, OQ-051, OQ-056)
        ("tx35_days: {threshold: null,", "tx35_days: {threshold: 1.0,"),
        ("tx40_days: {threshold: null,", "tx40_days: {threshold: 1.0,"),
        ("rx5day_mm: {threshold: null,", "rx5day_mm: {threshold: 1.0,"),
        ("wet_p95_exceed_freq: {threshold: null,", "wet_p95_exceed_freq: {threshold: 0.0,"),
        ("gust_mean_annual_max_ms: {threshold: null,", "gust_mean_annual_max_ms: {threshold: 1.0,"),
        (
            "national_targets:\n",
            (
                "national_targets:\n"
                "  ZZZ:\n"
                '    solar: {value: 0.0001, unit: GW, source: "ZZZ test value", horizon: 2040, alternatives: []}\n'
                '    wind: {value: 0.0001, unit: GW, source: "ZZZ test value", horizon: 2040, alternatives: []}\n'
            ),
        ),
        (
            "bootstrap_replicates: 200",
            "bootstrap_replicates: 10",
        ),  # the pre-registered 200 are tested apart
        (
            'source: "OQ-050 (H5), pre-registered 2026-10-14"\n',
            (
                'source: "OQ-050 (H5), pre-registered 2026-10-14"\n'
                "  RQ4: [{statistic: mr_sr_kendall_tau_b, comparison: ge, threshold: -2.0}]\n"
            ),
        ),
    ):
        assert experiments_text.count(old) == 1, old
        experiments_text = experiments_text.replace(old, new)
    experiments = data / "experiments_zzz.yaml"
    experiments.write_text(experiments_text, encoding="utf-8")

    patch = pytest.MonkeyPatch()
    patch.setenv("GEOFREA_DATA_DIR", str(data))
    patch.setattr(main, "TECHNOLOGIES_YAML", technologies)
    patch.setattr(main, "EXPERIMENTS_YAML", experiments)
    patch.setattr(main, "POWER_CURVES_DIR", CURVES)
    _the_ipsl_futures_displace_the_shortlist(patch)
    try:
        subprocess.run(
            [sys.executable, str(REPO / "scripts" / "generate_zzz_fixture.py")],
            check=True,
            env={**os.environ, "GEOFREA_DATA_DIR": str(data)},
            capture_output=True,
        )
        settings = load_settings(main.SETTINGS_YAML)
        patch.setattr(socket.socket, "connect", _no_network)
        patch.setattr(socket, "create_connection", _no_network)
        ok, _orchestrator, results = main.run_geofrea(
            "ZZZ",
            PHASES,
            [],
            settings.geospatial.resolutions,
            settings.geospatial.distance_cap_km,
            load_audit_config(main.AUDIT_YAML),
            "zzz-end-to-end",
            False,
            None,
            tuple(settings.run.technologies),
            False,
            settings.figures,
            settings.memory.max_batch_gb,
        )
        assert ok, {k: v.status for k, v in results.items()}
        # what main.main does after the country runs: the support phase cross_country_h4, then the thesis outputs again
        from geofrea.results_synthesis.runner import build_thesis
        from geofrea.robustness_analysis.cross_country import build_h4_verdict

        build_h4_verdict(["ZZZ"], tuple(settings.run.technologies))
        build_thesis(
            "ZZZ",
            tuple(settings.run.technologies),
            technologies_yaml=main.TECHNOLOGIES_YAML,
            experiments_yaml=main.EXPERIMENTS_YAML,
            parameters_json=main.PARAMETERS_JSON,
            methodology_md=main.METHODOLOGY_MD,
            phase_graph=main.thesis_phase_graph(tuple(settings.run.technologies)),
        )
        yield data, results
    finally:
        patch.undo()


@pytest.fixture(scope="module")
def zzz_fine(zzz):
    """The same phases at the 0.1 degree scale (V-07) in the same data directory: only the `scale` argument differs."""
    import main

    settings = load_settings(main.SETTINGS_YAML)
    ok, _orchestrator, results = main.run_geofrea(
        "ZZZ",
        PHASES,
        [],
        settings.geospatial.resolutions,
        settings.geospatial.distance_cap_km,
        load_audit_config(main.AUDIT_YAML),
        "zzz-end-to-end-0p1deg",
        False,
        None,
        tuple(settings.run.technologies),
        False,
        settings.figures,
        settings.memory.max_batch_gb,
        "0p1deg",
    )
    assert ok, {k: v.status for k, v in results.items()}
    return zzz[0], results


def _phase(zzz, phase, kind="artifacts"):
    """`outputs/ZZZ/<phase>/<kind>` of the scratch data directory (the autouse conftest fixture re-points the env var per test)."""
    return zzz[0] / "outputs" / "ZZZ" / phase / kind


def _eligibility(zzz, tech, scenario):
    return pd.read_parquet(_phase(zzz, "land_eligibility") / f"cells_{tech}__{scenario}.parquet")


@pytest.mark.synthetic
def test_every_phase_from_f1_to_f6_runs_and_succeeds(zzz):
    _, results = zzz
    assert {name: r.status for name, r in results.items()} == {
        name: "success"
        for name in (
            "data_acquisition",
            "data_quality_audit",
            "grid_alignment",
            "siting_layers",
            "land_eligibility",
            "external_inputs",
            "climate_forcing",
            "hazard_context",
            "technical_potential",
            "potential_maps",
            "lcoe_modeling",
            "sample_size_convergence",
            "robustness_analysis",
            "external_validation",
            "lcoe_maps",
            "robustness_maps",
            "results_synthesis",
        )
    }


# -- I-4: F3 invariants --------------------------------------------------------------------------


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_eligible_area_never_exceeds_the_cell_area(zzz, tech, scenario):
    cells = _eligibility(zzz, tech, scenario)
    assert len(cells) == N_CELLS
    assert (cells["eligible_area_km2"] >= 0).all()
    assert (cells["eligible_area_km2"] <= cells["cell_area_km2"] * (1 + 1e-9)).all()
    excluded = sum(cells[f"excluded_area_km2_E{i}"] for i in range(1, 7))
    assert (cells["eligible_area_km2"] + 0 <= cells["cell_area_km2"]).all() and (
        excluded >= 0
    ).all()


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_the_sum_of_cell_eligible_areas_equals_the_pixel_total(zzz, tech):
    """Independent of F3's own check: read the eligible-fraction raster and weight each pixel by its geodesic area."""
    art = _phase(zzz, "land_eligibility")
    with rasterio.open(art / f"eligible_fraction_{tech}.tif") as src:
        fraction = src.read(1, masked=True).astype("float64")
        area = pixel_row_area_km2(src.transform, src.height)[:, None]
    pixel_total = float(np.ma.filled(fraction * area, 0.0).sum())
    cell_total = float(_eligibility(zzz, tech, "central")["eligible_area_km2"].sum())
    assert cell_total == pytest.approx(pixel_total, rel=1e-6)


@pytest.mark.synthetic
def test_the_three_scenarios_are_ordered_by_eligible_area(zzz):
    for tech in ("solar", "wind"):
        total = {s: _eligibility(zzz, tech, s)["eligible_area_km2"].sum() for s in SCENARIOS}
        assert total["restrictive"] <= total["central"] <= total["permissive"]


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_every_cell_carries_the_admin1_unit_of_its_half_of_the_country(zzz, tech, scenario):
    """D-F3-012: the ZZZ border splits the country into a west and an east half of three cell columns each."""
    cells = _eligibility(zzz, tech, scenario)
    assert cells["admin1_id"].notna().all()
    west = cells["admin1_id"] == "ZZZ.1_1"
    assert west.sum() == N_CELLS // 2 and (cells["admin1_id"] == "ZZZ.2_1").sum() == N_CELLS // 2
    assert cells.loc[west, "col"].max() < cells.loc[~west, "col"].min()
    units = pd.read_parquet(_phase(zzz, "land_eligibility") / "admin1_units.parquet")
    assert units.set_index("admin1_id")["n_cells"].to_dict() == {"ZZZ.1_1": 12, "ZZZ.2_1": 12}
    candidates = pd.read_parquet(
        _phase(zzz, "land_eligibility") / f"candidates_{tech}__{scenario}.parquet"
    )
    merged = candidates.merge(
        cells[["cell_id", "admin1_id"]], on="cell_id", suffixes=("", "_cells")
    )
    assert (merged["admin1_id"] == merged["admin1_id_cells"]).all()


# -- F4 on the miniature CMIP6 files ---------------------------------------------------------------


@pytest.mark.synthetic
def test_the_forcing_comes_from_the_miniature_cmip6_files_and_declares_its_masked_cell_members(zzz):
    art = _phase(zzz, "climate_forcing")
    forcing, masked = (
        pd.read_parquet(art / "forcing.parquet"),
        pd.read_parquet(art / "forcing_masked.parquet"),
    )
    assert (
        len(forcing) == N_CELLS * N_MEMBERS
    )  # a row for every cell and member, whatever the wind ratio (M-F4-07)
    assert set(masked["member"].astype(str)) == {MASKED_MEMBER} and len(masked) > 0
    nan = forcing[forcing["delta_wind"].isna()].assign(member=lambda d: d["member"].astype(str))
    no_wind = nan["member"].str.startswith("m_miroc6")
    assert (
        no_wind.sum() == N_CELLS * N_NO_WIND
    )  # every cell of the MIROC6 members, declared by `members.yaml`
    assert set(zip(nan.loc[~no_wind, "cell_id"], nan.loc[~no_wind, "member"], strict=True)) == set(
        zip(masked["cell_id"], masked["member"].astype(str), strict=True)
    )  # every other NaN is a declared mask
    assert forcing["dT_isolated_native_cell"].dtype == bool
    members = yaml.safe_load((art / "members.yaml").read_text(encoding="utf-8"))
    channels = {m["member"]: m["channels"] for m in members["members"]}
    assert channels["m_miroc6_ssp370_2041_2070"] == {
        "resource_rsds": True,
        "resource_tas": True,
        "resource_wind": False,
        "hazard": False,
    }
    assert (
        channels[MASKED_MEMBER]["resource_wind"] is True and "dt_isolated_cell_members" in members
    )
    lo, hi = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))[
        "gcm_ensemble"
    ]["wind_factor_valid_range"]
    assert ((masked["delta_wind"] < lo) | (masked["delta_wind"] > hi)).all()
    assert forcing["delta_wind"].dropna().between(lo, hi).all()
    m0 = forcing[forcing["member"].astype(str) == "m0"]
    assert (m0["delta_rsds"] == 1).all() and (m0["dT"] == 0).all() and (m0["delta_wind"] == 1).all()
    warm = forcing[forcing["member"].astype(str) != "m0"]
    assert (warm["dT"] > 0).all()  # every synthetic window warms


# -- F5 --------------------------------------------------------------------------------------------


@pytest.mark.synthetic
def test_f5_writes_the_tables_for_three_scenarios_and_the_aggregates_with_both_series(zzz):
    art = _phase(zzz, "technical_potential")
    for tech in ("solar", "wind"):
        for scenario in SCENARIOS:
            assert (art / f"potential_{tech}__{scenario}.parquet").is_file()
        agg = pd.read_parquet(art / f"potential_aggregates_{tech}.parquet")
        # wind: no MIROC6 member (no altitude-sensitivity rows: the cells above 3000 m are not candidates, OQ-058)
        assert len(agg) == (3 * (N_MEMBERS - N_NO_WIND) if tech == "wind" else 3 * N_MEMBERS)
        assert {"P_GW", "P_GW_like_for_like", "E_TWh", "E_TWh_like_for_like"} <= set(agg.columns)


@pytest.mark.synthetic
def test_solar_has_candidates_only_in_the_grassland_band(zzz):
    for scenario in SCENARIOS:
        candidates = pd.read_parquet(
            _phase(zzz, "land_eligibility") / f"candidates_solar__{scenario}.parquet"
        )
        assert len(candidates) == 6  # one decision-cell row of the grassland band, six cells
        assert candidates["row"].nunique() == 1
    central = _eligibility(zzz, "solar", "central")
    assert (
        central.groupby("row")["eligible_area_km2"].sum().gt(0).sum() == 1
    )  # no eligible area outside that row
    assert (
        central["dominant_exclusion"].eq("E5").sum() >= 12
    )  # cropland and tree cover rows are land-cover exclusions


@pytest.mark.synthetic
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_solar_follows_m_f5_02_with_the_forcing_f4_wrote(zzz, scenario):
    """Every solar row: `CF = pvout / 24 * delta_rsds * (1 + gamma * dT)` with the F4 factors of its cell and member (M-F5-02)."""
    art = _phase(zzz, "technical_potential")
    table = pd.read_parquet(art / f"potential_solar__{scenario}.parquet")
    candidates = pd.read_parquet(
        _phase(zzz, "land_eligibility") / f"candidates_solar__{scenario}.parquet"
    )
    forcing = pd.read_parquet(_phase(zzz, "climate_forcing") / "forcing.parquet").astype(
        {"delta_rsds": "float64", "dT": "float64"}  # F4 stores float32; F5 computes in float64
    )
    table["member"] = table["member"].astype(str)
    forcing["member"] = forcing["member"].astype(str)
    merged = table.merge(
        forcing, on=["cell_id", "member"], how="left", validate="one_to_one"
    ).merge(
        candidates[["cell_id", "pvout_kwh_kwp_day", "eligible_area_km2"]],
        on="cell_id",
        validate="many_to_one",
    )
    assert merged["delta_rsds"].notna().all()
    gamma = -0.005  # ZZZ test value in config/parameters.json
    expected_cf = (
        merged["pvout_kwh_kwp_day"] / 24.0 * merged["delta_rsds"] * (1.0 + gamma * merged["dT"])
    )
    np.testing.assert_allclose(merged["CF"], expected_cf, rtol=1e-12)
    np.testing.assert_allclose(
        merged["P_MW"], merged["eligible_area_km2"] * 5.0, rtol=1e-12
    )  # luf 0.5 x 10 MW/km2
    np.testing.assert_allclose(merged["E_MWh"], merged["P_MW"] * merged["CF"] * 8760.0, rtol=1e-12)
    m0 = merged[merged["member"] == "m0"]
    np.testing.assert_allclose(
        m0["CF"], m0["pvout_kwh_kwp_day"] / 24.0, rtol=1e-12
    )  # the reference member is PVOUT / 24
    # a cell-member masked for the wind factor keeps its solar row: solar never loses a cell-member for a wind reason (M-F4-07)
    assert len(table) == len(candidates) * N_MEMBERS


@pytest.mark.synthetic
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_wind_potential_has_no_row_for_a_declared_masked_cell_member_and_a_row_for_every_other(
    zzz, scenario
):
    art = _phase(zzz, "technical_potential")
    table = pd.read_parquet(art / f"potential_wind__{scenario}.parquet")
    candidates = pd.read_parquet(
        _phase(zzz, "land_eligibility") / f"candidates_wind__{scenario}.parquet"
    )
    masked = pd.read_parquet(_phase(zzz, "climate_forcing") / "forcing_masked.parquet")
    masked_candidates = masked[masked["cell_id"].isin(candidates["cell_id"])]
    assert len(table) == len(candidates) * (N_MEMBERS - N_NO_WIND) - len(masked_candidates)
    assert not table["member"].astype(str).str.startswith("m_miroc6").any()  # absent by declaration
    present = set(zip(table["cell_id"], table["member"].astype(str), strict=True))
    for cell, member in zip(
        masked_candidates["cell_id"], masked_candidates["member"].astype(str), strict=True
    ):
        assert (cell, member) not in present
    agg = pd.read_parquet(art / "potential_aggregates_wind.parquet")
    row = agg[(agg["scenario"] == scenario) & (agg["member"] == MASKED_MEMBER)].iloc[0]
    assert row["n_cells_absent"] == len(masked_candidates)
    assert row["n_cells_like_for_like"] == len(candidates) - masked_candidates["cell_id"].nunique()


@pytest.mark.synthetic
def test_wind_invariants_cf_range_capacity_constant_and_country_equals_sum_of_cells(zzz):
    art = _phase(zzz, "technical_potential")
    table = pd.read_parquet(art / "potential_wind__central.parquet")
    assert ((table["CF"] > 0) & (table["CF"] <= 1)).all()
    assert (table.groupby("cell_id")["P_MW"].nunique() == 1).all()
    m0 = table[table["member"].astype(str) == "m0"]
    agg = pd.read_parquet(art / "potential_aggregates_wind.parquet")
    row = agg[(agg["scenario"] == "central") & (agg["member"] == "m0")].iloc[0]
    assert row["P_GW"] * 1e3 == pytest.approx(m0["P_MW"].sum(), rel=1e-12)
    # capacity follows M-F5-01 with the ZZZ test values luf 0.5 and 10 MW/km2
    candidates = pd.read_parquet(
        _phase(zzz, "land_eligibility") / "candidates_wind__central.parquet"
    )
    np.testing.assert_allclose(
        m0.sort_values("cell_id")["P_MW"].to_numpy(),
        candidates.sort_values("cell_id")["eligible_area_km2"].to_numpy() * 5.0,
        rtol=1e-12,
    )


@pytest.mark.synthetic
def test_potential_maps_write_cog_rasters_and_the_figures_the_setting_allows(zzz):
    art = _phase(zzz, "technical_potential")
    with rasterio.open(art / "potential_density_wind.tif") as src:
        data = src.read(1, masked=True)
        assert src.crs.to_epsg() == 4326 and src.profile["tiled"] is True
    candidates = pd.read_parquet(
        _phase(zzz, "land_eligibility") / "candidates_wind__central.parquet"
    )
    assert data.count() == len(candidates)
    expected = (
        candidates["eligible_area_km2"] * 5.0 / candidates["cell_area_km2"]
    )  # luf 0.5 x 10 MW/km2
    assert float(data.max()) == pytest.approx(float(expected.max()), rel=1e-5)
    with rasterio.open(art / "potential_density_solar.tif") as src:
        assert src.read(1, masked=True).count() == 6  # the six solar candidate cells
    figures = _phase(zzz, "technical_potential", "figures")
    assert (figures / "potential_density_wind__ref__na__na.png").is_file()
    assert (figures / "potential_density_solar__ref__na__na.png").is_file()


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_potential_maps_write_the_maps_of_capacity_and_energy_per_cell_and_per_state(zzz, tech):
    """D-F5-029: 8 maps and the limits file per technology; monotone limits; the states add up to the F5 total; the files are artifacts."""
    from tests.synthetic.absolute_maps_checks import check_absolute_maps

    content = check_absolute_maps(zzz[0], "ZZZ", tech)
    assert set(content["per_state"]["land_scenarios"]) == {"central", "restrictive", "permissive"}


# -- F6 --------------------------------------------------------------------------------------------


def _hand_lcoe(p, dist_grid, dist_road, e_year1, s):
    """M-F6-01 year by year with plain floats, independent of the kernel module."""
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


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_f6_produces_the_summary_design_matrix_and_supply_curve_from_the_f5_table(zzz, tech):
    art = _phase(zzz, "lcoe_modeling")
    potential = pd.read_parquet(
        _phase(zzz, "technical_potential") / f"potential_{tech}__central.parquet"
    )
    summary = pd.read_parquet(art / f"lcoe_summary_{tech}.parquet")
    design = pd.read_parquet(art / f"design_matrix_{tech}.parquet")
    supply = pd.read_parquet(art / f"supply_curve_{tech}.parquet")
    assert len(summary) == len(potential) == len(supply)  # one row per cell-member, in every table
    assert len(design) == INITIAL_SIZE + 1 and design["sample"].iloc[0] == 0
    assert (
        np.isfinite(
            summary[["lcoe_nominal", "lcoe_mean", "lcoe_var", "lcoe_p10", "lcoe_p50", "lcoe_p90"]]
        )
        .all()
        .all()
    )
    assert (summary["lcoe_p10"] <= summary["lcoe_p50"]).all() and (
        summary["lcoe_p50"] <= summary["lcoe_p90"]
    ).all()
    assert (summary["n_nonfinite"] == 0).all()
    cells = potential.drop_duplicates("cell_id")
    assert summary["cell_id"].nunique() == len(cells)  # no cell lost


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
@pytest.mark.parametrize("scenario", ["restrictive", "permissive"])
def test_f6_writes_the_nominal_lcoe_of_the_other_land_scenarios_with_no_draws(zzz, tech, scenario):
    """D-F6-018: one row per cell and member of the scenario's F5 table, only the nominal LCOE, finite and positive."""
    table = pd.read_parquet(
        _phase(zzz, "lcoe_modeling") / f"lcoe_nominal_{tech}__{scenario}.parquet"
    )
    potential = pd.read_parquet(
        _phase(zzz, "technical_potential") / f"potential_{tech}__{scenario}.parquet"
    )
    assert list(table.columns) == ["cell_id", "member", "lcoe_nominal"]
    assert len(table) == len(potential)
    assert np.isfinite(table["lcoe_nominal"]).all() and (table["lcoe_nominal"] > 0).all()
    keys = set(zip(table["cell_id"], table["member"].astype(str), strict=True))
    assert keys == set(zip(potential["cell_id"], potential["member"].astype(str), strict=True))


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_f6_summary_row_is_reproduced_by_hand_from_the_pipeline_tables(zzz, tech):
    """A row of the F6 summary, recomputed from the F5 and F3 tables, the F4 forcing and the stored design matrix by plain arithmetic."""
    from geofrea.core.config_loader import load_parameters

    art = _phase(zzz, "lcoe_modeling")
    summary = pd.read_parquet(art / f"lcoe_summary_{tech}.parquet").astype({"member": str})
    design = pd.read_parquet(art / f"design_matrix_{tech}.parquet").set_index("sample")
    potential = pd.read_parquet(
        _phase(zzz, "technical_potential") / f"potential_{tech}__central.parquet"
    ).astype({"member": str})
    candidates = pd.read_parquet(
        _phase(zzz, "land_eligibility") / f"candidates_{tech}__central.parquet"
    ).set_index("cell_id")
    forcing = pd.read_parquet(_phase(zzz, "climate_forcing") / "forcing.parquet").astype(
        {"member": str}
    )
    nominal = {
        k: float(v.value)
        for k, v in getattr(
            load_parameters(REPO / "config" / "parameters.json").countries["ZZZ"].technologies, tech
        ).__dict__.items()
        if hasattr(v, "value") and v.value is not None
    }
    energy_key = "gamma" if tech == "solar" else "eta_loss"
    warm = forcing[(forcing["member"] != "m0")].merge(potential, on=["cell_id", "member"])
    pick = warm.iloc[len(warm) // 2]
    cell, member = int(pick["cell_id"]), pick["member"]
    d_t = float(pick["dT"])

    def lcoe_of(sample):
        s = {
            k: float(design.loc[sample, k]) if k in design.columns else v
            for k, v in nominal.items()
        }
        x, x0 = s[energy_key], nominal[energy_key]
        factor = (1 + x * d_t) / (1 + x0 * d_t) if tech == "solar" else x / x0
        return _hand_lcoe(
            pick["P_MW"],
            candidates.loc[cell, "dist_grid_km"],
            candidates.loc[cell, "dist_road_km"],
            pick["E_MWh"] * factor,
            s,
        )

    draws = np.array([lcoe_of(i) for i in range(1, len(design))])
    row = summary[(summary["cell_id"] == cell) & (summary["member"] == member)].iloc[0]
    assert row["lcoe_nominal"] == pytest.approx(lcoe_of(0), rel=1e-10)
    assert row["lcoe_mean"] == pytest.approx(draws.mean(), rel=1e-10)
    assert row["lcoe_var"] == pytest.approx(draws.var(ddof=1), rel=1e-8)
    for column, q in (("lcoe_p10", 0.1), ("lcoe_p50", 0.5), ("lcoe_p90", 0.9)):
        assert row[column] == pytest.approx(np.quantile(draws, q), rel=1e-10)


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_sample_size_convergence_runs_on_zzz_with_small_sizes_to_prove_the_mechanism(zzz, tech):
    """D-F6-004: the protocol doubles from the initial size within the ceiling; its MR is the definitive function of F7 (D-F7-027)."""
    table = pq.read_table(
        _phase(zzz, "sample_size_convergence") / f"sample_size_convergence_{tech}.parquet"
    )
    meta = json.loads(table.schema.metadata[b"geofrea_convergence_provenance"])
    rows = table.to_pandas()
    assert meta["provisional"] is False and meta["mr_function"] == "f7"
    assert meta["cf_min"] > 0 and meta["top_k_percent"] == 25.0
    sizes = rows["n_samples"].tolist()
    assert sizes[0] == INITIAL_SIZE and sizes == [INITIAL_SIZE * 2**i for i in range(len(sizes))]
    assert max(sizes) <= CEILING and rows["k"].nunique() == 1
    assert np.isnan(rows["jaccard_with_previous"].iloc[0])
    converged = rows["meets_tolerance"].tolist()
    assert meta["adopted_size"] == (sizes[converged.index(True)] if any(converged) else None)
    summary = json.loads(
        (zzz[0] / "outputs" / "ZZZ" / "artifacts" / "sample_size_convergence.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["technologies"][tech]["adopted_size"] == meta["adopted_size"]
    assert summary["technologies"][tech]["mr_function"] == "f7"


# -- the scale check: F3 to F6 at 0.1 degree with the same code (V-07, D-F3-013, D-F4-020) --------------


def _fine(zzz_fine, phase, kind="artifacts"):
    return zzz_fine[0] / "outputs" / "ZZZ" / f"{phase}__0p1deg" / kind


@pytest.mark.synthetic
def test_the_scale_check_runs_every_phase_and_leaves_the_default_scale_untouched(zzz, zzz_fine):
    data, results = zzz_fine
    assert {r.status for r in results.values()} == {"success"}
    assert (data / "outputs" / "ZZZ" / "manifest__0p1deg.json").is_file()
    assert (data / "outputs" / "ZZZ" / "manifest.json").is_file()
    for phase in ("land_eligibility", "climate_forcing", "technical_potential", "lcoe_modeling"):
        assert (data / "outputs" / "ZZZ" / f"{phase}__0p1deg").is_dir()
    assert (
        len(_eligibility(zzz, "wind", "central")) == N_CELLS
    )  # the 0.05 degree tables are the ones of the first run
    assert not list(
        _fine(zzz_fine, "land_eligibility").glob("cells_0p1deg_*")
    )  # the 2 x 2 area check is a 0.05 degree output


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_the_coarse_cells_hold_the_same_land_and_eligible_area_as_the_fine_cells(
    zzz, zzz_fine, tech, scenario
):
    from geofrea.land_eligibility.cells import coarse_cell_id

    fine = _eligibility(zzz, tech, scenario)
    coarse = pd.read_parquet(
        _fine(zzz_fine, "land_eligibility") / f"cells_{tech}__{scenario}.parquet"
    )
    assert set(coarse["cell_id"]) == set(coarse_cell_id(fine["cell_id"].to_numpy()))
    assert len(coarse) < len(fine)
    for column in ("cell_area_km2", "eligible_area_km2"):
        assert coarse[column].sum() == pytest.approx(fine[column].sum(), rel=1e-9)
    assert (
        coarse["cell_id"] // 3600 == coarse["row"]
    ).all()  # the 0.1 degree lattice is 3600 columns wide
    assert coarse["admin1_id"].notna().all()


@pytest.mark.synthetic
def test_the_forcing_is_interpolated_at_the_coarse_centers_for_every_member(zzz, zzz_fine):
    forcing = pd.read_parquet(_fine(zzz_fine, "climate_forcing") / "forcing.parquet")
    masked = pd.read_parquet(_fine(zzz_fine, "climate_forcing") / "forcing_masked.parquet")
    cells = _eligibility_fine(zzz_fine, "wind", "central")
    assert set(forcing["cell_id"]) == set(cells["cell_id"])
    assert len(forcing) == len(cells) * N_MEMBERS
    assert set(masked["member"].astype(str)) <= {MASKED_MEMBER}


def _eligibility_fine(zzz_fine, tech, scenario):
    return pd.read_parquet(
        _fine(zzz_fine, "land_eligibility") / f"cells_{tech}__{scenario}.parquet"
    )


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_f5_and_f6_run_on_the_coarse_cells_with_the_same_files(zzz, zzz_fine, tech):
    candidates = pd.read_parquet(
        _fine(zzz_fine, "land_eligibility") / f"candidates_{tech}__central.parquet"
    )
    potential = pd.read_parquet(
        _fine(zzz_fine, "technical_potential") / f"potential_{tech}__central.parquet"
    )
    summary = pd.read_parquet(_fine(zzz_fine, "lcoe_modeling") / f"lcoe_summary_{tech}.parquet")
    assert set(potential["cell_id"]) <= set(candidates["cell_id"])
    assert len(summary) == len(potential) > 0
    assert set(zip(summary["cell_id"], summary["member"].astype(str), strict=True)) == set(
        zip(potential["cell_id"], potential["member"].astype(str), strict=True)
    )


# -- F7 ----------------------------------------------------------------------------------------------------


def _robustness(zzz, tech, role="core"):
    return pd.read_parquet(
        _phase(zzz, "robustness_analysis") / f"robustness_{tech}__{role}.parquet"
    )


class _HandWorld:
    """The ZZZ tables of one technology, read back for plain-arithmetic LCOE of any (cell, member, sample)."""

    def __init__(self, zzz, tech):
        from geofrea.core.config_loader import load_parameters

        self.tech = tech
        art = _phase(zzz, "lcoe_modeling")
        self.design = pd.read_parquet(art / f"design_matrix_{tech}.parquet").set_index("sample")
        self.potential = (
            pd.read_parquet(
                _phase(zzz, "technical_potential") / f"potential_{tech}__central.parquet"
            )
            .astype({"member": str})
            .set_index(["cell_id", "member"])
        )
        self.candidates = pd.read_parquet(
            _phase(zzz, "land_eligibility") / f"candidates_{tech}__central.parquet"
        ).set_index("cell_id")
        self.forcing = (
            pd.read_parquet(_phase(zzz, "climate_forcing") / "forcing.parquet")
            .astype({"member": str})
            .set_index(["cell_id", "member"])
        )
        params = getattr(
            load_parameters(REPO / "config" / "parameters.json").countries["ZZZ"].technologies, tech
        )
        self.nominal = {
            k: float(v.value)
            for k, v in params.__dict__.items()
            if hasattr(v, "value") and v.value is not None
        }
        self.energy_key = "gamma" if tech == "solar" else "eta_loss"

    def lcoe(self, cell, member, sample):
        s = {
            k: float(self.design.loc[sample, k]) if k in self.design.columns else v
            for k, v in self.nominal.items()
        }
        x, x0 = s[self.energy_key], self.nominal[self.energy_key]
        row = self.potential.loc[(cell, member)]
        d_t = float(self.forcing.loc[(cell, member), "dT"])
        factor = (1 + x * d_t) / (1 + x0 * d_t) if self.tech == "solar" else x / x0
        return _hand_lcoe(
            row["P_MW"],
            self.candidates.loc[cell, "dist_grid_km"],
            self.candidates.loc[cell, "dist_road_km"],
            row["E_MWh"] * factor,
            s,
        )


def _carries(entry, tech):
    """The member declares the channel the technology reads (M-F4-06): wind needs `resource_wind`, solar reads none of the wind channel."""
    return entry["channels"]["resource_wind"] if tech == "wind" else True


def _core_members(zzz, tech=None):
    entries = yaml.safe_load(
        (_phase(zzz, "climate_forcing") / "members.yaml").read_text(encoding="utf-8")
    )["members"]
    return [e["member"] for e in entries if e["window"] == "2041-2070" and _carries(e, tech)]


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_f7_classifies_every_candidate_and_ranks_the_whole_f7_set_in_the_core_window(zzz, tech):
    table = _robustness(zzz, tech)
    candidates = pd.read_parquet(
        _phase(zzz, "land_eligibility") / f"candidates_{tech}__central.parquet"
    )
    assert sorted(table["cell_id"]) == sorted(candidates["cell_id"])
    assert set(table["cell_class"]) == {"ranked"}  # cf_min is below every synthetic member
    assert (table["failing_members"].map(len) == 0).all()
    assert sorted(table["robust_rank"]) == list(range(1, len(table) + 1))
    assert sorted(table["nominal_rank"]) == list(range(1, len(table) + 1))
    assert (table["mr"] >= 0).all() and table["sr"].between(0, 1).all()
    assert table["topk_robust"].sum() == table["topk_nominal"].sum() == -(-len(table) // 4)
    assert set(table["admin1_id"]) <= {"ZZZ.1_1", "ZZZ.2_1"}


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_f7_nominal_lcoe_is_the_nominal_lcoe_of_f6_for_the_reference_and_every_core_member(
    zzz, tech
):
    nominal = pd.read_parquet(
        _phase(zzz, "robustness_analysis") / f"nominal_lcoe_by_member_{tech}__core.parquet"
    ).astype({"member": str})
    f6 = pd.read_parquet(_phase(zzz, "lcoe_modeling") / f"lcoe_summary_{tech}.parquet").astype(
        {"member": str}
    )
    merged = nominal.merge(
        f6, on=["cell_id", "member"], suffixes=("", "_f6"), validate="one_to_one"
    )
    assert (
        len(merged)
        == len(nominal)
        == len(_robustness(zzz, tech)) * (1 + len(_core_members(zzz, tech)))
    )
    np.testing.assert_allclose(merged["lcoe_nominal"], merged["lcoe_nominal_f6"], rtol=1e-13)


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_f7_max_regret_of_a_cell_is_recomputed_by_hand_from_the_pipeline_tables(zzz, tech):
    """M-F7-03 with plain arithmetic: regret against the lowest LCOE of each future, P90 over the draws, maximum over the members."""
    world = _HandWorld(zzz, tech)
    table = _robustness(zzz, tech).set_index("cell_id")
    cells = table.index.to_list()
    probe = table.sort_values("robust_rank").index[len(table) // 2]
    draws = range(1, len(world.design))
    per_member = []
    for member in _core_members(zzz, tech):
        regrets = []
        for s in draws:
            lcoe = {c: world.lcoe(c, member, s) for c in cells}
            lowest = min(lcoe.values())
            regrets.append((lcoe[probe] - lowest) / lowest)
        per_member.append(np.quantile(regrets, 0.9))
    assert table.loc[probe, "mr"] == pytest.approx(max(per_member), rel=1e-9)
    # the same cell under the two single-axis families
    climate_only = 0.0
    for member in _core_members(zzz, tech):
        lowest = min(world.lcoe(c, member, 0) for c in cells)
        climate_only = max(climate_only, (world.lcoe(probe, member, 0) - lowest) / lowest)
    assert table.loc[probe, "mr_clim"] == pytest.approx(climate_only, rel=1e-9)
    regrets = []
    for s in draws:
        lcoe = {c: world.lcoe(c, "m0", s) for c in cells}
        lowest = min(lcoe.values())
        regrets.append((lcoe[probe] - lowest) / lowest)
    assert table.loc[probe, "mr_tech"] == pytest.approx(np.quantile(regrets, 0.9), rel=1e-9)


@pytest.mark.synthetic
def test_f7_flags_the_cells_a_masked_member_removes_from_the_sensitivity_window(zzz):
    """D-F5-006: the masked cell-members of the 2071-2100 window make their cells climate-data-invalid there, and only there."""
    masked = pd.read_parquet(_phase(zzz, "climate_forcing") / "forcing_masked.parquet")
    wind = _robustness(zzz, "wind", "sensitivity").set_index("cell_id")
    expected = set(masked["cell_id"]) & set(wind.index)
    assert set(wind.index[wind["cell_class"] == "climate_data_invalid"]) == expected
    core = _robustness(zzz, "wind", "core")
    assert set(core["cell_class"]) == {"ranked"}
    assert (wind.loc[sorted(expected), "mr"].isna()).all()
    assert (wind.loc[sorted(set(wind.index) - expected), "cell_class"] == "ranked").all()


@pytest.mark.synthetic
def test_f7_lists_the_outputs_it_could_not_write_with_the_blocking_question(zzz):
    summary = json.loads(
        (zzz[0] / "outputs" / "ZZZ" / "artifacts" / "robustness_analysis.json").read_text(
            encoding="utf-8"
        )
    )
    for tech in ("solar", "wind"):
        entry = summary["technologies"][tech]
        roles = {
            "core",
            "sensitivity",
        }  # no altitude window: wind above 3000 m is not a candidate (OQ-058, COMMAND 46)
        assert entry["provisional"] is False and set(entry["windows"]) == roles
        assert all(s["reason"] and s["open_question"] for s in entry["skipped"])


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_f7_writes_h1_to_h5_without_verdict_and_t_r12_with_the_three_land_scenarios(zzz, tech):
    base = _phase(zzz, "robustness_analysis")
    hypothesis = pd.read_parquet(base / f"hypothesis_{tech}__core.parquet")
    assert set(hypothesis["hypothesis"]) == {"H1", "H2", "H3", "H4", "H5", "RQ4"}
    verdicts = hypothesis.set_index("statistic")["verdict"]
    assert (
        verdicts["mr_sr_kendall_tau_b"] == "met"
    )  # the test rule of RQ4 in this copy of the configuration (every hypothesis has its own rule)
    h1_rules = [
        "h1a_core_share",
        "h1b_vulnerable_share",
    ]  # H1 carries its pre-registered rule (OQ-050)
    assert verdicts[h1_rules].isin(["met", "not_met"]).all()
    assert (
        verdicts.drop(
            [
                "mr_sr_kendall_tau_b",
                "h2_overlap_index",
                "h3_beyond_reach_share",
                "h5a_resource_loss_ratio",
                "h5b_exposure_ratio",
                *h1_rules,
            ]
        )
        .isna()
        .all()
    )
    assert "mr_sr_kendall_tau_b" in set(hypothesis["statistic"])
    box = pd.read_parquet(base / f"prim_box_{tech}__core.parquet")
    primary = box[box["primary"]].iloc[0]
    assert primary["outcome_threshold"] == 0.20 and primary["n_futures"] > 0
    assert (
        primary["status"] == "box_found"
    )  # the GCM rule of this run makes the IPSL futures the cases of interest
    assert primary["n_cases"] == int(
        (
            pd.read_parquet(base / f"futures_{tech}__core.parquet").query("sample >= 1")["gcm"]
            == IPSL
        ).sum()
    )
    # the box isolates the IPSL futures; the descriptors that are constant within a member may stand in for the category, so it need not be alone
    assert IPSL in primary["gcm__in"].split("|") and primary["n_restricted"] <= 3
    assert primary["density"] == pytest.approx(1.0) and primary["coverage"] == pytest.approx(1.0)
    prim = pd.read_parquet(base / f"prim_boxes_{tech}__core.parquet")
    assert prim["step"].iloc[0] == 0 and prim["mass"].iloc[0] == 1.0 and prim["selected"].sum() == 1
    boot = pd.read_parquet(base / f"prim_bootstrap_{tech}__core.parquet")
    assert boot[boot["kind"] == "status"]["frequency"].sum() == pytest.approx(1.0)
    late = pd.read_parquet(base / f"prim_box_{tech}__sensitivity.parquet")
    assert len(late) == 0  # scenario discovery runs on the core window only
    below = pd.read_parquet(base / f"potential_below_tau_{tech}__core.parquet")
    assert set(below["land_scenario"]) == {"central", "restrictive", "permissive"}
    futures = pd.read_parquet(base / f"futures_{tech}__core.parquet")
    assert set(futures["sample"]) >= {0, 1}
    exposure = pd.read_parquet(base / f"hazard_exposure_{tech}__core.parquet")
    assert set(exposure["hazard"]) == {
        "tx35_days",
        "tx40_days",
        "rx5day_mm",
        "wet_p95_exceed_freq",
        "gust_mean_annual_max_ms",
        "any_channel",
    }  # every indicator has a (test) threshold in this run, and the union of the channels is H5b's
    assert (exposure["potential_gw"] >= 0).all() and set(exposure["group"]) >= {"f7_set"}


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_f7_writes_the_h1_table_with_c_k_v_k_the_reference_the_verdict_and_the_sensitivities(
    zzz, tech
):
    base = _phase(zzz, "robustness_analysis")
    summary = pd.read_parquet(base / f"h1_summary_{tech}__core.parquet")
    primary = summary[summary["primary"]].iloc[0]
    assert primary["verdict"] in {"supported", "partially_supported", "not_supported"}
    assert 0.0 <= primary["c_k"] <= 1.0 and 0.0 <= primary["v_k"] <= 1.0
    assert primary["reference"] == pytest.approx((primary["k"] / primary["n_cells"]) ** 2)
    assert (primary["alpha"], primary["beta"], primary["m"]) == (0.60, 0.20, primary["k"])
    assert bool(primary["h1a_holds"]) == (primary["c_k"] >= 0.60)
    assert bool(primary["h1b_holds"]) == (primary["v_k"] >= 0.20)
    variants = set(summary["variant"])
    assert {"top_k_percent_5", "top_k_percent_10", "top_k_percent_20"} <= variants
    assert {"tolerance_0.5k", "tolerance_1k", "tolerance_2k"} <= variants
    scores = pd.read_parquet(base / f"ssp_scores_{tech}__core.parquet")
    assert set(scores["ssp"]) == {"SSP1-2.6", "SSP3-7.0", "SSP5-8.5"}
    sites = pd.read_parquet(base / f"h1_sites_{tech}__core.parquet")
    assert len(sites) == primary["k"] and sites["vulnerable"].sum() == primary["n_vulnerable"]
    # the 2071-2100 window is the sensitivity run of the same table
    assert (base / f"h1_summary_{tech}__sensitivity.parquet").is_file()


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_f7_writes_the_h2_table_with_o_the_reference_the_verdict_and_the_sensitivities(zzz, tech):
    base = _phase(zzz, "robustness_analysis")
    summary = pd.read_parquet(base / f"h2_summary_{tech}__core.parquet")
    primary = summary[summary["primary"]].iloc[0]
    assert primary["verdict"] in {"supported", "not_supported", "not_testable"}
    assert 0.0 <= primary["overlap"] <= 1.0 and 0.0 < primary["overlap_ref"] <= 1.0
    assert primary["overlap_ref"] == pytest.approx(primary["target_mw"] / primary["q_max_mw"])
    assert (primary["gamma"], primary["partition"]) == (0.30, "admin1")
    assert primary["robustness_penalty"] >= -1e-12
    assert bool(primary["testable"]) == (primary["overlap_ref"] < 0.30)
    variants = set(summary["variant"])
    assert {"gamma_0.10", "gamma_0.30", "gamma_0.70"} <= variants
    assert {
        "top_k_percent_5",
        "top_k_percent_10",
        "top_k_percent_20",
        "median_statistic",
    } <= variants
    regions = pd.read_parquet(base / f"h2_regions_{tech}__core.parquet")
    assert len(regions) == primary["n_regions"] > 0
    assert regions["selected_admin_mw"].sum() == pytest.approx(primary["target_mw"])
    assert (base / f"h2_summary_{tech}__sensitivity.parquet").is_file()  # the 2071-2100 window
    hypothesis = pd.read_parquet(base / f"hypothesis_{tech}__core.parquet").set_index("statistic")
    verdict = hypothesis.loc["h2_overlap_index", "verdict"]
    expected = {"supported": "met", "not_supported": "not_met", "not_testable": None}[
        primary["verdict"]
    ]
    assert (verdict == expected) or (expected is None and pd.isna(verdict))


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_f7_writes_the_h3_table_with_d_the_reference_the_verdict_and_the_sensitivities(zzz, tech):
    base = _phase(zzz, "robustness_analysis")
    summary = pd.read_parquet(base / f"h3_summary_{tech}__core.parquet")
    primary = summary[summary["primary"]].iloc[0]
    assert primary["verdict"] in {"supported", "not_supported", "not_testable"}
    assert 0.0 <= primary["d"] <= 1.0
    assert primary["d_ref"] == pytest.approx(1 - 2 * primary["k"] / primary["n_ranked"])
    assert (primary["delta"], primary["m"]) == (0.20, primary["k"])
    assert primary["outside_capacity_mw"] == pytest.approx(
        primary["d"] * primary["robust_capacity_mw"]
    )
    assert bool(primary["testable"]) == (primary["d_ref"] >= 0.20)
    assert primary["price_of_robustness"] is not None and primary["benefit_of_robustness"] >= -1e-9
    variants = set(summary["variant"])
    assert {"top_k_percent_5", "top_k_percent_10", "top_k_percent_20"} <= variants
    assert {"tolerance_0.5k", "tolerance_2k"} <= variants
    sites = pd.read_parquet(base / f"h3_sites_{tech}__core.parquet")
    assert (
        sites["in_robust"].sum() == primary["k"]
        and sites["counts_in_d"].sum() == primary["n_outside"]
    )
    assert (base / f"h3_summary_{tech}__sensitivity.parquet").is_file()  # the 2071-2100 window
    hypothesis = pd.read_parquet(base / f"hypothesis_{tech}__core.parquet").set_index("statistic")
    verdict = hypothesis.loc["h3_beyond_reach_share", "verdict"]
    expected = {"supported": "met", "not_supported": "not_met", "not_testable": None}[
        primary["verdict"]
    ]
    assert (verdict == expected) or (expected is None and pd.isna(verdict))


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_f7_writes_h5_with_the_target_the_exposure_the_verdict_and_the_sensitivities(zzz, tech):
    base = _phase(zzz, "robustness_analysis")
    summary = pd.read_parquet(base / f"h5_summary_{tech}__core.parquet")
    primary = summary[summary["primary"]].iloc[0]
    assert primary["status"] == "tested" and primary["lam"] == 0.20
    assert (primary["target_value"], primary["target_unit"], primary["target_horizon"]) == (
        0.0001,
        "GW",
        2040,
    )
    assert primary["h0_twh"] == pytest.approx(primary["e0_twh"] - primary["g_twh"])
    members = pd.read_parquet(base / f"h5_members_{tech}__core.parquet").set_index("member")
    assert primary["delta_e_twh"] == pytest.approx(
        max(0.0, (members["energy_twh"] - primary["e0_twh"]).min() * -1.0)
    )
    assert primary["r_loss"] == pytest.approx(primary["delta_e_twh"] / primary["h0_twh"])
    assert primary["exposure_available"]
    hazard_members = members[members["carries_hazard_channel"]]
    assert len(hazard_members) == 9 and members["exposed_twh"].notna().sum() == 9
    assert primary["e_exp_twh"] == pytest.approx(hazard_members["exposed_twh"].max())
    assert primary["r_exp"] == pytest.approx(primary["e_exp_twh"] / primary["h0_twh"])
    assert (
        primary["verdict"]
        == {
            (True, True): "supported",
            (True, False): "partially_supported_resource",
            (False, True): "partially_supported_exposure",
            (False, False): "not_supported",
        }[(bool(primary["h5a_holds"]), bool(primary["h5b_holds"]))]
    )
    hypothesis = pd.read_parquet(base / f"hypothesis_{tech}__core.parquet").set_index("statistic")
    for name, holds in (
        ("h5a_resource_loss_ratio", primary["h5a_holds"]),
        ("h5b_exposure_ratio", primary["h5b_holds"]),
    ):
        assert hypothesis.loc[name, "verdict"] == ("met" if holds else "not_met")
    assert hypothesis.loc["h5a_resource_loss_ratio", "value"] == pytest.approx(primary["r_loss"])
    variants = set(summary["variant"])
    assert {
        "lambda_0.10",
        "dynamic_domain",
        "land_restrictive",
        "land_permissive",
        "channel_tx35_days",
        "channel_gust_mean_annual_max_ms",
    } <= variants
    late = (
        pd.read_parquet(base / f"h5_summary_{tech}__sensitivity.parquet").query("primary").iloc[0]
    )
    assert (
        late["window"] == "2071-2100" and not late["exposure_available"]
    )  # no hazard data there (L-021)
    assert late["verdict"] is None and pd.notna(late["r_loss"])
    fixed = pd.read_parquet(base / f"potential_below_tau_{tech}__core.parquet").query(
        "series == 'fixed_domain' and land_scenario == 'central' and basis == 'nominal'"
    )
    assert fixed.set_index("member").loc["m0", "potential_twh"] == pytest.approx(primary["e0_twh"])


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_f7_writes_the_h4_country_table_with_the_displacements_the_ratio_and_the_profile(zzz, tech):
    base = _phase(zzz, "robustness_analysis")
    summary = pd.read_parquet(base / f"h4_country_{tech}__core.parquet")
    primary = summary[summary["primary"]].iloc[0]
    assert primary["profile"] in {
        "climate_dominated",
        "techno_economic_dominated",
        "mixed",
        "no_displacement",
    }
    assert 0.0 <= primary["d_clim"] <= 1.0 and 0.0 <= primary["d_tec"] <= 1.0
    assert primary["d_sum"] == pytest.approx(primary["d_clim"] + primary["d_tec"])
    assert (primary["lower"], primary["upper"], primary["m"]) == (0.40, 0.60, primary["k"])
    if primary["d_sum"] > 0:
        assert primary["rho"] == pytest.approx(primary["d_clim"] / primary["d_sum"])
    else:
        assert pd.isna(primary["rho"]) and primary["profile"] == "no_displacement"
    variants = set(summary["variant"])
    assert {"top_k_percent_5", "tolerance_2k", "boundaries_0.30_0.70"} <= variants
    assert {v for v in variants if v.startswith("climate_ssp_")} == {
        "climate_ssp_SSP1-2.6",
        "climate_ssp_SSP3-7.0",
        "climate_ssp_SSP5-8.5",
    }
    assert (base / f"h4_country_{tech}__sensitivity.parquet").is_file()  # the 2071-2100 window
    joint = pd.read_parquet(base / f"h3_summary_{tech}__core.parquet").query("primary")["d"].iloc[0]
    assert primary["d_joint"] == pytest.approx(joint)


@pytest.mark.synthetic
def test_cross_country_h4_gives_not_testable_for_one_country_and_a_verdict_for_three(
    zzz, tmp_path, monkeypatch
):
    """ZZZ alone cannot test H4; ZZZ beside two copies whose profiles are set apart (a Climate- and a Techno-Economic-Dominated one) does."""
    import hashlib
    import shutil

    from geofrea.core.artifact_reader import ArtifactReader
    from geofrea.core.tables import write_table
    from geofrea.robustness_analysis.cross_country import build_h4_verdict, manifest_file
    from geofrea.robustness_analysis.table_schemas import (
        ROBUSTNESS_TABLE_SCHEMA_VERSION,
        H4CountryRow,
    )

    data = tmp_path / "data"
    shutil.copytree(zzz[0] / "outputs" / "ZZZ", data / "outputs" / "ZZZ")
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(data))
    alone = build_h4_verdict(["ZZZ"], ("solar", "wind"))
    assert {v.verdict for v in alone.verdicts} == {"not_testable"}
    assert {(v.n_countries, v.n_available) for v in alone.verdicts} == {(1, 1)}

    for iso, (d_clim, d_tec) in (("ZZB", (0.42, 0.08)), ("ZZC", (0.12, 0.38))):
        manifest = {"artifacts": {}}
        for tech in ("solar", "wind"):
            for role in ("core", "sensitivity"):
                real = _phase(zzz, "robustness_analysis") / f"h4_country_{tech}__{role}.parquet"
                frame = pd.read_parquet(real)
                at = frame.index[frame["primary"]][0]
                frame.loc[at, ["d_clim", "d_tec", "d_sum", "rho"]] = [
                    d_clim,
                    d_tec,
                    d_clim + d_tec,
                    d_clim / (d_clim + d_tec),
                ]
                frame.loc[at, "profile"] = (
                    "climate_dominated" if d_clim > d_tec else "techno_economic_dominated"
                )
                rel = f"outputs/{iso}/h4_country_{tech}__{role}.parquet"
                path = write_table(
                    frame,
                    data / rel,
                    schema_version=ROBUSTNESS_TABLE_SCHEMA_VERSION,
                    row_model=H4CountryRow,
                )
                manifest["artifacts"][f"h4_country_{tech}__{role}"] = {
                    "path": {"root": "data", "rel": rel},
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
        (data / "outputs" / iso / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

    three = build_h4_verdict(["ZZZ", "ZZB", "ZZC"], ("solar", "wind"))
    assert {(v.technology, v.role): v.verdict for v in three.verdicts} == dict.fromkeys(
        [(t, r) for t in ("solar", "wind") for r in ("core", "sensitivity")], "supported"
    )
    reader = ArtifactReader("cross_country", manifest_file=manifest_file())
    table = reader.table("h4_verdict_wind__core", {ROBUSTNESS_TABLE_SCHEMA_VERSION})
    real = pd.read_parquet(_phase(zzz, "robustness_analysis") / "h4_country_wind__core.parquet")
    shown = table[table["kind"] == "country"].set_index("country")
    assert shown.loc["ZZZ", "profile"] == real[real["primary"]]["profile"].iloc[0]
    assert shown.loc["ZZB", "profile"] == "climate_dominated"
    assert shown.loc["ZZC", "profile"] == "techno_economic_dominated"

    # F8 reads the same tables: T-R6 has the H4 row with the verdict and T-R7 one bar pair per country
    import main
    from geofrea.results_synthesis.runner import build_thesis

    out = tmp_path / "thesis"
    build_thesis(
        "ZZZ",
        ("solar", "wind"),
        technologies_yaml=main.TECHNOLOGIES_YAML,
        experiments_yaml=main.EXPERIMENTS_YAML,
        parameters_json=main.PARAMETERS_JSON,
        methodology_md=main.METHODOLOGY_MD,
        out_dir=out,
        phase_graph=main.thesis_phase_graph(("solar", "wind")),
    )
    verdicts = pd.read_csv(out / "T-R6_hypothesis_verdicts_ZZZ_wind.csv")
    h4 = verdicts[(verdicts["hypothesis"] == "H4") & (verdicts["role"] == "core")].iloc[0]
    assert h4["verdict"] == "supported" and h4["value"] == 1.0 and h4["value_2"] == 3.0
    cross = pd.read_csv(out / "T-R6_h4_verdict_wind.csv")
    assert set(cross.loc[cross["kind"] == "country", "country"]) == {"ZZZ", "ZZB", "ZZC"}
    axis = pd.read_csv(out / "T-R7_axis_displacement_wind.csv")
    core = axis[(axis["scale"] == "0p05deg") & (axis["role"] == "core")]
    assert list(core["country"]) == ["ZZZ", "ZZB", "ZZC"]
    assert core.set_index("country").loc["ZZB", "rho"] == pytest.approx(0.84)
    assert (out / "T-R7_axis_displacement_wind.png").stat().st_size > 0


@pytest.mark.synthetic
def test_f7_runs_at_the_coarse_scale_with_the_same_code_and_the_masked_wind_removes_only_wind_cells(
    zzz_fine,
):
    """V-07, M-F4-07: the 0.1 degree cells are fewer and wider, so the masked block of 2071-2100 reaches the coarse wind cells that it reaches; solar, which does
    not read the wind ratio, keeps all of them in both windows."""
    core = pd.read_parquet(
        _fine(zzz_fine, "robustness_analysis") / "robustness_solar__core.parquet"
    )
    sensitivity = pd.read_parquet(
        _fine(zzz_fine, "robustness_analysis") / "robustness_solar__sensitivity.parquet"
    )
    assert set(core["cell_class"]) == {"ranked"} and len(core) == len(sensitivity) > 0
    assert set(sensitivity["cell_class"]) == {"ranked"}  # a wind mask never removes a solar cell
    wind = pd.read_parquet(_fine(zzz_fine, "robustness_analysis") / "robustness_wind__core.parquet")
    assert sorted(wind["robust_rank"]) == list(range(1, len(wind) + 1))
    assert (wind["cell_id"] // 3600 == wind["lat_c"].rsub(90.0).floordiv(0.1)).all()
    wind_sensitivity = pd.read_parquet(
        _fine(zzz_fine, "robustness_analysis") / "robustness_wind__sensitivity.parquet"
    )
    masked = pd.read_parquet(_fine(zzz_fine, "climate_forcing") / "forcing_masked.parquet")
    invalid = wind_sensitivity["cell_class"] == "climate_data_invalid"
    assert invalid.any() and set(wind_sensitivity["cell_id"][invalid]) == set(
        masked["cell_id"]
    ) & set(wind_sensitivity["cell_id"])
    assert wind_sensitivity.loc[invalid, ["mr", "robust_rank"]].isna().all().all()
    assert (wind_sensitivity.loc[~invalid, "cell_class"] == "ranked").all()


@pytest.mark.synthetic
def test_no_path_the_pipeline_read_is_outside_the_data_directory(zzz):
    """COMMAND 37: every layer of the registry and every input hashed by grid_alignment is inside GEOFREA_DATA_DIR; the manifest uses the `data` root only."""
    data = zzz[0].resolve()
    registry = json.loads(
        (zzz[0] / "outputs" / "ZZZ" / "artifacts" / "layer_registry.json").read_text(
            encoding="utf-8"
        )
    )
    outside = []
    for layer in registry["layers"]:
        for path in ([layer["path"]] if layer.get("path") else []) + list(layer.get("paths") or []):
            if ":" in path and not path.startswith(("data:", "repo:")):  # an absolute path
                candidate = Path(path).resolve()
            elif path.startswith("data:"):
                candidate = data / path.split(":", 1)[1]
            else:
                continue
            if data not in (candidate, *candidate.parents):
                outside.append(path)
    assert outside == []
    hashed = json.loads(
        (zzz[0] / "interim" / "ZZZ" / "grid_alignment" / "input_sha256.json").read_text(
            encoding="utf-8"
        )
    )
    assert all(data in Path(k.split("|")[0]).resolve().parents for k in hashed)
    manifest = json.loads(
        (zzz[0] / "outputs" / "ZZZ" / "manifest.json").read_text(encoding="utf-8")
    )
    assert {a["path"]["root"] for a in manifest["artifacts"].values()} == {"data"}


@pytest.mark.synthetic
def test_the_run_used_no_network(zzz):
    """The fixture refused every socket connection while the phases ran; the run succeeded, so none was attempted."""
    assert socket.socket.connect is _no_network


# -- F7b: existing units against the exclusion set, the LCOE deciles and the published estimates ----------------


def _validation(zzz, name, fine=False):
    base = _fine(zzz, "external_validation") if fine else _phase(zzz, "external_validation")
    return pd.read_parquet(base / f"{name}.parquet")


# hand values of `generate_zzz_fixture.GEM_UNITS`: capacity in valid pixels and the excluded share each constraint gives
HAND_EXCLUSION = {
    "wind": {  # units of 10 (E1), 20 (free), 30 (free) and 40 MW (E5 and E6), 100 MW in the grid, 5 MW outside it
        "E1": 0.1,
        "E2": 0.0,
        "E3": 0.0,
        "E4": 0.0,
        "E5": 0.4,
        "E6": 0.4,
        "combined": 0.5,
    },
    "solar": {  # units of 12 (free), 8 (E5), 6 (E1 and E5) and 4 MW (E6), 30 MW in the grid
        "E1": 6 / 30,
        "E2": 0.0,
        "E3": 0.0,
        "E4": 0.0,
        "E5": 14 / 30,
        "E6": 4 / 30,
        "combined": 18 / 30,
    },
}


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_f7b_excluded_shares_under_the_units_equal_the_hand_computation(zzz, tech):
    table = _validation(zzz, "exclusion_shares")
    rows = table[(table["technology"] == tech) & (table["row_set"] == "operating")].set_index(
        "constraint"
    )
    assert set(rows.index) == {"E1", "E2", "E3", "E4", "E5", "E6", "combined"}
    for constraint, expected in HAND_EXCLUSION[tech].items():
        assert rows.loc[constraint, "mean_excluded_share"] == pytest.approx(expected, abs=1e-6)
    combined = rows.loc["combined"]
    assert combined["share_above_0"] == pytest.approx(HAND_EXCLUSION[tech]["combined"], abs=1e-6)
    assert combined["share_at_least_half"] == pytest.approx(combined["share_above_0"])
    assert combined["share_equal_1"] == pytest.approx(combined["share_above_0"])
    assert rows.loc["E1", "share_equal_1"] == pytest.approx(HAND_EXCLUSION[tech]["E1"], abs=1e-6)


@pytest.mark.synthetic
def test_f7b_counts_the_unit_outside_the_grid_and_leaves_out_units_that_are_not_operating(zzz):
    table = _validation(zzz, "exclusion_shares")
    wind = table[(table["technology"] == "wind") & (table["constraint"] == "E1")].iloc[0]
    assert wind["n_units"] == 5 and wind["capacity_mw"] == pytest.approx(105.0)
    assert wind["n_outside_grid"] == 1 and wind["capacity_outside_grid_mw"] == pytest.approx(5.0)
    assert wind["n_evaluated"] == 4 and wind["capacity_evaluated_mw"] == pytest.approx(100.0)
    solar = table[(table["technology"] == "solar") & (table["constraint"] == "E1")].iloc[0]
    assert solar["n_units"] == 4 and solar["capacity_mw"] == pytest.approx(
        30.0
    )  # 'announced' left out


def _hand_deciles(candidates: pd.DataFrame, lcoe: pd.DataFrame) -> dict[int, int]:
    """Deciles of eligible area ordered by LCOE, computed with plain loops (the cell goes to the decile of its area midpoint)."""
    by_cell = dict(zip(lcoe["cell_id"], lcoe["lcoe_nominal"], strict=True))
    ordered = sorted(
        zip(candidates["cell_id"], candidates["eligible_area_km2"], strict=True),
        key=lambda item: (by_cell[item[0]], item[0]),
    )
    total = sum(area for _, area in ordered)
    done, out = 0.0, {}
    for cell, area in ordered:
        out[int(cell)] = min(int((done + area / 2.0) / total * 10), 9) + 1
        done += area
    return out


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_f7b_enrichment_equals_a_hand_recomputation_from_the_candidates_and_the_nominal_lcoe(
    zzz, tech
):
    candidates = pd.read_parquet(
        _phase(zzz, "land_eligibility") / f"candidates_{tech}__central.parquet"
    )
    lcoe = pd.read_parquet(_phase(zzz, "lcoe_modeling") / f"lcoe_summary_{tech}.parquet")
    lcoe = lcoe[lcoe["member"].astype(str) == "m0"]
    decile = _hand_deciles(candidates, lcoe)
    units = _validation(zzz, "validation_units")
    units = units[(units["technology"] == tech) & units["in_grid"]]
    assert {
        int(c): int(d)
        for c, d in zip(units["cell_id"], units["decile"], strict=True)
        if pd.notna(d)
    } == {int(c): decile[int(c)] for c in units["cell_id"] if int(c) in decile}
    in_candidates = units[units["cell_id"].isin(decile)]
    table = _validation(zzz, "enrichment")
    rows = table[(table["technology"] == tech) & (table["row_set"] == "operating")]
    total_area = candidates["eligible_area_km2"].sum()
    for d in (1, 2, 3):
        low = rows[(rows["kind"] == "lowest") & (rows["decile"] == d)].iloc[0]
        cells = [c for c, k in decile.items() if k <= d]
        area_share = (
            candidates[candidates["cell_id"].isin(cells)]["eligible_area_km2"].sum() / total_area
        )
        capacity_share = (
            in_candidates[in_candidates["cell_id"].map(decile) <= d]["capacity_mw"].sum()
            / in_candidates["capacity_mw"].sum()
        )
        assert low["eligible_area_share"] == pytest.approx(area_share)
        assert low["capacity_share"] == pytest.approx(capacity_share)
        assert low["enrichment_ratio"] == pytest.approx(capacity_share / area_share)
    non_candidate = (
        units[~units["cell_id"].isin(decile)]["capacity_mw"].sum() / units["capacity_mw"].sum()
    )
    assert rows["capacity_share_non_candidate"].iloc[0] == pytest.approx(non_candidate)
    assert rows[rows["kind"] == "decile"]["eligible_area_share"].sum() == pytest.approx(1.0)


@pytest.mark.synthetic
def test_f7b_published_comparison_is_empty_and_flagged_while_there_are_no_entries(zzz):
    path = _phase(zzz, "external_validation") / "published_comparison.parquet"
    assert len(pd.read_parquet(path)) == 0
    flag = json.loads(pq.read_schema(path).metadata[b"geofrea_validation_skipped"])
    assert flag["open_question"] == "OQ-057"
    provenance = json.loads(pq.read_schema(path).metadata[b"geofrea_validation_provenance"])
    assert (
        provenance["synthetic_inventory"] is True
        and "plausibility evidence" in provenance["interpretation"]
    )


@pytest.mark.synthetic
def test_f7b_runs_at_the_coarse_scale_and_the_pixel_level_exclusions_do_not_change(zzz, zzz_fine):
    fine = _validation(zzz_fine, "exclusion_shares", fine=True)
    coarse = _validation(zzz, "exclusion_shares")
    pd.testing.assert_frame_equal(
        fine, coarse
    )  # the engine is evaluated at the pixels, whatever the cell size
    assert len(_validation(zzz_fine, "enrichment", fine=True)) == len(
        _validation(zzz, "enrichment")
    )


def _tables_of(zzz_fine, phases):
    """Every parquet table the phases wrote at the 0.1 degree scale, by relative path."""
    out = {}
    for phase in phases:
        for path in sorted(_fine(zzz_fine, phase).glob("*.parquet")):
            out[f"{phase}/{path.name}"] = pd.read_parquet(path)
    return out


@pytest.mark.synthetic
def test_v06_f5_to_f7_do_not_change_when_the_plant_inventory_is_absent(zzz_fine, monkeypatch):
    """D-F7b-005: the tables of F5, F6 and F7 are identical with and without the unit file (the inventory feeds F7b only)."""
    import shutil

    import main

    # the scale check ran last, so its manifest is the one that matches the shared layer registry
    monkeypatch.setenv(
        "GEOFREA_DATA_DIR", str(zzz_fine[0])
    )  # the autouse fixture re-points it per test
    phases = ("technical_potential", "lcoe_modeling", "robustness_analysis")
    before = _tables_of(zzz_fine, phases)
    assert before
    inventory = zzz_fine[0] / "raw" / "gem"
    parked = zzz_fine[0] / "raw" / "gem_parked"
    shutil.move(str(inventory), str(parked))
    try:
        settings = load_settings(main.SETTINGS_YAML)
        ok, _orchestrator, results = main.run_geofrea(
            "ZZZ",
            ["robustness_analysis"],
            list(phases),
            settings.geospatial.resolutions,
            settings.geospatial.distance_cap_km,
            load_audit_config(main.AUDIT_YAML),
            "zzz-v06-perturbation",
            False,
            None,
            tuple(settings.run.technologies),
            False,
            settings.figures,
            settings.memory.max_batch_gb,
            "0p1deg",
        )
        assert ok, {k: v.status for k, v in results.items()}
        assert all(results[name].status == "success" for name in phases)
        after = _tables_of(zzz_fine, phases)
    finally:
        shutil.move(str(parked), str(inventory))
    assert before.keys() == after.keys()
    for key, frame in before.items():
        pd.testing.assert_frame_equal(frame, after[key], obj=key)


# -- the LCOE and robustness maps ---------------------------------------------------------------------------


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_the_lcoe_map_of_the_reference_member_equals_the_f6_table_cell_by_cell(zzz, tech):
    import rasterio

    summary = pd.read_parquet(_phase(zzz, "lcoe_modeling") / f"lcoe_summary_{tech}.parquet")
    reference = summary[summary["member"].astype(str) == "m0"].set_index("cell_id")["lcoe_nominal"]
    with rasterio.open(_phase(zzz, "lcoe_modeling") / f"lcoe_nominal_{tech}.tif") as src:
        raster, transform = src.read(1), src.transform
    lat, lon = (
        pd.read_parquet(_phase(zzz, "land_eligibility") / f"candidates_{tech}__central.parquet")
        .set_index("cell_id")
        .loc[reference.index, ["lat_c", "lon_c"]]
        .to_numpy()
        .T
    )
    rows, cols = rasterio.transform.rowcol(transform, lon, lat)
    np.testing.assert_allclose(raster[rows, cols], reference.to_numpy(), rtol=1e-6)
    figures = {p.name for p in (_phase(zzz, "lcoe_modeling", "figures")).glob("*.png")}
    assert f"lcoe_nominal_{tech}__ref__na__na.png" in figures
    assert f"supply_curve_{tech}__ref__na__na.png" in figures
    assert {f"lcoe_nominal_{tech}__2041-2070__ssp126__na.png"} <= figures


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_the_robustness_maps_are_written_for_both_windows_and_the_max_regret_matches_the_table(
    zzz, tech
):
    import rasterio

    for role in ("core", "sensitivity"):
        table = _robustness(zzz, tech, role)
        with rasterio.open(
            _phase(zzz, "robustness_analysis") / f"max_regret_{tech}__{role}.tif"
        ) as src:
            raster, transform = src.read(1), src.transform
            nodata = src.nodata
        rows, cols = rasterio.transform.rowcol(
            transform, table["lon_c"].to_numpy(), table["lat_c"].to_numpy()
        )
        got = raster[rows, cols].astype("float64")
        want = table["mr"].to_numpy(dtype="float64")
        finite = np.isfinite(want)
        np.testing.assert_allclose(got[finite], want[finite], rtol=1e-5)
        assert (got[~finite] == nodata).all()
    window = "2041-2070"
    figures = {p.name for p in _phase(zzz, "robustness_analysis", "figures").glob("*.png")}
    assert f"cell_class_{tech}__{window}__na__na.png" in figures


# -- deterministic artifacts (COMMAND 24, A-02) ----------------------------------------------------------


@pytest.mark.synthetic
def test_every_registered_json_artifact_holds_no_timestamp_run_time_or_absolute_path(zzz):
    from geofrea.core.artifact_json import find_nondeterministic

    files = sorted((zzz[0] / "outputs" / "ZZZ" / "artifacts").glob("*.json"))
    assert files
    offenders = {}
    for path in files:
        found = find_nondeterministic(json.loads(path.read_text(encoding="utf-8")))
        if found:
            offenders[path.name] = found[:3]
    assert not offenders, offenders


@pytest.mark.synthetic
def test_parquet_metadata_holds_no_timestamp_or_absolute_path(zzz):
    import re

    pattern = re.compile(
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}|[A-Za-z]:[\/]|(?<![\w.])/(?:Users|home|mnt|tmp|var)/"
    )
    offenders = {}
    for path in sorted((zzz[0] / "outputs" / "ZZZ").rglob("*.parquet")):
        meta = pq.read_schema(path).metadata or {}
        for key, value in meta.items():
            if key == b"pandas":
                continue
            text = key.decode("utf-8", "replace") + "=" + value.decode("utf-8", "replace")
            if pattern.search(text):
                offenders.setdefault(path.name, []).append(text[:120])
    assert not offenders, offenders


@pytest.fixture
def advancing_clock(monkeypatch):
    """A clock injected into the orchestrator and the audit: every reading is one hour after the previous, so no two runs share a time."""
    from datetime import UTC, datetime, timedelta

    import geofrea.core.orchestrator as orchestrator_module
    import geofrea.data_quality_audit.audit as audit_module

    ticks = iter(range(10_000))
    base = datetime(2030, 1, 1, tzinfo=UTC)

    def now(tz=None):
        return base + timedelta(hours=next(ticks))

    class FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now(tz)

    monkeypatch.setattr(orchestrator_module, "_now_iso", lambda: now().isoformat())
    monkeypatch.setattr(audit_module, "datetime", FakeDatetime)


@pytest.mark.synthetic
def test_the_audit_report_has_the_same_hash_when_f1b_runs_twice(zzz, monkeypatch, advancing_clock):
    import main

    monkeypatch.setenv(
        "GEOFREA_DATA_DIR", str(zzz[0])
    )  # the autouse conftest fixture re-points it per test

    def audit_hash():
        settings = load_settings(main.SETTINGS_YAML)
        ok, orchestrator, _ = main.run_geofrea(
            "ZZZ",
            ["data_quality_audit"],
            ["data_quality_audit"],
            settings.geospatial.resolutions,
            settings.geospatial.distance_cap_km,
            load_audit_config(main.AUDIT_YAML),
            "zzz-f1b-twice",
            False,
            None,
            tuple(settings.run.technologies),
            False,
            settings.figures,
            settings.memory.max_batch_gb,
        )
        assert ok
        entry = orchestrator.manifest.artifacts["audit_report"]
        return entry.sha256, orchestrator.manifest.phases["data_quality_audit"].finished_at

    first_hash, first_finished = audit_hash()
    second_hash, second_finished = audit_hash()
    assert second_finished != first_finished  # the phase really ran again
    assert second_hash == first_hash


# -- F8: the thesis outputs, read from the registered artifacts (M-F8-01, M-F8-02) ----------------------------------

THESIS_TABLES = {
    "T-R3": ["cf_agreement_ZZZ_{t}"],
    "T-M2": ["methods_ZZZ_{t}"],
    "T-M3": ["uncertain_parameters_ZZZ_{t}"],
    "T-R2": ["potential_ZZZ_{t}", "land_interval_ZZZ_{t}"],
    "T-R6": [
        "hypothesis_statistics_ZZZ_{t}",
        "hypothesis_verdicts_ZZZ_{t}",
        "h1_summary_ZZZ_{t}",
        "h2_summary_ZZZ_{t}",
        "h3_summary_ZZZ_{t}",
        "h4_country_ZZZ_{t}",
        "h5_summary_ZZZ_{t}",
    ],
    "T-R10": ["hazard_exposure_ZZZ_{t}"],
    "T-R12": ["potential_below_tau_ZZZ_{t}"],
    "T-O1": ["prim_box_ZZZ_{t}"],
}
THESIS_FIGURES = {
    "T-R1": "potential_density_ZZZ_{t}",
    "T-R3": "cf_change_ZZZ_{t}",
    "T-R4": "max_regret_ZZZ_{t}",
    "T-R5": "rank_stability_ZZZ_{t}",
    "T-R11": "lcoe_map_ZZZ_{t}",
    "T-O1": "prim_box_ZZZ_{t}",
    "T-O2": "mr_sr_agreement_ZZZ_{t}",
    "T-O3": "supply_curves_ZZZ_{t}",
}
# the outputs that are about the countries together carry no ISO3 (names.stem)
THESIS_CROSS_TABLES = {
    "T-R6": ["h4_verdict_{t}"],
    "T-R7": ["axis_displacement_{t}"],
    "T-R8": [
        "country_profiles",
        "hypothesis_summary",
    ],  # about the countries and technologies together
}
THESIS_CROSS_FIGURES = {"T-R7": "axis_displacement_{t}"}


def _thesis(zzz):
    return zzz[0] / "outputs" / "thesis"


def _graph_of_the_orchestrator(technologies):
    """The phase graph the orchestrator derives from the phase specifications (T-M1 draws it)."""
    import main

    return main.thesis_phase_graph(tuple(technologies))


def _build_thesis(out_dir, technologies=("solar", "wind")):
    import main
    from geofrea.results_synthesis.runner import build_thesis

    return build_thesis(
        "ZZZ",
        technologies,
        technologies_yaml=main.TECHNOLOGIES_YAML,
        experiments_yaml=main.EXPERIMENTS_YAML,
        parameters_json=main.PARAMETERS_JSON,
        methodology_md=main.METHODOLOGY_MD,
        out_dir=out_dir,
        phase_graph=_graph_of_the_orchestrator(technologies),
    )


@pytest.mark.synthetic
def test_f8_writes_every_implemented_output_with_its_thesis_name_and_a_provenance_file(zzz):
    _, results = zzz
    assert results["results_synthesis"].status == "success"
    thesis = _thesis(zzz)
    for t_id, whats in THESIS_TABLES.items():
        for what in whats:
            for tech in ("solar", "wind"):
                stem = f"T-{t_id[2:]}_{what.format(t=tech)}"
                for suffix in (".csv", ".tex", ".provenance.json"):
                    assert (thesis / f"{stem}{suffix}").stat().st_size > 0, stem + suffix
    for t_id, what in THESIS_FIGURES.items():
        for tech in ("solar", "wind"):
            stem = f"T-{t_id[2:]}_{what.format(t=tech)}"
            for suffix in (".png", ".pdf", ".provenance.json"):
                assert (thesis / f"{stem}{suffix}").stat().st_size > 0, stem + suffix
    for t_id, whats in THESIS_CROSS_TABLES.items():
        for what in whats:
            for tech in ("solar", "wind"):
                stem = f"T-{t_id[2:]}_{what.format(t=tech)}"
                for suffix in (".csv", ".tex", ".provenance.json"):
                    assert (thesis / f"{stem}{suffix}").stat().st_size > 0, stem + suffix
    for t_id, what in THESIS_CROSS_FIGURES.items():
        for tech in ("solar", "wind"):
            stem = f"T-{t_id[2:]}_{what.format(t=tech)}"
            for suffix in (".png", ".pdf", ".provenance.json"):
                assert (thesis / f"{stem}{suffix}").stat().st_size > 0, stem + suffix
    assert (thesis / "T-M3_members_ZZZ.csv").is_file()
    for suffix in (".png", ".pdf", ".provenance.json"):
        assert (thesis / f"T-M1_framework_dag{suffix}").stat().st_size > 0
    for suffix in (".json", ".provenance.json"):
        assert (thesis / f"T-R8_hypothesis_profiles_ZZZ{suffix}").stat().st_size > 0
    for suffix in (".md", ".tex", ".provenance.json"):
        assert (thesis / f"T-R8_country_summary_ZZZ{suffix}").stat().st_size > 0
    for what in ("exclusion_shares", "enrichment", "published_comparison"):
        assert (thesis / f"T-R9_{what}_ZZZ.csv").is_file()
        assert (thesis / f"T-R9_{what}_ZZZ.tex").is_file()
    assert (thesis / "T-R9_units_ZZZ.csv").is_file()
    manifest = json.loads((thesis / "thesis_manifest.json").read_text(encoding="utf-8"))
    built = manifest["countries"]["ZZZ"]["built"]
    assert set(built) >= {
        "T-M1",
        "T-R1",
        "T-R3",
        "T-R4",
        "T-R5",
        "T-R11",
        "T-M2",
        "T-M3",
        "T-R2",
        "T-R6",
        "T-R7",
        "T-R8",
        "T-R9",
        "T-R10",
        "T-R12",
        "T-O1",
        "T-O2",
        "T-O3",
    }


@pytest.mark.synthetic
def test_f8_stamps_a_fixture_build_as_test_values_in_the_caption_and_the_provenance(zzz):
    thesis = _thesis(zzz)
    stem = thesis / "T-R2_potential_ZZZ_solar"
    provenance = json.loads(stem.with_suffix(".provenance.json").read_text(encoding="utf-8"))
    assert provenance["test_values"] is True and provenance["caption"].startswith("TEST VALUES")
    import main

    assert provenance["methodology_version"] == main._read_methodology_version(main.METHODOLOGY_MD)
    assert provenance["artifacts_read"]["potential_aggregates_solar"]
    assert "TEST VALUES" in stem.with_suffix(".tex").read_text(encoding="utf-8")


@pytest.mark.synthetic
def test_f8_numbers_equal_the_rows_they_were_read_from(zzz):
    thesis = _thesis(zzz)
    base = _phase(zzz, "robustness_analysis")
    for tech in ("solar", "wind"):
        aggregates = pd.read_parquet(
            _phase(zzz, "technical_potential") / f"potential_aggregates_{tech}.parquet"
        )
        table = pd.read_csv(thesis / f"T-R2_potential_ZZZ_{tech}.csv")
        row = table[(table["scenario"] == "central") & (table["quantity"] == "P_GW")].iloc[0]
        central = aggregates[aggregates["scenario"] == "central"]
        assert row["reference_m0"] == pytest.approx(
            float(central[central["member"] == "m0"]["P_GW"].iloc[0])
        )
        others = central[central["member"] != "m0"]["P_GW"]
        assert others.min() - 1e-9 <= row["core_min"] <= row["core_max"] <= others.max() + 1e-9
        interval = pd.read_csv(thesis / f"T-R2_land_interval_ZZZ_{tech}.csv")
        assert set(interval.columns) >= {"restrictive", "central", "permissive"}

        hypothesis = pd.read_parquet(base / f"hypothesis_{tech}__core.parquet")
        statistics = pd.read_csv(thesis / f"T-R6_hypothesis_statistics_ZZZ_{tech}.csv")
        core = statistics[(statistics["scale"] == "0p05deg") & (statistics["role"] == "core")]
        assert len(core) == int(hypothesis["hypothesis"].isin(["H1", "H2", "H3", "H4", "H5"]).sum())
        stored = hypothesis.set_index("statistic")
        for stat in ("h1a_core_share", "h1b_vulnerable_share"):
            shown = core.set_index("statistic").loc[stat]
            assert shown["value"] == pytest.approx(float(stored.loc[stat, "value"]))
            assert shown["verdict"] == stored.loc[stat, "verdict"]
        summary = pd.read_csv(thesis / f"T-R6_h1_summary_ZZZ_{tech}.csv")
        primary = summary[
            summary["primary"] & (summary["role"] == "core") & (summary["scale"] == "0p05deg")
        ]
        stored_h1 = (
            pd.read_parquet(base / f"h1_summary_{tech}__core.parquet").query("primary").iloc[0]
        )
        assert primary["verdict"].iloc[0] == stored_h1["verdict"]
        assert primary["c_k"].iloc[0] == pytest.approx(float(stored_h1["c_k"]))

        below = pd.read_parquet(base / f"potential_below_tau_{tech}__core.parquet")
        shown = pd.read_csv(thesis / f"T-R12_potential_below_tau_ZZZ_{tech}.csv")
        assert len(shown) == len(below)
        assert shown["potential_gw"].sum() == pytest.approx(float(below["potential_gw"].sum()))
        exposure = pd.read_parquet(base / f"hazard_exposure_{tech}__core.parquet")
        assert len(pd.read_csv(thesis / f"T-R10_hazard_exposure_ZZZ_{tech}.csv")) == len(exposure)

        tau = float(stored.loc["mr_sr_kendall_tau_b", "value"])
        caption = json.loads(
            (thesis / f"T-O2_mr_sr_agreement_ZZZ_{tech}.provenance.json").read_text(
                encoding="utf-8"
            )
        )["caption"]
        assert "Kendall tau-b" in caption
        assert -1.0 <= tau <= 1.0


@pytest.mark.synthetic
def test_f8_t_r6_has_one_verdict_row_per_hypothesis_read_from_the_summaries_of_f7(zzz):
    thesis = _thesis(zzz)
    base = _phase(zzz, "robustness_analysis")
    for tech in ("solar", "wind"):
        table = pd.read_csv(thesis / f"T-R6_hypothesis_verdicts_ZZZ_{tech}.csv")
        for role in ("core", "sensitivity"):
            rows = table[(table["scale"] == "0p05deg") & (table["role"] == role)]
            assert list(rows["hypothesis"]) == ["H1", "H2", "H3", "H4", "H5"], (tech, role)
            stored = {
                name: pd.read_parquet(base / f"{name}_summary_{tech}__{role}.parquet")
                .query("primary")
                .iloc[0]
                for name in ("h1", "h2", "h3", "h5")
            }
            by = rows.set_index("hypothesis")
            h1, h2, h3, h5 = stored["h1"], stored["h2"], stored["h3"], stored["h5"]
            assert by.loc["H1", "statistic"] == "h1a_core_share"
            assert by.loc["H1", "value"] == pytest.approx(float(h1["c_k"]))
            assert by.loc["H1", "reference"] == pytest.approx(float(h1["reference"]))
            assert by.loc["H1", "threshold"] == pytest.approx(0.60)
            assert by.loc["H1", "statistic_2"] == "h1b_vulnerable_share"
            assert by.loc["H1", "value_2"] == pytest.approx(float(h1["v_k"]))
            assert by.loc["H1", "threshold_2"] == pytest.approx(0.20)
            assert by.loc["H2", "statistic"] == "h2_overlap_index"
            assert by.loc["H2", "value"] == pytest.approx(float(h2["overlap"]))
            assert by.loc["H2", "reference"] == pytest.approx(float(h2["overlap_ref"]))
            assert by.loc["H2", "threshold"] == pytest.approx(0.30)
            assert by.loc["H3", "statistic"] == "h3_beyond_reach_share"
            assert by.loc["H3", "value"] == pytest.approx(float(h3["d"]))
            assert by.loc["H3", "reference"] == pytest.approx(float(h3["d_ref"]))
            assert by.loc["H3", "threshold"] == pytest.approx(0.20)
            for name, row in (("H1", h1), ("H2", h2), ("H3", h3)):
                assert by.loc[name, "verdict"] == row["verdict"]
                assert by.loc[name, "rule"]
            # H5 has two primary statistics, as H1: the resource ratio and the exposure ratio, both against lambda
            assert by.loc["H5", "statistic"] == "h5a_resource_loss_ratio"
            assert by.loc["H5", "value"] == pytest.approx(float(h5["r_loss"]))
            assert by.loc["H5", "threshold"] == pytest.approx(0.20)
            assert by.loc["H5", "statistic_2"] == "h5b_exposure_ratio"
            assert by.loc["H5", "threshold_2"] == pytest.approx(0.20)
            if (
                role == "core"
            ):  # the window 2071-2100 has no hazard data: H5b and the verdict are not available
                assert by.loc["H5", "value_2"] == pytest.approx(float(h5["r_exp"]))
                assert by.loc["H5", "verdict"] == h5["verdict"] and by.loc["H5", "rule"]
            else:
                assert pd.isna(by.loc["H5", "value_2"])
                assert by.loc["H5", "verdict"] == "exposure_not_available"
            # H4 is read from the support phase: ZZZ alone has one country with a profile, so the rule cannot be tested
            assert by.loc["H4", "statistic"] == "h4_strict_pair_count"
            assert by.loc["H4", "verdict"] == "not_testable"
            assert by.loc["H4", "threshold"] == 1.0 and by.loc["H4", "value_2"] == 1.0
            assert by.loc["H4", "threshold_2"] == 2.0
        # the summaries of H2 and H3 are shown whole, with their sensitivities
        h3_shown = pd.read_csv(thesis / f"T-R6_h3_summary_ZZZ_{tech}.csv")
        assert {"top_k_percent_5", "tolerance_2k"} <= set(h3_shown["variant"])
        h2_shown = pd.read_csv(thesis / f"T-R6_h2_summary_ZZZ_{tech}.csv")
        assert {"gamma_0.30", "median_statistic"} <= set(h2_shown["variant"])
        roles = {
            "core",
            "sensitivity",
        }  # no altitude window: wind above 3000 m is not a candidate (OQ-058, COMMAND 46)
        assert set(h3_shown["role"]) == roles


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_f8_t_r10_and_t_r12_agree_with_the_numbers_of_h5_in_t_r6(zzz, tech):
    thesis = _thesis(zzz)
    verdicts = pd.read_csv(thesis / f"T-R6_hypothesis_verdicts_ZZZ_{tech}.csv")
    shown = verdicts[(verdicts["scale"] == "0p05deg") & (verdicts["role"] == "core")]
    r_loss = float(shown.set_index("hypothesis").loc["H5", "value"])
    r_exp = float(shown.set_index("hypothesis").loc["H5", "value_2"])
    summary = pd.read_csv(thesis / f"T-R6_h5_summary_ZZZ_{tech}.csv")
    primary = summary[
        summary["primary"] & (summary["role"] == "core") & (summary["scale"] == "0p05deg")
    ].iloc[0]
    assert r_loss == pytest.approx(primary["r_loss"]) and r_exp == pytest.approx(primary["r_exp"])
    # T-R12: the energy of the fixed economic domain of the reference member and of each core member is the one of H5
    below = pd.read_csv(thesis / f"T-R12_potential_below_tau_ZZZ_{tech}.csv")
    fixed = below[
        (below["series"] == "fixed_domain")
        & (below["land_scenario"] == "central")
        & (below["basis"] == "nominal")
    ].set_index("member")
    assert fixed.loc["m0", "potential_twh"] == pytest.approx(primary["e0_twh"])
    core_energy = fixed.drop(index="m0").query("potential_twh == potential_twh")
    core_energy = core_energy[core_energy.index.isin(_core_members(zzz, tech))]["potential_twh"]
    loss = max(0.0, primary["e0_twh"] - core_energy.min())
    assert loss == pytest.approx(primary["delta_e_twh"])
    assert loss / primary["h0_twh"] == pytest.approx(r_loss)
    # T-R10: the exposed energy of the union of the channels over the economic domain, largest over the hazard members
    exposure = pd.read_csv(thesis / f"T-R10_hazard_exposure_ZZZ_{tech}.csv")
    union = exposure[
        (exposure["hazard"] == "any_channel")
        & (exposure["group"] == "economic_domain")
        & (exposure["basis"] == "absolute")
    ]
    assert len(union) == 9  # the nine members that carry the hazard channel
    assert union["potential_twh"].max() == pytest.approx(primary["e_exp_twh"])
    assert union["potential_twh"].max() / primary["h0_twh"] == pytest.approx(r_exp)
    reference = exposure[
        (exposure["hazard"] == "any_channel")
        & (exposure["group"] == "economic_domain")
        & (exposure["basis"] == "reference")
    ]
    assert reference["potential_twh"].max() == pytest.approx(primary["e_exp_reference_twh"])


def _core_members(zzz, tech=None):
    """The members of the core window that carry the channels of `tech`, from `members.yaml` of the climate phase."""
    entries = yaml.safe_load(
        (_phase(zzz, "climate_forcing") / "members.yaml").read_text(encoding="utf-8")
    )["members"]
    return {e["member"] for e in entries if str(e["window"]) == "2041-2070" and _carries(e, tech)}


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_f8_t_r7_shows_the_displacements_and_rho_of_the_country_with_the_boundaries(zzz, tech):
    thesis = _thesis(zzz)
    stored = pd.read_parquet(
        _phase(zzz, "robustness_analysis") / f"h4_country_{tech}__core.parquet"
    ).query("primary")
    table = pd.read_csv(thesis / f"T-R7_axis_displacement_{tech}.csv")
    shown = table[(table["scale"] == "0p05deg") & (table["role"] == "core")]
    assert list(shown["country"]) == ["ZZZ"]
    assert shown["d_clim"].iloc[0] == pytest.approx(float(stored["d_clim"].iloc[0]))
    assert shown["d_tec"].iloc[0] == pytest.approx(float(stored["d_tec"].iloc[0]))
    assert shown["profile"].iloc[0] == stored["profile"].iloc[0]
    if stored["d_sum"].iloc[0] > 0:
        assert shown["rho"].iloc[0] == pytest.approx(float(stored["rho"].iloc[0]))
    provenance = json.loads(
        (thesis / f"T-R7_axis_displacement_{tech}.provenance.json").read_text(encoding="utf-8")
    )
    assert "0.40 and 0.60" in provenance["caption"]
    assert provenance["artifacts_read_cross_country"][
        "0p05deg"
    ]  # the table of cross_country_h4 was read


@pytest.mark.synthetic
def test_f8_shows_the_empty_published_comparison_as_empty_and_says_why(zzz):
    published = pd.read_csv(_thesis(zzz) / "T-R9_published_comparison_ZZZ.csv")
    provenance = json.loads(
        (_thesis(zzz) / "T-R9_published_comparison_ZZZ.provenance.json").read_text(encoding="utf-8")
    )
    stored = pd.read_parquet(_phase(zzz, "external_validation") / "published_comparison.parquet")
    assert len(published) == len(stored)
    assert "M-F7b-04" in provenance["caption"]
    if stored.empty:
        assert "The table is empty" in provenance["caption"]


@pytest.mark.synthetic
def test_f8_is_deterministic_and_needs_only_the_registered_artifacts(zzz, tmp_path, monkeypatch):
    """Copy `outputs/ZZZ` alone (no raw, interim or shared data) to a new data directory and build twice: the same bytes each time and as the phase's."""
    import shutil

    copied = tmp_path / "copy"
    shutil.copytree(zzz[0] / "outputs" / "ZZZ", copied / "outputs" / "ZZZ")
    shutil.copytree(zzz[0] / "outputs" / "cross_country", copied / "outputs" / "cross_country")
    # the phase ran before the scale check existed, so its T-R6 holds the default scale only
    (copied / "outputs" / "ZZZ" / "manifest__0p1deg.json").unlink(missing_ok=True)
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(copied))
    first, second = tmp_path / "first", tmp_path / "second"
    summary = _build_thesis(first)
    _build_thesis(second)
    files = sorted(p.name for p in first.iterdir())
    assert files == sorted(p.name for p in second.iterdir()) and len(files) > 40
    for name in files:
        assert (first / name).read_bytes() == (second / name).read_bytes(), name
        original = _thesis(zzz) / name
        if name != "thesis_manifest.json" and original.is_file():
            assert (first / name).read_bytes() == original.read_bytes(), name
    assert summary.test_values is True


@pytest.mark.synthetic
def test_f8_refuses_an_artifact_that_changed_after_it_was_registered(zzz, tmp_path, monkeypatch):
    import shutil

    from geofrea.results_synthesis.inputs import ThesisInputError

    copied = tmp_path / "copy"
    shutil.copytree(zzz[0] / "outputs" / "ZZZ", copied / "outputs" / "ZZZ")
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(copied))
    target = (
        copied
        / "outputs"
        / "ZZZ"
        / "technical_potential"
        / "artifacts"
        / "potential_aggregates_solar.parquet"
    )
    target.write_bytes(target.read_bytes() + b"\0")
    with pytest.raises(ThesisInputError, match="changed since it was registered"):
        _build_thesis(tmp_path / "out", technologies=("solar",))


@pytest.mark.synthetic
def test_a_rerun_of_the_f7_of_a_country_makes_f8_refuse_t_r6_t_r7_and_t_r8_until_cross_country_h4_runs_again(
    zzz, tmp_path, monkeypatch
):
    """B-5: the H4 verdict names the `h4_country` tables it read; when F7 registers another one, F8 builds no output that reads the verdict."""
    import hashlib
    import shutil

    from geofrea.robustness_analysis.cross_country import build_h4_verdict

    copied = tmp_path / "copy"
    shutil.copytree(zzz[0] / "outputs" / "ZZZ", copied / "outputs" / "ZZZ")
    shutil.copytree(zzz[0] / "outputs" / "cross_country", copied / "outputs" / "cross_country")
    (copied / "outputs" / "ZZZ" / "manifest__0p1deg.json").unlink(missing_ok=True)
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(copied))
    current = _build_thesis(tmp_path / "current")
    assert not [n for n in current.not_built if "stale" in n.reason]
    # the F7 of ZZZ runs again: the table is replaced and registered with its new hash
    manifest_path = copied / "outputs" / "ZZZ" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = manifest["artifacts"]["h4_country_solar__core"]
    table = pd.read_parquet(
        copied
        / "outputs"
        / "ZZZ"
        / "robustness_analysis"
        / "artifacts"
        / "h4_country_solar__core.parquet"
    )
    from geofrea.core.tables import write_table
    from geofrea.robustness_analysis.table_schemas import (
        ROBUSTNESS_TABLE_SCHEMA_VERSION,
        H4CountryRow,
    )

    path = (
        copied
        / "outputs"
        / "ZZZ"
        / "robustness_analysis"
        / "artifacts"
        / "h4_country_solar__core.parquet"
    )
    table.loc[table["primary"], "d_clim"] += 0.01
    write_table(table, path, schema_version=ROBUSTNESS_TABLE_SCHEMA_VERSION, row_model=H4CountryRow)
    entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    stale = _build_thesis(tmp_path / "stale")
    refused = {n.t_id for n in stale.not_built if "stale" in n.reason}
    assert refused == {"T-R6", "T-R7", "T-R8"}
    assert not any(t in stale.built for t in refused)
    assert "T-R2" in stale.built  # the outputs that do not read the verdict are built
    build_h4_verdict(["ZZZ"], ("solar", "wind"))
    fresh = _build_thesis(tmp_path / "fresh")
    assert not [n for n in fresh.not_built if "stale" in n.reason]
    assert {"T-R6", "T-R7", "T-R8"} <= set(fresh.built)


@pytest.mark.synthetic
def test_the_scale_check_writes_its_thesis_outputs_apart(zzz, zzz_fine):
    fine_dir = zzz[0] / "outputs" / "thesis__0p1deg"
    assert (fine_dir / "T-R2_potential_ZZZ_solar.csv").is_file()
    default = pd.read_csv(_thesis(zzz) / "T-R2_potential_ZZZ_solar.csv")
    fine = pd.read_csv(fine_dir / "T-R2_potential_ZZZ_solar.csv")
    assert len(default) == len(fine)


def _profiles(zzz) -> dict:
    return json.loads(
        (_thesis(zzz) / "T-R8_hypothesis_profiles_ZZZ.json").read_text(encoding="utf-8")
    )


@pytest.mark.synthetic
def test_f8_hypothesis_profiles_hold_the_verdicts_the_numbers_the_ranges_and_the_changing_variants(
    zzz,
):
    base = _phase(zzz, "robustness_analysis")
    payload = _profiles(zzz)
    assert payload["schema_version"] == "1.0" and payload["country"] == "ZZZ"
    assert payload["test_values"] is True and payload["methodology_version"]
    assert [r["technology"] for r in payload["records"]] == ["solar", "wind"]
    for record in payload["records"]:
        tech = record["technology"]
        assert set(record["hypotheses"]) == {"H1", "H2", "H3", "H4", "H5"}
        robustness = pd.read_parquet(base / f"robustness_{tech}__core.parquet")
        assert record["n_candidates"] == len(robustness)
        assert record["n_f7_set"] == int(
            robustness["cell_class"].isin(["ranked", "climate_fragile"]).sum()
        )
        h1 = record["hypotheses"]["H1"]
        table = pd.read_parquet(base / f"h1_summary_{tech}__core.parquet")
        late = pd.read_parquet(base / f"h1_summary_{tech}__sensitivity.parquet").query("primary")
        primary = table[table["primary"]].iloc[0]
        c_k = h1["statistics"]["c_k"]
        assert c_k["value"] == pytest.approx(float(primary["c_k"]))
        assert c_k["reference"] == pytest.approx(float(primary["reference"]))
        assert c_k["threshold"] == pytest.approx(0.60)
        every = list(table["c_k"]) + list(
            late["c_k"]
        )  # the variants of the core window and the 2071-2100 window
        assert c_k["range"]["min"] == pytest.approx(min(every))
        assert c_k["range"]["max"] == pytest.approx(max(every))
        assert c_k["range"]["min"] <= c_k["value"] <= c_k["range"]["max"]

        # the variants whose class differs from the primary one, recomputed from the F7 tables (the partial class is split by what holds)
        def cls(row):
            if row["verdict"] == "partially_supported":
                return "core_stable" if row["h1a_holds"] else "vulnerable"
            return row["verdict"]

        differing = [
            row["variant"]
            for _, row in table.iterrows()
            if not row["primary"] and cls(row) != cls(primary)
        ]
        differing += ["window_2071-2100"] if cls(late.iloc[0]) != cls(primary) else []
        assert h1["n_variants_changing_verdict"] == len(differing)
        assert h1["n_variants"] == len(
            table
        )  # the sensitivities of the core window and the 2071-2100 window
        h5 = record["hypotheses"]["H5"]
        row = pd.read_parquet(base / f"h5_summary_{tech}__core.parquet").query("primary").iloc[0]
        assert h5["statistics"]["r_loss"]["value"] == pytest.approx(float(row["r_loss"]))
        assert h5["statistics"]["e0_twh"]["value"] == pytest.approx(float(row["e0_twh"]))
        assert h5["class"] == row["verdict"]
        h4 = record["hypotheses"]["H4"]
        assert h4["profile"] in {
            "climate_dominated",
            "techno_economic_dominated",
            "mixed",
            "no_displacement",
        }
        assert h4["technology_verdict"]["verdict"] == "not_testable"  # one country alone
        assert h4["technology_verdict"]["profiles"] == {"ZZZ": h4["profile"]}


@pytest.mark.synthetic
def test_f8_t_r8_with_one_country_is_not_assessable_and_gives_no_aggregate_verdict(zzz):
    thesis = _thesis(zzz)
    summary = pd.read_csv(thesis / "T-R8_hypothesis_summary.csv")
    assert set(summary["hypothesis"]) == {"H1", "H2", "H3", "H4", "H5"}
    assert len(summary) == 10  # five hypotheses and two technologies, one row each
    assert not any("aggregate" in c.lower() or "score" in c.lower() for c in summary.columns)
    for _, row in summary.iterrows():
        assert row["n_countries"] == 1
        if row["hypothesis"] == "H4":
            assert row["label"] == "comparative (verdict per technology)"
            assert row["verdict"] == "not_testable"
        else:
            assert (
                row["label"] == "not assessable"
            )  # one country gives fewer than two testable cases
            assert row["n_testable"] <= 1
    profiles = pd.read_csv(thesis / "T-R8_country_profiles.csv")
    assert set(profiles["country"]) == {"ZZZ"} and len(profiles) == 10
    assert {"value_1", "min_1", "max_1", "n_variants_changing_verdict"} <= set(profiles.columns)
    text = (thesis / "T-R8_country_summary_ZZZ.md").read_text(encoding="utf-8")
    assert "TEST VALUES" in text and all(f"**H{i}**" in text for i in range(1, 6))


@pytest.mark.synthetic
def test_f8_t_r8_reads_the_registered_profiles_of_the_other_countries_and_records_their_hashes(
    zzz, tmp_path, monkeypatch
):
    import copy

    import main
    from geofrea.results_synthesis.runner import build_thesis

    monkeypatch.setenv("GEOFREA_DATA_DIR", str(zzz[0]))
    own = _profiles(zzz)
    out = tmp_path / "thesis"
    out.mkdir()
    other = copy.deepcopy(own)
    other["country"] = "ZZB"
    for record in other["records"]:
        record["country"] = "ZZB"
    (out / "T-R8_hypothesis_profiles_ZZB.json").write_text(json.dumps(other), encoding="utf-8")
    from geofrea.results_synthesis.profile_registry import register_profile

    register_profile(out, "ZZB", out / "T-R8_hypothesis_profiles_ZZB.json")
    build_thesis(
        "ZZZ",
        ("solar", "wind"),
        technologies_yaml=main.TECHNOLOGIES_YAML,
        experiments_yaml=main.EXPERIMENTS_YAML,
        parameters_json=main.PARAMETERS_JSON,
        methodology_md=main.METHODOLOGY_MD,
        only=["T-R8"],
        out_dir=out,
    )
    summary = pd.read_csv(out / "T-R8_hypothesis_summary.csv")
    assert (summary["n_countries"] == 2).all()  # ZZZ, built now, and ZZB, read from its file
    profiles = pd.read_csv(out / "T-R8_country_profiles.csv")
    assert set(profiles["country"]) == {"ZZB", "ZZZ"} and len(profiles) == 20
    assert (out / "T-R8_hypothesis_profiles_ZZZ.json").is_file()
    provenance = json.loads(
        (out / "T-R8_country_profiles.provenance.json").read_text(encoding="utf-8")
    )
    assert set(provenance["profiles_read"]) == {"ZZB", "ZZZ"}  # the hash of each profile read (B-4)
    assert (
        provenance["profiles_read"]["ZZZ"]
        == hashlib.sha256((out / "T-R8_hypothesis_profiles_ZZZ.json").read_bytes()).hexdigest()
    )


@pytest.mark.synthetic
def test_f8_t_m1_draws_the_graph_of_the_orchestrator_and_marks_the_axes_of_the_configuration(zzz):
    provenance = json.loads(
        (_thesis(zzz) / "T-M1_framework_dag.provenance.json").read_text(encoding="utf-8")
    )
    graph = _graph_of_the_orchestrator(("solar", "wind"))
    assert provenance["edges"] == [
        [a, b] for a, b in sorted((n, p) for p, needs in graph.items() for n in needs)
    ]
    assert provenance["member_axis"] == sorted(
        ["climate_forcing", "technical_potential", "lcoe_modeling", "robustness_analysis"]
    )
    assert set(provenance["sample_axis"]) <= set(graph)
    assert "Framework of GeoFREA as the directed acyclic graph" in provenance["caption"]


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_f8_t_r3_share_in_agreement_equals_the_share_recomputed_from_the_potential_table(zzz, tech):
    from fractions import Fraction

    members = pd.DataFrame(
        yaml.safe_load(
            (_phase(zzz, "climate_forcing") / "members.yaml").read_text(encoding="utf-8")
        )["members"]
    )
    potential = pd.read_parquet(
        _phase(zzz, "technical_potential") / f"potential_{tech}__central.parquet"
    )
    wide = potential.pivot(index="cell_id", columns="member", values="CF")
    core = members[
        (members["window"].astype(str) == "2041-2070")
        & members["member"].isin(
            potential["member"].astype(str)
        )  # wind has no member of the GCM whose wind channel is excluded
    ]
    table = pd.read_csv(_thesis(zzz) / f"T-R3_cf_agreement_ZZZ_{tech}.csv").set_index("ssp")
    assert sorted(table.index) == sorted(core["ssp"].unique())
    for ssp, part in core.groupby("ssp"):
        change = wide[part["member"].tolist()].sub(wide["m0"], axis=0)
        signs = np.sign(change.to_numpy())
        agree = np.maximum((signs > 0).sum(axis=1), (signs < 0).sum(axis=1))
        marked = agree * 3 >= 2 * len(part)
        valid = change.notna().any(axis=1).to_numpy()
        assert table.loc[ssp, "n_gcms"] == len(part)
        assert table.loc[ssp, "n_cells_in_agreement"] == int(marked[valid].sum())
        assert table.loc[ssp, "share_in_agreement"] == pytest.approx(float(marked[valid].mean()))
        assert Fraction(table.loc[ssp, "min_share"]) == Fraction(2, 3)
