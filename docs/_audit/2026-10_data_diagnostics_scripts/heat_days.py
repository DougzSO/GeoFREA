# ruff: noqa
"""Item 4: reference heat-day counts (tx35_days_ref) of the ISIMIP3b hazard channel.
No ERA5 Tmax is on disk, so there is no like-for-like ERA5 comparison; this script (a) compares the three hazard GCMs with each other
(they are bias-adjusted to the same W5E5 data, so agreement is expected and is not an independent check) and (b) re-derives the
2041-2070 count from the reference daily series shifted by the mean tasmax change, to test whether +80 days for +2 K is arithmetic.
Usage: python heat_days.py"""

from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import *  # noqa

HAZ = {"gfdl-esm4": "gfdl_esm4", "ipsl-cm6a-lr": "ipsl_cm6a_lr", "mri-esm2-0": "mri_esm2_0"}


def daily(country, gcm, exp, years):
    ds = xr.open_dataset(DATA / "raw" / "isimip3b" / country / f"{gcm}_{exp}_tasmax_{country}.nc")
    da = ds["tasmax"].sel(time=slice(f"{years[0]}-01-01", f"{years[1]}-12-31")) - 273.15
    return da.load()


def inside(country, da):
    """Mask of native cells whose centre lies inside the mainland polygon (the crop is a bounding box and holds sea cells)."""
    import shapely

    lon2, lat2 = np.meshgrid(da["lon"].values, da["lat"].values)
    return shapely.contains_xy(country_polygon(country), lon2, lat2)


rows = []
store = {}
for country in ("BRA", "PRT", "IND"):
    for gcm in HAZ:
        ref = daily(country, gcm, "historical", REF)
        land = inside(country, ref.isel(time=0))
        sel = lambda a: np.where(land, a.values, np.nan)
        for ssp, exp in (("SSP3-7.0", "ssp370"), ("SSP5-8.5", "ssp585")):
            win = daily(country, gcm, exp, WINDOWS["2041-2070"])
            ny_ref, ny_win = 20, 30
            ref_cnt = (ref >= 35).sum("time") / ny_ref
            win_cnt = (win >= 35).sum("time") / ny_win
            dtx = win.mean("time") - ref.mean("time")  # mean tasmax change per cell
            shifted = ((ref + dtx) >= 35).sum("time") / ny_ref
            # same, but also scale the daily anomalies by the ratio of standard deviations (variance change)
            ratio = win.std("time") / ref.std("time")
            mu = ref.mean("time")
            scaled = ((mu + (ref - mu) * ratio + dtx) >= 35).sum("time") / ny_ref
            ref_cnt, win_cnt, shifted, scaled, dtx = (
                xr.DataArray(sel(x), coords=x.coords, dims=x.dims)
                for x in (ref_cnt, win_cnt, shifted, scaled, dtx)
            )
            m = np.isfinite(ref_cnt.values)
            rows.append(
                {
                    "country": country,
                    "GCM": gcm,
                    "SSP": ssp,
                    "native cells": int(m.sum()),
                    "median ref days": float(np.nanmedian(ref_cnt)),
                    "median window days": float(np.nanmedian(win_cnt)),
                    "median shifted-ref days": float(np.nanmedian(shifted)),
                    "median shifted+scaled days": float(np.nanmedian(scaled)),
                    "median dTmax (K)": float(np.nanmedian(dtx)),
                    "median |actual - shifted| (days)": float(
                        np.nanmedian(np.abs(win_cnt - shifted))
                    ),
                    "median |actual - shifted+scaled|": float(
                        np.nanmedian(np.abs(win_cnt - scaled))
                    ),
                }
            )
            if gcm == "gfdl-esm4" and ssp == "SSP3-7.0":
                store[country] = (ref_cnt, win_cnt, shifted)
print(
    "\n## Heat days (tasmax >= 35 C): reference, window, and the window re-derived by shifting the reference series (native 0.5 degree cells)\n"
)
print(md(pd.DataFrame(rows), ".3g"))

# (a) the three hazard GCMs against each other, from hazard_context.parquet ---------------------------------------------------
print(
    "\n## tx35_days_ref in hazard_context.parquet: the three hazard GCMs against each other (cells of the 0.05 degree lattice)\n"
)
out = []
for c in ("BRA", "PRT", "IND"):
    h = pd.read_parquet(
        DATA / "outputs" / c / "climate_forcing" / "artifacts" / "hazard_context.parquet"
    )
    h["gcm"] = h.member.astype(str).str.split("_").str[1:3].str.join("_")
    p = h.pivot_table(index="cell_id", columns="gcm", values="tx35_days_ref")
    spread = p.max(1) - p.min(1)
    out.append(
        {
            "country": c,
            **{f"median {k}": float(p[k].median()) for k in p.columns},
            "p99 (any GCM)": float(p.stack().quantile(0.99)),
            "max (any GCM)": float(p.max().max()),
            "median spread of the 3 (days)": float(spread.median()),
            "p95 spread": float(spread.quantile(0.95)),
        }
    )
print(md(pd.DataFrame(out), ".3g"))

# figure ------------------------------------------------------------------------------------------------------------------------
fig, axs = plt.subplots(2, 3, figsize=(15, 8.5), constrained_layout=True)
for j, c in enumerate(("BRA", "PRT", "IND")):
    ref_cnt, win_cnt, shifted = store[c]
    g = gpd.read_file(DATA / "raw" / "gadm" / c / f"gadm41_{c}_0_mainland.shp").to_crs(4326)
    ax = axs[0, j]
    mm = ax.pcolormesh(
        ref_cnt["lon"],
        ref_cnt["lat"],
        ref_cnt,
        vmin=0,
        vmax=250 if c == "IND" else 150,
        cmap="YlOrRd",
        shading="nearest",
    )
    g.boundary.plot(ax=ax, color="k", lw=0.5)
    x0, y0, x1, y1 = g.total_bounds
    ax.set_xlim(x0 - 0.5, x1 + 0.5)
    ax.set_ylim(y0 - 0.5, y1 + 0.5)
    ax.set_aspect("equal")
    ax.set_title(f"{c}: days >= 35 C per year, 1995-2014 (GFDL-ESM4, ISIMIP3b)", fontsize=9)
    fig.colorbar(mm, ax=ax, shrink=0.7, label="days per year")
    ax = axs[1, j]
    a, b, s = ref_cnt.values.ravel(), win_cnt.values.ravel(), shifted.values.ravel()
    ok = np.isfinite(a) & np.isfinite(b)
    ax.scatter(s[ok], b[ok], s=3, alpha=0.4)
    lim = max(np.nanmax(s[ok]), np.nanmax(b[ok]))
    ax.plot([0, lim], [0, lim], "k", lw=0.8)
    ax.set_xlabel("window days re-derived by shifting the reference series (days)")
    ax.set_ylabel("window days, ISIMIP3b SSP3-7.0 2041-2070")
    ax.set_title(f"{c}: native cells (GFDL-ESM4)", fontsize=9)
fig.savefig(FIG / "heat_days_reference_and_shift.png", dpi=130)
print("figure written")
