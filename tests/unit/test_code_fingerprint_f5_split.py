"""The code fingerprint of F5 holds the modules that write the potential tables, not the figure code of `potential_maps` (COMMAND 73,
R71-06): an edit of a figure does not invalidate F5, an edit of a module that writes the tables does."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import geofrea
from geofrea.core.code_fingerprint import (
    PHASE_CODE_ROOTS,
    TECHNICAL_POTENTIAL_FIGURE_MODULES,
    TECHNICAL_POTENTIAL_NUMERIC_MODULES,
    code_fingerprint,
    phase_modules,
)

pytestmark = pytest.mark.unit

SRC = Path(geofrea.__file__).resolve().parent
PACKAGE = SRC / "technical_potential"


@pytest.fixture
def source_copy(tmp_path) -> Path:
    target = tmp_path / "geofrea"
    shutil.copytree(SRC, target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (path.name, old, text.count(old))
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_every_module_of_the_package_is_numeric_or_figure_and_none_is_both():
    on_disk = {p.stem for p in PACKAGE.glob("*.py") if p.stem != "__init__"}
    numeric, figures = (
        set(TECHNICAL_POTENTIAL_NUMERIC_MODULES),
        set(TECHNICAL_POTENTIAL_FIGURE_MODULES),
    )
    assert numeric | figures == on_disk
    assert not numeric & figures


def test_the_closure_of_f5_holds_no_figure_code():
    f5 = set(phase_modules("technical_potential"))
    assert not f5 & {f"technical_potential.{m}" for m in TECHNICAL_POTENTIAL_FIGURE_MODULES}
    assert not [m for m in f5 if m == "viz" or m.startswith("viz.")]


def test_a_figure_module_does_not_invalidate_f5_and_invalidates_potential_maps(source_copy):
    before = {p: code_fingerprint(p, source_copy) for p in PHASE_CODE_ROOTS}
    _edit(
        source_copy / "technical_potential" / "maps.py",
        'CENTRAL = "central"\n',
        'CENTRAL = "centre"\n',
    )
    after = {p: code_fingerprint(p, source_copy) for p in PHASE_CODE_ROOTS}
    assert after["technical_potential"] == before["technical_potential"]
    assert after["potential_maps"] != before["potential_maps"]


def test_a_module_that_writes_the_tables_invalidates_f5_and_the_figures_follow_through_the_manifest(
    source_copy,
):
    before = {p: code_fingerprint(p, source_copy) for p in PHASE_CODE_ROOTS}
    _edit(
        source_copy / "technical_potential" / "capacity.py",
        "    return area * luf * power_density_mw_per_km2\n",
        "    return area * luf * power_density_mw_per_km2 * 1.0\n",
    )
    after = {p: code_fingerprint(p, source_copy) for p in PHASE_CODE_ROOTS}
    # `potential_maps` does not import `capacity`: it is marked stale by the content hash of the potential tables F5 then writes
    assert after["technical_potential"] != before["technical_potential"]
