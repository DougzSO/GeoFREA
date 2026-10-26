"""Display resolution of the maps (COMMAND 67b): what is drawn is never what is analysed.

Three small, numpy-only pieces, none of which touches a total, an LCOE or an analysis artifact:

  - `DisplayLayer`: a descriptive layer at a finer resolution than the 0.05 degree cell (the 0.01 degree grid of F2a), drawn instead of the
    analysis grid when the analysis cell would cover more than `MAX_PX_PER_CELL` pixels of the image;
  - `smooth_masked`: bilinear interpolation of a continuous field with a mask (normalised convolution: the weights of the no-data cells are
    zero, so no-data never leaks into the values), for what is still blocky in the finest layer, or comes from a GCM;
  - `block_mean` / `check_aggregation`: the 0.01 -> 0.05 degree aggregation (the eligible-area weighted mean of F3, `aggregate_to_cells`)
    and the check that a display layer reproduces the value of the analysis.

Smoothing is for continuous fields only (capacity factor, densities, climate deltas); classes, categories and per-state maps are never
smoothed, and the subtitle of a smoothed map says so (`smoothing_note`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import ndimage

Extent = tuple[float, float, float, float]  # west, east, south, north

MAX_PX_PER_CELL = 4.0  # above this many image pixels per cell of a layer, the cell shows as a block
MAX_IMAGE_PIXELS = 25_000_000  # the smoothed field is never larger than this
SMOOTHING_MODES = ("auto", "off")
M_PER_DEG = 111_320.0  # metres of an equatorial degree (a display estimate, not an area)
MIN_WEIGHT = 0.5  # of the mask after the interpolation: where a pixel is closer to a no-data cell than to a data cell, it has no value
CF_TOLERANCE = (
    0.01  # a display layer of CF aggregated to the analysis cell is within 1% of its value
)


@dataclass(frozen=True)
class DisplayLayer:
    """A descriptive layer at its own resolution: `grid` (row 0 north, NaN without value) over `extent` (west, east, south, north)."""

    name: str
    grid: np.ndarray
    extent: Extent
    cell_deg: float

    def __post_init__(self) -> None:
        if self.grid.ndim != 2:
            raise ValueError("a display layer is a 2-D grid")
        if self.cell_deg <= 0:
            raise ValueError("the cell of a display layer is positive")


def cell_deg_of(shape: tuple[int, int], extent: Extent) -> float:
    """The cell of a grid, in degrees (the mean of its two sides)."""
    west, east, south, north = extent
    return ((east - west) / shape[1] + (north - south) / shape[0]) / 2.0


def px_per_cell(cell_deg: float, lat_deg: float, pixel_m: float) -> float:
    """Image pixels along one side of a cell of `cell_deg` at latitude `lat_deg`, for a pixel of `pixel_m` metres on the map."""
    side_m = cell_deg * M_PER_DEG * math.sqrt(max(math.cos(math.radians(lat_deg)), 0.05))
    return side_m / pixel_m


def needs_smoothing(
    px: float, continuous: bool, mode: str = "auto", coarse_source: bool = False
) -> bool:
    """Whether a continuous field is smoothed for display: `auto` smooths when a cell covers more than `MAX_PX_PER_CELL` pixels, or when
    the field comes from a GCM (`coarse_source`); `off` never. A field that is not continuous (classes, categories, states) is never smoothed."""
    if mode not in SMOOTHING_MODES:
        raise ValueError(f"display_smoothing is one of {SMOOTHING_MODES}, got {mode!r}")
    if not continuous or mode == "off":
        return False
    return coarse_source or px > MAX_PX_PER_CELL


def upsample_factor(px: float, shape: tuple[int, int]) -> int:
    """The integer factor that brings a cell to about one pixel (at least 2), within `MAX_IMAGE_PIXELS`."""
    factor = max(2, math.ceil(px))
    while factor > 2 and shape[0] * shape[1] * factor * factor > MAX_IMAGE_PIXELS:
        factor -= 1
    return factor


def smooth_masked(grid: np.ndarray, factor: int) -> np.ndarray:
    """`grid` (NaN where there is no value) interpolated bilinearly to `factor` times the cells, by normalised convolution.

    The values are interpolated together with the mask and divided by it, so a no-data cell weighs nothing and the result is always between the
    smallest and the largest value of the cells that count. A pixel whose weight is below `MIN_WEIGHT` (closer to no-data than to data) is NaN:
    the border between data and no-data stays at the edge of the cells, nothing is invented beyond it. Returns an array of `grid.shape * factor`.
    """
    if factor < 1:
        raise ValueError("the factor is a positive integer")
    data = np.asarray(grid, dtype="float64")
    valid = np.isfinite(data)
    if factor == 1 or not valid.any():
        return np.where(valid, data, np.nan)
    kw = {"order": 1, "mode": "nearest", "grid_mode": True}
    weight = ndimage.zoom(valid.astype("float64"), factor, **kw)
    total = ndimage.zoom(np.where(valid, data, 0.0), factor, **kw)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(weight >= MIN_WEIGHT, total / weight, np.nan)
    lo, hi = float(data[valid].min()), float(data[valid].max())
    return np.clip(out, lo, hi)


def block_mean(fine: np.ndarray, k: int, weight: np.ndarray | None = None) -> np.ndarray:
    """The mean of each k x k block of `fine`, weighted by `weight` (default: the pixels with a value count the same): the 0.01 -> 0.05
    aggregation of F3 (eligible-area weighted mean). A block with no weight, or no value, is NaN. The shape must be a multiple of k."""
    h, w = fine.shape
    if h % k or w % k:
        raise ValueError(f"the shape {fine.shape} is not a multiple of {k}")
    values = np.asarray(fine, dtype="float64")
    finite = np.isfinite(values)
    wt = finite.astype("float64") if weight is None else np.where(finite, weight, 0.0)

    def blocks(a):
        return a.reshape(h // k, k, w // k, k).sum(axis=(1, 3))

    total = blocks(np.where(finite, values, 0.0) * wt)
    den = blocks(wt)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, total / den, np.nan)


def block_sum(fine: np.ndarray, k: int) -> np.ndarray:
    """The sum of each k x k block (NaN counts as zero), e.g. the eligible area of a cell."""
    h, w = fine.shape
    if h % k or w % k:
        raise ValueError(f"the shape {fine.shape} is not a multiple of {k}")
    return np.where(np.isfinite(fine), fine, 0.0).reshape(h // k, k, w // k, k).sum(axis=(1, 3))


@dataclass(frozen=True)
class AggregationCheck:
    """How well a display layer reproduces the analysis once aggregated to the analysis cell."""

    name: str
    cells: int
    max_rel_diff: float
    tolerance: float
    ok: bool


def check_aggregation(
    name: str,
    fine: np.ndarray,
    analysis: np.ndarray,
    k: int,
    *,
    weight: np.ndarray | None = None,
    tolerance: float = CF_TOLERANCE,
    how: str = "mean",
) -> AggregationCheck:
    """Aggregate the display layer `fine` to the analysis cell (`k` fine pixels per side) and compare it with `analysis`, cell by cell.

    The largest relative difference over the cells that have a value in both must be within `tolerance` (1% for a capacity factor, 0 for an
    eligible area: use `tolerance=1e-9`). A cell with a value in one and none in the other is a failure (`ok` False, `max_rel_diff` inf).
    `how` is `mean` (weighted, for an intensive quantity) or `sum` (an area or a capacity; a block with no value is NaN).
    """
    if how == "sum":
        mean = np.where(
            block_sum(np.isfinite(fine).astype(float), k) > 0, block_sum(fine, k), np.nan
        )
    else:
        mean = block_mean(fine, k, weight)
    both = np.isfinite(mean) & np.isfinite(analysis)
    mismatch = int((np.isfinite(mean) ^ np.isfinite(analysis)).sum())
    if not both.any():
        return AggregationCheck(name, 0, math.inf, tolerance, False)
    ref = np.abs(analysis[both])
    diff = np.abs(mean[both] - analysis[both])
    rel = np.where(ref > 0, diff / np.where(ref > 0, ref, 1.0), diff)
    worst = math.inf if mismatch else float(rel.max())
    return AggregationCheck(name, int(both.sum()), worst, tolerance, worst <= tolerance)
