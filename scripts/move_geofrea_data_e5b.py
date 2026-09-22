"""COMMAND E5b Part B: move GeoFREA repo-local data to the approved external layout.

Single-use migration script. Default mode is --dry-run (no filesystem changes,
report only). Real execution requires --execute.

Procedure (per E5b command, action 2 of the mover spec):
  1. Verify source (repo outputs/) and destination (GEOFREA_DATA_DIR) are on the
     same volume. If not, stop — no copy fallback.
  2. Snapshot every source file (path, sha256, size, mtime) to
     logs/_moves/e5b_pre.csv before any action (including in dry-run).
  3. Classify every file under outputs/ and outputs_baseline_fc7b43d/ into a
     destination, an approved deletion, or "unclassified" (stop-and-report,
     never guessed).
  4. Moves use os.replace() (same-volume rename, not copy+delete). After each
     move, sha256 is recomputed at the destination; any mismatch stops the
     script immediately.
  5. Deletions are restricted to the exact approved list; nothing else is ever
     deleted. Empty source directories are removed only when empty.
  6. GEOFREA_SHARED_RAW_DIR is never read from or written to for moves — only
     used for the before/after snapshot, which happens in dry-run too.
  7. Every action (move or delete) is logged to logs/_moves/e5b_move_log.csv.

Usage:
  python scripts/move_geofrea_data_e5b.py --dry-run   (default)
  python scripts/move_geofrea_data_e5b.py --execute
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Approved deletion list (E5b action 9) — nothing else is ever deleted.
APPROVED_DELETIONS = [
    REPO_ROOT / "outputs" / "BRA" / "processed_backup_preP6",
    REPO_ROOT / "outputs" / "PRT" / "processed_backup_preP6",
    REPO_ROOT / "outputs" / "PRT" / "manifest.baseline.json",
    REPO_ROOT / "main_run.log",
    REPO_ROOT / "recompute_run.log",
]

# Top-level stray files under outputs/<ISO3>/ — classified per Douglas's
# 2026-09-21 decision on the 26 files found by the first dry-run.
_PID_PATTERN = re.compile(r"^run(_\w+)?\.pid$")
_RUN_LOG_PATTERN = re.compile(r"^run_.*\.log$")  # also matches run_*.err.log
_LEGACY_MANIFEST_PATTERN = re.compile(r"^manifest\.json\.(bak|broken|stale|pre)_.*$")

# raw/ file -> source classification, by filename pattern.
_RAW_SOURCE_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^gadm41_.*"), "gadm"),
    (re.compile(r"^HydroRIVERS_.*"), "hydrosheds"),
    (re.compile(r"^HydroLAKES_.*"), "hydrosheds"),
    (re.compile(r".*_protected_areas_wdpa\.geojson$"), "wdpa"),
    (re.compile(r".*_wind_speed_100m\.tif$"), "gwa"),
    (re.compile(r"^global_power_plant_database\.csv$"), "wri_gppd"),
]

# processed/ file -> interim layer name, by filename pattern (strip country
# prefix / _clipped / _native suffix).
_PROCESSED_LAYER_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^lakes_clipped\.gpkg$"), "lakes"),
    (re.compile(r"^rivers_clipped\.gpkg$"), "rivers"),
    (re.compile(r"^roads_clipped\.gpkg$"), "roads"),
    (re.compile(r"^protected_clipped\.gpkg$"), "protected"),
    (re.compile(r"^[A-Z]{3}_slope_native\.tif$"), "slope"),
]

# Phase directories under outputs/<ISO3>/ that map straight to
# outputs/<ISO3>/<phase>/<kind>/ (kind = the dir's own name unless noted).
_PHASE_DIR_MAP = {
    "audit": ("data_quality_audit", "reports"),
    "grid_alignment": ("grid_alignment", "artifacts"),
    "suitability_criteria": ("suitability_criteria", None),  # keeps figures/reports/tif subdirs
    "artifacts": ("_artifacts", "artifacts"),  # phase-agnostic artifact registry files
}


@dataclass
class PlannedAction:
    kind: str  # "move" | "delete" | "unclassified"
    source: Path
    destination: Path | None = None
    size: int = 0
    sha256_before: str = ""


@dataclass
class DryRunReport:
    moves: list[PlannedAction] = field(default_factory=list)
    deletions: list[PlannedAction] = field(default_factory=list)
    unclassified: list[PlannedAction] = field(default_factory=list)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def same_volume(a: Path, b: Path) -> bool:
    return os.path.splitdrive(str(a))[0].upper() == os.path.splitdrive(str(b))[0].upper()


def snapshot_dir(root: Path, out_csv: Path, label: str) -> int:
    """Snapshot path/size/mtime/sha256 for every file under root. Returns file count."""
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["path", "size", "mtime", "sha256"])
        if root.exists():
            for p in sorted(root.rglob("*")):
                if p.is_file():
                    st = p.stat()
                    writer.writerow([str(p), st.st_size, st.st_mtime, sha256_of(p)])
                    count += 1
    print(f"[{label}] snapshot: {count} files -> {out_csv}")
    return count


def _classify_raw_file(rel_within_raw: Path, iso3_or_global: str) -> tuple[str, Path] | None:
    """Return (source_name, dest_relpath) for a file under outputs/<X>/raw/, or None."""
    top_name = rel_within_raw.parts[0]
    for pattern, source in _RAW_SOURCE_RULES:
        if pattern.match(top_name):
            dest = Path("raw") / source / iso3_or_global / rel_within_raw
            return source, dest
    return None


def _classify_processed_file(filename: str, iso3: str) -> Path | None:
    for pattern, layer in _PROCESSED_LAYER_RULES:
        if pattern.match(filename):
            return Path("interim") / iso3 / layer / filename
    return None


def build_plan(data_dir: Path) -> DryRunReport:
    report = DryRunReport()
    outputs_dir = REPO_ROOT / "outputs"

    # --- approved deletions ---
    for target in APPROVED_DELETIONS:
        if target.exists():
            if target.is_dir():
                size = sum(f.stat().st_size for f in target.rglob("*") if f.is_file())
            else:
                size = target.stat().st_size
            report.deletions.append(PlannedAction(kind="delete", source=target, size=size))

    # --- outputs_baseline_fc7b43d -> reference/legacy_baseline_fc7b43d/ ---
    legacy_src = REPO_ROOT / "outputs_baseline_fc7b43d"
    if legacy_src.exists():
        for f in sorted(legacy_src.rglob("*")):
            if f.is_file():
                rel = f.relative_to(legacy_src)
                dest = data_dir / "reference" / "legacy_baseline_fc7b43d" / rel
                report.moves.append(
                    PlannedAction(kind="move", source=f, destination=dest, size=f.stat().st_size)
                )

    # --- outputs/<ISO3>/... and outputs/_global/raw ---
    for iso_dir in sorted(outputs_dir.iterdir()):
        if not iso_dir.is_dir():
            continue
        iso3 = iso_dir.name  # "BRA", "PRT", "_global"

        for entry in sorted(iso_dir.iterdir()):
            name = entry.name

            # top-level files directly under outputs/<ISO3>/ (manifest.json, or unclassified extras)
            if entry.is_file():
                if entry in APPROVED_DELETIONS:
                    continue  # already captured in report.deletions
                if name == "manifest.json":
                    dest = data_dir / "outputs" / iso3 / "manifest.json"
                    report.moves.append(
                        PlannedAction(kind="move", source=entry, destination=dest, size=entry.stat().st_size)
                    )
                    continue
                if _PID_PATTERN.match(name):
                    report.deletions.append(
                        PlannedAction(kind="delete", source=entry, size=entry.stat().st_size)
                    )
                    continue
                if _RUN_LOG_PATTERN.match(name):
                    dest = data_dir / "logs" / iso3 / "legacy_runs" / name
                    report.moves.append(
                        PlannedAction(kind="move", source=entry, destination=dest, size=entry.stat().st_size)
                    )
                    continue
                if _LEGACY_MANIFEST_PATTERN.match(name):
                    dest = data_dir / "logs" / iso3 / "legacy_manifests" / name
                    report.moves.append(
                        PlannedAction(kind="move", source=entry, destination=dest, size=entry.stat().st_size)
                    )
                    continue
                # any other stray top-level file: unclassified, never guessed
                report.unclassified.append(
                    PlannedAction(kind="unclassified", source=entry, size=entry.stat().st_size)
                )
                continue

            # already-approved-for-deletion directories: skip (handled above)
            if entry in [d for d in APPROVED_DELETIONS if d.is_dir() and d.parent == iso_dir]:
                continue
            if name == "processed_backup_preP6":
                continue  # already in APPROVED_DELETIONS

            if name == "raw":
                for f in sorted(entry.rglob("*")):
                    if not f.is_file():
                        continue
                    rel = f.relative_to(entry)
                    result = _classify_raw_file(rel, iso3)
                    if result is None:
                        report.unclassified.append(
                            PlannedAction(kind="unclassified", source=f, size=f.stat().st_size)
                        )
                        continue
                    _source, dest_rel = result
                    dest = data_dir / dest_rel
                    report.moves.append(
                        PlannedAction(kind="move", source=f, destination=dest, size=f.stat().st_size)
                    )

            elif name == "processed":
                for f in sorted(entry.rglob("*")):
                    if not f.is_file():
                        continue
                    dest_rel = _classify_processed_file(f.name, iso3)
                    if dest_rel is None:
                        report.unclassified.append(
                            PlannedAction(kind="unclassified", source=f, size=f.stat().st_size)
                        )
                        continue
                    dest = data_dir / dest_rel
                    report.moves.append(
                        PlannedAction(kind="move", source=f, destination=dest, size=f.stat().st_size)
                    )

            elif name in _PHASE_DIR_MAP:
                for f in sorted(entry.rglob("*")):
                    if not f.is_file():
                        continue
                    rel = f.relative_to(entry)
                    if name == "suitability_criteria":
                        # preserve figures/reports/tif subdirs as "kind"
                        dest = data_dir / "outputs" / iso3 / "suitability_criteria" / rel
                    elif name == "artifacts":
                        dest = data_dir / "outputs" / iso3 / "artifacts" / rel
                    elif name == "audit":
                        dest = data_dir / "outputs" / iso3 / "data_quality_audit" / "reports" / rel
                    elif name == "grid_alignment":
                        dest = data_dir / "outputs" / iso3 / "grid_alignment" / "artifacts" / rel
                    else:
                        dest = data_dir / "outputs" / iso3 / name / rel
                    report.moves.append(
                        PlannedAction(kind="move", source=f, destination=dest, size=f.stat().st_size)
                    )

            else:
                # unrecognized subdirectory under outputs/<ISO3>/
                for f in sorted(entry.rglob("*")):
                    if f.is_file():
                        report.unclassified.append(
                            PlannedAction(kind="unclassified", source=f, size=f.stat().st_size)
                        )

    return report


def summarize(report: DryRunReport) -> None:
    by_dest_category: dict[str, tuple[int, int]] = {}
    for action in report.moves:
        assert action.destination is not None
        category = _category_of(action.destination)
        count, size = by_dest_category.get(category, (0, 0))
        by_dest_category[category] = (count + 1, size + action.size)

    print("\n=== Counts and total size per destination category ===")
    for cat, (count, size) in sorted(by_dest_category.items()):
        print(f"  {cat}: {count} files, {size / (1024**2):.1f} MiB")

    print(f"\n=== Deletion list ({len(report.deletions)} entries) ===")
    total_del = 0
    for d in report.deletions:
        print(f"  DELETE {d.source} ({d.size / 1024:.1f} KiB)")
        total_del += d.size
    print(f"  Total: {total_del / (1024**2):.2f} MiB")

    print(f"\n=== Unclassified files ({len(report.unclassified)}) — NOT moved, NOT deleted ===")
    for u in report.unclassified:
        print(f"  UNCLASSIFIED {u.source} ({u.size / 1024:.1f} KiB)")


_data_dir_root: Path | None = None


def _category_of(dest: Path) -> str:
    if _data_dir_root is not None:
        try:
            rel = dest.relative_to(_data_dir_root)
            return rel.parts[0]
        except ValueError:
            pass
    return dest.parts[-2] if len(dest.parts) > 1 else "?"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Perform real moves/deletes. Default is dry-run.")
    args = parser.parse_args()
    dry_run = not args.execute

    data_dir_env = os.environ.get("GEOFREA_DATA_DIR")
    shared_raw_env = os.environ.get("GEOFREA_SHARED_RAW_DIR")
    if not data_dir_env:
        print("ERROR: GEOFREA_DATA_DIR is not set. Cannot plan destinations.", file=sys.stderr)
        return 1
    if not shared_raw_env:
        print("ERROR: GEOFREA_SHARED_RAW_DIR is not set. Cannot verify it is untouched.", file=sys.stderr)
        return 1

    global _data_dir_root
    data_dir = Path(data_dir_env)
    shared_raw = Path(shared_raw_env)
    _data_dir_root = data_dir

    outputs_dir = REPO_ROOT / "outputs"

    print(f"Mode: {'DRY-RUN' if dry_run else 'EXECUTE'}")
    print(f"GEOFREA_DATA_DIR   = {data_dir}")
    print(f"GEOFREA_SHARED_RAW_DIR = {shared_raw}")

    # Volume check: repo (source) vs data_dir (destination)
    vol_ok = same_volume(outputs_dir, data_dir)
    print("\n=== Volume check ===")
    print(f"  outputs/ drive: {os.path.splitdrive(str(outputs_dir))[0]}")
    print(f"  GEOFREA_DATA_DIR drive: {os.path.splitdrive(str(data_dir))[0]}")
    print(f"  Same volume: {vol_ok}")
    if not vol_ok:
        print("ERROR: source and destination are on different volumes. os.replace() cannot be used "
              "and this script does not fall back to copy. Stopping.", file=sys.stderr)
        return 1

    # Free space on D:
    try:
        import shutil as _shutil
        _total, _used, free = _shutil.disk_usage(str(data_dir.drive) + "\\")
        print(f"  Free space on {data_dir.drive}: {free / (1024**3):.1f} GiB")
    except OSError as exc:
        print(f"  (could not determine free space: {exc})")

    # Pre-snapshot of shared raw (always, even in dry-run)
    logs_dir = data_dir / "logs" / "_snapshots"
    logs_dir.mkdir(parents=True, exist_ok=True)
    snap_name = "shared_raw_before.csv" if not (logs_dir / "shared_raw_before.csv").exists() else "shared_raw_before_e5b_mover.csv"
    snapshot_dir(shared_raw, logs_dir / snap_name, "shared_raw (pre-move, unaffected)")

    # Pre-snapshot of every source file under outputs/ + outputs_baseline_fc7b43d/ -> e5b_pre.csv
    moves_dir = REPO_ROOT / "logs" / "_moves" if not data_dir_env else data_dir / "logs" / "_moves"
    moves_dir.mkdir(parents=True, exist_ok=True)
    pre_csv = moves_dir / "e5b_pre.csv"
    file_count = 0
    with open(pre_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["path", "size", "mtime", "sha256"])
        for root in [outputs_dir, REPO_ROOT / "outputs_baseline_fc7b43d"]:
            if not root.exists():
                continue
            for p in sorted(root.rglob("*")):
                if p.is_file():
                    st = p.stat()
                    writer.writerow([str(p), st.st_size, st.st_mtime, sha256_of(p)])
                    file_count += 1
        for root_file in [REPO_ROOT / "main_run.log", REPO_ROOT / "recompute_run.log"]:
            if root_file.is_file():
                st = root_file.stat()
                writer.writerow([str(root_file), st.st_size, st.st_mtime, sha256_of(root_file)])
                file_count += 1
    print(f"\nPre-move snapshot: {file_count} source files -> {pre_csv}")

    # Build the plan
    report = build_plan(data_dir)
    summarize(report)

    deleted_file_count = 0
    for d in report.deletions:
        if d.source.is_dir():
            deleted_file_count += sum(1 for f in d.source.rglob("*") if f.is_file())
        else:
            deleted_file_count += 1
    total_planned = len(report.moves) + deleted_file_count + len(report.unclassified)
    print("\n=== Totals ===")
    print(f"  Moves: {len(report.moves)}")
    print(f"  Deletions: {len(report.deletions)} entries, {deleted_file_count} files")
    print(f"  Unclassified (stop-and-report): {len(report.unclassified)}")
    print(
        f"  Reconciliation: {len(report.moves)} moves + {deleted_file_count} deleted files + "
        f"{len(report.unclassified)} unclassified = {total_planned} "
        f"(must equal {file_count} source files)"
    )

    if dry_run:
        print("\nDRY-RUN complete. No files were moved or deleted.")
        if report.unclassified:
            print(f"\n{len(report.unclassified)} unclassified file(s) found — resolve before --execute.")
        return 0

    # --- EXECUTE MODE ---
    if report.unclassified:
        print(f"\nERROR: {len(report.unclassified)} unclassified file(s) found. Stopping before any change.", file=sys.stderr)
        return 1

    move_log = moves_dir / "e5b_move_log.csv"
    with open(move_log, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["source", "destination", "size", "sha256_before", "sha256_after", "action"])

        for action in report.moves:
            assert action.destination is not None
            sha_before = sha256_of(action.source)
            action.destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(action.source, action.destination)
            sha_after = sha256_of(action.destination)
            if sha_after != sha_before:
                print(f"ERROR: sha256 mismatch after move: {action.source} -> {action.destination}", file=sys.stderr)
                writer.writerow([action.source, action.destination, action.size, sha_before, sha_after, "MISMATCH"])
                return 1
            writer.writerow([action.source, action.destination, action.size, sha_before, sha_after, "moved"])

        for d in report.deletions:
            if d.source.is_dir():
                import shutil as _shutil
                _shutil.rmtree(d.source)
            else:
                d.source.unlink()
            writer.writerow([d.source, "", d.size, "", "", "deleted"])

    # remove now-empty source directories
    for iso_dir in sorted(outputs_dir.iterdir(), reverse=True):
        for sub in sorted(iso_dir.rglob("*"), reverse=True) if iso_dir.is_dir() else []:
            if sub.is_dir() and not any(sub.iterdir()):
                sub.rmdir()

    print(f"\nEXECUTE complete. Move log: {move_log}")

    # Post-snapshot of shared raw
    snapshot_dir(shared_raw, logs_dir / "shared_raw_after.csv", "shared_raw (post-move, must be unchanged)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
