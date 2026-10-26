"""The geographic side of the common map style (COMMAND 67): LAEA projection for drawing only, the raster copied cell by cell and clipped by
the country polygon (no staircase on the coast), the neighbours, the entry for "no potential", the locator inset, the resolution in the
subtitle, the graticule in degrees, the figure that narrows for a tall country. Synthetic data only."""

from __future__ import annotations

import math
import re

import numpy as np
import pytest
import shapely
from matplotlib.colors import ListedColormap, Normalize

from geofrea.viz import mapstyle as ms
from geofrea.viz.examples import synthetic_country

pytestmark = pytest.mark.unit

MAGENTA = (1.0, 0.0, 1.0)


def _intersect(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _px_to_mm(bb, canvas):
    k = 25.4 / canvas.fig.dpi
    return bb.x0 * k, bb.y0 * k, bb.x1 * k, bb.y1 * k


# -------------------------------------------------------------------------------------------------------------------------- projection


def test_the_frame_is_laea_centred_on_the_country_and_round_trips():
    country = synthetic_country("tall")
    polygon = ms.contiguous_geometry(country.geometry)
    frame = ms.make_frame(polygon)
    assert "+proj=laea" in frame.crs.to_proj4()
    centre = polygon.centroid
    x, y = frame.to_xy(centre.x, centre.y)
    assert abs(float(x)) < 1.0 and abs(float(y)) < 1.0
    lon, lat = frame.inverse.transform(*frame.to_xy([-70.0, -68.0], [-30.0, -35.0]))
    assert lon == pytest.approx([-70.0, -68.0]) and lat == pytest.approx([-30.0, -35.0])
    # the frame holds the projected country plus 3% of its size on each side
    xmin, ymin, xmax, ymax = frame.polygon.bounds
    assert frame.bounds[0] == pytest.approx(xmin - 0.03 * (xmax - xmin))
    assert frame.bounds[3] == pytest.approx(ymax + 0.03 * (ymax - ymin))


def test_laea_keeps_areas():
    """The projection is equal-area: a cell of 0.05 degree has the area of the sphere (R^2 dlon (sin lat2 - sin lat1)) in the projection."""
    frame = ms.make_frame(ms.contiguous_geometry(synthetic_country("wide").geometry))
    for lon, lat in ((20.0, 5.0), (12.0, 1.0), (28.0, 9.0)):
        cell = shapely.box(lon, lat, lon + 0.05, lat + 0.05)
        projected = frame.project_geometry(cell).area
        r = 6371008.8
        sphere = (
            r
            * r
            * math.radians(0.05)
            * (math.sin(math.radians(lat + 0.05)) - math.sin(math.radians(lat)))
        )
        assert projected == pytest.approx(sphere, rel=1e-2)  # the sphere against the WGS84 ellipsoid


def test_the_scale_bar_is_measured_in_the_projection():
    canvas = ms.new_map(
        synthetic_country("wide").geometry, iso="XXX", technology="Solar PV", variable="Capacity"
    )
    km = ms.scale_bar_length_km(None, width_km=canvas.frame.width_km)
    map_w = canvas.layout.map_box[2] - canvas.layout.map_box[0]
    canvas.fig.canvas.draw()
    bars = [a for a in canvas.artists["scale_bar"] if hasattr(a, "get_width")]
    drawn_mm = sum(a.get_width() for a in bars)
    assert drawn_mm / map_w * canvas.frame.width_km == pytest.approx(km, rel=1e-6)
    assert km in {1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000}


def test_the_graticule_is_labelled_in_degrees():
    canvas = ms.new_map(
        synthetic_country("tall").geometry, iso="XXX", technology="Solar PV", variable="Capacity"
    )
    canvas.fig.canvas.draw()
    labels = [t.get_text() for t in (*canvas.ax.get_xticklabels(), *canvas.ax.get_yticklabels())]
    assert labels and all(re.fullmatch(r"\d+(\.\d)?°[NSEW]|0°", t) for t in labels), labels


# ------------------------------------------------------------------------------------------------------------------------- the raster


def test_reprojection_copies_the_cell_that_contains_each_pixel():
    """A grid whose value is its own cell number: every pixel of the map holds a value that exists in the grid, equal to the cell that
    contains the centre of that pixel; nothing is interpolated."""
    country = synthetic_country("small")
    frame = ms.make_frame(ms.contiguous_geometry(country.geometry))
    west, east, south, north = country.grid_extent
    ny, nx = 40, 50
    grid = np.arange(ny * nx, dtype="float64").reshape(ny, nx)
    out, extent_m = ms.reproject_nearest(grid, country.grid_extent, frame, pixel_m=800.0)
    finite = np.isfinite(out)
    assert finite.any() and set(np.unique(out[finite])) <= set(grid.ravel())
    ys, xs = np.nonzero(finite)
    for r, c in list(zip(ys, xs))[:: max(len(ys) // 200, 1)]:
        x = extent_m[0] + (c + 0.5) * 800.0
        y = extent_m[3] - (r + 0.5) * 800.0
        lon, lat = frame.inverse.transform(x, y)
        col = math.floor((lon - west) / (east - west) * nx)
        row = math.floor((north - lat) / (north - south) * ny)
        assert out[r, c] == grid[row, col]


def _paint_everywhere(name: str, clip: bool):
    """The country drawn with a single colour over a grid that reaches well beyond it: the coloured pixels are exactly what the figure
    paints as data."""
    country = synthetic_country(name)
    canvas = ms.new_map(
        country.geometry,
        iso="XXX",
        country="Examplia",
        technology="Solar PV",
        variable="Capacity",
        width_mm=ms.HALF_WIDTH_MM,
        graticule=False,
    )
    west, east, south, north = canvas.frame.lonlat_extent
    pad = 1.0
    extent = (west - pad, east + pad, south - pad, north + pad)
    cells = 0.05
    grid = np.ones((int((extent[3] - extent[2]) / cells), int((extent[1] - extent[0]) / cells)))
    canvas.draw_raster(
        grid, extent, cmap=ListedColormap([MAGENTA]), norm=Normalize(0, 2), clip=clip
    )
    canvas.fig.canvas.draw()
    rgba = np.asarray(canvas.fig.canvas.buffer_rgba())
    bb = canvas.ax.get_window_extent()
    h = rgba.shape[0]
    cols = np.arange(int(bb.x0) + 1, int(bb.x1) - 1)
    rows = np.arange(int(h - bb.y1) + 1, int(h - bb.y0) - 1)
    px, py = np.meshgrid(cols + 0.5, h - (rows + 0.5))
    x, y = canvas.ax.transData.inverted().transform(np.column_stack([px.ravel(), py.ravel()])).T
    block = rgba[np.ix_(rows, cols)][..., :3] / 255.0
    painted = (np.abs(block - np.array(MAGENTA)).max(axis=2) < 0.06).ravel()
    metres_per_px = canvas.frame.width_m / (bb.x1 - bb.x0)
    return canvas, x, y, painted, metres_per_px


@pytest.mark.parametrize("name", ["small", "tall", "wide"])
def test_the_raster_is_clipped_by_the_polygon_with_no_staircase(name):
    canvas, x, y, painted, px_m = _paint_everywhere(name, clip=True)
    polygon = canvas.frame.polygon
    near = shapely.contains_xy(polygon.buffer(1.5 * px_m), x, y)
    inner = shapely.contains_xy(polygon.buffer(-1.5 * px_m), x, y)
    assert not (painted & ~near).any(), "data painted outside the coast"
    assert painted[inner].mean() > 0.995, "a hole inside the country"


def test_without_the_clip_the_cells_stick_out_over_the_sea():
    """The negative control: the same figure with `clip=False` paints beyond the polygon, so the test above does look at the coast."""
    canvas, x, y, painted, px_m = _paint_everywhere("small", clip=False)
    near = shapely.contains_xy(canvas.frame.polygon.buffer(1.5 * px_m), x, y)
    assert (painted & ~near).sum() > 500


def test_the_image_is_rasterised_nearest_without_smoothing():
    country = synthetic_country("small")
    canvas = ms.new_map(
        country.geometry, iso="XXX", country="Examplia", technology="T", variable="V"
    )
    image = canvas.draw_raster(
        country.grid,
        country.grid_extent,
        cmap=ms.colormap_for("density", "solar"),
        norm=Normalize(0, 5),
    )
    assert image.get_interpolation() == "nearest" and image.get_rasterized()
    assert image.get_clip_path() is not None


# ------------------------------------------------------------------------------------------------------------------ context and legend


def _raster(name: str, **kwargs):
    country = synthetic_country(name)
    args = {
        "iso": "XXX",
        "country": "Examplia",
        "technology": "Solar PV",
        "variable": "Capacity density",
        "label": "MW/km²",
        "kind": "density",
        "tech": "solar",
        "scenario": "Central",
        "climate": "Reference climate",
        "neighbours": country.neighbours,
    }
    args.update(kwargs)
    return ms.raster_map(country.grid, country.grid_extent, country.geometry, **args), country


@pytest.mark.parametrize("name", ["tall", "wide", "small"])
def test_no_potential_has_its_own_grey_and_its_own_legend_entry(name):
    canvas, _ = _raster(name, no_data_label="no potential")
    assert "no_data" in canvas.artists
    assert canvas.colours[ms.NO_DATA_COLOUR] == "no potential"
    assert ms.delta_e(ms.NO_DATA_COLOUR, ms.NEIGHBOUR_COLOUR) > 12.0
    assert canvas.colour_problems() == []
    canvas.fig.canvas.draw()
    renderer = canvas.fig.canvas.get_renderer()
    entry = _px_to_mm(
        shapely_union([a.get_window_extent(renderer) for a in canvas.artists["no_data"]]), canvas
    )
    bar = _px_to_mm(canvas.cax.get_tightbbox(renderer), canvas)
    assert not _intersect(entry, bar), "the entry meets the colour bar"
    assert not _intersect(entry, canvas.layout.map_box)
    assert entry[0] >= -0.2 and entry[2] <= canvas.layout.width_mm + 0.2


def shapely_union(boxes):
    from matplotlib.transforms import Bbox

    return Bbox.union(boxes)


def test_the_part_of_the_country_without_value_is_painted_grey():
    country = synthetic_country("wide")
    grid = country.grid.copy()
    grid[:, : grid.shape[1] // 2] = np.nan  # the west half has no value
    canvas = ms.raster_map(
        grid,
        country.grid_extent,
        country.geometry,
        iso="XXX",
        country="Examplia",
        technology="Solar PV",
        variable="Capacity density",
        label="MW/km²",
        kind="density",
        tech="solar",
        no_data_label="no potential",
        graticule=False,
    )
    canvas.fig.canvas.draw()
    rgba = np.asarray(canvas.fig.canvas.buffer_rgba())[..., :3] / 255.0
    grey = np.array(matplotlib_rgb(ms.NO_DATA_COLOUR))
    share = (np.abs(rgba - grey).max(axis=2) < 0.02).sum()
    assert share > 20000, "the grey of no potential is missing from the map"


def matplotlib_rgb(colour):
    from matplotlib.colors import to_rgb

    return to_rgb(colour)


def test_neighbours_are_drawn_in_light_grey_within_the_buffer_only():
    """A country 4 degrees away is outside the 2.5 degree buffer: not drawn. One that touches the border is."""
    import geopandas as gpd

    country = synthetic_country("small")
    polygon = ms.contiguous_geometry(country.geometry)
    _west, south, east, north = polygon.bounds
    touching = shapely.box(east - 0.05, south, east + 0.6, north)
    far = shapely.box(east + 4.0, south, east + 6.0, north)
    near_only = gpd.GeoDataFrame(geometry=[touching], crs="EPSG:4326")
    far_only = gpd.GeoDataFrame(geometry=[far], crs="EPSG:4326")
    kwargs = {
        "iso": "XXX",
        "country": "Examplia",
        "technology": "T",
        "variable": "V",
        "graticule": False,
    }
    a = ms.new_map(country.geometry, neighbours=near_only, **kwargs)
    b = ms.new_map(country.geometry, neighbours=far_only, **kwargs)
    grey = np.array(matplotlib_rgb(ms.NEIGHBOUR_COLOUR))

    def count(canvas):
        canvas.fig.canvas.draw()
        rgba = np.asarray(canvas.fig.canvas.buffer_rgba())[..., :3] / 255.0
        return int((np.abs(rgba - grey).max(axis=2) < 0.01).sum())

    assert count(a) > 5000 and count(b) < 1500  # a few grey pixels are the anti-aliasing of the text


def test_the_locator_inset_is_only_in_the_figures_that_ask_for_it():
    plain, _ = _raster("tall")
    assert "locator" not in plain.artists
    canvas, _ = _raster("tall", locator=True)
    assert "locator" in canvas.artists
    canvas.fig.canvas.draw()
    renderer = canvas.fig.canvas.get_renderer()
    inset = _px_to_mm(canvas.artists["locator"][0].get_window_extent(renderer), canvas)
    compass = _px_to_mm(
        __import__("matplotlib.transforms", fromlist=["Bbox"]).Bbox.union(
            [a.get_window_extent(renderer) for a in canvas.artists["compass"]]
        ),
        canvas,
    )
    title = _px_to_mm(canvas.texts["title"].get_window_extent(renderer), canvas)
    assert not _intersect(inset, compass) and not _intersect(inset, title)
    assert inset[1] > canvas.layout.map_box[3], "the inset is in the header"
    assert "this country (locator)" in canvas.colours.values()


def test_the_resolution_is_in_the_subtitle_and_in_the_metadata():
    assert ms.resolution_note(cell_deg=0.05) == "0.05° analysis grid"
    assert ms.resolution_note(native_m=30) == "native resolution ~30 m"
    with pytest.raises(ValueError):
        ms.resolution_note()
    with pytest.raises(ValueError):
        ms.resolution_note(cell_deg=0.05, native_m=30)
    canvas, _ = _raster("wide", resolution=ms.resolution_note(cell_deg=0.05))
    text = canvas.texts["subtitle"].get_text().replace("\n", " ")
    assert "Central · Reference climate · 0.05° analysis grid" in text
    assert canvas.meta["resolution"] == "0.05° analysis grid"


def test_a_very_tall_country_gets_a_narrower_figure_and_the_others_keep_the_preset_width():
    tall, _ = _raster("tall")
    wide, _ = _raster("wide")
    assert tall.layout.width_mm < ms.FULL_WIDTH_MM and tall.layout.width_mm >= 80.0
    assert wide.layout.width_mm == ms.FULL_WIDTH_MM
    content = tall.layout.legend_box[2] - tall.layout.map_box[0]
    assert content / tall.layout.width_mm > 0.45, "dead band at the sides of a narrow map"
    assert ms.fitted_width_mm(0.8, 190.0, 26.0) == 190.0
