"""Generate the ZZZ synthetic-country fixture (METHODOLOGY A-06/V-08, playbook COMMAND ADJ-2).

Writes every raw layer the data_acquisition registry (_LAYER_REGISTRY,
src/geofrea/data_acquisition/phase.py) declares, as small hand-computable
files, under a fixture root that is neither GEOFREA_SHARED_RAW_DIR nor the
repository -- GEOFREA_DATA_DIR/fixtures/synthetic_zzz/raw/.

Extent (see chat report / core.md for the rationale): lon [20.00, 20.30],
lat [-5.00, -4.80] -- 6 x 4 decision cells (0.05 deg) = 30 x 20 pixels
(0.01 deg). Every value below is chosen so the expected result is
computable by hand, not merely plausible; see the docstring of each
generator function for what it tests.

Run once, from the repository root, with GEOFREA_DATA_DIR set:
    python generate_zzz_fixture.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString, Point, box

# --- Extent -----------------------------------------------------------
WEST, EAST = 20.00, 20.30
SOUTH, NORTH = -5.00, -4.80
DECISION_CELL_DEG = 0.05
PIXEL_DEG = 0.01
N_COLS = round((EAST - WEST) / PIXEL_DEG)  # 30
N_ROWS = round((NORTH - SOUTH) / PIXEL_DEG)  # 20
N_CELLS_X = round((EAST - WEST) / DECISION_CELL_DEG)  # 6
N_CELLS_Y = round((NORTH - SOUTH) / DECISION_CELL_DEG)  # 4

FIXTURE_ROOT = Path(os.environ["GEOFREA_DATA_DIR"]) / "fixtures" / "synthetic_zzz"
RAW = FIXTURE_ROOT / "raw"

CRS = "EPSG:4326"


def _raster_transform():
    return from_origin(WEST, NORTH, PIXEL_DEG, PIXEL_DEG)


def _write_raster(path: Path, array: np.ndarray, dtype: str, nodata: float | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=array.shape[0],
        width=array.shape[1],
        count=1,
        dtype=dtype,
        crs=CRS,
        transform=_raster_transform(),
        nodata=nodata,
    ) as dst:
        dst.write(array, 1)


def gen_borders() -> None:
    """Country polygon: the full bbox rectangle -- nests exactly on 0.05 deg."""
    gdf = gpd.GeoDataFrame(
        {"GID_0": ["ZZZ"], "COUNTRY": ["Synthetica"]},
        geometry=[box(WEST, SOUTH, EAST, NORTH)],
        crs=CRS,
    )
    out = RAW / "countries_borders" / "Synthetica" / "gadm41_ZZZ_0.shp"
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out)


def gen_admin1() -> None:
    """Two admin1 divisions, exact west/east halves (3 decision cells each)."""
    mid = WEST + (EAST - WEST) / 2
    gdf = gpd.GeoDataFrame(
        {"GID_0": ["ZZZ", "ZZZ"], "GID_1": ["ZZZ.1_1", "ZZZ.2_1"], "NAME_1": ["West", "East"]},
        geometry=[box(WEST, SOUTH, mid, NORTH), box(mid, SOUTH, EAST, NORTH)],
        crs=CRS,
    )
    out = RAW / "countries_borders" / "Synthetica" / "gadm41_ZZZ_1.shp"
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out)


def gen_elevation() -> None:
    """Slope ramp: elevation(row, col) = col * 10 m. Known max = 290 m (col 29).

    A pure column ramp makes the DEM-derived slope's east-west gradient
    trivial to hand-check (10 m / pixel-width everywhere, 0 north-south).
    """
    row = np.arange(N_COLS, dtype="float32") * 10.0
    arr = np.tile(row, (N_ROWS, 1))
    _write_raster(RAW / "elevation" / "Synthetica" / "ZZZ_elevation.tif", arr, "float32", nodata=-9999.0)


def gen_population() -> None:
    """Population: value(row, col) = row * 20. Known sum, known threshold crossing.

    Row 0 = 0 ... row 19 = 380. Total sum = 20 * sum(0..19) * n_cols =
    20 * 190 * 30 = 114000 (hand-computable). A "threshold=200" query
    crosses exactly at row 10 (value 200) -- rows 0-9 are strictly below,
    rows 10-19 are >= threshold.
    """
    col = np.arange(N_ROWS, dtype="float32").reshape(-1, 1) * 20.0
    arr = np.tile(col, (1, N_COLS))
    _write_raster(RAW / "population" / "zzz_pop_2020.tif", arr, "float32", nodata=-1.0)


def gen_land_cover() -> None:
    """Single ESA-WorldCover-style tile, one class code, known area.

    Class 10 (tree cover) south half, class 40 (cropland) north half --
    each is exactly N_ROWS/2 * N_COLS = 300 pixels, at 0.01 deg (~1.23e-6
    deg^2/pixel at this latitude is not relevant -- the test only needs
    the per-class pixel COUNT, not a real-world area).
    """
    arr = np.full((N_ROWS, N_COLS), 10, dtype="uint8")
    arr[: N_ROWS // 2, :] = 40  # northern half (lower row index = north)
    tile_name = "ESA_WorldCover_10m_2020_v100_S05E020_Map.tif"
    _write_raster(RAW / "land_cover" / "Synthetica" / tile_name, arr, "uint8", nodata=0)


def gen_protected() -> None:
    """Protected polygon covering exactly a 5x5-pixel block (25 pixels, one decision cell)."""
    # Pixel (row, col) 0-indexed from NW corner; block = rows 0-4, cols 0-4
    # (the single NW-most decision cell).
    x0, x1 = WEST, WEST + 5 * PIXEL_DEG
    y1, y0 = NORTH, NORTH - 5 * PIXEL_DEG
    gdf = gpd.GeoDataFrame(
        {"WDPAID": [900001], "NAME": ["Synthetica Reserve"]},
        geometry=[box(x0, y0, x1, y1)],
        crs=CRS,
    )
    out = RAW / "protected_areas" / "wdpa_synthetic.gpkg"
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out, driver="GPKG")


def gen_rivers() -> None:
    """One river line, exact known length: a straight east-west line, full width.

    Length = EAST - WEST = 0.30 deg exactly (planar units, hand-checkable
    before any geodesic correction is applied downstream).
    """
    mid_lat = (SOUTH + NORTH) / 2
    gdf = gpd.GeoDataFrame(
        {"HYRIV_ID": [1]},
        geometry=[LineString([(WEST, mid_lat), (EAST, mid_lat)])],
        crs=CRS,
    )
    out = RAW / "hydrology" / "rivers" / "zzz_rivers.gpkg"
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out, driver="GPKG")


def gen_lakes() -> None:
    """One lake polygon covering exactly a 2x2-pixel block (4 pixels), centered."""
    cx = WEST + (N_COLS // 2) * PIXEL_DEG
    cy = NORTH - (N_ROWS // 2) * PIXEL_DEG
    gdf = gpd.GeoDataFrame(
        {"Lake_name": ["Synthetica Lake"]},
        geometry=[box(cx, cy - 2 * PIXEL_DEG, cx + 2 * PIXEL_DEG, cy)],
        crs=CRS,
    )
    out = RAW / "hydrology" / "lakes" / "zzz_lakes.gpkg"
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out, driver="GPKG")


def gen_roads() -> None:
    """One road line spanning the full north-south extent at the midline (known length 0.20 deg)."""
    mid_lon = WEST + (EAST - WEST) / 2
    gdf = gpd.GeoDataFrame(
        {"gp_gripreg": [99]},
        geometry=[LineString([(mid_lon, SOUTH), (mid_lon, NORTH)])],
        crs=CRS,
    )
    out = RAW / "infrastructure" / "roads" / "Region_9_Synthetic" / "GRIP4_region9.shp"
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out)


def gen_grid() -> None:
    """One transmission-grid line, the same full-height midline as roads, offset by 1 pixel east."""
    mid_lon = WEST + (EAST - WEST) / 2 + PIXEL_DEG
    gdf = gpd.GeoDataFrame(
        {"power": ["line"]},
        geometry=[LineString([(mid_lon, SOUTH), (mid_lon, NORTH)])],
        crs=CRS,
    )
    out = RAW / "infrastructure" / "grid" / "ZZZ_grid_osm.geojson"
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out, driver="GeoJSON")


def gen_solar() -> None:
    """Global-PVOUT-style raster, uniform value 4.5 kWh/kWp/day (known constant, easy mean check)."""
    arr = np.full((N_ROWS, N_COLS), 4.5, dtype="float32")
    out = RAW / "solar_potential" / "World_PVOUT_GISdata_LTAy_AvgDailyTotals_GlobalSolarAtlas-v2_GEOTIFF" / "PVOUT.tif"
    _write_raster(out, arr, "float32", nodata=-9999.0)


def gen_wind() -> None:
    """wind_speed @ 100m + the 11 GWA extra product/height rasters, each a known constant.

    Distinct constants per product so a mis-wired product/height pairing
    downstream is immediately visible instead of silently reading the
    wrong file with a plausible value.
    """
    products_heights = {
        ("wind_speed", 100): 7.0,
        ("wind_speed", 150): 7.5,
        ("wind_speed", 200): 8.0,
        ("combined-Weibull-A", 100): 8.2,
        ("combined-Weibull-A", 150): 8.6,
        ("combined-Weibull-A", 200): 9.0,
        ("combined-Weibull-k", 100): 2.1,
        ("combined-Weibull-k", 150): 2.2,
        ("combined-Weibull-k", 200): 2.3,
        ("air-density", 100): 1.20,
        ("air-density", 150): 1.18,
        ("air-density", 200): 1.16,
    }
    # GWA rasters ship at 0.0025 deg, finer than the 0.01 deg analysis grid.
    gwa_pixel = 0.0025
    gwa_cols = round((EAST - WEST) / gwa_pixel)
    gwa_rows = round((NORTH - SOUTH) / gwa_pixel)
    transform = from_origin(WEST, NORTH, gwa_pixel, gwa_pixel)
    for (product, height), value in products_heights.items():
        arr = np.full((gwa_rows, gwa_cols), value, dtype="float32")
        slug = product.lower().replace("-", "_")
        out = RAW / "wind" / "gwa" / f"ZZZ_{slug}_{height}m.tif"
        out.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(
            out, "w", driver="GTiff", height=gwa_rows, width=gwa_cols, count=1,
            dtype="float32", crs=CRS, transform=transform, nodata=-9999.0,
        ) as dst:
            dst.write(arr, 1)


def gen_power_plants() -> None:
    """3 power plants at known pixel locations, known total capacity_mw = 100."""
    pts = [
        Point(WEST + 2 * PIXEL_DEG, NORTH - 2 * PIXEL_DEG),
        Point(WEST + 15 * PIXEL_DEG, NORTH - 10 * PIXEL_DEG),
        Point(WEST + 28 * PIXEL_DEG, NORTH - 18 * PIXEL_DEG),
    ]
    gdf = gpd.GeoDataFrame(
        {
            "gppd_idnr": ["ZZZ0001", "ZZZ0002", "ZZZ0003"],
            "capacity_mw": [20.0, 30.0, 50.0],
            "primary_fuel": ["Solar", "Wind", "Solar"],
            "country": ["ZZZ", "ZZZ", "ZZZ"],
        },
        geometry=pts,
        crs=CRS,
    )
    out = RAW / "power_plants" / "zzz_power_plants.gpkg"
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out, driver="GPKG")


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    gen_borders()
    gen_admin1()
    gen_elevation()
    gen_population()
    gen_land_cover()
    gen_protected()
    gen_rivers()
    gen_lakes()
    gen_roads()
    gen_grid()
    gen_solar()
    gen_wind()
    gen_power_plants()

    manifest = {
        "extent": {"west": WEST, "east": EAST, "south": SOUTH, "north": NORTH},
        "decision_cells": {"x": N_CELLS_X, "y": N_CELLS_Y, "total": N_CELLS_X * N_CELLS_Y},
        "pixels_0p01deg": {"x": N_COLS, "y": N_ROWS, "total": N_COLS * N_ROWS},
    }
    (FIXTURE_ROOT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))
    print(f"Fixture written under: {RAW}")


if __name__ == "__main__":
    main()
