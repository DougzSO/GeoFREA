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
        cells.grid_cell_origin(
            from_origin(-9.013, 39.0, 0.01, 0.01), 10, 15
        )  # corner off the 0.05 lattice
    assert cells.grid_cell_origin(_transform(), 10, 15) == (1020, 3600 - 180)


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
    elig = ~(e1 | e2) & country

    df = cells.aggregate_to_cells(t, country, elig, {"E1": e1, "E2": e2})
    areas = cells.pixel_row_area_km2(t, 10)

    assert len(df) == 4  # the third cell column has no in-country pixel
    c00 = df[(df.row == 1020) & (df.col == 3420)].iloc[0]
    assert c00.eligible_area_km2 == 0 and c00.dominant_exclusion == "E1"
    assert c00.excluded_area_km2_E1 == pytest.approx(5 * areas[:5].sum())
    c10 = df[(df.row == 1021) & (df.col == 3420)].iloc[0]
    assert c10.dominant_exclusion == "E2"
    assert c10.eligible_area_km2 == pytest.approx(
        5 * areas[7:10].sum()
    )  # 3 of 5 pixel rows eligible
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
        t,
        country,
        elig,
        {"E1": ~elig},
        resources={"dist_grid_km": res},
        flags={"distance_capped": capped},
    )
    c = df[(df.row == 1020) & (df.col == 3420)].iloc[0]

    assert c.dist_grid_km == pytest.approx(
        (10 + 20 + 20) / 3, rel=1e-3
    )  # equal pixel areas per row
    assert c.distance_capped == pytest.approx(1 / 3, rel=1e-3)
    empty = df[(df.row == 1021) & (df.col == 3420)].iloc[0]
    assert np.isnan(empty.dist_grid_km) and np.isnan(
        empty.distance_capped
    )  # no eligible area: undefined, not 0


@pytest.mark.unit
def test_the_pixel_fraction_file_of_the_central_scenario_keeps_its_name_and_the_others_carry_the_scenario():
    from geofrea.land_eligibility.cells import eligible_fraction_file

    assert eligible_fraction_file("wind", "central") == "eligible_fraction_wind.tif"
    assert eligible_fraction_file("wind", "restrictive") == "eligible_fraction_wind__restrictive.tif"
    assert eligible_fraction_file("solar", "permissive") == "eligible_fraction_solar__permissive.tif"

# --- COMMAND 75: the cells are summed in stripes and give what the whole grid gave ---------------------------------------------------------

# the function as it was before the stripes (the whole grid in float64 work arrays): the oracle of the equality below
from geofrea.land_eligibility.cells import (  # noqa: E402
    _block_sum,
    cell_center,
    cell_id,
    lattice_window,
    pad_to_window,
    pixel_row_area_km2,
)

def reference_aggregate_to_cells(
    transform: rasterio.Affine,
    country_mask: np.ndarray,
    eligible: np.ndarray,
    exclusions: dict[str, np.ndarray],
    resources: dict[str, np.ndarray] | None = None,
    flags: dict[str, np.ndarray] | None = None,
) -> pd.DataFrame:
    """M-F3-03 on one country grid: one row per cell that contains at least one in-country pixel.

    Columns: `cell_id`, `row`, `col`, `lat_c`, `lon_c`, `cell_area_km2` (geodesic land area inside the
    country), `eligible_area_km2`, `excluded_area_km2_<Ek>` (overlapping, any-cause), `dominant_exclusion`
    (the Ek with the largest excluded area, <NA> when no area is excluded), one column per `resources`
    entry (eligible-area-weighted mean, NaN when the cell has no eligible area) and one per `flags` entry
    (eligible-area share of pixels where the boolean flag is True, e.g. `distance_capped`).
    Resource values that are NaN on an eligible pixel are excluded from that resource's mean.
    """
    height, width = country_mask.shape
    window = lattice_window(transform, height, width)
    k = window.k

    def block_sum(a: np.ndarray) -> np.ndarray:
        return _block_sum(pad_to_window(np.asarray(a, dtype=float), window), k)

    area_row = pixel_row_area_km2(transform, height)
    area = np.repeat(area_row[:, None], width, axis=1) * country_mask
    eligible_area = area * np.asarray(eligible, dtype=float)  # bool or an eligible share in [0, 1]

    cell_area = block_sum(area)
    el_area = block_sum(eligible_area)

    rows_i, cols_i = np.meshgrid(
        np.arange(window.n_rows) + window.row0,
        np.arange(window.n_cols) + window.col0,
        indexing="ij",
    )
    lat_c, lon_c = cell_center(rows_i, cols_i)
    frame: dict[str, np.ndarray] = {
        "cell_id": cell_id(rows_i, cols_i).ravel(),
        "row": rows_i.ravel(),
        "col": cols_i.ravel(),
        "lat_c": lat_c.ravel(),
        "lon_c": lon_c.ravel(),
        "cell_area_km2": cell_area.ravel(),
        "eligible_area_km2": el_area.ravel(),
    }

    excluded = {}
    for name, mask in exclusions.items():
        excluded[name] = block_sum(
            area * np.asarray(mask, dtype=float)
        )  # bool or a share in [0, 1]
        frame[f"excluded_area_km2_{name}"] = excluded[name].ravel()
    if excluded:
        names = list(excluded)
        stack = np.stack([excluded[n] for n in names])
        dominant = np.array(names, dtype=object)[stack.argmax(axis=0)]
        dominant = np.where(stack.max(axis=0) > 0, dominant, None)
        frame["dominant_exclusion"] = dominant.ravel()

    for name, values in (resources or {}).items():
        usable = eligible_area * np.isfinite(values)
        weighted = block_sum(np.where(np.isfinite(values), values, 0.0) * usable)
        weight = block_sum(usable)
        with np.errstate(invalid="ignore", divide="ignore"):
            frame[name] = np.where(weight > 0, weighted / weight, np.nan).ravel()
    for name, flag in (flags or {}).items():
        flagged = block_sum(eligible_area * flag.astype(bool))
        with np.errstate(invalid="ignore", divide="ignore"):
            frame[name] = np.where(el_area > 0, flagged / el_area, np.nan).ravel()

    out = pd.DataFrame(frame)
    if "dominant_exclusion" in out:  # nullable string: <NA> when nothing is excluded in the cell
        out["dominant_exclusion"] = out["dominant_exclusion"].astype("string")
    return out[out["cell_area_km2"] > 0].reset_index(drop=True)


def _stripe_world(rng, height, width, scale_id=None):
    country = rng.uniform(size=(height, width)) < 0.9
    eligible = (rng.uniform(0, 1, (height, width)) * (rng.uniform(size=(height, width)) < 0.7)).astype("float32")
    exclusions = {f"E{i}": rng.uniform(0, 1, (height, width)).astype("float32") for i in range(1, 7)}
    exclusions["E6"] = (exclusions["E6"] > 0.5).astype("float32")
    resources = {
        "wind_100": rng.uniform(1, 12, (height, width)).astype("float32"),
        "elevation": rng.uniform(0, 3000, (height, width)).astype("float32"),
    }
    resources["wind_100"][rng.uniform(size=(height, width)) < 0.05] = np.nan
    flags = {"dist_capped": rng.uniform(size=(height, width)) < 0.3}
    return country, eligible, exclusions, resources, flags


@pytest.mark.parametrize("stripe_pixels", [1, 7_000, 60_000, 4_000_000])
def test_the_striped_cell_sums_are_exactly_the_sums_of_the_whole_grid(monkeypatch, stripe_pixels):
    rng = np.random.default_rng(75)
    height, width = 45, 70  # a whole number of 0.05 degree cells (5 pixels), on the lattice
    transform = from_origin(cells.CELL_ORIGIN_LON + 100 * cells.CELL_DEG, cells.CELL_ORIGIN_LAT - 200 * cells.CELL_DEG, 0.01, 0.01)
    country, eligible, exclusions, resources, flags = _stripe_world(rng, height, width)
    monkeypatch.setattr(cells, "_STRIPE_PIXELS", stripe_pixels)
    got = cells.aggregate_to_cells(transform, country, eligible, exclusions, resources=resources, flags=flags)
    want = reference_aggregate_to_cells(transform, country, eligible, exclusions, resources=resources, flags=flags)
    pd.testing.assert_frame_equal(got, want, check_exact=True)
    assert len(got) > 0 and list(got.columns) == list(want.columns)


def test_the_striped_cell_sums_with_nothing_excluded_and_no_resources_equal_the_whole_grid(monkeypatch):
    rng = np.random.default_rng(76)
    transform = from_origin(cells.CELL_ORIGIN_LON + 100 * cells.CELL_DEG, cells.CELL_ORIGIN_LAT - 200 * cells.CELL_DEG, 0.01, 0.01)
    country = np.ones((20, 30), bool)
    eligible = rng.uniform(size=(20, 30)) < 0.5  # a boolean eligibility
    monkeypatch.setattr(cells, "_STRIPE_PIXELS", 1)
    pd.testing.assert_frame_equal(
        cells.aggregate_to_cells(transform, country, eligible, {}),
        reference_aggregate_to_cells(transform, country, eligible, {}),
        check_exact=True,
    )


@pytest.mark.parametrize("stripe_pixels", [1, 50_000, 4_000_000])
def test_the_striped_cell_sums_equal_the_whole_grid_at_the_coarse_scale_where_the_grid_starts_inside_a_cell(monkeypatch, stripe_pixels):
    from geofrea.core.scale import use_scale

    rng = np.random.default_rng(77)
    height, width = 55, 80  # starts 5 pixels inside a 0.1 degree cell on both axes and ends inside another: padded top, left, bottom and right
    transform = from_origin(cells.CELL_ORIGIN_LON + 100 * cells.CELL_DEG + 0.05, cells.CELL_ORIGIN_LAT - 200 * cells.CELL_DEG - 0.05, 0.01, 0.01)
    country, eligible, exclusions, resources, flags = _stripe_world(rng, height, width)
    monkeypatch.setattr(cells, "_STRIPE_PIXELS", stripe_pixels)
    with use_scale("0p1deg"):
        window = cells.lattice_window(transform, height, width)
        assert window.pad_top > 0 and window.pad_left > 0
        got = cells.aggregate_to_cells(transform, country, eligible, exclusions, resources=resources, flags=flags)
        want = reference_aggregate_to_cells(transform, country, eligible, exclusions, resources=resources, flags=flags)
    pd.testing.assert_frame_equal(got, want, check_exact=True)
