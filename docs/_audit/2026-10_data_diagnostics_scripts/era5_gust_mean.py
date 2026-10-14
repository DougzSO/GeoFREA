# ruff: noqa
"""Mean ERA5 10 m gust (fg10) over 1995-2014 on the 0.25 degree grid, from the hourly per-year files on disk.
The disk holds no ERA5 mean wind and no ERA5 Tmax (inventory in the report); the mean gust is the closest ERA5 wind field.
Usage: python era5_gust_mean.py BRA|PRT|IND"""

from __future__ import annotations

import sys

import numpy as np
import xarray as xr

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import *  # noqa

country = sys.argv[1]
tot, n, lat, lon = None, 0, None, None
for y in range(1995, 2015):
    with xr.open_dataset(DATA / "raw" / "era5" / "_global" / f"{country}_fg10_hourly_bbox_{y}.nc") as ds:
        da = ds["fg10"]
        lat, lon = da["latitude"].values, da["longitude"].values
        for i in range(0, da.sizes["valid_time"], 1000):
            blk = da.isel(valid_time=slice(i, i + 1000)).values.astype("float64")
            s = np.nansum(blk, axis=0)
            tot = s if tot is None else tot + s
            n += blk.shape[0]
    print(y, n, flush=True)
np.savez(SCRATCH / f"era5_gust_mean_{country}.npz", mean=(tot / n).astype("float32"), lat=lat, lon=lon, hours=n)
print("hours", n)
