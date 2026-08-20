"""data_quality_audit phase entry point.

Ports geoworld_framework's DataAuditor.run() (see
docs/architecture/data_quality_audit.md) into GeoFREA's orchestrator
contract: run_audit_phase(context, inputs) -> AuditResult, a validated
Pydantic model, instead of legacy's ad hoc dict. See DECISIONS.md
2026-08-20 - orchestrator + data_quality_audit phase.

Known simplifications vs. legacy (flagged here rather than silently
carried over or silently fixed):
  - No `country_name`: GeoFREA's parameters.json keys countries by ISO
    code only, with no name-lookup table (legacy accepted a name or code
    as CLI input and resolved it via ConfigLoader.get_country_by_name()).
    The audit report header uses country_code only.
  - `expected_resolutions` / `res_tolerance` stay as named module
    constants, not settings.yaml keys: legacy's own architecture notes
    (docs/architecture/data_quality_audit.md sec c) classify these as
    diagnostic-gate defaults, not scientific parameters — they gate only
    this phase's own alert text, never a downstream calculation.

slope_threshold_deg is technology-specific (CountryParams.technologies.
<tech>.slope_threshold_deg), not the legacy's single hardcoded 15.0°
per-country fallback — see docs/DECISIONS.md 2026-08-20 -
slope_threshold_deg moved to parameters.json. The slope-inactivity
check therefore runs once per technology (biomass/solar/wind), not
once per country.
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
    AuditInputs,
    AuditResult,
    AuditSummary,
    LandCoverInspection,
    PowerPlantsInspection,
    RasterInspection,
    SlopeThresholdCheck,
    VectorLayerInspection,
)

logger = logging.getLogger("geofrea.data_quality_audit.audit")

# Diagnostic-gate defaults — see module docstring. Not scientific
# parameters, so not sourced from parameters.json/settings.yaml.
_EXPECTED_RESOLUTIONS_DEG: dict[str, float] = {
    "land_cover": 0.0001,
    "solar": 0.0083,
    "wind": 0.0083,
    "elevation": 0.005,
    "slope": 0.005,
}
_RESOLUTION_TOLERANCE = 0.5
_SOLAR_PVOUT_SANITY_RANGE = (1.0, 10.0)  # kWh/m2/day
_TECHNOLOGIES = ("biomass", "solar", "wind")


def run_audit_phase(context: PhaseContext, inputs: AuditInputs) -> AuditResult:
    """Audit raw country data before any processing.

    Args:
        context: Shared phase context (country_code, outputs_dir, ...).
        inputs: Already-resolved raster/vector/tabular inputs to inspect.

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
        "seismic": inputs.seismic_path,
    }

    rasters: dict[str, dict] = {}
    for layer, path in raster_map.items():
        if path and Path(path).exists():
            with timer(layer, timings):
                meta = inspect_raster(Path(path), country_gdf=inputs.country_gdf)
                rasters[layer] = meta

                if layer == "solar":
                    solar_mean = meta.get("mean")
                    lo, hi = _SOLAR_PVOUT_SANITY_RANGE
                    if solar_mean is not None and not (lo < solar_mean < hi):
                        msg = (
                            f"PVOUT appears to be in incorrect units (mean "
                            f"{solar_mean:.1f}). Expected: kWh/m2/day (~{lo} to {hi}). "
                            f"Is the file in kWh/kWp/yr?"
                        )
                        logger.error("  %s", msg)
                        alerts.append(msg)
        else:
            rasters[layer] = {"error": "File not found"}
            timings[layer] = 0.0

    # ── Vector layers (lakes/rivers): presence and size only ──────────
    vector_layers: dict[str, dict] = {}
    for vname, vpath in [("lakes", inputs.lakes_path), ("rivers", inputs.rivers_path)]:
        if vpath and Path(vpath).exists():
            size_mb = round(Path(vpath).stat().st_size / 1e6, 1)
            vector_layers[vname] = {"found": True, "name": Path(vpath).name, "size_mb": size_mb}
        else:
            vector_layers[vname] = {"found": False}
        timings[vname] = 0.0

    # ── Land cover ──────────────────────────────────────────────────
    if inputs.skip_land_cover:
        land_cover: dict = {"skipped": True}
        skipped.append("land_cover")
        timings["land_cover"] = 0.0
        logger.info("  [land_cover] SKIP enabled.")
    elif inputs.land_cover_tiles:
        with timer("land_cover", timings):
            land_cover = inspect_land_cover_tiles(
                inputs.land_cover_tiles, country_gdf=inputs.country_gdf
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
    alerts.extend(diagnose_consistency(rasters, _EXPECTED_RESOLUTIONS_DEG, _RESOLUTION_TOLERANCE))

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
    summary = _build_summary(rasters, land_cover, power_plants, alerts, n_wind)
    elapsed_total = round((datetime.now(UTC) - started_at).total_seconds(), 1)

    result = AuditResult(
        country_code=context.country_code,
        timestamp=started_at.isoformat(),
        rasters={k: RasterInspection.model_validate(v) for k, v in rasters.items()},
        land_cover=LandCoverInspection.model_validate(land_cover),
        power_plants=PowerPlantsInspection.model_validate(power_plants),
        lakes=VectorLayerInspection.model_validate(vector_layers["lakes"]),
        rivers=VectorLayerInspection.model_validate(vector_layers["rivers"]),
        alerts=alerts,
        slope_threshold_check=slope_threshold_check,
        summary=summary,
        timings=timings,
        skipped=skipped,
        elapsed_total=elapsed_total,
        report_path=None,
    )

    report_text = _format_report(result)
    print(report_text)
    report_path = _save_report(report_text, context.country_code, started_at, context.outputs_dir)
    logger.info("Report saved: %s", report_path)

    return result.model_copy(update={"report_path": str(report_path)})


def _build_summary(
    rasters: dict[str, dict],
    land_cover: dict,
    power_plants: dict,
    alerts: list[str],
    n_wind: int,
) -> AuditSummary:
    """Build a concise summary from the raw audit dicts."""
    lc = land_cover or {}
    pp = power_plants or {}

    layers_ok: list[str] = []
    layers_missing: list[str] = []
    range_by_layer: dict[str, tuple[float, float] | None] = {
        "solar_range": None,
        "elev_range": None,
        "slope_range": None,
        "pop_range": None,
        "seismic_range": None,
    }
    range_map = {
        "solar": "solar_range",
        "elevation": "elev_range",
        "slope": "slope_range",
        "population": "pop_range",
        "seismic": "seismic_range",
    }

    for layer, meta in rasters.items():
        if meta.get("error"):
            layers_missing.append(layer)
        else:
            layers_ok.append(layer)
            if meta.get("min") is not None and layer in range_map:
                range_by_layer[range_map[layer]] = (meta["min"], meta["max"])

    return AuditSummary(
        layers_ok=layers_ok,
        layers_missing=layers_missing,
        n_wind_files=n_wind,
        lc_tiles_used=lc.get("tiles_used", 0),
        lc_tiles_total=lc.get("n_tiles", 0),
        lc_total_area_km2=lc.get("total_area_km2", 0),
        lc_classes=len(lc.get("class_stats", {})),
        total_plants=pp.get("total_plants", 0),
        total_cap_mw=pp.get("total_capacity_mw", 0),
        n_alerts=len(alerts),
        **range_by_layer,
    )


def _format_report(result: AuditResult) -> str:
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
    lines.append("  HYDROLOGY (VECTORS)")
    sep("-")
    for vname, label, layer in [
        ("lakes", "HydroLAKES", result.lakes),
        ("rivers", "HydroRIVERS", result.rivers),
    ]:
        if layer.found:
            lines.append(f"  [OK] {label}")
            row("File", layer.name or "—")
            row("Size", f"{layer.size_mb} MB  (global — crop in a later phase)")
        else:
            lines.append(f"  [MISSING] {label:<12}: not found")
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
    sep()
    lines.append("  SUMMARY")
    sep("-")
    s = result.summary
    row("Layers OK", ", ".join(s.layers_ok) or "none")
    row("Missing layers", ", ".join(s.layers_missing) or "none")
    row("LC tiles (used)", f"{s.lc_tiles_used} / {s.lc_tiles_total}")
    row("Land cover area", f"{s.lc_total_area_km2:,.0f} km²")
    row("LC classes", s.lc_classes)
    row("Wind files", s.n_wind_files)

    range_labels = {
        "solar_range": ("Solar PVOUT (kWh/m²/d)", "{0} – {1}"),
        "elev_range": ("Elevation (m)", "{0:.0f} – {1:.0f}"),
        "slope_range": ("Slope (°)", "{0:.1f} – {1:.1f}"),
        "pop_range": ("Population (people/pixel)", "{0:.1f} – {1:.1f}"),
        "seismic_range": ("Seismicity (hazard)", "{0:.4f} – {1:.4f}"),
    }
    for key, (label, fmt) in range_labels.items():
        value = getattr(s, key)
        if value:
            row(label, fmt.format(*value))

    row("HydroLAKES", "[OK] found" if result.lakes.found else "[--] missing")
    row("HydroRIVERS", "[OK] found" if result.rivers.found else "[--] missing")
    row("Power plants", s.total_plants)
    row("Installed capacity", f"{s.total_cap_mw:,.0f} MW")
    row("Alerts", s.n_alerts)

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
