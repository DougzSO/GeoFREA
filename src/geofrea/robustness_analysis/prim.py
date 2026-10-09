"""Patient rule induction (PRIM) for scenario discovery, minimal own implementation (M-F7-08, D-F7-021, OQ-056).

Peeling and pasting of Friedman and Fisher (1999) with the lenient objective of the `ema_workbench` reference implementation (the gain in the
mean of the outcome divided by the loss of support) and the settings of Bryant and Lempert (2010): the peeling fraction `alpha` and the
minimum support `mass_min`. One box is found, starting from all futures; the whole peeling and pasting trajectory is returned, because the
choice of the box on it (the trade-off between coverage and density) is the author's.

Descriptors are real (a box limit on each side) or categorical (the box keeps a set of categories). Pasting uses the same `alpha` as peeling.

Known differences from `ema_workbench` 3.0.0, the reference of the test (`tests/fixtures/prim_reference.json`):
  - Integer descriptors are not supported (the caller casts them to real).
  - `ema_workbench` stops pasting as soon as the real descriptors offer no paste, so it never pastes a categorical descriptor in a box that
    restricts no real one; here every restricted descriptor is considered. The reference cases avoid that situation.
  - `ema_workbench` iterates the categories of a set in hash order; here they are sorted, so ties between categorical peels are deterministic.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd


class PrimError(ValueError):
    """The input of PRIM is not valid (A-09)."""


@dataclass(frozen=True)
class PrimStep:
    """One box of the peeling and pasting trajectory (step 0 is the box with every future)."""

    step: int
    lower: dict[str, float]
    upper: dict[str, float]
    categories: dict[str, tuple[str, ...]]
    coverage: float
    density: float
    mass: float
    n: int
    k: int
    n_restricted: int


@dataclass(frozen=True)
class PrimResult:
    """The trajectory of the first box and the facts that frame it."""

    steps: tuple[PrimStep, ...]
    n_futures: int
    n_positive: int
    real_descriptors: tuple[str, ...]
    categorical_descriptors: tuple[str, ...]
    dropped_descriptors: tuple[str, ...]  # categorical descriptors with a single category


def sd_quantile(data: np.ndarray, quantile: float) -> float:
    """The quantile of `sdtoolkit` (and `ema_workbench`): the midpoint of two order statistics, stepping over ties away from the median.

    Raises:
        PrimError: `quantile` is not in the open interval (0, 1) or `data` is empty.
    """
    if not 0.0 < quantile < 1.0:
        raise PrimError(f"the quantile must be in (0, 1), got {quantile}")
    ordered = np.sort(np.asarray(data, dtype="float64"))
    if ordered.size == 0:
        raise PrimError("the quantile of an empty set is undefined")
    position = (ordered.size - 1) * quantile
    low, high = math.floor(position), math.ceil(position)
    if quantile > 0.5:
        while ordered[low] == ordered[high] and low > 0:
            low -= 1
    else:
        while ordered[low] == ordered[high] and high < ordered.size - 1:
            high += 1
    return float((ordered[low] + ordered[high]) / 2.0)


def _objective(y_old: np.ndarray, y_new: np.ndarray) -> float:
    """Lenient objective: the gain in the mean of the outcome divided by the loss of support (zero when the mean does not change)."""
    mean_old = float(y_old.mean())
    mean_new = float(y_new.mean()) if y_new.size else 0.0
    if mean_old == mean_new:
        return 0.0
    if y_old.size == y_new.size:
        raise PrimError("the mean changed while the support did not")
    return (mean_new - mean_old) / abs(y_old.size - y_new.size)


class _Box:
    """Limits of a box over the real columns and sets of categories over the categorical ones."""

    def __init__(self, lower, upper, categories):
        self.lower = lower
        self.upper = upper
        self.categories = categories

    def copy(self) -> _Box:
        return _Box(self.lower.copy(), self.upper.copy(), [set(c) for c in self.categories])


class _Search:
    def __init__(self, x: pd.DataFrame, y: np.ndarray, alpha: float, mass_min: float):
        real = [c for c in x.columns if pd.api.types.is_float_dtype(x[c])]
        other = [c for c in x.columns if c not in real]
        for column in other:
            if pd.api.types.is_numeric_dtype(x[column]) and not pd.api.types.is_bool_dtype(
                x[column]
            ):
                raise PrimError(f"descriptor {column}: integers are not supported, cast to float")
        categorical, dropped = [], []
        for column in other:
            if x[column].nunique() < 2:
                dropped.append(column)  # a single category cannot be peeled
            else:
                categorical.append(column)
        self.real, self.categorical, self.dropped = real, categorical, dropped
        self.xr = x[real].to_numpy(dtype="float64") if real else np.empty((len(x), 0))
        self.codes = []
        self.labels: list[list[str]] = []
        for column in categorical:
            cats = sorted(x[column].astype(str).unique())
            self.labels.append(cats)
            self.codes.append(pd.Categorical(x[column].astype(str), categories=cats).codes)
        self.y = y
        self.n = len(y)
        self.alpha = alpha
        self.mass_min = mass_min
        self.n_columns = len(real) + len(categorical)
        self.init = _Box(
            self.xr.min(axis=0) if real else np.empty(0),
            self.xr.max(axis=0) if real else np.empty(0),
            [set(range(len(c))) for c in self.labels],
        )

    def inside(self, box: _Box, dims: Sequence[tuple[str, int]], rows: np.ndarray) -> np.ndarray:
        """Boolean mask over `rows` of the futures inside `box` in the real and categorical dimensions listed in `dims`."""
        keep = np.ones(rows.size, dtype=bool)
        for kind, j in dims:
            if kind == "r":
                values = self.xr[rows, j]
                keep &= (values >= box.lower[j]) & (values <= box.upper[j])
            else:
                keep &= np.isin(self.codes[j][rows], list(box.categories[j]))
        return keep

    def restricted(self, box: _Box) -> list[tuple[str, int]]:
        dims = [
            ("r", j)
            for j in range(len(self.real))
            if box.lower[j] != self.init.lower[j] or box.upper[j] != self.init.upper[j]
        ]
        dims += [
            ("c", j)
            for j in range(len(self.categorical))
            if box.categories[j] != self.init.categories[j]
        ]
        return dims

    def step(self, index: int, box: _Box, rows: np.ndarray) -> PrimStep:
        y = self.y[rows]
        k = int(y.sum())
        return PrimStep(
            step=index,
            lower={c: float(box.lower[j]) for j, c in enumerate(self.real)},
            upper={c: float(box.upper[j]) for j, c in enumerate(self.real)},
            categories={
                c: tuple(self.labels[j][i] for i in sorted(box.categories[j]))
                for j, c in enumerate(self.categorical)
            },
            coverage=k / max(float(self.y.sum()), 1.0),
            density=k / y.size,
            mass=y.size / self.n,
            n=int(y.size),
            k=k,
            n_restricted=len(self.restricted(box)),
        )

    def _best(self, candidates, rows: np.ndarray):
        """The candidate with the largest objective, then the fewest restricted dimensions, then the first generated."""
        best, best_key = None, None
        for box, kept in candidates:
            key = (_objective(self.y[rows], self.y[kept]), -len(self.restricted(box)))
            if best_key is None or key > best_key:
                best, best_key = (box, kept), key
        return best, best_key

    def peel(
        self, box: _Box, rows: np.ndarray, trajectory: list[tuple[_Box, np.ndarray]]
    ) -> tuple[_Box, np.ndarray]:
        while True:
            candidates = []
            for j in range(len(self.real)):
                values = self.xr[rows, j]
                for direction in ("upper", "lower"):
                    cut = sd_quantile(
                        values, 1.0 - self.alpha if direction == "upper" else self.alpha
                    )
                    keep = values <= cut if direction == "upper" else values >= cut
                    new = box.copy()
                    (new.upper if direction == "upper" else new.lower)[j] = cut
                    candidates.append((new, rows[keep]))
            for j in range(len(self.categorical)):
                if len(box.categories[j]) < 2:
                    continue
                for category in sorted(box.categories[j]):
                    new = box.copy()
                    new.categories[j].discard(category)
                    candidates.append((new, rows[self.codes[j][rows] != category]))
            if not candidates:
                return box, rows
            (new, kept), (objective, _) = self._best(candidates, rows)
            mass_new, mass_old = kept.size / self.n, rows.size / self.n
            if mass_new >= self.mass_min and mass_new < mass_old and objective > 0:
                box, rows = new, kept
                trajectory.append((box, rows))
            else:
                return box, rows

    def paste(
        self, box: _Box, rows: np.ndarray, trajectory: list[tuple[_Box, np.ndarray]]
    ) -> tuple[_Box, np.ndarray]:
        everything = np.arange(self.n)
        while True:
            dims = self.restricted(box)
            candidates = []
            for kind, j in dims:
                if kind == "r":
                    for direction in ("lower", "upper"):
                        strip = box.copy()
                        if direction == "lower":
                            strip.lower[j], strip.upper[j] = self.init.lower[j], box.lower[j]
                        else:
                            strip.lower[j], strip.upper[j] = box.upper[j], self.init.upper[j]
                        values = self.xr[everything[self.inside(strip, dims, everything)], j]
                        new = box.copy()
                        if direction == "lower":
                            value = self.init.lower[j]
                            if values.size:
                                value = sd_quantile(values, 1.0 - self.alpha)
                            new.lower[j] = value
                        else:
                            value = self.init.upper[j]
                            if values.size:
                                value = sd_quantile(values, self.alpha)
                            new.upper[j] = value
                        candidates.append((new, everything[self.inside(new, dims, everything)]))
                else:
                    for category in sorted(self.init.categories[j] - box.categories[j]):
                        new = box.copy()
                        new.categories[j].add(category)
                        candidates.append((new, everything[self.inside(new, dims, everything)]))
            if not candidates:
                return box, rows
            (new, kept), (objective, _) = self._best(candidates, rows)
            mass_new, mass_old = kept.size / self.n, rows.size / self.n
            if (
                mass_new >= self.mass_min
                and mass_new > mass_old
                and objective > 0
                and float(self.y[kept].mean()) > float(self.y[rows].mean())
            ):
                box, rows = new, kept
                trajectory.append((box, rows))
            else:
                return box, rows


def run_prim(x: pd.DataFrame, y: np.ndarray, *, alpha: float, mass_min: float) -> PrimResult:
    """The peeling and pasting trajectory of the first PRIM box.

    Implements: M-F7-08, D-F7-021.

    Args:
        x: One row per future; float columns are real descriptors, string or categorical columns are categorical ones.
        y: The binary outcome of each future (1 where the futures are of interest).
        alpha: Peeling and pasting fraction, in (0, 0.5).
        mass_min: Smallest share of the futures a box may hold, in (0, 1].

    Raises:
        PrimError: the inputs disagree, `y` is not binary or a setting is outside its range.
    """
    y = np.asarray(y)
    if y.ndim != 1 or len(y) != len(x) or len(y) == 0:
        raise PrimError("one outcome per future is needed")
    if not set(np.unique(y)) <= {0, 1}:
        raise PrimError("the outcome must be binary")
    if not 0.0 < alpha < 0.5 or not 0.0 < mass_min <= 1.0:
        raise PrimError(
            f"alpha must be in (0, 0.5) and mass_min in (0, 1], got {alpha} and {mass_min}"
        )
    search = _Search(x.reset_index(drop=True), y.astype("float64"), alpha, mass_min)
    rows = np.arange(search.n)
    box = search.init.copy()
    trajectory = [(box, rows)]
    box, rows = search.peel(box, rows, trajectory)
    search.paste(box, rows, trajectory)
    return PrimResult(
        steps=tuple(search.step(i, b, r) for i, (b, r) in enumerate(trajectory)),
        n_futures=search.n,
        n_positive=int(y.sum()),
        real_descriptors=tuple(search.real),
        categorical_descriptors=tuple(search.categorical),
        dropped_descriptors=tuple(search.dropped),
    )
