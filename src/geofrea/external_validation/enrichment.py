"""Enrichment of existing capacity in the cheapest part of the candidate area (M-F7b-02, D-F7b-003).

Candidate cells are ordered by their nominal LCOE at `m0` and cut into ten deciles of eligible area (the area is the weight, so each decile
holds a tenth of the eligible area by construction, up to the cells that straddle a cut). The enrichment ratio of the lowest `d` deciles is
the share of the existing capacity in them divided by the share of the eligible area in them.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

N_DECILES = 10


def weighted_deciles(lcoe: np.ndarray, area: np.ndarray, cell_id: np.ndarray) -> np.ndarray:
    """Decile 1 to 10 of each cell: cells ordered by `lcoe` (ties by `cell_id`), the cell placed by the midpoint of its area.

    Raises:
        ValueError: the area is not positive or a value is not finite.
    """
    lcoe, area = np.asarray(lcoe, dtype="float64"), np.asarray(area, dtype="float64")
    if lcoe.size == 0:
        return np.empty(0, dtype="int64")
    if not (np.isfinite(lcoe).all() and np.isfinite(area).all() and (area > 0).all()):
        raise ValueError("deciles need finite LCOE and positive eligible area")
    order = np.lexsort((np.asarray(cell_id), lcoe))
    cumulative = np.cumsum(area[order])
    midpoint = (cumulative - area[order] / 2.0) / cumulative[-1]
    decile = np.empty(lcoe.size, dtype="int64")
    decile[order] = np.minimum((midpoint * N_DECILES).astype("int64"), N_DECILES - 1) + 1
    return decile


def enrichment_rows(
    technology: str,
    row_set: str,
    candidates: pd.DataFrame,
    units: pd.DataFrame,
    lowest_deciles: list[int],
) -> list[dict]:
    """The decile rows and the cumulative lowest-decile rows of one set of units.

    Implements: M-F7b-02.

    Args:
        candidates: `cell_id`, `eligible_area_km2`, `decile` (candidate cells with a finite LCOE at `m0`).
        units: `capacity_mw`, `cell_id` (null outside the grid) and `in_grid`.
        lowest_deciles: The `d` of the cumulative rows.
    """
    decile_of = candidates.set_index("cell_id")["decile"]
    in_grid = units["in_grid"].to_numpy(dtype=bool)
    capacity = units["capacity_mw"].to_numpy(dtype="float64")
    cells = units["cell_id"].to_numpy()
    unit_decile = np.zeros(len(units), dtype="int64")  # 0: not in a ranked candidate cell
    located = in_grid & pd.notna(units["cell_id"]).to_numpy()
    unit_decile[located] = (
        pd.Series(cells[located].astype("int64"))
        .map(decile_of)
        .fillna(0)
        .astype("int64")
        .to_numpy()
    )
    in_candidates = unit_decile > 0
    candidate_capacity = float(capacity[in_candidates].sum())
    grid_capacity = float(capacity[in_grid].sum())
    non_candidate = float(capacity[in_grid & ~in_candidates].sum())
    share_non_candidate = non_candidate / grid_capacity if grid_capacity > 0 else None
    area = candidates["eligible_area_km2"].to_numpy(dtype="float64")
    total_area = float(area.sum())
    deciles = candidates["decile"].to_numpy()
    n_cells = len(candidates)
    n_units = int(in_candidates.sum())

    def row(kind: str, d: int, keep_cells: np.ndarray, keep_units: np.ndarray) -> dict:
        area_share = float(area[keep_cells].sum() / total_area) if total_area > 0 else 0.0
        capacity_share = (
            float(capacity[keep_units].sum() / candidate_capacity)
            if candidate_capacity > 0
            else None
        )
        ratio = (
            capacity_share / area_share if capacity_share is not None and area_share > 0 else None
        )
        return {
            "technology": technology,
            "row_set": row_set,
            "kind": kind,
            "decile": d,
            "n_candidate_cells": n_cells,
            "n_units_in_candidates": n_units,
            "eligible_area_share": area_share,
            "capacity_share": capacity_share,
            "enrichment_ratio": ratio,
            "capacity_share_non_candidate": share_non_candidate,
        }

    rows = [row("decile", d, deciles == d, unit_decile == d) for d in range(1, N_DECILES + 1)]
    rows += [
        row("lowest", d, deciles <= d, (unit_decile >= 1) & (unit_decile <= d))
        for d in sorted(set(lowest_deciles))
    ]
    return rows
