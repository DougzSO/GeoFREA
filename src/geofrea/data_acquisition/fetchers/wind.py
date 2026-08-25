"""Global Wind Atlas fetcher.

Verified live 2026-08-24 (see docs/DECISIONS.md same date): a plain
unauthenticated GET against a country-scoped API endpoint returns a
302 redirect to a CDN-hosted per-country GeoTIFF. Tested successfully
for both PRT and BRA — GeoFREA's two current countries — before this
module was written (not assumed).

Endpoint pattern discovered from a third-party R package's source
(optimal2050/globalwindatlas, gwa_get_wind_speed()), not guessed, then
independently confirmed with a live request. The wind-speed endpoint
is the one used here; `capacity-factor_IEC{1,2,3}` exists at the same
`/api/gis/country/{iso3}/...` root but is NOT fetched by this module —
explicitly out of scope for this stage (see module docstring on
single-path below).

Single-path, NOT multi-file — explicit instruction for this stage,
despite capacity-factor being available at the same URL pattern:
AuditInputs.wind_paths only ever inspects the first file
(data_quality_audit/schemas.py's own docstring), so adding a second
fetched file here would be dead weight until something downstream
actually reads more than one wind file — a future scope decision, not
this one. AcquiredLayer.paths therefore stays untouched; this fetcher
returns a single Path, same as MULTI_FILE_LAYER_NAMES already implies
("wind" is not in that set).
"""

from __future__ import annotations

import logging
from pathlib import Path

from geofrea.core.http_retry import get_with_retry

logger = logging.getLogger("geofrea.data_acquisition.fetchers.wind")

_DEFAULT_HEIGHT_M = 100


def fetch_wind(outputs_dir: Path, country_code: str, height_m: int = _DEFAULT_HEIGHT_M) -> Path | None:
    """Download the Global Wind Atlas wind-speed raster for one country.

    Args:
        outputs_dir: Root outputs directory (PhaseContext.outputs_dir).
        country_code: ISO-3166-alpha-3 code.
        height_m: Turbine hub height in meters (the API also supports
            10/50/150/200 — 100 matches this stage's verified example
            and is not otherwise parameterized elsewhere in GeoFREA
            today).

    Returns:
        Path to the saved GeoTIFF, or None if the fetch failed (logged,
        not raised).
    """
    dest_dir = Path(outputs_dir) / country_code / "raw"
    dest_path = dest_dir / f"{country_code}_wind_speed_{height_m}m.tif"

    if dest_path.exists():
        return dest_path

    url = f"https://globalwindatlas.info/api/gis/country/{country_code}/wind-speed/{height_m}"

    try:
        resp = get_with_retry(url, timeout=60)
    except Exception as exc:  # noqa: BLE001 — one bad fetch must not abort acquisition
        logger.warning("Failed to fetch wind speed for %s: %s", country_code, exc)
        return None

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(resp.content)
    logger.info("Wind speed raster saved: %s", dest_path)
    return dest_path
