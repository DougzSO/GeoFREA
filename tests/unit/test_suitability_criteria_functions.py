"""Unit tests for geofrea.suitability_criteria.criteria_functions.

Small synthetic single-band rasters written to tmp_path. The pixel-exact
match against the frozen legacy baseline is a separate regression test
(tests/regression/test_suitability_criteria_regression.py); these check
the formula shape, nodata handling, and parameter plumbing.
"""

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from geofrea.core.constants import NODATA_FLOAT
from geofrea.core.schemas import CriteriaParams
from geofrea.suitability_criteria.criteria_functions import (
    compute_biomass_resource,
    compute_grid_suitability,
    compute_lakes_exclusion,
    compute_lc_biomass,
    compute_linear_proximity_suitability,
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
from tests.unit.test_schemas import VALID_CRITERIA


def _criteria(**overrides) -> CriteriaParams:
    import copy

    data = copy.deepcopy(VALID_CRITERIA)
    for key, value in overrides.items():
        data[key]["value"] = value
    return CriteriaParams.model_validate(data)


def _write_raster(path, array, nodata=NODATA_FLOAT):
    array = np.asarray(array, dtype=np.float32)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=array.shape[0],
        width=array.shape[1],
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(-9.5, 42.15, 0.01, 0.01),
        nodata=nodata,
    ) as dst:
        dst.write(array, 1)
    return path


# ─── solar / wind resource ────────────────────────────────────────────


@pytest.mark.unit
def test_compute_solar_resource_normalizes_positive_pixels(tmp_path):
    p = _write_raster(tmp_path / "solar.tif", [[1.0, 2.0, 3.0], [4.0, 5.0, NODATA_FLOAT]])
    score, _t, crs = compute_solar_resource(str(p), _criteria())
    assert crs == "EPSG:4326"
    assert score[1, 2] == NODATA_FLOAT
    finite = score[score != NODATA_FLOAT]
    assert finite.min() >= 0.0 and finite.max() <= 1.0
    assert score[0, 0] < score[1, 1]  # monotone with irradiance


@pytest.mark.unit
def test_compute_solar_resource_excludes_non_positive(tmp_path):
    p = _write_raster(tmp_path / "solar.tif", [[0.0, -1.0, 5.0, 10.0]])
    score, _t, _c = compute_solar_resource(str(p), _criteria())
    assert score[0, 0] == NODATA_FLOAT  # 0 excluded (data > 0)
    assert score[0, 1] == NODATA_FLOAT  # negative excluded
    assert score[0, 2] != NODATA_FLOAT


@pytest.mark.unit
def test_compute_solar_pvout_weight_scales_scores(tmp_path):
    p = _write_raster(tmp_path / "solar.tif", [[1.0, 5.0, 10.0, 20.0]])
    base, _t, _c = compute_solar_resource(str(p), _criteria())
    weighted, _t, _c = compute_solar_resource(str(p), _criteria(solar_pvout_weight=0.5))
    valid = base != NODATA_FLOAT
    assert np.allclose(weighted[valid], base[valid] * 0.5)


@pytest.mark.unit
def test_compute_solar_pvout_weight_preserves_nodata(tmp_path):
    # 0.0 is excluded (data > 0) -> that pixel's score is NODATA_FLOAT.
    # The legacy would have multiplied it (isfinite(-9999) is True);
    # GeoFREA guards it out (METHODOLOGY_REVISION 2026-09-10).
    p = _write_raster(tmp_path / "solar.tif", [[0.0, 5.0, 10.0, 20.0]])
    weighted, _t, _c = compute_solar_resource(str(p), _criteria(solar_pvout_weight=0.5))
    assert weighted[0, 0] == NODATA_FLOAT


@pytest.mark.unit
def test_compute_wind_resource_matches_normalize_percentile_path(tmp_path):
    p = _write_raster(tmp_path / "wind.tif", [[2.0, 4.0, 6.0, 8.0, 10.0]])
    score, _t, _c = compute_wind_resource(str(p), _criteria())
    finite = score[score != NODATA_FLOAT]
    assert finite.min() == pytest.approx(0.0)
    assert finite.max() == pytest.approx(1.0)


# ─── linear proximity (roads / grid) ─────────────────────────────────


@pytest.mark.unit
def test_linear_proximity_decays_then_normalizes(tmp_path):
    # distances 0..20 km, max_dist 15 -> raw clips to 0 beyond 15
    dists = np.linspace(0, 20, 21).reshape(1, 21)
    p = _write_raster(tmp_path / "roads.tif", dists)
    score, _t, _c = compute_linear_proximity_suitability(str(p), 15.0, 5.0, 95.0)
    assert score[0, 0] == pytest.approx(1.0)  # nearest -> best
    assert score[0, -1] == pytest.approx(0.0)  # far -> worst
    assert np.all(np.diff(score[0]) <= 1e-6)  # monotone non-increasing


@pytest.mark.unit
def test_linear_proximity_preserves_nodata(tmp_path):
    p = _write_raster(tmp_path / "roads.tif", [[0.0, 5.0, NODATA_FLOAT, 10.0]])
    score, _t, _c = compute_linear_proximity_suitability(str(p), 15.0, 5.0, 95.0)
    assert score[0, 2] == NODATA_FLOAT


@pytest.mark.unit
def test_compute_road_suitability_reads_params_from_criteria(tmp_path):
    dists = np.array([[0.0, 5.0, 10.0, 30.0]])
    p = _write_raster(tmp_path / "roads.tif", dists)
    tight, _t, _c = compute_road_suitability(str(p), _criteria(road_max_dist_km=5.0))
    wide, _t, _c = compute_road_suitability(str(p), _criteria(road_max_dist_km=15.0))
    # with max_dist 5, pixel at 10km clips to raw 0; with 15 it is raw 1/3
    assert tight[0, 2] != wide[0, 2]


# ─── river suitability ───────────────────────────────────────────────


@pytest.mark.unit
def test_compute_river_biomass_linear_access(tmp_path):
    dists = np.array([[0.0, 15.0, 30.0, 45.0]])
    p = _write_raster(tmp_path / "rivers.tif", dists)
    score, _t, _c = compute_river_suitability(str(p), _criteria(), "biomass")
    assert score[0, 0] == pytest.approx(1.0)
    assert score[0, 1] == pytest.approx(0.5)
    assert score[0, 2] == pytest.approx(0.0)
    assert score[0, 3] == pytest.approx(0.0)  # clipped, not negative


@pytest.mark.unit
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_compute_river_setback_is_binary(tmp_path, tech):
    dists = np.array([[0.1, 0.4, 0.5, 2.0]])
    p = _write_raster(tmp_path / "rivers.tif", dists)
    score, _t, _c = compute_river_suitability(str(p), _criteria(), tech)
    assert score[0, 0] == 0.0
    assert score[0, 1] == 0.0
    assert score[0, 2] == 1.0
    assert score[0, 3] == 1.0


@pytest.mark.unit
def test_compute_river_suitability_rejects_unknown_tech(tmp_path):
    p = _write_raster(tmp_path / "rivers.tif", [[1.0]])
    with pytest.raises(ValueError, match="tech must be"):
        compute_river_suitability(str(p), _criteria(), "hydro")


# ─── slope_degrees / terrain_score ───────────────────────────────────


@pytest.mark.unit
def test_compute_slope_degrees_is_passthrough(tmp_path):
    p = _write_raster(tmp_path / "slope.tif", [[0.0, 3.5, 12.0, NODATA_FLOAT], [-1.0, 7.0, 2.0, 9.0]])
    out, _t, _c = compute_slope_degrees(str(p))
    assert out[0, 1] == pytest.approx(3.5)
    assert out[0, 2] == pytest.approx(12.0)
    assert out[0, 3] == NODATA_FLOAT
    assert out[1, 0] == NODATA_FLOAT  # negative slope invalid


@pytest.mark.unit
def test_compute_terrain_score_slope_component_uses_threshold(tmp_path):
    # elev flat -> TRI score is 1 everywhere; combined = 0.6*slope_score + 0.4*1
    slope = _write_raster(tmp_path / "slope.tif", [[0.0, 5.0, 10.0, 20.0]])
    elev = _write_raster(tmp_path / "elev.tif", [[100.0, 100.0, 100.0, 100.0]])
    score, _t, _c = compute_terrain_score(str(slope), str(elev), _criteria(), slope_threshold_deg=10.0)
    # slope_score at 0 deg = 1 -> combined 1.0 ; at 10 deg = 0 -> combined 0.4
    assert score[0, 0] == pytest.approx(1.0)
    assert score[0, 2] == pytest.approx(0.4)
    assert score[0, 3] == pytest.approx(0.4)  # clipped, slope_score floors at 0


@pytest.mark.unit
def test_compute_terrain_score_per_country_threshold_changes_result(tmp_path):
    slope = _write_raster(tmp_path / "slope.tif", [[6.0, 6.0, 6.0]])
    elev = _write_raster(tmp_path / "elev.tif", [[10.0, 20.0, 15.0]])
    prt, _t, _c = compute_terrain_score(str(slope), str(elev), _criteria(), 10.0)
    bra, _t, _c = compute_terrain_score(str(slope), str(elev), _criteria(), 12.0)
    assert not np.allclose(prt[prt != NODATA_FLOAT], bra[bra != NODATA_FLOAT])


@pytest.mark.unit
def test_compute_terrain_score_without_elevation_is_slope_only(tmp_path):
    slope = _write_raster(tmp_path / "slope.tif", [[0.0, 5.0, 10.0]])
    score, _t, _c = compute_terrain_score(str(slope), None, _criteria(), 10.0)
    assert score[0, 0] == pytest.approx(1.0)
    assert score[0, 1] == pytest.approx(0.5)
    assert score[0, 2] == pytest.approx(0.0)


@pytest.mark.unit
def test_compute_terrain_score_nan_neighbour_falls_back_to_slope_only_not_nan(tmp_path):
    # Reproduces docs/DECISIONS.md 2026-09-11 ("TRI contamination guard"):
    # a residual literal NaN in the elevation input (e.g. from
    # grid_alignment's own reprojection, see
    # test_reproject_to_grid_sanitizes_literal_nan_despite_finite_declared_nodata)
    # must not leak into terrain_score as NaN, and must not silently
    # average over the NaN neighbour either.
    #
    #   elev (3x3):        (2,2) is the only invalid cell.
    #   100 100 100
    #   100 100 100
    #   100 100 NaN
    #
    # (1,1) is valid itself but diagonally adjacent to the NaN cell -> a
    # 1+ invalid-neighbour case: decision (b), TRI must come out nodata
    # there, not a partial/skewed number, so terrain_score falls back to
    # slope-only. (0,0) is far from the NaN cell (Chebyshev distance 2)
    # and must be completely unaffected -- still gets the full
    # slope+TRI combination.
    elev_arr = np.array(
        [[100.0, 100.0, 100.0], [100.0, 100.0, 100.0], [100.0, 100.0, np.nan]],
        dtype=np.float32,
    )
    slope = _write_raster(tmp_path / "slope.tif", np.full((3, 3), 5.0))
    elev = _write_raster(tmp_path / "elev.tif", elev_arr)

    score, _t, _c = compute_terrain_score(str(slope), str(elev), _criteria(), slope_threshold_deg=10.0)

    assert not np.isnan(score).any(), "a NaN neighbour must never leak into terrain_score as NaN"

    slope_score = 1.0 - 5.0 / 10.0  # 0.5, uniform slope input
    w_slope, w_tri = 0.6, 0.4  # matches this fixture's own weights (see criteria() default)

    # (0,0): unaffected by the NaN cell -> flat elevation there -> TRI
    # score 1.0 -> full slope+TRI combination.
    assert score[0, 0] == pytest.approx(w_slope * slope_score + w_tri * 1.0)

    # (1,1): valid elevation, but a NaN neighbour contaminates its TRI
    # stencil -> TRI must come out nodata, not a wrong number -> falls
    # back to slope-only, exactly like the "no elevation at all" path.
    assert score[1, 1] == pytest.approx(slope_score)

    # (2,2): its OWN elevation is the NaN cell -> unaffected by this fix,
    # pre-existing center-exclusion behavior -> slope-only too.
    assert score[2, 2] == pytest.approx(slope_score)


# ─── lc_biomass / biomass_resource ───────────────────────────────────


class _LS:
    def __init__(self, biomass):
        self.biomass = biomass


@pytest.mark.unit
def test_compute_lc_biomass_looks_up_table(tmp_path):
    p = _write_raster(tmp_path / "lc.tif", [[30, 40, 50, 30]], nodata=0)
    table = {30: _LS(0.9), 40: _LS(0.9), 50: _LS(0.0)}
    score, _t, _c = compute_lc_biomass(str(p), table)
    assert score[0, 0] == pytest.approx(0.9)
    assert score[0, 2] == pytest.approx(0.0)


@pytest.mark.unit
def test_compute_lc_biomass_unknown_class_scores_zero(tmp_path):
    p = _write_raster(tmp_path / "lc.tif", [[30, 99]], nodata=0)
    score, _t, _c = compute_lc_biomass(str(p), {30: _LS(0.9)})
    assert score[0, 1] == pytest.approx(0.0)


@pytest.mark.unit
def test_compute_lc_biomass_excludes_255_and_nodata(tmp_path):
    p = _write_raster(tmp_path / "lc.tif", [[30, 255, 0]], nodata=0)
    score, _t, _c = compute_lc_biomass(str(p), {30: _LS(0.9)})
    assert score[0, 1] == NODATA_FLOAT
    assert score[0, 2] == NODATA_FLOAT


@pytest.mark.unit
def test_compute_biomass_resource_normalizes_yields(tmp_path):
    p = _write_raster(
        tmp_path / "lc.tif", [[30, 30, 40, 40, 50, 50, 30, 40]], nodata=0
    )
    score, _t, _c = compute_biomass_resource(
        str(p), {30: 5.0, 40: 8.0}, _criteria(biomass_smooth_sigma=0.0)
    )
    valid = score[score != NODATA_FLOAT]
    assert valid.min() == pytest.approx(0.0)
    assert valid.max() == pytest.approx(1.0)
    # class 50 has no listed yield -> 0.0 -> lowest score
    assert score[0, 4] <= score[0, 0]


# ─── grid_suitability / lakes_exclusion ──────────────────────────────


@pytest.mark.unit
def test_compute_grid_suitability_uses_grid_max_dist(tmp_path):
    dists = np.array([[0.0, 10.0, 20.0, 40.0]])
    p = _write_raster(tmp_path / "grid.tif", dists)
    score, _t, _c = compute_grid_suitability(str(p), _criteria(grid_max_dist_km=20.0))
    assert score[0, 0] == pytest.approx(1.0)
    assert score[0, 3] == pytest.approx(0.0)
    assert np.all(np.diff(score[0]) <= 1e-6)


@pytest.mark.unit
def test_compute_lakes_exclusion_is_binary_mask(tmp_path):
    arr = np.array([[0, 1, 0, 255, 1]], dtype=np.uint8)
    with rasterio.open(
        tmp_path / "lakes.tif", "w", driver="GTiff", height=1, width=5, count=1,
        dtype="uint8", crs="EPSG:4326", transform=from_origin(-9.5, 42.15, 0.01, 0.01), nodata=255,
    ) as dst:
        dst.write(arr, 1)
    score, _t, _c = compute_lakes_exclusion(str(tmp_path / "lakes.tif"))
    assert score[0, 0] == 1.0  # land
    assert score[0, 1] == 0.0  # lake
    assert score[0, 2] == 1.0  # land
    assert score[0, 3] == NODATA_FLOAT  # 255 = outside country
    assert score[0, 4] == 0.0  # lake


# ─── population suitability ───────────────────────────────────────────


@pytest.mark.unit
def test_compute_population_suitability_log_penalty_is_monotone_decreasing(tmp_path):
    p = _write_raster(tmp_path / "pop.tif", [[0.0, 50.0, 200.0, 1000.0]])
    score, _t, crs = compute_population_suitability(str(p), _criteria(pop_density_threshold=200.0))
    assert crs == "EPSG:4326"
    assert score[0, 0] == pytest.approx(1.0)  # empty land = best
    assert score[0, 1] > score[0, 2]  # denser = worse
    assert score[0, 2] == pytest.approx(0.0, abs=1e-6)  # at threshold
    assert score[0, 3] == pytest.approx(0.0, abs=1e-6)  # clipped past threshold


@pytest.mark.unit
def test_compute_population_suitability_nodata_and_negative_excluded(tmp_path):
    p = _write_raster(tmp_path / "pop.tif", [[10.0, -1.0, NODATA_FLOAT]])
    score, _t, _c = compute_population_suitability(str(p), _criteria(pop_density_threshold=300.0))
    assert score[0, 0] != NODATA_FLOAT
    assert score[0, 1] == NODATA_FLOAT  # negative
    assert score[0, 2] == NODATA_FLOAT  # raster nodata


@pytest.mark.unit
def test_compute_population_suitability_threshold_changes_scores(tmp_path):
    p = _write_raster(tmp_path / "pop.tif", [[100.0]])
    lo, _t, _c = compute_population_suitability(str(p), _criteria(pop_density_threshold=200.0))
    hi, _t, _c = compute_population_suitability(str(p), _criteria(pop_density_threshold=300.0))
    assert hi[0, 0] > lo[0, 0]  # a higher threshold is more permissive at fixed density


# ─── seismic suitability ─────────────────────────────────────────────


@pytest.mark.unit
def test_compute_seismic_suitability_inverts_hazard(tmp_path):
    p = _write_raster(tmp_path / "seismic.tif", [[0.1, 0.2, 0.3, 0.4, 0.5]])
    score, _t, _c = compute_seismic_suitability(str(p), _criteria())
    valid = score[score != NODATA_FLOAT]
    assert valid.min() >= 0.0 and valid.max() <= 1.0
    assert score[0, 0] > score[0, 4]  # low hazard -> high suitability


@pytest.mark.unit
def test_compute_seismic_suitability_excludes_negative_and_nodata(tmp_path):
    p = _write_raster(tmp_path / "seismic.tif", [[-1.0, 0.0, 0.5, NODATA_FLOAT]])
    score, _t, _c = compute_seismic_suitability(str(p), _criteria())
    assert score[0, 0] == NODATA_FLOAT
    assert score[0, 3] == NODATA_FLOAT


# ─── protected areas (binary WDPA mask) ──────────────────────────────


def _mainland_gdf():
    import geopandas as gpd
    from shapely.geometry import Polygon

    # covers the raster written by _write_raster (origin -9.5, 42.15, 0.01)
    return gpd.GeoDataFrame(
        {"geometry": [Polygon([(-9.5, 42.05), (-9.4, 42.05), (-9.4, 42.15), (-9.5, 42.15)])]},
        crs="EPSG:4326",
    )


def _write_wdpa(path, polygons_with_cat):
    import geopandas as gpd

    gpd.GeoDataFrame(
        {
            "IUCN_CAT": [c for _g, c in polygons_with_cat],
            "geometry": [g for g, _c in polygons_with_cat],
        },
        crs="EPSG:4326",
    ).to_file(path)
    return path


@pytest.mark.unit
def test_compute_protected_areas_no_wdpa_is_all_free(tmp_path):
    from rasterio.transform import from_origin

    score, _t, _c, source = compute_protected_areas(
        None, _mainland_gdf(), from_origin(-9.5, 42.15, 0.01, 0.01), 5, 4, "EPSG:4326", ["ia", "ib", "ii"]
    )
    assert source == "assumed_free"
    inside = score[score != NODATA_FLOAT]
    assert inside.size > 0
    assert np.array_equal(np.unique(inside), np.array([1.0], dtype=np.float32))


@pytest.mark.unit
def test_compute_protected_areas_binary_strict_vs_non_strict(tmp_path):
    from rasterio.transform import from_origin
    from shapely.geometry import Polygon

    strict = Polygon([(-9.5, 42.13), (-9.48, 42.13), (-9.48, 42.15), (-9.5, 42.15)])
    lax = Polygon([(-9.44, 42.05), (-9.40, 42.05), (-9.40, 42.09), (-9.44, 42.09)])
    wdpa = _write_wdpa(tmp_path / "wdpa.shp", [(strict, "Ia"), (lax, "V")])

    score, _t, _c, source = compute_protected_areas(
        wdpa, _mainland_gdf(), from_origin(-9.5, 42.15, 0.01, 0.01), 5, 4, "EPSG:4326", ["ia", "ib", "ii"]
    )
    assert source == "wdpa"
    inside = score[score != NODATA_FLOAT]
    assert set(np.unique(inside).tolist()) <= {0.0, 1.0}
    assert (score[:2, :2] == 0.0).any()  # strict polygon burned an exclusion
    assert (inside == 1.0).any()  # lax polygon + free land indistinguishable at 1.0


@pytest.mark.unit
def test_compute_protected_areas_directory_input_resolves_polygon_shp(tmp_path):
    from rasterio.transform import from_origin
    from shapely.geometry import Polygon

    d = tmp_path / "wdpa_dir" / "shp_0"
    d.mkdir(parents=True)
    poly = Polygon([(-9.5, 42.13), (-9.48, 42.13), (-9.48, 42.15), (-9.5, 42.15)])
    _write_wdpa(d / "WDPA_x_shp-polygons.shp", [(poly, "Ia")])

    score, _t, _c, source = compute_protected_areas(
        tmp_path / "wdpa_dir", _mainland_gdf(),
        from_origin(-9.5, 42.15, 0.01, 0.01), 5, 4, "EPSG:4326", ["ia", "ib", "ii"],
    )
    assert source == "wdpa"
    assert (score == 0.0).any()


@pytest.mark.unit
def test_compute_protected_areas_empty_directory_is_assumed_free(tmp_path):
    # A directory that exists but holds NO shapefile is a genuine absence
    # (same as a missing token) -> assumed_free, NOT an error.
    from rasterio.transform import from_origin

    d = tmp_path / "wdpa_empty"
    d.mkdir()

    score, _t, _c, source = compute_protected_areas(
        d, _mainland_gdf(), from_origin(-9.5, 42.15, 0.01, 0.01), 5, 4, "EPSG:4326", ["ia", "ib", "ii"]
    )
    assert source == "assumed_free"
    assert np.array_equal(np.unique(score[score != NODATA_FLOAT]), np.array([1.0], dtype=np.float32))


@pytest.mark.unit
def test_compute_protected_areas_corrupted_shapefile_raises_not_assumed_free(tmp_path):
    # A WDPA file that IS present but is truncated/unreadable is a
    # data-integrity error — fail loud, do NOT fall back to assumed_free
    # (DECISIONS.md 2026-09-11). Distinct from the missing-file case above.
    from rasterio.transform import from_origin

    bad = tmp_path / "WDPA_broken_shp-polygons.shp"
    bad.write_bytes(b"\x00\x01\x02 this is not a valid ESRI shapefile \xff\xfe" * 4)

    with pytest.raises(RuntimeError) as excinfo:
        compute_protected_areas(
            bad, _mainland_gdf(),
            from_origin(-9.5, 42.15, 0.01, 0.01), 5, 4, "EPSG:4326", ["ia", "ib", "ii"],
        )

    msg = str(excinfo.value)
    assert "protected_areas" in msg
    assert "present but could not be read" in msg
    assert bad.name in msg  # names the offending file for diagnosis


@pytest.mark.unit
def test_compute_protected_areas_corrupted_shapefile_in_directory_also_raises(tmp_path):
    from rasterio.transform import from_origin

    d = tmp_path / "wdpa_dir" / "shp_0"
    d.mkdir(parents=True)
    (d / "WDPA_x_shp-polygons.shp").write_bytes(b"truncated garbage, not a shapefile")

    with pytest.raises(RuntimeError, match="could not be read"):
        compute_protected_areas(
            tmp_path / "wdpa_dir", _mainland_gdf(),
            from_origin(-9.5, 42.15, 0.01, 0.01), 5, 4, "EPSG:4326", ["ia", "ib", "ii"],
        )
