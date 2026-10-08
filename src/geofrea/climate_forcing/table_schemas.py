"""Row schemas and schema version of the F4 tables (A-07)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

CLIMATE_TABLE_SCHEMA_VERSION = "1.0"


class ForcingRow(BaseModel):
    """Change factors of one cell in one member (M-F4-06)."""

    model_config = ConfigDict(extra="forbid")

    cell_id: int
    member: str
    delta_rsds: float
    dT: float
    delta_wind: float


class ForcingMaskedRow(BaseModel):
    """A cell-member removed by the wind-factor validity mask (M-F4-07)."""

    model_config = ConfigDict(extra="forbid")

    cell_id: int
    member: str
    delta_wind: float
    reason: str


class HazardContextRow(BaseModel):
    """Hazard context indicators of one cell in one member (M-F4-05, M-F4-06); the indicator columns are listed by the model."""

    model_config = ConfigDict(extra="allow")

    cell_id: int
    member: str
