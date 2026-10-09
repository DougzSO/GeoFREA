"""The design matrix of one technology: the Latin hypercube draws as the kernel uses them (M-F6-02, D-F6-010)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from geofrea.lcoe_modeling.kernel import (
    ENERGY_PARAMETER_KEY,
    INTEGER_PARAMETER_KEYS,
    KERNEL_PARAMETER_KEYS,
    SampleInputs,
)
from geofrea.lcoe_modeling.sampling import UncertainSpec, draw_lhs


def build_design(specs: Sequence[UncertainSpec], n_samples: int, seed: int) -> pd.DataFrame:
    """The design matrix: `n_samples` draws plus the nominal vector as sample 0, with integer parameters rounded to whole years.

    Implements: M-F6-02, D-F6-010.

    The rounding is part of the design, so the stored matrix is what the kernel used. The nominal row is never changed.
    """
    design = draw_lhs(specs, n_samples, seed)
    for key in INTEGER_PARAMETER_KEYS:
        if key in design.columns:
            rounded = np.round(design[key].to_numpy())
            rounded[0] = design[key].to_numpy()[0]
            design[key] = rounded
    return design


def samples_from_design(
    design: pd.DataFrame, nominal: Mapping[str, float], energy_key: str
) -> SampleInputs:
    """Kernel samples from a design matrix: sampled parameters from their columns, the others repeated at their nominal value.

    Args:
        design: Output of `build_design`.
        nominal: Nominal value of every kernel key and of `energy_key`.
        energy_key: The parameter that scales the stored energy (`gamma` or `eta_loss`).
    """
    n = len(design)
    values: dict[str, np.ndarray | float] = {}
    for key in KERNEL_PARAMETER_KEYS:
        values[key] = design[key].to_numpy() if key in design.columns else float(nominal[key])
    values[ENERGY_PARAMETER_KEY] = (
        design[energy_key].to_numpy()
        if energy_key in design.columns
        else float(nominal[energy_key])
    )
    return SampleInputs.from_mapping(values, n)
