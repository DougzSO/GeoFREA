"""Complete the ERA5 gust product of a country through the CDS queue, resumable (COMMANDS 59, 62b and 63).

`extend_era5_gust.py` asked for the bounding box of every missing part, year by year, with a client-side timeout; a timeout does not cancel a job
at the CDS, so retries filled the queue ("Maximum number queued requests for this dataset has been reached") and everything after a few jobs was
rejected. This script is the downloader that replaced it. What the CDS showed (COMMAND 62b):

  - a request of more than two years is refused at once for cost (`403 cost limits exceeded`), whatever its area (81 cells and 6,600 cells alike),
    so a country needs ceil(years / 2) requests however small the missing part is: the area is not worth shrinking below one box;
  - a request is "accepted" when it is sent and may be "rejected" a few seconds later because of the queue cap, so the answer is read again
    before the next one is sent, and no more than `--max-active` (2) jobs are kept queued;
  - the wait is in the queue, not in the size.

So there is one request per two years for the box that holds every missing rectangle (the plan of `extend_era5_gust.plan()`, 0.25 degree margin),
for the years after the first of the reference period (the first year is on disk from the earlier request, whole box).

Resumable. The state is `raw/era5/_global/<ISO3>_box_jobs.json` (job id, years, status, times of submission, start and finish). On start the
script reconciles it with the CDS (`reconcile`) and with the disk (`pending_chunks`) and sends only the years that have neither a live job nor a
file; a job that is still `accepted` or `running` is never sent again. Per-year files are `<ISO3>_box_fg10_hourly_bbox_<year>.nc`.

    python scripts/era5_ext_queue.py IND                         # resume (or start); the jobs stay at the CDS if the script stops
    python scripts/era5_ext_queue.py IND --cancel <job id> ...   # cancel jobs first
    python scripts/era5_ext_queue.py IND --years-per-request 2 --max-active 2 --max-hours 40

When every year is on disk: reduce each year with the same code as the original product (`era5.write_annual_maxima_incremental`), join with
the product that was there (existing values win; `extend_era5_gust.join_products`), report the continuity of the seam and register the product with
the ids, dates and times of the requests (extension report and attributes of the NetCDF).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import xarray as xr
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from geofrea.core import paths as core_paths
from geofrea.core.constants import REFERENCE_PERIOD
from geofrea.data_acquisition.acquisition_area import cds_area
from geofrea.data_acquisition.era5_registry import Era5NativeGrid, Era5Registry, sha256_file
from geofrea.data_acquisition.fetchers import era5

MARGIN_DEG = 0.25
ACTIVE = ("accepted", "running")
BAD = ("failed", "rejected", "dismissed", "deleted")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    print(f"{now()} {msg}", flush=True)


def client_reason(remote) -> str:
    """Why the CDS rejected a job (the `traceback` of its results answer)."""
    try:
        remote.get_results()
    except Exception as exc:  # noqa: BLE001
        return str(exc)
    return ""


def live_years(rect: dict, file_exists) -> set[int]:
    """Years a job of the rectangle still holds: queued, running or successful and not yet cut; a collected job holds its years only while their files exist."""
    held: set[int] = set()
    for job in rect["jobs"].values():
        if job["status"] in (*ACTIVE, "successful"):
            held.update(job["years"])
        elif job["status"] == "collected":
            held.update(y for y in job["years"] if file_exists(y))
    return held


def pending_chunks(rect: dict, years: list[int], file_exists, per_request: int) -> list[list[int]]:
    """The requests still to send: consecutive years, at most `per_request` each, with no file on disk and no live job."""
    held = live_years(rect, file_exists)
    todo = [y for y in years if not file_exists(y) and y not in held]
    out: list[list[int]] = []
    cur: list[int] = []
    for y in todo:
        if cur and (y != cur[-1] + 1 or len(cur) == per_request):
            out.append(cur)
            cur = []
        cur.append(y)
    return out + ([cur] if cur else [])


def reconcile(state: dict, get_remote) -> dict:
    """Bring the state up to what the CDS says: the status and the times of every job that is not finished.

    `get_remote(job_id)` returns an object with `status`, `started_at`, `finished_at`. A job the CDS no longer knows (the call raises) is marked
    `lost`. Returns the jobs that changed: {"successful": [(key, id)], "rejected": [(key, id)], "lost": [(key, id)]}.
    """
    changed: dict[str, list] = {"successful": [], "rejected": [], "lost": []}
    for key, rect in state["rects"].items():
        for jid, job in rect["jobs"].items():
            if job["status"] not in (*ACTIVE, "successful"):
                continue
            try:
                remote = get_remote(jid)
            except Exception:  # noqa: BLE001 -- unknown to the CDS: not reachable, not held
                job["status"] = "lost"
                changed["lost"].append((key, jid))
                continue
            job["status"] = remote.status
            job["started"] = iso_or_none(getattr(remote, "started_at", None)) or job.get("started")
            job["finished"] = iso_or_none(getattr(remote, "finished_at", None)) or job.get(
                "finished"
            )
            if remote.status == "successful":
                changed["successful"].append((key, jid))
            elif remote.status in BAD:
                changed["rejected"].append((key, jid))
    return changed


def iso_or_none(value) -> str | None:
    return value.isoformat() if value is not None else None


def request_for(years: list[int], area: list[float]) -> dict:
    req = era5._request_for_year("fg10", years[0], area)
    req["year"] = [str(y) for y in years]
    return req


def rect_file(global_dir: Path, iso: str, key: str, year: int) -> Path:
    return global_dir / f"{iso}_{key}_fg10_hourly_bbox_{year}.nc"


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


def split_years(group_file: Path, years: list[int], global_dir: Path, iso: str, key: str) -> None:
    with xr.open_dataset(group_file) as ds:
        time_name = "valid_time" if "valid_time" in ds.variables else "time"
        for y in years:
            final = rect_file(global_dir, iso, key, y)
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
            log(f"{key} year {y}: {final.name} written ({sub[time_name].size} steps)")


def first_year_from_existing(
    global_dir: Path, iso: str, key: str, first: int, sample_year: int
) -> None:
    """The first year of a rectangle, cut from the file of the whole box on disk, on the lattice of another year of the same rectangle."""
    final = rect_file(global_dir, iso, key, first)
    if final.exists():
        return
    whole = global_dir / f"{iso}_ext_fg10_hourly_bbox_{first}.nc"
    with (
        xr.open_dataset(rect_file(global_dir, iso, key, sample_year)) as ref,
        xr.open_dataset(whole) as src,
    ):
        lat_name = "latitude" if "latitude" in ref.variables else "lat"
        lon_name = "longitude" if "longitude" in ref.variables else "lon"
        sub = src.sel(
            {
                lat_name: np.round(ref[lat_name].values, 3),
                lon_name: np.round(ref[lon_name].values, 3),
            },
            method="nearest",
            tolerance=1e-3,
        )
        part = final.with_suffix(".part.nc")
        sub.load().to_netcdf(part)
    part.replace(final)
    log(f"{key} year {first}: cut from {whole.name} to the lattice of the rectangle")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("iso")
    ap.add_argument(
        "--cancel", nargs="*", default=[], help="CDS job ids to cancel before submitting"
    )
    ap.add_argument("--mode", choices=["box", "rects"], default="box")
    ap.add_argument("--years-per-request", type=int, default=2)
    ap.add_argument("--max-active", type=int, default=2)
    ap.add_argument("--max-hours", type=float, default=40.0)
    ap.add_argument("--poll-s", type=float, default=60.0)
    ap.add_argument(
        "--request-first-year",
        action="store_true",
        help="request the first year of the period too, when the file of the earlier request does not hold the whole lattice of the box (it lacks the 0.25 deg margin: 1 cell of IND at 20.75 N, 87.0 E is outside the old product)",
    )
    args = ap.parse_args()
    iso = args.iso
    load_dotenv(REPO_ROOT / ".env", override=False)
    import ecmwf.datastores as ds

    client = ds.Client(url=os.environ["CDSAPI_URL"], key=os.environ["CDSAPI_KEY"])
    ext = _load("extend_era5_gust")
    plan = ext.plan(iso)
    if plan["covered"]:
        log(f"{iso}: the product already reaches the mask")
        return 0
    global_dir = core_paths.fetched_raw("era5", "_global")
    state_path = global_dir / f"{iso}_{args.mode}_jobs.json"
    first, last = REFERENCE_PERIOD
    years = list(range(first if args.request_first_year else first + 1, last + 1))
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        state = {"cancelled": {}, "rects": {}}
        if args.mode == "box":
            parts = {"box": plan["request_box"]}
        else:
            parts = {f"r{k}": part for k, part in enumerate(sorted(plan["parts"]), start=1)}
        for key, part in parts.items():
            w, s, e, n = part
            area = cds_area((w - MARGIN_DEG, s - MARGIN_DEG, e + MARGIN_DEG, n + MARGIN_DEG))
            state["rects"][key] = {"part": [float(v) for v in part], "area": area, "jobs": {}}

    def save():
        state_path.write_text(json.dumps(state, indent=1), encoding="utf-8")

    for jid in args.cancel:
        if jid in state["cancelled"]:
            continue
        remote = client.get_remote(jid)
        before = remote.status
        if before in ACTIVE:
            remote.delete()
        state["cancelled"][jid] = {"status_before": before, "at": now()}
        log(f"cancelled {jid[:8]} (was {before})")
    save()

    def file_exists_for(key):
        return lambda y: rect_file(global_dir, iso, key, y).exists()

    deadline = time.time() + args.max_hours * 3600
    quiet_until = 0.0  # after a rejection for the queue cap the CDS is not asked again for a while
    while True:
        # 1. reconcile with the CDS, download, cut
        changed = reconcile(state, client.get_remote)
        for key, jid in changed["rejected"]:
            job = state["rects"][key]["jobs"][jid]
            job["error"] = client_reason(client.get_remote(jid))[:300]
            log(
                f"{key} job {jid[:8]} years {job['years'][0]}-{job['years'][-1]}: {job['status']}: {job['error']}"
            )
            if (
                "queued requests" in job["error"]
            ):  # the queue cap, not the request: the years go back to the pending list
                quiet_until = time.time() + 300.0
        for key, jid in changed["lost"]:
            log(
                f"{key} job {jid[:8]}: not known to the CDS any more; its years go back to the pending list"
            )
        for key, jid in changed["successful"]:
            job = state["rects"][key]["jobs"][jid]
            remote = client.get_remote(jid)
            group_file = (
                global_dir / f"{iso}_{key}_group_{job['years'][0]}-{job['years'][-1]}_{jid[:8]}.nc"
            )
            if not group_file.exists():
                stage(remote, group_file)
            split_years(group_file, job["years"], global_dir, iso, key)
            job["status"] = "collected"
            log(
                f"{key} job {jid[:8]}: submitted {job['submitted']}, started {job['started']}, finished {job['finished']}"
            )
        save()
        # 2. submit, one at a time, and look at the answer before the next (the CDS accepts first and rejects a few seconds later)
        for key, rect in state["rects"].items():
            for chunk in pending_chunks(rect, years, file_exists_for(key), args.years_per_request):
                n_active = sum(
                    j["status"] in ACTIVE
                    for r in state["rects"].values()
                    for j in r["jobs"].values()
                )
                if n_active >= args.max_active or time.time() < quiet_until:
                    break
                try:
                    remote = client.submit(era5.ERA5_DATASET, request_for(chunk, rect["area"]))
                except Exception as exc:  # noqa: BLE001
                    log(
                        f"{key}: submit of {chunk[0]}-{chunk[-1]} refused: {type(exc).__name__}: {str(exc)[:120]}"
                    )
                    if "cost" in str(exc).lower() and len(chunk) > 1:
                        args.years_per_request = max(1, len(chunk) // 2)
                        log(
                            f"{key}: at most {args.years_per_request} year(s) per request from now on"
                        )
                    quiet_until = time.time() + 30.0
                    break
                rect["jobs"][remote.request_id] = {
                    "years": chunk,
                    "status": remote.status,
                    "submitted": iso_or_none(remote.created_at) or now(),
                    "started": None,
                    "finished": None,
                }
                log(
                    f"{key}: submitted {remote.request_id[:8]} for {chunk[0]}-{chunk[-1]} ({remote.status})"
                )
                save()
                time.sleep(8)
                remote = client.get_remote(remote.request_id)
                if remote.status in BAD:
                    reason = client_reason(remote)
                    rect["jobs"][remote.request_id].update(status=remote.status, error=reason[:300])
                    log(f"{key}: {remote.request_id[:8]} {remote.status} at once: {reason[:120]}")
                    quiet_until = time.time() + 300.0
                    save()
                    break
        done = all(
            all(rect_file(global_dir, iso, k, y).exists() for y in years) for k in state["rects"]
        )
        if done:
            break
        if time.time() > deadline:
            log("time limit reached; the jobs stay queued at the CDS: run the script again")
            return 1
        time.sleep(args.poll_s)

    # reduce each rectangle, join, report
    country_dir = core_paths.fetched_raw("era5", iso)
    registry_path = global_dir / "era5_registry.json"
    registry = Era5Registry.load(registry_path)
    entry = registry.entries[f"era5/{iso}/fg10"]
    parts_ds = []
    for key in state["rects"]:
        if not args.request_first_year:
            first_year_from_existing(global_dir, iso, key, first, years[0])
        year_paths = [
            rect_file(global_dir, iso, key, y)
            for y in (years if args.request_first_year else [first, *years])
        ]
        out = country_dir / f"{iso}_fg10_annual_max_{key}.nc"
        era5.write_annual_maxima_incremental(
            year_paths=year_paths,
            country_polygon_path=Path(plan["border"]),
            out_path=out,
            work_dir=global_dir / "_annual_ckpt" / f"{iso}_{key}",
            label=f"{iso}_{key}",
        )
        parts_ds.append(out)
    # the rectangles do not overlap: one extension product
    ext_path = country_dir / f"{iso}_fg10_annual_max_ext.nc"
    with xr.open_dataset(parts_ds[0]) as first_ds:
        merged = first_ds.load()
    for p in parts_ds[1:]:
        with xr.open_dataset(p) as other:
            merged = merged.combine_first(other.load())
    merged.to_netcdf(ext_path.with_suffix(".part.nc"))
    ext_path.with_suffix(".part.nc").replace(ext_path)

    reduced = Path(entry.reduced_path)
    backup = reduced.with_name(reduced.stem + ".before_extension" + reduced.suffix)
    if not backup.exists():
        shutil.copy2(reduced, backup)
    provenance = {
        "extension": "COMMAND 62b: one request per missing rectangle, fg10 hourly, reanalysis-era5-single-levels",
        "years_requested": [years[0], years[-1]],
        "first_year": (
            "requested like the others"
            if args.request_first_year
            else f"cut from {iso}_ext_fg10_hourly_bbox_{first}.nc (CDS job bfbe48be)"
        ),
        "rectangles": {
            k: {"part": r["part"], "area_NWSE": r["area"], "jobs": r["jobs"]}
            for k, r in state["rects"].items()
        },
        "cancelled_jobs": state["cancelled"],
        "joined": now(),
    }
    seam = ext.join_products(
        backup,
        ext_path,
        reduced,
        attrs_update={"extension_provenance": json.dumps(provenance, default=str)},
    )
    grid = era5.read_native_grid(reduced)
    registry.entries[f"era5/{iso}/fg10"] = entry.model_copy(
        update={
            "source_path": str(reduced),
            "source_sha256": sha256_file(reduced),
            "reduced_path": str(reduced),
            "reduced_sha256": sha256_file(reduced),
            "native_grid": Era5NativeGrid(
                lat_resolution_deg=grid.lat_resolution_deg,
                lon_resolution_deg=grid.lon_resolution_deg,
                lat_min=grid.lat_min,
                lat_max=grid.lat_max,
                lon_min=grid.lon_min,
                lon_max=grid.lon_max,
                n_lat=grid.n_lat,
                n_lon=grid.n_lon,
            ),
        }
    )
    registry.save(registry_path)
    report = {
        "plan": plan,
        "seam": seam,
        "backup": str(backup),
        "extension": str(ext_path),
        "provenance": provenance,
    }
    (country_dir / f"{iso}_fg10_extension_report.json").write_text(
        json.dumps(report, indent=1, default=str), encoding="utf-8"
    )
    log("joined; seam report: " + json.dumps(seam))
    return 0


if __name__ == "__main__":
    sys.exit(main())
