"""Prove that a change of `core.geo_utils` leaves the clip of a country unchanged, by content hash (COMMAND 77, items 1a and 3).

usage: python scripts/check_clip_equivalence.py --old-src <dir with the old geofrea/> [--sample PRT] [--layers roads rivers lakes] [--out file.json]

The same `read_clipped_to_country` runs in two child processes, one with the `src` of the old revision and one with the `src` of this tree, on the
raw layers of `--sample` (read from the shared data root, nothing is written there). Each child prints one sha256 per layer, over every feature in
order: its geometry as WKB (so coordinates, ring starts and part order all count) and its attributes. The two lists must be equal. The result goes to
JSON with the feature counts, the CPU seconds of each side and the verdict; the exit code is 0 only when every layer is equal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHILD = "--child"


def child(src: Path, sample: str, layers: list[str]) -> int:
    sys.path.insert(0, str(src))
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
    load_dotenv(REPO.parent / "GeoFREA" / ".env")
    import geopandas as gpd
    import shapely

    from geofrea.core import paths as core_paths
    from geofrea.core.geo_utils import read_clipped_to_country

    data = core_paths.data_root()
    registry = json.loads((data / "outputs" / sample / "artifacts" / "layer_registry.json").read_text(encoding="utf-8"))
    paths = {layer["layer_name"]: layer["path"] for layer in registry["layers"]}
    borders = gpd.read_file(data / str(paths["borders"]).removeprefix("data:"))
    out = {}
    for name in layers:
        t0, c0 = time.perf_counter(), time.process_time()
        clipped, _ = read_clipped_to_country(data / str(paths[name]).removeprefix("data:"), borders)
        wall, cpu = time.perf_counter() - t0, time.process_time() - c0
        h = hashlib.sha256()
        wkb = shapely.to_wkb(clipped.geometry.values)
        attrs = clipped.drop(columns=clipped.geometry.name).to_numpy(dtype=object)
        for i in range(len(clipped)):
            h.update(wkb[i] if wkb[i] is not None else b"")
            h.update("".join(repr(v) for v in attrs[i]).encode("utf-8"))
            h.update(b"\x1e")
        out[name] = {"sha256": h.hexdigest(), "n_features": len(clipped), "wall_s": round(wall, 2), "cpu_s": round(cpu, 2)}
    print("RESULT " + json.dumps(out))
    return 0


def run_side(src: Path, sample: str, layers: list[str]) -> dict:
    env = {**os.environ, "PYTHONPATH": str(src)}
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), CHILD, str(src), sample, *layers], capture_output=True, text=True, env=env, check=False
    )
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT "):
            return json.loads(line[7:])
    raise RuntimeError(f"child for {src} failed (exit {proc.returncode}):\n{proc.stderr[-2000:]}")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == CHILD:
        return child(Path(argv[1]), argv[2], argv[3:])
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--old-src", type=Path, required=True)
    ap.add_argument("--sample", default="PRT")
    ap.add_argument("--layers", nargs="+", default=["roads", "rivers", "lakes"])
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    old = run_side(args.old_src, args.sample, args.layers)
    new = run_side(REPO / "src", args.sample, args.layers)
    rows = {
        name: {"old": old[name], "new": new[name], "equal": old[name]["sha256"] == new[name]["sha256"] and old[name]["n_features"] == new[name]["n_features"]}
        for name in args.layers
    }
    result = {"sample": args.sample, "old_src": str(args.old_src), "layers": rows, "equal": all(r["equal"] for r in rows.values())}
    text = json.dumps(result, indent=1)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0 if result["equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
