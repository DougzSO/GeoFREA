"""The deferred content check on the synthetic country ZZZ, through the real phases (COMMAND 80; D-core-050).

ZZZ2 runs hazard_context and technical_potential; its manifest is the reference. An artifact of technical_potential is then altered by hand in the
reference (its recorded content hash), and the same phases run again: hazard_context matches the reference, technical_potential does not, with no change of
configuration to explain it, so the run stops before potential_maps and `outputs/ZZZ/deferred_check.json` names the artifact and the probable cause.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.slow, pytest.mark.synthetic]

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

import zzz2_world as world
import zzz_run

PHASES = ["hazard_context", "technical_potential", "potential_maps"]
CHECKED = PHASES[:2]


def _run(main, data, rerun):
    from geofrea.core.config_loader import load_audit_config, load_settings

    settings = load_settings(main.SETTINGS_YAML)
    return main.run_geofrea(
        "ZZZ",
        PHASES,
        rerun,
        settings.geospatial.resolutions,
        settings.geospatial.distance_cap_km,
        load_audit_config(main.AUDIT_YAML),
        "zzz-deferred-check",
        False,
        None,
        tuple(settings.run.technologies),
        False,
        "summary",
        settings.memory.max_batch_gb,
    )


def test_an_artifact_altered_by_hand_stops_the_run_and_is_named(tmp_path):
    import main  # repo-root script

    data = tmp_path / "zzz_data"
    data.mkdir()
    paths = zzz_run.prepare_configuration(data, 16, 64, parameter_changes=world.PARAMETER_OVERRIDES)
    patch = pytest.MonkeyPatch()
    patch.setenv("GEOFREA_DATA_DIR", str(data))
    patch.setattr(main, "TECHNOLOGIES_YAML", paths["technologies"])
    patch.setattr(main, "EXPERIMENTS_YAML", paths["experiments"])
    patch.setattr(main, "PARAMETERS_JSON", paths["parameters"])
    patch.setattr(main, "POWER_CURVES_DIR", zzz_run.CURVES)
    try:
        subprocess.run(
            [sys.executable, str(REPO / "scripts" / "generate_zzz2_fixture.py")],
            check=True,
            env={**os.environ, "GEOFREA_DATA_DIR": str(data)},
            capture_output=True,
        )
        zzz_run.refuse_network(patch)

        ok, orchestrator, _ = _run(main, data, [])  # the run that makes the reference
        assert ok
        manifest_path = data / "outputs" / "ZZZ" / "manifest.json"
        reference = json.loads(manifest_path.read_text(encoding="utf-8"))
        altered = next(k for k, e in reference["artifacts"].items() if e["phase"] == "technical_potential")
        reference["artifacts"][altered]["content_sha256"] = "altered-by-hand-" + reference["artifacts"][altered]["content_sha256"]
        (data / "reference_manifest.json").write_text(json.dumps(reference), encoding="utf-8")
        checks = data / "deferred_checks.yaml"
        checks.write_text(
            yaml.safe_dump(
                {
                    "countries": {"ZZZ": {"baseline": "reference_manifest.json", "phases": PHASES}},
                    "suspects": {"technical_potential": "the wind table"},
                }
            ),
            encoding="utf-8",
        )
        patch.setattr(main, "DEFERRED_CHECKS_YAML", checks)

        ok, _, results = _run(main, data, CHECKED)  # the run that is checked

        assert not ok
        assert results["hazard_context"].status == "success"
        assert results["technical_potential"].status == "success"
        assert results["potential_maps"].status == "skipped_upstream_failed"
        report = json.loads((data / "outputs" / "ZZZ" / "deferred_check.json").read_text(encoding="utf-8"))
        assert report["verdict"] == "DIFERENTE"
        assert report["phases"]["hazard_context"]["verdict"] == "IDENTICO"
        entry = report["phases"]["technical_potential"]
        assert entry["verdict"] == "DIFERENTE" and altered in entry["different_unexplained"]
        assert entry["probable_cause"] == "the wind table"
        assert "potential_maps" not in report["phases"]
    finally:
        patch.undo()
