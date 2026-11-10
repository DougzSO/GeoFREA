"""Rewrite the config fingerprint of phases whose scope gained keys, only under proof (COMMAND 127, item 5c).

Dry run by default: for every phase the change names and every country given, it proves (or refuses) and prints the table; `--apply` writes the manifests,
and only when every requested phase of that country is proved. See `geofrea.core.config_rebaseline` for the proof (A, B and C).

    python scripts/rebaseline_config_fingerprint.py --change scope-127-f2a-f3 --countries PRT IND BRA            # dry run
    python scripts/rebaseline_config_fingerprint.py --change scope-127-f2a-f3 --countries PRT --apply          # writes outputs/PRT/manifest.json

Exit status: 0 when every requested entry is proved or already current, 1 when any is refused (nothing is written for that country).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from geofrea.core import config_rebaseline as rb
from geofrea.core.config_fingerprint import CONFIG_FILES, DiskConfigSource
from geofrea.core.paths import manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--change", required=True, choices=sorted(rb.SCOPE_CHANGES))
    parser.add_argument("--countries", nargs="+", required=True)
    parser.add_argument("--phases", nargs="+", help="a subset of the phases the change names (default: all of them)")
    parser.add_argument("--ref", default="main", help="the branch whose commits were in force when the phases ran")
    parser.add_argument("--repo", type=Path, default=REPO, help="the git repository whose history holds the config (default: this one)")
    parser.add_argument("--config-dir", type=Path, default=REPO / "config")
    parser.add_argument("--manifest", type=Path, help="a manifest file (only with one country); default outputs/<ISO>/manifest.json")
    parser.add_argument("--refuse-dirty", action="store_true", help="refuse a manifest whose run had a dirty working tree (the real ones all do)")
    parser.add_argument("--apply", action="store_true", help="write the manifests (default: dry run)")
    args = parser.parse_args(argv)
    if args.manifest and len(args.countries) != 1:
        parser.error("--manifest takes exactly one country")

    change = rb.SCOPE_CHANGES[args.change]
    phases = args.phases or sorted(change.additions)
    unknown = [p for p in phases if p not in change.additions]
    if unknown:
        parser.error(f"{args.change} does not change the scope of {unknown}")
    current = DiskConfigSource(
        {key: args.config_dir / name for key, name in CONFIG_FILES.items()}, args.config_dir / "turbines"
    )
    failed = False
    for iso in args.countries:
        path = args.manifest or manifest_path(iso)
        manifest = rb.load_manifest(path)
        proofs: list[rb.Proof] = []
        for phase in phases:
            try:
                proof = rb.prove(args.repo, manifest, phase, change, current, ref=args.ref, refuse_dirty=args.refuse_dirty)
            except rb.RebaselineRefused as exc:
                failed = True
                print(f"REFUSED  {iso} {phase}: {exc}")
                proofs = []
                break
            proofs.append(proof)
            state = "current" if proof.already_current else "proved"
            commits = ", ".join(f"{e.label} {e.date} -> {e.commit[:10]}" for e in proof.executions)
            print(f"{state.upper():8s} {iso} {phase}: {proof.previous_fingerprint[:12]} -> {proof.new_fingerprint[:12]}  ({commits})")
            for key in proof.keys:
                print(f"           {key.file}:{key.selector} = {key.value_now}")
        if proofs and args.apply:
            rb.apply(path, proofs)
            print(f"WRITTEN  {path}")
        elif proofs:
            print(f"dry run  {path}: nothing written")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
