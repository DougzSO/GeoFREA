"""Run ERA5 gust acquisition (M-F1-05) against the real CDS.

COMMAND F4-2. Downloads the CDS derived daily-maximum `fg10` field for
BRA/PRT/IND, 1995-2014 (D-F4-008), CDS-side bbox-filtered per country,
then crops each to the real GADM polygon and reduces to one annual
maximum per cell per year. Writes only under GEOFREA_DATA_DIR. No A-11
header anywhere: CRAEI has no ERA5 of any kind (D12).

Run directly: `python scripts/acquire_era5_gust.py`
"""

from __future__ import annotations

import logging
import time
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

# Stall watchdog: a real run (2026-09-28) sat "accepted" on the CDS queue
# for over an hour with the underlying client.retrieve() call blocking
# uninterruptibly — no way to abort mid-poll via cdsapi's own API. Each
# (country, year) request is therefore run in its own thread with a hard
# wall-clock cap; a request that has not returned within this window is
# abandoned (recorded "missing" with a "stalled" reason, resumable on a
# later run) rather than left to block every later request indefinitely.
#
# 25 min (the original value) proved too tight for a large country: a
# real IND/1995 request finished its download (542 MB, tqdm reached
# 100%) inside the window but the combined queue+download wall time
# still exceeded 1500s, so `future.result(timeout=...)` fired anyway and
# the completed download was abandoned/discarded — a false-positive
# stall, not a real one. Widened to give a large bbox's download phase
# (observed ~11 min for IND alone, on top of queue time) real headroom.
STALL_TIMEOUT_S = 50 * 60


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

        # Per-year idempotency (task F4-2 dataset-switch verdict, point
        # 4): an in-progress "missing" entry from a prior stalled/failed
        # run still carries whatever year_sha256 entries it completed
        # before failing — reuse that progress rather than starting the
        # country's 20 years over.
        existing_entry = registry.entries.get(job.key)
        year_sha256: dict[str, str] = (
            dict(existing_entry.year_sha256) if existing_entry is not None else {}
        )

        year_paths: list[Path] = []
        failed = False
        for year in range(start_year, end_year + 1):
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
            pool = ThreadPoolExecutor(max_workers=1)
            try:
                future = pool.submit(
                    era5.download_country_bbox_year, client, job, year, bbox, global_dir
                )
                try:
                    year_path = future.result(timeout=STALL_TIMEOUT_S)
                except FutureTimeoutError as exc:
                    # The CDS call itself cannot be cancelled mid-poll
                    # (cdsapi blocks uninterruptibly): pool.shutdown(wait=
                    # False) below abandons the thread instead of joining
                    # it, so this (country, year) is recorded missing and
                    # the loop moves on immediately rather than hanging on
                    # the same stall again while waiting for the thread.
                    raise TimeoutError(
                        f"stalled: no result after {STALL_TIMEOUT_S}s in CDS queue"
                    ) from exc
                finally:
                    pool.shutdown(wait=False)
                era5.validate_downloaded_netcdf(year_path)
            except Exception as exc:  # noqa: BLE001 -- recorded as "missing" below
                queue_s, processing_s = capture.report()
                elapsed = time.time() - t0
                print(
                    f"[FAILED] {job.key}/{year}: {type(exc).__name__}: {exc} "
                    f"(queue={queue_s}, processing={processing_s}, elapsed={elapsed:.1f}s)",
                    flush=True,
                )
                registry.entries[job.key] = Era5RegistryEntry(
                    country_code=country,
                    status="missing",
                    missing_reason=f"{year}: {type(exc).__name__}: {exc}",
                    year_sha256=year_sha256,
                )
                registry.save(registry_path)
                failed = True
                break
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
            # Progress checkpoint after every single year — this is the
            # "no action reported without being executed" protection:
            # a crash mid-country still leaves every completed year's
            # hash on disk in the registry, verifiable independently of
            # this process's own stdout.
            registry.entries[job.key] = Era5RegistryEntry(
                country_code=country,
                status="missing",
                missing_reason=f"in progress: {len(year_sha256)}/{end_year - start_year + 1} years downloaded",
                year_sha256=year_sha256,
            )
            registry.save(registry_path)

        if failed:
            continue

        try:
            bbox_path = global_dir / f"{country}_fg10_hourly_bbox.nc"
            era5.merge_yearly_files(year_paths, bbox_path)
            # Re-validate the merged file itself, not just each year's
            # input — a truncated to_netcdf() write from a killed/crashed
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


if __name__ == "__main__":
    main()
