"""Solar capacity factor of the reference climate and of a climate member (M-F5-02)."""

from __future__ import annotations

import numpy as np


def solar_cf_reference(pvout_kwh_kwp_day: np.ndarray, hours_per_day: float) -> np.ndarray:
    """Reference capacity factor, `CF0 = pvout_kwh_kwp_day / hours_per_day`.

    PVOUT is kWh per kWp per day, so the quotient is dimensionless; it already includes the thermal losses of the reference
    climate.

    Implements: M-F5-02.

    Args:
        pvout_kwh_kwp_day: Photovoltaic output, kWh/kWp/day, shape (n_cells,).
        hours_per_day: Hours in a day (`geofrea.core.constants.HOURS_PER_DAY`).

    Returns:
        `CF0`, dimensionless, shape (n_cells,).
    """
    return np.asarray(pvout_kwh_kwp_day, dtype="float64") / hours_per_day


def solar_cf_member(
    cf0: np.ndarray, delta_rsds: np.ndarray, d_t: np.ndarray, gamma: float
) -> np.ndarray:
    """Member capacity factor, `CF_m = CF0 * delta_rsds_m * (1 + gamma * dT_m)`.

    Implements: M-F5-02.

    Args:
        cf0: Reference capacity factor, shape (n,).
        delta_rsds: Ratio of surface solar radiation, member over reference, shape (n,).
        d_t: Temperature change of the member, K, shape (n,).
        gamma: Module power temperature coefficient, 1/K (negative).

    Returns:
        `CF_m`, shape (n,).
    """
    return (
        np.asarray(cf0, dtype="float64")
        * np.asarray(delta_rsds, dtype="float64")
        * (1.0 + gamma * np.asarray(d_t, dtype="float64"))
    )
