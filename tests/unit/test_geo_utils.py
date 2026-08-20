"""Unit tests for geofrea.core.geo_utils."""

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from geofrea.core.geo_utils import detect_island_nation, get_local_utm_crs, get_mainland_gdf


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
