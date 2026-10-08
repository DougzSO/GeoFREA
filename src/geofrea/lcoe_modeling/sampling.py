"""Latin hypercube sampler of the uncertain parameters (M-F6-02, U-02, U-03, V5, A-12).

Parameters are sampled independently (V5): the hypercube stratifies each parameter's marginal and imposes no correlation between
parameters. Sample 0 is the nominal vector `s0` (M-F6-02). A draw is a pure function of the specification, the number of samples
and the seed, so a rerun with the same seed reproduces the design matrix exactly; the seed lives in `experiments.yaml` `sampler.seed`
and is recorded in the manifest. No phase uses this module yet (F6 will).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import qmc, triang

from geofrea.core.schemas import ParametersFile


class SamplingError(ValueError):
    """A parameter cannot be sampled: it has no value or no range (U-05), or the request is malformed."""


@dataclass(frozen=True)
class UncertainSpec:
    """One uncertain parameter: its nominal value and range, and the marginal distribution (U-05)."""

    name: str
    nominal: float
    low: float
    high: float
    distribution: str  # "uniform" | "triangular" (mode at the nominal value)

    def __post_init__(self) -> None:
        if not self.low <= self.nominal <= self.high:
            raise SamplingError(
                f"{self.name}: nominal {self.nominal} lies outside [{self.low}, {self.high}]"
            )
        if self.distribution not in ("uniform", "triangular"):
            raise SamplingError(f"{self.name}: unknown distribution {self.distribution!r}")


def specs_from_parameters(
    parameters: ParametersFile, country: str, technology: str, keys: Sequence[str]
) -> list[UncertainSpec]:
    """Specifications of the uncertain parameters `keys` of one country and technology, read from `parameters.json`.

    Raises:
        SamplingError: a key has no entry, no value or no range (nothing is invented).
    """
    params = getattr(parameters.countries[country].technologies, technology)
    specs = []
    for key in keys:
        vv = getattr(params, key, None)
        if vv is None or vv.value is None or vv.range is None:
            raise SamplingError(
                f"{country} {technology} {key}: no value or no range in parameters.json (U-05)"
            )
        specs.append(
            UncertainSpec(key, float(vv.value), vv.range.min, vv.range.max, vv.range.distribution)
        )
    return specs


def _transform(u: np.ndarray, spec: UncertainSpec) -> np.ndarray:
    width = spec.high - spec.low
    if width == 0.0:
        return np.full_like(u, spec.low)
    if spec.distribution == "uniform":
        return spec.low + u * width
    return triang.ppf(u, c=(spec.nominal - spec.low) / width, loc=spec.low, scale=width)


def draw_lhs(specs: Sequence[UncertainSpec], n_samples: int, seed: int) -> pd.DataFrame:
    """Design matrix: `n_samples` Latin hypercube draws plus the nominal vector as sample 0, one column per parameter.

    Implements: M-F6-02.

    Args:
        specs: The uncertain parameters, in column order.
        n_samples: Number of draws (the nominal vector is added as row 0, so the matrix has `n_samples + 1` rows).
        seed: Seed of the generator (A-12); the same inputs give the same matrix.

    Returns:
        DataFrame indexed by `sample` (0 = nominal vector), float64 columns named by parameter.
    """
    if n_samples <= 0:
        raise SamplingError("n_samples must be positive")
    if not specs:
        raise SamplingError("no uncertain parameter to sample")
    names = [s.name for s in specs]
    if len(set(names)) != len(names):
        raise SamplingError(f"duplicate parameter names: {names}")
    unit = qmc.LatinHypercube(d=len(specs), seed=seed).random(n_samples)
    columns = {s.name: _transform(unit[:, i], s) for i, s in enumerate(specs)}
    draws = pd.DataFrame(columns)
    nominal = pd.DataFrame({s.name: [s.nominal] for s in specs})
    design = pd.concat([nominal, draws], ignore_index=True)
    design.index.name = "sample"
    return design
