"""Latin hypercube sampler (M-F6-02, U-02, V5, A-12)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from geofrea.core.config_loader import load_parameters
from geofrea.lcoe_modeling.sampling import (
    SamplingError,
    UncertainSpec,
    draw_lhs,
    specs_from_parameters,
)

SPECS = [
    UncertainSpec("a", 5.0, 1.0, 10.0, "uniform"),
    UncertainSpec("b", 0.5, 0.0, 1.0, "triangular"),
    UncertainSpec("c", 100.0, 100.0, 100.0, "uniform"),  # a degenerate range stays at its value
]


@pytest.mark.unit
def test_lhs_is_reproducible_with_seed():
    first, again = draw_lhs(SPECS, 50, seed=42), draw_lhs(SPECS, 50, seed=42)
    assert first.equals(again)
    assert not first.equals(draw_lhs(SPECS, 50, seed=43))


@pytest.mark.unit
def test_sample_zero_is_the_nominal_vector_and_draws_stay_in_range():
    design = draw_lhs(SPECS, 200, seed=1)
    assert design.index.name == "sample" and len(design) == 201
    assert design.loc[0].tolist() == [5.0, 0.5, 100.0]
    draws = design.iloc[1:]
    assert draws["a"].between(1.0, 10.0).all() and draws["b"].between(0.0, 1.0).all() and (draws["c"] == 100.0).all()


@pytest.mark.unit
def test_each_marginal_is_stratified_one_draw_per_stratum_and_parameters_are_independent():
    n = 100
    design = draw_lhs(SPECS[:1], n, seed=7).iloc[1:]
    strata = np.floor((design["a"].to_numpy() - 1.0) / 9.0 * n).astype(int)
    assert sorted(strata.tolist()) == list(range(n))
    pair = [UncertainSpec("x", 0.5, 0, 1, "uniform"), UncertainSpec("y", 0.5, 0, 1, "uniform")]
    wide = draw_lhs(pair, 2000, seed=3).iloc[1:]
    assert abs(np.corrcoef(wide["x"], wide["y"])[0, 1]) < 0.1  # no correlation is imposed (V5)


@pytest.mark.unit
def test_triangular_marginal_has_its_mode_at_the_nominal_value():
    spec = UncertainSpec("t", 2.0, 0.0, 10.0, "triangular")
    draws = draw_lhs([spec], 4000, seed=5).iloc[1:]["t"]
    assert draws.mean() == pytest.approx((0.0 + 2.0 + 10.0) / 3, abs=0.1)


@pytest.mark.unit
def test_malformed_requests_raise():
    with pytest.raises(SamplingError):
        draw_lhs(SPECS, 0, seed=1)
    with pytest.raises(SamplingError):
        draw_lhs([], 10, seed=1)
    with pytest.raises(SamplingError):
        draw_lhs([SPECS[0], SPECS[0]], 10, seed=1)
    with pytest.raises(SamplingError, match="outside"):
        UncertainSpec("z", 11.0, 1.0, 10.0, "uniform")


@pytest.mark.unit
def test_specs_from_parameters_refuses_a_parameter_without_a_range():
    parameters = load_parameters(Path(__file__).resolve().parents[2] / "config" / "parameters.json")
    with pytest.raises(SamplingError, match="no value or no range"):
        specs_from_parameters(parameters, "PRT", "solar", ["capex_usd_per_kw"])
