"""Orchestration for the grid_alignment phase.

Ported from geoworld_framework's src/processors/grid_aligner.py
(`GridAligner.__init__()`/`run()` L898-1145, `_save_grid_metadata()`
L1147-1172, `_verify_alignment()` L1174-1212) — see docs/DECISIONS.md
2026-09-08, grid_alignment Passo 3.

Per-layer clip source (see schemas.py's module docstring and Passo 1's
design correction, same DECISIONS.md date):
  - roads/lakes/rivers (global source files, AcquiredLayer.path is
    unclipped): this module calls core.geo_utils.read_clipped_to_country()
    itself, caching the result at the SAME on-disk path
    data_quality_audit's audit.py already uses
    (outputs_dir/country_code/processed/{layer}_clipped.gpkg) — reuse
    by disk-file convention, not a dependency on that phase's
    PhaseResult. `_read_clipped_with_cache()` below duplicates
    vector_inspection.py's private helper of the same shape rather
    than importing it — deliberately NOT sharing code across phase
    packages here (see this function's own docstring for why).
  - grid (already country-scoped at the acquisition source): a
    lightweight bbox-only load (vector_alignment.load_vector_bbox()),
    no exact clip, no cache — same distinction audit.py's
    `_VECTOR_SPECS` already draws for this same layer (clip=False).

`get_mainland_gdf()`/`detect_island_nation()` (core/geo_utils.py) are
NOT called from this module. In legacy, main.py computes
`mainland_gdf = get_mainland_gdf(border_gdf)` exactly ONCE and passes
that same object to both DataAuditor.run() and GridAligner.run() — the
mainland-filtering step never happened inside grid_aligner.py itself.
GridAlignmentInputs.country_gdf's docstring documents this same
already-mainland-filtered contract (matching AuditInputs.country_gdf),
so this phase reuses get_mainland_gdf() the same way legacy's
GridAligner did: by relying on its caller to have already run it, not
by calling it again here. detect_island_nation() is narrower still —
in legacy it is called ONLY from data_auditor.py (on the RAW,
pre-mainland-filter border_gdf, to check how much territory
mainland-filtering would discard); grid_aligner.py never called it.
Since GridAlignmentInputs only carries the already-mainland-filtered
country_gdf (not the raw multi-polygon borders), there is no
meaningful input here to run that check against — calling it on an
already-single-polygon GeoDataFrame would be vacuous. Not invoked here.

Resolution (# TODO: pending Passo 4 methodological review): legacy
reads `cfg.geospatial.resolutions.suitability` ("adaptive" or a fixed
degree value) plus an `adaptive` fallback dict
(target_pixels/min_deg/max_deg) from settings.yaml. GeoFREA's
config/settings.yaml has no `geospatial.resolutions` section yet
(confirmed absent during the audit preceding this port) — this module
hardcodes legacy's exact "adaptive" behavior and its exact fallback
constants (50000/0.001/0.05) rather than inventing a new config-wiring
path that was not authorized. Once Passo 4 settles this (and a
CountryParams/settings.yaml field exists — same precedent as
slope_threshold_deg, DECISIONS.md 2026-08-20), this hardcoding should
be replaced by reading that field, not by picking new numbers here.

NEW finding surfaced while porting, not present in the Passo 4 list
(informational only, not fixed): legacy's land_cover step has a
filename mismatch between GridAligner.run()'s own cache-check and the
path it actually writes to — `_execute_or_load("land_cover", ...)`
checks for `{code}_land_cover_aligned.tif` (derived from the `label`
argument, "land_cover"), but the lambda calls
`_mosaic_land_cover(..., _path("lc"), ...)`, which writes
`{code}_lc_aligned.tif` instead. The cache-check can therefore never
find a match, so land_cover is silently recomputed on every run
instead of being skipped when already aligned — performance-only (the
returned path is still correct), but real, and ported here AS-IS
(same mismatched filenames, same behavior) rather than silently fixed,
since correcting it was not authorized. See this module's
`_execute_or_load` calls for "land_cover" below, and report to Douglas
for an explicit decision.
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
from rasterio.enums import Resampling

from geofrea.core.geo_utils import read_clipped_to_country
from geofrea.core.orchestrator import PhaseContext
from geofrea.core.raster_io import gdal_quiet, safe_raster_open
from geofrea.grid_alignment.raster_alignment import (
    combine_wind_layers,
    mosaic_land_cover,
    reproject_to_grid,
)
from geofrea.grid_alignment.reference_grid import GridContext, build_reference_grid
from geofrea.grid_alignment.schemas import GridAlignmentInputs, GridAlignmentResult, GridMetadata
from geofrea.grid_alignment.vector_alignment import (
    align_lakes,
    align_plants,
    align_rivers,
    load_vector_bbox,
    rasterize_linear_distance,
)

logger = logging.getLogger(__name__)


@contextmanager
def timer(label: str, timings: dict[str, float]) -> Generator[None, None, None]:
    """Context manager that measures execution time and stores it in timings.

    Same shape as data_quality_audit's raster_inspection.py::timer() —
    not imported from there, kept local, same reasoning as
    `_read_clipped_with_cache()` below (see module docstring).
    """
    t0 = time.perf_counter()
    logger.info("  [%s] starting...", label)
    try:
        yield
    finally:
        elapsed = time.perf_counter() - t0
        timings[label] = round(elapsed, 2)
        logger.info("  [%s] completed in %.1fs", label, elapsed)


def _read_clipped_with_cache(
    path: Path, country_gdf: gpd.GeoDataFrame, cache_path: Path
) -> gpd.GeoDataFrame:
    """read_clipped_to_country(), backed by an on-disk cache keyed by cache_path.

    Duplicates vector_inspection.py's private `_read_clipped_with_cache()`
    (data_quality_audit) rather than importing it: that function is
    internal to a different phase package, and Passo 1's design
    correction (see module docstring) deliberately avoids grid_alignment
    depending on anything inside data_quality_audit — reuse here is by
    disk-file convention (the same cache_path both phases compute),
    not by sharing code across the phase boundary. This is a small,
    known duplication (~10 lines), flagged for the user rather than
    resolved unilaterally by promoting it to a shared module — that
    would touch data_quality_audit/vector_inspection.py, outside this
    stage's authorized scope.

    Args:
        path: Vector file to read (unclipped).
        country_gdf: Country polygon(s) to clip against.
        cache_path: Where to persist/read back the already-clipped result.

    Returns:
        The clipped GeoDataFrame, from cache if present, else freshly
        computed and cached for next time.
    """
    if cache_path.exists():
        return gpd.read_file(str(cache_path))

    clipped = read_clipped_to_country(path, country_gdf)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        clipped.to_file(cache_path, driver="GPKG")
    except Exception as exc:  # noqa: BLE001 — caching is optional, must not fail alignment
        logger.warning("Failed to write clip cache %s: %s", cache_path, exc)
    return clipped


def _verify_alignment(aligned: dict[str, Path | None], grid: GridContext) -> None:
    """Verify every produced raster matches the reference grid's dimensions.

    Args:
        aligned: Layer name -> produced raster path (or None).
        grid: Reference GridContext.

    Raises:
        RuntimeError: If any raster's dimensions don't match the grid.
            Deliberately NOT caught anywhere in this module — see
            docs/DECISIONS.md 2026-09-08, grid_alignment Passo 3: a
            topology mismatch must propagate to the orchestrator as
            PhaseExecutionError, the same as any other unhandled
            exception from a phase's run() (DECISIONS.md 2026-08-20 -
            orchestrator + data_quality_audit phase, "try/except único
            no orchestrator").
    """
    for name, path in aligned.items():
        if path and Path(path).exists():
            with safe_raster_open(path) as src:
                if (src.height, src.width) != (grid.height, grid.width):
                    raise RuntimeError(
                        f"Topology mismatch: '{name}' failed grid harmonization — "
                        f"expected ({grid.height}, {grid.width}), got ({src.height}, {src.width})."
                    )
    logger.info(
        "  All geometries mapped to congruent matrix shape=(%d, %d)", grid.height, grid.width
    )


def _save_grid_metadata(
    country_code: str, out_dir: Path, grid: GridContext, resolution_deg: float
) -> GridMetadata:
    """Build GridMetadata and persist it to `{code}_grid_metadata.json`, matching legacy.

    Args:
        country_code: ISO-3166-alpha-3 code.
        out_dir: This phase's per-country output directory.
        grid: Reference GridContext.
        resolution_deg: Effective resolution used to build the grid.

    Returns:
        The GridMetadata object (also written to disk as JSON, for the
        same standalone-reproducibility reason legacy did).
    """
    meta = GridMetadata(
        crs=grid.crs,
        resolution_deg=resolution_deg,
        width=grid.width,
        height=grid.height,
        transform=tuple(grid.transform)[:6],
        n_valid_pixels=int(grid.country_mask.sum()),
    )
    (out_dir / f"{country_code}_grid_metadata.json").write_text(
        json.dumps(meta.model_dump(), indent=2), encoding="utf-8"
    )
    return meta


def run_grid_alignment_phase(context: PhaseContext, inputs: GridAlignmentInputs) -> GridAlignmentResult:
    """Reproject every input layer onto one reference grid for `context.country_code`.

    Parameter order matches data_quality_audit's run_audit_phase(context,
    inputs) — see that module for the same (context, inputs) convention.

    Args:
        context: Shared phase context (country_code, outputs_dir, ...).
        inputs: Raw, already-resolved geodata (see GridAlignmentInputs).

    Returns:
        GridAlignmentResult with one Path per successfully aligned layer.

    Raises:
        RuntimeError: From _verify_alignment() if a produced raster's
            dimensions don't match the reference grid — propagates
            uncaught, see _verify_alignment()'s own docstring.
    """
    out_dir = context.outputs_dir / context.country_code / "grid_alignment"
    out_dir.mkdir(parents=True, exist_ok=True)
    processed_dir = context.outputs_dir / context.country_code / "processed"

    timestamp = datetime.now(UTC).isoformat()
    timings: dict[str, float] = {}

    def _path(suffix: str) -> Path:
        return out_dir / f"{context.country_code}_{suffix}_aligned.tif"

    def _exists(p: Path | None) -> bool:
        return bool(p and Path(p).exists())

    def _execute_or_load(label: str, fn, condition: bool = True):
        p = _path(label)
        if p.exists():
            with safe_raster_open(p) as src:
                if (src.height, src.width) == (grid.height, grid.width):
                    logger.info("    %s: cached.", label)
                    return p
            p.unlink()
        if condition:
            result = fn()
            if result is None:
                logger.info("    %s: no data generated.", label)
            return result
        return None

    def _clipped_gdf(source_path: Path | None, layer_name: str) -> gpd.GeoDataFrame | None:
        if not _exists(source_path):
            return None
        cache_path = processed_dir / f"{layer_name}_clipped.gpkg"
        return _read_clipped_with_cache(source_path, inputs.country_gdf, cache_path)

    # TODO: pending Passo 4 methodological review — see module docstring
    # ("Resolution"). Hardcoded "adaptive" behavior + legacy's exact
    # fallback constants, ported as-is.
    minx, miny, maxx, maxy = inputs.country_gdf.total_bounds
    lat_mid_rad = math.radians((miny + maxy) / 2.0)
    lat_km = (111132.92 - 559.82 * math.cos(2 * lat_mid_rad)) / 1000.0
    lon_km = (111412.84 * math.cos(lat_mid_rad) - 93.50 * math.cos(3 * lat_mid_rad)) / 1000.0
    area_km2 = (maxx - minx) * lon_km * (maxy - miny) * lat_km
    target_pixels = 50000  # TODO: pending Passo 4 methodological review
    min_deg, max_deg = 0.001, 0.05  # TODO: pending Passo 4 methodological review
    computed_res = math.sqrt(area_km2 / target_pixels) / math.sqrt(lat_km * lon_km)
    resolution_deg = float(np.clip(computed_res, min_deg, max_deg))

    grid = build_reference_grid(inputs.country_gdf, resolution_deg)
    aligned: dict[str, Path | None] = {}

    with timer("elevation", timings), gdal_quiet():
        aligned["elevation"] = _execute_or_load(
            "elevation",
            lambda: reproject_to_grid(inputs.elevation_path, _path("elevation"), grid),
            _exists(inputs.elevation_path),
        )

    with timer("slope", timings), gdal_quiet():
        aligned["slope"] = _execute_or_load(
            "slope",
            lambda: reproject_to_grid(inputs.slope_path, _path("slope"), grid),
            _exists(inputs.slope_path),
        )

    with timer("solar", timings), gdal_quiet():
        aligned["solar"] = _execute_or_load(
            "solar",
            lambda: reproject_to_grid(inputs.solar_path, _path("solar"), grid),
            _exists(inputs.solar_path),
        )

    with timer("wind", timings), gdal_quiet():
        aligned["wind"] = _execute_or_load(
            "wind",
            lambda: combine_wind_layers(inputs.wind_paths, _path("wind"), grid),
            bool(inputs.wind_paths),
        )

    with timer("land_cover", timings):
        # NEW finding (see module docstring) preserved AS-IS: this
        # cache-check looks for "{code}_land_cover_aligned.tif" but
        # the lambda below writes "{code}_lc_aligned.tif" — the two
        # never match, so land_cover is always recomputed. Not fixed
        # here, ported faithfully from legacy's own mismatch.
        aligned["land_cover"] = _execute_or_load(
            "land_cover",
            lambda: mosaic_land_cover(
                inputs.land_cover_tiles, _path("lc"), grid, inputs.country_gdf
            ),
            bool(inputs.land_cover_tiles),
        )

    with timer("population", timings), gdal_quiet():
        aligned["population"] = _execute_or_load(
            "population",
            lambda: reproject_to_grid(inputs.population_path, _path("population"), grid),
            _exists(inputs.population_path),
        )

    with timer("grid_distance", timings):
        aligned["grid"] = _execute_or_load(
            "grid",
            lambda: rasterize_linear_distance(
                load_vector_bbox(inputs.grid_source, inputs.country_gdf, "grid"),
                _path("grid"),
                inputs.country_gdf,
                grid,
                "grid",
                100.0,  # TODO: pending Passo 4 methodological review
            ),
            _exists(inputs.grid_source),
        )

    with timer("roads", timings):
        aligned["roads"] = _execute_or_load(
            "roads",
            lambda: rasterize_linear_distance(
                _clipped_gdf(inputs.roads_source, "roads"),
                _path("roads"),
                inputs.country_gdf,
                grid,
                "roads",
                100.0,  # TODO: pending Passo 4 methodological review
            ),
            _exists(inputs.roads_source),
        )

    with timer("lakes", timings):
        aligned["lakes"] = _execute_or_load(
            "lakes",
            lambda: align_lakes(_clipped_gdf(inputs.lakes_path, "lakes"), _path("lakes"), grid),
            _exists(inputs.lakes_path),
        )

    with timer("rivers", timings):
        aligned["rivers"] = _execute_or_load(
            "rivers",
            lambda: align_rivers(_clipped_gdf(inputs.rivers_path, "rivers"), _path("rivers"), grid),
            _exists(inputs.rivers_path),
        )

    with timer("seismic", timings), gdal_quiet():
        aligned["seismic"] = _execute_or_load(
            "seismic",
            lambda: reproject_to_grid(
                inputs.seismic_path, _path("seismic"), grid, resampling=Resampling.bilinear
            ),
            _exists(inputs.seismic_path),
        )

    with timer("plants", timings):
        aligned["plants"] = _execute_or_load(
            "plants",
            lambda: align_plants(inputs.plants_df, _path("plants"), inputs.country_gdf, grid),
            inputs.plants_df is not None,
        )

    grid_metadata = _save_grid_metadata(context.country_code, out_dir, grid, resolution_deg)

    # Deliberately NOT wrapped in try/except — see _verify_alignment()'s
    # own docstring and docs/DECISIONS.md 2026-09-08, grid_alignment
    # Passo 3, item 2. A RuntimeError here propagates uncaught out of
    # run_grid_alignment_phase(), to the orchestrator's single
    # try/except, becoming PhaseExecutionError.
    _verify_alignment(aligned, grid)

    return GridAlignmentResult(
        country_code=context.country_code,
        timestamp=timestamp,
        grid_metadata=grid_metadata,
        **aligned,
    )
