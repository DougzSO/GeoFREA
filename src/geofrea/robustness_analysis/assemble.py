"""The rankings of M-F7-05 and M-F7-06 and the per-cell table of M-F7-11, from the evaluation and the classes (D-F7-010 to D-F7-013)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from geofrea.robustness_analysis.cell_set import CellSet
from geofrea.robustness_analysis.decision import TechDecision
from geofrea.robustness_analysis.evaluator import Evaluation
from geofrea.robustness_analysis.futures import FuturesResult, MemberLabel
from geofrea.robustness_analysis.h1_rank_robustness import H1Detail, H1Inputs, H1Variant
from geofrea.robustness_analysis.h2_aggregation import H2Detail, H2Variant
from geofrea.robustness_analysis.h3_robust_vs_nominal import H3Detail, H3Inputs, H3Variant
from geofrea.robustness_analysis.h4_axis_dominance import H4Variant
from geofrea.robustness_analysis.h5_climate_pressure import H5Variant
from geofrea.robustness_analysis.hypotheses import Statistic
from geofrea.robustness_analysis.prim import PrimResult
from geofrea.robustness_analysis.rankings import (
    TopK,
    capacity_target_set,
    order_by,
    ranks_from_order,
    take_top_k,
    top_k_size,
)


@dataclass(frozen=True)
class Rankings:
    """The orderings and top-k sets over the F7 set; `None` where the decision parameter that needs them is null."""

    k: int | None
    nominal_order: np.ndarray
    robust_order: np.ndarray
    climate_order: np.ndarray
    techno_order: np.ndarray
    nominal_rank: np.ndarray
    robust_rank: np.ndarray
    climate_rank: np.ndarray
    techno_rank: np.ndarray
    top_nominal: TopK | None
    top_robust: TopK | None
    top_climate: TopK | None
    top_techno: TopK | None
    capacity_mask: np.ndarray | None
    target_reached: bool | None

    @property
    def top_k_truncated(self) -> bool:
        return any(
            t is not None and t.truncated
            for t in (self.top_robust, self.top_climate, self.top_techno)
        )


def compute_rankings(cell_set: CellSet, evaluation: Evaluation, decision: TechDecision) -> Rankings:
    """Nominal, robust, climate-only and techno-only orderings, the top-k sets and the capacity-target set.

    Implements: M-F7-05, M-F7-06.

    The nominal ordering covers the F7 set, the other three the ranked set (the F7 set without the climate-fragile cells). The robust one
    breaks ties of `MR` by higher `SR` and then by `cell_id`; the sub-family orderings by `cell_id` (D-F7-012).
    """
    n = cell_set.n_f7
    ranked = cell_set.ranked
    nominal = evaluation.nominal_lcoe[:, 0]
    nominal_order = order_by(nominal)
    robust_order = order_by(evaluation.mr, candidates=ranked, descending_tiebreak=evaluation.sr)
    climate_order = order_by(evaluation.mr_clim, candidates=ranked)
    techno_order = order_by(evaluation.mr_tech, candidates=ranked)
    k = top_k_size(decision.top_k_percent, n) if decision.top_k_percent is not None else None
    tops = (
        tuple(
            take_top_k(order, k, n)
            for order in (nominal_order, robust_order, climate_order, techno_order)
        )
        if k is not None
        else (None, None, None, None)
    )
    mask, reached = (None, None)
    if decision.capacity_target_gw is not None:
        mask, reached = capacity_target_set(
            robust_order, cell_set.p_mw, decision.capacity_target_gw
        )
    return Rankings(
        k=k,
        nominal_order=nominal_order,
        robust_order=robust_order,
        climate_order=climate_order,
        techno_order=techno_order,
        nominal_rank=ranks_from_order(nominal_order, n),
        robust_rank=ranks_from_order(robust_order, n),
        climate_rank=ranks_from_order(climate_order, n),
        techno_rank=ranks_from_order(techno_order, n),
        top_nominal=tops[0],
        top_robust=tops[1],
        top_climate=tops[2],
        top_techno=tops[3],
        capacity_mask=mask,
        target_reached=reached,
    )


def _nullable(values: np.ndarray, present: np.ndarray, dtype: str) -> pd.Series:
    """`values` where `present`, a null elsewhere, as a pandas nullable dtype."""
    series = pd.Series(values).astype(dtype)
    return series.where(pd.Series(present), pd.NA)


def robustness_frame(
    cell_set: CellSet,
    evaluation: Evaluation,
    ranking: Rankings,
    candidates: pd.DataFrame,
) -> pd.DataFrame:
    """One row per candidate cell: the class, and the results for the cells of the F7 set (M-F7-11).

    Args:
        candidates: `cell_id`, `lat_c`, `lon_c` and `admin1_id` of every candidate, in the order of `cell_set.candidate_ids`.
    """
    ids = cell_set.candidate_ids
    position = cell_set.f7_position
    in_f7 = position >= 0
    at = np.where(in_f7, position, 0)
    failing = cell_set.failing_members()
    lists = [failing[p] if f else [] for p, f in zip(position, in_f7, strict=True)]
    f7_total = evaluation.var_total

    def pick(
        values: np.ndarray, dtype: str = "float64", present: np.ndarray | None = None
    ) -> pd.Series:
        flag = in_f7 if present is None else in_f7 & present
        return _nullable(np.asarray(values)[at], flag, dtype)

    with np.errstate(invalid="ignore", divide="ignore"):
        share_climate = np.where(f7_total > 0, evaluation.var_between / f7_total, np.nan)
        share_techno = np.where(f7_total > 0, evaluation.var_within / f7_total, np.nan)
    ranked_flag = np.asarray(cell_set.ranked)[at] & in_f7
    sr_column = (
        pick(evaluation.sr)
        if evaluation.sr is not None
        else pd.Series([pd.NA] * ids.size, dtype="Float64")
    )

    def flag(top, positions: np.ndarray) -> pd.Series:
        if top is None:
            return pd.Series([pd.NA] * ids.size, dtype="boolean")
        return _nullable(top.mask[positions], in_f7, "boolean")

    out = pd.DataFrame(
        {
            "cell_id": ids,
            "cell_class": cell_set.classes.astype(str),
            "admin1_id": candidates["admin1_id"].to_numpy(dtype=object),
            "lat_c": candidates["lat_c"].to_numpy(dtype="float64"),
            "lon_c": candidates["lon_c"].to_numpy(dtype="float64"),
            "p_mw": pick(cell_set.p_mw),
            "lcoe_nominal": pick(evaluation.nominal_lcoe[:, 0]),
            "nominal_rank": pick(ranking.nominal_rank, "Int64"),
            "mr": pick(evaluation.mr, present=ranked_flag),
            "sr": sr_column,
            "robust_rank": pick(ranking.robust_rank, "Int64", present=ranking.robust_rank[at] > 0),
            "mr_clim": pick(evaluation.mr_clim, present=ranked_flag),
            "mr_tech": pick(evaluation.mr_tech),
            "climate_only_rank": pick(
                ranking.climate_rank, "Int64", present=ranking.climate_rank[at] > 0
            ),
            "techno_only_rank": pick(
                ranking.techno_rank, "Int64", present=ranking.techno_rank[at] > 0
            ),
            "failing_members": lists,
            "n_failing_members": [len(x) for x in lists],
            "var_total": pick(f7_total),
            "var_share_climate": pick(share_climate),
            "var_share_techno": pick(share_techno),
            "topk_nominal": flag(ranking.top_nominal, at),
            "topk_robust": flag(ranking.top_robust, at),
            "topk_climate_only": flag(ranking.top_climate, at),
            "topk_techno_only": flag(ranking.top_techno, at),
            "topk_capacity_target": (
                pd.Series([pd.NA] * ids.size, dtype="boolean")
                if ranking.capacity_mask is None
                else _nullable(ranking.capacity_mask[at], in_f7, "boolean")
            ),
        }
    )
    return out


def classes_only_frame(cell_set: CellSet, candidates: pd.DataFrame) -> pd.DataFrame:
    """The classes of the candidates when the F7 set is empty: every result column is null (M-F7-01, D-F7-006)."""
    ids = cell_set.candidate_ids
    n = ids.size

    def nulls(dtype: str) -> pd.Series:
        return pd.Series([pd.NA] * n, dtype=dtype)

    return pd.DataFrame(
        {
            "cell_id": ids,
            "cell_class": cell_set.classes.astype(str),
            "admin1_id": candidates["admin1_id"].to_numpy(dtype=object),
            "lat_c": candidates["lat_c"].to_numpy(dtype="float64"),
            "lon_c": candidates["lon_c"].to_numpy(dtype="float64"),
            "p_mw": nulls("Float64"),
            "lcoe_nominal": nulls("Float64"),
            "nominal_rank": nulls("Int64"),
            "mr": nulls("Float64"),
            "sr": nulls("Float64"),
            "robust_rank": nulls("Int64"),
            "mr_clim": nulls("Float64"),
            "mr_tech": nulls("Float64"),
            "climate_only_rank": nulls("Int64"),
            "techno_only_rank": nulls("Int64"),
            "failing_members": [[] for _ in range(n)],
            "n_failing_members": np.zeros(n, dtype="int64"),
            "var_total": nulls("Float64"),
            "var_share_climate": nulls("Float64"),
            "var_share_techno": nulls("Float64"),
            "topk_nominal": nulls("boolean"),
            "topk_robust": nulls("boolean"),
            "topk_climate_only": nulls("boolean"),
            "topk_techno_only": nulls("boolean"),
            "topk_capacity_target": nulls("boolean"),
        }
    )


def empty_nominal_frame() -> pd.DataFrame:
    """The nominal-by-member table of an empty F7 set."""
    return pd.DataFrame(
        {
            "cell_id": pd.Series(dtype="int64"),
            "member": pd.Series(dtype="object"),
            "lcoe_nominal": pd.Series(dtype="float64"),
        }
    )


def nominal_by_member_frame(cell_set: CellSet, evaluation: Evaluation) -> pd.DataFrame:
    """The nominal LCOE of every cell of the F7 set in `m0` and every core member; null where the cell is infeasible in the member."""
    members = [evaluation.reference, *evaluation.members]
    frames = []
    for slot, member in enumerate(members):
        values = evaluation.nominal_lcoe[:, slot]
        frames.append(
            pd.DataFrame(
                {
                    "cell_id": cell_set.f7_ids,
                    "member": np.full(cell_set.n_f7, member, dtype=object),
                    "lcoe_nominal": pd.Series(values).where(np.isfinite(values), np.nan),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def futures_frame(
    cell_set: CellSet,
    evaluation: Evaluation,
    futures: FuturesResult,
    labels: Sequence[MemberLabel],
    design: pd.DataFrame,
    parameter_names: Sequence[str],
    factor_means: pd.DataFrame,
) -> pd.DataFrame:
    """One row per future `(m, s)`, sample 0 the nominal vector: descriptors, reference level and the sample-major reductions.

    Implements: M-F7-08 (the PRIM input), U-08.

    Args:
        design: The design matrix (`sample` index, one column per uncertain parameter).
        parameter_names: The uncertain parameters, in registry order.
        factor_means: `delta_rsds`, `dT`, `delta_wind` averaged over the F7 set, indexed by member.
    """
    n_samples = evaluation.lowest.shape[1]
    parameters = design.loc[:, list(parameter_names)].reset_index(drop=True)
    frames = []
    for j, label in enumerate(labels):
        frame = parameters.copy()
        frame.insert(0, "sample", np.arange(n_samples))
        frame.insert(0, "member", label.member)
        frame.insert(2, "gcm", label.gcm)
        frame.insert(3, "ssp", label.ssp)
        means = factor_means.loc[label.member]
        frame.insert(4, "delta_rsds_mean", float(means["delta_rsds"]))
        frame.insert(5, "dT_mean", float(means["dT"]))
        frame.insert(6, "delta_wind_mean", float(means["delta_wind"]))
        frame.insert(7, "lowest_lcoe", evaluation.lowest[1 + j])
        frame.insert(8, "share_nominal_top_k_leaving", futures.share_leaving[j])
        frame.insert(9, "jaccard_with_nominal_top_k", futures.jaccard_nominal[j])
        frame.insert(
            10,
            "potential_below_tau_gw",
            evaluation.potential_gw[1 + j]
            if evaluation.potential_gw is not None
            else pd.Series([pd.NA] * n_samples, dtype="Float64"),
        )
        frame.insert(
            11,
            "potential_below_tau_twh",
            evaluation.potential_twh[1 + j]
            if evaluation.potential_twh is not None
            else pd.Series([pd.NA] * n_samples, dtype="Float64"),
        )
        frames.append(frame)
    assert len(labels) == len(evaluation.members) == len(cell_set.core)
    return pd.concat(frames, ignore_index=True)


def draw_statistics_frame(futures: FuturesResult) -> pd.DataFrame:
    """The per-draw statistics of the sample-major pass in long form (sample 0 is the nominal vector)."""
    frames = []
    for name, values in futures.draw_statistics.items():
        finite = np.isfinite(values)
        frames.append(
            pd.DataFrame(
                {
                    "sample": np.arange(values.size),
                    "statistic": name,
                    "value": pd.Series(np.where(finite, values, np.nan)),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def hypothesis_frame(
    statistics: Sequence[Statistic], verdicts: Sequence[dict], window: str
) -> pd.DataFrame:
    """The statistics of H1 to H5 with the rule that names each one and its result (M-F7-07, OQ-050)."""
    rows = []
    for stat, verdict in zip(statistics, verdicts, strict=True):
        rows.append(
            {
                "hypothesis": stat.hypothesis,
                "statistic": stat.statistic,
                "window": window,
                "value": stat.value,
                "p10": stat.p10,
                "p50": stat.p50,
                "p90": stat.p90,
                "range_axis": stat.range_axis,
                "n_cells": stat.n_cells,
                "k": stat.k,
                "top_k_truncated": stat.top_k_truncated,
                "note": stat.note,
                "rule": verdict["rule"],
                "verdict": verdict["verdict"],
                "verdict_reason": verdict["verdict_reason"],
            }
        )
    return pd.DataFrame(rows)


def prim_input(
    futures: pd.DataFrame, parameter_names: Sequence[str], theta: float
) -> tuple[pd.DataFrame, np.ndarray]:
    """The descriptors and the binary outcome of PRIM: the draws `s >= 1`, outcome "the share of the nominal top-k that leaves is at least `theta`".

    Implements: M-F7-08, D-F7-021.

    Integer-valued parameters are cast to real (the own PRIM supports real and categorical descriptors).
    """
    draws = futures[futures["sample"] >= 1].reset_index(drop=True)
    real = [*parameter_names, "delta_rsds_mean", "dT_mean", "delta_wind_mean"]
    x = draws[real].astype("float64")
    x["gcm"] = draws["gcm"].astype(str)
    x["ssp"] = draws["ssp"].astype(str)
    share = draws["share_nominal_top_k_leaving"].to_numpy(dtype="float64")
    return x, (share >= theta).astype(int)


def prim_frame(result: PrimResult, theta: float) -> pd.DataFrame:
    """The trajectory of the first PRIM box, one row per box, with the limits of every descriptor."""
    rows = []
    for step in result.steps:
        row: dict[str, object] = {
            "step": step.step,
            "coverage": step.coverage,
            "density": step.density,
            "mass": step.mass,
            "n": step.n,
            "k": step.k,
            "n_restricted": step.n_restricted,
            "theta": theta,
        }
        for name in result.real_descriptors:
            row[f"{name}__min"] = step.lower[name]
            row[f"{name}__max"] = step.upper[name]
        for name in result.categorical_descriptors:
            row[f"{name}__in"] = "|".join(step.categories[name])
        rows.append(row)
    return pd.DataFrame(rows)


def ssp_scores_frame(cell_set: CellSet, detail: H1Detail) -> pd.DataFrame:
    """The scores of every cell of the F7 set in every SSP (`MR_i,sigma`, `R^clim_i,sigma`, ranks, top-k flag), null for a cell without a rank."""
    frames = []
    scores = detail.scores
    for s, ssp in enumerate(scores.ssps):
        has_rank = detail.mr_rank[s] > 0
        gcm = np.asarray(scores.gcms, dtype=object)[scores.r_clim_gcm[s]]
        frames.append(
            pd.DataFrame(
                {
                    "cell_id": cell_set.f7_ids,
                    "ssp": np.full(cell_set.n_f7, ssp, dtype=object),
                    "mr_ssp": _nullable(scores.mr[s], has_rank, "float64"),
                    "mr_ssp_rank": _nullable(detail.mr_rank[s], has_rank, "Int64"),
                    "topk_ssp": _nullable(detail.top_k[s], has_rank, "boolean"),
                    "r_clim_ssp": _nullable(scores.r_clim[s], has_rank, "float64"),
                    "r_clim_ssp_rank": _nullable(detail.clim_rank[s], has_rank, "Int64"),
                    "r_clim_gcm": pd.Series(gcm, dtype=object).where(pd.Series(has_rank), None),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def h1_sites_frame(cell_set: CellSet, inputs: H1Inputs, detail: H1Detail) -> pd.DataFrame:
    """One row per nominal top-k cell: whether it is vulnerable (H1b) and the magnitude of its loss of position."""
    sites = np.flatnonzero(detail.nominal_top)
    has_rank = ~np.isnan(detail.displacement[sites])
    ssps = np.asarray(detail.scores.ssps, dtype=object)
    gcms = np.asarray(detail.scores.gcms, dtype=object)
    reason = np.where(
        ~has_rank,
        "climate_fragile",
        np.where(detail.vulnerable[sites], "beyond_top_k_plus_m", None),
    )
    return pd.DataFrame(
        {
            "cell_id": cell_set.f7_ids[sites],
            "nominal_rank": inputs.nominal_rank[sites].astype("int64"),
            "vulnerable": detail.vulnerable[sites],
            "reason": pd.Series(reason, dtype=object),
            "displacement": _nullable(np.nan_to_num(detail.displacement[sites]), has_rank, "Int64"),
            "worst_ssp": pd.Series(
                ssps[np.maximum(detail.worst_ssp[sites], 0)], dtype=object
            ).where(pd.Series(has_rank), None),
            "worst_gcm": pd.Series(
                gcms[np.maximum(detail.worst_gcm[sites], 0)], dtype=object
            ).where(pd.Series(has_rank), None),
            "max_r_clim": _nullable(np.nan_to_num(detail.max_r_clim[sites]), has_rank, "float64"),
        }
    ).sort_values("nominal_rank", ignore_index=True)


def h1_summary_frame(
    variants: Sequence[H1Variant], window: str, alpha: float, beta: float
) -> pd.DataFrame:
    """The primary result of H1 and its sensitivities, one row each (D-F7-037); the first variant is the primary one."""
    return pd.DataFrame(
        [
            {
                "variant": v.variant,
                "primary": i == 0,
                "window": window,
                "top_k_percent": v.top_k_percent,
                "k": v.k,
                "m": v.m,
                "excluded_gcms": "|".join(v.excluded_gcms),
                "n_cells": v.n_cells,
                "n_ranked": v.n_ranked,
                "n_ssps": v.n_ssps,
                "core_size": v.core_size,
                "n_vulnerable": v.n_vulnerable,
                "c_k": v.c_k,
                "v_k": v.v_k,
                "reference": v.reference,
                "alpha": alpha,
                "beta": beta,
                "h1a_holds": v.h1a_holds,
                "h1b_holds": v.h1b_holds,
                "verdict": v.verdict,
            }
            for i, v in enumerate(variants)
        ]
    )


def h2_summary_frame(variants: Sequence[H2Variant], window: str, partition: str) -> pd.DataFrame:
    """The primary result of H2, the decision profile and the sensitivities, one row each (D-F7-040); the first variant is the primary one."""
    return pd.DataFrame(
        [
            {
                "variant": v.variant,
                "primary": i == 0,
                "window": window,
                "partition": partition,
                "region_statistic": v.region_statistic,
                "top_k_percent": v.top_k_percent,
                "k": v.k,
                "excluded_gcms": "|".join(v.excluded_gcms),
                "gamma": v.gamma,
                "n_ranked": v.n_ranked,
                "n_regions": v.n_regions,
                "target_mw": v.target_mw,
                "q_max_mw": v.q_max_mw,
                "overlap": v.overlap,
                "overlap_ref": v.overlap_ref,
                "testable": v.testable,
                "verdict": v.verdict,
                "robustness_penalty": v.robustness_penalty,
                "tv_distance": v.tv_distance,
                "iqr_over_median": v.iqr_over_median,
                "smallest_supporting_gamma": v.smallest_supporting_gamma,
                "target_unreachable": v.target_unreachable,
            }
            for i, v in enumerate(variants)
        ]
    ).astype({"top_k_percent": "float64", "k": "Int64"})


def h2_regions_frame(detail: H2Detail) -> pd.DataFrame:
    """One row per Admin1 region of the primary H2 result, in the order the regional selection takes them."""
    return pd.DataFrame(
        [
            {
                "region": r.region,
                "n_cells": r.n_cells,
                "capacity_mw": r.capacity_mw,
                "mean_z": r.mean_z,
                "median_z": r.median_z,
                "within_variance": r.within_variance,
                "position": r.position,
                "fraction_taken": r.fraction_taken,
                "selected_cell_mw": r.selected_cell_mw,
                "selected_admin_mw": r.selected_admin_mw,
                "share_cell": r.share_cell,
                "share_admin": r.share_admin,
            }
            for r in detail.regions
        ]
    )


def h3_summary_frame(variants: Sequence[H3Variant], window: str) -> pd.DataFrame:
    """The primary result of H3 and the sensitivities, one row each (D-F7-044); the first variant is the primary one."""
    return pd.DataFrame(
        [
            {
                "variant": v.variant,
                "primary": i == 0,
                "window": window,
                "top_k_percent": v.top_k_percent,
                "k": v.k,
                "m": v.m,
                "tolerance_multiple": v.tolerance_multiple,
                "excluded_gcms": "|".join(v.excluded_gcms),
                "delta": v.delta,
                "n_cells": v.n_cells,
                "n_ranked": v.n_ranked,
                "top_k_truncated": v.top_k_truncated,
                "robust_capacity_mw": v.robust_capacity_mw,
                "nominal_capacity_mw": v.nominal_capacity_mw,
                "outside_capacity_mw": v.outside_capacity_mw,
                "n_outside": v.n_outside,
                "d": v.d,
                "d_ref": v.d_ref,
                "testable": v.testable,
                "verdict": v.verdict,
                "robust_lcoe_mean": v.robust_lcoe_mean,
                "nominal_lcoe_mean": v.nominal_lcoe_mean,
                "robust_mr_mean": v.robust_mr_mean,
                "nominal_mr_mean": v.nominal_mr_mean,
                "price_of_robustness": v.price_of_robustness,
                "benefit_of_robustness": v.benefit_of_robustness,
                "centroid_distance_km": v.centroid_distance_km,
                "tv_distance": v.tv_distance,
                "spearman_lcoe_mr": v.spearman_lcoe_mr,
                "jaccard": v.jaccard,
            }
            for i, v in enumerate(variants)
        ]
    ).astype(
        {
            "top_k_percent": "float64",
            "robust_lcoe_mean": "float64",
            "nominal_lcoe_mean": "float64",
            "robust_mr_mean": "float64",
            "nominal_mr_mean": "float64",
            "price_of_robustness": "float64",
            "benefit_of_robustness": "float64",
            "centroid_distance_km": "float64",
            "tv_distance": "float64",
            "spearman_lcoe_mr": "float64",
        }
    )


def h3_sites_frame(inputs: H3Inputs, detail: H3Detail) -> pd.DataFrame:
    """One row per cell of the union of the robust and the nominal shortlists: scores, ranks, membership and whether the capacity counts in `D`."""
    sites = np.flatnonzero(detail.robust | detail.nominal)
    return pd.DataFrame(
        {
            "cell_id": inputs.cell_id[sites].astype("int64"),
            "admin1_id": pd.Series(inputs.region[sites].astype(str), dtype=object),
            "lat_c": inputs.lat[sites].astype("float64"),
            "lon_c": inputs.lon[sites].astype("float64"),
            "capacity_mw": inputs.q[sites].astype("float64"),
            "lcoe_f0": inputs.lcoe[sites].astype("float64"),
            "mr": detail.z[sites].astype("float64"),
            "nominal_rank": detail.nominal_rank[sites].astype("int64"),
            "robust_rank": detail.robust_rank[sites].astype("int64"),
            "in_robust": detail.robust[sites],
            "in_nominal": detail.nominal[sites],
            "within_tolerance": detail.within_tolerance[sites],
            "counts_in_d": detail.beyond[sites],
        }
    ).sort_values(["robust_rank", "nominal_rank"], ignore_index=True)


def h4_country_frame(variants: Sequence[H4Variant], window: str) -> pd.DataFrame:
    """The profile of the country (primary row), the climate axis by SSP, the sensitivities and the boundary variants, one row each (D-F7-047)."""
    return pd.DataFrame(
        [
            {
                "variant": v.variant,
                "primary": i == 0,
                "window": window,
                "top_k_percent": v.top_k_percent,
                "k": v.k,
                "m": v.m,
                "tolerance_multiple": v.tolerance_multiple,
                "excluded_gcms": "|".join(v.excluded_gcms),
                "ssp": v.ssp,
                "lower": v.lower,
                "upper": v.upper,
                "n_cells": v.n_cells,
                "n_ranked": v.n_ranked,
                "top_k_truncated": v.top_k_truncated,
                "clim_capacity_mw": v.clim_capacity_mw,
                "tec_capacity_mw": v.tec_capacity_mw,
                "d_clim": v.d_clim,
                "d_tec": v.d_tec,
                "d_sum": v.d_sum,
                "rho": v.rho,
                "profile": v.profile,
                "d_joint": v.d_joint,
                "distance_to_lower": v.distance_to_lower,
                "distance_to_upper": v.distance_to_upper,
            }
            for i, v in enumerate(variants)
        ]
    ).astype(
        {
            "top_k_percent": "float64",
            "rho": "float64",
            "distance_to_lower": "float64",
            "distance_to_upper": "float64",
            "ssp": "object",
        }
    )


def _scenario_of(variant: H5Variant, default: str) -> str:
    """The land scenario of a row: the `land_<scenario>` rows are the other scenarios, every other row keeps the one of the primary result."""
    return variant.variant.removeprefix("land_") if variant.variant.startswith("land_") else default


def h5_summary_frame(
    variants: Sequence[H5Variant], window: str, land_scenario: str = "central"
) -> pd.DataFrame:
    """The primary result of H5 and its sensitivities, one row each (D-F7-051); the first variant is the primary one."""
    return pd.DataFrame(
        [
            {
                "variant": v.variant,
                "primary": i == 0,
                "window": window,
                "land_scenario": _scenario_of(v, land_scenario),
                "lam": v.lam,
                "tau_usd_per_mwh": v.tau,
                "domain": v.domain,
                "conversion": v.conversion,
                "excluded_gcms": "|".join(v.excluded_gcms),
                "channels": "|".join(v.channels),
                "status": v.status,
                "verdict": v.verdict,
                "verdict_reason": v.verdict_reason,
                "n_domain_cells": v.n_domain_cells,
                "domain_capacity_gw": v.domain_capacity_gw,
                "e0_twh": v.e0_twh,
                "target_value": v.target_value,
                "target_unit": v.target_unit,
                "target_horizon": v.target_horizon,
                "target_source": v.target_source,
                "g_twh": v.g_twh,
                "cf_bar": v.cf_bar,
                "target_exceeds_domain": v.target_exceeds_domain,
                "h0_twh": v.h0_twh,
                "delta_e_twh": v.delta_e_twh,
                "member_min": v.member_min,
                "r_loss": v.r_loss,
                "h5a_holds": v.h5a_holds,
                "max_gain_twh": v.max_gain_twh,
                "median_change_twh": v.median_change_twh,
                "exposure_available": v.exposure_available,
                "exposure_reason": v.exposure_reason,
                "e_exp_twh": v.e_exp_twh,
                "member_exp_max": v.member_exp_max,
                "r_exp": v.r_exp,
                "h5b_holds": v.h5b_holds,
                "e_exp_comparable_twh": v.e_exp_comparable_twh,
                "e_exp_reference_twh": v.e_exp_reference_twh,
                "exposure_increment_twh": v.exposure_increment_twh,
                "reference_channels": "|".join(v.reference_channels),
                "delta_e_over_g": v.delta_e_over_g,
                "e_exp_over_g": v.e_exp_over_g,
            }
            for i, v in enumerate(variants)
        ]
    ).astype(
        {
            "verdict": "object",
            "verdict_reason": "object",
            "target_value": "float64",
            "target_unit": "object",
            "target_horizon": "Int64",
            "target_source": "object",
            "g_twh": "float64",
            "cf_bar": "float64",
            "h0_twh": "float64",
            "r_loss": "float64",
            "h5a_holds": "object",
            "exposure_reason": "object",
            "e_exp_twh": "float64",
            "member_exp_max": "object",
            "r_exp": "float64",
            "h5b_holds": "object",
            "e_exp_comparable_twh": "float64",
            "e_exp_reference_twh": "float64",
            "exposure_increment_twh": "float64",
            "delta_e_over_g": "float64",
            "e_exp_over_g": "float64",
        }
    )


def h5_members_frame(
    variant: H5Variant,
    window: str,
    labels: Mapping[str, tuple[str, str]],
    land_scenario: str = "central",
) -> pd.DataFrame:
    """H5 per member in the primary setting: the energy of the fixed domain, its change against `E_0` and the exposed energy (D-F7-051).

    Args:
        variant: The primary result.
        window: The window name.
        labels: Member -> (GCM, SSP).
        land_scenario: The land scenario of the result.
    """
    hazard = dict(zip(variant.hazard_members, variant.exposed_by_member_twh, strict=True))
    reference = (
        dict(zip(variant.hazard_members, variant.exposed_reference_by_member_twh, strict=True))
        if variant.exposed_reference_by_member_twh
        else {}
    )
    rows = []
    for member, energy in zip(variant.members, variant.member_energy_twh, strict=True):
        gcm, ssp = labels[member]
        rows.append(
            {
                "member": member,
                "gcm": gcm,
                "ssp": ssp,
                "window": window,
                "land_scenario": land_scenario,
                "e0_twh": variant.e0_twh,
                "energy_twh": energy,
                "change_twh": energy - variant.e0_twh,
                "attains_min": member == variant.member_min,
                "carries_hazard_channel": member in hazard,
                "exposed_twh": hazard.get(member),
                "exposed_reference_twh": reference.get(member),
                "attains_exposure_max": member == variant.member_exp_max,
            }
        )
    return pd.DataFrame(rows).astype({"exposed_twh": "float64", "exposed_reference_twh": "float64"})
