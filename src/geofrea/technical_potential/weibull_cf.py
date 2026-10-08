"""Wind capacity factor from a Weibull speed distribution and a power curve (M-F5-03; D-F5-001, D-F5-002).

A Weibull speed is a scale family: if `v ~ Weibull(A, k)` then `c * v ~ Weibull(c * A, k)`. The air-density correction
`v_eq = v * (rho / rho0)^(1/3)` and the climate factor `delta_wind` both multiply the speed, so both fold into the scale,

    A_eq = A_H * (rho_H / rho0)^(1/3),      A_eq,m = delta_wind_m * A_eq,

and the capacity factor is one function `I(A, k)` of two numbers and a fixed curve. `I` is evaluated in closed form per curve
segment: with the curve read as piecewise linear, `P(u) / P_rated = p_i + m_i * (u - v_i)` on `[v_i, v_{i+1}]`, and

    integral of (p_i + m_i (u - v_i)) f(u) du = p_i * dF + m_i * (M - v_i * dF),
    M = A * Gamma(1 + 1/k) * (Q(s, t_b) - Q(s, t_a)),   s = 1 + 1/k,   t = (u / A)^k,   dF = exp(-t_a) - exp(-t_b),

with `Q` the regularized lower incomplete gamma function. No speed step exists. The power above the cut-out is zero.
"""

from __future__ import annotations

import numpy as np
from scipy.special import gamma as gamma_fn
from scipy.special import gammainc, gammaincc

from geofrea.technical_potential.power_curve import PowerCurve

_CHUNK_CELLS = 20_000
_ROUNDING_TOLERANCE = 1e-9


def equivalent_scale(a: np.ndarray, rho: np.ndarray, rho0: float) -> np.ndarray:
    """Weibull scale seen by the power curve after the air-density correction, `A_eq = A * (rho / rho0)^(1/3)`.

    Implements: M-F5-03.

    Args:
        a: Weibull scale at hub height, m/s, shape (n_cells,).
        rho: Air density at hub height, kg/m3, shape (n_cells,).
        rho0: Reference air density of the power curve, kg/m3 (`geofrea.core.constants.RHO0_KG_M3`).

    Returns:
        `A_eq`, m/s, shape (n_cells,).

    Raises:
        ValueError: a non-positive density or reference density.
    """
    rho = np.asarray(rho, dtype="float64")
    if rho0 <= 0 or (rho <= 0).any():
        raise ValueError("air density must be positive (M-F5-03)")
    return np.asarray(a, dtype="float64") * (rho / rho0) ** (1.0 / 3.0)


def weibull_mean_speed(a: np.ndarray, k: np.ndarray) -> np.ndarray:
    """Mean of a Weibull speed, `A * Gamma(1 + 1/k)`, m/s (used by the IEC class rule).

    Implements: M-F5-03.
    """
    return np.asarray(a, dtype="float64") * gamma_fn(1.0 + 1.0 / np.asarray(k, dtype="float64"))


def _check_inputs(a: np.ndarray, k: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    a = np.atleast_1d(np.asarray(a, dtype="float64"))
    k = np.atleast_1d(np.asarray(k, dtype="float64"))
    if a.shape != k.shape:
        a, k = np.broadcast_arrays(a, k)
    if not (np.isfinite(a).all() and np.isfinite(k).all()):
        raise ValueError("Weibull A and k must be finite (A-09)")
    if (a <= 0).any() or (k <= 0).any():
        raise ValueError("Weibull A and k must be positive (M-F5-03)")
    return a, k


def _integral_chunk(a: np.ndarray, k: np.ndarray, v: np.ndarray, p: np.ndarray) -> np.ndarray:
    t = (v[None, :] / a[:, None]) ** k[:, None]  # (n, nodes)
    s = (1.0 + 1.0 / k)[:, None]
    lower = gammainc(s, t)
    upper = gammaincc(s, t)
    t_a, t_b = t[:, :-1], t[:, 1:]
    # use the difference of the smaller of Q and 1 - Q: the lower function below the mode region, the upper one above it
    d_gamma = np.where(t_a >= s, upper[:, :-1] - upper[:, 1:], lower[:, 1:] - lower[:, :-1])
    d_f = np.exp(-t_a) * (-np.expm1(-(t_b - t_a)))
    slope = (p[1:] - p[:-1]) / (v[1:] - v[:-1])
    mean_part = (a * gamma_fn(1.0 + 1.0 / k))[:, None] * d_gamma
    segment = p[None, :-1] * d_f + slope[None, :] * (mean_part - v[None, :-1] * d_f)
    return segment.sum(axis=1)


def weibull_capacity_factor(a: np.ndarray, k: np.ndarray, curve: PowerCurve) -> np.ndarray:
    """Capacity factor before losses, `I(A, k) = integral of P(u) / P_rated * weibull_pdf(u; A, k) du`.

    The curve is read as piecewise linear and the integral is exact for it (no speed step, no quadrature).

    Implements: M-F5-03.

    Args:
        a: Weibull scale of the speed the curve sees (after the density correction), m/s, shape (n_cells,).
        k: Weibull shape, dimensionless, shape (n_cells,).
        curve: Reference power curve.

    Returns:
        Capacity factor in [0, 1], shape (n_cells,).

    Raises:
        ValueError: a non-positive or non-finite `a` or `k`, or a result outside [0, 1] beyond rounding.
    """
    a, k = _check_inputs(a, k)
    v = np.asarray(curve.v_ms, dtype="float64")
    p = np.asarray(curve.p_normalized, dtype="float64")
    out = np.empty(a.shape, dtype="float64")
    for lo in range(0, a.size, _CHUNK_CELLS):
        hi = lo + _CHUNK_CELLS
        out[lo:hi] = _integral_chunk(a[lo:hi], k[lo:hi], v, p)
    if (out < -_ROUNDING_TOLERANCE).any() or (out > 1.0 + _ROUNDING_TOLERANCE).any():
        raise ValueError(f"capacity factor outside [0, 1]: min {out.min()}, max {out.max()} (V-03)")
    return np.clip(out, 0.0, 1.0)


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


def wind_cf_member(
    a_eq: np.ndarray, k_h: np.ndarray, delta_wind: np.ndarray, curve: PowerCurve, eta_loss: float
) -> np.ndarray:
    """Member capacity factor, `CF_m = eta_loss * I(delta_wind_m * A_eq, k_H)`.

    This equals the ratio form of M-F5-03, `CF0 * I(delta_wind * A_eq) / I(A_eq)`, because `eta_loss` cancels, and it does not
    divide by `I(A_eq)`, which is zero for a cell without usable wind.

    Implements: M-F5-03.

    Args:
        a_eq: Equivalent scale of the reference climate, m/s, shape (n_cells,).
        k_h: Weibull shape at hub height (unchanged by climate, L-003), shape (n_cells,).
        delta_wind: Wind-speed ratio of the member, shape (n_cells,).
        curve: Reference power curve.
        eta_loss: Wake and availability loss factor.
    """
    return eta_loss * weibull_capacity_factor(np.asarray(a_eq) * np.asarray(delta_wind), k_h, curve)


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
