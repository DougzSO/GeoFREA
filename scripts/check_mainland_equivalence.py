"""Prove that the contiguous-territory cache and the union memo give the same geometry as the code they replace (COMMAND 77, item 4).

usage: python scripts/check_mainland_equivalence.py --old-src <dir with the old geofrea/> [--samples PRT IND BRA] [--out file.json]

For each country the borders file of the shared data root is read and `load_mainland_boundary` runs in child processes: the old `src` (no cache),
this tree's `src` with an empty cache directory (cold: computed and written) and again with the file in place (warm: read back). The three WKB
hashes of the resulting geometry must be equal, as must the hash of the union that the clip computes (`country_union` against `union_all`).
Nothing is written in the shared data root: the child sets `GEOFREA_DATA_DIR` to a temporary directory that holds only the cache.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHILD = "--child"


def child(src: Path, sample: str, real_root: Path) -> int:
    sys.path.insert(0, str(src))
    import geopandas as gpd

    from geofrea.core.geo_utils import load_mainland_boundary

    registry = json.loads((real_root / "outputs" / sample / "artifacts" / "layer_registry.json").read_text(encoding="utf-8"))
    borders = next(layer["path"] for layer in registry["layers"] if layer["layer_name"] == "borders")
    path = real_root / str(borders).removeprefix("data:")
    t0, c0 = time.perf_counter(), time.process_time()
    mainland = load_mainland_boundary(path)
    cpu = time.process_time() - c0
    wall = time.perf_counter() - t0
    out = {"mainland_sha256": hashlib.sha256(mainland.geometry.iloc[0].wkb).hexdigest(), "wall_s": round(wall, 2), "cpu_s": round(cpu, 2)}
    gdf = gpd.read_file(path)
    try:
        from geofrea.core.geometry_memo import country_union

        union = country_union(gdf)
    except ImportError:
        union = gdf.geometry.union_all()
    out["union_sha256"] = hashlib.sha256(union.wkb).hexdigest()
    print("RESULT " + json.dumps(out))
    return 0


def run_side(src: Path, sample: str, real_root: Path, data_dir: Path) -> dict:
    env = {**os.environ, "PYTHONPATH": str(src), "GEOFREA_DATA_DIR": str(data_dir)}
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), CHILD, str(src), sample, str(real_root)], capture_output=True, text=True, env=env, check=False
    )
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT "):
            return json.loads(line[7:])
    raise RuntimeError(f"child for {src} failed (exit {proc.returncode}):\n{proc.stderr[-2000:]}")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == CHILD:
        return child(Path(argv[1]), argv[2], Path(argv[3]))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--old-src", type=Path, required=True)
    ap.add_argument("--samples", nargs="+", default=["PRT", "IND", "BRA"])
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
    real_root = Path(os.environ["GEOFREA_DATA_DIR"])
    rows = {}
    for sample in args.samples:
        with tempfile.TemporaryDirectory(prefix="mainland_equiv_") as tmp:
            old = run_side(args.old_src, sample, real_root, Path(tmp) / "old")
            cold = run_side(REPO / "src", sample, real_root, Path(tmp) / "new")
            warm = run_side(REPO / "src", sample, real_root, Path(tmp) / "new")
        equal = old["mainland_sha256"] == cold["mainland_sha256"] == warm["mainland_sha256"] and old["union_sha256"] == cold["union_sha256"]
        rows[sample] = {"old": old, "new_cold": cold, "new_warm": warm, "equal": equal}
    result = {"old_src": str(args.old_src), "samples": rows, "equal": all(r["equal"] for r in rows.values())}
    text = json.dumps(result, indent=1)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0 if result["equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
