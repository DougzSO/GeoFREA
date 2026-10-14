# ruff: noqa
"""Plausibility of the real F1-F4 outputs of BRA, PRT and IND (audit 2026-10, item 8). Read-only; prints Markdown tables.

Usage: python plausibility_real_data.py [GEOFREA_DATA_DIR]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import yaml

DATA = Path(sys.argv[1] if len(sys.argv) > 1 else r"D:\Douglas\DOUTORADO\GeoFREA_data")
REPO = Path(__file__).resolve().parents[3]
COUNTRIES = ("BRA", "PRT", "IND")


def q(x: np.ndarray, ps=(0, 1, 50, 99, 100)) -> list[float]:
    x = x[np.isfinite(x)]
    return [float(v) for v in np.percentile(x, ps)] if x.size else [float("nan")] * len(ps)


def fmt(v: list[float]) -> str:
    return " / ".join(f"{a:.4g}" for a in v)


def forcing() -> None:
    print(
        "\n## Forcing (F4): change factors by SSP and window, min / p1 / median / p99 / max over cells and members\n"
    )
    print("| Country | SSP | Window | n members | delta_rsds | dT (K) | delta_wind | share NaN |")
    print("|---|---|---|---|---|---|---|---|")
    for c in COUNTRIES:
        base = DATA / "outputs" / c / "climate_forcing" / "artifacts"
        members = yaml.safe_load((base / "members.yaml").read_text(encoding="utf-8"))["members"]
        info = {m["member"]: (str(m.get("ssp")), str(m.get("window"))) for m in members}
        f = pd.read_parquet(base / "forcing.parquet")
        f["ssp"] = f["member"].map(lambda m: info[m][0])
        f["win"] = f["member"].map(lambda m: info[m][1])
        for (ssp, win), part in f.groupby(["ssp", "win"]):
            if ssp == "None":
                continue
            print(
                f"| {c} | {ssp} | {win} | {part['member'].nunique()} | {fmt(q(part['delta_rsds'].to_numpy()))} | "
                f"{fmt(q(part['dT'].to_numpy()))} | {fmt(q(part['delta_wind'].to_numpy()))} | "
                f"{part[['delta_rsds', 'dT', 'delta_wind']].isna().mean().max():.3g} |"
            )
        ref = f[f["member"] == "m0"]
        print(
            f"| {c} | reference m0 | - | 1 | {fmt(q(ref['delta_rsds'].to_numpy()))} | {fmt(q(ref['dT'].to_numpy()))} | {fmt(q(ref['delta_wind'].to_numpy()))} | - |"
        )
        masked = pd.read_parquet(base / "forcing_masked.parquet")
        n_cells = f["cell_id"].nunique()
        print(
            f"| {c} | masked wind (M-F4-07) | - | - | {len(masked)} rows = {len(masked) / len(f):.3%} of rows, {masked['cell_id'].nunique()} of {n_cells} cells | | | |"
        )


def hazard() -> None:
    print(
        "\n## Hazard context (F4, window 2041-2070): min / p1 / median / p99 / max over cells and hazard members\n"
    )
    print("| Country | Indicator | Values | share NaN |")
    print("|---|---|---|---|")
    for c in COUNTRIES:
        h = pd.read_parquet(
            DATA / "outputs" / c / "climate_forcing" / "artifacts" / "hazard_context.parquet"
        )
        for col in h.columns:
            if col in ("cell_id", "member"):
                continue
            print(
                f"| {c} | {col} | {fmt(q(h[col].to_numpy(dtype='float64')))} | {h[col].isna().mean():.3g} |"
            )
        print(f"| {c} | members | {sorted(h['member'].unique())} | |")


def cells() -> None:
    print("\n## Candidate cells (F3, central scenario): resource and cost layers\n")
    print(
        "| Country | Tech | Cells | Candidates | Eligible area (km2) | Cell columns | min / p1 / median / p99 / max |"
    )
    print("|---|---|---|---|---|---|---|")
    for c in COUNTRIES:
        for tech, cols in (
            ("solar", ["dist_grid_km", "dist_road_km"]),
            (
                "wind",
                [
                    "dist_grid_km",
                    "dist_road_km",
                    "weibull_a_100m",
                    "weibull_k_100m",
                    "air_density_100m",
                    "weibull_a_150m",
                    "weibull_k_150m",
                    "air_density_150m",
                    "weibull_a_200m",
                    "weibull_k_200m",
                    "air_density_200m",
                ],
            ),
        ):
            t = pd.read_parquet(
                DATA
                / "outputs"
                / c
                / "land_eligibility"
                / "artifacts"
                / f"cells_{tech}__central.parquet"
            )
            cand = t[t["candidate"]]
            for col in [x for x in cols if x in t.columns]:
                print(
                    f"| {c} | {tech} | {len(t)} | {len(cand)} | {cand['eligible_area_km2'].sum():.4g} | {col} | {fmt(q(cand[col].to_numpy(dtype='float64')))} |"
                )
            print(
                f"| {c} | {tech} | {len(t)} | {len(cand)} | {cand['eligible_area_km2'].sum():.4g} | eligible_area_km2 per candidate | {fmt(q(cand['eligible_area_km2'].to_numpy(dtype='float64')))} |"
            )
            print(
                f"| {c} | {tech} | | | | cell_area_km2 | {fmt(q(t['cell_area_km2'].to_numpy(dtype='float64')))} |"
            )


def siting() -> None:
    print("\n## Siting layers (F2b): raster statistics\n")
    print("| Country | Layer | Shape | min / p1 / median / p99 / max | share valid |")
    print("|---|---|---|---|---|")
    for c in COUNTRIES:
        for tif in sorted((DATA / "outputs" / c / "siting_layers" / "artifacts").glob("*.tif")):
            with rasterio.open(tif) as src:
                a = src.read(1, masked=True).astype("float64")
                step = max(1, a.shape[0] // 1500)
                s = np.ma.filled(a[::step, ::step], np.nan)
                print(
                    f"| {c} | {tif.stem} | {a.shape} | {fmt(q(s.ravel()))} | {float((~np.ma.getmaskarray(a)).mean()):.3g} |"
                )


if __name__ == "__main__":
    print(f"# Plausibility of the real F1-F4 outputs (data dir {DATA})")
    forcing()
    hazard()
    siting()
    cells()
