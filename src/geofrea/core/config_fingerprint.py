"""Configuration fingerprint of a phase (manifest 2.5, A-02).

A phase is resumed from the manifest only while the configuration it reads is the one it ran with. The fingerprint of a phase is the
SHA-256 of the parts of the config files that the phase reads (`PHASE_CONFIG_SCOPE`), parsed and serialised in a canonical form: a
comment, the order of keys or a change in a section the phase does not read leave it unchanged; a change of any value it reads, or
of a power-curve file, gives another one.

A scope names top-level sections (or dotted paths, `*` standing for every child of a mapping) of a file: a new key in a section a phase reads is read by
it. When a phase begins to read another section, the scope is edited here and `test_config_fingerprint.py` checks that every
registered phase has a scope and every section named exists in the file.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

import yaml

ABSENT = "<absent>"
WHOLE = "*"

# file key -> file name in config/ (the `paths` of `config_fingerprint` maps the same keys to the files actually read)
CONFIG_FILES = {
    "experiments": "experiments.yaml",
    "parameters": "parameters.json",
    "audit": "audit.yaml",
    "technologies": "technologies.yaml",
    "settings": "settings.yaml",
    "countries": "countries.yaml",
    "published_potential": "published_potential.yaml",
}
TURBINES = "turbines"  # directory of the reference power curves; every file in it is part of the fingerprint

_ISO = "{iso}"


def _scope(**files: list[str]) -> dict[str, list[str]]:
    return dict(files)


# phase -> {file key -> sections read}; `{iso}` is replaced by the country code, `*` is the whole file, `turbines` the curve directory.
PHASE_CONFIG_SCOPE: dict[str, dict[str, list[str]]] = {
    "data_acquisition": _scope(countries=[_ISO]),
    "data_quality_audit": _scope(
        audit=["layers", "resolution_tolerance", "country_overrides"],
        experiments=[
            "land_availability.technologies.*.slope_max_deg"
        ],  # the strictest slope limit of the range (M-F1b)
    ),
    "grid_alignment": _scope(settings=["geospatial"]),
    "external_inputs": _scope(experiments=["gcm_ensemble"]),
    "siting_layers": _scope(),
    "land_eligibility": _scope(experiments=["land_availability"]),
    "climate_forcing": _scope(experiments=["gcm_ensemble"]),
    "hazard_context": _scope(experiments=["gcm_ensemble", "hazard_indicators"]),
    "climate_maps": _scope(settings=["figures"]),
    "technical_potential": _scope(
        technologies=[WHOLE],
        parameters=[f"countries.{_ISO}"],
        experiments=["gcm_ensemble", "land_availability"],
        audit=["derived_ranges"],
        settings=["run.technologies"],
        turbines=[WHOLE],
    ),
    "lcoe_modeling": _scope(
        technologies=[WHOLE],
        parameters=[f"countries.{_ISO}"],
        experiments=["sampler", "uncertain_parameters", "land_availability", "windows"],
        settings=["run.technologies"],
    ),
    "sample_size_convergence": _scope(
        technologies=[WHOLE],
        parameters=[f"countries.{_ISO}"],
        experiments=["sampler", "uncertain_parameters", "thresholds", "windows"],
        settings=["run.technologies"],
    ),
    "robustness_analysis": _scope(
        technologies=[WHOLE],
        parameters=[f"countries.{_ISO}"],
        experiments=[
            "sampler",
            "uncertain_parameters",
            "land_availability",
            "windows",
            "thresholds",
            "hypothesis_rules",
            "national_targets",
            "hazard_thresholds",
            "prim",
        ],
        settings=["run.technologies"],
    ),
    "external_validation": _scope(
        technologies=[WHOLE],
        experiments=["external_validation", "land_availability"],
        published_potential=[WHOLE],
        settings=["run.technologies"],
    ),
    "lcoe_maps": _scope(
        experiments=["windows", "gcm_ensemble"],
        settings=["figures", "run.technologies"],
    ),
    "robustness_maps": _scope(experiments=["windows"], settings=["figures", "run.technologies"]),
    "potential_maps": _scope(settings=["figures", "run.technologies"]),
    "results_synthesis": _scope(
        technologies=[WHOLE],
        parameters=[WHOLE],
        experiments=[
            "hypothesis_rules",
            "land_availability",
            "sampler",
            "synthesis",
            "thesis_figures",
            "uncertain_parameters",
            "windows",
        ],
        settings=["run.technologies"],
    ),
    "overview": _scope(settings=["figures"]),
}


class ConfigSource(Protocol):
    """Where the config files are read from: the disk, or any other store (a git revision, for an audit)."""

    def text(self, key: str) -> str | None:
        """Text of the file `key` (a key of CONFIG_FILES), or None when it does not exist."""

    def turbine_files(self) -> dict[str, bytes]:
        """Name and bytes of every file of the power-curve directory."""


class DiskConfigSource:
    """The config files at the paths the pipeline reads (`paths` maps CONFIG_FILES keys to files)."""

    def __init__(self, paths: Mapping[str, Path], turbines_dir: Path | None = None) -> None:
        self._paths = {k: Path(v) for k, v in paths.items()}
        self._turbines = Path(turbines_dir) if turbines_dir is not None else None

    def text(self, key: str) -> str | None:
        path = self._paths.get(key)
        return path.read_text(encoding="utf-8") if path is not None and path.is_file() else None

    def turbine_files(self) -> dict[str, bytes]:
        if self._turbines is None or not self._turbines.is_dir():
            return {}
        return {p.name: p.read_bytes() for p in sorted(self._turbines.iterdir()) if p.is_file()}


def _parse(key: str, text: str | None) -> Any:
    if text is None:
        return None
    return json.loads(text) if CONFIG_FILES[key].endswith(".json") else yaml.safe_load(text)


def _select(doc: Any, path: str) -> Any:
    """The value at the dotted `path` of `doc`, or ABSENT when a step is missing; a step `*` takes every child of a mapping."""
    if path == WHOLE:
        return doc
    node = doc
    steps = path.split(".")
    for i, step in enumerate(steps):
        if not isinstance(node, Mapping):
            return ABSENT
        if step == WHOLE:
            rest = ".".join(steps[i + 1 :])
            return {key: _select(child, rest) if rest else child for key, child in node.items()}
        if step not in node:
            return ABSENT
        node = node[step]
    return node


def phase_config_payload(phase: str, country_code: str, source: ConfigSource) -> dict[str, Any]:
    """The values behind the fingerprint of `phase`: file key -> {selector: value}.

    Raises:
        KeyError: `phase` has no entry in PHASE_CONFIG_SCOPE (a registered phase must declare what it reads).
    """
    scope = PHASE_CONFIG_SCOPE[phase]
    payload: dict[str, Any] = {}
    for key, selectors in scope.items():
        if key == TURBINES:
            payload[key] = {
                name: hashlib.sha256(data).hexdigest()
                for name, data in sorted(source.turbine_files().items())
            }
            continue
        doc = _parse(key, source.text(key))
        payload[key] = {
            selector.replace(_ISO, country_code): _select(doc, selector.replace(_ISO, country_code))
            for selector in selectors
        }
    return payload


def config_fingerprint(phase: str, country_code: str, source: ConfigSource) -> str:
    """SHA-256 of the configuration `phase` reads for `country_code` (canonical JSON of `phase_config_payload`)."""
    blob = json.dumps(
        phase_config_payload(phase, country_code, source),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
