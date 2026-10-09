"""Cell rasters and PNG maps on the lattice of the active scale, shared by the map phases (A-07, A-08, V-07).

A map phase places a value per cell on the lattice spanned by the country's cells, writes it as a Cloud Optimized GeoTIFF in EPSG:4326 (nodata
where a cell has no value) and, when `settings.yaml` `figures` allows, draws a PNG. The cell size is `active_scale().cell_deg`, so the same
code draws the 0.05 and the 0.1 degree runs.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch

from geofrea.core.constants import CELL_ORIGIN_LAT, CELL_ORIGIN_LON, NODATA_FLOAT
from geofrea.core.raster_io import safe_raster_write
from geofrea.core.scale import active_scale
from geofrea.land_eligibility.cells import row_col_from_id

FIGURE_MODES = ("all", "summary", "none")


class MapError(RuntimeError):
    """An input of a map is missing or inconsistent (A-09)."""


def check_figures_mode(mode: str) -> None:
    if mode not in FIGURE_MODES:
        raise MapError(f"figures must be one of {FIGURE_MODES}, got {mode!r}")


def cell_grid(cell_ids: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, int, int]:
    """`values` placed on the lattice spanned by the cells; returns the array (NaN where no cell) and its (row0, col0)."""
    rows, cols = row_col_from_id(cell_ids)
    row0, col0 = int(rows.min()), int(cols.min())
    out = np.full((int(rows.max()) - row0 + 1, int(cols.max()) - col0 + 1), np.nan, dtype="float64")
    out[rows - row0, cols - col0] = values
    return out, row0, col0


def write_cog(path: Path, grid: np.ndarray, row0: int, col0: int) -> Path:
    """`grid` as a float32 GeoTIFF on the lattice of the active scale; NaN becomes nodata."""
    cell = active_scale().cell_deg
    transform = rasterio.Affine(
        cell, 0, CELL_ORIGIN_LON + col0 * cell, 0, -cell, CELL_ORIGIN_LAT - row0 * cell
    )
    data = np.where(np.isnan(grid), NODATA_FLOAT, grid).astype("float32")
    with safe_raster_write(
        path,
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=NODATA_FLOAT,
    ) as dst:
        dst.write(data, 1)
    return path


def plot_grid(
    grid: np.ndarray,
    row0: int,
    col0: int,
    title: str,
    label: str,
    cmap: str,
    path: Path,
    *,
    categories: Mapping[int, str] | None = None,
) -> Path:
    """A PNG of `grid`; with `categories` (value -> name) the values are drawn as classes with a legend instead of a colour bar."""
    cell = active_scale().cell_deg
    west = CELL_ORIGIN_LON + col0 * cell
    north = CELL_ORIGIN_LAT - row0 * cell
    extent = (west, west + grid.shape[1] * cell, north - grid.shape[0] * cell, north)
    fig, ax = plt.subplots(figsize=(7, 6))
    masked = np.ma.masked_invalid(grid)
    if categories:
        codes = sorted(categories)
        colors = plt.get_cmap("tab10")(np.arange(len(codes)))
        norm = BoundaryNorm([c - 0.5 for c in codes] + [codes[-1] + 0.5], len(codes))
        ax.imshow(masked, extent=extent, origin="upper", cmap=ListedColormap(colors), norm=norm)
        ax.legend(
            handles=[Patch(color=colors[i], label=categories[c]) for i, c in enumerate(codes)],
            loc="lower left",
            fontsize=7,
        )
    else:
        image = ax.imshow(masked, extent=extent, origin="upper", cmap=cmap)
        fig.colorbar(image, ax=ax, label=label, shrink=0.8)
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("Longitude (deg)")
    ax.set_ylabel("Latitude (deg)")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path
