"""Test that ISO3 country code literals do not appear in src/ outside comments.

METHODOLOGY A-05: All country-specific mappings live in config/countries.yaml.
A test fails if an ISO3 code literal appears in src/ outside comments and
docstrings.

This test scans src/ for 3-letter ISO3 codes that match the known countries
(BRA, PRT, IND) and other codes present in countries.yaml or parameters.json,
raising if any are found in regular code (not comments/docstrings).

Uses Python's tokenize module to reliably exclude string literals, comments,
and docstrings from the scan.
"""

from __future__ import annotations

import json
import re
import tokenize
from pathlib import Path


def _extract_iso3_codes() -> set[str]:
    """Extract all ISO3 codes from config files (countries.yaml, parameters.json)."""
    iso3_codes = set()

    # Read countries.yaml
    countries_yaml = Path(__file__).parent.parent.parent / "config" / "countries.yaml"
    if countries_yaml.exists():
        with open(countries_yaml) as f:
            for line in f:
                # Match lines like "BRA:", "PRT:", "IND:"
                if match := re.match(r"^(\w{3}):", line):
                    iso3_codes.add(match.group(1))

    # Read parameters.json
    params_file = Path(__file__).parent.parent.parent / "config" / "parameters.json"
    if params_file.exists():
        with open(params_file) as f:
            params = json.load(f)
            # Extract country codes from parameters.json
            for country_code in params.get("countries", {}):
                iso3_codes.add(country_code)

    return iso3_codes


def test_no_iso3_literals_in_src() -> None:
    """Scan src/ for ISO3 literals outside comments/docstrings.

    ISO3 codes must only appear in:
    - Comments (# lines)
    - Docstrings (triple-quoted strings)
    - NOT in regular code as NAME tokens (identifiers like BRA = ...)
    - NOT in regular code as STRING tokens inside dictionaries/assignments (like "BRA": ...)

    All country mappings must live in config/countries.yaml (A-05).
    """
    src_dir = Path(__file__).parent.parent.parent / "src"
    iso3_codes = _extract_iso3_codes()

    violations = []

    for py_file in src_dir.rglob("*.py"):
        with open(py_file, "rb") as f:
            try:
                tokens = list(tokenize.tokenize(f.readline))
            except tokenize.TokenError:
                # Skip files that can't be tokenized
                continue

        # Track whether we're inside a docstring by watching STRING tokens that appear early
        # (after only ENCODING, NEWLINE, NL, INDENT, or NAME tokens in a docstring context)
        in_docstring = False

        # We need to detect two violations:
        # 1. NAME tokens that match ISO3 codes (e.g., BRA as a variable name)
        # 2. STRING tokens that contain ISO3 codes (e.g., "BRA" as a dict key or string value)
        #    BUT NOT when the STRING token is a docstring
        for i, token in enumerate(tokens):
            token_type = tokenize.tok_name[token.type]

            # Detect docstrings: STRING tokens at the start of a function/class/module
            # A docstring typically appears right after a function/class definition or at module start
            if token_type == "STRING":
                # Check if this is likely a docstring:
                # - It's triple-quoted (starts with """ or ''')
                # - And it's early in the file, or right after a colon (function/class def)
                is_triple_quoted = token.string.startswith(('"""', "'''"))

                # Look back to see if this follows a function/class definition
                prev_tokens = tokens[max(0, i-5):i]
                follows_def = any(
                    t.string in ("def", "class")
                    for t in prev_tokens
                    if tokenize.tok_name[t.type] == "NAME"
                )

                # It's a docstring if it's triple-quoted and either follows a def/class or is early
                if is_triple_quoted and (follows_def or i < 10):
                    in_docstring = True
                else:
                    in_docstring = False

            # Skip COMMENT tokens entirely
            if token_type == "COMMENT":
                continue

            # Check NAME tokens (e.g., BRA = ... or BRA as a variable)
            if token_type == "NAME" and token.string in iso3_codes:
                violations.append(
                    f"{py_file.relative_to(src_dir)}:{token.start[0]}: "
                    f"ISO3 literal '{token.string}' found as NAME token (move to config/countries.yaml per A-05)\n"
                    f"  {token.line.rstrip()}"
                )

            # Check STRING tokens (but not docstrings)
            if token_type == "STRING" and not in_docstring:
                # Remove quotes to get the actual string value
                string_value = token.string
                if string_value.startswith(('"""', "'''")):
                    # This is triple-quoted, so it's a docstring — skip it
                    continue

                # Remove quotes (handle both single and double quotes, and raw/f-strings)
                if string_value.startswith(('r"', 'r\'', 'f"', 'f\'', 'rf"', 'rf\'')):
                    # Remove prefix like r, f, rf
                    string_value = string_value.lstrip('rfRF')
                if string_value.startswith(('"', '\'')):
                    string_value = string_value[1:-1]  # Remove surrounding quotes

                # Now check if any ISO3 code appears in this string value
                for code in iso3_codes:
                    if re.search(r'\b' + re.escape(code) + r'\b', string_value):
                        violations.append(
                            f"{py_file.relative_to(src_dir)}:{token.start[0]}: "
                            f"ISO3 literal '{code}' found in string (move to config/countries.yaml per A-05)\n"
                            f"  {token.line.rstrip()}"
                        )
                        break  # Only report once per string

    if violations:
        raise AssertionError(
            "ISO3 literals found in src/ outside comments and docstrings "
            "(violates METHODOLOGY A-05):\n" + "\n".join(violations)
        )
