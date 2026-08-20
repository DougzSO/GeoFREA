"""Single orchestration mechanism for all GeoFREA pipeline phases.

Replaces geoworld_framework's split design (hand-rolled inline functions
for Phase 1/2a, a centralized PipelineOrchestrator for phases 2b-9) with
one mechanism used from phase 1 onward. See DECISIONS.md 2026-08-20 -
orchestrator + data_quality_audit phase for the full rationale.

Design summary:
    - Every phase returns a Pydantic model (its own output_model), not an
      ad hoc dict. There is no phase exempted from this, unlike legacy's
      phases 6-9 (output_model=None).
    - Each phase execution is wrapped in a single try/except, here in
      Orchestrator.run() — not scattered per phase like legacy's
      individual _run_phase_1_audit()/_run_phase_2a_align() functions.
      A failure produces a PhaseResult(status="failed", ...) and the
      original exception is re-raised (wrapped in PhaseExecutionError)
      after being logged and persisted to the manifest — it is never
      swallowed, and no dependent phase runs afterward.
    - After each successful phase, a run manifest is written to
      outputs/<country_code>/manifest.json. On the next run for the same
      country, phases already recorded as "success" are not re-executed:
      their output is reconstructed from the manifest (via each phase's
      own output_model) and the orchestrator resumes from the first
      phase not yet completed. This avoids re-running a pipeline that
      can take on the order of an hour per country after a late-phase
      failure (see docs/architecture/baseline-manifest.md for BRA's
      real ~56min legacy run time).
    - No implicit cross-phase mutation (the anti-pattern being avoided is
      legacy's _merge_pot_result_into_params, which mutated shared
      `params` after Phase 4 from inside main.py). Each phase receives a
      read-only view of prior phases' results (PhaseContext.prior_results)
      and returns everything it produces as part of its own output. If a
      later phase's output needs to feed into shared state for phases
      after it, that merge is done explicitly by the orchestrator's
      caller (main.py), visibly, not mutated in place here or inside a
      phase.

run_id: the manifest lives at outputs/<country_code>/manifest.json — one
manifest per country, not per invocation/timestamp. A per-invocation
run_id would defeat resumability: a fresh timestamp on every run would
never find the previous run's manifest to resume from. This mirrors
legacy's own outputs/<code>/ layout (main.py's `country_out` variable).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

from geofrea.core.schemas import CountryParams

logger = logging.getLogger("geofrea.core.orchestrator")

T = TypeVar("T", bound=BaseModel)

PhaseStatus = Literal["success", "failed"]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class PhaseResult(BaseModel, Generic[T]):
    """The outcome of executing a single phase, once.

    Args:
        phase: Phase name, matching a RunConfig.phases key.
        status: "success" or "failed". There is no "skipped" status: a
            phase disabled in RunConfig.phases is simply not attempted
            and never gets a PhaseResult (see Orchestrator.run()); a
            phase resumed from a prior successful manifest entry is
            still reported as "success", not a separate resumed state.
        output: The phase's own Pydantic output model instance, or None
            if status is "failed".
        error: str(exception) if status is "failed", else None.
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

    Unlike PhaseResult, `output` is a loose JSON dict rather than a
    typed model: reconstructing the exact typed output on resume is the
    orchestrator's job (via the phase's registered output_model), not
    something the manifest file itself needs to encode.
    """

    model_config = ConfigDict(extra="forbid")

    phase: str
    status: PhaseStatus
    output: dict[str, Any] | None
    error: str | None
    started_at: str
    finished_at: str


class RunManifest(BaseModel):
    """Root schema for outputs/<country_code>/manifest.json."""

    model_config = ConfigDict(extra="forbid")

    country_code: str
    phases: dict[str, PhaseManifestEntry] = {}


@dataclass(frozen=True)
class PhaseContext:
    """Read-only inputs shared by every phase, independent of phase-specific data.

    Phase-specific raw inputs (e.g. audit's raster paths) are NOT part of
    this context — they don't generalize across phases and would force
    the orchestrator to know about every phase's input shape. Instead,
    each PhaseSpec.run closure is built by the caller (main.py) with its
    own phase-specific inputs already bound, and only receives a
    PhaseContext at call time.

    Args:
        country_code: ISO-3166-alpha-3 code being processed.
        country_params: This country's validated CountryParams.
        outputs_dir: Root outputs directory for the whole run (not the
            per-country subdirectory — phases append country_code/... themselves).
        prior_results: Read-only mapping of phase name -> PhaseResult for
            every phase that has already completed successfully in this
            orchestrator run. A phase may read this but the orchestrator
            never mutates a phase's own output on its behalf.
    """

    country_code: str
    country_params: CountryParams
    outputs_dir: Path
    prior_results: Mapping[str, PhaseResult[Any]]


@dataclass(frozen=True)
class PhaseSpec:
    """One phase's registration: its name, output contract, and entry point.

    Args:
        name: Must match a key in RunConfig.phases.
        output_model: The Pydantic model type this phase's `run` returns.
            Used both to validate the live result and to reconstruct a
            typed PhaseResult from the manifest on resume.
        run: Zero-argument-besides-context callable. Phase-specific raw
            inputs must already be bound into this callable (e.g. via
            functools.partial) by whoever builds the PhaseSpec.
    """

    name: str
    output_model: type[BaseModel]
    run: Callable[[PhaseContext], BaseModel]


class PhaseExecutionError(RuntimeError):
    """Raised when a phase's `run` raises, after the failure is recorded.

    Wraps the original exception; str(exc) is what's stored as
    PhaseResult.error/PhaseManifestEntry.error.
    """

    def __init__(self, phase_name: str, original: Exception) -> None:
        super().__init__(f"Phase '{phase_name}' failed: {original}")
        self.phase_name = phase_name
        self.original = original


@dataclass
class Orchestrator:
    """Executes a sequence of PhaseSpecs for one country, with manifest resumability.

    Args:
        outputs_dir: Root outputs directory (manifest lives at
            outputs_dir/country_code/manifest.json).
        country_code: ISO-3166-alpha-3 code being processed.
        country_params: This country's validated CountryParams.
        phases_enabled: RunConfig.phases mapping (phase name -> bool) for
            this run. A phase not present or False is not executed and
            gets no PhaseResult.
    """

    outputs_dir: Path
    country_code: str
    country_params: CountryParams
    phases_enabled: Mapping[str, bool]
    manifest: RunManifest = field(init=False)

    def __post_init__(self) -> None:
        self.manifest = self._load_manifest()

    @property
    def manifest_path(self) -> Path:
        return self.outputs_dir / self.country_code / "manifest.json"

    def _load_manifest(self) -> RunManifest:
        if self.manifest_path.exists():
            return RunManifest.model_validate_json(
                self.manifest_path.read_text(encoding="utf-8")
            )
        return RunManifest(country_code=self.country_code)

    def _write_manifest(self) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            self.manifest.model_dump_json(indent=2), encoding="utf-8"
        )

    def run(self, phase_specs: Sequence[PhaseSpec]) -> dict[str, PhaseResult[Any]]:
        """Run each enabled phase in order, resuming from the manifest where possible.

        Args:
            phase_specs: Ordered phases to attempt this run.

        Returns:
            Mapping of phase name -> PhaseResult, for every phase that
            was either resumed or executed (disabled phases are absent).

        Raises:
            PhaseExecutionError: If any phase's `run` raises. The failure
                is logged and persisted to the manifest before this is
                raised — dependent phases after it are never attempted.
        """
        results: dict[str, PhaseResult[Any]] = {}

        for spec in phase_specs:
            if not self.phases_enabled.get(spec.name, False):
                logger.info(
                    "Phase '%s' disabled in settings.yaml — not run.", spec.name
                )
                continue

            existing = self.manifest.phases.get(spec.name)
            if existing is not None and existing.status == "success":
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
                    "Phase '%s' already completed — resumed from manifest.",
                    spec.name,
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
            except Exception as exc:
                finished_at = _now_iso()
                result: PhaseResult[Any] = PhaseResult(
                    phase=spec.name,
                    status="failed",
                    output=None,
                    error=str(exc),
                    started_at=started_at,
                    finished_at=finished_at,
                )
                results[spec.name] = result
                self.manifest.phases[spec.name] = PhaseManifestEntry(
                    phase=spec.name,
                    status="failed",
                    output=None,
                    error=str(exc),
                    started_at=started_at,
                    finished_at=finished_at,
                )
                self._write_manifest()
                logger.exception("Phase '%s' failed", spec.name)
                raise PhaseExecutionError(spec.name, exc) from exc

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
            self.manifest.phases[spec.name] = PhaseManifestEntry(
                phase=spec.name,
                status="success",
                output=output.model_dump(mode="json"),
                error=None,
                started_at=started_at,
                finished_at=finished_at,
            )
            self._write_manifest()
            logger.info("Phase '%s' completed.", spec.name)

        return results
