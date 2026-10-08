"""Common map style for the overview and the publishable figures: relief backdrop, country outline, rivers, scale bar, north arrow.

One place, so every map of every country looks the same and a figure that goes into the thesis only changes its layer, not its
look. The relief is a hillshade of the aligned elevation (about 1 km pixels, so it conveys the large landforms, not the 30 m
detail); layers are drawn over it with some transparency. Nothing here computes a result.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from matplotlib.colors import LightSource
from matplotlib.patches import Rectangle

from geofrea.core import paths as core_paths
from geofrea.core.geodesy import wgs84_km_per_degree

HILLSHADE_AZIMUTH_DEG = 315.0
HILLSHADE_ALTITUDE_DEG = 40.0
VERTICAL_EXAGGERATION = 8.0  # a 1 km pixel flattens relief; exaggerated so the large landforms read
RIVER_QUANTILE = 0.98  # draw the streams above this quantile of the country's mean discharge

Extent = tuple[float, float, float, float]  # (west, east, south, north) in degrees


def hillshade(elevation_m: np.ndarray, extent: Extent) -> np.ndarray:
    """Hillshade in [0, 1] of an elevation grid (NaN outside the country stays NaN)."""
    ny, nx = elevation_m.shape
    mid_lat = 0.5 * (extent[2] + extent[3])
    lat_km, lon_km = wgs84_km_per_degree(np.array([mid_lat]))
    dy = (extent[3] - extent[2]) / ny * float(lat_km[0]) * 1000.0
    dx = (extent[1] - extent[0]) / nx * float(lon_km[0]) * 1000.0
    finite = np.isfinite(elevation_m)
    filled = np.where(finite, elevation_m, np.nanmin(elevation_m) if finite.any() else 0.0)
    light = LightSource(azdeg=HILLSHADE_AZIMUTH_DEG, altdeg=HILLSHADE_ALTITUDE_DEG)
    shade = light.hillshade(filled, vert_exag=VERTICAL_EXAGGERATION, dx=dx, dy=dy)
    return np.where(finite, shade, np.nan)


def country_outline(iso: str) -> gpd.GeoDataFrame | None:
    """The mainland border for drawing, or None if the file is absent (the outline is cosmetic, the layers are not)."""
    path = core_paths.fetched_raw("gadm", iso) / f"gadm41_{iso}_0_mainland.shp"
    return gpd.read_file(path) if path.exists() else None


def major_rivers(iso: str) -> gpd.GeoDataFrame | None:
    """The country's largest streams (HydroRIVERS `DIS_AV_CMS` above RIVER_QUANTILE), or None if no clipped river file exists."""
    path = core_paths.outputs_dir() / iso / "processed" / "rivers_clipped.gpkg"
    if not path.exists():
        return None
    rivers = gpd.read_file(path)
    if "DIS_AV_CMS" not in rivers.columns or rivers.empty:
        return None
    return rivers[rivers["DIS_AV_CMS"] >= rivers["DIS_AV_CMS"].quantile(RIVER_QUANTILE)]


def draw_backdrop(ax, relief: np.ndarray | None, extent: Extent) -> None:
    """Grey relief under everything else (no-op without elevation)."""
    if relief is not None:
        ax.imshow(
            relief,
            extent=extent,
            cmap="Greys_r",
            vmin=0.0,
            vmax=1.0,
            interpolation="bilinear",
            zorder=0,
        )


def draw_overlay(
    ax,
    outline: gpd.GeoDataFrame | None,
    rivers: gpd.GeoDataFrame | None,
    extent: Extent,
    scale_bar: bool = True,
) -> None:
    """Country outline, major rivers, scale bar and north arrow; fixes the axes to `extent` with a geographic aspect."""
    if rivers is not None and len(rivers):
        rivers.plot(ax=ax, color="#2b6cb0", linewidth=0.5, alpha=0.8, zorder=3)
    if outline is not None:
        outline.boundary.plot(ax=ax, color="#222222", linewidth=0.8, zorder=4)
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_aspect(1.0 / np.cos(np.radians(0.5 * (extent[2] + extent[3]))))
    if scale_bar:
        _scale_bar(ax, extent)
    ax.annotate(
        "N",
        xy=(0.94, 0.93),
        xytext=(0.94, 0.80),
        xycoords="axes fraction",
        textcoords="axes fraction",
        ha="center",
        fontsize=9,
        fontweight="bold",
        arrowprops={"arrowstyle": "-|>", "color": "black"},
        zorder=6,
    )


def _scale_bar(ax, extent: Extent) -> None:
    mid_lat = 0.5 * (extent[2] + extent[3])
    _, lon_km = wgs84_km_per_degree(np.array([mid_lat]))
    width_km = (extent[1] - extent[0]) * float(lon_km[0])
    nice = [1, 2, 5, 10, 20, 50, 100, 200, 250, 500, 1000, 2000]
    length_km = max((n for n in nice if n <= width_km / 4), default=nice[0])
    deg = length_km / float(lon_km[0])
    x0, y0 = extent[0] + 0.04 * (extent[1] - extent[0]), extent[2] + 0.04 * (extent[3] - extent[2])
    h = 0.012 * (extent[3] - extent[2])
    ax.add_patch(Rectangle((x0, y0), deg / 2, h, facecolor="black", edgecolor="black", zorder=6))
    ax.add_patch(
        Rectangle((x0 + deg / 2, y0), deg / 2, h, facecolor="white", edgecolor="black", zorder=6)
    )
    ax.text(
        x0 + deg / 2,
        y0 + 1.8 * h,
        f"{length_km:g} km",
        ha="center",
        va="bottom",
        fontsize=7,
        zorder=6,
        bbox={"facecolor": "white", "alpha": 0.6, "pad": 1, "edgecolor": "none"},
    )


def load_relief(elevation_path: Path, max_pixels: int = 700) -> tuple[np.ndarray, Extent] | None:
    """Hillshade and extent from the aligned elevation raster (downsampled like the layers drawn on it), or None if absent."""
    if not Path(elevation_path).exists():
        return None
    with rasterio.open(elevation_path) as src:
        scale = max(1, int(np.ceil(max(src.height, src.width) / max_pixels)))
        shape = (max(1, src.height // scale), max(1, src.width // scale))
        arr = src.read(1, out_shape=shape).astype("float32")
        nodata, b = src.nodata, src.bounds
    if nodata is not None:
        arr[arr == nodata] = np.nan
    arr[~np.isfinite(arr)] = np.nan
    extent = (b.left, b.right, b.bottom, b.top)
    return hillshade(arr, extent), extent
