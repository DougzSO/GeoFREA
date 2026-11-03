"""A cold audit or F2a is not started on a machine that cannot hold it (COMMAND 77, item 6 of the profile 76 list).

The cold rounds of IND died twice at the roads of the audit, without a traceback, with about 1 GB of memory available (docs/_audit/profile_76.md D), and
the peaks of the cold phases are 2.3 GB (F2a, PRT) to 3.9 GB (F2a, IND). `cold_start_shortfall` returns the message that explains why a run must not start,
or None. `main.py` checks it before any phase of a country begins, so nothing is written to the manifest and the process leaves with `EXIT_NOT_STARTED`
(a run that did not start, not a failure of the data or of a phase).

A phase is cold when its interim directory holds no file: nothing it kept from an earlier run can shorten it. The phases that are not named in the
run, and the phases that already have their interim files, are not checked.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)

MIN_AVAILABLE_GB = 1.5  # lowered from 2.0 by the author for the Group 3 round (CONVENTIONS, "Memory before a cold round")
COLD_GATED_PHASES = ("data_quality_audit", "grid_alignment")  # F1b and F2a
EXIT_NOT_STARTED = 75  # EX_TEMPFAIL: the run did not start and can be tried again


def available_gb() -> float:
    """Memory the system can give a process now, in GB (2**30 bytes)."""
    return psutil.virtual_memory().available / 2**30


def is_cold(interim_dir: Path) -> bool:
    """True when `interim_dir` does not exist or holds no file."""
    return not interim_dir.is_dir() or not any(p.is_file() for p in interim_dir.rglob("*"))


def cold_start_shortfall(
    country_code: str,
    target_phases: Iterable[str],
    interim_of,
    *,
    min_gb: float = MIN_AVAILABLE_GB,
    available: float | None = None,
) -> str | None:
    """Why the cold phases named in `target_phases` must not start now, or None.

    Args:
        country_code: Country whose interim directories are looked at.
        target_phases: The phases of the run.
        interim_of: `interim_of(country_code, phase) -> Path`, the interim directory of a phase (`core.paths.interim`).
        min_gb: Memory that has to be available, GB.
        available: Available memory, GB; read from the system when None.
    """
    cold = [p for p in COLD_GATED_PHASES if p in set(target_phases) and is_cold(Path(interim_of(country_code, p)))]
    if not cold:
        return None
    free = available_gb() if available is None else available
    if free >= min_gb:
        return None
    return (
        f"{country_code}: NOT STARTED. The cold phase(s) {', '.join(cold)} need at least {min_gb:g} GB of available memory and only {free:.1f} GB is "
        f"available. Close other programs (the browser, the editor) and run again; nothing was written and no phase failed."
    )


# ─── the guard between and during the layers of F2a and F2b (COMMAND 88, item 5) ────────────────────────────────────────────────────
#
# A layer starts only when the memory that is free covers the peak measured for it plus a margin; until then the run waits (it never ends a
# process to make room). The only thing that stops a layer is the commit charge of the system, physical memory and the paging file together,
# passing 95 % of its limit: a low figure of free physical memory alone is normal on a machine that pages and is not a reason to stop.

COMMIT_STOP_FRACTION = 0.95
MARGIN_MB = 300  # free memory wanted above the measured peak of a layer
WAIT_TIMEOUT_S = 1800.0
WAIT_POLL_S = 5.0


class MemoryWaitTimeout(RuntimeError):
    """The memory a layer needs did not become free within the timeout; the layer was not started and nothing was stopped."""


class CommitLimitExceeded(RuntimeError):
    """The commit charge of the system passed `COMMIT_STOP_FRACTION` of its limit."""


def commit_fraction() -> float:
    """Commit charge of the system over its limit (physical memory plus the paging file), 0 to 1.

    On Windows it is `CommitTotal / CommitLimit` of `GetPerformanceInfo`. Elsewhere the same ratio is built from psutil: the memory in use
    (total minus available) plus the swap in use, over the physical memory plus the swap.
    """
    if sys.platform == "win32":

        class _PerformanceInfo(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong)] + [
                (name, ctypes.c_size_t)
                for name in (
                    "CommitTotal",
                    "CommitLimit",
                    "CommitPeak",
                    "PhysicalTotal",
                    "PhysicalAvailable",
                    "SystemCache",
                    "KernelTotal",
                    "KernelPaged",
                    "KernelNonpaged",
                    "PageSize",
                )
            ] + [("HandleCount", ctypes.c_ulong), ("ProcessCount", ctypes.c_ulong), ("ThreadCount", ctypes.c_ulong)]

        info = _PerformanceInfo()
        info.cb = ctypes.sizeof(info)
        if ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(info), info.cb) and info.CommitLimit:
            return info.CommitTotal / info.CommitLimit
    memory, swap = psutil.virtual_memory(), psutil.swap_memory()
    return ((memory.total - memory.available) + swap.used) / (memory.total + swap.total)


@dataclass
class WaitLog:
    """What the guard did before a layer: each wait with its reason, and how long the layer waited in all."""

    layer: str
    needed_mb: float
    waits: list[str] = field(default_factory=list)
    waited_s: float = 0.0


def wait_for_memory(
    layer: str,
    peak_mb: float,
    *,
    margin_mb: float = MARGIN_MB,
    timeout_s: float = WAIT_TIMEOUT_S,
    poll_s: float = WAIT_POLL_S,
    available_mb: Callable[[], float] = lambda: psutil.virtual_memory().available / 2**20,
    commit: Callable[[], float] = commit_fraction,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> WaitLog:
    """Wait until the free memory is at least `peak_mb + margin_mb`; log every wait with its reason.

    Raises:
        CommitLimitExceeded: the commit charge is over `COMMIT_STOP_FRACTION` (waiting would not help a machine that is out of commit).
        MemoryWaitTimeout: the memory did not become free within `timeout_s`. Nothing is stopped; the caller does not start the layer.
    """
    needed = peak_mb + margin_mb
    log = WaitLog(layer=layer, needed_mb=needed)
    start = clock()
    while True:
        used = commit()
        if used > COMMIT_STOP_FRACTION:
            raise CommitLimitExceeded(f"{layer}: the commit charge is {used:.0%} of the limit (stop above {COMMIT_STOP_FRACTION:.0%})")
        free = available_mb()
        log.waited_s = clock() - start
        if free >= needed:
            if log.waits:
                logger.info("    %s: starts after %.0f s; %.0f MB free, %.0f MB needed.", layer, log.waited_s, free, needed)
            return log
        if log.waited_s >= timeout_s:
            raise MemoryWaitTimeout(
                f"{layer}: waited {log.waited_s:.0f} s for {needed:.0f} MB free (peak {peak_mb:.0f} MB + {margin_mb:.0f} MB) and only {free:.0f} MB is; "
                f"the layer was not started and nothing was stopped"
            )
        reason = f"{free:.0f} MB free, {needed:.0f} MB needed (measured peak {peak_mb:.0f} MB + {margin_mb:.0f} MB); commit {used:.0%}"
        log.waits.append(reason)
        logger.info("    %s: waiting for memory: %s.", layer, reason)
        sleep(poll_s)
