"""The own PRIM against the stored `ema_workbench` reference, and its rules on hand-made cases (M-F7-08, D-F7-021, D16)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from geofrea.robustness_analysis.prim import PrimError, run_prim, sd_quantile

REFERENCE = Path(__file__).resolve().parents[1] / "fixtures" / "prim_reference.json"
CASES = json.loads(REFERENCE.read_text(encoding="utf-8"))["cases"]


def _frame(case) -> pd.DataFrame:
    return pd.DataFrame({c: v for c, v in case["x"].items()})


@pytest.mark.unit
def test_the_fixture_records_the_command_and_the_versions_that_generated_it():
    generator = json.loads(REFERENCE.read_text(encoding="utf-8"))["generator"]
    assert (
        generator["ema_workbench"] == "3.0.0"
        and "generate_prim_reference.py" in generator["command"]
    )
    assert generator["python"].startswith("3.12")


@pytest.mark.unit
@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_the_peeling_and_pasting_trajectory_equals_the_reference(case):
    result = run_prim(
        _frame(case), np.array(case["y"]), alpha=case["alpha"], mass_min=case["mass_min"]
    )
    assert len(result.steps) == len(case["steps"])
    for got, want in zip(result.steps, case["steps"], strict=True):
        assert (got.n, got.k, got.n_restricted) == (want["n"], want["k"], want["n_restricted"])
        assert got.coverage == pytest.approx(want["coverage"], rel=1e-12)
        assert got.density == pytest.approx(want["density"], rel=1e-12)
        assert got.mass == pytest.approx(want["mass"], rel=1e-12)
        for column, limits in want["limits"].items():
            if "categories" in limits:
                assert list(got.categories[column]) == limits["categories"]
            else:
                assert got.lower[column] == pytest.approx(limits["lower"], rel=1e-12, abs=1e-15)
                assert got.upper[column] == pytest.approx(limits["upper"], rel=1e-12, abs=1e-15)


@pytest.mark.unit
def test_the_reference_cases_find_a_box_where_one_is_planted_and_stay_put_without_signal():
    by_name = {c["name"]: c for c in CASES}
    assert len(by_name["two_real_planted_box"]["steps"]) > 3
    planted = by_name["two_real_planted_box"]["steps"][-1]
    assert planted["density"] > 0.8  # the reference itself found the planted box
    assert by_name["no_signal"]["steps"][-1]["n_restricted"] <= 2


@pytest.mark.unit
def test_the_quantile_is_the_sdtoolkit_midpoint_and_steps_over_ties_away_from_the_median():
    assert sd_quantile(np.arange(11.0), 0.95) == pytest.approx((9.0 + 10.0) / 2)
    # the upper quantile of a tied top slides down to the first smaller value
    assert sd_quantile(np.array([1.0, 2.0, 3.0, 4.0, 4.0, 4.0, 4.0, 4.0]), 0.95) == pytest.approx(
        3.5
    )
    assert sd_quantile(np.array([1.0, 1.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]), 0.05) == pytest.approx(
        1.5
    )


@pytest.mark.unit
def test_a_box_that_covers_the_planted_region_is_found_by_hand_on_a_grid():
    # x runs over 0..99; the outcome is 1 for x >= 70: peeling from below must end at the limit of the region
    x = pd.DataFrame({"x": np.arange(100.0)})
    y = (x["x"] >= 70).astype(int).to_numpy()
    result = run_prim(x, y, alpha=0.05, mass_min=0.05)
    last = result.steps[-1]
    # a pure box: its lower limit lies above the last cell outside the region, and it keeps most of the region (peeling is in 5% steps)
    assert last.density == pytest.approx(1.0) and last.coverage >= 0.9
    assert 69.0 < last.lower["x"] <= 75.0 and last.upper["x"] == 99.0


@pytest.mark.unit
def test_the_trajectory_honors_the_minimum_support_and_starts_at_the_full_box():
    rng = np.random.default_rng(1)
    x = pd.DataFrame({"a": rng.random(300), "b": rng.random(300)})
    y = ((x["a"] > 0.8) & (x["b"] > 0.8)).astype(int).to_numpy()
    result = run_prim(x, y, alpha=0.05, mass_min=0.2)
    assert result.steps[0].mass == 1.0 and result.steps[0].n_restricted == 0
    assert all(step.mass >= 0.2 for step in result.steps)
    assert result.n_futures == 300 and result.n_positive == int(y.sum())


@pytest.mark.unit
def test_a_categorical_descriptor_with_one_category_is_dropped_and_an_integer_one_is_refused():
    x = pd.DataFrame({"a": np.linspace(0, 1, 40), "ssp": ["s"] * 40})
    y = (x["a"] > 0.5).astype(int).to_numpy()
    assert run_prim(x, y, alpha=0.1, mass_min=0.1).dropped_descriptors == ("ssp",)
    with pytest.raises(PrimError, match="integers"):
        run_prim(pd.DataFrame({"n": np.arange(40)}), y, alpha=0.1, mass_min=0.1)


@pytest.mark.unit
@pytest.mark.parametrize(
    "alpha,mass_min,y",
    [(0.0, 0.1, [0, 1]), (0.6, 0.1, [0, 1]), (0.1, 0.0, [0, 1]), (0.1, 0.1, [0, 2])],
)
def test_settings_and_outcomes_outside_their_range_are_refused(alpha, mass_min, y):
    with pytest.raises(PrimError):
        run_prim(pd.DataFrame({"a": [0.0, 1.0]}), np.array(y), alpha=alpha, mass_min=mass_min)
