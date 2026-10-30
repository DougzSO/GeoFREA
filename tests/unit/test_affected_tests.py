"""scripts/affected_tests.py selects the test files a change can reach (COMMAND 75)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "affected_tests.py"


def _load():
    spec = importlib.util.spec_from_file_location("affected_tests", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_source_path_maps_to_its_module():
    at = _load()
    assert at.module_of("src/geofrea/technical_potential/cf_table.py") == "geofrea.technical_potential.cf_table"
    assert at.module_of("src/geofrea/core/__init__.py") == "geofrea.core"
    assert at.module_of("scripts/affected_tests.py") is None
    assert at.module_of("docs/CONVENTIONS.md") is None


def test_a_test_is_selected_when_a_module_in_its_import_closure_changes():
    at = _load()
    tests = ["tests/unit/test_cf_table.py", "tests/unit/test_adopt_aligned_cache_keys.py"]
    chosen = at.affected(["src/geofrea/technical_potential/cf_table.py"], tests)
    assert "tests/unit/test_cf_table.py" in chosen


def test_a_changed_test_is_selected_and_an_unrelated_change_selects_nothing():
    at = _load()
    tests = ["tests/unit/test_cf_table.py"]
    assert at.affected(["tests/unit/test_cf_table.py"], tests) == tests
    assert at.affected(["README.md"], tests) == []
