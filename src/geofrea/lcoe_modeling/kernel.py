"""Pure LCOE kernel (M-F6-01, M-F6-05; D-F6-001, D-F6-007, D-F6-010; Group 3, `docs/thesis/methods/group3_connection_degradation.tex`).

No input or output happens here: the functions take arrays and return arrays, so F6 and F7 import them (M-F6-05). Units: power in
MW, energy in MWh per year, distances in km, costs in constant 2024 USD (S-07), rates as fractions, the LCOE in USD/MWh.

The textbook form of M-F6-01, for a cell `i` and a parameter sample `s` (the member is fixed by the energy that is passed in):

    C_inter     = (c_line*tau_grid*D_sub + C_bay + c_road*tau_road*D_road) / P_ref        [USD/MW, external connection]
    CAPEX_total = P*(1000*capex + C_inter)
    OPEX_t      = opex_fixed_frac*P*1000*capex + opex_var*E_t,   E_t = E*(1 - d)^(t - 1)*eta_trans,   t = 1..n
    LCOE        = [CAPEX_total + sum_t OPEX_t/(1 + r)^t] / [sum_t E_t/(1 + r)^t]

with `d = d_low + w*(d_high - d_low)` per cell and sample (the weight `w` in [0, 1] is the sampled quantity; PV cells take the bounds of their
thermal zone, wind cells one pair) and `eta_trans = max(0, 1 - alpha*tau_grid*D_sub)` (`alpha = 0` in the central case, so `eta_trans = 1`).

The kernel evaluates it in a factored form that is exact and needs no loop over the years. With the annuity of a constant cost,
`A_o = sum_t (1 + r)^-t`, and the degradation-weighted energy annuity, `A_e = sum_t (1 - d)^(t - 1) (1 + r)^-t`, the variable
O&M cancels against the denominator:

    LCOE = opex_var + P * [ U + D_sub * (c_line*tau_grid/P_ref) + D_road * (c_road*tau_road/P_ref) ] / ( E * eta_trans * A_e ),
    U    = 1000*capex*(1 + opex_fixed_frac*A_o) + C_bay/P_ref.

The numerator of the whole (cells x samples) block is one matrix product, `(C x 3) @ (3 x S)`; `A_e` is computed once per distinct pair of
degradation bounds and gathered per cell. The textbook form with an explicit loop over the years, the reference of the tests, is in
`tests/oracles/kernel.py`.

Energy of a sample: `E_c(s) = energy_mwh_c * (energy_offset_c + energy_slope_c * x_s)`, where `x_s` is the sampled value of the
parameter that scales the stored energy (`gamma` or `eta_loss`, D-F6-012) and offset and slope come from the capacity-factor model's
`rescale_terms`. The factor is 1 at the nominal value of that parameter.

Zero energy gives `LCOE = +inf` (D-F6-007). An optional energy floor per cell, `min_energy_mwh`, extends that rule: an entry whose sampled
energy is below the floor is `+inf` too, so F7 can mark the cell-members that fail `CF_min` without a second energy block (M-F7-01,
D-F7-007). A negative or non-finite energy or distance (a missing distance is never a zero cost), a non-finite input, a non-integer lifetime
or a rate outside its domain raises `KernelInputError` (A-09). A discount rate of zero is evaluated by the limit of the closed form (D-F6-010).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

KERNEL_VERSION = "2.0"

# the parameters of M-F6-01 that vary by sample; the energy parameter is passed separately
KERNEL_PARAMETER_KEYS = (
    "capex_usd_per_kw",
    "opex_fixed_frac",
    "opex_var_usd_per_mwh",
    "lifetime_years",
    "discount_rate",
    "degradation_weight",
    "line_cost_usd_per_km",
    "bay_cost_usd",
    "road_cost_usd_per_km",
    "tortuosity_grid",
    "tortuosity_road",
    "reference_project_mw",
    "transmission_loss_per_km",
)
ENERGY_PARAMETER_KEY = "energy_parameter"
# parameters the kernel sums over whole years (D-F6-010); the design matrix rounds them
INTEGER_PARAMETER_KEYS = ("lifetime_years",)


class KernelInputError(ValueError):
    """An input of the LCOE kernel is outside its domain (A-09)."""


def annuity_factor(rate: np.ndarray | float, years: np.ndarray | float) -> np.ndarray:
    """`sum_{t=1..n} (1 + r)^-t = (1 - (1 + r)^-n) / r`; the limit `n` at `r = 0`.

    Implements: M-F6-01, V-02.

    Raises:
        KernelInputError: `rate <= -1` or `years < 0`.
    """
    r = np.asarray(rate, dtype="float64")
    n = np.asarray(years, dtype="float64")
    if (r <= -1.0).any() or (n < 0).any():
        raise KernelInputError("annuity_factor: rate must be above -1 and years non-negative")
    with np.errstate(divide="ignore", invalid="ignore"):
        value = -np.expm1(-n * np.log1p(r)) / r
    return np.where(r == 0.0, n, value)


def energy_annuity_factor(
    rate: np.ndarray | float, degradation: np.ndarray | float, years: np.ndarray | float
) -> np.ndarray:
    """`sum_{t=1..n} (1 - d)^(t - 1) (1 + r)^-t`, the discounted energy of one MWh in year 1 with degradation `d`.

    With `q = (1 - d)/(1 + r)` the sum is `(1/(1 + r)) * (1 - q^n)/(1 - q)`; it is evaluated with `expm1` and `log1p` so that it stays
    accurate when `q` is close to 1, and equals `n/(1 + r)` when `q = 1`.

    Implements: M-F6-01, V-02.

    Raises:
        KernelInputError: `rate <= -1`, `degradation` outside `[0, 1)` or `years < 0`.
    """
    r = np.asarray(rate, dtype="float64")
    d = np.asarray(degradation, dtype="float64")
    n = np.asarray(years, dtype="float64")
    if (r <= -1.0).any() or (n < 0).any() or (d < 0).any() or (d >= 1.0).any():
        raise KernelInputError(
            "energy_annuity_factor: rate above -1, degradation in [0, 1) and non-negative years required"
        )
    log_q = np.log1p(-d) - np.log1p(r)
    with np.errstate(divide="ignore", invalid="ignore"):
        geometric = np.expm1(n * log_q) / np.expm1(log_q)
    return np.where(log_q == 0.0, n, geometric) / (1.0 + r)


@dataclass(frozen=True)
class CellInputs:
    """Per-cell inputs of one member, arrays of shape `(C,)`.

    `energy_mwh` is the annual energy stored by F5 for the member at the nominal value of the energy parameter; the sampled energy is
    `energy_mwh * (energy_offset + energy_slope * x_s)`. `dist_sub_km` is the distance to the nearest eligible substation (`D_sub`); the
    degradation of a cell and sample is `degradation_low + w_s * (degradation_high - degradation_low)`.
    """

    p_mw: np.ndarray
    dist_sub_km: np.ndarray
    dist_road_km: np.ndarray
    energy_mwh: np.ndarray
    energy_offset: np.ndarray
    energy_slope: np.ndarray
    degradation_low: np.ndarray
    degradation_high: np.ndarray

    def __post_init__(self) -> None:
        arrays = {
            name: np.asarray(getattr(self, name), dtype="float64")
            for name in self.__dataclass_fields__
        }
        for name, value in arrays.items():
            object.__setattr__(self, name, value)
        shapes = {value.shape for value in arrays.values()}
        if len(shapes) != 1 or len(next(iter(shapes))) != 1:
            raise KernelInputError(
                f"cell inputs must be 1-D arrays of one length, got {sorted(shapes)}"
            )
        for name, value in arrays.items():
            if not np.isfinite(value).all():
                raise KernelInputError(f"cell input {name} has non-finite values")
        for name in ("p_mw", "dist_sub_km", "dist_road_km", "energy_mwh"):
            if (arrays[name] < 0).any():
                raise KernelInputError(f"cell input {name} has negative values")
        low, high = arrays["degradation_low"], arrays["degradation_high"]
        if (low < 0).any() or (high >= 1).any() or (low > high).any():
            raise KernelInputError(
                "degradation bounds must satisfy 0 <= degradation_low <= degradation_high < 1"
            )

    def __len__(self) -> int:
        return int(self.p_mw.shape[0])

    def take(self, index: slice | np.ndarray) -> CellInputs:
        """The cells at `index` (a slice or an integer or boolean array)."""
        return CellInputs(
            **{name: getattr(self, name)[index] for name in self.__dataclass_fields__}
        )


@dataclass(frozen=True)
class SampleInputs:
    """Parameter samples, arrays of shape `(S,)`; `energy_parameter` is the sampled `gamma` or `eta_loss`."""

    capex_usd_per_kw: np.ndarray
    opex_fixed_frac: np.ndarray
    opex_var_usd_per_mwh: np.ndarray
    lifetime_years: np.ndarray
    discount_rate: np.ndarray
    degradation_weight: np.ndarray
    line_cost_usd_per_km: np.ndarray
    bay_cost_usd: np.ndarray
    road_cost_usd_per_km: np.ndarray
    tortuosity_grid: np.ndarray
    tortuosity_road: np.ndarray
    reference_project_mw: np.ndarray
    transmission_loss_per_km: np.ndarray
    energy_parameter: np.ndarray

    def __post_init__(self) -> None:
        arrays = {
            name: np.asarray(getattr(self, name), dtype="float64")
            for name in self.__dataclass_fields__
        }
        for name, value in arrays.items():
            object.__setattr__(self, name, value)
        shapes = {value.shape for value in arrays.values()}
        if len(shapes) != 1 or len(next(iter(shapes))) != 1:
            raise KernelInputError(
                f"sample inputs must be 1-D arrays of one length, got {sorted(shapes)}"
            )
        for name, value in arrays.items():
            if not np.isfinite(value).all():
                raise KernelInputError(f"sample input {name} has non-finite values")
        for name in (
            "capex_usd_per_kw",
            "opex_fixed_frac",
            "opex_var_usd_per_mwh",
            "line_cost_usd_per_km",
            "bay_cost_usd",
            "road_cost_usd_per_km",
            "tortuosity_grid",
            "tortuosity_road",
            "transmission_loss_per_km",
        ):
            if (arrays[name] < 0).any():
                raise KernelInputError(f"sample input {name} has negative values")
        if (arrays["reference_project_mw"] <= 0).any():
            raise KernelInputError("reference_project_mw must be positive")
        n = arrays["lifetime_years"]
        if (n < 1).any() or (n != np.round(n)).any():
            raise KernelInputError("lifetime_years must be whole years of at least 1 (D-F6-010)")
        if (arrays["discount_rate"] <= -1).any():
            raise KernelInputError("discount_rate must be above -1")
        if (arrays["degradation_weight"] < 0).any() or (arrays["degradation_weight"] > 1).any():
            raise KernelInputError("degradation_weight must lie in [0, 1]")

    def __len__(self) -> int:
        return int(self.capex_usd_per_kw.shape[0])

    def take(self, index: slice | np.ndarray) -> SampleInputs:
        """The samples at `index` (a slice or an integer or boolean array)."""
        return SampleInputs(
            **{name: getattr(self, name)[index] for name in self.__dataclass_fields__}
        )

    @classmethod
    def from_mapping(cls, values: Mapping[str, np.ndarray | float], n_samples: int) -> SampleInputs:
        """Samples from a mapping of the kernel keys and `energy_parameter`; a scalar is repeated `n_samples` times.

        Raises:
            KernelInputError: a key is missing, or an array does not have `n_samples` entries.
        """
        wanted = (*KERNEL_PARAMETER_KEYS, ENERGY_PARAMETER_KEY)
        missing = [k for k in wanted if k not in values]
        if missing:
            raise KernelInputError(f"sample values lack {missing}")
        columns = {}
        for key in wanted:
            column = np.asarray(values[key], dtype="float64")
            if column.ndim == 0:
                column = np.full(n_samples, float(column))
            elif column.shape != (n_samples,):
                raise KernelInputError(
                    f"{key}: expected {n_samples} samples, got shape {column.shape}"
                )
            columns[key] = column
        return cls(**columns)


def _check_energy_not_negative(cells: CellInputs, samples: SampleInputs) -> None:
    """The sampled energy is linear in the energy parameter, so its minimum over the samples sits at an extreme of that parameter."""
    if len(samples) == 0 or len(cells) == 0:
        return
    x = samples.energy_parameter
    at_low = cells.energy_offset + cells.energy_slope * x.min()
    at_high = cells.energy_offset + cells.energy_slope * x.max()
    if (cells.energy_mwh * np.minimum(at_low, at_high) < 0).any():
        raise KernelInputError("negative annual energy for some cell and sample (A-09)")


def _check_floor(cells: CellInputs, min_energy_mwh: np.ndarray) -> np.ndarray:
    floor = np.asarray(min_energy_mwh, dtype="float64")
    if floor.shape != (len(cells),):
        raise KernelInputError(f"min_energy_mwh needs one value per cell, got shape {floor.shape}")
    if np.isnan(floor).any() or (floor < 0).any():
        raise KernelInputError("min_energy_mwh must be non-negative (infinity allowed) and not NaN")
    return floor


def _energy_annuity_block(cells: CellInputs, samples: SampleInputs) -> np.ndarray:
    """The energy annuity per cell and sample, `(C, S)`, or `(1, S)` when every cell shares one pair of degradation bounds.

    `A_e` depends on the cell only through its pair of bounds, so it is evaluated once per distinct pair (`K` of them: the PV thermal zones,
    or one) and gathered per cell.
    """
    pairs, inverse = np.unique(
        np.column_stack([cells.degradation_low, cells.degradation_high]), axis=0, return_inverse=True
    )
    d = pairs[:, :1] + samples.degradation_weight[None, :] * (pairs[:, 1:] - pairs[:, :1])
    a_e = energy_annuity_factor(samples.discount_rate[None, :], d, samples.lifetime_years[None, :])
    if len(pairs) == 1:
        return a_e
    return a_e[np.asarray(inverse).reshape(-1)]


def lcoe_block(
    cells: CellInputs, samples: SampleInputs, min_energy_mwh: np.ndarray | None = None
) -> np.ndarray:
    """LCOE of every cell under every sample, shape `(C, S)`, USD2024/MWh.

    Implements: M-F6-01, M-F6-05, M-F7-01 (the energy floor).

    `min_energy_mwh` is an optional floor per cell, in MWh per year: an entry whose annual sampled energy (before discounting) is below its floor is `+inf`, as an entry
    of zero energy is. A floor of `0` changes nothing, a floor of `+inf` makes the whole row infeasible.

    Three temporaries of the block size are never alive together: the numerator block is built, the energy block is built beside it,
    the numerator is divided in place and the energy block is released, so the peak is two blocks plus a boolean mask.

    Raises:
        KernelInputError: an input is non-finite or outside its domain, or the sampled energy is negative.
    """
    _check_energy_not_negative(cells, samples)
    floor = _check_floor(cells, min_energy_mwh) if min_energy_mwh is not None else None
    r, n = samples.discount_rate, samples.lifetime_years
    a_o = annuity_factor(r, n)
    p_ref = samples.reference_project_mw
    u = 1000.0 * samples.capex_usd_per_kw * (1.0 + samples.opex_fixed_frac * a_o)
    u = u + samples.bay_cost_usd / p_ref
    left = np.column_stack(
        [cells.p_mw, cells.p_mw * cells.dist_sub_km, cells.p_mw * cells.dist_road_km]
    )
    right = np.vstack(
        [
            u,
            samples.line_cost_usd_per_km * samples.tortuosity_grid / p_ref,
            samples.road_cost_usd_per_km * samples.tortuosity_road / p_ref,
        ]
    )
    block = left @ right  # numerator: capital cost plus discounted fixed O&M, (C, S)

    energy = np.multiply.outer(cells.energy_mwh * cells.energy_slope, samples.energy_parameter)
    energy += (cells.energy_mwh * cells.energy_offset)[:, None]
    below_floor = (
        energy < floor[:, None] if floor is not None else None
    )  # annual energy, before discounting
    energy *= _energy_annuity_block(cells, samples)
    alpha = samples.transmission_loss_per_km
    if (alpha != 0.0).any():
        eta = 1.0 - np.multiply.outer(cells.dist_sub_km, alpha * samples.tortuosity_grid)
        np.maximum(eta, 0.0, out=eta)
        energy *= eta
        del eta
    with np.errstate(divide="ignore", invalid="ignore"):
        np.divide(block, energy, out=block)
    zero = energy == 0.0
    if below_floor is not None:
        zero |= below_floor
        del below_floor
    del energy
    if zero.any():
        np.copyto(block, np.inf, where=zero)
    del zero
    block += samples.opex_var_usd_per_mwh[None, :]
    return block
