"""Unit tests for geofrea.data_quality_audit.audit (the phase entry point).

Real-data smoke test: NOT INCLUDED, flagged rather than fabricated. A
real audit input fixture would need actual raw geodata (elevation/solar/
land-cover rasters) for PRT or BRA; GeoFREA has no data acquisition
layer yet (see audit.py's module docstring and AuditInputs' docstring in
schemas.py), so no such raw data exists inside this repo. The legacy
reference repo (geoworld_framework, read-only per CLAUDE.md) has aligned
(post-Phase-2a) rasters under data/processed/, but those are a different
pipeline stage's outputs, not Phase-1 raw inputs, and depending on a
path outside this repo would make the test fail on any machine/clone
without that sibling directory present — the same reasoning already
applied to tests/regression/conftest.py's baseline skip. Synthetic (but
real-format, real-CRS) rasters are used instead, same as
test_raster_inspection.py.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from geofrea.core.config_loader import load_parameters
from geofrea.core.orchestrator import PhaseContext
from geofrea.data_quality_audit.audit import run_audit_phase
from geofrea.data_quality_audit.schemas import AuditInputs

REPO_ROOT = Path(__file__).resolve().parents[2]
PARAMETERS_JSON = REPO_ROOT / "config" / "parameters.json"

_ORIGIN_LON, _ORIGIN_LAT = -9.0, 39.0
_RES = 0.01
_SIZE = 10


def _write_raster(path: Path, data: np.ndarray, nodata: float | None = -9999.0) -> None:
    transform = from_origin(_ORIGIN_LON, _ORIGIN_LAT, _RES, _RES)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=data.dtype,
        crs="EPSG:4326",
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(data, 1)


def _covering_gdf() -> gpd.GeoDataFrame:
    west, north = _ORIGIN_LON, _ORIGIN_LAT
    east = west + _SIZE * _RES
    south = north - _SIZE * _RES
    return gpd.GeoDataFrame(geometry=[box(west, south, east, north)], crs="EPSG:4326")


def _context(tmp_path: Path, country_code: str = "PRT") -> PhaseContext:
    country_params = load_parameters(PARAMETERS_JSON).countries[country_code]
    return PhaseContext(
        country_code=country_code,
        country_params=country_params,
        outputs_dir=tmp_path,
        prior_results={},
    )


@pytest.mark.unit
def test_run_audit_phase_with_no_inputs_reports_every_layer_missing(tmp_path):
    result = run_audit_phase(_context(tmp_path), AuditInputs())

    for layer in ("solar", "elevation", "population", "slope", "wind"):
        assert result.rasters[layer].error == "File not found"
    assert result.land_cover.error == "Tiles not found"
    assert result.power_plants.error is not None
    for vname in ("borders", "admin1", "grid", "roads", "protected", "lakes", "rivers"):
        assert result.vectors[vname].found is False
    # AuditSummary.layers replaced the flat layers_ok/layers_missing
    # fields 2026-08-24 (see DECISIONS.md same date, "AuditSummary
    # refactor to layer-keyed dict") — now spans all 12 raster+vector
    # names, not just rasters.
    assert all(ls.status != "ok" for ls in result.summary.layers.values())
    missing_rasters = {
        name
        for name, ls in result.summary.layers.items()
        if ls.kind == "raster" and ls.status == "missing"
    }
    assert missing_rasters == {"solar", "elevation", "population", "slope", "wind"}
    missing_vectors = {
        name
        for name, ls in result.summary.layers.items()
        if ls.kind == "vector" and ls.status == "missing"
    }
    assert missing_vectors == {
        "borders",
        "admin1",
        "grid",
        "roads",
        "protected",
        "lakes",
        "rivers",
    }


@pytest.mark.unit
def test_run_audit_phase_summary_footer_text_for_raster_and_vector_layer(tmp_path):
    # Confirms the actual FORMATTED report text (not just AuditSummary.
    # layers' shape) for one raster and one vector layer — 2026-08-24
    # (see DECISIONS.md same date, "AuditSummary refactor to
    # layer-keyed dict"), covering _format_report()'s rewritten SUMMARY
    # section end to end, not just the schema behind it.
    elevation_path = tmp_path / "elevation.tif"
    data = np.full((_SIZE, _SIZE), 100.0, dtype=np.float32)
    data[0, 0] = 300.0
    _write_raster(elevation_path, data)

    lake = box(_ORIGIN_LON, _ORIGIN_LAT - 0.02, _ORIGIN_LON + 0.01, _ORIGIN_LAT - 0.01)
    lakes_path = tmp_path / "lakes.geojson"
    gpd.GeoDataFrame(geometry=[lake], crs="EPSG:4326").to_file(lakes_path, driver="GeoJSON")

    inputs = AuditInputs(
        elevation_path=elevation_path,
        lakes_path=lakes_path,
        country_gdf=_covering_gdf(),
    )
    result = run_audit_phase(_context(tmp_path), inputs)
    report_text = Path(result.report_path).read_text(encoding="utf-8")
    summary_section = report_text.split("  SUMMARY")[1].split("TIME PER STEP")[0]
    summary_lines = summary_section.splitlines()

    # Raster: value_range surfaces in the SUMMARY footer with the
    # existing label/format string.
    elevation_line = next(line for line in summary_lines if "Elevation (m)" in line)
    assert "100" in elevation_line
    assert "300" in elevation_line

    # Vector: HydroLAKES shows [OK] found in the footer, now sourced
    # from AuditSummary.layers (not result.vectors read directly).
    lakes_line = next(line for line in summary_lines if "HydroLAKES" in line)
    assert "[OK] found" in lakes_line

    # The consolidated "Layers OK" row spans both kinds — a raster
    # name and a vector name on the same line.
    layers_ok_line = next(line for line in summary_lines if "Layers OK" in line)
    assert "elevation" in layers_ok_line
    assert "lakes" in layers_ok_line


@pytest.mark.unit
def test_run_audit_phase_writes_report_under_outputs_dir(tmp_path):
    result = run_audit_phase(_context(tmp_path), AuditInputs())

    assert result.report_path is not None
    report_path = Path(result.report_path)
    assert report_path.exists()
    assert report_path.parent == tmp_path / "PRT" / "audit"
    assert "DATA AUDIT REPORT" in report_path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_run_audit_phase_inspects_a_present_raster(tmp_path):
    elevation_path = tmp_path / "elevation.tif"
    _write_raster(elevation_path, np.full((_SIZE, _SIZE), 250.0, dtype=np.float32))

    inputs = AuditInputs(elevation_path=elevation_path, country_gdf=_covering_gdf())
    result = run_audit_phase(_context(tmp_path), inputs)

    assert result.rasters["elevation"].error is None
    assert result.rasters["elevation"].mean == pytest.approx(250.0)
    assert result.summary.layers["elevation"].status == "ok"
    assert result.summary.layers["elevation"].value_range == pytest.approx((250.0, 250.0))
    # Everything else is still genuinely absent.
    assert result.rasters["solar"].error == "File not found"
    assert result.summary.layers["solar"].status == "missing"


@pytest.mark.unit
def test_run_audit_phase_flags_pvout_unit_mismatch(tmp_path):
    # Realistic kWh/m2/day PVOUT is ~2-8; a raster full of ~4000 looks
    # like it's actually in kWh/kWp/yr.
    solar_path = tmp_path / "solar.tif"
    _write_raster(solar_path, np.full((_SIZE, _SIZE), 4000.0, dtype=np.float32))

    inputs = AuditInputs(solar_path=solar_path, country_gdf=_covering_gdf())
    result = run_audit_phase(_context(tmp_path), inputs)

    assert any("PVOUT" in alert for alert in result.alerts)


@pytest.mark.unit
def test_run_audit_phase_slope_threshold_check_uses_per_technology_values(tmp_path):
    # No slope raster: threshold_deg still reads from parameters.json per
    # technology, max_observed_deg is None, nothing is "inactive" without
    # data to judge that against.
    # Updated 2026-09-21: per METHODOLOGY S-02 scope (solar and wind only),
    # biomass was removed from _TECHNOLOGIES in audit.py.
    result = run_audit_phase(_context(tmp_path), AuditInputs())

    assert set(result.slope_threshold_check.keys()) == {"solar", "wind"}
    assert result.slope_threshold_check["solar"].threshold_deg == pytest.approx(5.0)
    assert result.slope_threshold_check["wind"].threshold_deg == pytest.approx(8.5)
    for check in result.slope_threshold_check.values():
        assert check.max_observed_deg is None
        assert check.inactive is False


@pytest.mark.unit
def test_run_audit_phase_slope_threshold_check_varies_by_technology(tmp_path):
    # PRT thresholds: solar=5.0, wind=8.5. A max observed
    # slope of exactly 5.0 must be inactive for wind (8.5 > 5.0)
    # but NOT for solar (5.0 is not strictly less than its own 5.0
    # threshold) — this is the per-technology behavior criterion 3/4
    # asked for, replacing the old single per-country 15.0 fallback.
    # Updated 2026-09-21: biomass was removed per METHODOLOGY S-02.
    slope_path = tmp_path / "slope.tif"
    _write_raster(slope_path, np.full((_SIZE, _SIZE), 5.0, dtype=np.float32))

    inputs = AuditInputs(slope_path=slope_path, country_gdf=_covering_gdf())
    result = run_audit_phase(_context(tmp_path), inputs)

    assert result.slope_threshold_check["solar"].max_observed_deg == pytest.approx(5.0)
    assert result.slope_threshold_check["solar"].inactive is False
    assert result.slope_threshold_check["wind"].inactive is True

    assert not any("INACTIVE CRITERION [slope/solar]" in alert for alert in result.alerts)
    assert any("INACTIVE CRITERION [slope/wind]" in alert for alert in result.alerts)


@pytest.mark.unit
def test_run_audit_phase_slope_threshold_check_reads_bra_values(tmp_path):
    # BRA shares the same slope_threshold_deg values as PRT in
    # parameters.json (no country-specific slope source found this
    # session) — confirms the read goes through context.country_params
    # for the actual requested country, not a hardcoded PRT assumption.
    # Updated 2026-09-21: biomass was removed per METHODOLOGY S-02.
    result = run_audit_phase(_context(tmp_path, country_code="BRA"), AuditInputs())

    assert result.slope_threshold_check["solar"].threshold_deg == pytest.approx(5.0)
    assert result.slope_threshold_check["wind"].threshold_deg == pytest.approx(8.5)


@pytest.mark.unit
def test_run_audit_phase_skip_land_cover_flag(tmp_path):
    inputs = AuditInputs(skip_land_cover=True)
    result = run_audit_phase(_context(tmp_path), inputs)

    assert result.land_cover.skipped is True
    assert "land_cover" in result.skipped


@pytest.mark.unit
def test_run_audit_phase_inspects_power_plants(tmp_path):
    plants_df = pd.DataFrame(
        {"capacity_mw": [12.0, 8.0], "primary_fuel": ["Hydro", "Hydro"]}
    )
    inputs = AuditInputs(plants_df=plants_df)
    result = run_audit_phase(_context(tmp_path), inputs)

    assert result.power_plants.total_plants == 2
    assert result.power_plants.total_capacity_mw == pytest.approx(20.0)
    assert result.power_plants.by_fuel["Hydro"] == pytest.approx(20.0)


@pytest.mark.unit
def test_run_audit_phase_lakes_and_rivers_presence(tmp_path):
    # Extended 2026-08-24 (see DECISIONS.md same date, "vector layer
    # audit depth"): lakes/rivers now open the file, not just
    # stat()/exists() — a corrupted file is caught and reported via
    # `error`, not silently treated as "found with no other data".
    # country_gdf is required here since 2026-08-26 (clip=True + no
    # country_gdf now raises ClipRequiresCountryGdfError instead of
    # falling back to an unclipped full-file read — see that class's
    # docstring) — this test is about corrupted-file handling, not that
    # guard, so a real (if unused, given the file never parses)
    # country_gdf is supplied to reach the code path being tested.
    lakes_path = tmp_path / "lakes.gpkg"
    lakes_path.write_bytes(b"not a real geopackage, presence-only check")

    inputs = AuditInputs(lakes_path=lakes_path, country_gdf=_covering_gdf())
    result = run_audit_phase(_context(tmp_path), inputs)

    assert result.vectors["lakes"].found is True
    assert result.vectors["lakes"].name == "lakes.gpkg"
    assert result.vectors["lakes"].error is not None
    assert result.vectors["rivers"].found is False


@pytest.mark.unit
def test_run_audit_phase_inspects_a_valid_global_vector_layer_clipped(tmp_path):
    mainland = box(_ORIGIN_LON, _ORIGIN_LAT - 0.05, _ORIGIN_LON + 0.05, _ORIGIN_LAT)
    country_gdf = gpd.GeoDataFrame(geometry=[mainland], crs="EPSG:4326")

    lake_inside = box(_ORIGIN_LON, _ORIGIN_LAT - 0.02, _ORIGIN_LON + 0.01, _ORIGIN_LAT - 0.01)
    lake_outside = box(50.0, 50.0, 50.1, 50.1)
    lakes_path = tmp_path / "lakes.geojson"
    gpd.GeoDataFrame(geometry=[lake_inside, lake_outside], crs="EPSG:4326").to_file(
        lakes_path, driver="GeoJSON"
    )

    inputs = AuditInputs(lakes_path=lakes_path, country_gdf=country_gdf)
    result = run_audit_phase(_context(tmp_path), inputs)

    lakes = result.vectors["lakes"]
    assert lakes.found is True
    assert lakes.error is None
    assert lakes.clipped_to_country is True
    assert lakes.n_features == 1
    assert lakes.total_area_km2 is not None
    assert lakes.geometry_types == ["Polygon"]


@pytest.mark.unit
def test_run_audit_phase_protected_areas_iucn_breakdown(tmp_path):
    mainland = box(_ORIGIN_LON, _ORIGIN_LAT - 0.05, _ORIGIN_LON + 0.05, _ORIGIN_LAT)
    country_gdf = gpd.GeoDataFrame(geometry=[mainland], crs="EPSG:4326")

    park_ii = box(_ORIGIN_LON, _ORIGIN_LAT - 0.02, _ORIGIN_LON + 0.01, _ORIGIN_LAT - 0.01)
    reserve_iv = box(_ORIGIN_LON + 0.01, _ORIGIN_LAT - 0.02, _ORIGIN_LON + 0.02, _ORIGIN_LAT - 0.01)
    protected_path = tmp_path / "protected.geojson"
    gpd.GeoDataFrame(
        {"IUCN_CAT": ["II", "IV"]},
        geometry=[park_ii, reserve_iv],
        crs="EPSG:4326",
    ).to_file(protected_path, driver="GeoJSON")

    inputs = AuditInputs(protected_path=protected_path, country_gdf=country_gdf)
    result = run_audit_phase(_context(tmp_path), inputs)

    protected = result.vectors["protected"]
    assert protected.found is True
    assert protected.attribute_breakdown is not None
    # Bucket keys are lowercase since 2026-08-24 (see DECISIONS.md same
    # date, "IUCN category normalization fix") — "II"/"IV" normalize to
    # "ii"/"iv", replicating compute_protected_areas()'s own
    # .str.lower().str.strip() before it looks values up in IUCN_SCORES.
    assert set(protected.attribute_breakdown) == {"ii", "iv"}
    assert protected.attribute_breakdown["ii"].count == 1


@pytest.mark.unit
def test_run_audit_phase_borders_and_admin1_are_not_clipped(tmp_path):
    # borders/admin1/grid are already scoped to one country at the
    # acquisition source (GADM/OSM) — clip=False, see
    # vector_inspection.py's module docstring and DECISIONS.md
    # 2026-08-24 "vector layer audit depth". `roads` used to be in this
    # group too but flipped to clip=True 2026-09-08 (GRIP4 regional
    # file, see DECISIONS.md same date, Fase 2) — see
    # test_run_audit_phase_roads_is_clipped below instead. No
    # country_gdf is passed here at all, to prove clipping does not
    # happen / is not required for borders.
    borders_path = tmp_path / "borders.geojson"
    admin1_a = box(_ORIGIN_LON, _ORIGIN_LAT - 0.05, _ORIGIN_LON + 0.02, _ORIGIN_LAT)
    admin1_b = box(_ORIGIN_LON + 0.02, _ORIGIN_LAT - 0.05, _ORIGIN_LON + 0.05, _ORIGIN_LAT)
    gpd.GeoDataFrame(geometry=[admin1_a, admin1_b], crs="EPSG:4326").to_file(
        borders_path, driver="GeoJSON"
    )

    inputs = AuditInputs(borders_path=borders_path)
    result = run_audit_phase(_context(tmp_path), inputs)

    borders = result.vectors["borders"]
    assert borders.found is True
    assert borders.clipped_to_country is False
    assert borders.n_features == 2


@pytest.mark.unit
def test_run_audit_phase_roads_is_clipped(tmp_path):
    # roads flipped from clip=False (per-country OSM download) to
    # clip=True (GRIP4 regional shapefile, shared across countries)
    # 2026-09-08 — see DECISIONS.md same date, "wire das 5 camadas
    # restantes a partir do banco local, Fase 2 - roads". Mirrors
    # test_run_audit_phase_inspects_a_valid_global_vector_layer_clipped
    # above (same pattern already proven for lakes).
    mainland = box(_ORIGIN_LON, _ORIGIN_LAT - 0.05, _ORIGIN_LON + 0.05, _ORIGIN_LAT)
    country_gdf = gpd.GeoDataFrame(geometry=[mainland], crs="EPSG:4326")

    road_inside = box(_ORIGIN_LON, _ORIGIN_LAT - 0.02, _ORIGIN_LON + 0.01, _ORIGIN_LAT - 0.01)
    road_outside = box(50.0, 50.0, 50.1, 50.1)
    roads_path = tmp_path / "roads.geojson"
    gpd.GeoDataFrame(geometry=[road_inside, road_outside], crs="EPSG:4326").to_file(
        roads_path, driver="GeoJSON"
    )

    inputs = AuditInputs(roads_path=roads_path, country_gdf=country_gdf)
    result = run_audit_phase(_context(tmp_path), inputs)

    roads = result.vectors["roads"]
    assert roads.found is True
    assert roads.error is None
    assert roads.clipped_to_country is True
    assert roads.n_features == 1
