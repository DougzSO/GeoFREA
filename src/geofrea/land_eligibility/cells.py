"""Global 0.05 degree cell lattice, stable `cell_id`, and 5 x 5 pixel aggregation (M-F3-01/03/04, S-06).

Cell identity. The decision unit is a 0.05 degree cell (S-06), exactly 5 x 5 pixels of the 0.01 degree
F2a grid (M-F2a-01). Cells live on one global lattice anchored at the north-west corner (90 N, 180 W)
(`core.constants.CELL_ORIGIN_*`): `row` counts southward, `col` eastward,

    cell_id = row * N_COLS + col,   N_COLS = 7200, N_ROWS = 3600  (25,920,000 ids, fits int32)

so an id never depends on a country's extent, on the polygon (e.g. `mainland_only`) or on the run. The
same lattice nests the 0.1 degree V-07 cells (2 x 2): `coarse_cell_id()`. A cell on a border has the same
id in both countries; the real key is (country, cell_id). All index arithmetic is on integers (edges are
multiples of 0.05, so a rounded integer step count is exact) -- never on float coordinates compared for equality.

Aggregation. `aggregate_to_cells()` is a pure function over arrays already on a snapped F2a grid; it knows
nothing about files, technologies or experiments. Areas are geodesic (M-F2a-02), per pixel row.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import rasterio

from geofrea.core.constants import (
    CELL_DEG,
    CELL_NESTING_PIXELS,
    CELL_ORIGIN_LAT,
    CELL_ORIGIN_LON,
)
from geofrea.core.geodesy import wgs84_km_per_degree

N_COLS: int = round(360.0 / CELL_DEG)  # 7200
N_ROWS: int = round(180.0 / CELL_DEG)  # 3600
COARSE_FACTOR: int = 2  # 0.1 degree cells (V-07) = 2 x 2 cells

_EPS = 1e-9


class GridNotOnLatticeError(ValueError):
    """The grid's edges are not on the 0.05 degree lattice or its size is not a whole number of cells."""


def cell_row_col(lat: np.ndarray | float, lon: np.ndarray | float) -> tuple[np.ndarray, np.ndarray]:
    """Row and column of the cell containing each (lat, lon). Out-of-range points raise ValueError."""
    lat_a, lon_a = np.asarray(lat, dtype=float), np.asarray(lon, dtype=float)
    row = np.floor((CELL_ORIGIN_LAT - lat_a) / CELL_DEG + _EPS).astype(np.int64)
    col = np.floor((lon_a - CELL_ORIGIN_LON) / CELL_DEG + _EPS).astype(np.int64)
    # lat = -90 and lon = 180 sit exactly on the last edge: belong to the last row/column
    row = np.where(np.isclose(lat_a, -90.0), N_ROWS - 1, row)
    col = np.where(np.isclose(lon_a, 180.0), N_COLS - 1, col)
    if ((row < 0) | (row >= N_ROWS) | (col < 0) | (col >= N_COLS)).any():
        raise ValueError("point outside the global cell lattice")
    return row, col


def cell_id(row: np.ndarray | int, col: np.ndarray | int) -> np.ndarray:
    """Stable global id of cell (row, col)."""
    return np.asarray(row, dtype=np.int64) * N_COLS + np.asarray(col, dtype=np.int64)


def row_col_from_id(ids: np.ndarray | int) -> tuple[np.ndarray, np.ndarray]:
    ids = np.asarray(ids, dtype=np.int64)
    return ids // N_COLS, ids % N_COLS


def cell_center(row: np.ndarray | int, col: np.ndarray | int) -> tuple[np.ndarray, np.ndarray]:
    """(lat_c, lon_c) of the cell centers."""
    row, col = np.asarray(row, dtype=float), np.asarray(col, dtype=float)
    return CELL_ORIGIN_LAT - (row + 0.5) * CELL_DEG, CELL_ORIGIN_LON + (col + 0.5) * CELL_DEG


def coarse_cell_id(ids: np.ndarray | int) -> np.ndarray:
    """Id of the 0.1 degree cell (V-07) containing each 0.05 degree cell; on its own 3600-wide lattice."""
    row, col = row_col_from_id(ids)
    return (row // COARSE_FACTOR) * (N_COLS // COARSE_FACTOR) + col // COARSE_FACTOR


def pixel_row_area_km2(transform: rasterio.Affine, height: int) -> np.ndarray:
    """Geodesic area (km2) of one pixel for each of the `height` rows (M-F2a-02)."""
    rows = np.arange(height)
    lat_mid = transform.f + (rows + 0.5) * transform.e
    lat_km, lon_km = wgs84_km_per_degree(lat_mid)
    return abs(transform.a) * lon_km * abs(transform.e) * lat_km


def grid_cell_origin(transform: rasterio.Affine, height: int, width: int) -> tuple[int, int]:
    """(row0, col0) of the grid's north-west cell on the global lattice; validates the snapping."""
    k = CELL_NESTING_PIXELS
    if height % k or width % k:
        raise GridNotOnLatticeError(f"grid {height}x{width} px is not a whole number of {k}x{k} cells")
    row0 = (CELL_ORIGIN_LAT - transform.f) / CELL_DEG
    col0 = (transform.c - CELL_ORIGIN_LON) / CELL_DEG
    if abs(row0 - round(row0)) > 1e-6 or abs(col0 - round(col0)) > 1e-6:
        raise GridNotOnLatticeError(
            f"grid corner ({transform.f}, {transform.c}) is not on the {CELL_DEG} degree lattice"
        )
    return round(row0), round(col0)


def pixel_eligibility(
    exclusions: dict[str, np.ndarray], required_valid: list[np.ndarray] | None = None
) -> np.ndarray:
    """M-F3-01: `eligible = NOT (E1 OR ... OR E6) AND all required layers valid` (bool, pixel grid).

    `exclusions` maps a name (E1..E6) to a boolean array, True = excluded; `required_valid` are boolean
    arrays, True = the required layer has a value there.
    """
    shape = next(iter(exclusions.values())).shape if exclusions else None
    eligible = np.ones(shape, dtype=bool) if shape is not None else None
    for name, excluded in exclusions.items():
        if excluded.shape != eligible.shape:
            raise ValueError(f"exclusion {name} has shape {excluded.shape}, expected {eligible.shape}")
        eligible &= ~excluded.astype(bool)
    for valid in required_valid or []:
        eligible &= valid.astype(bool)
    return eligible


def _block_sum(a: np.ndarray, k: int) -> np.ndarray:
    h, w = a.shape
    return a.reshape(h // k, k, w // k, k).sum(axis=(1, 3))


def aggregate_to_cells(
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
    k = CELL_NESTING_PIXELS
    height, width = country_mask.shape
    row0, col0 = grid_cell_origin(transform, height, width)
    area_row = pixel_row_area_km2(transform, height)
    area = np.repeat(area_row[:, None], width, axis=1) * country_mask
    eligible_area = area * eligible

    n_r, n_c = height // k, width // k
    cell_area = _block_sum(area, k)
    el_area = _block_sum(eligible_area, k)

    rows_i, cols_i = np.meshgrid(np.arange(n_r) + row0, np.arange(n_c) + col0, indexing="ij")
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
        excluded[name] = _block_sum(area * mask.astype(bool), k)
        frame[f"excluded_area_km2_{name}"] = excluded[name].ravel()
    if excluded:
        names = list(excluded)
        stack = np.stack([excluded[n] for n in names])
        dominant = np.array(names, dtype=object)[stack.argmax(axis=0)]
        dominant = np.where(stack.max(axis=0) > 0, dominant, None)
        frame["dominant_exclusion"] = dominant.ravel()

    for name, values in (resources or {}).items():
        usable = eligible_area * np.isfinite(values)
        weighted = _block_sum(np.where(np.isfinite(values), values, 0.0) * usable, k)
        weight = _block_sum(usable, k)
        with np.errstate(invalid="ignore", divide="ignore"):
            frame[name] = np.where(weight > 0, weighted / weight, np.nan).ravel()
    for name, flag in (flags or {}).items():
        flagged = _block_sum(eligible_area * flag.astype(bool), k)
        with np.errstate(invalid="ignore", divide="ignore"):
            frame[name] = np.where(el_area > 0, flagged / el_area, np.nan).ravel()

    out = pd.DataFrame(frame)
    if "dominant_exclusion" in out:  # nullable string: <NA> when nothing is excluded in the cell
        out["dominant_exclusion"] = out["dominant_exclusion"].astype("string")
    return out[out["cell_area_km2"] > 0].reset_index(drop=True)


def candidate_cells(cells: pd.DataFrame, min_eligible_area_km2: float) -> pd.DataFrame:
    """M-F3-04: keep cells with `eligible_area_km2 >= min_eligible_area_km2`."""
    return cells[cells["eligible_area_km2"] >= min_eligible_area_km2].reset_index(drop=True)
