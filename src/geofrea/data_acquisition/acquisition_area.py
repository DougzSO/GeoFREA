"""Area that an acquisition must cover: the bounding box of the country mask plus a margin (COMMAND 59).

The mask is the contiguous territory of M-F2a-01. A layer acquired by bounding box is requested for `acquisition_bbox(mask)`, never for a fixed
box and never for what a provider calls the country (a provider's country polygon is its own border: the Global Wind Atlas file of IND stopped at
33.3 N while the mask reaches 35.5 N, and the ERA5 files had been requested for the mask of before COMMAND 55). A product already on disk is
checked against the same box (`native_grid_covers`), and the rectangles that complete it are given by `missing_parts`.

Boxes are `(west, south, east, north)` in degrees, EPSG:4326.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import shapely
from scipy.ndimage import binary_dilation, label
from scipy.spatial import cKDTree
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

MARGIN_DEG = 0.5

Bbox = tuple[float, float, float, float]


def acquisition_bbox(mask_bounds: Sequence[float], margin_deg: float = MARGIN_DEG) -> Bbox:
    """Bounding box of the mask grown by `margin_deg` on every side (`mask_bounds` = minx, miny, maxx, maxy)."""
    west, south, east, north = (float(v) for v in mask_bounds)
    if not (west < east and south < north):
        raise ValueError(f"empty or inverted mask bounds {tuple(mask_bounds)}")
    if margin_deg < 0:
        raise ValueError("the margin cannot be negative")
    return (west - margin_deg, south - margin_deg, east + margin_deg, north + margin_deg)


def bbox_contains(outer: Sequence[float], inner: Sequence[float], tol_deg: float = 1e-9) -> bool:
    return bool(
        outer[0] <= inner[0] + tol_deg
        and outer[1] <= inner[1] + tol_deg
        and outer[2] >= inner[2] - tol_deg
        and outer[3] >= inner[3] - tol_deg
    )


def native_grid_extent(
    lat_min: float, lat_max: float, lat_res: float, lon_min: float, lon_max: float, lon_res: float
) -> Bbox:
    """Edges of a regular grid given by the centres of its first and last cells."""
    return (
        lon_min - lon_res / 2,
        lat_min - lat_res / 2,
        lon_max + lon_res / 2,
        lat_max + lat_res / 2,
    )


def native_grid_covers(
    extent: Sequence[float],
    mask_bounds: Sequence[float],
    native_res_deg: float,
    tol_cells: float = 1.0,
) -> bool:
    """True when a product on a native grid reaches the mask, to within `tol_cells` native cells on each side.

    A product cropped to the polygon keeps the cells whose centre lies inside it, so its extent can fall short of the mask box by up to one cell
    at a coast; a shortfall of more is a missing part of the territory.
    """
    return bbox_contains(extent, mask_bounds, tol_deg=tol_cells * native_res_deg)


def missing_parts(
    have: Sequence[float], need: Sequence[float], overlap_deg: float = 0.0
) -> list[Bbox]:
    """Rectangles that, added to `have`, cover `need`; each is grown by `overlap_deg` towards `have` so the seam has cells on both sides.

    North and south parts span the whole width of `need`; west and east parts span the height of `have` only (the corners are in the north and
    south parts). An empty list means `have` already contains `need`.
    """
    parts: list[Bbox] = []
    hw, hs, he, hn = have
    nw, ns, ne, nn = need
    if nn > hn:
        parts.append((nw, hn - overlap_deg, ne, nn))
    if ns < hs:
        parts.append((nw, ns, ne, hs + overlap_deg))
    south, north = max(hs, ns), min(hn, nn)
    if nw < hw and south < north:
        parts.append((nw, south, hw + overlap_deg, north))
    if ne > he and south < north:
        parts.append((he - overlap_deg, south, ne, north))
    return parts


def uncovered_boxes(
    mask: BaseGeometry,
    lat: np.ndarray,
    lon: np.ndarray,
    valid: np.ndarray,
    native_res_deg: float,
    margin_deg: float = MARGIN_DEG,
    overlap_deg: float = 0.0,
    tol_cells: float = 1.0,
    step_deg: float = 0.05,
) -> list[Bbox]:
    """Boxes to acquire so that a product reaches the mask: one per part of the mask with no valid native cell within `tol_cells` cells.

    `valid[i, j]` tells whether the native cell at (lat[i], lon[j]) holds a value. The mask is sampled every `step_deg`; a sample farther than
    `tol_cells` native cells from every valid cell is uncovered (a coast cell that the polygon crop dropped is within the tolerance and is not a
    missing territory). Uncovered samples that are neighbours form one part; each part's box is grown by the margin and by `overlap_deg`, so the
    cells of the polygon crop are whole and the seam has cells on both sides, and boxes that touch are merged. The mask is the geometry, not its
    box: the north block and the east end of IND are two small boxes, not the width of the country, and a hole inside the product's box is found.
    """
    west, south, east, north = mask.bounds
    xs = np.arange(np.floor(west / step_deg) * step_deg + step_deg / 2, east, step_deg)
    ys = np.arange(np.floor(south / step_deg) * step_deg + step_deg / 2, north, step_deg)
    gx, gy = np.meshgrid(xs, ys)
    inside = shapely.contains_xy(mask, gx.ravel(), gy.ravel()).reshape(gx.shape)
    la, lo = np.meshgrid(np.asarray(lat, dtype=float), np.asarray(lon, dtype=float), indexing="ij")
    keep = np.asarray(valid, dtype=bool)
    if not keep.any():
        return [acquisition_bbox(mask.bounds, margin_deg)]
    dist, _ = cKDTree(np.column_stack([la[keep], lo[keep]])).query(
        np.column_stack([gy.ravel(), gx.ravel()])
    )
    uncovered = inside & (dist.reshape(gx.shape) > tol_cells * native_res_deg + 1e-9)
    if not uncovered.any():
        return []
    # samples closer than two native cells belong to the same part
    joined = binary_dilation(uncovered, iterations=max(1, round(2 * native_res_deg / step_deg)))
    labels, n = label(joined, structure=np.ones((3, 3)))
    grown = []
    for k in range(1, n + 1):
        part = (labels == k) & uncovered
        if not part.any():
            continue
        grown.append(
            box(
                *acquisition_bbox(
                    (gx[part].min(), gy[part].min(), gx[part].max(), gy[part].max()),
                    margin_deg + overlap_deg,
                )
            )
        )
    merged = unary_union(grown)
    boxes = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    return [tuple(float(v) for v in b.bounds) for b in boxes]


def cds_area(box: Sequence[float]) -> list[float]:
    """CDS `area` parameter [N, W, S, E] of a (west, south, east, north) box."""
    west, south, east, north = box
    return [float(north), float(west), float(south), float(east)]
