"""The 0.01 degree pixels of the candidate cells, for a capacity-factor model that is evaluated per pixel (M-F5-03, D-F5-038).

A wind cell is not one wind: its 5 x 5 pixels (0.01 degree, F2a) carry different Weibull A, k and air density, and the power curve is not
linear. F5 therefore evaluates the model on every eligible pixel and aggregates the capacity factors to the cell with the eligible area of
each pixel as weight, which is the weight F3 uses for every other cell quantity (`aggregate_to_cells`). This module reads the pixels of the
candidate cells and nothing else: it holds no model and no curve.

Layout: compressed by cell (CSR). The pixels of candidate cell `i` (position in the candidate table) are `offsets[i]:offsets[i + 1]`; only
pixels with eligible area and a finite value of every resource are kept, which is the rule of F3 for the cell means.

The rasters are read in bands of cell rows (COMMAND 126), never whole: the memory of the read is bounded by the band and by the result, not by
a full raster, its float64 weight and a padded copy of each of the ten rasters. The result is bit for bit that of reading the whole rasters
(`tests/unit/test_f5_memory_equivalence.py`).
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window

from geofrea.land_eligibility.cells import LatticeWindow, lattice_window, pixel_row_area_km2

# the eligible area of a cell in the F3 table and the sum of its pixel weights agree to the float32 precision of the pixel raster
AREA_AGREEMENT_RTOL = 1e-4
# pixels of one band of cell rows; a band gathers the weight and the nine resources of its cells at once (about 25 pixels per cell, float64)
BAND_PIXELS = 1_000_000


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


def _read_rows(
    src: rasterio.DatasetReader, window: LatticeWindow, first: int, stop: int, dtype: str, fill: float
) -> np.ndarray:
    """Cell rows `first:stop` of the lattice window of `src` as the pixel grid padded to whole cells, `fill` outside the raster.

    The values are those of `pad_to_window(src.read(1, masked=True).astype(dtype).filled(nan), window, fill)[first * k : stop * k]`, pixel
    for pixel: the same read, the same masking and the same cast, on the rows of the band only.
    """
    k = window.k
    top, bottom = first * k, stop * k  # rows of the padded grid
    out = np.full((bottom - top, window.n_cols * k), fill, dtype=dtype)
    raster_top = max(top - window.pad_top, 0)
    raster_bottom = min(bottom - window.pad_top, window.height)
    if raster_bottom > raster_top:
        band = src.read(
            1, window=Window(0, raster_top, window.width, raster_bottom - raster_top), masked=True
        )
        band = band.astype(dtype).filled(np.nan)
        out[
            raster_top + window.pad_top - top : raster_bottom + window.pad_top - top,
            window.pad_left : window.pad_left + window.width,
        ] = band
    return out


def _gather(
    grid: np.ndarray, r_loc: np.ndarray, c_loc: np.ndarray, n_band_rows: int, window: LatticeWindow
) -> np.ndarray:
    """(cells, k * k): the pixels of every cell of a band, row by row inside the cell; `r_loc` and `c_loc` are the cell positions in the band."""
    k = window.k
    i = np.arange(k)
    blocks = grid.reshape(n_band_rows, k, window.n_cols, k)
    picked = blocks[r_loc[:, None, None], i[None, :, None], c_loc[:, None, None], i[None, None, :]]
    return picked.reshape(len(r_loc), k * k)


def read_cell_pixels(
    cells: pd.DataFrame, fraction_path: Path, resource_paths: Mapping[str, Path]
) -> CellPixels:
    """The eligible pixels of the cells of `cells` (`row`, `col`, `eligible_area_km2`), in the order of the table.

    The rasters are read in bands of cell rows (`BAND_PIXELS` pixels each) and every pixel goes through the same operations as when the whole
    raster was read (read, mask, cast, weight by the row area, gather); the pixels of the cells are then placed in the order of the table.

    Args:
        cells: Candidate table of a land scenario (columns `row`, `col` of the 0.05 degree lattice and `eligible_area_km2`).
        fraction_path: Pixel eligible fraction of that scenario (`eligible_fraction_<tech>[__<scenario>].tif`, F3).
        resource_paths: Resource layer name -> its raster on the same grid (F2b, physical units).

    Raises:
        PixelInputError: a raster is not on the grid of the fraction, a cell lies outside it, a candidate cell has no eligible pixel, or the
            sum of the pixel weights of a cell differs from its eligible area in the F3 table (a raster of another scenario or run).
    """
    with ExitStack() as stack:
        fraction_src = stack.enter_context(rasterio.open(fraction_path))
        height, width = fraction_src.height, fraction_src.width
        transform = fraction_src.transform
        window = lattice_window(transform, height, width)
        k = window.k
        rows = cells["row"].to_numpy(dtype="int64") - window.row0
        cols = cells["col"].to_numpy(dtype="int64") - window.col0
        if len(cells) and (
            rows.min() < 0
            or cols.min() < 0
            or rows.max() >= window.n_rows
            or cols.max() >= window.n_cols
        ):
            raise PixelInputError(f"{fraction_path.name}: a candidate cell lies outside the raster")

        resource_srcs: dict[str, rasterio.DatasetReader] = {}
        for name, path in resource_paths.items():
            src = stack.enter_context(rasterio.open(path))
            if (src.height, src.width) != (height, width) or src.transform != transform:
                raise PixelInputError(f"{path.name} is not on the grid of {fraction_path.name}")
            resource_srcs[name] = src

        area_row = pixel_row_area_km2(transform, height)
        n_cells = len(rows)
        order = np.argsort(rows, kind="stable")  # the cells by band; inside a row, the order of the table
        rows_sorted = rows[order]
        band_rows = max(1, BAND_PIXELS // (window.n_cols * k * k))  # cell rows per band
        counts = np.zeros(n_cells, dtype="int64")
        weight_sum = np.zeros(n_cells, dtype="float64")
        chunks_w: list[np.ndarray] = []
        chunks_v: dict[str, list[np.ndarray]] = {name: [] for name in resource_srcs}
        for first in range(0, window.n_rows, band_rows):
            stop = min(first + band_rows, window.n_rows)
            lo = int(np.searchsorted(rows_sorted, first, side="left"))
            hi = int(np.searchsorted(rows_sorted, stop, side="left"))
            if hi == lo:
                continue
            sel = order[lo:hi]
            r_loc = rows[sel] - first
            c_loc = cols[sel]
            n_band_rows = stop - first

            fraction = _read_rows(fraction_src, window, first, stop, "float32", np.nan)
            weight = np.where(np.isfinite(fraction), fraction, 0.0).astype("float64")
            del fraction
            # the weight of a pixel is the fraction times the area of its raster row; outside the raster it stays 0 (the old pad_to_window fill)
            raster_top = max(first * k - window.pad_top, 0)
            raster_bottom = min(stop * k - window.pad_top, height)
            if raster_bottom > raster_top:
                inside_rows = slice(
                    raster_top + window.pad_top - first * k,
                    raster_bottom + window.pad_top - first * k,
                )
                inside_cols = slice(window.pad_left, window.pad_left + width)
                weight[inside_rows, inside_cols] *= area_row[raster_top:raster_bottom, None]
            w = _gather(weight, r_loc, c_loc, n_band_rows, window)
            del weight
            usable = w > 0
            values: dict[str, np.ndarray] = {}
            for name, src in resource_srcs.items():
                grid = _read_rows(src, window, first, stop, "float32", np.nan)
                values[name] = _gather(grid, r_loc, c_loc, n_band_rows, window).astype("float64")
                del grid
                usable &= np.isfinite(values[name])
            w = np.where(usable, w, 0.0)
            counts[sel] = usable.sum(axis=1)
            weight_sum[sel] = w.sum(axis=1)
            chunks_w.append(w[usable])
            for name, v in values.items():
                chunks_v[name].append(v[usable])
            del w, values, usable

    if (counts == 0).any():
        raise PixelInputError(
            f"{fraction_path.name}: {int((counts == 0).sum())} candidate cells have no eligible pixel with a finite resource"
        )
    table_area = cells["eligible_area_km2"].to_numpy(dtype="float64")
    gap = np.abs(weight_sum - table_area) / table_area
    if (gap > AREA_AGREEMENT_RTOL).any():
        worst = int(np.argmax(gap))
        raise PixelInputError(
            f"{fraction_path.name}: the pixel weights of {int((gap > AREA_AGREEMENT_RTOL).sum())} cells differ from the eligible area of the "
            f"F3 table by more than {AREA_AGREEMENT_RTOL:g} (largest {gap[worst]:.3g}, cell {int(cells['cell_id'].iloc[worst])})"
        )
    offsets = np.concatenate([[0], np.cumsum(counts)]).astype("int64")
    place: np.ndarray | None = None
    if not bool((order == np.arange(n_cells)).all()):
        # the bands hold the cells sorted by row: send the pixels of every cell to its place in the table
        sorted_counts = counts[order]
        sorted_offsets = np.concatenate([[0], np.cumsum(sorted_counts)])
        within = np.arange(int(sorted_counts.sum())) - np.repeat(sorted_offsets[:-1], sorted_counts)
        place = np.repeat(offsets[:-1][order], sorted_counts) + within

    def joined(chunks: list[np.ndarray]) -> np.ndarray:
        flat = np.concatenate(chunks) if chunks else np.empty(0, dtype="float64")
        chunks.clear()
        if place is None:
            return flat
        out = np.empty_like(flat)
        out[place] = flat
        return out

    weight_km2 = joined(chunks_w)
    resources = {name: joined(chunks) for name, chunks in chunks_v.items()}
    return CellPixels(offsets=offsets, weight_km2=weight_km2, resources=resources)
