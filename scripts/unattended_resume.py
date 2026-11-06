"""Find the unattended round that an interruption left unfinished, so that `run_unattended.ps1` run with no flags continues it (COMMAND 98).

usage: python scripts/unattended_resume.py --rounds-dir <data>/logs/unattended_rounds [--max-age-days 3]

A round is unfinished when the newest round log has no `unattended_round_<stamp>.json` beside it and no `ROUND FINISHED` line, and at least one country
started (`<ISO>: start;`). The output is one JSON line, `{"stamp", "countries", "phases", "age_days"}`, or nothing when there is no round to continue
(the newest round finished, did not start a country, or is older than `--max-age-days`: a round left that long ago is not continued silently).

The round takes up its own stamp, countries and phases again: the manifest saved before the round is kept (a partial manifest never replaces it), the
countries that finished (`<data>/outputs/<ISO>/unattended/<stamp>/done.json`) are skipped, and the rest run again, where the checkpoints and caches
take them from the point they had reached.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

_ROUND = re.compile(r"round (\S+): countries ([A-Za-z, ]+);")
_RUNNING = re.compile(r": running (\S+)\s*$", re.MULTILINE)


def find_incomplete_round(
    rounds_dir: Path, now: datetime | None = None, max_age_days: float = 3.0
) -> dict | None:
    """The newest round of `rounds_dir` that started a country, if it is unfinished and recent: `{"stamp", "countries", "phases", "age_days"}`, else None.

    A log that never reached `<ISO>: start;` (a try that stopped at the memory check, another process running, a dry run) is skipped: it must not hide the
    round that the interruption left behind.
    """
    rounds_dir = Path(rounds_dir)
    logs = sorted(
        rounds_dir.glob("unattended_round_*.log"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    for log in logs:
        text = log.read_text(encoding="utf-8", errors="replace")
        header = _ROUND.search(text)
        if header is None or ": start;" not in text:
            continue
        stamp = log.stem.removeprefix("unattended_round_")
        if (rounds_dir / f"unattended_round_{stamp}.json").exists() or "ROUND FINISHED" in text:
            return None
        age_days = (
            (now or datetime.now().astimezone()) - datetime.fromtimestamp(log.stat().st_mtime).astimezone()
        ).total_seconds() / 86400.0
        if age_days > max_age_days:
            return None
        running = _RUNNING.findall(text)
        return {
            "stamp": header.group(1),
            "countries": [c.strip().upper() for c in header.group(2).split(",") if c.strip()],
            "phases": running[0] if running else None,
            "age_days": round(age_days, 2),
        }
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--rounds-dir", type=Path, required=True)
    parser.add_argument("--max-age-days", type=float, default=3.0)
    args = parser.parse_args(argv)
    found = find_incomplete_round(args.rounds_dir, max_age_days=args.max_age_days)
    if found is not None:
        sys.stdout.write(json.dumps(found) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
