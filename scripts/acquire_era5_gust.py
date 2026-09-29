"""Run ERA5 gust acquisition (M-F1-05) against the real CDS.

COMMAND F4-2 (real acquisition), COMMAND F4-5 (retry/timeout policy,
OQ-038). Downloads the raw hourly `fg10` field for BRA/PRT/IND,
1995-2014 (D-F4-008), CDS-side bbox-filtered per country, then crops
each to the real GADM polygon and reduces to one annual maximum per
cell per year. Writes only under GEOFREA_DATA_DIR. No A-11 header
anywhere: CRAEI has no ERA5 of any kind (D12).

Run directly: `python scripts/acquire_era5_gust.py`
"""

from __future__ import annotations

import logging
import shutil
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from pathlib import Path

import cdsapi
import xarray as xr
from dotenv import load_dotenv

from geofrea.core import paths as core_paths
from geofrea.core.config_loader import load_countries, load_parameters
from geofrea.data_acquisition.era5_registry import (
    Era5NativeGrid,
    Era5Registry,
    Era5RegistryEntry,
    sha256_file,
)
from geofrea.data_acquisition.fetchers import era5
from geofrea.data_acquisition.fetchers.gadm import fetch_borders

REPO_ROOT = Path(__file__).resolve().parents[1]
COUNTRIES_YAML = REPO_ROOT / "config" / "countries.yaml"
PARAMETERS_JSON = REPO_ROOT / "config" / "parameters.json"

# --- Retry/timeout policy (OQ-038, closed COMMAND F4-5, 2026-09-28) ---
#
# Evidence base: docs/_audit/2026-09_cds_stability_diagnosis.md (F4-3)
# and docs/_audit/2026-09_arco_era5_validation.md (F4-4).
#
# QUEUE_TIMEOUT_S covers submit+poll only (the CDS "queued"/"running"
# states, until it reports the job done) -- NOT the download. F4-2's
# real run observed 3 min to 50+ min for this same request shape
# (docs/phases/F1_data_acquisition.md D-F1-018); F4-3's isolated,
# single, present-day probe reproduced a *successful* 51.4 min total
# (39 min 4 s queue + 12 min 9 s processing) outside any production
# code path -- the highest *confirmed-successful* combined queue+
# processing duration on record. A single shared timeout that discards
# real successes under this range is not tenable (D-F1-018's IND/1995
# false positive: a completed 542 MB download was thrown away because
# the *combined* queue+download timer had already run out). Set with
# margin over the worst *observed successful* case, not the mean:
# 90 min is ~1.75x the 51.4 min data point -- generous enough that
# today's normal variance does not trip it, while still bounding a run
# against a request that is genuinely, not just slowly, stuck.
QUEUE_TIMEOUT_S = 90 * 60

# DOWNLOAD_TIMEOUT_S covers the file-transfer phase alone, once the CDS
# has already reported the job done. Split from QUEUE_TIMEOUT_S
# specifically to fix the false-positive above: a slow queue no longer
# eats into the download's own budget, because the download does not
# start counting until the queue phase has already returned. Sized off
# the largest real file this acquisition has produced (BRA 1995,
# 568,777,194 bytes -- the largest of any country/year on disk to
# date) at the ~1.15 MB/s CDS-side transfer rate F4-3's isolated probe
# measured (6.91 MB in ~6 s): ~494 s (~8.2 min) expected, so 30 min is
# ~3.6x margin over the largest known real file at that rate.
DOWNLOAD_TIMEOUT_S = 30 * 60

# Retry policy: the observed failure mode (queue latency ranging 3 min
# to 50+ min on the same request shape, sometimes on consecutive
# requests) is consistent with CDS-side queue congestion under system
# load (F4-3 (a): the live dashboard showed thousands of queued
# requests platform-wide at check time), not a transient, quickly-
# resolved client-side error. There is no evidence a same-run retry
# resolves this kind of stall faster than just waiting once with an
# adequate timeout -- so retries buy insurance against a genuine
# one-off transient failure (a dropped connection, a real CDS restart)
# without pretending to fix congestion. Kept to one retry (two total
# attempts): at up to QUEUE_TIMEOUT_S + DOWNLOAD_TIMEOUT_S per attempt,
# a third or later attempt would let a single stubborn year consume
# hours of a 41-country-year run for no evidenced benefit.
MAX_ATTEMPTS_PER_YEAR = 2

# Fixed backoff between attempts -- not exponential. Exponential backoff
# is a response to a service recovering from a brief overload that a
# client's own request rate contributed to; a single sequential client
# (max_workers=1 throughout this script, confirmed not to be the cause
# of the observed variance per docs/_audit/2026-09_cds_stability_diagnosis.md
# (b)) making one retry is not contributing load an exponential ramp
# would need to back off from -- so "fixed vs exponential" is settled,
# fixed. The *duration* (COMMAND F4-6, revised from 60s): the confirmed
# root cause is CDS-side queue variance measured in minutes, not
# seconds -- F4-3's isolated probe alone spent 39 min 4 s in queue
# before running, and F4-2's real stalls spanned 3 min to 50+ min on
# the same request shape, sometimes on consecutive requests. A 60 s
# gap has no realistic chance of landing on a materially different
# queue state than the one that just caused the first attempt to fail;
# it is closer to an immediate resubmission than a real wait. Raised to
# 5 minutes: still small relative to the ~39-50+ min variance window
# (so a failing year does not cost anywhere near double its own
# QUEUE_TIMEOUT_S just waiting between attempts), but long enough to be
# a materially different point in time against queue dynamics that
# move over tens of minutes, not seconds -- a deliberate middle value,
# not a claim that 5 minutes reliably resolves congestion.
RETRY_BACKOFF_S = 5 * 60

# 502 Bad Gateway (observed once in F4-2, ~15:56-15:59, self-recovered):
# confirmed sufficient as-is, no additional handling here. Both cdsapi
# client implementations retry transient HTTP errors internally before
# any of this module's code sees them -- the classic `cdsapi.api.Client`
# lists `bad_gateway` explicitly in `Client.robust()`'s retriable set
# (up to `retry_max=500` attempts, `sleep_max=120s` between); the
# `LegacyClient` actually instantiated at runtime here (confirmed:
# `type(cdsapi.Client())` is `ecmwf.datastores.legacy_client.LegacyClient`,
# selected by `cdsapi.Client.__new__` from the CDSAPI_KEY format) wraps
# calls in `multiurl.robust()` instead, a different implementation of
# the same purpose. F4-2's real 502 recovering without any code change
# already empirically confirms this for both paths in production, not
# just by reading the source. This module's own QUEUE_TIMEOUT_S/
# DOWNLOAD_TIMEOUT_S still bound the total wait regardless of how many
# internal retries the client attempts underneath -- if the client's
# own retry loop is still running when our outer timeout fires, the
# thread is abandoned the same way a genuine stall would be (see
# `_run_with_timeout()` below), so no separate cap on the library's
# internal retry count is needed here.


def _study_countries() -> list[str]:
    """Same filter as acquire_cmip6_resource_channel.py::_study_countries()."""
    parameters = load_parameters(PARAMETERS_JSON)
    countries_config = load_countries(COUNTRIES_YAML)
    return [
        c
        for c in parameters.countries
        if not countries_config.get(c, {}).get("synthetic_fixture_root")
    ]


@dataclass
class _TimingCapture:
    """Same pattern as acquire_cmip6_resource_channel.py::_TimingCapture."""

    accepted_at: float | None = None
    running_at: float | None = None
    done_at: float | None = None

    def handler(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        now = time.time()
        if "accepted" in msg:
            self.accepted_at = now
        elif "running" in msg:
            self.running_at = now
        elif "successful" in msg:
            self.done_at = now

    def report(self) -> tuple[float | None, float | None]:
        queue_s = (
            self.running_at - self.accepted_at
            if self.accepted_at and self.running_at
            else None
        )
        processing_s = (
            self.done_at - self.running_at if self.running_at and self.done_at else None
        )
        return queue_s, processing_s


class _CaptureHandler(logging.Handler):
    def __init__(self, capture: _TimingCapture) -> None:
        super().__init__()
        self.capture = capture

    def emit(self, record: logging.LogRecord) -> None:
        self.capture.handler(record)


def _run_with_timeout(fn, timeout_s: float, stall_message: str):
    """Run `fn()` in its own thread with a hard wall-clock cap.

    Same "cdsapi blocks uninterruptibly, so abandon rather than join"
    pattern the original single-timeout version used
    (`pool.shutdown(wait=False)`): a thread that has not returned
    within `timeout_s` is abandoned, not killed (Python cannot kill a
    thread), so the caller must not touch anything that thread might
    still be writing to concurrently. Used here to give the poll phase
    and the download phase *independent* budgets instead of one shared
    one -- see QUEUE_TIMEOUT_S/DOWNLOAD_TIMEOUT_S above for why.
    """
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(fn)
        try:
            return future.result(timeout=timeout_s)
        except FutureTimeoutError as exc:
            raise TimeoutError(stall_message) from exc
    finally:
        pool.shutdown(wait=False)


def _submit_and_wait(client, request: dict):
    """Submit + poll only, no download.

    `client.retrieve(name, request, target=None)` is the public API's
    own poll-only phase: `LegacyClient.retrieve()` (the class actually
    instantiated at runtime, `ecmwf.datastores.legacy_client.LegacyClient`)
    calls `self.client.submit_and_wait_on_results()` and only calls
    `.download(target)` afterward if `target is not None`
    (`ecmwf.datastores.legacy_client.LegacyClient.retrieve`, read
    2026-09-28). This is the split QUEUE_TIMEOUT_S/DOWNLOAD_TIMEOUT_S
    needs; it exists because the classic `cdsapi.api.Client.retrieve()`
    has the identical `target is None` branch, so the same call shape
    works for either backend cdsapi.Client() may resolve to.
    """
    return client.retrieve(era5.ERA5_DATASET, request, None)


def _stage_downloaded_file(tmp_download: Path, tmp_path: Path, final_path: Path) -> None:
    """Move a completed download into place, unzipping if the CDS zipped it.

    Mirrors `era5.py::download_country_bbox_year()`'s own tail exactly
    (same zip-detection, same staging names, same atomic rename via
    Path.rename after a full write) -- duplicated here, not imported,
    because splitting the queue/download timeout (above) requires
    calling `client.retrieve()` in two separate phases instead of the
    single combined call `download_country_bbox_year()` makes
    internally; this task's scope is `scripts/acquire_era5_gust.py`
    only (COMMAND F4-5), so the tail logic is mirrored here rather than
    refactored out of `fetchers/era5.py`.
    """
    if not tmp_download.exists() or tmp_download.stat().st_size == 0:
        raise OSError("download produced no file or an empty file")

    if zipfile.is_zipfile(tmp_download):
        with zipfile.ZipFile(tmp_download) as zf:
            nc_members = [n for n in zf.namelist() if n.endswith(".nc")]
            if not nc_members:
                raise OSError("downloaded zip contains no .nc file")
            with zf.open(nc_members[0]) as src, open(tmp_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
        tmp_download.unlink()
    else:
        tmp_download.rename(tmp_path)

    if final_path.exists():
        final_path.unlink()
    tmp_path.rename(final_path)


def _download_year_once(client, job, year: int, bbox: list[float], out_dir: Path) -> Path:
    """One attempt: submit+poll (own timeout), then download (own timeout), then stage.

    Replaces a single call to `era5.download_country_bbox_year()` (which
    bundles submit+poll+download into one `client.retrieve(..., target=path)`
    call) so the two phases can carry independent timeouts.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    final_path = out_dir / f"{job.country}_{job.variable}_hourly_bbox_{year}.nc"
    tmp_path = out_dir / f"{job.country}_{job.variable}_hourly_bbox_{year}.part.nc"
    tmp_download = out_dir / f"{job.country}_{job.variable}_hourly_bbox_{year}.part.download"

    for stale in (tmp_path, tmp_download):
        if stale.exists():
            stale.unlink()

    request = era5._request_for_year(job.variable, year, bbox)

    result = _run_with_timeout(
        lambda: _submit_and_wait(client, request),
        QUEUE_TIMEOUT_S,
        f"stalled in CDS queue/processing: no result after {QUEUE_TIMEOUT_S}s",
    )

    if not hasattr(result, "download"):
        # Documented fallback (item 3): if a future cdsapi/datastores
        # version ever returns a plain value with no further download
        # step for this dataset, phase separation is not possible for
        # that response shape -- fail loud rather than silently
        # skipping the download.
        raise TypeError(
            f"CDS response has no .download() (got {type(result).__name__}); "
            "cannot separate queue and download phases for this response."
        )

    _run_with_timeout(
        lambda: result.download(str(tmp_download)),
        DOWNLOAD_TIMEOUT_S,
        f"stalled during download: no result after {DOWNLOAD_TIMEOUT_S}s",
    )

    _stage_downloaded_file(tmp_download, tmp_path, final_path)
    era5.validate_downloaded_netcdf(final_path)
    return final_path


def _download_year_with_retries(client, job, year: int, bbox: list[float], out_dir: Path) -> Path:
    """Up to MAX_ATTEMPTS_PER_YEAR attempts, RETRY_BACKOFF_S apart, then give up on this year."""
    last_exc: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS_PER_YEAR + 1):
        try:
            return _download_year_once(client, job, year, bbox, out_dir)
        except Exception as exc:  # noqa: BLE001 -- caller records and moves on
            last_exc = exc
            print(
                f"[retry] {job.key}/{year}: attempt {attempt}/{MAX_ATTEMPTS_PER_YEAR} "
                f"failed: {type(exc).__name__}: {exc}",
                flush=True,
            )
            if attempt < MAX_ATTEMPTS_PER_YEAR:
                time.sleep(RETRY_BACKOFF_S)
    assert last_exc is not None
    raise last_exc


def main() -> None:
    load_dotenv(REPO_ROOT / ".env", override=False)
    client = cdsapi.Client()

    global_dir = core_paths.fetched_raw("era5", "_global")
    outputs_root = core_paths.outputs_dir()
    registry_path = global_dir / "era5_registry.json"
    registry = Era5Registry.load(registry_path)

    study_countries = _study_countries()
    print(f"{len(study_countries)} countries to acquire (resume-aware).", flush=True)

    total_bytes = 0

    for country in study_countries:
        job = era5.Era5Job(country=country)
        if registry.is_complete(job.key):
            print(f"[skip] {job.key}: already registered and intact", flush=True)
            continue

        border_path = fetch_borders(outputs_root, country)
        if border_path is None:
            print(f"[skip] {job.key}: no GADM polygon available", flush=True)
            registry.entries[job.key] = Era5RegistryEntry(
                country_code=country,
                status="missing",
                missing_reason="no GADM polygon available",
            )
            registry.save(registry_path)
            continue

        bbox = era5.bbox_from_polygon(border_path)
        start_year, end_year = era5.REFERENCE_PERIOD
        expected_year_count = end_year - start_year + 1

        # Per-year idempotency (task F4-2 dataset-switch verdict, point
        # 4): an in-progress "missing" entry from a prior stalled/failed
        # run still carries whatever year_sha256 entries it completed
        # before failing -- reuse that progress rather than starting the
        # country's 20 years over.
        existing_entry = registry.entries.get(job.key)
        year_sha256: dict[str, str] = (
            dict(existing_entry.year_sha256) if existing_entry is not None else {}
        )
        # Permanent failures (COMMAND F4-6, OQ-038 follow-up): a year
        # that already exhausted MAX_ATTEMPTS_PER_YEAR retries in a
        # prior run is a terminal state, not retried automatically by a
        # later resume -- carried forward here so this run's own
        # completeness check (below) still counts it as accounted-for
        # (not silently re-attempted, not silently forgotten). A human
        # who wants to retry a specific permanently-failed (country,
        # year) does so by clearing that entry from
        # `permanently_failed_years` directly, a deliberate, directed
        # action -- not something a generic resume run should do on its
        # own.
        permanently_failed_years: dict[str, str] = (
            dict(existing_entry.permanently_failed_years) if existing_entry is not None else {}
        )

        year_paths: list[Path] = []
        for year in range(start_year, end_year + 1):
            if str(year) in permanently_failed_years:
                print(
                    f"[skip] {job.key}/{year}: permanently failed in a prior run "
                    f"({permanently_failed_years[str(year)]}) -- not retried automatically",
                    flush=True,
                )
                continue

            expected_path = global_dir / f"{country}_fg10_hourly_bbox_{year}.nc"
            recorded_hash = year_sha256.get(str(year))
            if recorded_hash and expected_path.exists() and sha256_file(expected_path) == recorded_hash:
                print(f"[skip] {job.key}/{year}: already downloaded and intact", flush=True)
                year_paths.append(expected_path)
                continue

            capture = _TimingCapture()
            cds_logger = logging.getLogger("cdsapi")
            handler = _CaptureHandler(capture)
            cds_logger.addHandler(handler)
            t0 = time.time()
            try:
                year_path = _download_year_with_retries(client, job, year, bbox, global_dir)
            except Exception as exc:  # noqa: BLE001 -- recorded permanently failed, loop continues
                queue_s, processing_s = capture.report()
                elapsed = time.time() - t0
                print(
                    f"[PERMANENT FAILURE] {job.key}/{year}: giving up after "
                    f"{MAX_ATTEMPTS_PER_YEAR} attempts: {type(exc).__name__}: {exc} "
                    f"(queue={queue_s}, processing={processing_s}, elapsed={elapsed:.1f}s)",
                    flush=True,
                )
                permanently_failed_years[str(year)] = f"{type(exc).__name__}: {exc}"
                registry.entries[job.key] = Era5RegistryEntry(
                    country_code=country,
                    status="missing",
                    missing_reason=(
                        f"{len(permanently_failed_years)} year(s) permanently failed after "
                        f"retries: {sorted(permanently_failed_years)}"
                    ),
                    year_sha256=year_sha256,
                    permanently_failed_years=permanently_failed_years,
                )
                registry.save(registry_path)
                continue
            finally:
                cds_logger.removeHandler(handler)

            elapsed = time.time() - t0
            year_size = year_path.stat().st_size
            total_bytes += year_size
            queue_s, processing_s = capture.report()
            print(
                f"[ok] {job.key}/{year}: queue={queue_s}, processing={processing_s}, "
                f"total={elapsed:.1f}s, bytes={year_size}, bbox={bbox}",
                flush=True,
            )
            year_paths.append(year_path)
            year_sha256[str(year)] = sha256_file(year_path)
            # Progress checkpoint after every single year -- this is the
            # "no action reported without being executed" protection:
            # a crash mid-country still leaves every completed year's
            # hash on disk in the registry, verifiable independently of
            # this process's own stdout.
            registry.entries[job.key] = Era5RegistryEntry(
                country_code=country,
                status="missing",
                missing_reason=f"in progress: {len(year_sha256)}/{expected_year_count} years downloaded",
                year_sha256=year_sha256,
                permanently_failed_years=permanently_failed_years,
            )
            registry.save(registry_path)

        if permanently_failed_years or len(year_sha256) < expected_year_count:
            # Correctness fix (COMMAND F4-5, extended F4-6): merge/crop/
            # reduce must never run over an incomplete year set --
            # continuing past a per-year failure (above) means
            # `year_paths` can now be short by exactly the years that
            # failed, which the old break-on-first-failure code never
            # had to guard against (a failure there always meant "stop,
            # nothing to merge"). This country's status stays "missing"
            # (never "registered") for as long as any year is
            # permanently failed -- there is no partial-country
            # "registered" state.
            print(
                f"[skip-merge] {job.key}: incomplete ({len(year_sha256)}/{expected_year_count} "
                f"years; permanently failed: {sorted(permanently_failed_years) if permanently_failed_years else 'none'}), "
                "not merging/cropping/reducing this run.",
                flush=True,
            )
            continue

        try:
            bbox_path = global_dir / f"{country}_fg10_hourly_bbox.nc"
            era5.merge_yearly_files(year_paths, bbox_path)
            # Re-validate the merged file itself, not just each year's
            # input -- a truncated to_netcdf() write from a killed/crashed
            # process would otherwise leave a right-sized-looking but
            # unreadable/incomplete file that a later `exists()`-only
            # resume check could not catch.
            era5.validate_downloaded_netcdf(bbox_path)
            print(
                f"[merge] {job.key}: {len(year_paths)} yearly files -> {bbox_path.name}",
                flush=True,
            )

            country_dir = core_paths.fetched_raw("era5", country)
            source_path = country_dir / f"{country}_fg10_hourly.nc"
            cells_before, cells_after = era5.crop_to_country_polygon(
                bbox_path=bbox_path, country_polygon_path=border_path, out_path=source_path
            )
            era5.validate_downloaded_netcdf(source_path)  # re-validate: see merge comment above
            print(f"[crop] {job.key}: {cells_before} -> {cells_after} cells", flush=True)

            grid = era5.read_native_grid(source_path)

            reduced_path = country_dir / f"{country}_fg10_annual_max.nc"
            era5.write_annual_maxima_from_hourly(source_path, reduced_path)
            with xr.open_dataset(reduced_path) as _check:  # re-validate: see merge comment above
                if "fg10" not in _check.data_vars or _check.sizes.get("year", 0) == 0:
                    raise OSError(
                        f"{reduced_path}: reduced product missing data or empty 'year' dim"
                    )
        except Exception as exc:  # noqa: BLE001 -- recorded as "missing" below
            print(f"[FAILED] {job.key}: post-download step: {type(exc).__name__}: {exc}", flush=True)
            registry.entries[job.key] = Era5RegistryEntry(
                country_code=country,
                status="missing",
                missing_reason=f"post-download: {type(exc).__name__}: {exc}",
                year_sha256=year_sha256,  # all 20 years already on disk; don't re-download on retry
            )
            registry.save(registry_path)
            continue

        start_year, end_year = era5.REFERENCE_PERIOD
        registry.entries[job.key] = Era5RegistryEntry(
            country_code=country,
            status="registered",
            bbox_path=str(bbox_path),
            source_path=str(source_path),
            source_sha256=sha256_file(source_path),
            reduced_path=str(reduced_path),
            reduced_sha256=sha256_file(reduced_path),
            reference_period_start=start_year,
            reference_period_end=end_year,
            native_grid=Era5NativeGrid(
                lat_resolution_deg=grid.lat_resolution_deg,
                lon_resolution_deg=grid.lon_resolution_deg,
                lat_min=grid.lat_min,
                lat_max=grid.lat_max,
                lon_min=grid.lon_min,
                lon_max=grid.lon_max,
                n_lat=grid.n_lat,
                n_lon=grid.n_lon,
            ),
            cells_before=cells_before,
            cells_after=cells_after,
            year_sha256=year_sha256,
        )
        registry.save(registry_path)

    registered = sum(1 for e in registry.entries.values() if e.status == "registered")
    missing = sum(1 for e in registry.entries.values() if e.status == "missing")
    print(
        f"\nDone. {registered} registered, {missing} missing. "
        f"New bbox bytes downloaded this run: {total_bytes} ({total_bytes / 1e6:.2f} MB).",
        flush=True,
    )

    # Explicit permanent-failure summary (COMMAND F4-6): read directly
    # back from the registry (not from this run's local variables) so
    # it reflects every country's accumulated state, including
    # countries whose permanent failures happened in an earlier run --
    # a directed manual resume should never require re-reading the full
    # execution log to find out which (country, year) pairs need it.
    any_permanent_failures = False
    for key, entry in sorted(registry.entries.items()):
        if entry.permanently_failed_years:
            if not any_permanent_failures:
                print("\nPermanently failed (country, year) pairs -- manual resume needed:", flush=True)
                any_permanent_failures = True
            for year, reason in sorted(entry.permanently_failed_years.items()):
                print(f"  {entry.country_code}/{year}: {reason}", flush=True)
    if not any_permanent_failures:
        print("\nNo permanently failed (country, year) pairs.", flush=True)


if __name__ == "__main__":
    main()
