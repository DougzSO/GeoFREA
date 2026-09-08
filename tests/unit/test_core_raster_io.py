"""Unit tests for geofrea.core.raster_io."""

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from geofrea.core.raster_io import gdal_quiet, safe_raster_open, safe_raster_write

_ORIGIN_LON, _ORIGIN_LAT = -9.0, 39.0
_RES = 0.01


def _write_plain_raster(path: Path, size: int = 5) -> None:
    transform = from_origin(_ORIGIN_LON, _ORIGIN_LAT, _RES, _RES)
    data = np.arange(size * size, dtype="float32").reshape(size, size)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=size,
        width=size,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=-9999.0,
    ) as dst:
        dst.write(data, 1)


@pytest.mark.unit
def test_safe_raster_open_yields_readable_dataset_and_closes(tmp_path):
    path = tmp_path / "layer.tif"
    _write_plain_raster(path)

    with safe_raster_open(path) as src:
        assert src.closed is False
        data = src.read(1)
        assert data.shape == (5, 5)

    assert src.closed is True


@pytest.mark.unit
def test_safe_raster_open_raises_file_not_found_for_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError), safe_raster_open(tmp_path / "does_not_exist.tif"):
        pass


@pytest.mark.unit
def test_safe_raster_write_creates_parent_directories(tmp_path):
    out_path = tmp_path / "nested" / "dirs" / "out.tif"
    assert not out_path.parent.exists()

    transform = from_origin(_ORIGIN_LON, _ORIGIN_LAT, _RES, _RES)
    with safe_raster_write(
        out_path,
        driver="GTiff",
        height=3,
        width=3,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=-9999.0,
    ) as dst:
        dst.write(np.ones((3, 3), dtype="float32"), 1)

    assert out_path.exists()
    with rasterio.open(out_path) as src:
        assert src.read(1).sum() == 9


@pytest.mark.unit
def test_safe_raster_write_defaults_to_lzw_compression_and_tiling(tmp_path):
    out_path = tmp_path / "out.tif"
    transform = from_origin(_ORIGIN_LON, _ORIGIN_LAT, _RES, _RES)
    with safe_raster_write(
        out_path,
        driver="GTiff",
        height=3,
        width=3,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=-9999.0,
    ) as dst:
        dst.write(np.ones((3, 3), dtype="float32"), 1)

    with rasterio.open(out_path) as src:
        assert src.profile.get("compress") == "lzw"
        assert src.profile.get("tiled") is True


@pytest.mark.unit
def test_safe_raster_write_caller_can_override_defaults(tmp_path):
    out_path = tmp_path / "out.tif"
    transform = from_origin(_ORIGIN_LON, _ORIGIN_LAT, _RES, _RES)
    with safe_raster_write(
        out_path,
        driver="GTiff",
        height=3,
        width=3,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=-9999.0,
        compress="none",
        tiled=False,
    ) as dst:
        dst.write(np.ones((3, 3), dtype="float32"), 1)

    with rasterio.open(out_path) as src:
        assert src.profile.get("compress") is None
        assert src.profile.get("tiled") is False


@pytest.mark.unit
def test_gdal_quiet_is_a_safe_noop_context_manager():
    # Must not raise regardless of whether osgeo bindings are installed
    # in this environment — see module docstring.
    with gdal_quiet():
        pass
