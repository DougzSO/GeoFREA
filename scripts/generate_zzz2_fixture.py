"""Generate the second synthetic world, ZZZ2 (audit 2026-10, M-1; COMMAND 39), into GEOFREA_DATA_DIR.

Same country code, extent, borders, protected block, rivers, lake, population, elevation and plant inventory as ZZZ (`generate_zzz_fixture.py`), written to the same
fixture root; what changes is described in `zzz2_world.py`: the land cover (grassland over three cell rows, so wind and solar both have candidates in every one of them),
the Weibull scale of the wind atlas (grows eastward), the transmission line (west edge) and the road (east edge), and the miniature CMIP6 files (a spatial pattern of the change
factors per GCM). The hazard inputs (ISIMIP3b, ERA5) are the ZZZ ones. Use a scratch GEOFREA_DATA_DIR: it is not a real country's directory.

Run from the repository root with GEOFREA_DATA_DIR set:
    python scripts/generate_zzz2_fixture.py
"""

from __future__ import annotations

import json
from pathlib import Path

import generate_zzz_fixture as base
import geopandas as gpd
import numpy as np
import rasterio
import zzz2_world as world
from rasterio.transform import from_origin
from shapely.geometry import LineString
from zzz_climate_fixture import write_climate_fixture

WEST_LINE = (
    base.WEST + base.PIXEL_DEG / 2
)  # a line exactly on the border of the grid would fall outside the first or the last pixel column
EAST_LINE = base.EAST - base.PIXEL_DEG / 2


def gen_land_cover() -> None:
    """Grassland (class 30, allowed for both technologies) over pixel rows 0 to 14, tree cover (excluded for both) over rows 15 to 19."""
    arr = np.full((base.N_ROWS, base.N_COLS), 10, dtype="uint8")
    arr[:15, :] = 30
    tile = "ESA_WorldCover_10m_2020_v100_S05E020_Map.tif"
    base._write_raster(base.RAW / "land_cover" / "ZZZ" / tile, arr, "uint8", nodata=0)


def gen_roads() -> None:
    """The road runs along the east edge (through the centres of the last pixel column): the distance to it grows westward."""
    gdf = gpd.GeoDataFrame(
        {"gp_gripreg": [99]},
        geometry=[LineString([(EAST_LINE, base.SOUTH), (EAST_LINE, base.NORTH)])],
        crs=base.CRS,
    )
    out = base.RAW / "infrastructure_roads" / "_global" / "Region_9_Synthetic" / "GRIP4_region9.shp"
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out)


def gen_grid() -> None:
    """The transmission line runs along the west edge (through the centres of the first pixel column): the distance to it grows eastward."""
    gdf = gpd.GeoDataFrame(
        {"power": ["line"]},
        geometry=[LineString([(WEST_LINE, base.SOUTH), (WEST_LINE, base.NORTH)])],
        crs=base.CRS,
    )
    out = base.RAW / "infrastructure_grid" / "ZZZ" / "ZZZ_grid_osm.geojson"
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out, driver="GeoJSON")


def gen_wind() -> None:
    """The twelve atlas rasters of ZZZ, with the Weibull scale multiplied by `wind_resource_factor(lon)` (the other products stay constant)."""
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
    pixel = 0.0025
    cols = round((base.EAST - base.WEST) / pixel)
    rows = round((base.NORTH - base.SOUTH) / pixel)
    lon = base.WEST + (np.arange(cols) + 0.5) * pixel
    transform = from_origin(base.WEST, base.NORTH, pixel, pixel)
    for (product, height), value in products_heights.items():
        row = value * (world.wind_resource_factor(lon) if product == "combined-Weibull-A" else 1.0)
        arr = np.tile(np.asarray(row, dtype="float32"), (rows, 1))
        slug = product.lower().replace("-", "_")
        out = base.RAW / "wind" / "gwa" / f"ZZZ_{slug}_{height}m.tif"
        out.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(
            out,
            "w",
            driver="GTiff",
            height=rows,
            width=cols,
            count=1,
            dtype="float32",
            crs=base.CRS,
            transform=transform,
            nodata=-9999.0,
        ) as dst:
            dst.write(arr, 1)


def main() -> None:
    base.RAW.mkdir(parents=True, exist_ok=True)
    base.gen_borders()
    base.gen_admin1()
    base.gen_elevation()
    base.gen_dem30()
    base.gen_population()
    gen_land_cover()
    base.gen_protected()
    base.gen_rivers()
    base.gen_lakes()
    gen_roads()
    gen_grid()
    base.gen_solar()
    gen_wind()
    base.gen_gem_inventory()
    summary = write_climate_fixture(
        Path(__file__).resolve().parents[1] / "config" / "experiments.yaml",
        cmip6_field=world.cmip6_field,
        native_lat=world.NATIVE_LAT,
        native_lon=world.NATIVE_LON,
    )
    (base.FIXTURE_ROOT / "MANIFEST.json").write_text(
        json.dumps({"world": "ZZZ2", "climate": summary}, indent=2)
    )
    print(f"ZZZ2 fixture written under: {base.RAW}; climate {summary}")


if __name__ == "__main__":
    main()
