"""Archive what the pipeline does not read out of GEOFREA_DATA_DIR (pre-research audit, section 9.3; COMMAND 37 action 4).

Nothing is deleted. Each item is moved to `<ARCHIVE>/<path relative to GEOFREA_DATA_DIR>` (the relative path is preserved, so a restore is
the reverse move) and recorded in `<ARCHIVE>/manifest.json` with origin, destination, size, SHA-256, reason and audit item. The archive is
`D:\\Douglas\\DOUTORADO\\database\\archive\\geofrea_2026-10` by default; nothing under `database\\raw` is touched.

Items (all selected by name, never by a glob that could reach a file the pipeline reads):

  L-1  ERA5 hourly `fg10` files: `<ISO3>_fg10_hourly.nc` and `_global/*_fg10_hourly_bbox*.nc`. The pipeline reads the annual maxima.
  L-2  CMIP6 files of the nine models that are not in `experiments.yaml` `gcm_ensemble`; their entries leave `cmip6_registry.json`.
  L-3  ISIMIP3b `tasmin` files and the files of the models that are not hazard channels; their entries leave `isimip3b_registry.json`.
  L-4  The zip of each pair zip and extracted folder (the pipeline reads the extracted folder).
  L-5  The old slope and the duplicate clips of `outputs/<ISO3>/processed` (the F1b caches themselves move to `interim`, see below).
  L-6  `reference/legacy_baseline_fc7b43d`.
  L-7  `outputs/<ISO3>/suitability_criteria` (a retired phase) and the empty `outputs/_global`.

Run: `python scripts/archive_geofrea_data.py` prints the plan and the code search; `--apply` moves (the ERA5 Tmax files `*_t2m_*` are refused by
name, so a live acquisition is never disturbed).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
ARCHIVE = Path(r"D:\Douglas\DOUTORADO\database\archive\geofrea_2026-10")
HAZARD_GCMS = (
    "gfdl-esm4",
    "ipsl-cm6a-lr",
    "mri-esm2-0",
)  # ISIMIP3b models with a hazard channel (experiments.yaml)


@dataclass
class Item:
    path: Path  # absolute origin
    reason: str
    audit_item: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def files_of(path: Path) -> list[Path]:
    return [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())


def selected_cmip6_stems(data: Path) -> set[str]:
    experiments = yaml.safe_load((REPO / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    return {g["cds_name"] for g in experiments["gcm_ensemble"]["gcms"]}


def plan(data: Path) -> list[Item]:
    items: list[Item] = []
    raw = data / "raw"
    # L-1
    for p in sorted(raw.joinpath("era5").rglob("*_fg10_hourly*.nc")):
        if "t2m" in p.name:
            continue
        items.append(
            Item(
                p,
                "raw hourly fg10 field; the pipeline reads the annual maximum `<ISO3>_fg10_annual_max.nc`",
                "L-1",
            )
        )
    # L-2
    selected = selected_cmip6_stems(data)
    for p in sorted(raw.joinpath("cmip6").rglob("*.nc")):
        m = re.match(r"(.+?)_(?:historical|ssp\d+)_", p.name)
        if m and m.group(1) not in selected:
            items.append(
                Item(p, f"CMIP6 model {m.group(1)} is not in experiments.yaml gcm_ensemble", "L-2")
            )
    # L-3
    for p in sorted(raw.joinpath("isimip3b").rglob("*.nc")):
        gcm = p.name.split("_")[0]
        if "_tasmin_" in p.name:
            items.append(Item(p, "ISIMIP3b tasmin: no indicator reads it", "L-3"))
        elif gcm not in HAZARD_GCMS:
            items.append(
                Item(p, f"ISIMIP3b model {gcm} has no hazard channel in experiments.yaml", "L-3")
            )
    # L-4
    for p in sorted(raw.rglob("*.zip")):
        extracted = p.with_suffix("")
        if extracted.is_dir():
            items.append(
                Item(
                    p,
                    f"zip of the extracted folder {extracted.name}, which is the one the pipeline reads",
                    "L-4",
                )
            )
    # L-5
    for iso in ("BRA", "IND", "PRT", "ZZZ"):
        for p in sorted(data.joinpath("outputs", iso, "processed").glob("*slope*")):
            items.append(
                Item(
                    p,
                    "old slope raster; slope is derived and cached by grid_alignment in interim",
                    "L-5",
                )
            )
    # L-6
    legacy = data / "reference" / "legacy_baseline_fc7b43d"
    if legacy.exists():
        items.append(
            Item(legacy, "retired legacy baseline; V-01 now uses the in-repo fixtures", "L-6")
        )
    # L-7
    for p in sorted(data.joinpath("outputs").glob("*/suitability_criteria")):
        items.append(Item(p, "outputs of the retired phase suitability_criteria", "L-7"))
    empty = data / "outputs" / "_global"
    if empty.is_dir() and not any(empty.iterdir()):
        items.append(Item(empty, "empty folder", "L-7"))
    return items


def refuse(item: Item) -> None:
    if any("t2m" in part for part in item.path.parts):
        raise SystemExit(f"refusing to move an ERA5 Tmax path: {item.path}")


def code_search(patterns: list[str]) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    roots = [REPO / "src", REPO / "main.py", REPO / "scripts", REPO / "config"]
    for pattern in patterns:
        rx = re.compile(pattern)
        found = []
        for root in roots:
            for p in (
                [root]
                if root.is_file()
                else sorted(root.rglob("*.py")) + sorted(root.rglob("*.yaml"))
            ):
                if p.name == "archive_geofrea_data.py":
                    continue
                for number, line in enumerate(
                    p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
                ):
                    if rx.search(line):
                        found.append(f"{p.relative_to(REPO)}:{number}: {line.strip()[:100]}")
        hits[pattern] = found
    return hits


def prune_registries(data: Path, items: list[Item], manifest: dict) -> None:
    """Drop from `cmip6_registry.json` and `isimip3b_registry.json` the entries of archived files; the registries as they were are kept in the archive."""
    archived = {Path(m["origin"]) for m in manifest["items"]}
    selected = selected_cmip6_stems(data)
    targets = {
        data / "raw" / "cmip6" / "_global" / "cmip6_registry.json": lambda key, entry: (
            key.split("/")[1] not in selected
        ),
        data / "raw" / "isimip3b" / "isimip3b_registry.json": lambda key, entry: (
            Path(entry["path"]) in archived
        ),
    }
    for registry, drop in targets.items():
        if not registry.is_file():
            continue
        document = json.loads(registry.read_text(encoding="utf-8"))
        before = ARCHIVE / registry.relative_to(data).with_name(
            registry.stem + ".before_archive.json"
        )
        before.parent.mkdir(parents=True, exist_ok=True)
        if not before.exists():
            before.write_text(json.dumps(document, indent=1), encoding="utf-8")
        entries = document["entries"]
        kept = {k: v for k, v in entries.items() if not drop(k, v)}
        document["entries"] = kept
        registry.write_text(json.dumps(document, indent=1), encoding="utf-8")
        manifest.setdefault("registries_pruned", {})[str(registry)] = {
            "entries_before": len(entries),
            "entries_after": len(kept),
            "copy_before": str(before),
        }


def main(argv: list[str]) -> int:
    load_dotenv(REPO / ".env", override=False)
    data = Path(os.environ["GEOFREA_DATA_DIR"])
    apply = "--apply" in argv
    items = plan(data)
    total = 0
    by_item: dict[str, list[int]] = {}
    for item in items:
        size = sum(f.stat().st_size for f in files_of(item.path))
        total += size
        by_item.setdefault(item.audit_item, [0, 0])
        by_item[item.audit_item][0] += 1
        by_item[item.audit_item][1] += size
    for key, (count, size) in sorted(by_item.items()):
        print(f"{key}: {count} items, {size / 1e9:.2f} GB")
    print(f"total {total / 1e9:.2f} GB in {len(items)} items")
    hits = code_search(
        [r"tasmin", r"fg10_hourly", r"suitability_criteria", r"legacy_baseline", r"LEGACY_BASELINE"]
    )
    for pattern, found in hits.items():
        print(f"code search {pattern!r}: {len(found)} hits")
        for h in found[:6]:
            print("   ", h)
    if not apply:
        return 0
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    manifest_path = ARCHIVE / "manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.is_file()
        else {"items": []}
    )
    done = {m["origin"] for m in manifest["items"]}
    for item in items:
        refuse(item)
        for f in files_of(item.path):
            if str(f) in done:
                continue
            relative = f.relative_to(data)
            destination = ARCHIVE / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            size = f.stat().st_size
            digest = sha256(f)
            if destination.exists():
                raise SystemExit(f"destination exists: {destination}")
            os.replace(f, destination)
            manifest["items"].append(
                {
                    "origin": str(f),
                    "destination": str(destination),
                    "relative_path": relative.as_posix(),
                    "size_bytes": size,
                    "sha256": digest,
                    "reason": item.reason,
                    "audit_item": item.audit_item,
                    "moved_at": datetime.now(UTC).isoformat(timespec="seconds"),
                }
            )
        manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        if item.path.is_dir():  # remove the emptied folders, never a file
            for folder in sorted((p for p in item.path.rglob("*") if p.is_dir()), reverse=True):
                if not any(folder.iterdir()):
                    folder.rmdir()
            if not any(item.path.iterdir()):
                item.path.rmdir()
    prune_registries(data, items, manifest)
    manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print("archived", len(manifest["items"]), "files; manifest", manifest_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
