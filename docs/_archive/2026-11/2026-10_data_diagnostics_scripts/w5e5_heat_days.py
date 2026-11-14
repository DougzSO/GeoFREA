# ruff: noqa
"""Addendum (V-83): reference heat days of the ISIMIP3b hazard channel against W5E5 v2.0 daily maximum temperature, 1995-2014.

W5E5 v2.0 is the observational reference ISIMIP3b was bias-adjusted to (ISIMIP3BASD v2.5.0 and W5E5 v2.0; https://www.isimip.org/gettingstarted/isimip3b-bias-adjustment/).
`raw/w5e5/<ISO3>/tasmax_W5E5v2.0_<ISO3>_19950101-20141231.nc` (scripts/place_w5e5_tasmax.py) is on exactly the cells of `raw/isimip3b/<ISO3>/`, so a cell is compared with
itself: the days a year at or above 35 and 40 C in W5E5 and in each hazard GCM (historical `tasmax`), over the 0.5 degree cells whose centre is inside the mainland polygon.
The check is not a check of truth: it asks whether the bias adjustment brought the GCM distribution of the hot tail to the reference it was adjusted to.
Usage: python w5e5_heat_days.py [ISO3 ...]
"""

from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely
import xarray as xr
from scipy.stats import pearsonr, spearmanr

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import *  # noqa

COUNTRIES = [c.upper() for c in sys.argv[1:]] or ["BRA", "PRT", "IND"]
HAZ = ["gfdl-esm4", "ipsl-cm6a-lr", "mri-esm2-0"]
THRESHOLDS = (35.0, 40.0)
PERIOD = slice("1995-01-01", "2014-12-31")


def days_per_year(da, t):
    return ((da >= t).sum("time") / da.sizes["time"] * 365.25).values


rows, store = [], {}
for country in COUNTRIES:
    ref = xr.open_dataset(
        DATA / "raw" / "w5e5" / country / f"tasmax_W5E5v2.0_{country}_19950101-20141231.nc"
    )["tasmax"]
    ref = (ref - 273.15).load()
    isi = {}
    for g in HAZ:
        ds = xr.open_dataset(
            DATA / "raw" / "isimip3b" / country / f"{g}_historical_tasmax_{country}.nc"
        )["tasmax"]
        isi[g] = (ds.sel(time=PERIOD) - 273.15).load()
        assert np.array_equal(isi[g]["lat"], ref["lat"]) and np.array_equal(
            isi[g]["lon"], ref["lon"]
        )
        assert isi[g].sizes["time"] == ref.sizes["time"] == 7305
    lat, lon = ref["lat"].values, ref["lon"].values
    lon2, lat2 = np.meshgrid(lon, lat)
    land = shapely.contains_xy(country_polygon(country), lon2, lat2)
    for t in THRESHOLDS:
        w = days_per_year(ref, t)
        counts = {g: days_per_year(isi[g], t) for g in HAZ}
        counts["mean of the three"] = np.mean([counts[g] for g in HAZ], axis=0)
        for name, i_val in counts.items():
            a, b = i_val[land], w[land]
            ok = np.std(a) > 0 and np.std(b) > 0
            rows.append(
                {
                    "country": country,
                    "threshold C": t,
                    "ISIMIP3b": name,
                    "cells": int(land.sum()),
                    "W5E5 median days": float(np.median(b)),
                    "ISIMIP3b median days": float(np.median(a)),
                    "median bias ISIMIP3b - W5E5 (days)": float(np.median(a - b)),
                    "mean bias (days)": float(np.mean(a - b)),
                    "median |diff| (days)": float(np.median(np.abs(a - b))),
                    "p95 |diff| (days)": float(np.percentile(np.abs(a - b), 95)),
                    "share of cells within 5 days": float(np.mean(np.abs(a - b) <= 5)),
                    "Pearson r": pearsonr(a, b)[0] if ok else np.nan,
                    "Spearman rho": spearmanr(a, b)[0] if ok else np.nan,
                }
            )
        if t == 35.0:
            store[country] = (lat, lon, land, w, counts["mean of the three"])
print(
    "\n## Reference heat days, ISIMIP3b against W5E5 v2.0 daily maximum temperature (1995-2014, the 0.5 degree cells of each country)\n"
)
print(md(pd.DataFrame(rows), ".3g"))

fig, axs = plt.subplots(
    2, len(store), figsize=(5.5 * len(store), 9), constrained_layout=True, squeeze=False
)
for j, (country, (lat, lon, land, w, i)) in enumerate(store.items()):
    g = gpd.read_file(DATA / "raw" / "gadm" / country / f"gadm41_{country}_0_mainland.shp").to_crs(
        4326
    )
    ax = axs[0, j]
    mm = ax.pcolormesh(
        lon, lat, np.where(land, i - w, np.nan), cmap="RdBu_r", vmin=-30, vmax=30, shading="nearest"
    )
    g.boundary.plot(ax=ax, color="k", lw=0.5)
    x0, y0, x1, y1 = g.total_bounds
    ax.set_xlim(x0 - 0.5, x1 + 0.5)
    ax.set_ylim(y0 - 0.5, y1 + 0.5)
    ax.set_aspect("equal")
    ax.set_title(f"{country}: ISIMIP3b (mean of 3) - W5E5 v2.0, days >= 35 C per year", fontsize=9)
    fig.colorbar(mm, ax=ax, shrink=0.7, label="days")
    ax = axs[1, j]
    ax.scatter(w[land], i[land], s=6, alpha=0.5)
    lim = np.nanmax([w[land].max(), i[land].max()])
    ax.plot([0, lim], [0, lim], "k", lw=0.8)
    ax.set_xlabel("W5E5 v2.0 days >= 35 C per year")
    ax.set_ylabel("ISIMIP3b days (mean of the three GCMs)")
fig.savefig(FIG / "w5e5_vs_isimip3b_heat_days.png", dpi=130)
print("figure written")
