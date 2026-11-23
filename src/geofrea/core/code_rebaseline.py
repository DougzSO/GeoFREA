"""Rewrite the `code_fingerprint` of a phase after a change that only took modules out of its hashed set, only under proof (COMMAND 208A, A-02).

The code fingerprint of a phase is the hash of every module in the closure of its roots (`core.code_fingerprint`). When a change of the roots takes a
module out of that closure (the F7 hashed the whole `robustness_analysis` package, `convergence.py` included, which the F7 never runs), the fingerprint
changes and the orchestrator would run the phase again for every country, although no module the phase executes has changed. The rewrite below is allowed
only when that is proved by the import graph, and it is recorded with the proof. Three proofs, as the command states them, and one more that closes a gap:

  A  in the commit in force on the date of each execution of the phase recorded in the manifest (the last commit of the reference branch before it), the
     fingerprint, recomputed with the roots that commit had, is the one the manifest recorded. A run made with uncommitted edits (the manifest says
     `dirty`) may be the code of the first commit made after it: when the commit in force does not reproduce the fingerprint, that commit is tried, and
     the execution is recorded as `<label>:next_commit`. The commit is a way to find the code, not part of the claim: the fingerprint it reproduces is;
  B  the set of modules reachable by the import graph from the entry point of the phase (`ENTRY_POINTS`: the module of the `build_*` function the
     phase calls, and the `__init__` of the packages on the way) is the same in the old commit and in the new tree, and each of its modules has the same
     normalised-AST digest in both;
  C  the modules that left the hashed set do not belong to that reachable set;
  D  every other module of the hashed set is in both and has the same digest, and the new tree hashes no module the old one did not: the fingerprint
     differs only by the modules that left (without D a change of a module the phase does not reach would be adopted too, and the fingerprint exists
     to say that code changed).

Anything else (a date with no commit, a fingerprint that does not reproduce, a reachable module that differs, a removed module that is reachable) is a
refusal that names it, and nothing is written: the phase then runs again, which is what the orchestrator does without this module. The proof is the
`CodeRebaseline` of the manifest entry. The consumers of the phase do not become stale: no artifact changes.

The module is run only by `scripts/rebaseline_code_fingerprint.py`, never by a phase or by the orchestrator.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from geofrea.core.atomic_io import replace_durable
from geofrea.core.code_fingerprint import (
    PHASE_CODE_ROOTS,
    SRC_ROOT,
    _file_digest,
    _module_file,
    closure_fingerprint,
    closure_modules,
)
from geofrea.core.config_rebaseline import RebaselineRefused, commit_in_force, load_manifest
from geofrea.core.orchestrator import (
    CodeRebaseline,
    ConfigRebaselineExecution,
    PhaseManifestEntry,
    RunManifest,
    compute_dirty,
    compute_git_commit,
)

SRC_SUBDIR = "src/geofrea"


@dataclass(frozen=True)
class EntryPoint:
    """Where the import graph of a phase starts: `function` of `module` (dotted, under `geofrea`), which the phase calls."""

    module: str
    function: str


# the phases whose fingerprint may be rebaselined, with the function their `PhaseSpec` runs; an entry is added with the change it serves and stays
ENTRY_POINTS: dict[str, EntryPoint] = {
    "robustness_analysis": EntryPoint("robustness_analysis.pipeline", "build_robustness"),
}


@dataclass
class Tree:
    """A source tree under proof: `src_root` is its `src/geofrea`, `roots` the roots the phase had in it."""

    label: str
    src_root: Path
    roots: tuple[str, ...]
    fingerprint: str = ""
    digests: dict[str, str] = field(default_factory=dict)  # every module of the hashed set -> normalised-AST digest
    reachable: dict[str, str] = field(default_factory=dict)  # the modules reachable from the entry point -> digest


def _digests(src_root: Path, names: Sequence[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in names:
        path = _module_file(src_root, name)
        if path is None:
            raise RebaselineRefused(f"module {name!r} has no file under {src_root}")
        out[name] = _file_digest(path, name)
    return out


def measure(label: str, src_root: Path, roots: tuple[str, ...], entry: EntryPoint) -> Tree:
    """The hashed set, the fingerprint and the reachable set of a tree for the roots and the entry point given."""
    tree = Tree(label, Path(src_root), tuple(roots))
    tree.fingerprint = closure_fingerprint(tree.roots, tree.src_root)
    tree.digests = _digests(tree.src_root, closure_modules(tree.roots, tree.src_root))
    entry_file = _module_file(tree.src_root, entry.module)
    if entry_file is None:
        raise RebaselineRefused(f"{label}: the entry module {entry.module} does not exist")
    defined = {n.name for n in ast.walk(ast.parse(entry_file.read_text(encoding="utf-8"))) if isinstance(n, ast.FunctionDef)}
    if entry.function not in defined:
        raise RebaselineRefused(f"{label}: {entry.module} does not define {entry.function}")
    tree.reachable = _digests(tree.src_root, closure_modules((entry.module,), tree.src_root))
    return tree


def reachable_sha256(reachable: Mapping[str, str]) -> str:
    return hashlib.sha256("".join(f"{name}:{digest}\n" for name, digest in sorted(reachable.items())).encode("utf-8")).hexdigest()


def extract_tree(repo: Path, commit: str, dest: Path) -> Path:
    """`src/geofrea` of `commit` written under `dest`; returns that directory."""
    done = subprocess.run(["git", "archive", "--format=tar", commit, SRC_SUBDIR], cwd=repo, capture_output=True, check=False)
    if done.returncode != 0:
        raise RebaselineRefused(f"git archive {commit[:10]} failed: {done.stderr.decode('utf-8', 'replace').strip()}")
    with tarfile.open(fileobj=io.BytesIO(done.stdout)) as archive:
        archive.extractall(dest, filter="data")
    return dest / SRC_SUBDIR


_ROOTS_PROGRAM = (
    "import json, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "from geofrea.core import code_fingerprint as cf\n"
    "json.dump(list(cf.PHASE_CODE_ROOTS[sys.argv[2]]), sys.stdout)\n"
)


def roots_in_tree(src_root: Path, phase: str) -> tuple[str, ...]:
    """`PHASE_CODE_ROOTS[phase]` as the tree at `src_root` defines it (its own `code_fingerprint.py`, run in a fresh interpreter)."""
    done = subprocess.run(
        [sys.executable, "-I", "-c", _ROOTS_PROGRAM, str(src_root.parent), phase],
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONUTF8": "1", "GEOFREA_DATA_DIR": ""},
    )
    if done.returncode != 0:
        raise RebaselineRefused(f"the roots of {phase} could not be read from {src_root}: {done.stderr.decode('utf-8', 'replace').strip()[-300:]}")
    return tuple(json.loads(done.stdout.decode("utf-8")))


@dataclass
class Proof:
    phase: str
    country_code: str
    entry_point: str
    previous_fingerprint: str
    new_fingerprint: str
    new_commit: str
    new_tree_dirty: bool
    manifest_dirty: bool = False
    already_current: bool = False
    executions: list[ConfigRebaselineExecution] = field(default_factory=list)
    previous_roots: list[str] = field(default_factory=list)
    new_roots: list[str] = field(default_factory=list)
    removed_modules: list[str] = field(default_factory=list)
    reachable_modules: int = 0
    reachable_hash: str = ""
    cold_updated: bool = False

    def record(self, rebaselined_at: str) -> CodeRebaseline:
        body = {
            "rebaselined_at": rebaselined_at,
            "entry_point": self.entry_point,
            "executions": [e.model_dump() for e in self.executions],
            "new_commit": self.new_commit,
            "new_tree_dirty": self.new_tree_dirty,
            "previous_fingerprint": self.previous_fingerprint,
            "new_fingerprint": self.new_fingerprint,
            "previous_roots": self.previous_roots,
            "new_roots": self.new_roots,
            "removed_modules": self.removed_modules,
            "reachable_modules": self.reachable_modules,
            "reachable_sha256": self.reachable_hash,
            "cold_updated": self.cold_updated,
            "manifest_dirty": self.manifest_dirty,
        }
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
        return CodeRebaseline(**body, proof_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest())


def commit_after(repo: Path, date: str, ref: str) -> str | None:
    """The first commit of `ref` (first parent) made after `date`, or None."""
    done = subprocess.run(
        ["git", "rev-list", "--first-parent", "--reverse", f"--after={date}", ref], cwd=repo, capture_output=True, check=False
    )
    lines = done.stdout.decode("utf-8").split()
    return lines[0] if done.returncode == 0 and lines else None


def _compare(old: Tree, new: Tree, phase: str, iso: str) -> list[str]:
    """Proofs B, C and D of `old` against `new`; the modules that left the hashed set, or a refusal."""
    where = f"{phase} [{iso}] ({old.label})"
    # B
    if set(old.reachable) != set(new.reachable):
        gone = sorted(set(old.reachable) - set(new.reachable))
        came = sorted(set(new.reachable) - set(old.reachable))
        raise RebaselineRefused(f"{where}: the modules reachable from the entry point differ (left {gone}, joined {came})")
    changed = sorted(name for name, digest in old.reachable.items() if new.reachable[name] != digest)
    if changed:
        raise RebaselineRefused(f"{where}: a module the phase reaches changed its normalised AST: {changed}")
    # D, first half: the new tree hashes nothing the old one did not
    joined = sorted(set(new.digests) - set(old.digests))
    if joined:
        raise RebaselineRefused(f"{where}: the new tree hashes modules the old one did not: {joined}")
    removed = sorted(set(old.digests) - set(new.digests))
    # C
    reached = sorted(set(removed) & (set(old.reachable) | set(new.reachable)))
    if reached:
        raise RebaselineRefused(f"{where}: a module that left the hashed set is reachable from the entry point: {reached}")
    # D, second half: the modules that stay are the same
    differing = sorted(name for name in new.digests if new.digests[name] != old.digests[name])
    if differing:
        raise RebaselineRefused(f"{where}: modules of the hashed set changed besides the ones that left: {differing}")
    return removed


def prove(
    repo: Path,
    manifest: RunManifest,
    phase: str,
    *,
    new_src_root: Path | None = None,
    new_roots: tuple[str, ...] | None = None,
    entry: EntryPoint | None = None,
    old_roots: Callable[[Path, str], tuple[str, ...]] = roots_in_tree,
    ref: str = "main",
    refuse_dirty: bool = False,
    new_commit: str | None = None,
    new_tree_dirty: bool | None = None,
) -> Proof:
    """The proof that the code fingerprint of `phase` may be rewritten for the country of `manifest`, or a `RebaselineRefused` that says what failed."""
    iso = manifest.country_code
    entry = entry or ENTRY_POINTS.get(phase)
    if entry is None:
        raise RebaselineRefused(f"{phase}: no entry point is declared (ENTRY_POINTS), its code fingerprint is not rebaselined")
    recorded_entry: PhaseManifestEntry | None = manifest.phases.get(phase)
    if recorded_entry is None or recorded_entry.status != "success":
        raise RebaselineRefused(f"{phase} [{iso}]: no successful entry in the manifest")
    if not recorded_entry.code_fingerprint:
        raise RebaselineRefused(f"{phase} [{iso}]: the entry records no code_fingerprint")
    if manifest.dirty and refuse_dirty:
        raise RebaselineRefused(f"{phase} [{iso}]: the manifest says its run had a dirty working tree")
    recorded = recorded_entry.code_fingerprint
    src_root = Path(new_src_root) if new_src_root is not None else SRC_ROOT
    roots = tuple(new_roots) if new_roots is not None else PHASE_CODE_ROOTS[phase]
    commit = new_commit if new_commit is not None else compute_git_commit(repo)
    dirty = new_tree_dirty if new_tree_dirty is not None else compute_dirty(repo)
    new = measure("new tree", src_root, roots, entry)
    proof = Proof(
        phase,
        iso,
        f"{entry.module}:{entry.function}",
        recorded,
        new.fingerprint,
        commit,
        dirty,
        manifest_dirty=manifest.dirty,
        new_roots=list(roots),
    )
    if recorded == new.fingerprint:
        proof.already_current = True
        return proof

    dates: list[tuple[str, str]] = [("started_at", recorded_entry.started_at)]
    if (
        recorded_entry.cold_started_at
        and recorded_entry.cold_started_at != recorded_entry.started_at
        and recorded_entry.cold_code_fingerprint == recorded
    ):
        dates.append(("cold_started_at", recorded_entry.cold_started_at))
    removed: list[str] = []
    seen: set[str] = set()
    for label, date in dates:
        candidates = [("", commit_in_force(repo, date, ref))]
        if manifest.dirty:  # a run with uncommitted edits may be the code of the first commit made after it (A', named in the proof)
            after = commit_after(repo, date, ref)
            if after:
                candidates.append((":next_commit", after))
        failure = ""
        for suffix, old_commit in candidates:
            with tempfile.TemporaryDirectory(prefix="geofrea_code_rebaseline_") as tmp:
                old_src = extract_tree(repo, old_commit, Path(tmp))
                old = measure(f"commit {old_commit[:10]}", old_src, old_roots(old_src, phase), entry)
                # A: the commit reproduces the recorded fingerprint with the roots it had
                if old.fingerprint != recorded:
                    failure += (
                        f" commit {old_commit[:10]} ({'first after' if suffix else 'in force on'} {label} {date}) gives {old.fingerprint[:12]} with its own "
                        f"roots, the manifest recorded {recorded[:12]};"
                    )
                    continue
                proof.executions.append(ConfigRebaselineExecution(label=label + suffix, date=date, commit=old_commit))
                if old_commit not in seen:
                    removed = _compare(old, new, phase, iso)
                    seen.add(old_commit)
                    proof.previous_roots = list(old.roots)
            break
        else:
            raise RebaselineRefused(f"{phase} [{iso}]: the code of the run is not a commit:{failure}")
    proof.removed_modules = removed
    proof.reachable_modules = len(new.reachable)
    proof.reachable_hash = reachable_sha256(new.reachable)
    return proof


def apply(manifest_path: Path, proofs: Sequence[Proof], *, allow_dirty_tree: bool = False) -> None:
    """Write the new fingerprints and their proofs into the manifest, in one atomic replace; nothing is written when no proof needs it."""
    pending = [p for p in proofs if not p.already_current]
    if not pending:
        return
    dirty = [p.phase for p in pending if p.new_tree_dirty]
    if dirty and not allow_dirty_tree:
        raise RebaselineRefused(f"{dirty}: the tree the new fingerprint was computed on has uncommitted changes; commit them first so the proof names a commit")
    manifest = load_manifest(manifest_path)
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    for proof in pending:
        entry = manifest.phases[proof.phase]
        if entry.code_fingerprint != proof.previous_fingerprint or manifest.country_code != proof.country_code:
            raise RebaselineRefused(f"{proof.phase}: the manifest changed since it was proved")
        update: dict[str, object] = {"code_fingerprint": proof.new_fingerprint}
        if entry.cold_code_fingerprint == proof.previous_fingerprint:
            update["cold_code_fingerprint"] = proof.new_fingerprint
            proof.cold_updated = True
        update["code_rebaselines"] = [*entry.code_rebaselines, proof.record(stamp)]
        manifest.phases[proof.phase] = entry.model_copy(update=update)
    temporary = manifest_path.with_name(manifest_path.name + ".tmp")
    temporary.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    replace_durable(temporary, manifest_path)


__all__ = [
    "ENTRY_POINTS",
    "EntryPoint",
    "Proof",
    "RebaselineRefused",
    "Tree",
    "apply",
    "extract_tree",
    "measure",
    "prove",
    "reachable_sha256",
    "roots_in_tree",
]
