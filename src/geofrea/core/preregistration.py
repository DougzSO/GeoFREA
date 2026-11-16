"""The pre-registered subset of the configuration and its digest (DEC-081, COMMAND 155B).

The decision parameters of group 4 are registered before the first production run of F6: from then on the subset of the configuration listed below
must not change in silence. The registration is an annotated git tag, `prereg-v1`, created once (COMMAND 162T) on the commit that fills the subset;
its message carries the digest of the subset. F6 and F7 on real data read the tag with the local `git` and refuse to run when the tag is absent or when
the digest of the live configuration differs from the one in the message; the message names the keys that changed. A country whose values are
`synthetic: true` is ignored. `scripts/preregistration_digest.py` prints the digests and the text of the message and creates nothing.

The subset (selectors of `PARAMETER_SELECTORS` and `EXPERIMENT_SELECTORS`; `{iso}` is the country, `*` every child of a mapping):

- per country and technology, in `parameters.json`: `tau_lcoe_usd_per_mwh`, `cf_min`, `top_k_percent`, the `range` of `discount_rate`, and the sensitivities that
  lcoe_modeling or a later phase reads: `hot_zone_sensitivity`, `transmission_loss_per_km_sensitivity`, `poi_sensitivity_threshold_kv`;
- in `experiments.yaml`: `thresholds.regret_quantile`, `prim.outcome_threshold`, `prim.sensitivity`, `hypothesis_rules.H5.sensitivity_lambda`,
  `windows.sensitivity` and `national_targets.{iso}` (with its `alternatives`).

Not in the subset: `land_availability.sensitivities.population_density_200` (`run: false`), the filters of `external_validation`, and the sensitivities that exist
only as constants of `core/constants.py` (p_k in {5, 10, 20}, `GAMMA_PROFILE`, `H4_SENSITIVITY_BOUNDARIES`): the registration commit pins those.

The subset digest moves no phase fingerprint: this module is read by `main.py` and the orchestrator hook, not by a phase.

The digest of a country is the SHA-256 of the canonical JSON (`sort_keys`, separators `(",", ":")`, `default=str`) of `{"subset_version", "keys"}`, where `keys` maps
each key of the subset, as `<file>:<selector with the country>`, to its validated value (the values the phases receive, `config_fingerprint._validated`). The
digest of one key is the SHA-256 of the canonical JSON of its value. The aggregate digest is that of `{iso: country digest}`.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from geofrea.core.config_fingerprint import ABSENT, ConfigSource, _parse, _select
from geofrea.core.orchestrator import Preregistration

TAG_NAME = "prereg-v1"
SUBSET_VERSION = 1

_ISO = "{iso}"

# file key of `config_fingerprint.CONFIG_FILES` -> selectors of the subset
PARAMETER_SELECTORS: tuple[str, ...] = (
    "countries.{iso}.technologies.*.tau_lcoe_usd_per_mwh",
    "countries.{iso}.technologies.*.cf_min",
    "countries.{iso}.technologies.*.top_k_percent",
    "countries.{iso}.technologies.*.discount_rate.range",
    "countries.{iso}.technologies.*.degradation_by_zone.hot_zone_sensitivity",
    "countries.{iso}.connection.transmission_loss_per_km_sensitivity",
    "countries.{iso}.connection.poi_sensitivity_threshold_kv",
)
EXPERIMENT_SELECTORS: tuple[str, ...] = (
    "thresholds.regret_quantile",
    "prim.outcome_threshold",
    "prim.sensitivity",
    "hypothesis_rules.H5.sensitivity_lambda",
    "windows.sensitivity",
    "national_targets.{iso}",
)
SUBSET: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("parameters", PARAMETER_SELECTORS),
    ("experiments", EXPERIMENT_SELECTORS),
)

# values that mark a country as a test fixture (`VerifiedValue.synthetic`): the guard ignores such a country
_SYNTHETIC_PROBES: tuple[str, ...] = (
    "countries.{iso}.technologies.*.tau_lcoe_usd_per_mwh",
    "countries.{iso}.technologies.*.cf_min",
    "countries.{iso}.technologies.*.top_k_percent",
)


class PreregistrationError(RuntimeError):
    """The pre-registered subset is not the one in the tag `prereg-v1`, or the tag is not usable; the phase must not run (DEC-081 item g)."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def subset_values(iso: str, source: ConfigSource) -> dict[str, Any]:
    """The key of the subset (`<file>:<selector>` with the country) -> its validated value, for `iso`; a key the config lacks is `ABSENT`."""
    values: dict[str, Any] = {}
    for file_key, selectors in SUBSET:
        doc = _parse(file_key, source.text(file_key))
        for selector in selectors:
            path = selector.replace(_ISO, iso)
            values[f"{file_key}:{path}"] = _select(doc, path) if doc is not None else ABSENT
    return values


def key_digests(values: Mapping[str, Any]) -> dict[str, str]:
    """The SHA-256 of the canonical JSON of each value of the subset."""
    return {key: _sha(_canonical(value)) for key, value in values.items()}


def country_digest(values: Mapping[str, Any]) -> str:
    """The digest of the subset of one country."""
    return _sha(_canonical({"subset_version": SUBSET_VERSION, "keys": dict(values)}))


def aggregate_digest(per_country: Mapping[str, str]) -> str:
    """The digest of the subset of every registered country: the SHA-256 of `{iso: country digest}`."""
    return _sha(_canonical(dict(per_country)))


def is_synthetic(iso: str, source: ConfigSource) -> bool:
    """True when the country's decision parameters are test values (`synthetic: true`): the guard ignores it."""
    doc = _parse("parameters", source.text("parameters"))
    if doc is None:
        return False
    for probe in _SYNTHETIC_PROBES:
        found = _select(doc, probe.replace(_ISO, iso))
        entries = found.values() if isinstance(found, dict) else []
        if any(isinstance(e, dict) and e.get("synthetic") is True for e in entries):
            return True
    return False


def registered_countries(source: ConfigSource) -> list[str]:
    """The countries of `parameters.json` that are not test fixtures, in file order."""
    doc = _parse("parameters", source.text("parameters")) or {}
    return [iso for iso in doc.get("countries", {}) if not is_synthetic(iso, source)]


@dataclass(frozen=True)
class SubsetDigests:
    """The digests of the live subset: per key and per country, and the aggregate."""

    keys: dict[str, dict[str, str]]  # iso -> key -> digest
    countries: dict[str, str]  # iso -> digest
    aggregate: str


def live_digests(countries: Sequence[str], source: ConfigSource) -> SubsetDigests:
    """The digests of the subset of the configuration `source` holds, for `countries`."""
    keys: dict[str, dict[str, str]] = {}
    per_country: dict[str, str] = {}
    for iso in countries:
        values = subset_values(iso, source)
        keys[iso] = key_digests(values)
        per_country[iso] = country_digest(values)
    return SubsetDigests(keys=keys, countries=per_country, aggregate=aggregate_digest(per_country))


def tag_message(digests: SubsetDigests, name: str = TAG_NAME) -> str:
    """The text of the annotated tag: the aggregate, the digest of each country and the digest of each key, one per line."""
    lines = [name, f"subset_version: {SUBSET_VERSION}", f"aggregate: {digests.aggregate}"]
    lines += [f"country {iso}: {digest}" for iso, digest in digests.countries.items()]
    for iso, by_key in digests.keys.items():
        lines += [f"key {iso} {key}: {digest}" for key, digest in by_key.items()]
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class ParsedTag:
    """What the message of the tag says: the subset version, the aggregate, the digest of each country and of each key."""

    subset_version: int | None
    aggregate: str | None
    countries: dict[str, str]
    keys: dict[str, dict[str, str]]


_COUNTRY_LINE = re.compile(r"^country (\S+): ([0-9a-f]{64})$")
_KEY_LINE = re.compile(r"^key (\S+) (\S+): ([0-9a-f]{64})$")
_AGGREGATE_LINE = re.compile(r"^aggregate: ([0-9a-f]{64})$")
_VERSION_LINE = re.compile(r"^subset_version: (\d+)$")


def parse_tag_message(text: str) -> ParsedTag:
    """Read the message written by `tag_message`; a line that is none of its forms is ignored (a message may carry a free comment)."""
    version: int | None = None
    aggregate: str | None = None
    countries: dict[str, str] = {}
    keys: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        if m := _VERSION_LINE.match(line):
            version = int(m.group(1))
        elif m := _AGGREGATE_LINE.match(line):
            aggregate = m.group(1)
        elif m := _COUNTRY_LINE.match(line):
            countries[m.group(1)] = m.group(2)
        elif m := _KEY_LINE.match(line):
            keys.setdefault(m.group(1), {})[m.group(2)] = m.group(3)
    return ParsedTag(version, aggregate, countries, keys)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)


def read_tag_message(repo: Path, name: str = TAG_NAME) -> str | None:
    """The message of the annotated tag `name` of the local repository `repo`, or None when the tag does not exist.

    Raises:
        PreregistrationError: the tag exists and is not an annotated tag (a lightweight tag carries no digest).
    """
    kind = _git(repo, "cat-file", "-t", f"refs/tags/{name}")
    if kind.returncode != 0:
        return None
    if kind.stdout.strip() != "tag":
        raise PreregistrationError(f"{name} is a lightweight tag: it must be an annotated tag whose message carries the digest of the subset")
    message = _git(repo, "tag", "-l", "--format=%(contents)", name)
    if message.returncode != 0:
        raise PreregistrationError(f"git could not read the message of the tag {name}: {message.stderr.strip()}")
    return message.stdout


def changed_keys(iso: str, live: SubsetDigests, tag: ParsedTag) -> list[str]:
    """The keys of `iso` whose digest differs from the tag (or that the tag does not list), sorted."""
    registered = tag.keys.get(iso, {})
    current = live.keys[iso]
    names = set(current) | set(registered)
    return sorted(key for key in names if current.get(key) != registered.get(key))


def verify(iso: str, source: ConfigSource, repo: Path, name: str = TAG_NAME) -> Preregistration | None:
    """The check of F6 and F7 on the data of `iso` (DEC-081 item g).

    Returns None for a country whose parameters are `synthetic: true` (ignored: no tag is read), and otherwise the two digests that were compared.

    Raises:
        PreregistrationError: the tag is absent, is not annotated, does not list the country, or its digest differs from the live one; the message
            names the keys that changed.
    """
    if is_synthetic(iso, source):
        return None
    message = read_tag_message(repo, name)
    if message is None:
        raise PreregistrationError(
            f"F6 and F7 on real data need the annotated tag {name} (COMMAND 162T): it does not exist in {repo}. Until it exists the decision parameters are a draft."
        )
    tag = parse_tag_message(message)
    live = live_digests([iso], source)
    digest_tag = tag.countries.get(iso)
    if digest_tag is None:
        raise PreregistrationError(f"the tag {name} does not register {iso}: its message lists {sorted(tag.countries)}")
    if tag.subset_version != SUBSET_VERSION:
        raise PreregistrationError(f"the tag {name} is of subset_version {tag.subset_version}, this code is {SUBSET_VERSION}")
    if live.countries[iso] != digest_tag:
        changed = changed_keys(iso, live, tag)
        raise PreregistrationError(
            f"the pre-registered subset of {iso} differs from the tag {name}: {', '.join(changed) if changed else 'no key differs, the digest does'}. "
            "A change after the tag is a deviation; it is not run and it is not rebaselined."
        )
    return Preregistration(digest_live=live.countries[iso], digest_tag=digest_tag)


def tag_conflict(countries: Sequence[str], source: ConfigSource, repo: Path, name: str = TAG_NAME) -> list[str] | None:
    """For `countries`, the keys that differ from the tag `name`; None when the tag does not exist, an empty list when the subset is the registered one."""
    message = read_tag_message(repo, name)
    if message is None:
        return None
    tag = parse_tag_message(message)
    live = live_digests(countries, source)
    out: list[str] = []
    for iso in countries:
        if iso not in tag.countries:
            out.append(f"{iso}: not registered in the tag")
        elif live.countries[iso] != tag.countries[iso]:
            out += [f"{iso} {key}" for key in changed_keys(iso, live, tag)] or [f"{iso}: digest differs"]
    return out
