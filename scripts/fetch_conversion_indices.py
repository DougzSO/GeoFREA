"""Download the World Bank price and exchange-rate indices used to convert Group 3 unit costs to constant 2024 USD (COMMAND 83).

usage: python scripts/fetch_conversion_indices.py [--out PATH] [--countries BRA IND PRT] [--from-year 2015]

Writes one JSON file under GEOFREA_DATA_DIR (`external/world_bank/conversion_indices.json`) with, per indicator and country, the values by year, plus the
indicator names, the API endpoint, the `lastupdated` stamp of the source and the access date:

- `NY.GDP.DEFL.ZS`: GDP deflator (index, the same base year for every year of a country);
- `PA.NUS.FCRF`: official exchange rate, local currency units per US dollar, period average.

The conversion of a cost of price year `y` to 2024 USD is `amount * deflator[2024] / deflator[y] / fx[2024]` (`lcoe_modeling/connection.py`). A year the
World Bank has not published yet is left out of the file, not estimated: F6 then refuses the cost that needs it.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--countries", nargs="+", default=["BRA", "IND", "PRT"])
    parser.add_argument("--from-year", type=int, default=2015)
    args = parser.parse_args(argv)

    last_year = datetime.now(tz=UTC).date().year
    result = {
        "source": "World Bank Open Data, API v2",
        "accessed": datetime.now(tz=UTC).date().isoformat(),
        "indicators": {},
    }
    for indicator, name in INDICATORS.items():
        values, updated = fetch(indicator, args.countries, args.from_year, last_year)
        result["indicators"][indicator] = {
            "name": name,
            "endpoint": API.format(countries=";".join(args.countries), indicator=indicator, first=args.from_year, last=last_year),
            "lastupdated": updated,
            "values": values,
        }
        for iso, series in values.items():
            years = sorted(series)
            print(f"{indicator} {iso}: {years[0]}-{years[-1]} ({len(years)} years); latest {series[years[-1]]:.4f}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
