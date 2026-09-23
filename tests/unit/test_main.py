"""Unit tests for main.py's phase wiring.

main.py lives at the repo root (not under src/geofrea/) — imported
here the same way pytest already resolves it for collection.

UnwiredPhasesError (and the guard that raised it) was removed
2026-08-25 — see docs/DECISIONS.md same date, "data_acquisition
activation" for why: real wiring makes the guard's original
justification ("audit would silently run against nothing") no longer
true. These tests replace the old
test_build_phase_specs_raises_when_both_unwired_phases_enabled with
tests that confirm the real wiring itself: _build_audit_inputs() reads
context.prior_results correctly, and _audit_run() produces an
AuditResult that reflects data_acquisition's real output end-to-end.
"""

from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

import main
from geofrea.core.config_loader import load_audit_config, load_parameters
from geofrea.core.orchestrator import (
    CountryParamsRequiredError,
    Orchestrator,
    PhaseContext,
    PhaseResult,
    PhaseSpec,
)
from geofrea.core.schemas import ResolutionsConfig
from geofrea.data_acquisition.schemas import AcquiredLayer, AcquisitionResult, AcquisitionSummary
from geofrea.data_quality_audit.schemas import AuditConfig, AuditInputs, AuditResult
from geofrea.grid_alignment.adapter import GridAlignmentRequiresBordersError
from geofrea.grid_alignment.schemas import GridAlignmentResult

REPO_ROOT = Path(__file__).resolve().parents[2]
PARAMETERS_JSON = REPO_ROOT / "config" / "parameters.json"
AUDIT_YAML = REPO_ROOT / "config" / "audit.yaml"


def _country_params(country_code: str = "PRT"):
    return load_parameters(PARAMETERS_JSON).countries[country_code]


def _criteria():
    return load_parameters(PARAMETERS_JSON).criteria


def _audit_config() -> AuditConfig:
    return load_audit_config(AUDIT_YAML)


def _context(tmp_path: Path, prior_results: dict, country_code: str = "PRT") -> PhaseContext:
    return PhaseContext(
        country_code=country_code,
        country_params=_country_params(country_code),
        outputs_dir=tmp_path,
        prior_results=prior_results,
    )


def _acquisition_summary(n: int) -> AcquisitionSummary:
    return AcquisitionSummary(
        layers_total=n,
        layers_fetched_provenance=n,
        layers_local_only_provenance=0,
        layers_requiring_auth=0,
        layers_resolved=n,
    )


def _acquisition_phase_result(layers: list[AcquiredLayer]) -> PhaseResult[AcquisitionResult]:
    output = AcquisitionResult(
        country_code="PRT",
        timestamp="2026-08-25T00:00:00+00:00",
        layers=layers,
        summary=_acquisition_summary(len(layers)),
    )
    return PhaseResult(
        phase="data_acquisition",
        status="success",
        output=output,
        error=None,
        started_at="2026-08-25T00:00:00+00:00",
        finished_at="2026-08-25T00:00:01+00:00",
    )


@pytest.mark.unit
def test_build_phase_specs_returns_all_phases_in_order():
    specs = main._build_phase_specs(ResolutionsConfig(), _criteria(), _audit_config())
    assert [spec.name for spec in specs] == [
        "data_acquisition",
        "data_quality_audit",
        "grid_alignment",
        "suitability_criteria",
    ]


@pytest.mark.unit
def test_build_audit_inputs_falls_back_to_empty_when_acquisition_did_not_run(tmp_path):
    inputs = main._build_audit_inputs(_context(tmp_path, prior_results={}))
    assert inputs == AuditInputs()


@pytest.mark.unit
def test_build_audit_inputs_falls_back_to_empty_when_acquisition_output_is_none(tmp_path):
    failed = PhaseResult(
        phase="data_acquisition",
        status="failed",
        output=None,
        error="boom",
        started_at="2026-08-25T00:00:00+00:00",
        finished_at="2026-08-25T00:00:01+00:00",
    )
    inputs = main._build_audit_inputs(_context(tmp_path, prior_results={"data_acquisition": failed}))
    assert inputs == AuditInputs()


@pytest.mark.unit
def test_build_audit_inputs_adapts_real_acquisition_output(tmp_path):
    elevation_path = Path("/fake/elevation.tif")
    prior_results = {
        "data_acquisition": _acquisition_phase_result(
            [
                AcquiredLayer(
                    layer_name="elevation",
                    provenance="fetched",
                    auth_required=False,
                    path=elevation_path,
                )
            ]
        )
    }

    inputs = main._build_audit_inputs(_context(tmp_path, prior_results=prior_results))

    assert inputs.elevation_path == elevation_path


@pytest.mark.unit
def test_audit_run_reflects_data_acquisition_output_end_to_end(tmp_path):
    # This is the exact scenario UnwiredPhasesError used to block: both
    # phases "enabled" (here, simulated by data_acquisition already
    # having a successful PhaseResult in prior_results) and audit
    # actually consuming it. A real boundary file on disk proves the
    # path travels all the way from AcquiredLayer through
    # acquisition_result_to_audit_inputs() into inspect_vector_layer()
    # inside run_audit_phase() — not just that the adapter is called.
    mainland = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    boundary_path = tmp_path / "borders.geojson"
    gpd.GeoDataFrame(geometry=[mainland], crs="EPSG:4326").to_file(boundary_path, driver="GeoJSON")

    prior_results = {
        "data_acquisition": _acquisition_phase_result(
            [
                AcquiredLayer(
                    layer_name="borders",
                    provenance="fetched",
                    auth_required=False,
                    path=boundary_path,
                )
            ]
        )
    }

    result = main._audit_run(_context(tmp_path, prior_results=prior_results), _audit_config())

    assert result.vectors["borders"].found is True
    assert result.vectors["borders"].n_features == 1
    # Untouched layers correctly surface as missing, not as an error —
    # this is the audit doing its job on a genuinely partial
    # acquisition, not a sign the wiring is broken.
    assert result.rasters["elevation"].error == "File not found"


@pytest.mark.unit
def test_audit_run_with_no_prior_acquisition_matches_standalone_behavior(tmp_path):
    result = main._audit_run(_context(tmp_path, prior_results={}), _audit_config())
    assert result.vectors["borders"].found is False
    assert result.rasters["elevation"].error == "File not found"


# ─── grid_alignment wiring (2026-09-08, see DECISIONS.md same date) ───
#
# test_build_grid_alignment_inputs_raises_when_acquisition_did_not_run
# and ..._raises_when_acquisition_output_is_none were REMOVED 2026-09-21
# (see docs/phases/core.md D-core-001): _build_grid_alignment_inputs()
# no longer guards with a RuntimeError — grid_alignment's PhaseSpec now
# declares requires={"layer_registry"}, produced only by
# data_acquisition, so Orchestrator.run()'s graph validation and
# dependency-skip logic already guarantee data_acquisition succeeded
# before this closure is ever called. The scenario these tests exercised
# (calling the closure directly with no/failed data_acquisition in
# prior_results) is no longer a case the function itself defends
# against; it is now a precondition enforced one level up, by the DAG.


@pytest.mark.unit
def test_build_grid_alignment_inputs_raises_when_borders_missing_from_real_output(tmp_path):
    # data_acquisition DID run, but never resolved a borders layer —
    # the adapter's own GridAlignmentRequiresBordersError, reached
    # through main.py's real wiring, not just unit-tested in isolation.
    prior_results = {
        "data_acquisition": _acquisition_phase_result(
            [
                AcquiredLayer(
                    layer_name="elevation",
                    provenance="fetched",
                    auth_required=False,
                    path=Path("/fake/elevation.tif"),
                )
            ]
        )
    }
    with pytest.raises(GridAlignmentRequiresBordersError):
        main._build_grid_alignment_inputs(_context(tmp_path, prior_results=prior_results), ResolutionsConfig())


@pytest.mark.unit
def test_build_grid_alignment_inputs_adapts_real_acquisition_output(tmp_path):
    mainland = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    boundary_path = tmp_path / "borders.geojson"
    gpd.GeoDataFrame(geometry=[mainland], crs="EPSG:4326").to_file(boundary_path, driver="GeoJSON")

    prior_results = {
        "data_acquisition": _acquisition_phase_result(
            [
                AcquiredLayer(
                    layer_name="borders", provenance="fetched", auth_required=False, path=boundary_path
                )
            ]
        )
    }

    inputs = main._build_grid_alignment_inputs(
        _context(tmp_path, prior_results=prior_results), ResolutionsConfig()
    )

    assert len(inputs.country_gdf) == 1


@pytest.mark.unit
def test_grid_alignment_run_produces_result_from_borders_only(tmp_path):
    mainland = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    boundary_path = tmp_path / "borders.geojson"
    gpd.GeoDataFrame(geometry=[mainland], crs="EPSG:4326").to_file(boundary_path, driver="GeoJSON")

    prior_results = {
        "data_acquisition": _acquisition_phase_result(
            [
                AcquiredLayer(
                    layer_name="borders", provenance="fetched", auth_required=False, path=boundary_path
                )
            ]
        )
    }

    specs = main._build_phase_specs(ResolutionsConfig(), _criteria(), _audit_config())
    grid_alignment_run = next(s.run for s in specs if s.name == "grid_alignment")
    result = grid_alignment_run(_context(tmp_path, prior_results=prior_results))

    assert isinstance(result, GridAlignmentResult)
    assert result.country_code == "PRT"
    assert result.elevation is None
    assert result.grid_metadata.n_valid_pixels > 0


@pytest.mark.unit
def test_orchestrator_runs_grid_alignment_with_data_quality_audit_not_targeted(tmp_path):
    # The point of this test: prove the independence Passo 1 designed
    # for actually holds through the REAL Orchestrator + main.py
    # closures, not just "grid_alignment's adapter doesn't import
    # AuditResult" in isolation. data_acquisition uses a stub run
    # function (no real fetch/network — out of scope for a unit test);
    # data_quality_audit and grid_alignment use main.py's REAL closures.
    # data_quality_audit is registered but not in target_phases and
    # nothing requires its output, so the DAG never pulls it in.
    mainland = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    boundary_path = tmp_path / "country" / "borders.geojson"
    boundary_path.parent.mkdir(parents=True)
    gpd.GeoDataFrame(geometry=[mainland], crs="EPSG:4326").to_file(boundary_path, driver="GeoJSON")

    def _stub_acquisition_run(context):
        result = _acquisition_phase_result(
            [
                AcquiredLayer(
                    layer_name="borders", provenance="fetched", auth_required=False, path=boundary_path
                )
            ]
        ).output
        context.register_artifact("layer_registry", boundary_path, "1.0")
        return result

    outputs_dir = tmp_path / "outputs"
    orchestrator = Orchestrator(
        outputs_dir=outputs_dir,
        country_code="PRT",
        country_params=_country_params("PRT"),
        target_phases=["grid_alignment"],
        rerun_phases=[],
        run_id="test-run-id",
        dirty=False,
    )

    real_grid_alignment_run = next(
        s.run for s in main._build_phase_specs(ResolutionsConfig(), _criteria(), _audit_config()) if s.name == "grid_alignment"
    )
    specs = [
        PhaseSpec(
            name="data_acquisition",
            output_model=AcquisitionResult,
            run=_stub_acquisition_run,
            requires=frozenset(),
            produces=frozenset({"layer_registry"}),
        ),
        PhaseSpec(
            name="data_quality_audit",
            output_model=AuditResult,
            run=main._audit_run,
            requires=frozenset({"layer_registry"}),
            produces=frozenset({"audit_report"}),
        ),
        PhaseSpec(
            name="grid_alignment",
            output_model=GridAlignmentResult,
            run=real_grid_alignment_run,
            requires=frozenset({"layer_registry"}),
            produces=frozenset({"aligned_rasters"}),
        ),
    ]

    results = orchestrator.run(specs)

    assert list(results.keys()) == ["data_acquisition", "grid_alignment"]
    assert "data_quality_audit" not in results  # not targeted, nothing requires it: never attempted
    assert results["grid_alignment"].status == "success"
    assert results["grid_alignment"].output.grid_metadata.n_valid_pixels > 0


# ─── run_geofrea exit-code contract (2026-09-21, see docs/phases/core.md) ───
#
# main.py must exit non-zero when any target phase ends "failed" or
# "skipped_upstream_failed" — run_geofrea() is what main() derives its
# return code from (main() itself is a thin loop over run_geofrea() +
# `all_ok`), so these test run_geofrea() directly with a stubbed
# _build_phase_specs() rather than re-deriving the whole real pipeline.


@pytest.mark.unit
def test_run_geofrea_returns_false_when_a_target_phase_fails(tmp_path, monkeypatch):
    def _failing_specs(resolutions, criteria, audit_config):
        def run(context):
            raise ValueError("boom")

        return [
            PhaseSpec(
                name="data_acquisition",
                output_model=AcquisitionResult,
                run=run,
                requires=frozenset(),
                produces=frozenset(),
            )
        ]

    monkeypatch.setattr(main, "_build_phase_specs", _failing_specs)

    ok = main.run_geofrea("PRT", ["data_acquisition"], [], ResolutionsConfig(), _audit_config(), "run-id", False)

    assert ok is False


@pytest.mark.unit
def test_run_geofrea_returns_false_when_a_target_phase_is_skipped_upstream_failed(tmp_path, monkeypatch):
    def _specs(resolutions, criteria, audit_config):
        def failing_run(context):
            raise ValueError("boom")

        def dependent_run(context):
            return _acquisition_phase_result([]).output

        return [
            PhaseSpec(
                name="a",
                output_model=AcquisitionResult,
                run=failing_run,
                requires=frozenset(),
                produces=frozenset({"a_out"}),
            ),
            PhaseSpec(
                name="b",
                output_model=AcquisitionResult,
                run=dependent_run,
                requires=frozenset({"a_out"}),
                produces=frozenset(),
            ),
        ]

    monkeypatch.setattr(main, "_build_phase_specs", _specs)

    ok = main.run_geofrea("PRT", ["b"], [], ResolutionsConfig(), _audit_config(), "run-id", False)

    assert ok is False


@pytest.mark.unit
def test_run_geofrea_returns_true_when_every_target_phase_succeeds(tmp_path, monkeypatch):
    def _specs(resolutions, criteria, audit_config):
        def run(context):
            return _acquisition_phase_result([]).output

        return [
            PhaseSpec(
                name="data_acquisition",
                output_model=AcquisitionResult,
                run=run,
                requires=frozenset(),
                produces=frozenset(),
            )
        ]

    monkeypatch.setattr(main, "_build_phase_specs", _specs)

    ok = main.run_geofrea("PRT", ["data_acquisition"], [], ResolutionsConfig(), _audit_config(), "run-id", False)

    assert ok is True


# ─── Gating moved to point of use (F2-2 follow-up, see docs/phases/core.md) ───
#
# A country present in countries.yaml but absent from parameters.json
# (IND, at the time this was written — see config/countries.yaml and
# OQ-012) must still be able to run phases that read no CountryParams
# field. Only a phase that actually reads one (data_quality_audit's
# slope_threshold_deg, suitability_criteria's criteria) fails loud,
# naming the country and the field, via
# PhaseContext.require_country_params().


@pytest.mark.unit
def test_run_geofrea_succeeds_for_country_absent_from_parameters_json(tmp_path, monkeypatch):
    def _specs(resolutions, criteria, audit_config):
        def run(context):
            # Reads country_code only, never country_params — same shape
            # as the real data_acquisition PhaseSpec.
            assert context.country_params is None
            return _acquisition_phase_result([]).output

        return [
            PhaseSpec(
                name="data_acquisition",
                output_model=AcquisitionResult,
                run=run,
                requires=frozenset(),
                produces=frozenset(),
            )
        ]

    monkeypatch.setattr(main, "_build_phase_specs", _specs)
    monkeypatch.setattr(main, "outputs_dir", lambda: tmp_path)

    # ZZZ (not a real ISO code): must be present in countries.yaml-style
    # test fixtures but absent from the real config/parameters.json —
    # IND no longer qualifies as of task F1-3 item B (now has a full
    # countries.IND entry, see docs/phases/F1b_data_quality_audit.md
    # D-F1b-007).
    ok = main.run_geofrea("ZZZ", ["data_acquisition"], [], ResolutionsConfig(), _audit_config(), "run-id", False)

    assert ok is True


@pytest.mark.unit
def test_audit_run_fails_loud_naming_country_and_field_when_params_absent(tmp_path):
    context = PhaseContext(
        country_code="IND",
        country_params=None,
        outputs_dir=tmp_path,
        prior_results={},
    )

    with pytest.raises(CountryParamsRequiredError) as exc_info:
        main._audit_run(context, _audit_config())

    assert exc_info.value.country_code == "IND"
    assert exc_info.value.field == "technologies.solar"
    assert "IND" in str(exc_info.value)
    assert "technologies.solar" in str(exc_info.value)


@pytest.mark.unit
def test_orchestrator_records_audit_as_failed_not_raised_when_params_absent(tmp_path):
    # A- 09: an exception from spec.run() becomes a "failed" PhaseResult,
    # never propagates out of Orchestrator.run() — same contract as any
    # other phase failure, confirmed here for the new error specifically.
    def stub_acquisition_run(context):
        context.register_artifact("layer_registry", tmp_path / "dummy.txt", "1.0")
        (tmp_path / "dummy.txt").write_text("x", encoding="utf-8")
        return _acquisition_phase_result([]).output

    specs = [
        PhaseSpec(
            name="data_acquisition",
            output_model=AcquisitionResult,
            run=stub_acquisition_run,
            requires=frozenset(),
            produces=frozenset({"layer_registry"}),
        ),
        PhaseSpec(
            name="data_quality_audit",
            output_model=AuditResult,
            run=lambda context: main._audit_run(context, _audit_config()),
            requires=frozenset({"layer_registry"}),
            produces=frozenset({"audit_report"}),
        ),
    ]

    orchestrator = Orchestrator(
        outputs_dir=tmp_path / "outputs",
        country_code="IND",
        country_params=None,
        target_phases=["data_quality_audit"],
        rerun_phases=[],
        run_id="test-run-id",
        dirty=False,
    )

    results = orchestrator.run(specs)

    assert results["data_acquisition"].status == "success"
    assert results["data_quality_audit"].status == "failed"
    assert "IND" in results["data_quality_audit"].error
    assert "technologies.solar" in results["data_quality_audit"].error


@pytest.mark.unit
def test_build_suitability_criteria_inputs_fails_loud_when_params_absent(tmp_path):
    # require_country_params("criteria") is only reached after
    # grid_alignment/data_acquisition's prior_results are read (see
    # main.py::_build_suitability_criteria_inputs) — neither is
    # inspected before the CountryParamsRequiredError, so dummy
    # PhaseResults with placeholder output are enough here; the real
    # adapter wiring is exercised end-to-end by the grid_alignment tests
    # above.
    dummy_result = PhaseResult(
        phase="dummy",
        status="success",
        output=None,
        error=None,
        started_at="2026-09-23T00:00:00+00:00",
        finished_at="2026-09-23T00:00:01+00:00",
    )
    context = PhaseContext(
        country_code="IND",
        country_params=None,
        outputs_dir=tmp_path,
        prior_results={"grid_alignment": dummy_result, "data_acquisition": dummy_result},
    )

    with pytest.raises(CountryParamsRequiredError) as exc_info:
        main._build_suitability_criteria_inputs(context, _criteria())

    assert exc_info.value.country_code == "IND"
    assert exc_info.value.field == "criteria"


@pytest.mark.unit
def test_run_geofrea_still_succeeds_for_bra_and_prt(monkeypatch, tmp_path):
    # BRA/PRT both have real parameters.json entries — confirm the
    # gating change doesn't alter their behavior.
    monkeypatch.setattr(main, "outputs_dir", lambda: tmp_path)
    for country in ("BRA", "PRT"):

        def _specs(resolutions, criteria, audit_config):
            def run(context):
                assert context.country_params is not None
                return _acquisition_phase_result([]).output

            return [
                PhaseSpec(
                    name="data_acquisition",
                    output_model=AcquisitionResult,
                    run=run,
                    requires=frozenset(),
                    produces=frozenset(),
                )
            ]

        monkeypatch.setattr(main, "_build_phase_specs", _specs)

        ok = main.run_geofrea(country, ["data_acquisition"], [], ResolutionsConfig(), _audit_config(), "run-id", False)

        assert ok is True
