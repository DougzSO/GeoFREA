"""Unit tests for geofrea.grid_alignment.adapter."""

from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from geofrea.core.schemas import ResolutionsConfig
from geofrea.data_acquisition.schemas import AcquiredLayer, AcquisitionResult, AcquisitionSummary
from geofrea.grid_alignment.adapter import (
    GridAlignmentRequiresBordersError,
    acquisition_result_to_grid_alignment_inputs,
)
from geofrea.grid_alignment.schemas import GridAlignmentInputs


def _summary(n: int) -> AcquisitionSummary:
    return AcquisitionSummary(
        layers_total=n,
        layers_fetched_provenance=0,
        layers_local_only_provenance=n,
        layers_requiring_auth=0,
        layers_resolved=n,
    )


def _result(layers: list[AcquiredLayer]) -> AcquisitionResult:
    return AcquisitionResult(
        country_code="PRT",
        timestamp="2026-09-08T00:00:00+00:00",
        layers=layers,
        summary=_summary(len(layers)),
    )


def _layer(name: str, path: Path | None = None, paths: list[Path] | None = None) -> AcquiredLayer:
    kwargs: dict = {"layer_name": name, "provenance": "local_only", "auth_required": False}
    if paths is not None:
        kwargs["paths"] = paths
    else:
        kwargs["path"] = path
    return AcquiredLayer(**kwargs)


def _boundary_path(tmp_path: Path) -> Path:
    mainland = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    islet = Polygon([(10, 10), (10.1, 10), (10.1, 10.1), (10, 10.1)])
    path = tmp_path / "borders.geojson"
    gpd.GeoDataFrame(geometry=[mainland, islet], crs="EPSG:4326").to_file(path, driver="GeoJSON")
    return path


@pytest.mark.unit
def test_adapter_raises_when_borders_layer_is_absent(tmp_path):
    result = _result([_layer("elevation", tmp_path / "elev.tif")])

    with pytest.raises(GridAlignmentRequiresBordersError, match="PRT"):
        acquisition_result_to_grid_alignment_inputs(
            result, ResolutionsConfig(suitability=0.01), 100.0
        )


@pytest.mark.unit
def test_adapter_raises_when_borders_layer_path_is_none(tmp_path):
    result = _result([_layer("borders", path=None)])

    with pytest.raises(GridAlignmentRequiresBordersError):
        acquisition_result_to_grid_alignment_inputs(
            result, ResolutionsConfig(suitability=0.01), 100.0
        )


@pytest.mark.unit
def test_adapter_with_only_borders_produces_mainland_filtered_country_gdf(tmp_path):
    boundary_path = _boundary_path(tmp_path)
    result = _result([_layer("borders", boundary_path)])

    inputs = acquisition_result_to_grid_alignment_inputs(
        result, ResolutionsConfig(suitability=0.01), 100.0
    )

    assert isinstance(inputs, GridAlignmentInputs)
    assert len(inputs.country_gdf) == 1  # mainland only, islet dropped
    assert inputs.elevation_path is None
    assert inputs.roads_source is None
    assert inputs.grid_source is None


@pytest.mark.unit
def test_adapter_maps_source_path_fields(tmp_path):
    boundary_path = _boundary_path(tmp_path)
    elevation_path = Path("/fake/elevation.tif")
    roads_path = Path("/fake/roads_grip4.shp")
    grid_path = Path("/fake/grid_osm.geojson")

    result = _result(
        [
            _layer("borders", boundary_path),
            _layer("elevation", elevation_path),
            _layer("roads", roads_path),
            _layer("grid", grid_path),
        ]
    )

    inputs = acquisition_result_to_grid_alignment_inputs(
        result, ResolutionsConfig(suitability=0.01), 100.0
    )

    assert inputs.elevation_path == elevation_path
    # Deliberately renamed fields (see schemas.py/adapter.py module
    # docstrings) — roads/grid map to *_source, not *_path.
    assert inputs.roads_source == roads_path
    assert inputs.grid_source == grid_path


@pytest.mark.unit
def test_adapter_does_not_map_protected_admin1_or_borders_passthrough(tmp_path):
    boundary_path = _boundary_path(tmp_path)
    result = _result(
        [
            _layer("borders", boundary_path),
            _layer("protected", Path("/fake/wdpa.shp")),
            _layer("admin1", Path("/fake/admin1.shp")),
        ]
    )

    inputs = acquisition_result_to_grid_alignment_inputs(
        result, ResolutionsConfig(suitability=0.01), 100.0
    )

    # GridAlignmentInputs has no protected_path/admin1_path/borders_path
    # fields at all — confirmed by extra="forbid" already covered in
    # test_grid_alignment_schemas.py; here we just confirm the adapter
    # doesn't try to smuggle them in under some other name.
    assert not hasattr(inputs, "protected_path")
    assert not hasattr(inputs, "admin1_path")
    assert not hasattr(inputs, "borders_path")


@pytest.mark.unit
def test_adapter_maps_every_gwa_product_and_height_to_its_own_wind_layer(tmp_path):
    boundary_path = _boundary_path(tmp_path)
    wind_100 = Path("/fake/wind_100m.tif")
    weibull_a_150 = Path("/fake/weibull_a_150m.tif")
    result = _result(
        [
            _layer("borders", boundary_path),
            _layer("wind", wind_100),  # wind_speed at 100 m keeps the bare registry name "wind"
            _layer("weibull_a_150m", weibull_a_150),
        ]
    )

    inputs = acquisition_result_to_grid_alignment_inputs(
        result, ResolutionsConfig(suitability=0.01), 100.0
    )

    assert inputs.wind_layers == {"wind_speed_100m": wind_100, "weibull_a_150m": weibull_a_150}


@pytest.mark.unit
def test_adapter_maps_land_cover_tiles_list(tmp_path):
    boundary_path = _boundary_path(tmp_path)
    tiles = [Path("/fake/tile1.tif"), Path("/fake/tile2.tif")]
    result = _result([_layer("borders", boundary_path), _layer("land_cover", paths=tiles)])

    inputs = acquisition_result_to_grid_alignment_inputs(
        result, ResolutionsConfig(suitability=0.01), 100.0
    )

    assert inputs.land_cover_tiles == tiles


# ─── resolutions threading (2026-09-09, grid_alignment Passo 4 item 3) ───


@pytest.mark.unit
def test_adapter_threads_fixed_resolution_from_resolutions_config(tmp_path):
    boundary_path = _boundary_path(tmp_path)
    result = _result([_layer("borders", boundary_path)])

    inputs = acquisition_result_to_grid_alignment_inputs(
        result, ResolutionsConfig(suitability=0.02), 100.0
    )

    assert inputs.resolution_deg == 0.02
