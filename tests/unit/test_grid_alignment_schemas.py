"""Unit tests for geofrea.grid_alignment.schemas."""

import geopandas as gpd
import pytest
from pydantic import ValidationError
from shapely.geometry import Polygon

from geofrea.grid_alignment.schemas import GridAlignmentInputs, GridAlignmentResult, GridMetadata

_COUNTRY_GDF = gpd.GeoDataFrame(
    geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])], crs="EPSG:4326"
)

_VALID_METADATA = {
    "crs": "EPSG:4326",
    "resolution_deg": 0.01,
    "width": 10,
    "height": 10,
    "transform": (0.01, 0.0, 0.0, 0.0, -0.01, 1.0),
    "n_valid_pixels": 50,
}


@pytest.mark.unit
def test_grid_alignment_inputs_requires_country_gdf():
    with pytest.raises(ValidationError):
        GridAlignmentInputs()


@pytest.mark.unit
def test_grid_alignment_inputs_accepts_country_gdf_only():
    inputs = GridAlignmentInputs(country_gdf=_COUNTRY_GDF)
    assert inputs.elevation_path is None
    assert inputs.roads_source is None
    assert inputs.grid_source is None
    assert inputs.wind_paths == []
    assert inputs.land_cover_tiles == []


@pytest.mark.unit
def test_grid_alignment_inputs_forbids_extra_fields():
    with pytest.raises(ValidationError):
        GridAlignmentInputs(country_gdf=_COUNTRY_GDF, roads_path="should_not_exist.shp")


@pytest.mark.unit
def test_grid_metadata_round_trips():
    meta = GridMetadata.model_validate(_VALID_METADATA)
    assert meta.width == 10
    assert meta.transform == (0.01, 0.0, 0.0, 0.0, -0.01, 1.0)


@pytest.mark.unit
def test_grid_alignment_result_all_layers_optional():
    result = GridAlignmentResult(
        country_code="PRT",
        timestamp="2026-09-08T00:00:00+00:00",
        grid_metadata=GridMetadata.model_validate(_VALID_METADATA),
    )
    assert result.elevation is None
    assert result.roads is None
    assert result.grid is None


@pytest.mark.unit
def test_grid_alignment_result_forbids_extra_fields():
    with pytest.raises(ValidationError):
        GridAlignmentResult(
            country_code="PRT",
            timestamp="2026-09-08T00:00:00+00:00",
            grid_metadata=GridMetadata.model_validate(_VALID_METADATA),
            verified=True,
        )
