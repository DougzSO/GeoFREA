"""The eligibility engine of F3 evaluated at the pixels of the plants only, by windows of rows (COMMAND 187, OQ-068).

F7b needs the six excluded shares, the combined excluded share and the validity of the pixel under each operating unit, nothing else. Before COMMAND 187
it built them for the whole grid (`prepare_shared_layers`, `technology_layers`, `eligible_fraction`): about 1.5 GB held on BRA before the first plant was
read, above the cap of 1,536 MB. Here the inputs are the row sources of F3 (`StripeInputs`, `RasterRows`) and the engine runs, with the same functions
as F3 (`ScenarioStripes`, which calls `eligible_fraction` and `valid_pixels` on a window), only on the windows of rows that hold a plant pixel. What is
resident is one window.

Nothing in the arithmetic changes: every exclusion is a function of one pixel, so a pixel gets the value it got from the whole grid, bit for bit
(`tests/unit/test_external_validation_windows.py`, tolerance 0; the whole-grid functions stay as the oracle). The height of a window is the one of F3
(`resolve_stripe_pixels`) and sets the memory and nothing else.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from geofrea.config_models.land_availability import ParameterSet
from geofrea.land_eligibility.windows import (
    RasterRows,
    ScenarioStripes,
    StripeInputs,
    resolve_stripe_pixels,
)

CONSTRAINT_KEYS = ("E1", "E2", "E3", "E4", "E5", "E6")


class PixelValues:
    """The values of a layer at a set of pixels, indexed as the whole array was: `values[rows, cols]` with arrays of rows and columns.

    Only the pixels given at the construction can be asked for; any other raises `KeyError` (a pixel that was not evaluated has no value, never a
    silent default).
    """

    def __init__(self, width: int, keys: np.ndarray, values: np.ndarray) -> None:
        self._width = int(width)
        self._keys = keys
        self._values = values

    def __getitem__(self, index: tuple[np.ndarray, np.ndarray]) -> np.ndarray:
        rows, cols = index
        flat = np.asarray(rows, dtype="int64") * self._width + np.asarray(cols, dtype="int64")
        if flat.size == 0:
            return self._values[:0]
        at = np.searchsorted(self._keys, flat)
        at = np.minimum(at, len(self._keys) - 1)
        if len(self._keys) == 0 or not np.array_equal(self._keys[at], flat):
            raise KeyError("a pixel that was not evaluated was asked for")
        return self._values[at]


def evaluate_at_pixels(
    inputs: StripeInputs,
    resources: Mapping[str, RasterRows],
    params: ParameterSet,
    rows: np.ndarray,
    cols: np.ndarray,
    stripe_pixels: int | None = None,
) -> tuple[dict[str, PixelValues], PixelValues]:
    """The excluded shares and the validity of the engine at the pixels `(rows[i], cols[i])`.

    Args:
        inputs: The row sources of F3 (`prepare_stripe_inputs`).
        resources: The resource layers the technology requires, as row sources; a gap in one makes the pixel invalid.
        params: The parameter set (the central scenario in F7b).
        rows, cols: The pixels to evaluate (repeats are allowed).
        stripe_pixels: Pixels of one window (else `GEOFREA_F3_STRIPE_PIXELS`, else the default of F3).

    Returns:
        (`E1` to `E6` and `combined` -> excluded share at the pixels, as float32 arrays of the whole-grid engine; the validity of each pixel).
        `combined` is `(1 - eligible)` as float32, the expression F7b used on the whole grid.
    """
    height, width = inputs.shape
    rows = np.asarray(rows, dtype="int64")
    cols = np.asarray(cols, dtype="int64")
    if rows.shape != cols.shape:
        raise ValueError("rows and cols must have the same length")
    if rows.size and (
        rows.min() < 0 or rows.max() >= height or cols.min() < 0 or cols.max() >= width
    ):
        raise ValueError("a pixel lies outside the grid")
    flat = np.unique(rows * width + cols)
    pix_rows, pix_cols = flat // width, flat % width
    n = len(flat)
    keys = list(CONSTRAINT_KEYS) + ["combined"]
    parts: dict[str, list[np.ndarray]] = {
        k: [] for k in keys
    }  # the dtype of each is the one the engine gives, never forced
    valid_parts: list[np.ndarray] = []
    window_rows = max(1, resolve_stripe_pixels(stripe_pixels) // max(1, width))
    # elevation is not read (None): F7b has no use for it
    stripes = ScenarioStripes(inputs, resources, None, params)
    first = 0
    while first < n:
        r0 = (int(pix_rows[first]) // window_rows) * window_rows
        r1 = min(r0 + window_rows, height)
        last = int(np.searchsorted(pix_rows, r1, side="left"))
        window = stripes._get(
            slice(r0, r1)
        )  # the window engine of F3: its eligible share, exclusions and validity
        r, c = pix_rows[first:last] - r0, pix_cols[first:last]
        for k in CONSTRAINT_KEYS:
            parts[k].append(window.excl[k][r, c])
        parts["combined"].append((1.0 - window.eligible).astype("float32")[r, c])
        valid_parts.append(window._valid[r, c])
        first = last
    stripes._window = None  # release the last window
    empty = np.empty(0, dtype=np.float32)
    result = {
        k: PixelValues(width, flat, np.concatenate(v) if v else empty) for k, v in parts.items()
    }
    return result, PixelValues(
        width, flat, np.concatenate(valid_parts) if valid_parts else np.empty(0, dtype=bool)
    )
