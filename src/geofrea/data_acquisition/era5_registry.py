"""JSON-backed registry for ERA5 gust acquisition (M-F1-05).

COMMAND F4-2 action 2 asked whether `cmip6_registry.py`'s shape fits
ERA5 before writing a third provenance store. It does not:
`Cmip6RegistryEntry.model`/`.experiment` are required fields with no
default, because every CMIP6 entry is keyed by (model, experiment,
variable) — ERA5 has neither axis, it is one reanalysis product with a
per-country bbox download and a per-country polygon crop, nothing to
enumerate across. Forcing ERA5 into that shape would mean two
permanently-empty required fields on every entry, so a separate,
smaller registry is built instead: one entry per country (not per
model/experiment/variable), and country_crops is a flat pair of
paths (source + reduced) rather than a list, since there is exactly
one country per entry already.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from geofrea.data_acquisition.cmip6_registry import Cmip6NativeGrid, sha256_file

__all__ = ["Era5NativeGrid", "Era5Registry", "Era5RegistryEntry", "sha256_file"]

# Reused directly (not redefined): a native-grid descriptor is generic
# (resolution/extent/cell count), nothing CMIP6-specific in its shape.
Era5NativeGrid = Cmip6NativeGrid


class Era5RegistryEntry(BaseModel):
    """One country's ERA5 gust acquisition.

    Args:
        status: "registered" (source and reduced product both on disk,
            validated, hashed) or "missing" (expected but not obtained
            — always carries missing_reason, same convention as
            Cmip6RegistryEntry).
        bbox_path: The CDS-side bbox download (raw/era5/_global/),
            kept for provenance but not itself registered with a hash
            — it is superseded by source_path, the polygon-cropped
            refinement of the same data (action 4).
        source_path: The polygon-cropped raw hourly field
            (raw/era5/<ISO3>/) — the expensive-to-re-acquire artifact,
            registered with its own hash (action 5: "keep both the
            source and the reduced product registered").
        reduced_path: The daily-then-annual-maxima reduction of
            source_path — a pure function of it, cheap to recompute,
            but registered anyway so a consumer never has to guess
            whether it is current against source_path (checked via
            source_sha256).
        reference_period_start / _end: 1995 / 2014 (D-F4-008).
        native_grid: Read from source_path (post-crop), not bbox_path.
        year_sha256: Per-year raw-hourly-download sha256, keyed by
            year as a string (JSON object keys). Populated
            progressively, one entry per year, as each year's request
            completes — the idempotency mechanism task F4-2's dataset
            switch asked for: a resumed run checks a year's file
            against this hash before re-downloading it, so a crash or
            stall partway through the 20-year sequence never re-does
            years that already landed.
        permanently_failed_years: Per-year failure reason, keyed by
            year as a string, for a year that exhausted
            `MAX_ATTEMPTS_PER_YEAR` retries (COMMAND F4-6, OQ-038
            follow-up). Distinct from a year present in neither this
            dict nor `year_sha256` (not yet attempted this run, or
            transiently unresolved and eligible for a future resume)
            and from a year in `year_sha256` (succeeded). A year here
            is not retried automatically by a later resume — it is a
            terminal state for that (country, year) pending manual
            attention, not a transient one.
    """

    model_config = ConfigDict(extra="forbid")

    country_code: str
    variable: str = "fg10"
    status: Literal["registered", "missing"]
    missing_reason: str | None = None
    bbox_path: str | None = None
    source_path: str | None = None
    source_sha256: str | None = None
    reduced_path: str | None = None
    reduced_sha256: str | None = None
    reference_period_start: int | None = None
    reference_period_end: int | None = None
    native_grid: Era5NativeGrid | None = None
    cells_before: int | None = None
    cells_after: int | None = None
    year_sha256: dict[str, str] = {}
    permanently_failed_years: dict[str, str] = {}

    @property
    def key(self) -> str:
        return f"era5/{self.country_code}/{self.variable}"

    @model_validator(mode="after")
    def _check_status_consistency(self) -> Era5RegistryEntry:
        if self.status == "missing":
            if self.missing_reason is None:
                raise ValueError(
                    f"Era5RegistryEntry({self.key}): status='missing' "
                    "requires missing_reason to be set."
                )
            if self.source_path is not None or self.reduced_path is not None:
                raise ValueError(
                    f"Era5RegistryEntry({self.key}): status='missing' "
                    "must not carry source_path/reduced_path."
                )
        else:
            if self.missing_reason is not None:
                raise ValueError(
                    f"Era5RegistryEntry({self.key}): missing_reason must "
                    "be None unless status='missing'."
                )
            if (
                self.source_path is None
                or self.source_sha256 is None
                or self.reduced_path is None
                or self.reduced_sha256 is None
            ):
                raise ValueError(
                    f"Era5RegistryEntry({self.key}): status='registered' "
                    "requires source_path, source_sha256, reduced_path and "
                    "reduced_sha256."
                )
        return self


class Era5Registry(BaseModel):
    """JSON-backed registry, keyed by `Era5RegistryEntry.key`."""

    model_config = ConfigDict(extra="forbid")

    entries: dict[str, Era5RegistryEntry] = {}

    @classmethod
    def load(cls, path: Path) -> Era5Registry:
        import json

        if path.exists():
            return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))
        return cls()

    def save(self, path: Path) -> None:
        import json

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def is_complete(self, key: str) -> bool:
        """True if `key` is registered, its source file exists, and its hash still matches."""
        entry = self.entries.get(key)
        if entry is None or entry.status != "registered":
            return False
        path = Path(entry.source_path)
        return path.exists() and sha256_file(path) == entry.source_sha256
