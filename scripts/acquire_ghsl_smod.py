"""Download and extract GHS-SMOD R2023A (epoch 2020, 1 km, Mollweide) into `GEOFREA_DATA_DIR/external/ghsl/` (Group 6, COMMAND 97).

Run: `python scripts/acquire_ghsl_smod.py`. One global file of about 36 MB, no account. The archive and the raster are checked against the SHA-256 pinned in
`geofrea.data_acquisition.fetchers.ghsl`; a mismatch stops the script (A-09). Resumable: a present, verified archive is not downloaded again.
"""

from __future__ import annotations

import logging
import sys
import zipfile

import requests
from dotenv import load_dotenv

from geofrea.data_acquisition.fetchers import ghsl


def main() -> int:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger("acquire_ghsl_smod")
    target = ghsl.directory()
    target.mkdir(parents=True, exist_ok=True)
    archive = target / f"{ghsl.PRODUCT}.zip"
    if not archive.is_file():
        logger.info("downloading %s", ghsl.URL)
        with requests.get(ghsl.URL, stream=True, timeout=120) as response:
            response.raise_for_status()
            with open(archive, "wb") as handle:
                handle.writelines(response.iter_content(1 << 20))
    ghsl.verify_archive(archive)
    folder = target / ghsl.PRODUCT
    if not (folder / f"{ghsl.PRODUCT}.tif").is_file():
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(folder)
    ghsl.verify_raster(folder / f"{ghsl.PRODUCT}.tif")
    print(folder / f"{ghsl.PRODUCT}.tif")
    return 0


if __name__ == "__main__":
    sys.exit(main())