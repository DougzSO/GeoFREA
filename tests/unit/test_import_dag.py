"""The imports between the packages of `src/geofrea` follow the phase DAG (L-9 of the pre-research audit; METHODOLOGY A-01).

A package may import only packages that come before it in `LAYERS`: the shared configuration models and `core` first, then the phases in
the order of the DAG, then the support packages that read the results of several phases. Every import counts, those inside functions and
under `TYPE_CHECKING` too. A new package must be placed in `LAYERS`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "geofrea"
LAYERS = (
    "config_models",
    "core",
    "viz",
    "data_acquisition",
    "data_quality_audit",
    "grid_alignment",
    "siting_layers",
    "land_eligibility",
    "climate_forcing",
    "technical_potential",
    "lcoe_modeling",
    "robustness_analysis",
    "external_validation",
    "overview",
    "results_synthesis",
    "explorer",
)


def package_edges(src: Path = SRC) -> dict[tuple[str, str], list[str]]:
    """`{(importing package, imported package): ["file:line", ...]}` for every `geofrea` import across two packages."""
    edges: dict[tuple[str, str], list[str]] = {}
    for path in sorted(src.rglob("*.py")):
        relative = path.relative_to(src)
        if len(relative.parts) == 1:
            continue
        package = relative.parts[0]
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            else:
                continue
            for module in modules:
                parts = module.split(".")
                if len(parts) > 1 and parts[0] == "geofrea" and parts[1] != package:
                    edges.setdefault((package, parts[1]), []).append(f"{relative}:{node.lineno}")
    return edges


def violations(
    edges: dict[tuple[str, str], list[str]], layers: tuple[str, ...] = LAYERS
) -> list[str]:
    rank = {name: i for i, name in enumerate(layers)}
    out = []
    for (importer, imported), where in sorted(edges.items()):
        if importer not in rank or imported not in rank:
            out.append(f"{importer} -> {imported}: a package is not in LAYERS ({where[0]})")
        elif rank[imported] >= rank[importer]:
            out.append(f"{importer} -> {imported} goes against the DAG ({', '.join(where[:3])})")
    return out


@pytest.mark.unit
def test_every_package_is_placed_in_the_layers():
    packages = {p.name for p in SRC.iterdir() if p.is_dir() and (p / "__init__.py").exists()}
    assert packages == set(LAYERS)


@pytest.mark.unit
def test_no_import_goes_against_the_phase_dag():
    assert violations(package_edges()) == []


@pytest.mark.unit
def test_the_check_flags_an_import_of_a_later_package(tmp_path):
    """A planted edge from `core` to a phase and one from F6 to F7 are both reported."""
    for name in ("core", "lcoe_modeling", "robustness_analysis"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "core" / "bad.py").write_text(
        "def f():\n    from geofrea.lcoe_modeling import x\n", encoding="utf-8"
    )
    (tmp_path / "lcoe_modeling" / "bad.py").write_text(
        "from geofrea.robustness_analysis.evaluator import evaluate\n", encoding="utf-8"
    )
    (tmp_path / "robustness_analysis" / "ok.py").write_text(
        "from geofrea.lcoe_modeling import inputs\n", encoding="utf-8"
    )
    found = violations(package_edges(tmp_path))
    assert len(found) == 2
    assert any(v.startswith("core -> lcoe_modeling") for v in found)
    assert any(v.startswith("lcoe_modeling -> robustness_analysis") for v in found)
