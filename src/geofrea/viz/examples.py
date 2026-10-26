"""Synthetic countries and rasters for the examples of `docs/figures/style_guide.md` and for the tests of `mapstyle`.

Three invented shapes (not any real country): a tall one, a wide one and a small one, each an ellipse with a far island that the
extent must ignore, plus a smooth skewed field. Nothing here is a result.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, replace
from pathlib import Path

import geopandas as gpd
import numpy as np
from matplotlib.colors import to_rgba
from shapely import affinity
from shapely.geometry import Point, box

from geofrea.viz.display import DisplayLayer
from geofrea.viz.mapstyle import Extent

# name: (centre lon, centre lat, half width deg, half height deg, rotation)
SHAPES = {
    "tall": (-70.0, -33.0, 3.0, 11.0, -18.0),
    "wide": (20.0, 5.0, 12.0, 3.5, 22.0),
    "small": (8.0, 47.0, 0.9, 0.6, 28.0),
}  # the last number turns the ellipse (degrees), so that two opposite corners of the map stay free


@dataclass(frozen=True)
class SyntheticCountry:
    name: str
    geometry: object  # mainland plus a far island, lon/lat
    mainland: object
    neighbours: gpd.GeoDataFrame
    grid: np.ndarray  # skewed positive field, NaN outside the mainland
    grid_extent: Extent


def synthetic_country(name: str, pixels: int = 220, seed: int = 56) -> SyntheticCountry:
    """The synthetic country `name` (`tall`, `wide` or `small`), with a neighbour on its eastern side and an island far out to sea."""
    lon, lat, hw, hh, turn = SHAPES[name]
    mainland = affinity.rotate(
        affinity.scale(Point(lon, lat).buffer(1.0, quad_segs=32), hw, hh), turn, origin=(lon, lat)
    )
    island = Point(lon - 4 * hw, lat - 3 * hh).buffer(0.1 * min(hw, hh))
    geometry = mainland.union(island)
    neighbour = box(lon + 0.85 * hw, lat - 1.6 * hh, lon + 3.2 * hw, lat + 1.6 * hh).difference(
        mainland.buffer(0.02 * hw)
    )
    neighbours = gpd.GeoDataFrame({"name": ["neighbour"]}, geometry=[neighbour], crs="EPSG:4326")
    w, s, e, n = mainland.bounds
    extent = (w, e, s, n)
    rng = np.random.default_rng(seed)
    ny = pixels
    nx = max(8, round(pixels * (e - w) / (n - s)))
    xs = w + (np.arange(nx) + 0.5) / nx * (e - w)
    ys = n - (np.arange(ny) + 0.5) / ny * (n - s)
    xx, yy = np.meshgrid(xs, ys)
    inside = _contains(mainland, xx, yy)
    field = np.exp(
        1.2 * np.sin(3 * (xx - lon) / hw) * np.cos(2 * (yy - lat) / hh)
        + 0.4 * rng.standard_normal(xx.shape)
    )
    field = field * (
        1
        + 4
        * np.exp(-(((xx - lon + 0.3 * hw) / (0.15 * hw)) ** 2 + ((yy - lat) / (0.15 * hh)) ** 2))
    )
    grid = np.where(inside, field, np.nan)
    return SyntheticCountry(name, geometry, mainland, neighbours, grid, extent)


def _contains(polygon, xx: np.ndarray, yy: np.ndarray) -> np.ndarray:
    import shapely

    return shapely.contains_xy(polygon, xx.ravel(), yy.ravel()).reshape(xx.shape)


# ----------------------------------------------------------------------------------------------------------- country archetypes (COMMAND 67)
# Real, simplified geometries (tests/fixtures/archetypes, `scripts/make_archetype_fixtures.py`) with synthetic data on a 0.05 degree grid:
# the same figure code is tried on a tall and narrow country, a very tall one, a wide one, a compact one, a fragmented one and a tiny one.

FIGURE_KINDS = ("density", "capacity_factor", "forcing", "eligibility", "state")
ARCHETYPE_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "archetypes"


def _load_archetypes() -> dict[str, tuple[str, bool]]:
    """ISO3 -> (shape, only the contiguous territory is mapped), from `tests/fixtures/archetypes/archetypes.yaml` (the code names no country)."""
    import yaml

    data = yaml.safe_load((ARCHETYPE_DIR / "archetypes.yaml").read_text(encoding="utf-8"))
    return {iso: (v["shape"], bool(v["contiguous"])) for iso, v in data.items()}


ARCHETYPES = _load_archetypes()
EXAMPLE_MARK = "EXAMPLE, synthetic data"


@dataclass(frozen=True)
class ArchetypeCountry:
    iso: str
    name: str
    shape: str
    geometry: object  # the country in lon/lat (all its parts)
    contiguous: bool
    neighbours: gpd.GeoDataFrame
    grid: (
        np.ndarray
    )  # a smooth skewed positive field on the 0.05 degree grid, NaN outside the country
    grid_extent: Extent
    cf: np.ndarray  # capacity factor, 0.08 to 0.38
    change: np.ndarray  # change of the resource in percent, from -4 to +9
    classes: np.ndarray  # dominant exclusion 0-4 and 5 = none, -1 outside
    units: gpd.GeoDataFrame  # synthetic "states": admin1_id, density, total
    mapped: object  # the territory that is mapped (the contiguous part, or all of it)
    field: FieldModel  # the smooth field of the data, defined at any resolution


FINE_FACTOR = 5  # a cell of 0.05 degree is 5 x 5 pixels of the 0.01 degree display layer
MAX_FINE_PIXELS = (
    6_000_000  # a larger country has no fine layer in the examples (it does not need one)
)
NOISE_PIXEL = 0.012  # the independent noise of a pixel, small beside the correlated field


@dataclass(frozen=True)
class FieldModel:
    """The smooth synthetic field of an archetype, defined for any point: a trend, a correlated noise (random waves, 3 cells and more across)
    and the constants that scale it to 0-1 over the cells of the country. The coarse and the fine layers are the same field."""

    west: float
    east: float
    south: float
    north: float
    cell_deg: float
    waves: np.ndarray  # rows: kx, ky, phase, amplitude
    lo: float
    span: float

    def smooth(self, xx: np.ndarray, yy: np.ndarray) -> np.ndarray:
        u = (xx - self.west) / max(self.east - self.west, 1e-9)
        v = (yy - self.south) / max(self.north - self.south, 1e-9)
        trend = np.sin(2.5 * u + 1.0) * np.cos(2.0 * v) + 0.6 * np.exp(
            -(((u - 0.35) / 0.2) ** 2 + ((v - 0.6) / 0.2) ** 2)
        )
        kx, ky, phase, amp = self.waves.T
        waves = (amp * np.cos(np.multiply.outer(xx, kx) + np.multiply.outer(yy, ky) + phase)).sum(
            axis=-1
        )
        return trend + 0.3 * waves

    def unit(self, xx: np.ndarray, yy: np.ndarray) -> np.ndarray:
        return (self.smooth(xx, yy) - self.lo) / self.span


def _waves(rng, size_deg: float, cell_deg: float, count: int = 24) -> np.ndarray:
    """Random plane waves with a wavelength from 3 cells (or 4% of the country) to 35% of the country, amplitudes that add up to unit variance."""
    shortest = max(3.0 * cell_deg, 0.04 * size_deg)
    longest = max(0.35 * size_deg, 2.0 * shortest)
    wavelength = rng.uniform(shortest, longest, count)
    angle = rng.uniform(0.0, 2.0 * math.pi, count)
    k = 2.0 * math.pi / wavelength
    return np.column_stack(
        [
            k * np.cos(angle),
            k * np.sin(angle),
            rng.uniform(0, 2 * math.pi, count),
            np.full(count, math.sqrt(2.0 / count)),
        ]
    )


def archetype_country(iso: str, cell_deg: float = 0.05, seed: int = 67) -> ArchetypeCountry:
    """The archetype `iso` with synthetic data. The data are invented: a smooth trend plus a spatially correlated field and a small noise
    per pixel (never an independent noise per cell), nothing computed from a result."""
    import shapely

    from geofrea.viz.mapstyle import contiguous_geometry, country_name

    shape, contiguous = ARCHETYPES[iso]
    frame = gpd.read_file(ARCHETYPE_DIR / f"{iso}.geojson")
    geometry = frame[frame["role"] == "country"].geometry.iloc[0]
    neighbours = frame[frame["role"] == "neighbour"][["geometry"]].reset_index(drop=True)
    mapped = contiguous_geometry(geometry) if contiguous else geometry
    w, s, e, n = mapped.bounds
    west, east = math.floor(w / cell_deg) * cell_deg, math.ceil(e / cell_deg) * cell_deg
    south, north = math.floor(s / cell_deg) * cell_deg, math.ceil(n / cell_deg) * cell_deg
    nx, ny = round((east - west) / cell_deg), round((north - south) / cell_deg)
    xs = west + (np.arange(nx) + 0.5) * cell_deg
    ys = north - (np.arange(ny) + 0.5) * cell_deg
    xx, yy = np.meshgrid(xs, ys)
    inside = shapely.contains_xy(mapped, xx.ravel(), yy.ravel()).reshape(xx.shape)
    rng = np.random.default_rng(seed)
    model = FieldModel(
        west,
        east,
        south,
        north,
        cell_deg,
        _waves(rng, max(east - west, north - south), cell_deg),
        0.0,
        1.0,
    )
    raw = model.smooth(xx, yy)
    model = replace(model, lo=float(raw[inside].min()), span=float(np.ptp(raw[inside])) or 1.0)
    unit = model.unit(xx, yy)
    v = (yy - south) / max(north - south, 1e-9)
    jitter = NOISE_PIXEL * rng.standard_normal(xx.shape)
    field = np.exp(0.9 * raw + 0.04 * rng.standard_normal(xx.shape))
    grid = np.where(inside, field, np.nan)
    cf = np.where(inside, 0.08 + 0.30 * np.clip(unit + jitter, 0, 1), np.nan)
    change = np.where(inside, -4.0 + 13.0 * np.clip(0.7 * v + 0.3 * unit + jitter, 0, 1), np.nan)
    noisy = unit * 5.5 + 0.35 * rng.standard_normal(xx.shape)
    classes = np.where(inside, np.clip(noisy.astype(int), 0, 5), -1)
    return ArchetypeCountry(
        iso,
        country_name(iso),
        shape,
        geometry,
        contiguous,
        gpd.GeoDataFrame(neighbours, crs="EPSG:4326"),
        grid,
        (west, east, south, north),
        cf,
        change,
        classes,
        _synthetic_units(mapped, inside, xx, yy, rng),
        mapped,
        model,
    )


def fine_layer(country: ArchetypeCountry, kind: str, seed: int = 68) -> DisplayLayer | None:
    """The 0.01 degree display layer of `kind` (`density` or `capacity_factor`) of the archetype: the same field as the 0.05 degree grid
    evaluated on pixels five times finer, with its own small noise; None for a kind with no such layer (a climate delta, classes, states) or a
    country too large for the examples."""
    import shapely

    if kind not in ("density", "capacity_factor"):
        return None
    west, east, south, north = country.grid_extent
    k = FINE_FACTOR
    fine_deg = country.field.cell_deg / k
    ny, nx = round((north - south) / fine_deg), round((east - west) / fine_deg)
    if nx * ny > MAX_FINE_PIXELS:
        return None
    xs = west + (np.arange(nx) + 0.5) * fine_deg
    ys = north - (np.arange(ny) + 0.5) * fine_deg
    xx, yy = np.meshgrid(xs, ys)
    inside = shapely.contains_xy(country.mapped, xx.ravel(), yy.ravel()).reshape(xx.shape)
    rng = np.random.default_rng(seed)
    raw = country.field.smooth(xx, yy)
    if kind == "density":
        values = np.exp(0.9 * raw + 0.04 * rng.standard_normal(xx.shape))
    else:
        unit = country.field.unit(xx, yy) + NOISE_PIXEL * rng.standard_normal(xx.shape)
        values = 0.08 + 0.30 * np.clip(unit, 0, 1)
    return DisplayLayer(
        f"display_{kind}", np.where(inside, values, np.nan), country.grid_extent, fine_deg
    )


def _synthetic_units(mapped, inside, xx, yy, rng, count: int = 6) -> gpd.GeoDataFrame:
    """Invented administrative units: the Voronoi cells of random points of the country, cut to it, with a density and a total each."""
    import shapely

    cells = np.flatnonzero(inside.ravel())
    k = min(count, max(len(cells) // 2, 2))
    pick = rng.choice(cells, size=k, replace=False)
    points = shapely.MultiPoint(list(zip(xx.ravel()[pick], yy.ravel()[pick], strict=True)))
    parts = shapely.voronoi_polygons(points, extend_to=mapped.envelope.buffer(1.0))
    polygons = [g.intersection(mapped) for g in parts.geoms]
    polygons = [g for g in polygons if not g.is_empty]
    density = np.sort(rng.uniform(0.2, 4.0, len(polygons)))[rng.permutation(len(polygons))]
    area = np.array([g.area for g in polygons])
    return gpd.GeoDataFrame(
        {
            "admin1_id": [f"U{i}" for i in range(len(polygons))],
            "density": density,
            "total": density * area * 100.0,
        },
        geometry=polygons,
        crs="EPSG:4326",
    )


def archetype_figure(
    country: ArchetypeCountry,
    kind: str,
    preset: str = "thesis",
    *,
    display_smoothing: str = "auto",
    fine: bool = True,
):
    """One figure of the kind `kind` (one of `FIGURE_KINDS`) of the archetype, drawn by `MapFigure` with its synthetic data.

    The continuous kinds use the 0.01 degree display layer (`fine_layer`) when the analysis cell would be a block, and are smoothed for
    display (`display_smoothing`) when a cell is still one; the climate delta always is (it comes from a GCM). The kinds of classes and
    states are never smoothed. `fine=False` leaves the display layer out."""
    from geofrea.viz import mapstyle as ms

    common = {"iso": country.iso, "preset": preset, "neighbours": country.neighbours}
    note = ms.resolution_note(cell_deg=0.05)
    if kind in ("density", "capacity_factor", "forcing"):
        technology, variable, label, vkind, tech, scenario, climate, grid = {
            "density": (
                "Solar PV",
                "Capacity density",
                "MW/km²",
                "density",
                "solar",
                "Central",
                "Reference climate",
                country.grid,
            ),
            "capacity_factor": (
                "Onshore wind",
                "Capacity factor",
                "Capacity factor",
                "capacity_factor",
                "wind",
                "Central",
                "Reference climate",
                country.cf,
            ),
            "forcing": (
                "Solar PV",
                "Change of the resource",
                "Change (%)",
                "delta",
                "solar",
                "SSP3-7.0",
                "2071-2100 vs 1995-2014",
                country.change,
            ),
        }[kind]
        return ms.raster_map(
            grid,
            country.grid_extent,
            country.geometry,
            technology=technology,
            variable=variable,
            label=label,
            kind=vkind,
            tech=tech,
            scenario=scenario,
            climate=f"{climate} · {EXAMPLE_MARK}",
            resolution=note,
            unit={"density": None, "capacity_factor": "", "forcing": "%"}[kind],
            total_text=EXAMPLE_MARK,
            no_data_label=ms.NO_DATA_LABEL if kind != "forcing" else None,
            contiguous=country.contiguous,
            display_layer=fine_layer(country, kind) if fine else None,
            display_smoothing=display_smoothing,
            coarse_source=kind == "forcing",
            **common,
        )
    if kind == "eligibility":
        spec = ms.qualitative_legend(
            "Dominant exclusion",
            ["E1 protected", "E2 water", "E3 riparian", "E4 slope", "E5 land cover"],
            none_label="None",
        )
        side, below = ms.legend_space(spec)
        canvas = ms.new_map(
            country.geometry,
            technology="Solar PV",
            variable="Dominant exclusion",
            subtitle=ms.format_subtitle("Central", note, EXAMPLE_MARK),
            legend_side_mm=side,
            legend_below_mm=below,
            contiguous=country.contiguous,
            **common,
        )
        colours = np.array(
            [[1.0, 1.0, 1.0, 0.0]]
            + [list(to_rgba(c)) for c in ms.class_colours(5)]
            + [list(to_rgba(ms.CLASS_NONE_COLOUR))]
        )
        canvas.draw_raster(colours[country.classes + 1], country.grid_extent)
        ms.draw_classed_legend(canvas, spec)
        canvas.meta["resolution"] = note
        return canvas
    if kind == "state":
        units = country.units
        edges = np.quantile(units["density"], [0.2, 0.4, 0.6, 0.8])
        classes = np.searchsorted(edges, units["density"].to_numpy())
        cmap = ms.colormap_for("density", "wind")
        colours = [cmap(0.15 + 0.85 * i / 4) for i in range(5)]
        labels = (
            [f"< {edges[0]:.2g}"]
            + [f"{a:.2g} to {b:.2g}" for a, b in itertools.pairwise(edges)]
            + [f"> {edges[-1]:.2g}"]
        )
        reference = float(units["total"].max())
        spec = ms.ClassedLegend(
            title="Capacity density (MW/km²)",
            labels=tuple(labels),
            colours=tuple(colours),
            no_value_label=ms.NO_DATA_LABEL,
            circle_title="Capacity (GW)",
            circles=tuple(
                (f"{v:g}", ms.circle_radius_mm(v, reference, ms.CIRCLE_MAX_MM))
                for v in ms.nice_values_below(reference)
            ),
        )
        side, below = ms.legend_space(spec)
        canvas = ms.new_map(
            country.geometry,
            technology="Onshore wind",
            variable="Capacity density by state",
            subtitle=ms.format_subtitle("Central", EXAMPLE_MARK),
            total_text=EXAMPLE_MARK,
            legend_side_mm=side,
            legend_below_mm=below,
            contiguous=country.contiguous,
            **common,
        )
        ms.draw_choropleth(canvas, units, [colours[c] for c in classes])
        anchors = units.geometry.representative_point()
        radii = [ms.circle_radius_mm(float(t), reference, ms.CIRCLE_MAX_MM) for t in units["total"]]
        ms.draw_circles(canvas, anchors.x, anchors.y, radii)
        ms.draw_classed_legend(canvas, spec)
        return canvas
    raise ValueError(f"unknown figure kind {kind!r}; one of {FIGURE_KINDS}")
