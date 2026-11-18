"""The guard against an accidental real run of F6 onwards (`--real-run`) and the plan of a run (`--plan`); COMMAND 176, L-244.

The guard is a check of the invocation in `main.py`: the phases of F6 onwards are refused on a real country unless the invocation carries
`--real-run`; a synthetic country does not need it; the pre-registration guard of the orchestrator is a separate check that stays in place. The plan
reads the manifest and the fingerprints and writes nothing.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

import main
from geofrea.core.config_loader import load_parameters
from geofrea.core.orchestrator import Orchestrator, PhaseSpec

REPO_ROOT = Path(__file__).resolve().parents[2]
PARAMETERS_JSON = REPO_ROOT / "config" / "parameters.json"
F6_ONWARDS = [
    "lcoe_modeling",
    "sample_size_convergence",
    "robustness_analysis",
    "cross_country_h4",
    "external_validation",
    "lcoe_maps",
    "robustness_maps",
    "results_synthesis",
]


# -- the check of the invocation ----------------------------------------------------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("phase", F6_ONWARDS)
def test_a_phase_of_f6_onwards_on_a_real_country_is_refused_without_the_option(phase):
    message = main.real_run_refusal(["PRT"], [phase], [], set(), real_run=False)
    assert message is not None
    assert phase in message
    assert "--real-run" in message
    assert "PRT" in message


@pytest.mark.unit
def test_the_message_lists_every_refused_phase_and_every_real_country():
    message = main.real_run_refusal(
        ["PRT", "ZZZ", "BRA"], ["lcoe_modeling", "technical_potential", "results_synthesis"], [], {"ZZZ"}, real_run=False
    )
    assert "lcoe_modeling" in message and "results_synthesis" in message
    assert "technical_potential" not in message  # F5 is not refused
    assert "PRT" in message and "BRA" in message and "ZZZ" not in message


@pytest.mark.unit
def test_the_option_lets_the_invocation_start():
    assert main.real_run_refusal(["PRT", "BRA"], F6_ONWARDS, [], set(), real_run=True) is None


@pytest.mark.unit
def test_a_synthetic_country_does_not_need_the_option():
    assert main.real_run_refusal(["ZZZ"], F6_ONWARDS, [], {"ZZZ"}, real_run=False) is None


@pytest.mark.unit
def test_the_phases_before_f6_do_not_need_the_option():
    before = ["data_acquisition", "grid_alignment", "land_eligibility", "technical_potential", "potential_maps", "overview"]
    assert main.real_run_refusal(["PRT", "IND", "BRA"], before, before, set(), real_run=False) is None


@pytest.mark.unit
def test_a_rerun_of_a_phase_of_f6_onwards_is_refused_too():
    message = main.real_run_refusal(["BRA"], ["potential_maps"], ["lcoe_modeling"], set(), real_run=False)
    assert message is not None and "lcoe_modeling" in message


# -- main: the refusal comes before any phase, the option reaches the run ---------------------------------------------------------------------------


class _Recorder:
    def __init__(self):
        self.calls: list[tuple] = []

    def __call__(self, *args, **kwargs):
        self.calls.append(args)
        return True, object(), {}


@pytest.fixture
def stubbed_run(monkeypatch):
    recorder = _Recorder()
    monkeypatch.setattr(main, "run_geofrea", recorder)
    monkeypatch.setattr(main, "cold_start_shortfall", lambda *_a, **_k: None)
    return recorder


@pytest.mark.unit
def test_main_refuses_a_real_country_without_the_option_and_runs_nothing(stubbed_run, caplog):
    with caplog.at_level(logging.ERROR):
        code = main._main(["PRT", "--phases", "lcoe_modeling"])
    assert code == 1
    assert stubbed_run.calls == []
    assert any("--real-run" in r.getMessage() and "lcoe_modeling" in r.getMessage() for r in caplog.records)


@pytest.mark.unit
def test_main_runs_the_phase_with_the_option(stubbed_run):
    code = main._main(["PRT", "--phases", "lcoe_modeling", "--real-run"])
    assert code == 0
    assert len(stubbed_run.calls) == 1
    assert stubbed_run.calls[0][0] == "PRT"


@pytest.mark.unit
def test_main_does_not_ask_for_the_option_on_the_synthetic_country(stubbed_run):
    code = main._main(["ZZZ", "--phases", "lcoe_modeling"])
    assert code == 0
    assert len(stubbed_run.calls) == 1


@pytest.mark.unit
def test_the_default_phases_of_the_settings_do_not_need_the_option(stubbed_run):
    assert main._main(["PRT"]) == 0
    assert len(stubbed_run.calls) == 1


@pytest.mark.unit
def test_the_preregistration_guard_stays_wired_to_the_orchestrator_with_the_option(tmp_path, monkeypatch):
    """`--real-run` is not the guard: the orchestrator of a run still receives the pre-registration check and calls the verifier with the country."""
    seen: dict = {}

    class _FakeOrchestrator:
        def __init__(self, **kwargs):
            seen["guard"] = kwargs["preregistration_guard"]

        def record_seed(self, *_a):
            pass

        def run(self, _specs):
            class _Ok:
                status = "success"

            return {"lcoe_modeling": _Ok()}

    called: list[str] = []
    monkeypatch.setattr(main, "Orchestrator", _FakeOrchestrator)
    monkeypatch.setattr(main, "_country_phase_specs", lambda *_a, **_k: [])
    monkeypatch.setattr(main, "verify_preregistration", lambda iso, *_a: called.append(iso))
    monkeypatch.setattr(main, "_config_source", lambda: None)

    ok, _, _ = main.run_geofrea(
        "PRT",
        ["lcoe_modeling"],
        [],
        main.ResolutionsConfig(suitability=0.01),
        100.0,
        main.load_audit_config(REPO_ROOT / "config" / "audit.yaml"),
        "run-id",
        False,
    )
    assert ok is True
    assert seen["guard"] is not None
    seen["guard"]("lcoe_modeling")
    assert called == ["PRT"]


@pytest.mark.unit
def test_the_unattended_script_passes_the_option_when_the_round_asks_for_f6_onwards():
    script = (REPO_ROOT / "scripts" / "run_unattended.ps1").read_text(encoding="utf-8")
    assert "--real-run" in script
    for phase in F6_ONWARDS:
        assert f"'{phase}'" in script


# -- the plan ------------------------------------------------------------------------------------------------------------------------------------


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int


def _spec(name: str, calls: list[str], requires=frozenset(), produces=frozenset(), config_fp: str | None = None) -> PhaseSpec:
    def run(context):
        calls.append(name)
        for key in produces:
            path = context.outputs_dir / f"{key}.txt"
            path.write_text(key, encoding="utf-8")
            context.register_artifact(key, path, "1.0")
        return _Out(value=1)

    return PhaseSpec(name=name, output_model=_Out, run=run, requires=requires, produces=produces, config_fingerprint=config_fp)


def _orch(tmp_path: Path, targets: list[str], rerun: list[str] | None = None) -> Orchestrator:
    return Orchestrator(
        outputs_dir=tmp_path,
        country_code="PRT",
        country_params=load_parameters(PARAMETERS_JSON).countries["PRT"],
        target_phases=targets,
        rerun_phases=rerun or [],
        run_id="run-1",
        methodology_version="test-1.0.0",
        dirty=False,
    )


def _two_phases(calls: list[str], config_b: str | None = "b1") -> list[PhaseSpec]:
    return [
        _spec("a", calls, produces=frozenset({"ka"}), config_fp="a1"),
        _spec("b", calls, requires=frozenset({"ka"}), produces=frozenset({"kb"}), config_fp=config_b),
    ]


@pytest.mark.unit
def test_the_plan_of_a_country_without_manifest_executes_everything_and_writes_nothing(tmp_path):
    calls: list[str] = []
    entries = _orch(tmp_path, ["b"]).plan(_two_phases(calls))
    assert [(e.phase, e.action) for e in entries] == [("a", "execute"), ("b", "execute")]
    assert all("no manifest entry yet" in e.reason for e in entries)
    assert calls == []
    assert list(tmp_path.rglob("*")) == []  # no manifest, no artifact


@pytest.mark.unit
def test_the_plan_resumes_a_phase_that_ran_and_executes_one_whose_configuration_changed(tmp_path):
    calls: list[str] = []
    _orch(tmp_path, ["b"]).run(_two_phases(calls))
    assert calls == ["a", "b"]
    manifest = tmp_path / "PRT" / "manifest.json"
    before = manifest.read_bytes()
    files_before = sorted(p.name for p in tmp_path.rglob("*"))

    same = _orch(tmp_path, ["b"]).plan(_two_phases(calls))
    assert [(e.phase, e.action) for e in same] == [("a", "resume"), ("b", "resume")]

    changed = _orch(tmp_path, ["b"]).plan(_two_phases(calls, config_b="b2"))
    by_phase = {e.phase: e for e in changed}
    assert by_phase["a"].action == "resume"
    assert by_phase["b"].action == "execute"
    assert "configuration it reads changed" in by_phase["b"].reason

    assert calls == ["a", "b"]  # the plan ran nothing
    assert manifest.read_bytes() == before  # and wrote nothing
    assert sorted(p.name for p in tmp_path.rglob("*")) == files_before


@pytest.mark.unit
def test_the_plan_lists_the_downstream_phases_that_may_become_stale_when_a_phase_is_forced(tmp_path):
    calls: list[str] = []
    _orch(tmp_path, ["b"]).run(_two_phases(calls))
    entries = _orch(tmp_path, ["b"], rerun=["a"]).plan(_two_phases(calls))
    actions = {e.phase: e.action for e in entries}
    assert actions == {"a": "execute", "b": "may_become_stale"}
    assert "named in rerun_phases" in next(e.reason for e in entries if e.phase == "a")


@pytest.mark.unit
def test_main_plan_prints_the_phases_notes_the_refusal_and_writes_no_manifest_and_no_log(tmp_path, capsys, monkeypatch):
    ran = _Recorder()
    monkeypatch.setattr(main, "run_geofrea", ran)
    code = main._main(["PRT", "--phases", "lcoe_modeling", "--plan"])
    out = capsys.readouterr().out
    assert code == 0
    assert ran.calls == []
    assert out.startswith("PLAN PRT")
    assert "lcoe_modeling" in out and "no manifest entry yet" in out
    assert "NOTE: run refused" in out and "--real-run" in out  # the invocation would be refused without the option
    assert list(tmp_path.rglob("manifest*.json")) == []
    assert list(tmp_path.rglob("*.log")) == []
    assert list(tmp_path.rglob("*.txt")) == []
