"""Existing GEM solar and wind plants drawn over the F2a distance-to-grid raster (visual QC; not a pipeline phase).

The plant trackers are validation-only (V-06), so this lives outside `src/` and the phase graph, like
`scripts/qc_plants_vs_grid.py`. Operating plants only. Writes
`outputs/<ISO3>/overview/figures/<ISO3>_gem_plants_over_grid.png`.

    python scripts/plot_plants_over_grid.py [ISO3 ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dotenv import load_dotenv

from geofrea.core import paths as core_paths
from geofrea.core.config_loader import load_countries
from geofrea.overview.figures import read_layer

REPO_ROOT = Path(__file__).resolve().parents[1]
COLORS = {"solar": "#d62728", "wind": "#1f77b4"}


def plot_country(iso: str) -> Path:
    plants = pd.read_parquet(core_paths.fetched_raw("gem", iso) / f"gem_solar_wind_{iso}.parquet")
    plants = plants[plants["status"] == "operating"]
    raster = core_paths.phase_dir(iso, "grid_alignment", "artifacts") / f"{iso}_grid_aligned.tif"
    arr, extent = read_layer(raster)
    fig, ax = plt.subplots(figsize=(10, 10), constrained_layout=True)
    vmax = float(np.nanpercentile(arr, 99))
    im = ax.imshow(arr, extent=extent, cmap="Greys", vmin=0, vmax=vmax, interpolation="nearest")
    fig.colorbar(
        im,
        ax=ax,
        shrink=0.7,
        label="distance to the OSM grid (km, colour limit at the 99th percentile)",
    )
    for tech, g in plants.groupby("tech"):
        ax.scatter(
            g["lon"],
            g["lat"],
            s=2 + g["capacity_mw"].clip(upper=500) / 10,
            c=COLORS[tech],
            alpha=0.55,
            linewidths=0,
            label=f"{tech} ({len(g):,} operating, {g['capacity_mw'].sum() / 1000:,.1f} GW)",
        )
    ax.legend(loc="lower left")
    ax.set_title(
        f"{iso}: GEM operating solar and wind plants over the distance to the grid (validation context only)"
    )
    out = core_paths.phase_dir(iso, "overview", "figures") / f"{iso}_gem_plants_over_grid.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=100)
    plt.close(fig)
    return out


def main(argv: list[str]) -> int:
    load_dotenv()
    countries = load_countries(REPO_ROOT / "config" / "countries.yaml")
    isos = argv or [iso for iso, cfg in countries.items() if cfg.get("gem_country_name")]
    for iso in isos:
        print(plot_country(iso))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
