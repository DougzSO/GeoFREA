"""The three miniatures of COMMAND 132 (ZZZ3, ZZZ3b, ZZZ3c; country codes ZZA, ZZB, ZZC): values a person can compute by hand.

They are not full countries (no F1 to F5 run): each one isolates what the earlier synthetic worlds do not exercise.

* ZZA (ZZZ3): 45 degrees west, a country entry with only the required keys, and a transmission grid whose features carry no `voltage` attribute.
* ZZB (ZZZ3b): the box -0.15 to 0.15 degrees of longitude, straddling the Greenwich meridian; the climate fields are written in 0..360 and in
  -180..180, and the change factors read from the two must be identical bit for bit.
* ZZC (ZZZ3c): 65 degrees north, with the area of a pixel and of a decision cell known from the ellipsoid in closed form.

The climate field of every case is linear in the true longitude and latitude (`dT = DT_LON * lon + DT_LAT * lat`), so the bilinear interpolation of F4 is exact and
the expected value at any point is the formula itself.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from shapely.geometry import LineString, Point, box

DT_LON, DT_LAT = 0.5, 0.2  # K per degree
RSDS_RATIO, WIND_RATIO = 1.1, 1.05

BOXES = {  # west, south, east, north
    "ZZA": (-45.15, 0.0, -44.85, 0.20),
    "ZZB": (-0.15, 0.0, 0.15, 0.20),
    "ZZC": (10.00, 65.00, 10.30, 65.20),
}


def dt_field(lat: np.ndarray, lon_true: np.ndarray) -> np.ndarray:
    """The warming (K) at a latitude and a longitude in -180..180: what every file of the miniatures holds, whatever its longitude convention."""
    return DT_LON * lon_true + DT_LAT * lat


def write_borders(raw: Path, iso: str) -> Path:
    west, south, east, north = BOXES[iso]
    out = raw / "countries_borders" / "Synthetica" / f"gadm41_{iso}_0.shp"
    out.parent.mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame({"GID_0": [iso], "COUNTRY": ["Synthetica"]}, geometry=[box(west, south, east, north)], crs="EPSG:4326").to_file(out)
    return out


def write_grid_without_voltage(raw: Path, iso: str) -> Path:
    """A line and a substation with NO `voltage` attribute (the OSM extract of a country that tags none)."""
    west, south, east, north = BOXES[iso]
    mid = (west + east) / 2
    out = raw / "infrastructure_grid" / iso / f"{iso}_grid_osm.geojson"
    out.parent.mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame(
        {"power": ["line", "substation"]},
        geometry=[LineString([(mid, south), (mid, north)]), Point(mid, (south + north) / 2)],
        crs="EPSG:4326",
    ).to_file(out, driver="GeoJSON")
    return out


def _axis(convention: str, lon_true: np.ndarray) -> np.ndarray:
    """The longitude values as stored: `-180..180` as they are, `0..360` with the negative ones plus 360 (and the file sorted ascending)."""
    return np.where(lon_true < 0, lon_true + 360.0, lon_true) if convention == "0..360" else lon_true


def write_climate(directory: Path, convention: str, lat: np.ndarray, lon_true: np.ndarray):
    """The registry of one GCM (historical and ssp126; rsds, sfcWind, tas) with the linear warming field, the longitude axis stored in `convention`.

    `lon_true` are the native longitudes in -180..180. In a `0..360` file the columns are stored sorted by the 0..360 value, as a global file is.
    """
    from geofrea.data_acquisition.cmip6_registry import (
        Cmip6NativeGrid,
        Cmip6Registry,
        Cmip6RegistryEntry,
    )

    stored = _axis(convention, lon_true)
    order = np.argsort(stored, kind="stable")
    stored, lon_sorted = stored[order], lon_true[order]
    registry = Cmip6Registry()
    grid = Cmip6NativeGrid(
        lat_resolution_deg=float(np.abs(np.diff(lat)).mean()),
        lon_resolution_deg=float(np.abs(np.diff(np.sort(lon_true))).mean()),
        lat_min=float(lat.min()),
        lat_max=float(lat.max()),
        lon_min=float(stored.min()),
        lon_max=float(stored.max()),
        n_lat=len(lat),
        n_lon=len(lon_true),
    )
    for experiment in ("historical", "ssp126"):
        years = (1995, 2014) if experiment == "historical" else (2041, 2100)
        times = pd.date_range(f"{years[0]}-01-01", f"{years[1]}-12-01", freq="MS")
        for variable, hist, scen_extra in (("rsds", 200.0, 200.0 * (RSDS_RATIO - 1)), ("sfcWind", 4.0, 4.0 * (WIND_RATIO - 1)), ("tas", 290.0, None)):
            base = np.full((len(lat), len(lon_sorted)), hist)
            if experiment != "historical":
                base = base + (dt_field(lat[:, None], lon_sorted[None, :]) if variable == "tas" else scen_extra)
            data = np.broadcast_to(base, (len(times), *base.shape)).copy()
            path = directory / f"{convention.replace('..', '_')}_{experiment}_{variable}.nc"
            xr.Dataset({variable: (("time", "lat", "lon"), data)}, coords={"time": times, "lat": lat, "lon": stored}).to_netcdf(path)
            entry = Cmip6RegistryEntry(
                model="gfdl_esm4", experiment=experiment, variable=variable, status="registered", global_path=str(path),
                source_sha256="ab" * 32, realization="r1i1p1f1", native_grid=grid,
            )  # fmt: skip
            registry.entries[entry.key] = entry
    return registry
