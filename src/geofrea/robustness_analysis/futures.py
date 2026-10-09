"""Pass 3 of F7: what compares members within one future (H1, H3, the PRIM outcome, the ranges over the draws; D-F7-008, D-F7-015).

Passes 1 and 2 go member by member and cannot say how the rankings of two members differ inside the same parameter draw. This pass is
sample-major: for a batch of draws it evaluates the LCOE of every core member over the F7 set, ranks the cells of each member (positions of
the ranking of M-F7-05: ascending LCOE, ties by index, an infeasible cell last), and reduces to a few numbers per future and per draw:

  - the share of the nominal top-k cells that are outside the top-k of the future, and the Jaccard of the two sets (PRIM outcome, H3);
  - Spearman correlation of the rankings, and Jaccard of the top-k sets, between SSPs of the same GCM and between the per-SSP medians over
    the GCMs (H1), and the share of the nominal top-k cells that leave the top-k under at least one member (H1).

Column 0 of the samples is the nominal vector `s0`: its values are the central values of the statistics. No array over cells, members and
draws is kept: a batch of draws is evaluated, reduced and released.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from geofrea.lcoe_modeling.kernel import SampleInputs, lcoe_block
from geofrea.robustness_analysis.evaluator import MemberWorld

LIVE_FACTOR = 3  # kernel blocks alive beside the stack of members while one batch is evaluated


class FuturesError(ValueError):
    """The sample-major pass cannot run on its inputs (A-09)."""


def slug(label: str) -> str:
    """A label as it appears in a statistic identifier: lower case, runs of other characters as one underscore."""
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


@dataclass(frozen=True)
class MemberLabel:
    """The GCM and SSP of a core member (`members.yaml`)."""

    member: str
    gcm: str
    ssp: str


@dataclass(frozen=True)
class FuturesResult:
    """Per future `(m, s)` and per draw `s` reductions; sample 0 is the nominal vector.

    Attributes:
        members: The core members, in order.
        share_leaving: `(M, N + 1)` share of the nominal top-k cells that are outside the top-k of the future.
        jaccard_nominal: `(M, N + 1)` Jaccard of the nominal top-k and the top-k of the future.
        draw_statistics: statistic identifier -> `(N + 1,)` value for each draw (H1 and the any-member share).
    """

    members: tuple[str, ...]
    share_leaving: np.ndarray
    jaccard_nominal: np.ndarray
    draw_statistics: dict[str, np.ndarray]


def batch_size(n_cells: int, n_members: int, max_batch_gb: float) -> int:
    """Draws per batch so that the stack of members plus the kernel blocks fit in `max_batch_gb` (A-10)."""
    if max_batch_gb <= 0:
        raise FuturesError("memory.max_batch_gb must be positive")
    return max(1, int(max_batch_gb * 1.0e9 // (8 * n_cells * (n_members + LIVE_FACTOR))))


def _positions(values: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Rank positions (0-based, ties by index, infinite last) and the boolean top-k mask of one future."""
    order = np.argsort(values, kind="stable")
    position = np.empty(values.size, dtype="float64")
    position[order] = np.arange(values.size)
    finite = int(np.isfinite(values).sum())
    top = np.zeros(values.size, dtype=bool)
    top[order[: min(k, finite)]] = True
    return position, top


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation of two rank vectors (Spearman's rho for ranks without ties)."""
    da, db = a - a.mean(), b - b.mean()
    denominator = float(np.sqrt((da @ da) * (db @ db)))
    return float(da @ db) / denominator if denominator > 0 else float("nan")


def _jaccard(a: np.ndarray, b: np.ndarray) -> float:
    union = int((a | b).sum())
    return float((a & b).sum()) / union if union else 1.0


def futures_pass(
    worlds: Sequence[MemberWorld],
    labels: Sequence[MemberLabel],
    samples: SampleInputs,
    nominal_top_k: np.ndarray,
    k: int,
    *,
    max_batch_gb: float,
    progress: Callable[[], None] | None = None,
) -> FuturesResult:
    """Evaluate every core member for every draw and reduce to the statistics of H1, H3 and the PRIM outcome.

    Implements: M-F7-07 (H1, H3), M-F7-08, M-F7-10.

    Args:
        worlds: The core members over the F7 set.
        labels: GCM and SSP of each member, in the same order.
        samples: Column 0 is `s0`.
        nominal_top_k: Boolean mask over the F7 set: the top-k at `f0`.
        k: The size of the top-k (M-F7-05).
        max_batch_gb: The memory budget.
        progress: Called once per batch.

    Raises:
        FuturesError: the members and labels disagree, or the nominal top-k is empty.
    """
    if len(worlds) != len(labels) or not worlds:
        raise FuturesError("one label per core member is needed")
    n_cells, n_members, n_samples = len(worlds[0].cells), len(worlds), len(samples)
    nominal_top_k = np.asarray(nominal_top_k, dtype=bool)
    nominal_size = int(nominal_top_k.sum())
    if nominal_size == 0:
        raise FuturesError("the nominal top-k is empty")
    by_gcm: dict[str, dict[str, int]] = {}
    by_ssp: dict[str, list[int]] = {}
    for j, label in enumerate(labels):
        by_gcm.setdefault(label.gcm, {})[label.ssp] = j
        by_ssp.setdefault(label.ssp, []).append(j)
    ssps = sorted(by_ssp)
    ssp_pairs = list(itertools.combinations(ssps, 2))
    share = np.empty((n_members, n_samples))
    jaccard_nominal = np.empty((n_members, n_samples))
    stats: dict[str, np.ndarray] = {"h1_leaving_any_member_share": np.empty(n_samples)}
    for gcm in sorted(by_gcm):
        for a, b in ssp_pairs:
            if a in by_gcm[gcm] and b in by_gcm[gcm]:
                stats[f"h1_spearman_gcm__{slug(gcm)}__{slug(a)}_vs_{slug(b)}"] = np.empty(n_samples)
                stats[f"h1_jaccard_gcm__{slug(gcm)}__{slug(a)}_vs_{slug(b)}"] = np.empty(n_samples)
    for a, b in ssp_pairs:
        stats[f"h1_spearman_median__{slug(a)}_vs_{slug(b)}"] = np.empty(n_samples)
        stats[f"h1_jaccard_median__{slug(a)}_vs_{slug(b)}"] = np.empty(n_samples)

    width = batch_size(n_cells, n_members, max_batch_gb)
    for start in range(0, n_samples, width):
        window = slice(start, min(start + width, n_samples))
        batch = samples.take(window)
        stack = np.empty((n_members, n_cells, len(batch)))
        for j, world in enumerate(worlds):
            stack[j] = lcoe_block(world.cells, batch, min_energy_mwh=world.floor)
        for column in range(len(batch)):
            s = start + column
            position = np.empty((n_members, n_cells))
            top = np.empty((n_members, n_cells), dtype=bool)
            for j in range(n_members):
                position[j], top[j] = _positions(stack[j, :, column], k)
            leaving = nominal_top_k[None, :] & ~top
            share[:, s] = leaving.sum(axis=1) / nominal_size
            for j in range(n_members):
                jaccard_nominal[j, s] = _jaccard(nominal_top_k, top[j])
            stats["h1_leaving_any_member_share"][s] = leaving.any(axis=0).sum() / nominal_size
            for gcm, members in by_gcm.items():
                for a, b in ssp_pairs:
                    if a in members and b in members:
                        ia, ib = members[a], members[b]
                        stats[f"h1_spearman_gcm__{slug(gcm)}__{slug(a)}_vs_{slug(b)}"][s] = (
                            _spearman(position[ia], position[ib])
                        )
                        stats[f"h1_jaccard_gcm__{slug(gcm)}__{slug(a)}_vs_{slug(b)}"][s] = _jaccard(
                            top[ia], top[ib]
                        )
            median_pos, median_top = {}, {}
            for ssp, indices in by_ssp.items():
                median_pos[ssp], median_top[ssp] = _positions(
                    np.median(stack[indices, :, column], axis=0), k
                )
            for a, b in ssp_pairs:
                stats[f"h1_spearman_median__{slug(a)}_vs_{slug(b)}"][s] = _spearman(
                    median_pos[a], median_pos[b]
                )
                stats[f"h1_jaccard_median__{slug(a)}_vs_{slug(b)}"][s] = _jaccard(
                    median_top[a], median_top[b]
                )
        del stack
        if progress is not None:
            progress()
    return FuturesResult(
        members=tuple(w.member for w in worlds),
        share_leaving=share,
        jaccard_nominal=jaccard_nominal,
        draw_statistics=stats,
    )
