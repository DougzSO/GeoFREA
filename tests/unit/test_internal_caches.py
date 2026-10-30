"""The internal caches hold the code that computed them (COMMAND 61, A-02).

A cache outside the manifest (clips, aligned layers, the land-cover tile results, the sub-pixel shares of F3, the extremes of the 30 m DEM, the
ERA5 reduction, the GWA mosaic, the GADM mainland files) holds a result that code computed. For each one: a change of a calculation line of the code
that computes it gives another key (the cache is recomputed), a comment, a docstring or a reformat does not. The keys are the real ones; the source
they read is a copy of the package, edited in the test.
"""

from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
import xarray as xr
from rasterio.transform import from_origin
from shapely.geometry import box

import geofrea
from geofrea.core import cache_code as cache_code_module
from geofrea.core.cache_code import CACHE_CODE_ROOTS, cache_code
from geofrea.core.cache_key import cache_key
from geofrea.core.code_fingerprint import closure_fingerprint

pytestmark = pytest.mark.unit

SRC = Path(geofrea.__file__).resolve().parent

# cache -> a module of the code that computes it (the test edits a numeric constant inside one of its functions)
TARGET = {
    "clip": "core/geo_utils.py",
    "aligned_layers": "grid_alignment/raster_alignment.py",
    "land_cover_tiles": "data_quality_audit/land_cover_tiles.py",
    "raster_audit": "data_quality_audit/raster_inspection.py",
    "subpixel_shares": "land_eligibility/fractions.py",
    "dem30_extremes": "siting_layers/sanity.py",
    "era5_reduction": "data_acquisition/fetchers/era5.py",
    "gwa_mask_mosaic": "data_acquisition/fetchers/wind.py",
    "gadm_mainland": "data_acquisition/fetchers/gadm.py",
    "cf_table": "technical_potential/cf_table.py",
}


@pytest.fixture
def source_copy(tmp_path) -> Path:
    target = tmp_path / "geofrea"
    shutil.copytree(SRC, target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


def _read_from(monkeypatch, root: Path) -> None:
    """Make every cache key read its code fingerprint from the package at `root`."""
    monkeypatch.setattr(
        cache_code_module,
        "cached_closure_fingerprint",
        lambda roots: closure_fingerprint(roots, root),
    )


def _change_a_calculation(path: Path) -> None:
    """Add one to the first number inside a function of the module: a changed line of calculation."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for func in ast.walk(tree):
        if not isinstance(func, ast.FunctionDef):
            continue
        for node in ast.walk(func):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, int | float)
                and not isinstance(node.value, bool)
            ):
                node.value = node.value + 1
                path.write_text(ast.unparse(tree) + "\n", encoding="utf-8")
                return
    raise AssertionError(f"no number inside a function in {path}")


def _only_a_comment_and_a_docstring(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(
        "# a comment that changes nothing\n\n\n" + text + "\n\n\n# another\n", encoding="utf-8"
    )


# ─── a probe per cache: the real key (or stamp) that decides whether the stored result is current ─────────────────


def _probe_clip(tmp: Path):
    source = tmp / "roads.gpkg"
    source.write_bytes(b"roads")
    mask = gpd.GeoDataFrame(geometry=[box(0, 0, 1, 1)], crs="EPSG:4326")

    def probe() -> str:
        from geofrea.core.geo_utils import clip_cache_key

        return clip_cache_key(source, mask)

    return probe


def _probe_aligned(tmp: Path):
    source = tmp / "dem.tif"
    source.write_bytes(b"dem")

    def probe() -> str:
        from geofrea.grid_alignment.alignment import aligned_layer_key

        return aligned_layer_key([source], {"resolution_deg": 0.01}, None)

    return probe


def _probe_tiles(tmp: Path):
    tile = tmp / "tile.tif"
    tile.write_bytes(b"tile")

    def probe() -> str:
        from geofrea.data_quality_audit.land_cover_tiles import _land_cover_tile_cache_key

        return _land_cover_tile_cache_key(tile, "polygon")

    return probe


def _probe_raster_audit(tmp: Path):
    path = tmp / "layer.tif"
    with rasterio.open(
        path, "w", driver="GTiff", height=4, width=4, count=1, dtype="float32",
        crs="EPSG:4326", transform=from_origin(0, 4, 1, 1),
    ) as dst:  # fmt: skip
        dst.write(np.ones((4, 4), dtype="float32"), 1)
    cache_dir = tmp / "raster_audit_cache"

    def probe() -> str:
        from geofrea.data_quality_audit.raster_inspection import inspect_raster_cached

        mask = gpd.GeoDataFrame(geometry=[box(0, 0, 4, 4)], crs="EPSG:4326")
        inspect_raster_cached(path, mask, cache_dir=cache_dir)
        return json.loads((cache_dir / "layer.json").read_text(encoding="utf-8"))["cache_key"]

    return probe


def _probe_shares(tmp: Path):
    source = tmp / "lakes.gpkg"
    source.write_bytes(b"lakes")
    mask = gpd.GeoDataFrame(geometry=[box(0, 0, 1, 1)], crs="EPSG:4326")

    def probe() -> str:
        from geofrea.land_eligibility.pipeline import _share_key

        return _share_key("lakes", source, mask, from_origin(0, 1, 0.01, 0.01), (100, 100))

    return probe


def _probe_dem30(tmp: Path):
    tiles = tmp / "tiles"
    tiles.mkdir()
    with rasterio.open(
        tiles / "t.tif", "w", driver="GTiff", height=2, width=2, count=1, dtype="float32",
        crs="EPSG:4326", transform=from_origin(0, 2, 1, 1),
    ) as dst:  # fmt: skip
        dst.write(np.array([[1, 2], [3, 4]], dtype="float32"), 1)
    cache = tmp / "dem30_extremes.json"

    def probe() -> str:
        from geofrea.siting_layers.sanity import dem30_extremes

        dem30_extremes(tiles, cache)
        return json.loads(cache.read_text(encoding="utf-8"))["code"]

    return probe


def _probe_era5(tmp: Path):
    path = tmp / "fg10_2000.nc"

    def probe() -> str:
        from geofrea.data_acquisition.fetchers.era5 import _batch_tag, _year_checkpoint_ok

        # the checkpoint is written under the current code; it is current only while the code is the one that wrote it
        stamp = cache_code("era5_reduction")
        ds = xr.Dataset(
            {"fg10": (("lat", "lon"), np.zeros((1, 1), "float32"))},
            coords={"lat": [0.0], "lon": [0.0]},
        )
        ds = ds.expand_dims(year=[2000])
        ds.attrs["mask_fingerprint"] = "m"
        ds.attrs["code_fingerprint"] = stamp
        ds.to_netcdf(path)
        assert _year_checkpoint_ok(path, 2000, "fg10", "m")
        return _batch_tag()

    return probe


def _probe_gwa(tmp: Path):
    source = tmp / "IND_wind.tif"
    source.write_bytes(b"gwa")
    mask = gpd.GeoDataFrame(geometry=[box(0, 0, 1, 1)], crs="EPSG:4326")

    def probe() -> str:
        from geofrea.data_acquisition.fetchers.wind import _stamp

        return json.dumps(_stamp([source], mask), sort_keys=True)

    return probe


def _probe_gadm(tmp: Path):
    def probe() -> str:
        from geofrea.data_acquisition.fetchers.gadm import _current_rule

        return _current_rule()

    return probe


def _probe_cf_table(tmp: Path):
    def probe() -> str:
        from geofrea.technical_potential.cf_table import table_key
        from geofrea.technical_potential.power_curve import PowerCurve

        curve = PowerCurve(
            curve_id="probe", iec_class="III", rated_power_kw=1000.0, v_ms=[3.0, 8.0, 12.0, 25.0],
            p_kw=[0.0, 400.0, 1000.0, 1000.0], cut_out_ms=25.0, reference_density_kg_m3=1.225, synthetic=True,
        )  # fmt: skip
        return table_key(curve)

    return probe


PROBES = {
    "clip": _probe_clip,
    "aligned_layers": _probe_aligned,
    "land_cover_tiles": _probe_tiles,
    "raster_audit": _probe_raster_audit,
    "subpixel_shares": _probe_shares,
    "dem30_extremes": _probe_dem30,
    "era5_reduction": _probe_era5,
    "gwa_mask_mosaic": _probe_gwa,
    "gadm_mainland": _probe_gadm,
    "cf_table": _probe_cf_table,
}


def test_every_cache_of_the_inventory_has_a_probe_and_a_target():
    assert set(CACHE_CODE_ROOTS) == set(PROBES) == set(TARGET)


@pytest.mark.parametrize("name", sorted(CACHE_CODE_ROOTS))
def test_a_changed_calculation_gives_another_key_and_a_comment_does_not(
    name, tmp_path, source_copy, monkeypatch
):
    target = source_copy / TARGET[name]
    probe = PROBES[name](tmp_path)

    _read_from(monkeypatch, source_copy)
    base = probe()
    assert probe() == base  # deterministic

    original = target.read_text(encoding="utf-8")
    _only_a_comment_and_a_docstring(target)
    assert probe() == base, "a comment changed the key"

    target.write_text(original, encoding="utf-8")
    _change_a_calculation(target)
    assert probe() != base, "a changed line of calculation left the key as it was"


def test_the_keys_of_two_caches_hold_the_code_of_their_own_modules(source_copy):
    """A line changed in the module of one cache does not invalidate a cache whose code does not import it."""
    before = {
        name: closure_fingerprint(roots, source_copy) for name, roots in CACHE_CODE_ROOTS.items()
    }
    _change_a_calculation(source_copy / TARGET["dem30_extremes"])
    after = {
        name: closure_fingerprint(roots, source_copy) for name, roots in CACHE_CODE_ROOTS.items()
    }
    changed = {n for n in before if before[n] != after[n]}
    assert "dem30_extremes" in changed
    assert "subpixel_shares" not in changed and "gadm_mainland" not in changed


# ─── no cache without the code in its key ────────────────────────────────────────────────────────────────────────


def test_a_cache_key_cannot_be_built_without_the_code():
    with pytest.raises(TypeError):
        cache_key(1, [], {})  # type: ignore[call-arg]


def test_the_code_is_part_of_the_key():
    assert cache_key(1, [], {}, code="a") != cache_key(1, [], {}, code="b")


def _calls(tree: ast.AST, name: str):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            called = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if called == name:
                yield node


def test_every_call_that_builds_a_cache_key_passes_the_code_and_names_a_cache_of_the_inventory():
    used: set[str] = set()
    for path in SRC.rglob("*.py"):
        if path.name == "cache_key.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in _calls(tree, "cache_key"):
            assert any(k.arg == "code" for k in call.keywords), (
                f"{path.name}:{call.lineno} has no code="
            )
        for call in _calls(tree, "cache_code"):
            arg = call.args[0]
            assert isinstance(arg, ast.Constant) and arg.value in CACHE_CODE_ROOTS, (
                f"{path.name}:{call.lineno}"
            )
            used.add(arg.value)
    assert used == set(CACHE_CODE_ROOTS), "an entry of the inventory that no cache uses"


def test_the_roots_of_every_cache_exist():
    for name, roots in CACHE_CODE_ROOTS.items():
        for root in roots:
            base = SRC.joinpath(*root.split("."))
            assert base.with_suffix(".py").is_file() or (base / "__init__.py").is_file(), (
                name,
                root,
            )
