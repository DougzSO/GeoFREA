"""Move the figures of `potential_maps` that are not part of the current set to `GEOFREA_DATA_DIR/archive/figures_<date>/` (COMMAND 60).

The current set of a country is, per technology, the maps named by `absolute_map_names(tech, per_cell)` plus the capacity-factor map and the
limits file. Anything else in `outputs/<ISO3>/technical_potential/figures/` (the maps of the earlier versions: MW and GWh per cell and GW and TWh
per state in classes, the old density map) is moved, never deleted, keeping its path under the archive folder.

    python scripts/archive_potential_figures.py BRA IND PRT [--dry-run]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from geofrea.core import paths as core_paths
from geofrea.core.config_loader import load_experiments, load_settings
from geofrea.technical_potential.absolute_maps import absolute_map_names

REPO_ROOT = Path(__file__).resolve().parents[1]


def current_set(technologies: tuple[str, ...], per_cell: bool) -> set[str]:
    keep: set[str] = set()
    for tech in technologies:
        keep.update(absolute_map_names(tech, per_cell).values())
        keep.add(f"capacity_factor_{tech}__ref__na__na.png")
    return keep


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("iso", nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    settings = load_settings(REPO_ROOT / "config" / "settings.yaml")
    technologies = tuple(settings.run.technologies)
    per_cell = load_experiments(REPO_ROOT / "config" / "experiments.yaml").absolute_maps.per_cell
    keep = current_set(technologies, per_cell)
    root = Path(core_paths.outputs_dir()).parent
    archive = root / "archive" / f"figures_{datetime.now(UTC):%Y%m%d}"
    moved = 0
    for iso in args.iso:
        figures = Path(core_paths.phase_dir(iso, "technical_potential", "figures"))
        for path in sorted(figures.glob("*")):
            if not path.is_file() or path.name in keep:
                continue
            target = archive / iso / "technical_potential" / "figures" / path.name
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
    sys.exit(main(sys.argv[1:]))
