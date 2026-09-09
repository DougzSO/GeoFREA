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

# Maximum distance (km) encoded in grid_alignment's linear-feature
# distance rasters (roads, grid, rivers) before clipping. Unified
# 2026-09-09 (see docs/DECISIONS.md same date, grid_alignment Passo 4
# item 2) — legacy diverged (100.0 for roads/grid, an undocumented
# separate 50.0 for rivers) with no found justification, and the
# divergence was confirmed functionally inert (downstream
# criteria_builder.py's own proximity-decay distances, 5-30km, sit well
# below both former caps regardless of which was used).
LINEAR_FEATURE_MAX_DIST_KM: float = 100.0

# Wind height variants combined by grid_alignment's AHP weighting
# (_combine_wind_layers()) and the Saaty pairwise-comparison matrix
# used to derive their weights. Ported as-is from legacy
# (src/core/constants.py). Reviewed in detail 2026-09-09 (see
# docs/DECISIONS.md same date, grid_alignment Passo 4 item 4) — kept as
# STRUCTURAL_PRESERVE, but the specific pairwise judgments below (200m
# 3x over 100m, 5x over 50m; 100m 3x over 50m) have NO cited source
# anywhere in the legacy codebase/docs/git history. This is DISTINCT
# from the AHP application legacy's docs/memory/04-algorithms.md cites
# Al Garni & Awasthi (2017) for — that reference covers Phase 3's
# suitability-criteria weighting (suitability_builder.py, not yet built
# in GeoFREA), a different AHP use of the same math, not this one.
# The consistency-ratio machinery below (RC, 0.10 threshold,
# AHP_RANDOM_INDEX) IS literature-grounded (Saaty, 1980) — only the
# matrix's own judgments are unsourced. Measured against this exact
# matrix: RC ≈ 0.034 (well under 0.10 — the uniform-weight fallback
# never triggers for it), inducing weights ≈ 63.3%/26.0%/10.6% for
# 200m/100m/50m. OPEN QUESTION, not resolved here (Douglas, 2026-09-09):
# revisit when suitability_criteria (Phase 3) is designed and its own
# criteria sourcing gets formalized — decide then whether this specific
# lack of a cited source is acceptable as-is or needs independent
# justification/replacement before being relied on in the thesis.
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
# RC > 0.10 threshold confirmed literature-standard (Saaty, 1980), not
# an arbitrary legacy choice — see docs/DECISIONS.md 2026-09-09,
# grid_alignment Passo 4 item 4.
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
