"""Pydantic schemas for the data_quality_audit phase.

Replaces geoworld_framework's DataAuditor.run(), which returned an ad
hoc dict (see docs/architecture/data_quality_audit.md sec a). AuditResult
is this phase's output_model, validated by the orchestrator like every
other phase — see DECISIONS.md 2026-08-20 - orchestrator + data_quality_audit
phase.

All models forbid extra fields, matching the convention already used in
core/schemas.py.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from pydantic import BaseModel, ConfigDict


class AuditInputs(BaseModel):
    """Raw, already-resolved geodata paths/objects the audit phase inspects.

    Mirrors DataAuditor.run()'s parameter list exactly (see
    docs/architecture/data_quality_audit.md sec a). GeoFREA has no data
    acquisition layer yet (legacy's DataFetcher/DataManager/DataOrchestrator
    are not ported — out of scope for this stage), so main.py currently
    has no way to populate these with real values; every field left at
    its default produces the same "file not found" reporting the legacy
    auditor already does for missing inputs. This is not fabricated
    behavior — it is the existing defensive path, just with nothing to
    find yet.

    Args:
        solar_path: PVOUT raster path.
        elevation_path: DEM raster path.
        slope_path: Slope raster path (derived from the DEM upstream).
        population_path: Population raster path.
        wind_paths: Wind speed/power-density raster paths (only the
            first, if any, is inspected — matches legacy's wind_files[0]).
        seismic_path: Seismic hazard raster path.
        land_cover_tiles: ESA WorldCover tile paths.
        lakes_path: HydroLAKES vector path (presence/size only, no
            per-feature inspection).
        rivers_path: HydroRIVERS vector path (presence/size only).
        plants_df: Existing power-plant records.
        country_gdf: Country polygon (mainland-filtered) used to mask
            every raster to the real country boundary, not a bounding box.
        skip_land_cover: If True, skip ESA tile analysis (the slowest step).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    solar_path: Path | None = None
    elevation_path: Path | None = None
    slope_path: Path | None = None
    population_path: Path | None = None
    wind_paths: list[Path] = []
    seismic_path: Path | None = None
    land_cover_tiles: list[Path] = []
    lakes_path: Path | None = None
    rivers_path: Path | None = None
    plants_df: pd.DataFrame | None = None
    country_gdf: gpd.GeoDataFrame | None = None
    skip_land_cover: bool = False


class RasterInspection(BaseModel):
    """Metadata and statistics for a single inspected raster layer.

    See docs/architecture/data_quality_audit.md sec b for the geodetic
    area formula and sec c for the PVOUT unit sanity-check bounds.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    size_mb: float | None = None
    crs: str | None = None
    resolution: float | None = None
    global_shape: tuple[int, int] | None = None
    analysis_shape: tuple[int, int] | None = None
    masked_by: str | None = None
    nodata: float | None = None
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    valid_pct: float | None = None
    area_km2: float | None = None
    error: str | None = None


class LandCoverClassStat(BaseModel):
    """Area/percentage for one ESA WorldCover class within the country."""

    model_config = ConfigDict(extra="forbid")

    name: str
    area_km2: float
    pct: float


class LandCoverInspection(BaseModel):
    """Aggregated ESA WorldCover statistics across all overlapping tiles."""

    model_config = ConfigDict(extra="forbid")

    skipped: bool = False
    error: str | None = None
    n_tiles: int = 0
    tiles_used: int = 0
    tiles_skipped: int = 0
    crs_set: list[str] = []
    res_set: list[float] = []
    class_stats: dict[int, LandCoverClassStat] = {}
    total_area_km2: float = 0.0
    errors: list[str] = []


class VectorLayerInspection(BaseModel):
    """Presence/size check for a global vector layer (lakes, rivers)."""

    model_config = ConfigDict(extra="forbid")

    found: bool
    name: str | None = None
    size_mb: float | None = None


class PowerPlantsInspection(BaseModel):
    """Aggregated statistics from existing power-generation plants."""

    model_config = ConfigDict(extra="forbid")

    total_plants: int = 0
    total_capacity_mw: float = 0.0
    by_fuel: dict[str, float] = {}
    error: str | None = None


class AuditSummary(BaseModel):
    """Concise cross-section of the full audit, used for the report footer."""

    model_config = ConfigDict(extra="forbid")

    layers_ok: list[str]
    layers_missing: list[str]
    n_wind_files: int
    lc_tiles_used: int
    lc_tiles_total: int
    lc_total_area_km2: float
    lc_classes: int
    solar_range: tuple[float, float] | None = None
    elev_range: tuple[float, float] | None = None
    slope_range: tuple[float, float] | None = None
    pop_range: tuple[float, float] | None = None
    seismic_range: tuple[float, float] | None = None
    total_plants: int
    total_cap_mw: float
    n_alerts: int


class SlopeThresholdCheck(BaseModel):
    """Slope-inactivity check result for one technology.

    Each technology now carries its own slope_threshold_deg
    (CountryParams.technologies.<tech>.slope_threshold_deg, see
    docs/DECISIONS.md 2026-08-20 - slope_threshold_deg moved to
    parameters.json) — there is no single per-country threshold
    anymore, so this check runs once per technology, not once per
    country.

    Args:
        threshold_deg: The technology's slope_threshold_deg.value used
            for this check.
        max_observed_deg: The max slope observed in the country's slope
            raster, or None if the slope raster was unavailable/errored.
        inactive: True if max_observed_deg is not None and below
            threshold_deg — the slope criterion would exclude no pixels
            for this technology.
    """

    model_config = ConfigDict(extra="forbid")

    threshold_deg: float
    max_observed_deg: float | None
    inactive: bool


class AuditResult(BaseModel):
    """Root output model for the data_quality_audit phase.

    Replaces the legacy `audit` dict (docs/architecture/data_quality_audit.md
    sec a). `land_cover` is always present as a structured
    LandCoverInspection (skipped=True when skip_land_cover was set),
    unlike legacy's dict which sometimes held just {"skipped": True}.

    Args:
        country_code: ISO-3166-alpha-3 code audited.
        timestamp: ISO-8601 UTC timestamp when the audit started.
        rasters: One RasterInspection per inspected raster layer
            (solar, elevation, slope, population, wind, seismic).
        land_cover: ESA WorldCover aggregate statistics.
        power_plants: Existing power-plant aggregate statistics.
        lakes: HydroLAKES presence/size check.
        rivers: HydroRIVERS presence/size check.
        alerts: Consistency/quality warnings raised during the audit
            (divergent CRS, unexpected resolution, PVOUT unit mismatch,
            inactive slope criterion per technology, island-nation
            detection).
        slope_threshold_check: One SlopeThresholdCheck per technology
            ("biomass", "solar", "wind") — see SlopeThresholdCheck.
        summary: Concise cross-section for the report footer.
        timings: Elapsed seconds per audit step.
        skipped: Step names that were explicitly skipped (e.g.
            "land_cover" when skip_land_cover=True).
        elapsed_total: Total audit wall-clock time, in seconds.
        report_path: Path to the saved human-readable .txt report, or
            None if it could not be written.
    """

    model_config = ConfigDict(extra="forbid")

    country_code: str
    timestamp: str
    rasters: dict[str, RasterInspection]
    land_cover: LandCoverInspection
    power_plants: PowerPlantsInspection
    lakes: VectorLayerInspection
    rivers: VectorLayerInspection
    alerts: list[str]
    slope_threshold_check: dict[str, SlopeThresholdCheck]
    summary: AuditSummary
    timings: dict[str, float]
    skipped: list[str]
    elapsed_total: float
    report_path: str | None = None
