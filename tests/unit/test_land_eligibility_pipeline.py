"""F3 end to end on a small synthetic country: exclusions, fractional E1/E3, aggregation, candidates, invariants (V-03)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString, box

from geofrea.land_eligibility.eligibility import (
    EligibilityLayers,
    MissingExclusionLayerError,
    eligible_fraction,
)
from geofrea.land_eligibility.parameters import ParameterSet
from geofrea.land_eligibility.pipeline import LandEligibilityError, build_eligibility
from geofrea.suitability_criteria.physical_layers import SitingLayersResult

EXPERIMENTS = Path(__file__).resolve().parents[2] / "config" / "experiments.yaml"
H, W = 20, 30  # pixels of 0.01 degree: 4 x 6 cells of 0.05 degree
LON0, LAT0 = 10.0, 5.0  # on the 0.05 degree lattice
TRANSFORM = from_origin(LON0, LAT0, 0.01, 0.01)


def _write(path: Path, data: np.ndarray, dtype="float32", nodata=-9999.0) -> Path:
    with rasterio.open(
        path, "w", driver="GTiff", height=H, width=W, count=1, dtype=dtype, crs="EPSG:4326", transform=TRANSFORM, nodata=nodata
    ) as dst:
        dst.write(data.astype(dtype), 1)
    return path


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path / "data"))
    land_cover = np.full((H, W), 30.0)  # grassland: allowed
    land_cover[:, :5] = 10.0  # tree cover in cell column 0: excluded for both technologies
    slope = np.zeros((H, W))
    slope[:5, 25:] = 40.0  # steep corner: excluded by E4
    population = np.zeros((H, W))
    base = tmp_path / "rasters"
    base.mkdir()
    flag = np.zeros((H, W))
    grid_result = SimpleNamespace(
        slope=_write(base / "slope.tif", slope),
        population=_write(base / "pop.tif", population),
        land_cover=_write(base / "lc.tif", land_cover),
        grid=_write(base / "grid.tif", np.full((H, W), 7.0)),
        grid_distance_capped=_write(base / "gcap.tif", flag, "uint8", 0),
        roads_distance_capped=_write(base / "rcap.tif", flag, "uint8", 0),
    )
    layers = {"dist_grid_km": 7.0, "dist_road_km": 2.0, "pvout_kwh_kwp_day": 4.5}
    for h in (100, 150, 200):
        layers.update({f"weibull_a_{h}m": 7.0, f"weibull_k_{h}m": 2.0, f"air_density_{h}m": 1.2})
    siting = SitingLayersResult(
        country_code="ZZZ", layers={name: _write(base / f"{name}.tif", np.full((H, W), v)) for name, v in layers.items()}
    )
    country = gpd.GeoDataFrame(geometry=[box(LON0, LAT0 - 0.2, LON0 + 0.3, LAT0)], crs="EPSG:4326")
    protected = gpd.GeoDataFrame({"IUCN_CAT": ["II"]}, geometry=[box(LON0 + 0.10, LAT0 - 0.2, LON0 + 0.15, LAT0)], crs="EPSG:4326")
    protected.to_file(tmp_path / "wdpa.gpkg", driver="GPKG")
    rivers = gpd.GeoDataFrame(geometry=[LineString([(LON0 + 0.205, LAT0), (LON0 + 0.205, LAT0 - 0.2)])], crs="EPSG:4326")
    rivers.to_file(tmp_path / "rivers.gpkg", driver="GPKG")
    return SimpleNamespace(
        grid_result=grid_result, siting=siting, country=country, protected=tmp_path / "wdpa.gpkg", rivers=tmp_path / "rivers.gpkg"
    )


def _run(world, techs=("solar",)):
    return build_eligibility(
        "ZZZ", EXPERIMENTS, world.grid_result, world.siting, world.country, world.protected, None, world.rivers, list(techs)
    )


def test_end_to_end_areas_candidates_and_invariants(world):
    summary = _run(world, ("solar", "wind"))
    solar = summary.technologies["solar"]
    cells = pd.read_parquet(solar.cells)
    assert len(cells) == 24 and solar.n_cells == 24
    assert (cells["eligible_area_km2"] <= cells["cell_area_km2"] * (1 + 1e-6)).all()
    col0 = cells["col"].min()
    first_col = cells[cells["col"] == col0]
    assert (first_col["eligible_area_km2"] < 1e-9).all()
    assert (first_col["dominant_exclusion"] == "E5").all()
    assert solar.excluded_share_by_constraint["E5"] > 0.15
    col2 = cells[cells["col"] == col0 + 2]  # the protected polygon covers it entirely
    assert (col2["eligible_area_km2"] < 1e-6).all() and (col2["dominant_exclusion"] == "E1").all()
    riverside = cells[cells["col"] == col0 + 4]  # a river inside it: only part of the pixels is excluded, not whole pixels
    assert (riverside["eligible_area_km2"] > 0).all() and (riverside["excluded_area_km2_E3"] > 0).all()
    assert (riverside["eligible_area_km2"] < riverside["cell_area_km2"]).all()
    cands = pd.read_parquet(solar.candidates)
    assert solar.n_candidates == len(cands) == int((cells["eligible_area_km2"] >= 0.1).sum())
    assert {"dist_grid_km", "dist_road_km", "pvout_kwh_kwp_day", "dist_grid_capped_share"} <= set(cands.columns)
    coarse = pd.read_parquet(solar.cells_0p1deg)
    assert coarse["eligible_area_km2"].sum() == pytest.approx(cells["eligible_area_km2"].sum())
    assert coarse["cell_area_km2"].sum() == pytest.approx(cells["cell_area_km2"].sum())
    for path in solar.rasters.values():
        assert Path(path).exists()
    wind = pd.read_parquet(summary.technologies["wind"].candidates)
    assert {"weibull_a_100m", "weibull_k_200m", "air_density_150m"} <= set(wind.columns)
    assert "pvout_kwh_kwp_day" not in wind.columns


def test_missing_required_resource_layer_is_an_error_not_free_land(world):
    world.siting.layers.pop("pvout_kwh_kwp_day")
    with pytest.raises(LandEligibilityError, match="pvout"):
        _run(world)


def _layers(shape, **over):
    base = {
        "country_mask": np.ones(shape, bool),
        "pixel_area_km2": np.ones(shape),
        "slope_deg": np.zeros(shape),
        "population_count": np.zeros(shape),
        "land_cover": np.full(shape, 30.0),
        "lakes_fraction": np.zeros(shape),
        "protected_fraction": {("ia",): np.zeros(shape)},
        "riparian_fraction": {0.5: np.zeros(shape)},
        "required_valid": {},
    }
    base.update(over)
    return EligibilityLayers(**base)


def test_pixel_without_a_population_value_is_not_eligible():
    layers = _layers((2, 2), population_count=np.array([[0.0, np.nan], [0.0, 0.0]]))
    eligible, _ = eligible_fraction(layers, ParameterSet(10.0, 100.0, 0.5, 0.1, (10,), ("ia",)))
    assert eligible.tolist() == [[1.0, 0.0], [1.0, 1.0]]


def test_population_density_uses_count_over_geodesic_area():
    layers = _layers((1, 2), pixel_area_km2=np.array([[1.0, 2.0]]), population_count=np.array([[150.0, 150.0]]))
    _, excl = eligible_fraction(layers, ParameterSet(10.0, 100.0, 0.5, 0.1, (10,), ("ia",)))
    assert excl["E6"].tolist() == [[1.0, 0.0]]  # 150/km2 excluded, 75/km2 kept


def test_riparian_share_is_interpolated_between_prepared_setbacks_and_never_extrapolated():
    shape = (1, 1)
    layers = _layers(shape, riparian_fraction={0.25: np.full(shape, 0.2), 1.0: np.full(shape, 0.8)})
    _, mid = eligible_fraction(layers, ParameterSet(10.0, 100.0, 0.625, 0.1, (10,), ("ia",)))
    assert mid["E3"][0, 0] == pytest.approx(0.5)
    with pytest.raises(MissingExclusionLayerError):
        eligible_fraction(layers, ParameterSet(10.0, 100.0, 2.0, 0.1, (10,), ("ia",)))
