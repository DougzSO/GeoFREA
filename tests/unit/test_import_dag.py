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


# -- cycles between modules (COMMAND 131: the package order above does not see two modules of one package that import each other) ---------


def _module_name(src: Path, path: Path) -> str:
    parts = list(path.relative_to(src).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def module_edges(src: Path = SRC) -> dict[str, set[str]]:
    """`{module: {modules of src it imports}}`, every import counted (inside functions and under TYPE_CHECKING too), by dotted name under `geofrea`.

    `from geofrea.a.b import c` is an edge to `a.b.c` when that is a module and to `a.b` when `c` is a name in it.
    """
    modules = {_module_name(src, p) for p in src.rglob("*.py")}
    edges: dict[str, set[str]] = {m: set() for m in modules}
    for path in sorted(src.rglob("*.py")):
        me = _module_name(src, path)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            targets: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "geofrea":
                base = ".".join(node.module.split(".")[1:])
                for alias in node.names:
                    deeper = f"{base}.{alias.name}" if base else alias.name
                    targets.append(deeper if deeper in modules else base)
            elif isinstance(node, ast.Import):
                targets = [".".join(a.name.split(".")[1:]) for a in node.names if a.name.split(".")[0] == "geofrea"]
            for target in targets:
                if target in modules and target != me:
                    edges[me].add(target)
    return edges


def cycles(edges: dict[str, set[str]]) -> list[list[str]]:
    """The strongly connected components of more than one module (Tarjan), each sorted, the list sorted."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    found: list[list[str]] = []
    counter = [0]

    def visit(start: str) -> None:  # iterative, so a deep import chain cannot hit the recursion limit
        work = [(start, iter(sorted(edges.get(start, ()))))]
        index[start] = low[start] = counter[0]
        counter[0] += 1
        stack.append(start)
        on_stack.add(start)
        while work:
            node, children = work[-1]
            advanced = False
            for child in children:
                if child not in index:
                    index[child] = low[child] = counter[0]
                    counter[0] += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(sorted(edges.get(child, ())))))
                    advanced = True
                    break
                if child in on_stack:
                    low[node] = min(low[node], index[child])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1:
                    found.append(sorted(component))

    for module in sorted(edges):
        if module not in index:
            visit(module)
    return sorted(found)


@pytest.mark.unit
def test_no_two_modules_import_each_other_directly_or_through_others():
    """`robustness_analysis.assemble` and `hypotheses` did (the second imported `Rankings` from the first under TYPE_CHECKING); `Rankings` now lives in `rankings`."""
    assert cycles(module_edges()) == []


@pytest.mark.unit
def test_the_cycle_check_flags_a_planted_cycle_of_two_and_one_of_three_and_not_a_chain(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    files = {
        "a": "from geofrea.pkg.b import f\n",
        "b": "def g():\n    from geofrea.pkg.a import h\n",  # a <-> b, the second inside a function
        "c": "from geofrea.pkg import d\n",
        "d": "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from geofrea.pkg.e import X\n",
        "e": "from geofrea.pkg.c import y\n",  # c -> d -> e -> c
        "chain1": "from geofrea.pkg.chain2 import z\n",
        "chain2": "x = 1\n",
    }
    for name, text in files.items():
        (pkg / f"{name}.py").write_text(text, encoding="utf-8")
    assert cycles(module_edges(tmp_path)) == [["pkg.a", "pkg.b"], ["pkg.c", "pkg.d", "pkg.e"]]
