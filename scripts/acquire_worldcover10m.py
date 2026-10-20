"""Download the 10 m ESA WorldCover tiles for IND, with the same tile names as the local 100 m set (D-F2a-017).

Run: `python scripts/acquire_worldcover10m.py [ISO3 ...]` (default IND). Public AWS bucket, no account, about 100 MB per
3 degree tile. Resumable: finished tiles are skipped. The local tile list is read from the country's land-cover directory.
"""

from __future__ import annotations

import logging
import sys

import geopandas as gpd
from dotenv import load_dotenv

from geofrea.core import paths as core_paths
from geofrea.data_acquisition import local_layers
from geofrea.data_acquisition.fetchers import esa_worldcover
from geofrea.data_acquisition.fetchers.gadm import fetch_borders


def main(argv: list[str]) -> int:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for iso in argv or ["IND"]:
        mask = (
            gpd.read_file(fetch_borders(core_paths.outputs_dir(), iso))
            .to_crs("EPSG:4326")
            .geometry.union_all()
        )
        wanted = set(esa_worldcover.tiles_for_mask(mask))
        local = {p.name for p in local_layers.resolve_land_cover_tiles(iso)}
        # the tiles of the mask, plus the ones the local set already names (they stay pinned); a tile that the bucket lacks is recorded as absent
        names = sorted(wanted | local)
        print(
            iso,
            f"{len(wanted - local)} tiles of the mask are not in the local set:",
            sorted(wanted - local),
        )
        print(iso, esa_worldcover.fetch_country(iso, names))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
