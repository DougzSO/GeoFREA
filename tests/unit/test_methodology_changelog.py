"""METHODOLOGY change protocol (Section 0): every item changed since the last version is named in the last changelog line.

The baseline is the METHODOLOGY file as it was before the commit that introduced the current version (or `HEAD` when the version
bump is not committed yet). An item is changed when any line it owns differs: its title line and the sub-bullets or continuation
lines below it, until the next title or heading. Item titles are bullets such as `- **M-F5-03.**` or `- **A-04. Registry.**` and
table rows that start with an ID such as `| T-R1 |`. Lines owned by no item (prose, the header table, the changelog itself)
are not checked here. The test is skipped outside a git checkout or when the history does not hold the baseline.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
METHODOLOGY = REPO / "docs" / "METHODOLOGY.md"
REL = "docs/METHODOLOGY.md"

_BULLET_ID = re.compile(r"^\s*[-*]\s+\*\*([A-Z]{1,3}(?:-[A-Za-z0-9]+)+?)\.?[\s*]")
_ROW_ID = re.compile(r"^\|\s*([A-Z]{1,3}-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)\s*\|")
_VERSION = re.compile(r"^\| Version \| (\d+\.\d+\.\d+) \|", re.MULTILINE)
_CHANGELOG_ROW = re.compile(r"^\| (\d+\.\d+\.\d+) \| (\d{4}-\d{2}-\d{2}) \|", re.MULTILINE)


def _owner_of_each_line(text: str) -> list[tuple[str, str | None]]:
    """`(line, item ID or None)` for every line; a heading ends the item, the changelog owns nothing."""
    owner: str | None = None
    in_changelog = False
    out = []
    for line in text.split("\n"):
        if line.startswith("#"):
            in_changelog = line.strip().lower().endswith("changelog")
            owner = None
        match = _BULLET_ID.match(line) or _ROW_ID.match(line)
        if match and not in_changelog:
            owner = match.group(1)
        out.append((line, None if in_changelog else owner))
    return out


def changed_item_ids(old: str, new: str) -> set[str]:
    """IDs of the items that own at least one line present in only one of the two texts."""
    old_lines, new_lines = _owner_of_each_line(old), _owner_of_each_line(new)
    old_set, new_set = {line for line, _ in old_lines}, {line for line, _ in new_lines}
    changed = {o for line, o in new_lines if o and line not in old_set and line.strip()}
    changed |= {o for line, o in old_lines if o and line not in new_set and line.strip()}
    return changed


def last_changelog_row(text: str) -> str:
    match = _CHANGELOG_ROW.search(text)
    assert match, "the changelog has no version row"
    return text[match.start() : text.index("\n", match.start())]


def missing_from_changelog(old: str, new: str) -> list[str]:
    row = last_changelog_row(new)
    return sorted(
        i
        for i in changed_item_ids(old, new)
        if not re.search(rf"(?<![\w-]){re.escape(i)}(?![\w-])", row)
    )


def _git(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False
        )
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def baseline_text(current: str) -> str | None:
    """The METHODOLOGY before the commit that introduced the current version; HEAD's when that bump is uncommitted."""
    version = _VERSION.search(current).group(1)
    log = _git("log", "--format=%H", f"-S| Version | {version} |", "--", REL)
    if log is None:
        return None
    introducing = [c for c in log.split() if c]
    if not introducing:
        return _git("show", f"HEAD:{REL}")
    return _git("show", f"{introducing[-1]}^:{REL}")


# -- the checker itself ----------------------------------------------------------------------------

OLD = """# Doc

| Version | 1.0.0 |

## 5. Phases

- **M-F5-01.** Capacity.
- **M-F5-03.** Wind capacity factor:
  - Hub height from the registry.
  - Weibull integral.
- **M-F5-04.** Loss.

## 9. Files

| File | Content |
|---|---|
| T-R1 | Figure | one |

## 14. Changelog

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-01-01 | first |
"""


@pytest.mark.unit
def test_changed_ids_include_sub_bullets_rows_and_removed_lines():
    new = OLD.replace("  - Weibull integral.", "  - Exact Weibull integral.").replace(
        "| T-R1 | Figure | one |", "| T-R1 | Figure | two |"
    )
    assert changed_item_ids(OLD, new) == {"M-F5-03", "T-R1"}
    removed = OLD.replace("- **M-F5-04.** Loss.\n", "")
    assert changed_item_ids(OLD, removed) == {"M-F5-04"}


@pytest.mark.unit
def test_unchanged_text_and_changelog_edits_change_no_item():
    assert changed_item_ids(OLD, OLD) == set()
    edited = OLD.replace(
        "| 1.0.0 | 2026-01-01 | first |",
        "| 1.0.1 | 2026-02-01 | M-F5-01 reworded |\n| 1.0.0 | 2026-01-01 | first |",
    )
    assert changed_item_ids(OLD, edited) == set()


@pytest.mark.unit
def test_an_item_missing_from_the_last_changelog_row_is_reported():
    new = OLD.replace("- **M-F5-01.** Capacity.", "- **M-F5-01.** Capacity per cell.").replace(
        "| 1.0.0 | 2026-01-01 | first |",
        "| 1.0.1 | 2026-02-01 | M-F5-010 and T-R1 reworded |\n| 1.0.0 | 2026-01-01 | first |",
    )
    assert missing_from_changelog(OLD, new) == [
        "M-F5-01"
    ]  # M-F5-010 is another ID: no prefix match
    fixed = new.replace("M-F5-010 and", "M-F5-01 and")
    assert missing_from_changelog(OLD, fixed) == []


# -- the real document -----------------------------------------------------------------------------


@pytest.mark.unit
def test_header_version_and_date_match_the_last_changelog_row():
    text = METHODOLOGY.read_text(encoding="utf-8")
    row = _CHANGELOG_ROW.search(text)
    assert _VERSION.search(text).group(1) == row.group(1)
    assert re.search(rf"^\| Updated \| {row.group(2)} \|", text, re.MULTILINE)


@pytest.mark.unit
def test_every_item_changed_since_the_last_version_is_in_the_last_changelog_row():
    current = METHODOLOGY.read_text(encoding="utf-8").replace("\r\n", "\n")
    baseline = baseline_text(current)
    if baseline is None:
        pytest.skip("no git history that holds the previous METHODOLOGY version")
    missing = missing_from_changelog(baseline.replace("\r\n", "\n"), current)
    assert not missing, (
        f"items changed since the previous version but absent from its changelog row: {missing}"
    )
