"""Overview figures and tables of one country's pipeline state (visual QC; no new method, no new numbers).

Everything here is read from outputs of earlier phases and drawn, never recomputed into a result: a layer that looks
displaced, clipped or implausible is visible at a glance before F3 builds on it.

Written under `outputs/<ISO3>/overview/`:
  - `figures/<ISO3>_aligned_layers.png`: the 12 F2a layers that F2b/F3 read (elevation, slope, land cover, population,
    distances to lakes/rivers/roads/grid in km, PVOUT, wind speed, Weibull k and air density at 100 m);
  - `figures/<ISO3>_eligibility.png`: F3 eligible share of each 0.05 degree cell and its dominant exclusion, per technology;
  - `figures/<ISO3>_hazard_context.png`: ISIMIP3b/ERA5 context indicators, mean over the hazard members, with changes;
  - `tables/<ISO3>_overview.md`: per-layer statistics, per-member change-factor ranges and masked counts, per-member
    hazard means.
The existing-plant trackers are NOT drawn here (V-06): `scripts/plot_plants_over_grid.py` does that outside the pipeline.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from pydantic import BaseModel, ConfigDict

from geofrea.core import paths as core_paths
from geofrea.core.constants import CELL_DEG, CELL_ORIGIN_LAT, CELL_ORIGIN_LON
from geofrea.land_eligibility.cells import row_col_from_id
from geofrea.overview import style

MAX_PIXELS = 700  # longest side of a drawn raster

# (file stem under grid_alignment/artifacts, title, colormap, kind) ; kind: "linear" | "log" | "categorical"
ALIGNED_PANELS = (
    ("elevation", "Elevation (m)", "terrain", "linear"),
    ("slope", "Slope (degrees)", "magma", "linear"),
    ("land_cover", "Land cover (ESA class)", "tab20", "categorical"),
    ("population", "Population (log10 per pixel)", "viridis", "log"),
    ("lakes", "Lakes (1 = water)", "Blues", "linear"),
    ("rivers", "Distance to river (km)", "YlGnBu", "linear"),
    ("roads", "Distance to road (km)", "YlOrBr", "linear"),
    ("grid", "Distance to grid (km, uncapped)", "YlOrRd", "linear"),
    ("solar", "PVOUT (kWh/kWp/day)", "YlOrRd", "linear"),
    ("wind_wind_speed_100m", "Wind speed 100 m (m/s)", "viridis", "linear"),
    ("wind_weibull_k_100m", "Weibull k 100 m", "cividis", "linear"),
    ("wind_air_density_100m", "Air density 100 m (kg/m3)", "plasma", "linear"),
)

HAZARD_PANELS = (
    ("tx35_days", "TX35: days >= 35 C per year (mean of members)", "YlOrRd"),
    ("tx35_change", "TX35 change vs 1995-2014 (days)", "RdBu_r"),
    ("rx5day_mm", "Rx5day (mm, mean of members)", "Blues"),
    ("rx5day_change", "Rx5day change vs 1995-2014 (mm)", "RdBu"),
    ("wet_p95_exceed_freq", "Wet days above baseline P95 (share)", "PuBu"),
    ("gust_mean_annual_max_ms", "ERA5 gust, mean annual maximum (m/s)", "viridis"),
)


class OverviewSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    figures: list[Path]
    table: Path


def overview_dir(iso: str) -> Path:
    return core_paths.phase_dir(iso, "overview", "figures").parent


def _aligned_path(iso: str, stem: str) -> Path:
    return core_paths.phase_dir(iso, "grid_alignment", "artifacts") / f"{iso}_{stem}_aligned.tif"


def read_layer(
    path: Path, max_pixels: int = MAX_PIXELS
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Band 1 as float32 with nodata -> NaN, downsampled so its longest side is `max_pixels`; and (W, E, S, N)."""
    with rasterio.open(path) as src:
        scale = max(1, int(np.ceil(max(src.height, src.width) / max_pixels)))
        shape = (max(1, src.height // scale), max(1, src.width // scale))
        arr = src.read(1, out_shape=shape).astype("float32")
        nodata = src.nodata
        b = src.bounds
    if nodata is not None:
        arr[arr == nodata] = np.nan
    arr[~np.isfinite(arr)] = np.nan
    return arr, (b.left, b.right, b.bottom, b.top)


def layer_stats(path: Path) -> dict:
    """Valid-pixel count and min / median / max of the full-resolution layer."""
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float64")
        nodata = src.nodata
    valid = np.isfinite(arr) if nodata is None else (np.isfinite(arr) & (arr != nodata))
    v = arr[valid]
    if v.size == 0:
        return {"n_valid": 0, "min": None, "median": None, "max": None}
    return {
        "n_valid": int(v.size),
        "min": float(v.min()),
        "median": float(np.median(v)),
        "max": float(v.max()),
    }


def plot_aligned_layers(iso: str, out_path: Path) -> Path:
    fig, axes = plt.subplots(3, 4, figsize=(18, 13), constrained_layout=True)
    loaded = style.load_relief(_aligned_path(iso, "elevation"))
    relief = loaded[0] if loaded else None
    outline, rivers = style.country_outline(iso), style.major_rivers(iso)
    for ax, (stem, title, cmap, kind) in zip(axes.ravel(), ALIGNED_PANELS, strict=True):
        path = _aligned_path(iso, stem)
        ax.set_title(title, fontsize=10)
        if not path.exists():
            ax.text(
                0.5, 0.5, f"missing\n{path.name}", ha="center", va="center", transform=ax.transAxes
            )
            ax.set_axis_off()
            continue
        arr, extent = read_layer(path)
        kwargs: dict = {"cmap": cmap, "interpolation": "nearest", "extent": extent}
        if relief is not None and stem != "elevation":
            style.draw_backdrop(ax, relief, extent)
            kwargs.update(alpha=0.78, zorder=1)
        if kind == "log":
            arr = np.log10(np.where(arr > 0, arr, np.nan))
        elif kind == "categorical":
            kwargs["cmap"] = "tab20"
        if np.isfinite(arr).any():
            lo, hi = (
                np.nanpercentile(arr, [1, 99])
                if kind == "linear"
                else (np.nanmin(arr), np.nanmax(arr))
            )
            if hi > lo:
                kwargs.update(vmin=lo, vmax=hi)
        im = ax.imshow(arr, **kwargs)
        if stem == "elevation" and relief is not None:  # terrain colours shaded by the relief
            ax.imshow(
                relief,
                extent=extent,
                cmap="Greys_r",
                vmin=0.0,
                vmax=1.0,
                alpha=0.35,
                interpolation="bilinear",
                zorder=2,
            )
        style.draw_overlay(ax, outline, rivers, extent)
        fig.colorbar(im, ax=ax, shrink=0.75)
        ax.tick_params(labelsize=7)
    fig.suptitle(
        f"{iso}: F2a aligned layers (colour limits at the 1st-99th percentile)", fontsize=13
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=100)
    plt.close(fig)
    return out_path


EXCLUSION_LABELS = (
    "none",
    "E1 protected",
    "E2 water",
    "E3 riparian",
    "E4 slope",
    "E5 land cover",
    "E6 population",
)


def plot_eligibility(iso: str, cell_tables: dict[str, pd.DataFrame], out_path: Path) -> Path:
    """One column per technology: eligible share of each cell (top) and the dominant exclusion (bottom)."""
    from matplotlib.colors import BoundaryNorm, ListedColormap

    techs = sorted(cell_tables)
    all_rows = np.concatenate([cell_tables[t]["row"].to_numpy() for t in techs])
    all_cols = np.concatenate([cell_tables[t]["col"].to_numpy() for t in techs])
    r0, r1, c0, c1 = (
        int(all_rows.min()),
        int(all_rows.max()),
        int(all_cols.min()),
        int(all_cols.max()),
    )
    extent = (
        CELL_ORIGIN_LON + c0 * CELL_DEG,
        CELL_ORIGIN_LON + (c1 + 1) * CELL_DEG,
        CELL_ORIGIN_LAT - (r1 + 1) * CELL_DEG,
        CELL_ORIGIN_LAT - r0 * CELL_DEG,
    )
    colors = ["#f0f0f0", "#1b9e77", "#1f78b4", "#6baed6", "#a65628", "#e6ab02", "#d95f02"]
    cmap, norm = ListedColormap(colors), BoundaryNorm(np.arange(-0.5, 7.5), len(colors))
    fig, axes = plt.subplots(
        2, len(techs), figsize=(7 * len(techs), 13), constrained_layout=True, squeeze=False
    )
    loaded = style.load_relief(_aligned_path(iso, "elevation"))
    outline, rivers = style.country_outline(iso), style.major_rivers(iso)
    codes = {name: i + 1 for i, name in enumerate(("E1", "E2", "E3", "E4", "E5", "E6"))}
    for j, tech in enumerate(techs):
        cells = cell_tables[tech]
        rows, cols = cells["row"].to_numpy() - r0, cells["col"].to_numpy() - c0
        share = np.full((r1 - r0 + 1, c1 - c0 + 1), np.nan, dtype=np.float32)
        share[rows, cols] = (cells["eligible_area_km2"] / cells["cell_area_km2"]).to_numpy()
        dom = np.full(share.shape, np.nan, dtype=np.float32)
        dom[rows, cols] = cells["dominant_exclusion"].map(codes).fillna(0).to_numpy()
        for k in (0, 1):
            if loaded:
                style.draw_backdrop(axes[k, j], loaded[0], loaded[1])
        im = axes[0, j].imshow(
            share,
            extent=extent,
            cmap="YlGn",
            vmin=0,
            vmax=1,
            interpolation="nearest",
            alpha=0.8,
            zorder=1,
        )
        fig.colorbar(im, ax=axes[0, j], shrink=0.7, label="eligible share of the cell")
        axes[0, j].set_title(
            f"{tech}: eligible share ({100 * cells['eligible_area_km2'].sum() / cells['cell_area_km2'].sum():.1f}% of the land)"
        )
        im2 = axes[1, j].imshow(
            dom, extent=extent, cmap=cmap, norm=norm, interpolation="nearest", alpha=0.85, zorder=1
        )
        for k in (0, 1):
            style.draw_overlay(axes[k, j], outline, rivers, extent)
        cb = fig.colorbar(im2, ax=axes[1, j], shrink=0.7, ticks=range(7))
        cb.ax.set_yticklabels(EXCLUSION_LABELS)
        axes[1, j].set_title(f"{tech}: dominant exclusion per cell")
    fig.suptitle(
        f"{iso}: F3 land eligibility, central parameters (open questions OQ-046 to OQ-049)",
        fontsize=13,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=100)
    plt.close(fig)
    return out_path


def _hazard_means(hazard: pd.DataFrame) -> pd.DataFrame:
    h = hazard.copy()
    h["tx35_change"] = h["tx35_days"] - h["tx35_days_ref"]
    h["rx5day_change"] = h["rx5day_mm"] - h["rx5day_mm_ref"]
    cols = [c for c, *_ in HAZARD_PANELS]
    return h.groupby("cell_id", observed=True)[cols].mean().reset_index()


def plot_hazard_context(iso: str, hazard: pd.DataFrame, out_path: Path) -> Path:
    means = _hazard_means(hazard)
    rows, cols = row_col_from_id(means["cell_id"].to_numpy())
    r0, r1, c0, c1 = int(rows.min()), int(rows.max()), int(cols.min()), int(cols.max())
    extent = (
        CELL_ORIGIN_LON + c0 * CELL_DEG,
        CELL_ORIGIN_LON + (c1 + 1) * CELL_DEG,
        CELL_ORIGIN_LAT - (r1 + 1) * CELL_DEG,
        CELL_ORIGIN_LAT - r0 * CELL_DEG,
    )
    fig, axes = plt.subplots(2, 3, figsize=(16, 10), constrained_layout=True)
    loaded = style.load_relief(_aligned_path(iso, "elevation"))
    outline, rivers = style.country_outline(iso), style.major_rivers(iso)
    for ax, (col, title, cmap) in zip(axes.ravel(), HAZARD_PANELS, strict=True):
        if loaded:
            style.draw_backdrop(ax, loaded[0], loaded[1])
        img = np.full((r1 - r0 + 1, c1 - c0 + 1), np.nan, dtype=np.float32)
        img[rows - r0, cols - c0] = means[col].to_numpy()
        vals = img[np.isfinite(img)]
        kwargs: dict = {
            "cmap": cmap,
            "extent": extent,
            "interpolation": "nearest",
            "alpha": 0.85,
            "zorder": 1,
        }
        if "change" in col and vals.size:
            half = float(np.nanmax(np.abs(np.nanpercentile(vals, [1, 99])))) or 1.0
            kwargs.update(vmin=-half, vmax=half)
        im = ax.imshow(img, **kwargs)
        style.draw_overlay(ax, outline, rivers, extent)
        ax.set_title(title, fontsize=10)
        fig.colorbar(im, ax=ax, shrink=0.8)
    n = hazard["member"].nunique()
    fig.suptitle(
        f"{iso}: hazard context, mean over {n} members (context only, OQ-007)", fontsize=13
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=100)
    plt.close(fig)
    return out_path


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
        f"\nMasked cell-members in total: {len(masked):,} (OQ-042 option C; bound tracked as OQ-043).\n",
        "## Hazard context: mean over cells, per member (window 2041-2070)\n",
        _md(pd.DataFrame(haz_rows)),
        "",
    ]
    return "\n".join(parts)


def build_overview(iso: str) -> OverviewSummary:
    art = core_paths.phase_dir(iso, "climate_forcing", "artifacts")
    forcing = pd.read_parquet(art / "forcing.parquet")
    masked = pd.read_parquet(art / "forcing_masked.parquet")
    hazard = pd.read_parquet(art / "hazard_context.parquet")
    out = overview_dir(iso)
    figures = [
        plot_aligned_layers(iso, out / "figures" / f"{iso}_aligned_layers.png"),
        plot_hazard_context(iso, hazard, out / "figures" / f"{iso}_hazard_context.png"),
    ]
    eligibility_dir = core_paths.phase_dir(iso, "land_eligibility", "artifacts")
    cell_tables = {
        p.stem.removeprefix("cells_").removesuffix("__central"): pd.read_parquet(p)
        for p in sorted(eligibility_dir.glob("cells_*__central.parquet"))
    }
    if cell_tables:
        figures.append(
            plot_eligibility(iso, cell_tables, out / "figures" / f"{iso}_eligibility.png")
        )
    table = out / "tables" / f"{iso}_overview.md"
    table.parent.mkdir(parents=True, exist_ok=True)
    table.write_text(build_tables(iso, forcing, masked, hazard), encoding="utf-8")
    return OverviewSummary(country_code=iso, figures=figures, table=table)
