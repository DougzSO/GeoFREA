"""H2, spatial aggregation bias: the cell and the Admin1 selections, the Capacity Overlap Index, the verdict and the sensitivities (M-F7-07; D-F7-039 to D-F7-042).

H2 asks whether assessing expansion by region instead of by cell selects different capacity. Two procedures take the same capacity `T`:

  - the cell selection takes cells in ascending order of `z_i = MR_i` (lower is better); for `T` the capacity of the robust top-k set of H1 it
    is exactly that set;
  - the regional selection ranks the Admin1 regions by the capacity-weighted mean of `z_i` and takes them whole until `T` is reached, the
    last one with the fraction `y` that makes the total exactly `T`; every cell inherits the fraction of its region.

`O = sum(q_i min(x_cell_i, x_admin_i)) / T` is the share of `T` that both select; `O_ref = T / Q_max` is the overlap of a uniform spread over the
country. The verdict (OQ-050, H2) is `not_testable` when `O_ref >= gamma`, `supported` when `O < gamma` and `not_supported` when `O >= gamma`.
The diagnostics (`Delta_z`, the within-region variance, the interquartile range over the median, `D_TV`) and the sensitivities never change it.

Everything is a pure function of arrays over the F7 set in `cell_id` order, so the position of a cell is its tie-break. A climate-fragile cell
has no `MR` and is not in the ranked set `I`; a region without a ranked cell of positive capacity does not enter.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from geofrea.robustness_analysis.rankings import order_by, take_top_k, top_k_size

NOT_TESTABLE = "not_testable"
SUPPORTED = "supported"
NOT_SUPPORTED = "not_supported"

PRIMARY = "primary"
MEAN = "capacity_weighted_mean"
MEDIAN = "capacity_weighted_median"
GAMMA_PROFILE = tuple(round(0.10 + 0.05 * i, 2) for i in range(13))  # 0.10 to 0.70 in steps of 0.05
SENSITIVITY_TOP_K_PERCENT = (5.0, 10.0, 20.0)  # p_k of the sensitivity (METHODOLOGY M-F7-07, H2)
_TOLERANCE = 1.0e-12


class H2Error(ValueError):
    """H2 cannot be computed from its inputs (A-09)."""


@dataclass(frozen=True)
class H2Inputs:
    """What H2 reads, over the F7 set in `cell_id` order and the `M` core members.

    Attributes:
        z: `(n,)` the score `MR_i` (NaN for a cell without one).
        q: `(n,)` installable capacity of the central land scenario, MW.
        region: `(n,)` Admin1 identifier of each cell.
        ranked: Boolean over the F7 set: the cell is not climate-fragile (the set `I`).
        sr: `(n,)` satisficing robustness for the tie-break of the robust order, or None.
        p90: `(n, M)` P90 over the draws of the relative regret in each member (to recompute `z` without a GCM).
        gcms: GCM of each member.
    """

    z: np.ndarray
    q: np.ndarray
    region: np.ndarray
    ranked: np.ndarray
    sr: np.ndarray | None
    p90: np.ndarray
    gcms: tuple[str, ...]

    @property
    def n_cells(self) -> int:
        return int(self.ranked.size)


def verdict_of(overlap: float, overlap_ref: float, gamma: float) -> str:
    """not testable (`O_ref >= gamma`), supported (`O < gamma`) or not supported (`O >= gamma`)."""
    if overlap_ref >= gamma:
        return NOT_TESTABLE
    return SUPPORTED if overlap < gamma else NOT_SUPPORTED


def scores_without(inputs: H2Inputs, exclude_gcms: Sequence[str]) -> np.ndarray:
    """`z` recomputed as the maximum over the members whose GCM is not excluded (NaN where the cell is not ranked).

    Raises:
        H2Error: no member is left.
    """
    keep = [j for j, g in enumerate(inputs.gcms) if g not in set(exclude_gcms)]
    if not keep:
        raise H2Error(f"no member is left once {sorted(exclude_gcms)} are excluded")
    return np.where(inputs.ranked, inputs.p90[:, keep].max(axis=1), np.nan)


def select_cells(
    z: np.ndarray,
    q: np.ndarray,
    ranked: np.ndarray,
    *,
    k: int | None = None,
    target_mw: float | None = None,
    sr: np.ndarray | None = None,
) -> tuple[np.ndarray, float, bool]:
    """The cell selection `x_cell` and its capacity `T`.

    With `k`, the robust top-k set (ties by higher `sr`, then index; M-F7-05) and `T` its capacity. With `target_mw`, cells in ascending order of
    `z` until the capacity is reached, the last cell with a fraction; a target above the capacity of the ranked set is capped at it and flagged.

    Returns:
        `x_cell` over the F7 set, `T` in MW, and whether the target was above the capacity of the ranked set.

    Raises:
        H2Error: neither or both of `k` and `target_mw`, or a target of no capacity.
    """
    if (k is None) == (target_mw is None):
        raise H2Error("give the top-k size or the capacity target, not both")
    order = order_by(z, candidates=ranked, descending_tiebreak=sr)
    x = np.zeros(z.size)
    if k is not None:
        mask = take_top_k(order, k, z.size).mask
        x[mask] = 1.0
        return x, float(q[mask].sum()), False
    assert target_mw is not None
    q_max = float(q[order].sum())
    unreachable = target_mw > q_max
    target = min(target_mw, q_max)
    if target <= 0:
        raise H2Error("the capacity target has no capacity")
    cumulative = np.cumsum(q[order])
    at = min(
        int(np.searchsorted(cumulative, target - _TOLERANCE * q_max, side="left")), order.size - 1
    )
    x[order[:at]] = 1.0
    before = float(cumulative[at - 1]) if at > 0 else 0.0
    x[order[at]] = min(1.0, (target - before) / float(q[order[at]]))
    return x, target, unreachable


@dataclass(frozen=True)
class RegionRow:
    """One Admin1 region: its capacity, score statistics, the fraction the regional selection takes and the shares of `T` by procedure."""

    region: str
    n_cells: int
    capacity_mw: float
    mean_z: float
    median_z: float
    within_variance: float
    position: int
    fraction_taken: float
    selected_cell_mw: float
    selected_admin_mw: float
    share_cell: float
    share_admin: float


def _weighted_median(z: np.ndarray, w: np.ndarray) -> float:
    """The smallest value whose cumulative weight reaches half of the total (ties by order of appearance)."""
    order = np.argsort(z, kind="stable")
    cumulative = np.cumsum(w[order])
    return float(z[order][int(np.searchsorted(cumulative, 0.5 * cumulative[-1], side="left"))])


def select_regions(
    z: np.ndarray,
    q: np.ndarray,
    region: np.ndarray,
    ranked: np.ndarray,
    target_mw: float,
    x_cell: np.ndarray,
    *,
    statistic: str = MEAN,
) -> tuple[np.ndarray, list[RegionRow]]:
    """The regional selection `x_admin` and the table of regions.

    Regions are ranked by the capacity-weighted mean (or median) of `z`, ties by region identifier, and taken whole until `target_mw`; the last
    one enters with the fraction `y`, `0 < y <= 1`.

    Raises:
        H2Error: an unknown statistic, a target of no capacity or above the capacity of the ranked set, or no region with capacity.
    """
    if statistic not in (MEAN, MEDIAN):
        raise H2Error(f"unknown regional ranking statistic {statistic!r}")
    labels = sorted({str(r) for r in region[ranked]})
    stats = []
    for label in labels:
        cells = np.flatnonzero(ranked & (region.astype(str) == label))
        capacity = float(q[cells].sum())
        if capacity <= 0:
            continue
        mean = float((q[cells] * z[cells]).sum() / capacity)
        median = _weighted_median(z[cells], q[cells])
        variance = float((q[cells] * (z[cells] - mean) ** 2).sum() / capacity)
        stats.append(
            (mean if statistic == MEAN else median, label, cells, capacity, mean, median, variance)
        )
    if not stats:
        raise H2Error("no region has a ranked cell with capacity")
    q_max = sum(s[3] for s in stats)
    if target_mw <= 0 or target_mw > q_max * (1 + _TOLERANCE):
        raise H2Error(f"the target {target_mw} MW is not within (0, {q_max}] MW")
    stats.sort(key=lambda s: (s[0], s[1]))
    x_admin = np.zeros(z.size)
    fractions: dict[str, float] = {}
    taken = 0.0
    for key, label, cells, capacity, *_ in stats:
        remaining = target_mw - taken
        if remaining <= _TOLERANCE * q_max:
            fraction = 0.0
        elif remaining >= capacity * (1 - _TOLERANCE):
            fraction = 1.0
        else:
            fraction = remaining / capacity
        fractions[label] = fraction
        x_admin[cells] = fraction
        taken += fraction * capacity
    rows = []
    for position, (_, label, cells, capacity, mean, median, variance) in enumerate(stats, start=1):
        cell_mw = float((q[cells] * x_cell[cells]).sum())
        admin_mw = fractions[label] * capacity
        rows.append(
            RegionRow(
                region=label,
                n_cells=int(cells.size),
                capacity_mw=capacity,
                mean_z=mean,
                median_z=median,
                within_variance=variance,
                position=position,
                fraction_taken=fractions[label],
                selected_cell_mw=cell_mw,
                selected_admin_mw=admin_mw,
                share_cell=cell_mw / target_mw,
                share_admin=admin_mw / target_mw,
            )
        )
    return x_admin, rows


@dataclass(frozen=True)
class H2Variant:
    """The result of H2 for one setting (the primary one, a point of the decision profile or a sensitivity)."""

    variant: str
    top_k_percent: float | None
    k: int | None
    region_statistic: str
    excluded_gcms: tuple[str, ...]
    gamma: float
    n_ranked: int
    n_regions: int
    target_mw: float
    q_max_mw: float
    overlap: float
    overlap_ref: float
    testable: bool
    verdict: str
    robustness_penalty: float
    tv_distance: float
    iqr_over_median: float | None
    smallest_supporting_gamma: float | None
    target_unreachable: bool


@dataclass(frozen=True)
class H2Detail:
    """What the primary variant keeps beyond the numbers."""

    x_cell: np.ndarray
    x_admin: np.ndarray
    regions: tuple[RegionRow, ...]


def smallest_supporting_gamma(overlap: float, overlap_ref: float) -> float | None:
    """The smallest `gamma` of the decision profile under which H2 would be supported (`O < gamma` and `O_ref < gamma`), or None."""
    options = [g for g in GAMMA_PROFILE if overlap < g and overlap_ref < g]
    return min(options) if options else None


def evaluate_variant(
    inputs: H2Inputs,
    *,
    variant: str,
    gamma: float,
    k: int | None = None,
    top_k_percent: float | None = None,
    target_mw: float | None = None,
    statistic: str = MEAN,
    exclude_gcms: Sequence[str] = (),
) -> tuple[H2Variant, H2Detail]:
    """`O`, `O_ref`, the verdict and the diagnostics for one setting.

    Implements: M-F7-07 (H2).

    Args:
        k: Size of the robust top-k set whose capacity is the target (`top_k_percent` gives it from the size of the F7 set).
        target_mw: A national capacity target instead of a top-k set.

    Raises:
        H2Error: the ranked set is empty, no target is given, or a region/target problem (see `select_cells`, `select_regions`).
    """
    n_ranked = int(inputs.ranked.sum())
    if n_ranked == 0:
        raise H2Error("the ranked set is empty (every cell of the F7 set is climate-fragile)")
    z = scores_without(inputs, exclude_gcms) if exclude_gcms else inputs.z
    if top_k_percent is not None:
        k = top_k_size(top_k_percent, inputs.n_cells)
    # the robust order breaks ties by the satisficing robustness of all members, which cannot be recomputed without a GCM
    sr = None if exclude_gcms else inputs.sr
    x_cell, target, unreachable = select_cells(
        z, inputs.q, inputs.ranked, k=k if target_mw is None else None, target_mw=target_mw, sr=sr
    )
    x_admin, rows = select_regions(
        z, inputs.q, inputs.region, inputs.ranked, target, x_cell, statistic=statistic
    )
    q = inputs.q
    q_max = float(q[inputs.ranked].sum())
    overlap = float((q * np.minimum(x_cell, x_admin)).sum() / target)
    overlap_ref = target / q_max
    z0 = np.where(inputs.ranked, z, 0.0)
    penalty = float((q * x_admin * z0).sum() - (q * x_cell * z0).sum()) / target
    tv = 0.5 * sum(abs(r.share_cell - r.share_admin) for r in rows)
    scores = z[inputs.ranked]
    q25, median, q75 = np.quantile(scores, [0.25, 0.5, 0.75])
    verdict = verdict_of(overlap, overlap_ref, gamma)
    result = H2Variant(
        variant=variant,
        top_k_percent=top_k_percent,
        k=k if target_mw is None else None,
        region_statistic=statistic,
        excluded_gcms=tuple(sorted(exclude_gcms)),
        gamma=gamma,
        n_ranked=n_ranked,
        n_regions=len(rows),
        target_mw=target,
        q_max_mw=q_max,
        overlap=overlap,
        overlap_ref=overlap_ref,
        testable=verdict != NOT_TESTABLE,
        verdict=verdict,
        robustness_penalty=penalty,
        tv_distance=tv,
        iqr_over_median=float((q75 - q25) / median) if median > 0 else None,
        smallest_supporting_gamma=smallest_supporting_gamma(overlap, overlap_ref),
        target_unreachable=unreachable,
    )
    return result, H2Detail(x_cell=x_cell, x_admin=x_admin, regions=tuple(rows))


def decision_profile(primary: H2Variant) -> list[H2Variant]:
    """The verdict of the primary result for `gamma` from 0.10 to 0.70 in steps of 0.05 (`O` does not depend on `gamma`)."""
    return [
        dataclasses.replace(
            primary,
            variant=f"gamma_{g:.2f}",
            gamma=g,
            testable=primary.overlap_ref < g,
            verdict=verdict_of(primary.overlap, primary.overlap_ref, g),
        )
        for g in GAMMA_PROFILE
    ]


def sensitivity_variants(
    inputs: H2Inputs,
    primary: H2Variant,
    *,
    k: int,
    national_target_mw: float | None,
    tcr_exception_gcms: Sequence[str],
) -> list[H2Variant]:
    """The mandatory sensitivities that one run can give, after the decision profile.

    The decision profile, `T` for `p_k` in {5, 10, 20} percent and for the national capacity target (when there is one), regions ranked by the
    capacity-weighted median, and `z` without the TCR-exception GCM (omitted when no member carries it: the variant would equal the primary
    one). The 2071-2100 window and the 0.1 degree scale are separate runs of F7, each with its own primary row.
    """
    out = decision_profile(primary)
    gamma = primary.gamma
    for percent in SENSITIVITY_TOP_K_PERCENT:
        out.append(
            evaluate_variant(
                inputs, variant=f"top_k_percent_{percent:g}", gamma=gamma, top_k_percent=percent
            )[0]
        )
    if national_target_mw is not None:
        out.append(
            evaluate_variant(
                inputs, variant="national_target", gamma=gamma, target_mw=national_target_mw
            )[0]
        )
    out.append(
        evaluate_variant(inputs, variant="median_statistic", gamma=gamma, k=k, statistic=MEDIAN)[0]
    )
    present = sorted(set(tcr_exception_gcms) & set(inputs.gcms))
    if present:
        out.append(
            evaluate_variant(
                inputs,
                variant="without_" + "_".join(present),
                gamma=gamma,
                k=k,
                exclude_gcms=present,
            )[0]
        )
    return out
