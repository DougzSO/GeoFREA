"""The statistics of H1 to H5 and the comparison with the pre-registered rules (M-F7-07; D-F7-014, D-F7-015).

F7 computes statistics. A rule of `experiments.yaml` `hypothesis_rules` (OQ-050) names one statistic, a comparison and a threshold; F7 writes
whether the comparison holds (`verdict` `met` or `not_met`) and nothing else: it combines no rules into a verdict on a hypothesis and runs no
test of significance. A hypothesis with no rule keeps its statistic rows with a null verdict and the reason, and a warning is logged.

A statistic that depends on the parameter draws has its central value at the nominal vector `s0` and the P10, P50 and P90 over the draws
`s >= 1` with the axis named (U-08). Cells are the F7 set; weights are the capacity of the cell.
"""

from __future__ import annotations

import logging
import operator
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from pyproj import Geod
from scipy.stats import kendalltau

from geofrea.core.config_schemas import HypothesisRule
from geofrea.robustness_analysis.cell_set import CellSet
from geofrea.robustness_analysis.evaluator import Evaluation
from geofrea.robustness_analysis.futures import FuturesResult
from geofrea.robustness_analysis.rankings import jaccard_masks

if TYPE_CHECKING:
    from geofrea.robustness_analysis.assemble import Rankings

logger = logging.getLogger("geofrea.robustness_analysis.hypotheses")

DRAW_AXIS = "techno-economic draws s >= 1 (members fixed)"
_COMPARISONS = {"ge": operator.ge, "gt": operator.gt, "le": operator.le, "lt": operator.lt}
_GEOD = Geod(ellps="WGS84")


class HypothesisRuleError(ValueError):
    """A pre-registered rule names a statistic that F7 does not write (A-09)."""


@dataclass(frozen=True)
class Statistic:
    """One statistic: the central value, the range over the draws if it has one, and the hypothesis it serves."""

    hypothesis: str
    statistic: str
    value: float | None
    p10: float | None = None
    p50: float | None = None
    p90: float | None = None
    range_axis: str | None = None
    n_cells: int = 0
    k: int | None = None
    top_k_truncated: bool = False
    note: str | None = None


def _clean(value: float | None) -> float | None:
    return None if value is None or not np.isfinite(value) else float(value)


def with_range(
    hypothesis: str,
    statistic: str,
    per_draw: np.ndarray,
    *,
    n_cells: int,
    k: int | None,
    truncated: bool,
    axis: str = DRAW_AXIS,
    note: str | None = None,
) -> Statistic:
    """A statistic given for every draw (index 0 is `s0`): the central value and the P10, P50, P90 of the draws."""
    draws = np.asarray(per_draw, dtype="float64")[1:]
    draws = draws[np.isfinite(draws)]
    q = np.quantile(draws, [0.1, 0.5, 0.9]) if draws.size else (np.nan, np.nan, np.nan)
    return Statistic(
        hypothesis,
        statistic,
        _clean(per_draw[0]),
        _clean(q[0]),
        _clean(q[1]),
        _clean(q[2]),
        axis,
        n_cells,
        k,
        truncated,
        note,
    )


def h1(futures: FuturesResult, cell_set: CellSet, ranking: Rankings) -> list[Statistic]:
    """H1: Spearman of the rankings and Jaccard of the top-k sets between SSPs, share of the nominal top-k that leaves under a member."""
    return [
        with_range(
            "H1",
            name,
            values,
            n_cells=cell_set.n_f7,
            k=ranking.k,
            truncated=False,
            note="Spearman of ranking positions (ties by cell_id)" if "spearman" in name else None,
        )
        for name, values in futures.draw_statistics.items()
    ]


def h2(cell_set: CellSet, evaluation: Evaluation, admin1: np.ndarray) -> list[Statistic]:
    """H2: dispersion of `MR` across the ranked cells, across admin1 units, and the capacity-weighted national aggregate."""
    ranked = cell_set.ranked
    mr = evaluation.mr[ranked]
    p_mw = cell_set.p_mw[ranked]
    units = np.asarray(admin1)[ranked]
    n = int(ranked.sum())
    if n == 0:
        return []
    q25, median, q75 = np.quantile(mr, [0.25, 0.5, 0.75])
    national = float((p_mw * mr).sum() / p_mw.sum()) if p_mw.sum() > 0 else float("nan")
    medians = np.array([np.median(mr[units == u]) for u in np.unique(units)])
    spread = float(medians.max() - medians.min())
    rows = [
        Statistic("H2", "h2_mr_median", _clean(median), n_cells=n),
        Statistic(
            "H2",
            "h2_mr_iqr_over_median",
            _clean((q75 - q25) / median) if median > 0 else None,
            n_cells=n,
        ),
        Statistic("H2", "h2_mr_capacity_weighted_national", _clean(national), n_cells=n),
        Statistic("H2", "h2_n_admin1_units", float(medians.size), n_cells=n),
        Statistic("H2", "h2_mr_admin1_median_range", _clean(spread), n_cells=n),
        Statistic(
            "H2",
            "h2_mr_admin1_median_range_over_national",
            _clean(spread / national) if national > 0 else None,
            n_cells=n,
        ),
    ]
    return rows


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


def h3(
    cell_set: CellSet,
    ranking: Rankings,
    futures: FuturesResult,
    lat: np.ndarray,
    lon: np.ndarray,
) -> list[Statistic]:
    """H3: Jaccard of the nominal and robust top-k, capacity of the robust top-k outside the nominal one, distance between centroids."""
    assert ranking.top_nominal is not None and ranking.top_robust is not None
    nominal, robust = ranking.top_nominal.mask, ranking.top_robust.mask
    p_mw = cell_set.p_mw
    robust_capacity = float(p_mw[robust].sum())
    outside = (
        float(p_mw[robust & ~nominal].sum() / robust_capacity) if robust_capacity > 0 else None
    )
    n, k, truncated = cell_set.n_f7, ranking.k, ranking.top_k_truncated
    median_jaccard = np.median(futures.jaccard_nominal, axis=0)
    median_share = np.median(futures.share_leaving, axis=0)
    return [
        Statistic(
            "H3",
            "h3_jaccard_nominal_robust",
            jaccard_masks(nominal, robust),
            n_cells=n,
            k=k,
            top_k_truncated=truncated,
        ),
        Statistic(
            "H3",
            "h3_robust_capacity_outside_nominal_share",
            _clean(outside),
            n_cells=n,
            k=k,
            top_k_truncated=truncated,
        ),
        Statistic(
            "H3",
            "h3_centroid_distance_km",
            centroid_distance_km(lat, lon, p_mw, nominal, robust),
            n_cells=n,
            k=k,
            top_k_truncated=truncated,
        ),
        with_range(
            "H3",
            "h3_future_jaccard_with_nominal_median_over_members",
            median_jaccard,
            n_cells=n,
            k=k,
            truncated=False,
        ),
        with_range(
            "H3",
            "h3_future_share_leaving_median_over_members",
            median_share,
            n_cells=n,
            k=k,
            truncated=False,
        ),
    ]


def h4(cell_set: CellSet, evaluation: Evaluation, ranking: Rankings | None) -> list[Statistic]:
    """H4: Jaccard of the nominal top-k with the climate-only and the techno-only top-k, and the variance shares (secondary)."""
    ranked = cell_set.ranked
    total = float(evaluation.var_total[ranked].sum())
    rows = []
    if total > 0:
        rows.append(
            Statistic(
                "H4",
                "h4_variance_share_climate",
                float(evaluation.var_between[ranked].sum() / total),
                n_cells=int(ranked.sum()),
            )
        )
        rows.append(
            Statistic(
                "H4",
                "h4_variance_share_techno",
                float(evaluation.var_within[ranked].sum() / total),
                n_cells=int(ranked.sum()),
            )
        )
    if ranking is not None and ranking.top_nominal is not None:
        assert ranking.top_climate is not None and ranking.top_techno is not None
        j_clim = jaccard_masks(ranking.top_nominal.mask, ranking.top_climate.mask)
        j_tech = jaccard_masks(ranking.top_nominal.mask, ranking.top_techno.mask)
        k, truncated = ranking.k, ranking.top_k_truncated
        rows += [
            Statistic(
                "H4",
                "h4_jaccard_climate_only",
                j_clim,
                n_cells=cell_set.n_f7,
                k=k,
                top_k_truncated=truncated,
            ),
            Statistic(
                "H4",
                "h4_jaccard_techno_only",
                j_tech,
                n_cells=cell_set.n_f7,
                k=k,
                top_k_truncated=truncated,
            ),
            Statistic(
                "H4",
                "h4_jaccard_difference_climate_minus_techno",
                j_clim - j_tech,
                n_cells=cell_set.n_f7,
                k=k,
                top_k_truncated=truncated,
            ),
        ]
    return rows


def h5(
    evaluation: Evaluation,
    n_cells: int,
    target_gw: float | None,
    exposure_shares: Mapping[str, float],
    land_range: Mapping[str, tuple[float, float]],
) -> list[Statistic]:
    """H5: potential below `tau` and its change against `m0`, the gap to the target, the exposed share, the land range.

    `evaluation.potential_*` have the reference member in row 0 and the core members after it; each is `(1 + M, N + 1)`.
    `land_range` maps a land scenario to the nominal potential below `tau` of `m0` (GW) and its median over the core members (GW).
    """
    rows: list[Statistic] = []
    if evaluation.potential_gw is None or evaluation.potential_twh is None:
        return rows
    for unit, array in (("gw", evaluation.potential_gw), ("twh", evaluation.potential_twh)):
        reference, members = array[0], array[1:]
        change = members - reference[None, :]  # (M, N + 1)
        rows.append(
            with_range(
                "H5",
                f"h5_potential_below_tau_{unit}_m0",
                reference,
                n_cells=n_cells,
                k=None,
                truncated=False,
            )
        )
        for label, fn in (("min", np.min), ("median", np.median), ("max", np.max)):
            rows.append(
                with_range(
                    "H5",
                    f"h5_climate_effect_{unit}_{label}_over_members",
                    fn(change, axis=0),
                    n_cells=n_cells,
                    k=None,
                    truncated=False,
                )
            )
    if target_gw is not None:
        gap = target_gw - np.median(evaluation.potential_gw[1:], axis=0)
        rows.append(
            with_range(
                "H5",
                "h5_gap_to_target_gw_median_over_members",
                gap,
                n_cells=n_cells,
                k=None,
                truncated=False,
            )
        )
    for name, share in exposure_shares.items():
        rows.append(
            Statistic("H5", f"h5_exposed_potential_share__{name}", _clean(share), n_cells=n_cells)
        )
    for scenario, (reference_gw, median_gw) in land_range.items():
        rows.append(
            Statistic(
                "H5",
                f"h5_land_{scenario}_potential_below_tau_gw_m0",
                _clean(reference_gw),
                n_cells=n_cells,
            )
        )
        rows.append(
            Statistic(
                "H5",
                f"h5_land_{scenario}_potential_below_tau_gw_median_over_members",
                _clean(median_gw),
                n_cells=n_cells,
            )
        )
    return rows


def _tied_pairs(*keys: np.ndarray) -> int:
    """The number of pairs of cells that share the same value in every one of `keys`."""
    _, counts = np.unique(np.column_stack(keys), axis=0, return_counts=True)
    return int((counts * (counts - 1) // 2).sum())


def agreement(cell_set: CellSet, evaluation: Evaluation) -> list[Statistic]:
    """MR against SR (M-F7-09, D-F7-022): Kendall's tau-b between `MR` and `-SR` over the ranked set, with the number of tied pairs.

    `MR` is better when low and `SR` when high, so the statistic is taken against `-SR`: a positive value means the two criteria order the
    cells alike. Nothing is written without `tau` (no `SR`) or with fewer than two ranked cells.
    """
    if evaluation.sr is None:
        return []
    ranked = cell_set.ranked
    mr, minus_sr = evaluation.mr[ranked], -evaluation.sr[ranked]
    n = int(ranked.sum())
    if n < 2:
        return []
    tau = float(kendalltau(mr, minus_sr, variant="b").statistic)
    note = "Kendall tau-b between MR and -SR over the ranked set; positive: the two criteria order the cells alike"
    return [
        Statistic("RQ4", "mr_sr_kendall_tau_b", _clean(tau), n_cells=n, note=note),
        Statistic("RQ4", "mr_sr_pairs", float(n * (n - 1) // 2), n_cells=n),
        Statistic("RQ4", "mr_sr_tied_pairs_mr", float(_tied_pairs(mr)), n_cells=n),
        Statistic("RQ4", "mr_sr_tied_pairs_sr", float(_tied_pairs(minus_sr)), n_cells=n),
        Statistic("RQ4", "mr_sr_tied_pairs_both", float(_tied_pairs(mr, minus_sr)), n_cells=n),
    ]


def evaluate_rules(
    statistics: Sequence[Statistic], rules: Mapping[str, Sequence[HypothesisRule] | None]
) -> list[dict[str, str | None]]:
    """Per statistic, the rule that names it, its result and the reason when there is none.

    Implements: M-F7-07 (OQ-050, D-F7-014).

    Returns:
        One dict per statistic with `rule`, `verdict` (`met`, `not_met` or None) and `verdict_reason`.

    Raises:
        HypothesisRuleError: a rule names a statistic that is not among `statistics`.
    """
    known = {s.statistic for s in statistics}
    by_name: dict[str, list[HypothesisRule]] = {}
    for hypothesis, listed in rules.items():
        for rule in listed or []:
            if rule.statistic not in known:
                raise HypothesisRuleError(
                    f"rule of {hypothesis} names the statistic {rule.statistic!r}, which F7 does not write here"
                )
            by_name.setdefault(rule.statistic, []).append(rule)
    out: list[dict[str, str | None]] = []
    for stat in statistics:
        listed = rules.get(stat.hypothesis)
        matching = by_name.get(stat.statistic, [])
        if not matching:
            reason = (
                "no pre-registered rule for this hypothesis (OQ-050)"
                if not listed
                else "this statistic is not named by a rule"
            )
            out.append({"rule": None, "verdict": None, "verdict_reason": reason})
            continue
        rule = matching[0]
        text = f"{rule.statistic} {rule.comparison} {rule.threshold}"
        if stat.value is None:
            out.append(
                {
                    "rule": text,
                    "verdict": None,
                    "verdict_reason": "the statistic has no value (empty set)",
                }
            )
            continue
        met = _COMPARISONS[rule.comparison](stat.value, rule.threshold)
        out.append({"rule": text, "verdict": "met" if met else "not_met", "verdict_reason": None})
    return out
