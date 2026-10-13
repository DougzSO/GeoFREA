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
from scipy.stats import kendalltau

from geofrea.core.config_schemas import HypothesisRule
from geofrea.robustness_analysis.cell_set import CellSet
from geofrea.robustness_analysis.evaluator import Evaluation
from geofrea.robustness_analysis.futures import FuturesResult, slug
from geofrea.robustness_analysis.h1_rank_robustness import H1Descriptive, H1Variant
from geofrea.robustness_analysis.h2_aggregation import NOT_TESTABLE, SUPPORTED, H2Variant
from geofrea.robustness_analysis.h3_robust_vs_nominal import (
    H3Variant,
    centroid_distance_km,
)
from geofrea.robustness_analysis.h4_axis_dominance import H4Variant
from geofrea.robustness_analysis.rankings import jaccard_masks

if TYPE_CHECKING:
    from geofrea.robustness_analysis.assemble import Rankings

logger = logging.getLogger("geofrea.robustness_analysis.hypotheses")

DRAW_AXIS = "techno-economic draws s >= 1 (members fixed)"
_COMPARISONS = {"ge": operator.ge, "gt": operator.gt, "le": operator.le, "lt": operator.lt}


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


H1_DESCRIPTIVE = "descriptive evidence, no verdict (the primary statistics of H1 are h1a_core_share and h1b_vulnerable_share)"


def h1(futures: FuturesResult, cell_set: CellSet, ranking: Rankings) -> list[Statistic]:
    """H1, descriptive: Spearman of the rankings and Jaccard of the top-k sets between SSPs, share of the nominal top-k that leaves under a member.

    These are the draw-level statistics of the sample-major pass; they carry no verdict (M-F7-07, H1).
    """
    return [
        with_range(
            "H1",
            name,
            values,
            n_cells=cell_set.n_f7,
            k=ranking.k,
            truncated=False,
            note=(
                f"{H1_DESCRIPTIVE}; Spearman of ranking positions (ties by cell_id)"
                if "spearman" in name
                else H1_DESCRIPTIVE
            ),
        )
        for name, values in futures.draw_statistics.items()
    ]


def h1_primary(
    variant: H1Variant, extra: H1Descriptive, n_cells: int, truncated: bool
) -> list[Statistic]:
    """H1: the primary statistics `C_k` and `V_k` (the ones the pre-registered rule names) and the descriptive evidence.

    Implements: M-F7-07 (H1). The verdict on the hypothesis is in the `h1_summary` table; the rows here carry the rule of each statistic.
    """
    k = variant.k

    def row(name: str, value: float | None, note: str | None = None) -> Statistic:
        return Statistic(
            "H1", name, _clean(value), n_cells=n_cells, k=k, top_k_truncated=truncated, note=note
        )

    rows = [
        row("h1a_core_share", variant.c_k, "H1a: C_k, the share of the top-k common to all SSPs"),
        row(
            "h1b_vulnerable_share",
            variant.v_k,
            f"H1b: V_k, the share of the nominal top-k outside the top {variant.k + variant.m} of the climate-only ranking in some SSP",
        ),
        row(
            "h1_core_share_reference",
            variant.reference,
            "p_k^2 with p_k = k / n: the expected C_k if the SSP rankings were independent",
        ),
        row("h1_core_size", float(variant.core_size)),
        row("h1_vulnerable_count", float(variant.n_vulnerable)),
        row(
            "h1_subhypotheses_holding",
            float(variant.h1a_holds) + float(variant.h1b_holds),
            f"verdict: {variant.verdict}",
        ),
    ]
    for a, b, jaccard, value, residual in extra.pairs:
        pair = f"{slug(a)}_vs_{slug(b)}"
        rows.append(row(f"h1_ssp_jaccard__{pair}", jaccard, H1_DESCRIPTIVE))
        rows.append(
            row(
                f"h1_ssp_rbo__{pair}",
                value,
                f"{H1_DESCRIPTIVE}; RBO truncated at the ranked set, p = {extra.rbo_p:.6g}, lower bound with residual {residual:.3g}",
            )
        )
    rows += [
        row(
            "h1_nominal_top_k_median_rank_across_ssps",
            extra.median_rank_across_ssps,
            f"{H1_DESCRIPTIVE}; median over the nominal top-k of the median rank (by MR per SSP) across SSPs, over {extra.n_sites_with_rank} cells with a rank",
        ),
        row(
            "h1_nominal_top_k_ssp_rank_iqr_median",
            extra.ssp_rank_iqr_median,
            f"{H1_DESCRIPTIVE}; median over the nominal top-k of the interquartile range of the rank across SSPs",
        ),
        row(
            "h1_nominal_top_k_displacement_median",
            extra.displacement_median,
            f"{H1_DESCRIPTIVE}; worst climate-only rank minus nominal rank, median over the nominal top-k",
        ),
        row(
            "h1_nominal_top_k_displacement_iqr",
            extra.displacement_iqr,
            f"{H1_DESCRIPTIVE}; interquartile range of the same displacement",
        ),
    ]
    return rows


H2_DESCRIPTIVE = (
    "descriptive evidence, no verdict (the primary statistic of H2 is h2_overlap_index)"
)
H2_PRIMARY = "h2_overlap_index"


def h2_primary(variant: H2Variant, n_cells: int) -> list[Statistic]:
    """H2: the Capacity Overlap Index `O` (the statistic the pre-registered rule names), its reference and the diagnostics.

    Implements: M-F7-07 (H2). The verdict is given by `h2_verdict_entry`; the full result is in the `h2_summary` table.
    """

    def row(name: str, value: float | None, note: str | None = None) -> Statistic:
        return Statistic("H2", name, _clean(value), n_cells=n_cells, k=variant.k, note=note)

    return [
        row(
            H2_PRIMARY,
            variant.overlap,
            "H2: O, the share of the target capacity T that the cell selection and the Admin1 selection both take",
        ),
        row(
            "h2_overlap_reference",
            variant.overlap_ref,
            "T / Q_max: the overlap of a uniform spread over the country; H2 is not testable when it reaches gamma",
        ),
        row("h2_target_mw", variant.target_mw, "T, the capacity of the robust top-k set (MW)"),
        row(
            "h2_candidate_capacity_mw",
            variant.q_max_mw,
            "Q_max, the capacity of the ranked set (MW)",
        ),
        row("h2_n_regions", float(variant.n_regions), H2_DESCRIPTIVE),
        row(
            "h2_robustness_penalty",
            variant.robustness_penalty,
            f"{H2_DESCRIPTIVE}; Delta_z: capacity-weighted increase of MR from selecting regions instead of cells",
        ),
        row(
            "h2_tv_distance",
            variant.tv_distance,
            f"{H2_DESCRIPTIVE}; total variation distance between the regional shares of T of the two selections",
        ),
    ]


def h2_verdict_entry(variant: H2Variant) -> dict[str, str | None]:
    """The rule, the verdict (`met` is supported) and the reason of the primary statistic of H2: not testable gives no verdict."""
    text = f"{H2_PRIMARY} lt {variant.gamma} (testable when h2_overlap_reference < {variant.gamma})"
    if variant.verdict == NOT_TESTABLE:
        return {
            "rule": text,
            "verdict": None,
            "verdict_reason": f"not testable: the reference overlap {variant.overlap_ref:.3f} reaches gamma {variant.gamma}",
        }
    return {
        "rule": text,
        "verdict": "met" if variant.verdict == SUPPORTED else "not_met",
        "verdict_reason": None,
    }


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
        Statistic("H2", "h2_mr_median", _clean(median), n_cells=n, note=H2_DESCRIPTIVE),
        Statistic(
            "H2",
            "h2_mr_iqr_over_median",
            _clean((q75 - q25) / median) if median > 0 else None,
            n_cells=n,
            note=H2_DESCRIPTIVE,
        ),
        Statistic(
            "H2",
            "h2_mr_capacity_weighted_national",
            _clean(national),
            n_cells=n,
            note=H2_DESCRIPTIVE,
        ),
        Statistic("H2", "h2_n_admin1_units", float(medians.size), n_cells=n, note=H2_DESCRIPTIVE),
        Statistic(
            "H2", "h2_mr_admin1_median_range", _clean(spread), n_cells=n, note=H2_DESCRIPTIVE
        ),
        Statistic(
            "H2",
            "h2_mr_admin1_median_range_over_national",
            _clean(spread / national) if national > 0 else None,
            n_cells=n,
            note=H2_DESCRIPTIVE,
        ),
    ]
    return rows


H3_DESCRIPTIVE = (
    "descriptive evidence, no verdict (the primary statistic of H3 is h3_beyond_reach_share)"
)
H3_PRIMARY = "h3_beyond_reach_share"


def h3_primary(variant: H3Variant, n_cells: int) -> list[Statistic]:
    """H3: `D`, the share of the robust capacity beyond the reach of the nominal plan (the statistic the pre-registered rule names), its
    reference, the price and the benefit of robustness and the diagnostics.

    Implements: M-F7-07 (H3). The verdict is given by `h3_verdict_entry`; the full result is in the `h3_summary` table.
    """

    def row(name: str, value: float | None, note: str | None = None) -> Statistic:
        return Statistic(
            "H3",
            name,
            _clean(value),
            n_cells=n_cells,
            k=variant.k,
            top_k_truncated=variant.top_k_truncated,
            note=note,
        )

    return [
        row(
            H3_PRIMARY,
            variant.d,
            "H3: D, the share of the capacity of the robust shortlist whose nominal rank exceeds k + m",
        ),
        row(
            "h3_reference_share",
            variant.d_ref,
            "1 - (k + m) / |I|: the share for unrelated rankings; H3 is not testable when it is below delta",
        ),
        row(
            "h3_price_of_robustness",
            variant.price_of_robustness,
            f"{H3_DESCRIPTIVE}; Pi: relative increase of the capacity-weighted LCOE at f0 from the nominal to the robust shortlist",
        ),
        row(
            "h3_benefit_of_robustness",
            variant.benefit_of_robustness,
            f"{H3_DESCRIPTIVE}; B: reduction of the capacity-weighted MR from the nominal to the robust shortlist",
        ),
        row(
            "h3_robust_capacity_mw",
            variant.robust_capacity_mw,
            "capacity of the robust shortlist (MW)",
        ),
        row(
            "h3_nominal_capacity_mw",
            variant.nominal_capacity_mw,
            "capacity of the nominal shortlist (MW)",
        ),
        row(
            "h3_shortlist_centroid_distance_km",
            variant.centroid_distance_km,
            f"{H3_DESCRIPTIVE}; geodesic distance between the capacity-weighted centroids of the two shortlists",
        ),
        row(
            "h3_tv_distance",
            variant.tv_distance,
            f"{H3_DESCRIPTIVE}; total variation distance between the Admin1 distributions of capacity of the two shortlists",
        ),
        row(
            "h3_spearman_lcoe_mr",
            variant.spearman_lcoe_mr,
            f"{H3_DESCRIPTIVE}; Spearman correlation between LCOE at f0 and MR over the ranked set",
        ),
        row(
            "h3_shortlist_jaccard",
            variant.jaccard,
            f"{H3_DESCRIPTIVE}; Jaccard overlap of the two shortlists by cell count",
        ),
    ]


def h3_verdict_entry(variant: H3Variant) -> dict[str, str | None]:
    """The rule, the verdict (`met` is supported) and the reason of the primary statistic of H3: not testable gives no verdict."""
    text = f"{H3_PRIMARY} ge {variant.delta} (testable when h3_reference_share >= {variant.delta})"
    if variant.verdict == NOT_TESTABLE:
        return {
            "rule": text,
            "verdict": None,
            "verdict_reason": f"not testable: the reference share {variant.d_ref:.3f} is below delta {variant.delta}",
        }
    return {
        "rule": text,
        "verdict": "met" if variant.verdict == SUPPORTED else "not_met",
        "verdict_reason": None,
    }


def h3(
    cell_set: CellSet,
    ranking: Rankings,
    futures: FuturesResult,
    lat: np.ndarray,
    lon: np.ndarray,
) -> list[Statistic]:
    """H3, descriptive rows over the F7 set: Jaccard of the nominal and robust top-k, capacity of the robust top-k outside the nominal one, distance
    between centroids, and the per-future statistics of the sample-major pass (the primary statistic of H3 is `h3_beyond_reach_share`)."""
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
            note=H3_DESCRIPTIVE,
        ),
        Statistic(
            "H3",
            "h3_robust_capacity_outside_nominal_share",
            _clean(outside),
            n_cells=n,
            k=k,
            top_k_truncated=truncated,
            note=H3_DESCRIPTIVE,
        ),
        Statistic(
            "H3",
            "h3_centroid_distance_km",
            centroid_distance_km(lat, lon, p_mw, nominal, robust),
            n_cells=n,
            k=k,
            top_k_truncated=truncated,
            note=H3_DESCRIPTIVE,
        ),
        with_range(
            "H3",
            "h3_future_jaccard_with_nominal_median_over_members",
            median_jaccard,
            n_cells=n,
            k=k,
            truncated=False,
            note=H3_DESCRIPTIVE,
        ),
        with_range(
            "H3",
            "h3_future_share_leaving_median_over_members",
            median_share,
            n_cells=n,
            k=k,
            truncated=False,
            note=H3_DESCRIPTIVE,
        ),
    ]


H4_DESCRIPTIVE = "descriptive evidence, no verdict (the primary statistics of H4 are h4_displacement_climate, h4_displacement_techno and h4_dominance_ratio)"
H4_PROFILE_NOTE = "the profile and the verdict of H4 are in the h4_country table and, across countries, in h4_verdict (cross_country_h4)"


def h4_primary(variant: H4Variant, n_cells: int) -> list[Statistic]:
    """H4: the displacements `D_clim` and `D_tec`, their sum, the dominance ratio and the joint displacement of one country and technology.

    Implements: M-F7-07 (H4). The statistics carry no verdict: the profile of the country is in `h4_country` and the verdict needs the other
    countries (`cross_country_h4`).
    """

    def row(name: str, value: float | None, note: str) -> Statistic:
        return Statistic(
            "H4",
            name,
            _clean(value),
            n_cells=n_cells,
            k=variant.k,
            top_k_truncated=variant.top_k_truncated,
            note=note,
        )

    return [
        row(
            "h4_displacement_climate",
            variant.d_clim,
            f"D_clim: share of the capacity of the climate-axis shortlist beyond the nominal top k + m; {H4_PROFILE_NOTE}",
        ),
        row(
            "h4_displacement_techno",
            variant.d_tec,
            f"D_tec: share of the capacity of the techno-economic-axis shortlist beyond the nominal top k + m; {H4_PROFILE_NOTE}",
        ),
        row("h4_displacement_sum", variant.d_sum, f"D_clim + D_tec; {H4_PROFILE_NOTE}"),
        row(
            "h4_dominance_ratio",
            variant.rho,
            f"rho = D_clim / (D_clim + D_tec), null when both are 0; profile {variant.profile}; {H4_PROFILE_NOTE}",
        ),
        row(
            "h4_displacement_joint",
            variant.d_joint,
            f"{H4_DESCRIPTIVE}; D of H3 (both axes together), beside D_clim and D_tec",
        ),
    ]


def h4(cell_set: CellSet, evaluation: Evaluation, ranking: Rankings | None) -> list[Statistic]:
    """H4, descriptive rows over the F7 set: the variance shares and the Jaccard of the nominal top-k with the climate-only and the techno-only top-k
    (the primary statistics of H4 are `h4_displacement_*` and `h4_dominance_ratio`)."""
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
                note=H4_DESCRIPTIVE,
            )
        )
        rows.append(
            Statistic(
                "H4",
                "h4_variance_share_techno",
                float(evaluation.var_within[ranked].sum() / total),
                n_cells=int(ranked.sum()),
                note=H4_DESCRIPTIVE,
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
                note=H4_DESCRIPTIVE,
            ),
            Statistic(
                "H4",
                "h4_jaccard_techno_only",
                j_tech,
                n_cells=cell_set.n_f7,
                k=k,
                top_k_truncated=truncated,
                note=H4_DESCRIPTIVE,
            ),
            Statistic(
                "H4",
                "h4_jaccard_difference_climate_minus_techno",
                j_clim - j_tech,
                n_cells=cell_set.n_f7,
                k=k,
                top_k_truncated=truncated,
                note=H4_DESCRIPTIVE,
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
