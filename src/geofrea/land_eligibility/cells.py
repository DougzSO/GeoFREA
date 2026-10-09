"""Global 0.05 degree cell lattice, stable `cell_id`, and 5 x 5 pixel aggregation (M-F3-01/03/04, S-06).

Cell identity. The decision unit is a 0.05 degree cell (S-06), exactly 5 x 5 pixels of the 0.01 degree
F2a grid (M-F2a-01); the scale check of V-07 uses 0.1 degree cells, 10 x 10 pixels (`core.scale`, the active scale).
Cells live on one global lattice anchored at the north-west corner (90 N, 180 W) (`core.constants.CELL_ORIGIN_*`):
`row` counts southward, `col` eastward,

    cell_id = row * n_cols + col,   n_cols = 7200, n_rows = 3600 at 0.05 degree (25,920,000 ids, fits int32)

so an id never depends on a country's extent, on the polygon (e.g. `mainland_only`) or on the run. The
0.05 degree lattice nests the 0.1 degree cells (2 x 2): `coarse_cell_id()`. A cell on a border has the same
id in both countries; the real key is (country, cell_id). All index arithmetic is on integers (edges are
multiples of the pixel size, so a rounded integer step count is exact) -- never on float coordinates compared for equality.
A grid that is a whole number of 0.05 degree cells need not be a whole number of 0.1 degree cells: `lattice_window` pads it to the
lattice of the scale, and a padded part has no land, so its area is zero.

Aggregation. `aggregate_to_cells()` is a pure function over arrays already on a snapped F2a grid; it knows
nothing about files, technologies or experiments. Areas are geodesic (M-F2a-02), per pixel row.
"""

from __future__ import annotations

from typing import NamedTuple

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
from geofrea.core.scale import active_scale

N_COLS: int = round(360.0 / CELL_DEG)  # 7200: the lattice of the default scale
N_ROWS: int = round(180.0 / CELL_DEG)  # 3600
COARSE_FACTOR: int = 2  # 0.1 degree cells (V-07) = 2 x 2 cells of the default lattice

_EPS = 1e-9


class GridNotOnLatticeError(ValueError):
    """The grid's edges are not on the 0.05 degree lattice or its size is not a whole number of cells."""


def cell_row_col(lat: np.ndarray | float, lon: np.ndarray | float) -> tuple[np.ndarray, np.ndarray]:
    """Row and column of the cell of the active scale containing each (lat, lon). Out-of-range points raise ValueError."""
    scale = active_scale()
    lat_a, lon_a = np.asarray(lat, dtype=float), np.asarray(lon, dtype=float)
    row = np.floor((CELL_ORIGIN_LAT - lat_a) / scale.cell_deg + _EPS).astype(np.int64)
    col = np.floor((lon_a - CELL_ORIGIN_LON) / scale.cell_deg + _EPS).astype(np.int64)
    # lat = -90 and lon = 180 sit exactly on the last edge: belong to the last row/column
    row = np.where(np.isclose(lat_a, -90.0), scale.n_rows - 1, row)
    col = np.where(np.isclose(lon_a, 180.0), scale.n_cols - 1, col)
    if ((row < 0) | (row >= scale.n_rows) | (col < 0) | (col >= scale.n_cols)).any():
        raise ValueError("point outside the global cell lattice")
    return row, col


def cell_id(row: np.ndarray | int, col: np.ndarray | int) -> np.ndarray:
    """Stable global id of cell (row, col) of the active scale."""
    return np.asarray(row, dtype=np.int64) * active_scale().n_cols + np.asarray(col, dtype=np.int64)


def row_col_from_id(ids: np.ndarray | int) -> tuple[np.ndarray, np.ndarray]:
    ids = np.asarray(ids, dtype=np.int64)
    n_cols = active_scale().n_cols
    return ids // n_cols, ids % n_cols


def cell_center(row: np.ndarray | int, col: np.ndarray | int) -> tuple[np.ndarray, np.ndarray]:
    """(lat_c, lon_c) of the cell centers of the active scale."""
    cell_deg = active_scale().cell_deg
    row, col = np.asarray(row, dtype=float), np.asarray(col, dtype=float)
    return CELL_ORIGIN_LAT - (row + 0.5) * cell_deg, CELL_ORIGIN_LON + (col + 0.5) * cell_deg


def coarse_cell_id(ids: np.ndarray | int) -> np.ndarray:
    """Id of the 0.1 degree cell (V-07) containing each 0.05 degree cell of the default lattice; on its own 3600-wide lattice."""
    ids = np.asarray(ids, dtype=np.int64)
    row, col = ids // N_COLS, ids % N_COLS
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
        raise GridNotOnLatticeError(
            f"grid {height}x{width} px is not a whole number of {k}x{k} cells"
        )
    row0 = (CELL_ORIGIN_LAT - transform.f) / CELL_DEG
    col0 = (transform.c - CELL_ORIGIN_LON) / CELL_DEG
    if abs(row0 - round(row0)) > 1e-6 or abs(col0 - round(col0)) > 1e-6:
        raise GridNotOnLatticeError(
            f"grid corner ({transform.f}, {transform.c}) is not on the {CELL_DEG} degree lattice"
        )
    return round(row0), round(col0)


class LatticeWindow(NamedTuple):
    """Where a pixel grid sits on the cell lattice of the active scale.

    `row0` and `col0` are the lattice row and column of the first cell; `pad_top` and `pad_left` are the pixels of that first cell that lie
    outside the grid; `n_rows` and `n_cols` count the cells that cover the grid; `k` is the pixels per cell side.
    """

    row0: int
    col0: int
    pad_top: int
    pad_left: int
    n_rows: int
    n_cols: int
    k: int
    height: int
    width: int


def lattice_window(transform: rasterio.Affine, height: int, width: int) -> LatticeWindow:
    """The cells of the active scale that cover a grid of `height` x `width` pixels.

    The grid must be a whole number of 0.05 degree cells on the 0.05 degree lattice (`grid_cell_origin`, the F2a snapping); at the 0.1 degree
    scale it may start and end inside a cell, which is then padded.

    Raises:
        GridNotOnLatticeError: the grid is not a whole number of 0.05 degree cells on that lattice.
    """
    grid_cell_origin(transform, height, width)
    k = active_scale().nesting_pixels
    pixel_deg = CELL_DEG / CELL_NESTING_PIXELS
    pix_row0 = round((CELL_ORIGIN_LAT - transform.f) / pixel_deg)
    pix_col0 = round((transform.c - CELL_ORIGIN_LON) / pixel_deg)
    pad_top, pad_left = pix_row0 % k, pix_col0 % k
    return LatticeWindow(
        row0=pix_row0 // k,
        col0=pix_col0 // k,
        pad_top=pad_top,
        pad_left=pad_left,
        n_rows=-(-(pad_top + height) // k),
        n_cols=-(-(pad_left + width) // k),
        k=k,
        height=height,
        width=width,
    )


def pad_to_window(a: np.ndarray, window: LatticeWindow, fill: float | bool = 0) -> np.ndarray:
    """`a` (one value per pixel of the grid) placed inside the whole cells of `window`, `fill` outside the grid."""
    out = np.full((window.n_rows * window.k, window.n_cols * window.k), fill, dtype=a.dtype)
    out[
        window.pad_top : window.pad_top + window.height,
        window.pad_left : window.pad_left + window.width,
    ] = a
    return out


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
            raise ValueError(
                f"exclusion {name} has shape {excluded.shape}, expected {eligible.shape}"
            )
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


def candidate_cells(cells: pd.DataFrame, min_eligible_area_km2: float) -> pd.DataFrame:
    """M-F3-04: keep cells with `eligible_area_km2 >= min_eligible_area_km2`."""
    return cells[cells["eligible_area_km2"] >= min_eligible_area_km2].reset_index(drop=True)
