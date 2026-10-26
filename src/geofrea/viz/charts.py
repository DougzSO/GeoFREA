"""Bar charts in the grid of the map figures (COMMAND 68; spec v2 T-10 and T-12).

A chart that goes with the maps (the share of each exclusion in the excluded area, the states ranked by their potential) has the header, the fonts,
the colours and the footer of a map: the title of the form `Country · Variable` and a subtitle on the left, the source on the lower right, the
sizes of the preset in points. It has no compass and no scale bar. It is saved with `mapstyle.save_png` (PNG only, with the metadata of the figure).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from types import SimpleNamespace

import numpy as np

from geofrea.viz import mapstyle as ms
from geofrea.viz.mapstyle import PT_MM, Preset, get_preset, validate_label
from geofrea.viz.panels import legend_height_mm, legend_rows

LEFT_LABEL_MM = 24.0  # the room for the names of the bars at the left of the axes
AXES_RIGHT_MM = 6.0
BAR_HEIGHT = 0.62  # of the room of a bar


@dataclass
class ChartFigure:
    """A chart under construction: `ax` for the bars, `overlay` (1 unit = 1 mm) for the header and the legend."""

    fig: object
    ax: object
    overlay: object
    width_mm: float
    height_mm: float
    preset: Preset
    texts: dict[str, object] = field(default_factory=dict)
    artists: dict[str, list] = field(default_factory=dict)
    colours: dict[str, str] = field(default_factory=dict)
    cmaps: dict[str, str] = field(default_factory=dict)
    meta: dict[str, str] = field(default_factory=dict)

    use_colour = ms.MapFigure.use_colour
    use_cmap = ms.MapFigure.use_cmap

    @property
    def layout(self) -> SimpleNamespace:
        return SimpleNamespace(width_mm=self.width_mm, height_mm=self.height_mm)


def new_chart(
    *,
    iso: str,
    variable: str,
    technology: str = "",
    subtitle: str = "",
    n_bars: int = 2,
    legend_labels: Sequence[str] = (),
    width_mm: float | None = None,
    preset: str | Preset | None = "thesis",
    country: str | None = None,
    source: str | None = None,
    lang: str = "en",
    bar_room_mm: float = 9.0,
    labels: Sequence[str] = (),
    plot_height_mm: float | None = None,
) -> ChartFigure:
    """The axes (one bar per `n_bars`, `bar_room_mm` of height each), the header and the legend rows of a chart of the country `iso`.

    `plot_height_mm` is the height of the axes of a chart that is not made of bars. `labels` are the names of the bars: the room at the left of the axes follows the longest. `source` is the footer text (the data it draws on);
    a chart has none unless it is given."""
    pre = get_preset(preset)
    width = pre.width_mm if width_mm is None else width_mm
    title = ms.format_title(country or ms.country_name(iso, lang), technology, variable)
    validate_label(subtitle, "subtitle")
    title_lines = ms._wrap(title, width - 4.0, pre.title_pt, bold=True)
    sub_lines = ms._wrap(subtitle, width - 4.0, pre.label_pt) if subtitle else []
    header_mm = (
        3.5
        + len(title_lines) * pre.title_pt * PT_MM * 1.35
        + len(sub_lines) * pre.label_pt * PT_MM * 1.35
    )
    legend_mm = legend_height_mm(legend_labels, width - 2 * ms.LEFT_MM, pre)
    axis_mm = 8.0  # the numbers under the axis and its name
    plot_mm = plot_height_mm if plot_height_mm is not None else n_bars * bar_room_mm
    footer = 6.0
    height = header_mm + plot_mm + axis_mm + legend_mm + footer
    with ms.plt.rc_context(ms._rc(pre)):
        fig = ms.plt.figure(figsize=(width / 25.4, height / 25.4), dpi=ms.DPI, facecolor="white")
        overlay = fig.add_axes((0, 0, 1, 1), facecolor="none")
        overlay.set_xlim(0, width)
        overlay.set_ylim(0, height)
        overlay.axis("off")
        overlay.set_zorder(5)
        y0 = footer + legend_mm + axis_mm
        lines = [line for label in labels for line in str(label).split("\n")]
        left = max(
            LEFT_LABEL_MM,
            max((ms._text_width_mm(line, pre.label_pt) for line in lines), default=0.0) + 5.0,
        )
        box = (left, y0, width - AXES_RIGHT_MM, y0 + plot_mm)
        ax = fig.add_axes(
            (box[0] / width, box[1] / height, (box[2] - box[0]) / width, (box[3] - box[1]) / height)
        )
        chart = ChartFigure(fig, ax, overlay, width, height, pre)
        chart.meta["axes_box_mm"] = ",".join(f"{v:.2f}" for v in box)
        chart.use_colour(ms.SEA_COLOUR, "background")
        ax.tick_params(labelsize=pre.label_pt, pad=1.5, width=0.4, length=2.0)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_linewidth(0.4)
            ax.spines[side].set_color("#888888")
        top = height - 2.0
        chart.texts["title"] = overlay.text(
            2.0,
            top,
            "\n".join(title_lines),
            fontsize=pre.title_pt,
            fontweight="bold",
            ha="left",
            va="top",
        )
        if subtitle:
            chart.texts["subtitle"] = overlay.text(
                2.0,
                top - len(title_lines) * pre.title_pt * PT_MM * 1.35,
                "\n".join(sub_lines),
                fontsize=pre.label_pt,
                color="#444444",
                ha="left",
                va="top",
            )
        if source:
            chart.texts["source"] = overlay.text(
                width - 2.0,
                1.0,
                source,
                fontsize=pre.footer_pt,
                color="#666666",
                ha="right",
                va="bottom",
            )
    chart.meta["legend_top_mm"] = f"{footer + legend_mm:.2f}"
    return chart


def stacked_bars(
    chart: ChartFigure,
    categories: Sequence[str],
    series: dict[str, Sequence[float]],
    colours: dict[str, str],
    *,
    unit: str = "%",
    minimum_label_pct: float = 6.0,
) -> list:
    """Horizontal stacked bars: one bar per category, one segment per series (values in `unit`, each bar adding up to 100 when `unit` is `%`).

    A segment wide enough carries its value; every series has a colour (`colours`) and a legend entry under the axis, and keeps its colour in
    the whole figure."""
    ax, pre = chart.ax, chart.preset
    y = np.arange(len(categories))[::-1]
    left = np.zeros(len(categories))
    artists: list = []
    for name, values in series.items():
        v = np.asarray(values, dtype="float64")
        chart.use_colour(colours[name], name)
        bars = ax.barh(
            y,
            v,
            left=left,
            height=BAR_HEIGHT,
            color=colours[name],
            edgecolor="white",
            linewidth=0.4,
            label=name,
        )
        artists.append(bars)
        for yi, li, vi in zip(y, left, v, strict=True):
            if vi >= minimum_label_pct:
                ax.text(
                    li + vi / 2.0,
                    yi,
                    f"{vi:.0f}",
                    ha="center",
                    va="center",
                    fontsize=pre.legend_pt,
                    color="#111111",
                )
        left = left + v
    ax.set_yticks(y, list(categories))
    ax.set_xlim(0, float(max(left.max(), 1e-9)))
    ax.set_ylim(-0.6, len(categories) - 0.4)
    ax.set_xlabel(
        f"Share of the excluded area ({unit})" if unit == "%" else unit, fontsize=pre.legend_pt
    )
    chart.artists["bars"] = artists
    _legend(chart, list(series), [colours[n] for n in series])
    return artists


def _legend(chart: ChartFigure, labels: Sequence[str], colours: Sequence[str]) -> None:
    """The patches of the legend in rows under the axis, at the left of the axes."""
    from matplotlib.patches import Rectangle

    pre = chart.preset
    top = float(chart.meta["legend_top_mm"])
    width = chart.width_mm - 2 * ms.LEFT_MM
    artists: list = []
    for r, members in enumerate(legend_rows(labels, width, pre)):
        x = ms.LEFT_MM
        y = top - (r + 1) * ms.ROW_MM + (ms.ROW_MM - ms.SWATCH_H_MM) / 2.0
        for i in members:
            artists.append(
                chart.overlay.add_patch(
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
                chart.overlay.text(
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
    chart.artists["legend"] = artists


def ranked_bars(
    chart: ChartFigure,
    labels: Sequence[str],
    values: Sequence[float],
    *,
    low: Sequence[float] | None = None,
    high: Sequence[float] | None = None,
    unit: str,
    colour: str,
    meaning: str,
    range_label: str | None = None,
) -> list:
    """Horizontal bars in the order given (largest on top), each with its value; `low` and `high` draw a thin line over the bar for the
    range of another set of values (the restrictive and the permissive land scenario around the central one)."""
    ax, pre = chart.ax, chart.preset
    y = np.arange(len(labels))[::-1]
    v = np.asarray(values, dtype="float64")
    chart.use_colour(colour, meaning)
    bars = ax.barh(y, v, height=BAR_HEIGHT, color=colour, edgecolor="white", linewidth=0.3)
    artists: list = [bars]
    top = float(np.nanmax(v if high is None else np.asarray(high, dtype="float64")))
    if low is not None and high is not None:
        lo, hi = np.asarray(low, dtype="float64"), np.asarray(high, dtype="float64")
        artists.append(ax.hlines(y, lo, hi, color="#222222", linewidth=0.9, zorder=3))
        artists.append(ax.vlines(lo, y - 0.22, y + 0.22, color="#222222", linewidth=0.9, zorder=3))
        artists.append(ax.vlines(hi, y - 0.22, y + 0.22, color="#222222", linewidth=0.9, zorder=3))
    for yi, vi in zip(y, v, strict=True):
        ax.text(
            top * 1.02,
            yi,
            f"{vi:.3g}",
            ha="left",
            va="center",
            fontsize=pre.legend_pt,
            color="#333333",
        )
    ax.set_yticks(y, list(labels))
    ax.set_xlim(0, top * 1.12)
    ax.set_ylim(-0.6, len(labels) - 0.4)
    ax.set_xlabel(unit, fontsize=pre.legend_pt)
    chart.artists["bars"] = artists
    if range_label:
        chart.meta["range"] = range_label
    return artists


def step_curve(
    chart: ChartFigure,
    x: Sequence[float],
    y: Sequence[float],
    *,
    xlabel: str,
    ylabel: str,
    colour: str,
    meaning: str,
) -> list:
    """A curve drawn as steps (a supply curve: the cost of the next block of capacity), with the labels of its axes."""
    ax, pre = chart.ax, chart.preset
    chart.use_colour(colour, meaning)
    line = ax.step(
        np.asarray(x, dtype="float64"),
        np.asarray(y, dtype="float64"),
        where="post",
        color=colour,
        linewidth=1.2,
    )
    ax.set_xlabel(xlabel, fontsize=pre.legend_pt)
    ax.set_ylabel(ylabel, fontsize=pre.legend_pt)
    ax.margins(x=0.02)
    chart.artists["curve"] = list(line)
    return list(line)
