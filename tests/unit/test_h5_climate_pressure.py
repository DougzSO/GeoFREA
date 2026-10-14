"""H5, climate pressure on the economic potential relative to the national target (M-F7-07; D-F7-050 to D-F7-053).

The worked example is that of the thesis text `docs/thesis/hypotheses/H5_climate_threat_to_targets.tex` (section 8): E_0 = 500, G = 300, members
480/450/470, Delta E = 50, R_loss = 0.25, E_exp = 60 (40 with the reference indicators, so 20 added by climate change), R_exp = 0.30: supported.
"""

from __future__ import annotations

import numpy as np
import pytest

from geofrea.robustness_analysis.h5_climate_pressure import (
    NOT_SUPPORTED,
    NOT_TESTABLE,
    PARTIAL_EXPOSURE,
    PARTIAL_RESOURCE,
    SUPPORTED,
    TARGET_NOT_MET,
    TESTED,
    WHOLE_DOMAIN,
    Exposure,
    H5Error,
    H5Inputs,
    Target,
    convert_target,
    evaluate_h5,
    sensitivity_variants,
    unavailable,
)

TAU = 50.0
LAM = 0.20
MEMBERS = ("A_ssp1", "B_ssp2", "C_ssp3")
GCMS = ("A", "B", "C")


def _exposure(absolute, reference=None, channels=("heat",), has_reference=(True,), slots=(0, 1, 2)):
    """Flags `(hazard members, channels, cells)` from nested lists; the reference defaults to nothing exposed."""
    absolute = np.asarray(absolute, dtype=bool)
    reference = np.zeros_like(absolute) if reference is None else np.asarray(reference, dtype=bool)
    return Exposure(tuple(slots), tuple(channels), absolute, reference, tuple(has_reference))


def _inputs(energy, *, lcoe=None, capacity=None, cf=None, exposure=None, members=MEMBERS):
    energy = np.asarray(energy, dtype="float64")
    n = energy.shape[0]
    return H5Inputs(
        cell_id=np.arange(1, n + 1),
        capacity_mw=np.full(n, 1000.0) if capacity is None else np.asarray(capacity, dtype=float),
        cf=np.full(n, 0.25) if cf is None else np.asarray(cf, dtype=float),
        energy_twh=energy,
        lcoe=np.full(energy.shape, 20.0) if lcoe is None else np.asarray(lcoe, dtype=float),
        members=tuple(members),
        gcms=GCMS[: len(members)],
        exposure=unavailable("no exposure in this case") if exposure is None else exposure,
    )


def _example():
    """Four cells; columns are m0 and the three members. E_0 = 500; the members sum to 480, 450 and 470."""
    energy = [
        [280, 270, 250, 260],
        [120, 110, 100, 110],
        [60, 60, 60, 60],
        [40, 40, 40, 40],
    ]
    # absolute: only the third cell is exposed, and only in member B (60 TWh); reference: only the fourth cell is (40 TWh)
    absolute = [[[0, 0, 0, 0]], [[0, 0, 1, 0]], [[0, 0, 0, 0]]]
    reference = [[[0, 0, 0, 1]], [[0, 0, 0, 1]], [[0, 0, 0, 1]]]
    return _inputs(energy, exposure=_exposure(absolute, reference))


@pytest.mark.unit
def test_the_worked_example_of_the_thesis_text_is_supported():
    result = evaluate_h5(_example(), Target(300.0, "TWh/year", 2030, "test"), lam=LAM, tau=TAU)
    assert result.status == TESTED
    assert result.e0_twh == pytest.approx(500.0)
    assert result.member_energy_twh == pytest.approx((480.0, 450.0, 470.0))
    assert result.h0_twh == pytest.approx(200.0)
    assert result.delta_e_twh == pytest.approx(50.0)
    assert result.r_loss == pytest.approx(0.25) and result.h5a_holds
    assert result.member_min == "B_ssp2"
    assert result.e_exp_twh == pytest.approx(60.0) and result.member_exp_max == "B_ssp2"
    assert result.r_exp == pytest.approx(0.30) and result.h5b_holds
    assert result.e_exp_reference_twh == pytest.approx(40.0)
    assert result.exposure_increment_twh == pytest.approx(20.0)
    assert result.verdict == SUPPORTED
    assert result.conversion == "none (target in TWh/year)" and result.cf_bar is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("target", "r_loss", "r_exp", "expected"),
    [
        (300.0, 50 / 200, 60 / 200, SUPPORTED),  # H_0 = 200: both reach 0.20
        (450.0, 50 / 50, 60 / 50, SUPPORTED),  # H_0 = 50: both far above
        (240.0, 50 / 260, 60 / 260, PARTIAL_EXPOSURE),  # H_0 = 260: 0.192 < 0.20 <= 0.231
        (150.0, 50 / 350, 60 / 350, NOT_SUPPORTED),  # H_0 = 350: 0.143 and 0.171
    ],
)
def test_the_verdict_follows_the_two_sub_hypotheses(target, r_loss, r_exp, expected):
    result = evaluate_h5(_example(), Target(target, "TWh/year", 2030, "t"), lam=LAM, tau=TAU)
    assert result.r_loss == pytest.approx(r_loss) and result.r_exp == pytest.approx(r_exp)
    assert result.verdict == expected


@pytest.mark.unit
def test_each_sub_hypothesis_alone_gives_its_partial_verdict_and_neither_gives_not_supported():
    target = Target(300.0, "TWh/year", 2030, "t")
    resource_only = _inputs(_example().energy_twh, exposure=_exposure(np.zeros((3, 1, 4))))
    assert evaluate_h5(resource_only, target, lam=LAM, tau=TAU).verdict == PARTIAL_RESOURCE
    gains = _example().energy_twh.copy()
    gains[:, 1:] = gains[:, :1] + 5.0
    neither = _inputs(gains, exposure=_exposure(np.zeros((3, 1, 4))))
    result = evaluate_h5(neither, target, lam=LAM, tau=TAU)
    assert result.verdict == NOT_SUPPORTED and result.delta_e_twh == 0.0
    exposure_only = _inputs(gains, exposure=_example().exposure)
    assert evaluate_h5(exposure_only, target, lam=LAM, tau=TAU).verdict == PARTIAL_EXPOSURE


@pytest.mark.unit
def test_a_gain_in_every_member_gives_no_loss_and_the_gains_are_descriptive():
    energy = [[100.0, 110.0, 120.0, 105.0], [100.0, 100.0, 130.0, 101.0]]
    result = evaluate_h5(_inputs(energy), Target(100.0, "TWh/year", 2030, "t"), lam=LAM, tau=TAU)
    assert result.delta_e_twh == 0.0 and result.r_loss == 0.0 and result.h5a_holds is False
    assert result.max_gain_twh == pytest.approx(
        50.0
    )  # the best member adds 50 TWh/year (250 against 200)
    assert result.median_change_twh == pytest.approx(10.0)
    assert result.member_min == "C_ssp3"  # the member with the smallest energy (206), even a gain


@pytest.mark.unit
def test_gains_in_some_members_do_not_offset_losses_in_others():
    energy = [[100.0, 130.0, 70.0, 100.0]]
    result = evaluate_h5(_inputs(energy), Target(50.0, "TWh/year", 2030, "t"), lam=LAM, tau=TAU)
    assert result.delta_e_twh == pytest.approx(
        30.0
    )  # only the loss counts, the +30 does not offset it
    assert result.r_loss == pytest.approx(30.0 / 50.0)


@pytest.mark.unit
def test_a_cell_with_two_channels_above_their_thresholds_is_counted_once():
    energy = [[100.0, 100.0, 100.0, 100.0], [50.0, 50.0, 50.0, 50.0]]
    # first cell exposed in both channels, second in the first channel only; three hazard members
    absolute = np.zeros((3, 2, 2), dtype=bool)
    absolute[:, 0, 0] = absolute[:, 1, 0] = absolute[:, 0, 1] = True
    exposure = _exposure(absolute, channels=("heat", "rain"), has_reference=(True, True))
    result = evaluate_h5(
        _inputs(energy, exposure=exposure), Target(10.0, "TWh/year", 2030, "t"), lam=LAM, tau=TAU
    )
    assert result.e_exp_twh == pytest.approx(150.0)  # both cells once, not 100 + 100 + 50
    one_by_one = {
        v.variant: v
        for v in sensitivity_variants(
            _inputs(energy, exposure=exposure),
            Target(10.0, "TWh/year", 2030, "t"),
            result,
            lam_sensitivity=0.10,
            tau_range=None,
            tcr_exception_gcms=(),
        )
    }
    assert one_by_one["channel_heat"].e_exp_twh == pytest.approx(150.0)
    assert one_by_one["channel_rain"].e_exp_twh == pytest.approx(
        100.0
    )  # channels one by one, no sum of overlapping cells


@pytest.mark.unit
def test_without_a_target_h5_is_not_testable_and_reports_no_ratios():
    result = evaluate_h5(_example(), Target(None), lam=LAM, tau=TAU)
    assert result.status == NOT_TESTABLE and result.verdict is None
    assert result.g_twh is None and result.h0_twh is None
    assert result.r_loss is None and result.r_exp is None
    assert result.e0_twh == pytest.approx(500.0) and result.delta_e_twh == pytest.approx(50.0)
    assert result.e_exp_twh == pytest.approx(60.0)
    assert "no national target" in result.verdict_reason


@pytest.mark.unit
@pytest.mark.parametrize("target", [500.0, 600.0])
def test_a_target_the_baseline_does_not_exceed_is_not_met_at_reference_with_ratios_on_g(target):
    result = evaluate_h5(_example(), Target(target, "TWh/year", 2030, "t"), lam=LAM, tau=TAU)
    assert result.status == TARGET_NOT_MET and result.verdict is None
    assert result.h0_twh == pytest.approx(500.0 - target)
    assert result.r_loss is None and result.r_exp is None and result.h5a_holds is None
    assert result.delta_e_over_g == pytest.approx(50.0 / target)
    assert result.e_exp_over_g == pytest.approx(60.0 / target)


@pytest.mark.unit
def test_the_conversion_of_a_capacity_target_is_the_capacity_weighted_factor_of_the_cheapest_cells():
    # three cells of 1000, 2000 and 1000 MW, cheapest first: the second (cf 0.30), the first (cf 0.20), the third (cf 0.50)
    capacity = np.array([1000.0, 2000.0, 1000.0])
    cf = np.array([0.20, 0.30, 0.50])
    lcoe = np.array([30.0, 20.0, 40.0])
    ids = np.array([1, 2, 3])
    domain = np.ones(3, dtype=bool)
    # G_cap = 3 GW takes 2 GW of cell 2 and 1 GW of cell 1: CFbar = (2 * 0.30 + 1 * 0.20) / 3 = 0.80 / 3
    g, cf_bar, exceeds = convert_target(capacity, cf, lcoe, ids, domain, 3.0)
    assert cf_bar == pytest.approx(0.8 / 3.0) and not exceeds
    assert g == pytest.approx(8.76 * 3.0 * 0.8 / 3.0)  # 7.008 TWh/year
    # G_cap = 3.5 GW: a fraction (0.5 GW) of the third cell, the dearest
    g, cf_bar, _ = convert_target(capacity, cf, lcoe, ids, domain, 3.5)
    expected = (2 * 0.30 + 1 * 0.20 + 0.5 * 0.50) / 3.5
    assert cf_bar == pytest.approx(expected)
    # the whole domain (the alternative conversion): (1 * 0.2 + 2 * 0.3 + 1 * 0.5) / 4
    _, cf_whole, _ = convert_target(capacity, cf, lcoe, ids, domain, 3.0, WHOLE_DOMAIN)
    assert cf_whole == pytest.approx(1.3 / 4.0)
    # a target above the capacity of the domain takes all of it and is flagged
    g, cf_bar, exceeds = convert_target(capacity, cf, lcoe, ids, domain, 6.0)
    assert (
        exceeds
        and cf_bar == pytest.approx(1.3 / 4.0)
        and g == pytest.approx(8.76 * 6.0 * 1.3 / 4.0)
    )
    # ties in the cost go to the lower cell_id
    _, cf_tied, _ = convert_target(capacity, cf, np.array([20.0, 20.0, 20.0]), ids, domain, 1.0)
    assert cf_tied == pytest.approx(0.20)
    # a cell outside the domain never enters
    only = np.array([True, False, True])
    _, cf_only, _ = convert_target(capacity, cf, lcoe, ids, only, 1.0)
    assert cf_only == pytest.approx(0.20)


@pytest.mark.unit
def test_a_target_in_gw_is_converted_and_reported_with_its_original_unit():
    inputs = _inputs(
        [[100.0, 90.0, 80.0, 95.0], [100.0, 100.0, 100.0, 100.0]],
        lcoe=np.array([[10.0] * 4, [30.0] * 4]),
        capacity=[2000.0, 3000.0],
        cf=[0.40, 0.20],
    )
    result = evaluate_h5(inputs, Target(2.0, "GW", 2035, "plan"), lam=LAM, tau=TAU)
    # 2 GW is exactly the cheapest cell: CFbar = 0.40 and G = 8.76 * 2 * 0.40 = 7.008 TWh/year
    assert result.cf_bar == pytest.approx(0.40) and result.g_twh == pytest.approx(7.008)
    assert (result.target_value, result.target_unit, result.target_horizon) == (2.0, "GW", 2035)
    assert result.conversion == "cheapest_cells_first" and not result.target_exceeds_domain
    assert result.h0_twh == pytest.approx(200.0 - 7.008)


@pytest.mark.unit
def test_the_dynamic_domain_differs_from_the_fixed_one_when_a_cell_changes_side_of_tau():
    # cell 1 is cheap at f0 and in A, dearer than tau in B; cell 2 is dear at f0 and cheap in C
    energy = [[100.0, 100.0, 100.0, 100.0], [40.0, 40.0, 40.0, 40.0]]
    lcoe = [[40.0, 40.0, 60.0, 40.0], [60.0, 60.0, 60.0, 40.0]]
    inputs = _inputs(energy, lcoe=lcoe)
    target = Target(50.0, "TWh/year", 2030, "t")
    fixed = evaluate_h5(inputs, target, lam=LAM, tau=TAU)
    dynamic = evaluate_h5(
        inputs, target, lam=LAM, tau=TAU, domain="dynamic", variant="dynamic_domain"
    )
    assert (
        fixed.e0_twh == pytest.approx(100.0) and fixed.delta_e_twh == 0.0
    )  # the domain is cell 1 for every member
    assert dynamic.member_energy_twh == pytest.approx((100.0, 0.0, 140.0))
    assert dynamic.delta_e_twh == pytest.approx(
        100.0
    )  # B loses the whole domain: it is dearer than tau there
    assert dynamic.variant == "dynamic_domain" and dynamic.domain == "dynamic"


@pytest.mark.unit
def test_cells_outside_the_domain_do_not_count_and_a_dearer_cell_enters_with_a_higher_tau():
    energy = [[100.0, 90.0, 90.0, 90.0], [100.0, 100.0, 100.0, 100.0]]
    lcoe = [[10.0] * 4, [80.0] * 4]
    inputs = _inputs(energy, lcoe=lcoe)
    target = Target(50.0, "TWh/year", 2030, "t")
    assert evaluate_h5(inputs, target, lam=LAM, tau=TAU).e0_twh == pytest.approx(100.0)
    assert evaluate_h5(inputs, target, lam=LAM, tau=100.0).e0_twh == pytest.approx(200.0)
    infinite = _inputs(energy, lcoe=[[10.0] * 4, [np.inf] * 4])
    assert evaluate_h5(infinite, target, lam=LAM, tau=1.0e9).e0_twh == pytest.approx(100.0)


@pytest.mark.unit
def test_without_hazard_members_the_exposure_is_not_available_and_there_is_no_verdict():
    result = evaluate_h5(
        _inputs(_example().energy_twh), Target(300.0, "TWh/year", 2030, "t"), lam=LAM, tau=TAU
    )
    assert result.status == TESTED and result.h5a_holds is True
    assert not result.exposure_available and result.r_exp is None and result.h5b_holds is None
    assert result.verdict is None and "H5b is not available" in result.verdict_reason


@pytest.mark.unit
def test_the_sensitivities_never_change_the_primary_result_and_cover_the_listed_settings():
    inputs = _example()
    target = Target(300.0, "TWh/year", 2030, "t")
    primary = evaluate_h5(inputs, target, lam=LAM, tau=TAU)
    variants = sensitivity_variants(
        inputs,
        target,
        primary,
        lam_sensitivity=0.10,
        tau_range=(10.0, 70.0),
        tcr_exception_gcms=("C",),
    )
    by_name = {v.variant: v for v in variants}
    assert set(by_name) == {
        "lambda_0.10",
        "tau_min",
        "tau_max",
        "dynamic_domain",
        "without_C",
        "channel_heat",
    }
    assert by_name["lambda_0.10"].lam == 0.10 and by_name["lambda_0.10"].r_loss == primary.r_loss
    assert by_name["without_C"].excluded_gcms == ("C",)
    assert (
        by_name["without_C"].member_energy_twh == primary.member_energy_twh
    )  # all members are still listed
    assert by_name["without_C"].delta_e_twh == pytest.approx(50.0)  # the loss is in member B
    assert evaluate_h5(inputs, target, lam=LAM, tau=TAU) == primary
    gw = sensitivity_variants(
        inputs,
        Target(1.0, "GW", 2030, "t"),
        evaluate_h5(inputs, Target(1.0, "GW", 2030, "t"), lam=LAM, tau=TAU),
        lam_sensitivity=0.10,
        tau_range=None,
        tcr_exception_gcms=(),
        alternative_targets=[Target(2.0, "GW", 2040, "alt")],
    )
    assert {"conversion_whole_domain", "target_alternative_1"} <= {v.variant for v in gw}


@pytest.mark.unit
def test_removing_the_gcm_that_attains_the_minimum_changes_the_loss_and_the_members():
    result = evaluate_h5(
        _example(),
        Target(300.0, "TWh/year", 2030, "t"),
        lam=LAM,
        tau=TAU,
        excluded_gcms=("B",),
        variant="x",
    )
    assert result.delta_e_twh == pytest.approx(30.0)  # members A (480) and C (470) remain
    assert result.member_min == "C_ssp3" and result.e_exp_twh == pytest.approx(0.0)
    assert result.hazard_members == ("A_ssp1", "C_ssp3")
    with pytest.raises(H5Error):
        evaluate_h5(
            _example(), Target(300.0, "TWh/year", 2030, "t"), lam=LAM, tau=TAU, excluded_gcms=GCMS
        )


@pytest.mark.unit
def test_a_unit_other_than_gw_or_twh_per_year_is_refused():
    with pytest.raises(H5Error, match="unit"):
        evaluate_h5(_example(), Target(5.0, "MW", 2030, "t"), lam=LAM, tau=TAU)


@pytest.mark.unit
def test_a_ratio_exactly_at_lambda_holds():
    # E_0 = 100, G = 50 -> H_0 = 50, Delta E = 10 -> R_loss = 0.20 exactly
    result = evaluate_h5(
        _inputs([[100.0, 90.0, 95.0, 99.0]]), Target(50.0, "TWh/year", 2030, "t"), lam=0.20, tau=TAU
    )
    assert result.r_loss == pytest.approx(0.20) and result.h5a_holds is True
