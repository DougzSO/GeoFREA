"""JSON-backed registry for the ISIMIP3b hazard-channel data (M-F4-05, D-F4-001).

OQ-036 (resolved 2026-10-05, route b): the hazard channel's per-country
ISIMIP3b crops are reused from CRAEI (A-11, code-and-data copy of the
projection channel only -- the W5E5 reference channel has no mapped
consumer in any M-F4-0x and was not copied) rather than read in place from
CRAEI_BASELINE_DIR. This registry records the one-time copy so a later run
can verify it is still intact without re-hashing 180 files, and so
`members.yaml` (M-F4-01, task J-1) has a single place to look up which
(gcm, scenario, variable, country) combinations actually exist on disk.

Keyed like `cmip6_registry.py` (model/experiment/variable), but each entry
is already per-country, because CRAEI pre-crops ISIMIP3b to BRA/IND/PRT
before GeoFREA ever sees it -- there is no global file to crop here, unlike
CMIP6's resource channel.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class Isimip3bRegistryEntry(BaseModel):
    """One (gcm, scenario, variable, country) ISIMIP3b projection file, copied from CRAEI.

    Args:
        gcm: Lowercase, hyphenated model name as CRAEI names it (e.g. "gfdl-esm4").
            Note (D-F4-004/members.yaml): GFDL-ESM4 also exists in the C1
            resource channel as a raw CMIP6 file -- the two are distinct
            source files for the same `gcm` label, one per channel.
        scenario: "historical", "ssp126", "ssp370", or "ssp585".
        variable: "pr", "tasmax", or "tasmin".
        country_code: ISO3 (BRA, IND, PRT).
        path: Absolute path under GEOFREA_DATA_DIR/raw/isimip3b/<ISO3>/.
        source_sha256: sha256 of the file's bytes, reused from the copy
            verification (oq036_isimip3b_copy_log.csv), not recomputed.
        size_bytes: File size, from the same copy log.
        bias_adjustment: Fixed provenance string for every entry -- CRAEI
            bias-adjusts the whole ISIMIP3b archive uniformly against
            W5E5 v2.0 via ISIMIP3BASD v2.5.0.
        copied_from: The CRAEI source path this entry was copied from, for
            provenance (A-11 permits copying data for this specific
            reuse per OQ-036's resolution; code is adapted separately).
    """

    model_config = ConfigDict(extra="forbid")

    gcm: str
    scenario: str
    variable: str
    country_code: str
    path: str
    source_sha256: str
    size_bytes: int
    bias_adjustment: str = "ISIMIP3BASD v2.5.0 against W5E5 v2.0 (Lange 2019; Frieler et al. 2021)"
    copied_from: str

    @property
    def key(self) -> str:
        return f"isimip3b/{self.gcm}/{self.scenario}/{self.variable}/{self.country_code}"


class Isimip3bRegistry(BaseModel):
    """JSON-backed registry, keyed by `Isimip3bRegistryEntry.key`."""

    model_config = ConfigDict(extra="forbid")

    entries: dict[str, Isimip3bRegistryEntry] = {}

    @classmethod
    def load(cls, path: Path) -> Isimip3bRegistry:
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
        """True if `key` is registered and its file still exists with the recorded size.

        Size-only check (not a re-hash) deliberately: this registry exists
        so a consumer does not have to re-hash 180 files on every read;
        `verify_registry_against_disk()` below is the full sha256 check,
        meant to run occasionally, not on every access.
        """
        entry = self.entries.get(key)
        if entry is None:
            return False
        path = Path(entry.path)
        return path.exists() and path.stat().st_size == entry.size_bytes
