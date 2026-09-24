"""GADM 4.1 administrative boundaries fetcher — borders (level 0) + admin1 (level 1).

Ported from geoworld_framework's DataFetcher.download_gadm()
(data_fetcher.py L308-353) + its NaturalEarth fallback
(_download_naturalearth_fallback, L355-429), and DataManager's
_find_borders()/get_admin_level_1() (data_manager.py L126-178).

One module for both `borders` and `admin1` because they are literally
the same download, not two fetches: GADM's 4.1 shapefile zip bundles
levels 0-3 (fewer for small countries) together in one archive —
phase.py's _LAYER_REGISTRY already documented this ("admin1 ... same
download as borders", confirmed against legacy in DECISIONS.md
2026-08-24 "data_acquisition skeleton"). fetch_admin1() does not
download anything on its own; it ensures the same GADM zip is
fetched+extracted (idempotent, shared with fetch_borders() via
_ensure_gadm_extracted()) and then locates the level-1 shapefile within
it — mirroring DataManager.get_admin_level_1() exactly, including that
function having no NaturalEarth-equivalent fallback (NaturalEarth's
1:110m country layer has no state/province boundaries at all).

NaturalEarth fallback — ported with one narrowing: legacy tries
`geodatasets.get_path(...)` first, then falls back to the now-removed
`geopandas.datasets` API. geopandas>=1.0 (GeoFREA's own pinned minimum,
pyproject.toml) dropped `gpd.datasets` entirely, so that second branch
is dead code under GeoFREA's dependency floor and is not ported — only
the `geodatasets` path is kept, itself optional (ImportError -> log and
return None, the same graceful-degradation contract every fetcher in
this package already follows). `geodatasets` is NOT a GeoFREA
dependency; until/unless it is installed, a GADM failure simply yields
no border, not a crash. Also narrowed: legacy additionally matches on
`country_name`/`SOVEREIGNT` — not ported, since no GeoFREA fetcher
signature carries a country_name (only country_code, matching every
other fetcher in this package); matching is by ISO-3166-alpha-3 column
alone (iso_a3/ISO_A3/ADM0_A3).

Zip-slip protection (_safe_extract() in legacy) is security-relevant
and ported in full: every extracted member's resolved path is checked
against the extraction directory before extraction, exactly as legacy
does.
"""

from __future__ import annotations

import hashlib
import logging
import zipfile
from pathlib import Path

import pandas as pd

from geofrea.core import paths
from geofrea.core.config_loader import load_countries
from geofrea.core.http_retry import get_with_retry
from geofrea.core.paths import MissingPathEnvironmentError
from geofrea.data_acquisition.schemas import HASH_CHUNK_BYTES

logger = logging.getLogger("geofrea.data_acquisition.fetchers.gadm")

_GADM_URL_TEMPLATE = "https://geodata.ucdavis.edu/gadm/gadm4.1/shp/gadm41_{code}_shp.zip"

_NATURALEARTH_ISO_COLUMNS = ("iso_a3", "ISO_A3", "ADM0_A3")

# Chunk size: geofrea.data_acquisition.schemas.HASH_CHUNK_BYTES (single
# source of truth as of 2026-09-24, ADJ-7 — this module previously
# defined its own 8 MiB constant locally; unchanged value, just no
# longer a second definition of it).

# Lazy-loaded cache for countries.yaml, same pattern as local_layers.py.
_COUNTRIES_CONFIG: dict[str, dict[str, str | None]] | None = None


class GadmChecksumMismatchError(RuntimeError):
    """A local-database GADM level-0 shapefile's sha256 doesn't match countries.yaml.

    METHODOLOGY M-F1-07 + A-09: fails loud, never silently re-downloads
    or falls through to the network on a checksum mismatch — a mismatch
    means the local database file is not the one countries.yaml records,
    which is a data-integrity problem to fix (or a checksum to update),
    not something to route around automatically.
    """


def _load_countries_config() -> dict[str, dict[str, str | None]]:
    global _COUNTRIES_CONFIG
    if _COUNTRIES_CONFIG is None:
        project_root = Path(__file__).resolve().parents[4]
        countries_file = project_root / "config" / "countries.yaml"
        _COUNTRIES_CONFIG = load_countries(countries_file)
    return _COUNTRIES_CONFIG


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _local_database_dir(country_code: str) -> Path | None:
    """Resolve GEOFREA_SHARED_RAW_DIR/countries_borders/<gadm_dir>, if configured.

    Returns None (not raised) when GEOFREA_SHARED_RAW_DIR is unset or
    countries.yaml has no gadm_dir mapping for this country — both mean
    "skip the local database, fall through to the existing cache/network
    chain", not a configuration error, since GADM already has a working
    fallback for countries the local database doesn't cover.
    """
    config = _load_countries_config()
    gadm_dir = config.get(country_code, {}).get("gadm_dir")
    if gadm_dir is None:
        return None
    try:
        shared_raw = paths.shared_raw()
    except MissingPathEnvironmentError:
        return None
    return shared_raw / "countries_borders" / gadm_dir


def _local_database_level0(country_code: str) -> Path | None:
    """Return the local-database level-0 shapefile if present and checksum-verified.

    Verifies against countries.yaml's `gadm_level0_sha256`. No recorded
    checksum (None) is treated the same as no local file — the local
    database is never trusted without a checksum to verify against.

    Raises:
        GadmChecksumMismatchError: The local file exists but its sha256
            does not match the recorded checksum.
    """
    local_dir = _local_database_dir(country_code)
    if local_dir is None:
        return None

    level0 = local_dir / f"gadm41_{country_code}_0.shp"
    if not level0.exists():
        return None

    config = _load_countries_config()
    expected_sha256 = config.get(country_code, {}).get("gadm_level0_sha256")
    if expected_sha256 is None:
        logger.warning(
            "Local GADM file found for %s at %s but countries.yaml has no "
            "gadm_level0_sha256 recorded — not trusting it, falling back.",
            country_code,
            level0,
        )
        return None

    actual_sha256 = _sha256_file(level0)
    if actual_sha256 != expected_sha256:
        raise GadmChecksumMismatchError(
            f"Local GADM level-0 shapefile for {country_code} at {level0} has "
            f"sha256 {actual_sha256}, but countries.yaml records "
            f"{expected_sha256}. Not falling back to the network — fix the "
            "local file or update the recorded checksum."
        )
    return level0


def _safe_extract(zip_path: Path, target_dir: Path) -> None:
    """Extract `zip_path` into `target_dir`, refusing any member that would escape it.

    Ported from legacy's DataFetcher._safe_extract() — a Zip Slip guard
    (a malicious/corrupt archive with a path-traversal member like
    "../../etc/passwd" must not be able to write outside target_dir).

    Raises:
        ValueError: If any archive member would extract outside target_dir.
    """
    target_resolved = target_dir.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            dest = (target_dir / member).resolve()
            try:
                dest.relative_to(target_resolved)
            except ValueError:
                raise ValueError(
                    f"Zip Slip detected: {member!r} escapes {target_dir} — "
                    "archive rejected."
                ) from None
        zf.extractall(target_dir)


def _gadm_paths(outputs_dir: Path, country_code: str) -> tuple[Path, Path]:
    dest_dir = paths.fetched_raw("gadm", country_code)
    zip_path = dest_dir / f"gadm41_{country_code}_shp.zip"
    extract_dir = dest_dir / f"gadm41_{country_code}_shp"
    return zip_path, extract_dir


def _ensure_gadm_extracted(outputs_dir: Path, country_code: str) -> Path | None:
    """Download (if needed) and extract the GADM 4.1 zip for one country.

    Idempotent, mirroring hydrosheds.py's _fetch_and_extract_shapefile():
    an already-extracted directory (any .shp present) is reused without
    re-downloading or re-extracting; an already-downloaded zip is reused
    without a new network call. Shared by fetch_borders() and
    fetch_admin1() — both need the same extracted directory, not two
    independent downloads.

    Returns:
        The extraction directory, or None if the download or extraction
        failed (logged, not raised — one bad fetch must not abort
        acquisition).
    """
    zip_path, extract_dir = _gadm_paths(outputs_dir, country_code)

    if extract_dir.exists() and any(extract_dir.rglob("*.shp")):
        return extract_dir

    if not zip_path.exists():
        url = _GADM_URL_TEMPLATE.format(code=country_code)
        try:
            resp = get_with_retry(url, timeout=120)
        except Exception as exc:  # noqa: BLE001 — one bad fetch must not abort acquisition
            logger.warning("Failed to fetch GADM borders for %s: %s", country_code, exc)
            return None
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        zip_path.write_bytes(resp.content)

    try:
        _safe_extract(zip_path, extract_dir)
    except Exception as exc:  # noqa: BLE001 — malformed/corrupt/unsafe zip must not abort acquisition
        logger.warning("Failed to extract GADM zip for %s: %s", country_code, exc)
        return None

    if not any(extract_dir.rglob("*.shp")):
        logger.warning("GADM zip for %s extracted but contains no .shp.", country_code)
        return None

    return extract_dir


def _naturalearth_fallback(outputs_dir: Path, country_code: str) -> Path | None:
    """Fall back to NaturalEarth 1:110m borders when GADM itself fails.

    Optional: needs the `geodatasets` package (not a GeoFREA
    dependency) — see module docstring for why only this path (of
    legacy's two) is ported.
    """
    try:
        import geodatasets
    except ImportError:
        logger.warning(
            "GADM download failed for %s and the NaturalEarth fallback needs the "
            "optional 'geodatasets' package (not installed) — no border available.",
            country_code,
        )
        return None

    import geopandas as gpd

    try:
        world = gpd.read_file(geodatasets.get_path("naturalearth.land"))
    except Exception as exc:  # noqa: BLE001 — fallback failure must not abort acquisition
        logger.warning("NaturalEarth fallback failed to load for %s: %s", country_code, exc)
        return None

    mask = pd.Series(False, index=world.index)
    for col in _NATURALEARTH_ISO_COLUMNS:
        if col in world.columns:
            mask |= world[col].str.upper() == country_code.upper()

    country_gdf = world[mask]
    if country_gdf.empty:
        logger.warning("%s not found in NaturalEarth fallback data.", country_code)
        return None

    dest_dir = paths.fetched_raw("gadm", country_code)
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_path = dest_dir / f"{country_code}_naturalearth_fallback.shp"
    country_gdf.to_file(out_path)
    logger.warning(
        "GADM unavailable for %s — using NaturalEarth fallback (~1:110m): %s",
        country_code,
        out_path,
    )
    return out_path


def fetch_borders(outputs_dir: Path, country_code: str) -> Path | None:
    """Resolve GADM 4.1 boundaries and return the level-0 (country) shapefile.

    METHODOLOGY M-F1-07: checks the local database
    (GEOFREA_SHARED_RAW_DIR/countries_borders/<gadm_dir>, countries.yaml)
    first, verifying the recorded sha256 — a match performs no network
    call at all. Only when the local database has no entry for this
    country (or no file at the expected path) does this fall through to
    the existing GEOFREA_DATA_DIR cache/network chain, then to
    NaturalEarth 1:110m if GADM itself fails — see
    _naturalearth_fallback() and the module docstring. A checksum
    mismatch raises GadmChecksumMismatchError instead of falling back
    (A-09: fail loud, never silently re-download).

    Args:
        outputs_dir: Root outputs directory (PhaseContext.outputs_dir).
        country_code: ISO-3166-alpha-3 code.

    Returns:
        Path to the level-0 .shp (local database, cache, or the
        NaturalEarth fallback .shp), or None if every path failed
        (logged, not raised).
    """
    local_level0 = _local_database_level0(country_code)
    if local_level0 is not None:
        return local_level0

    extract_dir = _ensure_gadm_extracted(outputs_dir, country_code)
    if extract_dir is None:
        return _naturalearth_fallback(outputs_dir, country_code)

    level0 = sorted(extract_dir.rglob("*_0.shp"))
    if level0:
        return level0[0]

    any_shp = sorted(extract_dir.rglob("*.shp"))
    return any_shp[0] if any_shp else None


def fetch_admin1(outputs_dir: Path, country_code: str) -> Path | None:
    """Locate the GADM level-1 (admin1) shapefile.

    METHODOLOGY M-F1-07: reuses fetch_borders()'s local-database check —
    a checksum-verified level-0 hit means the same local directory's
    level-1 file is trusted too (both are the same pre-placed shapefile
    set, not two independent artifacts). Otherwise falls through to the
    same GEOFREA_DATA_DIR cache/network chain fetch_borders() uses; not
    a separate download either way (see module docstring). Calls
    _ensure_gadm_extracted() itself so the network-fallback path works
    correctly even if called before/without fetch_borders() in the same
    run.

    Args:
        outputs_dir: Root outputs directory (PhaseContext.outputs_dir).
        country_code: ISO-3166-alpha-3 code.

    Returns:
        Path to the level-1 .shp, or None if GADM failed or the country
        has no level-1 boundaries (no NaturalEarth-equivalent fallback
        exists for admin1 — see module docstring).
    """
    local_level0 = _local_database_level0(country_code)
    if local_level0 is not None:
        level1 = local_level0.parent / f"gadm41_{country_code}_1.shp"
        return level1 if level1.exists() else None

    extract_dir = _ensure_gadm_extracted(outputs_dir, country_code)
    if extract_dir is None:
        return None

    level1 = sorted(extract_dir.rglob("*_1.shp"))
    return level1[0] if level1 else None
