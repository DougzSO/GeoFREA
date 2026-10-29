"""The check of an unattended round (COMMAND 78): every artifact of the phases that ran, compared with the manifest saved before the round.

usage: python scripts/unattended_check.py ISO --before manifest_before.json --after manifest.json --out unattended_check.json
           [--phases p1,p2,...] [--power power_events.json] [--started ISO8601] [--aborted "reason"]

For each artifact of the listed phases (all the phases of the manifest when none are listed) the canonical content hash before and after is compared
(`content_sha256`, the hash of the manifest that ignores what a file stores about when it was written; the byte hash where an entry has no content hash):

  IDENTICO       the same hash
  DIFERENTE      another hash; `config_changed` says whether the configuration the phase reads changed between the two manifests (a change of
                 `wind_cf_integral` from `exact` to `table`, for one, is expected to move the wind numbers of F5 by less than 1e-5)
  AUSENTE_ANTES  the artifact is new
  AUSENTE_DEPOIS the artifact is not in the manifest after the round (the phase did not finish)

Each phase that ran also gets its wall time, CPU time, peak resident memory and the awake time: the wall time less the seconds the computer slept
inside the phase (Windows events exported by `scripts/profiling/export_power_events.ps1`; the manifest times are UTC, the events local time).
The file ends with `verdict`: IDENTICO when no artifact is DIFERENTE, ABORTADO when the round was stopped early, DIFERENTE otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


# the comparison itself is the one the pipeline applies in its deferred check (core/deferred_check.py, D-core-045)
from geofrea.core.deferred_check import compare_artifacts, content_of  # noqa: E402,F401


def _local(stamp: str) -> datetime:
    """A manifest timestamp (UTC, with an offset) as naive local time, the clock of the Windows event log."""
    return datetime.fromisoformat(stamp).astimezone().replace(tzinfo=None)


def phase_table(after: dict, phases: list[str], sleeps: list[tuple[datetime, datetime]]) -> list[dict]:
    rows = []
    for name in phases:
        entry = after["phases"].get(name)
        if entry is None:
            continue
        wall = entry.get("wall_s")
        slept_s = 0.0
        if entry.get("started_at") and entry.get("finished_at"):
            a, b = _local(entry["started_at"]), _local(entry["finished_at"])
            slept_s = sum(max(0.0, (min(b, e) - max(a, s)).total_seconds()) for s, e in sleeps)
        rows.append(
            {
                "phase": name,
                "status": entry.get("status"),
                "finished_at": entry.get("finished_at"),
                "wall_s": None if wall is None else round(wall, 1),
                "slept_s": round(slept_s, 1),
                "awake_s": None if wall is None else round(max(wall - slept_s, 0.0), 1),
                "cpu_s": None if entry.get("cpu_s") is None else round(entry["cpu_s"], 1),
                "peak_rss_mb": None if entry.get("peak_rss_mb") is None else round(entry["peak_rss_mb"]),
            }
        )
    return rows


def load_sleeps(path: Path | None) -> list[tuple[datetime, datetime]]:
    """Sleep intervals: each Kernel-Power 42 to the next Power-Troubleshooter 1 (the real wake time); none without the file."""
    if path is None or not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    fmt = "%Y-%m-%d %H:%M:%S"
    starts = sorted(datetime.strptime(e["t"], fmt) for e in data.get("sleep_wake", []) if e["id"] == 42)
    wakes = sorted(datetime.strptime(e["t"], fmt) for e in data.get("resume", []))
    out = []
    for a in starts:
        later = [w for w in wakes if w >= a]
        if later:
            out.append((a, later[0]))
    return out


def build_report(
    iso: str,
    before: dict,
    after: dict,
    phases: list[str] | None,
    sleeps: list[tuple[datetime, datetime]],
    started: str | None = None,
    aborted: str | None = None,
) -> dict:
    ran = [p for p in (phases or list(after["phases"])) if p in after["phases"]]
    if started:
        since = datetime.fromisoformat(started)
        if since.tzinfo is None:  # the script gives UTC without an offset
            since = since.replace(tzinfo=timezone.utc)
        ran = [p for p in ran if after["phases"][p].get("finished_at") and datetime.fromisoformat(after["phases"][p]["finished_at"]) >= since]
    artifacts = compare_artifacts(before, after, ran)
    different = {k: r for k, r in artifacts.items() if r["status"] == "DIFERENTE"}
    verdict = "ABORTADO" if aborted else ("DIFERENTE" if different else "IDENTICO")
    return {
        "country": iso,
        "verdict": verdict,
        "aborted": aborted,
        "n_artifacts": len(artifacts),
        "n_identico": sum(r["status"] == "IDENTICO" for r in artifacts.values()),
        "different": sorted(different),
        "different_with_config_change": sorted(k for k, r in different.items() if r["config_changed"]),
        "different_unexplained": sorted(k for k, r in different.items() if not r["config_changed"]),
        "absent_after": sorted(k for k, r in artifacts.items() if r["status"] == "AUSENTE_DEPOIS"),
        "new": sorted(k for k, r in artifacts.items() if r["status"] == "AUSENTE_ANTES"),
        "phases": phase_table(after, ran, sleeps),
        "artifacts": artifacts,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("iso")
    ap.add_argument("--before", type=Path, required=True)
    ap.add_argument("--after", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--phases", default="")
    ap.add_argument("--power", type=Path, default=None)
    ap.add_argument("--started", default=None, help="only the phases that finished at or after this UTC time count as having run")
    ap.add_argument("--aborted", default=None)
    args = ap.parse_args(argv)

    before = json.loads(args.before.read_text(encoding="utf-8"))
    after = json.loads(args.after.read_text(encoding="utf-8"))
    phases = [p for p in args.phases.split(",") if p] or None
    report = build_report(args.iso, before, after, phases, load_sleeps(args.power), args.started, args.aborted)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(
        f"{args.iso}: {report['verdict']} ({report['n_identico']} of {report['n_artifacts']} artifacts IDENTICO; "
        f"{len(report['different_unexplained'])} DIFERENTE without a change of configuration, {len(report['different_with_config_change'])} with one)"
    )
    return 0 if report["verdict"] == "IDENTICO" else 1


if __name__ == "__main__":
    sys.exit(main())
