"""Local-database path resolution for elevation/population/grid/land_cover.

NOT a fetcher module — nothing here performs an HTTP request. These 4
layers have no automatable source today (see phase.py's _LAYER_REGISTRY
and schemas.py's AcquiredLayer.provenance docstring: "local_only" means
"no fetch mechanism exists for it at all ... must be pre-placed on
disk"). This module's only job is locating files that were already
placed on disk by hand, under GEOFREA_RAW_DATA_DIR, and handing back a
Path/list[Path] — the same shape run_acquisition_phase() would get from
a real fetcher, so phase.py's wiring for these 4 layers is a thin
"resolve instead of download" swap, not a new code path.

Phase 1 of "wire das 5 camadas restantes a partir do banco local" (see
docs/DECISIONS.md, same title) — elevation/population/grid/land_cover.
`roads` (the 5th remaining layer) is deliberately NOT covered here; see
that DECISIONS.md entry for why it was split into its own stage.

land_cover provenance change is a REVERT, not a bug fix: the original
skeleton (docs/DECISIONS.md 2026-08-24 "data_acquisition skeleton")
deliberately set land_cover to provenance="fetched"/auth_required=True
because Terrascope (the only source geoworld_framework's DataFetcher
ever used for it) requires credentials. This stage reverses that
decision — land_cover now resolves from pre-downloaded ESA WorldCover
tiles already sitting in the local database, same as
solar/seismic/protected always have — per Douglas's explicit
instruction, recorded in DECISIONS.md rather than silently changed.

fetch_status (AcquiredLayer, schemas.py — a computed field keyed off
IMPLEMENTED_FETCH_LAYER_NAMES) is UNCHANGED by this module: none of
these 4 layer_names are added to that set, so fetch_status keeps
reporting "not_implemented" for all of them. provenance says where a
layer's file comes from; fetch_status says whether GeoFREA's own code
fetches it. Resolving a pre-placed local path is neither — it is
exactly what "local_only" already means.

Two DIFFERENT failure modes, deliberately handled differently (Douglas,
explicit instruction this stage — not symmetric by oversight):
  - country_code missing from _ELEVATION_COUNTRY_DIRS /
    _LAND_COVER_COUNTRY_DIRS (the two lookup tables below): a
    CONFIGURATION gap — the same class of problem as hydrosheds.py's
    _COUNTRY_TO_REGION KeyError for an unmapped country. Raises
    KeyError, uncaught, so it surfaces loudly via the Orchestrator's own
    PhaseExecutionError instead of silently producing path=None for a
    country nobody remembered to add to the table.
  - GEOFREA_RAW_DATA_DIR unset, or the expected file/directory genuinely
    absent under it (download never completed, drive not mounted, wrong
    machine): graceful degradation, same contract every fetcher in this
    package already follows for a transient failure — log a warning,
    return None / []. This also means every existing
    test_data_acquisition_phase.py test that does not configure
    GEOFREA_RAW_DATA_DIR keeps passing unchanged (explicit Douglas
    decision this stage): an unconfigured local database is not a
    reason to fail the whole phase, any more than a network outage is.

population/grid need no lookup table at all — their on-disk naming is a
mechanical function of country_code (population: lowercase ISO3
filename prefix, flat directory; grid: uppercase ISO3 filename prefix,
flat directory), confirmed against the real database
(GEOFREA_RAW_DATA_DIR/population/*.tif,
GEOFREA_RAW_DATA_DIR/infrastructure/grid/*.geojson) for all 7 countries
currently on disk. elevation/land_cover are NOT mechanical — their
per-country subdirectory names were confirmed by directly listing
GEOFREA_RAW_DATA_DIR, not assumed from a naming convention:

  - land_cover subdirectories use the full English country name
    consistently ("Portugal", "Brazil", "South Africa", ...).
  - elevation subdirectories do NOT follow one convention: PRT and EGY
    use the ISO3 code itself as the directory name, while every other
    country (Brazil, China, India, Russia, South Africa) uses the full
    English name instead. Confirmed by listing, not a typo in this
    module — _ELEVATION_COUNTRY_DIRS reflects what is actually on disk.

Both tables cover only the 7 countries physically present in the local
database today (BRA, CHN, EGY, IND, PRT, RUS, ZAF) — parameters.json
currently only runs PRT/BRA, so the other 5 are unexercised head start
for a future scope expansion, not dead code to prune. Adding an 8th
country requires adding its directory name to both tables (elevation
and land_cover independently, since they don't share a convention).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("geofrea.data_acquisition.local_layers")

RAW_DATA_DIR_ENV_VAR = "GEOFREA_RAW_DATA_DIR"

# Confirmed 2026-09-08 by directly listing GEOFREA_RAW_DATA_DIR/elevation
# — NOT a naming convention, a literal record of what each of the 7
# directories on disk is actually called. See module docstring.
_ELEVATION_COUNTRY_DIRS: dict[str, str] = {
    "BRA": "Brazil",
    "CHN": "China",
    "EGY": "EGY",
    "IND": "India",
    "PRT": "PRT",
    "RUS": "Russia",
    "ZAF": "South Africa",
}

# Confirmed 2026-09-08 by directly listing GEOFREA_RAW_DATA_DIR/land_cover
# — full English country name in every case (unlike elevation above).
_LAND_COVER_COUNTRY_DIRS: dict[str, str] = {
    "BRA": "Brazil",
    "CHN": "China",
    "EGY": "Egypt",
    "IND": "India",
    "PRT": "Portugal",
    "RUS": "Russia",
    "ZAF": "South Africa",
}

_LAND_COVER_TILE_GLOB = "ESA_WorldCover_10m_2020_v100_*_Map.tif"


def _raw_data_dir() -> Path | None:
    """Resolve GEOFREA_RAW_DATA_DIR, or None if unset/empty.

    Deliberately graceful (log + None), not a raise — see module
    docstring's "two different failure modes". Re-read from the
    environment on every call rather than cached at import time, so a
    test's monkeypatch.setenv() takes effect without needing a reload.
    """
    raw = os.environ.get(RAW_DATA_DIR_ENV_VAR)
    if not raw:
        logger.warning(
            "%s is not set — local-only layers (elevation/population/grid/"
            "land_cover) cannot be resolved this run.",
            RAW_DATA_DIR_ENV_VAR,
        )
        return None
    return Path(raw)


def resolve_elevation_path(country_code: str) -> Path | None:
    """Resolve the local Copernicus DEM elevation raster for one country.

    Args:
        country_code: ISO-3166-alpha-3 code. Must be a key in
            _ELEVATION_COUNTRY_DIRS.

    Returns:
        Path to `<raw>/elevation/<dir>/<country_code>_elevation.tif`, or
        None if GEOFREA_RAW_DATA_DIR is unset or the file is genuinely
        absent on disk (logged, not raised in either case).

    Raises:
        KeyError: If country_code is not in _ELEVATION_COUNTRY_DIRS —
            a configuration gap, not a runtime condition (see module
            docstring).
    """
    country_dir = _ELEVATION_COUNTRY_DIRS[country_code]

    raw_data_dir = _raw_data_dir()
    if raw_data_dir is None:
        return None

    path = raw_data_dir / "elevation" / country_dir / f"{country_code}_elevation.tif"
    if not path.exists():
        logger.warning("Local elevation raster not found for %s: %s", country_code, path)
        return None
    return path


def resolve_population_path(country_code: str) -> Path | None:
    """Resolve the local WorldPop population raster for one country.

    Args:
        country_code: ISO-3166-alpha-3 code. No lookup table needed —
            the on-disk filename is a mechanical lowercase-ISO3 prefix
            in a flat directory (confirmed for all 7 countries currently
            on disk).

    Returns:
        Path to `<raw>/population/<iso3_lower>_pop_2020.tif`, or None if
        GEOFREA_RAW_DATA_DIR is unset or the file is genuinely absent on
        disk (logged, not raised).
    """
    raw_data_dir = _raw_data_dir()
    if raw_data_dir is None:
        return None

    path = raw_data_dir / "population" / f"{country_code.lower()}_pop_2020.tif"
    if not path.exists():
        logger.warning("Local population raster not found for %s: %s", country_code, path)
        return None
    return path


def resolve_grid_path(country_code: str) -> Path | None:
    """Resolve the local OSM power-grid vector file for one country.

    Args:
        country_code: ISO-3166-alpha-3 code. No lookup table needed —
            the on-disk filename is a mechanical uppercase-ISO3 prefix in
            a flat directory (confirmed for all 7 countries currently on
            disk). That directory also holds an unlabeled `grid.gpkg`
            with no country prefix — deliberately not matched by this
            function's exact filename construction (not a glob), so it
            is never picked up here; what it is remains unconfirmed and
            out of scope for this stage.

    Returns:
        Path to `<raw>/infrastructure/grid/<country_code>_grid_osm.geojson`,
        or None if GEOFREA_RAW_DATA_DIR is unset or the file is genuinely
        absent on disk (logged, not raised).
    """
    raw_data_dir = _raw_data_dir()
    if raw_data_dir is None:
        return None

    path = raw_data_dir / "infrastructure" / "grid" / f"{country_code}_grid_osm.geojson"
    if not path.exists():
        logger.warning("Local grid vector file not found for %s: %s", country_code, path)
        return None
    return path


def resolve_land_cover_tiles(country_code: str) -> list[Path]:
    """Resolve every local ESA WorldCover tile covering one country.

    land_cover is genuinely multi-file (MULTI_FILE_LAYER_NAMES,
    schemas.py) — every tile is consumed downstream
    (inspect_land_cover_tiles() iterates every tile), so this returns
    the full sorted list, not a single path.

    Args:
        country_code: ISO-3166-alpha-3 code. Must be a key in
            _LAND_COVER_COUNTRY_DIRS.

    Returns:
        Sorted list of tile Paths under
        `<raw>/land_cover/<dir>/ESA_WorldCover_10m_2020_v100_*_Map.tif`,
        or [] if GEOFREA_RAW_DATA_DIR is unset, the country directory
        does not exist, or it exists but contains no matching tile
        (logged, not raised in any of these cases).

    Raises:
        KeyError: If country_code is not in _LAND_COVER_COUNTRY_DIRS —
            a configuration gap, not a runtime condition (see module
            docstring).
    """
    country_dir = _LAND_COVER_COUNTRY_DIRS[country_code]

    raw_data_dir = _raw_data_dir()
    if raw_data_dir is None:
        return []

    tiles_dir = raw_data_dir / "land_cover" / country_dir
    tiles = sorted(tiles_dir.glob(_LAND_COVER_TILE_GLOB))
    if not tiles:
        logger.warning("No local land_cover tiles found for %s under %s", country_code, tiles_dir)
    return tiles
