"""Fill the cells of the country mask that the ERA5 annual-maximum product leaves empty, from a small hourly download (COMMAND 65 follow-up, D-F1-031).

After the extension of IND (`era5_ext_queue.py`) two cells of the mask were still empty in every year: (10.0 N, 76.25 E) and (23.75 N, 68.5 E). They were
empty in the earlier product as well and lie outside the rectangle of the extension. Their hourly `fg10` was requested in a small box
(`IND_patch_fg10_hourly_<years>_<job>.nc`, 1995-2014, two years per request) and the annual maximum of each cell is written into the product.

    python scripts/patch_era5_cells.py IND

The method is checked before anything is written: in the cells of the box that the product already holds, the annual maximum of the patch files must equal the product
(tolerance 1e-4 m/s, float32). The product is copied to `<name>.before_cell_patch.nc` first; the registry hash is updated.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import xarray as xr

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from dotenv import load_dotenv

from geofrea.core import paths as core_paths
from geofrea.data_acquisition.era5_registry import Era5Registry, sha256_file
from geofrea.data_acquisition.fetchers import era5

CELLS = ((10.0, 76.25), (23.75, 68.5))  # (lat, lon) of the empty cells of the IND mask
TOLERANCE = 1e-4


def annual_max_of_box(files: list[Path]) -> xr.DataArray:
    parts = []
    for f in sorted(files):
        with xr.open_dataset(f) as ds:
            da = (
                ds["fg10"].rename(valid_time="time")
                if "valid_time" in ds["fg10"].dims
                else ds["fg10"]
            )
            parts.append(da.groupby("time.year").max("time").load())
    return xr.concat(parts, dim="year").sortby("year")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("iso")
    args = ap.parse_args()
    load_dotenv(REPO_ROOT / ".env", override=False)
    iso = args.iso
    global_dir = core_paths.fetched_raw("era5", "_global")
    country_dir = core_paths.fetched_raw("era5", iso)
    product = country_dir / f"{iso}_fg10_annual_max.nc"
    backup = product.with_name(product.stem + ".before_cell_patch.nc")
    files = sorted(global_dir.glob(f"{iso}_patch_fg10_hourly_*.nc"))
    jobs = json.loads((global_dir / f"{iso}_patch_jobs.json").read_text(encoding="utf-8"))["jobs"]
    years_covered = sorted(y for j in jobs.values() for y in j["years"])
    assert years_covered == list(range(1995, 2015)), years_covered

    box = annual_max_of_box(files)
    assert list(box.year.values) == list(range(1995, 2015))
    with xr.open_dataset(product) as ds:
        prod = ds["fg10"].load()
        attrs = dict(ds.attrs)

    # 1. the method, where the product already has values: the cells of the box that are finite in the product
    la = prod.latitude.sel(latitude=slice(box.latitude.min() + 0.25, box.latitude.max() - 0.25))
    lo = prod.longitude.sel(longitude=slice(box.longitude.min() + 0.25, box.longitude.max() - 0.25))
    sub = prod.sel(latitude=la, longitude=lo)
    other = box.sel(
        latitude=sub.latitude, longitude=sub.longitude, method="nearest", tolerance=1e-3
    )
    other = other.assign_coords(latitude=sub.latitude, longitude=sub.longitude)
    both = np.isfinite(sub.values) & np.isfinite(other.values)
    diff = np.abs(sub.values - other.values)[both]
    check = {
        "cell_years_compared": int(both.sum()),
        "max_abs_diff_ms": float(diff.max()),
        "mean_abs_diff_ms": float(diff.mean()),
        "tolerance_ms": TOLERANCE,
    }
    print("method check:", json.dumps(check), flush=True)
    if check["max_abs_diff_ms"] > TOLERANCE:
        raise SystemExit(
            "the patch files do not reproduce the product where it has values: nothing written"
        )

    # 2. the cells
    if not backup.exists():
        shutil.copy2(product, backup)
    values = prod.values.copy()
    patched = []
    for lat, lon in CELLS:
        i = int(np.argmin(np.abs(prod.latitude.values - lat)))
        j = int(np.argmin(np.abs(prod.longitude.values - lon)))
        assert np.isnan(values[:, i, j]).all(), (lat, lon, "is not empty in every year")
        v = box.sel(latitude=lat, longitude=lon, method="nearest", tolerance=1e-3).values.astype(
            "float32"
        )
        assert np.isfinite(v).all() and v.shape == (20,)
        values[:, i, j] = v
        patched.append({"lat": lat, "lon": lon, "min_ms": float(v.min()), "max_ms": float(v.max())})
    out = prod.copy(data=values)
    provenance = {
        "cells": patched,
        "source": "reanalysis-era5-single-levels fg10 hourly, box lat 9.75-24.0, lon 68.25-76.5, 1995-2014, two years per request",
        "jobs": {
            k: {
                "years": v["years"],
                "submitted": v["submitted"],
                "started": v.get("started"),
                "finished": v.get("finished"),
            }
            for k, v in jobs.items()
        },
        "method_check": check,
        "patched": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
    }
    attrs["cell_patch_provenance"] = json.dumps(provenance, default=str)
    part = product.with_suffix(".part.nc")
    xr.Dataset({"fg10": out}, attrs=attrs).to_netcdf(part)
    part.replace(product)

    registry_path = global_dir / "era5_registry.json"
    registry = Era5Registry.load(registry_path)
    entry = registry.entries[f"era5/{iso}/fg10"]
    registry.entries[f"era5/{iso}/fg10"] = entry.model_copy(
        update={"source_sha256": sha256_file(product), "reduced_sha256": sha256_file(product)}
    )
    registry.save(registry_path)
    grid = era5.read_native_grid(product)
    print(
        json.dumps({"patched": patched, "grid": [grid.n_lat, grid.n_lon], "backup": str(backup)}),
        flush=True,
    )
    (country_dir / f"{iso}_fg10_cell_patch_report.json").write_text(
        json.dumps(provenance, indent=1, default=str), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
