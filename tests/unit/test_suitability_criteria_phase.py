"""Unit tests for geofrea.suitability_criteria.phase (orchestration).

Synthetic 4x5 aligned rasters. The pixel-exact baseline comparison is a
separate regression test.
"""

import copy
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Polygon

from geofrea.core.config_loader import load_parameters
from geofrea.core.constants import NODATA_FLOAT
from geofrea.core.orchestrator import (
    Orchestrator,
    PhaseContext,
    PhaseExecutionError,
    PhaseSpec,
    RunManifest,
)
from geofrea.core.schemas import CriteriaParams
from geofrea.grid_alignment.schemas import GridMetadata
from geofrea.suitability_criteria.phase import run_suitability_criteria_phase
from geofrea.suitability_criteria.schemas import (
    SuitabilityCriteriaInputs,
    SuitabilityCriteriaResult,
)
from tests.unit.test_schemas import VALID_CRITERIA

_REPO_ROOT = Path(__file__).resolve().parents[2]

HEIGHT, WIDTH = 4, 5
TRANSFORM = from_origin(-9.5, 42.15, 0.01, 0.01)


def _write(path, fill):
    arr = np.full((HEIGHT, WIDTH), fill, dtype=np.float32)
    arr[0, 0] = fill * 2 + 1.0  # a little variation so percentile maths is non-degenerate
    arr[1, 1] = fill * 3 + 2.0
    with rasterio.open(
        path, "w", driver="GTiff", height=HEIGHT, width=WIDTH, count=1, dtype="float32",
        crs="EPSG:4326", transform=TRANSFORM, nodata=NODATA_FLOAT,
    ) as dst:
        dst.write(arr, 1)
    return path


def _write_lakes(path):
    arr = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)  # 0 = land
    arr[0, 0] = 1  # one lake pixel
    arr[-1, -1] = 255  # one outside-country pixel
    with rasterio.open(
        path, "w", driver="GTiff", height=HEIGHT, width=WIDTH, count=1, dtype="uint8",
        crs="EPSG:4326", transform=TRANSFORM, nodata=255,
    ) as dst:
        dst.write(arr, 1)
    return path


def _grid_metadata() -> GridMetadata:
    return GridMetadata(
        crs="EPSG:4326",
        resolution_deg=0.01,
        width=WIDTH,
        height=HEIGHT,
        transform=tuple(TRANSFORM)[:6],
        n_valid_pixels=HEIGHT * WIDTH,
    )


def _mainland() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"geometry": [Polygon([(-9.5, 42.1), (-9.45, 42.1), (-9.45, 42.15), (-9.5, 42.15)])]},
        crs="EPSG:4326",
    )


def _inputs(tmp_path, *, with_roads=True, with_rivers=True, with_wind=True) -> SuitabilityCriteriaInputs:
    d = tmp_path / "aligned"
    d.mkdir()
    fields = {
        "elevation": _write(d / "elev.tif", 100.0),
        "slope": _write(d / "slope.tif", 3.0),
        "solar": _write(d / "solar.tif", 4.0),
        "land_cover": _write(d / "lc.tif", 30.0),
        "grid": _write(d / "grid.tif", 2.5),
        "lakes": _write_lakes(d / "lakes.tif"),
        "population": _write(d / "pop.tif", 50.0),
        "seismic": _write(d / "seismic.tif", 0.8),
    }
    if with_wind:
        fields["wind"] = _write(d / "wind.tif", 6.0)
    if with_roads:
        fields["roads"] = _write(d / "roads.tif", 2.0)
    if with_rivers:
        fields["rivers"] = _write(d / "rivers.tif", 1.5)
    return SuitabilityCriteriaInputs(
        **fields,
        grid_metadata=_grid_metadata(),
        criteria=CriteriaParams.model_validate(copy.deepcopy(VALID_CRITERIA)),
        yield_by_land_cover={30: 5.0},
        terrain_slope_threshold_deg=10.0,
        mainland_gdf=_mainland(),
    )


def _context(tmp_path) -> PhaseContext:
    return PhaseContext(
        country_code="PRT",
        country_params=None,  # phase does not read it (config flows via inputs)
        outputs_dir=tmp_path / "outputs",
        prior_results={},
    )


IMPLEMENTED = {
    "solar_resource",
    "wind_resource",
    "road_suitability",
    "river_biomass",
    "terrain_score",
    "lc_biomass",
    "biomass_resource",
    "grid_suitability",
    "river_solar",
    "river_wind",
    "lakes_exclusion",
    "pop_suitability",
    "seismic_suitability",
    "protected_areas",
}


@pytest.mark.unit
def test_phase_produces_all_implemented_criteria(tmp_path):
    result = run_suitability_criteria_phase(_context(tmp_path), _inputs(tmp_path))
    assert set(result.criteria) == IMPLEMENTED
    assert result.summary.n_criteria == len(IMPLEMENTED)
    assert result.country_code == "PRT"


@pytest.mark.unit
def test_phase_writes_slope_degrees_outside_criteria(tmp_path):
    result = run_suitability_criteria_phase(_context(tmp_path), _inputs(tmp_path))
    assert result.slope_degrees_tif is not None
    assert result.slope_degrees_tif.name == "slope_degrees.tif"
    assert result.slope_degrees_tif.exists()
    assert result.slope_degrees_png is not None
    assert result.slope_degrees_png.name == "slope_degrees.png"
    assert result.slope_degrees_png.exists()
    assert "slope_degrees" not in result.criteria


@pytest.mark.unit
def test_phase_writes_one_tif_per_criterion(tmp_path):
    result = run_suitability_criteria_phase(_context(tmp_path), _inputs(tmp_path))
    for name, layer in result.criteria.items():
        assert layer.tif_path.exists()
        assert layer.tif_path.name == f"{name}.tif"
        assert layer.figure_path is not None
        assert layer.figure_path.exists()
        assert layer.figure_path.name == f"{name}.png"
        with rasterio.open(layer.tif_path) as src:
            assert (src.height, src.width) == (HEIGHT, WIDTH)
            assert src.nodata == NODATA_FLOAT


@pytest.mark.unit
def test_phase_writes_report(tmp_path):
    result = run_suitability_criteria_phase(_context(tmp_path), _inputs(tmp_path))
    assert result.report_path.exists()
    assert result.report_path.name == "criteria_summary_PRT.txt"
    text = result.report_path.read_text(encoding="utf-8")
    assert "SUITABILITY CRITERIA SUMMARY" in text
    assert "road_suitability" in text


@pytest.mark.unit
def test_phase_separates_input_absent_from_not_implemented(tmp_path):
    result = run_suitability_criteria_phase(
        _context(tmp_path), _inputs(tmp_path, with_roads=False)
    )
    assert "road_suitability" not in result.criteria
    # road_suitability IS wired, but its input layer was absent this run
    assert result.summary.missing_expected == ["road_suitability"]
    # all 14 canonical criteria are implemented in this build
    assert result.summary.not_implemented == []
    # no WDPA file supplied -> mainland assumed unrestricted
    assert result.summary.protected_source == "assumed_free"


@pytest.mark.unit
def test_phase_protected_areas_assumed_free_without_wdpa(tmp_path):
    result = run_suitability_criteria_phase(_context(tmp_path), _inputs(tmp_path))
    assert "protected_areas" in result.criteria
    assert result.summary.protected_source == "assumed_free"
    with rasterio.open(result.criteria["protected_areas"].tif_path) as src:
        arr = src.read(1)
    inside = arr != NODATA_FLOAT
    assert inside.any()
    assert np.array_equal(np.unique(arr[inside]), np.array([1.0], dtype=np.float32))


@pytest.mark.unit
def test_phase_buckets_partition_canonical_criteria(tmp_path):
    from geofrea.suitability_criteria.schemas import CANONICAL_CRITERIA

    result = run_suitability_criteria_phase(_context(tmp_path), _inputs(tmp_path))
    buckets = (
        set(result.criteria)
        | set(result.summary.missing_expected)
        | set(result.summary.not_implemented)
    )
    assert buckets == set(CANONICAL_CRITERIA)


@pytest.mark.unit
def test_phase_raises_when_required_layer_missing(tmp_path):
    inp = _inputs(tmp_path)
    object.__setattr__(inp, "land_cover", None)
    with pytest.raises(RuntimeError, match="requires aligned"):
        run_suitability_criteria_phase(_context(tmp_path), inp)


@pytest.mark.unit
def test_phase_raises_on_topology_mismatch(tmp_path):
    inp = _inputs(tmp_path)
    # claim a different grid shape than the rasters actually have
    object.__setattr__(inp, "grid_metadata", inp.grid_metadata.model_copy(update={"width": 99}))
    with pytest.raises(RuntimeError, match="Topology mismatch"):
        run_suitability_criteria_phase(_context(tmp_path), inp)


@pytest.mark.unit
def test_phase_result_round_trips_through_output_model(tmp_path):
    result = run_suitability_criteria_phase(_context(tmp_path), _inputs(tmp_path))
    reloaded = SuitabilityCriteriaResult.model_validate(result.model_dump(mode="json"))
    assert reloaded == result


@pytest.mark.unit
def test_corrupted_wdpa_error_message_survives_to_orchestrator_output(tmp_path):
    # The RuntimeError from compute_protected_areas (WDPA file present but
    # unreadable — DECISIONS.md 2026-09-11) must reach a production
    # operator WITHOUT them opening a traceback: its text has to survive
    # verbatim into (a) the PhaseExecutionError message main.py logs and
    # (b) the persisted manifest's `error` field.
    bad_wdpa = tmp_path / "WDPA_broken_shp-polygons.shp"
    bad_wdpa.write_bytes(b"\x00 not a shapefile \xff" * 8)
    inp = _inputs(tmp_path).model_copy(update={"wdpa_path": bad_wdpa})

    spec = PhaseSpec(
        name="suitability_criteria",
        output_model=SuitabilityCriteriaResult,
        run=lambda ctx: run_suitability_criteria_phase(ctx, inp),
    )
    orchestrator = Orchestrator(
        outputs_dir=tmp_path / "out",
        country_code="PRT",
        country_params=load_parameters(_REPO_ROOT / "config" / "parameters.json").countries["PRT"],
        phases_enabled={"suitability_criteria": True},
    )

    with pytest.raises(PhaseExecutionError) as excinfo:
        orchestrator.run([spec])

    # (a) the exception the CLI logs, one line, no traceback needed
    final_msg = str(excinfo.value)
    assert "Phase 'suitability_criteria' failed" in final_msg
    assert "protected_areas: WDPA shapefile" in final_msg
    assert "present but could not be read" in final_msg
    assert bad_wdpa.name in final_msg
    # a generic I/O failure in another layer would NOT contain these

    # (b) the same diagnostic, persisted to manifest.json on disk
    on_disk = RunManifest.model_validate_json(
        orchestrator.manifest_path.read_text(encoding="utf-8")
    )
    entry = on_disk.phases["suitability_criteria"]
    assert entry.status == "failed"
    assert "protected_areas: WDPA shapefile" in entry.error
    assert "present but could not be read" in entry.error
