"""The area an acquisition must cover is the mask box plus a margin, and a product on disk is checked against it (COMMAND 59)."""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import MultiPolygon, box

from geofrea.data_acquisition.acquisition_area import (
    MARGIN_DEG,
    acquisition_bbox,
    bbox_contains,
    cds_area,
    missing_parts,
    native_grid_covers,
    native_grid_extent,
)
from geofrea.data_acquisition.fetchers.era5 import bbox_from_polygon

# a mask of two blocks, the second one north and east of the first: what the contiguous mask of COMMAND 55 gave IND
BODY = box(68.0, 8.0, 97.0, 32.0)
BLOCK = box(73.7, 32.0, 79.3, 35.5)
EAST = box(95.0, 26.8, 97.4, 29.4)


def test_the_acquisition_box_contains_the_mask_with_the_margin_on_every_side():
    mask = MultiPolygon([BODY, BLOCK, EAST])
    area = acquisition_bbox(mask.bounds)
    assert bbox_contains(area, mask.bounds)
    assert area == (68.0 - MARGIN_DEG, 8.0 - MARGIN_DEG, 97.4 + MARGIN_DEG, 35.5 + MARGIN_DEG)


def test_the_box_follows_the_mask_it_is_given_not_a_fixed_box():
    small = acquisition_bbox(BODY.bounds)
    grown = acquisition_bbox(MultiPolygon([BODY, BLOCK]).bounds)
    assert grown[3] > small[3] and grown[:3] == small[:3]


def test_empty_bounds_and_a_negative_margin_are_refused():
    with pytest.raises(ValueError):
        acquisition_bbox((1.0, 1.0, 1.0, 2.0))
    with pytest.raises(ValueError):
        acquisition_bbox((0.0, 0.0, 1.0, 1.0), margin_deg=-1)


def test_the_era5_request_area_is_the_acquisition_box_in_the_north_west_south_east_order(tmp_path):
    path = tmp_path / "mask.gpkg"
    gpd.GeoDataFrame(geometry=[MultiPolygon([BODY, BLOCK, EAST])], crs="EPSG:4326").to_file(
        path, driver="GPKG"
    )
    n, w, s, e = bbox_from_polygon(path)
    assert (w, s, e, n) == acquisition_bbox(MultiPolygon([BODY, BLOCK, EAST]).bounds)
    assert bbox_contains((w, s, e, n), MultiPolygon([BODY, BLOCK, EAST]).bounds)
    assert cds_area((w, s, e, n)) == [n, w, s, e]


def test_a_product_on_the_old_mask_does_not_cover_the_new_mask():
    # the ERA5 product of IND before COMMAND 59: cell centres 8.25-33.0 N and 68.5-97.0 E on 0.25 degree
    extent = native_grid_extent(8.25, 33.0, 0.25, 68.5, 97.0, 0.25)
    assert native_grid_covers(extent, (68.3, 8.3, 96.9, 32.0), 0.25)
    new_mask = MultiPolygon([BODY, BLOCK, EAST]).bounds
    assert not native_grid_covers(extent, new_mask, 0.25)


def test_a_shortfall_of_one_native_cell_at_a_coast_is_tolerated_and_two_are_not():
    extent = native_grid_extent(8.25, 33.0, 0.25, 68.5, 97.0, 0.25)  # edges 68.375 .. 97.125
    assert native_grid_covers(extent, (68.2, 10.0, 90.0, 30.0), 0.25)
    assert not native_grid_covers(extent, (67.9, 10.0, 90.0, 30.0), 0.25)


def test_the_missing_parts_complete_the_product_and_overlap_the_seam():
    have = native_grid_extent(8.25, 33.0, 0.25, 68.5, 97.0, 0.25)
    need = acquisition_bbox(MultiPolygon([BODY, BLOCK, EAST]).bounds)
    parts = missing_parts(have, need, overlap_deg=0.25)
    assert parts and all(p[0] < p[2] and p[1] < p[3] for p in parts)
    north = [p for p in parts if p[3] == need[3]]
    assert len(north) == 1 and north[0][1] == have[3] - 0.25  # one cell of overlap below the seam
    # every point of `need` is in `have` or in a part
    for x, y in [
        (need[0] + 0.01, need[1] + 0.01),
        (need[2] - 0.01, need[3] - 0.01),
        (need[2] - 0.01, 28.0),
        (75.0, need[3] - 0.01),
    ]:
        assert any(bbox_contains(b, (x, y, x, y)) for b in [have, *parts]), (x, y)


def test_nothing_is_missing_when_the_product_already_contains_the_area():
    have = (60.0, 0.0, 100.0, 40.0)
    assert missing_parts(have, acquisition_bbox(MultiPolygon([BODY, BLOCK, EAST]).bounds)) == []
