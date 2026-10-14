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
    displaced_capacity_share: float | None
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


class PrimBoxRow(BaseModel):
    """One box of the peeling and pasting trajectory of the primary PRIM search (M-F7-08, D-F7-021, D-F7-054): its statistics and its limits.

    Step 0 is the box with every future. The limits are extra columns: `<descriptor>__min` and `<descriptor>__max` for a real descriptor,
    `<descriptor>__in` for a categorical one (the categories the box keeps, joined by `|`). `theta` is the capacity share of the nominal shortlist
    beyond the tolerance at which a future counts as of interest. `selected` marks the box the pre-registered rule chooses (null of the
    special cases: no box is marked).
    """

    model_config = ConfigDict(extra="allow")

    step: int
    coverage: float
    density: float
    mass: float
    n: int
    k: int
    n_restricted: int
    theta: float
    selected: bool


class SspScoreRow(BaseModel):
    """The scores of one cell of the F7 set in one SSP (H1, D-F7-035): `MR_i,sigma`, `R^clim_i,sigma`, their ranks and the top-k flag.

    The ranks are among the ranked set (1 is best); the scores, ranks and flag are null for a climate-fragile cell. `r_clim_gcm` is the GCM
    whose regret at `s0` is the largest in the SSP (the one that sets `R^clim_i,sigma`).
    """

    model_config = ConfigDict(extra="forbid")

    cell_id: int
    ssp: str
    mr_ssp: float | None
    mr_ssp_rank: int | None
    topk_ssp: bool | None
    r_clim_ssp: float | None
    r_clim_ssp_rank: int | None
    r_clim_gcm: str | None


class H1SiteRow(BaseModel):
    """One cell of the nominal top-k and what H1b says about it (D-F7-036).

    `vulnerable` is true when the cell is outside the top `k + m` of the climate-only ranking in at least one SSP, or has no rank
    (`reason` `climate_fragile`). The magnitude (`displacement` = worst `r^clim` rank minus the nominal rank, the SSP and the GCM that set it, the
    largest `R^clim`) is reported for every cell with a rank, vulnerable or not, and carries no threshold.
    """

    model_config = ConfigDict(extra="forbid")

    cell_id: int
    nominal_rank: int
    vulnerable: bool
    reason: str | None
    displacement: int | None
    worst_ssp: str | None
    worst_gcm: str | None
    max_r_clim: float | None


class H1SummaryRow(BaseModel):
    """H1 for one setting: `variant` `primary` carries the verdict, the others are sensitivities (D-F7-037).

    `excluded_gcms` is the list joined by `|` (empty for none). `reference` is `(k / n)^2`, the expected core share if the SSP rankings were
    independent. `rule` is the pre-registered rule as applied. A sensitivity is reported beside the primary result and never revises it.
    """

    model_config = ConfigDict(extra="forbid")

    variant: str
    primary: bool
    window: str
    top_k_percent: float
    k: int
    m: int
    excluded_gcms: str
    n_cells: int
    n_ranked: int
    n_ssps: int
    core_size: int
    n_vulnerable: int
    c_k: float
    v_k: float
    reference: float
    alpha: float
    beta: float
    h1a_holds: bool
    h1b_holds: bool
    verdict: str


class H2SummaryRow(BaseModel):
    """H2 for one setting: `variant` `primary` carries the verdict, the `gamma_*` rows are the decision profile, the others sensitivities (D-F7-040).

    `overlap` is the Capacity Overlap Index `O`, `overlap_ref` is `T / Q_max`, the overlap of a uniform spread over the country; the verdict is
    `not_testable` when `overlap_ref >= gamma`. `excluded_gcms` is joined by `|`. `smallest_supporting_gamma` is the smallest `gamma` of the
    profile under which H2 would be supported (null if none). A sensitivity never revises the verdict.
    """

    model_config = ConfigDict(extra="forbid")

    variant: str
    primary: bool
    window: str
    partition: str
    region_statistic: str
    top_k_percent: float | None
    k: int | None
    excluded_gcms: str
    gamma: float
    n_ranked: int
    n_regions: int
    target_mw: float
    q_max_mw: float
    overlap: float
    overlap_ref: float
    testable: bool
    verdict: str
    robustness_penalty: float
    tv_distance: float
    iqr_over_median: float | None
    smallest_supporting_gamma: float | None
    target_unreachable: bool


class H2RegionRow(BaseModel):
    """One Admin1 region in the primary H2 result: capacity, score statistics, the fraction taken and the shares of `T` by procedure (D-F7-041)."""

    model_config = ConfigDict(extra="forbid")

    region: str
    n_cells: int
    capacity_mw: float
    mean_z: float
    median_z: float
    within_variance: float
    position: int
    fraction_taken: float
    selected_cell_mw: float
    selected_admin_mw: float
    share_cell: float
    share_admin: float


class H3SummaryRow(BaseModel):
    """H3 for one setting: `variant` `primary` carries the verdict, the others are sensitivities (D-F7-044).

    `d` is the share of the capacity of the robust shortlist `S_k` whose nominal rank exceeds `k + m`, `d_ref` is `1 - (k + m) / |I|`, the
    share for unrelated rankings; the verdict is `not_testable` when `d_ref < delta`. `price_of_robustness` is the relative increase of the
    capacity-weighted LCOE at `f0` from the nominal to the robust shortlist and `benefit_of_robustness` the reduction of the
    capacity-weighted `MR`; neither has a verdict. `excluded_gcms` is joined by `|`. A sensitivity never revises the verdict.
    """

    model_config = ConfigDict(extra="forbid")

    variant: str
    primary: bool
    window: str
    top_k_percent: float
    k: int
    m: int
    tolerance_multiple: float
    excluded_gcms: str
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


class H3SiteRow(BaseModel):
    """One cell of the union of the robust and the nominal shortlists of H3 (D-F7-045).

    The ranks are among the ranked set (1 is best). `counts_in_d` is true for a robust cell whose nominal rank exceeds `k + m`;
    `within_tolerance` for a robust cell ranked from `k + 1` to `k + m`, whose capacity is not counted.
    """

    model_config = ConfigDict(extra="forbid")

    cell_id: int
    admin1_id: str
    lat_c: float
    lon_c: float
    capacity_mw: float
    lcoe_f0: float
    mr: float
    nominal_rank: int
    robust_rank: int
    in_robust: bool
    in_nominal: bool
    within_tolerance: bool
    counts_in_d: bool


class H4CountryRow(BaseModel):
    """H4 for one country, technology, window and setting: `variant` `primary` carries the profile (D-F7-047).

    `d_clim` and `d_tec` are the H3 statistic on the shortlists of the climate-only and the techno-economic-only score, `rho` is
    `d_clim / d_sum` (null when `d_sum` is 0, profile `no_displacement`), `d_joint` the statistic of H3 on the joint shortlist. The profile uses
    the boundaries `lower` and `upper` of the row. `ssp` is set on the rows that keep the members of one SSP in the climate axis,
    `excluded_gcms` is joined by `|`. A sensitivity or a reading by SSP never revises the profile of the primary row.
    """

    model_config = ConfigDict(extra="forbid")

    variant: str
    primary: bool
    window: str
    top_k_percent: float
    k: int
    m: int
    tolerance_multiple: float
    excluded_gcms: str
    ssp: str | None
    lower: float
    upper: float
    n_cells: int
    n_ranked: int
    top_k_truncated: bool
    clim_capacity_mw: float
    tec_capacity_mw: float
    d_clim: float
    d_tec: float
    d_sum: float
    rho: float | None
    profile: str
    d_joint: float
    distance_to_lower: float | None
    distance_to_upper: float | None


class H4VerdictRow(BaseModel):
    """The verdict of H4 for one technology and window across countries (D-F7-049): one row per country and one row `ALL` (`kind` `technology`).

    A `country` row carries the profile and the statistics read from the primary row of its `h4_country` table, or `available` false and the
    `reason` (an empty table with the question that blocks it, or no table). The `technology` row carries the count of countries by profile
    and the `verdict` (`supported`, `not_supported`, `not_testable`) with its `reason`.
    """

    model_config = ConfigDict(extra="forbid")

    kind: str
    country: str
    window: str
    available: bool
    profile: str | None
    d_clim: float | None
    d_tec: float | None
    d_sum: float | None
    rho: float | None
    n_countries: int | None
    n_available: int | None
    n_climate_dominated: int | None
    n_techno_economic_dominated: int | None
    n_mixed: int | None
    n_no_displacement: int | None
    verdict: str | None
    reason: str | None


class H5SummaryRow(BaseModel):
    """H5 for one country, technology, window, land scenario and setting: `variant` `primary` carries the verdict (D-F7-051).

    `e0_twh` is the baseline economic potential of the fixed domain, `g_twh` the target in TWh/year (the original value, unit, horizon and
    source beside it, and `cf_bar` the capacity factor of the conversion of a target in GW), `h0_twh = e0_twh - g_twh` the slack. H5a is
    `delta_e_twh` (the largest reduction of the domain energy over the members, at least 0) and `r_loss = delta_e_twh / h0_twh`; H5b is
    `e_exp_twh` (the largest exposed energy over the hazard members) and `r_exp = e_exp_twh / h0_twh`, with the same statistic for the reference
    indicators (`e_exp_reference_twh`, over the `reference_channels`) and the increment against the absolute one on the same channels. `status`
    is `tested`, `not_testable` (no target) or `target_not_met_at_reference` (`h0_twh <= 0`, ratios on `g_twh` only); the verdict is null unless
    the status is `tested` and H5b is available. `excluded_gcms` and `channels` are joined by `|`.
    """

    model_config = ConfigDict(extra="forbid")

    variant: str
    primary: bool
    window: str
    land_scenario: str
    lam: float
    tau_usd_per_mwh: float
    domain: str
    conversion: str
    excluded_gcms: str
    channels: str
    status: str
    verdict: str | None
    verdict_reason: str | None
    n_domain_cells: int
    domain_capacity_gw: float
    e0_twh: float
    target_value: float | None
    target_unit: str | None
    target_horizon: int | None
    target_source: str | None
    g_twh: float | None
    cf_bar: float | None
    target_exceeds_domain: bool
    h0_twh: float | None
    delta_e_twh: float
    member_min: str
    r_loss: float | None
    h5a_holds: bool | None
    max_gain_twh: float
    median_change_twh: float
    exposure_available: bool
    exposure_reason: str | None
    e_exp_twh: float | None
    member_exp_max: str | None
    r_exp: float | None
    h5b_holds: bool | None
    e_exp_comparable_twh: float | None
    e_exp_reference_twh: float | None
    exposure_increment_twh: float | None
    reference_channels: str
    delta_e_over_g: float | None
    e_exp_over_g: float | None


class H5MemberRow(BaseModel):
    """H5 for one member of the window, in the primary setting (D-F7-051): the energy of the fixed domain and the exposed energy.

    `change_twh` is `energy_twh - e0_twh` (negative: a loss); `attains_min` marks the member that sets `Delta E`. The exposed energy is null
    for a member without the hazard channel, never zero (L-021); `exposed_reference_twh` is null where there is no channel with a reference value;
    `attains_exposure_max` marks the member that sets `E_exp`.
    """

    model_config = ConfigDict(extra="forbid")

    member: str
    gcm: str
    ssp: str
    window: str
    land_scenario: str
    e0_twh: float
    energy_twh: float
    change_twh: float
    attains_min: bool
    carries_hazard_channel: bool
    exposed_twh: float | None
    exposed_reference_twh: float | None
    attains_exposure_max: bool


class PrimVariantRow(BaseModel):
    """The PRIM result of one setting of the core window: `variant` `primary` is the pre-registered one (M-F7-08, D-F7-055).

    `status` is `box_found`, `no_cases` (no future is of interest), `all_cases` (every future is) or `no_eligible_box` (no box meets the coverage
    requirement); the box columns are null unless a box was found. The limits of the box are extra columns (`<descriptor>__min` and `__max` for a
    real descriptor, `__in` for a categorical one) and `restricted` lists the descriptors it restricts, joined by `|`. `base_rate` is the share of the
    futures that are of interest.
    """

    model_config = ConfigDict(extra="allow")

    variant: str
    primary: bool
    status: str
    outcome_threshold: float
    min_coverage: float
    mass_min: float
    n_futures: int
    n_cases: int
    base_rate: float
    density: float | None
    coverage: float | None
    mass: float | None
    n: int | None
    k: int | None
    n_restricted: int | None
    restricted: str


class PrimBootstrapRow(BaseModel):
    """The stability of the primary box over the bootstrap replicates (M-F7-08, D-F7-056).

    `kind` is `density`, `coverage` or `mass` (percentiles over the replicates that found a box), `lower` or `upper` (the percentiles of the bound of a
    real descriptor over the replicates that restrict it), `restriction` (`frequency`: the share of those replicates that restrict the descriptor),
    `category` (`frequency`: the share of the replicates that restrict the descriptor that keep the category in `level`) or `status` (`frequency`: the
    share of all replicates with that status). `n_used` is the number of replicates behind the row.
    """

    model_config = ConfigDict(extra="forbid")

    kind: str
    name: str
    level: str
    p_low: float | None
    p50: float | None
    p_high: float | None
    frequency: float | None
    n_used: int
