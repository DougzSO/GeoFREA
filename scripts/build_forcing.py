"""Build `forcing.parquet` and `members.yaml` for one or more countries (J-3; M-F4-03/04/06).

    python scripts/build_forcing.py PRT [IND BRA]

Reads the global CMIP6 files from the registry, the ensemble from config/experiments.yaml (`gcm_ensemble`) and the
in-country pixels of the F2a grid (grid_alignment must have run), and writes under
outputs/<ISO3>/climate_forcing/artifacts/. Requires GEOFREA_DATA_DIR.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from geofrea.climate_forcing.forcing import country_cells, forcing_frames, write_forcing  # noqa: E402
from geofrea.climate_forcing.members import load_ensemble, members_manifest, resolve_members  # noqa: E402
from geofrea.core import paths as core_paths  # noqa: E402
from geofrea.data_acquisition.cmip6_registry import Cmip6Registry  # noqa: E402


def ratio_qc(parquet: Path) -> dict:
    """Per GCM, the range of the two ratio factors and the share of cell-members outside 0.5-1.5.

    A diagnostic flag for reporting (OQ-042), not a rule: nothing is excluded or changed by it.
    """
    df = pd.read_parquet(parquet, columns=["member", "delta_rsds", "delta_wind"])
    df["member"] = df["member"].astype(str)
    df = df[df["member"] != "m0"]
    df["gcm"] = df["member"].str.extract(r"^m_(.+)_ssp")[0]
    out: dict = {}
    for gcm, g in df.groupby("gcm"):
        out[gcm] = {
            col: {
                "min": float(g[col].min()),
                "max": float(g[col].max()),
                "share_outside_0p5_1p5_pct": float(100 * ((g[col] < 0.5) | (g[col] > 1.5)).mean()),
            }
            for col in ("delta_rsds", "delta_wind")
        }
    return out


def build(iso: str) -> None:
    t0 = time.time()
    registry = Cmip6Registry.load(core_paths.fetched_raw("cmip6", "_global") / "cmip6_registry.json")
    ensemble = load_ensemble(REPO_ROOT / "config" / "experiments.yaml")
    members = resolve_members(ensemble)
    manifest = members_manifest(members, registry)  # fails loud before any heavy work

    mask_path = core_paths.phase_dir(iso, "grid_alignment", "artifacts") / f"{iso}_grid_aligned.tif"
    cells = country_cells(mask_path)
    out_dir = core_paths.phase_dir(iso, "climate_forcing", "artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)

    n = write_forcing(forcing_frames(cells, members, registry, ensemble.wind_ratio_neighbourhood_cells), out_dir / "forcing.parquet")
    manifest["qc_ratio_factors"] = ratio_qc(out_dir / "forcing.parquet")
    for gcm, stats in manifest["qc_ratio_factors"].items():
        for col, v in stats.items():
            if v["share_outside_0p5_1p5_pct"] > 0:
                print(f"  WARNING {iso} {gcm} {col}: {v['share_outside_0p5_1p5_pct']:.2f}% of cell-members outside 0.5-1.5 (max {v['max']:.2f})")
    manifest["wind_ratio_neighbourhood_cells"] = ensemble.wind_ratio_neighbourhood_cells
    manifest["country"] = iso
    manifest["n_cells"] = len(cells)
    manifest["n_rows"] = n
    (out_dir / "members.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    print(f"{iso}: {len(cells)} cells x {len(members)} members = {n} rows in {time.time() - t0:.0f}s -> {out_dir}")


if __name__ == "__main__":
    load_dotenv(REPO_ROOT / ".env", override=False)
    for code in sys.argv[1:] or ["PRT"]:
        build(code)
