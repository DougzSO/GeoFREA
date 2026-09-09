"""WGS84 geodesic scale-factor helpers, shared across phases.

Centralizes the Bowring-series latitude-correction formula that
previously existed as three independently-truncated copies:
data_quality_audit/raster_inspection.py::row_area_km2() (4 terms in
lat_km, 3 in lon_km — the most complete of the three, kept here as the
one true precision level), grid_alignment/vector_alignment.py::
calculate_wgs84_isotropic_distance() (3 terms in lat_km, missing
cos(6*phi)), and grid_alignment/alignment.py's adaptive-resolution
calculation (2 terms in each). See docs/DECISIONS.md 2026-09-09,
grid_alignment Passo 4 item 1.

Measured error from using the two more-truncated variants instead of
this one, at PRT (~39.5N) and BRA (~-10 to -30) latitudes: ~1e-6%
(vector_alignment's former 3-term lat_km) to ~1e-3% (alignment.py's
former 2-term lat_km/lon_km) — scientifically negligible either way.
Centralized to remove the duplication itself (Douglas: "mesmo padrão
de _country_window(), MULTI_FILE_LAYER_NAMES"), not because any of the
three was numerically wrong.
"""

from __future__ import annotations

import numpy as np


def wgs84_km_per_degree(lat_deg):
    """WGS84 ellipsoid arc-length scale factors, in km per degree, at lat_deg.

    Bowring-series approximation, full precision (lat_km: terms to
    cos(6*phi); lon_km: terms to cos(5*phi)) — ported from legacy's
    data_auditor.py::_row_area_km2(), the most complete of the three
    original variants (see module docstring).

    Args:
        lat_deg: Latitude(s) in decimal degrees. Scalar float or a
            numpy array (vectorizes via np.cos/np.radians either way).

    Returns:
        (lat_km_per_deg, lon_km_per_deg), same shape as lat_deg.
    """
    lat_rad = np.radians(lat_deg)
    lat_km_per_deg = (
        111132.92
        - 559.82 * np.cos(2 * lat_rad)
        + 1.175 * np.cos(4 * lat_rad)
        - 0.0023 * np.cos(6 * lat_rad)
    ) / 1000.0
    lon_km_per_deg = (
        111412.84 * np.cos(lat_rad)
        - 93.50 * np.cos(3 * lat_rad)
        + 0.118 * np.cos(5 * lat_rad)
    ) / 1000.0
    return lat_km_per_deg, lon_km_per_deg
