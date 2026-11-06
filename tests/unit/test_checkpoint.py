"""COMMAND 98: the checkpoint store, and F2a resuming an interrupted GLO-30 pass with a result identical to the continuous run."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Polygon

from geofrea.core import atomic_io, checkpoint
from geofrea.core.checkpoint import CheckpointStore, clear_checkpoint, make_key
from geofrea.core.content_hash import content_hash
from geofrea.grid_alignment import raster_alignment as ra
from geofrea.grid_alignment.reference_grid import build_reference_grid

# --- the store ----------------------------------------------------------------------------------------------------------------------------


def _store(tmp_path: Path, key: str = "k1", **kwargs) -> CheckpointStore:
    return CheckpointStore(tmp_path / "work_ckpt", key, label="test", **kwargs)


def test_arrays_json_and_frames_round_trip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    arrays = {
        "a": np.arange(12, dtype="float32").reshape(3, 4),
        "b": np.ones((2, 2), dtype="uint16"),
    }
    assert store.save_arrays(3, arrays, {"flag": True})
    loaded = store.load_arrays(3)
    assert loaded is not None
    got, meta = loaded
    assert meta == {"flag": True} and set(got) == {"a", "b"}
    np.testing.assert_array_equal(got["a"], arrays["a"])
    assert got["b"].dtype == np.uint16

    assert store.save_json("rng", {"state": {"x": [1, 2, 3]}})
    assert store.load_json("rng") == {"state": {"x": [1, 2, 3]}}

    frame = pd.DataFrame(
        {"cell": [1, 2, 3], "v": [0.5, 1.5, 2.5]}, index=pd.Index([10, 11, 12], name="member")
    )
    assert store.save_frame("m0", frame)
    pd.testing.assert_frame_equal(store.load_frame("m0"), frame)
    assert sorted(store.done_units()) == ["00000003", "m0", "rng"]


def test_a_missing_unit_is_none(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert (
        store.load_arrays(1) is None
        and store.load_json("x") is None
        and store.load_frame("x") is None
    )


def test_units_found_on_a_second_open_with_the_same_key(tmp_path: Path) -> None:
    _store(tmp_path).save_arrays(0, {"a": np.zeros(3)})
    again = _store(tmp_path)
    assert again.resumed_from == 1 and again.load_arrays(0) is not None


def test_another_key_drops_every_stored_unit_with_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _store(tmp_path, "old").save_arrays(0, {"a": np.zeros(3)})
    with caplog.at_level(logging.WARNING):
        fresh = _store(tmp_path, "new")
    assert fresh.resumed_from == 0 and fresh.load_arrays(0) is None
    assert "another computation" in caplog.text and "1 stored units dropped" in caplog.text


def test_a_truncated_manifest_drops_the_units(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save_arrays(0, {"a": np.zeros(3)})
    manifest = store.directory / "manifest.json"
    manifest.write_text(manifest.read_text(encoding="utf-8")[:20], encoding="utf-8")
    assert _store(tmp_path).resumed_from == 0


def test_an_unreadable_unit_is_removed_and_computed_again(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = _store(tmp_path)
    store.save_arrays(5, {"a": np.arange(1000.0)})
    path = store.directory / "00000005.npz"
    path.write_bytes(path.read_bytes()[: path.stat().st_size // 2])
    with caplog.at_level(logging.WARNING):
        assert store.load_arrays(5) is None
    assert not path.exists() and "cannot be read" in caplog.text


def test_a_unit_made_under_another_key_is_not_trusted(tmp_path: Path) -> None:
    store = _store(tmp_path, "k1")
    store.save_arrays(0, {"a": np.zeros(3)})
    other = _store(tmp_path, "k1")
    other.key = "k2"  # a stale unit that survived beside a manifest of another computation
    assert other.load_arrays(0) is None


def test_a_failure_while_storing_leaves_no_unit_and_no_residue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)

    def boom(self, target):
        raise RuntimeError("killed")

    monkeypatch.setattr(Path, "replace", boom)
    with pytest.raises(RuntimeError):
        store.save_arrays(0, {"a": np.zeros(3)})
    assert store.done_units() == [] and not list(store.directory.glob("*.tmp"))


def test_a_stored_unit_is_flushed_before_it_is_moved_into_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    order = []
    real = atomic_io.replace_durable
    monkeypatch.setattr(
        checkpoint, "replace_durable", lambda t, f: (order.append("durable"), real(t, f))[1]
    )
    _store(tmp_path).save_arrays(0, {"a": np.zeros(3)})
    assert order == ["durable"]


def test_the_disk_bound_stops_storing_and_warns_once(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = _store(tmp_path, max_bytes=2_000)
    assert store.save_arrays(0, {"a": np.zeros(100)})
    with caplog.at_level(logging.WARNING):
        assert store.save_arrays(1, {"a": np.zeros(10_000)}) is False
        assert store.save_arrays(2, {"a": np.zeros(10_000)}) is False
    assert caplog.text.count("are not stored") == 1


def test_the_bound_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(checkpoint.ENV_MAX_GB, "0.5")
    assert checkpoint.max_bytes_from_environment() == 2**29
    monkeypatch.setenv(checkpoint.ENV_MAX_GB, "not a number")
    assert checkpoint.max_bytes_from_environment() == int(checkpoint.DEFAULT_MAX_GB * 2**30)


def test_clear_removes_the_directory_and_is_idempotent(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save_arrays(0, {"a": np.zeros(3)})
    clear_checkpoint(store.directory)
    clear_checkpoint(store.directory)
    assert not store.directory.exists()


def test_make_key_depends_on_every_part() -> None:
    assert make_key(a=1, b=[2]) == make_key(b=[2], a=1)
    assert make_key(a=1, b=[2]) != make_key(a=1, b=[3])


# --- F2a: a GLO-30 pass interrupted in the middle resumes to the same rasters --------------------------------------------------------------

_SP = 400
_RES = 0.01


def _grid():
    triangle = Polygon(
        [(-9.0 + 0.05, 39.0 - 0.35), (-9.0 + 0.35, 39.0 - 0.35), (-9.0 + 0.05, 39.0 - 0.05)]
    )
    return build_reference_grid(
        gpd.GeoDataFrame(geometry=[triangle], crs="EPSG:4326"), resolution_deg=_RES
    )


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setattr(ra, "_CHECKPOINT_UNIT_ROWS", 4)
    monkeypatch.setattr(ra, "_OUTPUT_BLOCK_ROWS", 8)
    rng = np.random.default_rng(98)
    z = np.cumsum(rng.normal(0, 2.0, (_SP, _SP)), axis=1) + np.cumsum(
        rng.normal(0, 2.0, (_SP, _SP)), axis=0
    )
    z[100:130, 50:80] = np.nan
    tile = tmp_path / "Copernicus_DSM_COG_10_N38_00_W009_00_DEM.tif"
    with rasterio.open(
        tile, "w", driver="GTiff", height=_SP, width=_SP, count=1, dtype="float32", crs="EPSG:4326",
        transform=from_origin(-9.0 - 0.5 / _SP, 39.0 + 0.5 / _SP, 1 / _SP, 1 / _SP),
    ) as dst:  # fmt: skip
        dst.write(z.astype("float32"), 1)
    return {"tile": tile, "grid": _grid(), "tmp": tmp_path}


class _PowerLoss(
    BaseException
):  # like a Ctrl+C or a kill: not an Exception, so a broad `except Exception` cannot absorb it
    pass


def _run(
    world: dict,
    name: str,
    *,
    checkpoint_dir: Path | None,
    key: str = "layer-key",
    fail_at_row: int | None = None,
    calls: list | None = None,
):
    out = world["tmp"] / name
    out.mkdir(exist_ok=True)
    real = ra._glo30_strip_samples

    def spy(index, grid, r0, r1, sp, handles):
        if calls is not None:
            calls.append(r0)
        if fail_at_row is not None and r0 == fail_at_row:
            raise _PowerLoss
        return real(index, grid, r0, r1, sp, handles)

    ra._glo30_strip_samples = spy
    try:
        return ra.glo30_aligned_outputs(
            [world["tile"]], world["grid"],
            elevation_out=out / "elevation.tif", slope_out=out / "slope.tif", counts_out=out / "counts.tif",
            samples_per_degree=_SP, checkpoint_dir=checkpoint_dir, checkpoint_key=key if checkpoint_dir else None,
        )  # fmt: skip
    finally:
        ra._glo30_strip_samples = real


def _same(a: dict, b: dict) -> None:
    for name in ("elevation", "slope", "slope_counts"):
        assert a[name] is not None and b[name] is not None
        assert Path(a[name]).read_bytes() == Path(b[name]).read_bytes(), name
        assert content_hash(Path(a[name])) == content_hash(Path(b[name]))


def test_the_grid_of_the_test_has_several_units(world: dict) -> None:
    assert world["grid"].height > 3 * 8


def test_with_a_checkpoint_the_rasters_are_those_of_the_run_without_one(world: dict) -> None:
    plain = _run(world, "plain", checkpoint_dir=None)
    stored = _run(world, "stored", checkpoint_dir=world["tmp"] / "ck")
    _same(plain, stored)
    assert (
        len(list((world["tmp"] / "ck").glob("*.npz"))) > 3
    )  # the units are there until the caller clears them


def test_an_interruption_in_the_middle_resumes_to_the_continuous_result(world: dict) -> None:
    continuous = _run(world, "continuous", checkpoint_dir=None)
    ck = world["tmp"] / "ck"
    with pytest.raises(_PowerLoss):
        _run(world, "a", checkpoint_dir=ck, fail_at_row=13)
    assert not list((world["tmp"] / "a").glob("*.tif")) or all(
        ".writing" in p.name for p in (world["tmp"] / "a").glob("*.tif")
    )
    assert {p.name for p in ck.glob("*.npz")} == {
        "00000000.npz",
        "00000001.npz",
        "00000002.npz",
    }  # rows 0-11 were finished

    calls: list[int] = []
    resumed = _run(world, "resumed", checkpoint_dir=ck, calls=calls)
    assert min(calls) == 12  # nothing before the interrupted group is computed again
    _same(continuous, resumed)


def test_two_interruptions_in_a_row_still_give_the_continuous_result(world: dict) -> None:
    continuous = _run(world, "continuous", checkpoint_dir=None)
    ck = world["tmp"] / "ck"
    with pytest.raises(_PowerLoss):
        _run(world, "a", checkpoint_dir=ck, fail_at_row=9)
    with pytest.raises(_PowerLoss):
        _run(world, "b", checkpoint_dir=ck, fail_at_row=21)
    calls: list[int] = []
    final = _run(world, "c", checkpoint_dir=ck, calls=calls)
    assert min(calls) == 20
    _same(continuous, final)


def test_a_run_that_finished_every_group_computes_nothing_again(world: dict) -> None:
    ck = world["tmp"] / "ck"
    first = _run(world, "first", checkpoint_dir=ck)
    calls: list[int] = []
    again = _run(world, "again", checkpoint_dir=ck, calls=calls)
    assert calls == []
    _same(first, again)


def test_a_checkpoint_of_another_layer_key_is_dropped_and_everything_is_computed(
    world: dict, caplog: pytest.LogCaptureFixture
) -> None:
    ck = world["tmp"] / "ck"
    with pytest.raises(_PowerLoss):
        _run(world, "a", checkpoint_dir=ck, key="old-key", fail_at_row=17)
    calls: list[int] = []
    with caplog.at_level(logging.WARNING):
        _run(world, "b", checkpoint_dir=ck, key="new-key", calls=calls)
    assert min(calls) == 0 and "another computation" in caplog.text


def test_a_cut_unit_is_computed_again_and_the_result_is_still_identical(world: dict) -> None:
    continuous = _run(world, "continuous", checkpoint_dir=None)
    ck = world["tmp"] / "ck"
    with pytest.raises(_PowerLoss):
        _run(world, "a", checkpoint_dir=ck, fail_at_row=17)
    victim = ck / "00000001.npz"
    victim.write_bytes(victim.read_bytes()[:50])
    calls: list[int] = []
    resumed = _run(world, "resumed", checkpoint_dir=ck, calls=calls)
    assert 4 in calls and 0 not in calls  # group 1 (rows 4-7) again; group 0 from the store
    _same(continuous, resumed)


def test_a_cut_manifest_drops_the_checkpoint_and_the_result_is_still_identical(world: dict) -> None:
    continuous = _run(world, "continuous", checkpoint_dir=None)
    ck = world["tmp"] / "ck"
    with pytest.raises(_PowerLoss):
        _run(world, "a", checkpoint_dir=ck, fail_at_row=17)
    manifest = ck / "manifest.json"
    manifest.write_text(manifest.read_text(encoding="utf-8")[:15], encoding="utf-8")
    calls: list[int] = []
    resumed = _run(world, "resumed", checkpoint_dir=ck, calls=calls)
    assert min(calls) == 0
    _same(continuous, resumed)


# --- F2a: land cover, a tile is the unit ---------------------------------------------------------------------------------------------------


def _country() -> gpd.GeoDataFrame:
    triangle = Polygon(
        [(-9.0 + 0.05, 39.0 - 0.35), (-9.0 + 0.35, 39.0 - 0.35), (-9.0 + 0.05, 39.0 - 0.05)]
    )
    return gpd.GeoDataFrame(geometry=[triangle], crs="EPSG:4326")


def _strip_tile(path: Path, grid, k: int, row0: int, row1: int, pattern) -> None:
    """A tile of k x k samples per grid pixel that covers the grid rows `row0:row1` and every column, on the pixel edges."""
    res = abs(grid.transform.a) / k
    rows, cols = np.indices(((row1 - row0) * k, grid.width * k))
    with rasterio.open(
        path, "w", driver="GTiff", height=(row1 - row0) * k, width=grid.width * k, count=1, dtype="uint8", crs="EPSG:4326",
        transform=from_origin(grid.transform.c, grid.transform.f - row0 * abs(grid.transform.a), res, res), nodata=0,
    ) as dst:  # fmt: skip
        dst.write(pattern(rows + row0 * k, cols).astype("uint8"), 1)


@pytest.fixture
def counts_world(tmp_path: Path) -> dict:
    grid, k = _grid(), 10
    bounds = [0, 10, 20, grid.height]
    tiles = []
    for i in range(3):
        tile = tmp_path / f"ESA_WorldCover_10m_2020_v100_N36W01{i}_Map.tif"
        _strip_tile(
            tile,
            grid,
            k,
            bounds[i],
            bounds[i + 1],
            lambda r, c, i=i: np.where(c % k < 3 + 2 * i, 30 + 10 * i, 10),
        )
        tiles.append(tile)
    return {"grid": grid, "tiles": tiles, "tmp": tmp_path, "country": _country()}


def _counts_run(
    world: dict,
    name: str,
    *,
    checkpoint_dir=None,
    fail_at_call: int | None = None,
    calls: list | None = None,
) -> Path:
    real = ra._count_exact
    state = {"n": 0}

    def spy(src, counts, grid, k, lut):
        state["n"] += 1
        if calls is not None:
            calls.append(state["n"])
        if fail_at_call is not None and state["n"] == fail_at_call:
            raise _PowerLoss
        return real(src, counts, grid, k, lut)

    ra._count_exact = spy
    try:
        return ra.land_cover_class_counts(
            world["tiles"], world["tmp"] / f"{name}.tif", world["grid"], world["country"],
            checkpoint_dir=checkpoint_dir, checkpoint_key="lc-key" if checkpoint_dir else None,
        )  # fmt: skip
    finally:
        ra._count_exact = real


def test_land_cover_counts_resume_after_an_interruption_to_the_continuous_raster(
    counts_world: dict,
) -> None:
    continuous = _counts_run(counts_world, "continuous")
    ck = counts_world["tmp"] / "lc_ckpt"
    with pytest.raises(_PowerLoss):
        _counts_run(counts_world, "a", checkpoint_dir=ck, fail_at_call=3)
    assert len(list(ck.glob("*.npz"))) == 2  # the first two tiles are stored
    calls: list[int] = []
    resumed = _counts_run(counts_world, "resumed", checkpoint_dir=ck, calls=calls)
    assert calls == [1]  # one tile is counted again, the two stored are not
    assert resumed.read_bytes() == continuous.read_bytes()
    assert content_hash(resumed) == content_hash(continuous)


def test_land_cover_counts_with_a_checkpoint_equal_the_run_without_one(counts_world: dict) -> None:
    plain = _counts_run(counts_world, "plain")
    stored = _counts_run(counts_world, "stored", checkpoint_dir=counts_world["tmp"] / "ck")
    again = _counts_run(counts_world, "again", checkpoint_dir=counts_world["tmp"] / "ck")
    assert plain.read_bytes() == stored.read_bytes() == again.read_bytes()


def test_land_cover_counts_drop_a_checkpoint_made_with_another_tile_list(
    counts_world: dict, caplog: pytest.LogCaptureFixture
) -> None:
    ck = counts_world["tmp"] / "lc_ckpt"
    with pytest.raises(_PowerLoss):
        _counts_run(counts_world, "a", checkpoint_dir=ck, fail_at_call=3)
    counts_world["tiles"] = counts_world["tiles"][
        :2
    ]  # another set of tiles: the stored units are not this computation's
    with caplog.at_level(logging.WARNING):
        calls: list[int] = []
        _counts_run(counts_world, "b", checkpoint_dir=ck, calls=calls)
    assert calls == [1, 2] and "another computation" in caplog.text


@pytest.fixture
def mosaic_world(tmp_path: Path) -> dict:
    grid = _grid()
    height, width = grid.height, grid.width
    specs = (
        ("a", 30, slice(0, height), slice(0, width // 4)),
        ("b", 70, slice(height // 2, height), slice(width // 4, width * 3 // 5)),
        ("c", 90, slice(height * 3 // 4, height), slice(width // 2, width)),
    )
    tiles = []
    for name, value, rows, cols in specs:
        data = np.zeros((height, width), dtype="uint8")
        data[rows, cols] = value
        path = tmp_path / f"{name}.tif"
        with rasterio.open(
            path, "w", driver="GTiff", height=height, width=width, count=1, dtype="uint8", crs="EPSG:4326",
            transform=from_origin(grid.transform.c, grid.transform.f, abs(grid.transform.a), abs(grid.transform.a)), nodata=0,
        ) as dst:  # fmt: skip
            dst.write(data, 1)
        tiles.append(path)
    return {"grid": grid, "tiles": tiles, "tmp": tmp_path, "country": _country()}


def _mosaic_run(
    world: dict,
    name: str,
    *,
    checkpoint_dir=None,
    fail_at_call: int | None = None,
    calls: list | None = None,
) -> Path:
    real = ra.reproject
    state = {"n": 0}

    def spy(*args, **kwargs):
        state["n"] += 1
        if calls is not None:
            calls.append(state["n"])
        if fail_at_call is not None and state["n"] == fail_at_call:
            raise _PowerLoss
        return real(*args, **kwargs)

    ra.reproject = spy
    try:
        return ra.mosaic_land_cover(
            world["tiles"], world["tmp"] / f"{name}.tif", world["grid"], world["country"],
            checkpoint_dir=checkpoint_dir, checkpoint_key="mosaic-key" if checkpoint_dir else None,
        )  # fmt: skip
    finally:
        ra.reproject = real


def test_the_mosaic_resumes_after_an_interruption_and_the_first_tile_still_wins(
    mosaic_world: dict,
) -> None:
    continuous = _mosaic_run(mosaic_world, "continuous")
    ck = mosaic_world["tmp"] / "mosaic_ckpt"
    with pytest.raises(_PowerLoss):
        _mosaic_run(mosaic_world, "a", checkpoint_dir=ck, fail_at_call=3)
    assert len(list(ck.glob("*.npz"))) == 2
    calls: list[int] = []
    resumed = _mosaic_run(mosaic_world, "resumed", checkpoint_dir=ck, calls=calls)
    assert calls == [1]  # only the third tile is warped again
    assert resumed.read_bytes() == continuous.read_bytes()
    with rasterio.open(resumed) as src:
        data = src.read(1)
    inside = mosaic_world["grid"].country_mask
    assert (
        (data[inside] == 30).any() and (data[inside] == 70).any() and (data[inside] == 90).any()
    )  # the three tiles all contributed
    row, col = mosaic_world["grid"].height - 2, int(mosaic_world["grid"].width * 0.55)
    assert (
        inside[row, col] and data[row, col] == 70
    )  # tiles b and c overlap here: the first, b, keeps the pixel


def test_the_mosaic_with_a_checkpoint_equals_the_run_without_one(mosaic_world: dict) -> None:
    plain = _mosaic_run(mosaic_world, "plain")
    ck = mosaic_world["tmp"] / "ck"
    stored = _mosaic_run(mosaic_world, "stored", checkpoint_dir=ck)
    calls: list[int] = []
    again = _mosaic_run(mosaic_world, "again", checkpoint_dir=ck, calls=calls)
    assert calls == [] and plain.read_bytes() == stored.read_bytes() == again.read_bytes()


def test_the_mosaic_checkpoint_is_not_taken_when_the_tile_order_changes(
    mosaic_world: dict, caplog: pytest.LogCaptureFixture
) -> None:
    ck = mosaic_world["tmp"] / "mosaic_ckpt"
    with pytest.raises(_PowerLoss):
        _mosaic_run(mosaic_world, "a", checkpoint_dir=ck, fail_at_call=3)
    mosaic_world["tiles"] = list(
        reversed(mosaic_world["tiles"])
    )  # the order decides which tile keeps a pixel two tiles cover
    with caplog.at_level(logging.WARNING):
        calls: list[int] = []
        _mosaic_run(mosaic_world, "b", checkpoint_dir=ck, calls=calls)
    assert calls == [1, 2, 3] and "another computation" in caplog.text


# --- F3: the strips of a share ----------------------------------------------------------------------------------------------------------------

from shapely.geometry import LineString, box

from geofrea.land_eligibility import fractions as fr
from geofrea.land_eligibility import pipeline as f3

_T = from_origin(10.0, 0.2, 0.01, 0.01)
_SHAPE = (20, 20)


def _fail_on_call(
    monkeypatch: pytest.MonkeyPatch, module, name: str, at_call: int | None
) -> list[int]:
    """Make `module.name` raise a `_PowerLoss` on its `at_call`-th call; the list holds the number of every call made."""
    real = getattr(module, name)
    calls: list[int] = []

    def spy(*args, **kwargs):
        calls.append(len(calls) + 1)
        if at_call is not None and len(calls) == at_call:
            raise _PowerLoss
        return real(*args, **kwargs)

    monkeypatch.setattr(module, name, spy)
    return calls


def _gdf(*geoms):
    return gpd.GeoDataFrame(geometry=list(geoms), crs="EPSG:4326")


def _share_store(tmp_path: Path, key: str = "share-key") -> CheckpointStore:
    return CheckpointStore(tmp_path / "share_ckpt", key, label="share")


def test_polygon_strips_resume_to_the_same_shares(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    poly = _gdf(box(10.013, 0.03, 10.121, 0.147))
    continuous = fr.polygon_coverage_fraction(poly, _T, _SHAPE, strip_rows=3)
    store = _share_store(tmp_path)
    _fail_on_call(monkeypatch, fr, "rasterize", 4)
    with pytest.raises(_PowerLoss):
        fr.polygon_coverage_fraction(poly, _T, _SHAPE, strip_rows=3, checkpoint=store.group("a"))
    monkeypatch.undo()
    calls = _fail_on_call(monkeypatch, fr, "rasterize", None)
    resumed = fr.polygon_coverage_fraction(
        poly, _T, _SHAPE, strip_rows=3, checkpoint=store.group("a")
    )
    np.testing.assert_array_equal(resumed, continuous)
    assert 0 < len(calls) < 7  # the strips stored are not rasterized again


def test_river_corridor_strips_resume_to_the_same_shares(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    river = _gdf(LineString([(10.02, 0.0), (10.17, 0.2)]))
    continuous = fr.river_corridor_fraction(river, [500.0], _T, _SHAPE, strip_rows=3)
    store = _share_store(tmp_path)
    _fail_on_call(monkeypatch, fr, "rasterize", 3)
    with pytest.raises(_PowerLoss):
        fr.river_corridor_fraction(
            river, [500.0], _T, _SHAPE, strip_rows=3, checkpoint=store.group("c0")
        )
    monkeypatch.undo()
    calls = _fail_on_call(monkeypatch, fr, "rasterize", None)
    resumed = fr.river_corridor_fraction(
        river, [500.0], _T, _SHAPE, strip_rows=3, checkpoint=store.group("c0")
    )
    np.testing.assert_array_equal(resumed, continuous)
    assert 0 < len(calls) < 7


def test_settlement_setback_strips_resume_to_the_same_shares_for_every_setback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rng = np.random.default_rng(98)
    mask = rng.random(_SHAPE) < 0.05
    setbacks = [0.0, 500.0, 1000.0]
    continuous = fr.mask_setback_fractions(mask, _T, _SHAPE, setbacks, strip_rows=3)
    store = _share_store(tmp_path)
    _fail_on_call(monkeypatch, fr, "distance_transform_edt", 4)
    with pytest.raises(_PowerLoss):
        fr.mask_setback_fractions(
            mask, _T, _SHAPE, setbacks, strip_rows=3, checkpoint=store.group("s")
        )
    monkeypatch.undo()
    calls = _fail_on_call(monkeypatch, fr, "distance_transform_edt", None)
    resumed = fr.mask_setback_fractions(
        mask, _T, _SHAPE, setbacks, strip_rows=3, checkpoint=store.group("s")
    )
    for t in setbacks:
        np.testing.assert_array_equal(resumed[t], continuous[t])
    assert len(calls) < 7


def test_a_share_cache_is_built_whole_after_an_interruption_and_the_checkpoint_goes_away(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    river = _gdf(LineString([(10.02, 0.0), (10.17, 0.2)]))
    plain = tmp_path / "plain" / "river.npz"

    def build(store=None):
        group = None if store is None else store.group("c0")
        return {
            "c0": fr.river_corridor_fraction(
                river, [500.0], _T, _SHAPE, strip_rows=3, checkpoint=group
            )
        }

    expected = np.load(f3._fraction_files(plain, "k", build)["c0"])

    path = tmp_path / "work" / "river.npz"
    _fail_on_call(monkeypatch, fr, "rasterize", 4)
    with pytest.raises(_PowerLoss):
        f3._fraction_files(path, "k", build, checkpointed=True)
    ck = path.with_suffix("").with_name("river_ckpt")
    assert ck.is_dir() and any(ck.glob("*.npz"))  # the strips of the interrupted build are kept
    assert not (
        path.with_suffix("") / "_key.txt"
    ).exists()  # and the cache does not claim to be whole
    monkeypatch.undo()

    files = f3._fraction_files(path, "k", build, checkpointed=True)
    np.testing.assert_array_equal(np.load(files["c0"]), expected)
    assert not ck.exists()
    assert not list(path.with_suffix("").glob("*.tmp"))


def test_a_share_checkpoint_of_another_key_is_not_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    river = _gdf(LineString([(10.02, 0.0), (10.17, 0.2)]))

    def build(store=None):
        group = None if store is None else store.group("c0")
        return {
            "c0": fr.river_corridor_fraction(
                river, [500.0], _T, _SHAPE, strip_rows=3, checkpoint=group
            )
        }

    path = tmp_path / "river.npz"
    _fail_on_call(monkeypatch, fr, "rasterize", 4)
    with pytest.raises(_PowerLoss):
        f3._fraction_files(path, "key-A", build, checkpointed=True)
    monkeypatch.undo()
    calls = _fail_on_call(monkeypatch, fr, "rasterize", None)
    with caplog.at_level(logging.WARNING):
        f3._fraction_files(path, "key-B", build, checkpointed=True)
    assert len(calls) == 7 and "another computation" in caplog.text  # every strip again
