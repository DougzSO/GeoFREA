"""Adopt the aligned layers of a country under the current code instead of computing them again (COMMAND 75).

usage: python scripts/adopt_aligned_cache_keys.py <ISO3> --revision <git revision> [--proof docs/_audit/proofs_75_77/aligned_equivalence_PRT.json] [--check]

Every aligned layer of F2a has a cache key that holds the fingerprint of the code of `grid_alignment` (`cache_code("aligned_layers")`, A-02).
A change of that code gives another key, so the next run computes every layer again: for BRA that is about 42,000 s. COMMAND 75 changed the code
of F2a (the elevation, the slope and the slope bins come from one pass over the GLO-30 tiles) with outputs that are the same by content hash
(PRT, `docs/_audit/performance_75.md`); the other layers were not touched. This script records that equivalence for a country whose layers were
made under the code of `--revision` instead of making them again:

0. it reads the proof of equivalence written by `scripts/proofs/check_aligned_equivalence.py` (F2a of a sample country run on `--revision` and on the
   current tree, every aligned artifact compared by content hash) and stops unless it says `equal` for exactly these two code fingerprints:
   D-core-044 allows an adoption only after an automatic check of both revisions on a sample, never by the operator's statement;
1. it computes the cache fingerprint of `grid_alignment` on the source of `--revision` (the revision the layers were made with);
2. it runs the phase `grid_alignment` of the country as `main.py` does, with the key of every layer computed under that old fingerprint, so
   that every layer is found current and none is computed (a layer that would be computed stops the run before it starts: nothing is lost);
3. it writes, beside each `<layer>_aligned.tif`, the key of the current code in place of the old one (a copy of the old file is kept as
   `<layer>_aligned.tif.cachekey.before_adopt`).

It does not touch an aligned raster. The manifest entry of the phase is written by the run in step 2, with the current code fingerprint.
Use it only when the outputs of the changed code are known to equal the earlier ones; a layer of a changed algorithm must be computed again.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

CACHE_NAME = "aligned_layers"


class AdoptionError(RuntimeError):
    """A layer would be computed again, or the old fingerprint is not the one the layers were made with."""


def require_proof(proof: dict, old_code: str, new_code: str) -> None:
    """Stop unless `proof` (the file of `check_aligned_equivalence.py`) says that the aligned layers of the two code fingerprints are equal."""
    if not proof.get("equal"):
        raise AdoptionError(
            f"the equivalence check found {proof.get('n_equal')} of {proof.get('n_artifacts')} aligned artifacts equal on {proof.get('sample')}: no adoption"
        )
    if proof.get("old_cache_code") != old_code or proof.get("new_cache_code") != new_code:
        raise AdoptionError(
            "the equivalence check was made for other code (its fingerprints are not those of --revision and of the current tree): run "
            "scripts/proofs/check_aligned_equivalence.py again"
        )


def cache_code_at(revision: str) -> str:
    """The fingerprint of the code of the aligned-layer caches on the `src/geofrea` tree of a git revision."""
    from geofrea.core.cache_code import CACHE_CODE_ROOTS
    from geofrea.core.code_fingerprint import closure_fingerprint

    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "src.tar"
        subprocess.run(
            ["git", "-C", str(REPO), "archive", "--format=tar", "-o", str(archive), revision, "src/geofrea"],
            check=True,
        )
        subprocess.run(["tar", "-xf", str(archive), "-C", tmp], check=True)
        return closure_fingerprint(CACHE_CODE_ROOTS[CACHE_NAME], Path(tmp) / "src" / "geofrea")


@contextmanager
def pinned_to(old_code: str) -> Iterator[dict[str, str]]:
    """Inside the block the aligned-layer keys are computed under `old_code`; yields the map `old key -> key of the current code`.

    A layer that exists with a key that is not the old one raises `AdoptionError` (it would be computed again).
    """
    from geofrea.core.cache_key import cache_is_current as real_is_current
    from geofrea.core.cache_key import cache_key
    from geofrea.grid_alignment import alignment

    real_key = alignment.aligned_layer_key
    recorded: dict[str, str] = {}

    def old_key(files, config, hash_memo):
        new = real_key(files, config, hash_memo)
        old = cache_key(alignment.ALIGNMENT_ALGORITHM_VERSION, files, config, hash_memo, code=old_code)
        recorded[old] = new
        return old

    def must_be_current(output, key):
        current = real_is_current(output, key)
        if not current and Path(output).exists():
            raise AdoptionError(
                f"{Path(output).name} was not made under the code of the revision (its key is not the old one): adopting would "
                "compute it again. Nothing was written."
            )
        return current

    alignment.aligned_layer_key, alignment.cache_is_current = old_key, must_be_current
    try:
        yield recorded
    finally:
        alignment.aligned_layer_key, alignment.cache_is_current = real_key, real_is_current


def rewrite_sidecars(artifacts: Path, recorded: dict[str, str]) -> list[str]:
    """Replace the old key by the key of the current code in every `*_aligned.tif.cachekey` of `artifacts` whose key was recorded."""
    done = []
    for sidecar in sorted(Path(artifacts).glob("*_aligned.tif.cachekey")):
        old = sidecar.read_text(encoding="utf-8").strip()
        if old in recorded:
            shutil.copy2(sidecar, sidecar.with_name(sidecar.name + ".before_adopt"))
            sidecar.write_text(recorded[old], encoding="utf-8")
            done.append(sidecar.name)
    return done


def restore_before_adopt(artifacts: Path) -> list[str]:
    """Put back the key a sidecar had before an earlier adoption (the `.before_adopt` copy), so that adopting again, under newer code, starts from the
    key of the revision the layers were made with. A sidecar without that copy is left as it is."""
    restored = []
    for backup in sorted(Path(artifacts).glob("*_aligned.tif.cachekey.before_adopt")):
        sidecar = backup.with_name(backup.name.removesuffix(".before_adopt"))
        shutil.copy2(backup, sidecar)
        restored.append(sidecar.name)
    return restored


def phase_arguments(iso: str) -> list[str]:
    """The command line of the run that adopts: F2a is named in `--rerun`, so it executes even when its manifest entry is current. Without it a
    country whose F2a already ran under the current code would resume, no layer key would be computed and the sidecars put back by
    `restore_before_adopt` would stay on the old key (COMMAND 81)."""
    return [iso, "--phases", "grid_alignment", "--rerun", "grid_alignment"]


def adopt(run: Callable[[], object], old_code: str, artifacts: Path) -> list[str]:
    """Run `run` (the phase) with the keys pinned to `old_code`, then write the keys of the current code; returns the sidecars rewritten."""
    with pinned_to(old_code) as recorded:
        run()
    return rewrite_sidecars(artifacts, recorded)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("iso", help="country code")
    parser.add_argument("--revision", required=True, help="git revision of the code the aligned layers were made with")
    parser.add_argument(
        "--proof",
        type=Path,
        default=REPO / "docs" / "_audit" / "proofs_75_77" / "aligned_equivalence_PRT.json",
        help="result of scripts/proofs/check_aligned_equivalence.py (default: the PRT sample)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="resolve --revision, compute its cache code and check the proof against it and the current code; adopt nothing and run nothing",
    )
    args = parser.parse_args(argv)

    import main as pipeline
    from geofrea.core import paths as core_paths

    old_code = cache_code_at(args.revision)
    from geofrea.core.cache_code import cache_code

    require_proof(json.loads(args.proof.read_text(encoding="utf-8")), old_code, cache_code(CACHE_NAME))
    artifacts = core_paths.phase_dir(args.iso, "grid_alignment", "artifacts")
    print(f"aligned-layer cache code at {args.revision}: {old_code[:12]}")
    if args.check:
        print(f"check only: the proof matches {args.revision} ({old_code[:12]}) and the current code ({cache_code(CACHE_NAME)[:12]}); nothing adopted, no phase run")
        return 0
    restored = restore_before_adopt(artifacts)
    if restored:
        print(f"{len(restored)} sidecars put back to the key of {args.revision} (an earlier adoption under other code)")

    def run_phase() -> None:
        code = pipeline.main(phase_arguments(args.iso))
        if code not in (0, None):
            raise AdoptionError(f"main.py returned {code}")

    adopted = adopt(run_phase, old_code, artifacts)
    print(f"{len(adopted)} aligned layers adopted under the current code:", ", ".join(adopted))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
