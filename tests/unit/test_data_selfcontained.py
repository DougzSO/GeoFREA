"""GEOFREA_DATA_DIR is self-contained: the pipeline reads nothing outside it (COMMAND 37; METHODOLOGY A-08, M-F1-01)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from geofrea.core import paths
from geofrea.data_acquisition import local_layers
from geofrea.data_acquisition.fetchers import gadm

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_no_module_of_the_pipeline_names_the_shared_raw_directory():
    pattern = re.compile(r"SHARED_RAW|shared_raw")
    hits = [
        f"{p.relative_to(REPO)}:{i}"
        for p in [*(REPO / "src").rglob("*.py"), REPO / "main.py"]
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if pattern.search(line)
    ]
    assert hits == []
    assert not hasattr(paths, "shared_raw")


@pytest.mark.unit
def test_the_environment_example_does_not_declare_the_shared_raw_directory():
    assert "SHARED_RAW" not in (REPO / ".env.example").read_text(encoding="utf-8")


@pytest.mark.unit
def test_the_resolvers_ignore_a_shared_raw_directory_that_still_has_every_file(
    tmp_path, monkeypatch
):
    """With the old variable pointing at a complete tree and GEOFREA_DATA_DIR empty, nothing resolves."""
    shared = tmp_path / "shared"
    for rel in (
        "population/bra_pop_2020.tif",
        "infrastructure/grid/BRA_grid_osm.geojson",
        "infrastructure/roads/Region_2_Central_South_America/GRIP4_region2.shp",
        "land_cover/Brazil/ESA_WorldCover_10m_2020_v100_N00W051_Map.tif",
        "solar_potential/World_PVOUT_GISdata_LTAy_AvgDailyTotals_GlobalSolarAtlas-v2_GEOTIFF/PVOUT.tif",
        "countries_borders/Brazil/gadm41_BRA_0.shp",
    ):
        path = shared / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("GEOFREA_SHARED_RAW_DIR", str(shared))
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(data))
    assert local_layers.resolve_population_path("BRA") is None
    assert local_layers.resolve_grid_path("BRA") is None
    assert local_layers.resolve_roads_path("BRA") is None
    assert local_layers.resolve_land_cover_tiles("BRA") == []
    assert local_layers.resolve_solar_path("BRA") is None
    assert gadm._local_database_dir("BRA") == data / "raw" / "gadm" / "BRA" / "gadm41_BRA_shp"
    assert not gadm._local_database_dir("BRA").exists()


@pytest.mark.unit
def test_the_resolvers_read_the_layout_of_a8_inside_the_data_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    raw = tmp_path / "raw"
    expected = {
        "population": raw / "population" / "BRA" / "bra_pop_2020.tif",
        "grid": raw / "infrastructure_grid" / "BRA" / "BRA_grid_osm.geojson",
        "roads": raw
        / "infrastructure_roads"
        / "_global"
        / "Region_2_Central_South_America"
        / "GRIP4_region2.shp",
    }
    for path in expected.values():
        path.parent.mkdir(parents=True)
        path.write_bytes(b"")
    assert local_layers.resolve_population_path("BRA") == expected["population"]
    assert local_layers.resolve_grid_path("BRA") == expected["grid"]
    assert local_layers.resolve_roads_path("BRA") == expected["roads"]
