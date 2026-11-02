"""Substation counts per country for the POI layer (COMMAND 84, OQ-067): total, by geometry, tagged, inferred, excluded, and how many pass V_th.

Reads the raw grid extract (lines) and the fetched substations (`scripts/fetch_osm_substations.py`); writes nothing under `database/raw`.
Usage: python scripts/report_poi_counts.py PRT [IND BRA]
Output: stdout and docs/_audit/poi_counts_84.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from geofrea.core.config_loader import load_parameters, load_settings
from geofrea.grid_alignment.poi import select_poi

MINIMUM = {
    "BRA": 500,
    "IND": 300,
}  # COMMAND 84, step 1: below these the layer is stopped and reported


def _env(key: str) -> Path:
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(key + "="):
            return Path(line.split("=", 1)[1].strip().strip('"'))
    raise SystemExit(f"{key} is not set in .env")


def main(isos):
    data = _env("GEOFREA_DATA_DIR")
    raw = _env("GEOFREA_SHARED_RAW_DIR")
    params = load_parameters(REPO / "config" / "parameters.json")
    geo = load_settings(REPO / "config" / "settings.yaml").geospatial
    rows, failed = [], []
    for iso in isos:
        threshold = params.countries[iso].connection.poi_voltage_threshold_kv.value
        lines = gpd.read_file(raw / "infrastructure" / "grid" / f"{iso}_grid_osm.geojson")
        lines = lines[lines["power"] != "substation"]
        subs = gpd.read_file(data / geo.poi_substations_geojson.format(iso=iso))
        grid = gpd.GeoDataFrame(
            pd.concat([lines, subs], ignore_index=True), geometry="geometry", crs=lines.crs
        )
        points, counts = select_poi(grid, threshold, geo.poi_line_tolerance_m)
        by_source = points["voltage_source"].value_counts().to_dict()
        c = counts.as_dict()
        rows.append((iso, threshold, c, by_source, len(subs)))
        print(iso, threshold, c, by_source, flush=True)
        if iso in MINIMUM and c["eligible"] < MINIMUM[iso]:
            failed.append(f"{iso}: {c['eligible']} eligible < {MINIMUM[iso]}")
    out = REPO / "docs" / "_audit" / "poi_counts_84.md"
    lines_md = [
        "# Substations of the POI layer by country (COMMAND 84, OQ-067)",
        "",
        "Source: OSM `power=substation` as nodes, ways and relations (Overpass, `scripts/fetch_osm_substations.py`); lines from the raw grid extract.",
        f"Tolerance for the voltage of a substation without a tag: {geo.poi_line_tolerance_m} m. A node inside a polygon is dropped; the point is the `representative_point`.",
        "",
        "| Country | V_th (kV) | Read | Nodes | Polygons | Duplicates dropped | With tag | Inferred | Excluded (no voltage) | Below V_th | Eligible (pass V_th) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for iso, th, c, _src, n_read in rows:
        lines_md.append(
            f"| {iso} | {th:g} | {n_read} | {c['nodes']} | {c['polygons']} | {c['duplicates_removed']} | {c['with_tag']} | "
            f"{c['inferred']} | {c['excluded_no_voltage']} | {c['below_threshold']} | {c['eligible']} |"
        )
    out.write_text("\n".join(lines_md) + "\n", encoding="utf-8")
    if failed:
        print("BELOW MINIMUM:", "; ".join(failed))
        sys.exit(3)


if __name__ == "__main__":
    main(sys.argv[1:] or ["PRT"])
