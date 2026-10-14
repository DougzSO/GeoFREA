"""Cell rasters drawn in the thesis style: T-R1, T-R3, T-R4 and T-R11 place a value per cell on the lattice of the active scale (M-F8-02).

The maps read the Cloud Optimized GeoTIFFs that the map phases registered (`read_grid`), or place the values of a persisted table on the lattice
(`table_grid`). The drawing is `draw_grid`; no figure sets its own look.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

from geofrea.core.constants import CELL_ORIGIN_LAT, CELL_ORIGIN_LON
from geofrea.core.scale import active_scale

Extent = tuple[float, float, float, float]  # west, east, south, north


def grid_extent(grid: np.ndarray, row0: int, col0: int) -> Extent:
    """The extent in degrees of a grid placed on the lattice of the active scale with its first cell at `(row0, col0)`."""
    cell = active_scale().cell_deg
    west = CELL_ORIGIN_LON + col0 * cell
    north = CELL_ORIGIN_LAT - row0 * cell
    return west, west + grid.shape[1] * cell, north - grid.shape[0] * cell, north


def read_grid(path: Path) -> tuple[np.ndarray, Extent]:
    """The first band of a raster, NaN where it has no value, and its extent."""
    with rasterio.open(path) as source:
        band = source.read(1, masked=True)
        west, south, east, north = source.bounds
    return np.ma.filled(band.astype("float64"), np.nan), (west, east, south, north)


def table_grid(cell_ids: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, Extent]:
    """`values` of the cells placed on the lattice, NaN where no cell, and the extent."""
    ids = np.asarray(cell_ids, dtype=np.int64)
    n_cols = active_scale().n_cols
    rows, cols = (
        ids // n_cols,
        ids % n_cols,
    )  # the cell identifier is row * n_cols + col on the lattice of the scale
    row0, col0 = int(rows.min()), int(cols.min())
    grid = np.full((int(rows.max()) - row0 + 1, int(cols.max()) - col0 + 1), np.nan)
    grid[rows - row0, cols - col0] = np.asarray(values, dtype="float64")
    return grid, grid_extent(grid, row0, col0)


def draw_grid(
    fig,
    ax,
    grid: np.ndarray,
    extent: Extent,
    *,
    cmap: str,
    label: str,
    vmin: float | None = None,
    vmax: float | None = None,
    colorbar: bool = True,
):
    """A grid as an image with the degrees on the axes and, by default, a colour bar named `label`."""
    image = ax.imshow(
        np.ma.masked_invalid(grid),
        extent=extent,
        origin="upper",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        interpolation="nearest",
    )
    ax.set_xlabel("Longitude (deg)")
    ax.set_ylabel("Latitude (deg)")
    ax.grid(False)
    if colorbar:
        fig.colorbar(image, ax=ax, label=label, shrink=0.85)
    return image


def map_aspect(grid: np.ndarray) -> float:
    """The height over the width of a figure that holds one map and its colour bar."""
    return float(np.clip(grid.shape[0] / max(grid.shape[1], 1) * 0.85 + 0.12, 0.35, 1.1))
