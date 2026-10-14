"""The potential below `tau` (T-R12, H5) and the exposure of potential to hazards (T-R10, H5) (M-F7-07; D-F7-019, D-F7-020, D-F7-052).

Both are sums of the capacity (GW) and the energy (TWh) of groups of cells; neither enters regret or satisficing (M-F4-05). The wording is
"exposed": a hazard enters the LCOE only through a loss function of evidence Tier 1 or 2 (OQ-007).

H5 uses these calculations (D-F7-052): a cell is exposed in a channel when the indicator is at least its threshold (`exposed_flags`, OQ-051), and the
energy of the fixed economic domain in each member is the `fixed_domain` series of T-R12.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

REFERENCE_COLUMNS = {
    "tx35_days": "tx35_days_ref",
    "tx40_days": "tx40_days_ref",
    "rx5day_mm": "rx5day_mm_ref",
    "gust_mean_annual_max_ms": "gust_mean_annual_max_ms",  # scenario-invariant: its own reference (M-F1-05)
}  # `wet_p95_exceed_freq` has no reference column of the same quantity
UNION = "any_channel"  # the hazard of the rows that count a cell once when it is exposed in at least one channel (H5b)


class ThesisTableError(ValueError):
    """The tables behind T-R10 or T-R12 do not agree (A-09)."""


def merge_nominal_lcoe(
    potential: pd.DataFrame, lcoe_nominal: pd.DataFrame, scenario: str
) -> pd.DataFrame:
    """The F5 rows with the F6 nominal LCOE of the same cell and member.

    Raises:
        ThesisTableError: an F5 row has no F6 nominal LCOE.
    """
    table = potential.assign(member=potential["member"].astype(str)).merge(
        lcoe_nominal.assign(member=lcoe_nominal["member"].astype(str)),
        on=["cell_id", "member"],
        how="left",
        validate="one_to_one",
    )
    if table["lcoe_nominal"].isna().any():
        raise ThesisTableError(f"{scenario}: F5 rows without an F6 nominal LCOE")
    return table


def like_for_like_cells(
    table: pd.DataFrame, members: Sequence[str], reference: str, cf_min: float
) -> np.ndarray:
    """The cells present in `reference` and in every member of the window and feasible at the reference (the F7 set of the scenario), sorted.

    Implements: T-R12, M-F7-01, M-F7-07 (H5, `Omega`). A cell is feasible at the reference when its capacity factor is at least `cf_min` and its
    energy is positive.
    """
    wanted = [reference, *members]
    table = table[table["member"].isin(wanted)]
    counts = table.groupby("cell_id")["member"].nunique()
    in_all = set(counts[counts == len(wanted)].index)
    at_reference = table[table["member"] == reference].set_index("cell_id")
    feasible = set(at_reference.index[(at_reference["CF"] >= cf_min) & (at_reference["E_MWh"] > 0)])
    return np.array(sorted(in_all & feasible), dtype="int64")


def potential_below_tau_nominal(
    potential: pd.DataFrame,
    lcoe_nominal: pd.DataFrame,
    members: Sequence[str],
    reference: str,
    cf_min: float,
    tau: float,
    target_gw: float | None,
    scenario: str,
) -> list[dict]:
    """Nominal potential (GW, TWh) of the feasible cells with LCOE at most `tau`, per member, for one land scenario.

    Implements: T-R12, M-F7-07 (H5; D-F7-020).

    Three series: `all_present` (every cell the member has), `like_for_like` (the cells present in `reference` and every member of the
    window and feasible at the reference: the F7 set of that scenario) and `fixed_domain` (the cells of the like-for-like set whose nominal LCOE
    at the reference is at most `tau`, evaluated in every member whether or not they stay below `tau` there: the economic domain `Omega_econ` of
    H5, whose energy per member is `E_m`). In the first two a cell counts in a member when its capacity factor is at least `cf_min` and its
    nominal LCOE in that member is at most `tau`.

    Args:
        potential: F5 rows `cell_id, member, P_MW, CF, E_MWh` of the scenario.
        lcoe_nominal: `cell_id, member, lcoe_nominal` of the scenario (F6).
        members: The members of the window.
        reference: The reference member.
        cf_min: Minimum capacity factor.
        tau: Satisficing LCOE threshold, USD/MWh.
        target_gw: The national capacity target, or None.
        scenario: Name of the land scenario.

    Raises:
        ThesisTableError: an F5 row has no F6 nominal LCOE.
    """
    table = merge_nominal_lcoe(potential, lcoe_nominal, scenario)
    wanted = [reference, *members]
    table = table[table["member"].isin(wanted)]
    at_reference = table[table["member"] == reference].set_index("cell_id")
    like = set(like_for_like_cells(table, members, reference, cf_min).tolist())
    ok = (
        (table["CF"] >= cf_min)
        & np.isfinite(table["lcoe_nominal"])
        & (table["lcoe_nominal"] <= tau)
    )
    in_domain = set(
        at_reference.index[
            at_reference.index.isin(like)
            & np.isfinite(at_reference["lcoe_nominal"])
            & (at_reference["lcoe_nominal"] <= tau)
        ]
    )
    rows: list[dict] = []
    for series, keep in (
        ("all_present", ok),
        ("like_for_like", ok & table["cell_id"].isin(like)),
        ("fixed_domain", table["cell_id"].isin(in_domain)),
    ):
        per_member = table[keep].groupby("member").agg(p=("P_MW", "sum"), e=("E_MWh", "sum"))
        for member in wanted:
            gw = float(per_member["p"].get(member, 0.0)) / 1000.0
            twh = float(per_member["e"].get(member, 0.0)) / 1.0e6
            rows.append(
                {
                    "member": member,
                    "land_scenario": scenario,
                    "series": series,
                    "basis": "nominal",
                    "potential_gw": gw,
                    "potential_twh": twh,
                    "gap_to_target_gw": None if target_gw is None else target_gw - gw,
                }
            )
    return rows


def potential_below_tau_draws(
    members: Sequence[str],
    reference: str,
    potential_gw: np.ndarray,
    potential_twh: np.ndarray,
    target_gw: float | None,
) -> list[dict]:
    """The P10, P50 and P90 over the draws of the potential below `tau`, like-for-like, central scenario.

    `potential_*` have shape `(1 + M, N + 1)`, the reference member first; column 0 (the nominal vector) is not among the draws.
    """
    rows = []
    for slot, member in enumerate([reference, *members]):
        gw = np.quantile(potential_gw[slot, 1:], [0.1, 0.5, 0.9])
        twh = np.quantile(potential_twh[slot, 1:], [0.1, 0.5, 0.9])
        for basis, g, t in zip(("p10", "p50", "p90"), gw, twh, strict=True):
            rows.append(
                {
                    "member": member,
                    "land_scenario": "central",
                    "series": "like_for_like",
                    "basis": basis,
                    "potential_gw": float(g),
                    "potential_twh": float(t),
                    "gap_to_target_gw": None if target_gw is None else float(target_gw - g),
                }
            )
    return rows


@dataclass(frozen=True)
class HazardMember:
    """A member that carries the hazard channel, with its capacity and energy over the F7 set."""

    member: str
    gcm: str
    ssp: str
    p_mw: np.ndarray
    e_mwh: np.ndarray


def exposure_rows(
    hazard: pd.DataFrame,
    members: Sequence[HazardMember],
    thresholds: Mapping[str, float | None],
    f7_ids: np.ndarray,
    groups: Mapping[str, np.ndarray],
) -> tuple[list[dict], dict[str, float]]:
    """Potential in the cells whose hazard indicator is above its exposure threshold, per hazard, member and group.

    Implements: T-R10, D-F7-019.

    Args:
        hazard: `hazard_context.parquet` rows (`cell_id`, `member`, the indicators and their `*_ref` values).
        members: The members of the window that carry the hazard channel.
        thresholds: Exposure threshold per indicator; None skips the indicator (OQ-051). A cell is exposed when the indicator is at least it.
        f7_ids: Cell identifiers of the F7 set, in the order of the arrays of `members` and the masks of `groups`.
        groups: Group name -> boolean mask over the F7 set (`f7_set`, `economic_domain`, `nominal_top_k`, `robust_top_k`).

    Returns:
        The rows, and per indicator the share of the capacity of the F7 set that is exposed (median over the hazard members). Beside the
        indicators, the rows of `hazard` `any_channel` count a cell once when it is exposed in at least one channel with a threshold (the
        exposure of H5b); their `reference` basis uses the channels that have a reference value.

    Raises:
        ThesisTableError: a hazard member lacks hazard rows for cells of the F7 set.
    """
    haz = hazard.assign(member=hazard["member"].astype(str))
    rows: list[dict] = []
    shares: dict[str, list[float]] = {}
    for item in members:
        h = haz[haz["member"] == item.member].set_index("cell_id")
        if not np.isin(f7_ids, h.index).all():
            raise ThesisTableError(f"member {item.member}: hazard rows lack cells of the F7 set")
        union = {
            "absolute": np.zeros(f7_ids.size, dtype=bool),
            "reference": np.zeros(f7_ids.size, dtype=bool),
        }
        in_union = {"absolute": False, "reference": False}
        for indicator, threshold in thresholds.items():
            if threshold is None:
                continue
            for basis in ("absolute", "reference"):
                if basis == "reference" and (
                    indicator not in REFERENCE_COLUMNS
                    or REFERENCE_COLUMNS[indicator] not in h.columns
                ):
                    continue
                exposed = exposed_flags(h, f7_ids, indicator, threshold, basis, item.member)
                union[basis] |= exposed
                in_union[basis] = True
                rows += _exposure_group_rows(item, indicator, basis, exposed, groups)
                if basis == "absolute" and item.p_mw.sum() > 0:
                    shares.setdefault(indicator, []).append(
                        float(item.p_mw[exposed].sum() / item.p_mw.sum())
                    )
        for basis in ("absolute", "reference"):
            if in_union[basis]:
                rows += _exposure_group_rows(item, UNION, basis, union[basis], groups)
    return rows, {name: float(np.median(v)) for name, v in shares.items()}


def exposed_flags(
    rows: pd.DataFrame,
    cell_ids: np.ndarray,
    indicator: str,
    threshold: float,
    basis: str,
    member: str,
) -> np.ndarray:
    """The cells whose indicator reaches `threshold` (OQ-051: the comparison is "at least"), in the order of `cell_ids`.

    Implements: T-R10, M-F7-07 (H5b, D-F7-052). The same function gives the exposed cells of T-R10 and of H5.

    Args:
        rows: The `hazard_context` rows of one member, indexed by `cell_id`.
        cell_ids: The cells wanted.
        indicator: A hazard indicator of `hazard_context`.
        threshold: Its exposure threshold.
        basis: `absolute` (the indicator of the member) or `reference` (its reference value, `REFERENCE_COLUMNS`).
        member: Member identifier, for the message.

    Raises:
        ThesisTableError: the member has no hazard row for some of the cells, or the indicator has no reference column.
    """
    if not np.isin(cell_ids, rows.index).all():
        raise ThesisTableError(f"member {member}: hazard rows lack cells of the F7 set")
    if basis == "absolute":
        column = indicator
    elif indicator in REFERENCE_COLUMNS:
        column = REFERENCE_COLUMNS[indicator]
    else:
        raise ThesisTableError(f"{indicator} has no reference value of the same quantity")
    return rows.loc[cell_ids, column].to_numpy(dtype="float64") >= threshold  # a NaN is not exposed


def _exposure_group_rows(
    item: HazardMember,
    hazard: str,
    basis: str,
    exposed: np.ndarray,
    groups: Mapping[str, np.ndarray],
) -> list[dict]:
    rows = []
    for group, mask in groups.items():
        chosen = exposed & mask
        rows.append(
            {
                "hazard": hazard,
                "member": item.member,
                "gcm": item.gcm,
                "ssp": item.ssp,
                "group": group,
                "basis": basis,
                "n_cells": int(chosen.sum()),
                "potential_gw": float(item.p_mw[chosen].sum() / 1000.0),
                "potential_twh": float(item.e_mwh[chosen].sum() / 1.0e6),
            }
        )
    return rows
