"""Prove that a change in a raster step of F2a leaves its output unchanged, by content hash, on a window of a country (COMMAND 77, items 8 and 9).

usage: python scripts/check_raster_step_equivalence.py --old-src <dir with the old geofrea/> --step {glo30|population} [--window ISO LON0 LAT0 SIZE]... [--out file.json]

The real function of the step runs in two child processes, one with the `src` of the old revision and one with this tree's, on the same grid built over a
`size`-degree window of the country (the borders cut to the box, 0.01 degree, as F2a builds it), and every raster it writes is hashed with
`core.content_hash` (the hash the manifest keeps): glo30 -> elevation, slope and slope bins; population -> the summed population. Each side reports its CPU
seconds and the number of file opens. The exit code is 0 only when every hash is equal.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHILD = "--child"
DEFAULT_WINDOWS = (("PRT", -8.9, 38.9, 1.0), ("IND", 77.0, 28.0, 1.0))


def child(src: Path, step: str, iso: str, lon0: float, lat0: float, size: float) -> int:
    sys.path.insert(0, str(src))
    os.environ.setdefault("GDAL_CACHEMAX", "64")
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
    import geopandas as gpd
    import rasterio
    from shapely.geometry import box

    from geofrea.core import paths as core_paths
    from geofrea.core.content_hash import content_hash
    from geofrea.data_acquisition.fetchers import copernicus_dem30
    from geofrea.grid_alignment.raster_alignment import glo30_aligned_outputs, reproject_to_grid
    from geofrea.grid_alignment.reference_grid import build_reference_grid

    data = core_paths.data_root()
    registry = json.loads((data / "outputs" / iso / "artifacts" / "layer_registry.json").read_text(encoding="utf-8"))
    paths = {layer["layer_name"]: layer["path"] for layer in registry["layers"]}
    borders = gpd.read_file(data / str(paths["borders"]).removeprefix("data:"))
    window = gpd.GeoDataFrame(geometry=[borders.geometry.union_all().intersection(box(lon0, lat0, lon0 + size, lat0 + size))], crs=borders.crs)
    grid = build_reference_grid(window, 0.01, nesting_pixels=5)

    opens = {"n": 0}
    real_open = rasterio.open

    def counting(*a, **k):
        opens["n"] += 1
        return real_open(*a, **k)

    rasterio.open = counting
    hashes = {}
    with tempfile.TemporaryDirectory(prefix="step_equiv_") as tmp:
        tmp_path = Path(tmp)
        c0, t0 = time.process_time(), time.perf_counter()
        if step == "glo30":
            tiles = list(copernicus_dem30.load_tiles(iso))
            out = glo30_aligned_outputs(
                tiles, grid, elevation_out=tmp_path / "e.tif", slope_out=tmp_path / "s.tif", counts_out=tmp_path / "c.tif"
            )
            written = {k: v for k, v in out.items() if v is not None}
        else:
            from rasterio.enums import Resampling

            source = data / str(paths["population"]).removeprefix("data:")
            reproject_to_grid(source, tmp_path / "pop.tif", grid, resampling=Resampling.sum)
            written = {"population": tmp_path / "pop.tif"}
        cpu, wall = time.process_time() - c0, time.perf_counter() - t0
        for name, path in written.items():
            hashes[name] = content_hash(Path(path))
    print("RESULT " + json.dumps({"hashes": hashes, "cpu_s": round(cpu, 2), "wall_s": round(wall, 2), "opens": opens["n"], "grid_pixels": int(grid.height * grid.width)}))
    return 0


def run_side(src: Path, step: str, window: tuple) -> dict:
    iso, lon0, lat0, size = window
    env = {**os.environ, "PYTHONPATH": str(src)}
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), CHILD, str(src), step, iso, str(lon0), str(lat0), str(size)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT "):
            return json.loads(line[7:])
    raise RuntimeError(f"child for {src} failed (exit {proc.returncode}):\n{proc.stderr[-2000:]}")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == CHILD:
        return child(Path(argv[1]), argv[2], argv[3], float(argv[4]), float(argv[5]), float(argv[6]))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--old-src", type=Path, required=True)
    ap.add_argument("--step", choices=("glo30", "population"), required=True)
    ap.add_argument("--window", nargs=4, action="append", metavar=("ISO", "LON0", "LAT0", "SIZE"))
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    windows = [(w[0], float(w[1]), float(w[2]), float(w[3])) for w in args.window] if args.window else list(DEFAULT_WINDOWS)
    rows = {}
    for window in windows:
        old = run_side(args.old_src, args.step, window)
        new = run_side(REPO / "src", args.step, window)
        rows[f"{window[0]}@{window[1]},{window[2]},{window[3]}"] = {"old": old, "new": new, "equal": old["hashes"] == new["hashes"] and bool(new["hashes"])}
    result = {"step": args.step, "old_src": str(args.old_src), "windows": rows, "equal": all(r["equal"] for r in rows.values())}
    text = json.dumps(result, indent=1)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0 if result["equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
