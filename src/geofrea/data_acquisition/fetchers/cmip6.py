"""CMIP6 resource-channel acquisition from the Copernicus CDS.

Implements: M-F1-04 (resource channel only — monthly rsds, tas, sfcWind).
Scope fixed by F3-1 and docs/phases/F4_climate_forcing.md D-F4-001/D-F4-002:
no daily variable (tasmax/pr come from CRAEI's ISIMIP3b archive, OQ tracked
separately, see docs/OPEN_QUESTIONS.md), historical + 3 SSPs, both windows
combined into one request per experiment (F3-1 confirmed the CDS accepts a
multi-year `year` list in a single request).

Approved model set (D-F4-006): only S-04's minimum, GFDL-ESM4 and MIROC6.
M-F4-02's remaining ensemble slots are chosen in task J-1 against real
acquired data (OQ-009) — not expanded here.

No staging area (F3-1 measured seconds per request, not the hours ISIMIP3b
downloads take): every file writes directly to its destination under
GEOFREA_DATA_DIR, resolved only through geofrea.core.paths (A-08).
"""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import geopandas as gpd
import numpy as np
import rioxarray  # noqa: F401 -- registers the .rio accessor used below
import xarray as xr

CDS_DATASET = "projections-cmip6"

# Approved model set: S-04 minimum only. See module docstring.
CMIP6_MODELS: tuple[str, ...] = ("gfdl_esm4", "miroc6")

# GeoFREA variable name -> CDS `variable` request value.
CMIP6_VARIABLES: dict[str, str] = {
    "rsds": "surface_downwelling_shortwave_radiation",
    "tas": "near_surface_air_temperature",
    "sfcWind": "near_surface_wind_speed",
}

CMIP6_EXPERIMENTS: tuple[str, ...] = ("historical", "ssp126", "ssp370", "ssp585")

# S-05 reference climatology for historical; both future windows (core
# 2041-2070, sensitivity 2071-2100) combined into one request per SSP
# experiment — M-F7-07's H1 needs the resource channel for both windows,
# and F3-1 confirmed a multi-year request is accepted in one call.
YEAR_RANGES: dict[str, tuple[int, int]] = {
    "historical": (1995, 2014),
    "ssp126": (2041, 2100),
    "ssp370": (2041, 2100),
    "ssp585": (2041, 2100),
}

_ALL_MONTHS = [f"{m:02d}" for m in range(1, 13)]

# No in-scope country list here (A-05: no ISO3 literal in src/ outside
# comments/docstrings) — the caller supplies the country list, read from
# config/parameters.json's country keys (see scripts/
# acquire_cmip6_resource_channel.py, matching main.py's own filter).


# Adapted from CRAEI: https://github.com/<douglas-org>/craei
# Commit: 3520edd126f04a3dc2024568b71865477d744b02  Original path: src/craei/acquire/isimip.py:62-79 (IsimipJob, build_jobs)
# Adaptation: enumeration shape kept (one job per model/experiment/
# variable); ISIMIP-specific fields (key_prefix's per-country path,
# scenario terminology) replaced with CDS request fields; there is no
# per-country axis here — the CDS delivers one global file, the
# per-country crop is a separate, fresh step (see crop_to_country_polygon
# below), unlike ISIMIP3b which CRAEI crops as part of the same job.
@dataclass(frozen=True)
class Cmip6Job:
    """One CDS request unit: one model, one experiment, one variable."""

    model: str
    experiment: str
    variable: str

    @property
    def key(self) -> str:
        return f"cmip6/{self.model}/{self.experiment}/{self.variable}"


def build_jobs(
    models: tuple[str, ...] = CMIP6_MODELS,
    experiments: tuple[str, ...] = CMIP6_EXPERIMENTS,
    variables: tuple[str, ...] = tuple(CMIP6_VARIABLES),
) -> list[Cmip6Job]:
    """Enumerate the model x experiment x variable request matrix."""
    return [
        Cmip6Job(model=m, experiment=e, variable=v)
        for m in models
        for e in experiments
        for v in variables
    ]


# Adapted from CRAEI: https://github.com/<douglas-org>/craei
# Commit: 3520edd126f04a3dc2024568b71865477d744b02  Original path: src/craei/acquire/isimip.py:359-381 (_validate_raw_netcdf)
# Adaptation: h5py -> xarray (the CDS delivers a NetCDF file, and
# xarray's own engine sniffing already fails loud on a truncated or
# corrupt file without needing HDF5-specific tooling); same cheap
# sanity check — open the file and read its last time step.
def validate_downloaded_netcdf(path: Path) -> None:
    """Open `path` and read its last time step; raise if unreadable/empty.

    Implements: M-F1-04 (post-download integrity, no server checksum
    available from the CDS the way ISIMIP3b's files API provides one).
    """
    with xr.open_dataset(path) as ds:
        if "time" not in ds.variables:
            raise OSError(f"{path}: no 'time' coordinate found")
        time_vals = ds["time"].values
        if time_vals.size == 0:
            raise OSError(f"{path}: 'time' dimension is empty")
        _ = time_vals[-1]


class RealizationMismatchError(RuntimeError):
    """A model's variables/experiments do not all share one realization label.

    M-F1-04 requires one realization per model, identical across every
    variable and experiment. Fresh check — CRAEI has no counterpart (its
    ISIMIP3b variant labels are a hardcoded, unverified table; F3-1 action
    6). Nothing from the offending model is registered (action 5).
    """

    def __init__(
        self, model: str, key_a: str, label_a: str, key_b: str, label_b: str
    ) -> None:
        super().__init__(
            f"model {model!r}: realization mismatch between "
            f"{key_a!r} ({label_a!r}) and {key_b!r} ({label_b!r})"
        )
        self.model = model


def read_variant_label(path: Path) -> str:
    """Read the CMIP6 realization ('variant_label', e.g. 'r1i1p1f1') from
    the downloaded file's own global attributes.

    Never read from a filename (M-F1-04; no CRAEI counterpart — CRAEI's
    ISIMIP3b variant labels are a hardcoded per-model table, not read
    from any file, see F3-1 action 6).
    """
    with xr.open_dataset(path) as ds:
        label = ds.attrs.get("variant_label")
        if not label:
            raise OSError(f"{path}: no 'variant_label' global attribute found")
        return str(label)


def check_realizations_consistent(labels: dict[str, str], model: str) -> str:
    """Raise RealizationMismatchError unless every label in `labels` agrees.

    `labels` maps a job key (e.g. "cmip6/gfdl_esm4/historical/tas") to the
    realization label read from that job's downloaded file. Returns the
    single agreed label if consistent.
    """
    items = list(labels.items())
    first_key, first_label = items[0]
    for key, label in items[1:]:
        if label != first_label:
            raise RealizationMismatchError(model, first_key, first_label, key, label)
    return first_label


@dataclass(frozen=True)
class NativeGrid:
    """A downloaded model file's native lat/lon grid."""

    lat_resolution_deg: float
    lon_resolution_deg: float
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    n_lat: int
    n_lon: int


def read_native_grid(path: Path) -> NativeGrid:
    """Read a downloaded file's native grid resolution, extent and cell count.

    Fails loud if unreadable. Fresh check: M-F4-04 interpolates from each
    GCM's native grid, and unlike ISIMIP3b (which CRAEI consumes already
    pre-regridded to a shared 0.5 degree grid), raw CDS CMIP6 keeps each
    model's own native grid — no CRAEI counterpart exists for this
    (F3-1 action 5).
    """
    with xr.open_dataset(path) as ds:
        lat = np.asarray(ds["lat"].values, dtype=float)
        lon = np.asarray(ds["lon"].values, dtype=float)
        if lat.size < 2 or lon.size < 2:
            raise OSError(f"{path}: degenerate grid (n_lat={lat.size}, n_lon={lon.size})")
        return NativeGrid(
            lat_resolution_deg=float(np.abs(np.diff(lat)).mean()),
            lon_resolution_deg=float(np.abs(np.diff(lon)).mean()),
            lat_min=float(lat.min()),
            lat_max=float(lat.max()),
            lon_min=float(lon.min()),
            lon_max=float(lon.max()),
            n_lat=int(lat.size),
            n_lon=int(lon.size),
        )


def is_complete_download(final_path: Path, tmp_path: Path) -> Literal["complete", "partial", "absent"]:
    """Distinguish a finished download from a crashed/partial one.

    A live download always writes to `tmp_path` (suffix `.part.nc`) and is
    renamed to `final_path` only after `download_global()` returns
    successfully. A `.part.nc` left on disk (process killed mid-transfer)
    is never treated as complete and is never registered.
    """
    if final_path.exists():
        return "complete"
    if tmp_path.exists():
        return "partial"
    return "absent"


def download_global(client, job: Cmip6Job, out_dir: Path) -> Path:
    """Download one (model, experiment, variable) global monthly file.

    Writes directly to its destination (no staging area, F3-1). The live
    write goes to a `.part.nc` name; only a fully-returned `client.retrieve`
    call gets renamed to the final name, so a partial file is always
    distinguishable from a complete one (see `is_complete_download`).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    final_path = out_dir / f"{job.model}_{job.experiment}_{job.variable}.nc"
    tmp_path = out_dir / f"{job.model}_{job.experiment}_{job.variable}.part.nc"
    tmp_download = out_dir / f"{job.model}_{job.experiment}_{job.variable}.part.download"

    for stale in (tmp_path, tmp_download):
        if stale.exists():
            stale.unlink()

    start_year, end_year = YEAR_RANGES[job.experiment]
    request = {
        "temporal_resolution": "monthly",
        "experiment": job.experiment,
        "variable": CMIP6_VARIABLES[job.variable],
        "model": job.model,
        "year": [str(y) for y in range(start_year, end_year + 1)],
        "month": _ALL_MONTHS,
    }
    client.retrieve(CDS_DATASET, request, str(tmp_download))
    if not tmp_download.exists() or tmp_download.stat().st_size == 0:
        raise OSError(f"{job.key}: download produced no file or an empty file")

    # The CDS delivers a zip archive regardless of the requested target's
    # extension for this dataset; a plain NetCDF response (if the API ever
    # returns one directly) is handled too, so this does not assume either.
    if zipfile.is_zipfile(tmp_download):
        with zipfile.ZipFile(tmp_download) as zf:
            nc_members = [n for n in zf.namelist() if n.endswith(".nc")]
            if not nc_members:
                raise OSError(f"{job.key}: downloaded zip contains no .nc file")
            with zf.open(nc_members[0]) as src, open(tmp_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
        tmp_download.unlink()
    else:
        tmp_download.rename(tmp_path)

    if final_path.exists():
        final_path.unlink()
    tmp_path.rename(final_path)
    return final_path


def crop_to_country_polygon(
    global_path: Path, country_polygon_path: Path, out_path: Path
) -> tuple[int, int]:
    """Crop `global_path` to the real GADM country polygon.

    Fresh (no CRAEI port): CRAEI crops ISIMIP3b to a bounding box
    (`crop_to_country`/`crop_to_countries`, acquire/isimip.py), which is
    exactly the pattern CLAUDE.md's "Geometry over bounding box" rule
    forbids for GeoFREA. A native cell is kept whole iff its center lies
    inside the country polygon — never split, interpolated, or partially
    kept; cells within the polygon's bounding rectangle but outside the
    true polygon boundary are masked to NaN, not dropped from the grid
    axes (keeps every remaining cell on its native grid).

    Returns:
        (cells_before, cells_after): total native cells in the global
        file, and how many cell centers fall inside the country polygon.
    """
    country = gpd.read_file(country_polygon_path)
    geom = country.union_all()

    with xr.open_dataset(global_path) as ds:
        lat = np.asarray(ds["lat"].values, dtype=float)
        lon = np.asarray(ds["lon"].values, dtype=float)
        cells_before = int(lat.size * lon.size)

        lon_wrapped = np.where(lon > 180, lon - 360, lon)
        lon_grid, lat_grid = np.meshgrid(lon_wrapped, lat)
        points = gpd.points_from_xy(lon_grid.ravel(), lat_grid.ravel())
        mask_flat = gpd.GeoSeries(points, crs="EPSG:4326").intersects(geom).to_numpy()
        mask = mask_flat.reshape(lat_grid.shape)  # (lat, lon)
        cells_after = int(mask_flat.sum())

        lat_keep = mask.any(axis=1)
        lon_keep = mask.any(axis=0)
        cropped = ds.isel(lat=lat_keep, lon=lon_keep)
        sub_mask = xr.DataArray(mask[np.ix_(lat_keep, lon_keep)], dims=("lat", "lon"))

        # Mask only variables that actually vary over (lat, lon) — a
        # blanket Dataset.where() also touches ancillary, non-spatial
        # variables (e.g. CMIP6's `time_bnds`), which broke to_netcdf()
        # (object dtype it cannot infer once NaN-masked) even though
        # such variables were never meant to be spatially masked at all.
        for name, var in cropped.data_vars.items():
            if "lat" in var.dims and "lon" in var.dims:
                cropped[name] = var.where(sub_mask)

        # The CDS's raw CMIP6 lat/lon grid is WGS84 by convention, but
        # carries no embedded CRS of its own — unlike CRAEI's GWA files
        # (an externally sourced gap tolerated as-is, D-F1b-005), this
        # file is produced by this crop step itself, so the CRS is
        # written here rather than left for a downstream consumer to
        # assume or fail loud on (data_quality_audit's inspect_raster()
        # refuses to assume a CRS with no reference file to check
        # against — see F3-2 action 9's finding).
        cropped = cropped.rio.write_crs("EPSG:4326")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        cropped.load().to_netcdf(out_path)

    return cells_before, cells_after
