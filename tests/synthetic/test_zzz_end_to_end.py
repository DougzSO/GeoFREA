"""The synthetic country through F1 to F6 with no network (A-06, V-08, I-4, D13b, D-F6-014).

The ZZZ fixture and its miniature climate inputs are generated into a scratch data directory; the orchestrator then runs data_acquisition,
data_quality_audit, grid_alignment, siting_layers, land_eligibility (F3), external_inputs, climate_forcing (F4), technical_potential and
potential_maps (F5), lcoe_modeling and sample_size_convergence (F6) on them. The experiments file is copied with small sizes for
the sample-size protocol (initial size 16, ceiling 64, top-k 25 percent): the real values are the author's and are null there. Every socket connection is refused while the pipeline runs, so a hidden download fails the test.

F5 needs a power curve and an IEC class rule, which the real registry leaves null until OQ-005 closes (D-F5-003): this test copies the
registry with the synthetic rule (one class, no bound) and points the phase at the synthetic curve of `tests/fixtures/power_curves/`.
The ZZZ land cover has three bands of whole decision cells: cropland (north, excluded for solar), grassland (middle, allowed for both) and
tree cover (south, excluded for both). Solar therefore has candidates only in the grassland band, where the population gradient and the
river's setback trim them; wind has candidates in the cropland and grassland bands. Both technologies run through every phase.
"""

from __future__ import annotations

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
PHASES = ["technical_potential", "potential_maps", "lcoe_modeling", "sample_size_convergence"]
INITIAL_SIZE, CEILING, TOP_K_PERCENT = 16, 64, 25
SCENARIOS = ("central", "restrictive", "permissive")
MASKED_MEMBER = "m_miroc6_ssp370_2071_2100"
N_CELLS = 24  # 6 x 4 decision cells
N_MEMBERS = 37  # 36 and the reference member


class NetworkUsedError(AssertionError):
    pass


def _no_network(*_args, **_kwargs):
    raise NetworkUsedError("the ZZZ pipeline tried to open a network connection")


@pytest.fixture(scope="module")
def zzz(tmp_path_factory):
    import main  # repo-root script

    data = tmp_path_factory.mktemp("zzz_data")
    registry = yaml.safe_load((REPO / "config" / "technologies.yaml").read_text(encoding="utf-8"))
    registry["wind"]["power_curves"] = {"synthetic": "synthetic_curve"}
    registry["wind"]["iec_class_rule"] = [
        {"iec_class": "synthetic", "mean_speed_upper_ms": None, "source": None}
    ]
    technologies = data / "technologies_with_synthetic_rule.yaml"
    technologies.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    experiments_text = (REPO / "config" / "experiments.yaml").read_text(encoding="utf-8")
    for old, new in (
        ("initial_size: 500", f"initial_size: {INITIAL_SIZE}"),
        ("max_size_for_convergence: null", f"max_size_for_convergence: {CEILING}"),
        ("top_k_percent: null", f"top_k_percent: {TOP_K_PERCENT}"),
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
            "technical_potential",
            "potential_maps",
            "lcoe_modeling",
            "sample_size_convergence",
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
    assert len(forcing) + len(masked) == N_CELLS * N_MEMBERS
    assert set(masked["member"].astype(str)) == {MASKED_MEMBER} and len(masked) > 0
    lo, hi = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))[
        "gcm_ensemble"
    ]["wind_factor_valid_range"]
    assert ((masked["delta_wind"] < lo) | (masked["delta_wind"] > hi)).all()
    assert forcing["delta_wind"].between(lo, hi).all()
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
        assert len(agg) == 3 * N_MEMBERS
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
    # a cell-member declared masked for the wind factor is absent for solar too (D-F5-007)
    masked = pd.read_parquet(_phase(zzz, "climate_forcing") / "forcing_masked.parquet")
    masked_here = masked[masked["cell_id"].isin(candidates["cell_id"])]
    assert len(table) == len(candidates) * N_MEMBERS - len(masked_here)


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
    assert len(table) == len(candidates) * N_MEMBERS - len(masked_candidates)
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
    """D-F6-004: the protocol doubles from the initial size within the ceiling; its MR is the provisional stand-in for F7's."""
    table = pq.read_table(
        _phase(zzz, "sample_size_convergence") / f"sample_size_convergence_{tech}.parquet"
    )
    meta = json.loads(table.schema.metadata[b"geofrea_convergence_provenance"])
    rows = table.to_pandas()
    assert meta["provisional"] is True and meta["mr_function"] == "provisional"
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
    assert summary["technologies"][tech]["mr_function"] == "provisional"


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
    assert len(forcing) + len(masked) == len(cells) * N_MEMBERS
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


@pytest.mark.synthetic
def test_the_run_used_no_network(zzz):
    """The fixture refused every socket connection while the phases ran; the run succeeded, so none was attempted."""
    assert socket.socket.connect is _no_network
