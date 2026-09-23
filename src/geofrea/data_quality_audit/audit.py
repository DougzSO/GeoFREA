"""data_quality_audit phase entry point.

Ports geoworld_framework's DataAuditor.run() (see
docs/architecture/data_quality_audit.md) into GeoFREA's orchestrator
contract: run_audit_phase(context, inputs, audit_config) -> AuditResult,
a validated Pydantic model, instead of legacy's ad hoc dict. See
DECISIONS.md 2026-08-20 - orchestrator + data_quality_audit phase.

Known simplifications vs. legacy (flagged here rather than silently
carried over or silently fixed):
  - No `country_name`: GeoFREA's parameters.json keys countries by ISO
    code only, with no name-lookup table (legacy accepted a name or code
    as CLI input and resolved it via ConfigLoader.get_country_by_name()).
    The audit report header uses country_code only.

Expected resolutions, sanity ranges and units (M-F1b-01) come from
config/audit.yaml (AuditConfig), not from module constants — see
docs/phases/F1b_data_quality_audit.md action F7-2. A layer whose
config entry has no source is null there and reported `not_audited`,
never defaulted.

slope_threshold_deg is technology-specific (CountryParams.technologies.
<tech>.slope_threshold_deg), not the legacy's single hardcoded 15.0°
per-country fallback — see docs/DECISIONS.md 2026-08-20 -
slope_threshold_deg moved to parameters.json. The slope-inactivity
check therefore runs once per technology (biomass/solar/wind), not
once per country.

config/audit.yaml has no `slope` entry (removed 2026-09-23, see
docs/phases/F1b_data_quality_audit.md D-F1b-003): slope does not exist
as a file at F1b time (it is derived from the DEM later, in
grid_alignment), so F1b never has a resolution to audit for it. The
raster_map entry below still reports it — always "File not found"
today — which is a distinct, honest status, not the same as
`not_audited` (a layer that DOES have an inspected file but no
configured expectation).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from geofrea.core.geo_utils import detect_island_nation
from geofrea.core.orchestrator import PhaseContext
from geofrea.data_quality_audit.raster_inspection import (
    diagnose_consistency,
    inspect_land_cover_tiles,
    inspect_power_plants,
    inspect_raster,
    timer,
)
from geofrea.data_quality_audit.schemas import (
    AuditConfig,
    AuditInputs,
    AuditLayerConfig,
    AuditResult,
    AuditSummary,
    LandCoverInspection,
    PowerPlantsInspection,
    RasterInspection,
    RasterLayerSummary,
    SlopeThresholdCheck,
    VectorLayerInspection,
    VectorLayerSummary,
)
from geofrea.data_quality_audit.vector_inspection import inspect_vector_layer

logger = logging.getLogger("geofrea.data_quality_audit.audit")

_TECHNOLOGIES = ("solar", "wind")  # Per METHODOLOGY S-02 scope

# Layers with no AuditInputs field / fetch path at all today — M-F1b-01
# requires the audit to cover every active layer, so these are reported
# `not_audited` unconditionally rather than omitted. Task IDs match
# docs/OPEN_QUESTIONS.md OQ-027 to OQ-029 and the acquisition tasks that
# will populate them.
_UNACQUIRED_GWA_PRODUCTS: tuple[str, ...] = (
    "combined-Weibull-A",
    "combined-Weibull-k",
    "air-density",
)
_UNACQUIRED_LAYERS: dict[str, str] = {
    "cmip6": "not yet acquired (task F-3)",
    "era5_gust": "not yet acquired (task F-4)",
    "gem_existing_plants": "not yet acquired (task F-5)",
}


def run_audit_phase(
    context: PhaseContext, inputs: AuditInputs, audit_config: AuditConfig
) -> AuditResult:
    """Audit raw country data before any processing.

    Args:
        context: Shared phase context (country_code, outputs_dir, ...).
        inputs: Already-resolved raster/vector/tabular inputs to inspect.
        audit_config: config/audit.yaml, validated (M-F1b-01 expected
            resolutions, sanity ranges and units).

    Returns:
        A validated AuditResult.
    """
    if inputs.country_gdf is None:
        logger.warning(
            "country_gdf not provided for %s — areas will cover the entire file.",
            context.country_code,
        )

    logger.info("Audit: %s", context.country_code)
    timings: dict[str, float] = {}
    started_at = datetime.now(UTC)

    alerts: list[str] = []
    skipped: list[str] = []

    if inputs.country_gdf is not None and detect_island_nation(inputs.country_gdf):
        msg = (
            "ISLAND NATION DETECTED: largest polygon represents < 40% of total "
            "territory. Verify mainland-only filtering is appropriate for this country."
        )
        logger.warning("  %s", msg)
        alerts.append(msg)

    # ── Rasters ──────────────────────────────────────────────────────
    raster_map: dict[str, Path | None] = {
        "solar": inputs.solar_path,
        "elevation": inputs.elevation_path,
        "population": inputs.population_path,
        "slope": inputs.slope_path,
        "wind": inputs.wind_paths[0] if inputs.wind_paths else None,
    }

    solar_cfg = audit_config.layers.get("solar")

    rasters: dict[str, dict] = {}
    for layer, path in raster_map.items():
        if path and Path(path).exists():
            with timer(layer, timings):
                meta = inspect_raster(Path(path), country_gdf=inputs.country_gdf)
                rasters[layer] = meta

                if layer == "solar" and isinstance(solar_cfg, AuditLayerConfig):
                    solar_mean = meta.get("mean")
                    if solar_mean is not None and solar_cfg.sanity_range is not None:
                        lo, hi = solar_cfg.sanity_range
                        if not (lo < solar_mean < hi):
                            unit = solar_cfg.unit or "unit not configured"
                            msg = (
                                f"PVOUT appears to be in incorrect units (mean "
                                f"{solar_mean:.1f}). Expected: {unit} (~{lo} to {hi})."
                            )
                            logger.error("  %s", msg)
                            alerts.append(msg)
        else:
            rasters[layer] = {"error": "File not found"}
            timings[layer] = 0.0

    # ── Vector layers ───────────────────────────────────────────────
    # clip=True: single global/regional file spanning many countries
    # (protected, lakes, rivers, and — since 2026-09-08, see
    # DECISIONS.md same date, "wire das 5 camadas restantes a partir do
    # banco local, Fase 2 - roads" — roads, now a GRIP4 regional
    # shapefile instead of a per-country OSM download). clip=False:
    # still scoped to one country at the acquisition source (borders,
    # admin1, grid). See vector_inspection.py's module docstring and
    # DECISIONS.md 2026-08-24 - vector layer audit depth.
    _VECTOR_SPECS: tuple[tuple[str, Path | None, bool, bool], ...] = (
        ("borders", inputs.borders_path, False, False),
        ("admin1", inputs.admin1_path, False, False),
        ("grid", inputs.grid_path, False, False),
        ("roads", inputs.roads_path, True, False),
        ("protected", inputs.protected_path, True, True),
        ("lakes", inputs.lakes_path, True, False),
        ("rivers", inputs.rivers_path, True, False),
    )

    vectors: dict[str, dict] = {}
    for vname, vpath, clip, iucn_breakdown in _VECTOR_SPECS:
        # Clip-result cache (2026-08-25, see DECISIONS.md same date -
        # data_acquisition activation): only meaningful for clip=True
        # layers (protected/lakes/rivers) — see vector_inspection.py's
        # module docstring, "cache_path". clip=False layers pass
        # cache_path=None, which inspect_vector_layer() simply ignores.
        cache_path = (
            context.outputs_dir / context.country_code / "processed" / f"{vname}_clipped.gpkg"
            if clip
            else None
        )
        with timer(vname, timings):
            vectors[vname] = inspect_vector_layer(
                vpath,
                country_gdf=inputs.country_gdf,
                clip=clip,
                iucn_breakdown=iucn_breakdown,
                cache_path=cache_path,
            )

    # ── Land cover ──────────────────────────────────────────────────
    if inputs.skip_land_cover:
        land_cover: dict = {"skipped": True}
        skipped.append("land_cover")
        timings["land_cover"] = 0.0
        logger.info("  [land_cover] SKIP enabled.")
    elif inputs.land_cover_tiles:
        land_cover_cache_dir = (
            context.outputs_dir / context.country_code / "data_quality_audit"
            / "land_cover_tile_cache"
        )
        with timer("land_cover", timings):
            land_cover = inspect_land_cover_tiles(
                inputs.land_cover_tiles,
                country_gdf=inputs.country_gdf,
                cache_dir=land_cover_cache_dir,
            )
    else:
        land_cover = {"error": "Tiles not found"}
        timings["land_cover"] = 0.0

    # ── Power plants ────────────────────────────────────────────────
    if inputs.plants_df is not None:
        with timer("power_plants", timings):
            power_plants = inspect_power_plants(inputs.plants_df)
    else:
        power_plants = {"error": "Data not available", "total_plants": 0}
        timings["power_plants"] = 0.0

    # ── Consistency diagnostics ─────────────────────────────────────
    wind_cfg = audit_config.layers.get("wind", {})
    wind_speed_cfg = wind_cfg.get("wind-speed") if isinstance(wind_cfg, dict) else None
    expected_resolutions: dict[str, float | None] = {
        layer: (cfg.expected_resolution_deg if isinstance(cfg, AuditLayerConfig) else None)
        for layer, cfg in audit_config.layers.items()
        if isinstance(cfg, AuditLayerConfig)
    }
    expected_resolutions["wind"] = (
        wind_speed_cfg.expected_resolution_deg if wind_speed_cfg is not None else None
    )

    res_alerts, not_audited = diagnose_consistency(
        rasters, expected_resolutions, audit_config.resolution_tolerance
    )
    alerts.extend(res_alerts)

    # Layers with no fetch path at all today (M-F1b-01: audit covers
    # every active layer, not just the ones already wired into
    # AuditInputs) — reported unconditionally, never silently omitted.
    for product in _UNACQUIRED_GWA_PRODUCTS:
        product_cfg = wind_cfg.get(product) if isinstance(wind_cfg, dict) else None
        reason = "not yet fetched (task F-1)"
        if isinstance(product_cfg, AuditLayerConfig) and product_cfg.source:
            reason = f"configured, but not yet fetched (task F-1): {product_cfg.source}"
        not_audited[f"wind/{product}"] = reason
    not_audited.update(_UNACQUIRED_LAYERS)

    # ── Slope threshold inactivity check — once per technology ────────
    # Each technology carries its own slope_threshold_deg (see module
    # docstring); there is no single per-country value anymore.
    slope_meta = rasters.get("slope", {})
    slope_max_obs = (
        float(slope_meta["max"])
        if not slope_meta.get("error") and slope_meta.get("max") is not None
        else None
    )

    slope_threshold_check: dict[str, SlopeThresholdCheck] = {}
    for tech_name in _TECHNOLOGIES:
        tech_params = getattr(context.country_params.technologies, tech_name)
        threshold = tech_params.slope_threshold_deg.value
        inactive = slope_max_obs is not None and slope_max_obs < threshold
        slope_threshold_check[tech_name] = SlopeThresholdCheck(
            threshold_deg=threshold, max_observed_deg=slope_max_obs, inactive=inactive
        )
        if inactive:
            msg = (
                f"INACTIVE CRITERION [slope/{tech_name}]: threshold={threshold:.1f}° > "
                f"max observed slope={slope_max_obs:.2f}°. The slope criterion excludes "
                f"NO pixels for {context.country_code} ({tech_name})."
            )
            alerts.append(msg)
            logger.warning("  SLOPE THRESHOLD INACTIVE [%s]: %s", tech_name, msg)

    # ── Assemble + validate ─────────────────────────────────────────
    n_wind = len(inputs.wind_paths)
    summary = _build_summary(
        rasters, vectors, land_cover, power_plants, alerts, n_wind, not_audited
    )
    elapsed_total = round((datetime.now(UTC) - started_at).total_seconds(), 1)

    result = AuditResult(
        country_code=context.country_code,
        timestamp=started_at.isoformat(),
        rasters={k: RasterInspection.model_validate(v) for k, v in rasters.items()},
        land_cover=LandCoverInspection.model_validate(land_cover),
        power_plants=PowerPlantsInspection.model_validate(power_plants),
        vectors={k: VectorLayerInspection.model_validate(v) for k, v in vectors.items()},
        alerts=alerts,
        slope_threshold_check=slope_threshold_check,
        summary=summary,
        timings=timings,
        skipped=skipped,
        not_audited=not_audited,
        elapsed_total=elapsed_total,
        report_path=None,
    )

    report_text = _format_report(result, audit_config)
    print(report_text)
    report_path = _save_report(report_text, context.country_code, started_at, context.outputs_dir)
    logger.info("Report saved: %s", report_path)

    return result.model_copy(update={"report_path": str(report_path)})


# Layers that report a value_range in AuditSummary.layers — same set
# the old flat schema's range_map covered. "wind" is deliberately
# excluded (it never had a *_range field in the flat schema either,
# despite going through the same inspect_raster() pipeline as these
# four) — preserved as-is, not fixed, out of scope for this refactor.
_RASTER_LAYERS_WITH_RANGE = frozenset({"solar", "elevation", "slope", "population"})


def _build_summary(
    rasters: dict[str, dict],
    vectors: dict[str, dict],
    land_cover: dict,
    power_plants: dict,
    alerts: list[str],
    n_wind: int,
    not_audited: dict[str, str],
) -> AuditSummary:
    """Build a concise summary from the raw audit dicts.

    `layers` covers AuditResult.rasters + AuditResult.vectors' combined
    13 names (see AuditSummary.layers' docstring for why land_cover/
    power_plants stay separate) — added 2026-08-24 (see DECISIONS.md
    same date, "AuditSummary refactor to layer-keyed dict"), replacing
    the flat layers_ok/layers_missing/n_wind_files/*_range fields.
    """
    lc = land_cover or {}
    pp = power_plants or {}

    layers: dict[str, RasterLayerSummary | VectorLayerSummary] = {}

    for layer, meta in rasters.items():
        error = meta.get("error")
        value_range = None
        if not error and layer in _RASTER_LAYERS_WITH_RANGE and meta.get("min") is not None:
            value_range = (meta["min"], meta["max"])
        layers[layer] = RasterLayerSummary(
            status="missing" if error else "ok",
            error=error,
            value_range=value_range,
            file_count=n_wind if layer == "wind" else None,
        )

    for layer, meta in vectors.items():
        found = meta.get("found", False)
        error = meta.get("error")
        error_type = meta.get("error_type")
        if not found:
            status = "missing"
        elif error_type in ("read_error", "processing_error"):
            status = error_type
        elif error:
            # Defensive fallback: an error with no error_type shouldn't
            # happen from inspect_vector_layer() itself (both its
            # except blocks always set one), but a caller building this
            # dict by hand (tests, future callers) might not.
            status = "processing_error"
        else:
            status = "ok"
        layers[layer] = VectorLayerSummary(
            status=status,
            error=error,
            n_features=meta.get("n_features"),
        )

    return AuditSummary(
        layers=layers,
        lc_tiles_used=lc.get("tiles_used", 0),
        lc_tiles_total=lc.get("n_tiles", 0),
        lc_total_area_km2=lc.get("total_area_km2", 0),
        lc_classes=len(lc.get("class_stats", {})),
        total_plants=pp.get("total_plants", 0),
        total_cap_mw=pp.get("total_capacity_mw", 0),
        n_alerts=len(alerts),
        n_not_audited=len(not_audited),
    )


def _format_report(result: AuditResult, audit_config: AuditConfig) -> str:
    """Format the full audit report as a human-readable text string."""
    lines: list[str] = []
    W = 64

    def sep(c: str = "=") -> None:
        lines.append(c * W)

    def blank() -> None:
        lines.append("")

    def row(lbl: str, val, ind: int = 4) -> None:
        lines.append(f"{' ' * ind}{lbl:<33}: {val}")

    sep()
    lines.append("  DATA AUDIT REPORT")
    lines.append(f"  {result.country_code}")
    lines.append(f"  {result.timestamp[:19].replace('T', ' ')}")
    if result.skipped:
        lines.append(f"  Skipped steps: {result.skipped}")
    sep()

    blank()
    lines.append("  RASTERS")
    sep("-")
    for layer, meta in result.rasters.items():
        t = result.timings.get(layer, 0)
        if meta.error:
            lines.append(f"  [MISSING] {layer.upper():<12}: {meta.error}")
            continue

        lines.append(f"  [OK] {layer.upper()}  [{t:.1f}s]")
        row("File", meta.name or "—")
        row("Size", f"{meta.size_mb} MB" if meta.size_mb is not None else "—")
        row("CRS", meta.crs or "—")
        row("Resolution", f"{meta.resolution}°" if meta.resolution is not None else "—")
        row("Mask used", meta.masked_by or "—")

        if meta.global_shape != meta.analysis_shape:
            row("Global shape", str(meta.global_shape))
            row("Shape in country", str(meta.analysis_shape))
        else:
            row("Shape", str(meta.analysis_shape))

        if meta.area_km2 is not None:
            row("Valid area", f"{meta.area_km2:>10,.0f} km²")
        if meta.min is not None:
            row("Min / Max", f"{meta.min} / {meta.max}")
            row("Mean", f"{meta.mean}")
            row("Valid pixels", f"{meta.valid_pct}%")
        blank()

    sep("-")
    lines.append("  VECTOR LAYERS")
    sep("-")
    _VECTOR_LABELS = {
        "borders": "Borders (GADM)",
        "admin1": "Admin-1 (GADM)",
        "grid": "Power grid (OSM)",
        "roads": "Roads (GRIP4)",
        "protected": "Protected areas (WDPA)",
        "lakes": "HydroLAKES",
        "rivers": "HydroRIVERS",
    }
    for vname, label in _VECTOR_LABELS.items():
        layer = result.vectors.get(vname)
        if layer is None or not layer.found:
            lines.append(f"  [MISSING] {label:<24}: not found")
            continue
        if layer.error:
            lines.append(f"  [ERROR] {label:<24}: {layer.error}")
            continue

        t = result.timings.get(vname, 0)
        lines.append(f"  [OK] {label}  [{t:.1f}s]")
        row("File", layer.name or "—")
        row("Size", f"{layer.size_mb} MB")
        row("CRS", layer.crs or "—")
        row("Features", layer.n_features if layer.n_features is not None else "—")
        row("Geometry types", ", ".join(layer.geometry_types) or "—")
        row("Clipped to country", layer.clipped_to_country)
        if layer.total_area_km2 is not None:
            row("Total area", f"{layer.total_area_km2:>10,.1f} km²")
        if layer.total_length_km is not None:
            row("Total length", f"{layer.total_length_km:>10,.1f} km")
        if layer.attribute_breakdown:
            blank()
            lines.append("    Category                        |  Count  |    km²     |    %")
            lines.append("    " + "-" * 66)
            for cat, stat in sorted(layer.attribute_breakdown.items()):
                area = f"{stat.area_km2:>10,.1f}" if stat.area_km2 is not None else f"{'—':>10}"
                lines.append(f"    {cat:<32}| {stat.count:>7} | {area} | {stat.pct:>5.1f}%")
        blank()

    sep("-")
    lc = result.land_cover
    t_lc = result.timings.get("land_cover", 0)

    if lc.skipped:
        lines.append("  [SKIP] LAND COVER: skipped (skip_land_cover=True)")
    elif lc.error:
        lines.append(f"  [MISSING] LAND COVER: {lc.error}")
    else:
        lines.append(f"  [OK] LAND COVER (ESA WorldCover)  [{t_lc:.1f}s]")
        row("Total tiles", lc.n_tiles)
        row("Tiles used", f"{lc.tiles_used}  ({lc.tiles_skipped} without overlap)")
        row("CRS", ", ".join(lc.crs_set))
        row("Resolution(s)", ", ".join(str(r) for r in lc.res_set))
        row("Total area", f"{lc.total_area_km2:>10,.0f} km²")
        blank()
        lines.append("    Code | Class                         |    km²     |    %")
        lines.append("    " + "-" * 58)
        for cls, info in sorted(lc.class_stats.items()):
            lines.append(
                f"    {cls:>6} | {info.name:<31}| {info.area_km2:>10,.1f} | {info.pct:>5.1f}%"
            )
        for err in lc.errors:
            lines.append(f"  [WARNING]  {err}")

    blank()
    sep("-")
    pp = result.power_plants
    t_pp = result.timings.get("power_plants", 0)
    lines.append(f"  EXISTING POWER PLANTS  [{t_pp:.1f}s]")
    sep("-")
    if pp.error and not pp.total_plants:
        lines.append(f"  [MISSING] {pp.error}")
    else:
        row("Total plants", pp.total_plants)
        row("Total capacity", f"{pp.total_capacity_mw:,.0f} MW")
        if pp.by_fuel:
            blank()
            lines.append("    Fuel                           |    MW")
            lines.append("    " + "-" * 38)
            for fuel, cap in list(pp.by_fuel.items())[:12]:
                lines.append(f"    {fuel:<32}| {cap:>8,.0f}")

    blank()
    sep("-")
    lines.append("  CONSISTENCY ALERTS")
    sep("-")
    if not result.alerts:
        lines.append("  [OK] No alerts — data consistent.")
    else:
        for alert in result.alerts:
            lines.append(f"  [WARNING]  {alert}")

    blank()
    sep("-")
    lines.append("  NOT AUDITED (M-F1b-01: no configured expectation, never silently skipped)")
    sep("-")
    if not result.not_audited:
        lines.append("  [OK] Every inspected layer has a configured expectation.")
    else:
        for layer, reason in sorted(result.not_audited.items()):
            lines.append(f"  [NOT AUDITED] {layer}: {reason}")

    blank()
    sep()
    lines.append("  SUMMARY")
    sep("-")
    s = result.summary

    # "Layers OK"/"Layers missing" now spans all 13 names in s.layers
    # (raster + vector combined) — 2026-08-24 (see DECISIONS.md same
    # date, "AuditSummary refactor to layer-keyed dict"). Before this
    # refactor these two rows were raster-only (built from
    # layers_ok/layers_missing, which _build_summary() only ever
    # populated from the rasters dict); vector status had its own
    # separate found/missing rows further below. A vector's "error"
    # status (found but unreadable) counts as "missing" here — this
    # pair of rows has never distinguished error from missing on either
    # side, raster or vector; that distinction is still visible in the
    # per-vector-layer rows immediately below and in the full VECTOR
    # LAYERS section earlier in the report.
    layers_ok = sorted(name for name, ls in s.layers.items() if ls.status == "ok")
    layers_not_ok = sorted(name for name, ls in s.layers.items() if ls.status != "ok")
    row("Layers OK", ", ".join(layers_ok) or "none")
    row("Layers missing", ", ".join(layers_not_ok) or "none")

    row("LC tiles (used)", f"{s.lc_tiles_used} / {s.lc_tiles_total}")
    row("Land cover area", f"{s.lc_total_area_km2:,.0f} km²")
    row("LC classes", s.lc_classes)

    solar_cfg = audit_config.layers.get("solar")
    solar_unit = (
        solar_cfg.unit
        if isinstance(solar_cfg, AuditLayerConfig) and solar_cfg.unit
        else "unit not configured"
    )
    _RASTER_RANGE_LABELS = {
        "solar": (f"Solar PVOUT ({solar_unit})", "{0} – {1}"),
        "elevation": ("Elevation (m)", "{0:.0f} – {1:.0f}"),
        "slope": ("Slope (°)", "{0:.1f} – {1:.1f}"),
        "population": ("Population (people/pixel)", "{0:.1f} – {1:.1f}"),
    }
    for layer_name, (label, fmt) in _RASTER_RANGE_LABELS.items():
        layer_summary = s.layers.get(layer_name)
        if layer_summary is not None and layer_summary.value_range is not None:
            row(label, fmt.format(*layer_summary.value_range))

    wind_summary = s.layers.get("wind")
    row("Wind files", wind_summary.file_count if wind_summary and wind_summary.file_count else 0)

    # First time these rows are sourced from result.summary.layers
    # instead of reading result.vectors directly — see DECISIONS.md
    # 2026-08-24 "AuditSummary refactor to layer-keyed dict" for why
    # this is a source/granularity change, not vectors appearing in
    # the footer for the first time (they already did, since "vector
    # layer audit depth", 2026-08-24 earlier the same day).
    _VECTOR_STATUS_DISPLAY = {
        "ok": "[OK] found",
        "missing": "[--] missing",
        "read_error": "[ERROR] found (read failed)",
        "processing_error": "[ERROR] found (processing failed)",
    }
    for vname, label in _VECTOR_LABELS.items():
        vector_summary = s.layers.get(vname)
        status = vector_summary.status if vector_summary is not None else "missing"
        row(label, _VECTOR_STATUS_DISPLAY[status])

    row("Power plants", s.total_plants)
    row("Installed capacity", f"{s.total_cap_mw:,.0f} MW")
    row("Alerts", s.n_alerts)
    row("Not audited", s.n_not_audited)

    blank()
    lines.append("  TIME PER STEP")
    sep("-")
    for step, t in result.timings.items():
        lines.append(f"    {step:<22}: {t:>6.1f}s")
    row("TOTAL", f"{result.elapsed_total:.1f}s", ind=4)
    sep()
    blank()

    return "\n".join(lines)


def _save_report(text: str, code: str, ts: datetime, outputs_dir: Path) -> Path:
    """Save the audit report to outputs/<code>/audit/audit_<code>_<timestamp>.txt.

    Legacy saved to a repo-root outputs/reports/ directory, which its own
    skip-check glob (outputs/<code>/audit/) never matched — a real bug
    flagged in docs/architecture/data_quality_audit.md sec d (BLOCKER-015).
    GeoFREA doesn't inherit this bug: the manifest-based resumability in
    core/orchestrator.py replaces the glob-based skip-check entirely, and
    the report is saved under the same outputs/<code>/ tree the manifest
    itself uses.
    """
    reports_dir = outputs_dir / code / "audit"
    reports_dir.mkdir(parents=True, exist_ok=True)
    p = reports_dir / f"audit_{code}_{ts.strftime('%Y%m%dT%H%M%S')}.txt"
    p.write_text(text, encoding="utf-8")
    return p
