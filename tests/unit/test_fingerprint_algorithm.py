"""The text that the code fingerprints hash does not depend on the Python version (OQ-077, COMMAND 120).

`ast.dump` writes `type_params=[]` in every function and class definition from Python 3.12 on, so the same file had another digest outside 3.11.
`core.code_fingerprint.canonical_dump` writes the text of Python 3.11 on every version, through a statement that defines no name, so that no
definition the fingerprints read was edited and no recorded fingerprint or cache key changed. The unit job of CI runs these tests on 3.11 and
on 3.12: the literal digest below is the same on both.
"""

from __future__ import annotations

import ast
import hashlib
import shutil
import sys
from pathlib import Path

import pytest

import geofrea
from geofrea.core import code_fingerprint as cf
from geofrea.core import function_fingerprint as ff
from geofrea.core.cache_code import CACHE_FUNCTION_ENTRIES, cache_code
from geofrea.core.code_fingerprint import PHASE_CODE_ROOTS, closure_fingerprint, normalised_source

pytestmark = pytest.mark.unit

SRC_ROOT = Path(geofrea.__file__).resolve().parent

# a file with every kind of definition and expression the dump has to write: decorators, annotations, defaults, keyword-only and variadic arguments,
# comprehensions, an f-string with a conversion and a format spec, async, try/except/finally, a class with a metaclass, a lambda, structural matching
SNIPPET = '''
"""module docstring"""
import os
from typing import Generic, TypeVar

T = TypeVar("T")


@decorator(1, key="v")
def f(x: int, *args, y: float = 2.0, **kw) -> int:
    """docstring"""
    z = [i * 2 for i in range(x) if i % 2]
    w = {a: b for a, b in kw.items()}
    msg = f"{x!r:>10} and {y}"
    return x + 1 if z else -x


async def g(a):
    async with a as b:
        await b
    try:
        pass
    except (ValueError, KeyError) as e:
        raise RuntimeError("x") from e
    finally:
        pass


class C(Generic[T], metaclass=type):
    attr: int = 3

    @property
    def p(self):
        return lambda q, *, r=1: q @ r


match g:
    case [1, 2, *rest]:
        pass
    case {"k": v} | None:
        pass
    case _:
        pass
'''
# the SHA-256 of `normalised_source(SNIPPET)` on Python 3.11 with the algorithm of every fingerprint recorded before COMMAND 120 (version 1); the same on 3.12
SNIPPET_DIGEST = "19b3c9caf7815fc4bfdc04602713ca8d35bf653c109e9cabe0186a9e939a96e2"


def test_the_normalised_text_of_a_file_has_the_same_digest_on_every_python_version():
    assert hashlib.sha256(normalised_source(SNIPPET).encode()).hexdigest() == SNIPPET_DIGEST


def test_the_text_has_no_type_params_and_is_the_one_ast_dump_writes_on_python_311():
    text = normalised_source("def f(x):\n    return x\n\n\nclass C:\n    pass\n")
    assert "type_params" not in text
    assert text == (
        "Module(body=[FunctionDef(name='f', args=arguments(posonlyargs=[], args=[arg(arg='x')], kwonlyargs=[], kw_defaults=[], defaults=[]), "
        "body=[Return(value=Name(id='x', ctx=Load()))], decorator_list=[]), ClassDef(name='C', bases=[], keywords=[], body=[Pass()], decorator_list=[])], "
        "type_ignores=[])"
    )


@pytest.mark.skipif(sys.version_info[:2] not in ((3, 11), (3, 12)), reason="the stdlib dump of 3.13 and later also leaves out the empty and the None fields")
def test_the_canonical_text_is_the_stdlib_text_without_the_field_added_in_312_for_every_file_of_the_package():
    files = sorted(p for p in SRC_ROOT.rglob("*.py") if "__pycache__" not in p.parts)
    assert len(files) > 100
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        stdlib = ast.dump(tree, annotate_fields=True, include_attributes=False).replace(", type_params=[]", "")
        assert cf.canonical_dump(tree) == stdlib, path


def test_a_real_change_of_the_syntax_tree_changes_the_text_and_a_change_of_form_does_not():
    base = "def f(x):\n    return x + 1\n"
    assert normalised_source(base) == normalised_source('def f(x):\n    """doc"""\n    # a comment\n    return (x   +   1)\n')
    assert normalised_source(base) != normalised_source("def f(x):\n    return x + 2\n")
    assert normalised_source(base) != normalised_source("def f(y):\n    return y + 1\n")
    assert normalised_source(base) != normalised_source("def f(x):\n    return x - 1\n")


def test_the_version_of_the_algorithm_is_one_and_adds_nothing_to_what_is_hashed(monkeypatch):
    assert cf.FINGERPRINT_ALGO_VERSION == 1
    assert not normalised_source("x = 1\n").startswith("algo:")


def test_a_new_version_of_the_algorithm_changes_the_text_of_every_file_and_so_every_fingerprint(monkeypatch, tmp_path):
    root = tmp_path / "geofrea"
    shutil.copytree(SRC_ROOT, root, ignore=shutil.ignore_patterns("__pycache__"))
    roots = PHASE_CODE_ROOTS["grid_alignment"]
    before_phase = closure_fingerprint(roots, root)
    before_cache = ff.function_fingerprint(CACHE_FUNCTION_ENTRIES["aligned_layer.glo30"], root)
    before_text = normalised_source("x = 1\n")
    monkeypatch.setattr(cf, "FINGERPRINT_ALGO_VERSION", 2)
    cf._file_digest_cached.cache_clear()
    monkeypatch.setattr(cf, "_store", {"identity": "test", "digest": {}})  # the digests kept on disk are those of version 1
    try:
        assert normalised_source("x = 1\n") == "algo:2\n" + before_text
        assert closure_fingerprint(roots, root) != before_phase
        assert ff.function_fingerprint(CACHE_FUNCTION_ENTRIES["aligned_layer.glo30"], root) != before_cache
    finally:
        monkeypatch.undo()
        cf._file_digest_cached.cache_clear()
    assert closure_fingerprint(roots, root) == before_phase


def test_the_statements_that_install_the_stable_dump_define_no_name_that_a_fingerprint_reads():
    # the fingerprint of a layer follows the definitions its code reaches, and `cache_code` reaches both modules: nothing the statement uses or
    # defines may be reached, or the keys of roads, lakes and rivers change for no change of result
    for key in ("aligned_layer.glo30", "aligned_layer.roads", "aligned_layer.lakes", "aligned_layer.rivers"):
        reached = ff.reachable_definitions(CACHE_FUNCTION_ENTRIES[key])
        assert not any(d.endswith(("canonical_dump", "_StableAst", "stable_ast", "FINGERPRINT_ALGO_VERSION", "_REAL_AST")) for d in reached), key
    assert cache_code("aligned_layer.glo30")  # and the keys are computed at all


def test_the_function_fingerprint_module_hashes_with_the_same_dump_as_the_closure_fingerprint():
    assert ff.ast.dump is cf.canonical_dump
    assert cf.ast.dump is cf.canonical_dump
    assert ff.ast.AST is ast.AST and ff.ast.parse is ast.parse  # every other name is the stdlib's


def test_the_stdlib_ast_dump_is_intact_after_the_two_modules_are_imported():
    # the statement at the end of each module rebinds the name `ast` in that module's namespace only: the `ast` module, and its `dump`, are the stdlib's
    import importlib

    stdlib = importlib.import_module("ast")
    assert stdlib is sys.modules["ast"] and not isinstance(stdlib, cf._StableAst)
    assert stdlib.dump is not cf.canonical_dump
    assert stdlib.dump is cf._REAL_AST.dump
    text = stdlib.dump(stdlib.parse("def f(x):\n    return x\n"))
    assert ("type_params=[]" in text) == (sys.version_info >= (3, 12))


def test_a_fresh_interpreter_gives_the_same_stdlib_dump_before_and_after_the_import_of_the_two_modules():
    import subprocess

    code = (
        "import ast, sys\n"
        "src = 'def f(x): return x'\n"
        "dump, before = ast.dump, ast.dump(ast.parse(src))\n"
        f"sys.path.insert(0, {str(SRC_ROOT.parent)!r})\n"
        "import geofrea.core.code_fingerprint, geofrea.core.function_fingerprint\n"
        "assert ast.dump is dump and ast.dump(ast.parse(src)) == before\n"
        "assert type(ast).__name__ == 'module'\n"
        "print('ok')\n"
    )
    done = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ok"
