"""The support phase `cross_country_h4`: the verdict of H4 per technology from the profiles of all the countries (M-F7-07; D-F7-049).

The verdict of H4 compares countries, so it cannot be an artifact of one country: the manifest of a country holds only what that country's
phases produced. The phase takes the list of countries as its input, reads the `h4_country` table that F7 registered in each country's manifest
(through `ArtifactReader`, which checks the registered hash), applies the strict rule of `h4_axis_dominance.technology_verdict` and writes one
`h4_verdict_<tech>__<window role>` table per technology and window, with a manifest of its own beside them
(`outputs/cross_country/manifest.json`, `manifest__<scale id>.json` at another scale). A country that has no manifest, no table or an empty
table (a null decision parameter) is `unavailable` with the reason; it has no profile and is not counted as a country with one.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict

from geofrea.core import paths as core_paths
from geofrea.core.artifact_reader import ArtifactReader, ThesisInputError
from geofrea.core.scale import active_scale
from geofrea.core.tables import write_table
from geofrea.robustness_analysis.h4_axis_dominance import (
    PROFILES,
    CountryProfile,
    technology_verdict,
)
from geofrea.robustness_analysis.table_schemas import (
    ROBUSTNESS_TABLE_SCHEMA_VERSION,
    H4VerdictRow,
)

logger = logging.getLogger("geofrea.robustness_analysis.cross_country")

ROLES = ("core", "sensitivity")
PHASE_NAME = "cross_country_h4"
_MANIFEST_SCHEMA_VERSION = "1.0"


class VerdictEntry(BaseModel):
    """The H4 verdict of one technology and window role."""

    model_config = ConfigDict(extra="forbid")

    technology: str
    role: str
    verdict: str
    reason: str | None
    n_countries: int
    n_available: int
    counts: dict[str, int]


class CrossCountrySummary(BaseModel):
    """What one run of `cross_country_h4` wrote: the countries it read, the tables and the verdicts."""

    model_config = ConfigDict(extra="forbid")

    countries: list[str]
    scale: str
    manifest: str
    tables: dict[str, str]
    verdicts: list[VerdictEntry]


def output_dir() -> Path:
    """`outputs/cross_country/artifacts` (`artifacts__<scale id>` at another scale, A-08)."""
    scale = active_scale()
    name = "artifacts" if scale.is_default else f"artifacts__{scale.scale_id}"
    return core_paths.cross_country_dir() / name


def manifest_file() -> Path:
    return core_paths.cross_country_manifest_path()


def country_profile(
    country: str, technology: str, role: str, reader: ArtifactReader
) -> tuple[CountryProfile, str | None]:
    """The profile of one country and technology from the primary row of its `h4_country` table, and the hash of the table it read.

    A country that has no manifest, no table or an empty table is `unavailable` with the reason (the question that blocks the table when F7
    wrote it empty).
    """
    key = f"h4_country_{technology}__{role}"
    if not reader.available:
        return CountryProfile(country, False, reason="the country has no manifest"), None
    if not reader.has(key):
        return CountryProfile(country, False, reason=f"the manifest registers no {key}"), None
    table = reader.table(key, {ROBUSTNESS_TABLE_SCHEMA_VERSION})
    digest = reader.used[key]
    if table.empty:
        note = reader.skip_note(key) or {}
        why = f"{note.get('reason', 'the table has no row')} ({note.get('open_question', 'no open question named')})"
        return CountryProfile(country, False, reason=why), digest
    primary = table[table["primary"]]
    if len(primary) != 1:
        raise ThesisInputError(f"{country}: {key} has {len(primary)} primary rows, one is needed")
    row = primary.iloc[0]
    rho = None if pd.isna(row["rho"]) else float(row["rho"])
    return (
        CountryProfile(
            country,
            True,
            profile=str(row["profile"]),
            d_clim=float(row["d_clim"]),
            d_tec=float(row["d_tec"]),
            d_sum=float(row["d_sum"]),
            rho=rho,
        ),
        digest,
    )


def verdict_frame(
    profiles: Sequence[CountryProfile], window: str
) -> tuple[pd.DataFrame, str, str | None, dict]:
    """The rows of the `h4_verdict` table of one technology and window, and the verdict, its reason and the counts."""
    result = technology_verdict(profiles)
    rows = [
        {
            "kind": "country",
            "country": p.country,
            "window": window,
            "available": p.available,
            "profile": p.profile,
            "d_clim": p.d_clim,
            "d_tec": p.d_tec,
            "d_sum": p.d_sum,
            "rho": p.rho,
            "n_countries": None,
            "n_available": None,
            "n_climate_dominated": None,
            "n_techno_economic_dominated": None,
            "n_mixed": None,
            "n_no_displacement": None,
            "verdict": None,
            "reason": p.reason,
        }
        for p in profiles
    ]
    counts = result.counts
    rows.append(
        {
            "kind": "technology",
            "country": "ALL",
            "window": window,
            "available": result.n_available > 0,
            "profile": None,
            "d_clim": None,
            "d_tec": None,
            "d_sum": None,
            "rho": None,
            "n_countries": result.n_countries,
            "n_available": result.n_available,
            "n_climate_dominated": counts[PROFILES[0]],
            "n_techno_economic_dominated": counts[PROFILES[1]],
            "n_mixed": counts[PROFILES[2]],
            "n_no_displacement": counts[PROFILES[3]],
            "verdict": result.verdict,
            "reason": result.reason,
        }
    )
    frame = pd.DataFrame(rows).astype(
        {
            "d_clim": "float64",
            "d_tec": "float64",
            "d_sum": "float64",
            "rho": "float64",
            "n_countries": "Int64",
            "n_available": "Int64",
            "n_climate_dominated": "Int64",
            "n_techno_economic_dominated": "Int64",
            "n_mixed": "Int64",
            "n_no_displacement": "Int64",
            "profile": "object",
            "verdict": "object",
            "reason": "object",
        }
    )
    return frame, result.verdict, result.reason, dict(counts)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def build_h4_verdict(
    countries: Sequence[str], technologies: Sequence[str], *, run_id: str = "cross-country"
) -> CrossCountrySummary:
    """Write the `h4_verdict` tables of every technology and window role from the `h4_country` tables of `countries`.

    Implements: M-F7-07 (H4), D-F7-049.

    Raises:
        ThesisInputError: a registered `h4_country` table changed since it was registered, has an unknown schema version or no single
            primary row.
    """
    countries = [c.upper() for c in countries]
    out = output_dir()
    artifacts: dict[str, dict] = {}
    tables: dict[str, str] = {}
    verdicts: list[VerdictEntry] = []
    readers = {c: ArtifactReader(c) for c in countries}
    for technology in technologies:
        for role in ROLES:
            profiles: list[CountryProfile] = []
            read: dict[str, str] = {}
            window = role
            for country in countries:
                profile, digest = country_profile(country, technology, role, readers[country])
                profiles.append(profile)
                if digest:
                    read[f"{country}:h4_country_{technology}__{role}"] = digest
            frame, verdict, reason, counts = verdict_frame(profiles, window)
            key = f"h4_verdict_{technology}__{role}"
            path = write_table(
                frame,
                out / f"{key}.parquet",
                schema_version=ROBUSTNESS_TABLE_SCHEMA_VERSION,
                row_model=H4VerdictRow,
                compression="zstd",
                extra_metadata={
                    "countries": ",".join(countries),
                    "scale": active_scale().scale_id,
                    "artifacts_read": json.dumps(read, sort_keys=True),
                },
            )
            stored = core_paths.to_stored_path(path)
            artifacts[key] = {
                "key": key,
                "path": stored.model_dump(mode="json"),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
                "mtime_ns": path.stat().st_mtime_ns,
                "schema_version": ROBUSTNESS_TABLE_SCHEMA_VERSION,
                "phase": PHASE_NAME,
                "run_id": run_id,
            }
            tables[key] = str(path)
            verdicts.append(
                VerdictEntry(
                    technology=technology,
                    role=role,
                    verdict=verdict,
                    reason=reason,
                    n_countries=len(profiles),
                    n_available=sum(p.available for p in profiles),
                    counts=counts,
                )
            )
            logger.info(
                "H4 %s [%s]: %s across %s (%d of %d countries have a profile)",
                technology,
                role,
                verdict,
                ",".join(countries),
                sum(p.available for p in profiles),
                len(profiles),
            )
    manifest = manifest_file()
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "schema_version": _MANIFEST_SCHEMA_VERSION,
                "phase": PHASE_NAME,
                "countries": countries,
                "scale": active_scale().scale_id,
                "artifacts": artifacts,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return CrossCountrySummary(
        countries=countries,
        scale=active_scale().scale_id,
        manifest=str(manifest),
        tables=tables,
        verdicts=verdicts,
    )
