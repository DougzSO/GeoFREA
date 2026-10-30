"""The wind capacity factor integral by table: error against the exact integral, the grid, the cache, the option (D-F5-039, COMMAND 75)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pytest

from geofrea.technical_potential import cf_table
from geofrea.technical_potential.cf_models import get_cf_model
from geofrea.technical_potential.cf_table import (
    A_MAX_MS,
    K_MAX,
    K_MIN,
    TabulatedIntegral,
    cf_integral,
    table_key,
)
from geofrea.technical_potential.power_curve import load_power_curve
from geofrea.technical_potential.weibull_cf import weibull_capacity_factor, wind_cf_member
from tests.unit.test_technical_potential_pixels import (
    CURVE as SYNTHETIC_CURVE,
)
from tests.unit.test_technical_potential_pixels import (
    N_CELL_COLS,
    N_CELL_ROWS,
    SETTINGS,
    _mean_columns,
    _pixels,
    world,
)

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]
IEA = load_power_curve(REPO / "config" / "turbines" / "iea_3.4_130.csv")
TOLERANCE = 1e-5  # absolute, in the capacity factor (COMMAND 75)


@pytest.fixture(scope="module")
def tables():
    """The table of each curve, built once for the module."""
    return {"iea": TabulatedIntegral(IEA), "synthetic": TabulatedIntegral(SYNTHETIC_CURVE)}


def _points(n, a_range, k_range, seed):
    rng = np.random.default_rng(seed)
    return rng.uniform(*a_range, n), rng.uniform(*k_range, n)


@pytest.mark.parametrize("curve_name, curve", [("iea", IEA), ("synthetic", SYNTHETIC_CURVE)])
def test_the_table_is_within_the_tolerance_of_the_exact_integral_over_the_whole_validity_domain(tables, curve_name, curve):
    a, k = _points(200_000, (0.01, A_MAX_MS), (K_MIN, K_MAX), 1)
    error = np.abs(tables[curve_name](a, k) - weibull_capacity_factor(a, k, curve))
    assert error.max() <= TOLERANCE, f"largest error {error.max():.2e}"


def test_the_table_is_far_inside_the_tolerance_where_the_resource_is(tables):
    a, k = _points(200_000, (2.0, 25.0), (1.0, 4.0), 2)
    error = np.abs(tables["iea"](a, k) - weibull_capacity_factor(a, k, IEA))
    assert error.max() <= 1e-7, f"largest error {error.max():.2e}"


def test_a_point_outside_the_grid_is_evaluated_exactly(tables):
    a = np.array([A_MAX_MS + 3.0, 10.0, 10.0])
    k = np.array([2.0, K_MAX + 1.5, K_MIN - 0.1])
    np.testing.assert_array_equal(tables["iea"](a, k), weibull_capacity_factor(a, k, IEA))


def test_the_table_keeps_the_input_checks_of_the_integral(tables):
    for bad_a, bad_k in ((0.0, 2.0), (8.0, -1.0), (np.nan, 2.0)):
        with pytest.raises(ValueError):
            tables["iea"](np.array([bad_a]), np.array([bad_k]))


def test_the_capacity_factor_stays_in_zero_one(tables):
    a = np.linspace(0.05, A_MAX_MS, 5000)
    for k in (0.55, 1.0, 2.1, 6.0, 9.9):
        cf = tables["iea"](a, np.full_like(a, k))
        assert cf.min() >= 0.0 and cf.max() <= 1.0


def test_the_key_follows_the_curve_and_is_stable():
    assert table_key(IEA) == table_key(IEA)
    assert table_key(IEA) != table_key(SYNTHETIC_CURVE)
    changed = IEA.model_copy(update={"p_kw": [*IEA.p_kw[:-1], IEA.p_kw[-1] * 0.99]})
    assert table_key(changed) != table_key(IEA)


def test_the_table_is_stored_once_and_read_back(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    built = []
    real = cf_table.build_table
    monkeypatch.setattr(cf_table, "build_table", lambda curve: built.append(1) or real(curve))
    first = cf_table.load_or_build_table(SYNTHETIC_CURVE)
    second = cf_table.load_or_build_table(SYNTHETIC_CURVE)
    assert len(built) == 1
    np.testing.assert_array_equal(first, second)
    stored = list((tmp_path / "interim" / "cf_tables").glob("cf_table_*.npy"))
    assert len(stored) == 1 and table_key(SYNTHETIC_CURVE)[:24] in stored[0].name


def test_a_corrupt_stored_table_is_built_again(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    first = cf_table.load_or_build_table(SYNTHETIC_CURVE)
    stored = next((tmp_path / "interim" / "cf_tables").glob("cf_table_*.npy"))
    stored.write_bytes(b"not a table")
    np.testing.assert_array_equal(cf_table.load_or_build_table(SYNTHETIC_CURVE), first)


def test_the_option_chooses_the_function_and_refuses_another_value():
    a, k = np.array([8.0, 10.5]), np.array([2.0, 2.4])
    np.testing.assert_array_equal(cf_integral(IEA, "exact")(a, k), weibull_capacity_factor(a, k, IEA))
    assert abs(cf_integral(IEA, "table")(a, k) - weibull_capacity_factor(a, k, IEA)).max() <= TOLERANCE
    with pytest.raises(ValueError, match="wind_cf_integral"):
        cf_integral(IEA, "fast")


def test_the_member_capacity_factor_with_the_table_is_within_the_tolerance_of_the_exact_one(tables):
    rng = np.random.default_rng(5)
    n = 50_000
    args = (
        rng.uniform(5, 12, n), rng.uniform(1.4, 3.2, n), rng.uniform(1.0, 1.25, n),
        rng.uniform(0.0, 5.0, n), rng.uniform(0.85, 1.2, n), IEA, 0.866, 1.225, 288.15,
    )  # fmt: skip
    exact = wind_cf_member(*args)
    tabulated = wind_cf_member(*args, integral=tables["iea"])
    assert np.abs(tabulated - exact).max() <= TOLERANCE * 0.866


def test_the_cell_value_aggregated_from_the_pixels_agrees_between_the_table_and_the_exact_integral(world):
    """The cell energy follows the tolerance as well: the aggregation is a weighted mean, so the error of the mean is at most the largest pixel error."""
    pixels = _pixels(world)
    candidates = _mean_columns(world, pixels)
    model = get_cf_model("weibull_with_air_density")
    exact = model.prepare_pixels(candidates, SETTINGS, pixels)
    tabulated = model.prepare_pixels(candidates, dataclasses.replace(SETTINGS, wind_cf_integral="table"), pixels)
    rows = np.arange(len(candidates))
    d_t, delta_wind = np.full(len(rows), 2.0), np.full(len(rows), 1.05)
    ones = np.ones(len(rows))
    difference = np.abs(tabulated.member(rows, ones, d_t, delta_wind) - exact.member(rows, ones, d_t, delta_wind))
    assert difference.max() <= TOLERANCE
    assert N_CELL_ROWS * N_CELL_COLS - 1 == len(rows)


def test_the_option_of_the_settings_file_is_validated_and_defaults_to_the_exact_integral():
    from pydantic import ValidationError

    from geofrea.core.schemas import SettingsFile

    from geofrea.core.config_loader import load_settings

    settings = load_settings(REPO / "config" / "settings.yaml")
    assert settings.wind_cf_integral == "table"  # the setting of the runs
    raw = {"run": settings.run.model_dump(), "geospatial": settings.geospatial.model_dump(), "memory": settings.memory.model_dump(), "figures": "summary"}
    assert SettingsFile.model_validate(raw).wind_cf_integral == "exact"  # the API default is the closed form
    with pytest.raises(ValidationError):
        SettingsFile.model_validate({**raw, "wind_cf_integral": "fast"})
