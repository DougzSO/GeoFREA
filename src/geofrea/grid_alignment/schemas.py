"""Pydantic schemas for the grid_alignment phase.

Ported from geoworld_framework's src/processors/grid_aligner.py
(`GridAligner.run()`, 1213 lines — see docs/architecture/grid_alignment.md).
This phase reprojects every raw layer data_acquisition resolved onto a
single reference grid (same CRS/transform/dimensions), a prerequisite
for suitability_criteria (Fase 2b) — see module-mapping.md.

Design corrected from the legacy shape during the read-only audit that
preceded this schema (2026-09-08, see docs/DECISIONS.md same date —
grid_alignment contract, roads_source/grid_source vs. data_quality_audit's
cache_path): GridAlignmentInputs.roads_source/grid_source are always
the RAW, unclipped acquisition source — the same AcquiredLayer.path
data_acquisition resolved — never a data_quality_audit output.
run_grid_alignment_phase() (not implemented yet — schema only, this
stage) is expected to call core.geo_utils.read_clipped_to_country()
itself for `roads_source`, using the SAME on-disk cache_path
convention audit.py already uses
(outputs_dir/country_code/processed/roads_clipped.gpkg) — reuse by
disk-file convention, not a dependency on data_quality_audit's
PhaseResult. If that phase already ran for this country, the cache
file already exists and this phase gets a free hit; if not (or if
data_quality_audit is disabled in run.phases), it clips from scratch
and writes to the same path. This preserves PhaseContext.prior_results'
read-only contract (core/orchestrator.py) — no phase mutates or
implicitly depends on another phase's internal artifact.

Resolution and distance_cap_km: resolution_deg below is resolved from settings.yaml's
`geospatial.resolutions` section (ResolutionsConfig) by main.py and passed into GridAlignmentInputs by
adapter.py::acquisition_result_to_grid_alignment_inputs(), same precedent as slope_threshold_deg
(DECISIONS.md 2026-08-20): a settings.yaml field once a verdict was reached, not a silent Pydantic default.
distance_cap_km (`geospatial.distance_cap_km`) is the threshold of the `distance_capped` flag rasters
(M-F2a-03, OQ-040); it never truncates a stored distance.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from pydantic import BaseModel, ConfigDict


class GridAlignmentInputs(BaseModel):
    """Raw, already-resolved geodata this phase reprojects onto one reference grid.

    Field names mirror AuditInputs (data_quality_audit/schemas.py)
    exactly where the underlying layer is the same, so both phases
    read data_acquisition's AcquiredLayer entries identically. Two
    fields deliberately do NOT reuse that naming: `roads_source` and
    `grid_source`, not `roads_path`/`grid_path` — see module docstring.
    Making the rename visible at every call site is the point: these
    are always the raw acquisition source (roads: unclipped GRIP4
    regional shapefile; grid: per-country OSM geojson), never a
    clipped artifact from another phase.

    Args:
        elevation_path: DEM raster path.
        slope_path: OPTIONAL pre-computed slope raster override. Normally
            None: grid_alignment derives slope from `elevation_path` at
            the DEM's native resolution (raster_alignment.
            derive_slope_from_dem), then reprojects it onto the grid like
            elevation — see run_grid_alignment_phase(). Set this only to
            skip that derivation with a slope raster made elsewhere.
        solar_path: PVOUT raster path.
        wind_paths: Wind speed/power-density raster paths. Unlike
            AuditInputs (which only ever inspects wind_paths[0]),
            legacy's GridAligner combines up to 3 height variants by
            AHP weighting (_combine_wind_layers(), height parsed from
            each filename) — every path here is used, not just the
            first.
        population_path: Population raster path.
        land_cover_tiles: ESA WorldCover tile paths (mosaicked, not
            reprojected individually).
        roads_source: Raw GRIP4 regional shapefile path, unclipped —
            same underlying AcquiredLayer.path as AuditInputs.roads_path,
            deliberately renamed here, see module docstring.
        grid_source: Raw per-country OSM power-grid geojson path — same
            underlying AcquiredLayer.path as AuditInputs.grid_path,
            deliberately renamed here, see module docstring.
        lakes_path: HydroLAKES vector path (global — clipped internally
            by this phase, same approach data_quality_audit uses).
        rivers_path: HydroRIVERS vector path (global — clipped internally).
        country_gdf: Country polygon (mainland-filtered, from
            core.geo_utils.get_mainland_gdf()) — the geometry the
            output grid is built from (build_reference_grid() in
            legacy) and the clip mask applied to every output layer.
            Required, unlike AuditInputs.country_gdf (Optional there) —
            and this is a real behavioral divergence, not just a
            stricter convention. data_quality_audit still produces a
            meaningful result without one: it falls back to reporting
            presence/CRS/feature-count against the unclipped file
            (audit.py logs a warning, "areas will cover the entire
            file", and keeps going). grid_alignment has no equivalent
            degraded mode — build_reference_grid() IS country_gdf's
            bounds snapped to a resolution grid, and every raster/
            vector output is reprojected and masked against that same
            grid. Without country_gdf there is no reference grid to
            align anything to, so the field being required is not a
            style choice, it is the phase's one true precondition.
        resolution_deg: Fixed resolution in decimal degrees, from settings.yaml's
            `geospatial.resolutions.suitability` via main.py/adapter.py (no default here).
        distance_cap_km: Threshold (km) of the `distance_capped` flag rasters
            written beside the roads/grid/rivers distance rasters (M-F2a-03,
            OQ-040); it never truncates a stored distance. From settings.yaml's
            `geospatial.distance_cap_km`.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    elevation_path: Path | None = None
    slope_path: Path | None = None
    solar_path: Path | None = None
    wind_layers: dict[str, Path] = {}
    population_path: Path | None = None
    land_cover_tiles: list[Path] = []
    roads_source: Path | None = None
    grid_source: Path | None = None
    lakes_path: Path | None = None
    rivers_path: Path | None = None
    country_gdf: gpd.GeoDataFrame
    resolution_deg: float
    distance_cap_km: float


class GridMetadata(BaseModel):
    """Reference-grid parameters, ported from legacy's
    `{ISO3}_grid_metadata.json` (`GridAligner._save_grid_metadata()`).

    Args:
        crs: Always "EPSG:4326" (legacy hardcodes this in
            build_reference_grid(), not derived from any input layer).
        resolution_deg: Effective resolution used to build the grid —
            either the fixed configured value or the adaptive result.
            The adaptive knobs themselves are a pending methodological
            decision, not part of GridAlignmentInputs yet — see module
            docstring.
        width: Grid width, in pixels.
        height: Grid height, in pixels.
        transform: Affine transform coefficients (a, b, c, d, e, f) —
            same 6-tuple legacy's `list(grid.transform)[:6]` stores.
        n_valid_pixels: Count of True pixels in the country mask
            (`grid.country_mask.sum()` in legacy) — pixels actually
            inside the country polygon, not just inside its bbox.
    """

    model_config = ConfigDict(extra="forbid")

    crs: str
    resolution_deg: float
    width: int
    height: int
    transform: tuple[float, float, float, float, float, float]
    n_valid_pixels: int


class GridAlignmentResult(BaseModel):
    """Root output model for the grid_alignment phase.

    Mirrors legacy's AlignedLayers (geoworld_framework's
    src/core/schemas.py) field-for-field — 11 optional raster paths,
    all sharing the same CRS/transform/dimensions once produced. A
    missing input layer (e.g. no lakes_path resolved) simply leaves
    the corresponding field None; this phase does not fail for one
    missing layer (matches legacy's `_execute_or_load()` per-layer
    skip), only for structural failures (no country_gdf, or a produced
    raster failing the topology check). Legacy's `_verify_alignment()`
    raises RuntimeError rather than returning a flag, so this schema
    has no separate "verified" field — a topology mismatch is expected
    to surface as PhaseExecutionError from the orchestrator, not as
    data carried in this result.

    Args:
        country_code: ISO-3166-alpha-3 code this alignment run covers.
        timestamp: ISO-8601 UTC timestamp when alignment started.
        grid_metadata: Reference-grid parameters shared by every
            populated layer below.
        elevation: Bilinear-reprojected float32 DEM, or None if
            elevation_path was missing.
        slope: Bilinear-reprojected float32 slope raster, or None if
            slope_path was missing.
        solar: Bilinear-reprojected float32 PVOUT raster, or None if
            solar_path was missing.
        wind: AHP-combined (or uniform-weighted — see
            grid_alignment.md sec b item 2) wind raster, or None if no
            wind_paths were given.
        land_cover: Nearest-neighbour mosaicked ESA WorldCover raster
            (uint8), or None if no land_cover_tiles were given.
        population: Bilinear-reprojected float32 population raster, or
            None if population_path was missing.
        roads: Geodesic distance-to-road raster (km, float32,
            raw, never truncated; OQ-040), or None if roads_source was missing.
        grid: Geodesic distance-to-power-grid raster (km, float32,
            raw, never truncated; OQ-040), or None if grid_source was missing.
        lakes: Binary water-body mask (uint8), or None if no lakes
            were found within the country.
        rivers: Geodesic distance-to-river raster (km, float32,
            raw, never truncated; OQ-040), or None if no rivers were found within the country.
        roads_distance_capped/grid_distance_capped/rivers_distance_capped:
            uint8 flag rasters (1 = raw distance above `distance_cap_km`),
            written beside the distance rasters (M-F2a-03, OQ-040).
    """

    model_config = ConfigDict(extra="forbid")

    country_code: str
    timestamp: str
    grid_metadata: GridMetadata
    elevation: Path | None = None
    slope: Path | None = None
    solar: Path | None = None
    wind_layers: dict[str, Path] = {}
    land_cover: Path | None = None
    population: Path | None = None
    roads: Path | None = None
    grid: Path | None = None
    lakes: Path | None = None
    rivers: Path | None = None
    roads_distance_capped: Path | None = None
    grid_distance_capped: Path | None = None
    rivers_distance_capped: Path | None = None
