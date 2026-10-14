"""Reference forms of the wind capacity factor of M-F5-03 (the reference factor and the ratio form); the pipeline computes the member factor directly (V-02)."""

from __future__ import annotations

import numpy as np

from geofrea.technical_potential.power_curve import PowerCurve
from geofrea.technical_potential.weibull_cf import equivalent_scale, weibull_capacity_factor


def wind_cf_reference(
    a_h: np.ndarray,
    k_h: np.ndarray,
    rho_h: np.ndarray,
    curve: PowerCurve,
    rho0: float,
    eta_loss: float,
) -> np.ndarray:
    """Reference capacity factor, `CF0 = eta_loss * I(A_eq, k_H)`.

    Implements: M-F5-03.

    Args:
        a_h: Weibull scale at hub height, m/s, shape (n_cells,).
        k_h: Weibull shape at hub height, shape (n_cells,).
        rho_h: Air density at hub height, kg/m3, shape (n_cells,).
        curve: Reference power curve.
        rho0: Reference air density, kg/m3.
        eta_loss: Wake and availability loss factor, fraction in [0, 1].
    """
    return eta_loss * weibull_capacity_factor(equivalent_scale(a_h, rho_h, rho0), k_h, curve)


def member_cf_ratio(
    a_h: np.ndarray,
    k_h: np.ndarray,
    rho_h: np.ndarray,
    delta_wind: np.ndarray,
    curve: PowerCurve,
    rho0: float,
) -> np.ndarray:
    """Ratio `CF(A_H * delta_wind, k_H) / CF(A_H, k_H)` of M-F5-03, both with the density correction.

    Implements: M-F5-03.

    Raises:
        ValueError: a cell whose reference capacity factor is zero (the ratio is undefined).
    """
    a_eq = equivalent_scale(a_h, rho_h, rho0)
    base = weibull_capacity_factor(a_eq, k_h, curve)
    if (base <= 0).any():
        raise ValueError(
            "the reference capacity factor is zero in some cell: the member ratio is undefined"
        )
    return weibull_capacity_factor(a_eq * np.asarray(delta_wind), k_h, curve) / base
