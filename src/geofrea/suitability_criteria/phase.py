"""Orchestration for the suitability_criteria phase (Fase 2b).

Ported from legacy geoworld_framework's src/processors/criteria_builder.py
(`CriteriaBuilder.run()` L825-1087) — see docs/architecture/
suitability_criteria_audit.md for the full read-only audit and the
approved schema contract (sec 8).

Built incrementally, one criterion package at a time. Packages landed:
  1. solar_resource, wind_resource, road_suitability, river_biomass
  2. terrain_score, slope_degrees (cartography-only raster),
     lc_biomass, biomass_resource
  3. grid_suitability, river_solar, river_wind, lakes_exclusion
  4. protected_areas, pop_suitability, seismic_suitability
     -> all 14 canonical criteria are now implemented.

  5. Cartography (one PNG per criterion + slope_degrees), isolated in
     this phase per audit sec 7 D7 — see cartography.py::plot_criterion_map,
     not routed through any shared/generic renderer.

Deferred to later packages, deliberately NOT stubbed here:
  - End-to-end wiring validation against a real 0.01deg GridAlignmentResult
    for BRA, with full progress/ETA logging for the slow country
    (audit sec 9 item 4 / DECISIONS.md 2026-09-10). The regression
    tests for this package call the compute functions directly on the
    frozen legacy aligned inputs (Bloqueio 3 decision (a)).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

from rasterio.transform import Affine

from geofrea.core.orchestrator import PhaseContext
from geofrea.core.schemas import GeometryRepairSummary
from geofrea.suitability_criteria.cartography import plot_criterion_map
from geofrea.suitability_criteria.criteria_functions import (
    ComputeResult,
    compute_biomass_resource,
    compute_grid_suitability,
    compute_lakes_exclusion,
    compute_lc_biomass,
    compute_population_suitability,
    compute_protected_areas,
    compute_river_suitability,
    compute_road_suitability,
    compute_seismic_suitability,
    compute_slope_degrees,
    compute_solar_resource,
    compute_terrain_score,
    compute_wind_resource,
)
from geofrea.suitability_criteria.raster_output import criterion_stats, save_criterion_raster
from geofrea.suitability_criteria.report import format_criteria_report, save_criteria_report
from geofrea.suitability_criteria.schemas import (
    CANONICAL_CRITERIA,
    REQUIRED_ALIGNED_LAYERS,
    CriterionLayer,
    SuitabilityCriteriaInputs,
    SuitabilityCriteriaResult,
    SuitabilityCriteriaSummary,
)

logger = logging.getLogger(__name__)

# criterion name -> (required aligned-layer field on the inputs, compute
# callable). A criterion runs only when its required layer is present;
# the callable takes the resolved SuitabilityCriteriaInputs and returns
# (score, transform, crs). Grows one package at a time.
_CRITERION_SPECS: dict[str, tuple[str, Callable[[SuitabilityCriteriaInputs], ComputeResult]]] = {
    "solar_resource": (
        "solar",
        lambda inp: compute_solar_resource(str(inp.solar), inp.criteria),
    ),
    "wind_resource": (
        "wind",
        lambda inp: compute_wind_resource(str(inp.wind), inp.criteria),
    ),
    "road_suitability": (
        "roads",
        lambda inp: compute_road_suitability(str(inp.roads), inp.criteria),
    ),
    "river_biomass": (
        "rivers",
        lambda inp: compute_river_suitability(str(inp.rivers), inp.criteria, "biomass"),
    ),
    "terrain_score": (
        "slope",
        lambda inp: compute_terrain_score(
            str(inp.slope),
            str(inp.elevation) if inp.elevation is not None else None,
            inp.criteria,
            inp.terrain_slope_threshold_deg,
        ),
    ),
    "lc_biomass": (
        "land_cover",
        lambda inp: compute_lc_biomass(str(inp.land_cover), inp.criteria.land_suitability.value),
    ),
    "biomass_resource": (
        "land_cover",
        lambda inp: compute_biomass_resource(
            str(inp.land_cover), inp.yield_by_land_cover, inp.criteria
        ),
    ),
    "grid_suitability": (
        "grid",
        lambda inp: compute_grid_suitability(str(inp.grid), inp.criteria),
    ),
    "river_solar": (
        "rivers",
        lambda inp: compute_river_suitability(str(inp.rivers), inp.criteria, "solar"),
    ),
    "river_wind": (
        "rivers",
        lambda inp: compute_river_suitability(str(inp.rivers), inp.criteria, "wind"),
    ),
    "lakes_exclusion": (
        "lakes",
        lambda inp: compute_lakes_exclusion(str(inp.lakes)),
    ),
    "pop_suitability": (
        "population",
        lambda inp: compute_population_suitability(str(inp.population), inp.criteria),
    ),
    "seismic_suitability": (
        "seismic",
        lambda inp: compute_seismic_suitability(str(inp.seismic), inp.criteria),
    ),
}

# Canonical criteria handled outside the uniform _CRITERION_SPECS loop
# because they do not take a single aligned raster path. protected_areas
# rasterizes the mainland boundary + WDPA vector against the reference
# grid directly (audit D9), and reports which branch it took.
_SPECIAL_CRITERIA: tuple[str, ...] = ("protected_areas",)


def _check_required_layers(inputs: SuitabilityCriteriaInputs) -> None:
    """Raise if any of elevation/slope/solar/land_cover is missing.

    Matches legacy's `required` pre-flight (criteria_builder.py L853-858)
    and grid_alignment's fail-loud philosophy — an unhandled exception
    from a phase's run() becomes PhaseExecutionError in the orchestrator.
    """
    missing = [layer for layer in REQUIRED_ALIGNED_LAYERS if getattr(inputs, layer) is None]
    if missing:
        raise RuntimeError(
            f"suitability_criteria requires aligned {REQUIRED_ALIGNED_LAYERS} — "
            f"missing: {missing}. grid_alignment did not produce them for this country."
        )


def run_suitability_criteria_phase(
    context: PhaseContext, inputs: SuitabilityCriteriaInputs
) -> SuitabilityCriteriaResult:
    """Build normalised suitability criteria for `context.country_code`.

    Parameter order matches run_audit_phase / run_grid_alignment_phase
    (context, inputs).

    Args:
        context: Shared phase context (country_code, outputs_dir, ...).
        inputs: Resolved aligned rasters + params + boundary
            (see SuitabilityCriteriaInputs).

    Returns:
        SuitabilityCriteriaResult — paths and per-criterion statistics
        only, never in-memory arrays (audit D6).

    Raises:
        RuntimeError: If a required aligned layer is missing, or a
            produced criterion's shape does not match grid_metadata
            (a topology mismatch — same as grid_alignment's
            _verify_alignment).
    """
    _check_required_layers(inputs)

    out_base = context.outputs_dir / context.country_code / "suitability_criteria"
    tif_dir = out_base / "tif"
    figure_dir = out_base / "figures"
    tif_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).isoformat()
    gm = inputs.grid_metadata
    canonical_transform = Affine(*gm.transform)
    expected_shape = (gm.height, gm.width)

    produced: dict[str, CriterionLayer] = {}
    timings: dict[str, float] = {}
    total = len(_CRITERION_SPECS)

    for i, (name, (required_layer, compute)) in enumerate(_CRITERION_SPECS.items(), start=1):
        if getattr(inputs, required_layer) is None:
            logger.info("  [%d/%d] %s: skipped (no aligned '%s')", i, total, name, required_layer)
            continue

        logger.info("  [%d/%d] %s: computing...", i, total, name)
        t0 = time.perf_counter()
        score, _transform, _crs = compute(inputs)

        if score.shape != expected_shape:
            raise RuntimeError(
                f"Topology mismatch: criterion '{name}' produced shape {score.shape}, "
                f"grid_metadata expects {expected_shape}."
            )

        tif_path = tif_dir / f"{name}.tif"
        save_criterion_raster(score, tif_path, canonical_transform, gm.crs)
        stats = criterion_stats(score)

        figure_path = figure_dir / f"{name}.png"
        plot_criterion_map(
            score, canonical_transform, gm.crs, name, context.country_code,
            inputs.mainland_gdf, figure_path, context_gdf=inputs.context_gdf,
        )

        elapsed = time.perf_counter() - t0
        timings[name] = round(elapsed, 2)

        produced[name] = CriterionLayer(name=name, tif_path=tif_path, figure_path=figure_path, **stats)
        logger.info(
            "  [%d/%d] %s: done in %.1fs (valid=%s, mean=%.3f)",
            i, total, name, elapsed, f"{stats['valid_pixels']:,}", stats["mean"],
        )

    # protected_areas: rasterized from the mainland boundary + optional
    # WDPA vector against the reference grid (audit D9), not from a single
    # aligned raster — handled outside the uniform loop above.
    logger.info("  protected_areas: computing...")
    t0 = time.perf_counter()
    prot_score, _pt, _pc, protected_source, wdpa_repair_report = compute_protected_areas(
        inputs.wdpa_path,
        inputs.mainland_gdf,
        canonical_transform,
        gm.width,
        gm.height,
        gm.crs,
        inputs.criteria.iucn_strict_categories.value,
    )
    if prot_score.shape != expected_shape:
        raise RuntimeError(
            f"Topology mismatch: criterion 'protected_areas' produced shape "
            f"{prot_score.shape}, grid_metadata expects {expected_shape}."
        )
    prot_tif = tif_dir / "protected_areas.tif"
    save_criterion_raster(prot_score, prot_tif, canonical_transform, gm.crs)
    prot_stats = criterion_stats(prot_score)

    prot_figure_path = figure_dir / "protected_areas.png"
    plot_criterion_map(
        prot_score, canonical_transform, gm.crs, "protected_areas", context.country_code,
        inputs.mainland_gdf, prot_figure_path, context_gdf=inputs.context_gdf,
    )

    timings["protected_areas"] = round(time.perf_counter() - t0, 2)
    produced["protected_areas"] = CriterionLayer(
        name="protected_areas", tif_path=prot_tif, figure_path=prot_figure_path, **prot_stats
    )
    logger.info(
        "  protected_areas: done (source=%s, valid=%s, wdpa_geoms_repaired=%d/%d)",
        protected_source, f"{prot_stats['valid_pixels']:,}",
        wdpa_repair_report.n_repaired, wdpa_repair_report.n_total,
    )

    # slope_degrees: cartography-only raster, NOT a canonical criterion —
    # written to disk and referenced by the result, but never counted in
    # n_criteria or fed to the MCDA (audit sec 2b).
    slope_degrees_tif = None
    slope_degrees_png = None
    if inputs.slope is not None:
        s_deg, _t, _c = compute_slope_degrees(str(inputs.slope))
        if s_deg.shape != expected_shape:
            raise RuntimeError(
                f"Topology mismatch: slope_degrees produced shape {s_deg.shape}, "
                f"grid_metadata expects {expected_shape}."
            )
        slope_degrees_tif = tif_dir / "slope_degrees.tif"
        save_criterion_raster(s_deg, slope_degrees_tif, canonical_transform, gm.crs)

        slope_degrees_png = figure_dir / "slope_degrees.png"
        plot_criterion_map(
            s_deg, canonical_transform, gm.crs, "slope_degrees", context.country_code,
            inputs.mainland_gdf, slope_degrees_png, context_gdf=inputs.context_gdf,
        )
        logger.info("  slope_degrees: written (cartography-only, not a criterion)")

    wired = set(_CRITERION_SPECS) | set(_SPECIAL_CRITERIA)
    not_implemented = [c for c in CANONICAL_CRITERIA if c not in wired]
    missing_expected = [c for c in CANONICAL_CRITERIA if c in wired and c not in produced]
    if not_implemented:
        logger.info("  Not yet implemented in this build: %s", ", ".join(not_implemented))
    if missing_expected:
        logger.info("  Wired but input absent this run: %s", ", ".join(missing_expected))

    report_text = format_criteria_report(
        country_code=context.country_code,
        timestamp=timestamp,
        criteria=produced,
        missing_expected=missing_expected,
        not_implemented=not_implemented,
        protected_source=protected_source,
        timings=timings,
    )
    report_path = save_criteria_report(report_text, context.country_code, context.outputs_dir)
    logger.info("Criteria summary saved: %s", report_path)

    return SuitabilityCriteriaResult(
        country_code=context.country_code,
        timestamp=timestamp,
        tif_dir=tif_dir,
        figure_dir=figure_dir,
        report_path=report_path,
        criteria=produced,
        slope_degrees_tif=slope_degrees_tif,
        slope_degrees_png=slope_degrees_png,
        summary=SuitabilityCriteriaSummary(
            n_criteria=len(produced),
            missing_expected=missing_expected,
            not_implemented=not_implemented,
            protected_source=protected_source,
            protected_wdpa_repair=GeometryRepairSummary(**wdpa_repair_report._asdict()),
            grid_metadata=gm,
        ),
    )
