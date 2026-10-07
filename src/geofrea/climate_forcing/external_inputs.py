"""Check that the inputs acquired outside the phase graph are on disk and intact, before F4 uses them (A-09).

CMIP6 (monthly rsds, tas, sfcWind), ISIMIP3b (daily tasmax, pr crops) and the ERA5 gust annual maxima are fetched by
scripts (`scripts/acquire_*.py`, the OQ-036 copy) because they are large or queue for hours. Each has a registry with
a sha256. This check runs as the `external_inputs` phase, so a missing or altered file stops `climate_forcing` and
`hazard_context` with one message that names every problem, instead of a failure halfway through a phase.

Cost: existence and registry status for every file the ensemble needs; sha256 only for the small ERA5 product (a few
MB) and, with `full_hash=True`, for the large CMIP6 and ISIMIP3b files (about 29 GB, minutes). ISIMIP3b is checked by
size, as `Isimip3bRegistry.is_complete` does.

The existing-plant trackers are not checked here: no phase reads them before F7b, and V-06 keeps the plant data out
of the pipeline (their own acquisition script pins them and records their sha256).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from geofrea.climate_forcing.members import (
    VARIABLES,
    has_hazard_channel,
    load_ensemble,
    resolve_members,
)
from geofrea.core import paths as core_paths
from geofrea.data_acquisition.cmip6_registry import Cmip6Registry, sha256_file
from geofrea.data_acquisition.era5_registry import Era5Registry
from geofrea.data_acquisition.isimip3b_registry import Isimip3bRegistry

HAZARD_VARIABLES = ("tasmax", "pr")


class ExternalInputError(RuntimeError):
    """One or more external inputs are missing, unregistered or altered; the message lists all of them."""


class ExternalInputsReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    cmip6_files: int
    isimip3b_files: int
    era5_files: int
    full_hash: bool


def _cmip6_problems(
    registry: Cmip6Registry, gcm_names: list[str], experiments: list[str], full_hash: bool
) -> tuple[list[str], int]:
    problems: list[str] = []
    n = 0
    for gcm in gcm_names:
        for experiment in ("historical", *experiments):
            for variable in VARIABLES:
                key = f"cmip6/{gcm}/{experiment}/{variable}"
                entry = registry.entries.get(key)
                if entry is None or entry.status != "registered":
                    problems.append(f"CMIP6 {key}: not registered")
                    continue
                path = Path(entry.global_path)
                if not path.exists():
                    problems.append(f"CMIP6 {key}: file missing ({path})")
                    continue
                n += 1
                if full_hash and sha256_file(path) != entry.source_sha256:
                    problems.append(f"CMIP6 {key}: sha256 differs from the registry ({path})")
    return problems, n


def _isimip_problems(registry: Isimip3bRegistry, iso: str, members) -> tuple[list[str], int]:
    problems: list[str] = []
    needed = {(m.gcm.cds_name.replace("_", "-"), scenario) for m in members for scenario in ("historical", m.experiment)}
    n = 0
    for gcm, scenario in sorted(needed):
        for variable in HAZARD_VARIABLES:
            key = f"isimip3b/{gcm}/{scenario}/{variable}/{iso}"
            if not registry.is_complete(key):
                problems.append(f"ISIMIP3b {key}: not registered, missing or its size differs from the registry")
            else:
                n += 1
    return problems, n


def _era5_problems(registry: Era5Registry, iso: str) -> tuple[list[str], int]:
    entry = registry.entries.get(f"era5/{iso}/fg10")
    if entry is None or entry.status != "registered":
        return [f"ERA5 era5/{iso}/fg10: not registered"], 0
    path = Path(entry.reduced_path)
    if not path.exists():
        return [f"ERA5 era5/{iso}/fg10: annual-maximum file missing ({path})"], 0
    if sha256_file(path) != entry.reduced_sha256:
        return [f"ERA5 era5/{iso}/fg10: sha256 of {path} differs from the registry"], 0
    return [], 1


def check_external_inputs(iso: str, experiments_yaml: Path, full_hash: bool = False) -> ExternalInputsReport:
    """Raise `ExternalInputError` listing every problem; return the counts checked when there is none."""
    ensemble = load_ensemble(experiments_yaml)
    members = [m for m in resolve_members(ensemble) if m.gcm is not None]
    hazard_members = [m for m in members if has_hazard_channel(m, ensemble.hazard_windows_available)]
    raw = core_paths.fetched_raw

    problems: list[str] = []
    registries = {
        "CMIP6": raw("cmip6", "_global") / "cmip6_registry.json",
        "ISIMIP3b": raw("isimip3b", "") / "isimip3b_registry.json",
        "ERA5": raw("era5", "_global") / "era5_registry.json",
    }
    for name, path in registries.items():
        if not path.exists():
            problems.append(f"{name} registry missing: {path}")
    if problems:
        raise ExternalInputError("\n".join(problems))

    cmip6, n_cmip6 = _cmip6_problems(
        Cmip6Registry.load(registries["CMIP6"]),
        sorted({m.gcm.cds_name for m in members}),
        sorted({m.experiment for m in members}),
        full_hash,
    )
    isimip, n_isimip = _isimip_problems(Isimip3bRegistry.load(registries["ISIMIP3b"]), iso, hazard_members)
    era5, n_era5 = _era5_problems(Era5Registry.load(registries["ERA5"]), iso)
    problems = cmip6 + isimip + era5
    if problems:
        raise ExternalInputError(
            f"{len(problems)} external input problem(s) for {iso} (acquire them with the scripts in scripts/):\n"
            + "\n".join(problems)
        )
    return ExternalInputsReport(
        country_code=iso, cmip6_files=n_cmip6, isimip3b_files=n_isimip, era5_files=n_era5, full_hash=full_hash
    )
