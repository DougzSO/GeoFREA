"""Unit tests for geofrea.core.schemas.

Every schema's required fields are tested individually (one
parametrized case per field, not a single "missing fields in general"
test) by removing exactly that field from an otherwise-valid payload
and asserting pydantic raises ValidationError. The same per-case
pattern is used for the extra="forbid" and range-constraint tests
below. SolarParams/WindParams share required-field,
extra="forbid", and range-constraint tests via TECH_MODELS, since they
share the same shape (_TechnologyEconomicParams).
"""

import copy

import pytest
from pydantic import ValidationError

from geofrea.core.schemas import (
    CountryParams,
    ParameterRange,
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
    "unit": "dimensionless",
    "source": "IRENA 2025",
    "tier": None,
    "range": None,
    "verified": True,
    "verified_by": "Douglas",
    "verified_date": "2026-08-20",
    "verification_method": "manual_cross_check",
}

VALID_PENDING_VALUE = {
    "value": None,
    "unit": "dimensionless",
    "source": None,
    "tier": None,
    "range": None,
    "verified": False,
    "verified_by": None,
    "verified_date": None,
    "verification_method": "unverified",
    "status": "pending_research",
}

VALID_SOLAR = {
    "capex_usd_per_kw": {**VALID_VERIFIED_VALUE, "value": 823},
    "opex_fixed_frac": {**VALID_VERIFIED_VALUE, "value": 0.0092},
    "opex_var_usd_per_mwh": dict(VALID_PENDING_VALUE),
    "lifetime_years": {**VALID_VERIFIED_VALUE, "value": 25},
    "discount_rate": {**VALID_VERIFIED_VALUE, "value": 0.042},
    "discount_rate_increment": {**VALID_VERIFIED_VALUE, "value": 0.0},
    "luf": dict(VALID_PENDING_VALUE),
    "power_density_mw_per_km2": dict(VALID_PENDING_VALUE),
    "gamma": dict(VALID_PENDING_VALUE),
    "degradation_by_zone": None,
    "cf_min": dict(VALID_PENDING_VALUE),
    "tau_lcoe_usd_per_mwh": dict(VALID_PENDING_VALUE),
    "top_k_percent": dict(VALID_PENDING_VALUE),
}

VALID_WIND = {
    "capex_usd_per_kw": {**VALID_VERIFIED_VALUE, "value": 976},
    "opex_fixed_frac": {**VALID_VERIFIED_VALUE, "value": 0.0348},
    "opex_var_usd_per_mwh": dict(VALID_PENDING_VALUE),
    "lifetime_years": {**VALID_VERIFIED_VALUE, "value": 25},
    "discount_rate": {**VALID_VERIFIED_VALUE, "value": 0.037},
    "discount_rate_increment": {**VALID_VERIFIED_VALUE, "value": 0.0},
    "luf": dict(VALID_PENDING_VALUE),
    "power_density_mw_per_km2": dict(VALID_PENDING_VALUE),
    "eta_loss": dict(VALID_PENDING_VALUE),
    "hub_height_m": dict(VALID_PENDING_VALUE),
    "degradation_rate": dict(VALID_PENDING_VALUE),
    "wind_degradation_complex_terrain": dict(VALID_PENDING_VALUE),
    "cf_min": dict(VALID_PENDING_VALUE),
    "tau_lcoe_usd_per_mwh": dict(VALID_PENDING_VALUE),
    "top_k_percent": dict(VALID_PENDING_VALUE),
}

VALID_TECHNOLOGIES = {"solar": VALID_SOLAR, "wind": VALID_WIND}

VALID_YIELD_BY_LAND_COVER = {
    **VALID_VERIFIED_VALUE,
    "value": {"10": 8.0, "20": 3.0, "30": 5.0, "40": 6.0, "90": 0.0, "95": 0.0},
    "verified": False,
    "verified_by": None,
    "verified_date": None,
    "verification_method": "unverified",
}

VALID_LAND_SUITABILITY = {
    **VALID_VERIFIED_VALUE,
    "value": {
        "10": {"solar": 0.0, "wind": 0.0, "biomass": 0.0, "description": "Tree cover"},
        "30": {"solar": 0.8, "wind": 0.8, "biomass": 0.9},
    },
    "verified": False,
    "verified_by": None,
    "verified_date": None,
    "verification_method": "unverified",
}


def _cv(value):
    """A minimal valid VerifiedValue payload wrapping `value`."""
    return {**VALID_VERIFIED_VALUE, "value": value}


VALID_COUNTRY = {
    "technologies": VALID_TECHNOLOGIES,
}

VALID_PARAMETERS_FILE = {
    "countries": {"PRT": VALID_COUNTRY, "BRA": copy.deepcopy(VALID_COUNTRY)},
}

VALID_RUN_CONFIG = {
    "countries": [],
    "target_phases": ["data_quality_audit", "grid_alignment"],
    "technologies": ["solar", "wind"],
    "rerun_phases": [],
}

VALID_SETTINGS_FILE = {
    "run": VALID_RUN_CONFIG,
    "geospatial": {
        "resolutions": {"suitability": 0.01},
        "distance_cap_km": 100.0,
        "poi_line_tolerance_m": 50.0,
        "road_classes": {"grip4_gp_rtp": [1, 2, 3], "osm_highway": ["primary", "secondary"]},
        "poi_substations_geojson": "external/osm_substations/{iso}_substations_osm.geojson",
        "pvcz_csv": "external/pvcz/pvcz.csv",
        "pvcz_max_distance_km": 50.0,
    },
    "memory": {"max_batch_gb": 1.0},
    "figures": "all",
}

# tech_name -> (model class, valid payload) - shared across the tech-model tests below.
TECH_MODELS = {
    "solar": (SolarParams, VALID_SOLAR),
    "wind": (WindParams, VALID_WIND),
}

REQUIRED_TECH_FIELDS = [
    "capex_usd_per_kw",
    "opex_fixed_frac",
    "opex_var_usd_per_mwh",
    "lifetime_years",
    "discount_rate",
    "discount_rate_increment",
]


# ─── Valid-payload smoke tests ──────────────────────────────────────────


@pytest.mark.unit
def test_verified_value_accepts_valid_payload():
    result = VerifiedValue[float].model_validate(VALID_VERIFIED_VALUE)
    assert result.value == 1.0
    assert result.verified is True


@pytest.mark.unit
def test_solar_params_accepts_valid_payload():
    result = SolarParams.model_validate(VALID_SOLAR)
    assert result.capex_usd_per_kw.value == 823
    assert result.discount_rate.value == 0.042
    # solar's source doesn't split fixed/variable OPEX - variable stays unpopulated.
    assert result.opex_var_usd_per_mwh.value is None
    assert result.opex_var_usd_per_mwh.status == "pending_research"


@pytest.mark.unit
def test_wind_params_accepts_valid_payload():
    result = WindParams.model_validate(VALID_WIND)
    assert result.capex_usd_per_kw.value == 976
    assert result.discount_rate.value == 0.037
    assert result.opex_var_usd_per_mwh.value is None
    assert result.opex_var_usd_per_mwh.status == "pending_research"


@pytest.mark.unit
def test_technology_params_accepts_valid_payload():
    result = TechnologyParams.model_validate(VALID_TECHNOLOGIES)
    assert result.solar.lifetime_years.value == 25
    assert result.wind.lifetime_years.value == 25


@pytest.mark.unit
def test_country_params_accepts_valid_payload():
    result = CountryParams.model_validate(VALID_COUNTRY)
    assert result.technologies.solar.lifetime_years.value == 25


@pytest.mark.unit
def test_parameters_file_accepts_valid_payload():
    result = ParametersFile.model_validate(VALID_PARAMETERS_FILE)
    assert set(result.countries.keys()) == {"PRT", "BRA"}


@pytest.mark.unit
def test_run_config_accepts_valid_payload():
    result = RunConfig.model_validate(VALID_RUN_CONFIG)
    assert result.countries == []
    assert result.target_phases == ["data_quality_audit", "grid_alignment"]
    assert result.technologies == ["solar", "wind"]
    assert result.rerun_phases == []


@pytest.mark.unit
def test_run_config_rerun_phases_defaults_to_empty():
    data = copy.deepcopy(VALID_RUN_CONFIG)
    del data["rerun_phases"]
    result = RunConfig.model_validate(data)
    assert result.rerun_phases == []


@pytest.mark.unit
def test_run_config_empty_target_phases_raises():
    data = copy.deepcopy(VALID_RUN_CONFIG)
    data["target_phases"] = []
    with pytest.raises(ValidationError):
        RunConfig.model_validate(data)


@pytest.mark.unit
def test_settings_file_accepts_valid_payload():
    result = SettingsFile.model_validate(VALID_SETTINGS_FILE)
    assert result.run.countries == []


@pytest.mark.unit
def test_geospatial_values_have_no_schema_defaults_and_adaptive_mode_is_gone():
    """CONVENTIONS (no duplicated defaults) and G-3: resolution and distance threshold live only in settings.yaml."""
    from geofrea.core.schemas import GeospatialConfig, ResolutionsConfig

    with pytest.raises(ValidationError):
        ResolutionsConfig()
    with pytest.raises(ValidationError):
        GeospatialConfig(resolutions={"suitability": 0.01})  # distance_cap_km missing
    with pytest.raises(ValidationError):
        SettingsFile.model_validate({"run": VALID_RUN_CONFIG})  # geospatial missing
    with pytest.raises(ValidationError):
        ResolutionsConfig(suitability="adaptive")
    with pytest.raises(ValidationError):
        ResolutionsConfig(
            suitability=0.01, adaptive={"target_pixels": 1}
        )  # the adaptive block no longer exists


# ─── Required-field tests: one parametrized case per field ──────────────


@pytest.mark.unit
@pytest.mark.parametrize("field", ["value", "unit", "verified", "verification_method"])
def test_verified_value_missing_required_field_raises(field):
    data = dict(VALID_VERIFIED_VALUE)
    del data[field]
    with pytest.raises(ValidationError):
        VerifiedValue[float].model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("tech_name", ["solar", "wind"])
@pytest.mark.parametrize("field", REQUIRED_TECH_FIELDS)
def test_tech_economic_params_missing_required_field_raises(tech_name, field):
    model_cls, valid = TECH_MODELS[tech_name]
    data = copy.deepcopy(valid)
    del data[field]
    with pytest.raises(ValidationError):
        model_cls.model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("field", ["solar", "wind"])
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
@pytest.mark.parametrize("field", ["countries", "target_phases", "technologies"])
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
@pytest.mark.parametrize("tech_name", ["solar", "wind"])
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
@pytest.mark.parametrize("tech_name", ["solar", "wind"])
def test_opex_fixed_frac_out_of_range_raises(tech_name):
    model_cls, valid = TECH_MODELS[tech_name]
    data = copy.deepcopy(valid)
    data["opex_fixed_frac"]["value"] = 1.5
    with pytest.raises(ValidationError):
        model_cls.model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("tech_name", ["solar", "wind"])
def test_lifetime_years_out_of_range_raises(tech_name):
    model_cls, valid = TECH_MODELS[tech_name]
    data = copy.deepcopy(valid)
    data["lifetime_years"]["value"] = 0
    with pytest.raises(ValidationError):
        model_cls.model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("tech_name", ["solar", "wind"])
def test_discount_rate_out_of_range_raises(tech_name):
    model_cls, valid = TECH_MODELS[tech_name]
    data = copy.deepcopy(valid)
    data["discount_rate"]["value"] = -0.01
    with pytest.raises(ValidationError):
        model_cls.model_validate(data)


@pytest.mark.unit
def test_real_parameters_json_validates_and_has_no_criteria_block():
    """The real config/parameters.json validates; the legacy `criteria` blocks are gone (V16)."""
    from pathlib import Path

    from geofrea.core.config_loader import load_parameters

    repo_root = Path(__file__).resolve().parents[2]
    result = load_parameters(repo_root / "config" / "parameters.json")
    assert not hasattr(result, "criteria")
    # ZZZ (synthetic fixture, A-06/OQ-032) joined 2026-09-24 -- see
    # docs/phases/core.md D-core-018.
    assert set(result.countries) == {"PRT", "BRA", "IND", "ZZZ"}


# --- Pre-registration fields (DEC-081) ---------------------------------


def _solar_with(**values):
    """VALID_SOLAR with the entries of `values` replaced (a dict is the entry as it is written in parameters.json)."""
    return {**VALID_SOLAR, **values}


def _tau(**changes):
    return {**VALID_VERIFIED_VALUE, "unit": "USD/MWh", "value": 50.0, **changes}


@pytest.mark.unit
def test_currency_accepts_usd_only_and_a_value_without_it_dumps_without_the_key():
    assert VerifiedValue[float].model_validate({**VALID_VERIFIED_VALUE, "currency": "USD"}).currency == "USD"
    with pytest.raises(ValidationError):
        VerifiedValue[float].model_validate({**VALID_VERIFIED_VALUE, "currency": "EUR"})
    plain = VerifiedValue[float].model_validate(VALID_VERIFIED_VALUE)
    assert plain.currency is None
    assert "currency" not in plain.model_dump(mode="json")
    assert "currency" not in plain.model_dump()
    assert VerifiedValue[float].model_validate({**VALID_VERIFIED_VALUE, "currency": "USD"}).model_dump()["currency"] == "USD"


@pytest.mark.unit
def test_the_threshold_tau_needs_its_currency_when_it_has_a_price_year():
    with pytest.raises(ValidationError, match="currency is required"):
        SolarParams.model_validate(_solar_with(tau_lcoe_usd_per_mwh=_tau(price_year=2024)))
    solar = SolarParams.model_validate(_solar_with(tau_lcoe_usd_per_mwh=_tau(price_year=2024, currency="USD")))
    assert solar.tau_lcoe_usd_per_mwh.model_dump(mode="json")["currency"] == "USD"
    # no price year, no currency: the pending value of the real countries
    pending = SolarParams.model_validate(_solar_with(tau_lcoe_usd_per_mwh=_tau(value=None)))
    assert "currency" not in pending.tau_lcoe_usd_per_mwh.model_dump(mode="json")


@pytest.mark.unit
def test_wind_params_apply_the_same_two_rules():
    wind = {**VALID_WIND, "tau_lcoe_usd_per_mwh": _tau(price_year=2024)}
    with pytest.raises(ValidationError, match="currency is required"):
        WindParams.model_validate(wind)
    bad_bound = {**VALID_WIND, "capex_usd_per_kw": {**VALID_VERIFIED_VALUE, "value": 1100, "primary_bound": "max"}}
    with pytest.raises(ValidationError, match="primary_bound exists only on cf_min"):
        WindParams.model_validate(bad_bound)


@pytest.mark.unit
def test_a_value_other_than_tau_with_a_price_year_still_validates_without_a_currency():
    """About thirty real values carry a `price_year` and no `currency`; requiring it there would move fingerprints (DEC-081 item a)."""
    capex = {**VALID_VERIFIED_VALUE, "value": 823, "price_year": 2024}
    solar = SolarParams.model_validate(_solar_with(capex_usd_per_kw=capex))
    assert solar.capex_usd_per_kw.currency is None
    assert "currency" not in solar.capex_usd_per_kw.model_dump(mode="json")


@pytest.mark.unit
def test_primary_bound_is_accepted_on_cf_min_only_and_is_left_out_of_the_dump_while_null():
    floor = {**VALID_VERIFIED_VALUE, "value": 0.2}
    plain = SolarParams.model_validate(_solar_with(cf_min=floor))
    assert plain.cf_min.primary_bound is None
    assert "primary_bound" not in plain.cf_min.model_dump(mode="json")
    strict = SolarParams.model_validate(_solar_with(cf_min={**floor, "primary_bound": "max"}))
    assert strict.cf_min.model_dump(mode="json")["primary_bound"] == "max"
    with pytest.raises(ValidationError):
        SolarParams.model_validate(_solar_with(cf_min={**floor, "primary_bound": "strict"}))
    for other in ("capex_usd_per_kw", "discount_rate", "top_k_percent"):
        entry = {**VALID_VERIFIED_VALUE, "value": 1.0, "primary_bound": "max"}
        with pytest.raises(ValidationError, match="primary_bound exists only on cf_min"):
            SolarParams.model_validate(_solar_with(**{other: entry}))


@pytest.mark.unit
def test_a_reporting_range_is_accepted_by_the_schema_and_keeps_its_bounds():
    reporting = ParameterRange.model_validate(
        {"min": 36.0, "max": 77.0, "distribution": "reporting", "source": "IRENA p5 to p95", "tier": 2}
    )
    assert reporting.distribution == "reporting"
    value = VerifiedValue[float].model_validate({**VALID_VERIFIED_VALUE, "value": 48.0, "range": reporting.model_dump()})
    assert value.range is not None and (value.range.min, value.range.max) == (36.0, 77.0)
    with pytest.raises(ValidationError, match="must be within range"):
        VerifiedValue[float].model_validate({**VALID_VERIFIED_VALUE, "value": 80.0, "range": reporting.model_dump()})
    with pytest.raises(ValidationError):
        ParameterRange.model_validate({"min": 1.0, "max": 2.0, "distribution": "gaussian", "source": "x"})
