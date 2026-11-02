"""Distribution of the distance to the road D_road of the eligible area, per country and technology (COMMAND 86).

Reads the central candidates tables of F3 already on disk (`dist_road_km`, the eligible-area mean of each 0.05 degree cell) and weights each
cell by its eligible area: median, P90 and the share of the eligible area beyond 30 km. The road layer of those tables is the one made before
Group 3 (every road class of the source); the next F2a round rebuilds it with `geospatial.road_classes`, so rerun this script after that round.

Usage: python scripts/report_road_distance.py [BRA IND PRT]
Output: stdout and docs/_audit/road_distance_86.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
BEYOND_KM = 30.0


def _data_dir() -> Path:
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("GEOFREA_DATA_DIR="):
            return Path(line.split("=", 1)[1].strip().strip('"'))
    raise SystemExit("GEOFREA_DATA_DIR is not set in .env")


def weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    """Quantile `q` (0 to 1) of `values` with `weights`: the smallest value whose cumulative weight reaches `q` of the total."""
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order])
    return float(values[order][np.searchsorted(cumulative, q * cumulative[-1])])


def summarize(frame: pd.DataFrame) -> dict[str, float]:
    valid = frame[frame["dist_road_km"].notna() & (frame["eligible_area_km2"] > 0)]
    values = valid["dist_road_km"].to_numpy(dtype="float64")
    weights = valid["eligible_area_km2"].to_numpy(dtype="float64")
    return {
        "cells": int(len(valid)),
        "eligible_area_km2": float(weights.sum()),
        "median_km": weighted_quantile(values, weights, 0.5),
        "p90_km": weighted_quantile(values, weights, 0.9),
        "share_beyond_30km": float(weights[values > BEYOND_KM].sum() / weights.sum()),
    }


def main(isos: list[str]) -> None:
    out = _data_dir() / "outputs"
    lines = [
        "# Distance to the road D_road of the eligible area (COMMAND 86)",
        "",
        "Central scenario, `dist_road_km` of the F3 candidates (eligible-area mean per 0.05 degree cell), each cell weighted by its eligible area. The road layer is the one",
        "made before Group 3 (all road classes of the source); the next F2a round rebuilds it with the primary and secondary classes, so the figures are to be recomputed",
        "(`python scripts/report_road_distance.py`) after that round. They size the road term that `road_cost_excluded` leaves out.",
        "",
        "| Country | Technology | Cells | Eligible area (km2) | Median (km) | P90 (km) | Eligible area beyond 30 km |",
        "|---|---|---|---|---|---|---|",
    ]
    for iso in isos:
        for tech in ("solar", "wind"):
            path = (
                out / iso / "land_eligibility" / "artifacts" / f"candidates_{tech}__central.parquet"
            )
            if not path.is_file():
                lines.append(f"| {iso} | {tech} | not available | | | | |")
                continue
            s = summarize(pd.read_parquet(path, columns=["dist_road_km", "eligible_area_km2"]))
            print(iso, tech, s, flush=True)
            lines.append(
                f"| {iso} | {tech} | {s['cells']} | {s['eligible_area_km2']:.0f} | {s['median_km']:.1f} | {s['p90_km']:.1f} | {s['share_beyond_30km']:.1%} |"
            )
    (REPO / "docs" / "_audit" / "road_distance_86.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main(sys.argv[1:] or ["BRA", "IND", "PRT"])
