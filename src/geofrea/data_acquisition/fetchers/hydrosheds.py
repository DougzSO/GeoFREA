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

Zip internal layout — discovered live 2026-08-25 while validating
clip_vector_to_country() against real downloaded data (see
docs/DECISIONS.md same date, "data_acquisition activation"), NOT
something the earlier curl-only verification could have caught: both
zips nest their shapefile one directory level deep (e.g.
"HydroLAKES_polys_v10_shp/HydroLAKES_polys_v10.shp") alongside unrelated
top-level files (a tech-doc PDF). GDAL's vsizip auto-detection — what a
plain gpd.read_file(zip_path) relies on, and what
data_quality_audit/vector_inspection.py's inspect_vector_layer() does —
does NOT reliably find a shapefile nested this way: confirmed live that
gpd.read_file() raised pyogrio.errors.DataSourceError
("not recognized as being in a supported file format") for BOTH the
real HydroLAKES and HydroRIVERS downloads. This was a latent bug in the
previous stage's fetchers (2026-08-25 "real fetchers for power_plants/
wind/lakes/rivers") — invisible until real data existed to test
against, since every prior test/inspection used non-zip fixtures for
lakes/rivers.

Fixed here by extracting the zip once at fetch time
(_fetch_and_extract_shapefile below) and returning a direct path to the
.shp file — not a zip:// or /vsizip/ internal-path string, which would
just move the same nested-layout knowledge into every downstream reader
(inspect_vector_layer() is generic across 7 vector layers; it should
not need to know HydroSHEDS' internal zip structure). Idempotency now
checks for the already-extracted .shp, not just the .zip, so a rerun
after a successful extraction does no I/O at all; a rerun after a
download that succeeded but crashed before extraction reuses the
already-downloaded zip instead of re-fetching it.
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

from geofrea.core import paths
from geofrea.core.config_loader import CountryMappingError, load_countries
from geofrea.core.http_retry import get_with_retry

logger = logging.getLogger("geofrea.data_acquisition.fetchers.hydrosheds")

_LAKES_GLOBAL_URL = "https://data.hydrosheds.org/file/hydrolakes/HydroLAKES_polys_v10_shp.zip"

_RIVERS_TILE_URL_TEMPLATE = (
    "https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_{region}_shp.zip"
)

# Lazy-loaded cache for countries.yaml
_COUNTRIES_CONFIG: dict[str, dict[str, str | None]] | None = None


def _load_countries_config() -> dict[str, dict[str, str | None]]:
    """Load countries.yaml lazily, caching the result.

    Returns:
        The loaded countries configuration dictionary.

    Raises:
        FileNotFoundError: If countries.yaml is not found.
    """
    global _COUNTRIES_CONFIG
    if _COUNTRIES_CONFIG is None:
        # Find countries.yaml relative to this module
        # Path from hydrosheds.py to project root is up 4 levels:
        # hydrosheds.py -> fetchers -> data_acquisition -> geofrea -> src -> project_root
        project_root = Path(__file__).resolve().parents[4]
        countries_file = project_root / "config" / "countries.yaml"
        _COUNTRIES_CONFIG = load_countries(countries_file)
    return _COUNTRIES_CONFIG


def _get_hydrosheds_region(country_code: str) -> str:
    """Get the HydroSHEDS region tile code for a country.

    Args:
        country_code: ISO-3 country code (e.g., "BRA", "PRT").

    Returns:
        The region tile code (e.g., "sa", "eu").

    Raises:
        CountryMappingError: If the country is not in the config, or if
            the hydrosheds_region mapping is null.
    """
    config = _load_countries_config()

    if country_code not in config:
        raise CountryMappingError(
            f"Country '{country_code}' not found in config/countries.yaml"
        )

    region = config[country_code].get("hydrosheds_region")
    if region is None:
        raise CountryMappingError(
            f"HydroSHEDS region mapping for country '{country_code}' is null in "
            f"config/countries.yaml (not yet determined)"
        )

    return region


def _fetch_and_extract_shapefile(
    url: str, zip_path: Path, *, timeout: int, label: str
) -> Path | None:
    """Download `url` to `zip_path` if needed, then extract its shapefile.

    Shared by fetch_lakes()/fetch_rivers() — both HydroSHEDS zips have
    the same nested-shapefile-plus-extra-files layout (see module
    docstring, "Zip internal layout"), so the download/extract/
    idempotency logic is identical; only the URL and destination naming
    differ per caller.

    Args:
        url: Source zip URL.
        zip_path: Where to save the downloaded zip. Extraction target
            is a sibling directory, `zip_path.parent / zip_path.stem`.
        timeout: Per-request timeout in seconds (rivers tiles are
            smaller than the lakes global file, so callers use
            different values).
        label: Human-readable name for log messages (e.g. "HydroLAKES").

    Returns:
        Path to the extracted .shp file, or None if the fetch,
        extraction, or the extracted content itself failed/was
        malformed (logged, not raised — same graceful-degradation
        contract every other fetcher in this package follows).
    """
    extract_dir = zip_path.parent / zip_path.stem

    already_extracted = sorted(extract_dir.rglob("*.shp")) if extract_dir.exists() else []
    if len(already_extracted) == 1:
        return already_extracted[0]

    if not zip_path.exists():
        try:
            resp = get_with_retry(url, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 — one bad fetch must not abort acquisition
            logger.warning("Failed to fetch %s: %s", label, exc)
            return None
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        zip_path.write_bytes(resp.content)

    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
    except Exception as exc:  # noqa: BLE001 — malformed/corrupt zip must not abort acquisition
        logger.warning("Failed to extract %s zip %s: %s", label, zip_path, exc)
        return None

    shp_matches = sorted(extract_dir.rglob("*.shp"))
    if len(shp_matches) != 1:
        logger.warning(
            "Expected exactly one .shp under %s after extracting %s, found %d: %s",
            extract_dir,
            label,
            len(shp_matches),
            shp_matches,
        )
        return None

    logger.info("%s extracted: %s", label, shp_matches[0])
    return shp_matches[0]


def fetch_lakes(outputs_dir: Path) -> Path | None:
    """Download the HydroLAKES global shapefile (820 MB), once.

    Global dataset (country_specific=False in _LAYER_REGISTRY,
    unchanged by this stage) — saved once under `_global/`, not
    per-country. No regional-tile alternative exists (confirmed live,
    see module docstring) — this is deliberately the full global file.

    Args:
        outputs_dir: Root outputs directory (PhaseContext.outputs_dir).

    Returns:
        Path to the extracted .shp file, or None if the fetch/extraction
        failed (logged, not raised — see _fetch_and_extract_shapefile()).
    """
    dest_dir = paths.fetched_raw("hydrosheds", "_global")
    zip_path = dest_dir / "HydroLAKES_polys_v10_shp.zip"

    return _fetch_and_extract_shapefile(
        _LAKES_GLOBAL_URL, zip_path, timeout=300, label="HydroLAKES"
    )


def fetch_rivers(outputs_dir: Path, country_code: str) -> Path | None:
    """Download the HydroRIVERS regional tile covering one country.

    Args:
        outputs_dir: Root outputs directory (PhaseContext.outputs_dir).
        country_code: ISO-3166-alpha-3 code. Must have a hydrosheds_region
            mapping in config/countries.yaml — an unmapped country is a
            configuration gap to fix (add the region code), not a runtime
            condition to handle gracefully, so this raises CountryMappingError
            rather than silently returning None like the network-failure
            path below does.

    Returns:
        Path to the extracted .shp file, or None if the fetch/extraction
        failed (logged, not raised — see _fetch_and_extract_shapefile()).

    Raises:
        CountryMappingError: If country_code is not in countries.yaml or
            if its hydrosheds_region mapping is null.
    """
    region = _get_hydrosheds_region(country_code)

    dest_dir = paths.fetched_raw("hydrosheds", country_code)
    zip_path = dest_dir / f"HydroRIVERS_v10_{region}_shp.zip"
    url = _RIVERS_TILE_URL_TEMPLATE.format(region=region)

    return _fetch_and_extract_shapefile(
        url, zip_path, timeout=180, label=f"HydroRIVERS tile '{region}' for {country_code}"
    )
