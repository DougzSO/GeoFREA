# ruff: noqa
"""B-1 / 8-2 computation: native reference fields and per-cell change factors of every GCM, SSP and window, in memory
(cached as .npz in the scratch directory, never in GeoFREA_data). Usage: python b1_compute.py BRA"""

from __future__ import annotations

import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import *  # noqa
from geofrea.climate_forcing.change_factors import bilinear_to_points, neighbourhood_mean

country = sys.argv[1] if len(sys.argv) > 1 else "BRA"
NS = (1, 3, 5, 7)
t0 = time.time()
cells = forcing_cells(country)
lat, lon = cells["lat_c"].to_numpy(), cells["lon_c"].to_numpy()
print(country, "cells", len(cells), flush=True)

out = {"cell_id": cells["cell_id"].to_numpy(), "lat": lat, "lon": lon}
for g in GCMS:
    hist_w = load_native(g, "historical", "sfcWind", country)
    ref_w = annual_clim(hist_w, REF)
    out[f"native_ref_wind|{g}"] = ref_w.values
    out[f"native_lat|{g}"] = ref_w["lat"].values
    out[f"native_lon|{g}"] = ref_w["lon"].values
    out[f"native_land|{g}"] = native_land_mask(ref_w, country)
    hist_t = load_native(g, "historical", "tas", country)
    ref_t = annual_clim(hist_t, REF)
    for ssp, exp in SSPS.items():
        scen_w = load_native(g, exp, "sfcWind", country)
        scen_t = load_native(g, exp, "tas", country)
        for wn, years in WINDOWS.items():
            win_w = annual_clim(scen_w, years)
            for n in NS:
                a, b = (ref_w, win_w) if n == 1 else (neighbourhood_mean(ref_w, n), neighbourhood_mean(win_w, n))
                ratio = (b / a).where(a > 0)
                out[f"dw|{g}|{ssp}|{wn}|{n}"] = bilinear_to_points(ratio, lat, lon).astype("float32")
                if n == 3:
                    out[f"native_dw3|{g}|{ssp}|{wn}"] = ratio.values.astype("float32")
            dT = annual_clim(scen_t, years) - ref_t
            out[f"dT|{g}|{ssp}|{wn}"] = bilinear_to_points(dT, lat, lon).astype("float32")
            out[f"native_dT|{g}|{ssp}|{wn}"] = dT.values.astype("float32")
    print(g, f"{time.time() - t0:.0f}s", flush=True)
np.savez_compressed(SCRATCH / f"b1_{country}.npz", **out)
print("saved", SCRATCH / f"b1_{country}.npz")
