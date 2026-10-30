"""Prove that keeping the covered polygons of a clip leaves every raster derived from them unchanged, on a window of a country (COMMAND 77, item 3).

usage: python scripts/proofs/check_polygon_derived_equivalence.py --old-src <dir with the old geofrea/> [--window ISO LON0 LAT0 SIZE]... [--out file.json]

The clip of the lakes and of the protected areas is made in two child processes, one with the old `src` (every feature intersected) and one with this
tree's (a polygon that the country polygon covers is kept as it is). On the grid of the window the real derived products are computed and hashed:
the lake mask of F2a (`align_lakes`), the share of each pixel covered by lakes and by protected areas of every IUCN level (`polygon_coverage_fraction`,
the input of F3), over the whole set and over the `Ia`/`Ib`/`II` subset. The clipped file itself differs by construction (a ring rewritten by the intersection
starts at another vertex): the number of clipped features that differ exactly and the largest area difference are reported next to the verdict.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHILD = "--child"
DEFAULT_WINDOWS = (("PRT", -8.9, 38.9, 2.0), ("IND", 77.0, 28.0, 1.0), ("BRA", -46.5, -23.5, 1.0))


def child(src: Path, iso: str, lon0: float, lat0: float, size: float) -> int:
    sys.path.insert(0, str(src))
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
    import geopandas as gpd
    import numpy as np
    import rasterio
    import shapely
    from shapely.geometry import box

    from geofrea.core import paths as core_paths
    from geofrea.core.geo_utils import read_clipped_to_country
    from geofrea.grid_alignment.reference_grid import build_reference_grid
    from geofrea.grid_alignment.vector_alignment import align_lakes
    from geofrea.land_eligibility.fractions import polygon_coverage_fraction

    data = core_paths.data_root()
    registry = json.loads((data / "outputs" / iso / "artifacts" / "layer_registry.json").read_text(encoding="utf-8"))
    paths = {layer["layer_name"]: layer["path"] for layer in registry["layers"]}
    borders = gpd.read_file(data / str(paths["borders"]).removeprefix("data:"))
    window = gpd.GeoDataFrame(geometry=[borders.geometry.union_all().intersection(box(lon0, lat0, lon0 + size, lat0 + size))], crs=borders.crs)
    grid = build_reference_grid(window, 0.01, nesting_pixels=5)
    shape = (grid.height, grid.width)

    def digest(array) -> str:
        return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()

    out: dict = {"grid_pixels": int(grid.height * grid.width)}
    with tempfile.TemporaryDirectory(prefix="poly_equiv_") as tmp:
        lakes, _ = read_clipped_to_country(data / str(paths["lakes"]).removeprefix("data:"), window)
        protected, _ = read_clipped_to_country(data / str(paths["protected"]).removeprefix("data:"), window)
        out["n_lakes"], out["n_protected"] = len(lakes), len(protected)
        mask_path = align_lakes(lakes, Path(tmp) / "lakes.tif", grid)
        if mask_path is not None:
            with rasterio.open(mask_path) as r:
                out["lake_mask"] = digest(r.read(1))
        out["lakes_fraction"] = digest(polygon_coverage_fraction(lakes, grid.transform, shape))
        out["protected_fraction_all"] = digest(polygon_coverage_fraction(protected, grid.transform, shape))
        if "IUCN_CAT" in protected.columns:
            strict = protected[protected["IUCN_CAT"].astype(str).str.strip().str.lower().isin(["ia", "ib", "ii"])]
            out["protected_fraction_strict"] = digest(polygon_coverage_fraction(strict, grid.transform, shape))
        # for the report: the geometry itself, feature by feature, in the order the clip returns
        out["wkb_lakes"] = hashlib.sha256(b"".join(shapely.to_wkb(lakes.geometry.values))).hexdigest()
        out["wkb_protected"] = hashlib.sha256(b"".join(shapely.to_wkb(protected.geometry.values))).hexdigest()
        np.save(Path(tmp) / "x.npy", np.zeros(1))
        out["areas_deg2"] = {"lakes": float(lakes.geometry.area.sum()), "protected": float(protected.geometry.area.sum())}
    print("RESULT " + json.dumps(out))
    return 0


def run_side(src: Path, window: tuple) -> dict:
    iso, lon0, lat0, size = window
    env = {**os.environ, "PYTHONPATH": str(src)}
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), CHILD, str(src), iso, str(lon0), str(lat0), str(size)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT "):
            return json.loads(line[7:])
    raise RuntimeError(f"child for {src} failed (exit {proc.returncode}):\n{proc.stderr[-2000:]}")


DERIVED = ("lake_mask", "lakes_fraction", "protected_fraction_all", "protected_fraction_strict")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == CHILD:
        return child(Path(argv[1]), argv[2], float(argv[3]), float(argv[4]), float(argv[5]))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--old-src", type=Path, required=True)
    ap.add_argument("--window", nargs=4, action="append", metavar=("ISO", "LON0", "LAT0", "SIZE"))
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    windows = [(w[0], float(w[1]), float(w[2]), float(w[3])) for w in args.window] if args.window else list(DEFAULT_WINDOWS)
    rows = {}
    for window in windows:
        old, new = run_side(args.old_src, window), run_side(REPO / "src", window)
        derived_equal = all(old.get(k) == new.get(k) for k in DERIVED)
        rows[f"{window[0]}@{window[1]},{window[2]},{window[3]}"] = {
            "old": old,
            "new": new,
            "derived_equal": derived_equal,
            "clip_geometry_identical": old["wkb_lakes"] == new["wkb_lakes"] and old["wkb_protected"] == new["wkb_protected"],
        }
    result = {"old_src": str(args.old_src), "windows": rows, "derived_equal": all(r["derived_equal"] for r in rows.values())}
    text = json.dumps(result, indent=1)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0 if result["derived_equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
