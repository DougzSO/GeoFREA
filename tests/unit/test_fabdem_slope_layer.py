"""COMMAND 101 (D-F2a-028): the slope and the slope bins of F2a from FABDEM, the elevation untouched, and the Range fetcher of the tiles."""

from __future__ import annotations

import http.server
import json
import shutil
import sys
import threading
import zipfile
from pathlib import Path
from typing import ClassVar

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Polygon

from geofrea.core import function_fingerprint as ff
from geofrea.core.cache_code import CACHE_FUNCTION_ENTRIES, cache_code
from geofrea.core.code_fingerprint import SRC_ROOT
from geofrea.core.content_hash import content_hash
from geofrea.data_acquisition.fetchers import fabdem
from geofrea.grid_alignment import fabdem_slope as fs
from geofrea.grid_alignment import raster_alignment as ra
from geofrea.grid_alignment.reference_grid import build_reference_grid

# --- the key of the elevation does not move ------------------------------------------------------------------------------------------------

# The code fingerprint of the elevation layer (`aligned_layer.glo30`) at the commit before COMMAND 101. The elevation layer of BRA took 11,117 s and its key holds this value:
# a change here makes every country compute its elevation again, so it is a decision, not a side effect.
GLO30_KEY_CODE_BEFORE_COMMAND_101 = "da77f0affc7fb57308100a0edda01a3dd983abe3443373ade0dce6a7472af717"


def _copy_src(tmp_path: Path) -> Path:
    root = tmp_path / "geofrea"
    shutil.copytree(SRC_ROOT, root, ignore=shutil.ignore_patterns("__pycache__"))
    return root


def _fingerprints(root: Path) -> dict[str, str]:
    return {name: ff.function_fingerprint(entries, root) for name, entries in CACHE_FUNCTION_ENTRIES.items()}


@pytest.mark.skipif(
    sys.version_info[:2] != (3, 11),
    reason="the fingerprint hashes ast.dump, and Python 3.12 adds `type_params=[]` to every function and class definition: the same code has another hash outside 3.11 (OQ-077)",
)
def test_the_code_fingerprint_in_the_key_of_the_elevation_layer_is_the_one_it_had_before_command_101():
    assert cache_code("aligned_layer.glo30") == GLO30_KEY_CODE_BEFORE_COMMAND_101


def test_the_elevation_layer_is_registered_by_the_same_builder_and_the_slope_layer_has_its_own():
    assert CACHE_FUNCTION_ENTRIES["aligned_layer.glo30"][0] == "grid_alignment.layers:build_glo30"
    assert CACHE_FUNCTION_ENTRIES["aligned_layer.fabdem_slope"][0] == "grid_alignment.layers:build_fabdem_slope"
    assert cache_code("aligned_layer.fabdem_slope") != cache_code("aligned_layer.glo30")


def test_the_slope_layer_does_not_reach_the_elevation_builder_and_the_elevation_does_not_reach_the_slope_layer():
    slope = ff.reachable_definitions(CACHE_FUNCTION_ENTRIES["aligned_layer.fabdem_slope"])
    elevation = ff.reachable_definitions(CACHE_FUNCTION_ENTRIES["aligned_layer.glo30"])
    assert "grid_alignment.raster_alignment:_glo30_strip_samples" in slope  # the same differences as the elevation pass
    assert not any(d.startswith("grid_alignment.fabdem_slope:") for d in elevation)
    assert "grid_alignment.layers:build_fabdem_slope" not in elevation


def test_an_edit_of_the_fabdem_slope_code_changes_its_key_and_leaves_the_elevation_and_every_other_layer_alone(tmp_path):
    root = _copy_src(tmp_path)
    before = _fingerprints(root)
    path = root / "grid_alignment" / "fabdem_slope.py"
    text = path.read_text(encoding="utf-8")
    assert "np.clip(np.floor(np.where(valid, slope, 0)), 0, SLOPE_BINS - 1)" in text
    path.write_text(text.replace("np.clip(np.floor(np.where(valid, slope, 0)), 0, SLOPE_BINS - 1)", "np.clip(np.floor(np.where(valid, slope, 0)) + 1, 0, SLOPE_BINS - 1)"), encoding="utf-8")
    after = _fingerprints(root)
    assert {k for k in before if before[k] != after[k]} == {"aligned_layer.fabdem_slope"}


def test_registering_the_slope_layer_changed_the_key_of_no_other_layer(tmp_path):
    """The statement that registers `aligned_layer.fabdem_slope` is not in the dict literal that `cache_code` reaches: without it the other twelve keys are the same."""
    root = _copy_src(tmp_path)
    with_entry = _fingerprints(root)
    path = root / "core" / "cache_code.py"
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if 'CACHE_FUNCTION_ENTRIES["aligned_layer.fabdem_slope"]' not in ln]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    without = {k: ff.function_fingerprint(v, root) for k, v in CACHE_FUNCTION_ENTRIES.items() if k != "aligned_layer.fabdem_slope"}
    assert without == {k: v for k, v in with_entry.items() if k != "aligned_layer.fabdem_slope"}


# --- the slope of FABDEM is computed as the slope of GLO-30 --------------------------------------------------------------------------------

_SP = 400
_RES = 0.01


def _grid():
    triangle = Polygon([(-9.0 + 0.05, 39.0 - 0.35), (-9.0 + 0.35, 39.0 - 0.35), (-9.0 + 0.05, 39.0 - 0.05)])
    return build_reference_grid(gpd.GeoDataFrame(geometry=[triangle], crs="EPSG:4326"), resolution_deg=_RES)


def _write_tile(path: Path, z: np.ndarray, lat0: int, lon0: int, nodata=None) -> Path:
    data = z.astype("float32").copy()
    if nodata is not None:
        data[np.isnan(data)] = nodata
    with rasterio.open(
        path, "w", driver="GTiff", height=_SP, width=_SP, count=1, dtype="float32", crs="EPSG:4326", nodata=nodata,
        transform=from_origin(lon0 - 0.5 / _SP, lat0 + 1 + 0.5 / _SP, 1 / _SP, 1 / _SP),
    ) as dst:  # fmt: skip
        dst.write(data, 1)
    return path


def _surface(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    z = np.cumsum(rng.normal(0, 2.0, (_SP, _SP)), axis=1) + np.cumsum(rng.normal(0, 2.0, (_SP, _SP)), axis=0)
    z[100:130, 50:80] = np.nan
    return z


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(ra, "_CHECKPOINT_UNIT_ROWS", 4)
    monkeypatch.setattr(ra, "_OUTPUT_BLOCK_ROWS", 8)
    monkeypatch.setattr(fs, "_CHECKPOINT_UNIT_ROWS", 4)
    monkeypatch.setattr(fs, "_OUTPUT_BLOCK_ROWS", 8)
    z = _surface(101)
    glo = _write_tile(tmp_path / "Copernicus_DSM_COG_10_N38_00_W009_00_DEM.tif", z, 38, -9)
    return {"z": z, "glo": glo, "grid": _grid(), "tmp": tmp_path}


def _glo30(world, name):
    out = world["tmp"] / name
    out.mkdir(exist_ok=True)
    return ra.glo30_aligned_outputs([world["glo"]], world["grid"], elevation_out=out / "e.tif", slope_out=out / "s.tif", counts_out=out / "c.tif", samples_per_degree=_SP)


def _fab(world, name, fabdem_tiles, **kwargs):
    out = world["tmp"] / name
    out.mkdir(exist_ok=True)
    return fs.fabdem_slope_outputs(fabdem_tiles, [world["glo"]], world["grid"], slope_out=out / "s.tif", counts_out=out / "c.tif", report_out=out / "report.json", samples_per_degree=_SP, **kwargs)


def test_with_fabdem_equal_to_glo30_the_slope_and_the_bins_are_those_of_the_glo30_pass(world):
    fab_tile = _write_tile(world["tmp"] / "N38W009_FABDEM_V1-2.tif", world["z"], 38, -9, nodata=-9999.0)
    reference = _glo30(world, "ref")
    got = _fab(world, "fab", [fab_tile])
    assert set(got) == {"slope", "slope_counts"}  # no elevation: it is not a product of this pass
    # the data are the same; the tags are not (the source of the slope is named in them), and the content hash ignores tags (A-02)
    assert content_hash(Path(got["slope"])) == content_hash(Path(reference["slope"]))
    assert content_hash(Path(got["slope_counts"])) == content_hash(Path(reference["slope_counts"]))
    report = json.loads((world["tmp"] / "fab" / "report.json").read_text(encoding="utf-8"))
    assert report["squares_fabdem"] == 1 and report["squares_glo30_fallback"] == [] and report["fallback_area_km2"] == 0.0


def test_a_flatter_fabdem_surface_gives_other_bins_while_the_elevation_pass_is_unaffected(world):
    flat = _write_tile(world["tmp"] / "N38W009_FABDEM_V1-2.tif", world["z"] * 0.5, 38, -9, nodata=-9999.0)
    reference = _glo30(world, "ref")
    got = _fab(world, "fab", [flat])
    assert content_hash(Path(got["slope_counts"])) != content_hash(Path(reference["slope_counts"]))
    with rasterio.open(got["slope"]) as a, rasterio.open(reference["slope"]) as b:
        sa, sb = a.read(1), b.read(1)
        ok = (sa != a.nodata) & (sb != b.nodata)
        assert sa[ok].mean() < sb[ok].mean()
    # the elevation of the same run of glo30_aligned_outputs is a different pass: rerunning it gives the same bytes
    again = _glo30(world, "again")
    assert Path(again["elevation"]).read_bytes() == Path(reference["elevation"]).read_bytes()


def test_a_square_with_no_fabdem_tile_falls_back_to_glo30_and_is_reported_with_its_area(world):
    got = _fab(world, "fab", [])  # no FABDEM tile at all
    reference = _glo30(world, "ref")
    assert content_hash(Path(got["slope_counts"])) == content_hash(Path(reference["slope_counts"]))
    report = json.loads((world["tmp"] / "fab" / "report.json").read_text(encoding="utf-8"))
    assert report["squares_glo30_fallback"] == ["N38W009"]
    assert report["squares_fabdem"] == 0
    assert report["fallback_area_km2"] == pytest.approx(report["country_area_km2"], rel=1e-9) and report["fallback_area_km2"] > 0
    assert report["fallback_share"] == pytest.approx(1.0)


def test_an_interruption_resumes_to_the_continuous_result(world):
    fab_tile = _write_tile(world["tmp"] / "N38W009_FABDEM_V1-2.tif", world["z"] * 0.7, 38, -9, nodata=-9999.0)
    continuous = _fab(world, "continuous", [fab_tile])

    class Stop(BaseException):
        pass

    real = fs._glo30_strip_samples

    def spy(index, grid, r0, r1, sp, handles):
        if r0 == 13:
            raise Stop
        return real(index, grid, r0, r1, sp, handles)

    ck = world["tmp"] / "ck"
    fs._glo30_strip_samples = spy
    try:
        with pytest.raises(Stop):
            _fab(world, "a", [fab_tile], checkpoint_dir=ck, checkpoint_key="k")
    finally:
        fs._glo30_strip_samples = real
    resumed = _fab(world, "b", [fab_tile], checkpoint_dir=ck, checkpoint_key="k")
    for name in ("slope", "slope_counts"):
        assert Path(resumed[name]).read_bytes() == Path(continuous[name]).read_bytes()


def test_a_tile_whose_name_is_not_fabdems_is_refused(world):
    with pytest.raises(ValueError, match="FABDEM"):
        fs.slope_source_index([world["glo"]], [world["glo"]])


# --- the Range fetcher ---------------------------------------------------------------------------------------------------------------------


class _Handler(http.server.BaseHTTPRequestHandler):
    files: ClassVar[dict[str, bytes]] = {}
    fail_once: ClassVar[set[str]] = set()

    def log_message(self, *args):  # quiet
        pass

    def _serve(self, body_too: bool):
        data = self.files.get(self.path)
        if data is None:
            self.send_response(404)
            self.end_headers()
            return
        rng = self.headers.get("Range")
        if rng:
            start, end = (int(x) for x in rng.split("=")[1].split("-"))
            if self.path in self.fail_once and start > 0:
                self.fail_once.discard(self.path)  # the server drops the first block that is not the directory's
                self.connection.close()
                return
            chunk = data[start : end + 1]
            self.send_response(206)
            self.send_header("Content-Length", str(len(chunk)))
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
            self.end_headers()
            if body_too:
                self.wfile.write(chunk)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("ETag", '"abc"')
        self.end_headers()
        if body_too:
            self.wfile.write(data)

    def do_HEAD(self):
        self._serve(False)

    def do_GET(self):
        self._serve(True)


@pytest.fixture
def server(tmp_path, monkeypatch):
    members = {"N38W009_FABDEM_V1-2.tif": b"tile-A" * 700_000, "N38W008_FABDEM_V1-2.tif": b"tile-B" * 500_000}  # > one 4 MB block: the zip is read in several Range requests
    zip_path = tmp_path / "z.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as z:
        for name, body in members.items():
            z.writestr(f"{fabdem.zip_name('N38W009')[:-4]}/{name}", body)
    name = fabdem.zip_name("N38W009")
    _Handler.files = {f"/{name}": zip_path.read_bytes(), "/license.txt": b"CC BY-NC-SA 4.0 test text"}
    _Handler.fail_once = {f"/{name}"}
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    monkeypatch.setattr(fabdem, "BASE_URL", base)
    monkeypatch.setattr(fabdem, "LICENSE_URL", f"{base}/license.txt")
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(fabdem.time, "sleep", lambda s: None)
    yield members
    httpd.shutdown()


def test_the_zip_of_a_tile_is_named_by_its_ten_degree_corners():
    assert fabdem.zip_name("S18W051") == "S20W060-S10W050_FABDEM_V1-2.zip"
    assert fabdem.zip_name("N38W008") == "N30W010-N40E000_FABDEM_V1-2.zip"
    assert fabdem.tile_name(-3, -60) == "S03W060"


def test_the_fetcher_reads_only_the_tiles_asked_for_by_range_keeps_hash_and_licence_and_survives_a_dropped_block(server):
    dest = fabdem.fetch_tiles(["N38W009", "N30W009"])  # the second is not in the zip: open sea
    manifest = json.loads((dest / "fabdem_manifest.json").read_text(encoding="utf-8"))
    entry = manifest["tiles"]["N38W009"]
    body = server["N38W009_FABDEM_V1-2.tif"]
    assert (dest / "N38W009_FABDEM_V1-2.tif").read_bytes() == body
    assert entry["bytes"] == len(body) and entry["sha256"] == fabdem.sha256_file(dest / "N38W009_FABDEM_V1-2.tif")
    assert entry["range_bytes_read"] < len(body) + 6_000_000  # the member and a block or two of directory, not the zip of two members
    assert "N30W009" in manifest["absent_tiles"] and not (dest / "N38W008_FABDEM_V1-2.tif").exists()  # the other member of the zip was not read
    assert manifest["license"] == "CC BY-NC-SA 4.0" and manifest["license_sha256"] == fabdem.sha256_file(dest / fabdem.LICENSE_FILE)
    assert not list(dest.glob("*.part"))
    have, lacking = fabdem.load_tiles(["N38W009", "N30W009", "N38W008"])
    assert [p.name for p in have] == ["N38W009_FABDEM_V1-2.tif"] and lacking == ["N30W009", "N38W008"]


def test_a_second_run_fetches_nothing_and_a_tile_of_another_size_is_fetched_again(server):
    dest = fabdem.fetch_tiles(["N38W009"])
    stamp = json.loads((dest / "fabdem_manifest.json").read_text(encoding="utf-8"))["tiles"]["N38W009"]["fetched_at"]
    fabdem.fetch_tiles(["N38W009"])
    assert json.loads((dest / "fabdem_manifest.json").read_text(encoding="utf-8"))["tiles"]["N38W009"]["fetched_at"] == stamp
    (dest / "N38W009_FABDEM_V1-2.tif").write_bytes(b"short")  # an interrupted copy under the final name
    fabdem.fetch_tiles(["N38W009"])
    assert (dest / "N38W009_FABDEM_V1-2.tif").read_bytes() == server["N38W009_FABDEM_V1-2.tif"]


def test_the_volume_is_estimated_from_the_zip_directories_without_fetching_a_tile(server):
    estimate = fabdem.estimate_bytes(["N38W009", "N38W008", "N30W009"], dest=Path("nowhere"))
    assert estimate["tiles"] == 2 and estimate["absent"] == ["N30W009"]
    assert estimate["bytes"] == len(server["N38W009_FABDEM_V1-2.tif"]) + len(server["N38W008_FABDEM_V1-2.tif"])
    assert not Path("nowhere").exists()
