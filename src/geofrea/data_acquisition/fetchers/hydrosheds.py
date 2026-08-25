"""HydroSHEDS fetcher — HydroLAKES and HydroRIVERS.

One module for both layers because they are the same source (HydroSHEDS,
data.hydrosheds.org) — the point of organizing fetchers by source, not
by layer or by auth pattern (see docs/DECISIONS.md 2026-08-25 "real
fetchers for power_plants/wind/lakes/rivers", its "Por que fetch por
FONTE" section). Both verified live 2026-08-24/25, no auth, no
registration.

HydroLAKES vs. HydroRIVERS delivery — NOT symmetric, confirmed live,
not assumed:
  - HydroRIVERS is split into 9 regional/continental tiles (af, ar, as,
    au, eu, gr, na, sa, si) — confirmed working for `eu` (67.6 MB,
    covers PRT) and `sa` (95.3 MB, covers BRA). Using tiles instead of
    the 618 MB global file is this stage's explicit instruction, given
    GeoFREA's current 2-country scope.
  - HydroLAKES has NO regional tiles — confirmed by testing the same
    URL pattern HydroRIVERS uses (404 in every case) and by the
    product page itself presenting only a single global file. Per
    Douglas's explicit decision (2026-08-25, asked live during this
    stage rather than assumed): `lakes` fetches the single 820 MB
    global file — there is no smaller alternative, unlike `rivers`.

Region mapping (HydroRIVERS only) is inherent to the SOURCE's own
tiling scheme (continent-based, not country-based) — not a GeoFREA
invention. _COUNTRY_TO_REGION only covers GeoFREA's current 2
countries (PRT, BRA); adding a new country requires adding its region
code here (see the 9 codes in the module docstring above) — flagged
explicitly rather than silently limited, since a KeyError on an
unmapped country is intentional (see fetch_rivers()'s docstring).
"""

from __future__ import annotations

import logging
from pathlib import Path

from geofrea.core.http_retry import get_with_retry

logger = logging.getLogger("geofrea.data_acquisition.fetchers.hydrosheds")

_LAKES_GLOBAL_URL = "https://data.hydrosheds.org/file/hydrolakes/HydroLAKES_polys_v10_shp.zip"

_RIVERS_TILE_URL_TEMPLATE = (
    "https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_{region}_shp.zip"
)

# HydroRIVERS' own 9 continental tile codes (af, ar, as, au, eu, gr,
# na, sa, si) mapped to GeoFREA's current countries only. Extend this
# when a new country is added — see module docstring.
_COUNTRY_TO_REGION: dict[str, str] = {
    "PRT": "eu",  # Europe and Middle East
    "BRA": "sa",  # South America
}


def fetch_lakes(outputs_dir: Path) -> Path | None:
    """Download the HydroLAKES global shapefile (820 MB), once.

    Global dataset (country_specific=False in _LAYER_REGISTRY,
    unchanged by this stage) — saved once under `_global/`, not
    per-country. No regional-tile alternative exists (confirmed live,
    see module docstring) — this is deliberately the full global file.

    Args:
        outputs_dir: Root outputs directory (PhaseContext.outputs_dir).

    Returns:
        Path to the saved ZIP, or None if the fetch failed (logged,
        not raised).
    """
    dest_dir = Path(outputs_dir) / "_global" / "raw"
    dest_path = dest_dir / "HydroLAKES_polys_v10_shp.zip"

    if dest_path.exists():
        return dest_path

    try:
        resp = get_with_retry(_LAKES_GLOBAL_URL, timeout=300)
    except Exception as exc:  # noqa: BLE001 — one bad fetch must not abort acquisition
        logger.warning("Failed to fetch HydroLAKES: %s", exc)
        return None

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(resp.content)
    logger.info("HydroLAKES saved: %s", dest_path)
    return dest_path


def fetch_rivers(outputs_dir: Path, country_code: str) -> Path | None:
    """Download the HydroRIVERS regional tile covering one country.

    Args:
        outputs_dir: Root outputs directory (PhaseContext.outputs_dir).
        country_code: ISO-3166-alpha-3 code. Must be a key in
            _COUNTRY_TO_REGION — an unmapped country is a configuration
            gap to fix (add the region code), not a runtime condition
            to handle gracefully, so this raises KeyError rather than
            silently returning None like the network-failure path
            below does.

    Returns:
        Path to the saved regional-tile ZIP, or None if the fetch
        failed (logged, not raised).

    Raises:
        KeyError: If country_code is not in _COUNTRY_TO_REGION.
    """
    region = _COUNTRY_TO_REGION[country_code]

    dest_dir = Path(outputs_dir) / country_code / "raw"
    dest_path = dest_dir / f"HydroRIVERS_v10_{region}_shp.zip"

    if dest_path.exists():
        return dest_path

    url = _RIVERS_TILE_URL_TEMPLATE.format(region=region)

    try:
        resp = get_with_retry(url, timeout=180)
    except Exception as exc:  # noqa: BLE001 — one bad fetch must not abort acquisition
        logger.warning("Failed to fetch HydroRIVERS tile '%s' for %s: %s", region, country_code, exc)
        return None

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(resp.content)
    logger.info("HydroRIVERS tile '%s' saved: %s", region, dest_path)
    return dest_path
