"""Rewriting the code fingerprint of a phase after modules left its hashed set, only under proof (COMMAND 208A).

A scratch git repository holds a small `src/geofrea` package in commits with chosen dates; the manifests are built here. The real manifests are not touched.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from geofrea.core import code_rebaseline as rb
from geofrea.core.code_fingerprint import (
    PHASE_CODE_ROOTS,
    ROBUSTNESS_ANALYSIS_MODULES,
    SRC_ROOT,
    closure_fingerprint,
    closure_modules,
    phase_modules,
)
from geofrea.core.orchestrator import PhaseManifestEntry, RunManifest

pytestmark = pytest.mark.unit

ISO = "ZZZ"
PHASE = "robustness_analysis"
ENTRY = rb.EntryPoint("pkg.entry", "build_it")
T_FIRST = "2026-11-01T10:00:00+00:00"
T_RUN = "2026-11-09T09:00:00+00:00"
T_COLD = "2026-11-06T09:00:00+00:00"
T_LATER = "2026-11-10T09:00:00+00:00"
OLD_ROOTS = ("pkg",)  # the whole package, `extra` included
NEW_ROOTS = ("pkg.entry", "pkg.core_mod", "pkg.lib")  # without `extra`
FILES = {
    "geofrea/__init__.py": "",
    "geofrea/pkg/__init__.py": "",
    "geofrea/pkg/entry.py": "from geofrea.pkg import core_mod\n\n\ndef build_it():\n    return core_mod.value()\n",
    "geofrea/pkg/core_mod.py": "from geofrea.pkg.lib import twice\n\n\ndef value():\n    return twice(2)\n",
    "geofrea/pkg/lib.py": "def twice(x):\n    return 2 * x\n",
    "geofrea/pkg/extra.py": "from geofrea.pkg.only_extra import helper\n\n\ndef run():\n    return helper()\n",
    "geofrea/pkg/only_extra.py": "def helper():\n    return 1\n",
}


class Scratch:
    def __init__(self, root: Path) -> None:
        self.root = root
        for name, text in FILES.items():
            path = root / "src" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.org")
        self.git("config", "user.name", "t")
        self.commit("first", T_FIRST)

    @property
    def src(self) -> Path:
        return self.root / "src" / "geofrea"

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, check=True).stdout.strip()

    def commit(self, message: str, date: str) -> str:
        self.git("add", "-A")
        env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=self.root, env=env, check=True, capture_output=True)
        return self.git("rev-parse", "HEAD")

    def write(self, name: str, text: str) -> None:
        (self.root / "src" / "geofrea" / name).write_text(text, encoding="utf-8")

    def manifest(self, *, dirty: bool = False, started: str = T_RUN, cold: str | None = T_COLD, fingerprint: str | None = None) -> RunManifest:
        """A manifest whose phase ran under the package as committed now, hashed with the old roots (the whole package)."""
        recorded = fingerprint or closure_fingerprint(OLD_ROOTS, self.src)
        entry = PhaseManifestEntry(
            phase=PHASE,
            status="success",
            output=None,
            error=None,
            started_at=started,
            finished_at=started,
            code_fingerprint=recorded,
            cold_started_at=cold,
            cold_code_fingerprint=recorded,
        )
        return RunManifest(run_id="r" * 8, dirty=dirty, country_code=ISO, phases={PHASE: entry})

    def prove(self, manifest: RunManifest, **kwargs) -> rb.Proof:
        return rb.prove(
            self.root,
            manifest,
            PHASE,
            new_src_root=self.src,
            new_roots=kwargs.pop("new_roots", NEW_ROOTS),
            entry=ENTRY,
            old_roots=lambda _src, _phase: OLD_ROOTS,
            ref="main",
            **kwargs,
        )


@pytest.fixture
def scratch(tmp_path):
    return Scratch(tmp_path / "repo")


def _run_then_edit(scratch: Scratch, name: str, text: str) -> RunManifest:
    """The phase ran at T_RUN under the committed package; afterwards `name` is edited and committed."""
    manifest = scratch.manifest()
    scratch.write(name, text)
    scratch.commit(f"edit {name}", T_LATER)
    return manifest


def test_an_unreachable_module_leaving_the_hashed_set_is_adopted_with_its_proof(scratch):
    manifest = scratch.manifest()
    proof = scratch.prove(manifest)
    assert not proof.already_current
    assert proof.removed_modules == ["pkg.extra", "pkg.only_extra"]
    assert proof.previous_fingerprint == manifest.phases[PHASE].code_fingerprint
    assert proof.new_fingerprint == closure_fingerprint(NEW_ROOTS, scratch.src) != proof.previous_fingerprint
    assert proof.reachable_modules == len(closure_modules((ENTRY.module,), scratch.src))
    assert [e.label for e in proof.executions] == ["started_at", "cold_started_at"]
    assert proof.previous_roots == list(OLD_ROOTS)


def test_the_proof_is_recorded_in_the_manifest_and_the_cold_fingerprint_follows(scratch, tmp_path):
    manifest = scratch.manifest()
    path = tmp_path / "manifest.json"
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    proof = scratch.prove(manifest, new_commit=scratch.git("rev-parse", "HEAD"), new_tree_dirty=False)
    rb.apply(path, [proof])
    written = rb.load_manifest(path).phases[PHASE]
    assert written.code_fingerprint == proof.new_fingerprint == written.cold_code_fingerprint
    (record,) = written.code_rebaselines
    assert record.previous_fingerprint == proof.previous_fingerprint
    assert record.removed_modules == ["pkg.extra", "pkg.only_extra"]
    assert record.entry_point == "pkg.entry:build_it"
    assert record.new_commit == scratch.git("rev-parse", "HEAD")
    assert record.cold_updated and len(record.proof_sha256) == 64 and len(record.reachable_sha256) == 64
    assert [e.commit for e in record.executions] == [scratch.git("rev-parse", "HEAD")] * 2


def test_the_proof_is_refused_for_a_tree_with_uncommitted_changes_unless_allowed(scratch, tmp_path):
    manifest = scratch.manifest()
    path = tmp_path / "manifest.json"
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    proof = scratch.prove(manifest, new_tree_dirty=True)
    with pytest.raises(rb.RebaselineRefused, match="uncommitted"):
        rb.apply(path, [proof])
    assert rb.load_manifest(path).phases[PHASE].code_fingerprint == manifest.phases[PHASE].code_fingerprint
    rb.apply(path, [proof], allow_dirty_tree=True)
    assert rb.load_manifest(path).phases[PHASE].code_fingerprint == proof.new_fingerprint


def test_a_phase_whose_fingerprint_is_already_the_new_one_needs_no_rewrite(scratch):
    manifest = scratch.manifest(fingerprint=closure_fingerprint(NEW_ROOTS, scratch.src))
    assert scratch.prove(manifest).already_current


def test_a_reachable_module_that_changed_since_the_run_refuses(scratch):
    manifest = _run_then_edit(scratch, "pkg/lib.py", "def twice(x):\n    return 3 * x\n")
    with pytest.raises(rb.RebaselineRefused, match="reaches changed its normalised AST.*pkg.lib"):
        scratch.prove(manifest)


def test_a_change_of_a_comment_or_a_docstring_is_not_a_change(scratch):
    manifest = _run_then_edit(scratch, "pkg/lib.py", '"""Doubles."""\n# a comment\ndef twice(x):\n    return 2 * x\n')
    assert scratch.prove(manifest).removed_modules == ["pkg.extra", "pkg.only_extra"]


def test_a_removed_module_that_is_reachable_refuses(scratch):
    manifest = scratch.manifest()
    with pytest.raises(rb.RebaselineRefused, match="left the hashed set is reachable.*pkg.core_mod.*pkg.entry"):
        scratch.prove(manifest, new_roots=("pkg.lib",))  # the new roots no longer hash the entry module nor core_mod, which the phase runs


def test_a_module_that_stays_in_the_hashed_set_but_is_not_reached_must_be_the_same(scratch):
    """Proof D: the fingerprint exists to say that code changed; a change of a module outside the entry's reach is not adopted either."""
    manifest = _run_then_edit(scratch, "pkg/only_extra.py", "def helper():\n    return 2\n")
    with pytest.raises(rb.RebaselineRefused, match="besides the ones that left.*pkg.only_extra"):
        scratch.prove(manifest, new_roots=(*NEW_ROOTS, "pkg.only_extra"))  # it stays in the hashed set, the entry point does not reach it
    # whereas, left out of the roots, the same edit is no proof against: the module is gone from the hashed set
    assert scratch.prove(manifest).removed_modules == ["pkg.extra", "pkg.only_extra"]


def test_a_new_tree_that_hashes_a_module_the_old_one_did_not_refuses(scratch):
    scratch.write("pkg/newer.py", "def n():\n    return 0\n")
    manifest = scratch.manifest()  # the run did not have `newer` (not committed, the commit in force is the first)
    with pytest.raises(rb.RebaselineRefused):
        scratch.prove(manifest, new_roots=(*NEW_ROOTS, "pkg.newer"))


def test_a_recorded_fingerprint_that_no_commit_reproduces_refuses(scratch):
    manifest = scratch.manifest(fingerprint="0" * 64)
    with pytest.raises(rb.RebaselineRefused, match="the code of the run is not a commit"):
        scratch.prove(manifest)


def test_a_dirty_run_may_be_the_first_commit_made_after_it(scratch):
    """The PRT case: the F7 ran with uncommitted edits that were committed 30 minutes later; the commit is found by the fingerprint it reproduces."""
    scratch.write("pkg/lib.py", "def twice(x):\n    return x + x\n")
    fingerprint = closure_fingerprint(OLD_ROOTS, scratch.src)  # the code the run had (uncommitted at T_RUN)
    scratch.commit("commit of what had run", T_LATER)
    manifest = scratch.manifest(dirty=True, fingerprint=fingerprint, cold=None)
    proof = scratch.prove(manifest)
    assert [e.label for e in proof.executions] == ["started_at:next_commit"]
    with pytest.raises(rb.RebaselineRefused, match="not a commit"):
        scratch.prove(scratch.manifest(dirty=False, fingerprint=fingerprint, cold=None))  # a clean run cannot be the code of a later commit


def test_a_missing_entry_function_or_entry_point_refuses(scratch):
    manifest = scratch.manifest()
    with pytest.raises(rb.RebaselineRefused, match="does not define"):
        rb.prove(
            scratch.root, manifest, PHASE, new_src_root=scratch.src, new_roots=NEW_ROOTS, entry=rb.EntryPoint("pkg.entry", "nope"), old_roots=lambda *_: OLD_ROOTS
        )
    with pytest.raises(rb.RebaselineRefused, match="no entry point"):
        rb.prove(scratch.root, manifest, "some_phase", new_src_root=scratch.src, new_roots=NEW_ROOTS)


def test_a_phase_that_did_not_succeed_has_nothing_to_rebaseline(scratch):
    manifest = scratch.manifest()
    entry = manifest.phases[PHASE].model_copy(update={"status": "failed"})
    manifest.phases[PHASE] = entry
    with pytest.raises(rb.RebaselineRefused, match="no successful entry"):
        scratch.prove(manifest)


def test_the_manifest_changed_since_the_proof_is_refused_at_apply(scratch, tmp_path):
    manifest = scratch.manifest()
    path = tmp_path / "manifest.json"
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    proof = scratch.prove(manifest, new_tree_dirty=False)
    other = manifest.model_copy(deep=True)
    other.phases[PHASE] = other.phases[PHASE].model_copy(update={"code_fingerprint": "f" * 64})
    path.write_text(other.model_dump_json(indent=2), encoding="utf-8")
    with pytest.raises(rb.RebaselineRefused, match="changed since it was proved"):
        rb.apply(path, [proof])


def test_the_roots_of_a_commit_are_read_from_its_own_code_fingerprint_module():
    assert rb.roots_in_tree(SRC_ROOT, PHASE) == PHASE_CODE_ROOTS[PHASE]


# ── the real roots of the F7 (COMMAND 208A) ──────────────────────────────────────────────────────────────────────────────────────────────


def test_the_f7_lists_every_module_of_its_package_except_the_convergence():
    package = {p.stem for p in (SRC_ROOT / "robustness_analysis").glob("*.py") if p.stem != "__init__"}
    assert set(ROBUSTNESS_ANALYSIS_MODULES) == package - {"convergence"}
    assert len(set(ROBUSTNESS_ANALYSIS_MODULES)) == len(ROBUSTNESS_ANALYSIS_MODULES)


def test_the_convergence_is_in_the_closure_of_its_phase_and_not_in_that_of_the_f7():
    assert "robustness_analysis.convergence" in phase_modules("sample_size_convergence")
    assert "robustness_analysis.convergence" not in phase_modules("robustness_analysis")
    others = [p for p in PHASE_CODE_ROOTS if p not in ("sample_size_convergence",)]
    assert [p for p in others if "robustness_analysis.convergence" in phase_modules(p)] == []


def test_the_entry_point_of_the_f7_exists_and_does_not_reach_the_convergence():
    entry = rb.ENTRY_POINTS[PHASE]
    tree = rb.measure("now", SRC_ROOT, PHASE_CODE_ROOTS[PHASE], entry)
    assert "robustness_analysis.convergence" not in tree.reachable
    assert set(tree.reachable) <= set(tree.digests)
