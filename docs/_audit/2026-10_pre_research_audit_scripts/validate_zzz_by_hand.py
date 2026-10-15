# ruff: noqa
"""Hand validation of the synthetic country ZZZ, phase by phase (audit 2026-10, item 7).

Every expected value is computed here from the inputs of the phase with plain numpy/scipy, from the formula of METHODOLOGY and WITHOUT importing
anything from `geofrea` (the point is an independent implementation). The obtained value is read from the artifact the phase wrote. The script
prints a Markdown table (what, expected, obtained, difference, tolerance, result) and exits 1 if any row fails.

Usage: python validate_zzz_by_hand.py <data dir of a finished ZZZ or ZZZ2 run, e.g. pytest --basetemp=... zzz_data0> [technology] [world]

`world` is `zzz` (default) or `zzz2` (COMMAND 39, M-1/M-4). ZZZ keeps the order of its cells in every future, so there the PRIM outcome by hand is zero and the stored one is the test
rule of `tests/synthetic` (D-F7-057); in ZZZ2 the outcome is not replaced and must equal the one recomputed by hand for every future. The parameters are read from the run's own
`parameters_synthetic.json` when it has one (ZZZ2 raises the distance costs in that copy), else from `config/parameters.json`.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import xarray as xr
import yaml
from scipy import integrate
from scipy.interpolate import RegularGridInterpolator

DATA = Path(sys.argv[1])
TECH = sys.argv[2] if len(sys.argv) > 2 else "wind"
WORLD = sys.argv[3] if len(sys.argv) > 3 else "zzz"
REPO = Path(__file__).resolve().parents[3]
OUT = DATA / "outputs" / "ZZZ"
PARAMS = json.loads(
    (
        DATA / "parameters_synthetic.json"
        if (DATA / "parameters_synthetic.json").is_file()
        else REPO / "config" / "parameters.json"
    ).read_text(encoding="utf-8")
)["countries"][
    "ZZZ"
]["technologies"]
EXPERIMENTS = yaml.safe_load((DATA / "experiments_zzz.yaml").read_text(encoding="utf-8"))
CELL_DEG, PIXEL_DEG = 0.05, 0.01
HOURS = 8760.0
RHO0 = 1.225
ROWS: list[tuple[str, str, float, float, float, bool]] = []
EXPECT: dict[str, float] = {}  # values recomputed by hand that a test may pin (printed as JSON after the table)


def val(tech: str, key: str) -> float:
    return float(PARAMS[tech][key]["value"])


def check(label: str, expected: float, obtained: float, tol: float, relative: bool = True) -> None:
    diff = abs(expected - obtained)
    scale = max(abs(expected), 1e-300) if relative else 1.0
    ok = bool(diff / scale <= tol) if np.isfinite(diff) else False
    ROWS.append((label, f"{expected:.10g}", obtained, diff, tol, ok))


def check_text(label: str, expected: str, obtained: str) -> None:
    ROWS.append(
        (label, expected, obtained, 0.0 if expected == obtained else 1.0, 0.0, expected == obtained)
    )


def table(rel: str) -> pd.DataFrame:
    return pd.read_parquet(OUT / rel)


# ---------------------------------------------------------------------------------------------------------------------------------------
# F3 land eligibility: eligible area of a cell = sum over its pixels of (eligible fraction x geodesic pixel area)
# ---------------------------------------------------------------------------------------------------------------------------------------
A_WGS84, F_WGS84 = 6378137.0, 1 / 298.257223563
E2 = F_WGS84 * (2 - F_WGS84)


def pixel_area_km2(lat_south: float, lat_north: float, dlon_deg: float) -> float:
    """Area of a lat-lon rectangle on the WGS84 ellipsoid by integrating the area element (independent of any closed form)."""

    def element(phi: float) -> float:
        s = math.sin(phi)
        return A_WGS84**2 * (1 - E2) * math.cos(phi) / (1 - E2 * s * s) ** 2

    inner, _ = integrate.quad(
        element, math.radians(lat_south), math.radians(lat_north), epsabs=1e-3, epsrel=1e-12
    )
    return inner * math.radians(dlon_deg) / 1e6


def validate_f3() -> pd.Series:
    cand = table(f"land_eligibility/artifacts/candidates_{TECH}__central.parquet")
    cell = cand.loc[cand["eligible_area_km2"].idxmax()]
    with rasterio.open(OUT / f"land_eligibility/artifacts/eligible_fraction_{TECH}.tif") as src:
        data = src.read(1).astype("float64")
        nodata = src.nodata
        t = src.transform
        total_elig = total_area = 0.0
        for r in range(data.shape[0]):
            for c in range(data.shape[1]):
                lon, lat = t * (c + 0.5, r + 0.5)
                if (
                    abs(lat - cell["lat_c"]) < CELL_DEG / 2
                    and abs(lon - cell["lon_c"]) < CELL_DEG / 2
                ):
                    a = pixel_area_km2(lat - PIXEL_DEG / 2, lat + PIXEL_DEG / 2, PIXEL_DEG)
                    total_area += a
                    f = data[r, c]
                    total_elig += (
                        0.0 if (nodata is not None and f == nodata) or not np.isfinite(f) else f * a
                    )
    check(
        f"F3 cell {int(cell['cell_id'])}: cell_area_km2 (sum of 25 geodesic pixel areas)",
        total_area,
        float(cell["cell_area_km2"]),
        1e-4,
    )
    check(
        f"F3 cell {int(cell['cell_id'])}: eligible_area_km2 (sum fraction x pixel area)",
        total_elig,
        float(cell["eligible_area_km2"]),
        1e-4,
    )
    return cell


# ---------------------------------------------------------------------------------------------------------------------------------------
# F4 climate forcing: change factors of one member at one cell centre from the miniature CMIP6 files
# ---------------------------------------------------------------------------------------------------------------------------------------
MEMBER = "m_gfdl_esm4_ssp370_2041_2070"


def native(model: str, exp: str, var: str, y0: int, y1: int) -> xr.DataArray:
    path = DATA / "raw" / "cmip6" / "_global" / model / f"{model}_{exp}_{var}.nc"
    ds = xr.open_dataset(path)
    da = (
        ds[var].sel(time=slice(f"{y0}-01-01", f"{y1}-12-31")).astype("float64")
    )  # the files are float32: sum in double
    return da.mean("time").load()


def nbhd3(a: np.ndarray) -> np.ndarray:
    out = np.full_like(a, np.nan)
    for i in range(1, a.shape[0] - 1):
        for j in range(1, a.shape[1] - 1):
            out[i, j] = a[i - 1 : i + 2, j - 1 : j + 2].mean()
    return out


def bilinear(
    lat: np.ndarray, lon: np.ndarray, field: np.ndarray, plat: float, plon: float
) -> float:
    return float(RegularGridInterpolator((lat, lon), field, method="linear")((plat, plon)))


def validate_f4(cell: pd.Series) -> None:
    ref = {v: native("gfdl_esm4", "historical", v, 1995, 2014) for v in ("rsds", "tas", "sfcWind")}
    win = {v: native("gfdl_esm4", "ssp370", v, 2041, 2070) for v in ("rsds", "tas", "sfcWind")}
    lat, lon = ref["rsds"].lat.values, ref["rsds"].lon.values
    # the native grid ascends in lat and lon here; the cell must lie inside the interior ring so the 3x3 neighbourhood exists
    d_rsds = (win["rsds"] / ref["rsds"]).values
    d_t = (win["tas"] - ref["tas"]).values
    d_w = nbhd3(win["sfcWind"].values) / nbhd3(ref["sfcWind"].values)
    plat, plon = float(cell["lat_c"]), float(cell["lon_c"])
    forcing = table("climate_forcing/artifacts/forcing.parquet")
    row = forcing[
        (forcing["cell_id"] == int(cell["cell_id"])) & (forcing["member"] == MEMBER)
    ].iloc[0]
    check(
        f"F4 {MEMBER} cell {int(cell['cell_id'])}: delta_rsds (ratio of window and reference means, bilinear)",
        bilinear(lat, lon, d_rsds, plat, plon),
        float(row["delta_rsds"]),
        5e-7,  # the phase averages float32 fields in float32: single-precision rounding of the inputs
    )
    check(
        "F4 same: dT (difference of means, K; single-precision tolerance 2e-4 K)",
        bilinear(lat, lon, d_t, plat, plon),
        float(row["dT"]),
        2e-4,
        relative=False,
    )
    inner = (slice(1, -1), slice(1, -1))
    wv = bilinear(lat[1:-1], lon[1:-1], d_w[inner], plat, plon)
    check(
        "F4 same: delta_wind (3x3 neighbourhood ratio, bilinear)",
        wv,
        float(row["delta_wind"]),
        1e-7,  # float32 inputs
    )


# ---------------------------------------------------------------------------------------------------------------------------------------
# F5 technical potential
# ---------------------------------------------------------------------------------------------------------------------------------------
def piecewise_power(v: float, vs: np.ndarray, ps: np.ndarray, cut_out: float) -> float:
    if v < vs[0] or v > cut_out:
        return 0.0
    return float(np.interp(v, vs, ps))


def weibull_integral(a_eq: float, k: float, curve: dict) -> float:
    vs, ps = (
        np.array(curve["v_ms"], float),
        np.array(curve["p_kw"], float) / curve["rated_power_kw"],
    )
    pdf = lambda v: (k / a_eq) * (v / a_eq) ** (k - 1) * math.exp(-((v / a_eq) ** k))
    pts = list(vs)
    total = 0.0
    for lo, hi in zip(pts[:-1], pts[1:], strict=True):
        if lo >= curve["cut_out_ms"]:
            break
        val_, _ = integrate.quad(
            lambda v: piecewise_power(v, vs, ps, curve["cut_out_ms"]) * pdf(v),
            lo,
            hi,
            epsabs=0,
            epsrel=1e-12,
        )
        total += val_
    return total


def wind_cf(cell: pd.Series, delta_wind: float, curve: dict) -> float:
    h = val("wind", "hub_height_m")
    z1, z2 = (100.0, 150.0) if h <= 150 else (150.0, 200.0)
    a1, a2 = float(cell[f"weibull_a_{int(z1)}m"]), float(cell[f"weibull_a_{int(z2)}m"])
    k1, k2 = float(cell[f"weibull_k_{int(z1)}m"]), float(cell[f"weibull_k_{int(z2)}m"])
    r1, r2 = float(cell[f"air_density_{int(z1)}m"]), float(cell[f"air_density_{int(z2)}m"])
    alpha = math.log(a2 / a1) / math.log(z2 / z1)
    a_h = a1 * (h / z1) ** alpha
    w = (h - z1) / (z2 - z1)
    k_h, rho_h = k1 + w * (k2 - k1), r1 + w * (r2 - r1)
    a_eq = a_h * (rho_h / RHO0) ** (1 / 3)
    return val("wind", "eta_loss") * weibull_integral(delta_wind * a_eq, k_h, curve)


def validate_f5(cell: pd.Series) -> dict:
    forcing = table("climate_forcing/artifacts/forcing.parquet")
    pot = table(f"technical_potential/artifacts/potential_{TECH}__central.parquet")
    cid = int(cell["cell_id"])
    p_mw = (
        float(cell["eligible_area_km2"]) * val(TECH, "luf") * val(TECH, "power_density_mw_per_km2")
    )
    out = {}
    if TECH == "wind":
        curve = yaml.safe_load(
            (REPO / "tests" / "fixtures" / "power_curves" / "synthetic_curve.yaml").read_text(
                encoding="utf-8"
            )
        )
        for m in ("m0", MEMBER):
            dw = float(
                forcing[(forcing["cell_id"] == cid) & (forcing["member"] == m)]["delta_wind"].iloc[
                    0
                ]
            )
            cf = wind_cf(cell, dw, curve)
            row = pot[(pot["cell_id"] == cid) & (pot["member"] == m)].iloc[0]
            check(
                f"F5 wind cell {cid} {m}: CF (Weibull x power curve, numerical quadrature)",
                cf,
                float(row["CF"]),
                1e-6,
            )
            check(
                f"F5 wind cell {cid} {m}: P_MW = eligible_area x LUF x PD",
                p_mw,
                float(row["P_MW"]),
                1e-9,
            )
            check(
                f"F5 wind cell {cid} {m}: E_MWh = P x CF x 8760",
                p_mw * float(row["CF"]) * HOURS,
                float(row["E_MWh"]),
                1e-9,
            )
            out[m] = (float(row["CF"]), float(row["E_MWh"]), p_mw)
    else:
        for m in ("m0", MEMBER):
            f = forcing[(forcing["cell_id"] == cid) & (forcing["member"] == m)].iloc[0]
            cf = (
                float(cell["pvout_kwh_kwp_day"])
                / 24.0
                * float(f["delta_rsds"])
                * (1 + val("solar", "gamma") * float(f["dT"]))
            )
            row = pot[(pot["cell_id"] == cid) & (pot["member"] == m)].iloc[0]
            check(
                f"F5 solar cell {cid} {m}: CF = PVOUT/24 x delta_rsds x (1 + gamma dT)",
                cf,
                float(row["CF"]),
                1e-9,
            )
            check(
                f"F5 solar cell {cid} {m}: E_MWh = P x CF x 8760",
                p_mw * cf * HOURS,
                float(row["E_MWh"]),
                1e-9,
            )
            out[m] = (float(row["CF"]), float(row["E_MWh"]), p_mw)
    return out


# ---------------------------------------------------------------------------------------------------------------------------------------
# F6 LCOE: textbook form with an explicit loop over the years
# ---------------------------------------------------------------------------------------------------------------------------------------
def lcoe_textbook(
    p_mw: float, e_mwh: float, dist_grid: float, dist_road: float, s: dict, opex_var: float
) -> float:
    capex_total = (
        p_mw * 1000 * s["capex_usd_per_kw"]
        + p_mw * dist_grid * s["grid_cost_usd_per_mw_km"]
        + p_mw * s["substation_cost_usd_per_mw"]
        + dist_road * s["road_cost_usd_per_km"]
    )
    n = int(round(s["lifetime_years"]))
    num = capex_total
    den = 0.0
    for t in range(1, n + 1):
        e_t = e_mwh * (1 - s["degradation_rate"]) ** (t - 1)
        opex_t = s["opex_fixed_frac"] * p_mw * 1000 * s["capex_usd_per_kw"] + opex_var * e_t
        num += opex_t / (1 + s["discount_rate"]) ** t
        den += e_t / (1 + s["discount_rate"]) ** t
    return num / den


def validate_f6(cell: pd.Series, f5: dict) -> None:
    cid = int(cell["cell_id"])
    design = table(f"lcoe_modeling/artifacts/design_matrix_{TECH}.parquet").set_index("sample")
    summ = table(f"lcoe_modeling/artifacts/lcoe_summary_{TECH}.parquet")
    opex_var = val(TECH, "opex_var_usd_per_mwh")
    for m in ("m0", MEMBER):
        cf, e, p = f5[m]
        s0 = design.loc[0].to_dict()
        want = lcoe_textbook(
            p, e, float(cell["dist_grid_km"]), float(cell["dist_road_km"]), s0, opex_var
        )
        row = summ[(summ["cell_id"] == cid) & (summ["member"] == m)].iloc[0]
        check(
            f"F6 {TECH} cell {cid} {m}: nominal LCOE (textbook loop over the years)",
            want,
            float(row["lcoe_nominal"]),
            1e-9,
        )
    # draws s >= 1: the energy scales with the sampled eta_loss (wind) or gamma (solar) exactly as F5 stores it for the nominal value
    cf0, e0, p = f5[MEMBER]
    draws = []
    forcing = table("climate_forcing/artifacts/forcing.parquet")
    f = forcing[(forcing["cell_id"] == cid) & (forcing["member"] == MEMBER)].iloc[0]
    for s_idx in design.index[1:]:
        s = design.loc[s_idx].to_dict()
        if TECH == "wind":
            e_s = e0 * s["eta_loss"] / val("wind", "eta_loss")
        else:
            e_s = (
                e0
                * (1 + s["gamma"] * float(f["dT"]))
                / (1 + val("solar", "gamma") * float(f["dT"]))
            )
        draws.append(
            lcoe_textbook(
                p, e_s, float(cell["dist_grid_km"]), float(cell["dist_road_km"]), s, opex_var
            )
        )
    draws = np.array(draws)
    row = summ[(summ["cell_id"] == cid) & (summ["member"] == MEMBER)].iloc[0]
    check(
        f"F6 cell {cid} {MEMBER}: mean over the {len(draws)} draws",
        float(draws.mean()),
        float(row["lcoe_mean"]),
        1e-9,
    )
    check(
        "F6 same: variance over the draws (ddof=1)",
        float(draws.var(ddof=1)),
        float(row["lcoe_var"]),
        1e-8,
    )
    check(
        "F6 same: p10 (linear interpolation of order statistics)",
        float(np.quantile(draws, 0.1)),
        float(row["lcoe_p10"]),
        1e-9,
    )
    check("F6 same: p90", float(np.quantile(draws, 0.9)), float(row["lcoe_p90"]), 1e-9)


# ---------------------------------------------------------------------------------------------------------------------------------------
# F7 robustness: regrets, MR, rankings, H1 to H5 recomputed from the F5 potential, the F6 design matrix and the F3 candidates
# ---------------------------------------------------------------------------------------------------------------------------------------
class Robust:
    def __init__(self) -> None:
        self.cand = table(
            f"land_eligibility/artifacts/candidates_{TECH}__central.parquet"
        ).set_index("cell_id")
        self.pot = table(f"technical_potential/artifacts/potential_{TECH}__central.parquet")
        self.design = table(f"lcoe_modeling/artifacts/design_matrix_{TECH}.parquet").set_index(
            "sample"
        )
        self.robust = table(
            f"robustness_analysis/artifacts/robustness_{TECH}__core.parquet"
        ).set_index("cell_id")
        members = yaml.safe_load(
            (OUT / "climate_forcing/artifacts/members.yaml").read_text(encoding="utf-8")
        )["members"]
        self.members = {
            m["member"]: (m.get("gcm"), m.get("ssp"), str(m["window"])) for m in members
        }
        in_table = set(self.pot["member"].astype(str))  # a member without the channel of the technology has no row (M-F4-06)
        self.core = [
            m
            for m, (g, s, w) in self.members.items()
            if w == "2041-2070" and g is not None and m in in_table
        ]
        forcing = table("climate_forcing/artifacts/forcing.parquet")
        self.d_t = {
            (int(r.cell_id), str(r.member)): float(r.dT)
            for r in forcing.itertuples()
            if r.member in ("m0", *self.core)
        }
        self.cf_min = val(TECH, "cf_min")
        self.tau = val(TECH, "tau_lcoe_usd_per_mwh")
        self.opex_var = val(TECH, "opex_var_usd_per_mwh")
        self.p_k = val(TECH, "top_k_percent")
        wide_cf = self.pot.pivot(index="cell_id", columns="member", values="CF")
        wide_e = self.pot.pivot(index="cell_id", columns="member", values="E_MWh")
        self.p_mw = self.pot.groupby("cell_id")["P_MW"].first()
        # F7 set: candidates present in every core member and feasible in f0 (CF(m0) >= CF_min)
        present = wide_cf[self.core].notna().all(axis=1)
        self.i0 = [c for c in wide_cf.index if present[c] and wide_cf.loc[c, "m0"] >= self.cf_min]
        self.cf, self.e = wide_cf.loc[self.i0], wide_e.loc[self.i0]
        self.fragile = {
            c for c in self.i0 if any(self.cf.loc[c, m] < self.cf_min for m in self.core)
        }
        self.ranked = [c for c in self.i0 if c not in self.fragile]
        self.n = len(self.i0)
        self.k = max(1, math.ceil(self.p_k / 100 * self.n))

    def lcoe(self, c: int, member: str, s_idx: int) -> float:
        s = self.design.loc[s_idx].to_dict()
        cell = self.cand.loc[c]
        e0 = float(self.e.loc[c, member])
        if TECH == "wind":
            e_s = e0 * s["eta_loss"] / val("wind", "eta_loss")
        else:  # solar: the energy scales with the temperature term (1 + gamma dT) of the member
            d_t = self.d_t.get((c, member), 0.0)
            e_s = e0 * (1 + s["gamma"] * d_t) / (1 + val("solar", "gamma") * d_t)
        return lcoe_textbook(
            float(self.p_mw[c]),
            e_s,
            float(cell["dist_grid_km"]),
            float(cell["dist_road_km"]),
            s,
            self.opex_var,
        )

    def regrets(self, member: str, s_idx: int) -> dict[int, float]:
        """Relative regret of every cell of the F7 set in the future (member, sample): M-F7-02 with q_ref = 0."""
        lc = {
            c: (self.lcoe(c, member, s_idx) if self.cf.loc[c, member] >= self.cf_min else math.inf)
            for c in self.i0
        }
        feasible = {c: v for c, v in lc.items() if math.isfinite(v)}
        best, worst = min(feasible.values()), max(feasible.values())
        out = {}
        for c in self.i0:
            if math.isfinite(lc[c]):
                out[c] = (lc[c] - best) / best
            elif c in self.fragile:
                out[c] = math.inf
            else:
                out[c] = (worst - best) / best
        return out


def rank_order(scores: dict[int, float], tie: dict[int, float] | None = None) -> list[int]:
    """Ascending score, then higher tie value first, then ascending cell id (A-12)."""
    return sorted(scores, key=lambda c: (scores[c], -(tie[c] if tie else 0.0), c))


def validate_f7() -> None:
    R = Robust()
    samples = [s for s in R.design.index if s >= 1]
    reg = {(m, s): R.regrets(m, s) for m in R.core for s in samples}
    reg0 = {m: R.regrets(m, 0) for m in R.core}
    reg_ref0 = R.regrets("m0", 0)
    # M-F7-03: MR_i = max over members of P90 over draws s >= 1
    mr = {
        c: max(float(np.quantile([reg[(m, s)][c] for s in samples], 0.9)) for m in R.core)
        for c in R.ranked
    }
    probe = R.ranked[len(R.ranked) // 2]
    check(
        f"F7 MR of cell {probe} (max over {len(R.core)} members of the P90 over {len(samples)} draws of the relative regret)",
        mr[probe],
        float(R.robust.loc[probe, "mr"]),
        1e-9,
    )
    worst_diff = max(abs(mr[c] - float(R.robust.loc[c, "mr"])) for c in R.ranked)
    check(
        f"F7 MR of all {len(R.ranked)} ranked cells: largest absolute difference",
        0.0,
        worst_diff,
        1e-10,
        relative=False,
    )
    # SR (M-F7-04): share of the core futures feasible with LCOE <= tau; the futures are the members times the draws s >= 1 (D-F7-010)
    futures = [(m, s) for m in R.core for s in samples]
    sr = {
        c: float(
            np.mean([R.cf.loc[c, m] >= R.cf_min and R.lcoe(c, m, s) <= R.tau for m, s in futures])
        )
        for c in R.ranked
    }
    check(
        f"F7 SR of cell {probe} (share of {len(futures)} futures with LCOE <= tau)",
        sr[probe],
        float(R.robust.loc[probe, "sr"]),
        1e-12,
        relative=False,
    )
    # rankings (M-F7-05)
    nominal = {c: R.lcoe(c, "m0", 0) for c in R.i0}
    rnom = {c: i + 1 for i, c in enumerate(rank_order(nominal))}
    robust_order = rank_order(mr, sr)
    top_nom = set(rank_order(nominal)[: R.k])
    top_rob = set(robust_order[: R.k])
    check_text(
        f"F7 nominal top-{R.k} cells",
        str(sorted(top_nom)),
        str(sorted(R.robust.index[R.robust["topk_nominal"].fillna(False).astype(bool)].tolist())),
    )
    check_text(
        f"F7 robust top-{R.k} cells",
        str(sorted(top_rob)),
        str(sorted(R.robust.index[R.robust["topk_robust"].fillna(False).astype(bool)].tolist())),
    )

    # H1: C_k = |intersection over SSPs of top-k by MR_sigma| / k ; V_k from the climate-only ranks
    ssps = sorted({R.members[m][1] for m in R.core})
    tops = {}
    for sg in ssps:
        ms = [m for m in R.core if R.members[m][1] == sg]
        mr_s = {
            c: max(float(np.quantile([reg[(m, s)][c] for s in samples], 0.9)) for m in ms)
            for c in R.ranked
        }
        sr_s = {
            c: float(
                np.mean(
                    [
                        R.cf.loc[c, m] >= R.cf_min and R.lcoe(c, m, s) <= R.tau
                        for m in ms
                        for s in samples
                    ]
                )
            )
            for c in R.ranked
        }
        tops[sg] = set(rank_order(mr_s, sr_s)[: R.k])
    c_k = len(set.intersection(*tops.values())) / R.k
    h1 = table(f"robustness_analysis/artifacts/h1_summary_{TECH}__core.parquet")
    h1 = h1[h1["primary"]].iloc[0]
    check(
        "H1 C_k (|intersection of the three SSP top-k sets| / k)",
        c_k,
        float(h1["c_k"]),
        1e-12,
        relative=False,
    )
    r_clim = {
        sg: {c: max(reg0[m][c] for m in R.core if R.members[m][1] == sg) for c in R.ranked}
        for sg in ssps
    }
    rank_clim = {sg: {c: i + 1 for i, c in enumerate(rank_order(r_clim[sg]))} for sg in ssps}
    nom_top_ranked = [c for c in rank_order(nominal) if True][: R.k]
    vulnerable = [
        c
        for c in nom_top_ranked
        if c in R.fragile or any(rank_clim[sg].get(c, math.inf) > R.k + R.k for sg in ssps)
    ]
    check(
        "H1 V_k (share of the nominal top-k outside the top k+m of the climate-only ranking in some SSP)",
        len(vulnerable) / R.k,
        float(h1["v_k"]),
        1e-12,
        relative=False,
    )
    check("H1 reference p_k^2", (R.k / R.n) ** 2, float(h1["reference"]), 1e-12, relative=False)

    # H2: Capacity Overlap Index
    q = {c: float(R.p_mw[c]) for c in R.ranked}
    admin = {c: str(R.robust.loc[c, "admin1_id"]) for c in R.ranked}
    cell_sel = {c: 1.0 if c in top_rob else 0.0 for c in R.ranked}
    target = sum(q[c] for c in top_rob)
    regions = sorted(set(admin.values()))
    zbar = {
        r: sum(q[c] * mr[c] for c in R.ranked if admin[c] == r)
        / sum(q[c] for c in R.ranked if admin[c] == r)
        for r in regions
    }
    qreg = {r: sum(q[c] for c in R.ranked if admin[c] == r) for r in regions}
    taken, frac = 0.0, {r: 0.0 for r in regions}
    for r in sorted(regions, key=lambda r: (zbar[r], r)):
        if taken >= target - 1e-12:
            break
        take = min(1.0, (target - taken) / qreg[r])
        frac[r] = take
        taken += take * qreg[r]
    overlap = sum(q[c] * min(cell_sel[c], frac[admin[c]]) for c in R.ranked) / target
    h2 = table(f"robustness_analysis/artifacts/h2_summary_{TECH}__core.parquet")
    h2 = h2[h2["primary"]].iloc[0]
    check(
        "H2 O (share of T selected by both procedures)",
        overlap,
        float(h2["overlap"]),
        1e-12,
        relative=False,
    )
    check(
        "H2 O_ref = T / Q_max",
        target / sum(q.values()),
        float(h2["overlap_ref"]),
        1e-12,
        relative=False,
    )

    # H3 and H4
    def displacement(shortlist: list[int]) -> float:
        out = sum(q[c] for c in shortlist if rnom_ranked[c] > R.k + R.k)
        return out / sum(q[c] for c in shortlist)

    nominal_ranked = {c: nominal[c] for c in R.ranked}
    rnom_ranked = {c: i + 1 for i, c in enumerate(rank_order(nominal_ranked))}
    h3 = table(f"robustness_analysis/artifacts/h3_summary_{TECH}__core.parquet")
    h3 = h3[h3["primary"]].iloc[0]
    check(
        "H3 D (capacity share of the robust top-k whose nominal rank exceeds k+m)",
        displacement(robust_order[: R.k]),
        float(h3["d"]),
        1e-12,
        relative=False,
    )
    z_clim = {c: max(reg0[m][c] for m in R.core) for c in R.ranked}
    z_tec = {
        c: float(
            np.quantile(
                [reg[("m0", s)][c] if ("m0", s) in reg else R.regrets("m0", s)[c] for s in samples],
                0.9,
            )
        )
        for c in R.ranked
    }
    d_clim = displacement(rank_order(z_clim)[: R.k])
    d_tec = displacement(rank_order(z_tec)[: R.k])
    h4 = table(f"robustness_analysis/artifacts/h4_country_{TECH}__core.parquet")
    h4 = h4[h4["primary"]].iloc[0]
    check("H4 D_clim", d_clim, float(h4["d_clim"]), 1e-12, relative=False)
    check("H4 D_tec", d_tec, float(h4["d_tec"]), 1e-12, relative=False)
    if d_clim + d_tec > 0:
        check(
            "H4 rho = D_clim / (D_clim + D_tec)",
            d_clim / (d_clim + d_tec),
            float(h4["rho"]),
            1e-12,
            relative=False,
        )
    else:
        check_text("H4 profile when D_sum = 0", "no_displacement", str(h4["profile"]))

    # H5: R_loss from the energy of the fixed economic domain
    omega = [c for c in R.i0 if nominal[c] <= R.tau]
    e_m = {m: sum(float(R.e.loc[c, m]) for c in omega) / 1e6 for m in ["m0", *R.core]}
    e0 = e_m["m0"]
    delta_e = max(0.0, e0 - min(e_m[m] for m in R.core))
    h5 = table(f"robustness_analysis/artifacts/h5_summary_{TECH}__core.parquet")
    h5 = h5[h5["primary"]].iloc[0]
    target_cfg = EXPERIMENTS["national_targets"]["ZZZ"][TECH]
    check("H5 E_0 (TWh/year of the fixed domain at m0)", e0, float(h5["e0_twh"]), 1e-9)
    if target_cfg["unit"] == "GW":
        g_cap = float(target_cfg["value"])
        cum, num, den = 0.0, 0.0, 0.0
        for c in sorted(omega, key=lambda c: (nominal[c], c)):
            cap_gw = float(R.p_mw[c]) / 1000.0
            take = min(cap_gw, g_cap - cum)
            if take <= 0:
                break
            cf_ref = float(R.cf.loc[c, "m0"])
            num += take * cf_ref
            den += take
            cum += take
        g = 8.76 * g_cap * (num / den)
    else:
        g = float(target_cfg["value"])
    check(
        "H5 G (TWh/year; 8.76 x G_cap x capacity-weighted reference CF of the cheapest cells)",
        g,
        float(h5["g_twh"]),
        1e-9,
    )
    h0 = e0 - g
    check(
        "H5 Delta E = max(0, E_0 - min over the core members E_m)",
        delta_e,
        float(h5["delta_e_twh"]),
        1e-9,
        relative=delta_e > 0,
    )
    check(
        "H5 R_loss = Delta E / H_0", delta_e / h0, float(h5["r_loss"]), 1e-9, relative=delta_e > 0
    )

    # PRIM: density and coverage of the stored box recomputed on the stored futures table
    futures_t = table(f"robustness_analysis/artifacts/futures_{TECH}__core.parquet")
    futures_t = futures_t[futures_t["sample"] >= 1].reset_index(drop=True)
    box = table(f"robustness_analysis/artifacts/prim_box_{TECH}__core.parquet")
    box = box[box["primary"]].iloc[0]
    theta = float(box["outcome_threshold"])
    cases = futures_t["displaced_capacity_share"] >= theta - 1e-12
    inside = pd.Series(True, index=futures_t.index)
    for name in str(box["restricted"]).split("|"):
        if f"{name}__in" in box.index and isinstance(box[f"{name}__in"], str):
            inside &= futures_t[name].isin(str(box[f"{name}__in"]).split("|"))
        elif f"{name}__min" in box.index:
            inside &= (futures_t[name] >= box[f"{name}__min"] - 1e-12) & (
                futures_t[name] <= box[f"{name}__max"] + 1e-12
            )
        elif name == "gcm" and "gcm__in" in box.index:
            inside &= futures_t["gcm"].isin(str(box["gcm__in"]).split("|"))
    density = float((cases & inside).sum() / max(inside.sum(), 1))
    coverage = float((cases & inside).sum() / max(cases.sum(), 1))
    check(
        "PRIM density of the stored box, recomputed on the stored futures",
        density,
        float(box["density"]),
        1e-12,
        relative=False,
    )
    check(
        "PRIM coverage of the stored box, recomputed on the stored futures",
        coverage,
        float(box["coverage"]),
        1e-12,
        relative=False,
    )
    check(
        "PRIM coverage of the stored box is at least the pre-registered 0.50",
        1.0,
        float(coverage >= 0.5),
        0.0,
        relative=False,
    )
    # the outcome V_f by hand: the share of the capacity of the nominal shortlist whose rank by relative regret exceeds k + m in the future
    short = [c for c in rank_order(nominal_ranked)][: R.k]
    vf = {}
    for m in R.core:
        for s in samples:
            r = {c: reg[(m, s)][c] for c in R.ranked}
            rank_f = {c: i + 1 for i, c in enumerate(rank_order(r))}
            vf[(m, s)] = sum(q[c] for c in short if rank_f[c] > R.k + R.k) / sum(q[c] for c in short)
    stored = futures_t["displaced_capacity_share"]
    if WORLD == "zzz":
        check(
            f"PRIM outcome V_f by hand: the largest value over the {len(vf)} futures (ZZZ keeps the order of its cells)",
            0.0,
            max(vf.values()),
            1e-12,
            relative=False,
        )
        check_text(
            "PRIM stored outcome in this run (test rule on the GCM, tests/synthetic only)",
            "[0.05, 0.5]",
            str([float(x) for x in sorted(set(np.round(stored, 4)))]),
        )
    else:  # ZZZ2: the stored outcome is the real one and must equal the hand value in every future
        by_hand = np.array([vf[(m, int(s_))] for m, s_ in zip(futures_t["member"], futures_t["sample"], strict=True)])
        check(
            f"PRIM outcome V_f of all {len(by_hand)} futures: largest absolute difference between the stored and the hand value",
            0.0,
            float(np.max(np.abs(by_hand - stored.to_numpy()))),
            1e-12,
            relative=False,
        )
        check(
            "PRIM outcome V_f is non-trivial: the share of futures at or above the threshold is strictly between 0 and 1",
            1.0,
            float(0.0 < float((by_hand >= theta - 1e-12).mean()) < 1.0),
            0.0,
            relative=False,
        )
        EXPECT["v_f_cases"] = int((by_hand >= theta - 1e-12).sum())
        EXPECT["v_f_futures"] = len(by_hand)


def main() -> int:
    cell = validate_f3()
    validate_f4(cell)
    f5 = validate_f5(cell)
    validate_f6(cell, f5)
    validate_f7()
    print(f"# Hand validation of ZZZ ({TECH}), data dir {DATA}\n")
    print("| Check | Expected (by hand) | Obtained (artifact) | Difference | Tolerance | Result |")
    print("|---|---|---|---|---|---|")
    for label, exp, got, diff, tol, ok in ROWS:
        got_s = got if isinstance(got, str) else f"{got:.10g}"
        print(f"| {label} | {exp} | {got_s} | {diff:.3g} | {tol:g} | {'PASS' if ok else 'FAIL'} |")
    failed = [r for r in ROWS if not r[5]]
    print(f"\n{len(ROWS) - len(failed)} of {len(ROWS)} checks pass.")
    print("EXPECTED " + json.dumps(EXPECT, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
