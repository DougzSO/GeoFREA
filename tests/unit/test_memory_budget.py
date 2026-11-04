"""COMMAND 88, item 6: the heaviest layers, run on rasters the size of BRA's, stay under 1.5 GB of resident memory per process.

The peak of a layer is the peak of its own child process (`core.layer_process`), read from the operating system, so the test measures what a run
measures. Each case builds the worst moment of the layer on the real BRA dimensions without the hours of a whole run:

  population   the grid of BRA (3,925 pixels wide) and a source 54,172 pixels wide at 100 m, as the BRA population raster is, over 150 grid rows from
               a latitude that holds data: strips of 400 MB of source window, the case that stopped the cold F2a of BRA (population_memory_87.md).
  glo30        the grid of BRA (3,925 pixels wide) and a block of 256 grid rows, with the GLO-30 tiles of the first strip only: the output block of
               41 bins, the sums and the strip of about 20 million samples are all at their full size; the other strips find no tile and return at once.

A layer over the cap fails the test and the cap is the one in `config/memory_budget.json` (`core.memory_budget.cap_mb`).
"""

from __future__ import annotations

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import Window

from geofrea.core import layer_process, memory_budget
from geofrea.grid_alignment.reference_grid import GridContext

pytestmark = [pytest.mark.unit, pytest.mark.slow]

BRA_WIDTH_PX = 3925
BRA_LEFT, GRID_RES = -74.0, 0.01


@pytest.fixture
def child_mode(monkeypatch):
    monkeypatch.delenv(layer_process.IN_PROCESS_ENV, raising=False)


def _grid(height: int, top: float) -> GridContext:
    return GridContext(
        transform=from_origin(BRA_LEFT, top, GRID_RES, GRID_RES),
        width=BRA_WIDTH_PX,
        height=height,
        crs="EPSG:4326",
        country_mask=np.ones((height, BRA_WIDTH_PX), dtype=bool),
    )


def _write_population_source(path, grid_top: float, grid_rows: int) -> None:
    """A 100 m population-like source as wide as the BRA raster, over the latitudes of `grid_rows` grid rows (plus the kernel's reach)."""
    res = GRID_RES / 12
    width = 54172
    rows = int((grid_rows * GRID_RES + 0.1) / res)
    pattern = np.tile(np.arange(1, 257, dtype=np.float32), width // 256 + 1)[:width]
    with rasterio.open(
        path, "w", driver="GTiff", height=rows, width=width, count=1, dtype="float32", crs="EPSG:4326",
        transform=from_origin(-77.0, grid_top + 0.05, res, res), nodata=-99999.0, tiled=True, blockxsize=256, blockysize=256, compress="lzw",
    ) as dst:  # fmt: skip
        for row in range(0, rows, 256):
            height = min(256, rows - row)
            dst.write(np.tile(pattern, (height, 1)) * np.float32(0.01), 1, window=Window(0, row, width, height))


def test_the_population_warp_of_a_bra_sized_source_stays_under_the_cap(child_mode, tmp_path):
    top, rows = -14.7, 150
    source = tmp_path / "pop.tif"
    _write_population_source(source, top, rows)
    grid = _grid(rows, top)
    _, record = layer_process.run_layer(
        "population",
        "geofrea.grid_alignment.raster_alignment:sum_to_grid",
        {"src_path": source, "out_path": tmp_path / "out.tif", "grid": grid},
        work_dir=tmp_path,
    )
    print(f"BUDGET population peak_rss_mb={record.peak_rss_mb} commit={record.peak_commit_mb} wall={record.wall_s}")
    assert record.peak_rss_mb <= memory_budget.cap_mb(), f"population peaked at {record.peak_rss_mb:.0f} MB"


def _write_dem_tile(path, lat0: int, lon0: int) -> None:
    sp = 3600
    ramp = (np.arange(sp, dtype=np.float32)[:, None] + np.arange(sp, dtype=np.float32)[None, :]) * np.float32(0.05)
    with rasterio.open(
        path, "w", driver="GTiff", height=sp, width=sp, count=1, dtype="float32", crs="EPSG:4326",
        transform=from_origin(lon0, lat0 + 1, 1 / sp, 1 / sp), nodata=-32767.0, tiled=True, blockxsize=256, blockysize=256, compress="lzw",
    ) as dst:  # fmt: skip
        dst.write(ramp, 1)


def test_the_glo30_pass_over_a_bra_sized_block_stays_under_the_cap(child_mode, tmp_path):
    top, rows = -14.0, 256
    grid = _grid(rows, top)
    tiles = []
    for lon0 in range(-74, -34):  # the tiles of the first strip only (grid rows 0 to 3, between 14.00 and 14.04 S): one row of tiles, 40 wide
        tile = tmp_path / f"Copernicus_DSM_COG_10_S15_00_W{abs(lon0):03d}_00_DEM.tif"
        _write_dem_tile(tile, -15, lon0)
        tiles.append(tile)
    _, record = layer_process.run_layer(
        "glo30",
        "geofrea.grid_alignment.raster_alignment:glo30_aligned_outputs",
        {
            "dem_tiles": tiles,
            "grid": grid,
            "elevation_out": tmp_path / "e.tif",
            "slope_out": tmp_path / "s.tif",
            "counts_out": tmp_path / "c.tif",
        },
        work_dir=tmp_path,
    )
    print(f"BUDGET glo30 peak_rss_mb={record.peak_rss_mb} commit={record.peak_commit_mb} wall={record.wall_s}")
    assert record.peak_rss_mb <= memory_budget.cap_mb(), f"glo30 peaked at {record.peak_rss_mb:.0f} MB"
