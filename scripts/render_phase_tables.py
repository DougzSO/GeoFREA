"""Write the phase-name tables of the README and of the pipeline guide from `config/phases.yaml` (COMMAND 200).

    python scripts/render_phase_tables.py            # rewrite the generated blocks
    python scripts/render_phase_tables.py --check    # exit 1 when a block differs from the registry (a test runs this)

A generated block sits between `<!-- phases:begin -->` and `<!-- phases:end -->`; nothing else in the file is touched. The Name column of
the phase table of METHODOLOGY 4.2 is written by hand and checked against the registry by `tests/unit/test_phase_registry.py`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from geofrea.core.phase_registry import load_registry

TARGETS = (REPO / "README.md", REPO / "docs" / "PIPELINE_GUIDE.md")
BEGIN = "<!-- phases:begin (generated from config/phases.yaml by scripts/render_phase_tables.py; do not edit by hand) -->"
END = "<!-- phases:end -->"


def render_table() -> str:
    """The table of the registry, in execution order."""
    rows = ["| Code | Phase id | Name | Group | Orchestrated |", "|---|---|---|---|---|"]
    for e in load_registry():
        rows.append(f"| {e.code or '-'} | `{e.id}` | {e.name_en} | {e.group} | {'yes' if e.orchestrated else 'no'} |")
    return "\n".join(rows)


def render_block() -> str:
    return f"{BEGIN}\n{render_table()}\n{END}"


def apply(text: str) -> str:
    """`text` with its generated block replaced by the current one.

    Raises:
        ValueError: the markers are missing or out of order.
    """
    start = text.find("<!-- phases:begin")
    end = text.find(END)
    if start < 0 or end < start:
        raise ValueError("the phases:begin and phases:end markers are missing")
    return text[:start] + render_block() + text[end + len(END) :]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only report whether the blocks are current")
    args = parser.parse_args()
    stale = []
    for path in TARGETS:
        old = path.read_text(encoding="utf-8")
        new = apply(old)
        if new != old:
            stale.append(path.name)
            if not args.check:
                path.write_text(new, encoding="utf-8", newline="")
                print(f"rewrote {path.relative_to(REPO)}")
    if args.check and stale:
        print(f"stale: {stale}; run python scripts/render_phase_tables.py", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
