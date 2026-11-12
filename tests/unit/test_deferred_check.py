"""Deferred content check against a reference manifest (COMMAND 80; D-core-050)."""

from __future__ import annotations

import json
import re
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
                "countries": {"ZZZ": {"baseline": "reference_manifest.json", "phases": list(PHASES), "expected": expected or {}, "expected_reference_run": "r1"}},
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


def test_the_shipped_configuration_lists_prt_and_bra_with_the_twelve_phases_against_the_latest_round():
    checks = load_checks(REPO_ROOT / "config" / "deferred_checks.yaml", Path("D:/data"))
    assert set(checks) == {"PRT", "BRA"}  # IND left the check on 2026-11-12 (COMMAND 134); BRA stays for its F1b (docs/_audit/round_133.md)
    assert len(checks["BRA"].phases) == 12 and checks["BRA"].phases == checks["PRT"].phases
    for check in checks.values():  # the manifest and the rasters of the last accepted round of the reference store (COMMAND 91), not a backup directory
        assert check.baseline is None and check.reference_run == "latest" and check.baseline_label == "references/latest"
    # 2026-11-08 (COMMAND 104): the entries of COMMAND 101 (pinned to 74931e0a and 3a1b06e0) expired when the round 9c2dc3c8 was accepted and were removed, not
    # re-issued: no country declares a difference by design until a new round needs one.
    for iso in ("BRA", "PRT"):
        assert checks[iso].expected == {} and checks[iso].expected_pins == {}, iso
    assert all(phase in checks["BRA"].suspects for phase in checks["BRA"].phases)


def test_seed_records_only_the_phases_that_were_identical_and_leaves_the_rest_pending(tmp_path):
    from geofrea.core.deferred_check import CountryCheck, seed_from_comparison

    check = CountryCheck(iso="IND", baseline=tmp_path / "b.json", baseline_label="b", phases=("a", "b", "c", "d"))
    comparison = {
        "phases": [
            {"phase": "a", "status": "success"},
            {"phase": "b", "status": "success"},
            {"phase": "c", "status": "failed"},
            {"phase": "z", "status": "success"},
        ],
        "artifacts": {
            "a1": {"phase": "a", "status": "IDENTICO"},
            "a2": {"phase": "a", "status": "IDENTICO"},
            "b1": {"phase": "b", "status": "IDENTICO"},
            "b2": {"phase": "b", "status": "DIFERENTE"},
            "c1": {"phase": "c", "status": "IDENTICO"},
            "z1": {"phase": "z", "status": "IDENTICO"},
        },
    }
    manifest = {"phases": {"a": {"code_fingerprint": "fp-a"}}}
    report_path = tmp_path / "IND" / "deferred_check.json"

    assert seed_from_comparison(check, report_path, comparison, manifest, "round X") == ["a"]

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["phases"]["a"]["verdict"] == "IDENTICO" and report["phases"]["a"]["n_artifacts"] == 2
    assert report["phases"]["a"]["code_fingerprint"] == "fp-a" and report["phases"]["a"]["source"] == "round X"
    assert report["verdict"] == "PENDENTE" and report["pending"] == ["b", "c", "d"]


def test_a_seeded_phase_is_not_compared_again_by_the_pipeline(baseline):
    from geofrea.core.deferred_check import seed_from_comparison

    data, outputs, _ = baseline
    check = _check(data, outputs)
    seed_from_comparison(
        check.check,
        check.report_path,
        {"phases": [{"phase": "b", "status": "success"}], "artifacts": {"b_out": {"phase": "b", "status": "IDENTICO"}}},
        json.loads((outputs / "ZZZ" / "manifest.json").read_text(encoding="utf-8")),
        "an earlier round",
    )
    results = _orchestrator(outputs, check, rerun=PHASES).run(_specs({"a": 1, "b": 2, "c": 1}, SAME))  # b would differ, but it is settled
    assert results["c"].status == "success"
    assert _report(outputs)["phases"]["b"]["source"] == "an earlier round"


# --- COMMAND 91: the rasters that differ in the last bit are decided by tolerance against a reference copy ------------------------------------


def _raster(path: Path, data, nodata=-9999.0) -> Path:
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    arr = np.asarray(data, dtype="float32")
    with rasterio.open(
        path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1, dtype="float32", crs="EPSG:4326",
        transform=from_origin(10.0, 5.0, 0.01, 0.01), nodata=nodata,
    ) as dst:
        dst.write(arr, 1)
    return path


def _tolerance_case(tmp_path, new_values, *, reference_name="ZZZ_wind_weibull_a_100m_aligned.tif", key="siting/weibull_a_100m", expected=None, pin="seed"):
    """A reference round in the store with one raster and a run whose raster has `new_values`; returns the check, the manifest, the report path and the store."""
    from types import SimpleNamespace

    import numpy as np

    data = tmp_path / "data"
    refs = data / "refs"
    refs.mkdir(parents=True)
    (data / "outputs" / "ZZZ" / "siting").mkdir(parents=True)
    ref_values = np.linspace(1.0, 12.0, 6 * 8, dtype="float32").reshape(6, 8)
    _raster(refs / reference_name, ref_values)
    after = _raster(data / "outputs" / "ZZZ" / "siting" / "weibull_a_100m.tif", new_values(ref_values), nodata=-3.4028234663852886e38)
    baseline = data / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "phases": {"siting_layers": {"config_fingerprint": "c"}},
                "artifacts": {key: {"phase": "siting_layers", "sha256": "ref", "content_sha256": "tif:ref"}},
            }
        ),
        encoding="utf-8",
    )
    from geofrea.core.deferred_check import CountryCheck
    from geofrea.core.reference_store import ReferenceStore

    store = ReferenceStore(data / "references")
    store.import_directories("ZZZ", "seed", [refs], note="test")
    check = CountryCheck(
        iso="ZZZ", baseline=baseline, baseline_label="baseline", phases=("siting_layers",), expected=expected or {}, reference_run=pin
    )
    entry = SimpleNamespace(phase="siting_layers", content_sha256="tif:new", sha256="new", path=SimpleNamespace(resolve=lambda: after))
    manifest = SimpleNamespace(
        artifacts={key: entry}, phases={"siting_layers": SimpleNamespace(config_fingerprint="c", code_fingerprint="code")}
    )
    return check, manifest, data / "report.json", store


def test_a_raster_that_differs_in_the_last_bit_is_equivalent_by_tolerance_without_an_entry(tmp_path):
    check, manifest, report, store = _tolerance_case(tmp_path, lambda ref: ref * (1 + 1e-7))
    message = DeferredCheck(check, report, store).after_phase(manifest, "siting_layers")
    assert message is None
    entry = json.loads(report.read_text(encoding="utf-8"))
    phase = entry["phases"]["siting_layers"]
    assert phase["verdict"] == "EQUIVALENTE" and entry["verdict"] == "EQUIVALENTE" and phase["different_unexplained"] == {}
    assert phase["different_equivalent"]["siting/weibull_a_100m"]["reference"] == "ZZZ_wind_weibull_a_100m_aligned.tif"
    assert 0 < phase["different_equivalent"]["siting/weibull_a_100m"]["max_abs_delta"] < 1e-5


def test_a_raster_outside_the_tolerance_still_stops_the_run_and_the_report_says_by_how_much(tmp_path):
    check, manifest, report, store = _tolerance_case(tmp_path, lambda ref: ref * 1.001)
    message = DeferredCheck(check, report, store).after_phase(manifest, "siting_layers")
    assert message is not None and "siting/weibull_a_100m" in message
    phase = json.loads(report.read_text(encoding="utf-8"))["phases"]["siting_layers"]
    assert phase["verdict"] == "DIFERENTE"
    comparison = phase["different_unexplained"]["siting/weibull_a_100m"]["comparison"]
    assert comparison["equivalent"] is False and comparison["max_rel_delta"] > 1e-4


def test_a_raster_with_no_reference_copy_is_not_decided_by_tolerance(tmp_path):
    check, manifest, report, store = _tolerance_case(tmp_path, lambda ref: ref * (1 + 1e-7), reference_name="another_name.tif")
    assert DeferredCheck(check, report, store).after_phase(manifest, "siting_layers") is not None
    assert json.loads(report.read_text(encoding="utf-8"))["phases"]["siting_layers"]["verdict"] == "DIFERENTE"


def test_without_a_store_or_with_a_round_that_does_not_exist_nothing_is_decided_by_tolerance(tmp_path):
    from dataclasses import replace

    check, manifest, report, store = _tolerance_case(tmp_path, lambda ref: ref * (1 + 1e-7))
    assert DeferredCheck(check, report).after_phase(manifest, "siting_layers") is not None  # no store
    report.unlink()
    assert DeferredCheck(replace(check, reference_run="no_such_round"), report, store).after_phase(manifest, "siting_layers") is not None
    report.unlink()
    assert DeferredCheck(replace(check, reference_run="latest"), report, store).after_phase(manifest, "siting_layers") is not None  # an imported round is not latest


def test_the_reference_of_an_f2b_resource_layer_is_the_aligned_layer_it_copies(tmp_path):
    from geofrea.core.deferred_check import reference_file

    refs = tmp_path / "refs"
    refs.mkdir()
    for name in ("BRA_solar_aligned.tif", "BRA_wind_air_density_150m_aligned.tif", "BRA_wind_weibull_k_200m_aligned.tif", "BRA_roads_aligned.tif"):
        (refs / name).write_bytes(b"")
    out = tmp_path / "out"

    def find(name):
        return refs / name if (refs / name).is_file() else None

    assert reference_file("siting/pvout_kwh_kwp_day", out / "pvout_kwh_kwp_day.tif", "BRA", find) == refs / "BRA_solar_aligned.tif"
    assert reference_file("siting/air_density_150m", out / "air_density_150m.tif", "BRA", find) == refs / "BRA_wind_air_density_150m_aligned.tif"
    assert reference_file("siting/weibull_k_200m", out / "weibull_k_200m.tif", "BRA", find) == refs / "BRA_wind_weibull_k_200m_aligned.tif"
    assert reference_file("aligned/roads", out / "BRA_roads_aligned.tif", "BRA", find) == refs / "BRA_roads_aligned.tif"
    assert reference_file("siting/dist_road_km", out / "dist_road_km.tif", "BRA", find) is None  # a distance is not a copy of an aligned layer


def test_the_shipped_configuration_configures_the_reference_store():
    config = yaml.safe_load((REPO_ROOT / "config" / "deferred_checks.yaml").read_text(encoding="utf-8"))
    assert config["reference_store"]["root"] == "references" and ".json" in config["reference_store"]["suffixes"]
    assert {"grid_alignment", "siting_layers"} <= set(config["reference_store"]["raster_phases"])
    assert not [k for spec in config["countries"].values() for k in spec if k == "references"]  # no backup directory is read any more


def test_the_shipped_configuration_has_no_manual_entry_for_a_last_bit_difference():
    config = yaml.safe_load((REPO_ROOT / "config" / "deferred_checks.yaml").read_text(encoding="utf-8"))
    for iso in ("BRA",):
        spec = config["countries"][iso]
        assert spec["reference_run"] == "latest", iso  # the last accepted round of the store, not a backup directory
        assert not [k for k in (spec.get("expected") or {}) if re.fullmatch(r"siting/(weibull_a|weibull_k|air_density)_\d+m|siting/pvout_kwh_kwp_day", k)], iso


# --- the entries of `expected` are pinned to the reference they were declared against (COMMAND 96) --------------------------------------------------


def _store_check(baseline, expected, *, latest="r1", pin="r1"):
    """A check whose reference is the round `latest` of a store that holds the reference manifest; `expected` entries pinned to `pin`."""
    from geofrea.core.reference_store import ReferenceStore

    data, outputs, reference = baseline
    store = ReferenceStore(data / "references")
    store.publish_files("ZZZ", "r1", {}, manifest_data=json.loads(reference.read_text(encoding="utf-8")))
    if latest != "r1":
        store.publish_files("ZZZ", latest, {}, manifest_data=json.loads(reference.read_text(encoding="utf-8")))
    config = data / "deferred_checks.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "countries": {
                    "ZZZ": {
                        "baseline": "latest",
                        "reference_run": "latest",
                        "phases": list(PHASES),
                        "expected": {k: {"reason": v, "reference_run": pin} for k, v in expected.items()},
                    }
                },
                "suspects": {"b": "the code of phase b"},
            }
        ),
        encoding="utf-8",
    )
    check = for_country("zzz", config, data, outputs)
    assert check is not None
    return check


def test_an_entry_of_expected_needs_the_reference_it_was_declared_against():
    from geofrea.core.deferred_check import parse_expected

    reasons, pins = parse_expected(
        "ZZZ", {"expected_reference_run": "r1", "expected": {"a": "why a", "b": {"reason": "why b", "reference_run": "r0"}}}
    )
    assert reasons == {"a": "why a", "b": "why b"} and pins == {"a": "r1", "b": "r0"}
    with pytest.raises(ValueError, match="reference_run"):
        parse_expected("ZZZ", {"expected": {"a": "why a"}})  # no country pin, no entry pin
    with pytest.raises(ValueError, match="reason"):
        parse_expected("ZZZ", {"expected": {"a": {"reference_run": "r1"}}})


def test_an_entry_counts_while_its_reference_is_the_latest_and_expires_when_latest_moves(baseline):
    check = _store_check(baseline, {"b_out": "a report"})
    assert check.active_expected() == {"b_out": "a report"} and check.expired_expected() == {}
    moved = _store_check(baseline, {"b_out": "a report"}, latest="r2")  # r2 is now the last accepted round; the entry was declared against r1
    assert moved.reference_run_id() == "r2"
    assert moved.expired_expected() == {"b_out": "r1"} and moved.active_expected() == {}


def test_an_expired_entry_no_longer_explains_a_difference_and_the_gate_says_so(baseline, caplog):
    _, outputs, _ = baseline
    check = _store_check(baseline, {"b_out": "a report"}, latest="r2")
    with caplog.at_level("WARNING"):
        results = _orchestrator(outputs, check, rerun=PHASES).run(_specs({"a": 1, "b": 2, "c": 1}, SAME))
    assert _report(outputs)["phases"]["b"]["verdict"] == "DIFERENTE" and results["c"].status != "success"
    assert "no longer count" in caplog.text and "b_out" in caplog.text
    assert _report(outputs)["phases"]["b"]["expired_expected"] == ["b_out"]


def test_a_live_entry_still_explains_the_difference(baseline):
    _, outputs, _ = baseline
    check = _store_check(baseline, {"b_out": "a report"})
    results = _orchestrator(outputs, check, rerun=PHASES).run(_specs({"a": 1, "b": 2, "c": 1}, SAME))
    assert results["c"].status == "success" and _report(outputs)["phases"]["b"]["verdict"] == "EXPLICADO_REVISAR"


def test_the_script_lists_the_entries_that_can_be_removed(baseline, capsys):
    import importlib.util

    data, _, _ = baseline
    _store_check(baseline, {"b_out": "a report"}, latest="r2")
    spec = importlib.util.spec_from_file_location("list_expired_expected", REPO_ROOT / "scripts" / "list_expired_expected.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(["--data-dir", str(data), "--config", str(data / "deferred_checks.yaml")]) == 1
    out = capsys.readouterr().out
    assert "ZZZ" in out and "b_out" in out and "r2" in out
    _store_check(baseline, {"b_out": "a report"}, latest="r1", pin="r1")
    (data / "references" / "latest.json").write_text(json.dumps({"ZZZ": "r1"}), encoding="utf-8")
    assert module.main(["--data-dir", str(data), "--config", str(data / "deferred_checks.yaml")]) == 0
