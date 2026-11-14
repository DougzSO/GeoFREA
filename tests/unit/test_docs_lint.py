"""The docs lint (`scripts/lint_docs.py`): it passes on the repository and each check fails on a minimal case.

IDs are built by concatenation so that this file cites no ID of its own.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("lint_docs", REPO / "scripts" / "lint_docs.py")
lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint)

D1 = "D-" + "F9-001"
D2 = "D-" + "F9-002"
M1 = "M-" + "F9-01"
HEADER = lint.CONFORMANCE_HEADER


def write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def checks(root: Path) -> set[str]:
    return {f[0] for f in lint.run_checks(root)}


GOOD = {
    "docs/phases/F9_x.md": f"- **{D1} — A decision (2026-01-01).** Text.\n\n## Conformance\n\n{HEADER}\n|---|---|---|---|---|\n",
    "docs/METHODOLOGY.md": f"- **{M1}.** A rule.\n",
    "docs/OPEN_QUESTIONS.md": "| OQ-001 | F9 | Q | P | Douglas | open |\n",
    "src/m.py": f"def real_function():\n    pass  # {M1} and {D1}\n",
    "tests/unit/test_real.py": "def test_a_real_test():\n    pass\n",
}


def test_the_repository_passes_the_lint():
    assert lint.run_checks(REPO) == []


def test_the_minimal_clean_tree_passes(tmp_path):
    write(tmp_path, GOOD)
    assert lint.run_checks(tmp_path) == []


def test_ids_fail_when_a_cited_id_is_defined_nowhere(tmp_path):
    write(tmp_path, GOOD | {"docs/note.md": f"See {D2}.\n"})
    assert checks(tmp_path) == {"ids"}


def test_ids_fail_when_an_id_is_cited_in_code_and_defined_nowhere(tmp_path):
    write(tmp_path, GOOD | {"src/other.py": "# " + "M-" + "F9-77\n"})
    assert checks(tmp_path) == {"ids"}


def test_ids_fail_when_an_id_is_defined_twice(tmp_path):
    write(tmp_path, GOOD | {"docs/phases/F9_y.md": f"- **{D1} — Again (2026-01-02).** Text.\n"})
    assert checks(tmp_path) == {"ids"}


def test_paths_fail_when_a_cited_path_does_not_exist(tmp_path):
    write(tmp_path, GOOD | {"docs/note.md": "See `src/nope.py` and `src/m.py`.\n"})
    failures = lint.run_checks(tmp_path)
    assert {f[0] for f in failures} == {"paths"}
    assert "src/nope.py" in failures[0][3]


def test_tests_fail_when_a_cited_test_name_does_not_exist(tmp_path):
    write(
        tmp_path, GOOD | {"docs/note.md": "Test `test_a_real_test` and `test_that_is_not_there`.\n"}
    )
    failures = lint.run_checks(tmp_path)
    assert {f[0] for f in failures} == {"tests"}
    assert len(failures) == 1


def test_tests_fail_when_a_double_colon_name_is_not_defined(tmp_path):
    write(
        tmp_path,
        GOOD | {"docs/note.md": "`src/m.py::real_function` and `src/m.py::gone_function`.\n"},
    )
    failures = lint.run_checks(tmp_path)
    assert {f[0] for f in failures} == {"tests"}
    assert "gone_function" in failures[0][3]


def test_lines_fail_on_a_citation_with_a_line_number(tmp_path):
    write(tmp_path, GOOD | {"docs/note.md": "See `src/m.py:12`.\n"})
    assert checks(tmp_path) == {"lines"}


def decisions_text(n_entries: int, bad_position: int | None = None, replaces: str = "") -> str:
    out = ["# DECISIONS", "", "## [data] DEC-nnn - template", "Substitui: DEC-nnn", "", "---", ""]
    for pos in range(1, n_entries + 1):
        label = f"DEC-{pos:03d}" if pos >= lint.FIRST_DEC_WITH_ID else ""
        if pos == bad_position:
            label = f"DEC-{pos + 1:03d}"
        out += [f"## [2026-01-01] {label} - entry {pos}", "Tipo: STRUCTURAL_PRESERVE"]
        if pos == n_entries and replaces:
            out.append(f"Substitui: {replaces}")
        out.append("")
    return "\n".join(out)


def test_decisions_pass_when_the_ids_follow_the_position(tmp_path):
    write(tmp_path, GOOD | {"docs/DECISIONS.md": decisions_text(61, replaces="DEC-005 (a phrase)")})
    assert lint.run_checks(tmp_path) == []


def test_decisions_fail_when_a_header_id_is_out_of_order(tmp_path):
    write(tmp_path, GOOD | {"docs/DECISIONS.md": decisions_text(61, bad_position=60)})
    assert checks(tmp_path) == {"decisions"}


def test_decisions_fail_when_a_substitui_names_a_missing_decision(tmp_path):
    write(tmp_path, GOOD | {"docs/DECISIONS.md": decisions_text(61, replaces="DEC-099 (nothing)")})
    assert checks(tmp_path) == {"decisions"}


def test_open_questions_fail_on_a_status_outside_the_three_values(tmp_path):
    write(
        tmp_path, GOOD | {"docs/OPEN_QUESTIONS.md": "| OQ-001 | F9 | Q | P | Douglas | closed |\n"}
    )
    assert checks(tmp_path) == {"open_questions"}


@pytest.mark.parametrize("status", lint.OQ_STATUSES)
def test_open_questions_accept_each_of_the_three_values(tmp_path, status):
    write(
        tmp_path,
        GOOD | {"docs/OPEN_QUESTIONS.md": f"| OQ-001 | F9 | Q | P | Douglas | {status} |\n"},
    )
    assert lint.run_checks(tmp_path) == []


def test_conformance_fails_when_the_header_differs_between_phases(tmp_path):
    other = "| Item | Requirement | Status |"
    write(tmp_path, GOOD | {"docs/phases/F9_y.md": f"## Conformance\n\n{other}\n|---|---|---|\n"})
    assert checks(tmp_path) == {"conformance"}


def test_a_marker_on_the_line_exempts_that_line(tmp_path):
    write(tmp_path, GOOD | {"docs/note.md": "See `src/nope.py:3`. <!-- lint: skip -->\n"})
    assert lint.run_checks(tmp_path) == []


def test_a_marker_alone_exempts_the_lines_up_to_the_next_blank_line(tmp_path):
    text = "<!-- lint: skip -->\nSee `src/nope.py`.\nAnd `src/gone.py`.\n\nBut `src/third.py` is not exempt.\n"
    write(tmp_path, GOOD | {"docs/note.md": text})
    failures = lint.run_checks(tmp_path)
    assert [f[2] for f in failures] == [5]


@pytest.mark.parametrize("folder", ["docs/_audit", "docs/_archive/2026-11", "docs/thesis"])
def test_the_exempt_folders_are_not_checked(tmp_path, folder):
    write(
        tmp_path,
        GOOD | {f"{folder}/note.md": f"See `src/nope.py:3`, {D2} and `test_that_is_not_there`.\n"},
    )
    assert lint.run_checks(tmp_path) == []


def test_the_output_counts_the_lines_exempted_by_the_marker(tmp_path, capsys):
    marker = "<!-- lint: skip -->"
    text = f"{marker}\nSee `src/nope.py`.\nAnd `src/gone.py`.\n\nPlain line. {marker}\n"
    write(tmp_path, GOOD | {"docs/note.md": text, "docs/_audit/x.md": f"{marker}\nx\n"})
    assert lint.main(tmp_path) == 0
    out = capsys.readouterr().out
    assert "skipped    4 line(s) in docs/note.md" in out
    assert "skipped    4 line(s) in 1 file(s), in total" in out
    assert "_audit" not in out


def test_the_output_counts_zero_when_there_is_no_marker(tmp_path, capsys):
    write(tmp_path, GOOD)
    assert lint.main(tmp_path) == 0
    assert "skipped    0 line(s) in 0 file(s), in total" in capsys.readouterr().out
