"""data_acquisition phase entry point — STRUCTURE ONLY, no fetch logic.

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

Orchestrator wiring note: the Orchestrator enforces NO ordering or
dependency between phases on its own — RunConfig.phases (settings.yaml)
is a flat enabled/disabled toggle map with no ordering semantics at
all; execution order is entirely the position of this PhaseSpec in the
list main.py passes to Orchestrator.run(). This phase MUST be placed
before data_quality_audit in that list for the (future) real fetch
logic to make sense — the orchestrator will not infer that.

settings.yaml does not have a "data_acquisition" key yet in
run.phases — adding one is a config change out of scope for this
skeleton stage (not touched here). Until it's added,
phases_enabled.get("data_acquisition", False) defaults to False and
this phase is skipped entirely by Orchestrator.run(), same as any
other unlisted phase name.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import NamedTuple

from geofrea.core.orchestrator import PhaseContext
from geofrea.data_acquisition.schemas import (
    MULTI_FILE_LAYER_NAMES,
    AcquiredLayer,
    AcquisitionResult,
    AcquisitionSummary,
)

logger = logging.getLogger("geofrea.data_acquisition.phase")


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
# also multi-file in legacy, but stays on AcquiredLayer.path by
# decision (see schemas.py module docstring, "wind vs. land_cover",
# DECISIONS.md 2026-08-24).
_LAYER_REGISTRY: tuple[_LayerSpec, ...] = (
    _LayerSpec("borders", "fetched", False, "GADM 4.1 (fallback: NaturalEarth)", True),
    _LayerSpec("admin1", "fetched", False, "GADM 4.1 (level-1, same download as borders)", True),
    _LayerSpec("land_cover", "fetched", True, "Terrascope (ESA WorldCover 10m)", True),
    _LayerSpec("elevation", "fetched", False, "Copernicus DEM 30m (public S3)", True),
    _LayerSpec("population", "fetched", False, "WorldPop", True),
    _LayerSpec("grid", "fetched", False, "OpenStreetMap (Overpass API)", True),
    _LayerSpec("roads", "fetched", False, "OpenStreetMap (Overpass API)", True),
    _LayerSpec("wind", "local_only", False, "local bundled file (no fetch method in legacy)", True),
    # country_specific corrected 2026-08-24 (see DECISIONS.md same date,
    # "vector layer audit depth"): was True in the original skeleton,
    # inconsistent with how WDPA is actually consumed in legacy —
    # criteria_builder.py::compute_protected_areas(wdpa_path, ...) treats
    # it as a single global file clipped per-country, the same pattern
    # as lakes/rivers (both country_specific=False below), not a file
    # fetched or scoped separately per country.
    _LayerSpec("protected", "local_only", False, "local bundled file (WDPA, no fetch method)", False),
    _LayerSpec("solar", "local_only", False, "local bundled file (global PVOUT, no fetch method)", False),
    _LayerSpec("lakes", "local_only", False, "local bundled file (HydroLAKES, global, no fetch method)", False),
    _LayerSpec("rivers", "local_only", False, "local bundled file (HydroRIVERS, global, no fetch method)", False),
    _LayerSpec("seismic", "local_only", False, "local bundled file (global hazard raster, no fetch method)", False),
    _LayerSpec("power_plants", "local_only", False, "local bundled CSV (global_power_plant_database.csv)", False),
)


def run_acquisition_phase(context: PhaseContext) -> AcquisitionResult:
    """Build a placeholder AcquisitionResult for one country.

    No file is read, no network call is made, no .env variable is
    read. Every AcquiredLayer.path/paths is empty — this only
    establishes the structural contract that a real fetch
    implementation will populate later.

    Args:
        context: Shared phase context (country_code, outputs_dir, ...).

    Returns:
        A validated AcquisitionResult with placeholder layers.
    """
    logger.info(
        "data_acquisition (skeleton, no fetch logic): %s", context.country_code
    )
    started_at = datetime.now(UTC)

    layers = []
    for spec in _LAYER_REGISTRY:
        # MULTI_FILE_LAYER_NAMES (schemas.py) is read directly here,
        # not a per-registry `multi_file` flag (removed 2026-08-24 —
        # see DECISIONS.md same date, "path/paths source-of-truth
        # consolidation"). path/paths both still end up empty/None
        # either way in this skeleton — nothing is fetched yet, so
        # there's no data to place in the "right" field regardless of
        # layer kind. What is_multi_file actually decides, here and in
        # any future real fetch implementation, is which field is
        # ALLOWED to be populated for this layer_name — enforced by
        # AcquiredLayer's own validator, not by branching in this loop.
        is_multi_file = spec.layer_name in MULTI_FILE_LAYER_NAMES
        logger.debug(
            "%s: %s layer (uses `%s`)",
            spec.layer_name,
            "multi-file" if is_multi_file else "single-file",
            "paths" if is_multi_file else "path",
        )
        layers.append(
            AcquiredLayer(
                layer_name=spec.layer_name,
                provenance=spec.provenance,
                auth_required=spec.auth_required,
                source_name=spec.source_name,
                country_code=context.country_code if spec.country_specific else None,
                path=None,
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
