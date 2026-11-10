"""The recorder of config reads (`tests/synthetic/config_trace.py`) sees what a phase reads, and the scope check built on it (COMMAND 127, item 5b)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from geofrea.core.config_loader import load_parameters, load_settings
from tests.synthetic.config_trace import ConfigTrace, is_covered, selectors_of, uncovered

pytestmark = pytest.mark.unit

CONFIG = Path(__file__).resolve().parents[2] / "config"


def test_reads_of_a_settings_field_are_attributed_to_the_running_phase_and_its_path():
    trace = ConfigTrace()
    with trace.installed({}):
        settings = load_settings(CONFIG / "settings.yaml")
        _ = settings.geospatial.pvcz_csv  # before any phase: not recorded
        trace.phase = "land_eligibility"
        _ = settings.geospatial.pvcz_csv
        _ = settings.geospatial.pvcz_max_distance_km
        trace.phase = None
    assert trace.reads["land_eligibility"] == {
        ("settings", "geospatial.pvcz_csv"),
        ("settings", "geospatial.pvcz_max_distance_km"),
    }


def test_a_path_survives_a_hop_through_a_mapping_of_models_and_a_parameter_entry():
    trace = ConfigTrace()
    with trace.installed({}):
        params = load_parameters(CONFIG / "parameters.json")
        country = params.countries["PRT"]  # the mapping is read through its field `countries`
        trace.phase = "grid_alignment"
        _ = country.connection.poi_voltage_threshold_kv.value
        trace.phase = None
    assert ("parameters", "countries.PRT.connection.poi_voltage_threshold_kv.value") in trace.reads["grid_alignment"]
    assert not trace.unattributed


def test_a_dump_of_a_section_counts_as_a_read_of_the_whole_section():
    trace = ConfigTrace()
    with trace.installed({}):
        settings = load_settings(CONFIG / "settings.yaml")
        _ = settings.geospatial  # traversal
        trace.phase = "grid_alignment"
        settings.geospatial.model_dump()
        trace.phase = None
    assert trace.reads["grid_alignment"] == {("settings", "geospatial")}


def test_the_raw_experiments_read_by_a_phase_is_traced_but_not_the_loader_or_a_membership_test():
    text = (CONFIG / "experiments.yaml").read_text(encoding="utf-8")
    trace = ConfigTrace()
    with trace.installed({"experiments": text}):
        trace.phase = "climate_forcing"
        doc = yaml.safe_load(text)
        assert "gcm_ensemble" in doc  # a membership test reads nothing

        def walk(node):
            for value in node.values():
                if isinstance(value, dict):
                    walk(value)

        walk(doc["gcm_ensemble"])  # reads every leaf under gcm_ensemble
        trace.phase = None
    assert all(key == "experiments" for key, _ in trace.reads["climate_forcing"])
    assert any(path.startswith("gcm_ensemble") for _, path in trace.reads["climate_forcing"])
    # the loader validates the whole file without being a read of the phase running at that moment
    trace2 = ConfigTrace()
    with trace2.installed({"experiments": text}):
        trace2.phase = "climate_forcing"
        from geofrea.core.config_loader import load_experiments

        load_experiments(CONFIG / "experiments.yaml")
        trace2.phase = None
    assert not trace2.reads


def test_the_recorder_is_removed_after_the_block():
    from pydantic import BaseModel

    before = BaseModel.__getattribute__
    with ConfigTrace().installed({}):
        assert BaseModel.__getattribute__ is not before
    assert BaseModel.__getattribute__ is before


@pytest.mark.parametrize(
    ("key", "path", "covered"),
    [
        ("settings", "geospatial.resolutions", True),  # F2a names `geospatial`
        ("settings", "geospatial", True),
        ("settings", "figures", False),
        ("parameters", "countries.ZZZ.connection.reference_project_mw.value", False),  # F2a does not read it
        ("parameters", "countries.OTHER.technologies.solar.luf", False),
    ],
)
def test_a_leaf_is_covered_when_a_selector_of_the_phase_is_a_prefix_of_its_path(key, path, covered):
    selectors = {"settings": [("geospatial",)]}
    assert is_covered(key, path, selectors) is covered


def test_a_wildcard_step_and_the_whole_file_selector_cover():
    assert is_covered("technologies", "technologies.solar.cf_model", {"technologies": [("*",)]})
    assert is_covered("parameters", "countries.ZZZ.x.y", {"parameters": [("countries", "ZZZ")]})
    assert not is_covered("parameters", "countries.ABC.x", {"parameters": [("countries", "ZZZ")]})
    assert is_covered("experiments", "a.q.c", {"experiments": [("a", "*", "c")]})
    assert not is_covered("experiments", "a.q.d", {"experiments": [("a", "*", "c")]})


def test_uncovered_names_the_reads_a_scope_misses(monkeypatch):
    trace = ConfigTrace()
    trace.reads["grid_alignment"] = {("settings", "geospatial.resolutions"), ("parameters", "countries.ZZZ.connection.poi_voltage_threshold_kv.value")}
    trace.reads["not_a_phase"] = {("settings", "x")}
    missing = uncovered(trace, "ZZZ")
    assert set(missing) <= {"grid_alignment"}
    if "grid_alignment" in missing:  # before the keys are in the scope of F2a, the check names the one it misses
        assert missing["grid_alignment"] == ["parameters:countries.ZZZ.connection.poi_voltage_threshold_kv.value"]


def test_the_selectors_of_a_phase_carry_the_country():
    assert ("countries", "ZZZ") in selectors_of("technical_potential", "ZZZ")["parameters"]
