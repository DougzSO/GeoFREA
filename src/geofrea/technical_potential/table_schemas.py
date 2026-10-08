"""Row schemas and schema version of the F5 tables (A-07, M-F5-06)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

POTENTIAL_TABLE_SCHEMA_VERSION = "1.0"


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
