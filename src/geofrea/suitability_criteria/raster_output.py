"""Write a criterion score raster and summarise its distribution.

Ported from legacy geoworld_framework's src/processors/criteria_builder.py
(`_save_criterion` L94-112) and the statistics `write_criteria_summary`
/ the phase's own console log compute (L1056-1063).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from rasterio.transform import Affine

from geofrea.core.constants import NODATA_FLOAT
from geofrea.core.raster_io import safe_raster_write


def save_criterion_raster(
    score: np.ndarray, out_path: Path, transform: Affine, crs: str
) -> None:
    """Write a normalised criterion raster as a tiled, LZW GeoTIFF.

    Matches legacy's `_save_criterion` profile exactly: float32, 1 band,
    nodata = NODATA_FLOAT, 256x256 internal tiling.

    Args:
        score: float32 score array (NODATA_FLOAT for invalid pixels).
        out_path: Destination .tif path (parent dirs created).
        transform: Affine geotransform.
        crs: CRS string (e.g. "EPSG:4326").
    """
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "width": score.shape[1],
        "height": score.shape[0],
        "count": 1,
        "crs": crs,
        "transform": transform,
        "nodata": NODATA_FLOAT,
        "compress": "lzw",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with safe_raster_write(out_path, **profile) as dst:
        dst.write(score.astype("float32"), 1)


def _valid_scores(score: np.ndarray) -> np.ndarray:
    """The finite, non-nodata, non-negative score pixels (legacy's filter)."""
    return score[np.isfinite(score) & (score != NODATA_FLOAT) & (score >= 0)]


def criterion_stats(score: np.ndarray) -> dict[str, float | int]:
    """Summary statistics for a criterion score array.

    Same filter and metrics the legacy uses for its summary report and
    console log: valid = finite & != NODATA_FLOAT & >= 0.

    Args:
        score: The criterion score array.

    Returns:
        dict with keys valid_pixels, mean, std, p10, p50, p90,
        frac_ge_0_6. If there are no valid pixels, the numeric stats are
        0.0 and valid_pixels is 0 (the criterion is still recorded, so a
        consumer can see it produced nothing).
    """
    v = _valid_scores(score)
    if v.size == 0:
        return {
            "valid_pixels": 0,
            "mean": 0.0,
            "std": 0.0,
            "p10": 0.0,
            "p50": 0.0,
            "p90": 0.0,
            "frac_ge_0_6": 0.0,
        }
    p10, p50, p90 = (float(x) for x in np.percentile(v, [10, 50, 90]))
    return {
        "valid_pixels": int(v.size),
        "mean": float(v.mean()),
        "std": float(v.std()),
        "p10": p10,
        "p50": p50,
        "p90": p90,
        "frac_ge_0_6": float((v >= 0.6).mean()),
    }
