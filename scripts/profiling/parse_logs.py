"""Tabela A of COMMAND 76: every phase and every inner step of every logged run, from the logs only (no run, no data read beyond the log text).

usage: python scripts/profiling/parse_logs.py [--logs <GEOFREA_DATA_DIR>/logs] [--out <dir>]

Reads `logs/<ISO>/<run id>.log` of the three countries and writes, into `--out`:
  phases.csv  one row per phase execution: country, date, run, phase, reason, wall_s, cpu_s, cpu/wall, peak_rss_mb, cold|warm, class, revision
  steps.csv   one row per inner step (`[name] starting... / completed in Ns` and the `N/N done, elapsed Ns` passes)

The logs hold the CPU time of a phase (the orchestrator's `(CPU Cs)`), not of a step, and the peak memory only in the run summary table; a step has
its wall time only. A step is therefore classified by the ratio cpu/wall of the phase it ran in, and the row says so (`inherited`). The rules:

  class (ratio r = cpu_s / wall_s of the phase)
    negligible   the phase took less than 5 s: its ratio says nothing
    cpu          0.75 <= r <= 1.25   the process was busy the whole time
    multithread  r > 1.25            more than one core was busy
    mixed        0.33 <= r < 0.75    CPU and waiting alternate
    io_or_wait   r < 0.33 and an I/O-heavy step explains it (a raster tile pass, a clip of a large vector file, GLO-30, population)
    suspended    r < 0.33 and nothing explains it: the wall time is probably inflated by the computer's sleep or a stalled disk; use cpu_s
    unknown      no CPU time for the phase in that log and none in any other run of the same phase to borrow a ratio from
  Sleep: the intervals in which the computer slept are read from the Windows event log (`--power`: Kernel-Power 42 starts a sleep, the next
  Power-Troubleshooter 1 ends it; see `export_power_events.ps1`). An execution or step whose interval overlaps a sleep gets `slept_s` and
  `awake_s = wall_s - slept_s`; with more than 30% of its wall time asleep its class is `suspended (sleep)` and only `awake_s` counts as a cost.
  A phase whose log has no CPU time takes the median ratio of the other runs of the same country, phase and temperature (else of the same phase in
  any country); its class then ends in `*` and `class_source` says `estimated from other runs`.
  Runs before `--since` (default 2026-10-14) are left out.

  cold|warm      a step is cold when its log lines say `cache key differs ... recomputing` or it is a tile pass; warm when they say `cached`;
                 `always` when the step has no cache. A phase is cold when any of its steps is cold.
  revision       the last commit (any branch, committer date) at or before the start of the run: an approximation, a run on a dirty tree is not told apart.
"""

# ruff: noqa: DTZ007 - the logs and the Windows event log carry naive local times; they are compared with each other only
from __future__ import annotations

import argparse
import csv
import re
import statistics
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3}) (\w+) (\S+) (.*)$")
EXEC = re.compile(r"^Phase '(\w+)' \[(\w{3})\]: (executing|resuming|revalidated)\b(.*)$")
DONE = re.compile(r"^Phase '(\w+)' \[(\w{3})\] completed in ([\d.]+)s(?: \(CPU ([\d.]+)s(?:, peak RSS (\d+) MB)?\))?")
FAILED = re.compile(r"^Phase '(\w+)' \[(\w{3})\] FAILED")
STEP_START = re.compile(r"^\s*\[([\w.\-]+)\] starting\.\.\.")
STEP_DONE = re.compile(r"^\s*\[([\w.\-]+)\] completed in ([\d.]+)s")
PASS = re.compile(r"^(.+?): (\d+)/(\d+) done, elapsed (\d+)s")
RECOMPUTE = re.compile(r"^\s+([\w.\-]+): cache key differs")
CACHED = re.compile(r"^\s+([\w.\-]+): cached\.")
SUMMARY_ROW = re.compile(r"^(\w{3})\s+(\w+)\s+(\w+)\s+([\d.]+)\s+(\d+|-)\s+(\d+)\s*$")

# steps whose time is dominated by reading large files: a low cpu/wall there is explained by I/O
IO_HEAVY = ("tile audit", "class counts", "mosaic", "GLO-30", "slope", "elevation and slope", "population", "roads", "rivers", "protected", "land_cover", "lakes")


NETWORK_PHASES = ("data_acquisition",)  # fetches and checksums: waiting on the network and the disk explains a low cpu/wall


SLEEPS: list[tuple[datetime, datetime]] = []


def load_sleeps(path: Path) -> list[tuple[datetime, datetime]]:
    """Sleep intervals from the exported events: each Kernel-Power 42 to the next Power-Troubleshooter 1 (the real wake time)."""
    import json

    data = json.loads(path.read_text(encoding="utf-8-sig"))
    fmt = "%Y-%m-%d %H:%M:%S"
    starts = sorted(datetime.strptime(e["t"], fmt) for e in data["sleep_wake"] if e["id"] == 42)
    wakes = sorted(datetime.strptime(e["t"], fmt) for e in data["resume"])
    out = []
    for a in starts:
        later = [w for w in wakes if w >= a]
        if later:
            out.append((a, later[0]))
    return out


def slept(start: datetime, end: datetime) -> float:
    """Seconds of [start, end] that fall inside a sleep interval."""
    return sum(max(0.0, (min(end, b) - max(start, a)).total_seconds()) for a, b in SLEEPS)


def classify(ratio: float | None, io_explained: bool, wall_s: float | None = None) -> str:
    if wall_s is not None and wall_s < 5:
        return "negligible"
    if ratio is None:
        return "unknown"
    if ratio > 1.25:
        return "multithread"
    if ratio >= 0.75:
        return "cpu"
    if ratio >= 0.33:
        return "mixed"
    return "io_or_wait" if io_explained else "suspended"


def commits() -> list[tuple[datetime, str]]:
    out = subprocess.run(
        ["git", "-C", str(REPO), "log", "--all", "--format=%H%x09%cI"], capture_output=True, text=True, check=False
    ).stdout.splitlines()
    rows = []
    for line in out:
        sha, _, when = line.partition("\t")
        rows.append((datetime.fromisoformat(when).replace(tzinfo=None), sha[:7]))
    return sorted(rows)


def revision_at(history: list[tuple[datetime, str]], when: datetime) -> str:
    best = "?"
    for t, sha in history:
        if t <= when:
            best = sha
        else:
            break
    return best


def parse_log(path: Path, iso: str, history) -> tuple[list[dict], list[dict]]:
    phases, steps = [], []
    current: dict | None = None
    open_steps: dict[str, dict] = {}
    passes: dict[str, dict] = {}
    run_start = None
    summary: dict[str, tuple[float, int | None]] = {}
    in_summary = False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = TS.match(raw)
        if not m:
            row = SUMMARY_ROW.match(raw.strip())
            if in_summary and row and row.group(1) == iso:
                summary[row.group(2)] = (float(row.group(4)), None if row.group(5) == "-" else int(row.group(5)))
            if current is not None:
                _cache_marks(raw, current)
            continue
        when = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        text = m.group(5)
        if run_start is None:
            run_start = when
        if text.startswith("Run summary"):
            in_summary = True
        e = EXEC.match(text)
        if e and e.group(2) == iso:
            if e.group(3) == "executing":
                current = {
                    "country": iso, "date": when.strftime("%Y-%m-%d %H:%M"), "run": path.stem[:8], "phase": e.group(1),
                    "reason": _reason(e.group(4)), "start": when, "steps": [], "cold": False,
                }
                open_steps, passes = {}, {}
            continue
        d = DONE.match(text)
        if d and d.group(2) == iso and current and d.group(1) == current["phase"]:
            wall = float(d.group(3))
            cpu = float(d.group(4)) if d.group(4) else None
            current.update(wall_s=wall, cpu_s=cpu, peak_rss_mb=int(d.group(5)) if d.group(5) else None, status="success", end=when)
            _close(current, passes, phases, steps, history)
            current = None
            continue
        f = FAILED.match(text)
        if f and f.group(2) == iso and current and f.group(1) == current["phase"]:
            current.update(wall_s=(when - current["start"]).total_seconds(), cpu_s=None, peak_rss_mb=None, status="failed", end=when)
            _close(current, passes, phases, steps, history)
            current = None
            continue
        if current is None:
            continue
        s = STEP_START.match(text)
        if s:
            open_steps[s.group(1)] = {"step": s.group(1), "phase": current["phase"], "start": when, "cold": None, "logger": m.group(4)}
            continue
        s = STEP_DONE.match(text)
        if s and s.group(1) in open_steps:
            st = open_steps.pop(s.group(1))
            st["wall_s"] = float(s.group(2))
            current["steps"].append(st)
            continue
        p = PASS.match(text)
        if p:
            passes[p.group(1)] = {"step": p.group(1), "phase": current["phase"], "wall_s": float(p.group(4)), "cold": True, "logger": m.group(4), "pass": True,
                                  "start": when - timedelta(seconds=float(p.group(4))), "done": int(p.group(2)), "of": int(p.group(3))}
            continue
        _cache_marks(text, current, open_steps)
    # the run-summary table gives the peak memory of runs whose phase lines have none
    for ph in phases:
        if ph["run"] == path.stem[:8] and ph["peak_rss_mb"] is None and ph["phase"] in summary:
            ph["peak_rss_mb"] = summary[ph["phase"]][1]
    return phases, steps


def _reason(rest: str) -> str:
    rest = rest.lstrip(" —-")
    for key in ("named in rerun_phases", "stale_upstream", "no manifest entry", "failed", "code it runs changed", "configuration it reads changed", "skipped_upstream_failed"):
        if key in rest:
            return key
    return rest[:40]


def _cache_marks(text: str, current: dict, open_steps: dict | None = None) -> None:
    r = RECOMPUTE.match(text)
    c = CACHED.match(text)
    name = (r or c).group(1) if (r or c) else None
    if name is None:
        return
    if r:
        current["cold"] = True
    marks = current.setdefault("marks", {})
    marks[name] = "cold" if r else "warm"
    if open_steps:
        for key, st in open_steps.items():
            if key == name or name.startswith(key) or key.startswith(name):
                st["cold"] = bool(r)


def _close(current: dict, passes: dict, phases: list, steps: list, history) -> None:
    ratio = None if not current.get("cpu_s") or not current["wall_s"] else current["cpu_s"] / current["wall_s"]
    all_steps = current["steps"] + list(passes.values())
    if any(s.get("cold") for s in all_steps):
        current["cold"] = True
    ph_temp = "cold" if current["cold"] else ("warm" if all_steps else "always")
    io_explained = current["phase"] in NETWORK_PHASES or any(any(k in s["step"] for k in IO_HEAVY) and s["wall_s"] > 0.25 * max(current["wall_s"], 1) for s in all_steps)
    asleep = slept(current["start"], current["end"])
    current["slept_s"] = asleep
    current["awake_s"] = max(0.0, current["wall_s"] - asleep)
    current["ratio"] = ratio
    current["temperature"] = ph_temp
    current["class"] = "failed" if current["status"] == "failed" else classify(ratio, io_explained, current["wall_s"])
    if asleep > 0.3 * current["wall_s"] and current["status"] == "success":
        current["class"] = "suspended (sleep)"
    current["revision"] = revision_at(history, current["start"])
    phases.append({k: v for k, v in current.items() if k not in ("steps", "marks", "end", "start", "cold")})
    for s in all_steps:
        temp = "cold" if s.get("cold") else ("warm" if s.get("cold") is False else "always")
        step_io = any(k in s["step"] for k in IO_HEAVY)
        cls = classify(ratio, step_io or current["phase"] in NETWORK_PHASES, current["wall_s"])
        step_asleep = slept(s["start"], s["start"] + timedelta(seconds=s["wall_s"]))
        if step_asleep > 0.3 * s["wall_s"]:
            cls = "suspended (sleep)"
        steps.append({
            "country": current["country"], "date": current["date"], "run": current["run"], "phase": current["phase"], "step": s["step"],
            "wall_s": s["wall_s"], "slept_s": step_asleep, "awake_s": max(0.0, s["wall_s"] - step_asleep), "temperature": temp, "class": cls, "class_source": "inherited from phase", "phase_ratio": ratio,
            "kind": "pass" if s.get("pass") else "step", "revision": current["revision"],
        })


def estimate_missing_cpu(phases: list[dict], steps: list[dict]) -> None:
    """Give a phase without CPU time the median cpu/wall ratio of the runs of the same country, phase and temperature (else of the same phase)."""
    known = [r for r in phases if r["ratio"] is not None and r["status"] == "success"]

    def median_of(rows):
        return statistics.median(r["ratio"] for r in rows) if rows else None

    for r in phases:
        r["class_source"] = "measured"
        if r["ratio"] is not None or r["status"] != "success":
            continue
        same = [k for k in known if (k["country"], k["phase"], k["temperature"]) == (r["country"], r["phase"], r["temperature"])]
        est = median_of(same) or median_of([k for k in known if k["phase"] == r["phase"]])
        if est is not None:
            r["ratio_estimated"] = est
            r["class"] = classify(est, r["class"] == "io_or_wait" or r["phase"] in NETWORK_PHASES, r["wall_s"]) + "*"
            r["class_source"] = "estimated from other runs"
    by_run = {(r["run"], r["country"], r["phase"]): r for r in phases}
    for s in steps:
        ph = by_run.get((s["run"], s["country"], s["phase"]))
        if ph and ph["class_source"] != "measured":
            est = ph.get("ratio_estimated")
            if est is not None:
                step_io = any(k in s["step"] for k in IO_HEAVY)
                s["class"] = classify(est, step_io or s["phase"] in NETWORK_PHASES, ph["wall_s"]) + "*"
                s["class_source"] = "inherited from phase, ratio estimated from other runs"


def write(rows: list[dict], path: Path, fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.3f}" if isinstance(v, float) else v) for k, v in r.items()})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--logs", type=Path, default=Path(r"D:\Douglas\DOUTORADO\GeoFREA_data\logs"))
    ap.add_argument("--out", type=Path, default=REPO / "docs" / "_audit" / "profile_76_tables")
    ap.add_argument("--power", type=Path, default=None, help="JSON of the sleep and wake events (export_power_events.ps1)")
    ap.add_argument("--since", default="2026-10-14", help="first day of the runs kept")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.power:
        SLEEPS.extend(load_sleeps(args.power))
    history = commits()
    phases, steps = [], []
    for iso in ("PRT", "IND", "BRA"):
        for path in sorted((args.logs / iso).glob("*.log")):
            p, s = parse_log(path, iso, history)
            phases += p
            steps += s
    phases = [r for r in phases if r["date"] >= args.since]
    steps = [r for r in steps if r["date"] >= args.since]
    estimate_missing_cpu(phases, steps)
    phases.sort(key=lambda r: (r["date"], r["country"]))
    steps.sort(key=lambda r: (r["date"], r["country"]))
    write(phases, args.out / "phases.csv", ["country", "date", "run", "phase", "reason", "status", "wall_s", "slept_s", "awake_s", "cpu_s", "ratio", "peak_rss_mb", "temperature", "class", "class_source", "revision"])
    write(steps, args.out / "steps.csv", ["country", "date", "run", "phase", "step", "kind", "wall_s", "slept_s", "awake_s", "temperature", "class", "class_source", "phase_ratio", "revision"])
    print(f"{len(phases)} phase executions, {len(steps)} steps -> {args.out}")
    by = defaultdict(int)
    for r in phases:
        by[r["class"]] += 1
    print(len([r for r in phases if r["class"] == "unknown"]), "phase executions stay unknown")
    print(dict(by))
    return 0


if __name__ == "__main__":
    sys.exit(main())
