"""Several maps of one country on one sheet, in the layout of `MapFigure` (COMMAND 68; spec v2 T-01 and T-09 to T-12).

A `PanelFigure` is the same grid as a `MapFigure` with `n_rows x n_cols` maps of the same country (same frame, same projection, same
size) instead of one: the title, the subtitle and the compass rose in the header, a caption over each map, the degrees only on the left
column and the bottom row, one colour bar (shared by all, or one under each map of a single row), and a footer with the scale bar, a note
and the source. The panels are drawn by the methods of `MapFigure` (`draw_raster`, `fill_country`), so a panel cuts the raster by the
country, copies the cells without interpolation and may be smoothed for display exactly as a single map is.

A map, a colour or a colour map keeps one meaning in the whole sheet (`use_colour`, `use_cmap`), and the sheet is saved with `mapstyle.save_png`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import numpy as np

from geofrea.viz import mapstyle as ms
from geofrea.viz.mapstyle import (
    BOTTOM_MM,
    COLORBAR_MM,
    LEFT_MM,
    NEIGHBOUR_COLOUR,
    OUTLINE_COLOUR,
    PAD_MM,
    PT_MM,
    RIGHT_MM,
    SEA_COLOUR,
    BoxMm,
    Furniture,
    MapFigure,
    Preset,
    draw_compass,
    draw_scale_bar,
    footer_item_sizes,
    get_preset,
    header_text,
    plan_footer,
    validate_label,
)

PANEL_GAP_MM = 3.0  # between two maps of a row
ROW_GAP_MM = 2.0  # between the bottom of a map and the caption of the next row
TICK_MM = 5.0  # the degrees under the bottom row
BAR_MM = 11.5  # a horizontal colour bar with its numbers and its name
MAX_SHEET_MM = 250.0
STIPPLE_MM = 1.8  # the distance between two dots of the stipple, on paper
STIPPLE_COLOUR = "#111111"


@dataclass
class Panel:
    """One map of the sheet: its axes, the frame it shares with the others and its box in millimetres. It draws like a `MapFigure`."""

    ax: object
    frame: ms.MapFrame
    layout: SimpleNamespace
    caption: object
    parent: PanelFigure
    index: int
    no_data_label: str | None = None

    pixel_m = MapFigure.pixel_m
    px_per_cell = MapFigure.px_per_cell
    draw_raster = MapFigure.draw_raster
    fill_country = MapFigure.fill_country
    to_xy = MapFigure.to_xy

    def use_colour(self, colour, meaning: str) -> None:
        self.parent.use_colour(colour, meaning)

    def stipple(self, mask, extent_grid: ms.Extent, label: str | None = None):
        """Dots over the cells where `mask` (a lon/lat grid like `draw_raster`'s, True = mark) holds, on a regular lattice clipped by the
        country: the agreement (or the lack of it) of an ensemble. `label` is what the dots mean (a footer note is the caller's)."""
        import shapely

        frame = self.frame
        step_m = frame.width_m / (self.layout.map_box[2] - self.layout.map_box[0]) * STIPPLE_MM
        grid, extent_m = ms.reproject_nearest(
            np.asarray(mask, dtype="float64"), extent_grid, frame, step_m
        )
        rows, cols = np.nonzero(np.nan_to_num(grid, nan=0.0) > 0.5)
        x = extent_m[0] + (cols + 0.5) * step_m
        y = extent_m[3] - (rows + 0.5) * step_m
        inside = shapely.contains_xy(frame.polygon, x, y)
        artist = self.ax.scatter(
            x[inside],
            y[inside],
            s=0.55,
            c=STIPPLE_COLOUR,
            marker="o",
            linewidths=0,
            zorder=3.5,
            rasterized=True,
        )
        self.ax.set_xlim(frame.bounds[0], frame.bounds[1])
        self.ax.set_ylim(frame.bounds[2], frame.bounds[3])
        return artist


@dataclass
class PanelFigure:
    """A sheet of maps under construction: `panels`, one colour bar slot per panel or one for all, `overlay` (1 unit = 1 mm) for the text."""

    fig: object
    overlay: object
    width_mm: float
    height_mm: float
    preset: Preset
    frame: ms.MapFrame
    panels: list[Panel] = field(default_factory=list)
    bars: list[object] = field(
        default_factory=list
    )  # the colour bar axes: one for all, or one per panel
    bar_boxes: list[BoxMm] = field(default_factory=list)
    furniture: dict[str, Furniture] = field(default_factory=dict)
    texts: dict[str, object] = field(default_factory=dict)
    artists: dict[str, list] = field(default_factory=dict)
    colours: dict[str, str] = field(default_factory=dict)
    cmaps: dict[str, str] = field(default_factory=dict)
    meta: dict[str, str] = field(default_factory=dict)
    footer_mm: float = 0.0
    grid_box: BoxMm = (0.0, 0.0, 0.0, 0.0)  # all the maps with their captions
    bar_mode: str = "shared"

    use_colour = MapFigure.use_colour
    use_cmap = MapFigure.use_cmap
    colour_problems = MapFigure.colour_problems
    mm_to_fig = MapFigure.mm_to_fig

    @property
    def layout(self) -> SimpleNamespace:  # what `png_metadata` and the tests ask of a figure
        return SimpleNamespace(width_mm=self.width_mm, height_mm=self.height_mm)


def panel_sizes(
    n_rows: int,
    n_cols: int,
    ratio: float,
    width_mm: float,
    header_mm: float,
    footer_mm: float,
    caption_mm: float,
    bar_mm: float,
    max_sheet_mm: float = MAX_SHEET_MM,
) -> tuple[float, float]:
    """Width and height in mm of one map: the widest that fits the sheet in width, narrower when the sheet would be taller than `max_sheet_mm`."""
    avail = width_mm - LEFT_MM - RIGHT_MM - (n_cols - 1) * PANEL_GAP_MM
    pw = avail / n_cols
    fixed = (
        header_mm
        + footer_mm
        + BOTTOM_MM
        + TICK_MM
        + bar_mm
        + n_rows * caption_mm
        + (n_rows - 1) * ROW_GAP_MM
    )
    ph_max = (max_sheet_mm - fixed) / n_rows
    if pw * ratio > ph_max:
        pw = ph_max / ratio
    return pw, pw * ratio


def new_panels(
    geometry,
    *,
    iso: str,
    variable: str,
    captions: list[str],
    n_rows: int,
    n_cols: int,
    technology: str = "",
    subtitle: str = "",
    total_text: str | None = None,
    width_mm: float | None = None,
    preset: str | Preset | None = "thesis",
    neighbours=None,
    extent: ms.Extent | None = None,
    contiguous: bool = True,
    country: str | None = None,
    source: str | None = ms.DEFAULT_SOURCE,
    lang: str = "en",
    no_data_label: str | None = None,
    graticule: bool = True,
    bar: str = "shared",
) -> PanelFigure:
    """The axes, the colour bar slots, the title and the furniture of `n_rows x n_cols` maps of the country `geometry` (lon/lat).

    `captions` has one text per map, in reading order (left to right, top to bottom); `bar` is `shared` (one horizontal colour bar under
    all the maps, for maps that share a scale) or `each` (one under each map, a single row, for maps of different variables) or `none`.
    The rest is as in `mapstyle.new_map`; the projection and the frame are those of `new_map` for the same country.
    """
    import geopandas as gpd

    if len(captions) != n_rows * n_cols:
        raise ValueError(
            f"{n_rows} x {n_cols} maps need {n_rows * n_cols} captions, got {len(captions)}"
        )
    if bar not in ("shared", "each", "none"):
        raise ValueError(f"bar is shared, each or none, got {bar!r}")
    if bar == "each" and n_rows != 1:
        raise ValueError("a colour bar under each map needs a single row of maps")
    pre = get_preset(preset)
    polygon = ms.contiguous_geometry(geometry) if contiguous else ms._as_geometry(geometry)
    frame = ms.make_frame(polygon, extent)
    ratio = frame.ratio
    title = ms.format_title(country or ms.country_name(iso, lang), technology, variable)
    validate_label(subtitle, "subtitle")
    for text in [*captions, total_text, source, no_data_label]:
        if text:
            validate_label(text, "label")
    if source == ms.DEFAULT_SOURCE:
        source = ms.LABELS[lang]["source"]
    width = pre.width_mm if width_mm is None else width_mm
    bar_mm = BAR_MM if bar != "none" else 0.0
    title_lines, sub_lines, header_mm = header_text(width, title, subtitle, pre)
    if total_text:
        total_text = ms.wrap_total_text(
            total_text, width - LEFT_MM - RIGHT_MM - 2 * PAD_MM - 4.0, pre.legend_pt
        )
    cw, ch = ms.compass_size_mm(pre)

    # The footer needs the width of a map for the scale bar, the map needs the height of the footer, and a caption that does not fit the width of
    # a narrow map takes more lines, which takes height from the map: a few passes settle it.
    def sizes_for(footer: float, caption_mm: float):
        pw, ph = panel_sizes(n_rows, n_cols, ratio, width, header_mm, footer, caption_mm, bar_mm)
        return pw, ph, footer_item_sizes(None, pw, total_text, source, pre, frame.width_km)

    lines = 1
    for _ in range(4):
        caption_mm = pre.label_pt * PT_MM * 1.3 * lines + 1.2
        pw, ph, sizes = sizes_for(0.0, caption_mm)
        _, footer = plan_footer(sizes, LEFT_MM, width - RIGHT_MM)
        pw, ph, sizes = sizes_for(footer, caption_mm)
        wrapped = [ms._wrap(c, pw - 0.5, pre.label_pt, bold=True) for c in captions]
        need = max(len(w) for w in wrapped)
        if need == lines:
            break
        lines = need
    boxes, _ = plan_footer(sizes, LEFT_MM, width - RIGHT_MM)
    height = (
        header_mm
        + BOTTOM_MM
        + footer
        + bar_mm
        + TICK_MM
        + n_rows * (caption_mm + ph)
        + (n_rows - 1) * ROW_GAP_MM
    )
    # a narrow map (a tall country) leaves the gap that its widest caption word needs, so that two captions never touch
    word_w = max(ms._text_width_mm(w, pre.label_pt, bold=True) for c in captions for w in c.split())
    gap = max(PANEL_GAP_MM, word_w - pw + 1.5)
    grid_w = n_cols * pw + (n_cols - 1) * gap
    x_first = LEFT_MM + (width - LEFT_MM - RIGHT_MM - grid_w) / 2.0
    compass_box = (width - 1.0 - cw, height - 1.0 - ch, width - 1.0, height - 1.0)
    placed = {"compass": Furniture("compass", compass_box, "header")}
    placed.update({n: Furniture(n, b, "footer") for n, b in boxes.items()})

    y_bottom = BOTTOM_MM + footer + bar_mm + TICK_MM  # the bottom of the last row of maps
    with ms.plt.rc_context(ms._rc(pre)):
        fig = ms.plt.figure(figsize=(width / 25.4, height / 25.4), dpi=ms.DPI, facecolor="white")
        overlay = fig.add_axes((0, 0, 1, 1), facecolor="none")
        overlay.set_xlim(0, width)
        overlay.set_ylim(0, height)
        overlay.axis("off")
        overlay.set_zorder(5)
        sheet = PanelFigure(
            fig,
            overlay,
            width,
            height,
            pre,
            frame,
            furniture=placed,
            footer_mm=footer,
            bar_mode=bar,
        )
        sheet.use_colour(SEA_COLOUR, "sea")
        near = ms._neighbours_in_frame(neighbours, frame) if neighbours is not None else None
        if near is not None:
            sheet.use_colour(NEIGHBOUR_COLOUR, "neighbouring countries")
        for k, text in enumerate(captions):
            r, c = divmod(k, n_cols)
            x0 = x_first + c * (pw + gap)
            y0 = y_bottom + (n_rows - 1 - r) * (caption_mm + ph + ROW_GAP_MM)
            box = (x0, y0, x0 + pw, y0 + ph)
            ax = fig.add_axes(sheet.mm_to_fig(box))
            ax.set_facecolor(SEA_COLOUR)
            ax.set_aspect("equal")
            for spine in ax.spines.values():
                spine.set_linewidth(0.4)
                spine.set_color("#888888")
            ax.tick_params(labelsize=pre.label_pt, pad=1.5)
            if near is not None and len(near):
                for is_gap, part in near.groupby("gap"):
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
            panel = Panel(
                ax,
                frame,
                SimpleNamespace(map_box=box),
                None,
                sheet,
                k,
                no_data_label=no_data_label,
            )
            if graticule:
                ms._draw_graticule(
                    SimpleNamespace(frame=frame, ax=ax),
                    left_labels=c == 0,
                    bottom_labels=r == n_rows - 1,
                    keep_inside_m=ms._text_width_mm("179°W", pre.label_pt)
                    / 2.0
                    * frame.width_m
                    / pw,
                )
            else:
                ax.set_xticks([])
                ax.set_yticks([])
            ax.set_xlim(frame.bounds[0], frame.bounds[1])
            ax.set_ylim(frame.bounds[2], frame.bounds[3])
            panel.caption = overlay.text(
                x0,
                y0 + ph + 0.6,
                "\n".join(wrapped[k]),
                fontsize=pre.label_pt,
                fontweight="bold",
                ha="left",
                va="bottom",
            )
            sheet.panels.append(panel)
        sheet.grid_box = (
            x_first,
            y_bottom,
            x_first + grid_w,
            y_bottom + n_rows * (caption_mm + ph) + (n_rows - 1) * ROW_GAP_MM,
        )
        # colour bar slots
        bar_y = (
            BOTTOM_MM + footer + 1.0 + (bar_mm - COLORBAR_MM - 8.0)
        )  # the numbers and the name are under the bar
        bar_y = BOTTOM_MM + footer + 8.0
        if bar == "shared":
            bw = min(0.6 * grid_w, 90.0)
            bx = x_first + (grid_w - bw) / 2.0
            sheet.bar_boxes = [(bx, bar_y, bx + bw, bar_y + COLORBAR_MM)]
        elif bar == "each":
            sheet.bar_boxes = [
                (
                    p.layout.map_box[0] + 0.1 * pw,
                    bar_y,
                    p.layout.map_box[2] - 0.1 * pw,
                    bar_y + COLORBAR_MM,
                )
                for p in sheet.panels
            ]
        sheet.bars = [fig.add_axes(sheet.mm_to_fig(b)) for b in sheet.bar_boxes]
        # the header
        top = height - 2.0
        sheet.texts["title"] = overlay.text(
            2.0,
            top,
            "\n".join(title_lines),
            fontsize=pre.title_pt,
            fontweight="bold",
            ha="left",
            va="top",
        )
        if subtitle:
            sheet.texts["subtitle"] = overlay.text(
                2.0,
                top - len(title_lines) * pre.title_pt * PT_MM * 1.35,
                "\n".join(sub_lines),
                fontsize=pre.label_pt,
                color="#444444",
                ha="left",
                va="top",
            )
        sheet.artists["compass"] = draw_compass(overlay, compass_box, pre)
        sheet.artists["scale_bar"] = draw_scale_bar(
            overlay, placed["scale_bar"].box, None, pw, pre, frame.width_km
        )
        if total_text:
            box = placed["total"].box
            artist = overlay.text(
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
            sheet.texts["total"] = artist
            sheet.artists["total"] = [artist]
        if source:
            box = placed["source"].box
            artist = overlay.text(
                box[2] - PAD_MM,
                box[1] + 0.5,
                source,
                fontsize=pre.footer_pt,
                color="#666666",
                ha="right",
                va="bottom",
            )
            sheet.texts["source"] = artist
            sheet.artists["source"] = [artist]
    if no_data_label:
        sheet.meta["no_data_label"] = no_data_label
    return sheet


def add_panel_colorbar(
    sheet: PanelFigure, mappable, label: str, extend: str = "neither", index: int = 0
):
    """The colour bar of the sheet (`index` 0 when it is shared, the number of the map when there is one under each)."""
    validate_label(label, "colour bar label")
    pt = sheet.preset.legend_pt
    sheet.use_cmap(mappable.get_cmap(), label)
    with ms.plt.rc_context(ms._rc(sheet.preset)):
        bar = sheet.fig.colorbar(
            mappable, cax=sheet.bars[index], orientation="horizontal", extend=extend
        )
        bar.outline.set_linewidth(0.3)
        bar.ax.tick_params(labelsize=pt, width=0.4, length=2.0)
        bar.set_label(label, fontsize=pt, labelpad=1.0)
    return bar


def stipple_note() -> str:
    """What the dots of a stippled map mean (T-09): fewer than two thirds of the models agree on the sign of the change."""
    return "Dots: fewer than 2/3 of the models agree on the sign"
