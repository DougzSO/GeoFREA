"""Generic HTTP retry helper shared across data_acquisition fetchers.

Ported (adapted, not copied verbatim) from geoworld_framework's
DataFetcher._request_with_retry() — the one piece of legacy fetch
infrastructure that is genuinely cross-source: every one of legacy's 6
download_* methods that uses plain HTTP (GADM, OSM/Overpass,
OpenTopography fallback) shares this exact retry/backoff shape,
independent of which source it's fetching from. WorldPop (FTP) and
Terrascope's catalogue client each need their own retry loop because
they're a different transport entirely — not because of a different
auth pattern. See docs/DECISIONS.md 2026-08-25 "real fetchers for
power_plants/wind/lakes/rivers" (its "Por que fetch por FONTE"
section) for the full (a)-vs-(b) rationale, which is why this lives
here as one shared HTTP-transport utility rather than duplicated per
fetcher, while each fetcher module (data_acquisition/fetchers/) still
owns its own source-specific URL construction, response parsing, and
country/region resolution.

Not a full port: legacy's version also handled a configurable
request_delay_s between successful requests (throttling even on
success, read from settings.yaml). Not needed here — none of GeoFREA's
current fetchers hit an endpoint with a documented per-request rate
limit (see the fonte-por-fonte research, 2026-08-24) that would need
inter-request throttling on top of retry-on-failure.
"""

from __future__ import annotations

import logging
import time

import requests

logger = logging.getLogger("geofrea.core.http_retry")

_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BACKOFF_BASE_S = 5.0


def request_with_retry(
    method: str,
    url: str,
    *,
    timeout: int = 120,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    backoff_base_s: float = _DEFAULT_BACKOFF_BASE_S,
    **kwargs,
) -> requests.Response:
    """Make an HTTP request, retrying on 429/503 and transient network errors.

    Mirrors geoworld_framework's DataFetcher._request_with_retry():
    honors a `Retry-After` header on 429/503 responses, falls back to
    exponential backoff (`backoff_base_s * 2**attempt`) otherwise, and
    retries `requests.RequestException` (connection errors, timeouts)
    with a steeper backoff (`backoff_base_s * 3**attempt`).

    Args:
        method: HTTP method (GET, POST, etc.).
        url: Target URL.
        timeout: Per-request timeout in seconds.
        max_retries: Maximum number of attempts.
        backoff_base_s: Base seconds for exponential backoff.
        **kwargs: Passed through to requests.request().

    Returns:
        The successful Response.

    Raises:
        requests.RequestException: If every attempt fails.
    """
    last_exc: Exception = RuntimeError("No attempts made.")

    for attempt in range(max_retries):
        try:
            resp = requests.request(method, url, timeout=timeout, **kwargs)

            if resp.status_code in (429, 503):
                retry_after = resp.headers.get("Retry-After")
                wait = int(retry_after) if retry_after else int(backoff_base_s * (2**attempt))
                logger.warning(
                    "HTTP %d on attempt %d/%d for %s. Waiting %ds.",
                    resp.status_code,
                    attempt + 1,
                    max_retries,
                    url,
                    wait,
                )
                time.sleep(wait)
                continue

            resp.raise_for_status()
            return resp

        except requests.RequestException as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait = backoff_base_s * (3**attempt)
                logger.warning(
                    "Attempt %d/%d failed for %s: %s. Retrying in %ds.",
                    attempt + 1,
                    max_retries,
                    url,
                    exc,
                    wait,
                )
                time.sleep(wait)

    raise last_exc


def get_with_retry(url: str, *, timeout: int = 120, **kwargs) -> requests.Response:
    """Convenience wrapper for GET requests — see request_with_retry()."""
    return request_with_retry("GET", url, timeout=timeout, **kwargs)
