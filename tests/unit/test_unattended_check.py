"""scripts/unattended_check.py compares an unattended round with the manifest saved before it (COMMAND 78)."""

from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "unattended_check.py"


def _load():
    spec = importlib.util.spec_from_file_location("unattended_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest(artifacts: dict[str, tuple[str, str]], configs: dict[str, str] | None = None, wall: float = 100.0) -> dict:
    phases = {}
    for _, (phase, _) in artifacts.items():
        phases.setdefault(
            phase,
            {
                "status": "success",
                "config_fingerprint": (configs or {}).get(phase, "c0"),
                "wall_s": wall,
                "cpu_s": 90.0,
                "peak_rss_mb": 512.4,
                "started_at": "2026-10-30T03:00:00+00:00",
                "finished_at": "2026-10-30T03:01:40+00:00",
            },
        )
    return {
        "phases": phases,
        "artifacts": {k: {"phase": ph, "sha256": "bytes-" + h, "content_sha256": h} for k, (ph, h) in artifacts.items()},
    }


def test_identical_hashes_give_an_identical_verdict():
    uc = _load()
    m = _manifest({"a": ("F2a", "h1"), "b": ("F3", "h2")})
    report = uc.build_report("PRT", m, m, None, [])
    assert report["verdict"] == "IDENTICO" and report["n_identico"] == 2 and not report["different"]


def test_a_changed_hash_is_reported_with_whether_the_configuration_changed():
    uc = _load()
    before = _manifest({"a": ("F2a", "h1"), "w": ("F5", "h2")}, {"F5": "exact"})
    after = _manifest({"a": ("F2a", "h1x"), "w": ("F5", "h2x")}, {"F5": "table"})
    report = uc.build_report("BRA", before, after, None, [])
    assert report["verdict"] == "DIFERENTE"
    assert report["different_unexplained"] == ["a"] and report["different_with_config_change"] == ["w"]


def test_content_hash_decides_and_the_byte_hash_is_the_fallback():
    uc = _load()
    before = {"phases": {"p": {}}, "artifacts": {"x": {"phase": "p", "sha256": "same", "content_sha256": "c1"}, "y": {"phase": "p", "sha256": "b1"}}}
    after = {"phases": {"p": {}}, "artifacts": {"x": {"phase": "p", "sha256": "other-bytes", "content_sha256": "c1"}, "y": {"phase": "p", "sha256": "b2"}}}
    rows = uc.compare_artifacts(before, after)
    assert rows["x"]["status"] == "IDENTICO" and rows["y"]["status"] == "DIFERENTE"


def test_artifacts_that_appear_or_vanish_are_named():
    uc = _load()
    before = _manifest({"gone": ("F3", "h"), "kept": ("F3", "k")})
    after = _manifest({"kept": ("F3", "k"), "fresh": ("F3", "n")})
    rows = uc.compare_artifacts(before, after)
    assert rows["gone"]["status"] == "AUSENTE_DEPOIS" and rows["fresh"]["status"] == "AUSENTE_ANTES"


def test_an_aborted_round_is_not_called_identical():
    uc = _load()
    m = _manifest({"a": ("F2a", "h1")})
    assert uc.build_report("IND", m, m, None, [], aborted="available memory 310 MB")["verdict"] == "ABORTADO"


def test_awake_time_is_the_wall_time_less_the_sleep_inside_the_phase():
    uc = _load()
    m = _manifest({"a": ("F2a", "h1")}, wall=100.0)
    started = uc._local("2026-10-30T03:00:00+00:00")
    # one sleep that covers 30 s of the phase and 50 s before it
    sleeps = [(datetime.fromtimestamp(started.timestamp() - 50), datetime.fromtimestamp(started.timestamp() + 30))]
    row = uc.phase_table(m, ["F2a"], sleeps)[0]
    assert row["slept_s"] == 30.0 and row["awake_s"] == 70.0 and row["peak_rss_mb"] == 512


def test_only_the_phases_that_finished_since_the_start_of_the_round_count():
    uc = _load()
    old = _manifest({"a": ("F2a", "h1")})
    old["phases"]["F2a"]["finished_at"] = "2026-10-29T00:00:00+00:00"
    report = uc.build_report("PRT", old, old, None, [], started="2026-10-30T00:00:00+00:00")
    assert report["n_artifacts"] == 0 and report["phases"] == []


def test_the_sleep_intervals_are_read_from_the_exported_events(tmp_path):
    uc = _load()
    path = tmp_path / "power.json"
    path.write_text(
        '{"sleep_wake": [{"t": "2026-10-30 01:00:00", "id": 42}], "resume": [{"t": "2026-10-30 01:20:00", "id": 1}]}', encoding="utf-8"
    )
    assert uc.load_sleeps(path) == [(datetime(2026, 10, 30, 1, 0), datetime(2026, 10, 30, 1, 20))]
    assert uc.load_sleeps(tmp_path / "missing.json") == []
