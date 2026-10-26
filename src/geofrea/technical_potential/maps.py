"""Maps of the technical potential at the central land scenario and the reference climate (T-R1; D-F5-015, A-07, A-08; COMMAND 60).

Reads `potential_<tech>__central.parquet` (member `m0`) and `cells_<tech>__central.parquet` (every country cell, for the extent
and the cell area) and writes, under
`outputs/<ISO3>/technical_potential/`:

  - `artifacts/potential_density_<tech>.tif`: `P_MW / cell_area_km2`, MW per km2 of cell (T-R1), Cloud Optimized GeoTIFF on the
    0.05 degree lattice, EPSG:4326, nodata where a cell is not a candidate (a technology without candidates gets an all-nodata raster and no figure);
  - `artifacts/capacity_factor_<tech>.tif`: `CF` at `m0`, same grid;
  - `figures/`: the maps of `technical_potential/absolute_maps.py` (densities per cell and per state, circles of the totals) and the map of the
    capacity factor, all in the common style of `viz/mapstyle.py`.

`settings.yaml` `figures` decides the PNGs: `all` draws everything, `summary` only the two density maps per cell, `none` none. The rasters are
artifacts and are always written. A cell without a `m0` row cannot occur (the reference factors are 1, 0, 1 and never masked).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID
from geofrea.core import paths as core_paths
from geofrea.core.config_schemas import AbsoluteMapsConfig
from geofrea.land_eligibility.map_raster import FIGURE_MODES, cell_grid, write_cog
from geofrea.technical_potential.absolute_maps import (
    SUBTITLE_CLIMATE,
    build_absolute_maps,
    build_cell_density_maps,
    capacity_factor_name,
    country_geometry,
    draw_cell_density_map,
    load_neighbours,
    map_context,
)
from geofrea.technical_potential.display_layers import load_display_layer

CENTRAL = "central"


class PotentialMapsError(RuntimeError):
    """An input of the maps is missing or inconsistent (A-09)."""


class PotentialMapsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    figures_mode: str
    rasters: dict[str, Path]
    figures: list[Path]
    # D-F5-029: the maps of capacity and energy (per cell and per state) and the files of their class limits, by artifact key, and the sum checks
    # of each technology (the cells and the states against the F5 national total); empty when `figures` is not `all` or no admin1 units were given
    absolute_figures: dict[str, Path] = {}
    absolute_checks: dict[str, Any] = {}


def build_potential_maps(
    iso: str,
    technologies: tuple[str, ...] | list[str],
    figures_mode: str,
    *,
    potential_dir: Path | None = None,
    cells_dir: Path | None = None,
    figures_dir: Path | None = None,
    units: gpd.GeoDataFrame | None = None,
    absolute_maps: AbsoluteMapsConfig | None = None,
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
        units: The admin1 units of the country (`read_units` of the F3 admin1 layer); with `absolute_maps` and `figures_mode == "all"` the state
            maps are drawn (D-F5-029); without them the territory is the union of the cells.
        absolute_maps: Classification of those maps (`experiments.yaml` `absolute_maps`).

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
    neighbours = load_neighbours(iso) if figures_mode != "none" else None
    ctx = None  # the contiguous territory, the extent and the neighbours cut to it: found once per country, used by every map
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
        if has_values and figures_mode == "all":
            ctx = ctx or map_context(country_geometry(units, cell_ids), neighbours)
            figures.append(
                draw_cell_density_map(
                    cell_ids,
                    merged["CF"].to_numpy(),
                    ctx,
                    iso=iso,
                    tech=tech,
                    variable="Capacity factor",
                    label="Capacity factor",
                    kind="capacity_factor",
                    subtitle=f"Central scenario · {SUBTITLE_CLIMATE}",
                    total_text=None,
                    path=Path(figures_dir) / capacity_factor_name(iso, tech),
                    data_source=f"F5 potential_{tech}__{CENTRAL}, member m0",
                    display_layer=load_display_layer(artifacts, "capacity-factor", tech),
                    display_smoothing=(
                        absolute_maps.display_smoothing if absolute_maps is not None else "auto"
                    ),
                )[0]
            )
        if has_values and figures_mode == "summary":
            written, _ = build_cell_density_maps(
                iso,
                tech,
                artifacts,
                cells_dir,
                Path(figures_dir),
                units,
                neighbours,
                ctx,
                display_smoothing=(
                    absolute_maps.display_smoothing if absolute_maps is not None else "auto"
                ),
            )
            figures.extend(p for k, p in written.items() if "density" in k)
    absolute_figures: dict[str, Path] = {}
    absolute_checks: dict[str, Any] = {}
    if figures_mode == "all" and units is not None and absolute_maps is not None:
        ctx = ctx or map_context(country_geometry(units, np.empty(0, dtype="int64")), neighbours)
        for tech in technologies:
            written, content = build_absolute_maps(
                iso,
                tech,
                Path(artifacts),
                Path(cells_dir),
                Path(figures_dir),
                units,
                absolute_maps,
                neighbours,
                ctx,
            )
            absolute_figures.update(written)
            absolute_checks[tech] = content["sum_checks"]
    return PotentialMapsSummary(
        country_code=iso,
        figures_mode=figures_mode,
        rasters=rasters,
        figures=figures,
        absolute_figures=absolute_figures,
        absolute_checks=absolute_checks,
    )
