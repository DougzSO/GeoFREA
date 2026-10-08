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

    p95 = hz.wet_day_percentile(ref)
    freq = hz.wet_day_exceedance_frequency(win, p95)

    assert float(p95.isel(lat=0, lon=0)) == pytest.approx(
        np.percentile(np.arange(1, 21), 95), rel=0.06
    )
    assert (
        float(freq.isel(lat=0, lon=0)) > 0.05
    )  # a wetter window exceeds the baseline P95 more than 5% of wet days
    same = hz.wet_day_exceedance_frequency(ref, p95)
    assert float(same.isel(lat=0, lon=0)) == pytest.approx(
        0.05, abs=0.03
    )  # about 5% by construction


@pytest.mark.unit
def test_dry_cells_have_nan_exceedance_not_a_filled_value():
    pr = _daily(2041, 2045, lambda t: 0.0)  # no wet day at all
    p95 = xr.DataArray(
        np.full((2, 2), 5.0), dims=("lat", "lon"), coords={"lat": [0.0, 0.5], "lon": [10.0, 10.5]}
    )

    assert bool(np.isnan(hz.wet_day_exceedance_frequency(pr, p95)).all())


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
def test_maps_draw_one_png_per_member_and_show_masked_cells(tmp_path):
    from geofrea.climate_forcing import maps
    from geofrea.land_eligibility.cells import cell_id

    rows, cols = np.meshgrid(np.arange(100, 104), np.arange(200, 204), indexing="ij")
    ids = cell_id(rows.ravel(), cols.ravel())
    frames = []
    for member in ("m0", "m_a_ssp126_2041_2070", "m_a_ssp370_2041_2070"):
        base = 1.0 if member == "m0" else 1.05
        frames.append(
            pd.DataFrame(
                {
                    "cell_id": ids,
                    "member": member,
                    "delta_rsds": base,
                    "delta_wind": base,
                    "dT": 0.0 if member == "m0" else 2.0,
                }
            )
        )
    forcing = pd.concat(frames, ignore_index=True)
    forcing = forcing[
        ~((forcing["member"] == "m_a_ssp370_2041_2070") & (forcing["cell_id"] == ids[0]))
    ]
    masked = pd.DataFrame(
        {"cell_id": [ids[0]], "member": ["m_a_ssp370_2041_2070"], "delta_wind": [9.0]}
    )

    out = maps.plot_all_members(forcing, masked, tmp_path, "ZZZ", {"m_a_ssp370_2041_2070": "note"})

    assert sorted(p.name for p in out) == [
        "ZZZ_m_a_ssp126_2041_2070.png",
        "ZZZ_m_a_ssp370_2041_2070.png",
    ]  # no m0
    assert all(p.exists() and p.stat().st_size > 5000 for p in out)
