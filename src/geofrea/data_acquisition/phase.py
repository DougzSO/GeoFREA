"""data_acquisition phase entry point.

Registers the same way data_quality_audit does: a plain function
matching PhaseSpec.run's signature (Callable[[PhaseContext], BaseModel]),
constructed into a PhaseSpec by main.py's _build_phase_specs(). See
docs/DECISIONS.md 2026-08-24 (data_acquisition skeleton).

Unlike data_quality_audit's run_audit_phase(context, inputs), this
phase takes ONLY a PhaseContext: it has no phase-specific raw inputs to
receive from the caller — it IS the thing that would resolve raw paths
for later phases, so there is nothing upstream of it to bind via
functools.partial.

_LAYER_REGISTRY enumerates every raw layer geoworld_framework's
DataOrchestrator.acquire_all() handles, per the legacy audit performed
before this stage — EXCEPT "slope", deliberately excluded (see
schemas.py's module docstring): it is neither fetched nor bundled, and
GeoFREA derives it inside grid_alignment
(raster_alignment.derive_slope_from_dem(), 2026-09-11), from that
phase's elevation input — not here.

Real fetch logic: 2026-08-25 (see docs/DECISIONS.md same date — "real
fetchers for power_plants/wind/lakes/rivers") wired 4 of the 14 layers
(power_plants, wind, lakes, rivers) to a real fetcher instead of always
leaving path=None. 2026-08-26 (see DECISIONS.md same date) added
borders + admin1 (fetchers/gadm.py) — 6 of 14 now call a real fetcher.
_FETCHED_LAYER_HANDLERS below is the only place this phase knows about
individual fetcher modules.

Local-database resolution: 2026-09-08 Fase 1 (see docs/DECISIONS.md same
date — "wire das 5 camadas restantes a partir do banco local, Fase 1")
wired elevation/population/grid/land_cover to resolve a pre-placed path
from the local database (local_layers.py) instead of always leaving
path=None/paths=[] — no fetch/download logic involved, just locating
files already on disk. Fase 2 (same date, "...Fase 2 - roads") added
`roads` the same way, resolving to the raw GRIP4 regional shapefile
UNCLIPPED — unlike the 4 Fase-1 layers, the per-country clip for `roads`
happens downstream in data_quality_audit (inspect_vector_layer(clip=
True), same as lakes/rivers/protected), not in this phase; see
local_layers.py's module docstring. `solar` was
added 2026-09-11 the same way (single global Global Solar Atlas PVOUT
file, resolve_solar_path) — hard-required by suitability_criteria, which
could not run end-to-end without it. _LOCAL_PATH_HANDLERS /
_LOCAL_MULTI_PATH_HANDLERS below are the only places this phase knows
about local_layers.py. `protected` was activated 2026-09-11 (see
DECISIONS.md same date, "protected_planet API activation") — it now
calls a real fetcher too, wired into _FETCHED_LAYER_HANDLERS like the
other 6 (see fetchers/protected_planet.py's module docstring).
`seismic` remains out of scope (no confirmed automatable source and no
local resolver yet, see DECISIONS.md 2026-08-25). fetch_status is
UNCHANGED by the local-resolution wiring specifically — none of the 6
local-resolved layer_names (Fase 1 + Fase 2 above) are in
IMPLEMENTED_FETCH_LAYER_NAMES, so they keep reporting "not_implemented"
(resolving a local path is not the same
as GeoFREA's own code fetching one — see local_layers.py's module
docstring).

Orchestrator wiring note: the Orchestrator enforces NO ordering or
dependency between phases on its own — RunConfig.phases (settings.yaml)
is a flat enabled/disabled toggle map with no ordering semantics at
all; execution order is entirely the position of this PhaseSpec in the
list main.py passes to Orchestrator.run(). This phase MUST be placed
before data_quality_audit in that list for the (future) real fetch
logic to make sense — the orchestrator will not infer that.

settings.yaml does not have a "data_acquisition" key yet in
run.phases — adding one is a config change out of scope for this
stage (not touched here, still blocked pending review — see
DECISIONS.md 2026-08-25). Until it's added,
phases_enabled.get("data_acquisition", False) defaults to False and
this phase is skipped entirely by Orchestrator.run(), same as any
other unlisted phase name.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

from geofrea.core.orchestrator import PhaseContext
from geofrea.data_acquisition.fetchers.gadm import fetch_admin1, fetch_borders
from geofrea.data_acquisition.fetchers.hydrosheds import fetch_lakes, fetch_rivers
from geofrea.data_acquisition.fetchers.power_plants import fetch_power_plants
from geofrea.data_acquisition.fetchers.protected_planet import fetch_protected_areas
from geofrea.data_acquisition.fetchers.wind import fetch_wind
from geofrea.data_acquisition.local_layers import (
    resolve_elevation_path,
    resolve_grid_path,
    resolve_land_cover_tiles,
    resolve_population_path,
    resolve_roads_path,
    resolve_solar_path,
)
from geofrea.data_acquisition.schemas import (
    IMPLEMENTED_FETCH_LAYER_NAMES,
    MULTI_FILE_LAYER_NAMES,
    AcquiredLayer,
    AcquisitionResult,
    AcquisitionSummary,
)

logger = logging.getLogger("geofrea.data_acquisition.phase")

# layer_name -> fetch function, for the 7 layers with a real fetcher
# wired in as of 2026-09-11 (see module docstring). Each fetcher
# already catches its own network/parsing failures internally and
# returns None rather than raising (see fetchers/*.py) — deliberate
# exceptions are hydrosheds.fetch_rivers() raising KeyError for a
# country outside _COUNTRY_TO_REGION, and protected_planet.
# fetch_protected_areas() raising ProtectedPlanetTokenMissingError when
# no token is configured. Both are intentionally NOT caught here
# either: an unmapped country or a missing token are configuration
# gaps, not transient failures, so they should fail this phase loudly
# (surfaced via the Orchestrator's own PhaseExecutionError) rather
# than silently degrade to path=None like a real network error would.
_FETCHED_LAYER_HANDLERS: dict[str, Callable[[PhaseContext], Path | None]] = {
    "power_plants": lambda ctx: fetch_power_plants(ctx.outputs_dir),
    "wind": lambda ctx: fetch_wind(ctx.outputs_dir, ctx.country_code),
    "lakes": lambda ctx: fetch_lakes(ctx.outputs_dir),
    "rivers": lambda ctx: fetch_rivers(ctx.outputs_dir, ctx.country_code),
    "borders": lambda ctx: fetch_borders(ctx.outputs_dir, ctx.country_code),
    "admin1": lambda ctx: fetch_admin1(ctx.outputs_dir, ctx.country_code),
    # Activated 2026-09-11 (see DECISIONS.md same date, "protected_planet
    # API activation") once a real PROTECTED_PLANET_API_KEY was placed
    # in .env — fetch_protected_areas reads it from the environment
    # itself (api_token=None default), same as every other credentialed
    # fetcher in this dict reading its own env var internally.
    "protected": lambda ctx: fetch_protected_areas(ctx.outputs_dir, ctx.country_code),
}

# AcquiredLayer.fetch_status (schemas.py, a computed field) mirrors
# this dict's keys via IMPLEMENTED_FETCH_LAYER_NAMES rather than
# importing this dict directly (schemas.py is imported by this module,
# so the reverse import would be circular). Asserted here, at import
# time, so the two cannot silently drift apart — same rationale as the
# MULTI_FILE_LAYER_NAMES consolidation (see DECISIONS.md 2026-08-24,
# "path/paths source-of-truth consolidation").
assert set(_FETCHED_LAYER_HANDLERS) == IMPLEMENTED_FETCH_LAYER_NAMES, (
    "_FETCHED_LAYER_HANDLERS and schemas.IMPLEMENTED_FETCH_LAYER_NAMES "
    "have drifted apart — update both together."
)

# layer_name -> local-database resolver, for the 4 single-path layers
# wired 2026-09-08 (see module docstring, "Local-database resolution").
# Deliberately a SEPARATE dict from _FETCHED_LAYER_HANDLERS, not merged
# into it: these resolvers do no fetch/download at all (local_layers.py
# is not a fetcher module), and none of these layer_names belong in
# IMPLEMENTED_FETCH_LAYER_NAMES/fetch_status — see that module's
# docstring for why "resolved locally" and "fetched by GeoFREA's own
# code" are deliberately different facts.
_LOCAL_PATH_HANDLERS: dict[str, Callable[[str], Path | None]] = {
    "elevation": lambda country_code: resolve_elevation_path(country_code),
    "population": lambda country_code: resolve_population_path(country_code),
    "grid": lambda country_code: resolve_grid_path(country_code),
    "roads": lambda country_code: resolve_roads_path(country_code),
    "solar": lambda country_code: resolve_solar_path(country_code),
}

# land_cover is multi-file (MULTI_FILE_LAYER_NAMES) — kept in its own
# dict rather than _LOCAL_PATH_HANDLERS since it returns list[Path], not
# Path | None, same path/paths split as elsewhere in this module.
#
# Every handler above and below is a lambda that calls the resolver by
# name, not a direct function reference — same pattern
# _FETCHED_LAYER_HANDLERS already uses (module docstring's lambdas call
# fetch_power_plants() etc. by name). This is not stylistic: a direct
# reference would bind the function object at dict-construction time,
# so a test's monkeypatch.setattr(phase_module, "resolve_elevation_path", ...)
# would silently miss it — the lambda instead looks the name up in this
# module's globals on every call, which is what makes that monkeypatch
# pattern work at all (confirmed by the test suite, not assumed).
_LOCAL_MULTI_PATH_HANDLERS: dict[str, Callable[[str], list[Path]]] = {
    "land_cover": lambda country_code: resolve_land_cover_tiles(country_code),
}

assert not set(_LOCAL_PATH_HANDLERS) & set(_FETCHED_LAYER_HANDLERS), (
    "_LOCAL_PATH_HANDLERS and _FETCHED_LAYER_HANDLERS overlap — a layer_name "
    "should resolve from exactly one of a real fetcher or the local database, "
    "not both."
)
assert not set(_LOCAL_MULTI_PATH_HANDLERS) & set(_FETCHED_LAYER_HANDLERS), (
    "_LOCAL_MULTI_PATH_HANDLERS and _FETCHED_LAYER_HANDLERS overlap — same "
    "requirement as _LOCAL_PATH_HANDLERS above."
)


class _LayerSpec(NamedTuple):
    layer_name: str
    provenance: str  # "fetched" | "local_only"
    auth_required: bool
    source_name: str
    country_specific: bool
    # No `multi_file` flag here anymore (removed 2026-08-24, see
    # DECISIONS.md same date, "path/paths source-of-truth
    # consolidation"): whether a layer is multi-file is decided
    # exclusively by schemas.py's MULTI_FILE_LAYER_NAMES, consulted
    # directly in run_acquisition_phase() below — a per-entry flag here
    # would be a second, independently-editable source of truth for
    # the same fact, exactly the drift risk that prompted this change.


# Per the legacy audit (geoworld_framework's DataFetcher/DataManager/
# DataOrchestrator): only 6 download_* methods exist in the whole
# codebase (gadm, land_cover, elevation, worldpop, osm_grid,
# osm_roads) — the original skeleton (DECISIONS.md 2026-08-24) treated
# all 6 as "fetched" on that basis, since a fetch mechanism existed in
# legacy even where GeoFREA had not yet ported it.
#
# REVERTED 2026-08-24 -> 2026-09-08 for land_cover/elevation/population/
# grid/roads (see DECISIONS.md 2026-09-08, "wire das 5 camadas
# restantes a partir do banco local", Fase 1 for the first 4, Fase 2 for
# roads — NOT a bug fix, an explicit scope reversal in both cases):
# these 5 now resolve from pre-placed files in the local database
# (local_layers.py) instead, same as solar/seismic/protected always
# have — so they are local_only now, matching how they are actually
# acquired today, not how legacy could in principle acquire them.
# land_cover in particular reverses the original skeleton's
# auth_required=True (Terrascope credentials) — the local tiles need no
# auth at all. `roads` also flips country_specific True -> False (Fase
# 2): its source changed from a per-country OSM download to a single
# GRIP4 regional shapefile shared across many countries, clipped
# per-country downstream by data_quality_audit — the same pattern
# lakes/rivers/protected already use, and the same reason those three
# are country_specific=False (see the comment above them below).
#
# land_cover is multi-file (see schemas.py's MULTI_FILE_LAYER_NAMES,
# the single source of truth — not repeated here as a flag): wind is
# also multi-file at its source, but stays on AcquiredLayer.path by
# decision (see schemas.py module docstring, "wind vs. land_cover",
# DECISIONS.md 2026-08-24).
#
# provenance for power_plants/wind/lakes/rivers changed from
# local_only to fetched 2026-08-25 (see DECISIONS.md same date, "real
# fetchers for power_plants/wind/lakes/rivers") — real, live-verified
# fetchers now exist for these 4 (fetchers/power_plants.py,
# fetchers/wind.py, fetchers/hydrosheds.py). borders/admin1 already
# said "fetched" from the original skeleton (see AcquiredLayer's own
# provenance docstring, "fetched" means "comes OR WOULD come from a
# live external source") — 2026-08-26 gave them a real handler too
# (fetchers/gadm.py), with no provenance value change needed since it
# was already correct. `protected` joined "fetched" 2026-09-11 (see
# DECISIONS.md same date, "protected_planet API activation") once a
# real PROTECTED_PLANET_API_KEY was placed in .env — its fetcher
# (fetchers/protected_planet.py) was already complete and tested, just
# gated behind a manual token before now. All 7 wired below via
# _FETCHED_LAYER_HANDLERS. provenance is NOT a proxy for "has a real
# fetcher today" — see AcquiredLayer.fetch_status, schemas.py, for the
# field that actually answers that question. `solar` stays local_only
# but now has a local resolver (resolve_solar_path, 2026-09-11);
# `seismic` stays local_only with no resolver yet — no confirmed
# automatable source.
_LAYER_REGISTRY: tuple[_LayerSpec, ...] = (
    _LayerSpec("borders", "fetched", False, "GADM 4.1 (fallback: NaturalEarth)", True),
    _LayerSpec("admin1", "fetched", False, "GADM 4.1 (level-1, same download as borders)", True),
    _LayerSpec(
        "land_cover",
        "local_only",
        False,
        "ESA WorldCover 10m (local bundled tiles, pre-downloaded — "
        "reverted from Terrascope live fetch, see DECISIONS.md 2026-09-08)",
        True,
    ),
    _LayerSpec(
        "elevation",
        "local_only",
        False,
        "Copernicus DEM 30m (local bundled file, pre-downloaded)",
        True,
    ),
    _LayerSpec(
        "population", "local_only", False, "WorldPop (local bundled file, pre-downloaded)", True
    ),
    _LayerSpec(
        "grid",
        "local_only",
        False,
        "OpenStreetMap (local bundled file, pre-downloaded via Overpass)",
        True,
    ),
    _LayerSpec(
        "roads",
        "local_only",
        False,
        "GRIP4 (Global Roads Inventory Project) — local bundled regional "
        "shapefile, pre-downloaded, clipped per-country downstream — "
        "reverted from OSM/Overpass live fetch, see DECISIONS.md 2026-09-08",
        False,
    ),
    _LayerSpec("wind", "fetched", False, "Global Wind Atlas 3.0 (globalwindatlas.info/api)", True),
    # country_specific corrected 2026-08-24 (see DECISIONS.md same date,
    # "vector layer audit depth"): was True in the original skeleton,
    # inconsistent with how WDPA is actually consumed in legacy —
    # criteria_builder.py::compute_protected_areas(wdpa_path, ...) treats
    # it as a single global file clipped per-country, the same pattern
    # as lakes/rivers (both country_specific=False below), not a file
    # fetched or scoped separately per country.
    _LayerSpec(
        "protected",
        "fetched",
        True,
        "Protected Planet / WDPA API (api.protectedplanet.net/v4) — "
        "activated 2026-09-11, see DECISIONS.md same date",
        False,
    ),
    _LayerSpec("solar", "local_only", False, "local bundled file (global PVOUT, no confirmed automatable source)", False),
    _LayerSpec("lakes", "fetched", False, "HydroSHEDS (HydroLAKES global file, data.hydrosheds.org)", False),
    _LayerSpec("rivers", "fetched", False, "HydroSHEDS (HydroRIVERS regional tile, data.hydrosheds.org)", False),
    _LayerSpec("seismic", "local_only", False, "local bundled file (source unidentified — no URL in legacy)", False),
    _LayerSpec("power_plants", "fetched", False, "WRI Global Power Plant Database (GitHub, pinned commit)", False),
)


def run_acquisition_phase(context: PhaseContext) -> AcquisitionResult:
    """Build an AcquisitionResult for one country.

    7 layers (power_plants, wind, lakes, rivers, borders, admin1,
    protected — see _FETCHED_LAYER_HANDLERS) call a real fetcher and
    may have a real `path` populated. 6 more (elevation, population,
    grid, roads, land_cover, solar — see _LOCAL_PATH_HANDLERS /
    _LOCAL_MULTI_PATH_HANDLERS) resolve a pre-placed path/paths from
    the local database instead — no fetch/download involved (see
    local_layers.py's module docstring). The remaining layer (seismic)
    is still a structural placeholder — path=None — no fetcher/resolver
    exists for it yet (see module docstring).

    Args:
        context: Shared phase context (country_code, outputs_dir, ...).

    Returns:
        A validated AcquisitionResult.
    """
    logger.info("data_acquisition: %s", context.country_code)
    started_at = datetime.now(UTC)

    layers = []
    for spec in _LAYER_REGISTRY:
        # MULTI_FILE_LAYER_NAMES (schemas.py) is the single source of
        # truth for path vs. paths (see DECISIONS.md 2026-08-24,
        # "path/paths source-of-truth consolidation").
        is_multi_file = spec.layer_name in MULTI_FILE_LAYER_NAMES

        fetch_handler = _FETCHED_LAYER_HANDLERS.get(spec.layer_name)
        local_handler = _LOCAL_PATH_HANDLERS.get(spec.layer_name)
        # Disjoint by construction (asserted above at import time), so
        # at most one of these two ever applies to a given layer_name.
        if fetch_handler:
            path = fetch_handler(context)
        elif local_handler:
            path = local_handler(context.country_code)
        else:
            path = None

        local_multi_handler = _LOCAL_MULTI_PATH_HANDLERS.get(spec.layer_name)
        paths = local_multi_handler(context.country_code) if local_multi_handler else []

        layers.append(
            AcquiredLayer(
                layer_name=spec.layer_name,
                provenance=spec.provenance,
                auth_required=spec.auth_required,
                source_name=spec.source_name,
                country_code=context.country_code if spec.country_specific else None,
                path=None if is_multi_file else path,
                paths=paths,
                crs_metadata=None,
            )
        )

    summary = AcquisitionSummary(
        layers_total=len(layers),
        layers_fetched_provenance=sum(1 for layer in layers if layer.provenance == "fetched"),
        layers_local_only_provenance=sum(
            1 for layer in layers if layer.provenance == "local_only"
        ),
        layers_requiring_auth=sum(1 for layer in layers if layer.auth_required),
        layers_resolved=sum(1 for layer in layers if layer.path is not None or layer.paths),
    )

    return AcquisitionResult(
        country_code=context.country_code,
        timestamp=started_at.isoformat(),
        layers=layers,
        summary=summary,
    )
