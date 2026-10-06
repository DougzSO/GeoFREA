"""Run CMIP6 resource-channel acquisition (M-F1-04) against the real CDS.

COMMAND F3-2. Downloads monthly rsds/tas/sfcWind for historical + 3 SSPs,
for the approved model set (GFDL-ESM4, MIROC6 — D-F4-006), both windows
combined per experiment, then crops each global file to BRA/PRT/IND by
real GADM polygon intersection. Writes only under GEOFREA_DATA_DIR (no
staging area, per F3-1). Registers every combination in a JSON registry,
including any expected combination that could not be obtained (recorded
as "missing" with a reason, never silently absent).

Run directly: `python scripts/acquire_cmip6_resource_channel.py`
"""

from __future__ import annotations

import argparse
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import cdsapi
from dotenv import load_dotenv

from geofrea.core import paths as core_paths
from geofrea.core.config_loader import load_countries, load_parameters
from geofrea.data_acquisition.cmip6_registry import (
    Cmip6CountryCrop,
    Cmip6NativeGrid,
    Cmip6Registry,
    Cmip6RegistryEntry,
    sha256_file,
)
from geofrea.data_acquisition.fetchers import cmip6
from geofrea.data_acquisition.fetchers.gadm import fetch_borders

REPO_ROOT = Path(__file__).resolve().parents[1]
COUNTRIES_YAML = REPO_ROOT / "config" / "countries.yaml"
PARAMETERS_JSON = REPO_ROOT / "config" / "parameters.json"


def _study_countries() -> list[str]:
    """In-scope countries: parameters.json's country keys, minus any
    synthetic fixture (same filter as main.py's own default_countries)."""
    parameters = load_parameters(PARAMETERS_JSON)
    countries_config = load_countries(COUNTRIES_YAML)
    return [
        c
        for c in parameters.countries
        if not countries_config.get(c, {}).get("synthetic_fixture_root")
    ]


@dataclass
class _TimingCapture:
    """Parses cdsapi's own log lines to report queue vs. processing time,
    matching F3-1's report style (accepted -> running -> successful)."""

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


def _acquire_job(
    job,
    client,
    registry: Cmip6Registry,
    registry_path: Path,
    global_dir: Path,
    lock: threading.Lock,
    labels_by_model: dict[str, dict[str, str]],
    time_requests: bool,
) -> int:
    """Download, validate and register one job; return the bytes downloaded (0 if skipped/failed).

    Registry mutation and saves go through `lock`, so jobs can run in parallel threads.
    """
    with lock:
        complete = registry.is_complete(job.key)
        if complete:
            labels_by_model.setdefault(job.model, {})[job.key] = registry.entries[job.key].realization
    if complete:
        print(f"[skip] {job.key}: already registered and intact", flush=True)
        return 0

    # Queue/processing timing parses the shared "cdsapi" logger, so it is only
    # meaningful when one request runs at a time.
    capture = _TimingCapture()
    cds_logger = logging.getLogger("cdsapi")
    handler = _CaptureHandler(capture)
    if time_requests:
        cds_logger.addHandler(handler)
    t0 = time.time()
    try:
        path = cmip6.download_global(client, job, global_dir)
        cmip6.validate_downloaded_netcdf(path)
    except Exception as exc:  # noqa: BLE001 -- recorded as "missing" below
        queue_s, processing_s = capture.report()
        print(
            f"[FAILED] {job.key}: {type(exc).__name__}: {exc} "
            f"(queue={queue_s}, processing={processing_s}, elapsed={time.time() - t0:.1f}s)",
            flush=True,
        )
        with lock:
            registry.entries[job.key] = Cmip6RegistryEntry(
                model=job.model,
                experiment=job.experiment,
                variable=job.variable,
                status="missing",
                missing_reason=f"{type(exc).__name__}: {exc}",
            )
            registry.save(registry_path)
        return 0
    finally:
        if time_requests:
            cds_logger.removeHandler(handler)

    elapsed = time.time() - t0
    size = path.stat().st_size
    queue_s, processing_s = capture.report()
    label = cmip6.read_variant_label(path)
    grid = cmip6.read_native_grid(path)
    start_year, end_year = cmip6.YEAR_RANGES[job.experiment]
    sha = sha256_file(path)
    print(
        f"[ok] {job.key}: queue={queue_s}, processing={processing_s}, "
        f"total={elapsed:.1f}s, bytes={size}, years={start_year}-{end_year}, "
        f"realization={label}, grid={grid.n_lat}x{grid.n_lon} "
        f"({grid.lat_resolution_deg:.3f}x{grid.lon_resolution_deg:.3f} deg)",
        flush=True,
    )
    with lock:
        labels_by_model.setdefault(job.model, {})[job.key] = label
        registry.entries[job.key] = Cmip6RegistryEntry(
            model=job.model,
            experiment=job.experiment,
            variable=job.variable,
            status="registered",
            global_path=str(path),
            source_sha256=sha,
            temporal_coverage_start=start_year,
            temporal_coverage_end=end_year,
            realization=label,
            native_grid=Cmip6NativeGrid(
                lat_resolution_deg=grid.lat_resolution_deg,
                lon_resolution_deg=grid.lon_resolution_deg,
                lat_min=grid.lat_min,
                lat_max=grid.lat_max,
                lon_min=grid.lon_min,
                lon_max=grid.lon_max,
                n_lat=grid.n_lat,
                n_lon=grid.n_lon,
            ),
        )
        registry.save(registry_path)
    return size


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--models",
        default=",".join(cmip6.CMIP6_MODELS),
        help="comma-separated CDS model names (default: the S-04 minimum, cmip6.CMIP6_MODELS)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="parallel CDS requests (default 1: sequential, with queue/processing timing)",
    )
    args = parser.parse_args()
    models = tuple(m.strip() for m in args.models.split(",") if m.strip())

    load_dotenv(REPO_ROOT / ".env", override=False)

    global_dir = core_paths.fetched_raw("cmip6", "_global")
    registry_path = global_dir / "cmip6_registry.json"
    registry = Cmip6Registry.load(registry_path)

    jobs = cmip6.build_jobs(models=models)
    print(
        f"{len(jobs)} jobs to acquire for {len(models)} model(s), {args.workers} worker(s) "
        "(resume-aware).",
        flush=True,
    )

    lock = threading.Lock()
    labels_by_model: dict[str, dict[str, str]] = {}
    # One client per worker thread (requests sessions are not shared across threads).
    local = threading.local()

    def _run(job) -> int:
        if not hasattr(local, "client"):
            local.client = cdsapi.Client()
        return _acquire_job(
            job, local.client, registry, registry_path, global_dir, lock, labels_by_model,
            time_requests=args.workers == 1,
        )

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        total_bytes = sum(pool.map(_run, jobs))

    # Realization consistency, per model, across every registered job.
    for model, labels in labels_by_model.items():
        try:
            cmip6.check_realizations_consistent(labels, model)
        except cmip6.RealizationMismatchError as exc:
            print(f"[REALIZATION MISMATCH] {exc}", flush=True)
            for key in labels:
                if key in registry.entries:
                    del registry.entries[key]
            registry.entries[f"cmip6/{model}/_realization_mismatch"] = Cmip6RegistryEntry(
                model=model,
                experiment="_all",
                variable="_all",
                status="missing",
                missing_reason=str(exc),
            )
            registry.save(registry_path)

    # Per-country polygon crop, for every entry that survived realization
    # checking and is registered.
    outputs_root = core_paths.outputs_dir()
    study_countries = _study_countries()
    for key, entry in list(registry.entries.items()):
        if entry.status != "registered" or entry.country_crops:
            continue
        crops = []
        for country in study_countries:
            border_path = fetch_borders(outputs_root, country)
            if border_path is None:
                print(f"[skip crop] {key} {country}: no GADM polygon available", flush=True)
                continue
            country_dir = core_paths.fetched_raw("cmip6", country)
            out_path = country_dir / f"{entry.model}_{entry.experiment}_{entry.variable}_{country}.nc"
            cells_before, cells_after = cmip6.crop_to_country_polygon(
                global_path=entry.global_path, country_polygon_path=border_path, out_path=out_path
            )
            crops.append(
                Cmip6CountryCrop(
                    country_code=country,
                    path=str(out_path),
                    cells_before=cells_before,
                    cells_after=cells_after,
                )
            )
            print(
                f"[crop] {key} {country}: {cells_before} -> {cells_after} cells",
                flush=True,
            )
        entry.country_crops = crops
        registry.entries[key] = entry
        registry.save(registry_path)

    registered = sum(1 for e in registry.entries.values() if e.status == "registered")
    missing = sum(1 for e in registry.entries.values() if e.status == "missing")
    print(
        f"\nDone. {registered} registered, {missing} missing. "
        f"New bytes downloaded this run: {total_bytes} ({total_bytes / 1e9:.3f} GB).",
        flush=True,
    )


if __name__ == "__main__":
    main()
