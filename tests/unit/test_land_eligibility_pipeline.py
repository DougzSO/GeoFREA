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
from geofrea.land_eligibility.pipeline import (
    LandEligibilityError,
    MissingRequiredLayerError,
    build_eligibility,
)
from geofrea.siting_layers.physical_layers import SitingLayersResult

EXPERIMENTS = Path(__file__).resolve().parents[2] / "config" / "experiments.yaml"
H, W = 20, 30  # pixels of 0.01 degree: 4 x 6 cells of 0.05 degree
LON0, LAT0 = 10.0, 5.0  # on the 0.05 degree lattice
TRANSFORM = from_origin(LON0, LAT0, 0.01, 0.01)


CLASSES = (10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100)
SPP = 144  # samples per pixel in the synthetic counts


def _counts(class_map: np.ndarray, shares: dict[int, float] | None = None) -> np.ndarray:
    """uint16 (class, row, col) counts: every pixel wholly of its class, or split by `shares` (class -> share) where given."""
    out = np.zeros((len(CLASSES),) + class_map.shape, dtype=np.uint16)
    for band, code in enumerate(CLASSES):
        out[band][class_map == code] = SPP
    return out


def _slope_counts(slope_map: np.ndarray) -> np.ndarray:
    """uint16 (bin, row, col) with every pixel's SPP samples at its slope, in 1 degree bins (last bin open ended)."""
    out = np.zeros((41,) + slope_map.shape, dtype=np.uint16)
    bins = np.clip(np.floor(slope_map).astype(int), 0, 40)
    for b in range(41):
        out[b][bins == b] = SPP
    return out


def _write_slope_counts(path: Path, counts: np.ndarray) -> Path:
    with rasterio.open(
        path, "w", driver="GTiff", height=H, width=W, count=41, dtype="uint16", crs="EPSG:4326", transform=TRANSFORM, nodata=65535
    ) as dst:
        dst.write(counts)
    return path


def _write_counts(path: Path, counts: np.ndarray) -> Path:
    with rasterio.open(
        path, "w", driver="GTiff", height=H, width=W, count=len(CLASSES), dtype="uint16", crs="EPSG:4326", transform=TRANSFORM,
        nodata=65535,
    ) as dst:
        dst.write(counts)
        dst.update_tags(worldcover_classes=",".join(map(str, CLASSES)), samples_per_pixel=str(SPP))
    return path


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
        land_cover_counts=_write_counts(base / "lcc.tif", _counts(land_cover)),
        slope_counts=_write_slope_counts(base / "sc.tif", _slope_counts(slope)),
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
    rivers = gpd.GeoDataFrame(
        {"DIS_AV_CMS": [50.0]}, geometry=[LineString([(LON0 + 0.205, LAT0), (LON0 + 0.205, LAT0 - 0.2)])], crs="EPSG:4326"
    )
    rivers.to_file(tmp_path / "rivers.gpkg", driver="GPKG")
    lakes = gpd.GeoDataFrame(geometry=[box(LON0 + 5, LAT0 + 5, LON0 + 5.1, LAT0 + 5.1)], crs="EPSG:4326")  # none inside the country
    lakes.to_file(tmp_path / "lakes.gpkg", driver="GPKG")
    return SimpleNamespace(
        grid_result=grid_result, siting=siting, country=country, protected=tmp_path / "wdpa.gpkg", rivers=tmp_path / "rivers.gpkg",
        lakes=tmp_path / "lakes.gpkg",
    )


def _run(world, techs=("solar",), **override):
    paths = {"protected": world.protected, "lakes": world.lakes, "rivers": world.rivers, **override}
    return build_eligibility(
        "ZZZ", EXPERIMENTS, world.grid_result, world.siting, world.country, paths["protected"], paths["lakes"], paths["rivers"],
        list(techs),
    )


def test_named_land_scenarios_are_ordered(world):
    """U-06 (V2): restrictive <= central <= permissive eligible area in every cell; one pair of tables per scenario, named by it."""
    summary = _run(world, ("solar", "wind"))
    for tech, tech_summary in summary.technologies.items():
        assert list(tech_summary.scenarios) == ["central", "restrictive", "permissive"]
        area = {}
        for scenario, s in tech_summary.scenarios.items():
            assert s.cells.name == f"cells_{tech}__{scenario}.parquet" and s.cells.exists()
            assert s.candidates.name == f"candidates_{tech}__{scenario}.parquet" and s.candidates.exists()
            area[scenario] = pd.read_parquet(s.cells).set_index("cell_id")["eligible_area_km2"].sort_index()
        assert (area["restrictive"] <= area["central"] + 1e-9).all()
        assert (area["central"] <= area["permissive"] + 1e-9).all()
        assert tech_summary.scenarios["central"].cells == tech_summary.cells
        # only ranges with status `sourced` move; the rest is declared as held at central
        varied = tech_summary.scenarios["restrictive"].varied
        assert "riparian_setback_km" in varied and "pop_density_max_per_km2" not in varied
        assert "pop_density_max_per_km2" in tech_summary.scenarios["restrictive"].held_central
    solar = summary.technologies["solar"].scenarios
    assert solar["restrictive"].eligible_area_km2 < solar["central"].eligible_area_km2 < solar["permissive"].eligible_area_km2


def test_candidate_stability_table_counts_the_scenarios_in_which_a_cell_is_a_candidate(world):
    summary = _run(world, ("solar",))
    solar = summary.technologies["solar"]
    stab = pd.read_parquet(solar.stability)
    assert solar.stability.name == "candidate_stability_solar.parquet"
    assert set(stab["n_scenarios"]) <= {1, 2, 3}
    assert (stab["share_of_scenarios"] == stab["n_scenarios"] / 3).all()
    central = set(pd.read_parquet(solar.candidates)["cell_id"])
    assert central == set(stab.loc[stab["candidate_central"], "cell_id"])
    # a candidate of the restrictive scenario is a candidate of central, and a candidate of central of the permissive one
    assert not (stab["candidate_restrictive"] & ~stab["candidate_central"]).any()
    assert not (stab["candidate_central"] & ~stab["candidate_permissive"]).any()


@pytest.mark.parametrize("layer", ["protected", "lakes", "rivers"])
@pytest.mark.parametrize("absent", ["none", "no_file"])
def test_missing_required_layer_raises(world, tmp_path, layer, absent):
    """M-F2b-05 (V17): an absent protected-area, lake or river layer raises a named error, never a zero share."""
    value = None if absent == "none" else tmp_path / "does_not_exist.gpkg"
    with pytest.raises(MissingRequiredLayerError, match=layer):
        _run(world, **{layer: value})


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
        "slope_counts": _slope_counts(np.zeros(shape)),
        "slope_valid": np.ones(shape, bool),
        "population_count": np.zeros(shape),
        "land_cover_counts": _counts(np.full(shape, 30)),
        "land_cover_classes": CLASSES,
        "land_cover_valid": np.ones(shape, bool),
        "samples_per_pixel": SPP,
        "lakes_fraction": np.zeros(shape),
        "protected_fraction": {("ia",): np.zeros(shape)},
        "riparian_fraction": {(0.0, 0.5): np.zeros(shape)},
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
    layers = _layers(shape, riparian_fraction={(0.0, 0.25): np.full(shape, 0.2), (0.0, 1.0): np.full(shape, 0.8)})
    _, mid = eligible_fraction(layers, ParameterSet(10.0, 100.0, 0.625, 0.1, (10,), ("ia",)))
    assert mid["E3"][0, 0] == pytest.approx(0.5)
    with pytest.raises(MissingExclusionLayerError):
        eligible_fraction(layers, ParameterSet(10.0, 100.0, 2.0, 0.1, (10,), ("ia",)))


def test_excluded_land_cover_is_the_share_of_samples_not_in_an_allowed_class():
    counts = _counts(np.full((1, 2), 30))
    counts[CLASSES.index(30), 0, 0] = 100  # pixel 0: 100 of 144 samples grassland, 44 forest
    counts[CLASSES.index(10), 0, 0] = 44
    layers = _layers((1, 2), land_cover_counts=counts)
    eligible, excl = eligible_fraction(layers, ParameterSet(10.0, 100.0, 0.5, 0.1, (10,), ("ia",)))
    assert excl["E5"][0, 0] == pytest.approx(44 / 144, abs=1e-6) and excl["E5"][0, 1] == 0.0
    assert eligible[0, 0] == pytest.approx(100 / 144, abs=1e-6)


def test_samples_of_no_class_count_as_not_allowed_and_a_pixel_without_any_sample_is_invalid():
    counts = _counts(np.full((1, 2), 30))
    counts[CLASSES.index(30), 0, 0] = 72  # the other half of the pixel is open sea (no class)
    counts[:, 0, 1] = 0
    layers = _layers((1, 2), land_cover_counts=counts, land_cover_valid=np.array([[True, False]]))
    eligible, _ = eligible_fraction(layers, ParameterSet(10.0, 100.0, 0.5, 0.1, (10,), ("ia",)))
    assert eligible.tolist() == [[0.5, 0.0]]


def test_an_excluded_class_missing_from_the_bands_is_an_error():
    with pytest.raises(MissingExclusionLayerError):
        eligible_fraction(_layers((1, 1)), ParameterSet(10.0, 100.0, 0.5, 0.1, (11,), ("ia",)))


def test_riparian_share_is_bilinear_in_setback_and_discharge_and_falls_with_discharge():
    shape = (1, 1)
    shares = {
        (0.0, 0.25): np.full(shape, 0.2), (0.0, 1.0): np.full(shape, 0.8),
        (10.0, 0.25): np.full(shape, 0.0), (10.0, 1.0): np.full(shape, 0.4),
    }
    layers = _layers(shape, riparian_fraction=shares)

    def e3(setback, q):
        params = ParameterSet(10.0, 100.0, setback, 0.1, (10,), ("ia",), riparian_min_discharge_m3s=q)
        return eligible_fraction(layers, params)[1]["E3"][0, 0]

    assert e3(1.0, 0.0) == pytest.approx(0.8) and e3(1.0, 10.0) == pytest.approx(0.4)
    assert e3(1.0, 5.0) == pytest.approx(0.6)  # halfway in discharge
    assert e3(0.625, 5.0) == pytest.approx(0.35)  # halfway in both: (0.1 + 0.6) / 2
    with pytest.raises(MissingExclusionLayerError):
        e3(1.0, 20.0)  # beyond the prepared discharges: never extrapolated


def test_steep_share_reads_whole_bins_and_a_proportion_of_the_bin_holding_the_threshold():
    counts = np.zeros((41, 1, 1), dtype=np.uint16)
    counts[5, 0, 0], counts[10, 0, 0], counts[12, 0, 0], counts[40, 0, 0] = 100, 100, 100, 100  # 400 samples
    layers = _layers((1, 1), slope_counts=counts)

    def e4(limit):
        return eligible_fraction(layers, ParameterSet(limit, 100.0, 0.5, 0.1, (10,), ("ia",)))[1]["E4"][0, 0]

    assert e4(10.0) == pytest.approx(0.75)  # bins 10-11, 12-13 and 40+ are above 10 degrees
    assert e4(10.5) == pytest.approx(0.625)  # half of the 10-11 bin counts
    assert e4(11.0) == pytest.approx(0.5)
    assert e4(40.0) == pytest.approx(0.25)  # only the open-ended bin
    with pytest.raises(MissingExclusionLayerError):
        e4(45.0)
