"""Keep the state a country has on disk as an accepted round of the reference store, with the check as evidence (COMMAND 91; D-core-051).

The pipeline keeps a round by itself when it is accepted (`core.reference_store`). This script does it by hand for the state that is on disk now: for a country
the check lists (`config/deferred_checks.yaml`) it first runs the check on every listed phase of the manifest, against the reference the yaml names, and writes
the verdicts, the rasters decided by tolerance and the differences nobody explained to the index of the round; it refuses the country if one phase is DIFERENTE.
A country the yaml does not list has no check: the round is kept with the note it was given, which has to say what proves it.

    python scripts/publish_reference.py PRT IND BRA --note "state after COMMAND 91" --historical BRA:seed_20261102_BRA IND:seed_20261102_IND

`--historical` marks rounds as historical (kept, readable, pinnable; no reference to move forward from). Only the phases that ended `success` are kept.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from geofrea.core.deferred_check import DeferredCheck, load_checks, load_store
from geofrea.core.orchestrator import RunManifest

YAML = REPO / "config" / "deferred_checks.yaml"


def _data_dir() -> Path:
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("GEOFREA_DATA_DIR="):
            return Path(line.split("=", 1)[1].strip().strip('"'))
    raise SystemExit("GEOFREA_DATA_DIR is not set in .env")


def _evidence(iso: str, manifest: RunManifest, store, data: Path, note: str) -> tuple[dict, DeferredCheck | None]:
    check = load_checks(YAML, data).get(iso)
    if check is None:
        return {"deferred_check": None, "note": note}, None
    gate = DeferredCheck(check, Path(tempfile.mkdtemp()) / "deferred_check.json", store)
    messages = []
    for phase in check.phases:
        if phase in manifest.phases and manifest.phases[phase].status == "success":
            message = gate.after_phase(manifest, phase)
            if message:
                messages.append(message)
    report = json.loads(gate.report_path.read_text(encoding="utf-8")) if gate.report_path.is_file() else {"phases": {}}
    phases = report["phases"]
    return {
        "deferred_check": {
            "reference": check.baseline_label,
            "reference_run": check.reference_run,
            "verdicts": {p: v["verdict"] for p, v in phases.items()},
            "different_expected": {p: sorted(v.get("different_expected", {})) for p, v in phases.items() if v.get("different_expected")},
            "equivalent_by_tolerance": {p: sorted(v["different_equivalent"]) for p, v in phases.items() if v.get("different_equivalent")},
            "unexplained": {p: sorted(v["different_unexplained"]) for p, v in phases.items() if v.get("different_unexplained")},
            "messages": messages,
        },
        "note": note,
    }, gate


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("isos", nargs="+")
    parser.add_argument("--note", required=True)
    parser.add_argument("--historical", nargs="*", default=[], help="ISO:run_id of the rounds to mark as historical once the rounds are kept")
    args = parser.parse_args(argv)
    data = _data_dir()
    os.environ.setdefault("GEOFREA_DATA_DIR", str(data))  # the manifest paths resolve against it
    store = load_store(YAML, data)
    for iso in (i.upper() for i in args.isos):
        manifest_path = data / "outputs" / iso / "manifest.json"
        manifest = RunManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        evidence, gate = _evidence(iso, manifest, store, data, args.note)
        run_dir = store.publish_state(manifest, manifest_path, gate, evidence=evidence)
        index = store.index(iso, manifest.run_id)
        print(f"{iso}: round {manifest.run_id[:12]}... kept, {len(index['files'])} files, phases {sorted(index['phases'])}, not kept {index['not_kept_phases']}")
        if evidence["deferred_check"]:
            print("   check:", evidence["deferred_check"]["verdicts"])
        print("   at", run_dir)
    for item in args.historical:
        iso, run_id = item.split(":", 1)
        store.mark_historical(iso.upper(), run_id, args.note)
        print(f"{iso.upper()} {run_id}: marked historical")


if __name__ == "__main__":
    main()
