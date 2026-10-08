"""Download the 10 m ESA WorldCover tiles for IND, with the same tile names as the local 100 m set (D-F2a-017).

Run: `python scripts/acquire_worldcover10m.py [ISO3 ...]` (default IND). Public AWS bucket, no account, about 100 MB per
3 degree tile. Resumable: finished tiles are skipped. The local tile list is read from the country's land-cover directory.
"""

from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv

from geofrea.data_acquisition import local_layers
from geofrea.data_acquisition.fetchers import esa_worldcover


def main(argv: list[str]) -> int:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for iso in argv or ["IND"]:
        names = sorted({p.name for p in local_layers.resolve_land_cover_tiles(iso)})
        if not names:
            raise SystemExit(f"{iso}: no local land-cover tiles to take the tile names from")
        print(iso, esa_worldcover.fetch_country(iso, names))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
