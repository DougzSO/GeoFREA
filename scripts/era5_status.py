"""Report acquire_era5_gust.py progress and detect stalls, without tailing raw logs by hand.

Not a registry mutation -- read-only. Meant to answer "checar" in one
shot: per-country % done, which step is active (download / merge /
crop / reduce), whether the process is alive, and whether the
in-progress country's target file has stopped growing while the
process is still alive (the PageIn/thrashing failure mode from
2026-09-30, not a code bug -- see CLAUDE.md's Memory safety note).

Usage: .venv/Scripts/python.exe scripts/era5_status.py [--log PATH] [--stall-after-s N]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import time
from pathlib import Path

from dotenv import load_dotenv

from geofrea.core import paths as core_paths
from geofrea.data_acquisition.era5_registry import Era5Registry

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env", override=False)
REFERENCE_YEARS = 20  # era5.REFERENCE_PERIOD span; avoids importing cdsapi-dependent module here

STEP_RE = re.compile(r"\[(merge-start|merge|crop-start|crop|reduce-start)\]\s+era5/(\w+)/")

# Ordered pipeline stages after all years are downloaded. A "-start" tag
# marks a step in progress; the bare tag marks it done. Older logs (pre
# this script's *-start markers) only ever show the bare tag, so the
# step *after* the last bare tag seen is inferred to be the one
# actually running -- this keeps the tool useful without a restart.
STAGE_ORDER = ["merge-start", "merge", "crop-start", "crop", "reduce-start"]
STAGE_PCT = {"merge-start": 85, "merge": 88, "crop-start": 90, "crop": 93, "reduce-start": 95}
NEXT_START = {"merge": "crop-start", "crop": "reduce-start"}


def _any_python_running() -> bool:
    try:
        out = subprocess.run(
            ["tasklist"], capture_output=True, text=True, timeout=10, check=False
        ).stdout
    except (OSError, subprocess.SubprocessError):  # no tasklist, or it timed out: status unknown
        return False
    return "python.exe" in out.lower()


def _latest_log(logs_dir: Path) -> Path | None:
    logs = list(logs_dir.glob("acquire_era5_gust_*.log"))
    return max(logs, key=lambda p: p.stat().st_mtime) if logs else None


def _last_step_per_country(log_path: Path) -> dict[str, str]:
    last: dict[str, str] = {}
    with open(log_path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = STEP_RE.search(line)
            if m:
                last[m.group(2)] = m.group(1)
    return last


def _target_file_for_step(country_dir: Path, global_dir: Path, country: str, step: str) -> Path | None:
    return {
        "merge-start": global_dir / f"{country}_fg10_hourly_bbox.nc",
        "crop-start": country_dir / f"{country}_fg10_hourly.nc",
        "reduce-start": country_dir / f"{country}_fg10_annual_max.nc",
    }.get(step)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stall-after-s", type=int, default=600)
    args = parser.parse_args()

    global_dir = core_paths.fetched_raw("era5", "_global")
    registry_path = global_dir / "era5_registry.json"
    registry = Era5Registry.load(registry_path)

    log_path = _latest_log(REPO_ROOT / "logs")
    last_step = _last_step_per_country(log_path) if log_path else {}
    process_alive = _any_python_running()

    print(f"process_alive={process_alive}  log={log_path.name if log_path else 'none'}")
    print()

    for key, entry in sorted(registry.entries.items()):
        country = entry.country_code
        years_done = len(entry.year_sha256)
        n_failed = len(entry.permanently_failed_years)

        if entry.status == "registered":
            print(f"{key}: 100% -- registered")
            continue

        raw_step = last_step.get(country)
        if years_done < REFERENCE_YEARS and raw_step is None:
            pct = round(100 * years_done / REFERENCE_YEARS)
            print(f"{key}: ~{pct}% -- downloading years ({years_done}/{REFERENCE_YEARS}, {n_failed} permanently failed)")
            continue

        # Bare (non "-start") tag on an old-code log means that step
        # finished but the next one's start was never logged -- infer
        # it's the active step now.
        active_step = NEXT_START.get(raw_step, raw_step) if raw_step else "merge-start"
        step_pct = STAGE_PCT.get(active_step, 85)
        print(f"{key}: ~{step_pct}% -- post-download step: {active_step}")

        if process_alive:
            country_dir = core_paths.fetched_raw("era5", country)
            target = _target_file_for_step(country_dir, global_dir, country, active_step)
            if target and target.exists():
                mtime_age = time.time() - target.stat().st_mtime
                size = target.stat().st_size
                flag = " <-- STALLED?" if mtime_age > args.stall_after_s else ""
                print(
                    f"    {target.name}: {size / 1e9:.2f} GB, last modified {mtime_age:.0f}s ago{flag}"
                )
            elif target:
                print(f"    {target.name}: not created yet (step just starting)")
        else:
            print("    process not running -- run stopped mid-step, needs a manual restart")


if __name__ == "__main__":
    main()
