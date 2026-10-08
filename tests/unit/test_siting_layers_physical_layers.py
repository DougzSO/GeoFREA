"""Unit tests for H-4: cost-driver and resource layers keep physical units (M-F2b-02/03/04)."""

from __future__ import annotations

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from geofrea.core.constants import NODATA_FLOAT
from geofrea.grid_alignment.schemas import GridAlignmentResult, GridMetadata
from geofrea.siting_layers import physical_layers as pl

TRANSFORM = from_origin(-9.0, 42.0, 0.01, 0.01)


def _raster(path, values, nodata=None):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        dtype="float32",
        width=values.shape[1],
        height=values.shape[0],
        count=1,
        crs="EPSG:4326",
        transform=TRANSFORM,
        nodata=nodata,
    ) as dst:
        dst.write(values.astype("float32"), 1)
    return path


def _result(tmp_path, drop=None):
    base = np.array([[1.0, 250.0], [3.5, 400.0]])  # 250 and 400 km: beyond any cap, must survive
    wind = {}
    for h in pl.WIND_HEIGHTS_M:
        for product in ("weibull_a", "weibull_k", "air_density"):
            if f"{product}_{h}m" != drop:
                wind[f"{product}_{h}m"] = _raster(tmp_path / f"{product}_{h}.tif", base + h)
    return GridAlignmentResult(
        country_code="PRT",
        timestamp="2026-10-06T00:00:00+00:00",
        grid_metadata=GridMetadata(
            crs="EPSG:4326",
            resolution_deg=0.01,
            width=2,
            height=2,
            transform=(0.01, 0.0, -9.0, 0.0, -0.01, 42.0),
            n_valid_pixels=4,
        ),
        grid=_raster(tmp_path / "grid.tif", base, nodata=-9999.0),
        roads=_raster(tmp_path / "roads.tif", base * 2),
        solar=_raster(tmp_path / "solar.tif", np.array([[4.0, 5.0], [np.nan, 6.0]])),
        wind_layers=wind,
    )


@pytest.mark.unit
def test_every_layer_is_written_with_unchanged_values_and_units(tmp_path):
    out = pl.build_physical_layers(_result(tmp_path), tmp_path / "out")

    assert set(out) == {s.name for s in pl.LAYER_SPECS}
    assert len(out) == 3 + 9
    with rasterio.open(out["dist_grid_km"]) as r:
        np.testing.assert_array_equal(
            r.read(1), [[1.0, 250.0], [3.5, 400.0]]
        )  # raw, uncapped, unscaled
        assert r.tags()["units"] == "km" and r.tags()["normalized"] == "false"
    with rasterio.open(out["weibull_k_150m"]) as r:
        assert r.tags()["units"] == "1"
        assert r.read(1)[0, 0] == pytest.approx(151.0)


@pytest.mark.unit
def test_invalid_pixels_become_nodata_and_nothing_else_changes(tmp_path):
    out = pl.build_physical_layers(_result(tmp_path), tmp_path / "out")
    with rasterio.open(out["pvout_kwh_kwp_day"]) as r:
        data = r.read(1)
        assert r.nodata == NODATA_FLOAT
    assert data[1, 0] == NODATA_FLOAT
    assert data[0, 0] == 4.0 and data[1, 1] == 6.0


@pytest.mark.unit
def test_source_nodata_value_is_mapped_to_the_project_nodata(tmp_path):
    res = _result(tmp_path)
    _raster(res.grid, np.array([[1.0, -9999.0], [3.0, 4.0]]), nodata=-9999.0)
    out = pl.build_physical_layers(res, tmp_path / "out")
    with rasterio.open(out["dist_grid_km"]) as r:
        assert r.read(1)[0, 1] == NODATA_FLOAT


@pytest.mark.unit
def test_missing_required_layer_fails_loud_naming_it(tmp_path):
    with pytest.raises(pl.MissingPhysicalLayerError, match="air_density_200m"):
        pl.build_physical_layers(_result(tmp_path, drop="air_density_200m"), tmp_path / "out")
