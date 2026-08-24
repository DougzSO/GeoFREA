"""Unit tests for geofrea.data_acquisition.schemas."""

import copy

import pytest
from pydantic import ValidationError

from geofrea.data_acquisition.schemas import (
    MULTI_FILE_LAYER_NAMES,
    AcquiredLayer,
    AcquisitionResult,
    AcquisitionSummary,
    CrsMetadata,
)

VALID_LAYER = {
    "layer_name": "elevation",
    "provenance": "fetched",
    "auth_required": False,
    "source_name": "Copernicus DEM 30m (public S3)",
    "country_code": "PRT",
    "path": None,
    "crs_metadata": None,
}

VALID_SUMMARY = {
    "layers_total": 1,
    "layers_fetched_provenance": 1,
    "layers_local_only_provenance": 0,
    "layers_requiring_auth": 0,
    "layers_resolved": 0,
}

VALID_RESULT = {
    "country_code": "PRT",
    "timestamp": "2026-08-24T00:00:00+00:00",
    "layers": [VALID_LAYER],
    "summary": VALID_SUMMARY,
}


@pytest.mark.unit
def test_crs_metadata_all_fields_optional():
    result = CrsMetadata.model_validate({})
    assert result.native_crs is None
    assert result.target_crs is None
    assert result.reprojected is None


@pytest.mark.unit
def test_crs_metadata_rejects_unexpected_field():
    with pytest.raises(ValidationError):
        CrsMetadata.model_validate({"unexpected_key": "typo"})


@pytest.mark.unit
def test_acquired_layer_accepts_valid_payload():
    result = AcquiredLayer.model_validate(VALID_LAYER)
    assert result.layer_name == "elevation"
    assert result.provenance == "fetched"
    assert result.path is None


@pytest.mark.unit
@pytest.mark.parametrize("provenance", ["fetched", "local_only"])
def test_acquired_layer_accepts_both_provenance_values(provenance):
    data = {**VALID_LAYER, "provenance": provenance}
    result = AcquiredLayer.model_validate(data)
    assert result.provenance == provenance


@pytest.mark.unit
def test_acquired_layer_rejects_invalid_provenance():
    data = {**VALID_LAYER, "provenance": "invented_value"}
    with pytest.raises(ValidationError):
        AcquiredLayer.model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("field", ["layer_name", "provenance", "auth_required"])
def test_acquired_layer_missing_required_field_raises(field):
    data = dict(VALID_LAYER)
    del data[field]
    with pytest.raises(ValidationError):
        AcquiredLayer.model_validate(data)


@pytest.mark.unit
def test_acquired_layer_rejects_unexpected_field():
    data = {**VALID_LAYER, "unexpected_key": "typo"}
    with pytest.raises(ValidationError):
        AcquiredLayer.model_validate(data)


@pytest.mark.unit
def test_acquired_layer_optional_fields_default_to_none():
    minimal = {"layer_name": "solar", "provenance": "local_only", "auth_required": False}
    result = AcquiredLayer.model_validate(minimal)
    assert result.source_name is None
    assert result.country_code is None
    assert result.path is None
    assert result.crs_metadata is None


@pytest.mark.unit
def test_multi_file_layer_names_contains_only_land_cover():
    # The set itself, not just AcquiredLayer's use of it — a change
    # here silently changes which layers are allowed to use `paths`.
    assert MULTI_FILE_LAYER_NAMES == frozenset({"land_cover"})


@pytest.mark.unit
def test_acquired_layer_land_cover_with_path_set_is_rejected():
    data = {**VALID_LAYER, "layer_name": "land_cover", "path": "/fake/tile.tif"}
    with pytest.raises(ValidationError, match="land_cover"):
        AcquiredLayer.model_validate(data)


@pytest.mark.unit
def test_acquired_layer_land_cover_with_paths_and_no_path_is_accepted():
    data = {**VALID_LAYER, "layer_name": "land_cover", "path": None, "paths": ["/fake/tile.tif"]}
    result = AcquiredLayer.model_validate(data)
    assert result.path is None
    assert len(result.paths) == 1


@pytest.mark.unit
def test_acquired_layer_single_file_layer_with_paths_set_is_rejected():
    data = {**VALID_LAYER, "layer_name": "elevation", "paths": ["/fake/extra.tif"]}
    with pytest.raises(ValidationError, match="elevation"):
        AcquiredLayer.model_validate(data)


@pytest.mark.unit
def test_acquired_layer_single_file_layer_with_path_set_is_accepted():
    data = {**VALID_LAYER, "layer_name": "elevation", "path": "/fake/elevation.tif"}
    result = AcquiredLayer.model_validate(data)
    assert result.paths == []


@pytest.mark.unit
def test_acquisition_summary_accepts_valid_payload():
    result = AcquisitionSummary.model_validate(VALID_SUMMARY)
    assert result.layers_total == 1


@pytest.mark.unit
def test_acquisition_summary_rejects_unexpected_field():
    data = {**VALID_SUMMARY, "unexpected_key": "typo"}
    with pytest.raises(ValidationError):
        AcquisitionSummary.model_validate(data)


@pytest.mark.unit
def test_acquisition_result_accepts_valid_payload():
    result = AcquisitionResult.model_validate(VALID_RESULT)
    assert result.country_code == "PRT"
    assert len(result.layers) == 1


@pytest.mark.unit
@pytest.mark.parametrize("field", ["country_code", "timestamp", "layers", "summary"])
def test_acquisition_result_missing_required_field_raises(field):
    data = copy.deepcopy(VALID_RESULT)
    del data[field]
    with pytest.raises(ValidationError):
        AcquisitionResult.model_validate(data)


@pytest.mark.unit
def test_acquisition_result_rejects_unexpected_field():
    data = {**copy.deepcopy(VALID_RESULT), "unexpected_key": "typo"}
    with pytest.raises(ValidationError):
        AcquisitionResult.model_validate(data)
