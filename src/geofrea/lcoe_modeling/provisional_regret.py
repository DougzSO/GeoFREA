"""PROVISIONAL stand-in for the max-regret of F7 (M-F7-02, M-F7-03), used only by the sample-size protocol (U-04, D-F6-004).

F7 does not exist yet, and the protocol that sizes the Latin hypercube needs the primary metric `MR`. This module computes it from the
pure F6 kernel in the two passes per member that D-F6-001 describes, with these simplifications, each to be removed when F7 supplies its
own function:

  - feasibility is "the energy is positive" (an infinite LCOE is infeasible), because `CF_min` (OQ-008) has no value yet;
  - the reference level `L*_f` is the minimum LCOE over the feasible cells of the future (`q_ref = 0`; any other `q_ref`, OQ-020, is
    refused), so the first pass is a running minimum over cell blocks;
  - ties and the satisficing tie-break of M-F7-05 are not used here.

Nothing computed by this module is a result of the thesis. Replace it with the function of F7 when it exists.
"""

from __future__ import annotations

import numpy as np

from geofrea.lcoe_modeling.kernel import CellInputs, SampleInputs, lcoe_block
from geofrea.lcoe_modeling.summary import quantiles_of_rows

PROVISIONAL = True
P90 = 0.9  # the quantile over parameter samples of M-F7-03


class ProvisionalRegretError(ValueError):
    """The provisional regret cannot be computed (A-09)."""


def provisional_max_regret(
    per_member: list[CellInputs], draws: SampleInputs, block_cells: int
) -> np.ndarray:
    """`MR_i = max over members of the P90 over the draws of r_i,(m,s)` for the cells common to every member.

    Implements: M-F7-02, M-F7-03 (provisional, see the module docstring).

    Args:
        per_member: One `CellInputs` per member, all over the same cells in the same order.
        draws: The Latin hypercube draws `s >= 1`; the nominal vector is not among them (D-F6-003).
        block_cells: Cells per block, from the memory budget.

    Returns:
        `MR` per cell, shape `(C,)`, non-negative.

    Raises:
        ProvisionalRegretError: no members, members over different cell counts, or a future with no feasible cell.
    """
    if not per_member:
        raise ProvisionalRegretError("no member to evaluate")
    n_cells = len(per_member[0])
    if any(len(cells) != n_cells for cells in per_member):
        raise ProvisionalRegretError("the members do not cover the same cells")
    n = len(draws)
    mr = np.full(n_cells, -np.inf)
    for cells in per_member:
        # pass 1: per sample, the reference level (running minimum) and the highest feasible LCOE
        lowest = np.full(n, np.inf)
        highest = np.full(n, -np.inf)
        for start in range(0, n_cells, block_cells):
            block = lcoe_block(cells.take(slice(start, start + block_cells)), draws)
            lowest = np.minimum(
                lowest, block.min(axis=0)
            )  # infinite entries are infeasible and never the minimum
            np.copyto(block, -np.inf, where=np.isposinf(block))
            highest = np.maximum(highest, block.max(axis=0))
        if np.isposinf(lowest).any():
            raise ProvisionalRegretError("a future has no feasible cell, the regret is undefined")
        worst = (highest - lowest) / lowest  # the regret given to an infeasible cell (M-F7-02)
        # pass 2: the regret, then the P90 over samples, then the maximum over members
        for start in range(0, n_cells, block_cells):
            window = slice(start, min(start + block_cells, n_cells))
            block = lcoe_block(cells.take(window), draws)
            infeasible = ~np.isfinite(block)
            block -= lowest
            block /= lowest
            np.copyto(block, np.broadcast_to(worst, block.shape), where=infeasible)
            del infeasible
            p90 = quantiles_of_rows(block, (P90,))[0]
            mr[window] = np.maximum(mr[window], p90)
    if (mr < -1e-12).any():
        raise ProvisionalRegretError("a negative regret, V-03 is violated")
    return np.maximum(mr, 0.0)
