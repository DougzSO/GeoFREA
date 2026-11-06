"""Every module in FINGERPRINT_EXEMPT_MODULES has a registered test that its output is byte-identical to the output without it (COMMAND 98).

The list in `code_fingerprint.FINGERPRINT_EXEMPT_MODULES` takes a module out of every code fingerprint (CONVENTIONS, "Write mechanics outside the
fingerprints"). The criterion for entering it is that the content of everything written through the module is equal before and after: this file
turns that criterion from text into a check. A module cannot be exempt without a line in `BYTE_IDENTICAL_TEST`, and the test named there must exist.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from geofrea.core.code_fingerprint import FINGERPRINT_EXEMPT_MODULES

pytestmark = pytest.mark.unit

UNIT = Path(__file__).resolve().parent

# module -> "<test file>::<test name>": the test that shows the bytes written through it equal the bytes written without it (or, for a module that
# writes nothing of a result, that it leaves the result untouched). A new exempt module adds its line here, with its own test, in the same change.
BYTE_IDENTICAL_TEST: dict[str, str] = {
    "core.atomic_io": "test_atomic_io.py::test_safe_raster_write_gives_the_same_content_as_before",
    "core.cog_write": "test_atomic_io.py::test_the_cog_bytes_are_those_of_the_conversion_before_the_change",
    "core.checkpoint": "test_checkpoint.py::test_with_a_checkpoint_the_rasters_are_those_of_the_run_without_one",
    "core.resumable_download": "test_resumable_download.py::test_a_whole_download_is_named_only_when_complete_and_gives_the_manifest_entry",
    "core.cache_integrity": "test_cache_integrity.py::test_a_cut_raster_is_found_and_its_key_removed_but_not_the_file",
}


def _test_names(path: Path) -> set[str]:
    return {n.name for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))) if isinstance(n, ast.FunctionDef)}


def test_every_exempt_module_has_a_registered_byte_identical_test() -> None:
    missing = sorted(FINGERPRINT_EXEMPT_MODULES - BYTE_IDENTICAL_TEST.keys())
    assert not missing, f"exempt from the fingerprints without a byte-identical test registered: {missing}"


def test_the_registry_names_no_module_that_is_not_exempt() -> None:
    stale = sorted(BYTE_IDENTICAL_TEST.keys() - FINGERPRINT_EXEMPT_MODULES)
    assert not stale, f"registered but no longer exempt (remove the line): {stale}"


@pytest.mark.parametrize("module", sorted(BYTE_IDENTICAL_TEST))
def test_the_registered_test_exists(module: str) -> None:
    file_name, _, test_name = BYTE_IDENTICAL_TEST[module].partition("::")
    path = UNIT / file_name
    assert path.is_file(), f"{module}: {file_name} does not exist"
    assert test_name in _test_names(path), f"{module}: {file_name} has no test named {test_name}"
