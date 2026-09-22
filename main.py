"""main.py — GeoFREA entry point.

Loads config/parameters.json + config/settings.yaml, resolves which
countries to run (RunConfig.countries empty = every country present in
parameters.json), and runs the orchestrator's registered phases for
each. The orchestrator itself (src/geofrea/core/orchestrator.py) is
generic and does not need redesigning as phases are added.

data_acquisition -> data_quality_audit wiring (2026-08-25, see
DECISIONS.md same date - data_acquisition activation): the audit
PhaseSpec's `run` is now a per-context closure (_audit_run below), not
a functools.partial with a hardcoded AuditInputs() — it reads
context.prior_results["data_acquisition"].output at call time (a
partial can't do this: it binds `inputs` before any phase has run) and
converts it via geofrea.data_acquisition.adapter's
acquisition_result_to_audit_inputs(). When data_acquisition did not run
this pipeline (disabled in settings.yaml, standalone audit run),
_build_audit_inputs() falls back to AuditInputs() empty, unchanged from
the prior skeleton-stage behavior.

UnwiredPhasesError, which used to block enabling data_acquisition and
data_quality_audit together, was REMOVED this same stage (not relaxed
to a warning, not kept) — see DECISIONS.md 2026-08-25 for the full
rationale. Summary: its only justification was that audit would
silently run against a hardcoded-empty AuditInputs regardless of what
data_acquisition produced; now that the two are genuinely wired, that
is no longer true — layers without a real fetch yet correctly surface
as `None`/missing in the audit report (inspect_raster()/
inspect_vector_layer() already handle that gracefully), which is the
audit doing its job, not a misleading run.

grid_alignment wiring (2026-09-08, see DECISIONS.md same date - grid_
alignment orchestrator wiring): registered as the THIRD PhaseSpec, but
its `run` closure reads ONLY context.prior_results["data_acquisition"]
— never data_quality_audit's. This was a deliberate design decision
closed in an earlier stage of this same session (Passo 1 of the
grid_alignment port): grid_alignment must keep working with
data_quality_audit disabled in settings.yaml, paying at most a cold
clip-cache cost, never failing outright. List position (third, after
data_quality_audit) is about readable pipeline ordering only — it does
NOT imply a data dependency the same way data_acquisition ->
data_quality_audit's position does. Same per-context-closure pattern as
_audit_run below, not a functools.partial with eagerly-bound inputs —
that eager-binding shape is exactly what UnwiredPhasesError was
protecting against in 2026-08-25 (see that DECISIONS.md entry): a
partial can only bind inputs that already exist when
_build_phase_specs() runs, before ANY phase has executed, which is
correct for data_acquisition (no phase-specific inputs at all) but
would be wrong here — grid_alignment's inputs (AcquisitionResult) only
exist once the orchestrator has actually run that phase for this
country.

Usage:
    python main.py
"""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

from pydantic import BaseModel

from geofrea.core.config_loader import load_parameters, load_settings
from geofrea.core.orchestrator import (
    Orchestrator,
    PhaseContext,
    PhaseSpec,
    compute_dirty,
    compute_git_commit,
    compute_run_id,
)
from geofrea.core.paths import log_path, outputs_dir
from geofrea.core.schemas import CriteriaParams, ResolutionsConfig, SettingsFile
from geofrea.data_acquisition.adapter import acquisition_result_to_audit_inputs
from geofrea.data_acquisition.phase import run_acquisition_phase
from geofrea.data_acquisition.schemas import AcquisitionResult
from geofrea.data_quality_audit.audit import run_audit_phase
from geofrea.data_quality_audit.schemas import AuditInputs, AuditResult
from geofrea.grid_alignment.adapter import acquisition_result_to_grid_alignment_inputs
from geofrea.grid_alignment.alignment import run_grid_alignment_phase
from geofrea.grid_alignment.schemas import GridAlignmentInputs, GridAlignmentResult
from geofrea.suitability_criteria.adapter import build_suitability_criteria_inputs
from geofrea.suitability_criteria.phase import run_suitability_criteria_phase
from geofrea.suitability_criteria.schemas import (
    SuitabilityCriteriaInputs,
    SuitabilityCriteriaResult,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("geofrea.main")

REPO_ROOT = Path(__file__).resolve().parent
PARAMETERS_JSON = REPO_ROOT / "config" / "parameters.json"
SETTINGS_YAML = REPO_ROOT / "config" / "settings.yaml"
METHODOLOGY_MD = REPO_ROOT / "docs" / "METHODOLOGY.md"

_METHODOLOGY_VERSION_RE = re.compile(r"^\|\s*Version\s*\|\s*([0-9.]+)\s*\|\s*$", re.MULTILINE)


def _read_methodology_version(path: Path) -> str:
    """Parse the `| Version | x.y.z |` row from METHODOLOGY.md's header table."""
    match = _METHODOLOGY_VERSION_RE.search(path.read_text(encoding="utf-8"))
    if match is None:
        raise RuntimeError(f"Could not find a Version row in {path}.")
    return match.group(1)


def _register_json_artifact(
    context: PhaseContext, key: str, output: BaseModel, schema_version: str = "1.0"
) -> None:
    """Dump `output` as JSON and register it as the artifact identified by `key`.

    Each migrated phase's real outputs already exist on disk as
    individual rasters/vectors, written by that phase's own code
    (unchanged here). This JSON dump is a single, hashable, resumable
    artifact file representing the whole phase output for the artifact
    registry (METHODOLOGY A-02) — it does not replace or duplicate the
    underlying raster/vector writers.
    """
    artifact_dir = context.outputs_dir / context.country_code / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / f"{key}.json"
    path.write_text(output.model_dump_json(indent=2), encoding="utf-8")
    context.register_artifact(key, path, schema_version)


def _build_audit_inputs(context: PhaseContext) -> AuditInputs:
    """Build AuditInputs from data_acquisition's output, if it ran this pipeline.

    data_quality_audit can also run standalone (data_acquisition
    disabled in settings.yaml) — e.g. an ad hoc audit of manually
    placed local files. In that case there is nothing in
    context.prior_results to adapt, so this falls back to AuditInputs()
    empty, exactly as main.py behaved before data_acquisition had any
    real fetch logic.

    Args:
        context: The audit phase's PhaseContext, as passed by
            Orchestrator.run() — prior_results contains every
            successfully-completed earlier phase's PhaseResult
            (resumed-from-manifest or freshly run, no distinction here).

    Returns:
        Real AuditInputs adapted from data_acquisition's output, or
        AuditInputs() empty if data_acquisition did not run.
    """
    acquisition_result = context.prior_results.get("data_acquisition")
    if acquisition_result is None or acquisition_result.output is None:
        return AuditInputs()
    return acquisition_result_to_audit_inputs(acquisition_result.output)


_AUDIT_REPORT_SCHEMA_VERSION = "2.0"  # bumped 2026-09-21: VectorLayerSummary.status
# gained read_error/processing_error, replacing the single "error" value
# (see docs/phases/core.md, docs/phases/F1b_data_quality_audit.md) — an
# old "1.0" audit_report entry cannot be reconstructed into the current
# AuditResult schema, so a stale one must be rejected on resume
# (StaleManifestEntryError via produces_schema_versions below), not
# silently misvalidated.


def _audit_run(context: PhaseContext) -> AuditResult:
    result = run_audit_phase(context, inputs=_build_audit_inputs(context))
    _register_json_artifact(context, "audit_report", result, _AUDIT_REPORT_SCHEMA_VERSION)
    return result


def _build_grid_alignment_inputs(
    context: PhaseContext, resolutions: ResolutionsConfig
) -> GridAlignmentInputs:
    """Build GridAlignmentInputs from data_acquisition's output.

    No RuntimeError guard here (removed 2026-09-21, see docs/phases/
    core.md D-core-001): grid_alignment's PhaseSpec declares
    requires={"layer_registry"}, produced only by data_acquisition, so
    the orchestrator's graph validation and dependency-skip logic
    (Orchestrator.run()) already guarantee data_acquisition succeeded
    before this closure is ever called — the DAG covers what the
    RuntimeError used to guard against.

    Args:
        context: The grid_alignment phase's PhaseContext, as passed by
            Orchestrator.run().
        resolutions: settings.yaml's `geospatial.resolutions` (see
            docs/DECISIONS.md 2026-09-09, grid_alignment Passo 4 item 3).

    Returns:
        Real GridAlignmentInputs adapted from data_acquisition's output.

    Raises:
        GridAlignmentRequiresBordersError: If data_acquisition ran but
            its AcquisitionResult has no usable `borders` layer (see
            grid_alignment/adapter.py).
    """
    acquisition_output = context.prior_results["data_acquisition"].output
    return acquisition_result_to_grid_alignment_inputs(acquisition_output, resolutions)


def _build_suitability_criteria_inputs(
    context: PhaseContext, criteria: CriteriaParams
) -> SuitabilityCriteriaInputs:
    """Build suitability_criteria's input from grid_alignment + data_acquisition.

    No RuntimeError guards here (removed 2026-09-21, see docs/phases/
    core.md D-core-001): suitability_criteria's PhaseSpec declares
    requires={"aligned_rasters", "layer_registry"}, produced only by
    grid_alignment and data_acquisition respectively — the
    orchestrator's graph validation and dependency-skip logic already
    guarantee both succeeded before this closure is ever called.

    Args:
        context: The suitability_criteria phase's PhaseContext.
        criteria: The global CriteriaParams block from parameters.json,
            closed over by the phase spec (same per-context-closure
            pattern as `resolutions` for grid_alignment).

    Returns:
        Real SuitabilityCriteriaInputs.
    """
    grid_output = context.prior_results["grid_alignment"].output
    acquisition_output = context.prior_results["data_acquisition"].output
    return build_suitability_criteria_inputs(
        grid_output,
        acquisition_output,
        criteria,
        context.country_params.criteria,
    )


def _data_acquisition_run(context: PhaseContext) -> AcquisitionResult:
    result = run_acquisition_phase(context)
    _register_json_artifact(context, "layer_registry", result)
    return result


# GridAlignmentResult's raster fields registered individually (METHODOLOGY
# A-02, 2026-09-21 — see docs/phases/core.md D-core-003). Excludes
# `seismic`: METHODOLOGY S-08 puts the seismic hazard layer out of scope,
# so GridAlignmentResult.seismic is always None — never a real artifact
# to register, unlike the other 11 fields, which real F1 data resolves
# for every country currently in scope (PRT, BRA; see docs/PROGRESS.json).
_ALIGNED_RASTER_LAYER_KEYS = (
    "elevation",
    "slope",
    "solar",
    "wind",
    "land_cover",
    "population",
    "roads",
    "grid",
    "lakes",
    "rivers",
    "plants",
)


def _register_aligned_rasters(context: PhaseContext, result: GridAlignmentResult) -> None:
    """Register each of grid_alignment's raster outputs as its own artifact.

    A layer that resolved to None (no source data for this country) is
    not registered — see _ALIGNED_RASTER_LAYER_KEYS' docstring note for
    why this is safe for PRT/BRA today, and the known limitation this
    creates for a future country missing one of these layers (recorded
    in docs/phases/core.md Known issues).
    """
    for layer_key in _ALIGNED_RASTER_LAYER_KEYS:
        path = getattr(result, layer_key)
        if path is not None:
            context.register_artifact(f"aligned/{layer_key}", path, "1.0")


def _build_phase_specs(
    resolutions: ResolutionsConfig, criteria: CriteriaParams
) -> list[PhaseSpec]:
    """Registered phases, with their requires/produces artifact contracts.

    Execution order is no longer this list's order: the Orchestrator
    derives it from each PhaseSpec's requires/produces (METHODOLOGY
    A-01, docs/phases/core.md D-core-001). data_quality_audit and
    grid_alignment both require only "layer_registry" (data_acquisition's
    output) — neither requires the other's output, preserving the
    independence grid_alignment's own closure has always relied on (see
    _build_grid_alignment_inputs, which reads only
    context.prior_results["data_acquisition"]).

    grid_alignment registers one artifact per raster field
    ("aligned/<layer>", see _ALIGNED_RASTER_LAYER_KEYS) plus the
    "aligned_rasters" JSON summary of the whole GridAlignmentResult.
    data_acquisition and data_quality_audit still register only their
    own output-model summary ("layer_registry", "audit_report") — F1's
    AcquiredLayer entries have no per-layer content to hash beyond the
    resolved path itself (see OQ-024, docs/OPEN_QUESTIONS.md).

    suitability_criteria (F2b) produces only its own output-model
    artifact ("suitability_criteria_result"), not a per-layer
    breakdown — a temporary exception, see docs/phases/core.md Known
    issues, pending the Estágio H rebuild of F2b into siting_layers.

    Args:
        resolutions: settings.yaml's `geospatial.resolutions`, closed
            over by grid_alignment's run closure (2026-09-09, see
            docs/DECISIONS.md same date, grid_alignment Passo 4 item 3).

    Returns:
        The registered PhaseSpecs.
    """

    def grid_alignment_run(context: PhaseContext) -> GridAlignmentResult:
        result = run_grid_alignment_phase(
            context, inputs=_build_grid_alignment_inputs(context, resolutions)
        )
        _register_json_artifact(context, "aligned_rasters", result)
        _register_aligned_rasters(context, result)
        return result

    def suitability_criteria_run(context: PhaseContext) -> SuitabilityCriteriaResult:
        result = run_suitability_criteria_phase(
            context, inputs=_build_suitability_criteria_inputs(context, criteria)
        )
        _register_json_artifact(context, "suitability_criteria_result", result)
        return result

    return [
        PhaseSpec(
            name="data_acquisition",
            output_model=AcquisitionResult,
            run=_data_acquisition_run,
            requires=frozenset(),
            produces=frozenset({"layer_registry"}),
        ),
        PhaseSpec(
            name="data_quality_audit",
            output_model=AuditResult,
            run=_audit_run,
            requires=frozenset({"layer_registry"}),
            produces=frozenset({"audit_report"}),
            produces_schema_versions={"audit_report": _AUDIT_REPORT_SCHEMA_VERSION},
        ),
        PhaseSpec(
            name="grid_alignment",
            output_model=GridAlignmentResult,
            run=grid_alignment_run,
            requires=frozenset({"layer_registry"}),
            produces=frozenset({"aligned_rasters"})
            | {f"aligned/{key}" for key in _ALIGNED_RASTER_LAYER_KEYS},
        ),
        PhaseSpec(
            name="suitability_criteria",
            output_model=SuitabilityCriteriaResult,
            run=suitability_criteria_run,
            requires=frozenset({"aligned_rasters", "layer_registry"}),
            produces=frozenset({"suitability_criteria_result"}),
        ),
    ]


def _resolved_config_json(settings: SettingsFile, parameters) -> str:
    return json.dumps(
        {
            "settings": settings.model_dump(mode="json"),
            "parameters": parameters.model_dump(mode="json"),
        },
        sort_keys=True,
    )


def run_geofrea(
    country_code: str,
    target_phases: list[str],
    force_rerun: bool,
    resolutions: ResolutionsConfig,
    run_id: str,
    dirty: bool,
) -> bool:
    """Run the phases needed to satisfy target_phases for a single country.

    Args:
        country_code: ISO-3166-alpha-3 code, must be a key in parameters.json.
        target_phases: RunConfig.target_phases for this run.
        force_rerun: RunConfig.force_rerun for this run.
        resolutions: settings.yaml's `geospatial.resolutions`, threaded
            through to grid_alignment's PhaseSpec (see
            _build_phase_specs()).
        run_id: This run's identifier (see
            geofrea.core.orchestrator.compute_run_id).
        dirty: Whether the working tree has uncommitted changes (see
            geofrea.core.orchestrator.compute_dirty).

    Returns:
        True if every one of target_phases ended "success", False if any
        ended "failed" or "skipped_upstream_failed" (main()'s exit code
        is derived from this — see module-level Usage note).
    """
    # Set up file logging in addition to console logging
    log_file_path = log_path(country_code, run_id)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)
    logger.info("Starting run for %s with run_id %s", country_code, run_id)

    parameters = load_parameters(PARAMETERS_JSON)
    country_params = parameters.countries[country_code]

    orchestrator = Orchestrator(
        outputs_dir=outputs_dir(),
        country_code=country_code,
        country_params=country_params,
        target_phases=target_phases,
        force_rerun=force_rerun,
        run_id=run_id,
        dirty=dirty,
    )

    results = orchestrator.run(_build_phase_specs(resolutions, parameters.criteria))
    ok = all(results[name].status == "success" for name in target_phases)
    if not ok:
        logger.error(
            "Run incomplete for %s: %s",
            country_code,
            {name: results[name].status for name in target_phases if results[name].status != "success"},
        )
    else:
        logger.info("Run completed for %s.", country_code)
    return ok


def main() -> int:
    settings = load_settings(SETTINGS_YAML)
    parameters = load_parameters(PARAMETERS_JSON)

    countries = settings.run.countries or list(parameters.countries.keys())
    unknown = [c for c in countries if c not in parameters.countries]
    if unknown:
        logger.error(
            "settings.yaml's run.countries lists %s, not present in parameters.json.",
            unknown,
        )
        return 1

    methodology_version = _read_methodology_version(METHODOLOGY_MD)
    git_commit = compute_git_commit(REPO_ROOT)
    dirty = compute_dirty(REPO_ROOT)
    run_id = compute_run_id(
        _resolved_config_json(settings, parameters), methodology_version, git_commit
    )

    all_ok = True
    for country_code in countries:
        ok = run_geofrea(
            country_code,
            settings.run.target_phases,
            settings.run.force_rerun,
            settings.geospatial.resolutions,
            run_id,
            dirty,
        )
        all_ok = all_ok and ok

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
