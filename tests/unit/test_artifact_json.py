"""Deterministic artifact JSON: no timestamp, run time or absolute path in the content of a registered artifact (COMMAND 24, A-02)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from geofrea.core.artifact_json import REPO_ROOT, dump_artifact, find_nondeterministic


class _Inner(BaseModel):
    path: Path
    timings: dict[str, float]


class _Output(BaseModel):
    country_code: str
    timestamp: str
    elapsed_total: float
    report_path: str | None
    layers: list[_Inner]
    note: str = "https://example.org/a"


def _output(data_dir: Path, timestamp: str, elapsed: float) -> _Output:
    return _Output(
        country_code="ZZZ",
        timestamp=timestamp,
        elapsed_total=elapsed,
        report_path=str(data_dir / "outputs" / "audit_x.txt"),
        layers=[_Inner(path=data_dir / "raw" / "a.tif", timings={"a": elapsed})],
    )


def test_two_runs_with_other_times_and_the_same_result_give_the_same_bytes(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    first = dump_artifact(_output(tmp_path, "2026-10-12T10:00:00+00:00", 1.5))
    second = dump_artifact(_output(tmp_path, "2026-10-13T11:30:00+00:00", 99.0))
    assert first == second


def test_volatile_fields_are_dropped_and_data_paths_become_portable(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    loaded = json.loads(dump_artifact(_output(tmp_path, "2026-10-12T10:00:00+00:00", 1.5)))
    assert set(loaded) == {"country_code", "layers", "note"}
    assert loaded["layers"] == [{"path": "data:raw/a.tif"}]
    assert loaded["note"] == "https://example.org/a"  # a URL is not a machine path
    assert find_nondeterministic(loaded) == []


def test_a_path_inside_the_repository_becomes_repo_relative(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    out = _Output(
        country_code="ZZZ",
        timestamp="t",
        elapsed_total=0.0,
        report_path=None,
        layers=[_Inner(path=REPO_ROOT / "config" / "audit.yaml", timings={})],
    )
    assert json.loads(dump_artifact(out))["layers"][0]["path"] == "repo:config/audit.yaml"


def test_the_detector_finds_a_volatile_field_and_an_absolute_path():
    found = find_nondeterministic({"a": {"timestamp": "x"}, "b": ["D:\\data\\f.tif", "ok"]})
    assert any("timestamp" in f for f in found)
    assert any("D:\\data" in f for f in found)
