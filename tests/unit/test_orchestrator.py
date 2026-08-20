"""Unit tests for geofrea.core.orchestrator.

Uses a trivial dummy phase (not the real audit phase) so orchestrator
behavior — success/failure handling, manifest persistence, resume — is
tested independently of any phase-specific logic. See
tests/unit/test_audit.py for the data_quality_audit phase itself.
"""

from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from geofrea.core.config_loader import load_parameters
from geofrea.core.orchestrator import (
    Orchestrator,
    PhaseExecutionError,
    PhaseSpec,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PARAMETERS_JSON = REPO_ROOT / "config" / "parameters.json"


class DummyOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int


def _country_params():
    """A real, valid CountryParams instance (loaded, not hand-built)."""
    return load_parameters(PARAMETERS_JSON).countries["PRT"]


def _make_spec(name: str, call_log: list[str], *, fail: bool = False, value: int = 1) -> PhaseSpec:
    def run(context):
        call_log.append(name)
        if fail:
            raise ValueError(f"{name} boom")
        return DummyOutput(value=value)

    return PhaseSpec(name=name, output_model=DummyOutput, run=run)


def _orchestrator(tmp_path: Path, phases_enabled: dict[str, bool]) -> Orchestrator:
    return Orchestrator(
        outputs_dir=tmp_path,
        country_code="PRT",
        country_params=_country_params(),
        phases_enabled=phases_enabled,
    )


@pytest.mark.unit
def test_phase_success_records_result(tmp_path):
    call_log: list[str] = []
    spec = _make_spec("phase_a", call_log, value=42)
    orchestrator = _orchestrator(tmp_path, {"phase_a": True})

    results = orchestrator.run([spec])

    assert call_log == ["phase_a"]
    assert results["phase_a"].status == "success"
    assert results["phase_a"].output.value == 42
    assert results["phase_a"].error is None


@pytest.mark.unit
def test_disabled_phase_is_not_run_and_absent_from_results(tmp_path):
    call_log: list[str] = []
    spec = _make_spec("phase_a", call_log)
    orchestrator = _orchestrator(tmp_path, {"phase_a": False})

    results = orchestrator.run([spec])

    assert call_log == []
    assert "phase_a" not in results


@pytest.mark.unit
def test_phase_not_listed_in_phases_enabled_defaults_to_not_run(tmp_path):
    call_log: list[str] = []
    spec = _make_spec("phase_a", call_log)
    orchestrator = _orchestrator(tmp_path, {})

    results = orchestrator.run([spec])

    assert call_log == []
    assert "phase_a" not in results


@pytest.mark.unit
def test_phase_failure_produces_failed_result_and_raises(tmp_path):
    call_log: list[str] = []
    spec = _make_spec("phase_a", call_log, fail=True)
    orchestrator = _orchestrator(tmp_path, {"phase_a": True})

    with pytest.raises(PhaseExecutionError) as exc_info:
        orchestrator.run([spec])

    assert exc_info.value.phase_name == "phase_a"
    assert "phase_a boom" in str(exc_info.value.original)


@pytest.mark.unit
def test_phase_failure_is_persisted_to_manifest_before_raising(tmp_path):
    call_log: list[str] = []
    spec = _make_spec("phase_a", call_log, fail=True)
    orchestrator = _orchestrator(tmp_path, {"phase_a": True})

    with pytest.raises(PhaseExecutionError):
        orchestrator.run([spec])

    assert orchestrator.manifest_path.exists()
    entry = orchestrator.manifest.phases["phase_a"]
    assert entry.status == "failed"
    assert "phase_a boom" in entry.error
    assert entry.output is None


@pytest.mark.unit
def test_phase_failure_stops_dependent_phases(tmp_path):
    call_log: list[str] = []
    failing = _make_spec("phase_a", call_log, fail=True)
    dependent = _make_spec("phase_b", call_log)
    orchestrator = _orchestrator(tmp_path, {"phase_a": True, "phase_b": True})

    with pytest.raises(PhaseExecutionError):
        orchestrator.run([failing, dependent])

    assert call_log == ["phase_a"]


@pytest.mark.unit
def test_manifest_written_on_success(tmp_path):
    call_log: list[str] = []
    spec = _make_spec("phase_a", call_log, value=7)
    orchestrator = _orchestrator(tmp_path, {"phase_a": True})

    orchestrator.run([spec])

    assert orchestrator.manifest_path == tmp_path / "PRT" / "manifest.json"
    assert orchestrator.manifest_path.exists()
    entry = orchestrator.manifest.phases["phase_a"]
    assert entry.status == "success"
    assert entry.output == {"value": 7}


@pytest.mark.unit
def test_resume_from_manifest_skips_completed_phase(tmp_path):
    call_log: list[str] = []
    spec = _make_spec("phase_a", call_log, value=9)

    first_run = _orchestrator(tmp_path, {"phase_a": True})
    first_results = first_run.run([spec])
    assert call_log == ["phase_a"]
    assert first_results["phase_a"].status == "success"

    second_run = _orchestrator(tmp_path, {"phase_a": True})
    second_results = second_run.run([spec])

    # Not re-invoked: call_log is unchanged.
    assert call_log == ["phase_a"]
    assert second_results["phase_a"].status == "success"
    assert second_results["phase_a"].output.value == 9


@pytest.mark.unit
def test_resume_does_not_apply_to_a_previously_failed_phase(tmp_path):
    call_log: list[str] = []
    failing_spec = _make_spec("phase_a", call_log, fail=True)

    first_run = _orchestrator(tmp_path, {"phase_a": True})
    with pytest.raises(PhaseExecutionError):
        first_run.run([failing_spec])
    assert call_log == ["phase_a"]

    # A failed phase is retried on the next run, not silently resumed as
    # if it had succeeded.
    succeeding_spec = _make_spec("phase_a", call_log, value=1)
    second_run = _orchestrator(tmp_path, {"phase_a": True})
    second_results = second_run.run([succeeding_spec])

    assert call_log == ["phase_a", "phase_a"]
    assert second_results["phase_a"].status == "success"
