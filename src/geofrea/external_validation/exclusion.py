"""Excluded share of the pixels under existing plants, per constraint (M-F7b-01, D-F7b-002).

The shares come from the pure eligibility engine of F3 evaluated on the aligned layers (nothing per pixel is read from F3's outputs), and are
averaged over the units with the capacity as the weight. Units outside the country grid, and units in a pixel the engine marks invalid, are
counted and left out of the shares.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

CONSTRAINTS = ("E1", "E2", "E3", "E4", "E5", "E6", "combined")
FULL = 1.0 - 1.0e-6  # a float32 share this close to 1 is a pixel that is entirely excluded


def exclusion_rows(
    technology: str,
    row_set: str,
    units: pd.DataFrame,
    excluded: dict[str, np.ndarray],
    valid: np.ndarray,
) -> list[dict]:
    """One row per constraint for the units of one set.

    Implements: M-F7b-01.

    Args:
        technology: The technology the units belong to.
        row_set: Name of the set of units.
        units: `capacity_mw`, `row`, `col`, `in_grid`.
        excluded: Constraint -> excluded share per pixel (`E1` to `E6`, `combined`).
        valid: Pixels where the engine has every layer it needs.
    """
    capacity = units["capacity_mw"].to_numpy(dtype="float64")
    in_grid = units["in_grid"].to_numpy(dtype=bool)
    row = units["row"].to_numpy()
    col = units["col"].to_numpy()
    valid_pixel = np.zeros(len(units), dtype=bool)
    valid_pixel[in_grid] = valid[row[in_grid], col[in_grid]]
    evaluated = in_grid & valid_pixel
    counts = {
        "n_units": len(units),
        "capacity_mw": float(capacity.sum()),
        "n_outside_grid": int((~in_grid).sum()),
        "capacity_outside_grid_mw": float(capacity[~in_grid].sum()),
        "n_invalid_pixel": int((in_grid & ~valid_pixel).sum()),
        "capacity_invalid_pixel_mw": float(capacity[in_grid & ~valid_pixel].sum()),
        "n_evaluated": int(evaluated.sum()),
        "capacity_evaluated_mw": float(capacity[evaluated].sum()),
    }
    rows = []
    for constraint in CONSTRAINTS:
        row_stats: dict[str, float | None] = dict.fromkeys(
            ("mean_excluded_share", "share_above_0", "share_at_least_half", "share_equal_1")
        )
        total = counts["capacity_evaluated_mw"]
        if total > 0:
            share = excluded[constraint][row[evaluated], col[evaluated]].astype("float64")
            weight = capacity[evaluated]
            row_stats = {
                "mean_excluded_share": float((weight * share).sum() / total),
                "share_above_0": float(weight[share > 0].sum() / total),
                "share_at_least_half": float(weight[share >= 0.5].sum() / total),
                "share_equal_1": float(weight[share >= FULL].sum() / total),
            }
        rows.append(
            {"technology": technology, "row_set": row_set, "constraint": constraint, **counts}
            | row_stats
        )
    return rows
