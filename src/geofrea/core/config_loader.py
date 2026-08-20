"""Loads and validates GeoFREA's configuration files.

Both parameters.json and settings.yaml are validated against the
schemas in schemas.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from geofrea.core.schemas import ParametersFile, SettingsFile


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
    return SettingsFile.model_validate(raw)
