"""QC: how far are existing power plants from the OSM grid layer? (L-018, OQ-041 evidence)

Existing plants (GEM Global Integrated Power Tracker, operating units, all fuels; the pinned snapshot of F5-1) are connected to the grid in reality. If many sit far from the mapped OSM grid, the OSM
layer has holes there, and a large `dist_grid_km` is a mapping gap rather than a real absence of grid. Samples the
aligned F2a grid-distance raster at each plant inside the country mainland and prints distribution tables.

    python scripts/qc_plants_vs_grid.py [--min-mw 1] > report
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio

from geofrea.core.config_loader import load_countries
from geofrea.data_acquisition.fetchers import gem_trackers

COUNTRIES = ("PRT", "IND", "BRA")
THRESHOLDS_KM = (5, 10, 25, 50, 100)


def plants_for(xlsx: Path, iso: str, gem_name: str, boundary: Path) -> pd.DataFrame:
    """Operating GEM units of every fuel inside the mainland polygon; columns match what main() expects."""
    df = pd.read_excel(xlsx, sheet_name=gem_trackers.SHEET)
    df = df[(df["Country/area"] == gem_name) & (df["Status"] == "operating")]
    df = df.rename(
        columns={"Type": "tech", "Status": "status", "Latitude": "lat", "Longitude": "lon"}
    )
    df["capacity_mw"] = pd.to_numeric(df["Capacity (MW)"], errors="coerce")
    df = df.dropna(subset=["lat", "lon", "capacity_mw"])
    clipped = gem_trackers.clip_country(
        df[["Country/area", "tech", "status", "lat", "lon", "capacity_mw"]],
        iso,
        gem_name,
        gpd.read_file(boundary),
    )
    return clipped.rename(columns={"tech": "primary_fuel", "lat": "latitude", "lon": "longitude"})


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
    xlsx = data / "raw" / "gem" / "_global" / gem_trackers.load_pin()["file"]
    countries = load_countries(Path(__file__).resolve().parents[1] / "config" / "countries.yaml")
    print(
        f"Plants with capacity >= {args.min_mw} MW inside the mainland, distance to the OSM grid (km, aligned F2a raster)\n"
    )
    for iso in COUNTRIES:
        raster = data / "outputs" / iso / "grid_alignment" / "artifacts" / f"{iso}_grid_aligned.tif"
        boundary = data / "raw" / "gadm" / iso / f"gadm41_{iso}_0_mainland.shp"
        df = plants_for(xlsx, iso, countries[iso]["gem_country_name"], boundary)
        df = df[df["capacity_mw"] >= args.min_mw]
        df["dist_km"] = sample(raster, df["latitude"].to_numpy(), df["longitude"].to_numpy())
        inside = df.dropna(subset=["dist_km"])
        print(
            f"## {iso}: {len(df)} plants, {len(inside)} inside the mainland grid, {inside['capacity_mw'].sum():.0f} MW"
        )
        rows = []
        for label, sub in [("all", inside)] + [
            (f, g) for f, g in inside.groupby("primary_fuel") if len(g) >= 10
        ]:
            w = sub["capacity_mw"].to_numpy()
            d = sub["dist_km"].to_numpy()
            row = {
                "group": label,
                "n": len(sub),
                "median_km": float(np.median(d)),
                "p90_km": float(np.percentile(d, 90)),
                "max_km": float(d.max()),
            }
            for t in THRESHOLDS_KM:
                row[f">{t}km_%n"] = 100 * float((d > t).mean())
            row[">50km_%MW"] = 100 * float(w[d > 50].sum() / w.sum())
            rows.append(row)
        print(_markdown(pd.DataFrame(rows).round(1)))
        far = inside.sort_values("dist_km", ascending=False).head(5)[
            ["primary_fuel", "capacity_mw", "dist_km"]
        ]
        print(
            "\nfarthest 5:",
            "; ".join(
                f"{r.primary_fuel} {r.capacity_mw:.0f} MW at {r.dist_km:.0f} km"
                for r in far.itertuples()
            ),
            "\n",
        )


if __name__ == "__main__":
    main()
