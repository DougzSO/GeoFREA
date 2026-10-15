# ruff: noqa
"""Item 3 (cont.): native land cells whose dT deviates by more than 1 K from the median of their 8 neighbours, per GCM.
Needs b1_BRA.npz. Usage: python dT_isolated_cells.py"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from scipy.ndimage import generic_filter

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import *  # noqa

Z = np.load(SCRATCH / "b1_BRA.npz")
rows = []
for g in GCMS:
    land = Z[f"native_land|{g}"]
    for s in SSPS:
        for w in WINDOWS:
            a = Z[f"native_dT|{g}|{s}|{w}"].astype(float)
            dev = generic_filter(
                a, lambda x: x[4] - np.nanmedian(np.delete(x, 4)), size=3, mode="nearest"
            )[land]
            rows.append(
                (g, s, w, int(land.sum()), int((np.abs(dev) > 1).sum()), float(np.abs(dev).max()))
            )
df = pd.DataFrame(
    rows,
    columns=[
        "GCM",
        "SSP",
        "window",
        "native land cells",
        "isolated cells (|dev| > 1 K)",
        "max |deviation| (K)",
    ],
)
print(
    md(
        df.groupby("GCM", sort=False)
        .agg(
            **{
                "native land cells": ("native land cells", "first"),
                "members": ("SSP", "size"),
                "isolated cells, all members": ("isolated cells (|dev| > 1 K)", "sum"),
                "max |deviation| (K)": ("max |deviation| (K)", "max"),
            }
        )
        .reset_index()
    )
)
