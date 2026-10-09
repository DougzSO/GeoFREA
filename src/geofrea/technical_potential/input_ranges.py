"""F5 validates its resource and distance inputs against the sanity ranges of `config/audit.yaml` (V-04, second half: "raise in F5").

F1b reports a value outside a range; F5 stops. The candidate-cell tables carry the inputs of the capacity-factor models (Weibull A and
k, air density, PVOUT) and the two distances. Each column is checked against:

- PVOUT: `layers.solar.sanity_range` of `audit.yaml` (the country override wins, as in F1b);
- air density at height `h`: the ISO 2533 envelope of the country's elevation span at `h`, widened by the declared relative
  quality-control tolerance (`derived_ranges.air_density`, `siting_layers/sanity.py`);
- distance to the grid and to the roads: `[0, diagonal of the country's bounding box]`;
- Weibull A and k: no range exists yet (OQ-053). A layer without a range is reported as a **warning**, never an error, and its values
  are not checked here.

A value outside a range, or not finite, raises `InputRangeError`, naming the technology, scenario, layer, how many candidate cells,
the extreme values, the range and where it comes from. Nothing is clipped or corrected (A-09).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from geofrea.data_quality_audit.schemas import AuditConfig
from geofrea.siting_layers.sanity import CountryGeometry, SanityError, derived_range, pvout_range

logger = logging.getLogger("geofrea.technical_potential.input_ranges")

DISTANCE_COLUMNS = ("dist_grid_km", "dist_road_km")
_PVOUT_COLUMN = "pvout_kwh_kwp_day"
_HEIGHT_COLUMN = re.compile(r"^(weibull_a|weibull_k|air_density)_(\d+)m$")
# The candidate tables hold area-weighted means of pixels, so a value equal to a bound can differ from it by floating-point rounding
# (the synthetic country has a PVOUT range of one value, [4.5, 4.5]). This slack is rounding, not a quality-control tolerance.
ROUNDING_SLACK_REL = 1e-9


class InputRangeError(ValueError):
    """An F5 input is outside the sanity range of its layer, or the registry names a layer that has no declared range (V-04)."""


@dataclass(frozen=True)
class InputRange:
    """The range of one input column, or the open question that explains why there is none."""

    column: str
    low: float | None
    high: float | None
    source: str
    open_question: str | None = None

    @property
    def is_open(self) -> bool:
        return self.low is None


def resolve_input_ranges(
    iso: str, audit: AuditConfig, geometry: CountryGeometry, columns: list[str]
) -> dict[str, InputRange]:
    """The range of every column F5 validates; a column with no declared range is an error, so the registry cannot drift from it.

    Implements: V-04.

    Args:
        iso: Country code.
        audit: The parsed `config/audit.yaml`.
        geometry: The country's elevation span and bounding box.
        columns: Resource-layer columns of the registry plus the distance columns.

    Raises:
        InputRangeError: a column is not a known resource layer, or its range is declared nowhere.
    """
    ranges: dict[str, InputRange] = {}
    for column in dict.fromkeys(columns):
        if column == _PVOUT_COLUMN:
            try:
                (low, high), source = pvout_range(audit, iso)
            except SanityError as exc:
                raise InputRangeError(str(exc)) from exc
            ranges[column] = InputRange(column, low, high, source)
            continue
        if column in DISTANCE_COLUMNS:
            kind, height = column, None
        else:
            match = _HEIGHT_COLUMN.match(column)
            if match is None:
                raise InputRangeError(
                    f"{column}: not a layer with a sanity range (V-04); declare it in audit.yaml"
                )
            kind, height = match.group(1), float(match.group(2))
        config = audit.derived_ranges.get(kind)
        if config is None:
            raise InputRangeError(f"audit.yaml derived_ranges has no entry for {kind!r} ({column})")
        if config.derivation is None:
            ranges[column] = InputRange(
                column, None, None, "no range declared", open_question=config.open_question
            )
            continue
        derived = derived_range(kind, geometry, height, config.tolerance_rel or 0.0)
        assert derived is not None  # a derivation is declared
        suffix = (
            f", widened by {config.tolerance_rel:.0%} on each side (quality-control tolerance)"
            if config.tolerance_rel
            else ""
        )
        ranges[column] = InputRange(
            column,
            float(derived[0]),
            float(derived[1]),
            f"audit.yaml derived_ranges.{kind} ({config.derivation}){suffix}",
        )
    return ranges


def warn_unranged(iso: str, technology: str, ranges: Mapping[str, InputRange]) -> None:
    """One warning per layer that has no range yet; its values are not checked."""
    for column, rng in ranges.items():
        if rng.is_open:
            logger.warning(
                "%s %s: %s has no sanity range (%s); its values are not range-checked",
                iso,
                technology,
                column,
                rng.open_question,
            )


def validate_candidates(
    iso: str,
    technology: str,
    scenario: str,
    frame: pd.DataFrame,
    ranges: Mapping[str, InputRange],
) -> None:
    """Raise `InputRangeError` listing every layer of the candidate table with a value outside its range or not finite.

    Implements: V-04.

    Args:
        iso: Country code.
        technology: Technology key.
        scenario: Land scenario of the table.
        frame: Candidate table (F3 output) with a `cell_id` column.
        ranges: Result of `resolve_input_ranges`.
    """
    problems: list[str] = []
    for column, rng in ranges.items():
        if rng.is_open:
            continue
        if column not in frame.columns:
            problems.append(f"{column}: column absent from the candidate table")
            continue
        values = frame[column].to_numpy(dtype="float64")
        slack = ROUNDING_SLACK_REL * max(abs(rng.low), abs(rng.high), 1.0)
        bad = ~np.isfinite(values) | (values < rng.low - slack) | (values > rng.high + slack)
        if not bad.any():
            continue
        finite = values[np.isfinite(values)]
        first = int(frame["cell_id"].to_numpy()[bad][0])
        extremes = (
            f"min {finite.min():.6g}, max {finite.max():.6g}" if finite.size else "no finite value"
        )
        problems.append(
            f"{column}: {int(bad.sum())} of {len(values)} candidate cells outside [{rng.low:.6g}, {rng.high:.6g}] "
            f"or not finite ({extremes}; first cell_id {first}); range from {rng.source}"
        )
    if problems:
        raise InputRangeError(
            f"{iso} {technology} [{scenario}]: input outside its sanity range (V-04); nothing was computed:\n  "
            + "\n  ".join(problems)
        )
