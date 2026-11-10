"""Rewrite the `config_fingerprint` of a phase after its scope gained keys, only under proof (COMMAND 127, item 5c; defect 1 of the generality audit).

When `PHASE_CONFIG_SCOPE` of a phase gains keys the phase already read, its fingerprint changes and the orchestrator would run it again for every country,
although nothing it read has changed. The rewrite below is allowed only when that is proved, and it is recorded with the proof:

  A  for every execution date of the phase recorded in the manifest (`started_at`, and `cold_started_at` when it differs), the commit in force on that date
     (the last commit of the reference branch before it) gives, with the scope the phase had before, the fingerprint the manifest recorded;
  B  the value of every key the scope gained is the same in each of those commits and in the current files;
  C  the current files give, with the old scope, the recorded fingerprint: no key the phase already declared has changed since.

The manifest records whether its run had a dirty working tree. A run with uncommitted edits to a key the scope gained cannot be told from a clean one
(A sees only the keys the phase already declared), so the flag is kept in the proof, and `refuse_dirty` (the script's `--refuse-dirty`) refuses on it.

Anything else (a date with no commit, a dirty run, a fingerprint that does not reproduce, a value that differs) is a refusal that names it, and nothing is
written: the phase then runs again, which is what the orchestrator does without this module. The proof is the `ConfigRebaseline` of the manifest entry.

The module is run only by `scripts/rebaseline_config_fingerprint.py`, never by a phase or by the orchestrator.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from geofrea.core.atomic_io import replace_durable
from geofrea.core.config_fingerprint import (
    CONFIG_FILES,
    PHASE_CONFIG_SCOPE,
    ConfigSource,
    config_fingerprint,
    phase_config_payload,
)
from geofrea.core.orchestrator import (
    _MANIFEST_SCHEMA_VERSION,
    _READABLE_MANIFEST_SCHEMA_VERSIONS,
    ConfigRebaseline,
    ConfigRebaselineExecution,
    ConfigRebaselineKey,
    PhaseManifestEntry,
    RunManifest,
)

CONFIG_DIR = "config"
TURBINES_DIR = f"{CONFIG_DIR}/turbines"


@dataclass(frozen=True)
class ScopeChange:
    """Keys added to the scope of some phases: `additions[phase][file key]` are the selectors, as written in `PHASE_CONFIG_SCOPE`."""

    id: str
    description: str
    additions: Mapping[str, Mapping[str, Sequence[str]]]


# every change of scope that may be rebaselined; an entry is added with the change of `PHASE_CONFIG_SCOPE` it describes and stays
SCOPE_CHANGES: dict[str, ScopeChange] = {
    "scope-127-f2a-f3": ScopeChange(
        id="scope-127-f2a-f3",
        description="F2a and F3 name the keys of parameters.json and settings.yaml they read (defect 1 of docs/_audit/generality_audit.md)",
        additions={
            "grid_alignment": {
                "parameters": [
                    "countries.{iso}.connection.poi_voltage_threshold_kv",
                    "countries.{iso}.connection.poi_sensitivity_threshold_kv",
                ],
            },
            "land_eligibility": {
                "parameters": [
                    "countries.{iso}.connection.reference_project_mw",
                    "countries.{iso}.technologies.*.power_density_mw_per_km2",
                ],
                "settings": ["geospatial.pvcz_csv", "geospatial.pvcz_max_distance_km"],
            },
        },
    ),
}


def load_manifest(path: Path) -> RunManifest:
    """The manifest at `path` as the orchestrator reads it: an older readable schema is taken as the current one (its new fields default)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") not in _READABLE_MANIFEST_SCHEMA_VERSIONS:
        raise RebaselineRefused(f"{path}: schema_version {data.get('schema_version')!r} is not readable")
    data["schema_version"] = _MANIFEST_SCHEMA_VERSION
    return RunManifest.model_validate(data)


class RebaselineRefused(RuntimeError):
    """The proof does not hold; nothing is written."""


class GitConfigSource:
    """The config files as they were in a commit of `repo` (a `ConfigSource` for `config_fingerprint`)."""

    def __init__(self, repo: Path, commit: str) -> None:
        self.repo, self.commit = Path(repo), commit

    def _git(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, check=False)

    def text(self, key: str) -> str | None:
        done = self._git("show", f"{self.commit}:{CONFIG_DIR}/{CONFIG_FILES[key]}")
        return done.stdout.decode("utf-8") if done.returncode == 0 else None

    def turbine_files(self) -> dict[str, bytes]:
        listing = self._git("ls-tree", "--name-only", f"{self.commit}:{TURBINES_DIR}")
        if listing.returncode != 0:
            return {}
        out: dict[str, bytes] = {}
        for name in sorted(listing.stdout.decode("utf-8").split("\n")):
            if name:
                out[name] = self._git("show", f"{self.commit}:{TURBINES_DIR}/{name}").stdout
        return out


def commit_in_force(repo: Path, date: str, ref: str) -> str:
    """The last commit of `ref` (first parent) made before `date`; a refusal when there is none."""
    done = subprocess.run(
        ["git", "rev-list", "-n", "1", "--first-parent", f"--before={date}", ref],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    commit = done.stdout.decode("utf-8").strip()
    if done.returncode != 0 or not commit:
        raise RebaselineRefused(f"no commit of {ref} before {date}")
    return commit


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def old_scope_of(phase: str, change: ScopeChange) -> dict[str, list[str]]:
    """The scope of `phase` in the code without the keys `change` added."""
    added = change.additions.get(phase)
    if not added:
        raise RebaselineRefused(f"{change.id} does not change the scope of {phase}")
    scope = {key: list(selectors) for key, selectors in PHASE_CONFIG_SCOPE[phase].items()}
    for key, selectors in added.items():
        missing = [s for s in selectors if s not in scope.get(key, [])]
        if missing:
            raise RebaselineRefused(f"{phase}: the scope of the code does not name {key}: {missing}, which {change.id} says it added")
        scope[key] = [s for s in scope[key] if s not in selectors]
        if not scope[key]:
            del scope[key]
    return scope


@dataclass
class Proof:
    phase: str
    country_code: str
    change_id: str
    previous_fingerprint: str
    new_fingerprint: str
    manifest_dirty: bool = False
    already_current: bool = False
    executions: list[ConfigRebaselineExecution] = field(default_factory=list)
    keys: list[ConfigRebaselineKey] = field(default_factory=list)
    old_scope_fingerprint_now: str = ""

    def record(self, rebaselined_at: str) -> ConfigRebaseline:
        body = {
            "change_id": self.change_id,
            "rebaselined_at": rebaselined_at,
            "previous_fingerprint": self.previous_fingerprint,
            "new_fingerprint": self.new_fingerprint,
            "executions": [e.model_dump() for e in self.executions],
            "keys": [k.model_dump() for k in self.keys],
            "old_scope_fingerprint_now": self.old_scope_fingerprint_now,
            "manifest_dirty": self.manifest_dirty,
        }
        return ConfigRebaseline(**body, proof_sha256=hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest())


def prove(
    repo: Path,
    manifest: RunManifest,
    phase: str,
    change: ScopeChange,
    current: ConfigSource,
    *,
    ref: str = "main",
    refuse_dirty: bool = False,
) -> Proof:
    """The proof that the fingerprint of `phase` may be rewritten for the country of `manifest`, or a `RebaselineRefused` that says what failed."""
    iso = manifest.country_code
    entry: PhaseManifestEntry | None = manifest.phases.get(phase)
    if entry is None or entry.status != "success":
        raise RebaselineRefused(f"{phase} [{iso}]: no successful entry in the manifest")
    if not entry.config_fingerprint:
        raise RebaselineRefused(f"{phase} [{iso}]: the entry records no config_fingerprint")
    if manifest.dirty and refuse_dirty:
        raise RebaselineRefused(f"{phase} [{iso}]: the manifest says its run had a dirty working tree, the config of the run is not certainly a commit")
    recorded = entry.config_fingerprint
    old_scope = old_scope_of(phase, change)
    new_now = config_fingerprint(phase, iso, current)
    proof = Proof(phase, iso, change.id, recorded, new_now, manifest_dirty=manifest.dirty)
    if recorded == new_now:
        proof.already_current = True
        return proof

    # C: no key the phase already declared has changed since
    proof.old_scope_fingerprint_now = config_fingerprint(phase, iso, current, old_scope)
    if proof.old_scope_fingerprint_now != recorded:
        raise RebaselineRefused(
            f"{phase} [{iso}]: the current config gives {proof.old_scope_fingerprint_now[:12]} with the old scope, the manifest recorded "
            f"{recorded[:12]}: a key the phase already declared has changed since it ran; the phase must run again"
        )

    # the dates of the executions: the last one and the slowest one under the current code
    dates: list[tuple[str, str]] = [("started_at", entry.started_at)]
    if entry.cold_started_at and entry.cold_started_at != entry.started_at:
        dates.append(("cold_started_at", entry.cold_started_at))
    additions = {key: list(selectors) for key, selectors in change.additions[phase].items()}
    sources: dict[str, ConfigSource] = {}
    for label, date in dates:
        commit = commit_in_force(repo, date, ref)
        source = GitConfigSource(repo, commit)
        proof.executions.append(ConfigRebaselineExecution(label=label, date=date, commit=commit))
        # A: the commit in force then reproduces the recorded fingerprint with the old scope
        at_commit = config_fingerprint(phase, iso, source, old_scope)
        if at_commit != recorded:
            raise RebaselineRefused(
                f"{phase} [{iso}]: commit {commit[:10]}, in force on {label} {date}, gives {at_commit[:12]} with the old scope, the manifest "
                f"recorded {recorded[:12]}: the config of that run is not that commit"
            )
        sources[label] = source

    # B: the keys the scope gained have the same value then and now
    now_values = phase_config_payload(phase, iso, current, additions)
    at_values = {label: phase_config_payload(phase, iso, source, additions) for label, source in sources.items()}
    differing: list[str] = []
    for key, selectors in additions.items():
        for selector in selectors:
            name = selector.replace("{iso}", iso)
            now = _canonical(now_values[key][name])
            by_label = {label: _canonical(values[key][name]) for label, values in at_values.items()}
            proof.keys.append(ConfigRebaselineKey(file=key, selector=name, value_now=now, value_at=by_label))
            differing += [f"{key}:{name} on {label}: {value} (now {now})" for label, value in by_label.items() if value != now]
    if differing:
        raise RebaselineRefused(f"{phase} [{iso}]: a key the scope gained changed since the phase ran: " + "; ".join(differing))
    return proof


def apply(manifest_path: Path, proofs: Sequence[Proof]) -> None:
    """Write the new fingerprints and their proofs into the manifest, in one atomic replace; nothing is written when no proof needs it."""
    pending = [p for p in proofs if not p.already_current]
    if not pending:
        return
    manifest = load_manifest(manifest_path)
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    for proof in pending:
        entry = manifest.phases[proof.phase]
        if entry.config_fingerprint != proof.previous_fingerprint or manifest.country_code != proof.country_code:
            raise RebaselineRefused(f"{proof.phase}: the manifest changed since it was proved")
        manifest.phases[proof.phase] = entry.model_copy(
            update={
                "config_fingerprint": proof.new_fingerprint,
                "config_rebaselines": [*entry.config_rebaselines, proof.record(stamp)],
            }
        )
    temporary = manifest_path.with_name(manifest_path.name + ".tmp")
    temporary.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    replace_durable(temporary, manifest_path)


__all__ = [
    "SCOPE_CHANGES",
    "GitConfigSource",
    "Proof",
    "RebaselineRefused",
    "ScopeChange",
    "apply",
    "commit_in_force",
    "load_manifest",
    "old_scope_of",
    "prove",
]
