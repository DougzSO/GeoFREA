"""The two-pass evaluator of F7: regret, satisficing and the variance decomposition over cells, members and draws.

Implements M-F7-01 to M-F7-04, M-F7-06 and M-F7-10 for one country, technology and window (D-F7-006 to D-F7-011).

The futures are the members of the window times the Latin hypercube draws `s >= 1`; the nominal vector `s0` (column 0 of the samples) is the
nominal parameter set and enters only the nominal LCOE, `MR_clim`, the potential at `s0` and the ranges' central values (D-F7-010). Every
member is evaluated in two passes over blocks of cells that hold all samples of the block, so the quantiles are exact and the memory stays under
the budget (A-10):

  - pass 1 gives, per sample, the reference level `L*` (the minimum LCOE over the feasible cells of the F7 set, `q_ref = 0`) and the highest
    feasible LCOE (the worst-case regret of M-F7-02 is `(H - L*) / L*`);
  - pass 2 gives the regret `r = LCOE / L* - 1`, its P90 over the draws (`MR` is the maximum over members), the satisficing counter, the
    moments of `r` (the variance of `X = LCOE / L*` is the variance of `r`), `MR_clim`, `MR_tech` and the potential below `tau` of each
    future.

Feasibility is an energy floor per cell handed to the kernel (`MemberWorld.floor`): `+inf` for a cell-member whose `CF(m, s0)` is below `CF_min`
and `0` otherwise, so for a feasible cell-member a draw is infeasible only at zero energy (D-F7-007). An infeasible entry is `+inf` LCOE; in the
P90 it takes the worst-case regret of its sample, and a climate-fragile cell is given no `MR` afterwards (D-F7-011).

Nothing sample-level is returned: the arrays are per cell, per member or per (member, sample).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from geofrea.lcoe_modeling.kernel import CellInputs, SampleInputs, lcoe_block
from geofrea.lcoe_modeling.summary import quantiles_of_rows

logger = logging.getLogger("geofrea.robustness_analysis.evaluator")

P90 = 0.9  # the quantile over parameter samples of M-F7-03
_SLABS = 8  # column slabs of the reductions, so their temporaries are an eighth of a block


class EvaluationError(ValueError):
    """A future cannot be evaluated: no feasible cell, a non-positive LCOE or inputs that disagree (A-09)."""


@dataclass(frozen=True)
class MemberWorld:
    """One member over the cells of the F7 set (the same cells, in the same order, for every member).

    Args:
        member: Member identifier.
        cells: Kernel inputs of the cells.
        floor: Energy floor per cell for the kernel, MWh per year: `+inf` where `CF(m, s0) < CF_min`, else `0` (D-F7-007).
    """

    member: str
    cells: CellInputs
    floor: np.ndarray

    def __post_init__(self) -> None:
        floor = np.asarray(self.floor, dtype="float64")
        object.__setattr__(self, "floor", floor)
        if floor.shape != (len(self.cells),):
            raise EvaluationError(f"member {self.member}: one floor per cell is needed")

    @property
    def fails_cf_min(self) -> np.ndarray:
        """Cells whose `CF(m, s0)` is below `CF_min` in this member."""
        return np.isposinf(self.floor)


@dataclass(frozen=True)
class Evaluation:
    """Per-cell, per-member and per-future results of the two passes for the core members (and the reference member `m0`).

    Cells are the F7 set in `cell_id` order. The member axis of `nominal_lcoe`, `potential_*` and `reference_*` is `[reference, *core]`.
    """

    members: tuple[str, ...]  # the core members, in order
    reference: str
    n_draws: int
    nominal_lcoe: (
        np.ndarray
    )  # (C, 1 + M): nominal LCOE at s0, USD/MWh; column 0 is the reference member
    mr: np.ndarray  # (C,): max over core members of the P90 over draws of r (NaN for a cell that fails CF_min in some core member)
    mr_clim: np.ndarray  # (C,): max over core members of r at s0
    mr_tech: np.ndarray  # (C,): P90 over draws of r in the reference member
    sr: (
        np.ndarray | None
    )  # (C,): share of the core futures that are feasible with LCOE <= tau; None without tau
    var_total: (
        np.ndarray
    )  # (C,): variance of the relative LCOE over the core futures (finite ones), population form
    var_within: np.ndarray  # (C,): E_m[Var_s] part (techno-economic)
    var_between: np.ndarray  # (C,): Var_m[E_s] part (climate)
    n_futures_finite: np.ndarray  # (C,): number of finite core futures
    lowest: np.ndarray  # (1 + M, N + 1): L* of each future (column 0 is s0)
    highest: np.ndarray  # (1 + M, N + 1): highest feasible LCOE of each future
    potential_gw: (
        np.ndarray | None
    )  # (1 + M, N + 1): capacity of the cells that are feasible with LCOE <= tau, per future
    potential_twh: np.ndarray | None  # (1 + M, N + 1): energy of those cells


def _slab_bounds(n: int) -> list[tuple[int, int]]:
    width = max(1, -(-n // _SLABS))
    return [(a, min(a + width, n)) for a in range(0, n, width)]


def reference_levels(
    world: MemberWorld, samples: SampleInputs, block_cells: int
) -> tuple[np.ndarray, np.ndarray]:
    """Pass 1: `L*` (minimum over feasible cells) and the highest feasible LCOE, per sample, for one member.

    Implements: M-F7-02.

    Raises:
        EvaluationError: a sample has no feasible cell, or a feasible LCOE is not positive (the relative regret is undefined).
    """
    n_cells = len(world.cells)
    lowest = np.full(len(samples), np.inf)
    highest = np.full(len(samples), -np.inf)
    for start in range(0, n_cells, block_cells):
        window = slice(start, min(start + block_cells, n_cells))
        block = lcoe_block(world.cells.take(window), samples, min_energy_mwh=world.floor[window])
        lowest = np.minimum(lowest, block.min(axis=0))
        np.copyto(block, -np.inf, where=np.isposinf(block))
        highest = np.maximum(highest, block.max(axis=0))
    if np.isposinf(lowest).any():
        bad = int(np.flatnonzero(np.isposinf(lowest))[0])
        raise EvaluationError(
            f"member {world.member}: sample {bad} has no feasible cell, the regret is undefined"
        )
    if (lowest <= 0).any():
        raise EvaluationError(f"member {world.member}: a reference level is not positive")
    return lowest, highest


def _finite_moments(x: np.ndarray, finite: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Count, mean and sum of squared deviations of the finite entries of each row, in column slabs."""
    n_rows = x.shape[0]
    count = finite.sum(axis=1)
    total = np.zeros(n_rows)
    for a, b in _slab_bounds(x.shape[1]):
        total += np.where(finite[:, a:b], x[:, a:b], 0.0).sum(axis=1)
    mean = np.where(count > 0, total / np.maximum(count, 1), 0.0)
    m2 = np.zeros(n_rows)
    for a, b in _slab_bounds(x.shape[1]):
        deviation = np.where(finite[:, a:b], x[:, a:b] - mean[:, None], 0.0)
        m2 += np.einsum("ij,ij->i", deviation, deviation)
    return count, mean, m2


def _masked_matvec(vector: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """`vector @ mask` for a boolean (cells x samples) mask, without a float copy of the whole mask."""
    out = np.zeros(mask.shape[1])
    for a, b in _slab_bounds(mask.shape[1]):
        out[a:b] = vector @ mask[:, a:b].astype("float64")
    return out


class _Accumulator:
    """Running state across members; one `add_*` call per member."""

    def __init__(self, n_cells: int, n_members: int, n_samples: int, with_tau: bool) -> None:
        self.nominal = np.full((n_cells, 1 + n_members), np.nan)
        self.mr = np.full(n_cells, -np.inf)
        self.mr_clim = np.full(n_cells, -np.inf)
        self.mr_tech = np.full(n_cells, np.nan)
        self.sr_count = np.zeros(n_cells, dtype="int64")
        self.mean = np.zeros((n_cells, n_members))
        self.count = np.zeros((n_cells, n_members), dtype="int64")
        self.within_ss = np.zeros(n_cells)
        self.lowest = np.full((1 + n_members, n_samples), np.nan)
        self.highest = np.full((1 + n_members, n_samples), np.nan)
        self.potential_p = np.zeros((1 + n_members, n_samples)) if with_tau else None
        self.potential_e = np.zeros((1 + n_members, n_samples)) if with_tau else None


def _member_pass_two(
    world: MemberWorld,
    samples: SampleInputs,
    lowest: np.ndarray,
    highest: np.ndarray,
    acc: _Accumulator,
    *,
    slot: int,
    core: bool,
    tau: float | None,
    block_cells: int,
) -> None:
    """Pass 2 of one member: nominal LCOE, regret, P90, satisficing counter, moments, potential below `tau`."""
    n_cells = len(world.cells)
    energy_x = samples.energy_parameter
    worst = (highest - lowest) / lowest  # M-F7-02: the regret given to an infeasible entry
    draw_low = lowest[1:]
    draw_worst = worst[1:]
    acc.lowest[slot], acc.highest[slot] = lowest, highest
    for start in range(0, n_cells, block_cells):
        window = slice(start, min(start + block_cells, n_cells))
        part = world.cells.take(window)
        block = lcoe_block(part, samples, min_energy_mwh=world.floor[window])
        acc.nominal[window, slot] = block[:, 0]
        nominal_regret = block[:, 0] / lowest[0] - 1.0
        nominal_regret = np.where(np.isfinite(nominal_regret), nominal_regret, worst[0])
        draws = block[:, 1:]
        finite = np.isfinite(draws)
        if tau is not None:
            within_tau = finite & (draws <= tau)
            if core:
                acc.sr_count[window] += within_tau.sum(axis=1)
            both = np.concatenate([block[:, :1] <= tau, within_tau], axis=1) & np.concatenate(
                [np.isfinite(block[:, :1]), finite], axis=1
            )
            assert acc.potential_p is not None and acc.potential_e is not None
            acc.potential_p[slot] += _masked_matvec(part.p_mw, both) / 1000.0
            offset_e = part.energy_mwh * part.energy_offset
            slope_e = part.energy_mwh * part.energy_slope
            acc.potential_e[slot] += (
                _masked_matvec(offset_e, both) + energy_x * _masked_matvec(slope_e, both)
            ) / 1.0e6
            del both, within_tau
        regret = draws / draw_low
        regret -= 1.0
        del block, draws
        if core:
            count, mean, m2 = _finite_moments(regret, finite)
            acc.count[window, slot - 1] = count
            acc.mean[window, slot - 1] = mean
            acc.within_ss[window] += m2
            acc.mr_clim[window] = np.maximum(acc.mr_clim[window], nominal_regret)
        np.copyto(regret, np.broadcast_to(draw_worst, regret.shape), where=~finite)
        del finite
        p90 = quantiles_of_rows(regret, (P90,))[0]
        del regret
        if core:
            acc.mr[window] = np.maximum(acc.mr[window], p90)
        else:
            acc.mr_tech[window] = p90


def evaluate(
    reference: MemberWorld,
    core: Sequence[MemberWorld],
    samples: SampleInputs,
    *,
    tau: float | None,
    block_cells: int,
    progress: Callable[[], None] | None = None,
) -> Evaluation:
    """Evaluate the reference member and the core members over the F7 set.

    Implements: M-F7-02, M-F7-03, M-F7-04, M-F7-06, M-F7-10.

    Args:
        reference: The reference member `m0`, over the F7 set.
        core: The members of the window, over the same cells in the same order.
        samples: Column 0 is the nominal vector `s0`, columns `1..N` the draws.
        tau: The satisficing threshold, USD/MWh; None skips `SR` and the potential below `tau`.
        block_cells: Cells per block, from the memory budget.
        progress: Called once per member pass.

    Returns:
        The `Evaluation`; cells that fail `CF_min` in some core member have `mr = NaN`.

    Raises:
        EvaluationError: no member, members over different cells, fewer than two draws, or a future without a feasible cell.
    """
    if not core:
        raise EvaluationError("no member to evaluate")
    n_cells = len(reference.cells)
    if any(len(w.cells) != n_cells for w in core):
        raise EvaluationError("the members do not cover the same cells")
    n_draws = len(samples) - 1
    if n_draws < 2:
        raise EvaluationError("at least two draws are needed")
    acc = _Accumulator(n_cells, len(core), len(samples), tau is not None)
    worlds = [reference, *core]
    for slot, world in enumerate(worlds):
        lowest, highest = reference_levels(world, samples, block_cells)
        _member_pass_two(
            world,
            samples,
            lowest,
            highest,
            acc,
            slot=slot,
            core=slot > 0,
            tau=tau,
            block_cells=block_cells,
        )
        if progress is not None:
            progress()
    if (acc.mr < -1e-12).any() or (acc.mr_tech < -1e-12).any():
        raise EvaluationError("a negative regret, V-03 is violated")
    fragile = np.any([w.fails_cf_min for w in core], axis=0)
    mr = np.where(fragile, np.nan, np.maximum(acc.mr, 0.0))
    total_n = acc.count.sum(axis=1)
    safe_n = np.maximum(total_n, 1)
    grand = (acc.count * acc.mean).sum(axis=1) / safe_n
    between = (acc.count * (acc.mean - grand[:, None]) ** 2).sum(axis=1)
    within = acc.within_ss
    with np.errstate(invalid="ignore", divide="ignore"):
        var_total = np.where(total_n > 0, (within + between) / safe_n, np.nan)
        var_within = np.where(total_n > 0, within / safe_n, np.nan)
        var_between = np.where(total_n > 0, between / safe_n, np.nan)
    return Evaluation(
        members=tuple(w.member for w in core),
        reference=reference.member,
        n_draws=n_draws,
        nominal_lcoe=acc.nominal,
        mr=mr,
        mr_clim=np.maximum(acc.mr_clim, 0.0),
        mr_tech=np.maximum(acc.mr_tech, 0.0),
        sr=None if tau is None else acc.sr_count / (len(core) * n_draws),
        var_total=var_total,
        var_within=var_within,
        var_between=var_between,
        n_futures_finite=total_n,
        lowest=acc.lowest,
        highest=acc.highest,
        potential_gw=acc.potential_p,
        potential_twh=acc.potential_e,
    )
