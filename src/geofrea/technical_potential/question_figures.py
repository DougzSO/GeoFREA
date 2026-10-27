"""Figures that answer the questions of the thesis directly (COMMAND 69; spec v2 T-15 items 1 to 4).

For each country:

  - `supply_chart`: the supply curve against the capacity factor (item 1): the cells of a technology from the highest capacity factor down, the
    cumulative capacity (or energy) on the vertical axis, one line per land scenario. There is **no resource cut**: every candidate cell is on the
    curve (decision 3 of the author); the cut is the `CF_min` of the group 4 parameters, applied downstream. The version against the LCOE comes
    after F6;
  - `land_range_chart`: the interval of land availability (item 3): for the eligible area, the capacity and the energy, the central value with the
    line from the restrictive to the permissive scenario, one row per technology;
  - `change_sheet` and `change_total_chart` (item 4): the change of the capacity factor of every cell, by SSP and window, as the mean of the GCMs
    with dots where fewer than 2/3 of them agree on the sign, and the change of the national energy with the range between the GCMs. The capacity of
    a cell does not depend on the climate member, so the change of the potential is the change of the energy and, cell by cell, the change of the
    capacity factor: this is where F4 enters F5 (RQ3).

Across the countries, `comparison_sheet` and `comparison_supply_chart` (item 2) put the same metrics of every country on one sheet with the same
axes. The metrics are per unit of the **area of the cells of the country** (the denominator is in the subtitle), so that a large country does not
dominate; the capacity-factor axis is fixed per technology across the countries.

The figures read the potential tables, the cell tables of F3 and `members.yaml` of F4. Nothing here changes a number of the phases.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.colors import to_hex

from geofrea.climate_forcing.figures import (
    AGREEMENT,
    MemberInfo,
    _draw,
    _meta,
    _norm,
    _plan,
    _resolution_text,
    _scale_note,
    _window_label,
    ensemble_field,
    read_members,
)
from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID
from geofrea.core import paths as core_paths
from geofrea.core.constants import HOURS_PER_YEAR
from geofrea.viz import mapstyle as ms
from geofrea.viz.charts import ChartFigure, curves, interval_rows, new_chart
from geofrea.viz.context import MapContext, lattice_of, technology_name, to_grid
from geofrea.viz.panels import PanelFigure, add_panel_colorbar, new_panels, stipple_note

logger = logging.getLogger("geofrea.technical_potential.question_figures")

FIGURE_PHASE = "F5"
CENTRAL = "central"
ORDER = ("restrictive", CENTRAL, "permissive")
SCENARIO_FILE = "land-scenarios"
ALL_COUNTRIES = "ALL"  # the code in the name of a figure that compares countries
MAX_POINTS = 1500  # points of a drawn curve (the cells are thinned to this, the ends kept)
SCENARIO_COLOURS = {"restrictive": "#0072B2", CENTRAL: "#000000", "permissive": "#D55E00"}
SCENARIO_WIDTHS = {"restrictive": 1.1, CENTRAL: 1.8, "permissive": 1.1}
COUNTRY_COLOURS = ("#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9")
SSP_COLOURS = ("#009E73", "#E69F00", "#D55E00", "#CC79A7", "#0072B2")
DENOMINATOR = "area of the cells of the country"
SOURCE = "Source: F5 technical potential, reference climate"
ROOM_PER_ROW_MM = 9.0


class ThesisFiguresError(RuntimeError):
    """An input of the figures is missing or inconsistent (A-09)."""


# ------------------------------------------------------------------------------------------------------------------------------- the data


@dataclass(frozen=True)
class TechData:
    """What the figures of one country and one technology read: the reference member of each land scenario, the aggregates of every member and
    the areas."""

    tech: str
    reference: dict[str, pd.DataFrame]  # scenario -> cell_id, P_MW, CF, E_MWh of the member m0
    aggregates: pd.DataFrame  # `potential_aggregates_<tech>` (every scenario, every member)
    country_area_km2: float  # the area of the cells of the country
    eligible_area_km2: dict[str, float]
    members: dict[str, pd.DataFrame]  # central scenario, the rows of the members that are not m0


def read_tech(
    iso: str,
    tech: str,
    *,
    potential_dir: Path | None = None,
    cells_dir: Path | None = None,
    with_members: bool = True,
) -> TechData:
    """The tables of `tech` of the country `iso`. `with_members` also keeps the rows of every climate member of the central scenario (the
    change maps need them; the comparison does not)."""
    potential_dir = Path(
        potential_dir or core_paths.phase_dir(iso, "technical_potential", "artifacts")
    )
    cells_dir = Path(cells_dir or core_paths.phase_dir(iso, "land_eligibility", "artifacts"))
    reference: dict[str, pd.DataFrame] = {}
    members: dict[str, pd.DataFrame] = {}
    for scenario in ORDER:
        path = potential_dir / f"potential_{tech}__{scenario}.parquet"
        if not path.is_file():
            raise ThesisFiguresError(f"missing input {path}")
        table = pd.read_parquet(path, columns=["cell_id", "member", "P_MW", "CF", "E_MWh"])
        is_reference = table["member"].astype(str) == REFERENCE_MEMBER_ID
        reference[scenario] = table[is_reference].reset_index(drop=True)
        if scenario == CENTRAL and with_members:
            members[CENTRAL] = table[~is_reference].reset_index(drop=True)
    aggregates_path = potential_dir / f"potential_aggregates_{tech}.parquet"
    if not aggregates_path.is_file():
        raise ThesisFiguresError(f"missing input {aggregates_path}")
    eligible: dict[str, float] = {}
    area = math.nan
    for scenario in ORDER:
        path = cells_dir / f"cells_{tech}__{scenario}.parquet"
        if not path.is_file():
            raise ThesisFiguresError(f"missing input {path}")
        cells = pd.read_parquet(path, columns=["cell_area_km2", "eligible_area_km2"])
        eligible[scenario] = float(cells["eligible_area_km2"].sum())
        if scenario == CENTRAL:
            area = float(cells["cell_area_km2"].sum())
    return TechData(tech, reference, pd.read_parquet(aggregates_path), area, eligible, members)


def totals(data: TechData) -> dict[str, tuple[float, float]]:
    """Scenario -> (capacity in GW, energy in TWh per year) of the reference member, from the cells."""
    return {
        s: (float(t["P_MW"].sum()) / 1e3, float(t["E_MWh"].sum()) / 1e6)
        for s, t in data.reference.items()
    }


def energy_weighted_cf(table: pd.DataFrame) -> float:
    capacity = float(table["P_MW"].sum())
    return float(table["E_MWh"].sum()) / (capacity * HOURS_PER_YEAR) if capacity > 0 else math.nan


def supply_curve(table: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The cells with capacity from the highest capacity factor down: (capacity factor of the cell, cumulative GW, cumulative TWh per year).
    The points are thinned to `MAX_POINTS` with the first and the last kept."""
    cells = table[table["P_MW"] > 0].sort_values("CF", ascending=False, kind="stable")
    cf = cells["CF"].to_numpy(dtype="float64")
    gw = cells["P_MW"].cumsum().to_numpy(dtype="float64") / 1e3
    twh = cells["E_MWh"].cumsum().to_numpy(dtype="float64") / 1e6
    if cf.size > MAX_POINTS:
        keep = np.unique(np.linspace(0, cf.size - 1, MAX_POINTS).astype(int))
        cf, gw, twh = cf[keep], gw[keep], twh[keep]
    return cf, gw, twh


def cf_limits(tables: Sequence[pd.DataFrame]) -> tuple[float, float]:
    """The capacity-factor axis of a technology: from 0 or the lower multiple of 0.05 below the smallest factor, to the multiple of 0.05 above the
    largest, over all the tables given."""
    values = np.concatenate(
        [t.loc[t["P_MW"] > 0, "CF"].to_numpy(dtype="float64") for t in tables if len(t)]
    )
    if not values.size:
        return (0.0, 1.0)
    return (
        max(0.0, math.floor(float(values.min()) / 0.05) * 0.05),
        min(1.0, math.ceil(float(values.max()) / 0.05) * 0.05),
    )


def family_colour(tech: str, level: float = 0.7) -> str:
    return to_hex(ms.colormap_for("density", ms.family_of(tech))(level))


def _num(value: float) -> str:
    """A number for a note: three significant figures below 100, whole numbers with thousands separators above."""
    return f"{value:,.3g}" if abs(value) < 100 else f"{value:,.0f}"


def _status(chart: ChartFigure, data_source: str) -> None:
    chart.meta["data_source"] = data_source
    chart.meta["status"] = "thesis"


# ------------------------------------------------------------------------------------------------------------------------ 1. supply curve


def supply_name(iso: str, quantity: str, tech: str) -> str:
    return ms.figure_filename(
        iso, FIGURE_PHASE, f"supply-curve-{quantity}", tech, SCENARIO_FILE, "ref"
    )


def supply_chart(
    iso: str,
    data: TechData,
    quantity: str,
    *,
    limits: tuple[float, float] | None = None,
    preset: str = "thesis",
    country: str | None = None,
) -> ChartFigure:
    """The cumulative capacity (`quantity` `capacity`, GW) or energy (`energy`, TWh per year) against the capacity factor of the cell, one line per
    land scenario. The label of each line gives the total at the end of the curve."""
    index = {"capacity": 1, "energy": 2}[quantity]
    unit = {"capacity": "GW", "energy": "TWh per year"}[quantity]
    sums = totals(data)
    labels = {s: f"{s.capitalize()}: {sums[s][index - 1]:,.1f} {unit}" for s in ORDER}
    limits = limits or cf_limits(list(data.reference.values()))
    chart = new_chart(
        iso=iso,
        technology=technology_name(data.tech),
        variable=f"Supply curve, cumulative {quantity} against capacity factor",
        subtitle=ms.format_subtitle(
            "Cells from the highest capacity factor down",
            "no resource cut: every candidate cell is on the curve",
            "reference climate",
        ),
        plot_height_mm=70.0,
        legend_labels=list(labels.values()),
        source=SOURCE,
        preset=preset,
        country=country,
    )
    series = {}
    for scenario in ORDER:
        cf, gw, twh = supply_curve(data.reference[scenario])
        series[labels[scenario]] = (cf, (gw, twh)[index - 1])
    curves(
        chart,
        series,
        {labels[s]: SCENARIO_COLOURS[s] for s in ORDER},
        xlabel="Capacity factor of the cell (cells from the highest down)",
        ylabel=f"Cumulative {quantity} ({unit})",
        widths={labels[s]: SCENARIO_WIDTHS[s] for s in ORDER},
        xlim=limits,
        invert_x=True,
    )
    chart.meta["cf_axis"] = f"{limits[0]:.2f},{limits[1]:.2f}"
    _status(chart, f"F5 potential_{data.tech}, member m0, three land scenarios")
    return chart


# -------------------------------------------------------------------------------------------------------------------- 3. land availability


def land_range_name(iso: str) -> str:
    return ms.figure_filename(iso, FIGURE_PHASE, "land-availability", None, SCENARIO_FILE, "ref")


def _range_values(data: TechData, quantity: str) -> list[float]:
    """Restrictive, central and permissive value of `quantity` (`area` in thousand km2, `capacity` in GW, `energy` in TWh per year)."""
    if quantity == "area":
        return [data.eligible_area_km2[s] / 1e3 for s in ORDER]
    sums = totals(data)
    index = {"capacity": 0, "energy": 1}[quantity]
    return [sums[s][index] for s in ORDER]


def land_range_chart(
    iso: str,
    by_tech: dict[str, TechData],
    *,
    preset: str = "thesis",
    country: str | None = None,
) -> ChartFigure:
    """Three panels (eligible area, capacity, energy), one row per technology: the central value (dot) and the line from the restrictive to the
    permissive land scenario, with the three numbers written beside the row."""
    techs = list(by_tech)
    panels = (
        ("area", "Eligible area (thousand km²)"),
        ("capacity", "Capacity (GW)"),
        ("energy", "Energy (TWh per year)"),
    )
    chart = new_chart(
        iso=iso,
        variable="Interval of land availability",
        subtitle=ms.format_subtitle(
            "Dot: central land scenario",
            "line: from the restrictive to the permissive scenario",
            "reference climate",
        ),
        n_bars=len(techs),
        bar_room_mm=ROOM_PER_ROW_MM,
        labels=[technology_name(t) for t in techs],
        grid=(len(panels), 1),
        panel_titles=[title for _, title in panels],
        source=SOURCE,
        preset=preset,
        country=country,
    )
    for ax, (quantity, title) in zip(chart.axes, panels, strict=True):
        rows = [_range_values(by_tech[t], quantity) for t in techs]
        low = [r[0] for r in rows]
        mid = [r[1] for r in rows]
        high = [r[2] for r in rows]
        notes = [
            f"{_num(m)} ({_num(lo)} to {_num(hi)})"
            for lo, m, hi in zip(low, mid, high, strict=True)
        ]
        interval_rows(
            chart,
            [technology_name(t) for t in techs],
            {"Land availability": (mid, low, high)},
            {"Land availability": "#444444"},
            xlabel=title,
            xlim=None,
            notes=notes,
            ax=ax,
        )
        ax.set_xlim(left=0.0)
    _status(chart, "F5 potential tables and F3 cell tables, member m0")
    return chart


# ----------------------------------------------------------------------------------------------------------- 4. change by SSP and window


def change_sheet_name(iso: str, tech: str) -> str:
    return ms.figure_filename(
        iso, FIGURE_PHASE, "change-capacity-factor", tech, CENTRAL, "ssp-window"
    )


def change_total_name(iso: str) -> str:
    return ms.figure_filename(iso, FIGURE_PHASE, "change-energy", None, CENTRAL, "ssp-window")


def change_grids(
    data: TechData, members: Sequence[MemberInfo], reference_cells: np.ndarray
) -> tuple[dict[str, dict[str, np.ndarray]], object]:
    """For each climate member, the change of the capacity factor of every cell against the reference member, in percent, on the lattice of the
    cells of the country: `{member: {"change": grid}}`. A cell with no value in the member, or with no capacity factor at the reference, is NaN."""
    table = data.members[CENTRAL]
    lattice = lattice_of(reference_cells)
    base = data.reference[CENTRAL].set_index("cell_id")["CF"]
    grids: dict[str, dict[str, np.ndarray]] = {}
    for info in members:
        rows = table[table["member"].astype(str) == info.member]
        if rows.empty:
            grids[info.member] = {"change": np.full(lattice.shape, np.nan, dtype="float32")}
            continue
        ref = base.reindex(rows["cell_id"].to_numpy()).to_numpy(dtype="float64")
        with np.errstate(invalid="ignore", divide="ignore"):
            change = np.where(
                ref > 0, (rows["CF"].to_numpy(dtype="float64") / ref - 1.0) * 100.0, np.nan
            )
        grids[info.member] = {"change": to_grid(rows["cell_id"].to_numpy(), change, lattice)}
    return grids, lattice


def change_sheet(
    ctx: MapContext,
    iso: str,
    data: TechData,
    members: Sequence[MemberInfo],
    *,
    display_smoothing: str = "auto",
    preset: str = "thesis",
    country: str | None = None,
) -> PanelFigure:
    """The change of the capacity factor (and of the energy of the cell, which is the same percentage) by SSP (rows) and window (columns): the
    mean of the GCMs of each scenario, one colour scale for all the maps, dots where fewer than 2/3 of the GCMs agree on the sign."""
    reference_cells = data.reference[CENTRAL]["cell_id"].to_numpy()
    grids, lattice = change_grids(data, members, reference_cells)
    scenarios = sorted({(m.ssp, m.window) for m in members})
    ssps = sorted({s for s, _ in scenarios})
    windows = sorted({w for _, w in scenarios})
    fields = {sw: ensemble_field("change", sw[0], sw[1], members, grids) for sw in scenarios}
    spec = ms.ScaleSpec("shared", diverging=True)
    limits = ms.shared_limits([f.mean[np.isfinite(f.mean)] for f in fields.values()], spec)
    values = np.concatenate([f.mean[np.isfinite(f.mean)] for f in fields.values()])
    info = _norm("change", values, limits)
    extent = lattice.extent
    resolution = _resolution_text(members, ctx)
    captions = [f"{s} · {_window_label(w)}" for s in ssps for w in windows]

    def build(shown: str | None) -> PanelFigure:
        return new_panels(
            ctx.polygon,
            iso=iso,
            technology=technology_name(data.tech),
            variable="Change of the capacity factor by SSP and window",
            captions=captions,
            n_rows=len(ssps),
            n_cols=len(windows),
            subtitle=ms.format_subtitle(
                "Ensemble mean of the GCMs against the reference climate",
                "the capacity of a cell does not change, so the energy changes by the same percentage",
                shown,
                _scale_note([info]),
            ),
            total_text=stipple_note(),
            neighbours=ctx.neighbours,
            extent=ctx.extent,
            contiguous=False,
            country=country,
            preset=preset,
            bar="shared",
        )

    sheet = build(resolution)
    plan = _plan(sheet, fields[scenarios[0]].mean, extent, resolution, display_smoothing)
    if plan.shown != resolution:
        ms.close_figure(sheet)
        sheet = build(plan.shown)
    image = None
    cmap = ms.colormap_for("delta")
    for panel, sw in zip(sheet.panels, [(s, w) for s in ssps for w in windows], strict=True):
        field = fields.get(sw)
        if field is None:  # a combination the members do not have: the panel stays empty
            panel.fill_country()
            continue
        image = _draw(panel, field.mean, extent, cmap, info.norm, plan)
        panel.stipple(field.disagree, extent)
    add_panel_colorbar(sheet, image, "Change (%)", info.extend)
    _meta(sheet, {"change": limits}, plan, display_smoothing, variable="change-capacity-factor")
    sheet.meta["data_source"] = f"F5 potential_{data.tech} (members) against m0, F4 members"
    sheet.meta["status"] = "thesis"
    sheet.meta["agreement_threshold"] = f"{AGREEMENT:.3f}"
    return sheet


def change_totals(data: TechData, members: Sequence[MemberInfo]) -> pd.DataFrame:
    """The change of the national energy against the reference member (like for like, central scenario) for each (SSP, window): the mean of the
    GCMs and the smallest and largest GCM. One row per (ssp, window)."""
    agg = data.aggregates
    agg = agg[agg["scenario"].astype(str) == CENTRAL].set_index(
        agg.loc[agg["scenario"].astype(str) == CENTRAL, "member"].astype(str)
    )
    rows = []
    for ssp, window in sorted({(m.ssp, m.window) for m in members}):
        chosen = [m.member for m in members if m.ssp == ssp and m.window == window]
        values = (
            agg.reindex(chosen)["delta_E_pct_vs_m0_like_for_like"]
            .dropna()
            .to_numpy(dtype="float64")
        )
        rows.append(
            {
                "ssp": ssp,
                "window": window,
                "n_gcms": int(values.size),
                "mean": float(values.mean()) if values.size else math.nan,
                "low": float(values.min()) if values.size else math.nan,
                "high": float(values.max()) if values.size else math.nan,
            }
        )
    return pd.DataFrame(rows)


def change_total_chart(
    iso: str,
    by_tech: dict[str, TechData],
    members: Sequence[MemberInfo],
    *,
    preset: str = "thesis",
    country: str | None = None,
) -> ChartFigure:
    """The change of the national energy by SSP and window, one series per technology: the dot is the mean of the GCMs and the line goes from
    the smallest to the largest GCM."""
    tables = {t: change_totals(d, members) for t, d in by_tech.items()}
    first = next(iter(tables.values()))
    labels = [f"{r.ssp} · {_window_label(r.window)}" for r in first.itertuples()]
    names = {t: technology_name(t) for t in tables}
    chart = new_chart(
        iso=iso,
        variable="Change of the national energy by SSP and window",
        subtitle=ms.format_subtitle(
            "Dot: mean of the GCMs",
            "line: smallest to largest GCM",
            "central land scenario, against the reference climate, same cells",
        ),
        n_bars=len(labels) * max(1, len(tables)),
        bar_room_mm=3.6,
        labels=labels,
        legend_labels=list(names.values()),
        source=SOURCE,
        preset=preset,
        country=country,
    )
    interval_rows(
        chart,
        labels,
        {
            names[t]: (tab["mean"].to_numpy(), tab["low"].to_numpy(), tab["high"].to_numpy())
            for t, tab in tables.items()
        },
        {names[t]: family_colour(t) for t in tables},
        xlabel="Change of the energy (%)",
        zero_line=True,
    )
    _status(chart, "F5 potential_aggregates, central scenario, like-for-like cells")
    return chart


# -------------------------------------------------------------------------------------------------------------------- 2. country comparison


def _country_name(iso: str) -> str:
    try:
        return ms.country_name(iso)
    except (KeyError, ValueError):
        return iso


def comparison_dir() -> Path:
    return Path(core_paths.outputs_dir()) / "comparison" / "figures"


def comparison_name(variable: str, tech: str) -> str:
    return ms.figure_filename(ALL_COUNTRIES, FIGURE_PHASE, variable, tech, SCENARIO_FILE, "ref")


def _series(rows: Sequence[Sequence[float]]) -> tuple[list[float], list[float], list[float]]:
    """(centre, low, high) per country from the rows `[restrictive, central, permissive]` of the countries."""
    return [r[1] for r in rows], [r[0] for r in rows], [r[2] for r in rows]


def comparison_sheet(
    by_country: dict[str, TechData],
    tech: str,
    members: dict[str, Sequence[MemberInfo]],
    *,
    names: dict[str, str] | None = None,
    limits: tuple[float, float] | None = None,
    preset: str = "thesis",
) -> ChartFigure:
    """The same metrics of every country on one sheet with the same axes: (a) the eligible share of the area of the cells, (b) the capacity density,
    (c) the energy-weighted capacity factor on the fixed axis of the technology, (d) the change of the national energy of the last window by SSP.
    In (a) to (c) the dot is the central land scenario and the line goes from the restrictive to the permissive one."""
    isos = list(by_country)
    labels = [(names or {}).get(i, i) for i in isos]
    cf_values = [energy_weighted_cf(t) for d in by_country.values() for t in d.reference.values()]
    cf_axis = (0.0, min(1.0, math.ceil(max(cf_values) * 1.25 / 0.05) * 0.05))
    ssps = sorted({m.ssp for ms_ in members.values() for m in ms_})
    window = max(m.window for ms_ in members.values() for m in ms_)
    chart = new_chart(
        iso=ALL_COUNTRIES,
        country=" · ".join(labels),
        technology=technology_name(tech),
        variable="Comparison of the countries",
        subtitle=ms.format_subtitle(
            f"Per {DENOMINATOR}",
            "dot: central land scenario, line: restrictive to permissive",
            "reference climate",
        ),
        n_bars=len(isos),
        bar_room_mm=ROOM_PER_ROW_MM,
        labels=labels,
        grid=(2, 2),
        panel_titles=(
            "Eligible share of the area (%)",
            "Capacity density (MW per km²)",
            "Capacity factor, energy-weighted",
            f"Change of the energy, {_window_label(window)} (%), by SSP",
        ),
        legend_labels=list(ssps),
        source=SOURCE,
        preset=preset,
    )
    share, density, cf = [], [], []
    for iso in isos:
        d = by_country[iso]
        sums = totals(d)
        share.append([100.0 * d.eligible_area_km2[s] / d.country_area_km2 for s in ORDER])
        density.append([sums[s][0] * 1e3 / d.country_area_km2 for s in ORDER])
        cf.append([energy_weighted_cf(d.reference[s]) for s in ORDER])
    colour = {tech: family_colour(tech)}
    for ax, rows, label in (
        (chart.axes[0], share, "Eligible share (%)"),
        (chart.axes[1], density, "Capacity density (MW per km²)"),
    ):
        interval_rows(
            chart,
            labels,
            {technology_name(tech): _series(rows)},
            {technology_name(tech): colour[tech]},
            xlabel=label,
            ax=ax,
        )
        ax.set_xlim(left=0.0)
    interval_rows(
        chart,
        labels,
        {technology_name(tech): _series(cf)},
        {technology_name(tech): colour[tech]},
        xlabel="Capacity factor",
        xlim=cf_axis,
        ax=chart.axes[2],
    )
    series: dict[str, tuple[list[float], list[float], list[float]]] = {}
    for k, ssp in enumerate(ssps):
        centre, low, high = [], [], []
        for iso in isos:
            tab = change_totals(by_country[iso], members[iso])
            row = tab[(tab["ssp"] == ssp) & (tab["window"] == window)]
            centre.append(float(row["mean"].iloc[0]) if len(row) else math.nan)
            low.append(float(row["low"].iloc[0]) if len(row) else math.nan)
            high.append(float(row["high"].iloc[0]) if len(row) else math.nan)
        series[ssp] = (centre, low, high)
    interval_rows(
        chart,
        labels,
        series,
        {ssp: SSP_COLOURS[k % len(SSP_COLOURS)] for k, ssp in enumerate(ssps)},
        xlabel="Change of the energy (%)",
        zero_line=True,
        ax=chart.axes[3],
    )
    chart.meta["countries"] = ",".join(isos)
    chart.meta["cf_axis"] = f"{cf_axis[0]:.2f},{cf_axis[1]:.2f}"
    chart.meta["denominator"] = DENOMINATOR
    _status(chart, "F5 potential tables, F3 cell tables, F4 members of each country")
    return chart


def comparison_supply_chart(
    by_country: dict[str, TechData],
    tech: str,
    *,
    names: dict[str, str] | None = None,
    limits: tuple[float, float] | None = None,
    preset: str = "thesis",
) -> ChartFigure:
    """The central supply curve of every country in capacity per area of the cells of the country, on the capacity-factor axis fixed for the
    technology: the curves can be read against each other. The shaded range of the land scenarios is not drawn, the restrictive and the permissive
    curves are thin lines of the colour of the country."""
    isos = list(by_country)
    labels = {i: (names or {}).get(i, i) for i in isos}
    limits = limits or cf_limits([t for d in by_country.values() for t in d.reference.values()])
    chart = new_chart(
        iso=ALL_COUNTRIES,
        country=" · ".join(labels.values()),
        technology=technology_name(tech),
        variable="Supply curve of the countries per area",
        subtitle=ms.format_subtitle(
            f"Cumulative capacity per {DENOMINATOR}",
            "cells from the highest capacity factor down, no resource cut",
            "thick line: central land scenario, thin lines: restrictive and permissive",
        ),
        plot_height_mm=70.0,
        legend_labels=list(labels.values()),
        source=SOURCE,
        preset=preset,
    )
    series, colours, widths, meanings = {}, {}, {}, {}
    for k, iso in enumerate(isos):
        d = by_country[iso]
        for scenario in ORDER:
            cf, gw, _ = supply_curve(d.reference[scenario])
            key = labels[iso] if scenario == CENTRAL else f"{labels[iso]} {scenario}"
            series[key] = (cf, gw * 1e3 / d.country_area_km2)
            colours[key] = COUNTRY_COLOURS[k % len(COUNTRY_COLOURS)]
            widths[key] = 1.8 if scenario == CENTRAL else 0.8
            meanings[key] = labels[iso]
    curves(
        chart,
        series,
        colours,
        xlabel="Capacity factor of the cell (cells from the highest down)",
        ylabel="Cumulative capacity (MW per km²)",
        widths=widths,
        xlim=limits,
        invert_x=True,
        meanings={key: label for key, label in meanings.items()},
        legend=list(labels.values()),
    )
    chart.meta["countries"] = ",".join(isos)
    chart.meta["cf_axis"] = f"{limits[0]:.2f},{limits[1]:.2f}"
    chart.meta["denominator"] = DENOMINATOR
    _status(chart, "F5 potential tables and F3 cell tables of each country, member m0")
    return chart


# -------------------------------------------------------------------------------------------------------------------------- the phase part


def question_figure_keys(technologies: Sequence[str]) -> tuple[str, ...]:
    """The artifact keys of the figures of one country (the PhaseSpec `produces`; they do not depend on the country)."""
    keys = []
    for tech in technologies:
        keys += [
            f"potential_supply_curve_capacity_{tech}",
            f"potential_supply_curve_energy_{tech}",
            f"potential_change_map_{tech}",
        ]
    keys += ["potential_land_range", "potential_change_total"]
    return tuple(keys)


def question_figure_names(iso: str, technologies: Sequence[str]) -> dict[str, str]:
    names: dict[str, str] = {}
    for tech in technologies:
        names[f"potential_supply_curve_capacity_{tech}"] = supply_name(iso, "capacity", tech)
        names[f"potential_supply_curve_energy_{tech}"] = supply_name(iso, "energy", tech)
        names[f"potential_change_map_{tech}"] = change_sheet_name(iso, tech)
    names["potential_land_range"] = land_range_name(iso)
    names["potential_change_total"] = change_total_name(iso)
    assert list(names) == list(question_figure_keys(technologies))
    return names


def build_question_figures(
    iso: str,
    technologies: Sequence[str],
    ctx: MapContext,
    out_dir: Path,
    *,
    potential_dir: Path | None = None,
    cells_dir: Path | None = None,
    members_yaml: Path | None = None,
    display_smoothing: str = "auto",
    country: str | None = None,
    preset: str = "thesis",
) -> dict[str, Path]:
    """The figures of items 1, 3 and 4 of one country, by artifact key. A technology without candidate cells is left out of every figure."""
    out_dir = Path(out_dir)
    members_yaml = Path(
        members_yaml or core_paths.phase_dir(iso, "climate_forcing", "artifacts") / "members.yaml"
    )
    if not members_yaml.is_file():
        raise ThesisFiguresError(f"missing input {members_yaml}")
    members = read_members(members_yaml)
    by_tech: dict[str, TechData] = {}
    for tech in technologies:
        data = read_tech(iso, tech, potential_dir=potential_dir, cells_dir=cells_dir)
        if data.reference[CENTRAL].empty or float(data.reference[CENTRAL]["P_MW"].sum()) <= 0:
            logger.warning("%s %s has no candidate cell: left out of the figures", iso, tech)
            continue
        by_tech[tech] = data
    names = question_figure_names(iso, technologies)
    written: dict[str, Path] = {}
    kw = {"preset": preset, "country": country}
    for tech, data in by_tech.items():
        shared = cf_limits(list(data.reference.values()))
        for quantity in ("capacity", "energy"):
            chart = supply_chart(iso, data, quantity, limits=shared, **kw)
            key = f"potential_supply_curve_{quantity}_{tech}"
            written[key] = ms.save_png(chart, out_dir / names[key])
        sheet = change_sheet(ctx, iso, data, members, display_smoothing=display_smoothing, **kw)
        key = f"potential_change_map_{tech}"
        written[key] = ms.save_png(sheet, out_dir / names[key])
        data.members.clear()  # the rows of the members are large: the rest of the figures needs only the aggregates
    if by_tech:
        chart = land_range_chart(iso, by_tech, **kw)
        written["potential_land_range"] = ms.save_png(
            chart, out_dir / names["potential_land_range"]
        )
        chart = change_total_chart(iso, by_tech, members, **kw)
        written["potential_change_total"] = ms.save_png(
            chart, out_dir / names["potential_change_total"]
        )
    if written:
        ms.write_figures_index(out_dir)
    return {k: written[k] for k in names if k in written}


def build_comparison(
    countries: Sequence[str],
    technologies: Sequence[str],
    *,
    names: dict[str, str] | None = None,
    out_dir: Path | None = None,
) -> list[Path]:
    """The comparison figures of the countries that have the tables of F3, F4 and F5 (a country that lacks them is left out and the log says
    so); nothing is drawn for fewer than two countries. They go to `outputs/comparison/figures/`."""
    out_dir = Path(out_dir or comparison_dir())
    names = names or {iso: _country_name(iso) for iso in countries}
    available = []
    for iso in countries:
        try:
            for tech in technologies:
                read_tech(iso, tech, with_members=False)
            if not (
                core_paths.phase_dir(iso, "climate_forcing", "artifacts") / "members.yaml"
            ).is_file():
                raise ThesisFiguresError("members.yaml")
            available.append(iso)
        except (ThesisFiguresError, FileNotFoundError, OSError) as error:
            logger.warning("%s has no tables for the comparison (%s): left out", iso, error)
    if len(available) < 2:
        logger.warning("fewer than two countries have the tables of F5: no comparison figure")
        return []
    members = {
        iso: read_members(
            core_paths.phase_dir(iso, "climate_forcing", "artifacts") / "members.yaml"
        )
        for iso in available
    }
    written: list[Path] = []
    for tech in technologies:
        by_country = {iso: read_tech(iso, tech, with_members=False) for iso in available}
        by_country = {
            iso: d for iso, d in by_country.items() if float(d.reference[CENTRAL]["P_MW"].sum()) > 0
        }
        if len(by_country) < 2:
            continue
        shared = cf_limits([t for d in by_country.values() for t in d.reference.values()])
        sheet = comparison_sheet(
            by_country, tech, {i: members[i] for i in by_country}, names=names, limits=shared
        )
        written.append(ms.save_png(sheet, out_dir / comparison_name("comparison", tech)))
        chart = comparison_supply_chart(by_country, tech, names=names, limits=shared)
        written.append(ms.save_png(chart, out_dir / comparison_name("supply-curve-per-area", tech)))
    if written:
        ms.write_figures_index(out_dir)
    return written
