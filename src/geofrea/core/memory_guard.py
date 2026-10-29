"""A cold audit or F2a is not started on a machine that cannot hold it (COMMAND 77, item 6 of the profile 76 list).

The cold rounds of IND died twice at the roads of the audit, without a traceback, with about 1 GB of memory available (docs/_audit/profile_76.md D), and
the peaks of the cold phases are 2.3 GB (F2a, PRT) to 3.9 GB (F2a, IND). `cold_start_shortfall` returns the message that explains why a run must not start,
or None. `main.py` checks it before any phase of a country begins, so nothing is written to the manifest and the process leaves with `EXIT_NOT_STARTED`
(a run that did not start, not a failure of the data or of a phase).

A phase is cold when its interim directory holds no file: nothing it kept from an earlier run can shorten it. The phases that are not named in the
run, and the phases that already have their interim files, are not checked.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import psutil

MIN_AVAILABLE_GB = 2.0  # CONVENTIONS, "Memory before a cold round"
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
