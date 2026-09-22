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

import logging
import zipfile
from pathlib import Path

import pandas as pd

from geofrea.core import paths
from geofrea.core.http_retry import get_with_retry

logger = logging.getLogger("geofrea.data_acquisition.fetchers.gadm")

_GADM_URL_TEMPLATE = "https://geodata.ucdavis.edu/gadm/gadm4.1/shp/gadm41_{code}_shp.zip"

_NATURALEARTH_ISO_COLUMNS = ("iso_a3", "ISO_A3", "ADM0_A3")


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
    """Download GADM 4.1 boundaries and return the level-0 (country) shapefile.

    Falls back to NaturalEarth 1:110m if GADM itself fails — see
    _naturalearth_fallback() and the module docstring.

    Args:
        outputs_dir: Root outputs directory (PhaseContext.outputs_dir).
        country_code: ISO-3166-alpha-3 code.

    Returns:
        Path to the level-0 .shp (or the NaturalEarth fallback .shp),
        or None if both failed (logged, not raised).
    """
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

    Not a separate download — a subproduct of the same zip
    fetch_borders() uses (see module docstring). Calls
    _ensure_gadm_extracted() itself so this works correctly even if
    called before/without fetch_borders() in the same run.

    Args:
        outputs_dir: Root outputs directory (PhaseContext.outputs_dir).
        country_code: ISO-3166-alpha-3 code.

    Returns:
        Path to the level-1 .shp, or None if GADM failed or the country
        has no level-1 boundaries (no NaturalEarth-equivalent fallback
        exists for admin1 — see module docstring).
    """
    extract_dir = _ensure_gadm_extracted(outputs_dir, country_code)
    if extract_dir is None:
        return None

    level1 = sorted(extract_dir.rglob("*_1.shp"))
    return level1[0] if level1 else None
