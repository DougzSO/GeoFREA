"""Rewrite the code fingerprint of a phase after a change that only took modules out of its hashed set, only under proof (COMMAND 208A).

Dry run by default: for every phase and country given, it proves (or refuses) and prints the table; `--apply` writes the manifests, and only when every requested
phase of that country is proved and the tree the new fingerprint was computed on is committed. See `geofrea.core.code_rebaseline` for the proof (A to D).

    python scripts/rebaseline_code_fingerprint.py --countries PRT IND BRA                       # dry run, manifest.json
    python scripts/rebaseline_code_fingerprint.py --countries PRT IND BRA --scale 0p1deg        # dry run, manifest__0p1deg.json
    python scripts/rebaseline_code_fingerprint.py --countries PRT --apply                       # writes outputs/PRT/manifest.json

Exit status: 0 when every requested entry is proved or already current, 1 when any is refused (nothing is written for that country).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from geofrea.core import code_rebaseline as rb
from geofrea.core.paths import manifest_path
from geofrea.core.scale import SCALES, use_scale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--countries", nargs="+", required=True)
    parser.add_argument("--phases", nargs="+", default=sorted(rb.ENTRY_POINTS), help="phases with a declared entry point (default: all of them)")
    parser.add_argument("--scale", default="0p05deg", choices=sorted(SCALES), help="which manifest: manifest.json (0p05deg) or manifest__<scale>.json")
    parser.add_argument("--ref", default="main", help="the branch whose commits were in force when the phases ran")
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--refuse-dirty", action="store_true", help="refuse a manifest whose run had a dirty working tree")
    parser.add_argument("--allow-dirty-tree", action="store_true", help="with --apply: accept a new tree with uncommitted changes (the proof then names HEAD only)")
    parser.add_argument("--apply", action="store_true", help="write the manifests (default: dry run)")
    args = parser.parse_args(argv)
    unknown = [p for p in args.phases if p not in rb.ENTRY_POINTS]
    if unknown:
        parser.error(f"no entry point declared for {unknown}")
    failed = False
    with use_scale(args.scale):
        for iso in args.countries:
            path = manifest_path(iso)
            manifest = rb.load_manifest(path)
            proofs: list[rb.Proof] = []
            for phase in args.phases:
                try:
                    proof = rb.prove(args.repo, manifest, phase, ref=args.ref, refuse_dirty=args.refuse_dirty)
                except rb.RebaselineRefused as exc:
                    failed = True
                    print(f"REFUSED  {iso} {args.scale} {phase}: {exc}")
                    proofs = []
                    break
                proofs.append(proof)
                state = "current" if proof.already_current else "proved"
                commits = ", ".join(f"{e.label} {e.date} -> {e.commit[:10]}" for e in proof.executions)
                print(f"{state.upper():8s} {iso} {args.scale} {phase}: {proof.previous_fingerprint[:12]} -> {proof.new_fingerprint[:12]}  ({commits})")
                if not proof.already_current:
                    print(f"           entry {proof.entry_point}; reachable {proof.reachable_modules} modules, sha256 {proof.reachable_hash[:16]}")
                    print(f"           removed from the hashed set: {', '.join(proof.removed_modules) or '-'}; new tree {proof.new_commit[:10]}{' (dirty)' if proof.new_tree_dirty else ''}")
            if proofs and args.apply:
                try:
                    rb.apply(path, proofs, allow_dirty_tree=args.allow_dirty_tree)
                except rb.RebaselineRefused as exc:
                    failed = True
                    print(f"REFUSED  {iso} {args.scale}: {exc}")
                    continue
                print(f"WRITTEN  {path}")
            elif proofs:
                print(f"dry run  {path}: nothing written")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
