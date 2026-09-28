"""Unit tests for geofrea.data_acquisition.fetchers.cmip6.

Network is never touched — every test builds synthetic NetCDF/GeoJSON
fixtures on disk and drives the module's pure functions directly.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pytest
import xarray as xr
from shapely.geometry import box

from geofrea.data_acquisition.fetchers import cmip6


def _write_netcdf(path, lat, lon, variant_label="r1i1p1f1", n_time=12):
    time = np.arange(n_time)
    data = np.random.rand(n_time, len(lat), len(lon))
    ds = xr.Dataset(
        {"tas": (("time", "lat", "lon"), data)},
        coords={"time": time, "lat": lat, "lon": lon},
    )
    ds.attrs["variant_label"] = variant_label
    ds.to_netcdf(path)


@pytest.mark.unit
def test_build_jobs_is_the_full_model_experiment_variable_matrix():
    jobs = cmip6.build_jobs()
    assert len(jobs) == len(cmip6.CMIP6_MODELS) * len(cmip6.CMIP6_EXPERIMENTS) * len(
        cmip6.CMIP6_VARIABLES
    )
    assert cmip6.Cmip6Job(model="gfdl_esm4", experiment="historical", variable="tas") in jobs


@pytest.mark.unit
def test_validate_downloaded_netcdf_raises_on_empty_time(tmp_path):
    path = tmp_path / "empty_time.nc"
    ds = xr.Dataset(
        {"tas": (("time", "lat", "lon"), np.zeros((0, 2, 2)))},
        coords={"time": np.array([], dtype="int64"), "lat": [0.0, 1.0], "lon": [0.0, 1.0]},
    )
    ds.to_netcdf(path)

    with pytest.raises(OSError, match="'time' dimension is empty"):
        cmip6.validate_downloaded_netcdf(path)


@pytest.mark.unit
def test_validate_downloaded_netcdf_passes_on_a_real_file(tmp_path):
    path = tmp_path / "ok.nc"
    _write_netcdf(path, lat=[0.0, 1.0], lon=[0.0, 1.0])
    cmip6.validate_downloaded_netcdf(path)  # does not raise


@pytest.mark.unit
def test_read_variant_label_never_reads_from_filename(tmp_path):
    path = tmp_path / "totally_unrelated_name.nc"
    _write_netcdf(path, lat=[0.0, 1.0], lon=[0.0, 1.0], variant_label="r2i1p1f1")
    assert cmip6.read_variant_label(path) == "r2i1p1f1"


@pytest.mark.unit
def test_read_variant_label_raises_when_attribute_absent(tmp_path):
    path = tmp_path / "no_label.nc"
    ds = xr.Dataset(
        {"tas": (("time", "lat", "lon"), np.zeros((1, 2, 2)))},
        coords={"time": [0], "lat": [0.0, 1.0], "lon": [0.0, 1.0]},
    )
    ds.to_netcdf(path)
    with pytest.raises(OSError, match="variant_label"):
        cmip6.read_variant_label(path)


@pytest.mark.unit
def test_check_realizations_consistent_passes_when_all_labels_agree():
    labels = {
        "cmip6/gfdl_esm4/historical/tas": "r1i1p1f1",
        "cmip6/gfdl_esm4/historical/rsds": "r1i1p1f1",
        "cmip6/gfdl_esm4/ssp126/tas": "r1i1p1f1",
    }
    assert cmip6.check_realizations_consistent(labels, "gfdl_esm4") == "r1i1p1f1"


@pytest.mark.unit
def test_check_realizations_consistent_raises_on_mismatch_naming_both_labels():
    labels = {
        "cmip6/gfdl_esm4/historical/tas": "r1i1p1f1",
        "cmip6/gfdl_esm4/historical/rsds": "r1i1p1f2",
    }
    with pytest.raises(cmip6.RealizationMismatchError) as exc_info:
        cmip6.check_realizations_consistent(labels, "gfdl_esm4")
    message = str(exc_info.value)
    assert "gfdl_esm4" in message
    assert "r1i1p1f1" in message
    assert "r1i1p1f2" in message


@pytest.mark.unit
def test_read_native_grid_records_resolution_extent_and_cell_count(tmp_path):
    path = tmp_path / "grid.nc"
    lat = np.array([-10.0, -9.0, -8.0, -7.0])
    lon = np.array([0.0, 1.5, 3.0])
    _write_netcdf(path, lat=lat, lon=lon)

    grid = cmip6.read_native_grid(path)

    assert grid.n_lat == 4
    assert grid.n_lon == 3
    assert grid.lat_resolution_deg == pytest.approx(1.0)
    assert grid.lon_resolution_deg == pytest.approx(1.5)
    assert grid.lat_min == pytest.approx(-10.0)
    assert grid.lat_max == pytest.approx(-7.0)


@pytest.mark.unit
def test_read_native_grid_fails_loud_on_degenerate_grid(tmp_path):
    path = tmp_path / "degenerate.nc"
    _write_netcdf(path, lat=[0.0], lon=[0.0, 1.0])
    with pytest.raises(OSError, match="degenerate grid"):
        cmip6.read_native_grid(path)


@pytest.mark.unit
def test_is_complete_download_distinguishes_partial_from_complete(tmp_path):
    final_path = tmp_path / "a.nc"
    tmp_download_path = tmp_path / "a.part.nc"

    assert cmip6.is_complete_download(final_path, tmp_download_path) == "absent"

    tmp_download_path.write_bytes(b"partial-bytes")
    assert cmip6.is_complete_download(final_path, tmp_download_path) == "partial"

    tmp_download_path.rename(final_path)
    assert cmip6.is_complete_download(final_path, tmp_download_path) == "complete"


class _FakeClient:
    """Stand-in for cdsapi.Client(): writes a tiny valid NetCDF to `target`."""

    def __init__(self, lat, lon):
        self.lat = lat
        self.lon = lon
        self.calls = []

    def retrieve(self, dataset, request, target):
        self.calls.append((dataset, dict(request), target))
        _write_netcdf(target, lat=self.lat, lon=self.lon)


@pytest.mark.unit
def test_download_global_writes_to_part_name_then_renames_to_final(tmp_path):
    client = _FakeClient(lat=[0.0, 1.0], lon=[0.0, 1.0])
    job = cmip6.Cmip6Job(model="gfdl_esm4", experiment="historical", variable="tas")

    result = cmip6.download_global(client, job, tmp_path)

    assert result == tmp_path / "gfdl_esm4_historical_tas.nc"
    assert result.exists()
    assert not (tmp_path / "gfdl_esm4_historical_tas.part.nc").exists()
    # requested years match the historical reference climatology (S-05)
    _, request, _ = client.calls[0]
    assert request["year"][0] == "1995"
    assert request["year"][-1] == "2014"


@pytest.mark.unit
def test_download_global_never_registers_an_empty_download(tmp_path, monkeypatch):
    class _EmptyClient:
        def retrieve(self, dataset, request, target):
            open(target, "wb").close()  # zero-byte file, simulating a broken transfer

    job = cmip6.Cmip6Job(model="gfdl_esm4", experiment="historical", variable="tas")
    with pytest.raises(OSError, match="empty file"):
        cmip6.download_global(_EmptyClient(), job, tmp_path)
    assert not (tmp_path / "gfdl_esm4_historical_tas.nc").exists()


@pytest.mark.unit
def test_crop_to_country_polygon_keeps_whole_native_cells_by_polygon(tmp_path):
    # A 4x4 native grid at 1-degree resolution.
    lat = np.array([-2.0, -1.0, 0.0, 1.0])
    lon = np.array([-2.0, -1.0, 0.0, 1.0])
    global_path = tmp_path / "global.nc"
    _write_netcdf(global_path, lat=lat, lon=lon)

    # A synthetic "country" polygon covering exactly the bottom-left 2x2
    # block of cell centers: lat/lon in [-2.5, -0.5].
    polygon_path = tmp_path / "synthetic_country.geojson"
    gpd.GeoDataFrame(geometry=[box(-2.5, -2.5, -0.5, -0.5)], crs="EPSG:4326").to_file(
        polygon_path, driver="GeoJSON"
    )

    out_path = tmp_path / "cropped.nc"
    cells_before, cells_after = cmip6.crop_to_country_polygon(global_path, polygon_path, out_path)

    assert cells_before == 16  # 4x4 native grid, unchanged
    assert cells_after == 4  # exactly the 2x2 block of cell centers inside the polygon

    with xr.open_dataset(out_path) as cropped:
        # Native cell values are preserved verbatim (no interpolation): the
        # trimmed lat/lon axes are a subset of the original coordinates.
        assert set(cropped["lat"].values).issubset(set(lat))
        assert set(cropped["lon"].values).issubset(set(lon))
