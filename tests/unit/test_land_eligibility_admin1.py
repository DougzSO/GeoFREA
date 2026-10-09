"""The admin1 unit of a cell is the one with the largest area inside it, by geometry (M-F3-03, D-F3-012)."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pytest
import shapely
from shapely.geometry import MultiPolygon, Polygon, box

from geofrea.core.constants import CELL_DEG
from geofrea.land_eligibility import admin1
from geofrea.land_eligibility.cells import cell_row_col

LON0, LAT0 = 10.0, 5.0  # north-west corner of the test area, on the 0.05 degree lattice


def _units(geometries: dict[str, object]):
    frame = gpd.GeoDataFrame(
        {"GID_1": list(geometries), "NAME_1": [f"name {k}" for k in geometries]},
        geometry=list(geometries.values()),
        crs="EPSG:4326",
    )
    return admin1.read_units(frame)


def _cells(n_cols: int, n_rows: int = 1):
    """Rows and columns of an `n_rows` x `n_cols` block of cells whose north-west corner is (LON0, LAT0)."""
    row0, col0 = cell_row_col(LAT0 - CELL_DEG / 2, LON0 + CELL_DEG / 2)
    rows, cols = np.meshgrid(np.arange(n_rows) + row0, np.arange(n_cols) + col0, indexing="ij")
    return rows.ravel(), cols.ravel()


def _cell_box(col_offset: int = 0):
    return box(
        LON0 + col_offset * CELL_DEG, LAT0 - CELL_DEG, LON0 + (col_offset + 1) * CELL_DEG, LAT0
    )


@pytest.mark.unit
def test_a_cell_inside_one_unit_takes_it_and_a_split_cell_takes_the_larger_part():
    # cells 0, 1, 2 in a row; the border between the units is at 0.12 degree: cell 2 (0.10 to 0.15) is split 2 : 3, so B has the larger part
    units = _units(
        {
            "A": box(LON0, LAT0 - CELL_DEG, LON0 + 0.12, LAT0),
            "B": box(LON0 + 0.12, LAT0 - CELL_DEG, LON0 + 0.30, LAT0),
        }
    )
    rows, cols = _cells(6)
    assert admin1.assign_admin1(rows, cols, units).tolist() == ["A", "A", "B", "B", "B", "B"]


@pytest.mark.unit
def test_geometry_decides_and_not_the_cell_centre():
    """A thin band through the centre of the cell belongs to unit A, the two outer parts to B (larger in total): B wins."""
    band = box(LON0, LAT0 - 0.03, LON0 + CELL_DEG, LAT0 - 0.02)
    outer = MultiPolygon(
        [
            box(LON0, LAT0 - CELL_DEG, LON0 + CELL_DEG, LAT0 - 0.03),
            box(LON0, LAT0 - 0.02, LON0 + CELL_DEG, LAT0),
        ]
    )
    centre = shapely.Point(LON0 + CELL_DEG / 2, LAT0 - CELL_DEG / 2)
    assert band.contains(centre) and not outer.contains(centre)
    units = _units({"A": band, "B": outer})
    rows, cols = _cells(1)
    assert admin1.assign_admin1(rows, cols, units).tolist() == ["B"]


@pytest.mark.unit
def test_a_tie_goes_to_the_smallest_unit_identifier():
    units = _units(
        {
            "Z": box(LON0 + CELL_DEG / 2, LAT0 - CELL_DEG, LON0 + CELL_DEG, LAT0),
            "A": box(LON0, LAT0 - CELL_DEG, LON0 + CELL_DEG / 2, LAT0),
        }
    )
    rows, cols = _cells(1)
    assert admin1.assign_admin1(rows, cols, units).tolist() == ["A"]


@pytest.mark.unit
def test_the_parts_of_a_multipart_unit_add_up_across_a_cell():
    parts = MultiPolygon(
        [
            box(LON0, LAT0 - 0.02, LON0 + 0.02, LAT0),  # 0.02 x 0.02 in the north-west corner
            box(
                LON0 + 0.03, LAT0 - CELL_DEG, LON0 + CELL_DEG, LAT0 - 0.03
            ),  # 0.02 x 0.02 south-east
        ]
    )
    rest = Polygon(
        [
            (LON0 + 0.02, LAT0),
            (LON0 + CELL_DEG, LAT0),
            (LON0 + CELL_DEG, LAT0 - 0.03),
            (LON0 + 0.03, LAT0 - 0.03),
            (LON0 + 0.03, LAT0 - CELL_DEG),
            (LON0, LAT0 - CELL_DEG),
            (LON0, LAT0 - 0.02),
            (LON0 + 0.02, LAT0 - 0.02),
        ]
    )
    # parts: 0.0008 against rest: 0.0025 - 0.0008 = 0.0017, so the rest wins; a unit of one of the two parts would lose to it
    units = _units({"parts": parts, "rest": rest})
    rows, cols = _cells(1)
    assert admin1.assign_admin1(rows, cols, units).tolist() == ["rest"]
    units2 = _units(
        {"parts": parts, "rest": box(LON0 + 0.02, LAT0 - 0.03, LON0 + 0.03, LAT0 - 0.02)}
    )
    assert admin1.assign_admin1(rows, cols, units2).tolist() == ["parts"]  # 0.0008 > 0.0001


@pytest.mark.unit
def test_the_shortcut_for_cells_inside_a_unit_gives_the_same_answer_as_the_intersection():
    rng = np.random.default_rng(3)
    # a 5 x 5 cell block cut into random convex-ish unit polygons by distance to random seed points
    rows, cols = _cells(5, 5)
    boxes = admin1.cell_boxes(rows, cols)
    seeds = rng.uniform(0, 0.25, (4, 2))
    xs = np.linspace(0, 0.25, 251)
    units_geoms = {}
    grid_x, grid_y = np.meshgrid(xs, xs)
    owner = np.argmin(
        (grid_x[..., None] - seeds[:, 0]) ** 2 + (grid_y[..., None] - seeds[:, 1]) ** 2, axis=2
    )
    for k in range(4):
        pieces = [
            box(LON0 + xs[j], LAT0 - xs[i + 1], LON0 + xs[j + 1], LAT0 - xs[i])
            for i in range(250)
            for j in range(250)
            if owner[i, j] == k
        ]
        units_geoms[f"U{k}"] = shapely.union_all(pieces) if pieces else Polygon()
    units = _units({k: v for k, v in units_geoms.items() if not v.is_empty})
    got = admin1.assign_admin1(rows, cols, units)
    expected = []
    for b in boxes:
        areas = {
            u: b.intersection(g).area
            for u, g in zip(units["admin1_id"], units.geometry, strict=True)
        }
        best = max(areas.values())
        expected.append(min(u for u, a in areas.items() if a >= best - 1e-15))
    assert got.tolist() == expected


@pytest.mark.unit
def test_a_cell_that_overlaps_no_unit_is_an_error():
    units = _units({"A": box(LON0, LAT0 - CELL_DEG, LON0 + CELL_DEG, LAT0)})
    rows, cols = _cells(3)
    with pytest.raises(admin1.Admin1Error, match="overlap no admin1 unit"):
        admin1.assign_admin1(rows, cols, units)


@pytest.mark.unit
def test_a_layer_without_the_columns_or_with_a_repeated_identifier_is_refused():
    frame = gpd.GeoDataFrame({"NAME_1": ["x"]}, geometry=[_cell_box()], crs="EPSG:4326")
    with pytest.raises(admin1.Admin1Error, match="GID_1"):
        admin1.read_units(frame)
    twice = gpd.GeoDataFrame(
        {"GID_1": ["a", "a"], "NAME_1": ["x", "y"]},
        geometry=[_cell_box(0), _cell_box(1)],
        crs="EPSG:4326",
    )
    with pytest.raises(admin1.Admin1Error, match="repeats"):
        admin1.read_units(twice)
    with pytest.raises(admin1.Admin1Error, match="no unit"):
        admin1.read_units(
            gpd.GeoDataFrame({"GID_1": [], "NAME_1": []}, geometry=[], crs="EPSG:4326")
        )
