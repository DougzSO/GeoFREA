"""Vertical interpolation of the wind resource to hub height (M-F5-03).

The resource layers exist at the data heights (100, 150 and 200 m). The Weibull scale `A` is interpolated by a power law
between the two bracketing heights; the shape `k` and the air density are interpolated linearly. A hub height outside the
data heights raises: nothing is extrapolated (A-09, D-F5-012).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import pairwise

import numpy as np


class HubHeightError(ValueError):
    """The hub height is outside the heights of the resource data (A-09)."""


def bracket_heights(hub_height_m: float, heights_m: Sequence[float]) -> tuple[float, float]:
    """The two data heights `(z1, z2)`, `z1 < z2`, with `z1 <= hub_height_m <= z2`.

    Implements: M-F5-03.

    Raises:
        HubHeightError: fewer than two data heights, or `hub_height_m` outside their range.
    """
    zs = sorted(float(z) for z in heights_m)
    if len(zs) < 2:
        raise HubHeightError(f"need at least two data heights, got {zs}")
    if not zs[0] <= hub_height_m <= zs[-1]:
        raise HubHeightError(
            f"hub height {hub_height_m} m is outside the data heights {zs[0]} to {zs[-1]} m; F5 does not extrapolate"
        )
    for lo, hi in pairwise(zs):
        if lo <= hub_height_m <= hi:
            return lo, hi
    raise AssertionError("unreachable: the hub height lies inside the data range")


def weibull_scale_at_height(
    a1: np.ndarray, a2: np.ndarray, z1: float, z2: float, hub_height_m: float
) -> np.ndarray:
    """Weibull scale at hub height by power law, `alpha = ln(A2/A1) / ln(z2/z1)`, `A_H = A1 * (H/z1)^alpha`.

    Implements: M-F5-03.

    Args:
        a1: Weibull scale at height `z1`, m/s, shape (n_cells,), > 0.
        a2: Weibull scale at height `z2`, m/s, shape (n_cells,), > 0.
        z1: Lower data height, m.
        z2: Upper data height, m, `z2 > z1`.
        hub_height_m: Hub height, m.

    Returns:
        `A_H`, m/s, shape (n_cells,).

    Raises:
        ValueError: `z2 <= z1` or a non-positive scale.
    """
    if z2 <= z1:
        raise ValueError(f"z2 ({z2}) must be above z1 ({z1})")
    a1 = np.asarray(a1, dtype="float64")
    a2 = np.asarray(a2, dtype="float64")
    if (a1 <= 0).any() or (a2 <= 0).any():
        raise ValueError("Weibull scale must be positive at both heights (M-F5-03)")
    alpha = np.log(a2 / a1) / np.log(z2 / z1)
    return a1 * (hub_height_m / z1) ** alpha


def linear_at_height(
    v1: np.ndarray, v2: np.ndarray, z1: float, z2: float, hub_height_m: float
) -> np.ndarray:
    """Linear interpolation in height, for the Weibull shape `k` and the air density.

    Implements: M-F5-03.

    Args:
        v1: Value at height `z1`, shape (n_cells,).
        v2: Value at height `z2`, shape (n_cells,).
        z1: Lower data height, m.
        z2: Upper data height, m, `z2 > z1`.
        hub_height_m: Hub height, m.

    Returns:
        Value at hub height, shape (n_cells,).
    """
    if z2 <= z1:
        raise ValueError(f"z2 ({z2}) must be above z1 ({z1})")
    w = (hub_height_m - z1) / (z2 - z1)
    return (1.0 - w) * np.asarray(v1, dtype="float64") + w * np.asarray(v2, dtype="float64")


def resource_at_hub_height(
    a_by_height: Mapping[float, np.ndarray],
    k_by_height: Mapping[float, np.ndarray],
    rho_by_height: Mapping[float, np.ndarray],
    hub_height_m: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """`(A_H, k_H, rho_H)` at hub height from the layers at the data heights.

    Implements: M-F5-03.

    Args:
        a_by_height: Weibull scale, m/s, keyed by data height in m.
        k_by_height: Weibull shape, keyed by the same heights.
        rho_by_height: Air density, kg/m3, keyed by the same heights.
        hub_height_m: Hub height, m.

    Raises:
        HubHeightError: the hub height is outside the data heights.
        ValueError: the three mappings do not have the same heights.
    """
    if not (set(a_by_height) == set(k_by_height) == set(rho_by_height)):
        raise ValueError("Weibull A, k and air density must be given at the same heights")
    z1, z2 = bracket_heights(hub_height_m, list(a_by_height))
    a_h = weibull_scale_at_height(a_by_height[z1], a_by_height[z2], z1, z2, hub_height_m)
    k_h = linear_at_height(k_by_height[z1], k_by_height[z2], z1, z2, hub_height_m)
    rho_h = linear_at_height(rho_by_height[z1], rho_by_height[z2], z1, z2, hub_height_m)
    return a_h, k_h, rho_h
