"""COMMAND 187 (OQ-068): F7b evaluates the pixels of the plants by windows of rows and gets, bit for bit, what the whole grid gave.

The oracle is the whole-grid computation F7b used before: `prepare_shared_layers` + `technology_layers` + `eligible_fraction` + `valid_pixels`. The world is
the random one of the F3 stripe tests (land-cover and slope samples, population with gaps, resources with gaps, a country that does not fill its grid,
partial protected areas, rivers, lakes), so that every exclusion and the validity mask do work. The tolerance is 0.
"""

# ruff: noqa: F811, F401  (the `world` fixture is imported and used as an argument)
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from geofrea.config_models.land_availability import load_land_availability
from geofrea.external_validation.exclusion import exclusion_rows
from geofrea.external_validation.pipeline import _unit_table
from geofrea.external_validation.pixels import PixelValues, evaluate_at_pixels
from geofrea.land_eligibility import pipeline
from geofrea.land_eligibility.eligibility import eligible_fraction, valid_pixels
from geofrea.land_eligibility.scenarios import scenario_set
from geofrea.land_eligibility.windows import RasterRows
from tests.unit.test_land_eligibility_stripes import (
    EXPERIMENTS,
    H,
    W,
    world,
)

KEYS = ("E1", "E2", "E3", "E4", "E5", "E6", "combined")


def _oracle(world, tech):
    la = load_land_availability(EXPERIMENTS)
    params = scenario_set(la, tech, "ZZZ", "central")
    interim = world.tmp / "interim_oracle"
    interim.mkdir(exist_ok=True)
    shared = pipeline.prepare_shared_layers(
        la,
        [params],
        world.grid_result,
        world.country,
        world.protected,
        world.lakes,
        world.rivers,
        interim,
    )
    layers, _ = pipeline.technology_layers(shared, tech, world.siting)
    eligible, excl = eligible_fraction(layers, params)
    excluded = {**excl, "combined": (1.0 - eligible).astype("float32")}
    return la, params, excluded, valid_pixels(layers)


def _inputs(world, la, params):
    interim = world.tmp / "interim_windows"
    interim.mkdir(exist_ok=True)
    scratch = world.tmp / "scratch_windows"
    inputs = pipeline.prepare_stripe_inputs(
        la,
        [params],
        world.grid_result,
        world.country,
        world.protected,
        world.lakes,
        world.rivers,
        interim,
        scratch,
    )
    resources = {
        n: RasterRows(p, n, "float32")
        for n, p in pipeline._required_resources("solar", world.siting.layers).items()
    }
    return inputs, resources


@pytest.mark.parametrize("tech", ["solar", "wind"])
@pytest.mark.parametrize("stripe_pixels", [W, 7 * W, 1000, 10_000_000])
def test_every_pixel_of_the_grid_gets_the_whole_grid_value_for_any_window_height(
    world, tech, stripe_pixels
):
    """One row a window, seven rows (a height that does not divide the 60 rows), 25 rows, and the whole grid in one window."""
    la, params, excluded, valid = _oracle(world, tech)
    inputs, _ = _inputs(world, la, params)
    resources = {
        n: RasterRows(p, n, "float32")
        for n, p in pipeline._required_resources(tech, world.siting.layers).items()
    }
    rows, cols = np.divmod(np.arange(H * W), W)
    got, got_valid = evaluate_at_pixels(inputs, resources, params, rows, cols, stripe_pixels)
    for key in KEYS:
        np.testing.assert_array_equal(got[key][rows, cols], excluded[key][rows, cols])
        assert got[key][rows, cols].dtype == excluded[key].dtype
    np.testing.assert_array_equal(got_valid[rows, cols], valid[rows, cols])


def test_plants_in_several_windows_with_repeats_and_in_any_order_get_the_whole_grid_value(world):
    la, params, excluded, valid = _oracle(world, "solar")
    inputs, resources = _inputs(world, la, params)
    rng = np.random.default_rng(187)
    rows = rng.integers(0, H, size=40)
    cols = rng.integers(0, W, size=40)
    rows = np.concatenate([rows, rows[:5], [0, H - 1]])
    cols = np.concatenate([cols, cols[:5], [0, W - 1]])
    got, got_valid = evaluate_at_pixels(inputs, resources, params, rows, cols, 3 * W)
    for key in KEYS:
        np.testing.assert_array_equal(got[key][rows, cols], excluded[key][rows, cols])
    np.testing.assert_array_equal(got_valid[rows, cols], valid[rows, cols])
    # the tables of F7b are the same on the pixel values as on the whole arrays
    units = pd.DataFrame(
        {
            "capacity_mw": rng.uniform(1, 500, size=len(rows)),
            "row": rows,
            "col": cols,
            "in_grid": np.ones(len(rows), dtype=bool),
        }
    )
    dense = exclusion_rows("solar", "operating", units, excluded, valid)
    sparse = exclusion_rows("solar", "operating", units, got, got_valid)
    assert dense == sparse


def test_the_unit_table_is_the_same_on_the_pixel_values_as_on_the_whole_arrays(world):
    la, params, excluded, valid = _oracle(world, "solar")
    inputs, resources = _inputs(world, la, params)
    rng = np.random.default_rng(1870)
    n = 30
    rows, cols = rng.integers(0, H, size=n), rng.integers(0, W, size=n)
    in_grid = rng.uniform(size=n) < 0.9
    units = pd.DataFrame(
        {
            "gem_unit_id": [f"U{i}" for i in range(n)],
            "capacity_mw": rng.uniform(1, 500, size=n),
            "start_year": rng.integers(1990, 2024, size=n).astype("float64"),
            "location_accuracy": ["exact"] * n,
            "lat": rng.uniform(0, 1, size=n),
            "lon": rng.uniform(0, 1, size=n),
            "row": np.where(in_grid, rows, -1),
            "col": np.where(in_grid, cols, -1),
            "in_grid": in_grid,
            "cell_id": pd.Series(
                pd.array(np.where(in_grid, np.arange(n) % 6, 0), dtype="Int64")
            ).where(in_grid, pd.NA),
        }
    )
    ranked = pd.DataFrame({"cell_id": np.arange(6), "decile": [1, 2, 3, 4, 5, 6]})
    got, got_valid = evaluate_at_pixels(
        inputs, resources, params, rows[in_grid], cols[in_grid], 2 * W
    )
    dense = _unit_table("solar", units, excluded, valid, ranked, pd.Series(np.arange(4)))
    sparse = _unit_table("solar", units, got, got_valid, ranked, pd.Series(np.arange(4)))
    pd.testing.assert_frame_equal(dense, sparse, check_exact=True)


def test_a_pixel_that_was_not_evaluated_is_refused_and_no_pixel_gives_empty_values(world):
    la, params, _, _ = _oracle(world, "solar")
    inputs, resources = _inputs(world, la, params)
    got, _ = evaluate_at_pixels(inputs, resources, params, np.array([3]), np.array([4]))
    with pytest.raises(KeyError):
        got["E1"][np.array([3]), np.array([5])]
    assert got["E1"][np.array([], dtype=int), np.array([], dtype=int)].size == 0
    none, none_valid = evaluate_at_pixels(
        inputs, resources, params, np.array([], dtype=int), np.array([], dtype=int)
    )
    assert (
        isinstance(none["combined"], PixelValues)
        and none_valid[np.array([], dtype=int), np.array([], dtype=int)].size == 0
    )
    with pytest.raises(ValueError):
        evaluate_at_pixels(inputs, resources, params, np.array([H]), np.array([0]))
