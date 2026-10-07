"""Build `forcing.parquet` and `members.yaml` for one or more countries (J-3; M-F4-03/04/06).

    python scripts/build_forcing.py PRT [IND BRA]

Reads the global CMIP6 files from the registry, the ensemble from config/experiments.yaml (`gcm_ensemble`) and the
country's mainland polygon, and writes under outputs/<ISO3>/climate_forcing/artifacts/. Requires GEOFREA_DATA_DIR.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import geopandas as gpd
import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from geofrea.climate_forcing.forcing import country_cells, forcing_frames, write_forcing  # noqa: E402
from geofrea.climate_forcing.members import load_ensemble, members_manifest, resolve_members  # noqa: E402
from geofrea.core import paths as core_paths  # noqa: E402
from geofrea.data_acquisition.cmip6_registry import Cmip6Registry  # noqa: E402


def build(iso: str) -> None:
    t0 = time.time()
    registry = Cmip6Registry.load(core_paths.fetched_raw("cmip6", "_global") / "cmip6_registry.json")
    ensemble = load_ensemble(REPO_ROOT / "config" / "experiments.yaml")
    members = resolve_members(ensemble)
    manifest = members_manifest(members, registry)  # fails loud before any heavy work

    mainland_path = core_paths.fetched_raw("gadm", iso) / f"gadm41_{iso}_0_mainland.shp"
    cells = country_cells(gpd.read_file(mainland_path))
    out_dir = core_paths.phase_dir(iso, "climate_forcing", "artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)

    n = write_forcing(forcing_frames(cells, members, registry), out_dir / "forcing.parquet")
    manifest["country"] = iso
    manifest["n_cells"] = len(cells)
    manifest["n_rows"] = n
    (out_dir / "members.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    print(f"{iso}: {len(cells)} cells x {len(members)} members = {n} rows in {time.time() - t0:.0f}s -> {out_dir}")


if __name__ == "__main__":
    load_dotenv(REPO_ROOT / ".env", override=False)
    for code in sys.argv[1:] or ["PRT"]:
        build(code)
