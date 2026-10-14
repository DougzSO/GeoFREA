"""The registry of the hypothesis profiles in `outputs/thesis/thesis_manifest.json` (B-4 of the 2026-10 audit; D-F8-023).

T-R8 compares the countries, so a country's build reads the profiles that the builds of the other countries wrote. A profile file found in the
directory is not an input: only a file registered here, with the SHA-256 it had when its country's build registered it, is read, and the hash of
each profile read goes into the provenance of the T-R8 tables. A file that was edited, replaced or deleted after its registration is refused; the
country's build is run again to register a new one.
"""

from __future__ import annotations

import json
from pathlib import Path

from geofrea.core.artifact_reader import ThesisInputError, sha256_of

MANIFEST_NAME = "thesis_manifest.json"
PROFILES_KEY = "hypothesis_profiles"


def _load(out_dir: Path) -> dict:
    path = Path(out_dir) / MANIFEST_NAME
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"countries": {}}


def write_manifest(out_dir: Path, manifest: dict) -> None:
    (Path(out_dir) / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def register_profile(out_dir: Path, iso: str, path: Path) -> str:
    """Register the profile file `path` of `iso` with its hash and return the hash."""
    manifest = _load(out_dir)
    digest = sha256_of(path)
    entry = manifest["countries"].setdefault(iso, {})
    entry.setdefault("artifacts", {})[PROFILES_KEY] = {"file": Path(path).name, "sha256": digest}
    write_manifest(out_dir, manifest)
    return digest


def registered_profiles(out_dir: Path) -> dict[str, tuple[Path, str]]:
    """`{country: (file, sha256)}` of the registered profiles, sorted by country, each file checked against its registered hash.

    Raises:
        ThesisInputError: a registered file is absent or its content differs from the registered hash.
    """
    out = {}
    for iso, entry in sorted(_load(out_dir)["countries"].items()):
        registered = entry.get("artifacts", {}).get(PROFILES_KEY)
        if registered is None:
            continue
        path = Path(out_dir) / registered["file"]
        if not path.is_file():
            raise ThesisInputError(
                f"{iso}: the profile {registered['file']} is registered but absent"
            )
        if sha256_of(path) != registered["sha256"]:
            raise ThesisInputError(
                f"{iso}: the profile {registered['file']} changed since it was registered; build the thesis outputs of {iso} again"
            )
        out[iso] = (path, registered["sha256"])
    return out
