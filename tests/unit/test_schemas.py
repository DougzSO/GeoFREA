"""Unit tests for geofrea.core.schemas.

Every schema's required fields are tested individually (one
parametrized case per field, not a single "missing fields in general"
test) by removing exactly that field from an otherwise-valid payload
and asserting pydantic raises ValidationError. The same per-case
pattern is used for the extra="forbid" and range-constraint tests
below. BiomassParams/SolarParams/WindParams share required-field,
extra="forbid", and range-constraint tests via TECH_MODELS, since they
share the same shape (_TechnologyEconomicParams).
"""

import copy

import pytest
from pydantic import ValidationError

from geofrea.core.schemas import (
    BiomassParams,
    CountryParams,
    ParametersFile,
    RunConfig,
    SettingsFile,
    SolarParams,
    TechnologyParams,
    VerifiedValue,
    WindParams,
)

VALID_VERIFIED_VALUE = {
    "value": 1.0,
    "source": "IRENA 2025",
    "verified": True,
    "verified_by": "Douglas",
    "verified_date": "2026-08-20",
    "verification_method": "manual_cross_check",
}

VALID_PENDING_VALUE = {
    "value": None,
    "source": None,
    "verified": False,
    "verified_by": None,
    "verified_date": None,
    "verification_method": "unverified",
    "status": "pending_research",
}

VALID_BIOMASS = {
    "capex_usd_per_kw": {**VALID_VERIFIED_VALUE, "value": 3606},
    "opex_fixed_pct_of_capex": {**VALID_VERIFIED_VALUE, "value": 0.04},
    "opex_variable_usd_per_kwh": {**VALID_VERIFIED_VALUE, "value": 0.004},
    "capacity_factor": {**VALID_VERIFIED_VALUE, "value": 0.81},
    "lifetime_years": {**VALID_VERIFIED_VALUE, "value": 20},
    "discount_rate": {**VALID_VERIFIED_VALUE, "value": 0.05},
    "discount_rate_increment": {**VALID_VERIFIED_VALUE, "value": 0.0},
    "slope_threshold_deg": {**VALID_VERIFIED_VALUE, "value": 8.5},
}

VALID_SOLAR = {
    "capex_usd_per_kw": {**VALID_VERIFIED_VALUE, "value": 823},
    "opex_fixed_pct_of_capex": {**VALID_VERIFIED_VALUE, "value": 0.0092},
    "opex_variable_usd_per_kwh": dict(VALID_PENDING_VALUE),
    "capacity_factor": {**VALID_VERIFIED_VALUE, "value": 0.12},
    "lifetime_years": {**VALID_VERIFIED_VALUE, "value": 25},
    "discount_rate": {**VALID_VERIFIED_VALUE, "value": 0.042},
    "discount_rate_increment": {**VALID_VERIFIED_VALUE, "value": 0.0},
    "slope_threshold_deg": {**VALID_VERIFIED_VALUE, "value": 5.0},
}

VALID_WIND = {
    "capex_usd_per_kw": {**VALID_VERIFIED_VALUE, "value": 976},
    "opex_fixed_pct_of_capex": {**VALID_VERIFIED_VALUE, "value": 0.0348},
    "opex_variable_usd_per_kwh": dict(VALID_PENDING_VALUE),
    "capacity_factor": {**VALID_VERIFIED_VALUE, "value": 0.34},
    "lifetime_years": {**VALID_VERIFIED_VALUE, "value": 25},
    "discount_rate": {**VALID_VERIFIED_VALUE, "value": 0.037},
    "discount_rate_increment": {**VALID_VERIFIED_VALUE, "value": 0.0},
    "slope_threshold_deg": {**VALID_VERIFIED_VALUE, "value": 8.5},
}

VALID_TECHNOLOGIES = {"biomass": VALID_BIOMASS, "solar": VALID_SOLAR, "wind": VALID_WIND}

VALID_COUNTRY = {"technologies": VALID_TECHNOLOGIES}

VALID_PARAMETERS_FILE = {"countries": {"PRT": VALID_COUNTRY, "BRA": copy.deepcopy(VALID_COUNTRY)}}

VALID_RUN_CONFIG = {
    "countries": [],
    "phases": {"data_quality_audit": False, "grid_alignment": False},
}

VALID_SETTINGS_FILE = {"run": VALID_RUN_CONFIG}

# tech_name -> (model class, valid payload) - shared across the tech-model tests below.
TECH_MODELS = {
    "biomass": (BiomassParams, VALID_BIOMASS),
    "solar": (SolarParams, VALID_SOLAR),
    "wind": (WindParams, VALID_WIND),
}

REQUIRED_TECH_FIELDS = [
    "capex_usd_per_kw",
    "opex_fixed_pct_of_capex",
    "opex_variable_usd_per_kwh",
    "capacity_factor",
    "lifetime_years",
    "discount_rate",
    "discount_rate_increment",
    "slope_threshold_deg",
]


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
    assert result.discount_rate.value == 0.05
    assert result.opex_variable_usd_per_kwh.value == 0.004
    assert result.slope_threshold_deg.value == 8.5


@pytest.mark.unit
def test_solar_params_accepts_valid_payload():
    result = SolarParams.model_validate(VALID_SOLAR)
    assert result.capex_usd_per_kw.value == 823
    assert result.discount_rate.value == 0.042
    # solar's source doesn't split fixed/variable OPEX - variable stays unpopulated.
    assert result.opex_variable_usd_per_kwh.value is None
    assert result.opex_variable_usd_per_kwh.status == "pending_research"
    assert result.slope_threshold_deg.value == 5.0


@pytest.mark.unit
def test_wind_params_accepts_valid_payload():
    result = WindParams.model_validate(VALID_WIND)
    assert result.capex_usd_per_kw.value == 976
    assert result.discount_rate.value == 0.037
    assert result.opex_variable_usd_per_kwh.value is None
    assert result.opex_variable_usd_per_kwh.status == "pending_research"
    # Same value as biomass: no wind-specific slope-threshold source found.
    assert result.slope_threshold_deg.value == 8.5


@pytest.mark.unit
def test_technology_params_accepts_valid_payload():
    result = TechnologyParams.model_validate(VALID_TECHNOLOGIES)
    assert result.biomass.capacity_factor.value == 0.81
    assert result.solar.capacity_factor.value == 0.12
    assert result.wind.capacity_factor.value == 0.34


@pytest.mark.unit
def test_country_params_accepts_valid_payload():
    result = CountryParams.model_validate(VALID_COUNTRY)
    assert result.technologies.biomass.lifetime_years.value == 20


@pytest.mark.unit
def test_parameters_file_accepts_valid_payload():
    result = ParametersFile.model_validate(VALID_PARAMETERS_FILE)
    assert set(result.countries.keys()) == {"PRT", "BRA"}


@pytest.mark.unit
def test_run_config_accepts_valid_payload():
    result = RunConfig.model_validate(VALID_RUN_CONFIG)
    assert result.countries == []
    assert result.phases["grid_alignment"] is False


@pytest.mark.unit
def test_settings_file_accepts_valid_payload():
    result = SettingsFile.model_validate(VALID_SETTINGS_FILE)
    assert result.run.countries == []


# ─── Required-field tests: one parametrized case per field ──────────────


@pytest.mark.unit
@pytest.mark.parametrize("field", ["value", "verified", "verification_method"])
def test_verified_value_missing_required_field_raises(field):
    data = dict(VALID_VERIFIED_VALUE)
    del data[field]
    with pytest.raises(ValidationError):
        VerifiedValue[float].model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("tech_name", ["biomass", "solar", "wind"])
@pytest.mark.parametrize("field", REQUIRED_TECH_FIELDS)
def test_tech_economic_params_missing_required_field_raises(tech_name, field):
    model_cls, valid = TECH_MODELS[tech_name]
    data = copy.deepcopy(valid)
    del data[field]
    with pytest.raises(ValidationError):
        model_cls.model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("field", ["biomass", "solar", "wind"])
def test_technology_params_missing_required_field_raises(field):
    data = copy.deepcopy(VALID_TECHNOLOGIES)
    del data[field]
    with pytest.raises(ValidationError):
        TechnologyParams.model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("field", ["technologies"])
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


@pytest.mark.unit
@pytest.mark.parametrize("field", ["countries", "phases"])
def test_run_config_missing_required_field_raises(field):
    data = copy.deepcopy(VALID_RUN_CONFIG)
    del data[field]
    with pytest.raises(ValidationError):
        RunConfig.model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("field", ["run"])
def test_settings_file_missing_required_field_raises(field):
    data = copy.deepcopy(VALID_SETTINGS_FILE)
    del data[field]
    with pytest.raises(ValidationError):
        SettingsFile.model_validate(data)


# ─── extra="forbid" tests: one case per model ────────────────────────────


@pytest.mark.unit
def test_verified_value_rejects_unexpected_field():
    data = {**VALID_VERIFIED_VALUE, "unexpected_key": "typo"}
    with pytest.raises(ValidationError):
        VerifiedValue[float].model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("tech_name", ["biomass", "solar", "wind"])
def test_tech_economic_params_rejects_unexpected_field(tech_name):
    model_cls, valid = TECH_MODELS[tech_name]
    data = {**copy.deepcopy(valid), "unexpected_key": "typo"}
    with pytest.raises(ValidationError):
        model_cls.model_validate(data)


@pytest.mark.unit
def test_technology_params_rejects_unexpected_field():
    # "solar"/"wind" are now legitimate required fields (not unexpected
    # keys), so the injected bogus key must be something else.
    data = {**copy.deepcopy(VALID_TECHNOLOGIES), "unexpected_key": "typo"}
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


@pytest.mark.unit
def test_run_config_rejects_unexpected_field():
    data = {**copy.deepcopy(VALID_RUN_CONFIG), "unexpected_key": "typo"}
    with pytest.raises(ValidationError):
        RunConfig.model_validate(data)


@pytest.mark.unit
def test_settings_file_rejects_unexpected_field():
    data = {**copy.deepcopy(VALID_SETTINGS_FILE), "unexpected_key": "typo"}
    with pytest.raises(ValidationError):
        SettingsFile.model_validate(data)


# ─── Range-constraint tests: one parametrized case per constraint, per tech ──


@pytest.mark.unit
@pytest.mark.parametrize("tech_name", ["biomass", "solar", "wind"])
def test_capacity_factor_out_of_range_raises(tech_name):
    model_cls, valid = TECH_MODELS[tech_name]
    data = copy.deepcopy(valid)
    data["capacity_factor"]["value"] = -0.1
    with pytest.raises(ValidationError):
        model_cls.model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("tech_name", ["biomass", "solar", "wind"])
def test_opex_fixed_pct_of_capex_out_of_range_raises(tech_name):
    model_cls, valid = TECH_MODELS[tech_name]
    data = copy.deepcopy(valid)
    data["opex_fixed_pct_of_capex"]["value"] = 1.5
    with pytest.raises(ValidationError):
        model_cls.model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("tech_name", ["biomass", "solar", "wind"])
def test_lifetime_years_out_of_range_raises(tech_name):
    model_cls, valid = TECH_MODELS[tech_name]
    data = copy.deepcopy(valid)
    data["lifetime_years"]["value"] = 0
    with pytest.raises(ValidationError):
        model_cls.model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("tech_name", ["biomass", "solar", "wind"])
def test_discount_rate_out_of_range_raises(tech_name):
    model_cls, valid = TECH_MODELS[tech_name]
    data = copy.deepcopy(valid)
    data["discount_rate"]["value"] = -0.01
    with pytest.raises(ValidationError):
        model_cls.model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("tech_name", ["biomass", "solar", "wind"])
def test_slope_threshold_deg_out_of_range_raises(tech_name):
    model_cls, valid = TECH_MODELS[tech_name]
    data = copy.deepcopy(valid)
    data["slope_threshold_deg"]["value"] = -1.0
    with pytest.raises(ValidationError):
        model_cls.model_validate(data)
