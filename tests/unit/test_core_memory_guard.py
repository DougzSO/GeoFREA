"""COMMAND 77: a cold audit or F2a is not started without 2 GB of available memory."""

from __future__ import annotations

import contextlib

import pytest

from geofrea.core.memory_guard import (
    COLD_GATED_PHASES,
    MIN_AVAILABLE_GB,
    cold_start_shortfall,
    is_cold,
)

pytestmark = pytest.mark.unit

PHASES = ["data_acquisition", *COLD_GATED_PHASES, "land_eligibility"]


def _interim(tmp_path, warm: tuple[str, ...] = ()):
    for phase in warm:
        d = tmp_path / "PRT" / phase
        d.mkdir(parents=True)
        (d / "cache.gpkg").write_bytes(b"x")

    return lambda country, phase: tmp_path / country / phase


def test_a_cold_run_with_too_little_memory_does_not_start_and_says_why(tmp_path):
    message = cold_start_shortfall("PRT", PHASES, _interim(tmp_path), available=1.2)
    assert message is not None
    assert "NOT STARTED" in message and "data_quality_audit" in message and "grid_alignment" in message
    assert f"{MIN_AVAILABLE_GB:g} GB" in message and "1.2 GB" in message and "no phase failed" in message


def test_enough_memory_lets_a_cold_run_start(tmp_path):
    assert cold_start_shortfall("PRT", PHASES, _interim(tmp_path), available=2.0) is None


def test_phases_with_their_interim_files_are_not_cold(tmp_path):
    interim = _interim(tmp_path, warm=("data_quality_audit", "grid_alignment"))
    assert cold_start_shortfall("PRT", PHASES, interim, available=0.5) is None


def test_only_the_cold_phase_is_named(tmp_path):
    interim = _interim(tmp_path, warm=("data_quality_audit",))
    message = cold_start_shortfall("PRT", PHASES, interim, available=0.5)
    assert "grid_alignment" in message and "data_quality_audit" not in message


def test_phases_that_are_not_in_the_run_are_not_checked(tmp_path):
    assert cold_start_shortfall("PRT", ["land_eligibility", "overview"], _interim(tmp_path), available=0.1) is None


def test_an_empty_or_missing_directory_is_cold(tmp_path):
    (tmp_path / "empty").mkdir()
    assert is_cold(tmp_path / "empty") and is_cold(tmp_path / "missing")
    (tmp_path / "empty" / "sub").mkdir()
    assert is_cold(tmp_path / "empty")  # a directory without a file
    (tmp_path / "empty" / "sub" / "f").write_bytes(b"1")
    assert not is_cold(tmp_path / "empty")


def test_main_leaves_with_the_not_started_code_before_any_phase(monkeypatch):
    import main
    from geofrea.core.memory_guard import EXIT_NOT_STARTED

    monkeypatch.setattr(main, "cold_start_shortfall", lambda *a, **k: "PRT: NOT STARTED. test")
    monkeypatch.setattr(main, "keep_awake", contextlib.nullcontext)
    monkeypatch.setattr(main, "_keep_awake_enabled", lambda: False)
    monkeypatch.setattr(main, "run_geofrea", lambda *a, **k: pytest.fail("a phase started"))
    assert main.main(["PRT", "--phases", "data_quality_audit,grid_alignment"]) == EXIT_NOT_STARTED


# ─── COMMAND 88, item 5: wait for the memory a layer needs; stop only on the commit charge ───────────────────────────────────────────

from geofrea.core.memory_guard import (
    COMMIT_STOP_FRACTION,
    CommitLimitExceeded,
    MemoryWaitTimeout,
    commit_fraction,
    wait_for_memory,
)


class _Clock:
    def __init__(self):
        self.now = 0.0

    def sleep(self, seconds):
        self.now += seconds

    def __call__(self):
        return self.now


def test_the_layer_starts_at_once_when_the_peak_plus_the_margin_is_free():
    clock = _Clock()
    log = wait_for_memory("population", 1000, available_mb=lambda: 1400, commit=lambda: 0.5, sleep=clock.sleep, clock=clock)
    assert log.waits == [] and log.needed_mb == 1300


def test_the_layer_waits_for_memory_and_logs_each_wait_with_its_reason():
    clock = _Clock()
    free = iter([500, 800, 1200, 1400])
    log = wait_for_memory("population", 1000, available_mb=lambda: next(free), commit=lambda: 0.5, sleep=clock.sleep, clock=clock, poll_s=5)
    assert len(log.waits) == 3 and log.waited_s == 15
    assert "500 MB free, 1300 MB needed" in log.waits[0] and "measured peak 1000 MB" in log.waits[0]


def test_a_wait_that_times_out_does_not_start_the_layer_and_ends_nothing():
    clock = _Clock()
    with pytest.raises(MemoryWaitTimeout, match="not started and nothing was stopped"):
        wait_for_memory("population", 1000, available_mb=lambda: 100, commit=lambda: 0.5, sleep=clock.sleep, clock=clock, timeout_s=30, poll_s=5)
    assert clock.now >= 30


def test_low_physical_memory_with_a_paging_file_to_spare_only_waits_it_does_not_stop():
    clock = _Clock()
    free = iter([100, 100, 2000])  # physical memory is low, the commit charge is not
    wait_for_memory("roads", 500, available_mb=lambda: next(free), commit=lambda: 0.60, sleep=clock.sleep, clock=clock)


def test_a_commit_charge_over_95_percent_stops_the_run_before_the_layer():
    clock = _Clock()
    with pytest.raises(CommitLimitExceeded, match="95%"):
        wait_for_memory("roads", 500, available_mb=lambda: 5000, commit=lambda: COMMIT_STOP_FRACTION + 0.01, sleep=clock.sleep, clock=clock)


def test_the_commit_fraction_is_a_share_of_the_limit():
    assert 0.0 < commit_fraction() < 1.0
