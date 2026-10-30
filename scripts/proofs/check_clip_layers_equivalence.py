"""Prove that the clip of whole layers of a country is unchanged by the current code (COMMAND 79, step 3).

usage: python scripts/check_clip_layers_equivalence.py ISO --old layer=path.gpkg [--old layer=path.gpkg ...] [--out file.json]

Each layer named is clipped from its source in the layer registry with this tree's `read_clipped_to_country` and compared with the clip made before
(`--old`): the clip is written to a GeoPackage and read back as the pipeline stores it; the same rows in the same order, the same attributes, and every geometry equal with `equals_exact` at tolerance 0. Nothing is written but the JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("iso")
    ap.add_argument("--old", action="append", required=True, metavar="LAYER=PATH")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    sys.path.insert(0, str(REPO / "src"))
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
    import geopandas as gpd
    import shapely

    from geofrea.core import paths as core_paths
    from geofrea.core.geo_utils import load_mainland_boundary, read_clipped_to_country

    data = core_paths.data_root()
    registry = json.loads((data / "outputs" / args.iso / "artifacts" / "layer_registry.json").read_text(encoding="utf-8"))
    source = {layer["layer_name"]: data / str(layer["path"]).removeprefix("data:") for layer in registry["layers"]}
    country = load_mainland_boundary(source["borders"])  # the polygon the phases clip with: the contiguous territory
    rows = {}
    for spec in args.old:
        layer, _, old_path = spec.partition("=")
        new, _ = read_clipped_to_country(source[layer], country)
        with tempfile.TemporaryDirectory(prefix="clip_equiv_") as tmp:  # the stored clip is a GeoPackage, whose layer type promotes Polygon to MultiPolygon
            new.to_file(Path(tmp) / "new.gpkg", driver="GPKG")
            new = gpd.read_file(Path(tmp) / "new.gpkg")
        old = gpd.read_file(old_path)
        row = {"n_old": len(old), "n_new": len(new)}
        if len(old) == len(new):
            geometry_equal = shapely.equals_exact(old.geometry.values, new.geometry.values, tolerance=0.0)
            row["geometries_differ"] = int((~geometry_equal).sum())
            columns = [c for c in old.columns if c != "geometry"]
            row["same_columns"] = columns == [c for c in new.columns if c != "geometry"]
            row["attributes_equal"] = bool(row["same_columns"] and old[columns].reset_index(drop=True).equals(new[columns].reset_index(drop=True)))
            row["equal"] = row["geometries_differ"] == 0 and row["attributes_equal"]
        else:
            row["equal"] = False
        rows[layer] = row
        print(args.iso, layer, json.dumps(row), flush=True)
        del new, old
    result = {"iso": args.iso, "old": args.old, "layers": rows, "equal": all(r["equal"] for r in rows.values())}
    if args.out:
        args.out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("EQUAL" if result["equal"] else "DIFFERENT")
    return 0 if result["equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
