"""COMMAND 98: a download continues where it stopped, is never named complete before it is, and a tile already there is checked (local HTTP server)."""

from __future__ import annotations

import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from geofrea.core.resumable_download import (
    DownloadError,
    download_resumable,
    existing_entry,
    sha256_of,
)
from geofrea.data_acquisition.fetchers import copernicus_dem30, esa_worldcover

PAYLOAD = np.random.default_rng(98).integers(0, 256, 300_000, dtype=np.uint8).tobytes()


class _Server:
    """Serves `/file` (the payload), `/gone` (404) and `/denied` (403); can cut the body short or ignore the Range header."""

    def __init__(self) -> None:
        self.requests: list[str | None] = []  # the Range header of each request
        self.cut_after: int | None = None  # bytes sent before the connection is closed (once)
        self.ignore_range = False
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silence
                pass

            def do_GET(self):
                outer.requests.append(self.headers.get("Range"))
                if self.path == "/gone":
                    self.send_response(404)
                    self.end_headers()
                    return
                if self.path == "/denied":
                    self.send_response(403)
                    self.end_headers()
                    return
                start = 0
                rng = self.headers.get("Range")
                if rng and not outer.ignore_range:
                    start = int(rng.split("=")[1].split("-")[0])
                    if start >= len(PAYLOAD):
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{len(PAYLOAD)}")
                        self.end_headers()
                        return
                    self.send_response(206)
                    self.send_header(
                        "Content-Range", f"bytes {start}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}"
                    )
                else:
                    self.send_response(200)
                body = PAYLOAD[start:]
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if outer.cut_after is not None:
                    self.wfile.write(body[: outer.cut_after])
                    self.wfile.flush()
                    outer.cut_after = None
                    self.connection.close()
                    return
                self.wfile.write(body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server():
    s = _Server()
    yield s
    s.close()


def test_a_whole_download_is_named_only_when_complete_and_gives_the_manifest_entry(
    tmp_path: Path, server: _Server
) -> None:
    target = tmp_path / "tile.tif"
    entry = download_resumable(f"{server.url}/file", target)
    assert target.read_bytes() == PAYLOAD
    assert entry == {"bytes": len(PAYLOAD), "sha256": hashlib.sha256(PAYLOAD).hexdigest()}
    assert not target.with_suffix(".part").exists()


def test_a_part_left_by_an_interrupted_run_is_continued_with_a_range_request(
    tmp_path: Path, server: _Server
) -> None:
    target = tmp_path / "tile.tif"
    target.with_suffix(".part").write_bytes(PAYLOAD[:100_000])  # what a stop left
    download_resumable(f"{server.url}/file", target)
    assert target.read_bytes() == PAYLOAD
    assert server.requests == ["bytes=100000-"]  # only the missing bytes were asked for


def test_a_connection_cut_in_the_middle_is_continued_within_the_call(
    tmp_path: Path, server: _Server
) -> None:
    target = tmp_path / "tile.tif"
    server.cut_after = 120_000
    download_resumable(f"{server.url}/file", target)
    assert target.read_bytes() == PAYLOAD
    assert server.requests == [None, "bytes=65536-"]  # the 64 KiB block that was cut is read again, nothing before it


def test_a_transfer_that_never_ends_whole_raises_and_keeps_the_part_for_the_next_run(
    tmp_path: Path, server: _Server
) -> None:
    target = tmp_path / "tile.tif"
    original = server.httpd.RequestHandlerClass.do_GET

    def always_cut(handler):
        server.cut_after = 100_000
        original(handler)

    server.httpd.RequestHandlerClass.do_GET = always_cut
    with pytest.raises(DownloadError, match="expected"):
        download_resumable(f"{server.url}/file", target, attempts=2)
    assert not target.exists()  # a cut file is never named as the tile
    assert 0 < target.with_suffix(".part").stat().st_size < len(PAYLOAD)
    server.httpd.RequestHandlerClass.do_GET = original
    download_resumable(f"{server.url}/file", target)  # the next run goes on from the part
    assert target.read_bytes() == PAYLOAD


def test_a_server_that_ignores_the_range_starts_the_file_over(
    tmp_path: Path, server: _Server
) -> None:
    target = tmp_path / "tile.tif"
    target.with_suffix(".part").write_bytes(b"x" * 1000)
    server.ignore_range = True
    download_resumable(f"{server.url}/file", target)
    assert target.read_bytes() == PAYLOAD  # not 1000 bytes of garbage followed by the file


def test_a_part_as_long_as_the_file_is_taken_for_complete_and_a_longer_one_is_dropped(
    tmp_path: Path, server: _Server
) -> None:
    complete = tmp_path / "a.tif"
    complete.with_suffix(".part").write_bytes(PAYLOAD)
    assert download_resumable(f"{server.url}/file", complete)["bytes"] == len(PAYLOAD)
    longer = tmp_path / "b.tif"
    longer.with_suffix(".part").write_bytes(PAYLOAD + b"extra")
    download_resumable(f"{server.url}/file", longer)
    assert longer.read_bytes() == PAYLOAD


def test_a_file_that_does_not_exist_is_none_and_leaves_nothing(
    tmp_path: Path, server: _Server
) -> None:
    target = tmp_path / "sea.tif"
    assert download_resumable(f"{server.url}/gone", target) is None
    assert download_resumable(f"{server.url}/denied", target, absent_statuses=(403, 404)) is None
    assert not target.exists() and not target.with_suffix(".part").exists()


def test_a_file_refused_by_the_verification_is_not_named(tmp_path: Path, server: _Server) -> None:
    target = tmp_path / "tile.tif"

    def refuse(path: Path) -> None:
        raise ValueError("wrong hash")

    with pytest.raises(DownloadError, match="refused"):
        download_resumable(f"{server.url}/file", target, verify=refuse)
    assert not target.exists() and not target.with_suffix(".part").exists()


# --- a tile that is already at its name --------------------------------------------------------------------------------------------------------


def _geotiff(path: Path) -> None:
    with rasterio.open(
        path, "w", driver="GTiff", height=600, width=600, count=1, dtype="float32", crs="EPSG:4326",
        transform=from_origin(0, 1, 0.001, 0.001), tiled=True, blockxsize=256, blockysize=256,
    ) as dst:  # fmt: skip
        dst.write(np.random.default_rng(1).random((600, 600)).astype("float32"), 1)


def test_an_existing_tile_is_whole_when_it_matches_the_recorded_size_and_hash(
    tmp_path: Path,
) -> None:
    tile = tmp_path / "t.tif"
    _geotiff(tile)
    recorded = {"bytes": tile.stat().st_size, "sha256": sha256_of(tile)}
    assert existing_entry(tile, recorded) == recorded
    assert existing_entry(tile, {**recorded, "sha256": "0" * 64}) is None
    assert existing_entry(tile, {**recorded, "bytes": recorded["bytes"] + 1}) is None


def test_without_a_record_a_cut_geotiff_is_refused_and_a_whole_one_accepted(tmp_path: Path) -> None:
    tile = tmp_path / "t.tif"
    _geotiff(tile)
    assert existing_entry(tile, None) is not None
    tile.write_bytes(tile.read_bytes()[: tile.stat().st_size // 2])
    assert existing_entry(tile, None) is None
    tile.write_bytes(b"")
    assert existing_entry(tile, None) is None
    assert existing_entry(tmp_path / "missing.tif", None) is None


# --- the two fetchers ---------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("module", [copernicus_dem30, esa_worldcover])
def test_a_fetcher_sets_a_cut_tile_aside_and_fetches_it_again(
    tmp_path: Path, server: _Server, monkeypatch: pytest.MonkeyPatch, module
) -> None:
    monkeypatch.setattr(module, "BASE_URL", server.url)
    name = "file"  # the server answers /file for the DEM URL <base>/<name>/<name>.tif only through the next patch
    monkeypatch.setattr(
        module,
        "download_resumable",
        lambda url, target, **kw: download_resumable(f"{server.url}/file", target, **kw),
    )
    dest = tmp_path / "tiles"
    dest.mkdir()
    target = dest / (f"{name}.tif" if module is copernicus_dem30 else name)
    target.write_bytes(PAYLOAD[:1000])  # cut tile with no record: not a GeoTIFF
    entry = module._fetch(name, dest)
    assert entry["bytes"] == len(PAYLOAD) and target.read_bytes() == PAYLOAD
    assert (
        target.with_name(target.name + ".corrupt").read_bytes() == PAYLOAD[:1000]
    )  # kept aside, not deleted


@pytest.mark.parametrize("module", [copernicus_dem30, esa_worldcover])
def test_a_fetcher_keeps_a_tile_that_matches_its_manifest_without_downloading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module
) -> None:
    def no_network(*args, **kwargs):
        raise AssertionError("a tile that is whole was downloaded again")

    monkeypatch.setattr(module, "download_resumable", no_network)
    dest = tmp_path / "tiles"
    dest.mkdir()
    name = "tile"
    target = dest / (f"{name}.tif" if module is copernicus_dem30 else name)
    _geotiff(target)
    recorded = {"name": name, "bytes": target.stat().st_size, "sha256": sha256_of(target)}
    assert module._fetch(name, dest, recorded) == recorded
