"""H3, robust versus nominal site selection: the two shortlists, `D`, `D_ref`, the verdict, the price and benefit of robustness, the
diagnostics and the sensitivities (M-F7-07; D-F7-043 to D-F7-045).

H3 asks whether planning for robustness changes where capacity would be built. Both rankings are over the ranked set `I` (the cells that
are not climate-fragile), so that a difference between them reflects the criterion and not the candidate set:

  - the robust shortlist `S_k` is the `k` cells with the lowest `z_i = MR_i` (ties by higher `SR`, then index; M-F7-05), the same set as the
    target of H2;
  - the nominal rank `r^nom_i` is the rank of the cell within `I` by `LCOE_i,f0`, and the nominal shortlist `S^nom_k` is its first `k` cells.

`D` is the share of the capacity of `S_k` in cells with `r^nom_i > k + m`; a cell of `S_k` ranked from `k + 1` to `k + m` is not counted.
`D_ref = 1 - (k + m) / |I|` is the expected `D` for unrelated rankings. The verdict (OQ-050, H3) is `not_testable` when `D_ref < delta`,
`supported` when `D >= delta` and `not_supported` when `D < delta`. The price `Pi` and the benefit `B` of robustness, the diagnostics and the
sensitivities never change it.

Everything is a pure function of arrays over the F7 set in `cell_id` order, so the position of a cell is its tie-break.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from pyproj import Geod
from scipy.stats import rankdata

from geofrea.robustness_analysis.h1_rank_robustness import tolerance_size
from geofrea.robustness_analysis.h2_aggregation import NOT_SUPPORTED, NOT_TESTABLE, SUPPORTED
from geofrea.robustness_analysis.rankings import (
    jaccard_masks,
    order_by,
    ranks_from_order,
    take_top_k,
    top_k_size,
)

__all__ = [
    "NOT_SUPPORTED",
    "NOT_TESTABLE",
    "SUPPORTED",
    "H3Detail",
    "H3Error",
    "H3Inputs",
    "H3Variant",
    "centroid_distance_km",
    "evaluate_variant",
    "sensitivity_variants",
    "verdict_of",
]

PRIMARY = "primary"
SENSITIVITY_TOP_K_PERCENT = (5.0, 10.0, 20.0)  # p_k of the sensitivity (METHODOLOGY M-F7-07, H3)
SENSITIVITY_TOLERANCE_MULTIPLES = (0.5, 2.0)  # m in {k/2, 2k} (the primary one is m = k)
_GEOD = Geod(ellps="WGS84")


class H3Error(ValueError):
    """H3 cannot be computed from its inputs (A-09)."""


@dataclass(frozen=True)
class H3Inputs:
    """What H3 reads, over the F7 set in `cell_id` order and the `M` core members.

    Attributes:
        cell_id: `(n,)` identifier of each cell.
        z: `(n,)` the robustness score `MR_i` (NaN for a cell without one).
        lcoe: `(n,)` the levelised cost `LCOE_i,f0` of the reference climate at the nominal parameters.
        q: `(n,)` installable capacity of the central land scenario, MW.
        region: `(n,)` Admin1 identifier of each cell.
        lat: `(n,)` latitude of the cell centre.
        lon: `(n,)` longitude of the cell centre.
        ranked: Boolean over the F7 set: the cell is not climate-fragile (the set `I`).
        sr: `(n,)` satisficing robustness for the tie-break of the robust order, or None.
        p90: `(n, M)` P90 over the draws of the relative regret in each member (to recompute `z` without a GCM).
        gcms: GCM of each member.
    """

    cell_id: np.ndarray
    z: np.ndarray
    lcoe: np.ndarray
    q: np.ndarray
    region: np.ndarray
    lat: np.ndarray
    lon: np.ndarray
    ranked: np.ndarray
    sr: np.ndarray | None
    p90: np.ndarray
    gcms: tuple[str, ...]

    @property
    def n_cells(self) -> int:
        return int(self.ranked.size)


def verdict_of(d: float, d_ref: float, delta: float) -> str:
    """not testable (`D_ref < delta`), supported (`D >= delta`) or not supported (`D < delta`)."""
    if d_ref < delta:
        return NOT_TESTABLE
    return SUPPORTED if d >= delta else NOT_SUPPORTED


def scores_without(inputs: H3Inputs, exclude_gcms: Sequence[str]) -> np.ndarray:
    """`z` recomputed as the maximum over the members whose GCM is not excluded (NaN where the cell is not ranked).

    Raises:
        H3Error: no member is left.
    """
    keep = [j for j, g in enumerate(inputs.gcms) if g not in set(exclude_gcms)]
    if not keep:
        raise H3Error(f"no member is left once {sorted(exclude_gcms)} are excluded")
    return np.where(inputs.ranked, inputs.p90[:, keep].max(axis=1), np.nan)


def centroid_distance_km(
    lat: np.ndarray, lon: np.ndarray, weight: np.ndarray, first: np.ndarray, second: np.ndarray
) -> float | None:
    """Geodesic distance (WGS84, km) between the capacity-weighted centroids of two sets of cells; None if one set has no capacity."""
    points = []
    for mask in (first, second):
        w = weight[mask]
        if not mask.any() or w.sum() <= 0:
            return None
        points.append(((w * lat[mask]).sum() / w.sum(), (w * lon[mask]).sum() / w.sum()))
    (lat1, lon1), (lat2, lon2) = points
    return float(_GEOD.inv(lon1, lat1, lon2, lat2)[2] / 1000.0)


def _weighted_mean(values: np.ndarray, q: np.ndarray, mask: np.ndarray) -> float | None:
    """`sum(q X) / sum(q)` over `mask`, or None when the set has no capacity."""
    capacity = float(q[mask].sum())
    return float((q[mask] * values[mask]).sum() / capacity) if capacity > 0 else None


def _spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    """Spearman's rank correlation (average ranks for ties), or None when one variable is constant or there are fewer than two cells."""
    if a.size < 2 or np.ptp(a) == 0 or np.ptp(b) == 0:
        return None
    return float(np.corrcoef(rankdata(a), rankdata(b))[0, 1])


def _total_variation(
    q: np.ndarray, region: np.ndarray, first: np.ndarray, second: np.ndarray
) -> float:
    """`0.5 * sum over regions of |P_first - P_second|`, `P` the share of the capacity of each set that lies in the region."""
    labels = region.astype(str)
    distance = 0.0
    shares = []
    for mask in (first, second):
        total = float(q[mask].sum())
        shares.append({r: float(q[mask & (labels == r)].sum()) / total for r in set(labels[mask])})
    for r in set(shares[0]) | set(shares[1]):
        distance += abs(shares[0].get(r, 0.0) - shares[1].get(r, 0.0))
    return 0.5 * distance


@dataclass(frozen=True)
class H3Variant:
    """The result of H3 for one setting (the primary one or a sensitivity)."""

    variant: str
    top_k_percent: float | None
    k: int
    m: int
    tolerance_multiple: float
    excluded_gcms: tuple[str, ...]
    delta: float
    n_cells: int
    n_ranked: int
    top_k_truncated: bool
    robust_capacity_mw: float
    nominal_capacity_mw: float
    outside_capacity_mw: float
    n_outside: int
    d: float
    d_ref: float
    testable: bool
    verdict: str
    robust_lcoe_mean: float | None
    nominal_lcoe_mean: float | None
    robust_mr_mean: float | None
    nominal_mr_mean: float | None
    price_of_robustness: float | None
    benefit_of_robustness: float | None
    centroid_distance_km: float | None
    tv_distance: float | None
    spearman_lcoe_mr: float | None
    jaccard: float


@dataclass(frozen=True)
class H3Detail:
    """What the primary variant keeps beyond the numbers, over the F7 set."""

    robust: np.ndarray  # bool: the cell is in `S_k`
    nominal: np.ndarray  # bool: the cell is in `S^nom_k`
    robust_rank: np.ndarray  # int64: rank within I by MR (0 outside I)
    nominal_rank: np.ndarray  # int64: rank within I by LCOE at f0 (0 outside I)
    beyond: np.ndarray  # bool: in `S_k` with `r^nom > k + m` (its capacity counts in D)
    within_tolerance: np.ndarray  # bool: in `S_k` with `k < r^nom <= k + m` (not counted)
    z: np.ndarray


def evaluate_variant(
    inputs: H3Inputs,
    *,
    variant: str,
    delta: float,
    tolerance_multiple: float,
    top_k_percent: float,
    exclude_gcms: Sequence[str] = (),
) -> tuple[H3Variant, H3Detail]:
    """`D`, `D_ref`, the verdict, `Pi`, `B` and the diagnostics for one setting.

    Implements: M-F7-07 (H3).

    Args:
        top_k_percent: `p_k` in percent; `k = ceil(p_k / 100 * n)` with `n` the size of the F7 set (M-F7-05).
        tolerance_multiple: `m / k`; `m = ceil(multiple * k)`, at least 1 (as in H1).

    Raises:
        H3Error: the ranked set is empty, the robust shortlist has no capacity, or no member is left without the excluded GCMs.
    """
    n = inputs.n_cells
    n_ranked = int(inputs.ranked.sum())
    if n_ranked == 0:
        raise H3Error("the ranked set is empty (every cell of the F7 set is climate-fragile)")
    z = scores_without(inputs, exclude_gcms) if exclude_gcms else inputs.z
    k = top_k_size(top_k_percent, n)
    m = tolerance_size(tolerance_multiple, k)
    # the robust order breaks ties by the satisficing robustness of all members, which cannot be recomputed without a GCM
    sr = None if exclude_gcms else inputs.sr
    robust_order = order_by(z, candidates=inputs.ranked, descending_tiebreak=sr)
    nominal_order = order_by(inputs.lcoe, candidates=inputs.ranked)
    robust_top = take_top_k(robust_order, k, n)
    nominal_top = take_top_k(nominal_order, k, n)
    robust, nominal = robust_top.mask, nominal_top.mask
    nominal_rank = ranks_from_order(nominal_order, n)
    robust_rank = ranks_from_order(robust_order, n)
    q = inputs.q
    robust_capacity = float(q[robust].sum())
    if robust_capacity <= 0:
        raise H3Error("the robust shortlist has no capacity")
    beyond = robust & (nominal_rank > k + m)
    within = robust & (nominal_rank > k) & (nominal_rank <= k + m)
    outside = float(q[beyond].sum())
    d = outside / robust_capacity
    d_ref = 1.0 - (k + m) / n_ranked
    verdict = verdict_of(d, d_ref, delta)
    lcoe_robust = _weighted_mean(inputs.lcoe, q, robust)
    lcoe_nominal = _weighted_mean(inputs.lcoe, q, nominal)
    z0 = np.where(inputs.ranked, z, 0.0)
    mr_robust = _weighted_mean(z0, q, robust)
    mr_nominal = _weighted_mean(z0, q, nominal)
    price = (
        None
        if lcoe_robust is None or lcoe_nominal is None or lcoe_nominal <= 0
        else (lcoe_robust - lcoe_nominal) / lcoe_nominal
    )
    benefit = None if mr_robust is None or mr_nominal is None else mr_nominal - mr_robust
    nominal_capacity = float(q[nominal].sum())
    ranked = inputs.ranked
    result = H3Variant(
        variant=variant,
        top_k_percent=top_k_percent,
        k=k,
        m=m,
        tolerance_multiple=tolerance_multiple,
        excluded_gcms=tuple(sorted(exclude_gcms)),
        delta=delta,
        n_cells=n,
        n_ranked=n_ranked,
        top_k_truncated=robust_top.truncated,
        robust_capacity_mw=robust_capacity,
        nominal_capacity_mw=nominal_capacity,
        outside_capacity_mw=outside,
        n_outside=int(beyond.sum()),
        d=d,
        d_ref=d_ref,
        testable=verdict != NOT_TESTABLE,
        verdict=verdict,
        robust_lcoe_mean=lcoe_robust,
        nominal_lcoe_mean=lcoe_nominal,
        robust_mr_mean=mr_robust,
        nominal_mr_mean=mr_nominal,
        price_of_robustness=price,
        benefit_of_robustness=benefit,
        centroid_distance_km=centroid_distance_km(inputs.lat, inputs.lon, q, robust, nominal),
        tv_distance=_total_variation(q, inputs.region, robust, nominal)
        if nominal_capacity > 0
        else None,
        spearman_lcoe_mr=_spearman(inputs.lcoe[ranked], z[ranked]),
        jaccard=jaccard_masks(robust, nominal),
    )
    detail = H3Detail(
        robust=robust,
        nominal=nominal,
        robust_rank=robust_rank,
        nominal_rank=nominal_rank,
        beyond=beyond,
        within_tolerance=within,
        z=z,
    )
    return result, detail


def sensitivity_variants(
    inputs: H3Inputs,
    primary: H3Variant,
    *,
    tcr_exception_gcms: Sequence[str],
) -> list[H3Variant]:
    """The mandatory sensitivities that one run can give: without the TCR-exception GCM, `p_k` in {5, 10, 20} percent, `m` in {k/2, 2k}.

    The 2071-2100 window and the 0.1 degree scale are separate runs of F7, each with its own primary row. A GCM of `tcr_exception_gcms`
    that is not in the members is skipped: the variant would equal the primary one.
    """
    common = {
        "delta": primary.delta,
        "tolerance_multiple": primary.tolerance_multiple,
        "top_k_percent": primary.top_k_percent,
    }
    out: list[H3Variant] = []
    present = sorted(set(tcr_exception_gcms) & set(inputs.gcms))
    if present:
        out.append(
            evaluate_variant(
                inputs, variant="without_" + "_".join(present), exclude_gcms=present, **common
            )[0]
        )
    for percent in SENSITIVITY_TOP_K_PERCENT:
        out.append(
            evaluate_variant(
                inputs,
                variant=f"top_k_percent_{percent:g}",
                **{**common, "top_k_percent": percent},
            )[0]
        )
    for multiple in SENSITIVITY_TOLERANCE_MULTIPLES:
        out.append(
            evaluate_variant(
                inputs,
                variant=f"tolerance_{multiple:g}k",
                **{**common, "tolerance_multiple": multiple},
            )[0]
        )
    return out
