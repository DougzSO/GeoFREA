"""Keep the state a country has on disk as the reference of the store, after a gate over EVERY phase of the round (COMMAND 91, 137; D-core-051; OQ-080).

The pipeline does not move the reference by itself. This is the explicit act (the other is `python main.py --publish-reference`). For each country it:

1. compares every phase of the manifest that ended `success` with the reference round of the country (`references/latest.json`), none skipped and none taken
   from an earlier report: a settled verdict of an earlier round counts for nothing;
2. refuses (nothing written, exit 1) if a phase is DIFERENTE, or has no comparison (it is not in the reference) and is not named in `--allow-without-reference`.
   An entry of `expected` in `config/deferred_checks.yaml` pinned to the reference of now leaves the phase EXPLICADO_REVISAR, which passes;
3. keeps the round (the JSON artifacts and the rasters of `raster_phases`) with the summary of the verdicts in `index.json` (`evidence.gate`).

    python scripts/publish_reference.py PRT IND BRA --note "round 133"
    python scripts/publish_reference.py ZZZ --first --note "first reference"      # a country with no reference yet
    python scripts/publish_reference.py BRA --allow-without-reference overview --note "..."

`--historical` marks rounds as historical (kept, readable, pinnable; no reference to move forward from). Only the phases that ended `success` are kept.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from geofrea.core.deferred_check import PublicationRefused, load_store, publish_with_gate
from geofrea.core.orchestrator import RunManifest

YAML = REPO / "config" / "deferred_checks.yaml"


def _data_dir() -> Path:
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("GEOFREA_DATA_DIR="):
            return Path(line.split("=", 1)[1].strip().strip('"'))
    raise SystemExit("GEOFREA_DATA_DIR is not set in .env")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("isos", nargs="+")
    parser.add_argument("--note", required=True)
    parser.add_argument("--first", action="store_true", help="the country has no reference yet: every phase is without comparison and that is allowed (refused if a reference exists)")
    parser.add_argument("--allow-without-reference", default="", help="comma-separated phases that are new (not in the reference) and may be kept with no comparison")
    parser.add_argument("--historical", nargs="*", default=[], help="ISO:run_id of the rounds to mark as historical once the rounds are kept")
    args = parser.parse_args(argv)
    data = _data_dir()
    os.environ.setdefault("GEOFREA_DATA_DIR", str(data))  # the manifest paths resolve against it
    store = load_store(YAML, data)
    allowed = tuple(p for p in args.allow_without_reference.split(",") if p)
    failed = False
    for iso in (i.upper() for i in args.isos):
        manifest_path = data / "outputs" / iso / "manifest.json"
        manifest = RunManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        try:
            run_dir, gate = publish_with_gate(manifest, manifest_path, store, YAML, data, note=args.note, first=args.first, without_reference=allowed)
        except PublicationRefused as exc:
            print(f"{iso}: REFUSED: {exc}")
            print("   verdicts:", exc.summary["verdicts"])
            failed = True
            continue
        index = store.index(iso, manifest.run_id)
        print(f"{iso}: round {manifest.run_id[:12]}... kept, {len(index['files'])} files, phases {sorted(index['phases'])}, not kept {index['not_kept_phases']}")
        print("   gate against", gate.reference_run, "->", gate.summary()["counts"])
        print("   at", run_dir)
    if failed:
        return 1
    for item in args.historical:
        iso, run_id = item.split(":", 1)
        store.mark_historical(iso.upper(), run_id, args.note)
        print(f"{iso.upper()} {run_id}: marked historical")
    return 0


if __name__ == "__main__":
    sys.exit(main())
