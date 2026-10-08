"""The `reference_grid` artifact: the analysis grid definition, deterministic and independent of the other layers."""

from __future__ import annotations

import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from geofrea.grid_alignment.reference_grid import write_reference_grid_artifact


def _raster(path, values, nodata=-9999.0):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=values.shape[0],
        width=values.shape[1],
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(10.0, 5.0, 0.01, 0.01),
        nodata=nodata,
    ) as dst:
        dst.write(values.astype("float32"), 1)
    return path


@pytest.mark.unit
def test_reference_grid_artifact_is_deterministic_and_ignores_the_values_inside_the_country(
    tmp_path,
):
    base = np.full((10, 15), 3.0)
    base[0, :] = -9999.0  # outside the country
    one = write_reference_grid_artifact(_raster(tmp_path / "a.tif", base), tmp_path / "a.json")
    other_values = np.where(base > 0, 99.0, base)  # other distances, same country
    two = write_reference_grid_artifact(
        _raster(tmp_path / "b.tif", other_values), tmp_path / "b.json"
    )
    assert one.read_bytes() == two.read_bytes()
    d = json.loads(one.read_text(encoding="utf-8"))
    assert (
        d["width"] == 15
        and d["height"] == 10
        and d["valid_pixels"] == 135
        and d["pixel_size_deg"] == 0.01
    )


@pytest.mark.unit
def test_reference_grid_artifact_changes_when_the_country_mask_changes(tmp_path):
    base = np.full((10, 15), 3.0)
    one = write_reference_grid_artifact(_raster(tmp_path / "a.tif", base), tmp_path / "a.json")
    moved = base.copy()
    moved[5, 5] = -9999.0
    two = write_reference_grid_artifact(_raster(tmp_path / "b.tif", moved), tmp_path / "b.json")
    assert one.read_bytes() != two.read_bytes()
