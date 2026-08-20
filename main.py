"""main.py — GeoFREA entry point.

Loads config/parameters.json + config/settings.yaml, resolves which
countries to run (RunConfig.countries empty = every country present in
parameters.json), and runs the orchestrator's registered phases for
each. Only data_quality_audit is registered — the orchestrator itself
(src/geofrea/core/orchestrator.py) is generic and does not need
redesigning when phase 2 (grid_alignment) is added; it will be appended
to _PHASE_SPECS below.

No data acquisition layer exists yet in GeoFREA (legacy's
DataFetcher/DataManager/DataOrchestrator are not ported — out of scope
for this stage; see src/geofrea/data_quality_audit/schemas.py's
AuditInputs docstring). This main.py therefore runs the audit phase
with empty inputs: every raster will report "File not found", which is
the same defensive path the phase already takes for genuinely missing
files, not new/fabricated behavior. Real auditing becomes possible once
a data acquisition module is built and wired in here.

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
from geofrea.data_quality_audit.audit import run_audit_phase
from geofrea.data_quality_audit.schemas import AuditInputs, AuditResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("geofrea.main")

REPO_ROOT = Path(__file__).resolve().parent
PARAMETERS_JSON = REPO_ROOT / "config" / "parameters.json"
SETTINGS_YAML = REPO_ROOT / "config" / "settings.yaml"
OUTPUTS_DIR = REPO_ROOT / "outputs"


def _build_phase_specs() -> list[PhaseSpec]:
    """Registered phases, in execution order.

    Only data_quality_audit exists so far (see module docstring). Adding
    grid_alignment next means appending one more PhaseSpec here — the
    Orchestrator itself does not change.
    """
    audit_run = functools.partial(run_audit_phase, inputs=AuditInputs())
    return [
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
