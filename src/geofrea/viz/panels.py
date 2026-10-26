"""Several maps of one country on one sheet, in the layout of `MapFigure` (COMMAND 68; spec v2 T-01 and T-09 to T-12).

A `PanelFigure` is the same grid as a `MapFigure` with `n_rows x n_cols` maps of the same country (same frame, same projection, same
size) instead of one: the title, the subtitle and the compass rose in the header, a caption over each map, the degrees only on the left
column and the bottom row, one colour bar (shared by all, or one under each map of a single row), and a footer with the scale bar, a note
and the source. The panels are drawn by the methods of `MapFigure` (`draw_raster`, `fill_country`), so a panel cuts the raster by the
country, copies the cells without interpolation and may be smoothed for display exactly as a single map is.

A map, a colour or a colour map keeps one meaning in the whole sheet (`use_colour`, `use_cmap`), and the sheet is saved with `mapstyle.save_png`.
"""

from __future__ import annotations

from collections.abc import Sequence
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
BAR_MM = 12.5  # a horizontal colour bar with its numbers and its name, and the space above it
MAX_SHEET_MM = 250.0
STIPPLE_MM = 1.8  # the distance between two dots of the stipple, on paper
SLOT_MIN_MM = (
    55.0  # a legend under a narrow map may be this wide (the room between two maps allowing)
)
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
    slot_boxes: list[BoxMm] = field(
        default_factory=list
    )  # the room of each legend: the bar, its numbers and its name, or the class patches
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


def adaptive_grid(n: int, ratio: float, target: float = 1.0) -> tuple[int, int]:
    """Rows and columns for `n` maps of a country whose map is `ratio` (height over width) tall: the arrangement whose sheet is closest to
    `target` times as tall as it is wide, so that a tall country gets a row of narrow maps and a wide one a stack (T-10, T-11).

    Only arrangements without an empty place are considered (`rows x cols == n`).
    """
    best = min(
        ((n // c, c) for c in range(1, n + 1) if n % c == 0),
        key=lambda rc: (abs(rc[0] * ratio / rc[1] - target), rc[0]),
    )
    return best


def bar_space(bar: str, n_rows: int, slot_mm: float) -> float:
    """The height the legend slots take: one slot under all the maps, one under each row, or none."""
    return {"shared": slot_mm, "each": n_rows * slot_mm}.get(bar, 0.0)


def legend_rows(labels: Sequence[str], width_mm: float, preset: Preset) -> list[list[int]]:
    """The class labels packed into rows of a legend `width_mm` wide (a patch, its label and a gap each): the indices of each row."""
    rows: list[list[int]] = [[]]
    used = 0.0
    for i, label in enumerate(labels):
        w = ms.SWATCH_W_MM + 1.5 + ms._text_width_mm(label, preset.legend_pt) + 3.0
        if rows[-1] and used + w > width_mm:
            rows.append([])
            used = 0.0
        rows[-1].append(i)
        used += w
    return rows


def legend_height_mm(labels: Sequence[str], width_mm: float, preset: Preset) -> float:
    """The height of a class legend of `labels` in a map `width_mm` wide (0 without labels)."""
    if not labels:
        return 0.0
    return len(legend_rows(labels, width_mm, preset)) * ms.ROW_MM + 3.0


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
    legend_labels: Sequence[str] = (),
    legend_extra_mm: float = 0.0,
) -> PanelFigure:
    """The axes, the colour bar slots, the title and the furniture of `n_rows x n_cols` maps of the country `geometry` (lon/lat).

    `captions` has one text per map, in reading order (left to right, top to bottom); `bar` is `shared` (one horizontal colour bar under
    all the maps, for maps that share a scale), `each` (a slot under each map, for maps of different variables: a colour bar, or the patches of
    a class legend, `add_panel_classes`) or `none`. `legend_labels` are the longest set of labels of a class legend, so that the slot is as tall
    as that legend needs at the width of a map, and `legend_extra_mm` more room under it (the circles of `add_panel_circles`). The rest is as in `mapstyle.new_map`; the projection and the frame are those of `new_map` for
    the same country.
    """
    import geopandas as gpd

    if len(captions) != n_rows * n_cols:
        raise ValueError(
            f"{n_rows} x {n_cols} maps need {n_rows * n_cols} captions, got {len(captions)}"
        )
    if bar not in ("shared", "each", "none"):
        raise ValueError(f"bar is shared, each or none, got {bar!r}")
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
    title_lines, sub_lines, header_mm = header_text(width, title, subtitle, pre)
    if total_text:
        total_text = ms.wrap_total_text(
            total_text, width - LEFT_MM - RIGHT_MM - 2 * PAD_MM - 4.0, pre.legend_pt
        )
    cw, ch = ms.compass_size_mm(pre)

    # The footer needs the width of a map for the scale bar, the map needs the height of the footer, and a caption (or a class legend) that does not
    # fit the width of a narrow map takes more lines, which takes height from the map: a few passes settle it.
    def sizes_for(footer: float, caption_mm: float, slot_mm: float):
        pw, ph = panel_sizes(
            n_rows,
            n_cols,
            ratio,
            width,
            header_mm,
            footer,
            caption_mm,
            bar_space(bar, n_rows, slot_mm),
        )
        return pw, ph, footer_item_sizes(None, pw, total_text, source, pre, frame.width_km)

    # a narrow map (a tall country) leaves the gap that its widest caption word needs, so that two captions never touch
    word_w = max(ms._text_width_mm(w, pre.label_pt, bold=True) for c in captions for w in c.split())
    if legend_labels:  # and the widest entry of a class legend (patch, label), which is not broken
        word_w = max(
            word_w,
            *(ms.SWATCH_W_MM + 1.5 + ms._text_width_mm(s, pre.legend_pt) for s in legend_labels),
        )

    def slot_width(pw: float) -> float:
        """The room of a legend under a map: its own width, or more when the map is narrow (never into the slot of the next map)."""
        if n_cols == 1:
            return min(max(pw, SLOT_MIN_MM), width - LEFT_MM - RIGHT_MM)
        gap = max(PANEL_GAP_MM, word_w - pw + 1.5)
        if bar == "shared":  # one slot under all the maps: as wide as the maps are together
            return n_cols * pw + (n_cols - 1) * gap
        return min(max(pw, SLOT_MIN_MM), pw + gap - 1.0)

    lines, slot_mm = 1, BAR_MM
    for _ in range(5):
        caption_mm = pre.label_pt * PT_MM * 1.3 * lines + 1.2
        pw, ph, sizes = sizes_for(0.0, caption_mm, slot_mm)
        _, footer = plan_footer(sizes, LEFT_MM, width - RIGHT_MM)
        pw, ph, sizes = sizes_for(footer, caption_mm, slot_mm)
        wrapped = [ms._wrap(c, pw - 0.5, pre.label_pt, bold=True) for c in captions]
        need = max(len(w) for w in wrapped)
        need_slot = (
            max(BAR_MM, legend_height_mm(legend_labels, slot_width(pw), pre) + legend_extra_mm)
            if bar != "none"
            else 0.0
        )
        if need == lines and abs(need_slot - slot_mm) < 1e-6:
            break
        lines, slot_mm = need, need_slot
    boxes, _ = plan_footer(sizes, LEFT_MM, width - RIGHT_MM)
    bar_total = bar_space(bar, n_rows, slot_mm)
    height = (
        header_mm
        + BOTTOM_MM
        + footer
        + bar_total
        + TICK_MM
        + n_rows * (caption_mm + ph)
        + (n_rows - 1) * ROW_GAP_MM
    )
    gap = max(PANEL_GAP_MM, word_w - pw + 1.5)
    grid_w = n_cols * pw + (n_cols - 1) * gap
    x_first = LEFT_MM + (width - LEFT_MM - RIGHT_MM - grid_w) / 2.0
    compass_box = (width - 1.0 - cw, height - 1.0 - ch, width - 1.0, height - 1.0)
    placed = {"compass": Furniture("compass", compass_box, "header")}
    placed.update({n: Furniture(n, b, "footer") for n, b in boxes.items()})

    # from the bottom: the footer, the shared slot, then each row (its own slot under it when `each`, the degrees under the last one)
    y = BOTTOM_MM + footer
    shared_slot_y = y
    if bar == "shared":
        y += slot_mm
    slot_y: dict[int, float] = {}
    map_y0: dict[int, float] = {}
    for r in reversed(range(n_rows)):
        if bar == "each":
            slot_y[r] = y
            y += slot_mm
        if r == n_rows - 1:
            y += TICK_MM
        map_y0[r] = y
        y += ph + caption_mm
        if r > 0:
            y += ROW_GAP_MM
    y_bottom = map_y0[n_rows - 1]
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
            y0 = map_y0[r]
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
        sheet.grid_box = (x_first, y_bottom, x_first + grid_w, map_y0[0] + ph + caption_mm)
        # colour bar slots: the bar is at the top of its slot, its numbers and its name under it
        if bar == "shared":
            bw = min(0.6 * grid_w, 90.0)
            bx = x_first + (grid_w - bw) / 2.0
            by = shared_slot_y + slot_mm - COLORBAR_MM - 1.0
            sheet.bar_boxes = [(bx, by, bx + bw, by + COLORBAR_MM)]
            sheet.slot_boxes = [(x_first, shared_slot_y, x_first + grid_w, shared_slot_y + slot_mm)]
        elif bar == "each":
            for k, p in enumerate(sheet.panels):
                r = k // n_cols
                by = slot_y[r] + slot_mm - COLORBAR_MM - 1.0
                sheet.bar_boxes.append(
                    (
                        p.layout.map_box[0] + 0.1 * pw,
                        by,
                        p.layout.map_box[2] - 0.1 * pw,
                        by + COLORBAR_MM,
                    )
                )
                centre = (p.layout.map_box[0] + p.layout.map_box[2]) / 2.0
                half = slot_width(pw) / 2.0
                left = max(centre - half, 2.0)
                sheet.slot_boxes.append(
                    (left, slot_y[r], min(left + 2 * half, width - 2.0), slot_y[r] + slot_mm)
                )
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


def add_panel_classes(
    sheet: PanelFigure,
    index: int,
    labels: Sequence[str],
    colours: Sequence,
    meaning: str,
    title: str | None = None,
) -> list:
    """The patches of a class legend (a colour and its label, in rows) in the slot of the map `index`; the colour bar axes of that slot is hidden.

    `meaning` names what the colours stand for in this sheet (a colour keeps one meaning in a sheet); a `title` (the unit, say) takes the first row
    of the slot, which the caller has paid for in `legend_extra_mm`."""
    from matplotlib.patches import Rectangle

    pre = sheet.preset
    box = sheet.slot_boxes[index]
    sheet.bars[index].set_visible(False)
    rows = legend_rows(labels, box[2] - box[0], pre)
    artists: list = []
    y_top = box[3] - 1.5
    if title:
        validate_label(title, "legend title")
        artists.append(
            sheet.overlay.text(
                box[0],
                y_top - ms.ROW_MM / 2.0,
                title,
                fontsize=pre.legend_pt,
                fontweight="bold",
                color="#333333",
                ha="left",
                va="center",
            )
        )
        y_top -= ms.ROW_MM
    for r, members in enumerate(rows):
        x = box[0]
        y = y_top - (r + 1) * ms.ROW_MM + (ms.ROW_MM - ms.SWATCH_H_MM) / 2.0
        for i in members:
            sheet.use_colour(colours[i], f"{meaning}: {labels[i]}")
            artists.append(
                sheet.overlay.add_patch(
                    Rectangle(
                        (x, y),
                        ms.SWATCH_W_MM,
                        ms.SWATCH_H_MM,
                        facecolor=colours[i],
                        edgecolor="#555555",
                        linewidth=0.2,
                    )
                )
            )
            artists.append(
                sheet.overlay.text(
                    x + ms.SWATCH_W_MM + 1.5,
                    y + ms.SWATCH_H_MM / 2.0,
                    labels[i],
                    fontsize=pre.legend_pt,
                    color="#333333",
                    ha="left",
                    va="center",
                )
            )
            x += ms.SWATCH_W_MM + 1.5 + ms._text_width_mm(labels[i], pre.legend_pt) + 3.0
    sheet.artists[f"legend {index}"] = artists
    return artists


def add_panel_circles(
    sheet: PanelFigure,
    index: int,
    title: str,
    items: Sequence[tuple[str, float]],
) -> list:
    """The size legend of the circles of a sheet at the bottom of the slot `index`: `title`, then each circle (radius in mm on paper) with its label.

    The sizes are the ones the circles of the maps have (`mapstyle.circle_radius_mm`), taken from the data by the caller."""
    from matplotlib.patches import Circle

    pre = sheet.preset
    box = sheet.slot_boxes[index]
    validate_label(title, "legend title")
    artists: list = []
    x = box[0]
    y_base = box[1] + 0.8
    artists.append(
        sheet.overlay.text(
            x,
            y_base + max((r for _, r in items), default=0.0),
            title,
            fontsize=pre.legend_pt,
            color="#333333",
            fontweight="bold",
            ha="left",
            va="center",
        )
    )
    x += ms._text_width_mm(title, pre.legend_pt, bold=True) + 4.0
    for label, radius in items:
        validate_label(label, "legend label")
        artists.append(
            sheet.overlay.add_patch(
                Circle(
                    (x + radius, y_base + radius),
                    radius,
                    facecolor=ms.CIRCLE_FACE,
                    edgecolor=ms.CIRCLE_EDGE,
                    linewidth=0.4,
                )
            )
        )
        artists.append(
            sheet.overlay.text(
                x + 2 * radius + 1.2,
                y_base + radius,
                label,
                fontsize=pre.legend_pt,
                color="#333333",
                ha="left",
                va="center",
            )
        )
        x += 2 * radius + 1.2 + ms._text_width_mm(label, pre.legend_pt) + 4.0
    sheet.artists[f"circles {index}"] = artists
    return artists


def add_panel_colorbar(
    sheet: PanelFigure,
    mappable,
    label: str,
    extend: str = "neither",
    index: int = 0,
    meaning: str | None = None,
):
    """The colour bar of the sheet (`index` 0 when it is shared, the number of the map when there is one under each). Two maps that share a
    colormap say what they have in common with `meaning` (the label of the bar by default): a colormap keeps one meaning in a sheet."""
    validate_label(label, "colour bar label")
    pt = sheet.preset.legend_pt
    sheet.use_cmap(mappable.get_cmap(), meaning or label)
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
