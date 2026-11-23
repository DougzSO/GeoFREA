"""Registry of the human-readable phase names (COMMAND 200; `config/phases.yaml`).

The id of a phase is the name the code uses (`PhaseSpec.name`, the manifests, the artifact folders) and never changes. The registry adds a
short code, an English name and a group, for the plan, the log, the docs tables and the future platform. The file is not
in any phase's configuration fingerprint, so editing a name never makes a phase run again.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

REGISTRY_FILE = Path(__file__).resolve().parents[3] / "config" / "phases.yaml"


@dataclass(frozen=True)
class PhaseInfo:
    """One entry of `config/phases.yaml`."""

    id: str
    code: str | None
    name_en: str
    group: str
    orchestrated: bool = True


@cache
def load_registry(path: Path = REGISTRY_FILE) -> tuple[PhaseInfo, ...]:
    """The entries of the registry in execution order.

    Raises:
        ValueError: an entry lacks a field, or an id is repeated.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries: list[PhaseInfo] = []
    seen: set[str] = set()
    for row in raw["phases"]:
        missing = {"id", "name_en", "group"} - set(row)
        if missing:
            raise ValueError(f"{path.name}: entry {row.get('id', row)!r} lacks {sorted(missing)}")
        if row["id"] in seen:
            raise ValueError(f"{path.name}: id {row['id']!r} is repeated")
        seen.add(row["id"])
        entries.append(
            PhaseInfo(
                id=row["id"],
                code=row.get("code"),
                name_en=row["name_en"],
                group=row["group"],
                orchestrated=row.get("orchestrated", True),
            )
        )
    return tuple(entries)


def phase_info(phase_id: str) -> PhaseInfo | None:
    """The entry of `phase_id`, or None for an id the registry does not list (a fixture phase of a test)."""
    return next((e for e in load_registry() if e.id == phase_id), None)


def phase_label(phase_id: str) -> str:
    """The English name of the phase for a message, or the id itself when the registry does not list it."""
    info = phase_info(phase_id)
    return info.name_en if info else phase_id


def validate_against(spec_names: set[str] | frozenset[str] | list[str]) -> None:
    """Check that the orchestrated entries of the registry are exactly the registered `PhaseSpec` names.

    Raises:
        ValueError: a PhaseSpec has no entry, or an orchestrated entry has no PhaseSpec.
    """
    names = set(spec_names)
    orchestrated = {e.id for e in load_registry() if e.orchestrated}
    missing = sorted(names - orchestrated)
    extra = sorted(orchestrated - names)
    if missing or extra:
        raise ValueError(f"phases.yaml and the PhaseSpecs differ: no entry for {missing}; no PhaseSpec for {extra}")
