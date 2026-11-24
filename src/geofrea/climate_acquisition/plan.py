"""Download plan: what is already registered, what a local CRAEI copy covers, what has to be downloaded, and how big it is.

Provenance (A-11). The size estimate follows the crop-ratio idea of `src/craei/acquire/isimip_layer.py` of the CRAEI
repository (https://github.com/DougzSO/CRAEI.git, commit 7e9a6ac233e4a9ccd169292f7dc7dda069b1ba9f): the cut-out is a fraction of the global file, measured on
files already cut. Here the fraction is measured per (family, variable) on the local files and scaled by the
number of 0.5 degree cells of each country box.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .config import ATMOSPHERE, Requirement, grid_cells
from .manifest import Manifest, atomic_write_text

IN_MANIFEST, LOCAL_COPY, DOWNLOAD = "in_manifest", "local_copy", "download"


def local_source_path(req: Requirement, craei_root: Path, local_country: str) -> Path | None:
    """Where the CRAEI keeps the cut of this requirement, if the file is there (read only); it holds one country only."""
    if req.country != local_country:
        return None
    if req.family == ATMOSPHERE:
        p = craei_root / "isimip3b" / req.gcm / req.scenario / req.variable / req.name
    else:
        p = craei_root / "isimip3b_water" / str(req.ghm) / req.gcm / req.scenario / req.variable / req.name
    return p if p.is_file() else None


def classify(reqs: list[Requirement], layout: dict, manifest: Manifest, craei_root: Path | None, local_country: str) -> dict[str, str]:
    """Status of each requirement, keyed by its relative path."""
    out: dict[str, str] = {}
    for r in reqs:
        rel = r.rel_path(layout)
        if manifest.is_intact(rel):
            out[rel] = IN_MANIFEST
        elif craei_root is not None and local_source_path(r, craei_root, local_country) is not None:
            out[rel] = LOCAL_COPY
        else:
            out[rel] = DOWNLOAD
    return out


def crop_ratios(reqs: list[Requirement], craei_root: Path | None, local_country: str) -> dict[tuple[str, str], float]:
    """Measured fraction of the global size that a cut of the local country occupies, per (family, variable)."""
    sums: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    if craei_root is not None:
        for r in reqs:
            p = local_source_path(r, craei_root, local_country)
            if p is not None and r.global_bytes:
                s = sums[(r.family, r.variable)]
                s[0] += p.stat().st_size
                s[1] += r.global_bytes
    ratios = {k: a / b for k, (a, b) in sums.items() if b}
    for r in reqs:  # variables never cut by the CRAEI (tas): the mean of the daily variables that were
        if (r.family, r.variable) not in ratios:
            peers = [v for (fam, _), v in ratios.items() if fam == r.family]
            if peers:
                ratios[(r.family, r.variable)] = sum(peers) / len(peers)
    return ratios


def estimate_bytes(req: Requirement, ratios: dict, ref_bbox: list[float]) -> int | None:
    ratio = ratios.get((req.family, req.variable))
    if ratio is None or not req.global_bytes:
        return None
    return int(req.global_bytes * ratio * grid_cells(list(req.bbox)) / grid_cells(ref_bbox))


def summarise(reqs: list[Requirement], status: dict[str, str], layout: dict, ratios: dict, ref_bbox: list[float]) -> dict:
    """Counts and estimated bytes per status, family and country."""
    rows: dict[str, dict] = {}
    for r in reqs:
        st = status[r.rel_path(layout)]
        key = f"{st}|{r.family}|{r.country}"
        row = rows.setdefault(key, {"status": st, "family": r.family, "country": r.country, "files": 0, "est_bytes": 0, "unestimated": 0})
        row["files"] += 1
        est = estimate_bytes(r, ratios, ref_bbox)
        if est is None:
            row["unestimated"] += 1
        else:
            row["est_bytes"] += est
    return {"rows": sorted(rows.values(), key=lambda x: (x["status"], x["family"], x["country"]))}


def write_plan(path: Path, cfg: dict, reqs: list[Requirement], status: dict[str, str], gaps: list[dict], ratios: dict,
               free_bytes: int | None, accessed_utc: str) -> dict:
    layout = cfg["layout"]
    bra = cfg["bboxes"][cfg["local_source_country"]]
    items = []
    for r in reqs:
        rel = r.rel_path(layout)
        items.append({"rel_path": rel, "status": status[rel], "est_bytes": estimate_bytes(r, ratios, bra), **r.as_dict()})
    summary = summarise(reqs, status, layout, ratios, bra)
    to_dl = sum(i["est_bytes"] or 0 for i in items if i["status"] == DOWNLOAD)
    doc = {
        "schema_version": 1,
        "accessed_utc": accessed_utc,
        "crop_ratios": {f"{a}/{b}": v for (a, b), v in sorted(ratios.items())},
        "summary": summary,
        "estimated_download_bytes": to_dl,
        "free_bytes_data_drive": free_bytes,
        "free_space_margin_gb": cfg["download"]["free_space_margin_gb"],
        "gaps": gaps,
        "items": items,
    }
    atomic_write_text(path, json.dumps(doc, indent=1, sort_keys=True))
    return doc
