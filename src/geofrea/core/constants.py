"""Raster-format and physical constants shared across phases.

Ported from geoworld_framework's src/core/constants.py — only the subset
actually used so far (data_quality_audit's raster inspection, and, as
of 2026-09-08, grid_alignment — see docs/DECISIONS.md same date). Not a
full port of the legacy constants module: MCDA/LCOE/criteria constants
belong to the phases that use them and are ported when those phases are
built, not pre-emptively (see docs/CONVENTIONS.md, "Parameters" — no
schemas/constants against data that doesn't exist yet).
"""

from __future__ import annotations

# NoData sentinel used to fill masked-out pixels before statistics are
# computed (distinct from a raster's own `nodata` metadata value).
MASK_FILL: float = -9999.0

# NoData sentinels for grid_alignment's OWN output rasters (float32
# distance/reprojection layers vs. uint8 categorical/binary layers).
# Numerically equal to MASK_FILL today but kept as separate named
# constants, matching legacy's own choice (src/core/constants.py) to
# not alias them — they serve different phases/purposes and nothing
# guarantees they stay equal.
NODATA_FLOAT: float = -9999.0
NODATA_UINT8: int = 255

# Decision-unit cell (S-06, M-F3-03): 0.05 degree = exactly 5 x 5 pixels of the 0.01 degree
# analysis grid. The F2a grid is snapped to multiples of CELL_DEG so every cell nests
# exactly (M-F2a-01); the F3 cell index is anchored on the same lattice (CELL_ORIGIN_*).
CELL_DEG: float = 0.05
CELL_NESTING_PIXELS: int = 5
# Global cell lattice origin (north-west corner), degrees. Both are exact multiples of CELL_DEG
# (90 / 0.05 = 1800, -180 / 0.05 = -3600), so the 0.01 pixels (5 x 5) and the 0.1 degree
# V-07 cells (2 x 2) nest exactly in the same index.
CELL_ORIGIN_LAT: float = 90.0
CELL_ORIGIN_LON: float = -180.0

# ESA WorldCover land-cover class codes -> human-readable names.
ESA_CLASS_NAMES: dict[int, str] = {
    10: "Tree cover",
    20: "Shrubland",
    30: "Grassland",
    40: "Cropland",
    50: "Built-up",
    60: "Bare / Sparse vegetation",
    70: "Snow and ice",
    80: "Permanent water bodies",
    90: "Herbaceous wetland",
    95: "Mangroves",
    100: "Moss and lichen",
}

# Physical and calendar constants of F5 (D-F5-009). They are constants of a standard or of the calendar, not
# scientific parameters with a range (U-05), so they live here and not in `config/parameters.json`.
# Reference air density, kg/m3 (M-F5-03): the International Standard Atmosphere at sea level and 15 degC (ISO 2533), which is the
# reference density of the power-curve convention of IEC 61400-12-1.
RHO0_KG_M3: float = 1.225
# Hours in a year as M-F5-05 defines it; leap years are ignored by that definition.
HOURS_PER_YEAR: float = 8760.0
# Hours in a day, the unit conversion of PVOUT (kWh/kWp/day) to a capacity factor (M-F5-02).
HOURS_PER_DAY: float = 24.0

# Price base year of every cost in F6: constant 2024 USD (S-07). A cost parameter must declare it as its `price_year` (D-F6-008).
PRICE_BASE_YEAR_USD: int = 2024

# International Standard Atmosphere, ISO 2533, troposphere (V-04 sanity range of the air density; siting_layers/sanity.py).
# Standard values of the atmosphere model, not parameters with a range (U-05).
ISA_T0_K: float = 288.15  # temperature at mean sea level
ISA_P0_PA: float = 101325.0  # pressure at mean sea level
ISA_LAPSE_K_PER_M: float = 0.0065  # temperature lapse rate in the troposphere
ISA_G_M_S2: float = 9.80665  # standard gravity
ISA_R_J_KG_K: float = 287.05287  # specific gas constant of dry air
