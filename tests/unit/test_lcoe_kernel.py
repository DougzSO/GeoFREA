"""The pure LCOE kernel (M-F6-01, M-F6-05, V-02): closed forms, the textbook reference, limits and the domain checks."""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from geofrea.lcoe_modeling import kernel
from geofrea.lcoe_modeling.kernel import (
    CellInputs,
    KernelInputError,
    SampleInputs,
    annuity_factor,
    capital_recovery_factor,
    energy_annuity_factor,
    lcoe_block,
    lcoe_direct,
)

KERNEL_FILE = Path(kernel.__file__)


def _cells(p, dg, dr, e, offset=None, slope=None):
    p = np.atleast_1d(np.asarray(p, dtype="float64"))
    n = len(p)
    return CellInputs(
        p_mw=p,
        dist_grid_km=np.broadcast_to(np.asarray(dg, dtype="float64"), n).copy(),
        dist_road_km=np.broadcast_to(np.asarray(dr, dtype="float64"), n).copy(),
        energy_mwh=np.broadcast_to(np.asarray(e, dtype="float64"), n).copy(),
        energy_offset=np.ones(n) if offset is None else np.asarray(offset, dtype="float64"),
        energy_slope=np.zeros(n) if slope is None else np.asarray(slope, dtype="float64"),
    )


def _samples(**kw):
    base = {
        "capex_usd_per_kw": 1000.0,
        "opex_fixed_frac": 0.05,
        "opex_var_usd_per_mwh": 0.0,
        "lifetime_years": 20.0,
        "discount_rate": 0.05,
        "degradation_rate": 0.0,
        "grid_cost_usd_per_mw_km": 1000.0,
        "substation_cost_usd_per_mw": 20000.0,
        "road_cost_usd_per_km": 50000.0,
        "energy_parameter": 0.9,
    }
    base.update(kw)
    n = max(np.size(v) for v in base.values())
    return SampleInputs.from_mapping(base, n)


def _crf(r, n):
    return r * (1 + r) ** n / ((1 + r) ** n - 1)


# -- closed forms (V-02) ----------------------------------------------------------------------------


@pytest.mark.unit
def test_crf_and_annuity_match_the_explicit_sum_and_the_tabulated_value():
    assert float(capital_recovery_factor(0.05, 20)) == pytest.approx(0.0802425872, rel=1e-8)
    for r, n in [(0.05, 20), (0.0708, 25), (0.01, 30), (0.2, 5)]:
        explicit = sum((1 + r) ** -t for t in range(1, n + 1))
        assert float(annuity_factor(r, n)) == pytest.approx(explicit, rel=1e-12)
        assert float(capital_recovery_factor(r, n)) == pytest.approx(1 / explicit, rel=1e-12)
        assert float(capital_recovery_factor(r, n)) == pytest.approx(_crf(r, n), rel=1e-12)


@pytest.mark.unit
def test_zero_discount_rate_is_the_limit_of_the_formula_with_no_division_by_zero():
    with np.errstate(all="raise"):  # a hidden 0/0 would raise here
        assert float(annuity_factor(0.0, 25)) == 25.0
        assert float(capital_recovery_factor(0.0, 25)) == pytest.approx(1 / 25)
        assert float(energy_annuity_factor(0.0, 0.0, 25)) == 25.0
    assert float(annuity_factor(1e-13, 25)) == pytest.approx(
        25.0, rel=1e-9
    )  # continuity at the limit
    assert float(energy_annuity_factor(0.0, 0.01, 25)) == pytest.approx(
        sum(0.99 ** (t - 1) for t in range(1, 26)), rel=1e-12
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("r", "d", "n"),
    [
        (0.05, 0.0, 20),
        (0.05, 0.005, 25),
        (0.0, 0.02, 10),
        (0.077, 0.01, 30),
        (0.03, 0.03, 15),
        (0.02, 0.0, 1),
    ],
)
def test_energy_annuity_matches_the_explicit_degraded_sum(r, d, n):
    explicit = sum((1 - d) ** (t - 1) / (1 + r) ** t for t in range(1, n + 1))
    assert float(energy_annuity_factor(r, d, n)) == pytest.approx(explicit, rel=1e-12)


@pytest.mark.unit
def test_without_degradation_and_with_constant_opex_the_lcoe_is_the_crf_form():
    """V-02: `LCOE = (CAPEX * CRF + OPEX) / E` for `d = 0`, constant OPEX and no variable O&M."""
    p, dg, dr, e = 10.0, 20.0, 5.0, 30000.0
    capex = p * 1000 * 1000.0 + p * dg * 1000.0 + p * 20000.0 + dr * 50000.0  # 1.065e7
    assert capex == pytest.approx(10_650_000.0)
    opex = 0.05 * p * 1000 * 1000.0  # fixed O&M on the plant cost only
    expected = (capex * _crf(0.05, 20) + opex) / e
    got = lcoe_block(_cells(p, dg, dr, e), _samples())
    assert got.shape == (1, 1)
    assert float(got[0, 0]) == pytest.approx(expected, rel=1e-12)
    assert float(lcoe_direct(_cells(p, dg, dr, e), _samples())[0, 0]) == pytest.approx(
        expected, rel=1e-12
    )


@pytest.mark.unit
def test_at_a_zero_discount_rate_the_lcoe_is_total_cost_over_total_energy():
    """V-02: `r -> 0` gives `(CAPEX + n * OPEX) / (n * E)`."""
    p, dg, dr, e, n = 10.0, 20.0, 5.0, 30000.0, 20
    capex = p * 1000 * 1000.0 + p * dg * 1000.0 + p * 20000.0 + dr * 50000.0
    opex = 0.05 * p * 1000 * 1000.0
    expected = (capex + n * opex) / (n * e)
    for fn in (lcoe_block, lcoe_direct):
        got = fn(_cells(p, dg, dr, e), _samples(discount_rate=0.0, lifetime_years=float(n)))
        assert float(got[0, 0]) == pytest.approx(expected, rel=1e-12)


@pytest.mark.unit
def test_zero_energy_gives_plus_infinity_not_an_error_and_other_cells_stay_finite():
    cells = _cells([10.0, 10.0, 0.0], [5.0, 5.0, 5.0], [1.0, 1.0, 1.0], [0.0, 30000.0, 0.0])
    for fn in (lcoe_block, lcoe_direct):
        got = fn(cells, _samples(opex_var_usd_per_mwh=[0.0, 3.0]))
        assert (
            np.isposinf(got[0]).all() and np.isposinf(got[2]).all()
        )  # E = 0 with and without cost
        assert np.isfinite(got[1]).all()


@pytest.mark.unit
def test_energy_that_is_zero_only_at_one_sample_is_infinite_only_there():
    """Solar-like terms: the factor is `a + b * x`; at `x` where it vanishes the energy is zero."""
    cells = _cells([5.0], [1.0], [1.0], [1000.0], offset=[1.0], slope=[1.0])  # factor 1 + x
    got = lcoe_block(cells, _samples(energy_parameter=[-1.0, 0.0, 1.0]))
    assert np.isposinf(got[0, 0]) and np.isfinite(got[0, 1:]).all()


@pytest.mark.unit
def test_variable_om_adds_exactly_its_value_because_it_cancels_against_the_energy_denominator():
    cells = _cells([10.0, 4.0], [20.0, 80.0], [5.0, 1.0], [30000.0, 9000.0])
    base = lcoe_block(cells, _samples(degradation_rate=0.01))
    more = lcoe_block(cells, _samples(degradation_rate=0.01, opex_var_usd_per_mwh=7.5))
    np.testing.assert_allclose(more - base, 7.5, rtol=1e-12, atol=1e-9)


# -- the factored kernel against the textbook form ------------------------------------------------------


def _random_problem(seed, n_cells=40, n_samples=30):
    rng = np.random.default_rng(seed)
    cells = CellInputs(
        p_mw=rng.uniform(0.5, 400.0, n_cells),
        dist_grid_km=rng.uniform(0.0, 250.0, n_cells),
        dist_road_km=rng.uniform(0.0, 60.0, n_cells),
        energy_mwh=rng.uniform(1e3, 1e6, n_cells),
        energy_offset=rng.uniform(0.9, 1.1, n_cells),
        energy_slope=rng.uniform(-0.3, 0.3, n_cells),
    )
    samples = SampleInputs(
        capex_usd_per_kw=rng.uniform(600, 1800, n_samples),
        opex_fixed_frac=rng.uniform(0.005, 0.05, n_samples),
        opex_var_usd_per_mwh=rng.uniform(0, 6, n_samples),
        lifetime_years=rng.integers(15, 36, n_samples).astype(float),
        discount_rate=rng.choice([0.0, 0.03, 0.05, 0.08, 0.12], n_samples),
        degradation_rate=rng.uniform(0.0, 0.015, n_samples),
        grid_cost_usd_per_mw_km=rng.uniform(300, 2500, n_samples),
        substation_cost_usd_per_mw=rng.uniform(5e3, 6e4, n_samples),
        road_cost_usd_per_km=rng.uniform(1e4, 1e5, n_samples),
        energy_parameter=rng.uniform(0.8, 1.1, n_samples),
    )
    return cells, samples


@pytest.mark.unit
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_factored_kernel_equals_the_textbook_form_on_random_blocks(seed):
    cells, samples = _random_problem(seed)
    np.testing.assert_allclose(lcoe_block(cells, samples), lcoe_direct(cells, samples), rtol=1e-11)


@pytest.mark.unit
def test_a_block_is_the_same_as_its_columns_and_rows_taken_one_at_a_time():
    cells, samples = _random_problem(7, n_cells=12, n_samples=9)
    block = lcoe_block(cells, samples)
    column = lcoe_block(cells, samples.take(slice(4, 5)))
    np.testing.assert_allclose(block[:, 4:5], column, rtol=1e-13)  # BLAS may differ in the last bit
    row = lcoe_block(cells.take(slice(3, 4)), samples)
    np.testing.assert_allclose(block[3:4], row, rtol=1e-13)


@pytest.mark.unit
def test_lcoe_rises_with_capex_distance_and_discount_rate_and_falls_with_energy():
    cells = _cells([10.0, 10.0], [10.0, 90.0], [2.0, 2.0], [30000.0, 30000.0])
    near_far = lcoe_block(cells, _samples())[:, 0]
    assert near_far[1] > near_far[0]  # farther from the grid
    low, high = lcoe_block(cells, _samples(capex_usd_per_kw=[800.0, 1200.0])).T
    assert (high > low).all()
    low, high = lcoe_block(cells, _samples(discount_rate=[0.03, 0.09])).T
    assert (high > low).all()
    more_energy = lcoe_block(_cells([10.0], [10.0], [2.0], [40000.0]), _samples())[0, 0]
    assert more_energy < near_far[0]


# -- domain checks (A-09) -------------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "change",
    [
        {"lifetime_years": 20.5},
        {"lifetime_years": 0.0},
        {"degradation_rate": 1.0},
        {"degradation_rate": -0.01},
        {"discount_rate": -1.0},
        {"capex_usd_per_kw": -5.0},
        {"opex_var_usd_per_mwh": float("nan")},
        {"energy_parameter": float("inf")},
    ],
)
def test_samples_outside_their_domain_raise(change):
    with pytest.raises(KernelInputError):
        _samples(**change)


@pytest.mark.unit
def test_cells_with_negative_or_non_finite_values_and_negative_energy_raise():
    with pytest.raises(KernelInputError, match="negative"):
        _cells([10.0], [1.0], [1.0], [-5.0])
    with pytest.raises(KernelInputError, match="non-finite"):
        _cells([float("nan")], [1.0], [1.0], [5.0])
    with pytest.raises(KernelInputError, match="negative annual energy"):
        # factor 1 + x is negative at x = -2
        lcoe_block(
            _cells([5.0], [1.0], [1.0], [1000.0], offset=[1.0], slope=[1.0]),
            _samples(energy_parameter=[-2.0, 0.5]),
        )


@pytest.mark.unit
def test_from_mapping_repeats_scalars_and_rejects_missing_keys_and_wrong_lengths():
    s = SampleInputs.from_mapping(
        {
            **{k: 1.0 for k in kernel.KERNEL_PARAMETER_KEYS},
            "energy_parameter": 0.9,
            "lifetime_years": 10.0,
            "degradation_rate": 0.01,
        },
        4,
    )
    assert len(s) == 4
    with pytest.raises(KernelInputError, match="lack"):
        SampleInputs.from_mapping({"capex_usd_per_kw": 1.0}, 4)
    bad = {
        **{k: 1.0 for k in kernel.KERNEL_PARAMETER_KEYS},
        "degradation_rate": 0.01,
        "energy_parameter": np.ones(3),
    }
    with pytest.raises(KernelInputError, match="expected 4"):
        SampleInputs.from_mapping(bad, 4)


@pytest.mark.unit
def test_the_kernel_module_is_pure_it_imports_no_io_or_table_library():
    """M-F6-05: the kernel is importable by F7 and does no I/O."""
    tree = ast.parse(KERNEL_FILE.read_text(encoding="utf-8"))
    imported = {
        (node.module or "").split(".")[0]
        if isinstance(node, ast.ImportFrom)
        else alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in (node.names if isinstance(node, ast.Import) else [None])
    }
    assert imported <= {"__future__", "collections", "dataclasses", "numpy"}
    assert not any(isinstance(n, ast.Name) and n.id in {"open", "print"} for n in ast.walk(tree))


# -- the energy floor (M-F7-01, D-F7-007) ----------------------------------------------------------


@pytest.mark.unit
def test_a_floor_of_zero_changes_nothing_and_an_infinite_floor_makes_the_row_infeasible():
    cells = _cells([100.0, 200.0, 50.0], [10.0, 30.0, 5.0], [2.0, 4.0, 1.0], [3.0e5, 6.0e5, 1.5e5])
    samples = _samples(energy_parameter=np.array([0.8, 0.9, 0.95]))
    plain = lcoe_block(cells, samples)
    np.testing.assert_array_equal(lcoe_block(cells, samples, min_energy_mwh=np.zeros(3)), plain)
    floored = lcoe_block(cells, samples, min_energy_mwh=np.array([0.0, np.inf, 0.0]))
    assert np.isposinf(floored[1]).all()
    np.testing.assert_array_equal(floored[[0, 2]], plain[[0, 2]])


@pytest.mark.unit
def test_the_floor_compares_with_the_sampled_energy_and_is_the_cf_min_condition():
    """`E >= P * 8760 * CF_min` is `CF >= CF_min`: a floor built that way marks exactly the cells below `CF_min`, per sample."""
    p = np.array([100.0, 100.0, 100.0])
    cf = np.array([0.20, 0.30, 0.40])
    cells = _cells(p, 0.0, 0.0, p * cf * 8760.0, offset=np.ones(3), slope=np.zeros(3))
    cf_min = 0.25
    out = lcoe_block(cells, _samples(), min_energy_mwh=p * 8760.0 * cf_min)
    assert np.isposinf(out[0]).all() and np.isfinite(out[1:]).all()
    # a sampled energy that moves with the energy parameter crosses the floor inside one cell
    slope = np.array([0.0, 0.0, 1.0])
    offset = np.array([1.0, 1.0, 0.0])
    moving = _cells(p, 0.0, 0.0, p * 0.4 * 8760.0, offset=offset, slope=slope)  # cell 2: E = E0 * x
    samples = _samples(energy_parameter=np.array([0.5, 0.7, 0.9]))  # CF of cell 2 = 0.2, 0.28, 0.36
    out = lcoe_block(moving, samples, min_energy_mwh=p * 8760.0 * cf_min)
    assert np.isposinf(out[2, 0]) and np.isfinite(out[2, 1:]).all()


@pytest.mark.unit
def test_a_bad_floor_is_refused():
    cells = _cells([100.0, 100.0], 1.0, 1.0, 1.0e5)
    for bad in (np.zeros(3), np.array([0.0, -1.0]), np.array([0.0, np.nan])):
        with pytest.raises(KernelInputError):
            lcoe_block(cells, _samples(), min_energy_mwh=bad)
