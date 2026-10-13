"""The fixed style of the thesis figures (M-F8-02; D-F8-002).

It extends `overview/style.py` (the map style: relief backdrop, outline, rivers, scale bar), so a diagnostic can graduate to a thesis
figure by changing the layer only. This module adds what a plot needs: fonts, sizes, one colour for each SSP, one colour for the reference
member and for each technology (by position in the run's technology list: no technology name here, A-04), and a deterministic save.
No figure sets its own look.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from geofrea.overview.style import (  # noqa: F401  (the map style, re-exported)
    draw_backdrop,
    draw_overlay,
    hillshade,
)

PAGE_WIDTH_IN = 6.3
FONT_SIZE = 8.0
TITLE_SIZE = 9.0
DPI = 200
SSP_COLORS = {"SSP1-2.6": "#1b7837", "SSP3-7.0": "#e08214", "SSP5-8.5": "#b2182b"}
SSP_FALLBACK = "#6a51a3"
REFERENCE_COLOR = "#222222"
AXIS_COLORS = {
    "climate": "#1f78b4",
    "techno_economic": "#e6550d",
}  # H4: one colour per uncertainty axis
TECHNOLOGY_COLORS = ("#d95f02", "#1f78b4", "#33a02c", "#6a3d9a", "#b15928")

_RC = {
    "font.family": "DejaVu Sans",
    "font.size": FONT_SIZE,
    "axes.titlesize": TITLE_SIZE,
    "axes.labelsize": FONT_SIZE,
    "legend.fontsize": FONT_SIZE - 1,
    "xtick.labelsize": FONT_SIZE - 1,
    "ytick.labelsize": FONT_SIZE - 1,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.5,
    "figure.dpi": DPI,
    "savefig.dpi": DPI,
    "pdf.fonttype": 42,
}


def ssp_color(ssp: str) -> str:
    return SSP_COLORS.get(ssp, SSP_FALLBACK)


def technology_color(technologies: Sequence[str], technology: str) -> str:
    """The colour of a technology: its position in the run's list, so the same list always gives the same colours."""
    return TECHNOLOGY_COLORS[list(technologies).index(technology) % len(TECHNOLOGY_COLORS)]


@contextmanager
def thesis_style() -> Iterator[None]:
    """Draw inside this block to get the thesis look."""
    with matplotlib.rc_context(_RC):
        yield


def new_figure(
    width_fraction: float = 1.0, aspect: float = 0.62, **kwargs
) -> tuple[Figure, object]:
    """A figure `width_fraction` of the page wide, `aspect` high over wide, with one axes."""
    width = PAGE_WIDTH_IN * width_fraction
    fig, ax = plt.subplots(figsize=(width, width * aspect), layout="constrained", **kwargs)
    return fig, ax


def save_figure(fig: Figure, stem_path: Path) -> list[Path]:
    """`<stem>.png` and `<stem>.pdf` with no creation date or software tag, so the same figure gives the same bytes."""
    png, pdf = stem_path.with_suffix(".png"), stem_path.with_suffix(".pdf")
    fig.savefig(png, metadata={"Software": None})
    fig.savefig(pdf, metadata={"CreationDate": None, "Creator": None, "Producer": None})
    plt.close(fig)
    return [png, pdf]
