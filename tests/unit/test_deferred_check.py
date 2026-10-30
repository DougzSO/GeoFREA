"""Deferred content check against a reference manifest (COMMAND 80; D-core-050)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel, ConfigDict

from geofrea.core.config_loader import load_parameters
from geofrea.core.deferred_check import DeferredCheck, compare_artifacts, for_country, load_checks
from geofrea.core.orchestrator import Orchestrator, PhaseSpec

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
PHASES = ("a", "b", "c")
SAME = {"a": "cfg-1", "b": "cfg-1", "c": "cfg-1"}


class Out(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int


def _spec(name: str, values: dict[str, int], requires=frozenset(), produces=frozenset(), config_fingerprint=None) -> PhaseSpec:
    def run(context):
        for key in produces:
            path = context.outputs_dir / f"{key}.txt"
            path.write_text(f"{key}-{values[name]}", encoding="utf-8")
            context.register_artifact(key, path, "1.0")
        return Out(value=values[name])

    return PhaseSpec(name=name, output_model=Out, run=run, requires=requires, produces=produces, config_fingerprint=config_fingerprint)


def _specs(values: dict[str, int], config: dict[str, str]) -> list[PhaseSpec]:
    return [
        _spec("a", values, produces=frozenset({"a_out"}), config_fingerprint=config["a"]),
        _spec("b", values, requires=frozenset({"a_out"}), produces=frozenset({"b_out"}), config_fingerprint=config["b"]),
        _spec("c", values, requires=frozenset({"b_out"}), produces=frozenset({"c_out"}), config_fingerprint=config["c"]),
    ]


def _orchestrator(outputs: Path, check: DeferredCheck | None, rerun=()) -> Orchestrator:
    return Orchestrator(
        outputs_dir=outputs,
        country_code="ZZZ",
        country_params=load_parameters(REPO_ROOT / "config" / "parameters.json").countries["PRT"],
        target_phases=["c"],
        rerun_phases=list(rerun),
        run_id="run",
        methodology_version="test",
        dirty=False,
        deferred_check=check,
    )


@pytest.fixture
def baseline(tmp_path):
    """A first run (the reference): a, b and c with value 1; returns the data root, the outputs dir and the reference manifest."""
    data = tmp_path / "data"
    outputs = data / "outputs"
    (outputs / "ZZZ").mkdir(parents=True)
    _orchestrator(outputs, None).run(_specs({"a": 1, "b": 1, "c": 1}, SAME))
    reference = data / "reference_manifest.json"
    shutil.copy(outputs / "ZZZ" / "manifest.json", reference)
    return data, outputs, reference


def _check(data: Path, outputs: Path, expected=None) -> DeferredCheck:
    config = data / "deferred_checks.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "countries": {"ZZZ": {"baseline": "reference_manifest.json", "phases": list(PHASES), "expected": expected or {}}},
                "suspects": {"b": "the code of phase b"},
            }
        ),
        encoding="utf-8",
    )
    check = for_country("zzz", config, data, outputs)
    assert check is not None
    return check


def _report(outputs: Path) -> dict:
    return json.loads((outputs / "ZZZ" / "deferred_check.json").read_text(encoding="utf-8"))


def test_a_rerun_with_the_same_content_is_identical_and_settles_every_phase(baseline):
    data, outputs, _ = baseline
    results = _orchestrator(outputs, _check(data, outputs), rerun=PHASES).run(_specs({"a": 1, "b": 1, "c": 1}, SAME))
    assert [results[p].status for p in PHASES] == ["success"] * 3
    report = _report(outputs)
    assert report["verdict"] == "IDENTICO" and report["pending"] == []
    assert {p: v["verdict"] for p, v in report["phases"].items()} == {"a": "IDENTICO", "b": "IDENTICO", "c": "IDENTICO"}


def test_an_artifact_that_differs_without_a_change_of_configuration_stops_the_run_before_the_next_phase(baseline):
    data, outputs, _ = baseline
    results = _orchestrator(outputs, _check(data, outputs), rerun=PHASES).run(_specs({"a": 1, "b": 2, "c": 1}, SAME))

    assert results["a"].status == "success" and results["b"].status == "success"
    assert results["c"].status == "skipped_upstream_failed" and "deferred check" in results["c"].error
    report = _report(outputs)
    assert report["verdict"] == "DIFERENTE"
    entry = report["phases"]["b"]
    assert entry["verdict"] == "DIFERENTE" and list(entry["different_unexplained"]) == ["b_out"]
    assert entry["probable_cause"] == "the code of phase b"
    assert "c" not in report["phases"]


def test_the_phase_after_the_stop_is_not_overwritten_as_failed(baseline):
    data, outputs, _ = baseline
    manifest = outputs / "ZZZ" / "manifest.json"
    before = json.loads(manifest.read_text(encoding="utf-8"))["phases"]["c"]
    _orchestrator(outputs, _check(data, outputs), rerun=["a", "b"]).run(_specs({"a": 1, "b": 2, "c": 1}, SAME))
    after = json.loads(manifest.read_text(encoding="utf-8"))["phases"]["c"]
    # the changed content of b marks c stale, as in any run; the stop adds no "skipped_upstream_failed" entry and leaves c's run as it was
    assert before["status"] == "success" and after["status"] == "stale_upstream" and after["finished_at"] == before["finished_at"]


def test_a_difference_that_a_change_of_configuration_explains_does_not_stop_the_run(baseline):
    data, outputs, _ = baseline
    results = _orchestrator(outputs, _check(data, outputs), rerun=PHASES).run(_specs({"a": 1, "b": 2, "c": 1}, {**SAME, "b": "cfg-2"}))
    assert results["c"].status == "success"
    report = _report(outputs)
    assert report["phases"]["b"]["verdict"] == "EXPLICADO" and report["phases"]["b"]["different_with_config_change"] == ["b_out"]
    assert report["verdict"] == "IDENTICO"


def test_an_expected_artifact_is_accepted_and_flagged_for_review(baseline):
    data, outputs, _ = baseline
    check = _check(data, outputs, expected={"b_out": "a report"})
    results = _orchestrator(outputs, check, rerun=PHASES).run(_specs({"a": 1, "b": 2, "c": 1}, SAME))
    assert results["c"].status == "success"
    report = _report(outputs)
    assert report["phases"]["b"]["verdict"] == "EXPLICADO_REVISAR" and report["verdict"] == "REVISAR"


def test_a_phase_that_only_resumes_is_not_compared(baseline):
    data, outputs, _ = baseline
    _orchestrator(outputs, _check(data, outputs)).run(_specs({"a": 1, "b": 9, "c": 9}, SAME))
    assert not (outputs / "ZZZ" / "deferred_check.json").exists()


def test_a_settled_phase_is_not_compared_again_and_a_failed_one_is(baseline):
    data, outputs, _ = baseline
    _orchestrator(outputs, _check(data, outputs), rerun=PHASES).run(_specs({"a": 1, "b": 2, "c": 1}, SAME))  # b differs: DIFERENTE
    assert _report(outputs)["phases"]["b"]["verdict"] == "DIFERENTE"
    _orchestrator(outputs, _check(data, outputs), rerun=PHASES).run(_specs({"a": 1, "b": 1, "c": 1}, SAME))  # fixed: compared again, identical now
    assert _report(outputs)["verdict"] == "IDENTICO"
    _orchestrator(outputs, _check(data, outputs), rerun=PHASES).run(_specs({"a": 1, "b": 7, "c": 1}, SAME))  # settled: a later change is not an error
    assert _report(outputs)["verdict"] == "IDENTICO"


def test_the_verdict_is_pending_until_every_listed_phase_has_run(baseline):
    data, outputs, _ = baseline
    orchestrator = _orchestrator(outputs, _check(data, outputs), rerun=["a"])
    orchestrator.target_phases = ["a"]
    orchestrator.run(_specs({"a": 1, "b": 1, "c": 1}, SAME))
    report = _report(outputs)
    assert report["verdict"] == "PENDENTE" and report["pending"] == ["b", "c"]


def test_a_missing_reference_compares_nothing_and_does_not_stop(baseline):
    data, outputs, reference = baseline
    check = _check(data, outputs)
    reference.unlink()
    results = _orchestrator(outputs, check, rerun=PHASES).run(_specs({"a": 1, "b": 2, "c": 1}, SAME))
    assert results["c"].status == "success"
    assert _report(outputs)["phases"]["b"]["verdict"] == "SEM_REFERENCIA"


def test_a_country_that_is_not_listed_has_no_check(tmp_path):
    config = tmp_path / "c.yaml"
    config.write_text(yaml.safe_dump({"countries": {"IND": {"baseline": "x.json", "phases": ["a"]}}}), encoding="utf-8")
    assert for_country("BRA", config, tmp_path, tmp_path) is None
    assert for_country("ind", config, tmp_path, tmp_path) is not None
    assert for_country("BRA", tmp_path / "absent.yaml", tmp_path, tmp_path) is None


def test_compare_artifacts_reports_absent_artifacts_and_config_change():
    before = {"artifacts": {"x": {"phase": "p", "sha256": "1"}, "y": {"phase": "p", "content_sha256": "c"}}, "phases": {"p": {"config_fingerprint": "f"}}}
    after = {"artifacts": {"x": {"phase": "p", "sha256": "2"}, "z": {"phase": "p", "sha256": "3"}}, "phases": {"p": {"config_fingerprint": "g"}}}
    rows = compare_artifacts(before, after)
    assert {k: r["status"] for k, r in rows.items()} == {"x": "DIFERENTE", "y": "AUSENTE_DEPOIS", "z": "AUSENTE_ANTES"}
    assert all(r["config_changed"] for r in rows.values())


def test_the_shipped_configuration_lists_ind_and_bra_with_the_twelve_phases():
    checks = load_checks(REPO_ROOT / "config" / "deferred_checks.yaml", Path("D:/data"))
    assert set(checks) == {"IND", "BRA"}
    assert len(checks["IND"].phases) == 12 and checks["IND"].phases == checks["BRA"].phases
    assert checks["IND"].baseline.as_posix().endswith("outputs/IND/unattended/20261029_135838/manifest_before.json")
    assert list(checks["BRA"].expected) == ["audit_report"] and not checks["IND"].expected
    assert all(phase in checks["IND"].suspects for phase in checks["IND"].phases)
