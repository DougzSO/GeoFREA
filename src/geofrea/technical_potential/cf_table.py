"""The wind capacity factor integral `I(A, k)` by table (M-F5-03, D-F5-039; COMMAND 75).

The capacity factor of a wind pixel is `eta_loss * I(A_eq, k)` with `A_eq = delta_wind * A_H * (rho / rho0)^(1/3)`: the density correction and the
wind ratio of F4 both multiply the speed, so they fold into the Weibull scale (`weibull_cf`), and the raw capacity factor depends on two numbers
and a fixed curve. `weibull_cf.weibull_capacity_factor` evaluates `I` exactly (about 30 microseconds a point); this module evaluates the same exact
function once on a grid and interpolates it with a cubic spline (about 0.2 microseconds a point). The grid is fixed (`A_STEP_MS`, `K_STEP`), and a
point outside it (`A` above `A_MAX_MS` or `k` outside `[K_MIN, K_MAX]`) is evaluated exactly, so the table never extrapolates.

The measured error of the table against the exact integral is in `docs/_audit/performance_75.md`; the tolerance (1e-5 absolute in the capacity
factor) is checked by `tests/unit/test_cf_table.py`. The option `settings.yaml` `technical_potential.wind_cf_integral` chooses `table` or `exact`
(the validation mode).

The table is a cache outside the manifest: it is keyed by the curve, the grid and the code that computes it (`core.cache_code`), stored in
`<data>/interim/cf_tables/`, and built again whenever the key changes. It holds no input of the analysis.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Callable

import numpy as np
from scipy.ndimage import map_coordinates, spline_filter

from geofrea.core import paths as core_paths
from geofrea.core.cache_code import cache_code
from geofrea.core.paths import MissingPathEnvironmentError
from geofrea.technical_potential.power_curve import PowerCurve
from geofrea.technical_potential.weibull_cf import _check_inputs, weibull_capacity_factor

logger = logging.getLogger(__name__)

CF_TABLE_ALGORITHM_VERSION = 1
WIND_CF_INTEGRALS = ("table", "exact")

A_STEP_MS = 0.05
A_MAX_MS = 45.0  # above the validity limit of A (25 m/s) times the largest wind ratio (1.5) and the density factor
K_MIN = 0.5
K_MAX = 10.0  # the validity limit of k (M-F5-03)
K_STEP = 0.02
# The grid goes `_MARGIN` beyond the range it is used in: a spline is least accurate at the edge of its grid, so the edge is kept out of the range.
_MARGIN_A_MS = 1.0
_MARGIN_K = 0.2
_SPLINE_ORDER = 3

Integral = Callable[[np.ndarray, np.ndarray], np.ndarray]


def _grids() -> tuple[np.ndarray, np.ndarray]:
    a_top, k_low, k_top = A_MAX_MS + _MARGIN_A_MS, K_MIN - _MARGIN_K, K_MAX + _MARGIN_K
    n_a = int(round(a_top / A_STEP_MS)) + 1
    n_k = int(round((k_top - k_low) / K_STEP)) + 1
    return np.linspace(0.0, a_top, n_a), np.linspace(k_low, k_top, n_k)


def table_key(curve: PowerCurve) -> str:
    """Key of the table of `curve`: the curve, the grid, the algorithm version and the code that computes the integral."""
    payload = {
        "algorithm_version": CF_TABLE_ALGORITHM_VERSION,
        "v_ms": [float(v).hex() for v in curve.v_ms],
        "p_normalized": [float(p).hex() for p in curve.p_normalized],
        "grid": [A_STEP_MS, A_MAX_MS, K_MIN, K_MAX, K_STEP, _MARGIN_A_MS, _MARGIN_K],
        "code": cache_code("cf_table"),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def build_table(curve: PowerCurve) -> np.ndarray:
    """The exact integral on the grid, shape (n_a, n_k); the row of `A = 0` is zero (no wind, no power)."""
    a_grid, k_grid = _grids()
    a_mesh, k_mesh = np.meshgrid(a_grid, k_grid, indexing="ij")
    values = weibull_capacity_factor(np.where(a_mesh > 0, a_mesh, 1e-6).ravel(), k_mesh.ravel(), curve)
    return values.reshape(a_mesh.shape)


def _table_dir():
    try:
        return core_paths.data_root() / "interim" / "cf_tables"
    except MissingPathEnvironmentError:
        return None


def load_or_build_table(curve: PowerCurve) -> np.ndarray:
    """The table of `curve`, read from `<data>/interim/cf_tables` when its key is current, else built and stored."""
    key = table_key(curve)
    directory = _table_dir()
    path = None if directory is None else directory / f"cf_table_{key[:24]}.npy"
    if path is not None and path.is_file():
        try:
            table = np.load(path)
            if table.shape == tuple(len(g) for g in _grids()):
                return table
        except (OSError, ValueError):
            logger.warning("CF table %s is unreadable; building it again.", path)
    table = build_table(curve)
    if path is not None:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(f".{os.getpid()}.tmp.npy")
            np.save(temporary, table)
            os.replace(temporary, path)
        except OSError as exc:
            logger.warning("Could not write the CF table %s: %s", path, exc)
    return table


class TabulatedIntegral:
    """`I(A, k)` of one curve by cubic-spline interpolation of the exact integral on a fixed grid; exact outside the grid."""

    def __init__(self, curve: PowerCurve, table: np.ndarray | None = None) -> None:
        self.curve = curve
        self.key = table_key(curve)
        self._table = load_or_build_table(curve) if table is None else table
        self._coefficients = spline_filter(self._table, order=_SPLINE_ORDER, mode="mirror")
        self._a_grid, self._k_grid = _grids()

    def __call__(self, a: np.ndarray, k: np.ndarray) -> np.ndarray:
        a, k = _check_inputs(a, k)
        inside = (a <= A_MAX_MS) & (k >= K_MIN) & (k <= K_MAX)
        out = np.empty(a.shape, dtype="float64")
        if inside.any():
            coordinates = np.vstack([a[inside] / A_STEP_MS, (k[inside] - self._k_grid[0]) / K_STEP])
            out[inside] = map_coordinates(
                self._coefficients, coordinates, order=_SPLINE_ORDER, mode="mirror", prefilter=False
            )
        if not inside.all():
            out[~inside] = weibull_capacity_factor(a[~inside], k[~inside], self.curve)
        return np.clip(out, 0.0, 1.0)


_BY_KEY: dict[str, TabulatedIntegral] = {}


def cf_integral(curve: PowerCurve, mode: str) -> Integral:
    """The function `(A, k) -> I` of `mode`: `table` (built once per process and per curve) or `exact` (the closed form)."""
    if mode == "exact":
        return lambda a, k: weibull_capacity_factor(a, k, curve)
    if mode != "table":
        raise ValueError(f"wind_cf_integral must be one of {WIND_CF_INTEGRALS}, got {mode!r}")
    key = table_key(curve)
    if key not in _BY_KEY:
        _BY_KEY[key] = TabulatedIntegral(curve)
    return _BY_KEY[key]
