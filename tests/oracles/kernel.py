"""Reference implementations of the LCOE kernel: the closed form of the capital recovery factor and the textbook LCOE with an explicit loop over the years (M-F6-01, V-02). The tests compare the vectorised kernel with them."""

from __future__ import annotations

import numpy as np

from geofrea.lcoe_modeling.kernel import (
    CellInputs,
    SampleInputs,
    _check_energy_not_negative,
    annuity_factor,
)


def capital_recovery_factor(rate: np.ndarray | float, years: np.ndarray | float) -> np.ndarray:
    """`CRF = r / (1 - (1 + r)^-n)`, the inverse of the annuity factor; the limit `1/n` at `r = 0`.

    Implements: M-F6-01, V-02 (reference in the tests).
    """
    return 1.0 / annuity_factor(rate, years)


def lcoe_direct(cells: CellInputs, samples: SampleInputs) -> np.ndarray:
    """The textbook form of M-F6-01 with an explicit loop over the years, shape `(C, S)`; the reference of the tests.

    Implements: M-F6-01, V-02 (reference in the tests).
    """
    _check_energy_not_negative(cells, samples)
    out = np.empty((len(cells), len(samples)))
    for s in range(len(samples)):
        capex_kw = samples.capex_usd_per_kw[s]
        capex_total = (
            cells.p_mw * 1000.0 * capex_kw
            + cells.p_mw * cells.dist_grid_km * samples.grid_cost_usd_per_mw_km[s]
            + cells.p_mw * samples.substation_cost_usd_per_mw[s]
            + cells.dist_road_km * samples.road_cost_usd_per_km[s]
        )
        energy_1 = cells.energy_mwh * (
            cells.energy_offset + cells.energy_slope * samples.energy_parameter[s]
        )
        numerator = capex_total.copy()
        denominator = np.zeros(len(cells))
        r, d = samples.discount_rate[s], samples.degradation_rate[s]
        for t in range(1, int(samples.lifetime_years[s]) + 1):
            e_t = energy_1 * (1.0 - d) ** (t - 1)
            opex_t = samples.opex_fixed_frac[s] * cells.p_mw * 1000.0 * capex_kw + (
                samples.opex_var_usd_per_mwh[s] * e_t
            )
            numerator += opex_t / (1.0 + r) ** t
            denominator += e_t / (1.0 + r) ** t
        with np.errstate(divide="ignore", invalid="ignore"):
            value = numerator / denominator
        out[:, s] = np.where(denominator == 0.0, np.inf, value)
    return out
