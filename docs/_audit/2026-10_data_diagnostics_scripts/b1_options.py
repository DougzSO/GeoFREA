# ruff: noqa
"""B-1: invalid-cell counts of each mask option, computed in memory from b1_BRA.npz. Prints Markdown tables.
Usage: python b1_options.py [BRA]"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import *  # noqa

country = sys.argv[1] if len(sys.argv) > 1 else "BRA"
Z = np.load(SCRATCH / f"b1_{country}.npz")
cid = Z["cell_id"]
LO, HI = 0.5, 1.5
cand = {t: np.isin(cid, candidates(country, t)["cell_id"].to_numpy()) for t in ("solar", "wind")}
cand["all"] = np.ones(len(cid), bool)
gc = list(GCMS)
member = lambda g, s, w: f"m_{GCMS[g]}_{SSPS[s].replace('ssp', 'ssp')}_{w.replace('-', '_')}"


def mask(g, s, w, n, lo=LO, hi=HI):
    v = Z[f"dw|{g}|{s}|{w}|{n}"]
    return ~((v >= lo) & (v <= hi))  # NaN counts as masked


# --- 0. reproduce the stored mask (n=3, 0.5-1.5) -------------------------------------------------------------------
stored = pd.read_parquet(DATA / "outputs" / country / "climate_forcing" / "artifacts" / "forcing_masked.parquet")
mine = []
for g in gc:
    for s in SSPS:
        for w in WINDOWS:
            m = mask(g, s, w, 3)
            mine.append(pd.DataFrame({"cell_id": cid[m], "member": member(g, s, w), "delta_wind": Z[f"dw|{g}|{s}|{w}|3"][m]}))
mine = pd.concat(mine)
a = set(zip(stored["cell_id"], stored["member"]))
b = set(zip(mine["cell_id"], mine["member"]))
print(f"\n## Reproduction of forcing_masked.parquet\n\nstored {len(a)} cell-members, recomputed {len(b)}, in both {len(a & b)}, only stored {len(a - b)}, only recomputed {len(b - a)}")
mm = stored.merge(mine, on=["cell_id", "member"], suffixes=("_stored", "_mine"))
print(f"max |delta_wind stored - recomputed| over the common rows: {np.abs(mm.delta_wind_stored - mm.delta_wind_mine).max():.2e}")

# --- 1. option table -----------------------------------------------------------------------------------------------
def invalid_cells(gcms, windows, n, lo=LO, hi=HI):
    """Boolean array over cells: masked in at least one member of the given GCMs and windows."""
    bad = np.zeros(len(cid), bool)
    for g in gcms:
        for s in SSPS:
            for w in windows:
                bad |= mask(g, s, w, n, lo, hi)
    return bad


others = [g for g in gc if g != "MIROC6"]
# pooled bounds of option (e): all cells of the country, all members of the five other GCMs, n = 3
pool = np.concatenate([Z[f"dw|{g}|{s}|{w}|3"] for g in others for s in SSPS for w in WINDOWS])
pool = pool[np.isfinite(pool)]
b_minmax = (float(pool.min()), float(pool.max()))
b_p1p99 = (float(np.percentile(pool, 1)), float(np.percentile(pool, 99)))
b_p01 = (float(np.percentile(pool, 0.1)), float(np.percentile(pool, 99.9)))
print(f"\n## Option (e) bounds from the other five GCMs ({len(pool)} cell-members, n = 3)\n")
print(f"min-max [{b_minmax[0]:.3f}, {b_minmax[1]:.3f}]; p0.1-p99.9 [{b_p01[0]:.3f}, {b_p01[1]:.3f}]; p1-p99 [{b_p1p99[0]:.3f}, {b_p1p99[1]:.3f}]")
print("per GCM, share of its cell-members outside [0.5, 1.5] / outside min-max of the other five:")
rows = []
for g in gc:
    v = np.concatenate([Z[f"dw|{g}|{s}|{w}|3"] for s in SSPS for w in WINDOWS])
    oth = np.concatenate([Z[f"dw|{h}|{s}|{w}|3"] for h in gc if h != g for s in SSPS for w in WINDOWS])
    rows.append((g, np.mean((v < LO) | (v > HI)), np.mean((v < oth.min()) | (v > oth.max())), float(np.nanpercentile(v, 1)), float(np.nanpercentile(v, 99)), float(np.nanmin(v)), float(np.nanmax(v))))
print(md(pd.DataFrame(rows, columns=["GCM", "share outside 0.5-1.5", "share outside others' min-max", "p1", "p99", "min", "max"])))

core, both = ["2041-2070"], list(WINDOWS)
scen = []
def add(label, bad_by_tech):
    scen.append({"option": label, **bad_by_tech})

def counts(bad):  # bad over cells
    return {t: int((bad & cand[t]).sum()) for t in ("solar", "wind", "all")}

N = {t: int(cand[t].sum()) for t in ("solar", "wind", "all")}
res = {}
for win_label, wins in (("core window 2041-2070 (F7)", core), ("both windows", both)):
    r = {}
    r["(a) keep 0.5-1.5, 3x3 [today]"] = counts(invalid_cells(gc, wins, 3))
    r["(a') same, but no neighbourhood (1x1)"] = counts(invalid_cells(gc, wins, 1))
    r["(b) 5x5 neighbourhood"] = counts(invalid_cells(gc, wins, 5))
    r["(b) 7x7 neighbourhood"] = counts(invalid_cells(gc, wins, 7))
    oth_bad = invalid_cells(others, wins, 3)
    r["(c) drop MIROC6 wind channel; wind mask drops the whole row of the other five (wind cells)"] = {"wind": int((oth_bad & cand["wind"]).sum())}
    r["(c) same, solar cells, row-level mask (today's contract)"] = {"solar": int((oth_bad & cand["solar"]).sum())}
    r["(c') as (c) but the wind mask drops only the wind channel (solar cells never invalid)"] = {"solar": 0, "wind": int((oth_bad & cand["wind"]).sum())}
    r["(d) drop MIROC6 entirely (5 GCMs), mask 0.5-1.5"] = counts(oth_bad)
    for lab, (lo, hi) in (("min-max", b_minmax), ("p0.1-p99.9", b_p01), ("p1-p99", b_p1p99)):
        r[f"(e) range from the other five, {lab} = [{lo:.2f}, {hi:.2f}]"] = counts(invalid_cells(gc, wins, 3, lo, hi))
    res[win_label] = r
    print(f"\n## {win_label}: candidate cells that would be `climate_data_invalid` (BRA candidates: solar {N['solar']}, wind {N['wind']}, all cells {N['all']})\n")
    print("| Option | Solar candidates | Wind candidates | All forcing cells |")
    print("|---|---|---|---|")
    for k, v in r.items():
        f = lambda t: f"{v[t]} ({v[t] / N[t]:.2%})" if t in v else "-"
        print(f"| {k} | {f('solar')} | {f('wind')} | {f('all')} |")

# who masks (a), by GCM, among candidates (core window)
print("\n## Cells invalid under (a) in the core window, by the GCM that masks them (a cell can have several)\n")
print("| GCM | cells masked (all) | wind candidates | solar candidates | cells masked by this GCM only |")
print("|---|---|---|---|---|")
per = {g: invalid_cells([g], core, 3) for g in gc}
for g in gc:
    only = per[g] & ~np.any([per[h] for h in gc if h != g], axis=0)
    print(f"| {g} | {int(per[g].sum())} | {int((per[g] & cand['wind']).sum())} | {int((per[g] & cand['solar']).sum())} | {int(only.sum())} |")

# severity of MIROC6 mask: delta_wind of masked cell-members
v = np.concatenate([Z[f"dw|MIROC6|{s}|{w}|3"][mask('MIROC6', s, w, 3)] for s in SSPS for w in WINDOWS])
print(f"\nMIROC6 rejected delta_wind: n={len(v)}, p5/p50/p95/max = {np.percentile(v, 5):.2f} / {np.percentile(v, 50):.2f} / {np.percentile(v, 95):.2f} / {v.max():.1f}; below 0.5: {(v < 0.5).sum()}; above 1.5: {(v > 1.5).sum()}")
json.dump({"bounds": {"minmax": b_minmax, "p01": b_p01, "p1p99": b_p1p99}, "N": N, "res": {k: v for k, v in res.items()}}, open(SCRATCH / f"b1_options_{country}.json", "w"), indent=1)
