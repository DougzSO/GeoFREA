"""Synthetic countries and rasters for the examples of `docs/figures/style_guide.md` and for the tests of `mapstyle`.

Three invented shapes (not any real country): a tall one, a wide one and a small one, each an ellipse with a far island that the
extent must ignore, plus a smooth skewed field. Nothing here is a result.
"""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import numpy as np
from shapely import affinity
from shapely.geometry import Point, box

from geofrea.viz.mapstyle import Extent

# name: (centre lon, centre lat, half width deg, half height deg, rotation)
SHAPES = {
    "tall": (-70.0, -33.0, 3.0, 11.0, -18.0),
    "wide": (20.0, 5.0, 12.0, 3.5, 22.0),
    "small": (8.0, 47.0, 0.9, 0.6, 28.0),
}  # the last number turns the ellipse (degrees), so that two opposite corners of the map stay free


@dataclass(frozen=True)
class SyntheticCountry:
    name: str
    geometry: object  # mainland plus a far island, lon/lat
    mainland: object
    neighbours: gpd.GeoDataFrame
    grid: np.ndarray  # skewed positive field, NaN outside the mainland
    grid_extent: Extent


def synthetic_country(name: str, pixels: int = 220, seed: int = 56) -> SyntheticCountry:
    """The synthetic country `name` (`tall`, `wide` or `small`), with a neighbour on its eastern side and an island far out to sea."""
    lon, lat, hw, hh, turn = SHAPES[name]
    mainland = affinity.rotate(
        affinity.scale(Point(lon, lat).buffer(1.0, quad_segs=32), hw, hh), turn, origin=(lon, lat)
    )
    island = Point(lon - 4 * hw, lat - 3 * hh).buffer(0.1 * min(hw, hh))
    geometry = mainland.union(island)
    neighbour = box(lon + 0.85 * hw, lat - 1.6 * hh, lon + 3.2 * hw, lat + 1.6 * hh).difference(
        mainland.buffer(0.02 * hw)
    )
    neighbours = gpd.GeoDataFrame({"name": ["neighbour"]}, geometry=[neighbour], crs="EPSG:4326")
    w, s, e, n = mainland.bounds
    extent = (w, e, s, n)
    rng = np.random.default_rng(seed)
    ny = pixels
    nx = max(8, round(pixels * (e - w) / (n - s)))
    xs = w + (np.arange(nx) + 0.5) / nx * (e - w)
    ys = n - (np.arange(ny) + 0.5) / ny * (n - s)
    xx, yy = np.meshgrid(xs, ys)
    inside = _contains(mainland, xx, yy)
    field = np.exp(
        1.2 * np.sin(3 * (xx - lon) / hw) * np.cos(2 * (yy - lat) / hh)
        + 0.4 * rng.standard_normal(xx.shape)
    )
    field = field * (
        1
        + 4
        * np.exp(-(((xx - lon + 0.3 * hw) / (0.15 * hw)) ** 2 + ((yy - lat) / (0.15 * hh)) ** 2))
    )
    grid = np.where(inside, field, np.nan)
    return SyntheticCountry(name, geometry, mainland, neighbours, grid, extent)


def _contains(polygon, xx: np.ndarray, yy: np.ndarray) -> np.ndarray:
    import shapely

    return shapely.contains_xy(polygon, xx.ravel(), yy.ravel()).reshape(xx.shape)
