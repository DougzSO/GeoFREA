"""Code fingerprint of one entry function: the functions it can reach, not the modules it imports (COMMAND 88, item 3, A-02).

`code_fingerprint.closure_fingerprint` hashes whole modules, so an edit of the population step changed the key of the elevation layer, which
lives in the same module. The fingerprint here starts at an entry function (`"grid_alignment.layers:build_elevation"`) and follows the names it
uses: a function, class or constant defined at the top level of the same module, or imported from another `geofrea` module (`from geofrea.x
import y`, `import geofrea.x as m` then `m.y`). Each definition reached enters as its normalised syntax tree (no comments, docstrings or
formatting, as in `code_fingerprint.normalised_source`); the SHA-256 is taken over the sorted `module:name` lines with those digests.

What it follows: names read anywhere in a definition, decorators, base classes, default values and annotations included. A class that is
reached enters whole, methods and all, so a call through an instance is covered. What it cannot follow is a call through an object whose class
it never names (a callback received from outside is covered by the file that passes it, which names it).

An edit of a definition the entry cannot reach leaves the fingerprint unchanged; an edit of one it reaches changes it.
"""

from __future__ import annotations

import ast
import hashlib
from functools import lru_cache
from pathlib import Path

from geofrea.core.code_fingerprint import (
    PACKAGE,
    SRC_ROOT,
    _module_file,
    _strip_docstrings,
)

_Def = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


class UnknownEntryError(KeyError):
    """The entry named `module:name` is not defined at the top level of the module."""


class _Module:
    """One parsed module: its top-level definitions and the geofrea names it imports."""

    def __init__(self, src_root: Path, dotted: str) -> None:
        path = _module_file(src_root, dotted)
        if path is None:
            raise UnknownEntryError(f"{dotted}: not a module of {PACKAGE}")
        self.dotted = dotted
        self.tree = ast.parse(path.read_text(encoding="utf-8"))
        self.defs: dict[str, list[ast.stmt]] = {}
        self.imported_names: dict[str, tuple[str, str]] = {}  # local name -> (module, name) for `from geofrea.m import n`
        self.imported_modules: dict[str, str] = {}  # local alias -> module for `import geofrea.m as a` / `from geofrea import m`
        is_package = path.name == "__init__.py"
        self._index(src_root, is_package)

    def _index(self, src_root: Path, is_package: bool) -> None:
        for stmt in self.tree.body:
            if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                self.defs.setdefault(stmt.name, []).append(stmt)
            elif isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    for name in _target_names(target):
                        self.defs.setdefault(name, []).append(stmt)
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                self.defs.setdefault(stmt.target.id, []).append(stmt)
        here = self.dotted.split(".") if self.dotted else []
        package = here if is_package else here[:-1]
        for node in ast.walk(self.tree):  # imports at any depth: a function-level import may run
            if isinstance(node, ast.Import):
                for alias in node.names:
                    parts = alias.name.split(".")
                    if parts[0] == PACKAGE and alias.asname:
                        self.imported_modules[alias.asname] = ".".join(parts[1:])
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
                for alias in node.names:
                    local = alias.asname or alias.name
                    as_module = ".".join([*base_parts, alias.name])
                    if _module_file(src_root, as_module) is not None and as_module:
                        self.imported_modules[local] = as_module
                    elif _module_file(src_root, base_name) is not None:
                        self.imported_names[local] = (base_name, alias.name)


def _target_names(target: ast.expr) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Tuple | ast.List):
        return [name for element in target.elts for name in _target_names(element)]
    return []


def _references(stmt: ast.AST) -> tuple[set[str], set[tuple[str, str]]]:
    """(bare names read, `alias.attr` pairs read) anywhere inside `stmt`."""
    names: set[str] = set()
    attrs: set[tuple[str, str]] = set()
    for node in ast.walk(stmt):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            attrs.add((node.value.id, node.attr))
    return names, attrs


def _normalised(stmt: ast.stmt) -> str:
    """The syntax tree of one definition without docstrings, as text."""
    wrapper = ast.Module(body=[stmt], type_ignores=[])
    _strip_docstrings(wrapper)
    return ast.dump(wrapper, annotate_fields=True, include_attributes=False)


@lru_cache(maxsize=512)
def _module(src_root: str, dotted: str, mtime_ns: int, size: int) -> _Module:
    return _Module(Path(src_root), dotted)


def _load(src_root: Path, dotted: str) -> _Module:
    path = _module_file(src_root, dotted)
    if path is None:
        raise UnknownEntryError(f"{dotted}: not a module of {PACKAGE}")
    stat = path.stat()
    return _module(str(src_root), dotted, stat.st_mtime_ns, stat.st_size)


def reachable_definitions(entries: tuple[str, ...], src_root: Path | None = None) -> list[str]:
    """The `module:name` of every definition reachable from `entries` (each `"module:name"`, a dotted name under `geofrea`), sorted."""
    root = Path(src_root) if src_root is not None else SRC_ROOT
    seen: set[tuple[str, str]] = set()
    queue: list[tuple[str, str]] = []
    for entry in entries:
        dotted, _, name = entry.partition(":")
        if not name or name not in _load(root, dotted).defs:
            raise UnknownEntryError(f"{entry}: not defined at the top level of {dotted}")
        queue.append((dotted, name))
    while queue:
        key = queue.pop()
        if key in seen:
            continue
        seen.add(key)
        module = _load(root, key[0])
        for stmt in module.defs.get(key[1], []):
            names, attrs = _references(stmt)
            for ref in names:
                if ref in module.defs and ref != key[1]:
                    queue.append((key[0], ref))
                if ref in module.imported_names:
                    target_module, target_name = module.imported_names[ref]
                    if target_name in _load(root, target_module).defs:
                        queue.append((target_module, target_name))
            for alias, attr in attrs:
                target_module = module.imported_modules.get(alias)
                if target_module is not None and attr in _load(root, target_module).defs:
                    queue.append((target_module, attr))
    return sorted(f"{dotted}:{name}" for dotted, name in seen)


def function_fingerprint(entries: tuple[str, ...], src_root: Path | None = None) -> str:
    """SHA-256 of the normalised source of every definition reachable from `entries`, each with its `module:name`."""
    root = Path(src_root) if src_root is not None else SRC_ROOT
    digest = hashlib.sha256()
    for qualified in reachable_definitions(entries, root):
        dotted, _, name = qualified.partition(":")
        body = "".join(_normalised(stmt) for stmt in _load(root, dotted).defs[name])
        digest.update(f"{qualified}:{hashlib.sha256(body.encode('utf-8')).hexdigest()}\n".encode())
    return digest.hexdigest()
