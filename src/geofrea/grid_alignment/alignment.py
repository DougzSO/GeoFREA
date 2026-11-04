"""Orchestration for the grid_alignment phase.

Ported from geoworld_framework's src/processors/grid_aligner.py
(`GridAligner.__init__()`/`run()` L898-1145, `_save_grid_metadata()`
L1147-1172, `_verify_alignment()` L1174-1212) — see docs/_archive/2026-09/DECISIONS.md
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

Resolution (DECIDED 2026-09-09, see docs/_archive/2026-09/DECISIONS.md same date,
grid_alignment Passo 4 item 3): `inputs.resolution_deg` (populated by
the adapter from settings.yaml's new `geospatial.resolutions.
suitability` — "adaptive" or a fixed degree value, config_loader.py/
schemas.py's ResolutionsConfig) drives this, not a hardcoded value.
Default is 0.01 fixed (~1km), matching legacy's own actual configured
value ("~1 km, consistent with global climate datasets") — the one
that generated the frozen PRT/BRA baseline
(docs/_archive/2026-09/architecture/baseline-manifest.md). Legacy's "adaptive" code path
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
docs/_archive/2026-09/DECISIONS.md same date — Passo 6 land_cover cache fix): legacy's
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

import hashlib
import json
import logging
import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from geofrea.core import memory_budget
from geofrea.core import paths as core_paths
from geofrea.core.cache_code import cache_code
from geofrea.core.cache_key import FileHashMemo, cache_is_current, cache_key, write_cache_key
from geofrea.core.constants import CELL_NESTING_PIXELS
from geofrea.core.layer_process import LayerFailedError, LayerRecord, append_ledger, run_layer
from geofrea.core.orchestrator import PhaseContext
from geofrea.core.raster_io import safe_raster_open
from geofrea.grid_alignment.layers import LayerContext
from geofrea.grid_alignment.layers import _read_clipped_with_cache as _read_clipped_with_cache  # noqa: PLC0414 — stays importable from here
from geofrea.grid_alignment.layers import gwa_crs_for as _gwa_crs_for  # noqa: F401
from geofrea.grid_alignment.poi import POI_ALGORITHM_VERSION
from geofrea.grid_alignment.reference_grid import GridContext, build_reference_grid
from geofrea.grid_alignment.schemas import GridAlignmentInputs, GridAlignmentResult, GridMetadata
from geofrea.grid_alignment.vector_alignment import distance_capped_path

logger = logging.getLogger(__name__)

_BUILDERS = "geofrea.grid_alignment.layers"

# Version of the alignment logic, part of every aligned layer's cache key (OQ-026). Bump it by hand when the logic of any aligner
# changes (resampling, masking, binning, distance rasterization), or the previous outputs would be reused.
ALIGNMENT_ALGORITHM_VERSION = (
    2  # 2: elevation and slope from the GLO-30 tiles (D-F2a-021, COMMAND 55)
)


class AlignmentLayersFailedError(RuntimeError):
    """One or more layers of F2a failed; every other layer was still built and is in place (the ledger `layers.json` says which and why)."""


def aligned_layer_key(kind: str, files, config: dict, hash_memo: FileHashMemo | None) -> str:
    """Key of an aligned layer: the algorithm version, the code of ITS builder (`cache_code`, COMMAND 88), the input files by content and the config.

    `kind` names the builder (`aligned_layer.<kind>` in `core.cache_code.CACHE_FUNCTION_ENTRIES`): only the functions it can reach enter the key,
    so an edit of one layer's code leaves the others current.
    """
    return cache_key(
        ALIGNMENT_ALGORITHM_VERSION, files, config, hash_memo, code=cache_code(f"aligned_layer.{kind}")
    )


@contextmanager
def timer(label: str, timings: dict[str, float]) -> Generator[None, None, None]:
    """Context manager that measures execution time and stores it in timings.

    Same shape as data_quality_audit's raster_inspection.py::timer() —
    not imported from there, kept local, same reasoning as
    `_read_clipped_with_cache()` (see module docstring).
    """
    t0 = time.perf_counter()
    logger.info("  [%s] starting...", label)
    try:
        yield
    finally:
        elapsed = time.perf_counter() - t0
        timings[label] = round(elapsed, 2)
        logger.info("  [%s] completed in %.1fs", label, elapsed)


def _verify_alignment(aligned: dict[str, Path | None], grid: GridContext) -> None:
    """Verify every produced raster matches the reference grid's dimensions.

    Args:
        aligned: Layer name -> produced raster path (or None).
        grid: Reference GridContext.

    Raises:
        RuntimeError: If any raster's dimensions don't match the grid.
            Deliberately NOT caught anywhere in this module — see
            docs/_archive/2026-09/DECISIONS.md 2026-09-08, grid_alignment Passo 3: a
            topology mismatch must propagate to the orchestrator as
            a failed phase, the same as any other unhandled
            exception from a phase's run() (DECISIONS.md 2026-08-20 -
            orchestrator + data_quality_audit phase, a single try/except
            in the orchestrator).
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


def run_grid_alignment_phase(
    context: PhaseContext, inputs: GridAlignmentInputs
) -> GridAlignmentResult:
    """Reproject every input layer onto one reference grid for `context.country_code`.

    Parameter order matches data_quality_audit's run_audit_phase(context,
    inputs) — see that module for the same (context, inputs) convention.

    The phase only coordinates (COMMAND 88): each layer is built by its function in `layers.py` in a child process, one at a time, after the memory
    guard has waited for the peak measured for that layer; a layer that fails does not remove the layers already written.

    Args:
        context: Shared phase context (country_code, outputs_dir, ...).
        inputs: Raw, already-resolved geodata (see GridAlignmentInputs).

    Returns:
        GridAlignmentResult with one Path per successfully aligned layer.

    Raises:
        RuntimeError: From _verify_alignment() if a produced raster's
            dimensions don't match the reference grid — propagates
            uncaught, see _verify_alignment()'s own docstring.
        AlignmentLayersFailedError: A layer's child process failed (after every other layer was built).
        MemoryWaitTimeout, CommitLimitExceeded: the machine could not give the memory (`core.memory_guard`); nothing already written is lost.
    """
    # METHODOLOGY A-08: phase outputs under outputs/<ISO3>/<phase>/<kind>/, intermediate caches under
    # interim/<ISO3>/<layer>/ (core.paths.interim(), from GEOFREA_DATA_DIR).
    out_dir = context.outputs_dir / context.country_code / "grid_alignment" / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    interim_dir = core_paths.interim(context.country_code, "grid_alignment")
    interim_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).isoformat()
    timings: dict[str, float] = {}
    ledger: list[LayerRecord] = []
    failures: list[str] = []

    def _path(suffix: str) -> Path:
        return out_dir / f"{context.country_code}_{suffix}_aligned.tif"

    def _exists(p: Path | None) -> bool:
        return bool(p and Path(p).exists())

    hash_memo = FileHashMemo(interim_dir / "input_sha256.json")
    polygon_sha256 = hashlib.sha256(
        b"".join(g.wkb for g in inputs.country_gdf.geometry)
    ).hexdigest()

    def _key(kind: str, files, **config) -> str:
        # Output-affecting config shared by every layer: the grid (resolution, nesting, country polygon).
        common = {
            "resolution_deg": float(inputs.resolution_deg),
            "cell_nesting_pixels": CELL_NESTING_PIXELS,
            "country_polygon_sha256": polygon_sha256,
        }
        return aligned_layer_key(kind, files, {**common, **config}, hash_memo)

    # Fixed resolution (M-F2a-01), from settings.yaml's geospatial.resolutions.suitability.
    resolution_deg = float(inputs.resolution_deg)

    grid = build_reference_grid(
        inputs.country_gdf, resolution_deg, nesting_pixels=CELL_NESTING_PIXELS
    )
    layer_context = LayerContext(
        inputs=inputs, grid=grid, out_dir=out_dir, interim_dir=interim_dir, country_code=context.country_code
    )

    def _build(label: str, kind: str, builder: str, **kwargs):
        """Run the builder `layers.<builder>` for `label` in a child process (`core.layer_process`); its row goes to the ledger at once."""
        try:
            value, record = run_layer(
                label,
                f"{_BUILDERS}:{builder}",
                {"ctx": layer_context, **kwargs},
                peak_mb=memory_budget.peak_mb(kind),
                work_dir=interim_dir,
            )
        except LayerFailedError as exc:
            ledger.append(LayerRecord(layer=label, status="failed", detail=str(exc)))
            append_ledger(interim_dir / "layers.json", ledger)
            logger.error("    %s: FAILED (%s); the other layers go on.", label, exc)
            failures.append(label)
            return None
        except BaseException:
            ledger.append(LayerRecord(layer=label, status="stopped", detail="the run was stopped before this layer finished"))
            append_ledger(interim_dir / "layers.json", ledger)
            raise
        ledger.append(record)
        append_ledger(interim_dir / "layers.json", ledger)
        logger.info("    %s: built in %.1fs (peak %.0f MB).", label, record.wall_s, record.peak_rss_mb)
        return value

    def _is_current(label: str, key: str | None) -> Path | None:
        """The raster of `label` when it exists with a current key and the grid's shape; a stale or misshapen one is removed."""
        p = _path(label)
        if not p.exists():
            return None
        if key is not None and cache_is_current(p, key):
            with safe_raster_open(p) as src:
                if (src.height, src.width) == (grid.height, grid.width):
                    logger.info("    %s: cached.", label)
                    ledger.append(LayerRecord(layer=label, status="cached"))
                    return p
        else:
            logger.info("    %s: cache key differs or is absent; recomputing.", label)
        p.unlink()
        return None

    def _execute_or_load(label: str, kind: str, builder: str, condition: bool = True, files=(), builder_kwargs=None, **config):
        key = _key(kind, files, **config) if condition else None
        current = _is_current(label, key)
        if current is not None:
            return current
        if not condition:
            return None
        result = _build(label, kind, builder, **(builder_kwargs or {}))
        if result is None:
            logger.info("    %s: no data generated.", label)
        elif Path(result) == _path(label):
            write_cache_key(Path(result), key)
        return result

    aligned: dict[str, Path | None] = {}

    # Elevation and slope come from the same source and the same pixel rule (D-F2a-021): the mean of the 30 m Copernicus GLO-30 samples
    # inside each pixel (METHODOLOGY 15.2.0, M-F2a-02). There is no other DEM input (the bundled `<ISO>_elevation.tif` is not read).
    dem_tiles = list(inputs.slope_dem_tiles)
    glo30: dict[str, Path | None] = {}

    def _glo30_layer(label: str) -> Path | None:
        """One pass over the GLO-30 tiles writes the elevation, the slope and the slope bins (COMMAND 75): the first of the three that is stale
        runs it and the other two find their raster current, with the key of the same source."""
        if not dem_tiles:
            return None
        key = _key("glo30", dem_tiles)
        current = _is_current(label, key)
        if current is not None:
            return current
        if not glo30:
            glo30.update(_build(label, "glo30", "build_glo30") or {})
            for raster in glo30.values():  # every raster comes from one pass over one source: each is as current as the others
                if raster is not None:
                    write_cache_key(raster, key)
        if glo30.get(label) is None:
            logger.info("    %s: no data generated.", label)
        return glo30.get(label)

    with timer("elevation", timings):
        aligned["elevation"] = _glo30_layer("elevation")

    with timer("slope", timings):
        aligned["slope"] = _glo30_layer("slope")

    with timer("solar", timings):
        aligned["solar"] = _execute_or_load(
            "solar", "solar", "build_solar", _exists(inputs.solar_path), files=[inputs.solar_path]
        )

    # M-F2a-04 (G-2): every GWA product at every height is aligned on its own; nothing is
    # combined across heights. Keys are "<product>_<height>m" (e.g. "weibull_a_150m").
    wind_layers: dict[str, Path] = {}
    for key, wind_src in inputs.wind_layers.items():
        with timer(f"wind_{key}", timings):
            out = _execute_or_load(
                f"wind_{key}",
                "wind",
                "build_wind",
                _exists(wind_src),
                # The CRS of a tile without one is taken from the wind-speed file of the same height.
                files=[wind_src, inputs.wind_layers.get(f"wind_speed_{key.rsplit('_', 1)[-1]}")],
                builder_kwargs={"key": key},
            )
        if out is not None:
            wind_layers[key] = out

    with timer("land_cover", timings):
        # Writes to _path("land_cover"), matching the cache-check of _execute_or_load (a filename mismatch made it recompute on every run until 2026-09-09).
        aligned["land_cover"] = _execute_or_load(
            "land_cover",
            "land_cover",
            "build_land_cover",
            bool(inputs.land_cover_tiles),
            files=inputs.land_cover_tiles,
        )
        aligned["land_cover_counts"] = _execute_or_load(
            "land_cover_counts",
            "land_cover_counts",
            "build_land_cover_counts",
            bool(inputs.land_cover_tiles),
            files=inputs.land_cover_count_tiles or inputs.land_cover_tiles,
        )

    with timer("slope_counts", timings):
        aligned["slope_counts"] = _glo30_layer("slope_counts")

    with timer("population", timings):
        aligned["population"] = _execute_or_load(
            "population", "population", "build_population", _exists(inputs.population_path), files=[inputs.population_path]
        )

    with timer("grid_distance", timings):
        aligned["grid"] = _execute_or_load(
            "grid",
            "grid",
            "build_grid_distance",
            _exists(inputs.grid_source),
            files=[inputs.grid_source],
            distance_cap_km=inputs.distance_cap_km,
        )

    poi_counts_path = out_dir / "poi_counts.json"
    with timer("poi_distance", timings):
        aligned["poi"] = _execute_or_load(
            "poi",
            "poi",
            "build_poi",
            _exists(inputs.grid_source) and inputs.poi_voltage_threshold_kv is not None,
            files=[inputs.grid_source]
            + ([] if inputs.poi_substation_source is None else [inputs.poi_substation_source]),
            builder_kwargs={"name": "poi", "threshold_kv": inputs.poi_voltage_threshold_kv, "counts_path": poi_counts_path},
            distance_cap_km=inputs.distance_cap_km,
            poi_voltage_threshold_kv=inputs.poi_voltage_threshold_kv,
            poi_line_tolerance_m=inputs.poi_line_tolerance_m,
            poi_algorithm=POI_ALGORITHM_VERSION,
        )

    # Sensitivity `poi_ind_132kv` (COMMAND 86): the same layer at another voltage threshold, computed in the same pass (IND: 132 kV)
    poi_sensitivity_counts_path = out_dir / "poi_sensitivity_counts.json"
    aligned["poi_sensitivity"] = None
    if inputs.poi_sensitivity_threshold_kv is not None:
        with timer("poi_sensitivity_distance", timings):
            aligned["poi_sensitivity"] = _execute_or_load(
                "poi_sensitivity",
                "poi",
                "build_poi",
                _exists(inputs.grid_source),
                files=[inputs.grid_source]
                + ([] if inputs.poi_substation_source is None else [inputs.poi_substation_source]),
                builder_kwargs={
                    "name": "poi_sensitivity",
                    "threshold_kv": inputs.poi_sensitivity_threshold_kv,
                    "counts_path": poi_sensitivity_counts_path,
                },
                distance_cap_km=inputs.distance_cap_km,
                poi_voltage_threshold_kv=inputs.poi_sensitivity_threshold_kv,
                poi_line_tolerance_m=inputs.poi_line_tolerance_m,
                poi_algorithm=POI_ALGORITHM_VERSION,
            )

    with timer("roads", timings):
        aligned["roads"] = _execute_or_load(
            "roads",
            "roads",
            "build_roads",
            _exists(inputs.roads_source),
            files=[inputs.roads_source],
            distance_cap_km=inputs.distance_cap_km,
            road_classes=None
            if inputs.road_classes is None
            else inputs.road_classes.model_dump(mode="json"),
        )

    with timer("lakes", timings):
        aligned["lakes"] = _execute_or_load(
            "lakes", "lakes", "build_lakes", _exists(inputs.lakes_path), files=[inputs.lakes_path]
        )

    with timer("rivers", timings):
        aligned["rivers"] = _execute_or_load(
            "rivers",
            "rivers",
            "build_rivers",
            _exists(inputs.rivers_path),
            files=[inputs.rivers_path],
            distance_cap_km=inputs.distance_cap_km,
        )

    append_ledger(interim_dir / "layers.json", ledger)
    if failures:
        raise AlignmentLayersFailedError(
            f"{context.country_code}: {len(failures)} layer(s) of F2a failed: {', '.join(failures)}. The other layers are built and kept "
            f"(see {interim_dir / 'layers.json'}); run the phase again once the cause is fixed."
        )

    for layer in ("roads", "grid", "rivers", "poi", "poi_sensitivity"):
        flag_path = distance_capped_path(aligned[layer]) if aligned.get(layer) else None
        aligned[f"{layer}_distance_capped"] = (
            flag_path if flag_path and flag_path.exists() else None
        )

    grid_metadata = _save_grid_metadata(context.country_code, out_dir, grid, resolution_deg)

    # Deliberately NOT wrapped in try/except — see _verify_alignment()'s
    # own docstring and docs/_archive/2026-09/DECISIONS.md 2026-09-08, grid_alignment
    # Passo 3, item 2. A RuntimeError here propagates uncaught out of
    # run_grid_alignment_phase(), to the orchestrator's single
    # try/except, becoming a failed phase.
    _verify_alignment({**aligned, **{f"wind_{k}": v for k, v in wind_layers.items()}}, grid)

    poi_counts = (
        json.loads(poi_counts_path.read_text(encoding="utf-8"))
        if aligned.get("poi") and poi_counts_path.exists()
        else None
    )
    return GridAlignmentResult(
        country_code=context.country_code,
        timestamp=timestamp,
        grid_metadata=grid_metadata,
        wind_layers=wind_layers,
        poi_counts=poi_counts,
        poi_sensitivity_counts=(
            json.loads(poi_sensitivity_counts_path.read_text(encoding="utf-8"))
            if aligned.get("poi_sensitivity") and poi_sensitivity_counts_path.exists()
            else None
        ),
        **aligned,
    )
