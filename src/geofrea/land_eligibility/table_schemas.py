"""Row schemas and schema version of the F3 tables (A-07). Technology-dependent columns (resources) are allowed extras."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

LAND_ELIGIBILITY_TABLE_SCHEMA_VERSION = "1.1"


class CellRow(BaseModel):
    """One 0.05 degree cell: geometry, areas, excluded areas per constraint, cost drivers and resource attributes (M-F3-03)."""

    model_config = ConfigDict(extra="allow")

    cell_id: int
    row: int
    col: int
    lat_c: float
    lon_c: float
    cell_area_km2: float
    eligible_area_km2: float
    excluded_area_km2_E1: float
    excluded_area_km2_E2: float
    excluded_area_km2_E3: float
    excluded_area_km2_E4: float
    excluded_area_km2_E5: float
    excluded_area_km2_E6: float
    dominant_exclusion: str | None
    dist_grid_km: float | None
    dist_road_km: float | None
    dist_grid_capped_share: float | None
    dist_road_capped_share: float | None
    admin1_id: str  # GADM level-1 unit with the largest area of the cell (M-F3-03, D-F3-012)


class Admin1UnitRow(BaseModel):
    """One admin1 unit with cells in the country: identifier, name, number of cells and their land area (D-F3-012)."""

    model_config = ConfigDict(extra="forbid")

    admin1_id: str
    admin1_name: str
    n_cells: int
    cell_area_km2: float


class CoarseCellRow(BaseModel):
    """One 0.1 degree cell, the exact sum of its 0.05 degree cells (M-F3-06)."""

    model_config = ConfigDict(extra="forbid")

    cell_0p1deg_id: int
    cell_area_km2: float
    eligible_area_km2: float
    excluded_area_km2_E1: float
    excluded_area_km2_E2: float
    excluded_area_km2_E3: float
    excluded_area_km2_E4: float
    excluded_area_km2_E5: float
    excluded_area_km2_E6: float
    n_cells_0p05deg: int


class CandidateStabilityRow(BaseModel):
    """A cell that is a candidate in at least one named scenario, with its area and candidacy per scenario (V1)."""

    model_config = ConfigDict(extra="allow")

    cell_id: int
    n_scenarios: int
    share_of_scenarios: float
