"""IEC class of each cell from the siting rule of the technology registry (M-F5-03; D-F5-004, D-F5-017).

The rule is data in `technologies.yaml` `iec_class_rule`: a list of `{iec_class, mean_speed_upper_ms, source}` ordered from the
lowest class to the highest, the last bound `null` (no upper limit). A cell takes the first class whose bound is not below the
annual mean wind speed at hub height in the reference climate, and keeps it in every member (a turbine is chosen for the site
climate, not re-chosen for each future). The thresholds are values of the IEC standard that OQ-005 asks the author to source;
nothing here carries a number, and a power curve (a turbine) carries none either.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

import numpy as np

from geofrea.core.config_schemas import IecClassBound
from geofrea.technical_potential.power_curve import PowerCurveError


class IecClassError(PowerCurveError):
    """The class rule is malformed, or a cell fits no class (A-09)."""


def assign_by_mean_speed(mean_speed_ms: np.ndarray, rule: Sequence[IecClassBound]) -> np.ndarray:
    """Index into `rule` of the class of each cell: the first class whose upper bound is not below the mean speed.

    Implements: M-F5-03.

    Args:
        mean_speed_ms: Annual mean wind speed at hub height in the reference climate, m/s, shape (n_cells,).
        rule: The registry rule, lowest class first, the last bound `None`.

    Returns:
        Integer array of indices into `rule`, shape (n_cells,).

    Raises:
        IecClassError: an empty rule, bounds not increasing, a bound that is `None` before the last class, a last bound that is
            not `None`, or a mean speed that is not finite.
    """
    if not rule:
        raise IecClassError("the iec_class_rule is empty")
    bounds = [b.mean_speed_upper_ms for b in rule]
    if any(b is None for b in bounds[:-1]) or bounds[-1] is not None:
        raise IecClassError("only the last class of iec_class_rule has no upper bound (null)")
    finite = bounds[:-1]
    if any(b2 <= b1 for b1, b2 in pairwise(finite)):
        raise IecClassError("the upper bounds of iec_class_rule must be strictly increasing")
    mean_speed_ms = np.asarray(mean_speed_ms, dtype="float64")
    if not np.isfinite(mean_speed_ms).all():
        raise IecClassError("the mean wind speed is not finite in some cell")
    return np.searchsorted(np.asarray(finite, dtype="float64"), mean_speed_ms, side="left")
