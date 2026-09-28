"""JSON-backed registry for CMIP6 resource-channel acquisition (M-F1-04).

Fresh design (no CRAEI counterpart): CRAEI's Manifest (manifest.py) is
keyed by a single `country` axis alongside model/experiment/variable and
tracks only path/sha256/size/origin. This registry is global-first
(model, experiment, variable) with an optional per-country crop list
nested under each entry, and additionally records realization and native
grid (M-F1-04's own verification requirements, absent from ISIMIP3b/
CRAEI's problem — see docs/_audit F3-1 action 5/6) and distinguishes an
expected-but-unavailable combination ("missing", with a reason) from one
never attempted, per action 7's instruction that a missing combination is
recorded, never silently absent.

Registered separately from data_acquisition's per-country AcquiredLayer
registry (schemas.py): CMIP6 resource-channel entries are global objects
shared across countries (one file per model/experiment/variable, cropped
many times), not a single per-country path/paths pair, so they do not fit
AcquiredLayer's shape without distorting it. This is a deliberate
decision, recorded in docs/phases/F1_data_acquisition.md and
docs/phases/F4_climate_forcing.md, not an oversight.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from geofrea.data_acquisition.schemas import HASH_CHUNK_BYTES


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Cmip6NativeGrid(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat_resolution_deg: float
    lon_resolution_deg: float
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    n_lat: int
    n_lon: int


class Cmip6CountryCrop(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    path: str
    cells_before: int
    cells_after: int


class Cmip6RegistryEntry(BaseModel):
    """One (model, experiment, variable, frequency) combination.

    Args:
        status: "registered" (global file downloaded, validated,
            realization and native grid recorded) or "missing" (expected
            per the model/experiment/variable matrix but not obtained —
            always carries missing_reason, per action 7: never silently
            absent).
        missing_reason: Required when status="missing"; None otherwise.
        global_path: Path to the downloaded global monthly file.
        source_sha256: sha256 of the global file's bytes.
        temporal_coverage_start / _end: Years actually requested/covered.
        realization: The CMIP6 variant_label, verified identical across
            every variable/experiment of this model (M-F1-04).
        native_grid: This model's native lat/lon grid, read from the file.
        country_crops: Per-country polygon crops of this global file.
    """

    model_config = ConfigDict(extra="forbid")

    model: str
    experiment: str
    variable: str
    frequency: Literal["monthly"] = "monthly"
    status: Literal["registered", "missing"]
    missing_reason: str | None = None
    global_path: str | None = None
    source_sha256: str | None = None
    temporal_coverage_start: int | None = None
    temporal_coverage_end: int | None = None
    realization: str | None = None
    native_grid: Cmip6NativeGrid | None = None
    country_crops: list[Cmip6CountryCrop] = []

    @property
    def key(self) -> str:
        return f"cmip6/{self.model}/{self.experiment}/{self.variable}"

    @model_validator(mode="after")
    def _check_status_consistency(self) -> Cmip6RegistryEntry:
        if self.status == "missing":
            if self.missing_reason is None:
                raise ValueError(
                    f"Cmip6RegistryEntry({self.key}): status='missing' "
                    "requires missing_reason to be set."
                )
            if self.global_path is not None or self.source_sha256 is not None:
                raise ValueError(
                    f"Cmip6RegistryEntry({self.key}): status='missing' "
                    "must not carry global_path/source_sha256."
                )
        else:
            if self.missing_reason is not None:
                raise ValueError(
                    f"Cmip6RegistryEntry({self.key}): missing_reason must "
                    "be None unless status='missing'."
                )
            if self.global_path is None or self.source_sha256 is None or self.realization is None:
                raise ValueError(
                    f"Cmip6RegistryEntry({self.key}): status='registered' "
                    "requires global_path, source_sha256 and realization."
                )
        return self


class Cmip6Registry(BaseModel):
    """JSON-backed registry, keyed by `Cmip6RegistryEntry.key`."""

    model_config = ConfigDict(extra="forbid")

    entries: dict[str, Cmip6RegistryEntry] = {}

    @classmethod
    def load(cls, path: Path) -> Cmip6Registry:
        if path.exists():
            return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))
        return cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def is_complete(self, key: str) -> bool:
        """True if `key` is registered, its file exists, and its hash still matches.

        Resume logic (action 6): keyed at model/experiment/variable
        granularity, per F3-1's finding that this is new relative to
        GeoFREA's existing per-country layer registry.
        """
        entry = self.entries.get(key)
        if entry is None or entry.status != "registered":
            return False
        path = Path(entry.global_path)
        return path.exists() and sha256_file(path) == entry.source_sha256
