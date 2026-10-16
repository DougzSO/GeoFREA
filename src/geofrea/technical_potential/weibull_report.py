"""Distribution of the Global Wind Atlas Weibull A and k over the candidate cells, reported as information (OQ-053 closed).

The validity limit (A in (0, 25] m/s, k in (0, 10], `audit.yaml`) is checked by `input_ranges.validate_candidates` and stops the phase. This report
describes what lies inside it: no value of it is a plausibility threshold, so nothing here is a warning. The counts of k below 1 and above 4 are the
two values the first real run looked at (`docs/phases/F5/fix_round_46.md`).
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

_COLUMN = re.compile(r"^weibull_(a|k)_(\d+)m$")
K_LOW_REFERENCE = 1.0
K_HIGH_REFERENCE = 4.0
REPORT_COLUMNS = (
    "variable",
    "height_m",
    "n_cells",
    "p1",
    "p50",
    "p99",
    "min",
    "max",
    "n_k_below_1",
    "n_k_above_4",
)


def weibull_distribution_report(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per Weibull layer of the candidate table: P1, P50, P99, extremes and, for k, the cells below 1 and above 4.

    Implements: M-F5-06.

    Args:
        frame: Candidate table of one land scenario with columns `weibull_a_<h>m` and `weibull_k_<h>m`.

    Returns:
        DataFrame with the columns `REPORT_COLUMNS`, empty when the table has no Weibull layer. The two counts are missing (NA) for A.
    """
    rows = []
    for column in frame.columns:
        match = _COLUMN.match(column)
        if match is None:
            continue
        values = frame[column].to_numpy(dtype="float64")
        values = values[np.isfinite(values)]
        is_k = match.group(1) == "k"
        p1, p50, p99 = (np.percentile(values, q) if values.size else np.nan for q in (1, 50, 99))
        rows.append(
            {
                "variable": match.group(1).upper() if not is_k else "k",
                "height_m": int(match.group(2)),
                "n_cells": int(values.size),
                "p1": float(p1),
                "p50": float(p50),
                "p99": float(p99),
                "min": float(values.min()) if values.size else np.nan,
                "max": float(values.max()) if values.size else np.nan,
                "n_k_below_1": int((values < K_LOW_REFERENCE).sum()) if is_k else pd.NA,
                "n_k_above_4": int((values > K_HIGH_REFERENCE).sum()) if is_k else pd.NA,
            }
        )
    table = pd.DataFrame(rows, columns=list(REPORT_COLUMNS))
    table["n_k_below_1"] = table["n_k_below_1"].astype("Int64")
    table["n_k_above_4"] = table["n_k_above_4"].astype("Int64")
    return table.sort_values(["variable", "height_m"], ignore_index=True)
