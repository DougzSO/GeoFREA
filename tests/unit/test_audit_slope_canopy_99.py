"""`scripts/audit_slope_canopy_99.py`: the cut by slope split by land-cover class, on a 2-pixel raster computed by hand."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "audit_slope_canopy_99.py"
spec = importlib.util.spec_from_file_location("audit_slope_canopy_99", SCRIPT)
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

CLASSES = (10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100)


def write(path, data, transform, nodata, tags=None):
    with rasterio.open(path, "w", driver="GTiff", height=data.shape[1], width=data.shape[2], count=data.shape[0], dtype=data.dtype, crs="EPSG:4326", transform=transform, nodata=nodata) as dst:
        dst.write(data)
        if tags:
            dst.update_tags(**tags)


def test_the_cut_is_split_by_class_and_the_overlap_readings_are_ordered(tmp_path):
    transform = from_origin(0.0, 0.02, 0.01, 0.01)  # 2 rows x 1 column near the equator
    slope = np.zeros((41, 2, 1), dtype=np.uint16)
    slope[0, 0, 0] = 100  # pixel 0: all samples flat
    slope[30, 1, 0] = 100  # pixel 1: all samples at 30 degrees, steeper than any threshold below
    lc = np.zeros((11, 2, 1), dtype=np.uint16)
    lc[0, 0, 0] = 14400  # pixel 0: all trees
    lc[0, 1, 0] = 7200  # pixel 1: half trees, half grassland
    lc[2, 1, 0] = 7200
    write(tmp_path / "X_slope_counts_aligned.tif", slope, transform, 65535)
    write(tmp_path / "X_land_cover_counts_aligned.tif", lc, transform, 65535, {"samples_per_pixel": "14400", "worldcover_classes": ",".join(map(str, CLASSES))})
    write(tmp_path / "X_grid_aligned.tif", np.ones((1, 2, 1), dtype=np.float32), transform, -9999.0)

    rows = sc.diagnose("X", tmp_path, {("wind", "central"): (11.31, 20.0, (10, 50))})
    (row,) = rows
    area1 = float(sc.pixel_row_area_km2(rasterio.open(tmp_path / "X_grid_aligned.tif").transform, 2)[1])
    assert row["cut_km2"] == pytest.approx(area1)  # only pixel 1 is steep, all of it
    assert row["cut_trees_km2"] == pytest.approx(0.5 * area1)
    assert row["cut_grassland_km2"] == pytest.approx(0.5 * area1)
    assert row["in_excluded_independent_km2"] == pytest.approx(0.5 * area1)  # e = 1, F = 0.5
    assert row["in_excluded_lower_km2"] == pytest.approx(0.5 * area1)  # max(0, 1 + 0.5 - 1)
    assert row["in_excluded_upper_km2"] == pytest.approx(0.5 * area1)  # min(1, 0.5)
    assert row["pure_trees_mean_e4"] == pytest.approx(0.0)  # the only >= 90 % tree pixel is flat
    assert row["in_excluded_lower_km2"] <= row["in_excluded_independent_km2"] <= row["in_excluded_upper_km2"]
