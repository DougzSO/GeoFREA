"""Group 3 inputs of F6 (COMMAND 83): conversion to 2024 USD, the refusal of a run with unsourced costs, the degradation bounds of a cell."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from geofrea.core.config_loader import load_parameters, load_technologies
from geofrea.core.schemas import UnitCost
from geofrea.lcoe_modeling.connection import (
    ConversionError,
    DegradationModel,
    group3_problems,
    load_conversion_indices,
    resolve_group3,
    to_usd_2024,
    transmission_efficiency_report,
)
from geofrea.lcoe_modeling.inputs import LcoeMissingInputError, resolve_technology_costs

REPO = Path(__file__).resolve().parents[2]
PARAMETERS = REPO / "config" / "parameters.json"
TECHNOLOGIES = REPO / "config" / "technologies.yaml"


def _indices_file(tmp_path, deflator=None, fx=None):
    """Synthetic World Bank series for the country XXX: the deflator doubles from 2020 to 2024 and one US dollar buys 4 units in 2024."""
    data = {
        "source": "synthetic",
        "accessed": "2026-01-01",
        "indicators": {
            "NY.GDP.DEFL.ZS": {"values": {"XXX": deflator or {"2020": 50.0, "2024": 100.0}}},
            "PA.NUS.FCRF": {"values": {"XXX": fx or {"2024": 4.0}}},
        },
    }
    path = tmp_path / "indices.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _cost(**kw):
    base = {
        "value": 2.0,
        "low": 1.0,
        "high": 3.0,
        "unit": "MXXX/km",
        "currency": "XXX",
        "scale": 1.0e6,
        "per": "km",
        "price_year": 2020,
        "status": "sourced",
    }
    base.update(kw)
    return UnitCost.model_validate(base)


@pytest.mark.unit
def test_conversion_to_2024_usd_follows_the_deflator_and_the_exchange_rate(tmp_path):
    indices = load_conversion_indices(_indices_file(tmp_path), "XXX")
    # 2 million XXX of 2020 = 4 million of 2024 (deflator 50 -> 100) = 1 million USD (4 XXX per USD)
    assert to_usd_2024(2.0, _cost(), indices) == pytest.approx(1.0e6)
    assert indices.factor(2024) == pytest.approx(0.25)


@pytest.mark.unit
def test_a_usd_cost_of_2024_needs_no_index_and_a_missing_index_is_named(tmp_path):
    usd = _cost(currency="USD", scale=1.0, price_year=2024)
    assert to_usd_2024(5.0, usd, None) == 5.0
    with pytest.raises(ConversionError, match="no conversion indices"):
        to_usd_2024(5.0, _cost(), None)
    no_year = load_conversion_indices(_indices_file(tmp_path, deflator={"2024": 100.0}), "XXX")
    with pytest.raises(ConversionError, match="NY.GDP.DEFL.ZS 2020"):
        to_usd_2024(5.0, _cost(), no_year)
    no_fx = load_conversion_indices(_indices_file(tmp_path, fx={"2023": 4.0}), "XXX")
    with pytest.raises(ConversionError, match="PA.NUS.FCRF 2024"):
        to_usd_2024(5.0, _cost(), no_fx)


@pytest.mark.unit
def test_a_missing_index_file_or_country_is_an_error_not_a_default(tmp_path):
    with pytest.raises(ConversionError, match="not found"):
        load_conversion_indices(tmp_path / "absent.json", "XXX")
    with pytest.raises(ConversionError, match="YYY"):
        load_conversion_indices(_indices_file(tmp_path), "YYY")


@pytest.mark.unit
def test_a_null_price_year_is_refused_with_the_source_to_confirm():
    with pytest.raises(ConversionError, match="price_year is null"):
        to_usd_2024(1.0, _cost(price_year=None, status="verify", source="acer2023uic"), None)


@pytest.mark.unit
def test_a_cost_to_be_sourced_has_no_number_and_a_sourced_one_has_its_range():
    UnitCost.model_validate(
        {"unit": "BRL/km", "currency": "BRL", "per": "km", "status": "to_be_sourced"}
    )
    with pytest.raises(ValueError, match="to_be_sourced"):
        _cost(status="to_be_sourced")  # a value with the status that says there is none
    with pytest.raises(ValueError, match="needs value, low and high"):
        _cost(low=None)
    with pytest.raises(ValueError, match="within"):
        _cost(value=5.0)


@pytest.fixture(scope="module")
def parameters():
    return load_parameters(PARAMETERS)


@pytest.fixture(scope="module")
def registry():
    return load_technologies(TECHNOLOGIES)


@pytest.mark.unit
def test_f6_is_refused_while_a_group_3_cost_is_null_and_the_message_cites_oq_001(parameters, registry):
    bra = parameters.countries["BRA"]
    with pytest.raises(LcoeMissingInputError) as caught:
        resolve_technology_costs(
            "BRA", "wind", registry.technologies["wind"], bra.technologies.wind, bra.connection
        )
    text = str(caught.value)
    for name in ("line_cost_per_km", "bay_cost", "road_cost_per_km"):
        assert f"{name} (no value, status to_be_sourced; OQ-001)" in text
    assert "capex_usd_per_kw" not in text  # what is recorded is not listed


@pytest.mark.unit
def test_a_country_without_the_connection_block_is_refused(parameters, registry):
    ind = parameters.countries["IND"]
    with pytest.raises(LcoeMissingInputError, match="no `connection` block"):
        resolve_technology_costs("IND", "wind", registry.technologies["wind"], ind.technologies.wind, None)


@pytest.mark.unit
def test_the_acer_costs_are_accepted_by_the_schema_but_refused_by_f6_until_the_year_is_confirmed(parameters):
    prt = parameters.countries["PRT"]
    problems = group3_problems("PRT", "wind", prt.connection, prt.technologies.wind)
    assert any(p.startswith("line_cost_per_km price_year (null, status verify") for p in problems)
    assert any(p.startswith("bay_cost price_year") for p in problems)
    assert any(p.startswith("road_cost_per_km (no value") for p in problems)


@pytest.mark.unit
def test_the_synthetic_country_resolves_and_its_group_3_values_reach_the_kernel_keys(parameters, registry):
    zzz = parameters.countries["ZZZ"]
    for tech in ("solar", "wind"):
        resolved = resolve_technology_costs(
            "ZZZ", tech, registry.technologies[tech], getattr(zzz.technologies, tech), zzz.connection
        )
        g3 = resolved.group3
        assert resolved.nominal["line_cost_usd_per_km"] == 100000.0  # USD 2024: no conversion
        assert resolved.nominal["reference_project_mw"] == 100.0
        assert resolved.nominal["transmission_loss_per_km"] == 0.0
        assert g3.long_distance_flag_km == 100.0
        names = [s.name for s in resolved.specs]
        assert {"degradation_weight", "line_cost_usd_per_km", "bay_cost_usd", "tortuosity_grid"} <= set(names)
        # the degradation weight is a position between the bounds, uniform on [0, 1]
        spec = next(s for s in resolved.specs if s.name == "degradation_weight")
        assert (spec.low, spec.high, spec.distribution) == (0.0, 1.0, "uniform")


@pytest.mark.unit
def test_wind_nominal_weight_places_the_value_inside_its_range_and_pv_nominal_is_the_median(parameters):
    zzz = parameters.countries["ZZZ"]
    wind = resolve_group3("ZZZ", "wind", zzz.connection, zzz.technologies.wind, None)
    entry = zzz.technologies.wind.degradation_rate
    low, high = wind.degradation.single
    assert (low, high) == (entry.range.min, entry.range.max)
    assert low + wind.nominal["degradation_weight"] * (high - low) == pytest.approx(entry.value)
    solar = resolve_group3("ZZZ", "solar", zzz.connection, zzz.technologies.solar, None)
    assert solar.nominal["degradation_weight"] == 0.0  # the central PV rate is the median of the zone
    zones = zzz.technologies.solar.degradation_by_zone.zones
    assert solar.degradation.by_zone[3][0] == zones["T3"].median
    assert solar.degradation.by_zone[3][1] == zones["T3"].mean


@pytest.mark.unit
def test_degradation_bounds_per_cell_cap_hot_zones_at_t7_and_flag_cells_without_a_zone():
    by_zone = {z: (0.004 + 0.001 * z, 0.005 + 0.001 * z) for z in range(1, 8)}
    model = DegradationModel(single=None, by_zone=by_zone)
    zone = np.array([1, 7, 8, 9, 10, 0], dtype="int8")
    low, high, known = model.bounds_for_cells(zone, len(zone))
    assert known.tolist() == [True, True, True, True, True, False]
    np.testing.assert_allclose(low[:5], [0.005, 0.011, 0.011, 0.011, 0.011])  # T8 to T10 take T7
    np.testing.assert_allclose(high[:5], [0.006, 0.012, 0.012, 0.012, 0.012])
    with pytest.raises(ConversionError, match="pvcz_zone"):
        model.bounds_for_cells(None, 3)
    single = DegradationModel(single=(0.0017, 0.0053), by_zone=None)
    low, high, known = single.bounds_for_cells(None, 4)
    assert known.all() and (low == 0.0017).all() and (high == 0.0053).all()


@pytest.mark.unit
def test_hot_zone_sensitivity_replaces_the_bounds_of_t7_and_above_only(parameters):
    by_zone = {z: (0.004 + 0.001 * z, 0.005 + 0.001 * z) for z in range(1, 8)}
    hot = DegradationModel(single=None, by_zone=by_zone).with_hot_zone_rate(0.0094, 7)
    assert hot.by_zone[7] == (0.0094, 0.0094)
    assert all(hot.by_zone[z] == by_zone[z] for z in range(1, 7))
    with pytest.raises(ConversionError, match="by zone"):
        DegradationModel(single=(0.001, 0.002), by_zone=None).with_hot_zone_rate(0.0094, 7)
    # the real countries carry the rate of Straub and Mueck 2025 for PV and none for wind
    for iso in ("BRA", "IND", "PRT"):
        tech = parameters.countries[iso].technologies
        hz = tech.solar.degradation_by_zone.hot_zone_sensitivity
        assert (hz.rate, hz.applies_from_zone) == (0.0094, 7)
        assert not hasattr(tech.wind, "degradation_by_zone")
    zzz = parameters.countries["ZZZ"]
    assert resolve_group3("ZZZ", "solar", zzz.connection, zzz.technologies.solar, None).hot_zone_sensitivity is None


@pytest.mark.unit
def test_the_efficiency_report_floors_at_zero_and_counts_cells_below_ninety_percent():
    d = np.array([0.0, 50.0, 400.0, 5000.0])  # km
    eta_min, below = transmission_efficiency_report(d, 1.25, 0.0005)
    assert eta_min == 0.0  # the last cell is floored
    assert below == 2  # 1 - 0.0005*1.25*400 = 0.75 and the floored one; 50 km gives 0.96875
    assert transmission_efficiency_report(d, 1.25, 0.0) == (1.0, 0)


@pytest.mark.unit
def test_the_fleet_file_of_the_degradation_zones_is_present_and_the_conversion_indices_are_loadable():
    """The fleet file and the World Bank indices live in GEOFREA_DATA_DIR/external: a missing file fails this test (pending for Douglas)."""
    # the autouse fixture of conftest points GEOFREA_DATA_DIR at a temporary directory: the real one is read from the key of `.env` (only that key)
    env = REPO / ".env"
    values = dict(
        line.split("=", 1) for line in env.read_text(encoding="utf-8").splitlines() if line.startswith("GEOFREA_DATA_DIR=")
    ) if env.is_file() else {}
    assert values.get("GEOFREA_DATA_DIR"), "GEOFREA_DATA_DIR is not set in .env"
    root = Path(values["GEOFREA_DATA_DIR"].strip().strip('"'))
    fleet = root / "external" / "pv_degradation" / "Fleet_results_public_2022_02_02.csv"
    assert fleet.is_file(), f"fleet data absent: {fleet}"
    indices = root / "external" / "world_bank" / "conversion_indices.json"
    for iso in ("BRA", "IND", "PRT"):
        loaded = load_conversion_indices(indices, iso)
        assert loaded.factor(2024) > 0
