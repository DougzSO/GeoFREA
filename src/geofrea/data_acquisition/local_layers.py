"""Local-database path resolution for elevation/population/grid/land_cover/roads/solar.

NOT a fetcher module — nothing here performs an HTTP request. These
layers have no automatable source today (see phase.py's _LAYER_REGISTRY
and schemas.py's AcquiredLayer.provenance docstring: "local_only" means
"no fetch mechanism exists for it at all ... must be pre-placed on
disk"). This module's only job is locating files that were already
placed on disk by hand, under GEOFREA_RAW_DATA_DIR, and handing back a
Path/list[Path] — the same shape run_acquisition_phase() would get from
a real fetcher, so phase.py's wiring for these layers is a thin
"resolve instead of download" swap, not a new code path.

`solar` was added 2026-09-11 (resolve_solar_path): a single global
Global Solar Atlas v2 PVOUT raster, hard-required by suitability_criteria
(REQUIRED_ALIGNED_LAYERS) — the phase could not run end-to-end without
it. Unlike elevation/population/grid it is not country-split; the
country_code argument is accepted only for a uniform handler signature.

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

roads (added 2026-09-08, Fase 2 of "wire das 5 camadas restantes a
partir do banco local" — see docs/DECISIONS.md same date): resolves to
the GRIP4 (Global Roads Inventory Project) regional shapefile covering
one country, UNCLIPPED — unlike elevation/population/grid/land_cover
above, this file spans many countries (GRIP4's own continental region
split, not a per-country product), so it is resolved the same way
lakes/rivers/protected already are: point AcquiredLayer.path at the
raw regional source, and let data_quality_audit's existing
inspect_vector_layer(clip=True) + read_clipped_to_country() +
cache_path machinery (vector_inspection.py, core/geo_utils.py) do the
actual per-country clip at inspection time, not here. This module does
no clipping itself — same boundary as every other resolver in this
file, "locate a path, don't process it."

_ROADS_COUNTRY_REGION_DIRS is DELIBERATELY restricted to BRA/PRT only,
not all 7 countries like the tables above — GEOFREA_RAW_DATA_DIR also
ships a regions_lookup.json meant to map every country to its GRIP4
region, but it was found (2026-09-08) to DISAGREE with the actual
region number embedded in each shapefile's own `gp_gripreg` attribute
for every region except the two this stage needs: regions_lookup.json
labels official region 1 as Africa, 5 as South Asia, 6 as East/
Southeast Asia, 7 as Central/West Asia, but the folders physically on
disk (Region_3_Africa, Region_5_Middle_East_Central_Asia,
Region_6_Central_East_Asia) contain data whose own gp_gripreg field
reads 3, 5, 6 respectively — confirmed by sampling 5,000 rows per file,
not assumed. For BRA (Region_2_Central_South_America, gp_gripreg=2)
and PRT (Region_4_Europe, gp_gripreg=4), every source agrees — folder
number, folder descriptive name, regions_lookup.json's key, and the
shapefile's own gp_gripreg column all point to the same file, so there
is no ambiguity for either country actually in parameters.json today.
Extending this table to CHN/EGY/IND/RUS/ZAF requires first resolving
which numbering regions_lookup.json actually intended — NOT guessed
here. Two of the 8 official GRIP4 regions (1-Africa, 7-Central/West
Asia per regions_lookup.json's own labels) are additionally still
zipped (GRIP4_Region1_vector_shp.zip, GRIP4_Region7_vector_shp.zip),
not extracted, on disk — unusable without an extraction step regardless
of the numbering question.

GRIP4_Region1/7_vector_shp.zip are NOT the same files as the
`Region_3_Africa`/etc. directories despite the "Region_N" naming
overlap being confusing — the zips retain their original download
numbering (matching regions_lookup.json's official scheme), the
extracted directories do not (see above). Left unresolved and
unextracted; flagged, not touched, this stage.

Also found under GEOFREA_RAW_DATA_DIR/infrastructure/roads/, NOT used
by this module: `<ISO3>_roads_osm.geojson` files for CHN/EGY/IND/ZAF
(not BRA/PRT) — leftovers from an earlier OSM-based roads acquisition
attempt, orphaned now that GRIP4 is the designated source for `roads`.
Left in place, not deleted (out of scope), see DECISIONS.md 2026-09-08.

Live-verified 2026-09-08 (isolated script, real GADM boundary +
read_clipped_to_country(), not assumed to scale linearly from the
smaller HydroRIVERS precedent per Douglas's explicit instruction): cold
clip took 17.5s for PRT (178,986 features, 63,475 km) and 184.4s
(~3.1 min) for BRA (548,287 features, 694,571 km) — both faster than
the historical rivers/BRA benchmark (191.63s isolated / 348.8s
production, DECISIONS.md 2026-08-25/26) despite GRIP4's regional files
being larger on disk than HydroRIVERS' tiles; system RAM stayed healthy
throughout both runs (never dropped below ~5.2 GB free of 15.8 GB).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from geofrea.core.config_loader import CountryMappingError, load_countries

logger = logging.getLogger("geofrea.data_acquisition.local_layers")

RAW_DATA_DIR_ENV_VAR = "GEOFREA_RAW_DATA_DIR"

_LAND_COVER_TILE_GLOB = "ESA_WorldCover_10m_2020_v100_*_Map.tif"

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
        # Path from local_layers.py to project root is up 3 levels:
        # local_layers.py -> data_acquisition -> geofrea -> src -> project_root
        project_root = Path(__file__).resolve().parents[3]
        countries_file = project_root / "config" / "countries.yaml"
        _COUNTRIES_CONFIG = load_countries(countries_file)
    return _COUNTRIES_CONFIG


def _get_country_mapping(country_code: str, key: str) -> str:
    """Get a mapping value from countries.yaml for a country.

    Args:
        country_code: ISO-3 country code (e.g., "BRA", "PRT").
        key: The mapping key (e.g., "elevation_dir", "land_cover_dir").

    Returns:
        The mapping value (a non-null string).

    Raises:
        CountryMappingError: If the country is not in the config, or if
            the requested mapping is null (not yet determined).
    """
    config = _load_countries_config()

    if country_code not in config:
        raise CountryMappingError(
            f"Country '{country_code}' not found in config/countries.yaml"
        )

    value = config[country_code].get(key)
    if value is None:
        raise CountryMappingError(
            f"Mapping '{key}' for country '{country_code}' is null in "
            f"config/countries.yaml (not yet determined)"
        )

    return value


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
            "roads/land_cover) cannot be resolved this run.",
            RAW_DATA_DIR_ENV_VAR,
        )
        return None
    return Path(raw)


def resolve_elevation_path(country_code: str) -> Path | None:
    """Resolve the local Copernicus DEM elevation raster for one country.

    Args:
        country_code: ISO-3166-alpha-3 code. Must have an elevation_dir
            mapping in config/countries.yaml.

    Returns:
        Path to `<raw>/elevation/<dir>/<country_code>_elevation.tif`, or
        None if GEOFREA_RAW_DATA_DIR is unset or the file is genuinely
        absent on disk (logged, not raised in either case).

    Raises:
        CountryMappingError: If country_code is not in countries.yaml or
            if its elevation_dir mapping is null — a configuration gap,
            not a runtime condition (see module docstring).
    """
    country_dir = _get_country_mapping(country_code, "elevation_dir")

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


# Single GLOBAL file (Global Solar Atlas v2 long-term-average PVOUT),
# not a per-country raster — grid_alignment clips/reprojects it to each
# country's target grid. Confirmed 2026-09-11 by listing
# GEOFREA_RAW_DATA_DIR/solar_potential/. The sibling `World_TEMP_...`
# bundle (air temperature) is deliberately not matched — it is not a
# suitability_criteria input.
_SOLAR_PVOUT_RELPATH = Path(
    "solar_potential"
) / "World_PVOUT_GISdata_LTAy_AvgDailyTotals_GlobalSolarAtlas-v2_GEOTIFF" / "PVOUT.tif"


def resolve_solar_path(country_code: str) -> Path | None:
    """Resolve the local Global Solar Atlas PVOUT raster.

    Args:
        country_code: ISO-3166-alpha-3 code. Accepted for a uniform
            handler signature with the other resolvers, but UNUSED —
            solar is one global file, not country-split (unlike
            elevation/population/grid). grid_alignment clips and
            reprojects it to each country's grid downstream.

    Returns:
        Path to `<raw>/solar_potential/World_PVOUT_.../PVOUT.tif`, or None
        if GEOFREA_RAW_DATA_DIR is unset or the file is genuinely absent
        on disk (logged, not raised — same as resolve_elevation_path).
    """
    raw_data_dir = _raw_data_dir()
    if raw_data_dir is None:
        return None

    path = raw_data_dir / _SOLAR_PVOUT_RELPATH
    if not path.exists():
        logger.warning("Local solar PVOUT raster not found: %s", path)
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
        country_code: ISO-3166-alpha-3 code. Must have a land_cover_dir
            mapping in config/countries.yaml.

    Returns:
        Sorted list of tile Paths under
        `<raw>/land_cover/<dir>/ESA_WorldCover_10m_2020_v100_*_Map.tif`,
        or [] if GEOFREA_RAW_DATA_DIR is unset, the country directory
        does not exist, or it exists but contains no matching tile
        (logged, not raised in any of these cases).

    Raises:
        CountryMappingError: If country_code is not in countries.yaml or
            if its land_cover_dir mapping is null — a configuration gap,
            not a runtime condition (see module docstring).
    """
    country_dir = _get_country_mapping(country_code, "land_cover_dir")

    raw_data_dir = _raw_data_dir()
    if raw_data_dir is None:
        return []

    tiles_dir = raw_data_dir / "land_cover" / country_dir
    tiles = sorted(tiles_dir.glob(_LAND_COVER_TILE_GLOB))
    if not tiles:
        logger.warning("No local land_cover tiles found for %s under %s", country_code, tiles_dir)
    return tiles


def resolve_roads_path(country_code: str) -> Path | None:
    """Resolve the local GRIP4 regional roads shapefile covering one country.

    UNCLIPPED — this is the same shape of resolver as
    resolve_elevation_path() etc. (locate a path, do not process it),
    but the file itself spans many countries (GRIP4's continental
    region split), same as lakes/rivers/protected's global/continental
    source files. The per-country clip happens downstream, at
    inspection time, via data_quality_audit's existing
    inspect_vector_layer(clip=True) + read_clipped_to_country() +
    cache_path machinery — see module docstring.

    Args:
        country_code: ISO-3166-alpha-3 code. Must have grip4_region_dir
            and grip4_region_file mappings in config/countries.yaml —
            deliberately BRA/PRT only this stage (see module docstring
            for why extending this is blocked on a regions_lookup.json
            numbering conflict, not just unstarted work).

    Returns:
        Path to `<raw>/infrastructure/roads/<region_dir>/<region_file>.shp`,
        or None if GEOFREA_RAW_DATA_DIR is unset or the file is
        genuinely absent on disk (logged, not raised).

    Raises:
        CountryMappingError: If country_code is not in countries.yaml or
            if its grip4_region_dir or grip4_region_file mappings are null —
            a configuration gap, not a runtime condition (see module
            docstring; same treatment as elevation/land_cover above).
    """
    region_dir = _get_country_mapping(country_code, "grip4_region_dir")
    region_file = _get_country_mapping(country_code, "grip4_region_file")

    raw_data_dir = _raw_data_dir()
    if raw_data_dir is None:
        return None

    path = raw_data_dir / "infrastructure" / "roads" / region_dir / region_file
    if not path.exists():
        logger.warning("Local GRIP4 roads file not found for %s: %s", country_code, path)
        return None
    return path
