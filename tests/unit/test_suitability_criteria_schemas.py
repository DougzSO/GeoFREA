"""Unit tests for geofrea.suitability_criteria.schemas (Fase 2b contract).

Same per-field / per-constraint pattern as test_schemas.py. The
GridMetadata payload and a minimal CriteriaParams payload are reused
from the grid_alignment and core schema test modules' conventions.
"""

import copy
from pathlib import Path

import geopandas as gpd
import pytest
from pydantic import ValidationError
from shapely.geometry import Polygon

from geofrea.suitability_criteria.schemas import (
    CANONICAL_CRITERIA,
    REQUIRED_ALIGNED_LAYERS,
    CriterionLayer,
    SuitabilityCriteriaInputs,
    SuitabilityCriteriaResult,
    SuitabilityCriteriaSummary,
)
from tests.unit.test_schemas import VALID_CRITERIA

VALID_GRID_METADATA = {
    "crs": "EPSG:4326",
    "resolution_deg": 0.01,
    "width": 333,
    "height": 518,
    "transform": [0.01, 0.0, -9.5, 0.0, -0.01, 42.15],
    "n_valid_pixels": 93149,
}


def _mainland() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"geometry": [Polygon([(-9, 37), (-6, 37), (-6, 42), (-9, 42)])]}, crs="EPSG:4326"
    )


def _valid_inputs() -> dict:
    return {
        "elevation": Path("PRT_elevation_aligned.tif"),
        "slope": Path("PRT_slope_aligned.tif"),
        "solar": Path("PRT_solar_aligned.tif"),
        "land_cover": Path("PRT_land_cover_aligned.tif"),
        "grid_metadata": dict(VALID_GRID_METADATA),
        "criteria": copy.deepcopy(VALID_CRITERIA),
        "yield_by_land_cover": {10: 8.0, 30: 5.0},
        "terrain_slope_threshold_deg": 10.0,
        "mainland_gdf": _mainland(),
    }


def _valid_criterion_layer(name: str = "solar_resource") -> dict:
    return {
        "name": name,
        "tif_path": Path(f"tif/{name}.tif"),
        "figure_path": Path(f"figures/{name}.png"),
        "valid_pixels": 93149,
        "mean": 0.56,
        "std": 0.30,
        "p10": 0.10,
        "p50": 0.61,
        "p90": 0.94,
        "frac_ge_0_6": 0.51,
    }


def _valid_result() -> dict:
    layer = _valid_criterion_layer("road_suitability")
    return {
        "country_code": "PRT",
        "timestamp": "2026-09-10T00:00:00+00:00",
        "tif_dir": Path("outputs/PRT/suitability_criteria/tif"),
        "figure_dir": Path("outputs/PRT/suitability_criteria/figures"),
        "report_path": Path("outputs/PRT/suitability_criteria/reports/criteria_summary_PRT.txt"),
        "criteria": {"road_suitability": layer},
        "slope_degrees_tif": Path("tif/slope_degrees.tif"),
        "summary": {
            "n_criteria": 1,
            "missing_expected": [],
            "not_implemented": [c for c in CANONICAL_CRITERIA if c != "road_suitability"],
            "protected_source": "assumed_free",
            "protected_wdpa_repair": {
                "n_total": 0,
                "n_invalid": 0,
                "n_repaired": 0,
                "n_dropped_empty": 0,
                "invalid_reasons": {},
                "country_polygon_repaired": False,
            },
            "grid_metadata": dict(VALID_GRID_METADATA),
        },
    }


# ─── constants ─────────────────────────────────────────────────────────


@pytest.mark.unit
def test_canonical_criteria_has_13_entries_and_excludes_slope_degrees():
    assert len(CANONICAL_CRITERIA) == 13
    assert "slope_degrees" not in CANONICAL_CRITERIA
    assert REQUIRED_ALIGNED_LAYERS == ("elevation", "slope", "solar", "land_cover")


# ─── SuitabilityCriteriaInputs ────────────────────────────────────────


@pytest.mark.unit
def test_inputs_accept_valid_payload():
    result = SuitabilityCriteriaInputs.model_validate(_valid_inputs())
    assert result.criteria.road_max_dist_km.value == 15.0
    assert result.yield_by_land_cover[10] == 8.0
    assert result.wind is None
    assert result.wdpa_path is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "field",
    ["grid_metadata", "criteria", "yield_by_land_cover", "terrain_slope_threshold_deg", "mainland_gdf"],
)
def test_inputs_missing_required_field_raises(field):
    data = _valid_inputs()
    del data[field]
    with pytest.raises(ValidationError):
        SuitabilityCriteriaInputs.model_validate(data)


@pytest.mark.unit
def test_inputs_reject_unexpected_field():
    data = {**_valid_inputs(), "roads_source": Path("x")}
    with pytest.raises(ValidationError):
        SuitabilityCriteriaInputs.model_validate(data)


@pytest.mark.unit
def test_inputs_optional_layers_default_to_none():
    result = SuitabilityCriteriaInputs.model_validate(_valid_inputs())
    for layer in ("wind", "population", "roads", "grid", "lakes", "rivers", "plants"):
        assert getattr(result, layer) is None


# ─── CriterionLayer ───────────────────────────────────────────────────


@pytest.mark.unit
def test_criterion_layer_accepts_valid_payload():
    result = CriterionLayer.model_validate(_valid_criterion_layer())
    assert result.name == "solar_resource"
    assert result.figure_path is not None


@pytest.mark.unit
def test_criterion_layer_figure_path_optional():
    data = _valid_criterion_layer()
    del data["figure_path"]
    assert CriterionLayer.model_validate(data).figure_path is None


@pytest.mark.unit
def test_criterion_layer_rejects_non_canonical_name():
    with pytest.raises(ValidationError):
        CriterionLayer.model_validate(_valid_criterion_layer("slope_degrees"))


@pytest.mark.unit
@pytest.mark.parametrize(
    "field", ["name", "tif_path", "valid_pixels", "mean", "std", "p10", "p50", "p90", "frac_ge_0_6"]
)
def test_criterion_layer_missing_required_field_raises(field):
    data = _valid_criterion_layer()
    del data[field]
    with pytest.raises(ValidationError):
        CriterionLayer.model_validate(data)


# ─── SuitabilityCriteriaSummary ───────────────────────────────────────


@pytest.mark.unit
def test_summary_accepts_valid_payload():
    result = SuitabilityCriteriaSummary.model_validate(_valid_result()["summary"])
    assert result.protected_source == "assumed_free"
    assert result.n_criteria == 1


@pytest.mark.unit
def test_summary_rejects_unknown_protected_source():
    data = dict(_valid_result()["summary"])
    data["protected_source"] = "guessed"
    with pytest.raises(ValidationError):
        SuitabilityCriteriaSummary.model_validate(data)


# ─── SuitabilityCriteriaResult ────────────────────────────────────────


@pytest.mark.unit
def test_result_accepts_valid_payload():
    result = SuitabilityCriteriaResult.model_validate(_valid_result())
    assert result.country_code == "PRT"
    assert set(result.criteria) == {"road_suitability"}


@pytest.mark.unit
def test_result_rejects_summary_count_mismatch():
    data = _valid_result()
    data["summary"]["n_criteria"] = 5
    with pytest.raises(ValidationError):
        SuitabilityCriteriaResult.model_validate(data)


@pytest.mark.unit
def test_result_rejects_non_canonical_criterion_key():
    data = _valid_result()
    layer = _valid_criterion_layer("road_suitability")
    data["criteria"] = {"not_a_criterion": layer}
    with pytest.raises(ValidationError):
        SuitabilityCriteriaResult.model_validate(data)


@pytest.mark.unit
def test_result_rejects_key_name_mismatch():
    data = _valid_result()
    # key says solar_resource but the layer's own name is road_suitability
    data["criteria"] = {"solar_resource": _valid_criterion_layer("road_suitability")}
    data["summary"]["n_criteria"] = 1
    with pytest.raises(ValidationError):
        SuitabilityCriteriaResult.model_validate(data)


@pytest.mark.unit
def test_result_slope_degrees_tif_optional():
    data = _valid_result()
    del data["slope_degrees_tif"]
    assert SuitabilityCriteriaResult.model_validate(data).slope_degrees_tif is None


@pytest.mark.unit
def test_result_rejects_incomplete_bucket_partition():
    data = _valid_result()
    data["summary"]["not_implemented"] = data["summary"]["not_implemented"][:-1]  # drop one
    with pytest.raises(ValidationError, match="partition"):
        SuitabilityCriteriaResult.model_validate(data)


@pytest.mark.unit
def test_result_rejects_bucket_overlap():
    data = _valid_result()
    data["summary"]["missing_expected"] = ["terrain_score"]  # also in not_implemented
    with pytest.raises(ValidationError, match="overlap"):
        SuitabilityCriteriaResult.model_validate(data)
