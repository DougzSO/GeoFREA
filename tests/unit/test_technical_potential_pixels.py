"""The wind capacity factor per 0.01 degree pixel, aggregated to the cell by the eligible area of each pixel (M-F5-03, D-F5-038)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio

from geofrea.core.constants import (
    CELL_DEG,
    CELL_NESTING_PIXELS,
    CELL_ORIGIN_LAT,
    CELL_ORIGIN_LON,
    ISA_T0_K,
    RHO0_KG_M3,
)
from geofrea.land_eligibility.cells import cell_id, pixel_row_area_km2
from geofrea.technical_potential import cf_models
from geofrea.technical_potential.cf_models import CfModelError, CfSettings, get_cf_model
from geofrea.technical_potential.pixel_inputs import PixelInputError, read_cell_pixels
from geofrea.technical_potential.power_curve import load_power_curve
from geofrea.technical_potential.weibull_cf import wind_cf_member
from geofrea.technical_potential.wind_profile import resource_at_hub_height

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]
CURVE = load_power_curve(REPO / "tests" / "fixtures" / "power_curves" / "synthetic_curve.yaml")
K = CELL_NESTING_PIXELS
PIXEL_DEG = CELL_DEG / K
ROW0, COL0 = 1000, 2000
N_CELL_ROWS, N_CELL_COLS = 2, 3
H, W = N_CELL_ROWS * K, N_CELL_COLS * K
TRANSFORM = rasterio.Affine(
    PIXEL_DEG, 0.0, CELL_ORIGIN_LON + COL0 * CELL_DEG, 0.0, -PIXEL_DEG, CELL_ORIGIN_LAT - ROW0 * CELL_DEG
)
HEIGHTS = (100, 150, 200)
PRODUCTS = ("weibull_a", "weibull_k", "air_density")
LAYERS = tuple(f"{p}_{h}m" for p in PRODUCTS for h in HEIGHTS)
HUB_M = 125.0  # between two data heights: the interpolation runs on the pixels
SETTINGS = CfSettings(
    parameters={"eta_loss": 0.85, "hub_height_m": HUB_M},
    curve=CURVE,
    class_flag=None,
    resource_layers=LAYERS,
    rho0=RHO0_KG_M3,
    t_star_k=ISA_T0_K,
    hours_per_day=24.0,
)


def _write(path: Path, grid: np.ndarray) -> Path:
    with rasterio.open(
        path, "w", driver="GTiff", dtype="float32", count=1, nodata=-9999.0, crs="EPSG:4326",
        transform=TRANSFORM, height=H, width=W,
    ) as dst:  # fmt: skip
        dst.write(np.where(np.isfinite(grid), grid, -9999.0).astype("float32"), 1)
    return path


@pytest.fixture
def world(tmp_path):
    """Six cells (2 x 3); a different fraction, scale, shape and density in every pixel."""
    rng = np.random.default_rng(74)
    fraction = rng.uniform(0.2, 1.0, (H, W))
    fraction[:K, :K] = 0.0  # the first cell has no eligible pixel at all (not a candidate)
    fraction[K : K + 2, K : 2 * K] = 0.0  # two rows of the fifth cell are not eligible
    base = {
        "weibull_a": rng.uniform(5.0, 11.0, (H, W)),
        "weibull_k": rng.uniform(1.6, 2.8, (H, W)),
        "air_density": rng.uniform(1.0, 1.2, (H, W)),
    }
    # the three heights differ by smooth, pixel-dependent factors: the interpolation to the hub height is not trivial
    grids = {
        f"{p}_{h}m": base[p] * (1.0 + {"weibull_a": 0.08, "weibull_k": 0.03, "air_density": -0.01}[p] * (h - 100) / 50.0)
        for p in PRODUCTS
        for h in HEIGHTS
    }
    paths = {"fraction": _write(tmp_path / "fraction.tif", fraction)}
    paths.update({name: _write(tmp_path / f"{name}.tif", grid) for name, grid in grids.items()})
    area = (
        np.where(np.isfinite(fraction), fraction, 0.0).astype("float32").astype("float64")
        * pixel_row_area_km2(TRANSFORM, H)[:, None]
    )
    rows, cols = np.meshgrid(np.arange(N_CELL_ROWS), np.arange(N_CELL_COLS), indexing="ij")
    cells = pd.DataFrame(
        {
            "cell_id": cell_id(ROW0 + rows.ravel(), COL0 + cols.ravel()),
            "row": ROW0 + rows.ravel(),
            "col": COL0 + cols.ravel(),
        }
    )
    blocks = area.reshape(N_CELL_ROWS, K, N_CELL_COLS, K)
    cells["eligible_area_km2"] = blocks.sum(axis=(1, 3)).ravel()
    cells = cells[cells["eligible_area_km2"] > 0].reset_index(drop=True)
    return {"paths": paths, "cells": cells, "fraction": fraction, "grids": grids, "area": area}


def _pixels(world):
    return read_cell_pixels(
        world["cells"],
        world["paths"]["fraction"],
        {n: world["paths"][n] for n in LAYERS},
    )


def _mean_columns(world, pixels) -> pd.DataFrame:
    """The candidate table of F3: the eligible-area-weighted mean of every resource per cell."""
    cells = world["cells"].copy()
    cell_of = np.repeat(np.arange(len(cells)), pixels.counts)
    total = np.bincount(cell_of, weights=pixels.weight_km2)
    for name in LAYERS:
        cells[name] = np.bincount(cell_of, weights=pixels.weight_km2 * pixels.resources[name]) / total
    return cells


def _oracle(world, d_t: float, delta_wind: float) -> np.ndarray:
    """One loop over cells and pixels, with the scalar function of the model: the definition of the aggregation."""
    out = []
    for _, cell in world["cells"].iterrows():
        r, c = int(cell["row"]) - ROW0, int(cell["col"]) - COL0
        num = den = 0.0
        for i in range(K):
            for j in range(K):
                y, x = r * K + i, c * K + j
                w = world["area"][y, x]
                if w <= 0:
                    continue
                at = {
                    p: {h: np.array([world["grids"][f"{p}_{h}m"][y, x]], dtype="float32").astype("float64") for h in HEIGHTS}
                    for p in PRODUCTS
                }
                a_h, k_h, rho_h = resource_at_hub_height(at["weibull_a"], at["weibull_k"], at["air_density"], HUB_M)
                cf = wind_cf_member(
                    a_h, k_h, rho_h, np.array([d_t]), np.array([delta_wind]), CURVE, 0.85, RHO0_KG_M3, ISA_T0_K
                )[0]
                num += w * cf
                den += w
        out.append(num / den)
    return np.array(out)


def test_only_the_eligible_pixels_of_each_candidate_cell_are_read_in_the_order_of_the_table(world):
    pixels = _pixels(world)
    assert len(pixels.offsets) == len(world["cells"]) + 1
    assert (pixels.weight_km2 > 0).all()
    per_cell = np.add.reduceat(pixels.weight_km2, pixels.offsets[:-1])
    np.testing.assert_allclose(per_cell, world["cells"]["eligible_area_km2"], rtol=1e-12)
    # the fifth cell lost two rows of five pixels
    assert pixels.counts.min() == 15  # the cell that lost two rows of five pixels
    assert len(pixels.counts) == N_CELL_ROWS * N_CELL_COLS - 1  # the first cell has no eligible pixel and is not a candidate
    assert set(pixels.resources) == set(LAYERS)


def test_a_pixel_without_a_finite_resource_leaves_the_cell_mean_as_f3_defines_it(world, tmp_path):
    broken = world["grids"]["weibull_a_100m"].copy()
    broken[K + 3, 2 * K + 1] = np.nan  # an eligible pixel of the last cell
    path = _write(tmp_path / "a_broken.tif", broken)
    paths = {**{n: world["paths"][n] for n in LAYERS}, "weibull_a_100m": path}
    cells = world["cells"].copy()
    cells.loc[cells.index[-1], "eligible_area_km2"] -= world["area"][K + 3, 2 * K + 1]
    pixels = read_cell_pixels(cells, world["paths"]["fraction"], paths)
    assert np.isfinite(pixels.resources["weibull_a_100m"]).all()
    assert pixels.counts[-1] == _pixels(world).counts[-1] - 1


def test_a_cell_outside_the_raster_is_refused(world):
    cells = world["cells"].copy()
    cells.loc[0, "row"] = ROW0 + 50
    with pytest.raises(PixelInputError, match="outside the raster"):
        read_cell_pixels(cells, world["paths"]["fraction"], {n: world["paths"][n] for n in LAYERS})


def test_a_candidate_cell_without_an_eligible_pixel_is_refused(world):
    cells = pd.concat(
        [
            world["cells"],
            pd.DataFrame(
                {"cell_id": [cell_id(ROW0, COL0)], "row": [ROW0], "col": [COL0], "eligible_area_km2": [5.0]}
            ),
        ],
        ignore_index=True,
    )
    with pytest.raises(PixelInputError, match="no eligible pixel"):
        read_cell_pixels(cells, world["paths"]["fraction"], {n: world["paths"][n] for n in LAYERS})


def test_a_resource_raster_on_another_grid_is_refused(world, tmp_path):
    other = tmp_path / "other.tif"
    with rasterio.open(
        other, "w", driver="GTiff", dtype="float32", count=1, crs="EPSG:4326",
        transform=TRANSFORM * rasterio.Affine.translation(1, 0), height=H, width=W,
    ) as dst:  # fmt: skip
        dst.write(np.ones((H, W), dtype="float32"), 1)
    paths = {n: world["paths"][n] for n in LAYERS} | {"weibull_k_100m": other}
    with pytest.raises(PixelInputError, match="not on the grid"):
        read_cell_pixels(world["cells"], world["paths"]["fraction"], paths)


@pytest.mark.parametrize(("d_t", "delta_wind"), [(0.0, 1.0), (2.5, 0.93)])
def test_the_cell_capacity_factor_is_the_area_weighted_mean_of_the_pixel_factors(world, d_t, delta_wind):
    pixels = _pixels(world)
    candidates = _mean_columns(world, pixels)
    prepared = get_cf_model("weibull_with_air_density").prepare_pixels(candidates, SETTINGS, pixels)
    rows = np.arange(len(candidates))
    cf = prepared.member(rows, np.ones(len(rows)), np.full(len(rows), d_t), np.full(len(rows), delta_wind))
    np.testing.assert_allclose(cf, _oracle(world, d_t, delta_wind), rtol=1e-12)


def test_the_result_does_not_depend_on_the_size_of_the_blocks_nor_on_the_rows_asked(world, monkeypatch):
    pixels = _pixels(world)
    candidates = _mean_columns(world, pixels)
    prepared = get_cf_model("weibull_with_air_density").prepare_pixels(candidates, SETTINGS, pixels)
    rows = np.array([4, 0, 2])
    d_t, wind = np.array([0.0, 1.0, 3.0]), np.array([1.0, 0.9, 1.1])
    whole = prepared.member(rows, np.ones(3), d_t, wind)
    monkeypatch.setattr(cf_models, "PIXELS_PER_BLOCK", 30)  # a block holds one or two cells
    in_blocks = prepared.member(rows, np.ones(3), d_t, wind)
    np.testing.assert_array_equal(whole, in_blocks)
    monkeypatch.setattr(cf_models, "PIXELS_PER_BLOCK", 1)  # one cell per block, whatever its size
    np.testing.assert_array_equal(whole, prepared.member(rows, np.ones(3), d_t, wind))
    single = prepared.member(np.array([2]), np.ones(1), np.array([3.0]), np.array([1.1]))
    assert single[0] == whole[2]


def test_a_cell_of_identical_pixels_has_the_factor_of_its_mean(world, tmp_path):
    value = {"weibull_a": 8.0, "weibull_k": 2.0, "air_density": 1.1}
    flat = {
        f"{p}_{h}m": _write(tmp_path / f"{p}_{h}m_flat.tif", np.full((H, W), value[p] * (1.0 + 0.02 * (h - 100) / 50.0)))
        for p in PRODUCTS
        for h in HEIGHTS
    }
    cells = world["cells"]
    pixels = read_cell_pixels(cells, world["paths"]["fraction"], flat)
    candidates = _mean_columns(world, pixels)
    model = get_cf_model("weibull_with_air_density")
    rows = np.arange(len(cells))
    args = (rows, np.ones(len(rows)), np.full(len(rows), 1.0), np.full(len(rows), 1.0))
    by_pixel = model.prepare_pixels(candidates, SETTINGS, pixels).member(*args)
    by_mean = model.prepare(candidates, SETTINGS).member(*args)
    np.testing.assert_allclose(by_pixel, by_mean, rtol=1e-6)  # the float32 of the rasters


def test_the_density_check_and_the_class_flag_keep_reading_the_cell_means(world):
    pixels = _pixels(world)
    candidates = _mean_columns(world, pixels)
    model = get_cf_model("weibull_with_air_density")
    cell = model.prepare(candidates, SETTINGS)
    prepared = model.prepare_pixels(candidates, SETTINGS, pixels)
    np.testing.assert_array_equal(prepared.rho_ref, cell.rho_ref)
    assert prepared.class_flag is cell.class_flag and prepared.v_ave_ms is cell.v_ave_ms


def test_a_model_evaluated_on_the_cell_means_refuses_the_pixels_and_the_registry_names_each_aggregation():
    assert get_cf_model("weibull_with_air_density").aggregation == "pixel"
    assert get_cf_model("pvout_with_temperature").aggregation == "cell"
    with pytest.raises(CfModelError, match="cell means"):
        get_cf_model("pvout_with_temperature").prepare_pixels(pd.DataFrame(), SETTINGS, None)
