"""F5 pure functions: capacity, solar and wind capacity factor, interpolation, power curve, rescale (V-02, V-03, M-F5-01 to M-F5-05)."""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.special import gamma as gamma_fn

from geofrea.core.constants import HOURS_PER_DAY, HOURS_PER_YEAR, RHO0_KG_M3
from geofrea.technical_potential.capacity import annual_energy_mwh, capacity_mw
from geofrea.technical_potential.power_curve import (
    PowerCurve,
    PowerCurveError,
    SyntheticCurveError,
    assert_curve_usable,
    curve_file_sha256,
    load_power_curve,
)
from geofrea.technical_potential.rescale import rescale_cf_solar, rescale_cf_wind
from geofrea.technical_potential.solar import solar_cf_member, solar_cf_reference
from geofrea.technical_potential.weibull_cf import (
    equivalent_scale,
    member_cf_ratio,
    weibull_capacity_factor,
    weibull_mean_speed,
    wind_cf_member,
    wind_cf_reference,
)
from geofrea.technical_potential.wind_profile import (
    HubHeightError,
    bracket_heights,
    linear_at_height,
    resource_at_hub_height,
    weibull_scale_at_height,
)

CURVE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "power_curves" / "synthetic_curve.yaml"
)
V02_RELATIVE_TOLERANCE = 1e-6  # D-F5-002
QUAD_EPSREL = 1e-10  # D-F5-002


@pytest.fixture(scope="module")
def curve() -> PowerCurve:
    return load_power_curve(CURVE_PATH)


def _weibull_pdf(u: float, a: float, k: float) -> float:
    return (k / a) * (u / a) ** (k - 1.0) * np.exp(-((u / a) ** k))


def _reference_cf(a: float, k: float, curve: PowerCurve, speed_factor: float = 1.0) -> float:
    """Independent reference: `quad` per curve segment with breakpoints at the nodes, curve read as piecewise linear.

    `speed_factor` multiplies the speed the curve sees, `P(c * v)`, which is the direct form of the density correction.
    """
    v = np.asarray(curve.v_ms)
    p = np.asarray(curve.p_normalized)

    def power(u: float) -> float:
        return float(np.interp(speed_factor * u, v, p, left=0.0, right=0.0))

    edges = v / speed_factor
    total = 0.0
    for lo, hi in pairwise(edges):
        part, _err = quad(
            lambda u: power(u) * _weibull_pdf(u, a, k),
            lo,
            hi,
            epsabs=0.0,
            epsrel=QUAD_EPSREL,
            limit=200,
        )
        total += part
    return total


AK_GRID = [(a, k) for a in (3.0, 5.5, 8.0, 11.0, 14.0) for k in (1.3, 2.0, 2.7, 3.5)]


# -- V-02: Weibull CF against numerical integration ---------------------------------------------


@pytest.mark.unit
def test_weibull_cf_matches_numerical_integration_over_a_grid(curve):
    a = np.array([x[0] for x in AK_GRID])
    k = np.array([x[1] for x in AK_GRID])
    exact = weibull_capacity_factor(a, k, curve)
    reference = np.array([_reference_cf(ai, ki, curve) for ai, ki in AK_GRID])
    np.testing.assert_allclose(exact, reference, rtol=V02_RELATIVE_TOLERANCE, atol=0.0)


@pytest.mark.unit
def test_density_folds_into_the_scale(curve):
    """M-F5-03: the integral of `P(c v) f(v)` with `c = (rho / rho0)^(1/3)` equals `I(c A, k)`."""
    rho = np.array([1.05, 1.225, 1.3])
    a = np.array([7.0, 9.0, 6.0])
    k = np.array([2.0, 2.4, 1.8])
    folded = weibull_capacity_factor(equivalent_scale(a, rho, RHO0_KG_M3), k, curve)
    direct = np.array(
        [
            _reference_cf(ai, ki, curve, speed_factor=(ri / RHO0_KG_M3) ** (1 / 3))
            for ai, ki, ri in zip(a, k, rho, strict=True)
        ]
    )
    np.testing.assert_allclose(folded, direct, rtol=V02_RELATIVE_TOLERANCE)


@pytest.mark.unit
def test_ratio_form_equals_direct_form(curve):
    """M-F5-03: `CF0 * I(dw A_eq) / I(A_eq)` equals `eta * I(dw A_eq)`; eta cancels in the ratio."""
    a = np.array([6.5, 8.0, 10.0])
    k = np.array([2.0, 2.2, 3.0])
    rho = np.array([1.1, 1.2, 1.25])
    dw = np.array([0.93, 1.0, 1.08])
    eta = 0.9
    cf0 = wind_cf_reference(a, k, rho, curve, RHO0_KG_M3, eta)
    ratio_form = cf0 * member_cf_ratio(a, k, rho, dw, curve, RHO0_KG_M3)
    a_eq = equivalent_scale(a, rho, RHO0_KG_M3)
    direct_form = wind_cf_member(a_eq, k, dw, curve, eta)
    np.testing.assert_allclose(ratio_form, direct_form, rtol=1e-12)


@pytest.mark.unit
def test_reference_member_returns_cf0_exactly(curve):
    a, k, rho = np.array([7.0, 9.5]), np.array([2.0, 2.5]), np.array([1.2, 1.1])
    cf0 = wind_cf_reference(a, k, rho, curve, RHO0_KG_M3, 0.85)
    member = wind_cf_member(equivalent_scale(a, rho, RHO0_KG_M3), k, np.ones(2), curve, 0.85)
    np.testing.assert_array_equal(cf0, member)


@pytest.mark.unit
def test_cf_is_between_zero_and_one_and_grows_with_the_scale_below_the_cut_out_region(curve):
    """V-03: `0 <= CF <= 1`. CF grows with A while the cut-out does not dominate (it falls for very large A, as it should)."""
    a = np.linspace(2.0, 20.0, 40)
    cf = weibull_capacity_factor(a, np.full_like(a, 2.0), curve)
    assert (cf >= 0).all() and (cf <= 1).all()
    rising = a <= 10.0
    assert (np.diff(cf[rising]) > 0).all()
    assert cf[-1] < cf.max()


@pytest.mark.unit
def test_degenerate_curve_gives_closed_form_cf(curve):
    """A curve that is 1 from 0 to the cut-out has `CF = F(cut-out)` for the Weibull CDF (closed form)."""
    flat = PowerCurve(
        curve_id="flat",
        iec_class="synthetic",
        rated_power_kw=1000.0,
        v_ms=[0.0, 1e-9, 20.0],
        p_kw=[0.0, 1000.0, 1000.0],
        cut_out_ms=20.0,
        synthetic=True,
    )
    a, k = np.array([8.0]), np.array([2.0])
    expected = 1.0 - np.exp(-((20.0 / 8.0) ** 2.0))
    np.testing.assert_allclose(weibull_capacity_factor(a, k, flat), expected, rtol=1e-8)


@pytest.mark.unit
@pytest.mark.parametrize("bad_a, bad_k", [(0.0, 2.0), (-1.0, 2.0), (5.0, 0.0), (np.nan, 2.0)])
def test_weibull_cf_rejects_invalid_parameters(curve, bad_a, bad_k):
    with pytest.raises(ValueError):
        weibull_capacity_factor(np.array([bad_a]), np.array([bad_k]), curve)


@pytest.mark.unit
def test_weibull_cf_is_chunk_independent(curve, monkeypatch):
    import geofrea.technical_potential.weibull_cf as module

    rng = np.random.default_rng(7)
    a, k = rng.uniform(4, 12, 37), rng.uniform(1.5, 3.2, 37)
    whole = weibull_capacity_factor(a, k, curve)
    monkeypatch.setattr(module, "_CHUNK_CELLS", 5)
    np.testing.assert_array_equal(module.weibull_capacity_factor(a, k, curve), whole)


@pytest.mark.unit
def test_weibull_mean_speed_closed_form():
    assert weibull_mean_speed(np.array([8.0]), np.array([1.0]))[0] == pytest.approx(8.0)
    assert weibull_mean_speed(np.array([8.0]), np.array([2.0]))[0] == pytest.approx(
        8.0 * gamma_fn(1.5)
    )


# -- V-02: power-law and linear interpolation ---------------------------------------------------


@pytest.mark.unit
def test_power_law_with_equal_scale_at_both_heights_returns_that_scale():
    a = np.array([7.2, 5.0])
    out = weibull_scale_at_height(a, a, 100.0, 150.0, 123.0)
    np.testing.assert_allclose(out, a, rtol=1e-14)


@pytest.mark.unit
def test_power_law_reproduces_the_data_heights_exactly():
    a1, a2 = np.array([6.0, 7.0]), np.array([7.5, 8.0])
    np.testing.assert_allclose(weibull_scale_at_height(a1, a2, 100.0, 150.0, 100.0), a1, rtol=1e-14)
    np.testing.assert_allclose(weibull_scale_at_height(a1, a2, 100.0, 150.0, 150.0), a2, rtol=1e-14)


@pytest.mark.unit
def test_power_law_closed_form_case():
    """Doubling the height with `alpha = 0.5` multiplies the scale by `sqrt(2)`: A(200) = A(100) * 2^0.5."""
    a1 = np.array([6.0])
    a2 = a1 * 2.0**0.5
    mid = weibull_scale_at_height(a1, a2, 100.0, 200.0, 141.4213562373095)
    np.testing.assert_allclose(mid, a1 * (1.4142135623730951**0.5), rtol=1e-12)


@pytest.mark.unit
def test_linear_interpolation_midpoint_and_ends():
    v1, v2 = np.array([1.2]), np.array([1.1])
    assert linear_at_height(v1, v2, 100.0, 200.0, 150.0)[0] == pytest.approx(1.15)
    assert linear_at_height(v1, v2, 100.0, 200.0, 100.0)[0] == pytest.approx(1.2)
    assert linear_at_height(v1, v2, 100.0, 200.0, 200.0)[0] == pytest.approx(1.1)


@pytest.mark.unit
@pytest.mark.parametrize("hub", [99.9, 200.1, 0.0, 300.0])
def test_hub_height_outside_the_data_heights_raises(hub):
    with pytest.raises(HubHeightError, match="does not extrapolate"):
        bracket_heights(hub, [100, 150, 200])


@pytest.mark.unit
def test_bracket_heights_picks_the_bracketing_pair():
    assert bracket_heights(125.0, [100, 150, 200]) == (100.0, 150.0)
    assert bracket_heights(175.0, [200, 100, 150]) == (150.0, 200.0)
    assert bracket_heights(200.0, [100, 150, 200]) == (150.0, 200.0)
    assert bracket_heights(100.0, [100, 150, 200]) == (100.0, 150.0)


@pytest.mark.unit
def test_resource_at_hub_height_uses_the_bracketing_heights_and_checks_alignment():
    a = {100: np.array([6.0]), 150: np.array([7.0]), 200: np.array([7.5])}
    k = {100: np.array([2.0]), 150: np.array([2.2]), 200: np.array([2.4])}
    rho = {100: np.array([1.2]), 150: np.array([1.18]), 200: np.array([1.16])}
    a_h, k_h, rho_h = resource_at_hub_height(a, k, rho, 125.0)
    assert k_h[0] == pytest.approx(2.1)
    assert rho_h[0] == pytest.approx(1.19)
    assert a_h[0] == pytest.approx(6.0 * (1.25 ** (np.log(7.0 / 6.0) / np.log(1.5))))
    with pytest.raises(ValueError, match="same heights"):
        resource_at_hub_height(a, {100: k[100]}, rho, 125.0)


@pytest.mark.unit
def test_non_positive_scale_raises():
    with pytest.raises(ValueError, match="positive"):
        weibull_scale_at_height(np.array([0.0]), np.array([5.0]), 100.0, 150.0, 120.0)


# -- M-F5-02: solar -----------------------------------------------------------------------------


@pytest.mark.unit
def test_pvout_to_cf_units_only():
    """Units only (no data value): 24 kWh/kWp/day is a CF of 1, 0 is 0, 6 is 0.25."""
    cf0 = solar_cf_reference(np.array([24.0, 0.0, 6.0]), HOURS_PER_DAY)
    np.testing.assert_array_equal(cf0, [1.0, 0.0, 0.25])


@pytest.mark.unit
def test_solar_member_reference_factors_return_cf0_and_gamma_sign():
    cf0 = np.array([0.2, 0.25])
    np.testing.assert_array_equal(solar_cf_member(cf0, np.ones(2), np.zeros(2), gamma=-0.004), cf0)
    warmer = solar_cf_member(cf0, np.ones(2), np.full(2, 2.0), gamma=-0.004)
    assert (warmer < cf0).all()
    np.testing.assert_allclose(warmer, cf0 * (1 - 0.008))
    brighter = solar_cf_member(cf0, np.full(2, 1.05), np.zeros(2), gamma=-0.004)
    np.testing.assert_allclose(brighter, cf0 * 1.05)


# -- M-F5-01 and M-F5-05 -------------------------------------------------------------------------


@pytest.mark.unit
def test_capacity_and_energy_closed_form():
    p = capacity_mw(np.array([10.0, 0.0, 2.5]), luf=0.5, power_density_mw_per_km2=10.0)
    np.testing.assert_allclose(p, [50.0, 0.0, 12.5])
    e = annual_energy_mwh(p, np.array([0.2, 0.3, 0.5]), HOURS_PER_YEAR)
    np.testing.assert_allclose(e, [50.0 * 0.2 * 8760, 0.0, 12.5 * 0.5 * 8760])


@pytest.mark.unit
@pytest.mark.parametrize(
    "luf, pd_, area", [(1.2, 10.0, 1.0), (-0.1, 10.0, 1.0), (0.5, -1.0, 1.0), (0.5, 10.0, -1.0)]
)
def test_capacity_rejects_out_of_domain_inputs(luf, pd_, area):
    with pytest.raises(ValueError):
        capacity_mw(np.array([area]), luf, pd_)


# -- rescale (D-F5-008) -------------------------------------------------------------------------


@pytest.mark.unit
def test_rescale_wind_equals_recomputing_with_the_new_eta(curve):
    a_eq, k, dw = np.array([8.0, 9.5]), np.array([2.0, 2.6]), np.array([0.95, 1.05])
    nominal = wind_cf_member(a_eq, k, dw, curve, 0.9)
    np.testing.assert_allclose(
        rescale_cf_wind(nominal, 0.9, 0.8), wind_cf_member(a_eq, k, dw, curve, 0.8), rtol=1e-13
    )


@pytest.mark.unit
def test_rescale_solar_equals_recomputing_with_the_new_gamma():
    cf0, rsds, d_t = np.array([0.2, 0.22]), np.array([1.02, 0.98]), np.array([1.5, 3.0])
    nominal = solar_cf_member(cf0, rsds, d_t, -0.004)
    np.testing.assert_allclose(
        rescale_cf_solar(nominal, d_t, -0.004, -0.006),
        solar_cf_member(cf0, rsds, d_t, -0.006),
        rtol=1e-13,
    )


@pytest.mark.unit
def test_rescale_rejects_undefined_cases():
    with pytest.raises(ValueError):
        rescale_cf_wind(np.array([0.3]), 0.0, 0.9)
    with pytest.raises(ValueError, match="undefined"):
        rescale_cf_solar(np.array([0.2]), np.array([250.0]), -0.004, -0.005)


# -- power curve schema (A-09, D-F5-003) -----------------------------------------------------------


def _curve_dict(**changes):
    base = {
        "curve_id": "c",
        "iec_class": "synthetic",
        "rated_power_kw": 100.0,
        "v_ms": [3.0, 5.0, 10.0],
        "p_kw": [0.0, 50.0, 100.0],
        "cut_out_ms": 10.0,
        "synthetic": True,
    }
    return {**base, **changes}


@pytest.mark.unit
@pytest.mark.parametrize(
    "changes, message",
    [
        ({"v_ms": [3.0, 3.0, 10.0]}, "strictly increasing"),
        ({"v_ms": [3.0, 5.0, 8.0]}, "cut-out must be declared"),
        ({"p_kw": [0.0, 50.0, 120.0], "rated_power_kw": 100.0}, "must lie in"),
        ({"p_kw": [10.0, 50.0, 100.0]}, "zero power"),
        ({"p_kw": [0.0, 50.0, 90.0]}, "largest node power"),
        ({"p_kw": [0.0, 50.0]}, "same length"),
        ({"tier": 2}, "no evidence tier"),
        ({"synthetic": False}, "needs a source and a tier"),
    ],
)
def test_power_curve_validation(changes, message):
    with pytest.raises(ValueError, match=message):
        PowerCurve.model_validate(_curve_dict(**changes))


@pytest.mark.unit
def test_loader_checks_the_stem_and_the_file(tmp_path, curve):
    with pytest.raises(PowerCurveError, match="not found"):
        load_power_curve(tmp_path / "absent.yaml")
    wrong = tmp_path / "other_name.yaml"
    wrong.write_text(CURVE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(PowerCurveError, match="differs from the file stem"):
        load_power_curve(wrong)
    assert curve.cut_out_ms == curve.v_ms[-1] and curve.synthetic
    assert len(curve_file_sha256(CURVE_PATH)) == 64


@pytest.mark.unit
def test_synthetic_curve_is_refused_in_production_only(curve):
    assert_curve_usable(curve, production=False)
    with pytest.raises(SyntheticCurveError, match="production"):
        assert_curve_usable(curve, production=True)
