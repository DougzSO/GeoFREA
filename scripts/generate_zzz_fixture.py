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

The climate inputs F4 reads (D13b) are written by `zzz_climate_fixture.py` under GEOFREA_DATA_DIR/raw/ (where
`core.paths.fetched_raw` looks); set ZZZ_CLIMATE=0 to skip them, and use a scratch GEOFREA_DATA_DIR for them (a real
registry is never overwritten).

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
from shapely.geometry import LineString, box
from zzz_climate_fixture import write_climate_fixture

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
    _write_raster(
        RAW / "elevation" / "Synthetica" / "ZZZ_elevation.tif", arr, "float32", nodata=-9999.0
    )


def gen_dem30() -> None:
    """One Copernicus GLO-30-style 1 degree tile (S05 E020, 3600 x 3600 samples) with the same eastward ramp as `gen_elevation`.

    10 m per 0.01 degree is 10/36 m per 30 m sample, a slope near 0.5 degrees everywhere (bin 0) except where the stencil leaves
    the tile. Written beside the pinned-tile manifest the acquisition script would write, under GEOFREA_DATA_DIR/raw/copernicus_dem30/ZZZ.
    """
    sp = 3600
    dest = Path(os.environ["GEOFREA_DATA_DIR"]) / "raw" / "copernicus_dem30" / "ZZZ"
    dest.mkdir(parents=True, exist_ok=True)
    name = "Copernicus_DSM_COG_10_S05_00_E020_00_DEM"
    z = np.tile(np.arange(sp, dtype="float32") * (10.0 / 36.0), (sp, 1))
    with rasterio.open(
        dest / f"{name}.tif",
        "w",
        driver="GTiff",
        height=sp,
        width=sp,
        count=1,
        dtype="float32",
        crs=CRS,
        transform=from_origin(20.0 - 0.5 / sp, -4.0 + 0.5 / sp, 1 / sp, 1 / sp),
        compress="deflate",
    ) as dst:
        dst.write(z, 1)
    (dest / "manifest.json").write_text(
        json.dumps({"source": "synthetic ZZZ", "tiles": [{"name": name}], "absent_tiles": []})
    )


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
    """Single ESA-WorldCover-style tile with three bands of whole decision cells (5 pixel rows each), known areas.

    North, rows 0-9: class 40 (cropland), excluded for solar (`cropland_excluded`), allowed for wind.
    Middle, rows 10-14: class 30 (grassland), allowed for both technologies: this is the only band where solar has candidates,
    and the population gradient (`gen_population`) and the river's setback (`gen_rivers`) trim it, so the solar path of F3 to F5
    is exercised with a known, non-trivial share.
    South, rows 15-19: class 10 (tree cover), excluded for both.
    Each band is a whole number of decision-cell rows, so no cell mixes classes.
    """
    arr = np.full((N_ROWS, N_COLS), 10, dtype="uint8")
    arr[:10, :] = 40  # northern half (lower row index = north)
    arr[10:15, :] = 30
    tile_name = "ESA_WorldCover_10m_2020_v100_S05E020_Map.tif"
    _write_raster(RAW / "land_cover" / "Synthetica" / tile_name, arr, "uint8", nodata=0)


def gen_protected() -> None:
    """Protected polygon covering exactly a 5x5-pixel block (25 pixels, one decision cell)."""
    # Pixel (row, col) 0-indexed from NW corner; block = rows 0-4, cols 0-4
    # (the single NW-most decision cell).
    x0, x1 = WEST, WEST + 5 * PIXEL_DEG
    y1, y0 = NORTH, NORTH - 5 * PIXEL_DEG
    gdf = gpd.GeoDataFrame(
        {"WDPAID": [900001], "NAME": ["Synthetica Reserve"], "IUCN_CAT": ["Ia"]},
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

    `DIS_AV_CMS` (HydroRIVERS long-term mean discharge, m3/s) is a test value of 50, above every discharge threshold of the
    riparian grid, so the line counts as a river at every threshold F3 evaluates.
    """
    mid_lat = (SOUTH + NORTH) / 2
    gdf = gpd.GeoDataFrame(
        {"HYRIV_ID": [1], "DIS_AV_CMS": [50.0]},
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
    out = (
        RAW
        / "solar_potential"
        / "World_PVOUT_GISdata_LTAy_AvgDailyTotals_GlobalSolarAtlas-v2_GEOTIFF"
        / "PVOUT.tif"
    )
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
            out,
            "w",
            driver="GTiff",
            height=gwa_rows,
            width=gwa_cols,
            count=1,
            dtype="float32",
            crs=CRS,
            transform=transform,
            nodata=-9999.0,
        ) as dst:
            dst.write(arr, 1)


# Synthetic plant inventory for F7b (D-F7b-006): one unit per case so that every metric is a hand computation. (row, col) are pixels of the
# 0.01 degree grid counted from the north-west corner; the expected excluded shares follow from `gen_land_cover`, `gen_protected` and
# `gen_population` (density = people / pixel area of about 1.2265 km2, so rows 0 to 12 stay below the 200 per km2 limit and rows 13 and
# above exceed it).
GEM_UNITS = [
    # (tech, status, MW, start_year, location accuracy, row, col)
    ("wind", "operating", 10.0, 2012, "exact", 2, 2),  # inside the protected block: E1 = 1
    (
        "wind",
        "operating",
        20.0,
        2018,
        "exact",
        7,
        22,
    ),  # cropland is allowed for wind, nothing excludes it
    (
        "wind",
        "operating",
        30.0,
        2020,
        "approximate",
        12,
        10,
    ),  # grassland, density just below the limit: nothing excludes it
    (
        "wind",
        "operating",
        40.0,
        2008,
        "exact",
        16,
        10,
    ),  # tree cover (E5 = 1) and density above the limit (E6 = 1)
    ("wind", "construction", 99.0, 2025, "exact", 2, 2),  # not operating: left out
    ("wind", "retired", 7.0, 2001, "exact", 7, 22),  # not operating: left out
    ("solar", "operating", 12.0, 2019, "exact", 12, 5),  # grassland: nothing excludes it
    (
        "solar",
        "operating",
        8.0,
        2015,
        "approximate",
        7,
        12,
    ),  # cropland is excluded for solar (E5 = 1)
    (
        "solar",
        "operating",
        6.0,
        2021,
        "exact",
        3,
        3,
    ),  # protected block and cropland (E1 = 1, E5 = 1)
    (
        "solar",
        "operating",
        4.0,
        2022,
        "exact",
        14,
        25,
    ),  # grassland, density above the limit (E6 = 1)
    ("solar", "announced", 50.0, 2027, "exact", 12, 5),  # not operating: left out
]
GEM_OUTSIDE = ("wind", "operating", 5.0, 2019, "exact", -4.90, 19.50)  # west of the country grid


def gen_gem_inventory() -> None:
    """`raw/gem/ZZZ/gem_solar_wind_ZZZ.parquet` and its snapshot record with `synthetic: true` (refused by a production run)."""
    import pandas as pd

    rows = []
    for i, (tech, status, mw, year, accuracy, r, c) in enumerate(GEM_UNITS):
        rows.append(
            (
                f"ZZZ-U{i:02d}",
                tech,
                status,
                mw,
                year,
                accuracy,
                NORTH - (r + 0.5) * PIXEL_DEG,
                WEST + (c + 0.5) * PIXEL_DEG,
            )
        )
    tech, status, mw, year, accuracy, lat, lon = GEM_OUTSIDE
    rows.append((f"ZZZ-U{len(GEM_UNITS):02d}", tech, status, mw, year, accuracy, lat, lon))
    frame = pd.DataFrame(
        rows,
        columns=[
            "gem_unit_id",
            "tech",
            "status",
            "capacity_mw",
            "start_year",
            "location_accuracy",
            "lat",
            "lon",
        ],
    )
    frame["start_year"] = frame["start_year"].astype("float64")
    frame["country"] = "ZZZ"
    out = Path(os.environ["GEOFREA_DATA_DIR"]) / "raw" / "gem" / "ZZZ"
    out.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out / "gem_solar_wind_ZZZ.parquet", index=False)
    (out / "gem_snapshot.json").write_text(
        json.dumps({"synthetic": True, "n_features": len(frame), "source": "synthetic ZZZ"}),
        encoding="utf-8",
    )


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    gen_borders()
    gen_admin1()
    gen_elevation()
    gen_dem30()
    gen_population()
    gen_land_cover()
    gen_protected()
    gen_rivers()
    gen_lakes()
    gen_roads()
    gen_grid()
    gen_solar()
    gen_wind()
    gen_gem_inventory()
    if os.environ.get("ZZZ_CLIMATE") != "0":
        write_climate_summary = write_climate_fixture(
            Path(__file__).resolve().parents[1] / "config" / "experiments.yaml"
        )
        print(f"Climate fixture: {write_climate_summary}")

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
