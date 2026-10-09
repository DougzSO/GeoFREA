"""F5 maps: COG of potential density and CF at m0 (central scenario), the T-R1 figure, and `settings.yaml` `figures` (D-F5-015)."""

# ruff: noqa: F401, F811  (the F5 pipeline test module owns the fixtures; they are imported by name for pytest)
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio

from geofrea.core.config_loader import load_settings
from geofrea.core.constants import CELL_DEG, CELL_ORIGIN_LAT, CELL_ORIGIN_LON, NODATA_FLOAT
from geofrea.land_eligibility.cells import row_col_from_id
from geofrea.technical_potential.maps import PotentialMapsError, build_potential_maps
from tests.unit.test_technical_potential_pipeline import (
    CELL_IDS,
    MEMBERS,
    N_CELLS,
    PVOUT,
    SCENARIO_AREAS,
    registry,
    run_ok,
    synthetic_params,
)

REPO = Path(__file__).resolve().parents[2]
SETTINGS = REPO / "config" / "settings.yaml"


def _maps(run_ok, tmp_path, mode):
    _, out = run_ok
    land = out.parent / "in" / "land"
    return build_potential_maps(
        "ZZZ",
        ["solar", "wind"],
        mode,
        potential_dir=out,
        cells_dir=land,
        figures_dir=tmp_path / "figures",
    )


@pytest.mark.unit
def test_rasters_are_cog_on_the_cell_lattice_and_hold_the_m0_values(run_ok, tmp_path):
    result = _maps(run_ok, tmp_path, "none")
    assert set(result.rasters) == {
        "potential_density_solar",
        "capacity_factor_solar",
        "potential_density_wind",
        "capacity_factor_wind",
    }
    with rasterio.open(result.rasters["potential_density_solar"]) as src:
        assert src.crs.to_epsg() == 4326 and src.nodata == NODATA_FLOAT
        assert src.profile["tiled"] is True
        assert src.transform.a == pytest.approx(CELL_DEG) and src.transform.e == pytest.approx(
            -CELL_DEG
        )
        rows, cols = row_col_from_id(CELL_IDS)
        assert src.transform.c == pytest.approx(CELL_ORIGIN_LON + cols.min() * CELL_DEG)
        assert src.transform.f == pytest.approx(CELL_ORIGIN_LAT - rows.min() * CELL_DEG)
        data = src.read(1)
        # luf 0.5 and density 10 MW/km2 (ZZZ test values): P = 5 * area; cell area 25 km2 in the candidate tables
        expected = np.array(SCENARIO_AREAS["central"]) * 5.0 / 25.0
        np.testing.assert_allclose(data[rows - rows.min(), cols - cols.min()], expected, rtol=1e-6)
    with rasterio.open(result.rasters["capacity_factor_solar"]) as src:
        data = src.read(1)
        np.testing.assert_allclose(data[0, :N_CELLS], PVOUT / 24.0, rtol=1e-6)


@pytest.mark.unit
def test_cells_outside_the_candidate_set_are_nodata_in_the_raster(run_ok, tmp_path):
    result = _maps(run_ok, tmp_path, "none")
    out = run_ok[1]
    table = pd.read_parquet(out / "potential_solar__central.parquet")
    keep = CELL_IDS[
        [0, 3]
    ]  # cells 1 and 2 lie between them on the lattice and are not in this table
    # a hole: rebuild the central table without some cells and map again
    reduced = out.parent / "reduced"
    reduced.mkdir()
    table[table["cell_id"].isin(keep)].to_parquet(reduced / "potential_solar__central.parquet")
    land = out.parent / "in" / "land"
    mapped = build_potential_maps(
        "ZZZ",
        ["solar"],
        "none",
        potential_dir=reduced,
        cells_dir=land,
        figures_dir=tmp_path / "f",
    )
    with rasterio.open(mapped.rasters["potential_density_solar"]) as src:
        data = src.read(1)
    # the F3 cell table has 10 cells (8 candidates and 2 that are not): the raster spans all of them
    assert data.shape == (1, 10) and (data == NODATA_FLOAT).sum() == 8
    assert result.rasters  # the full map exists as well


@pytest.mark.unit
def test_a_technology_without_candidates_gets_an_all_nodata_raster_and_no_figure(run_ok, tmp_path):
    out = run_ok[1]
    empty = out.parent / "empty"
    empty.mkdir()
    pd.read_parquet(out / "potential_solar__central.parquet").iloc[0:0].to_parquet(
        empty / "potential_solar__central.parquet"
    )
    mapped = build_potential_maps(
        "ZZZ", ["solar"], "all", potential_dir=empty, cells_dir=out.parent / "in" / "land",
        figures_dir=tmp_path / "f",
    )  # fmt: skip
    with rasterio.open(mapped.rasters["capacity_factor_solar"]) as src:
        assert (src.read(1) == NODATA_FLOAT).all()
    assert mapped.figures == []


@pytest.mark.unit
def test_figures_follow_the_figures_setting(run_ok, tmp_path):
    none = _maps(run_ok, tmp_path / "none", "none")
    assert none.figures == [] and not (tmp_path / "none" / "figures").exists()
    assert none.rasters  # rasters are artifacts and are written whatever the figures setting is

    summary = _maps(run_ok, tmp_path / "summary", "summary")
    assert sorted(p.name for p in summary.figures) == [
        "potential_density_solar__ref__na__na.png",
        "potential_density_wind__ref__na__na.png",
    ]

    everything = _maps(run_ok, tmp_path / "all", "all")
    assert sorted(p.name for p in everything.figures) == [
        "capacity_factor_solar__ref__na__na.png",
        "capacity_factor_wind__ref__na__na.png",
        "potential_density_solar__ref__na__na.png",
        "potential_density_wind__ref__na__na.png",
    ]
    assert all(p.stat().st_size > 1000 for p in everything.figures)


@pytest.mark.unit
def test_unknown_figures_mode_and_missing_inputs_raise(run_ok, tmp_path):
    out = run_ok[1]
    with pytest.raises(PotentialMapsError, match="figures must be one of"):
        build_potential_maps("ZZZ", ["solar"], "some", potential_dir=out)
    with pytest.raises(PotentialMapsError, match="missing input"):
        build_potential_maps("ZZZ", ["solar"], "none", potential_dir=tmp_path, cells_dir=tmp_path)


@pytest.mark.unit
def test_the_real_settings_file_declares_figures():
    assert load_settings(SETTINGS).figures in ("all", "summary", "none")
    assert MEMBERS  # shared constant imported for the fixtures
