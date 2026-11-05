"""Sub-pixel excluded shares for vector exclusions (E1 protected areas, E2 lakes, E3 river corridors, E6 settlement setbacks; OQ-045 option c).

At 0.01 degree (about 1.1 km) a vector exclusion cannot be decided pixel by pixel: a corridor or a setback below the pixel size would
exclude "the pixels that contain a river" (a third of the land in PRT, IND and BRA). Here each pixel is split into
`factor` x `factor` sub-pixels (default 10 x 10, about 110 m), the vector is rasterized or measured on that finer grid, and the
share of sub-pixels excluded becomes the pixel's excluded fraction in [0, 1].

The work is done in strips of coarse rows so memory stays bounded (BRA is about 4,300 pixels wide, 43,000 sub-pixels).
Distances are geodesic: the sub-pixel size in km is taken at the strip's mid latitude (the error over one strip of
0.4 degree of latitude is far below the sub-pixel size).

E3 (Group 6, `eq:g6_width`): each river reach is excluded within `W/2 + B_c(W)` of its centre line, `W = a Q^b` from the mean discharge of the reach.
E6: the 0.01 degree settlement mask (GHS-SMOD) and its geodesic setback.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import rasterio
import shapely
from rasterio.features import rasterize
from scipy.ndimage import distance_transform_edt
from shapely.geometry import box

from geofrea.core.geodesy import wgs84_km_per_degree

DEFAULT_FACTOR = 10
DEFAULT_STRIP_ROWS = 40
# The sampling points of the sub-pixel grid are moved this far (degrees) east, and 0.618 times as far south. A source whose vertices lie on the
# sub-pixel lattice (the WDPA file of IND: 96% of the vertices have three decimals, the sub-pixel is 0.001 degree) has diagonal edges that run
# exactly through sub-pixel centres, and whether such a centre is inside was decided by rounding noise in the origin of the grid: the same
# polygons gave other shares on a grid with another origin (COMMAND 58: 20,691 of 53,633 protected cells of IND changed between two grids of the
# same country, none in PRT or BRA). A shift much larger than the noise (1e-13) and much smaller than the sub-pixel (1e-7 is 1e-4 of it) decides
# those centres by geometry, the same on every grid. The two shifts differ, by an irrational ratio: with equal shifts an edge of slope -1 would
# keep the centres on it (the edge moves as much as the centre), and so would any edge whose slope is the ratio of the shifts.
TIE_BREAK_DEG = 1e-7
TIE_BREAK_SOUTH_RATIO = 0.6180339887498949
# The distance transform of a strip is taken in blocks of this many sub-pixel columns, each with a margin of the setback in columns on both sides
# (COMMAND 91: the transform of a whole BRA strip, 17 M sub-pixels, held 1 GB). A sub-pixel is excluded when a river lies within the largest setback,
# and any such river is inside the margin, so `dist <= t` is the same as on the whole strip; a pixel whose nearest river is farther than the margin
# is farther than every setback in both. A multiple of `DEFAULT_FACTOR`, so that a block holds whole pixels.
RIVER_BLOCK_SUBCOLUMNS = 8000
# A distance from the centre of a sub-pixel to the nearest settlement sub-pixel centre overstates the distance from its edge by half a sub-pixel: the
# setback of a settlement mask is taken from the edge of the mask pixels (`mask_setback_fractions`), as this fraction of the smaller sub-pixel side.
HALF_SUBPIXEL = 0.5


def _block_mean(a: np.ndarray, k: int) -> np.ndarray:
    h, w = a.shape
    return a.reshape(h // k, k, w // k, k).mean(axis=(1, 3), dtype=np.float32)


def _strip_geoms(
    gdf: gpd.GeoDataFrame,
    transform: rasterio.Affine,
    row0: int,
    row1: int,
    width: int,
    pad_deg: float,
):
    """Geometries that can touch the strip [row0, row1) (plus a pad), through the spatial index."""
    window = _strip_window(transform, row0, row1, width, pad_deg)
    return gdf.geometry.iloc[list(gdf.sindex.query(window, predicate="intersects"))]


def _fine_transform(
    transform: rasterio.Affine, factor: int, row_off: int, tie_break_deg: float = TIE_BREAK_DEG
) -> rasterio.Affine:
    return rasterio.Affine(
        transform.a / factor,
        0.0,
        transform.c + tie_break_deg,
        0.0,
        transform.e / factor,
        transform.f + row_off * transform.e - tie_break_deg * TIE_BREAK_SOUTH_RATIO,
    )


def _anchored_strips(
    transform: rasterio.Affine, height: int, strip_rows: int
) -> list[tuple[int, int, int]]:
    """Strips of rows `(r0, r1, k0)` whose boundaries lie on multiples of `strip_rows` of the absolute row index (rows counted from 90 degrees north).

    `k0` is the absolute index of the first row of the whole strip, also for the first and the last strip, which can be partial. The strips
    of a pixel therefore do not depend on where the grid of the country begins (the mask), and a quantity taken at the middle of a strip is
    the same for the same pixel on any grid of the same lattice.
    """
    pixel = abs(transform.e)
    top = round((90.0 - transform.f) / pixel)
    strips = []
    r = 0
    while r < height:
        k = top + r
        k0 = (k // strip_rows) * strip_rows
        r1 = min(r + (k0 + strip_rows - k), height)
        strips.append((r, r1, k0))
        r = r1
    return strips


def polygon_coverage_fraction(
    gdf: gpd.GeoDataFrame | None,
    transform: rasterio.Affine,
    shape: tuple[int, int],
    factor: int = DEFAULT_FACTOR,
    strip_rows: int = DEFAULT_STRIP_ROWS,
    tie_break_deg: float = TIE_BREAK_DEG,
) -> np.ndarray:
    """Share of each pixel covered by the polygons of `gdf` (float32 in [0, 1]); zeros when `gdf` is None or empty."""
    height, width = shape
    out = np.zeros(shape, dtype=np.float32)
    if gdf is None or len(gdf) == 0:
        return out
    gdf = gdf.reset_index(drop=True)
    for r0, r1, _ in _anchored_strips(transform, height, strip_rows):
        geoms = _strip_geoms(gdf, transform, r0, r1, width, pad_deg=0.0)
        if len(geoms) == 0:
            continue
        fine = rasterize(
            [(g, 1) for g in geoms if g is not None and not g.is_empty],
            out_shape=((r1 - r0) * factor, width * factor),
            transform=_fine_transform(transform, factor, r0, tie_break_deg),
            fill=0,
            all_touched=False,
            dtype=np.uint8,
        )
        out[r0:r1] = _block_mean(fine.astype(np.float32), factor)
    return out


def buffer_m(steps, width_m):
    """B_c(W): the buffer beyond the channel edge for an estimated width (scalar or array), from the steps `(below_width_m or None, buffer_m)`.

    A reach narrower than `below_width_m` of the first step that holds gets its buffer; the last step (`None`) takes every wider reach. The classes
    are half-open: W = 10 m is in the class of 10 to 50 m, not of less than 10 m.
    """
    w = np.asarray(width_m, dtype="float64")
    out = np.full(w.shape, float(steps[-1][1]), dtype="float64")
    for below, value in reversed(list(steps)[:-1]):
        out = np.where(w < below, float(value), out)
    return out


def river_widths_m(
    discharge_m3s, coefficient: float, exponent: float, exponent_range: tuple[float, float] | None = None
) -> np.ndarray:
    """Channel width `W = a Q^b` (m) from the long-term mean discharge Q (m3/s) of each reach (eq:g6_width).

    With `exponent_range = (b_low, b_high)` the width of each reach is taken at the extreme of the range: an `exponent` equal to `b_low` gives
    `a min(Q^b_low, Q^b_high)` and one equal to `b_high` gives `a max(Q^b_low, Q^b_high)`. Q^b falls as b grows for Q < 1 m3/s and rises for Q > 1, so
    the extremes (not the extreme exponents) make the narrow, central and wide channels nested on every reach. An exponent inside the range is used as is.

    Raises:
        ValueError: a discharge is missing or negative (A-09: never read a missing discharge as a small river).
    """
    q = np.asarray(discharge_m3s, dtype="float64")
    if not np.isfinite(q).all() or (q < 0).any():
        raise ValueError("river discharge must be finite and non-negative for every reach")
    a = float(coefficient)
    if exponent_range is not None:
        low, high = (float(b) for b in exponent_range)
        if float(exponent) == low or float(exponent) == high:
            pick = np.minimum if float(exponent) == min(low, high) else np.maximum
            return a * pick(np.power(q, low), np.power(q, high))
    return a * np.power(q, float(exponent))


def corridor_half_widths_m(
    discharge_m3s, coefficient: float, exponent: float, steps, exponent_range: tuple[float, float] | None = None
) -> np.ndarray:
    """Half-width of the excluded corridor of each reach, `W/2 + B_c(W)` (m)."""
    w = river_widths_m(discharge_m3s, coefficient, exponent, exponent_range)
    return w / 2.0 + buffer_m(steps, w)


def river_corridor_fraction(
    lines: gpd.GeoDataFrame | None,
    half_width_m,
    transform: rasterio.Affine,
    shape: tuple[int, int],
    factor: int = DEFAULT_FACTOR,
    strip_rows: int = DEFAULT_STRIP_ROWS,
    tie_break_deg: float = TIE_BREAK_DEG,
) -> np.ndarray:
    """Share of each pixel inside the union of the river corridors: every reach buffered by its own half-width (m) around its centre line (E3).

    The buffer is taken in a local metric frame of the strip (degrees of longitude scaled by the km-per-degree ratio at the middle of the strip, on the
    absolute lattice as `_anchored_strips`), then burnt on 10 x 10 sub-pixels by the centre of each sub-pixel with the same tie-break as the polygons
    (`polygon_coverage_fraction`). Corridors that overlap are burnt once, so the union is not summed. A reach narrower than a sub-pixel (about 110 m) is
    represented by the sub-pixels whose centre it covers: unbiased on average, noisy within a pixel.

    Args:
        lines: The reaches (any geometry that buffers), one row each; `None` or empty gives zeros.
        half_width_m: Half-width of the corridor of each row of `lines`, in metres.
    """
    height, width = shape
    out = np.zeros(shape, dtype=np.float32)
    if lines is None or len(lines) == 0:
        return out
    lines = lines.reset_index(drop=True)
    half = np.asarray(half_width_m, dtype="float64")
    if half.shape != (len(lines),):
        raise ValueError(f"{len(half)} half-widths for {len(lines)} reaches")
    geometry = lines.geometry.to_numpy()
    for r0, r1, k0 in _anchored_strips(transform, height, strip_rows):
        lat_mid = 90.0 - (k0 + 0.5 * strip_rows) * abs(transform.e)
        lat_km, lon_km = wgs84_km_per_degree(np.array([lat_mid]))
        m_lat, m_lon = float(lat_km[0]) * 1000.0, float(lon_km[0]) * 1000.0
        pad_deg = float(half.max()) / min(m_lat, m_lon) + 1e-6
        window = _strip_window(transform, r0, r1, width, pad_deg)
        idx = np.asarray(lines.sindex.query(window, predicate="intersects"))
        if idx.size == 0:
            continue
        ratio = m_lon / m_lat  # x in units of latitude degrees: metres are then equal in both axes
        scaled = shapely.transform(geometry[idx], lambda c, k=ratio: c * np.array([k, 1.0]))
        buffered = shapely.buffer(scaled, half[idx] / m_lat, quad_segs=4)
        back = shapely.transform(buffered, lambda c, k=ratio: c * np.array([1.0 / k, 1.0]))
        fine = rasterize(
            [(g, 1) for g in back if g is not None and not g.is_empty],
            out_shape=((r1 - r0) * factor, width * factor),
            transform=_fine_transform(transform, factor, r0, tie_break_deg),
            fill=0,
            all_touched=False,
            dtype=np.uint8,
        )
        out[r0:r1] = _block_mean(fine.astype(np.float32), factor)
    return out


def _strip_window(transform: rasterio.Affine, row0: int, row1: int, width: int, pad_deg: float):
    """The box of the strip [row0, row1) padded by `pad_deg`."""
    top = transform.f + row0 * transform.e
    bottom = transform.f + row1 * transform.e
    return box(
        transform.c - pad_deg,
        min(top, bottom) - pad_deg,
        transform.c + width * transform.a + pad_deg,
        max(top, bottom) + pad_deg,
    )


def mask_setback_fractions(
    mask: np.ndarray | None,
    transform: rasterio.Affine,
    shape: tuple[int, int],
    setbacks_m: list[float],
    factor: int = DEFAULT_FACTOR,
    strip_rows: int = DEFAULT_STRIP_ROWS,
    block_subcolumns: int = RIVER_BLOCK_SUBCOLUMNS,
) -> dict[float, np.ndarray]:
    """For each setback in `setbacks_m`, the share of each pixel within that geodesic distance of the True pixels of `mask` (settlements, E6).

    The mask pixels are split into `factor` x `factor` sub-pixels, the distance from each sub-pixel to the nearest True one is measured (geodesic, with the
    km per degree at the middle of the strip, anchored on the absolute lattice) and the share of sub-pixels within the setback becomes the pixel's excluded
    fraction. The distance is measured from sub-pixel centres, so `HALF_SUBPIXEL` (half the smaller side of a sub-pixel) is added to the setback: the
    setback runs from the edge of the settlement pixels, and a setback of 0 excludes the settlement pixels and nothing else.
    """
    height = shape[0]
    out = {float(t): np.zeros(shape, dtype=np.float32) for t in setbacks_m}
    if mask is None or not mask.any() or not setbacks_m:
        return out
    mask = np.asarray(mask, dtype=bool)
    sub_deg = abs(transform.a) / factor
    max_m = max(float(t) for t in setbacks_m)
    for r0, r1, k0 in _anchored_strips(transform, height, strip_rows):
        lat_mid = 90.0 - (k0 + 0.5 * strip_rows) * abs(transform.e)
        lat_km, lon_km = wgs84_km_per_degree(np.array([lat_mid]))
        dy_m, dx_m = sub_deg * float(lat_km[0]) * 1000.0, sub_deg * float(lon_km[0]) * 1000.0
        edge_m = HALF_SUBPIXEL * min(dy_m, dx_m)
        pad_coarse = int(np.ceil((int(np.ceil((max_m + edge_m) / dy_m)) + 2) / factor))
        p0, p1 = max(0, r0 - pad_coarse), min(height, r1 + pad_coarse)
        if not mask[p0:p1].any():
            continue
        fine = np.repeat(np.repeat(mask[p0:p1], factor, axis=0), factor, axis=1)
        inner = slice((r0 - p0) * factor, (r1 - p0) * factor)
        n_sub = fine.shape[1]
        halo = int(np.ceil((max_m + edge_m) / dx_m)) + 2
        block = max(factor, (block_subcolumns // factor) * factor)
        for c0 in range(0, n_sub, block):
            c1 = min(c0 + block, n_sub)
            a, b = max(0, c0 - halo), min(n_sub, c1 + halo)
            if not fine[:, a:b].any():
                continue
            dist = distance_transform_edt(~fine[:, a:b], sampling=(dy_m, dx_m))[inner, c0 - a : c1 - a]
            for t, share in out.items():
                share[r0:r1, c0 // factor : c1 // factor] = _block_mean((dist <= t + edge_m).astype(np.float32), factor)
    return out