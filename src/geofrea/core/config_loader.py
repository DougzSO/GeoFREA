"""Loads and validates GeoFREA's configuration files.

parameters.json is validated against the schemas in schemas.py.
settings.yaml is parsed but not schema-validated yet: it currently has
no keys (see config/settings.yaml's header comment) — it holds only
operational/pipeline-control configuration, never scientific/technology
parameters, so a settings schema is deferred until it actually has
content to validate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from geofrea.core.schemas import ParametersFile


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


def load_settings(path: Path) -> dict[str, Any]:
    """Load settings.yaml.

    Args:
        path: Path to a settings.yaml file.

    Returns:
        Parsed YAML content as a dict. Empty dict if the file has no
        keys (only comments), which is the current state of
        config/settings.yaml.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw or {}
