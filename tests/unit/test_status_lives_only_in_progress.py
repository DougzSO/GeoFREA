"""Status lives only in docs/PROGRESS.json (CONVENTIONS, "Where status lives").

METHODOLOGY Section 12 and the comments of the config files carry no state term, and the phase records carry no status line. The list is closed and kept here. `parameters.json`
is out of scope: its `status` values are the verification vocabulary of one parameter, not the state of a phase, a country or a
milestone.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STATE_TERMS = re.compile(
    r"not started|in progress|\bbuilt\b|pending|state as of|not yet|not built|not implemented"
    r"|to be (?:built|implemented)|still to|currently|\bwip\b",
    re.IGNORECASE,
)


def state_terms(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in STATE_TERMS.finditer(text)})


def roadmap_section(methodology: str) -> str:
    start = methodology.index("## 12. Implementation roadmap")
    return methodology[start : methodology.index("## 13.", start)]


def yaml_comments(text: str) -> str:
    return "\n".join(line.split("#", 1)[1] for line in text.splitlines() if "#" in line)


def test_status_lives_only_in_progress():
    methodology = (REPO / "docs" / "METHODOLOGY.md").read_text(encoding="utf-8")
    found = {"METHODOLOGY section 12": state_terms(roadmap_section(methodology))}
    for path in sorted((REPO / "config").glob("*.yaml")):
        found[f"config/{path.name}"] = state_terms(yaml_comments(path.read_text(encoding="utf-8")))
    offenders = {where: terms for where, terms in found.items() if terms}
    assert not offenders, f"state belongs in docs/PROGRESS.json, not here: {offenders}"


def test_the_detector_flags_an_inserted_state_phrase():
    methodology = (REPO / "docs" / "METHODOLOGY.md").read_text(encoding="utf-8")
    assert state_terms(roadmap_section(methodology + "")) == []
    assert state_terms(yaml_comments("key: 1  # not started")) == ["not started"]
    assert state_terms(yaml_comments("# State as of 2026-10-08")) == ["state as of"]
    assert state_terms(
        roadmap_section("## 12. Implementation roadmap\n| MS-0 | x | in progress |\n## 13. x")
    ) == ["in progress"]


STATUS_LINE = re.compile(r"^\s*(?:\*\*)?(?:status|state)(?:\*\*)?\s*[:=]", re.IGNORECASE)


def status_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if STATUS_LINE.match(line)]


def test_phase_records_carry_no_status_line():
    offenders = {}
    for path in sorted((REPO / "docs" / "phases").glob("*.md")):
        found = status_lines(path.read_text(encoding="utf-8"))
        if found:
            offenders[path.name] = found
    assert not offenders, f"phase records record decisions, not status: {offenders}"


def test_the_status_line_detector_flags_the_forms_the_records_used():
    assert status_lines("Status: `in_progress`") == ["Status: `in_progress`"]
    assert status_lines("**Status:** built") == ["**Status:** built"]
    assert status_lines("  state: done") == ["  state: done"]
    assert status_lines("The status of the phase is recorded elsewhere.") == []
