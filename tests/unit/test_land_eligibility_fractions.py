"""Sub-pixel excluded shares (OQ-045 option c): polygon coverage and riparian setback fractions."""

from __future__ import annotations

import itertools

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
    assert all(
        f.sum() == 0 for f in river_setback_fractions(None, TRANSFORM, SHAPE, [0.5]).values()
    )


def test_a_river_excludes_only_the_share_within_the_setback_not_the_whole_pixel():
    river = _gdf(
        LineString([(10.095, 0.0), (10.095, 0.2)])
    )  # a vertical line through the middle of pixel column 9
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
    assert (
        fr[1.0][10, 9] > fr[0.25][10, 9] + 0.1
    )  # at pixel level both would simply be "the pixel has a river"


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
    assert (
        fr[(0.0, 0.5)][10, 4] > 0.5 and fr[(1.0, 0.5)][10, 4] == 0.0
    )  # the small stream only counts at q = 0
    assert np.allclose(
        fr[(0.0, 0.5)][10, 9], fr[(1.0, 0.5)][10, 9]
    )  # the big one counts either way
    with pytest.raises(ValueError, match="DIS_AV_CMS"):
        river_fractions(_gdf(big), TRANSFORM, SHAPE, [0.5], [1.0])


# ─── the result does not depend on the origin of the grid (COMMAND 58, E1 of IND) ────────────────────────────────────────────────────────────

from shapely.geometry import Polygon

from geofrea.land_eligibility.fractions import _anchored_strips


def _diagonal_polygons():
    """Polygons with every vertex on the 0.001 degree lattice and diagonal edges, which run exactly through sub-pixel centres (0.0005 offsets)."""
    return _gdf(
        Polygon([(10.0123, 0.1011), (10.0623, 0.1511), (10.0123, 0.1511)]),
        Polygon([(10.1002, 0.0301), (10.1402, 0.0701), (10.1802, 0.0301)]),
        Polygon([(10.0501, 0.0105), (10.0901, 0.0105), (10.0701, 0.0505)]),
    )


def test_a_polygon_edge_through_sub_pixel_centres_gives_the_same_shares_on_every_float_noise_of_the_origin():
    rng = np.random.default_rng(58)
    polygons = _diagonal_polygons()
    base = polygon_coverage_fraction(polygons, TRANSFORM, SHAPE)
    assert base.sum() > 0
    for _ in range(200):
        dx, dy = rng.uniform(-2e-13, 2e-13, 2)
        noisy = from_origin(10.0 + dx, 0.2 + dy, 0.01, 0.01)
        assert np.array_equal(polygon_coverage_fraction(polygons, noisy, SHAPE), base)


def test_the_same_polygons_give_the_same_shares_on_two_grids_of_the_same_lattice_for_edges_of_slope_plus_and_minus_one_and_one_half():
    """Edges of slope +1, -1, +1/2 and -2 between lattice vertices: the shares of the pixels of one grid are those of the same pixels on a larger grid."""
    polygons = _gdf(
        Polygon([(10.0123, 0.1011), (10.0623, 0.1511), (10.1123, 0.1011)]),  # slopes +1 and -1
        Polygon([(10.1502, 0.0301), (10.1902, 0.0501), (10.1502, 0.0701)]),  # slopes +1/2 and -1/2
        Polygon([(10.0501, 0.0105), (10.0701, 0.0505), (10.0901, 0.0105)]),  # slopes +2 and -2
    )
    small = polygon_coverage_fraction(polygons, TRANSFORM, SHAPE)
    larger_transform = from_origin(
        10.0 - 0.03, 0.2 + 0.05, 0.01, 0.01
    )  # 3 pixels west, 5 north, another width and height
    larger = polygon_coverage_fraction(polygons, larger_transform, (30, 28))
    assert small.sum() > 0
    assert np.array_equal(larger[5:25, 3:23], small)


def test_without_the_tie_break_that_noise_does_change_the_shares():
    """The control of the test above: at `tie_break_deg=0` the same noise flips some sub-pixel centres (the defect that was fixed)."""
    rng = np.random.default_rng(58)
    polygons = _diagonal_polygons()
    base = polygon_coverage_fraction(polygons, TRANSFORM, SHAPE, tie_break_deg=0.0)
    flipped = 0
    for _ in range(200):
        dx, dy = rng.uniform(-2e-13, 2e-13, 2)
        noisy = from_origin(10.0 + dx, 0.2 + dy, 0.01, 0.01)
        flipped += not np.array_equal(
            polygon_coverage_fraction(polygons, noisy, SHAPE, tie_break_deg=0.0), base
        )
    assert flipped > 0


def test_the_tie_break_changes_a_share_by_far_less_than_a_sub_pixel():
    polygons = _diagonal_polygons()
    exact = polygon_coverage_fraction(polygons, TRANSFORM, SHAPE, tie_break_deg=0.0)
    shifted = polygon_coverage_fraction(polygons, TRANSFORM, SHAPE)
    assert abs(float(exact.sum()) - float(shifted.sum())) < 0.05 * float(
        exact.sum()
    )  # a few sub-pixels of thousands
    assert (
        np.abs(exact - shifted).max() <= 0.1 + 1e-6
    )  # a pixel crossed along a 45 degree edge: its ten centres on the edge go to one side


def test_anchored_strips_cover_every_row_once_and_start_on_multiples_of_the_strip_height():
    for top in (35.55, 33.30, 10.0):
        transform = from_origin(68.15, top, 0.01, 0.01)
        strips = _anchored_strips(transform, 250, 40)
        assert strips[0][0] == 0 and strips[-1][1] == 250
        assert all(a[1] == b[0] for a, b in itertools.pairwise(strips))
        absolute_top = round((90.0 - top) / 0.01)
        for r0, _r1, k0 in strips:
            assert k0 % 40 == 0 and k0 <= absolute_top + r0 < k0 + 40


def test_the_same_pixels_fall_in_the_same_strip_on_two_grids_of_the_same_lattice():
    a = from_origin(68.15, 35.55, 0.01, 0.01)
    b = from_origin(68.45, 33.30, 0.01, 0.01)
    strip_of = {}
    for name, transform, height in (("a", a, 400), ("b", b, 400)):
        for r0, r1, k0 in _anchored_strips(transform, height, 40):
            for r in range(r0, r1):
                strip_of[(name, round((90.0 - transform.f) / 0.01) + r)] = k0
    common = {k for (n, k) in strip_of if n == "a"} & {k for (n, k) in strip_of if n == "b"}
    assert common and all(strip_of[("a", k)] == strip_of[("b", k)] for k in common)


def test_riparian_shares_do_not_depend_on_where_the_grid_begins():
    """The setback distance is measured with the km per degree at the middle of a strip: that middle is now taken on the absolute lattice."""
    line = _gdf(LineString([(10.02, 40.0), (10.31, 39.62), (10.55, 39.9)]))
    ta = from_origin(10.0, 40.0, 0.01, 0.01)  # top at 40.00 -> absolute row 5000
    tb = from_origin(10.0, 39.9, 0.01, 0.01)  # top 10 rows lower
    fa = river_setback_fractions(line, ta, (60, 60), [3.0, 6.0], strip_rows=8)
    fb = river_setback_fractions(line, tb, (50, 60), [3.0, 6.0], strip_rows=8)
    for t in (3.0, 6.0):
        # the rows within the setback of the north edge of the second grid do not see the river beyond it (the grid is the horizon of the strip)
        assert np.array_equal(fa[t][22:60], fb[t][12:50]), t
