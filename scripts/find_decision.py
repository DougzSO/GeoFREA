"""Print where a decision record (D-<phase>-<number>) is defined.

Read-only. A record is defined by a line that starts with its ID in the one format of
`docs/phases/*.md` (`- **D-F5-023 - Title (date).** ...` or a table row `| D-F5-023 |`).
Lines that only cite the ID are not shown. An ID with two defining lines (a record that adds
a paragraph for the same ID) shows both.

Usage: .venv/Scripts/python.exe scripts/find_decision.py D-F5-023 [D-core-042 ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PHASES = Path(__file__).resolve().parent.parent / "docs" / "phases"


def definitions(decision_id: str) -> list[tuple[Path, int, str]]:
    """Lines of `docs/phases/**/*.md` that define `decision_id`."""
    head = re.compile(rf"^\s*(?:[-*]\s+\*\*|\|\s*){re.escape(decision_id)}(?![\w-])")
    found = []
    for path in sorted(PHASES.rglob("*.md")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if head.match(line):
                found.append((path, number, line.strip()[:140]))
    return found


def main(argv: list[str]) -> int:
    """Print the definitions of every ID given; exit 1 when one has none."""
    missing = 0
    for decision_id in argv:
        rows = definitions(decision_id)
        if not rows:
            print(f"{decision_id}: no definition found")
            missing = 1
        for path, number, text in rows:
            print(f"{decision_id}: {path.relative_to(PHASES.parent.parent)}:{number}  {text}")
    return missing


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
