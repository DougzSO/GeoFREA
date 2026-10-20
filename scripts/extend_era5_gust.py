"""Complete the ERA5 gust product of a country that does not reach the current mask (COMMAND 59).

The annual-maximum product of `acquire_era5_gust.py` was requested for the mask of the day. When the mask grew (COMMAND 55: the contiguous territory of
IND gained the north block and Arunachal Pradesh) the product stopped at the old box and `hazard_context` could not find a native cell for the added
cells. This script requests, for the reference years and with the same product, variable and aggregation, one rectangle that holds every part of the
acquisition box (mask box + 0.5 degree) the product lacks, reduces it to annual maxima over the same polygon, joins it to the existing product on
the native lattice, and reports the continuity of the seam (the cells present in both). The product that was there is kept beside the new one.

    python scripts/extend_era5_gust.py IND --plan      # what would be requested, and the time to expect; no network
    python scripts/extend_era5_gust.py IND             # request, reduce, join, register

Resume-aware: a year file already downloaded (named `<ISO3>_ext_fg10_hourly_bbox_<year>.nc`) is not requested again.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import xarray as xr

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import geopandas as gpd
from dotenv import load_dotenv

from geofrea.core import paths as core_paths
from geofrea.core.constants import REFERENCE_PERIOD
from geofrea.data_acquisition.acquisition_area import (
    acquisition_bbox,
    cds_area,
    native_grid_extent,
    uncovered_boxes,
)
from geofrea.data_acquisition.era5_registry import (
    Era5NativeGrid,
    Era5Registry,
    sha256_file,
)
from geofrea.data_acquisition.fetchers import era5
from geofrea.data_acquisition.fetchers.gadm import fetch_borders

CELL_DEG = 0.25
# the tolerance F4 accepts for the gust (hazards.py: 0.5 degree = 2 native cells; a lattice cell on an island such as Pamban is 0.43 away)
TOL_CELLS = 2.0
# Measured in D-F1-018/D-F1-022: 3 to 16 minutes per request when the queue is short, past 50 when it is not (one watchdog per request).
TYPICAL_MIN_PER_REQUEST = (11, 16)
WORST_MIN_PER_REQUEST = 60


def _load_acquire_module():
    spec = importlib.util.spec_from_file_location(
        "acquire_era5_gust", REPO_ROOT / "scripts" / "acquire_era5_gust.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # a dataclass in the module looks itself up here
    spec.loader.exec_module(mod)
    return mod


def plan(iso: str) -> dict:
    outputs_root = core_paths.outputs_dir()
    border = fetch_borders(outputs_root, iso)
    if border is None:
        raise SystemExit(f"{iso}: no mask polygon")
    mask = gpd.read_file(border).to_crs("EPSG:4326").geometry.union_all()
    mask_bounds = [float(v) for v in mask.bounds]
    registry = Era5Registry.load(core_paths.fetched_raw("era5", "_global") / "era5_registry.json")
    entry = registry.entries.get(f"era5/{iso}/fg10")
    if entry is None or entry.status != "registered" or entry.native_grid is None:
        raise SystemExit(f"{iso}: no registered ERA5 product to extend (use acquire_era5_gust.py)")
    g = entry.native_grid
    have = native_grid_extent(
        g.lat_min, g.lat_max, g.lat_resolution_deg, g.lon_min, g.lon_max, g.lon_resolution_deg
    )
    need = acquisition_bbox(mask_bounds)
    out = {
        "iso": iso,
        "border": str(border),
        "mask_bounds": mask_bounds,
        "have": have,
        "need": need,
    }
    with xr.open_dataset(entry.reduced_path) as ds:
        da = ds["fg10"]
        valid = np.isfinite(da.isel(year=0).values)
        parts = uncovered_boxes(
            mask,
            ds["latitude"].values,
            ds["longitude"].values,
            valid,
            g.lat_resolution_deg,
            overlap_deg=CELL_DEG,
            tol_cells=TOL_CELLS,
        )
    if not parts:
        out.update(covered=True, parts=[], request_box=None)
        return out
    west = min(p[0] for p in parts)
    south = min(p[1] for p in parts)
    east = max(p[2] for p in parts)
    north = max(p[3] for p in parts)
    box = (west, south, east, north)
    start, end = REFERENCE_PERIOD
    n_years = end - start + 1
    cells = round((east - west) / CELL_DEG) * round((north - south) / CELL_DEG)
    have_cells = g.n_lat * g.n_lon
    out.update(
        covered=False,
        parts=parts,
        request_box=box,
        cds_area=cds_area(box),
        requests=n_years,
        cells_per_request=cells,
        share_of_existing_grid=round(cells / have_cells, 2),
        estimate_hours_typical=[round(n_years * m / 60, 1) for m in TYPICAL_MIN_PER_REQUEST],
        estimate_hours_worst=round(n_years * WORST_MIN_PER_REQUEST / 60, 1),
    )
    return out


def _round_coords(ds: xr.Dataset) -> xr.Dataset:
    return ds.assign_coords(
        latitude=np.round(ds["latitude"].values.astype("float64"), 3),
        longitude=np.round(ds["longitude"].values.astype("float64"), 3),
    )


def join_products(existing: Path, extension: Path, out_path: Path) -> dict:
    """Existing values win; the extension fills the cells the existing product lacks. Returns the continuity of the seam."""
    with xr.open_dataset(existing) as a, xr.open_dataset(extension) as b:
        a, b = _round_coords(a.load()), _round_coords(b.load())
        va, vb = a["fg10"], b["fg10"]
        both_lat = np.intersect1d(va["latitude"].values, vb["latitude"].values)
        both_lon = np.intersect1d(va["longitude"].values, vb["longitude"].values)
        sa = va.sel(latitude=both_lat, longitude=both_lon)
        sb = vb.sel(latitude=both_lat, longitude=both_lon)
        overlap = np.isfinite(sa.values) & np.isfinite(sb.values)
        diff = np.abs(sa.values - sb.values)[overlap]
        report = {
            "overlap_cell_years": int(overlap.sum()),
            "overlap_cells": int(overlap.any(axis=0).sum()),
            "mean_abs_diff_ms": float(diff.mean()) if diff.size else None,
            "max_abs_diff_ms": float(diff.max()) if diff.size else None,
            "mean_value_in_overlap_ms": float(sa.values[overlap].mean()) if diff.size else None,
        }
        merged = va.combine_first(vb).astype("float32")
        ds = xr.Dataset({"fg10": merged}, attrs=a.attrs)
        report["cells_with_value_before"] = int(np.isfinite(va.isel(year=0)).sum())
        report["cells_with_value_after"] = int(np.isfinite(merged.isel(year=0)).sum())
        report["grid_after"] = {
            "lat": [float(merged["latitude"].min()), float(merged["latitude"].max())],
            "lon": [float(merged["longitude"].min()), float(merged["longitude"].max())],
        }
        tmp = out_path.with_suffix(".part.nc")
        tmp.unlink(missing_ok=True)
        ds.to_netcdf(tmp)
    tmp.replace(out_path)
    return report


def run(iso: str) -> dict:
    import cdsapi

    acq = _load_acquire_module()
    p = plan(iso)
    if p["covered"]:
        print(f"{iso}: the product already reaches the acquisition box, nothing to do", flush=True)
        return p
    load_dotenv(REPO_ROOT / ".env", override=False)
    client = cdsapi.Client()
    global_dir = core_paths.fetched_raw("era5", "_global")
    country_dir = core_paths.fetched_raw("era5", iso)
    registry_path = global_dir / "era5_registry.json"
    registry = Era5Registry.load(registry_path)
    entry = registry.entries[f"era5/{iso}/fg10"]
    job = era5.Era5Job(country=f"{iso}_ext")
    start, end = REFERENCE_PERIOD
    year_paths: list[Path] = []
    failed: dict[str, str] = {}
    for year in range(start, end + 1):
        final = global_dir / f"{job.country}_fg10_hourly_bbox_{year}.nc"
        if final.exists():
            print(f"[skip] {job.key}/{year}: already downloaded", flush=True)
            year_paths.append(final)
            continue
        t0 = time.time()
        try:
            path = acq._download_year_with_retries(client, job, year, p["cds_area"], global_dir)
        except Exception as exc:  # noqa: BLE001 -- recorded, the join is refused below
            failed[str(year)] = f"{type(exc).__name__}: {exc}"
            print(f"[PERMANENT FAILURE] {job.key}/{year}: {failed[str(year)]}", flush=True)
            continue
        print(
            f"[ok] {job.key}/{year}: {time.time() - t0:.0f}s, {path.stat().st_size} bytes",
            flush=True,
        )
        year_paths.append(path)
    if failed:
        raise SystemExit(f"{iso}: years missing {sorted(failed)}; the product is left as it was")

    ext_path = country_dir / f"{iso}_fg10_annual_max_ext.nc"
    era5.write_annual_maxima_incremental(
        year_paths=year_paths,
        country_polygon_path=Path(p["border"]),
        out_path=ext_path,
        work_dir=global_dir / "_annual_ckpt" / f"{iso}_ext",
        label=f"{iso}_ext",
    )
    reduced = Path(entry.reduced_path)
    backup = reduced.with_name(reduced.stem + ".before_extension" + reduced.suffix)
    if not backup.exists():
        shutil.copy2(reduced, backup)
    report = join_products(backup, ext_path, reduced)
    grid = era5.read_native_grid(reduced)
    registry.entries[f"era5/{iso}/fg10"] = entry.model_copy(
        update={
            "source_path": str(reduced),
            "source_sha256": sha256_file(reduced),
            "reduced_path": str(reduced),
            "reduced_sha256": sha256_file(reduced),
            "native_grid": Era5NativeGrid(
                lat_resolution_deg=grid.lat_resolution_deg,
                lon_resolution_deg=grid.lon_resolution_deg,
                lat_min=grid.lat_min,
                lat_max=grid.lat_max,
                lon_min=grid.lon_min,
                lon_max=grid.lon_max,
                n_lat=grid.n_lat,
                n_lon=grid.n_lon,
            ),
        }
    )
    registry.save(registry_path)
    out = {"plan": p, "seam": report, "backup": str(backup), "extension": str(ext_path)}
    (country_dir / f"{iso}_fg10_extension_report.json").write_text(
        json.dumps(out, indent=1, default=str), encoding="utf-8"
    )
    print(json.dumps(report, indent=1), flush=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("iso", nargs="+")
    ap.add_argument(
        "--plan", action="store_true", help="print the plan and the time estimate; no network"
    )
    args = ap.parse_args()
    for iso in args.iso:
        if args.plan:
            print(json.dumps(plan(iso), indent=1, default=str))
        else:
            run(iso)


if __name__ == "__main__":
    main()
