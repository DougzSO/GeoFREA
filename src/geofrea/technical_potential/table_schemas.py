"""Row schemas and schema version of the F5 tables (A-07, M-F5-06)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

POTENTIAL_TABLE_SCHEMA_VERSION = "1.0"
ENSEMBLE_TABLE_SCHEMA_VERSION = "1.0"
CLASS_FLAG_TABLE_SCHEMA_VERSION = "1.2"  # 1.1: the ISA density-ratio columns (M-F5-03); 1.2: the Weibull flag column of 1.1 is gone (OQ-053 closed)


class PotentialRow(BaseModel):
    """Capacity, capacity factor and annual energy of one cell in one member (M-F5-06).

    A cell-member declared in `forcing_masked.parquet` has no row (M-F4-07). `P_MW` is the same in every member of a cell.
    """

    model_config = ConfigDict(extra="forbid")

    cell_id: int
    member: str
    P_MW: float
    CF: float
    E_MWh: float


class EnsembleRow(BaseModel):
    """How many members of the ensemble a candidate cell has (OQ-069, D-F5-041).

    `n_expected` is the members of the technology, `m0` included (those whose `members.yaml` channels include the ones its capacity-factor
    model reads); `n_members` is the number that have a row for the cell in `potential_<tech>__<scenario>.parquet`. A cell with fewer is
    `incomplete_ensemble`: some of its cell-members are masked (M-F4-07). The cell stays in F5 and F6 with the members it has; F7 does not analyse it.
    """

    model_config = ConfigDict(extra="forbid")

    cell_id: int
    n_members: int
    n_expected: int
    incomplete_ensemble: bool


class PotentialAggregateRow(BaseModel):
    """Country totals of one member in one land scenario, in two series (M-F5-06, D-F5-006).

    The *all present cells* series sums the cells that have a row in the member. The *like-for-like* series sums the cells present
    in every member of the scenario, so a member is compared with `m0` over the same cells; the climate effect uses it.
    """

    model_config = ConfigDict(extra="forbid")

    scenario: str
    member: str
    n_cells: int
    n_cells_absent: int
    n_cells_like_for_like: int
    eligible_area_km2: float
    P_GW: float
    E_TWh: float
    cf_energy_weighted: float | None
    P_GW_like_for_like: float
    E_TWh_like_for_like: float
    delta_E_pct_vs_m0_like_for_like: float | None


class ClassFlagRow(BaseModel):
    """The design-class screening flag of one candidate cell (M-F5-03): the reference mean speed of the flag layer and whether it
    exceeds the class limit. Fixed across members; it changes neither the capacity factor nor the eligibility."""

    model_config = ConfigDict(extra="forbid")

    cell_id: int
    v_ave_ms: float
    exceeds_class: bool
    density_ratio_isa: float  # rho_ref / rho_ISA(z + hub height), reported only (M-F5-03)
    density_outside_isa_check: bool  # that ratio outside [0.90, 1.10]
