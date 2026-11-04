"""Unit tests for geofrea.grid_alignment.poi: voltage parsing, inference from lines, threshold filter, counts (COMMAND 83, M-F2a-09)."""

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point, Polygon

from geofrea.grid_alignment.poi import PoiError, parse_voltage_kv, select_poi


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("220000", 220.0),  # volts to kV
        ("138000;69000", 138.0),  # a list takes the largest
        ("69000;138000", 138.0),
        ("138000_69000_23000", 138.0),
        ("132000/133000", 133.0),
        ("0;400000", 400.0),  # a zero entry is ignored
        ("500 kV", 500.0),  # an explicit unit
        ("345kV", 345.0),
        ("66000.5", 66.0005),
        ("220", None),  # bare value below 1000: the unit would be a guess
        ("600", None),
        ("0", None),
        ("yes", None),  # text is absent
        ("", None),
        (None, None),
        (float("nan"), None),
        ("high", None),
        ("220000;high", 220.0),  # a text token beside a number is ignored
    ],
)
def test_parse_voltage_kv(raw, expected):
    got = parse_voltage_kv(raw)
    if expected is None:
        assert got is None
    else:
        assert got == pytest.approx(expected)


def _grid(substations, lines):
    rows = [{"power": "substation", "voltage": v, "geometry": g} for v, g in substations]
    rows += [{"power": "line", "voltage": v, "geometry": g} for v, g in lines]
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


@pytest.mark.unit
def test_threshold_filters_tagged_substations_and_counts_each_outcome():
    grid = _grid(
        [
            ("230000", Point(0.0, 0.0)),  # eligible, tagged
            ("138000", Point(1.0, 0.0)),  # exactly at the threshold: eligible
            ("69000", Point(2.0, 0.0)),  # below
            (None, Point(3.0, 0.0)),  # no tag, no line: excluded
        ],
        [],
    )
    poi, counts = select_poi(grid, threshold_kv=138.0, tolerance_m=50.0)
    assert sorted(poi["voltage_kv"]) == [138.0, 230.0]
    assert set(poi["voltage_source"]) == {"tag"}
    assert counts.as_dict() == {
        "total": 4,
        "with_tag": 3,
        "inferred": 0,
        "excluded_no_voltage": 1,
        "below_threshold": 1,
        "eligible": 2,
        "nodes": 4,
        "polygons": 0,
        "duplicates_removed": 0,
    }


@pytest.mark.unit
def test_substation_without_a_tag_takes_the_highest_voltage_of_the_lines_that_touch_it():
    grid = _grid(
        [(None, Point(10.0, 10.0))],
        [
            ("69000", LineString([(10.0, 10.0), (11.0, 10.0)])),  # touches
            ("230000;138000", LineString([(9.0, 10.0), (10.0, 10.0)])),  # touches, higher
            ("500000", LineString([(20.0, 20.0), (21.0, 20.0)])),  # far away: ignored
        ],
    )
    poi, counts = select_poi(grid, threshold_kv=138.0, tolerance_m=50.0)
    assert list(poi["voltage_kv"]) == [230.0]
    assert list(poi["voltage_source"]) == ["inferred"]
    assert counts.inferred == 1 and counts.with_tag == 0 and counts.eligible == 1


@pytest.mark.unit
def test_inference_honors_the_declared_tolerance():
    # about 30 m east of the line end at the equator (0.00027 degree)
    grid = _grid(
        [(None, Point(0.00027, 0.0))], [("230000", LineString([(-1.0, 0.0), (0.0, 0.0)]))]
    )
    near, _ = select_poi(grid, threshold_kv=138.0, tolerance_m=50.0)
    far, counts = select_poi(grid, threshold_kv=138.0, tolerance_m=10.0)
    assert len(near) == 1
    assert len(far) == 0 and counts.excluded_no_voltage == 1


@pytest.mark.unit
def test_untagged_lines_do_not_give_a_voltage():
    grid = _grid([(None, Point(0.0, 0.0))], [(None, LineString([(0.0, 0.0), (1.0, 0.0)]))])
    poi, counts = select_poi(grid, threshold_kv=138.0, tolerance_m=50.0)
    assert len(poi) == 0 and counts.excluded_no_voltage == 1 and counts.inferred == 0


@pytest.mark.unit
def test_a_polygon_substation_is_represented_by_a_point_inside_it():
    square = Polygon([(0, 0), (0.002, 0), (0.002, 0.002), (0, 0.002)])
    grid = _grid([("230000", square)], [])
    poi, _ = select_poi(grid, threshold_kv=138.0, tolerance_m=50.0)
    assert poi.geometry.iloc[0].geom_type == "Point"
    assert square.contains(poi.geometry.iloc[0])


@pytest.mark.unit
def test_lines_are_not_returned_as_points_and_a_bad_threshold_raises():
    grid = _grid([("230000", Point(0, 0))], [("230000", LineString([(0, 0), (1, 1)]))])
    poi, counts = select_poi(grid, threshold_kv=138.0, tolerance_m=50.0)
    assert counts.total == 1 and len(poi) == 1
    with pytest.raises(PoiError):
        select_poi(grid, threshold_kv=0.0, tolerance_m=50.0)


@pytest.mark.unit
def test_a_node_inside_a_polygon_is_dropped_and_the_polygon_kept_with_its_own_tag():
    square = Polygon([(0, 0), (0.002, 0), (0.002, 0.002), (0, 0.002)])
    grid = _grid(
        [
            ("230000", square),
            ("69000", Point(0.001, 0.001)),  # inside: the duplicate of the polygon, whatever its tag
            ("230000", Point(5.0, 5.0)),  # elsewhere: kept
        ],
        [],
    )
    poi, counts = select_poi(grid, threshold_kv=138.0, tolerance_m=50.0)
    assert (counts.total, counts.nodes, counts.polygons, counts.duplicates_removed) == (2, 1, 1, 1)
    assert counts.below_threshold == 0 and counts.eligible == 2 and len(poi) == 2


@pytest.mark.unit
def test_a_line_that_crosses_a_polygon_gives_it_a_voltage_even_when_the_point_is_far_from_the_line():
    # a 2 km wide polygon: the representative point is about 1 km from the line that crosses only its western edge
    big = Polygon([(0, 0), (0.02, 0), (0.02, 0.02), (0, 0.02)])
    crossing = LineString([(-0.01, 0.019), (0.0005, 0.019)])
    grid = _grid([(None, big)], [("230000", crossing)])
    poi, counts = select_poi(grid, threshold_kv=138.0, tolerance_m=50.0)
    assert list(poi["voltage_kv"]) == [230.0] and list(poi["voltage_source"]) == ["inferred"]
    assert counts.inferred == 1 and counts.polygons == 1
    # a line 1 km from the polygon edge does not reach it
    away = LineString([(-0.01, 0.01), (-0.009, 0.01)])
    far, far_counts = select_poi(_grid([(None, big)], [("230000", away)]), threshold_kv=138.0, tolerance_m=50.0)
    assert len(far) == 0 and far_counts.excluded_no_voltage == 1


@pytest.mark.unit
def test_the_sensitivity_threshold_gives_a_denser_layer_than_the_main_one():
    """`poi_sensitivity` (IND, 132 kV) is the same selection at a lower threshold: it keeps every substation of the main layer and adds the lower ones."""
    grid = _grid(
        [("230000", Point(0.0, 0.0)), ("132000", Point(1.0, 0.0)), ("69000", Point(2.0, 0.0))],
        [],
    )
    main, main_counts = select_poi(grid, threshold_kv=220.0, tolerance_m=50.0)
    sensitivity, sensitivity_counts = select_poi(grid, threshold_kv=132.0, tolerance_m=50.0)
    assert (main_counts.eligible, sensitivity_counts.eligible) == (1, 2)
    assert {g.wkt for g in main.geometry} <= {g.wkt for g in sensitivity.geometry}
