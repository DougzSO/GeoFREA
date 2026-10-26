"""Diagnostic figures of the inputs of the pipeline in the common map style (COMMAND 68; spec v2 T-11; A-08, H-5).

They are for looking at the data before F3 builds on them, not for the thesis, and say so (`Diagnostic` in the subtitle and `geofrea_status` in the PNG):

  - `aligned_sheet`: the aligned layers of F2a in three sheets by theme (terrain and land, distances, resource), each layer with its own colour bar
    in the unit it has (the population in people per km2, not per pixel) and the scale of its percentiles, the layout following the shape of the
    country (`adaptive_grid`); a layer that is missing is left out of the sheet and the overview table says it is missing;
  - `land_cover_map`: the land cover as classes with a legend of the classes that exist;
  - `hazard_sheet`: the hazard context of F4, the mean over its members (context only, OQ-007: no hazard enters a loss function);
  - `cost_driver_map`: the distance to the grid and to the road of F2b, uncapped.

A layer is read with decimation (the longest side at most `MAX_PIXELS`), never resampled by value, and the subtitle says at which grid it is drawn.
Nothing here computes a result.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import to_rgba

from geofrea.core import paths as core_paths
from geofrea.core.geodesy import wgs84_km_per_degree
from geofrea.viz import mapstyle as ms
from geofrea.viz.context import MapContext
from geofrea.viz.panels import (
    PanelFigure,
    adaptive_grid,
    add_panel_classes,
    add_panel_colorbar,
    new_panels,
)

logger = logging.getLogger("geofrea.overview.diagnostic")

MAX_PIXELS = 700  # longest side of a drawn raster
STATUS = "diagnostic"
WATER_COLOUR = "#4C8BC7"

# ESA WorldCover 2021 legend (the colours of the product), by class code
LAND_COVER = {
    10: ("Tree cover", "#006400"),
    20: ("Shrubland", "#FFBB22"),
    30: ("Grassland", "#FFFF4C"),
    40: ("Cropland", "#F096FF"),
    50: ("Built-up", "#FA0000"),
    60: ("Bare or sparse vegetation", "#B4B4B4"),
    70: ("Snow and ice", "#F0F0F0"),
    80: ("Permanent water", "#0064C8"),
    90: ("Herbaceous wetland", "#0096A0"),
    95: ("Mangroves", "#00CF75"),
    100: ("Moss and lichen", "#FAE6A0"),
}


@dataclass(frozen=True)
class AlignedLayer:
    """A layer of F2a as a panel: the file stem, the words, the kind of colour and what is done to the values before they are drawn."""

    stem: str
    caption: str
    kind: str  # `colormap_for` kind
    label: str  # colour bar label, with the unit
    table_title: str  # the row of the overview table
    tech: str | None = None
    per_km2: bool = False  # a count per pixel drawn per km2
    binary: bool = False  # 1 where there is water


LAYERS = (
    AlignedLayer("elevation", "Elevation", "elevation", "Elevation (m)", "Elevation (m)"),
    AlignedLayer("slope", "Slope", "slope", "Slope (degrees)", "Slope (degrees)"),
    AlignedLayer(
        "population",
        "Population density",
        "population",
        "People per km²",
        "Population (people per pixel)",
        per_km2=True,
    ),
    AlignedLayer("lakes", "Lakes", "water", "Water", "Lakes (1 = water)", binary=True),
    AlignedLayer(
        "rivers", "Distance to river", "distance", "Distance (km)", "Distance to river (km)"
    ),
    AlignedLayer("roads", "Distance to road", "distance", "Distance (km)", "Distance to road (km)"),
    AlignedLayer(
        "grid",
        "Distance to the grid",
        "distance",
        "Distance (km)",
        "Distance to grid (km, uncapped)",
    ),
    AlignedLayer(
        "solar",
        "Solar resource",
        "density",
        "PVOUT (kWh/kWp/day)",
        "PVOUT (kWh/kWp/day)",
        tech=ms.SOLAR,
    ),
    AlignedLayer(
        "wind_wind_speed_100m",
        "Wind speed at 100 m",
        "density",
        "Wind speed (m/s)",
        "Wind speed 100 m (m/s)",
        tech=ms.WIND,
    ),
    AlignedLayer(
        "wind_weibull_k_100m", "Weibull k at 100 m", "weibull_k", "Weibull k", "Weibull k 100 m"
    ),
    AlignedLayer(
        "wind_air_density_100m",
        "Air density at 100 m",
        "air_density",
        "Air density (kg per m³)",
        "Air density 100 m (kg/m3)",
    ),
)
LAND_COVER_STEM = "land_cover"
LAND_COVER_TITLE = "Land cover (ESA class)"
BY_STEM = {layer.stem: layer for layer in LAYERS}
SHEETS = (
    ("terrain-and-land", "Terrain and land", ("elevation", "slope", "population", "lakes")),
    ("distances", "Distances", ("rivers", "roads", "grid")),
    (
        "resource",
        "Resource",
        ("solar", "wind_wind_speed_100m", "wind_weibull_k_100m", "wind_air_density_100m"),
    ),
)

# the hazard context of F4: column, caption, unit label, colour kind, technology of the colour family
HAZARD_PANELS = (
    ("tx35_days", "Days of 35 °C or more", "Days per year", "temperature", None),
    (
        "tx35_change",
        "Change of the days of 35 °C or more",
        "Change (days per year)",
        "temperature",
        None,
    ),
    ("rx5day_mm", "Largest rainfall in 5 days", "Rainfall (mm)", "water", None),
    ("rx5day_change", "Change of the largest rainfall in 5 days", "Change (mm)", "delta_alt", None),
    (
        "wet_p95_exceed_freq",
        "Wet days above the reference P95",
        "Share of the days",
        "frequency",
        None,
    ),
    (
        "gust_mean_annual_max_ms",
        "Annual maximum of the gust (ERA5)",
        "Gust (m/s)",
        "density",
        ms.WIND,
    ),
)
HAZARD_MEANING = {  # panels that share a colormap say what they have in common
    "tx35_days": "hot days",
    "tx35_change": "hot days",
}


def aligned_path(iso: str, stem: str) -> Path:
    return core_paths.phase_dir(iso, "grid_alignment", "artifacts") / f"{iso}_{stem}_aligned.tif"


def read_layer(
    path: Path, max_pixels: int = MAX_PIXELS
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Band 1 as float32 with nodata -> NaN, decimated so that its longest side is at most `max_pixels`; and (W, E, S, N)."""
    with rasterio.open(path) as src:
        scale = max(1, int(np.ceil(max(src.height, src.width) / max_pixels)))
        shape = (max(1, src.height // scale), max(1, src.width // scale))
        arr = src.read(1, out_shape=shape).astype("float32")
        nodata, b = src.nodata, src.bounds
    if nodata is not None:
        arr[arr == nodata] = np.nan
    arr[~np.isfinite(arr)] = np.nan
    return arr, (b.left, b.right, b.bottom, b.top)


def layer_stats(path: Path) -> dict:
    """Valid-pixel count and min / median / max of the full-resolution layer."""
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float64")
        nodata = src.nodata
    valid = np.isfinite(arr) if nodata is None else (np.isfinite(arr) & (arr != nodata))
    v = arr[valid]
    if v.size == 0:
        return {"n_valid": 0, "min": None, "median": None, "max": None}
    return {
        "n_valid": int(v.size),
        "min": float(v.min()),
        "median": float(np.median(v)),
        "max": float(v.max()),
    }


def per_km2(arr: np.ndarray, extent) -> np.ndarray:
    """A count per pixel as a density per km2: each row of the grid has the geodesic area of its pixels."""
    ny, nx = arr.shape
    west, east, south, north = extent
    lat = north - (np.arange(ny) + 0.5) * (north - south) / ny
    lat_km, lon_km = wgs84_km_per_degree(lat)
    area = lon_km * (east - west) / nx * lat_km * (north - south) / ny
    return arr / area[:, None]


def drawn_resolution(extent, shape, native_deg: float = 0.01) -> str:
    """What the subtitle says of the grid a layer is drawn on: its own 0.01 degree grid, or the decimated one."""
    deg = (extent[1] - extent[0]) / shape[1]
    if deg <= native_deg * 1.05:
        return f"aligned grid {native_deg:g}°"
    return f"aligned grid {native_deg:g}°, drawn at {deg:.2g}°"


def _norm(values: np.ndarray, kind: str, tech: str | None) -> ms.NormInfo:
    finite = values[np.isfinite(values)]
    if not finite.size:
        finite = np.array([0.0, 1.0])
    return ms.resolve_scale(finite, ms.default_scale(kind, tech))


def _scale_note(infos: Sequence[ms.NormInfo]) -> str:
    return (
        ms.clip_note(next((i for i in infos if i.extend != "neither"), infos[0])) if infos else ""
    )


def _sheet(
    ctx: MapContext,
    iso: str,
    title: str,
    subtitle: str,
    captions: list[str],
    legend_labels: Sequence[str],
    preset: str,
    country: str | None,
) -> PanelFigure:
    rows, cols = adaptive_grid(len(captions), ms.make_frame(ctx.polygon, ctx.extent).ratio)
    return new_panels(
        ctx.polygon,
        iso=iso,
        variable=title,
        captions=captions,
        n_rows=rows,
        n_cols=cols,
        subtitle=subtitle,
        total_text=None,
        source="Boundaries: GADM 4.1, illustrative · diagnostic figure, not for the thesis",
        neighbours=ctx.neighbours,
        extent=ctx.extent,
        contiguous=False,
        country=country,
        preset=preset,
        bar="each",
        legend_labels=legend_labels,
    )


def aligned_sheet(
    ctx: MapContext,
    iso: str,
    key: str,
    title: str,
    stems: Sequence[str],
    *,
    preset: str = "thesis",
    country: str | None = None,
) -> PanelFigure | None:
    """The sheet of the layers `stems` that exist for the country (None when none does)."""
    loaded = []
    for stem in stems:
        layer = BY_STEM[stem]
        path = aligned_path(iso, stem)
        if not path.is_file():
            logger.warning("%s: no %s, its panel is not drawn", iso, path.name)
            continue
        arr, extent = read_layer(path)
        if layer.per_km2:
            arr = per_km2(arr, extent)
        loaded.append((layer, arr, extent))
    if not loaded:
        return None
    infos = [None if lay.binary else _norm(arr, lay.kind, lay.tech) for lay, arr, _ in loaded]
    note = _scale_note([i for i in infos if i is not None])
    resolution = drawn_resolution(loaded[0][2], loaded[0][1].shape)
    sheet = _sheet(
        ctx,
        iso,
        f"Aligned layers · {title}",
        ms.format_subtitle("Diagnostic", resolution, note),
        [lay.caption for lay, _, _ in loaded],
        ["Water"] if any(lay.binary for lay, _, _ in loaded) else (),
        preset,
        country,
    )
    for i, ((layer, arr, extent), info) in enumerate(zip(loaded, infos, strict=True)):
        panel = sheet.panels[i]
        if layer.binary:
            rgba = np.zeros(arr.shape + (4,))
            rgba[arr == 1] = to_rgba(WATER_COLOUR)
            panel.draw_raster(rgba, extent)
            add_panel_classes(sheet, i, ["Water"], [WATER_COLOUR], "Lakes")
            continue
        image = panel.draw_raster(
            np.ma.masked_invalid(arr),
            extent,
            cmap=ms.colormap_for(layer.kind, layer.tech),
            norm=info.norm,
        )
        add_panel_colorbar(sheet, image, layer.label, info.extend, i)
    sheet.meta["status"] = STATUS
    sheet.meta["data_source"] = "F2a aligned layers"
    sheet.meta["scale_mode"] = "percentile"
    sheet.meta["scale_scope"] = "per_country"
    return sheet


def land_cover_map(
    ctx: MapContext, iso: str, *, preset: str = "thesis", country: str | None = None
) -> ms.MapFigure | None:
    """The land cover as classes: the colours of the ESA product, the legend lists the classes that the country has."""
    path = aligned_path(iso, LAND_COVER_STEM)
    if not path.is_file():
        logger.warning("%s: no %s, the land cover map is not drawn", iso, path.name)
        return None
    arr, extent = read_layer(path)
    present = [c for c in LAND_COVER if (arr == c).any()]
    if not present:
        return None
    spec = ms.ClassedLegend(
        title="Land cover (ESA WorldCover)",
        labels=tuple(LAND_COVER[c][0] for c in present),
        colours=tuple(to_rgba(LAND_COVER[c][1]) for c in present),
    )
    side, below = ms.legend_space(spec)
    canvas = ms.new_map(
        ctx.polygon,
        iso=iso,
        technology="",
        variable="Land cover",
        subtitle=ms.format_subtitle("Diagnostic", drawn_resolution(extent, arr.shape)),
        neighbours=ctx.neighbours,
        extent=ctx.extent,
        contiguous=False,
        country=country,
        preset=preset,
        legend_side_mm=side,
        legend_below_mm=below,
        source="Boundaries: GADM 4.1, illustrative · diagnostic figure, not for the thesis",
    )
    rgba = np.zeros(arr.shape + (4,))
    for code in present:
        rgba[arr == code] = to_rgba(LAND_COVER[code][1])
    canvas.draw_raster(rgba, extent)
    ms.draw_classed_legend(canvas, spec)
    canvas.meta.update({"status": STATUS, "data_source": "F2a aligned land cover"})
    return canvas


def hazard_means(hazard: pd.DataFrame) -> pd.DataFrame:
    """The mean over the members of each hazard indicator and of its change against the reference, per cell."""
    h = hazard.copy()
    h["tx35_change"] = h["tx35_days"] - h["tx35_days_ref"]
    h["rx5day_change"] = h["rx5day_mm"] - h["rx5day_mm_ref"]
    cols = [c for c, *_ in HAZARD_PANELS]
    return h.groupby("cell_id", observed=True)[cols].mean().reset_index()


def hazard_sheet(
    ctx: MapContext,
    iso: str,
    hazard: pd.DataFrame,
    *,
    preset: str = "thesis",
    country: str | None = None,
) -> PanelFigure:
    """The six hazard indicators of the context of F4 (the mean over the hazard members), each on its own scale."""
    from geofrea.viz.context import lattice_of, to_grid

    means = hazard_means(hazard)
    lattice = lattice_of(means["cell_id"].to_numpy())
    extent = lattice.extent
    grids = {
        c: to_grid(means["cell_id"].to_numpy(), means[c].to_numpy(), lattice)
        for c, *_ in HAZARD_PANELS
    }
    infos = {
        c: (
            ms.resolve_scale(grids[c][np.isfinite(grids[c])], ms.default_scale(kind, tech))
            if np.isfinite(grids[c]).any()
            else None
        )
        for c, _, _, kind, tech in HAZARD_PANELS
    }
    note = _scale_note([i for i in infos.values() if i is not None])
    n_members = int(hazard["member"].nunique())
    sheet = _sheet(
        ctx,
        iso,
        "Hazard context",
        ms.format_subtitle(
            "Diagnostic",
            f"mean of {n_members} members",
            "context only, no hazard enters a loss function",
            "values of the native grid of the hazard data, copied to the 0.05° cells",
            note,
        ),
        [caption for _, caption, *_ in HAZARD_PANELS],
        (),
        preset,
        country,
    )
    for i, (column, _caption, label, kind, tech) in enumerate(HAZARD_PANELS):
        info = infos[column]
        panel = sheet.panels[i]
        image = panel.draw_raster(
            np.ma.masked_invalid(grids[column]),
            extent,
            cmap=ms.colormap_for(kind, tech),
            norm=info.norm if info else None,
        )
        add_panel_colorbar(
            sheet,
            image,
            label,
            info.extend if info else "neither",
            i,
            meaning=HAZARD_MEANING.get(column),
        )
    sheet.meta["status"] = STATUS
    sheet.meta["data_source"] = "F4 hazard_context, mean over members"
    return sheet


def cost_driver_map(
    ctx: MapContext,
    iso: str,
    raster: Path,
    variable: str,
    *,
    preset: str = "thesis",
    country: str | None = None,
) -> ms.MapFigure:
    """A distance raster of F2b (km, uncapped) as a diagnostic map."""
    arr, extent = read_layer(raster)
    canvas = ms.raster_map(
        arr,
        extent,
        ctx.polygon,
        iso=iso,
        technology="",
        variable=variable,
        label="Distance (km)",
        kind="distance",
        subtitle=ms.format_subtitle("Diagnostic", "uncapped"),
        resolution=drawn_resolution(extent, arr.shape),
        neighbours=ctx.neighbours,
        extent=ctx.extent,
        contiguous=False,
        country=country,
        preset=preset,
    )
    canvas.meta.update({"status": STATUS, "data_source": "F2b siting layers"})
    return canvas


def _name(iso: str, phase: str, variable, tech=None, scenario=None, climate=None) -> str:
    return ms.figure_filename(iso, phase, variable, tech, scenario, climate)


def aligned_name(iso: str, key: str) -> str:
    return _name(iso, "F2a", ["aligned-layers", key])


def land_cover_name(iso: str) -> str:
    return _name(iso, "F2a", "land-cover")


def hazard_name(iso: str) -> str:
    return _name(iso, "F4", "hazard-context")


def cost_driver_name(iso: str, what: str) -> str:
    return _name(iso, "F2b", ["distance", what])
