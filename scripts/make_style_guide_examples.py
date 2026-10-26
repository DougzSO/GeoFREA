"""Draw the examples of `docs/figures/style_guide.md` with `geofrea.viz.mapstyle`: real (simplified) geometries of six countries with
synthetic data, marked "EXAMPLE, synthetic data" in the subtitle and in the box of totals, one kind of figure each.

usage: python scripts/make_style_guide_examples.py
Writes `docs/figures/examples/<ISO3>_example_*.png` and `figures_index.json`. The geometry is `tests/fixtures/archetypes`; the data are
invented (`geofrea.viz.examples.archetype_country`); nothing under GEOFREA_DATA_DIR is read or written, and no result is drawn.
"""

from __future__ import annotations

from pathlib import Path

from geofrea.viz import mapstyle as ms
from geofrea.viz.examples import archetype_country, archetype_figure

OUT = Path(__file__).resolve().parents[1] / "docs" / "figures" / "examples"
# the pieces of the file name of each kind of figure: variable, technology, scenario, climate
NAMES = {
    "density": ("capacity-density", "solar", "central", "ref"),
    "capacity_factor": ("capacity-factor", "wind", "central", "ref"),
    "forcing": ("forcing", "solar", "SSP3-7.0", "2071-2100"),
    "eligibility": ("dominant-exclusion", "solar", "central", None),
    "state": ("capacity-density-state", "wind", "central", None),
}
# ISO3: (kind of figure, preset)
EXAMPLES = {
    "PRT": ("density", "thesis"),
    "BRA": ("capacity_factor", "thesis"),
    "CHE": ("forcing", "article_single"),
    "CHL": ("eligibility", "thesis"),
    "IDN": ("state", "thesis"),
    "LUX": ("density", "article_single"),
}


def example_name(iso: str, kind: str) -> str:
    variable, tech, scenario, climate = NAMES[kind]
    return ms.figure_filename(iso, "example", variable, tech, scenario, climate)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for iso, (kind, preset) in EXAMPLES.items():
        canvas = archetype_figure(archetype_country(iso), kind, preset)
        path = ms.save_png(
            canvas,
            OUT / example_name(iso, kind),
            {"grid": "0.05 degree analysis grid", "data_source": "EXAMPLE, synthetic data"},
        )
        print(path.name)
    print(ms.write_figures_index(OUT))


if __name__ == "__main__":
    main()
