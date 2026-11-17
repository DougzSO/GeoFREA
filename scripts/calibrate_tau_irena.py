"""Measure, per country-technology pair, the bias between the published IRENA LCOE and the LCOE of the F6 kernel, and the discount rate that equates them (COMMAND 159).

Prints a table and files nothing: no production result is created, tau is not fixed, and no value is assumed. The reference values are those of
`config/irena_reference.yaml` (report 11, DEC-075 to DEC-080); a pair that has a `null` in a field it needs is refused and the fields are listed, the others run.

    python scripts/calibrate_tau_irena.py
    python scripts/calibrate_tau_irena.py --conversion-indices PATH     # the file with the US deflator, for the secondary run

The primary run (edition `irena_rpgc_2024`, DEC-076) builds, for each pair, one reference cell (`p_mw` = `reference_project_mw` of the country, distances zero,
`energy_mwh` = CF x 8760 x p_mw) and one sample (`capex_usd_per_kw` = the IRENA TIC, `opex_fixed_frac` = the IRENA O&M over the TIC, no variable O&M, the lifetime of the
edition, no connection cost: the TIC is total, no degradation: the inputs of the published LCOE), and calls `lcoe_block`. TIC and CF enter together, as IRENA publishes them,
without conversion: for solar the TIC is per kW DC and the CF is AC energy over DC capacity, the DC basis of F6 (DEC-087); for wind both are AC-to-AC. The F6 LCOE is evaluated at the central discount rate of F6 for the pair (`parameters.json`); the discount rate that gives the published LCOE is
found by root search (Brent) between 0 and 60 %. The DEC-072 range (the union of the regional WACC of 2024 plus or minus one point and the country point of 2021) is printed
with the rate, to say whether the rate is above its ceiling (OQ-104).

The secondary run compares the same F6 LCOE with the national LCOE of the edition `irena_rpgc_2025` (USD of 2025), converted with `to_usd_2024` and the US GDP deflator
(DEC-071, COMMAND 158). It needs the series of the United States in the conversion-indices file; without it the secondary lines are refused. It is labelled "secondary" and is
never part of the primary result or of any aggregate.

A pair whose reference value is a proxy (the solar capacity factor of Portugal, `regional_proxy`, DEC-078) is printed with the mark and is left out of every aggregate.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

import numpy as np
import yaml
from scipy.optimize import brentq

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from geofrea.core.config_loader import load_parameters
from geofrea.core.schemas import UnitCost
from geofrea.lcoe_modeling.connection import (
    ConversionError,
    load_conversion_indices,
    to_usd_2024,
)
from geofrea.lcoe_modeling.kernel import (
    KERNEL_PARAMETER_KEYS,
    CellInputs,
    SampleInputs,
    lcoe_block,
)

PAIRS = [("BRA", "solar"), ("BRA", "wind"), ("IND", "solar"), ("IND", "wind"), ("PRT", "solar"), ("PRT", "wind")]
PRIMARY, SECONDARY = "irena_rpgc_2024", "irena_rpgc_2025"
HOURS_PER_YEAR = 8760.0
RATE_SEARCH = (0.0, 0.60)
NEEDED = ("tic_usd_per_kw", "cf", "om_usd_per_kw_yr", "lcoe_usd_per_mwh")  # the fields of an edition-2024 pair the primary run needs, besides the lifetime


def _value(entry: dict | None) -> float | None:
    return None if entry is None else entry.get("value")


def pair_entries(ref: dict, edition: str, iso: str, tech: str) -> dict:
    return ref["editions"][edition]["pairs"].get(iso, {}).get(tech, {})


def missing_fields(ref: dict, iso: str, tech: str) -> list[str]:
    """The fields the primary run needs that are absent or `null` for the pair, as `edition:field`."""
    entries = pair_entries(ref, PRIMARY, iso, tech)
    missing = [f"{PRIMARY}:{name}" for name in NEEDED if _value(entries.get(name)) is None]
    if _value(ref["editions"][PRIMARY].get("life_years")) is None:
        missing.append(f"{PRIMARY}:life_years")
    return missing


def reference_cell(p_mw: float, cf: float, degradation: tuple[float, float] = (0.0, 0.0)) -> CellInputs:
    """One cell with no connection distance and the energy of the IRENA capacity factor: `energy_mwh = CF x 8760 x p_mw`; the energy is not rescaled."""
    return CellInputs(
        p_mw=np.array([p_mw]),
        dist_sub_km=np.zeros(1),
        dist_road_km=np.zeros(1),
        energy_mwh=np.array([cf * HOURS_PER_YEAR * p_mw]),
        energy_offset=np.ones(1),
        energy_slope=np.zeros(1),
        degradation_low=np.array([degradation[0]]),
        degradation_high=np.array([degradation[1]]),
    )


def f6_lcoe(rate: float, *, tic: float, om: float, life: int, p_mw: float, cf: float, degradation: tuple[float, float] = (0.0, 0.0)) -> float:
    """The LCOE of the F6 kernel (`lcoe_block`) for the IRENA inputs at `rate`, in USD/MWh."""
    values = dict.fromkeys(KERNEL_PARAMETER_KEYS, 0.0)
    values.update(
        capex_usd_per_kw=tic,
        opex_fixed_frac=om / tic,  # the O&M of IRENA in USD/kW per year as the fraction of the capex that F6 uses
        opex_var_usd_per_mwh=0.0,
        lifetime_years=float(life),
        discount_rate=rate,
        degradation_weight=0.0,
        tortuosity_grid=1.0,
        tortuosity_road=1.0,
        reference_project_mw=p_mw,
        energy_parameter=0.0,
    )
    block = lcoe_block(reference_cell(p_mw, cf, degradation), SampleInputs.from_mapping(values, 1))
    return float(block[0, 0])


def equating_rate(target: float, **kernel_inputs) -> float | None:
    """The discount rate in `RATE_SEARCH` at which the F6 LCOE equals `target`, or None when the target lies outside the values the search interval gives."""
    low, high = RATE_SEARCH
    f_low, f_high = f6_lcoe(low, **kernel_inputs) - target, f6_lcoe(high, **kernel_inputs) - target
    if f_low * f_high > 0:
        return None
    return float(brentq(lambda r: f6_lcoe(r, **kernel_inputs) - target, low, high, xtol=1e-10))


def dec072_range(ref: dict, iso: str, tech: str) -> tuple[float, float]:
    """The WACC range of DEC-072: the union of [regional 2024 - 1 point, regional 2024 + 1 point] and the country point of 2021."""
    regional = ref["wacc"]["regional_2024"][ref["region_of"][iso]][tech]["value"]
    country = ref["wacc"]["country_2021"][iso][tech]["value"]
    return min(regional - 0.01, country), max(regional + 0.01, country)


def fmt(value: float | None, spec: str = ".2f") -> str:
    return "n/a" if value is None else format(value, spec)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--reference", type=Path, default=REPO / "config" / "irena_reference.yaml")
    parser.add_argument("--parameters", type=Path, default=REPO / "config" / "parameters.json")
    parser.add_argument("--conversion-indices", type=Path, help="the file written by scripts/fetch_conversion_indices.py (default: the one of parameters.json under GEOFREA_DATA_DIR)")
    args = parser.parse_args(argv)

    ref = yaml.safe_load(args.reference.read_text(encoding="utf-8"))
    parameters = load_parameters(args.parameters)
    life = int(_value(ref["editions"][PRIMARY].get("life_years")) or 0)
    indices_path = args.conversion_indices
    if indices_path is None:
        try:
            from geofrea.core.paths import data_root

            indices_path = data_root() / parameters.countries["BRA"].connection.conversion_indices_path
        except Exception:  # noqa: BLE001 - the environment is not set: the secondary lines say so
            indices_path = None

    print("PRIMARY RUN: edition irena_rpgc_2024 (TIC, CF, O&M, LCOE, lifetime of the same edition, DEC-076); TIC and CF as published by IRENA, unconverted (solar: per kW DC and AC-DC; wind: AC-to-AC; DEC-087)")
    print("F6 LCOE = lcoe_block on one reference cell (distances 0, E = CF x 8760 x p_mw), no connection cost, no degradation; evaluated at the F6 central discount rate of the pair.\n")
    header = f"{'pair':<10}{'F6 LCOE':>9}{'published':>10}{'diff':>8}{'rate F6':>9}{'rate equal':>11}{'DEC-072 range':>16}  note"
    print(header)
    print("-" * len(header))
    rows: dict[tuple[str, str], dict] = {}
    refused: list[str] = []
    for iso, tech in PAIRS:
        missing = missing_fields(ref, iso, tech)
        if missing:
            refused.append(f"{iso} {tech}: REFUSED, null in {', '.join(missing)}")
            continue
        entries = pair_entries(ref, PRIMARY, iso, tech)
        tic, cf, om, published = (float(entries[k]["value"]) for k in NEEDED)
        tech_params = getattr(parameters.countries[iso].technologies, tech)
        p_mw = float(parameters.countries[iso].connection.reference_project_mw.value)
        rate_f6 = float(tech_params.discount_rate.value)
        kernel = {"tic": tic, "om": om, "life": life, "p_mw": p_mw, "cf": cf}
        f6 = f6_lcoe(rate_f6, **kernel)
        rate_eq = equating_rate(published, **kernel)
        low, high = dec072_range(ref, iso, tech)
        proxy = bool(entries["cf"].get("regional_proxy"))
        rows[(iso, tech)] = {"f6": f6, "published": published, "rate_f6": rate_f6, "rate_eq": rate_eq, "range": (low, high), "proxy": proxy, "kernel": kernel, "params": tech_params, "p_mw": p_mw, "tic": tic, "om": om}
        note = "regional_proxy (left out of every aggregate)" if proxy else ""
        if rate_eq is None:
            note = (note + "; " if note else "") + "no rate in 0-60 % gives the published LCOE"
        elif rate_eq > high:
            note = (note + "; " if note else "") + "rate above the ceiling of DEC-072 (OQ-104)"
        print(
            f"{iso + ' ' + tech:<10}{f6:>9.2f}{published:>10.2f}{f6 - published:>8.2f}{rate_f6 * 100:>8.2f}%{fmt(None if rate_eq is None else rate_eq * 100):>10}%"
            f"{f'{low * 100:.2f}-{high * 100:.2f}%':>16}  {note}"
        )
    for line in refused:
        print(line)

    counted = [r for r in rows.values() if not r["proxy"]]
    if counted:
        diffs = [r["f6"] - r["published"] for r in counted]
        print(f"\naggregate of the primary run over {len(counted)} pairs (regional_proxy pairs left out): mean diff {statistics.mean(diffs):+.2f} USD/MWh, median {statistics.median(diffs):+.2f}")

    print("\nSECONDARY RUN (labelled secondary, not part of the primary result): F6 LCOE of the primary run against the national LCOE of irena_rpgc_2025, converted to USD 2024 with to_usd_2024 (DEC-071)")
    secondary_header = f"{'pair':<10}{'F6 LCOE':>9}{'2025 (USD25)':>14}{'2025 (USD24)':>14}{'diff':>8}{'rate equal':>11}  note"
    print(secondary_header)
    print("-" * len(secondary_header))
    for iso, tech in PAIRS:
        row = rows.get((iso, tech))
        entry = pair_entries(ref, SECONDARY, iso, tech).get("lcoe_usd_per_mwh")
        if row is None:
            print(f"{iso + ' ' + tech:<10}refused: the primary run of the pair was refused")
            continue
        if _value(entry) is None:
            print(f"{iso + ' ' + tech:<10}refused: null in {SECONDARY}:lcoe_usd_per_mwh")
            continue
        try:
            if indices_path is None:
                raise ConversionError("no conversion-indices file (set GEOFREA_DATA_DIR or pass --conversion-indices)")
            indices = load_conversion_indices(indices_path, iso)
            cost = UnitCost.model_validate(
                {"value": entry["value"], "low": entry["value"], "high": entry["value"], "unit": "USD/MWh", "currency": entry["currency"], "scale": 1.0, "per": "km", "price_year": entry["price_year"], "status": "sourced"}
            )
            converted = to_usd_2024(float(entry["value"]), cost, indices)
        except ConversionError as exc:
            print(f"{iso + ' ' + tech:<10}refused: {exc}")
            continue
        eq = equating_rate(converted, **row["kernel"])
        print(f"{iso + ' ' + tech:<10}{row['f6']:>9.2f}{entry['value']:>14.2f}{converted:>14.2f}{row['f6'] - converted:>8.2f}{fmt(None if eq is None else eq * 100):>10}%  secondary")

    print("\nAUDIT (item 6 of COMMAND 159)")
    print("(d) O&M, IRENA against the central O&M of F6 (the primary run uses the IRENA one only):")
    print(f"{'pair':<10}{'IRENA USD/kW/yr':>17}{'IRENA frac of TIC':>19}{'F6 USD/kW/yr':>14}{'F6 frac of capex':>18}")
    for (iso, tech), row in rows.items():
        p = row["params"]
        f6_frac = float(p.opex_fixed_frac.value)
        f6_capex = float(p.capex_usd_per_kw.value)
        print(f"{iso + ' ' + tech:<10}{row['om']:>17.2f}{row['om'] / row['tic']:>19.5f}{f6_frac * f6_capex:>14.2f}{f6_frac:>18.5f}")
    sample = next(iter(rows.values()), None)
    note = next(iter(rows.values()))["params"].discount_rate.note if sample else ""
    print(f"(a) discount_rate of F6 is REAL, not nominal: parameters.json says \"{note}\"; the kernel discounts constant-price cash flows, with no inflation escalation (`lcoe_modeling/kernel.py`).")
    print("(b) the power basis of `lcoe_block` is none by itself: it divides P x 1000 x capex by the energy it is given. F6 gives it DC capacity (D-F6-028: the solar capacity factor is PVOUT in kWh/kWp/day / 24, per kW DC);")
    print("    the calibration gives it the TIC and the CF of IRENA together, as published and unconverted: the solar TIC per kW DC and the solar CF AC-DC (IRENA 2024, p. 92 footnote 27 and p. 99 footnote 32), the same DC basis as F6, so no DC/AC conversion applies when tau is applied to the cells (DEC-087, OQ-105).")
    print("(c) construction period: none. The capital cost is spent at t = 0, undiscounted, and O&M and energy run for t = 1..n with the factor (1 + r)^-t (kernel docstring, M-F6-01); there is no interest during construction.")
    print("    degradation: the energy of year t is E x (1 - d)^(t - 1), from the first year, with d = d_low + w (d_high - d_low) per cell and sample; the central rate is the lower bound (median of the PV zone, newer vintages for wind).")
    print("    The calibration uses d = 0 (the inputs of the published LCOE). For comparison, the F6 LCOE at its own central rate with the F6 degradation (not used above):")
    print(f"{'pair':<10}{'F6 degradation (central, F6)':<42}{'LCOE d=low':>11}{'LCOE d=high':>13}")
    for (iso, tech), row in rows.items():
        p = row["params"]
        wind_central = getattr(p, "degradation_rate", None)
        if tech == "wind":
            rate = float(wind_central.value)
            bounds, text = (rate, rate), f"wind {rate:.4f}/yr"
        else:
            medians = [z.median for z in p.degradation_by_zone.zones.values()]
            bounds, text = (min(medians), max(medians)), f"PV zones T1-T7 medians {min(medians):.4f} to {max(medians):.4f}/yr"
        low = f6_lcoe(row["rate_f6"], **row["kernel"], degradation=(bounds[0], bounds[0]))
        high = f6_lcoe(row["rate_f6"], **row["kernel"], degradation=(bounds[1], bounds[1]))
        print(f"{iso + ' ' + tech:<10}{text:<42}{low:>11.2f}{high:>13.2f}")
    print("\nThe discount rates of the 'rate equal' column are the values for OQ-104.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
