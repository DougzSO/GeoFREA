"""Group 3 inputs of F6: unit costs of the external connection in 2024 USD, the degradation bounds of each cell, and the checks that refuse a run.

The connection costs are stored per project in the currency and price year of their source (`UnitCost`, parameters.json). Here they become constant
2024 USD with the national GDP deflator and the 2024 average exchange rate (World Bank `NY.GDP.DEFL.ZS` and `PA.NUS.FCRF`, file written by
`scripts/fetch_conversion_indices.py`):

    usd_2024 = amount * scale * deflator[2024] / deflator[price_year] / fx[2024]

and the sampling range is converted the same way. A value in USD of price year 2024 needs no index. Nothing is estimated: a missing index, a missing
price year or a cost still `to_be_sourced` is a problem, and F6 refuses to run while one exists (`group3_problems`).

Implements: M-F6-08 (Group 3 connection cost and degradation, `docs/thesis/methods/group3_connection_degradation.tex`), A-09.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from geofrea.core.constants import PRICE_BASE_YEAR_USD
from geofrea.core.pv_zones import FLEET_TOP_ZONE, NO_ZONE, zone_degradation_bounds
from geofrea.core.schemas import ConnectionParams, UnitCost

DEFLATOR = "NY.GDP.DEFL.ZS"
EXCHANGE_RATE = "PA.NUS.FCRF"
LONG_DISTANCE_SHARE_OF = "dist_sub_capped_share"
# the kernel keys that Group 3 provides, in the order of `KERNEL_PARAMETER_KEYS`
SAMPLED_KEYS = (
    "degradation_weight",
    "line_cost_usd_per_km",
    "bay_cost_usd",
    "road_cost_usd_per_km",
    "tortuosity_grid",
    "tortuosity_road",
)
OPEN_QUESTION_COSTS = "OQ-001"
EFFICIENCY_WARNING_BELOW = 0.9  # a cell whose transmission efficiency falls under this is reported (sensitivity transmission_losses)


class ConversionError(RuntimeError):
    """A cost cannot be converted to 2024 USD: a missing index, price year or value."""


@dataclass(frozen=True)
class ConversionIndices:
    """World Bank series of one country: GDP deflator and exchange rate (local currency units per US dollar) by year."""

    iso: str
    deflator: Mapping[int, float]
    exchange_rate: Mapping[int, float]
    source: str
    accessed: str

    def factor(self, price_year: int, target_year: int = PRICE_BASE_YEAR_USD) -> float:
        """Local-currency amount of `price_year` to 2024 US dollars, as a multiplier."""
        missing = [
            f"{DEFLATOR} {y}" for y in (price_year, target_year) if y not in self.deflator
        ] + ([f"{EXCHANGE_RATE} {target_year}"] if target_year not in self.exchange_rate else [])
        if missing:
            raise ConversionError(f"{self.iso}: conversion index missing: {', '.join(missing)}")
        return self.deflator[target_year] / self.deflator[price_year] / self.exchange_rate[target_year]


def load_conversion_indices(path: Path, iso: str) -> ConversionIndices:
    """Indices of `iso` from the JSON written by `scripts/fetch_conversion_indices.py`.

    Raises:
        ConversionError: the file is absent or has no series for the country.
    """
    path = Path(path)
    if not path.is_file():
        raise ConversionError(
            f"conversion indices not found: {path}; run scripts/fetch_conversion_indices.py (World Bank {DEFLATOR}, {EXCHANGE_RATE})"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        deflator = {int(y): float(v) for y, v in data["indicators"][DEFLATOR]["values"][iso].items()}
        fx = {int(y): float(v) for y, v in data["indicators"][EXCHANGE_RATE]["values"][iso].items()}
    except KeyError as exc:
        raise ConversionError(f"{path}: no {exc} series for {iso}") from exc
    return ConversionIndices(iso, deflator, fx, data.get("source", ""), data.get("accessed", ""))


def to_usd_2024(amount: float, cost: UnitCost, indices: ConversionIndices | None) -> float:
    """`amount`, in the `unit` of `cost`, as constant 2024 USD per km or per bay.

    Raises:
        ConversionError: the price year is null, or the index the conversion needs is absent.
    """
    if cost.price_year is None:
        raise ConversionError(f"price_year is null (status {cost.status!r}): confirm the price base year of {cost.source}")
    in_currency = amount * cost.scale
    if cost.currency == "USD" and cost.price_year == PRICE_BASE_YEAR_USD:
        return in_currency
    if indices is None:
        raise ConversionError("no conversion indices")
    if cost.currency == "USD":
        raise ConversionError("a USD cost of a price year other than 2024 needs a US deflator, which is not loaded")
    return in_currency * indices.factor(cost.price_year)


@dataclass(frozen=True)
class DegradationModel:
    """Degradation bounds of a technology: one pair, or one pair per PVCZ zone for PV; the central rate is the lower bound.

    A cell takes `d_low + w * (d_high - d_low)` with the sampled weight `w` in [0, 1]. `by_zone` maps the zone number (1 to 7; hotter zones take 7)
    to its bounds; `single` is the pair of a technology without zones.
    """

    single: tuple[float, float] | None
    by_zone: Mapping[int, tuple[float, float]] | None

    def with_hot_zone_rate(self, rate: float, from_zone: int) -> DegradationModel:
        """The model of the sensitivity `pv_hot_zone_degradation`: zones `from_zone` and above take `(rate, rate)`, the others keep their bounds."""
        if self.by_zone is None:
            raise ConversionError("the hot-zone sensitivity applies to a technology with degradation by zone")
        return DegradationModel(
            single=None,
            by_zone={z: ((rate, rate) if z >= from_zone else bounds) for z, bounds in self.by_zone.items()},
        )

    def bounds_for_cells(self, zone: np.ndarray | None, n_cells: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """`(low, high, has_bounds)` per cell; a PV cell with no zone has no bounds (it is excluded and counted)."""
        if self.by_zone is None:
            low, high = self.single
            return np.full(n_cells, low), np.full(n_cells, high), np.ones(n_cells, dtype=bool)
        if zone is None:
            raise ConversionError("the candidates table has no pvcz_zone column: F3 must run again (Group 3)")
        capped = np.where(np.asarray(zone) > FLEET_TOP_ZONE, FLEET_TOP_ZONE, np.asarray(zone))
        low = np.zeros(n_cells)
        high = np.zeros(n_cells)
        known = capped != NO_ZONE
        for z, (lo, hi) in self.by_zone.items():
            at = capped == z
            low[at], high[at] = lo, hi
        return low, high, known


def _pv_zone_bounds(zones: Mapping[str, object]) -> dict[int, tuple[float, float]]:
    return {int(name[1:]): zone_degradation_bounds({"median": z.median, "mean": z.mean}) for name, z in zones.items()}


@dataclass(frozen=True)
class Group3:
    """What F6 takes from the Group 3 parameters of one country and technology."""

    nominal: dict[str, float]  # kernel keys of Group 3 at their nominal value
    ranges: dict[str, tuple[float, float, str]]  # sampled keys -> (low, high, distribution)
    degradation: DegradationModel
    long_distance_flag_km: float
    loss_sensitivity_per_km: tuple[float, float]  # the range of the named scenario `transmission_losses`
    hot_zone_sensitivity: tuple[float, int] | None = None  # (rate, first zone) of the named scenario `pv_hot_zone_degradation`


def group3_problems(iso: str, technology: str, connection: ConnectionParams | None, tech_params: object, indices_dir: Path | None = None) -> list[str]:
    """Every reason Group 3 cannot feed F6 for this country and technology, as messages for `LcoeMissingInputError` (empty when it can).

    Implements: A-09, M-F6-08.
    """
    if connection is None:
        return [f"connection (no `connection` block in parameters.json for {iso}, Group 3; {OPEN_QUESTION_COSTS})"]
    problems: list[str] = []
    for name in ("line_cost_per_km", "bay_cost", "road_cost_per_km"):
        cost: UnitCost = getattr(connection, name)
        if cost.value is None:
            suffix = f"; {cost.open_question}" if cost.open_question else f"; {OPEN_QUESTION_COSTS}"
            problems.append(f"{name} (no value, status {cost.status}{suffix})")
        elif cost.price_year is None:
            problems.append(f"{name} price_year (null, status {cost.status}: confirm the base year of {cost.source})")
    if hasattr(tech_params, "degradation_by_zone"):  # a technology whose degradation follows the thermal zone of the cell (A-04: no technology name)
        zones = tech_params.degradation_by_zone
        if zones is None or not zones.zones:
            problems.append("degradation_by_zone (no zone rates: run scripts/derive_pv_degradation_by_zone.py)")
    else:
        entry = getattr(tech_params, "degradation_rate", None)
        if entry is None or entry.value is None or entry.range is None:
            problems.append("degradation_rate (no value or range)")
        elif entry.range.min < 0 or entry.range.max >= 1:
            problems.append(
                f"degradation_rate range [{entry.range.min}, {entry.range.max}] (degradation outside [0, 1))"
            )
    return problems


def resolve_group3(
    iso: str,
    technology: str,
    connection: ConnectionParams,
    tech_params: object,
    indices: ConversionIndices | None,
) -> Group3:
    """The Group 3 nominal values, sampling ranges and degradation model, with the costs in 2024 USD.

    Call `group3_problems` first; this raises `ConversionError` for what it cannot convert.
    """
    nominal: dict[str, float] = {}
    ranges: dict[str, tuple[float, float, str]] = {}
    for kernel_key, name in (
        ("line_cost_usd_per_km", "line_cost_per_km"),
        ("bay_cost_usd", "bay_cost"),
        ("road_cost_usd_per_km", "road_cost_per_km"),
    ):
        cost: UnitCost = getattr(connection, name)
        nominal[kernel_key] = to_usd_2024(cost.value, cost, indices)
        ranges[kernel_key] = (to_usd_2024(cost.low, cost, indices), to_usd_2024(cost.high, cost, indices), "uniform")
    for kernel_key, entry in (
        ("tortuosity_grid", connection.tortuosity_grid),
        ("tortuosity_road", connection.tortuosity_road),
    ):
        nominal[kernel_key] = float(entry.value)
        ranges[kernel_key] = (entry.range.min, entry.range.max, entry.range.distribution)
    nominal["reference_project_mw"] = float(connection.reference_project_mw.value)
    nominal["transmission_loss_per_km"] = float(connection.transmission_loss_per_km.value)

    if hasattr(tech_params, "degradation_by_zone"):
        degradation = DegradationModel(single=None, by_zone=_pv_zone_bounds(tech_params.degradation_by_zone.zones))
        nominal["degradation_weight"] = 0.0
    else:
        entry = tech_params.degradation_rate
        low, high = entry.range.min, entry.range.max
        degradation = DegradationModel(single=(low, high), by_zone=None)
        nominal["degradation_weight"] = 0.0 if high == low else (float(entry.value) - low) / (high - low)
    ranges["degradation_weight"] = (0.0, 1.0, "uniform")
    sensitivity = connection.transmission_loss_per_km_sensitivity
    hot_zone = None
    if hasattr(tech_params, "degradation_by_zone") and tech_params.degradation_by_zone.hot_zone_sensitivity is not None:
        hz = tech_params.degradation_by_zone.hot_zone_sensitivity
        hot_zone = (hz.rate, hz.applies_from_zone)
    return Group3(
        nominal=nominal,
        ranges=ranges,
        degradation=degradation,
        long_distance_flag_km=float(connection.long_distance_flag_km.value),
        loss_sensitivity_per_km=(sensitivity.range.min, sensitivity.range.max) if sensitivity.range else (sensitivity.value,) * 2,
        hot_zone_sensitivity=hot_zone,
    )


def transmission_efficiency_report(dist_sub_km: np.ndarray, tortuosity_grid: float, loss_per_km: float) -> tuple[float, int]:
    """`(minimum efficiency, number of cells below 0.9)` of `eta = max(0, 1 - alpha * tau * D_sub)`, for the warning of the loss sensitivity."""
    eta = np.maximum(0.0, 1.0 - loss_per_km * tortuosity_grid * np.asarray(dist_sub_km, dtype="float64"))
    return float(eta.min()) if eta.size else 1.0, int((eta < EFFICIENCY_WARNING_BELOW).sum())
