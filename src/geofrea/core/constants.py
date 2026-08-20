"""Raster-format constants shared across phases.

Ported from geoworld_framework's src/core/constants.py — only the subset
actually used so far (data_quality_audit's raster inspection). Not a
full port of the legacy constants module: MCDA/LCOE/criteria constants
belong to the phases that use them and are ported when those phases are
built, not pre-emptively (see docs/CONVENTIONS.md, "Parameters" — no
schemas/constants against data that doesn't exist yet).
"""

from __future__ import annotations

# NoData sentinel used to fill masked-out pixels before statistics are
# computed (distinct from a raster's own `nodata` metadata value).
MASK_FILL: float = -9999.0

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
