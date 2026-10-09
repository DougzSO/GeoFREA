"""The rankings of M-F7-05 and M-F7-06 and the per-cell table of M-F7-11, from the evaluation and the classes (D-F7-010 to D-F7-013)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from geofrea.robustness_analysis.cell_set import CellSet
from geofrea.robustness_analysis.decision import TechDecision
from geofrea.robustness_analysis.evaluator import Evaluation
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
