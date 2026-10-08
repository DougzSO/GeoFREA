"""Capacity and annual energy per cell (M-F5-01, M-F5-05)."""

from __future__ import annotations

import numpy as np


def capacity_mw(
    eligible_area_km2: np.ndarray, luf: float, power_density_mw_per_km2: float
) -> np.ndarray:
    """Installable capacity per cell, `P_MW = eligible_area_km2 * LUF * PD`.

    Implements: M-F5-01.

    Args:
        eligible_area_km2: Eligible area of each cell, km2, shape (n_cells,).
        luf: Land-utilization factor, fraction in [0, 1].
        power_density_mw_per_km2: Power density on the project footprint, MW/km2, >= 0.

    Returns:
        Capacity of each cell, MW, shape (n_cells,).

    Raises:
        ValueError: `luf` outside [0, 1], a negative power density or a negative area.
    """
    if not 0.0 <= luf <= 1.0:
        raise ValueError(f"luf {luf} is outside [0, 1] (M-F5-01)")
    if power_density_mw_per_km2 < 0.0:
        raise ValueError(f"power density {power_density_mw_per_km2} MW/km2 is negative (M-F5-01)")
    area = np.asarray(eligible_area_km2, dtype="float64")
    if (area < 0).any():
        raise ValueError("eligible_area_km2 has negative values (M-F5-01)")
    return area * luf * power_density_mw_per_km2


def annual_energy_mwh(p_mw: np.ndarray, cf: np.ndarray, hours_per_year: float) -> np.ndarray:
    """Annual energy, `E = P_MW * CF * hours_per_year`.

    Implements: M-F5-05.

    Args:
        p_mw: Capacity, MW, shape (n,).
        cf: Capacity factor in [0, 1], shape (n,).
        hours_per_year: Hours in a year (`geofrea.core.constants.HOURS_PER_YEAR`).

    Returns:
        Energy, MWh per year, shape (n,).
    """
    return np.asarray(p_mw, dtype="float64") * np.asarray(cf, dtype="float64") * hours_per_year
