"""Unit tests for geofrea.core.config_loader.

No key-overlap test between parameters.json and settings.yaml: the two
files don't hold conflicting/duplicated data under the same key.
settings.yaml's run.countries is a subset *selector* referencing
parameters.json's countries key by code — not a redeclaration of any
per-country data — so there's no precedence rule to test, just a
(currently unenforced) cross-file reference. See docs/DECISIONS.md
2026-08-20 - settings.yaml phase toggles.

Legacy-value comparison scope (acceptance criterion 5): only
capex_usd_per_kw and lifetime_years for biomass have a direct legacy
equivalent to compare against — geoworld_framework's
lcoe_calculator.py::DEFAULT_LCOE_PARAMS["biomass"], as documented in
docs/DECISIONS.md 2026-08-19 (capex=2720, opex=109 flat, lifetime=20,
dr=0.07). Note: docs/architecture/module-mapping.md itself does not
carry these per-technology numeric legacy values (it only records that
DEFAULT_LCOE_PARAMS exists as a hardcoded fallback — see
lcoe_modeling.md sec c.1); the biomass numbers used below trace back to
the direct code investigation recorded in DECISIONS.md 2026-08-19, not
to module-mapping.md. Flagging this as a documentation gap rather than
treating module-mapping.md as the source.

opex has no like-for-like legacy comparison: the legacy value was a
single flat USD/kW/yr figure, while GeoFREA's IRENA-2025-sourced value
is structurally split into opex_fixed_pct_of_capex (dimensionless
fraction) and opex_variable_usd_per_kwh (USD/kWh) - different units,
not just different numbers, per docs/DECISIONS.md 2026-08-20.

capacity_factor and discount_rate_increment are NEW parameters with no
legacy equivalent at all (capacity_factor didn't exist as a per-country
canonical value at this level in the legacy pipeline or in the
2026-08-19 entry; discount_rate_increment is pending_research with no
value yet) - criterion 5 does not apply to either.
"""

from pathlib import Path

import pytest

from geofrea.core.config_loader import load_parameters, load_settings
from geofrea.core.schemas import ParametersFile, SettingsFile

REPO_ROOT = Path(__file__).resolve().parents[2]
PARAMETERS_JSON = REPO_ROOT / "config" / "parameters.json"
SETTINGS_YAML = REPO_ROOT / "config" / "settings.yaml"

# Legacy hardcoded biomass values, geoworld_framework's
# lcoe_calculator.py::DEFAULT_LCOE_PARAMS["biomass"], as recorded in
# docs/DECISIONS.md 2026-08-19 - biomass CAPEX/OPEX/lifetime fallback
# values.
_LEGACY_BIOMASS_CAPEX_USD_KW = 2720.0
_LEGACY_BIOMASS_LIFETIME_YEARS = 20


@pytest.mark.unit
def test_load_real_parameters_json_validates():
    """Criterion 2: the REAL config/parameters.json must validate as-is."""
    result = load_parameters(PARAMETERS_JSON)
    assert isinstance(result, ParametersFile)
    assert set(result.countries.keys()) == {"PRT", "BRA"}


@pytest.mark.unit
def test_load_real_settings_yaml_validates():
    """The REAL config/settings.yaml must validate against SettingsFile."""
    result = load_settings(SETTINGS_YAML)
    assert isinstance(result, SettingsFile)
    # Empty = run every country in parameters.json, per RunConfig's contract.
    assert result.run.countries == []
    # data_acquisition/data_quality_audit have real phase runners now
    # (see docs/DECISIONS.md 2026-08-25 - data_acquisition activation);
    # every flag is still off by default.
    assert set(result.run.phases.keys()) == {
        "data_acquisition",
        "data_quality_audit",
        "grid_alignment",
        "suitability_criteria",
        "land_eligibility",
        "climate_forcing",
        "technical_potential",
        "lcoe_modeling",
        "robustness_analysis",
        "external_validation",
        "results_synthesis",
        "explorer",
    }
    assert all(enabled is False for enabled in result.run.phases.values())


@pytest.mark.unit
@pytest.mark.parametrize("country", ["PRT", "BRA"])
@pytest.mark.parametrize(
    "field_name",
    ["capex_usd_per_kw", "opex_fixed_pct_of_capex", "opex_variable_usd_per_kwh", "lifetime_years"],
)
def test_biomass_verification_metadata_readable(country, field_name):
    """Criterion 4: verification metadata is present/readable on the parsed model."""
    result = load_parameters(PARAMETERS_JSON)
    field = getattr(result.countries[country].technologies.biomass, field_name)
    assert field.verified is True
    assert field.verified_by == "Douglas"
    assert field.verified_date == "2026-08-20"
    assert field.verification_method == "manual_cross_check"


@pytest.mark.unit
@pytest.mark.parametrize("country", ["PRT", "BRA"])
def test_biomass_capex_deliberately_diverges_from_legacy(country):
    """Criterion 5: CAPEX was a deliberate METHODOLOGY_REVISION, not a
    preserved legacy value (DECISIONS.md 2026-08-20, addendum to
    2026-08-19 - biomass parameters restructure). Pins the new value
    and asserts it differs from the legacy figure, so an accidental
    revert to the old number would fail this test instead of silently
    passing as a valid load.
    """
    result = load_parameters(PARAMETERS_JSON)
    capex = result.countries[country].technologies.biomass.capex_usd_per_kw.value
    assert capex == 3606.0
    assert capex != _LEGACY_BIOMASS_CAPEX_USD_KW


@pytest.mark.unit
@pytest.mark.parametrize("country", ["PRT", "BRA"])
def test_biomass_lifetime_preserved_from_legacy(country):
    """Criterion 5: lifetime_years is the one field DECISIONS.md
    2026-08-20 states was NOT changed from the legacy/2024 value —
    asserts it still matches, unlike capex.
    """
    result = load_parameters(PARAMETERS_JSON)
    lifetime = result.countries[country].technologies.biomass.lifetime_years.value
    assert lifetime == _LEGACY_BIOMASS_LIFETIME_YEARS
