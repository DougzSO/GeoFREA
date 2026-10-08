"""Reference definitions of the two binary masks frozen in the V-01 fixtures (`e1_protected`, `e2_water`).

They are the binary masks the fixtures were frozen with (1 = free, 0 = excluded; nodata outside the country), moved
here from the retired `suitability_criteria` phase (V16) with identical logic so the frozen values are unchanged.
They are test references, not pipeline code: F3 measures E1-E3 as sub-pixel shares (`land_eligibility/fractions.py`).
The IUCN categories below are the ones the fixtures were frozen with (Ia, Ib, II).
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
from rasterio.features import rasterize
from rasterio.transform import Affine
from shapely.geometry import mapping

from geofrea.core.constants import NODATA_FLOAT
from geofrea.core.geo_utils import clip_vector_to_country
from geofrea.core.raster_io import safe_raster_open

FROZEN_STRICT_IUCN_CATEGORIES = ("ia", "ib", "ii")


def lakes_mask(lakes_path: str) -> np.ndarray:
    """Lake pixels -> 0, land pixels -> 1, outside the country (255) -> NODATA_FLOAT."""
    with safe_raster_open(lakes_path) as src:
        lake = src.read(1).astype(np.uint8)
    out = np.full(lake.shape, NODATA_FLOAT, dtype=np.float32)
    out[(lake != 255) & (lake == 0)] = 1.0
    out[(lake != 255) & (lake == 1)] = 0.0
    return out


def protected_mask(
    wdpa_gpkg: Path, mainland: gpd.GeoDataFrame, transform: Affine, width: int, height: int, crs: str
) -> np.ndarray:
    """WDPA mask: 0 where a polygon's IUCN category is in the frozen set, 1 elsewhere on the mainland."""
    strict = set(FROZEN_STRICT_IUCN_CATEGORIES)
    union = mainland.to_crs(crs).union_all()
    mainland_mask = rasterize([(mapping(union), 1)], out_shape=(height, width), transform=transform, fill=0, dtype="uint8")
    score = np.full((height, width), NODATA_FLOAT, dtype=np.float32)
    raw = gpd.read_file(wdpa_gpkg)
    raw = raw[~raw.geometry.is_empty]
    gdf, _report = clip_vector_to_country(raw, mainland)
    if gdf.crs is not None and str(gdf.crs) != crs:
        gdf = gdf.to_crs(crs)
    gdf = gdf[~gdf.geometry.is_empty]
    if gdf.empty:
        score[mainland_mask > 0] = 1.0
        return score
    col = next((c for c in ("IUCN_CAT", "iucn_cat", "IUCN", "DESIGNATION") if c in gdf.columns), None)
    if col is not None:
        cats = gdf[col].astype("string").str.lower().str.strip()
        values = np.where(cats.isin(strict), 0.0, 1.0)
    else:
        values = np.full(len(gdf), 1.0)
    order = np.argsort(-values, kind="stable")
    shapes = [(mapping(g), float(v)) for g, v in zip(gdf.geometry.to_numpy()[order], values[order])]
    temp = np.full((height, width), 1.0, dtype=np.float32)
    rasterize(shapes, out_shape=(height, width), transform=transform, out=temp)
    score[mainland_mask > 0] = temp[mainland_mask > 0]
    return score
