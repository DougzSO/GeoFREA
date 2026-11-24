"""Copy of the files of the local country that the CRAEI already holds, with the hash checked on both sides.

Provenance (A-11). Adapted from the CRAEI repository (https://github.com/DougzSO/CRAEI.git, commit
7e9a6ac233e4a9ccd169292f7dc7dda069b1ba9f): the per-file records of `manifest_extension_b12.json` (sha256, global
source, job URL, units, calendar) are the reference hashes. The CRAEI tree is only read: files are copied, never moved.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .config import Requirement
from .manifest import Manifest, sha256_file
from .plan import LOCAL_COPY, local_source_path


def load_craei_hashes(manifest_path: Path | None) -> dict[str, dict]:
    """sha256 and source records of the CRAEI extension manifest, keyed by file name."""
    out: dict[str, dict] = {}
    if manifest_path is None or not Path(manifest_path).is_file():
        return out
    doc = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    for rec in doc.values():
        for f in rec.get("files", []):
            out[Path(f["file"]).name] = {"sha256": f["sha256"], "bytes": f["bytes"], "job_url": rec.get("job_url"),
                                         "file_url": rec.get("file_url"), "date": rec.get("date")}
    return out


def _copy_hashed(src: Path, dst: Path) -> str:
    """Copy `src` to `dst` through a `.part` file and return the sha256 of the bytes written."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(dst.name + ".part")
    h = hashlib.sha256()
    with open(src, "rb") as fin, open(part, "wb") as fout:
        while chunk := fin.read(1 << 20):
            h.update(chunk)
            fout.write(chunk)
    shutil.copystat(src, part)
    os.replace(part, dst)
    return h.hexdigest()


def copy_local(reqs: list[Requirement], status: dict[str, str], cfg: dict, root: Path, manifest: Manifest, craei_root: Path,
               craei_hashes: dict[str, dict], now=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")) -> dict:
    """Copy every requirement whose status is `local_copy`. Returns counts and the list of failures."""
    layout = cfg["layout"]
    done, failed = 0, []
    for r in reqs:
        rel = r.rel_path(layout)
        if status[rel] != LOCAL_COPY:
            continue
        src = local_source_path(r, craei_root, cfg["local_source_country"])
        if src is None:
            failed.append({"rel_path": rel, "reason": "source vanished"})
            continue
        ref = craei_hashes.get(src.name)
        src_sha = sha256_file(src)
        if ref is not None and ref["sha256"] != src_sha:
            failed.append({"rel_path": rel, "reason": "source sha256 differs from the CRAEI manifest"})
            continue
        dst = root / rel
        dst_sha = _copy_hashed(src, dst)
        if dst_sha != src_sha or sha256_file(dst) != src_sha:
            dst.unlink(missing_ok=True)
            failed.append({"rel_path": rel, "reason": "copy sha256 differs from the source"})
            continue
        manifest.add(rel, {
            "sha256": dst_sha,
            "size_bytes": dst.stat().st_size,
            "url": (ref or {}).get("file_url") or r.global_path,
            "accessed_utc": (ref or {}).get("date") or now(),
            "bbox": list(r.bbox),
            "gcm": r.gcm,
            "ghm": r.ghm,
            "scenario": r.scenario,
            "variable": r.variable,
            "country": r.country,
            "period": [r.start_year, r.end_year],
            "time_step": r.time_step,
            "spatial_resolution_deg": 0.5,
            "origin": "craei_local_copy",
            "effective_source": f"copied from {src.as_posix()} at {now()}",
            "isimip_file": r.global_path,
            "soc": r.soc,
            "source_sha256": src_sha,
            "hash_reference": "craei_manifest" if ref is not None else "computed_on_both_sides",
        })
        done += 1
    return {"copied": done, "failed": failed}
