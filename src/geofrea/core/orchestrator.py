"""Single orchestration mechanism for all GeoFREA pipeline phases.

Design summary (rebuilt 2026-09-21 for METHODOLOGY A-01, A-02, A-03,
A-09 — see docs/phases/core.md D-core-001):
    - Every phase declares `requires`/`produces` artifact keys. The
      orchestrator validates the resulting graph before running
      anything (missing producer, cycle, duplicate producer) and
      determines execution order by topological sort, not by list
      position.
    - Each phase registers its own output artifacts via
      `PhaseContext.register_artifact()`. After a phase runs, the
      registered keys must exactly match its declared `produces`.
    - The manifest (outputs/<country_code>/manifest.json) records both
      per-phase outcomes and a per-artifact registry (path, sha256,
      size, mtime, schema_version, producing phase, run_id). A phase
      resumed from the manifest has its artifacts' integrity checked
      (size/mtime/hash) before being trusted — a mismatch raises
      ArtifactIntegrityError rather than silently recomputing.
    - A phase failure marks only that phase and its transitive
      dependents as not attempted (status "skipped_upstream_failed");
      independent branches still run.
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

from geofrea.core.schemas import CountryParams

logger = logging.getLogger("geofrea.core.orchestrator")

T = TypeVar("T", bound=BaseModel)

PhaseStatus = Literal["success", "failed", "skipped_upstream_failed"]

_HASH_CHUNK_SIZE = 8 * 1024 * 1024
_LARGE_FILE_LOG_THRESHOLD_BYTES = 500 * 1024 * 1024
_MANIFEST_SCHEMA_VERSION = "2.0"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class MissingProducerError(RuntimeError):
    """A PhaseSpec requires an artifact key no registered phase produces."""


class DependencyCycleError(RuntimeError):
    """The declared requires/produces graph contains a cycle."""


class DuplicateProducerError(RuntimeError):
    """Two PhaseSpecs declare the same artifact key in `produces`."""


class UndeclaredArtifactMissingError(RuntimeError):
    """A phase's run() did not register an artifact listed in its `produces`."""


class UnexpectedArtifactError(RuntimeError):
    """A phase's run() registered an artifact key not listed in its `produces`."""


class LegacyManifestError(RuntimeError):
    """An on-disk manifest predates schema_version 2.0; no migration exists.

    Delete the manifest and rerun the pipeline for this country instead.
    """


class ArtifactIntegrityError(RuntimeError):
    """A resumed artifact's file is missing or no longer matches its recorded hash."""


class StaleManifestEntryError(RuntimeError):
    """A phase's successful manifest entry no longer matches its current PhaseSpec.

    Raised on resume when either:
      - the artifact keys recorded for this phase (manifest.artifacts
        entries with `phase == spec.name`) no longer equal exactly
        `spec.produces` (a produces contract change since the entry was
        written — e.g. E4's per-raster grid_alignment keys landing on
        top of an older single-summary entry); or
      - a recorded artifact's `schema_version` no longer matches what
        `spec.produces_schema_versions` now declares for that key.

    Not auto-recovered: the fix is `force_rerun=True` targeting this
    phase (or a phase that transitively requires it), which discards
    the stale entry and reruns it — see RunConfig.force_rerun.
    """


def _sha256_file(path: Path) -> str:
    """Hash a file in fixed-size blocks, logging progress for large files."""
    size = path.stat().st_size
    log_progress = size > _LARGE_FILE_LOG_THRESHOLD_BYTES
    digest = hashlib.sha256()
    read_bytes = 0
    with path.open("rb") as f:
        while chunk := f.read(_HASH_CHUNK_SIZE):
            digest.update(chunk)
            read_bytes += len(chunk)
            if log_progress:
                logger.info("Hashing %s: %d/%d bytes", path, read_bytes, size)
    return digest.hexdigest()


def compute_git_commit(repo_root: Path) -> str:
    """Return `git rev-parse HEAD` for repo_root."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def compute_dirty(repo_root: Path) -> bool:
    """True if `git status --porcelain` reports changes under src/ or config/."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "src/", "config/"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(result.stdout.strip())


def compute_run_id(resolved_config: str, methodology_version: str, git_commit: str) -> str:
    """sha256 of the resolved configuration, METHODOLOGY version, and git commit."""
    digest = hashlib.sha256()
    digest.update(resolved_config.encode("utf-8"))
    digest.update(b"\0")
    digest.update(methodology_version.encode("utf-8"))
    digest.update(b"\0")
    digest.update(git_commit.encode("utf-8"))
    return digest.hexdigest()


class PhaseResult(BaseModel, Generic[T]):
    """The outcome of executing (or resuming, or skipping) a single phase.

    Args:
        phase: Phase name, matching a PhaseSpec.name.
        status: "success", "failed", or "skipped_upstream_failed" (a
            transitive dependent of a failed phase, never attempted).
        output: The phase's own Pydantic output model instance, or None
            if status is not "success".
        error: str(exception) if status is "failed"; a message naming
            the failed upstream phase if "skipped_upstream_failed";
            None if "success".
        started_at: ISO-8601 UTC timestamp.
        finished_at: ISO-8601 UTC timestamp.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    phase: str
    status: PhaseStatus
    output: T | None
    error: str | None
    started_at: str
    finished_at: str


class PhaseManifestEntry(BaseModel):
    """The on-disk (manifest.json) record of one phase's outcome.

    Args:
        consumed_run_ids: For a "success" entry, the run_id of every
            upstream artifact this phase's run() read (keyed by
            artifact key, i.e. one entry per key in this phase's
            PhaseSpec.requires that had a manifest artifact at the time
            it ran). Empty for "failed"/"skipped_upstream_failed"
            entries and for phases with no requires. Lineage only,
            never blocks a resume by itself — see Orchestrator.run()'s
            lineage-drift warning.
    """

    model_config = ConfigDict(extra="forbid")

    phase: str
    status: PhaseStatus
    output: dict[str, Any] | None
    error: str | None
    started_at: str
    finished_at: str
    consumed_run_ids: dict[str, str] = {}


class ArtifactEntry(BaseModel):
    """The on-disk (manifest.json) record of one registered artifact.

    Args:
        key: Artifact key, matching an entry in some PhaseSpec.produces.
        path: Filesystem path of the artifact, as a string (JSON-
            portable).
        sha256: Content hash, computed at registration and reused on a
            later registration at the same path when size_bytes and
            mtime_ns are unchanged.
        size_bytes: File size at hash time.
        mtime_ns: File modification time (nanoseconds) at hash time.
        schema_version: Schema version of the artifact's content.
        phase: Name of the phase that produced this artifact.
        run_id: run_id of the run that produced this artifact.
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    path: str
    sha256: str
    size_bytes: int
    mtime_ns: int
    schema_version: str
    phase: str
    run_id: str


class RunManifest(BaseModel):
    """Root schema for outputs/<country_code>/manifest.json.

    schema_version is fixed at "2.0" (see LegacyManifestError): a
    manifest written by the pre-A-01/A-02 orchestrator has no
    schema_version key at all and is treated as unreadable, not
    migrated in place.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["2.0"] = _MANIFEST_SCHEMA_VERSION
    run_id: str
    dirty: bool
    country_code: str
    phases: dict[str, PhaseManifestEntry] = {}
    artifacts: dict[str, ArtifactEntry] = {}


@dataclass(frozen=True)
class PhaseContext:
    """Read-only inputs shared by every phase, plus the artifact-registration sink.

    Args:
        country_code: ISO-3166-alpha-3 code being processed.
        country_params: This country's validated CountryParams.
        outputs_dir: Root outputs directory for the whole run.
        prior_results: Read-only mapping of phase name -> PhaseResult for
            every phase already completed (resumed or freshly run) in
            this orchestrator invocation.
        _artifact_sink: Mutable dict a running phase's `register_artifact`
            calls append to. Populated fresh by the orchestrator before
            each phase's `run()` is invoked; not meant to be constructed
            by callers directly (defaults to an empty dict so existing
            call sites that build PhaseContext by hand still work).
    """

    country_code: str
    country_params: CountryParams
    outputs_dir: Path
    prior_results: Mapping[str, PhaseResult[Any]]
    _artifact_sink: dict[str, tuple[Path, str]] = field(default_factory=dict)

    def register_artifact(self, key: str, path: Path, schema_version: str) -> None:
        """Record that the currently running phase produced `path` under `key`.

        Args:
            key: Artifact key; must be one of the running phase's
                declared `produces` (enforced by the orchestrator after
                `run()` returns, not here).
            path: Filesystem path of the artifact. Must exist by the
                time the phase's `run()` returns.
            schema_version: Schema version of the artifact's content.
        """
        self._artifact_sink[key] = (Path(path), schema_version)


@dataclass(frozen=True)
class PhaseSpec:
    """One phase's registration: its name, dependency contract, output contract, and entry point.

    Args:
        name: Phase name.
        output_model: The Pydantic model type this phase's `run` returns.
        run: Zero-argument-besides-context callable. Phase-specific raw
            inputs must already be bound into this callable by whoever
            builds the PhaseSpec.
        requires: Artifact keys this phase reads, produced by some other
            registered PhaseSpec.
        produces: Artifact keys this phase's `run` must register via
            `PhaseContext.register_artifact`, exactly.
        produces_schema_versions: Optional expected schema_version per
            produces key. A key absent here is not schema-version-
            checked on resume (only its presence in produces is).
            Populated by callers who want a schema bump on an artifact's
            content to invalidate old manifest entries — see
            StaleManifestEntryError.
    """

    name: str
    output_model: type[BaseModel]
    run: Callable[[PhaseContext], BaseModel]
    requires: frozenset[str] = frozenset()
    produces: frozenset[str] = frozenset()
    produces_schema_versions: Mapping[str, str] = field(default_factory=dict)


class PhaseExecutionError(RuntimeError):
    """Raised only for a phase failure the orchestrator cannot record and continue past.

    Normal phase failures are recorded as PhaseResult(status="failed",
    ...) and do NOT raise (see A-09: independent branches keep running).
    This is reserved for structural failures (e.g. a phase omits a
    required artifact registration) that indicate a broken PhaseSpec,
    not a data/runtime failure of the phase's own logic.
    """

    def __init__(self, phase_name: str, original: Exception) -> None:
        super().__init__(f"Phase '{phase_name}' failed: {original}")
        self.phase_name = phase_name
        self.original = original


def _validate_and_order(phase_specs: Sequence[PhaseSpec]) -> list[PhaseSpec]:
    """Validate the requires/produces graph and return phases in topological order.

    Ties are broken by phase name, so a shuffled `phase_specs` input
    always yields the same order.

    Raises:
        DuplicateProducerError: Two specs declare the same produces key.
        MissingProducerError: A requires key has no producer among
            phase_specs.
        DependencyCycleError: The dependency graph has a cycle.
    """
    by_name = {spec.name: spec for spec in phase_specs}

    producer_of: dict[str, str] = {}
    for spec in phase_specs:
        for key in spec.produces:
            if key in producer_of:
                raise DuplicateProducerError(
                    f"Artifact key '{key}' is produced by both "
                    f"'{producer_of[key]}' and '{spec.name}'."
                )
            producer_of[key] = spec.name

    deps: dict[str, set[str]] = {}
    for spec in phase_specs:
        dep_names: set[str] = set()
        for key in spec.requires:
            if key not in producer_of:
                raise MissingProducerError(
                    f"Phase '{spec.name}' requires artifact key '{key}', "
                    "which no registered phase produces."
                )
            dep_names.add(producer_of[key])
        deps[spec.name] = dep_names

    consumers: dict[str, list[str]] = {name: [] for name in by_name}
    in_degree: dict[str, int] = {}
    for name, dep_names in deps.items():
        in_degree[name] = len(dep_names)
        for dep_name in dep_names:
            consumers[dep_name].append(name)

    import heapq

    ready = [name for name, degree in in_degree.items() if degree == 0]
    heapq.heapify(ready)
    order: list[str] = []
    remaining = dict(in_degree)

    while ready:
        name = heapq.heappop(ready)
        order.append(name)
        for consumer in sorted(consumers[name]):
            remaining[consumer] -= 1
            if remaining[consumer] == 0:
                heapq.heappush(ready, consumer)

    if len(order) != len(by_name):
        cyclic = sorted(set(by_name) - set(order))
        raise DependencyCycleError(f"Cycle detected among phases: {cyclic}")

    return [by_name[name] for name in order]


def _transitive_closure(
    start: set[str], edges: Mapping[str, set[str]]
) -> set[str]:
    """Follow `edges` (name -> set of related names) from `start`, including it."""
    seen = set(start)
    stack = list(start)
    while stack:
        name = stack.pop()
        for neighbor in edges.get(name, ()):
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    return seen


@dataclass
class Orchestrator:
    """Executes a DAG of PhaseSpecs for one country, with manifest resumability.

    Args:
        outputs_dir: Root outputs directory (manifest lives at
            outputs_dir/country_code/manifest.json).
        country_code: ISO-3166-alpha-3 code being processed.
        country_params: This country's validated CountryParams.
        target_phases: Phase names the caller wants executed. The
            orchestrator also runs (or resumes) every phase these
            transitively require, to satisfy the graph.
        force_rerun: If True, target_phases and every phase that
            transitively depends on them (per requires/produces) are
            re-executed even if already recorded as successful.
        run_id: This run's identifier (see compute_run_id).
        dirty: Whether the working tree has uncommitted changes under
            src/ or config/ (see compute_dirty).
    """

    outputs_dir: Path
    country_code: str
    country_params: CountryParams
    target_phases: Sequence[str]
    force_rerun: bool
    run_id: str
    dirty: bool
    manifest: RunManifest = field(init=False)

    def __post_init__(self) -> None:
        self.manifest = self._load_manifest()

    @property
    def manifest_path(self) -> Path:
        return self.outputs_dir / self.country_code / "manifest.json"

    def _load_manifest(self) -> RunManifest:
        if not self.manifest_path.exists():
            return RunManifest(
                run_id=self.run_id, dirty=self.dirty, country_code=self.country_code
            )
        raw = self.manifest_path.read_text(encoding="utf-8")
        import json

        data = json.loads(raw)
        if data.get("schema_version") != _MANIFEST_SCHEMA_VERSION:
            raise LegacyManifestError(
                f"{self.manifest_path} has schema_version "
                f"{data.get('schema_version')!r}, not '{_MANIFEST_SCHEMA_VERSION}'. "
                "There is no migration path — delete this manifest and rerun the "
                "pipeline for this country from scratch."
            )
        return RunManifest.model_validate(data)

    def _write_manifest(self) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            self.manifest.model_dump_json(indent=2), encoding="utf-8"
        )

    def _hash_with_reuse(self, key: str, path: Path) -> tuple[str, int, int]:
        """Hash `path`, reusing a prior sha256 for this key if size/mtime match."""
        stat = path.stat()
        size_bytes = stat.st_size
        mtime_ns = stat.st_mtime_ns
        existing = self.manifest.artifacts.get(key)
        if (
            existing is not None
            and existing.path == str(path)
            and existing.size_bytes == size_bytes
            and existing.mtime_ns == mtime_ns
        ):
            return existing.sha256, size_bytes, mtime_ns
        return _sha256_file(path), size_bytes, mtime_ns

    def _check_resume_is_not_stale(self, spec: PhaseSpec) -> None:
        """Raise StaleManifestEntryError if spec's recorded entry no longer fits spec.

        See StaleManifestEntryError's docstring for the two checks.
        """
        recorded_keys = {
            entry.key for entry in self.manifest.artifacts.values() if entry.phase == spec.name
        }
        if recorded_keys != spec.produces:
            missing = sorted(spec.produces - recorded_keys)
            extra = sorted(recorded_keys - spec.produces)
            raise StaleManifestEntryError(
                f"Phase '{spec.name}' has a successful manifest entry, but its recorded "
                f"artifact keys ({sorted(recorded_keys)}) no longer match this PhaseSpec's "
                f"produces ({sorted(spec.produces)}) — missing={missing}, extra={extra}. "
                f"Pass force_rerun=True targeting '{spec.name}' to discard the stale entry "
                "and rerun it."
            )

        for key, expected_schema_version in spec.produces_schema_versions.items():
            entry = self.manifest.artifacts.get(key)
            if entry is not None and entry.schema_version != expected_schema_version:
                raise StaleManifestEntryError(
                    f"Phase '{spec.name}' artifact '{key}' has schema_version "
                    f"{entry.schema_version!r} recorded, but this PhaseSpec now expects "
                    f"{expected_schema_version!r}. Pass force_rerun=True targeting "
                    f"'{spec.name}' to discard the stale entry and rerun it."
                )

    def _warn_on_lineage_drift(self, spec: PhaseSpec, existing: PhaseManifestEntry) -> None:
        """Log (never raise) when a resumed phase's upstream lineage has moved on."""
        for key, recorded_run_id in existing.consumed_run_ids.items():
            current_entry = self.manifest.artifacts.get(key)
            if current_entry is not None and current_entry.run_id != recorded_run_id:
                logger.warning(
                    "Phase '%s' resumed, but upstream artifact '%s' was produced by "
                    "run_id %s when '%s' last ran and is now run_id %s. Resuming anyway "
                    "— lineage drift does not block.",
                    spec.name, key, recorded_run_id, spec.name, current_entry.run_id,
                )

    def _verify_artifact_integrity(self, key: str) -> None:
        entry = self.manifest.artifacts.get(key)
        if entry is None:
            return
        path = Path(entry.path)
        if not path.exists():
            raise ArtifactIntegrityError(
                f"Artifact '{key}' (phase '{entry.phase}') is recorded at "
                f"{path}, but the file no longer exists. Not recomputing."
            )
        actual_sha256 = _sha256_file(path)
        if actual_sha256 != entry.sha256:
            raise ArtifactIntegrityError(
                f"Artifact '{key}' (phase '{entry.phase}') at {path} no longer "
                f"matches its recorded sha256 ({entry.sha256} -> {actual_sha256}). "
                "Not recomputing."
            )

    def run(self, phase_specs: Sequence[PhaseSpec]) -> dict[str, PhaseResult[Any]]:
        """Run the phases needed to satisfy target_phases, resuming where possible.

        Args:
            phase_specs: Every registered phase (order does not matter;
                execution order is derived from requires/produces).

        Returns:
            Mapping of phase name -> PhaseResult, for every phase that
            was attempted, resumed, or skipped due to an upstream
            failure. Phases outside the transitive closure of
            target_phases are absent.
        """
        ordered = _validate_and_order(phase_specs)
        by_name = {spec.name: spec for spec in ordered}

        producer_of: dict[str, str] = {}
        for spec in ordered:
            for key in spec.produces:
                producer_of[key] = spec.name

        deps: dict[str, set[str]] = {
            spec.name: {producer_of[key] for key in spec.requires} for spec in ordered
        }
        consumers: dict[str, set[str]] = {spec.name: set() for spec in ordered}
        for name, dep_names in deps.items():
            for dep_name in dep_names:
                consumers[dep_name].add(name)

        unknown_targets = [name for name in self.target_phases if name not in by_name]
        if unknown_targets:
            raise MissingProducerError(
                f"run.target_phases names phases not registered: {unknown_targets}"
            )

        target_set = set(self.target_phases)
        needed = _transitive_closure(target_set, deps)
        forced = _transitive_closure(target_set, consumers) if self.force_rerun else set()
        to_attempt = {name for name in needed | forced if name in by_name}
        attempt_order = [spec for spec in ordered if spec.name in to_attempt]

        results: dict[str, PhaseResult[Any]] = {}

        for spec in attempt_order:
            failed_deps = [
                dep_name
                for dep_name in deps[spec.name]
                if dep_name in results
                and results[dep_name].status in ("failed", "skipped_upstream_failed")
            ]
            if failed_deps:
                now = _now_iso()
                result: PhaseResult[Any] = PhaseResult(
                    phase=spec.name,
                    status="skipped_upstream_failed",
                    output=None,
                    error=f"Upstream phase(s) did not succeed: {failed_deps}",
                    started_at=now,
                    finished_at=now,
                )
                results[spec.name] = result
                self.manifest.phases[spec.name] = PhaseManifestEntry(**result.model_dump())
                self._write_manifest()
                logger.warning(
                    "Phase '%s' skipped — upstream failed: %s", spec.name, failed_deps
                )
                continue

            must_force = self.force_rerun and spec.name in forced
            existing = self.manifest.phases.get(spec.name)
            if not must_force and existing is not None and existing.status == "success":
                self._check_resume_is_not_stale(spec)
                for key in spec.produces:
                    self._verify_artifact_integrity(key)
                self._warn_on_lineage_drift(spec, existing)
                output = (
                    spec.output_model.model_validate(existing.output)
                    if existing.output is not None
                    else None
                )
                results[spec.name] = PhaseResult(
                    phase=spec.name,
                    status="success",
                    output=output,
                    error=None,
                    started_at=existing.started_at,
                    finished_at=existing.finished_at,
                )
                logger.info(
                    "Phase '%s' already completed — resumed from manifest.", spec.name
                )
                continue

            context = PhaseContext(
                country_code=self.country_code,
                country_params=self.country_params,
                outputs_dir=self.outputs_dir,
                prior_results=results,
            )
            started_at = _now_iso()

            try:
                output = spec.run(context)

                registered_keys = set(context._artifact_sink.keys())
                missing = spec.produces - registered_keys
                if missing:
                    raise UndeclaredArtifactMissingError(
                        f"Phase '{spec.name}' did not register artifact(s) "
                        f"{sorted(missing)}, declared in its produces."
                    )
                extra = registered_keys - spec.produces
                if extra:
                    raise UnexpectedArtifactError(
                        f"Phase '{spec.name}' registered artifact(s) "
                        f"{sorted(extra)}, not declared in its produces."
                    )

                new_artifacts: dict[str, ArtifactEntry] = {}
                for key, (path, schema_version) in context._artifact_sink.items():
                    sha256, size_bytes, mtime_ns = self._hash_with_reuse(key, path)
                    new_artifacts[key] = ArtifactEntry(
                        key=key,
                        path=str(path),
                        sha256=sha256,
                        size_bytes=size_bytes,
                        mtime_ns=mtime_ns,
                        schema_version=schema_version,
                        phase=spec.name,
                        run_id=self.run_id,
                    )
            except Exception as exc:
                finished_at = _now_iso()
                result = PhaseResult(
                    phase=spec.name,
                    status="failed",
                    output=None,
                    error=str(exc),
                    started_at=started_at,
                    finished_at=finished_at,
                )
                results[spec.name] = result
                self.manifest.phases[spec.name] = PhaseManifestEntry(**result.model_dump())
                self._write_manifest()
                logger.exception("Phase '%s' failed", spec.name)
                continue

            finished_at = _now_iso()
            result = PhaseResult(
                phase=spec.name,
                status="success",
                output=output,
                error=None,
                started_at=started_at,
                finished_at=finished_at,
            )
            results[spec.name] = result
            consumed_run_ids = {
                key: self.manifest.artifacts[key].run_id
                for key in spec.requires
                if key in self.manifest.artifacts
            }
            self.manifest.phases[spec.name] = PhaseManifestEntry(
                phase=spec.name,
                status="success",
                output=output.model_dump(mode="json"),
                error=None,
                started_at=started_at,
                finished_at=finished_at,
                consumed_run_ids=consumed_run_ids,
            )
            self.manifest.artifacts.update(new_artifacts)
            self._write_manifest()
            logger.info("Phase '%s' completed.", spec.name)

        return results
