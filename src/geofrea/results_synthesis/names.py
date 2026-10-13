"""File names of the thesis outputs (CONVENTIONS, "Artifacts and outputs"; D-F8-003).

`T-<id>_<what>_<ISO3>_<tech>.<ext>`, for example `T-R4_max_regret_BRA_solar.png`. A cross-country output has no country and an output
that is not per technology has no technology. A table is written as `.csv` and `.tex`, a figure as `.png` and `.pdf`, and each output
has a `<stem>.provenance.json` beside it.
"""

from __future__ import annotations

import re

THESIS_IDS = (
    "T-M1", "T-M2", "T-M3",
    "T-R1", "T-R2", "T-R3", "T-R4", "T-R5", "T-R6", "T-R7", "T-R8", "T-R9", "T-R10", "T-R11", "T-R12",
    "T-O1", "T-O2", "T-O3",
)  # fmt: skip
OPTIONAL = frozenset({"T-O1", "T-O2"})  # METHODOLOGY Section 10: every other output is Essential
_WHAT = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")


class OutputNameError(ValueError):
    """A name that does not follow the rule."""


def stem(t_id: str, what: str, iso: str | None = None, technology: str | None = None) -> str:
    """The name of an output without extension.

    Raises:
        OutputNameError: `t_id` is not one of Section 10, or `what` is not lower-case words joined by underscores.
    """
    if t_id not in THESIS_IDS:
        raise OutputNameError(f"{t_id!r} is not a thesis output of METHODOLOGY Section 10")
    if not _WHAT.match(what):
        raise OutputNameError(f"{what!r}: use lower-case words joined by underscores")
    parts = [t_id, what]
    if iso:
        parts.append(iso)
    if technology:
        parts.append(technology)
    return "_".join(parts)
