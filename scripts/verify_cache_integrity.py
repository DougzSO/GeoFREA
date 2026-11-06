"""Check that the cached artifacts of a country are whole, after any interruption (COMMAND 98).

usage: python scripts/verify_cache_integrity.py [IND PRT BRA] [--include-raw] [--dry-run] [--workers N]

Every artifact of the manifest and every file that carries a cache key is opened and read to the end, and the manifest's size, byte hash and
content hash are compared with the file (`geofrea.core.cache_integrity`). A file that is unreadable or whose hash differs gets its cache key
removed (never the file), so the next run computes it again; `--dry-run` only reports. Residue of an interrupted write is listed, not removed.

Countries are checked in the order given (default IND, PRT, BRA: IND first, the country of the last interruption). The report goes to
`<data>/logs/integrity/integrity_<stamp>.md` and `.json`. Exit code: 0 nothing wrong, 1 something was wrong (see the report), 2 the check could
not run. `--include-raw` also reads every file under `raw/<source>/<ISO>` (about 60 GB for the three countries: minutes per country).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

DEFAULT_COUNTRIES = ("IND", "PRT", "BRA")


def render_markdown(stamp: str, results: dict[str, dict], include_raw: bool, dry_run: bool) -> str:
    from geofrea.core.cache_integrity import INFO_STATUSES, OK

    lines = [
        f"# Cache integrity {stamp}",
        "",
        f"Raw data read: {'yes' if include_raw else 'no'}. Cache keys {'NOT touched (dry run)' if dry_run else 'invalidated for what failed'}.",
        "",
        "| country | files | ok | problems | invalidated | residue | seconds | phases to rerun |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for country, result in results.items():
        summary = result["summary"]
        counts = summary["counts"]
        total = sum(counts.values())
        lines.append(
            f"| {country} | {total} | {counts.get(OK, 0)} | {summary['problems']} | {summary['invalidated']} | "
            f"{counts.get('residue', 0)} | {result['seconds']:.0f} | {', '.join(summary['phases_to_rerun']) or '-'} |"
        )
    for country, result in results.items():
        findings = result["findings"]
        problems = [f for f in findings if f["status"] not in (OK, *INFO_STATUSES)]
        info = [f for f in findings if f["status"] in INFO_STATUSES]
        lines += ["", f"## {country}", ""]
        if not problems:
            lines.append("No unreadable file and no hash that differs from the manifest.")
        else:
            lines += [
                "| status | scope | phase | file | detail | key invalidated |",
                "|---|---|---|---|---|---|",
            ]
            lines += [
                f"| {f['status']} | {f['scope']} | {f['phase'] or '-'} | `{f['path']}` | {f['detail'] or '-'} | {'yes' if f['invalidated'] else 'no'} |"
                for f in problems
            ]
        if info:
            lines += ["", "Information (not failures):", ""]
            lines += [f"- {f['status']}: `{f['path']}` ({f['detail']})" for f in info]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "countries",
        nargs="*",
        default=list(DEFAULT_COUNTRIES),
        help="ISO3 codes, checked in this order",
    )
    parser.add_argument(
        "--include-raw", action="store_true", help="also read every file under raw/<source>/<ISO>"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="report only; do not invalidate any cache key"
    )
    parser.add_argument(
        "--workers", type=int, default=4, help="files read at the same time (default 4)"
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="GEOFREA_DATA_DIR (default: the environment, then the .env of the repository)",
    )
    args = parser.parse_args(argv)

    data_dir = args.data_dir or os.environ.get("GEOFREA_DATA_DIR")
    if not data_dir:
        from dotenv import load_dotenv

        load_dotenv(REPO / ".env", override=False)
        data_dir = os.environ.get("GEOFREA_DATA_DIR")
    if not data_dir or not Path(data_dir).is_dir():
        print(f"GEOFREA_DATA_DIR is not set or is not a directory: {data_dir!r}", file=sys.stderr)
        return 2
    data_root = Path(data_dir)

    from geofrea.core.cache_integrity import check_country, summarize, to_dicts

    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    results: dict[str, dict] = {}
    for country in args.countries:
        started = time.perf_counter()
        print(f"{country}: checking...", flush=True)
        findings = check_country(
            country,
            data_root,
            include_raw=args.include_raw,
            invalidate=not args.dry_run,
            workers=args.workers,
        )
        summary = summarize(findings)
        results[country] = {
            "findings": to_dicts(findings),
            "summary": summary,
            "seconds": time.perf_counter() - started,
        }
        print(f"{country}: {summary['counts']} ({results[country]['seconds']:.0f} s)", flush=True)

    out_dir = data_root / "logs" / "integrity"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"integrity_{stamp}.json").write_text(
        json.dumps(results, indent=1), encoding="utf-8"
    )
    report = out_dir / f"integrity_{stamp}.md"
    report.write_text(
        render_markdown(stamp, results, args.include_raw, args.dry_run), encoding="utf-8"
    )
    print(f"report: {report}")
    return 1 if any(r["summary"]["problems"] for r in results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
