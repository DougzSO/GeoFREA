"""Unit tests for J-4 hazard context indicators (M-F4-05) on synthetic daily fields with known answers."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from geofrea.climate_forcing import hazards as hz


def _daily(start, end, fn, lat=(0.0, 0.5), lon=(10.0, 10.5)):
    times = pd.date_range(f"{start}-01-01", f"{end}-12-31", freq="D")
    data = np.array([fn(t) for t in times], dtype=float)[:, None, None] * np.ones(
        (1, len(lat), len(lon))
    )
    return xr.DataArray(
        data,
        dims=("time", "lat", "lon"),
        coords={"time": times, "lat": list(lat), "lon": list(lon)},
    )


@pytest.mark.unit
def test_mean_annual_hot_days_counts_days_at_or_above_the_threshold():
    # 10 days a year at 36 degC, the rest 20 degC: TX35 = 10, TX40 = 0
    tx = _daily(2041, 2050, lambda t: 36.0 if (t.month == 7 and t.day <= 10) else 20.0)

    assert float(hz.mean_annual_hot_days(tx, 35.0).isel(lat=0, lon=0)) == pytest.approx(10.0)
    assert float(hz.mean_annual_hot_days(tx, 40.0).isel(lat=0, lon=0)) == 0.0
    assert float(hz.mean_annual_hot_days(tx, 36.0).isel(lat=0, lon=0)) == pytest.approx(
        10.0
    )  # >= includes equality


@pytest.mark.unit
def test_rx5day_is_the_largest_five_day_total_per_year_averaged_over_years():
    # every year: a 5-day block of 10 mm/day (total 50) and 1 mm/day on the other days
    pr = _daily(2041, 2045, lambda t: 10.0 if (t.month == 3 and 10 <= t.day <= 14) else 1.0)

    assert float(hz.mean_annual_rx5day(pr).isel(lat=0, lon=0)) == pytest.approx(50.0)


@pytest.mark.unit
def test_wet_day_threshold_comes_from_the_reference_only_and_exceedance_is_pooled():
    ref = _daily(1995, 2014, lambda t: float(1 + (t.dayofyear % 20)))  # wet days 1..20 mm
    win = _daily(
        2041, 2050, lambda t: float(1 + (t.dayofyear % 20)) * 2.0
    )  # twice as wet: more exceedances

    p95 = hz.wet_day_percentile(ref, 95.0, 1.0)
    freq = hz.wet_day_exceedance_frequency(win, p95, 1.0)

    assert float(p95.isel(lat=0, lon=0)) == pytest.approx(
        np.percentile(np.arange(1, 21), 95), rel=0.06
    )
    assert (
        float(freq.isel(lat=0, lon=0)) > 0.05
    )  # a wetter window exceeds the baseline P95 more than 5% of wet days
    same = hz.wet_day_exceedance_frequency(ref, p95, 1.0)
    assert float(same.isel(lat=0, lon=0)) == pytest.approx(
        0.05, abs=0.03
    )  # about 5% by construction


@pytest.mark.unit
def test_dry_cells_have_nan_exceedance_not_a_filled_value():
    pr = _daily(2041, 2045, lambda t: 0.0)  # no wet day at all
    p95 = xr.DataArray(
        np.full((2, 2), 5.0), dims=("lat", "lon"), coords={"lat": [0.0, 0.5], "lon": [10.0, 10.5]}
    )

    assert bool(np.isnan(hz.wet_day_exceedance_frequency(pr, p95, 1.0)).all())


@pytest.mark.unit
def test_sample_nearest_uses_the_nearest_cell_and_fails_loud_beyond_the_tolerance():
    field = xr.DataArray(
        np.array([[1.0, 2.0], [3.0, 4.0]]),
        dims=("lat", "lon"),
        coords={"lat": [0.0, 0.5], "lon": [10.0, 10.5]},
    )

    out = hz.sample_nearest(field, np.array([0.05, 0.45]), np.array([10.05, 10.45]), 0.5)
    assert out.tolist() == [1.0, 4.0]
    with pytest.raises(hz.HazardDataError, match="within"):
        hz.sample_nearest(field, np.array([5.0]), np.array([50.0]), 0.5)

    holes = field.copy()
    holes[0, 0] = (
        np.nan
    )  # ERA5-like crop: NaN outside the polygon -> the nearest VALID cell is used
    assert hz.sample_nearest(holes, np.array([0.0]), np.array([10.0]), 1.0)[0] in (2.0, 3.0)
    assert np.isnan(
        hz.sample_nearest(holes, np.array([0.0]), np.array([10.0]), 1.0, skip_nan=False)[0]
    )


@pytest.mark.unit
def test_an_incomplete_period_fails_loud():
    short = _daily(1995, 2000, lambda t: 1.0)
    with pytest.raises(hz.HazardDataError, match="expected 20 years"):
        hz._years(short, 1995, 2014)


@pytest.mark.unit
def test_the_wet_day_threshold_and_the_percentile_are_the_ones_given():
    ref = _daily(1995, 2014, lambda t: float(1 + (t.dayofyear % 20)))
    low = hz.wet_day_percentile(ref, 50.0, 1.0)
    high = hz.wet_day_percentile(ref, 95.0, 1.0)
    strict = hz.wet_day_percentile(ref, 50.0, 10.0)  # only the wet days of 10 mm or more
    assert float(low.isel(lat=0, lon=0)) < float(high.isel(lat=0, lon=0))
    assert float(strict.isel(lat=0, lon=0)) > float(low.isel(lat=0, lon=0))


@pytest.mark.unit
def test_the_indicator_definitions_are_in_the_configuration_with_their_names():
    """M-8 of the pre-research audit: 35 and 40 C and the 95th percentile of the wet-day indicator are read from experiments.yaml."""
    from pathlib import Path

    from geofrea.core.config_loader import load_experiments

    experiments = load_experiments(
        Path(__file__).resolve().parents[2] / "config" / "experiments.yaml"
    )
    indicators = experiments.hazard_indicators
    assert (indicators.tx35_days.threshold_c, indicators.tx40_days.threshold_c) == (35.0, 40.0)
    assert (
        indicators.wet_p95_exceed_freq.percentile,
        indicators.wet_p95_exceed_freq.wet_day_mm,
    ) == (95.0, 1.0)
    assert not hasattr(hz, "HEAT_THRESHOLDS_C") and not hasattr(hz, "WET_DAY_PERCENTILE")


# --- COMMAND 75: the fields are computed by bands of latitude rows and are the ones of the whole grid ------------------------------------------


def _crop(path, variable, start, end, rng, scale, lats=(0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0)):
    times = pd.date_range(f"{start}-01-01", f"{end}-12-31", freq="D")
    data = (rng.uniform(0.0, 1.0, (len(times), len(lats), 4)) * scale).astype("float32")
    xr.Dataset(
        {variable: (("time", "lat", "lon"), data)},
        coords={"time": times, "lat": list(lats), "lon": [10.0, 10.5, 11.0, 11.5]},
    ).to_netcdf(path)
    return path


@pytest.mark.unit
@pytest.mark.parametrize("rows", [1, 2, 3, 100])
def test_the_hazard_fields_by_bands_of_latitude_rows_are_those_of_the_whole_grid(tmp_path, monkeypatch, rows):
    from pathlib import Path

    from geofrea.core.config_loader import load_experiments

    indicators = load_experiments(Path(__file__).resolve().parents[2] / "config" / "experiments.yaml").hazard_indicators
    rng = np.random.default_rng(75)
    files = (
        _crop(tmp_path / "h_tx.nc", "tasmax", 1995, 2014, rng, 320.0),
        _crop(tmp_path / "s_tx.nc", "tasmax", 2041, 2050, rng, 325.0),
        _crop(tmp_path / "h_pr.nc", "pr", 1995, 2014, rng, 4e-4),
        _crop(tmp_path / "s_pr.nc", "pr", 2041, 2050, rng, 5e-4),
    )
    monkeypatch.setattr(hz, "LAT_ROWS_PER_BAND", 10_000)
    whole = hz.hazard_fields(*files, (2041, 2050), indicators)
    monkeypatch.setattr(hz, "LAT_ROWS_PER_BAND", rows)
    banded = hz.hazard_fields(*files, (2041, 2050), indicators)
    assert set(banded) == set(whole) and len(whole) == 8
    for name in whole:
        xr.testing.assert_identical(banded[name], whole[name])
    assert banded["tx35_days"].dims == ("lat", "lon") and banded["tx35_days"].sizes["lat"] == 7


@pytest.mark.unit
def test_crops_that_do_not_share_their_latitude_rows_are_refused(tmp_path):
    from pathlib import Path

    from geofrea.core.config_loader import load_experiments

    indicators = load_experiments(Path(__file__).resolve().parents[2] / "config" / "experiments.yaml").hazard_indicators
    rng = np.random.default_rng(76)
    shifted = (0.1, 0.6, 1.1, 1.6, 2.1, 2.6, 3.1)
    files = (
        _crop(tmp_path / "h_tx.nc", "tasmax", 1995, 2014, rng, 320.0),
        _crop(tmp_path / "s_tx.nc", "tasmax", 2041, 2050, rng, 325.0, lats=shifted),
        _crop(tmp_path / "h_pr.nc", "pr", 1995, 2014, rng, 4e-4),
        _crop(tmp_path / "s_pr.nc", "pr", 2041, 2050, rng, 5e-4),
    )
    with pytest.raises(hz.HazardDataError, match="latitude rows"):
        hz.hazard_fields(*files, (2041, 2050), indicators)
