"""The charts that go with the maps: header, bars and legend in the grid of the map figures (`viz/charts.py`)."""

from __future__ import annotations

import pytest

from geofrea.viz import mapstyle as ms
from geofrea.viz.charts import new_chart, ranked_bars, stacked_bars, step_curve


@pytest.mark.unit
def test_stacked_bars_have_the_title_a_legend_entry_per_series_and_save_with_metadata(tmp_path):
    chart = new_chart(iso="BRA", variable="Exclusions", n_bars=2, legend_labels=["A", "B"])
    stacked_bars(
        chart,
        ["One", "Two"],
        {"A": [60.0, 30.0], "B": [40.0, 70.0]},
        {"A": "#0072B2", "B": "#E69F00"},
    )
    assert chart.texts["title"].get_text().startswith("Brazil")
    assert len(chart.artists["legend"]) == 4
    path = ms.save_png(chart, tmp_path / "chart.png")
    assert path.is_file() and path.stat().st_size > 0


@pytest.mark.unit
def test_ranked_bars_and_a_step_curve_draw_on_the_axes(tmp_path):
    chart = new_chart(iso="PRT", variable="Ranking", n_bars=3)
    ranked_bars(
        chart,
        ["a", "b", "c"],
        [3.0, 2.0, 1.0],
        low=[2.0, 1.0, 0.5],
        high=[4.0, 3.0, 2.0],
        unit="GW",
        colour="#CC79A7",
        meaning="potential",
    )
    assert len(chart.ax.patches) == 3
    curve = new_chart(iso="PRT", variable="Supply curve", plot_height_mm=60.0)
    step_curve(
        curve, [1, 2, 3], [10.0, 12.0, 15.0], xlabel="GW", ylabel="EUR", colour="#000000", meaning="cost"
    )
    assert len(curve.artists["curve"]) == 1
    assert ms.save_png(curve, tmp_path / "curve.png").is_file()
