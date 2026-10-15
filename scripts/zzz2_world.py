"""The second synthetic world, ZZZ2 (audit 2026-10, M-1; COMMAND 39): the same country code and extent as ZZZ, other inputs.

Why a second world. ZZZ keeps the order of its cells in every future (its wind and irradiance factors do not depend on the cell, its distances to the grid and the road
do not trade against each other), so the end-to-end values of `V_k`, `D`, `D_clim`, `D_tec`, `V_f` and of the PRIM box are zero there and the checks on them would also pass
for a function that returns zero. In ZZZ2 every one of them is non-trivial and known before the run, because the fields are written in closed form:

- The resource of the reference climate varies from west to east: the Weibull scale of the Global Wind Atlas grows eastward by `WIND_RESOURCE_SLOPE` per `u` unit.
- Each GCM carries its own spatial pattern of the change factors, linear in longitude and latitude: `delta_wind = 1 + scale(ssp, window) * (a_g u + b_g v + c_g)`,
  `delta_rsds` the same with its own coefficients, `dT = d_g scale + e_g u + f_g v` (K). GFDL-ESM4 and IPSL-CM6A-LR take wind from the east, ACCESS-CM2 gives it to the
  east, CNRM-CM6-1 takes it from the north: a cell that is best in one member is not in another, and the climate-only ranking of the maximum regret is not the nominal one.
- The transmission line runs along the west edge and the road along the east edge, so the distance to the grid grows eastward and the distance to the road westward. With the
  distance costs of the test parameters (`PARAMETER_OVERRIDES`) a draw with a dear grid favours the west and a draw with a dear road favours the east: the order of the cells
  changes between draws, which is what `D_tec` measures.

Linear fields keep the expected values exact: the 3 x 3 neighbourhood mean of a linear field is its value at the centre, and bilinear interpolation of a linear field is exact, so
the change factor of a cell centre is the closed form below (`delta_wind`, `delta_rsds`, `delta_t`), not a number read back from the pipeline.

The native grid is 0.1 degree and extends 0.5 degree beyond the country on every side, so that the neighbourhood of every interpolation node exists.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

WEST, EAST, SOUTH, NORTH = 20.00, 20.30, -5.00, -4.80
LON_C, LAT_C = 20.15, -4.90  # centre of the country
U_HALF, V_HALF = (
    0.15,
    0.10,
)  # u = (lon - LON_C) / U_HALF and v = (lat - LAT_C) / V_HALF are -1..1 over the country

NATIVE_LAT = np.round(np.arange(-5.5, -4.3 + 1e-9, 0.1), 6)
NATIVE_LON = np.round(np.arange(19.5, 20.8 + 1e-9, 0.1), 6)

# reference climate of every GCM (constant in space, with a seasonal cycle that averages to zero over the 12 months)
REF_WIND_MS, REF_RSDS_WM2, REF_TAS_K = 5.0, 220.0, 295.0

WIND_RESOURCE_SLOPE = 0.02  # relative growth of the Weibull scale per unit u (east is windier)

GCMS = ("gfdl_esm4", "miroc6", "access_cm2", "ipsl_cm6a_lr", "cnrm_cm6_1", "mri_esm2_0")
SSP_SCALE = (0.6, 1.0, 1.4)  # SSP1-2.6, SSP3-7.0, SSP5-8.5
WINDOW_SCALE = (1.0, 1.5)  # 2041-2070, 2071-2100

# (a, b, c) of delta_wind = 1 + scale * (a u + b v + c); MIROC6 has no wind channel but its file is written
WIND_PATTERN = {
    "gfdl_esm4": (-0.16, 0.00, 0.00),
    "miroc6": (0.00, 0.00, 0.00),
    "access_cm2": (0.06, 0.00, 0.00),
    "ipsl_cm6a_lr": (-0.18, 0.03, 0.00),
    "cnrm_cm6_1": (0.00, -0.03, 0.00),
    "mri_esm2_0": (0.02, 0.01, 0.00),
}
# (a, b, c) of delta_rsds = 1 + scale * (a u + b v + c)
RSDS_PATTERN = {
    "gfdl_esm4": (-0.10, 0.04, 0.00),
    "miroc6": (-0.08, 0.00, 0.01),
    "access_cm2": (0.08, -0.04, 0.00),
    "ipsl_cm6a_lr": (-0.12, -0.04, -0.01),
    "cnrm_cm6_1": (-0.06, 0.03, 0.00),
    "mri_esm2_0": (-0.04, 0.02, 0.01),
}
# (d, e, f) of dT = scale * (d + e u + f v), K
TAS_PATTERN = {
    "gfdl_esm4": (1.2, 0.30, 0.00),
    "miroc6": (1.0, 0.00, 0.20),
    "access_cm2": (1.4, -0.30, 0.10),
    "ipsl_cm6a_lr": (1.8, 0.20, -0.30),
    "cnrm_cm6_1": (1.5, 0.00, 0.30),
    "mri_esm2_0": (1.1, 0.10, 0.10),
}

# Test values of the cost parameters and thresholds, applied to the copy of parameters.json that the ZZZ2 run reads (the real file keeps the ZZZ values).
# The distance costs are large and their ranges wide, so that the distance matters as much as the climate and a draw with a dear grid reorders the cells against a draw with a dear
# road: grid cost in USD/(MW km), road cost in USD/km of the whole plant. `cf_min` is below every member of the world (no climate-fragile cell) and `tau` inside the spread of the LCOE.
PARAMETER_OVERRIDES = {
    "wind": {
        "grid_cost_usd_per_mw_km": {"value": 9660.0, "min": 5730.0, "max": 28650.0},
        "road_cost_usd_per_km": {"value": 1.75e6, "min": 1.56e6, "max": 2.51e6},
        "cf_min": {"value": 0.2},
        "tau_lcoe_usd_per_mwh": {"value": 55.0},
    },
    "solar": {
        "grid_cost_usd_per_mw_km": {"value": 9720.0, "min": 7800.0, "max": 29200.0},
        "road_cost_usd_per_km": {"value": 1.43e6, "min": 1.24e6, "max": 2.06e6},
        "cf_min": {"value": 0.1},
        "tau_lcoe_usd_per_mwh": {"value": 105.0},
    },
}


def u_of(lon: float | np.ndarray) -> float | np.ndarray:
    return (lon - LON_C) / U_HALF


def v_of(lat: float | np.ndarray) -> float | np.ndarray:
    return (lat - LAT_C) / V_HALF


def scale(s: int, w: int) -> float:
    return SSP_SCALE[s] * WINDOW_SCALE[w]


def delta_wind(gcm: str, s: int, w: int, lon, lat):
    a, b, c = WIND_PATTERN[gcm]
    return 1.0 + scale(s, w) * (a * u_of(lon) + b * v_of(lat) + c)


def delta_rsds(gcm: str, s: int, w: int, lon, lat):
    a, b, c = RSDS_PATTERN[gcm]
    return 1.0 + scale(s, w) * (a * u_of(lon) + b * v_of(lat) + c)


def delta_t(gcm: str, s: int, w: int, lon, lat):
    d, e, f = TAS_PATTERN[gcm]
    return scale(s, w) * (d + e * u_of(lon) + f * v_of(lat))


def wind_resource_factor(lon):
    """Multiplier of the Weibull scale (and nothing else) at a longitude."""
    return 1.0 + WIND_RESOURCE_SLOPE * u_of(lon)


def cmip6_field(variable: str, experiment: str, g: int, s: int, gcm_name: str) -> xr.Dataset:
    """The monthly field of one file: a constant reference, or the reference times (plus) the closed-form change factor of the window."""
    lat, lon = NATIVE_LAT[:, None], NATIVE_LON[None, :]
    shape = (len(NATIVE_LAT), len(NATIVE_LON))

    def block(years: tuple[int, int], w: int | None) -> xr.Dataset:
        time = pd.date_range(f"{years[0]}-01-01", f"{years[1]}-12-01", freq="MS") + pd.Timedelta(
            days=14
        )
        season = np.sin(2 * np.pi * (np.arange(len(time)) % 12) / 12.0)[:, None, None]
        if variable == "sfcWind":
            level = REF_WIND_MS * (1.0 if w is None else delta_wind(gcm_name, s, w, lon, lat))
            values = np.broadcast_to(level, shape)[None] + 0.4 * season
        elif variable == "rsds":
            level = REF_RSDS_WM2 * (1.0 if w is None else delta_rsds(gcm_name, s, w, lon, lat))
            values = np.broadcast_to(level, shape)[None] + 15.0 * season
        else:
            level = REF_TAS_K + (0.0 if w is None else delta_t(gcm_name, s, w, lon, lat))
            values = np.broadcast_to(level, shape)[None] + 4.0 * season
        ds = xr.Dataset(
            {variable: (("time", "lat", "lon"), values.astype("float32"))},
            coords={"time": time, "lat": NATIVE_LAT, "lon": NATIVE_LON},
        )
        ds[variable].attrs["units"] = {"rsds": "W m-2", "sfcWind": "m s-1", "tas": "K"}[variable]
        return ds

    if experiment == "historical":
        return block((1995, 2014), None)
    return xr.concat([block((2041, 2070), 0), block((2071, 2100), 1)], dim="time")
