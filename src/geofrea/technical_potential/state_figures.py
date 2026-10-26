"""Figures of the potential by state (admin1 unit) in the common style (COMMAND 68; spec v2 T-12; D-F5-029).

For each technology and each of the two quantities (capacity density, energy density):

  - `state_sheet`: the three land scenarios (restrictive, central, permissive) side by side (or one over the other for a wide country) as small
    multiples on one set of classes, so that the same colour means the same density in the three maps: that is the interval of land availability
    (U-06) seen in space. The density of a state is its total over **the land area of the state** (the denominator is in the title of the legend), the
    classes are computed from the data (Fisher-Jenks of the central scenario, the last class open), a circle over each state has an area proportional
    to its state total, and the legend of the circle sizes is made from the largest total of the three scenarios;
  - `ranking_chart`: the states ranked by their central density, each with the range of the restrictive and the permissive scenario.

The states come from the admin1 layer of F1; a country whose layer has fewer than `MIN_UNITS` units has no useful state map and is refused with that
message instead of a map of one or two polygons. Nothing here changes a total: the sums of the cells and of the states are checked against F5 before.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgba

from geofrea.viz import mapstyle as ms
from geofrea.viz.charts import new_chart, ranked_bars
from geofrea.viz.context import MapContext, technology_name
from geofrea.viz.panels import (
    PanelFigure,
    adaptive_grid,
    add_panel_circles,
    add_panel_classes,
    new_panels,
)

MIN_UNITS = 2  # one state is not a map of states
ORDER = ("restrictive", "central", "permissive")
FIGURE_PHASE = "F5"
NO_POTENTIAL_LABEL = ms.NO_DATA_LABEL
DENOMINATOR = "land area of the state"
SCENARIO_FILE = "land-scenarios"


class StateFigureError(RuntimeError):
    """The states cannot be drawn (too few units)."""


def check_units(units: gpd.GeoDataFrame) -> None:
    if len(units) < MIN_UNITS:
        raise StateFigureError(
            f"the admin1 layer has {len(units)} unit(s), fewer than {MIN_UNITS}: it is not a useful division for a map of states "
            "(give the pipeline another administrative layer for this country)"
        )


def class_colours(tech: str, n: int) -> list[tuple[float, ...]]:
    """`n` colours of the family of the technology, from light to dark (the same colours as the density maps of the cells)."""
    cmap = ms.colormap_for("density", ms.family_of(tech))
    if n == 1:
        return [cmap(0.6)]
    return [cmap(0.1 + 0.9 * i / (n - 1)) for i in range(n)]


def scenario_caption(scenario: str) -> str:
    return f"{scenario.capitalize()} land scenario"


def state_sheet_name(iso: str, quantity: str, tech: str) -> str:
    return ms.figure_filename(
        iso, FIGURE_PHASE, [f"{quantity}-density", "state"], tech, SCENARIO_FILE, "ref"
    )


def ranking_name(iso: str, quantity: str, tech: str) -> str:
    return ms.figure_filename(
        iso, FIGURE_PHASE, [f"{quantity}-density", "ranking"], tech, SCENARIO_FILE, "ref"
    )


def state_sheet(
    ctx: MapContext,
    iso: str,
    tech: str,
    units: gpd.GeoDataFrame,
    states: dict[str, pd.DataFrame],
    breaks,
    *,
    quantity: str,
    unit_label: str,
    class_labels: Sequence[str],
    circle_title: str,
    circle_reference: float,
    totals_text: str,
    preset: str = "thesis",
    country: str | None = None,
) -> tuple[PanelFigure, dict[str, Any]]:
    """The small multiples of the three land scenarios: states coloured by `<quantity>_density` in `breaks`, a circle over each state for
    its `<quantity>_gw` / `_twh` total. Returns the sheet and what the circles are (for the file of the limits)."""
    check_units(units)
    density_col = f"{'capacity' if quantity == 'capacity' else 'energy'}_density"
    total_col = "capacity_gw" if quantity == "capacity" else "energy_twh"
    units = units.to_crs("EPSG:4326").reset_index(drop=True)
    colours = class_colours(tech, breaks.n_classes)
    labels = [*class_labels, NO_POTENTIAL_LABEL]
    legend_colours = [*colours, ms.NO_DATA_COLOUR]
    r_max = ms.CIRCLE_MAX_MM
    legend_values = ms.nice_values_below(circle_reference)
    rows, cols = adaptive_grid(len(ORDER), ms.make_frame(ctx.polygon, ctx.extent).ratio)
    sheet = new_panels(
        ctx.polygon,
        iso=iso,
        technology=technology_name(tech),
        variable=f"{quantity.capitalize()} density by state",
        captions=[scenario_caption(s) for s in ORDER],
        n_rows=rows,
        n_cols=cols,
        subtitle=ms.format_subtitle(
            "Reference climate",
            f"state total over the {DENOMINATOR}",
            "classes from the central scenario, the same in the three maps",
        ),
        total_text=totals_text,
        neighbours=ctx.neighbours,
        extent=ctx.extent,
        contiguous=False,
        country=country,
        preset=preset,
        bar="shared",
        legend_labels=labels,
        legend_extra_mm=2 * r_max + 3.0 + ms.ROW_MM,
    )
    info: dict[str, Any] = {}
    for panel, scenario in zip(sheet.panels, ORDER, strict=True):
        st = states[scenario]
        values = units["admin1_id"].map(st[density_col]).to_numpy(dtype="float64")
        classes = breaks.assign(np.nan_to_num(values, nan=0.0))
        face = [colours[c] if c >= 0 else to_rgba(ms.NO_DATA_COLOUR) for c in classes]
        ms.draw_choropleth(panel, units, face)
        anchors = units.geometry.apply(_anchor)
        radii = [
            ms.circle_radius_mm(float(st[total_col].get(a1, 0.0)), circle_reference, r_max)
            for a1 in units["admin1_id"]
        ]
        drawn = [i for i, r in enumerate(radii) if r > 0]
        if drawn:
            ms.draw_circles(
                panel,
                [anchors.iloc[i].x for i in drawn],
                [anchors.iloc[i].y for i in drawn],
                [radii[i] for i in drawn],
            )
        info[scenario] = {"states_with_circle": len(drawn)}
    add_panel_classes(
        sheet, 0, labels, legend_colours, f"{quantity} density classes", title=unit_label
    )
    add_panel_circles(
        sheet,
        0,
        circle_title,
        [(f"{v:g}", ms.circle_radius_mm(v, circle_reference, r_max)) for v in legend_values],
    )
    sheet.meta.update(
        {
            "denominator": DENOMINATOR,
            "classes_computed_on": "central scenario, shared by the three maps",
            "scale_mode": "shared",
            "scale_scope": "per_country",
            "data_source": f"F5 potential_{tech}, member m0, three land scenarios",
        }
    )
    info["circle_unit"] = circle_title
    info["circle_reference_total"] = circle_reference
    info["circle_legend_values"] = legend_values
    return sheet, info


def _anchor(geom):
    """A point inside the largest part of a unit (the middle of a state with islands is not in the sea)."""
    if geom.geom_type == "MultiPolygon":
        geom = max(geom.geoms, key=lambda g: g.area)
    return geom.representative_point()


def ranking_chart(
    iso: str,
    tech: str,
    units: gpd.GeoDataFrame,
    states: dict[str, pd.DataFrame],
    *,
    quantity: str,
    unit_label: str,
    preset: str = "thesis",
    country: str | None = None,
):
    """The states ranked by their central density (largest on top); the thin line is the range from the restrictive to the permissive scenario."""
    check_units(units)
    density_col = f"{quantity}_density"
    names = units.set_index("admin1_id")["admin1_name"].astype(str)
    central = states["central"][density_col]
    order = central.sort_values(ascending=False).index
    low = states["restrictive"][density_col].reindex(order).fillna(0.0)
    high = states["permissive"][density_col].reindex(order).fillna(0.0)
    chart = new_chart(
        iso=iso,
        technology=technology_name(tech),
        variable=f"{quantity.capitalize()} density by state, ranked",
        subtitle=ms.format_subtitle(
            "Bar: central land scenario",
            "line: from the restrictive to the permissive scenario",
            f"state total over the {DENOMINATOR}",
        ),
        n_bars=len(order),
        bar_room_mm=4.6,
        labels=[names.get(i, str(i)) for i in order],
        source="Source: F5 technical potential, reference climate",
        preset=preset,
        country=country,
    )
    colour = ms.colormap_for("density", ms.family_of(tech))(0.7)
    ranked_bars(
        chart,
        [names.get(i, str(i)) for i in order],
        central.reindex(order).fillna(0.0).to_numpy(),
        low=low.to_numpy(),
        high=high.to_numpy(),
        unit=unit_label,
        colour=colour,
        meaning=f"{quantity} density, central scenario",
        range_label="restrictive to permissive",
    )
    chart.meta["denominator"] = DENOMINATOR
    chart.meta["data_source"] = f"F5 potential_{tech}, member m0, three land scenarios"
    return chart
