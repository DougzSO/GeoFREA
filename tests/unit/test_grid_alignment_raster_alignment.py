"""Unit tests for geofrea.grid_alignment.raster_alignment."""

from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Polygon

from geofrea.core.constants import NODATA_FLOAT, NODATA_UINT8
from geofrea.grid_alignment.raster_alignment import (
    combine_wind_layers,
    compute_ahp_weights,
    mosaic_land_cover,
    reproject_to_grid,
)
from geofrea.grid_alignment.reference_grid import build_reference_grid

_ORIGIN_LON, _ORIGIN_LAT = -9.0, 39.0
_RES = 0.01


def _square(cx: float, cy: float, half_side: float) -> Polygon:
    return Polygon(
        [
            (cx - half_side, cy - half_side),
            (cx + half_side, cy - half_side),
            (cx + half_side, cy + half_side),
            (cx - half_side, cy + half_side),
        ]
    )


def _country_gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(geometry=[_square(_ORIGIN_LON + 0.2, _ORIGIN_LAT - 0.2, 0.15)], crs="EPSG:4326")


def _grid():
    return build_reference_grid(_country_gdf(), resolution_deg=_RES)


def _write_raster(path: Path, value: float, size: int = 60, dtype: str = "float32", nodata: float = -9999.0) -> None:
    transform = from_origin(_ORIGIN_LON, _ORIGIN_LAT, _RES, _RES)
    data = np.full((size, size), value, dtype=dtype)
    with rasterio.open(
        path, "w", driver="GTiff", height=size, width=size, count=1,
        dtype=dtype, crs="EPSG:4326", transform=transform, nodata=nodata,
    ) as dst:
        dst.write(data, 1)


@pytest.mark.unit
def test_reproject_to_grid_preserves_constant_value_inside_country_mask(tmp_path):
    grid = _grid()
    src_path = tmp_path / "src.tif"
    _write_raster(src_path, value=42.0)

    out_path = reproject_to_grid(src_path, tmp_path / "out.tif", grid)

    with rasterio.open(out_path) as src:
        data = src.read(1)

    assert np.allclose(data[grid.country_mask], 42.0, atol=0.01)
    assert np.all(data[~grid.country_mask] == NODATA_FLOAT)


@pytest.mark.unit
def test_reproject_to_grid_uint8_dtype_uses_zero_nodata_default(tmp_path):
    grid = _grid()
    src_path = tmp_path / "src.tif"
    _write_raster(src_path, value=5, dtype="uint8", nodata=0)

    out_path = reproject_to_grid(
        src_path, tmp_path / "out.tif", grid, nodata_out=NODATA_UINT8, dtype_out="uint8"
    )

    with rasterio.open(out_path) as src:
        assert src.nodata == NODATA_UINT8
        data = src.read(1)
    assert data[~grid.country_mask].max() == NODATA_UINT8


@pytest.mark.unit
def test_compute_ahp_weights_perfectly_consistent_matrix_gives_zero_rc():
    # A matrix built from a real ratio scale (v = [1, 2, 4], matrix[i][j]
    # = v[i]/v[j]) is perfectly Saaty-consistent by construction: its
    # principal eigenvalue equals n exactly, so CI = CR = 0. The
    # identity matrix is NOT such a matrix (every vector is one of its
    # eigenvectors, with eigenvalue 1, not n) — it does not exercise
    # this function's real invariant.
    v = np.array([1.0, 2.0, 4.0])
    matrix = v[:, None] / v[None, :]

    weights, rc = compute_ahp_weights(matrix)

    assert weights == pytest.approx(v / v.sum(), abs=1e-9)
    assert rc == pytest.approx(0.0, abs=1e-9)


@pytest.mark.unit
def test_compute_ahp_weights_inconsistent_matrix_gives_positive_rc():
    matrix = np.array([[1.0, 9.0, 1 / 9], [1 / 9, 1.0, 9.0], [9.0, 1 / 9, 1.0]])

    _weights, rc = compute_ahp_weights(matrix)

    assert rc > 0.10  # this specific cyclic matrix is a textbook-inconsistent case


@pytest.mark.unit
def test_combine_wind_layers_raises_on_empty_list():
    grid = _grid()
    with pytest.raises(ValueError, match="No wind raster paths"):
        combine_wind_layers([], Path("out.tif"), grid)


@pytest.mark.unit
def test_combine_wind_layers_single_height_uses_full_weight(tmp_path):
    grid = _grid()
    path = tmp_path / "PRT_wind_100m.tif"
    _write_raster(path, value=8.0)

    out_path = combine_wind_layers([path], tmp_path / "wind.tif", grid)

    with rasterio.open(out_path) as src:
        data = src.read(1)
    assert np.allclose(data[grid.country_mask], 8.0, atol=0.05)


@pytest.mark.unit
def test_combine_wind_layers_two_heights_use_uniform_half_weights(tmp_path):
    # len(present) == 2, not 3 -> uniform 1/n branch (AHP only applies
    # to the full 3-height case), so the combined result is a plain
    # 50/50 average of the two source values.
    grid = _grid()
    p50 = tmp_path / "wind_50m.tif"
    p100 = tmp_path / "wind_100m.tif"
    _write_raster(p50, value=4.0)
    _write_raster(p100, value=10.0)

    out_path = combine_wind_layers([p50, p100], tmp_path / "wind.tif", grid)

    with rasterio.open(out_path) as src:
        data = src.read(1)
    assert np.allclose(data[grid.country_mask], 7.0, atol=0.05)


@pytest.mark.unit
def test_combine_wind_layers_three_heights_uses_ahp_not_uniform_weights(tmp_path):
    # All three recognized heights present -> AHP branch. WIND_AHP_MATRIX
    # favors 200m most heavily (row 1 in the Saaty matrix), so with
    # distinct values per height the AHP-weighted result must differ
    # from the plain 1/3-uniform average — locks in that the AHP branch
    # actually ran, not silently fell back to uniform.
    grid = _grid()
    p200 = tmp_path / "wind_200m.tif"
    p100 = tmp_path / "wind_100m.tif"
    p50 = tmp_path / "wind_50m.tif"
    _write_raster(p200, value=20.0)
    _write_raster(p100, value=10.0)
    _write_raster(p50, value=5.0)

    out_path = combine_wind_layers([p200, p100, p50], tmp_path / "wind.tif", grid)

    with rasterio.open(out_path) as src:
        data = src.read(1)
    combined = data[grid.country_mask].mean()
    uniform_average = (20.0 + 10.0 + 5.0) / 3
    assert combined != pytest.approx(uniform_average, abs=0.05)
    # 200m should be weighted most heavily -> combined skews toward 20.
    assert combined > uniform_average


@pytest.mark.unit
def test_combine_wind_layers_falls_back_to_uniform_when_ahp_rc_exceeds_threshold(tmp_path):
    # WIND_AHP_MATRIX (core/constants.py) is a real Saaty-consistent
    # matrix, so RC>0.10 is never naturally reached with the shipped
    # constant — this forces the branch with a deliberately
    # inconsistent 3x3 matrix, to prove the fallback-to-uniform path
    # itself works, not just that it's unreachable in practice.
    grid = _grid()
    p200 = tmp_path / "wind_200m.tif"
    p100 = tmp_path / "wind_100m.tif"
    p50 = tmp_path / "wind_50m.tif"
    _write_raster(p200, value=20.0)
    _write_raster(p100, value=10.0)
    _write_raster(p50, value=5.0)

    inconsistent_matrix = [[1.0, 9.0, 1 / 9], [1 / 9, 1.0, 9.0], [9.0, 1 / 9, 1.0]]

    import geofrea.grid_alignment.raster_alignment as raster_alignment_module

    with patch.object(raster_alignment_module, "WIND_AHP_MATRIX", inconsistent_matrix):
        out_path = combine_wind_layers([p200, p100, p50], tmp_path / "wind.tif", grid)

    with rasterio.open(out_path) as src:
        data = src.read(1)
    combined = data[grid.country_mask].mean()
    uniform_average = (20.0 + 10.0 + 5.0) / 3
    assert combined == pytest.approx(uniform_average, abs=0.05)


@pytest.mark.unit
def test_combine_wind_layers_unidentified_file_defaults_to_100m(tmp_path):
    grid = _grid()
    path = tmp_path / "wind_unlabeled.tif"
    _write_raster(path, value=6.0)

    out_path = combine_wind_layers([path], tmp_path / "wind.tif", grid)

    with rasterio.open(out_path) as src:
        data = src.read(1)
    assert np.allclose(data[grid.country_mask], 6.0, atol=0.05)


@pytest.mark.unit
def test_combine_wind_layers_second_unidentified_file_is_discarded(tmp_path):
    grid = _grid()
    first_unlabeled = tmp_path / "wind_a.tif"
    second_unlabeled = tmp_path / "wind_b.tif"
    _write_raster(first_unlabeled, value=6.0)
    _write_raster(second_unlabeled, value=999.0)  # must NOT influence the result

    out_path = combine_wind_layers([first_unlabeled, second_unlabeled], tmp_path / "wind.tif", grid)

    with rasterio.open(out_path) as src:
        data = src.read(1)
    assert np.allclose(data[grid.country_mask], 6.0, atol=0.05)


@pytest.mark.unit
def test_mosaic_land_cover_skips_tile_with_no_bbox_overlap(tmp_path):
    grid = _grid()
    country_gdf = _country_gdf()

    near_tile = tmp_path / "near.tif"
    _write_raster(near_tile, value=10, dtype="uint8", nodata=0)

    far_tile = tmp_path / "far.tif"
    far_transform = from_origin(100.0, 100.0, _RES, _RES)
    with rasterio.open(
        far_tile, "w", driver="GTiff", height=10, width=10, count=1,
        dtype="uint8", crs="EPSG:4326", transform=far_transform, nodata=0,
    ) as dst:
        dst.write(np.full((10, 10), 88, dtype="uint8"), 1)

    out_path = mosaic_land_cover([near_tile, far_tile], tmp_path / "lc.tif", grid, country_gdf)

    assert out_path is not None
    with rasterio.open(out_path) as src:
        data = src.read(1)
    assert 88 not in data  # far tile's value must never appear
    assert (data[grid.country_mask] == 10).any()


@pytest.mark.unit
def test_mosaic_land_cover_skips_corrupted_tile_without_crashing(tmp_path):
    grid = _grid()
    country_gdf = _country_gdf()

    good_tile = tmp_path / "good.tif"
    _write_raster(good_tile, value=20, dtype="uint8", nodata=0)

    corrupted_tile = tmp_path / "corrupted.tif"
    corrupted_tile.write_bytes(b"not a real geotiff")

    out_path = mosaic_land_cover([corrupted_tile, good_tile], tmp_path / "lc.tif", grid, country_gdf)

    assert out_path is not None
    with rasterio.open(out_path) as src:
        data = src.read(1)
    assert (data[grid.country_mask] == 20).any()


@pytest.mark.unit
def test_mosaic_land_cover_returns_none_when_every_tile_fails(tmp_path):
    grid = _grid()
    country_gdf = _country_gdf()

    corrupted_tile = tmp_path / "corrupted.tif"
    corrupted_tile.write_bytes(b"not a real geotiff")

    result = mosaic_land_cover([corrupted_tile], tmp_path / "lc.tif", grid, country_gdf)

    assert result is None


@pytest.mark.unit
def test_mosaic_land_cover_first_tile_wins_on_overlap(tmp_path):
    # mask_fill = (tile_reprojected > 0) & (lc_out == 0) — a pixel
    # already filled by an earlier tile is never overwritten by a
    # later, overlapping one.
    grid = _grid()
    country_gdf = _country_gdf()

    tile_a = tmp_path / "a.tif"
    tile_b = tmp_path / "b.tif"
    _write_raster(tile_a, value=30, dtype="uint8", nodata=0)
    _write_raster(tile_b, value=70, dtype="uint8", nodata=0)

    out_path = mosaic_land_cover([tile_a, tile_b], tmp_path / "lc.tif", grid, country_gdf)

    with rasterio.open(out_path) as src:
        data = src.read(1)
    assert (data[grid.country_mask] == 30).any()
    assert not (data[grid.country_mask] == 70).any()
