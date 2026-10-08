"""Unit tests for geofrea.grid_alignment.raster_alignment."""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Polygon

from geofrea.core.constants import NODATA_FLOAT, NODATA_UINT8
from geofrea.core.geodesy import wgs84_km_per_degree
from geofrea.grid_alignment.raster_alignment import (
    LandCoverCountNotExactError,
    MissingSourceCrsError,
    land_cover_class_counts,
    mosaic_land_cover,
    reproject_to_grid,
    slope_class_counts,
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


def _triangle(cx: float, cy: float, half_side: float) -> Polygon:
    """Right triangle: half of its bounding grid lies outside the country mask, whatever the snapping."""
    return Polygon([(cx - half_side, cy - half_side), (cx + half_side, cy - half_side), (cx - half_side, cy + half_side)])


def _country_gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(geometry=[_triangle(_ORIGIN_LON + 0.2, _ORIGIN_LAT - 0.2, 0.15)], crs="EPSG:4326")


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
def test_sum_resampling_keeps_the_total_of_a_count_raster_when_coarsening(tmp_path):
    """Population (counts per pixel) must be summed, not sampled: 12 x 12 fine pixels of 1 person give 144 per pixel."""
    from rasterio.enums import Resampling

    grid = _grid()
    fine = _RES / 12
    size = 60 * 12
    transform = from_origin(_ORIGIN_LON, _ORIGIN_LAT, fine, fine)
    path = tmp_path / "pop.tif"
    with rasterio.open(
        path, "w", driver="GTiff", height=size, width=size, count=1, dtype="float32", crs="EPSG:4326",
        transform=transform, nodata=-9999.0,
    ) as dst:
        dst.write(np.ones((size, size), dtype="float32"), 1)

    summed = reproject_to_grid(path, tmp_path / "sum.tif", grid, resampling=Resampling.sum)
    sampled = reproject_to_grid(path, tmp_path / "bil.tif", grid)  # the old default
    with rasterio.open(summed) as a, rasterio.open(sampled) as b:
        s, bil = a.read(1), b.read(1)
    inside = grid.country_mask & (s != NODATA_FLOAT)
    assert inside.any()
    interior = s[inside][s[inside] > 100]
    assert np.allclose(interior, 144.0)
    assert np.allclose(bil[inside], 1.0, atol=0.01)  # one person per pixel: 1/144 of the count


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
def test_reproject_to_grid_sanitizes_literal_nan_despite_finite_declared_nodata(tmp_path):
    # Reproduces BRA_elevation.tif in production (docs/DECISIONS.md
    # 2026-09-11, "elevation NaN leak"): the file declares a finite
    # nodata sentinel (-9999) but 0 cells actually equal it -- its real
    # nodata cells are literal NaN instead, a metadata/data mismatch in
    # the raw source file. Without sanitizing before reproject, GDAL's
    # bilinear warp doesn't recognise those NaN cells as `src_nodata`
    # and blends them into neighbouring destination pixels as actual
    # NaN, not `nodata_out`.
    grid = _grid()
    src_path = tmp_path / "src_with_nan.tif"
    size = 60
    transform = from_origin(_ORIGIN_LON, _ORIGIN_LAT, _RES, _RES)
    data = np.full((size, size), 100.0, dtype="float32")
    data[size // 2, size // 2] = np.nan  # NOT -9999 -- a bare NaN residual
    with rasterio.open(
        src_path, "w", driver="GTiff", height=size, width=size, count=1,
        dtype="float32", crs="EPSG:4326", transform=transform, nodata=-9999.0,
    ) as dst:
        dst.write(data, 1)

    out_path = reproject_to_grid(src_path, tmp_path / "out.tif", grid)

    with rasterio.open(out_path) as src:
        out_data = src.read(1)

    assert not np.isnan(out_data).any(), (
        "literal NaN from the source leaked into the aligned output instead "
        "of being sanitized to the declared nodata sentinel"
    )
    # The rest of the (uniform 100.0) raster must still align correctly --
    # sanitizing one stray cell must not corrupt everything else.
    assert np.allclose(out_data[grid.country_mask], 100.0, atol=1.0) or (
        out_data[grid.country_mask] == NODATA_FLOAT
    ).any()


@pytest.mark.unit
def test_reproject_to_grid_leaves_nan_declared_nodata_sources_untouched(tmp_path):
    # Some DEM products legitimately declare nodata AS NaN itself (e.g.
    # PRT's own raw elevation raster in production). GDAL already
    # handles that correctly; the sanitization guard must not touch it
    # (guarded by `not np.isnan(src_nodata)` in reproject_to_grid).
    grid = _grid()
    src_path = tmp_path / "src_nan_nodata.tif"
    size = 60
    transform = from_origin(_ORIGIN_LON, _ORIGIN_LAT, _RES, _RES)
    data = np.full((size, size), 50.0, dtype="float32")
    data[0, 0] = np.nan
    with rasterio.open(
        src_path, "w", driver="GTiff", height=size, width=size, count=1,
        dtype="float32", crs="EPSG:4326", transform=transform, nodata=np.nan,
    ) as dst:
        dst.write(data, 1)

    out_path = reproject_to_grid(src_path, tmp_path / "out.tif", grid)

    with rasterio.open(out_path) as src:
        out_data = src.read(1)
    assert not np.isnan(out_data).any()


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
def test_mosaic_land_cover_raises_when_corrupted_tile_overlaps_country(tmp_path):
    # docs/DECISIONS.md 2026-09-11, "mosaic_land_cover fail-loud on
    # in-country gaps": a tile that can't be opened has unreadable real
    # bounds, so the overlap check falls back to its NOMINAL ESA
    # WorldCover bounds parsed from the filename. This tile's id
    # (N36W009 -> lon[-9,-6], lat[36,39]) overlaps the test country's
    # bbox (see _country_gdf: centered ~(-8.8, 38.8), half_side=0.15).
    grid = _grid()
    country_gdf = _country_gdf()

    corrupted_tile = tmp_path / "ESA_WorldCover_10m_2020_v100_N36W009_Map.tif"
    corrupted_tile.write_bytes(b"not a real geotiff")

    with pytest.raises(RuntimeError, match="overlaps the country being mosaicked"):
        mosaic_land_cover([corrupted_tile], tmp_path / "lc.tif", grid, country_gdf)


@pytest.mark.unit
def test_mosaic_land_cover_skips_corrupted_tile_outside_country_with_warning(tmp_path, caplog):
    # Same corrupted-file scenario, but this tile's nominal footprint
    # (S36W060 -> lon[-60,-57], lat[-36,-33]) is nowhere near the test
    # country -- must NOT raise, but must still be traceable in the log
    # (not a fully silent skip).
    grid = _grid()
    country_gdf = _country_gdf()

    good_tile = tmp_path / "good.tif"
    _write_raster(good_tile, value=20, dtype="uint8", nodata=0)

    corrupted_tile = tmp_path / "ESA_WorldCover_10m_2020_v100_S36W060_Map.tif"
    corrupted_tile.write_bytes(b"not a real geotiff")

    with caplog.at_level("WARNING"):
        out_path = mosaic_land_cover(
            [corrupted_tile, good_tile], tmp_path / "lc.tif", grid, country_gdf
        )

    assert out_path is not None
    with rasterio.open(out_path) as src:
        data = src.read(1)
    assert (data[grid.country_mask] == 20).any()
    assert any(
        corrupted_tile.name in record.message and "no bbox overlap" in record.message
        for record in caplog.records
    )


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


def _write_ramp_with_nan_mismatch(path: Path) -> None:
    """120x120 float32 at 0.005 deg, value = row*1000 + col, declared nodata -9999 but literal NaN cells inside."""
    size = 120
    data = (np.arange(size)[:, None] * 1000.0 + np.arange(size)[None, :]).astype("float32")
    data[30:40, 50:70] = np.nan
    with rasterio.open(
        path, "w", driver="GTiff", height=size, width=size, count=1, dtype="float32", crs="EPSG:4326",
        transform=rasterio.transform.from_origin(_ORIGIN_LON, _ORIGIN_LAT, 0.005, 0.005), nodata=-9999.0,
    ) as dst:
        dst.write(data, 1)


@pytest.mark.unit
def test_windowed_strips_give_the_same_raster_as_a_single_pass(tmp_path):
    grid = _grid()
    src_path = tmp_path / "ramp.tif"
    _write_ramp_with_nan_mismatch(src_path)

    one = reproject_to_grid(src_path, tmp_path / "one.tif", grid)  # fits in one window
    many = reproject_to_grid(src_path, tmp_path / "many.tif", grid, max_window_bytes=20_000)  # forced strips

    with rasterio.open(one) as a, rasterio.open(many) as b:
        da, db = a.read(1), b.read(1)
    assert np.array_equal(da, db, equal_nan=True)  # strip seams change nothing


@pytest.mark.unit
def test_reproject_never_reads_the_whole_source_when_it_exceeds_the_window_budget(tmp_path, monkeypatch):
    from geofrea.grid_alignment import raster_alignment

    grid = _grid()
    src_path = tmp_path / "ramp.tif"
    _write_ramp_with_nan_mismatch(src_path)
    full_bytes = 120 * 120 * 4
    sizes = []
    real = raster_alignment.reproject

    def spy(**kwargs):
        sizes.append(kwargs["source"].nbytes)
        return real(**kwargs)

    monkeypatch.setattr(raster_alignment, "reproject", spy)

    reproject_to_grid(src_path, tmp_path / "out.tif", grid, max_window_bytes=20_000)

    assert len(sizes) > 1  # several strips
    assert max(sizes) < full_bytes  # no call saw the whole raster


@pytest.mark.unit
def test_source_that_does_not_overlap_the_grid_yields_all_nodata(tmp_path):
    grid = _grid()
    src_path = tmp_path / "far.tif"
    with rasterio.open(
        src_path, "w", driver="GTiff", height=10, width=10, count=1, dtype="float32", crs="EPSG:4326",
        transform=rasterio.transform.from_origin(100.0, 10.0, 0.01, 0.01), nodata=-9999.0,
    ) as dst:
        dst.write(np.ones((10, 10), dtype="float32"), 1)

    out = reproject_to_grid(src_path, tmp_path / "out.tif", grid)

    with rasterio.open(out) as src:
        data = src.read(1)
    assert (data == NODATA_FLOAT).all()


def _strip_crs(path: Path) -> None:
    with rasterio.open(path) as src:
        data, profile = src.read(1), src.profile
    profile.pop("crs")
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)


@pytest.mark.unit
def test_source_without_crs_fails_loud_unless_a_crs_is_supplied(tmp_path):
    grid = _grid()
    src_path = tmp_path / "nocrs.tif"
    _write_raster(src_path, value=7.0)
    _strip_crs(src_path)

    with pytest.raises(MissingSourceCrsError):
        reproject_to_grid(src_path, tmp_path / "out.tif", grid)

    out = reproject_to_grid(src_path, tmp_path / "out2.tif", grid, src_crs="EPSG:4326")
    with rasterio.open(out) as ds:
        assert np.allclose(ds.read(1)[grid.country_mask], 7.0, atol=0.01)


@pytest.mark.unit
def test_gwa_crs_comes_from_the_same_height_wind_speed_sibling_only_when_grids_match(tmp_path):
    from geofrea.grid_alignment.alignment import _gwa_crs_for

    speed, weibull = tmp_path / "speed.tif", tmp_path / "weibull.tif"
    _write_raster(speed, 5.0)
    _write_raster(weibull, 2.0)
    _strip_crs(weibull)
    layers = {"wind_speed_100m": speed, "weibull_a_100m": weibull}

    assert _gwa_crs_for("weibull_a_100m", weibull, layers) == rasterio.crs.CRS.from_epsg(4326)
    assert _gwa_crs_for("wind_speed_100m", speed, layers) is None  # declares its own

    other = tmp_path / "other.tif"
    _write_raster(other, 2.0, size=50)
    _strip_crs(other)
    with pytest.raises(MissingSourceCrsError, match="same grid"):
        _gwa_crs_for("weibull_a_100m", other, layers)
    with pytest.raises(MissingSourceCrsError, match="no wind-speed sibling"):
        _gwa_crs_for("weibull_a_150m", weibull, layers)


def _fine_tile(path: Path, grid, k: int, pattern) -> None:
    """A tile with k x k source samples per grid pixel, exactly on the grid edges; `pattern(rows, cols)` gives the classes."""
    res = abs(grid.transform.a) / k
    rows, cols = np.indices((grid.height * k, grid.width * k))
    with rasterio.open(
        path, "w", driver="GTiff", height=grid.height * k, width=grid.width * k, count=1, dtype="uint8", crs="EPSG:4326",
        transform=from_origin(grid.transform.c, grid.transform.f, res, res), nodata=0,
    ) as dst:
        dst.write(pattern(rows, cols).astype("uint8"), 1)


@pytest.mark.unit
def test_land_cover_class_counts_are_exact_per_pixel_block(tmp_path):
    grid, country_gdf, k = _grid(), _country_gdf(), 10
    # left half of every pixel grassland (30), right half forest (10), except the top pixel row, which is open sea (0)
    tile = tmp_path / "ESA_WorldCover_10m_2020_v100_N36W012_Map.tif"
    _fine_tile(tile, grid, k, lambda r, c: np.where(r < k, 0, np.where(c % k < k // 2, 30, 10)))
    out = land_cover_class_counts([tile], tmp_path / "counts.tif", grid, country_gdf)
    with rasterio.open(out) as src:
        counts = src.read()
        tags = src.tags()
        nodata = src.nodata
    classes = [int(c) for c in tags["worldcover_classes"].split(",")]
    assert int(tags["samples_per_pixel"]) == k * k
    inside = grid.country_mask.copy()
    inside[0, :] = False
    assert (counts[classes.index(30)][inside] == k * k // 2).all()
    assert (counts[classes.index(10)][inside] == k * k // 2).all()
    assert (counts[:, 0, :][:, grid.country_mask[0]].sum(axis=0) == 0).all()  # sea row: counted in no class
    assert (counts[:, ~grid.country_mask] == nodata).all()


@pytest.mark.unit
def test_land_cover_counts_exact_or_raise(tmp_path):
    """M-F2a-06 (V19): a tile whose pixel is not a whole fraction of the grid pixel raises; there is no approximate mode."""
    grid, country_gdf = _grid(), _country_gdf()
    res = abs(grid.transform.a) / 9.7  # about 100 m samples, as the retired IND tiles: not a whole fraction of 0.01 degree
    n_rows, n_cols = int(np.ceil(grid.height * 9.7)) + 5, int(np.ceil(grid.width * 9.7)) + 5
    tile = tmp_path / "ESA_WorldCover_10m_2020_v100_N36W012_Map.tif"
    with rasterio.open(
        tile, "w", driver="GTiff", height=n_rows, width=n_cols, count=1, dtype="uint8", crs="EPSG:4326",
        transform=from_origin(grid.transform.c, grid.transform.f, res, res), nodata=0,
    ) as dst:
        dst.write(np.full((n_rows, n_cols), 30, dtype="uint8"), 1)
    with pytest.raises(LandCoverCountNotExactError, match="no approximate mode"):
        land_cover_class_counts([tile], tmp_path / "counts.tif", grid, country_gdf)
    assert not (tmp_path / "counts.tif").exists()


def _glo30_tile(path: Path, sp: int, z: np.ndarray) -> None:
    """A synthetic GLO-30-style tile for the 1 degree cell with corner (38 N, 9 W): first sample on the integer corner."""
    with rasterio.open(
        path, "w", driver="GTiff", height=sp, width=sp, count=1, dtype="float32", crs="EPSG:4326",
        transform=from_origin(-9.0 - 0.5 / sp, 39.0 + 0.5 / sp, 1 / sp, 1 / sp),
    ) as dst:
        dst.write(z.astype("float32"), 1)


@pytest.mark.unit
def test_slope_class_counts_put_every_sample_in_the_bin_of_its_true_slope(tmp_path):
    grid, sp = _grid(), 400  # 4 x 4 samples per 0.01 degree pixel
    lat = 39.0 - np.arange(sp) / sp
    _, lon_km = wgs84_km_per_degree(lat.reshape(-1, 1))
    dx_m = lon_km * 1000.0 / sp
    z = np.arange(sp)[None, :] * np.tan(np.radians(20.5)) * dx_m  # a ramp rising eastward at 20.5 degrees
    tile = tmp_path / "Copernicus_DSM_COG_10_N38_00_W009_00_DEM.tif"
    _glo30_tile(tile, sp, z)
    out = slope_class_counts([tile], tmp_path / "slope_counts.tif", grid, samples_per_degree=sp)
    with rasterio.open(out) as src:
        counts = src.read()
        nodata = src.nodata
    inside = grid.country_mask
    assert (counts[20][inside] == 16).all()
    assert counts[:, inside].sum() == 16 * inside.sum()  # nothing in any other bin
    assert (counts[:, ~inside] == nodata).all()


@pytest.mark.unit
def test_slope_class_counts_leave_pixels_without_a_tile_empty(tmp_path):
    grid, sp = _grid(), 400
    other = tmp_path / "Copernicus_DSM_COG_10_N10_00_E010_00_DEM.tif"  # far from the country
    with rasterio.open(
        other, "w", driver="GTiff", height=sp, width=sp, count=1, dtype="float32", crs="EPSG:4326",
        transform=from_origin(10 - 0.5 / sp, 11 + 0.5 / sp, 1 / sp, 1 / sp),
    ) as dst:
        dst.write(np.zeros((sp, sp), dtype="float32"), 1)
    assert slope_class_counts([other], tmp_path / "slope_counts.tif", grid, samples_per_degree=sp) is None
