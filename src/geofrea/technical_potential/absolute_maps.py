"""Maps of the technical potential, in the common style: densities per cell and per state, with circles for the state totals (COMMAND 60).

For every technology of a country, at the reference climate (member `m0`):

  - per cell, central land scenario: capacity density (MW per km2 of the land area of the cell) and energy density (GWh per km2 per year),
    continuous, with the robust norm of the style (`viz/mapstyle.py`), one pixel per cell of 0.05 degree, nothing interpolated;
  - per state (admin1 unit of F3), in each of the three land scenarios: the same two densities as a choropleth (the total of the state over its
    land area, not the total, which the size of the state dominates), 6 classes by Fisher-Jenks natural breaks of the central scenario, the same
    classes in the three maps, the last class open ("> limit"); over each state a circle whose area is proportional to its total (GW or TWh
    per year), one circle scale for the three scenarios;
  - with `absolute_maps.per_cell: true`, the classed maps of MW and GWh per cell of the earlier version (7 classes by quantiles).

The class limits are never fixed: they come from the data of the country and the technology, are rounded to the configured significant
figures (the last limit of a closed class upwards, so that the largest value is inside; an open last class has none), and a class that
collapses with its neighbour after the rounding is dropped and recorded. The limits go to `potential_breaks_<tech>.json` beside the figures,
with the totals that the maps are checked against. The sum of the cells and the sum of the states must equal the national total of F5 within
0.1% in every scenario, or the phase fails (A-09).

Files (one map per file, `<map>__<window>__<ssp>__<gcm>.png`, 300 dpi) under `outputs/<ISO3>/technical_potential/figures/`:
`potential_capacity_density_<tech>_central__ref__na__na.png`, `potential_energy_density_<tech>_central__ref__na__na.png`,
`potential_capacity_density_state_<tech>_<scenario>__ref__na__na.png`, `potential_energy_density_state_<tech>_<scenario>__ref__na__na.png`
(and, with `per_cell`, `potential_capacity_mw_cell_<tech>_central...` and `potential_energy_gwh_cell_<tech>_central...`).
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import numpy as np
import pandas as pd

from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID
from geofrea.core.config_schemas import AbsoluteMapsConfig
from geofrea.core.constants import CELL_ORIGIN_LAT, CELL_ORIGIN_LON
from geofrea.core.scale import active_scale
from geofrea.land_eligibility.cells import row_col_from_id
from geofrea.land_eligibility.map_raster import cell_grid
from geofrea.land_eligibility.scenarios import LAND_SCENARIOS
from geofrea.technical_potential.display_layers import load_display_layer
from geofrea.technical_potential.state_figures import (
    ranking_chart,
    ranking_name,
    state_sheet,
    state_sheet_name,
)
from geofrea.viz import mapstyle as ms
from geofrea.viz.context import (  # noqa: F401  (the context moved to viz; the names stay importable from here)
    MapContext,
    country_geometry,
    load_neighbours,
    map_context,
    technology_name,
)
from geofrea.viz.display import DisplayLayer

CENTRAL = "central"
TOTAL_TOLERANCE = (
    1e-3  # 0.1% between the sum of the cells, the sum of the states and the F5 national total
)
UNIT_CELL_CAPACITY, UNIT_CELL_ENERGY = "MW per cell", "GWh per year per cell"
UNIT_STATE_CAPACITY, UNIT_STATE_ENERGY = "GW per state", "TWh per year per state"
SCENARIOS = tuple(LAND_SCENARIOS)


class AbsoluteMapsError(RuntimeError):
    """An input of the maps is missing, or a total does not add up (A-09)."""


# ---------------------------------------------------------------------------------------------------------- the class limits


@dataclass(frozen=True)
class ClassBreaks:
    """Upper limits of the classes of the values above zero; class i holds (limits[i-1], limits[i]], with limits[-1] before the first = 0.

    With `open_last` the last class has no upper limit: it holds every value above `limits[-1]` ("> limit"), so there is one class more than limits.
    """

    method: str
    requested: int
    limits: tuple[float, ...]
    raw_limits: tuple[float, ...]
    n_values: int
    notes: tuple[str, ...]
    open_last: bool = False

    @property
    def n_classes(self) -> int:
        return len(self.limits) + (1 if self.open_last and self.limits else 0)

    def assign(self, values: np.ndarray) -> np.ndarray:
        """Class index (0-based) of each value above zero; -1 for a value that is not above zero or not finite."""
        values = np.asarray(values, dtype="float64")
        out = np.full(values.shape, -1, dtype="int64")
        positive = np.isfinite(values) & (values > 0)
        out[positive] = np.minimum(
            np.searchsorted(np.asarray(self.limits), values[positive], side="left"),
            self.n_classes - 1,
        )
        return out

    def intervals(self) -> list[tuple[float, float | None]]:
        """(low, high] of every class; the high of an open last class is None."""
        lows = (0.0, *self.limits[: self.n_classes - 1])
        highs = (*self.limits, *((None,) if self.open_last and self.limits else ()))
        return list(zip(lows, highs, strict=True))

    def as_json(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "classes_requested": self.requested,
            "classes_final": self.n_classes,
            "collapsed": self.n_classes < self.requested,
            "last_class_open": bool(self.open_last and self.limits),
            "upper_limits": list(self.limits),
            "upper_limits_before_rounding": list(self.raw_limits),
            "intervals": [[lo, hi] for lo, hi in self.intervals()],
            "n_values_above_zero": self.n_values,
            "notes": list(self.notes),
        }


def round_significant(x: float, figures: int, *, up: bool = False) -> float:
    """`x` rounded to `figures` significant figures, to the nearest or (`up`) upwards."""
    if x == 0 or not math.isfinite(x):
        return x
    exponent = math.floor(math.log10(abs(x)))
    scale = 10.0 ** (figures - 1 - exponent)
    scaled = round(x * scale, 6)
    rounded = math.ceil(scaled) if up else round(scaled)
    return float(f"{rounded / scale:.10g}")


def class_breaks(
    values: np.ndarray, method: str, classes: int, figures: int, *, open_last: bool = False
) -> ClassBreaks:
    """Class limits of the values above zero by `method` (`quantile` or `fisher_jenks`), rounded to `figures` significant figures.

    With `open_last` the largest limit (the maximum of `values`) is dropped and the last class is "> the limit before it": values larger
    than any of `values` belong to it. The number of classes is reduced, and the reduction recorded, when there are fewer distinct values
    than classes or when two limits are the same number after the rounding.
    """
    values = np.asarray(values, dtype="float64")
    values = values[np.isfinite(values) & (values > 0)]
    if values.size == 0:
        return ClassBreaks(method, classes, (), (), 0, ("no value above zero",), open_last)
    notes: list[str] = []
    n_distinct = int(np.unique(values).size)
    k = min(classes, n_distinct)
    if k < classes:
        notes.append(f"{n_distinct} distinct values above zero: {k} classes instead of {classes}")
    if method == "quantile":
        raw = [float(q) for q in np.quantile(values, [i / k for i in range(1, k)])] + [
            float(values.max())
        ]
    elif method == "fisher_jenks":
        import mapclassify

        raw = [float(b) for b in mapclassify.FisherJenks(values, k=k).bins]
    else:
        raise AbsoluteMapsError(f"unknown classification method {method!r}")
    rounded = [round_significant(b, figures) for b in raw[:-1]] + [
        round_significant(raw[-1], figures, up=True)
    ]
    limits: list[float] = []
    for b in rounded:
        if not limits or b > limits[-1]:
            limits.append(b)
    limits = [b for b in limits[:-1] if b < limits[-1]] + [limits[-1]]
    if open_last and len(limits) > 1:
        limits = limits[:-1]  # the last class has no upper limit
    else:
        open_last = False  # one class only: it holds everything
    n_final = len(limits) + (1 if open_last else 0)
    if n_final < k:
        notes.append(
            f"{k - n_final} class(es) merged: limits {rounded} are not distinct at {figures} significant figures; {n_final} classes"
        )
    return ClassBreaks(
        method, classes, tuple(limits), tuple(raw), int(values.size), tuple(notes), open_last
    )


def format_limit(x: float) -> str:
    if x >= 1000:
        return f"{x:,.0f}"
    if x >= 1:
        return f"{x:g}"
    return np.format_float_positional(x, trim="-")


# ------------------------------------------------------------------------------------------------------------------- the data


def _scenario_table(
    potential_dir: Path, cells_dir: Path, tech: str, scenario: str, *, with_admin1: bool = True
) -> pd.DataFrame:
    """Every cell of the country in `scenario` with the `m0` capacity (MW) and energy (MWh/yr); zero where the cell is not a candidate."""
    potential_path = Path(potential_dir) / f"potential_{tech}__{scenario}.parquet"
    cells_path = Path(cells_dir) / f"cells_{tech}__{scenario}.parquet"
    for needed in (potential_path, cells_path):
        if not needed.is_file():
            raise AbsoluteMapsError(f"missing input {needed}")
    reference = pd.read_parquet(
        potential_path,
        columns=["cell_id", "member", "P_MW", "E_MWh"],
        filters=[("member", "==", REFERENCE_MEMBER_ID)],
    )[
        ["cell_id", "P_MW", "E_MWh"]
    ]  # only m0 is read: the tables of the real countries hold 37 members
    cells = pd.read_parquet(
        cells_path, columns=["cell_id", "cell_area_km2", *(["admin1_id"] if with_admin1 else [])]
    )
    if with_admin1 and cells["admin1_id"].isna().any():
        raise AbsoluteMapsError(f"{cells_path.name}: cells without an admin1 unit")
    merged = cells.merge(reference, on="cell_id", how="left", validate="one_to_one")
    if len(reference) != int(merged["P_MW"].notna().sum()):
        raise AbsoluteMapsError(
            f"{potential_path.name}: rows of cells absent from {cells_path.name}"
        )
    return merged


def _national_totals(potential_dir: Path, tech: str) -> dict[str, tuple[float, float]]:
    """F5 national totals of `m0` per scenario: (P_GW, E_TWh), the series over all present cells."""
    aggregates = pd.read_parquet(Path(potential_dir) / f"potential_aggregates_{tech}.parquet")
    ref = aggregates[aggregates["member"].astype(str) == REFERENCE_MEMBER_ID].set_index("scenario")
    return {s: (float(ref.loc[s, "P_GW"]), float(ref.loc[s, "E_TWh"])) for s in ref.index}


def _check(label: str, got: float, expected: float) -> dict[str, float | bool]:
    rel = abs(got - expected) / abs(expected) if expected else abs(got)
    return {
        "got": got,
        "expected": expected,
        "relative_difference": rel,
        "ok": rel <= TOTAL_TOLERANCE,
    }


# --------------------------------------------------------------------------------------------------------------------- drawing
# COMMAND 60: every map is drawn with the common style of `viz/mapstyle.py` (extent from the country, geographic aspect, compass, scale bar,
# neighbours, short title, 300 dpi PNG). Resolution: the cell of the analysis is 0.05 degree (the potential, the capacity factor and the eligible
# share are defined per cell); nothing is interpolated or smoothed, a pixel on the map is a cell.

UNIT_CAPACITY_DENSITY, UNIT_ENERGY_DENSITY = "MW per km²", "GWh per km² per year"
UNIT_CIRCLE_CAPACITY, UNIT_CIRCLE_ENERGY = "Capacity (GW)", "Energy (TWh per year)"
NO_POTENTIAL_LABEL = ms.NO_DATA_LABEL
SUBTITLE_CLIMATE = "reference climate"
logger = logging.getLogger("geofrea.technical_potential.absolute_maps")


def _palette(name: str, n: int) -> list[tuple[float, ...]]:
    return [tuple(c) for c in matplotlib.colormaps[name](np.linspace(0.0, 1.0, max(n, 1)))]


def class_labels(breaks: ClassBreaks) -> tuple[str, ...]:
    return tuple(
        f"> {format_limit(lo)}" if hi is None else f"{format_limit(lo)} - {format_limit(hi)}"
        for lo, hi in breaks.intervals()
    )


def _grid_extent(shape: tuple[int, int], row0: int, col0: int) -> ms.Extent:
    cell = active_scale().cell_deg
    west = CELL_ORIGIN_LON + col0 * cell
    north = CELL_ORIGIN_LAT - row0 * cell
    return (west, west + shape[1] * cell, north - shape[0] * cell, north)


def _in_country(cell_ids: np.ndarray, row0: int, col0: int, shape: tuple[int, int]) -> np.ndarray:
    """Boolean grid, True at the cells of the country (every id in `cell_ids`), including the cells whose value is NaN."""
    rows, cols = row_col_from_id(cell_ids)
    mask = np.zeros(shape, dtype=bool)
    mask[rows - row0, cols - col0] = True
    return mask


def _total_text(gw: float, twh: float) -> str:
    return f"National total\n{gw:,.1f} GW · {twh:,.1f} TWh per year"


def compose_cell_density_map(
    cell_ids: np.ndarray,
    values: np.ndarray,
    ctx: MapContext,
    *,
    iso: str,
    tech: str,
    variable: str,
    label: str,
    kind: str,
    subtitle: str,
    total_text: str | None,
    display_layer: DisplayLayer | None = None,
    display_smoothing: str = "auto",
) -> tuple[ms.MapCanvas, dict[str, Any]]:
    """A continuous map of a per-cell variable at the resolution of the cells, with the robust norm of the style; cells of the country
    without potential (not a candidate, or zero) in light grey. Returns the file and how the colour limits were chosen.

    Display resolution (COMMAND 67b): a finer `display_layer` (0.01 degree, descriptive) is drawn instead of the cells when they would be blocks,
    and `display_smoothing` (`auto`/`off`) interpolates a field whose cell is still a block; the colours and the legend come from the cells."""
    grid, row0, col0 = cell_grid(cell_ids, values)
    extent_grid = _grid_extent(grid.shape, row0, col0)
    positive = np.isfinite(grid) & (grid > 0)
    data = np.where(positive, grid, np.nan)
    info = ms.resolve_scale(grid[positive], ms.default_scale(kind, tech))
    resolution = ms.resolution_note(cell_deg=active_scale().cell_deg)

    def build(resolution_text: str | None) -> ms.MapCanvas:
        return ms.new_map(
            ctx.polygon,
            iso=iso,
            technology=technology_name(tech),
            variable=variable,
            subtitle=ms.format_subtitle(subtitle, resolution_text, ms.clip_note(info, label)),
            total_text=total_text,
            neighbours=ctx.neighbours,
            extent=ctx.extent,
            contiguous=False,
            no_data_label=NO_POTENTIAL_LABEL,
        )

    canvas = build(resolution)
    plan = ms.plan_display(canvas, data, extent_grid, resolution, display_layer, display_smoothing)
    if plan.shown != resolution:
        ms.close_figure(canvas)
        canvas = build(plan.shown)
    canvas.meta.update(ms.display_meta(plan, display_smoothing))
    canvas.fill_country()  # the cells of the country without potential show the grey of "no potential" under the data
    image = canvas.draw_raster(
        np.ma.masked_invalid(plan.grid),
        plan.extent,
        cmap=ms.colormap_for(kind, tech),
        norm=info.norm,
        smooth=plan.factor,
    )
    ms.add_colorbar(canvas, image, label, info.extend)
    return canvas, {
        "unit": label,
        "norm": info.kind,
        "colour_limits": [info.vmin, info.vmax],
        "scale_mode": info.mode,
        "scale_scope": info.scope,
        "percentiles": list(ms.CLIP_PERCENTILES),
        "extend": info.extend,
        "p98_over_p50": None if not math.isfinite(info.skew) else info.skew,
        "cells_with_value": int(positive.sum()),
        "cell_deg": active_scale().cell_deg,
        "interpolation": "display smoothing" if plan.smooth else "none (one pixel is one cell)",
        "display_px_per_cell": round(plan.px, 1),
    }


def draw_cell_density_map(
    *args, path: Path, data_source: str | None = None, **kwargs
) -> tuple[Path, dict[str, Any]]:
    """`compose_cell_density_map`, saved as PNG at `path` (with its `data_source` in the metadata); returns the file and how the colour limits were chosen."""
    canvas, info = compose_cell_density_map(*args, **kwargs)
    meta = {"data_source": data_source} if data_source else None
    return ms.save_png(canvas, path, meta), info


def draw_classed_cell_map(
    cell_ids: np.ndarray,
    values: np.ndarray,
    breaks: ClassBreaks,
    ctx: MapContext,
    *,
    iso: str,
    tech: str,
    variable: str,
    unit: str,
    subtitle: str,
    total_text: str,
    palette: str,
    path: Path,
) -> Path:
    """The per-cell map with classes (MW or GWh per cell), kept for `absolute_maps.per_cell: true`; same style as the others."""
    grid, row0, col0 = cell_grid(cell_ids, values)
    extent_grid = _grid_extent(grid.shape, row0, col0)
    in_country = _in_country(cell_ids, row0, col0, grid.shape)
    positive = np.isfinite(grid) & (grid > 0)
    classes = np.full(grid.shape, -2, dtype="int64")
    classes[in_country] = -1
    classes[positive] = breaks.assign(grid[positive])
    colours = _palette(palette, breaks.n_classes)
    image = np.zeros(grid.shape + (4,))
    image[classes == -1] = matplotlib.colors.to_rgba(ms.NO_DATA_COLOUR)
    for i, colour in enumerate(colours):
        image[classes == i] = colour
    spec = ms.ClassedLegend(
        title=unit,
        labels=class_labels(breaks),
        colours=tuple(colours),
        no_value_label=NO_POTENTIAL_LABEL,
    )
    side, below = ms.legend_space(spec)
    canvas = ms.new_map(
        ctx.polygon,
        iso=iso,
        technology=technology_name(tech),
        variable=variable,
        subtitle=subtitle,
        total_text=total_text,
        neighbours=ctx.neighbours,
        extent=ctx.extent,
        contiguous=False,
        legend_side_mm=side,
        legend_below_mm=below,
    )
    canvas.draw_raster(image, extent_grid)
    ms.draw_classed_legend(canvas, spec)
    return ms.save_png(canvas, path)


# --------------------------------------------------------------------------------------------------------------- the phase part


def absolute_map_keys(tech: str, per_cell: bool = False) -> tuple[str, ...]:
    """The artifact keys of the maps and of the limits file of one technology (the PhaseSpec `produces`; they do not depend on the country).

    The maps of MW and GWh per cell are in the list only when `absolute_maps.per_cell` is true."""
    keys = [
        f"potential_capacity_density_{tech}",
        f"potential_energy_density_{tech}",
        f"potential_capacity_density_state_{tech}",
        f"potential_energy_density_state_{tech}",
        f"potential_capacity_density_ranking_{tech}",
        f"potential_energy_density_ranking_{tech}",
        f"potential_breaks_{tech}",
    ]
    if per_cell:
        keys += [f"potential_capacity_cell_{tech}", f"potential_energy_cell_{tech}"]
    return tuple(keys)


def absolute_map_names(iso: str, tech: str, per_cell: bool = False) -> dict[str, str]:
    """Artifact key -> file name of the maps and of the limits file of one technology of the country `iso`, in the standard names
    (`mapstyle.figure_filename`; the writer and the `produces` agree through the keys)."""
    fn = ms.figure_filename
    names = {
        f"potential_capacity_density_{tech}": fn(
            iso, "F5", "capacity-density", tech, CENTRAL, "ref"
        ),
        f"potential_energy_density_{tech}": fn(iso, "F5", "energy-density", tech, CENTRAL, "ref"),
        f"potential_capacity_density_state_{tech}": state_sheet_name(iso, "capacity", tech),
        f"potential_energy_density_state_{tech}": state_sheet_name(iso, "energy", tech),
        f"potential_capacity_density_ranking_{tech}": ranking_name(iso, "capacity", tech),
        f"potential_energy_density_ranking_{tech}": ranking_name(iso, "energy", tech),
        f"potential_breaks_{tech}": f"potential_breaks_{tech}.json",
    }
    if per_cell:
        names[f"potential_capacity_cell_{tech}"] = fn(
            iso, "F5", "capacity-per-cell", tech, CENTRAL, "ref"
        )
        names[f"potential_energy_cell_{tech}"] = fn(
            iso, "F5", "energy-per-cell", tech, CENTRAL, "ref"
        )
    assert list(names) == list(absolute_map_keys(tech, per_cell))
    return names


def capacity_factor_name(iso: str, tech: str) -> str:
    return ms.figure_filename(iso, "F5", "capacity-factor", tech, CENTRAL, "ref")


def build_cell_density_maps(
    iso: str,
    tech: str,
    potential_dir: Path,
    cells_dir: Path,
    figures_dir: Path,
    units: gpd.GeoDataFrame | None,
    neighbours=None,
    ctx: MapContext | None = None,
    display_smoothing: str = "auto",
) -> tuple[dict[str, Path], dict[str, Any]]:
    """The two continuous maps of the central scenario (capacity density, energy density) and how their colour limits were chosen.

    The 0.01 degree display layers of the technology (`display_layers`, in `potential_dir`) are drawn when the cells would be blocks.

    Raises:
        AbsoluteMapsError: a table is missing.
    """
    names = absolute_map_names(iso, tech)
    table = _scenario_table(potential_dir, cells_dir, tech, CENTRAL, with_admin1=False)
    totals = _national_totals(potential_dir, tech)
    ids = table["cell_id"].to_numpy()
    area = table["cell_area_km2"].to_numpy(dtype="float64")
    ctx = ctx or map_context(country_geometry(units, ids), neighbours)
    gw, twh = totals[CENTRAL]
    subtitle = f"{CENTRAL.capitalize()} scenario · {SUBTITLE_CLIMATE}"
    out = Path(figures_dir)
    written: dict[str, Path] = {}
    info: dict[str, Any] = {}
    for key, variable, values, label, kind, layer in (
        (
            f"potential_capacity_density_{tech}",
            "Capacity density",
            table["P_MW"].to_numpy() / area,
            UNIT_CAPACITY_DENSITY,
            "potential",
            "capacity-density",
        ),
        (
            f"potential_energy_density_{tech}",
            "Energy density",
            table["E_MWh"].to_numpy() / 1e3 / area,
            UNIT_ENERGY_DENSITY,
            "energy",
            "energy-density",
        ),
    ):
        written[key], info[key] = draw_cell_density_map(
            ids,
            values,
            ctx,
            iso=iso,
            tech=tech,
            variable=variable,
            label=label,
            kind=kind,
            subtitle=subtitle,
            total_text=_total_text(gw, twh),
            path=out / names[key],
            data_source=f"F5 potential_{tech}__{CENTRAL}, member m0",
            display_layer=load_display_layer(potential_dir, layer, tech),
            display_smoothing=display_smoothing,
        )
    return written, info


def build_absolute_maps(
    iso: str,
    tech: str,
    potential_dir: Path,
    cells_dir: Path,
    figures_dir: Path,
    units: gpd.GeoDataFrame,
    cfg: AbsoluteMapsConfig,
    neighbours=None,
    ctx: MapContext | None = None,
) -> tuple[dict[str, Path], dict[str, Any]]:
    """The maps of one technology and the limits file; returns (artifact key -> path, the content of the limits file).

    The two continuous density maps of the cells, the choropleth of the density of the states with circles of their totals in each land
    scenario (classes from the central scenario, the same in the three), and, with `cfg.per_cell`, the classed maps of MW and GWh per cell.

    Raises:
        AbsoluteMapsError: a table is missing, or the sum of the cells or of the states differs from the F5 national total by more than 0.1%.
    """
    names = absolute_map_names(iso, tech, cfg.per_cell)
    out = Path(figures_dir)
    tables = {s: _scenario_table(potential_dir, cells_dir, tech, s) for s in SCENARIOS}
    totals = _national_totals(potential_dir, tech)
    checks: dict[str, Any] = {}
    states: dict[str, pd.DataFrame] = {}
    for scenario, table in tables.items():
        p_gw, e_twh = table["P_MW"].sum() / 1e3, table["E_MWh"].sum() / 1e6
        by_state = table.groupby("admin1_id")[["P_MW", "E_MWh"]].sum(min_count=1).fillna(0.0)
        area = table.groupby("admin1_id")["cell_area_km2"].sum()
        states[scenario] = pd.DataFrame(
            {
                "capacity_gw": by_state["P_MW"] / 1e3,
                "energy_twh": by_state["E_MWh"] / 1e6,
                "area_km2": area.reindex(by_state.index),
            }
        )
        states[scenario]["capacity_density"] = by_state["P_MW"] / states[scenario]["area_km2"]
        states[scenario]["energy_density"] = by_state["E_MWh"] / 1e3 / states[scenario]["area_km2"]
        unknown = set(states[scenario].index) - set(units["admin1_id"])
        if unknown:
            raise AbsoluteMapsError(
                f"{scenario}: admin1 units of the cells not in the admin1 layer: {sorted(unknown)}"
            )
        expected_gw, expected_twh = totals[scenario]
        checks[scenario] = {
            "capacity_gw": {
                "cells": _check("cells", float(p_gw), expected_gw),
                "states": _check(
                    "states", float(states[scenario]["capacity_gw"].sum()), expected_gw
                ),
            },
            "energy_twh": {
                "cells": _check("cells", float(e_twh), expected_twh),
                "states": _check(
                    "states", float(states[scenario]["energy_twh"].sum()), expected_twh
                ),
            },
        }
    bad = [
        f"{s} {q} {kind}: {c['got']:.6g} against {c['expected']:.6g}"
        for s, by_q in checks.items()
        for q, by_kind in by_q.items()
        for kind, c in by_kind.items()
        if not c["ok"]
    ]
    if bad:
        raise AbsoluteMapsError(
            f"{iso} {tech}: the maps do not add up to the F5 national total (tolerance 0.1%): {bad}"
        )

    sig = cfg.significant_figures
    central = tables[CENTRAL]
    ids = central["cell_id"].to_numpy()
    ctx = ctx or map_context(country_geometry(units, ids), neighbours)
    written, density_info = build_cell_density_maps(
        iso,
        tech,
        potential_dir,
        cells_dir,
        out,
        units,
        neighbours,
        ctx,
        display_smoothing=cfg.display_smoothing,
    )

    basis = SCENARIOS if cfg.per_state.basis == "all_scenarios" else (CENTRAL,)
    on = {
        q: pd.concat([states[s][q] for s in basis]).to_numpy()
        for q in ("capacity_density", "energy_density")
    }
    open_last = cfg.per_state.open_last_class
    state_cap = class_breaks(
        on["capacity_density"],
        cfg.per_state.method,
        cfg.per_state.classes,
        sig,
        open_last=open_last,
    )
    state_en = class_breaks(
        on["energy_density"],
        cfg.per_state.method,
        cfg.per_state.classes,
        sig,
        open_last=open_last,
    )
    # one circle scale for the three scenarios of a quantity: the largest state total of the three
    ref_gw = max(float(states[s]["capacity_gw"].max()) for s in SCENARIOS)
    ref_twh = max(float(states[s]["energy_twh"].max()) for s in SCENARIOS)
    totals_text = "\n".join(
        f"{s.capitalize()}: {totals[s][0]:,.1f} GW · {totals[s][1]:,.1f} TWh per year"
        for s in ("restrictive", "central", "permissive")
    )
    circles: dict[str, Any] = {}
    for quantity, breaks, unit, circle_unit, reference in (
        ("capacity", state_cap, UNIT_CAPACITY_DENSITY, UNIT_CIRCLE_CAPACITY, ref_gw),
        ("energy", state_en, UNIT_ENERGY_DENSITY, UNIT_CIRCLE_ENERGY, ref_twh),
    ):
        key = f"potential_{quantity}_density_state_{tech}"
        sheet, circles[key] = state_sheet(
            ctx, iso, tech, units, states, breaks,
            quantity=quantity, unit_label=unit, class_labels=class_labels(breaks),
            circle_title=circle_unit, circle_reference=reference, totals_text=totals_text,
        )  # fmt: skip
        written[key] = ms.save_png(sheet, out / names[key], {"grid": "admin1 units of F1"})
        key = f"potential_{quantity}_density_ranking_{tech}"
        written[key] = ms.save_png(
            ranking_chart(iso, tech, units, states, quantity=quantity, unit_label=unit),
            out / names[key],
        )

    per_cell_content: dict[str, Any] | None = None
    if cfg.per_cell:
        cap_mw, en_gwh = central["P_MW"].to_numpy(), central["E_MWh"].to_numpy() / 1e3
        cell_cap = class_breaks(
            cap_mw, cfg.per_cell_classes.method, cfg.per_cell_classes.classes, sig
        )
        cell_en = class_breaks(
            en_gwh, cfg.per_cell_classes.method, cfg.per_cell_classes.classes, sig
        )
        gw_c, twh_c = totals[CENTRAL]
        subtitle = f"{CENTRAL.capitalize()} scenario · {SUBTITLE_CLIMATE}"
        for key, variable, values, unit, br in (
            (f"potential_capacity_cell_{tech}", "Capacity per cell", cap_mw, UNIT_CELL_CAPACITY, cell_cap),
            (f"potential_energy_cell_{tech}", "Energy per cell", en_gwh, UNIT_CELL_ENERGY, cell_en),
        ):  # fmt: skip
            written[key] = draw_classed_cell_map(
                ids, values, br, ctx, iso=iso, tech=tech, variable=variable, unit=unit,
                subtitle=subtitle, total_text=_total_text(gw_c, twh_c), palette=cfg.palette, path=out / names[key],
            )  # fmt: skip
        per_cell_content = {
            "land_scenario": CENTRAL,
            "capacity": {"unit": UNIT_CELL_CAPACITY, **cell_cap.as_json()},
            "energy": {"unit": UNIT_CELL_ENERGY, **cell_en.as_json()},
        }

    content = {
        "country_code": iso,
        "technology": tech,
        "climate": "reference (member m0)",
        "significant_figures": sig,
        "resolution": {
            "cell_deg": active_scale().cell_deg,
            "note": "the potential, the capacity factor and the eligible share are defined per cell of this size; the maps draw one pixel per cell, "
            "with no interpolation or smoothing",
        },
        "density_cells": {
            "land_scenario": CENTRAL,
            "area": "cell_area_km2 of F3 (the area of the cell inside the territory)",
            **{
                k.removeprefix("potential_").removesuffix(f"_{tech}"): v
                for k, v in density_info.items()
            },
        },
        "per_state": {
            "land_scenarios": list(SCENARIOS),
            "density": "state total over the sum of the land area of its cells (km2)",
            "classes_computed_on": f"the state densities of the {' and '.join(basis)} scenario(s); the same classes in the three maps"
            + ("; the last class is open (above its lower limit)" if open_last else ""),
            "capacity_density": {"unit": UNIT_CAPACITY_DENSITY, **state_cap.as_json()},
            "energy_density": {"unit": UNIT_ENERGY_DENSITY, **state_en.as_json()},
            "circles": circles,
        },
        "per_cell_classed": per_cell_content,
        "national_totals_f5": {s: {"P_GW": totals[s][0], "E_TWh": totals[s][1]} for s in SCENARIOS},
        "sum_checks": checks,
        "tolerance": TOTAL_TOLERANCE,
    }
    breaks_path = out / names[f"potential_breaks_{tech}"]
    breaks_path.write_text(json.dumps(content, indent=1), encoding="utf-8")
    written[f"potential_breaks_{tech}"] = breaks_path
    return written, content
