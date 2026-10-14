"""Scenario discovery: the outcome, the choice of the box, the special cases and the bootstrap (M-F7-08; D-F7-054 to D-F7-057).

The synthetic case has a known box: two descriptors generate the outcome, a third and a categorical one do not.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from geofrea.robustness_analysis.prim import PrimResult, PrimStep
from geofrea.robustness_analysis.scenario_discovery import (
    ALL_CASES,
    BOX_FOUND,
    NO_CASES,
    NO_ELIGIBLE_BOX,
    DiscoverySettings,
    bootstrap,
    cases_of_interest,
    derive_seed,
    discover,
    restricted_descriptors,
    select_box,
)

SETTINGS = DiscoverySettings(
    outcome_threshold=0.20, peel_alpha=0.05, mass_min=0.05, min_coverage=0.50, max_restricted=3
)


def _synthetic(n=3000, seed=3):
    """The share beyond the tolerance is 0.5 when `a > 0.6` and `b < 0.3`, else 0.05: the box is a in [0.6, 1] and b in [0, 0.3]."""
    rng = np.random.default_rng(seed)
    x = pd.DataFrame(
        {
            "a": rng.uniform(0.0, 1.0, n),
            "b": rng.uniform(0.0, 1.0, n),
            "c": rng.uniform(0.0, 1.0, n),
            "gcm": rng.choice(["G1", "G2", "G3"], n),
        }
    )
    shares = np.where((x["a"] > 0.6) & (x["b"] < 0.3), 0.5, 0.05)
    return x, shares


def _step(i, coverage, density, restricted):
    return PrimStep(i, {}, {}, {}, coverage, density, 0.1, 100, 10, restricted)


def _trajectory(*steps):
    return PrimResult(tuple(steps), 1000, 100, (), (), ())


@pytest.mark.unit
def test_a_case_of_interest_is_a_share_of_at_least_theta():
    shares = np.array([0.0, 0.1999999, 0.2, 0.2000001, 1.0])
    assert cases_of_interest(shares, 0.20).tolist() == [0, 0, 1, 1, 1]
    assert cases_of_interest(np.array([0.1, 0.1 + 1e-15]), 0.1).tolist() == [
        1,
        1,
    ]  # at the threshold


@pytest.mark.unit
def test_two_descriptors_that_generate_the_outcome_are_recovered_with_their_limits():
    x, shares = _synthetic()
    found = discover(x, shares, SETTINGS)
    assert found.status == BOX_FOUND and found.chosen is not None
    box = found.chosen
    assert {"a", "b"} <= set(restricted_descriptors(found))
    assert (
        0.55 <= box.lower["a"] <= 0.65
    )  # the true limit is 0.6, found within about one peeling step
    assert 0.25 <= box.upper["b"] <= 0.35
    assert box.upper["a"] == pytest.approx(x["a"].max()) and box.lower["b"] == pytest.approx(
        x["b"].min()
    )
    assert box.density >= 0.90 and box.coverage >= 0.50
    assert box.n_restricted <= 3 and set(box.categories["gcm"]) == {"G1", "G2", "G3"}


@pytest.mark.unit
def test_the_box_is_the_densest_with_coverage_of_at_least_the_minimum_and_few_descriptors():
    trajectory = _trajectory(
        _step(0, 1.00, 0.10, 0),
        _step(1, 0.80, 0.30, 1),
        _step(2, 0.55, 0.60, 2),
        _step(3, 0.40, 0.90, 2),  # the densest, but it explains less than half of the cases
        _step(4, 0.55, 0.95, 4),  # denser and covering, but it restricts four descriptors
    )
    assert select_box(trajectory, 0.50, 3).step == 2
    assert select_box(trajectory, 0.40, 3).step == 3  # a lower requirement admits the denser box
    assert (
        select_box(trajectory, 0.60, 3).step == 1
    )  # a higher one takes the box that covers enough
    assert select_box(trajectory, 0.50, 4).step == 4  # and the cap on descriptors is a setting
    assert select_box(trajectory, 0.99, 3) is None  # no restricted box covers 99 percent


@pytest.mark.unit
def test_the_whole_space_is_not_a_box_and_a_tie_in_density_goes_to_the_larger_support():
    only_whole = _trajectory(_step(0, 1.0, 0.1, 0))
    assert select_box(only_whole, 0.5, 3) is None
    a = PrimStep(1, {}, {}, {}, 0.7, 0.5, 0.20, 100, 10, 1)
    b = PrimStep(2, {}, {}, {}, 0.6, 0.5, 0.30, 100, 10, 1)
    assert select_box(_trajectory(_step(0, 1.0, 0.1, 0), a, b), 0.5, 3).step == 2


@pytest.mark.unit
def test_the_chosen_box_respects_the_coverage_requirement_on_a_real_search():
    x, shares = _synthetic()
    for min_coverage in (0.40, 0.50, 0.60, 0.90):
        found = discover(
            x,
            shares,
            DiscoverySettings(0.20, 0.05, 0.05, min_coverage, 3),
        )
        assert found.status == BOX_FOUND
        assert found.chosen.coverage >= min_coverage - 1e-12
        eligible = [
            s
            for s in found.result.steps
            if s.coverage >= min_coverage - 1e-12 and 1 <= s.n_restricted <= 3
        ]
        assert found.chosen.density == max(s.density for s in eligible)


@pytest.mark.unit
def test_the_special_cases_are_reported_and_choose_no_box():
    x, _ = _synthetic(500)
    none = discover(x, np.full(len(x), 0.05), SETTINGS)
    assert (none.status, none.n_cases, none.chosen, none.result) == (NO_CASES, 0, None, None)
    every = discover(x, np.full(len(x), 0.9), SETTINGS)
    assert (every.status, every.n_cases, every.chosen) == (ALL_CASES, len(x), None)
    # cases that no box can explain (the descriptors are independent of the outcome) and a requirement above what peeling reaches
    rng = np.random.default_rng(0)
    noise = np.where(rng.uniform(size=len(x)) < 0.3, 0.5, 0.05)
    hard = discover(x, noise, DiscoverySettings(0.20, 0.05, 0.05, 0.999, 3))
    assert hard.status == NO_ELIGIBLE_BOX and hard.chosen is None and hard.result is not None


@pytest.mark.unit
def test_a_lower_theta_makes_more_cases_and_a_larger_support_changes_the_box():
    x, shares = _synthetic()
    shares = shares.copy()
    shares[(x["a"] > 0.5) & (x["a"] <= 0.6) & (x["b"] < 0.3)] = 0.15  # cases only for theta 0.10
    strict = discover(x, shares, DiscoverySettings(0.20, 0.05, 0.05, 0.5, 3))
    loose = discover(x, shares, DiscoverySettings(0.10, 0.05, 0.05, 0.5, 3))
    assert loose.n_cases > strict.n_cases
    assert loose.chosen.lower["a"] < strict.chosen.lower["a"]  # the box widens to the new cases
    wide = discover(x, shares, DiscoverySettings(0.20, 0.05, 0.10, 0.5, 3))
    assert wide.chosen.mass >= 0.10 - 1e-12


@pytest.mark.unit
def test_the_bootstrap_is_reproducible_with_the_same_seed_and_not_with_another():
    x, shares = _synthetic(600)
    kwargs = {"replicates": 12, "percentiles": (5.0, 95.0)}
    first = bootstrap(x, shares, SETTINGS, seed=derive_seed(42), **kwargs)
    again = bootstrap(x, shares, SETTINGS, seed=derive_seed(42), **kwargs)
    pd.testing.assert_frame_equal(first, again)
    other = bootstrap(x, shares, SETTINGS, seed=derive_seed(43), **kwargs)
    assert not first.equals(other)
    assert derive_seed(42) == derive_seed(42) != derive_seed(43)


@pytest.mark.unit
def test_the_bootstrap_reports_the_ranges_of_the_bounds_and_the_frequency_of_each_descriptor():
    x, shares = _synthetic(1200)
    table = bootstrap(
        x, shares, SETTINGS, replicates=30, seed=derive_seed(7), percentiles=(5.0, 95.0)
    )
    status = table[table["kind"] == "status"].set_index("name")["frequency"]
    assert status.sum() == pytest.approx(1.0) and set(status.index) == {
        BOX_FOUND,
        NO_CASES,
        ALL_CASES,
        NO_ELIGIBLE_BOX,
    }
    assert status[BOX_FOUND] > 0.9
    restriction = table[table["kind"] == "restriction"].set_index("name")["frequency"]
    assert restriction["a"] > 0.9 and restriction["b"] > 0.9  # the two drivers are stable
    assert restriction["c"] < restriction["a"]  # an inert descriptor is restricted less often
    lower_a = table[(table["kind"] == "lower") & (table["name"] == "a")].iloc[0]
    assert 0.5 <= lower_a["p_low"] <= lower_a["p50"] <= lower_a["p_high"] <= 0.7
    assert lower_a["n_used"] >= 27
    density = table[table["kind"] == "density"].iloc[0]
    coverage = table[table["kind"] == "coverage"].iloc[0]
    assert density["p_low"] <= density["p50"] <= density["p_high"] <= 1.0
    assert coverage["p_low"] >= 0.5 - 1e-12  # every replicate respects the rule
    categories = table[table["kind"] == "category"]
    assert set(categories["name"]) == {"gcm"} and set(categories["level"]) == {"G1", "G2", "G3"}
