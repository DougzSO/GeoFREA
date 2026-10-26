"""The country archetypes of the figure tests (spec v2, T-13; COMMAND 67): real simplified geometry (PRT, CHL, BRA, CHE, IDN, LUX) with synthetic
data; for each one the five kinds of figure (density, capacity factor, forcing, eligibility, state) are drawn by the same code and checked for
overlap, cut text, dead space and the standard place of the furniture, and against a perceptual-hash golden. Nothing here is a result."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest
import shapely
from matplotlib.colors import ListedColormap, Normalize
from matplotlib.transforms import Bbox
from PIL import Image

from geofrea.viz import mapstyle as ms
from geofrea.viz.examples import ARCHETYPES, FIGURE_KINDS, archetype_country, archetype_figure

pytestmark = pytest.mark.unit

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "archetypes" / "hashes.json"
CASES = [(iso, kind) for iso in ARCHETYPES for kind in FIGURE_KINDS]


def _mm(bb, canvas):
    k = 25.4 / canvas.fig.dpi
    return bb.x0 * k, bb.y0 * k, bb.x1 * k, bb.y1 * k


def _meet(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _elements(canvas) -> dict[str, tuple[float, float, float, float]]:
    """Real boxes in mm of every piece of the figure that must not overlap another."""
    canvas.fig.canvas.draw()
    renderer = canvas.fig.canvas.get_renderer()
    out = {}
    for name, artists in canvas.artists.items():
        boxes = []
        for a in artists:
            bb = a.get_window_extent(renderer)
            if hasattr(a, "get_bbox_patch") and a.get_bbox_patch() is not None:
                bb = a.get_bbox_patch().get_window_extent(renderer)
            boxes.append(bb)
        out[name] = _mm(Bbox.union(boxes), canvas)
    title = [canvas.texts["title"]] + (
        [canvas.texts["subtitle"]] if "subtitle" in canvas.texts else []
    )
    out["title"] = _mm(Bbox.union([t.get_window_extent(renderer) for t in title]), canvas)
    out["axes"] = _mm(
        canvas.ax.get_tightbbox(renderer), canvas
    )  # the map and its labels in degrees
    if canvas.cax.get_visible():
        out["colour bar"] = _mm(canvas.cax.get_tightbbox(renderer), canvas)
    return out


def dhash(path: Path, size: int = 16) -> str:
    with Image.open(path) as im:
        gray = np.asarray(
            im.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS), dtype="float64"
        )
    bits = (gray[:, 1:] > gray[:, :-1]).ravel()
    return f"{int(''.join('1' if b else '0' for b in bits), 2):0{size * size // 4}x}"


def hamming(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()


@pytest.fixture(scope="module")
def countries():
    return {}


def _country(countries, iso):
    if iso not in countries:
        countries[iso] = archetype_country(iso)
    return countries[iso]


def test_the_fixtures_are_the_six_documented_archetypes():
    assert list(ARCHETYPES) == ["PRT", "CHL", "BRA", "CHE", "IDN", "LUX"]
    assert FIGURE_KINDS == ("density", "capacity_factor", "forcing", "eligibility", "state")
    for iso in ARCHETYPES:
        path = Path(__file__).resolve().parents[1] / "fixtures" / "archetypes" / f"{iso}.geojson"
        assert 3_000 < path.stat().st_size < 200_000, f"{iso} fixture is not small"


@pytest.mark.parametrize("iso", list(ARCHETYPES))
def test_the_synthetic_data_sit_on_the_country(iso, countries):
    c = _country(countries, iso)
    finite = np.isfinite(c.grid)
    assert finite.sum() > 20 and np.isfinite(c.cf).sum() == finite.sum()
    assert 0.08 <= np.nanmin(c.cf) and np.nanmax(c.cf) <= 0.38
    assert (c.classes[finite] >= 0).all() and (c.classes[~finite] == -1).all()
    assert len(c.units) >= 2 and c.units["density"].gt(0).all()


@pytest.mark.parametrize("iso,kind", CASES)
def test_every_figure_is_clean_and_matches_its_golden(iso, kind, countries, tmp_path):
    canvas = archetype_figure(_country(countries, iso), kind)
    w, h = canvas.layout.width_mm, canvas.layout.height_mm
    boxes = _elements(canvas)

    # no overlap: nothing meets anything else (the colour bar and the map are neighbours, not overlaps)
    names = list(boxes)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            if {a, b} == {"axes", "colour bar"}:
                continue
            assert not _meet(boxes[a], boxes[b]), f"{a} meets {b} ({iso}, {kind})"
    for name in ("compass", "scale_bar", "source", "total", "no_data", "locator"):
        if name in boxes:
            assert not _meet(boxes[name], canvas.layout.map_box), (
                f"{name} over the map ({iso}, {kind})"
            )

    # no text cut: every piece, every label and the figure stay inside the sheet
    for name, box in boxes.items():
        assert box[0] >= -0.2 and box[1] >= -0.2 and box[2] <= w + 0.2 and box[3] <= h + 0.2, (
            f"{name} leaves the figure ({iso}, {kind}): {box} in {w:.0f} x {h:.0f}"
        )

    # no dead space: the country fills the frame in one direction (frame = country + 3%), the map is not
    # separated from its legend, and the content is not a thin strip in the middle of a wide sheet
    xmin, ymin, xmax, ymax = canvas.frame.polygon.bounds
    fx0, fx1, fy0, fy1 = canvas.frame.bounds
    fill = max((xmax - xmin) / (fx1 - fx0), (ymax - ymin) / (fy1 - fy0))
    assert fill > 0.93, f"the country fills {fill:.0%} of its frame ({iso}, {kind})"
    legend = boxes.get("legend") or boxes.get("colour bar")
    gap = (
        legend[0] - canvas.layout.map_box[2]
        if canvas.layout.legend == "right"
        else (canvas.layout.map_box[1] - legend[3])
    )
    assert gap < 14.0, f"a band of {gap:.0f} mm between the map and its legend ({iso}, {kind})"
    span = (
        legend[2] if canvas.layout.legend == "right" else canvas.layout.map_box[2]
    ) - canvas.layout.map_box[0]
    assert span / w > 0.4, (
        f"the map and its legend fill {span / w:.0%} of the width ({iso}, {kind})"
    )

    # the furniture is at the standard place: compass at the upper right, scale bar at the lower left, source at the lower right
    assert boxes["compass"][2] > w - 4.0 and boxes["compass"][3] > h - 4.0
    assert boxes["scale_bar"][0] < 20.0 and boxes["scale_bar"][3] < canvas.layout.map_box[1]
    assert boxes["source"][2] > w - 6.0 and boxes["source"][3] < canvas.layout.map_box[1]

    # perceptual-hash golden
    path = ms.save_png(canvas, tmp_path / ms.figure_filename(iso, "test", kind))
    got = dhash(path)
    with Image.open(path) as im:
        size = list(im.size)
    key = f"{iso}_{kind}"
    if os.environ.get("GEOFREA_UPDATE_MAPSTYLE_BASELINES") == "1":
        data = json.loads(GOLDEN.read_text()) if GOLDEN.exists() else {}
        data[key] = {"hash": got, "size": size}
        GOLDEN.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    expected = json.loads(GOLDEN.read_text())[key]
    assert abs(size[0] - expected["size"][0]) <= 3 and abs(size[1] - expected["size"][1]) <= 3
    assert hamming(got, expected["hash"]) <= 14, (
        f"{key} differs from its golden: look at it, refreeze if intended"
    )


def test_the_furniture_has_the_same_place_in_every_country(countries):
    """Compass, scale bar, source and title at the same offsets from the corners of the sheet in all six archetypes."""
    rows = []
    for iso in ARCHETYPES:
        canvas = archetype_figure(_country(countries, iso), "density")
        boxes = _elements(canvas)
        w, h = canvas.layout.width_mm, canvas.layout.height_mm
        rows.append(
            (
                w - boxes["compass"][2],
                h - boxes["compass"][3],
                boxes["scale_bar"][0],
                w - boxes["source"][2],
                boxes["source"][1],
                boxes["title"][0],
                h - boxes["title"][3],
            )
        )
        canvas.fig.clf()
    for k in range(7):
        values = [r[k] for r in rows]
        assert max(values) - min(values) < 0.8, f"offset {k} differs between archetypes: {values}"


# ---------------------------------------------------------------------------------------------------------- the coast of Portugal


def test_the_synthetic_portugal_has_no_staircase_on_the_coast(countries):
    """PRT is the country of the stairs (about 90 x 70 cells of 0.05 degree): the raster is painted in a single colour over a grid that reaches
    beyond the coast and the border, and no coloured pixel may be farther than 1.5 pixels from the vector outline."""
    c = _country(countries, "PRT")
    canvas = ms.new_map(
        c.geometry,
        iso="PRT",
        technology="Solar PV",
        variable="Capacity density",
        graticule=False,
        width_mm=ms.FULL_WIDTH_MM,
    )
    west, east, south, north = canvas.frame.lonlat_extent
    extent = (west - 1.0, east + 1.0, south - 1.0, north + 1.0)
    grid = np.ones((round((extent[3] - extent[2]) / 0.05), round((extent[1] - extent[0]) / 0.05)))
    canvas.draw_raster(grid, extent, cmap=ListedColormap([(1.0, 0.0, 1.0)]), norm=Normalize(0, 2))
    canvas.fig.canvas.draw()
    rgba = np.asarray(canvas.fig.canvas.buffer_rgba())
    bb = canvas.ax.get_window_extent()
    height = rgba.shape[0]
    cols = np.arange(int(bb.x0) + 1, int(bb.x1) - 1)
    rows = np.arange(int(height - bb.y1) + 1, int(height - bb.y0) - 1)
    px, py = np.meshgrid(cols + 0.5, height - (rows + 0.5))
    x, y = canvas.ax.transData.inverted().transform(np.column_stack([px.ravel(), py.ravel()])).T
    block = rgba[np.ix_(rows, cols)][..., :3] / 255.0
    painted = (np.abs(block - np.array([1.0, 0.0, 1.0])).max(axis=2) < 0.06).ravel()
    metres_per_px = canvas.frame.width_m / (bb.x1 - bb.x0)
    polygon = canvas.frame.polygon
    outside = painted & ~shapely.contains_xy(polygon.buffer(1.5 * metres_per_px), x, y)
    assert outside.sum() == 0, f"{outside.sum()} pixels of data outside the coast"
    inside = shapely.contains_xy(polygon.buffer(-1.5 * metres_per_px), x, y)
    assert painted[inside].mean() > 0.995
    # one cell of 0.05 degree is about 25 pixels across here: a staircase would put pixels that far from the line
    assert 0.05 * 111_000 / metres_per_px > 15
