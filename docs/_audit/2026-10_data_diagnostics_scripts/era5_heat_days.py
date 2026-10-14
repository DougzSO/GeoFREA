# ruff: noqa
"""Addendum (V-83): reference heat days of the ISIMIP3b hazard channel against ERA5 daily maximum 2 m temperature, 1995-2014.

ERA5 comes from `scripts/acquire_era5_tmax_daily.py` (CDS derived daily statistics, daily maximum of t2m, UTC day, 0.25 degree). ISIMIP3b is the
historical `tasmax` of the three hazard GCMs (0.5 degree, bias-adjusted to W5E5 v2.0). Both are brought to the same 0.5 degree cells (ISIMIP3b native
cells whose centre lies inside the mainland polygon): ERA5 is averaged 2 x 2 to 0.5 degree FIRST and the days at or above the threshold are counted
on the averaged series (the same operation ISIMIP3b went through); the count of the 0.25 degree cells averaged afterwards is reported as a variant.
Usage: python era5_heat_days.py [ISO3 ...]
"""

from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from scipy.stats import pearsonr, spearmanr

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import *  # noqa

COUNTRIES = [c.upper() for c in sys.argv[1:]] or ["BRA", "PRT", "IND"]
HAZ = ["gfdl-esm4", "ipsl-cm6a-lr", "mri-esm2-0"]
THRESHOLDS = (35.0, 40.0)


def inside(country, lon, lat):
    import shapely

    lon2, lat2 = np.meshgrid(lon, lat)
    return shapely.contains_xy(country_polygon(country), lon2, lat2)


def era5_daily(country):
    da = xr.open_dataset(DATA / "raw" / "era5" / country / f"{country}_t2m_dailymax.nc")["tmax_c"]
    return da.rename({n: m for n, m in (("latitude", "lat"), ("longitude", "lon")) if n in da.dims})


def count(da, t):
    return (da >= t).sum("time") / da.sizes["time"] * 365.25


rows, store = [], {}
for country in COUNTRIES:
    era = era5_daily(country).sel(time=slice("1995-01-01", "2014-12-31"))
    isi = {}
    for g in HAZ:
        ds = xr.open_dataset(DATA / "raw" / "isimip3b" / country / f"{g}_historical_tasmax_{country}.nc")["tasmax"]
        isi[g] = (ds.sel(time=slice("1995-01-01", "2014-12-31")) - 273.15).load()
    ref = next(iter(isi.values()))
    lat, lon = ref["lat"].values, ref["lon"].values
    land = inside(country, lon, lat)
    # ERA5 on the ISIMIP3b 0.5 degree cells: mean of the 0.25 degree cells whose centre lies within 0.25 degree of the 0.5 degree centre
    ila = np.abs(era["lat"].values[:, None] - lat[None, :]).argmin(axis=1)
    ilo = np.abs(era["lon"].values[:, None] - lon[None, :]).argmin(axis=1)
    ok_lat = np.abs(era["lat"].values - lat[ila]) <= 0.25 + 1e-6
    ok_lon = np.abs(era["lon"].values - lon[ilo]) <= 0.25 + 1e-6
    vals = era.transpose("time", "lat", "lon").values
    out = np.zeros((era.sizes["time"], len(lat), len(lon)), dtype="float64")
    cnt = np.zeros((len(lat), len(lon)))
    for i in np.flatnonzero(ok_lat):
        for j in np.flatnonzero(ok_lon):
            v = vals[:, i, j]
            out[:, ila[i], ilo[j]] += np.where(np.isfinite(v), v, 0.0)
            cnt[ila[i], ilo[j]] += np.isfinite(v[0])
    half = np.where(cnt[None] > 0, out / np.maximum(cnt[None], 1), np.nan)
    half_da = xr.DataArray(half, coords={"time": era["time"], "lat": lat, "lon": lon}, dims=("time", "lat", "lon"))
    for t in THRESHOLDS:
        e_cnt = count(half_da, t)
        e_fine = count(era, t).interp(lat=lat, lon=lon, method="nearest")  # the count of the 0.25 degree cells, nearest to the 0.5 cell centre
        m = land & (cnt > 0)
        i_cnt = {g: count(isi[g], t).values for g in HAZ}
        i_mean = np.mean([i_cnt[g] for g in HAZ], axis=0)
        for name, i_val in (*i_cnt.items(), ("mean of the three", i_mean)):
            a, b = i_val[m], e_cnt.values[m]
            rows.append({
                "country": country, "threshold C": t, "ISIMIP3b": name, "cells": int(m.sum()), "ERA5 median days": float(np.median(b)), "ISIMIP3b median days": float(np.median(a)),
                "median bias ISIMIP3b - ERA5 (days)": float(np.median(a - b)), "mean bias (days)": float(np.mean(a - b)), "median |diff| (days)": float(np.median(np.abs(a - b))),
                "share of cells within 10 days": float(np.mean(np.abs(a - b) <= 10)), "Pearson r": pearsonr(a, b)[0] if np.std(a) > 0 and np.std(b) > 0 else np.nan,
                "Spearman rho": spearmanr(a, b)[0] if np.std(a) > 0 and np.std(b) > 0 else np.nan,
                "ERA5 0.25 degree count, nearest cell, median": float(np.nanmedian(e_fine.values[m])),
            })
        if t == 35.0:
            store[country] = (lat, lon, land, e_cnt.values, i_mean)
print("\n## Reference heat days, ISIMIP3b against ERA5 daily maximum temperature (1995-2014, 0.5 degree cells of each country)\n")
print(md(pd.DataFrame(rows), ".3g"))

fig, axs = plt.subplots(2, len(store), figsize=(5.5 * len(store), 9), constrained_layout=True, squeeze=False)
for j, (country, (lat, lon, land, e, i)) in enumerate(store.items()):
    g = gpd.read_file(DATA / "raw" / "gadm" / country / f"gadm41_{country}_0_mainland.shp").to_crs(4326)
    ax = axs[0, j]
    d = np.where(land, i - e, np.nan)
    mm = ax.pcolormesh(lon, lat, d, cmap="RdBu_r", vmin=-60, vmax=60, shading="nearest")
    g.boundary.plot(ax=ax, color="k", lw=0.5)
    x0, y0, x1, y1 = g.total_bounds
    ax.set_xlim(x0 - 0.5, x1 + 0.5); ax.set_ylim(y0 - 0.5, y1 + 0.5); ax.set_aspect("equal")
    ax.set_title(f"{country}: ISIMIP3b (mean of 3) - ERA5, days >= 35 C per year", fontsize=9)
    fig.colorbar(mm, ax=ax, shrink=0.7, label="days")
    ax = axs[1, j]
    ax.scatter(e[land], i[land], s=6, alpha=0.5)
    lim = np.nanmax([e[land].max(), i[land].max()])
    ax.plot([0, lim], [0, lim], "k", lw=0.8)
    ax.set_xlabel("ERA5 days >= 35 C per year"); ax.set_ylabel("ISIMIP3b days (mean of the three GCMs)")
fig.savefig(FIG / "era5_vs_isimip3b_heat_days.png", dpi=130)
print("figure written")
