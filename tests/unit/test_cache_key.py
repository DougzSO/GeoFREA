"""Content-addressed cache keys (OQ-026): every component of the key invalidates the cache.

The components are the sorted input files with their SHA-256, the config values that affect the output, and the algorithm-version
constant of the module. They are tested on the key itself, on the aligned layers of F2a and on the land-cover tile cache of F1b.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
from shapely.geometry import LineString

import geofrea.grid_alignment.alignment as alignment_module
from geofrea.core.cache_key import (
    FileHashMemo,
    cache_is_current,
    cache_key,
    file_sha256,
    key_path,
    write_cache_key,
)
from geofrea.data_quality_audit import raster_inspection
from geofrea.grid_alignment.alignment import run_grid_alignment_phase
from tests.unit.test_grid_alignment_alignment import (  # noqa: F401  (_data_dir is an autouse fixture)
    _context,
    _country_gdf,
    _data_dir,
    _inputs,
    _small_glo30_tiles,
    _write_dem_tile,
    _write_raster,
)


def _file(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# -- the key itself ------------------------------------------------------------------------------------------------------------


def test_the_key_is_stable_for_the_same_inputs_config_and_version(tmp_path):
    a, b = _file(tmp_path / "a.txt", "a"), _file(tmp_path / "b.txt", "b")
    assert cache_key(1, [a, b], {"cap": 5.0}) == cache_key(1, [a, b], {"cap": 5.0})


def test_the_order_in_which_files_are_listed_does_not_change_the_key(tmp_path):
    a, b = _file(tmp_path / "a.txt", "a"), _file(tmp_path / "b.txt", "b")
    assert cache_key(1, [a, b]) == cache_key(1, [b, a])


def test_a_data_directory_that_moves_keeps_the_key(tmp_path):
    first = _file(tmp_path / "one" / "t.txt", "x")
    second = _file(tmp_path / "two" / "t.txt", "x")
    assert cache_key(1, [first]) == cache_key(1, [second])


def test_the_content_of_an_input_file_changes_the_key(tmp_path):
    a = _file(tmp_path / "a.txt", "a")
    before = cache_key(1, [a])
    _file(tmp_path / "a.txt", "changed")
    assert cache_key(1, [a]) != before


def test_adding_or_removing_an_input_file_changes_the_key(tmp_path):
    a, b = _file(tmp_path / "a.txt", "a"), _file(tmp_path / "b.txt", "b")
    assert len({cache_key(1, [a]), cache_key(1, [a, b]), cache_key(1, [b])}) == 3


def test_a_config_value_changes_the_key(tmp_path):
    a = _file(tmp_path / "a.txt", "a")
    assert cache_key(1, [a], {"cap": 5.0}) != cache_key(1, [a], {"cap": 6.0})
    assert cache_key(1, [a], {"cap": 5.0}) != cache_key(1, [a], {"cap": 5.0, "extra": 1})


def test_the_algorithm_version_changes_the_key(tmp_path):
    a = _file(tmp_path / "a.txt", "a")
    assert cache_key(1, [a]) != cache_key(2, [a])


def test_an_output_with_no_sidecar_or_another_key_is_not_current(tmp_path):
    out = _file(tmp_path / "out.tif", "data")
    assert not cache_is_current(out, "k1")
    write_cache_key(out, "k1")
    assert cache_is_current(out, "k1")
    assert not cache_is_current(out, "k2")
    assert key_path(out).name == "out.tif.cachekey"
    out.unlink()
    assert not cache_is_current(out, "k1")


def test_the_hash_memo_reuses_a_hash_while_size_and_mtime_hold_and_survives_a_reload(tmp_path):
    f = _file(tmp_path / "f.txt", "abc")
    memo_path = tmp_path / "memo.json"
    assert FileHashMemo(memo_path).sha256(f) == file_sha256(f)
    assert json.loads(memo_path.read_text(encoding="utf-8"))
    with patch("geofrea.core.cache_key.file_sha256", side_effect=AssertionError("hashed again")):
        assert FileHashMemo(memo_path).sha256(f)


# -- F2a: the aligned layers ---------------------------------------------------------------------------------------------------


def _calls_of_reproject(inputs, context):
    """Calls of the elevation and slope pass (F2a reads the GLO-30 tiles, D-F2a-021)."""
    with patch.object(
        alignment_module,
        "elevation_and_slope_from_glo30",
        wraps=alignment_module.elevation_and_slope_from_glo30,
    ) as spy:
        run_grid_alignment_phase(context, inputs)
    return spy.call_count


def test_alignment_recomputes_a_layer_only_when_a_component_of_its_key_changes(
    tmp_path, monkeypatch
):
    tiles = _write_dem_tile(tmp_path, 55.0)
    inputs = _inputs(slope_dem_tiles=tiles, country_gdf=_country_gdf())
    context = _context(tmp_path)
    assert _calls_of_reproject(inputs, context) >= 1

    assert _calls_of_reproject(inputs, context) == 0  # nothing changed: reused

    monkeypatch.setattr(alignment_module, "ALIGNMENT_ALGORITHM_VERSION", 99)  # algorithm version
    assert _calls_of_reproject(inputs, context) >= 1
    assert _calls_of_reproject(inputs, context) == 0

    _write_dem_tile(tmp_path, 77.0)  # content of the input file
    assert _calls_of_reproject(inputs, context) >= 1
    assert _calls_of_reproject(inputs, context) == 0


def test_an_aligned_layer_without_a_key_sidecar_is_recomputed(tmp_path):
    inputs = _inputs(slope_dem_tiles=_write_dem_tile(tmp_path, 55.0), country_gdf=_country_gdf())
    context = _context(tmp_path)
    result = run_grid_alignment_phase(context, inputs)
    aligned = result.elevation
    before = aligned.stat().st_mtime_ns
    key_path(aligned).unlink()
    assert _calls_of_reproject(inputs, context) == 1  # exactly one recomputation of the layer
    assert key_path(aligned).is_file()  # the key sidecar is written again
    assert aligned.stat().st_mtime_ns > before  # the raster itself was rewritten


def test_the_distance_cap_is_a_config_component_of_the_distance_layers(tmp_path):
    grid_file = tmp_path / "grid.geojson"
    gpd.GeoDataFrame(geometry=[LineString([(-8.9, 38.9), (-8.7, 38.7)])], crs="EPSG:4326").to_file(
        grid_file, driver="GeoJSON"
    )
    context = _context(tmp_path)

    def calls(cap: float) -> int:
        inputs = _inputs(grid_source=grid_file, country_gdf=_country_gdf(), distance_cap_km=cap)
        with patch.object(
            alignment_module,
            "rasterize_linear_distance",
            wraps=alignment_module.rasterize_linear_distance,
        ) as spy:
            run_grid_alignment_phase(context, inputs)
        return spy.call_count

    assert calls(100.0) == 1
    assert calls(100.0) == 0
    assert calls(50.0) == 1  # a config value of the key


def test_the_list_of_land_cover_tiles_is_part_of_the_key(tmp_path):
    t1, t2 = tmp_path / "t1.tif", tmp_path / "t2.tif"
    _write_raster(t1, 10.0)
    _write_raster(t2, 20.0)
    context = _context(tmp_path)

    def fake_mosaic(tiles, out_path, grid, country_gdf):
        _write_raster(out_path, 10.0, size=grid.height)
        return out_path

    def calls(tiles) -> int:
        inputs = _inputs(land_cover_tiles=tiles, country_gdf=_country_gdf())
        with (
            patch.object(alignment_module, "mosaic_land_cover", side_effect=fake_mosaic) as spy,
            patch.object(alignment_module, "land_cover_class_counts", return_value=None),
        ):
            run_grid_alignment_phase(context, inputs)
        return spy.call_count

    assert calls([t1]) == 1
    assert calls([t1]) == 0
    assert calls([t1, t2]) == 1  # a tile added to the list
    assert calls([t1, t2]) == 0
    assert calls([t2]) == 1  # a tile removed


# -- F1b: the land-cover tile cache --------------------------------------------------------------------------------------------


def test_the_land_cover_tile_key_has_every_component(tmp_path, monkeypatch):
    tile = _file(tmp_path / "tile.tif", "bytes")
    key = raster_inspection._land_cover_tile_cache_key
    base = key(tile, "polygon-a")
    assert base == key(tile, "polygon-a")

    assert key(tile, "polygon-b") != base  # config: the masking polygon
    with monkeypatch.context() as m:
        m.setattr(raster_inspection, "_LAND_COVER_WINDOW_PX", 4096)  # config: the scan window
        assert key(tile, "polygon-a") != base
    with monkeypatch.context() as m:
        m.setattr(raster_inspection, "LAND_COVER_TILE_ALGORITHM_VERSION", 2)  # algorithm version
        assert key(tile, "polygon-a") != base
    _file(tmp_path / "tile.tif", "other bytes")  # input content
    assert key(tile, "polygon-a") != base


def test_a_saved_tile_entry_is_a_miss_after_the_algorithm_version_changes(tmp_path, monkeypatch):
    tile = _file(tmp_path / "tile.tif", "bytes")
    cache_dir = tmp_path / "cache"
    payload = {"crs": "EPSG:4326", "res": 0.1, "class_areas": {"10": 1.0}}
    raster_inspection._save_land_cover_tile_cache(cache_dir, tile, "fp", payload)
    assert raster_inspection._load_land_cover_tile_cache(cache_dir, tile, "fp") is not None
    monkeypatch.setattr(raster_inspection, "LAND_COVER_TILE_ALGORITHM_VERSION", 2)
    assert raster_inspection._load_land_cover_tile_cache(cache_dir, tile, "fp") is None
