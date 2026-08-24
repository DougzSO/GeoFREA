"""Unit tests for main.py's phase_specs construction guard.

main.py lives at the repo root (not under src/geofrea/) — imported
here the same way pytest already resolves it for collection.
"""

import pytest

import main


@pytest.mark.unit
def test_build_phase_specs_raises_when_both_unwired_phases_enabled():
    with pytest.raises(main.UnwiredPhasesError):
        main._build_phase_specs(
            {"data_acquisition": True, "data_quality_audit": True}
        )


@pytest.mark.unit
def test_build_phase_specs_ok_when_only_acquisition_enabled():
    specs = main._build_phase_specs({"data_acquisition": True, "data_quality_audit": False})
    assert [spec.name for spec in specs] == ["data_acquisition", "data_quality_audit"]


@pytest.mark.unit
def test_build_phase_specs_ok_when_only_audit_enabled():
    specs = main._build_phase_specs({"data_acquisition": False, "data_quality_audit": True})
    assert [spec.name for spec in specs] == ["data_acquisition", "data_quality_audit"]


@pytest.mark.unit
def test_build_phase_specs_ok_when_neither_enabled():
    specs = main._build_phase_specs({})
    assert [spec.name for spec in specs] == ["data_acquisition", "data_quality_audit"]
