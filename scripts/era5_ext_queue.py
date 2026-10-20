"""Download the ERA5 gust years of `extend_era5_gust.py` through the CDS queue without losing jobs (COMMAND 59).

Why a second downloader: `extend_era5_gust.py` asked for one request per year with a client-side timeout. A timeout does not cancel the job at
the CDS, so every retry left one more job queued, and the CDS answers "Maximum number queued requests for this dataset has been reached" to
everything after a few; all the remaining years were rejected within minutes. This script

  - keeps the id of every job it submits in `raw/era5/_global/<ISO3>_ext_jobs.json`, so a restart reattaches instead of submitting again;
  - never times out a queued job: it polls (the CDS serves a job when it can) and downloads when the job is successful;
  - keeps at most `--max-active` jobs queued, and submits a request for several consecutive years at once (`--group-years`), because the wait is
    in the queue, not in the size; the multi-year file is split into the per-year files `<ISO3>_ext_fg10_hourly_bbox_<year>.nc` that
    `extend_era5_gust.py` reduces (same product, variable, area and netCDF format as the per-year request);
  - dismisses a duplicate of a job it already holds for the same year.

    python scripts/era5_ext_queue.py IND [--group-years 5] [--max-active 2] [--max-hours 40]

When every year is on disk, run `python scripts/extend_era5_gust.py IND`: it finds the files, reduces them and joins the product.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import xarray as xr
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import importlib.util

from geofrea.core import paths as core_paths
from geofrea.core.constants import REFERENCE_PERIOD
from geofrea.data_acquisition.fetchers import era5

ACTIVE = ("accepted", "running")
DONE_BAD = ("failed", "rejected", "dismissed", "deleted")


def _load_extend():
    spec = importlib.util.spec_from_file_location(
        "extend_era5_gust", REPO_ROOT / "scripts" / "extend_era5_gust.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    print(f"{now()} {msg}", flush=True)


def year_file(global_dir: Path, iso: str, year: int) -> Path:
    return global_dir / f"{iso}_ext_{era5.Era5Job(country=iso).variable}_hourly_bbox_{year}.nc"


def request_for(years: list[int], area: list[float]) -> dict:
    req = era5._request_for_year("fg10", years[0], area)
    req["year"] = [str(y) for y in years]
    return req


def split_into_years(group_file: Path, years: list[int], global_dir: Path, iso: str) -> None:
    """Write `<ISO3>_ext_fg10_hourly_bbox_<year>.nc` for each year of a downloaded multi-year file (atomic rename, validated)."""
    with xr.open_dataset(group_file) as ds:
        time_name = "valid_time" if "valid_time" in ds.variables else "time"
        for y in years:
            final = year_file(global_dir, iso, y)
            if final.exists():
                continue
            part = final.with_suffix(".part.nc")
            part.unlink(missing_ok=True)
            sub = ds.sel({time_name: slice(f"{y}-01-01", f"{y}-12-31T23:59")})
            if sub[time_name].size < 8700:
                raise OSError(
                    f"{group_file.name}: year {y} has only {sub[time_name].size} hourly steps"
                )
            sub.load().to_netcdf(part)
            era5.validate_downloaded_netcdf(part)
            part.replace(final)
            log(f"year {y}: {final.name} written ({sub[time_name].size} steps)")


def stage(remote, group_file: Path) -> None:
    tmp = group_file.with_suffix(".part.download")
    tmp.unlink(missing_ok=True)
    remote.download(str(tmp))
    if zipfile.is_zipfile(tmp):
        with zipfile.ZipFile(tmp) as zf:
            members = [n for n in zf.namelist() if n.endswith(".nc")]
            if not members:
                raise OSError("downloaded zip holds no .nc file")
            with zf.open(members[0]) as src, open(group_file, "wb") as dst:
                shutil.copyfileobj(src, dst)
        tmp.unlink()
    else:
        tmp.replace(group_file)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("iso")
    ap.add_argument("--group-years", type=int, default=5)
    ap.add_argument("--max-active", type=int, default=2)
    ap.add_argument("--max-hours", type=float, default=40.0)
    ap.add_argument("--poll-s", type=float, default=120.0)
    ap.add_argument(
        "--adopt",
        nargs="*",
        default=[],
        help="job ids already queued at the CDS for this product (year read from the request)",
    )
    args = ap.parse_args()
    iso = args.iso
    load_dotenv(REPO_ROOT / ".env", override=False)
    import ecmwf.datastores as ds

    client = ds.Client(url=os.environ["CDSAPI_URL"], key=os.environ["CDSAPI_KEY"])
    ext = _load_extend()
    plan = ext.plan(iso)
    if plan["covered"]:
        log(f"{iso}: the product already reaches the mask")
        return 0
    area = plan["cds_area"]
    global_dir = core_paths.fetched_raw("era5", "_global")
    state_path = global_dir / f"{iso}_ext_jobs.json"
    state = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.exists()
        else {"area": area, "jobs": {}}
    )
    if state.get("area") != area:
        raise SystemExit(
            "the area of the plan changed since the jobs were submitted; look at the state file before going on"
        )
    start, end = REFERENCE_PERIOD
    all_years = list(range(start, end + 1))

    def save():
        state_path.write_text(json.dumps(state, indent=1), encoding="utf-8")

    def covered_by_active() -> set[int]:
        return {y for j in state["jobs"].values() if j["status"] in ACTIVE for y in j["years"]}

    for job_id in args.adopt:
        if job_id in state["jobs"]:
            continue
        remote = client.get_remote(job_id)
        years = sorted(int(y) for y in remote.request["year"])
        if remote.request.get("area") != area:
            log(f"adopt {job_id}: other area, skipped")
            continue
        dup = set(years) & covered_by_active()
        if dup and remote.status in ACTIVE:
            log(
                f"adopt {job_id}: years {sorted(dup)} are already covered by a queued job; dismissing the duplicate"
            )
            remote.delete()
            continue
        state["jobs"][job_id] = {
            "years": years,
            "status": remote.status,
            "submitted": remote.created_at.isoformat() if remote.created_at else now(),
            "adopted": True,
        }
        log(f"adopt {job_id}: years {years}, {remote.status}")
    save()

    deadline = time.time() + args.max_hours * 3600
    group = args.group_years
    quiet_until = 0.0  # after a rejection the CDS is not asked again for a while
    while time.time() < deadline:
        # 1. refresh and collect
        for job_id, job in state["jobs"].items():
            if job["status"] not in ACTIVE:
                continue
            remote = client.get_remote(job_id)
            status = remote.status
            if status != job["status"]:
                log(f"job {job_id[:8]} years {job['years']}: {job['status']} -> {status}")
                job["status"] = status
            if status == "successful":
                group_file = (
                    global_dir
                    / f"{iso}_ext_group_{job['years'][0]}-{job['years'][-1]}_{job_id[:8]}.nc"
                )
                if not group_file.exists():
                    stage(remote, group_file)
                split_into_years(group_file, job["years"], global_dir, iso)
                job["status"] = "collected"
            elif status in DONE_BAD:
                job["error"] = str(getattr(remote, "error", "") or "")[:300]
                log(f"job {job_id[:8]}: {status} {job['error']}")
                quiet_until = time.time() + 900.0
        save()
        missing = [y for y in all_years if not year_file(global_dir, iso, y).exists()]
        if not missing:
            log("every year is on disk: run scripts/extend_era5_gust.py " + iso)
            return 0
        # 2. submit
        active = [j for j in state["jobs"].values() if j["status"] in ACTIVE]
        todo = [y for y in missing if y not in covered_by_active()]
        while todo and len(active) < args.max_active and time.time() >= quiet_until:
            chunk = [todo[0]]
            while len(chunk) < group and todo[len(chunk) :] and todo[len(chunk)] == chunk[-1] + 1:
                chunk.append(todo[len(chunk)])
            try:
                remote = client.submit(era5.ERA5_DATASET, request_for(chunk, area))
            except Exception as exc:  # noqa: BLE001 -- the queue is full or the request is too large: wait, or ask for less
                log(f"submit of {chunk} refused: {type(exc).__name__}: {str(exc)[:200]}")
                if len(chunk) > 1 and "too large" in str(exc).lower():
                    group = max(1, group // 2)
                    log(f"group size reduced to {group}")
                break
            status = remote.status
            state["jobs"][remote.request_id] = {
                "years": chunk,
                "status": status,
                "submitted": now(),
            }
            log(f"submitted {remote.request_id[:8]} for years {chunk[0]}-{chunk[-1]} ({status})")
            if status in DONE_BAD:  # rejected on arrival (queue cap): do not keep submitting
                state["jobs"][remote.request_id]["error"] = str(getattr(remote, "error", "") or "")[
                    :300
                ]
                log("rejected on arrival: " + state["jobs"][remote.request_id].get("error", ""))
                break
            active.append(state["jobs"][remote.request_id])
            todo = [y for y in todo if y not in chunk]
            save()
        save()
        time.sleep(args.poll_s)
    log(
        "time limit reached; the jobs stay queued at the CDS and the state is saved: run the script again"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
