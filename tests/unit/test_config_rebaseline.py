"""Rewriting the config fingerprint of a phase after its scope gained keys, only under proof (COMMAND 127, item 5c).

A scratch git repository holds a copy of the real `config/` in commits with chosen dates; the manifests are built here. The real manifests are not touched.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from geofrea.core import config_rebaseline as rb
from geofrea.core.config_fingerprint import (
    CONFIG_FILES,
    PHASE_CONFIG_SCOPE,
    DiskConfigSource,
    config_fingerprint,
)
from geofrea.core.orchestrator import PhaseManifestEntry, RunManifest

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]
CHANGE = rb.SCOPE_CHANGES["scope-127-f2a-f3"]
ISO = "PRT"
PHASES = sorted(CHANGE.additions)
T_FIRST = "2026-11-01T10:00:00+00:00"
T_COLD = "2026-11-06T09:00:00+00:00"
T_RUN = "2026-11-09T09:00:00+00:00"
T_LATER = "2026-11-10T09:00:00+00:00"


class Scratch:
    """A scratch repository with a `config/` and the means to commit a change of it at a given date."""

    def __init__(self, root: Path) -> None:
        self.root = root
        shutil.copytree(REPO / "config", root / "config", ignore=shutil.ignore_patterns("__pycache__"))
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.org")
        self.git("config", "user.name", "t")
        self.commit("first", T_FIRST)

    def git(self, *args: str) -> str:
        done = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, check=True)
        return done.stdout.strip()

    def commit(self, message: str, date: str) -> str:
        self.git("add", "-A")
        env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=self.root, env=env, check=True, capture_output=True)
        return self.git("rev-parse", "HEAD")

    def edit_parameters(self, mutate) -> None:
        path = self.root / "config" / "parameters.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def edit_settings(self, old: str, new: str) -> None:
        path = self.root / "config" / "settings.yaml"
        text = path.read_text(encoding="utf-8")
        assert text.count(old) == 1, old
        path.write_text(text.replace(old, new), encoding="utf-8")

    def bump_tolerance(self) -> str:
        """Change `geospatial.poi_line_tolerance_m` (a key F2a already declared); returns the text before."""
        path = self.root / "config" / "settings.yaml"
        text = path.read_text(encoding="utf-8")
        match = re.search(r"^(\s*poi_line_tolerance_m:\s*)([0-9.]+)", text, flags=re.MULTILINE)
        assert match, "settings.yaml has no poi_line_tolerance_m"
        path.write_text(text.replace(match.group(0), f"{match.group(1)}{float(match.group(2)) + 1}"), encoding="utf-8")
        return text

    def source(self) -> DiskConfigSource:
        config = self.root / "config"
        return DiskConfigSource({key: config / name for key, name in CONFIG_FILES.items()}, config / "turbines")

    def manifest(self, *, dirty: bool = False, recorded: dict[str, str] | None = None, cold: str | None = T_COLD, started: str = T_RUN) -> RunManifest:
        """A manifest whose phases ran under the config of the working tree now, with the OLD scope (what the manifests on disk hold)."""
        source = self.source()
        phases = {}
        for phase in PHASES:
            fingerprint = (recorded or {}).get(phase) or config_fingerprint(phase, ISO, source, rb.old_scope_of(phase, CHANGE))
            phases[phase] = PhaseManifestEntry(
                phase=phase,
                status="success",
                output=None,
                error=None,
                started_at=started,
                finished_at=started,
                config_fingerprint=fingerprint,
                cold_started_at=cold,
            )
        return RunManifest(run_id="r" * 8, dirty=dirty, country_code=ISO, phases=phases)


@pytest.fixture
def scratch(tmp_path):
    return Scratch(tmp_path / "repo")


def _prove(scratch: Scratch, manifest: RunManifest, phase: str):
    return rb.prove(scratch.root, manifest, phase, CHANGE, scratch.source(), ref="main")


def test_the_scope_of_the_code_names_every_key_the_change_says_it_added():
    for phase in PHASES:
        assert rb.old_scope_of(phase, CHANGE) != dict(PHASE_CONFIG_SCOPE[phase])  # and the old scope is the code scope minus the keys


def test_every_key_of_the_change_is_present_for_the_three_countries():
    from geofrea.core.config_fingerprint import ABSENT, phase_config_payload

    source = DiskConfigSource({key: REPO / "config" / name for key, name in CONFIG_FILES.items()}, REPO / "config" / "turbines")
    for iso in ("PRT", "IND", "BRA"):
        for phase, files in CHANGE.additions.items():
            payload = phase_config_payload(phase, iso, source, {k: list(v) for k, v in files.items()})
            for key, values in payload.items():
                for selector, value in values.items():
                    if selector.endswith("poi_sensitivity_threshold_kv"):
                        continue  # only IND has one (COMMAND 86); absent is a value like another
                    assert value != ABSENT, (iso, phase, key, selector)


@pytest.mark.parametrize("phase", PHASES)
def test_the_proof_holds_when_nothing_the_phase_reads_changed(scratch, phase):
    manifest = scratch.manifest()
    proof = _prove(scratch, manifest, phase)
    assert not proof.already_current
    assert proof.new_fingerprint != proof.previous_fingerprint
    assert [e.label for e in proof.executions] == ["started_at", "cold_started_at"]
    assert {e.commit for e in proof.executions} == {scratch.git("rev-parse", "HEAD")}
    assert {k.selector for k in proof.keys} == {
        s.replace("{iso}", ISO) for files in [CHANGE.additions[phase]] for sels in files.values() for s in sels
    }
    assert proof.old_scope_fingerprint_now == proof.previous_fingerprint


def test_an_unrelated_change_after_the_run_does_not_block_the_proof(scratch):
    manifest = scratch.manifest()
    scratch.edit_parameters(lambda d: d["countries"]["BRA"]["connection"]["poi_voltage_threshold_kv"].update(value=999.0))  # another country
    scratch.commit("other country", T_LATER)
    for phase in PHASES:
        assert not _prove(scratch, manifest, phase).already_current


def test_a_key_the_scope_gained_that_changed_after_the_run_is_refused(scratch):
    manifest = scratch.manifest()
    scratch.edit_parameters(lambda d: d["countries"][ISO]["connection"]["poi_voltage_threshold_kv"].update(value=111.0))
    scratch.commit("threshold changed", T_LATER)
    with pytest.raises(rb.RebaselineRefused, match="poi_voltage_threshold_kv"):
        _prove(scratch, manifest, "grid_alignment")
    _prove(scratch, manifest, "land_eligibility")  # F3 does not read it: its own keys did not change


def test_a_value_that_differed_on_the_cold_run_is_refused(scratch):
    scratch.edit_parameters(lambda d: d["countries"][ISO]["connection"]["reference_project_mw"].update(value=77.0))
    scratch.commit("project size", "2026-11-05T09:00:00+00:00")  # in force on the cold run (06 Nov)
    scratch.edit_parameters(lambda d: d["countries"][ISO]["connection"]["reference_project_mw"].update(value=100.0))
    scratch.commit("project size back", "2026-11-08T09:00:00+00:00")  # in force on the last run (09 Nov) and now
    manifest = scratch.manifest()  # the old scope ignores the key: the recorded fingerprint fits both commits
    with pytest.raises(rb.RebaselineRefused, match=r"reference_project_mw.*cold_started_at"):
        _prove(scratch, manifest, "land_eligibility")


def test_a_key_the_phase_already_declared_that_changed_since_is_refused(scratch):
    manifest = scratch.manifest()
    scratch.bump_tolerance()
    scratch.commit("tolerance", T_LATER)
    with pytest.raises(rb.RebaselineRefused, match="already declared"):
        _prove(scratch, manifest, "grid_alignment")


def test_a_fingerprint_the_commit_of_the_run_does_not_reproduce_is_refused(scratch):
    # the working tree is the one the manifest recorded, but the commit in force on the run holds another value of a declared key
    manifest = scratch.manifest()
    original = scratch.bump_tolerance()
    scratch.commit("tolerance changed before the run", "2026-11-05T09:00:00+00:00")
    (scratch.root / "config" / "settings.yaml").write_text(original, encoding="utf-8")  # the working tree holds the original value again: C holds
    with pytest.raises(rb.RebaselineRefused, match="is not that commit"):
        _prove(scratch, manifest, "grid_alignment")


def test_a_dirty_run_and_a_date_before_any_commit_are_refused(scratch):
    dirty = scratch.manifest(dirty=True)
    with pytest.raises(rb.RebaselineRefused, match="dirty"):
        rb.prove(scratch.root, dirty, "grid_alignment", CHANGE, scratch.source(), ref="main", refuse_dirty=True)
    proof = _prove(scratch, dirty, "grid_alignment")  # by default the commit is the reference, and the flag goes into the proof
    assert proof.manifest_dirty and proof.record("2026-11-10T00:00:00+00:00").manifest_dirty
    with pytest.raises(rb.RebaselineRefused, match="no commit"):
        _prove(scratch, scratch.manifest(started="2026-10-01T00:00:00+00:00", cold=None), "grid_alignment")


def test_an_entry_that_is_not_a_success_or_has_no_fingerprint_is_refused(scratch):
    manifest = scratch.manifest()
    manifest.phases["grid_alignment"] = manifest.phases["grid_alignment"].model_copy(update={"status": "failed"})
    manifest.phases["land_eligibility"] = manifest.phases["land_eligibility"].model_copy(update={"config_fingerprint": None})
    with pytest.raises(rb.RebaselineRefused, match="no successful entry"):
        _prove(scratch, manifest, "grid_alignment")
    with pytest.raises(rb.RebaselineRefused, match="no config_fingerprint"):
        _prove(scratch, manifest, "land_eligibility")


def _write(path: Path, manifest: RunManifest) -> None:
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")


def test_apply_writes_the_new_fingerprint_and_the_proof_and_nothing_else(scratch, tmp_path):
    manifest = scratch.manifest()
    path = tmp_path / "manifest.json"
    _write(path, manifest)
    before = json.loads(path.read_text(encoding="utf-8"))
    proofs = [_prove(scratch, manifest, phase) for phase in PHASES]
    rb.apply(path, proofs)
    after = json.loads(path.read_text(encoding="utf-8"))
    reloaded = RunManifest.model_validate_json(path.read_text(encoding="utf-8"))
    for proof in proofs:
        entry = reloaded.phases[proof.phase]
        assert entry.config_fingerprint == proof.new_fingerprint == config_fingerprint(proof.phase, ISO, scratch.source())
        (recorded,) = entry.config_rebaselines
        assert recorded.previous_fingerprint == proof.previous_fingerprint and recorded.change_id == CHANGE.id
        assert [e.commit for e in recorded.executions] == [e.commit for e in proof.executions]
        body = {k: v for k, v in recorded.model_dump().items() if k != "proof_sha256"}
        assert recorded.proof_sha256 == hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        # nothing but those two fields moved
        a, b = after["phases"][proof.phase], before["phases"][proof.phase]
        assert {k for k in a if a[k] != b[k]} == {"config_fingerprint", "config_rebaselines"}
    assert after["artifacts"] == before["artifacts"] and after["run_id"] == before["run_id"]


def test_a_second_run_finds_the_fingerprint_current_and_writes_nothing(scratch, tmp_path):
    manifest = scratch.manifest()
    path = tmp_path / "manifest.json"
    _write(path, manifest)
    rb.apply(path, [_prove(scratch, manifest, phase) for phase in PHASES])
    written = path.read_bytes()
    again = RunManifest.model_validate_json(written.decode("utf-8"))
    proofs = [_prove(scratch, again, phase) for phase in PHASES]
    assert all(p.already_current for p in proofs)
    rb.apply(path, proofs)
    assert path.read_bytes() == written


def test_apply_refuses_a_manifest_that_changed_since_the_proof(scratch, tmp_path):
    manifest = scratch.manifest()
    path = tmp_path / "manifest.json"
    _write(path, manifest)
    proofs = [_prove(scratch, manifest, "grid_alignment")]
    other = manifest.model_copy(deep=True)
    other.phases["grid_alignment"] = other.phases["grid_alignment"].model_copy(update={"config_fingerprint": "f" * 64})
    _write(path, other)
    bytes_before = path.read_bytes()
    with pytest.raises(rb.RebaselineRefused, match="changed since"):
        rb.apply(path, proofs)
    assert path.read_bytes() == bytes_before


def _script(scratch: Scratch, manifest_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "rebaseline_config_fingerprint.py"),
            "--change",
            CHANGE.id,
            "--countries",
            ISO,
            "--manifest",
            str(manifest_path),
            "--repo",
            str(scratch.root),
            "--config-dir",
            str(scratch.root / "config"),
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(REPO / "src")},
    )


def test_the_script_is_a_dry_run_unless_asked(scratch, tmp_path):
    path = tmp_path / "manifest.json"
    _write(path, scratch.manifest())
    before = path.read_bytes()
    dry = _script(scratch, path)
    assert dry.returncode == 0, dry.stdout + dry.stderr
    assert dry.stdout.count("PROVED") == len(PHASES) and "dry run" in dry.stdout
    assert path.read_bytes() == before
    done = _script(scratch, path, "--apply")
    assert done.returncode == 0 and "WRITTEN" in done.stdout, done.stdout + done.stderr
    assert path.read_bytes() != before
    again = _script(scratch, path, "--apply")
    assert again.returncode == 0 and again.stdout.count("CURRENT") == len(PHASES)


def test_the_script_writes_nothing_when_any_phase_is_refused(scratch, tmp_path):
    path = tmp_path / "manifest.json"
    manifest = scratch.manifest()
    _write(path, manifest)
    scratch.edit_parameters(lambda d: d["countries"][ISO]["connection"]["poi_voltage_threshold_kv"].update(value=111.0))
    scratch.commit("threshold changed", T_LATER)  # F2a is refused, F3 would be proved
    before = path.read_bytes()
    done = _script(scratch, path, "--apply")
    assert done.returncode == 1 and "REFUSED" in done.stdout and "poi_voltage_threshold_kv" in done.stdout
    assert "WRITTEN" not in done.stdout
    assert path.read_bytes() == before
