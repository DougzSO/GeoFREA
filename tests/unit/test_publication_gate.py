"""The reference moves only by an explicit publication that gates EVERY phase of the round (COMMAND 137; OQ-080)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel, ConfigDict

from geofrea.core.config_loader import load_parameters
from geofrea.core.deferred_check import PublicationRefused, gate_for_publication, publish_with_gate
from geofrea.core.orchestrator import Orchestrator, PhaseSpec
from geofrea.core.reference_store import ReferenceStore

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
NO_YAML = Path("absent_deferred_checks.yaml")


class Out(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int


def _specs(values: dict[str, int]) -> list[PhaseSpec]:
    def make(name, requires=frozenset(), produces=frozenset()):
        def run(context):
            summary = context.outputs_dir / f"{name}_summary.json"
            summary.write_text(json.dumps({"phase": name, "v": values[name]}), encoding="utf-8")
            context.register_artifact(f"{name}_summary", summary, "1.0")
            return Out(value=values[name])

        return PhaseSpec(name=name, output_model=Out, run=run, requires=requires, produces=produces)

    specs = [make("a", produces=frozenset({"a_summary"})), make("b", requires=frozenset({"a_summary"}), produces=frozenset({"b_summary"}))]
    if "c" in values:
        specs.append(make("c", requires=frozenset({"b_summary"}), produces=frozenset({"c_summary"})))
    return specs


def _round(root: Path, run_id: str, values: dict[str, int]) -> Orchestrator:
    """A round of country ZZZ run in its own data root (`root`), so that two rounds can differ and share one reference store."""
    outputs = root / "data" / "outputs"
    (outputs / "ZZZ").mkdir(parents=True)
    orchestrator = Orchestrator(
        outputs_dir=outputs,
        country_code="ZZZ",
        country_params=load_parameters(REPO_ROOT / "config" / "parameters.json").countries["PRT"],
        target_phases=["c" if "c" in values else "b"],
        rerun_phases=[],
        run_id=run_id,
        methodology_version="test",
        dirty=False,
    )
    results = orchestrator.run(_specs(values))
    assert all(r.status == "success" for r in results.values())
    return orchestrator


def _publish(store, orchestrator, tmp_path, yaml_path=NO_YAML, **kwargs):
    return publish_with_gate(orchestrator.manifest, orchestrator.manifest_path, store, yaml_path, tmp_path, note="test", **kwargs)


def _store_with_reference(tmp_path) -> ReferenceStore:
    store = ReferenceStore(tmp_path / "references")
    first = _round(tmp_path / "r1", "run-1", {"a": 1, "b": 1})
    _publish(store, first, tmp_path, first=True)
    assert store.latest("ZZZ") == "run-1"
    return store


def test_the_orchestrator_does_not_publish_a_reference_by_itself(tmp_path):
    store = ReferenceStore(tmp_path / "references")
    with pytest.raises(TypeError):
        Orchestrator(  # type: ignore[call-arg]
            outputs_dir=tmp_path,
            country_code="ZZZ",
            country_params=None,
            target_phases=["a"],
            rerun_phases=[],
            run_id="x",
            methodology_version="t",
            dirty=False,
            reference_store=store,
        )
    _round(tmp_path / "r1", "run-1", {"a": 1, "b": 1})
    assert store.latest("ZZZ") is None and not (tmp_path / "references").exists()


def test_a_publication_with_a_phase_that_is_different_is_refused_and_writes_nothing(tmp_path):
    store = _store_with_reference(tmp_path)
    second = _round(tmp_path / "r2", "run-2", {"a": 1, "b": 2})  # phase b changed with no change of configuration
    with pytest.raises(PublicationRefused, match=r"b: DIFERENTE") as refused:
        _publish(store, second, tmp_path)
    assert refused.value.summary["verdicts"] == {"a": "IDENTICO", "b": "DIFERENTE"}
    assert store.latest("ZZZ") == "run-1" and not store.round_dir("ZZZ", "run-2").exists()


def test_a_publication_with_every_phase_identical_is_accepted_and_keeps_the_verdicts_in_the_index(tmp_path):
    store = _store_with_reference(tmp_path)
    second = _round(tmp_path / "r2", "run-2", {"a": 1, "b": 1})
    run_dir, gate = _publish(store, second, tmp_path)
    assert run_dir is not None and store.latest("ZZZ") == "run-2"
    assert gate.verdicts() == {"a": "IDENTICO", "b": "IDENTICO"}
    kept = store.index("ZZZ", "run-2")["evidence"]["gate"]
    assert kept["verdicts"] == {"a": "IDENTICO", "b": "IDENTICO"} and kept["reference_run"] == "run-1" and kept["counts"] == {"IDENTICO": 2}
    assert kept["phases"]["b"]["n_artifacts"] == 1 and kept["first_reference"] is False


def test_the_gate_does_not_skip_a_phase_whose_verdict_was_settled_in_an_earlier_report(tmp_path):
    """The gate of the pipeline skips a phase with a settled verdict; this one compares every phase again, whatever `deferred_check.json` says."""
    store = _store_with_reference(tmp_path)
    second = _round(tmp_path / "r2", "run-2", {"a": 1, "b": 2})
    config = tmp_path / "deferred_checks.yaml"
    config.write_text(yaml.safe_dump({"countries": {"ZZZ": {"baseline": "latest", "reference_run": "latest", "phases": ["a"]}}}), encoding="utf-8")
    report = second.outputs_dir / "ZZZ" / "deferred_check.json"
    report.write_text(
        json.dumps({"country": "ZZZ", "baseline": "references/latest", "phases": {p: {"verdict": "IDENTICO"} for p in ("a", "b")}, "verdict": "IDENTICO"}),
        encoding="utf-8",
    )
    before = report.read_text(encoding="utf-8")
    gate = gate_for_publication("ZZZ", second.manifest, store, config, tmp_path)
    assert gate.verdicts() == {"a": "IDENTICO", "b": "DIFERENTE"}  # b is not listed in the yaml and its old verdict is IDENTICO: compared all the same
    assert report.read_text(encoding="utf-8") == before  # nothing is written to the data root
    with pytest.raises(PublicationRefused):
        _publish(store, second, tmp_path, config)


def test_a_phase_with_no_comparison_refuses_the_publication_unless_it_is_named(tmp_path):
    store = _store_with_reference(tmp_path)
    second = _round(tmp_path / "r2", "run-2", {"a": 1, "b": 1, "c": 5})  # c is not in the reference round
    with pytest.raises(PublicationRefused, match=r"c: no comparison \(SEM_REFERENCIA\)"):
        _publish(store, second, tmp_path)
    assert store.latest("ZZZ") == "run-1"
    _, gate = _publish(store, second, tmp_path, without_reference=("c",))
    assert gate.verdicts()["c"] == "SEM_REFERENCIA" and store.latest("ZZZ") == "run-2"
    assert store.index("ZZZ", "run-2")["evidence"]["gate"]["allowed_without_reference"] == ["c"]


def test_the_first_reference_is_explicit(tmp_path):
    store = ReferenceStore(tmp_path / "references")
    first = _round(tmp_path / "r1", "run-1", {"a": 1, "b": 1})
    with pytest.raises(PublicationRefused, match="no reference round"):
        _publish(store, first, tmp_path)
    assert store.latest("ZZZ") is None
    _publish(store, first, tmp_path, first=True)
    assert store.latest("ZZZ") == "run-1"
    second = _round(tmp_path / "r2", "run-2", {"a": 1, "b": 1})
    with pytest.raises(PublicationRefused, match="already has a reference"):
        _publish(store, second, tmp_path, first=True)


def test_an_expected_entry_pinned_to_the_reference_of_now_passes_as_explicado_revisar(tmp_path):
    store = _store_with_reference(tmp_path)
    second = _round(tmp_path / "r2", "run-2", {"a": 1, "b": 2})
    config = tmp_path / "deferred_checks.yaml"

    def write(pin):
        spec = {"baseline": "latest", "reference_run": "latest", "phases": ["a"], "expected": {"b_summary": {"reason": "carries no result", "reference_run": pin}}}
        config.write_text(yaml.safe_dump({"countries": {"ZZZ": spec}}), encoding="utf-8")

    write("run-1")
    _, gate = _publish(store, second, tmp_path, config)
    assert gate.verdicts() == {"a": "IDENTICO", "b": "EXPLICADO_REVISAR"} and store.latest("ZZZ") == "run-2"
    # a pin to another reference explains nothing
    third = _round(tmp_path / "r3", "run-3", {"a": 1, "b": 3})
    write("run-0")
    with pytest.raises(PublicationRefused, match=r"b: DIFERENTE"):
        _publish(store, third, tmp_path, config)
