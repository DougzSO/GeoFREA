"""The manifest is replaced as a whole (COMMAND 78): an interrupted write never leaves a truncated manifest.json."""

from __future__ import annotations

from pathlib import Path

import pytest

from geofrea.core.orchestrator import Orchestrator


def test_write_manifest_goes_through_a_temporary_file_and_leaves_no_residue(tmp_path, monkeypatch):
    class Fake:
        manifest_path = tmp_path / "outputs" / "PRT" / "manifest.json"

        class manifest:  # noqa: N801 - a stand-in object with the one method used
            @staticmethod
            def model_dump_json(indent=2):
                return '{"ok": true}'

    seen = {}
    real_replace = Path.replace

    def spy(self, target):
        seen["tmp_existed"] = self.exists()
        seen["tmp_name"] = self.name
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", spy)
    Orchestrator._write_manifest(Fake)
    assert seen == {"tmp_existed": True, "tmp_name": "manifest.json.tmp"}
    assert Fake.manifest_path.read_text(encoding="utf-8") == '{"ok": true}'
    assert not list(Fake.manifest_path.parent.glob("*.tmp"))


def test_a_failure_while_writing_keeps_the_previous_manifest(tmp_path, monkeypatch):
    path = tmp_path / "manifest.json"
    path.write_text("previous", encoding="utf-8")

    class Fake:
        manifest_path = path

        class manifest:  # noqa: N801
            @staticmethod
            def model_dump_json(indent=2):
                raise RuntimeError("killed while serialising")

    with pytest.raises(RuntimeError):
        Orchestrator._write_manifest(Fake)
    assert path.read_text(encoding="utf-8") == "previous"
