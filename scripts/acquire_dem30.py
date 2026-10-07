"""Download the Copernicus DEM GLO-30 tiles (30 m) for each configured country (D-F2a-016).

Run: `python scripts/acquire_dem30.py [ISO3 ...]` (default: every country with a GADM mainland polygon and a GEM name, i.e. PRT IND BRA).
Public AWS bucket, no account; about 42 MB per 1 degree tile. Resumable: finished tiles are skipped.
"""

from __future__ import annotations

import logging
import sys

import geopandas as gpd
from dotenv import load_dotenv

from geofrea.core import paths as core_paths
from geofrea.data_acquisition.fetchers import copernicus_dem30


def main(argv: list[str]) -> int:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for iso in argv or ["PRT", "IND", "BRA"]:
        boundary = gpd.read_file(core_paths.fetched_raw("gadm", iso) / f"gadm41_{iso}_0_mainland.shp")
        out = copernicus_dem30.fetch_country(iso, boundary)
        print(iso, out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
