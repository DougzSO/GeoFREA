# ruff: noqa
"""Item 5: wind candidates by DEM altitude and air density, protected-area overlap, position in the nominal ranking under the
synthetic parameters (in memory, ZZZ test values and the synthetic power curve), and the Weibull k < 1 cells.
Reads only outputs of F2a, F2b and F3. Usage: python altitude_k.py"""

from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import *  # noqa
from geofrea.lcoe_modeling.kernel import CellInputs, SampleInputs, lcoe_direct
from geofrea.technical_potential.capacity import annual_energy_mwh, capacity_mw
from geofrea.technical_potential.pipeline import HOURS_PER_YEAR, RHO0_KG_M3
from geofrea.technical_potential.power_curve import load_power_curve
from geofrea.technical_potential.weibull_cf import wind_cf_reference
from geofrea.technical_potential.wind_profile import resource_at_hub_height
import json

REPO = Path(__file__).resolve().parents[3]
CURVE = load_power_curve(REPO / "tests" / "fixtures" / "power_curves" / "synthetic_curve.yaml")
Z = json.load(open(REPO / "config" / "parameters.json", encoding="utf-8"))["countries"]["ZZZ"]["technologies"]["wind"]
P = {k: v["value"] for k, v in Z.items()}
print(f"synthetic parameters used (ZZZ test values): {P}\nrho0 = {RHO0_KG_M3} kg/m3, {HOURS_PER_YEAR} h/year, synthetic power curve rated {CURVE.rated_power_kw} kW\n")
ALT = (2000, 3000, 4000)
DENS = (1.0, 0.9, 0.8, 0.7)


def cell_elevation(country: str, c: pd.DataFrame) -> np.ndarray:
    """Mean DEM elevation (m) over the 5 x 5 pixels (0.01 degree) of each 0.05 degree cell, from the F2a aligned elevation."""
    with rasterio.open(DATA / "outputs" / country / "grid_alignment" / "artifacts" / f"{country}_elevation_aligned.tif") as src:
        a = src.read(1).astype("float64")
        a[a == src.nodata] = np.nan
        t = src.transform
    r0 = np.round((t.f - (c["lat_c"].to_numpy() + 0.025)) / -t.e).astype(int)
    c0 = np.round(((c["lon_c"].to_numpy() - 0.025) - t.c) / t.a).astype(int)
    out = np.full(len(c), np.nan)
    for i, (r, k) in enumerate(zip(r0, c0)):
        blk = a[max(r, 0) : r + 5, max(k, 0) : k + 5]
        if blk.size and np.isfinite(blk).any():
            out[i] = np.nanmean(blk)
    return out


def nominal_lcoe(c: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    a, k, rho = resource_at_hub_height(
        {100.0: c.weibull_a_100m.to_numpy(), 150.0: c.weibull_a_150m.to_numpy(), 200.0: c.weibull_a_200m.to_numpy()},
        {100.0: c.weibull_k_100m.to_numpy(), 150.0: c.weibull_k_150m.to_numpy(), 200.0: c.weibull_k_200m.to_numpy()},
        {100.0: c.air_density_100m.to_numpy(), 150.0: c.air_density_150m.to_numpy(), 200.0: c.air_density_200m.to_numpy()},
        float(P["hub_height_m"]),
    )
    cf = wind_cf_reference(a, k, rho, CURVE, RHO0_KG_M3, float(P["eta_loss"]))
    p = capacity_mw(c.eligible_area_km2.to_numpy(), float(P["luf"]), float(P["power_density_mw_per_km2"]))
    e = annual_energy_mwh(p, cf, HOURS_PER_YEAR)
    cells = CellInputs(p_mw=p, dist_grid_km=c.dist_grid_km.to_numpy(), dist_road_km=c.dist_road_km.to_numpy(), energy_mwh=e, energy_offset=np.ones(len(c)), energy_slope=np.zeros(len(c)))
    s = SampleInputs.from_mapping({
        "capex_usd_per_kw": P["capex_usd_per_kw"], "opex_fixed_frac": P["opex_fixed_frac"], "opex_var_usd_per_mwh": P["opex_var_usd_per_mwh"], "lifetime_years": P["lifetime_years"],
        "discount_rate": P["discount_rate"], "degradation_rate": P["degradation_rate"], "grid_cost_usd_per_mw_km": P["grid_cost_usd_per_mw_km"],
        "substation_cost_usd_per_mw": P["substation_cost_usd_per_mw"], "road_cost_usd_per_km": P["road_cost_usd_per_km"], "energy_parameter": P["eta_loss"]}, 1)
    return lcoe_direct(cells, s)[:, 0], cf, p


res_alt, res_dens, res_prot, res_rank, res_k = [], [], [], [], []
frames = {}
for country in ("BRA", "PRT", "IND"):
    c = candidates(country, "wind").reset_index(drop=True)
    perm = candidates_perm = pd.read_parquet(DATA / "outputs" / country / "land_eligibility" / "artifacts" / "candidates_wind__permissive.parquet").set_index("cell_id")
    c["elev_m"] = cell_elevation(country, c)
    c["lcoe"], c["cf"], c["p_mw"] = nominal_lcoe(c)
    c["rank_pct"] = c["lcoe"].rank(method="first") / len(c)
    # capacity-weighted position: share of total candidate capacity that is cheaper than or equal to this cell
    order = np.argsort(c["lcoe"].to_numpy(), kind="stable")
    cum = np.cumsum(c["p_mw"].to_numpy()[order]) / c["p_mw"].sum()
    c["cap_rank"] = np.empty(len(c)); c.loc[order, "cap_rank"] = cum
    c["e1_share"] = c["excluded_area_km2_E1"] / c["cell_area_km2"]
    c["e1_perm_share"] = perm["excluded_area_km2_E1"].reindex(c["cell_id"]).to_numpy() / c["cell_area_km2"]
    frames[country] = c
    n = len(c)
    print(f"\n### {country}: {n} wind candidates, elevation known for {int(c.elev_m.notna().sum())}; median {c.elev_m.median():.0f} m, p99 {c.elev_m.quantile(.99):.0f} m, max {c.elev_m.max():.0f} m")
    top_cells = c["rank_pct"] <= 0.10
    top_cap = c["cap_rank"] <= 0.10
    for t in ALT:
        s = c.elev_m > t
        res_alt.append({"country": country, "DEM altitude": f"> {t} m", "candidates": int(s.sum()), "share of candidates": s.mean(), "eligible area (km2)": c.loc[s, "eligible_area_km2"].sum(),
                        "capacity, synthetic PD and LUF (MW)": c.loc[s, "p_mw"].sum(), "with air_density_100m < 0.8": int((s & (c.air_density_100m < 0.8)).sum()),
                        "median air density 100 m": c.loc[s, "air_density_100m"].median() if s.any() else np.nan})
        res_prot.append({"country": country, "DEM altitude": f"> {t} m", "candidates": int(s.sum()), "overlap a protected area (E1 > 0, central)": int((s & (c.e1_share > 0)).sum()),
                         "E1 share >= 0.5": int((s & (c.e1_share >= 0.5)).sum()), "less excluded by E1 in the permissive scenario": int((s & (c.e1_perm_share < c.e1_share - 1e-9)).sum()),
                         "dominant exclusion is E1": int((s & (c.dominant_exclusion == "E1")).sum())})
        res_rank.append({"country": country, "DEM altitude": f"> {t} m", "candidates": int(s.sum()), "in the cheapest 10% of cells": int((s & top_cells).sum()), "of those cells, share of the top 10%": (s & top_cells).sum() / max(top_cells.sum(), 1),
                         "in the cheapest 10% of capacity": int((s & top_cap).sum()), "median nominal CF": c.loc[s, "cf"].median() if s.any() else np.nan,
                         "median nominal LCOE (USD/MWh)": c.loc[s, "lcoe"].median() if s.any() else np.nan})
    for d in DENS:
        s = c.air_density_100m < d
        res_dens.append({"country": country, "air_density_100m": f"< {d} kg/m3", "candidates": int(s.sum()), "share": s.mean(), "eligible area (km2)": c.loc[s, "eligible_area_km2"].sum(),
                         "median DEM altitude (m)": c.loc[s, "elev_m"].median() if s.any() else np.nan, "in the cheapest 10% of cells": int((s & top_cells).sum())})
    kk = c.weibull_k_100m
    for name, s in (("k_100 < 1", kk < 1), ("k_100 < 1.2", kk < 1.2), ("k_150 < 1", c.weibull_k_150m < 1), ("k_200 < 1", c.weibull_k_200m < 1), ("k at the hub height (125 m) < 1", None)):
        if s is None:
            a_, k_, r_ = resource_at_hub_height({100.0: c.weibull_a_100m.to_numpy(), 150.0: c.weibull_a_150m.to_numpy()}, {100.0: c.weibull_k_100m.to_numpy(), 150.0: c.weibull_k_150m.to_numpy()}, {100.0: c.air_density_100m.to_numpy(), 150.0: c.air_density_150m.to_numpy()}, 125.0)
            s = pd.Series(k_ < 1, index=c.index)
        res_k.append({"country": country, "criterion": name, "candidates": int(s.sum()), "share": s.mean(), "eligible area (km2)": c.loc[s, "eligible_area_km2"].sum(),
                      "median DEM altitude (m)": c.loc[s, "elev_m"].median() if s.any() else np.nan, "in the cheapest 10% of cells": int((s & top_cells).sum()), "median Weibull A 100 m": c.loc[s, "weibull_a_100m"].median() if s.any() else np.nan})
    c1 = c[c.weibull_k_100m < 1]
    if len(c1):
        print(f"k_100 < 1: n={len(c1)}, k min {c1.weibull_k_100m.min():.2f}, p50 {c1.weibull_k_100m.median():.2f}; A_100 p50 {c1.weibull_a_100m.median():.2f}; elevation p50 {c1.elev_m.median():.0f} m, p90 {c1.elev_m.quantile(.9):.0f} m; "
              f"cheapest-10% cells: {int((c1.rank_pct <= .1).sum())}; CF p50 {c1.cf.median():.3f}")
    # relation between altitude and density: the ISA-based expectation
    ok = c.elev_m.notna()
    print(f"correlation elevation vs air_density_100m: {np.corrcoef(c.elev_m[ok], c.air_density_100m[ok])[0, 1]:.3f}")

for title, rows in (("Wind candidates by DEM altitude (cell mean of the 30 m DEM aligned to 0.01 degree)", res_alt), ("Overlap with protected areas (E1)", res_prot),
                    ("Position in the nominal ranking under the synthetic parameters (in memory; ranking of the candidates of the central scenario)", res_rank), ("Wind candidates by air density at 100 m", res_dens), ("Weibull shape k below 1 or 1.2", res_k)):
    print(f"\n## {title}\n")
    print(md(pd.DataFrame(rows), ".4g"))

# figures --------------------------------------------------------------------------------------------------------------------------
fig, axs = plt.subplots(2, 3, figsize=(15, 8.5), constrained_layout=True)
for j, country in enumerate(("BRA", "PRT", "IND")):
    c = frames[country]
    g = gpd.read_file(DATA / "raw" / "gadm" / country / f"gadm41_{country}_0_mainland.shp").to_crs(4326)
    ax = axs[0, j]
    g.boundary.plot(ax=ax, color="k", lw=0.4)
    ax.scatter(c.lon_c, c.lat_c, s=0.2, c="#cccccc")
    hi = c[c.elev_m > 2000]
    sc = ax.scatter(hi.lon_c, hi.lat_c, s=2, c=hi.elev_m, cmap="plasma", vmin=2000, vmax=max(5000, hi.elev_m.max() if len(hi) else 5000))
    lo = c[c.weibull_k_100m < 1]
    ax.scatter(lo.lon_c, lo.lat_c, s=14, facecolors="none", edgecolors="c", linewidths=0.6, label=f"k_100 < 1 ({len(lo)})")
    ax.set_aspect("equal"); ax.legend(fontsize=8, loc="lower left")
    ax.set_title(f"{country}: wind candidates (grey); > 2000 m coloured by DEM altitude ({len(hi)})", fontsize=9)
    if len(hi): fig.colorbar(sc, ax=ax, shrink=0.6, label="m")
    ax = axs[1, j]
    ax.scatter(c.elev_m, c.air_density_100m, s=1, alpha=0.3)
    for d in (0.8,):
        ax.axhline(d, color="r", lw=0.8, ls=":")
    for t in ALT:
        ax.axvline(t, color="grey", lw=0.8, ls=":")
    ax.set_xlabel("cell DEM altitude (m)"); ax.set_ylabel("air density at 100 m (kg/m3)")
    ax.set_title(f"{country}: density vs altitude", fontsize=9)
fig.savefig(FIG / "altitude_density_k_candidates.png", dpi=130)

fig, axs = plt.subplots(1, 3, figsize=(15, 4.5), constrained_layout=True)
for j, country in enumerate(("BRA", "PRT", "IND")):
    c = frames[country]
    ax = axs[j]
    ax.hist(c.weibull_k_100m, bins=100, color="#2c7fb8")
    ax.axvline(1, color="r")
    ax.set_yscale("log")
    ax.set_xlabel("Weibull k at 100 m, wind candidates"); ax.set_title(f"{country}: k < 1 in {(c.weibull_k_100m < 1).sum()} of {len(c)}", fontsize=9)
fig.savefig(FIG / "weibull_k_distribution.png", dpi=130)
print("figures written")
