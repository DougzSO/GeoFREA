"""Draw the synthetic examples of `docs/figures/style_guide.md` with `geofrea.viz.mapstyle` (tall, wide and small country; solar and wind
families; a classed map).

usage: python scripts/make_style_guide_examples.py
Writes `docs/figures/examples/XXX_example_*.png` (invented country "Examplia", marked EXAMPLE, no result) and `figures_index.json`.
Nothing under GEOFREA_DATA_DIR is read or written.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from matplotlib.colors import to_rgba

from geofrea.viz import mapstyle as ms
from geofrea.viz.examples import synthetic_country

OUT = Path(__file__).resolve().parents[1] / "docs" / "figures" / "examples"
MARK = "EXAMPLE – synthetic data"
# file name: (shape, preset, technology key, kind, variable, label)
RASTERS = {
    ms.figure_filename("XXX", "example", "capacity-density", "solar", "central", "ref"): (
        "tall",
        "thesis",
        "solar",
        "density",
        "Capacity density",
        "MW/km²",
    ),
    ms.figure_filename("XXX", "example", "capacity-density", "wind", "central", "ref"): (
        "wide",
        "thesis",
        "wind",
        "density",
        "Capacity density",
        "MW/km²",
    ),
    ms.figure_filename("XXX", "example", "capacity-factor", "solar", "central", "ref"): (
        "small",
        "article_single",
        "solar",
        "capacity_factor",
        "Capacity factor",
        "Capacity factor",
    ),
}
CLASSES_FILE = ms.figure_filename("XXX", "example", "dominant-exclusion", "solar", "central")
TECHNOLOGY = {"solar": "Solar PV", "wind": "Onshore wind"}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (shape, preset, tech, kind, variable, label) in RASTERS.items():
        country = synthetic_country(shape)
        grid = country.grid
        if (
            kind == "capacity_factor"
        ):  # a skewed field is a density; rescale it to a plausible capacity factor
            finite = np.isfinite(grid)
            grid = np.where(finite, 0.08 + 0.2 * grid / np.nanmax(grid), np.nan)
        canvas = ms.raster_map(
            grid,
            country.grid_extent,
            country.geometry,
            iso="XXX",
            country="Examplia",
            technology=TECHNOLOGY[tech],
            variable=variable,
            label=label,
            kind=kind,
            tech=tech,
            scenario="Central",
            climate="Reference climate",
            total_text=MARK,
            preset=preset,
            neighbours=country.neighbours,
        )
        print(name, ms.save_png(canvas, OUT / name, {"grid": "synthetic", "data_source": MARK}))

    country = synthetic_country("tall")
    spec = ms.qualitative_legend(
        "Dominant exclusion",
        ["E1 protected", "E2 water", "E3 riparian", "E4 slope", "E5 land cover"],
        none_label="None",
    )
    side, below = ms.legend_space(spec)
    canvas = ms.new_map(
        country.geometry,
        iso="XXX",
        country="Examplia",
        technology="Solar PV",
        variable="Dominant exclusion",
        subtitle=ms.format_subtitle("Central", MARK),
        neighbours=country.neighbours,
        legend_side_mm=side,
        legend_below_mm=below,
    )
    rng = np.random.default_rng(66)
    classes = np.where(np.isfinite(country.grid), rng.integers(0, 6, country.grid.shape), -1)
    colours = np.array(
        [[1.0, 1.0, 1.0, 0.0]]
        + [list(to_rgba(c)) for c in ms.class_colours(5)]
        + [list(to_rgba(ms.CLASS_NONE_COLOUR))]
    )
    image = colours[np.where(classes < 0, 0, classes + 1)]
    canvas.ax.imshow(
        image,
        extent=country.grid_extent,
        origin="upper",
        interpolation="nearest",
        zorder=2,
        aspect=ms.geographic_aspect(canvas.extent),
    )
    canvas.ax.set_xlim(canvas.extent[0], canvas.extent[1])
    canvas.ax.set_ylim(canvas.extent[2], canvas.extent[3])
    ms.draw_classed_legend(canvas, spec)
    print(
        CLASSES_FILE,
        ms.save_png(canvas, OUT / CLASSES_FILE, {"grid": "synthetic", "data_source": MARK}),
    )
    print(ms.write_figures_index(OUT))


if __name__ == "__main__":
    main()
