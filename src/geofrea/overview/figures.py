"""Overview figures and tables of one country's pipeline state (visual QC; no new method, no new numbers).

Everything here is read from outputs of earlier phases and drawn, never recomputed into a result: a layer that looks displaced, clipped or
implausible is visible at a glance before F3 builds on it. The figures are in the common map style (`overview/diagnostic.py`,
`land_eligibility/figures.py`) and the diagnostic ones say so.

Written under `outputs/<ISO3>/overview/`:
  - `figures/<ISO3>_F2a_aligned-layers_<theme>.png`: the F2a layers that F2b/F3 read in three sheets (terrain and land, distances, resource), and
    `<ISO3>_F2a_land-cover.png`;
  - `figures/<ISO3>_F3_land-eligibility_<tech>_central.png` and `<ISO3>_F3_exclusion-contribution_central.png`: F3 eligible share, dominant
    exclusion and the share of each exclusion;
  - `figures/<ISO3>_F4_hazard-context.png`: ISIMIP3b/ERA5 context indicators, mean over the hazard members, with changes;
  - `figures/layers/`: one map of each exclusion and technology (F3) and the distances to the grid and to the road (F2b), diagnostics;
  - `tables/<ISO3>_overview.md`: per-layer statistics, per-member change-factor ranges and masked counts, per-member hazard means.
The existing-plant trackers are NOT drawn here (V-06): `scripts/plot_plants_over_grid.py` does that outside the pipeline.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from geofrea.core import paths as core_paths
from geofrea.land_eligibility.figures import draw_country as eligibility_figures
from geofrea.land_eligibility.figures import read_cell_tables
from geofrea.overview import diagnostic as dg
from geofrea.overview.diagnostic import (  # noqa: F401  (read_layer is the reader of the scripts)
    layer_stats,
    read_layer,
)
from geofrea.viz import mapstyle as ms
from geofrea.viz.context import country_context

# (file stem under grid_alignment/artifacts, title in the table of the overview, kind of colour) in the order of the table
ALIGNED_PANELS = (
    ("elevation", dg.BY_STEM["elevation"].table_title, "elevation", ""),
    ("slope", dg.BY_STEM["slope"].table_title, "slope", ""),
    (dg.LAND_COVER_STEM, dg.LAND_COVER_TITLE, "categorical", ""),
    *(
        (s, dg.BY_STEM[s].table_title, dg.BY_STEM[s].kind, "")
        for s in (
            "population",
            "lakes",
            "rivers",
            "roads",
            "grid",
            "solar",
            "wind_wind_speed_100m",
            "wind_weibull_k_100m",
            "wind_air_density_100m",
        )
    ),
)


class OverviewSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    figures: list[Path]
    table: Path


def overview_dir(iso: str) -> Path:
    return core_paths.phase_dir(iso, "overview", "figures").parent


def _aligned_path(iso: str, stem: str) -> Path:
    return dg.aligned_path(iso, stem)


def _md(df: pd.DataFrame) -> str:
    head = "| " + " | ".join(str(c) for c in df.columns) + " |"
    rule = "|" + "|".join("---" for _ in df.columns) + "|"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([head, rule, *body])


def _fmt(v) -> str:
    return "-" if v is None else f"{v:,.3g}"


def build_tables(
    iso: str, forcing: pd.DataFrame, masked: pd.DataFrame, hazard: pd.DataFrame
) -> str:
    layer_rows = []
    for stem, panel_title, _cmap, _kind in ALIGNED_PANELS:
        title = panel_title.replace(
            "(log10 per pixel)", "(people per pixel)"
        )  # the table shows raw values, not log10
        path = _aligned_path(iso, stem)
        if not path.exists():
            layer_rows.append(
                {"layer": title, "valid pixels": "missing", "min": "-", "median": "-", "max": "-"}
            )
            continue
        s = layer_stats(path)
        layer_rows.append(
            {
                "layer": title,
                "valid pixels": f"{s['n_valid']:,}",
                "min": _fmt(s["min"]),
                "median": _fmt(s["median"]),
                "max": _fmt(s["max"]),
            }
        )

    f = forcing.copy()
    f["member"] = f["member"].astype(str)
    f = f[f["member"] != "m0"]
    m_counts = masked["member"].astype(str).value_counts()
    member_rows = []
    for member, g in f.groupby("member"):
        member_rows.append(
            {
                "member": member,
                "cells": len(g),
                "masked": int(m_counts.get(member, 0)),
                "wind ratio NaN": int(g.delta_wind.isna().sum()),
                "isolated dT cells": int(g.dT_isolated_native_cell.sum()),
                "delta_rsds (min / median / max)": " / ".join(
                    _fmt(x) for x in (g.delta_rsds.min(), g.delta_rsds.median(), g.delta_rsds.max())
                ),
                "delta_wind (min / median / max)": " / ".join(
                    _fmt(x) for x in (g.delta_wind.min(), g.delta_wind.median(), g.delta_wind.max())
                ),
                "dT K (min / median / max)": " / ".join(
                    _fmt(x) for x in (g.dT.min(), g.dT.median(), g.dT.max())
                ),
            }
        )

    h = hazard.copy()
    h["member"] = h["member"].astype(str)
    haz_rows = [
        {
            "member": member,
            "TX35 days": _fmt(g.tx35_days.mean()),
            "TX35 ref": _fmt(g.tx35_days_ref.mean()),
            "TX40 days": _fmt(g.tx40_days.mean()),
            "Rx5day mm": _fmt(g.rx5day_mm.mean()),
            "Rx5day ref": _fmt(g.rx5day_mm_ref.mean()),
            "wet P95 share": _fmt(g.wet_p95_exceed_freq.mean()),
        }
        for member, g in h.groupby("member")
    ]
    parts = [
        f"# {iso}: pipeline overview\n",
        "Generated from the outputs of the earlier phases; nothing here is a new result. Context indicators enter no loss function (OQ-007).\n",
        "## F2a aligned layers (full resolution)\n",
        _md(pd.DataFrame(layer_rows)),
        "\n## Climate members: change factors per cell (after masking)\n",
        _md(pd.DataFrame(member_rows)),
        (
            f"\nMasked cell-members in total: {len(masked):,} (OQ-042 option C; bound tracked as OQ-043). A masked cell-member keeps its row with a NaN wind ratio; "
            "a member without a wind channel (M-F4-02 item 6) has a NaN wind ratio in every cell, counted in the column `wind ratio NaN`. "
            "`isolated dT cells` counts the cells interpolated from an isolated native cell of `dT` (flagged, not corrected).\n"
        ),
        "## Hazard context: mean over cells, per member (window 2041-2070)\n",
        _md(pd.DataFrame(haz_rows)),
        "",
    ]
    return "\n".join(parts)


def build_overview(iso: str, figures_mode: str, display_smoothing: str = "auto") -> OverviewSummary:
    """Overview figures and table. `figures_mode` is `settings.yaml` `figures` (A-08): `none` writes the table only; `summary` draws the sheets and
    the chart (aligned layers, hazard context, F3), `all` also the diagnostic map of each exclusion and the cost drivers."""
    if figures_mode not in ("all", "summary", "none"):
        raise ValueError(f"figures must be all, summary or none, got {figures_mode!r}")
    art = core_paths.phase_dir(iso, "climate_forcing", "artifacts")
    forcing = pd.read_parquet(art / "forcing.parquet")
    masked = pd.read_parquet(art / "forcing_masked.parquet")
    hazard = pd.read_parquet(art / "hazard_context.parquet")
    out = overview_dir(iso)
    figures: list[Path] = []
    if figures_mode != "none":
        figures += draw_diagnostics(iso, hazard, forcing, out / "figures", figures_mode == "all")
        eligibility_dir = core_paths.phase_dir(iso, "land_eligibility", "artifacts")
        cell_tables = read_cell_tables(eligibility_dir)
        if cell_tables:
            ctx = country_context(
                iso, np.concatenate([c["cell_id"].to_numpy() for c in cell_tables.values()])
            )
            figures += eligibility_figures(
                iso,
                cell_tables,
                ctx,
                out / "figures",
                eligibility_dir,
                display_smoothing=display_smoothing,
                with_layers=figures_mode == "all",
            )
    table = out / "tables" / f"{iso}_overview.md"
    table.parent.mkdir(parents=True, exist_ok=True)
    table.write_text(build_tables(iso, forcing, masked, hazard), encoding="utf-8")
    return OverviewSummary(country_code=iso, figures=figures, table=table)


def draw_diagnostics(
    iso: str, hazard: pd.DataFrame, forcing: pd.DataFrame, out_dir: Path, with_layers: bool
) -> list[Path]:
    """The diagnostic sheets of the inputs (F2a layers, land cover, hazard context) and, with `with_layers`, the cost-driver maps of F2b."""
    ctx = country_context(iso, forcing["cell_id"].to_numpy())
    written: list[Path] = []
    for key, title, stems in dg.SHEETS:
        sheet = dg.aligned_sheet(ctx, iso, key, title, stems)
        if sheet is not None:
            written.append(ms.save_png(sheet, out_dir / dg.aligned_name(iso, key)))
    land_cover = dg.land_cover_map(ctx, iso)
    if land_cover is not None:
        written.append(ms.save_png(land_cover, out_dir / dg.land_cover_name(iso)))
    written.append(ms.save_png(dg.hazard_sheet(ctx, iso, hazard), out_dir / dg.hazard_name(iso)))
    if with_layers:
        siting = core_paths.phase_dir(iso, "siting_layers", "artifacts")
        for stem, what, variable in (
            ("dist_grid_km", "grid", "Distance to the transmission grid"),
            ("dist_road_km", "road", "Distance to the nearest road"),
        ):
            raster = Path(siting) / f"{stem}.tif"
            if not raster.is_file():
                continue
            canvas = dg.cost_driver_map(ctx, iso, raster, variable)
            written.append(ms.save_png(canvas, out_dir / "layers" / dg.cost_driver_name(iso, what)))
        if (out_dir / "layers").is_dir():
            ms.write_figures_index(out_dir / "layers")
    ms.write_figures_index(out_dir)
    return written
