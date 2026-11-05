"""Error of the 1-degree-bin interpolation of E4 against the exact share of 30 m samples (COMMAND 97, extra item).

Per 1x1 degree tile: slope samples exactly as F2a computes them (`_glo30_strip_samples`), the exact steep share per 0.01 degree pixel
(mean of slope > threshold over the valid samples) against `eligibility._steep_share` on the 1-degree bins built from the same samples.
Run as: python -I bin_error.py  (with PYTHONPATH=src of GeoFREA).
"""
import random
import sys
import types
from pathlib import Path

import numpy as np
import rasterio

from geofrea.grid_alignment import raster_alignment as ra
from geofrea.land_eligibility.eligibility import _steep_share

SP = ra._GLO30_SAMPLES_PER_DEGREE
BINS = ra.SLOPE_BINS
RES = 0.01
THR = {"PV 3%": 1.718, "PV 5%": 2.862, "PV 10%": 5.711, "wind 10%": 5.711, "wind 20%": 11.310, "wind 30%": 16.699}
THR = {"PV 3%": float(np.degrees(np.arctan(0.03))), "PV 5%": float(np.degrees(np.arctan(0.05))),
       "PV 10%": float(np.degrees(np.arctan(0.10))), "wind 20%": float(np.degrees(np.arctan(0.20))),
       "wind 30%": float(np.degrees(np.arctan(0.30)))}


def tile_window(path: Path):
    stem = path.stem  # Copernicus_DSM_COG_10_N00_00_W050_00_DEM
    parts = stem.split("_")
    lat = int(parts[4][1:]) * (1 if parts[4][0] == "N" else -1)
    lon = int(parts[6][1:]) * (1 if parts[6][0] == "E" else -1)
    return lat, lon


def run(country: str, n_tiles: int, seed: int):
    tiles = sorted(Path(rf"D:\Douglas\DOUTORADO\GeoFREA_data\raw\copernicus_dem30\{country}").glob("*.tif"))
    rng = random.Random(seed)
    pick = tiles if len(tiles) <= n_tiles else rng.sample(tiles, n_tiles)
    index = ra._glo30_tile_index(tiles)
    acc = {k: {"elig_exact": 0.0, "elig_bins": 0.0, "pix": 0, "maxabs": 0.0, "sumabs": 0.0} for k in THR}
    used = 0
    for p in pick:
        lat, lon = tile_window(p)
        # grid: 100 x 100 pixels of 0.01 degree covering the tile; north-west corner (lat+1, lon)
        grid = types.SimpleNamespace(
            transform=rasterio.Affine(RES, 0, lon, 0, -RES, lat + 1.0), width=100, height=100
        )
        strip = ra._glo30_strip_samples(index, grid, 0, 100, SP)
        if strip is None:
            continue
        _, slope, grow, gcol = strip
        valid = np.isfinite(slope)
        if not valid.any():
            continue
        pix = (grow[:, None] * 100 + gcol[None, :])[valid]
        s = slope[valid]
        n = np.bincount(pix, minlength=10000).astype(np.float64)
        bins = np.clip(np.floor(s), 0, BINS - 1).astype(np.int64)
        counts = np.bincount(pix * BINS + bins, minlength=10000 * BINS).reshape(10000, BINS).T.reshape(BINS, 100, 100)
        has = (n > 0).reshape(100, 100)
        for name, thr in THR.items():
            above = np.bincount(pix[s > thr], minlength=10000).astype(np.float64)
            exact = np.where(n > 0, above / np.maximum(n, 1), 0.0).reshape(100, 100)
            approx = _steep_share(counts.astype(np.uint16), thr).astype(np.float64)
            d = np.abs(approx - exact)[has]
            a = acc[name]
            a["elig_exact"] += float((1 - exact)[has].sum())
            a["elig_bins"] += float((1 - approx)[has].sum())
            a["pix"] += int(has.sum())
            a["maxabs"] = max(a["maxabs"], float(d.max()))
            a["sumabs"] += float(d.sum())
        used += 1
        print(country, p.name, "ok", flush=True)
    return used, acc


if __name__ == "__main__":
    for country, n in (("PRT", 100), ("BRA", int(sys.argv[1]) if len(sys.argv) > 1 else 40)):
        used, acc = run(country, n, seed=97)
        print(f"\n== {country}: {used} tiles")
        for name, a in acc.items():
            rel = (a["elig_bins"] - a["elig_exact"]) / a["elig_exact"] * 100
            print(
                f"{name:9s} thr={THR[name]:.3f} deg  pixels={a['pix']:7d}  eligible(slope only) exact={a['elig_exact']:.1f} bins={a['elig_bins']:.1f}"
                f"  relerr={rel:+.3f}%  mean|dshare|={a['sumabs'] / a['pix']:.5f}  max|dshare|={a['maxabs']:.4f}"
            )
