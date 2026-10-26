"""What the maps of one country share: its territory, the extent of its maps and its neighbours (COMMAND 68).

Found once per country and used by every family of figures (F2a layers, F3 eligibility, F4 forcing, F5 potential, states), so that the
border, the frame and the neighbours are the same in all of them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import geopandas as gpd
import numpy as np

from geofrea.core import paths as core_paths
from geofrea.core.constants import CELL_ORIGIN_LAT, CELL_ORIGIN_LON
from geofrea.core.scale import active_scale
from geofrea.viz import mapstyle as ms


def row_col_from_id(ids: np.ndarray | int) -> tuple[np.ndarray, np.ndarray]:
    """Row and column on the lattice of the active scale of the cell ids (as `land_eligibility.cells.row_col_from_id`; `viz` may import `core` only)."""
    ids = np.asarray(ids, dtype=np.int64)
    n_cols = active_scale().n_cols
    return ids // n_cols, ids % n_cols


NATURAL_EARTH_FILE = "ne_50m_admin_0_countries.shp"
logger = logging.getLogger("geofrea.viz.context")


def country_geometry(units: gpd.GeoDataFrame | None, cell_ids: np.ndarray):
    """The territory as drawn: the union of the admin1 units, or (no units) the union of the cells of the country."""
    if units is not None and len(units):
        return units.to_crs("EPSG:4326").union_all()
    from shapely.geometry import box
    from shapely.ops import unary_union

    cell = active_scale().cell_deg
    rows, cols = row_col_from_id(cell_ids)
    return unary_union(
        [
            box(
                CELL_ORIGIN_LON + c * cell,
                CELL_ORIGIN_LAT - (r + 1) * cell,
                CELL_ORIGIN_LON + (c + 1) * cell,
                CELL_ORIGIN_LAT - r * cell,
            )
            for r, c in zip(rows.tolist(), cols.tolist(), strict=True)
        ]
    )


def load_neighbours(iso: str) -> gpd.GeoDataFrame | None:
    """The neighbouring countries (Natural Earth 50 m, public domain) in `raw/natural_earth/_global/`, without the country itself; `None` when the
    file was not acquired (`scripts/acquire_natural_earth.py`): the maps are then drawn without neighbours and the log says so."""
    path = core_paths.fetched_raw("natural_earth", "_global") / NATURAL_EARTH_FILE
    if not path.is_file():
        logger.warning(
            "neighbouring countries not drawn: %s is missing (scripts/acquire_natural_earth.py)",
            path,
        )
        return None
    world = gpd.read_file(path).to_crs("EPSG:4326")
    code = next((c for c in ("ADM0_A3", "ISO_A3", "SOV_A3") if c in world.columns), None)
    if code is None:
        return None
    return world[world[code] != iso][["geometry"]]


def _clip_neighbours(neighbours, geometry, extent):
    """The neighbours cut to the window of the map and without the territory itself (the borders of two sources do not agree to the metre)."""
    if neighbours is None:
        return None
    from shapely.geometry import box

    window = box(extent[0] - 1.0, extent[2] - 1.0, extent[1] + 1.0, extent[3] + 1.0)
    out = neighbours.copy()
    out["geometry"] = out.geometry.intersection(window).difference(geometry)
    return out[~out.geometry.is_empty]


@dataclass(frozen=True)
class MapContext:
    """What every map of a country shares, computed once: the contiguous territory, the extent of the maps and the neighbours cut to it.

    The contiguous territory of a large country (a few hundred thousand vertices) takes about a minute to find, so it is not found again for each of the
    sixteen or so maps of a technology.
    """

    polygon: object
    extent: ms.Extent
    neighbours: gpd.GeoDataFrame | None


def map_context(geometry, neighbours: gpd.GeoDataFrame | None) -> MapContext:
    polygon = ms.contiguous_geometry(geometry)
    extent = ms.country_extent(polygon, contiguous=False)
    return MapContext(polygon, extent, _clip_neighbours(neighbours, polygon, extent))


def country_context(iso: str, cell_ids: np.ndarray | None = None) -> MapContext:
    """The context of a country from the GADM 4.1 level 0 mainland file that the pipeline masks with (`gadm41_<ISO3>_0_mainland.shp`) and
    the Natural Earth neighbours; the territory is the mask of the analysis, so that the border of a map is the border of its data.

    Without the file the territory is the union of the `cell_ids` of the country (and the log says so); without them the file is required.
    """
    path = core_paths.fetched_raw("gadm", iso) / f"gadm41_{iso}_0_mainland.shp"
    if path.is_file():
        geometry = gpd.read_file(path).to_crs("EPSG:4326").union_all()
    elif cell_ids is not None:
        logger.warning(
            "the mainland border of %s is missing (%s): the territory is the union of its cells",
            iso,
            path,
        )
        geometry = country_geometry(None, cell_ids)
    else:
        raise FileNotFoundError(f"the mainland border of {iso} is missing: {path}")
    return map_context(geometry, load_neighbours(iso))
