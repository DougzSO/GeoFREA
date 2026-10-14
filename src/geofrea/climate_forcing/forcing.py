"""Per-cell change factors for every member: `forcing.parquet` (M-F4-03, M-F4-04, M-F4-06).

For each GCM the factors are computed on its native grid from monthly climatologies (M-F4-03) and then
bilinearly interpolated to the cell centers of the run scale (M-F4-04, 0.05 degree by default). The interpolation reads the GLOBAL files
(subset to the country bounding box plus a margin), not the polygon crops of F1: a crop keeps only native cells whose
centers lie inside the polygon, so near a border the four cells around a cell center are missing and the
interpolation would return NaN there.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import rasterio
import xarray as xr

from geofrea.climate_forcing.change_factors import (
    FACTOR_DEFINITIONS,
    bilinear_to_points,
    compute_change_factor,
)
from geofrea.climate_forcing.members import (
    VARIABLES,
    Gcm,
    Member,
    MemberResolutionError,
)
from geofrea.climate_forcing.table_schemas import CLIMATE_TABLE_SCHEMA_VERSION, ForcingRow
from geofrea.core.constants import REFERENCE_PERIOD
from geofrea.core.tables import table_metadata, validate_columns
from geofrea.data_acquisition.cmip6_registry import Cmip6Registry
from geofrea.land_eligibility.cells import cell_center, cell_id, lattice_window, pad_to_window

_MARGIN_NATIVE_CELLS = 3


class ForcingGapError(ValueError):
    """A cell has no valid change factor (NaN after interpolation); never filled silently (A-09)."""


def country_cells(mask_path: Path) -> pd.DataFrame:
    """Lattice cells of the active scale (0.05 degree by default, global ids) that hold at least one in-country pixel of the F2a grid.

    This is the definition F3 uses (`aggregate_to_cells` keeps a cell when its in-country area is positive), so the
    forcing covers exactly the cells F3 can later make candidates. It reads the F2a aligned raster's own valid
    pixels instead of intersecting boxes with the country polygon: on IND's coastline (millions of vertices) the
    polygon test did not finish in 40 minutes, the raster test takes seconds.

    Args:
        mask_path: An aligned F2a raster whose valid pixels are the in-country pixels (e.g. `<ISO3>_grid_aligned.tif`).

    Returns:
        DataFrame with `cell_id`, `lat_c`, `lon_c`, sorted by `cell_id`.
    """
    with rasterio.open(mask_path) as src:
        band = src.read(1)
        valid = (
            np.isfinite(band) if src.nodata is None else (np.isfinite(band) & (band != src.nodata))
        )
        transform, height, width = src.transform, src.height, src.width
    window = lattice_window(transform, height, width)
    k = window.k
    padded = pad_to_window(valid, window, False)
    any_valid = padded.reshape(window.n_rows, k, window.n_cols, k).any(axis=(1, 3))
    r, c = np.nonzero(any_valid)
    rows, cols = r + window.row0, c + window.col0
    lat_c, lon_c = cell_center(rows, cols)
    out = pd.DataFrame({"cell_id": cell_id(rows, cols), "lat_c": lat_c, "lon_c": lon_c})
    return out.sort_values("cell_id").reset_index(drop=True)


def _subset(
    da: xr.DataArray, lat_range: tuple[float, float], lon_range: tuple[float, float]
) -> xr.DataArray:
    """Native-grid subset covering the ranges plus a margin; lon_range in the file's own convention."""
    lat = da["lat"].values
    lon = da["lon"].values
    dlat = float(np.abs(np.diff(np.sort(lat))).mean())
    dlon = float(np.abs(np.diff(np.sort(lon))).mean())
    lat_sel = (lat >= lat_range[0] - _MARGIN_NATIVE_CELLS * dlat) & (
        lat <= lat_range[1] + _MARGIN_NATIVE_CELLS * dlat
    )
    lon_sel = (lon >= lon_range[0] - _MARGIN_NATIVE_CELLS * dlon) & (
        lon <= lon_range[1] + _MARGIN_NATIVE_CELLS * dlon
    )
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


def isolated_native_cells(field: xr.DataArray, threshold: float) -> xr.DataArray:
    """Boolean native-grid field: True where the value departs from the median of the eight neighbours by more than `threshold`.

    Implements: M-F4-06 (V-82). The comparison is made on the subset the forcing reads (country box plus margin); the cells at its
    edge have fewer neighbours (NaN-padded) and are tested against those. Nothing is corrected.
    """
    values = np.asarray(field.values, dtype="float64")
    padded = np.pad(values, 1, constant_values=np.nan)
    h, w = values.shape
    neighbours = np.stack(
        [
            padded[1 + di : 1 + di + h, 1 + dj : 1 + dj + w]
            for di in (-1, 0, 1)
            for dj in (-1, 0, 1)
            if (di, dj) != (0, 0)
        ]
    )
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter(
            "ignore", RuntimeWarning
        )  # a cell with no valid neighbour has no median
        median = np.nanmedian(neighbours, axis=0)
    flagged = np.isfinite(median) & np.isfinite(values) & (np.abs(values - median) > threshold)
    return xr.DataArray(flagged, coords=field.coords, dims=field.dims)


def member_factor_fields(
    registry: Cmip6Registry,
    gcm: Gcm,
    experiment: str,
    window: tuple[int, int],
    lat_range,
    lon_range,
    wind_neighbourhood: int | None = None,
    dt_isolated_threshold_k: float | None = None,
) -> dict[str, xr.DataArray]:
    """Native-grid change-factor fields (delta_rsds, delta_wind, dT) of one GCM, scenario and window.

    `wind_neighbourhood` applies OQ-042 option A to `delta_wind` only: the ratio of n x n neighbourhood means, so a
    native cell whose reference wind is near zero does not make the ratio explode. `delta_rsds` and `dT` keep the
    per-cell definition. A GCM without a wind channel (M-F4-02 item 6) has no `delta_wind` field: its wind file is not read.
    With `dt_isolated_threshold_k` the result also holds `dT_isolated` (1.0 where the native dT is isolated, see `isolated_native_cells`).
    """
    fields: dict[str, xr.DataArray] = {}
    for variable in VARIABLES:
        if variable == "sfcWind" and not gcm.wind_channel:
            continue
        hist = registry.entries[f"cmip6/{gcm.cds_name}/historical/{variable}"]
        scen = registry.entries[f"cmip6/{gcm.cds_name}/{experiment}/{variable}"]
        column = FACTOR_DEFINITIONS[variable][0]
        fields[column] = compute_change_factor(
            variable,
            _load_variable(hist, variable, lat_range, lon_range),
            _load_variable(scen, variable, lat_range, lon_range),
            REFERENCE_PERIOD,
            window,
            neighbourhood=wind_neighbourhood if variable == "sfcWind" else None,
        )
    if dt_isolated_threshold_k is not None:
        fields["dT_isolated"] = isolated_native_cells(fields["dT"], dt_isolated_threshold_k).astype(
            "float64"
        )
    return fields


def forcing_frames(
    cells: pd.DataFrame,
    members: list[Member],
    registry: Cmip6Registry,
    wind_neighbourhood: int | None = None,
    wind_valid_range: tuple[float, float] | None = None,
    masked_sink: list[pd.DataFrame] | None = None,
    dt_isolated_threshold_k: float | None = None,
) -> Iterator[pd.DataFrame]:
    """One DataFrame per member (`cell_id`, `member`, `delta_rsds`, `dT`, `delta_wind`, `dT_isolated_native_cell`), in member order.

    `delta_wind` is NaN where the wind ratio is not available, and only there:

      - the member's GCM has no wind channel (M-F4-02 item 6): every cell, declared by `channels.resource_wind: false` in `members.yaml`;
      - with `wind_valid_range` (OQ-042, option C) the cell-member's ratio lies outside the range: it is masked, listed in `masked_sink`
        (`cell_id`, `member`, `delta_wind`) with the rejected value, and its row is KEPT with a NaN `delta_wind`, so that a technology
        that does not read the wind ratio never loses the cell-member because of wind. Nothing is replaced by another value.

    `dT_isolated_native_cell` is True where a native cell that the cell's interpolation reads is flagged by `isolated_native_cells` (False
    when no threshold is given). Nothing is corrected.

    Raises:
        ForcingGapError: if any cell gets a NaN factor that is not a declared absence.
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
                    "dT_isolated_native_cell": False,
                }
            )
            continue
        key = (m.gcm.cds_name, m.experiment, m.window)
        if key not in cache:
            fields = member_factor_fields(
                registry,
                m.gcm,
                m.experiment,
                m.window,
                lat_range,
                lon_range,
                wind_neighbourhood,
                dt_isolated_threshold_k,
            )
            cache.clear()  # keep memory bounded: one member's interpolated fields at a time
            cache[key] = {col: bilinear_to_points(field, lat, lon) for col, field in fields.items()}
        values = cache[key]
        n = len(cells)
        delta_wind = values.get("delta_wind", np.full(n, np.nan))
        isolated = values.get("dT_isolated")
        frame = pd.DataFrame(
            {
                "cell_id": cells["cell_id"].to_numpy(),
                "member": m.member_id,
                "delta_rsds": values["delta_rsds"].astype(np.float32),
                "dT": values["dT"].astype(np.float32),
                "delta_wind": delta_wind.astype(np.float32),
                "dT_isolated_native_cell": (isolated > 0)
                if isolated is not None
                else np.zeros(n, dtype=bool),
            }
        )
        required = ["delta_rsds", "dT"] + (["delta_wind"] if m.gcm.wind_channel else [])
        bad = frame[required].isna().any(axis=1)
        if bad.any():
            raise ForcingGapError(
                f"{m.member_id}: {int(bad.sum())} of {len(frame)} cells have no valid change factor"
            )
        if wind_valid_range is not None and m.gcm.wind_channel:
            lo, hi = wind_valid_range
            invalid = (frame["delta_wind"] < lo) | (frame["delta_wind"] > hi)
            if invalid.any():
                if masked_sink is not None:
                    masked_sink.append(
                        frame.loc[invalid, ["cell_id", "member", "delta_wind"]].copy()
                    )
                frame.loc[invalid, "delta_wind"] = np.float32("nan")
        yield frame


def write_forcing(frames: Iterator[pd.DataFrame], out_path: Path) -> int:
    """Stream the per-member frames into one Parquet file; return the number of rows written."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = None
    n = 0
    try:
        for frame in frames:
            frame["member"] = frame["member"].astype("category")
            validate_columns(frame, ForcingRow)
            table = pa.Table.from_pandas(frame, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(
                    out_path,
                    table_metadata(table.schema, CLIMATE_TABLE_SCHEMA_VERSION, ForcingRow),
                    compression="zstd",
                )
            writer.write_table(table.cast(writer.schema))
            n += len(frame)
    finally:
        if writer is not None:
            writer.close()
    return n


class ForcingContractError(ValueError):
    """The forcing a consumer reads breaks the contract: a factor out of range or an undeclared absence (A-09)."""


def assert_forcing_usable(
    forcing: pd.DataFrame,
    masked: pd.DataFrame,
    candidate_cell_ids,
    members: list[str],
    wind_valid_range: tuple[float, float],
    channels: tuple[str, ...] = ("resource_wind",),
) -> None:
    """Guard F5 calls before using the forcing of a country (OQ-042 option C; D-F4-004; M-F4-07).

    `members` are the members that carry the `channels` the technology reads (M-F4-06); a member without a channel is absent by
    declaration in `members.yaml` and is not asked for. Raises ForcingContractError if (1) a candidate cell-member has no row in
    `forcing`, (2) a factor a channel reads is NaN where it is not a declared mask, or (3) a `delta_wind` read by the wind channel is
    outside `wind_valid_range`. A row with a NaN `delta_wind` is valid for a technology that does not read wind.
    """
    lo, hi = wind_valid_range
    cand = pd.Index(np.asarray(candidate_cell_ids)).unique()
    f = forcing[forcing["cell_id"].isin(cand) & forcing["member"].astype(str).isin(members)]
    expected = len(cand) * len(members)
    present = f[["cell_id", "member"]].drop_duplicates()
    if len(present) != expected:
        raise ForcingContractError(
            f"{expected - len(present)} candidate cell-members have no row in forcing.parquet (a row is kept for every cell-member; "
            "only the wind ratio can be NaN, declared in forcing_masked.parquet)"
        )
    for channel, column in (("resource_rsds", "delta_rsds"), ("resource_tas", "dT")):
        if channel in channels and f[column].isna().any():
            raise ForcingContractError(
                f"{int(f[column].isna().sum())} candidate cell-members have a NaN {column}"
            )
    if "resource_wind" in channels:
        wind = f["delta_wind"]
        nan = f.loc[wind.isna(), ["cell_id", "member"]].assign(
            member=lambda d: d["member"].astype(str)
        )
        declared = masked.loc[
            masked["cell_id"].isin(cand) & masked["member"].astype(str).isin(members),
            ["cell_id", "member"],
        ].assign(member=lambda d: d["member"].astype(str))
        undeclared = nan.merge(declared, how="left", indicator=True)
        undeclared = undeclared[undeclared["_merge"] == "left_only"]
        if len(undeclared):
            raise ForcingContractError(
                f"{len(undeclared)} candidate cell-members have a NaN delta_wind that forcing_masked.parquet does not declare"
            )
        bad = f[(wind < lo) | (wind > hi)]
        if len(bad):
            raise ForcingContractError(
                f"{len(bad)} candidate cell-members have delta_wind outside {wind_valid_range} "
                f"(e.g. {bad['member'].astype(str).iloc[0]}, {bad['delta_wind'].max():.2f}); mask them (OQ-042) before F5"
            )
