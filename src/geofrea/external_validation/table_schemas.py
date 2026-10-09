"""Row schemas and schema version of the F7b tables (A-07; D-F7b-002 to D-F7b-004)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

VALIDATION_TABLE_SCHEMA_VERSION = "1.0"


class ExclusionRow(BaseModel):
    """Excluded share of the pixels under existing plants for one constraint (M-F7b-01, D-F7b-002).

    `constraint` is `E1` to `E6` or `combined` (1 minus the eligible fraction of the pixel). `row_set` names the units kept: `operating` (all
    operating units) or a sensitivity set of the configuration (`vintage`, `accuracy`). The units outside the country grid and the units in
    a pixel the engine marks invalid are counted apart; the shares are over the units in valid pixels, weighted by capacity.
    `mean_excluded_share` is the primary statistic; `share_above_0`, `share_at_least_half` and `share_equal_1` are the capacity shares in
    pixels whose excluded share is above 0, at least 0.5 and 1.
    """

    model_config = ConfigDict(extra="forbid")

    technology: str
    row_set: str
    constraint: str
    n_units: int
    capacity_mw: float
    n_outside_grid: int
    capacity_outside_grid_mw: float
    n_invalid_pixel: int
    capacity_invalid_pixel_mw: float
    n_evaluated: int
    capacity_evaluated_mw: float
    mean_excluded_share: float | None
    share_above_0: float | None
    share_at_least_half: float | None
    share_equal_1: float | None


class EnrichmentRow(BaseModel):
    """Capacity of existing plants against the deciles of eligible area ordered by the nominal LCOE at `m0` (M-F7b-02, D-F7b-003).

    `kind` is `decile` (`decile` 1 to 10: the area and capacity in that decile alone) or `lowest` (`decile` d: the cumulative lowest d
    deciles, with `enrichment_ratio` = capacity share / area share, null when the area share is 0). The capacity shares are over the units
    in candidate cells; the capacity of units in cells that are not candidates is reported apart in `capacity_share_non_candidate` (over
    the units inside the grid).
    """

    model_config = ConfigDict(extra="forbid")

    technology: str
    row_set: str
    kind: str
    decile: int
    n_candidate_cells: int
    n_units_in_candidates: int
    eligible_area_share: float
    capacity_share: float | None
    enrichment_ratio: float | None
    capacity_share_non_candidate: float | None


class PublishedComparisonRow(BaseModel):
    """A published national estimate beside F5's central-scenario potential at `m0` (M-F7b-03, D-F7b-004).

    The F5 columns are the national sum over the cells of the central scenario, and the restrictive and permissive land scenarios give the
    interval. No number is computed from the published value; `definition_matches` says whether the estimate is a technical potential.
    """

    model_config = ConfigDict(extra="forbid")

    technology: str
    source: str
    year: int
    definition: str
    tier: str
    unit: str
    published_value: float
    f5_central_m0: float
    f5_restrictive_m0: float
    f5_permissive_m0: float
    definition_matches: bool
    note: str | None


class ValidationUnitRow(BaseModel):
    """One existing unit with where it falls and what the engine says about its pixel (the basis of T-R9)."""

    model_config = ConfigDict(extra="forbid")

    technology: str
    gem_unit_id: str | None
    capacity_mw: float
    start_year: float | None
    location_accuracy: str | None
    lat: float
    lon: float
    in_grid: bool
    valid_pixel: bool
    cell_id: int | None
    candidate: bool | None
    decile: int | None
    excluded_E1: float | None
    excluded_E2: float | None
    excluded_E3: float | None
    excluded_E4: float | None
    excluded_E5: float | None
    excluded_E6: float | None
    excluded_combined: float | None
