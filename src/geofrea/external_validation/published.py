"""Published national estimates beside F5's potential (M-F7b-03, D-F7b-004, OQ-057).

`config/published_potential.yaml` holds the author's entries (source, year, definition, tier); it is empty until OQ-057 closes and only F7b reads
it. Nothing is computed from a published number: the table puts it beside F5's central-scenario potential at `m0` and the land interval, and
says whether the definition is a technical potential, as F5's is.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "config" / "published_potential.yaml"
UNITS = ("GW", "TWh_per_year")


class PublishedEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country: str
    technology: str
    value: float
    unit: Literal["GW", "TWh_per_year"]
    source: str
    year: int
    definition: Literal["technical", "economic", "resource", "other"]
    tier: str
    note: str | None = None


class PublishedFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[PublishedEntry]


def load_published(path: Path | None = None) -> list[PublishedEntry]:
    """The entries of the file (empty while OQ-057 is open).

    Raises:
        FileNotFoundError: the file is absent.
    """
    path = Path(path or DEFAULT_PATH)
    if not path.is_file():
        raise FileNotFoundError(f"{path} is absent (M-F7b-03, OQ-057)")
    return PublishedFile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8"))).entries


def national_potential(table: pd.DataFrame, reference: str, unit: str) -> float:
    """The sum over the cells of the reference member, in GW or in TWh per year."""
    rows = table[table["member"].astype(str) == reference]
    if unit == "GW":
        return float(rows["P_MW"].sum() / 1000.0)
    return float(rows["E_MWh"].sum() / 1.0e6)


def comparison_rows(
    entries: list[PublishedEntry],
    iso: str,
    potentials: dict[str, dict[str, pd.DataFrame]],
    reference: str,
) -> list[dict]:
    """One row per entry of this country whose technology was run; `potentials[technology][scenario]` are the F5 tables."""
    rows = []
    for entry in entries:
        if entry.country != iso or entry.technology not in potentials:
            continue
        by_scenario = potentials[entry.technology]
        value = {s: national_potential(t, reference, entry.unit) for s, t in by_scenario.items()}
        rows.append(
            {
                "technology": entry.technology,
                "source": entry.source,
                "year": entry.year,
                "definition": entry.definition,
                "tier": entry.tier,
                "unit": entry.unit,
                "published_value": entry.value,
                "f5_central_m0": value["central"],
                "f5_restrictive_m0": value["restrictive"],
                "f5_permissive_m0": value["permissive"],
                "definition_matches": entry.definition == "technical",
                "note": entry.note,
            }
        )
    return rows
