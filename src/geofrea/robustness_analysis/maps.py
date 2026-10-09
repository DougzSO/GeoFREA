"""Robustness maps of the central land scenario: max regret, satisficing, top-k flags, classes and the sub-family regrets (T-R4; D-F7-024, A-07, A-08).

Reads `robustness_<tech>__<role>.parquet` (F7) and writes, per technology and window role (`core`, `sensitivity`), under
`outputs/<ISO3>/robustness_analysis/`:

  - `artifacts/<map>_<tech>__<role>.tif`: COG on the lattice of the active scale, nodata where a cell is not a candidate or the value is null;
    `<map>` is `max_regret`, `satisficing`, `topk_nominal`, `topk_robust` (1 in the set, 0 outside it), `cell_class` (a code, see `CLASS_CODES`),
    `max_regret_climate_only`, `max_regret_techno_only` and `n_failing_members`;
  - `figures/<map>_<tech>__<window>__na__na.png`: with `figures: all` every map, with `summary` the max regret, the satisficing, the
    robust top-k and the classes, with `none` nothing.

The rasters are always written; a map with no value (a null `tau` or `top_k_percent`) gets an all-nodata raster and no figure.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from geofrea.core import paths as core_paths
from geofrea.land_eligibility.map_raster import (
    MapError,
    cell_grid,
    check_figures_mode,
    plot_grid,
    write_cog,
)

CLASS_CODES = {"ranked": 0, "climate_fragile": 1, "climate_data_invalid": 2, "infeasible_at_f0": 3}
# map -> (column, label, colormap, shown in the `summary` mode)
MAPS = {
    "max_regret": ("mr", "max regret MR (relative)", "magma_r", True),
    "satisficing": ("sr", "satisficing robustness SR", "viridis", True),
    "topk_nominal": ("topk_nominal", "nominal top-k (1 = in)", "Greens", False),
    "topk_robust": ("topk_robust", "robust top-k (1 = in)", "Greens", True),
    "cell_class": ("cell_class", "class", "tab10", True),
    "max_regret_climate_only": ("mr_clim", "MR_clim (relative)", "magma_r", False),
    "max_regret_techno_only": ("mr_tech", "MR_tech (relative)", "magma_r", False),
    "n_failing_members": ("n_failing_members", "members below CF_min", "Reds", False),
}


class RobustnessMapsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    figures_mode: str
    rasters: dict[str, Path]
    figures: list[Path]


def _values(table: pd.DataFrame, column: str) -> np.ndarray:
    if column == "cell_class":
        return table[column].map(CLASS_CODES).astype("float64").to_numpy()
    return pd.to_numeric(table[column], errors="coerce").astype("float64").to_numpy()


def build_robustness_maps(
    iso: str,
    technologies: tuple[str, ...] | list[str],
    figures_mode: str,
    windows: dict[str, str],
    *,
    robustness_dir: Path | None = None,
    figures_dir: Path | None = None,
) -> RobustnessMapsSummary:
    """COG rasters and PNG maps of the F7 results, per technology and window role.

    Implements: T-R4 (F7 diagnostic figure; the thesis figure is made by F8).

    Args:
        iso: Country code.
        technologies: Technology keys of the run.
        figures_mode: `all`, `summary` or `none` (`settings.yaml` `figures`).
        windows: Window role -> `start-end` (`core`, `sensitivity`), used in the names of the figures.
        robustness_dir: Directory of the F7 tables (default: the F7 artifacts directory).
        figures_dir: Directory of the PNGs (default: the F7 figures directory).

    Raises:
        MapError: unknown `figures_mode` or a missing table.
    """
    check_figures_mode(figures_mode)
    artifacts = Path(
        robustness_dir or core_paths.phase_dir(iso, "robustness_analysis", "artifacts")
    )
    figures_dir = Path(figures_dir or core_paths.phase_dir(iso, "robustness_analysis", "figures"))
    rasters: dict[str, Path] = {}
    figures: list[Path] = []
    for tech in technologies:
        for role, window in windows.items():
            path = artifacts / f"robustness_{tech}__{role}.parquet"
            if not path.is_file():
                raise MapError(f"missing input {path}")
            table = pd.read_parquet(path)
            cell_ids = table["cell_id"].to_numpy()
            for name, (column, label, cmap, in_summary) in MAPS.items():
                values = _values(table, column)
                grid, row0, col0 = cell_grid(cell_ids, values)
                rasters[f"{name}_{tech}__{role}"] = write_cog(
                    artifacts / f"{name}_{tech}__{role}.tif", grid, row0, col0
                )
                wanted = figures_mode == "all" or (figures_mode == "summary" and in_summary)
                if wanted and np.isfinite(grid).any():
                    figures.append(
                        plot_grid(
                            grid,
                            row0,
                            col0,
                            f"{tech}: {label}, {window}, central land scenario",
                            label,
                            cmap,
                            figures_dir / f"{name}_{tech}__{window}__na__na.png",
                            categories={v: k for k, v in CLASS_CODES.items()}
                            if name == "cell_class"
                            else None,
                        )
                    )
    return RobustnessMapsSummary(
        country_code=iso, figures_mode=figures_mode, rasters=rasters, figures=figures
    )
