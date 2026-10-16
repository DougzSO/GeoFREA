"""M-F5-03 (METHODOLOGY 15.0.0): the density correction applies at every altitude, and `rho_ref / rho_ISA(z + H)` is only reported."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from geofrea.core.constants import ISA_T0_K
from geofrea.siting_layers.sanity import isa_density_kg_m3
from geofrea.technical_potential.density_check import (
    RATIO_HIGH,
    RATIO_LOW,
    isa_density_ratio,
    outside_isa_check,
)
from geofrea.technical_potential.power_curve import load_power_curve
from geofrea.technical_potential.weibull_cf import wind_cf_member

CURVE = load_power_curve(
    Path(__file__).resolve().parents[2] / "config" / "turbines" / "iea_3.4_130.csv"
)


@pytest.mark.unit
def test_the_isa_density_at_sea_level_and_at_4000_m_matches_the_standard_table():
    assert isa_density_kg_m3(0.0) == pytest.approx(1.2250, abs=5e-4)
    assert isa_density_kg_m3(4000.0) == pytest.approx(0.8194, abs=5e-4)


@pytest.mark.unit
@pytest.mark.parametrize("elevation_m", [0.0, 4000.0])
def test_a_layer_equal_to_the_standard_atmosphere_at_the_hub_has_ratio_one_at_0_and_4000_m(
    elevation_m,
):
    hub = 100.0
    rho = isa_density_kg_m3(elevation_m + hub)
    ratio = isa_density_ratio(np.array([rho]), np.array([elevation_m]), hub)
    assert ratio[0] == pytest.approx(1.0, abs=1e-12)
    assert not outside_isa_check(ratio)[0]


@pytest.mark.unit
def test_a_sea_level_density_on_a_4000_m_cell_is_outside_the_check_and_still_not_changed():
    """The density of a plain placed on a plateau is inconsistent with its elevation: the ratio is far above 1.10, the cell is counted and nothing else happens."""
    rho = np.array([1.225, 1.225])
    ratio = isa_density_ratio(rho, np.array([0.0, 4000.0]), 100.0)
    assert ratio[0] == pytest.approx(
        1.225 / isa_density_kg_m3(100.0), rel=1e-12
    )  # about 1.01: inside
    assert ratio[1] > RATIO_HIGH
    assert outside_isa_check(ratio).tolist() == [False, True]
    assert rho.tolist() == [1.225, 1.225]


@pytest.mark.unit
def test_the_bounds_are_those_of_the_verdict_and_non_finite_values_are_outside():
    assert (RATIO_LOW, RATIO_HIGH) == (0.90, 1.10)
    assert outside_isa_check(np.array([0.9, 1.1, 0.899, 1.101, np.nan, np.inf])).tolist() == [
        False,
        False,
        True,
        True,
        True,
        True,
    ]


@pytest.mark.unit
@pytest.mark.parametrize("rho_over_rho0", [0.5, 0.7, 0.95, 1.0, 1.05])
def test_the_density_correction_is_not_truncated_at_any_altitude(rho_over_rho0):
    """The capacity factor at density `rho` is the one of the reference density with the scale multiplied by `(rho / rho0)^(1/3)`, even at 0.5."""
    rho0 = CURVE.reference_density_kg_m3 or 1.225
    a, k = np.array([8.0]), np.array([2.2])
    d_t, delta_wind = np.array([0.0]), np.array([1.0])
    thin = wind_cf_member(
        a, k, np.array([rho_over_rho0 * rho0]), d_t, delta_wind, CURVE, 1.0, rho0, ISA_T0_K
    )
    equivalent = wind_cf_member(
        a * rho_over_rho0 ** (1.0 / 3.0),
        k,
        np.array([rho0]),
        d_t,
        delta_wind,
        CURVE,
        1.0,
        rho0,
        ISA_T0_K,
    )
    assert thin[0] == pytest.approx(equivalent[0], rel=1e-12)
    if rho_over_rho0 < 1.0:
        reference = wind_cf_member(
            a, k, np.array([rho0]), d_t, delta_wind, CURVE, 1.0, rho0, ISA_T0_K
        )
        assert thin[0] < reference[0]
