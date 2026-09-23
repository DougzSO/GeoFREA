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
    CountryCriteriaParams,
    CountryParams,
    CriteriaParams,
    LandCoverSuitability,
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

VALID_BIOMASS = {
    "capex_usd_per_kw": {**VALID_VERIFIED_VALUE, "value": 3606},
    "opex_fixed_pct_of_capex": {**VALID_VERIFIED_VALUE, "value": 0.04},
    "opex_variable_usd_per_kwh": {**VALID_VERIFIED_VALUE, "value": 0.004},
    "lifetime_years": {**VALID_VERIFIED_VALUE, "value": 20},
    "discount_rate": {**VALID_VERIFIED_VALUE, "value": 0.05},
    "discount_rate_increment": {**VALID_VERIFIED_VALUE, "value": 0.0},
    "slope_threshold_deg": {**VALID_VERIFIED_VALUE, "value": 8.5},
}

VALID_SOLAR = {
    "capex_usd_per_kw": {**VALID_VERIFIED_VALUE, "value": 823},
    "opex_fixed_pct_of_capex": {**VALID_VERIFIED_VALUE, "value": 0.0092},
    "opex_variable_usd_per_kwh": dict(VALID_PENDING_VALUE),
    "lifetime_years": {**VALID_VERIFIED_VALUE, "value": 25},
    "discount_rate": {**VALID_VERIFIED_VALUE, "value": 0.042},
    "discount_rate_increment": {**VALID_VERIFIED_VALUE, "value": 0.0},
    "slope_threshold_deg": {**VALID_VERIFIED_VALUE, "value": 5.0},
}

VALID_WIND = {
    "capex_usd_per_kw": {**VALID_VERIFIED_VALUE, "value": 976},
    "opex_fixed_pct_of_capex": {**VALID_VERIFIED_VALUE, "value": 0.0348},
    "opex_variable_usd_per_kwh": dict(VALID_PENDING_VALUE),
    "lifetime_years": {**VALID_VERIFIED_VALUE, "value": 25},
    "discount_rate": {**VALID_VERIFIED_VALUE, "value": 0.037},
    "discount_rate_increment": {**VALID_VERIFIED_VALUE, "value": 0.0},
    "slope_threshold_deg": {**VALID_VERIFIED_VALUE, "value": 8.5},
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


VALID_CRITERIA = {
    "slope_threshold_deg_solar": _cv(5.0),
    "slope_threshold_deg_wind": _cv(25.0),
    "slope_threshold_deg_biomass": _cv(15.0),
    "river_safety_buffer_km": _cv(0.5),
    "pop_density_threshold": _cv(200.0),
    "road_max_dist_km": _cv(15.0),
    "river_max_dist_biomass_km": _cv(30.0),
    "grid_max_dist_km": _cv(20.0),
    "normalization_min_percentile": _cv(5.0),
    "normalization_max_percentile": _cv(95.0),
    "linear_proximity_percentile_low": _cv(5.0),
    "linear_proximity_percentile_high": _cv(95.0),
    "terrain_slope_weight": _cv(0.6),
    "terrain_tri_weight": _cv(0.4),
    "tri_threshold_m": _cv(50.0),
    "proximity_decay_sigma_km": _cv(10.0),
    "proximity_smooth_sigma_px": _cv(2.0),
    "proximity_plants_neutral_score": _cv(0.3),
    "biomass_smooth_sigma": _cv(1.0),
    "solar_pvout_weight": _cv(1.0),
    "renewable_fuel_labels": _cv(["solar", "wind", "biomass", "waste"]),
    "protected_as_exclusion": _cv(True),
    "iucn_strict_categories": _cv(["ia", "ib", "ii"]),
    "land_suitability": dict(VALID_LAND_SUITABILITY),
}

VALID_COUNTRY_CRITERIA = {
    "yield_by_land_cover": dict(VALID_YIELD_BY_LAND_COVER),
    "terrain_slope_threshold_deg": _cv(10.0),
}

VALID_COUNTRY = {
    "technologies": VALID_TECHNOLOGIES,
    "criteria": copy.deepcopy(VALID_COUNTRY_CRITERIA),
}

VALID_PARAMETERS_FILE = {
    "countries": {"PRT": VALID_COUNTRY, "BRA": copy.deepcopy(VALID_COUNTRY)},
    "criteria": copy.deepcopy(VALID_CRITERIA),
}

VALID_RUN_CONFIG = {
    "countries": [],
    "target_phases": ["data_quality_audit", "grid_alignment"],
    "technologies": ["solar", "wind"],
    "rerun_phases": [],
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


# ─── Required-field tests: one parametrized case per field ──────────────


@pytest.mark.unit
@pytest.mark.parametrize("field", ["value", "unit", "verified", "verification_method"])
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
@pytest.mark.parametrize("field", ["solar", "wind"])
def test_technology_params_missing_required_field_raises(field):
    data = copy.deepcopy(VALID_TECHNOLOGIES)
    del data[field]
    with pytest.raises(ValidationError):
        TechnologyParams.model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("field", ["technologies", "criteria"])
def test_country_params_missing_required_field_raises(field):
    data = copy.deepcopy(VALID_COUNTRY)
    del data[field]
    with pytest.raises(ValidationError):
        CountryParams.model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("field", ["countries", "criteria"])
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


# ─── CriteriaParams / LandCoverSuitability (Fase 2b, added 2026-09-10) ───


@pytest.mark.unit
def test_land_cover_suitability_accepts_valid_payload():
    result = LandCoverSuitability.model_validate(
        {"solar": 0.8, "wind": 0.8, "biomass": 0.9, "description": "Grassland"}
    )
    assert result.biomass == 0.9
    assert result.description == "Grassland"


@pytest.mark.unit
def test_land_cover_suitability_description_is_optional():
    result = LandCoverSuitability.model_validate({"solar": 0.0, "wind": 0.0, "biomass": 0.0})
    assert result.description is None


@pytest.mark.unit
@pytest.mark.parametrize("field", ["solar", "wind", "biomass"])
def test_land_cover_suitability_missing_required_field_raises(field):
    data = {"solar": 0.5, "wind": 0.5, "biomass": 0.5}
    del data[field]
    with pytest.raises(ValidationError):
        LandCoverSuitability.model_validate(data)


@pytest.mark.unit
def test_land_cover_suitability_score_out_of_range_raises():
    with pytest.raises(ValidationError):
        LandCoverSuitability.model_validate({"solar": 1.5, "wind": 0.0, "biomass": 0.0})


@pytest.mark.unit
def test_criteria_params_accepts_valid_payload():
    result = CriteriaParams.model_validate(copy.deepcopy(VALID_CRITERIA))
    assert result.road_max_dist_km.value == 15.0
    assert result.slope_threshold_deg_wind.value == 25.0
    assert result.iucn_strict_categories.value == ["ia", "ib", "ii"]
    assert result.land_suitability.value[30].biomass == 0.9
    assert result.protected_as_exclusion.value is True


@pytest.mark.unit
@pytest.mark.parametrize("field", sorted(VALID_CRITERIA))
def test_criteria_params_missing_required_field_raises(field):
    data = copy.deepcopy(VALID_CRITERIA)
    del data[field]
    with pytest.raises(ValidationError):
        CriteriaParams.model_validate(data)


@pytest.mark.unit
def test_criteria_params_rejects_unexpected_field():
    data = {**copy.deepcopy(VALID_CRITERIA), "unexpected_key": _cv(1.0)}
    with pytest.raises(ValidationError):
        CriteriaParams.model_validate(data)


@pytest.mark.unit
def test_criteria_params_slope_threshold_out_of_range_raises():
    data = copy.deepcopy(VALID_CRITERIA)
    data["slope_threshold_deg_wind"]["value"] = 95.0
    with pytest.raises(ValidationError):
        CriteriaParams.model_validate(data)


@pytest.mark.unit
def test_criteria_params_percentile_out_of_range_raises():
    data = copy.deepcopy(VALID_CRITERIA)
    data["normalization_max_percentile"]["value"] = 120.0
    with pytest.raises(ValidationError):
        CriteriaParams.model_validate(data)


@pytest.mark.unit
def test_criteria_params_rejects_inverted_percentile_bounds():
    data = copy.deepcopy(VALID_CRITERIA)
    data["normalization_min_percentile"]["value"] = 95.0
    data["normalization_max_percentile"]["value"] = 5.0
    with pytest.raises(ValidationError):
        CriteriaParams.model_validate(data)


@pytest.mark.unit
def test_criteria_params_rejects_terrain_weights_not_summing_to_one():
    data = copy.deepcopy(VALID_CRITERIA)
    data["terrain_slope_weight"]["value"] = 0.6
    data["terrain_tri_weight"]["value"] = 0.5
    with pytest.raises(ValidationError):
        CriteriaParams.model_validate(data)


@pytest.mark.unit
def test_country_criteria_params_accepts_valid_payload():
    result = CountryCriteriaParams.model_validate(copy.deepcopy(VALID_COUNTRY_CRITERIA))
    assert result.yield_by_land_cover.value[10] == 8.0  # string keys coerced to int
    assert result.terrain_slope_threshold_deg.value == 10.0


@pytest.mark.unit
@pytest.mark.parametrize("field", ["yield_by_land_cover", "terrain_slope_threshold_deg"])
def test_country_criteria_params_missing_required_field_raises(field):
    data = copy.deepcopy(VALID_COUNTRY_CRITERIA)
    del data[field]
    with pytest.raises(ValidationError):
        CountryCriteriaParams.model_validate(data)


@pytest.mark.unit
def test_country_criteria_params_terrain_threshold_out_of_range_raises():
    data = copy.deepcopy(VALID_COUNTRY_CRITERIA)
    data["terrain_slope_threshold_deg"]["value"] = 95.0
    with pytest.raises(ValidationError):
        CountryCriteriaParams.model_validate(data)


@pytest.mark.unit
def test_country_criteria_params_rejects_unexpected_field():
    data = {**copy.deepcopy(VALID_COUNTRY_CRITERIA), "unexpected_key": _cv(1.0)}
    with pytest.raises(ValidationError):
        CountryCriteriaParams.model_validate(data)


@pytest.mark.unit
def test_real_parameters_json_criteria_block_validates():
    """The real config/parameters.json must carry valid criteria blocks."""
    from pathlib import Path

    from geofrea.core.config_loader import load_parameters

    repo_root = Path(__file__).resolve().parents[2]
    result = load_parameters(repo_root / "config" / "parameters.json")
    assert result.criteria.road_max_dist_km.value == 15.0
    assert result.criteria.road_max_dist_km.verified is True
    assert result.criteria.terrain_slope_weight.value + result.criteria.terrain_tri_weight.value == 1.0
    assert set(result.countries) == {"PRT", "BRA"}
    assert result.countries["PRT"].criteria.yield_by_land_cover.value[20] == 3.0
    assert result.countries["BRA"].criteria.yield_by_land_cover.value[20] == 4.0
    assert result.countries["PRT"].criteria.terrain_slope_threshold_deg.value == 10.0
    assert result.countries["BRA"].criteria.terrain_slope_threshold_deg.value == 12.0
