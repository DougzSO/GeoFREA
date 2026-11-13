"""Check the ERA5 hourly files of `raw/era5` against the registry (COMMAND 138). Read-only.

For each entry of `raw/era5/_global/era5_registry.json` it looks for the file whose SHA-256 equals each `year_sha256` (the hourly year download) and for the
file at `reduced_path` whose SHA-256 equals `reduced_sha256` (the annual maximum the pipeline reads). The hourly files that the registry holds no hash for
(`<ISO3>_fg10_hourly.nc`, the group and patch files) are checked against the manifest of the archive, if `--archive` is given.

    python scripts/verify_era5_hourly.py                      # registry only
    python scripts/verify_era5_hourly.py --archive D:\\Douglas\\DOUTORADO\\database\\archive\\geofrea_2026-10

Exit code 0 when every hash of the registry is found, 1 otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(8 << 20):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--data-root",
        default=os.environ.get("GEOFREA_DATA_DIR"),
        help="GeoFREA_data (default: $GEOFREA_DATA_DIR)",
    )
    ap.add_argument(
        "--archive",
        default=None,
        help="folder of the archive with manifest.json (checks the hourly files the registry holds no hash for)",
    )
    args = ap.parse_args()
    if not args.data_root:
        print("give --data-root or set GEOFREA_DATA_DIR", file=sys.stderr)
        return 2
    root = Path(args.data_root)
    era5 = root / "raw" / "era5"
    registry = json.loads((era5 / "_global" / "era5_registry.json").read_text(encoding="utf-8"))[
        "entries"
    ]

    on_disk: dict[str, Path] = {}
    for p in sorted((era5 / "_global").glob("*_fg10_hourly_bbox_*.nc")):
        on_disk[sha256_of(p)] = p
    bad = 0
    checked = 0
    for key, entry in registry.items():
        for year, want in sorted(entry.get("year_sha256", {}).items()):
            checked += 1
            if want in on_disk:
                continue
            bad += 1
            print(
                f"MISSING  {key} year {year}: no file in raw/era5/_global with sha256 {want[:16]}..."
            )
        reduced = Path(entry["reduced_path"])
        checked += 1
        if not reduced.is_file() or sha256_of(reduced) != entry["reduced_sha256"]:
            bad += 1
            print(f"DIFFERS  {key} reduced product {reduced}")
    print(
        f"registry: {checked} hashes checked, {bad} not matched ({len(on_disk)} hourly year files on disk)"
    )

    if args.archive:
        archive = Path(args.archive)
        items = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))["items"]
        wanted = [e for e in items if e["audit_item"] == "L-1"]
        absent = differ = 0
        for e in wanted:
            p = root / e["relative_path"]
            if not p.is_file():
                absent += 1
                print(f"ABSENT   {e['relative_path']}")
            elif sha256_of(p) != e["sha256"]:
                differ += 1
                print(f"DIFFERS  {e['relative_path']}")
        print(f"archive manifest, item L-1: {len(wanted)} files, {absent} absent, {differ} differ")
        bad += absent + differ
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
