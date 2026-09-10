"""Array normalisation for suitability_criteria (Fase 2b).

Ported verbatim (behaviour, not line-for-line) from legacy
geoworld_framework's src/utils/normalization.py::normalize_percentile.

Kept inside this phase package for now, NOT in core/: the legacy shared
it with Phase 5 (LCOE) and Phase 8 (Sensitivity), but neither exists in
GeoFREA yet, and docs/CONVENTIONS.md ("Parameters") is explicit about
not building shared abstractions against code that doesn't exist. Same
reasoning grid_alignment used to keep its own local `timer()` /
`_read_clipped_with_cache()` rather than pre-emptively promoting them.
Move to core/ when the second real consumer arrives.
"""

from __future__ import annotations

import numpy as np

from geofrea.core.constants import NODATA_FLOAT


def valid_finite_mask(data: np.ndarray, nodata: float | None) -> np.ndarray:
    """Boolean mask: True for finite pixels that are not the nodata value.

    Args:
        data: Raster band as a float array.
        nodata: The raster's declared nodata value, or None.

    Returns:
        Boolean array, same shape as `data`.
    """
    mask = np.isfinite(data)
    if nodata is not None:
        mask &= data != float(nodata)
    return mask


def normalize_percentile(
    data: np.ndarray,
    valid: np.ndarray,
    p_low: float,
    p_high: float,
) -> np.ndarray:
    """Min-max normalise `data` into [0, 1] with percentile clipping.

    S(x) = clip((x - P_low) / (P_high - P_low), 0, 1), computed over the
    pixels selected by `valid` only. Matches legacy exactly, including
    the two degenerate cases:
      - no valid pixels: returns an all-NODATA_FLOAT array.
      - P_high <= P_low (a flat distribution): every valid pixel gets
        0.5, not a divide-by-zero.

    Args:
        data: Raw input array (any dtype; cast to float64 internally for
            the percentile maths).
        valid: Boolean mask of pixels to consider for statistics and to
            write a score for. Invalid pixels stay NODATA_FLOAT.
        p_low: Lower percentile clip, in [0, 100].
        p_high: Upper percentile clip, in [0, 100].

    Returns:
        float32 array, same shape as `data`; scores in [0, 1] where
        `valid`, NODATA_FLOAT elsewhere.
    """
    score = np.full(data.shape, NODATA_FLOAT, dtype=np.float32)
    if not valid.any():
        return score

    vals = data[valid].astype(np.float64)
    v_low = np.percentile(vals, p_low)
    v_high = np.percentile(vals, p_high)

    if v_high <= v_low:
        score[valid] = 0.5
        return score

    score[valid] = np.clip((vals - v_low) / (v_high - v_low), 0.0, 1.0).astype(np.float32)
    return score
