"""Sub-pixel excluded shares (OQ-045 option c): polygon coverage, river corridors by estimated width and settlement setbacks (Group 6)."""

from __future__ import annotations

import itertools

import geopandas as gpd
import numpy as np
import pytest
from rasterio.transform import from_origin
from shapely.geometry import LineString, box

from geofrea.land_eligibility.fractions import (
    buffer_m,
    corridor_half_widths_m,
    mask_setback_fractions,
    polygon_coverage_fraction,
    river_corridor_fraction,
    river_widths_m,
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
    assert river_corridor_fraction(None, [], TRANSFORM, SHAPE).sum() == 0
    assert all(f.sum() == 0 for f in mask_setback_fractions(None, TRANSFORM, SHAPE, [500.0]).values())
    assert all(f.sum() == 0 for f in mask_setback_fractions(np.zeros(SHAPE, bool), TRANSFORM, SHAPE, [500.0]).values())


# ─── the width of a reach and the buffer of a country (eq:g6_width, tab:g6_riparian) ─────────────────────────────────────────────────────────

BRA_STEPS = [(10.0, 30.0), (50.0, 50.0), (200.0, 100.0), (600.0, 200.0), (None, 500.0)]


def test_width_is_a_power_of_the_mean_discharge():
    q = np.array([1.0, 4.0, 100.0])
    assert np.allclose(river_widths_m(q, 7.2, 0.50), [7.2, 14.4, 72.0])
    assert np.allclose(river_widths_m(q, 7.2, 0.52), 7.2 * q**0.52)
    with pytest.raises(ValueError, match="finite and non-negative"):
        river_widths_m([1.0, float("nan")], 7.2, 0.5)
    with pytest.raises(ValueError, match="finite and non-negative"):
        river_widths_m([-1.0], 7.2, 0.5)


@pytest.mark.parametrize(
    ("q_limit", "width_limit", "below", "above"),
    [
        (1.93, 10.0, 30.0, 50.0),
        (48.2, 50.0, 50.0, 100.0),
        (771.6, 200.0, 100.0, 200.0),
        (6944.0, 600.0, 200.0, 500.0),
    ],
)
def test_the_brazilian_classes_change_at_the_synthetic_discharges_of_the_class_limits(q_limit, width_limit, below, above):
    """Synthetic reaches at the limits of the five classes with b = 0.50: Q of about 1.93, 48.2, 771.6 and 6,944 m3/s give W of 10, 50, 200 and 600 m."""
    q_exact = (width_limit / 7.2) ** 2
    assert q_exact == pytest.approx(q_limit, rel=2e-3)
    w_below = river_widths_m(q_exact * 0.995, 7.2, 0.50)
    w_at = river_widths_m(q_exact, 7.2, 0.50)
    w_above = river_widths_m(q_exact * 1.005, 7.2, 0.50)
    assert w_at == pytest.approx(width_limit)
    assert buffer_m(BRA_STEPS, w_below) == below  # narrower than the limit: the class below
    assert buffer_m(BRA_STEPS, w_above) == above  # wider than the limit: the class above
    assert buffer_m(BRA_STEPS, width_limit) == above  # the classes are half-open: exactly at the limit is the class above


def test_the_half_width_of_the_corridor_is_half_the_channel_plus_the_buffer():
    half = corridor_half_widths_m([1.0, 48.2, 7000.0], 7.2, 0.50, BRA_STEPS)
    assert np.allclose(half, [7.2 / 2 + 30.0, 50.0 / 2 + 50.0, 602.4 / 2 + 500.0], atol=0.2)


def test_portuguese_steps_one_class_and_none_beyond_the_last_step():
    prt_central = [(10.0, 10.0), (None, 30.0)]
    assert list(buffer_m(prt_central, [5.0, 10.0, 80.0])) == [10.0, 30.0, 30.0]
    assert list(buffer_m([(None, 200.0)], [0.0, 1e6])) == [200.0, 200.0]


# ─── river corridors ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


def test_a_river_corridor_excludes_only_the_share_within_its_half_width_not_the_whole_pixel():
    river = _gdf(LineString([(10.095, 0.0), (10.095, 0.2)]))  # a vertical line through the middle of pixel column 9
    shares = {h: river_corridor_fraction(river, [h], TRANSFORM, SHAPE)[10, :] for h in (250.0, 500.0, 1000.0)}
    mid = shares[500.0]
    # 0.5 km on each side is about +/-0.0045 degree: the pixel with the river holds about 0.9 of its width (0.8 to 0.9 by the centres of the sub-pixels), neighbours little
    assert 0.75 < mid[9] <= 1.0
    assert mid[8] < 0.35 and mid[10] < 0.35
    assert mid[0] == 0.0 and mid[15] == 0.0
    # monotone in the half-width, and pixels beyond 1.5 pixels are untouched at 0.25 km
    assert (shares[250.0] <= shares[500.0] + 1e-6).all() and (shares[500.0] <= shares[1000.0] + 1e-6).all()
    assert shares[250.0][7] == 0.0


def test_corridors_below_the_pixel_size_differ_unlike_the_pixel_level_distance():
    river = _gdf(LineString([(10.095, 0.0), (10.095, 0.2)]))
    narrow = river_corridor_fraction(river, [250.0], TRANSFORM, SHAPE)
    wide = river_corridor_fraction(river, [1000.0], TRANSFORM, SHAPE)
    assert wide[10, 9] > narrow[10, 9] + 0.1


def test_every_reach_has_its_own_half_width_and_overlapping_corridors_are_a_union_not_a_sum():
    big = LineString([(10.095, 0.0), (10.095, 0.2)])
    near = LineString([(10.1, 0.0), (10.1, 0.2)])  # 0.005 degree (about 0.55 km) east of the first, overlapping its corridor
    both = river_corridor_fraction(_gdf(big, near), [500.0, 500.0], TRANSFORM, SHAPE)
    alone = river_corridor_fraction(_gdf(big), [500.0], TRANSFORM, SHAPE)
    other = river_corridor_fraction(_gdf(near), [500.0], TRANSFORM, SHAPE)
    assert (both <= 1.0 + 1e-6).all()
    assert (both >= np.maximum(alone, other) - 1e-6).all()  # at least either corridor
    assert (both < alone + other - 1e-3).any()  # and where they overlap less than their sum
    wide_and_narrow = river_corridor_fraction(_gdf(big, near), [1000.0, 250.0], TRANSFORM, SHAPE)
    assert np.allclose(wide_and_narrow[10, :8], river_corridor_fraction(_gdf(big), [1000.0], TRANSFORM, SHAPE)[10, :8], atol=1e-6)
    with pytest.raises(ValueError, match="half-widths"):
        river_corridor_fraction(_gdf(big, near), [500.0], TRANSFORM, SHAPE)


def test_corridor_strips_give_the_same_result_as_one_pass():
    river = _gdf(LineString([(10.02, 0.0), (10.17, 0.2)]))
    one = river_corridor_fraction(river, [500.0], TRANSFORM, SHAPE, strip_rows=20)
    many = river_corridor_fraction(river, [500.0], TRANSFORM, SHAPE, strip_rows=3)
    assert np.allclose(one, many, atol=1e-6)
    poly = _gdf(box(10.013, 0.03, 10.121, 0.147))
    assert np.allclose(
        polygon_coverage_fraction(poly, TRANSFORM, SHAPE, strip_rows=20),
        polygon_coverage_fraction(poly, TRANSFORM, SHAPE, strip_rows=3),
        atol=1e-6,
    )


def test_the_corridor_of_a_wide_river_is_a_band_of_about_its_width():
    """A reach with a 2 km half-width covers about 4 km of a row of pixels (3.6 pixels of 1.11 km), whatever the sub-pixel size."""
    river = _gdf(LineString([(10.1, 0.0), (10.1, 0.2)]))
    row = river_corridor_fraction(river, [2000.0], TRANSFORM, SHAPE)[10, :]
    assert row.sum() == pytest.approx(4.0 / 1.1132, rel=0.05)


# ─── settlement setbacks ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


def _mask(*cells):
    mask = np.zeros(SHAPE, dtype=bool)
    for r, c in cells:
        mask[r, c] = True
    return mask


def test_a_setback_of_zero_excludes_the_settlement_pixels_and_nothing_else():
    shares = mask_setback_fractions(_mask((10, 10)), TRANSFORM, SHAPE, [0.0])[0.0]
    expected = np.zeros(SHAPE, dtype=np.float32)
    expected[10, 10] = 1.0
    np.testing.assert_array_equal(shares, expected)


def test_a_setback_runs_from_the_edge_of_the_settlement_pixel_not_its_centre():
    fr = mask_setback_fractions(_mask((10, 10)), TRANSFORM, SHAPE, [0.0, 250.0, 500.0, 1000.0])
    assert fr[500.0][10, 10] == 1.0
    # 500 m beyond the edge of a pixel 1.11 km wide: the neighbour holds about 0.45 of its width within the setback
    assert 0.35 < fr[500.0][10, 11] < 0.55
    assert fr[500.0][10, 12] == 0.0
    assert fr[1000.0][10, 11] > 0.85
    assert (fr[250.0] <= fr[500.0] + 1e-6).all() and (fr[500.0] <= fr[1000.0] + 1e-6).all()
    assert fr[0.0].sum() < fr[250.0].sum() < fr[500.0].sum() < fr[1000.0].sum()


def test_the_setback_does_not_depend_on_where_the_grid_begins_or_on_the_strip():
    mask = _mask((3, 4), (4, 4), (12, 15))
    a = mask_setback_fractions(mask, TRANSFORM, SHAPE, [500.0, 800.0], strip_rows=20)
    b = mask_setback_fractions(mask, TRANSFORM, SHAPE, [500.0, 800.0], strip_rows=3)
    for t in (500.0, 800.0):
        assert np.allclose(a[t], b[t], atol=1e-6)


def test_settlement_setback_by_blocks_of_columns_gives_the_shares_of_the_whole_strip():
    rng = np.random.default_rng(97)
    mask = rng.random(SHAPE) < 0.04
    setbacks = [0.0, 500.0, 1000.0]
    whole = mask_setback_fractions(mask, TRANSFORM, SHAPE, setbacks, block_subcolumns=10**9)
    for block in (10, 30, 70):
        blocks = mask_setback_fractions(mask, TRANSFORM, SHAPE, setbacks, block_subcolumns=block)
        for t in setbacks:
            np.testing.assert_array_equal(blocks[t], whole[t], err_msg=f"block {block}, setback {t}")
    assert mask.any() and 0 < whole[1000.0].mean() < 1


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


def test_corridor_shares_do_not_depend_on_where_the_grid_begins():
    """The metres per degree are taken at the middle of a strip: that middle is on the absolute lattice, so a pixel gets the same share on any grid."""
    line = _gdf(LineString([(10.02, 40.0), (10.31, 39.62), (10.55, 39.9)]))
    ta = from_origin(10.0, 40.0, 0.01, 0.01)  # top at 40.00 -> absolute row 5000
    tb = from_origin(10.0, 39.9, 0.01, 0.01)  # top 10 rows lower
    half = [3000.0]
    fa = river_corridor_fraction(line, half, ta, (60, 60), strip_rows=8)
    fb = river_corridor_fraction(line, half, tb, (50, 60), strip_rows=8)
    assert np.array_equal(fa[10:60], fb[0:50])
