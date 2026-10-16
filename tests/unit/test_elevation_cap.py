"""OQ-058: the `elevation_max_m` parameter of the land-availability configuration (M-F2b-06)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from geofrea.config_models.land_availability import (
    ElevationCap,
    elevation_role,
    elevation_sensitivity_m,
    load_land_availability,
    nominal_set,
)

EXPERIMENTS = Path(__file__).resolve().parents[2] / "config" / "experiments.yaml"


@pytest.mark.unit
def test_the_real_configuration_excludes_wind_above_3000_m_as_an_unsourced_tier_3_limit_and_solar_has_none():
    la = load_land_availability(EXPERIMENTS)
    cap = la.technologies["wind"].elevation_max_m
    assert cap is not None and cap.nominal == 3000.0 and cap.sensitivity is None
    assert cap.tier == 3 and cap.source is None and cap.status == "excluded_unsourced"
    assert la.technologies["solar"].elevation_max_m is None
    assert nominal_set(la.technologies["wind"]).elevation_max_m == 3000.0  # excluded in the central case
    assert nominal_set(la.technologies["solar"]).elevation_max_m is None
    assert elevation_sensitivity_m(la, "wind") is None and elevation_sensitivity_m(la, "solar") is None


@pytest.mark.unit
def test_a_limit_with_a_value_and_no_source_cannot_claim_to_be_sourced():
    with pytest.raises(ValidationError, match="without a source"):
        ElevationCap(nominal=3000.0, unit="m", status="sourced")
    ElevationCap(nominal=3000.0, unit="m", status="sensitivity_unsourced", tier=3)


@pytest.mark.unit
def test_the_role_of_the_altitude_sensitivity_names_the_limit():
    assert elevation_role(3000.0) == "core_below_3000m"
