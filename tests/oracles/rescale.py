"""Reference implementations of the rescaling of a stored capacity factor to another `eta_loss` or `gamma` (M-F5-02, M-F5-03; V-02). The tests compare the offset-and-slope terms that F6 uses with them."""

from __future__ import annotations

import numpy as np


def rescale_cf_wind(cf: np.ndarray, eta_nominal: float, eta: float) -> np.ndarray:
    """`CF(eta) = CF(eta_nominal) * eta / eta_nominal`; exact, because `eta_loss` is a scalar factor of M-F5-03.

    Implements: M-F5-03.

    Raises:
        ValueError: a non-positive nominal `eta_loss`.
    """
    if eta_nominal <= 0:
        raise ValueError("the nominal eta_loss must be positive")
    return np.asarray(cf, dtype="float64") * (eta / eta_nominal)


def rescale_cf_solar(
    cf: np.ndarray, d_t: np.ndarray, gamma_nominal: float, gamma: float
) -> np.ndarray:
    """`CF(gamma) = CF(gamma_nominal) * (1 + gamma * dT) / (1 + gamma_nominal * dT)`; exact for M-F5-02.

    Implements: M-F5-02.

    Raises:
        ValueError: `1 + gamma_nominal * dT` is zero in some cell.
    """
    d_t = np.asarray(d_t, dtype="float64")
    denominator = 1.0 + gamma_nominal * d_t
    if (denominator == 0).any():
        raise ValueError("1 + gamma_nominal * dT is zero in some cell: the rescale is undefined")
    return np.asarray(cf, dtype="float64") * (1.0 + gamma * d_t) / denominator
