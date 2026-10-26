"""No script draws a map outside the common figure style (COMMAND 68; spec v2 section 4).

`matplotlib.pyplot` opens the figures, so it is imported only by the package `viz` (MapFigure, PanelFigure, charts) and by the modules whose
figures are not maps of a country: the audit charts of `scripts/audit_potential.py` and the thesis figures of `results_synthesis`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = {
    "scripts/audit_potential.py",
    "src/geofrea/results_synthesis/style.py",
}
ALLOWED_PREFIXES = ("src/geofrea/viz/",)


def _imports_pyplot(path: Path) -> bool:
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import) and any(a.name == "matplotlib.pyplot" for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom):
            if node.module == "matplotlib.pyplot":
                return True
            if node.module == "matplotlib" and any(a.name == "pyplot" for a in node.names):
                return True
    return False


@pytest.mark.unit
def test_pyplot_is_imported_only_by_the_viz_package_and_the_authorised_modules():
    found = {
        path.relative_to(ROOT).as_posix()
        for folder in ("src", "scripts")
        for path in (ROOT / folder).rglob("*.py")
        if _imports_pyplot(path)
    }
    outside = {f for f in found if f not in ALLOWED and not f.startswith(ALLOWED_PREFIXES)}
    assert not outside, f"figures must go through the package viz, found pyplot in {sorted(outside)}"
