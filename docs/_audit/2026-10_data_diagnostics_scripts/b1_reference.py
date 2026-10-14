# ruff: noqa
"""B-1, item 1: reference-period (1995-2014) mean sfcWind of the six GCMs over Brazil on the native grids, against the ERA5
mean 10 m gust (the only ERA5 wind field on disk) and the Global Wind Atlas 100 m mean wind; fractions of native land cells
below 0.5, 1 and 2 m/s; where the masked cells are. Needs b1_BRA.npz and era5_gust_mean_BRA.npz in the scratch directory.
Usage: python b1_reference.py"""

from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from rasterio.enums import Resampling
from scipy.stats import pearsonr, spearmanr

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import *  # noqa

country = "BRA"
Z = np.load(SCRATCH / f"b1_{country}.npz")
E = np.load(SCRATCH / f"era5_gust_mean_{country}.npz")
poly = country_polygon(country)
gc = list(GCMS)


def edges(c):
    c = np.asarray(c, float)
    m = (c[1:] + c[:-1]) / 2
    return np.concatenate([[c[0] - (m[0] - c[0])], m, [c[-1] + (c[-1] - m[-1])]])


def block_mean(vals, slat, slon, glat, glon):
    """Mean of the source cells (regular, any order) whose centres fall in each target cell; NaN-aware."""
    ilat = np.digitize(slat, edges(glat)) - 1
    ilon = np.digitize(slon, edges(glon)) - 1
    ok_lat = (ilat >= 0) & (ilat < len(glat))
    ok_lon = (ilon >= 0) & (ilon < len(glon))
    LA, LO = np.meshgrid(ilat, ilon, indexing="ij")
    OKA, OKO = np.meshgrid(ok_lat, ok_lon, indexing="ij")
    m = OKA & OKO & np.isfinite(vals)
    idx = (LA * len(glon) + LO)[m]
    s = np.bincount(idx, weights=vals[m], minlength=len(glat) * len(glon))
    n = np.bincount(idx, minlength=len(glat) * len(glon))
    out = np.where(n > 0, s / np.maximum(n, 1), np.nan)
    return out.reshape(len(glat), len(glon)), n.reshape(len(glat), len(glon))


# --- ERA5 mean gust and GWA 100 m mean wind --------------------------------------------------------------------------------
era = E["mean"]  # (lat desc, lon)
elat, elon = E["lat"], E["lon"]
with rasterio.open(DATA / "raw" / "gwa" / country / f"{country}_wind_speed_100m.tif") as src:
    f = 16
    h, w = src.height // f, src.width // f
    arr = src.read(1, out_shape=(h, w), resampling=Resampling.average, masked=True).astype("float64").filled(np.nan)
    tr = src.transform * src.transform.scale(src.width / w, src.height / h)
glat = tr.f + tr.e * (np.arange(h) + 0.5)
glon = tr.c + tr.a * (np.arange(w) + 0.5)

rows, ref_fields = [], {}
for g in gc:
    la, lo = Z[f"native_lat|{g}"], Z[f"native_lon|{g}"]
    ref = Z[f"native_ref_wind|{g}"]
    land = Z[f"native_land|{g}"]
    e_g, _ = block_mean(era, elat, elon, la, lo)
    w_g, nw = block_mean(arr, glat, glon, la, lo)
    ref_fields[g] = (la, lo, ref, land, e_g, w_g)
    v = ref[land]
    r = {"GCM": g, "grid (lat x lon deg)": f"{abs(la[1] - la[0]):.2f} x {abs(lo[1] - lo[0]):.2f}", "native land cells": int(land.sum())}
    for t in (0.5, 1.0, 2.0):
        r[f"< {t} m/s"] = f"{(v < t).sum()} ({(v < t).mean():.1%})"
    r.update({"min": v.min(), "p5": np.percentile(v, 5), "median": np.median(v), "p95": np.percentile(v, 95), "max": v.max()})
    ok = land & np.isfinite(e_g) & np.isfinite(w_g)
    r["r vs ERA5 gust"] = pearsonr(ref[ok], e_g[ok])[0]
    r["r vs GWA 100 m"] = pearsonr(ref[ok], w_g[ok])[0]
    r["rho vs GWA 100 m"] = spearmanr(ref[ok], w_g[ok])[0]
    r["median GCM / GWA100"] = float(np.median(ref[ok] / w_g[ok]))
    r["median GCM / ERA5 gust"] = float(np.median(ref[ok] / e_g[ok]))
    rows.append(r)
print("\n## Reference mean sfcWind on the native grids, land cells (centre inside the mainland polygon)\n")
print(md(pd.DataFrame(rows)))

# --- what ERA5 and GWA say where MIROC6 is calm --------------------------------------------------------------------------
la, lo, ref, land, e_g, w_g = ref_fields["MIROC6"]
print("\n## Where MIROC6 reference wind is below 0.5, 1 and 2 m/s: the independent fields in the same native cells\n")
out = []
for t in (0.5, 1.0, 2.0):
    m = land & (ref < t) & np.isfinite(e_g) & np.isfinite(w_g)
    out.append({"MIROC6 ref <": f"{t} m/s", "native cells": int(m.sum()), "MIROC6 mean": ref[m].mean(), "ERA5 mean gust (median)": np.median(e_g[m]), "GWA 100 m (median)": np.median(w_g[m]),
                "GWA 100 m (min)": w_g[m].min(), "other five GCMs (median of the five)": np.nan})
# the other five GCMs interpolated to the MIROC6 land cells
mi = xr.DataArray(ref, coords={"lat": la, "lon": lo}, dims=("lat", "lon"))
LA2, LO2 = np.meshgrid(la, lo, indexing="ij")
others = []
for g in gc:
    if g == "MIROC6":
        continue
    a, b, r2, *_ = ref_fields[g]
    da = xr.DataArray(r2, coords={"lat": a, "lon": b}, dims=("lat", "lon"))
    others.append(da.interp(lat=xr.DataArray(la, dims="lat"), lon=xr.DataArray(lo, dims="lon")).values)
med5 = np.nanmedian(np.array(others), axis=0)
for i, t in enumerate((0.5, 1.0, 2.0)):
    m = land & (ref < t) & np.isfinite(med5)
    out[i]["other five GCMs (median of the five)"] = np.median(med5[m])
print(md(pd.DataFrame(out)))
ratio = ref / med5
print(f"\nMIROC6 / median of the other five, land cells: p5 {np.nanpercentile(ratio[land], 5):.2f}, median {np.nanmedian(ratio[land]):.2f}, p95 {np.nanpercentile(ratio[land], 95):.2f}, min {np.nanmin(ratio[land]):.2f}")
print("Pairwise Pearson correlation of the reference fields (land cells of MIROC6's grid, other GCMs interpolated):")
allf = {"MIROC6": ref, **{g: o for g, o in zip([x for x in gc if x != "MIROC6"], others)}}
D = pd.DataFrame({k: v[land] for k, v in allf.items()}).dropna()
print(D.corr().round(2).to_string())

# --- masked cells ------------------------------------------------------------------------------------------------------------
masked = pd.read_parquet(DATA / "outputs" / country / "climate_forcing" / "artifacts" / "forcing_masked.parquet")
core_ids = [f"m_{GCMS[g]}_{s}_2041_2070" for g in gc for s in SSPS.values()]
mk = masked.assign(core=masked["member"].isin(core_ids))
cid, lat, lon = Z["cell_id"], Z["lat"], Z["lon"]
per_cell = mk.groupby("cell_id").agg(n_all=("member", "size"), n_core=("core", "sum"))
pc = pd.DataFrame({"cell_id": cid, "lat": lat, "lon": lon}).merge(per_cell, on="cell_id", how="left").fillna({"n_all": 0, "n_core": 0})
cw = candidates(country, "wind")["cell_id"].to_numpy()
cs = candidates(country, "solar")["cell_id"].to_numpy()
pc["wind_cand"], pc["solar_cand"] = pc.cell_id.isin(cw), pc.cell_id.isin(cs)
sel = pc[pc.n_all > 0]
print("\n## Masked cells (any member, both windows)\n")
print(f"cells with a masked member: {len(sel)} of {len(pc)}; wind candidates {int(sel.wind_cand.sum())}, solar candidates {int(sel.solar_cand.sum())}, neither {int((~sel.wind_cand & ~sel.solar_cand).sum())}")
print(f"masked in the core window: {int((pc.n_core > 0).sum())} cells; wind candidates {int(((pc.n_core > 0) & pc.wind_cand).sum())}, solar candidates {int(((pc.n_core > 0) & pc.solar_cand).sum())}")
print("members masked per cell (core window, cells with at least one): " + pc.loc[pc.n_core > 0, "n_core"].describe().round(1).to_dict().__repr__())
by_state = pd.read_parquet(DATA / "outputs" / country / "land_eligibility" / "artifacts" / "admin1_units.parquet")
print("admin1 columns", list(by_state.columns)[:6])
cwd = candidates(country, "wind")[["cell_id", "admin1_id"]].merge(pc[["cell_id", "n_core"]], on="cell_id")
st = cwd.groupby("admin1_id").agg(wind_candidates=("cell_id", "size"), invalid_core=("n_core", lambda s: int((s > 0).sum())))
st["share"] = st.invalid_core / st.wind_candidates
print("\nWind candidates invalid in the core window, by admin 1 unit (top 10 by count):\n")
print(md(st.sort_values("invalid_core", ascending=False).head(10).reset_index()))

# --- figures -----------------------------------------------------------------------------------------------------------------
import geopandas as gpd

bra = gpd.read_file(DATA / "raw" / "gadm" / country / f"gadm41_{country}_0_mainland.shp").to_crs(4326)
ext = (-74.5, -33.5, -34.5, 6.0)


def outline(ax):
    bra.boundary.plot(ax=ax, color="k", lw=0.5)
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])


fig, axs = plt.subplots(2, 4, figsize=(15, 8.2), constrained_layout=True)
for ax, g in zip(axs.ravel()[:6], gc):
    la_, lo_, r_, land_, *_ = ref_fields[g]
    m = ax.pcolormesh(edges(lo_), edges(la_), r_, vmin=0, vmax=7, cmap="viridis", shading="flat")
    outline(ax)
    ax.set_title(f"{g}: sfcWind 1995-2014 (m/s)", fontsize=9)
la_, lo_, *_ = ref_fields["ACCESS-CM2"]
ax = axs.ravel()[6]
ax.imshow(era, extent=(elon[0] - 0.125, elon[-1] + 0.125, elat[-1] - 0.125, elat[0] + 0.125), vmin=0, vmax=7, cmap="viridis")
outline(ax)
ax.set_title("ERA5 mean 10 m gust fg10 (m/s)\n(not mean wind)", fontsize=9)
ax = axs.ravel()[7]
ax.imshow(arr, extent=(glon[0], glon[-1], glat[-1], glat[0]), vmin=0, vmax=7, cmap="viridis")
outline(ax)
ax.set_title("Global Wind Atlas mean wind at 100 m (m/s)", fontsize=9)
fig.colorbar(m, ax=axs, shrink=0.6, label="m/s (same scale in every panel)")
fig.savefig(FIG / "b1_reference_wind_maps.png", dpi=130)
plt.close(fig)

fig, axs = plt.subplots(1, 3, figsize=(15, 5.2), constrained_layout=True)
ax = axs[0]
for g in gc:
    la_, lo_, r_, land_, *_ = ref_fields[g]
    v = np.sort(r_[land_])
    ax.plot(v, np.arange(1, len(v) + 1) / len(v), label=g, lw=2 if g == "MIROC6" else 1)
for t in (0.5, 1, 2):
    ax.axvline(t, color="grey", ls=":", lw=0.8)
ax.set_xlim(0, 5)
ax.set_xlabel("reference mean sfcWind of a native land cell (m/s)")
ax.set_ylabel("cumulative share of native land cells")
ax.legend(fontsize=8)
ax.set_title("Distribution over native land cells")
ax = axs[1]
ax.scatter(w_g[land], ref[land], s=14, alpha=0.7, label="MIROC6 native land cells")
ax.axhline(0.5, color="r", ls=":")
ax.set_xlabel("Global Wind Atlas 100 m mean wind, averaged to the MIROC6 cell (m/s)")
ax.set_ylabel("MIROC6 reference sfcWind (m/s)")
ax.set_title(f"MIROC6 vs GWA (r = {rows[1]['r vs GWA 100 m']:.2f})")
ax = axs[2]
sc = ax.scatter(sel.lon, sel.lat, c=sel.n_all, s=0.6, cmap="magma_r", vmin=1, vmax=36)
bra.boundary.plot(ax=ax, color="k", lw=0.5)
ax.set_xlim(ext[0], ext[1])
ax.set_ylim(ext[2], ext[3])
ax.set_aspect("equal")
fig.colorbar(sc, ax=ax, shrink=0.7, label="members masked (of 36)")
ax.set_title("Cells with a masked member (0.05 degree)")
fig.savefig(FIG / "b1_miroc6_distribution_and_mask.png", dpi=130)
plt.close(fig)

fig, axs = plt.subplots(1, 3, figsize=(15, 5), constrained_layout=True)
cm_ = lambda v: np.where(v, 1.0, np.nan)
for ax, (title, cond) in zip(axs, (("Masked in the core window, any cell", pc.n_core > 0), ("... of which wind candidates", (pc.n_core > 0) & pc.wind_cand), ("... of which solar candidates", (pc.n_core > 0) & pc.solar_cand))):
    ax.scatter(pc.lon[~pc.n_core.gt(0)], pc.lat[~pc.n_core.gt(0)], s=0.15, c="#dddddd")
    ax.scatter(pc.lon[cond], pc.lat[cond], s=0.8, c="#c0392b")
    bra.boundary.plot(ax=ax, color="k", lw=0.5)
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3]); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(f"{title}: {int(cond.sum())} cells", fontsize=10)
fig.savefig(FIG / "b1_masked_cells_candidates.png", dpi=130)
plt.close(fig)
print("figures written")
