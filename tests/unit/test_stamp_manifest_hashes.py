"""scripts/stamp_manifest_hashes.py: a manifest of schema 2.5 gets the code fingerprint of its phases (from a revision) and the content hash of the
artifacts whose file is the registered one; nothing else changes (COMMAND 58)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from geofrea.core.content_hash import content_hash

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "stamp_manifest_hashes.py"


def _load():
    spec = importlib.util.spec_from_file_location("stamp_manifest_hashes", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_stamp_adds_the_code_fingerprint_and_the_content_hash_and_keeps_the_rest(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    stamp = _load()
    good = tmp_path / "outputs" / "XXX" / "good.parquet"
    changed = tmp_path / "outputs" / "XXX" / "changed.json"
    good.parent.mkdir(parents=True)
    pd.DataFrame({"a": [1, 2, 3]}).to_parquet(good)
    changed.write_text('{"x": 1}', encoding="utf-8")
    manifest = {
        "schema_version": "2.5",
        "run_id": "r",
        "phases": {
            "land_eligibility": {"status": "success", "phase": "land_eligibility"},
            "overview": {"status": "stale_upstream", "phase": "overview"},
            "technical_potential": {
                "status": "success",
                "phase": "technical_potential",
                "code_fingerprint": "kept",
            },
        },
        "artifacts": {
            "good": {
                "path": {"root": "data", "rel": "outputs/XXX/good.parquet"},
                "sha256": _sha(good),
            },
            "changed": {
                "path": {"root": "data", "rel": "outputs/XXX/changed.json"},
                "sha256": "0" * 64,
            },
            "absent": {
                "path": {"root": "data", "rel": "outputs/XXX/absent.json"},
                "sha256": "0" * 64,
            },
        },
    }
    path = tmp_path / "outputs" / "XXX" / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    report = stamp.stamp(
        path, {"land_eligibility": "fp-f3", "technical_potential": "fp-f5", "overview": "fp-ov"}
    )

    out = json.loads(path.read_text(encoding="utf-8"))
    assert out["schema_version"] == "2.6"
    assert out["phases"]["land_eligibility"]["code_fingerprint"] == "fp-f3"
    assert (
        out["phases"]["technical_potential"]["code_fingerprint"] == "kept"
    )  # an existing one is never replaced
    assert "code_fingerprint" not in out["phases"]["overview"]  # only a successful phase
    assert out["artifacts"]["good"]["content_sha256"] == content_hash(good)
    assert (
        "content_sha256" not in out["artifacts"]["changed"]
        and "content_sha256" not in out["artifacts"]["absent"]
    )
    assert report["not_stamped"] == {
        "changed": "bytes differ from the recorded sha256",
        "absent": "file absent",
    }
    assert path.with_name("manifest.json.before_stamp").is_file()
    assert out["run_id"] == "r"


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    stamp = _load()
    path = tmp_path / "manifest.json"
    original = json.dumps(
        {"schema_version": "2.5", "phases": {"overview": {"status": "success"}}, "artifacts": {}}
    )
    path.write_text(original, encoding="utf-8")
    stamp.stamp(path, {"overview": "fp"}, dry_run=True)
    assert (
        path.read_text(encoding="utf-8") == original
        and not path.with_name("manifest.json.before_stamp").exists()
    )


def test_fingerprints_at_a_revision_cover_every_phase():
    stamp = _load()
    prints = stamp.fingerprints_at("HEAD")
    from geofrea.core.code_fingerprint import PHASE_CODE_ROOTS

    assert set(prints) == set(PHASE_CODE_ROOTS) and all(len(v) == 64 for v in prints.values())
