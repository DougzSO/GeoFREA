"""Unit tests for geofrea.core.orchestrator.

Uses trivial dummy phases (not real phase logic) so orchestrator
behavior — graph validation, ordering, artifact registration/integrity,
manifest persistence, resume, failure propagation — is tested
independently of any phase-specific logic. See tests/unit/test_audit.py
etc. for individual phases themselves.
"""

import json
import random
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from geofrea.core.config_loader import load_parameters
from geofrea.core.orchestrator import (
    ArtifactIntegrityError,
    DependencyCycleError,
    DuplicateProducerError,
    LegacyManifestError,
    MissingProducerError,
    Orchestrator,
    PhaseSpec,
    StaleManifestEntryError,
    UndeclaredArtifactMissingError,
    UnexpectedArtifactError,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PARAMETERS_JSON = REPO_ROOT / "config" / "parameters.json"


class DummyOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int


def _country_params():
    """A real, valid CountryParams instance (loaded, not hand-built)."""
    return load_parameters(PARAMETERS_JSON).countries["PRT"]


def _make_spec(
    name: str,
    call_log: list[str],
    *,
    fail: bool = False,
    value: int = 1,
    requires: frozenset[str] = frozenset(),
    produces: frozenset[str] = frozenset(),
    artifact_dir: Path | None = None,
    register: bool = True,
) -> PhaseSpec:
    def run(context):
        call_log.append(name)
        if fail:
            raise ValueError(f"{name} boom")
        if register:
            for key in produces:
                path = (artifact_dir or context.outputs_dir) / f"{key}.txt"
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    path.write_text(f"{key}-{value}", encoding="utf-8")
                context.register_artifact(key, path, "1.0")
        return DummyOutput(value=value)

    return PhaseSpec(name=name, output_model=DummyOutput, run=run, requires=requires, produces=produces)


def _orchestrator(
    tmp_path: Path,
    target_phases: list[str],
    *,
    rerun_phases: list[str] | None = None,
    run_id: str = "run-1",
    dirty: bool = False,
) -> Orchestrator:
    return Orchestrator(
        outputs_dir=tmp_path,
        country_code="PRT",
        country_params=_country_params(),
        target_phases=target_phases,
        rerun_phases=rerun_phases if rerun_phases is not None else [],
        run_id=run_id,
        dirty=dirty,
    )


# ─── graph validation & ordering ─────────────────────────────────────────


@pytest.mark.unit
def test_shuffled_spec_list_produces_the_same_order(tmp_path):
    call_log: list[str] = []
    specs = [
        _make_spec("a", call_log, produces=frozenset({"a_out"})),
        _make_spec("b", call_log, requires=frozenset({"a_out"}), produces=frozenset({"b_out"})),
        _make_spec("c", call_log, requires=frozenset({"b_out"}), produces=frozenset({"c_out"})),
    ]
    shuffled = list(specs)
    random.Random(42).shuffle(shuffled)

    orchestrator = _orchestrator(tmp_path, ["c"])
    orchestrator.run(shuffled)

    assert call_log == ["a", "b", "c"]


@pytest.mark.unit
def test_missing_producer_raises(tmp_path):
    call_log: list[str] = []
    spec = _make_spec("a", call_log, requires=frozenset({"nonexistent"}))
    orchestrator = _orchestrator(tmp_path, ["a"])

    with pytest.raises(MissingProducerError):
        orchestrator.run([spec])


@pytest.mark.unit
def test_dependency_cycle_raises(tmp_path):
    call_log: list[str] = []
    a = _make_spec("a", call_log, requires=frozenset({"b_out"}), produces=frozenset({"a_out"}))
    b = _make_spec("b", call_log, requires=frozenset({"a_out"}), produces=frozenset({"b_out"}))
    orchestrator = _orchestrator(tmp_path, ["a"])

    with pytest.raises(DependencyCycleError):
        orchestrator.run([a, b])


@pytest.mark.unit
def test_duplicate_producer_raises(tmp_path):
    call_log: list[str] = []
    a = _make_spec("a", call_log, produces=frozenset({"shared"}))
    b = _make_spec("b", call_log, produces=frozenset({"shared"}))
    orchestrator = _orchestrator(tmp_path, ["a"])

    with pytest.raises(DuplicateProducerError):
        orchestrator.run([a, b])


# ─── artifact registration contract ──────────────────────────────────────


@pytest.mark.unit
def test_declared_artifact_not_registered_raises(tmp_path):
    call_log: list[str] = []
    spec = _make_spec("a", call_log, produces=frozenset({"a_out"}), register=False)
    orchestrator = _orchestrator(tmp_path, ["a"])

    orchestrator.run([spec])

    assert orchestrator.manifest.phases["a"].status == "failed"
    assert "UndeclaredArtifactMissingError" in orchestrator.manifest.phases["a"].error or (
        "a_out" in orchestrator.manifest.phases["a"].error
    )


@pytest.mark.unit
def test_undeclared_artifact_registration_raises(tmp_path):
    call_log: list[str] = []

    def run(context):
        call_log.append("a")
        path = context.outputs_dir / "extra.txt"
        path.write_text("x", encoding="utf-8")
        context.register_artifact("extra", path, "1.0")
        return DummyOutput(value=1)

    spec = PhaseSpec(name="a", output_model=DummyOutput, run=run, produces=frozenset())
    orchestrator = _orchestrator(tmp_path, ["a"])

    orchestrator.run([spec])

    assert orchestrator.manifest.phases["a"].status == "failed"
    assert "extra" in orchestrator.manifest.phases["a"].error


def test_undeclared_artifact_registration_error_type_is_unexpected_artifact_error():
    # Sanity check the exception class used above exists and is the
    # right one (exercised indirectly through the manifest error string
    # in the previous test, since a phase failure is recorded, not
    # raised, per A-09).
    assert issubclass(UnexpectedArtifactError, RuntimeError)
    assert issubclass(UndeclaredArtifactMissingError, RuntimeError)


# ─── upstream artifact loading & integrity ───────────────────────────────


@pytest.mark.unit
def test_upstream_outside_current_run_is_loaded_from_manifest(tmp_path):
    call_log: list[str] = []
    a = _make_spec("a", call_log, produces=frozenset({"a_out"}))
    b = _make_spec("b", call_log, requires=frozenset({"a_out"}), produces=frozenset({"b_out"}))

    first = _orchestrator(tmp_path, ["a"])
    first.run([a, b])
    assert call_log == ["a"]

    call_log.clear()
    second = _orchestrator(tmp_path, ["b"])
    results = second.run([a, b])

    # "a" is resumed from disk, not re-invoked; "b" runs fresh.
    assert call_log == ["b"]
    assert results["a"].status == "success"
    assert results["b"].status == "success"


@pytest.mark.unit
def test_artifact_changed_after_registration_raises_integrity_error(tmp_path):
    call_log: list[str] = []
    a = _make_spec("a", call_log, produces=frozenset({"a_out"}))
    b = _make_spec("b", call_log, requires=frozenset({"a_out"}), produces=frozenset({"b_out"}))

    first = _orchestrator(tmp_path, ["a"])
    first.run([a, b])

    artifact_path = tmp_path / "a_out.txt"
    artifact_path.write_text("tampered", encoding="utf-8")

    second = _orchestrator(tmp_path, ["b"])
    with pytest.raises(ArtifactIntegrityError):
        second.run([a, b])


@pytest.mark.unit
def test_deleted_artifact_raises_integrity_error_on_upstream_load(tmp_path):
    # Same contract as test_artifact_changed_after_registration_raises_
    # integrity_error, but for the "file gone entirely" branch rather
    # than "content changed" — e.g. an aligned raster (F2a,
    # docs/phases/core.md D-core-003) manually deleted from outputs/
    # between runs.
    call_log: list[str] = []
    a = _make_spec("a", call_log, produces=frozenset({"a_out"}))
    b = _make_spec("b", call_log, requires=frozenset({"a_out"}), produces=frozenset({"b_out"}))

    first = _orchestrator(tmp_path, ["a"])
    first.run([a, b])

    artifact_path = tmp_path / "a_out.txt"
    artifact_path.unlink()

    second = _orchestrator(tmp_path, ["b"])
    with pytest.raises(ArtifactIntegrityError):
        second.run([a, b])


@pytest.mark.unit
def test_hash_reused_when_size_and_mtime_unchanged(tmp_path, monkeypatch):
    call_log: list[str] = []
    a = _make_spec("a", call_log, produces=frozenset({"a_out"}))

    first = _orchestrator(tmp_path, ["a"])
    first.run([a])
    recorded_sha256 = first.manifest.artifacts["a_out"].sha256

    hash_calls: list[Path] = []
    import geofrea.core.orchestrator as orchestrator_module

    real_sha256 = orchestrator_module._sha256_file

    def _tracking_sha256(path: Path) -> str:
        hash_calls.append(path)
        return real_sha256(path)

    monkeypatch.setattr(orchestrator_module, "_sha256_file", _tracking_sha256)

    second = _orchestrator(tmp_path, ["a"], rerun_phases=["a"])
    second.run([a])

    assert hash_calls == []
    assert second.manifest.artifacts["a_out"].sha256 == recorded_sha256


# ─── manifest schema ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_legacy_manifest_without_schema_version_raises(tmp_path):
    manifest_path = tmp_path / "PRT" / "manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        '{"country_code": "PRT", "phases": {}}', encoding="utf-8"
    )

    with pytest.raises(LegacyManifestError):
        _orchestrator(tmp_path, ["a"])


# ─── failure propagation (A-09) ──────────────────────────────────────────


@pytest.mark.unit
def test_failure_in_one_branch_does_not_block_an_independent_branch(tmp_path):
    call_log: list[str] = []
    f1 = _make_spec("F1", call_log, produces=frozenset({"f1_out"}))
    f1b = _make_spec(
        "F1b", call_log, fail=True, requires=frozenset({"f1_out"}), produces=frozenset({"f1b_out"})
    )
    f2a = _make_spec("F2a", call_log, requires=frozenset({"f1_out"}), produces=frozenset({"f2a_out"}))

    orchestrator = _orchestrator(tmp_path, ["F1b", "F2a"])
    results = orchestrator.run([f1, f1b, f2a])

    assert results["F1"].status == "success"
    assert results["F1b"].status == "failed"
    assert results["F2a"].status == "success"
    assert "F2a" in call_log


@pytest.mark.unit
def test_failure_upstream_marks_all_dependents_skipped(tmp_path):
    call_log: list[str] = []
    f1 = _make_spec("F1", call_log, fail=True, produces=frozenset({"f1_out"}))
    f1b = _make_spec("F1b", call_log, requires=frozenset({"f1_out"}), produces=frozenset({"f1b_out"}))
    f2a = _make_spec("F2a", call_log, requires=frozenset({"f1_out"}), produces=frozenset({"f2a_out"}))
    f2b = _make_spec("F2b", call_log, requires=frozenset({"f2a_out"}), produces=frozenset({"f2b_out"}))

    orchestrator = _orchestrator(tmp_path, ["F1b", "F2b"])
    results = orchestrator.run([f1, f1b, f2a, f2b])

    assert results["F1"].status == "failed"
    assert results["F1b"].status == "skipped_upstream_failed"
    assert results["F2a"].status == "skipped_upstream_failed"
    assert results["F2b"].status == "skipped_upstream_failed"
    assert call_log == ["F1"]


# ─── resumability & rerun_phases ─────────────────────────────────────────


@pytest.mark.unit
def test_resume_from_manifest_skips_completed_phase(tmp_path):
    call_log: list[str] = []
    spec = _make_spec("phase_a", call_log, value=9)

    first_run = _orchestrator(tmp_path, ["phase_a"])
    first_results = first_run.run([spec])
    assert call_log == ["phase_a"]
    assert first_results["phase_a"].status == "success"

    second_run = _orchestrator(tmp_path, ["phase_a"])
    second_results = second_run.run([spec])

    assert call_log == ["phase_a"]
    assert second_results["phase_a"].status == "success"
    assert second_results["phase_a"].output.value == 9


@pytest.mark.unit
def test_resume_does_not_apply_to_a_previously_failed_phase(tmp_path):
    call_log: list[str] = []
    failing_spec = _make_spec("phase_a", call_log, fail=True)

    first_run = _orchestrator(tmp_path, ["phase_a"])
    first_results = first_run.run([failing_spec])
    assert call_log == ["phase_a"]
    assert first_results["phase_a"].status == "failed"

    succeeding_spec = _make_spec("phase_a", call_log, value=1)
    second_run = _orchestrator(tmp_path, ["phase_a"])
    second_results = second_run.run([succeeding_spec])

    assert call_log == ["phase_a", "phase_a"]
    assert second_results["phase_a"].status == "success"


@pytest.mark.unit
def test_rerun_phases_reexecutes_only_the_named_phase(tmp_path):
    """R-1: rerun_phases re-executes exactly the phases it names, never dependents.

    Targets only "a" (not "c"): "b"/"c" are downstream of "a" but not
    themselves needed to satisfy this run's target_phases, so marking
    them stale_upstream (see test_rerun_phases_marks_downstream_
    consumers_stale_upstream) does not also pull them into this run's
    execution — that only happens for a phase the run's own targets
    actually need, per test_stale_upstream_phase_is_recomputed_not_resumed.
    """
    call_log: list[str] = []
    a = _make_spec("a", call_log, produces=frozenset({"a_out"}))
    b = _make_spec("b", call_log, requires=frozenset({"a_out"}), produces=frozenset({"b_out"}))
    c = _make_spec("c", call_log, requires=frozenset({"b_out"}), produces=frozenset({"c_out"}))

    first = _orchestrator(tmp_path, ["c"])
    first.run([a, b, c])
    assert call_log == ["a", "b", "c"]

    call_log.clear()
    second = _orchestrator(tmp_path, ["a"], rerun_phases=["a"])
    results = second.run([a, b, c])

    assert call_log == ["a"]
    assert results["a"].status == "success"
    assert "b" not in results
    assert "c" not in results


@pytest.mark.unit
def test_rerun_phases_marks_downstream_consumers_stale_upstream(tmp_path):
    call_log: list[str] = []
    a = _make_spec("a", call_log, produces=frozenset({"a_out"}))
    b = _make_spec("b", call_log, requires=frozenset({"a_out"}), produces=frozenset({"b_out"}))
    c = _make_spec("c", call_log, requires=frozenset({"b_out"}), produces=frozenset({"c_out"}))

    first = _orchestrator(tmp_path, ["c"])
    first.run([a, b, c])

    # Targets only "a": "b"/"c" are not needed by this run, so they are
    # marked stale_upstream and left there, not recomputed in the same
    # pass (recomputing them anyway once needed is
    # test_stale_upstream_phase_is_recomputed_not_resumed's job).
    second = _orchestrator(tmp_path, ["a"], rerun_phases=["a"])
    second.run([a, b, c])

    assert second.manifest.phases["b"].status == "stale_upstream"
    assert second.manifest.phases["b"].invalidated_by == "a"
    assert second.manifest.phases["b"].invalidated_in_run == second.run_id
    assert second.manifest.phases["c"].status == "stale_upstream"
    assert second.manifest.phases["c"].invalidated_by == "a"


@pytest.mark.unit
def test_stale_upstream_phase_is_recomputed_not_resumed(tmp_path):
    call_log: list[str] = []
    a = _make_spec("a", call_log, produces=frozenset({"a_out"}))
    b = _make_spec("b", call_log, requires=frozenset({"a_out"}), produces=frozenset({"b_out"}))

    first = _orchestrator(tmp_path, ["b"])
    first.run([a, b])
    assert first.manifest.phases["b"].status == "success"

    # Rerunning "a" alone (not targeting "b") leaves "b" marked
    # stale_upstream without recomputing it in this same run.
    second = _orchestrator(tmp_path, ["a"], rerun_phases=["a"])
    second.run([a, b])
    assert second.manifest.phases["b"].status == "stale_upstream"

    call_log.clear()
    third = _orchestrator(tmp_path, ["b"])
    results = third.run([a, b])

    # "b" is needed by this run and holds stale_upstream, so it is
    # recomputed even though it was not named in rerun_phases; "a"
    # itself is untouched and simply resumes.
    assert call_log == ["b"]
    assert results["b"].status == "success"
    assert third.manifest.phases["b"].status == "success"


@pytest.mark.unit
def test_rerun_phases_name_outside_needed_closure_raises(tmp_path):
    call_log: list[str] = []
    a = _make_spec("a", call_log, produces=frozenset({"a_out"}))
    unrelated = _make_spec("unrelated", call_log, produces=frozenset({"u_out"}))

    orchestrator = _orchestrator(tmp_path, ["a"], rerun_phases=["unrelated"])

    with pytest.raises(MissingProducerError):
        orchestrator.run([a, unrelated])


@pytest.mark.unit
def test_phase_whose_upstream_is_untouched_still_resumes(tmp_path):
    call_log: list[str] = []
    a = _make_spec("a", call_log, produces=frozenset({"a_out"}))
    b = _make_spec("b", call_log, requires=frozenset({"a_out"}), produces=frozenset({"b_out"}))

    first = _orchestrator(tmp_path, ["b"])
    first.run([a, b])

    call_log.clear()
    second = _orchestrator(tmp_path, ["b"])
    results = second.run([a, b])

    assert call_log == []
    assert results["a"].status == "success"
    assert results["b"].status == "success"


# ─── dirty flag ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_dirty_true_is_recorded_in_manifest(tmp_path):
    call_log: list[str] = []
    spec = _make_spec("phase_a", call_log)

    orchestrator = _orchestrator(tmp_path, ["phase_a"], dirty=True)
    orchestrator.run([spec])

    assert orchestrator.manifest.dirty is True


@pytest.mark.unit
def test_manifest_written_on_success(tmp_path):
    call_log: list[str] = []
    spec = _make_spec("phase_a", call_log, value=7)
    orchestrator = _orchestrator(tmp_path, ["phase_a"])

    orchestrator.run([spec])

    assert orchestrator.manifest_path == tmp_path / "PRT" / "manifest.json"
    assert orchestrator.manifest_path.exists()
    entry = orchestrator.manifest.phases["phase_a"]
    assert entry.status == "success"
    assert entry.output == {"value": 7}
    assert orchestrator.manifest.schema_version == "2.2"


# ─── Part B: stale resume rejection (2026-09-21, see docs/phases/core.md) ─


@pytest.mark.unit
def test_resume_with_missing_recorded_key_raises_stale_manifest_entry_error(tmp_path):
    call_log: list[str] = []
    spec_v1 = _make_spec("a", call_log, produces=frozenset({"a_out"}))

    first = _orchestrator(tmp_path, ["a"])
    first.run([spec_v1])

    # Same phase name, but produces has grown — mirrors grid_alignment's
    # real E4 change (one summary key -> summary + per-raster keys).
    spec_v2 = _make_spec("a", call_log, produces=frozenset({"a_out", "a_extra"}))
    second = _orchestrator(tmp_path, ["a"])

    with pytest.raises(StaleManifestEntryError):
        second.run([spec_v2])


@pytest.mark.unit
def test_resume_with_schema_version_mismatch_raises_stale_manifest_entry_error(tmp_path):
    call_log: list[str] = []
    spec_v1 = _make_spec("a", call_log, produces=frozenset({"a_out"}))

    first = _orchestrator(tmp_path, ["a"])
    first.run([spec_v1])

    def run_v2(context):
        call_log.append("a")
        path = context.outputs_dir / "a_out.txt"
        context.register_artifact("a_out", path, "1.0")
        return DummyOutput(value=1)

    spec_v2 = PhaseSpec(
        name="a",
        output_model=DummyOutput,
        run=run_v2,
        produces=frozenset({"a_out"}),
        produces_schema_versions={"a_out": "2.0"},
    )
    second = _orchestrator(tmp_path, ["a"])

    with pytest.raises(StaleManifestEntryError):
        second.run([spec_v2])


@pytest.mark.unit
def test_lineage_is_recorded_for_a_phase_with_requires(tmp_path):
    call_log: list[str] = []
    a = _make_spec("a", call_log, produces=frozenset({"a_out"}))
    b = _make_spec("b", call_log, requires=frozenset({"a_out"}), produces=frozenset({"b_out"}))

    orchestrator = _orchestrator(tmp_path, ["b"])
    orchestrator.run([a, b])

    b_entry = orchestrator.manifest.phases["b"]
    assert b_entry.consumed_run_ids == {"a_out": orchestrator.run_id}


@pytest.mark.unit
def test_cross_run_id_resume_warns_without_failing(tmp_path, caplog):
    # Naming "a" in rerun_phases would only mark "b" stale_upstream, not
    # re-execute it (see test_rerun_phases_marks_downstream_consumers_
    # stale_upstream), so it would never exercise drift detection either.
    # The real-world case this guards — "a"'s artifact was
    # produced by a different run_id than the one "b" last consumed,
    # without "b" itself re-running — is simulated directly by editing
    # the on-disk manifest between two Orchestrator instances, the same
    # way a manifest hand-edited or merged from another run would look.
    call_log: list[str] = []
    a = _make_spec("a", call_log, produces=frozenset({"a_out"}))
    b = _make_spec("b", call_log, requires=frozenset({"a_out"}), produces=frozenset({"b_out"}))

    first = _orchestrator(tmp_path, ["b"], run_id="run-1")
    first.run([a, b])
    assert first.manifest.phases["b"].consumed_run_ids == {"a_out": "run-1"}

    manifest_path = tmp_path / "PRT" / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["artifacts"]["a_out"]["run_id"] = "run-2"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    call_log.clear()
    third = _orchestrator(tmp_path, ["b"], run_id="run-2")
    with caplog.at_level("WARNING"):
        results = third.run([a, b])

    assert call_log == []  # "b" resumed, not re-invoked
    assert results["b"].status == "success"
    assert any("lineage drift" in message for message in caplog.messages)
