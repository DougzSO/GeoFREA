"""One cartographic style for every GeoFREA map (COMMANDS 56 and 66): `MapFigure`, the single module of figure.

A fixed grid of layout, the same for every country: header (title and subtitle at the left, eight-point compass rose at the right),
map, legend (colour bar or patches; right of a tall map, below a wide one) and footer (scale bar, box of totals, source). Presets
(`thesis`, `article_single`, `article_double`, `slide`) fix the width in mm and the fonts in pt. Neighbours in light grey, geographic
aspect, extent from the country geometry, PNG at 300 dpi.

Nothing here computes a result. The modules of the phases call it; none draws a map on its own.

Everything is laid out in millimetres on a figure whose size is exact: an overlay axes covers the figure with 1 unit = 1 mm, so the
fonts (pt) and the furniture (compass, scale bar, text box) have their true print size and their boxes can be tested.

Credit: the 8-triangle compass rose and the alternating-segment scale bar follow the logic of `scripts/article_map_utils.py`
(`compass`, `scale_bar`) of the craei-brazil repository (same author), redrawn here in millimetres instead of degrees.
"""

from __future__ import annotations

import functools
import hashlib
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import ticker
from matplotlib.colors import (
    Colormap,
    LinearSegmentedColormap,
    LogNorm,
    Normalize,
    PowerNorm,
    to_hex,
    to_rgb,
)
from matplotlib.figure import Figure
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.patches import Rectangle

from geofrea.core.geo_utils import get_contiguous_mainland_gdf
from geofrea.core.geodesy import wgs84_km_per_degree
from geofrea.viz import display

Extent = tuple[float, float, float, float]  # (west, east, south, north) in degrees
BoxMm = tuple[
    float, float, float, float
]  # (x0, y0, x1, y1) in millimetres from the lower left of the figure

# ------------------------------------------------------------------------------------------------------------------------- constants

DPI = 300
EXTENT_MARGIN = 0.03
PT_MM = 25.4 / 72.0
MAX_HEIGHT_MM = 230.0

FONT_FAMILY = "DejaVu Sans"


@dataclass(frozen=True)
class Preset:
    """A destination of the figure: its width in millimetres and the fonts in points at that print size."""

    name: str
    width_mm: float
    title_pt: float
    label_pt: float
    legend_pt: float
    footer_pt: float
    compass_mm: float


PRESETS: dict[str, Preset] = {
    "thesis": Preset("thesis", 190.0, 10.0, 8.0, 8.0, 6.5, 10.0),
    "article_single": Preset("article_single", 90.0, 8.0, 6.5, 6.5, 5.5, 8.0),
    "article_double": Preset("article_double", 180.0, 9.0, 7.0, 7.0, 6.0, 9.0),
    "slide": Preset("slide", 254.0, 16.0, 12.0, 12.0, 9.0, 14.0),
}
THESIS = PRESETS["thesis"]
FULL_WIDTH_MM = THESIS.width_mm
HALF_WIDTH_MM = PRESETS["article_single"].width_mm
TITLE_PT, LABEL_PT, LEGEND_PT = THESIS.title_pt, THESIS.label_pt, THESIS.legend_pt
COMPASS_MM = THESIS.compass_mm


def get_preset(preset: str | Preset | None) -> Preset:
    """The preset by name (`thesis`, `article_single`, `article_double`, `slide`); a `Preset` is returned as is, None is `thesis`."""
    if preset is None:
        return THESIS
    if isinstance(preset, Preset):
        return preset
    try:
        return PRESETS[preset]
    except KeyError:
        raise ValueError(f"unknown preset {preset!r}; one of {sorted(PRESETS)}") from None


NEIGHBOUR_COLOUR = "#e3e3e3"
SEA_COLOUR = "white"
OUTLINE_COLOUR = "#222222"
NO_DATA_LABEL = "no potential"
NO_DATA_COLOUR = (
    "#bdbdbd"  # "no potential": a medium grey that is neither the neighbours (#ececec) nor the sea
)

SKEW_LIMIT = 20.0  # P98 / P50 above this: logarithmic or power norm
CLIP_PERCENTILES = (2.0, 98.0)

LEFT_MM, RIGHT_MM, BOTTOM_MM = 14.0, 3.0, 8.0
LEGEND_SIDE_MM, LEGEND_BELOW_MM = 26.0, 15.5
COLORBAR_MM = 3.5
PAD_MM = 2.0  # clear space around a furniture element
FOOTER_GAP_MM = 3.0  # horizontal gap between the elements of a footer row


def _rc(preset: Preset) -> dict:
    return {
        "font.family": FONT_FAMILY,
        "font.size": preset.label_pt,
        "axes.titlesize": preset.title_pt,
        "axes.labelsize": preset.label_pt,
        "xtick.labelsize": preset.label_pt,
        "ytick.labelsize": preset.label_pt,
        "legend.fontsize": preset.legend_pt,
        "axes.linewidth": 0.4,
        "xtick.major.width": 0.4,
        "ytick.major.width": 0.4,
        "xtick.major.size": 2.0,
        "ytick.major.size": 2.0,
        "savefig.dpi": DPI,
        "figure.dpi": DPI,
    }


_RC = _rc(THESIS)


# ------------------------------------------------------------------------------------------------------------------- extent and aspect


def _as_geometry(geometry):
    """A shapely geometry in lon/lat from a GeoDataFrame, a GeoSeries or a shapely geometry."""
    if hasattr(geometry, "union_all"):
        return geometry.union_all()
    return geometry


def contiguous_geometry(geometry):
    """The geometry reduced to the contiguous territory (METHODOLOGY 15.2.0): the largest polygon plus those touching it or within 1 km.

    Islands farther away (Trindade, Fernando de Noronha) are dropped, so they never stretch the map. The geometry is in lon/lat.
    """
    import geopandas as gpd

    geom = _as_geometry(geometry)
    gdf = gpd.GeoDataFrame(geometry=[geom], crs="EPSG:4326")
    return get_contiguous_mainland_gdf(gdf).geometry.iloc[0]


def country_extent(geometry, margin: float = EXTENT_MARGIN, contiguous: bool = True) -> Extent:
    """(west, east, south, north) of the country, enlarged by `margin` of its width and height on each side.

    With `contiguous` (the default) the far islands are discarded first, as in the country mask of the pipeline.
    """
    geom = contiguous_geometry(geometry) if contiguous else _as_geometry(geometry)
    west, south, east, north = geom.bounds
    dx, dy = (east - west) * margin, (north - south) * margin
    return (west - dx, east + dx, south - dy, north + dy)


def geographic_aspect(extent: Extent) -> float:
    """The `set_aspect` value of a lon/lat axes: 1 / cos(central latitude), so that a degree of longitude is drawn as long as it is."""
    return 1.0 / math.cos(math.radians(0.5 * (extent[2] + extent[3])))


def map_height_over_width(extent: Extent) -> float:
    """Height over width of the map on paper for `extent` with the geographic aspect."""
    west, east, south, north = extent
    return (north - south) * 1.0 / ((east - west) * math.cos(math.radians(0.5 * (south + north))))


def legend_position(extent: Extent) -> str:
    """`right` for a tall country (the map is higher than wide), `below` for a wide one."""
    return "right" if map_height_over_width(extent) > 1.0 else "below"


def format_degrees(value: float, axis: str) -> str:
    """40°S, 50°W, 0° (latitude `lat`, longitude `lon`); half degrees keep one decimal."""
    v = round(float(value), 6)
    mag = abs(v)
    text = f"{mag:.0f}" if abs(mag - round(mag)) < 1e-6 else f"{mag:.1f}"
    if abs(v) < 1e-9:
        return "0°"
    hemisphere = ("N" if v > 0 else "S") if axis == "lat" else ("E" if v > 0 else "W")
    return f"{text}°{hemisphere}"


# ------------------------------------------------------------------------------------------------------------ projection and clipping (T-06, T-08)
# The map is drawn in a Lambert azimuthal equal-area projection centred on the country (only for drawing: the areas of the analysis are
# computed on the sphere, elsewhere). A raster is copied cell by cell into the projected frame (nearest neighbour, nothing interpolated)
# and clipped by the country polygon, so the coast and the border are the vector line and never the staircase of the cells.

NEIGHBOUR_BUFFER_DEG = (
    2.5  # the locator inset (not the map) shows the neighbours within this distance of the border
)
BORDER_GAP_M = 8_000.0  # the gap between the borders of two sources that is closed with the colour of the neighbours
RENDER_DPI = (
    200  # resolution of the reprojected raster on paper; the cells are copied, never smoothed
)
GRATICULE_COLOUR = "#b0b0b0"


def laea_crs(lon0: float, lat0: float):
    """The Lambert azimuthal equal-area CRS centred on (lon0, lat0), in metres."""
    from pyproj import CRS

    return CRS.from_proj4(
        f"+proj=laea +lat_0={lat0:.6f} +lon_0={lon0:.6f} +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )


@dataclass(frozen=True)
class MapFrame:
    """The projection of one map: the CRS, the two transformers, the bounds of the drawing in metres and the country in the projection."""

    crs: object
    forward: object  # lon/lat -> x, y
    inverse: object  # x, y -> lon/lat
    bounds: tuple[float, float, float, float]  # xmin, xmax, ymin, ymax in metres
    polygon: object  # the country, projected
    lonlat_extent: Extent  # west, east, south, north that contain the frame

    @property
    def width_m(self) -> float:
        return self.bounds[1] - self.bounds[0]

    @property
    def height_m(self) -> float:
        return self.bounds[3] - self.bounds[2]

    @property
    def ratio(self) -> float:
        """Height over width of the map on paper."""
        return self.height_m / self.width_m

    @property
    def width_km(self) -> float:
        return self.width_m / 1000.0

    def to_xy(self, lon, lat):
        """lon/lat (degrees) to metres in the frame."""
        return self.forward.transform(
            np.asarray(lon, dtype="float64"), np.asarray(lat, dtype="float64")
        )

    def project_geometry(self, geometry):
        """A shapely geometry in lon/lat in the projection of the frame (edges densified first)."""
        import shapely
        from shapely.ops import transform

        return transform(self.forward.transform, shapely.segmentize(geometry, 0.1))


def _box_edge(west: float, east: float, south: float, north: float, n: int = 60):
    xs = np.concatenate(
        [np.linspace(west, east, n), np.full(n, east), np.linspace(east, west, n), np.full(n, west)]
    )
    ys = np.concatenate(
        [
            np.full(n, south),
            np.linspace(south, north, n),
            np.full(n, north),
            np.linspace(north, south, n),
        ]
    )
    return xs, ys


_FRAMES: dict = {}  # the frames already made, by the polygon and the extent: a country's polygon has hundreds of thousands of vertices


def make_frame(polygon, extent: Extent | None = None, margin: float = EXTENT_MARGIN) -> MapFrame:
    key = (hashlib.blake2b(polygon.wkb, digest_size=16).digest(), extent, margin)
    if key not in _FRAMES:
        if len(_FRAMES) >= 8:
            _FRAMES.pop(next(iter(_FRAMES)))
        _FRAMES[key] = _make_frame(polygon, extent, margin)
    return _FRAMES[key]


def _make_frame(polygon, extent: Extent | None, margin: float) -> MapFrame:
    """The frame of a country (lon/lat polygon): LAEA centred on its centroid, bounds of the projected polygon plus `margin` of its width
    and height on each side, or the bounds of the lon/lat `extent` (edges sampled) when it is given."""
    from pyproj import Transformer

    centre = polygon.centroid
    crs = laea_crs(centre.x, centre.y)
    forward = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    inverse = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    frame = MapFrame(crs, forward, inverse, (0.0, 1.0, 0.0, 1.0), polygon, (0, 0, 0, 0))
    poly_xy = frame.project_geometry(polygon)
    if extent is None:
        xmin, ymin, xmax, ymax = poly_xy.bounds
        dx, dy = (xmax - xmin) * margin, (ymax - ymin) * margin
        bounds = (xmin - dx, xmax + dx, ymin - dy, ymax + dy)
    else:
        x, y = forward.transform(*_box_edge(*extent))
        bounds = (float(x.min()), float(x.max()), float(y.min()), float(y.max()))
    bx, by = _box_edge_xy(bounds)
    lon, lat = inverse.transform(bx, by)
    lonlat = (float(lon.min()), float(lon.max()), float(lat.min()), float(lat.max()))
    return MapFrame(crs, forward, inverse, bounds, poly_xy, lonlat)


def _box_edge_xy(bounds, n: int = 60):
    xmin, xmax, ymin, ymax = bounds
    return _box_edge(xmin, xmax, ymin, ymax, n)


def geometry_path(geometry):
    """A matplotlib Path (with holes) of a Polygon or MultiPolygon, to clip with."""
    from matplotlib.path import Path as MplPath

    polygons = [geometry] if geometry.geom_type == "Polygon" else list(geometry.geoms)
    vertices, codes = [], []
    for polygon in polygons:
        for ring in (polygon.exterior, *polygon.interiors):
            xy = np.asarray(ring.coords)
            vertices.append(xy)
            codes += [MplPath.MOVETO] + [MplPath.LINETO] * (len(xy) - 2) + [MplPath.CLOSEPOLY]
    return MplPath(np.concatenate(vertices), codes)


def reproject_nearest(
    data: np.ndarray, extent_grid: Extent, frame: MapFrame, pixel_m: float
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """The lon/lat grid `data` (row 0 north, `extent_grid` = west, east, south, north; 2-D values or 3-D RGBA) copied into the projected
    frame: each pixel of the frame takes the value of the cell that contains its centre. Nothing is interpolated.

    Returns the array (NaN, or transparent for RGBA, where the frame is outside the grid) and its extent in metres.
    """
    xmin, xmax, ymin, ymax = frame.bounds
    nx, ny = (
        max(math.ceil((xmax - xmin) / pixel_m), 1),
        max(math.ceil((ymax - ymin) / pixel_m), 1),
    )
    xs = xmin + (np.arange(nx) + 0.5) * pixel_m
    ys = ymax - (np.arange(ny) + 0.5) * pixel_m
    gx, gy = np.meshgrid(xs, ys)
    lon, lat = frame.inverse.transform(gx.ravel(), gy.ravel())
    west, east, south, north = extent_grid
    gny, gnx = data.shape[:2]
    cols = np.floor((lon - west) / (east - west) * gnx).astype(np.int64)
    rows = np.floor((north - lat) / (north - south) * gny).astype(np.int64)
    inside = (cols >= 0) & (cols < gnx) & (rows >= 0) & (rows < gny)
    if data.ndim == 3:
        out = np.zeros((ny * nx, data.shape[2]), dtype="float64")
        out[inside] = data[rows[inside], cols[inside]]
        out = out.reshape(ny, nx, data.shape[2])
    else:
        values = np.ma.filled(np.ma.asarray(data, dtype="float64"), np.nan)
        out = np.full(ny * nx, np.nan)
        out[inside] = values[rows[inside], cols[inside]]
        out = out.reshape(ny, nx)
    return out, (xmin, xmin + nx * pixel_m, ymax - ny * pixel_m, ymax)


def resolution_note(
    cell_deg: float | None = None, native_m: float | None = None, display_deg: float | None = None
) -> str:
    """What the subtitle says about the resolution of the data drawn: `0.05° analysis grid` for the results of the analysis, `native ~30 m`
    for a descriptive layer drawn at the resolution it has, `0.01° display layer` for a finer layer made only to be drawn."""
    if sum(x is not None for x in (cell_deg, native_m, display_deg)) != 1:
        raise ValueError(
            "give one of the cell of the analysis grid, the native resolution or the display layer"
        )
    if cell_deg is not None:
        return f"{cell_deg:g}° analysis grid"
    if display_deg is not None:
        return f"{display_deg:g}° display layer"
    return f"native resolution ~{native_m:g} m"


def smoothing_note(source: str | None = None) -> str:
    """What the subtitle of a smoothed map says: the smoothing and the resolution of the data it came from."""
    return f"display smoothing (source: {source})" if source else "display smoothing"


# --------------------------------------------------------------------------------------------------------------- colour and normalisation
# The semantics of colour and of scale live here and nowhere else: variable -> (colormap, scale, scope). No module of a phase chooses a
# colormap or colour limits by itself.

SOLAR, WIND = "solar", "wind"
TRUNCATE_FROM = 0.15  # the sequential maps of the technologies start here, so that the lowest value is not the white of the sea

TECH_CMAPS = {
    SOLAR: "YlOrBr",
    WIND: "GnBu",
}  # warm for the sun, cool for the wind; viridis is for neither
TECH_KINDS = ("potential", "energy", "density", "capacity_factor", "eligible_share")
PLAIN_CMAPS = {  # kinds that do not depend on the technology
    "excluded_share": "Reds",  # diagnostic figures only, never beside a map coloured by technology
    "delta": "RdBu",  # climate change of the solar resource (centred on 0 as percent, on 1 as ratio)
    "delta_alt": "BrBG",  # climate change of the wind resource
    "temperature": "YlOrRd",  # change of temperature (sequential)
    # the aligned layers of F2a (diagnostic figures): one colour map for each kind of layer, so that a colour means one thing in a sheet
    "distance": "viridis",  # distances to the river, the road, the grid, the lakes (km)
    "elevation": "cividis",
    "slope": "magma_r",
    "population": "Purples",
    "water": "Blues",
    "weibull_k": "PuRd",
    "air_density": "BuPu",
    "frequency": "PuBu",  # a share of days
    # the maps of F6 and F7 (diagnostic): the cost, the regret, the satisficing share and a count
    "lcoe": "viridis_r",
    "regret": "magma_r",
    "satisficing": "viridis",
    "count": "Reds",
}
TRUNCATED_PLAIN = {
    "population",
    "water",
    "weibull_k",
    "air_density",
    "frequency",
}  # sequential maps that start at white: cut from 15% like the technologies
COLORMAPS = {**{k: None for k in TECH_KINDS}, **PLAIN_CMAPS}

# Qualitative classes (the dominant exclusion E1-E6): the Okabe-Ito colours without green and without the black, and a neutral grey for "none".
CLASS_COLOURS = ("#E69F00", "#56B4E9", "#0072B2", "#CC79A7", "#F0E442", "#D55E00")
CLASS_NONE_COLOUR = "#7f7f7f"

MIN_DELTA_E = 8.0  # two colours with different meanings must differ at least this much (CIE76), also under colour-blind simulation
MIN_DELTA_E_CMAP = 5.0  # a flat colour against the colours a continuous map passes through


@functools.cache
def _truncated(name: str, start: float) -> Colormap:
    base = matplotlib.colormaps[name]
    cmap = LinearSegmentedColormap.from_list(
        f"{name}_from{round(start * 100):d}", base(np.linspace(start, 1.0, 256))
    )
    matplotlib.colormaps.register(
        cmap, force=True
    )  # by name, so that a figure can look it up again
    return cmap


def family_of(tech: str) -> str:
    """The family of colours of a technology: a variant of a technology takes the family of its name."""
    return WIND if WIND in tech else SOLAR


def colormap_for(kind: str, tech: str | None = None) -> Colormap:
    """The colormap of a kind of variable.

    The kinds in `TECH_KINDS` (`potential`, `energy`, `density`, `capacity_factor`, `eligible_share`) take the family of the technology
    (`solar`: YlOrBr, `wind`: GnBu, truncated to start at 15%); the others do not depend on it (`excluded_share`: Reds, `delta`: RdBu,
    `delta_alt`: BrBG, `temperature`: YlOrRd).
    """
    if kind in TECH_KINDS:
        if tech not in TECH_CMAPS:
            raise ValueError(f"the kind {kind!r} needs a technology, one of {sorted(TECH_CMAPS)}")
        return _truncated(TECH_CMAPS[tech], TRUNCATE_FROM)
    if kind not in PLAIN_CMAPS:
        raise ValueError(f"unknown kind {kind!r}")
    if kind in TRUNCATED_PLAIN:
        return _truncated(PLAIN_CMAPS[kind], TRUNCATE_FROM)
    return matplotlib.colormaps[PLAIN_CMAPS[kind]]


def class_colours(n: int) -> list[str]:
    """The first `n` qualitative class colours (colour-blind safe, no green)."""
    if not 0 < n <= len(CLASS_COLOURS):
        raise ValueError(f"at most {len(CLASS_COLOURS)} classes have a colour, asked {n}")
    return list(CLASS_COLOURS[:n])


# --- colour-blind simulation (Machado, Oliveira and Fernandes 2009, severity 1) and CIE76 distance

_CVD = {
    "deuteranopia": np.array(
        [
            [0.367322, 0.860646, -0.227968],
            [0.280085, 0.672501, 0.047413],
            [-0.011820, 0.042940, 0.968881],
        ]
    ),
    "protanopia": np.array(
        [
            [0.152286, 1.052583, -0.204868],
            [0.114503, 0.786281, 0.099216],
            [-0.003882, -0.048116, 1.051998],
        ]
    ),
}
VISIONS = ("normal", *_CVD)


def _to_linear(rgb: np.ndarray) -> np.ndarray:
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def _from_linear(lin: np.ndarray) -> np.ndarray:
    lin = np.clip(lin, 0.0, 1.0)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)


def simulate_vision(colour, vision: str) -> tuple[float, float, float]:
    """The sRGB colour as seen with `vision` (`normal`, `deuteranopia` or `protanopia`)."""
    rgb = np.asarray(to_rgb(colour), dtype="float64")
    if vision == "normal":
        return tuple(float(x) for x in rgb)
    out = _from_linear(_CVD[vision] @ _to_linear(rgb))
    return tuple(float(x) for x in out)


def _lab(rgb) -> np.ndarray:
    lin = _to_linear(np.asarray(rgb, dtype="float64"))
    xyz = (
        np.array(
            [
                [0.4124564, 0.3575761, 0.1804375],
                [0.2126729, 0.7151522, 0.0721750],
                [0.0193339, 0.1191920, 0.9503041],
            ]
        )
        @ lin
    ) / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def delta_e(colour_a, colour_b, vision: str = "normal") -> float:
    """CIE76 distance between two colours as seen with `vision`."""
    a = _lab(simulate_vision(colour_a, vision))
    b = _lab(simulate_vision(colour_b, vision))
    return float(np.linalg.norm(a - b))


def colour_conflicts(colours: dict[str, str], cmaps: dict[str, str] | None = None) -> list[str]:
    """What is wrong with the colours of a figure: `colours` maps a flat colour to its meaning and `cmaps` a colormap name to its meaning.

    A conflict is a flat colour that is the same as another with a different meaning, two colormaps with different meanings that
    are the same one, or two meanings whose colours differ by less than `MIN_DELTA_E` for a normal eye, for deuteranopia or for
    protanopia (flat against the colours a colormap passes through: `MIN_DELTA_E_CMAP`).
    """
    problems: list[str] = []
    flat = [(to_hex(c).lower(), m) for c, m in colours.items()]
    for i, (ca, ma) in enumerate(flat):
        for cb, mb in flat[i + 1 :]:
            if ma == mb:
                continue
            if ca == cb:
                problems.append(f"{ca} means {ma!r} and {mb!r}")
                continue
            for vision in VISIONS:
                d = delta_e(ca, cb, vision)
                if d < MIN_DELTA_E:
                    problems.append(
                        f"{ma!r} ({ca}) and {mb!r} ({cb}) differ by {d:.1f} for {vision}"
                    )
                    break
    maps = list((cmaps or {}).items())
    for i, (na, ma) in enumerate(maps):
        for nb, mb in maps[i + 1 :]:
            if na == nb and ma != mb:
                problems.append(f"the colormap {na!r} means {ma!r} and {mb!r}")
    for colour, meaning in flat:
        for name, cmap_meaning in maps:
            if cmap_meaning == meaning:
                continue
            cm = matplotlib.colormaps[name]
            for v in np.linspace(0.0, 1.0, 11):
                for vision in VISIONS:
                    if delta_e(colour, cm(v), vision) < MIN_DELTA_E_CMAP:
                        problems.append(
                            f"{meaning!r} ({to_hex(colour)}) is almost the colour of {cmap_meaning!r} ({name} at {v:.1f}) for {vision}"
                        )
                        break
                else:
                    continue
                break
    return problems


# --- scales (T-03)

SCALE_MODES = ("fixed", "percentile", "shared")
SCALE_SCOPES = ("per_country", "shared_across_countries")


@dataclass(frozen=True)
class ScaleSpec:
    """How the colour limits of a variable are chosen.

    `fixed`: the physical limits in `limits`. `percentile`: the percentiles of the values drawn (`percentiles`). `shared`: the limits
    computed over the values of every map that must be compared (`shared_limits`). `scope` says whether the limits are those of one
    country or are shared across countries; it goes to the PNG metadata and, when a clip is drawn, to the subtitle.
    """

    mode: str
    limits: tuple[float, float] | None = None
    percentiles: tuple[float, float] = CLIP_PERCENTILES
    scope: str = "per_country"
    diverging: bool = False
    center: float = 0.0

    def __post_init__(self) -> None:
        if self.mode not in SCALE_MODES:
            raise ValueError(f"scale mode {self.mode!r} is not one of {SCALE_MODES}")
        if self.scope not in SCALE_SCOPES:
            raise ValueError(f"scale scope {self.scope!r} is not one of {SCALE_SCOPES}")
        if self.mode == "fixed" and (self.limits is None or not self.limits[0] < self.limits[1]):
            raise ValueError("a fixed scale needs limits (low, high) with low < high")


FIXED_CF = {
    SOLAR: (0.10, 0.25),
    WIND: (0.0, 0.60),
}  # capacity factor, dimensionless, the same in every country


def default_scale(kind: str, tech: str | None = None) -> ScaleSpec:
    """The default scale of a kind of variable (spec v2, section 4): CF fixed per technology and the same in the three countries; shares
    fixed at 0-1; changes symmetric about the centre at percentiles of the data; densities at percentiles of each country."""
    if kind == "capacity_factor":
        if tech not in FIXED_CF:
            raise ValueError("the capacity factor needs a technology")
        return ScaleSpec("fixed", FIXED_CF[tech], scope="shared_across_countries")
    if kind in ("eligible_share", "excluded_share"):
        return ScaleSpec("fixed", (0.0, 1.0), scope="shared_across_countries")
    if kind.startswith("delta"):
        return ScaleSpec("percentile", diverging=True)
    return ScaleSpec("percentile")


@dataclass(frozen=True)
class NormInfo:
    """The norm of a continuous map and how it was chosen."""

    norm: Normalize
    extend: str  # colorbar extend: neither, min, max, both
    vmin: float
    vmax: float
    kind: str  # linear, log, power or diverging
    skew: float  # P98 / P50 (inf when the median is not positive)
    mode: str = "percentile"  # fixed, percentile or shared
    scope: str = "per_country"
    percentiles: tuple[float, float] = CLIP_PERCENTILES


def robust_norm(
    values,
    *,
    diverging: bool = False,
    center: float = 0.0,
    percentiles: tuple[float, float] = CLIP_PERCENTILES,
    skew_limit: float = SKEW_LIMIT,
) -> NormInfo:
    """Colour limits at the 2nd and 98th percentiles of the finite values; extend wherever values fall outside.

    Sequential: a logarithmic norm when the limits are positive and P98 / P50 exceeds `skew_limit`, a power norm (gamma 0.5) when it
    exceeds it with a lower limit that is not positive; linear otherwise. Diverging: symmetric about `center`, the half range being the
    larger of the two percentile distances.
    """
    arr = np.asarray(values, dtype="float64")
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        raise ValueError("no finite value to normalise")
    lo, hi = (float(x) for x in np.percentile(arr, percentiles))
    median = float(np.median(arr))
    if diverging:
        half = max(abs(lo - center), abs(hi - center)) or 1.0
        vmin, vmax = center - half, center + half
        return NormInfo(
            Normalize(vmin, vmax), _extend(arr, vmin, vmax), vmin, vmax, "diverging", math.nan
        )
    if hi <= lo:  # nearly constant: widen so that the norm is valid
        hi = lo + (abs(lo) * 1e-6 or 1e-6)
    skew = hi / median if median > 0 else math.inf
    extend = _extend(arr, lo, hi)
    if skew > skew_limit and lo > 0:
        return NormInfo(LogNorm(lo, hi), extend, lo, hi, "log", skew)
    if skew > skew_limit:
        return NormInfo(PowerNorm(0.5, lo, hi), extend, lo, hi, "power", skew)
    return NormInfo(Normalize(lo, hi), extend, lo, hi, "linear", skew)


def _extend(arr: np.ndarray, vmin: float, vmax: float) -> str:
    """The colour bar `extend` that matches the data: an arrow where, and only where, values lie beyond the limits."""
    arr = arr[np.isfinite(arr)]
    below, above = bool((arr < vmin).any()), bool((arr > vmax).any())
    return "both" if below and above else "min" if below else "max" if above else "neither"


def resolve_scale(
    values, spec: ScaleSpec, shared_limits: tuple[float, float] | None = None
) -> NormInfo:
    """The norm of `values` under `spec`; `extend` is always the one the data need against the limits that were used.

    `fixed` uses `spec.limits`. `percentile` uses the percentiles of `values`, unless the scope is `shared_across_countries` and
    `shared_limits` were given (then they rule and the mode is `shared`). `shared` needs `shared_limits` (or `spec.limits`).
    """
    arr = np.asarray(values, dtype="float64")
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        raise ValueError("no finite value to normalise")
    limits = None
    mode = spec.mode
    if mode == "fixed":
        limits = spec.limits
    elif mode == "shared" or (
        spec.scope == "shared_across_countries" and shared_limits is not None
    ):
        limits = shared_limits or spec.limits
        if limits is None:
            raise ValueError(
                "a shared scale needs the limits computed over the maps that are compared"
            )
        mode = "shared"
    if limits is None:
        info = robust_norm(
            arr, diverging=spec.diverging, center=spec.center, percentiles=spec.percentiles
        )
        return replace(info, mode="percentile", scope=spec.scope, percentiles=spec.percentiles)
    lo, hi = float(limits[0]), float(limits[1])
    return NormInfo(
        Normalize(lo, hi), _extend(arr, lo, hi), lo, hi, "linear", math.nan, mode, spec.scope
    )


def shared_limits(arrays: Sequence, spec: ScaleSpec) -> tuple[float, float]:
    """Limits for maps that are compared (scenarios, SSPs, countries): the percentiles of all their values together
    (symmetric about the centre for a diverging variable), so that the same colour means the same value in every map."""
    pooled = np.concatenate([np.asarray(a, dtype="float64").ravel() for a in arrays])
    info = robust_norm(
        pooled, diverging=spec.diverging, center=spec.center, percentiles=spec.percentiles
    )
    return info.vmin, info.vmax


def _fmt(x: float) -> str:
    return f"{x:.3g}"


def _ordinal(p: float) -> str:
    n = f"{p:g}"
    if "." in n or n.endswith(("11", "12", "13")):
        return f"{n}th"
    return n + {"1": "st", "2": "nd", "3": "rd"}.get(n[-1], "th")


def clip_note(info: NormInfo, unit: str = "") -> str:
    """What the subtitle must say when the colour scale cuts values (empty when nothing is cut): `Scale: 2nd–98th percentile`,
    `Scale: fixed` or `Scale: shared`. The numeric limits, the scope and the norm are in the metadata of the PNG (`scale_meta`)."""
    if info.extend == "neither":
        return ""
    if info.mode == "fixed":
        return "Scale: fixed"
    if info.mode == "shared":
        return "Scale: shared"
    lo, hi = info.percentiles
    return f"Scale: {_ordinal(lo)}–{_ordinal(hi)} percentile"


def format_subtitle(*parts: str | None) -> str:
    """The subtitle `Scenario · Climate (· more)`: the parts that are not empty, joined by ` · `."""
    return " · ".join(p for p in parts if p)


# ---------------------------------------------------------------------------------------------------------------------------- layout
# The figure is a fixed grid, from the top: header (title and subtitle at the left, compass rose at the right), map with its legend
# (colour bar or patches) to the right of a tall map and below a wide one, footer (scale bar at the left, box of totals in the middle or at
# the right, source at the right). No element is placed by looking for an empty corner: the same grid serves every country.

DEFAULT_SOURCE = "Boundaries: GADM 4.1, illustrative"


def _text_width_mm(text: str, pt: float, bold: bool = False) -> float:
    """Estimated width of `text` (the widest line) in mm: the average advance of the sans family; the tests measure the real boxes."""
    em = 0.68 if bold else 0.62
    return max((len(line) for line in text.split("\n")), default=0) * pt * PT_MM * em


def _wrap(text: str, width_mm: float, pt: float, bold: bool = False) -> list[str]:
    """Words of `text` on lines no wider than `width_mm` by the same width estimate as the furniture."""
    lines, current = [], ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if current and _text_width_mm(trial, pt, bold) > width_mm:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines or [""]


def wrap_total_text(text: str, width_mm: float, pt: float) -> str:
    """The text of the box of totals on lines no wider than `width_mm`: breaks first at the ` · ` between the figures, then at spaces."""
    out: list[str] = []
    for line in text.split("\n"):
        current = ""
        for part in line.split(" · "):
            trial = f"{current} · {part}" if current else part
            if current and _text_width_mm(trial, pt) > width_mm:
                out.append(current)
                current = part
            else:
                current = trial
        if current:
            out.extend(_wrap(current, width_mm, pt))
    return "\n".join(out)


def compass_size_mm(preset: Preset = THESIS) -> tuple[float, float]:
    """Width and height of the box of the compass rose (arms, the N above and the padding)."""
    return (
        preset.compass_mm + 2 * PAD_MM,
        preset.compass_mm + 0.6 + preset.legend_pt * PT_MM * 1.3 + 2 * PAD_MM,
    )


def header_text(
    width_mm: float,
    title: str,
    subtitle: str,
    preset: Preset = THESIS,
    reserve_mm: float = 0.0,
) -> tuple[list[str], list[str], float]:
    """The title and subtitle wrapped to the room the compass rose leaves, and the height of the header that holds them and the rose."""
    room = width_mm - 2.0 - compass_size_mm(preset)[0] - 3.0 - reserve_mm
    title_lines = _wrap(title, room, preset.title_pt, bold=True)
    sub_lines = _wrap(subtitle, room, preset.label_pt) if subtitle else []
    text_h = (
        2.0
        + len(title_lines) * preset.title_pt * PT_MM * 1.35
        + len(sub_lines) * preset.label_pt * PT_MM * 1.35
        + 1.5
    )
    return title_lines, sub_lines, max(text_h, compass_size_mm(preset)[1] + 2.0)


HEADER_MM = header_text(FULL_WIDTH_MM, "T", "S")[2]  # the header of a one-line title and subtitle


@dataclass(frozen=True)
class Layout:
    """The figure in millimetres from the lower left corner."""

    width_mm: float
    height_mm: float
    map_box: BoxMm
    legend_box: BoxMm
    legend: str  # right or below
    header_box: BoxMm
    footer_mm: float  # height of the footer strip under everything
    no_data_box: BoxMm | None = None  # the legend entry of the part of the country without value


def fitted_width_mm(
    ratio: float,
    width_mm: float,
    side_mm: float,
    header_mm: float = HEADER_MM,
    footer_mm: float = 14.0,
    max_height_mm: float = MAX_HEIGHT_MM,
) -> float:
    """Width of the figure: `width_mm`, or less for a very tall country whose map is limited by the height of the sheet (the figure does
    not keep a wide empty band on each side of a narrow map). Never below 42% of `width_mm` and 80 mm, where the title and the footer still fit."""
    if ratio <= 1.0:
        return width_mm
    map_w = (max_height_mm - header_mm - BOTTOM_MM - footer_mm) / ratio
    needed = LEFT_MM + RIGHT_MM + side_mm + map_w
    return min(width_mm, max(needed, min(width_mm, max(0.42 * width_mm, 80.0))))


def compute_layout(
    extent: Extent | None,
    width_mm: float = FULL_WIDTH_MM,
    footer_mm: float = 0.0,
    max_height_mm: float = MAX_HEIGHT_MM,
    legend_side_mm: float | None = None,
    legend_below_mm: float | None = None,
    header_mm: float = HEADER_MM,
    ratio: float | None = None,
    no_data_mm: float = 0.0,
) -> Layout:
    """Figure size and boxes: the height follows the aspect of the map (`ratio`, or that of the lon/lat `extent`); the legend is to the right
    of a tall map, below a wide one.

    A very tall country is limited to `max_height_mm`: the map gets narrower and is centred. The colour bar has the height of the map
    (right) or 70% of its width (below); `no_data_mm` is the room that the entry "no potential" takes from the bar (its height on the right, its
    width below), and the entry gets `Layout.no_data_box`.
    """
    if ratio is None:
        ratio = map_height_over_width(extent)
    side = ratio > 1.0
    side_mm = (
        LEGEND_SIDE_MM if legend_side_mm is None else legend_side_mm
    )  # a classed legend needs more than a colour bar
    below_mm = LEGEND_BELOW_MM if legend_below_mm is None else legend_below_mm
    avail_w = width_mm - LEFT_MM - RIGHT_MM - (side_mm if side else 0.0)
    fixed_h = header_mm + BOTTOM_MM + footer_mm + (0.0 if side else below_mm)
    map_w = min(avail_w, (max_height_mm - fixed_h) / ratio)
    map_h = map_w * ratio
    height = fixed_h + map_h
    x0 = LEFT_MM + (avail_w - map_w) / 2.0
    y0 = BOTTOM_MM + footer_mm + (0.0 if side else below_mm)
    map_box = (x0, y0, x0 + map_w, y0 + map_h)
    no_data_box = None
    if side:
        bar_x = x0 + map_w + 4.0
        legend_box = (bar_x, y0 + no_data_mm, bar_x + COLORBAR_MM, y0 + map_h)
        if no_data_mm:
            no_data_box = (bar_x, y0, bar_x + side_mm - 4.0, y0 + no_data_mm - 1.5)
    else:
        bar_y = footer_mm + 9.0  # under the bar: its tick labels and its name
        bar_x0, bar_x1 = x0 + 0.15 * map_w, x0 + 0.85 * map_w
        if no_data_mm:
            bar_x1 = min(bar_x1, x0 + map_w - no_data_mm - 3.0)
            bar_x0 = min(bar_x0, bar_x1 - 0.35 * map_w)
            no_data_box = (x0 + map_w - no_data_mm, bar_y, x0 + map_w, bar_y + COLORBAR_MM)
        legend_box = (bar_x0, bar_y, bar_x1, bar_y + COLORBAR_MM)
    header_box = (0.0, height - header_mm, width_mm, height)
    return Layout(
        width_mm,
        height,
        map_box,
        legend_box,
        "right" if side else "below",
        header_box,
        footer_mm,
        no_data_box,
    )


# ------------------------------------------------------------------------------------------------------------------------ furniture


def nice_length_km(target_km: float) -> float:
    """The 1, 2 or 5 times a power of ten closest to `target_km` (closest in ratio, so it is never more than 1.6 times off)."""
    if target_km <= 0:
        raise ValueError("target length must be positive")
    exponent = math.floor(math.log10(target_km))
    candidates = [m * 10.0 ** (exponent + e) for e in (0, 1) for m in (1.0, 2.0, 5.0)]
    return min(candidates, key=lambda c: abs(math.log(c / target_km)))


def _scale_width_km(extent: Extent | None, width_km: float | None) -> float:
    """The width of the map in km: given (projected maps), or measured at the central latitude of the lon/lat `extent`."""
    if width_km is not None:
        return width_km
    _, lon_km = wgs84_km_per_degree(np.array([0.5 * (extent[2] + extent[3])]))
    return (extent[1] - extent[0]) * float(lon_km[0])


def scale_bar_length_km(
    extent: Extent | None, share: float = 0.20, width_km: float | None = None
) -> float:
    """Rounded length (1, 2 or 5 x 10^n km) closest to `share` of the map width (`width_km` in the projection of the map, or the width of
    the lon/lat `extent` at its central latitude)."""
    return nice_length_km(share * _scale_width_km(extent, width_km))


def _scale_bar_length_mm(
    extent: Extent | None, map_w_mm: float, width_km: float | None = None
) -> float:
    return (
        scale_bar_length_km(extent, width_km=width_km)
        / _scale_width_km(extent, width_km)
        * map_w_mm
    )


@dataclass(frozen=True)
class Furniture:
    """An element of the figure outside the map: its name, the box it occupies (padding included) and the strip it sits in."""

    name: str
    box: BoxMm
    where: str  # header or footer


def footer_item_sizes(
    extent: Extent | None,
    map_w_mm: float,
    total_text: str | None,
    source: str | None,
    preset: Preset = THESIS,
    width_km: float | None = None,
) -> dict[str, tuple[float, float]]:
    """Size in mm (padding included) of what the footer holds, in reading order: scale bar, box of totals, source."""
    pt = preset.legend_pt
    label = _text_width_mm(f"{scale_bar_length_km(extent, width_km=width_km):g} km", pt)
    sizes = {
        "scale_bar": (
            _scale_bar_length_mm(extent, map_w_mm, width_km)
            + _text_width_mm("0", pt) / 2.0
            + label / 2.0
            + 2 * PAD_MM,
            1.8 + 1.0 + pt * PT_MM + 2 * PAD_MM,
        )
    }
    if total_text:
        lines = total_text.split("\n")
        sizes["total"] = (
            _text_width_mm(total_text, pt) + 4.0 + 2 * PAD_MM,
            len(lines) * pt * PT_MM * 1.25 + 2.0 + 2 * PAD_MM,
        )
    if source:
        sizes["source"] = (
            _text_width_mm(source, preset.footer_pt) + 2 * PAD_MM,
            preset.footer_pt * PT_MM * 1.3 + 1.0,
        )
    return sizes


def plan_footer(
    sizes: dict[str, tuple[float, float]], x_left: float, x_right: float, y0: float = 0.5
) -> tuple[dict[str, BoxMm], float]:
    """Boxes of the footer elements and the height of the strip.

    The elements go in reading order on one row; when the row would be wider than `x_right - x_left` the next element starts a new row
    below. In a row the scale bar is at the left, the source at the right and the box of totals in the middle between them (at the right
    when the source is not in its row).
    """
    rows: list[list[str]] = [[]]
    used = 0.0
    for name, (w, _) in sizes.items():
        need = w + (FOOTER_GAP_MM if rows[-1] else 0.0)
        if rows[-1] and used + need > x_right - x_left:
            rows.append([])
            used, need = 0.0, w
        rows[-1].append(name)
        used += need
    boxes: dict[str, BoxMm] = {}
    y = y0
    for row in reversed(rows):  # the first row is the top one
        height = max(sizes[n][1] for n in row)
        left = x_left
        right = x_right
        if "scale_bar" in row:
            w = sizes["scale_bar"][0]
            boxes["scale_bar"] = (left, y, left + w, y + sizes["scale_bar"][1])
            left += w + FOOTER_GAP_MM
        if "source" in row:
            w = sizes["source"][0]
            boxes["source"] = (right - w, y, right, y + sizes["source"][1])
            right -= w + FOOTER_GAP_MM
        if "total" in row:
            w = sizes["total"][0]
            x = (left + right - w) / 2.0 if "source" in row else x_right - w
            x = min(max(x, left), right - w)
            boxes["total"] = (x, y, x + w, y + sizes["total"][1])
        y += height + 1.0
    return boxes, (y if sizes else 0.0)


def draw_compass(overlay, box: BoxMm, preset: Preset = THESIS) -> list:
    """Eight-triangle compass rose (cardinal points, each split into a dark and a light half) with an N above, inside `box`.

    Logic of `compass` in craei-brazil `scripts/article_map_utils.py`; the size here is millimetres, not a share of the extent.
    """
    x0, y0, x1, _ = box
    h = preset.compass_mm / 2.0
    d = h * 0.35
    cx, cy = (x0 + x1) / 2.0, y0 + PAD_MM + h
    polys = [
        ([[cx, cy + h], [cx - d, cy], [cx, cy]], "black"),
        ([[cx, cy + h], [cx + d, cy], [cx, cy]], "#888888"),
        ([[cx + h, cy], [cx, cy + d], [cx, cy]], "black"),
        ([[cx + h, cy], [cx, cy - d], [cx, cy]], "#888888"),
        ([[cx, cy - h], [cx + d, cy], [cx, cy]], "#CCCCCC"),
        ([[cx, cy - h], [cx - d, cy], [cx, cy]], "#EFEFEF"),
        ([[cx - h, cy], [cx, cy - d], [cx, cy]], "#CCCCCC"),
        ([[cx - h, cy], [cx, cy + d], [cx, cy]], "#EFEFEF"),
    ]
    artists: list = [
        overlay.add_patch(MplPolygon(coords, closed=True, fc=fc, ec="black", lw=0.3, zorder=10))
        for coords, fc in polys
    ]
    artists.append(
        overlay.text(
            cx,
            cy + h + 0.6,
            "N",
            fontsize=preset.legend_pt,
            weight="bold",
            ha="center",
            va="bottom",
            zorder=11,
        )
    )
    return artists


def draw_scale_bar(
    overlay,
    box: BoxMm,
    extent: Extent | None,
    map_w_mm: float,
    preset: Preset = THESIS,
    width_km: float | None = None,
) -> list:
    """Four alternating segments labelled 0, half and full length in km, calculated at the central latitude (craei-brazil `scale_bar`)."""
    pt = preset.legend_pt
    km = scale_bar_length_km(extent, width_km=width_km)
    length = _scale_bar_length_mm(extent, map_w_mm, width_km)
    seg = length / 4.0
    x0 = (
        box[0] + PAD_MM + _text_width_mm("0", pt) / 2.0
    )  # the bar always starts at the same distance from the left of its box
    y0 = box[1] + PAD_MM + pt * PT_MM + 1.0
    artists: list = [
        overlay.add_patch(
            Rectangle((x0 + i * seg, y0), seg, 1.8, fc=fc, ec="black", lw=0.4, zorder=10)
        )
        for i, fc in enumerate(["black", "white", "black", "white"])
    ]
    label_w = _text_width_mm(f"{km:g} km", pt)
    labels = [(0.0, "0"), (1.0, f"{km:g} km")]
    if (
        length / 2.0 >= 1.2 * label_w
    ):  # the middle label only when it does not run into its neighbours
        labels.insert(1, (0.5, f"{km / 2:g}"))
    for frac, text in labels:
        artists.append(
            overlay.text(
                x0 + frac * length, y0 - 0.6, text, fontsize=pt, ha="center", va="top", zorder=10
            )
        )
    return artists


# ------------------------------------------------------------------------------------------------------------------------- the canvas


@dataclass
class MapFigure:
    """A map figure under construction: `ax` for the data, `cax` for the legend, `overlay` (1 unit = 1 mm) for title and furniture."""

    fig: Figure
    ax: object
    cax: object
    overlay: object
    layout: Layout
    extent: Extent
    furniture: dict[str, Furniture] = field(default_factory=dict)
    texts: dict[str, object] = field(default_factory=dict)
    artists: dict[str, list] = field(
        default_factory=dict
    )  # the drawn pieces of each piece of furniture, for measuring
    preset: Preset = THESIS
    colours: dict[str, str] = field(
        default_factory=dict
    )  # flat colour (hex) -> what it means in this figure
    cmaps: dict[str, str] = field(
        default_factory=dict
    )  # colormap name -> what it means in this figure
    meta: dict[str, str] = field(default_factory=dict)  # what goes into the PNG text chunks
    frame: MapFrame | None = None  # the projection of the map (LAEA centred on the country)
    no_data_label: str | None = None

    def to_xy(self, lon, lat):
        """lon/lat (degrees) to the metres of the map frame."""
        return self.frame.to_xy(lon, lat)

    def fill_country(self, colour=NO_DATA_COLOUR, zorder: float = 1.5):
        """Paint the country in the grey of "no potential" under the data: what the data do not cover stays grey and has its legend entry."""
        from matplotlib.patches import PathPatch

        patch = PathPatch(
            geometry_path(self.frame.polygon),
            facecolor=colour,
            edgecolor="none",
            zorder=zorder,
            transform=self.ax.transData,
        )
        self.ax.add_artist(
            patch
        )  # not `add_patch`: that walks every vertex of the polygon to update the limits
        self.use_colour(colour, self.no_data_label or NO_DATA_LABEL)
        return patch

    def draw_raster(
        self,
        data,
        extent_grid: Extent,
        *,
        cmap=None,
        norm=None,
        zorder: float = 2.0,
        clip: bool = True,
        smooth: int | None = None,
    ):
        """Draw a lon/lat grid (row 0 north, `extent_grid` = west, east, south, north; 2-D values, or 3-D RGBA) in the projected frame.

        Each pixel of the map takes the value of the cell that contains it (nearest neighbour, no anti-aliasing, rasterised), and the image is
        clipped by the polygon of the country, so the coast and the border are the vector line, not the staircase of the cells.
        `smooth` (an integer factor, 2-D continuous fields only) first interpolates the field bilinearly with its mask (`display.smooth_masked`);
        the caller declares it in the subtitle (`smoothing_note`).
        """
        from matplotlib.patches import PathPatch

        frame = self.frame
        pixel_m = self.pixel_m()
        if smooth and np.ndim(data) == 3:
            raise ValueError("an image of classes or colours is never smoothed")
        if smooth:
            array = np.ma.masked_invalid(display.smooth_masked(np.ma.filled(data, np.nan), smooth))
        else:
            array = (
                np.asarray(data, dtype="float64")
                if np.ndim(data) == 3
                else np.ma.masked_invalid(data)
            )
        out, extent_m = reproject_nearest(array, extent_grid, frame, pixel_m)
        if out.ndim == 2:
            out = np.ma.masked_invalid(out)
        image = self.ax.imshow(
            out,
            extent=extent_m,
            origin="upper",
            cmap=cmap,
            norm=norm,
            interpolation="nearest",
            zorder=zorder,
            aspect="equal",
            rasterized=True,
        )
        if clip:
            patch = PathPatch(
                geometry_path(frame.polygon),
                facecolor="none",
                edgecolor="none",
                transform=self.ax.transData,
            )
            self.ax.add_artist(patch)
            image.set_clip_path(patch)
        self.ax.set_xlim(frame.bounds[0], frame.bounds[1])
        self.ax.set_ylim(frame.bounds[2], frame.bounds[3])
        return image

    def pixel_m(self) -> float:
        """Metres of the map on one pixel of the raster of this figure (`RENDER_DPI` on paper)."""
        map_w_mm = self.layout.map_box[2] - self.layout.map_box[0]
        return self.frame.width_m / max(map_w_mm / 25.4 * RENDER_DPI, 1.0)

    def px_per_cell(self, cell_deg: float) -> float:
        """Image pixels along one side of a cell of `cell_deg` in this figure (the preset, the country and the width decide)."""
        south, north = self.frame.lonlat_extent[2:]
        return display.px_per_cell(cell_deg, (south + north) / 2.0, self.pixel_m())

    def mm_to_fig(self, box: BoxMm) -> tuple[float, float, float, float]:
        w, h = self.layout.width_mm, self.layout.height_mm
        return box[0] / w, box[1] / h, (box[2] - box[0]) / w, (box[3] - box[1]) / h

    def use_colour(self, colour, meaning: str) -> None:
        """Record that `colour` means `meaning` here; the same colour with another meaning is an error."""
        key = to_hex(colour).lower()
        if self.colours.setdefault(key, meaning) != meaning:
            raise ValueError(
                f"{key} means {self.colours[key]!r} and {meaning!r} in the same figure"
            )

    def use_cmap(self, cmap, meaning: str) -> None:
        """Record that the colormap `cmap` (name or object) means `meaning` here."""
        name = cmap if isinstance(cmap, str) else cmap.name
        if self.cmaps.setdefault(name, meaning) != meaning:
            raise ValueError(f"the colormap {name!r} means {self.cmaps[name]!r} and {meaning!r}")

    def colour_problems(self) -> list[str]:
        """Conflicts of the colours of this figure, also under deuteranopia and protanopia (`colour_conflicts`)."""
        return colour_conflicts(self.colours, self.cmaps)


MapCanvas = MapFigure  # the name before COMMAND 66


def _load_country_names() -> dict[str, dict[str, str]]:
    """`config/country_names.yaml`: the name of a country in a title, by language (the code names no country, A-05)."""
    import yaml

    path = Path(__file__).resolve().parents[3] / "config" / "country_names.yaml"
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError:
        return {"en": {}, "pt": {}}


COUNTRY_NAMES = _load_country_names()

LABELS = {  # the words the module writes itself, by language (`en` is the default, `pt` the other one the thesis may use)
    "en": {
        "total": "Total",
        "energy_unit": "TWh/yr",
        "mean_cf": "mean CF",
        "eligible_area": "eligible area",
        "source": "Boundaries: GADM 4.1, illustrative",
    },
    "pt": {
        "total": "Total",
        "energy_unit": "TWh/ano",
        "mean_cf": "FC médio",
        "eligible_area": "área elegível",
        "source": "Limites: GADM 4.1, ilustrativo",
    },
}


def country_name(iso: str, lang: str = "en") -> str:
    """The name of the country for a title (never the ISO3 code), from `COUNTRY_NAMES`: the countries of the thesis and the test archetypes.

    A country that is not in the table needs its name (`country=` of `new_map`) and, to be listed, an entry in the table.
    """
    if lang not in LABELS:
        raise ValueError(f"language {lang!r} is not one of {sorted(LABELS)}")
    name = COUNTRY_NAMES[lang].get(iso) or COUNTRY_NAMES["en"].get(iso)
    if name is None:
        raise ValueError(f"no name for {iso!r}: give `country=` or add it to COUNTRY_NAMES")
    return name


# What may not appear in a title, a subtitle or a label: identifiers of the project, raw model names, counts of cells.
FORBIDDEN_IN_LABELS = (
    (r"\bOQ-?\d+", "open question"),
    (r"\b(?:L|A|U|V|M)-\d{2,}\b", "limitation or method item"),
    (r"\b[A-Za-z]-[A-Za-z0-9]+-\d{2,}\b", "decision id"),
    (r"(?i)\bcommand\s+\d+", "command number"),
    (r"\bm_[a-z0-9_]+\b", "member id"),
    (r"\bssp\d{3}\b", "raw scenario code (write SSP3-7.0)"),
    (r"\b[a-z0-9]+(?:_[a-z0-9]+)+\b", "snake_case identifier"),
    (r"\d[\d,.]*\s+(?:grid\s+)?cells?\b", "cell count"),
)
LABEL_TYPOS = (  # misspellings that were found in labels; the test greps the sources for them too
    "elgible",
    "eligble",
    "elegible",
    "capcity",
    "capaciy",
    "densitiy",
    "temprature",
    "potental",
    "scnenario",
    "enviroment",
)
TYPO_PATTERN = r"(?i)\b(?:" + "|".join(LABEL_TYPOS) + r")"


def validate_label(text: str, what: str = "label") -> str:
    """The text itself when it is clean; ValueError when it holds an internal id, a raw model name, a cell count or a known typo."""
    for pattern, reason in FORBIDDEN_IN_LABELS:
        found = re.search(pattern, text)
        if found:
            raise ValueError(f"the {what} {text!r} holds a {reason}: {found.group(0)!r}")
    typo = re.search(TYPO_PATTERN, text)
    if typo:
        raise ValueError(f"the {what} {text!r} holds a typo: {typo.group(0)!r}")
    return text


def format_title(country: str, technology: str, variable: str) -> str:
    """The short title: `<Country> · <Technology> · <Variable>` (the technology is left out for a map that has none).

    The first part is the name of the country, never its ISO3 code, and the title is checked by `validate_label`.
    """
    if re.fullmatch(r"[A-Z]{3}", country):
        raise ValueError(f"the title needs the name of the country, not the code {country!r}")
    return validate_label(" · ".join(p for p in (country, technology, variable) if p), "title")


def totals_text(
    capacity_gw: float | None = None,
    energy_twh: float | None = None,
    mean_cf: float | None = None,
    eligible_km2: float | None = None,
    lang: str = "en",
) -> str:
    """The box of totals: `Total: X GW · Y TWh/yr · mean CF Z% · eligible area W km²` (the parts that are given)."""
    words = LABELS[lang]
    parts = []
    if capacity_gw is not None:
        parts.append(f"{capacity_gw:,.1f} GW")
    if energy_twh is not None:
        parts.append(f"{energy_twh:,.1f} {words['energy_unit']}")
    if mean_cf is not None:
        parts.append(f"{words['mean_cf']} {100 * mean_cf:.1f}%")
    if eligible_km2 is not None:
        parts.append(f"{words['eligible_area']} {eligible_km2:,.0f} km²")
    return f"{words['total']}: " + " · ".join(parts)


def _draw_graticule(
    canvas, left_labels: bool = True, bottom_labels: bool = True, keep_inside_m: float = 0.0
) -> None:
    """Meridians and parallels in thin light lines, labelled in degrees where they cross the left and the bottom edge of the map
    (`left_labels` and `bottom_labels` leave the numbers out, for the inner maps of a sheet; `keep_inside_m` drops a longitude label
    whose text would run out of the map by being closer than that to its sides)."""
    frame, ax = canvas.frame, canvas.ax
    xmin, xmax, ymin, ymax = frame.bounds
    west, east, south, north = frame.lonlat_extent
    lon_ticks = [
        t
        for t in ticker.MaxNLocator(nbins=4, steps=[1, 2, 5, 10]).tick_values(west, east)
        if west < t < east
    ]
    lat_ticks = [
        t
        for t in ticker.MaxNLocator(nbins=4, steps=[1, 2, 5, 10]).tick_values(south, north)
        if south < t < north
    ]
    style = {"color": GRATICULE_COLOUR, "linewidth": 0.3, "linestyle": (0, (1.5, 2.0)), "zorder": 3}
    xt, xl, yt, yl = [], [], [], []
    sweep_lon = np.linspace(west, east, 240)
    sweep_lat = np.linspace(south, north, 240)
    for lat in lat_ticks:
        x, y = frame.to_xy(sweep_lon, np.full_like(sweep_lon, lat))
        ax.plot(x, y, scalex=False, scaley=False, **style)
        order = np.argsort(x)
        if x.min() <= xmin <= x.max():
            y_edge = float(np.interp(xmin, x[order], y[order]))
            if ymin < y_edge < ymax:
                yt.append(y_edge)
                yl.append(format_degrees(lat, "lat"))
    for lon in lon_ticks:
        x, y = frame.to_xy(np.full_like(sweep_lat, lon), sweep_lat)
        ax.plot(x, y, scalex=False, scaley=False, **style)
        order = np.argsort(y)
        if y.min() <= ymin <= y.max():
            x_edge = float(np.interp(ymin, y[order], x[order]))
            if xmin + keep_inside_m < x_edge < xmax - keep_inside_m:
                xt.append(x_edge)
                xl.append(format_degrees(lon, "lon"))
    ax.set_xticks(xt if bottom_labels else [], xl if bottom_labels else [])
    ax.set_yticks(yt if left_labels else [], yl if left_labels else [])
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)


_NEIGHBOURS: dict = {}  # the neighbours cut to a frame, kept: the sheets of a country share a frame


def _remember(key, value):
    if len(_NEIGHBOURS) >= 8:
        _NEIGHBOURS.pop(next(iter(_NEIGHBOURS)))
    _NEIGHBOURS[key] = value
    return value


def _neighbours_in_frame(neighbours, frame: MapFrame):
    """The neighbouring countries in the projection, cut by the rectangle of the map: a straight cut at the frame, not a buffer round the
    country (which leaves rounded shapes and white wedges)."""
    import geopandas as gpd
    import shapely

    key = (id(neighbours), len(neighbours), frame.bounds, str(frame.crs))
    if key in _NEIGHBOURS:
        return _NEIGHBOURS[key]
    west, east, south, north = frame.lonlat_extent
    pad = 1.0
    wide = shapely.box(west - pad, south - pad, east + pad, north + pad)
    near = neighbours.to_crs("EPSG:4326").clip(wide)
    if not len(near):
        return _remember(key, near.assign(gap=[]))
    projected = near.to_crs(frame.crs)
    xmin, xmax, ymin, ymax = frame.bounds
    # the borders of two sources of geometry never coincide: the gap between the country and its neighbours (not the sea) is closed
    gap = (
        projected.geometry.union_all()
        .simplify(BORDER_GAP_M / 20)
        .buffer(BORDER_GAP_M, quad_segs=2)
        .intersection(frame.polygon.simplify(BORDER_GAP_M / 20).buffer(BORDER_GAP_M, quad_segs=2))
        .difference(
            frame.polygon
        )  # only the sliver outside the country: inside it the map has its own colours
    )
    cut = gpd.GeoSeries([*projected.geometry, gap], crs=frame.crs).clip_by_rect(
        xmin, ymin, xmax, ymax
    )
    out = gpd.GeoDataFrame(geometry=cut, crs=frame.crs)
    out["gap"] = [False] * len(projected) + [True]
    return _remember(key, out[~out.geometry.is_empty].reset_index(drop=True))


def _draw_locator(canvas: MapFigure, box: BoxMm, polygon, neighbours) -> list:
    """The locator inset (overview figures only): the country in dark grey among its neighbours within 10 degrees, in the same projection."""
    import geopandas as gpd

    frame = make_frame(polygon, extent=None, margin=0.0)
    wide = polygon.buffer(10.0)
    ax = canvas.fig.add_axes(canvas.mm_to_fig(box))
    ax.set_facecolor(SEA_COLOUR)
    xmin, ymin, xmax, ymax = frame.project_geometry(wide).bounds
    target = (box[2] - box[0]) / (
        box[3] - box[1]
    )  # the limits get the shape of the inset, so that nothing is stretched or dropped
    cx, cy = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0
    half_w, half_h = (xmax - xmin) / 2.0, (ymax - ymin) / 2.0
    if half_w / half_h < target:
        half_w = half_h * target
    else:
        half_h = half_w / target
    xmin, xmax, ymin, ymax = cx - half_w, cx + half_w, cy - half_h, cy + half_h
    if neighbours is not None:
        near = neighbours.to_crs("EPSG:4326").clip(wide)
        if len(near):
            near.to_crs(frame.crs).plot(
                ax=ax, color=NEIGHBOUR_COLOUR, edgecolor="white", linewidth=0.2, zorder=1
            )
    gpd.GeoSeries([frame.polygon], crs=frame.crs).plot(ax=ax, color=LOCATOR_COLOUR, zorder=3)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_linewidth(0.4)
        spine.set_color("#888888")
    canvas.use_colour(LOCATOR_COLOUR, "this country (locator)")
    return [ax]


LOCATOR_COLOUR = "#4d4d4d"
LOCATOR_W_MM = 24.0  # width of the inset in mm; its height is that of the compass box


def new_map(
    geometry,
    *,
    iso: str,
    technology: str,
    variable: str,
    subtitle: str = "",
    total_text: str | None = None,
    width_mm: float | None = None,
    preset: str | Preset | None = "thesis",
    neighbours=None,
    extent: Extent | None = None,
    contiguous: bool = True,
    legend_side_mm: float | None = None,
    legend_below_mm: float | None = None,
    country: str | None = None,
    source: str | None = DEFAULT_SOURCE,
    lang: str = "en",
    no_data_label: str | None = None,
    locator: bool = False,
    graticule: bool = True,
) -> MapFigure:
    """Axes, legend slot, title and furniture of a map of the country `geometry` (lon/lat), ready to receive the data.

    The map is drawn in a Lambert azimuthal equal-area projection centred on the country (`make_frame`); its frame is the projected country
    plus 3% (far islands out), or the bounds of `extent` (lon/lat) when it is given. `preset` gives the fonts and, unless `width_mm` is given,
    the width (a very tall country gets a narrower figure, `fitted_width_mm`). `neighbours` (a GeoDataFrame) are drawn in light grey within
    the rectangle of the map, the sea stays white. `no_data_label` adds the legend entry for the part of the country without
    value (drawn by `fill_country`), `locator` the inset that says where the country is (overview figures only). Draw the data with
    `canvas.draw_raster` (or `draw_choropleth`) and the colour bar on `canvas.cax` (`add_colorbar`), then save with `save_png`.
    """
    import geopandas as gpd

    pre = get_preset(preset)
    polygon = contiguous_geometry(geometry) if contiguous else _as_geometry(geometry)
    frame = make_frame(polygon, extent)
    ratio = frame.ratio
    title = format_title(country or country_name(iso, lang), technology, variable)
    validate_label(subtitle, "subtitle")
    if source == DEFAULT_SOURCE:
        source = LABELS[lang]["source"]
    for text in (total_text, source, no_data_label):
        if text:
            validate_label(text, "footer text")
    side_mm = LEGEND_SIDE_MM if legend_side_mm is None else legend_side_mm
    no_data_mm = 0.0
    if no_data_label:
        entry_w = SWATCH_W_MM + 2.0 + _text_width_mm(no_data_label, pre.legend_pt)
        if ratio > 1.0:
            side_mm = max(side_mm, 4.0 + entry_w + 3.0)
            no_data_mm = ROW_MM + 1.5
        else:
            no_data_mm = entry_w + 1.0
    base_width = pre.width_mm if width_mm is None else width_mm
    width_mm = fitted_width_mm(ratio, base_width, side_mm)
    if total_text:
        total_text = wrap_total_text(
            total_text, width_mm - LEFT_MM - RIGHT_MM - 2 * PAD_MM - 4.0, pre.legend_pt
        )
    cw, ch = compass_size_mm(pre)
    locator_w = LOCATOR_W_MM if locator else 0.0
    title_lines, sub_lines, header_mm = header_text(
        width_mm, title, subtitle, pre, reserve_mm=locator_w + (3.0 if locator else 0.0)
    )

    def layout_for(footer: float) -> Layout:
        return compute_layout(
            None,
            width_mm,
            footer_mm=footer,
            legend_side_mm=side_mm,
            legend_below_mm=legend_below_mm,
            header_mm=header_mm,
            ratio=ratio,
            no_data_mm=no_data_mm,
        )

    # The footer height depends on the width of the scale bar, which depends on the map width, which depends on the footer height when the
    # map is limited by the height of the sheet. The footer only shrinks the map, so the second pass cannot need more room than the first.
    layout = layout_for(0.0)
    sizes = footer_item_sizes(
        None, layout.map_box[2] - layout.map_box[0], total_text, source, pre, frame.width_km
    )
    _, footer = plan_footer(sizes, LEFT_MM, width_mm - RIGHT_MM)
    layout = layout_for(footer)
    sizes = footer_item_sizes(
        None, layout.map_box[2] - layout.map_box[0], total_text, source, pre, frame.width_km
    )
    boxes, _ = plan_footer(sizes, LEFT_MM, width_mm - RIGHT_MM)
    compass_box = (
        width_mm - 1.0 - cw,
        layout.height_mm - 1.0 - ch,
        width_mm - 1.0,
        layout.height_mm - 1.0,
    )
    placed = {"compass": Furniture("compass", compass_box, "header")}
    if locator:
        lbox = (
            compass_box[0] - 3.0 - locator_w,
            compass_box[1] + PAD_MM,
            compass_box[0] - 3.0,
            compass_box[3] - PAD_MM,
        )
        placed["locator"] = Furniture("locator", lbox, "header")
    placed.update({n: Furniture(n, b, "footer") for n, b in boxes.items()})

    with plt.rc_context(_rc(pre)):
        fig = plt.figure(
            figsize=(layout.width_mm / 25.4, layout.height_mm / 25.4), dpi=DPI, facecolor="white"
        )
        canvas = MapFigure(
            fig, None, None, None, layout, frame.lonlat_extent, placed, preset=pre, frame=frame
        )
        ax = fig.add_axes(canvas.mm_to_fig(layout.map_box))
        ax.set_facecolor(SEA_COLOUR)
        cax = fig.add_axes(canvas.mm_to_fig(layout.legend_box))
        overlay = fig.add_axes((0, 0, 1, 1), facecolor="none")
        overlay.set_xlim(0, layout.width_mm)
        overlay.set_ylim(0, layout.height_mm)
        overlay.axis("off")
        overlay.set_zorder(5)
        canvas.ax, canvas.cax, canvas.overlay = ax, cax, overlay

        ax.set_xlim(frame.bounds[0], frame.bounds[1])
        ax.set_ylim(frame.bounds[2], frame.bounds[3])
        ax.set_aspect("equal")
        ax.tick_params(labelsize=pre.label_pt, pad=1.5)
        for spine in ax.spines.values():
            spine.set_linewidth(0.4)
            spine.set_color("#888888")
        canvas.use_colour(SEA_COLOUR, "sea")
        near = None
        if neighbours is not None:
            canvas.use_colour(NEIGHBOUR_COLOUR, "neighbouring countries")
            near = _neighbours_in_frame(neighbours, frame)
            for is_gap, part in near.groupby("gap") if len(near) else ():
                part.plot(
                    ax=ax,
                    color=NEIGHBOUR_COLOUR,
                    edgecolor="none" if is_gap else "white",
                    linewidth=0.3,
                    zorder=0.4 if is_gap else 0.5,
                )
        gpd.GeoSeries([frame.polygon], crs=frame.crs).boundary.plot(
            ax=ax, color=OUTLINE_COLOUR, linewidth=0.5, zorder=4
        )
        if graticule:
            _draw_graticule(canvas)
        else:
            ax.set_xticks([])
            ax.set_yticks([])
        ax.set_xlim(frame.bounds[0], frame.bounds[1])
        ax.set_ylim(frame.bounds[2], frame.bounds[3])

        top = layout.height_mm - 2.0
        canvas.texts["title"] = overlay.text(
            2.0,
            top,
            "\n".join(title_lines),
            fontsize=pre.title_pt,
            fontweight="bold",
            ha="left",
            va="top",
        )
        if subtitle:
            canvas.texts["subtitle"] = overlay.text(
                2.0,
                top - len(title_lines) * pre.title_pt * PT_MM * 1.35,
                "\n".join(sub_lines),
                fontsize=pre.label_pt,
                color="#444444",
                ha="left",
                va="top",
            )
        map_w = layout.map_box[2] - layout.map_box[0]
        canvas.artists["scale_bar"] = draw_scale_bar(
            overlay, placed["scale_bar"].box, None, map_w, pre, frame.width_km
        )
        canvas.artists["compass"] = draw_compass(overlay, placed["compass"].box, pre)
        if locator:
            canvas.artists["locator"] = _draw_locator(
                canvas, placed["locator"].box, polygon, neighbours
            )
        if no_data_label and layout.no_data_box is not None:
            canvas.no_data_label = no_data_label
            box = layout.no_data_box
            canvas.use_colour(NO_DATA_COLOUR, no_data_label)
            swatch = overlay.add_patch(
                Rectangle(
                    (box[0], box[1] + (box[3] - box[1] - SWATCH_H_MM) / 2),
                    SWATCH_W_MM,
                    SWATCH_H_MM,
                    facecolor=NO_DATA_COLOUR,
                    edgecolor="#555555",
                    linewidth=0.2,
                )
            )
            text_artist = overlay.text(
                box[0] + SWATCH_W_MM + 2.0,
                (box[1] + box[3]) / 2,
                no_data_label,
                fontsize=pre.legend_pt,
                color="#333333",
                ha="left",
                va="center",
            )
            canvas.artists["no_data"] = [swatch, text_artist]
        if total_text:
            box = placed["total"].box
            total_artist = overlay.text(
                box[0] + PAD_MM + 1.0,
                box[1] + PAD_MM + 1.0,
                total_text,
                fontsize=pre.legend_pt,
                color="#333333",
                ha="left",
                va="bottom",
                bbox={
                    "facecolor": "white",
                    "edgecolor": "#bbbbbb",
                    "linewidth": 0.3,
                    "boxstyle": "square,pad=0.3",
                    "alpha": 0.9,
                },
            )
            canvas.texts["total"] = total_artist
            canvas.artists["total"] = [total_artist]
        if source:
            box = placed["source"].box
            source_artist = overlay.text(
                box[2] - PAD_MM,
                box[1] + 0.5,
                source,
                fontsize=pre.footer_pt,
                color="#666666",
                ha="right",
                va="bottom",
            )
            canvas.texts["source"] = source_artist
            canvas.artists["source"] = [source_artist]
    return canvas


def add_colorbar(canvas: MapFigure, mappable, label: str, extend: str = "neither"):
    """The colour bar in the legend slot: vertical to the right of a tall map, horizontal below a wide one."""
    orientation = "vertical" if canvas.layout.legend == "right" else "horizontal"
    pt = canvas.preset.legend_pt
    validate_label(label, "colour bar label")
    canvas.use_cmap(mappable.get_cmap(), label)
    with plt.rc_context(_rc(canvas.preset)):
        bar = canvas.fig.colorbar(mappable, cax=canvas.cax, orientation=orientation, extend=extend)
        bar.outline.set_linewidth(0.3)
        bar.ax.tick_params(labelsize=pt, width=0.4, length=2.0)
        if orientation == "vertical":
            bar.set_label(label, fontsize=pt)
        else:
            bar.set_label(label, fontsize=pt, labelpad=1.0)
    return bar


@dataclass(frozen=True)
class DisplayPlan:
    """What a continuous map draws and says about its resolution: the grid (the analysis grid or a finer display layer), its pixels per cell,
    the interpolation factor (None: none), the source of the data and the text for the subtitle (`shown`)."""

    grid: np.ndarray
    extent: Extent
    px: float
    source: str | None
    smooth: bool
    factor: int | None
    shown: str | None


def plan_display(
    canvas: MapFigure,
    grid,
    extent_grid: Extent,
    resolution: str | None,
    layer: display.DisplayLayer | None = None,
    mode: str = "auto",
    coarse_source: bool = False,
) -> DisplayPlan:
    """Decide, for a continuous field on `canvas`, which grid is drawn and whether it is smoothed (COMMAND 67b).

    The image pixels per cell of `grid` are counted for this figure (preset, country, width). Above `display.MAX_PX_PER_CELL` the finer `layer`
    is drawn when there is one; if a cell is still a block, or the field comes from a GCM (`coarse_source`), the field is interpolated with its
    mask unless `mode` is `off`. The caller builds the header with `shown` (the resolution note, with `display smoothing` when it applies).
    """
    cell_deg = display.cell_deg_of(np.shape(grid), extent_grid)
    px = canvas.px_per_cell(cell_deg)
    drawn, extent, source = grid, extent_grid, resolution
    if layer is not None and px > display.MAX_PX_PER_CELL:
        drawn, extent = layer.grid, layer.extent
        px = canvas.px_per_cell(layer.cell_deg)
        source = resolution_note(display_deg=layer.cell_deg)
    smooth = display.needs_smoothing(px, True, mode, coarse_source)
    factor = display.upsample_factor(px, np.shape(drawn)) if smooth else None
    return DisplayPlan(
        drawn, extent, px, source, smooth, factor, smoothing_note(source) if smooth else source
    )


def display_meta(plan: DisplayPlan, mode: str) -> dict[str, str]:
    """The display resolution of a map as PNG text: pixels per cell drawn, whether it was smoothed, the source."""
    return {
        "display_px_per_cell": f"{plan.px:.1f}",
        "display_smoothing": "applied" if plan.smooth else ("off" if mode == "off" else "none"),
        "display_source": plan.source or "",
    }


def raster_map(
    grid: np.ndarray,
    extent_grid: Extent,
    geometry,
    *,
    iso: str,
    technology: str,
    variable: str,
    label: str,
    kind: str = "potential",
    tech: str | None = None,
    subtitle: str = "",
    scenario: str | None = None,
    climate: str | None = None,
    total_text: str | None = None,
    width_mm: float | None = None,
    preset: str | Preset | None = "thesis",
    neighbours=None,
    diverging_center: float = 0.0,
    country: str | None = None,
    scale: ScaleSpec | None = None,
    shared: tuple[float, float] | None = None,
    unit: str | None = None,
    lang: str = "en",
    resolution: str | None = None,
    no_data_label: str | None = None,
    locator: bool = False,
    graticule: bool = True,
    contiguous: bool = True,
    display_layer: display.DisplayLayer | None = None,
    display_smoothing: str = "auto",
    coarse_source: bool = False,
    extent: Extent | None = None,
) -> MapFigure:
    """A continuous raster map in the common style: the colormap and the scale of `kind` (and `tech`), extend where needed.

    The scale is `scale` or `default_scale(kind, tech)`; `shared` are the limits of `shared_limits` for maps that are compared. The
    subtitle is `subtitle` or `Scenario · Climate`, then `resolution` (`resolution_note`), then what the scale cuts (`clip_note`, in `unit`).
    `tech` is `solar` or `wind` (needed by the kinds that take the family of the technology). With `no_data_label` the part of the country
    without value is drawn in the grey of "no potential" and has its own entry in the legend.

    Display resolution (COMMAND 67b): the figure counts the image pixels per cell of `grid`; above `display.MAX_PX_PER_CELL` it draws the finer
    `display_layer` when there is one (a descriptive layer only, never a result: the colours and the legend still come from `grid`), and when
    a cell is still a block, or the field comes from a GCM (`coarse_source`), it interpolates the field with its mask (`display_smoothing`
    `auto`, `off` never does) and says so in the subtitle with the resolution of the source. The analysis grid and its totals are not touched.
    """
    data = np.ma.masked_invalid(grid)
    if kind.startswith("delta") and scale is None:
        scale = replace(default_scale(kind, tech), center=diverging_center)
    spec = scale or default_scale(kind, tech)
    info = resolve_scale(data.compressed(), spec, shared)
    base = subtitle or format_subtitle(scenario, climate)
    scale_text = clip_note(info, unit if unit is not None else label)

    def build(resolution_text: str | None) -> MapFigure:
        return new_map(
            geometry,
            iso=iso,
            technology=technology,
            variable=variable,
            subtitle=format_subtitle(base, resolution_text, scale_text),
            total_text=total_text,
            width_mm=width_mm,
            preset=preset,
            neighbours=neighbours,
            country=country,
            lang=lang,
            no_data_label=no_data_label,
            locator=locator,
            graticule=graticule,
            contiguous=contiguous,
            extent=extent,
        )

    canvas = build(resolution)
    plan = plan_display(
        canvas, grid, extent_grid, resolution, display_layer, display_smoothing, coarse_source
    )
    shown = plan.shown
    if (
        shown != resolution
    ):  # the subtitle changes with the layer and the smoothing: draw the header again
        plt.close(canvas.fig)
        canvas = build(shown)
    if no_data_label:
        canvas.fill_country()
    image = canvas.draw_raster(
        np.ma.masked_invalid(plan.grid),
        plan.extent,
        cmap=colormap_for(kind, tech),
        norm=info.norm,
        smooth=plan.factor,
    )
    add_colorbar(canvas, image, label, info.extend)
    canvas.meta.update(display_meta(plan, display_smoothing))
    canvas.meta.update(scale_meta(info))
    if shown:
        canvas.meta["resolution"] = shown
    return canvas


def scale_meta(info: NormInfo) -> dict[str, str]:
    """The scale of a map as PNG text: the mode (fixed, percentile, shared), the scope, the limits, the norm and the extend."""
    return {
        "scale_mode": info.mode,
        "scale_scope": info.scope,
        "scale_limits": f"{info.vmin:.6g},{info.vmax:.6g}",
        "scale_norm": info.kind,
        "scale_extend": info.extend,
    }


# ------------------------------------------------------------------------------------------------------ file names, metadata and index (T-05)

NOT_APPLICABLE = {
    "na",
    "n-a",
    "none",
    "nan",
    "null",
    "nil",
}  # a field that does not apply is left out, never written like this
FILENAME_RE = re.compile(r"^[A-Z]{3}_[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9][A-Za-z0-9.\-]*)+\.png$")
META_PREFIX = "geofrea_"


def slug(text: str) -> str:
    """A readable piece of a file name: letters, digits, `.` and `-`; spaces, underscores and slashes become `-`. The case is kept
    (`ACCESS-CM2`, `SSP3-7.0`, `E5-land-cover`)."""
    out = re.sub(r"[\s_/\\]+", "-", str(text).strip())
    out = re.sub(r"[^A-Za-z0-9.\-]", "", out)
    return re.sub(r"-{2,}", "-", out).strip("-.")


def _pieces(field_value) -> list[str]:
    if field_value is None:
        return []
    items = [field_value] if isinstance(field_value, str) else list(field_value)
    return [p for p in (slug(i) for i in items if i is not None) if p]


def figure_filename(
    iso: str,
    phase: str,
    variable: str | Sequence[str],
    technology: str | Sequence[str] | None = None,
    scenario: str | Sequence[str] | None = None,
    climate: str | Sequence[str] | None = None,
) -> str:
    """`{ISO3}_{phase}_{variable}_{technology}_{scenario}_{climate}.png`, with the fields that do not apply left out.

    Examples: `BRA_F3_excluded-share_E5-land-cover_wind.png` (variable given as two pieces),
    `BRA_F4_forcing_ACCESS-CM2_SSP3-7.0_2041-2070.png` (climate as three pieces), `PRT_F5_capacity-factor_wind_central_ref.png`.
    The code of the country is always there (three countries never write the same name), no field is empty or `na`, no hash.
    """
    if not re.fullmatch(r"[A-Z]{3}", iso):
        raise ValueError(f"the file name starts with the ISO3 code of the country, got {iso!r}")
    parts = [iso, slug(phase)]
    if not parts[1]:
        raise ValueError("the file name needs the phase")
    named = {
        "variable": variable,
        "technology": technology,
        "scenario": scenario,
        "climate": climate,
    }
    for field_name, value in named.items():
        pieces = _pieces(value)
        if field_name == "variable" and not pieces:
            raise ValueError("the file name needs the variable")
        parts += pieces
    for piece in parts:
        if piece.lower() in NOT_APPLICABLE:
            raise ValueError(
                f"a field that does not apply is left out of the file name, not written as {piece!r}"
            )
    name = "_".join(parts) + ".png"
    validate_filename(name)
    return name


def validate_filename(name: str) -> str:
    """The name itself when it follows the standard; ValueError otherwise (no ISO3 first, an empty field, `na`, a hash-like tail)."""
    if not FILENAME_RE.match(name):
        raise ValueError(f"{name!r} does not follow {{ISO3}}_{{phase}}_{{variable}}[_...].png")
    stem = name[:-4]
    for piece in stem.split("_"):
        if piece.lower() in NOT_APPLICABLE:
            raise ValueError(f"{name!r} has a field written as {piece!r}")
    if re.search(r"(?:^|_)[0-9a-f]{6,}$", stem) and not re.search(r"[A-Z]", stem.split("_")[-1]):
        raise ValueError(f"{name!r} ends with what looks like a hash: use a readable slug")
    return name


@functools.cache
def repo_commit() -> str:
    """The short commit of the code that draws (`GEOFREA_GIT_COMMIT` if set), or `unknown` outside a repository."""
    import os
    import subprocess

    if os.environ.get("GEOFREA_GIT_COMMIT"):
        return os.environ["GEOFREA_GIT_COMMIT"]
    root = Path(__file__).resolve().parents[3]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


@functools.cache
def config_hash() -> str:
    """The first 12 hex digits of the SHA-256 of `config/parameters.json` (or `unknown`)."""
    import hashlib

    path = Path(__file__).resolve().parents[3] / "config" / "parameters.json"
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    except OSError:
        return "unknown"


def png_metadata(canvas: MapFigure, extra: dict[str, str] | None = None) -> dict[str, str]:
    """The text chunks of the PNG: title and subtitle, commit, hash of the config, date, preset, the scale (mode, scope, limits) and
    whatever the caller adds (`grid` for the grid and resolution, `data_source`). Keys of the project start with `geofrea_`."""
    from datetime import UTC, datetime

    meta = {
        "Title": canvas.texts["title"].get_text().replace("\n", " "),
        "geofrea_commit": repo_commit(),
        "geofrea_config_hash": config_hash(),
        "geofrea_date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "geofrea_preset": canvas.preset.name,
    }
    if "subtitle" in canvas.texts:
        meta["Description"] = canvas.texts["subtitle"].get_text().replace("\n", " ")
    meta.update({f"{META_PREFIX}{k}": str(v) for k, v in canvas.meta.items()})
    for key, value in (extra or {}).items():
        meta[
            key
            if key in {"Title", "Description"}
            else f"{META_PREFIX}{key.removeprefix(META_PREFIX)}"
        ] = str(value)
    return meta


def close_figure(figure) -> None:
    """Close a figure that will not be saved (a header that is drawn again): the `Figure` itself, or a map or sheet that holds one."""
    plt.close(getattr(figure, "fig", figure))


def save_png(canvas_or_fig, path: Path, metadata: dict[str, str] | None = None) -> Path:
    """Write the figure as PNG at 300 dpi and its exact print size, with no software tag. Only PNG is written.

    A `MapFigure` carries its metadata in the text chunks of the file (`png_metadata`): there is no sidecar file per figure.
    `metadata` adds fields, e.g. `{"grid": "0.05 degree analysis grid", "data_source": "F5 potential_wind__central"}`.
    """
    path = Path(path)
    if path.suffix.lower() != ".png":
        raise ValueError(f"maps are written as PNG only, got {path.suffix!r}")
    is_map = isinstance(canvas_or_fig, MapFigure) or (
        hasattr(canvas_or_fig, "texts") and hasattr(canvas_or_fig, "fig")
    )  # a MapFigure or a PanelFigure
    fig = canvas_or_fig.fig if is_map else canvas_or_fig
    text = {"Software": None}
    if is_map:
        text.update(png_metadata(canvas_or_fig, metadata))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, facecolor="white", metadata=text)
    plt.close(fig)
    return path


def read_png_metadata(path: Path) -> dict[str, str]:
    """The text chunks of a PNG."""
    from PIL import Image

    with Image.open(path) as im:
        return {str(k): str(v) for k, v in im.text.items()}


def write_figures_index(folder: Path) -> Path:
    """`figures_index.json` of a folder: for each PNG its file name, size, SHA-256 and the `geofrea_*` text of the file, and the list
    of the files whose name does not follow the standard. One index per folder, the only file besides the figures."""
    import hashlib
    import json

    from PIL import Image

    folder = Path(folder)
    entries, nonconforming = [], []
    for png in sorted(folder.glob("*.png")):
        try:
            validate_filename(png.name)
        except ValueError:
            nonconforming.append(png.name)
        with Image.open(png) as im:
            size = list(im.size)
            text = {str(k): str(v) for k, v in im.text.items()}
        entries.append(
            {
                "file": png.name,
                "size_px": size,
                "sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
                "title": text.get("Title", ""),
                "subtitle": text.get("Description", ""),
                "metadata": {k: v for k, v in sorted(text.items()) if k.startswith(META_PREFIX)},
            }
        )
    out = folder / "figures_index.json"
    out.write_text(
        json.dumps(
            {"figures": entries, "nonconforming": nonconforming}, indent=1, ensure_ascii=False
        )
        + "\n",
        encoding="utf-8",
    )
    return out


# ------------------------------------------------------------------------------------------------- classed maps and proportional circles
# (COMMAND 60: a choropleth with classes, and circles whose area is proportional to a total, drawn over it)

SWATCH_W_MM, SWATCH_H_MM = 4.0, 3.2
ROW_MM = 4.8  # height of one row of the class legend
CIRCLE_MAX_MM = 9.0  # radius of the circle of the reference total (the largest), on paper
CIRCLE_FACE, CIRCLE_EDGE = (
    (0.85, 0.2, 0.15, 0.55),
    "#7a1010",
)  # the circles of the totals and their legend
CIRCLE_MIN_MM = (
    0.35  # a circle of a state with a total above zero is never smaller than this radius
)


@dataclass(frozen=True)
class ClassedLegend:
    """What the legend of a classed map holds: a title (the unit), one label and colour per class, an optional "no value" entry and an
    optional list of proportional circles (label, radius in mm) with its own title."""

    title: str
    labels: tuple[str, ...]
    colours: tuple
    no_value_label: str | None = None
    circle_title: str | None = None
    circles: tuple[tuple[str, float], ...] = ()


def circle_radius_mm(value: float, reference: float, max_radius_mm: float) -> float:
    """Radius in mm of the circle of `value`: the area is proportional to the value, the circle of `reference` has `max_radius_mm`.

    A value of zero (or less) has no circle; a positive value is never smaller than `CIRCLE_MIN_MM`.
    """
    if not (value > 0) or not (reference > 0):
        return 0.0
    return max(CIRCLE_MIN_MM, max_radius_mm * math.sqrt(value / reference))


def nice_values_below(maximum: float, n: int = 3) -> list[float]:
    """`n` round values (1, 2 or 5 times a power of ten) for a circle legend, the largest not above `maximum`, each about a tenth of the one before."""
    if not (maximum > 0):
        return []
    exponent = math.floor(math.log10(maximum))
    top = max(
        m * 10.0**exponent for m in (1.0, 2.0, 5.0) if m * 10.0**exponent <= maximum * (1 + 1e-9)
    )
    return [top / 10.0**i for i in range(n)]


def qualitative_legend(
    title: str, labels: Sequence[str], none_label: str | None = None
) -> ClassedLegend:
    """The legend of a categorical map (dominant exclusion E1-E6, land cover): named patches in the colour-blind safe class colours, and a
    neutral grey for a class that means "none", never a colour bar."""
    colours = class_colours(len(labels))
    labels = list(labels)
    if none_label:
        labels.append(none_label)
        colours.append(CLASS_NONE_COLOUR)
    return ClassedLegend(title=title, labels=tuple(labels), colours=tuple(colours))


def legend_space(spec: ClassedLegend, preset: Preset = THESIS) -> tuple[float, float]:
    """(side, below) space in mm that the legend needs: `side` is the width of the strip right of a tall map, `below` the height under a wide one."""
    labels = list(spec.labels) + ([spec.no_value_label] if spec.no_value_label else [])
    widest = max(_text_width_mm(t, preset.legend_pt) for t in labels)
    circle_w = max(
        (2 * r + 2.0 + _text_width_mm(t, preset.legend_pt) for t, r in spec.circles), default=0.0
    )
    title_w = max(
        (
            _text_width_mm(w, preset.legend_pt)
            for w in (spec.title + " " + (spec.circle_title or "")).split()
        ),
        default=0.0,
    )
    side = 4.0 + max(SWATCH_W_MM + 2.0 + widest, circle_w, title_w) + 3.0
    biggest = max((r for _, r in spec.circles), default=0.0)
    below = 17.5 + (2 * biggest + 8.0 if spec.circles else 0.0)
    return side, below


def draw_classed_legend(canvas: MapFigure, spec: ClassedLegend) -> dict[str, list]:
    """Draw the legend of a classed map in the strip the layout reserved (right of a tall map, below a wide one).

    The colour-bar axes of the canvas is hidden. The drawn pieces are kept in `canvas.artists["legend"]` for the overlap tests.
    """
    from matplotlib.patches import Circle

    layout, overlay = canvas.layout, canvas.overlay
    pt = canvas.preset.legend_pt
    canvas.cax.set_visible(False)
    text_kw = {"fontsize": pt, "color": "#333333"}
    pieces: list = []
    labels = list(spec.labels) + ([spec.no_value_label] if spec.no_value_label else [])
    colours = list(spec.colours) + ([NO_DATA_COLOUR] if spec.no_value_label else [])
    for text in (spec.title, spec.circle_title or "", *labels):
        validate_label(text, "legend text")
    for text, colour in zip(labels, colours, strict=True):
        canvas.use_colour(colour, text)
    line_mm = pt * PT_MM * 1.3

    def swatch(x, y, w, colour):
        return overlay.add_patch(
            Rectangle(
                (x, y - SWATCH_H_MM),
                w,
                SWATCH_H_MM,
                facecolor=colour,
                edgecolor="#555555",
                linewidth=0.2,
            )
        )

    if layout.legend == "right":
        x0 = layout.map_box[2] + 4.0
        avail = layout.width_mm - RIGHT_MM - x0
        y = layout.map_box[3]
        for line in _wrap(spec.title, avail, pt):
            pieces.append(
                overlay.text(x0, y, line, va="top", ha="left", fontweight="bold", **text_kw)
            )
            y -= line_mm
        y -= 1.5
        for text, colour in zip(labels, colours, strict=True):
            pieces.append(swatch(x0, y, SWATCH_W_MM, colour))
            pieces.append(
                overlay.text(
                    x0 + SWATCH_W_MM + 2.0,
                    y - SWATCH_H_MM / 2,
                    text,
                    va="center",
                    ha="left",
                    **text_kw,
                )
            )
            y -= ROW_MM
        if spec.circles:
            y -= 2.5
            for line in _wrap(spec.circle_title or "", avail, pt):
                pieces.append(
                    overlay.text(x0, y, line, va="top", ha="left", fontweight="bold", **text_kw)
                )
                y -= line_mm
            y -= 1.0
            biggest = max(r for _, r in spec.circles)
            for text, r in spec.circles:
                cy = y - r
                pieces.append(
                    overlay.add_patch(
                        Circle(
                            (x0 + biggest, cy),
                            r,
                            facecolor=CIRCLE_FACE,
                            edgecolor=CIRCLE_EDGE,
                            linewidth=0.4,
                        )
                    )
                )
                pieces.append(
                    overlay.text(
                        x0 + 2 * biggest + 2.0, cy, text, va="center", ha="left", **text_kw
                    )
                )
                y -= 2 * r + 1.5
    else:
        n = len(labels)
        x_start = layout.map_box[0]
        width = layout.map_box[2] - layout.map_box[0]
        slot = width / max(n, 1)
        y = layout.map_box[1] - 6.0
        for line in _wrap(spec.title, width, pt):
            pieces.append(
                overlay.text(x_start, y, line, va="top", ha="left", fontweight="bold", **text_kw)
            )
            y -= line_mm
        y -= 1.0
        for i, (text, colour) in enumerate(zip(labels, colours, strict=True)):
            pieces.append(swatch(x_start + i * slot + 0.5, y, slot - 1.0, colour))
            pieces.append(
                overlay.text(
                    x_start + (i + 0.5) * slot,
                    y - SWATCH_H_MM - 0.8,
                    text,
                    va="top",
                    ha="center",
                    **text_kw,
                )
            )
        if spec.circles:
            y -= SWATCH_H_MM + 0.8 + line_mm + 2.0
            biggest = max(r for _, r in spec.circles)
            x = x_start
            pieces.append(
                overlay.text(
                    x, y, spec.circle_title or "", va="top", ha="left", fontweight="bold", **text_kw
                )
            )
            x += _text_width_mm(spec.circle_title or "", pt) + 6.0
            cy = y - biggest - 1.0
            for text, r in spec.circles:
                pieces.append(
                    overlay.add_patch(
                        Circle(
                            (x + r, cy),
                            r,
                            facecolor=CIRCLE_FACE,
                            edgecolor=CIRCLE_EDGE,
                            linewidth=0.4,
                        )
                    )
                )
                pieces.append(
                    overlay.text(x + 2 * r + 1.5, cy, text, va="center", ha="left", **text_kw)
                )
                x += 2 * r + 1.5 + _text_width_mm(text, pt) + 6.0
    canvas.artists["legend"] = pieces
    return {"legend": pieces}


def draw_choropleth(
    canvas: MapFigure, units, facecolors, *, edgecolor: str = "#555555", linewidth: float = 0.25
) -> None:
    """Fill the units (GeoDataFrame, lon/lat unless it has a CRS) with `facecolors` (one per row, RGBA or names), projected like the map."""
    if units.crs is None:
        units = units.set_crs("EPSG:4326")
    units.to_crs(canvas.frame.crs).plot(
        ax=canvas.ax, color=list(facecolors), edgecolor=edgecolor, linewidth=linewidth, zorder=2
    )
    canvas.ax.set_xlim(canvas.frame.bounds[0], canvas.frame.bounds[1])
    canvas.ax.set_ylim(canvas.frame.bounds[2], canvas.frame.bounds[3])


def draw_circles(canvas: MapFigure, lon, lat, radii_mm) -> object:
    """Circles of the given radii (mm on paper) centred on (lon, lat) over the map, largest first so that the small ones stay visible."""
    radii = np.asarray(radii_mm, dtype="float64")
    order = np.argsort(-radii)
    diameter_pt = 2.0 * radii[order] / PT_MM
    x, y = canvas.to_xy(
        np.asarray(lon, dtype="float64")[order], np.asarray(lat, dtype="float64")[order]
    )
    return canvas.ax.scatter(
        x,
        y,
        s=diameter_pt**2,
        facecolors=CIRCLE_FACE,
        edgecolors=CIRCLE_EDGE,
        linewidths=0.4,
        zorder=6,
    )


__all__: Sequence[str] = (
    "FULL_WIDTH_MM",
    "HALF_WIDTH_MM",
    "NO_DATA_LABEL",
    "ClassedLegend",
    "MapCanvas",
    "MapFigure",
    "MapFrame",
    "circle_radius_mm",
    "colormap_for",
    "country_extent",
    "draw_choropleth",
    "draw_circles",
    "draw_classed_legend",
    "geographic_aspect",
    "legend_space",
    "make_frame",
    "new_map",
    "nice_values_below",
    "raster_map",
    "resolution_note",
    "robust_norm",
    "save_png",
)
