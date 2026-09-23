"""Loads and validates GeoFREA's configuration files.

Both parameters.json and settings.yaml are validated against the
schemas in schemas.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from geofrea.core.schemas import ParametersFile, SettingsFile
from geofrea.data_quality_audit.schemas import AuditConfig


class CountryMappingError(KeyError):
    """Raised when a requested country has no mapping in config/countries.yaml.

    Per METHODOLOGY A-05: a null mapping for a requested country must raise
    a named error (not silently proceed). This exception extends KeyError so
    it still behaves like the key was not found, but with better semantics
    for country configuration gaps.
    """



def load_parameters(path: Path) -> ParametersFile:
    """Load and validate parameters.json.

    Args:
        path: Path to a parameters.json file.

    Returns:
        A validated ParametersFile model instance.

    Raises:
        pydantic.ValidationError: If the file's content doesn't match
            the schema (e.g. a required field is missing).
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ParametersFile.model_validate(raw)


def load_settings(path: Path) -> SettingsFile:
    """Load and validate settings.yaml.

    Args:
        path: Path to a settings.yaml file.

    Returns:
        A validated SettingsFile model instance.

    Raises:
        pydantic.ValidationError: If the file's content doesn't match
            the schema (e.g. a required field is missing).

    Note:
        When SettingsFile.run.countries is empty, a future phase runner
        resolves the actual country list dynamically from
        load_parameters(...).countries.keys() — not from settings.yaml.
        No such runner exists yet, so this resolution is not
        implemented here; this note documents the intended contract for
        when it is.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    run_raw = raw.get("run") if isinstance(raw, dict) else None
    if isinstance(run_raw, dict) and "force_rerun" in run_raw:
        raise ValueError(
            f"{path} sets run.force_rerun, which no longer exists (R-1). Replace it "
            "with run.rerun_phases: a list of phase names to re-execute exactly "
            "(never their dependents); an empty list means normal resume behavior."
        )
    return SettingsFile.model_validate(raw)


def load_audit_config(path: Path) -> AuditConfig:
    """Load and validate config/audit.yaml.

    Args:
        path: Path to an audit.yaml file.

    Returns:
        A validated AuditConfig model instance.

    Raises:
        pydantic.ValidationError: If the file's content doesn't match
            the schema.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return AuditConfig.model_validate(raw)


def load_countries(path: Path) -> dict[str, dict[str, str | None]]:
    """Load countries.yaml and return the country mappings.

    Args:
        path: Path to a countries.yaml file.

    Returns:
        A dictionary mapping ISO-3 country codes to sub-dictionaries
        containing mappings like hydrosheds_region, elevation_dir, etc.
        Values may be None if a mapping is not yet determined.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw if raw else {}
