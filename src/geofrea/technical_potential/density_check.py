"""Consistency of the reference air density of the Global Wind Atlas with the standard atmosphere (M-F5-03, report only).

The density correction of F5 is applied at every elevation: a low density on a high plateau is physical and is not truncated. As a check
that the layer and the elevation of the cell agree, the ratio `rho_ref / rho_ISA(z + h)` is computed, with `z` the cell elevation (eligible-area
weighted mean of the aligned DEM), `h` the hub height and `rho_ISA` the ISO 2533 troposphere density. A cell whose ratio is outside
`[RATIO_LOW, RATIO_HIGH]` is counted and reported; it is neither removed nor changed, and the check never raises.
"""

from __future__ import annotations

import numpy as np

from geofrea.siting_layers.sanity import isa_density_kg_m3

RATIO_LOW = 0.90
RATIO_HIGH = 1.10


def isa_density_ratio(
    rho_ref_kg_m3: np.ndarray, elevation_m: np.ndarray, hub_height_m: float
) -> np.ndarray:
    """`rho_ref / rho_ISA(z + h)` per cell.

    Implements: M-F5-03.

    Args:
        rho_ref_kg_m3: Reference air density at the hub height, shape (n_cells,).
        elevation_m: Cell elevation above sea level, m.
        hub_height_m: Hub height above ground, m.
    """
    z = np.asarray(elevation_m, dtype="float64") + float(hub_height_m)
    return np.asarray(rho_ref_kg_m3, dtype="float64") / np.asarray(isa_density_kg_m3(z))


def outside_isa_check(ratio: np.ndarray) -> np.ndarray:
    """True where the ratio is outside `[RATIO_LOW, RATIO_HIGH]` (or not finite)."""
    ratio = np.asarray(ratio, dtype="float64")
    return ~np.isfinite(ratio) | (ratio < RATIO_LOW) | (ratio > RATIO_HIGH)
