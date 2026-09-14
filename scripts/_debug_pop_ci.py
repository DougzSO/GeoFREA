"""TEMPORARY diagnostic script -- investigating a CI-only pop_suitability
bit-exactness gap (2026-09-14). Bit-exact locally on Windows (0 differing
pixels vs the frozen baseline); fails on the Linux CI runner with a
~1e-7 max delta. Run only via workflow_dispatch (see
.github/workflows/regression.yml). Delete both files once the root
cause is confirmed -- see docs/DECISIONS.md for the writeup.
"""

import platform
import sys

import numpy as np
import rasterio

from geofrea.core.config_loader import load_parameters
from geofrea.suitability_criteria.criteria_functions import compute_population_suitability

print("platform:", platform.platform())
print("python:", sys.version)
print("numpy:", np.__version__)
try:
    print("numpy CPU features:", np.show_config(mode="dicts")["SIMD Extensions"])
except Exception as e:  # noqa: BLE001 - diagnostic script, broad catch is fine
    print("could not get SIMD info:", e)

params = load_parameters("config/parameters.json")
criteria = params.criteria.model_copy(deep=True)
criteria.pop_density_threshold = criteria.pop_density_threshold.model_copy(update={"value": 300.0})

pop_path = ".legacy_baseline/data/processed/PRT/PRT_population_aligned.tif"
frozen_path = "outputs_baseline_fc7b43d/PRT/criteria_builder/tif/pop_suitability.tif"

with rasterio.open(pop_path) as src:
    pop_raw = src.read(1)
score, _t, _c = compute_population_suitability(pop_path, criteria)
with rasterio.open(frozen_path) as src:
    frozen = src.read(1).astype(np.float32)


def valid(a):
    return np.isfinite(a) & (a != -9999.0) & (a >= 0)


fv = valid(frozen)
diff = np.abs(frozen[fv].astype(np.float64) - score[fv].astype(np.float64))
n_diff = int((diff != 0).sum())
print(f"differing pixels: {n_diff} / {diff.size}  max={diff.max():.6e}")

diff_full = np.zeros(frozen.shape, dtype=bool)
diff_full[fv] = diff != 0
rows, cols = np.where(diff_full)
pop_at_diff = pop_raw[rows, cols].astype(np.float64)
pop_at_same = pop_raw[fv][diff == 0].astype(np.float64)

if n_diff:
    print(f"pop at DIFFERING pixels: min={pop_at_diff.min():.6f} max={pop_at_diff.max():.6f}")
    print("  >=threshold(300):", int((pop_at_diff >= 300).sum()), "/", n_diff)
    print("  percentiles:", np.percentile(pop_at_diff, [0, 10, 25, 50, 75, 90, 100]))
if pop_at_same.size:
    print(f"pop at EXACT pixels: min={pop_at_same.min():.6f} max={pop_at_same.max():.6f}")
    print("  >=threshold(300):", int((pop_at_same >= 300).sum()), "/", pop_at_same.size)

one = np.float32(1.0)
ulp = np.nextafter(one, np.float32(2.0)) - one
print(f"float32 ULP near 1.0: {ulp:.6e}")
if n_diff:
    print(f"max delta in ULPs: {diff.max() / ulp:.3f}")
    print("sample differing pixels (pop, frozen, ours, delta):")
    for i in range(min(8, n_diff)):
        r, c = int(rows[i]), int(cols[i])
        p = float(pop_raw[r, c])
        fz = float(frozen[r, c])
        sc = float(score[r, c])
        print(f"  pop={p:.6f}  frozen={fz:.10f}  ours={sc:.10f}  delta={abs(fz - sc):.3e}")
