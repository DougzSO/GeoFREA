"""Record in a country's deferred check the phases that an unattended comparison already found IDENTICO (COMMAND 81).

usage: python scripts/seed_deferred_check.py ISO --from outputs/<ISO>/unattended_check.json --source "round 20261029_205135"

The comparison must have been made against the reference named for the country in `config/deferred_checks.yaml` (`scripts/run_unattended.ps1`
compares with `-BaselineStamp`, whose default is that reference). The phases whose artifacts were all IDENTICO are written to
`outputs/<ISO>/deferred_check.json` as settled, with the source named here; the others stay pending.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("iso")
    ap.add_argument("--from", dest="comparison", type=Path, required=True)
    ap.add_argument("--source", required=True, help="where the comparison was made, written in the record")
    args = ap.parse_args(argv)

    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
    from geofrea.core import paths as core_paths
    from geofrea.core.deferred_check import REPORT_NAME, load_checks, seed_from_comparison

    iso = args.iso.upper()
    checks = load_checks(REPO / "config" / "deferred_checks.yaml", core_paths.data_root())
    if iso not in checks:
        print(f"{iso} is not in config/deferred_checks.yaml")
        return 1
    outputs = core_paths.outputs_dir() / iso
    manifest = json.loads((outputs / "manifest.json").read_text(encoding="utf-8"))
    comparison = json.loads(args.comparison.read_text(encoding="utf-8"))
    recorded = seed_from_comparison(checks[iso], outputs / REPORT_NAME, comparison, manifest, args.source)
    print(f"{iso}: {len(recorded)} phases recorded as settled: {', '.join(recorded) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
