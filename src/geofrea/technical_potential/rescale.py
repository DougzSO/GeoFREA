"""Rescaling of a stored capacity factor to another value of an uncertain parameter (U-03; D-F5-008).

`gamma` and `eta_loss` are sampled in F6 but enter the capacity factor in F5, which stores the factor at their nominal values.
Both enter in closed form, so F6 obtains `CF(m, s)` from the stored `CF(m, nominal)` without recomputing the integral.
"""

from __future__ import annotations

import numpy as np


def wind_rescale_terms(n_cells: int, eta_nominal: float) -> tuple[np.ndarray, np.ndarray]:
    """Offset and slope of `factor = CF(eta) / CF(eta_nominal) = offset + slope * eta`: `(0, 1/eta_nominal)` in every cell.

    Implements: M-F5-03, M-F6-01.

    Raises:
        ValueError: a non-positive nominal `eta_loss`.
    """
    if eta_nominal <= 0:
        raise ValueError("the nominal eta_loss must be positive")
    return np.zeros(n_cells), np.full(n_cells, 1.0 / eta_nominal)


def solar_rescale_terms(d_t: np.ndarray, gamma_nominal: float) -> tuple[np.ndarray, np.ndarray]:
    """Offset and slope of `factor = (1 + gamma dT) / (1 + gamma_nominal dT) = offset + slope * gamma`.

    Implements: M-F5-02, M-F6-01.

    Raises:
        ValueError: `1 + gamma_nominal * dT` is zero in some cell.
    """
    d_t = np.asarray(d_t, dtype="float64")
    denominator = 1.0 + gamma_nominal * d_t
    if (denominator == 0).any():
        raise ValueError("1 + gamma_nominal * dT is zero in some cell: the rescale is undefined")
    return 1.0 / denominator, d_t / denominator
