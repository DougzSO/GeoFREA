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
def test_safe_raster_write_caller_can_override_compression_and_output_is_a_cog(tmp_path):
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
    ) as dst:
        dst.write(np.ones((3, 3), dtype="float32"), 1)

    with rasterio.open(out_path) as src:
        assert src.profile.get("compress") is None
        assert src.profile.get("tiled") is True  # a COG is always tiled
        assert src.tags(ns="IMAGE_STRUCTURE").get("LAYOUT") == "COG"


@pytest.mark.unit
def test_rasters_are_written_as_cog_with_values_tags_and_nodata_unchanged(tmp_path):
    """A-07: the file is a Cloud Optimized GeoTIFF; values, nodata, tags and georeferencing are those that were written."""
    out_path = tmp_path / "cog.tif"
    transform = from_origin(_ORIGIN_LON, _ORIGIN_LAT, _RES, _RES)
    data = np.arange(60 * 70, dtype="float32").reshape(60, 70)
    data[0, 0] = -9999.0
    with safe_raster_write(
        out_path,
        driver="GTiff",
        height=60,
        width=70,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=-9999.0,
        blockxsize=256,
        blockysize=256,
        predictor=3,
    ) as dst:
        dst.write(data, 1)
        dst.update_tags(layer="x", units="km")

    with rasterio.open(out_path) as src:
        assert src.tags(ns="IMAGE_STRUCTURE").get("LAYOUT") == "COG"
        assert src.profile["compress"] == "lzw"
        assert src.nodata == -9999.0 and src.crs.to_epsg() == 4326 and src.transform == transform
        assert src.tags()["layer"] == "x" and src.tags()["units"] == "km"
        assert np.array_equal(src.read(1), data)
    assert not list(tmp_path.glob("*.writing.tif"))


@pytest.mark.unit
def test_failed_raster_write_leaves_no_partial_file(tmp_path):
    out_path = tmp_path / "bad.tif"
    with (
        pytest.raises(RuntimeError, match="boom"),
        safe_raster_write(
            out_path, driver="GTiff", height=2, width=2, count=1, dtype="float32"
        ) as dst,
    ):
        dst.write(np.ones((2, 2), dtype="float32"), 1)
        raise RuntimeError("boom")
    assert not out_path.exists() and not list(tmp_path.glob("*.writing.tif"))


@pytest.mark.unit
def test_gdal_quiet_is_a_safe_noop_context_manager():
    # Must not raise regardless of whether osgeo bindings are installed
    # in this environment — see module docstring.
    with gdal_quiet():
        pass


@pytest.mark.unit
def test_safe_raster_write_retries_a_transient_permission_denied_then_succeeds(
    tmp_path, monkeypatch
):
    from geofrea.core import raster_io

    real_open, calls = rasterio.open, []

    def flaky(path, mode="r", **kw):
        calls.append(path)
        if len(calls) < 3:
            raise rasterio.errors.RasterioIOError("Deleting x.tif failed: Permission denied")
        return real_open(path, mode, **kw)

    monkeypatch.setattr(raster_io.rasterio, "open", flaky)
    monkeypatch.setattr(raster_io, "_WRITE_RETRY_WAITS_S", (0.0, 0.0, 0.0))
    profile = {"driver": "GTiff", "height": 2, "width": 2, "count": 1, "dtype": "float32"}

    with safe_raster_write(tmp_path / "out.tif", **profile) as dst:
        dst.write(np.ones((2, 2), dtype="float32"), 1)

    assert len(calls) == 3
    assert (tmp_path / "out.tif").exists()


@pytest.mark.unit
def test_safe_raster_write_does_not_retry_other_errors_and_gives_up_after_the_waits(
    tmp_path, monkeypatch
):
    from geofrea.core import raster_io

    attempts = []

    def always(path, mode="r", **kw):
        attempts.append(1)
        raise rasterio.errors.RasterioIOError("Permission denied")

    monkeypatch.setattr(raster_io.rasterio, "open", always)
    monkeypatch.setattr(raster_io, "_WRITE_RETRY_WAITS_S", (0.0, 0.0))
    with (
        pytest.raises(rasterio.errors.RasterioIOError),
        safe_raster_write(tmp_path / "o.tif", driver="GTiff"),
    ):
        pass
    assert len(attempts) == 3  # first try + two retries

    attempts.clear()

    def other(path, mode="r", **kw):
        attempts.append(1)
        raise rasterio.errors.RasterioIOError("no such file")

    monkeypatch.setattr(raster_io.rasterio, "open", other)
    with (
        pytest.raises(rasterio.errors.RasterioIOError),
        safe_raster_write(tmp_path / "o2.tif", driver="GTiff"),
    ):
        pass
    assert len(attempts) == 1
