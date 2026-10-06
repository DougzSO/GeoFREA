"""Raster-format constants shared across phases.

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

# Flat mean kilometres-per-degree-of-latitude, used ONLY by
# grid_alignment's slope-from-DEM derivation (derive_slope_from_dem()),
# ported verbatim from legacy's src/core/constants.py::KM_PER_DEG_LAT for
# STRUCTURAL_PRESERVE parity with RasterProcessor.calculate_slope (see
# docs/DECISIONS.md 2026-09-11). Deliberately NOT
# core.geodesy.wgs84_km_per_degree(): the legacy slope code used this
# single constant (and cos(lat) only for the E-W term), and reproducing
# its numbers means using the same scale factor it used.
KM_PER_DEG_LAT: float = 111.32

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
