"""The Group 1 and Group 2 values recorded in `config/parameters.json` against the tables of the .tex (M-F5-01, M-F5-03, M-F6-07, U-05).

Not a check of the sources (the audit `docs/phases/F5/audit_groups1-2.md` did that); a check that the file holds what the tables say,
with the schema of U-05, and that the F6 sampler reproduces the IRENA mean (eq:g2_capex_interval).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from geofrea.core.config_loader import load_parameters, load_technologies
from geofrea.core.production import audit_parameters
from geofrea.lcoe_modeling.design import build_design
from geofrea.lcoe_modeling.sampling import UncertainSpec, draw_lhs
from geofrea.technical_potential.pipeline import resolve_technology
from geofrea.technical_potential.power_curve import PowerCurve, assert_curve_usable, load_power_curve
from geofrea.technical_potential.weibull_cf import weibull_capacity_factor
from tests.unit.test_technical_potential_functions import AK_GRID, V02_RELATIVE_TOLERANCE, _reference_cf

REPO = Path(__file__).resolve().parents[2]
PARAMS = load_parameters(REPO / "config" / "parameters.json")
COUNTRIES = ("BRA", "PRT", "IND")

LUF = {
    ("solar", "BRA"): (0.10, 0.25, 0.35),
    ("solar", "PRT"): (0.10, 0.25, 0.35),
    ("solar", "IND"): (0.05, 0.10, 0.25),
    ("wind", "BRA"): (0.05, 0.15, 0.30),
    ("wind", "PRT"): (0.05, 0.15, 0.30),
    ("wind", "IND"): (0.05, 0.075, 0.15),
}
CAPEX = {  # IRENA mean, P5
    ("solar", "BRA"): (724, 503),
    ("solar", "IND"): (525, 415),
    ("solar", "PRT"): (779, 524),
    ("wind", "BRA"): (1307, 1015),
    ("wind", "IND"): (1110, 984),
    ("wind", "PRT"): (1659, 1211),
}
OPEX = {  # central, min, max of tab:g2_opex; PRT wind from the European rows of IRENA Table A3 (29 to 53, midpoint 41) over 1659
    ("solar", "BRA"): (0.0124, 0.0097, 0.0181),
    ("solar", "IND"): (0.0171, 0.0133, 0.0250),
    ("solar", "PRT"): (0.0250, 0.0234, 0.0266),
    ("wind", "BRA"): (0.0222, 0.0178, 0.0266),
    ("wind", "IND"): (0.0207, 0.0166, 0.0249),
    ("wind", "PRT"): (41 / 1659, 29 / 1659, 53 / 1659),
}


def _tech(iso: str, tech: str):
    return getattr(PARAMS.countries[iso].technologies, tech)


@pytest.mark.unit
@pytest.mark.parametrize("tech, iso", sorted(LUF))
def test_luf_and_power_density_are_the_scenario_triples_of_the_tex(tech, iso):
    t = _tech(iso, tech)
    s = t.luf.scenario_values
    assert (s.restrictive, s.central, s.permissive) == LUF[(tech, iso)]
    assert t.luf.value == s.central and t.luf.range is None and t.luf.tier == 3
    expected = (45.0, 50.0, 75.0) if tech == "solar" else (3.32, 4.99, 7.12)
    pd_s = t.power_density_mw_per_km2.scenario_values
    assert (pd_s.restrictive, pd_s.central, pd_s.permissive) == expected
    assert t.power_density_mw_per_km2.tier == 2 and t.power_density_mw_per_km2.range is None


@pytest.mark.unit
@pytest.mark.parametrize("iso", COUNTRIES)
def test_gamma_eta_and_hub_height_of_group_1(iso):
    g = _tech(iso, "solar").gamma
    assert g.value == -0.0030 and (g.range.min, g.range.max) == (-0.0032, -0.0028)
    assert g.range.distribution == "uniform"
    e = _tech(iso, "wind").eta_loss  # a retention factor: 0.866, not the 13.4 percent loss
    assert e.value == 0.866 and (e.range.min, e.range.max) == (0.803, 0.932)
    assert e.range.distribution == "uniform"
    assert _tech(iso, "wind").hub_height_m.value == 100.0


@pytest.mark.unit
@pytest.mark.parametrize("tech, iso", sorted(CAPEX))
def test_capex_is_the_irena_mean_on_the_symmetric_interval_without_ilr(tech, iso):
    mean, p5 = CAPEX[(tech, iso)]
    c = _tech(iso, tech).capex_usd_per_kw
    assert c.value == mean and c.range.min == p5 and c.range.max == 2 * mean - p5
    assert c.range.distribution == "uniform" and c.price_year == 2024 and c.proxy is False


@pytest.mark.unit
@pytest.mark.parametrize("tech, iso", sorted(CAPEX))
def test_the_mean_of_10000_capex_draws_is_the_irena_mean(tech, iso):
    c = _tech(iso, tech).capex_usd_per_kw
    spec = UncertainSpec("capex_usd_per_kw", c.value, c.range.min, c.range.max, c.range.distribution)
    draws = draw_lhs([spec], 10_000, seed=20261016)["capex_usd_per_kw"].to_numpy()[1:]
    assert abs(draws.mean() / CAPEX[(tech, iso)][0] - 1.0) < 0.01


@pytest.mark.unit
@pytest.mark.parametrize("tech, iso", sorted(OPEX))
def test_fixed_om_fraction_variable_om_zero_lifetime_and_year(tech, iso):
    t = _tech(iso, tech)
    f, lo, hi = OPEX[(tech, iso)]
    assert t.opex_fixed_frac.value == pytest.approx(f, abs=5e-7)
    assert t.opex_fixed_frac.range.min == pytest.approx(lo, abs=5e-7)
    assert t.opex_fixed_frac.range.max == pytest.approx(hi, abs=5e-7)
    assert t.opex_var_usd_per_mwh.value == 0.0 and t.opex_var_usd_per_mwh.price_year == 2024
    assert t.lifetime_years.value == 30
    assert (t.lifetime_years.range.min, t.lifetime_years.range.max) == (25.0, 30.0)
    assert t.commissioning_year.value == 2026


@pytest.mark.unit
@pytest.mark.parametrize("tech", ["solar", "wind"])
@pytest.mark.parametrize("iso", COUNTRIES)
def test_no_discount_rate_is_recorded_and_nothing_is_a_proxy(tech, iso):
    t = _tech(iso, tech)
    assert t.discount_rate.value is None and t.discount_rate.range is None
    for key, entry in t.__dict__.items():
        if hasattr(entry, "proxy"):
            assert entry.proxy is False, key


@pytest.mark.unit
def test_the_design_rounds_the_lifetime_to_whole_years_so_the_crf_never_sees_a_fraction():
    """A non-integer lifetime is not supported by the F6 kernel: the draw is continuous and the design matrix rounds it (D-F6-010)."""
    spec = UncertainSpec("lifetime_years", 30.0, 25.0, 30.0, "uniform")
    design = build_design([spec], 200, seed=1)
    assert (design["lifetime_years"] == np.round(design["lifetime_years"])).all()
    assert design["lifetime_years"].iloc[0] == 30.0


@pytest.mark.unit
def test_the_loader_audit_leaves_no_f5_gap_and_only_discount_rate_and_group_3_for_f6():
    technologies = load_technologies(REPO / "config" / "technologies.yaml")
    audit = audit_parameters(PARAMS, technologies, list(COUNTRIES), ["solar", "wind"])
    f5 = {"luf", "power_density_mw_per_km2", "gamma", "eta_loss", "hub_height_m"}
    f6_open = {
        "discount_rate",
        "degradation_rate",
        "grid_cost_usd_per_mw_km",
        "substation_cost_usd_per_mw",
        "road_cost_usd_per_km",
    }
    f7 = {"cf_min", "tau_lcoe_usd_per_mwh", "top_k_percent"}
    keys = {e.split(":")[0].split()[-1] for e in audit.errors}
    assert not keys & f5
    assert keys <= f6_open | f7
    assert {"discount_rate", "degradation_rate", "grid_cost_usd_per_mw_km"} <= keys


REAL_CURVE_PATH = REPO / "config" / "turbines" / "iea_3.4_130.csv"


@pytest.fixture(scope="module")
def real_curve() -> PowerCurve:
    return load_power_curve(REAL_CURVE_PATH)


@pytest.mark.unit
def test_the_real_turbine_curve_loads_with_its_provenance_and_integrates_like_the_quadrature(real_curve):
    assert real_curve.curve_id == "iea_3.4_130" and not real_curve.synthetic
    assert (real_curve.v_ms[0], real_curve.cut_in_ms, real_curve.cut_out_ms) == (3.0, 3.0, 25.0)
    assert real_curve.p_kw[0] == pytest.approx(51.62, abs=0.01) and real_curve.p_kw[0] > 0
    assert real_curve.license == "Apache-2.0" and len(real_curve.commit) == 40
    assert real_curve.reference_density_kg_m3 == 1.225 and real_curve.reference_density_verified is False
    assert real_curve.rated_power_kw == pytest.approx(3370.0, rel=1e-4)
    assert_curve_usable(real_curve, production=True)
    a = np.array([x[0] for x in AK_GRID])
    k = np.array([x[1] for x in AK_GRID])
    exact = weibull_capacity_factor(a, k, real_curve)
    reference = np.array([_reference_cf(ai, ki, real_curve) for ai, ki in AK_GRID])
    np.testing.assert_allclose(exact, reference, rtol=V02_RELATIVE_TOLERANCE)
    assert (exact >= 0).all() and (exact <= 1).all()



@pytest.mark.unit
@pytest.mark.parametrize("iso", ["BRA", "PRT", "IND"])
def test_the_real_countries_have_every_f5_input_and_the_real_curve_is_usable(iso):
    """Group 1 is recorded: the three countries resolve for solar and wind with the real turbine in a production run."""
    technologies = load_technologies(REPO / "config" / "technologies.yaml")
    params = PARAMS.countries[iso]
    for tech in ("solar", "wind"):
        resolved = resolve_technology(
            iso, tech, technologies.technologies[tech], getattr(params.technologies, tech),
            REPO / "config" / "turbines", production=True,
        )  # fmt: skip
        assert set(resolved.scenario_parameters) == {"luf", "power_density_mw_per_km2"}


