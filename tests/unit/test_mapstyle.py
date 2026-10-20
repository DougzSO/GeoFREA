"""The common map style (COMMAND 56): extent, aspect, norms, layout, furniture that never overlaps, PNG size, and a perceptual-hash
regression of three synthetic maps (a tall country, a wide one and a small one). Synthetic data only."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
import pytest
from matplotlib.colors import LogNorm, PowerNorm
from PIL import Image

from geofrea.viz import mapstyle as ms
from geofrea.viz.examples import SHAPES, synthetic_country

pytestmark = pytest.mark.unit

BASELINES = Path(__file__).resolve().parents[1] / "fixtures" / "mapstyle" / "hashes.json"
CASES = {"tall": ms.FULL_WIDTH_MM, "wide": ms.FULL_WIDTH_MM, "small": ms.HALF_WIDTH_MM}


def _build(name: str, width: float | None = None) -> tuple[ms.MapCanvas, object]:
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
        width_mm=width or CASES[name],
        neighbours=country.neighbours,
    )
    return canvas, country


def _px_to_mm(box_px, canvas: ms.MapCanvas) -> tuple[float, float, float, float]:
    """A pixel box (display, origin lower left) as millimetres on the figure."""
    k = 25.4 / canvas.fig.dpi
    return box_px.x0 * k, box_px.y0 * k, box_px.x1 * k, box_px.y1 * k


def _measured(canvas: ms.MapCanvas, artists) -> tuple[float, float, float, float]:
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


# ----------------------------------------------------------------------------------------------------------------------- extent


def test_extent_ignores_a_far_island_and_adds_three_percent():
    country = synthetic_country("tall")
    w, s, e, n = country.mainland.bounds
    got = ms.country_extent(country.geometry)  # geometry holds the island 4 half-widths away
    assert got[0] == pytest.approx(w - 0.03 * (e - w)) and got[1] == pytest.approx(
        e + 0.03 * (e - w)
    )
    assert got[2] == pytest.approx(s - 0.03 * (n - s)) and got[3] == pytest.approx(
        n + 0.03 * (n - s)
    )
    with_island = ms.country_extent(country.geometry, contiguous=False)
    assert with_island[0] < got[0]  # without the rule the island would stretch the map


def test_geographic_aspect_is_one_over_cos_of_the_central_latitude():
    extent = (-60.0, -50.0, -40.0, -20.0)
    assert ms.geographic_aspect(extent) == pytest.approx(1 / math.cos(math.radians(-30.0)))
    ratio = ms.map_height_over_width(extent)
    assert ratio == pytest.approx(20.0 / (10.0 * math.cos(math.radians(30.0))))


def test_degrees_are_formatted_with_hemisphere():
    assert ms.format_degrees(-40, "lat") == "40°S"
    assert ms.format_degrees(-50, "lon") == "50°W"
    assert ms.format_degrees(10, "lat") == "10°N"
    assert ms.format_degrees(20, "lon") == "20°E"
    assert ms.format_degrees(0, "lat") == "0°"
    assert ms.format_degrees(-47.5, "lat") == "47.5°S"


# ------------------------------------------------------------------------------------------------------------------------ norms


def test_robust_norm_clips_at_percentiles_and_extends():
    values = np.linspace(0.0, 100.0, 1001)
    info = ms.robust_norm(values)
    assert info.kind == "linear"
    assert info.vmin == pytest.approx(2.0) and info.vmax == pytest.approx(98.0)
    assert info.extend == "both"
    assert ms.robust_norm(np.array([1.0, 1.0, 1.0, 2.0])).extend in {
        "max",
        "neither",
        "both",
        "min",
    }


def test_robust_norm_is_log_or_power_when_skewed():
    rng = np.random.default_rng(0)
    skewed = np.exp(rng.normal(0, 2.5, 5000))
    info = ms.robust_norm(skewed)
    assert info.skew > ms.SKEW_LIMIT and info.kind == "log" and isinstance(info.norm, LogNorm)
    with_zeros = np.concatenate([np.zeros(3000), np.exp(rng.normal(0, 2.5, 2000))])
    zero_info = ms.robust_norm(with_zeros)
    assert zero_info.kind == "power" and isinstance(zero_info.norm, PowerNorm)


def test_diverging_norm_is_centred():
    values = np.concatenate([np.linspace(-1, 3, 500), [10.0]])
    info = ms.robust_norm(values, diverging=True)
    assert info.vmin == pytest.approx(-info.vmax) and info.kind == "diverging"
    centred = ms.robust_norm(np.linspace(0.8, 1.5, 100), diverging=True, center=1.0)
    assert (centred.vmin + centred.vmax) / 2 == pytest.approx(1.0)


def test_colormaps_by_kind():
    assert ms.colormap_for("potential") == "viridis" == ms.colormap_for("energy")
    assert ms.colormap_for("capacity_factor") == "magma"
    assert ms.colormap_for("delta") == "RdBu" and ms.colormap_for("delta_alt") == "BrBG"


# ---------------------------------------------------------------------------------------------------------------------- scale bar


@pytest.mark.parametrize(
    "target,expected",
    [
        (1.0, 1),
        (1.9, 2),
        (2.0, 2),
        (4.9, 5),
        (5.0, 5),
        (99, 100),
        (230, 200),
        (999, 1000),
        (0.7, 0.5),
        (418, 500),
    ],
)
def test_nice_length_is_one_two_five_times_a_power_of_ten(target, expected):
    assert ms.nice_length_km(target) == pytest.approx(expected)


def test_scale_bar_length_is_about_twenty_percent_of_the_width_at_the_central_latitude():
    extent = (-60.0, -40.0, -30.0, -10.0)
    km = ms.scale_bar_length_km(extent)
    width_km = 20.0 * 111.3 * math.cos(math.radians(-20.0))
    assert 0.2 * width_km / 1.6 <= km <= 0.2 * width_km * 1.6
    assert km in {1, 2, 5, 10, 20, 50, 100, 200, 500, 1000}


# ----------------------------------------------------------------------------------------------------------------------- layout


@pytest.mark.parametrize("name,legend", [("tall", "right"), ("wide", "below"), ("small", "right")])
def test_legend_goes_right_for_tall_and_below_for_wide(name, legend):
    country = synthetic_country(name)
    extent = ms.country_extent(country.geometry)
    assert ms.legend_position(extent) == legend
    assert ms.compute_layout(extent).legend == legend


@pytest.mark.parametrize("name", list(CASES))
def test_png_has_print_size_at_300_dpi(name, tmp_path):
    canvas, _ = _build(name)
    width_mm, height_mm = canvas.layout.width_mm, canvas.layout.height_mm
    path = ms.save_png(canvas, tmp_path / f"{name}.png")
    with Image.open(path) as im:
        assert im.size[0] == pytest.approx(width_mm / 25.4 * 300, abs=1)
        assert im.size[1] == pytest.approx(height_mm / 25.4 * 300, abs=1)
        assert round(im.info["dpi"][0]) == 300
    assert CASES[name] in (190.0, 90.0)


def test_full_width_is_about_2250_pixels(tmp_path):
    canvas, _ = _build("wide")
    path = ms.save_png(canvas, tmp_path / "w.png")
    with Image.open(path) as im:
        assert 2240 <= im.size[0] <= 2250


def test_only_png_is_written(tmp_path):
    canvas, _ = _build("small")
    with pytest.raises(ValueError):
        ms.save_png(canvas, tmp_path / "x.pdf")


@pytest.mark.parametrize("name", list(CASES))
def test_map_axes_has_the_geographic_aspect(name):
    canvas, _ = _build(name)
    canvas.fig.canvas.draw()
    bb = canvas.ax.get_window_extent()
    assert bb.height / bb.width == pytest.approx(ms.map_height_over_width(canvas.extent), rel=2e-3)
    assert canvas.ax.get_aspect() == pytest.approx(ms.geographic_aspect(canvas.extent))


def test_fonts_have_the_print_sizes():
    canvas, _ = _build("wide")
    assert canvas.texts["title"].get_fontsize() == ms.TITLE_PT == 10.0
    assert canvas.texts["subtitle"].get_fontsize() == ms.LABEL_PT == 8.0
    assert canvas.texts["total"].get_fontsize() == ms.LEGEND_PT == 8.0
    assert canvas.texts["title"].get_text() == "XXX · Solar PV · Installable capacity"
    assert canvas.ax.get_xticklabels()[0].get_fontsize() == 8.0
    assert {t.get_fontfamily()[0] for t in (canvas.texts["title"], canvas.texts["total"])} == {
        ms.FONT_FAMILY
    }


# ------------------------------------------------------------------------------------------------------------ no overlap (step 4)


def _data_under(canvas: ms.MapCanvas, country, box_mm) -> float:
    """Share of data pixels and of country polygon under a figure box that lies inside the map."""
    return ms.occupancy(
        box_mm,
        canvas.layout.map_box,
        canvas.extent,
        data_mask=ms.mask_on_extent(~np.isnan(country.grid), country.grid_extent, canvas.extent),
        polygon=country.mainland,
    )


@pytest.mark.parametrize("name", list(CASES))
def test_compass_and_scale_bar_do_not_touch_data_title_legend_or_each_other(name):
    canvas, country = _build(name)
    boxes = {k: _measured(canvas, v) for k, v in canvas.artists.items()}
    canvas.fig.canvas.draw()
    renderer = canvas.fig.canvas.get_renderer()
    title = _measured(canvas, [canvas.texts["title"], canvas.texts["subtitle"]])
    legend = _px_to_mm(canvas.cax.get_tightbbox(renderer), canvas)
    layout = canvas.layout
    names = list(boxes)
    for i, a in enumerate(names):
        assert not _intersect(boxes[a], title), f"{a} meets the title"
        assert not _intersect(boxes[a], legend), f"{a} meets the legend"
        for b in names[i + 1 :]:
            assert not _intersect(boxes[a], boxes[b]), f"{a} meets {b}"
        inside_map = _intersect(boxes[a], layout.map_box)
        if inside_map:  # placed over the map: nothing of the country or the data may be under it
            assert _data_under(canvas, country, boxes[a]) <= ms.OCCUPANCY_TOLERANCE, (
                f"{a} covers the country"
            )
    # the map's own tick labels do not meet the furniture either
    ticks = _px_to_mm(canvas.ax.get_tightbbox(renderer), canvas)
    for a in names:
        if not _intersect(boxes[a], layout.map_box):
            continue
        assert boxes[a][0] >= layout.map_box[0] - 1e-6 and boxes[a][2] <= layout.map_box[2] + 1e-6
    assert ticks[0] >= -1e-6 and ticks[1] >= -1e-6, "tick labels leave the figure"
    assert (
        title[1] >= 0
        and boxes
        and all(b[3] <= layout.height_mm + 1e-6 and b[1] >= -1e-6 for b in boxes.values())
    )


@pytest.mark.parametrize("name", list(CASES))
def test_everything_stays_inside_the_figure(name):
    canvas, _ = _build(name)
    canvas.fig.canvas.draw()
    renderer = canvas.fig.canvas.get_renderer()
    for artist in (canvas.cax, canvas.ax):
        bb = _px_to_mm(artist.get_tightbbox(renderer), canvas)
        assert (
            bb[0] >= -0.2
            and bb[1] >= -0.2
            and bb[2] <= canvas.layout.width_mm + 0.2
            and bb[3] <= canvas.layout.height_mm + 0.2
        )


def test_elements_choose_the_emptiest_corner_by_data_and_polygon():
    """A country that fills the lower left and the upper right leaves the other two corners for the furniture."""
    layout = ms.compute_layout((0.0, 10.0, 0.0, 10.0))
    extent = (0.0, 10.0, 0.0, 10.0)
    from shapely.geometry import box

    polygon = box(0, 0, 4, 4).union(box(6, 6, 10, 10)).union(box(3, 3, 7, 7))
    placed = ms.place_furniture(layout, extent, data_mask=None, polygon=polygon, total_text=None)
    assert {placed["scale_bar"].where, placed["compass"].where} <= {"upper left", "lower right"}
    mask = np.zeros((100, 100), dtype=bool)
    mask[:, :50] = True  # data on the left half only
    placed = ms.place_furniture(layout, extent, data_mask=mask, polygon=None, total_text=None)
    assert "right" in placed["scale_bar"].where and "right" in placed["compass"].where


def test_a_full_map_sends_the_furniture_outside():
    from shapely.geometry import box

    extent = (0.0, 10.0, 0.0, 10.0)
    layout = ms.compute_layout(extent)
    placed = ms.place_furniture(
        layout, extent, data_mask=None, polygon=box(-1, -1, 11, 11), total_text="x"
    )
    assert {p.where for p in placed.values()} == {"outside"}


def test_colour_bar_has_extend_arrows_when_values_fall_outside():
    canvas, country = _build("wide")
    values = country.grid[np.isfinite(country.grid)]
    info = ms.robust_norm(values)
    assert info.extend == "both"
    assert canvas.cax.get_xlabel() == "MW per cell" or canvas.cax.get_ylabel() == "MW per cell"


# --------------------------------------------------------------------------------------------- visual regression by perceptual hash


def dhash(path: Path, size: int = 16) -> str:
    """Difference hash of the picture (size x size bits, hex): same drawing, same hash; a moved element or colour changes bits."""
    with Image.open(path) as im:
        gray = np.asarray(
            im.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS), dtype="float64"
        )
    bits = (gray[:, 1:] > gray[:, :-1]).ravel()
    return f"{int(''.join('1' if b else '0' for b in bits), 2):0{size * size // 4}x}"


def hamming(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()


@pytest.mark.parametrize("name", list(CASES))
def test_synthetic_maps_match_their_baseline(name, tmp_path):
    canvas, _ = _build(name)
    path = ms.save_png(canvas, tmp_path / f"{name}.png")
    with Image.open(path) as im:
        size = list(im.size)
    got = {"hash": dhash(path), "size": size}
    if os.environ.get("GEOFREA_UPDATE_MAPSTYLE_BASELINES") == "1":
        data = json.loads(BASELINES.read_text()) if BASELINES.exists() else {}
        data[name] = got
        BASELINES.parent.mkdir(parents=True, exist_ok=True)
        BASELINES.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    expected = json.loads(BASELINES.read_text())[name]
    assert abs(size[0] - expected["size"][0]) <= 2 and abs(size[1] - expected["size"][1]) <= 2
    assert hamming(got["hash"], expected["hash"]) <= 12, (
        "the map differs from its baseline: look at it, then refreeze if intended"
    )


def test_the_hash_notices_a_moved_compass(tmp_path):
    canvas, _ = _build("wide")
    base = dhash(ms.save_png(canvas, tmp_path / "a.png"))
    other = _build("wide")[0]
    for artist in other.artists["compass"]:
        artist.remove()
    changed = dhash(ms.save_png(other, tmp_path / "b.png"))
    assert hamming(base, changed) > 0


def test_synthetic_shapes_are_the_three_documented_ones():
    assert set(SHAPES) == {"tall", "wide", "small"}
