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

import hashlib
import multiprocessing as mp
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

# 2026-09-30, real use: a `to_netcdf()` write on BRA's merge froze
# twice -- zero CPU across *every* thread in the process, no PageIn
# wait (unlike the separate RAM-thrash stall earlier the same day, and
# system RAM was healthy both times). An identical call against the
# same files ran cleanly in a fresh process, but a second repro against
# those files also froze *while the first frozen process was still
# alive*, and started working again immediately after killing it --
# consistent with the frozen process holding some OS/disk-level
# resource that blocked other processes' I/O on the same drive, not a
# reproducible bug in this module's own logic. No Python stack trace
# was obtainable (no signal-based introspection for a hung process on
# Windows) to confirm the exact syscall.
#
# A same-process thread watchdog was tried first and did not work: all
# threads showed zero CPU, including the polling thread itself -- if
# the freeze holds the GIL (a C-extension call that does not release it
# around a blocking syscall, which HDF5/netCDF4 are not guaranteed to
# do on every code path), no thread in that same process can run Python
# bytecode to notice or act on the stall. `_run_worker_with_watchdog()`
# below runs the actual write in a **separate OS process**
# (`multiprocessing`, not `threading`) instead: the parent polls a
# shared counter and calls `Process.terminate()`/`.kill()` on stall,
# both of which act at the OS level and do not depend on the child's
# interpreter making any progress.
WRITE_STALL_TIMEOUT_S = 15 * 60

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

    def __init__(self, label: str, interval_s: float = 30.0, mp_progress=None) -> None:
        self.label = label
        self.interval_s = interval_s
        self.mp_progress = mp_progress  # a multiprocessing.Value('l'), shared with the parent process's watchdog
        self._lock = threading.Lock()
        self._start = 0.0
        self._total = 0
        self._done = 0
        self._last_log = 0.0

    def _start_state(self, dsk, state) -> None:
        self._start = time.time()
        self._total = sum(len(state[k]) for k in ("ready", "waiting", "running", "finished"))
        self._done = len(state["finished"])
        self._last_log = self._start
        if self.mp_progress is not None:
            self.mp_progress.value = self._done
        print(f"[{self.label}-progress] 0% (0/{self._total} tasks)", flush=True)

    def _posttask(self, key, result, dsk, state, worker_id) -> None:
        with self._lock:
            self._done += 1
            now = time.time()
            done, total = self._done, self._total
            if self.mp_progress is not None:
                self.mp_progress.value = done
            if now - self._last_log < self.interval_s and done < total:
                return
            self._last_log = now
        pct = round(100 * done / total) if total else 100
        print(
            f"[{self.label}-progress] {pct}% ({done}/{total} tasks, {now - self._start:.0f}s elapsed)",
            flush=True,
        )


def _run_worker_with_watchdog(
    target, args: tuple, label: str, result_queue: mp.Queue | None = None
):
    """Run `target(*args, mp_progress[, result_queue])` in its own OS process; kill it if stalled.

    See `WRITE_STALL_TIMEOUT_S`'s module-level comment for why this is
    a *process* (`multiprocessing`), not a thread: a same-process
    thread watchdog was tried first and could not detect the real
    stall it was built for, because that stall showed zero CPU on
    every thread including the watchdog's own polling thread -- a
    same-process fallback offers no protection if the freeze holds the
    GIL. `Process.terminate()`/`.kill()` act at the OS level and work
    regardless of what the child's interpreter is doing.

    `target` must be an importable module-level function (Windows uses
    the `spawn` start method, which pickles a reference to `target` by
    qualified name, not a closure) whose last positional parameter is
    `mp_progress: multiprocessing.sharedctypes.Synchronized` -- it must
    update `mp_progress.value` as work progresses (the `_LoggingProgress`
    callback's `mp_progress=` parameter does this automatically). If
    `result_queue` is given, it is appended as the final argument and
    `target` must `.put()` its return value onto it.
    """
    mp_progress = mp.Value("l", -1)
    full_args = (*args, mp_progress) if result_queue is None else (*args, mp_progress, result_queue)
    proc = mp.Process(target=target, args=full_args)
    proc.start()
    try:
        last_value = -1
        last_progress_at = time.time()
        while True:
            proc.join(timeout=10)
            if not proc.is_alive():
                break
            value = mp_progress.value
            if value != last_value:
                last_value = value
                last_progress_at = time.time()
                continue
            if time.time() - last_progress_at > WRITE_STALL_TIMEOUT_S:
                proc.terminate()
                proc.join(timeout=30)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=30)
                raise TimeoutError(
                    f"{label}: no write progress for {WRITE_STALL_TIMEOUT_S}s "
                    f"(worker pid {proc.pid}, {value} tasks done) -- terminated as hung"
                )
    finally:
        if proc.is_alive():
            proc.terminate()
    if proc.exitcode != 0:
        raise RuntimeError(f"{label}: worker subprocess exited with code {proc.exitcode}")


def _merge_worker(year_paths: list[Path], out_path: Path, label: str, mp_progress) -> None:
    """Subprocess entry point for `merge_yearly_files()` -- see `_run_worker_with_watchdog()`."""
    with xr.open_mfdataset(sorted(year_paths), combine="by_coords") as merged:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with _LoggingProgress(label, mp_progress=mp_progress):
            merged.to_netcdf(out_path)


def _merge_to(paths: list[Path], out_path: Path, label: str) -> None:
    """Run one watchdog-supervised merge, atomically (`.part.nc` tmp name, renamed on success).

    A killed attempt (watchdog timeout, crash, power loss) leaves only
    the tmp file behind -- `out_path` only ever exists fully written,
    so callers can use `out_path.exists()` as a trustworthy
    skip-if-intact check, same as the per-year download's `.part.nc`
    pattern (`download_country_bbox_year()`).
    """
    tmp_path = out_path.with_suffix(".part.nc")
    if tmp_path.exists():
        tmp_path.unlink()
    _run_worker_with_watchdog(_merge_worker, (sorted(paths), tmp_path, label), label)
    if out_path.exists():
        out_path.unlink()
    tmp_path.rename(out_path)


_MERGE_BATCH_SIZE = 5  # years per intermediate merge batch -- see merge_yearly_files() docstring


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

    Runs in a watchdog-supervised subprocess (COMMAND 2026-09-30, see
    `WRITE_STALL_TIMEOUT_S`) -- functionally identical to calling
    `xr.open_mfdataset(...).to_netcdf(out_path)` directly, just immune
    to hanging forever if the write itself freezes.

    Batched (COMMAND 2026-10-01: BRA's merge itself stalled at 0 tasks
    under the watchdog on a re-run, same intermittent external-drive
    I/O hang already seen on the crop step -- see `WRITE_STALL_TIMEOUT_S`'s
    comment; not a code bug, the watchdog caught it correctly). Years
    are merged in groups of `_MERGE_BATCH_SIZE` first, each batch
    written atomically to its own intermediate file
    (`<out_path stem>_batch<N>of<M>.nc`) before a final merge combines
    the batches into `out_path`. A watchdog-killed attempt only loses
    the one batch (or final merge) in progress -- already-finished
    batches are kept and skipped on retry, the same skip-if-intact
    resume pattern used for the per-year downloads. With
    `len(year_paths) <= _MERGE_BATCH_SIZE` there is only one batch,
    merged directly to `out_path` with no intermediate file.
    """
    sorted_years = sorted(year_paths)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    batches = [sorted_years[i : i + _MERGE_BATCH_SIZE] for i in range(0, len(sorted_years), _MERGE_BATCH_SIZE)]

    if len(batches) == 1:
        _merge_to(batches[0], out_path, "merge")
        return out_path

    n = len(batches)
    batch_out_paths = [out_path.with_name(f"{out_path.stem}_batch{i + 1}of{n}{out_path.suffix}") for i in range(n)]
    for i, (batch, batch_out) in enumerate(zip(batches, batch_out_paths), start=1):
        if batch_out.exists():
            print(f"[merge-skip] batch {i}/{n} already merged: {batch_out.name}", flush=True)
            continue
        _merge_to(batch, batch_out, f"merge-batch{i}of{n}")

    _merge_to(batch_out_paths, out_path, "merge-final")
    for batch_out in batch_out_paths:
        batch_out.unlink(missing_ok=True)
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
            # Median, not mean: a polygon-cropped axis drops rows/columns with no
            # in-polygon cell (islands: PRT, IND), so some steps are multiples of
            # the native step and the mean would overstate the resolution.
            lat_resolution_deg=float(np.median(np.abs(np.diff(lat)))),
            lon_resolution_deg=float(np.median(np.abs(np.diff(lon)))),
            lat_min=float(lat.min()),
            lat_max=float(lat.max()),
            lon_min=float(lon.min()),
            lon_max=float(lon.max()),
            n_lat=int(lat.size),
            n_lon=int(lon.size),
        )


_CROP_TIME_CHUNK_SIZE = 500  # hours per chunk after rechunking -- see _crop_worker()'s rechunk comment


def _crop_worker(
    bbox_path: Path,
    country_polygon_path: Path,
    out_path: Path,
    year_range: tuple[int, int] | None,
    mp_progress,
    result_queue,
) -> None:
    """Subprocess entry point for `crop_to_country_polygon()` -- see `_run_worker_with_watchdog()`."""
    country = gpd.read_file(country_polygon_path)
    geom = country.union_all()

    # chunks="auto" (COMMAND F4-7): dask-backed, same reason as
    # merge_yearly_files() above -- bbox_path is already the full
    # multi-year merged field by this point, so an eager open here
    # would re-materialize the exact array `merge_yearly_files()` was
    # just fixed to avoid holding in memory.
    with xr.open_dataset(bbox_path, chunks="auto") as ds:
        time_name = "valid_time" if "valid_time" in ds.variables else "time"
        if year_range is not None:
            start, end = year_range
            ds = ds.sel({time_name: slice(f"{start}-01-01", f"{end}-12-31")})
        # Rechunk the time axis to a small, fixed size (COMMAND 2026-10-05:
        # BRA's crop-batch1of4 stalled at exactly 301/535 tasks three times
        # in a row across separate run attempts, same batch, different
        # worker pids -- not plausible as pure random external-drive I/O
        # timing, since that would not reproduce the identical task index.
        # `chunks="auto"` above sizes chunks from the *full* multi-year
        # file before this batch's year_range slice is applied, so one
        # inherited chunk can land disproportionately large for this
        # batch and consistently exceed WRITE_STALL_TIMEOUT_S. Rechunking
        # to a small, uniform time-chunk size after slicing bounds every
        # write task to roughly the same size regardless of which batch
        # or file boundary it falls on.
        ds = ds.chunk({time_name: _CROP_TIME_CHUNK_SIZE})
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
        with _LoggingProgress("crop", mp_progress=mp_progress):  # dask-backed write, see chunks= note above
            cropped.to_netcdf(out_path)

    result_queue.put((cells_before, cells_after))


def _crop_cell_counts(bbox_path: Path, country_polygon_path: Path) -> tuple[int, int]:
    """Cheaply recompute (cells_before, cells_after) without writing any netcdf.

    Same lat/lon-only mask logic as `_crop_worker()`, minus the actual
    crop-and-write -- used when every crop batch was already on disk
    from a prior run, so there is no fresh worker result to read.
    """
    country = gpd.read_file(country_polygon_path)
    geom = country.union_all()
    with xr.open_dataset(bbox_path) as ds:
        lat_name = "latitude" if "latitude" in ds.variables else "lat"
        lon_name = "longitude" if "longitude" in ds.variables else "lon"
        lat = np.asarray(ds[lat_name].values, dtype=float)
        lon = np.asarray(ds[lon_name].values, dtype=float)
        cells_before = int(lat.size * lon.size)
        lon_wrapped = np.where(lon > 180, lon - 360, lon)
        lon_grid, lat_grid = np.meshgrid(lon_wrapped, lat)
        points = gpd.points_from_xy(lon_grid.ravel(), lat_grid.ravel())
        mask_flat = gpd.GeoSeries(points, crs="EPSG:4326").intersects(geom).to_numpy()
        cells_after = int(mask_flat.sum())
    return cells_before, cells_after


_CROP_BATCH_YEARS = 1  # years per intermediate crop batch (lowered from 5, COMMAND 2026-10-05: smaller
# batches bound how much work a watchdog kill loses per retry, on top of the time-axis rechunk fix
# above) -- see crop_to_country_polygon() docstring


def _crop_year_batches(bbox_path: Path) -> list[tuple[int, int]]:
    """Split `bbox_path`'s valid_time span into `_CROP_BATCH_YEARS`-year (start, end) ranges."""
    with xr.open_dataset(bbox_path) as ds:
        time_name = "valid_time" if "valid_time" in ds.variables else "time"
        years = sorted({int(y) for y in ds[time_name].dt.year.values})
    return [
        (years[i], years[min(i + _CROP_BATCH_YEARS, len(years)) - 1])
        for i in range(0, len(years), _CROP_BATCH_YEARS)
    ]


def _crop_to(
    bbox_path: Path,
    country_polygon_path: Path,
    out_path: Path,
    label: str,
    year_range: tuple[int, int] | None = None,
) -> tuple[int, int]:
    """Run one watchdog-supervised crop, atomically (`.part.nc` tmp name, renamed on success).

    Same atomic-write pattern as `_merge_to()` -- see that function's
    docstring.
    """
    tmp_path = out_path.with_suffix(".part.nc")
    if tmp_path.exists():
        tmp_path.unlink()
    result_queue: mp.Queue = mp.Queue()
    _run_worker_with_watchdog(
        _crop_worker,
        (bbox_path, country_polygon_path, tmp_path, year_range),
        label,
        result_queue=result_queue,
    )
    cells = result_queue.get(timeout=30)
    if out_path.exists():
        out_path.unlink()
    tmp_path.rename(out_path)
    return cells


def crop_to_country_polygon(
    bbox_path: Path, country_polygon_path: Path, out_path: Path
) -> tuple[int, int]:
    """Crop `bbox_path` (CDS-side bbox download) to the real GADM country polygon.

    Adapted from `cmip6.py::crop_to_country_polygon()` (same repository,
    not A-11 — see module docstring): identical "keep whole native
    cells, mask the rest to NaN, write EPSG:4326 explicitly" logic,
    generalized for ERA5's `latitude`/`longitude` dimension names.

    Runs in a watchdog-supervised subprocess (COMMAND 2026-09-30, see
    `WRITE_STALL_TIMEOUT_S`) for the same reason `merge_yearly_files()`
    does.

    Batched (COMMAND 2026-10-05: BRA's and IND's crop steps kept
    stalling under the watchdog -- same intermittent external-drive I/O
    hang as `merge_yearly_files()`'s own batching fix, just hitting the
    crop write instead of the merge write). `bbox_path`'s time span is
    split into groups of `_CROP_BATCH_YEARS` years, each cropped and
    written atomically to its own intermediate file
    (`<out_path stem>_batch<N>of<M>.nc`) before a final concat combines
    the batches into `out_path`. A watchdog-killed attempt only loses
    the one batch (or final concat) in progress -- already-finished
    batches are kept and skipped on retry, same skip-if-intact resume
    pattern as the merge batching. With a single year-range covering the
    whole file there is only one batch, cropped directly to `out_path`
    with no intermediate file.

    Returns:
        (cells_before, cells_after): total native cells in the
        bbox-downloaded file, and how many cell centers fall inside the
        country polygon.
    """
    year_batches = _crop_year_batches(bbox_path)

    if len(year_batches) == 1:
        return _crop_to(bbox_path, country_polygon_path, out_path, "crop", year_batches[0])

    n = len(year_batches)
    batch_out_paths = [out_path.with_name(f"{out_path.stem}_batch{i + 1}of{n}{out_path.suffix}") for i in range(n)]
    cells: tuple[int, int] | None = None
    for i, (year_range, batch_out) in enumerate(zip(year_batches, batch_out_paths), start=1):
        if batch_out.exists():
            print(f"[crop-skip] batch {i}/{n} already cropped: {batch_out.name}", flush=True)
            continue
        cells = _crop_to(bbox_path, country_polygon_path, batch_out, f"crop-batch{i}of{n}", year_range)

    _merge_to(batch_out_paths, out_path, "crop-final")
    for batch_out in batch_out_paths:
        batch_out.unlink(missing_ok=True)

    if cells is None:
        # Every batch was already cropped on a prior run (all skipped
        # above, so no `_crop_to()` call ran to hand back a result).
        # cells_before/cells_after depend only on bbox_path's lat/lon
        # grid and the country polygon, not on which years a batch
        # covers, so recomputing the mask directly is cheap and exact
        # -- no need to re-run any crop.
        cells = _crop_cell_counts(bbox_path, country_polygon_path)
    return cells


def compute_daily_maxima(hourly_path: Path, variable: str = "fg10") -> xr.Dataset:
    """Reduce an hourly field to one daily maximum per cell per UTC calendar day.

    Pure function, no network dependency. M-F1-05 does not state a
    timezone for the daily reduction it describes — ERA5's own
    `valid_time` coordinate is UTC and is used as-is here rather than
    converted to a per-country local time. Douglas's verdict (OQ-037,
    2026-10-06): UTC is kept -- see docs/phases/F4_climate_forcing.md D-F4-011.

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


def _reduce_worker(hourly_path: Path, out_path: Path, variable: str, mp_progress) -> None:
    """Subprocess entry point for `write_annual_maxima_from_hourly()` -- see `_run_worker_with_watchdog()`."""
    daily_ds = compute_daily_maxima(hourly_path, variable=variable)
    annual = compute_annual_maxima(daily_ds, variable=variable)
    ds_out = annual.to_dataset(name=variable)
    ds_out = ds_out.rio.write_crs("EPSG:4326")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with _LoggingProgress("reduce", mp_progress=mp_progress):
        ds_out.to_netcdf(out_path)


def write_annual_maxima_from_hourly(hourly_path: Path, out_path: Path, variable: str = "fg10") -> None:
    """Compute daily-then-annual maxima from a raw hourly field and persist the result.

    The pipeline requested in COMMAND F4-2's dataset-switch verdict:
    hourly max per day (UTC calendar day, OQ-037), then annual max per
    year from those daily maxima — not a single-step max over all
    hours, so the daily-maximum intermediate stays an explicit,
    auditable step even though `max` is associative and would give the
    same annual result either way.

    Runs in a watchdog-supervised subprocess (COMMAND 2026-09-30, see
    `WRITE_STALL_TIMEOUT_S`) for the same reason `merge_yearly_files()`
    does.
    """
    _run_worker_with_watchdog(_reduce_worker, (hourly_path, out_path, variable), "reduce")


# ---------------------------------------------------------------------------
# Incremental (per-year, checkpointed) reduction -- COMMAND 2026-10-05
#
# merge -> crop -> reduce above materializes a ~12 GB multi-year bbox
# file and a ~16 GB cropped hourly file just to end with a ~35 KB annual
# maximum, and loses everything in the stage that fails (BRA's
# merge-final died at 24% of 3146 tasks with an HDF write error on a
# 5.9 GB-RAM machine). The annual maximum of year Y only depends on year
# Y's own file (every ERA5 yearly file spans exactly Jan 1 - Dec 31 UTC,
# so UTC days never straddle two files), so it is computed here one year
# at a time, one month in memory at a time, and checkpointed as a tiny
# per-year file. A crash/kill loses at most the year in progress.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CountryMask:
    """Whole-native-cell polygon mask on a bbox grid (same logic as `_crop_worker()`)."""

    lat_keep: np.ndarray  # bool, over the bbox file's latitude axis
    lon_keep: np.ndarray  # bool, over the bbox file's longitude axis
    sub_mask: np.ndarray  # bool (n_lat_keep, n_lon_keep): cell center inside polygon
    cells_before: int
    cells_after: int

    @property
    def fingerprint(self) -> str:
        """Identity of the crop (which rows/columns/cells), stamped on every year checkpoint.

        A checkpoint written for a different polygon (e.g. before a country became
        mainland-only) must not be reused: its grid and cells would silently survive.
        """
        h = hashlib.sha256()
        for arr in (self.lat_keep, self.lon_keep, self.sub_mask):
            h.update(np.ascontiguousarray(arr).tobytes())
            h.update(str(arr.shape).encode())
        return h.hexdigest()[:16]


def _contiguous_range(any_flags: np.ndarray) -> np.ndarray:
    """Bool array True from the first to the last True of `any_flags` (all False stays all False)."""
    keep = np.zeros_like(any_flags, dtype=bool)
    idx = np.flatnonzero(any_flags)
    if idx.size:
        keep[idx[0] : idx[-1] + 1] = True
    return keep


def build_country_mask(sample_year_path: Path, country_polygon_path: Path) -> CountryMask:
    """Compute the polygon mask once per country from any one of its yearly bbox files."""
    geom = gpd.read_file(country_polygon_path).union_all()
    with xr.open_dataset(sample_year_path) as ds:
        lat_name = "latitude" if "latitude" in ds.variables else "lat"
        lon_name = "longitude" if "longitude" in ds.variables else "lon"
        lat = np.asarray(ds[lat_name].values, dtype=float)
        lon = np.asarray(ds[lon_name].values, dtype=float)
    lon_wrapped = np.where(lon > 180, lon - 360, lon)
    lon_grid, lat_grid = np.meshgrid(lon_wrapped, lat)
    points = gpd.points_from_xy(lon_grid.ravel(), lat_grid.ravel())
    mask_flat = gpd.GeoSeries(points, crs="EPSG:4326").intersects(geom).to_numpy()
    mask = mask_flat.reshape(lat_grid.shape)
    # Contiguous bounding range, not "rows/columns with any in-polygon cell":
    # dropping interior rows (islands far from the mainland) leaves an
    # irregular axis that GDAL cannot georeference (identity transform,
    # resolution reported as 1.0). Cells outside the polygon stay NaN.
    lat_keep = _contiguous_range(mask.any(axis=1))
    lon_keep = _contiguous_range(mask.any(axis=0))
    return CountryMask(
        lat_keep=lat_keep,
        lon_keep=lon_keep,
        sub_mask=mask[np.ix_(lat_keep, lon_keep)],
        cells_before=int(lat.size * lon.size),
        cells_after=int(mask_flat.sum()),
    )


def _annual_year_worker(
    year_path: Path,
    year: int,
    mask: CountryMask,
    out_path: Path,
    variable: str,
    mp_progress,
) -> None:
    """Subprocess entry point: one year -> one tiny (lat, lon) annual-maximum file.

    Peak memory is one month of the cropped hourly field (~100 MB for
    BRA), not a year or the 20-year stack. daily max -> annual max is
    kept as the explicit two-step reduction of `write_annual_maxima_from_hourly()`.
    """
    with xr.open_dataset(year_path) as ds:
        time_name = "valid_time" if "valid_time" in ds.variables else "time"
        lat_name = "latitude" if "latitude" in ds.variables else "lat"
        lon_name = "longitude" if "longitude" in ds.variables else "lon"
        times = ds[time_name].to_index()
        years = sorted(set(times.year))
        if years != [year]:
            raise OSError(f"{year_path}: expected only year {year}, found {years}")
        da = ds[variable].isel({lat_name: mask.lat_keep, lon_name: mask.lon_keep})
        running = None
        mp_progress.value = 0
        for month in sorted(set(times.month)):
            idx = np.flatnonzero(times.month == month)
            block = da.isel({time_name: slice(int(idx[0]), int(idx[-1]) + 1)}).load()
            month_max = block.resample({time_name: "1D"}).max().max(dim=time_name).values
            running = month_max if running is None else np.fmax(running, month_max)
            mp_progress.value += 1
        lat_vals = da[lat_name].values
        lon_vals = da[lon_name].values
    annual = np.where(mask.sub_mask, running, np.nan).astype("float32")
    out = xr.Dataset(
        {variable: ((lat_name, lon_name), annual)},
        coords={lat_name: lat_vals, lon_name: lon_vals},
    ).expand_dims(year=[year])
    out.attrs["mask_fingerprint"] = mask.fingerprint
    out.to_netcdf(out_path)


def _year_checkpoint_ok(path: Path, year: int, variable: str, fingerprint: str) -> bool:
    if not path.exists():
        return False
    try:
        with xr.open_dataset(path) as ds:
            return (
                variable in ds.data_vars
                and list(ds["year"].values) == [year]
                and ds.attrs.get("mask_fingerprint") == fingerprint
            )
    except Exception:  # noqa: BLE001 -- unreadable checkpoint = redo that year
        return False


def _fmt_dur(seconds: float) -> str:
    seconds = int(max(seconds, 0))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{s:02d}s"


def write_annual_maxima_incremental(
    year_paths: list[Path],
    country_polygon_path: Path,
    out_path: Path,
    work_dir: Path,
    label: str,
    variable: str = "fg10",
) -> tuple[int, int]:
    """Per-year, checkpointed, low-RAM replacement for merge -> crop -> reduce.

    Each year is reduced in its own watchdog-supervised subprocess to
    `work_dir/<label>_<year>.nc` (atomic `.part.nc` -> rename). Years
    whose checkpoint already exists and validates are skipped, so a
    re-run resumes where it stopped. The final concat of the (tiny)
    checkpoints is atomic as well. Logs `[annual] i/N` lines with the
    mean time per year computed in this run and an ETA.

    Returns:
        (cells_before, cells_after), as `crop_to_country_polygon()`.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    sorted_paths = sorted(year_paths)
    mask = build_country_mask(sorted_paths[0], country_polygon_path)
    n = len(sorted_paths)
    checkpoints: list[Path] = []
    done_this_run: list[float] = []
    t_run = time.time()

    for i, year_path in enumerate(sorted_paths, start=1):
        year = int(year_path.stem.rsplit("_", 1)[-1])
        ckpt = work_dir / f"{label}_{year}.nc"
        checkpoints.append(ckpt)
        if _year_checkpoint_ok(ckpt, year, variable, mask.fingerprint):
            print(f"[annual-skip] {label} {year}: checkpoint intact ({i}/{n})", flush=True)
            continue
        tmp = ckpt.with_suffix(".part.nc")
        tmp.unlink(missing_ok=True)
        t0 = time.time()
        _run_worker_with_watchdog(
            _annual_year_worker, (year_path, year, mask, tmp, variable), f"annual-{label}-{year}"
        )
        ckpt.unlink(missing_ok=True)
        tmp.rename(ckpt)
        dt = time.time() - t0
        done_this_run.append(dt)
        # Years after this one that still need work (not already checkpointed).
        todo = sum(
            1
            for p in sorted_paths[i:]
            if not _year_checkpoint_ok(
                work_dir / f"{label}_{p.stem.rsplit('_', 1)[-1]}.nc",
                int(p.stem.rsplit("_", 1)[-1]),
                variable,
                mask.fingerprint,
            )
        )
        eta = (sum(done_this_run) / len(done_this_run)) * todo
        print(
            f"[annual] {label} {year}: {i}/{n} years | this year {_fmt_dur(dt)} | "
            f"run elapsed {_fmt_dur(time.time() - t_run)} | ETA {_fmt_dur(eta)} "
            f"({todo} to go)",
            flush=True,
        )

    tmp_final = out_path.with_suffix(".part.nc")
    tmp_final.unlink(missing_ok=True)
    parts = [xr.open_dataset(c) for c in checkpoints]
    try:
        combined = xr.concat(parts, dim="year").sortby("year")
        combined = combined.rio.write_crs("EPSG:4326")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        combined.to_netcdf(tmp_final)
    finally:
        for p in parts:
            p.close()
    out_path.unlink(missing_ok=True)
    tmp_final.rename(out_path)
    print(f"[annual-done] {label}: {n} years -> {out_path.name}", flush=True)
    return mask.cells_before, mask.cells_after
