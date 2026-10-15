"""One-off tool of COMMAND 37 (2026-10-14): copy (never move) the files of the author's local database that the pipeline read into GeoFREA_data/raw in the A-08 layout.

The pipeline no longer reads the local database; this script is kept as the record of how the files were placed (the origin is `raw/_shared_origin/manifest.json`).

Read set: the local_only layers of outputs/<ISO>/artifacts/layer_registry.json for PRT, BRA and IND (path and paths), plus the sidecars
of every shapefile. Destination: raw/<source>/<ISO3|_global>/. Each copy is checked by SHA-256 against its origin.
The origin is only read. Writes a manifest of origin, destination, size and sha256.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

DATA = Path(r"D:\Douglas\DOUTORADO\GeoFREA_data")
SHARED = Path(r"D:\Douglas\DOUTORADO\database\raw")
ISO_OF_DIR = {"Portugal": "PRT", "Brazil": "BRA", "India": "IND"}
KEEP_EXT = None  # all sidecars of a shapefile


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def destination(rel: Path, iso: str) -> Path:
    parts = rel.parts
    top = parts[0]
    if top == "elevation":
        return Path("elevation") / iso / rel.name
    if top == "population":
        return Path("population") / iso / rel.name
    if top == "infrastructure" and parts[1] == "grid":
        return Path("infrastructure_grid") / iso / rel.name
    if top == "infrastructure" and parts[1] == "roads":
        return Path("infrastructure_roads") / "_global" / Path(*parts[2:])
    if top == "land_cover":
        return Path("land_cover") / iso / rel.name
    if top == "solar_potential":
        return Path("solar_potential") / "_global" / Path(*parts[1:])
    raise ValueError(f"unmapped shared path {rel}")


def read_set() -> dict[Path, str]:
    """origin (absolute) -> country that reads it."""
    out: dict[Path, str] = {}
    for iso in ("PRT", "BRA", "IND"):
        reg = json.loads(
            (DATA / "outputs" / iso / "artifacts" / "layer_registry.json").read_text(
                encoding="utf-8"
            )
        )
        for layer in reg["layers"]:
            paths = ([layer["path"]] if layer.get("path") else []) + list(layer.get("paths") or [])
            for p in paths:
                pp = Path(p)
                try:
                    pp.relative_to(SHARED)
                except ValueError:
                    continue
                files = [pp]
                if pp.suffix.lower() == ".shp":
                    files = sorted(pp.parent.glob(pp.stem + ".*"))
                for f in files:
                    out.setdefault(f, iso)
    return out


def main(dry: bool) -> None:
    items = read_set()
    plan = []
    for origin, iso in sorted(items.items()):
        rel = origin.relative_to(SHARED)
        plan.append((origin, DATA / "raw" / destination(rel, iso), iso))
    total = sum(o.stat().st_size for o, _, _ in plan)
    print(len(plan), "files", round(total / 1e9, 2), "GB")
    if dry:
        for o, d, _ in plan[:5] + plan[-5:]:
            print(o, "->", d)
        return
    manifest = []
    for i, (origin, dest, iso) in enumerate(plan, 1):
        size = origin.stat().st_size
        src_hash = sha256(origin)
        if dest.exists() and dest.stat().st_size == size and sha256(dest) == src_hash:
            status = "already_copied"
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".part")
            shutil.copyfile(origin, tmp)
            if sha256(tmp) != src_hash:
                tmp.unlink()
                raise SystemExit(f"checksum mismatch copying {origin}")
            tmp.replace(dest)
            status = "copied"
        manifest.append(
            {
                "origin": str(origin),
                "destination": str(dest),
                "size_bytes": size,
                "sha256": src_hash,
                "read_by_country": iso,
                "status": status,
            }
        )
        if i % 10 == 0 or size > 200e6:
            print(i, len(plan), status, dest.name, flush=True)
    out = DATA / "raw" / "_shared_origin" / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"origin_root": str(SHARED), "files": manifest}, indent=1), encoding="utf-8"
    )
    print("manifest", out, len(manifest))


if __name__ == "__main__":
    main("--dry" in sys.argv)
