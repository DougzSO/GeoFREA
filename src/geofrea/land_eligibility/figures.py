"""Figures of the land eligibility in the common map style (COMMAND 68; spec v2 T-10; M-F3-05, A-08).

For each technology of a country (central land scenario):

  - `eligibility_sheet`: two maps side by side (or one above the other for a wide country, `adaptive_grid`): the eligible share of the land of each cell
    in the colours of the technology, and the dominant exclusion of each cell in discrete classes with a legend. The denominator is declared (the
    land area of the cell, from the country mask, not the area of the cell with data) and so is the rule of "dominant";
  - `exclusion_chart`: the share of each exclusion E1 to E6 in the excluded area, stacked bars, one bar per technology;
  - `layer_map`: one map of the excluded share of an exclusion, a diagnostic that is not drawn for the thesis.

The exclusions overlap (a pixel can be both protected and steep), so the areas of the exclusions are measured criterion by criterion and add up to more
than the excluded land; the dominant exclusion of a cell is the one with the largest area, the lower number winning a tie, and `None` where nothing
is excluded. Nothing here changes a number of F3.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import Normalize, to_rgba

from geofrea.core.scale import active_scale
from geofrea.land_eligibility.eligibility import EXCLUSION_NAMES
from geofrea.viz import display
from geofrea.viz import mapstyle as ms
from geofrea.viz.charts import new_chart, stacked_bars
from geofrea.viz.context import MapContext, lattice_of, lattice_of_extent, technology_name, to_grid
from geofrea.viz.panels import (
    PanelFigure,
    adaptive_grid,
    add_panel_classes,
    add_panel_colorbar,
    new_panels,
)

logger = logging.getLogger("geofrea.land_eligibility.figures")

FIGURE_PHASE = "F3"
EXCLUSION_TITLES = {
    "E1": "E1 protected areas",
    "E2": "E2 water bodies",
    "E3": "E3 riparian setback",
    "E4": "E4 steep slope",
    "E5": "E5 land cover",
    "E6": "E6 population",
}
EXCLUSION_SLUGS = {
    "E1": "E1-protected",
    "E2": "E2-water",
    "E3": "E3-riparian",
    "E4": "E4-slope",
    "E5": "E5-land-cover",
    "E6": "E6-population",
}
NONE_LABEL = "None"
DOMINANT_RULE = (
    "Dominant: the exclusion with the largest area in the cell (exclusions overlap); "
    "the lower number wins a tie; None where nothing is excluded"
)
SHARE_LABEL = "Eligible share of the land area of the cell"
CLASS_LABELS = [NONE_LABEL, *(EXCLUSION_TITLES[c] for c in EXCLUSION_NAMES)]
CHECK_TOLERANCE = 0.02  # the fine layer, aggregated to the cell, is within this (share of the cell) of the cell table
SCENARIO = "central"


def class_colours() -> list[str]:
    """The colour of None and of each exclusion, in the order of `CLASS_LABELS` (the Okabe-Ito classes, a grey for None)."""
    return [ms.CLASS_NONE_COLOUR, *ms.class_colours(len(EXCLUSION_NAMES))]


def dominant_codes(cells: pd.DataFrame) -> np.ndarray:
    """0 for None and 1 to 6 for E1 to E6: the exclusion with the largest excluded area of each cell, the lower number on a tie.

    The table of F3 holds the code (`dominant_exclusion`); here it is also recomputed from the areas, so that a table whose code disagrees with
    its areas is noticed."""
    exclusion_codes(cells.columns)
    areas = np.column_stack(
        [cells[f"excluded_area_km2_{c}"].to_numpy(dtype="float64") for c in EXCLUSION_NAMES]
    )
    best = areas.argmax(axis=1) + 1  # argmax takes the first of equal maxima: the lower number
    return np.where(areas.max(axis=1) > 0, best, 0)


def eligible_share(cells: pd.DataFrame) -> np.ndarray:
    return (cells["eligible_area_km2"] / cells["cell_area_km2"]).to_numpy(dtype="float64")


def read_fraction_layer(path: Path) -> display.DisplayLayer | None:
    """The eligible fraction of each 0.01 degree pixel of F3 as a display layer (a descriptive layer: no result reads it)."""
    if not Path(path).is_file():
        return None
    with rasterio.open(path) as src:
        grid = src.read(1).astype("float64")
        nodata, b, cell = src.nodata, src.bounds, abs(src.transform.a)
    if nodata is not None:
        grid[grid == nodata] = np.nan
    return display.DisplayLayer("eligible-fraction", grid, (b.left, b.right, b.bottom, b.top), cell)


def check_fraction_layer(
    layer: display.DisplayLayer, cells: pd.DataFrame, tolerance: float = CHECK_TOLERANCE
) -> display.AggregationCheck:
    """The fine layer aggregated to the cell against the share of the cell table, over the cells that lie wholly inside the country.

    A cell whose land area is less than 99% of the largest has pixels outside the country (the fine layer holds 0 there) and is left out."""
    k = round(active_scale().cell_deg / layer.cell_deg)
    lattice = lattice_of_extent(layer.extent)
    share = to_grid(cells["cell_id"].to_numpy(), eligible_share(cells), lattice)
    area = to_grid(cells["cell_id"].to_numpy(), cells["cell_area_km2"].to_numpy(), lattice)
    if layer.grid.shape != (share.shape[0] * k, share.shape[1] * k):
        return display.AggregationCheck("eligible-fraction", 0, float("inf"), tolerance, False)
    interior = np.isfinite(area) & (area >= 0.99 * np.nanmax(area))
    mean = display.block_mean(layer.grid, k)
    both = interior & np.isfinite(mean) & np.isfinite(share)
    worst = float(np.abs(mean[both] - share[both]).max()) if both.any() else float("inf")
    return display.AggregationCheck(
        "eligible-fraction", int(both.sum()), worst, tolerance, worst <= tolerance
    )


def eligibility_sheet(
    ctx: MapContext,
    iso: str,
    tech: str,
    cells: pd.DataFrame,
    *,
    fraction: display.DisplayLayer | None = None,
    display_smoothing: str = "auto",
    preset: str = "thesis",
    country: str | None = None,
) -> PanelFigure:
    """The sheet of one technology: the eligible share and the dominant exclusion of each cell, the total and the denominator in the footer."""
    lattice = lattice_of(cells["cell_id"].to_numpy())
    extent = lattice.extent
    share = to_grid(cells["cell_id"].to_numpy(), eligible_share(cells), lattice)
    codes = to_grid(cells["cell_id"].to_numpy(), dominant_codes(cells), lattice)
    land_km2 = float(cells["cell_area_km2"].sum())
    eligible_km2 = float(cells["eligible_area_km2"].sum())
    total = (
        f"Eligible: {eligible_km2:,.0f} km² of {land_km2:,.0f} km² of land ({100 * eligible_km2 / land_km2:.1f}%)\n"
        f"{DOMINANT_RULE}"
    )
    rows, cols = adaptive_grid(2, ms.make_frame(ctx.polygon, ctx.extent).ratio)
    resolution = ms.resolution_note(cell_deg=0.05)

    def build(shown: str | None) -> PanelFigure:
        return new_panels(
            ctx.polygon,
            iso=iso,
            technology=technology_name(tech),
            variable="Land eligibility",
            captions=["Eligible share", "Dominant exclusion"],
            n_rows=rows,
            n_cols=cols,
            subtitle=ms.format_subtitle("Central land scenario", shown),
            total_text=total,
            neighbours=ctx.neighbours,
            extent=ctx.extent,
            contiguous=False,
            country=country,
            preset=preset,
            bar="each",
            legend_labels=CLASS_LABELS,
        )

    sheet = build(resolution)
    plan = ms.plan_display(sheet.panels[0], share, extent, resolution, fraction, display_smoothing)
    if plan.shown != resolution:
        ms.close_figure(sheet)
        sheet = build(plan.shown)
    left, right = sheet.panels
    left.fill_country()
    image = left.draw_raster(
        np.ma.masked_invalid(plan.grid),
        plan.extent,
        cmap=ms.colormap_for("eligible_share", tech),
        norm=Normalize(0.0, 1.0),
        smooth=plan.factor,
    )
    add_panel_colorbar(sheet, image, SHARE_LABEL, "neither", 0)
    palette = np.array([to_rgba(c) for c in class_colours()])
    rgba = np.zeros(codes.shape + (4,))
    present = np.isfinite(codes)
    rgba[present] = palette[codes[present].astype(int)]
    right.draw_raster(rgba, extent)
    add_panel_classes(sheet, 1, CLASS_LABELS, class_colours(), "Dominant exclusion")
    sheet.meta.update(ms.display_meta(plan, display_smoothing))
    sheet.meta.update(
        {
            "scale_mode": "fixed",
            "scale_scope": "shared_across_countries",
            "scale_limits": "0,1",
            "denominator": "land area of the cell",
            "dominant_rule": "largest excluded area, ties to the lower number, None when nothing is excluded",
            "data_source": f"F3 cells_{tech}__{SCENARIO}",
        }
    )
    return sheet


def exclusion_shares(cell_tables: dict[str, pd.DataFrame]) -> dict[str, list[float]]:
    """For each exclusion, its share (%) of the sum of the excluded areas of the exclusions, one value per technology (in the order of the tables)."""
    out: dict[str, list[float]] = {c: [] for c in EXCLUSION_NAMES}
    for cells in cell_tables.values():
        areas = {c: float(cells[f"excluded_area_km2_{c}"].sum()) for c in EXCLUSION_NAMES}
        total = sum(areas.values()) or 1.0
        for c in EXCLUSION_NAMES:
            out[c].append(100.0 * areas[c] / total)
    return out


def exclusion_chart(
    iso: str,
    cell_tables: dict[str, pd.DataFrame],
    *,
    preset: str = "thesis",
    country: str | None = None,
):
    """Stacked bars, one per technology: what share of the excluded area each exclusion accounts for."""
    techs = sorted(cell_tables)
    shares = exclusion_shares({t: cell_tables[t] for t in techs})
    land = {t: float(cell_tables[t]["cell_area_km2"].sum()) for t in techs}
    chart = new_chart(
        iso=iso,
        variable="Contribution of each exclusion to the excluded land",
        subtitle="Central land scenario · the exclusions overlap: each is measured alone and the bars add up to 100% of their sum, not of the union",
        n_bars=len(techs),
        labels=[f"{technology_name(t)}\n{land[t]:,.0f} km² of land" for t in techs],
        source="Source: F3 land eligibility, central scenario",
        legend_labels=[EXCLUSION_TITLES[c] for c in EXCLUSION_NAMES],
        preset=preset,
        country=country,
    )
    colours = dict(zip(CLASS_LABELS[1:], class_colours()[1:], strict=True))
    stacked_bars(
        chart,
        [f"{technology_name(t)}\n{land[t]:,.0f} km² of land" for t in techs],
        {EXCLUSION_TITLES[c]: shares[c] for c in EXCLUSION_NAMES},
        colours,
        unit="%",
    )
    chart.meta["denominator"] = "sum of the excluded areas of E1 to E6"
    chart.meta["data_source"] = f"F3 cells_<tech>__{SCENARIO}"
    return chart


def layer_map(
    ctx: MapContext,
    iso: str,
    tech: str,
    code: str,
    cells: pd.DataFrame,
    *,
    preset: str = "thesis",
    country: str | None = None,
) -> ms.MapFigure:
    """A diagnostic map: the share of the land of each cell excluded by one exclusion (the colour scale is 0 to 1 in every country)."""
    lattice = lattice_of(cells["cell_id"].to_numpy())
    share = to_grid(
        cells["cell_id"].to_numpy(),
        (cells[f"excluded_area_km2_{code}"] / cells["cell_area_km2"]).to_numpy(dtype="float64"),
        lattice,
    )
    canvas = ms.raster_map(
        share,
        lattice.extent,
        ctx.polygon,
        iso=iso,
        technology=technology_name(tech),
        variable=f"{EXCLUSION_TITLES[code]}, excluded share",
        label="Excluded share of the land area of the cell",
        kind="excluded_share",
        subtitle=ms.format_subtitle("Diagnostic", "central land scenario"),
        resolution=ms.resolution_note(cell_deg=0.05),
        neighbours=ctx.neighbours,
        extent=ctx.extent,
        contiguous=False,
        country=country,
        preset=preset,
    )
    canvas.meta["status"] = "diagnostic"
    return canvas


def sheet_name(iso: str, tech: str) -> str:
    return ms.figure_filename(iso, FIGURE_PHASE, "land-eligibility", tech, SCENARIO)


def chart_name(iso: str) -> str:
    return ms.figure_filename(iso, FIGURE_PHASE, "exclusion-contribution", None, SCENARIO)


def layer_name(iso: str, tech: str, code: str) -> str:
    return ms.figure_filename(
        iso, FIGURE_PHASE, ["excluded-share", EXCLUSION_SLUGS[code]], tech, SCENARIO
    )


def read_cell_tables(eligibility_dir: Path) -> dict[str, pd.DataFrame]:
    """The F3 cell tables of the central scenario by technology (the 0.1 degree aggregation of V-07 is not one of them)."""
    tables = {}
    for path in sorted(Path(eligibility_dir).glob("cells_*__central.parquet")):
        if path.name.startswith("cells_0p1deg"):
            continue
        tables[path.stem.removeprefix("cells_").removesuffix("__central")] = pd.read_parquet(path)
    return tables


def draw_country(
    iso: str,
    cell_tables: dict[str, pd.DataFrame],
    ctx: MapContext,
    out_dir: Path,
    eligibility_dir: Path | None = None,
    *,
    display_smoothing: str = "auto",
    with_layers: bool = True,
    country: str | None = None,
    preset: str = "thesis",
) -> list[Path]:
    """The F3 figures of a country: one sheet per technology and the exclusion chart in `out_dir`, and with `with_layers` one diagnostic map of each
    exclusion and technology in `out_dir/layers`. The fine layer of the eligible fraction is used when F3 wrote it and it agrees with the cells."""
    out_dir = Path(out_dir)
    written: list[Path] = []
    kw = {"display_smoothing": display_smoothing, "preset": preset, "country": country}
    for tech in sorted(cell_tables):
        cells = cell_tables[tech]
        fraction = None
        if eligibility_dir is not None:
            fraction = read_fraction_layer(Path(eligibility_dir) / f"eligible_fraction_{tech}.tif")
        if fraction is not None:
            check = check_fraction_layer(fraction, cells)
            if not check.ok:
                logger.warning(
                    "%s %s: the fine eligible fraction differs from the cells by %.3g (limit %.3g): the cells are drawn",
                    iso,
                    tech,
                    check.max_rel_diff,
                    check.tolerance,
                )
                fraction = None
        sheet = eligibility_sheet(ctx, iso, tech, cells, fraction=fraction, **kw)
        written.append(ms.save_png(sheet, out_dir / sheet_name(iso, tech)))
    written.append(
        ms.save_png(
            exclusion_chart(iso, cell_tables, preset=preset, country=country),
            out_dir / chart_name(iso),
        )
    )
    ms.write_figures_index(out_dir)
    if with_layers:
        layers = out_dir / "layers"
        for tech in sorted(cell_tables):
            for code in EXCLUSION_NAMES:
                canvas = layer_map(
                    ctx, iso, tech, code, cell_tables[tech], preset=preset, country=country
                )
                written.append(ms.save_png(canvas, layers / layer_name(iso, tech, code)))
        ms.write_figures_index(layers)
    return written


def exclusion_codes(columns: Sequence[str]) -> list[str]:
    """The exclusions that a cell table has areas for (all six, or an error naming the missing column)."""
    missing = [
        f"excluded_area_km2_{c}" for c in EXCLUSION_NAMES if f"excluded_area_km2_{c}" not in columns
    ]
    if missing:
        raise ValueError(f"the cell table has no column {missing[0]}")
    return list(EXCLUSION_NAMES)
