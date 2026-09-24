"""Enforce the test-value/sourced-value separation OQ-032's verdict requires.

docs/phases/core.md D-core-018 (closing OQ-032, playbook COMMAND ADJ-3):
a synthetic country (ZZZ, A-06/V-08) carries test values, chosen for what
they exercise, never sourced values — METHODOLOGY U-07's sourcing rule
governs values that enter a result, not a fixture, but the two must never
mix. This module is the enforcement-by-test the verdict calls for,
independent of docs/phases/core.md's prose or any reviewer remembering to
check it by hand.

Four checks, each named after the playbook's own wording:
  1. No country marked synthetic (`countries.yaml`'s
     `synthetic_fixture_root`) may enter the default thesis-scope country
     expansion (`main.py::main()`).
  2. No `VerifiedValue` under a REAL country in `config/parameters.json`
     may set `synthetic=True`.
  3. No REAL country's `config/countries.yaml` mapping may carry
     `synthetic_fixture_root`.
  4. Every `VerifiedValue` under a country whose `countries.yaml` mapping
     DOES carry `synthetic_fixture_root` must set `synthetic=True` — a
     synthetic country's values are never silently read as sourced
     either.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COUNTRIES_YAML = _REPO_ROOT / "config" / "countries.yaml"
_PARAMETERS_JSON = _REPO_ROOT / "config" / "parameters.json"


def _load_countries_config() -> dict[str, dict[str, Any]]:
    return yaml.safe_load(_COUNTRIES_YAML.read_text(encoding="utf-8")) or {}


def _load_parameters() -> dict[str, Any]:
    return json.loads(_PARAMETERS_JSON.read_text(encoding="utf-8"))


def _synthetic_country_codes(countries_config: dict[str, dict[str, Any]]) -> set[str]:
    return {code for code, mapping in countries_config.items() if mapping.get("synthetic_fixture_root")}


def _iter_verified_values(node: Any, path: str = ""):
    """Yield (path, dict) for every VerifiedValue-shaped dict under `node`.

    A VerifiedValue always has these four keys together (see
    core/schemas.py) — a plain nested dict (e.g. yield_by_land_cover's
    `value` payload, itself {class_code: float}) never has all four, so
    this cannot mistake ordinary data for a VerifiedValue block.
    """
    if isinstance(node, dict):
        if {"unit", "verified", "verification_method", "synthetic"} <= node.keys():
            yield path, node
            return  # a VerifiedValue's own sub-fields (range, etc.) are not separately walked
        for key, value in node.items():
            yield from _iter_verified_values(value, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from _iter_verified_values(item, f"{path}[{i}]")


@pytest.mark.unit
def test_default_country_expansion_excludes_synthetic_countries():
    """Check 1: main()'s "empty run.countries = every country" default never includes a synthetic one."""
    from geofrea.core.config_loader import load_parameters

    countries_config = _load_countries_config()
    synthetic = _synthetic_country_codes(countries_config)
    assert synthetic, "expected at least ZZZ to be marked synthetic — fixture removed?"

    parameters = load_parameters(_PARAMETERS_JSON)
    default_countries = [
        c for c in parameters.countries if not countries_config.get(c, {}).get("synthetic_fixture_root")
    ]
    assert synthetic.isdisjoint(default_countries), (
        f"synthetic countries {synthetic & set(default_countries)} would run in main()'s "
        "default (empty settings.run.countries) expansion — a thesis run must never "
        "include a test fixture."
    )


@pytest.mark.unit
def test_no_real_country_value_is_marked_synthetic():
    """Check 2: a real country's parameters.json entry never sets VerifiedValue.synthetic=True."""
    countries_config = _load_countries_config()
    synthetic_codes = _synthetic_country_codes(countries_config)
    parameters = _load_parameters()

    offending: list[str] = []
    for country_code, country_block in parameters.get("countries", {}).items():
        if country_code in synthetic_codes:
            continue
        for path, vv in _iter_verified_values(country_block, country_code):
            if vv.get("synthetic") is True:
                offending.append(path)

    assert not offending, f"real country value(s) marked synthetic=True: {offending}"


@pytest.mark.unit
def test_no_real_country_carries_the_synthetic_fixture_marker():
    """Check 3: only a country explicitly meant as a fixture may set synthetic_fixture_root."""
    countries_config = _load_countries_config()
    real_countries = {"BRA", "PRT", "IND"}  # CLAUDE.md "Scope reminders" — the only real countries in scope

    offending = [
        code
        for code in real_countries
        if countries_config.get(code, {}).get("synthetic_fixture_root")
    ]
    assert not offending, f"real country/countries carry synthetic_fixture_root: {offending}"


@pytest.mark.unit
def test_every_synthetic_country_value_is_marked_synthetic():
    """Check 4: every VerifiedValue under a synthetic country's parameters.json entry sets synthetic=True."""
    countries_config = _load_countries_config()
    synthetic_codes = _synthetic_country_codes(countries_config)
    parameters = _load_parameters()

    missing: list[str] = []
    for country_code in synthetic_codes:
        country_block = parameters.get("countries", {}).get(country_code)
        if country_block is None:
            continue  # no parameters.json entry at all -- nothing to mis-mark
        for path, vv in _iter_verified_values(country_block, country_code):
            if vv.get("synthetic") is not True:
                missing.append(path)

    assert not missing, f"synthetic country value(s) NOT marked synthetic=True: {missing}"
