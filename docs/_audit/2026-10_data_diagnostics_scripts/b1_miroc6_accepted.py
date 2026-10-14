# ruff: noqa
"""B-1 follow-up: the output mask (delta_wind in 0.5-1.5) only tests the ratio. How many MIROC6 cell-members that PASS the mask still rest on
a near-zero reference wind? Needs b1_BRA.npz. Usage: python b1_miroc6_accepted.py"""

from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import *  # noqa
from geofrea.climate_forcing.change_factors import bilinear_to_points, neighbourhood_mean

Z = np.load(SCRATCH / "b1_BRA.npz")
cid, lat, lon = Z["cell_id"], Z["lat"], Z["lon"]
cw = np.isin(cid, candidates("BRA", "wind")["cell_id"].to_numpy())
cs = np.isin(cid, candidates("BRA", "solar")["cell_id"].to_numpy())
rows = []
ref_cells = {}
for g in GCMS:
    h = load_native(g, "historical", "sfcWind", "BRA")
    ref = annual_clim(h, REF)
    ref3 = neighbourhood_mean(ref, 3)
    ref_cells[g] = bilinear_to_points(ref3, lat, lon)
    r = ref_cells[g]
    rec = {"GCM": g, "cells with 3x3 reference < 0.5 m/s": int((r < 0.5).sum()), "< 1 m/s": int((r < 1).sum()), "< 2 m/s": int((r < 2).sum())}
    ok = np.ones(len(cid), bool)
    for s in SSPS:
        for w in WINDOWS:
            v = Z[f"dw|{g}|{s}|{w}|3"]
            ok &= (v >= 0.5) & (v <= 1.5)
    rec["pass the 0.5-1.5 mask in all 6 member-windows"] = int(ok.sum())
    rec["... of which reference < 1 m/s"] = int((ok & (r < 1)).sum())
    rec["... of which reference < 2 m/s"] = int((ok & (r < 2)).sum())
    rec["wind candidates with reference < 1 m/s"] = int((cw & (r < 1)).sum())
    rec["solar candidates with reference < 1 m/s"] = int((cs & (r < 1)).sum())
    rows.append(rec)
print("\n## Cells whose reference (3x3 neighbourhood mean, interpolated to the 0.05 degree cell) is low, by GCM; and how many of them the output mask lets through\n")
print(md(pd.DataFrame(rows)))

# MIROC6 accepted cells with low reference: how different is their delta_wind from the other five?
oth = [g for g in GCMS if g != "MIROC6"]
out = []
for thr in (0.5, 1.0, 2.0):
    sel = ref_cells["MIROC6"] < thr
    for s in SSPS:
        w = "2041-2070"
        d = Z[f"dw|MIROC6|{s}|{w}|3"]
        acc = sel & (d >= 0.5) & (d <= 1.5)
        med5 = np.median(np.array([Z[f"dw|{g}|{s}|{w}|3"] for g in oth]), axis=0)
        out.append({"MIROC6 reference <": f"{thr} m/s", "SSP (2041-2070)": s, "cells": int(sel.sum()), "accepted by the mask": int(acc.sum()),
                    "accepted: MIROC6 delta_wind median": float(np.median(d[acc])) if acc.any() else np.nan,
                    "accepted: median of the other five": float(np.median(med5[acc])) if acc.any() else np.nan,
                    "accepted: median |MIROC6 - other five|": float(np.median(np.abs(d[acc] - med5[acc]))) if acc.any() else np.nan})
print("\n## Cells with a low MIROC6 reference that the mask accepts: how far is their delta_wind from the median of the other five GCMs (core window)\n")
print(md(pd.DataFrame(out)))

# alternative rule: mask on the INPUT (3x3 reference below a floor), counted on candidates, core window, any technology
print("\n## Input-based rule for MIROC6 (mask the MIROC6 members of a cell whose 3x3 reference wind is below a floor), plus today's output mask for the other GCMs\n")
core = ["2041-2070"]
bad_oth = np.zeros(len(cid), bool)
for g in oth:
    for s in SSPS:
        for w in core:
            v = Z[f"dw|{g}|{s}|{w}|3"]
            bad_oth |= ~((v >= 0.5) & (v <= 1.5))
tab = []
for floor in (0.5, 1.0, 1.5, 2.0):
    low = ref_cells["MIROC6"] < floor
    out_mask = np.zeros(len(cid), bool)
    for s in SSPS:
        v = Z[f"dw|MIROC6|{s}|2041-2070|3"]
        out_mask |= ~((v >= 0.5) & (v <= 1.5))
    inv = bad_oth | low | out_mask
    tab.append({"floor on MIROC6 reference (m/s)": floor, "cells below floor": int(low.sum()), "wind candidates invalid": int((inv & cw).sum()), "share": float((inv & cw).sum() / cw.sum()),
                "solar candidates invalid (row-level)": int((inv & cs).sum()), "cells invalid, all": int(inv.sum())})
print(md(pd.DataFrame(tab)))

fig, axs = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
ax = axs[0]
r = ref_cells["MIROC6"]
d = Z["dw|MIROC6|SSP3-7.0|2041-2070|3"]
ax.scatter(r, d, s=0.5, alpha=0.3)
ax.axhspan(0.5, 1.5, color="g", alpha=0.12, label="accepted range 0.5-1.5")
ax.set_yscale("log"); ax.set_xlabel("MIROC6 reference sfcWind, 3x3 mean at the 0.05 degree cell (m/s)"); ax.set_ylabel("delta_wind, SSP3-7.0 2041-2070")
ax.legend(); ax.set_title("MIROC6: the ratio against its own reference (285,999 cells)")
ax = axs[1]
for g in GCMS:
    ax.hist(ref_cells[g], bins=np.linspace(0, 6, 121), histtype="step", label=g, lw=2 if g == "MIROC6" else 1)
ax.set_xlabel("reference sfcWind, 3x3 mean at the cell (m/s)"); ax.set_ylabel("cells"); ax.legend(fontsize=8)
ax.set_title("Distribution at the 285,999 cells of Brazil")
fig.savefig(FIG / "b1_miroc6_ratio_vs_reference.png", dpi=130)
print("figure written")
