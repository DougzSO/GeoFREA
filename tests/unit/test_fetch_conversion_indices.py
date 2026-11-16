"""The collection script of the conversion indices and its manual entry for the US deflator (COMMAND 158, DEC-071)."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "fetch_conversion_indices.py"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("fetch_conversion_indices", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_a_manual_entry_carries_its_values_source_date_and_the_provisional_note(script):
    entry = script.manual_entry(["2024=119.03", "2025=122.36"], "World Bank, read by the author", "", "2026-11-16")
    assert entry["values"] == {"2024": 119.03, "2025": 122.36}
    assert entry["source"] == "World Bank, read by the author"
    assert entry["collected"] == "2026-11-16"
    assert "provisional" in entry["note"]


@pytest.mark.unit
@pytest.mark.parametrize("pairs", [["2025"], ["year=1.0"], ["2025=abc"]])
def test_a_malformed_manual_value_is_refused(script, pairs):
    with pytest.raises(ValueError):
        script.manual_entry(pairs, "source", "", "2026-11-16")


@pytest.mark.unit
def test_a_manual_entry_without_its_source_is_refused(script):
    with pytest.raises(ValueError, match="source"):
        script.manual_entry(["2025=122.36"], "", "", "2026-11-16")


@pytest.mark.unit
def test_the_indicator_and_the_us_code_are_the_ones_the_loader_reads(script):
    from geofrea.lcoe_modeling.connection import DEFLATOR, US

    assert (script.DEFLATOR, script.US_ISO) == (DEFLATOR, US)
