"""Peak resident memory of a phase (manifest 2.7)."""

from __future__ import annotations

import time

import numpy as np
import pytest

from geofrea.core import peak_memory
from geofrea.core.peak_memory import PhasePeak

pytestmark = pytest.mark.unit

MB = 2**20


def test_the_peak_is_none_until_the_block_ends_and_then_a_positive_number_of_mb():
    peak = PhasePeak(interval_s=0.01)
    assert peak.peak_rss_mb is None
    with peak:
        assert peak.peak_rss_mb is None
    assert peak.peak_rss_mb is not None and peak.peak_rss_mb > 10


def test_a_block_that_holds_a_large_array_reports_at_least_its_size():
    with PhasePeak(interval_s=0.01) as peak:
        block = np.ones(80 * MB // 8)  # 80 MB, touched
        block += 1.0
        total = float(block.sum())
    assert total > 0
    assert peak.peak_rss_mb >= 80


def test_the_peak_is_the_sampled_maximum_when_the_phase_stays_below_the_process_peak(monkeypatch):
    # (resident set, process peak): the process peak of an earlier phase never rises during this one
    readings = iter([(100 * MB, 900 * MB), (400 * MB, 900 * MB)])
    monkeypatch.setattr(
        peak_memory, "_current_and_peak_bytes", lambda _p: next(readings, (200 * MB, 900 * MB))
    )
    with PhasePeak(interval_s=0.001) as peak:
        time.sleep(0.05)
    assert peak.peak_rss_mb == pytest.approx(400)


def test_the_peak_is_the_os_value_when_the_phase_raised_it(monkeypatch):
    readings = iter([(100 * MB, 300 * MB)])
    monkeypatch.setattr(
        peak_memory, "_current_and_peak_bytes", lambda _p: next(readings, (150 * MB, 700 * MB))
    )
    with PhasePeak(interval_s=10.0) as peak:
        pass
    assert peak.peak_rss_mb == pytest.approx(700)


def test_an_exception_in_the_block_propagates_and_the_peak_is_still_recorded():
    peak = PhasePeak(interval_s=0.01)
    with pytest.raises(RuntimeError), peak:
        raise RuntimeError("phase failed")
    assert peak.peak_rss_mb is not None
