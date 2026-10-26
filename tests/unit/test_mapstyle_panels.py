"""The multi-panel sheet (`viz/panels.py`, COMMAND 68): the same fixed grid as a single map with several maps of one country, checked on the
six archetypes: no overlap, nothing cut, the degrees only on the outer maps, one meaning per colour, the stipple inside the country."""

from __future__ import annotations

import numpy as np
import pytest
import shapely
from matplotlib.colors import Normalize
from matplotlib.transforms import Bbox

from geofrea.viz import mapstyle as ms
from geofrea.viz.examples import ARCHETYPES, archetype_country
from geofrea.viz.panels import add_panel_colorbar, new_panels, panel_sizes, stipple_note

pytestmark = pytest.mark.unit

SHAPES = [(1, 3, "each"), (2, 3, "shared"), (3, 2, "shared")]


def _mm(bb, sheet):
    k = 25.4 / sheet.fig.dpi
    return bb.x0 * k, bb.y0 * k, bb.x1 * k, bb.y1 * k


def _meet(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _sheet(iso, rows, cols, bar, countries={}):  # noqa: B006 (a cache of the archetypes across the tests of the module)
    if iso not in countries:
        countries[iso] = archetype_country(iso)
    c = countries[iso]
    caps = [f"SSP{i + 1}-{i}.5 · 2041–2070" for i in range(rows * cols)]
    sheet = new_panels(
        c.geometry,
        iso=iso,
        variable="Climate forcing",
        captions=caps,
        n_rows=rows,
        n_cols=cols,
        subtitle="Ensemble mean of 6 GCMs · 0.05° analysis grid",
        total_text=stipple_note(),
        neighbours=c.neighbours,
        contiguous=c.contiguous,
        bar=bar,
    )
    norm = Normalize(-5, 10)
    image = None
    for i, panel in enumerate(sheet.panels):
        image = panel.draw_raster(c.change + i, c.grid_extent, cmap="RdBu", norm=norm)
        panel.stipple(np.isfinite(c.change) & (c.cf > 0.2), c.grid_extent)
    if bar == "shared":
        add_panel_colorbar(sheet, image, "Change (%)", "both")
    else:
        for i, panel in enumerate(sheet.panels):
            add_panel_colorbar(sheet, panel.ax.images[0], "Change (%)", "both", i)
    return sheet, c


def _boxes(sheet):
    sheet.fig.canvas.draw()
    r = sheet.fig.canvas.get_renderer()
    out = {}
    title = [sheet.texts["title"]] + (
        [sheet.texts["subtitle"]] if "subtitle" in sheet.texts else []
    )
    out["title"] = _mm(Bbox.union([t.get_window_extent(r) for t in title]), sheet)
    for name, artists in sheet.artists.items():
        boxes = []
        for a in artists:
            bb = a.get_window_extent(r)
            if hasattr(a, "get_bbox_patch") and a.get_bbox_patch() is not None:
                bb = a.get_bbox_patch().get_window_extent(r)
            boxes.append(bb)
        out[name] = _mm(Bbox.union(boxes), sheet)
    for i, p in enumerate(sheet.panels):
        out[f"map {i}"] = _mm(p.ax.get_tightbbox(r), sheet)
        out[f"caption {i}"] = _mm(p.caption.get_window_extent(r), sheet)
    for i, b in enumerate(sheet.bars):
        out[f"bar {i}"] = _mm(b.get_tightbbox(r), sheet)
    return out


@pytest.mark.parametrize("iso", list(ARCHETYPES))
@pytest.mark.parametrize("rows,cols,bar", SHAPES)
def test_nothing_overlaps_and_nothing_is_cut_in_any_sheet(iso, rows, cols, bar):
    sheet, _ = _sheet(iso, rows, cols, bar)
    boxes = _boxes(sheet)
    names = list(boxes)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            assert not _meet(boxes[a], boxes[b]), f"{a} meets {b} ({iso} {rows}x{cols})"
    w, h = sheet.width_mm, sheet.height_mm
    for name, box in boxes.items():
        assert box[0] >= -0.2 and box[1] >= -0.2 and box[2] <= w + 0.2 and box[3] <= h + 0.2, (
            f"{name} leaves the sheet ({iso} {rows}x{cols}): {box} in {w:.0f} x {h:.0f}"
        )
    assert h <= 250.5, f"the sheet is {h:.0f} mm tall"
    # the white middle of a diverging scale is the colour of the sea by design (the outline separates them): nothing else may conflict
    assert all("'sea'" in problem for problem in sheet.colour_problems())
    # the furniture is at its standard place: compass at the upper right, scale bar at the lower left, source at the lower right
    assert boxes["compass"][2] > w - 4.0 and boxes["compass"][3] > h - 4.0
    assert boxes["scale_bar"][0] < 20.0 and boxes["source"][2] > w - 6.0
    sheet.fig.clf()


def test_the_degrees_are_only_on_the_left_column_and_the_bottom_row():
    sheet, _ = _sheet("PRT", 2, 3, "shared")
    for i, panel in enumerate(sheet.panels):
        r, c = divmod(i, 3)
        has_y = len(panel.ax.get_yticks()) > 0
        has_x = len(panel.ax.get_xticks()) > 0
        assert has_y == (c == 0), f"panel {i}: latitude labels {has_y}"
        assert has_x == (r == 1), f"panel {i}: longitude labels {has_x}"
    sheet.fig.clf()


def test_every_map_has_the_same_frame_and_size_and_the_stipple_is_inside_the_country():
    sheet, _ = _sheet("CHE", 2, 3, "shared")
    sizes = {
        (
            round(p.layout.map_box[2] - p.layout.map_box[0], 6),
            round(p.layout.map_box[3] - p.layout.map_box[1], 6),
        )
        for p in sheet.panels
    }
    assert len(sizes) == 1
    for p in sheet.panels:
        dots = [
            coll
            for coll in p.ax.collections
            if coll.get_offsets().shape[0] > 0 and coll.get_rasterized()
        ]
        assert dots
        xy = np.asarray(dots[-1].get_offsets())
        assert xy.shape[0] > 20
        assert shapely.contains_xy(p.frame.polygon, xy[:, 0], xy[:, 1]).all(), (
            "a dot outside the country"
        )
    sheet.fig.clf()


def test_a_sheet_refuses_wrong_captions_and_a_bar_under_each_map_of_several_rows():
    c = archetype_country("LUX")
    with pytest.raises(ValueError, match="captions"):
        new_panels(c.geometry, iso="LUX", variable="V", captions=["a"], n_rows=1, n_cols=2)
    with pytest.raises(ValueError, match="single row"):
        new_panels(
            c.geometry,
            iso="LUX",
            variable="V",
            captions=list("abcd"),
            n_rows=2,
            n_cols=2,
            bar="each",
        )
    with pytest.raises(ValueError, match="OQ"):
        new_panels(
            c.geometry, iso="LUX", variable="V (OQ-12)", captions=["a", "b"], n_rows=1, n_cols=2
        )


def test_the_sheet_is_not_taller_than_the_page_and_the_maps_shrink_to_fit():
    pw, ph = panel_sizes(3, 2, 3.5, 190.0, 15.0, 14.0, 5.0, 11.5)
    assert 3 * ph + 15.0 + 14.0 <= 250.0
    pw2, ph2 = panel_sizes(1, 3, 1.0, 190.0, 15.0, 14.0, 5.0, 11.5)
    assert pw2 > pw and ph2 / pw2 == pytest.approx(1.0)


def test_the_sheet_png_carries_its_metadata(tmp_path):
    sheet, _ = _sheet("PRT", 1, 3, "each")
    sheet.meta["scale_mode"] = "shared"
    path = ms.save_png(sheet, tmp_path / "PRT_F4_forcing_solar_SSP3-7.0_2071-2100.png")
    meta = ms.read_png_metadata(path)
    assert meta["geofrea_scale_mode"] == "shared" and meta["Title"].startswith("Portugal")
