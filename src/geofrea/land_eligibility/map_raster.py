"""Cell rasters and PNG maps on the lattice of the active scale, shared by the map phases (A-07, A-08, V-07).

A map phase places a value per cell on the lattice spanned by the country's cells, writes it as a Cloud Optimized GeoTIFF in EPSG:4326 (nodata
where a cell has no value) and, when `settings.yaml` `figures` allows, draws a PNG. The cell size is `active_scale().cell_deg`, so the same
code draws the 0.05 and the 0.1 degree runs.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import numpy as np
import rasterio
from matplotlib.colors import to_rgba

from geofrea.core.constants import CELL_ORIGIN_LAT, CELL_ORIGIN_LON, NODATA_FLOAT
from geofrea.core.raster_io import safe_raster_write
from geofrea.core.scale import active_scale
from geofrea.land_eligibility.cells import row_col_from_id
from geofrea.viz import mapstyle as ms
from geofrea.viz.context import country_context

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


def draw_grid(
    grid: np.ndarray,
    row0: int,
    col0: int,
    *,
    iso: str,
    variable: str,
    label: str,
    kind: str,
    path: Path,
    technology: str = "",
    tech: str | None = None,
    subtitle: str = "",
    categories: Mapping[int, str] | None = None,
) -> Path:
    """A PNG of `grid` (a map of the cells of F3 to F7) in the common map style (`viz/mapstyle.py`): the colours and the scale of `kind`, the
    title of the form `Country · Technology · Variable`, the compass, the scale bar and the neighbours. These maps are diagnostics of a phase
    (A-08). With `categories` (value -> name) the values are drawn as classes with a legend of the patches instead of a colour bar."""
    cell = active_scale().cell_deg
    west = CELL_ORIGIN_LON + col0 * cell
    north = CELL_ORIGIN_LAT - row0 * cell
    extent = (west, west + grid.shape[1] * cell, north - grid.shape[0] * cell, north)
    cells = np.flatnonzero(np.isfinite(grid).ravel())
    rows, cols = np.divmod(cells, grid.shape[1])
    ids = (rows + row0) * active_scale().n_cols + cols + col0
    ctx = country_context(iso, ids)
    common = {
        "iso": iso,
        "technology": technology,
        "variable": variable,
        "neighbours": ctx.neighbours,
        "extent": ctx.extent,
        "contiguous": False,
    }
    if categories:
        codes = sorted(categories)
        colours = ms.class_colours(len(codes))
        spec = ms.ClassedLegend(
            title=label, labels=tuple(categories[c] for c in codes), colours=tuple(colours)
        )
        side, below = ms.legend_space(spec)
        canvas = ms.new_map(
            ctx.polygon,
            subtitle=ms.format_subtitle(subtitle, ms.resolution_note(cell_deg=cell)),
            legend_side_mm=side,
            legend_below_mm=below,
            **common,
        )
        rgba = np.zeros(grid.shape + (4,))
        for code, colour in zip(codes, colours, strict=True):
            rgba[grid == code] = to_rgba(colour)
        canvas.draw_raster(rgba, extent)
        ms.draw_classed_legend(canvas, spec)
    else:
        canvas = ms.raster_map(
            grid,
            extent,
            ctx.polygon,
            label=label,
            kind=kind,
            tech=tech,
            subtitle=subtitle,
            resolution=ms.resolution_note(cell_deg=cell),
            **common,
        )
    canvas.meta["status"] = "diagnostic"
    return ms.save_png(canvas, path)
