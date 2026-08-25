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
schemas.py's module docstring: it's derived from elevation, not fetched
or bundled, so it doesn't fit either provenance value).

Real fetch logic (2026-08-25, see docs/DECISIONS.md same date —
"real fetchers for power_plants/wind/lakes/rivers"): 4 of the 14
layers (power_plants, wind, lakes, rivers) now call a real fetcher
from data_acquisition/fetchers/ instead of always leaving path=None.
The other 10 remain structural placeholders — either genuinely
unimplemented (borders/admin1/land_cover/elevation/population/grid/
roads, still skeleton) or implemented-but-not-activated (protected —
see fetchers/protected_planet.py's module docstring for why) or
explicitly out of scope this stage (solar, seismic — no confirmed
per-country/automatable source, see DECISIONS.md same date).
_FETCHED_LAYER_HANDLERS below is the only place this phase knows about
individual fetcher modules — everything else in this file is unchanged
from the skeleton.

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
from geofrea.data_acquisition.fetchers.hydrosheds import fetch_lakes, fetch_rivers
from geofrea.data_acquisition.fetchers.power_plants import fetch_power_plants
from geofrea.data_acquisition.fetchers.wind import fetch_wind
from geofrea.data_acquisition.schemas import (
    MULTI_FILE_LAYER_NAMES,
    AcquiredLayer,
    AcquisitionResult,
    AcquisitionSummary,
)

logger = logging.getLogger("geofrea.data_acquisition.phase")

# layer_name -> fetch function, for the 4 layers with a real fetcher
# wired in as of 2026-08-25 (see module docstring). Each fetcher
# already catches its own network/parsing failures internally and
# returns None rather than raising (see fetchers/*.py) — the one
# deliberate exception is hydrosheds.fetch_rivers() raising KeyError
# for a country outside _COUNTRY_TO_REGION, which is intentionally
# NOT caught here either: an unmapped country is a configuration gap,
# not a transient failure, so it should fail this phase loudly
# (surfaced via the Orchestrator's own PhaseExecutionError) rather
# than silently degrade to path=None like a real network error would.
_FETCHED_LAYER_HANDLERS: dict[str, Callable[[PhaseContext], Path | None]] = {
    "power_plants": lambda ctx: fetch_power_plants(ctx.outputs_dir),
    "wind": lambda ctx: fetch_wind(ctx.outputs_dir, ctx.country_code),
    "lakes": lambda ctx: fetch_lakes(ctx.outputs_dir),
    "rivers": lambda ctx: fetch_rivers(ctx.outputs_dir, ctx.country_code),
}


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
# osm_roads); every other layer has no fetch mechanism whatsoever and
# must be a pre-placed local file. Only Land Cover (Terrascope) needs
# credentials — confirmed via geoworld_framework's
# ConfigLoader.credentials, which exposes exactly
# terrascope_username/terrascope_password and nothing else.
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
# fetchers/wind.py, fetchers/hydrosheds.py), wired below via
# _FETCHED_LAYER_HANDLERS. `protected` stays local_only even though a
# real fetcher exists for it too (fetchers/protected_planet.py) —
# gated behind a manual API token, not activated here (see that
# module's docstring). `solar`/`seismic` stay local_only — no
# confirmed automatable source this stage.
_LAYER_REGISTRY: tuple[_LayerSpec, ...] = (
    _LayerSpec("borders", "fetched", False, "GADM 4.1 (fallback: NaturalEarth)", True),
    _LayerSpec("admin1", "fetched", False, "GADM 4.1 (level-1, same download as borders)", True),
    _LayerSpec("land_cover", "fetched", True, "Terrascope (ESA WorldCover 10m)", True),
    _LayerSpec("elevation", "fetched", False, "Copernicus DEM 30m (public S3)", True),
    _LayerSpec("population", "fetched", False, "WorldPop", True),
    _LayerSpec("grid", "fetched", False, "OpenStreetMap (Overpass API)", True),
    _LayerSpec("roads", "fetched", False, "OpenStreetMap (Overpass API)", True),
    _LayerSpec("wind", "fetched", False, "Global Wind Atlas 3.0 (globalwindatlas.info/api)", True),
    # country_specific corrected 2026-08-24 (see DECISIONS.md same date,
    # "vector layer audit depth"): was True in the original skeleton,
    # inconsistent with how WDPA is actually consumed in legacy —
    # criteria_builder.py::compute_protected_areas(wdpa_path, ...) treats
    # it as a single global file clipped per-country, the same pattern
    # as lakes/rivers (both country_specific=False below), not a file
    # fetched or scoped separately per country.
    _LayerSpec("protected", "local_only", False, "Protected Planet / WDPA API — fetcher ready, gated by manual token", False),
    _LayerSpec("solar", "local_only", False, "local bundled file (global PVOUT, no confirmed automatable source)", False),
    _LayerSpec("lakes", "fetched", False, "HydroSHEDS (HydroLAKES global file, data.hydrosheds.org)", False),
    _LayerSpec("rivers", "fetched", False, "HydroSHEDS (HydroRIVERS regional tile, data.hydrosheds.org)", False),
    _LayerSpec("seismic", "local_only", False, "local bundled file (source unidentified — no URL in legacy)", False),
    _LayerSpec("power_plants", "fetched", False, "WRI Global Power Plant Database (GitHub, pinned commit)", False),
)


def run_acquisition_phase(context: PhaseContext) -> AcquisitionResult:
    """Build an AcquisitionResult for one country.

    4 layers (power_plants, wind, lakes, rivers — see
    _FETCHED_LAYER_HANDLERS) call a real fetcher and may have a real
    `path` populated. Every other layer is still a structural
    placeholder — path=None, paths=[] — either because no fetcher
    exists yet, or because one exists but is deliberately not wired in
    (see module docstring).

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
        # "path/paths source-of-truth consolidation") — none of the 4
        # real fetchers wired in below produce a multi-file layer, so
        # `paths` stays [] unconditionally here; only `path` varies.
        is_multi_file = spec.layer_name in MULTI_FILE_LAYER_NAMES

        handler = _FETCHED_LAYER_HANDLERS.get(spec.layer_name)
        path = handler(context) if handler else None

        layers.append(
            AcquiredLayer(
                layer_name=spec.layer_name,
                provenance=spec.provenance,
                auth_required=spec.auth_required,
                source_name=spec.source_name,
                country_code=context.country_code if spec.country_specific else None,
                path=None if is_multi_file else path,
                paths=[],
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
