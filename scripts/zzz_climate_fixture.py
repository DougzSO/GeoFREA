"""Miniature climate inputs of the ZZZ synthetic country (D13b; METHODOLOGY A-06, V-08).

F4 reads global CMIP6 monthly files, ISIMIP3b daily crops and an ERA5 gust product through their registries. This module writes
small, deterministic stand-ins for all three under `GEOFREA_DATA_DIR/raw/{cmip6,isimip3b,era5}/...`, where
`core.paths.fetched_raw` looks for them, so `external_inputs`, `climate_forcing` and F5 run on ZZZ without a network.

- CMIP6: every GCM of `gcm_ensemble` x {historical 1995-2014, each SSP 2041-2100} x {rsds, sfcWind, tas}, on a 2 degree grid
  around the ZZZ extent. Values are a smooth base times a window effect; one scenario/window of one model carries a wind-speed
  ratio the validity mask must reject (M-F4-07), so the masked path runs in CI.
- ISIMIP3b: three-day stubs for the hazard-channel models (the registry check is by size; no phase of F1 to F5 reads them).
- ERA5: a constant annual-maximum gust product.

Every file carries the mark `SYNTHETIC_MARK` and every registry has a `.synthetic` sidecar; `write_climate_fixture` refuses to
overwrite a registry without one, so a data directory that holds real CMIP6 files is never touched. Use a scratch `GEOFREA_DATA_DIR` for it.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from geofrea.climate_forcing.members import SSP_EXPERIMENT, VARIABLES, load_ensemble
from geofrea.data_acquisition.cmip6_registry import (
    Cmip6NativeGrid,
    Cmip6Registry,
    Cmip6RegistryEntry,
)
from geofrea.data_acquisition.era5_registry import Era5Registry, Era5RegistryEntry
from geofrea.data_acquisition.isimip3b_registry import Isimip3bRegistry, Isimip3bRegistryEntry

SYNTHETIC_MARK = "synthetic ZZZ fixture (scripts/zzz_climate_fixture.py)"
CLIMATE_LAT = np.arange(
    -12.0, 3.0, 2.0
)  # native grid around the ZZZ extent (lon 20.0-20.3, lat -5.0 to -4.8)
CLIMATE_LON = np.arange(14.0, 29.0, 2.0)
UNITS = {"rsds": "W m-2", "sfcWind": "m s-1", "tas": "K"}
# test value: this scenario and window of this model get a wind-speed block the validity mask must reject
MASKED_GCM, MASKED_EXPERIMENT, MASKED_WINDOW = "miroc6", "ssp370", (2071, 2100)
MASKED_WIND_FACTOR = 11.0
MASKED_BLOCK_CENTER = (-8.0, 22.0)  # lat, lon of the one native cell that is raised
MASKED_BLOCK_HALF_WIDTH_DEG = 0.0  # a single native cell


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _monthly_field(variable: str, years: tuple[int, int], effect: float, spike: bool) -> xr.Dataset:
    """Monthly (time, lat, lon) test field: a smooth base plus the window `effect` (a ratio, or K for tas)."""
    time = pd.date_range(f"{years[0]}-01-01", f"{years[1]}-12-01", freq="MS") + pd.Timedelta(
        days=14
    )
    ilat = np.arange(len(CLIMATE_LAT))[None, :, None]
    ilon = np.arange(len(CLIMATE_LON))[None, None, :]
    season = np.sin(2 * np.pi * (np.arange(len(time)) % 12) / 12.0)[:, None, None]
    if variable == "rsds":
        values = (200.0 + 3.0 * ilat + 2.0 * ilon + 20.0 * season) * effect
    elif variable == "sfcWind":
        values = (4.0 + 0.1 * (ilat + ilon) + 0.5 * season) * effect
        if spike:
            block = (
                np.abs(CLIMATE_LAT[None, :, None] - MASKED_BLOCK_CENTER[0])
                <= MASKED_BLOCK_HALF_WIDTH_DEG
            ) & (
                np.abs(CLIMATE_LON[None, None, :] - MASKED_BLOCK_CENTER[1])
                <= MASKED_BLOCK_HALF_WIDTH_DEG
            )
            values = np.where(block, values * MASKED_WIND_FACTOR, values)
    else:
        values = 295.0 + 0.3 * ilat - 0.2 * ilon + 4.0 * season + effect
    ds = xr.Dataset(
        {variable: (("time", "lat", "lon"), values.astype("float32"))},
        coords={"time": time, "lat": CLIMATE_LAT, "lon": CLIMATE_LON},
    )
    ds[variable].attrs["units"] = UNITS[variable]
    return ds


def _effect(variable: str, g: int, s: int, window_index: int) -> float:
    """Window effect of GCM index g, SSP index s: a ratio for rsds and sfcWind, kelvin for tas (round, deterministic)."""
    scale = 1.0 if window_index == 0 else 1.5
    if variable == "rsds":
        return 1.0 + (0.004 * (g - 2.5) + 0.002 * s) * scale
    if variable == "sfcWind":
        return 1.0 - 0.01 * g * (s + 1) / 3.0 * scale
    return (1.0 + 0.5 * g) * (1 + s) * 0.5 * scale


def _marker(path: Path) -> Path:
    return path.with_name(path.name + ".synthetic")


def _mark_registry(path: Path) -> None:
    """A sidecar file marks the registry as the fixture's own (the registry models forbid extra keys)."""
    _marker(path).write_text(SYNTHETIC_MARK + "\n", encoding="utf-8")


def _is_foreign(path: Path) -> bool:
    return path.exists() and not _marker(path).exists()


def write_climate_fixture(experiments_yaml: Path, data_dir: Path | None = None) -> dict[str, int]:
    """Write the miniature climate inputs and their registries; return the file counts.

    Raises:
        SystemExit: a registry already exists and is not a synthetic-fixture registry.
    """
    ensemble = load_ensemble(experiments_yaml)
    raw = Path(data_dir or os.environ["GEOFREA_DATA_DIR"]) / "raw"
    cmip6_dir, isimip_dir, era5_dir = (
        raw / "cmip6" / "_global",
        raw / "isimip3b",
        raw / "era5" / "_global",
    )
    paths = (
        cmip6_dir / "cmip6_registry.json",
        isimip_dir / "isimip3b_registry.json",
        era5_dir / "era5_registry.json",
    )
    for path in paths:
        if _is_foreign(path):
            raise SystemExit(
                f"{path} exists and is not a synthetic-fixture registry: use a scratch GEOFREA_DATA_DIR"
            )
    grid = Cmip6NativeGrid(
        lat_resolution_deg=2.0,
        lon_resolution_deg=2.0,
        lat_min=float(CLIMATE_LAT.min()),
        lat_max=float(CLIMATE_LAT.max()),
        lon_min=float(CLIMATE_LON.min()),
        lon_max=float(CLIMATE_LON.max()),
        n_lat=len(CLIMATE_LAT),
        n_lon=len(CLIMATE_LON),
    )
    experiments = [SSP_EXPERIMENT[s] for s in ensemble.ssps]
    entries: dict[str, Cmip6RegistryEntry] = {}
    for g, gcm in enumerate(ensemble.gcms):
        for experiment in ("historical", *experiments):
            s = experiments.index(experiment) if experiment != "historical" else 0
            years = (1995, 2014) if experiment == "historical" else (2041, 2100)
            for variable in VARIABLES:
                if experiment == "historical":
                    ds = _monthly_field(variable, years, 1.0 if variable != "tas" else 0.0, False)
                else:
                    spike = gcm.cds_name == MASKED_GCM and experiment == MASKED_EXPERIMENT
                    first = _monthly_field(
                        variable, (2041, 2070), _effect(variable, g, s, 0), False
                    )
                    second = _monthly_field(
                        variable, (2071, 2100), _effect(variable, g, s, 1), spike
                    )
                    ds = xr.concat([first, second], dim="time")
                ds.attrs["title"] = SYNTHETIC_MARK
                path = cmip6_dir / gcm.cds_name / f"{gcm.cds_name}_{experiment}_{variable}.nc"
                path.parent.mkdir(parents=True, exist_ok=True)
                ds.to_netcdf(path)
                entry = Cmip6RegistryEntry(
                    model=gcm.cds_name,
                    experiment=experiment,
                    variable=variable,
                    status="registered",
                    global_path=str(path),
                    source_sha256=_sha256(path),
                    temporal_coverage_start=years[0],
                    temporal_coverage_end=years[1],
                    realization="r1i1p1f1",
                    native_grid=grid,
                )
                entries[entry.key] = entry
    Cmip6Registry(entries=entries).save(paths[0])
    _mark_registry(paths[0])

    isimip: dict[str, Isimip3bRegistryEntry] = {}
    for gcm in (g for g in ensemble.gcms if g.hazard_channel):
        name = gcm.cds_name.replace("_", "-")
        for scenario in ("historical", *experiments):
            for variable in ("tasmax", "pr"):
                path = isimip_dir / "ZZZ" / f"{name}_{scenario}_{variable}_ZZZ.nc"
                path.parent.mkdir(parents=True, exist_ok=True)
                value = 300.0 if variable == "tasmax" else 1e-5
                xr.Dataset(
                    {variable: (("time",), np.full(3, value, dtype="float32"))},
                    coords={"time": pd.date_range("2041-01-01", periods=3, freq="D")},
                    attrs={"title": SYNTHETIC_MARK},
                ).to_netcdf(path)
                entry = Isimip3bRegistryEntry(
                    gcm=name,
                    scenario=scenario,
                    variable=variable,
                    country_code="ZZZ",
                    path=str(path),
                    source_sha256=_sha256(path),
                    size_bytes=path.stat().st_size,
                    copied_from=SYNTHETIC_MARK,
                )
                isimip[entry.key] = entry
    Isimip3bRegistry(entries=isimip).save(paths[1])
    _mark_registry(paths[1])

    era5_path = era5_dir / "ZZZ" / "fg10_annual_max_ZZZ.nc"
    era5_path.parent.mkdir(parents=True, exist_ok=True)
    xr.Dataset(
        {"fg10": (("year", "latitude", "longitude"), np.full((20, 3, 3), 15.0, dtype="float32"))},
        coords={
            "year": np.arange(1995, 2015),
            "latitude": [-5.25, -5.0, -4.75],
            "longitude": [19.75, 20.0, 20.25],
        },
        attrs={"title": SYNTHETIC_MARK},
    ).to_netcdf(era5_path)
    era5 = Era5RegistryEntry(
        country_code="ZZZ",
        status="registered",
        source_path=str(era5_path),
        source_sha256=_sha256(era5_path),
        reduced_path=str(era5_path),
        reduced_sha256=_sha256(era5_path),
        reference_period_start=1995,
        reference_period_end=2014,
    )
    Era5Registry(entries={era5.key: era5}).save(paths[2])
    _mark_registry(paths[2])
    return {"cmip6": len(entries), "isimip3b": len(isimip), "era5": 1}
