"""Rankings, top-k sets and the capacity-target reading (M-F7-05; D-F7-012, D-F7-013).

Ties are exact equality of the float, then the next key, and finally ascending `cell_id` (A-12). No tolerance is introduced. All functions
work on arrays over the F7 set, in `cell_id` order, so the index of a cell is also its tie-break position.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


class RankingError(ValueError):
    """A ranking cannot be built from its inputs (A-09)."""


def top_k_size(top_k_percent: float, n_cells: int) -> int:
    """`k = ceil(p_k / 100 * n)`, at least 1 (M-F7-05).

    Raises:
        RankingError: `p_k` outside `(0, 100]` or no cell.
    """
    if not 0 < top_k_percent <= 100:
        raise RankingError(f"top_k_percent {top_k_percent} is outside (0, 100]")
    if n_cells < 1:
        raise RankingError("the F7 set is empty")
    return max(1, math.ceil(top_k_percent / 100.0 * n_cells))


def order_by(
    primary: np.ndarray,
    *,
    candidates: np.ndarray | None = None,
    descending_tiebreak: np.ndarray | None = None,
) -> np.ndarray:
    """Indices that sort `primary` ascending, ties broken by `descending_tiebreak` (higher first), then by index.

    Args:
        primary: The key, ascending; NaN is not allowed among the `candidates`.
        candidates: Boolean mask of the entries to order (default all); the others are left out of the result.
        descending_tiebreak: Second key, higher first (the satisficing robustness `SR`).

    Raises:
        RankingError: a NaN key among the candidates.
    """
    index = np.arange(primary.size) if candidates is None else np.flatnonzero(candidates)
    keys = primary[index]
    if np.isnan(keys).any():
        raise RankingError("a NaN key among the cells to rank")
    sort_keys: list[np.ndarray] = [index]
    if descending_tiebreak is not None:
        sort_keys.append(-descending_tiebreak[index])
    sort_keys.append(keys)
    return index[np.lexsort(tuple(sort_keys))]


def ranks_from_order(order: np.ndarray, size: int) -> np.ndarray:
    """1-based rank of every entry (0 for an entry that is not in `order`), as an int64 array of length `size`."""
    rank = np.zeros(size, dtype="int64")
    rank[order] = np.arange(1, order.size + 1)
    return rank


@dataclass(frozen=True)
class TopK:
    """A top-k set over the F7 set.

    Attributes:
        mask: Boolean over the F7 set.
        k: The size asked for (M-F7-05).
        size: The cells actually taken (smaller than `k` when the ranked set is).
        truncated: `size < k`.
    """

    mask: np.ndarray
    k: int
    size: int
    truncated: bool


def take_top_k(order: np.ndarray, k: int, n_cells: int) -> TopK:
    """The first `k` cells of `order` (all of them when there are fewer): flag `truncated` then."""
    taken = order[:k]
    mask = np.zeros(n_cells, dtype=bool)
    mask[taken] = True
    return TopK(mask=mask, k=k, size=int(taken.size), truncated=bool(taken.size < k))


def capacity_target_set(
    order: np.ndarray, p_mw: np.ndarray, target_gw: float
) -> tuple[np.ndarray, bool]:
    """The fewest cells along `order` whose capacity reaches `target_gw`; `reached` is False when all of them do not.

    Implements: M-F7-05 (strategy-level reading, OQ-010).

    Returns:
        The boolean mask over the F7 set and whether the target was reached (False: all cells of `order` were taken,
        `target_unreachable`).

    Raises:
        RankingError: a negative target.
    """
    if target_gw < 0:
        raise RankingError("the capacity target is negative")
    mask = np.zeros(p_mw.size, dtype=bool)
    if target_gw == 0:
        return mask, True
    cumulative = np.cumsum(p_mw[order]) / 1000.0
    if order.size == 0 or cumulative[-1] < target_gw:
        mask[order] = True
        return mask, False
    count = int(np.searchsorted(cumulative, target_gw, side="left")) + 1
    mask[order[:count]] = True
    return mask, True


def jaccard_masks(a: np.ndarray, b: np.ndarray) -> float:
    """`|A and B| / |A or B|` of two boolean masks; 1 for two empty sets."""
    union = int((a | b).sum())
    return float((a & b).sum()) / union if union else 1.0
