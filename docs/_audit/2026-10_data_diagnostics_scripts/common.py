# ruff: noqa
"""Shared helpers of the 2026-10 data diagnostics. Read-only on GeoFREA_data; caches go to a scratch directory."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

DATA = Path(os.environ.get("GEOFREA_DATA_DIR", r"D:\Douglas\DOUTORADO\GeoFREA_data"))
SCRATCH = Path(os.environ.get("DIAG_SCRATCH", r"D:\tmp_diag"))
FIG = Path(__file__).resolve().parents[1] / "2026-10_data_diagnostics_figures"
SCRATCH.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

GCMS = {  # label -> file stem in raw/cmip6/_global
    "GFDL-ESM4": "gfdl_esm4",
    "MIROC6": "miroc6",
    "ACCESS-CM2": "access_cm2",
    "IPSL-CM6A-LR": "ipsl_cm6a_lr",
    "CNRM-CM6-1": "cnrm_cm6_1",
    "MRI-ESM2-0": "mri_esm2_0",
}
SSPS = {"SSP1-2.6": "ssp126", "SSP3-7.0": "ssp370", "SSP5-8.5": "ssp585"}
WINDOWS = {"2041-2070": (2041, 2070), "2071-2100": (2071, 2100)}
REF = (1995, 2014)
BBOX = {
    "BRA": (-34.5, 6.0, -74.5, -28.0),
    "PRT": (36.5, 42.5, -10.0, -6.0),
    "IND": (6.0, 37.5, 67.5, 98.0),
}  # lat0, lat1, lon0, lon1


def cmip_path(gcm: str, exp: str, var: str) -> Path:
    return DATA / "raw" / "cmip6" / "_global" / f"{GCMS[gcm]}_{exp}_{var}.nc"


def load_native(gcm: str, exp: str, var: str, country: str, margin: float = 6.0) -> xr.DataArray:
    """Native-grid subset (country bbox + margin degrees), lon in -180..180, sorted."""
    ds = xr.open_dataset(cmip_path(gcm, exp, var))
    da = ds[var]
    lat0, lat1, lon0, lon1 = BBOX[country]
    lon = da["lon"].values
    if lon.max() > 180:
        da = da.assign_coords(lon=((lon + 180) % 360) - 180)
    da = da.sortby("lon").sortby("lat")
    return da.sel(
        lat=slice(lat0 - margin, lat1 + margin), lon=slice(lon0 - margin, lon1 + margin)
    ).load()


def annual_clim(da: xr.DataArray, years: tuple[int, int]) -> xr.DataArray:
    """Mean of the 12 calendar-month climatological means (M-F4-03)."""
    w = da.sel(time=slice(f"{years[0]}-01-01", f"{years[1]}-12-31"))
    assert w.sizes["time"] == (years[1] - years[0] + 1) * 12
    return w.groupby("time.month").mean("time").mean("month")


def country_polygon(country: str):
    import geopandas as gpd

    g = gpd.read_file(DATA / "raw" / "gadm" / country / f"gadm41_{country}_0_mainland.shp")
    return g.to_crs(4326).geometry.union_all()


def native_land_mask(da: xr.DataArray, country: str) -> np.ndarray:
    """True where the native cell centre lies inside the mainland polygon."""
    import shapely

    lon2, lat2 = np.meshgrid(da["lon"].values, da["lat"].values)
    return shapely.contains_xy(country_polygon(country), lon2, lat2)


def candidates(country: str, tech: str) -> pd.DataFrame:
    return pd.read_parquet(
        DATA
        / "outputs"
        / country
        / "land_eligibility"
        / "artifacts"
        / f"candidates_{tech}__central.parquet"
    )


def forcing_cells(country: str) -> pd.DataFrame:
    """Cells of the forcing (country_cells of F4), recomputed from the F2a grid exactly as F4 does."""
    from geofrea.climate_forcing.forcing import country_cells

    return country_cells(
        DATA / "outputs" / country / "grid_alignment" / "artifacts" / f"{country}_grid_aligned.tif"
    )


def md(df: pd.DataFrame, floatfmt: str = ".4g") -> str:
    """Markdown table without the optional `tabulate` dependency."""
    cols = [str(c) for c in df.columns]
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        out.append(
            "| "
            + " | ".join(
                format(v, floatfmt) if isinstance(v, (float, np.floating)) else str(v) for v in row
            )
            + " |"
        )
    return "\n".join(out)
