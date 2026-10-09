"""The inventory of existing solar and wind units and where each one falls on the country grid (M-F1-06, M-F7b-01; V-06).

The inventory is validation-only (V-06): only F7b reads it, and nothing computed from it reaches a parameter, a threshold or a
configuration value. A synthetic inventory (`synthetic: true` in its snapshot record, D-F7b-006) is refused in a production run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

from geofrea.core import paths as core_paths

INVENTORY_COLUMNS = (
    "gem_unit_id",
    "tech",
    "status",
    "capacity_mw",
    "start_year",
    "location_accuracy",
    "lat",
    "lon",
)
SNAPSHOT_NAME = "gem_snapshot.json"
OPERATING = "operating"


class InventoryError(RuntimeError):
    """The inventory is missing, has no usable column set, or is synthetic in a production run (A-09)."""


@dataclass(frozen=True)
class Inventory:
    frame: pd.DataFrame
    path: Path
    synthetic: bool


def inventory_path(iso: str) -> Path:
    return core_paths.fetched_raw("gem", iso) / f"gem_solar_wind_{iso}.parquet"


def load_inventory(iso: str, *, production: bool) -> Inventory:
    """The solar and wind units of `iso` with the columns F7b needs.

    Implements: M-F1-06, D-F7b-006.

    Raises:
        InventoryError: the file is absent, lacks a column, has a unit without coordinates or capacity, or is synthetic in a production run.
    """
    path = inventory_path(iso)
    if not path.is_file():
        raise InventoryError(
            f"{iso}: the plant inventory {path} is absent; acquire it with scripts/acquire_gem_trackers.py (V-06: validation only)"
        )
    frame = pd.read_parquet(path)
    missing = [c for c in INVENTORY_COLUMNS if c not in frame.columns]
    if missing:
        raise InventoryError(f"{path.name}: columns missing: {missing}")
    record = path.parent / SNAPSHOT_NAME
    synthetic = bool(
        record.is_file() and json.loads(record.read_text(encoding="utf-8")).get("synthetic")
    )
    if synthetic and production:
        raise InventoryError(
            f"{iso}: the plant inventory is synthetic; a production run refuses it"
        )
    bad = frame[["lat", "lon", "capacity_mw"]].isna().any(axis=1)
    if bad.any():
        raise InventoryError(f"{path.name}: {int(bad.sum())} units without coordinates or capacity")
    return Inventory(frame=frame.reset_index(drop=True), path=path, synthetic=synthetic)


def row_sets(
    frame: pd.DataFrame, vintage_min_start_year: int | None, excluded_accuracy: list[str] | None
) -> dict[str, pd.DataFrame]:
    """The unit sets of the report: every operating unit, and the sensitivity sets whose filter is configured (D-F7b-003).

    A unit with no start year is dropped from the vintage set; a unit with no location accuracy stays in the accuracy set.
    """
    operating = frame[frame["status"].astype(str).str.lower() == OPERATING]
    sets = {"operating": operating}
    if vintage_min_start_year is not None:
        sets["vintage"] = operating[operating["start_year"] >= vintage_min_start_year]
    if excluded_accuracy:
        accuracy = operating["location_accuracy"].astype("string")
        sets["accuracy"] = operating[~accuracy.isin(list(excluded_accuracy)).fillna(False)]
    return sets


def pixel_of_units(
    lat: np.ndarray,
    lon: np.ndarray,
    transform: rasterio.Affine,
    country_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Row, column and whether the unit falls on a pixel of the country grid (inside the raster and its country mask).

    Rows and columns outside the raster are returned as they are computed (they index nothing); use `in_grid` first.
    """
    inverse = ~transform
    col = np.floor(inverse.a * lon + inverse.b * lat + inverse.c).astype("int64")
    row = np.floor(inverse.d * lon + inverse.e * lat + inverse.f).astype("int64")
    height, width = country_mask.shape
    inside = (row >= 0) & (row < height) & (col >= 0) & (col < width)
    in_grid = np.zeros(row.shape, dtype=bool)
    in_grid[inside] = country_mask[row[inside], col[inside]]
    return row, col, in_grid
