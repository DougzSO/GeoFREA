"""The memory a layer of F2a or F2b needs, measured (COMMAND 88, items 0 and 5).

`config/memory_budget.json` holds the peak resident memory measured for each kind of layer on the largest country (BRA), in MB, and the cap every
layer must stay under. Before a layer starts, the guard waits until that peak plus a margin is free (`memory_guard.wait_for_memory`); the budget
test runs the heaviest layer on a raster the size of BRA and fails above the cap.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

BUDGET_FILE = Path(__file__).resolve().parents[3] / "config" / "memory_budget.json"
CAP_MB = 1536  # 1.5 GB per process


@cache
def _load(path: str) -> dict:
    file = Path(path)
    return json.loads(file.read_text(encoding="utf-8")) if file.is_file() else {}


def peak_mb(kind: str, path: Path = BUDGET_FILE) -> float | None:
    """The measured peak (MB) of the layer kind `kind` ("population", "glo30", "wind"...), or None when none was measured."""
    row = _load(str(path)).get("layers", {}).get(kind)
    return None if row is None else float(row["peak_rss_mb"])


def cap_mb(path: Path = BUDGET_FILE) -> float:
    """The cap per process, MB."""
    return float(_load(str(path)).get("cap_mb", CAP_MB))
