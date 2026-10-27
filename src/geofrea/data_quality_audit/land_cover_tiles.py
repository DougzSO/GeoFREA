"""Per-tile land-cover audit of F1b: the area of every ESA WorldCover class inside the country polygon, with its cache (OQ-026, D-F1b-018).

Kept in a module of its own so that the code fingerprint of the cache (`core.cache_code`, name `land_cover_tiles`) holds only the code that computes
the class areas: an edit of any other part of `raster_inspection.py` no longer invalidates the 111 tiles of BRA (55 minutes to compute again).
Nothing here imports `raster_inspection`.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from shapely.geometry import box

from geofrea.core.cache_code import cache_code
from geofrea.core.cache_key import cache_key
from geofrea.core.geodesy import wgs84_km_per_degree

logger = logging.getLogger(__name__)


def row_area_km2(shape: tuple[int, int], transform: rasterio.Affine) -> np.ndarray:
    """Compute geodetic area per pixel row in km², corrected by latitude.

    Returns a 1D array (height,) rather than a full 2D grid to avoid
    memory issues with large tiles. WGS84 scale factors come from
    core.geodesy.wgs84_km_per_degree() — centralized 2026-09-09 (see
    docs/_archive/2026-09/DECISIONS.md same date, grid_alignment Passo 4 item 1; this
    was the most complete of three previously-divergent truncations,
    now the shared one).
    """
    height, _ = shape
    res_x = abs(transform.a)
    res_y = abs(transform.e)

    rows = np.arange(height)
    y_top = transform.f + rows * transform.e
    y_bottom = transform.f + (rows + 1) * transform.e
    lat_mid = (y_top + y_bottom) / 2.0

    lat_km, lon_km = wgs84_km_per_degree(lat_mid)

    km_x = res_x * lon_km
    km_y = res_y * lat_km
    return (km_x * km_y).astype(np.float64)


# Version of the per-tile class-area computation, part of every tile cache key (OQ-026). Bump it by hand when the logic of
# `inspect_land_cover_tiles` changes (masking, area weights, class handling), or old cache entries would be reused.
LAND_COVER_TILE_ALGORITHM_VERSION = 1
_LAND_COVER_WINDOW_PX = 8192


def _land_cover_geom_fingerprint(country_geom) -> str:
    """Short hash of the country polygon actually used to mask tiles.

    Included in every per-tile cache key so a changed island-filtering
    rule or a different country_gdf invalidates cached results instead
    of silently reusing areas computed against a stale polygon.
    """
    return hashlib.sha256(country_geom.wkb).hexdigest()[:16]


def _land_cover_tile_cache_key(tile: Path, geom_fingerprint: str) -> str:
    """Cache key for one tile (OQ-026): the algorithm version, the tile's SHA-256 and the config values that change the result.

    The inputs are the tile (by content, so a re-fetch of identical bytes still hits) and the config is the masking polygon's
    fingerprint and the window size of the scan. Any of the three changing, or `LAND_COVER_TILE_ALGORITHM_VERSION`, misses.
    """
    return cache_key(
        LAND_COVER_TILE_ALGORITHM_VERSION,
        [tile],
        {"country_polygon_fingerprint": geom_fingerprint, "window_px": _LAND_COVER_WINDOW_PX},
        code=cache_code("land_cover_tiles"),
    )


def _load_land_cover_tile_cache(
    cache_dir: Path, tile: Path, geom_fingerprint: str
) -> dict[str, Any] | None:
    cache_file = cache_dir / f"{tile.stem}.json"
    if not cache_file.exists():
        return None
    try:
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("[land_cover] Failed to read tile cache %s: %s", cache_file, exc)
        return None
    if cached.get("cache_key") != _land_cover_tile_cache_key(tile, geom_fingerprint):
        return None
    return cached


def _save_land_cover_tile_cache(
    cache_dir: Path, tile: Path, geom_fingerprint: str, payload: dict[str, Any]
) -> None:
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        payload_with_key = {
            **payload,
            "cache_key": _land_cover_tile_cache_key(tile, geom_fingerprint),
        }
        (cache_dir / f"{tile.stem}.json").write_text(json.dumps(payload_with_key), encoding="utf-8")
    except OSError as exc:
        logger.warning("[land_cover] Failed to write tile cache for %s: %s", tile.name, exc)


def score_land_cover_tile(tile: Path, country_geom, country_bounds) -> dict[str, Any] | None:
    """Class areas (km2) of one tile inside the country polygon.

    Args:
        tile: ESA WorldCover tile.
        country_geom: Country polygon (the union of the mask).
        country_bounds: `total_bounds` of the country.

    Returns:
        `{"crs", "res", "class_areas": {class: km2}}`, or None when the tile does not overlap the country (bounding box or polygon).
    """
    with rasterio.open(str(tile)) as src:
        t_bounds = src.bounds

        if (
            t_bounds[2] < country_bounds[0]
            or t_bounds[0] > country_bounds[2]
            or t_bounds[3] < country_bounds[1]
            or t_bounds[1] > country_bounds[3]
        ):
            return None

        intersected_geom = country_geom.intersection(box(*t_bounds))
        if intersected_geom.is_empty:
            return None

        tile_crs = str(src.crs)
        tile_res = round(abs(src.res[0]), 8)
        row_areas_global = row_area_km2((src.height, src.width), src.transform)
        tile_class_areas: dict[int, float] = {}

        step = _LAND_COVER_WINDOW_PX
        for r in range(0, src.height, step):
            for c in range(0, src.width, step):
                window = rasterio.windows.Window(
                    c, r, min(step, src.width - c), min(step, src.height - r)
                )

                w_bounds = src.window_bounds(window)
                if not box(*w_bounds).intersects(intersected_geom):
                    continue

                data_block = src.read(1, window=window)
                if not np.any(data_block > 0):
                    continue

                win_transform = src.window_transform(window)
                block_mask = geometry_mask(
                    [intersected_geom],
                    out_shape=data_block.shape,
                    transform=win_transform,
                    invert=True,
                )

                valid_mask = (data_block > 0) & block_mask
                if not np.any(valid_mask):
                    continue

                row_areas_win = row_areas_global[window.row_off : window.row_off + window.height]
                unique_classes = np.unique(data_block[valid_mask])

                for cls in unique_classes:
                    cls_mask = (data_block == cls) & block_mask
                    cls_per_row = cls_mask.sum(axis=1)
                    area = float((row_areas_win * cls_per_row).sum())
                    cls_int = int(cls)
                    tile_class_areas[cls_int] = tile_class_areas.get(cls_int, 0.0) + area

        del row_areas_global

    return {"crs": tile_crs, "res": tile_res, "class_areas": tile_class_areas}
