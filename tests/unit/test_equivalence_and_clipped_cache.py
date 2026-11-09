"""COMMAND 88, items 2 and 4: the equivalence rule by data type, and the pre-clip of a source raster."""

from __future__ import annotations

import numpy as np
import pytest
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin

from geofrea.core.clipped_cache import clipped_source
from geofrea.core.equivalence import ABS_TOL, REL_TOL, compare_arrays, compare_rasters
from geofrea.grid_alignment.raster_alignment import reproject_to_grid
from tests.unit.test_grid_alignment_raster_alignment import _grid

pytestmark = pytest.mark.unit


# ─── item 4: float within tolerance passes, integers and categories are exact ────────────────────────────────────────────────────────

def test_a_float_within_the_relative_tolerance_passes():
    ref = np.array([1.0, 1000.0, 1e6], dtype=np.float32)
    new = ref * np.float32(1 + 0.5 * REL_TOL)
    result = compare_arrays(ref, new)
    assert result.equivalent and result.kind == "float" and result.max_abs_delta > 0


def test_a_float_beyond_the_tolerance_fails_and_the_largest_difference_is_reported():
    ref = np.array([1.0, 1000.0], dtype=np.float64)
    new = np.array([1.0, 1000.0 * (1 + 3 * REL_TOL)])
    result = compare_arrays(ref, new)
    assert not result.equivalent and result.n_outside == 1 and result.max_rel_delta == pytest.approx(3 * REL_TOL, rel=1e-6)


def test_the_absolute_term_covers_a_reference_of_zero():
    assert compare_arrays(np.array([0.0]), np.array([0.5 * ABS_TOL])).equivalent
    assert not compare_arrays(np.array([0.0]), np.array([2 * ABS_TOL])).equivalent


def test_an_integer_or_categorical_layer_must_be_exactly_equal():
    ref = np.array([1, 2, 3], dtype=np.uint16)
    assert compare_arrays(ref, ref.copy()).equivalent
    result = compare_arrays(ref, np.array([1, 2, 4], dtype=np.uint16))
    assert not result.equivalent and result.kind == "exact" and result.n_outside == 1


def test_a_missing_value_must_be_missing_in_both():
    ref = np.array([1.0, np.nan, -9999.0])
    assert compare_arrays(ref, np.array([1.0, np.nan, -9999.0]), nodata=-9999.0).equivalent
    result = compare_arrays(ref, np.array([1.0, 2.0, -9999.0]), nodata=-9999.0)
    assert not result.equivalent and result.n_missing_mismatch == 1


def test_rasters_are_compared_by_their_dtype_and_must_share_the_grid(tmp_path):
    transform = from_origin(0, 10, 1, 1)
    profile = {"driver": "GTiff", "height": 10, "width": 10, "count": 1, "crs": "EPSG:4326", "transform": transform}
    values = np.linspace(1, 100, 100).reshape(10, 10)
    for name, dtype, array in (("a", "float32", values), ("b", "float32", values * (1 + 1e-7)), ("c", "float32", values * 1.01)):
        with rasterio.open(tmp_path / f"{name}.tif", "w", dtype=dtype, **profile) as dst:
            dst.write(array.astype(dtype), 1)
    assert compare_rasters(tmp_path / "a.tif", tmp_path / "b.tif", rows_per_block=3).equivalent
    assert not compare_rasters(tmp_path / "a.tif", tmp_path / "c.tif").equivalent
    shifted = {**profile, "transform": from_origin(1, 10, 1, 1)}
    with rasterio.open(tmp_path / "d.tif", "w", dtype="float32", **shifted) as dst:
        dst.write(values.astype("float32"), 1)
    assert not compare_rasters(tmp_path / "a.tif", tmp_path / "d.tif").equivalent


# ─── item 2: the pre-clip of a source ────────────────────────────────────────────────────────────────────────────────────────────────

def _world_source(path, res=0.05, nodata=-99999.0):
    """A source far larger than the test grid, so that a clip is worth making."""
    rng = np.random.default_rng(2)
    width, height = int(40 / res), int(30 / res)
    data = rng.uniform(1, 100, (height, width)).astype(np.float32)
    with rasterio.open(
        path, "w", driver="GTiff", height=height, width=width, count=1, dtype="float32", crs="EPSG:4326",
        transform=from_origin(-20, 50, res, res), nodata=nodata,
    ) as dst:  # fmt: skip
        dst.write(data, 1)
    return path


def test_the_clip_is_a_small_file_in_the_cache_named_by_the_source_hash(tmp_path):
    source = _world_source(tmp_path / "world.tif")
    grid = _grid()
    clip = clipped_source(source, grid, directory=tmp_path / "cache")
    assert clip != source and clip.parent == tmp_path / "cache"
    with rasterio.open(source) as s, rasterio.open(clip) as c:
        assert c.width * c.height < 0.1 * s.width * s.height
        assert (c.dtypes, c.nodata, c.crs) == (s.dtypes, s.nodata, s.crs)
    again = clipped_source(source, grid, directory=tmp_path / "cache")
    assert again == clip and clip.stat().st_mtime_ns == again.stat().st_mtime_ns  # found, not made again


def test_another_source_gets_another_clip(tmp_path):
    first = clipped_source(_world_source(tmp_path / "a.tif"), _grid(), directory=tmp_path / "cache")
    other = _world_source(tmp_path / "b.tif")
    with rasterio.open(other, "r+") as dst:
        dst.write(np.zeros((dst.height, dst.width), dtype="float32"), 1)
    assert clipped_source(other, _grid(), directory=tmp_path / "cache") != first


def test_a_source_that_the_window_nearly_covers_is_not_copied(tmp_path):
    grid = _grid()
    left, top = grid.transform * (0, 0)
    right, bottom = grid.transform * (grid.width, grid.height)
    cols, rows = round((right - left + 0.22) / 0.01), round((top - bottom + 0.22) / 0.01)
    tight = tmp_path / "tight.tif"
    with rasterio.open(tight, "w", driver="GTiff", height=rows, width=cols, count=1, dtype="float32", crs="EPSG:4326",
                       transform=from_origin(left - 0.11, top + 0.11, 0.01, 0.01)) as dst:  # fmt: skip
        dst.write(np.ones((rows, cols), dtype="float32"), 1)
    assert clipped_source(tight, grid, directory=tmp_path / "cache") == tight


@pytest.mark.parametrize("resampling", [Resampling.bilinear, Resampling.sum])
def test_warping_the_clip_gives_the_same_raster_as_warping_the_source(tmp_path, resampling):
    source = _world_source(tmp_path / "world.tif", res=0.0125)
    grid = _grid()
    clip = clipped_source(source, grid, directory=tmp_path / "cache")
    assert clip != source
    whole = reproject_to_grid(source, tmp_path / "whole.tif", grid, resampling=resampling)
    clipped = reproject_to_grid(clip, tmp_path / "clipped.tif", grid, resampling=resampling)
    with rasterio.open(whole) as a, rasterio.open(clipped) as b:
        np.testing.assert_array_equal(a.read(), b.read())
