"""Unit tests for geofrea.data_quality_audit.vector_inspection."""

from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import LineString, box

from geofrea.data_quality_audit.vector_inspection import inspect_vector_layer


@pytest.mark.unit
def test_inspect_vector_layer_missing_path_returns_not_found():
    result = inspect_vector_layer(None)
    assert result["found"] is False
    assert result["error"] is None


@pytest.mark.unit
def test_inspect_vector_layer_nonexistent_file_returns_not_found():
    result = inspect_vector_layer(Path("/does/not/exist.geojson"))
    assert result["found"] is False


@pytest.mark.unit
def test_inspect_vector_layer_corrupted_file_reports_error_not_raise(tmp_path):
    path = tmp_path / "corrupt.geojson"
    path.write_text("this is not valid geojson", encoding="utf-8")

    result = inspect_vector_layer(path)

    assert result["found"] is True
    assert result["error"] is not None
    assert result["n_features"] is None


@pytest.mark.unit
def test_inspect_vector_layer_polygon_layer_computes_area_and_clips(tmp_path):
    country_gdf = gpd.GeoDataFrame(geometry=[box(0, 0, 2, 2)], crs="EPSG:4326")
    inside = box(0.2, 0.2, 0.5, 0.5)
    outside = box(10, 10, 10.1, 10.1)
    path = tmp_path / "polygons.geojson"
    gpd.GeoDataFrame(geometry=[inside, outside], crs="EPSG:4326").to_file(path, driver="GeoJSON")

    result = inspect_vector_layer(path, country_gdf=country_gdf, clip=True)

    assert result["found"] is True
    assert result["error"] is None
    assert result["clipped_to_country"] is True
    assert result["n_features"] == 1
    assert result["geometry_types"] == ["Polygon"]
    assert result["total_area_km2"] is not None
    assert result["total_length_km"] is None


@pytest.mark.unit
def test_inspect_vector_layer_line_layer_computes_length_not_area(tmp_path):
    line = LineString([(0, 0), (0, 1)])
    path = tmp_path / "lines.geojson"
    gpd.GeoDataFrame(geometry=[line], crs="EPSG:4326").to_file(path, driver="GeoJSON")

    result = inspect_vector_layer(path, clip=False)

    assert result["total_length_km"] is not None
    assert result["total_area_km2"] is None


@pytest.mark.unit
def test_inspect_vector_layer_clip_false_skips_clipping_even_with_country_gdf(tmp_path):
    country_gdf = gpd.GeoDataFrame(geometry=[box(0, 0, 1, 1)], crs="EPSG:4326")
    far_away = box(50, 50, 50.1, 50.1)
    path = tmp_path / "unclipped.geojson"
    gpd.GeoDataFrame(geometry=[far_away], crs="EPSG:4326").to_file(path, driver="GeoJSON")

    result = inspect_vector_layer(path, country_gdf=country_gdf, clip=False)

    assert result["clipped_to_country"] is False
    assert result["n_features"] == 1


@pytest.mark.unit
def test_inspect_vector_layer_iucn_breakdown_groups_by_category(tmp_path):
    park = box(0, 0, 1, 1)
    reserve = box(2, 2, 3, 3)
    path = tmp_path / "protected.geojson"
    gpd.GeoDataFrame(
        {"IUCN_CAT": ["II", "II"]},
        geometry=[park, reserve],
        crs="EPSG:4326",
    ).to_file(path, driver="GeoJSON")

    result = inspect_vector_layer(path, clip=False, iucn_breakdown=True)

    assert result["attribute_breakdown"] is not None
    # Bucket keys are lowercase since 2026-08-24 (see DECISIONS.md same
    # date, "IUCN category normalization fix") — "II" normalizes to "ii".
    assert result["attribute_breakdown"]["ii"]["count"] == 2


@pytest.mark.unit
def test_inspect_vector_layer_iucn_breakdown_normalizes_roman_numeral_case(tmp_path):
    # Added 2026-08-24 (see DECISIONS.md same date, "IUCN category
    # normalization fix"): case-varied roman-numeral category codes
    # ("II"/"ii"/"Ii") are the most likely real-world case in WDPA data
    # — more so than "Not Reported" varying case — and must collapse
    # into a single "ii" bucket, same as the designation-text case.
    a = box(0, 0, 1, 1)
    b = box(2, 2, 3, 3)
    c = box(4, 4, 5, 5)
    path = tmp_path / "protected.geojson"
    gpd.GeoDataFrame(
        {"IUCN_CAT": ["II", "ii", "Ii"]},
        geometry=[a, b, c],
        crs="EPSG:4326",
    ).to_file(path, driver="GeoJSON")

    result = inspect_vector_layer(path, clip=False, iucn_breakdown=True)

    assert result["attribute_breakdown"] is not None
    assert set(result["attribute_breakdown"]) == {"ii"}
    assert result["attribute_breakdown"]["ii"]["count"] == 3


@pytest.mark.unit
def test_inspect_vector_layer_iucn_breakdown_normalizes_case_before_grouping(tmp_path):
    # Added 2026-08-24 (see DECISIONS.md same date, "IUCN category
    # normalization fix"): "Not Reported" and "not reported" must
    # collapse into one bucket, replicating compute_protected_areas()'s
    # own .str.lower().str.strip() normalization in the legacy pipeline
    # — without it, real WDPA data (which is not case-consistent) would
    # fragment identical categories into separate buckets.
    a = box(0, 0, 1, 1)
    b = box(2, 2, 3, 3)
    c = box(4, 4, 5, 5)
    path = tmp_path / "protected.geojson"
    gpd.GeoDataFrame(
        {"IUCN_CAT": ["Not Reported", "not reported", "NOT REPORTED"]},
        geometry=[a, b, c],
        crs="EPSG:4326",
    ).to_file(path, driver="GeoJSON")

    result = inspect_vector_layer(path, clip=False, iucn_breakdown=True)

    assert result["attribute_breakdown"] is not None
    assert set(result["attribute_breakdown"]) == {"not reported"}
    assert result["attribute_breakdown"]["not reported"]["count"] == 3


@pytest.mark.unit
def test_inspect_vector_layer_iucn_breakdown_none_when_no_category_column(tmp_path):
    path = tmp_path / "roads.geojson"
    gpd.GeoDataFrame(geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:4326").to_file(
        path, driver="GeoJSON"
    )

    result = inspect_vector_layer(path, clip=False, iucn_breakdown=True)

    assert result["attribute_breakdown"] is None
