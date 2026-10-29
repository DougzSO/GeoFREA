"""Run a micro-benchmark under the limits of COMMAND 76: one core, low priority, 500 MB of memory, and never when the machine is short of memory.

usage: python scripts/profiling/bench_guard.py --name NAME [--cap-mb 500] [--min-free-mb 1500] [--cpu N] [--wait-min 0] -- <command...>

The benchmark must not compete with the round that is running (COMMAND 75), so the guard

1. waits (up to `--wait-min` minutes, default 0 = do not wait) until the memory available to the system is at least `--min-free-mb`, and at least
   `--kill-free-mb` + `--cap-mb` (the command may grow to its cap and must still leave the minimum free), and refuses to start otherwise (exit 3);
2. starts the command with BELOW_NORMAL priority and its CPU affinity on a single core (`--cpu`, default the last one);
3. samples every 0.25 s the resident memory of the command's process tree and the memory available to the system, and kills the command if the
   tree passes `--cap-mb` (exit 4) or the system's available memory falls below `--kill-free-mb` (default `--min-free-mb`, exit 5; a profile that is itself large starts only
   with plenty of memory free and is killed only when the system is really short);
4. appends one JSON line to `bench_log.jsonl` (next to the profiling scripts' output directory): the name, the verdict, the wall time, the peak
   memory of the tree, the lowest available system memory observed while it ran and the lowest observed at the start. These lines are the record
   of the minimum free memory demanded by the criterion of the command.

The exit code of the command is passed through when it ends by itself.
"""

# ruff: noqa: DTZ005 - local wall-clock stamps of the machine that runs the benchmark
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import psutil

REPO = Path(__file__).resolve().parents[2]
DEFAULT_LOG = REPO / "docs" / "_audit" / "profile_76_tables" / "bench_log.jsonl"
BELOW_NORMAL = 0x00004000  # CREATE flag of Windows; harmless elsewhere (ignored below)


def available_mb() -> float:
    return psutil.virtual_memory().available / 2**20


def tree_rss_mb(root: psutil.Process) -> float:
    try:
        procs = [root, *root.children(recursive=True)]
    except psutil.Error:
        return 0.0
    total = 0
    for p in procs:
        try:
            total += p.memory_info().rss
        except psutil.Error:
            continue
    return total / 2**20


def kill_tree(root: psutil.Process) -> None:
    try:
        procs = [*root.children(recursive=True), root]
    except psutil.Error:
        procs = [root]
    for p in procs:
        try:
            p.kill()
        except psutil.Error:
            pass


def run(name: str, command: list[str], cap_mb: float, min_free_mb: float, cpu: int | None, wait_min: float, log: Path, kill_free_mb: float | None = None) -> int:
    kill_free_mb = min_free_mb if kill_free_mb is None else kill_free_mb
    # the command may grow to `cap_mb`: it starts only when that growth still leaves `kill_free_mb` free, or it would kill itself at once
    start_needs = max(min_free_mb, kill_free_mb + cap_mb)
    waited = 0.0
    start_free = available_mb()
    while start_free < start_needs and waited < wait_min * 60:
        time.sleep(15)
        waited += 15
        start_free = available_mb()
    record = {"name": name, "when": datetime.now().isoformat(timespec="seconds"), "cap_mb": cap_mb, "min_free_mb": min_free_mb, "kill_free_mb": kill_free_mb, "free_at_start_mb": round(start_free)}
    if start_free < start_needs:
        record.update(verdict=f"not started: {start_free:.0f} MB available, {start_needs:.0f} needed", wait_s=waited)
        _append(log, record)
        print(json.dumps(record))
        return 3
    cpu = psutil.cpu_count(logical=True) - 1 if cpu is None else cpu
    flags = BELOW_NORMAL if sys.platform == "win32" else 0
    t0 = time.perf_counter()
    proc = subprocess.Popen(command, creationflags=flags, cwd=REPO)
    root = psutil.Process(proc.pid)
    try:
        root.cpu_affinity([cpu])
    except (psutil.Error, AttributeError):
        record["affinity"] = "not set"
    peak, low_free, verdict = 0.0, start_free, "finished"
    code = None
    while code is None:
        rss, free = tree_rss_mb(root), available_mb()
        peak, low_free = max(peak, rss), min(low_free, free)
        if rss > cap_mb:
            verdict = f"killed: {rss:.0f} MB passed the cap"
            kill_tree(root)
            code = 4
        elif free < kill_free_mb:
            verdict = f"killed: available memory fell to {free:.0f} MB"
            kill_tree(root)
            code = 5
        else:
            polled = proc.poll()
            if polled is not None:
                code = polled
            else:
                time.sleep(0.25)
    proc.wait()
    record.update(verdict=verdict, exit=code, wall_s=round(time.perf_counter() - t0, 1), peak_tree_mb=round(peak), min_free_during_mb=round(low_free))
    _append(log, record)
    print(json.dumps(record))
    return code


def _append(log: Path, record: dict) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--name", required=True)
    ap.add_argument("--cap-mb", type=float, default=500)
    ap.add_argument("--min-free-mb", type=float, default=1500)
    ap.add_argument("--kill-free-mb", type=float, default=None, help="kill the command below this much available memory (default: --min-free-mb)")
    ap.add_argument("--cpu", type=int, default=None)
    ap.add_argument("--wait-min", type=float, default=0)
    ap.add_argument("--log", type=Path, default=DEFAULT_LOG)
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        ap.error("no command after --")
    return run(args.name, command, args.cap_mb, args.min_free_mb, args.cpu, args.wait_min, args.log, args.kill_free_mb)


if __name__ == "__main__":
    raise SystemExit(main())
