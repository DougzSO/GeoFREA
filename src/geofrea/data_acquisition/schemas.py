"""Pydantic schemas for the data_acquisition phase.

This module defines the acquisition contract; it contains no fetch/
download logic itself, and (as of 2026-09-08) no local-database
resolution logic either (see phase.py, fetchers/, and
local_layers.py). As of 2026-09-08 (2026-08-25 "real fetchers for
power_plants/wind/lakes/rivers" + 2026-08-26 "real fetcher for
borders/admin1" + 2026-09-08 "wire das 5 camadas restantes a partir do
banco local" (Fase 1 + Fase 2), all docs/DECISIONS.md), 11 of the 14
AcquiredLayer entries run_acquisition_phase() produces can have a real
`path`/`paths` — 6 via a real fetcher (power_plants, wind, lakes,
rivers, borders, admin1) and 5 via local-database resolution
(elevation, population, grid, roads, land_cover) — the other 3
(protected, solar, seismic) still always have path=None/paths=[] (see
phase.py's module docstring for exactly which and why). See
docs/DECISIONS.md 2026-08-24 (data_acquisition skeleton) for the
original rationale and the open gaps flagged below, most still
unresolved.

wind vs. land_cover (RESOLVED 2026-08-24, see DECISIONS.md same date):
both are multi-file in legacy's DataOrchestrator, but they are NOT
treated the same way here — this is a deliberate scope decision, not
an oversight:
  - wind stays on the single AcquiredLayer.path field. AuditInputs'
    own docstring (data_quality_audit/schemas.py) confirms only the
    first wind file is ever inspected ("only the first, if any, is
    inspected") — a list field would carry information nothing
    downstream reads, so there is no real gap to close for wind.
  - land_cover gets AcquiredLayer.paths: list[Path] (see below) — ESA
    WorldCover tiles are genuinely multi-file and ALL tiles are
    consumed (inspect_land_cover_tiles() iterates every tile), so a
    single path would be lossy, unlike wind.

path/paths source-of-truth consolidation (2026-08-24, see DECISIONS.md
same date): MULTI_FILE_LAYER_NAMES (this module) is now the ONLY place
that decides whether a layer_name uses `path` or `paths` —
AcquiredLayer's own validator enforces it. Previously phase.py's
`_LayerSpec` carried a redundant `multi_file: bool` flag per registry
entry, hand-set to match this module's land_cover special-case with
nothing enforcing the two stayed in sync. That flag is now removed;
phase.py reads MULTI_FILE_LAYER_NAMES directly.

Known gaps still open, flagged rather than silently patched (per this
stage's instructions — do not improvise past what was asked):
  - "slope" is deliberately NOT in the layer registry (see phase.py):
    it is neither fetched nor bundled. GeoFREA derives it inside
    grid_alignment (raster_alignment.derive_slope_from_dem(), 2026-09-11
    — see docs/DECISIONS.md), from the aligned-phase's elevation input,
    at the DEM's native resolution and then reprojected onto the grid.
    That is a change from where the legacy did it (its own main.py, glue
    code between acquisition and alignment); data_acquisition has no part
    in it either way.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, computed_field, model_validator

# Single source of truth for which layers are genuinely multi-file (see
# AcquiredLayer's module/field docstrings, "wind vs. land_cover").
# Public so phase.py can consult it directly instead of carrying a
# redundant per-registry-entry flag (see DECISIONS.md 2026-08-24 -
# path/paths source-of-truth consolidation).
MULTI_FILE_LAYER_NAMES: frozenset[str] = frozenset({"land_cover"})

# Single source of truth for AcquiredLayer.fetch_status (see that
# field's docstring). Canonically this is "which layer_names does
# phase.py's _FETCHED_LAYER_HANDLERS dispatch to a real fetcher" — but
# that dict lives in phase.py, which already imports this module, so
# mirroring it here (rather than importing phase.py from schemas.py)
# avoids a circular import. phase.py asserts at import time that
# set(_FETCHED_LAYER_HANDLERS) == IMPLEMENTED_FETCH_LAYER_NAMES, so the
# two cannot silently drift apart.
IMPLEMENTED_FETCH_LAYER_NAMES: frozenset[str] = frozenset(
    {"power_plants", "wind", "lakes", "rivers", "borders", "admin1"}
)

# protected (WDPA) has a complete, tested fetcher
# (fetchers/protected_planet.py) that is deliberately not wired into
# _FETCHED_LAYER_HANDLERS — gated behind a manual API token, not a
# missing implementation (see that module's docstring and
# docs/DECISIONS.md 2026-08-25). It is neither "implemented" (no
# handler dispatches to it) nor plain "not_implemented" (the fetcher
# exists and is tested) — hence the third fetch_status value.
IMPLEMENTED_NOT_ACTIVATED_LAYER_NAMES: frozenset[str] = frozenset({"protected"})


class CrsMetadata(BaseModel):
    """Reserved for future CRS/reprojection bookkeeping — not populated yet.

    Motivated by a legacy audit finding: GADM boundary acquisition sat
    entirely outside DataOrchestrator in geoworld_framework's main.py,
    with no structured place to record e.g. "this layer arrived in
    EPSG:4326 and needs reprojecting to X" before downstream phases
    consume it. This field exists so that information has somewhere to
    live once fetch logic is implemented, instead of being invented ad
    hoc in a later stage.

    Args:
        native_crs: CRS of the acquired file as delivered by its
            source, or None if not yet known/applicable.
        target_crs: CRS this layer should be reprojected to for
            GeoFREA's pipeline, or None if not yet decided.
        reprojected: Whether reprojection has already been applied to
            the stored file, or None if not yet determined.
    """

    model_config = ConfigDict(extra="forbid")

    native_crs: str | None = None
    target_crs: str | None = None
    reprojected: bool | None = None


class AcquiredLayer(BaseModel):
    """One raw data layer's acquisition record.

    Structural placeholder only in this stage — every instance produced
    by run_acquisition_phase() has path=None. Follows VerifiedValue's
    convention (core/schemas.py) of explicit, named optional fields
    rather than a loose dict.

    Args:
        layer_name: Canonical layer identifier (e.g. "elevation",
            "solar", "land_cover") — matches AuditInputs' field naming
            where a 1:1 mapping exists (see adapter.py).
        provenance: "fetched" if this layer comes (or would come) from
            a live external source (GADM, Copernicus, WorldPop, OSM,
            Terrascope). "local_only" if no fetch mechanism exists for
            it at all — geoworld_framework's DataFetcher has exactly 6
            download_* methods (gadm, land_cover, elevation, worldpop,
            osm_grid, osm_roads); solar/lakes/rivers/seismic/protected/
            power_plants have none and must be pre-placed on disk.
            Deliberately unchanged in meaning by fetch_status below —
            provenance is about intended/eventual source, not today's
            execution state (see fetch_status for that).
        auth_required: Whether the (future) fetch for this layer needs
            credentials. Always False today (2026-09-08): land_cover was
            the one case where this was True (Terrascope, per the
            legacy audit) until it reverted to local_only — it now
            resolves from pre-placed tiles needing no auth at all, same
            as every other fetched source (GADM, Copernicus DEM S3,
            WorldPop, OSM Overpass), all public (see DECISIONS.md
            2026-09-08, "wire das 5 camadas restantes a partir do banco
            local, Fase 1"). Never holds the credential itself — this is
            a capability flag, not a secret.
        source_name: Human-readable source identifier (e.g. "GADM 4.1",
            "Terrascope ESA WorldCover"), or None if undetermined.
        country_code: ISO-3166-alpha-3 code this layer was/would be
            acquired for, or None for layers that are not country-
            specific (Solar/Lakes/Rivers/Seismic/Power Plants/Protected
            — see geoworld_framework's DataOrchestrator.global_layers.
            Protected/WDPA was corrected from country_specific=True to
            False 2026-08-24 — see phase.py's _LAYER_REGISTRY comment
            and DECISIONS.md same date, "vector layer audit depth".
            Roads joined this set 2026-09-08 for the same reason: its
            source became a single GRIP4 regional file shared across
            many countries, clipped per-country downstream, not a
            per-country download — see DECISIONS.md same date).
        path: Resolved path once acquired, for single-file layers only
            (always None in this skeleton). Must be None when
            layer_name is in MULTI_FILE_LAYER_NAMES — enforced by this
            model's validator, not just a docstring convention.
        paths: Resolved paths for genuinely multi-file layers, reserved
            for land_cover only (ESA WorldCover tiles — every tile is
            consumed downstream, unlike wind, so a single `path` would
            be lossy). Must be empty when layer_name is NOT in
            MULTI_FILE_LAYER_NAMES — enforced by this model's
            validator. Always [] in this skeleton.
        crs_metadata: Reserved for future CRS/reprojection bookkeeping.
        fetch_status: Computed, not stored — "implemented" if
            layer_name has a real fetcher wired into phase.py's
            _FETCHED_LAYER_HANDLERS (power_plants/wind/lakes/rivers
            today); "implemented_not_activated" if a complete, tested
            fetcher exists but is deliberately not wired in (protected
            only, see IMPLEMENTED_NOT_ACTIVATED_LAYER_NAMES); otherwise
            "not_implemented". Orthogonal to provenance: provenance
            says where a layer would come from if fetched, fetch_status
            says whether that fetch actually happens today. A computed
            property rather than a constructor field so existing
            AcquiredLayer(...) call sites (tests, adapter.py) don't need
            to pass it — see docs/DECISIONS.md 2026-08-26 "fetch_status
            computed field".
    """

    model_config = ConfigDict(extra="forbid")

    layer_name: str
    provenance: Literal["fetched", "local_only"]
    auth_required: bool
    source_name: str | None = None
    country_code: str | None = None
    path: Path | None = None
    paths: list[Path] = []
    crs_metadata: CrsMetadata | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fetch_status(
        self,
    ) -> Literal["implemented", "implemented_not_activated", "not_implemented"]:
        """See the field docstring above — derived from layer_name alone."""
        if self.layer_name in IMPLEMENTED_FETCH_LAYER_NAMES:
            return "implemented"
        if self.layer_name in IMPLEMENTED_NOT_ACTIVATED_LAYER_NAMES:
            return "implemented_not_activated"
        return "not_implemented"

    @model_validator(mode="after")
    def _check_path_paths_match_layer_kind(self) -> AcquiredLayer:
        """Enforce a single source of truth for path vs. paths.

        MULTI_FILE_LAYER_NAMES (this module) decides which field a
        given layer_name is allowed to populate — not a per-caller
        convention. Added 2026-08-24 (see DECISIONS.md same date,
        "path/paths source-of-truth consolidation") to close a gap
        where phase.py's now-removed `multi_file` flag on `_LayerSpec`
        could in principle drift from this module's own
        MULTI_FILE_LAYER_NAMES set (they happened to agree, but nothing
        enforced it).
        """
        is_multi_file = self.layer_name in MULTI_FILE_LAYER_NAMES

        if is_multi_file and self.path is not None:
            raise ValueError(
                f"AcquiredLayer(layer_name={self.layer_name!r}): this is a "
                "multi-file layer (in MULTI_FILE_LAYER_NAMES) — `path` must "
                "be None, resolved files belong in `paths` instead."
            )

        if not is_multi_file and self.paths:
            raise ValueError(
                f"AcquiredLayer(layer_name={self.layer_name!r}): this is a "
                "single-file layer (not in MULTI_FILE_LAYER_NAMES) — "
                "`paths` must be empty, the resolved file belongs in "
                "`path` instead."
            )

        return self


class AcquisitionSummary(BaseModel):
    """Rollup counts across an AcquisitionResult's layers.

    Mirrors data_quality_audit's AuditSummary — a concise cross-section
    of the full result, not a substitute for reading `layers` directly.
    """

    model_config = ConfigDict(extra="forbid")

    layers_total: int
    layers_fetched_provenance: int
    layers_local_only_provenance: int
    layers_requiring_auth: int
    layers_resolved: int  # path is not None — always 0 in this skeleton


class AcquisitionResult(BaseModel):
    """Root output model for the data_acquisition phase.

    Structural skeleton only (see module docstring) — this phase does
    not fetch anything yet. Mirrors AuditResult's shape (country_code +
    timestamp + per-item detail + a summary rollup) so a future phase
    reading context.prior_results["data_acquisition"].output follows
    the same conventions as reading data_quality_audit's own output.

    Args:
        country_code: ISO-3166-alpha-3 code this acquisition run covers.
        timestamp: ISO-8601 UTC timestamp when acquisition started.
        layers: One AcquiredLayer per raw data source GeoFREA's
            pipeline needs (see _LAYER_REGISTRY in phase.py).
        summary: Rollup counts across `layers`.
    """

    model_config = ConfigDict(extra="forbid")

    country_code: str
    timestamp: str
    layers: list[AcquiredLayer]
    summary: AcquisitionSummary
