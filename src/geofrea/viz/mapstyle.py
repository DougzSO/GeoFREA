"""One cartographic style for every GeoFREA map (COMMAND 56): print sizes in mm, fonts at print size, geographic aspect, extent from the
country geometry, compass rose and scale bar placed where the map is emptiest, neighbours in light grey, one colormap per kind of
variable, robust colour limits, PNG at 300 dpi.

Nothing here computes a result and no existing figure uses it yet (`docs/figures/inventory.md` lists what will move to it).

Everything is laid out in millimetres on a figure whose size is exact: an overlay axes covers the figure with 1 unit = 1 mm, so the
fonts (pt) and the furniture (compass, scale bar, text box) have their true print size and their boxes can be tested.

Credit: the 8-triangle compass rose and the alternating-segment scale bar follow the logic of `scripts/article_map_utils.py`
(`compass`, `scale_bar`) of the craei-brazil repository (same author), redrawn here in millimetres instead of degrees.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import ticker
from matplotlib.colors import LogNorm, Normalize, PowerNorm
from matplotlib.figure import Figure
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.patches import Rectangle
from shapely.geometry import box as shapely_box

from geofrea.core.geo_utils import get_contiguous_mainland_gdf
from geofrea.core.geodesy import wgs84_km_per_degree

Extent = tuple[float, float, float, float]  # (west, east, south, north) in degrees
BoxMm = tuple[
    float, float, float, float
]  # (x0, y0, x1, y1) in millimetres from the lower left of the figure

# ------------------------------------------------------------------------------------------------------------------------- constants

FULL_WIDTH_MM = 190.0
HALF_WIDTH_MM = 90.0
MAX_HEIGHT_MM = 230.0
DPI = 300
EXTENT_MARGIN = 0.03
PT_MM = 25.4 / 72.0

FONT_FAMILY = "DejaVu Sans"
TITLE_PT, LABEL_PT, LEGEND_PT = 10.0, 8.0, 8.0

NEIGHBOUR_COLOUR = "#ececec"
SEA_COLOUR = "white"
OUTLINE_COLOUR = "#222222"
NO_DATA_COLOUR = "#d9d9d9"

COLORMAPS = {  # one colormap per kind of variable, the same in every country
    "potential": "viridis",
    "energy": "viridis",
    "capacity_factor": "magma",
    "delta": "RdBu",
    "delta_alt": "BrBG",
}
SKEW_LIMIT = 20.0  # P98 / P50 above this: logarithmic or power norm
CLIP_PERCENTILES = (2.0, 98.0)

LEFT_MM, RIGHT_MM, HEADER_MM, BOTTOM_MM = 14.0, 3.0, 13.0, 8.0
LEGEND_SIDE_MM, LEGEND_BELOW_MM = 26.0, 15.5
COLORBAR_MM = 3.5
PAD_MM = 2.0  # clear space around a placed element
OCCUPANCY_TOLERANCE = 0.01  # a corner with more occupied share than this is not free
COMPASS_MM = 10.0
CORNERS = ("lower left", "upper right", "lower right", "upper left")  # order of preference on ties

_RC = {
    "font.family": FONT_FAMILY,
    "font.size": LABEL_PT,
    "axes.titlesize": TITLE_PT,
    "axes.labelsize": LABEL_PT,
    "xtick.labelsize": LABEL_PT,
    "ytick.labelsize": LABEL_PT,
    "legend.fontsize": LEGEND_PT,
    "axes.linewidth": 0.4,
    "xtick.major.width": 0.4,
    "ytick.major.width": 0.4,
    "xtick.major.size": 2.0,
    "ytick.major.size": 2.0,
    "savefig.dpi": DPI,
    "figure.dpi": DPI,
}


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


# --------------------------------------------------------------------------------------------------------------- colour and normalisation


def colormap_for(kind: str) -> str:
    """The colormap of a kind of variable (`potential`, `energy`, `capacity_factor`, `delta`, `delta_alt`)."""
    return COLORMAPS[kind]


@dataclass(frozen=True)
class NormInfo:
    """The norm of a continuous map and how it was chosen."""

    norm: Normalize
    extend: str  # colorbar extend: neither, min, max, both
    vmin: float
    vmax: float
    kind: str  # linear, log, power or diverging
    skew: float  # P98 / P50 (inf when the median is not positive)


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
    below, above = bool((arr < vmin).any()), bool((arr > vmax).any())
    return "both" if below and above else "min" if below else "max" if above else "neither"


# ---------------------------------------------------------------------------------------------------------------------------- layout


@dataclass(frozen=True)
class Layout:
    """The figure in millimetres from the lower left corner."""

    width_mm: float
    height_mm: float
    map_box: BoxMm
    legend_box: BoxMm
    legend: str  # right or below
    header_box: BoxMm
    footer_mm: float  # extra strip under the map for furniture that found no free corner


def compute_layout(
    extent: Extent,
    width_mm: float = FULL_WIDTH_MM,
    footer_mm: float = 0.0,
    max_height_mm: float = MAX_HEIGHT_MM,
) -> Layout:
    """Figure size and boxes: the height follows the aspect of the extent; the legend is to the right of a tall map, below a wide one.

    A very tall country is limited to `max_height_mm`: the map gets narrower and is centred, the figure width stays `width_mm`.
    """
    ratio = map_height_over_width(extent)
    side = legend_position(extent) == "right"
    avail_w = width_mm - LEFT_MM - RIGHT_MM - (LEGEND_SIDE_MM if side else 0.0)
    fixed_h = HEADER_MM + BOTTOM_MM + footer_mm + (0.0 if side else LEGEND_BELOW_MM)
    map_w = min(avail_w, (max_height_mm - fixed_h) / ratio)
    map_h = map_w * ratio
    height = fixed_h + map_h
    x0 = LEFT_MM + (avail_w - map_w) / 2.0
    y0 = BOTTOM_MM + footer_mm + (0.0 if side else LEGEND_BELOW_MM)
    map_box = (x0, y0, x0 + map_w, y0 + map_h)
    if side:
        bar_x = x0 + map_w + 4.0
        legend_box = (bar_x, y0 + 0.1 * map_h, bar_x + COLORBAR_MM, y0 + 0.9 * map_h)
    else:
        bar_y = footer_mm + 9.0  # under the bar: its tick labels and its name
        legend_box = (x0 + 0.15 * map_w, bar_y, x0 + 0.85 * map_w, bar_y + COLORBAR_MM)
    header_box = (0.0, height - HEADER_MM, width_mm, height)
    return Layout(
        width_mm, height, map_box, legend_box, "right" if side else "below", header_box, footer_mm
    )


# ------------------------------------------------------------------------------------------------------------------------ furniture


def nice_length_km(target_km: float) -> float:
    """The 1, 2 or 5 times a power of ten closest to `target_km` (closest in ratio, so it is never more than 1.6 times off)."""
    if target_km <= 0:
        raise ValueError("target length must be positive")
    exponent = math.floor(math.log10(target_km))
    candidates = [m * 10.0 ** (exponent + e) for e in (0, 1) for m in (1.0, 2.0, 5.0)]
    return min(candidates, key=lambda c: abs(math.log(c / target_km)))


def scale_bar_length_km(extent: Extent, share: float = 0.20) -> float:
    """Rounded length (1, 2 or 5 x 10^n km) closest to `share` of the map width, measured at the central latitude."""
    _, lon_km = wgs84_km_per_degree(np.array([0.5 * (extent[2] + extent[3])]))
    width_km = (extent[1] - extent[0]) * float(lon_km[0])
    return nice_length_km(share * width_km)


def _text_width_mm(text: str, pt: float) -> float:
    return (
        len(text) * pt * PT_MM * 0.62
    )  # average advance of the sans family; the tests measure the real box


@dataclass(frozen=True)
class Furniture:
    """An element of the map placed in the figure: its name, the box it occupies (padding included) and where it sits."""

    name: str
    box: BoxMm
    where: str  # a corner name, or `outside`


def _element_size_mm(
    name: str, map_w_mm: float, extent: Extent, total_text: str | None
) -> tuple[float, float]:
    if name == "compass":
        return COMPASS_MM + 2 * PAD_MM, COMPASS_MM + 3.5 + 2 * PAD_MM  # arms plus the "N" above
    if name == "scale_bar":
        km = scale_bar_length_km(extent)
        _, lon_km = wgs84_km_per_degree(np.array([0.5 * (extent[2] + extent[3])]))
        length = km / ((extent[1] - extent[0]) * float(lon_km[0])) * map_w_mm
        label = _text_width_mm(f"{km:g} km", LEGEND_PT)
        return (
            length + label / 2.0 + label / 2.0 + 2 * PAD_MM,
            1.8 + 1.0 + LEGEND_PT * PT_MM + 2 * PAD_MM,
        )
    text = total_text or ""
    lines = text.split("\n")
    return max(_text_width_mm(s, LEGEND_PT) for s in lines) + 4.0 + 2 * PAD_MM, len(
        lines
    ) * LEGEND_PT * PT_MM * 1.25 + 2.0 + 2 * PAD_MM


def corner_box(
    corner: str, size_mm: tuple[float, float], map_box: BoxMm, inset_mm: float = 1.0
) -> BoxMm:
    """The box of an element of `size_mm` in `corner` of the map (figure millimetres)."""
    x0, y0, x1, y1 = map_box
    w, h = size_mm
    left = x0 + inset_mm if "left" in corner else x1 - inset_mm - w
    bottom = y0 + inset_mm if "lower" in corner else y1 - inset_mm - h
    return (left, bottom, left + w, bottom + h)


def occupancy(
    box: BoxMm,
    map_box: BoxMm,
    extent: Extent,
    *,
    data_mask: np.ndarray | None = None,
    polygon=None,
) -> float:
    """Share of `box` that holds data or country: the larger of the data-pixel share and the polygon share.

    `data_mask` is a boolean grid over `extent` (row 0 north) that is True where a pixel has data; `polygon` is the country in lon/lat.
    """
    mx0, my0, mx1, my1 = map_box
    west, east, south, north = extent
    fx0, fx1 = (box[0] - mx0) / (mx1 - mx0), (box[2] - mx0) / (mx1 - mx0)
    fy0, fy1 = (box[1] - my0) / (my1 - my0), (box[3] - my0) / (my1 - my0)
    shares = [0.0]
    if data_mask is not None and data_mask.size:
        ny, nx = data_mask.shape
        c0, c1 = math.floor(max(fx0, 0.0) * nx), math.ceil(min(fx1, 1.0) * nx)
        r0, r1 = math.floor((1 - min(fy1, 1.0)) * ny), math.ceil((1 - max(fy0, 0.0)) * ny)
        sub = data_mask[r0:r1, c0:c1]
        if sub.size:
            shares.append(float(sub.mean()))
    if polygon is not None:
        window = shapely_box(
            west + fx0 * (east - west),
            south + fy0 * (north - south),
            west + fx1 * (east - west),
            south + fy1 * (north - south),
        )
        shares.append(float(polygon.intersection(window).area / window.area))
    return max(shares)


def place_furniture(
    layout: Layout,
    extent: Extent,
    *,
    data_mask: np.ndarray | None,
    polygon,
    total_text: str | None,
) -> dict[str, Furniture]:
    """Put the scale bar, the compass rose and (if given) the total box each in the free corner with the least occupancy.

    The corners are tried by the occupancy of the box the element actually fills (data pixels and country polygon). Elements go to the free corner with the least stacked, largest first, and may share a corner by stacking; when the best corner is not free (above `OCCUPANCY_TOLERANCE`) it goes outside the map: the compass in
    the header, the others in the footer strip, which the layout then reserves.
    """
    map_w = layout.map_box[2] - layout.map_box[0]
    names = ["scale_bar", "compass"] + (["total"] if total_text else [])
    stacked: dict[
        str, float
    ] = {}  # height already used in each corner, so that elements can share a free corner
    placed: dict[str, Furniture] = {}
    for name in names:
        size = _element_size_mm(name, map_w, extent, total_text)
        scored = []
        for order, corner in enumerate(CORNERS):
            used = stacked.get(corner, 0.0)
            box = corner_box(corner, size, layout.map_box)
            shift = used if "lower" in corner else -used
            box = (box[0], box[1] + shift, box[2], box[3] + shift)
            if box[1] < layout.map_box[1] or box[3] > layout.map_box[3]:
                continue
            scored.append(
                (
                    occupancy(box, layout.map_box, extent, data_mask=data_mask, polygon=polygon),
                    used,
                    order,
                    corner,
                    box,
                )
            )
        scored.sort(key=lambda s: (s[0] > OCCUPANCY_TOLERANCE, s[1], s[0], s[2]))
        if scored and scored[0][0] <= OCCUPANCY_TOLERANCE:
            _, used, _, corner, box = scored[0]
            stacked[corner] = used + size[1]
            placed[name] = Furniture(name, box, corner)
        else:
            placed[name] = Furniture(name, (0.0, 0.0, size[0], size[1]), "outside")
    return placed


def _rebase(el: Furniture, old: Layout, new: Layout) -> Furniture:
    """The same element at the same place of the map after the layout grew a footer (the map moved up by the difference)."""
    dx, dy = new.map_box[0] - old.map_box[0], new.map_box[1] - old.map_box[1]
    return Furniture(
        el.name, (el.box[0] + dx, el.box[1] + dy, el.box[2] + dx, el.box[3] + dy), el.where
    )


def _outside_boxes(placed: dict[str, Furniture], layout: Layout) -> dict[str, Furniture]:
    """Final boxes of the elements that sit outside the map: the compass at the right end of the header, the rest left to right in the footer."""
    out = dict(placed)
    x_footer = layout.map_box[0]
    for name, el in placed.items():
        if el.where != "outside":
            continue
        w, h = el.box[2] - el.box[0], el.box[3] - el.box[1]
        if name == "compass":
            x1 = layout.width_mm - 1.0
            box = (x1 - w, layout.height_mm - h - 1.0, x1, layout.height_mm - 1.0)
        else:
            box = (x_footer, 0.5, x_footer + w, 0.5 + h)
            x_footer += w + 2.0
        out[name] = Furniture(name, box, "outside")
    return out


def draw_compass(overlay, box: BoxMm) -> list:
    """Eight-triangle compass rose (cardinal points, each split into a dark and a light half) with an N above, inside `box`.

    Logic of `compass` in craei-brazil `scripts/article_map_utils.py`; the size here is millimetres, not a share of the extent.
    """
    x0, y0, x1, _ = box
    h = COMPASS_MM / 2.0
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
            fontsize=LEGEND_PT,
            weight="bold",
            ha="center",
            va="bottom",
            zorder=11,
        )
    )
    return artists


def draw_scale_bar(overlay, box: BoxMm, extent: Extent, map_w_mm: float) -> list:
    """Four alternating segments labelled 0, half and full length in km, calculated at the central latitude (craei-brazil `scale_bar`)."""
    km = scale_bar_length_km(extent)
    _, lon_km = wgs84_km_per_degree(np.array([0.5 * (extent[2] + extent[3])]))
    length = km / ((extent[1] - extent[0]) * float(lon_km[0])) * map_w_mm
    seg = length / 4.0
    x0 = box[0] + PAD_MM + _text_width_mm(f"{km:g} km", LEGEND_PT) / 2.0
    y0 = box[1] + PAD_MM + LEGEND_PT * PT_MM + 1.0
    artists: list = [
        overlay.add_patch(
            Rectangle((x0 + i * seg, y0), seg, 1.8, fc=fc, ec="black", lw=0.4, zorder=10)
        )
        for i, fc in enumerate(["black", "white", "black", "white"])
    ]
    label_w = _text_width_mm(f"{km:g} km", LEGEND_PT)
    labels = [(0.0, "0"), (1.0, f"{km:g} km")]
    if (
        length / 2.0 >= 1.2 * label_w
    ):  # the middle label only when it does not run into its neighbours
        labels.insert(1, (0.5, f"{km / 2:g}"))
    for frac, text in labels:
        artists.append(
            overlay.text(
                x0 + frac * length,
                y0 - 0.6,
                text,
                fontsize=LEGEND_PT,
                ha="center",
                va="top",
                zorder=10,
            )
        )
    return artists


# ------------------------------------------------------------------------------------------------------------------------- the canvas


@dataclass
class MapCanvas:
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

    def mm_to_fig(self, box: BoxMm) -> tuple[float, float, float, float]:
        w, h = self.layout.width_mm, self.layout.height_mm
        return box[0] / w, box[1] / h, (box[2] - box[0]) / w, (box[3] - box[1]) / h


def format_title(iso: str, technology: str, variable: str) -> str:
    """The short title: `<ISO> · <Technology> · <Variable>`."""
    return f"{iso} · {technology} · {variable}"


def new_map(
    geometry,
    *,
    iso: str,
    technology: str,
    variable: str,
    subtitle: str = "",
    total_text: str | None = None,
    width_mm: float = FULL_WIDTH_MM,
    neighbours=None,
    data_mask: np.ndarray | None = None,
    extent: Extent | None = None,
    contiguous: bool = True,
    grid_mask: tuple[np.ndarray, Extent] | None = None,
) -> MapCanvas:
    """Axes, legend slot, title and furniture of a map of the country `geometry` (lon/lat), ready to receive the data.

    The extent comes from the country geometry (+3% margin, far islands out) unless given. `neighbours` is a GeoDataFrame drawn in very
    light grey under everything; the sea stays white. `data_mask` (True where a pixel has data, over `extent`, row 0 north; or `grid_mask` = (mask, its extent) to have it resampled) and the
    country polygon decide the free corner of the compass and the scale bar. Draw the data on `canvas.ax` and the colour bar on
    `canvas.cax` (`add_colorbar`), then save with `save_png`.
    """
    polygon = contiguous_geometry(geometry) if contiguous else _as_geometry(geometry)
    extent = extent or country_extent(polygon, contiguous=False)
    if grid_mask is not None:
        data_mask = mask_on_extent(grid_mask[0], grid_mask[1], extent)
    layout0 = compute_layout(extent, width_mm)
    placed = place_furniture(
        layout0, extent, data_mask=data_mask, polygon=polygon, total_text=total_text
    )
    footer = max(
        (
            el.box[3] - el.box[1] + 1.0
            for n, el in placed.items()
            if el.where == "outside" and n != "compass"
        ),
        default=0.0,
    )
    layout = compute_layout(extent, width_mm, footer_mm=footer)
    placed = _outside_boxes(
        {
            n: (el if el.where == "outside" else _rebase(el, layout0, layout))
            for n, el in placed.items()
        },
        layout,
    )

    with plt.rc_context(_RC):
        fig = plt.figure(
            figsize=(layout.width_mm / 25.4, layout.height_mm / 25.4), dpi=DPI, facecolor="white"
        )
        canvas = MapCanvas(fig, None, None, None, layout, extent, placed)
        ax = fig.add_axes(canvas.mm_to_fig(layout.map_box))
        ax.set_facecolor(SEA_COLOUR)
        cax = fig.add_axes(canvas.mm_to_fig(layout.legend_box))
        overlay = fig.add_axes((0, 0, 1, 1), facecolor="none")
        overlay.set_xlim(0, layout.width_mm)
        overlay.set_ylim(0, layout.height_mm)
        overlay.axis("off")
        overlay.set_zorder(5)
        canvas.ax, canvas.cax, canvas.overlay = ax, cax, overlay

        ax.set_xlim(extent[0], extent[1])
        ax.set_ylim(extent[2], extent[3])
        ax.set_aspect(geographic_aspect(extent))
        ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=4, steps=[1, 2, 5, 10]))
        ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=4, steps=[1, 2, 5, 10]))
        ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: format_degrees(v, "lon")))
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: format_degrees(v, "lat")))
        ax.tick_params(labelsize=LABEL_PT, pad=1.5)
        for spine in ax.spines.values():
            spine.set_linewidth(0.4)
            spine.set_color("#888888")
        if neighbours is not None:
            neighbours.plot(
                ax=ax, color=NEIGHBOUR_COLOUR, edgecolor="white", linewidth=0.3, zorder=0.5
            )
        import geopandas as gpd

        gpd.GeoSeries([polygon], crs="EPSG:4326").boundary.plot(
            ax=ax, color=OUTLINE_COLOUR, linewidth=0.5, zorder=4
        )
        ax.set_xlim(extent[0], extent[1])
        ax.set_ylim(extent[2], extent[3])

        canvas.texts["title"] = overlay.text(
            2.0,
            layout.height_mm - 2.0,
            format_title(iso, technology, variable),
            fontsize=TITLE_PT,
            fontweight="bold",
            ha="left",
            va="top",
        )
        if subtitle:
            canvas.texts["subtitle"] = overlay.text(
                2.0,
                layout.height_mm - 2.0 - TITLE_PT * PT_MM * 1.35,
                subtitle,
                fontsize=LABEL_PT,
                color="#444444",
                ha="left",
                va="top",
            )
        map_w = layout.map_box[2] - layout.map_box[0]
        canvas.artists["scale_bar"] = draw_scale_bar(
            overlay, placed["scale_bar"].box, extent, map_w
        )
        canvas.artists["compass"] = draw_compass(overlay, placed["compass"].box)
        if total_text:
            box = placed["total"].box
            total_artist = overlay.text(
                box[0] + PAD_MM + 1.0,
                box[1] + PAD_MM + 1.0,
                total_text,
                fontsize=LEGEND_PT,
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
    return canvas


def add_colorbar(canvas: MapCanvas, mappable, label: str, extend: str = "neither"):
    """The colour bar in the legend slot: vertical to the right of a tall map, horizontal below a wide one."""
    orientation = "vertical" if canvas.layout.legend == "right" else "horizontal"
    with plt.rc_context(_RC):
        bar = canvas.fig.colorbar(mappable, cax=canvas.cax, orientation=orientation, extend=extend)
        bar.outline.set_linewidth(0.3)
        bar.ax.tick_params(labelsize=LEGEND_PT, width=0.4, length=2.0)
        if orientation == "vertical":
            bar.set_label(label, fontsize=LEGEND_PT)
        else:
            bar.set_label(label, fontsize=LEGEND_PT, labelpad=1.0)
    return bar


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
    subtitle: str = "",
    total_text: str | None = None,
    width_mm: float = FULL_WIDTH_MM,
    neighbours=None,
    diverging_center: float = 0.0,
) -> MapCanvas:
    """A continuous raster map in the common style: robust norm, the colormap of `kind`, extend where needed, furniture in free corners."""
    data = np.ma.masked_invalid(grid)
    diverging = kind.startswith("delta")
    info = robust_norm(data.compressed(), diverging=diverging, center=diverging_center)
    canvas = new_map(
        geometry,
        iso=iso,
        technology=technology,
        variable=variable,
        subtitle=subtitle,
        total_text=total_text,
        width_mm=width_mm,
        neighbours=neighbours,
        data_mask=None,
        grid_mask=(~np.ma.getmaskarray(data), extent_grid),
    )
    image = canvas.ax.imshow(
        data,
        extent=extent_grid,
        origin="upper",
        cmap=colormap_for(kind),
        norm=info.norm,
        interpolation="nearest",
        zorder=2,
        aspect=geographic_aspect(canvas.extent),
    )
    canvas.ax.set_xlim(canvas.extent[0], canvas.extent[1])
    canvas.ax.set_ylim(canvas.extent[2], canvas.extent[3])
    add_colorbar(canvas, image, label, info.extend)
    return canvas


def mask_on_extent(
    mask: np.ndarray, grid_extent: Extent, map_extent: Extent, size: int = 300
) -> np.ndarray:
    """The data mask of a grid sampled over the map extent (row 0 north); False where the map reaches beyond the grid."""
    gw, ge, gs, gn = grid_extent
    mw, me, ms, mn = map_extent
    ny, nx = mask.shape
    xs = mw + (np.arange(size) + 0.5) / size * (me - mw)
    ys = mn - (np.arange(size) + 0.5) / size * (mn - ms)
    cols = np.floor((xs - gw) / (ge - gw) * nx).astype(int)
    rows = np.floor((gn - ys) / (gn - gs) * ny).astype(int)
    inside = ((rows >= 0) & (rows < ny))[:, None] & ((cols >= 0) & (cols < nx))[None, :]
    out = np.zeros((size, size), dtype=bool)
    out[inside] = mask[np.clip(rows, 0, ny - 1)[:, None], np.clip(cols, 0, nx - 1)[None, :]][inside]
    return out


def save_png(canvas_or_fig, path: Path) -> Path:
    """Write the figure as PNG at 300 dpi and its exact print size, with no software tag. Only PNG is written."""
    path = Path(path)
    if path.suffix.lower() != ".png":
        raise ValueError(f"maps are written as PNG only, got {path.suffix!r}")
    fig = canvas_or_fig.fig if isinstance(canvas_or_fig, MapCanvas) else canvas_or_fig
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, facecolor="white", metadata={"Software": None})
    plt.close(fig)
    return path


__all__: Sequence[str] = (
    "FULL_WIDTH_MM",
    "HALF_WIDTH_MM",
    "MapCanvas",
    "colormap_for",
    "country_extent",
    "geographic_aspect",
    "new_map",
    "raster_map",
    "robust_norm",
    "save_png",
)
