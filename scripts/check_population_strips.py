"""Measure the peak memory of the population warp for several window sizes and prove that the summed population does not depend on them (COMMAND 77, item 9).

usage: python scripts/check_population_strips.py [--window ISO LON0 LAT0 SIZE]... [--bytes 400000000 200000000 100000000 50000000] [--out file.json]

`reproject_to_grid(..., Resampling.sum)` reads the source in horizontal strips of at most `max_window_bytes`. For each window of a country and each size the warp
runs in its own process; the result is the content hash of the written raster, the peak working set of the process (`peak_wset`) and the CPU seconds.
The summed population per cell is unchanged by the strip size when the hashes are equal. The exit code is 0 only when they are.
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
DEFAULT_WINDOWS = (("PRT", -9.5, 37.0, 3.0), ("IND", 73.0, 20.0, 8.0))


def child(iso: str, lon0: float, lat0: float, size: float, max_bytes: int) -> int:
    sys.path.insert(0, str(REPO / "src"))
    os.environ.setdefault("GDAL_CACHEMAX", "64")
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
    import geopandas as gpd
    import psutil
    from rasterio.enums import Resampling
    from shapely.geometry import box

    from geofrea.core import paths as core_paths
    from geofrea.core.content_hash import content_hash
    from geofrea.grid_alignment.raster_alignment import reproject_to_grid
    from geofrea.grid_alignment.reference_grid import build_reference_grid

    data = core_paths.data_root()
    registry = json.loads((data / "outputs" / iso / "artifacts" / "layer_registry.json").read_text(encoding="utf-8"))
    paths = {layer["layer_name"]: layer["path"] for layer in registry["layers"]}
    borders = gpd.read_file(data / str(paths["borders"]).removeprefix("data:"))
    window = gpd.GeoDataFrame(geometry=[borders.geometry.union_all().intersection(box(lon0, lat0, lon0 + size, lat0 + size))], crs=borders.crs)
    grid = build_reference_grid(window, 0.01, nesting_pixels=5)
    source = data / str(paths["population"]).removeprefix("data:")
    with tempfile.TemporaryDirectory(prefix="pop_strips_") as tmp:
        c0, t0 = time.process_time(), time.perf_counter()
        reproject_to_grid(source, Path(tmp) / "pop.tif", grid, resampling=Resampling.sum, max_window_bytes=max_bytes)
        cpu, wall = time.process_time() - c0, time.perf_counter() - t0
        digest = content_hash(Path(tmp) / "pop.tif")
    peak = psutil.Process().memory_info()
    print("RESULT " + json.dumps({"hash": digest, "cpu_s": round(cpu, 2), "wall_s": round(wall, 2), "peak_mb": round(getattr(peak, "peak_wset", peak.rss) / 2**20), "grid_pixels": int(grid.height * grid.width)}))
    return 0


def run(window: tuple, max_bytes: int) -> dict:
    iso, lon0, lat0, size = window
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), CHILD, iso, str(lon0), str(lat0), str(size), str(max_bytes)], capture_output=True, text=True, check=False
    )
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT "):
            return json.loads(line[7:])
    raise RuntimeError(f"child failed (exit {proc.returncode}):\n{proc.stderr[-2000:]}")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == CHILD:
        return child(argv[1], float(argv[2]), float(argv[3]), float(argv[4]), int(argv[5]))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--window", nargs=4, action="append", metavar=("ISO", "LON0", "LAT0", "SIZE"))
    ap.add_argument("--bytes", nargs="+", type=int, default=[400_000_000, 200_000_000, 100_000_000, 50_000_000])
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    windows = [(w[0], float(w[1]), float(w[2]), float(w[3])) for w in args.window] if args.window else list(DEFAULT_WINDOWS)
    rows = {}
    for window in windows:
        runs = {str(b): run(window, b) for b in args.bytes}
        hashes = {r["hash"] for r in runs.values()}
        rows[f"{window[0]}@{window[1]},{window[2]},{window[3]}"] = {"runs": runs, "identical": len(hashes) == 1}
    result = {"windows": rows, "identical": all(r["identical"] for r in rows.values())}
    text = json.dumps(result, indent=1)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0 if result["identical"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
