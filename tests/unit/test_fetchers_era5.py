"""Unit tests for geofrea.data_acquisition.fetchers.era5.

Network is never touched — every test builds synthetic NetCDF/GeoJSON
fixtures on disk and drives the module's pure functions directly, same
convention as test_fetchers_cmip6.py.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import xarray as xr
from shapely.geometry import box

from geofrea.data_acquisition.era5_registry import Era5Registry, Era5RegistryEntry
from geofrea.data_acquisition.fetchers import era5


def _write_daily_netcdf(path, lat, lon, dates):
    """Synthetic daily-maximum field: dims (valid_time, latitude, longitude)."""
    n_time = len(dates)
    data = np.random.rand(n_time, len(lat), len(lon))
    ds = xr.Dataset(
        {"fg10": (("valid_time", "latitude", "longitude"), data)},
        coords={"valid_time": pd.to_datetime(dates), "latitude": lat, "longitude": lon},
    )
    ds.to_netcdf(path)


@pytest.mark.unit
def test_validate_downloaded_netcdf_raises_on_empty_time(tmp_path):
    path = tmp_path / "empty.nc"
    ds = xr.Dataset(
        {"fg10": (("valid_time", "latitude", "longitude"), np.zeros((0, 2, 2)))},
        coords={
            "valid_time": np.array([], dtype="datetime64[ns]"),
            "latitude": [0.0, 1.0],
            "longitude": [0.0, 1.0],
        },
    )
    ds.to_netcdf(path)
    with pytest.raises(OSError, match="'valid_time' dimension is empty"):
        era5.validate_downloaded_netcdf(path)


@pytest.mark.unit
def test_validate_downloaded_netcdf_passes_on_a_real_file(tmp_path):
    path = tmp_path / "ok.nc"
    _write_daily_netcdf(path, lat=[0.0, 1.0], lon=[0.0, 1.0], dates=["2010-01-01", "2010-01-02"])
    era5.validate_downloaded_netcdf(path)  # does not raise


@pytest.mark.unit
def test_read_native_grid_uses_latitude_longitude_names(tmp_path):
    path = tmp_path / "grid.nc"
    lat = np.array([36.0, 36.25, 36.5, 36.75])
    lon = np.array([-9.5, -9.25, -9.0])
    _write_daily_netcdf(path, lat=lat, lon=lon, dates=["2010-01-01"])

    grid = era5.read_native_grid(path)

    assert grid.n_lat == 4
    assert grid.n_lon == 3
    assert grid.lat_resolution_deg == pytest.approx(0.25)
    assert grid.lon_resolution_deg == pytest.approx(0.25)


@pytest.mark.unit
def test_read_native_grid_resolution_survives_gaps_from_polygon_crop(tmp_path):
    path = tmp_path / "gappy.nc"
    # Mainland rows plus a far island row/column: the axis has a 4.5-degree gap.
    lat = np.array([37.0, 36.75, 36.5, 32.0])
    lon = np.array([-28.5, -9.5, -9.25, -9.0])
    _write_daily_netcdf(path, lat=lat, lon=lon, dates=["2010-01-01"])

    grid = era5.read_native_grid(path)

    assert grid.lat_resolution_deg == pytest.approx(0.25)
    assert grid.lon_resolution_deg == pytest.approx(0.25)


@pytest.mark.unit
def test_is_complete_download_distinguishes_partial_from_complete(tmp_path):
    final_path = tmp_path / "a.nc"
    tmp_download_path = tmp_path / "a.part.nc"

    assert era5.is_complete_download(final_path, tmp_download_path) == "absent"
    tmp_download_path.write_bytes(b"partial-bytes")
    assert era5.is_complete_download(final_path, tmp_download_path) == "partial"
    tmp_download_path.rename(final_path)
    assert era5.is_complete_download(final_path, tmp_download_path) == "complete"


class _FakeClient:
    """Stand-in for cdsapi.Client(): writes a tiny valid NetCDF to `target`."""

    def __init__(self, lat, lon, dates):
        self.lat = lat
        self.lon = lon
        self.dates = dates
        self.calls = []

    def retrieve(self, dataset, request, target):
        self.calls.append((dataset, dict(request), target))
        _write_daily_netcdf(target, lat=self.lat, lon=self.lon, dates=self.dates)


@pytest.mark.unit
def test_download_country_bbox_year_writes_to_part_name_then_renames_to_final(tmp_path):
    client = _FakeClient(lat=[0.0, 1.0], lon=[0.0, 1.0], dates=["2010-01-01"])
    job = era5.Era5Job(country="ZZZ")
    bbox = [1.0, -1.0, 0.0, 1.0]

    result = era5.download_country_bbox_year(client, job, 1995, bbox, tmp_path)

    assert result == tmp_path / "ZZZ_fg10_hourly_bbox_1995.nc"
    assert result.exists()
    assert not (tmp_path / "ZZZ_fg10_hourly_bbox_1995.part.nc").exists()
    _, request, _ = client.calls[0]
    assert request["variable"] == "10m_wind_gust_since_previous_post_processing"
    assert len(request["time"]) == 24  # raw hourly, all 24 hours requested
    assert request["area"] == bbox
    assert request["year"] == ["1995"]  # one year per request (action 1 finding)


@pytest.mark.unit
def test_merge_yearly_files_concatenates_along_time(tmp_path):
    year_a = tmp_path / "a.nc"
    year_b = tmp_path / "b.nc"
    _write_daily_netcdf(year_a, lat=[0.0, 1.0], lon=[0.0], dates=["2010-01-01", "2010-01-02"])
    _write_daily_netcdf(year_b, lat=[0.0, 1.0], lon=[0.0], dates=["2011-01-01", "2011-01-02"])

    out_path = tmp_path / "merged.nc"
    era5.merge_yearly_files([year_a, year_b], out_path)

    with xr.open_dataset(out_path) as merged:
        assert merged.sizes["valid_time"] == 4


@pytest.mark.unit
def test_download_country_bbox_year_never_registers_an_empty_download(tmp_path):
    class _EmptyClient:
        def retrieve(self, dataset, request, target):
            open(target, "wb").close()

    job = era5.Era5Job(country="ZZZ")
    with pytest.raises(OSError, match="empty file"):
        era5.download_country_bbox_year(_EmptyClient(), job, 1995, [1.0, -1.0, 0.0, 1.0], tmp_path)
    assert not (tmp_path / "ZZZ_fg10_hourly_bbox_1995.nc").exists()


@pytest.mark.unit
def test_crop_to_country_polygon_keeps_whole_native_cells_by_polygon(tmp_path):
    lat = np.array([-2.0, -1.0, 0.0, 1.0])
    lon = np.array([-2.0, -1.0, 0.0, 1.0])
    bbox_path = tmp_path / "bbox.nc"
    _write_daily_netcdf(bbox_path, lat=lat, lon=lon, dates=["2010-01-01"])

    polygon_path = tmp_path / "synthetic_country.geojson"
    gpd.GeoDataFrame(geometry=[box(-2.5, -2.5, -0.5, -0.5)], crs="EPSG:4326").to_file(
        polygon_path, driver="GeoJSON"
    )

    out_path = tmp_path / "cropped.nc"
    cells_before, cells_after = era5.crop_to_country_polygon(bbox_path, polygon_path, out_path)

    assert cells_before == 16
    assert cells_after == 4

    with xr.open_dataset(out_path) as cropped:
        assert set(cropped["latitude"].values).issubset(set(lat))
        assert set(cropped["longitude"].values).issubset(set(lon))


@pytest.mark.unit
def test_compute_annual_maxima_matches_known_construction(tmp_path):
    """Two cells: one whose maximum falls in a single hour/day (a spike),
    one that is constant — the annual maximum must equal what each cell
    was constructed with, per year, exactly."""
    path = tmp_path / "daily.nc"
    dates = pd.date_range("2010-01-01", "2011-12-31", freq="D")
    lat = np.array([0.0, 1.0])
    lon = np.array([0.0])

    data = np.full((len(dates), 2, 1), 5.0)  # baseline everywhere
    years = dates.year.to_numpy()

    # Cell (lat=0.0): constant 5.0 every day, every year -> annual max == 5.0.
    # Cell (lat=1.0): a single spike of 42.0 on one day in 2010 only.
    spike_idx = np.where((years == 2010) & (dates.dayofyear == 150))[0][0]
    data[spike_idx, 1, 0] = 42.0

    ds = xr.Dataset(
        {"fg10": (("valid_time", "latitude", "longitude"), data)},
        coords={"valid_time": dates, "latitude": lat, "longitude": lon},
    )
    ds.to_netcdf(path)

    annual = era5.compute_annual_maxima(path)

    assert annual.sel(year=2010, latitude=0.0, longitude=0.0).item() == pytest.approx(5.0)
    assert annual.sel(year=2011, latitude=0.0, longitude=0.0).item() == pytest.approx(5.0)
    assert annual.sel(year=2010, latitude=1.0, longitude=0.0).item() == pytest.approx(42.0)
    assert annual.sel(year=2011, latitude=1.0, longitude=0.0).item() == pytest.approx(5.0)


@pytest.mark.unit
def test_compute_daily_maxima_reduces_hourly_to_one_value_per_utc_day(tmp_path):
    path = tmp_path / "hourly.nc"
    hours = pd.date_range("2010-01-01 00:00", "2010-01-02 23:00", freq="h")
    lat = np.array([0.0])
    lon = np.array([0.0])
    data = np.zeros((len(hours), 1, 1))
    # Day 1: values 0..23, max 23. Day 2: a single spike at hour 5.
    data[:24, 0, 0] = np.arange(24)
    data[24:, 0, 0] = 1.0
    data[24 + 5, 0, 0] = 99.0

    ds = xr.Dataset(
        {"fg10": (("valid_time", "latitude", "longitude"), data)},
        coords={"valid_time": hours, "latitude": lat, "longitude": lon},
    )
    ds.to_netcdf(path)

    daily = era5.compute_daily_maxima(path)

    assert daily["fg10"].sizes["valid_time"] == 2
    values = daily["fg10"].isel(latitude=0, longitude=0).values
    assert values[0] == pytest.approx(23.0)
    assert values[1] == pytest.approx(99.0)


@pytest.mark.unit
def test_write_annual_maxima_from_hourly_persists_a_readable_netcdf(tmp_path):
    path = tmp_path / "hourly.nc"
    hours = pd.date_range("2010-01-01 00:00", "2010-01-02 23:00", freq="h")
    _write_daily_netcdf(path, lat=[0.0, 1.0], lon=[0.0], dates=hours)

    out_path = tmp_path / "annual_max.nc"
    era5.write_annual_maxima_from_hourly(path, out_path)

    assert out_path.exists()
    with xr.open_dataset(out_path) as ds:
        assert "fg10" in ds.data_vars
        assert "year" in ds.dims
        assert "spatial_ref" in ds.variables  # CRS written by rio.write_crs()


@pytest.mark.unit
def test_bbox_from_polygon_adds_margin_around_the_real_polygon(tmp_path):
    polygon_path = tmp_path / "country.geojson"
    gpd.GeoDataFrame(geometry=[box(-10.0, 36.0, -6.0, 42.0)], crs="EPSG:4326").to_file(
        polygon_path, driver="GeoJSON"
    )
    north, west, south, east = era5.bbox_from_polygon(polygon_path, margin_deg=0.5)
    assert north == pytest.approx(42.5)
    assert west == pytest.approx(-10.5)
    assert south == pytest.approx(35.5)
    assert east == pytest.approx(-5.5)


@pytest.mark.unit
def test_era5_registry_resume_skip_keyed_by_country(tmp_path):
    """A registered, intact entry is skipped; a missing or corrupted one is not."""
    registry = Era5Registry()
    source_path = tmp_path / "BRA_fg10_daily_max.nc"
    reduced_path = tmp_path / "BRA_fg10_annual_max.nc"
    source_path.write_bytes(b"fake-netcdf-bytes")
    reduced_path.write_bytes(b"fake-reduced-bytes")

    from geofrea.data_acquisition.era5_registry import sha256_file

    registry.entries["era5/BRA/fg10"] = Era5RegistryEntry(
        country_code="BRA",
        status="registered",
        source_path=str(source_path),
        source_sha256=sha256_file(source_path),
        reduced_path=str(reduced_path),
        reduced_sha256=sha256_file(reduced_path),
        reference_period_start=1995,
        reference_period_end=2014,
    )

    assert registry.is_complete("era5/BRA/fg10") is True
    assert registry.is_complete("era5/PRT/fg10") is False  # never attempted

    source_path.write_bytes(b"corrupted-different-bytes")
    assert registry.is_complete("era5/BRA/fg10") is False  # hash no longer matches


@pytest.mark.unit
def test_era5_registry_entry_missing_status_requires_reason():
    with pytest.raises(ValueError, match="missing_reason"):
        Era5RegistryEntry(country_code="BRA", status="missing")


@pytest.mark.unit
def test_era5_registry_entry_registered_status_requires_paths_and_hashes():
    with pytest.raises(ValueError, match="requires source_path"):
        Era5RegistryEntry(country_code="BRA", status="registered")
