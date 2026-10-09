"""Nominal supply curve of a member: cells in increasing nominal LCOE with cumulative capacity and energy (M-F6-06; D-F6-013)."""

from __future__ import annotations

import numpy as np
import pandas as pd

MW_PER_GW = 1.0e3
MWH_PER_TWH = 1.0e6


def supply_curve(
    member: str,
    cell_id: np.ndarray,
    lcoe_nominal: np.ndarray,
    p_mw: np.ndarray,
    e_mwh: np.ndarray,
) -> pd.DataFrame:
    """The curve of one member: rank 1 is the cheapest cell; ties are ordered by `cell_id`, infinite LCOE comes last.

    Implements: M-F6-06.

    Args:
        member: Member identifier.
        cell_id: Cell identifiers, shape `(C,)`.
        lcoe_nominal: Nominal LCOE of the cells, USD2024/MWh.
        p_mw: Capacity of the cells, MW.
        e_mwh: Annual energy of the cells at the nominal parameters, MWh.

    Returns:
        DataFrame with `member`, `rank`, `cell_id`, `lcoe_nominal`, `cum_P_GW` and `cum_E_TWh`.
    """
    order = np.lexsort((cell_id, lcoe_nominal))
    return pd.DataFrame(
        {
            "member": np.full(len(order), member, dtype=object),
            "rank": np.arange(1, len(order) + 1, dtype="int64"),
            "cell_id": np.asarray(cell_id, dtype="int64")[order],
            "lcoe_nominal": np.asarray(lcoe_nominal, dtype="float64")[order],
            "cum_P_GW": np.cumsum(np.asarray(p_mw, dtype="float64")[order]) / MW_PER_GW,
            "cum_E_TWh": np.cumsum(np.asarray(e_mwh, dtype="float64")[order]) / MWH_PER_TWH,
        }
    )
