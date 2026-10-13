"""The members of the run, read from the `members` artifact of F4 (a table of who is who for the thesis outputs; no computation)."""

from __future__ import annotations

import pandas as pd
import yaml

from geofrea.results_synthesis.inputs import ArtifactReader

REFERENCE = "reference"


def members_table(reader: ArtifactReader) -> pd.DataFrame:
    """One row per member of `members.yaml`: `member`, `gcm`, `ssp`, `window` (the reference member has `window` `reference`)."""
    entries = yaml.safe_load(reader.path("members").read_text(encoding="utf-8"))["members"]
    return pd.DataFrame(
        {
            "member": [e["member"] for e in entries],
            "gcm": [e.get("gcm") for e in entries],
            "ssp": [e.get("ssp") for e in entries],
            "window": [REFERENCE if e.get("gcm") is None else str(e["window"]) for e in entries],
            "tcr_exception": [bool(e.get("tcr_exception", False)) for e in entries],
        }
    )
