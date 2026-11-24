"""Row schemas and schema version of the exploratory tables (A-07; DEC-098). Every table carries `exploratory: true` in its provenance."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

EXPLORATORY_TABLE_SCHEMA_VERSION = "1.0"
PROVENANCE_KEY = "geofrea_exploratory_provenance"


class H5cCurveRow(BaseModel):
    """MC and AC of one member at one level, for the nominal curves (`basis` nominal) or the per-cell P90 envelope (`basis` p90_envelope)."""

    model_config = ConfigDict(extra="forbid")

    basis: str
    level: str
    g_twh: float
    member: str
    gcm: str | None
    ssp: str | None
    mc: float | None
    ac: float | None
    d_mc: float | None
    d_ac: float | None
    level_unreachable: bool


class H5cSummaryRow(BaseModel):
    """The statistics of one level: MC and AC at the reference member, Delta_MC and Delta_AC (maximum, member, SSP, median, per SSP) and the label."""

    model_config = ConfigDict(extra="forbid")

    basis: str
    level: str
    g_twh: float
    g_share_of_total_m0: float | None
    mc_m0: float | None
    ac_m0: float | None
    reference_unreachable: bool
    n_core_members: int
    n_unreachable_members: int
    delta_mc_max: float | None
    delta_mc_member: str | None
    delta_mc_ssp: str | None
    delta_mc_median: float | None
    delta_mc_by_ssp: str
    delta_ac_max: float | None
    delta_ac_member: str | None
    delta_ac_ssp: str | None
    delta_ac_median: float | None
    delta_ac_by_ssp: str
    label: str | None


class VulnerabilityRow(BaseModel):
    """The cells of the F7 set (ranked and climate-fragile) with their vulnerability indices; the fragile cells have none (reported apart)."""

    model_config = ConfigDict(extra="forbid")

    cell_id: int
    cell_class: str
    lat_c: float
    lon_c: float
    p_mw: float | None
    lcoe_f0: float | None
    mr: float | None
    topk_nominal: bool | None
    n_failing_members: int
    vul_clim: float | None
    vul_tec: float | None
    vul: float | None
    vul_clim_upper_quartile: bool | None
    quadrant: str | None


class StatisticRow(BaseModel):
    """A `group`, `statistic` and `value` row: the summaries of VUL, the V_f diagnostic and the tau comparison."""

    model_config = ConfigDict(extra="forbid")

    group: str
    statistic: str
    value: float | None
    text: str | None


class TauCellRow(BaseModel):
    """tau of the IRENA reference plant, its recalculation on the cell basis, and the capacity of the F7 set at or below each."""

    model_config = ConfigDict(extra="forbid")

    tau_registered: float | None
    tau_reference: float
    tau_life_only: float
    tau_om_only: float
    tau_cell_basis: float
    tau_difference_reference: float | None
    tic_usd_per_kw: float
    cf_reference: float
    om_irena_usd_per_kw_yr: float
    om_f6_usd_per_kw_yr: float
    life_irena_years: float
    life_f6_years: float
    discount_rate: float
    capex_f6_usd_per_kw: float
    opex_fixed_frac_f6: float
    n_cells_f7_set: int
    capacity_gw_f7_set: float
    n_cells_below_registered: int | None
    capacity_gw_below_registered: float | None
    n_cells_below_cell_basis: int
    capacity_gw_below_cell_basis: float
