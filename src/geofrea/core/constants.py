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

# Wind height variants combined by grid_alignment's AHP weighting
# (_combine_wind_layers()) and the Saaty pairwise-comparison matrix
# used to derive their weights. Ported as-is from legacy
# (src/core/constants.py) — the matrix's own pairwise judgments were
# NOT reviewed for this port (see docs/DECISIONS.md 2026-09-08,
# grid_alignment Passo 4 — pending methodological review).
WIND_HEIGHT_KEYS: list[str] = ["200m", "100m", "50m"]
WIND_AHP_MATRIX: list[list[float]] = [
    [1.0, 3.0, 5.0],
    [1 / 3, 1.0, 3.0],
    [1 / 5, 1 / 3, 1.0],
]

# Saaty Random Index (RI) table, keyed by matrix size n — used to
# compute the Consistency Ratio (CR = CI/RI) that decides whether
# _compute_ahp_weights()'s result is accepted or discarded in favor of
# uniform weights. Ported as-is from legacy (src/core/constants.py).
AHP_RANDOM_INDEX: dict[int, float] = {
    1: 0.00,
    2: 0.00,
    3: 0.58,
    4: 0.90,
    5: 1.12,
    6: 1.24,
    7: 1.32,
    8: 1.41,
    9: 1.45,
    10: 1.49,
    11: 1.51,
    12: 1.53,
    13: 1.56,
    14: 1.57,
    15: 1.59,
}

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
