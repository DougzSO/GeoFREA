"""Draw the synthetic examples of `docs/figures/style_guide.md` with `geofrea.viz.mapstyle` (tall, wide and small country).

usage: python scripts/make_style_guide_examples.py
Writes `docs/figures/examples/example_<shape>.png` (invented countries, no result).
"""

from __future__ import annotations

from pathlib import Path

from geofrea.viz import mapstyle as ms
from geofrea.viz.examples import synthetic_country

OUT = Path(__file__).resolve().parents[1] / "docs" / "figures" / "examples"
CASES = {"tall": ms.FULL_WIDTH_MM, "wide": ms.FULL_WIDTH_MM, "small": ms.HALF_WIDTH_MM}


def main() -> None:
    for name, width in CASES.items():
        country = synthetic_country(name)
        canvas = ms.raster_map(
            country.grid,
            country.grid_extent,
            country.geometry,
            iso="XXX",
            technology="Solar PV",
            variable="Installable capacity",
            label="MW per cell",
            subtitle="Central scenario · reference climate",
            total_text="National total\n1,234.5 GW",
            width_mm=width,
            neighbours=country.neighbours,
        )
        print(name, ms.save_png(canvas, OUT / f"example_{name}.png"))


if __name__ == "__main__":
    main()
