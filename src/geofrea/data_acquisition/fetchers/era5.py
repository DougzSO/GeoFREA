"""ERA5 gust acquisition from the Copernicus CDS (M-F1-05).

Built fresh: CRAEI's own D12 decided against ERA5 gust entirely, so
there is nothing to adapt (docs/DECISIONS.md, docs/METHODS_SPEC.md;
confirmed against CRAEI_BASELINE_DIR, COMMAND F4-1) — no A-11 header
anywhere in this module.

Scope fixed by COMMAND F4-1/F4-1b: variable `fg10` (10 m wind gust
since previous post-processing, not `i10fg`), the CDS derived
daily-statistics dataset (`daily_statistic: "daily_maximum"`, confirmed
by arithmetic on real probe data to give the same annual maximum as
reducing the raw hourly field — docs/phases/F1_data_acquisition.md
D-F1-016), reduction annual maximum, reference period 1995-2014 (S-05
coherence, docs/phases/F4_climate_forcing.md D-F4-008).

Reuses the CDS client from `fetchers/cmip6.py` (COMMAND F3-2): the same
`cdsapi.Client()`, loaded from the same `.env` credential — no second
client wrapper (see `scripts/acquire_era5_gust.py`, which mirrors
`scripts/acquire_cmip6_resource_channel.py::main()`'s `cdsapi.Client()`
call almost verbatim). Two request-shape differences from a CMIP6
projection request, both because this is a reanalysis, not a
projection (COMMAND F4-2 action 1):

  - Time axis: `fetchers/cmip6.py::download_global()` (line ~242-250)
    requests `year` + `month` only (a monthly product). This module's
    request additionally needs `day` (the field is daily here, having
    already been reduced from hourly server-side) and `daily_statistic`
    — there is no `temporal_resolution` key on this dataset the way
    `projections-cmip6` has one.
  - Area: `download_global()` requests no `area` at all — CMIP6's
    monthly global file is affordable whole-planet, per-country crop
    happens locally afterward. A 20-year daily field at 0.25 deg is not
    affordable whole-planet (F4-1b's hourly probe alone was ~36 GB/year
    at global extent); the CDS `area` bbox parameter is used per
    country instead (`bbox_from_polygon()` below), so — unlike CMIP6 —
    there is no single shared global file: each country gets its own
    CDS-side bbox download, still refined afterward to the true GADM
    polygon.
  - Batching: `download_global()` spans a whole `YEAR_RANGES` window
    (up to 60 years) in one request — F3-1 confirmed the CDS accepts a
    multi-year `year` list for `projections-cmip6`. A real request
    against this dataset for the full 1995-2014 range was rejected
    outright (`403 cost limits exceeded`, COMMAND F4-2 action 1) — a
    hard per-request cost cap `derived-era5-single-levels-daily-statistics`
    enforces that neither `projections-cmip6` nor the raw
    `reanalysis-era5-single-levels` dataset (F4-1b's one-country/
    one-year probe) hit. `download_country_bbox_year()` below requests
    one year at a time instead (20 requests per country) and
    `merge_yearly_files()` concatenates them locally before the polygon
    crop — a genuine batching-granularity difference, not just extra
    request fields.

The GADM-polygon crop step itself (`crop_to_country_polygon()` below)
is adapted from `cmip6.py::crop_to_country_polygon()` (same repository,
not A-11): identical "keep whole native cells, mask the rest to NaN,
write EPSG:4326 explicitly" logic, generalized only for ERA5's
`latitude`/`longitude`/`valid_time` dimension names in place of CMIP6's
`lat`/`lon`/`time` (the CDS's newer unified backend names ERA5 fields
this way; verified against COMMAND F4-1b's real probe file).
"""

from __future__ import annotations

import shutil
import threading
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import geopandas as gpd
import numpy as np
import rioxarray  # noqa: F401 -- registers the .rio accessor used below
import xarray as xr
from dask.callbacks import Callback

# Switched from the CDS derived daily-statistics dataset to the raw
# hourly reanalysis (task F4-2, 2026-09-28, Douglas's verdict): the
# derived dataset (`derived-era5-single-levels-daily-statistics`)
# rejected the intended request twice in real use — first a hard `403
# cost limits exceeded` on a 20-year request, then, even chunked to one
# year per request, a CDS-side queue that never left "accepted" after
# 25+ minutes on two separate real runs (COMMAND F4-2 actions).
# `reanalysis-era5-single-levels` (the raw hourly dataset) is what
# F4-1b's own probe used and it returned in 181s queue + 12s download
# for one country-year — this module now downloads that raw hourly
# field and does the daily-then-annual-maximum reduction locally
# (`compute_daily_maxima()`/`compute_annual_maxima()` below) instead of
# asking the CDS to do it server-side. `_DEPRECATED_ERA5_DERIVED_DATASET`
# is kept only as a historical marker, not used by any function below.
_DEPRECATED_ERA5_DERIVED_DATASET = "derived-era5-single-levels-daily-statistics"
ERA5_DATASET = "reanalysis-era5-single-levels"

# GeoFREA variable name -> CDS `variable` request value. `fg10`, not
# `i10fg`/`instantaneous_10m_wind_gust`: D-F4-008 selected the
# max-over-interval gust (matches C2's cut-out/tracker-stow framing),
# not the instantaneous one — unchanged by the dataset switch above,
# this is still the same physical variable, `fg10`, now read from the
# raw hourly field (max-since-previous-post-processing, i.e. the max
# over the hour preceding each timestamp) and reduced locally instead
# of requesting the CDS's own daily maximum of it.
ERA5_VARIABLES: dict[str, str] = {"fg10": "10m_wind_gust_since_previous_post_processing"}

# S-05 reference period (D-F4-008), coherent with M-F4-03's own
# historical reference (cmip6.py::YEAR_RANGES["historical"]).
REFERENCE_PERIOD: tuple[int, int] = (1995, 2014)

_ALL_MONTHS = [f"{m:02d}" for m in range(1, 13)]
_ALL_DAYS = [f"{d:02d}" for d in range(1, 32)]
_ALL_HOURS = [f"{h:02d}:00" for h in range(24)]

# No in-scope country list here (A-05: no ISO3 literal in src/ outside
# comments/docstrings) — same convention as cmip6.py; the caller
# supplies the country list (see scripts/acquire_era5_gust.py).


@dataclass(frozen=True)
class Era5Job:
    """One CDS request unit: one country, one variable.

    No model/experiment axis (unlike Cmip6Job) — ERA5 is a single
    reanalysis product, not an ensemble of GCM projections.
    """

    country: str
    variable: str = "fg10"

    @property
    def key(self) -> str:
        return f"era5/{self.country}/{self.variable}"


def bbox_from_polygon(country_polygon_path: Path, margin_deg: float = 0.5) -> list[float]:
    """Compute a CDS `area` bbox [N, W, S, E] around a country's real GADM polygon.

    A margin is added so the polygon crop step afterward (action 4)
    always has whole native cells on every side to intersect against,
    never a boundary cell truncated by the CDS-side bbox itself.
    """
    country = gpd.read_file(country_polygon_path)
    minx, miny, maxx, maxy = country.total_bounds
    return [
        float(maxy + margin_deg),
        float(minx - margin_deg),
        float(miny - margin_deg),
        float(maxx + margin_deg),
    ]


def is_complete_download(final_path: Path, tmp_path: Path) -> Literal["complete", "partial", "absent"]:
    """Distinguish a finished download from a crashed/partial one.

    Same pattern as `cmip6.py::is_complete_download()`: a live download
    always writes to `tmp_path` first, renamed to `final_path` only
    after the CDS call returns successfully.
    """
    if final_path.exists():
        return "complete"
    if tmp_path.exists():
        return "partial"
    return "absent"


def _request_for_year(variable: str, year: int, bbox: list[float]) -> dict:
    """Raw hourly request — same shape F4-1b's real probe used successfully
    (`reanalysis-era5-single-levels`, product_type=reanalysis, full year,
    all months/days/hours, bbox `area`)."""
    return {
        "product_type": "reanalysis",
        "variable": ERA5_VARIABLES[variable],
        "year": [str(year)],
        "month": _ALL_MONTHS,
        "day": _ALL_DAYS,
        "time": _ALL_HOURS,
        "area": bbox,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def download_country_bbox_year(
    client, job: Era5Job, year: int, bbox: list[float], out_dir: Path
) -> Path:
    """Download one country's raw hourly `fg10` field for one year, CDS-side bbox-filtered.

    One request per year (20 requests per country over the reference
    period), CDS-side bbox pre-filtered — no per-country truly-global
    file the way CMIP6 has one, for the same reason CMIP6 does not need
    the derived-dataset dance this module went through: see module
    docstring for why the CDS derived daily-statistics dataset was
    dropped in favor of this raw hourly one.

    Idempotent by design at the caller level (`scripts/acquire_era5_gust.py`
    checks each year's file + recorded sha256 before calling this again
    — resume never re-downloads a year already on disk and intact).

    Writes directly to its destination (no staging area, same
    rationale as `cmip6.py::download_global()`). The live write goes to
    a `.part.nc` name; only a fully-returned `client.retrieve` call
    gets renamed to the final name.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    final_path = out_dir / f"{job.country}_{job.variable}_hourly_bbox_{year}.nc"
    tmp_path = out_dir / f"{job.country}_{job.variable}_hourly_bbox_{year}.part.nc"
    tmp_download = out_dir / f"{job.country}_{job.variable}_hourly_bbox_{year}.part.download"

    for stale in (tmp_path, tmp_download):
        if stale.exists():
            stale.unlink()

    request = _request_for_year(job.variable, year, bbox)
    client.retrieve(ERA5_DATASET, request, str(tmp_download))
    if not tmp_download.exists() or tmp_download.stat().st_size == 0:
        raise OSError(f"{job.key}/{year}: download produced no file or an empty file")

    if zipfile.is_zipfile(tmp_download):
        with zipfile.ZipFile(tmp_download) as zf:
            nc_members = [n for n in zf.namelist() if n.endswith(".nc")]
            if not nc_members:
                raise OSError(f"{job.key}/{year}: downloaded zip contains no .nc file")
            with zf.open(nc_members[0]) as src, open(tmp_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
        tmp_download.unlink()
    else:
        tmp_download.rename(tmp_path)

    if final_path.exists():
        final_path.unlink()
    tmp_path.rename(final_path)
    return final_path


class _LoggingProgress(Callback):
    """Log periodic `dask.array.store()` task-completion progress to stdout.

    2026-09-30: with no visibility inside a long `to_netcdf()` write,
    Douglas had nothing between "still running" and "done" for over an
    hour during BRA's crop step -- the target file's logical size is
    fixed by NetCDF's own pre-allocation, so file size cannot answer
    "how far along is this". Dask's own scheduler already knows task
    completion counts; this just logs them, throttled to `interval_s`
    (not per-task -- a chunked write can be thousands of tasks) so the
    log stays readable instead of spammed.
    """

    def __init__(self, label: str, interval_s: float = 30.0) -> None:
        self.label = label
        self.interval_s = interval_s
        self._lock = threading.Lock()
        self._start = 0.0
        self._total = 0
        self._done = 0
        self._last_log = 0.0

    def _start_state(self, dsk, state) -> None:  # noqa: ANN001 -- dask's own untyped Callback hook signature
        self._start = time.time()
        self._total = sum(len(state[k]) for k in ("ready", "waiting", "running", "finished"))
        self._done = len(state["finished"])
        self._last_log = self._start
        print(f"[{self.label}-progress] 0% (0/{self._total} tasks)", flush=True)

    def _posttask(self, key, result, dsk, state, worker_id) -> None:  # noqa: ANN001
        with self._lock:
            self._done += 1
            now = time.time()
            done, total = self._done, self._total
            if now - self._last_log < self.interval_s and done < total:
                return
            self._last_log = now
        pct = round(100 * done / total) if total else 100
        print(
            f"[{self.label}-progress] {pct}% ({done}/{total} tasks, {now - self._start:.0f}s elapsed)",
            flush=True,
        )


def merge_yearly_files(year_paths: list[Path], out_path: Path) -> Path:
    """Concatenate per-year hourly files along time into one bbox source file.

    Pure function, no network — the per-year files are already on disk
    once `download_country_bbox_year()` has run for the full reference
    period.

    Streamed via dask, not `.load()`-ed into one array first (found in
    real use, COMMAND F4-6/F4-7, 2026-09-28/29): `open_mfdataset()` is
    already dask-backed by default (one chunk per input file, i.e. one
    year), but the prior code called `.load()` before `.to_netcdf()`,
    forcing the full 20-year hourly field into a single in-memory numpy
    array first — `MemoryError: Unable to allocate 3.57 GiB for an
    array with shape (175320, 52, 105)` on PRT's real 20-year merge
    (52x105 is PRT's small CDS-side bbox grid; BRA's is far larger). `merged.to_netcdf(out_path)` on the still-dask-backed
    dataset writes it chunk by chunk instead (`dask.array.store`'s
    write path), keeping peak memory near one year's worth of data
    (~150-200 MB) regardless of how many years are merged.
    """
    with xr.open_mfdataset(sorted(year_paths), combine="by_coords") as merged:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with _LoggingProgress("merge"):
            merged.to_netcdf(out_path)
    return out_path


def validate_downloaded_netcdf(path: Path) -> None:
    """Open `path` and read its last time step; raise if unreadable/empty.

    Adapted from `cmip6.py::validate_downloaded_netcdf()`: same cheap
    sanity check, generalized to accept either `time` (CMIP6) or
    `valid_time` (ERA5's dimension name on the CDS's unified backend).
    """
    with xr.open_dataset(path) as ds:
        time_name = "valid_time" if "valid_time" in ds.variables else "time"
        if time_name not in ds.variables:
            raise OSError(f"{path}: no 'time'/'valid_time' coordinate found")
        time_vals = ds[time_name].values
        if time_vals.size == 0:
            raise OSError(f"{path}: '{time_name}' dimension is empty")
        _ = time_vals[-1]


@dataclass(frozen=True)
class NativeGrid:
    """A downloaded file's native grid resolution, extent and cell count."""

    lat_resolution_deg: float
    lon_resolution_deg: float
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    n_lat: int
    n_lon: int


def read_native_grid(path: Path) -> NativeGrid:
    """Read a downloaded file's native grid. Adapted from `cmip6.py::read_native_grid()`
    for ERA5's `latitude`/`longitude` dimension names."""
    with xr.open_dataset(path) as ds:
        lat_name = "latitude" if "latitude" in ds.variables else "lat"
        lon_name = "longitude" if "longitude" in ds.variables else "lon"
        lat = np.asarray(ds[lat_name].values, dtype=float)
        lon = np.asarray(ds[lon_name].values, dtype=float)
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


def crop_to_country_polygon(
    bbox_path: Path, country_polygon_path: Path, out_path: Path
) -> tuple[int, int]:
    """Crop `bbox_path` (CDS-side bbox download) to the real GADM country polygon.

    Adapted from `cmip6.py::crop_to_country_polygon()` (same repository,
    not A-11 — see module docstring): identical "keep whole native
    cells, mask the rest to NaN, write EPSG:4326 explicitly" logic,
    generalized for ERA5's `latitude`/`longitude` dimension names.

    Returns:
        (cells_before, cells_after): total native cells in the
        bbox-downloaded file, and how many cell centers fall inside the
        country polygon.
    """
    country = gpd.read_file(country_polygon_path)
    geom = country.union_all()

    # chunks="auto" (COMMAND F4-7): dask-backed, same reason as
    # merge_yearly_files() above -- bbox_path is already the full
    # multi-year merged field by this point, so an eager open here
    # would re-materialize the exact array `merge_yearly_files()` was
    # just fixed to avoid holding in memory.
    with xr.open_dataset(bbox_path, chunks="auto") as ds:
        lat_name = "latitude" if "latitude" in ds.variables else "lat"
        lon_name = "longitude" if "longitude" in ds.variables else "lon"
        lat = np.asarray(ds[lat_name].values, dtype=float)
        lon = np.asarray(ds[lon_name].values, dtype=float)
        cells_before = int(lat.size * lon.size)

        lon_wrapped = np.where(lon > 180, lon - 360, lon)
        lon_grid, lat_grid = np.meshgrid(lon_wrapped, lat)
        points = gpd.points_from_xy(lon_grid.ravel(), lat_grid.ravel())
        mask_flat = gpd.GeoSeries(points, crs="EPSG:4326").intersects(geom).to_numpy()
        mask = mask_flat.reshape(lat_grid.shape)  # (lat, lon)
        cells_after = int(mask_flat.sum())

        lat_keep = mask.any(axis=1)
        lon_keep = mask.any(axis=0)
        cropped = ds.isel({lat_name: lat_keep, lon_name: lon_keep})
        sub_mask = xr.DataArray(mask[np.ix_(lat_keep, lon_keep)], dims=(lat_name, lon_name))

        for name, var in cropped.data_vars.items():
            if lat_name in var.dims and lon_name in var.dims:
                cropped[name] = var.where(sub_mask)

        cropped = cropped.rio.write_crs("EPSG:4326")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with _LoggingProgress("crop"):  # dask-backed write, see chunks= note above
            cropped.to_netcdf(out_path)

    return cells_before, cells_after


def compute_daily_maxima(hourly_path: Path, variable: str = "fg10") -> xr.Dataset:
    """Reduce an hourly field to one daily maximum per cell per UTC calendar day.

    Pure function, no network dependency. M-F1-05 does not state a
    timezone for the daily reduction it describes — ERA5's own
    `valid_time` coordinate is UTC and is used as-is here rather than
    converted to a per-country local time; this default is registered
    as OQ-037 (docs/OPEN_QUESTIONS.md), not resolved silently (task
    F4-2, Douglas's verdict pending).

    Replaces the CDS's own `daily_statistic: "daily_maximum"` derived
    product (dropped — see module docstring): this is the same
    reduction, computed locally over the raw hourly field instead of
    server-side.

    Opened dask-backed (`chunks="auto"`, COMMAND F4-7) so the
    resample-max reduction itself runs chunked rather than forcing the
    full hourly field into memory first -- but still materialized
    (`.load()`) before returning, inside this function's own `with`
    block: `hourly_path` here is `crop_to_country_polygon()`'s output
    (already reduced to the real country polygon's cells, not the full
    CDS-side bbox rectangle `merge_yearly_files()`/
    `crop_to_country_polygon()` had to fix for, COMMAND F4-6/F4-7's
    real MemoryError), so this step's own memory footprint was not the
    reported failure. Kept eager (rather than deferred like the two
    steps above) because the returned Dataset must stay usable after
    this function's own file handle closes -- `compute_annual_maxima()`
    below documents its `xr.Dataset` input as already in-memory.
    """
    with xr.open_dataset(hourly_path, chunks="auto") as ds:
        time_name = "valid_time" if "valid_time" in ds.variables else "time"
        da = ds[variable]
        daily = da.resample({time_name: "1D"}).max()
        return daily.load().to_dataset(name=variable)


def compute_annual_maxima(daily_max_path: Path | xr.Dataset, variable: str = "fg10") -> xr.DataArray:
    """Reduce a daily-maximum field to one annual maximum per cell per year.

    Pure function over the downloaded/cropped/daily-reduced field, no
    network dependency (action 5). Accepts either a path to a
    daily-maximum NetCDF or an already-open Dataset (the in-memory
    output of `compute_daily_maxima()`), so the daily-then-annual
    pipeline does not require an intermediate file write between the
    two reductions. Kept per-year (not collapsed to a single period
    scalar): the period-level indicator M-F1-05 describes is the mean
    of these annual maxima, a cheap downstream aggregate over this
    already-small product — see docs/phases/F4_climate_forcing.md
    D-F4-009 for why this representation was chosen over collapsing to
    one scalar at acquisition time.
    """
    if isinstance(daily_max_path, xr.Dataset):
        ds = daily_max_path
        time_name = "valid_time" if "valid_time" in ds.variables else "time"
        da = ds[variable]
        annual = da.groupby(f"{time_name}.year").max(dim=time_name)
        return annual.load()

    with xr.open_dataset(daily_max_path) as ds:
        time_name = "valid_time" if "valid_time" in ds.variables else "time"
        da = ds[variable]
        annual = da.groupby(f"{time_name}.year").max(dim=time_name)
        return annual.load()


def write_annual_maxima_from_hourly(hourly_path: Path, out_path: Path, variable: str = "fg10") -> None:
    """Compute daily-then-annual maxima from a raw hourly field and persist the result.

    The pipeline requested in COMMAND F4-2's dataset-switch verdict:
    hourly max per day (UTC calendar day, OQ-037), then annual max per
    year from those daily maxima — not a single-step max over all
    hours, so the daily-maximum intermediate stays an explicit,
    auditable step even though `max` is associative and would give the
    same annual result either way.
    """
    daily_ds = compute_daily_maxima(hourly_path, variable=variable)
    annual = compute_annual_maxima(daily_ds, variable=variable)
    ds_out = annual.to_dataset(name=variable)
    ds_out = ds_out.rio.write_crs("EPSG:4326")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with _LoggingProgress("reduce"):
        ds_out.to_netcdf(out_path)
