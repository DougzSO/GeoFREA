"""Distribution of the distance to the road D_road of the eligible area, per country and technology (COMMAND 86).

Reads the central candidates tables of F3 already on disk (`dist_road_km`, the eligible-area mean of each 0.05 degree cell) and weights each
cell by its eligible area: median, P90 and the share of the eligible area beyond 30 km. The road layer of those tables is the one made before
Group 3 (every road class of the source); the next F2a round rebuilds it with `geospatial.road_classes`, so rerun this script after that round.

The same cells weight the technical potential of F5 (`potential_<tech>__central.parquet`: P_MW and E_MWh of each cell and member, averaged over the
members of the cell): the share of the capacity (MW) and of the energy (GWh) that lies in cells beyond 30 km of a road (COMMAND 91, item d). The potential
tables are those on disk; a cell of the candidates table with no row in them is counted, never dropped silently.

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
        "cells": len(valid),
        "eligible_area_km2": float(weights.sum()),
        "median_km": weighted_quantile(values, weights, 0.5),
        "p90_km": weighted_quantile(values, weights, 0.9),
        "share_beyond_30km": float(weights[values > BEYOND_KM].sum() / weights.sum()),
    }


def potential_beyond(candidates: pd.DataFrame, potential: pd.DataFrame) -> dict[str, float]:
    """Capacity (MW) and energy (GWh) of the potential, and their shares in the cells beyond 30 km of a road.

    The potential of a cell is the mean over its members of `P_MW` and `E_MWh` (the capacity of a cell does not depend on the member).
    """
    per_cell = potential.groupby("cell_id", sort=False).agg(P_MW=("P_MW", "mean"), E_MWh=("E_MWh", "mean"))
    cells = candidates[["cell_id", "dist_road_km"]].drop_duplicates("cell_id").merge(per_cell, left_on="cell_id", right_index=True, how="left")
    missing = int(cells["P_MW"].isna().sum())
    known = cells[cells["P_MW"].notna() & cells["dist_road_km"].notna()]
    far = known["dist_road_km"] > BEYOND_KM
    p_total, e_total = float(known["P_MW"].sum()), float(known["E_MWh"].sum()) / 1000.0
    return {
        "capacity_gw": p_total / 1000.0,
        "energy_twh": e_total / 1000.0,
        "share_mw_beyond_30km": float(known.loc[far, "P_MW"].sum() / p_total) if p_total else float("nan"),
        "share_gwh_beyond_30km": float(known.loc[far, "E_MWh"].sum() / 1000.0 / e_total) if e_total else float("nan"),
        "cells_without_potential": missing,
        "cells_without_distance": int(cells["dist_road_km"].isna().sum()),
    }


def main(isos: list[str]) -> None:
    out = _data_dir() / "outputs"
    lines = [
        "# Distance to the road D_road of the eligible area (COMMAND 86)",
        "",
        "Central scenario, `dist_road_km` of the F3 candidates (eligible-area mean per 0.05 degree cell), each cell weighted by its eligible area. The road layer is the one",
        "of the round of 2026-11-03 (F2a with `geospatial.road_classes`, F3 rerun in all three countries); the figures before it, made with every road class of the source,",
        "were BRA 2.4 km median and 0.6% beyond 30 km. They size the road term that `road_cost_excluded` leaves out.",
        "",
        "| Country | Technology | Cells | Eligible area (km2) | Median (km) | P90 (km) | Eligible area beyond 30 km |",
        "|---|---|---|---|---|---|---|",
    ]
    potential_lines = [
        "",
        "## Technical potential beyond 30 km of a road",
        "",
        "Central scenario of F5, mean over the members of each cell (the capacity does not depend on the member). The share is that of the potential of the cells whose `dist_road_km` is above 30 km.",
        "",
        "| Country | Technology | Capacity (GW) | Energy (TWh/yr) | Capacity beyond 30 km | Energy beyond 30 km | Candidate cells without potential |",
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
            pot = out / iso / "technical_potential" / "artifacts" / f"potential_{tech}__central.parquet"
            if pot.is_file():
                q = potential_beyond(
                    pd.read_parquet(path, columns=["cell_id", "dist_road_km"]),
                    pd.read_parquet(pot, columns=["cell_id", "P_MW", "E_MWh"]),
                )
                print(iso, tech, q, flush=True)
                potential_lines.append(
                    f"| {iso} | {tech} | {q['capacity_gw']:.1f} | {q['energy_twh']:.1f} | {q['share_mw_beyond_30km']:.1%} | {q['share_gwh_beyond_30km']:.1%} | {q['cells_without_potential']} |"
                )
            else:
                potential_lines.append(f"| {iso} | {tech} | not available | | | | |")
            lines.append(
                f"| {iso} | {tech} | {s['cells']} | {s['eligible_area_km2']:.0f} | {s['median_km']:.1f} | {s['p90_km']:.1f} | {s['share_beyond_30km']:.1%} |"
            )
    (REPO / "docs" / "_audit" / "road_distance_86.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main(sys.argv[1:] or ["BRA", "IND", "PRT"])
