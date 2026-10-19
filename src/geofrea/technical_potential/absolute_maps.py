"""Maps of the technical potential in capacity and energy, per cell and per state, with classes from the distribution (D-F5-029).

For every technology of a country, at the reference climate (member `m0`):

  - per cell, central land scenario: installable capacity (MW per cell) and annual energy (GWh per year per cell), 7 classes by quantiles
    of the cells with a value above zero (the distribution is very skewed);
  - per state (admin1 unit of F3), in each of the three land scenarios: capacity (GW per state) and energy (TWh per year per state), 6
    classes by Fisher-Jenks natural breaks (`mapclassify`) of the state totals of the central scenario, the same classes in the three
    maps so that the colours are comparable between scenarios, the last class open ("> limit") so that a state of the restrictive or the
    permissive scenario above the largest central value falls in it (D-F5-030).

The class limits are never fixed: they come from the data of the country and the technology, are rounded to the configured significant
figures (the last limit of a closed class upwards, so that the largest value is inside; an open last class has none), and a class that
collapses with its neighbour after the rounding is dropped and recorded. The limits go to `potential_breaks_<tech>.json` beside the figures, with the totals that the maps are checked against.
The sum of the cells and the sum of the states must equal the national total of F5 within 0.1% in every scenario, or the phase fails (A-09).

Files (one map per file, `<map>__<window>__<ssp>__<gcm>.png`, 300 dpi) under `outputs/<ISO3>/technical_potential/figures/`:
`potential_capacity_mw_cell_<tech>_central__ref__na__na.png`, `potential_energy_gwh_cell_<tech>_central__ref__na__na.png`,
`potential_capacity_gw_state_<tech>_<scenario>__ref__na__na.png`, `potential_energy_twh_state_<tech>_<scenario>__ref__na__na.png`.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID
from geofrea.core.config_schemas import AbsoluteMapsConfig
from geofrea.core.constants import CELL_ORIGIN_LAT, CELL_ORIGIN_LON
from geofrea.core.scale import active_scale
from geofrea.land_eligibility.map_raster import cell_grid
from geofrea.land_eligibility.scenarios import LAND_SCENARIOS

CENTRAL = "central"
TOTAL_TOLERANCE = (
    1e-3  # 0.1% between the sum of the cells, the sum of the states and the F5 national total
)
NO_VALUE_COLOUR = "#d9d9d9"  # a cell of the country with no potential (not a candidate, or zero)
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


@dataclass(frozen=True)
class CountryUnits:
    """The admin1 units of the country as drawn: `admin1_id`, `admin1_name`, geometry in degrees."""

    units: gpd.GeoDataFrame


def _scenario_table(potential_dir: Path, cells_dir: Path, tech: str, scenario: str) -> pd.DataFrame:
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
    cells = pd.read_parquet(cells_path, columns=["cell_id", "admin1_id"])
    if cells["admin1_id"].isna().any():
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


def _palette(name: str, n: int) -> list[tuple[float, ...]]:
    return [tuple(c) for c in plt.get_cmap(name)(np.linspace(0.0, 1.0, max(n, 1)))]


def _legend(ax, breaks: ClassBreaks, colours, unit: str) -> None:
    handles = [
        Patch(
            facecolor=colours[i],
            edgecolor="none",
            label=f"> {format_limit(lo)}"
            if hi is None
            else f"{format_limit(lo)} - {format_limit(hi)}",
        )
        for i, (lo, hi) in enumerate(breaks.intervals())
    ]
    handles.append(
        Patch(
            facecolor=NO_VALUE_COLOUR, edgecolor="none", label="no potential (not eligible or zero)"
        )
    )
    ax.legend(
        handles=handles,
        title=unit,
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        fontsize=7,
        title_fontsize=8,
        frameon=False,
    )


def _boundaries(ax, units: gpd.GeoDataFrame) -> None:
    units.boundary.plot(ax=ax, color="#333333", linewidth=0.25)
    gpd.GeoSeries([units.union_all()], crs=units.crs).boundary.plot(
        ax=ax, color="black", linewidth=0.6
    )


def _finish(fig, ax, title: str, path: Path, dpi: int) -> Path:
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("Longitude (deg)", fontsize=8)
    ax.set_ylabel("Latitude (deg)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.set_aspect("equal")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _plot_cells(
    cell_ids: np.ndarray,
    values: np.ndarray,
    breaks: ClassBreaks,
    units: gpd.GeoDataFrame,
    unit: str,
    title: str,
    path: Path,
    cfg: AbsoluteMapsConfig,
) -> Path:
    """One cell map: classes in the palette, cells of the country without potential in light grey, everything else white."""
    grid, row0, col0 = cell_grid(cell_ids, values)
    classes = np.full(grid.shape, -2, dtype="int64")  # -2: no cell of the country
    classes[_in_country(cell_ids, row0, col0, grid.shape)] = -1
    positive = np.isfinite(grid) & (grid > 0)
    classes[positive] = breaks.assign(grid[positive])
    colours = _palette(cfg.palette, breaks.n_classes)
    image = np.ones(grid.shape + (3,))
    image[classes == -1] = matplotlib.colors.to_rgb(NO_VALUE_COLOUR)
    for i, colour in enumerate(colours):
        image[classes == i] = colour[:3]
    cell = active_scale().cell_deg
    west = CELL_ORIGIN_LON + col0 * cell
    north = CELL_ORIGIN_LAT - row0 * cell
    fig, ax = plt.subplots(figsize=(8, 6.5))
    ax.imshow(
        image,
        extent=(west, west + grid.shape[1] * cell, north - grid.shape[0] * cell, north),
        origin="upper",
        interpolation="nearest",
    )
    _boundaries(ax, units)
    _legend(ax, breaks, colours, unit)
    return _finish(fig, ax, title, path, cfg.dpi)


def _in_country(cell_ids: np.ndarray, row0: int, col0: int, shape: tuple[int, int]) -> np.ndarray:
    """Boolean grid, True at the cells of the country (every id in `cell_ids`), including the cells whose value is NaN."""
    from geofrea.land_eligibility.cells import row_col_from_id

    rows, cols = row_col_from_id(cell_ids)
    mask = np.zeros(shape, dtype=bool)
    mask[rows - row0, cols - col0] = True
    return mask


def _plot_states(
    state_values: pd.Series,
    breaks: ClassBreaks,
    units: gpd.GeoDataFrame,
    unit: str,
    title: str,
    path: Path,
    cfg: AbsoluteMapsConfig,
) -> Path:
    colours = _palette(cfg.palette, breaks.n_classes)
    values = units["admin1_id"].map(state_values).fillna(0.0).to_numpy()
    classes = breaks.assign(values)
    face = [colours[c] if c >= 0 else matplotlib.colors.to_rgba(NO_VALUE_COLOUR) for c in classes]
    fig, ax = plt.subplots(figsize=(8, 6.5))
    units.plot(ax=ax, color=face, edgecolor="#333333", linewidth=0.25)
    gpd.GeoSeries([units.union_all()], crs=units.crs).boundary.plot(
        ax=ax, color="black", linewidth=0.6
    )
    _legend(ax, breaks, colours, unit)
    return _finish(fig, ax, title, path, cfg.dpi)


# --------------------------------------------------------------------------------------------------------------- the phase part


def absolute_map_names(tech: str) -> dict[str, str]:
    """Artifact key -> file name of the maps and of the limits file of one technology (the PhaseSpec `produces` and the writer agree)."""
    names = {
        f"potential_capacity_cell_{tech}": f"potential_capacity_mw_cell_{tech}_{CENTRAL}__ref__na__na.png",
        f"potential_energy_cell_{tech}": f"potential_energy_gwh_cell_{tech}_{CENTRAL}__ref__na__na.png",
        f"potential_breaks_{tech}": f"potential_breaks_{tech}.json",
    }
    for scenario in SCENARIOS:
        names[f"potential_capacity_state_{tech}__{scenario}"] = (
            f"potential_capacity_gw_state_{tech}_{scenario}__ref__na__na.png"
        )
        names[f"potential_energy_state_{tech}__{scenario}"] = (
            f"potential_energy_twh_state_{tech}_{scenario}__ref__na__na.png"
        )
    return names


def build_absolute_maps(
    iso: str,
    tech: str,
    potential_dir: Path,
    cells_dir: Path,
    figures_dir: Path,
    units: gpd.GeoDataFrame,
    cfg: AbsoluteMapsConfig,
) -> tuple[dict[str, Path], dict[str, Any]]:
    """The 8 maps and the limits file of one technology; returns (artifact key -> path, the content of the limits file).

    Raises:
        AbsoluteMapsError: a table is missing, or the sum of the cells or of the states differs from the F5 national total by more than 0.1%.
    """
    names = absolute_map_names(tech)
    out = Path(figures_dir)
    tables = {s: _scenario_table(potential_dir, cells_dir, tech, s) for s in SCENARIOS}
    totals = _national_totals(potential_dir, tech)
    checks: dict[str, Any] = {}
    states: dict[str, pd.DataFrame] = {}
    for scenario, table in tables.items():
        p_gw, e_twh = table["P_MW"].sum() / 1e3, table["E_MWh"].sum() / 1e6
        by_state = table.groupby("admin1_id")[["P_MW", "E_MWh"]].sum(min_count=1).fillna(0.0)
        states[scenario] = pd.DataFrame(
            {"capacity_gw": by_state["P_MW"] / 1e3, "energy_twh": by_state["E_MWh"] / 1e6}
        )
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
    cap_mw, en_gwh = central["P_MW"].to_numpy(), central["E_MWh"].to_numpy() / 1e3
    cell_cap = class_breaks(cap_mw, cfg.per_cell.method, cfg.per_cell.classes, sig)
    cell_en = class_breaks(en_gwh, cfg.per_cell.method, cfg.per_cell.classes, sig)
    basis = SCENARIOS if cfg.per_state.basis == "all_scenarios" else (CENTRAL,)
    on = {
        q: pd.concat([states[s][q] for s in basis]).to_numpy()
        for q in ("capacity_gw", "energy_twh")
    }
    open_last = cfg.per_state.open_last_class
    state_cap = class_breaks(
        on["capacity_gw"], cfg.per_state.method, cfg.per_state.classes, sig, open_last=open_last
    )
    state_en = class_breaks(
        on["energy_twh"], cfg.per_state.method, cfg.per_state.classes, sig, open_last=open_last
    )

    written: dict[str, Path] = {}
    gw_c, twh_c = totals[CENTRAL]
    what = f"{iso} {tech}, reference climate"
    written[f"potential_capacity_cell_{tech}"] = _plot_cells(
        ids, cap_mw, cell_cap, units, UNIT_CELL_CAPACITY,
        f"{what}, central land scenario: installable capacity per cell\nNational total {gw_c:,.1f} GW, {twh_c:,.1f} TWh per year",
        out / names[f"potential_capacity_cell_{tech}"], cfg,
    )  # fmt: skip
    written[f"potential_energy_cell_{tech}"] = _plot_cells(
        ids, en_gwh, cell_en, units, UNIT_CELL_ENERGY,
        f"{what}, central land scenario: annual energy per cell\nNational total {gw_c:,.1f} GW, {twh_c:,.1f} TWh per year",
        out / names[f"potential_energy_cell_{tech}"], cfg,
    )  # fmt: skip
    for scenario in SCENARIOS:
        gw, twh = totals[scenario]
        total = f"National total {gw:,.1f} GW, {twh:,.1f} TWh per year"
        written[f"potential_capacity_state_{tech}__{scenario}"] = _plot_states(
            states[scenario]["capacity_gw"], state_cap, units, UNIT_STATE_CAPACITY,
            f"{what}, {scenario} land scenario: installable capacity per state\n{total}",
            out / names[f"potential_capacity_state_{tech}__{scenario}"], cfg,
        )  # fmt: skip
        written[f"potential_energy_state_{tech}__{scenario}"] = _plot_states(
            states[scenario]["energy_twh"], state_en, units, UNIT_STATE_ENERGY,
            f"{what}, {scenario} land scenario: annual energy per state\n{total}",
            out / names[f"potential_energy_state_{tech}__{scenario}"], cfg,
        )  # fmt: skip

    content = {
        "country_code": iso,
        "technology": tech,
        "climate": "reference (member m0)",
        "significant_figures": sig,
        "per_cell": {
            "land_scenario": CENTRAL,
            "capacity": {"unit": UNIT_CELL_CAPACITY, **cell_cap.as_json()},
            "energy": {"unit": UNIT_CELL_ENERGY, **cell_en.as_json()},
        },
        "per_state": {
            "land_scenarios": list(SCENARIOS),
            "classes_computed_on": f"the state totals of the {' and '.join(basis)} scenario(s); the same classes in the three maps"
            + ("; the last class is open (above its lower limit)" if open_last else ""),
            "capacity": {"unit": UNIT_STATE_CAPACITY, **state_cap.as_json()},
            "energy": {"unit": UNIT_STATE_ENERGY, **state_en.as_json()},
        },
        "national_totals_f5": {s: {"P_GW": totals[s][0], "E_TWh": totals[s][1]} for s in SCENARIOS},
        "sum_checks": checks,
        "tolerance": TOTAL_TOLERANCE,
    }
    breaks_path = out / names[f"potential_breaks_{tech}"]
    breaks_path.write_text(json.dumps(content, indent=1), encoding="utf-8")
    written[f"potential_breaks_{tech}"] = breaks_path
    return written, content
