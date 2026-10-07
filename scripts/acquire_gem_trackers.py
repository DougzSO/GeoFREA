"""F5-1: pin the GEM Global Integrated Power Tracker snapshot and clip solar/wind plants per country (M-F1-06, V-06).

The GEM release is obtained by a form (no direct URL); this reuses the global xlsx CRAEI already holds.
Run: `python scripts/acquire_gem_trackers.py [path/to/gem_xlsx]`
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

from geofrea.core import paths as core_paths
from geofrea.core.config_loader import load_countries
from geofrea.data_acquisition.fetchers import gem_trackers

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path("D:/Douglas/OUTROS/CRAEI_raw_data/raw/gem/gem_global_integrated_power_tracker_{20260809}.xlsx")


def main(argv: list[str]) -> int:
    load_dotenv()
    source = Path(argv[0]) if argv else DEFAULT_SOURCE
    dest = gem_trackers.import_snapshot(source)
    print(f"pinned {dest}")
    countries = load_countries(REPO_ROOT / "config" / "countries.yaml")
    for iso, cfg in countries.items():
        if not cfg.get("gem_country_name"):
            continue  # ZZZ fixture and any country without a GEM spelling
        boundary = core_paths.fetched_raw("gadm", iso) / f"gadm41_{iso}_0_mainland.shp"
        out = gem_trackers.build_country(iso, cfg["gem_country_name"], boundary)
        print(iso, out)
    pin = gem_trackers.load_pin()
    for iso, info in pin["countries"].items():
        print(iso, info["n_features"], {k: v["n"] for k, v in info["counts"].items() if k.endswith("operating")})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
