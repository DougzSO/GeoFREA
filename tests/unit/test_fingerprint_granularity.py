"""Granularity of the fingerprints (COMMAND 61): a change of a config schema reaches only the phases that read the section it describes.

A phase runs again when its code fingerprint or its configuration fingerprint changes. The schema modules are not in the code fingerprint by
their declarations (fields, defaults, validators); the configuration fingerprint holds the section as the schema validates it, with the defaults
resolved. A field added with a default to a schema, or a default changed, then invalidates the phases that read that section, and no other.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

import pytest

import geofrea
from geofrea.config_models.land_availability import LandAvailability
from geofrea.core import config_fingerprint as cf
from geofrea.core.code_fingerprint import (
    CONFIG_SCHEMA_MODULES,
    PHASE_CODE_ROOTS,
    code_fingerprint,
    phase_modules,
)
from geofrea.core.config_fingerprint import (
    CONFIG_FILES,
    PHASE_CONFIG_SCOPE,
    TURBINES,
    DiskConfigSource,
    config_fingerprint,
)
from geofrea.core.config_schemas import AbsoluteMapsConfig, ExperimentsFile, HazardIndicators

pytestmark = pytest.mark.unit

SRC = Path(geofrea.__file__).resolve().parent
CONFIG = SRC.parents[1] / "config"
F3_AND_AFTER = {
    "land_eligibility",
    "technical_potential",
    "lcoe_modeling",
    "robustness_analysis",
    "external_validation",
    "results_synthesis",
}


@pytest.fixture(autouse=True)
def _fresh_parse_cache():
    cf._parse_text.cache_clear()
    yield
    cf._parse_text.cache_clear()


@pytest.fixture
def source_copy(tmp_path) -> Path:
    target = tmp_path / "geofrea"
    shutil.copytree(SRC, target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


def _config_fingerprints(config_dir: Path = CONFIG, iso: str = "PRT") -> dict[str, str]:
    source = DiskConfigSource(
        {k: config_dir / name for k, name in CONFIG_FILES.items()}, config_dir / TURBINES
    )
    return {phase: config_fingerprint(phase, iso, source) for phase in PHASE_CONFIG_SCOPE}


def _code_fingerprints(root: Path) -> dict[str, str]:
    return {phase: code_fingerprint(phase, root) for phase in PHASE_CODE_ROOTS}


def _changed(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return {p for p in before if before[p] != after[p]}


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (path.name, old, text.count(old))
    path.write_text(text.replace(old, new), encoding="utf-8")


# ─── the configuration side ──────────────────────────────────────────────


def test_a_new_field_with_a_default_in_the_schema_of_the_maps_invalidates_only_potential_maps(
    monkeypatch,
):
    before = _config_fingerprints()

    class MapsEdited(AbsoluteMapsConfig):
        label_size_pt: int = 7

    class Edited(ExperimentsFile):
        absolute_maps: MapsEdited

    monkeypatch.setattr(cf, "ExperimentsFile", Edited)
    cf._parse_text.cache_clear()
    assert _changed(before, _config_fingerprints()) == {"potential_maps"}


def test_a_new_field_with_a_default_in_a_schema_f3_does_not_read_leaves_f3_and_its_chain_unchanged(
    monkeypatch,
):
    before = _config_fingerprints()

    class HazardsEdited(HazardIndicators):
        window_days: int = 5

    class Edited(ExperimentsFile):
        hazard_indicators: HazardsEdited

    monkeypatch.setattr(cf, "ExperimentsFile", Edited)
    cf._parse_text.cache_clear()
    changed = _changed(before, _config_fingerprints())
    assert changed == {"hazard_context"}
    assert not changed & F3_AND_AFTER


def test_a_changed_default_of_a_field_f3_reads_invalidates_f3_and_the_phases_after_it_that_read_it(
    monkeypatch, tmp_path
):
    config = tmp_path / "config"
    shutil.copytree(CONFIG, config)
    path = config / "experiments.yaml"
    text = path.read_text(encoding="utf-8")
    line = "  missing_elevation: ineligible\n"
    assert text.count(line) == 1
    path.write_text(text.replace(line, ""), encoding="utf-8")
    before = _config_fingerprints(
        config
    )  # the field is not written: the default is what the phases receive

    class LandEdited(LandAvailability):
        missing_elevation: Literal["ineligible", "eligible"] = "eligible"

    class Edited(ExperimentsFile):
        land_availability: LandEdited

    monkeypatch.setattr(cf, "ExperimentsFile", Edited)
    cf._parse_text.cache_clear()
    changed = _changed(before, _config_fingerprints(config))
    assert F3_AND_AFTER <= changed
    assert not changed & {"potential_maps", "hazard_context", "climate_forcing", "data_acquisition"}


def test_the_configuration_a_phase_reads_holds_the_defaults_resolved():
    source = DiskConfigSource(
        {k: CONFIG / name for k, name in CONFIG_FILES.items()}, CONFIG / TURBINES
    )
    payload = cf.phase_config_payload("land_eligibility", "PRT", source)
    assert payload["experiments"]["land_availability"]["missing_elevation"] == "ineligible"


def test_writing_a_default_explicitly_does_not_change_a_fingerprint(tmp_path):
    config = tmp_path / "config"
    shutil.copytree(CONFIG, config)
    before = _config_fingerprints(config)
    # `significant_figures: 2` is the value; `per_cell: false` is the default: spelling the default out changes nothing
    text = (config / "experiments.yaml").read_text(encoding="utf-8")
    assert "  per_cell: false\n" in text
    (config / "experiments.yaml").write_text(
        text.replace("  per_cell: false\n", ""), encoding="utf-8"
    )
    assert _changed(before, _config_fingerprints(config)) == set()


# ─── the code side ───────────────────────────────────────────────────────


def test_every_schema_module_exists_and_the_phases_that_read_them_do_import_them():
    for name in CONFIG_SCHEMA_MODULES:
        assert (SRC / Path(*name.split("."))).with_suffix(".py").is_file(), name
    assert any("core.config_schemas" in phase_modules(p) for p in PHASE_CODE_ROOTS)


def test_a_field_added_with_a_default_to_a_schema_module_changes_no_code_fingerprint(source_copy):
    before = _code_fingerprints(source_copy)
    _edit(
        source_copy / "core" / "config_schemas.py",
        '    palette: Literal["viridis", "cividis"]\n',
        '    palette: Literal["viridis", "cividis"]\n    label_size_pt: int = 7\n',
    )
    assert _changed(before, _code_fingerprints(source_copy)) == set()


def test_a_changed_default_or_validator_of_a_schema_module_changes_no_code_fingerprint(source_copy):
    before = _code_fingerprints(source_copy)
    _edit(
        source_copy / "config_models" / "land_availability.py",
        'missing_elevation: Literal["ineligible"] = "ineligible"',
        'missing_elevation: Literal["ineligible", "eligible"] = "eligible"',
    )
    _edit(
        source_copy / "core" / "config_schemas.py",
        "        for name, rule in self.hypothesis_rules.items():\n",
        "        for name, rule in sorted(self.hypothesis_rules.items()):\n",
    )
    assert _changed(before, _code_fingerprints(source_copy)) == set()


def test_a_calculation_in_a_schema_module_still_changes_the_phases_that_import_it(source_copy):
    before = _code_fingerprints(source_copy)
    _edit(
        source_copy / "core" / "schemas.py",
        "            return float(getattr(self, scenario))\n",
        "            return float(getattr(self, scenario)) * 1.0001\n",
    )
    expected = {p for p in PHASE_CODE_ROOTS if "core.schemas" in phase_modules(p, source_copy)}
    assert expected
    assert _changed(before, _code_fingerprints(source_copy)) == expected


def test_a_helper_function_of_a_schema_module_counts_as_code(source_copy):
    before = _code_fingerprints(source_copy)
    _edit(
        source_copy / "config_models" / "land_availability.py",
        "    r = params.riparian_setback_km\n",
        "    r = params.riparian_setback_km  # same line\n    _ = 1\n",
    )
    expected = {
        p
        for p in PHASE_CODE_ROOTS
        if "config_models.land_availability" in phase_modules(p, source_copy)
    }
    assert expected
    assert _changed(before, _code_fingerprints(source_copy)) == expected


def test_a_change_of_the_maps_schema_alone_runs_only_potential_maps(source_copy, monkeypatch):
    """Code and configuration together: the phases that would run again after a field is added to the schema of the maps."""
    code_before, config_before = _code_fingerprints(source_copy), _config_fingerprints()
    _edit(
        source_copy / "core" / "config_schemas.py",
        '    palette: Literal["viridis", "cividis"]\n',
        '    palette: Literal["viridis", "cividis"]\n    label_size_pt: int = 7\n',
    )

    class MapsEdited(AbsoluteMapsConfig):
        label_size_pt: int = 7

    class Edited(ExperimentsFile):
        absolute_maps: MapsEdited

    monkeypatch.setattr(cf, "ExperimentsFile", Edited)
    cf._parse_text.cache_clear()
    rerun = _changed(code_before, _code_fingerprints(source_copy)) | _changed(
        config_before, _config_fingerprints()
    )
    assert rerun == {"potential_maps"}
