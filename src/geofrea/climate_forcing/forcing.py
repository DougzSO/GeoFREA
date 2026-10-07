"""Per-cell change factors for every member: `forcing.parquet` (M-F4-03, M-F4-04, M-F4-06).

For each GCM the factors are computed on its native grid from monthly climatologies (M-F4-03) and then
bilinearly interpolated to the 0.05 degree cell centers (M-F4-04). The interpolation reads the GLOBAL files
(subset to the country bounding box plus a margin), not the polygon crops of F1: a crop keeps only native cells whose
centers lie inside the polygon, so near a border the four cells around a cell center are missing and the
interpolation would return NaN there.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import shapely
import xarray as xr

from geofrea.climate_forcing.change_factors import FACTOR_DEFINITIONS, bilinear_to_points, compute_change_factor
from geofrea.climate_forcing.members import REFERENCE_WINDOW, VARIABLES, Gcm, Member, MemberResolutionError
from geofrea.core.constants import CELL_DEG, CELL_ORIGIN_LAT, CELL_ORIGIN_LON
from geofrea.data_acquisition.cmip6_registry import Cmip6Registry
from geofrea.land_eligibility.cells import cell_center, cell_id

_MARGIN_NATIVE_CELLS = 3


class ForcingGapError(ValueError):
    """A cell has no valid change factor (NaN after interpolation); never filled silently (A-09)."""


def country_cells(mainland) -> pd.DataFrame:
    """Lattice cells (0.05 degree, global ids) that intersect the mainland polygon(s).

    Args:
        mainland: GeoDataFrame in EPSG:4326 holding the mainland polygon(s).

    Returns:
        DataFrame with `cell_id`, `lat_c`, `lon_c`, sorted by `cell_id`.
    """
    geom = shapely.union_all(mainland.geometry.values)
    xmin, ymin, xmax, ymax = geom.bounds
    row0 = int(np.floor((CELL_ORIGIN_LAT - ymax) / CELL_DEG))
    row1 = int(np.floor((CELL_ORIGIN_LAT - ymin) / CELL_DEG))
    col0 = int(np.floor((xmin - CELL_ORIGIN_LON) / CELL_DEG))
    col1 = int(np.floor((xmax - CELL_ORIGIN_LON) / CELL_DEG))
    rows, cols = np.meshgrid(np.arange(row0, row1 + 1), np.arange(col0, col1 + 1), indexing="ij")
    rows, cols = rows.ravel(), cols.ravel()
    west = CELL_ORIGIN_LON + cols * CELL_DEG
    north = CELL_ORIGIN_LAT - rows * CELL_DEG
    boxes = shapely.box(west, north - CELL_DEG, west + CELL_DEG, north)
    shapely.prepare(geom)
    # a cell that only touches the polygon along an edge shares no area with the country: not included
    keep = shapely.intersects(boxes, geom) & ~shapely.touches(boxes, geom)
    rows, cols = rows[keep], cols[keep]
    lat_c, lon_c = cell_center(rows, cols)
    out = pd.DataFrame({"cell_id": cell_id(rows, cols), "lat_c": lat_c, "lon_c": lon_c})
    return out.sort_values("cell_id").reset_index(drop=True)


def _subset(da: xr.DataArray, lat_range: tuple[float, float], lon_range: tuple[float, float]) -> xr.DataArray:
    """Native-grid subset covering the ranges plus a margin; lon_range in the file's own convention."""
    lat = da["lat"].values
    lon = da["lon"].values
    dlat = float(np.abs(np.diff(np.sort(lat))).mean())
    dlon = float(np.abs(np.diff(np.sort(lon))).mean())
    lat_sel = (lat >= lat_range[0] - _MARGIN_NATIVE_CELLS * dlat) & (lat <= lat_range[1] + _MARGIN_NATIVE_CELLS * dlat)
    lon_sel = (lon >= lon_range[0] - _MARGIN_NATIVE_CELLS * dlon) & (lon <= lon_range[1] + _MARGIN_NATIVE_CELLS * dlon)
    return da.isel(lat=np.flatnonzero(lat_sel), lon=np.flatnonzero(lon_sel))


def _to_file_lon(lon_range: tuple[float, float], file_lon: np.ndarray) -> tuple[float, float]:
    lo, hi = lon_range
    if float(file_lon.max()) > 180.0:
        lo, hi = (lo + 360.0 if lo < 0 else lo), (hi + 360.0 if hi < 0 else hi)
    if lo > hi:
        raise MemberResolutionError("a bounding box that crosses the 0/360 seam is not supported")
    return lo, hi


def _load_variable(entry, variable: str, lat_range, lon_range) -> xr.DataArray:
    with xr.open_dataset(entry.global_path) as ds:
        da = ds[variable]
        lon_file = _to_file_lon(lon_range, ds["lon"].values)
        return _subset(da, lat_range, lon_file).load()


def member_factor_fields(
    registry: Cmip6Registry, gcm: Gcm, experiment: str, window: tuple[int, int], lat_range, lon_range
) -> dict[str, xr.DataArray]:
    """Native-grid change-factor fields (delta_rsds, delta_wind, dT) of one GCM, scenario and window."""
    fields: dict[str, xr.DataArray] = {}
    for variable in VARIABLES:
        hist = registry.entries[f"cmip6/{gcm.cds_name}/historical/{variable}"]
        scen = registry.entries[f"cmip6/{gcm.cds_name}/{experiment}/{variable}"]
        column = FACTOR_DEFINITIONS[variable][0]
        fields[column] = compute_change_factor(
            variable,
            _load_variable(hist, variable, lat_range, lon_range),
            _load_variable(scen, variable, lat_range, lon_range),
            REFERENCE_WINDOW,
            window,
        )
    return fields


def forcing_frames(
    cells: pd.DataFrame, members: list[Member], registry: Cmip6Registry
) -> Iterator[pd.DataFrame]:
    """One DataFrame per member (`cell_id`, `member`, `delta_rsds`, `dT`, `delta_wind`), in member order.

    Raises:
        ForcingGapError: if any cell gets a NaN factor.
    """
    lat_range = (float(cells["lat_c"].min()), float(cells["lat_c"].max()))
    lon_range = (float(cells["lon_c"].min()), float(cells["lon_c"].max()))
    lat, lon = cells["lat_c"].to_numpy(), cells["lon_c"].to_numpy()
    cache: dict[tuple[str, str, tuple[int, int]], dict[str, np.ndarray]] = {}
    for m in members:
        if m.gcm is None:
            yield pd.DataFrame(
                {
                    "cell_id": cells["cell_id"].to_numpy(),
                    "member": m.member_id,
                    "delta_rsds": np.float32(1.0),
                    "dT": np.float32(0.0),
                    "delta_wind": np.float32(1.0),
                }
            )
            continue
        key = (m.gcm.cds_name, m.experiment, m.window)
        if key not in cache:
            fields = member_factor_fields(registry, m.gcm, m.experiment, m.window, lat_range, lon_range)
            cache.clear()  # keep memory bounded: one member's interpolated fields at a time
            cache[key] = {col: bilinear_to_points(field, lat, lon) for col, field in fields.items()}
        values = cache[key]
        frame = pd.DataFrame(
            {
                "cell_id": cells["cell_id"].to_numpy(),
                "member": m.member_id,
                "delta_rsds": values["delta_rsds"].astype(np.float32),
                "dT": values["dT"].astype(np.float32),
                "delta_wind": values["delta_wind"].astype(np.float32),
            }
        )
        bad = frame[["delta_rsds", "dT", "delta_wind"]].isna().any(axis=1)
        if bad.any():
            raise ForcingGapError(f"{m.member_id}: {int(bad.sum())} of {len(frame)} cells have no valid change factor")
        yield frame


def write_forcing(frames: Iterator[pd.DataFrame], out_path: Path) -> int:
    """Stream the per-member frames into one Parquet file; return the number of rows written."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = None
    n = 0
    try:
        for frame in frames:
            frame["member"] = frame["member"].astype("category")
            table = pa.Table.from_pandas(frame, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(out_path, table.schema, compression="zstd")
            writer.write_table(table.cast(writer.schema))
            n += len(frame)
    finally:
        if writer is not None:
            writer.close()
    return n
