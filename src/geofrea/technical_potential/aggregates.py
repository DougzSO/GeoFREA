"""Country aggregates per land scenario and member, all present cells and like-for-like (M-F5-06; D-F5-006).

The climate effect on potential is the change of a member against `m0` over the cells present in every member of the scenario:
a cell dropped from a member because of a masked wind factor (M-F4-07) lowers that member's total for a data reason and not a
climate reason, so the all-present series is not comparable with `m0`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd


def like_for_like_mask(energy_by_member: Mapping[str, np.ndarray]) -> np.ndarray:
    """Cells present (finite energy) in every member.

    Implements: M-F5-06.

    Args:
        energy_by_member: Energy per candidate cell, MWh, one array per member, NaN where the member is absent.

    Returns:
        Boolean array over the candidate cells.
    """
    arrays = list(energy_by_member.values())
    if not arrays:
        raise ValueError("no member given")
    present = np.ones(arrays[0].shape, dtype=bool)
    for energy in arrays:
        present &= np.isfinite(energy)
    return present


def aggregate_scenario(
    scenario: str,
    members: Sequence[str],
    p_mw: np.ndarray,
    eligible_area_km2: np.ndarray,
    energy_by_member: Mapping[str, np.ndarray],
    reference_member: str,
    hours_per_year: float,
) -> pd.DataFrame:
    """One row per member with the all-present and the like-for-like totals of a land scenario.

    Implements: M-F5-06.

    Args:
        scenario: Land scenario name.
        members: Member ids, in output order; `reference_member` must be one of them.
        p_mw: Capacity of each candidate cell, MW, shape (n_cells,).
        eligible_area_km2: Eligible area of each candidate cell, km2, shape (n_cells,).
        energy_by_member: Energy per candidate cell, MWh, NaN where the member is absent in that cell.
        reference_member: The reference member id (`m0`).
        hours_per_year: Hours in a year, for the energy-weighted capacity factor.

    Returns:
        A frame with the columns of `PotentialAggregateRow`.
    """
    if reference_member not in members:
        raise ValueError(f"reference member {reference_member!r} is not among the members")
    if set(energy_by_member) != set(members):
        raise ValueError("energy_by_member must have exactly the listed members")
    lfl = like_for_like_mask(energy_by_member)
    p_lfl = float(p_mw[lfl].sum()) / 1e3
    e_lfl_ref = float(energy_by_member[reference_member][lfl].sum()) / 1e6
    rows = []
    for member in members:
        energy = energy_by_member[member]
        present = np.isfinite(energy)
        p_sum_mw = float(p_mw[present].sum())
        e_sum_mwh = float(energy[present].sum())
        e_lfl = float(energy[lfl].sum()) / 1e6
        rows.append(
            {
                "scenario": scenario,
                "member": member,
                "n_cells": int(present.sum()),
                "n_cells_absent": int((~present).sum()),
                "n_cells_like_for_like": int(lfl.sum()),
                "eligible_area_km2": float(eligible_area_km2[present].sum()),
                "P_GW": p_sum_mw / 1e3,
                "E_TWh": e_sum_mwh / 1e6,
                "cf_energy_weighted": e_sum_mwh / (p_sum_mw * hours_per_year)
                if p_sum_mw > 0
                else None,
                "P_GW_like_for_like": p_lfl,
                "E_TWh_like_for_like": e_lfl,
                "delta_E_pct_vs_m0_like_for_like": 100.0 * (e_lfl / e_lfl_ref - 1.0)
                if e_lfl_ref > 0
                else None,
            }
        )
    return pd.DataFrame(rows)
