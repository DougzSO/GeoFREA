"""Run F2a of a sample country on two revisions and compare every aligned artifact by content hash (COMMAND 75; D-core-044).

usage: python scripts/check_aligned_equivalence.py --revision <git revision> [--sample PRT] [--out docs/_audit/aligned_equivalence_<sample>.json]

D-core-044 allows adopting the internal caches of an earlier revision (`scripts/adopt_aligned_cache_keys.py`) only when the refactor costs more
than 2 h of rebuild in one country, and then with an automatic equivalence check that runs both revisions on a sample and compares the results,
never by the operator's statement. This is that check for the aligned layers of F2a:

1. the tree of `--revision` (`main.py`, `config/`, `docs/`, `src/`) is extracted with `git archive` into a temporary directory;
2. F2a of the sample country runs there and in the current tree, each with its own `GEOFREA_DATA_DIR` (the raw data is shared through a directory
   junction, the interim caches and the outputs are not), so both start with no cache;
3. every artifact of `grid_alignment` in the two manifests is compared by canonical content hash (`core.content_hash`);
4. the result is written as JSON: the revisions, the code fingerprint of the aligned-layer caches on each, every hash and the verdict.

The adoption script refuses a country unless this file says `equal` for the current code. The exit code is 0 only when every artifact is equal.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

DEFAULT_PROOF_DIR = REPO / "docs" / "_audit"
PHASE = "grid_alignment"


def proof_path(sample: str, directory: Path = DEFAULT_PROOF_DIR) -> Path:
    return directory / f"aligned_equivalence_{sample}.json"


def compare_manifests(old: dict, new: dict, phase: str | tuple[str, ...] = PHASE) -> dict:
    """The artifacts of `phase` (one name or several) in two manifests compared by content hash (the byte hash where an entry has none)."""
    phases = (phase,) if isinstance(phase, str) else tuple(phase)
    keys = sorted(k for k, e in {**old["artifacts"], **new["artifacts"]}.items() if e["phase"] in phases)
    rows = {}
    for key in keys:
        a, b = old["artifacts"].get(key), new["artifacts"].get(key)
        ha = None if a is None else (a.get("content_sha256") or a["sha256"])
        hb = None if b is None else (b.get("content_sha256") or b["sha256"])
        rows[key] = {"old": ha, "new": hb, "equal": ha is not None and ha == hb}
    return {
        "artifacts": rows,
        "n_artifacts": len(rows),
        "n_equal": sum(r["equal"] for r in rows.values()),
        "equal": bool(rows) and all(r["equal"] for r in rows.values()),
    }


def _junction(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)


def _run_f2a(repo: Path, data_dir: Path, sample: str, real_raw: Path, phases: str = PHASE) -> dict:
    """The phases (F2a by default; a comma list runs in that order in one process) of `sample` in the tree `repo` with its own data directory; returns its manifest."""
    _junction(data_dir / "raw", real_raw)
    env = {**os.environ, "GEOFREA_DATA_DIR": str(data_dir), "PYTHONPATH": str(repo / "src")}
    done = subprocess.run(
        [sys.executable, "main.py", sample, "--phases", phases],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        raise RuntimeError(f"F2a of {sample} failed in {repo}:\n{done.stdout[-2000:]}\n{done.stderr[-2000:]}")
    return json.loads((data_dir / "outputs" / sample / "manifest.json").read_text(encoding="utf-8"))


def cache_code_at(tree_src: Path) -> str:
    from geofrea.core.cache_code import CACHE_CODE_ROOTS
    from geofrea.core.code_fingerprint import closure_fingerprint

    return closure_fingerprint(CACHE_CODE_ROOTS["aligned_layers"], tree_src / "geofrea")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--revision", required=True)
    parser.add_argument("--sample", default="PRT")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--phases",
        default=PHASE,
        help="comma list run in order in each tree (e.g. data_quality_audit,grid_alignment, to prove a cache shared between phases); the artifacts of all of them are compared",
    )
    args = parser.parse_args(argv)

    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")  # GEOFREA_DATA_DIR, as main.py reads it
    from geofrea.core import paths as core_paths

    real_raw = core_paths.data_root() / "raw"
    out = args.out or proof_path(args.sample)
    with tempfile.TemporaryDirectory(prefix="geofrea_equiv_") as tmp:
        tmp_path = Path(tmp)
        old_repo = tmp_path / "old_repo"
        old_repo.mkdir()
        tar = tmp_path / "old.tar"
        subprocess.run(
            ["git", "-C", str(REPO), "archive", "--format=tar", "-o", str(tar), args.revision, "main.py", "config", "docs", "src"],
            check=True,
        )
        subprocess.run(["tar", "-xf", str(tar), "-C", str(old_repo)], check=True)
        # the run records `git rev-parse HEAD`: the extracted tree needs a commit of its own (its content does not depend on it)
        git = ["git", "-C", str(old_repo), "-c", "user.name=equiv", "-c", "user.email=equiv@localhost"]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "add", "-A"], check=True, capture_output=True)
        subprocess.run([*git, "commit", "-q", "-m", f"tree of {args.revision}"], check=True, capture_output=True)
        try:
            old_manifest = _run_f2a(old_repo, tmp_path / "data_old", args.sample, real_raw, args.phases)
            new_manifest = _run_f2a(REPO, tmp_path / "data_new", args.sample, real_raw, args.phases)
        finally:
            # release the junctions before the temporary tree is removed: removing a junction must not touch the real raw data
            for data in ("data_old", "data_new"):
                link = tmp_path / data / "raw"
                if link.exists() or link.is_symlink():
                    os.rmdir(link) if os.name == "nt" else link.unlink()
        verdict = compare_manifests(old_manifest, new_manifest, tuple(args.phases.split(",")))
        verdict.update(
            {
                "sample": args.sample,
                "phase": args.phases,
                "old_revision": args.revision,
                "old_cache_code": cache_code_at(old_repo / "src"),
                "new_cache_code": cache_code_at(REPO / "src"),
            }
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(verdict, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{verdict['n_equal']} of {verdict['n_artifacts']} artifacts of {args.phases} equal on {args.sample}: {'equal' if verdict['equal'] else 'DIFFERENT'} -> {out}")
    return 0 if verdict["equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
