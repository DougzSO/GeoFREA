"""Pydantic schemas for the data_acquisition phase — STRUCTURE ONLY.

This module defines the acquisition contract; it contains no fetch/
download logic (see phase.py). Every AcquiredLayer produced by this
stage's run_acquisition_phase() has path=None — nothing is actually
resolved yet. See docs/DECISIONS.md 2026-08-24 (data_acquisition
skeleton) for the rationale and the open gaps flagged below.

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
    legacy never fetches or bundles slope, it derives it from the
    elevation raster (RasterProcessor.calculate_slope(), called in
    main.py after acquisition finishes) — it doesn't fit either
    provenance value ("fetched" implies an external source,
    "local_only" implies a pre-placed file). Where slope derivation
    belongs in GeoFREA's architecture is undecided; out of scope here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

# Single source of truth for which layers are genuinely multi-file (see
# AcquiredLayer's module/field docstrings, "wind vs. land_cover").
# Public so phase.py can consult it directly instead of carrying a
# redundant per-registry-entry flag (see DECISIONS.md 2026-08-24 -
# path/paths source-of-truth consolidation).
MULTI_FILE_LAYER_NAMES: frozenset[str] = frozenset({"land_cover"})


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
        auth_required: Whether the (future) fetch for this layer needs
            credentials. True only for land_cover (Terrascope) per the
            legacy audit — every other fetched source (GADM, Copernicus
            DEM S3, WorldPop, OSM Overpass) is public. Never holds the
            credential itself — this is a capability flag, not a secret.
        source_name: Human-readable source identifier (e.g. "GADM 4.1",
            "Terrascope ESA WorldCover"), or None if undetermined.
        country_code: ISO-3166-alpha-3 code this layer was/would be
            acquired for, or None for layers that are not country-
            specific (Solar/Lakes/Rivers/Seismic/Power Plants/Protected
            — see geoworld_framework's DataOrchestrator.global_layers.
            Protected/WDPA was corrected from country_specific=True to
            False 2026-08-24 — see phase.py's _LAYER_REGISTRY comment
            and DECISIONS.md same date, "vector layer audit depth").
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
