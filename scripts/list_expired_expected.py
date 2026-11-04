"""List the entries of `expected` in config/deferred_checks.yaml that no longer count and can be removed.

An entry is pinned to the reference round (a run_id of the reference store) it was declared against. When the last accepted round of the country
(`reference_run: latest`) is another one, the entry is expired: it is not applied by the gate and is dead text in the file.

Usage: python scripts/list_expired_expected.py [--data-dir DIR] [--config FILE]
Exit code: 0 when nothing is expired, 1 when something can be removed.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from geofrea.core.deferred_check import DeferredCheck, load_checks, load_store


def expired_entries(config: Path, data_root: Path) -> dict[str, dict[str, str]]:
    """Per country, the expired entries: key -> the run_id they were declared against."""
    store = load_store(config, data_root)
    out: dict[str, dict[str, str]] = {}
    for iso, check in load_checks(config, data_root).items():
        expired = DeferredCheck(check, data_root / "outputs" / iso / "deferred_check.json", store).expired_expected()
        if expired:
            out[iso] = expired
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", default=os.environ.get("GEOFREA_DATA_DIR", ""))
    parser.add_argument("--config", default=str(REPO / "config" / "deferred_checks.yaml"))
    args = parser.parse_args(argv)
    if not args.data_dir:
        parser.error("--data-dir or GEOFREA_DATA_DIR is needed")
    found = expired_entries(Path(args.config), Path(args.data_dir))
    if not found:
        print("no expired entry of `expected`")
        return 0
    store = load_store(Path(args.config), Path(args.data_dir))
    for iso, entries in found.items():
        print(f"{iso}: the reference is now {store.latest(iso)}; these entries were declared against another one and can be removed:")
        for key, pin in sorted(entries.items()):
            print(f"  {key}   (declared against {pin[:12]})")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
