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

    No longer takes phases_enabled (see module docstring —
    UnwiredPhasesError, the only reason this function inspected it, was
    removed 2026-08-25): which phases actually execute is decided by
    Orchestrator.run() itself, per phase, via Orchestrator.phases_enabled.

    Returns:
        The two registered PhaseSpecs, in execution order.
    """
    return [
        PhaseSpec(
            name="data_acquisition", output_model=AcquisitionResult, run=run_acquisition_phase
        ),
        PhaseSpec(name="data_quality_audit", output_model=AuditResult, run=_audit_run),
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
