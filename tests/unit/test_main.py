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
from geofrea.core.config_loader import load_parameters
from geofrea.core.orchestrator import PhaseContext, PhaseResult
from geofrea.data_acquisition.schemas import AcquiredLayer, AcquisitionResult, AcquisitionSummary
from geofrea.data_quality_audit.schemas import AuditInputs

REPO_ROOT = Path(__file__).resolve().parents[2]
PARAMETERS_JSON = REPO_ROOT / "config" / "parameters.json"


def _country_params(country_code: str = "PRT"):
    return load_parameters(PARAMETERS_JSON).countries[country_code]


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
def test_build_phase_specs_returns_both_phases_in_order():
    specs = main._build_phase_specs()
    assert [spec.name for spec in specs] == ["data_acquisition", "data_quality_audit"]


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

    result = main._audit_run(_context(tmp_path, prior_results=prior_results))

    assert result.vectors["borders"].found is True
    assert result.vectors["borders"].n_features == 1
    # Untouched layers correctly surface as missing, not as an error —
    # this is the audit doing its job on a genuinely partial
    # acquisition, not a sign the wiring is broken.
    assert result.rasters["elevation"].error == "File not found"


@pytest.mark.unit
def test_audit_run_with_no_prior_acquisition_matches_standalone_behavior(tmp_path):
    result = main._audit_run(_context(tmp_path, prior_results={}))
    assert result.vectors["borders"].found is False
    assert result.rasters["elevation"].error == "File not found"
