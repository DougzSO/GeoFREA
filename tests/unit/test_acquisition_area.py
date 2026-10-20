"""The area an acquisition must cover is the mask box plus a margin, and a product on disk is checked against it (COMMAND 59)."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
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
    uncovered_boxes,
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


def _product(west, south, east, north, res=0.25, holes=()):
    """Cell centres of a regular product with the cells inside the given boxes (west, south, east, north) switched off."""
    lat = np.arange(south + res / 2, north, res)
    lon = np.arange(west + res / 2, east, res)
    valid = np.ones((len(lat), len(lon)), dtype=bool)
    for hw, hs, he, hn in holes:
        valid[np.ix_((lat >= hs) & (lat <= hn), (lon >= hw) & (lon <= he))] = False
    return lat, lon, valid


def test_only_the_parts_of_the_mask_with_no_valid_cell_are_asked_for_and_each_has_its_own_box():
    mask = MultiPolygon([BODY, BLOCK, EAST])
    lat, lon, valid = _product(68.0, 8.0, 97.0, 33.0)  # the product of the old mask
    boxes = uncovered_boxes(mask, lat, lon, valid, 0.25, overlap_deg=0.25)
    assert len(boxes) == 2
    north = next(b for b in boxes if b[3] > 35.0)
    east = next(b for b in boxes if b[3] < 35.0)
    assert bbox_contains(north, (73.8, 33.6, 79.2, 35.4)), "the north block is inside its box"
    assert north[3] == pytest.approx(35.5 + MARGIN_DEG + 0.25, abs=0.06)
    assert east[0] < 97.0 < east[2] and east[1] > 20.0, (
        "the east box is the height of the east end, not of the country"
    )


def test_a_hole_inside_the_box_of_the_product_is_found():
    # the old territory stopped at 32.0 N: between 32.0 and 33.0 N the product has cells with no value inside the block
    mask = MultiPolygon([BODY, BLOCK])
    lat, lon, valid = _product(68.0, 8.0, 97.0, 33.0, holes=[(73.0, 32.0, 80.0, 33.0)])
    boxes = uncovered_boxes(mask, lat, lon, valid, 0.25)
    assert len(boxes) == 1 and bbox_contains(boxes[0], BLOCK.bounds)


def test_nothing_is_asked_when_the_product_reaches_the_mask_to_within_a_cell():
    lat, lon, valid = _product(68.0, 8.0, 97.0, 33.0)
    assert uncovered_boxes(box(68.3, 8.2, 96.9, 32.9), lat, lon, valid, 0.25) == []
    # a coast cell dropped by the polygon crop: one native cell short on the west side
    assert uncovered_boxes(box(67.9, 8.2, 96.9, 32.9), lat, lon, valid, 0.25) == []


def test_a_product_with_no_valid_cell_asks_for_the_whole_acquisition_box():
    lat, lon, valid = _product(68.0, 8.0, 97.0, 33.0)
    boxes = uncovered_boxes(BODY, lat, lon, np.zeros_like(valid), 0.25)
    assert boxes == [acquisition_bbox(BODY.bounds)]


def test_the_worldcover_tile_list_follows_the_mask_including_a_block_the_old_list_lacked():
    from geofrea.data_acquisition.fetchers.esa_worldcover import tile_name, tiles_for_mask

    assert tile_name(33, 72) == "ESA_WorldCover_10m_2020_v100_N33E072_Map.tif"
    assert tile_name(-3, -51) == "ESA_WorldCover_10m_2020_v100_S03W051_Map.tif"
    names = set(tiles_for_mask(MultiPolygon([BODY, BLOCK, EAST])))
    assert (
        "ESA_WorldCover_10m_2020_v100_N33E072_Map.tif" in names
    )  # the north block (73.7-79.3 E, 32-35.5 N)
    assert "ESA_WorldCover_10m_2020_v100_N33E078_Map.tif" in names
    assert "ESA_WorldCover_10m_2020_v100_N36E072_Map.tif" not in names  # north of the mask
    assert all(n.endswith("_Map.tif") for n in names)
