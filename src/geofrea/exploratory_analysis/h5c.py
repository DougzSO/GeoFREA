"""Cost-to-target, H5c: the marginal and the average cost of reaching an energy level, per member (M-X-01; DEC-098).

EXPLORATORY. The pre-registered H5 (M-F7-07) is unchanged and remains the primary result; no cost threshold tau is used here.

For a member `m` the cells of the F7 set are ordered by `LCOE_i,(m,s0)` ascending, ties by `cell_id`, and their annual energy `E_i,m` is accumulated. For an
energy level `G` (TWh/year) the marginal cost `MC_m(G)` is the LCOE of the cell at which the cumulative energy first reaches `G` (the last cell is
fractional) and the average cost `AC_m(G)` is the energy-weighted mean LCOE of the cells taken (the last one for the fraction that is needed). A cell-member
with no finite LCOE (infeasible, `CF < CF_min`) or no energy supplies nothing at a finite cost and is left out of the curve; a level that the cumulative
energy of a member does not reach is `level_unreachable` for that member.

Every function here is pure: it reads arrays and returns arrays or numbers, so it can be tested by hand on small cases.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

REFERENCE_MEMBER = "m0"  # `geofrea.climate_forcing.members.REFERENCE_MEMBER_ID`; a test pins the equality
P_LEVELS = (0.05, 0.10, 0.25)  # G_p = p x E_total,m0 (DEC-098 a)
MATERIAL_DELTA_MC = 0.05  # the descriptive label threshold of DEC-098 a)
LABEL_MATERIAL = "material climate pressure on the cost of the target"
LABEL_NOT_MATERIAL = "no material climate pressure on the cost of the target"
LABEL_UNREACHABLE = "target level not reached by the reference member"
LEVEL_TARGET = "target"
_REACH_TOLERANCE = 1.0e-9  # relative: a level equal to the total energy is reached


@dataclass(frozen=True)
class CostCurve:
    """The finite-cost cells of one member in ascending order of LCOE, with the running energy and the running cost."""

    cell_id: np.ndarray
    lcoe: np.ndarray
    energy_twh: np.ndarray
    cumulative_energy_twh: np.ndarray
    cumulative_cost: np.ndarray  # sum of LCOE x energy, USD millions per year

    @property
    def total_twh(self) -> float:
        return float(self.cumulative_energy_twh[-1]) if len(self.cumulative_energy_twh) else 0.0


def cost_curve(cell_id: np.ndarray, lcoe: np.ndarray, energy_twh: np.ndarray) -> CostCurve:
    """The curve of a member: cells with a finite LCOE and positive energy, by LCOE ascending and `cell_id` ascending."""
    cell_id = np.asarray(cell_id, dtype="int64")
    lcoe = np.asarray(lcoe, dtype="float64")
    energy = np.asarray(energy_twh, dtype="float64")
    keep = np.isfinite(lcoe) & np.isfinite(energy) & (energy > 0)
    cell_id, lcoe, energy = cell_id[keep], lcoe[keep], energy[keep]
    order = np.lexsort((cell_id, lcoe))  # last key is the primary key
    cell_id, lcoe, energy = cell_id[order], lcoe[order], energy[order]
    return CostCurve(cell_id, lcoe, energy, np.cumsum(energy), np.cumsum(lcoe * energy))


def reached(curve: CostCurve, level_twh: float) -> bool:
    """True when the cumulative energy of the curve reaches `level_twh`."""
    return level_twh > 0 and curve.total_twh >= level_twh * (1.0 - _REACH_TOLERANCE)


def marginal_cost(curve: CostCurve, level_twh: float) -> float:
    """`MC(G)`: the LCOE of the cell at which the cumulative energy first reaches `G`; NaN when the level is not reached."""
    if not reached(curve, level_twh):
        return float("nan")
    index = min(int(np.searchsorted(curve.cumulative_energy_twh, level_twh * (1.0 - _REACH_TOLERANCE), side="left")), len(curve.lcoe) - 1)
    return float(curve.lcoe[index])


def average_cost(curve: CostCurve, level_twh: float) -> float:
    """`AC(G)`: the energy-weighted mean LCOE of the cells taken to reach `G`, the last cell fractional; NaN when the level is not reached."""
    if not reached(curve, level_twh):
        return float("nan")
    index = min(int(np.searchsorted(curve.cumulative_energy_twh, level_twh * (1.0 - _REACH_TOLERANCE), side="left")), len(curve.lcoe) - 1)
    before_energy = float(curve.cumulative_energy_twh[index - 1]) if index > 0 else 0.0
    before_cost = float(curve.cumulative_cost[index - 1]) if index > 0 else 0.0
    taken = min(level_twh - before_energy, float(curve.energy_twh[index]))
    return (before_cost + float(curve.lcoe[index]) * taken) / (before_energy + taken)


def levels(g_target_twh: float | None, total_m0_twh: float, p_levels: Sequence[float] = P_LEVELS) -> list[tuple[str, float]]:
    """The levels of DEC-098 a): `target` (when a target exists and converts to a positive energy) and `p05`, `p10`, `p25` of the energy of the F7 set at m0."""
    out: list[tuple[str, float]] = []
    if g_target_twh is not None and np.isfinite(g_target_twh) and g_target_twh > 0:
        out.append((LEVEL_TARGET, float(g_target_twh)))
    out += [(f"p{round(p * 100):02d}", float(p * total_m0_twh)) for p in p_levels]
    return out


def member_rows(
    curves: Mapping[str, CostCurve], gcm_of: Mapping[str, str], ssp_of: Mapping[str, str], level_twh: float, reference: str = REFERENCE_MEMBER
) -> pd.DataFrame:
    """One row per core member for a level: `mc`, `ac`, the relative changes against the reference member and `level_unreachable`."""
    mc0 = marginal_cost(curves[reference], level_twh)
    ac0 = average_cost(curves[reference], level_twh)
    rows = []
    for member in sorted(m for m in curves if m != reference):
        mc, ac = marginal_cost(curves[member], level_twh), average_cost(curves[member], level_twh)
        rows.append(
            {
                "member": member,
                "gcm": gcm_of.get(member),
                "ssp": ssp_of.get(member),
                "mc": mc,
                "ac": ac,
                "d_mc": (mc - mc0) / mc0 if np.isfinite(mc) and np.isfinite(mc0) and mc0 > 0 else float("nan"),
                "d_ac": (ac - ac0) / ac0 if np.isfinite(ac) and np.isfinite(ac0) and ac0 > 0 else float("nan"),
                "level_unreachable": not (np.isfinite(mc) and np.isfinite(ac)),
            }
        )
    return pd.DataFrame(
        rows, columns=["member", "gcm", "ssp", "mc", "ac", "d_mc", "d_ac", "level_unreachable"]
    ).astype({"level_unreachable": bool})


def _extreme(rows: pd.DataFrame, column: str) -> tuple[float, str | None, str | None]:
    """The largest finite value of `column`, the member and the SSP that attain it (the first member in order on a tie)."""
    finite = rows[np.isfinite(rows[column])]
    if finite.empty:
        return float("nan"), None, None
    best = finite.loc[finite[column].idxmax()]  # idxmax returns the first of equal maxima
    return float(best[column]), str(best["member"]), None if best["ssp"] is None else str(best["ssp"])


def pressure(rows: pd.DataFrame, which: str) -> dict:
    """`Delta` of `which` (`mc` or `ac`): the maximum over the core members with the member and the SSP, the median over members, and the value per SSP
    (the maximum over its GCMs)."""
    column = f"d_{which}"
    top, member, ssp = _extreme(rows, column)
    finite = rows[np.isfinite(rows[column])]
    by_ssp = {str(s): float(g[column].max()) for s, g in finite.groupby("ssp", sort=True)}
    return {
        f"delta_{which}_max": top,
        f"delta_{which}_member": member,
        f"delta_{which}_ssp": ssp,
        f"delta_{which}_median": float(finite[column].median()) if len(finite) else float("nan"),
        f"delta_{which}_by_ssp": by_ssp,
    }


def label_for(level_id: str, delta_mc_max: float) -> str | None:
    """The descriptive label of DEC-098 a): defined at the target level only."""
    if level_id != LEVEL_TARGET:
        return None
    if not np.isfinite(delta_mc_max):
        return LABEL_UNREACHABLE
    return LABEL_MATERIAL if delta_mc_max >= MATERIAL_DELTA_MC else LABEL_NOT_MATERIAL
