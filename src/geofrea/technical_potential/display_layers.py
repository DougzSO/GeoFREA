"""Display layers of the potential maps at the 0.01 degree grid of F2a (COMMAND 67b, D-core-047).

A map of a small country drawn on the 0.05 degree cells of the analysis shows blocks. The data that the analysis aggregated are finer: the pixels of
F2a (0.01 degree, 5 x 5 pixels per cell). A *display layer* is the same descriptive quantity on those pixels, made only to be drawn:

  - `capacity-factor`: the capacity factor of the pixel, from the same model as F5 (`CfModel.prepare` on the pixels: the air density of the hub
    height, the Weibull speed, the curve; the reference member), only on the pixels of the cells that F5 retained;
  - `eligible-fraction`: the share of the pixel that F3 found eligible;
  - `capacity-density`: MW per km2 of land of the pixel (`capacity_density_mw_km2` times the eligible fraction);
  - `energy-density`: GWh per km2 per year of the pixel (the capacity density times the capacity factor times the hours of the year).

Nothing here replaces an analysis artifact: the layers are `display_<layer>_<tech>.tif` under the artifacts of F5 with `display_layers_<tech>.json`
(their own fingerprint: the inputs, the parameters and the checks). They are used only by `potential_maps` to draw descriptive maps; no total, no
LCOE and no ranking reads them. Every layer is checked against the analysis when it is built (`check_aggregation`): the capacity factor
aggregated back to the 0.05 degree cell (weighted by the eligible area, as F3 does) is within 1% of the value of the analysis in every cell, and the
eligible area and the capacity are exact.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

from geofrea.technical_potential.cf_models import CfModel, CfSettings
from geofrea.viz import display
from geofrea.viz.display import AggregationCheck, DisplayLayer

LAYERS = ("capacity-factor", "eligible-fraction", "capacity-density", "energy-density")
FINE_PER_CELL = 5  # 0.01 degree pixels along one side of a 0.05 degree cell
EXACT_TOLERANCE = (
    1e-6  # float32 precision of the stored analysis rasters (an eligible area, a capacity): "exact"
)
NODATA = -9999.0
HOURS_PER_YEAR = 8760.0


class DisplayLayerError(RuntimeError):
    """A display layer cannot be built, or does not reproduce the analysis (A-09)."""


@dataclass(frozen=True)
class DisplayBuild:
    layers: dict[str, DisplayLayer]
    checks: list[AggregationCheck]
    fingerprint: str


def display_path(directory: Path, layer: str, tech: str) -> Path:
    return Path(directory) / f"display_{layer}_{tech}.tif"


def meta_path(directory: Path, tech: str) -> Path:
    return Path(directory) / f"display_layers_{tech}.json"


def fine_capacity_factor(
    model: CfModel, settings: CfSettings, resources: Mapping[str, np.ndarray], keep: np.ndarray
) -> np.ndarray:
    """The reference-member capacity factor of every pixel of `keep` (True), by the F5 model itself; NaN elsewhere.

    `resources` are the resource layers of the registry on the pixels (the columns the model reads: the PVOUT, or the Weibull and air density
    layers at their heights). The air density rule and the curve are those of F5 because the model is.
    """
    shape = keep.shape
    frame = pd.DataFrame(
        {name: np.asarray(a, dtype="float64")[keep] for name, a in resources.items()}
    )
    out = np.full(shape, np.nan)
    if not len(frame):
        return out
    prepared = model.prepare(frame, settings)
    rows = np.arange(len(frame))
    ones, zeros = np.ones(len(frame)), np.zeros(len(frame))
    out[keep] = prepared.member(rows, ones, zeros, ones)
    return out


def _upsample(cells: np.ndarray, k: int) -> np.ndarray:
    return np.kron(cells, np.ones((k, k), dtype=cells.dtype))


def _fingerprint(parts: dict) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _array_hash(a: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(a, dtype="float64").tobytes()).hexdigest()[:12]


def build_display_layers(
    *,
    model: CfModel,
    settings: CfSettings,
    resources: Mapping[str, np.ndarray],
    eligible_fraction: np.ndarray,
    pixel_area_km2: np.ndarray,
    extent: display.Extent,
    analysis_cf: np.ndarray,
    analysis_eligible_area_km2: np.ndarray,
    analysis_capacity_density: np.ndarray,
    capacity_density_mw_km2: float,
    cell_area_km2: np.ndarray,
    k: int = FINE_PER_CELL,
    cf_tolerance: float = display.CF_TOLERANCE,
) -> DisplayBuild:
    """The four display layers of a technology from the pixels of F2a/F3, and their checks against the analysis grid.

    Pixel arrays (`resources`, `eligible_fraction`, `pixel_area_km2`) are `k` times finer than the analysis arrays (`analysis_cf`, the eligible area
    of F3, the capacity density `P_MW / cell_area_km2` and the land `cell_area_km2` of the cell, NaN where F5 retained no cell). Only the pixels of a
    retained cell with eligible area are drawn (the retention of F5). Raises `DisplayLayerError` if a check fails.
    """
    fine_shape = eligible_fraction.shape
    if tuple(s // k for s in fine_shape) != analysis_cf.shape or any(s % k for s in fine_shape):
        raise DisplayLayerError(
            f"the pixels {fine_shape} are not {k} times the analysis grid {analysis_cf.shape}"
        )
    retained = _upsample(np.isfinite(analysis_cf), k)
    fraction = np.where(np.isfinite(eligible_fraction), eligible_fraction, 0.0)
    eligible_km2 = pixel_area_km2 * fraction
    keep = retained & (eligible_km2 > 0)
    cf = fine_capacity_factor(model, settings, resources, keep)
    cap_density = np.where(keep, capacity_density_mw_km2 * fraction, np.nan)
    energy_density = cap_density * cf * HOURS_PER_YEAR / 1000.0  # MW/km2 * h = MWh/km2 -> GWh/km2
    layers = {
        "capacity-factor": cf,
        "eligible-fraction": np.where(retained, fraction, np.nan),
        "capacity-density": cap_density,
        "energy-density": energy_density,
    }
    cell_deg = display.cell_deg_of(fine_shape, extent)
    out = {name: DisplayLayer(name, grid, extent, cell_deg) for name, grid in layers.items()}

    weight = np.where(keep, eligible_km2, 0.0)
    cap_cell = display.block_sum(np.where(keep, cap_density * pixel_area_km2, 0.0), k)
    with np.errstate(invalid="ignore", divide="ignore"):
        cap_density_back = np.where(np.isfinite(analysis_cf), cap_cell / cell_area_km2, np.nan)
    checks = [
        display.check_aggregation(
            "capacity-factor", cf, analysis_cf, k, weight=weight, tolerance=cf_tolerance
        ),
        display.check_aggregation(
            "eligible-area",
            np.where(keep, eligible_km2, np.nan),
            np.where(np.isfinite(analysis_cf), analysis_eligible_area_km2, np.nan),
            k,
            tolerance=EXACT_TOLERANCE,
            how="sum",
        ),
        display.check_aggregation(
            "capacity-density",
            cap_density_back,
            np.where(np.isfinite(analysis_cf), analysis_capacity_density, np.nan),
            1,
            tolerance=EXACT_TOLERANCE,
        ),
    ]
    failed = [c for c in checks if not c.ok]
    if failed:
        raise DisplayLayerError(
            "a display layer does not reproduce the analysis: "
            + "; ".join(
                f"{c.name} differs by {c.max_rel_diff:.3g} (limit {c.tolerance:g})" for c in failed
            )
        )
    fingerprint = _fingerprint(
        {
            "layers": LAYERS,
            "k": k,
            "extent": extent,
            "capacity_density_mw_km2": capacity_density_mw_km2,
            "cf_tolerance": cf_tolerance,
            "inputs": {n: _array_hash(a) for n, a in sorted(resources.items())},
            "fraction": _array_hash(eligible_fraction),
            "area": _array_hash(pixel_area_km2),
            "analysis": [_array_hash(analysis_cf), _array_hash(analysis_eligible_area_km2)],
        }
    )
    return DisplayBuild(out, checks, fingerprint)


def write_display_layers(directory: Path, tech: str, build: DisplayBuild) -> dict[str, Path]:
    """The layers as GeoTIFFs (EPSG:4326, float32, NaN as nodata) and `display_layers_<tech>.json` with the fingerprint and the checks."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for name, layer in build.layers.items():
        west, east, south, north = layer.extent
        height, width = layer.grid.shape
        transform = rasterio.Affine(
            (east - west) / width, 0, west, 0, -(north - south) / height, north
        )
        path = display_path(directory, name, tech)
        data = np.where(np.isfinite(layer.grid), layer.grid, NODATA).astype("float32")
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=transform,
            nodata=NODATA,
            compress="deflate",
        ) as dst:
            dst.write(data, 1)
        written[name] = path
    meta_path(directory, tech).write_text(
        json.dumps(
            {
                "fingerprint": build.fingerprint,
                "display_only": True,
                "layers": list(build.layers),
                "checks": [
                    {
                        "name": c.name,
                        "cells": c.cells,
                        "max_rel_diff": c.max_rel_diff,
                        "tolerance": c.tolerance,
                        "ok": c.ok,
                    }
                    for c in build.checks
                ],
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    return written


def load_display_layer(directory: Path, layer: str, tech: str) -> DisplayLayer | None:
    """The display layer `layer` of `tech`, or None when it was not built (or its record is missing): the map then draws the analysis cells."""
    path = display_path(directory, layer, tech)
    record = meta_path(directory, tech)
    if not path.is_file() or not record.is_file():
        return None
    if not json.loads(record.read_text(encoding="utf-8")).get("fingerprint"):
        return None
    with rasterio.open(path) as src:
        grid = src.read(1).astype("float64")
        b = src.bounds
        cell = abs(src.transform.a)
    grid[grid == NODATA] = np.nan
    return DisplayLayer(layer, grid, (b.left, b.right, b.bottom, b.top), cell)
