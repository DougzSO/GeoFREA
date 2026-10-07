"""Unit tests for geofrea.climate_forcing.change_factors (M-F4-03, M-F4-04) on synthetic fields."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from geofrea.climate_forcing import change_factors as cf


def _monthly(values_by_year_month, lat=(0.0, 1.0), lon=(0.0, 1.25)):
    """(time, lat, lon) monthly field; values_by_year_month(year, month) -> scalar everywhere."""
    times = pd.date_range("1995-01-01", "2070-12-01", freq="MS")
    data = np.array([values_by_year_month(t.year, t.month) for t in times], dtype=float)
    data = data[:, None, None] * np.ones((1, len(lat), len(lon)))
    return xr.DataArray(
        data, dims=("time", "lat", "lon"), coords={"time": times, "lat": list(lat), "lon": list(lon)}
    )


@pytest.mark.unit
def test_annual_mean_weights_the_twelve_months_equally():
    # month m has value m in every year: annual mean of the climatology = mean(1..12) = 6.5
    da = _monthly(lambda y, m: float(m))

    out = cf.annual_mean_of_climatology(da, (1995, 2014))

    assert float(out.isel(lat=0, lon=0)) == pytest.approx(6.5)


@pytest.mark.unit
def test_ratio_factor_is_window_over_reference_and_difference_is_window_minus_reference():
    hist = _monthly(lambda y, m: 100.0)
    scen = _monthly(lambda y, m: 110.0 if y >= 2041 else 100.0)

    ratio = cf.compute_change_factor("rsds", hist, scen, (1995, 2014), (2041, 2070))
    wind = cf.compute_change_factor("sfcWind", hist, scen, (1995, 2014), (2041, 2070))
    dt = cf.compute_change_factor("tas", hist, scen, (1995, 2014), (2041, 2070))

    assert float(ratio.isel(lat=0, lon=0)) == pytest.approx(1.10)
    assert float(wind.isel(lat=0, lon=0)) == pytest.approx(1.10)
    assert float(dt.isel(lat=0, lon=0)) == pytest.approx(10.0)  # additive, in the variable's unit (K)


@pytest.mark.unit
def test_change_factor_definitions_match_the_methodology_columns():
    assert cf.FACTOR_DEFINITIONS == {
        "rsds": ("delta_rsds", "ratio"),
        "sfcWind": ("delta_wind", "ratio"),
        "tas": ("dT", "difference"),
    }


@pytest.mark.unit
def test_a_truncated_period_fails_loud():
    da = _monthly(lambda y, m: 1.0).isel(time=slice(0, 100))  # ends mid-2003

    with pytest.raises(cf.IncompletePeriodError):
        cf.annual_mean_of_climatology(da, (1995, 2014))


@pytest.mark.unit
def test_nan_cells_outside_a_crop_are_not_read_as_missing_months():
    da = _monthly(lambda y, m: 2.0)
    da[:, 0, 0] = np.nan  # a cell outside the country polygon, NaN at every time step

    out = cf.annual_mean_of_climatology(da, (1995, 2014))

    assert bool(np.isnan(out.isel(lat=0, lon=0)))
    assert float(out.isel(lat=1, lon=1)) == pytest.approx(2.0)


@pytest.mark.unit
def test_ratio_over_a_non_positive_reference_fails_loud_and_nan_cells_stay_nan():
    ref = xr.DataArray([[1.0, np.nan], [0.0, 2.0]], dims=("lat", "lon"))
    win = xr.DataArray([[2.0, 2.0], [1.0, 4.0]], dims=("lat", "lon"))

    with pytest.raises(cf.NonPositiveReferenceError):
        cf.change_factor(ref, win, "ratio")

    ref_ok = xr.DataArray([[1.0, np.nan], [1.0, 2.0]], dims=("lat", "lon"))
    out = cf.change_factor(ref_ok, win, "ratio")
    assert np.isnan(float(out[0, 1])) and float(out[1, 1]) == pytest.approx(2.0)


@pytest.mark.unit
def test_bilinear_is_exact_for_a_field_that_is_linear_in_lat_and_lon():
    lat = np.arange(-10.0, 11.0, 2.0)
    lon = np.arange(0.0, 360.0, 5.0)
    field = xr.DataArray(
        3.0 + 2.0 * lat[:, None] - 0.5 * lon[None, :],
        dims=("lat", "lon"),
        coords={"lat": lat, "lon": lon},
    )
    pts_lat = np.array([0.3, -7.7, 4.4])
    pts_lon = np.array([12.2, 101.9, 33.3])

    got = cf.bilinear_to_points(field, pts_lat, pts_lon)

    assert got == pytest.approx(3.0 + 2.0 * pts_lat - 0.5 * pts_lon)


@pytest.mark.unit
def test_bilinear_wraps_negative_longitudes_and_the_zero_360_seam():
    lat = np.array([0.0, 1.0])
    lon = np.array([0.0, 90.0, 180.0, 270.0])
    field = xr.DataArray(
        np.array([[0.0, 1.0, 2.0, 3.0]] * 2), dims=("lat", "lon"), coords={"lat": lat, "lon": lon}
    )

    # -45 deg is 315 deg: halfway between the last column (270 -> 3.0) and the seam column (360 == 0 -> 0.0)
    got = cf.bilinear_to_points(field, np.array([0.5]), np.array([-45.0]))

    assert got[0] == pytest.approx(1.5)


@pytest.mark.unit
def test_bilinear_does_not_extrapolate_or_fill_nan_neighbours():
    lat = np.array([0.0, 1.0, 2.0])
    lon = np.array([0.0, 1.0, 2.0])
    data = np.ones((3, 3))
    data[1, 1] = np.nan
    field = xr.DataArray(data, dims=("lat", "lon"), coords={"lat": lat, "lon": lon})

    out = cf.bilinear_to_points(field, np.array([0.5, 5.0]), np.array([0.5, 0.5]))

    assert np.isnan(out[0])  # one of its four native neighbours is NaN
    assert np.isnan(out[1])  # outside the latitude range


def _spike_fields():
    times = pd.date_range("1995-01-01", "2070-12-01", freq="MS")
    shape = (len(times), 5, 5)
    ref = np.full(shape, 4.0)
    win = np.full(shape, 4.4)
    ref[:, 2, 2], win[:, 2, 2] = 0.002, 0.5  # one native cell whose reference wind is near zero
    mk = lambda a: xr.DataArray(  # noqa: E731
        a, dims=("time", "lat", "lon"), coords={"time": times, "lat": np.arange(5.0), "lon": np.arange(5.0)}
    )
    return mk(ref), mk(win)


@pytest.mark.unit
def test_wind_neighbourhood_ratio_keeps_a_near_zero_reference_cell_from_exploding():
    ref, win = _spike_fields()

    per_cell = cf.compute_change_factor("sfcWind", ref, win, (1995, 2014), (2041, 2070))
    smoothed = cf.compute_change_factor("sfcWind", ref, win, (1995, 2014), (2041, 2070), neighbourhood=3)

    assert float(per_cell.max()) == pytest.approx(250.0)
    assert float(smoothed.max()) < 1.2 and float(smoothed.min()) == pytest.approx(1.1)


@pytest.mark.unit
def test_neighbourhood_applies_to_ratio_factors_only_and_must_be_odd():
    ref, win = _spike_fields()
    diff_a = cf.compute_change_factor("tas", ref, win, (1995, 2014), (2041, 2070))
    diff_b = cf.compute_change_factor("tas", ref, win, (1995, 2014), (2041, 2070), neighbourhood=3)
    xr.testing.assert_allclose(diff_a, diff_b)  # dT is a difference: untouched

    with pytest.raises(ValueError, match="odd"):
        cf.neighbourhood_mean(ref.isel(time=0), 2)
