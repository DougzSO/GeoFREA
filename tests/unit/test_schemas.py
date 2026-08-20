"""Unit tests for geofrea.core.schemas.

Every schema's required fields are tested individually (one
parametrized case per field, not a single "missing fields in general"
test) by removing exactly that field from an otherwise-valid payload
and asserting pydantic raises ValidationError. The same per-case
pattern is used for the extra="forbid" and range-constraint tests
below.
"""

import copy

import pytest
from pydantic import ValidationError

from geofrea.core.schemas import (
    BiomassParams,
    CountryParams,
    ParametersFile,
    TechnologyParams,
    VerifiedValue,
)

VALID_VERIFIED_VALUE = {
    "value": 1.0,
    "source": "IRENA 2025",
    "verified": True,
    "verified_by": "Douglas",
    "verified_date": "2026-08-20",
    "verification_method": "manual_cross_check",
}

VALID_BIOMASS = {
    "capex_usd_per_kw": {**VALID_VERIFIED_VALUE, "value": 3606},
    "opex_fixed_pct_of_capex": {**VALID_VERIFIED_VALUE, "value": 0.04},
    "opex_variable_usd_per_kwh": {**VALID_VERIFIED_VALUE, "value": 0.004},
    "capacity_factor": {**VALID_VERIFIED_VALUE, "value": 0.81},
    "lifetime_years": {**VALID_VERIFIED_VALUE, "value": 20},
    "discount_rate_increment": {
        "value": None,
        "source": None,
        "verified": False,
        "verified_by": None,
        "verified_date": None,
        "verification_method": "unverified",
        "status": "pending_research",
    },
}

VALID_TECHNOLOGIES = {"biomass": VALID_BIOMASS}

VALID_COUNTRY = {
    "discount_rate": {
        "value": 0.07,
        "source": None,
        "verified": False,
        "verified_by": None,
        "verified_date": None,
        "verification_method": "unverified",
    },
    "technologies": VALID_TECHNOLOGIES,
}

VALID_PARAMETERS_FILE = {"countries": {"PRT": VALID_COUNTRY, "BRA": copy.deepcopy(VALID_COUNTRY)}}


# ─── Valid-payload smoke tests ──────────────────────────────────────────


@pytest.mark.unit
def test_verified_value_accepts_valid_payload():
    result = VerifiedValue[float].model_validate(VALID_VERIFIED_VALUE)
    assert result.value == 1.0
    assert result.verified is True


@pytest.mark.unit
def test_biomass_params_accepts_valid_payload():
    result = BiomassParams.model_validate(VALID_BIOMASS)
    assert result.capex_usd_per_kw.value == 3606
    assert result.discount_rate_increment.value is None
    assert result.discount_rate_increment.status == "pending_research"


@pytest.mark.unit
def test_technology_params_accepts_valid_payload():
    result = TechnologyParams.model_validate(VALID_TECHNOLOGIES)
    assert result.biomass.capacity_factor.value == 0.81


@pytest.mark.unit
def test_country_params_accepts_valid_payload():
    result = CountryParams.model_validate(VALID_COUNTRY)
    assert result.discount_rate.value == 0.07
    assert result.technologies.biomass.lifetime_years.value == 20


@pytest.mark.unit
def test_parameters_file_accepts_valid_payload():
    result = ParametersFile.model_validate(VALID_PARAMETERS_FILE)
    assert set(result.countries.keys()) == {"PRT", "BRA"}


# ─── Required-field tests: one parametrized case per field ──────────────


@pytest.mark.unit
@pytest.mark.parametrize("field", ["value", "verified", "verification_method"])
def test_verified_value_missing_required_field_raises(field):
    data = dict(VALID_VERIFIED_VALUE)
    del data[field]
    with pytest.raises(ValidationError):
        VerifiedValue[float].model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize(
    "field",
    [
        "capex_usd_per_kw",
        "opex_fixed_pct_of_capex",
        "opex_variable_usd_per_kwh",
        "capacity_factor",
        "lifetime_years",
        "discount_rate_increment",
    ],
)
def test_biomass_params_missing_required_field_raises(field):
    data = copy.deepcopy(VALID_BIOMASS)
    del data[field]
    with pytest.raises(ValidationError):
        BiomassParams.model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("field", ["biomass"])
def test_technology_params_missing_required_field_raises(field):
    data = copy.deepcopy(VALID_TECHNOLOGIES)
    del data[field]
    with pytest.raises(ValidationError):
        TechnologyParams.model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("field", ["discount_rate", "technologies"])
def test_country_params_missing_required_field_raises(field):
    data = copy.deepcopy(VALID_COUNTRY)
    del data[field]
    with pytest.raises(ValidationError):
        CountryParams.model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("field", ["countries"])
def test_parameters_file_missing_required_field_raises(field):
    data = copy.deepcopy(VALID_PARAMETERS_FILE)
    del data[field]
    with pytest.raises(ValidationError):
        ParametersFile.model_validate(data)


# ─── extra="forbid" tests: one case per model ────────────────────────────


@pytest.mark.unit
def test_verified_value_rejects_unexpected_field():
    data = {**VALID_VERIFIED_VALUE, "unexpected_key": "typo"}
    with pytest.raises(ValidationError):
        VerifiedValue[float].model_validate(data)


@pytest.mark.unit
def test_biomass_params_rejects_unexpected_field():
    data = {**copy.deepcopy(VALID_BIOMASS), "unexpected_key": "typo"}
    with pytest.raises(ValidationError):
        BiomassParams.model_validate(data)


@pytest.mark.unit
def test_technology_params_rejects_unexpected_field():
    data = {**copy.deepcopy(VALID_TECHNOLOGIES), "solar": "not a real domain yet"}
    with pytest.raises(ValidationError):
        TechnologyParams.model_validate(data)


@pytest.mark.unit
def test_country_params_rejects_unexpected_field():
    data = {**copy.deepcopy(VALID_COUNTRY), "unexpected_key": "typo"}
    with pytest.raises(ValidationError):
        CountryParams.model_validate(data)


@pytest.mark.unit
def test_parameters_file_rejects_unexpected_field():
    data = {**copy.deepcopy(VALID_PARAMETERS_FILE), "unexpected_key": "typo"}
    with pytest.raises(ValidationError):
        ParametersFile.model_validate(data)


# ─── Range-constraint tests: one case per new Field() constraint ────────


@pytest.mark.unit
def test_capacity_factor_out_of_range_raises():
    data = copy.deepcopy(VALID_BIOMASS)
    data["capacity_factor"]["value"] = -0.1
    with pytest.raises(ValidationError):
        BiomassParams.model_validate(data)


@pytest.mark.unit
def test_opex_fixed_pct_of_capex_out_of_range_raises():
    data = copy.deepcopy(VALID_BIOMASS)
    data["opex_fixed_pct_of_capex"]["value"] = 1.5
    with pytest.raises(ValidationError):
        BiomassParams.model_validate(data)


@pytest.mark.unit
def test_lifetime_years_out_of_range_raises():
    data = copy.deepcopy(VALID_BIOMASS)
    data["lifetime_years"]["value"] = 0
    with pytest.raises(ValidationError):
        BiomassParams.model_validate(data)


@pytest.mark.unit
def test_discount_rate_out_of_range_raises():
    data = copy.deepcopy(VALID_COUNTRY)
    data["discount_rate"]["value"] = -0.01
    with pytest.raises(ValidationError):
        CountryParams.model_validate(data)
