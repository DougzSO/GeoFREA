"""Unit tests for geofrea.grid_alignment.raster_alignment.derive_slope_from_dem.

Slope parity is checked against an INDEPENDENT analytic reference (a
planar DEM has a closed-form slope), NOT against the legacy's
`*_slope_aligned.tif` — we cannot confirm that file was produced by the
same origin pipeline (see docs/DECISIONS.md 2026-09-11).

The nodata-adjacency test is the point of the data-integrity correction:
it FAILS against a naive port of the legacy (which feeds -9999 into
numpy.gradient) and PASSES with the fix (nodata -> NaN before the
gradient, so contaminated pixels become nodata, not a wrong number).
"""

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from geofrea.core.constants import KM_PER_DEG_LAT, NODATA_FLOAT
from geofrea.grid_alignment.raster_alignment import derive_slope_from_dem

# Raster placed on the equator so cos(lat) == 1 and the E-W pixel size is
# exactly res_x * KM_PER_DEG_LAT * 1000 m — makes the analytic slope of a
# planar DEM a single number for every interior pixel.
_RES = 0.01
_ORIGIN_LON, _ORIGIN_LAT = 0.0, 0.03  # 6 rows span lat +0.03 .. -0.03, centred on 0
_DX_M = _RES * KM_PER_DEG_LAT * 1000.0


def _write_dem(path, data, nodata=NODATA_FLOAT):
    data = np.asarray(data, dtype=np.float32)
    with rasterio.open(
        path, "w", driver="GTiff", height=data.shape[0], width=data.shape[1],
        count=1, dtype="float32", crs="EPSG:4326",
        transform=from_origin(_ORIGIN_LON, _ORIGIN_LAT, _RES, _RES), nodata=nodata,
    ) as dst:
        dst.write(data, 1)
    return path


def _read(path):
    with rasterio.open(path) as src:
        return src.read(1), src.nodata


@pytest.mark.unit
def test_derive_slope_planar_dem_matches_analytic_reference(tmp_path):
    # z = STEP per column, flat in the row direction -> pure E-W gradient
    # STEP / dx_m, so slope = degrees(arctan(STEP / dx_m)) everywhere.
    step = 5.0
    ncols = 8
    z = np.tile(np.arange(ncols, dtype=np.float32) * step, (7, 1))
    dem = _write_dem(tmp_path / "plane.tif", z)

    out = derive_slope_from_dem(dem, tmp_path / "slope.tif")
    slope, _nd = _read(out)

    expected = np.degrees(np.arctan(step / _DX_M))
    # every pixel (a plane's one-sided edge difference equals its central
    # difference, so the border matches too)
    assert np.allclose(slope, expected, atol=1e-4)


@pytest.mark.unit
def test_derive_slope_flat_dem_is_zero(tmp_path):
    dem = _write_dem(tmp_path / "flat.tif", np.full((6, 6), 200.0, dtype=np.float32))
    slope, _nd = _read(derive_slope_from_dem(dem, tmp_path / "slope.tif"))
    assert np.allclose(slope, 0.0, atol=1e-6)


@pytest.mark.unit
def test_derive_slope_outer_edge_pixels_are_finite_and_correct(tmp_path):
    # A tilted plane in BOTH directions; np.gradient uses one-sided
    # differences on the true raster border. For a plane those still equal
    # the exact gradient, so the border must be finite and match interior.
    rows, cols = 6, 6
    ii, jj = np.meshgrid(np.arange(rows), np.arange(cols), indexing="ij")
    z = (3.0 * jj + 2.0 * ii).astype(np.float32)
    dem = _write_dem(tmp_path / "tilt.tif", z)

    slope, nd = _read(derive_slope_from_dem(dem, tmp_path / "slope.tif"))

    assert np.isfinite(slope).all()
    assert (slope != nd).all()
    # top-left corner, top edge, left edge all equal the interior value
    assert slope[0, 0] == pytest.approx(slope[rows // 2, cols // 2], abs=1e-4)
    assert slope[0, cols // 2] == pytest.approx(slope[rows // 2, cols // 2], abs=1e-4)
    assert slope[rows // 2, 0] == pytest.approx(slope[rows // 2, cols // 2], abs=1e-4)


@pytest.mark.unit
def test_derive_slope_valid_pixel_next_to_nodata_is_not_contaminated(tmp_path):
    # Planar DEM with ONE nodata cell at [2, 2]. A naive legacy port feeds
    # -9999 into np.gradient, so the 4-neighbours of [2, 2] get a huge
    # bogus slope (~90 deg). The corrected version masks nodata BEFORE the
    # gradient, so those 4-neighbours (and [2, 2] itself) are nodata, and
    # every pixel whose stencil never touched [2, 2] keeps the clean
    # planar slope.
    step = 4.0
    rows, cols = 6, 7
    z = np.tile(np.arange(cols, dtype=np.float32) * step, (rows, 1))
    z[2, 2] = NODATA_FLOAT
    dem = _write_dem(tmp_path / "hole.tif", z)

    slope, nd = _read(derive_slope_from_dem(dem, tmp_path / "slope.tif"))
    planar = np.degrees(np.arctan(step / _DX_M))

    # the nodata cell and its 4-connected neighbours: nodata, NOT a number
    assert slope[2, 2] == nd
    for r, c in ((1, 2), (3, 2), (2, 1), (2, 3)):
        assert slope[r, c] == nd, f"({r},{c}) leaked nodata contamination: {slope[r, c]}"
        assert slope[r, c] != pytest.approx(90.0, abs=1.0)

    # a diagonal neighbour never enters [2,2]'s central-difference stencil
    assert slope[1, 1] == pytest.approx(planar, abs=1e-4)
    # and a pixel well away from the hole is untouched
    assert slope[4, 5] == pytest.approx(planar, abs=1e-4)


@pytest.mark.unit
def test_derive_slope_preserves_nodata_value_and_dtype(tmp_path):
    z = np.tile(np.arange(6, dtype=np.float32) * 3.0, (6, 1))
    z[0, 0] = NODATA_FLOAT
    dem = _write_dem(tmp_path / "d.tif", z, nodata=NODATA_FLOAT)

    out = derive_slope_from_dem(dem, tmp_path / "s.tif")
    with rasterio.open(out) as src:
        assert src.dtypes[0] == "float32"
        assert src.nodata == NODATA_FLOAT
        assert src.profile["compress"].lower() == "lzw"


@pytest.mark.unit
def test_derive_slope_returns_none_for_degenerate_dem(tmp_path):
    dem = _write_dem(tmp_path / "row.tif", np.array([[1.0, 2.0, 3.0]], dtype=np.float32))
    assert derive_slope_from_dem(dem, tmp_path / "s.tif") is None


@pytest.mark.unit
def test_derive_slope_block_seam_matches_single_block(tmp_path):
    # Force >1 block by monkeypatching the block height down, and confirm
    # the +/-1 padding makes seam pixels identical to a single-block run.
    import geofrea.grid_alignment.raster_alignment as ra

    rng = np.random.default_rng(0)
    z = (rng.standard_normal((40, 12)) * 50.0 + 500.0).astype(np.float32)
    dem = _write_dem(tmp_path / "rough.tif", z)

    full, _ = _read(derive_slope_from_dem(dem, tmp_path / "full.tif"))

    original = ra._SLOPE_BLOCK_HEIGHT
    try:
        ra._SLOPE_BLOCK_HEIGHT = 8
        blocked, _ = _read(derive_slope_from_dem(dem, tmp_path / "blocked.tif"))
    finally:
        ra._SLOPE_BLOCK_HEIGHT = original

    assert np.allclose(full, blocked, atol=1e-5, equal_nan=True)
