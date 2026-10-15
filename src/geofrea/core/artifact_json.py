"""Deterministic JSON for registered artifacts.

The content of a registered artifact holds no timestamp, no run time and no absolute machine path: the same inputs give the same bytes, so
the artifact hash changes only when the result changes and a consumer is not invalidated by a rerun that reproduces its inputs (A-02).
The volatile fields stay in the phase output that the manifest entry records; absolute paths become `<root>:<relative path>`
(`data`, `legacy_baseline`, or `repo` for a path inside the repository).
"""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePath
from typing import Any

from pydantic import BaseModel

from geofrea.core import paths

# Names of fields that describe the run, not the result, at any depth of an artifact.
VOLATILE_FIELDS = frozenset(
    {
        "timestamp",
        "started_at",
        "finished_at",
        "elapsed_total",
        "elapsed_s",
        "timings",
        "report_path",
    }
)
REPO_ROOT = Path(__file__).resolve().parents[3]
_ABSOLUTE = re.compile(r"^(?:[A-Za-z]:[\\/]|/)")


def _portable(value: str) -> str:
    """`value` as `<root>:<relative>` when it is an absolute path under a known root; unchanged otherwise."""
    if not _ABSOLUTE.match(value) or "://" in value:
        return value
    path = Path(value)
    try:
        stored = paths.to_stored_path(path)
        return f"{stored.root}:{stored.rel}"
    except (ValueError, OSError, paths.MissingPathEnvironmentError):
        pass
    try:
        return f"repo:{path.resolve().relative_to(REPO_ROOT).as_posix()}"
    except ValueError:
        return value


def deterministic(value: Any) -> Any:
    """`value` without volatile fields and with absolute paths made portable, recursively."""
    if isinstance(value, dict):
        return {k: deterministic(v) for k, v in value.items() if k not in VOLATILE_FIELDS}
    if isinstance(value, (list, tuple)):
        return [deterministic(v) for v in value]
    if isinstance(value, PurePath):
        return _portable(str(value))
    if isinstance(value, str):
        return _portable(value)
    return value


def dump_artifact(output: BaseModel) -> str:
    """JSON text of a phase output as a registered artifact: stable key order, no volatile field, portable paths."""
    return (
        json.dumps(deterministic(output.model_dump(mode="json")), indent=2, sort_keys=True) + "\n"
    )


def find_nondeterministic(value: Any, where: str = "") -> list[str]:
    """Locations in a loaded artifact that hold a volatile field or an absolute path (for tests)."""
    found: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            if k in VOLATILE_FIELDS:
                found.append(f"{where}/{k}")
            found += find_nondeterministic(v, f"{where}/{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            found += find_nondeterministic(v, f"{where}[{i}]")
    elif isinstance(value, str) and _ABSOLUTE.match(value) and "://" not in value:
        found.append(f"{where} = {value}")
    return found
