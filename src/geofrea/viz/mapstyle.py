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

from geofrea.core.geo_utils import get_contiguous_mainland_gdf
from geofrea.core.geodesy import wgs84_km_per_degree

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


NEIGHBOUR_COLOUR = "#ececec"
SEA_COLOUR = "white"
OUTLINE_COLOUR = "#222222"
NO_DATA_COLOUR = (
    "#bdbdbd"  # "no potential": a medium grey that is neither the neighbours (#ececec) nor the sea
)

COLORMAPS = {  # one colormap per kind of variable, the same in every country
    "potential": "viridis",
    "energy": "viridis",
    "capacity_factor": "magma",
    "delta": "RdBu",
    "delta_alt": "BrBG",
}
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
    width_mm: float, title: str, subtitle: str, preset: Preset = THESIS
) -> tuple[list[str], list[str], float]:
    """The title and subtitle wrapped to the room the compass rose leaves, and the height of the header that holds them and the rose."""
    room = width_mm - 2.0 - compass_size_mm(preset)[0] - 3.0
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


def compute_layout(
    extent: Extent,
    width_mm: float = FULL_WIDTH_MM,
    footer_mm: float = 0.0,
    max_height_mm: float = MAX_HEIGHT_MM,
    legend_side_mm: float | None = None,
    legend_below_mm: float | None = None,
    header_mm: float = HEADER_MM,
) -> Layout:
    """Figure size and boxes: the height follows the aspect of the extent; the legend is to the right of a tall map, below a wide one.

    A very tall country is limited to `max_height_mm`: the map gets narrower and is centred, the figure width stays `width_mm`.
    The colour bar has the height of the map (right) or 70% of its width (below).
    """
    ratio = map_height_over_width(extent)
    side = legend_position(extent) == "right"
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
    if side:
        bar_x = x0 + map_w + 4.0
        legend_box = (bar_x, y0, bar_x + COLORBAR_MM, y0 + map_h)
    else:
        bar_y = footer_mm + 9.0  # under the bar: its tick labels and its name
        legend_box = (x0 + 0.15 * map_w, bar_y, x0 + 0.85 * map_w, bar_y + COLORBAR_MM)
    header_box = (0.0, height - header_mm, width_mm, height)
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


def _scale_bar_length_mm(extent: Extent, map_w_mm: float) -> float:
    _, lon_km = wgs84_km_per_degree(np.array([0.5 * (extent[2] + extent[3])]))
    return scale_bar_length_km(extent) / ((extent[1] - extent[0]) * float(lon_km[0])) * map_w_mm


@dataclass(frozen=True)
class Furniture:
    """An element of the figure outside the map: its name, the box it occupies (padding included) and the strip it sits in."""

    name: str
    box: BoxMm
    where: str  # header or footer


def footer_item_sizes(
    extent: Extent,
    map_w_mm: float,
    total_text: str | None,
    source: str | None,
    preset: Preset = THESIS,
) -> dict[str, tuple[float, float]]:
    """Size in mm (padding included) of what the footer holds, in reading order: scale bar, box of totals, source."""
    pt = preset.legend_pt
    label = _text_width_mm(f"{scale_bar_length_km(extent):g} km", pt)
    sizes = {
        "scale_bar": (
            _scale_bar_length_mm(extent, map_w_mm)
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
    overlay, box: BoxMm, extent: Extent, map_w_mm: float, preset: Preset = THESIS
) -> list:
    """Four alternating segments labelled 0, half and full length in km, calculated at the central latitude (craei-brazil `scale_bar`)."""
    pt = preset.legend_pt
    km = scale_bar_length_km(extent)
    length = _scale_bar_length_mm(extent, map_w_mm)
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

    def mm_to_fig(self, box: BoxMm) -> tuple[float, float, float, float]:
        w, h = self.layout.width_mm, self.layout.height_mm
        return box[0] / w, box[1] / h, (box[2] - box[0]) / w, (box[3] - box[1]) / h


MapCanvas = MapFigure  # the name before COMMAND 66


def format_title(country: str, technology: str, variable: str) -> str:
    """The short title: `<Country> · <Technology> · <Variable>` (the technology is left out for a map that has none)."""
    return " · ".join(p for p in (country, technology, variable) if p)


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
) -> MapFigure:
    """Axes, legend slot, title and furniture of a map of the country `geometry` (lon/lat), ready to receive the data.

    The extent comes from the country geometry (+3% margin, far islands out) unless given. `preset` gives the fonts and, unless
    `width_mm` is given, the width. `neighbours` is a GeoDataFrame drawn in very light grey under everything; the sea stays white. Draw the
    data on `canvas.ax` and the colour bar on `canvas.cax` (`add_colorbar`), then save with `save_png`.
    """
    pre = get_preset(preset)
    width_mm = pre.width_mm if width_mm is None else width_mm
    polygon = contiguous_geometry(geometry) if contiguous else _as_geometry(geometry)
    extent = extent or country_extent(polygon, contiguous=False)
    title = format_title(country or iso, technology, variable)
    if total_text:
        total_text = wrap_total_text(
            total_text, width_mm - LEFT_MM - RIGHT_MM - 2 * PAD_MM - 4.0, pre.legend_pt
        )
    title_lines, sub_lines, header_mm = header_text(width_mm, title, subtitle, pre)

    def layout_for(footer: float) -> Layout:
        return compute_layout(
            extent,
            width_mm,
            footer_mm=footer,
            legend_side_mm=legend_side_mm,
            legend_below_mm=legend_below_mm,
            header_mm=header_mm,
        )

    # The footer height depends on the width of the scale bar, which depends on the map width, which depends on the footer height when the
    # map is limited by the height of the sheet. The footer only shrinks the map, so the second pass cannot need more room than the first.
    layout = layout_for(0.0)
    sizes = footer_item_sizes(
        extent, layout.map_box[2] - layout.map_box[0], total_text, source, pre
    )
    _, footer = plan_footer(sizes, LEFT_MM, width_mm - RIGHT_MM)
    layout = layout_for(footer)
    sizes = footer_item_sizes(
        extent, layout.map_box[2] - layout.map_box[0], total_text, source, pre
    )
    boxes, _ = plan_footer(sizes, LEFT_MM, width_mm - RIGHT_MM)
    cw, ch = compass_size_mm(pre)
    compass_box = (
        width_mm - 1.0 - cw,
        layout.height_mm - 1.0 - ch,
        width_mm - 1.0,
        layout.height_mm - 1.0,
    )
    placed = {"compass": Furniture("compass", compass_box, "header")}
    placed.update({n: Furniture(n, b, "footer") for n, b in boxes.items()})

    with plt.rc_context(_rc(pre)):
        fig = plt.figure(
            figsize=(layout.width_mm / 25.4, layout.height_mm / 25.4), dpi=DPI, facecolor="white"
        )
        canvas = MapFigure(fig, None, None, None, layout, extent, placed, preset=pre)
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
        ax.tick_params(labelsize=pre.label_pt, pad=1.5)
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
            overlay, placed["scale_bar"].box, extent, map_w, pre
        )
        canvas.artists["compass"] = draw_compass(overlay, placed["compass"].box, pre)
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
    with plt.rc_context(_rc(canvas.preset)):
        bar = canvas.fig.colorbar(mappable, cax=canvas.cax, orientation=orientation, extend=extend)
        bar.outline.set_linewidth(0.3)
        bar.ax.tick_params(labelsize=pt, width=0.4, length=2.0)
        if orientation == "vertical":
            bar.set_label(label, fontsize=pt)
        else:
            bar.set_label(label, fontsize=pt, labelpad=1.0)
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
    width_mm: float | None = None,
    preset: str | Preset | None = "thesis",
    neighbours=None,
    diverging_center: float = 0.0,
    country: str | None = None,
) -> MapFigure:
    """A continuous raster map in the common style: robust norm, the colormap of `kind`, extend where needed."""
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
        preset=preset,
        neighbours=neighbours,
        country=country,
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


def save_png(canvas_or_fig, path: Path) -> Path:
    """Write the figure as PNG at 300 dpi and its exact print size, with no software tag. Only PNG is written."""
    path = Path(path)
    if path.suffix.lower() != ".png":
        raise ValueError(f"maps are written as PNG only, got {path.suffix!r}")
    fig = canvas_or_fig.fig if isinstance(canvas_or_fig, MapFigure) else canvas_or_fig
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, facecolor="white", metadata={"Software": None})
    plt.close(fig)
    return path


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
    below = 15.5 + (2 * biggest + 8.0 if spec.circles else 0.0)
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
    colours = list(spec.colours) + (["#d9d9d9"] if spec.no_value_label else [])
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
        y = layout.map_box[1] - 4.0
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
    """Fill the units (GeoDataFrame in lon/lat) with `facecolors` (one per row, RGBA or names) on the map axes."""
    units.plot(
        ax=canvas.ax, color=list(facecolors), edgecolor=edgecolor, linewidth=linewidth, zorder=2
    )
    canvas.ax.set_xlim(canvas.extent[0], canvas.extent[1])
    canvas.ax.set_ylim(canvas.extent[2], canvas.extent[3])


def draw_circles(canvas: MapFigure, lon, lat, radii_mm) -> object:
    """Circles of the given radii (mm on paper) centred on (lon, lat) over the map, largest first so that the small ones stay visible."""
    radii = np.asarray(radii_mm, dtype="float64")
    order = np.argsort(-radii)
    diameter_pt = 2.0 * radii[order] / PT_MM
    return canvas.ax.scatter(
        np.asarray(lon, dtype="float64")[order],
        np.asarray(lat, dtype="float64")[order],
        s=diameter_pt**2,
        facecolors=CIRCLE_FACE,
        edgecolors=CIRCLE_EDGE,
        linewidths=0.4,
        zorder=6,
    )


__all__: Sequence[str] = (
    "FULL_WIDTH_MM",
    "HALF_WIDTH_MM",
    "ClassedLegend",
    "MapCanvas",
    "MapFigure",
    "circle_radius_mm",
    "colormap_for",
    "country_extent",
    "draw_choropleth",
    "draw_circles",
    "draw_classed_legend",
    "geographic_aspect",
    "legend_space",
    "new_map",
    "nice_values_below",
    "raster_map",
    "robust_norm",
    "save_png",
)
