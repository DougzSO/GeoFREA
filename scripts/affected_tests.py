"""The test files affected by the files changed since a revision (COMMAND 75): the loop of development, not the gate of a merge.

usage: python scripts/affected_tests.py [--base main] [--run] [-- <extra pytest arguments>]

A test file is affected when one of the `geofrea` modules it imports, directly or through the modules those import (the same import closure that
fingerprints the code of a phase, `core.code_fingerprint`), is a changed file; or when it is itself changed; or when it names a changed file that
is not Python (a config file, a script, a document). `main.py` is not followed through its imports, which would reach every module: the tests that
import it are selected when `main.py` itself changes.

The full suite stays mandatory before every merge (`docs/CONVENTIONS.md`, Tests): this selection can miss a test that reaches a module through a
string (a path, a registry), which only the full suite catches. Without `--run` the files are printed, one a line.
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
sys.path.insert(0, str(SRC))

from geofrea.core.code_fingerprint import closure_modules  # noqa: E402


def changed_files(base: str) -> list[str]:
    """Paths (repo-relative, forward slashes) changed since `base`, committed or not, and the untracked ones."""
    def lines(*cmd: str) -> list[str]:
        return subprocess.run(["git", "-C", str(REPO), *cmd], capture_output=True, text=True, check=True).stdout.splitlines()

    names = set(lines("diff", "--name-only", f"{base}...HEAD")) | set(lines("diff", "--name-only", "HEAD"))
    names |= set(lines("ls-files", "--others", "--exclude-standard"))
    return sorted(n for n in names if n)


def module_of(path: str) -> str | None:
    """`geofrea.pkg.mod` of a source path under `src/geofrea`, else None (`__init__` stands for its package)."""
    p = Path(path)
    if p.suffix != ".py" or p.parts[:2] != ("src", "geofrea"):
        return None
    parts = list(p.with_suffix("").parts[2:])
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(["geofrea", *parts]) if parts else "geofrea"


@lru_cache(maxsize=None)
def imported_roots(test_path: str) -> tuple[str, ...]:
    """The `geofrea` modules a test file imports directly, as `pkg.mod` (the form `closure_modules` takes, without the `geofrea.` prefix)."""
    tree = ast.parse((REPO / test_path).read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name for a in node.names if a.name.startswith("geofrea."))
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0 and node.module.startswith("geofrea"):
            roots.add(node.module)
            roots.update(f"{node.module}.{a.name}" for a in node.names)
    return tuple(sorted(r.removeprefix("geofrea.") for r in roots if r != "geofrea"))


@lru_cache(maxsize=None)
def closure_of_test(test_path: str) -> frozenset[str]:
    """Every `geofrea` module the test reaches through its imports (`geofrea.pkg.mod`)."""
    reached: set[str] = set()
    for root in imported_roots(test_path):
        try:
            reached.update(f"geofrea.{m}" for m in closure_modules((root,)))
        except Exception:  # noqa: BLE001 - a name that is a function or a class, not a module: its module was added by the parent
            continue
    return frozenset(reached)


def affected(changed: list[str], tests: list[str]) -> list[str]:
    changed_modules = {m for m in map(module_of, changed) if m}
    other = [Path(c).name for c in changed if module_of(c) is None and not c.startswith("tests/")]
    selected = set()
    for test in tests:
        text = (REPO / test).read_text(encoding="utf-8")
        if test in changed:
            selected.add(test)
        elif changed_modules & closure_of_test(test):
            selected.add(test)
        elif any(name in text for name in other):
            selected.add(test)
        elif "main.py" in changed and ("import main" in text or "from main import" in text):
            selected.add(test)
    return sorted(selected)


def all_tests() -> list[str]:
    return sorted(p.relative_to(REPO).as_posix() for p in (REPO / "tests").rglob("test_*.py"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base", default="main", help="revision the changes are counted from (default: main)")
    parser.add_argument("--run", action="store_true", help="run pytest on the selected files")
    parser.add_argument("pytest_args", nargs="*", help="extra pytest arguments, after --")
    args = parser.parse_args(argv)
    selected = affected(changed_files(args.base), all_tests())
    if not args.run:
        print("\n".join(selected))
        return 0
    if not selected:
        print("no test file is affected by the changes")
        return 0
    return subprocess.run([sys.executable, "-m", "pytest", *selected, *args.pytest_args], cwd=REPO, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
