"""State of a download that writes to a temporary name first."""

from __future__ import annotations

from pathlib import Path
from typing import Literal


def is_complete_download(
    final_path: Path, tmp_path: Path
) -> Literal["complete", "partial", "absent"]:
    """Distinguish a finished download from a crashed/partial one.

    A live download always writes to `tmp_path` (suffix `.part.nc`) and is renamed to `final_path` only after the
    request returns successfully (`fetchers/cmip6.py`, `fetchers/era5.py`). A `.part.nc` left on disk (process
    killed mid-transfer) is never treated as complete and is never registered.
    """
    if final_path.exists():
        return "complete"
    if tmp_path.exists():
        return "partial"
    return "absent"
