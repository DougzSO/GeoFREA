"""When two artifacts count as equal (COMMAND 88, item 4; CONVENTIONS "Changes that must not change a result").

The content hash is exact: a float summed in another order, as GDAL does when its warp chunks change, differs in the last bits and the hash with it. The
comparison here decides by the kind of data:

  float        equal when |new - ref| <= REL_TOL * |ref| + ABS_TOL at every pixel (REL_TOL = 1e-6, ABS_TOL = 1e-9); a missing value (NaN or the
               declared nodata) must be missing in both
  integer      exact equality (counts, classes, flags, categorical codes)
  other        exact equality

The largest absolute difference and the largest relative difference of a float artifact are reported, so a tolerance never hides how much was used.
Frozen regression fixtures (V-01) keep their own rule (`rtol = 1e-6`, binary layers exact); this module governs the proofs of equivalence of a change
of code and the adoption of earlier layers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

REL_TOL = 1e-6
ABS_TOL = 1e-9


@dataclass(frozen=True)
class Comparison:
    """Outcome of comparing two arrays: whether they are equivalent, the rule that applied and how far apart they are."""

    equivalent: bool
    kind: str  # "float" | "exact"
    n_compared: int = 0
    n_outside: int = 0  # pixels beyond the tolerance (float) or different (exact)
    n_missing_mismatch: int = 0  # missing in one and present in the other
    max_abs_delta: float = 0.0
    max_rel_delta: float = 0.0

    def as_dict(self) -> dict:
        return asdict(self)


def compare_arrays(ref: np.ndarray, new: np.ndarray, nodata: float | None = None) -> Comparison:
    """Compare `new` with `ref` by the rule of their dtype (see the module docstring); `nodata` is a value that counts as missing."""
    if ref.shape != new.shape:
        return Comparison(False, "exact", n_compared=int(ref.size), n_outside=int(max(ref.size, new.size)))
    if not (np.issubdtype(ref.dtype, np.floating) and np.issubdtype(new.dtype, np.floating)):
        differ = ref != new
        return Comparison(not bool(differ.any()), "exact", n_compared=int(ref.size), n_outside=int(differ.sum()))
    ref64, new64 = ref.astype(np.float64), new.astype(np.float64)
    missing_ref, missing_new = ~np.isfinite(ref64), ~np.isfinite(new64)
    if nodata is not None:
        missing_ref |= ref64 == nodata
        missing_new |= new64 == nodata
    mismatch = int((missing_ref != missing_new).sum())
    both = ~missing_ref & ~missing_new
    delta = np.abs(new64[both] - ref64[both])
    bound = REL_TOL * np.abs(ref64[both]) + ABS_TOL
    outside = int((delta > bound).sum())
    max_abs = float(delta.max()) if delta.size else 0.0
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = np.where(ref64[both] != 0, delta / np.abs(ref64[both]), 0.0)
    return Comparison(
        equivalent=mismatch == 0 and outside == 0,
        kind="float",
        n_compared=int(both.sum()),
        n_outside=outside,
        n_missing_mismatch=mismatch,
        max_abs_delta=max_abs,
        max_rel_delta=float(rel.max()) if rel.size else 0.0,
    )


def _merge(a: Comparison | None, b: Comparison) -> Comparison:
    if a is None:
        return b
    return Comparison(
        equivalent=a.equivalent and b.equivalent,
        kind=a.kind,
        n_compared=a.n_compared + b.n_compared,
        n_outside=a.n_outside + b.n_outside,
        n_missing_mismatch=a.n_missing_mismatch + b.n_missing_mismatch,
        max_abs_delta=max(a.max_abs_delta, b.max_abs_delta),
        max_rel_delta=max(a.max_rel_delta, b.max_rel_delta),
    )


def compare_rasters(ref_path: Path, new_path: Path, rows_per_block: int = 512) -> Comparison:
    """Compare band 1 of two rasters by dtype, `rows_per_block` rows at a time; the grid (shape, transform, CRS) must be identical or they are not equivalent."""
    import rasterio
    from rasterio.windows import Window

    with rasterio.open(ref_path) as ref, rasterio.open(new_path) as new:
        if (ref.shape, ref.transform, ref.crs) != (new.shape, new.transform, new.crs):
            return Comparison(False, "exact", n_compared=int(ref.width * ref.height), n_outside=int(ref.width * ref.height))
        total: Comparison | None = None
        for row in range(0, ref.height, rows_per_block):
            window = Window(0, row, ref.width, min(rows_per_block, ref.height - row))
            total = _merge(total, compare_arrays(ref.read(1, window=window), new.read(1, window=window), ref.nodata))
    assert total is not None
    return total
