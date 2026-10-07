"""Global Energy Monitor existing solar and wind plants, for F7b only (M-F1-06, V-06).

Access (checked 2026-10-07): the GEM trackers are released under CC BY 4.0 and are obtained through GEM's download
page (a form, not an API); no direct file URL is published, so this module does not download. The file is the
Global Integrated Power Tracker, sheet "Power facilities", that CRAEI already holds (snapshot of 2026-08-09, one global
xlsx with solar, wind and the other types). It is copied once (same route as OQ-036 for ISIMIP3b) and pinned by sha256
and snapshot date, so F7b is reproducible against one frozen release.

Validation only (V-06): nothing derived from these plants may reach a configuration file or any phase before F7b.
`tests/unit/test_gem_trackers.py` fails if another phase imports this module or a config file mentions the tracker.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd

from geofrea.core import paths

SHEET = "Power facilities"
TYPES = {"utility-scale solar": "solar", "wind": "wind"}
COLUMNS = {
    "GEM unit/phase ID": "gem_unit_id",
    "GEM location ID": "gem_location_id",
    "Plant / Project name": "plant_name",
    "Unit / Phase name": "unit_name",
    "Type": "type",
    "Technology": "technology",
    "Status": "status",
    "Capacity (MW)": "capacity_mw",
    "Start year": "start_year",
    "Retired year": "retired_year",
    "Location accuracy": "location_accuracy",
    "Latitude": "lat",
    "Longitude": "lon",
}
REGISTRY_NAME = "gem_snapshot.json"
LICENSE = "CC BY 4.0 (some TransitionZero-sourced records CC BY-NC 4.0; GEM page, 2026-10-07)"


class GemSnapshotError(ValueError):
    """The GEM file is missing, unreadable, or lacks a field F7b needs (A-09: fail loud)."""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_date_from_name(name: str) -> str:
    """`..._{20260809}.xlsx` -> `2026-08-09`; a name without a date cannot be pinned, so it is an error."""
    m = re.search(r"(\d{4})(\d{2})(\d{2})", name)
    if not m:
        raise GemSnapshotError(f"{name}: no YYYYMMDD snapshot date in the file name; cannot pin the version")
    return date(int(m[1]), int(m[2]), int(m[3])).isoformat()


def import_snapshot(source_xlsx: Path) -> Path:
    """Copy the global GEM xlsx to raw/gem/_global and write its pin (sha256, snapshot date, license, origin)."""
    source_xlsx = Path(source_xlsx)
    if not source_xlsx.exists():
        raise GemSnapshotError(f"GEM file not found: {source_xlsx}")
    dest_dir = paths.fetched_raw("gem", "_global")
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = source_xlsx.name.replace("{", "").replace("}", "")
    dest = dest_dir / safe_name
    if not dest.exists():
        shutil.copy2(source_xlsx, dest)
    pin = {
        "product": "Global Energy Monitor, Global Integrated Power Tracker",
        "sheet": SHEET,
        "file": dest.name,
        "snapshot_date": snapshot_date_from_name(source_xlsx.name),
        "sha256": _sha256(dest),
        "size_bytes": dest.stat().st_size,
        "license": LICENSE,
        "copied_from": str(source_xlsx),
        "access": "GEM download form (no direct URL); file reused from the CRAEI raw data",
        "use": "validation only (V-06, F7b)",
    }
    (dest_dir / REGISTRY_NAME).write_text(json.dumps(pin, indent=2), encoding="utf-8")
    return dest


def load_pin() -> dict:
    path = paths.fetched_raw("gem", "_global") / REGISTRY_NAME
    if not path.exists():
        raise GemSnapshotError(f"{path} missing: run scripts/acquire_gem_trackers.py")
    return json.loads(path.read_text(encoding="utf-8"))


def read_solar_wind(xlsx: Path) -> pd.DataFrame:
    """Solar and wind rows of the global sheet, with the F7b columns renamed; every row must have coordinates."""
    df = pd.read_excel(xlsx, sheet_name=SHEET)
    missing = [c for c in ("Country/area", *COLUMNS) if c not in df.columns]
    if missing:
        raise GemSnapshotError(f"{xlsx.name}: columns missing from '{SHEET}': {missing}")
    df = df[df["Type"].isin(TYPES)]
    out = df[["Country/area", *COLUMNS]].rename(columns=COLUMNS).copy()
    out["tech"] = out["type"].map(TYPES)
    out["capacity_mw"] = pd.to_numeric(out["capacity_mw"], errors="coerce")
    for col in ("start_year", "retired_year"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    # GEM text columns mix strings and numbers, which parquet cannot store
    for col in ("gem_unit_id", "gem_location_id", "plant_name", "unit_name", "technology", "location_accuracy"):
        out[col] = out[col].map(lambda v: None if pd.isna(v) else str(v))
    return out.reset_index(drop=True)


def clip_country(plants: pd.DataFrame, iso: str, gem_name: str, boundary: gpd.GeoDataFrame) -> pd.DataFrame:
    """Plants of the country's GEM name (config/countries.yaml `gem_country_name`) whose point lies inside `boundary` (the mainland polygon, OQ-039 for PRT)."""
    named = plants[plants["Country/area"] == gem_name].copy()
    if named[["lat", "lon"]].isna().any().any():
        raise GemSnapshotError(f"{iso}: GEM rows without coordinates")
    pts = gpd.GeoDataFrame(named, geometry=gpd.points_from_xy(named["lon"], named["lat"]), crs="EPSG:4326")
    boundary = boundary.to_crs("EPSG:4326")
    inside = pts.within(boundary.union_all())
    kept = pd.DataFrame(pts[inside].drop(columns="geometry")).drop(columns="Country/area")
    kept["country"] = iso
    return kept.reset_index(drop=True)


def counts(clipped: pd.DataFrame) -> dict:
    """Feature count and capacity (MW) per technology and status; the figure the registry carries."""
    g = clipped.groupby(["tech", "status"]).agg(n=("capacity_mw", "size"), mw=("capacity_mw", "sum"))
    return {f"{t}/{s}": {"n": int(r.n), "mw": round(float(r.mw), 1)} for (t, s), r in g.iterrows()}


def build_country(iso: str, gem_name: str, boundary_path: Path) -> Path:
    """raw/gem/<ISO3>/gem_solar_wind_<ISO3>.parquet and its counts, appended to the pin file."""
    pin = load_pin()
    xlsx = paths.fetched_raw("gem", "_global") / pin["file"]
    if _sha256(xlsx) != pin["sha256"]:
        raise GemSnapshotError(f"{xlsx} no longer matches its pinned sha256")
    clipped = clip_country(read_solar_wind(xlsx), iso, gem_name, gpd.read_file(boundary_path))
    out_dir = paths.fetched_raw("gem", iso)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"gem_solar_wind_{iso}.parquet"
    clipped.to_parquet(out, index=False)
    pin.setdefault("countries", {})[iso] = {
        "boundary": str(boundary_path),
        "n_features": len(clipped),
        "counts": counts(clipped),
    }
    (paths.fetched_raw("gem", "_global") / REGISTRY_NAME).write_text(json.dumps(pin, indent=2), encoding="utf-8")
    return out
