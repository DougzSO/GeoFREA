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

    for layer in ("solar", "elevation", "population", "slope", "wind", "seismic"):
        assert result.rasters[layer].error == "File not found"
    assert result.land_cover.error == "Tiles not found"
    assert result.power_plants.error is not None
    assert result.lakes.found is False
    assert result.rivers.found is False
    assert result.summary.layers_ok == []
    assert set(result.summary.layers_missing) == {
        "solar",
        "elevation",
        "population",
        "slope",
        "wind",
        "seismic",
    }


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
    assert "elevation" in result.summary.layers_ok
    # Everything else is still genuinely absent.
    assert result.rasters["solar"].error == "File not found"


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
    result = run_audit_phase(_context(tmp_path), AuditInputs())

    assert set(result.slope_threshold_check.keys()) == {"biomass", "solar", "wind"}
    assert result.slope_threshold_check["biomass"].threshold_deg == pytest.approx(8.5)
    assert result.slope_threshold_check["solar"].threshold_deg == pytest.approx(5.0)
    assert result.slope_threshold_check["wind"].threshold_deg == pytest.approx(8.5)
    for check in result.slope_threshold_check.values():
        assert check.max_observed_deg is None
        assert check.inactive is False


@pytest.mark.unit
def test_run_audit_phase_slope_threshold_check_varies_by_technology(tmp_path):
    # PRT thresholds: biomass=8.5, solar=5.0, wind=8.5. A max observed
    # slope of exactly 5.0 must be inactive for biomass/wind (8.5 > 5.0)
    # but NOT for solar (5.0 is not strictly less than its own 5.0
    # threshold) — this is the per-technology behavior criterion 3/4
    # asked for, replacing the old single per-country 15.0 fallback.
    slope_path = tmp_path / "slope.tif"
    _write_raster(slope_path, np.full((_SIZE, _SIZE), 5.0, dtype=np.float32))

    inputs = AuditInputs(slope_path=slope_path, country_gdf=_covering_gdf())
    result = run_audit_phase(_context(tmp_path), inputs)

    assert result.slope_threshold_check["biomass"].max_observed_deg == pytest.approx(5.0)
    assert result.slope_threshold_check["biomass"].inactive is True
    assert result.slope_threshold_check["solar"].inactive is False
    assert result.slope_threshold_check["wind"].inactive is True

    assert any("INACTIVE CRITERION [slope/biomass]" in alert for alert in result.alerts)
    assert any("INACTIVE CRITERION [slope/wind]" in alert for alert in result.alerts)
    assert not any("INACTIVE CRITERION [slope/solar]" in alert for alert in result.alerts)


@pytest.mark.unit
def test_run_audit_phase_slope_threshold_check_reads_bra_values(tmp_path):
    # BRA shares the same slope_threshold_deg values as PRT in
    # parameters.json (no country-specific slope source found this
    # session) — confirms the read goes through context.country_params
    # for the actual requested country, not a hardcoded PRT assumption.
    result = run_audit_phase(_context(tmp_path, country_code="BRA"), AuditInputs())

    assert result.slope_threshold_check["biomass"].threshold_deg == pytest.approx(8.5)
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
    lakes_path = tmp_path / "lakes.gpkg"
    lakes_path.write_bytes(b"not a real geopackage, presence-only check")

    inputs = AuditInputs(lakes_path=lakes_path)
    result = run_audit_phase(_context(tmp_path), inputs)

    assert result.lakes.found is True
    assert result.lakes.name == "lakes.gpkg"
    assert result.rivers.found is False
