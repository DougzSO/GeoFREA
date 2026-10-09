"""The admin1 unit of every cell (M-F3-03, D-F3-012): the GADM level-1 unit that covers the largest area of the cell.

Geometry decides, never a bounding box (CLAUDE.md). A cell is a box of the lattice of the run scale; its overlap with a unit is the
area of their intersection in degrees squared. Within one cell the degree-to-kilometre factors are the same for every unit, so the
ordering of the overlaps is the ordering of the geodesic areas to the accuracy of a cell's width. A cell that is wholly inside a
unit takes it without an intersection (the shortcut that makes the real countries fast); the other cells intersect the units
that touch them. Ties go to the smallest unit identifier. A cell that overlaps no unit is an error (A-09): the cells come from the
in-country pixels, so every one of them has land that a unit of the same country must cover.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely import STRtree

from geofrea.core.constants import CELL_DEG, CELL_ORIGIN_LAT, CELL_ORIGIN_LON

UNIT_ID_COLUMN = "GID_1"
UNIT_NAME_COLUMN = "NAME_1"


class Admin1Error(RuntimeError):
    """The admin1 layer is unusable or a cell has no unit (A-09)."""


def read_units(units: gpd.GeoDataFrame) -> pd.DataFrame:
    """Unit identifiers and names of a GADM level-1 layer, sorted by identifier, with the geometry in degrees (EPSG:4326).

    Raises:
        Admin1Error: the layer lacks the identifier or name column, repeats an identifier, or is empty.
    """
    for column in (UNIT_ID_COLUMN, UNIT_NAME_COLUMN):
        if column not in units.columns:
            raise Admin1Error(f"the admin1 layer has no {column} column")
    if len(units) == 0:
        raise Admin1Error("the admin1 layer has no unit")
    frame = units.to_crs("EPSG:4326")[[UNIT_ID_COLUMN, UNIT_NAME_COLUMN, "geometry"]].rename(
        columns={UNIT_ID_COLUMN: "admin1_id", UNIT_NAME_COLUMN: "admin1_name"}
    )
    frame["admin1_id"] = frame["admin1_id"].astype(str)
    if frame["admin1_id"].duplicated().any():
        raise Admin1Error("the admin1 layer repeats a unit identifier")
    return frame.sort_values("admin1_id").reset_index(drop=True)


def cell_boxes(row: np.ndarray, col: np.ndarray) -> np.ndarray:
    """Shapely boxes (degrees, EPSG:4326) of the cells at lattice `(row, col)`."""
    west = CELL_ORIGIN_LON + np.asarray(col, dtype="float64") * CELL_DEG
    north = CELL_ORIGIN_LAT - np.asarray(row, dtype="float64") * CELL_DEG
    return shapely.box(west, north - CELL_DEG, west + CELL_DEG, north)


def assign_admin1(row: np.ndarray, col: np.ndarray, units: pd.DataFrame) -> np.ndarray:
    """The `admin1_id` of every cell at `(row, col)`: the unit with the largest overlap.

    Implements: M-F3-03.

    Args:
        row: Lattice rows of the cells.
        col: Lattice columns of the cells.
        units: Output of `read_units` (geometry in degrees).

    Returns:
        Array of unit identifiers, object dtype, one per cell.

    Raises:
        Admin1Error: a cell overlaps no unit.
    """
    boxes = cell_boxes(row, col)
    geometries = np.asarray(units.geometry.values, dtype=object)
    parts, owner = shapely.get_parts(geometries, return_index=True)
    tree = STRtree(parts)
    cell_idx, part_idx = tree.query(boxes, predicate="intersects")
    shapely.prepare(parts)
    inside = shapely.contains_properly(parts[part_idx], boxes[cell_idx])
    overlap = np.where(inside, shapely.area(boxes[cell_idx]), np.nan)
    rest = np.flatnonzero(~inside)
    if rest.size:
        overlap[rest] = shapely.area(
            shapely.intersection(boxes[cell_idx[rest]], parts[part_idx[rest]])
        )
    pairs = pd.DataFrame({"cell": cell_idx, "unit": owner[part_idx], "overlap": overlap})
    per_unit = pairs.groupby(["cell", "unit"], as_index=False)["overlap"].sum()
    # the unit rows are sorted by identifier, so the smallest index wins a tie
    per_unit = per_unit.sort_values(["cell", "overlap", "unit"], ascending=[True, False, True])
    best = per_unit.drop_duplicates("cell").set_index("cell")
    if (best["overlap"] <= 0).any() or len(best) != len(boxes):
        missing = int(len(boxes) - int((best["overlap"] > 0).sum()))
        raise Admin1Error(f"{missing} cell(s) overlap no admin1 unit")
    ids = units["admin1_id"].to_numpy(dtype=object)
    return ids[best["unit"].reindex(np.arange(len(boxes))).to_numpy()]
