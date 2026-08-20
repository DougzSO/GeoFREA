"""Unit tests for geofrea.data_quality_audit.raster_inspection.

inspect_raster/inspect_land_cover_tiles need real georeferenced rasters,
so small synthetic GeoTIFFs are written to tmp_path with rasterio rather
than fabricated dict fixtures — this exercises the actual windowed-read +
polygon-mask + geodetic-area code path, not just its return shape. See
tests/unit/test_audit.py's module docstring for why *real* baseline
geodata (as opposed to synthetic-but-real-format rasters) isn't used.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from geofrea.data_quality_audit.raster_inspection import (
    _nodata_mask,
    diagnose_consistency,
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


def _covering_gdf() -> gpd.GeoDataFrame:
    """Polygon covering the full extent of the synthetic raster above."""
    west, north = _ORIGIN_LON, _ORIGIN_LAT
    east = west + _SIZE * _RES
    south = north - _SIZE * _RES
    return gpd.GeoDataFrame(geometry=[box(west, south, east, north)], crs="EPSG:4326")


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

    alerts = diagnose_consistency(raster_meta, {}, 0.5)

    assert any("DIVERGENT CRS" in a for a in alerts)


@pytest.mark.unit
def test_diagnose_consistency_flags_unexpected_resolution():
    raster_meta = {"solar": {"crs": "EPSG:4326", "resolution": 0.05, "error": None}}

    alerts = diagnose_consistency(raster_meta, {"solar": 0.0083}, 0.5)

    assert any("UNEXPECTED RESOLUTION" in a for a in alerts)


@pytest.mark.unit
def test_diagnose_consistency_no_alerts_when_consistent():
    raster_meta = {"solar": {"crs": "EPSG:4326", "resolution": 0.0083, "error": None}}

    alerts = diagnose_consistency(raster_meta, {"solar": 0.0083}, 0.5)

    assert alerts == []
