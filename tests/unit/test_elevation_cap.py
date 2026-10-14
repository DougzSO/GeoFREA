"""OQ-058: the `elevation_max_m` parameter of the land-availability configuration (M-F2b-06)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from geofrea.land_eligibility.parameters import (
    ElevationCap,
    elevation_role,
    elevation_sensitivity_m,
    load_land_availability,
    nominal_set,
)

EXPERIMENTS = Path(__file__).resolve().parents[2] / "config" / "experiments.yaml"


@pytest.mark.unit
def test_the_real_configuration_has_no_central_limit_and_a_unsourced_tier_3_sensitivity_for_wind_only():
    la = load_land_availability(EXPERIMENTS)
    cap = la.technologies["wind"].elevation_max_m
    assert cap is not None and cap.nominal is None and cap.sensitivity == 3000.0
    assert cap.tier == 3 and cap.source is None and cap.status == "sensitivity_unsourced"
    assert la.technologies["solar"].elevation_max_m is None
    assert (
        nominal_set(la.technologies["wind"]).elevation_max_m is None
    )  # no exclusion in the central case
    assert (
        elevation_sensitivity_m(la, "wind") == 3000.0
        and elevation_sensitivity_m(la, "solar") is None
    )


@pytest.mark.unit
def test_a_limit_with_a_value_and_no_source_cannot_claim_to_be_sourced():
    with pytest.raises(ValidationError, match="without a source"):
        ElevationCap(nominal=3000.0, unit="m", status="sourced")
    ElevationCap(nominal=3000.0, unit="m", status="sensitivity_unsourced", tier=3)


@pytest.mark.unit
def test_the_role_of_the_altitude_sensitivity_names_the_limit():
    assert elevation_role(3000.0) == "core_below_3000m"
