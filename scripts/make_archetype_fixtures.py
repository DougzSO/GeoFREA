"""Build the small geometry fixtures of the country archetypes of the figure tests (spec v2, T-13).

usage: python scripts/make_archetype_fixtures.py
Reads (never writes) `GEOFREA_DATA_DIR/raw`: the GADM 4.1 level-0 mainland files of the countries that have them (PRT, BRA) and the Natural
Earth 1:50m countries (`raw/natural_earth/_global`) for the others and for the neighbours. Writes `tests/fixtures/archetypes/<ISO3>.geojson`:
the country (`role` = country) and its neighbours within 2.5 degrees (`role` = neighbour), simplified, 4 decimals. The geometry is real
and illustrative; the data drawn on it in the tests are synthetic. Re-run only to change the archetypes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import geopandas as gpd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from geofrea.viz.mapstyle import NEIGHBOUR_BUFFER_DEG

DATA = Path(os.environ.get("GEOFREA_DATA_DIR", "D:/Douglas/DOUTORADO/GeoFREA_data")) / "raw"
NE = DATA / "natural_earth" / "_global" / "ne_50m_admin_0_countries.shp"
OUT = REPO / "tests" / "fixtures" / "archetypes"

# ISO3: (shape, source, simplification tolerance in degrees)
ARCHETYPES = {
    "PRT": ("tall and narrow", "gadm", 0.004),
    "CHL": ("very tall and narrow", "ne", 0.02),
    "BRA": ("wide", "gadm", 0.03),
    "CHE": ("compact", "ne", 0.005),
    "IDN": ("fragmented", "ne", 0.05),
    "LUX": ("tiny", "ne", 0.003),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ne = gpd.read_file(NE).to_crs("EPSG:4326")
    for iso, (shape, source, tolerance) in ARCHETYPES.items():
        if source == "gadm":
            country = gpd.read_file(DATA / "gadm" / iso / f"gadm41_{iso}_0_mainland.shp").to_crs(
                "EPSG:4326"
            )
        else:
            country = ne[ne["ADM0_A3"] == iso][["geometry"]]
        geom = country.geometry.union_all()
        ring = geom.buffer(NEIGHBOUR_BUFFER_DEG)
        others = ne[(ne["ADM0_A3"] != iso) & ne.intersects(ring)].copy()
        others["geometry"] = others.geometry.intersection(
            geom.buffer(NEIGHBOUR_BUFFER_DEG + 0.1)
        ).difference(geom)
        others = others[~others.is_empty]
        frame = gpd.GeoDataFrame(
            {
                "role": ["country"] + ["neighbour"] * len(others),
                "shape": [shape] * (1 + len(others)),
            },
            geometry=[geom.simplify(tolerance, preserve_topology=True)]
            + [g.simplify(0.05, preserve_topology=True) for g in others.geometry],
            crs="EPSG:4326",
        )
        path = OUT / f"{iso}.geojson"
        frame.to_file(path, driver="GeoJSON", COORDINATE_PRECISION=4)
        print(iso, shape, f"{path.stat().st_size / 1024:.0f} kB", len(others), "neighbours")


if __name__ == "__main__":
    main()
