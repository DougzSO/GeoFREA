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

import logging
import sys
from pathlib import Path

from geofrea.core.config_loader import load_parameters, load_settings
from geofrea.core.orchestrator import (
    Orchestrator,
    PhaseContext,
    PhaseExecutionError,
    PhaseSpec,
)
from geofrea.data_acquisition.adapter import acquisition_result_to_audit_inputs
from geofrea.data_acquisition.phase import run_acquisition_phase
from geofrea.data_acquisition.schemas import AcquisitionResult
from geofrea.data_quality_audit.audit import run_audit_phase
from geofrea.data_quality_audit.schemas import AuditInputs, AuditResult
from geofrea.grid_alignment.adapter import acquisition_result_to_grid_alignment_inputs
from geofrea.grid_alignment.alignment import run_grid_alignment_phase
from geofrea.grid_alignment.schemas import GridAlignmentInputs, GridAlignmentResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("geofrea.main")

REPO_ROOT = Path(__file__).resolve().parent
PARAMETERS_JSON = REPO_ROOT / "config" / "parameters.json"
SETTINGS_YAML = REPO_ROOT / "config" / "settings.yaml"
OUTPUTS_DIR = REPO_ROOT / "outputs"


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


def _audit_run(context: PhaseContext) -> AuditResult:
    return run_audit_phase(context, inputs=_build_audit_inputs(context))


def _build_grid_alignment_inputs(context: PhaseContext) -> GridAlignmentInputs:
    """Build GridAlignmentInputs from data_acquisition's output.

    Unlike _build_audit_inputs(), there is NO empty-inputs fallback:
    grid_alignment has no degraded mode (see GridAlignmentInputs'
    docstring in schemas.py, and GridAlignmentRequiresBordersError) —
    it cannot produce anything meaningful without a real
    AcquisitionResult to adapt. If data_acquisition did not run this
    pipeline (disabled in settings.yaml, or a hypothetical standalone
    grid_alignment-only run), this raises immediately rather than
    silently building a request GridAlignmentInputs could never
    satisfy — same "fail loud at construction time" philosophy as
    GridAlignmentRequiresBordersError itself (see adapter.py).

    Args:
        context: The grid_alignment phase's PhaseContext, as passed by
            Orchestrator.run().

    Returns:
        Real GridAlignmentInputs adapted from data_acquisition's output.

    Raises:
        RuntimeError: If data_acquisition did not run (or failed) in
            this pipeline — grid_alignment has nothing to adapt from.
        GridAlignmentRequiresBordersError: If data_acquisition ran but
            its AcquisitionResult has no usable `borders` layer (see
            grid_alignment/adapter.py).
    """
    acquisition_result = context.prior_results.get("data_acquisition")
    if acquisition_result is None or acquisition_result.output is None:
        raise RuntimeError(
            "grid_alignment requires data_acquisition to have run in this "
            "same pipeline (see settings.yaml's run.phases) — it has no "
            "degraded/empty-inputs mode, unlike data_quality_audit."
        )
    return acquisition_result_to_grid_alignment_inputs(acquisition_result.output)


def _grid_alignment_run(context: PhaseContext) -> GridAlignmentResult:
    return run_grid_alignment_phase(context, inputs=_build_grid_alignment_inputs(context))


def _build_phase_specs() -> list[PhaseSpec]:
    """Registered phases, in execution order.

    data_acquisition MUST come before data_quality_audit: the
    Orchestrator enforces no ordering or dependency between phases on
    its own (RunConfig.phases is a flat enabled/disabled toggle map,
    with no ordering semantics) — this list's order is the only thing
    that determines execution order, and it's also what makes
    data_acquisition's PhaseResult available in context.prior_results
    by the time _audit_run() executes (see module docstring for the
    wiring itself).

    grid_alignment is registered THIRD (2026-09-08, see DECISIONS.md
    same date), matching the readable pipeline order
    (acquisition -> audit -> alignment, same as legacy's Fase 1/2a
    numbering) — but its closure (_grid_alignment_run) only reads
    context.prior_results["data_acquisition"], never
    ["data_quality_audit"]. List position here governs execution order
    only; it does not imply grid_alignment depends on
    data_quality_audit having run (see module docstring's "grid_
    alignment wiring" section for why that independence matters).

    No longer takes phases_enabled (see module docstring —
    UnwiredPhasesError, the only reason this function inspected it, was
    removed 2026-08-25): which phases actually execute is decided by
    Orchestrator.run() itself, per phase, via Orchestrator.phases_enabled.

    Returns:
        The three registered PhaseSpecs, in execution order.
    """
    return [
        PhaseSpec(
            name="data_acquisition", output_model=AcquisitionResult, run=run_acquisition_phase
        ),
        PhaseSpec(name="data_quality_audit", output_model=AuditResult, run=_audit_run),
        PhaseSpec(
            name="grid_alignment", output_model=GridAlignmentResult, run=_grid_alignment_run
        ),
    ]


def run_geofrea(country_code: str, phases_enabled: dict[str, bool]) -> bool:
    """Run every enabled, registered phase for a single country.

    Args:
        country_code: ISO-3166-alpha-3 code, must be a key in parameters.json.
        phases_enabled: RunConfig.phases for this run.

    Returns:
        True if every attempted phase succeeded (or none were enabled),
        False if a phase failed.
    """
    parameters = load_parameters(PARAMETERS_JSON)
    country_params = parameters.countries[country_code]

    orchestrator = Orchestrator(
        outputs_dir=OUTPUTS_DIR,
        country_code=country_code,
        country_params=country_params,
        phases_enabled=phases_enabled,
    )

    try:
        orchestrator.run(_build_phase_specs())
    except PhaseExecutionError as exc:
        logger.error("Run aborted for %s: %s", country_code, exc)
        return False

    logger.info("Run completed for %s.", country_code)
    return True


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

    if not any(settings.run.phases.values()):
        logger.warning(
            "No phase is enabled in settings.yaml's run.phases — nothing to do."
        )

    all_ok = True
    for country_code in countries:
        ok = run_geofrea(country_code, settings.run.phases)
        all_ok = all_ok and ok

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
