"""Existing GEM solar and wind plants drawn over the F2a distance-to-grid raster (visual QC; not a pipeline phase).

The plant trackers are validation-only (V-06), so this lives outside `src/` and the phase graph, like `scripts/qc_plants_vs_grid.py`. Operating plants
only. The map is a `MapFigure` of the common style (`viz/mapstyle.py`): the distance in the colours of the distances, the plants as points over it.
Writes `outputs/<ISO3>/overview/figures/<ISO3>_F2a_plants-over-grid.png`.

    python scripts/plot_plants_over_grid.py [ISO3 ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from geofrea.core import paths as core_paths
from geofrea.core.config_loader import load_countries
from geofrea.overview.diagnostic import aligned_path, drawn_resolution, read_layer
from geofrea.viz import mapstyle as ms
from geofrea.viz.context import country_context

REPO_ROOT = Path(__file__).resolve().parents[1]
COLOURS = {
    "solar": "#D55E00",
    "wind": "#0072B2",
}  # Okabe-Ito vermillion and blue, apart from the viridis of the distances


def plot_country(iso: str) -> Path:
    plants = pd.read_parquet(core_paths.fetched_raw("gem", iso) / f"gem_solar_wind_{iso}.parquet")
    plants = plants[plants["status"] == "operating"]
    arr, extent = read_layer(aligned_path(iso, "grid"))
    ctx = country_context(iso)
    canvas = ms.raster_map(
        arr,
        extent,
        ctx.polygon,
        iso=iso,
        technology="",
        variable="Existing plants over the distance to the grid",
        label="Distance (km)",
        kind="distance",
        subtitle=ms.format_subtitle(
            "Operating plants of the GEM trackers", "validation context only"
        ),
        resolution=drawn_resolution(extent, arr.shape),
        neighbours=ctx.neighbours,
        extent=ctx.extent,
        contiguous=False,
    )
    for tech, g in plants.groupby("tech"):
        x, y = canvas.to_xy(g["lon"].to_numpy(), g["lat"].to_numpy())
        canvas.ax.scatter(
            x,
            y,
            s=2 + g["capacity_mw"].clip(upper=500) / 10,
            c=COLOURS[tech],
            alpha=0.6,
            linewidths=0,
            label=f"{tech.capitalize()}: {len(g):,} plants, {g['capacity_mw'].sum() / 1000:,.1f} GW",
            zorder=6,
        )
    canvas.ax.set_xlim(canvas.frame.bounds[0], canvas.frame.bounds[1])
    canvas.ax.set_ylim(canvas.frame.bounds[2], canvas.frame.bounds[3])
    canvas.ax.legend(
        loc="lower left", fontsize=canvas.preset.legend_pt, frameon=True, framealpha=0.9
    )
    canvas.meta["status"] = "diagnostic"
    canvas.meta["data_source"] = "GEM operating plants, F2a grid distance"
    out = core_paths.phase_dir(iso, "overview", "figures") / ms.figure_filename(
        iso, "F2a", "plants-over-grid"
    )
    return ms.save_png(canvas, out)


def main(argv: list[str]) -> int:
    load_dotenv()
    countries = load_countries(REPO_ROOT / "config" / "countries.yaml")
    isos = argv or [iso for iso, cfg in countries.items() if cfg.get("gem_country_name")]
    for iso in isos:
        print(plot_country(iso))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
