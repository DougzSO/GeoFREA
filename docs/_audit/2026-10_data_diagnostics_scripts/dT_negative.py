# ruff: noqa
"""Item 3: negative dT over Brazil. Which members, where, and is it a native-cell edge effect or a cooling region of the model?
Needs b1_BRA.npz. Usage: python dT_negative.py"""

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

Z = np.load(SCRATCH / "b1_BRA.npz")
cid, lat, lon = Z["cell_id"], Z["lat"], Z["lon"]
gc = list(GCMS)

# 1. negatives by member, cell level --------------------------------------------------------------------------------------------
rows = []
for g in gc:
    for s in SSPS:
        for w in WINDOWS:
            d = Z[f"dT|{g}|{s}|{w}"]
            nat = Z[f"native_dT|{g}|{s}|{w}"]
            land = Z[f"native_land|{g}"]
            nl = nat[land]
            rows.append(
                {"GCM": g, "SSP": s, "window": w, "cells dT<0": int((d < 0).sum()), "share of cells": (d < 0).mean(),
                 "min dT cell (K)": float(d.min()), "median dT cell (K)": float(np.median(d)),
                 "native land cells": int(land.sum()), "native land cells dT<0": int((nl < 0).sum()), "min native dT (K)": float(nl.min())}
            )
T = pd.DataFrame(rows)
print("\n## Cells with dT < 0, by member (0.05 degree cells of Brazil, 285,999)\n")
print(md(T[T["cells dT<0"] > 0]))
print(f"\ntotal negative cell-members {int(T['cells dT<0'].sum())} of {len(cid) * 36}; members with at least one: {int((T['cells dT<0'] > 0).sum())} of 36")
print("members with a negative native land cell (even when no 0.05 degree cell is negative):")
print(md(T[(T["native land cells dT<0"] > 0)][["GCM", "SSP", "window", "native land cells", "native land cells dT<0", "min native dT (K)"]]))

# 2. global-mean warming of the same members, to separate model cooling from a field-wide offset -----------------------------
def gmean(gcm, exp, years):
    ds = xr.open_dataset(cmip_path(gcm, exp, "tas"))
    da = ds["tas"].sel(time=slice(f"{years[0]}-01-01", f"{years[1]}-12-31"))
    wgt = np.cos(np.deg2rad(da["lat"]))
    return float(da.groupby("time.month").mean("time").mean("month").weighted(wgt).mean(("lat", "lon")))


print("\n## Global-mean tas change of the members that have negative cells (annual mean of the monthly climatology)\n")
out = []
seen = T[T["cells dT<0"] > 0]
for _, r in seen.iterrows():
    h = gmean(r["GCM"], "historical", REF)
    f = gmean(r["GCM"], SSPS[r["SSP"]], WINDOWS[r["window"]])
    out.append({"GCM": r["GCM"], "SSP": r["SSP"], "window": r["window"], "global dT (K)": f - h, "Brazil median dT (K)": r["median dT cell (K)"], "Brazil min dT (K)": r["min dT cell (K)"]})
print(md(pd.DataFrame(out)))

# 3. edge effect or cooling region? ---------------------------------------------------------------------------------------------
print("\n## Edge of a native cell, or a cooling region of the model?\n")
chk = []
for _, r in seen.iterrows():
    g, s, w = r["GCM"], r["SSP"], r["window"]
    d = Z[f"dT|{g}|{s}|{w}"]
    nat = Z[f"native_dT|{g}|{s}|{w}"]
    la, lo = Z[f"native_lat|{g}"], Z[f"native_lon|{g}"]
    neg = d < 0
    # nearest native centre of each negative cell, and whether that centre is itself negative
    ii = np.abs(la[None, :] - lat[neg][:, None]).argmin(axis=1)
    jj = np.abs(lo[None, :] - lon[neg][:, None]).argmin(axis=1)
    centre_neg = nat[ii, jj] < 0
    dist_lat = np.abs(la[ii] - lat[neg]) / (abs(la[1] - la[0]) / 2)
    dist_lon = np.abs(lo[jj] - lon[neg]) / (abs(lo[1] - lo[0]) / 2)
    # bilinear interpolation cannot go below the lowest of its four corners: report that corner count
    chk.append({"member": f"{g} {s} {w}", "negative cells": int(neg.sum()), "share whose nearest native centre is negative": float(centre_neg.mean()),
                "lowest native dT among these cells' centres (K)": float(nat[ii, jj].min()), "median distance to centre (1 = cell edge)": float(np.median(np.maximum(dist_lat, dist_lon))),
                "native cells negative in the Brazil window": int((nat < 0).sum()), "native cells in the window": int(nat.size)})
print(md(pd.DataFrame(chk)))

# 4. figure ----------------------------------------------------------------------------------------------------------------------
bra = gpd.read_file(DATA / "raw" / "gadm" / "BRA" / "gadm41_BRA_0_mainland.shp").to_crs(4326)


def edges(c):
    m = (c[1:] + c[:-1]) / 2
    return np.concatenate([[c[0] - (m[0] - c[0])], m, [c[-1] + (c[-1] - m[-1])]])


top = seen.sort_values("cells dT<0", ascending=False).head(3)
fig, axs = plt.subplots(2, 3, figsize=(14, 9), constrained_layout=True)
for k, (_, r) in enumerate(top.iterrows()):
    g, s, w = r["GCM"], r["SSP"], r["window"]
    la, lo = Z[f"native_lat|{g}"], Z[f"native_lon|{g}"]
    nat = Z[f"native_dT|{g}|{s}|{w}"]
    ax = axs[0, k]
    m = ax.pcolormesh(edges(lo), edges(la), nat, cmap="RdBu_r", vmin=-3, vmax=3, shading="flat")
    bra.boundary.plot(ax=ax, color="k", lw=0.5)
    d = Z[f"dT|{g}|{s}|{w}"]
    ax.scatter(lon[d < 0], lat[d < 0], s=0.3, c="k")
    ax.set_xlim(-74.5, -33.5); ax.set_ylim(-34.5, 6); ax.set_aspect("equal")
    ax.set_title(f"{g} {s} {w}\nnative dT (K); black = 0.05 degree cells with dT < 0", fontsize=9)
    ax = axs[1, k]
    ax.hist(d, bins=80, color="#2c7fb8")
    ax.axvline(0, color="r")
    ax.set_xlabel("dT of the 285,999 cells (K)")
    ax.set_title(f"{int((d < 0).sum())} cells below 0, min {d.min():.2f} K", fontsize=9)
fig.colorbar(m, ax=axs[0], shrink=0.7, label="K")
fig.savefig(FIG / "dT_negative_members.png", dpi=130)
print("figure written")
