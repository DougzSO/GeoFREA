"""Move the figures of a country that are about to be redrawn to `GEOFREA_DATA_DIR/archive/figures_<date>/<ISO3>/` (COMMAND 68).

Every file under the `figures` folder of a phase (`climate_forcing`, `technical_potential`, `overview`, and the map phases of F6 and F7 when they exist),
with its path inside the folder, is moved, never deleted and never over an existing file. After the move the folder is empty and the phase draws its
current set into it, so a `figures` folder holds only the figures of the standard in force.

    python scripts/archive_figures.py BRA IND PRT [--dry-run] [--date YYYYMMDD]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from geofrea.core import paths as core_paths

PHASES = (
    "climate_forcing",
    "technical_potential",
    "overview",
    "lcoe_modeling",
    "robustness_analysis",
)


def files_to_move(iso: str) -> list[tuple[Path, Path]]:
    """(file, its path relative to `outputs/<ISO3>`) for every file in the figures folders of the phases of the country."""
    root = Path(core_paths.outputs_dir()) / iso
    out = []
    for phase in PHASES:
        folder = root / phase / "figures"
        if folder.is_dir():
            out += [(p, p.relative_to(root)) for p in sorted(folder.rglob("*")) if p.is_file()]
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("iso", nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--date", default=f"{datetime.now(UTC):%Y%m%d}")
    args = ap.parse_args(argv)
    archive = Path(core_paths.outputs_dir()).parent / "archive" / f"figures_{args.date}"
    moved = 0
    for iso in args.iso:
        for path, relative in files_to_move(iso):
            target = archive / iso / relative
            print(("would move " if args.dry_run else "move ") + f"{path} -> {target}")
            if not args.dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    raise SystemExit(f"{target} exists: nothing is overwritten")
                shutil.move(str(path), str(target))
            moved += 1
    print(f"{moved} file(s) {'would be ' if args.dry_run else ''}moved to {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
