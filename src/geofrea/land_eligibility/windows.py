"""Row-window inputs and the stripe engine of F3 (COMMAND 91).

F3 of BRA held 2.3 GB between calls and peaked at 3.6 GB (`docs/_audit/f3_memory_90.md`): every input and every exclusion of the grid was a whole
array, although each operation is a function of one pixel and the cells are summed from whole rows of cells. Here every input is read by a window
of rows, the exclusions of one window are computed by the same functions as before (`eligible_fraction`, `aggregate_to_cells`), and the eligible
fraction is written window by window, so that what is resident is a stripe and not the country.

Nothing in the arithmetic changes: a pixel gets the value it got from the whole grid, and the cell sums are taken in float64 over the same pixels in
the same order (`cells.aggregate_to_cells` sums in stripes of whole cell rows).

The height of a stripe is `stripe_pixels` pixels (`resolve_stripe_pixels`: the argument, else the environment variable `GEOFREA_F3_STRIPE_PIXELS`,
else `DEFAULT_STRIPE_PIXELS`). It sets the memory and nothing else.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

from geofrea.config_models.land_availability import ParameterSet
from geofrea.core.raster_io import safe_raster_open
from geofrea.land_eligibility.eligibility import (
    EXCLUSION_NAMES,
    EligibilityLayers,
    _steep_share,
    corridor_key,
    eligible_fraction,
    valid_pixels,
)
from geofrea.land_eligibility.errors import LandEligibilityError

DEFAULT_STRIPE_PIXELS = 1_000_000
STRIPE_ENV = "GEOFREA_F3_STRIPE_PIXELS"
_PREPARE_WINDOW_PIXELS = 500_000  # window of the one pass over the 41 slope bins (82 bytes a pixel)


def resolve_stripe_pixels(value: int | None = None) -> int:
    """Pixels of one stripe: `value`, else the environment variable `GEOFREA_F3_STRIPE_PIXELS`, else `DEFAULT_STRIPE_PIXELS`."""
    if value is None:
        raw = os.environ.get(STRIPE_ENV)
        value = int(raw) if raw else DEFAULT_STRIPE_PIXELS
    if int(value) < 1:
        raise ValueError(f"a stripe needs at least one pixel, got {value}")
    return int(value)


def _bounds(rows: slice, height: int) -> tuple[int, int]:
    r0, r1, step = rows.indices(height)
    if step != 1:
        raise ValueError("rows must be a contiguous slice")
    return r0, r1


class RasterRows:
    """Band 1 of a raster by rows, converted as `pipeline._read` converts the whole band: `dtype`, nodata and non-finite values -> NaN."""

    def __init__(self, path: Path | None, name: str, dtype: str = "float64") -> None:
        if path is None or not Path(path).exists():
            raise LandEligibilityError(f"required layer {name!r} is missing ({path})")
        self.path, self.dtype = Path(path), dtype
        with safe_raster_open(self.path) as src:
            self.shape = (src.height, src.width)
            self.nodata = src.nodata

    def __getitem__(self, rows: slice) -> np.ndarray:
        r0, r1 = _bounds(rows, self.shape[0])
        with safe_raster_open(self.path) as src:
            arr = src.read(1, window=Window(0, r0, self.shape[1], r1 - r0)).astype(self.dtype, copy=False)
        if self.nodata is not None and np.isfinite(self.nodata):
            arr[arr == self.nodata] = np.nan
        arr[~np.isfinite(arr)] = np.nan
        return arr


class FlagRows(RasterRows):
    """A 0/1 flag raster by rows, as the boolean `_read(...) == 1` of the whole raster."""

    def __getitem__(self, rows: slice) -> np.ndarray:
        return super().__getitem__(rows) == 1


class ClassCountRows:
    """The aligned class-count raster (one band per land-cover class) by rows: (counts, valid mask) of a window, as `pipeline._read_class_counts`."""

    def __init__(self, path: Path | None) -> None:
        if path is None or not Path(path).exists():
            raise LandEligibilityError(
                "the aligned land-cover class counts (F2a `land_cover_counts`) are missing; rerun grid_alignment"
            )
        self.path = Path(path)
        with safe_raster_open(self.path) as src:
            self.shape = (src.height, src.width)
            self.nodata = src.nodata
            tags = src.tags()
        self.classes = tuple(int(c) for c in tags["worldcover_classes"].split(","))
        self.samples_per_pixel = int(tags["samples_per_pixel"])
        if 0 in self.classes or self.samples_per_pixel <= 0:
            raise LandEligibilityError(
                "the aligned land-cover class counts come from the retired centre-count mode (a band for no class, or no samples per "
                "pixel); delete the file and rerun grid_alignment (M-F2a-06, V19)"
            )

    def __getitem__(self, rows: slice) -> tuple[np.ndarray, np.ndarray]:
        r0, r1 = _bounds(rows, self.shape[0])
        with safe_raster_open(self.path) as src:
            counts = src.read(window=Window(0, r0, self.shape[1], r1 - r0))
        outside = (counts == self.nodata).all(axis=0)
        counts[:, outside] = 0
        return counts, ~outside & (counts.sum(axis=0, dtype=np.uint32) > 0)


class NpyWriter:
    """A `.npy` file written row by row, in order, without holding the array (the header first, then the rows)."""

    def __init__(self, path: Path, shape: tuple[int, int], dtype) -> None:
        self.path, self.shape, self.dtype = Path(path), tuple(shape), np.dtype(dtype)
        self._rows = 0
        self._file = open(self.path, "wb")  # noqa: SIM115  (closed by `close`, rows are written one call at a time)
        np.lib.format.write_array_header_1_0(
            self._file,
            {"descr": np.lib.format.dtype_to_descr(self.dtype), "fortran_order": False, "shape": self.shape},
        )

    def write(self, rows: np.ndarray) -> None:
        arr = np.ascontiguousarray(rows, dtype=self.dtype)
        if arr.shape[1:] != self.shape[1:]:
            raise ValueError(f"rows of shape {arr.shape} do not fit {self.shape}")
        self._file.write(arr.tobytes())
        self._rows += arr.shape[0]

    def close(self) -> Path:
        self._file.close()
        if self._rows != self.shape[0]:
            raise ValueError(f"{self.path.name}: {self._rows} rows written of {self.shape[0]}")
        return self.path


class NpyRows:
    """A `.npy` array read by rows through a memory map opened for the call and closed after it, so that the pages do not stay in the working set."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        mm = np.load(self.path, mmap_mode="r")
        self.shape, self.dtype = mm.shape, mm.dtype
        del mm

    def __getitem__(self, rows: slice) -> np.ndarray:
        r0, r1 = _bounds(rows, self.shape[0])
        mm = np.load(self.path, mmap_mode="r")
        try:
            return np.array(mm[r0:r1])
        finally:
            del mm


@dataclass
class SlopeShares:
    """E4 per slope maximum and the validity of the slope bins, as files read by rows."""

    valid: NpyRows
    steep: dict[float, NpyRows]


def prepare_slope_shares(path: Path | None, maxima, out_dir: Path) -> SlopeShares:
    """One pass over the 41 slope bins by windows: the E4 share of each slope maximum and the validity mask, written under `out_dir`.

    The values are those of `pipeline._read_slope_counts` followed by `eligibility.slope_steep_shares` on the whole grid: `_steep_share` is taken per
    pixel and sums the bins of a pixel in the same order whatever the window.
    """
    if path is None or not Path(path).exists():
        raise LandEligibilityError(
            "the aligned slope bins (F2a `slope_counts`) are missing: run `python scripts/acquire_dem30.py`, then rerun grid_alignment"
        )
    thresholds = sorted({float(t) for t in maxima})
    out_dir.mkdir(parents=True, exist_ok=True)
    with safe_raster_open(path) as src:
        height, width, nodata = src.height, src.width, src.nodata
        valid_w = NpyWriter(out_dir / "slope_valid.npy", (height, width), bool)
        steep_w = {t: NpyWriter(out_dir / f"slope_steep_{t}.npy", (height, width), np.float32) for t in thresholds}
        step = max(1, _PREPARE_WINDOW_PIXELS // max(1, width))
        for r0 in range(0, height, step):
            r1 = min(r0 + step, height)
            counts = src.read(window=Window(0, r0, width, r1 - r0))
            outside = (counts == nodata).all(axis=0)
            counts[:, outside] = 0
            valid_w.write(~outside & (counts.sum(axis=0, dtype=np.uint32) > 0))
            for t, w in steep_w.items():
                w.write(_steep_share(counts, t))
            del counts
    valid_w.close()
    for w in steep_w.values():
        w.close()
    return SlopeShares(
        valid=NpyRows(out_dir / "slope_valid.npy"),
        steep={t: NpyRows(out_dir / f"slope_steep_{t}.npy") for t in thresholds},
    )


@dataclass
class StripeInputs:
    """Everything the six exclusions read for a country, as row sources (none is resident but the country mask and one value a row)."""

    transform: rasterio.Affine
    shape: tuple[int, int]
    country_mask: np.ndarray  # bool, 1 byte a pixel
    area_row: np.ndarray  # geodesic area (km2) of a pixel of each row, float64
    population: RasterRows
    land_cover: ClassCountRows
    slope: SlopeShares
    lakes: NpyRows
    protected: dict[tuple[str, ...], NpyRows]
    corridor: dict[tuple, NpyRows]  # the river-corridor shares by eligibility.corridor_key of the scenarios
    settlement: dict[float, NpyRows]  # the settlement-setback shares by setback in metres
    settlement_class: RasterRows | None  # the aligned GHS-SMOD class of each pixel (NaN where missing); None when only the density sensitivity runs
    flags: dict[str, FlagRows]


class RowsView:
    """An array-like whose `[rows]` is computed on demand: what `cells.aggregate_to_cells` indexes by stripe."""

    def __init__(self, fn: Callable[[slice], np.ndarray]) -> None:
        self._fn = fn

    def __getitem__(self, rows: slice) -> np.ndarray:
        return self._fn(rows)


class _Window:
    __slots__ = ("_valid", "area", "elevation", "eligible", "excl", "mask", "r0", "r1", "resources")


class ScenarioStripes:
    """The exclusions of one technology under one parameter set, computed by windows of rows as `cells.aggregate_to_cells` asks for them.

    The window last asked for is kept, so that the eligible share, the six exclusions and the resources of a stripe are computed once. Beside the
    cells the stripes give: `pixel_total` (the sum of eligible area over the pixels, V-03), `n_valid` (the valid pixels, for the invalid share) and,
    through `on_eligible(first_row, eligible)`, the eligible fraction of each window for the raster that is written as it goes.

    `eligible_override` (Group 6, COMMAND 97) replaces the eligible fraction of a window by the one after the minimum-area rules, which need the
    eligible fraction of the whole grid (`min_area.py`): the first pass computes the fraction without the rules (`pass_eligible`), the second reads the
    result and sums the cells. The six excluded shares are those of the exclusions in both.
    """

    def __init__(
        self,
        inputs: StripeInputs,
        resources: Mapping[str, RasterRows],
        elevation: RasterRows | None,
        params: ParameterSet,
        on_eligible: Callable[[int, np.ndarray], None] | None = None,
        eligible_override: NpyRows | None = None,
    ) -> None:
        self.inputs, self.resources, self.elevation, self.params = inputs, resources, elevation, params
        self._on_eligible = on_eligible
        self._override = eligible_override
        self._window: _Window | None = None
        self.pixel_total = 0.0
        self.n_valid = 0
        self.rows_done = 0
        self.eligible = RowsView(lambda rows: self._get(rows).eligible)
        self.exclusions = {name: RowsView(lambda rows, n=name: self._get(rows).excl[n]) for name in EXCLUSION_NAMES}
        self.cell_resources: dict[str, RowsView] = {
            name: RowsView(lambda rows, n=name: self._get(rows).resources[n]) for name in resources
        }

    def elevation_view(self) -> RowsView:
        return RowsView(lambda rows: self._get(rows).elevation)

    def pass_eligible(self, write_rows: Callable[[np.ndarray], None], window_rows: int) -> None:
        """The eligible fraction of the whole grid in order, window by window, handed to `write_rows` (the first pass of the minimum-area rules).

        The six exclusions and the validity of the resource layers are read, not the elevation. The counters of the stripes (`pixel_total`, `n_valid`) are not advanced.
        """
        height = self.inputs.shape[0]
        for r0 in range(0, height, max(1, int(window_rows))):
            r1 = min(r0 + max(1, int(window_rows)), height)
            write_rows(self._compute(r0, r1, with_elevation=False).eligible)
        self._window = None

    def _compute(self, r0: int, r1: int, with_elevation: bool) -> _Window:
        w = _Window()
        w.r0, w.r1 = r0, r1
        inp, params = self.inputs, self.params
        width = inp.shape[1]
        w.resources = {name: src[r0:r1] for name, src in self.resources.items()}
        w.elevation = self.elevation[r0:r1] if (with_elevation and self.elevation is not None) else None
        counts, lc_valid = inp.land_cover[r0:r1]
        key = tuple(sorted(params.iucn_categories))
        mask = inp.country_mask[r0:r1]
        area = np.repeat(inp.area_row[r0:r1, None], width, axis=1)
        density_rule = params.pop_density_max_per_km2 is not None
        settlement = {} if density_rule else {float(params.settlement_setback_m): inp.settlement[float(params.settlement_setback_m)][r0:r1]}
        settlement_valid = None
        if not density_rule:
            if inp.settlement_class is None:
                raise LandEligibilityError("the settlement layer is required unless the density sensitivity runs")
            settlement_valid = np.isfinite(inp.settlement_class[r0:r1])
        layers = EligibilityLayers(
            country_mask=mask,
            pixel_area_km2=area,
            slope_counts=None,
            slope_valid=inp.slope.valid[r0:r1],
            population_count=inp.population[r0:r1],
            land_cover_counts=counts,
            land_cover_classes=inp.land_cover.classes,
            land_cover_valid=lc_valid,
            samples_per_pixel=inp.land_cover.samples_per_pixel,
            lakes_fraction=inp.lakes[r0:r1],
            protected_fraction={key: inp.protected[key][r0:r1]},
            river_corridor={corridor_key(params): inp.corridor[corridor_key(params)][r0:r1]},
            settlement_share=settlement,
            settlement_valid=settlement_valid,
            slope_steep_share={float(params.slope_max_deg): inp.slope.steep[float(params.slope_max_deg)][r0:r1]},
            required_valid={name: np.isfinite(a) for name, a in w.resources.items()},
        )
        w.eligible, w.excl = eligible_fraction(layers, params)
        w._valid = valid_pixels(layers)
        w.area, w.mask = area, mask
        return w

    def _get(self, rows: slice) -> _Window:
        r0, r1 = _bounds(rows, self.inputs.shape[0])
        w = self._window
        if w is not None and (w.r0, w.r1) == (r0, r1):
            return w
        self._window = None  # the previous window goes before the next one is built
        w = self._compute(r0, r1, with_elevation=True)
        if self._override is not None:
            w.eligible = self._override[r0:r1]
        self.pixel_total += float((w.eligible * w.area * w.mask).sum())
        self.n_valid += int(np.count_nonzero(w._valid))
        if self._on_eligible is not None:
            self._on_eligible(r0, w.eligible)
        self.rows_done += r1 - r0
        self._window = w
        return w