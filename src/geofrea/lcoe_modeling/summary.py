"""Exact summaries of the LCOE draws of a block of cells (M-F6-04; D-F6-002, D-F6-003, D-F6-007).

A block holds every draw of its cells, so the quantiles are exact (no streaming estimator). The quantile is the linear interpolation
of the order statistics (Hyndman-Fan type 7, the NumPy default), computed here from a partition so that `+inf` draws (zero energy)
give an infinite quantile instead of the NaN a subtraction `inf - inf` would produce. The mean and the variance (`ddof = 1`) run over
the finite draws; a count of the others is returned.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

QUANTILES = (0.1, 0.5, 0.9)
_SLABS = 8  # the mean and the variance read the block in this many column slabs, so their temporaries are an eighth of a block


class SummaryError(ValueError):
    """A block cannot be summarized (A-09)."""


@dataclass(frozen=True)
class BlockSummary:
    """Statistics of each row (cell) of a block of draws, arrays of shape `(C,)`."""

    mean: np.ndarray
    var: np.ndarray
    p10: np.ndarray
    p50: np.ndarray
    p90: np.ndarray
    n_nonfinite: np.ndarray


def _lerp(lower: np.ndarray, upper: np.ndarray, t: float) -> np.ndarray:
    """`lower + (upper - lower) * t` as NumPy computes a linear quantile, with an infinite `upper` giving `upper`."""
    if t == 0.0:
        return lower.copy()
    with np.errstate(invalid="ignore"):
        gap = upper - lower
        value = lower + gap * t if t < 0.5 else upper - gap * (1.0 - t)
    return np.where(np.isinf(upper), upper, value)


def quantiles_of_rows(draws: np.ndarray, qs: tuple[float, ...]) -> list[np.ndarray]:
    """The quantiles `qs` of every row of `draws`, shape `(C, N)`, by linear interpolation of the order statistics (type 7).

    The entries of each row are reordered in place (a partition). `+inf` entries give an infinite quantile, never NaN.
    """
    n = draws.shape[1]
    positions = [(n - 1) * q for q in qs]
    kth = sorted({int(np.floor(h)) for h in positions} | {int(np.ceil(h)) for h in positions})
    draws.partition(kth, axis=1)
    out = []
    for h in positions:
        lo, hi = int(np.floor(h)), int(np.ceil(h))
        out.append(_lerp(draws[:, lo], draws[:, hi], h - lo))
    return out


def summarize_draws(draws: np.ndarray) -> BlockSummary:
    """Mean, variance, p10, p50, p90 and the count of non-finite draws of every row of `draws`, shape `(C, N)` with `N >= 2`.

    Implements: M-F6-04.

    The entries of each row are reordered in place (a partition), so `draws` is not meaningful afterwards; this is what keeps the
    summary within the memory of the block it was handed.

    Raises:
        SummaryError: fewer than two draws, an array that is not 2-D float64, or a NaN among the draws.
    """
    if draws.ndim != 2 or draws.dtype != np.float64:
        raise SummaryError("draws must be a 2-D float64 array")
    n_cells, n = draws.shape
    if n < 2:
        raise SummaryError("at least two draws are needed for a variance")
    finite_count = np.empty(n_cells, dtype="int64")
    total = np.zeros(n_cells)
    width = max(1, -(-n // _SLABS))
    starts = range(0, n, width)
    finite_count[:] = 0
    for j in starts:
        slab = draws[:, j : j + width]
        if np.isnan(slab).any():
            raise SummaryError("a NaN LCOE reached the summary (A-09)")
        ok = np.isfinite(slab)
        finite_count += ok.sum(axis=1)
        total += np.where(ok, slab, 0.0).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(finite_count > 0, total / finite_count, np.nan)
    squares = np.zeros(n_cells)
    centre = np.where(np.isfinite(mean), mean, 0.0)[:, None]
    for j in starts:
        slab = draws[:, j : j + width]
        deviation = np.where(np.isfinite(slab), slab - centre, 0.0)
        squares += np.einsum("ij,ij->i", deviation, deviation)
    with np.errstate(invalid="ignore", divide="ignore"):
        var = np.where(finite_count >= 2, squares / (finite_count - 1), np.nan)

    out = quantiles_of_rows(draws, QUANTILES)
    return BlockSummary(
        mean=mean,
        var=var,
        p10=out[0],
        p50=out[1],
        p90=out[2],
        n_nonfinite=(n - finite_count).astype("int64"),
    )
