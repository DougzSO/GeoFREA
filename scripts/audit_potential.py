"""Numerical audit of the technical potential (T-14 of docs/figures/GEOFREA_figuras_spec_v2.md, COMMAND 65).

Read-only: it reads the artifacts of F3, F4 and F5 of the final round and `config/parameters.json`, writes nothing to the pipeline outputs, and imports nothing
from the pipeline. One country at a time:

    python scripts/audit_potential.py PRT [--out docs/phases/F5/audit_potential_65]

writes `<out>/<ISO3>.json` (every number of the report) and the curves `<out>/<ISO3>_supply_curves.png`. `docs/phases/F5/audit_potential_65.md` is written
from the three JSON files.

Items (T-14): 1 wind against solar; 2 area weighting; 3 supply curves and CF bands, with no resource cut; 4 plausibility of the totals; 5 effective
resolution of the figures; 6 climate forcing by GCM, SSP and window.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("GEOFREA_DATA_DIR", "D:/Douglas/DOUTORADO/GeoFREA_data")) / "outputs"
SCENARIOS = ("restrictive", "central", "permissive")
HOURS = 8760.0
EARTH_RADIUS_KM = 6371.0088  # mean radius; the spec's R^2 * dlon * (sin lat2 - sin lat1)
CELL_DEG = 0.05
CF_BANDS = ((0.0, 0.15), (0.15, 0.25), (0.25, 0.35), (0.35, 1.01))
CF_BAND_LABELS = ("<0.15", "0.15-0.25", "0.25-0.35", ">0.35")

# national electricity consumption, with source and year; the values were read from the pages cited, none is in the repository
CONSUMPTION_TWH = {
    "PRT": (
        50.7,
        2023,
        "REN, electricity supplied by the public grid in 2023 (REN press release of 2024-01-02, 'Renewable energy generation sets new record in 2023')",
    ),
    "BRA": (
        616.3,
        2023,
        "IBGE Anuario Estatistico do Brasil 2024, table 3105, reproducing the BEN 2024 (EPE, base year 2023): total electricity consumption 616.3 TWh (read from the table, to confirm in the EPE report)",
    ),
    "IND": (
        1505.9,
        2022,
        "Government statistics reported by the press: 1,505.91 billion units consumed in FY2022-23 (the full year FY2023-24 was not found; April-January of FY2023-24 was 1,354.97 BU, +7.5%)",
    ),
}


def log(msg: str) -> None:
    print(msg, flush=True)


def stats(x: np.ndarray) -> dict:
    x = np.asarray(x, dtype="float64")
    x = x[np.isfinite(x)]
    if x.size == 0:
        return {"n": 0}
    q = np.percentile(x, [5, 50, 95])
    return {
        "n": int(x.size),
        "mean": float(x.mean()),
        "min": float(x.min()),
        "p5": float(q[0]),
        "median": float(q[1]),
        "p95": float(q[2]),
        "max": float(x.max()),
    }


def corr(a: np.ndarray, b: np.ndarray) -> dict:
    from scipy import stats as sps

    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if a.size < 3 or np.ptp(a) == 0 or np.ptp(b) == 0:
        return {"n": int(a.size), "pearson": None, "spearman": None}
    return {
        "n": int(a.size),
        "pearson": float(sps.pearsonr(a, b)[0]),
        "spearman": float(sps.spearmanr(a, b)[0]),
    }


def parameters(iso: str) -> dict:
    p = json.loads((REPO_ROOT / "config" / "parameters.json").read_text(encoding="utf-8"))
    out = {}
    for tech in ("solar", "wind"):
        t = p["countries"][iso]["technologies"][tech]
        out[tech] = {key: t[key]["scenario_values"] for key in ("luf", "power_density_mw_per_km2")}
        out[tech]["eta_loss"] = t.get("eta_loss", {}).get("value")
    return out


class Country:
    def __init__(self, iso: str):
        self.iso = iso
        self.root = DATA / iso
        self.f3 = self.root / "land_eligibility" / "artifacts"
        self.f4 = self.root / "climate_forcing" / "artifacts"
        self.f5 = self.root / "technical_potential" / "artifacts"
        self.params = parameters(iso)

    def cells(self, tech: str, scenario: str) -> pd.DataFrame:
        return pd.read_parquet(self.f3 / f"cells_{tech}__{scenario}.parquet")

    def potential(self, tech: str, scenario: str, member: str = "m0") -> pd.DataFrame:
        df = pd.read_parquet(
            self.f5 / f"potential_{tech}__{scenario}.parquet",
            filters=[("member", "==", member)],
        )
        df["member"] = df["member"].astype(str)
        return df


# ─── item 1 ──────────────────────────────────────────────────────────────────────────────────────────────────────────


def item1(c: Country) -> dict:
    out: dict = {}
    cw, cs = c.cells("wind", "central"), c.cells("solar", "central")
    pw, ps = c.potential("wind", "central"), c.potential("solar", "central")
    luf_pd = {
        t: c.params[t]["luf"]["central"] * c.params[t]["power_density_mw_per_km2"]["central"]
        for t in ("solar", "wind")
    }
    out["luf_x_pd_central"] = luf_pd
    out["expected_ratio_constant_factor"] = luf_pd["solar"] / luf_pd["wind"]

    # (a) the ratio of the capacity densities, cell by cell, and what it is made of
    m = (
        pw[["cell_id", "P_MW", "CF", "E_MWh"]]
        .merge(ps[["cell_id", "P_MW", "CF", "E_MWh"]], on="cell_id", suffixes=("_w", "_s"))
        .merge(
            cw[["cell_id", "cell_area_km2", "eligible_area_km2"]].rename(
                columns={"eligible_area_km2": "elig_w"}
            ),
            on="cell_id",
        )
        .merge(
            cs[["cell_id", "eligible_area_km2"]].rename(columns={"eligible_area_km2": "elig_s"}),
            on="cell_id",
        )
    )
    m = m[(m.P_MW_w > 0) & (m.P_MW_s > 0)]
    dens_w, dens_s = m.P_MW_w / m.cell_area_km2, m.P_MW_s / m.cell_area_km2
    ratio = (dens_s / dens_w).to_numpy()
    share_ratio = (m.elig_s / m.elig_w).to_numpy()
    predicted = out["expected_ratio_constant_factor"] * share_ratio
    out["cells_with_both"] = len(m)
    out["cells_wind_only"] = int((~pw.cell_id.isin(ps.cell_id)).sum())
    out["cells_solar_only"] = int((~ps.cell_id.isin(pw.cell_id)).sum())
    out["capacity_density_ratio_solar_over_wind"] = stats(ratio)
    out["eligible_share_ratio_solar_over_wind"] = stats(share_ratio)
    out["ratio_equals_factor_times_share_ratio_max_rel_err"] = float(
        np.max(np.abs(ratio - predicted) / predicted)
    )
    out["share_of_cells_ratio_within_1pct_of_factor"] = float(
        np.mean(np.abs(ratio / out["expected_ratio_constant_factor"] - 1) < 0.01)
    )
    # the capacity of the cell is eligible area x LUF x PD
    for tech, df, cells in (("wind", pw, cw), ("solar", ps, cs)):
        j = df.merge(cells[["cell_id", "eligible_area_km2"]], on="cell_id")
        expect = j.eligible_area_km2 * luf_pd[tech]
        out[f"{tech}_P_equals_eligible_x_luf_x_pd_max_rel_err"] = float(
            np.max(np.abs(j.P_MW - expect) / np.maximum(expect, 1e-12))
        )
        out[f"{tech}_E_equals_P_x_CF_x_8760_max_rel_err"] = float(
            np.max(np.abs(j.E_MWh - j.P_MW * j.CF * HOURS) / np.maximum(j.E_MWh, 1e-12))
        )

    # (b) the eligible shares of the two technologies over all cells of the country
    j = cw.merge(cs, on="cell_id", suffixes=("_w", "_s"))
    sh_w = (j.eligible_area_km2_w / j.cell_area_km2_w).to_numpy()
    sh_s = (j.eligible_area_km2_s / j.cell_area_km2_s).to_numpy()
    out["eligible_share"] = {
        "cells": len(j),
        "mean_wind": float(sh_w.mean()),
        "mean_solar": float(sh_s.mean()),
        "cells_identical_share": float(np.mean(np.isclose(sh_w, sh_s, atol=1e-9))),
        "cells_wind_greater": float(np.mean(sh_w > sh_s + 1e-9)),
        "cells_solar_greater": float(np.mean(sh_s > sh_w + 1e-9)),
        "mean_abs_difference": float(np.mean(np.abs(sh_w - sh_s))),
        "correlation_wind_solar": corr(sh_w, sh_s),
    }
    # the terms that differ: cropland is excluded for solar and allowed for wind (E5), the slope maximum and the population limit also differ by technology
    terms = {}
    for e in ("E1", "E2", "E3", "E4", "E5", "E6"):
        a, b = j[f"excluded_area_km2_{e}_w"].to_numpy(), j[f"excluded_area_km2_{e}_s"].to_numpy()
        terms[e] = {
            "total_km2_wind": float(a.sum()),
            "total_km2_solar": float(b.sum()),
            "cells_wind_greater": float(np.mean(a > b + 1e-9)),
            "cells_solar_greater": float(np.mean(b > a + 1e-9)),
        }
    out["excluded_terms"] = terms
    # the cells where solar has the larger share: wind has requirements that solar does not (resource layers, the 3000 m limit of D-F3-015)
    sol_gt = sh_s > sh_w + 1e-9
    elev = j["elevation_m_w"].to_numpy()
    no_resource = (
        j[["weibull_a_100m", "weibull_k_100m", "air_density_100m"]].isna().any(axis=1).to_numpy()
    )
    out["cells_solar_share_above_wind"] = {
        "cells": int(sol_gt.sum()),
        "of_which_above_3000m": int((sol_gt & (elev > 3000)).sum()),
        "of_which_wind_resource_missing": int((sol_gt & no_resource).sum()),
        "of_which_other": int((sol_gt & ~(elev > 3000) & ~no_resource).sum()),
    }

    # (c) energy density against the CF of the technology itself
    dens = {}
    for tech, df, cells in (("wind", pw, cw), ("solar", ps, cs)):
        j2 = df.merge(cells[["cell_id", "cell_area_km2", "eligible_area_km2"]], on="cell_id")
        j2 = j2[j2.P_MW > 0]
        dens[tech] = {
            "energy_density_vs_own_CF": corr(
                (j2.E_MWh / j2.cell_area_km2).to_numpy(), j2.CF.to_numpy()
            ),
            "energy_per_eligible_km2_vs_own_CF": corr(
                (j2.E_MWh / j2.eligible_area_km2).to_numpy(), j2.CF.to_numpy()
            ),
            "capacity_density_vs_own_CF": corr(
                (j2.P_MW / j2.cell_area_km2).to_numpy(), j2.CF.to_numpy()
            ),
            "energy_density_vs_eligible_share": corr(
                (j2.E_MWh / j2.cell_area_km2).to_numpy(),
                (j2.eligible_area_km2 / j2.cell_area_km2).to_numpy(),
            ),
        }
    dens["cross_energy_density_wind_vs_solar_CF"] = None
    jj = pw.merge(ps, on="cell_id", suffixes=("_w", "_s")).merge(
        cw[["cell_id", "cell_area_km2"]], on="cell_id"
    )
    dens["energy_density_wind_vs_energy_density_solar"] = corr(
        (jj.E_MWh_w / jj.cell_area_km2).to_numpy(), (jj.E_MWh_s / jj.cell_area_km2).to_numpy()
    )
    dens["CF_wind_vs_CF_solar"] = corr(jj.CF_w.to_numpy(), jj.CF_s.to_numpy())
    dens["energy_density_wind_vs_solar_CF"] = corr(
        (jj.E_MWh_w / jj.cell_area_km2).to_numpy(), jj.CF_s.to_numpy()
    )
    out["energy_density_correlations"] = dens
    return out


# ─── item 2 ──────────────────────────────────────────────────────────────────────────────────────────────────────────


def spherical_area_km2(lat_c: np.ndarray, step_deg: float = CELL_DEG) -> np.ndarray:
    lat1 = np.radians(lat_c - step_deg / 2)
    lat2 = np.radians(lat_c + step_deg / 2)
    return EARTH_RADIUS_KM**2 * np.radians(step_deg) * (np.sin(lat2) - np.sin(lat1))


def item2(c: Country) -> dict:
    out: dict = {}
    for tech in ("wind", "solar"):
        cells = c.cells(tech, "central")
        pot = c.potential(tech, "central").merge(
            cells[["cell_id", "eligible_area_km2", "cell_area_km2", "lat_c"]], on="cell_id"
        )
        luf_pd = (
            c.params[tech]["luf"]["central"] * c.params[tech]["power_density_mw_per_km2"]["central"]
        )
        lat = cells.lat_c.to_numpy()
        sph = spherical_area_km2(lat)
        rel = (cells.cell_area_km2.to_numpy() - sph) / sph
        # the area of the table is the area of the cell inside the country: a cell cut by the border or the coast is smaller than the full cell of the formula
        full = rel > -0.01
        # the rows of the potential table are the candidate cells; the unweighted variants rebuild the same total with the eligible share of each cell
        share = (pot.eligible_area_km2 / pot.cell_area_km2).to_numpy()
        a_const = float(cells.cell_area_km2.mean())
        a_equator = float(spherical_area_km2(np.array([0.0]))[0])
        total_w = float(pot.P_MW.sum() / 1000)
        e_w = float(pot.E_MWh.sum() / 1e6)
        a_min, a_max = float(cells.cell_area_km2.min()), float(cells.cell_area_km2.max())
        lat_of_min, lat_of_max = (
            float(lat[cells.cell_area_km2.argmin()]),
            float(lat[cells.cell_area_km2.argmax()]),
        )
        out[tech] = {
            "cells_in_table": len(cells),
            "area_km2_min_max": [a_min, a_max],
            "lat_of_smallest_cell": lat_of_min,
            "lat_of_largest_cell": lat_of_max,
            "smallest_over_largest_area": a_min / a_max,
            "share_of_cells_cut_by_the_border": float(1 - full.mean()),
            "full_cells_area_vs_spherical_formula_rel_diff": stats(rel[full]),
            "full_cells_area_decreases_with_latitude": bool(
                np.corrcoef(
                    np.abs(cells.lat_c.to_numpy()[full]), cells.cell_area_km2.to_numpy()[full]
                )[0, 1]
                < 0
            ),
            "full_cell_area_at_lat_min_over_lat_max": float(
                spherical_area_km2(np.array([np.abs(lat).min()]))[0]
                / spherical_area_km2(np.array([np.abs(lat).max()]))[0]
            ),
            "abs_lat_min_max": [float(np.abs(lat).min()), float(np.abs(lat).max())],
            "uses_variable_area": bool(np.ptp(cells.cell_area_km2) > 1e-6),
            "P_GW_table": total_w,
            "E_TWh_table": e_w,
            "P_GW_cell_count_times_mean_area": float((share * a_const * luf_pd).sum() / 1000),
            "P_GW_constant_equatorial_area": float((share * a_equator * luf_pd).sum() / 1000),
            "mean_cell_area_km2": a_const,
            "equatorial_cell_area_km2": a_equator,
            "eligible_area_km2_sum": float(cells.eligible_area_km2.sum()),
            "eligible_area_km2_if_mean_area": float(
                (cells.eligible_area_km2 / cells.cell_area_km2).sum() * a_const
            ),
        }
        o = out[tech]
        o["effect_mean_area_pct"] = 100 * (o["P_GW_cell_count_times_mean_area"] / total_w - 1)
        o["effect_equatorial_area_pct"] = 100 * (o["P_GW_constant_equatorial_area"] / total_w - 1)
    return out


# ─── item 3 ──────────────────────────────────────────────────────────────────────────────────────────────────────────


def item3(c: Country, out_dir: Path) -> dict:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out: dict = {}
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
    colours = {"restrictive": "#0072B2", "central": "#000000", "permissive": "#D55E00"}
    for row, tech in enumerate(("solar", "wind")):
        out[tech] = {}
        for scenario in SCENARIOS:
            pot = c.potential(tech, scenario)
            pot = pot[pot.P_MW > 0].sort_values("CF", ascending=False)
            cum_gw = pot.P_MW.cumsum().to_numpy() / 1000
            cum_twh = pot.E_MWh.cumsum().to_numpy() / 1e6
            cf = pot.CF.to_numpy()
            for col, (y, lab) in enumerate(((cum_gw, "GW"), (cum_twh, "TWh per year"))):
                ax = axes[row, col]
                ax.plot(
                    cf,
                    y,
                    color=colours[scenario],
                    lw=2 if scenario == "central" else 1.2,
                    label=scenario,
                )
                ax.set_xlabel("capacity factor of the cell (cells from the highest CF down)")
                ax.set_ylabel(f"cumulative {lab}")
                ax.set_title(f"{c.iso} {tech}: cumulative {lab} against CF")
                ax.invert_xaxis()
                ax.grid(alpha=0.3)
            bands = []
            for (lo, hi), label in zip(CF_BANDS, CF_BAND_LABELS):
                sel = (pot.CF >= lo) & (pot.CF < hi)
                bands.append(
                    {
                        "band": label,
                        "cells": int(sel.sum()),
                        "GW": float(pot.P_MW[sel].sum() / 1000),
                        "TWh": float(pot.E_MWh[sel].sum() / 1e6),
                    }
                )
            tot_gw = sum(b["GW"] for b in bands)
            tot_twh = sum(b["TWh"] for b in bands)
            for b in bands:
                b["GW_share"] = b["GW"] / tot_gw if tot_gw else None
                b["TWh_share"] = b["TWh"] / tot_twh if tot_twh else None
            out[tech][scenario] = {
                "bands": bands,
                "total_GW": float(pot.P_MW.sum() / 1000),
                "total_TWh": float(pot.E_MWh.sum() / 1e6),
                "cf_energy_weighted": float(pot.E_MWh.sum() / (pot.P_MW.sum() * HOURS)),
                "cf_stats": stats(cf),
            }
    axes[0, 0].legend()
    path = out_dir / f"{c.iso}_supply_curves.png"
    fig.savefig(path, dpi=130)
    plt.close(fig)
    out["figure"] = path.name
    return out


# ─── item 4 ──────────────────────────────────────────────────────────────────────────────────────────────────────────


def item4(c: Country) -> dict:
    out: dict = {"consumption": None}
    twh, year, src = CONSUMPTION_TWH[c.iso]
    out["consumption"] = {"TWh": twh, "year": year, "source": src}
    for tech in ("solar", "wind"):
        out[tech] = {}
        for scenario in SCENARIOS:
            cells = c.cells(tech, scenario)
            pot = c.potential(tech, scenario).merge(
                cells[["cell_id", "cell_area_km2", "eligible_area_km2"]], on="cell_id"
            )
            luf = c.params[tech]["luf"][scenario]
            pd_ = c.params[tech]["power_density_mw_per_km2"][scenario]
            ceiling = luf * pd_
            dens = (pot.P_MW / pot.cell_area_km2).to_numpy()
            share = (pot.eligible_area_km2 / pot.cell_area_km2).to_numpy()
            e_twh = float(pot.E_MWh.sum() / 1e6)
            out[tech][scenario] = {
                "eligible_fraction_of_country_area": float(
                    cells.eligible_area_km2.sum() / cells.cell_area_km2.sum()
                ),
                "country_area_km2_of_cells": float(cells.cell_area_km2.sum()),
                "eligible_area_km2": float(cells.eligible_area_km2.sum()),
                "luf": luf,
                "power_density_mw_per_km2": pd_,
                "ceiling_mw_per_km2": ceiling,
                "max_observed_capacity_density_mw_per_km2": float(dens.max())
                if dens.size
                else None,
                "max_density_over_ceiling": float(dens.max() / ceiling) if dens.size else None,
                "max_eligible_share": float(share.max()) if share.size else None,
                "candidate_cells": int(share.size),
                "cells_with_share_ge_0.999": int((share >= 0.999).sum()),
                "eligible_share_percentiles_p50_p90_p99": [
                    float(v) for v in np.percentile(share, [50, 90, 99])
                ]
                if share.size
                else None,
                "ceiling_times_max_share": float(ceiling * share.max()) if share.size else None,
                "P_GW": float(pot.P_MW.sum() / 1000),
                "E_TWh": e_twh,
                "E_over_national_consumption": e_twh / twh,
            }
    return out


# ─── item 5 ──────────────────────────────────────────────────────────────────────────────────────────────────────────


def png_size(path: Path) -> tuple[int, int]:
    with open(path, "rb") as f:
        head = f.read(24)
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def item5(c: Country) -> dict:
    import rasterio

    out: dict = {"rasters": {}, "figures": {}}
    for phase_dir in sorted(p for p in c.root.iterdir() if (p / "artifacts").is_dir()):
        res = {}
        for tif in sorted((phase_dir / "artifacts").glob("*.tif")):
            with rasterio.open(tif) as r:
                res[tif.name] = {
                    "res_deg": [round(abs(r.res[0]), 6), round(abs(r.res[1]), 6)],
                    "shape": list(r.shape),
                    "crs": str(r.crs),
                }
        if res:
            out["rasters"][phase_dir.name] = res
    shapes = {
        name: v["shape"]
        for name, v in out["rasters"].get("technical_potential", {}).items()
        if name.startswith("potential_density")
    }
    ncols = next(iter(shapes.values()))[1] if shapes else None
    out["analysis_grid_columns"] = ncols
    for phase_dir in sorted(p for p in c.root.iterdir() if (p / "figures").is_dir()):
        pngs = sorted((phase_dir / "figures").glob("*.png"))
        if not pngs:
            continue
        sizes = {p.name: png_size(p) for p in pngs}
        width = [s[0] for s in sizes.values()]
        out["figures"][phase_dir.name] = {
            "n_png": len(pngs),
            "width_px_min_max": [min(width), max(width)],
            "height_px_min_max": [
                min(s[1] for s in sizes.values()),
                max(s[1] for s in sizes.values()),
            ],
            "example": pngs[0].name,
        }
    if ncols:
        for v in out["figures"].values():
            v["image_px_per_analysis_cell_upper_bound"] = v["width_px_min_max"][1] / ncols
    return out


# ─── item 6 ──────────────────────────────────────────────────────────────────────────────────────────────────────────


def item6(c: Country) -> dict:
    members = yaml.safe_load((c.f4 / "members.yaml").read_text(encoding="utf-8"))["members"]
    meta = {m["member"]: m for m in members}
    f = pd.read_parquet(
        c.f4 / "forcing.parquet", columns=["member", "delta_rsds", "dT", "delta_wind"]
    )
    f["member"] = f["member"].astype(str)
    # cells at the ends of the valid range of the wind factor [0.5, 1.5] (F4 contract)
    f["_hi"] = (f.delta_wind >= 1.4999).astype("float32")
    f["_lo"] = (f.delta_wind <= 0.5001).astype("float32")
    g = f.groupby("member", observed=True)
    rows = []
    agg = pd.concat(
        {
            "rsds_mean": g.delta_rsds.mean(),
            "rsds_min": g.delta_rsds.min(),
            "rsds_max": g.delta_rsds.max(),
            "wind_mean": g.delta_wind.mean(),
            "wind_min": g.delta_wind.min(),
            "wind_max": g.delta_wind.max(),
            "dT_mean": g.dT.mean(),
            "dT_min": g.dT.min(),
            "dT_max": g.dT.max(),
            "n": g.size(),
            "wind_share_at_upper_limit": g._hi.mean(),
            "wind_share_at_lower_limit": g._lo.mean(),
        },
        axis=1,
    )
    del f
    aggs = {
        t: pd.read_parquet(c.f5 / f"potential_aggregates_{t}.parquet") for t in ("solar", "wind")
    }
    for name, r in agg.iterrows():
        m = meta.get(name, {})
        row = {
            "member": name,
            "gcm": m.get("gcm", "reference"),
            "ssp": m.get("ssp", "-"),
            "window": m.get("window", "1995-2014"),
            **{k: float(v) for k, v in r.items()},
        }
        for t in ("solar", "wind"):
            a = aggs[t]
            a = a[(a.scenario == "central") & (a.member == name)]
            if len(a):
                row[f"dE_{t}_pct_like_for_like"] = float(a.delta_E_pct_vs_m0_like_for_like.iloc[0])
                row[f"E_{t}_TWh"] = float(a.E_TWh.iloc[0])
        rows.append(row)
    table = pd.DataFrame(rows)
    fut = table[table.member != "m0"].copy()
    pivot = fut.pivot_table(index=["gcm", "ssp"], columns="window", values="rsds_mean")
    out = {"members": rows, "reference": table[table.member == "m0"].iloc[0].to_dict()}

    # sanity: is a later window of the lowest-forcing SSP above an earlier window of a higher one?
    flags = []
    for gcm in sorted(fut.gcm.unique()):
        sub = fut[fut.gcm == gcm].set_index(["ssp", "window"]).rsds_mean
        try:
            late126 = sub[("SSP1-2.6", "2071-2100")]
            early370 = sub[("SSP3-7.0", "2041-2070")]
            flags.append(
                {
                    "gcm": gcm,
                    "rsds_ssp126_2071_2100": float(late126),
                    "rsds_ssp370_2041_2070": float(early370),
                    "ssp126_late_above_ssp370_early": bool(late126 > early370),
                }
            )
        except KeyError:
            pass
    out["solar_ratio_ordering_check"] = flags
    ens = fut.groupby(["ssp", "window"])[["rsds_mean", "wind_mean", "dT_mean"]].mean()
    out["ensemble_mean"] = [
        {"ssp": s, "window": w, **{k: float(v) for k, v in r.items()}}
        for (s, w), r in ens.iterrows()
    ]
    # does the change of the energy follow the change of the forcing? solar: ratio x thermal term; wind: roughly the cube of the wind ratio near rated
    chk = fut.copy()
    chk["wind_ratio_cubed_minus_1_pct"] = 100 * (chk.wind_mean**3 - 1)
    chk["solar_ratio_minus_1_pct"] = 100 * (chk.rsds_mean - 1)
    out["energy_vs_forcing"] = {
        "wind_dE_vs_cubed_wind_ratio": corr(
            chk.dE_wind_pct_like_for_like.to_numpy(), chk.wind_ratio_cubed_minus_1_pct.to_numpy()
        ),
        "solar_dE_vs_rsds_ratio": corr(
            chk.dE_solar_pct_like_for_like.to_numpy(), chk.solar_ratio_minus_1_pct.to_numpy()
        ),
        "wind_dE_pct_range": [
            float(chk.dE_wind_pct_like_for_like.min()),
            float(chk.dE_wind_pct_like_for_like.max()),
        ],
        "solar_dE_pct_range": [
            float(chk.dE_solar_pct_like_for_like.min()),
            float(chk.dE_solar_pct_like_for_like.max()),
        ],
        "wind_ratio_range": [float(chk.wind_mean.min()), float(chk.wind_mean.max())],
    }
    out["_pivot_rsds"] = {f"{g}|{s}": r.to_dict() for (g, s), r in pivot.iterrows()}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("iso")
    ap.add_argument(
        "--out", default=str(REPO_ROOT / "docs" / "phases" / "F5" / "audit_potential_65")
    )
    ap.add_argument("--items", default="1,2,3,4,5,6")
    args = ap.parse_args(argv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    c = Country(args.iso)
    wanted = {int(x) for x in args.items.split(",")}
    result: dict = {"iso": args.iso, "parameters": c.params}
    steps = {
        1: lambda: item1(c),
        2: lambda: item2(c),
        3: lambda: item3(c, out_dir),
        4: lambda: item4(c),
        5: lambda: item5(c),
        6: lambda: item6(c),
    }
    for k, fn in steps.items():
        if k in wanted:
            log(f"[{args.iso}] item {k}")
            result[f"item{k}"] = fn()
    path = out_dir / f"{args.iso}.json"
    if path.exists() and wanted != {1, 2, 3, 4, 5, 6}:
        previous = json.loads(path.read_text(encoding="utf-8"))
        previous.update(result)
        result = previous
    path.write_text(json.dumps(result, indent=1, default=float), encoding="utf-8")
    log(f"[{args.iso}] written {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
