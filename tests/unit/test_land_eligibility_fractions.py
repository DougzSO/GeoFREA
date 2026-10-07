"""Sub-pixel excluded shares (OQ-045 option c): polygon coverage and riparian setback fractions."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pytest
from rasterio.transform import from_origin
from shapely.geometry import LineString, box

from geofrea.land_eligibility.fractions import (
    polygon_coverage_fraction,
    river_fractions,
    river_setback_fractions,
)

# 20 x 20 pixels of 0.01 degree at the equator: about 1.11 km per pixel
TRANSFORM = from_origin(10.0, 0.2, 0.01, 0.01)
SHAPE = (20, 20)


def _gdf(*geoms):
    return gpd.GeoDataFrame(geometry=list(geoms), crs="EPSG:4326")


def test_polygon_covering_half_of_each_pixel_gives_a_share_of_one_half():
    # columns 10.00-10.10 fully, plus nothing else: pixels 0-9 -> 1; a polygon over 10.10-10.105 covers half of pixel 10
    cover = polygon_coverage_fraction(_gdf(box(10.0, 0.0, 10.105, 0.2)), TRANSFORM, SHAPE)
    assert np.allclose(cover[:, :10], 1.0)
    assert np.allclose(cover[:, 10], 0.5, atol=0.01)
    assert np.allclose(cover[:, 11:], 0.0)


def test_empty_or_missing_vectors_give_zero():
    assert polygon_coverage_fraction(None, TRANSFORM, SHAPE).sum() == 0
    assert polygon_coverage_fraction(_gdf(), TRANSFORM, SHAPE).sum() == 0
    assert all(f.sum() == 0 for f in river_setback_fractions(None, TRANSFORM, SHAPE, [0.5]).values())


def test_a_river_excludes_only_the_share_within_the_setback_not_the_whole_pixel():
    river = _gdf(LineString([(10.095, 0.0), (10.095, 0.2)]))  # a vertical line through the middle of pixel column 9
    fr = river_setback_fractions(river, TRANSFORM, SHAPE, [0.25, 0.5, 1.0])
    mid = fr[0.5][10, :]
    # 0.5 km on each side is about +/-0.0045 degree: the pixel with the river holds about 0.9 of its width, neighbours little
    assert 0.80 < mid[9] <= 1.0
    assert mid[8] < 0.35 and mid[10] < 0.35
    assert mid[0] == 0.0 and mid[15] == 0.0
    # monotone in the setback, and pixels beyond 1.5 pixels are untouched at 0.25 km
    assert (fr[0.25][10] <= fr[0.5][10] + 1e-6).all() and (fr[0.5][10] <= fr[1.0][10] + 1e-6).all()
    assert fr[0.25][10, 7] == 0.0


def test_setbacks_below_the_pixel_size_differ_unlike_the_pixel_level_distance():
    river = _gdf(LineString([(10.095, 0.0), (10.095, 0.2)]))
    fr = river_setback_fractions(river, TRANSFORM, SHAPE, [0.25, 1.0])
    assert fr[1.0][10, 9] > fr[0.25][10, 9] + 0.1  # at pixel level both would simply be "the pixel has a river"


def test_strips_give_the_same_result_as_one_pass():
    river = _gdf(LineString([(10.02, 0.0), (10.17, 0.2)]))
    one = river_setback_fractions(river, TRANSFORM, SHAPE, [0.5], strip_rows=20)[0.5]
    many = river_setback_fractions(river, TRANSFORM, SHAPE, [0.5], strip_rows=3)[0.5]
    assert np.allclose(one, many, atol=1e-6)
    poly = _gdf(box(10.013, 0.03, 10.121, 0.147))
    assert np.allclose(
        polygon_coverage_fraction(poly, TRANSFORM, SHAPE, strip_rows=20),
        polygon_coverage_fraction(poly, TRANSFORM, SHAPE, strip_rows=3),
        atol=1e-6,
    )


def test_discharge_threshold_drops_small_streams_and_needs_the_column():
    big = LineString([(10.095, 0.0), (10.095, 0.2)])
    small = LineString([(10.045, 0.0), (10.045, 0.2)])
    rivers = gpd.GeoDataFrame({"DIS_AV_CMS": [20.0, 0.5]}, geometry=[big, small], crs="EPSG:4326")
    fr = river_fractions(rivers, TRANSFORM, SHAPE, [0.5], [0.0, 1.0])
    assert fr[(0.0, 0.5)][10, 4] > 0.5 and fr[(1.0, 0.5)][10, 4] == 0.0  # the small stream only counts at q = 0
    assert np.allclose(fr[(0.0, 0.5)][10, 9], fr[(1.0, 0.5)][10, 9])  # the big one counts either way
    with pytest.raises(ValueError, match="DIS_AV_CMS"):
        river_fractions(_gdf(big), TRANSFORM, SHAPE, [0.5], [1.0])
