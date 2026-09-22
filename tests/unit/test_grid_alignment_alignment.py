"""Unit tests for geofrea.grid_alignment.alignment (the phase entry point)."""

from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString, Polygon

import geofrea.grid_alignment.alignment as alignment_module
from geofrea.core.config_loader import load_parameters
from geofrea.core.orchestrator import PhaseContext
from geofrea.grid_alignment.alignment import (
    _read_clipped_with_cache,
    _verify_alignment,
    run_grid_alignment_phase,
)
from geofrea.grid_alignment.reference_grid import build_reference_grid
from geofrea.grid_alignment.schemas import GridAlignmentInputs

REPO_ROOT = Path(__file__).resolve().parents[2]
PARAMETERS_JSON = REPO_ROOT / "config" / "parameters.json"

_ORIGIN_LON, _ORIGIN_LAT = -9.0, 39.0
_RES = 0.01


def _square(cx: float, cy: float, half_side: float) -> Polygon:
    return Polygon(
        [
            (cx - half_side, cy - half_side),
            (cx + half_side, cy - half_side),
            (cx + half_side, cy + half_side),
            (cx - half_side, cy + half_side),
        ]
    )


def _country_gdf(cx: float = _ORIGIN_LON + 0.2, cy: float = _ORIGIN_LAT - 0.2, half_side: float = 0.15) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(geometry=[_square(cx, cy, half_side)], crs="EPSG:4326")


def _context(tmp_path: Path, country_code: str = "PRT") -> PhaseContext:
    country_params = load_parameters(PARAMETERS_JSON).countries[country_code]
    return PhaseContext(
        country_code=country_code,
        country_params=country_params,
        outputs_dir=tmp_path,
        prior_results={},
    )


def _write_raster(path: Path, value: float, size: int = 60) -> None:
    transform = from_origin(_ORIGIN_LON, _ORIGIN_LAT, _RES, _RES)
    data = np.full((size, size), value, dtype="float32")
    with rasterio.open(
        path, "w", driver="GTiff", height=size, width=size, count=1,
        dtype="float32", crs="EPSG:4326", transform=transform, nodata=-9999.0,
    ) as dst:
        dst.write(data, 1)


# ─── _verify_alignment() (isolated) ───


@pytest.mark.unit
def test_verify_alignment_raises_runtime_error_on_dimension_mismatch(tmp_path):
    country_gdf = _country_gdf()
    grid = build_reference_grid(country_gdf, resolution_deg=_RES)

    bad_path = tmp_path / "bad.tif"
    transform = from_origin(_ORIGIN_LON, _ORIGIN_LAT, _RES, _RES)
    with rasterio.open(
        bad_path, "w", driver="GTiff", height=3, width=3, count=1,
        dtype="float32", crs="EPSG:4326", transform=transform, nodata=-9999.0,
    ) as dst:
        dst.write(np.ones((3, 3), dtype="float32"), 1)

    with pytest.raises(RuntimeError, match="Topology mismatch"):
        _verify_alignment({"elevation": bad_path}, grid)


@pytest.mark.unit
def test_verify_alignment_passes_for_matching_dimensions_and_none_entries(tmp_path):
    country_gdf = _country_gdf()
    grid = build_reference_grid(country_gdf, resolution_deg=_RES)

    good_path = tmp_path / "good.tif"
    _write_raster(good_path, value=1.0, size=grid.width)
    # Height/width may differ if grid isn't square — force exact match.
    transform = from_origin(_ORIGIN_LON, _ORIGIN_LAT, _RES, _RES)
    with rasterio.open(
        good_path, "w", driver="GTiff", height=grid.height, width=grid.width, count=1,
        dtype="float32", crs="EPSG:4326", transform=transform, nodata=-9999.0,
    ) as dst:
        dst.write(np.ones((grid.height, grid.width), dtype="float32"), 1)

    _verify_alignment({"elevation": good_path, "roads": None}, grid)  # must not raise


# ─── run_grid_alignment_phase(): RuntimeError propagation (item 2) ───


@pytest.mark.unit
def test_run_grid_alignment_phase_propagates_topology_mismatch_uncaught(tmp_path):
    country_gdf = _country_gdf()
    elev_path = tmp_path / "elev.tif"
    _write_raster(elev_path, value=100.0)
    inputs = GridAlignmentInputs(elevation_path=elev_path, country_gdf=country_gdf)
    context = _context(tmp_path)

    def bad_reproject(src_path, out_path, grid, *args, **kwargs):
        transform = from_origin(_ORIGIN_LON, _ORIGIN_LAT, _RES, _RES)
        with rasterio.open(
            out_path, "w", driver="GTiff", height=3, width=3, count=1,
            dtype="float32", crs="EPSG:4326", transform=transform, nodata=-9999.0,
        ) as dst:
            dst.write(np.ones((3, 3), dtype="float32"), 1)
        return out_path

    with (
        patch.object(alignment_module, "reproject_to_grid", side_effect=bad_reproject),
        pytest.raises(RuntimeError, match="Topology mismatch"),
    ):
        run_grid_alignment_phase(context, inputs)


@pytest.mark.unit
def test_run_grid_alignment_phase_has_no_try_except_around_verify_alignment():
    # Static guard, independent of the dynamic test above: parse this
    # module's own source and confirm no try/except statement's body
    # contains the _verify_alignment call. A future edit that wraps it
    # in a broad try/except (silently reintroducing the anti-pattern
    # Passo 3 item 2 explicitly ruled out) will fail this test.
    import ast
    import inspect

    source = inspect.getsource(alignment_module.run_grid_alignment_phase)
    tree = ast.parse(source)

    class _TryVisitor(ast.NodeVisitor):
        found_verify_inside_try = False

        def visit_Try(self, node):
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id == "_verify_alignment"
                ):
                    self.found_verify_inside_try = True
            self.generic_visit(node)

    visitor = _TryVisitor()
    visitor.visit(tree)
    assert visitor.found_verify_inside_try is False


# ─── _execute_or_load()'s own cache paths (alignment-level, distinct
# from the vector-clip cache tested above) ───


@pytest.mark.unit
def test_run_grid_alignment_phase_reuses_already_aligned_raster_on_second_call(tmp_path):
    # _execute_or_load()'s own cache: a second call, with the reference
    # grid unchanged (same country_gdf/resolution), must reuse the
    # already-aligned elevation tif from the first call rather than
    # calling reproject_to_grid() again.
    country_gdf = _country_gdf()
    elev_path = tmp_path / "elev.tif"
    _write_raster(elev_path, value=55.0)
    inputs = GridAlignmentInputs(elevation_path=elev_path, country_gdf=country_gdf)
    context = _context(tmp_path)

    first = run_grid_alignment_phase(context, inputs)
    assert first.elevation is not None

    def fail_if_called(*a, **k):
        raise AssertionError("reproject_to_grid() was called again — alignment cache was NOT reused!")

    with patch.object(alignment_module, "reproject_to_grid", side_effect=fail_if_called):
        second = run_grid_alignment_phase(context, inputs)

    assert second.elevation == first.elevation


@pytest.mark.unit
def test_run_grid_alignment_phase_logs_and_returns_none_when_layer_fn_yields_nothing(tmp_path):
    # condition=True (grid_source exists on disk) but the loaded data
    # has no overlap with the country bbox -> load_vector_bbox() itself
    # returns None -> rasterize_linear_distance(None, ...) returns None
    # -> _execute_or_load()'s "result is None" branch, not the
    # condition=False early-return tested elsewhere.
    country_gdf = _country_gdf()
    far_away_grid_line = gpd.GeoDataFrame(
        geometry=[LineString([(80.0, 80.0), (81.0, 81.0)])], crs="EPSG:4326"
    )
    grid_source = tmp_path / "grid_far.geojson"
    far_away_grid_line.to_file(grid_source, driver="GeoJSON")
    inputs = GridAlignmentInputs(grid_source=grid_source, country_gdf=country_gdf)

    result = run_grid_alignment_phase(_context(tmp_path), inputs)

    assert result.grid is None


@pytest.mark.unit
def test_run_grid_alignment_phase_recomputes_when_cached_raster_dims_mismatch(tmp_path):
    # _execute_or_load()'s dims-mismatch branch: a pre-existing aligned
    # elevation tif with the WRONG dimensions for the current reference
    # grid must be unlinked and recomputed, not returned as-is (that
    # would silently defeat _verify_alignment()'s whole purpose).
    country_gdf = _country_gdf()
    elev_path = tmp_path / "elev.tif"
    _write_raster(elev_path, value=55.0)
    inputs = GridAlignmentInputs(elevation_path=elev_path, country_gdf=country_gdf)
    context = _context(tmp_path)

    stale_path = context.outputs_dir / "PRT" / "grid_alignment" / "PRT_elevation_aligned.tif"
    stale_path.parent.mkdir(parents=True)
    transform = from_origin(_ORIGIN_LON, _ORIGIN_LAT, _RES, _RES)
    with rasterio.open(
        stale_path, "w", driver="GTiff", height=2, width=2, count=1,
        dtype="float32", crs="EPSG:4326", transform=transform, nodata=-9999.0,
    ) as dst:
        dst.write(np.ones((2, 2), dtype="float32"), 1)

    result = run_grid_alignment_phase(context, inputs)

    assert result.elevation is not None
    with rasterio.open(result.elevation) as src:
        assert (src.height, src.width) == (result.grid_metadata.height, result.grid_metadata.width)


# ─── Happy path / result shape ───


@pytest.mark.unit
def test_run_grid_alignment_phase_minimal_inputs_produces_result(tmp_path):
    country_gdf = _country_gdf()
    elev_path = tmp_path / "elev.tif"
    _write_raster(elev_path, value=123.0)
    inputs = GridAlignmentInputs(elevation_path=elev_path, country_gdf=country_gdf)

    result = run_grid_alignment_phase(_context(tmp_path), inputs)

    assert result.country_code == "PRT"
    assert result.elevation is not None
    assert result.elevation.exists()
    with rasterio.open(result.elevation) as src:
        assert (src.height, src.width) == (result.grid_metadata.height, result.grid_metadata.width)
    assert result.roads is None
    assert result.grid is None


@pytest.mark.unit
def test_run_grid_alignment_phase_missing_layers_leave_none_without_error(tmp_path):
    country_gdf = _country_gdf()
    inputs = GridAlignmentInputs(country_gdf=country_gdf)  # nothing else provided

    result = run_grid_alignment_phase(_context(tmp_path), inputs)

    for field in ("elevation", "slope", "solar", "wind", "land_cover", "population",
                  "roads", "grid", "lakes", "rivers", "seismic", "plants"):
        assert getattr(result, field) is None


@pytest.mark.unit
def test_run_grid_alignment_phase_saves_grid_metadata_json(tmp_path):
    country_gdf = _country_gdf()
    inputs = GridAlignmentInputs(country_gdf=country_gdf)
    context = _context(tmp_path)

    result = run_grid_alignment_phase(context, inputs)

    meta_path = context.outputs_dir / "PRT" / "grid_alignment" / "PRT_grid_metadata.json"
    assert meta_path.exists()
    import json

    on_disk = json.loads(meta_path.read_text(encoding="utf-8"))
    assert on_disk["width"] == result.grid_metadata.width
    assert on_disk["height"] == result.grid_metadata.height


@pytest.mark.unit
def test_run_grid_alignment_phase_reprojects_source_with_different_crs(tmp_path):
    country_gdf = _country_gdf()
    elev_path = tmp_path / "elev_3857.tif"
    # Build a raster in EPSG:3857 covering the same area.
    from pyproj import Transformer

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    x0, y0 = transformer.transform(_ORIGIN_LON, _ORIGIN_LAT)
    x1, y1 = transformer.transform(_ORIGIN_LON + 0.6, _ORIGIN_LAT - 0.6)
    transform = rasterio.transform.from_bounds(x0, y1, x1, y0, 60, 60)
    with rasterio.open(
        elev_path, "w", driver="GTiff", height=60, width=60, count=1,
        dtype="float32", crs="EPSG:3857", transform=transform, nodata=-9999.0,
    ) as dst:
        dst.write(np.full((60, 60), 77.0, dtype="float32"), 1)

    inputs = GridAlignmentInputs(elevation_path=elev_path, country_gdf=country_gdf)

    result = run_grid_alignment_phase(_context(tmp_path), inputs)

    assert result.elevation is not None
    with rasterio.open(result.elevation) as src:
        assert src.crs.to_string() == "EPSG:4326"
        data = src.read(1)
    valid = data[data != -9999.0]
    assert valid.size > 0
    assert np.allclose(valid, 77.0, atol=1.0)


@pytest.mark.unit
def test_run_grid_alignment_phase_multi_polygon_country_gdf_does_not_crash(tmp_path):
    # grid_alignment does not call get_mainland_gdf()/detect_island_nation()
    # itself (see alignment.py's module docstring) — it must handle
    # whatever country_gdf it's given, single- or multi-polygon, without
    # special-casing.
    mainland = _square(_ORIGIN_LON + 0.2, _ORIGIN_LAT - 0.2, 0.15)
    islet = _square(_ORIGIN_LON + 5.0, _ORIGIN_LAT - 5.0, 0.02)
    country_gdf = gpd.GeoDataFrame(geometry=[mainland, islet], crs="EPSG:4326")

    inputs = GridAlignmentInputs(country_gdf=country_gdf)

    result = run_grid_alignment_phase(_context(tmp_path), inputs)

    assert result.grid_metadata.n_valid_pixels > 0


# ─── _read_clipped_with_cache() / cache-by-path-convention reuse ───


@pytest.mark.unit
def test_read_clipped_with_cache_computes_and_writes_when_absent(tmp_path):
    country_gdf = _country_gdf()
    src_path = tmp_path / "src.geojson"
    gpd.GeoDataFrame(geometry=[LineString([(_ORIGIN_LON, _ORIGIN_LAT - 0.4), (_ORIGIN_LON + 0.4, _ORIGIN_LAT)])], crs="EPSG:4326").to_file(
        src_path, driver="GeoJSON"
    )
    cache_path = tmp_path / "cache" / "roads_clipped.gpkg"
    assert not cache_path.exists()

    result = _read_clipped_with_cache(src_path, country_gdf, cache_path)

    assert cache_path.exists()
    assert len(result) >= 0  # ran without error; content covered by geo_utils tests


@pytest.mark.unit
def test_read_clipped_with_cache_write_failure_is_logged_not_raised(tmp_path):
    # Caching is a performance optimization, not a correctness
    # requirement — a failure writing the cache file (disk full,
    # permissions, ...) must not abort alignment; the freshly-clipped
    # GeoDataFrame is still returned.
    country_gdf = _country_gdf()
    src_path = tmp_path / "src.geojson"
    gpd.GeoDataFrame(
        geometry=[LineString([(_ORIGIN_LON, _ORIGIN_LAT - 0.4), (_ORIGIN_LON + 0.4, _ORIGIN_LAT)])],
        crs="EPSG:4326",
    ).to_file(src_path, driver="GeoJSON")
    cache_path = tmp_path / "cache" / "roads_clipped.gpkg"

    def boom(*a, **k):
        raise OSError("simulated disk failure")

    with patch.object(gpd.GeoDataFrame, "to_file", side_effect=boom):
        result = _read_clipped_with_cache(src_path, country_gdf, cache_path)

    assert not cache_path.exists()
    assert result is not None


@pytest.mark.unit
def test_read_clipped_with_cache_reads_from_cache_without_calling_read_clipped_to_country(tmp_path):
    country_gdf = _country_gdf()
    cache_path = tmp_path / "cache" / "roads_clipped.gpkg"
    cache_path.parent.mkdir(parents=True)
    pre_seeded = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:4326")
    pre_seeded.to_file(cache_path, driver="GPKG")

    def fail_if_called(*a, **k):
        raise AssertionError("read_clipped_to_country() must not be called when cache exists")

    with patch.object(alignment_module, "read_clipped_to_country", side_effect=fail_if_called):
        result = _read_clipped_with_cache(Path("irrelevant_never_read.shp"), country_gdf, cache_path)

    assert len(result) == 1


@pytest.mark.unit
def test_run_grid_alignment_phase_reuses_preexisting_clip_cache_without_data_quality_audit(tmp_path):
    # The core Passo 1 guarantee: if the SAME cache_path convention
    # already has a file (e.g. because data_quality_audit ran earlier in
    # a separate process), grid_alignment picks it up without ever
    # touching the raw roads_source — proving reuse is by disk-file
    # convention, not a dependency on data_quality_audit's PhaseResult.
    country_gdf = _country_gdf()
    context = _context(tmp_path)

    cache_path = context.outputs_dir / "PRT" / "processed" / "roads_clipped.gpkg"
    cache_path.parent.mkdir(parents=True)
    pre_clipped = gpd.GeoDataFrame(
        geometry=[LineString([(_ORIGIN_LON + 0.1, _ORIGIN_LAT - 0.3), (_ORIGIN_LON + 0.3, _ORIGIN_LAT - 0.1)])],
        crs="EPSG:4326",
    )
    pre_clipped.to_file(cache_path, driver="GPKG")

    # roads_source must still exist on disk (the same real acquisition
    # file both phases would read in production — Passo 1 argues
    # against depending on data_quality_audit's PhaseResult, not
    # against the raw source file being present), but must NEVER
    # actually be read: read_clipped_to_country() is mocked to fail
    # loudly if called, proving the cache is what actually got used.
    roads_source = tmp_path / "roads_source_never_read.shp"
    gpd.GeoDataFrame(geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:4326").to_file(roads_source)
    inputs = GridAlignmentInputs(roads_source=roads_source, country_gdf=country_gdf)

    def fail_if_called(*a, **k):
        raise AssertionError("read_clipped_to_country() was called — cache was NOT reused!")

    with patch.object(alignment_module, "read_clipped_to_country", side_effect=fail_if_called):
        result = run_grid_alignment_phase(context, inputs)

    assert result.roads is not None
    assert result.roads.exists()


@pytest.mark.unit
def test_run_grid_alignment_phase_lakes_and_rivers_also_use_cache_convention(tmp_path):
    country_gdf = _country_gdf()
    context = _context(tmp_path)
    processed_dir = context.outputs_dir / "PRT" / "processed"
    processed_dir.mkdir(parents=True)

    lake = gpd.GeoDataFrame(geometry=[_square(_ORIGIN_LON + 0.2, _ORIGIN_LAT - 0.2, 0.03)], crs="EPSG:4326")
    lake.to_file(processed_dir / "lakes_clipped.gpkg", driver="GPKG")
    river = gpd.GeoDataFrame(
        geometry=[LineString([(_ORIGIN_LON + 0.1, _ORIGIN_LAT - 0.3), (_ORIGIN_LON + 0.3, _ORIGIN_LAT - 0.1)])],
        crs="EPSG:4326",
    )
    river.to_file(processed_dir / "rivers_clipped.gpkg", driver="GPKG")

    lakes_source = tmp_path / "lakes_source_never_read.shp"
    rivers_source = tmp_path / "rivers_source_never_read.shp"
    gpd.GeoDataFrame(geometry=[Polygon([(0, 0), (1, 0), (1, 1)])], crs="EPSG:4326").to_file(lakes_source)
    gpd.GeoDataFrame(geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:4326").to_file(rivers_source)
    inputs = GridAlignmentInputs(lakes_path=lakes_source, rivers_path=rivers_source, country_gdf=country_gdf)

    def fail_if_called(*a, **k):
        raise AssertionError("read_clipped_to_country() was called — cache was NOT reused!")

    with patch.object(alignment_module, "read_clipped_to_country", side_effect=fail_if_called):
        result = run_grid_alignment_phase(context, inputs)

    assert result.lakes is not None and result.lakes.exists()
    assert result.rivers is not None and result.rivers.exists()


# ─── land_cover cache filename mismatch (fixed 2026-09-09) ───


@pytest.mark.unit
def test_run_grid_alignment_phase_land_cover_hits_alignment_cache_on_second_run(tmp_path):
    # Was test_run_grid_alignment_phase_land_cover_never_hits_alignment_cache,
    # documenting the finding reported in Passo 3 (see alignment.py's
    # module docstring): _execute_or_load("land_cover", ...) checked for
    # "{code}_land_cover_aligned.tif" but mosaic_land_cover() wrote
    # "{code}_lc_aligned.tif" — the two never matched, so land_cover
    # recomputed on every call. Fixed 2026-09-09 (Passo 6, authorized
    # after live PRT+BRA validation measured the real cost: 529.7s
    # recomputed every grid_alignment run for BRA). Flipped from
    # call_count == 2 to == 1 — this now locks in the FIXED behavior;
    # without the fix in alignment.py, this assertion fails (confirmed
    # by running it against the pre-fix source: call_count == 2).
    country_gdf = _country_gdf()
    context = _context(tmp_path)

    tile = tmp_path / "tile.tif"
    transform = from_origin(_ORIGIN_LON, _ORIGIN_LAT, _RES, _RES)
    with rasterio.open(
        tile, "w", driver="GTiff", height=60, width=60, count=1,
        dtype="uint8", crs="EPSG:4326", transform=transform, nodata=0,
    ) as dst:
        dst.write(np.full((60, 60), 10, dtype="uint8"), 1)

    inputs = GridAlignmentInputs(land_cover_tiles=[tile], country_gdf=country_gdf)

    call_count = {"n": 0}
    real_mosaic = alignment_module.mosaic_land_cover

    def counting_mosaic(*args, **kwargs):
        call_count["n"] += 1
        return real_mosaic(*args, **kwargs)

    with patch.object(alignment_module, "mosaic_land_cover", side_effect=counting_mosaic):
        run_grid_alignment_phase(context, inputs)
        run_grid_alignment_phase(context, inputs)

    # Cache now works: the second call hits _execute_or_load's cache
    # check and skips recomputation entirely, so mosaic_land_cover() is
    # only ever called once.
    assert call_count["n"] == 1


# ─── resolution mode: fixed default vs. "adaptive" opt-in (2026-09-09, grid_alignment Passo 4 item 3) ───


@pytest.mark.unit
def test_run_grid_alignment_phase_defaults_to_fixed_0_01_resolution(tmp_path):
    # GridAlignmentInputs.resolution_deg defaults to 0.01 (not
    # "adaptive") — matches the value that generated the frozen PRT/BRA
    # baseline. No target_pixels/min_deg/adaptive_pixel_ceiling_deg
    # formula involved when this default is used.
    country_gdf = _country_gdf()
    inputs = GridAlignmentInputs(country_gdf=country_gdf)

    result = run_grid_alignment_phase(_context(tmp_path), inputs)

    assert result.grid_metadata.resolution_deg == pytest.approx(0.01)


@pytest.mark.unit
def test_run_grid_alignment_phase_honors_explicit_fixed_resolution(tmp_path):
    country_gdf = _country_gdf()
    inputs = GridAlignmentInputs(country_gdf=country_gdf, resolution_deg=0.02)

    result = run_grid_alignment_phase(_context(tmp_path), inputs)

    assert result.grid_metadata.resolution_deg == pytest.approx(0.02)


@pytest.mark.unit
def test_run_grid_alignment_phase_adaptive_mode_computes_resolution_from_area(tmp_path):
    # "adaptive" is an explicit opt-in (not the default) — when
    # selected, reproduces legacy's own formula: sqrt(area/target_pixels)
    # / sqrt(lat_km*lon_km), clipped to [min_deg, adaptive_pixel_ceiling_deg].
    # Using an unrealistically small target_pixels forces the clip to
    # the ceiling,
    # giving a value independent of the exact WGS84 scale-factor
    # arithmetic (covered separately by test_core_geodesy.py) and
    # trivial to assert on.
    country_gdf = _country_gdf()
    inputs = GridAlignmentInputs(
        country_gdf=country_gdf,
        resolution_deg="adaptive",
        adaptive_target_pixels=1,
        adaptive_min_deg=0.001,
        adaptive_pixel_ceiling_deg=0.03,
    )

    result = run_grid_alignment_phase(_context(tmp_path), inputs)

    assert result.grid_metadata.resolution_deg == pytest.approx(0.03)


@pytest.mark.unit
def test_run_grid_alignment_phase_adaptive_mode_respects_min_deg_clip(tmp_path):
    # Symmetric case: an unrealistically large target_pixels forces the
    # clip to min_deg instead.
    country_gdf = _country_gdf()
    inputs = GridAlignmentInputs(
        country_gdf=country_gdf,
        resolution_deg="adaptive",
        adaptive_target_pixels=10_000_000_000,
        adaptive_min_deg=0.005,
        adaptive_pixel_ceiling_deg=0.05,
    )

    result = run_grid_alignment_phase(_context(tmp_path), inputs)

    assert result.grid_metadata.resolution_deg == pytest.approx(0.005)


# ─── max_dist_km unification (2026-09-09, grid_alignment Passo 4 item 2) ───


@pytest.mark.unit
def test_run_grid_alignment_phase_passes_inputs_max_dist_km_to_roads_and_rivers(tmp_path):
    # roads/grid/rivers all used to hardcode their own max_dist_km
    # (100.0 for roads/grid, an inline 50.0 for rivers). Both now read
    # inputs.max_dist_km — confirmed here with a non-default value,
    # captured via mocks rather than assumed.
    country_gdf = _country_gdf()
    roads_source = tmp_path / "roads_source.shp"
    gpd.GeoDataFrame(
        geometry=[LineString([(_ORIGIN_LON + 0.1, _ORIGIN_LAT - 0.3), (_ORIGIN_LON + 0.3, _ORIGIN_LAT - 0.1)])],
        crs="EPSG:4326",
    ).to_file(roads_source)
    rivers_source = tmp_path / "rivers_source.shp"
    gpd.GeoDataFrame(
        geometry=[LineString([(_ORIGIN_LON + 0.1, _ORIGIN_LAT - 0.3), (_ORIGIN_LON + 0.3, _ORIGIN_LAT - 0.1)])],
        crs="EPSG:4326",
    ).to_file(rivers_source)
    inputs = GridAlignmentInputs(
        roads_source=roads_source, rivers_path=rivers_source, country_gdf=country_gdf, max_dist_km=77.0
    )

    real_rasterize = alignment_module.rasterize_linear_distance
    real_align_rivers = alignment_module.align_rivers
    captured: dict[str, float] = {}

    def spy_rasterize(gdf, out_path, country_gdf_arg, grid, label, max_dist_km):
        if label == "roads":
            captured["roads"] = max_dist_km
        return real_rasterize(gdf, out_path, country_gdf_arg, grid, label, max_dist_km)

    def spy_align_rivers(gdf, out_path, grid, max_dist_km):
        captured["rivers"] = max_dist_km
        return real_align_rivers(gdf, out_path, grid, max_dist_km)

    with (
        patch.object(alignment_module, "rasterize_linear_distance", side_effect=spy_rasterize),
        patch.object(alignment_module, "align_rivers", side_effect=spy_align_rivers),
    ):
        run_grid_alignment_phase(_context(tmp_path), inputs)

    assert captured["roads"] == 77.0
    assert captured["rivers"] == 77.0
