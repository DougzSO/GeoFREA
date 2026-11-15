"""The protected-area footprint of a real country, from the local data (V-01 complement for PRT and BRA).

Reads the WDPA file of the country and the aligned grid of F2a in the real data directory, and
computes the share of each 0.01 degree pixel covered by the polygons with the function that F3 uses
(`land_eligibility.fractions.polygon_coverage_fraction`, the selection of `land_eligibility.pipeline._iucn_subset`).
The test `test_protected_footprint.py` compares the counts with `tests/fixtures/protected_footprint/footprint.json`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio

from geofrea.land_eligibility.cells import pixel_row_area_km2
from geofrea.land_eligibility.fractions import polygon_coverage_fraction
from geofrea.land_eligibility.pipeline import ANY_CATEGORY, _iucn_subset

LEVELS = {"any": (ANY_CATEGORY,), "ia_ib_ii": ("ia", "ib", "ii")}


def wdpa_file(root: Path, iso: str) -> Path:
    return root / "raw" / "wdpa" / iso / f"{iso}_protected_areas_wdpa.geojson"


def grid_file(root: Path, iso: str) -> Path:
    return root / "outputs" / iso / "grid_alignment" / "artifacts" / f"{iso}_elevation_aligned.tif"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def footprint(root: Path, iso: str) -> dict:
    """Pixels with a share above 0 and of at least one half, and the covered area (km2), per level."""
    with rasterio.open(grid_file(root, iso)) as grid:
        transform, shape = grid.transform, (grid.height, grid.width)
    gdf = gpd.read_file(wdpa_file(root, iso))
    area_row = pixel_row_area_km2(transform, shape[0])
    out = {}
    for name, cats in LEVELS.items():
        share = polygon_coverage_fraction(_iucn_subset(gdf, cats), transform, shape)
        out[name] = {
            "pixels_above_0": int((share > 0).sum()),
            "pixels_at_least_half": int((share >= 0.5).sum()),
            "area_km2": float((share.astype(np.float64) * area_row[:, None]).sum()),
        }
    return out
