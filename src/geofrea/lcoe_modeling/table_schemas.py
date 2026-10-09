"""Row schemas and schema version of the F6 tables (A-07, M-F6-04, M-F6-06; D-F6-013)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

LCOE_TABLE_SCHEMA_VERSION = "1.0"


class LcoeSummaryRow(BaseModel):
    """LCOE of one cell in one member, USD2024/MWh (M-F6-04).

    `lcoe_nominal` is the nominal parameter vector `s0` and enters no statistic. Mean, variance (`ddof = 1`), p10, p50 and p90 are
    taken over the Latin hypercube draws `s >= 1`; the mean and the variance run over the finite draws, the quantiles over all of them
    (a zero-energy draw is `+inf`, D-F6-007). `n_nonfinite` counts the non-finite draws; `lcoe_mean` and `lcoe_var` are null when no
    finite draw (two for the variance) exists.
    """

    model_config = ConfigDict(extra="forbid")

    cell_id: int
    member: str
    lcoe_nominal: float
    lcoe_mean: float | None
    lcoe_var: float | None
    lcoe_p10: float
    lcoe_p50: float
    lcoe_p90: float
    n_nonfinite: int


class LcoeNominalRow(BaseModel):
    """The nominal LCOE (sample `s0`, no draws) of one cell in one member for a land scenario other than the central one (M-F6-06, D-F6-018)."""

    model_config = ConfigDict(extra="forbid")

    cell_id: int
    member: str
    lcoe_nominal: float


class DesignMatrixRow(BaseModel):
    """One parameter sample; the columns after `sample` are the uncertain parameters of the technology (M-F6-02).

    `sample` 0 is the nominal vector `s0`; the draws are `sample >= 1`. Extra columns are the uncertain parameters, which depend on
    the technology registry.
    """

    model_config = ConfigDict(extra="allow")

    sample: int


class SupplyCurveRow(BaseModel):
    """One step of the nominal supply curve of a member: cells in increasing nominal LCOE, with cumulative capacity and energy."""

    model_config = ConfigDict(extra="forbid")

    member: str
    rank: int
    cell_id: int
    lcoe_nominal: float
    cum_P_GW: float
    cum_E_TWh: float
