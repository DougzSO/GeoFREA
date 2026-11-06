"""Fetch the FABDEM tiles of each configured country by HTTP Range (COMMAND 101, D-F2a-028).

Run: `python scripts/acquire_fabdem.py [ISO3 ...] [--max-gb 40] [--workers 3] [--dry-run]` (default PRT IND BRA).

The tiles are those whose footprint intersects the GADM mainland polygon of the country (the set GLO-30 uses). The volume is read first from the zip directories (no tile is
fetched) and the run stops if it passes `--max-gb`. Tiles go to `GEOFREA_DATA_DIR/external/fabdem/` with `fabdem_manifest.json` and the licence text (CC BY-NC-SA 4.0).
Interrupted runs continue: a tile at its name with the recorded size is kept, the others are fetched again from their zip.
"""

from __future__ import annotations

import argparse
import logging
import sys

import geopandas as gpd
from dotenv import load_dotenv

from geofrea.core import paths as core_paths
from geofrea.data_acquisition.fetchers import fabdem


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("countries", nargs="*", default=["PRT", "IND", "BRA"])
    parser.add_argument("--max-gb", type=float, default=40.0, help="stop, fetching nothing, if the missing tiles cost more than this (default 40)")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true", help="only estimate the volume")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    tiles: list[str] = []
    for iso in args.countries:
        boundary = gpd.read_file(core_paths.fetched_raw("gadm", iso) / f"gadm41_{iso}_0_mainland.shp")
        names = fabdem.tiles_for(boundary)
        print(f"{iso}: {len(names)} tiles")
        tiles += names
    tiles = list(dict.fromkeys(tiles))
    estimate = fabdem.estimate_bytes(tiles)
    gb = estimate["bytes"] / 1e9
    print(f"to fetch: {estimate['tiles']} tiles, {gb:.2f} GB; not in the dataset (GLO-30 fallback): {estimate['absent'] or 'none'}")
    if gb > args.max_gb:
        print(f"STOP: {gb:.1f} GB is over the limit of {args.max_gb:g} GB; nothing was fetched", file=sys.stderr)
        return 2
    if args.dry_run:
        return 0
    dest = fabdem.fetch_tiles(tiles, workers=args.workers)
    print("done:", dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
