"""Unit tests for geofrea.data_quality_audit.raster_inspection.

inspect_raster/inspect_land_cover_tiles need real georeferenced rasters,
so small synthetic GeoTIFFs are written to tmp_path with rasterio rather
than fabricated dict fixtures — this exercises the actual windowed-read +
polygon-mask + geodetic-area code path, not just its return shape. See
tests/unit/test_audit.py's module docstring for why *real* baseline
geodata (as opposed to synthetic-but-real-format rasters) isn't used.
"""

import importlib
import logging
import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.errors import WindowError
from rasterio.transform import from_origin
from shapely.geometry import Polygon, box

from geofrea.core.constants import MASK_FILL
from geofrea.data_quality_audit import raster_inspection
from geofrea.data_quality_audit.raster_inspection import (
    _country_window,
    _mask_raster_by_polygon,
    _nodata_mask,
    _stats_chunked,
    diagnose_consistency,
    inspect_land_cover_tiles,
    inspect_power_plants,
    inspect_raster,
    row_area_km2,
)

# Small raster near Lisbon: 10x10 pixels, 0.01deg resolution.
_ORIGIN_LON, _ORIGIN_LAT = -9.0, 39.0
_RES = 0.01
_SIZE = 10


def _write_raster(path: Path, data: np.ndarray, nodata: float | None = None) -> None:
    transform = from_origin(_ORIGIN_LON, _ORIGIN_LAT, _RES, _RES)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=data.dtype,
        crs="EPSG:4326",
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(data, 1)


def _write_raster_no_crs(path: Path, data: np.ndarray, nodata: float | None = None) -> None:
    """Like _write_raster, but with no CRS at all (e.g. combined-Weibull-A/k, D-F1b-005)."""
    transform = from_origin(_ORIGIN_LON, _ORIGIN_LAT, _RES, _RES)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=data.dtype,
        crs=None,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(data, 1)


def _covering_gdf() -> gpd.GeoDataFrame:
    """Polygon covering the full extent of the synthetic raster above."""
    west, north = _ORIGIN_LON, _ORIGIN_LAT
    east = west + _SIZE * _RES
    south = north - _SIZE * _RES
    return gpd.GeoDataFrame(geometry=[box(west, south, east, north)], crs="EPSG:4326")


def _write_raster_at(
    path: Path,
    data: np.ndarray,
    *,
    origin_lon: float,
    origin_lat: float,
    res: float,
    nodata: float | None = None,
) -> None:
    """Like _write_raster, but with an arbitrary origin/resolution.

    Needed for the multi-tile inspect_land_cover_tiles tests below, where
    tiles at different real-world locations (and, for the multi-window
    test, a different resolution) must be placed deliberately relative to
    a country polygon.
    """
    transform = from_origin(origin_lon, origin_lat, res, res)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=data.dtype,
        crs="EPSG:4326",
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(data, 1)


@pytest.mark.unit
def test_nodata_mask_handles_none_nan_and_sentinel():
    data = np.array([1.0, np.nan, -9999.0, 5.0], dtype=np.float32)

    assert list(_nodata_mask(data, None)) == [True, False, True, True]
    assert list(_nodata_mask(data, -9999.0)) == [True, False, False, True]


@pytest.mark.unit
def test_row_area_km2_shrinks_toward_the_poles():
    shape = (100, 10)
    equator_transform = from_origin(0.0, 1.0, 0.01, 0.01)  # rows span ~1..0 deg lat
    polar_transform = from_origin(0.0, -80.0, 0.01, 0.01)  # rows span ~-80..-81 deg lat

    equator_areas = row_area_km2(shape, equator_transform)
    polar_areas = row_area_km2(shape, polar_transform)

    assert equator_areas.mean() > polar_areas.mean()


@pytest.mark.unit
def test_inspect_raster_reports_error_for_a_corrupt_file(tmp_path):
    # inspect_raster assumes the file exists (its caller, audit.py, is
    # the one that checks Path.exists() first — same contract as
    # legacy's DataAuditor.run(), whose `result["size_mb"] = path.stat()...`
    # also runs unguarded before its own try/except). An existing-but-
    # unreadable file is the case this function's own error handling
    # actually covers.
    path = tmp_path / "corrupt.tif"
    path.write_bytes(b"not a real geotiff")

    result = inspect_raster(path)

    assert result["error"] is not None


@pytest.mark.unit
def test_inspect_raster_computes_stats_over_full_coverage(tmp_path):
    data = np.arange(_SIZE * _SIZE, dtype=np.float32).reshape(_SIZE, _SIZE)
    path = tmp_path / "elevation.tif"
    _write_raster(path, data, nodata=-9999.0)

    result = inspect_raster(path, country_gdf=_covering_gdf())

    assert result["error"] is None
    assert result["min"] == pytest.approx(0.0)
    assert result["max"] == pytest.approx(99.0)
    assert result["mean"] == pytest.approx(49.5)
    assert result["valid_pct"] == pytest.approx(100.0)
    assert result["area_km2"] > 0
    assert result["crs"] == "EPSG:4326"


@pytest.mark.unit
def test_inspect_raster_excludes_nodata_pixels_from_stats(tmp_path):
    data = np.full((_SIZE, _SIZE), 10.0, dtype=np.float32)
    data[0, :] = -9999.0  # one full row of nodata
    path = tmp_path / "with_nodata.tif"
    _write_raster(path, data, nodata=-9999.0)

    result = inspect_raster(path, country_gdf=_covering_gdf())

    assert result["error"] is None
    assert result["mean"] == pytest.approx(10.0)
    assert result["valid_pct"] < 100.0


@pytest.mark.unit
def test_inspect_raster_without_country_gdf_reads_full_file(tmp_path):
    data = np.full((_SIZE, _SIZE), 3.0, dtype=np.float32)
    path = tmp_path / "no_mask.tif"
    _write_raster(path, data)

    result = inspect_raster(path, country_gdf=None)

    assert result["error"] is None
    assert result["masked_by"] == "full file"
    assert result["mean"] == pytest.approx(3.0)


@pytest.mark.unit
def test_inspect_power_plants_with_capacity_and_fuel():
    df = pd.DataFrame(
        {
            "Capacity_MW": [10.0, 5.0, 20.0],
            "Primary_Fuel": ["Solar", "Wind", "Solar"],
        }
    )

    result = inspect_power_plants(df)

    assert result["total_plants"] == 3
    assert result["total_capacity_mw"] == pytest.approx(35.0)
    assert result["by_fuel"]["Solar"] == pytest.approx(30.0)
    assert result["by_fuel"]["Wind"] == pytest.approx(5.0)


@pytest.mark.unit
def test_inspect_power_plants_empty_dataframe_returns_error():
    result = inspect_power_plants(pd.DataFrame())

    assert result["error"] is not None
    assert result["total_plants"] == 0


@pytest.mark.unit
def test_inspect_power_plants_none_returns_error():
    result = inspect_power_plants(None)

    assert result["error"] is not None


@pytest.mark.unit
def test_diagnose_consistency_flags_divergent_crs():
    raster_meta = {
        "solar": {"crs": "EPSG:4326", "resolution": 0.0083, "error": None},
        "elevation": {"crs": "EPSG:3857", "resolution": 0.005, "error": None},
    }

    alerts, not_audited = diagnose_consistency(raster_meta, {}, 0.5)

    assert any("DIVERGENT CRS" in a for a in alerts)
    assert not_audited == {}


@pytest.mark.unit
def test_diagnose_consistency_flags_unexpected_resolution():
    raster_meta = {"solar": {"crs": "EPSG:4326", "resolution": 0.05, "error": None}}

    alerts, not_audited = diagnose_consistency(raster_meta, {"solar": 0.0083}, 0.5)

    assert any("UNEXPECTED RESOLUTION" in a for a in alerts)
    assert not_audited == {}


@pytest.mark.unit
def test_diagnose_consistency_no_alerts_when_consistent():
    raster_meta = {"solar": {"crs": "EPSG:4326", "resolution": 0.0083, "error": None}}

    alerts, not_audited = diagnose_consistency(raster_meta, {"solar": 0.0083}, 0.5)

    assert alerts == []
    assert not_audited == {}


@pytest.mark.unit
def test_diagnose_consistency_reports_not_audited_for_null_expectation():
    raster_meta = {"slope": {"crs": "EPSG:4326", "resolution": 0.005, "error": None}}

    alerts, not_audited = diagnose_consistency(raster_meta, {"slope": None}, 0.5)

    assert alerts == []
    assert "slope" in not_audited


# ===========================================================================
# inspect_land_cover_tiles — previously 0% covered (l.359-465, the single
# largest gap in this module). Read in full before writing any of these:
# it aggregates ESA WorldCover class areas across possibly many tiles,
# masked to the real country polygon, scanning each tile in 8192x8192
# windows (real WorldCover 10m tiles routinely exceed that in both
# dimensions) to bound memory use.
# ===========================================================================


@pytest.mark.unit
def test_inspect_land_cover_tiles_without_country_gdf_returns_error():
    result = inspect_land_cover_tiles([Path("unused.tif")], country_gdf=None)

    assert result == {"error": "country_gdf required for tile analysis"}


@pytest.mark.unit
def test_inspect_land_cover_tiles_skips_tiles_outside_country_bbox(tmp_path):
    near_path = tmp_path / "tile_near.tif"
    _write_raster(near_path, np.full((_SIZE, _SIZE), 10, dtype=np.uint8))  # Tree cover

    far_path = tmp_path / "tile_far.tif"
    _write_raster_at(
        far_path,
        np.full((5, 5), 40, dtype=np.uint8),
        origin_lon=50.0,
        origin_lat=10.0,
        res=0.01,
    )

    result = inspect_land_cover_tiles([near_path, far_path], country_gdf=_covering_gdf())

    assert result["n_tiles"] == 2
    assert result["tiles_used"] == 1
    assert result["tiles_skipped"] == 1
    assert 10 in result["class_stats"]
    assert 40 not in result["class_stats"]


@pytest.mark.unit
def test_inspect_land_cover_tiles_skips_tile_when_bbox_overlaps_but_polygon_does_not(
    tmp_path,
):
    # A country's bounding box (rectangle) is not the country itself —
    # the coarse bbox pre-check (cheap, runs first) can pass while the
    # real polygon intersection (below it) is empty. Any non-rectangular
    # country hits this in practice; a triangle is the simplest example.
    triangle = Polygon([(0.0, 2.0), (2.0, 2.0), (0.0, 0.0)])  # covers y >= x only
    country_gdf = gpd.GeoDataFrame(geometry=[triangle], crs="EPSG:4326")

    tile_path = tmp_path / "tile_outside_triangle.tif"
    _write_raster_at(
        tile_path,
        np.full((10, 10), 10, dtype=np.uint8),
        origin_lon=1.5,
        origin_lat=0.5,
        res=0.01,
    )
    # tile spans lon[1.5,1.6] x lat[0.4,0.5]: inside the triangle's (0,0)-
    # (2,2) bounding box, but entirely below the y=x line (outside it).

    result = inspect_land_cover_tiles([tile_path], country_gdf=country_gdf)

    assert result["tiles_used"] == 0
    assert result["tiles_skipped"] == 1


@pytest.mark.unit
def test_inspect_land_cover_tiles_aggregates_class_areas_across_tiles(tmp_path):
    tile_a = tmp_path / "tile_a.tif"
    _write_raster(tile_a, np.full((_SIZE, _SIZE), 10, dtype=np.uint8))  # Tree cover

    tile_b = tmp_path / "tile_b.tif"
    _write_raster_at(
        tile_b,
        np.full((_SIZE, _SIZE), 40, dtype=np.uint8),  # Cropland
        origin_lon=_ORIGIN_LON,
        origin_lat=_ORIGIN_LAT - _SIZE * _RES,
        res=_RES,
    )  # directly south of tile_a, like two adjacent real WorldCover tiles

    country_gdf = gpd.GeoDataFrame(
        geometry=[
            box(
                _ORIGIN_LON,
                _ORIGIN_LAT - 2 * _SIZE * _RES,
                _ORIGIN_LON + _SIZE * _RES,
                _ORIGIN_LAT,
            )
        ],
        crs="EPSG:4326",
    )

    result = inspect_land_cover_tiles([tile_a, tile_b], country_gdf=country_gdf)

    assert result["tiles_used"] == 2
    assert result["class_stats"][10]["name"] == "Tree cover"
    assert result["class_stats"][40]["name"] == "Cropland"
    assert result["class_stats"][10]["pct"] == pytest.approx(50.0, abs=1.0)
    assert result["class_stats"][40]["pct"] == pytest.approx(50.0, abs=1.0)
    assert result["total_area_km2"] > 0


@pytest.mark.unit
def test_inspect_land_cover_tiles_reuses_cached_tile_without_reopening_it(tmp_path, monkeypatch):
    # Real incident, 2026-09-22: a BRA run was interrupted partway
    # through 112 tiles with no per-tile persistence, forcing a full
    # restart. cache_dir lets a resumed run skip tiles already scored —
    # verified here by spying on rasterio.open, not just by the result.
    tile = tmp_path / "tile.tif"
    _write_raster(tile, np.full((_SIZE, _SIZE), 10, dtype=np.uint8))  # Tree cover
    country_gdf = _covering_gdf()
    cache_dir = tmp_path / "cache"

    first = inspect_land_cover_tiles([tile], country_gdf=country_gdf, cache_dir=cache_dir)
    assert first["tiles_used"] == 1
    assert (cache_dir / f"{tile.stem}.json").exists()

    opened: list[str] = []
    real_open = rasterio.open

    def _spy_open(path, *args, **kwargs):
        opened.append(str(path))
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(
        "geofrea.data_quality_audit.raster_inspection.rasterio.open", _spy_open
    )

    second = inspect_land_cover_tiles([tile], country_gdf=country_gdf, cache_dir=cache_dir)

    assert opened == []  # the cached tile was never reopened
    assert second["tiles_used"] == 1
    assert second["errors"] == []
    assert second["class_stats"] == first["class_stats"]


@pytest.mark.unit
def test_inspect_land_cover_tiles_invalidates_cache_when_tile_changes(tmp_path):
    tile = tmp_path / "tile.tif"
    _write_raster(tile, np.full((_SIZE, _SIZE), 10, dtype=np.uint8))  # Tree cover
    country_gdf = _covering_gdf()
    cache_dir = tmp_path / "cache"

    inspect_land_cover_tiles([tile], country_gdf=country_gdf, cache_dir=cache_dir)

    # Overwrite with different data and a fresh mtime — the cache entry
    # keyed by the old mtime/size must not be reused.
    _write_raster(tile, np.full((_SIZE, _SIZE), 40, dtype=np.uint8))  # Cropland

    result = inspect_land_cover_tiles([tile], country_gdf=country_gdf, cache_dir=cache_dir)

    assert result["class_stats"][40]["name"] == "Cropland"
    assert 10 not in result["class_stats"]


@pytest.mark.unit
def test_inspect_land_cover_tiles_without_cache_dir_recomputes_every_time(tmp_path):
    tile = tmp_path / "tile.tif"
    _write_raster(tile, np.full((_SIZE, _SIZE), 10, dtype=np.uint8))

    result = inspect_land_cover_tiles([tile], country_gdf=_covering_gdf())

    assert result["tiles_used"] == 1
    assert not (tmp_path / "cache").exists()


@pytest.mark.unit
def test_inspect_land_cover_tiles_skips_block_with_no_positive_pixels(tmp_path):
    # ESA WorldCover uses 0 as its own "no data" value (not a declared
    # GeoTIFF nodata tag) — an all-zero tile is a real no-data/water-only
    # corner tile, not a fabricated case.
    tile_path = tmp_path / "tile_all_zero.tif"
    _write_raster(tile_path, np.zeros((_SIZE, _SIZE), dtype=np.uint8))

    result = inspect_land_cover_tiles([tile_path], country_gdf=_covering_gdf())

    assert result["tiles_used"] == 1
    assert result["class_stats"] == {}
    assert result["total_area_km2"] == 0.0


@pytest.mark.unit
def test_inspect_land_cover_tiles_skips_block_whose_positive_pixels_lie_outside_polygon(
    tmp_path,
):
    data = np.zeros((_SIZE, _SIZE), dtype=np.uint8)
    data[:5, :5] = 10  # positive data confined to the tile's NW quadrant
    tile_path = tmp_path / "tile_offset_data.tif"
    _write_raster(tile_path, data)

    # Country polygon covers only the tile's SE quadrant: the tile-level
    # bbox/polygon checks pass (non-empty intersection), but no data > 0
    # pixel falls inside the country polygon itself.
    se_quadrant = box(
        _ORIGIN_LON + 5 * _RES,
        _ORIGIN_LAT - 10 * _RES,
        _ORIGIN_LON + 10 * _RES,
        _ORIGIN_LAT - 5 * _RES,
    )
    country_gdf = gpd.GeoDataFrame(geometry=[se_quadrant], crs="EPSG:4326")

    result = inspect_land_cover_tiles([tile_path], country_gdf=country_gdf)

    assert result["tiles_used"] == 1
    assert result["class_stats"] == {}
    assert result["total_area_km2"] == 0.0


@pytest.mark.unit
def test_inspect_land_cover_tiles_skips_window_outside_polygon_in_a_multi_window_tile(
    tmp_path,
):
    # The function scans each tile in 8192x8192-pixel windows. Real
    # WorldCover 10m tiles are routinely far larger than that in both
    # dimensions, so a country covering only part of a tile skips whole
    # windows early (l.416-417) rather than reading+masking them. A
    # 2-row-tall strip wider than one window step keeps this test cheap
    # while still producing two real windows.
    step = 8192
    width = step + 8
    res = 0.0001
    data = np.zeros((2, width), dtype=np.uint8)
    data[:, :step] = 10  # Tree cover — first window
    data[:, step:] = 40  # Cropland — second window
    tile_path = tmp_path / "tile_wide.tif"
    _write_raster_at(tile_path, data, origin_lon=-9.0, origin_lat=39.0, res=res)

    # Country covers only the first window's extent, with a wide safety
    # margin clear of the window boundary (avoids float-precision flake).
    country_gdf = gpd.GeoDataFrame(
        geometry=[box(-9.0, 39.0 - 2 * res, -9.0 + 8000 * res, 39.0)],
        crs="EPSG:4326",
    )

    result = inspect_land_cover_tiles([tile_path], country_gdf=country_gdf)

    assert 10 in result["class_stats"]
    assert 40 not in result["class_stats"]


@pytest.mark.unit
def test_inspect_land_cover_tiles_updates_progress_bar_status_when_tqdm_available(
    tmp_path, monkeypatch
):
    # tqdm is a soft dependency — NOT installed in this project's own
    # venv (confirmed by the fallback test below, which is why this
    # branch is otherwise unreachable here). When a real tqdm-like object
    # IS present (e.g. a dev's interactive environment per this module's
    # own docstring), it should get a per-tile status message. Stubbed
    # with a minimal object exposing the one method this code calls,
    # rather than adding tqdm as a hard test dependency.
    calls: list[dict] = []

    class _FakePbar(list):
        def set_postfix(self, info):
            calls.append(info)

    monkeypatch.setattr(raster_inspection, "tqdm", lambda iterable, **kw: _FakePbar(iterable))

    tile_path = tmp_path / "tile.tif"
    _write_raster(tile_path, np.full((_SIZE, _SIZE), 10, dtype=np.uint8))

    inspect_land_cover_tiles([tile_path], country_gdf=_covering_gdf())

    assert calls == [{"status": tile_path.name[-20:]}]


@pytest.mark.unit
def test_inspect_land_cover_tiles_continues_after_one_corrupt_tile(tmp_path):
    bad_path = tmp_path / "tile_corrupt.tif"
    bad_path.write_bytes(b"not a real geotiff")

    good_path = tmp_path / "tile_good.tif"
    _write_raster(good_path, np.full((_SIZE, _SIZE), 10, dtype=np.uint8))

    result = inspect_land_cover_tiles([bad_path, good_path], country_gdf=_covering_gdf())

    assert result["tiles_used"] == 1
    assert len(result["errors"]) == 1
    assert "tile_corrupt.tif" in result["errors"][0]
    assert 10 in result["class_stats"]


@pytest.mark.unit
def test_inspect_land_cover_tiles_warns_when_no_tile_overlaps(tmp_path, caplog):
    far_path = tmp_path / "tile_far.tif"
    _write_raster_at(
        far_path,
        np.full((5, 5), 10, dtype=np.uint8),
        origin_lon=50.0,
        origin_lat=10.0,
        res=0.01,
    )

    with caplog.at_level(
        logging.WARNING, logger="geofrea.data_quality_audit.raster_inspection"
    ):
        result = inspect_land_cover_tiles([far_path], country_gdf=_covering_gdf())

    assert result["tiles_used"] == 0
    assert result["tiles_skipped"] == 1
    assert result["class_stats"] == {}
    assert any("No tile overlapped" in rec.message for rec in caplog.records)


# ===========================================================================
# _stats_chunked — the chunked-read fallback for rasters too large to
# mask in one windowed read (previously 0% covered, l.163-234).
# ===========================================================================


@pytest.mark.unit
def test_stats_chunked_matches_expected_stats_across_multiple_chunks(tmp_path, monkeypatch):
    data = np.arange(40, dtype=np.float32).reshape(10, 4)
    data[3, 2] = -9999.0  # one nodata pixel, inside an interior chunk once forced below
    path = tmp_path / "chunked.tif"
    _write_raster(path, data, nodata=-9999.0)

    monkeypatch.setattr(raster_inspection, "_CHUNK_ROWS", 3)  # forces 4 chunks over 10 rows

    country_gdf = gpd.GeoDataFrame(
        geometry=[
            box(_ORIGIN_LON, _ORIGIN_LAT - 10 * _RES, _ORIGIN_LON + 4 * _RES, _ORIGIN_LAT)
        ],
        crs="EPSG:4326",
    )

    with rasterio.open(path) as src:
        stats, transform = _stats_chunked(src, country_gdf)

    expected = data[data != -9999.0]
    assert stats["min"] == pytest.approx(float(expected.min()))
    assert stats["max"] == pytest.approx(float(expected.max()))
    assert stats["mean"] == pytest.approx(float(expected.mean()), rel=1e-4)
    assert stats["valid_px"] == 39
    assert stats["total_px"] == 40
    assert stats["area_km2"] > 0
    assert transform is not None


@pytest.mark.unit
def test_stats_chunked_returns_zero_stats_when_polygon_does_not_overlap(tmp_path):
    # total_px == 0 here, not _SIZE * _SIZE — changed 2026-09-08 (see
    # docs/DECISIONS.md same date and _stats_chunked()'s own docstring,
    # "total_px scoping fixed"): total_px now reflects the country-bbox
    # window's own pixel count (zero, since there is no overlap at all),
    # not the full raster's, matching _mask_raster_by_polygon()'s
    # scoping. No end-user-visible effect either way — inspect_raster()
    # already guards valid_pct with `if total_px > 0 else 0.0`, so both
    # the old (100) and new (0) denominators produced the same 0.0%.
    data = np.ones((_SIZE, _SIZE), dtype=np.float32)
    path = tmp_path / "no_overlap.tif"
    _write_raster(path, data)

    far_gdf = gpd.GeoDataFrame(geometry=[box(100.0, 100.0, 101.0, 101.0)], crs="EPSG:4326")

    with rasterio.open(path) as src:
        stats, transform = _stats_chunked(src, far_gdf)

    assert stats == {
        "min": None,
        "max": None,
        "mean": None,
        "valid_px": 0,
        "total_px": 0,
        "area_km2": 0.0,
    }
    assert transform is not None


@pytest.mark.unit
def test_stats_chunked_total_px_scoped_to_country_window_not_full_raster(tmp_path, monkeypatch):
    # The real bug (see docs/DECISIONS.md 2026-09-08 and
    # _stats_chunked()'s own docstring, "total_px scoping fixed"): a
    # raster file bigger than the country's own bbox used to make
    # total_px (and therefore valid_pct) reflect the WHOLE file, not
    # just the country-relevant window — live-verified via BRA
    # population (45.8% windowed vs 39.7% chunked for the exact same
    # data). Reproduced here at unit scale: a 20x20 raster where the
    # country_gdf only covers the top-left 10x10 quadrant.
    big_size = 20
    data = np.ones((big_size, big_size), dtype=np.float32)
    path = tmp_path / "bigger_than_country.tif"
    _write_raster(path, data)

    # Forces _stats_chunked (not the windowed path) regardless of size —
    # this test is about total_px scoping, not the memory-budget guard.
    monkeypatch.setattr(raster_inspection, "_CHUNK_ROWS", 4)

    quadrant_gdf = gpd.GeoDataFrame(
        geometry=[
            box(
                _ORIGIN_LON,
                _ORIGIN_LAT - _SIZE * _RES,
                _ORIGIN_LON + _SIZE * _RES,
                _ORIGIN_LAT,
            )
        ],
        crs="EPSG:4326",
    )

    with rasterio.open(path) as src:
        stats, _transform = _stats_chunked(src, quadrant_gdf)

    # Country window is _SIZE x _SIZE (100 px), NOT big_size x big_size
    # (400 px) — the whole point of this fix.
    assert stats["total_px"] == _SIZE * _SIZE
    assert stats["valid_px"] == _SIZE * _SIZE


@pytest.mark.unit
def test_stats_chunked_returns_none_when_country_gdf_has_no_crs(tmp_path):
    # A boundary layer read without its .prj sidecar has crs=None — a
    # real, observed data-quality failure mode (see adapter.py's own
    # docstring on its two undefended loaders), not invented for this test.
    data = np.ones((_SIZE, _SIZE), dtype=np.float32)
    path = tmp_path / "raster.tif"
    _write_raster(path, data)

    naive_gdf = gpd.GeoDataFrame(geometry=[box(0, 0, 1, 1)])  # no crs set

    with rasterio.open(path) as src:
        stats, transform = _stats_chunked(src, naive_gdf)

    assert stats is None
    assert transform is None


# ===========================================================================
# _country_window — single source of truth for the country-bbox window,
# extracted 2026-09-08 (see docs/DECISIONS.md same date) after
# _mask_raster_by_polygon() and _stats_chunked() were found to have
# silently diverged on this exact computation (the total_px bug above).
# ===========================================================================


@pytest.mark.unit
def test_country_window_matches_country_bbox(tmp_path):
    path = tmp_path / "window.tif"
    _write_raster(path, np.ones((_SIZE, _SIZE), dtype=np.float32))

    # Top-left half of the raster only.
    half_gdf = gpd.GeoDataFrame(
        geometry=[
            box(_ORIGIN_LON, _ORIGIN_LAT - 5 * _RES, _ORIGIN_LON + 10 * _RES, _ORIGIN_LAT)
        ],
        crs="EPSG:4326",
    )

    with rasterio.open(path) as src:
        bounds = half_gdf.to_crs(src.crs).total_bounds
        window = _country_window(bounds, src.transform, src.width, src.height)

    assert round(window.col_off) == 0
    assert round(window.row_off) == 0
    assert round(window.width) == 10
    assert round(window.height) == 5


@pytest.mark.unit
def test_country_window_raises_windowerror_when_no_overlap(tmp_path):
    path = tmp_path / "window_no_overlap.tif"
    _write_raster(path, np.ones((_SIZE, _SIZE), dtype=np.float32))

    far_gdf = gpd.GeoDataFrame(geometry=[box(100.0, 100.0, 101.0, 101.0)], crs="EPSG:4326")

    with rasterio.open(path) as src:
        bounds = far_gdf.to_crs(src.crs).total_bounds
        with pytest.raises(WindowError):
            _country_window(bounds, src.transform, src.width, src.height)


# ===========================================================================
# _mask_raster_by_polygon — the proactive window-size budget check added
# 2026-09-08 after a real near-OOM incident (see raster_inspection.py's
# _WINDOWED_READ_MAX_BYTES docstring: free system RAM dropped to 0.14 GB
# of 15.84 GB reading population/BRA's real ~8.8 GB window). Verified
# with a REAL (not mocked) MemoryError this time — lowering the budget
# via monkeypatch makes even this file's tiny 10x10 synthetic raster
# exceed it, without needing a multi-GB fixture.
# ===========================================================================


@pytest.mark.unit
def test_mask_raster_by_polygon_raises_memory_error_when_window_exceeds_budget(
    tmp_path, monkeypatch
):
    data = np.ones((_SIZE, _SIZE), dtype=np.float32)
    path = tmp_path / "budget.tif"
    _write_raster(path, data)

    # _SIZE*_SIZE*4 bytes = 400 bytes for the real fixture above — set
    # the budget just under that so the real estimate trips it for
    # real, not simulated.
    monkeypatch.setattr(raster_inspection, "_WINDOWED_READ_MAX_BYTES", 399)

    with rasterio.open(path) as src, pytest.raises(MemoryError, match="Windowed read would allocate"):
        _mask_raster_by_polygon(src, _covering_gdf())


@pytest.mark.unit
def test_mask_raster_by_polygon_reads_normally_under_budget(tmp_path):
    # Sanity check the check itself doesn't false-positive at the
    # library's real default budget (_WINDOWED_READ_MAX_BYTES,
    # untouched here) for an ordinary small raster.
    data = np.arange(_SIZE * _SIZE, dtype=np.float32).reshape(_SIZE, _SIZE)
    path = tmp_path / "under_budget.tif"
    _write_raster(path, data)

    with rasterio.open(path) as src:
        result_data, transform = _mask_raster_by_polygon(src, _covering_gdf())

    assert result_data.shape == (_SIZE, _SIZE)
    assert transform is not None


@pytest.mark.unit
def test_mask_raster_by_polygon_propagates_windowerror_when_no_overlap(tmp_path):
    # Locks in the DOCUMENTED policy (see this function's own
    # docstring, 2026-09-08): unlike _stats_chunked(), which treats a
    # non-overlapping country/raster pairing as a legitimate empty
    # result, this function lets WindowError propagate — the caller,
    # inspect_raster(), surfaces it via result["error"], same as a
    # corrupt file. A future edit that silently swallowed this instead
    # (e.g. while "simplifying" _country_window() error handling) would
    # break this test, not just this docstring.
    data = np.ones((_SIZE, _SIZE), dtype=np.float32)
    path = tmp_path / "no_overlap.tif"
    _write_raster(path, data)

    far_gdf = gpd.GeoDataFrame(geometry=[box(100.0, 100.0, 101.0, 101.0)], crs="EPSG:4326")

    with rasterio.open(path) as src, pytest.raises(WindowError):
        _mask_raster_by_polygon(src, far_gdf)


# ===========================================================================
# inspect_raster — the MemoryError -> chunked-read fallback wiring
# (previously 0% covered, l.278-306), plus the smaller uncovered branches
# in its non-fallback path (l.318, l.334-335).
# ===========================================================================


@pytest.mark.unit
def test_inspect_raster_falls_back_to_chunked_stats_on_memory_error(tmp_path, monkeypatch):
    # The documented real trigger is a multi-GB WorldPop tile
    # (_stats_chunked's own docstring); this test exercises the
    # fallback WIRING generically with a mocked trigger — the dedicated
    # test above verifies the real, unmocked trigger itself.
    data = np.arange(_SIZE * _SIZE, dtype=np.float32).reshape(_SIZE, _SIZE)
    path = tmp_path / "large.tif"
    _write_raster(path, data)

    def _raise_memory_error(*_args, **_kwargs):
        raise MemoryError("simulated: windowed read too large")

    monkeypatch.setattr(raster_inspection, "_mask_raster_by_polygon", _raise_memory_error)

    result = inspect_raster(path, country_gdf=_covering_gdf())

    assert result["error"] is None
    assert result["masked_by"] == "country polygon (chunked)"
    assert result["analysis_shape"] == (_SIZE, _SIZE)
    assert result["min"] == pytest.approx(0.0)
    assert result["max"] == pytest.approx(99.0)
    assert result["mean"] == pytest.approx(49.5)
    assert result["valid_pct"] == pytest.approx(100.0)
    assert result["area_km2"] > 0


@pytest.mark.unit
def test_inspect_raster_reports_error_when_both_strategies_fail(tmp_path, monkeypatch):
    data = np.ones((_SIZE, _SIZE), dtype=np.float32)
    path = tmp_path / "unreadable_by_both.tif"
    _write_raster(path, data)

    def _raise_memory_error(*_args, **_kwargs):
        raise MemoryError("simulated")

    monkeypatch.setattr(raster_inspection, "_mask_raster_by_polygon", _raise_memory_error)
    monkeypatch.setattr(raster_inspection, "_stats_chunked", lambda *_a, **_k: (None, None))

    result = inspect_raster(path, country_gdf=_covering_gdf())

    assert result["error"] == (
        "Failed to process raster (both windowed and chunked strategies failed)"
    )


@pytest.mark.unit
def test_inspect_raster_applies_declared_nodata_distinct_from_mask_fill(tmp_path):
    # MASK_FILL (-9999.0) is this module's own internal sentinel; real
    # rasters commonly declare a different one — -32768 is the classic
    # Int16 DEM sentinel — and both must be excluded from stats.
    data = np.full((_SIZE, _SIZE), 10.0, dtype=np.float32)
    data[0, :] = -32768.0
    path = tmp_path / "declared_nodata.tif"
    _write_raster(path, data, nodata=-32768.0)

    result = inspect_raster(path, country_gdf=_covering_gdf())

    assert result["error"] is None
    assert result["mean"] == pytest.approx(10.0)
    assert result["valid_pct"] < 100.0


@pytest.mark.unit
def test_inspect_raster_reports_missing_crs_error_with_no_reference_given(tmp_path):
    # combined-Weibull-A/k ship with no embedded CRS at all (D-F1b-005) —
    # reachable from inspect_raster() whenever country_gdf is given but
    # assume_crs_from is not: _effective_crs() raises
    # MissingCrsWithNoReferenceError, caught by inspect_raster()'s own
    # broad except and surfaced as result["error"], never a silent
    # default CRS.
    data = np.ones((_SIZE, _SIZE), dtype=np.float32)
    path = tmp_path / "no_crs.tif"
    _write_raster_no_crs(path, data)

    result = inspect_raster(path, country_gdf=_covering_gdf())

    assert result["error"] is not None
    assert "no embedded CRS" in result["error"]
    assert "no reference file was given" in result["error"]


@pytest.mark.unit
def test_inspect_raster_reports_crs_assumption_mismatch_error(tmp_path):
    # A reference file is given (assume_crs_from) but its grid does not
    # match the CRS-less file exactly — assigning its CRS anyway would be
    # an unverified guess, so inspect_raster() must fail loud instead
    # (CrsAssumptionMismatchError), not silently borrow a mismatched CRS.
    data = np.ones((_SIZE, _SIZE), dtype=np.float32)
    path = tmp_path / "no_crs.tif"
    _write_raster_no_crs(path, data)

    reference_path = tmp_path / "reference.tif"
    _write_raster_at(
        reference_path,
        data,
        origin_lon=_ORIGIN_LON + 5.0,  # different grid entirely
        origin_lat=_ORIGIN_LAT,
        res=_RES,
    )

    result = inspect_raster(path, country_gdf=_covering_gdf(), assume_crs_from=reference_path)

    assert result["error"] is not None
    assert "does not confirm a matching grid" in result["error"]
    assert "refusing to assume a CRS from it" in result["error"]


@pytest.mark.unit
def test_inspect_raster_reports_zero_stats_when_every_pixel_is_masked(tmp_path):
    # Real case: an elevation tile for an all-offshore country segment,
    # where every analysis-window pixel is nodata.
    data = np.full((_SIZE, _SIZE), MASK_FILL, dtype=np.float32)
    path = tmp_path / "all_masked.tif"
    _write_raster(path, data)  # no declared nodata tag — MASK_FILL used directly

    result = inspect_raster(path, country_gdf=_covering_gdf())

    assert result["error"] is None
    assert result["valid_pct"] == 0.0
    assert result["area_km2"] == 0.0
    assert result["min"] is None
    assert result["max"] is None


# ===========================================================================
# _nodata_mask — the three defensive early-returns for malformed nodata
# metadata (previously uncovered: l.76-77, l.80, l.86).
# ===========================================================================


@pytest.mark.unit
def test_nodata_mask_falls_back_to_finite_when_nodata_is_not_numeric():
    data = np.array([1.0, np.nan, 3.0], dtype=np.float32)

    assert list(_nodata_mask(data, "not-a-number")) == [True, False, True]


@pytest.mark.unit
def test_nodata_mask_falls_back_to_finite_when_nodata_is_infinite():
    data = np.array([1.0, np.nan, 3.0], dtype=np.float32)

    assert list(_nodata_mask(data, math.inf)) == [True, False, True]


@pytest.mark.unit
def test_nodata_mask_falls_back_to_finite_when_nodata_overflows_dtype():
    # A nodata sentinel that overflows the raster's own dtype on cast
    # (e.g. a huge sentinel in a float16-stored raster) becomes +/-inf —
    # must not then be silently treated as a valid data value.
    data = np.array([1.0, 2.0, 3.0], dtype=np.float16)

    assert list(_nodata_mask(data, 1e10)) == [True, True, True]


# ===========================================================================
# inspect_power_plants — malformed-input error branch (l.517-518).
# ===========================================================================


@pytest.mark.unit
def test_inspect_power_plants_reports_error_for_malformed_columns():
    # A CSV with a blank/duplicate header cell gets an integer column
    # label from pandas (e.g. an "Unnamed: N" column renumbered to N) —
    # a real malformed-source-file failure mode. .strip() on that integer
    # label raises AttributeError, caught by this function's own
    # exception handler.
    df = pd.DataFrame({"Capacity_MW": [10.0, 5.0], 0: ["x", "y"]})

    result = inspect_power_plants(df)

    assert result["error"] is not None


# ===========================================================================
# tqdm soft-dependency fallback (l.41-42) — tqdm is optional; if it's ever
# missing from the environment, iteration must still work without a
# progress bar.
# ===========================================================================


@pytest.mark.unit
def test_tqdm_fallback_passes_iterable_through_when_tqdm_is_missing(monkeypatch):
    # Simulates tqdm being uninstalled by making it resolve to None in
    # sys.modules (the standard technique for forcing ImportError), then
    # reloads this module so its own `try: from tqdm import tqdm` re-runs
    # and falls through to the local fallback definition.
    monkeypatch.setitem(sys.modules, "tqdm", None)
    try:
        importlib.reload(raster_inspection)
        assert list(raster_inspection.tqdm([1, 2, 3], desc="x")) == [1, 2, 3]
    finally:
        monkeypatch.undo()
        importlib.reload(raster_inspection)
