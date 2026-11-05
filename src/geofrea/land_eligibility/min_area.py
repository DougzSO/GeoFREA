"""The minimum eligible area of Group 6: a pixel floor and a cluster floor, applied to the eligible fraction of the whole grid (COMMAND 97).

Eligible pixels (fraction > 0) are grouped into clusters of 8-connected 0.01 degree pixels. A cluster is kept only if its eligible area (the sum over its
pixels of eligible fraction x geodesic pixel area) reaches `min_cluster_km2`; a pixel whose eligible fraction is below `min_pixel_fraction` is dropped before
the clusters are formed (the share needed for one turbine per square kilometre, `subsec:g6_minarea`). A scenario with no minimum is left as it is.

The clusters are labelled on the whole grid, not by stripe: F3 works by stripes of rows (D-F3-024), and a cluster that crosses stripes has one area. The
eligible fraction of the whole grid is held as one `float32` array and the labels as one `int32` array (BRA: about 70 MB each, measured in
`docs/_audit/group6_audit_97.md`), after the stripes of the first pass are released, so the peak of the phase does not grow by more than that. The labelling
needs no union of labels between stripes. `label_clusters` and `cluster_areas` are the same functions the tests compare with a brute-force reference.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import ndimage

from geofrea.config_models.land_availability import ParameterSet
from geofrea.land_eligibility.windows import NpyRows, NpyWriter

EIGHT_CONNECTED = np.ones((3, 3), dtype=bool)
_CHUNK_ROWS = 512


@dataclass(frozen=True)
class MinAreaStats:
    """What the minimum-area rules did in one technology and scenario (areas in km2)."""

    n_clusters: int  # clusters of 8-connected pixels with an eligible fraction > 0, after the pixel floor
    n_clusters_kept: int
    area_before_km2: float
    area_removed_by_pixel_floor_km2: float
    area_removed_by_cluster_floor_km2: float


def label_clusters(fraction: np.ndarray) -> tuple[np.ndarray, int]:
    """Labels (`int32`, 0 for no cluster) of the 8-connected pixels of `fraction` > 0, and the number of clusters."""
    labels, n = ndimage.label(fraction > 0, structure=EIGHT_CONNECTED, output=np.int32)
    return labels, int(n)


def cluster_areas(labels: np.ndarray, n: int, fraction: np.ndarray, area_row_km2: np.ndarray) -> np.ndarray:
    """Eligible area (km2) of each cluster, index 0 is the background: the sum of eligible fraction x geodesic pixel area of its pixels (float64)."""
    total = np.zeros(n + 1, dtype=np.float64)
    for r0 in range(0, labels.shape[0], _CHUNK_ROWS):
        r1 = min(r0 + _CHUNK_ROWS, labels.shape[0])
        weights = fraction[r0:r1].astype(np.float64) * area_row_km2[r0:r1, None]
        total += np.bincount(labels[r0:r1].ravel(), weights=weights.ravel(), minlength=n + 1)
    return total


def apply_minimum_area(
    fraction: np.ndarray,
    area_row_km2: np.ndarray,
    min_pixel_fraction: float | None,
    min_cluster_km2: float | None,
) -> tuple[np.ndarray, MinAreaStats]:
    """The eligible fraction after the pixel floor and the cluster floor, and what they removed.

    Args:
        fraction: Eligible fraction of every pixel of the grid (`float32`, 0 where not eligible).
        area_row_km2: Geodesic area (km2) of a pixel of each row.
        min_pixel_fraction: Drop a pixel whose eligible fraction is below this share (null: none).
        min_cluster_km2: Drop a cluster whose eligible area is below this (null: none).
    """
    area_before = float((fraction.sum(axis=1, dtype=np.float64) * area_row_km2).sum())
    out = fraction
    removed_pixel = 0.0
    if min_pixel_fraction is not None:
        keep = out >= np.float32(min_pixel_fraction)
        removed_pixel = float((np.where(keep, np.float32(0.0), out).sum(axis=1, dtype=np.float64) * area_row_km2).sum())
        out = np.where(keep, out, np.float32(0.0)).astype(np.float32)
        del keep
    n = kept = 0
    removed_cluster = 0.0
    if min_cluster_km2 is not None:
        labels, n = label_clusters(out)
        areas = cluster_areas(labels, n, out, area_row_km2)
        keep_label = areas >= float(min_cluster_km2)
        keep_label[0] = False
        kept = int(keep_label.sum())
        removed_cluster = float(areas[1:][~keep_label[1:]].sum())
        out = np.where(keep_label[labels], out, np.float32(0.0)).astype(np.float32)
        del labels
    return out, MinAreaStats(n, kept, area_before, removed_pixel, removed_cluster)


def write_minimum_area(
    raw: NpyRows, area_row_km2: np.ndarray, params: ParameterSet, out_path: Path
) -> tuple[NpyRows, MinAreaStats | None]:
    """The eligible fraction of the whole grid after the minimum-area rules of `params`, written to `out_path` (read back by rows).

    With neither rule the first-pass fraction is the result and `raw` is returned unchanged, with no statistics.
    """
    if params.min_pixel_fraction is None and params.min_cluster_km2 is None:
        return raw, None
    height = raw.shape[0]
    fraction = raw[0:height]
    result, stats = apply_minimum_area(fraction, area_row_km2, params.min_pixel_fraction, params.min_cluster_km2)
    del fraction
    writer = NpyWriter(out_path, raw.shape, np.float32)
    for r0 in range(0, height, _CHUNK_ROWS):
        writer.write(result[r0 : r0 + _CHUNK_ROWS])
    writer.close()
    del result
    return NpyRows(out_path), stats
