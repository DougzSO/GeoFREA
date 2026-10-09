"""The synthetic country through F1 to F5 with no network (A-06, V-08, I-4, D13b).

The ZZZ fixture and its miniature climate inputs are generated into a scratch data directory; the orchestrator then runs data_acquisition,
data_quality_audit, grid_alignment, siting_layers, land_eligibility (F3), external_inputs, climate_forcing (F4), technical_potential and
potential_maps (F5) on them. Every socket connection is refused while the pipeline runs, so a hidden download fails the test.

F5 needs a power curve and an IEC class rule, which the real registry leaves null until OQ-005 closes (D-F5-003): this test copies the
registry with the synthetic rule (one class, no bound) and points the phase at the synthetic curve of `tests/fixtures/power_curves/`.
The ZZZ land cover has three bands of whole decision cells: cropland (north, excluded for solar), grassland (middle, allowed for both) and
tree cover (south, excluded for both). Solar therefore has candidates only in the grassland band, where the population gradient and the
river's setback trim them; wind has candidates in the cropland and grassland bands. Both technologies run through every phase.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio
import yaml

from geofrea.core.config_loader import load_audit_config, load_settings
from geofrea.land_eligibility.cells import pixel_row_area_km2

REPO = Path(__file__).resolve().parents[2]
CURVES = REPO / "tests" / "fixtures" / "power_curves"
PHASES = ["technical_potential", "potential_maps"]
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

    patch = pytest.MonkeyPatch()
    patch.setenv("GEOFREA_DATA_DIR", str(data))
    patch.setattr(main, "TECHNOLOGIES_YAML", technologies)
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
        )
        assert ok, {k: v.status for k, v in results.items()}
        yield data, results
    finally:
        patch.undo()


def _phase(zzz, phase, kind="artifacts"):
    """`outputs/ZZZ/<phase>/<kind>` of the scratch data directory (the autouse conftest fixture re-points the env var per test)."""
    return zzz[0] / "outputs" / "ZZZ" / phase / kind


def _eligibility(zzz, tech, scenario):
    return pd.read_parquet(_phase(zzz, "land_eligibility") / f"cells_{tech}__{scenario}.parquet")


@pytest.mark.synthetic
def test_every_phase_from_f1_to_f5_runs_and_succeeds(zzz):
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


@pytest.mark.synthetic
def test_the_run_used_no_network(zzz):
    """The fixture refused every socket connection while the phases ran; the run succeeded, so none was attempted."""
    assert socket.socket.connect is _no_network
