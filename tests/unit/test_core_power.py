"""V-T: `keep_awake` blocks the suspension of the computer while a run is going (Windows) and does nothing elsewhere."""

from __future__ import annotations

import pytest

from geofrea.core import power


@pytest.mark.unit
def test_on_windows_the_system_is_kept_awake_inside_the_block_and_the_state_is_restored_after(
    monkeypatch,
):
    calls: list[int] = []
    monkeypatch.setattr(power.sys, "platform", "win32")
    monkeypatch.setattr(power, "_set_execution_state", lambda flags: calls.append(flags) or 1)

    with power.keep_awake() as granted:
        assert granted is True
        assert calls == [power.ES_CONTINUOUS | power.ES_SYSTEM_REQUIRED]
    assert calls == [power.ES_CONTINUOUS | power.ES_SYSTEM_REQUIRED, power.ES_CONTINUOUS]


@pytest.mark.unit
def test_the_state_is_restored_when_the_block_raises(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(power.sys, "platform", "win32")
    monkeypatch.setattr(power, "_set_execution_state", lambda flags: calls.append(flags) or 1)

    with pytest.raises(RuntimeError), power.keep_awake():
        raise RuntimeError("a phase failed")

    assert calls[-1] == power.ES_CONTINUOUS


@pytest.mark.unit
def test_a_refused_request_is_warned_and_nothing_is_restored(monkeypatch, caplog):
    calls: list[int] = []
    monkeypatch.setattr(power.sys, "platform", "win32")
    monkeypatch.setattr(power, "_set_execution_state", lambda flags: calls.append(flags) or 0)

    with caplog.at_level("WARNING"), power.keep_awake() as granted:
        assert granted is False

    assert len(calls) == 1 and "Could not block system suspension" in caplog.text


@pytest.mark.unit
def test_on_other_systems_nothing_is_called(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(power.sys, "platform", "linux")
    monkeypatch.setattr(power, "_set_execution_state", lambda flags: calls.append(flags) or 1)

    with power.keep_awake() as granted:
        assert granted is False

    assert calls == []


@pytest.mark.unit
def test_main_runs_inside_keep_awake(monkeypatch):
    import main

    events: list[str] = []

    class Recorder:
        def __enter__(self):
            events.append("enter")

        def __exit__(self, *exc):
            events.append("exit")
            return False

    monkeypatch.setattr(main, "keep_awake", lambda: Recorder())
    monkeypatch.setattr(main, "_main", lambda argv=None: events.append("run") or 0)

    assert main.main([]) == 0
    assert events == ["enter", "run", "exit"]
