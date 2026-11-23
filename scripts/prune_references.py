"""Prune the reference store: keep `latest.json` and the rounds it points to, remove the rest (COMMAND 196, V196).

    python scripts/prune_references.py            # the plan only: what would go and how much it frees; nothing is touched
    python scripts/prune_references.py --apply    # the plan, then the removal

Reads `GEOFREA_DATA_DIR` (and the store path of `config/deferred_checks.yaml`) like `scripts/publish_reference.py`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from geofrea.core.deferred_check import load_store
from geofrea.core.paths import data_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="remove what the plan lists (without it nothing is touched)")
    args = parser.parse_args(argv)
    store = load_store(REPO_ROOT / "config" / "deferred_checks.yaml", data_root())
    plan = store.prune(dry_run=True)
    gib = 1024**3
    print("keep:", ", ".join(f"{iso}:{run[:12]}" for iso, run in plan.keep_rounds))
    print(f"rounds to remove: {len(plan.remove_rounds)}")
    for path in plan.remove_rounds:
        print("  ", path.relative_to(store.root))
    print(f"objects to remove: {len(plan.remove_objects)}; objects kept: {plan.kept_bytes / gib:.3f} GiB; frees {plan.freed_bytes / gib:.3f} GiB")
    for path in plan.unknown:
        print("left alone (not a round):", path)
    if not args.apply:
        print("dry run: nothing was removed")
        return 0
    store.prune(dry_run=False)
    print("pruned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
