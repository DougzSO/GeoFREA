"""Design-class screening flag of the single reference turbine (M-F5-03).

One turbine is used in every cell, so the IEC class does not choose a curve. It is kept as a flag: a cell is flagged when the annual
mean wind speed of the Weibull layer at the rule's height, in the reference climate, exceeds the class limit `V_ave` (`class_flag`
in `technologies.yaml`). The flag is computed once, is fixed across members and does not change the capacity factor or the
eligibility; it reports the share of potential where a real project would use a stronger turbine.
"""

from __future__ import annotations

import numpy as np

from geofrea.technical_potential.power_curve import PowerCurveError


class IecClassError(PowerCurveError):
    """The class flag cannot be computed: a mean speed that is not finite (A-09)."""


def exceeds_class(mean_speed_ms: np.ndarray, threshold_ms: float) -> np.ndarray:
    """True where the reference mean wind speed is above the class limit (strictly: a cell at the limit is not flagged).

    Implements: M-F5-03.

    Args:
        mean_speed_ms: Annual mean wind speed of the layer at the rule's height in the reference climate, m/s, shape (n_cells,).
        threshold_ms: `V_ave` limit of the class, m/s.

    Returns:
        Boolean array, shape (n_cells,).

    Raises:
        IecClassError: a mean speed that is not finite.
    """
    mean_speed_ms = np.asarray(mean_speed_ms, dtype="float64")
    if not np.isfinite(mean_speed_ms).all():
        raise IecClassError("the mean wind speed is not finite in some cell")
    return mean_speed_ms > threshold_ms
