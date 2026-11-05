"""OQ-058, Group 6: the `elevation_max_m` parameter of the land-eligibility configuration (M-F2b-06)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from geofrea.config_models.land_availability import (
    ScenarioValue,
    elevation_role,
    elevation_sensitivity_m,
    load_land_availability,
)
from geofrea.land_eligibility.scenarios import scenario_sets

EXPERIMENTS = Path(__file__).resolve().parents[2] / "config" / "experiments.yaml"
PROJECT_AREA = {"restrictive": 3.0, "central": 2.0, "permissive": 1.0}


@pytest.mark.unit
def test_the_real_configuration_limits_wind_to_2000_m_restrictive_3000_m_central_and_nothing_permissive_and_solar_has_none():
    la = load_land_availability(EXPERIMENTS)
    cap = la.technologies["wind"].elevation_max_m
    assert cap is not None and (cap.restrictive, cap.central, cap.permissive) == (2000.0, 3000.0, None)
    assert cap.sensitivity is None and cap.tier == 3 and cap.status == "verify"  # the central 3,000 m is Tier 3 and the source edition is to verify
    assert la.technologies["solar"].elevation_max_m is None
    wind = scenario_sets(la, "wind", "BRA", PROJECT_AREA)
    assert [wind[s].elevation_max_m for s in ("restrictive", "central", "permissive")] == [2000.0, 3000.0, None]
    assert {s.elevation_max_m for s in scenario_sets(la, "solar", "BRA", PROJECT_AREA).values()} == {None}
    assert elevation_sensitivity_m(la, "wind") is None and elevation_sensitivity_m(la, "solar") is None


@pytest.mark.unit
def test_a_limit_with_a_value_and_no_source_cannot_claim_to_be_sourced_and_must_be_tier_3():
    with pytest.raises(ValidationError, match="without a source"):
        ScenarioValue(restrictive=None, central=3000.0, permissive=None, unit="m", status="sourced")
    with pytest.raises(ValidationError, match="Tier 3"):
        ScenarioValue(restrictive=None, central=3000.0, permissive=None, unit="m", status="verify")
    ScenarioValue(restrictive=None, central=3000.0, permissive=None, unit="m", status="verify", tier=3)


@pytest.mark.unit
def test_the_role_of_the_altitude_sensitivity_names_the_limit():
    assert elevation_role(3000.0) == "core_below_3000m"