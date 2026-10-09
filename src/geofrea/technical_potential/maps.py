"""Potential-density and capacity-factor maps of the central land scenario at the reference climate (T-R1; D-F5-015, A-07, A-08).

Reads `potential_<tech>__central.parquet` (member `m0`) and `cells_<tech>__central.parquet` (every country cell, for the extent
and the cell area) and writes, under
`outputs/<ISO3>/technical_potential/`:

  - `artifacts/potential_density_<tech>.tif`: `P_MW / cell_area_km2`, MW per km2 of cell (T-R1), Cloud Optimized GeoTIFF on the
    0.05 degree lattice, EPSG:4326, nodata where a cell is not a candidate (a technology without candidates gets an all-nodata raster and no figure);
  - `artifacts/capacity_factor_<tech>.tif`: `CF` at `m0`, same grid;
  - `figures/potential_density_<tech>__ref__na__na.png` and `figures/capacity_factor_<tech>__ref__na__na.png`.

`settings.yaml` `figures` decides the PNGs: `all` draws both, `summary` only the density map, `none` none. The rasters are artifacts
and are always written. A cell without a `m0` row cannot occur (the reference factors are 1, 0, 1 and never masked).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID
from geofrea.core import paths as core_paths
from geofrea.land_eligibility.map_raster import FIGURE_MODES, cell_grid, plot_grid, write_cog

CENTRAL = "central"


class PotentialMapsError(RuntimeError):
    """An input of the maps is missing or inconsistent (A-09)."""


class PotentialMapsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    figures_mode: str
    rasters: dict[str, Path]
    figures: list[Path]


def build_potential_maps(
    iso: str,
    technologies: tuple[str, ...] | list[str],
    figures_mode: str,
    *,
    potential_dir: Path | None = None,
    cells_dir: Path | None = None,
    figures_dir: Path | None = None,
) -> PotentialMapsSummary:
    """COG rasters and PNG maps of `P_MW / cell_area_km2` and `CF` at `m0`, central land scenario.

    Implements: T-R1 (F5 diagnostic figure; the thesis output is made by F8).

    Args:
        iso: Country code.
        technologies: Technology keys of the run.
        figures_mode: `all`, `summary` or `none` (`settings.yaml` `figures`).
        potential_dir: Directory of the potential tables (default: the F5 artifacts directory).
        cells_dir: Directory of the F3 cell tables (default: the F3 artifacts directory).
        figures_dir: Directory of the PNGs (default: the F5 figures directory).

    Raises:
        PotentialMapsError: unknown `figures_mode`, a missing table, or potential rows for cells the F3 table lacks.
    """
    if figures_mode not in FIGURE_MODES:
        raise PotentialMapsError(f"figures must be one of {FIGURE_MODES}, got {figures_mode!r}")
    artifacts = potential_dir or core_paths.phase_dir(iso, "technical_potential", "artifacts")
    cells_dir = cells_dir or core_paths.phase_dir(iso, "land_eligibility", "artifacts")
    figures_dir = figures_dir or core_paths.phase_dir(iso, "technical_potential", "figures")
    rasters: dict[str, Path] = {}
    figures: list[Path] = []
    for tech in technologies:
        potential_path = Path(artifacts) / f"potential_{tech}__{CENTRAL}.parquet"
        cells_path = Path(cells_dir) / f"cells_{tech}__{CENTRAL}.parquet"
        for needed in (potential_path, cells_path):
            if not needed.is_file():
                raise PotentialMapsError(f"missing input {needed}")
        table = pd.read_parquet(potential_path)
        reference = table[table["member"].astype(str) == REFERENCE_MEMBER_ID]
        cells = pd.read_parquet(cells_path, columns=["cell_id", "cell_area_km2"])
        merged = cells.merge(reference, on="cell_id", how="left", validate="one_to_one")
        if len(reference) != int(merged["P_MW"].notna().sum()):
            raise PotentialMapsError(
                f"{potential_path.name}: rows of cells absent from {cells_path.name}"
            )
        cell_ids = merged["cell_id"].to_numpy()
        density, row0, col0 = cell_grid(
            cell_ids, (merged["P_MW"] / merged["cell_area_km2"]).to_numpy()
        )
        cf, _, _ = cell_grid(cell_ids, merged["CF"].to_numpy())
        has_values = bool(np.isfinite(density).any())
        rasters[f"potential_density_{tech}"] = write_cog(
            Path(artifacts) / f"potential_density_{tech}.tif", density, row0, col0
        )
        rasters[f"capacity_factor_{tech}"] = write_cog(
            Path(artifacts) / f"capacity_factor_{tech}.tif", cf, row0, col0
        )
        if has_values and figures_mode in ("all", "summary"):
            figures.append(
                plot_grid(
                    density,
                    row0,
                    col0,
                    f"{tech}: technical potential density, reference climate, central land scenario",
                    "MW per km2 of cell",
                    "viridis",
                    Path(figures_dir) / f"potential_density_{tech}__ref__na__na.png",
                )
            )
        if has_values and figures_mode == "all":
            figures.append(
                plot_grid(
                    cf,
                    row0,
                    col0,
                    f"{tech}: capacity factor, reference climate, central land scenario",
                    "capacity factor",
                    "magma",
                    Path(figures_dir) / f"capacity_factor_{tech}__ref__na__na.png",
                )
            )
    return PotentialMapsSummary(
        country_code=iso, figures_mode=figures_mode, rasters=rasters, figures=figures
    )
