"""Classed maps and proportional circles of the common style (COMMAND 60): the circle scale, the legend, no overlap of any element of the map,
the extent without the far island, and a perceptual-hash regression of the state map on three synthetic countries. Synthetic data only."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from PIL import Image
from shapely.geometry import box

from geofrea.technical_potential.absolute_maps import (
    class_breaks,
    compose_state_map,
    map_context,
    technology_name,
)
from geofrea.viz import mapstyle as ms
from geofrea.viz.examples import SHAPES, synthetic_country

pytestmark = pytest.mark.unit

BASELINES = Path(__file__).resolve().parents[1] / "fixtures" / "mapstyle" / "hashes.json"
CASES = {
    "tall": ms.FULL_WIDTH_MM,
    "wide": ms.FULL_WIDTH_MM,
    "small": ms.FULL_WIDTH_MM,
}  # state maps are full-page maps (title and circles need the width)


# ------------------------------------------------------------------------------------------------------------------------- the pieces


def test_the_area_of_a_circle_is_proportional_to_its_value():
    r = [ms.circle_radius_mm(v, 100.0, 9.0) for v in (100.0, 25.0, 4.0)]
    assert r[0] == pytest.approx(9.0)
    assert r[1] == pytest.approx(4.5) and r[2] == pytest.approx(
        1.8
    )  # a quarter of the value is half the radius
    assert (r[1] / r[0]) ** 2 == pytest.approx(0.25)


def test_a_zero_value_has_no_circle_and_a_tiny_one_is_still_visible():
    assert ms.circle_radius_mm(0.0, 100.0, 9.0) == 0.0
    assert ms.circle_radius_mm(-1.0, 100.0, 9.0) == 0.0
    assert ms.circle_radius_mm(1e-9, 100.0, 9.0) == ms.CIRCLE_MIN_MM


@pytest.mark.parametrize(
    "maximum,expected",
    [
        (37.0, [20.0, 2.0, 0.2]),
        (1234.0, [1000.0, 100.0, 10.0]),
        (0.8, [0.5, 0.05, 0.005]),
        (5.0, [5.0, 0.5, 0.05]),
    ],
)
def test_the_legend_values_are_round_and_never_above_the_largest_total(maximum, expected):
    values = ms.nice_values_below(maximum)
    assert values == pytest.approx(expected)
    assert values[0] <= maximum


def test_the_legend_asks_for_more_room_when_its_labels_and_circles_are_larger():
    base = ms.ClassedLegend("MW per km²", ("0 - 1", "1 - 2"), ("#000", "#fff"))
    wide = ms.ClassedLegend("MW per km²", ("0 - 1", "1,000 - 12,000,000"), ("#000", "#fff"))
    with_circles = ms.ClassedLegend(
        "MW per km²",
        ("0 - 1", "1 - 2"),
        ("#000", "#fff"),
        circle_title="GW",
        circles=(("20", 9.0), ("2", 2.8)),
    )
    assert ms.legend_space(wide)[0] > ms.legend_space(base)[0]
    assert ms.legend_space(with_circles)[1] > ms.legend_space(base)[1]


# ------------------------------------------------------------------------------------------------------------- a state map on a synthetic country


def _units(country) -> gpd.GeoDataFrame:
    """The mainland cut in a 2 x 3 tiling of states, the far island added to the first one."""
    w, s, e, n = country.mainland.bounds
    cuts_x, cuts_y = np.linspace(w, e, 4), np.linspace(s, n, 3)
    geoms, ids = [], []
    for j in range(2):
        for i in range(3):
            part = country.mainland.intersection(
                box(cuts_x[i], cuts_y[j], cuts_x[i + 1], cuts_y[j + 1])
            )
            if not part.is_empty:
                geoms.append(part)
                ids.append(f"XXX.{len(ids) + 1}_1")
    island = country.geometry.difference(country.mainland)
    geoms[0] = geoms[0].union(island)
    return gpd.GeoDataFrame({"admin1_id": ids}, geometry=geoms, crs="EPSG:4326")


def _state_map(name: str):
    country = synthetic_country(name)
    units = _units(country)
    rng = np.random.default_rng(60)
    density = pd.Series(rng.uniform(0.05, 2.0, len(units)), index=units["admin1_id"])
    totals = pd.Series(rng.uniform(1.0, 400.0, len(units)), index=units["admin1_id"])
    breaks = class_breaks(density.to_numpy(), "fisher_jenks", 5, 2, open_last=True)
    canvas, info = compose_state_map(
        units, density, totals, breaks, map_context(country.geometry, country.neighbours),
        iso="XXX", tech="solar", variable="Energy density by state", unit="GWh per km² per year",
        circle_unit="Energy (TWh per year)", circle_reference=float(totals.max()), scenario="central",
        total_text="National total\n1,234.5 GW · 2,345.6 TWh per year", palette="viridis", width_mm=CASES[name],
    )  # fmt: skip
    return canvas, country, units, totals, info


def _px_to_mm(box_px, canvas):
    k = 25.4 / canvas.fig.dpi
    return box_px.x0 * k, box_px.y0 * k, box_px.x1 * k, box_px.y1 * k


def _measured(canvas, artists):
    canvas.fig.canvas.draw()
    renderer = canvas.fig.canvas.get_renderer()
    boxes = []
    for a in artists:
        bb = a.get_window_extent(renderer)
        if hasattr(a, "get_bbox_patch") and a.get_bbox_patch() is not None:
            bb = a.get_bbox_patch().get_window_extent(renderer)
        boxes.append(_px_to_mm(bb, canvas))
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _intersect(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _circle_boxes(canvas) -> list[tuple[float, float, float, float]]:
    """The boxes of the circles drawn on the map, in millimetres on the figure (from their centres and their sizes)."""
    canvas.fig.canvas.draw()
    collection = next(
        c for c in canvas.ax.collections if hasattr(c, "get_sizes") and len(c.get_sizes())
    )
    k = 25.4 / canvas.fig.dpi
    out = []
    for (x, y), s in zip(collection.get_offsets(), collection.get_sizes(), strict=True):
        px, py = canvas.ax.transData.transform((x, y))
        r = math.sqrt(float(s)) / 2.0 * ms.PT_MM
        out.append((px * k - r, py * k - r, px * k + r, py * k + r))
    return out


@pytest.mark.parametrize("name", list(CASES))
def test_no_element_of_a_state_map_overlaps_another(name):
    canvas, _, _, _, _ = _state_map(name)
    furniture = {k: _measured(canvas, v) for k, v in canvas.artists.items() if k != "legend"}
    legend = _measured(canvas, canvas.artists["legend"])
    title = _measured(canvas, [canvas.texts["title"], canvas.texts["subtitle"]])
    layout = canvas.layout
    assert not _intersect(legend, title), "the legend meets the title"
    assert not _intersect(legend, layout.map_box), "the legend is over the map"
    names = list(furniture)
    for i, a in enumerate(names):
        assert not _intersect(furniture[a], title), f"{a} meets the title"
        assert not _intersect(furniture[a], legend), f"{a} meets the legend"
        for b in names[i + 1 :]:
            assert not _intersect(furniture[a], furniture[b]), f"{a} meets {b}"
    for box_mm in (*furniture.values(), legend, title):  # everything is inside the figure
        assert box_mm[0] >= -0.2 and box_mm[1] >= -0.2
        assert box_mm[2] <= layout.width_mm + 0.2 and box_mm[3] <= layout.height_mm + 0.2


@pytest.mark.parametrize("name", list(CASES))
def test_no_circle_meets_the_compass_the_scale_bar_the_total_or_the_legend(name):
    canvas, _, _, _, info = _state_map(name)
    furniture = {k: _measured(canvas, v) for k, v in canvas.artists.items() if k != "legend"}
    legend = _measured(canvas, canvas.artists["legend"])
    circles = _circle_boxes(canvas)
    assert len(circles) == info["states_with_circle"] > 0
    map_box = canvas.layout.map_box
    for c in circles:
        assert not _intersect(c, legend), "a circle reaches the legend"
        for k, f in furniture.items():
            if _intersect(f, map_box):  # an element placed over the map
                assert not _intersect(c, f), f"a circle meets the {k}"
        assert (
            c[0] >= map_box[0] - 0.5 and c[2] <= map_box[2] + 0.5
        )  # the circles of a country stay on its map


@pytest.mark.parametrize("name", list(CASES))
def test_the_extent_of_a_state_map_ignores_the_far_island(name):
    canvas, country, _, _, _ = _state_map(name)
    w, s, e, n = country.mainland.bounds
    island = country.geometry.difference(country.mainland).bounds
    west, east, south, north = canvas.extent
    assert west <= w and east >= e and south <= s and north >= n
    assert not (west <= island[0] and south <= island[1]), "the extent stretches to the island"
    assert (east - west) < 1.5 * (e - w) and (north - south) < 1.5 * (n - s)


def test_the_circles_have_the_same_scale_in_two_maps_of_one_reference():
    canvas, _, _, totals, info = _state_map("tall")
    sizes = sorted(canvas.ax.collections[-1].get_sizes(), reverse=True)
    biggest = math.sqrt(sizes[0]) / 2.0 * ms.PT_MM
    assert biggest == pytest.approx(
        ms.circle_radius_mm(float(totals.max()), info["circle_reference_total"], ms.CIRCLE_MAX_MM),
        rel=1e-6,
    )
    assert info["circle_legend_values"][0] <= info["circle_reference_total"]


def test_the_legend_names_every_class_the_no_value_entry_and_the_circle_sizes():
    canvas, *_ = _state_map("tall")
    texts = {t.get_text() for t in canvas.artists["legend"] if hasattr(t, "get_text")}
    assert "GWh per km² per year" in texts or any("GWh" in t for t in texts)
    assert "no potential" in texts
    assert any(t.startswith("> ") for t in texts), "the open last class"
    assert any("TWh" in t for t in texts)


def test_technology_names_are_the_short_ones_of_the_titles():
    assert (
        technology_name("solar_tracking") == "Solar Tracking" and technology_name("wind") == "Wind"
    )


# --------------------------------------------------------------------------------------------- visual regression by perceptual hash


def dhash(path: Path, size: int = 16) -> str:
    with Image.open(path) as im:
        gray = np.asarray(
            im.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS), dtype="float64"
        )
    bits = (gray[:, 1:] > gray[:, :-1]).ravel()
    return f"{int(''.join('1' if b else '0' for b in bits), 2):0{size * size // 4}x}"


def hamming(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()


@pytest.mark.parametrize("name", list(CASES))
def test_state_maps_match_their_baseline(name, tmp_path):
    canvas, *_ = _state_map(name)
    path = ms.save_png(canvas, tmp_path / f"{name}.png")
    with Image.open(path) as im:
        size = list(im.size)
        assert round(im.info["dpi"][0]) == 300
    got = {"hash": dhash(path), "size": size}
    key = f"state_{name}"
    if os.environ.get("GEOFREA_UPDATE_MAPSTYLE_BASELINES") == "1":
        data = json.loads(BASELINES.read_text()) if BASELINES.exists() else {}
        data[key] = got
        BASELINES.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    expected = json.loads(BASELINES.read_text())[key]
    assert abs(size[0] - expected["size"][0]) <= 2 and abs(size[1] - expected["size"][1]) <= 2
    assert hamming(got["hash"], expected["hash"]) <= 12, (
        "the map differs from its baseline: look at it, then refreeze if intended"
    )


def test_the_synthetic_shapes_are_the_three_documented_ones():
    assert set(SHAPES) == {"tall", "wide", "small"}
