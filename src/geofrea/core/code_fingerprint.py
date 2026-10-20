"""Code fingerprint of a phase (manifest 2.6, A-02).

The configuration fingerprint (`config_fingerprint.py`) sees the config files only, so a change of code that gives other results did not
invalidate a phase (COMMAND 52 and 55). The code fingerprint is the SHA-256 of the source of the modules a phase runs: every file of its
package (or the named module) and, transitively, every `geofrea` module those files import, including the `__init__` of each package on the
way. Each file enters as its normalised syntax tree: comments, docstrings, blank lines and formatting do not change it, a changed
expression, constant, name or statement does.

A phase lists its roots in `PHASE_CODE_ROOTS` (a package, or a module for the phases that share a package with another, such as
`potential_maps` in `technical_potential`). The closure follows imports at any depth in the file (a function-level or `TYPE_CHECKING`
import counts: it may run). Not included: the modules of `INFRASTRUCTURE_MODULES` (the manifest, the fingerprints, the run log: they decide whether a phase runs and compute no result), `main.py` (it only wires the phases), the config files (the other fingerprint), third-party
packages and the interpreter.
"""

from __future__ import annotations

import ast
import hashlib
from functools import cache, lru_cache
from pathlib import Path

PACKAGE = "geofrea"
SRC_ROOT = Path(__file__).resolve().parents[1]  # .../src/geofrea

# phase -> packages (all their files) or modules (one file) that start its closure, as dotted names under `geofrea`
PHASE_CODE_ROOTS: dict[str, tuple[str, ...]] = {
    "data_acquisition": ("data_acquisition",),
    "data_quality_audit": ("data_quality_audit",),
    "grid_alignment": ("grid_alignment",),
    "external_inputs": ("climate_forcing.external_inputs",),
    "siting_layers": ("siting_layers",),
    "land_eligibility": ("land_eligibility",),
    "climate_forcing": ("climate_forcing",),
    "hazard_context": ("climate_forcing.hazards", "climate_forcing.pipeline"),
    "climate_maps": ("climate_forcing.maps", "climate_forcing.pipeline"),
    "technical_potential": ("technical_potential",),
    "lcoe_modeling": ("lcoe_modeling",),
    "sample_size_convergence": ("robustness_analysis.convergence",),
    "robustness_analysis": ("robustness_analysis",),
    "external_validation": ("external_validation",),
    "lcoe_maps": ("lcoe_modeling.maps",),
    "robustness_maps": ("robustness_analysis.maps",),
    "potential_maps": ("technical_potential.maps", "technical_potential.absolute_maps"),
    "results_synthesis": ("results_synthesis",),
    "overview": ("overview",),
}

# Infrastructure of the manifest and of the run: it decides whether a phase runs, it never computes a result, so a phase that imports it
# (for `PhaseContext`, say) is not invalidated by an edit of it.
INFRASTRUCTURE_MODULES = frozenset(
    {
        "core.orchestrator",
        "core.code_fingerprint",
        "core.config_fingerprint",
        "core.content_hash",
        "core.run_logging",
        "core.power",
    }
)


def _module_file(src_root: Path, dotted: str) -> Path | None:
    """The file of module `dotted` (a name under `geofrea`, `""` for the package itself), or None when it is not ours."""
    base = src_root.joinpath(*dotted.split(".")) if dotted else src_root
    if base.with_suffix(".py").is_file() and dotted:
        return base.with_suffix(".py")
    init = base / "__init__.py"
    return init if init.is_file() else None


def _is_package(src_root: Path, dotted: str) -> bool:
    base = src_root.joinpath(*dotted.split(".")) if dotted else src_root
    return (base / "__init__.py").is_file()


def _package_files(src_root: Path, dotted: str) -> list[str]:
    """Dotted names of every module of the package `dotted` (itself included)."""
    base = src_root.joinpath(*dotted.split("."))
    names = []
    for path in sorted(base.rglob("*.py")):
        rel = path.relative_to(src_root).with_suffix("")
        parts = list(rel.parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        names.append(".".join(parts))
    return names


def _imported_modules(src_root: Path, dotted: str, tree: ast.AST) -> set[str]:
    """The `geofrea` modules a module imports (dotted names under `geofrea`), at any depth of the file."""
    found: set[str] = set()
    here = dotted.split(".") if dotted else []
    package = here if _is_package(src_root, dotted) else here[:-1]

    def add(name: str) -> None:
        if name and _module_file(src_root, name) is not None:
            found.add(name)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == PACKAGE:
                    add(".".join(parts[1:]))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - (node.level - 1)] if node.level > 1 else package
                base_parts = [*base, *(node.module.split(".") if node.module else [])]
            else:
                parts = (node.module or "").split(".")
                if parts[0] != PACKAGE:
                    continue
                base_parts = parts[1:]
            base_name = ".".join(base_parts)
            add(base_name)
            for alias in node.names:  # `from geofrea.x import y` where y is a module
                add(".".join([*base_parts, alias.name]))
    return found


def _strip_docstrings(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]


def normalised_source(source: str) -> str:
    """The syntax tree of `source` without docstrings, as text: comments, blank lines and formatting are not in it.

    A source that does not parse is returned as it is (its bytes then count).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    _strip_docstrings(tree)
    return ast.dump(tree, annotate_fields=True, include_attributes=False)


@lru_cache(maxsize=4096)
def _file_digest_cached(path: str, mtime_ns: int, size: int) -> str:
    return hashlib.sha256(
        normalised_source(Path(path).read_text(encoding="utf-8")).encode("utf-8")
    ).hexdigest()


def _file_digest(path: Path) -> str:
    stat = path.stat()
    return _file_digest_cached(str(path), stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=4096)
def _parsed_imports(root: str, name: str, path: str, mtime_ns: int, size: int) -> frozenset[str]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return frozenset(_imported_modules(Path(root), name, tree))


def phase_modules(phase: str, src_root: Path | None = None) -> list[str]:
    """Dotted names of the modules whose source counts for `phase`: its roots and everything they import, transitively.

    Raises:
        KeyError: `phase` has no entry in PHASE_CODE_ROOTS (a registered phase must declare its code).
    """
    root = Path(src_root) if src_root is not None else SRC_ROOT
    queue: list[str] = []
    for item in PHASE_CODE_ROOTS[phase]:
        if _is_package(root, item):
            queue.extend(_package_files(root, item))
        else:
            queue.append(item)
    seen: set[str] = set()
    while queue:
        name = queue.pop()
        if name in seen or name in INFRASTRUCTURE_MODULES:
            continue
        path = _module_file(root, name)
        if path is None:
            continue
        seen.add(name)
        parts = name.split(".") if name else []
        for i in range(len(parts)):  # the __init__ of every package on the way runs too
            queue.append(".".join(parts[:i]))
        stat = path.stat()
        queue.extend(_parsed_imports(str(root), name, str(path), stat.st_mtime_ns, stat.st_size))
    return sorted(seen)


def code_fingerprint(phase: str, src_root: Path | None = None) -> str:
    """SHA-256 of the normalised source of the modules of `phase` (`phase_modules`), each with its dotted name."""
    root = Path(src_root) if src_root is not None else SRC_ROOT
    digest = hashlib.sha256()
    for name in phase_modules(phase, root):
        path = _module_file(root, name)
        assert path is not None
        digest.update(f"{name}:{_file_digest(path)}\n".encode())
    return digest.hexdigest()


@cache
def cached_code_fingerprint(phase: str) -> str:
    """`code_fingerprint(phase)` of the installed source, computed once per process."""
    return code_fingerprint(phase)
