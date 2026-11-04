"""Fetch the OSM substations (nodes, ways and relations) of a country from Overpass (COMMAND 84, OQ-067).

The raw grid extracts hold substations as points only, so the point-of-interconnection layer cannot be carried by them. This script asks Overpass
for `power=substation` as nodes, closed ways and multipolygon relations and writes a GeoJSON beside the other external inputs, never under
`database/raw`. A closed way becomes a Polygon, a relation the polygons of its outer rings (holes from the inner rings), a node a Point.

Usage: python scripts/fetch_osm_substations.py PRT [IND BRA]
Output: GEOFREA_DATA_DIR/external/osm_substations/<ISO>_substations_osm.geojson (+ a .json sidecar with query, date and counts)
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import requests
from shapely.geometry import MultiPolygon, Point, Polygon, mapping
from shapely.ops import polygonize, unary_union

ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
QUERY = '[out:json][timeout:900];area["ISO3166-1:alpha3"="{iso}"]->.a;nwr["power"="substation"](area.a);out geom tags;'


def _data_dir() -> Path:
    for line in (
        (Path(__file__).resolve().parents[1] / ".env").read_text(encoding="utf-8").splitlines()
    ):
        if line.startswith("GEOFREA_DATA_DIR="):
            return Path(line.split("=", 1)[1].strip().strip('"'))
    raise SystemExit("GEOFREA_DATA_DIR is not set in .env")


def _ring(geometry):
    return [(p["lon"], p["lat"]) for p in geometry]


def _relation_geometry(element):
    """Polygons from the outer rings of a multipolygon relation, with the inner rings as holes; None if no ring closes."""
    outer, inner = [], []
    for member in element.get("members", []):
        if member.get("type") != "way" or "geometry" not in member:
            continue
        (inner if member.get("role") == "inner" else outer).append(_ring(member["geometry"]))
    from shapely.geometry import LineString

    def rings(parts):
        lines = [LineString(p) for p in parts if len(p) >= 2]
        return list(polygonize(unary_union(lines))) if lines else []

    shells = rings(outer)
    if not shells:
        return None
    holes = unary_union(rings(inner)) if inner else None
    merged = unary_union(shells)
    return merged.difference(holes) if holes is not None and not holes.is_empty else merged


def feature(element):
    tags = element.get("tags", {})
    kind = element["type"]
    if kind == "node":
        geom = Point(element["lon"], element["lat"])
    elif kind == "way":
        ring = _ring(element.get("geometry", []))
        if len(ring) >= 4 and ring[0] == ring[-1]:
            geom = Polygon(ring)
        elif ring:
            return None  # an open way is a line, not an area
        else:
            return None
    else:
        geom = _relation_geometry(element)
    if geom is None or geom.is_empty:
        return None
    if not geom.is_valid:
        geom = geom.buffer(0)
    if not isinstance(geom, (Point, Polygon, MultiPolygon)):
        return None
    props = {"osm_type": kind, "osm_id": element["id"], "power": "substation", **tags}
    return {"type": "Feature", "properties": props, "geometry": mapping(geom)}


def fetch(iso: str) -> dict:
    query = QUERY.format(iso=iso)
    last = None
    for attempt in range(6):
        url = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            response = requests.post(
                url,
                data={"data": query},
                headers={"User-Agent": "GeoFREA-thesis/1.0 (research; dogaosilva322@gmail.com)"},
                timeout=1000,
            )
            if response.status_code == 200:
                return response.json()
            last = f"{url}: HTTP {response.status_code}"
        except requests.RequestException as error:
            last = f"{url}: {error}"
        print(f"  attempt {attempt + 1} failed ({last}); waiting", flush=True)
        time.sleep(30 * (attempt + 1))
    raise SystemExit(f"Overpass failed for {iso}: {last}")


def main(isos):
    out_dir = _data_dir() / "external" / "osm_substations"
    out_dir.mkdir(parents=True, exist_ok=True)
    for iso in isos:
        print(f"{iso}: querying Overpass", flush=True)
        payload = fetch(iso)
        elements = payload.get("elements", [])
        features, dropped = [], 0
        for element in elements:
            f = feature(element)
            if f is None:
                dropped += 1
            else:
                features.append(f)
        counts = {
            "elements": len(elements),
            "kept": len(features),
            "dropped_open_or_empty": dropped,
        }
        for kind in ("node", "way", "relation"):
            counts[kind] = sum(1 for f in features if f["properties"]["osm_type"] == kind)
        path = out_dir / f"{iso}_substations_osm.geojson"
        path.write_text(
            json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8"
        )
        sidecar = {
            "iso": iso,
            "query": QUERY.format(iso=iso),
            "fetched": datetime.now(tz=UTC).date().isoformat(),
            "osm_base": payload.get("osm3s", {}).get("timestamp_osm_base"),
            "counts": counts,
        }
        path.with_suffix(".json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        print(f"{iso}: {counts} -> {path}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or ["PRT"])
