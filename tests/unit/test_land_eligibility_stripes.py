"""COMMAND 91: F3 by stripes of rows gives, bit for bit, what the whole grid gave.

The oracle is the whole-grid computation of before, still the one F7b uses: `prepare_shared_layers` + `technology_layers` + `eligible_fraction` +
`apply_minimum_area` + `aggregate_to_cells` on whole arrays. The minimum-area rules of Group 6 (the pixel floor and the clusters of 8-connected pixels, labelled on the
whole grid) run on the world with clusters that cross the stripes. The world is random (land-cover and slope samples, population with gaps, resources with gaps, a country that
does not fill its grid, partial protected areas, rivers, capped-distance flags), so that every exclusion, the validity masks and the cell means do work.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString, Polygon, box

from geofrea.config_models.land_availability import ELEVATION_COLUMN, load_land_availability
from geofrea.core.constants import NODATA_FLOAT
from geofrea.land_eligibility import pipeline
from geofrea.land_eligibility.cells import (
    aggregate_to_cells,
    eligible_fraction_file,
    pixel_row_area_km2,
)
from geofrea.land_eligibility.eligibility import eligible_fraction, slope_steep_shares
from geofrea.land_eligibility.min_area import apply_minimum_area
from geofrea.land_eligibility.scenarios import scenario_sets
from geofrea.land_eligibility.windows import (
    ClassCountRows,
    NpyRows,
    NpyWriter,
    RasterRows,
    prepare_slope_shares,
    resolve_stripe_pixels,
)
from geofrea.siting_layers.physical_layers import SitingLayersResult

EXPERIMENTS = Path(__file__).resolve().parents[2] / "config" / "experiments.yaml"
H, W = 60, 40  # 12 x 8 cells of 0.05 degree (5 x 5 pixels)
LON0, LAT0 = 10.0, 5.0
TRANSFORM = from_origin(LON0, LAT0, 0.01, 0.01)
CLASSES = (10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100)
SPP = 144


def _write(path, data, dtype="float32", nodata=-9999.0, count=1, tags=None):
    with rasterio.open(
        path, "w", driver="GTiff", height=H, width=W, count=count, dtype=dtype, crs="EPSG:4326", transform=TRANSFORM, nodata=nodata
    ) as dst:
        if count == 1:
            dst.write(data.astype(dtype), 1)
        else:
            dst.write(data.astype(dtype))
        if tags:
            dst.update_tags(**tags)
    return path


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path / "data"))
    rng = np.random.default_rng(91)
    base = tmp_path / "rasters"
    base.mkdir()
    # land-cover samples: each pixel splits SPP samples over the classes, some pixels have none (open sea) and some are nodata
    probs = rng.dirichlet(np.ones(len(CLASSES)) * 0.4, size=(H, W))
    counts = np.floor(probs * SPP).astype("uint16").transpose(2, 0, 1)
    counts[:, rng.uniform(size=(H, W)) < 0.03] = 0
    counts[:, :6, :6] = 65535  # outside the data
    # slope samples in 1 degree bins
    slope_bin = np.clip(rng.gamma(2.0, 3.0, size=(H, W)).astype(int), 0, 40)
    sc = np.zeros((41, H, W), dtype="uint16")
    for b in range(41):
        sc[b][slope_bin == b] = SPP - 1
    sc[np.clip(slope_bin + 1, 0, 40), np.arange(H)[:, None], np.arange(W)[None, :]] += 1  # a second bin in every pixel
    sc[:, :4, :4] = 65535
    population = rng.gamma(0.4, 80.0, size=(H, W))
    population[rng.uniform(size=(H, W)) < 0.04] = -9999.0
    smod_classes = np.array([10, 11, 12, 13, 21, 22, 23, 30])
    settlements = smod_classes[rng.choice(len(smod_classes), size=(H, W), p=[0.05, 0.2, 0.3, 0.2, 0.1, 0.07, 0.05, 0.03])].astype("uint8")
    settlements[rng.uniform(size=(H, W)) < 0.02] = 255  # a pixel with no class is invalid, never free
    grid = np.full((H, W), 7.0)
    grid[-8:, -10:] = -9999.0  # the country does not fill its grid
    elevation = rng.uniform(0, 3600, size=(H, W))
    elevation[rng.uniform(size=(H, W)) < 0.02] = -9999.0
    flags = lambda p: (rng.uniform(size=(H, W)) < p).astype("uint8")
    grid_result = SimpleNamespace(
        elevation=_write(base / "elev.tif", elevation),
        population=_write(base / "pop.tif", population, "float64"),
        settlements=_write(base / "smod.tif", settlements, "uint8", 255),
        land_cover_counts=_write(base / "lcc.tif", counts, "uint16", 65535, len(CLASSES), {"worldcover_classes": ",".join(map(str, CLASSES)), "samples_per_pixel": str(SPP)}),
        slope_counts=_write(base / "sc.tif", sc, "uint16", 65535, 41),
        grid=_write(base / "grid.tif", grid),
        grid_distance_capped=_write(base / "gcap.tif", flags(0.3), "uint8", 255),
        poi_distance_capped=_write(base / "pcap.tif", flags(0.4), "uint8", 255),
        roads_distance_capped=_write(base / "rcap.tif", flags(0.2), "uint8", 255),
    )
    layers = {}
    for name, lo, hi in [("dist_grid_km", 0, 80), ("dist_sub_km", 0, 80), ("dist_road_km", 0, 30), ("pvout_kwh_kwp_day", 3, 6)]:
        layers[name] = rng.uniform(lo, hi, size=(H, W))
    for h in (100, 150, 200):
        layers.update(
            {
                f"weibull_a_{h}m": rng.uniform(4, 11, size=(H, W)),
                f"weibull_k_{h}m": rng.uniform(1.5, 2.8, size=(H, W)),
                f"air_density_{h}m": rng.uniform(1.0, 1.3, size=(H, W)),
            }
        )
    for v in layers.values():
        v[rng.uniform(size=(H, W)) < 0.03] = -9999.0  # a resource gap makes the pixel invalid
    siting = SitingLayersResult(country_code="ZZZ", layers={n: _write(base / f"{n}.tif", v) for n, v in layers.items()})
    country = gpd.GeoDataFrame(geometry=[box(LON0, LAT0 - 0.6, LON0 + 0.4, LAT0)], crs="EPSG:4326")
    protected = gpd.GeoDataFrame(
        {"IUCN_CAT": ["II", "IV", "Not Reported"]},
        geometry=[
            Polygon([(LON0 + 0.07, LAT0 - 0.05), (LON0 + 0.2, LAT0 - 0.12), (LON0 + 0.13, LAT0 - 0.3)]),
            box(LON0 + 0.25, LAT0 - 0.5, LON0 + 0.38, LAT0 - 0.38),
            box(LON0 + 0.01, LAT0 - 0.55, LON0 + 0.1, LAT0 - 0.41),
        ],
        crs="EPSG:4326",
    )
    protected.to_file(tmp_path / "wdpa.gpkg", driver="GPKG")
    rivers = gpd.GeoDataFrame(
        {"DIS_AV_CMS": [60.0, 2.0, 400.0]},
        geometry=[
            LineString([(LON0 + 0.05, LAT0), (LON0 + 0.17, LAT0 - 0.31), (LON0 + 0.3, LAT0 - 0.6)]),
            LineString([(LON0, LAT0 - 0.4), (LON0 + 0.4, LAT0 - 0.33)]),
            LineString([(LON0 + 0.33, LAT0), (LON0 + 0.31, LAT0 - 0.6)]),
        ],
        crs="EPSG:4326",
    )
    rivers.to_file(tmp_path / "rivers.gpkg", driver="GPKG")
    lakes = gpd.GeoDataFrame(geometry=[box(LON0 + 0.2, LAT0 - 0.2, LON0 + 0.27, LAT0 - 0.24)], crs="EPSG:4326")
    lakes.to_file(tmp_path / "lakes.gpkg", driver="GPKG")
    admin1 = gpd.GeoDataFrame(
        {"GID_1": ["ZZZ.1_1", "ZZZ.2_1"], "NAME_1": ["West", "East"]},
        geometry=[box(LON0, LAT0 - 0.6, LON0 + 0.17, LAT0), box(LON0 + 0.17, LAT0 - 0.6, LON0 + 0.4, LAT0)],
        crs="EPSG:4326",
    )
    admin1.to_file(tmp_path / "admin1.gpkg", driver="GPKG")
    return SimpleNamespace(
        grid_result=grid_result,
        siting=siting,
        country=country,
        protected=tmp_path / "wdpa.gpkg",
        rivers=tmp_path / "rivers.gpkg",
        lakes=tmp_path / "lakes.gpkg",
        admin1=tmp_path / "admin1.gpkg",
        tmp=tmp_path,
    )


# the area of the reference project per scenario (km2, P_ref / PD of parameters.json): about 2.5 and 9 pixels of 1.2 km2, so that the cluster floor bites
PROJECT_AREA = {
    "solar": {"restrictive": 3.0, "central": 2.0, "permissive": 1.0},
    "wind": {"restrictive": 9.0, "central": 5.0, "permissive": 3.0},
}


def _build(world, stripe_pixels, techs=("solar", "wind")):
    return pipeline.build_eligibility(
        "ZZZ",
        EXPERIMENTS,
        world.grid_result,
        world.siting,
        world.country,
        world.protected,
        world.lakes,
        world.rivers,
        world.admin1,
        list(techs),
        stripe_pixels=stripe_pixels,
        project_area_km2=PROJECT_AREA,
    )


def _oracle(world, tech):
    """{scenario: (cells, eligible)} from the whole-grid functions."""
    la = load_land_availability(EXPERIMENTS)
    interim = world.tmp / "interim_oracle"
    interim.mkdir(exist_ok=True)
    sets = scenario_sets(la, tech, "ZZZ", PROJECT_AREA[tech])
    shared = pipeline.prepare_shared_layers(la, list(sets.values()), world.grid_result, world.country, world.protected, world.lakes, world.rivers, interim)
    layers, resources = pipeline.technology_layers(shared, tech, world.siting)
    elevation = pipeline._read(world.grid_result.elevation, "elevation", "float32")
    area_row = pixel_row_area_km2(shared.transform, shared.shape[0])
    out = {}
    for scenario, params in sets.items():
        eligible, excl = eligible_fraction(layers, params)
        eligible, _ = apply_minimum_area(eligible, area_row, params.min_pixel_fraction, params.min_cluster_km2)
        cells = aggregate_to_cells(
            shared.transform, shared.country_mask, eligible, excl, resources={**resources, ELEVATION_COLUMN: elevation}, flags=shared.flags
        )
        out[scenario] = (cells, eligible)
    return out


def _raster(path):
    with rasterio.open(path) as src:
        return src.read(1)


@pytest.mark.parametrize("stripe_pixels", [200, 1000, 1400, 10_000_000])
def test_the_stripe_engine_gives_the_whole_grid_result_bit_for_bit_for_any_stripe_height(world, stripe_pixels):
    """200 px is one row of cells a stripe, 1,000 px five (12 rows of cells: 5 + 5 + 2, a height that does not divide the raster), 1,400 px seven
    (7 + 5) and 10 M px the whole grid in one stripe."""
    summary = _build(world, stripe_pixels)
    for tech in ("solar", "wind"):
        for scenario, (cells, eligible) in _oracle(world, tech).items():
            got = pd.read_parquet(summary.technologies[tech].scenarios[scenario].cells)
            shared_columns = [c for c in cells.columns if c in got.columns]
            assert set(cells.columns) <= set(got.columns)
            pd.testing.assert_frame_equal(got[shared_columns], cells[shared_columns], check_exact=True, check_dtype=True)
            written = _raster(summary.technologies[tech].scenarios[scenario].cells.parent / eligible_fraction_file(tech, scenario))
            expect = np.where(np.isfinite(eligible), eligible, NODATA_FLOAT).astype("float32")
            np.testing.assert_array_equal(written, expect)


def test_every_artifact_is_identical_for_two_stripe_heights(world):
    """The tables of the two heights are equal as files' contents, the rasters pixel for pixel, and the summaries agree."""
    out = pipeline.artifacts_dir("ZZZ")
    first = _build(world, 200)
    snap = {p.name: (pd.read_parquet(p) if p.suffix == ".parquet" else _raster(p)) for p in sorted(out.iterdir()) if p.suffix in (".parquet", ".tif")}
    second = _build(world, 1400)
    assert set(snap) == {p.name for p in out.iterdir() if p.suffix in (".parquet", ".tif")}
    for name, ref in snap.items():
        now = pd.read_parquet(out / name) if name.endswith(".parquet") else _raster(out / name)
        if isinstance(ref, pd.DataFrame):
            pd.testing.assert_frame_equal(now, ref, check_exact=True)
        else:
            np.testing.assert_array_equal(now, ref)
    for tech in first.technologies:
        a, b = first.technologies[tech], second.technologies[tech]
        assert (a.n_cells, a.n_candidates, a.eligible_area_km2, a.invalid_pixel_share) == (b.n_cells, b.n_candidates, b.eligible_area_km2, b.invalid_pixel_share)
        assert a.excluded_share_by_constraint == b.excluded_share_by_constraint


def test_the_invalid_pixel_share_is_the_one_of_the_whole_grid(world):
    la = load_land_availability(EXPERIMENTS)
    interim = world.tmp / "interim_oracle2"
    interim.mkdir()
    central = scenario_sets(la, "wind", "ZZZ", PROJECT_AREA["wind"])["central"]
    shared = pipeline.prepare_shared_layers(la, [central], world.grid_result, world.country, world.protected, world.lakes, world.rivers, interim)
    layers, _ = pipeline.technology_layers(shared, "wind", world.siting)
    from geofrea.land_eligibility.eligibility import valid_pixels

    expect = 1.0 - np.count_nonzero(valid_pixels(layers)) / max(1, np.count_nonzero(shared.country_mask))
    got = _build(world, 1000, ("wind",)).technologies["wind"].invalid_pixel_share
    assert got == expect and 0 < got < 1


def test_the_window_readers_give_what_the_whole_readers_give(world):
    g = world.grid_result
    for path, name, dtype in [(g.population, "population", "float64"), (g.elevation, "elevation", "float32"), (g.grid, "grid", "float64")]:
        whole = pipeline._read(path, name, dtype)
        rows = RasterRows(path, name, dtype)
        got = np.concatenate([rows[r : r + 7] for r in range(0, H, 7)])  # 7 does not divide 60
        np.testing.assert_array_equal(got, whole)
        assert got.dtype == whole.dtype
    counts, classes, valid, spp = pipeline._read_class_counts(g.land_cover_counts)
    cr = ClassCountRows(g.land_cover_counts)
    assert (cr.classes, cr.samples_per_pixel) == (classes, spp)
    parts = [cr[r : r + 11] for r in range(0, H, 11)]
    np.testing.assert_array_equal(np.concatenate([p[0] for p in parts], axis=1), counts)
    np.testing.assert_array_equal(np.concatenate([p[1] for p in parts]), valid)


def test_the_slope_shares_by_window_equal_the_shares_of_the_whole_bins(world, tmp_path):
    g = world.grid_result
    bins, valid = pipeline._read_slope_counts(g.slope_counts)
    maxima = [8.0, 10.0, 12.5, 30.0]
    expect = slope_steep_shares(bins, maxima)
    from geofrea.land_eligibility import windows

    old = windows._PREPARE_WINDOW_PIXELS
    windows._PREPARE_WINDOW_PIXELS = 7 * W  # 7 rows a window: 60 rows are 8 windows and one of 4 rows
    try:
        shares = prepare_slope_shares(g.slope_counts, maxima, tmp_path / "slopes")
    finally:
        windows._PREPARE_WINDOW_PIXELS = old
    np.testing.assert_array_equal(shares.valid[0:H], valid)
    for t in maxima:
        np.testing.assert_array_equal(shares.steep[t][0:H], expect[t])
        assert shares.steep[t].dtype == np.float32


def test_a_npy_file_written_by_rows_is_read_by_rows(tmp_path):
    a = np.random.default_rng(1).random((13, 5)).astype("float32")
    w = NpyWriter(tmp_path / "a.npy", a.shape, np.float32)
    for r in range(0, 13, 4):
        w.write(a[r : r + 4])
    w.close()
    np.testing.assert_array_equal(np.load(tmp_path / "a.npy"), a)
    rows = NpyRows(tmp_path / "a.npy")
    np.testing.assert_array_equal(rows[3:9], a[3:9])
    np.testing.assert_array_equal(rows[0:13], a)
    short = NpyWriter(tmp_path / "b.npy", (4, 2), np.float32)
    short.write(np.zeros((3, 2), "float32"))
    with pytest.raises(ValueError, match="3 rows written of 4"):
        short.close()


def test_a_share_cache_made_as_one_npz_is_converted_and_not_rebuilt(tmp_path):
    path = tmp_path / "shares.npz"
    np.savez_compressed(path, _key=np.array("the key"), a=np.arange(6, dtype="float32").reshape(2, 3), b=np.ones((2, 3), "float32"))

    def build():
        raise AssertionError("the legacy file with the same key must be converted, not rebuilt")

    files = pipeline._fraction_files(path, "the key", build)
    assert set(files) == {"a", "b"}
    np.testing.assert_array_equal(np.load(files["a"]), np.arange(6, dtype="float32").reshape(2, 3))
    assert pipeline._fraction_files(path, "the key", build).keys() == files.keys()  # now read from the folder
    rebuilt = pipeline._fraction_files(path, "another key", lambda: {"c": np.zeros((2, 3), "float32")})
    assert set(rebuilt) == {"c"}  # the files of the old key are gone


def test_the_stripe_height_comes_from_the_argument_then_the_environment_then_the_default(monkeypatch):
    monkeypatch.delenv("GEOFREA_F3_STRIPE_PIXELS", raising=False)
    assert resolve_stripe_pixels() == 1_000_000
    monkeypatch.setenv("GEOFREA_F3_STRIPE_PIXELS", "250000")
    assert resolve_stripe_pixels() == 250_000 and resolve_stripe_pixels(5000) == 5000
    with pytest.raises(ValueError):
        resolve_stripe_pixels(0)


def test_a_failed_scenario_leaves_no_eligible_raster_behind(world, monkeypatch):
    def boom(*a, **k):
        raise pipeline.LandEligibilityError("forced")

    monkeypatch.setattr(pipeline, "_check_invariants", boom)
    with pytest.raises(pipeline.LandEligibilityError, match="forced"):
        _build(world, 1000, ("solar",))
    out = pipeline.artifacts_dir("ZZZ")
    assert not list(out.glob("eligible_fraction_*.tif")) and not list(out.glob("*.writing.tif"))


def test_the_corridor_shares_made_one_key_at_a_time_are_those_of_a_direct_call(world, tmp_path):
    from geofrea.land_eligibility.fractions import corridor_half_widths_m, river_corridor_fraction

    la = load_land_availability(EXPERIMENTS)
    rivers = gpd.read_file(world.rivers)
    corridors = sorted({pipeline.corridor_key(p) for p in scenario_sets(la, "wind", "ZZZ", PROJECT_AREA["wind"]).values()}, key=repr)
    assert len(corridors) == 3  # the width exponent differs in the three scenarios
    made = dict(pipeline._corridor_shares(rivers, la, corridors, TRANSFORM, (H, W)))
    for i, (exponent, exponent_range, steps) in enumerate(corridors):
        half = corridor_half_widths_m(rivers["DIS_AV_CMS"], la.riparian.width_coefficient, exponent, steps, exponent_range)
        np.testing.assert_array_equal(made[f"c{i}"], river_corridor_fraction(rivers, half, TRANSFORM, (H, W)))
    files = pipeline._fraction_files(tmp_path / "corr.npz", "k", lambda: pipeline._corridor_shares(rivers, la, corridors, TRANSFORM, (H, W)))
    assert set(files) == set(made)  # a builder that yields pairs is stored like a dict
    np.testing.assert_array_equal(np.load(files["c1"]), made["c1"])
    # a permissive corridor is nested in the central one and that in the restrictive one
    assert (made["c0"] <= made["c1"] + 1e-6).all() and (made["c1"] <= made["c2"] + 1e-6).all()


def test_a_cluster_that_crosses_several_stripes_is_one_cluster_and_the_stripe_heights_agree_on_it(world):
    """The labels come from the whole grid, so a cluster that crosses stripes has one area: the cell tables of three stripe heights are identical, and the
    minimum-area rules removed something in the scenarios that have them (the test would be empty otherwise)."""
    summaries = [_build(world, n) for n in (200, 1000, 10_000_000)]
    for tech in ("solar", "wind"):
        removed = {s: sum_removed(summaries[0].technologies[tech].scenarios[s]) for s in ("restrictive", "central", "permissive")}
        assert removed["permissive"] == 0.0
        assert removed["restrictive"] > 0.0
        for scenario in ("restrictive", "central", "permissive"):
            base = pd.read_parquet(summaries[0].technologies[tech].scenarios[scenario].cells)
            for other in summaries[1:]:
                pd.testing.assert_frame_equal(pd.read_parquet(other.technologies[tech].scenarios[scenario].cells), base, check_exact=True)


def sum_removed(scenario_summary):
    stats = scenario_summary.min_area
    return 0.0 if stats is None else stats["area_removed_by_pixel_floor_km2"] + stats["area_removed_by_cluster_floor_km2"]
