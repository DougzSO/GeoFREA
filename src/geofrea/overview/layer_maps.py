"""One map per file of the cost-driver layers of a country (H-5; A-08, METHODOLOGY Section 11).

Written under `outputs/<ISO3>/overview/figures/layers/`, named `<map>__na__na__na.png` (the layers do not depend on a climate window,
scenario or model): `dist_grid_km` and `dist_road_km` from the F2b rasters (`siting_layers/artifacts/`; km, uncapped, OQ-040).

The eligible share and the excluded share of each exclusion are figures of F3 now (`land_eligibility/figures.py`, `overview/figures/layers/`).
`settings.yaml` `figures`: `all` draws the two maps, `summary` and `none` nothing. An input that does not exist is logged and skipped here (the
overview table shows what is missing); nothing is drawn for it and nothing is invented.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio

from geofrea.core import paths as core_paths
from geofrea.core.constants import CELL_ORIGIN_LAT, CELL_ORIGIN_LON
from geofrea.core.scale import active_scale
from geofrea.land_eligibility.cells import row_col_from_id

logger = logging.getLogger("geofrea.overview.layer_maps")

# E1 to E6 as M-F2b-01 names them (the order of `exclusions` in technologies.yaml), for the file names
EXCLUSION_LABELS = {
    "E1": "protected",
    "E2": "water",
    "E3": "riparian",
    "E4": "slope",
    "E5": "land_cover",
    "E6": "population",
}
COST_LAYERS = (
    ("dist_grid_km", "Distance to the transmission grid (km)"),
    ("dist_road_km", "Distance to the nearest road (km)"),
)
_MAX_PIXELS = 700  # longest side of a drawn raster; the file is read with decimation, never resampled by value


def _cell_grid(
    cells: pd.DataFrame, values: np.ndarray
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    rows, cols = row_col_from_id(cells["cell_id"].to_numpy())
    row0, col0 = int(rows.min()), int(cols.min())
    grid = np.full((int(rows.max()) - row0 + 1, int(cols.max()) - col0 + 1), np.nan)
    grid[rows - row0, cols - col0] = values
    west = CELL_ORIGIN_LON + col0 * active_scale().cell_deg
    north = CELL_ORIGIN_LAT - row0 * active_scale().cell_deg
    return grid, (
        west,
        west + grid.shape[1] * active_scale().cell_deg,
        north - grid.shape[0] * active_scale().cell_deg,
        north,
    )


def _draw(
    grid: np.ndarray, extent, title: str, label: str, cmap: str, path: Path, vmin=None, vmax=None
) -> Path:
    fig, ax = plt.subplots(figsize=(7, 6))
    image = ax.imshow(
        np.ma.masked_invalid(grid), extent=extent, origin="upper", cmap=cmap, vmin=vmin, vmax=vmax
    )
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("Longitude (deg)")
    ax.set_ylabel("Latitude (deg)")
    fig.colorbar(image, ax=ax, label=label, shrink=0.8)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def _cost_map(raster: Path, title: str, out: Path) -> Path:
    with rasterio.open(raster) as src:
        step = max(1, max(src.height, src.width) // _MAX_PIXELS)
        data = src.read(1, out_shape=(src.height // step, src.width // step), masked=True).astype(
            "float64"
        )
        b = src.bounds
    return _draw(
        np.ma.filled(data, np.nan), (b.left, b.right, b.bottom, b.top), title, "km", "viridis", out
    )


def build_layer_maps(
    iso: str,
    figures_mode: str,
    *,
    siting_dir: Path | None = None,
    out_dir: Path | None = None,
) -> list[Path]:
    """The per-layer maps allowed by `figures_mode`.

    Implements: H-5 (diagnostic maps), A-08.

    Raises:
        ValueError: unknown `figures_mode`, or a cell table without the excluded-area columns it should have.
    """
    if figures_mode not in ("all", "summary", "none"):
        raise ValueError(f"figures must be all, summary or none, got {figures_mode!r}")
    if figures_mode == "none":
        return []
    siting_dir = siting_dir or core_paths.phase_dir(iso, "siting_layers", "artifacts")
    out_dir = out_dir or core_paths.phase_dir(iso, "overview", "figures") / "layers"
    written: list[Path] = []
    if figures_mode == "all":
        for name, title in COST_LAYERS:
            raster = Path(siting_dir) / f"{name}.tif"
            if not raster.is_file():
                logger.warning("%s: no %s, its map is not drawn", iso, raster.name)
                continue
            written.append(
                _cost_map(raster, f"{iso}: {title}", out_dir / f"{name}__na__na__na.png")
            )
    return written
