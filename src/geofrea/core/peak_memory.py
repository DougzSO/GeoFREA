"""Peak resident memory of a phase (manifest 2.7, A-02).

The operating system keeps one peak per process, not one per phase. On Windows `peak_wset` is the highest working set the process ever had;
a phase that raises it has its own peak, which is that value exactly. A phase that stays below the peak of an earlier phase cannot be read
from it, so a sampler thread also records the highest working set it sees while the phase runs (every `SAMPLE_INTERVAL_S`); the peak of the
phase is the OS value when the phase raised it and the sampled maximum otherwise (a lower bound: a spike shorter than the interval can be
missed). Memory of child processes is not counted. Nothing here changes a result.

With a `PhaseCap` (`core.memory_cap`, COMMAND 131) the sampler also applies the cap of the phase: when the rule says the phase must stop, it raises
`MemoryCapExceeded` in the thread that entered the block (`PyThreadState_SetAsyncExc`: delivered at the next Python instruction of that thread).
"""

from __future__ import annotations

import ctypes
import logging
import threading
from collections.abc import Callable
from types import TracebackType
from typing import Self

import psutil

from geofrea.core.memory_cap import MemoryCapExceeded, PhaseCap, over_cap, verdict

logger = logging.getLogger(__name__)

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

    def __init__(
        self,
        interval_s: float = SAMPLE_INTERVAL_S,
        cap: PhaseCap | None = None,
        available_mb: Callable[[], float] = lambda: psutil.virtual_memory().available / _MB,
    ) -> None:
        self._interval_s = interval_s
        self.cap = cap
        self._available_mb = available_mb
        self._lock = threading.Lock()
        self._closed = False
        self._owner: int | None = None
        self.stopped_by_cap: str | None = None  # the reason, when the rule stopped the phase
        self.peak_over_cap_mb: float | None = None  # excess of the peak over the cap, MB; None when within it (or no cap)
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
            if self.cap is not None and self.stopped_by_cap is None:
                reason = verdict(self.cap, current / _MB, self._available_mb())
                if reason is not None:
                    self._stop_phase(reason)

    def _stop_phase(self, reason: str) -> None:
        """Raise `MemoryCapExceeded(reason)` in the owner thread, once, unless the block has already ended."""
        message = reason

        class _Stop(MemoryCapExceeded):
            def __init__(self) -> None:
                super().__init__(message)

        with self._lock:
            if self._closed or self._owner is None:
                return
            self.stopped_by_cap = reason
            logger.error("Memory cap: %s; stopping the phase.", reason)
            ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(self._owner), ctypes.py_object(_Stop))

    def __enter__(self) -> Self:
        self._owner = threading.get_ident()
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
        with self._lock:
            self._closed = True
            if self.stopped_by_cap is not None and exc_type is None:
                # the stop was not delivered before the phase ended (a long call into C code): the result is complete, so it is kept
                ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(self._owner or 0), None)
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        current, end_peak = _current_and_peak_bytes(self._process)
        self._sampled = max(self._sampled, current)
        os_peak = end_peak if end_peak > self._start_peak else 0
        self.peak_rss_mb = max(os_peak, self._sampled) / _MB
        self.peak_over_cap_mb = over_cap(self.cap, self.peak_rss_mb)
        if self.peak_over_cap_mb is not None and exc_type is None:
            logger.warning(
                "Memory cap: %s peaked at %.0f MB, %.0f MB above its cap of %.0f MB%s.",
                self.cap.phase if self.cap else "?",
                self.peak_rss_mb,
                self.peak_over_cap_mb,
                self.cap.cap_mb if self.cap else 0,
                " (a stop was raised but the phase ended first)" if self.stopped_by_cap else "",
            )
