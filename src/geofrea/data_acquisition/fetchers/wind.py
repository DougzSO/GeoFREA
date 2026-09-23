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

M-F1-03 (implemented 2026-09-23, task F1-2): fetch_gwa_product() below
generalizes the same verified endpoint pattern to the other three GWA
products (combined-Weibull-A, combined-Weibull-k, air-density) at all
three hub-relevant heights (100/150/200 m) — probed live against PRT
before implementing (all 12 product/height combinations return 200
with a real GeoTIFF; see docs/phases/F1_data_acquisition.md). Kept
deliberately separate from fetch_wind() above rather than rewriting it
in terms of the new function: fetch_wind() feeds the single "wind"
registry entry that grid_alignment/suitability_criteria already
consume as GeoFREA's actual wind resource layer, and its existing
soft-fail contract (returns None, never raises — see
tests/unit/test_fetchers_wind.py) is relied on by every other fetcher
in phase.py's _FETCHED_LAYER_HANDLERS. fetch_gwa_product() instead
raises on failure, per M-F1-03's explicit requirement that a missing
product fail loud (A-09) rather than be registered as silently absent
— phase.py's per-layer isolation already turns a raised exception into
that one layer's own resolution_status="failed" without aborting
others, so "raise" here is the correct contract, not an oversight.
"""

from __future__ import annotations

import logging
from pathlib import Path

from geofrea.core import paths
from geofrea.core.http_retry import get_with_retry

logger = logging.getLogger("geofrea.data_acquisition.fetchers.wind")

_DEFAULT_HEIGHT_M = 100

# Internal layer-name key -> Global Wind Atlas URL slug. M-F1-03's four
# products. "wind_speed" here is the same product fetch_wind() above
# already fetches at 100 m (for the "wind" registry entry) — this dict
# lets fetch_gwa_product() also fetch it at 150/200 m under its own
# distinct registry entries (M-F1-03 requires all three heights for
# every product, not just wind-speed).
GWA_PRODUCTS: dict[str, str] = {
    "wind_speed": "wind-speed",
    "weibull_a": "combined-Weibull-A",
    "weibull_k": "combined-Weibull-k",
    "air_density": "air-density",
}

# M-F1-03's three hub-relevant heights.
GWA_HEIGHTS_M: tuple[int, ...] = (100, 150, 200)


class GwaProductNotFoundError(RuntimeError):
    """A GWA product/height combination could not be fetched.

    Raised when the CDN response after the redirect is not a
    successful download — the real failure mode observed live: a
    missing product/height combination still 302-redirects to a CDN
    URL, but that URL then answers with an S3-style 403 "AccessDenied"
    XML body, not a 404 on the API itself. get_with_retry() ->
    request_with_retry() already calls resp.raise_for_status() against
    that FINAL response (core/http_retry.py) — this wraps the resulting
    requests.HTTPError (or any other request failure) so phase.py's
    per-layer failure record names the product and height directly,
    per M-F1-03's "existence confirmed on the CDN response after the
    redirect, never the redirect itself."
    """

    def __init__(self, country_code: str, product: str, height_m: int, cause: Exception) -> None:
        super().__init__(
            f"GWA product {product!r} at {height_m}m does not exist for "
            f"{country_code!r}, or the request failed after retries: {cause}"
        )
        self.country_code = country_code
        self.product = product
        self.height_m = height_m


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
    dest_dir = paths.fetched_raw("gwa", country_code)
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


def fetch_gwa_product(outputs_dir: Path, country_code: str, product: str, height_m: int) -> Path:
    """Download one Global Wind Atlas product at one hub height for one country.

    Implements: M-F1-03.

    Generalizes fetch_wind()'s verified endpoint pattern to all four GWA
    products (see GWA_PRODUCTS) at all three hub-relevant heights (see
    GWA_HEIGHTS_M) — probed live against PRT before this was wired into
    phase.py (all 12 combinations return 200 with a real GeoTIFF; see
    docs/phases/F1_data_acquisition.md). Unlike fetch_wind(), this
    raises rather than returning None on failure: M-F1-03 requires a
    missing product to fail loud (A-09), never be registered as an
    absent layer.

    Args:
        outputs_dir: Root outputs directory (PhaseContext.outputs_dir)
            — unused internally (destination resolves via
            paths.fetched_raw(), same as fetch_wind()); kept for
            call-site symmetry with phase.py's other fetch handlers.
        country_code: ISO-3166-alpha-3 code.
        product: One of GWA_PRODUCTS' keys.
        height_m: One of GWA_HEIGHTS_M.

    Returns:
        Path to the saved GeoTIFF.

    Raises:
        KeyError: If `product` is not one of GWA_PRODUCTS' keys.
        GwaProductNotFoundError: If the CDN response after the redirect
            is not a successful download (product/height does not
            exist in the catalogue, or the request failed after
            retries).
    """
    gwa_slug = GWA_PRODUCTS[product]
    dest_dir = paths.fetched_raw("gwa", country_code)
    dest_path = dest_dir / f"{country_code}_{product}_{height_m}m.tif"

    if dest_path.exists():
        return dest_path

    url = f"https://globalwindatlas.info/api/gis/country/{country_code}/{gwa_slug}/{height_m}"

    try:
        resp = get_with_retry(url, timeout=60)
    except Exception as exc:
        raise GwaProductNotFoundError(country_code, product, height_m, exc) from exc

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(resp.content)
    logger.info("GWA %s at %sm saved: %s", product, height_m, dest_path)
    return dest_path
