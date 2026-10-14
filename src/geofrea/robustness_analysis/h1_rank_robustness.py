"""H1, climate robustness of the site ranking: the scores per SSP, `C_k`, `V_k`, the verdict and the sensitivities (M-F7-07; D-F7-035 to D-F7-038).

H1 asks two independent questions, each with one primary statistic fixed before any real result (OQ-050, H1):

  - H1a, core stability: `C_k = |intersection over the SSPs of S^sigma_k| / k`, the top-k by `MR_i,sigma` (the worst case over the GCMs of the P90
    over the draws, M-F7-03 restricted to one SSP); holds when `C_k >= alpha`. The reference value is `p_k^2` with `p_k = k / n`.
  - H1b, climate vulnerability: a nominal top-k cell is vulnerable when its rank by `R^clim_i,sigma` (the worst case over the GCMs of the
    relative regret at `s0`) is beyond `k + m` in at least one SSP; `V_k` is their share of `k`; holds when `V_k >= beta`.

The verdict is `supported` (both hold), `partially_supported` (one) or `not_supported` (neither). The descriptive metrics and the sensitivities
never change it. Everything here is a pure function of arrays over the F7 set, in `cell_id` order, so the position of a cell is its tie-break.
A climate-fragile cell has no rank (M-F7-05): it is not in any `S^sigma_k`, and if it is in the nominal top-k it is vulnerable (it leaves the
top-k in every comparison) with no displacement.

Nothing here accumulates an array over cells, members and draws: the inputs are the per-member P90 and the per-member regret at `s0`, both of
size cells x members (A-10).
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from geofrea.core.constants import SENSITIVITY_TOP_K_PERCENT
from geofrea.robustness_analysis.evaluator import Evaluation
from geofrea.robustness_analysis.rankings import (
    jaccard_masks,
    order_by,
    ranks_from_order,
    take_top_k,
    top_k_size,
)

SUPPORTED = "supported"
PARTIALLY_SUPPORTED = "partially_supported"
NOT_SUPPORTED = "not_supported"

PRIMARY = "primary"
SENSITIVITY_TOLERANCE_MULTIPLES = (0.5, 1.0, 2.0)  # m / k of the sensitivity


class H1Error(ValueError):
    """H1 cannot be computed from its inputs (A-09)."""


@dataclass(frozen=True)
class H1Inputs:
    """What H1 reads, over the F7 set in `cell_id` order and the `M` core members.

    Attributes:
        p90: `(n, M)` P90 over the draws `s >= 1` of the relative regret of each cell in each member (before the maximum over members).
        r_clim: `(n, M)` relative regret at `s0` of each cell in each member.
        ssps: SSP of each member.
        gcms: GCM of each member.
        ranked: Boolean over the F7 set: the cell is not climate-fragile.
        nominal_order: Indices of the F7 set by nominal LCOE (M-F7-05).
        nominal_rank: 1-based nominal rank of each cell of the F7 set.
    """

    p90: np.ndarray
    r_clim: np.ndarray
    ssps: tuple[str, ...]
    gcms: tuple[str, ...]
    ranked: np.ndarray
    nominal_order: np.ndarray
    nominal_rank: np.ndarray

    @property
    def n_cells(self) -> int:
        return int(self.ranked.size)


def climate_only_regret(evaluation: Evaluation) -> np.ndarray:
    """`(n, M)` relative regret at `s0` of each cell in each core member, with the finite worst case for an infeasible entry (M-F7-02).

    Its maximum over the members is `evaluation.mr_clim`.
    """
    lowest, highest = evaluation.lowest[1:, 0], evaluation.highest[1:, 0]
    nominal = evaluation.nominal_lcoe[:, 1:]
    with np.errstate(invalid="ignore", divide="ignore"):
        regret = nominal / lowest[None, :] - 1.0
        worst = (highest - lowest) / lowest
    return np.where(np.isfinite(nominal), regret, worst[None, :])


@dataclass(frozen=True)
class SspScores:
    """`MR_i,sigma` and `R^clim_i,sigma` per SSP (NaN for a cell without a rank), with the GCM that sets `R^clim`.

    Attributes:
        ssps: The SSPs, sorted.
        mr: `(S, n)`.
        r_clim: `(S, n)`.
        r_clim_gcm: `(S, n)` index into `gcms` of the GCM with the largest regret at `s0` in that SSP.
        gcms: The GCM names the index refers to.
    """

    ssps: tuple[str, ...]
    mr: np.ndarray
    r_clim: np.ndarray
    r_clim_gcm: np.ndarray
    gcms: tuple[str, ...]


def ssp_scores(inputs: H1Inputs, exclude_gcms: Sequence[str] = ()) -> SspScores:
    """The scores per SSP over the members whose GCM is not excluded.

    Implements: M-F7-07 (H1).

    Raises:
        H1Error: an SSP is left with no member.
    """
    keep = [j for j, g in enumerate(inputs.gcms) if g not in set(exclude_gcms)]
    ssps = tuple(sorted(set(inputs.ssps)))
    gcms = tuple(sorted({inputs.gcms[j] for j in keep}))
    n = inputs.n_cells
    mr = np.full((len(ssps), n), np.nan)
    r_clim = np.full((len(ssps), n), np.nan)
    who = np.zeros((len(ssps), n), dtype="int64")
    for s, ssp in enumerate(ssps):
        members = [j for j in keep if inputs.ssps[j] == ssp]
        if not members:
            raise H1Error(f"{ssp} has no member once {sorted(exclude_gcms)} are excluded")
        top = inputs.p90[:, members].max(axis=1)
        regret = inputs.r_clim[:, members]
        largest = regret.argmax(axis=1)
        mr[s] = np.where(inputs.ranked, top, np.nan)
        r_clim[s] = np.where(inputs.ranked, regret.max(axis=1), np.nan)
        who[s] = [gcms.index(inputs.gcms[members[a]]) for a in largest]
    return SspScores(ssps=ssps, mr=mr, r_clim=r_clim, r_clim_gcm=who, gcms=gcms)


def rbo(order_a: np.ndarray, order_b: np.ndarray, p: float) -> tuple[float, float]:
    """Rank-biased overlap of two rankings of the same set (Webber et al. 2010), the truncated finite estimator, and its residual.

    `RBO = (1 - p) * sum over d = 1..n of p^(d - 1) * A_d`, `A_d` the share of the first `d` positions common to both lists, summed over the
    whole length `n` (the lists are complete). It is a lower bound; the unseen weight is `p^n`, returned as the residual.

    Args:
        order_a: Cells in rank order (indices of the F7 set).
        order_b: The same cells in the other rank order.
        p: Persistence in `[0, 1)`.

    Raises:
        H1Error: the lists differ in cells or `p` is outside `[0, 1)`.
    """
    if not 0 <= p < 1:
        raise H1Error(f"RBO persistence {p} is outside [0, 1)")
    n = order_a.size
    if order_b.size != n or set(order_a.tolist()) != set(order_b.tolist()):
        raise H1Error("RBO needs two rankings of the same cells")
    if n == 0:
        return 1.0, 0.0
    size = int(max(order_a.max(), order_b.max())) + 1
    position_a, position_b = np.zeros(size, dtype="int64"), np.zeros(size, dtype="int64")
    position_a[order_a] = np.arange(n)
    position_b[order_b] = np.arange(n)
    entry = np.maximum(
        position_a[order_a], position_b[order_a]
    )  # depth (0-based) at which a cell is in both prefixes
    common = np.cumsum(np.bincount(entry, minlength=n))
    depth = np.arange(1, n + 1)
    weights = (1.0 - p) * np.power(p, depth - 1.0)
    return float((weights * common / depth).sum()), float(p**n)


@dataclass(frozen=True)
class H1Variant:
    """The result of H1 for one setting (the primary one or a sensitivity)."""

    variant: str
    top_k_percent: float
    k: int
    m: int
    excluded_gcms: tuple[str, ...]
    n_cells: int
    n_ranked: int
    n_ssps: int
    core_size: int
    n_vulnerable: int
    c_k: float
    v_k: float
    reference: float
    h1a_holds: bool
    h1b_holds: bool
    verdict: str


@dataclass(frozen=True)
class H1Detail:
    """What the primary variant keeps beyond the numbers: the ranks and top-k sets per SSP and the status of each nominal top-k cell."""

    scores: SspScores
    mr_order: tuple[np.ndarray, ...]
    mr_rank: np.ndarray  # (S, n) 0 where the cell has no rank
    clim_rank: np.ndarray  # (S, n)
    top_k: np.ndarray  # (S, n) boolean
    nominal_top: np.ndarray  # (n,) boolean
    vulnerable: np.ndarray  # (n,) boolean, within the nominal top-k
    displacement: (
        np.ndarray
    )  # (n,) float, NaN outside the nominal top-k and for a cell without a rank
    worst_ssp: np.ndarray  # (n,) index into scores.ssps, -1 where undefined
    worst_gcm: (
        np.ndarray
    )  # (n,) index into scores.gcms of the GCM responsible in the worst SSP, -1 where undefined
    max_r_clim: np.ndarray  # (n,) largest R^clim over the SSPs, NaN where undefined


def verdict_of(h1a: bool, h1b: bool) -> str:
    """supported (both), partially supported (exactly one), not supported (neither)."""
    return SUPPORTED if h1a and h1b else PARTIALLY_SUPPORTED if h1a or h1b else NOT_SUPPORTED


def tolerance_size(multiple: float, k: int) -> int:
    """`m = ceil(multiple * k)`, at least 1."""
    return max(1, math.ceil(multiple * k))


def evaluate_variant(
    inputs: H1Inputs,
    *,
    variant: str,
    top_k_percent: float,
    tolerance_multiple: float,
    alpha: float,
    beta: float,
    exclude_gcms: Sequence[str] = (),
) -> tuple[H1Variant, H1Detail]:
    """`C_k`, `V_k` and the verdict for one setting.

    Implements: M-F7-07 (H1).

    Raises:
        H1Error: the ranked set is empty, or an SSP has no member left.
    """
    n = inputs.n_cells
    n_ranked = int(inputs.ranked.sum())
    if n_ranked == 0:
        raise H1Error("the ranked set is empty (every cell of the F7 set is climate-fragile)")
    scores = ssp_scores(inputs, exclude_gcms)
    n_ssps = len(scores.ssps)
    if n_ssps < 2:
        raise H1Error(f"H1 compares SSPs and the members carry {n_ssps}")
    k = top_k_size(top_k_percent, n)
    m = tolerance_size(tolerance_multiple, k)
    mr_order = tuple(order_by(scores.mr[s], candidates=inputs.ranked) for s in range(n_ssps))
    clim_order = tuple(order_by(scores.r_clim[s], candidates=inputs.ranked) for s in range(n_ssps))
    mr_rank = np.stack([ranks_from_order(o, n) for o in mr_order])
    clim_rank = np.stack([ranks_from_order(o, n) for o in clim_order])
    top_k = np.stack([take_top_k(o, k, n).mask for o in mr_order])
    nominal_top = take_top_k(inputs.nominal_order, k, n).mask

    core = top_k.all(axis=0)
    c_k = float(core.sum()) / k
    beyond = (clim_rank == 0) | (clim_rank > k + m)  # no rank (climate-fragile) counts as beyond
    vulnerable = nominal_top & beyond.any(axis=0)
    v_k = float(vulnerable.sum()) / k

    gap = clim_rank - inputs.nominal_rank[None, :]
    gap = np.where(clim_rank > 0, gap, -np.iinfo("int64").max).astype("float64")
    has_rank = (clim_rank > 0).all(axis=0)
    displacement = np.where(nominal_top & has_rank, gap.max(axis=0), np.nan)
    worst_ssp = np.where(nominal_top & has_rank, gap.argmax(axis=0), -1)
    at = np.arange(n)
    worst_gcm = np.where(worst_ssp >= 0, scores.r_clim_gcm[np.maximum(worst_ssp, 0), at], -1)
    max_r = np.where(
        nominal_top & has_rank,
        np.nanmax(np.where(np.isnan(scores.r_clim), -np.inf, scores.r_clim), axis=0),
        np.nan,
    )

    h1a, h1b = c_k >= alpha, v_k >= beta
    result = H1Variant(
        variant=variant,
        top_k_percent=top_k_percent,
        k=k,
        m=m,
        excluded_gcms=tuple(sorted(exclude_gcms)),
        n_cells=n,
        n_ranked=n_ranked,
        n_ssps=n_ssps,
        core_size=int(core.sum()),
        n_vulnerable=int(vulnerable.sum()),
        c_k=c_k,
        v_k=v_k,
        reference=(k / n) ** 2,
        h1a_holds=bool(h1a),
        h1b_holds=bool(h1b),
        verdict=verdict_of(bool(h1a), bool(h1b)),
    )
    detail = H1Detail(
        scores=scores,
        mr_order=mr_order,
        mr_rank=mr_rank,
        clim_rank=clim_rank,
        top_k=top_k,
        nominal_top=nominal_top,
        vulnerable=vulnerable,
        displacement=displacement,
        worst_ssp=worst_ssp.astype("int64"),
        worst_gcm=worst_gcm.astype("int64"),
        max_r_clim=max_r,
    )
    return result, detail


def sensitivity_variants(
    inputs: H1Inputs,
    *,
    top_k_percent: float,
    tolerance_multiple: float,
    alpha: float,
    beta: float,
    tcr_exception_gcms: Sequence[str],
) -> list[H1Variant]:
    """The mandatory sensitivities that one run can give: without the TCR-exception GCM, `p_k` in {5, 10, 20} %, `m` in {k/2, k, 2k}.

    The 2071-2100 window and the 0.1 degree scale are separate runs of F7 (the sensitivity-window tables and the other scale), each with its
    own primary row. A GCM of `tcr_exception_gcms` that is not in the members is skipped: the variant would equal the primary one.
    """
    common = {"alpha": alpha, "beta": beta}
    out: list[H1Variant] = []
    present = sorted(set(tcr_exception_gcms) & set(inputs.gcms))
    if present:
        out.append(
            evaluate_variant(
                inputs,
                variant="without_" + "_".join(present),
                top_k_percent=top_k_percent,
                tolerance_multiple=tolerance_multiple,
                exclude_gcms=present,
                **common,
            )[0]
        )
    for percent in SENSITIVITY_TOP_K_PERCENT:
        out.append(
            evaluate_variant(
                inputs,
                variant=f"top_k_percent_{percent:g}",
                top_k_percent=percent,
                tolerance_multiple=tolerance_multiple,
                **common,
            )[0]
        )
    for multiple in SENSITIVITY_TOLERANCE_MULTIPLES:
        out.append(
            evaluate_variant(
                inputs,
                variant=f"tolerance_{multiple:g}k",
                top_k_percent=top_k_percent,
                tolerance_multiple=multiple,
                **common,
            )[0]
        )
    return out


@dataclass(frozen=True)
class H1Descriptive:
    """Descriptive evidence of H1 (no verdict): per SSP pair, Jaccard and RBO; over the nominal top-k, displacement and rank dispersion."""

    pairs: tuple[
        tuple[str, str, float, float, float], ...
    ]  # (ssp_a, ssp_b, jaccard, rbo, rbo_residual)
    rbo_p: float
    median_rank_across_ssps: float | None
    ssp_rank_iqr_median: float | None
    displacement_median: float | None
    displacement_iqr: float | None
    n_sites_with_rank: int


def descriptive(inputs: H1Inputs, primary: H1Variant, detail: H1Detail) -> H1Descriptive:
    """Pairwise Jaccard of the SSP top-k sets, RBO with `p = 1 - 1/k`, and the rank dispersion of the nominal top-k across SSPs.

    Implements: M-F7-07 (H1, descriptive evidence).

    The rank of a cell in an SSP is its position by `MR_i,sigma`; the displacement is the worst rank by `R^clim` minus the nominal rank
    (the quantity of the magnitude of H1b). A nominal top-k cell without a rank is left out of the dispersion and counted.
    """
    p = 1.0 - 1.0 / primary.k
    ssps = detail.scores.ssps
    pairs = []
    for a, b in itertools.combinations(range(len(ssps)), 2):
        value, residual = rbo(detail.mr_order[a], detail.mr_order[b], p)
        pairs.append(
            (ssps[a], ssps[b], jaccard_masks(detail.top_k[a], detail.top_k[b]), value, residual)
        )
    sites = detail.nominal_top & (detail.mr_rank > 0).all(axis=0)
    if not sites.any():
        return H1Descriptive(tuple(pairs), p, None, None, None, None, 0)
    ranks = detail.mr_rank[:, sites].astype("float64")  # (S, sites)
    q25, q75 = np.percentile(ranks, [25, 75], axis=0)
    shifts = detail.displacement[sites]
    shifts = shifts[np.isfinite(shifts)]
    d25, d75 = np.percentile(shifts, [25, 75]) if shifts.size else (np.nan, np.nan)
    return H1Descriptive(
        pairs=tuple(pairs),
        rbo_p=p,
        median_rank_across_ssps=float(np.median(np.median(ranks, axis=0))),
        ssp_rank_iqr_median=float(np.median(q75 - q25)),
        displacement_median=float(np.median(shifts)) if shifts.size else None,
        displacement_iqr=float(d75 - d25) if shifts.size else None,
        n_sites_with_rank=int(sites.sum()),
    )
