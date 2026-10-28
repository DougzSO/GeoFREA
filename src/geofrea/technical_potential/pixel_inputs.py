"""The 0.01 degree pixels of the candidate cells, for a capacity-factor model that is evaluated per pixel (M-F5-03, D-F5-038).

A wind cell is not one wind: its 5 x 5 pixels (0.01 degree, F2a) carry different Weibull A, k and air density, and the power curve is not
linear. F5 therefore evaluates the model on every eligible pixel and aggregates the capacity factors to the cell with the eligible area of
each pixel as weight, which is the weight F3 uses for every other cell quantity (`aggregate_to_cells`). This module reads the pixels of the
candidate cells and nothing else: it holds no model and no curve.

Layout: compressed by cell (CSR). The pixels of candidate cell `i` (position in the candidate table) are `offsets[i]:offsets[i + 1]`; only
pixels with eligible area and a finite value of every resource are kept, which is the rule of F3 for the cell means.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

from geofrea.land_eligibility.cells import lattice_window, pad_to_window, pixel_row_area_km2

# the eligible area of a cell in the F3 table and the sum of its pixel weights agree to the float32 precision of the pixel raster
AREA_AGREEMENT_RTOL = 1e-4


class PixelInputError(RuntimeError):
    """The pixel rasters do not match the candidate cells (A-09)."""


@dataclass(frozen=True)
class CellPixels:
    """Eligible pixels of the candidate cells: the eligible area of each (km2) and the value of every resource layer."""

    offsets: np.ndarray  # (n_cells + 1,) int64
    weight_km2: np.ndarray  # (n_pixels,) float64, > 0
    resources: Mapping[str, np.ndarray]  # layer -> (n_pixels,) float64, finite

    @property
    def counts(self) -> np.ndarray:
        return np.diff(self.offsets)


def _read(path: Path, dtype: str) -> tuple[np.ndarray, rasterio.Affine]:
    with rasterio.open(path) as src:
        return src.read(1, masked=True).astype(dtype).filled(np.nan), src.transform


def read_cell_pixels(
    cells: pd.DataFrame, fraction_path: Path, resource_paths: Mapping[str, Path]
) -> CellPixels:
    """The eligible pixels of the cells of `cells` (`row`, `col`, `eligible_area_km2`), in the order of the table.

    Args:
        cells: Candidate table of a land scenario (columns `row`, `col` of the 0.05 degree lattice and `eligible_area_km2`).
        fraction_path: Pixel eligible fraction of that scenario (`eligible_fraction_<tech>[__<scenario>].tif`, F3).
        resource_paths: Resource layer name -> its raster on the same grid (F2b, physical units).

    Raises:
        PixelInputError: a raster is not on the grid of the fraction, a cell lies outside it, a candidate cell has no eligible pixel, or the
            sum of the pixel weights of a cell differs from its eligible area in the F3 table (a raster of another scenario or run).
    """
    fraction, transform = _read(fraction_path, "float32")
    height, width = fraction.shape
    window = lattice_window(transform, height, width)
    k = window.k
    rows = cells["row"].to_numpy(dtype="int64") - window.row0
    cols = cells["col"].to_numpy(dtype="int64") - window.col0
    if len(cells) and (
        rows.min() < 0 or cols.min() < 0 or rows.max() >= window.n_rows or cols.max() >= window.n_cols
    ):
        raise PixelInputError(f"{fraction_path.name}: a candidate cell lies outside the raster")

    area_row = pixel_row_area_km2(transform, height)
    weight = np.where(np.isfinite(fraction), fraction, 0.0).astype("float64") * area_row[:, None]
    del fraction
    padded = pad_to_window(weight, window)
    del weight

    def gather(grid: np.ndarray) -> np.ndarray:
        """(n_cells, k * k): the pixels of every cell, row by row inside the cell."""
        blocks = grid.reshape(window.n_rows, k, window.n_cols, k)
        i = np.arange(k)
        picked = blocks[rows[:, None, None], i[None, :, None], cols[:, None, None], i[None, None, :]]
        return picked.reshape(len(rows), k * k)

    w = gather(padded)
    del padded
    values: dict[str, np.ndarray] = {}
    usable = w > 0
    for name, path in resource_paths.items():
        grid, other = _read(path, "float32")
        if grid.shape != (height, width) or other != transform:
            raise PixelInputError(f"{path.name} is not on the grid of {fraction_path.name}")
        values[name] = gather(pad_to_window(grid, window, np.nan)).astype("float64")
        del grid
        usable &= np.isfinite(values[name])
    w = np.where(usable, w, 0.0)

    counts = usable.sum(axis=1)
    if (counts == 0).any():
        raise PixelInputError(
            f"{fraction_path.name}: {int((counts == 0).sum())} candidate cells have no eligible pixel with a finite resource"
        )
    table_area = cells["eligible_area_km2"].to_numpy(dtype="float64")
    gap = np.abs(w.sum(axis=1) - table_area) / table_area
    if (gap > AREA_AGREEMENT_RTOL).any():
        worst = int(np.argmax(gap))
        raise PixelInputError(
            f"{fraction_path.name}: the pixel weights of {int((gap > AREA_AGREEMENT_RTOL).sum())} cells differ from the eligible area of the "
            f"F3 table by more than {AREA_AGREEMENT_RTOL:g} (largest {gap[worst]:.3g}, cell {int(cells['cell_id'].iloc[worst])})"
        )
    offsets = np.concatenate([[0], np.cumsum(counts)]).astype("int64")
    return CellPixels(
        offsets=offsets,
        weight_km2=w[usable],
        resources={name: v[usable] for name, v in values.items()},
    )
