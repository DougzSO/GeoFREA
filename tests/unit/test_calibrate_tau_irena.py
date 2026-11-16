"""The calibration of tau against the published IRENA LCOE and the reference file it reads (COMMAND 159, DEC-072, DEC-075 to DEC-080)."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "calibrate_tau_irena.py"
REFERENCE = REPO / "config" / "irena_reference.yaml"
FIELDS = {"currency", "price_year", "edition", "source", "status", "verified"}


@pytest.fixture(scope="module")
def calib():
    spec = importlib.util.spec_from_file_location("calibrate_tau_irena", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ref():
    return yaml.safe_load(REFERENCE.read_text(encoding="utf-8"))


def _entries(node):
    if isinstance(node, dict):
        if "edition" in node and "verified" in node:
            yield node
        for child in node.values():
            yield from _entries(child)


# --- the reference file -----------------------------------------------------------------------------------------


@pytest.mark.unit
def test_every_value_of_the_reference_file_carries_the_six_fields(ref):
    entries = list(_entries(ref))
    assert len(entries) > 40
    for entry in entries:
        assert FIELDS <= set(entry), entry
        assert entry["edition"] in {"irena_rpgc_2024", "irena_rpgc_2025", "irena_finance_2023"}


@pytest.mark.unit
def test_the_2021_wacc_points_are_verified_and_the_solar_cf_of_portugal_is_a_regional_proxy(ref):
    for by_tech in ref["wacc"]["country_2021"].values():
        assert all(entry["verified"] is True for entry in by_tech.values())
    cf = ref["editions"]["irena_rpgc_2024"]["pairs"]["PRT"]["solar"]["cf"]
    assert cf["regional_proxy"] is True and cf["status"] == "regional_proxy" and cf["value"] == 0.15
    assert ref["wacc"]["country_2021"]["BRA"]["solar"]["value"] == 0.063
    assert ref["wacc"]["country_2021"]["IND"]["wind"]["value"] == 0.059


@pytest.mark.unit
def test_the_table_of_report_11_is_copied_without_change(ref):
    pairs = ref["editions"]["irena_rpgc_2024"]["pairs"]
    values = {(iso, tech): {k: pairs[iso][tech][k]["value"] for k in ("tic_usd_per_kw", "cf", "om_usd_per_kw_yr", "lcoe_usd_per_mwh")} for iso in pairs for tech in pairs[iso]}
    assert values[("BRA", "solar")] == {"tic_usd_per_kw": 724, "cf": 0.20, "om_usd_per_kw_yr": 10.95, "lcoe_usd_per_mwh": 48}
    assert values[("IND", "wind")] == {"tic_usd_per_kw": 1110, "cf": 0.29, "om_usd_per_kw_yr": 23, "lcoe_usd_per_mwh": 48}
    assert values[("PRT", "wind")] == {"tic_usd_per_kw": 1659, "cf": 0.34, "om_usd_per_kw_yr": 45, "lcoe_usd_per_mwh": 51}
    assert ref["editions"]["irena_rpgc_2024"]["life_years"]["value"] == 25
    assert pairs["BRA"]["wind"]["cf"]["alternative"]["value"] == 0.56  # Table 2.2, the sensitivity of DEC-077
    secondary = ref["editions"]["irena_rpgc_2025"]["pairs"]
    assert (secondary["BRA"]["solar"]["lcoe_usd_per_mwh"]["value"], secondary["IND"]["wind"]["lcoe_usd_per_mwh"]["value"]) == (37, 43)
    assert secondary["PRT"]["solar"]["lcoe_usd_per_mwh"]["value"] is None  # no number: null


# --- the kernel run -----------------------------------------------------------------------------------------------


def _explicit_lcoe(rate, tic, om, life, cf):
    """The textbook form with an explicit loop over the years, per kW: capex at t = 0, O&M and energy at t = 1..n, no degradation."""
    energy = cf * 8760.0 / 1000.0  # MWh per kW per year
    cost = tic + sum(om / (1 + rate) ** t for t in range(1, life + 1))
    discounted_energy = sum(energy / (1 + rate) ** t for t in range(1, life + 1))
    return cost / discounted_energy


@pytest.mark.unit
@pytest.mark.parametrize("rate", [0.0, 0.042, 0.077])
def test_the_kernel_run_equals_the_textbook_sum_over_the_years(calib, ref, rate):
    entries = ref["editions"]["irena_rpgc_2024"]["pairs"]["BRA"]["wind"]
    tic, cf, om = entries["tic_usd_per_kw"]["value"], entries["cf"]["value"], entries["om_usd_per_kw_yr"]["value"]
    value = calib.f6_lcoe(rate, tic=tic, om=om, life=25, p_mw=100.0, cf=cf)
    assert value == pytest.approx(_explicit_lcoe(rate, tic, om, 25, cf), rel=1e-9)


@pytest.mark.unit
def test_the_reference_cell_has_no_distance_and_the_energy_of_the_capacity_factor(calib):
    cell = calib.reference_cell(100.0, 0.20)
    assert cell.p_mw[0] == 100.0
    assert cell.dist_sub_km[0] == 0.0 and cell.dist_road_km[0] == 0.0
    assert cell.energy_mwh[0] == pytest.approx(0.20 * 8760.0 * 100.0)
    assert cell.energy_slope[0] == 0.0 and cell.energy_offset[0] == 1.0


@pytest.mark.unit
def test_the_equating_rate_gives_back_the_published_lcoe_and_a_target_outside_the_search_gives_none(calib, ref):
    entries = ref["editions"]["irena_rpgc_2024"]["pairs"]["IND"]["solar"]
    kernel = {"tic": 525.0, "om": 10.95, "life": 25, "p_mw": 100.0, "cf": entries["cf"]["value"]}
    rate = calib.equating_rate(38.0, **kernel)
    assert rate is not None and 0.0 < rate < 0.6
    assert calib.f6_lcoe(rate, **kernel) == pytest.approx(38.0, abs=1e-6)
    assert calib.equating_rate(1.0, **kernel) is None  # below the LCOE at a zero rate: no root


@pytest.mark.unit
def test_a_pair_with_a_null_field_is_refused_and_the_fields_are_listed_and_the_others_run(calib, ref, tmp_path):
    broken = yaml.safe_load(REFERENCE.read_text(encoding="utf-8"))
    pair = broken["editions"]["irena_rpgc_2024"]["pairs"]["IND"]["wind"]
    pair["cf"]["value"] = None
    pair["om_usd_per_kw_yr"]["value"] = None
    assert calib.missing_fields(broken, "IND", "wind") == ["irena_rpgc_2024:cf", "irena_rpgc_2024:om_usd_per_kw_yr"]
    assert calib.missing_fields(broken, "IND", "solar") == []
    path = tmp_path / "broken.yaml"
    path.write_text(yaml.safe_dump(broken), encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPT), "--reference", str(path)], capture_output=True, text=True, check=False)
    assert done.returncode == 0
    assert "IND wind: REFUSED, null in irena_rpgc_2024:cf, irena_rpgc_2024:om_usd_per_kw_yr" in done.stdout
    for other in ("BRA solar", "BRA wind", "IND solar", "PRT solar", "PRT wind"):
        assert f"\n{other}" in done.stdout


# --- the printed table ------------------------------------------------------------------------------------------


def _indices_with_us(tmp_path):
    series = {"2023": 116.144257693854, "2024": 119.027387038617, "2025": 122.361624831936}
    data = {
        "source": "test",
        "accessed": "2026-11-16",
        "indicators": {
            "NY.GDP.DEFL.ZS": {"values": {iso: {"2024": 100.0} for iso in ("BRA", "IND", "PRT")} | {"USA": series}},
            "PA.NUS.FCRF": {"values": {iso: {"2024": 1.0} for iso in ("BRA", "IND", "PRT")}},
        },
    }
    path = tmp_path / "indices.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _run(tmp_path, *extra):
    return subprocess.run([sys.executable, str(SCRIPT), *extra], capture_output=True, text=True, check=False, cwd=tmp_path)


@pytest.mark.unit
def test_the_script_runs_the_six_pairs_marks_the_proxy_and_leaves_it_out_of_the_aggregate(tmp_path):
    done = _run(tmp_path, "--conversion-indices", str(_indices_with_us(tmp_path)))
    assert done.returncode == 0, done.stderr
    primary = done.stdout.split("SECONDARY RUN")[0]
    for pair in ("BRA solar", "BRA wind", "IND solar", "IND wind", "PRT solar", "PRT wind"):
        assert f"\n{pair}" in primary
    assert "regional_proxy (left out of every aggregate)" in primary.split("\nPRT solar")[1].splitlines()[0]
    assert "over 5 pairs (regional_proxy pairs left out)" in primary
    assert "OQ-104" in primary


@pytest.mark.unit
def test_the_secondary_run_is_labelled_converts_with_to_usd_2024_and_is_refused_without_the_us_series(tmp_path):
    with_us = _run(tmp_path, "--conversion-indices", str(_indices_with_us(tmp_path))).stdout
    secondary = with_us.split("SECONDARY RUN")[1].split("AUDIT")[0]
    assert "labelled secondary" in secondary
    bra = next(line for line in secondary.splitlines() if line.startswith("BRA solar"))
    assert " 37.00 " in bra and " 35.99 " in bra  # 37 USD of 2025 as 35.99 USD of 2024 (DEC-071)
    assert "refused: null in irena_rpgc_2025:lcoe_usd_per_mwh" in secondary  # Portugal has no 2025 national value
    no_us = json.loads(_indices_with_us(tmp_path).read_text(encoding="utf-8"))
    del no_us["indicators"]["NY.GDP.DEFL.ZS"]["values"]["USA"]
    path = tmp_path / "no_us.json"
    path.write_text(json.dumps(no_us), encoding="utf-8")
    refused = _run(tmp_path, "--conversion-indices", str(path)).stdout.split("SECONDARY RUN")[1]
    assert "needs a US deflator, which is not loaded" in refused


@pytest.mark.unit
def test_the_script_prints_the_audit_of_item_6_and_creates_no_file(tmp_path):
    done = _run(tmp_path, "--conversion-indices", str(_indices_with_us(tmp_path)))
    audit = done.stdout.split("AUDIT")[1]
    for marker in ("(d) O&M", "(a) discount_rate of F6 is REAL", "(b) the power basis", "(c) construction period: none", "degradation:"):
        assert marker in audit, marker
    assert "IRENA USD/kW/yr" in audit and "F6 frac of capex" in audit
    assert not [p for p in tmp_path.iterdir() if p.suffix in {".parquet", ".csv", ".json"} and p.name != "indices.json"]
