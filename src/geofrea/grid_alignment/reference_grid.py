"""Reference-grid construction for the grid_alignment phase.

Ported from geoworld_framework's src/processors/grid_aligner.py
(`GridContext`, `build_reference_grid()`, L64-134) with no logic
changes — see docs/DECISIONS.md 2026-09-08, grid_alignment Passo 3.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds as transform_from_bounds
from shapely.geometry import mapping

logger = logging.getLogger(__name__)


@dataclass
class GridContext:
    """The spatial reference grid every output layer is reprojected/masked to.

    Args:
        transform: Rasterio affine transform.
        width: Grid width, in pixels.
        height: Grid height, in pixels.
        crs: Coordinate reference system string.
        country_mask: Boolean array, True where a pixel is inside the
            country polygon (not just its bounding box).
    """

    transform: rasterio.Affine
    width: int
    height: int
    crs: str
    country_mask: np.ndarray


def _snap(value: float, step: float, *, up: bool) -> float:
    """Round `value` down/up to a multiple of `step`, tolerant to float noise (36.99999999 -> 37)."""
    q = value / step
    q = np.ceil(q - 1e-9) if up else np.floor(q + 1e-9)
    return float(q * step)


def build_reference_grid(
    country_gdf: gpd.GeoDataFrame, resolution_deg: float, nesting_pixels: int = 1
) -> GridContext:
    """Construct the master spatial reference grid from the country geometry.

    Bounds are snapped to multiples of `resolution_deg * nesting_pixels`, so every pixel
    aligns exactly on the grid and, with `nesting_pixels=5` (M-F2a-01), the grid holds a whole
    number of 0.05 degree cells (5 x 5 pixels each) whose edges sit on the global 0.05 degree
    lattice, regardless of the country's raw extent.

    Args:
        country_gdf: Country polygon(s) the grid is built to cover.
        resolution_deg: Grid resolution, in decimal degrees.
        nesting_pixels: Pixels per side of the coarser cell the grid must nest (1 = snap to the
            pixel only).

    Returns:
        GridContext with aligned transform, dimensions, and country mask.
    """
    minx, miny, maxx, maxy = country_gdf.total_bounds

    step = resolution_deg * nesting_pixels
    minx = _snap(minx, step, up=False)
    miny = _snap(miny, step, up=False)
    maxx = _snap(maxx, step, up=True)
    maxy = _snap(maxy, step, up=True)

    width = round((maxx - minx) / resolution_deg)
    height = round((maxy - miny) / resolution_deg)
    if width % nesting_pixels or height % nesting_pixels:
        raise AssertionError(
            f"grid {height}x{width} px is not a whole number of {nesting_pixels}x{nesting_pixels} cells"
        )
    crs = "EPSG:4326"
    transform = transform_from_bounds(minx, miny, maxx, maxy, width, height)

    logger.info(
        "  Grid extent: %dx%d px | res=%.4f deg | bounds=[%.3f, %.3f, %.3f, %.3f]",
        height,
        width,
        resolution_deg,
        minx,
        miny,
        maxx,
        maxy,
    )

    shapes = [(mapping(geom), 1) for geom in country_gdf.geometry]
    country_mask = rasterize(
        shapes,
        out_shape=(height, width),
        transform=transform,
        fill=0,
        dtype=np.uint8,
        all_touched=False,
    ).astype(bool)

    return GridContext(transform, width, height, crs, country_mask)
