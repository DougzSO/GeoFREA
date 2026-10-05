"""One-off: build isimip3b_registry.json from the OQ-036 copy log.

Single-use for COMMAND OQ036-1 (2026-10-05). Reuses the sha256 already
computed during the verified copy (oq036_isimip3b_copy_log.csv) -- does
not re-hash any file. Run once; re-running is harmless (idempotent,
overwrites with the same content as long as the copy log and files are
unchanged).
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from geofrea.data_acquisition.isimip3b_registry import (
    Isimip3bRegistry,
    Isimip3bRegistryEntry,
)

COPY_LOG = Path(r"D:/Douglas/DOUTORADO/GeoFREA_data/logs/_moves/oq036_isimip3b_copy_log.csv")
REGISTRY_PATH = Path(r"D:/Douglas/DOUTORADO/GeoFREA_data/raw/isimip3b/isimip3b_registry.json")


def main() -> None:
    registry = Isimip3bRegistry()
    with open(COPY_LOG, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    mismatches = [r for r in rows if r["status"] == "MISMATCH"]
    if mismatches:
        print(f"REFUSING to register: {len(mismatches)} MISMATCH rows in the copy log")
        for r in mismatches:
            print(f"  {r['src_path']}")
        raise SystemExit(1)

    registered = 0
    for row in rows:
        if row["status"] not in ("COPIED_VERIFIED", "ALREADY_PRESENT_VERIFIED"):
            continue
        dest = Path(row["dest_path"])
        stem = dest.stem  # e.g. gfdl-esm4_historical_pr_BRA
        parts = stem.split("_")
        country_code = parts[-1]
        variable = parts[-2]
        scenario = parts[-3]
        gcm = "_".join(parts[:-3])
        entry = Isimip3bRegistryEntry(
            gcm=gcm,
            scenario=scenario,
            variable=variable,
            country_code=country_code,
            path=str(dest),
            source_sha256=row["sha256"],
            size_bytes=int(row["size_bytes"]),
            copied_from=row["src_path"],
        )
        registry.entries[entry.key] = entry
        registered += 1

    registry.save(REGISTRY_PATH)
    print(f"registered={registered} entries -> {REGISTRY_PATH}")


if __name__ == "__main__":
    main()
