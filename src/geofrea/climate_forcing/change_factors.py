"""Delta-change factors and their bilinear interpolation (M-F4-03, M-F4-04).

Pure functions over xarray fields, no I/O and no member/cell wiring: the callers (members.yaml,
the F3 cell grid, forcing.parquet) come later. Built fresh: CRAEI has no delta-change or
interpolation code (its ISIMIP3b hazards are computed per pre-gridded file, A-11 lookup 2026-10-06),
so there is nothing to adapt.

M-F4-03, on each GCM's native grid, from monthly climatologies:
    delta_rsds = mean_window(rsds) / mean_ref(rsds)        (multiplicative)
    delta_wind = mean_window(sfcWind) / mean_ref(sfcWind)  (multiplicative)
    dT         = mean_window(tas) - mean_ref(tas)          (additive, K)
with the climatology the mean of the 12 calendar-month means over the period's years, and the
annual mean the mean of those 12 values (months weighted equally, as M-F4-03 states).

M-F4-04: the change factors are interpolated bilinearly to 0.05 degree cell centers. Interpolate
from the *uncropped* native field: a country crop masks cells outside the polygon to NaN, and
bilinear interpolation next to the coast would then return NaN.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import xarray as xr

Kind = Literal["ratio", "difference"]

# GeoFREA variable -> (change-factor column, definition), M-F4-03.
FACTOR_DEFINITIONS: dict[str, tuple[str, Kind]] = {
    "rsds": ("delta_rsds", "ratio"),
    "sfcWind": ("delta_wind", "ratio"),
    "tas": ("dT", "difference"),
}


class IncompletePeriodError(ValueError):
    """The requested period is not fully covered by the monthly series (A-09: fail loud)."""


class NonPositiveReferenceError(ValueError):
    """A multiplicative change factor would divide by a zero or negative reference mean."""


def monthly_climatology(da: xr.DataArray, years: tuple[int, int]) -> xr.DataArray:
    """Mean over `years` (inclusive) for each calendar month; dims (month, ...).

    Raises IncompletePeriodError unless every year of the period has all 12 months, so a
    truncated series cannot silently shift the climatology.
    """
    start, end = years
    window = da.sel(time=slice(f"{start}-01-01", f"{end}-12-31"))
    expected = (end - start + 1) * 12
    if window.sizes["time"] != expected:
        raise IncompletePeriodError(
            f"{start}-{end}: expected {expected} monthly steps, found {window.sizes['time']}"
        )
    # count the time steps themselves: counting data values would read NaN cells outside a crop as missing months
    per_year = window["time"].groupby("time.year").count()
    if not (per_year == 12).all():
        raise IncompletePeriodError(f"{start}-{end}: not every year has 12 months")
    return window.groupby("time.month").mean("time")


def annual_mean_of_climatology(da: xr.DataArray, years: tuple[int, int]) -> xr.DataArray:
    """Annual mean = mean of the 12 monthly-climatology values (dims: the spatial ones)."""
    return monthly_climatology(da, years).mean("month")


def change_factor(
    reference: xr.DataArray, window: xr.DataArray, kind: Kind
) -> xr.DataArray:
    """`window / reference` (ratio) or `window - reference` (difference), same grid.

    NaN cells (outside a crop, ocean mask) stay NaN. A ratio over a non-positive reference mean
    raises NonPositiveReferenceError instead of producing inf or a sign flip.
    """
    if kind == "difference":
        return window - reference
    if kind != "ratio":
        raise ValueError(f"unknown change-factor kind {kind!r}")
    if bool((reference <= 0).any()):
        raise NonPositiveReferenceError("reference mean <= 0 in at least one cell")
    return window / reference


def compute_change_factor(
    variable: str,
    historical: xr.DataArray,
    scenario: xr.DataArray,
    reference_years: tuple[int, int],
    window_years: tuple[int, int],
) -> xr.DataArray:
    """One member's change factor for `variable` on the model's native grid (M-F4-03)."""
    _, kind = FACTOR_DEFINITIONS[variable]
    ref = annual_mean_of_climatology(historical, reference_years)
    win = annual_mean_of_climatology(scenario, window_years)
    return change_factor(ref, win, kind)


def _with_periodic_longitude(field: xr.DataArray) -> xr.DataArray:
    """Pad one native column on each side so interpolation works across the 0/360 seam."""
    lon = field["lon"]
    west = field.isel(lon=[-1]).assign_coords(lon=[float(lon[-1]) - 360.0])
    east = field.isel(lon=[0]).assign_coords(lon=[float(lon[0]) + 360.0])
    return xr.concat([west, field, east], dim="lon")


def bilinear_to_points(
    field: xr.DataArray, lat: np.ndarray, lon: np.ndarray
) -> np.ndarray:
    """Bilinear interpolation of a native-grid (lat, lon) field to the points (lat[i], lon[i]).

    `lon` may be given in -180..180; it is wrapped to the field's convention (0..360 or
    -180..180). Points outside the field's latitude range, or next to NaN native cells, give NaN
    (never extrapolated or filled).
    """
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    if lat.shape != lon.shape:
        raise ValueError("lat and lon must have the same shape")
    f = field.sortby("lat").sortby("lon")
    if float(f["lon"].max()) > 180.0:
        lon = np.where(lon < 0.0, lon + 360.0, lon)
    f = _with_periodic_longitude(f)
    points_lat = xr.DataArray(lat, dims="points")
    points_lon = xr.DataArray(lon, dims="points")
    out = f.interp(lat=points_lat, lon=points_lon, method="linear")
    return np.asarray(out.values, dtype=float)
