"""Unit tests for geofrea.grid_alignment.reference_grid."""

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Polygon

from geofrea.grid_alignment.reference_grid import GridContext, build_reference_grid


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
def test_build_reference_grid_snaps_bounds_to_resolution_multiples():
    # A deliberately "off-grid" bbox — bounds must be floor/ceil-snapped
    # to multiples of resolution_deg, not used raw.
    country_gdf = gpd.GeoDataFrame(
        geometry=[Polygon([(0.03, 0.07), (1.02, 0.07), (1.02, 1.01), (0.03, 1.01)])],
        crs="EPSG:4326",
    )
    grid = build_reference_grid(country_gdf, resolution_deg=0.1)

    assert grid.transform.c == pytest.approx(0.0)  # floor(0.03/0.1)*0.1
    assert grid.transform.f == pytest.approx(1.1)  # ceil(1.01/0.1)*0.1
    assert grid.width == 11  # (1.1 - 0.0) / 0.1
    assert grid.height == 11  # (1.1 - 0.0) / 0.1
    assert grid.crs == "EPSG:4326"


@pytest.mark.unit
def test_build_reference_grid_country_mask_matches_geometry_not_bbox():
    # A diamond (rotated square): its bounding box is inherently larger
    # than its own footprint (the four corners of the bbox fall outside
    # the diamond), regardless of resolution-snapping — unlike an
    # axis-aligned square whose bounds can snap to an exact rectangle
    # with no fringe at all.
    diamond = Polygon([(0.3, 0.0), (0.0, 0.3), (-0.3, 0.0), (0.0, -0.3)])
    country_gdf = gpd.GeoDataFrame(geometry=[diamond], crs="EPSG:4326")
    grid = build_reference_grid(country_gdf, resolution_deg=0.1)

    assert isinstance(grid, GridContext)
    assert grid.country_mask.dtype == bool
    # Not every pixel in the (rectangular) grid is inside a square
    # polygon's mask unless the polygon exactly fills the bbox — here
    # bounds snapping adds a fringe of False pixels around the edges.
    assert grid.country_mask.sum() < grid.country_mask.size
    assert grid.country_mask.any()


@pytest.mark.unit
def test_build_reference_grid_multi_polygon_masks_the_union():
    mainland = _square(0.0, 0.0, 0.3)
    exclave = _square(3.0, 3.0, 0.1)
    country_gdf = gpd.GeoDataFrame(geometry=[mainland, exclave], crs="EPSG:4326")

    grid = build_reference_grid(country_gdf, resolution_deg=0.1)

    # Grid extent must cover both polygons' combined bounds.
    minx, _miny, _maxx, maxy = country_gdf.total_bounds
    assert grid.transform.c <= minx
    assert grid.transform.f >= maxy
    assert grid.country_mask.sum() > 0
    # Two disjoint True regions expected — a coarse check that both
    # polygons contributed pixels, not just the first.
    row_has_true = grid.country_mask.any(axis=1)
    true_row_indices = np.where(row_has_true)[0]
    assert true_row_indices.max() - true_row_indices.min() > 5
