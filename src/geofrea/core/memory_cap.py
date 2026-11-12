"""The memory a phase may hold, by phase (COMMAND 131, item 1; OQ-068, L-067).

Until COMMAND 131 the 1,536 MB cap of `config/memory_budget.json` bound only the layer processes of F2a and F2b (`core.layer_process` waits for the
measured peak of a layer plus a margin) and the test of the heaviest layers; a phase that ran in the main process was only measured
(`core.peak_memory`), so `hazard_context`, `climate_maps` and `overview` could hold 2 to 2.7 GB on BRA without anything noticing. This module gives each
phase its own cap and the rule that applies it:

* cap of a phase = ceil(1.25 x the peak measured on the largest country) rounded up to a multiple of 64 MB, written with the date of the
  measurement under `phase_caps.phases` in `config/memory_budget.json`. A phase with no entry has the cap of the file (`cap_mb`, 1,536 MB).
* up to 25 % above the cap the phase goes on, as long as the memory the system has free covers the excess plus a reserve
  (`phase_caps.over_cap_reserve_mb`); the excess is written to the manifest as `peak_over_cap`.
* at `cap x 1.25` (the hard limit), or when the free memory does not cover the excess and the reserve, the phase is stopped: `MemoryCapExceeded` is
  raised in the thread that runs it and the orchestrator records the phase as failed, as for any other error.

The caps bind the runs of `main.py` and not the tests; `GEOFREA_MEMORY_CAPS=0` in the environment switches them off for a run (the measurement and `peak_rss_mb` stay).

Limits, stated: the memory read is the working set of the whole process (what the manifest has always recorded), sampled every 0.25 s, so a phase that starts in a process that earlier phases of the same run have grown carries that memory into its figure (the peaks the caps come from were measured in runs of one or a few phases: a first full BRA chain in one process is the test of whether the caps leave room for it); the
exception is delivered at the next Python instruction of the phase, so a long call into C code (a GDAL warp, a Parquet write) ends first; a phase that
finishes before the stop is delivered is not failed (its result is complete) and carries `peak_over_cap` and a warning. The module changes no result
and it is outside every code fingerprint: only `core.orchestrator` and `core.peak_memory` import it and the closures do not enter them. It is not in
`INFRASTRUCTURE_MODULES` on purpose: that frozenset is reachable from the function fingerprint of the aligned layers (through `cache_code`), so
editing it would change those keys (checked in COMMAND 131); adding it is an item of the window.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from geofrea.core.memory_budget import BUDGET_FILE, CAP_MB

CAP_FACTOR = 1.25  # cap = ceil(CAP_FACTOR x measured peak)
ROUND_MB = 64  # ... rounded up to a multiple of this
HARD_FACTOR = 1.25  # hard limit = cap x HARD_FACTOR
DEFAULT_RESERVE_MB = 300.0  # free memory wanted beyond the excess while a phase is above its cap (same margin as the layer guard)


class MemoryCapExceeded(RuntimeError):
    """A phase went past its memory cap and the rule stopped it (hard limit, or not enough free memory for the excess and the reserve)."""


@dataclass(frozen=True)
class PhaseCap:
    """The cap of one phase and where it comes from.

    Attributes:
        phase: Phase name.
        cap_mb: Cap, MB.
        hard_mb: Hard limit, MB (cap x 1.25).
        reserve_mb: Free memory wanted beyond the excess while the phase is above its cap, MB.
        measured_mb: The peak the cap comes from, MB; None when the phase has no measurement.
        measured_on: Date of that measurement (ISO), or None.
        source: "measured" or "default".
    """

    phase: str
    cap_mb: float
    hard_mb: float
    reserve_mb: float
    measured_mb: float | None = None
    measured_on: str | None = None
    source: str = "default"


def cap_from_peak(peak_mb: float) -> int:
    """ceil(1.25 x peak) rounded up to a multiple of 64 MB."""
    return int(math.ceil(CAP_FACTOR * peak_mb / ROUND_MB) * ROUND_MB)


@cache
def _load(path: str) -> dict:
    file = Path(path)
    return json.loads(file.read_text(encoding="utf-8")) if file.is_file() else {}


def phase_cap(phase: str, path: Path = BUDGET_FILE) -> PhaseCap:
    """The cap of `phase`: its measured one, or the cap of the file (1,536 MB) when the phase has none."""
    data = _load(str(path))
    block = data.get("phase_caps", {})
    reserve = float(block.get("over_cap_reserve_mb", DEFAULT_RESERVE_MB))
    row = block.get("phases", {}).get(phase)
    if row is None:
        cap = float(data.get("cap_mb", CAP_MB))
        return PhaseCap(phase, cap, cap * HARD_FACTOR, reserve)
    cap = float(row["cap_mb"])
    return PhaseCap(phase, cap, cap * HARD_FACTOR, reserve, float(row["peak_rss_mb"]), row.get("measured_on"), "measured")


def verdict(cap: PhaseCap, current_mb: float, available_mb: float) -> str | None:
    """Why a phase holding `current_mb` must stop, or None when it may go on.

    Args:
        cap: The cap of the phase.
        current_mb: Memory the process holds now, MB.
        available_mb: Memory the system has free now, MB.
    """
    if current_mb > cap.hard_mb:
        return f"{cap.phase}: holds {current_mb:.0f} MB, above the hard limit of {cap.hard_mb:.0f} MB (cap {cap.cap_mb:.0f} MB x {HARD_FACTOR:g})"
    if current_mb > cap.cap_mb:
        excess = current_mb - cap.cap_mb
        if available_mb < excess + cap.reserve_mb:
            return (
                f"{cap.phase}: holds {current_mb:.0f} MB, {excess:.0f} MB above its cap of {cap.cap_mb:.0f} MB, and only {available_mb:.0f} MB is free "
                f"(the excess plus a reserve of {cap.reserve_mb:.0f} MB is {excess + cap.reserve_mb:.0f} MB)"
            )
    return None


def over_cap(cap: PhaseCap | None, peak_mb: float | None) -> float | None:
    """The excess of `peak_mb` over the cap, MB (rounded to 0.1), or None when there is no cap, no peak, or the peak is within the cap."""
    if cap is None or peak_mb is None or peak_mb <= cap.cap_mb:
        return None
    return round(peak_mb - cap.cap_mb, 1)
