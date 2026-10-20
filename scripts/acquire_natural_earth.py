"""Download the Natural Earth 50 m country borders, used only to draw the neighbouring countries on the maps (COMMAND 60).

Public domain (naturalearthdata.com). The files go to `GEOFREA_DATA_DIR/raw/natural_earth/_global/` with the sha256 of the zip in
`manifest.json`; nothing else reads them. Run: `python scripts/acquire_natural_earth.py`. Resumable: a file already there is kept.
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from datetime import UTC, datetime

import requests

from geofrea.core import paths

URL = "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip"
STEM = "ne_50m_admin_0_countries"


def main() -> int:
    dest = paths.fetched_raw("natural_earth", "_global")
    dest.mkdir(parents=True, exist_ok=True)
    shp = dest / f"{STEM}.shp"
    if shp.is_file():
        print(f"{shp} already there")
        return 0
    archive = dest / f"{STEM}.zip"
    response = requests.get(URL, timeout=120)
    response.raise_for_status()
    archive.write_bytes(response.content)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(dest)
    manifest = {
        "source": "Natural Earth 1:50m Admin 0 - Countries (public domain)",
        "url": URL,
        "downloaded_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "zip_sha256": hashlib.sha256(response.content).hexdigest(),
        "use": "neighbouring countries on the maps (viz/mapstyle.py); no result reads it",
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    print(f"{len(response.content)} bytes -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
