"""Unit tests for geofrea.land_eligibility.cells (S-06, M-F3-01/03/04) on synthetic grids."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from rasterio.transform import from_origin

from geofrea.data_quality_audit.raster_inspection import row_area_km2
from geofrea.land_eligibility import cells

# North-west corner on the 0.05 lattice: -9.0 W (= -180 steps), 39.0 N (= 1020 steps)
WEST, NORTH = -9.0, 39.0


def _transform():
    return from_origin(WEST, NORTH, 0.01, 0.01)


@pytest.mark.unit
def test_lattice_size_and_id_formula():
    assert (cells.N_ROWS, cells.N_COLS) == (3600, 7200)
    assert int(cells.cell_id(0, 0)) == 0
    assert int(cells.cell_id(3599, 7199)) == 3600 * 7200 - 1 < 2**31  # fits int32
    row, col = cells.row_col_from_id(cells.cell_id(1234, 5678))
    assert (int(row), int(col)) == (1234, 5678)


@pytest.mark.unit
def test_cell_of_a_point_and_its_center_round_trip():
    lat, lon = 38.7223, -9.1393  # Lisbon
    row, col = cells.cell_row_col(lat, lon)
    lat_c, lon_c = cells.cell_center(row, col)

    assert abs(float(lat_c) - lat) <= 0.025 and abs(float(lon_c) - lon) <= 0.025
    assert tuple(int(v) for v in cells.cell_row_col(lat_c, lon_c)) == (int(row), int(col))


@pytest.mark.unit
def test_lattice_corners_and_out_of_range():
    r, c = cells.cell_row_col(90.0, -180.0)
    assert (int(r), int(c)) == (0, 0)
    r, c = cells.cell_row_col(-90.0, 180.0)
    assert (int(r), int(c)) == (3599, 7199)
    with pytest.raises(ValueError):
        cells.cell_row_col(91.0, 0.0)


@pytest.mark.unit
def test_ids_do_not_depend_on_the_country_extent():
    """The same place gets the same id whether the grid started at a different corner."""
    lat, lon = 38.9725, -8.9625  # inside the grid below
    expected = cells.cell_id(*cells.cell_row_col(lat, lon))
    t = _transform()
    df = cells.aggregate_to_cells(
        t, np.ones((10, 15), bool), np.ones((10, 15), bool), {"E1": np.zeros((10, 15), bool)}
    )
    in_cell = df[(abs(df.lat_c - 38.975) < 1e-9) & (abs(df.lon_c - (-8.975)) < 1e-9)]
    assert int(in_cell.cell_id.iloc[0]) == int(expected)


@pytest.mark.unit
def test_0_1_degree_cell_contains_exactly_four_0_05_cells():
    ids = []
    for dr in (0, 1):
        for dc in (0, 1):
            ids.append(int(cells.cell_id(1000 + dr, 2000 + dc)))
    coarse = {int(cells.coarse_cell_id(i)) for i in ids}
    assert len(coarse) == 1
    assert int(cells.coarse_cell_id(cells.cell_id(1002, 2000))) != coarse.pop()


@pytest.mark.unit
def test_pixel_row_area_matches_the_audit_helper():
    t = _transform()
    assert cells.pixel_row_area_km2(t, 10) == pytest.approx(row_area_km2((10, 15), t))


@pytest.mark.unit
def test_grid_off_the_lattice_or_not_whole_cells_fails_loud():
    with pytest.raises(cells.GridNotOnLatticeError):
        cells.grid_cell_origin(_transform(), 10, 14)  # 14 px is not 5 x 5 cells
    with pytest.raises(cells.GridNotOnLatticeError):
        cells.grid_cell_origin(from_origin(-9.013, 39.0, 0.01, 0.01), 10, 15)  # corner off the 0.05 lattice
    assert cells.grid_cell_origin(_transform(), 10, 15) == (1020, 3600 - 180)


@pytest.mark.unit
def test_pixel_eligibility_is_not_any_exclusion_and_all_required_layers_valid():
    e1 = np.array([[True, False], [False, False]])
    e2 = np.array([[False, False], [True, False]])
    valid = np.array([[True, True], [True, False]])

    out = cells.pixel_eligibility({"E1": e1, "E2": e2}, [valid])

    assert out.tolist() == [[False, True], [False, False]]


def _grid_inputs():
    h, w = 10, 15  # 2 x 3 cells
    country = np.ones((h, w), bool)
    country[:, 10:] = False  # third cell column is outside the country
    country[:5, 5:10] = np.arange(25).reshape(5, 5) % 2 == 0  # cell (0,1) only partly inside
    e1 = np.zeros((h, w), bool)
    e1[:5, :5] = True  # whole cell (0,0) excluded by E1
    e2 = np.zeros((h, w), bool)
    e2[5:, :5][:2, :] = True  # two pixel rows of cell (1,0) excluded by E2
    return country, e1, e2


@pytest.mark.unit
def test_aggregation_areas_dominant_exclusion_and_candidate_filter():
    t = _transform()
    country, e1, e2 = _grid_inputs()
    elig = cells.pixel_eligibility({"E1": e1, "E2": e2}) & country

    df = cells.aggregate_to_cells(t, country, elig, {"E1": e1, "E2": e2})
    areas = cells.pixel_row_area_km2(t, 10)

    assert len(df) == 4  # the third cell column has no in-country pixel
    c00 = df[(df.row == 1020) & (df.col == 3420)].iloc[0]
    assert c00.eligible_area_km2 == 0 and c00.dominant_exclusion == "E1"
    assert c00.excluded_area_km2_E1 == pytest.approx(5 * areas[:5].sum())
    c10 = df[(df.row == 1021) & (df.col == 3420)].iloc[0]
    assert c10.dominant_exclusion == "E2"
    assert c10.eligible_area_km2 == pytest.approx(5 * areas[7:10].sum())  # 3 of 5 pixel rows eligible
    assert c10.cell_area_km2 == pytest.approx(5 * areas[5:10].sum())
    c01 = df[(df.row == 1020) & (df.col == 3421)].iloc[0]
    assert 0 < c01.cell_area_km2 < 5 * areas[:5].sum()  # partly inside the country: land area only
    assert pd.isna(c01.dominant_exclusion)  # nothing excluded there

    keep = cells.candidate_cells(df, min_eligible_area_km2=float(c10.eligible_area_km2))
    assert set(keep.cell_id) >= {int(c10.cell_id)} and int(c00.cell_id) not in set(keep.cell_id)


@pytest.mark.unit
def test_resources_are_eligible_area_weighted_means_and_flags_are_eligible_shares():
    t = _transform()
    h, w = 10, 15
    country = np.ones((h, w), bool)
    elig = np.zeros((h, w), bool)
    elig[:5, :5] = True
    elig[:5, :2] = False  # 3 of 5 pixel columns eligible in cell (0,0)
    res = np.zeros((h, w))
    res[:5, 2] = 10.0
    res[:5, 3:5] = 20.0
    capped = np.zeros((h, w), bool)
    capped[:5, 2] = True

    df = cells.aggregate_to_cells(
        t, country, elig, {"E1": ~elig}, resources={"dist_grid_km": res}, flags={"distance_capped": capped}
    )
    c = df[(df.row == 1020) & (df.col == 3420)].iloc[0]

    assert c.dist_grid_km == pytest.approx((10 + 20 + 20) / 3, rel=1e-3)  # equal pixel areas per row
    assert c.distance_capped == pytest.approx(1 / 3, rel=1e-3)
    empty = df[(df.row == 1021) & (df.col == 3420)].iloc[0]
    assert np.isnan(empty.dist_grid_km) and np.isnan(empty.distance_capped)  # no eligible area: undefined, not 0
