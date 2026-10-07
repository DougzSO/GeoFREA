"""Hazard context indicators per cell and member (M-F4-05, M-F4-06; D-F4-001, D-F4-004, D-F4-009).

C2/C3 hazards enter F5/F6 quantitatively only with a loss function of evidence Tier 1 or 2 (OQ-007). Until then they
are per-cell, per-member CONTEXT indicators in `hazard_context.parquet` and never enter regret or satisficing.

Indicators (absolute values, bias-adjusted ISIMIP3b daily data, D-F4-001):
  - `tx35_days`, `tx40_days`: mean annual number of days with tasmax >= 35 / 40 degC (extreme heat, C2).
  - `rx5day_mm`: mean annual maximum of the 5-day precipitation total (C3).
  - `wet_p95_exceed_freq`: share of wet days (>= 1 mm) above the GCM's own 1995-2014 wet-day 95th percentile (C3).
  - `gust_mean_annual_max_ms`: mean of the annual maxima of the ERA5 10 m gust, scenario-invariant (C2, D-F4-009).
The `*_ref` columns are the same GCM's 1995-2014 values, so a change can be read from one row.

Definitions adapted from CRAEI per A-11 (see the provenance comments above each function).
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy.spatial import cKDTree

logger = logging.getLogger(__name__)

KELVIN_OFFSET_C = 273.15  # CRAEI hazards/pet.py KELVIN_OFFSET_C
PR_FLUX_TO_MM_PER_DAY = 86400.0  # kg m-2 s-1 -> mm d-1 (CRAEI hazards/loading.py)
WET_DAY_THRESHOLD_MM = 1.0  # CRAEI hazards/precip.py WET_DAY_THRESHOLD_MM
HEAT_THRESHOLDS_C = (35.0, 40.0)  # CRAEI config/params.yaml heat_tx35/tx40_threshold_c (tier 1, IPCC AR6 Atlas)
WET_DAY_PERCENTILE = 95.0
REFERENCE_YEARS = (1995, 2014)  # S-05

INDICATOR_COLUMNS = (
    "tx35_days",
    "tx35_days_ref",
    "tx40_days",
    "tx40_days_ref",
    "rx5day_mm",
    "rx5day_mm_ref",
    "wet_p95_exceed_freq",
    "wet_days_per_year_ref",
    "gust_mean_annual_max_ms",
)


class HazardDataError(ValueError):
    """Hazard input is missing, incomplete or does not cover the cells (A-09: fail loud, never filled)."""


def _years(da: xr.DataArray, start: int, end: int) -> xr.DataArray:
    window = da.sel(time=slice(f"{start}-01-01", f"{end}-12-31"))
    expected_years = end - start + 1
    got = np.unique(window["time"].dt.year.values)
    if len(got) != expected_years:
        raise HazardDataError(f"expected {expected_years} years {start}-{end}, found {len(got)}")
    return window


# Adapted from CRAEI (https://github.com/ -- local baseline CRAEI_BASELINE_DIR), commit
# 76c9f8212e3bba0fd138409a809156f6fc0b77b1, src/craei/hazards/heat.py::annual_hot_day_counts.
# Adaptation: pandas groupby over a long frame -> xarray over the (time, lat, lon) grid; same definition
# (count of days with tasmax >= threshold per year), averaged over the years of the window.
def mean_annual_hot_days(tasmax_c: xr.DataArray, threshold_c: float) -> xr.DataArray:
    """Mean over years of the annual count of days with `tasmax_c` >= `threshold_c`; dims (lat, lon).

    Implements: M-F4-05 (C2 extreme heat context indicator).
    """
    counts = (tasmax_c >= threshold_c).groupby("time.year").sum("time")
    return counts.mean("year").astype("float32")


# Adapted from CRAEI commit 76c9f8212e3bba0fd138409a809156f6fc0b77b1, src/craei/hazards/precip.py::annual_rx5day.
# Adaptation: pandas rolling by group -> xarray rolling(time=5).sum() on the grid; annual maximum, then the mean
# over the years of the window.
def mean_annual_rx5day(pr_mm: xr.DataArray) -> xr.DataArray:
    """Mean over years of the annual maximum 5-day precipitation total (mm); dims (lat, lon).

    Implements: M-F4-05 (C3 extreme precipitation context indicator).
    """
    roll5 = pr_mm.rolling(time=5).sum()
    annual_max = roll5.groupby("time.year").max("time")
    return annual_max.mean("year").astype("float32")


# Adapted from CRAEI commit 76c9f8212e3bba0fd138409a809156f6fc0b77b1, src/craei/hazards/precip.py::wet_day_p95.
# Adaptation: per-cell percentile of wet days on the grid; computed on the reference period only (CRAEI rule 4:
# the threshold cannot see future rows).
def wet_day_percentile(pr_ref_mm: xr.DataArray, percentile: float = WET_DAY_PERCENTILE) -> xr.DataArray:
    """Per-cell `percentile` of the wet-day (>= 1 mm) precipitation of the reference period."""
    wet = pr_ref_mm.where(pr_ref_mm >= WET_DAY_THRESHOLD_MM)
    return wet.quantile(percentile / 100.0, dim="time", skipna=True).drop_vars("quantile").astype("float32")


# Adapted from CRAEI commit 76c9f8212e3bba0fd138409a809156f6fc0b77b1, src/craei/hazards/precip.py::exceedance_frequency.
# Adaptation: pooled counts over the whole window (a single ratio, not an average of yearly ratios), on the grid.
def wet_day_exceedance_frequency(pr_mm: xr.DataArray, p95_mm: xr.DataArray) -> xr.DataArray:
    """Share of wet days above each cell's baseline P95, pooled over the window; NaN where no wet day exists."""
    wet = pr_mm >= WET_DAY_THRESHOLD_MM
    n_wet = wet.sum("time")
    n_exceed = (wet & (pr_mm > p95_mm)).sum("time")
    return (n_exceed / n_wet.where(n_wet > 0)).astype("float32")


def to_celsius(tasmax_kelvin: xr.DataArray) -> xr.DataArray:
    return tasmax_kelvin - KELVIN_OFFSET_C


def to_mm_per_day(pr_flux: xr.DataArray) -> xr.DataArray:
    return pr_flux * PR_FLUX_TO_MM_PER_DAY


def sample_nearest(
    field: xr.DataArray,
    lat: np.ndarray,
    lon: np.ndarray,
    max_distance_deg: float,
    skip_nan: bool = True,
    return_distance: bool = False,
):
    """Value of the nearest native cell for each (lat, lon); raises if any is farther than the tolerance.

    Counts and extremes are not interpolated (bilinear would blend thresholds). With `skip_nan` (ERA5, whose crop
    is NaN outside the country polygon) the nearest cell WITH a value is used; without it (ISIMIP3b, a full box)
    the nearest cell is used as is and a NaN there stays NaN. A cell with no native cell within `max_distance_deg`
    is an error, never filled.
    """
    la, lo = np.meshgrid(field["lat"].values, field["lon"].values, indexing="ij")
    values = field.transpose("lat", "lon").values
    keep = np.isfinite(values) if skip_nan else np.ones(values.shape, dtype=bool)
    if not keep.any():
        raise HazardDataError("the native field has no valid cell")
    tree = cKDTree(np.column_stack([la[keep], lo[keep]]))
    dist, idx = tree.query(np.column_stack([lat, lon]))
    if (dist > max_distance_deg).any():
        raise HazardDataError(
            f"{int((dist > max_distance_deg).sum())} cells have no native cell within {max_distance_deg} degrees"
        )
    if return_distance:
        return values[keep][idx], dist
    return values[keep][idx]


def era5_gust_mean_annual_max(era5_annual_max: Path, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Mean over the 20 annual maxima of the ERA5 gust at the nearest valid ERA5 cell (D-F4-009).

    Implements: M-F1-05, M-F4-05 (C2 extreme wind context, scenario-invariant).
    """
    with xr.open_dataset(era5_annual_max) as ds:
        field = ds["fg10"].mean("year").rename({"latitude": "lat", "longitude": "lon"}).load()
    # Tolerance 2 native cells (0.5 degree): the ERA5 crop keeps only cells whose center lies inside the country
    # polygon, so a lattice cell on a narrow coastal strip or an island (IND, Pamban, 0.43 degree from the nearest
    # valid cell) has no valid cell within one. Cells beyond one native cell are counted in the log, never hidden.
    values, dist = sample_nearest(field, lat, lon, max_distance_deg=0.5, return_distance=True)
    n_far = int((dist > 0.25).sum())
    if n_far:
        logger.warning("ERA5 gust: %d of %d cells use a native cell more than 0.25 degree away", n_far, len(lat))
    return values


def load_daily(path: Path, variable: str, start: int, end: int) -> xr.DataArray:
    """One ISIMIP3b crop, daily, restricted to [start, end] with every year present."""
    with xr.open_dataset(path) as ds:
        return _years(ds[variable], start, end).load()


def hazard_fields(
    historical_tasmax: Path, scenario_tasmax: Path, historical_pr: Path, scenario_pr: Path, window: tuple[int, int]
) -> dict[str, xr.DataArray]:
    """Native-grid indicator fields (window and reference) for one GCM and scenario."""
    ref0, ref1 = REFERENCE_YEARS
    tx_ref = to_celsius(load_daily(historical_tasmax, "tasmax", ref0, ref1))
    tx_win = to_celsius(load_daily(scenario_tasmax, "tasmax", *window))
    pr_ref = to_mm_per_day(load_daily(historical_pr, "pr", ref0, ref1))
    pr_win = to_mm_per_day(load_daily(scenario_pr, "pr", *window))
    p95 = wet_day_percentile(pr_ref)
    n_years_ref = ref1 - ref0 + 1
    return {
        "tx35_days": mean_annual_hot_days(tx_win, 35.0),
        "tx35_days_ref": mean_annual_hot_days(tx_ref, 35.0),
        "tx40_days": mean_annual_hot_days(tx_win, 40.0),
        "tx40_days_ref": mean_annual_hot_days(tx_ref, 40.0),
        "rx5day_mm": mean_annual_rx5day(pr_win),
        "rx5day_mm_ref": mean_annual_rx5day(pr_ref),
        "wet_p95_exceed_freq": wet_day_exceedance_frequency(pr_win, p95),
        "wet_days_per_year_ref": ((pr_ref >= WET_DAY_THRESHOLD_MM).sum("time") / n_years_ref).astype("float32"),
    }


def hazard_frame(
    cells: pd.DataFrame, member_id: str, fields: dict[str, xr.DataArray], gust: np.ndarray, max_distance_deg: float
) -> pd.DataFrame:
    """One member's hazard context rows for `cells` (nearest valid native cell per indicator)."""
    lat, lon = cells["lat_c"].to_numpy(), cells["lon_c"].to_numpy()
    data = {"cell_id": cells["cell_id"].to_numpy(), "member": member_id}
    for name, field in fields.items():
        sampled = sample_nearest(field, lat, lon, max_distance_deg, skip_nan=False).astype(np.float32)
        if name != "wet_p95_exceed_freq" and not np.isfinite(sampled).all():
            raise HazardDataError(f"{member_id}: indicator {name} is NaN in {int((~np.isfinite(sampled)).sum())} cells")
        data[name] = sampled
    data["gust_mean_annual_max_ms"] = gust.astype(np.float32)
    frame = pd.DataFrame(data)
    # wet_p95_exceed_freq is NaN only where a cell has no wet day in the window: a declared property, not a gap
    return frame[["cell_id", "member", *INDICATOR_COLUMNS]]
