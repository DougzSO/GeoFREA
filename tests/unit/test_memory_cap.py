"""The memory cap by phase (COMMAND 131, item 1; OQ-068, L-067): the numbers, the rule and its application by the peak sampler and the orchestrator."""

from __future__ import annotations

import json
import time

import pytest

from geofrea.core import memory_cap, orchestrator
from geofrea.core.memory_cap import (
    MemoryCapExceeded,
    PhaseCap,
    cap_from_peak,
    over_cap,
    phase_cap,
    verdict,
)
from geofrea.core.peak_memory import PhasePeak

pytestmark = pytest.mark.unit

MB = 2**20


def _cap(cap_mb: float = 1000.0, reserve_mb: float = 300.0) -> PhaseCap:
    return PhaseCap("p", cap_mb, cap_mb * 1.25, reserve_mb)


# -- the numbers ----------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("peak", "cap"),
    [(1579, 1984), (1676, 2112), (1018, 1280), (1207, 1536), (338, 448), (657, 832), (64, 128), (512, 640)],
)
def test_the_cap_is_125_percent_of_the_peak_rounded_up_to_64_mb(peak, cap):
    assert cap_from_peak(peak) == cap
    assert cap % 64 == 0 and cap >= 1.25 * peak and cap - 64 < 1.25 * peak


def test_every_cap_in_the_file_follows_the_formula_and_carries_its_date():
    rows = json.loads(memory_cap.BUDGET_FILE.read_text(encoding="utf-8"))["phase_caps"]["phases"]
    assert rows, "no phase has a cap"
    for phase, row in rows.items():
        assert row["cap_mb"] == cap_from_peak(row["peak_rss_mb"]), phase
        assert row["country"] == "BRA" and len(row["measured_on"]) == 10, phase


def test_the_peaks_of_command_129_are_the_ones_the_caps_come_from():
    assert phase_cap("technical_potential").measured_mb == 1579
    assert phase_cap("potential_maps").measured_mb == 1676
    assert phase_cap("technical_potential").cap_mb == 1984
    assert phase_cap("potential_maps").cap_mb == 2112
    rows = json.loads(memory_cap.BUDGET_FILE.read_text(encoding="utf-8"))["phase_caps"]["phases"]
    assert rows["technical_potential"]["other_countries_mb"] == {"IND": 1018, "PRT": 338}
    assert rows["potential_maps"]["other_countries_mb"]["IND"] == 1207


def test_a_phase_with_no_measurement_has_the_cap_of_the_file():
    cap = phase_cap("a_phase_that_never_ran")
    assert (cap.cap_mb, cap.source, cap.measured_mb) == (1536, "default", None)
    assert cap.hard_mb == pytest.approx(1536 * 1.25)


def test_the_phases_of_f6_to_f8_have_no_cap_of_their_own():
    for phase in ("robustness_analysis", "external_validation", "results_synthesis"):
        assert phase_cap(phase).source == "default", phase


# -- the rule -------------------------------------------------------------------------------------------------------------------------


def test_a_phase_within_its_cap_goes_on_whatever_the_free_memory():
    assert verdict(_cap(), 999, available_mb=0) is None


def test_a_phase_above_the_cap_goes_on_while_the_free_memory_covers_the_excess_and_the_reserve():
    assert verdict(_cap(), 1100, available_mb=100 + 300) is None
    assert "only 399 MB is free" in verdict(_cap(), 1100, available_mb=399)


def test_a_phase_above_the_hard_limit_stops_whatever_the_free_memory():
    assert "hard limit of 1250 MB" in verdict(_cap(), 1251, available_mb=10**6)
    assert verdict(_cap(), 1250, available_mb=10**6) is None


def test_the_excess_over_the_cap_is_none_when_within_and_the_difference_when_above():
    assert over_cap(_cap(), 1000) is None and over_cap(None, 5000) is None and over_cap(_cap(), None) is None
    assert over_cap(_cap(), 1234.56) == 234.6


# -- the sampler ----------------------------------------------------------------------------------------------------------------------


def _hold(sampler_mb: float, monkeypatch) -> None:
    from geofrea.core import peak_memory

    monkeypatch.setattr(peak_memory, "_current_and_peak_bytes", lambda _p: (int(sampler_mb * MB), int(sampler_mb * MB)))


def test_a_phase_over_the_hard_limit_is_stopped_with_the_reason(monkeypatch):
    _hold(1300, monkeypatch)
    peak = PhasePeak(interval_s=0.005, cap=_cap(), available_mb=lambda: 10**6)
    with pytest.raises(MemoryCapExceeded, match="hard limit of 1250 MB"), peak:
        for _ in range(400):
            time.sleep(0.01)
    assert peak.stopped_by_cap and peak.peak_rss_mb == pytest.approx(1300) and peak.peak_over_cap_mb == 300


def test_a_phase_between_the_cap_and_the_hard_limit_stops_only_when_the_free_memory_is_short(monkeypatch):
    _hold(1100, monkeypatch)
    with PhasePeak(interval_s=0.005, cap=_cap(), available_mb=lambda: 5000) as roomy:
        time.sleep(0.1)
    assert roomy.stopped_by_cap is None and roomy.peak_over_cap_mb == 100
    tight = PhasePeak(interval_s=0.005, cap=_cap(), available_mb=lambda: 350)
    with pytest.raises(MemoryCapExceeded, match="only 350 MB is free"), tight:
        for _ in range(400):
            time.sleep(0.01)


def test_a_phase_within_its_cap_is_not_touched_and_has_no_excess(monkeypatch):
    _hold(900, monkeypatch)
    with PhasePeak(interval_s=0.005, cap=_cap(), available_mb=lambda: 0) as peak:
        time.sleep(0.05)
    assert peak.stopped_by_cap is None and peak.peak_over_cap_mb is None and peak.peak_rss_mb == pytest.approx(900)


def test_without_a_cap_nothing_is_enforced_and_nothing_is_recorded(monkeypatch):
    _hold(9000, monkeypatch)
    with PhasePeak(interval_s=0.005) as peak:
        time.sleep(0.05)
    assert peak.stopped_by_cap is None and peak.peak_over_cap_mb is None


def test_a_stop_that_arrives_after_the_block_ended_is_not_raised(monkeypatch):
    # the sampler decides to stop, but the block has already closed: the owner thread must not get an exception later
    _hold(1300, monkeypatch)
    peak = PhasePeak(interval_s=10.0, cap=_cap(), available_mb=lambda: 10**6)
    with peak:
        pass
    peak._stop_phase("late")
    time.sleep(0.05)  # an exception delivered late would surface here
    assert peak.stopped_by_cap is None


# -- the orchestrator -----------------------------------------------------------------------------------------------------------------


def _phase_cap_of(cap_mb: float):
    return lambda name: PhaseCap(name, cap_mb, cap_mb * 1.25, 300.0, 100.0, "2026-01-01", "measured")


def _run_one(tmp_path, monkeypatch, *, caps: bool, cap_mb: float, hold_mb: float):
    from geofrea.core import peak_memory
    from tests.unit.test_orchestrator import _make_spec, _orchestrator

    spec = _make_spec("alpha", [])
    inner = spec.run

    def slow(context):
        for _ in range(60):  # long enough for the sampler to look at the process several times, and for a stop to be delivered
            time.sleep(0.005)
        return inner(context)

    object.__setattr__(spec, "run", slow)
    monkeypatch.setattr(orchestrator, "phase_cap", _phase_cap_of(cap_mb))
    monkeypatch.setattr(peak_memory, "_current_and_peak_bytes", lambda _p: (int(hold_mb * MB), int(hold_mb * MB)))
    monkeypatch.setattr(peak_memory.PhasePeak, "__init__", _fast_init(peak_memory.PhasePeak.__init__))
    o = _orchestrator(tmp_path, ["alpha"])
    o.memory_caps = caps
    o.run([spec])
    return o.manifest.phases["alpha"]


def _fast_init(original):
    def init(self, interval_s=0.005, cap=None, available_mb=lambda: 10**6):
        original(self, interval_s=0.005, cap=cap, available_mb=available_mb)

    return init


def test_the_manifest_records_the_cap_and_the_excess_of_a_phase_above_its_cap(tmp_path, monkeypatch):
    entry = _run_one(tmp_path, monkeypatch, caps=True, cap_mb=1000, hold_mb=1100)
    assert entry.status == "success" and entry.memory_cap_mb == 1000 and entry.peak_over_cap == 100


def test_a_phase_over_the_hard_limit_is_recorded_as_failed_with_its_peak(tmp_path, monkeypatch):
    entry = _run_one(tmp_path, monkeypatch, caps=True, cap_mb=1000, hold_mb=1300)
    assert entry.status == "failed" and "hard limit" in entry.error
    assert entry.peak_over_cap == 300 and entry.memory_cap_mb == 1000


def test_a_phase_within_its_cap_has_the_cap_and_no_excess(tmp_path, monkeypatch):
    entry = _run_one(tmp_path, monkeypatch, caps=True, cap_mb=1000, hold_mb=500)
    assert entry.status == "success" and entry.memory_cap_mb == 1000 and entry.peak_over_cap is None


def test_a_run_that_does_not_ask_for_caps_applies_none(tmp_path, monkeypatch):
    entry = _run_one(tmp_path, monkeypatch, caps=False, cap_mb=1000, hold_mb=5000)
    assert entry.status == "success" and entry.memory_cap_mb is None and entry.peak_over_cap is None


def test_main_applies_the_caps_unless_the_environment_switches_them_off(monkeypatch):
    """`main._run_geofrea` builds the orchestrator with `memory_caps` from `GEOFREA_MEMORY_CAPS` (default on; the test suite sets it to 0)."""
    import inspect

    import main

    source = inspect.getsource(main._run_geofrea)
    assert 'memory_caps=os.environ.get("GEOFREA_MEMORY_CAPS", "1") != "0"' in source
