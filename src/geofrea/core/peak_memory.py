"""Peak resident memory of a phase (manifest 2.7, A-02).

The operating system keeps one peak per process, not one per phase. On Windows `peak_wset` is the highest working set the process ever had;
a phase that raises it has its own peak, which is that value exactly. A phase that stays below the peak of an earlier phase cannot be read
from it, so a sampler thread also records the highest working set it sees while the phase runs (every `SAMPLE_INTERVAL_S`); the peak of the
phase is the OS value when the phase raised it and the sampled maximum otherwise (a lower bound: a spike shorter than the interval can be
missed). Memory of child processes is not counted. Nothing here changes a result.
"""

from __future__ import annotations

import threading
from types import TracebackType
from typing import Self

import psutil

SAMPLE_INTERVAL_S = 0.25
_MB = 1024 * 1024


def _current_and_peak_bytes(process: psutil.Process) -> tuple[int, int]:
    """(resident set now, highest resident set of the process so far), bytes; the peak is the current value where the OS reports none."""
    info = process.memory_info()
    peak = getattr(info, "peak_wset", None)
    return info.rss, int(peak) if peak is not None else info.rss


class PhasePeak:
    """Context manager measuring the peak resident memory of the code run inside it.

    Attributes:
        peak_rss_mb: Peak resident memory of the process during the block, MB (1 MB = 2**20 bytes); None until the block ends.
    """

    def __init__(self, interval_s: float = SAMPLE_INTERVAL_S) -> None:
        self._interval_s = interval_s
        self._process = psutil.Process()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_peak = 0
        self._sampled = 0
        self.peak_rss_mb: float | None = None

    def _sample(self) -> None:
        while not self._stop.wait(self._interval_s):
            current, _ = _current_and_peak_bytes(self._process)
            self._sampled = max(self._sampled, current)

    def __enter__(self) -> Self:
        current, self._start_peak = _current_and_peak_bytes(self._process)
        self._sampled = current
        self._thread = threading.Thread(target=self._sample, name="phase-peak", daemon=True)
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        current, end_peak = _current_and_peak_bytes(self._process)
        self._sampled = max(self._sampled, current)
        os_peak = end_peak if end_peak > self._start_peak else 0
        self.peak_rss_mb = max(os_peak, self._sampled) / _MB
