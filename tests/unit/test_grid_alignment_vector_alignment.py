"""Unit tests for geofrea.grid_alignment.vector_alignment."""

from unittest.mock import patch

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from shapely.geometry import LineString, Point, Polygon

from geofrea.core.constants import NODATA_FLOAT, NODATA_UINT8
from geofrea.grid_alignment.reference_grid import build_reference_grid
from geofrea.grid_alignment.vector_alignment import (
    align_lakes,
    align_plants,
    align_rivers,
    calculate_wgs84_isotropic_distance,
    load_vector_bbox,
    rasterize_linear_distance,
)

_RES = 0.01


def _square(cx: float, cy: float, half_side: float) -> Polygon:
    return Polygon(
        [
            (cx - half_side, cy - half_side),
            (cx + half_side, cy - half_side),
            (cx + half_side, cy + half_side),
            (cx - half_side, cy + half_side),
        ]
    )


def _country_gdf() -> gpd.GeoDataFrame:
    # A diamond (rotated square), not an axis-aligned square: its own
    # bounding-box CORNERS fall outside the diamond's footprint
    # regardless of resolution-snapping (an axis-aligned square's bbox
    # can snap to an exact rectangle with no fringe at all — see
    # test_grid_alignment_reference_grid.py for the same fix). The
    # corner gap is what lets a feature sit inside the grid's raster
    # bounds but outside country_mask, needed to test
    # rasterize_linear_distance() vs. align_rivers()'s asymmetry.
    diamond = Polygon([(0.2, 0.0), (0.0, 0.2), (-0.2, 0.0), (0.0, -0.2)])
    return gpd.GeoDataFrame(geometry=[diamond], crs="EPSG:4326")


def _grid():
    return build_reference_grid(_country_gdf(), resolution_deg=_RES)


@pytest.mark.unit
def test_load_vector_bbox_filters_to_country_bbox_and_reprojects(tmp_path):
    country_gdf = _country_gdf()
    inside = Point(0.0, 0.0)
    far_away = Point(50.0, 50.0)
    gdf = gpd.GeoDataFrame(geometry=[inside, far_away], crs="EPSG:4326").to_crs("EPSG:3857")
    path = tmp_path / "layer.geojson"
    gdf.to_file(path, driver="GeoJSON")

    result = load_vector_bbox(path, country_gdf, "test")

    assert result is not None
    assert len(result) == 1
    assert result.crs.to_string() == country_gdf.crs.to_string()


@pytest.mark.unit
def test_load_vector_bbox_returns_none_for_empty_result(tmp_path):
    country_gdf = _country_gdf()
    far_away = gpd.GeoDataFrame(geometry=[Point(80.0, 80.0)], crs="EPSG:4326")
    path = tmp_path / "layer.geojson"
    far_away.to_file(path, driver="GeoJSON")

    assert load_vector_bbox(path, country_gdf, "test") is None


@pytest.mark.unit
def test_load_vector_bbox_returns_none_on_read_error(tmp_path):
    country_gdf = _country_gdf()
    assert load_vector_bbox(tmp_path / "does_not_exist.shp", country_gdf, "test") is None


@pytest.mark.unit
def test_calculate_wgs84_isotropic_distance_is_zero_at_feature_and_increases_away():
    grid = _grid()
    feature_mask_inv = np.ones((grid.height, grid.width), dtype=np.uint8)
    center = (grid.height // 2, grid.width // 2)
    feature_mask_inv[center] = 0  # 0 = feature pixel

    dist_km = calculate_wgs84_isotropic_distance(feature_mask_inv, grid)

    assert dist_km[center] == pytest.approx(0.0)
    assert dist_km[center[0], center[1] + 5] > dist_km[center[0], center[1] + 1] > 0


@pytest.mark.unit
def test_rasterize_linear_distance_returns_none_for_empty_or_none_gdf(tmp_path):
    grid = _grid()
    country_gdf = _country_gdf()

    assert rasterize_linear_distance(None, tmp_path / "out.tif", country_gdf, grid, "roads", 100.0) is None
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    assert rasterize_linear_distance(empty, tmp_path / "out.tif", country_gdf, grid, "roads", 100.0) is None


@pytest.mark.unit
def test_rasterize_linear_distance_respects_max_dist_km_cap(tmp_path):
    grid = _grid()
    country_gdf = _country_gdf()
    # A line through the middle of the country -> far corners should be
    # capped at max_dist_km rather than the true (larger) distance.
    line = gpd.GeoDataFrame(geometry=[LineString([(0.0, -0.2), (0.0, 0.2)])], crs="EPSG:4326")

    out_path = rasterize_linear_distance(
        line, tmp_path / "out.tif", country_gdf, grid, "roads", max_dist_km=5.0
    )

    assert out_path is not None
    with rasterio.open(out_path) as src:
        data = src.read(1)
    in_country = data[grid.country_mask]
    assert in_country.max() <= 5.0 + 1e-3
    assert in_country.min() == pytest.approx(0.0, abs=0.5)  # pixels on the line itself


@pytest.mark.unit
def test_rasterize_linear_distance_masks_output_outside_country():
    grid = _grid()
    country_gdf = _country_gdf()
    line = gpd.GeoDataFrame(geometry=[LineString([(0.0, -0.2), (0.0, 0.2)])], crs="EPSG:4326")

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        out_path = rasterize_linear_distance(
            line, Path(td) / "out.tif", country_gdf, grid, "roads", max_dist_km=5.0
        )
        with rasterio.open(out_path) as src:
            data = src.read(1)

    assert np.all(data[~grid.country_mask] == NODATA_FLOAT)


def _line_in_bbox_corner_outside_diamond() -> gpd.GeoDataFrame:
    # The diamond (|x| + |y| <= 0.2) leaves its own bounding box's
    # corners empty — a line through (0.12, 0.12)-(0.18, 0.18) has
    # |x|+|y| in [0.24, 0.36], safely outside the diamond, but well
    # within the grid's raster bounds (bbox snaps to roughly
    # [-0.2, 0.2] at this resolution).
    return gpd.GeoDataFrame(
        geometry=[LineString([(0.12, 0.12), (0.18, 0.18)])], crs="EPSG:4326"
    )


@pytest.mark.unit
def test_rasterize_linear_distance_returns_none_when_feature_does_not_intersect_country(tmp_path):
    # A feature entirely outside the country polygon (the diamond's own
    # bbox corner gap) but still inside the grid's raster bounds — the
    # STRtree intersects-filter must exclude it, unlike align_rivers()
    # (see test_align_rivers_includes_features_outside_country_mask below).
    grid = _grid()
    country_gdf = _country_gdf()
    line_outside = _line_in_bbox_corner_outside_diamond()

    result = rasterize_linear_distance(
        line_outside, tmp_path / "out.tif", country_gdf, grid, "roads", max_dist_km=100.0
    )

    assert result is None


@pytest.mark.unit
def test_align_rivers_includes_features_outside_country_mask_unlike_rasterize_linear_distance(tmp_path):
    # Locks in the documented asymmetry (vector_alignment.py module
    # docstring): align_rivers() has no STRtree intersects-prefilter and
    # does not AND the rasterized mask with grid.country_mask before the
    # distance transform, so a river feature outside the country still
    # legitimately shortens the distance value at nearby in-country
    # pixels — unlike rasterize_linear_distance(), which excludes such a
    # feature entirely (see the test above).
    grid = _grid()
    line_outside = _line_in_bbox_corner_outside_diamond()

    out_path = align_rivers(line_outside, tmp_path / "rivers.tif", grid)

    assert out_path is not None
    with rasterio.open(out_path) as src:
        data = src.read(1)
    # In-country pixels near the diamond's corner (closest to the
    # outside river) must show a distance well below the 50km cap,
    # proving the outside feature was NOT excluded.
    in_country = data[grid.country_mask]
    assert in_country.min() < 50.0


@pytest.mark.unit
def test_align_rivers_returns_none_for_empty_or_none_gdf(tmp_path):
    assert align_rivers(None, tmp_path / "out.tif", _grid()) is None
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    assert align_rivers(empty, tmp_path / "out.tif", _grid()) is None


@pytest.mark.unit
def test_align_rivers_caps_distance_at_50km(tmp_path):
    grid = _grid()
    line = gpd.GeoDataFrame(geometry=[LineString([(0.0, -0.2), (0.0, 0.2)])], crs="EPSG:4326")

    out_path = align_rivers(line, tmp_path / "rivers.tif", grid)

    with rasterio.open(out_path) as src:
        data = src.read(1)
    assert data[grid.country_mask].max() <= 50.0 + 1e-3


@pytest.mark.unit
def test_align_lakes_returns_none_for_empty_or_none_gdf(tmp_path):
    assert align_lakes(None, tmp_path / "out.tif", _grid()) is None
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    assert align_lakes(empty, tmp_path / "out.tif", _grid()) is None


@pytest.mark.unit
def test_align_lakes_produces_binary_mask_within_country(tmp_path):
    grid = _grid()
    lake = gpd.GeoDataFrame(geometry=[_square(0.0, 0.0, 0.05)], crs="EPSG:4326")

    out_path = align_lakes(lake, tmp_path / "lakes.tif", grid)

    assert out_path is not None
    with rasterio.open(out_path) as src:
        data = src.read(1)
    assert set(np.unique(data[grid.country_mask])) <= {0, 1}
    assert (data[grid.country_mask] == 1).any()
    assert np.all(data[~grid.country_mask] == NODATA_UINT8)


@pytest.mark.unit
def test_align_lakes_returns_none_when_every_geometry_is_empty(tmp_path):
    gdf = gpd.GeoDataFrame(geometry=[Polygon()], crs="EPSG:4326")  # non-empty gdf, empty geometry
    assert not gdf.empty
    assert align_lakes(gdf, tmp_path / "lakes.tif", _grid()) is None


@pytest.mark.unit
def test_align_rivers_returns_none_when_every_geometry_is_empty(tmp_path):
    gdf = gpd.GeoDataFrame(geometry=[Polygon()], crs="EPSG:4326")
    assert not gdf.empty
    assert align_rivers(gdf, tmp_path / "rivers.tif", _grid()) is None


@pytest.mark.unit
def test_rasterize_linear_distance_catches_rasterize_failure_and_returns_none(tmp_path):
    # Locks in the graceful-degradation contract (ported from legacy's
    # _align_linear_features): a failure inside the rasterize/distance
    # pipeline must not propagate, only make this one layer return None.
    grid = _grid()
    country_gdf = _country_gdf()
    line = gpd.GeoDataFrame(geometry=[LineString([(0.0, -0.1), (0.0, 0.1)])], crs="EPSG:4326")

    import geofrea.grid_alignment.vector_alignment as vector_alignment_module

    def boom(*a, **k):
        raise RuntimeError("simulated rasterize failure")

    with patch.object(vector_alignment_module, "rasterize", side_effect=boom):
        result = rasterize_linear_distance(line, tmp_path / "out.tif", country_gdf, grid, "roads", 100.0)

    assert result is None


@pytest.mark.unit
def test_align_plants_returns_none_when_missing_or_empty():
    grid = _grid()
    country_gdf = _country_gdf()
    assert align_plants(None, "out.tif", country_gdf, grid) is None
    assert align_plants(pd.DataFrame(), "out.tif", country_gdf, grid) is None


@pytest.mark.unit
def test_align_plants_returns_none_when_lat_lon_columns_missing():
    grid = _grid()
    country_gdf = _country_gdf()
    df = pd.DataFrame({"name": ["Plant A"], "capacity_mw": [10.0]})
    assert align_plants(df, "out.tif", country_gdf, grid) is None


@pytest.mark.unit
def test_align_plants_accepts_lat_lon_column_aliases(tmp_path):
    grid = _grid()
    country_gdf = _country_gdf()
    df = pd.DataFrame({"Lat": [0.0], "Long": [0.0]})

    out_path = align_plants(df, tmp_path / "plants.tif", country_gdf, grid)

    assert out_path is not None
    with rasterio.open(out_path) as src:
        data = src.read(1)
    assert (data[grid.country_mask] == 1).any()


@pytest.mark.unit
def test_align_plants_drops_points_outside_country_and_returns_none_if_all_dropped(tmp_path):
    grid = _grid()
    country_gdf = _country_gdf()
    df = pd.DataFrame({"latitude": [80.0], "longitude": [80.0]})

    assert align_plants(df, tmp_path / "plants.tif", country_gdf, grid) is None
