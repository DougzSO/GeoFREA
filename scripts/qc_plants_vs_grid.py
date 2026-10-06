"""QC: how far are existing power plants from the OSM grid layer? (L-018, OQ-041 evidence)

Existing plants (WRI GPPD) are connected to the grid in reality. If many sit far from the mapped OSM grid, the OSM
layer has holes there, and a large `dist_grid_km` is a mapping gap rather than a real absence of grid. Samples the
aligned F2a grid-distance raster at each plant inside the country mainland and prints distribution tables.

    python scripts/qc_plants_vs_grid.py [--min-mw 1] > report
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

COUNTRIES = ("PRT", "IND", "BRA")
THRESHOLDS_KM = (5, 10, 25, 50, 100)


def plants_for(csv: Path, iso: str) -> pd.DataFrame:
    df = pd.read_csv(csv, usecols=["country", "capacity_mw", "primary_fuel", "latitude", "longitude"], low_memory=False)
    return df[df["country"] == iso].dropna(subset=["latitude", "longitude"]).copy()


def sample(raster: Path, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    with rasterio.open(raster) as src:
        vals = np.full(len(lat), np.nan)
        rows, cols = rasterio.transform.rowcol(src.transform, lon, lat)
        rows, cols = np.asarray(rows), np.asarray(cols)
        ok = (rows >= 0) & (rows < src.height) & (cols >= 0) & (cols < src.width)
        band = src.read(1)
        v = band[rows[ok], cols[ok]].astype(float)
        v[(src.nodata is not None) & (v == src.nodata)] = np.nan
        vals[ok] = v
    return vals


def _markdown(df: pd.DataFrame) -> str:
    head = "| " + " | ".join(df.columns) + " |"
    rule = "|" + "|".join("---" for _ in df.columns) + "|"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([head, rule, *body])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-mw", type=float, default=1.0)
    args = ap.parse_args()
    data = Path(os.environ["GEOFREA_DATA_DIR"])
    csv = data / "raw" / "wri_gppd" / "_global" / "global_power_plant_database.csv"
    print(f"Plants with capacity >= {args.min_mw} MW inside the mainland, distance to the OSM grid (km, aligned F2a raster)\n")
    for iso in COUNTRIES:
        raster = data / "outputs" / iso / "grid_alignment" / "artifacts" / f"{iso}_grid_aligned.tif"
        df = plants_for(csv, iso)
        df = df[df["capacity_mw"] >= args.min_mw]
        df["dist_km"] = sample(raster, df["latitude"].to_numpy(), df["longitude"].to_numpy())
        inside = df.dropna(subset=["dist_km"])
        print(f"## {iso}: {len(df)} plants, {len(inside)} inside the mainland grid, {inside['capacity_mw'].sum():.0f} MW")
        rows = []
        for label, sub in [("all", inside)] + [(f, g) for f, g in inside.groupby("primary_fuel") if len(g) >= 10]:
            w = sub["capacity_mw"].to_numpy()
            d = sub["dist_km"].to_numpy()
            row = {"group": label, "n": len(sub), "median_km": float(np.median(d)), "p90_km": float(np.percentile(d, 90)), "max_km": float(d.max())}
            for t in THRESHOLDS_KM:
                row[f">{t}km_%n"] = 100 * float((d > t).mean())
            row[">50km_%MW"] = 100 * float(w[d > 50].sum() / w.sum())
            rows.append(row)
        print(_markdown(pd.DataFrame(rows).round(1)))
        far = inside.sort_values("dist_km", ascending=False).head(5)[["primary_fuel", "capacity_mw", "dist_km"]]
        print("\nfarthest 5:", "; ".join(f"{r.primary_fuel} {r.capacity_mw:.0f} MW at {r.dist_km:.0f} km" for r in far.itertuples()), "\n")


if __name__ == "__main__":
    main()
