"""Unit tests for geofrea.suitability_criteria.adapter."""

import copy

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from geofrea.core.schemas import CountryCriteriaParams, CriteriaParams
from geofrea.data_acquisition.schemas import AcquiredLayer, AcquisitionResult, AcquisitionSummary
from geofrea.grid_alignment.schemas import GridAlignmentResult, GridMetadata
from geofrea.suitability_criteria.adapter import (
    SuitabilityCriteriaRequiresBordersError,
    build_suitability_criteria_inputs,
)
from tests.unit.test_schemas import VALID_COUNTRY_CRITERIA, VALID_CRITERIA


def _criteria() -> CriteriaParams:
    return CriteriaParams.model_validate(copy.deepcopy(VALID_CRITERIA))


def _country_criteria() -> CountryCriteriaParams:
    return CountryCriteriaParams.model_validate(copy.deepcopy(VALID_COUNTRY_CRITERIA))


def _grid_result(tmp_path) -> GridAlignmentResult:
    solar = tmp_path / "PRT_solar_aligned.tif"
    solar.write_bytes(b"")  # path presence only; adapter doesn't open it
    return GridAlignmentResult(
        country_code="PRT",
        timestamp="2026-09-10T00:00:00+00:00",
        grid_metadata=GridMetadata(
            crs="EPSG:4326", resolution_deg=0.01, width=333, height=518,
            transform=(0.01, 0.0, -9.5, 0.0, -0.01, 42.15), n_valid_pixels=93149,
        ),
        solar=solar,
        roads=tmp_path / "PRT_roads_aligned.tif",
    )


def _acquisition(tmp_path, *, with_borders=True, with_protected=True) -> AcquisitionResult:
    boundary = tmp_path / "borders.geojson"
    gpd.GeoDataFrame(
        {"geometry": [Polygon([(-9, 37), (-6, 37), (-6, 42), (-9, 42)])]}, crs="EPSG:4326"
    ).to_file(boundary, driver="GeoJSON")
    layers = []
    if with_borders:
        layers.append(
            AcquiredLayer(layer_name="borders", provenance="fetched", auth_required=False, path=boundary)
        )
    if with_protected:
        layers.append(
            AcquiredLayer(
                layer_name="protected", provenance="local_only", auth_required=True,
                path=tmp_path / "wdpa.shp",
            )
        )
    return AcquisitionResult(
        country_code="PRT",
        timestamp="2026-09-10T00:00:00+00:00",
        layers=layers,
        summary=AcquisitionSummary(
            layers_total=len(layers), layers_fetched_provenance=1,
            layers_local_only_provenance=len(layers) - 1, layers_requiring_auth=0,
            layers_resolved=len(layers),
        ),
    )


@pytest.mark.unit
def test_adapter_maps_aligned_rasters_and_wdpa(tmp_path):
    inputs = build_suitability_criteria_inputs(
        _grid_result(tmp_path), _acquisition(tmp_path), _criteria(), _country_criteria()
    )
    assert inputs.solar is not None and inputs.solar.name == "PRT_solar_aligned.tif"
    assert inputs.roads is not None
    assert inputs.elevation is None
    assert inputs.wdpa_path is not None and inputs.wdpa_path.name == "wdpa.shp"
    assert inputs.yield_by_land_cover == {10: 8.0, 20: 3.0, 30: 5.0, 40: 6.0, 90: 0.0, 95: 0.0}
    assert inputs.terrain_slope_threshold_deg == 10.0
    assert inputs.grid_metadata.n_valid_pixels == 93149
    assert not inputs.mainland_gdf.empty


@pytest.mark.unit
def test_adapter_wdpa_none_when_protected_layer_absent(tmp_path):
    inputs = build_suitability_criteria_inputs(
        _grid_result(tmp_path), _acquisition(tmp_path, with_protected=False), _criteria(), _country_criteria()
    )
    assert inputs.wdpa_path is None


@pytest.mark.unit
def test_adapter_raises_when_borders_missing(tmp_path):
    with pytest.raises(SuitabilityCriteriaRequiresBordersError):
        build_suitability_criteria_inputs(
            _grid_result(tmp_path), _acquisition(tmp_path, with_borders=False), _criteria(), _country_criteria()
        )
