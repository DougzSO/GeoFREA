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

Resolution (DECIDED 2026-09-09, see docs/DECISIONS.md same date,
grid_alignment Passo 4 item 3): `inputs.resolution_deg` (populated by
the adapter from settings.yaml's new `geospatial.resolutions.
suitability` — "adaptive" or a fixed degree value, config_loader.py/
schemas.py's ResolutionsConfig) drives this, not a hardcoded value.
Default is 0.01 fixed (~1km), matching legacy's own actual configured
value ("~1 km, consistent with global climate datasets") — the one
that generated the frozen PRT/BRA baseline
(docs/architecture/baseline-manifest.md). Legacy's "adaptive" code path
existed but was never the value legacy's real settings.yaml used;
GeoFREA had ported that unused code path as its only, hardcoded
behavior until this fix — measured divergence from the baseline before
this fix: BRA rendered at 785x781px (0.05deg, adaptive's pixel-ceiling
default) vs. the baseline's 3920x3902px (0.01deg fixed), ~25x fewer
pixels. "adaptive" is preserved as an explicit opt-in (its
target_pixels/min_deg/adaptive_pixel_ceiling_deg fallback constants
ported unchanged, see inputs.adaptive_target_pixels/adaptive_min_deg/
adaptive_pixel_ceiling_deg — this ceiling field's old name was renamed
2026-09-22 to avoid confusion with S-06's unrelated 0.05deg decision
cell), not the default.

land_cover cache filename mismatch (FIXED 2026-09-09, see
docs/DECISIONS.md same date — Passo 6 land_cover cache fix): legacy's
land_cover step had a filename mismatch between GridAligner.run()'s own
cache-check and the path it actually wrote to —
`_execute_or_load("land_cover", ...)` checks for
`{code}_land_cover_aligned.tif` (derived from the `label` argument,
"land_cover"), but the mosaic lambda used to call
`mosaic_land_cover(..., _path("lc"), ...)`, writing
`{code}_lc_aligned.tif` instead. The cache-check could therefore never
find a match, so land_cover was silently recomputed on every run
instead of being skipped when already aligned. Ported AS-IS (same
mismatched filenames) during the initial port per Passo 3, then
surfaced to Douglas as a real-execution finding during Passo 6's live
PRT+BRA validation (BRA cost: 529.7s recomputed every single
grid_alignment run, purely from this mismatch). Authorized and fixed
same day: the lambda now calls `_path("land_cover")`, matching the
cache-check — "land_cover" (not "lc") is the canonical name, same
convention every other layer in this module already follows (the
`_execute_or_load` label IS the on-disk suffix). Performance-only fix,
no change to the mosaic's output content, no METHODOLOGY_REVISION.
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
from geofrea.core.geodesy import wgs84_km_per_degree
from geofrea.core.orchestrator import PhaseContext
from geofrea.core.raster_io import gdal_quiet, safe_raster_open
from geofrea.grid_alignment.raster_alignment import (
    combine_wind_layers,
    derive_slope_from_dem,
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

    clipped, repair_report = read_clipped_to_country(path, country_gdf)
    if repair_report.n_invalid:
        # Not silent (METHODOLOGY A-02/A-09 spirit, see docs/phases/
        # core.md): repair_invalid_geometries() runs unconditionally
        # inside read_clipped_to_country() now, but grid_alignment's
        # own output schema has no slot for the report itself (unlike
        # data_quality_audit's VectorLayerInspection.geometry_repair) —
        # logged here so a repair on this phase's inputs is still
        # visible, not just on the audit/criteria side.
        logger.warning(
            "%s: %d/%d features were topologically invalid and repaired "
            "before clipping (reasons: %s).",
            path, repair_report.n_invalid, repair_report.n_total, repair_report.invalid_reasons,
        )
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

    # Resolution decided 2026-09-09 (see docs/DECISIONS.md same date,
    # grid_alignment Passo 4 item 3): inputs.resolution_deg comes from
    # settings.yaml's geospatial.resolutions.suitability, default 0.01
    # (fixed, matching the frozen PRT/BRA baseline) — "adaptive" is an
    # explicit opt-in, not the default, computed here exactly as legacy
    # did (same formula, now via core.geodesy.wgs84_km_per_degree() for
    # the WGS84 scale factors — see that module's docstring).
    if inputs.resolution_deg == "adaptive":
        minx, miny, maxx, maxy = inputs.country_gdf.total_bounds
        lat_mid = (miny + maxy) / 2.0
        lat_km, lon_km = wgs84_km_per_degree(lat_mid)
        area_km2 = (maxx - minx) * lon_km * (maxy - miny) * lat_km
        computed_res = math.sqrt(area_km2 / inputs.adaptive_target_pixels) / math.sqrt(lat_km * lon_km)
        resolution_deg = float(
            np.clip(computed_res, inputs.adaptive_min_deg, inputs.adaptive_pixel_ceiling_deg)
        )
    else:
        resolution_deg = float(inputs.resolution_deg)

    grid = build_reference_grid(inputs.country_gdf, resolution_deg)
    aligned: dict[str, Path | None] = {}

    with timer("elevation", timings), gdal_quiet():
        aligned["elevation"] = _execute_or_load(
            "elevation",
            lambda: reproject_to_grid(inputs.elevation_path, _path("elevation"), grid),
            _exists(inputs.elevation_path),
        )

    # slope is NOT an acquired layer — it is derived here from the DEM at
    # the DEM's native resolution (legacy main.py L598-609 / raster_
    # processor.calculate_slope), then reprojected onto the reference
    # grid like elevation. `inputs.slope_path`, when set, is an optional
    # pre-computed override; normally it is None and we derive.
    def _align_slope() -> Path | None:
        slope_src = inputs.slope_path
        if not _exists(slope_src):
            slope_src = processed_dir / f"{context.country_code}_slope_native.tif"
            processed_dir.mkdir(parents=True, exist_ok=True)
            if derive_slope_from_dem(inputs.elevation_path, slope_src) is None:
                return None
        return reproject_to_grid(slope_src, _path("slope"), grid)

    with timer("slope", timings), gdal_quiet():
        aligned["slope"] = _execute_or_load(
            "slope",
            _align_slope,
            _exists(inputs.slope_path) or _exists(inputs.elevation_path),
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
        # Cache filename mismatch fixed 2026-09-09 (see module
        # docstring) — writes to _path("land_cover") now, matching
        # _execute_or_load("land_cover", ...)'s own cache-check, so a
        # second run for the same country hits the cache instead of
        # always recomputing.
        aligned["land_cover"] = _execute_or_load(
            "land_cover",
            lambda: mosaic_land_cover(
                inputs.land_cover_tiles, _path("land_cover"), grid, inputs.country_gdf
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
                inputs.max_dist_km,
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
                inputs.max_dist_km,
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
            lambda: align_rivers(
                _clipped_gdf(inputs.rivers_path, "rivers"), _path("rivers"), grid, inputs.max_dist_km
            ),
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
