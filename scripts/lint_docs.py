"""Lint of the documents: the clean repository is the floor, there is no baseline.

    python scripts/lint_docs.py

Exit status 0 when every check passes, 1 otherwise; each failure is printed as `check file:line message`.

Checks (the active documents are the text files of `docs/` except `docs/DECISIONS.md`, `docs/_audit/`,
`docs/_archive/` and `docs/thesis/`):

* ids: every `D-*` and `M-*` cited in `src`, `tests`, `scripts`, `config` and the active documents is defined
  (`D-*` in `docs/phases/`, `M-*` in `docs/METHODOLOGY.md`), and none is defined twice;
* paths: a path with the prefix `config/`, `docs/`, `src/`, `tests/`, `scripts/` or `.github/` cited in an
  active document exists;
* tests: a `test_*` name and a `file::name` cited in an active document exist;
* lines: no `file.py:NNN` in an active document (a line number breaks at the next edit; cite the symbol);
* decisions: in `docs/DECISIONS.md` the `DEC-nnn` IDs of the headers follow the position of the header from
  DEC-059 on, and every `Substitui:` names an existing DEC;
* open_questions: the status of each row of `docs/OPEN_QUESTIONS.md` is one of the three values;
* conformance: the header of the Conformance table is the same in every phase record.

Exemptions: `docs/DECISIONS.md` (except the `decisions` check), `docs/_audit/`, `docs/_archive/`, `docs/thesis/`,
and the lines marked `<!-- lint: skip -->`: a marker on a line exempts that line; a marker alone on a line
exempts the lines that follow it up to the next blank line. In a Python file the marker goes in a comment.
At the end the lint prints the number of lines exempted by the marker, per file and in total.
"""

from __future__ import annotations

import re
import sys
import time
from collections.abc import Iterable, Iterator
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("src", "tests", "scripts", "config", "docs", ".github")
TEXT_SUFFIXES = {".md", ".py", ".yml", ".yaml", ".json", ".txt", ".toml"}
SKIP_PARTS = {"__pycache__", ".git", ".venv", "node_modules", "outputs"}
EXCLUDED_DOCS = ("docs/DECISIONS.md", "docs/_audit/", "docs/_archive/", "docs/thesis/")
PATH_PREFIXES = ("config/", "docs/", "src/", "tests/", "scripts/", ".github/")
OQ_STATUSES = ("open", "research_in_progress", "awaiting_verdict")
CONFORMANCE_HEADER = "| Item | Requirement | Implementation (module:function) | Test | Status |"
FIRST_DEC_WITH_ID = 59

SELF_FILES = ("scripts/lint_docs.py", "tests/unit/test_docs_lint.py")
MARKER = re.compile(r"<!--\s*lint:\s*skip\s*-->")
ID_PATTERN = r"(?:D-(?:F\d+[ab]?|E\d+[ab]?|core)-\d{1,3}|M-(?:F\d+[ab]?|E\d+)-\d{1,3}[a-z]?)"
ID_TOKEN = re.compile(r"(?<![\w\-])(" + ID_PATTERN + r")(?![\w\-])")
DEF_LINE = re.compile(r"^\s*(?:[-*+]\s+|#{1,6}\s+|\|\s*)?\**\s*(" + ID_PATTERN + r")(?![\w\-])")
PATH_TOKEN = re.compile(
    r"(?<![\w/.\-*])((?:[\w.\-]+/)*[\w.\-]+\.(?:py|md|tex|yaml|yml|bib|toml|sh|json|csv))(?![\w/\-])"
)
TEST_TOKEN = re.compile(r"(?<![\w.])(test_[A-Za-z0-9_]+)(?![\w.]*\.py)(?!\w)")
DOUBLE_COLON = re.compile(r"((?:[\w.\-]+/)*[\w.\-]+\.py)::([A-Za-z_]\w*)")
LINE_CITE = re.compile(
    r"(?<![\w/.\-])((?:[\w.\-]+/)*[\w.\-]+\.(?:py|md|tex|yaml|yml|json|toml|sh|bib)):(\d+)(?:[-–](\d+))?(?!\d)"
)
RESOLVE_BASES = ("", "src/geofrea/", "src/", "tests/unit/", "tests/", "scripts/", "docs/")

Failure = tuple[str, str, int, str]  # (check, file, line, message)


def is_active_doc(rel: str) -> bool:
    return (
        rel.startswith("docs/")
        and not rel.startswith(EXCLUDED_DOCS)
        and Path(rel).suffix in TEXT_SUFFIXES
    )


def load(root: Path) -> dict[str, str]:
    """The text files of the directories the lint reads, keyed by their path relative to `root`."""
    corpus: dict[str, str] = {}
    for d in SOURCE_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if (
                p.suffix.lower() not in TEXT_SUFFIXES
                or not p.is_file()
                or SKIP_PARTS & set(p.parts)
            ):
                continue
            rel = p.relative_to(root).as_posix()
            if rel.startswith("docs/_audit/2026-11_docs_audit/") or p.stat().st_size > 3_000_000:
                continue
            corpus[rel] = p.read_text(encoding="utf-8", errors="replace")
    return corpus


def skipped_lines(text: str) -> set[int]:
    """Numbers (1-based) of the lines a `<!-- lint: skip -->` marker exempts."""
    skipped: set[int] = set()
    in_block = False
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            in_block = False
            continue
        if MARKER.search(line):
            skipped.add(n)
            if not MARKER.sub("", line).strip(" #"):
                in_block = True
            continue
        if in_block:
            skipped.add(n)
    return skipped


def _lines(
    corpus: dict[str, str], files: Iterable[str], skip: bool = True
) -> Iterator[tuple[str, int, str]]:
    for rel in files:
        text = corpus[rel]
        skipped = skipped_lines(text) if skip else set()
        for n, line in enumerate(text.splitlines(), 1):
            if n not in skipped:
                yield rel, n, line


def check_ids(corpus: dict[str, str]) -> list[Failure]:
    defs: dict[str, list[tuple[str, int]]] = {}
    sources = [r for r in corpus if r.startswith("docs/phases/") or r == "docs/METHODOLOGY.md"]
    for rel, n, line in _lines(corpus, sources, skip=False):
        m = DEF_LINE.match(line)
        if not m:
            continue
        i = m.group(1)
        if (i.startswith("D-") and rel.startswith("docs/phases/")) or (
            i.startswith("M-") and rel == "docs/METHODOLOGY.md"
        ):
            defs.setdefault(i, []).append((rel, n))
    out: list[Failure] = []
    for i, where in sorted(defs.items()):
        if len(where) > 1:
            out.append(
                (
                    "ids",
                    where[0][0],
                    where[0][1],
                    f"{i} is defined {len(where)} times: "
                    + ", ".join(f"{f}:{n}" for f, n in where),
                )
            )
    cited_in = [
        r
        for r in corpus
        if r.split("/")[0] in ("src", "tests", "scripts", "config") or is_active_doc(r)
    ]
    for rel, n, line in _lines(corpus, cited_in):
        out.extend(
            ("ids", rel, n, f"{m.group(1)} is cited and defined nowhere")
            for m in ID_TOKEN.finditer(line)
            if m.group(1) not in defs
        )
    return out


def _resolve_file(root: Path, cited: str) -> list[str]:
    """Repository paths a `file.py` of a citation may name (a path that is not found as written matches by suffix)."""
    found = [b + cited for b in RESOLVE_BASES if (root / (b + cited)).is_file()]
    if found:
        return found
    name = Path(cited).name
    return [
        p.relative_to(root).as_posix()
        for d in ("src", "tests", "scripts")
        if (root / d).is_dir()
        for p in (root / d).rglob(name)
        if p.as_posix().endswith("/" + cited) or "/" not in cited
    ]


def check_paths(corpus: dict[str, str], root: Path) -> list[Failure]:
    out: list[Failure] = []
    for rel, n, line in _lines(corpus, [r for r in corpus if is_active_doc(r)]):
        for m in PATH_TOKEN.finditer(line):
            p = m.group(1).rstrip(".")
            if (
                not p.startswith(PATH_PREFIXES)
                or any(c in p for c in "<>{}*$%")
                or "…" in line[max(0, m.start() - 1) : m.end() + 1]
            ):
                continue
            if not (root / p).exists():
                out.append(("paths", rel, n, f"{p} does not exist"))
    return out


def _defines(text: str, name: str) -> bool:
    return bool(
        re.search(
            r"^\s*(?:async\s+)?(?:def|class)\s+" + re.escape(name) + r"\b", text, re.MULTILINE
        )
        or re.search(r"^\s*" + re.escape(name) + r"\s*(?::[^=\n]+)?=", text, re.MULTILINE)
    )


def check_tests(corpus: dict[str, str], root: Path) -> list[Failure]:
    test_defs: set[str] = set()
    for rel, text in corpus.items():
        if rel.startswith(("tests/", "scripts/")):
            test_defs.update(
                re.findall(r"^\s*(?:async\s+)?def (test_\w+)", text, flags=re.MULTILINE)
            )
    out: list[Failure] = []
    for rel, n, line in _lines(corpus, [r for r in corpus if is_active_doc(r)]):
        for m in TEST_TOKEN.finditer(line):
            name = m.group(1)
            if len(name) >= 8 and not name.endswith("_") and name not in test_defs:
                out.append(("tests", rel, n, f"{name} is not a test of the repository"))
        for m in DOUBLE_COLON.finditer(line):
            files = _resolve_file(root, m.group(1))
            if not files:
                out.append(
                    ("tests", rel, n, f"{m.group(1)} does not exist (cited with ::{m.group(2)})")
                )
                continue
            texts = (
                corpus[f]
                if f in corpus
                else (root / f).read_text(encoding="utf-8", errors="replace")
                for f in files
            )
            if not any(_defines(t, m.group(2)) for t in texts):
                out.append(("tests", rel, n, f"{m.group(2)} is not defined in {m.group(1)}"))
    return out


def check_lines(corpus: dict[str, str]) -> list[Failure]:
    return [
        ("lines", rel, n, f"{m.group(0)}: cite the symbol, not the line")
        for rel, n, line in _lines(corpus, [r for r in corpus if is_active_doc(r)])
        for m in LINE_CITE.finditer(line)
    ]


def check_decisions(corpus: dict[str, str]) -> list[Failure]:
    text = corpus.get("docs/DECISIONS.md")
    if text is None:
        return []
    lines = text.splitlines()
    sep = next((i for i, line in enumerate(lines) if line.strip() == "---"), -1)
    headers = [(i + 1, line) for i, line in enumerate(lines) if i > sep and line.startswith("## ")]
    out: list[Failure] = []
    for pos, (n, line) in enumerate(headers, 1):
        m = re.search(r"\bDEC-(\d+)\b", line)
        if pos >= FIRST_DEC_WITH_ID and (not m or int(m.group(1)) != pos):
            out.append(
                (
                    "decisions",
                    "docs/DECISIONS.md",
                    n,
                    f"header {pos} must carry DEC-{pos:03d}: {line[:70]}",
                )
            )
        elif pos < FIRST_DEC_WITH_ID and m:
            out.append(
                (
                    "decisions",
                    "docs/DECISIONS.md",
                    n,
                    f"header {pos} has an ID before DEC-{FIRST_DEC_WITH_ID:03d}: {line[:70]}",
                )
            )
    for i, line in enumerate(lines):
        if i > sep and line.startswith("Substitui:"):
            out.extend(
                (
                    "decisions",
                    "docs/DECISIONS.md",
                    i + 1,
                    f"Substitui: names DEC-{m.group(1)}, which does not exist",
                )
                for m in re.finditer(r"\bDEC-(\d+)\b", line)
                if not 1 <= int(m.group(1)) <= len(headers)
            )
    return out


def check_open_questions(corpus: dict[str, str]) -> list[Failure]:
    text = corpus.get("docs/OPEN_QUESTIONS.md")
    if text is None:
        return []
    out: list[Failure] = []
    for n, line in enumerate(text.splitlines(), 1):
        if re.match(r"^\| OQ-\d+ \|", line):
            status = re.split(r"(?<!\\)\|", line)[-2].strip()
            if status not in OQ_STATUSES:
                out.append(
                    (
                        "open_questions",
                        "docs/OPEN_QUESTIONS.md",
                        n,
                        f"status {status!r} is not one of {', '.join(OQ_STATUSES)}",
                    )
                )
    return out


def check_conformance(corpus: dict[str, str]) -> list[Failure]:
    out: list[Failure] = []
    for rel, text in sorted(corpus.items()):
        if not (rel.startswith("docs/phases/") and rel.endswith(".md")):
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if re.match(r"^##\s+Conformance\b", line):
                header = next((x for x in lines[i + 1 :] if x.strip()), "").strip()
                if header != CONFORMANCE_HEADER:
                    out.append(
                        (
                            "conformance",
                            rel,
                            i + 1,
                            f"header of the Conformance table is {header[:80]!r}",
                        )
                    )
    return out


def skipped_counts(corpus: dict[str, str]) -> dict[str, int]:
    """Lines exempted by a marker, per file, for the files the checks read (not the lint's own files)."""
    counts: dict[str, int] = {}
    for rel, text in sorted(corpus.items()):
        if rel in SELF_FILES or (rel.startswith("docs/") and not is_active_doc(rel)):
            continue
        n = len(skipped_lines(text))
        if n:
            counts[rel] = n
    return counts


def run_checks(root: Path = REPO, corpus: dict[str, str] | None = None) -> list[Failure]:
    if corpus is None:
        corpus = load(root)
    return [
        *check_ids(corpus),
        *check_paths(corpus, root),
        *check_tests(corpus, root),
        *check_lines(corpus),
        *check_decisions(corpus),
        *check_open_questions(corpus),
        *check_conformance(corpus),
    ]


def main(root: Path = REPO) -> int:
    start = time.perf_counter()
    corpus = load(root)
    failures = run_checks(root, corpus)
    for check, rel, n, message in failures:
        print(f"{check} {rel}:{n} {message}")
    counts = skipped_counts(corpus)
    for rel, n in counts.items():
        print(f"lint_docs: skipped {n:4d} line(s) in {rel}")
    print(
        f"lint_docs: skipped {sum(counts.values()):4d} line(s) in {len(counts)} file(s), in total"
    )
    print(f"lint_docs: {len(failures)} failure(s) in {time.perf_counter() - start:.1f} s")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
