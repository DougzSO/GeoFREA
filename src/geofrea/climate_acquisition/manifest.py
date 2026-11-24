"""Manifest of the ISIMIP3b files of the v2 climate channel (`raw/isimip3b/isimip3b_v2_manifest.json`).

Provenance (A-11). Replaces the manifest bridge of the CRAEI repository (https://github.com/DougzSO/CRAEI.git, commit 7e9a6ac233e4a9ccd169292f7dc7dda069b1ba9f,
`src/craei/manifest.py` and `src/craei/storage.py`): same idea (one record per file, atomic write, intact check by
size, full check by sha256), rewritten for this package. A file enters the manifest only when it is complete.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path

SCHEMA_VERSION = 1
ENTRY_FIELDS = (
    "sha256", "size_bytes", "url", "accessed_utc", "bbox", "gcm", "ghm", "scenario", "variable", "country", "period",
    "time_step", "spatial_resolution_deg", "origin", "effective_source", "isimip_file", "soc", "source_sha256",
)


def sha256_file(path: Path, block: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(block):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


class Manifest:
    """JSON manifest keyed by the path of each file relative to `root` (`GEOFREA_DATA_DIR/raw/isimip3b`)."""

    def __init__(self, path: Path, root: Path):
        self.path = Path(path)
        self.root = Path(root)
        self._lock = threading.Lock()
        self.entries: dict[str, dict] = {}
        if self.path.exists():
            doc = json.loads(self.path.read_text(encoding="utf-8"))
            self.entries = doc.get("entries", {})

    def save(self) -> None:
        doc = {"schema_version": SCHEMA_VERSION, "entries": self.entries}
        atomic_write_text(self.path, json.dumps(doc, indent=1, sort_keys=True))

    def add(self, rel_path: str, entry: dict) -> None:
        missing = [f for f in ENTRY_FIELDS if f not in entry]
        if missing:
            raise ValueError(f"manifest entry of {rel_path} lacks {missing}")
        with self._lock:
            self.entries[rel_path] = entry
            self.save()

    def is_intact(self, rel_path: str) -> bool:
        """Registered and the file is there with the recorded size (cheap check; `verify` re-hashes)."""
        entry = self.entries.get(rel_path)
        if entry is None:
            return False
        p = self.root / rel_path
        return p.is_file() and p.stat().st_size == entry["size_bytes"]

    def verify(self, rel_paths: list[str] | None = None) -> dict[str, list[str]]:
        """Re-hash the files and compare with the manifest. Returns the paths that are missing or different."""
        out: dict[str, list[str]] = {"missing": [], "size": [], "sha256": []}
        for rel in rel_paths if rel_paths is not None else sorted(self.entries):
            entry = self.entries[rel]
            p = self.root / rel
            if not p.is_file():
                out["missing"].append(rel)
            elif p.stat().st_size != entry["size_bytes"]:
                out["size"].append(rel)
            elif sha256_file(p) != entry["sha256"]:
                out["sha256"].append(rel)
        return out
