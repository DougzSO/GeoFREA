"""Sub-pixel excluded shares for vector exclusions (E1 protected areas, E2 lakes, E3 riparian setback; OQ-045 option c).

At 0.01 degree (about 1.1 km) a vector exclusion cannot be decided pixel by pixel: any riparian setback below the pixel size
excludes "the pixels that contain a river" (a third of the land in PRT, IND and BRA). Here each pixel is split into
`factor` x `factor` sub-pixels (default 10 x 10, about 110 m), the vector is rasterized or measured on that finer grid, and the
share of sub-pixels excluded becomes the pixel's excluded fraction in [0, 1].

The work is done in strips of coarse rows so memory stays bounded (BRA is about 4,300 pixels wide, 43,000 sub-pixels).
Riparian distances are geodesic: the sub-pixel size in km is taken at the strip's mid latitude (the error over one strip of
0.4 degree of latitude is far below the sub-pixel size).
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from scipy.ndimage import distance_transform_edt
from shapely.geometry import box

from geofrea.core.geodesy import wgs84_km_per_degree

DEFAULT_FACTOR = 10
DEFAULT_STRIP_ROWS = 40


def _block_mean(a: np.ndarray, k: int) -> np.ndarray:
    h, w = a.shape
    return a.reshape(h // k, k, w // k, k).mean(axis=(1, 3), dtype=np.float32)


def _strip_geoms(gdf: gpd.GeoDataFrame, transform: rasterio.Affine, row0: int, row1: int, width: int, pad_deg: float):
    """Geometries that can touch the strip [row0, row1) (plus a pad), through the spatial index."""
    top = transform.f + row0 * transform.e
    bottom = transform.f + row1 * transform.e
    left = transform.c
    right = transform.c + width * transform.a
    window = box(left - pad_deg, min(top, bottom) - pad_deg, right + pad_deg, max(top, bottom) + pad_deg)
    return gdf.geometry.iloc[list(gdf.sindex.query(window, predicate="intersects"))]


def _fine_transform(transform: rasterio.Affine, factor: int, row_off: int) -> rasterio.Affine:
    return rasterio.Affine(
        transform.a / factor, 0.0, transform.c, 0.0, transform.e / factor, transform.f + row_off * transform.e
    )


def polygon_coverage_fraction(
    gdf: gpd.GeoDataFrame | None,
    transform: rasterio.Affine,
    shape: tuple[int, int],
    factor: int = DEFAULT_FACTOR,
    strip_rows: int = DEFAULT_STRIP_ROWS,
) -> np.ndarray:
    """Share of each pixel covered by the polygons of `gdf` (float32 in [0, 1]); zeros when `gdf` is None or empty."""
    height, width = shape
    out = np.zeros(shape, dtype=np.float32)
    if gdf is None or len(gdf) == 0:
        return out
    gdf = gdf.reset_index(drop=True)
    for r0 in range(0, height, strip_rows):
        r1 = min(r0 + strip_rows, height)
        geoms = _strip_geoms(gdf, transform, r0, r1, width, pad_deg=0.0)
        if len(geoms) == 0:
            continue
        fine = rasterize(
            [(g, 1) for g in geoms if g is not None and not g.is_empty],
            out_shape=((r1 - r0) * factor, width * factor),
            transform=_fine_transform(transform, factor, r0),
            fill=0,
            all_touched=False,
            dtype=np.uint8,
        )
        out[r0:r1] = _block_mean(fine.astype(np.float32), factor)
    return out


def river_setback_fractions(
    lines: gpd.GeoDataFrame | None,
    transform: rasterio.Affine,
    shape: tuple[int, int],
    thresholds_km: list[float],
    factor: int = DEFAULT_FACTOR,
    strip_rows: int = DEFAULT_STRIP_ROWS,
) -> dict[float, np.ndarray]:
    """For each setback in `thresholds_km`, the share of each pixel within that geodesic distance of a river line."""
    height, width = shape
    out = {t: np.zeros(shape, dtype=np.float32) for t in thresholds_km}
    if lines is None or len(lines) == 0 or not thresholds_km:
        return out
    lines = lines.reset_index(drop=True)
    sub_deg = abs(transform.a) / factor
    max_km = max(thresholds_km)
    for r0 in range(0, height, strip_rows):
        r1 = min(r0 + strip_rows, height)
        lat_mid = transform.f + 0.5 * (r0 + r1) * transform.e
        lat_km, lon_km = wgs84_km_per_degree(np.array([lat_mid]))
        dy_km, dx_km = sub_deg * float(lat_km[0]), sub_deg * float(lon_km[0])
        pad_rows = int(np.ceil(max_km / dy_km)) + 2  # sub-pixel rows of context above and below the strip
        pad_coarse = int(np.ceil(pad_rows / factor))
        p0, p1 = max(0, r0 - pad_coarse), min(height, r1 + pad_coarse)
        geoms = _strip_geoms(lines, transform, p0, p1, width, pad_deg=0.0)
        if len(geoms) == 0:
            continue
        river = rasterize(
            [(g, 1) for g in geoms if g is not None and not g.is_empty],
            out_shape=((p1 - p0) * factor, width * factor),
            transform=_fine_transform(transform, factor, p0),
            fill=0,
            all_touched=True,
            dtype=np.uint8,
        ).astype(bool)
        if not river.any():
            continue
        dist = distance_transform_edt(~river, sampling=(dy_km, dx_km))
        inner = slice((r0 - p0) * factor, (r1 - p0) * factor)
        for t in thresholds_km:
            out[t][r0:r1] = _block_mean((dist[inner] <= t).astype(np.float32), factor)
    return out
