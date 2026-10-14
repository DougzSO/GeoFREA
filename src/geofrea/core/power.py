"""Keep the computer awake while a long run is going (V-T; METHODOLOGY A-02 records the wall and CPU time of each phase).

On 2026-10-08 the F4 of India logged 27,764 s in a phase that needs about 140 s: Windows suspended the computer 31 s after the phase started and
resumed it 7 h 40 min later (docs/_audit/2026-10_data_diagnostics.md, section 6). On Windows `keep_awake` asks the system, through
`SetThreadExecutionState`, not to suspend while the context is open; on any other system it does nothing.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager

logger = logging.getLogger(__name__)

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def _set_execution_state(flags: int) -> int:
    """`SetThreadExecutionState(flags)` of kernel32; returns the previous state, 0 if the call failed."""
    return int(ctypes.windll.kernel32.SetThreadExecutionState(ctypes.c_uint(flags)))  # type: ignore[attr-defined]


@contextmanager
def keep_awake() -> Iterator[bool]:
    """Prevent the system from suspending while the block runs; yields True when the request was made (Windows only).

    The state belongs to the calling thread, so the block must run on it. The previous state is restored on exit.
    """
    if not sys.platform.startswith("win"):
        yield False
        return
    try:
        granted = _set_execution_state(ES_CONTINUOUS | ES_SYSTEM_REQUIRED) != 0
    except (AttributeError, OSError):  # pragma: no cover - ctypes without windll
        granted = False
    if granted:
        logger.info(
            "System suspension is blocked for the duration of the run (SetThreadExecutionState)."
        )
    else:
        logger.warning(
            "Could not block system suspension; a long run may be suspended by the operating system."
        )
    try:
        yield granted
    finally:
        if granted:
            _set_execution_state(ES_CONTINUOUS)
