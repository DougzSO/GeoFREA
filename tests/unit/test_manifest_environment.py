"""Every phase entry records the versions of Python and of the libraries that decide its files (COMMAND 128, OQ-084)."""

from __future__ import annotations

import json
import platform
from importlib import metadata

import pytest

from geofrea.core.orchestrator import ENVIRONMENT_PACKAGES, runtime_environment
from tests.unit.test_orchestrator import _make_spec, _orchestrator

pytestmark = pytest.mark.unit


def test_the_environment_names_python_and_the_six_libraries_with_the_installed_versions():
    env = runtime_environment()
    assert list(env) == ["python", *ENVIRONMENT_PACKAGES]
    assert ENVIRONMENT_PACKAGES == ("pyarrow", "pandas", "numpy", "geopandas", "rasterio", "pyproj")
    assert env["python"] == platform.python_version()
    for name in ENVIRONMENT_PACKAGES:
        assert env[name] == metadata.version(name)


def test_a_success_and_a_failure_both_carry_it_on_disk(tmp_path):
    log: list[str] = []
    ok = _make_spec("phase_ok", log, produces=frozenset({"ok_key"}))
    bad = _make_spec("phase_bad", log, fail=True)
    orchestrator = _orchestrator(tmp_path, ["phase_ok", "phase_bad"])
    orchestrator.run([ok, bad])
    on_disk = json.loads(orchestrator.manifest_path.read_text(encoding="utf-8"))
    assert {n: e["environment"] for n, e in on_disk["phases"].items()} == {"phase_ok": runtime_environment(), "phase_bad": runtime_environment()}


def test_a_manifest_of_an_older_schema_is_read_with_an_empty_environment_and_keeps_it_when_resumed(tmp_path):
    log: list[str] = []
    spec = _make_spec("phase_a", log)
    first = _orchestrator(tmp_path, ["phase_a"])
    first.run([spec])
    data = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    data["schema_version"] = "2.9"
    for entry in data["phases"].values():
        del entry["environment"]
    first.manifest_path.write_text(json.dumps(data), encoding="utf-8")
    second = _orchestrator(tmp_path, ["phase_a"])
    second.run([spec])  # resumed, not executed: the entry is the one of the old run
    assert second.manifest.phases["phase_a"].environment == {}
    assert second.manifest.schema_version == "2.11"
