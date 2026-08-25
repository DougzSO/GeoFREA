"""Protected Planet (WDPA) fetcher — implemented, NOT activated.

Verified live 2026-08-24/25 (see docs/DECISIONS.md same dates): unlike
what geoworld_framework's own README claimed ("no public bulk API"),
a real API exists at api.protectedplanet.net (v3 archived, v4
current) — confirmed by an unauthenticated request returning
`{"error": "Unauthorized. Invalid or expired token."}`, not a 404.
It requires a personal API token obtained through a manual request
form (no self-service signup), and it is genuinely NOT a bulk/global
download even with a token: results are paginated (max 50/page) and
filtered per country, not a single-file dump.

`protected`'s provenance in _LAYER_REGISTRY (phase.py) STAYS
"local_only" after this stage — this fetcher is complete and testable,
but not wired into run_acquisition_phase(). The only thing blocking
activation is a manual, one-time step external to this codebase (a
human getting a token from UNEP-WCMC) — see docs/DECISIONS.md
2026-08-25 for the activation checklist. This is the one fetcher in
this stage that is not just "not automatable" but "automatable, just
gated behind a human action GeoFREA cannot script."

Response schema NOT independently verified against a live authenticated
response — this session has no API token. Field names below
(`protected_areas`, `geojson`, `iucn_category`, `wdpa_id`) come from
api.protectedplanet.net/documentation/v3's published examples, not
from an actual authenticated call. Flagged explicitly: re-verify
against a real response the first time this fetcher is actually run
with a token, before trusting its output blindly.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from geofrea.core.http_retry import get_with_retry

logger = logging.getLogger("geofrea.data_acquisition.fetchers.protected_planet")

TOKEN_ENV_VAR = "PROTECTED_PLANET_API_TOKEN"
REGISTRATION_URL = "https://api.protectedplanet.net/request"

_BASE_URL = "https://api.protectedplanet.net/v4"
_PER_PAGE = 50  # documented maximum


class ProtectedPlanetTokenMissingError(RuntimeError):
    """Raised when PROTECTED_PLANET_API_TOKEN is not set in the environment."""


def _require_token(api_token: str | None) -> str:
    token = api_token or os.environ.get(TOKEN_ENV_VAR)
    if not token:
        raise ProtectedPlanetTokenMissingError(
            f"{TOKEN_ENV_VAR} is not set. Protected Planet requires a personal "
            f"API token — register at {REGISTRATION_URL} to request one, then "
            f"set {TOKEN_ENV_VAR} in the environment. Note: the API is "
            "paginated (max 50 results/page) and queried per country — it is "
            "not a bulk/global download, even once you have a token."
        )
    return token


def fetch_protected_areas(
    outputs_dir: Path, country_code: str, *, api_token: str | None = None
) -> Path | None:
    """Download all WDPA protected areas for one country via the Protected Planet API.

    Paginates through /v4/protected_areas/search?country={iso3} until a
    short page (fewer than _PER_PAGE results) is returned — the API
    documentation does not publish a total-pages/total-count field
    (confirmed absent from the published examples), so this is the
    standard REST short-page termination heuristic, not a verified
    contract. Assembles all features into a single GeoJSON
    FeatureCollection on disk, gpd.read_file()-able like every other
    vector layer AuditInputs consumes.

    Each feature's IUCN category is written under the property key
    `IUCN_CAT` (not the API's own `iucn_category` key) — a deliberate
    normalization so vector_inspection.py's existing column-detection
    list (IUCN_CAT/iucn_cat/IUCN/DESIGNATION) finds it without any
    change to that module. This fetcher fully controls the GeoJSON it
    writes, so this rename happens once, here, rather than needing a
    5th column-name variant added downstream.

    Args:
        outputs_dir: Root outputs directory (PhaseContext.outputs_dir).
        country_code: ISO-3166-alpha-3 code.
        api_token: Explicit token, or None to read PROTECTED_PLANET_API_TOKEN
            from the environment.

    Returns:
        Path to the saved GeoJSON, or None if the fetch failed after
        the token was successfully resolved (logged, not raised).

    Raises:
        ProtectedPlanetTokenMissingError: If no token is available —
            this is a configuration problem, not a transient failure,
            so it raises rather than degrading to None like a network
            error would.
    """
    token = _require_token(api_token)

    features: list[dict[str, Any]] = []
    page = 1

    try:
        while True:
            resp = get_with_retry(
                f"{_BASE_URL}/protected_areas/search",
                params={
                    "token": token,
                    "country": country_code,
                    "with_geometry": "true",
                    "per_page": _PER_PAGE,
                    "page": page,
                },
                timeout=60,
            )
            data = resp.json()
            protected_areas = data.get("protected_areas", [])

            for pa in protected_areas:
                geojson_feature = pa.get("geojson")
                if not geojson_feature or not geojson_feature.get("geometry"):
                    continue
                properties = dict(geojson_feature.get("properties") or {})
                properties["IUCN_CAT"] = pa.get("iucn_category")
                properties["wdpa_id"] = pa.get("wdpa_id")
                properties["name"] = pa.get("name")
                features.append(
                    {
                        "type": "Feature",
                        "geometry": geojson_feature["geometry"],
                        "properties": properties,
                    }
                )

            if len(protected_areas) < _PER_PAGE:
                break
            page += 1

    except Exception as exc:  # noqa: BLE001 — one bad fetch must not abort acquisition
        logger.warning("Failed to fetch protected areas for %s: %s", country_code, exc)
        return None

    dest_dir = Path(outputs_dir) / country_code / "raw"
    dest_path = dest_dir / f"{country_code}_protected_areas_wdpa.geojson"
    dest_dir.mkdir(parents=True, exist_ok=True)

    feature_collection = {"type": "FeatureCollection", "features": features}
    dest_path.write_text(json.dumps(feature_collection), encoding="utf-8")

    logger.info("Protected areas saved: %s (%d features)", dest_path, len(features))
    return dest_path
