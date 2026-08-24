"""main.py — GeoFREA entry point.

Loads config/parameters.json + config/settings.yaml, resolves which
countries to run (RunConfig.countries empty = every country present in
parameters.json), and runs the orchestrator's registered phases for
each. The orchestrator itself (src/geofrea/core/orchestrator.py) is
generic and does not need redesigning as phases are added.

data_acquisition (registered first, below) is a STRUCTURE-ONLY skeleton
— see src/geofrea/data_acquisition/phase.py's module docstring. It has
no fetch/download logic yet and always returns placeholder
(path=None) layers, so it isn't wired to feed data_quality_audit's
AuditInputs here: the audit PhaseSpec below still runs with AuditInputs()
empty, exactly as before. Wiring them together needs
_build_phase_specs() to change from eager functools.partial(inputs=...)
to a per-context closure that reads
context.prior_results["data_acquisition"].output at call time (partial
binds inputs before any phase has run, so it can't reference
prior_results yet) — a real change to the audit registration itself,
not just an addition, so it's flagged here rather than done as a side
effect of adding data_acquisition. See
src/geofrea/data_acquisition/adapter.py, which is ready to be called
from that future closure once it exists.

Also: settings.yaml's run.phases has no "data_acquisition" key yet
(out of scope for this skeleton stage) — until it's added, this phase
is skipped by Orchestrator.run() like any other unlisted phase name.

Usage:
    python main.py
"""

from __future__ import annotations

import functools
import logging
import sys
from pathlib import Path

from geofrea.core.config_loader import load_parameters, load_settings
from geofrea.core.orchestrator import Orchestrator, PhaseExecutionError, PhaseSpec
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


class UnwiredPhasesError(RuntimeError):
    """Raised when enabling both phases together would silently misbehave.

    data_acquisition and data_quality_audit are not wired together yet
    (see module docstring) — data_quality_audit still runs with a
    hardcoded empty AuditInputs() regardless of what data_acquisition
    produced. Enabling both in settings.yaml's run.phases today would
    silently run an audit against nothing, looking superficially like a
    real end-to-end run. This is raised at phase_specs construction
    time — before Orchestrator.run() executes anything — rather than
    left as a log warning easy to miss.
    """


def _build_phase_specs(phases_enabled: dict[str, bool]) -> list[PhaseSpec]:
    """Registered phases, in execution order.

    data_acquisition MUST come before data_quality_audit: the
    Orchestrator enforces no ordering or dependency between phases on
    its own (RunConfig.phases is a flat enabled/disabled toggle map,
    with no ordering semantics) — this list's order is the only thing
    that determines execution order. See module docstring for why
    data_quality_audit's inputs are not yet wired to data_acquisition's
    output despite both being registered here.

    Args:
        phases_enabled: RunConfig.phases for this run — checked here
            (not just later, per-phase) so an unwired combination is
            rejected before any phase executes.

    Raises:
        UnwiredPhasesError: If both data_acquisition and
            data_quality_audit are enabled together (see that class's
            docstring).
    """
    if phases_enabled.get("data_acquisition", False) and phases_enabled.get(
        "data_quality_audit", False
    ):
        raise UnwiredPhasesError(
            "settings.yaml's run.phases enables both 'data_acquisition' and "
            "'data_quality_audit', but they are not wired together yet — "
            "data_quality_audit would still run with AuditInputs() empty, "
            "not data_acquisition's output (see main.py's module "
            "docstring and geofrea.data_acquisition.adapter). Disable one "
            "of the two in settings.yaml until the wiring is implemented."
        )

    audit_run = functools.partial(run_audit_phase, inputs=AuditInputs())
    return [
        PhaseSpec(
            name="data_acquisition", output_model=AcquisitionResult, run=run_acquisition_phase
        ),
        PhaseSpec(name="data_quality_audit", output_model=AuditResult, run=audit_run),
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
        orchestrator.run(_build_phase_specs(phases_enabled))
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
