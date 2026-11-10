"""Unit tests for geofrea.grid_alignment.vector_alignment."""

from unittest.mock import patch

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from shapely.geometry import LineString, Point, Polygon

from geofrea.core.constants import NODATA_FLOAT, NODATA_UINT8
from geofrea.grid_alignment.reference_grid import build_reference_grid
from geofrea.grid_alignment.vector_alignment import (
    align_lakes,
    align_rivers,
    densify_step_deg,
    distance_capped_path,
    feature_vertices,
    filter_road_classes,
    geodesic_distance_to_vertices,
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
def test_rasterize_linear_distance_returns_none_for_empty_or_none_gdf(tmp_path):
    grid = _grid()
    country_gdf = _country_gdf()

    assert (
        rasterize_linear_distance(None, tmp_path / "out.tif", country_gdf, grid, "roads", 100.0)
        is None
    )
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    assert (
        rasterize_linear_distance(empty, tmp_path / "out.tif", country_gdf, grid, "roads", 100.0)
        is None
    )


@pytest.mark.unit
def test_rasterize_linear_distance_stores_the_raw_distance_and_flags_beyond_the_cap(tmp_path):
    # OQ-040 (M-F2a-03, METHODOLOGY 1.4.0): the distance is never truncated; distance_cap_km only
    # sets the `distance_capped` flag raster written beside it.
    grid = _grid()
    country_gdf = _country_gdf()
    line = gpd.GeoDataFrame(geometry=[LineString([(0.0, -0.2), (0.0, 0.2)])], crs="EPSG:4326")

    out_path = rasterize_linear_distance(
        line, tmp_path / "out.tif", country_gdf, grid, "roads", distance_cap_km=5.0
    )

    assert out_path is not None
    with rasterio.open(out_path) as src:
        data = src.read(1)
    with rasterio.open(distance_capped_path(out_path)) as src:
        flag = src.read(1)
    in_country = data[grid.country_mask]
    assert in_country.max() > 5.0 + 1.0  # far corners keep their real, larger distance
    assert in_country.min() == pytest.approx(0.557, abs=0.05)  # the line runs on a pixel edge: the nearest centres are half a pixel (0.005 degree) away
    inside_flag = flag[grid.country_mask]
    assert set(np.unique(inside_flag)) <= {0, 1}
    assert np.array_equal(
        inside_flag == 1, in_country > 5.0
    )  # flag marks exactly the raw distances above the cap
    assert (flag[~grid.country_mask] == NODATA_UINT8).all()


@pytest.mark.unit
def test_rasterize_linear_distance_masks_output_outside_country():
    grid = _grid()
    country_gdf = _country_gdf()
    line = gpd.GeoDataFrame(geometry=[LineString([(0.0, -0.2), (0.0, 0.2)])], crs="EPSG:4326")

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        out_path = rasterize_linear_distance(
            line, Path(td) / "out.tif", country_gdf, grid, "roads", distance_cap_km=5.0
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
    return gpd.GeoDataFrame(geometry=[LineString([(0.12, 0.12), (0.18, 0.18)])], crs="EPSG:4326")


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
        line_outside, tmp_path / "out.tif", country_gdf, grid, "roads", distance_cap_km=100.0
    )

    assert result is None


@pytest.mark.unit
def test_align_rivers_includes_features_outside_country_mask_unlike_rasterize_linear_distance(
    tmp_path,
):
    # Locks in the documented asymmetry (vector_alignment.py module
    # docstring): align_rivers() has no STRtree intersects-prefilter and
    # does not AND the rasterized mask with grid.country_mask before the
    # distance transform, so a river feature outside the country still
    # legitimately shortens the distance value at nearby in-country
    # pixels — unlike rasterize_linear_distance(), which excludes such a
    # feature entirely (see the test above).
    grid = _grid()
    line_outside = _line_in_bbox_corner_outside_diamond()

    out_path = align_rivers(line_outside, tmp_path / "rivers.tif", grid, 100.0)

    assert out_path is not None
    with rasterio.open(out_path) as src:
        data = src.read(1)
    # In-country pixels near the diamond's corner (closest to the
    # outside river) must show a distance well below the cap, proving
    # the outside feature was NOT excluded.
    in_country = data[grid.country_mask]
    assert in_country.min() < 100.0


@pytest.mark.unit
def test_align_rivers_returns_none_for_empty_or_none_gdf(tmp_path):
    assert align_rivers(None, tmp_path / "out.tif", _grid(), 100.0) is None
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    assert align_rivers(empty, tmp_path / "out.tif", _grid(), 100.0) is None


@pytest.mark.unit
def test_align_rivers_stores_the_raw_distance_and_flags_beyond_the_cap(tmp_path):
    grid = _grid()
    line = gpd.GeoDataFrame(geometry=[LineString([(0.0, -0.2), (0.0, 0.2)])], crs="EPSG:4326")

    out_path = align_rivers(line, tmp_path / "rivers.tif", grid, 5.0)

    with rasterio.open(out_path) as src:
        data = src.read(1)
    with rasterio.open(distance_capped_path(out_path)) as src:
        flag = src.read(1)
    assert data[grid.country_mask].max() > 6.0  # not truncated at the 5 km threshold
    assert np.array_equal(flag[grid.country_mask] == 1, data[grid.country_mask] > 5.0)


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
    assert align_rivers(gdf, tmp_path / "rivers.tif", _grid(), 100.0) is None


@pytest.mark.unit
def test_rasterize_linear_distance_catches_rasterize_failure_and_returns_none(tmp_path):
    # Locks in the graceful-degradation contract (ported from legacy's
    # _align_linear_features): a failure inside the vertex/distance
    # pipeline must not propagate, only make this one layer return None.
    grid = _grid()
    country_gdf = _country_gdf()
    line = gpd.GeoDataFrame(geometry=[LineString([(0.0, -0.1), (0.0, 0.1)])], crs="EPSG:4326")

    import geofrea.grid_alignment.vector_alignment as vector_alignment_module

    def boom(*a, **k):
        raise RuntimeError("simulated rasterize failure")

    with patch.object(vector_alignment_module, "geodesic_distance_to_vertices", side_effect=boom):
        result = rasterize_linear_distance(
            line, tmp_path / "out.tif", country_gdf, grid, "roads", 100.0
        )

    assert result is None


# -- road classes (Group 3, M-F2a-10) ---------------------------------------------------------------------


def _roads(column, values):
    return gpd.GeoDataFrame(
        {column: values},
        geometry=[LineString([(0.0, i), (1.0, i)]) for i in range(len(values))],
        crs="EPSG:4326",
    )


@pytest.mark.unit
def test_filter_road_classes_keeps_the_grip4_primary_and_secondary_roads_and_the_highways():
    from geofrea.core.schemas import RoadClasses

    classes = RoadClasses(grip4_gp_rtp=[1, 2, 3], osm_highway=["primary"])
    kept = filter_road_classes(_roads("GP_RTP", [1, 2, 3, 4, 5, 3]), classes)
    assert kept["GP_RTP"].tolist() == [1, 2, 3, 3]


@pytest.mark.unit
def test_filter_road_classes_reads_the_osm_highway_tag_and_ignores_a_source_without_classes():
    from geofrea.core.schemas import RoadClasses

    classes = RoadClasses(grip4_gp_rtp=[1], osm_highway=["motorway", "trunk", "primary", "secondary"])
    osm = _roads("highway", ["tertiary", "primary", "secondary", "residential", "motorway"])
    assert filter_road_classes(osm, classes)["highway"].tolist() == ["primary", "secondary", "motorway"]
    plain = _roads("gp_gripreg", [99, 99])  # the synthetic country has no road class
    assert len(filter_road_classes(plain, classes)) == 2
    assert filter_road_classes(osm, None) is osm  # no configuration keeps every road
    assert filter_road_classes(None, classes) is None


@pytest.mark.unit
def test_filter_road_classes_gives_none_when_no_road_is_in_the_classes():
    from geofrea.core.schemas import RoadClasses

    classes = RoadClasses(grip4_gp_rtp=[1], osm_highway=["primary"])
    assert filter_road_classes(_roads("GP_RTP", [4, 5]), classes) is None


# -- geodesic distance to the exact features (M-F2a-03, COMMAND 115) --------------------------------------
#
# The expected values come from `pyproj.Geod.inv` on the geodetic points of the pixel centre and of the target, an implementation that shares
# nothing with the tree of the function under test (a nearest neighbour in Earth-centred coordinates).

from pyproj import Geod
from rasterio.transform import from_origin

from geofrea.grid_alignment.reference_grid import GridContext

_WGS84 = Geod(ellps="WGS84")


def _window(lat_top: float, lon_left: float = 10.0, rows: int = 30, cols: int = 30) -> GridContext:
    """A 0.01-degree window whose north edge is `lat_top`, every pixel in the country."""
    return GridContext(
        transform=from_origin(lon_left, lat_top, _RES, _RES),
        width=cols,
        height=rows,
        crs="EPSG:4326",
        country_mask=np.ones((rows, cols), dtype=bool),
    )


def _centres(grid: GridContext) -> tuple[np.ndarray, np.ndarray]:
    rows, cols = np.indices((grid.height, grid.width))
    return (
        grid.transform.c + (cols + 0.5) * grid.transform.a,
        grid.transform.f + (rows + 0.5) * grid.transform.e,
    )


@pytest.mark.unit
@pytest.mark.parametrize("lat_top", [-29.85, 0.15, 40.15])
@pytest.mark.parametrize("direction", ["east-west", "north-south", "diagonal"])
def test_the_distance_to_one_point_is_the_wgs84_geodesic_at_three_latitudes(lat_top, direction):
    grid = _window(lat_top)
    lon_c, lat_c = _centres(grid)
    # the point sits at a corner of the window, so the pixels lie east-west of it, north-south of it, or on the diagonal
    corner_lon, corner_lat = lon_c[0, 0], lat_c[0, 0]
    keep = np.zeros(lon_c.shape, bool)
    if direction == "east-west":
        keep[0, :] = True
    elif direction == "north-south":
        keep[:, 0] = True
    else:
        keep = np.eye(grid.height, grid.width, dtype=bool)
    grid.country_mask[:] = keep

    got = geodesic_distance_to_vertices(np.array([corner_lon]), np.array([corner_lat]), grid)

    expected = (
        _WGS84.inv(lon_c[keep], lat_c[keep], np.full(keep.sum(), corner_lon), np.full(keep.sum(), corner_lat))[2] / 1000.0
    )
    assert expected.max() > 3.0  # a real distance, not only the zero of the pixel of the point
    # the raster is float32 (about 6e-8 relative); the method itself is exact
    np.testing.assert_allclose(got[keep].astype("float64"), expected, rtol=1e-6, atol=1e-9)
    assert np.isnan(got[~keep]).all()


@pytest.mark.unit
def test_a_point_inside_a_pixel_is_measured_from_its_exact_position_not_from_the_pixel_centre():
    grid = _window(10.5, rows=5, cols=5)
    lon_c, lat_c = _centres(grid)
    # a point 0.0041 degree east and 0.0033 degree north of the centre of pixel (2, 2): inside that pixel, nowhere near its centre
    point_lon, point_lat = lon_c[2, 2] + 0.0041, lat_c[2, 2] + 0.0033
    assert grid.transform.c + 3 * _RES > point_lon > grid.transform.c + 2 * _RES

    got = geodesic_distance_to_vertices(np.array([point_lon]), np.array([point_lat]), grid)

    for r, c in [(2, 2), (2, 3), (3, 2), (0, 4)]:
        exact = _WGS84.inv(lon_c[r, c], lat_c[r, c], point_lon, point_lat)[2] / 1000.0
        assert got[r, c] == pytest.approx(exact, rel=1e-6)
    # the pixel that holds the point is not at distance zero (as it was when the point was burnt into a pixel), and the neighbour is not a
    # whole pixel away from it
    assert got[2, 2] > 0.4
    centre_to_centre = _WGS84.inv(lon_c[2, 2], lat_c[2, 2], lon_c[2, 3], lat_c[2, 3])[2] / 1000.0
    assert abs(got[2, 3] - centre_to_centre) > 0.1


@pytest.mark.unit
def test_the_distance_to_a_densified_line_stays_within_s_squared_over_8d_of_the_distance_to_the_line():
    grid = _window(40.15, rows=60, cols=60)
    lon_c, lat_c = _centres(grid)
    # a straight east-west line at 40 N: the nearest point of the line to a pixel centre is taken as the point at the same longitude
    line_lat = 40.0
    line = LineString([(grid.transform.c - 0.05, line_lat), (grid.transform.c + 0.65, line_lat)])
    lon, lat = feature_vertices(gpd.GeoSeries([line], crs="EPSG:4326"), grid, within_country=True)
    assert len(lon) > 600  # about 100 m apart over 0.7 degree
    step_m = float(np.max(_WGS84.inv(lon[:-1], lat[:-1], lon[1:], lat[1:])[2]))
    assert step_m <= 100.0 + 1e-6

    got = geodesic_distance_to_vertices(lon, lat, grid).astype("float64")

    expected = _WGS84.inv(lon_c, lat_c, lon_c, np.full(lon_c.shape, line_lat))[2] / 1000.0
    far = expected > 0.5
    # a vertex lies at most s/2 along the line from the foot of the perpendicular: the excess is at most (s/2)^2 / (2 D) = s^2 / (8 D)
    bound = (step_m / 1000.0) ** 2 / (8.0 * expected[far])
    assert (got[far] >= expected[far] * (1 - 1e-6)).all()  # never nearer than the line itself
    assert (got[far] - expected[far] <= bound * 1.01 + 1e-5).all()  # 1e-5 km: the float32 raster


@pytest.mark.unit
def test_the_densify_step_is_100_m_along_a_meridian_and_no_more_in_any_direction():
    for lat_top in (-30.0, 0.0, 40.0):
        grid = _window(lat_top, rows=3000)
        step = densify_step_deg(grid)
        lat = np.linspace(grid.transform.f + grid.transform.e * grid.height, grid.transform.f, 7)
        for d_lon, d_lat in ((step, 0.0), (0.0, step), (step / 2**0.5, step / 2**0.5)):
            metres = _WGS84.inv(np.full(7, 10.0), lat, np.full(7, 10.0 + d_lon), lat + d_lat)[2]
            assert metres.max() <= 100.001  # the Bowring series of core/geodesy.py is within 4e-7 of the geodesic
        north = _WGS84.inv(10.0, lat[3], 10.0, lat[3] + step)[2]
        assert north == pytest.approx(100.0, rel=0.01)


@pytest.mark.unit
def test_the_distance_agrees_with_a_brute_force_geodesic_on_a_sample_of_pixels():
    grid = _window(-12.0, rows=120, cols=150)
    rng = np.random.default_rng(115)
    lon_t = grid.transform.c + rng.uniform(0.0, grid.width * _RES, 40)
    lat_t = grid.transform.f + rng.uniform(-grid.height * _RES, 0.0, 40)
    lon_c, lat_c = _centres(grid)
    pick = rng.choice(lon_c.size, 600, replace=False)
    plon, plat = lon_c.ravel()[pick], lat_c.ravel()[pick]
    brute = np.array(
        [_WGS84.inv(np.full(40, x), np.full(40, y), lon_t, lat_t)[2].min() / 1000.0 for x, y in zip(plon, plat, strict=True)]
    )

    got = geodesic_distance_to_vertices(lon_t, lat_t, grid, strip_rows=17).ravel()[pick]

    np.testing.assert_allclose(got.astype("float64"), brute, rtol=1e-6, atol=1e-6)


@pytest.mark.unit
def test_the_strips_of_an_interrupted_run_are_taken_from_the_checkpoint_and_give_the_same_raster(tmp_path):
    grid = _window(5.0, rows=40, cols=30)
    lon_t, lat_t = np.array([10.05, 10.2]), np.array([4.9, 4.7])
    first = geodesic_distance_to_vertices(lon_t, lat_t, grid, checkpoint_dir=tmp_path / "ck", checkpoint_key="k", strip_rows=8)
    assert len(list((tmp_path / "ck").glob("strip_*.npz"))) == 5
    with patch("geofrea.grid_alignment.vector_alignment.cKDTree", side_effect=AssertionError("the tree is built although every strip is stored")):
        again = geodesic_distance_to_vertices(lon_t, lat_t, grid, checkpoint_dir=tmp_path / "ck", checkpoint_key="k", strip_rows=8)
    np.testing.assert_array_equal(first, again)
    # other points (another computation) drop the stored strips
    other = geodesic_distance_to_vertices(lon_t + 0.01, lat_t, grid, checkpoint_dir=tmp_path / "ck", checkpoint_key="k", strip_rows=8)
    assert not np.array_equal(first, other)


@pytest.mark.unit
def test_the_vertices_of_a_layer_are_the_same_whatever_the_size_of_the_chunk(monkeypatch):
    from geofrea.grid_alignment import vector_alignment as va

    grid = _grid()
    rng = np.random.default_rng(5)
    lines = [LineString(rng.uniform([-0.15, -0.15], [0.15, 0.15], (4, 2))) for _ in range(60)]
    series = gpd.GeoSeries(lines, crs="EPSG:4326")
    whole = feature_vertices(series, grid, within_country=False)
    monkeypatch.setattr(va, "_FEATURE_CHUNK", 7)
    chunked = feature_vertices(series, grid, within_country=False)
    np.testing.assert_array_equal(whole[0], chunked[0])
    np.testing.assert_array_equal(whole[1], chunked[1])
    assert len(whole[0]) > 60 * 4


@pytest.mark.unit
def test_a_vertex_counts_only_when_the_pixel_that_holds_it_is_in_the_country_mask():
    grid = _grid()
    inside, corner_outside = Point(0.0, 0.0), Point(0.19, 0.19)  # the diamond leaves the corners of its bounding box empty
    off_grid = Point(5.0, 5.0)
    series = gpd.GeoSeries([inside, corner_outside, off_grid], crs="EPSG:4326")
    kept_country = feature_vertices(series, grid, within_country=True)
    kept_grid = feature_vertices(series, grid, within_country=False)
    assert list(zip(kept_country[0], kept_country[1], strict=True)) == [(0.0, 0.0)]
    assert list(zip(kept_grid[0], kept_grid[1], strict=True)) == [(0.0, 0.0), (0.19, 0.19)]


@pytest.mark.unit
def test_the_substations_of_a_layer_are_the_points_whose_pixel_is_in_the_country_and_their_count_does_not_change():
    from geofrea.grid_alignment.poi import select_poi

    grid = _grid()
    frame = gpd.GeoDataFrame(
        {
            "power": ["substation"] * 4,
            "voltage": ["220000", "220000", "220000", "10000"],
            "geometry": [Point(0.0, 0.0), Point(0.05, 0.02), Point(0.19, 0.19), Point(0.01, 0.01)],
        },
        crs="EPSG:4326",
    )
    points, counts = select_poi(frame, 110.0, 50.0)
    assert counts.eligible == 3 and len(points) == 3  # selection and counts are those of select_poi: this change does not touch them
    lon, lat = feature_vertices(points.geometry, grid, within_country=True)
    assert len(lon) == 2  # the one in the empty corner of the bounding box is not a point of the layer, as its burnt pixel was not before
    got = geodesic_distance_to_vertices(lon, lat, grid)
    lon_c, lat_c = _centres(grid)
    expected = (
        np.minimum(
            _WGS84.inv(lon_c, lat_c, np.full(lon_c.shape, 0.0), np.full(lon_c.shape, 0.0))[2],
            _WGS84.inv(lon_c, lat_c, np.full(lon_c.shape, 0.05), np.full(lon_c.shape, 0.02))[2],
        )
        / 1000.0
    )
    np.testing.assert_allclose(got[grid.country_mask].astype("float64"), expected[grid.country_mask], rtol=1e-6, atol=1e-6)


# -- blocks of vertices (COMMAND 117): one tree alive at a time, the same result ------------------------------------


def _brute_km(lon_c, lat_c, lon_t, lat_t) -> np.ndarray:
    """The geodesic from every pixel centre to every target, the minimum, by `pyproj.Geod` alone."""
    n = len(lon_t)
    out = np.empty(lon_c.shape)
    for idx in np.ndindex(lon_c.shape):
        out[idx] = _WGS84.inv(np.full(n, lon_c[idx]), np.full(n, lat_c[idx]), lon_t, lat_t)[2].min()
    return out / 1000.0


class _CountingTree:
    """A cKDTree that counts how many are built and the most vertices one holds."""

    built = 0
    largest = 0

    def __new__(cls, data, *args, **kwargs):
        from scipy.spatial import cKDTree

        cls.built += 1
        cls.largest = max(cls.largest, len(data))
        return cKDTree(data, *args, **kwargs)


@pytest.mark.unit
def test_the_distance_in_blocks_equals_the_distance_with_one_block_on_lines_with_many_vertices():
    grid = _window(-8.0, rows=40, cols=50)
    rng = np.random.default_rng(117)
    lines = [LineString(rng.uniform([10.0, -8.4], [10.5, -8.0], (5, 2))) for _ in range(40)]
    lon, lat = feature_vertices(gpd.GeoSeries(lines, crs="EPSG:4326"), grid, within_country=False)
    assert len(lon) > 1500

    one = geodesic_distance_to_vertices(lon, lat, grid, block_vertices=10**9)
    for block in (len(lon) // 2, 400, 97):
        blocks = geodesic_distance_to_vertices(lon, lat, grid, block_vertices=block, strip_rows=13)
        np.testing.assert_allclose(blocks.astype("float64"), one.astype("float64"), rtol=1e-9, atol=0.0)
        np.testing.assert_array_equal(np.isnan(blocks), np.isnan(one))


@pytest.mark.unit
def test_the_nearest_vertex_may_be_in_a_block_that_is_not_the_first():
    grid = _window(10.5, rows=20, cols=20)
    lon_c, lat_c = _centres(grid)
    # 40 vertices, blocks of 10: every vertex is far to the north-west of the window except number 35 (the fourth block), which is next to a pixel
    lon = np.full(40, 9.0) + np.arange(40) * 1e-3
    lat = np.full(40, 11.5)
    target = (7, 12)
    lon[35], lat[35] = lon_c[target] + 0.002, lat_c[target] - 0.001
    _CountingTree.built = 0
    with patch("geofrea.grid_alignment.vector_alignment.cKDTree", _CountingTree):
        got = geodesic_distance_to_vertices(lon, lat, grid, block_vertices=10)
    assert _CountingTree.built == 5 and _CountingTree.largest == 10  # four blocks and the tree of the seeds (every 32nd vertex: 0 and 32)
    expected = _WGS84.inv(lon_c[target], lat_c[target], lon[35], lat[35])[2] / 1000.0
    assert got[target] == pytest.approx(expected, rel=1e-6)
    # a pixel whose nearest vertex is in the first block still takes it, and the whole raster is the brute force
    brute = _brute_km(lon_c, lat_c, lon, lat)
    np.testing.assert_allclose(got.astype("float64"), brute, rtol=1e-6, atol=1e-6)


@pytest.mark.unit
def test_with_the_default_limit_the_layers_of_the_three_countries_are_one_block_and_do_not_change():
    from geofrea.grid_alignment import vector_alignment as va

    # the largest layer that is not the rivers has 5.8 million distinct vertices (IND roads, COMMAND 117): one block
    assert va._BLOCK_VERTICES >= 5_800_000
    grid = _window(-12.0, rows=60, cols=80)
    rng = np.random.default_rng(115)
    lon_t = grid.transform.c + rng.uniform(0.0, grid.width * _RES, 25)
    lat_t = grid.transform.f + rng.uniform(-grid.height * _RES, 0.0, 25)
    _CountingTree.built = 0
    with patch("geofrea.grid_alignment.vector_alignment.cKDTree", _CountingTree):
        default = geodesic_distance_to_vertices(lon_t, lat_t, grid)
    assert _CountingTree.built == 1
    lon_c, lat_c = _centres(grid)
    brute = _brute_km(lon_c, lat_c, lon_t, lat_t)
    np.testing.assert_allclose(default.astype("float64"), brute, rtol=1e-6, atol=1e-6)  # the COMMAND 115 test on the same data


@pytest.mark.unit
def test_exactly_equal_vertices_are_one_target_and_no_distinct_vertex_is_dropped():
    grid = _grid()
    first = LineString([(0.0, 0.0), (0.05, 0.0)])
    second = LineString([(0.05, 0.0), (0.05, 0.05)])  # shares its first vertex with the end of `first`
    lon, lat = feature_vertices(gpd.GeoSeries([first, second], crs="EPSG:4326"), grid, within_country=False)
    pairs = list(zip(lon, lat, strict=True))
    assert len(pairs) == len(set(pairs))
    assert (0.05, 0.0) in pairs and (0.0, 0.0) in pairs and (0.05, 0.05) in pairs
    step = densify_step_deg(grid)
    expected_distinct = len(set(map(tuple, np.round(shapely_coords([first, second], step), 12))))
    assert len(pairs) == expected_distinct


def shapely_coords(lines, step):
    import shapely

    return shapely.get_coordinates(shapely.segmentize(np.array(lines, dtype=object), step))


@pytest.mark.unit
def test_the_state_after_each_block_is_checkpointed_and_a_finished_run_builds_no_tree(tmp_path):
    grid = _window(5.0, rows=30, cols=30)
    rng = np.random.default_rng(3)
    lon_t = 10.0 + rng.uniform(0.0, 0.3, 50)
    lat_t = 5.0 - rng.uniform(0.0, 0.3, 50)
    first = geodesic_distance_to_vertices(lon_t, lat_t, grid, checkpoint_dir=tmp_path / "ck", checkpoint_key="k", block_vertices=12)
    with patch("geofrea.grid_alignment.vector_alignment.cKDTree", side_effect=AssertionError("a tree was built after the last block")):
        again = geodesic_distance_to_vertices(lon_t, lat_t, grid, checkpoint_dir=tmp_path / "ck", checkpoint_key="k", block_vertices=12)
    np.testing.assert_array_equal(first, again)
    np.testing.assert_allclose(
        first.astype("float64"), geodesic_distance_to_vertices(lon_t, lat_t, grid, block_vertices=10**9).astype("float64"), rtol=1e-9
    )
