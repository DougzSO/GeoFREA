"""Unit tests for geofrea.core.geo_utils."""

import math

import geopandas as gpd
import numpy as np
import pytest
import shapely
from shapely.geometry import Polygon

from geofrea.core.geo_utils import (
    _THREADED_INTERSECTION_MIN_FEATURES,
    _intersection_threaded,
    _simplify_for_intersection,
    clip_vector_to_country,
    detect_island_nation,
    get_local_utm_crs,
    get_mainland_gdf,
    read_clipped_to_country,
    repair_invalid_geometries,
)


def _dense_circle(cx: float, cy: float, radius: float, n_points: int) -> Polygon:
    """A polygon with `n_points` vertices — stands in for a real, vertex-dense boundary."""
    return Polygon(
        [
            (cx + radius * math.cos(2 * math.pi * i / n_points), cy + radius * math.sin(2 * math.pi * i / n_points))
            for i in range(n_points)
        ]
    )


def _square(cx: float, cy: float, half_side: float) -> Polygon:
    return Polygon(
        [
            (cx - half_side, cy - half_side),
            (cx + half_side, cy - half_side),
            (cx + half_side, cy + half_side),
            (cx - half_side, cy + half_side),
        ]
    )


@pytest.mark.unit
def test_get_local_utm_crs_matches_known_zone_for_portugal():
    # Mainland Portugal: lon ~ -8, lat ~ 39 -> UTM zone 29N -> EPSG:32629.
    gdf = gpd.GeoDataFrame(geometry=[_square(-8.0, 39.0, 0.1)], crs="EPSG:4326")
    assert get_local_utm_crs(gdf) == "EPSG:32629"


@pytest.mark.unit
def test_get_local_utm_crs_southern_hemisphere_uses_327_prefix():
    # Southern hemisphere -> 327xx EPSG prefix, not 326xx.
    gdf = gpd.GeoDataFrame(geometry=[_square(-47.0, -15.0, 0.1)], crs="EPSG:4326")
    crs = get_local_utm_crs(gdf)
    assert crs.startswith("EPSG:327")


@pytest.mark.unit
def test_get_mainland_gdf_picks_the_largest_polygon():
    mainland = _square(0.0, 0.0, 1.0)  # ~2deg square
    island = _square(5.0, 5.0, 0.01)  # tiny square, far away
    gdf = gpd.GeoDataFrame(geometry=[mainland, island], crs="EPSG:4326")

    result = get_mainland_gdf(gdf)

    assert len(result) == 1
    assert result.crs.to_string() == "EPSG:4326"
    # The returned polygon must be the big one, not the tiny island.
    assert result.geometry.iloc[0].area > island.area


@pytest.mark.unit
def test_detect_island_nation_true_when_mainland_is_a_small_fraction():
    # Three equal-area polygons, far apart: the "largest" is ~33% of the
    # total, below the 40% floor (largest_pct < 1 - 0.60).
    parts = [_square(0.0, 0.0, 1.0), _square(5.0, 5.0, 1.0), _square(-5.0, -5.0, 1.0)]
    gdf = gpd.GeoDataFrame(geometry=parts, crs="EPSG:4326")

    assert detect_island_nation(gdf) is True


@pytest.mark.unit
def test_detect_island_nation_false_for_a_single_polygon_country():
    gdf = gpd.GeoDataFrame(geometry=[_square(0.0, 0.0, 1.0)], crs="EPSG:4326")

    assert detect_island_nation(gdf) is False


@pytest.mark.unit
def test_clip_vector_to_country_drops_features_outside_and_cuts_crossing_ones():
    country_gdf = gpd.GeoDataFrame(geometry=[_square(0.0, 0.0, 1.0)], crs="EPSG:4326")

    inside = _square(0.0, 0.0, 0.2)
    crossing = _square(0.9, 0.0, 0.3)  # centered near the country's edge
    far_away = _square(10.0, 10.0, 0.1)
    gdf = gpd.GeoDataFrame(geometry=[inside, crossing, far_away], crs="EPSG:4326")

    clipped, _repair = clip_vector_to_country(gdf, country_gdf)

    assert len(clipped) == 2
    # The crossing feature must be cut down, not kept whole.
    crossing_result = clipped.geometry.iloc[
        clipped.geometry.apply(lambda g: g.centroid.x > 0.5).to_numpy().argmax()
    ]
    assert crossing_result.area < crossing.area


@pytest.mark.unit
def test_clip_vector_to_country_matches_by_position_not_by_pandas_label():
    # clip_vector_to_country() was rewritten 2026-08-25 (see module
    # docstring and DECISIONS.md same date, STRtree fix) to select
    # matches via shapely.STRtree.query() + gdf.iloc[positions] rather
    # than a boolean mask. STRtree.query() returns POSITIONS into the
    # array passed to it (prefiltered.geometry.values), which only
    # lines up correctly with prefiltered.iloc[...] if the pandas
    # label index is never confused for a position — this GeoDataFrame
    # has a deliberately non-default, non-contiguous index (from
    # slicing a larger frame) to catch a regression where a future
    # edit swaps .iloc for .loc, or otherwise assumes label == position.
    country_gdf = gpd.GeoDataFrame(geometry=[_square(0.0, 0.0, 1.0)], crs="EPSG:4326")

    far_away_1 = _square(20.0, 20.0, 0.1)
    inside_a = _square(0.0, 0.0, 0.2)
    far_away_2 = _square(-20.0, -20.0, 0.1)
    inside_b = _square(0.3, 0.3, 0.1)
    far_away_3 = _square(30.0, -30.0, 0.1)

    full_gdf = gpd.GeoDataFrame(
        geometry=[far_away_1, inside_a, far_away_2, inside_b, far_away_3],
        index=[100, 205, 7, 999, 3],
        crs="EPSG:4326",
    )
    # A non-contiguous, out-of-order slice — label index no longer
    # resembles 0..n-1 in any way after this.
    gdf = full_gdf.loc[[999, 100, 205, 3, 7]]

    clipped, _repair = clip_vector_to_country(gdf, country_gdf)

    assert len(clipped) == 2
    centroids_x = sorted(round(g.centroid.x, 1) for g in clipped.geometry)
    assert centroids_x == [0.0, 0.3]


@pytest.mark.unit
def test_clip_vector_to_country_reprojects_when_crs_differs():
    country_gdf = gpd.GeoDataFrame(geometry=[_square(-8.0, 39.0, 1.0)], crs="EPSG:4326")
    gdf = gpd.GeoDataFrame(geometry=[_square(-8.0, 39.0, 0.2)], crs="EPSG:4326").to_crs(
        "EPSG:3857"
    )

    clipped, _repair = clip_vector_to_country(gdf, country_gdf)

    assert len(clipped) == 1


# ─── _simplify_for_intersection() / country_geom simplification
# (2026-08-25, see module docstring and DECISIONS.md same date) ───


@pytest.mark.unit
def test_simplify_for_intersection_reduces_vertices_for_geographic_crs():
    dense = _dense_circle(0.0, 0.0, radius=1.0, n_points=5000)
    assert shapely.get_num_coordinates(dense) > 4900

    simplified, _repaired = _simplify_for_intersection(dense, gpd.GeoSeries([dense], crs="EPSG:4326").crs)

    n = shapely.get_num_coordinates(simplified)
    assert 0 < n < 500  # drastic reduction at 0.001deg tolerance on a 1deg-radius circle
    # Area must stay close to the original — a fidelity check, not just "fewer points".
    assert simplified.area == pytest.approx(dense.area, rel=0.01)


@pytest.mark.unit
def test_simplify_for_intersection_uses_meters_tolerance_for_projected_crs():
    # A circle with a radius on the order of the projected (meters)
    # tolerance itself (~100m) should collapse hard under that
    # tolerance — this would NOT happen if the function mistakenly
    # applied the degrees tolerance (0.001) to projected-CRS data,
    # since 0.001 "units" here means 0.001 METERS, i.e. no-op.
    dense = _dense_circle(500000.0, 4000000.0, radius=150.0, n_points=2000)
    crs = gpd.GeoSeries([dense], crs="EPSG:32633").crs  # UTM zone 33N, projected, meters
    assert crs.is_geographic is False

    simplified, _repaired = _simplify_for_intersection(dense, crs)

    assert shapely.get_num_coordinates(simplified) < shapely.get_num_coordinates(dense)


@pytest.mark.unit
def test_simplify_for_intersection_repairs_invalid_geometry_before_simplifying():
    # A classic bowtie/self-intersecting polygon — invalid input.
    bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)])
    assert not shapely.is_valid(bowtie)

    result, repaired = _simplify_for_intersection(bowtie, gpd.GeoSeries([bowtie], crs="EPSG:4326").crs)

    assert shapely.is_valid(result)
    assert repaired is True


@pytest.mark.unit
def test_clip_vector_to_country_with_vertex_dense_boundary_still_matches_correctly():
    # End-to-end: a country polygon with thousands of vertices (real
    # Brazil has 311,499 — this uses a smaller but still "dense"
    # stand-in to keep the test fast) must still correctly include
    # inside features, exclude far-away ones, and cut crossing ones,
    # despite the boundary being simplified internally.
    country_gdf = gpd.GeoDataFrame(geometry=[_dense_circle(0.0, 0.0, radius=1.0, n_points=3000)], crs="EPSG:4326")

    inside = _square(0.0, 0.0, 0.2)
    crossing = _square(0.95, 0.0, 0.3)
    far_away = _square(10.0, 10.0, 0.1)
    gdf = gpd.GeoDataFrame(geometry=[inside, crossing, far_away], crs="EPSG:4326")

    clipped, _repair = clip_vector_to_country(gdf, country_gdf)

    assert len(clipped) == 2
    by_centroid_x = {round(g.centroid.x, 2): g for g in clipped.geometry}
    inside_result = by_centroid_x[0.0]
    crossing_result = next(g for cx, g in by_centroid_x.items() if cx != 0.0)

    assert inside_result.area == pytest.approx(inside.area, rel=0.01)  # stayed ~whole
    assert crossing_result.area < crossing.area  # cut down, not kept whole


@pytest.mark.unit
def test_read_clipped_to_country_matches_read_then_clip(tmp_path):
    # read_clipped_to_country() pushes the bbox filter into the read
    # itself (added 2026-08-25, see module docstring) — this confirms
    # it produces the exact same result as the old
    # clip_vector_to_country(gpd.read_file(path), country_gdf) two-step,
    # not just "some" clipped output.
    country_gdf = gpd.GeoDataFrame(geometry=[_square(0.0, 0.0, 1.0)], crs="EPSG:4326")
    inside = _square(0.0, 0.0, 0.2)
    crossing = _square(0.9, 0.0, 0.3)
    far_away = _square(10.0, 10.0, 0.1)
    path = tmp_path / "layer.geojson"
    gpd.GeoDataFrame(geometry=[inside, crossing, far_away], crs="EPSG:4326").to_file(
        path, driver="GeoJSON"
    )

    via_read_time_bbox, _repair_a = read_clipped_to_country(path, country_gdf)
    via_full_read, _repair_b = clip_vector_to_country(gpd.read_file(path), country_gdf)

    assert len(via_read_time_bbox) == len(via_full_read) == 2
    assert sorted(via_read_time_bbox.geometry.area) == pytest.approx(
        sorted(via_full_read.geometry.area)
    )


@pytest.mark.unit
def test_read_clipped_to_country_reprojects_bbox_to_the_files_own_crs(tmp_path):
    # The file's CRS (EPSG:3857) differs from country_gdf's (EPSG:4326)
    # — the bbox used for the read-time filter must be computed in the
    # FILE's CRS (via pyogrio.read_info()), not country_gdf's, or the
    # bbox read would silently return the wrong (or zero) rows.
    country_gdf = gpd.GeoDataFrame(geometry=[_square(-8.0, 39.0, 1.0)], crs="EPSG:4326")
    path = tmp_path / "layer_3857.geojson"
    gpd.GeoDataFrame(geometry=[_square(-8.0, 39.0, 0.2)], crs="EPSG:4326").to_crs(
        "EPSG:3857"
    ).to_file(path, driver="GeoJSON")

    clipped, _repair = read_clipped_to_country(path, country_gdf)

    assert len(clipped) == 1


# ─── _intersection_threaded() (2026-08-25, see module docstring and
# DECISIONS.md same date) ───


@pytest.mark.unit
def test_intersection_threaded_caps_workers_at_physical_core_fallback(monkeypatch):
    # Douglas's explicit adjustment 2026-08-25: os.cpu_count() (logical,
    # e.g. 16 on the dev machine) is capped at _MAX_INTERSECTION_WORKERS
    # (8) rather than used directly — measured speedup saturates past
    # physical core count, and logical count overstates it on shared/CI
    # environments. Simulate a 32-logical-core machine and confirm the
    # ThreadPoolExecutor is never asked for more than 8 workers.
    import geofrea.core.geo_utils as geo_utils_module

    monkeypatch.setattr(geo_utils_module.os, "cpu_count", lambda: 32)

    seen_max_workers = []
    real_executor_cls = geo_utils_module.ThreadPoolExecutor

    class _SpyExecutor(real_executor_cls):
        def __init__(self, max_workers=None, *args, **kwargs):
            seen_max_workers.append(max_workers)
            super().__init__(*args, max_workers=max_workers, **kwargs)

    monkeypatch.setattr(geo_utils_module, "ThreadPoolExecutor", _SpyExecutor)

    clip_geom = _square(0.0, 0.0, 5.0)
    n = _THREADED_INTERSECTION_MIN_FEATURES + 500
    geoms = np.array([_square(float(i % 10) - 4.5, 0.0, 0.4) for i in range(n)])

    _intersection_threaded(geoms, clip_geom)

    assert seen_max_workers == [8]


@pytest.mark.unit
def test_intersection_threaded_below_min_features_matches_plain_shapely():
    clip_geom = _square(0.0, 0.0, 5.0)
    geoms = np.array([_square(float(i % 3), 0.0, 0.4) for i in range(50)])
    assert len(geoms) < _THREADED_INTERSECTION_MIN_FEATURES

    result = _intersection_threaded(geoms, clip_geom)
    expected = shapely.intersection(geoms, clip_geom)

    assert len(result) == len(expected) == 50
    assert all(a.equals(b) for a, b in zip(result, expected, strict=True))


@pytest.mark.unit
def test_intersection_threaded_above_min_features_matches_plain_shapely():
    # Exercises the actual ThreadPoolExecutor branch — cheap geometries
    # (small squares) so the test stays fast despite the large count,
    # since the point is to verify correctness of the chunk/reassemble
    # logic, not to re-benchmark the real speedup (already measured
    # live on real Brazil data — see module docstring).
    n = _THREADED_INTERSECTION_MIN_FEATURES + 500
    clip_geom = _square(0.0, 0.0, 5.0)
    geoms = np.array([_square(float(i % 10) - 4.5, 0.0, 0.4) for i in range(n)])

    result = _intersection_threaded(geoms, clip_geom)
    expected = shapely.intersection(geoms, clip_geom)

    assert len(result) == len(expected) == n
    assert all(a.equals(b) for a, b in zip(result, expected, strict=True))
    assert any(not g.is_empty for g in result)  # not a degenerate all-empty result


@pytest.mark.unit
def test_clip_vector_to_country_uses_threaded_path_above_min_features():
    # End-to-end: clip_vector_to_country() itself must route through
    # the threaded branch (not just _intersection_threaded() in
    # isolation) once the STRtree-matched count crosses the threshold,
    # and still produce correct output.
    country_gdf = gpd.GeoDataFrame(geometry=[_square(0.0, 0.0, 5.0)], crs="EPSG:4326")
    n = _THREADED_INTERSECTION_MIN_FEATURES + 500
    inside = [_square(float(i % 10) - 4.5, 0.0, 0.4) for i in range(n)]
    far_away = _square(100.0, 100.0, 0.1)
    gdf = gpd.GeoDataFrame(geometry=[*inside, far_away], crs="EPSG:4326")

    clipped, _repair = clip_vector_to_country(gdf, country_gdf)

    assert len(clipped) == n  # far_away dropped, everything else survives (fully inside)


# ─── repair_invalid_geometries() / clip_vector_to_country() unconditional
# repair (2026-09-21, see docs/phases/core.md — moved from
# suitability_criteria's WDPA-only repair) ───


def _bowtie() -> Polygon:
    return Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)])


@pytest.mark.unit
def test_repair_invalid_geometries_repairs_bowtie_and_reports_it():
    bowtie = _bowtie()
    assert not bowtie.is_valid

    gdf = gpd.GeoDataFrame(geometry=[bowtie], crs="EPSG:4326")
    repaired_gdf, report = repair_invalid_geometries(gdf)

    assert report.n_total == 1
    assert report.n_invalid == 1
    assert report.n_repaired == 1
    assert "Self-intersection" in report.invalid_reasons
    assert all(g.is_valid for g in repaired_gdf.geometry)


@pytest.mark.unit
def test_repair_invalid_geometries_leaves_valid_geometry_untouched():
    square = _square(0.0, 0.0, 1.0)
    gdf = gpd.GeoDataFrame(geometry=[square], crs="EPSG:4326")

    repaired_gdf, report = repair_invalid_geometries(gdf)

    assert report.n_total == 1
    assert report.n_invalid == 0
    assert report.n_repaired == 0
    assert report.invalid_reasons == {}
    assert repaired_gdf.geometry.iloc[0].equals(square)


@pytest.mark.unit
def test_clip_vector_to_country_repairs_bowtie_feature_without_raising():
    # A bowtie in the CANDIDATE features (not the country polygon) used
    # to crash .intersection() with a GEOSException before repair moved
    # into the shared clip path — this must now succeed and count the
    # repair.
    country_gdf = gpd.GeoDataFrame(geometry=[_square(0.0, 0.0, 5.0)], crs="EPSG:4326")
    bowtie = _bowtie()
    gdf = gpd.GeoDataFrame(geometry=[bowtie], crs="EPSG:4326")

    clipped, report = clip_vector_to_country(gdf, country_gdf)

    assert report.n_invalid == 1
    assert report.n_repaired == 1
    assert len(clipped) >= 1


@pytest.mark.unit
def test_clip_vector_to_country_repairs_invalid_simplified_country_polygon(monkeypatch):
    # Simulate shapely.simplify() producing an invalid result (rare in
    # practice, but the post-simplify validity check must catch it and
    # repair it, per docs/phases/core.md — not just trust simplify()).
    import geofrea.core.geo_utils as geo_utils_module

    bowtie = _bowtie()
    real_simplify = shapely.simplify

    def _simplify_returns_bowtie(geom, tolerance, preserve_topology):
        return bowtie

    monkeypatch.setattr(geo_utils_module.shapely, "simplify", _simplify_returns_bowtie)

    country_gdf = gpd.GeoDataFrame(geometry=[_square(0.0, 0.0, 1.0)], crs="EPSG:4326")
    gdf = gpd.GeoDataFrame(geometry=[_square(0.0, 0.0, 0.2)], crs="EPSG:4326")

    _clipped, report = clip_vector_to_country(gdf, country_gdf)

    assert report.country_polygon_repaired is True
    monkeypatch.setattr(geo_utils_module.shapely, "simplify", real_simplify)
