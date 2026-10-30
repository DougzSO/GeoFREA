"""Capacity-factor models selected by the `cf_model` string of the technology registry (A-04).

A model has two steps: `prepare` turns the candidate table into the per-cell quantities of the reference climate (once per land
scenario), and the prepared object's `member` returns the capacity factor of a member for the cells that have a forcing row. No
technology name appears here: the registry maps a technology to a model name, and a model reads the resource columns the
registry lists for the technology.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np
import pandas as pd

from geofrea.core.config_schemas import ClassFlagRule
from geofrea.technical_potential.cf_table import cf_integral
from geofrea.technical_potential.iec_class import exceeds_class
from geofrea.technical_potential.pixel_inputs import CellPixels
from geofrea.technical_potential.power_curve import PowerCurve
from geofrea.technical_potential.rescale import solar_rescale_terms, wind_rescale_terms
from geofrea.technical_potential.solar import solar_cf_member, solar_cf_reference
from geofrea.technical_potential.weibull_cf import weibull_mean_speed, wind_cf_member
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
    """Resolved inputs of a model: nominal parameters by key, the reference turbine curve, class flag rule, resource layers, constants."""

    parameters: Mapping[str, float]
    curve: PowerCurve | None  # the single reference turbine (wind)
    class_flag: ClassFlagRule | None
    resource_layers: Sequence[str]
    rho0: float  # density of the standard atmosphere, used when the curve does not state its own
    t_star_k: float
    hours_per_day: float
    wind_cf_integral: str = "exact"  # `table` (cf_table, D-F5-039) or `exact` (the closed form); settings.yaml technical_potential.wind_cf_integral


class PreparedCf(Protocol):
    # Per candidate cell: True where the reference mean speed exceeds the class limit (fixed across members); `None` without a flag.
    class_flag: np.ndarray | None
    v_ave_ms: np.ndarray | None
    # Per candidate cell: the reference air density at the hub height, kg/m3; `None` for a model without a density input.
    rho_ref: np.ndarray | None

    def member(
        self, rows: np.ndarray, delta_rsds: np.ndarray, d_t: np.ndarray, delta_wind: np.ndarray
    ) -> np.ndarray:
        """Capacity factor of a member for the candidate rows `rows` (positions in the candidate table)."""
        ...


class CfModel(Protocol):
    parameter_keys: tuple[str, ...]
    needs_curves: bool
    # "cell": the model is evaluated on the cell-mean resources; "pixel": on every eligible 0.01 degree pixel, aggregated to the cell by the
    # eligible area of the pixel (`prepare_pixels`, D-F5-038)
    aggregation: str
    # the uncertain parameter that scales the stored energy in F6 (D-F6-012)
    sampled_parameter_key: str

    def prepare(self, candidates: pd.DataFrame, settings: CfSettings) -> PreparedCf: ...

    def prepare_pixels(
        self, candidates: pd.DataFrame, settings: CfSettings, pixels: CellPixels
    ) -> PreparedCf:
        """As `prepare`, with the capacity factor of a cell the eligible-area-weighted mean of the pixel capacity factors."""
        ...

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
    class_flag: np.ndarray | None = None
    v_ave_ms: np.ndarray | None = None
    rho_ref: np.ndarray | None = None

    def member(self, rows, delta_rsds, d_t, delta_wind):
        return solar_cf_member(self.cf0[rows], delta_rsds, d_t, self.gamma)


class PvoutWithTemperature:
    """M-F5-02: `CF0 = pvout / 24`, member `CF0 * delta_rsds * (1 + gamma * dT)`."""

    parameter_keys = ("gamma",)
    needs_curves = False
    aggregation = "cell"  # the model is linear in the resource, so the cell mean and the pixel mean agree (1e-16)
    sampled_parameter_key = "gamma"

    def prepare_pixels(
        self, candidates: pd.DataFrame, settings: CfSettings, pixels: CellPixels
    ) -> PreparedCf:
        raise CfModelError("the PVOUT model is evaluated on the cell means (aggregation 'cell')")

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
    a_h: np.ndarray
    k_h: np.ndarray
    rho_ref: np.ndarray
    curve: PowerCurve
    rho0: float
    t_star_k: float
    eta_loss: float
    class_flag: np.ndarray | None
    v_ave_ms: np.ndarray | None = None

    def member(self, rows, delta_rsds, d_t, delta_wind):
        return wind_cf_member(
            self.a_h[rows],
            self.k_h[rows],
            self.rho_ref[rows],
            d_t,
            delta_wind,
            self.curve,
            self.eta_loss,
            self.rho0,
            self.t_star_k,
        )


@dataclass(frozen=True)
class _WeibullPixelPrepared:
    """Wind capacity factor per eligible pixel, aggregated to the cell by the eligible area of the pixel (M-F5-03, D-F5-038).

    The class flag, the mean speed and the reference density stay those of the cell means (`cell`): they describe the cell and do not
    enter the capacity factor.
    """

    cell: _WeibullPrepared
    offsets: np.ndarray
    weight_km2: np.ndarray
    a_h: np.ndarray
    k_h: np.ndarray
    rho_pixel: np.ndarray  # pixel air density at hub height, kg/m3
    class_flag: np.ndarray | None
    v_ave_ms: np.ndarray | None
    rho_ref: np.ndarray  # of the cell means, for the density check
    integral: Callable[[np.ndarray, np.ndarray], np.ndarray] | None = None  # `(A, k) -> I`; None: the exact closed form

    def member(self, rows, delta_rsds, d_t, delta_wind):
        rows = np.asarray(rows, dtype="int64")
        d_t = np.asarray(d_t, dtype="float64")
        delta_wind = np.asarray(delta_wind, dtype="float64")
        counts = np.diff(self.offsets)[rows]
        out = np.empty(len(rows))
        ends = np.cumsum(counts)
        start = 0
        while start < len(rows):  # blocks of cells of at most PIXELS_PER_BLOCK pixels: the memory does not grow with the country
            before = ends[start - 1] if start else 0
            stop = max(int(np.searchsorted(ends, before + PIXELS_PER_BLOCK, side="right")), start + 1)
            block = slice(start, stop)
            n_pix = counts[block]
            cell_of = np.repeat(np.arange(stop - start), n_pix)
            first = np.repeat(self.offsets[rows[block]] - (np.cumsum(n_pix) - n_pix), n_pix)
            pix = first + np.arange(int(n_pix.sum()))
            cf = wind_cf_member(
                self.a_h[pix],
                self.k_h[pix],
                self.rho_pixel[pix],
                d_t[block][cell_of],
                delta_wind[block][cell_of],
                self.cell.curve,
                self.cell.eta_loss,
                self.cell.rho0,
                self.cell.t_star_k,
                self.integral,
            )
            weight = self.weight_km2[pix]
            total = np.bincount(cell_of, weights=weight, minlength=stop - start)
            out[block] = np.bincount(cell_of, weights=weight * cf, minlength=stop - start) / total
            start = stop
        return out


# pixels evaluated at once: about 100 MB of working arrays
PIXELS_PER_BLOCK = 1_000_000

_LAYER = re.compile(r"^(weibull_a|weibull_k|air_density)_(\d+)m$")


class WeibullWithAirDensity:
    """M-F5-03: Weibull speed distribution at hub height, one reference turbine, density of the member folded into the scale."""

    parameter_keys = ("eta_loss", "hub_height_m")
    needs_curves = True
    aggregation = "pixel"
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
        if settings.curve is None:
            raise CfModelError("the wind model needs the reference turbine curve of the registry")
        flag = None
        v_ave = None
        rule = settings.class_flag
        if rule is not None:
            height = float(rule.layer_height_m)
            if height not in by_product["weibull_a"]:
                raise CfModelError(
                    f"the class flag reads the {height:g} m layer, which the registry does not list"
                )
            v_ave = weibull_mean_speed(
                by_product["weibull_a"][height], by_product["weibull_k"][height]
            )
            flag = exceeds_class(v_ave, rule.mean_speed_threshold_ms)
        curve_rho0 = settings.curve.reference_density_kg_m3
        return _WeibullPrepared(
            a_h=a_h,
            k_h=k_h,
            rho_ref=rho_h,
            curve=settings.curve,
            rho0=settings.rho0 if curve_rho0 is None else float(curve_rho0),
            t_star_k=settings.t_star_k,
            eta_loss=float(settings.parameters["eta_loss"]),
            class_flag=flag,
            v_ave_ms=v_ave,
        )

    def prepare_pixels(
        self, candidates: pd.DataFrame, settings: CfSettings, pixels: CellPixels
    ) -> PreparedCf:
        cell = self.prepare(candidates, settings)
        by_product: dict[str, dict[float, np.ndarray]] = {
            "weibull_a": {},
            "weibull_k": {},
            "air_density": {},
        }
        for name in settings.resource_layers:
            match = _LAYER.match(name)
            if match is None or name not in pixels.resources:
                raise CfModelError(f"resource layer {name!r} has no pixel values")
            by_product[match.group(1)][float(match.group(2))] = np.asarray(
                pixels.resources[name], dtype="float64"
            )
        a_h, k_h, rho_h = resource_at_hub_height(
            by_product["weibull_a"],
            by_product["weibull_k"],
            by_product["air_density"],
            float(settings.parameters["hub_height_m"]),
        )
        if len(pixels.offsets) != len(candidates) + 1:
            raise CfModelError("the pixels are not those of the candidate table")
        return _WeibullPixelPrepared(
            cell=cell,
            offsets=pixels.offsets,
            weight_km2=pixels.weight_km2,
            a_h=a_h,
            k_h=k_h,
            rho_pixel=rho_h,
            class_flag=cell.class_flag,
            v_ave_ms=cell.v_ave_ms,
            rho_ref=cell.rho_ref,
            integral=None if settings.wind_cf_integral == "exact" else cf_integral(settings.curve, settings.wind_cf_integral),
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
