"""LCOE maps of the central land scenario at the reference climate and by SSP, and the nominal supply curve (T-R11; D-F6-015, D-F7-024, A-07, A-08).

Reads `lcoe_summary_<tech>.parquet` (F6), `supply_curve_<tech>.parquet`, `cells_<tech>__central.parquet` (every country cell, for the extent)
and `members.yaml` (F4), and writes, under `outputs/<ISO3>/lcoe_modeling/`:

  - `artifacts/lcoe_<stat>_<tech>.tif`, `<stat>` = `nominal`, `p10`, `p50`, `p90`: the LCOE of the reference member `m0` in USD2024/MWh,
    COG on the lattice of the active scale, nodata where a cell is not a candidate or its LCOE is not finite;
  - `artifacts/lcoe_nominal_<tech>__<ssp>.tif`: the nominal LCOE of the core window, the median over the members of that SSP (all GCMs);
  - `figures/<ISO3>_F6_lcoe-nominal_<tech>_central_ref.png` (T-R11), and with `figures: all` the three quantile maps, the maps by SSP and
    `<ISO3>_F6_supply-curve_<tech>_central_ref.png`, in the common style of `viz/mapstyle.py` (diagnostics, A-08).

`settings.yaml` `figures` decides the PNGs: `all` draws all of them, `summary` only the nominal map at `m0`, `none` none. The rasters are
always written.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict

from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID
from geofrea.core import paths as core_paths
from geofrea.land_eligibility.map_raster import (
    MapError,
    cell_grid,
    check_figures_mode,
    draw_grid,
    write_cog,
)
from geofrea.viz import mapstyle as ms
from geofrea.viz.charts import new_chart, step_curve
from geofrea.viz.context import technology_name

CENTRAL = "central"
STATISTICS = {"nominal": "lcoe_nominal", "p10": "lcoe_p10", "p50": "lcoe_p50", "p90": "lcoe_p90"}
LABEL = "LCOE (USD2024/MWh)"


class LcoeMapsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    figures_mode: str
    rasters: dict[str, Path]
    figures: list[Path]


def slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", label.lower())


def _finite(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype="float64")
    return np.where(np.isfinite(values), values, np.nan)


def _supply_curve_figure(curve: pd.DataFrame, iso: str, tech: str, path: Path) -> Path:
    """The nominal supply curve as a chart in the common style: the cumulative capacity against the LCOE of the next block."""
    finite = curve[np.isfinite(curve["lcoe_nominal"])]
    chart = new_chart(
        iso=iso,
        technology=technology_name(tech),
        variable="Nominal supply curve",
        subtitle="Reference climate · central land scenario · diagnostic",
        plot_height_mm=70.0,
        source="Source: F6 supply curve, member m0",
    )
    step_curve(
        chart,
        finite["cum_P_GW"],
        finite["lcoe_nominal"],
        xlabel="Cumulative capacity (GW)",
        ylabel=LABEL,
        colour=ms.colormap_for("lcoe")(0.3),
        meaning="nominal LCOE",
    )
    chart.meta["status"] = "diagnostic"
    return ms.save_png(chart, path)


def build_lcoe_maps(
    iso: str,
    technologies: tuple[str, ...] | list[str],
    figures_mode: str,
    core_window: str,
    *,
    lcoe_dir: Path | None = None,
    cells_dir: Path | None = None,
    members_file: Path | None = None,
    figures_dir: Path | None = None,
) -> LcoeMapsSummary:
    """COG rasters and PNG maps of the LCOE at `m0` (nominal, p10, p50, p90) and the nominal LCOE of the core window by SSP.

    Implements: T-R11 (F6 diagnostic figure; the thesis figure is made by F8).

    Args:
        iso: Country code.
        technologies: Technology keys of the run.
        figures_mode: `all`, `summary` or `none` (`settings.yaml` `figures`).
        core_window: `start-end` of the core window (`experiments.yaml` `windows.core`).
        lcoe_dir: Directory of the F6 tables (default: the F6 artifacts directory).
        cells_dir: Directory of the F3 cell tables (default: the F3 artifacts directory).
        members_file: `members.yaml` of F4 (default: the F4 artifacts directory).
        figures_dir: Directory of the PNGs (default: the F6 figures directory).

    Raises:
        MapError: unknown `figures_mode`, a missing table, rows of cells the F3 table lacks, or a core window with no member.
    """
    check_figures_mode(figures_mode)
    artifacts = Path(lcoe_dir or core_paths.phase_dir(iso, "lcoe_modeling", "artifacts"))
    cells_dir = Path(cells_dir or core_paths.phase_dir(iso, "land_eligibility", "artifacts"))
    figures_dir = Path(figures_dir or core_paths.phase_dir(iso, "lcoe_modeling", "figures"))
    members_file = Path(
        members_file or core_paths.phase_dir(iso, "climate_forcing", "artifacts") / "members.yaml"
    )
    if not members_file.is_file():
        raise MapError(f"missing input {members_file}")
    entries = yaml.safe_load(members_file.read_text(encoding="utf-8"))["members"]
    by_ssp: dict[str, list[str]] = {}
    for entry in entries:
        if str(entry["window"]) == core_window and entry["member"] != REFERENCE_MEMBER_ID:
            by_ssp.setdefault(str(entry["ssp"]), []).append(entry["member"])
    if not by_ssp:
        raise MapError(f"members.yaml has no member of the core window {core_window}")
    rasters: dict[str, Path] = {}
    figures: list[Path] = []
    for tech in technologies:
        summary_path = artifacts / f"lcoe_summary_{tech}.parquet"
        curve_path = artifacts / f"supply_curve_{tech}.parquet"
        cells_path = cells_dir / f"cells_{tech}__{CENTRAL}.parquet"
        for needed in (summary_path, curve_path, cells_path):
            if not needed.is_file():
                raise MapError(f"missing input {needed}")
        table = pd.read_parquet(summary_path)
        table = table.assign(member=table["member"].astype(str))
        cells = pd.read_parquet(cells_path, columns=["cell_id"])
        if not table["cell_id"].isin(cells["cell_id"]).all():
            raise MapError(f"{summary_path.name}: rows of cells absent from {cells_path.name}")
        cell_ids = cells["cell_id"].to_numpy()
        reference = table[table["member"] == REFERENCE_MEMBER_ID].set_index("cell_id")
        for stat, column in STATISTICS.items():
            values = _finite(reference[column].reindex(cell_ids).to_numpy())
            grid, row0, col0 = cell_grid(cell_ids, values)
            rasters[f"lcoe_{stat}_{tech}"] = write_cog(
                artifacts / f"lcoe_{stat}_{tech}.tif", grid, row0, col0
            )
            wanted = (stat == "nominal" and figures_mode in ("all", "summary")) or (
                stat != "nominal" and figures_mode == "all"
            )
            if wanted and np.isfinite(grid).any():
                figures.append(
                    draw_grid(
                        grid,
                        row0,
                        col0,
                        iso=iso,
                        technology=technology_name(tech),
                        variable="Nominal LCOE" if stat == "nominal" else f"LCOE, {stat.upper()}",
                        label=LABEL,
                        kind="lcoe",
                        subtitle="Reference climate · central land scenario",
                        path=figures_dir
                        / ms.figure_filename(iso, "F6", f"lcoe-{stat}", tech, CENTRAL, "ref"),
                    )
                )
        for ssp, members in sorted(by_ssp.items()):
            rows = table[table["member"].isin(members)]
            median = rows.groupby("cell_id")["lcoe_nominal"].median().reindex(cell_ids)
            grid, row0, col0 = cell_grid(cell_ids, _finite(median.to_numpy()))
            rasters[f"lcoe_nominal_{tech}__{slug(ssp)}"] = write_cog(
                artifacts / f"lcoe_nominal_{tech}__{slug(ssp)}.tif", grid, row0, col0
            )
            if figures_mode == "all" and np.isfinite(grid).any():
                figures.append(
                    draw_grid(
                        grid,
                        row0,
                        col0,
                        iso=iso,
                        technology=technology_name(tech),
                        variable="Nominal LCOE, median of the members",
                        label=LABEL,
                        kind="lcoe",
                        subtitle=f"{ssp} · {core_window} · central land scenario",
                        path=figures_dir
                        / ms.figure_filename(iso, "F6", "lcoe-nominal", tech, ssp, core_window),
                    )
                )
        curve = pd.read_parquet(curve_path)
        curve = curve[curve["member"].astype(str) == REFERENCE_MEMBER_ID]
        if figures_mode == "all" and np.isfinite(curve["lcoe_nominal"]).any():
            figures.append(
                _supply_curve_figure(
                    curve,
                    iso,
                    tech,
                    figures_dir
                    / ms.figure_filename(iso, "F6", "supply-curve", tech, CENTRAL, "ref"),
                )
            )
    return LcoeMapsSummary(
        country_code=iso, figures_mode=figures_mode, rasters=rasters, figures=figures
    )
