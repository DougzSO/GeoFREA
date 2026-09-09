"""Unit tests for geofrea.core.geodesy — centralized Bowring-series WGS84 scale factors.

See docs/DECISIONS.md 2026-09-09, grid_alignment Passo 4 item 1: this
function replaces three previously independently-truncated copies of
the same formula (data_quality_audit/raster_inspection.py::row_area_km2(),
grid_alignment/vector_alignment.py::calculate_wgs84_isotropic_distance(),
grid_alignment/alignment.py's adaptive-resolution calculation).
"""

import math

import numpy as np
import pytest

from geofrea.core.geodesy import wgs84_km_per_degree


def _reference(lat_deg: float) -> tuple[float, float]:
    """Independently reimplemented full-precision formula (not imported from geodesy.py)."""
    lat_rad = math.radians(lat_deg)
    lat_km = (
        111132.92
        - 559.82 * math.cos(2 * lat_rad)
        + 1.175 * math.cos(4 * lat_rad)
        - 0.0023 * math.cos(6 * lat_rad)
    ) / 1000.0
    lon_km = (
        111412.84 * math.cos(lat_rad)
        - 93.50 * math.cos(3 * lat_rad)
        + 0.118 * math.cos(5 * lat_rad)
    ) / 1000.0
    return lat_km, lon_km


@pytest.mark.unit
@pytest.mark.parametrize("lat_deg", [0.0, 39.5, -10.0, -30.0, 60.0, -60.0])
def test_wgs84_km_per_degree_matches_reference_formula(lat_deg):
    lat_km, lon_km = wgs84_km_per_degree(lat_deg)
    ref_lat_km, ref_lon_km = _reference(lat_deg)

    assert lat_km == pytest.approx(ref_lat_km, rel=1e-12)
    assert lon_km == pytest.approx(ref_lon_km, rel=1e-12)


@pytest.mark.unit
def test_wgs84_km_per_degree_equator_is_close_to_111_km():
    lat_km, lon_km = wgs84_km_per_degree(0.0)
    # Sanity range, not exact — 1 degree of latitude/longitude at the
    # equator is ~111km on a sphere; WGS84 corrections shift this only
    # slightly.
    assert 110.0 < lat_km < 112.0
    assert 111.0 < lon_km < 112.0


@pytest.mark.unit
def test_wgs84_km_per_degree_lon_km_shrinks_toward_the_poles():
    _, lon_km_equator = wgs84_km_per_degree(0.0)
    _, lon_km_60 = wgs84_km_per_degree(60.0)
    # Meridian convergence: a degree of longitude covers less ground
    # distance the further from the equator.
    assert lon_km_60 < lon_km_equator


@pytest.mark.unit
def test_wgs84_km_per_degree_accepts_numpy_array_and_vectorizes():
    lats = np.array([0.0, 39.5, -30.0])
    lat_km, lon_km = wgs84_km_per_degree(lats)

    assert lat_km.shape == (3,)
    assert lon_km.shape == (3,)
    for i, lat_deg in enumerate(lats):
        ref_lat_km, ref_lon_km = _reference(float(lat_deg))
        assert lat_km[i] == pytest.approx(ref_lat_km, rel=1e-12)
        assert lon_km[i] == pytest.approx(ref_lon_km, rel=1e-12)
