"""The reference store: what is kept of an accepted round, when, and how the check reads it (COMMAND 91; D-core-051)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import rasterio
from pydantic import BaseModel, ConfigDict
from rasterio.transform import from_origin

from geofrea.core.config_loader import load_parameters
from geofrea.core.deferred_check import CountryCheck, DeferredCheck, load_store
from geofrea.core.orchestrator import Orchestrator, PhaseSpec
from geofrea.core.reference_store import ReferenceStore, StoreConfig

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]


def _tif(path: Path, value: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path, "w", driver="GTiff", height=4, width=5, count=1, dtype="float32", crs="EPSG:4326", transform=from_origin(10.0, 5.0, 0.01, 0.01), nodata=-9999.0
    ) as dst:
        dst.write(np.full((4, 5), value, dtype="float32"), 1)
    return path


def _result(status="success", wall_s=1.0):
    return SimpleNamespace(status=status, wall_s=wall_s)


# --- the store itself ------------------------------------------------------------------------------------------------------------------


def test_a_round_keeps_the_files_once_across_rounds_and_latest_follows_the_last_accepted(tmp_path):
    store = ReferenceStore(tmp_path / "references")
    a = tmp_path / "a.json"
    a.write_text(json.dumps({"n": 1}), encoding="utf-8")
    layer = _tif(tmp_path / "layer.tif", 3.0)
    store.publish_files("ZZZ", "run1", {"outputs/ZZZ/artifacts/summary.json": (a, None, {"phase": "p"}), "outputs/ZZZ/x/layer.tif": (layer, None, {})})
    a.write_text(json.dumps({"n": 2}), encoding="utf-8")  # the summary changes, the layer does not
    store.publish_files("ZZZ", "run2", {"outputs/ZZZ/artifacts/summary.json": (a, None, {}), "outputs/ZZZ/x/layer.tif": (layer, None, {})})
    assert store.latest("ZZZ") == "run2" and store.latest("zzz") == "run2" and store.latest("BRA") is None
    assert store.json_summary("ZZZ", "run1", "summary.json") == {"n": 1} and store.json_summary("ZZZ", "latest", "summary.json") == {"n": 2}
    objects = [p for p in (store.root / "objects").rglob("*") if p.is_file()]
    assert len(objects) == 3  # two summaries and one layer: the layer is kept once for two rounds
    assert store.find("ZZZ", "run1", "layer.tif").read_bytes() == layer.read_bytes()
    assert store.find("ZZZ", "run1", "nothing.tif") is None and store.resolve("ZZZ", "no_such") is None
    assert store.index("ZZZ", "run2")["files"]["outputs/ZZZ/artifacts/summary.json"]["size_bytes"] > 0


def test_a_file_that_is_not_the_one_the_manifest_recorded_refuses_the_round_and_writes_nothing(tmp_path):
    store = ReferenceStore(tmp_path / "references")
    f = tmp_path / "f.json"
    f.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="not the one the manifest recorded"):
        store.publish_files("ZZZ", "run1", {"outputs/ZZZ/f.json": (f, "0" * 64, {})})
    assert not store.round_dir("ZZZ", "run1").exists() and store.latest("ZZZ") is None


def test_an_imported_directory_is_a_round_that_is_not_latest(tmp_path):
    store = ReferenceStore(tmp_path / "references")
    backup = tmp_path / "backup"
    _tif(backup / "ZZZ_solar_aligned.tif", 1.0)
    (backup / "note.txt").write_text("not kept", encoding="utf-8")
    (backup / "x.tif.cachekey").write_text("not kept", encoding="utf-8")
    store.import_directories("ZZZ", "seed_1", [backup], note="by hand")
    assert store.latest("ZZZ") is None and store.resolve("ZZZ", "latest") is None
    index = store.index("ZZZ", "seed_1")
    assert list(index["files"]) == ["outputs/ZZZ/imported/backup/ZZZ_solar_aligned.tif"] and index["note"] == "by hand"
    assert store.find("ZZZ", "seed_1", "ZZZ_solar_aligned.tif") is not None


def test_a_round_is_accepted_only_if_it_executed_something_and_nothing_failed_or_was_blocked():
    accepts = ReferenceStore.accepts

    class Check:
        def __init__(self, blocked):
            self._blocked = blocked

        def blocked_phases(self):
            return self._blocked

    assert accepts({"a": _result(), "b": _result(wall_s=None)})[0]
    assert not accepts({})[0]
    assert "did not end success" in accepts({"a": _result(), "b": _result("failed")})[1]
    assert "skipped_upstream_failed" not in accepts({"a": _result("skipped_upstream_failed")})[1] and not accepts({"a": _result("skipped_upstream_failed")})[0]
    assert "resumed" in accepts({"a": _result(wall_s=None)})[1]
    assert accepts({"a": _result()}, Check([]))[0]
    ok, why = accepts({"a": _result()}, Check(["land_eligibility"]))
    assert not ok and "land_eligibility" in why


# --- the pipeline keeps the round when it is accepted ----------------------------------------------------------------------------------


class Out(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int


def _specs(fail: bool = False) -> list[PhaseSpec]:
    def make(name, requires=frozenset(), produces=frozenset()):
        def run(context):
            summary = context.outputs_dir / f"{name}_summary.json"
            summary.write_text(json.dumps({"phase": name}), encoding="utf-8")
            context.register_artifact(f"{name}_summary", summary, "1.0")
            table = context.outputs_dir / f"{name}.txt"
            table.write_text("not kept", encoding="utf-8")
            context.register_artifact(f"{name}_table", table, "1.0")
            layer = _tif(context.outputs_dir / f"{name}_layer.tif", 2.0)
            context.register_artifact(f"{name}_layer", layer, "1.0")
            if fail and name == "b":
                raise RuntimeError("forced")
            return Out(value=1)

        return PhaseSpec(name=name, output_model=Out, run=run, requires=requires, produces=produces)

    return [
        make("a", produces=frozenset({"a_summary", "a_table", "a_layer"})),
        make("b", requires=frozenset({"a_summary"}), produces=frozenset({"b_summary", "b_table", "b_layer"})),
    ]


def _orchestrator(outputs: Path, store, run_id: str, check=None):
    return Orchestrator(
        outputs_dir=outputs,
        country_code="ZZZ",
        country_params=load_parameters(REPO_ROOT / "config" / "parameters.json").countries["PRT"],
        target_phases=["b"],
        rerun_phases=[],
        run_id=run_id,
        methodology_version="test",
        dirty=False,
        deferred_check=check,
        reference_store=store,
    )


def test_the_orchestrator_keeps_the_summaries_and_the_layers_of_an_accepted_round_and_not_the_tables(tmp_path):
    outputs = tmp_path / "data" / "outputs"
    (outputs / "ZZZ").mkdir(parents=True)
    store = ReferenceStore(tmp_path / "data" / "references", StoreConfig(raster_phases=("a",)))
    _orchestrator(outputs, store, "run-1").run(_specs())
    assert store.latest("ZZZ") == "run-1"
    index = store.index("ZZZ", "run-1")
    kept = sorted(Path(rel).name for rel in index["files"])
    assert kept == ["a_layer.tif", "a_summary.json", "b_summary.json"]  # b's layer is of a phase that is not in raster_phases; no .txt table
    assert (store.round_dir("ZZZ", "run-1") / "manifest.json").is_file() and set(index["phases"]) == {"a", "b"}
    assert store.json_summary("ZZZ", "latest", "b_summary.json") == {"phase": "b"}
    # a round that only resumes keeps nothing new
    _orchestrator(outputs, store, "run-2").run(_specs())
    assert store.latest("ZZZ") == "run-1" and not store.round_dir("ZZZ", "run-2").exists()


def test_a_round_with_a_failed_phase_is_not_kept(tmp_path):
    outputs = tmp_path / "data" / "outputs"
    (outputs / "ZZZ").mkdir(parents=True)
    store = ReferenceStore(tmp_path / "data" / "references")
    _orchestrator(outputs, store, "run-1").run(_specs(fail=True))
    assert store.latest("ZZZ") is None and not store.round_dir("ZZZ", "run-1").exists()


def test_a_round_with_a_phase_the_check_found_different_is_not_kept(tmp_path):
    outputs = tmp_path / "data" / "outputs"
    (outputs / "ZZZ").mkdir(parents=True)
    store = ReferenceStore(tmp_path / "data" / "references")

    class Blocked:
        def after_phase(self, manifest, phase):
            return None

        def blocked_phases(self):
            return ["a"]

        def verdicts(self):
            return {"a": "DIFERENTE"}

    _orchestrator(outputs, store, "run-1", Blocked()).run(_specs())
    assert store.latest("ZZZ") is None


def test_the_store_of_the_shipped_configuration_is_under_the_data_root(tmp_path):
    store = load_store(REPO_ROOT / "config" / "deferred_checks.yaml", tmp_path)
    assert store.root == tmp_path / "references" and ".json" in store.config.suffixes and "siting_layers" in store.config.raster_phases
    assert load_store(tmp_path / "absent.yaml", tmp_path).config == StoreConfig()


def test_the_check_reads_the_last_accepted_round_when_the_country_says_latest(tmp_path):
    """A round published by the pipeline is what `reference_run: latest` compares with; a raster equal to it within the tolerance passes."""
    data = tmp_path / "data"
    store = ReferenceStore(data / "references")
    layer = _tif(data / "outputs" / "ZZZ" / "grid_alignment" / "ZZZ_wind_weibull_a_100m_aligned.tif", 5.0)
    store.publish_files("ZZZ", "accepted-1", {"outputs/ZZZ/grid_alignment/ZZZ_wind_weibull_a_100m_aligned.tif": (layer, None, {})})
    after = _tif(data / "outputs" / "ZZZ" / "siting" / "weibull_a_100m.tif", 5.0 * (1 + 1e-7))
    baseline = data / "baseline.json"
    baseline.write_text(
        json.dumps({"phases": {"siting_layers": {"config_fingerprint": "c"}}, "artifacts": {"siting/weibull_a_100m": {"phase": "siting_layers", "sha256": "x", "content_sha256": "tif:x"}}}),
        encoding="utf-8",
    )
    entry = SimpleNamespace(phase="siting_layers", content_sha256="tif:y", sha256="y", path=SimpleNamespace(resolve=lambda: after))
    manifest = SimpleNamespace(artifacts={"siting/weibull_a_100m": entry}, phases={"siting_layers": SimpleNamespace(config_fingerprint="c", code_fingerprint="k")})
    check = CountryCheck(iso="ZZZ", baseline=baseline, baseline_label="b", phases=("siting_layers",), reference_run="latest")
    assert DeferredCheck(check, data / "report.json", store).after_phase(manifest, "siting_layers") is None
    verdict = json.loads((data / "report.json").read_text(encoding="utf-8"))["phases"]["siting_layers"]
    assert verdict["verdict"] == "EQUIVALENTE" and verdict["different_equivalent"]["siting/weibull_a_100m"]["reference"] == "ZZZ_wind_weibull_a_100m_aligned.tif"


# --- the state of a country kept by hand, historical rounds, and a baseline that is the store ---------------------------------------------


def _manifest_with_a_stale_phase(tmp_path):
    from geofrea.core.orchestrator import RunManifest

    outputs = tmp_path / "data" / "outputs"
    (outputs / "ZZZ").mkdir(parents=True)
    _orchestrator(outputs, None, "run-1").run(_specs())
    path = outputs / "ZZZ" / "manifest.json"
    manifest = RunManifest.model_validate_json(path.read_text(encoding="utf-8"))
    return manifest, path


def test_the_state_of_a_country_keeps_only_the_phases_that_ended_success_and_says_which_it_left_out(tmp_path):
    manifest, path = _manifest_with_a_stale_phase(tmp_path)
    manifest.phases["b"].status = "stale_upstream"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["phases"]["b"]["status"] = "stale_upstream"
    path.write_text(json.dumps(data), encoding="utf-8")
    store = ReferenceStore(tmp_path / "data" / "references", StoreConfig(raster_phases=("a", "b")))
    store.publish_state(manifest, path, None, evidence={"note": "by hand"})
    index = store.index("ZZZ", "run-1")
    assert sorted(Path(r).name for r in index["files"]) == ["a_layer.tif", "a_summary.json"]  # nothing of b, which waits for a rerun
    assert index["not_kept_phases"] == {"b": "stale_upstream"} and index["status"] == "state" and index["evidence"] == {"note": "by hand"}
    kept = json.loads((store.round_dir("ZZZ", "run-1") / "manifest.json").read_text(encoding="utf-8"))
    assert set(kept["phases"]) == {"a"} and {a["phase"] for a in kept["artifacts"].values()} == {"a"}  # a later run is not compared with b's old artifacts
    assert store.latest("ZZZ") == "run-1" and store.manifest_path("ZZZ", "latest") == store.round_dir("ZZZ", "run-1") / "manifest.json"


def test_the_state_of_a_country_is_refused_when_a_phase_failed_or_the_check_is_blocked(tmp_path):
    manifest, path = _manifest_with_a_stale_phase(tmp_path)
    store = ReferenceStore(tmp_path / "data" / "references")

    class Blocked:
        def blocked_phases(self):
            return ["a"]

        def verdicts(self):
            return {"a": "DIFERENTE"}

    with pytest.raises(ValueError, match="DIFERENTE"):
        store.publish_state(manifest, path, Blocked(), evidence={})
    manifest.phases["b"].status = "failed"
    with pytest.raises(ValueError, match="failed"):
        store.publish_state(manifest, path, None, evidence={})
    assert store.latest("ZZZ") is None and not store.round_dir("ZZZ", "run-1").exists()


def test_a_round_marked_historical_is_kept_readable_and_pinnable(tmp_path):
    store = ReferenceStore(tmp_path / "references")
    backup = tmp_path / "backup"
    _tif(backup / "ZZZ_solar_aligned.tif", 1.0)
    store.import_directories("ZZZ", "seed_1", [backup], note="by hand")
    assert store.status("ZZZ", "seed_1") == "imported"
    store.mark_historical("ZZZ", "seed_1", "replaced by the state after COMMAND 91")
    index = store.index("ZZZ", "seed_1")
    assert store.status("ZZZ", "seed_1") == "historical" and index["status_before"] == "imported" and "replaced" in index["historical_note"]
    assert store.find("ZZZ", "seed_1", "ZZZ_solar_aligned.tif") is not None and store.resolve("ZZZ", "seed_1") == "seed_1"


def test_a_baseline_of_latest_is_the_manifest_of_the_round_in_the_store_and_a_report_of_another_baseline_starts_again(tmp_path):
    import yaml

    manifest, path = _manifest_with_a_stale_phase(tmp_path)
    data = tmp_path / "data"
    store = ReferenceStore(data / "references")
    store.publish_state(manifest, path, None, evidence={})
    config = data / "deferred_checks.yaml"
    config.write_text(yaml.safe_dump({"countries": {"ZZZ": {"baseline": "latest", "reference_run": "latest", "phases": ["a", "b"]}}}), encoding="utf-8")
    from geofrea.core.deferred_check import load_checks

    check = load_checks(config, data)["ZZZ"]
    assert check.baseline is None and check.baseline_label == "references/latest"
    report = data / "outputs" / "ZZZ" / "deferred_check.json"
    gate = DeferredCheck(check, report, store)
    assert gate.after_phase(manifest, "a") is None and gate.after_phase(manifest, "b") is None  # the state against itself
    phases = json.loads(report.read_text(encoding="utf-8"))["phases"]
    assert phases["a"]["verdict"] == "IDENTICO" and phases["b"]["verdict"] == "IDENTICO" and gate.blocked_phases() == []
    # a report made against another baseline is not reused
    old = json.loads(report.read_text(encoding="utf-8"))
    old["baseline"] = "outputs/ZZZ/old/manifest_before.json"
    old["phases"]["a"]["verdict"] = "DIFERENTE"
    report.write_text(json.dumps(old), encoding="utf-8")
    assert DeferredCheck(check, report, store).verdicts() == {}
    # a country with nothing in the store has no reference: nothing is compared and the run is not stopped
    empty = DeferredCheck(check, data / "empty.json", ReferenceStore(data / "nothing"))
    assert empty.after_phase(manifest, "a") is None
    assert json.loads((data / "empty.json").read_text(encoding="utf-8"))["phases"]["a"]["verdict"] == "SEM_REFERENCIA"


def test_two_countries_of_one_run_id_are_two_rounds_and_a_round_kept_again_is_set_aside_not_deleted(tmp_path):
    """The run_id of a manifest names the code of the run, not the country: the countries of one unattended round share it (found when PRT, IND and BRA were
    kept on 2026-11-04 and each replaced the one before)."""
    store = ReferenceStore(tmp_path / "references")
    f = tmp_path / "f.json"
    f.write_text(json.dumps({"v": 1}), encoding="utf-8")
    store.publish_files("AAA", "same-run", {"outputs/AAA/f.json": (f, None, {})})
    store.publish_files("BBB", "same-run", {"outputs/BBB/f.json": (f, None, {})})
    assert store.latest("AAA") == store.latest("BBB") == "same-run"
    assert store.index("AAA", "same-run")["country"] == "AAA" and list(store.index("BBB", "same-run")["files"]) == ["outputs/BBB/f.json"]
    assert store.find("AAA", "latest", "f.json") != store.find("BBB", "latest", "f.json")
    f.write_text(json.dumps({"v": 2}), encoding="utf-8")  # the same pair kept again
    store.publish_files("AAA", "same-run", {"outputs/AAA/f.json": (f, None, {})})
    assert store.json_summary("AAA", "latest", "f.json") == {"v": 2} and store.json_summary("BBB", "latest", "f.json") == {"v": 1}
    superseded = [d for d in (store.root / "same-run").iterdir() if ".superseded_" in d.name]
    assert len(superseded) == 1 and json.loads(next((superseded[0] / "files").rglob("f.json")).read_text(encoding="utf-8")) == {"v": 1}
