"""COMMAND 88, items 1 and 5: a layer runs in a child process, and the guard waits for memory instead of ending anything."""

from __future__ import annotations

import pytest

from geofrea.core import layer_process, memory_guard
from geofrea.core.layer_process import LayerFailedError, LayerRecord, append_ledger, run_layer

pytestmark = pytest.mark.unit

ECHO = "geofrea.core.layer_process:selftest_echo"


@pytest.fixture
def child_mode(monkeypatch):
    monkeypatch.delenv(layer_process.IN_PROCESS_ENV, raising=False)


def test_a_layer_runs_in_another_process_and_returns_its_value(child_mode, tmp_path):
    value, record = run_layer("echo", ECHO, {"value": {"a": [1, 2]}}, work_dir=tmp_path)
    assert value == {"a": [1, 2]}
    assert record.status == "ok" and record.wall_s > 0 and record.peak_rss_mb > 0


def test_the_child_peak_is_what_the_child_held_not_the_parent(child_mode, tmp_path):
    _, small = run_layer("small", ECHO, {"megabytes": 0}, work_dir=tmp_path)
    _, big = run_layer("big", ECHO, {"megabytes": 200}, work_dir=tmp_path)
    assert big.peak_rss_mb > small.peak_rss_mb + 100


def test_a_failing_layer_raises_with_the_traceback_tail_and_leaves_no_file(child_mode, tmp_path):
    with pytest.raises(LayerFailedError, match="no_such_function"):
        run_layer("bad", "geofrea.core.layer_process:no_such_function", {}, work_dir=tmp_path)
    assert not list(tmp_path.iterdir())  # the payload and the result of the child are removed


def test_the_commit_limit_ends_the_child_and_says_so(child_mode, tmp_path, monkeypatch):
    monkeypatch.setattr(memory_guard, "commit_fraction", lambda: 0.99)
    with pytest.raises(memory_guard.CommitLimitExceeded, match="child was ended"):
        run_layer("over", ECHO, {"megabytes": 0}, work_dir=tmp_path)


def test_low_free_physical_memory_alone_does_not_stop_a_running_child(child_mode, tmp_path, monkeypatch):
    monkeypatch.setattr(memory_guard, "commit_fraction", lambda: 0.40)
    monkeypatch.setattr("psutil.virtual_memory", lambda: type("M", (), {"available": 50 * 2**20})())
    value, _ = run_layer("squeezed", ECHO, {"value": 7}, work_dir=tmp_path)  # no peak given: no wait before the start either
    assert value == 7


def test_in_process_mode_calls_the_function_in_this_process(monkeypatch, tmp_path):
    monkeypatch.setenv(layer_process.IN_PROCESS_ENV, "1")
    value, record = run_layer("echo", ECHO, {"value": 3}, work_dir=tmp_path)
    assert value == 3 and record.status == "ok"


def test_the_ledger_is_replaced_atomically_and_keeps_every_row(tmp_path):
    path = tmp_path / "x" / "layers.json"
    append_ledger(path, [LayerRecord(layer="a", status="ok", peak_rss_mb=10.0)])
    append_ledger(path, [LayerRecord(layer="a", status="ok", peak_rss_mb=10.0), LayerRecord(layer="b", status="failed", detail="boom")])
    import json

    rows = json.loads(path.read_text(encoding="utf-8"))
    assert [r["layer"] for r in rows] == ["a", "b"] and rows[1]["detail"] == "boom"
    assert not list(path.parent.glob("*.tmp"))


def test_work_folders_left_by_a_killed_run_are_removed_when_the_layer_starts_again(tmp_path):
    stale = tmp_path / "layer_echo_abc123"
    stale.mkdir()
    (stale / "payload.pkl").write_bytes(b"x" * 100)
    other = tmp_path / "layer_echo_notes"  # no payload: not a work folder of ours
    other.mkdir()
    assert layer_process.remove_stale_work_dirs("echo", tmp_path) == 1
    assert not stale.exists() and other.exists()
    assert layer_process.remove_stale_work_dirs("echo", None) == 0
