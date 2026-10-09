"""Capacity-factor models selected by the `cf_model` string of the technology registry (A-04).

A model has two steps: `prepare` turns the candidate table into the per-cell quantities of the reference climate (once per land
scenario), and the prepared object's `member` returns the capacity factor of a member for the cells that have a forcing row. No
technology name appears here: the registry maps a technology to a model name, and a model reads the resource columns the
registry lists for the technology.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np
import pandas as pd

from geofrea.core.config_schemas import IecClassBound
from geofrea.technical_potential.iec_class import assign_by_mean_speed
from geofrea.technical_potential.power_curve import PowerCurve
from geofrea.technical_potential.rescale import solar_rescale_terms, wind_rescale_terms
from geofrea.technical_potential.solar import solar_cf_member, solar_cf_reference
from geofrea.technical_potential.weibull_cf import (
    equivalent_scale,
    weibull_mean_speed,
    wind_cf_member,
)
from geofrea.technical_potential.wind_profile import resource_at_hub_height


class CfModelError(RuntimeError):
    """A capacity-factor model cannot be built from the registry, the parameters or the candidate table (A-09)."""


class MissingParameterError(RuntimeError):
    """F5 cannot start because parameters, curves or registry rules are absent; the message lists every missing item (A-09)."""

    def __init__(self, country: str, technology: str, missing: Sequence[str]) -> None:
        self.country = country
        self.technology = technology
        self.missing = list(missing)
        super().__init__(
            f"F5 cannot run for {country} {technology}: {len(self.missing)} missing item(s): "
            + "; ".join(self.missing)
        )


@dataclass(frozen=True)
class CfSettings:
    """Resolved inputs of a model: nominal parameters by key, curves, class rule, resource layers, constants."""

    parameters: Mapping[str, float]
    curves: Mapping[str, PowerCurve]  # IEC class -> curve
    iec_class_rule: Sequence[IecClassBound] | None
    resource_layers: Sequence[str]
    rho0: float
    hours_per_day: float


class PreparedCf(Protocol):
    def member(
        self, rows: np.ndarray, delta_rsds: np.ndarray, d_t: np.ndarray, delta_wind: np.ndarray
    ) -> np.ndarray:
        """Capacity factor of a member for the candidate rows `rows` (positions in the candidate table)."""
        ...


class CfModel(Protocol):
    parameter_keys: tuple[str, ...]
    needs_curves: bool
    # the uncertain parameter that scales the stored energy in F6 (D-F6-012)
    sampled_parameter_key: str

    def prepare(self, candidates: pd.DataFrame, settings: CfSettings) -> PreparedCf: ...

    def rescale_terms(self, nominal: float, d_t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Offset and slope per cell such that the stored energy times `offset + slope * x` is the energy at the value `x` of
        `sampled_parameter_key`; the factor is 1 at `x = nominal` (D-F5-008, D-F6-012)."""
        ...


def _column(candidates: pd.DataFrame, name: str) -> np.ndarray:
    if name not in candidates.columns:
        raise CfModelError(
            f"candidate table has no column {name!r} (listed in the registry resource_layers)"
        )
    values = candidates[name].to_numpy(dtype="float64")
    if not np.isfinite(values).all():
        raise CfModelError(f"column {name!r} has non-finite values in the candidate cells")
    return values


@dataclass(frozen=True)
class _PvoutPrepared:
    cf0: np.ndarray
    gamma: float

    def member(self, rows, delta_rsds, d_t, delta_wind):
        return solar_cf_member(self.cf0[rows], delta_rsds, d_t, self.gamma)


class PvoutWithTemperature:
    """M-F5-02: `CF0 = pvout / 24`, member `CF0 * delta_rsds * (1 + gamma * dT)`."""

    parameter_keys = ("gamma",)
    needs_curves = False
    sampled_parameter_key = "gamma"

    def rescale_terms(self, nominal: float, d_t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return solar_rescale_terms(d_t, nominal)

    def prepare(self, candidates: pd.DataFrame, settings: CfSettings) -> PreparedCf:
        if len(settings.resource_layers) != 1:
            raise CfModelError(
                f"expected one resource layer (PVOUT), the registry lists {list(settings.resource_layers)}"
            )
        cf0 = solar_cf_reference(
            _column(candidates, settings.resource_layers[0]), settings.hours_per_day
        )
        return _PvoutPrepared(cf0=cf0, gamma=float(settings.parameters["gamma"]))


@dataclass(frozen=True)
class _WeibullPrepared:
    a_eq: np.ndarray
    k_h: np.ndarray
    class_of_cell: np.ndarray
    curves: Sequence[PowerCurve]  # in the order of the class rule
    eta_loss: float

    def member(self, rows, delta_rsds, d_t, delta_wind):
        out = np.empty(len(rows), dtype="float64")
        cls = self.class_of_cell[rows]
        for index, curve in enumerate(self.curves):
            sel = cls == index
            if sel.any():
                out[sel] = wind_cf_member(
                    self.a_eq[rows][sel], self.k_h[rows][sel], delta_wind[sel], curve, self.eta_loss
                )
        return out


_LAYER = re.compile(r"^(weibull_a|weibull_k|air_density)_(\d+)m$")


class WeibullWithAirDensity:
    """M-F5-03: Weibull speed distribution at hub height, density folded into the scale, IEC class per cell."""

    parameter_keys = ("eta_loss", "hub_height_m")
    needs_curves = True
    sampled_parameter_key = "eta_loss"

    def rescale_terms(self, nominal: float, d_t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return wind_rescale_terms(len(d_t), nominal)

    def prepare(self, candidates: pd.DataFrame, settings: CfSettings) -> PreparedCf:
        by_product: dict[str, dict[float, np.ndarray]] = {
            "weibull_a": {},
            "weibull_k": {},
            "air_density": {},
        }
        for name in settings.resource_layers:
            match = _LAYER.match(name)
            if match is None:
                raise CfModelError(
                    f"resource layer {name!r} is not <weibull_a|weibull_k|air_density>_<height>m"
                )
            by_product[match.group(1)][float(match.group(2))] = _column(candidates, name)
        a_h, k_h, rho_h = resource_at_hub_height(
            by_product["weibull_a"],
            by_product["weibull_k"],
            by_product["air_density"],
            float(settings.parameters["hub_height_m"]),
        )
        rule = settings.iec_class_rule
        if rule is None:
            raise CfModelError("the wind model needs the iec_class_rule of the registry")
        class_of_cell = assign_by_mean_speed(weibull_mean_speed(a_h, k_h), rule)
        return _WeibullPrepared(
            a_eq=equivalent_scale(a_h, rho_h, settings.rho0),
            k_h=k_h,
            class_of_cell=class_of_cell,
            curves=tuple(settings.curves[b.iec_class] for b in rule),
            eta_loss=float(settings.parameters["eta_loss"]),
        )


CF_MODELS: dict[str, CfModel] = {
    "pvout_with_temperature": PvoutWithTemperature(),
    "weibull_with_air_density": WeibullWithAirDensity(),
}


def get_cf_model(name: str) -> CfModel:
    """The model registered under `name`; an unknown name raises (A-09)."""
    try:
        return CF_MODELS[name]
    except KeyError:
        raise CfModelError(f"unknown cf_model {name!r} (known: {sorted(CF_MODELS)})") from None
