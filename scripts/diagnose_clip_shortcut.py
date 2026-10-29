"""Read-only diagnosis of the covered-line clip shortcut (COMMAND 79, step 1).

usage: python scripts/diagnose_clip_shortcut.py ISO [--layers roads rivers lakes protected] [--out file.json]

For each layer the features the shortcut would keep (lines wholly covered by the simplified country polygon) are also intersected the exact way, and
the two geometries are compared with `equals_exact` at tolerance 0. The features that differ are counted by the type of the original geometry and by
properties that can make GEOS rewrite a line (self-touching, repeated points, a closed ring, several parts). Nothing is written but the JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAX_SAMPLE = 150_000
TYPE_NAMES = {1: "LineString", 2: "LinearRing", 5: "MultiLineString"}


def has_repeated_points(geoms) -> "list[bool]":
    import shapely

    out = []
    for g in geoms:
        parts = list(g.geoms) if g.geom_type == "MultiLineString" else [g]
        flag = False
        for p in parts:
            c = shapely.get_coordinates(p)
            if len(c) > 1 and (c[1:] == c[:-1]).all(axis=1).any():
                flag = True
                break
        out.append(flag)
    return out


def diagnose(iso: str, layer: str, paths: dict, country_gdf) -> dict:
    import geopandas as gpd
    import numpy as np
    import pyogrio
    import shapely

    from geofrea.core.geo_utils import (
        _simplify_for_intersection,
        country_union,
        repair_invalid_geometries,
    )

    path = paths[layer]
    crs = pyogrio.read_info(str(path))["crs"]
    cin = country_gdf.to_crs(crs) if crs else country_gdf
    gdf = gpd.read_file(str(path), bbox=tuple(cin.total_bounds), columns=[])
    gdf, _ = repair_invalid_geometries(gdf)
    simplified, _ = _simplify_for_intersection(country_union(cin), gdf.crs)
    minx, miny, maxx, maxy = cin.total_bounds
    pre = gdf.cx[minx:maxx, miny:maxy]
    tree = shapely.STRtree(pre.geometry.values)
    geoms = pre.geometry.values[tree.query(simplified, predicate="intersects")]
    tid = shapely.get_type_id(geoms)
    lines = np.isin(tid, (1, 2, 5))
    shapely.prepare(simplified)
    covered = np.zeros(len(geoms), dtype=bool)
    covered[lines] = shapely.covers(simplified, geoms[lines])
    idx = np.where(covered)[0]
    n_covered = len(idx)
    if len(idx) > MAX_SAMPLE:  # roads and rivers: a fixed-seed sample keeps the exact intersection affordable
        idx = np.sort(np.random.default_rng(79).choice(idx, MAX_SAMPLE, replace=False))
    original = geoms[idx]
    if len(idx):
        with ThreadPoolExecutor(max_workers=8) as pool:
            exact = np.concatenate(list(pool.map(lambda c: shapely.intersection(c, simplified), np.array_split(original, 64))))
    else:
        exact = original
    same = shapely.equals_exact(original, exact, tolerance=0)
    res = {
        "n_matched": int(len(geoms)),
        "n_lines": int(lines.sum()),
        "n_covered": int(n_covered),
        "n_checked": int(len(idx)),
        "n_differ": int((~same).sum()),
        "by_original_type": {},
    }
    otype = shapely.get_type_id(original)
    for t, name in TYPE_NAMES.items():
        sel = otype == t
        if not sel.any():
            continue
        d = ~same & sel
        row = {"covered": int(sel.sum()), "differ": int(d.sum())}
        if d.any():
            dg, eg = original[d], exact[d]
            row["differ_not_simple"] = int((~shapely.is_simple(dg)).sum())
            row["differ_repeated_points"] = int(sum(has_repeated_points(dg)))
            row["differ_closed"] = int(shapely.is_closed(dg).sum()) if t != 5 else None
            row["differ_exact_becomes"] = {TYPE_NAMES.get(k, str(k)): int((shapely.get_type_id(eg) == k).sum()) for k in np.unique(shapely.get_type_id(eg))}
            row["differ_fewer_vertices"] = int((shapely.get_num_coordinates(eg) < shapely.get_num_coordinates(dg)).sum())
            row["differ_same_normalized"] = int(shapely.equals_exact(shapely.normalize(dg), shapely.normalize(eg), tolerance=0).sum())
        if (~same & sel).any():
            ok = same & sel
            row["identical_not_simple"] = int((~shapely.is_simple(original[ok])).sum())
        res["by_original_type"][name] = row
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("iso")
    ap.add_argument("--layers", nargs="+", default=["protected", "roads", "rivers", "lakes"])
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    sys.path.insert(0, str(REPO / "src"))
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
    import geopandas as gpd

    from geofrea.core import paths as core_paths

    data = core_paths.data_root()
    registry = json.loads((data / "outputs" / args.iso / "artifacts" / "layer_registry.json").read_text(encoding="utf-8"))
    layer_paths = {layer["layer_name"]: data / str(layer["path"]).removeprefix("data:") for layer in registry["layers"]}
    country = gpd.read_file(layer_paths["borders"])
    result = {}
    for layer in args.layers:
        result[layer] = diagnose(args.iso, layer, layer_paths, country)
        print(args.iso, layer, json.dumps(result[layer]), flush=True)
    if args.out:
        args.out.write_text(json.dumps({"iso": args.iso, "layers": result}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
