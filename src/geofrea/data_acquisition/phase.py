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
fetch_status is UNCHANGED by the local-resolution wiring specifically — none of the 6
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

import hashlib
import logging
import time
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

import geopandas as gpd

from geofrea.core.orchestrator import PhaseContext
from geofrea.data_acquisition.fetchers.gadm import fetch_admin1, fetch_borders
from geofrea.data_acquisition.fetchers.hydrosheds import fetch_lakes, fetch_rivers
from geofrea.data_acquisition.fetchers.power_plants import fetch_power_plants
from geofrea.data_acquisition.fetchers.protected_planet import fetch_protected_areas
from geofrea.data_acquisition.fetchers.wind import (
    GWA_HEIGHTS_M,
    GWA_PRODUCTS,
    fetch_gwa_product,
    fetch_wind,
)
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


class DataAcquisitionLayerFailedError(RuntimeError):
    """One or more layers failed to resolve (per-layer isolation, 2026-09-23).

    Raised AFTER the full AcquisitionResult — including every layer that
    DID resolve — has been built and registered as the "layer_registry"
    artifact (see run_acquisition_phase()'s caller, main.py::
    _data_acquisition_run). This is what makes the orchestrator record
    the phase's own status as "failed" (A-09 still stops dependents),
    while the artifact itself still holds what succeeded (A-02) — unlike
    a raw exception from inside the resolution loop, which would abort
    before anything got registered at all (the prior behavior; see
    docs/phases/F1_data_acquisition.md for the IND case this replaced).
    """

    def __init__(self, country_code: str, failed_layer_names: list[str]) -> None:
        super().__init__(
            f"data_acquisition for {country_code!r}: layer(s) "
            f"{failed_layer_names} failed to resolve — see the "
            "layer_registry artifact for each one's exception and file:line."
        )
        self.country_code = country_code
        self.failed_layer_names = failed_layer_names

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

# M-F1-03 (2026-09-23, task F1-2): the 11 GWA product/height
# combinations beyond the existing "wind" entry (= wind_speed at
# 100 m, fetch_wind() above, unchanged). Generated from
# fetchers/wind.py's GWA_PRODUCTS x GWA_HEIGHTS_M rather than written
# out by hand, so the registry, IMPLEMENTED_FETCH_LAYER_NAMES
# (schemas.py) and this dict cannot silently drift apart — the
# `product`/`height_m` default-argument binding below (`p=product,
# h=height`) avoids the classic late-binding closure bug (every lambda
# would otherwise capture the *same* loop variable's final value).
# fetch_gwa_product() raises rather than returning None (see its
# docstring) — a missing product/height fails that one layer only,
# per phase.py's existing per-layer isolation, never the whole phase.
_GWA_EXTRA_LAYER_SPECS: tuple[tuple[str, str, int], ...] = tuple(
    (f"{product}_{height}m", product, height)
    for product in GWA_PRODUCTS
    for height in GWA_HEIGHTS_M
    if not (product == "wind_speed" and height == 100)  # already "wind"
)

for _layer_name, _product, _height in _GWA_EXTRA_LAYER_SPECS:
    _FETCHED_LAYER_HANDLERS[_layer_name] = (
        lambda ctx, p=_product, h=_height: fetch_gwa_product(ctx.outputs_dir, ctx.country_code, p, h)
    )
del _layer_name, _product, _height

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
_LOCAL_MULTI_PATH_HANDLERS: dict[str, Callable[[str, gpd.GeoDataFrame | None], list[Path]]] = {
    # country_gdf: the borders polygon fetched earlier in this same
    # loop (see run_acquisition_phase()'s _borders_gdf), used by
    # resolve_land_cover_tiles()'s real polygon-overlap filter — see
    # that function's docstring for the TILE-SCAN rationale.
    "land_cover": lambda country_code, country_gdf: resolve_land_cover_tiles(
        country_code, country_gdf
    ),
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


# Per-layer hashing budget (docs/phases/core.md D-core-016, resolving
# OQ-024). Measured 2026-09-23 against every layer already resolved for
# BRA and PRT (F1-1b action 1): the worst case was BRA's land_cover at
# ~55.8s (112 tiles, 6.2 GB) and BRA's population at ~30.2s (4.2 GB) —
# both under this budget, so no layer is skipped for cost today. Not
# tuned to those two files specifically; it is the "exceeds one minute
# per country" ceiling the verdict itself specified.
_HASH_BUDGET_S = 60.0

_HASH_CHUNK_BYTES = 1 << 20  # 1 MiB


def _sha256_file(path: Path) -> str:
    """Hash one file's bytes in fixed-size chunks (no full-file read into memory)."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(_HASH_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _hash_layer_files(files: list[Path]) -> tuple[dict[str, str] | None, str | None]:
    """Hash every file a layer resolved to, within `_HASH_BUDGET_S` per layer.

    A fact about the file, recorded once at resolve time — never a gate
    (see AcquiredLayer.source_sha256's docstring, schemas.py). Runs
    inside the same per-layer try/except as fetch/resolve in
    run_acquisition_phase() below, so a real hashing failure (e.g. the
    file vanishing between resolve and hash) surfaces as that layer's
    own resolution_status="failed", same as a fetch/resolve exception —
    not swallowed here.

    Args:
        files: The layer's resolved file(s) — `[path]` for a
            single-file layer, `paths` for a multi-file one. Empty if
            nothing resolved.

    Returns:
        (source_sha256, skipped_reason): exactly one is None.
        source_sha256 is None with no reason when `files` is empty
        (nothing to hash, nothing to explain); None with a reason when
        the budget was exceeded partway through; otherwise a full
        {path_str: hexdigest} dict.
    """
    if not files:
        return None, None

    digests: dict[str, str] = {}
    started = time.perf_counter()
    for fp in files:
        digests[str(fp)] = _sha256_file(fp)
        if time.perf_counter() - started > _HASH_BUDGET_S:
            return None, (
                f"hashing {len(files)} file(s) exceeded the {_HASH_BUDGET_S:.0f}s "
                f"per-layer budget after {len(digests)} file(s) — "
                "see docs/phases/core.md D-core-016"
            )
    return digests, None


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
# (local_layers.py) instead, same as solar/protected always
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
# but now has a local resolver (resolve_solar_path, 2026-09-11).
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
    # M-F1-03 (2026-09-23, task F1-2): the 11 remaining GWA product/
    # height registry entries — generated from _GWA_EXTRA_LAYER_SPECS
    # above so this tuple, _FETCHED_LAYER_HANDLERS and
    # IMPLEMENTED_FETCH_LAYER_NAMES (schemas.py) all enumerate the same
    # 11 names. Each is its own fetched, country-specific, no-auth
    # layer, same shape as "wind" itself.
    *(
        _LayerSpec(
            layer_name,
            "fetched",
            False,
            f"Global Wind Atlas 3.0 (globalwindatlas.info/api, {product} @ {height}m)",
            True,
        )
        for layer_name, product, height in _GWA_EXTRA_LAYER_SPECS
    ),
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
    local_layers.py's module docstring).

    Args:
        context: Shared phase context (country_code, outputs_dir, ...).

    Returns:
        A validated AcquisitionResult.
    """
    logger.info("data_acquisition: %s", context.country_code)
    started_at = datetime.now(UTC)

    layers = []
    # Populated once "borders" (first in _LAYER_REGISTRY) is fetched,
    # then reused by the "land_cover" handler's real polygon-overlap
    # filter (resolve_land_cover_tiles()'s country_gdf argument) — see
    # that function's docstring, TILE-SCAN, 2026-09-22. Stays None if
    # the borders fetch failed/returned no path, or the shapefile
    # can't be read; the filter degrades gracefully to
    # excluded_land_cover_tiles-only in that case.
    borders_gdf: gpd.GeoDataFrame | None = None
    for spec in _LAYER_REGISTRY:
        # MULTI_FILE_LAYER_NAMES (schemas.py) is the single source of
        # truth for path vs. paths (see DECISIONS.md 2026-08-24,
        # "path/paths source-of-truth consolidation").
        is_multi_file = spec.layer_name in MULTI_FILE_LAYER_NAMES

        fetch_handler = _FETCHED_LAYER_HANDLERS.get(spec.layer_name)
        local_handler = _LOCAL_PATH_HANDLERS.get(spec.layer_name)
        local_multi_handler = _LOCAL_MULTI_PATH_HANDLERS.get(spec.layer_name)

        # Per-layer isolation (2026-09-23, see docs/phases/F1_data_acquisition.md
        # — the IND/hydrosheds_region case that motivated this): one
        # layer's resolver raising no longer aborts the whole phase
        # (which used to discard every other already-resolved layer,
        # see git history of this function). Each layer resolves
        # independently; a raised exception is recorded on ITS OWN
        # AcquiredLayer entry (resolution_status="failed" + exception
        # type/file:line/message) and the loop continues.
        path: Path | None = None
        paths: list[Path] = []
        source_sha256: dict[str, str] | None = None
        source_sha256_skipped_reason: str | None = None
        resolution_status = "resolved"
        error_type: str | None = None
        error_location: str | None = None
        error_message: str | None = None
        try:
            # Disjoint by construction (asserted above at import time),
            # so at most one of these two ever applies to a given
            # layer_name.
            if fetch_handler:
                path = fetch_handler(context)
            elif local_handler:
                path = local_handler(context.country_code)

            if spec.layer_name == "borders" and path is not None:
                try:
                    borders_gdf = gpd.read_file(path)
                except Exception:
                    logger.warning(
                        "Could not read borders shapefile %s for land_cover's "
                        "polygon-overlap filter — falling back to "
                        "excluded_land_cover_tiles only.",
                        path,
                        exc_info=True,
                    )

            if local_multi_handler:
                paths = local_multi_handler(context.country_code, borders_gdf)

            hashed_files = [path] if (path is not None and not is_multi_file) else paths
            source_sha256, source_sha256_skipped_reason = _hash_layer_files(hashed_files)
        except Exception as exc:  # noqa: BLE001 — one layer's failure must not abort the others
            path = None
            paths = []
            source_sha256 = None
            source_sha256_skipped_reason = None
            resolution_status = "failed"
            error_type = type(exc).__name__
            error_message = str(exc)
            tb = traceback.extract_tb(exc.__traceback__)
            error_location = f"{tb[-1].filename}:{tb[-1].lineno}" if tb else "unknown"
            logger.error(
                "Layer '%s' failed to resolve for %s: %s at %s: %s",
                spec.layer_name,
                context.country_code,
                error_type,
                error_location,
                error_message,
            )

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
                source_sha256=source_sha256,
                source_sha256_skipped_reason=source_sha256_skipped_reason,
                resolution_status=resolution_status,
                error_type=error_type,
                error_location=error_location,
                error_message=error_message,
            )
        )

    failed_layer_names = [layer.layer_name for layer in layers if layer.resolution_status == "failed"]

    summary = AcquisitionSummary(
        layers_total=len(layers),
        layers_fetched_provenance=sum(1 for layer in layers if layer.provenance == "fetched"),
        layers_local_only_provenance=sum(
            1 for layer in layers if layer.provenance == "local_only"
        ),
        layers_requiring_auth=sum(1 for layer in layers if layer.auth_required),
        layers_resolved=sum(1 for layer in layers if layer.path is not None or layer.paths),
        layers_failed=len(failed_layer_names),
    )

    # Deliberately does NOT raise here even if failed_layer_names is
    # non-empty: this function always returns the full result — every
    # layer that DID resolve, plus each failed one's own record — so
    # the caller (main.py::_data_acquisition_run) can register it as
    # the "layer_registry" artifact (A-02) BEFORE deciding whether the
    # phase's own status should read "failed" (A-09). Raising here
    # would discard the result before it could ever be registered,
    # reproducing the exact problem this whole mechanism replaced.
    return AcquisitionResult(
        country_code=context.country_code,
        timestamp=started_at.isoformat(),
        layers=layers,
        summary=summary,
    )
