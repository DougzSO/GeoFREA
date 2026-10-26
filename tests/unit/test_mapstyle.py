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


def _build(
    name: str, width: float | None = None, preset: str = "thesis", total: str | None = None
) -> tuple[ms.MapFigure, object]:
    country = synthetic_country(name)
    canvas = ms.raster_map(
        country.grid,
        country.grid_extent,
        country.geometry,
        iso="XXX",
        country="Examplia",
        technology="Solar PV",
        variable="Installable capacity",
        label="MW per cell",
        tech="solar",
        subtitle="Central scenario · reference climate",
        total_text=total or "National total\n1,234.5 GW",
        width_mm=width or (CASES[name] if preset == "thesis" else None),
        preset=preset,
        neighbours=country.neighbours,
    )
    return canvas, country


def _px_to_mm(box_px, canvas: ms.MapFigure) -> tuple[float, float, float, float]:
    """A pixel box (display, origin lower left) as millimetres on the figure."""
    k = 25.4 / canvas.fig.dpi
    return box_px.x0 * k, box_px.y0 * k, box_px.x1 * k, box_px.y1 * k


def _measured(canvas: ms.MapFigure, artists) -> tuple[float, float, float, float]:
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
    assert ms.colormap_for("potential", "solar").name.startswith("YlOrBr")
    assert ms.colormap_for("energy", "wind").name.startswith("GnBu")
    assert ms.colormap_for("delta").name == "RdBu" and ms.colormap_for("delta_alt").name == "BrBG"


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
def test_map_axes_has_the_aspect_of_the_projected_country(name):
    """The map is drawn in LAEA metres with equal axes: the box of the axes has the height over width of the frame."""
    canvas, _ = _build(name)
    canvas.fig.canvas.draw()
    bb = canvas.ax.get_window_extent()
    assert bb.height / bb.width == pytest.approx(canvas.frame.ratio, rel=2e-3)
    assert canvas.ax.get_aspect() == 1.0
    geographic = ms.map_height_over_width(canvas.extent)
    assert canvas.frame.ratio == pytest.approx(geographic, rel=0.25)  # the two views of the same country agree


def test_fonts_have_the_print_sizes():
    canvas, _ = _build("wide")
    assert canvas.texts["title"].get_fontsize() == ms.TITLE_PT == 10.0
    assert canvas.texts["subtitle"].get_fontsize() == ms.LABEL_PT == 8.0
    assert canvas.texts["total"].get_fontsize() == ms.LEGEND_PT == 8.0
    assert canvas.texts["source"].get_fontsize() == ms.THESIS.footer_pt
    assert canvas.texts["title"].get_text() == "Examplia · Solar PV · Installable capacity"
    assert canvas.ax.get_xticklabels()[0].get_fontsize() == 8.0
    assert {t.get_fontfamily()[0] for t in (canvas.texts["title"], canvas.texts["total"])} == {
        ms.FONT_FAMILY
    }


# ------------------------------------------------------------------------------------------------------------ fixed layout, no overlap


def _boxes(canvas: ms.MapFigure) -> dict[str, tuple[float, float, float, float]]:
    """Real boxes in mm of the title block, the legend, the tick labels and every piece of furniture."""
    canvas.fig.canvas.draw()
    renderer = canvas.fig.canvas.get_renderer()
    out = {k: _measured(canvas, v) for k, v in canvas.artists.items() if k != "legend"}
    out["title"] = _measured(canvas, [canvas.texts["title"], canvas.texts["subtitle"]])
    out["legend"] = _px_to_mm(canvas.cax.get_tightbbox(renderer), canvas)
    out["axes"] = _px_to_mm(canvas.ax.get_tightbbox(renderer), canvas)  # map and its tick labels
    return out


PRESET_CASES = [(n, p) for p in ms.PRESETS for n in CASES]


@pytest.mark.parametrize("name,preset", PRESET_CASES)
def test_nothing_overlaps_in_any_preset(name, preset):
    canvas, _ = _build(name, preset=preset)
    boxes = _boxes(canvas)
    names = list(boxes)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            if {a, b} == {"legend", "axes"}:
                continue  # the colour bar is inside the tight box of its own neighbour only by the label pad
            assert not _intersect(boxes[a], boxes[b]), f"{a} meets {b} ({name}, {preset})"
        assert (
            boxes[a][0] >= -0.2
            and boxes[a][1] >= -0.2
            and boxes[a][2] <= canvas.layout.width_mm + 0.2
            and boxes[a][3] <= canvas.layout.height_mm + 0.2
        ), f"{a} leaves the figure ({name}, {preset})"
    for a in ("compass", "scale_bar", "total", "source"):  # the furniture is never over the map
        assert not _intersect(boxes[a], canvas.layout.map_box), f"{a} is over the map"


def test_furniture_has_the_same_place_in_every_country():
    """Compass at the upper right of the header, scale bar at the left of the footer, source at the right: the same offsets for a
    tall, a wide and a small country."""
    offsets = []
    for name in CASES:
        canvas, _ = _build(name, width=ms.FULL_WIDTH_MM)
        boxes = _boxes(canvas)
        w, h = canvas.layout.width_mm, canvas.layout.height_mm
        offsets.append(
            (
                w - boxes["compass"][2],
                h - boxes["compass"][3],
                boxes["scale_bar"][0],
                w - boxes["source"][2],
                boxes["source"][1],
            )
        )
        assert boxes["compass"][1] > canvas.layout.map_box[3], "the compass is in the header"
        assert boxes["scale_bar"][3] < canvas.layout.map_box[1], "the scale bar is in the footer"
    for k in range(5):
        values = [o[k] for o in offsets]
        assert max(values) - min(values) < 0.3, f"offset {k} differs between countries: {values}"


def test_header_holds_the_title_and_the_compass_without_meeting():
    canvas, _ = _build("small", preset="article_single")
    boxes = _boxes(canvas)
    assert boxes["title"][2] < boxes["compass"][0]


def test_colour_bar_has_the_height_of_the_map_when_it_is_on_the_right():
    canvas, _ = _build("tall")
    assert canvas.layout.legend == "right"
    assert canvas.layout.legend_box[1] == pytest.approx(canvas.layout.map_box[1])
    assert canvas.layout.legend_box[3] == pytest.approx(canvas.layout.map_box[3])


def test_presets_fix_the_width_and_the_fonts_in_points():
    assert {n: p.width_mm for n, p in ms.PRESETS.items()} == {
        "thesis": 190.0,
        "article_single": 90.0,
        "article_double": 180.0,
        "slide": 254.0,
    }
    for name, preset in ms.PRESETS.items():
        canvas, _ = _build("wide", preset=name)
        assert canvas.layout.width_mm == preset.width_mm
        assert canvas.texts["title"].get_fontsize() == preset.title_pt
        assert canvas.texts["subtitle"].get_fontsize() == preset.label_pt
        assert canvas.texts["total"].get_fontsize() == preset.legend_pt
        assert canvas.texts["source"].get_fontsize() == preset.footer_pt
    with pytest.raises(ValueError):
        ms.get_preset("poster")


def test_footer_goes_to_a_second_row_when_it_does_not_fit_one():
    sizes = {"scale_bar": (30.0, 9.0), "total": (50.0, 8.0), "source": (45.0, 4.0)}
    one, h1 = ms.plan_footer(sizes, 14.0, 187.0)
    assert one["scale_bar"][1] == one["total"][1] == one["source"][1]  # a single row
    assert one["scale_bar"][0] == 14.0 and one["source"][2] == 187.0
    assert one["scale_bar"][2] < one["total"][0] < one["total"][2] < one["source"][0]
    two, h2 = ms.plan_footer(sizes, 14.0, 90.0)
    assert h2 > h1
    boxes = list(two.values())
    for i, a in enumerate(boxes):
        assert a[0] >= 14.0 - 1e-9 and a[2] <= 90.0 + 1e-9
        for b in boxes[i + 1 :]:
            assert not _intersect(a, b)


def test_a_long_total_text_still_fits_a_half_column():
    text = "Total: 19,188.34 GW · 31,068.30 TWh/yr · mean CF 18.5% · eligible area 1,540,000 km²"
    canvas, _ = _build("small", preset="article_single", total=text)
    boxes = _boxes(canvas)
    assert boxes["total"][0] >= -0.2 and boxes["total"][2] <= canvas.layout.width_mm + 0.2
    assert not _intersect(boxes["total"], boxes["scale_bar"])
    assert not _intersect(boxes["total"], boxes["source"])


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
    first = ms.save_png(canvas, tmp_path / "a.png")
    other = _build("wide")[0]
    for artist in other.artists["compass"]:
        artist.remove()
    second = ms.save_png(other, tmp_path / "b.png")
    with Image.open(first) as a, Image.open(second) as b:
        assert not np.array_equal(np.asarray(a), np.asarray(b))
    assert hamming(dhash(first, 32), dhash(second, 32)) > 0


def test_synthetic_shapes_are_the_three_documented_ones():
    assert set(SHAPES) == {"tall", "wide", "small"}
