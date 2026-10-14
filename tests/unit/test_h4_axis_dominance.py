"""H4, context-dependent dominance of the two uncertainty axes, on hand-made cells and countries (M-F7-06, M-F7-07; thesis text
docs/thesis/hypotheses/H4_axis_dominance.tex)."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from geofrea.lcoe_modeling.kernel import CellInputs, SampleInputs
from geofrea.robustness_analysis.evaluator import MemberWorld, evaluate
from geofrea.robustness_analysis.h4_axis_dominance import (
    CLIMATE_DOMINATED,
    MIXED,
    NO_DISPLACEMENT,
    NOT_SUPPORTED,
    NOT_TESTABLE,
    SUPPORTED,
    TECHNO_ECONOMIC_DOMINATED,
    CountryProfile,
    H4Error,
    H4Inputs,
    evaluate_variant,
    profile_of,
    sensitivity_variants,
    technology_verdict,
)
from geofrea.robustness_analysis.rankings import order_by
from tests.oracles.kernel import lcoe_direct

LOWER, UPPER = 0.40, 0.60


def _country(name: str, d_clim: float, d_tec: float) -> CountryProfile:
    rho, profile = profile_of(d_clim, d_tec, LOWER, UPPER)
    return CountryProfile(name, True, profile, d_clim, d_tec, d_clim + d_tec, rho)


# -- the profile and the verdict (section 8 of the thesis text) ---------------------------------------------------------


@pytest.mark.unit
def test_the_worked_example_of_the_thesis_text_gives_three_profiles_and_h4_supported():
    a, b, c = _country("A", 0.12, 0.38), _country("B", 0.42, 0.08), _country("C", 0.25, 0.25)
    assert (a.profile, b.profile, c.profile) == (
        TECHNO_ECONOMIC_DOMINATED,
        CLIMATE_DOMINATED,
        MIXED,
    )
    assert a.rho == pytest.approx(0.24) and b.rho == pytest.approx(0.84)
    assert c.rho == pytest.approx(0.50) and a.d_sum == pytest.approx(0.50)
    verdict = technology_verdict([a, b, c])
    assert verdict.verdict == SUPPORTED == "supported" and verdict.reason is None
    assert dict(verdict.counts) == {
        CLIMATE_DOMINATED: 1,
        TECHNO_ECONOMIC_DOMINATED: 1,
        MIXED: 1,
        NO_DISPLACEMENT: 0,
    }


@pytest.mark.unit
def test_country_b_with_rho_055_is_mixed_and_h4_is_not_supported():
    b = _country("B", 0.275, 0.225)  # rho = 0.55
    assert b.rho == pytest.approx(0.55) and b.profile == MIXED
    verdict = technology_verdict([_country("A", 0.12, 0.38), b, _country("C", 0.25, 0.25)])
    assert verdict.verdict == NOT_SUPPORTED and verdict.n_available == 3


@pytest.mark.unit
def test_rho_exactly_at_a_boundary_is_mixed_and_just_beyond_it_is_not():
    assert profile_of(0.2, 0.3, LOWER, UPPER) == (pytest.approx(0.4), MIXED)
    assert profile_of(0.3, 0.2, LOWER, UPPER) == (pytest.approx(0.6), MIXED)
    assert profile_of(0.19, 0.31, LOWER, UPPER)[1] == TECHNO_ECONOMIC_DOMINATED
    assert profile_of(0.31, 0.19, LOWER, UPPER)[1] == CLIMATE_DOMINATED
    assert profile_of(0.5, 0.0, LOWER, UPPER) == (1.0, CLIMATE_DOMINATED)
    assert profile_of(0.0, 0.5, LOWER, UPPER) == (0.0, TECHNO_ECONOMIC_DOMINATED)


@pytest.mark.unit
def test_no_displacement_has_no_ratio_and_does_not_support_h4():
    assert profile_of(0.0, 0.0, LOWER, UPPER) == (None, NO_DISPLACEMENT)
    verdict = technology_verdict([_country("A", 0.0, 0.0), _country("B", 0.4, 0.0)])
    assert (
        verdict.verdict == NOT_SUPPORTED
    )  # one dominance class with No Displacement is not a pair


@pytest.mark.unit
def test_a_country_without_inputs_is_unavailable_and_not_counted_as_having_a_profile():
    gone = CountryProfile("D", False, reason="the country has no manifest")
    assert gone.profile is None
    verdict = technology_verdict([_country("A", 0.12, 0.38), _country("B", 0.42, 0.08), gone])
    assert verdict.verdict == SUPPORTED and (verdict.n_countries, verdict.n_available) == (3, 2)
    # fewer than two countries with a profile: the rule cannot be tested
    one = technology_verdict([_country("A", 0.12, 0.38), gone])
    assert one.verdict == NOT_TESTABLE and "1 of 2" in one.reason
    none = technology_verdict([gone, CountryProfile("E", False, reason="x")])
    assert none.verdict == NOT_TESTABLE and none.n_available == 0
    assert (
        technology_verdict([_country("A", 0.1, 0.4), _country("B", 0.1, 0.4)]).verdict
        == NOT_SUPPORTED
    )


# -- the displacements of one country ------------------------------------------------------------------------------------


def _inputs(
    z_clim: list[float],
    z_tec: list[float],
    z_joint: list[float] | None = None,
    *,
    q: list[float] | None = None,
    ranked: list[bool] | None = None,
    members: tuple[tuple[str, str], ...] = (("G", "SSP1"),),
    r_clim: np.ndarray | None = None,
) -> H4Inputs:
    """20 cells whose nominal rank is their position plus 1 (the LCOE increases with the index); one member unless `r_clim` is given."""
    n = len(z_tec)
    return H4Inputs(
        r_clim=np.array(z_clim, dtype=float)[:, None] if r_clim is None else r_clim,
        z_tec=np.array(z_tec, dtype=float),
        z_joint=np.array(z_joint if z_joint is not None else z_tec, dtype=float),
        lcoe=np.arange(1.0, n + 1.0),
        q=np.array(q if q is not None else [1.0] * n),
        ranked=np.ones(n, dtype=bool) if ranked is None else np.array(ranked),
        sr=None,
        ssps=tuple(m[1] for m in members),
        gcms=tuple(m[0] for m in members),
    )


def _score_with_best(cells: list[int], n: int = 20) -> list[float]:
    """A score whose lowest values are on `cells`, in the order given."""
    z = [10.0 + i for i in range(n)]
    for rank, cell in enumerate(cells):
        z[cell] = float(rank)
    return z


def _evaluate(inputs: H4Inputs, **kwargs):
    settings = {
        "variant": "primary",
        "lower": LOWER,
        "upper": UPPER,
        "tolerance_multiple": 1.0,
        "top_k_percent": 10.0,
    }
    return evaluate_variant(inputs, **{**settings, **kwargs})


@pytest.mark.unit
def test_each_axis_displacement_is_the_h3_statistic_on_its_own_shortlist():
    # k = 2, m = 2: a cell of nominal rank above 4 (index 4 or more) is beyond the tolerance
    inputs = _inputs(
        z_clim=_score_with_best([0, 9]),  # climate shortlist: ranks 1 and 10
        z_tec=_score_with_best([10, 11]),  # techno shortlist: ranks 11 and 12
        z_joint=_score_with_best([0, 1]),  # joint shortlist: ranks 1 and 2
    )
    result = _evaluate(inputs)
    assert (result.k, result.m) == (2, 2)
    assert result.d_clim == pytest.approx(0.5) and result.d_tec == pytest.approx(1.0)
    assert result.d_joint == 0.0 and result.d_sum == pytest.approx(1.5)
    assert result.rho == pytest.approx(1 / 3) and result.profile == TECHNO_ECONOMIC_DOMINATED
    assert result.distance_to_lower == pytest.approx(abs(1 / 3 - 0.4))
    assert result.distance_to_upper == pytest.approx(abs(1 / 3 - 0.6))
    assert (result.clim_capacity_mw, result.tec_capacity_mw) == (2.0, 2.0)


@pytest.mark.unit
def test_a_cell_ranked_between_k_plus_1_and_k_plus_m_is_not_displaced_and_capacity_weights():
    inputs = _inputs(
        z_clim=_score_with_best([2, 3]),  # nominal ranks 3 and 4: inside k + m = 4
        z_tec=_score_with_best([4, 5]),  # ranks 5 and 6: beyond; capacities 1 and 9
        q=[1.0] * 4 + [1.0, 9.0] + [1.0] * 14,
    )
    result = _evaluate(inputs)
    assert result.d_clim == 0.0
    assert result.d_tec == pytest.approx(1.0)
    both = _evaluate(
        _inputs(
            z_clim=_score_with_best([0, 5]),
            z_tec=_score_with_best([0, 5]),
            q=[1.0] * 5 + [9.0] + [1.0] * 14,
        )
    )
    assert both.d_clim == pytest.approx(0.9) and both.d_tec == pytest.approx(0.9)
    assert both.rho == pytest.approx(0.5) and both.profile == MIXED


@pytest.mark.unit
def test_two_axes_that_leave_the_nominal_shortlist_alone_give_no_displacement():
    inputs = _inputs(_score_with_best([0, 1]), _score_with_best([1, 0]))
    result = _evaluate(inputs)
    assert (result.d_clim, result.d_tec, result.d_sum) == (0.0, 0.0, 0.0)
    assert result.rho is None and result.profile == NO_DISPLACEMENT
    assert result.distance_to_lower is None and result.distance_to_upper is None


@pytest.mark.unit
def test_the_ranked_set_is_the_domain_and_the_climate_axis_needs_a_member():
    # cell 0 has the best scores and the lowest cost but is climate-fragile: it is outside I and in no shortlist
    ranked = [False] + [True] * 19
    inputs = _inputs(_score_with_best([0, 1]), _score_with_best([0, 1]), ranked=ranked)
    result = _evaluate(inputs)
    assert result.n_ranked == 19 and result.n_cells == 20 and result.k == 2
    assert result.d_clim == 0.0  # cells 1 and 2 hold nominal ranks 1 and 2 within I
    with pytest.raises(H4Error, match="ranked set is empty"):
        _evaluate(_inputs(_score_with_best([0]), _score_with_best([0]), ranked=[False] * 20))
    with pytest.raises(H4Error, match="no climate member"):
        _evaluate(inputs, exclude_gcms=["G"])


@pytest.mark.unit
def test_the_climate_axis_is_the_worst_member_and_the_ssp_and_gcm_readings_restrict_it():
    # two members of different SSPs and GCMs: member 1 puts cells 0 and 1 first, member 2 puts cells 10 and 11 first
    first, second = _score_with_best([0, 1]), _score_with_best([10, 11])
    r_clim = np.array([first, second], dtype=float).T
    inputs = _inputs(
        z_clim=first,
        z_tec=_score_with_best([0, 1]),
        r_clim=r_clim,
        members=(("A", "SSP1"), ("B", "SSP3")),
    )
    worst = np.maximum(np.array(first), np.array(second))
    result = _evaluate(inputs)
    order = order_by(worst)[:2]
    assert result.d_clim == pytest.approx(float(np.mean(order >= 4)))
    ssp1 = _evaluate(inputs, only_ssp="SSP1", variant="climate_ssp_SSP1")
    ssp3 = _evaluate(inputs, only_ssp="SSP3", variant="climate_ssp_SSP3")
    assert ssp1.d_clim == 0.0 and ssp3.d_clim == 1.0 and ssp3.ssp == "SSP3"
    without_b = _evaluate(inputs, exclude_gcms=["B"], variant="without_B")
    assert without_b.d_clim == ssp1.d_clim and without_b.excluded_gcms == ("B",)
    names = [v.variant for v in sensitivity_variants(inputs, result, tcr_exception_gcms=["B"])]
    assert names == [
        "climate_ssp_SSP1",
        "climate_ssp_SSP3",
        "without_B",
        "top_k_percent_5",
        "top_k_percent_10",
        "top_k_percent_20",
        "tolerance_0.5k",
        "tolerance_2k",
        "boundaries_0.30_0.70",
        "boundaries_0.45_0.55",
    ]


@pytest.mark.unit
def test_the_boundary_variants_change_only_the_profile():
    result = _evaluate(_inputs(_score_with_best([0, 9]), _score_with_best([10, 11])))  # rho = 1/3
    variants = {
        v.variant: v
        for v in sensitivity_variants(
            _inputs(_score_with_best([0, 9]), _score_with_best([10, 11])),
            result,
            tcr_exception_gcms=[],
        )
    }
    wide, narrow = variants["boundaries_0.30_0.70"], variants["boundaries_0.45_0.55"]
    assert result.profile == TECHNO_ECONOMIC_DOMINATED
    assert wide.profile == MIXED  # 0.30 <= 0.333 <= 0.70
    assert narrow.profile == TECHNO_ECONOMIC_DOMINATED
    for v in (wide, narrow):
        assert (v.d_clim, v.d_tec, v.rho) == (result.d_clim, result.d_tec, result.rho)
    assert (
        dataclasses.replace(
            wide,
            variant=result.variant,
            lower=LOWER,
            upper=UPPER,
            profile=result.profile,
            distance_to_lower=result.distance_to_lower,
            distance_to_upper=result.distance_to_upper,
        )
        == result
    )


# -- the invariance of section 2 of the thesis text ---------------------------------------------------------------------

N_DRAWS = 40


def _world(rng, n_cells=60, n_core=3):
    p = rng.uniform(20.0, 300.0, n_cells)
    grid = rng.uniform(0.0, 120.0, n_cells)
    road = rng.uniform(0.0, 30.0, n_cells)
    cf = rng.uniform(0.15, 0.45, n_cells)
    worlds = [
        MemberWorld(
            member=f"m{j}",
            cells=CellInputs(
                p_mw=p,
                dist_grid_km=grid,
                dist_road_km=road,
                energy_mwh=p * cf * (1.0 - 0.05 * j) * 8760.0,
                energy_offset=np.full(n_cells, 1.0),
                energy_slope=np.zeros(n_cells),
            ),
            floor=np.zeros(n_cells),
        )
        for j in range(n_core + 1)
    ]
    return worlds[0], worlds[1:]


def _samples(rng, *, scale=1.0, shift=0.0):
    n = N_DRAWS + 1

    def column(low, high):
        v = rng.uniform(low, high, n)
        v[0] = (low + high) / 2.0
        return v

    return SampleInputs(
        capex_usd_per_kw=scale * column(800, 1200),
        opex_fixed_frac=column(0.03, 0.07),
        opex_var_usd_per_mwh=scale * np.full(n, 2.0) + shift,
        lifetime_years=np.round(column(15, 25)),
        discount_rate=column(0.03, 0.08),
        degradation_rate=column(0.0, 0.01),
        grid_cost_usd_per_mw_km=scale * column(500, 1500),
        substation_cost_usd_per_mw=scale * column(1e4, 3e4),
        road_cost_usd_per_km=scale * column(2.5e4, 7.5e4),
        energy_parameter=np.full(n, 0.9),
    )


@pytest.mark.unit
def test_a_common_increasing_affine_transformation_of_the_cost_does_not_change_the_order_of_the_sites():
    """Equation 2 of the thesis text: with LCOE' = a + b LCOE, b > 0, the order of the sites is that of the cost in every future; for the
    common scaling of every cost (a = 0) the relative regret, and with it the techno-economic score and its shortlist, do not change."""
    reference, worlds = _world(np.random.default_rng(11))
    base = _samples(np.random.default_rng(5))
    scaled = _samples(np.random.default_rng(5), scale=1.7)
    shifted = _samples(
        np.random.default_rng(5), scale=1.7, shift=3.0
    )  # variable cost adds to the LCOE of every cell
    original = lcoe_direct(reference.cells, base)
    # the premise: the transformed samples really give LCOE' = b LCOE (+ a)
    np.testing.assert_allclose(lcoe_direct(reference.cells, scaled), 1.7 * original, rtol=1e-9)
    np.testing.assert_allclose(
        lcoe_direct(reference.cells, shifted), 1.7 * original + 3.0, rtol=1e-9
    )
    for transformed in (scaled, shifted):
        moved = lcoe_direct(reference.cells, transformed)
        for draw in range(original.shape[1]):
            np.testing.assert_array_equal(np.argsort(original[:, draw]), np.argsort(moved[:, draw]))
    plain = evaluate(reference, worlds, base, tau=None, block_cells=17)
    rescaled = evaluate(reference, worlds, scaled, tau=None, block_cells=17)
    np.testing.assert_allclose(rescaled.mr_tech, plain.mr_tech, rtol=1e-9)
    np.testing.assert_array_equal(order_by(rescaled.mr_tech), order_by(plain.mr_tech))
    np.testing.assert_array_equal(order_by(rescaled.mr_clim), order_by(plain.mr_clim))
