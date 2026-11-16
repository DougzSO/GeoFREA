"""Download the World Bank price and exchange-rate indices used to convert Group 3 unit costs to constant 2024 USD (COMMAND 83).

usage: python scripts/fetch_conversion_indices.py [--out PATH] [--countries BRA IND PRT] [--from-year 2015]
                                                   [--manual-us-deflator 2024=119.03 2025=122.36 --manual-source TEXT --manual-note TEXT]

Writes one JSON file under GEOFREA_DATA_DIR (`external/world_bank/conversion_indices.json`) with, per indicator and country, the values by year, plus the
indicator names, the API endpoint, the `lastupdated` stamp of the source and the access date:

- `NY.GDP.DEFL.ZS`: GDP deflator (index, the same base year for every year of a country), also for the United States (`USA`), which converts a USD cost of a
  price year other than 2024 (DEC-071; `NY.GDP.DEFL.ZS` has no exchange rate for the United States, so `PA.NUS.FCRF` is fetched for `--countries` only);
- `PA.NUS.FCRF`: official exchange rate, local currency units per US dollar, period average.

The conversion of a cost of price year `y` to 2024 USD is `amount * deflator[2024] / deflator[y] / fx[2024]` (`lcoe_modeling/connection.py`). A year the
World Bank has not published yet is left out of the file, not estimated: F6 then refuses the cost that needs it.

If the API has no year of the US series (2025, say) or cannot be reached, `--manual-us-deflator YEAR=VALUE ...` records those values by hand under
`indicators["NY.GDP.DEFL.ZS"]["manual"]["USA"]` with their `source`, the date of collection and a note that the latest year may be provisional. The loader
(`lcoe_modeling/connection.py`) uses a manual value only for a year the API series lacks; it never replaces an API value.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

US_ISO = "USA"
DEFLATOR = "NY.GDP.DEFL.ZS"
PROVISIONAL_NOTE = "The latest year may be provisional and revised by the World Bank; the date of collection is recorded for that."
DEFAULT_OUT = Path("D:/Douglas/DOUTORADO/GeoFREA_data/external/world_bank/conversion_indices.json")
INDICATORS = {
    "NY.GDP.DEFL.ZS": "GDP deflator (base year varies by country)",
    "PA.NUS.FCRF": "Official exchange rate (LCU per US$, period average)",
}
API = "https://api.worldbank.org/v2/country/{countries}/indicator/{indicator}?format=json&date={first}:{last}&per_page=500"


def fetch(indicator: str, countries: list[str], first: int, last: int) -> tuple[dict, str]:
    url = API.format(countries=";".join(countries), indicator=indicator, first=first, last=last)
    last_error: Exception | None = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                payload = json.load(response)
            if len(payload) < 2 or not payload[1]:
                raise ValueError(f"{indicator}: the API returned no data ({payload[:1]})")
            by_country: dict[str, dict[str, float]] = {c: {} for c in countries}
            for row in payload[1]:
                if row["value"] is not None:
                    by_country[row["countryiso3code"]][row["date"]] = row["value"]
            return by_country, payload[0].get("lastupdated", "")
        except Exception as exc:  # noqa: BLE001 - retried, then reported
            last_error = exc
    raise RuntimeError(f"could not fetch {indicator}: {last_error}")


def parse_manual(pairs: list[str]) -> dict[str, float]:
    """`["2025=122.36", ...]` as `{"2025": 122.36}`; a malformed pair raises `ValueError`."""
    values: dict[str, float] = {}
    for pair in pairs:
        year, sep, value = pair.partition("=")
        if not sep or not year.strip().isdigit():
            raise ValueError(f"expected YEAR=VALUE, got {pair!r}")
        values[year.strip()] = float(value)
    return values


def manual_entry(pairs: list[str], source: str, note: str, collected: str) -> dict:
    """The block recorded by hand for the US deflator: the values, where they come from, when they were collected and a note."""
    if not source:
        raise ValueError("a manual entry needs its source (--manual-source)")
    return {"values": parse_manual(pairs), "source": source, "collected": collected, "note": note or PROVISIONAL_NOTE}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--countries", nargs="+", default=["BRA", "IND", "PRT"])
    parser.add_argument("--from-year", type=int, default=2015)
    parser.add_argument("--manual-us-deflator", nargs="+", metavar="YEAR=VALUE", help="record these US deflator values by hand (the API lacks them or is unreachable)")
    parser.add_argument("--manual-source", default="", help="where the manual values come from (required with --manual-us-deflator)")
    parser.add_argument("--manual-note", default="", help=f"default: {PROVISIONAL_NOTE!r}")
    args = parser.parse_args(argv)

    last_year = datetime.now(tz=UTC).date().year
    result = {
        "source": "World Bank Open Data, API v2",
        "accessed": datetime.now(tz=UTC).date().isoformat(),
        "indicators": {},
    }
    manual = (
        manual_entry(args.manual_us_deflator, args.manual_source, args.manual_note, result["accessed"])
        if args.manual_us_deflator
        else None
    )
    for indicator, name in INDICATORS.items():
        values, updated = fetch(indicator, args.countries, args.from_year, last_year)
        if indicator == DEFLATOR:
            try:  # the United States has its own call: it has no exchange rate, and a manual entry may stand in for an API that fails
                us_values, _ = fetch(indicator, [US_ISO], args.from_year, last_year)
                values[US_ISO] = us_values[US_ISO]
            except RuntimeError as exc:
                if manual is None:
                    raise
                print(f"{indicator} {US_ISO}: the API failed ({exc}); the manual entry is used")
                values[US_ISO] = {}
        result["indicators"][indicator] = {
            "name": name,
            "endpoint": API.format(countries=";".join(args.countries), indicator=indicator, first=args.from_year, last=last_year),
            "lastupdated": updated,
            "values": values,
        }
        if indicator == DEFLATOR and manual is not None:
            result["indicators"][indicator]["manual"] = {US_ISO: manual}
        for iso, series in values.items():
            years = sorted(series)
            if not years:
                print(f"{indicator} {iso}: no value from the API")
                continue
            print(f"{indicator} {iso}: {years[0]}-{years[-1]} ({len(years)} years); latest {series[years[-1]]:.4f}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
