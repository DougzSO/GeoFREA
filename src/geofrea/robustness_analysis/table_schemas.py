"""Row schemas and schema version of the F7 tables (A-07, M-F7-11; D-F7-025)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

ROBUSTNESS_TABLE_SCHEMA_VERSION = "1.0"


class RobustnessRow(BaseModel):
    """One candidate cell: its class and, for the cells of the F7 set, the nominal and robust results (M-F7-11).

    The columns after `failing_members` are null for a cell outside the F7 set; the top-k flags are null when `top_k_percent` is null, the
    SR columns when `tau` is null, `topk_capacity_target` when the capacity target is null.
    """

    model_config = ConfigDict(extra="forbid")

    cell_id: int
    cell_class: str
    admin1_id: str
    lat_c: float
    lon_c: float
    p_mw: float | None
    lcoe_nominal: float | None
    nominal_rank: int | None
    mr: float | None
    sr: float | None
    robust_rank: int | None
    mr_clim: float | None
    mr_tech: float | None
    climate_only_rank: int | None
    techno_only_rank: int | None
    failing_members: list[str]
    n_failing_members: int
    var_total: float | None
    var_share_climate: float | None
    var_share_techno: float | None
    topk_nominal: bool | None
    topk_robust: bool | None
    topk_climate_only: bool | None
    topk_techno_only: bool | None
    topk_capacity_target: bool | None


class NominalByMemberRow(BaseModel):
    """The nominal LCOE (sample `s0`) of a cell of the F7 set in a member of the window, for H1 and T-R12."""

    model_config = ConfigDict(extra="forbid")

    cell_id: int
    member: str
    lcoe_nominal: float | None  # null where the cell is infeasible in the member (CF below CF_min)


class FutureRow(BaseModel):
    """One future `(m, s)`: its descriptors, its reference level and what the sample-major pass reduced (PRIM input, T-R6 ranges).

    The parameter values of the draw are extra columns (one per uncertain parameter of the technology).
    """

    model_config = ConfigDict(extra="allow")

    member: str
    sample: int
    gcm: str
    ssp: str
    delta_rsds_mean: float
    dT_mean: float
    delta_wind_mean: float
    lowest_lcoe: float
    share_nominal_top_k_leaving: float | None
    jaccard_with_nominal_top_k: float | None
    potential_below_tau_gw: float | None
    potential_below_tau_twh: float | None


class DrawStatisticRow(BaseModel):
    """One statistic of the sample-major pass for one draw (sample 0 is the nominal vector)."""

    model_config = ConfigDict(extra="forbid")

    sample: int
    statistic: str
    value: float | None


class HypothesisRow(BaseModel):
    """One statistic of H1 to H5 for one scale-independent run (M-F7-07; D-F7-014, D-F7-015).

    `value` is the central value (at `s0` where the statistic depends on the draws); `p10`, `p50` and `p90` are the range over the draws with
    the `range_axis` named (U-08), null for a statistic without draws. `rule` and `verdict` come from the pre-registered rules of
    `experiments.yaml` (OQ-050): both null, with `verdict_reason`, when the hypothesis has none.
    """

    model_config = ConfigDict(extra="forbid")

    hypothesis: str
    statistic: str
    window: str
    value: float | None
    p10: float | None
    p50: float | None
    p90: float | None
    range_axis: str | None
    n_cells: int
    k: int | None
    top_k_truncated: bool
    note: str | None
    rule: str | None
    verdict: str | None
    verdict_reason: str | None


class ExposureRow(BaseModel):
    """Potential (GW, TWh) in cells above the exposure threshold of one hazard indicator, for one member and one cell group (T-R10).

    `group` is `f7_set`, `nominal_top_k` or `robust_top_k`; `basis` is `absolute` (the indicator of the member) or `reference` (its `*_ref`
    value, the exposure of the reference climate).
    """

    model_config = ConfigDict(extra="forbid")

    hazard: str
    member: str
    gcm: str
    ssp: str
    group: str
    basis: str
    n_cells: int
    potential_gw: float
    potential_twh: float


class PotentialBelowTauRow(BaseModel):
    """Potential (GW, TWh) of the cells that are feasible with LCOE at most `tau`, per member (T-R12, H5).

    `series` is `like_for_like` (the F7 set) or `all_present`. `basis` is `nominal` (sample `s0`), or `p10`/`p50`/`p90` over the draws of
    the central land scenario (like-for-like only). `land_scenario` is the scenario the table comes from; draws exist only for `central`.
    `gap_to_target_gw` is the capacity target minus the potential, null without a target.
    """

    model_config = ConfigDict(extra="forbid")

    member: str
    land_scenario: str
    series: str
    basis: str
    potential_gw: float
    potential_twh: float
    gap_to_target_gw: float | None
