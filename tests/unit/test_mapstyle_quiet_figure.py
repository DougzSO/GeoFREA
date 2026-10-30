"""COMMAND 77, item 5: the idle redraw that geopandas triggers after each layer is not run, and the saved pixels do not change."""

from __future__ import annotations

import io

import geopandas as gpd
import numpy as np
import pytest
from PIL import Image
from shapely.geometry import Polygon

from geofrea.viz import mapstyle as ms

pytestmark = pytest.mark.unit


def _layers():
    squares = [Polygon([(x, 0), (x + 1, 0), (x + 1, 1), (x, 1)]) for x in range(0, 6, 2)]
    return gpd.GeoSeries(squares), gpd.GeoSeries([squares[0].boundary.buffer(0.02)])


def _render(quiet: bool):
    fig = ms.plt.figure(figsize=(3, 2), dpi=100, facecolor="white")
    if quiet:
        ms.quiet_figure(fig)
    draws = {"n": 0}
    real_draw = fig.canvas.draw

    def counting(*a, **k):
        draws["n"] += 1
        return real_draw(*a, **k)

    fig.canvas.draw = counting
    ax = fig.add_axes((0.1, 0.1, 0.8, 0.8))
    for series in _layers():
        series.plot(ax=ax, color="#336699", edgecolor="white", linewidth=0.3)
    ax.set_xlim(-0.5, 6)
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=100, facecolor="white")
    ms.plt.close(fig)
    return np.asarray(Image.open(io.BytesIO(buffer.getvalue())).convert("RGBA")), draws["n"]


def test_a_quiet_figure_is_drawn_only_when_it_is_saved_and_the_pixels_are_the_same():
    loud, loud_draws = _render(False)
    quiet, quiet_draws = _render(True)
    assert loud_draws > quiet_draws  # each plot() drew the whole figure
    assert quiet_draws <= 1  # only the save (savefig draws through its own canvas, so it may not count here)
    assert loud.shape == quiet.shape
    np.testing.assert_array_equal(loud, quiet)
