"""Unit tests for geofrea.data_acquisition.local_layers.

All tests build a fake raw-data directory under tmp_path and point
RAW_DATA_DIR_ENV_VAR at it via monkeypatch — no dependency on the real
local database (see pyproject.toml's "unit" marker, "no external data
dependency"). GEOFREA_RAW_DATA_DIR is also explicitly cleared by an
autouse fixture so these tests are hermetic regardless of what is set
in the developer's own shell/.env.
"""

from pathlib import Path

import pytest

from geofrea.data_acquisition.local_layers import (
    RAW_DATA_DIR_ENV_VAR,
    resolve_elevation_path,
    resolve_grid_path,
    resolve_land_cover_tiles,
    resolve_population_path,
    resolve_roads_path,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(RAW_DATA_DIR_ENV_VAR, raising=False)


def _make_raw_dir(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    return raw


@pytest.mark.unit
def test_resolve_elevation_path_found(tmp_path, monkeypatch):
    raw = _make_raw_dir(tmp_path)
    (raw / "elevation" / "Brazil").mkdir(parents=True)
    expected = raw / "elevation" / "Brazil" / "BRA_elevation.tif"
    expected.write_bytes(b"")
    monkeypatch.setenv(RAW_DATA_DIR_ENV_VAR, str(raw))

    assert resolve_elevation_path("BRA") == expected


@pytest.mark.unit
def test_resolve_elevation_path_uses_iso3_dir_name_for_prt(tmp_path, monkeypatch):
    # PRT is one of the two countries whose elevation directory is
    # named by ISO3 code rather than full country name (confirmed
    # against the real database — see local_layers.py's module
    # docstring, "elevation subdirectories do NOT follow one
    # convention").
    raw = _make_raw_dir(tmp_path)
    (raw / "elevation" / "PRT").mkdir(parents=True)
    expected = raw / "elevation" / "PRT" / "PRT_elevation.tif"
    expected.write_bytes(b"")
    monkeypatch.setenv(RAW_DATA_DIR_ENV_VAR, str(raw))

    assert resolve_elevation_path("PRT") == expected


@pytest.mark.unit
def test_resolve_elevation_path_missing_file_returns_none(tmp_path, monkeypatch):
    raw = _make_raw_dir(tmp_path)
    (raw / "elevation" / "Brazil").mkdir(parents=True)
    monkeypatch.setenv(RAW_DATA_DIR_ENV_VAR, str(raw))

    assert resolve_elevation_path("BRA") is None


@pytest.mark.unit
def test_resolve_elevation_path_unmapped_country_raises_keyerror(tmp_path, monkeypatch):
    raw = _make_raw_dir(tmp_path)
    monkeypatch.setenv(RAW_DATA_DIR_ENV_VAR, str(raw))

    with pytest.raises(KeyError):
        resolve_elevation_path("XXX")


@pytest.mark.unit
def test_resolve_elevation_path_no_env_var_returns_none(tmp_path):
    # GEOFREA_RAW_DATA_DIR unset entirely — graceful, not a raise (see
    # module docstring's "two different failure modes"). Deliberately
    # NOT raised even for a country that IS in the mapping table.
    assert resolve_elevation_path("BRA") is None


@pytest.mark.unit
def test_resolve_population_path_found(tmp_path, monkeypatch):
    raw = _make_raw_dir(tmp_path)
    (raw / "population").mkdir(parents=True)
    expected = raw / "population" / "bra_pop_2020.tif"
    expected.write_bytes(b"")
    monkeypatch.setenv(RAW_DATA_DIR_ENV_VAR, str(raw))

    assert resolve_population_path("BRA") == expected


@pytest.mark.unit
def test_resolve_population_path_missing_file_returns_none(tmp_path, monkeypatch):
    raw = _make_raw_dir(tmp_path)
    (raw / "population").mkdir(parents=True)
    monkeypatch.setenv(RAW_DATA_DIR_ENV_VAR, str(raw))

    assert resolve_population_path("BRA") is None


@pytest.mark.unit
def test_resolve_population_path_no_lookup_table_needed(tmp_path, monkeypatch):
    # Unlike elevation/land_cover, population has no per-country mapping
    # table — any ISO3 code resolves mechanically, even one absent from
    # both _ELEVATION_COUNTRY_DIRS and _LAND_COVER_COUNTRY_DIRS.
    raw = _make_raw_dir(tmp_path)
    (raw / "population").mkdir(parents=True)
    expected = raw / "population" / "xxx_pop_2020.tif"
    expected.write_bytes(b"")
    monkeypatch.setenv(RAW_DATA_DIR_ENV_VAR, str(raw))

    assert resolve_population_path("XXX") == expected


@pytest.mark.unit
def test_resolve_grid_path_found(tmp_path, monkeypatch):
    raw = _make_raw_dir(tmp_path)
    (raw / "infrastructure" / "grid").mkdir(parents=True)
    expected = raw / "infrastructure" / "grid" / "BRA_grid_osm.geojson"
    expected.write_bytes(b"")
    monkeypatch.setenv(RAW_DATA_DIR_ENV_VAR, str(raw))

    assert resolve_grid_path("BRA") == expected


@pytest.mark.unit
def test_resolve_grid_path_ignores_unlabeled_gpkg(tmp_path, monkeypatch):
    # infrastructure/grid also holds an unlabeled grid.gpkg in the real
    # database — must never be picked up for a country's exact filename
    # lookup (see local_layers.py's resolve_grid_path docstring).
    raw = _make_raw_dir(tmp_path)
    (raw / "infrastructure" / "grid").mkdir(parents=True)
    (raw / "infrastructure" / "grid" / "grid.gpkg").write_bytes(b"")
    monkeypatch.setenv(RAW_DATA_DIR_ENV_VAR, str(raw))

    assert resolve_grid_path("BRA") is None


@pytest.mark.unit
def test_resolve_land_cover_tiles_found_sorted(tmp_path, monkeypatch):
    raw = _make_raw_dir(tmp_path)
    tiles_dir = raw / "land_cover" / "Portugal"
    tiles_dir.mkdir(parents=True)
    tile_b = tiles_dir / "ESA_WorldCover_10m_2020_v100_N27W009_Map.tif"
    tile_a = tiles_dir / "ESA_WorldCover_10m_2020_v100_N27W006_Map.tif"
    tile_a.write_bytes(b"")
    tile_b.write_bytes(b"")
    monkeypatch.setenv(RAW_DATA_DIR_ENV_VAR, str(raw))

    assert resolve_land_cover_tiles("PRT") == [tile_a, tile_b]


@pytest.mark.unit
def test_resolve_land_cover_tiles_ignores_non_matching_files(tmp_path, monkeypatch):
    raw = _make_raw_dir(tmp_path)
    tiles_dir = raw / "land_cover" / "Portugal"
    tiles_dir.mkdir(parents=True)
    (tiles_dir / "readme.txt").write_bytes(b"")
    monkeypatch.setenv(RAW_DATA_DIR_ENV_VAR, str(raw))

    assert resolve_land_cover_tiles("PRT") == []


@pytest.mark.unit
def test_resolve_land_cover_tiles_missing_dir_returns_empty_list(tmp_path, monkeypatch):
    raw = _make_raw_dir(tmp_path)
    monkeypatch.setenv(RAW_DATA_DIR_ENV_VAR, str(raw))

    assert resolve_land_cover_tiles("PRT") == []


@pytest.mark.unit
def test_resolve_land_cover_tiles_unmapped_country_raises_keyerror(tmp_path, monkeypatch):
    raw = _make_raw_dir(tmp_path)
    monkeypatch.setenv(RAW_DATA_DIR_ENV_VAR, str(raw))

    with pytest.raises(KeyError):
        resolve_land_cover_tiles("XXX")


@pytest.mark.unit
def test_resolve_land_cover_tiles_no_env_var_returns_empty_list(tmp_path):
    assert resolve_land_cover_tiles("PRT") == []


@pytest.mark.unit
@pytest.mark.parametrize(
    ("country_code", "region_dir", "region_file"),
    [
        ("BRA", "Region_2_Central_South_America", "GRIP4_region2.shp"),
        ("PRT", "Region_4_Europe", "GRIP4_region4.shp"),
    ],
)
def test_resolve_roads_path_found(tmp_path, monkeypatch, country_code, region_dir, region_file):
    raw = _make_raw_dir(tmp_path)
    (raw / "infrastructure" / "roads" / region_dir).mkdir(parents=True)
    expected = raw / "infrastructure" / "roads" / region_dir / region_file
    expected.write_bytes(b"")
    monkeypatch.setenv(RAW_DATA_DIR_ENV_VAR, str(raw))

    assert resolve_roads_path(country_code) == expected


@pytest.mark.unit
def test_resolve_roads_path_missing_file_returns_none(tmp_path, monkeypatch):
    raw = _make_raw_dir(tmp_path)
    (raw / "infrastructure" / "roads" / "Region_2_Central_South_America").mkdir(parents=True)
    monkeypatch.setenv(RAW_DATA_DIR_ENV_VAR, str(raw))

    assert resolve_roads_path("BRA") is None


@pytest.mark.unit
def test_resolve_roads_path_unmapped_country_raises_keyerror(tmp_path, monkeypatch):
    # _ROADS_COUNTRY_REGION_DIRS is deliberately BRA/PRT only — see
    # local_layers.py's module docstring for why extending it to other
    # countries is blocked on a regions_lookup.json numbering conflict,
    # not just unstarted work. Any other country must raise, not guess.
    raw = _make_raw_dir(tmp_path)
    monkeypatch.setenv(RAW_DATA_DIR_ENV_VAR, str(raw))

    with pytest.raises(KeyError):
        resolve_roads_path("CHN")


@pytest.mark.unit
def test_resolve_roads_path_no_env_var_returns_none(tmp_path):
    assert resolve_roads_path("BRA") is None
