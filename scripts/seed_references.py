"""Put the rasters and JSON files of a backup made by hand into the reference store as a named round (COMMAND 91; D-core-051).

The deferred check (`config/deferred_checks.yaml`) compares the rasters of a run with the files of a round of the reference store. The store is filled by
the pipeline each time a round is accepted; a country whose reference is a round that predates the store (IND and BRA: the outputs of 2026-11-02,
copied by hand to `backup_before_89`) is given that round once with this script, and pins it with `reference_run` in the yaml.

Usage:
    python scripts/seed_references.py BRA --run-id seed_20261102_BRA --from backup_before_89/BRA backup_before_89/BRA_siting --note "outputs of 2026-11-02"

The directories are relative to the data root. The round is kept at `references/<run-id>/<ISO>/`, marked `imported`, and is not `latest`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from geofrea.core.deferred_check import load_store


def _data_dir() -> Path:
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("GEOFREA_DATA_DIR="):
            return Path(line.split("=", 1)[1].strip().strip('"'))
    raise SystemExit("GEOFREA_DATA_DIR is not set in .env")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("iso")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--from", dest="sources", nargs="+", required=True, help="directories relative to the data root")
    parser.add_argument("--note", required=True, help="where the files come from")
    args = parser.parse_args(argv)
    data = _data_dir()
    store = load_store(REPO / "config" / "deferred_checks.yaml", data)
    if store.round_dir(args.iso, args.run_id).exists():
        raise SystemExit(f"round {args.run_id} of {args.iso.upper()} already exists in {store.root}")
    directories = [data / d for d in args.sources]
    missing = [str(d) for d in directories if not d.is_dir()]
    if missing:
        raise SystemExit(f"not a directory: {', '.join(missing)}")
    run_dir = store.import_directories(args.iso, args.run_id, directories, note=args.note)
    index = store.index(args.iso, args.run_id)
    print(f"{args.run_id}: {len(index['files'])} files kept in {run_dir}")


if __name__ == "__main__":
    main()
