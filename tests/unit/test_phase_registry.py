"""COMMAND 200: `config/phases.yaml` names every PhaseSpec and only them, is read by the plan and the log, and no fingerprint sees it."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

import main as geofrea_main
from geofrea.core import phase_registry
from geofrea.core.config_fingerprint import CONFIG_FILES, PHASE_CONFIG_SCOPE
from geofrea.core.phase_registry import (
    PhaseInfo,
    load_registry,
    phase_info,
    phase_label,
    validate_against,
)

REPO = Path(__file__).resolve().parents[2]


def _specs():
    return geofrea_main._build_phase_specs(
        geofrea_main.ResolutionsConfig(suitability=0.01),
        100.0,
        geofrea_main.load_audit_config(geofrea_main.AUDIT_YAML),
        ("solar", "wind"),
    )


@pytest.mark.unit
def test_the_orchestrated_entries_are_exactly_the_phase_specs():
    names = {s.name for s in _specs()}
    assert {e.id for e in load_registry() if e.orchestrated} == names
    validate_against(names)  # does not raise


@pytest.mark.unit
def test_validate_against_names_what_differs():
    names = {s.name for s in _specs()}
    with pytest.raises(ValueError, match=r"no entry for \['brand_new'\]"):
        validate_against(names | {"brand_new"})
    with pytest.raises(ValueError, match=r"no PhaseSpec for \['overview'\]"):
        validate_against(names - {"overview"})


@pytest.mark.unit
def test_the_support_entries_outside_the_orchestrator_are_marked():
    assert {e.id for e in load_registry() if not e.orchestrated} == {"cross_country_h4", "explorer"}


@pytest.mark.unit
def test_every_entry_is_complete_and_ids_and_codes_are_unique():
    entries = load_registry()
    assert len({e.id for e in entries}) == len(entries)
    codes = [e.code for e in entries if e.code]
    assert len(set(codes)) == len(codes)
    for e in entries:
        assert e.name_en.strip() and e.group.strip()


@pytest.mark.unit
def test_the_registry_order_respects_the_requires_and_produces_of_the_specs():
    position = {e.id: i for i, e in enumerate(load_registry())}
    producer = {key: s.name for s in _specs() for key in s.produces}
    for spec in _specs():
        for key in spec.requires:
            if key in producer and producer[key] != spec.name:
                assert position[producer[key]] < position[spec.name], f"{spec.name} requires {key} from {producer[key]}"


@pytest.mark.unit
def test_phases_yaml_is_in_no_fingerprint_scope():
    assert "phases" not in CONFIG_FILES  # the file keys a phase may read
    for phase, scope in PHASE_CONFIG_SCOPE.items():
        assert "phases" not in scope, phase
        assert not any("phases.yaml" in str(sel) for sels in scope.values() for sel in sels)


@pytest.mark.unit
def test_a_phase_the_registry_does_not_list_keeps_its_id_as_label():
    assert phase_info("not_a_phase") is None
    assert phase_label("not_a_phase") == "not_a_phase"
    assert phase_label("lcoe_modeling") == "Levelized cost"


@pytest.mark.unit
def test_a_repeated_id_or_a_missing_field_is_refused(tmp_path):
    bad = tmp_path / "phases.yaml"
    bad.write_text("phases:\n  - {id: a, name_en: A, group: G}\n  - {id: a, name_en: B, group: G}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="repeated"):
        phase_registry.load_registry.__wrapped__(bad)
    bad.write_text("phases:\n  - {id: a, group: G}\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"lacks \['name_en'\]"):
        phase_registry.load_registry.__wrapped__(bad)


@pytest.mark.unit
def test_the_plan_prints_the_portuguese_name(capsys):
    from geofrea.core.orchestrator import PlanEntry

    geofrea_main.print_plan(
        "PRT",
        [PlanEntry(phase="lcoe_modeling", action="execute", reason="no manifest entry yet")],
        ["lcoe_modeling"],
        [],
        "0p05deg",
        None,
    )
    out = capsys.readouterr().out
    assert "lcoe_modeling" in out and "Levelized cost" in out and "execute" in out


@pytest.mark.unit
def test_the_generated_tables_of_the_docs_are_current():
    done = subprocess.run([sys.executable, str(REPO / "scripts" / "render_phase_tables.py"), "--check"], check=False, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


@pytest.mark.unit
def test_the_name_column_of_methodology_4_2_matches_the_registry():
    text = (REPO / "docs" / "METHODOLOGY.md").read_text(encoding="utf-8")
    section = text.split("### 4.2 Phase table", 1)[1].split("\n---", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("|")][2:]
    by_key = {}
    for e in load_registry():
        by_key[e.id] = e
        if e.code:
            by_key[e.code] = e
    assert rows
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        entry = by_key[cells[0]]
        assert cells[1] == entry.name_en, cells[0]
    header = section.splitlines()[2]
    assert re.match(r"\| Phase \| Name \| Module", header)


@pytest.mark.unit
def test_phase_info_is_a_frozen_record():
    info = phase_info("overview")
    assert isinstance(info, PhaseInfo) and info.orchestrated and info.group == "Territory"


@pytest.mark.unit
def test_the_registry_file_is_english_only():
    text = (REPO / "config" / "phases.yaml").read_text(encoding="utf-8")
    assert text.isascii()  # no Portuguese name or accented word (COMMAND 200B)
    assert "name_pt" not in text
    assert {e.group for e in load_registry()} <= {"Data", "Territory", "Climate", "Potential", "Economics", "Robustness", "Validation", "Synthesis", "Platform"}
