"""Stamp the hashes of manifest schema 2.6 on a manifest written before it (COMMAND 58, A-02).

usage: python scripts/stamp_manifest_hashes.py <ISO3> --revision <git revision> [--dry-run]

A manifest of schema 2.5 has no `code_fingerprint` on its phases and no `content_sha256` on its artifacts. Without them the orchestrator
resumes each phase once and adopts the fingerprint of the code it finds today, so a change of code made after the real run would never be
detected, and an artifact rewritten with the same data would be compared by its bytes. This script records what the real run had:

- `code_fingerprint` of every successful phase entry that has none: the fingerprint of the phase computed on the source of `--revision`, the
  revision of the code the phase ran with (the caller states it; this script only reads that tree with `git archive`);
- `content_sha256` of every artifact entry that has none: the canonical content hash of the file on disk, only when the SHA-256 of its bytes
  equals the recorded `sha256` (the file is the registered one). Other artifacts are named and left without it.

It edits `outputs/<ISO3>/manifest.json` (a copy is written beside it as `manifest.json.before_stamp`), sets `schema_version` to 2.6, and prints
what it did. Nothing else is touched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from geofrea.core import paths as core_paths
from geofrea.core.code_fingerprint import PHASE_CODE_ROOTS, code_fingerprint
from geofrea.core.content_hash import content_hash
from geofrea.core.paths import StoredPath
from geofrea.core.scale import manifest_file_name


def fingerprints_at(revision: str) -> dict[str, str]:
    """The code fingerprint of every phase on the `src/geofrea` tree of a git revision."""
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "src.tar"
        subprocess.run(
            [
                "git",
                "-C",
                str(REPO),
                "archive",
                "--format=tar",
                "-o",
                str(archive),
                revision,
                "src/geofrea",
            ],
            check=True,
        )
        subprocess.run(["tar", "-xf", str(archive), "-C", tmp], check=True)
        root = Path(tmp) / "src" / "geofrea"
        return {phase: code_fingerprint(phase, root) for phase in PHASE_CODE_ROOTS}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def stamp(manifest_path: Path, fingerprints: dict[str, str], dry_run: bool = False) -> dict:
    """Edit the manifest at `manifest_path`; returns what was stamped and what was left."""
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    report: dict = {"code_fingerprint": [], "content_sha256": [], "not_stamped": {}}
    for name, entry in data["phases"].items():
        if (
            entry.get("status") == "success"
            and not entry.get("code_fingerprint")
            and name in fingerprints
        ):
            entry["code_fingerprint"] = fingerprints[name]
            report["code_fingerprint"].append(name)
    for key, entry in data["artifacts"].items():
        if entry.get("content_sha256"):
            continue
        path = StoredPath.model_validate(entry["path"]).resolve()
        if not path.is_file():
            report["not_stamped"][key] = "file absent"
        elif _sha256(path) != entry["sha256"]:
            report["not_stamped"][key] = "bytes differ from the recorded sha256"
        else:
            entry["content_sha256"] = content_hash(path)
            report["content_sha256"].append(key)
    data["schema_version"] = "2.6"
    if not dry_run:
        shutil.copy2(manifest_path, manifest_path.with_name(manifest_path.name + ".before_stamp"))
        manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("iso")
    parser.add_argument(
        "--revision", required=True, help="git revision of the code the real run used"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    manifest = core_paths.outputs_dir() / args.iso / manifest_file_name()
    report = stamp(manifest, fingerprints_at(args.revision), args.dry_run)
    print(
        json.dumps(
            {
                "manifest": str(manifest),
                "revision": args.revision,
                "phases_stamped": report["code_fingerprint"],
                "artifacts_stamped": len(report["content_sha256"]),
                "artifacts_not_stamped": report["not_stamped"],
                "dry_run": args.dry_run,
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
