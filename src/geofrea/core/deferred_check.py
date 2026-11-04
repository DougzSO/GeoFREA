"""Deferred content check of a country against a reference manifest (COMMAND 80; D-core-050).

The performance work of COMMANDS 75 to 77 changed how the phases compute, not what they compute. For PRT every artifact of F1 to F5 was proved equal by
content hash; for IND and BRA the proof is made by this check, the first time the pipeline runs those phases on the new code. `config/deferred_checks.yaml`
names, per country, the manifest saved before the change (the reference) and the phases to check. Each time a listed phase is *executed* (a phase that
only resumes from its manifest entry proves nothing about the new code), the content hash of each of its artifacts is compared with the reference:

  IDENTICO           every artifact has the hash of the reference
  EXPLICADO          some differ, and the configuration the phase reads changed between the reference and now (`config_fingerprint`): the
                     difference is the one the change of configuration is expected to cause (BRA F5: `wind_cf_integral` exact -> table)
  EXPLICADO_REVISAR  some differ, with no change of configuration, but the artifact is named in `expected` of the country: it carries no result and
                     its difference is explained in the file (BRA `audit_report`); it is flagged for a manual look
  EQUIVALENTE        some differ in hash, and each of them is a raster that has a reference file (the reference store, `core.reference_store`) and is equal to it
                     within the tolerance of CONVENTIONS (`core.equivalence`: |d| <= 1e-6 |ref| + 1e-9, same grid, same missing pixels): a last-bit
                     difference of a float, decided by the numbers and not by an entry in `expected` (COMMAND 91)
  DIFERENTE          some differ with no change of configuration and no entry in `expected`: the run stops before the phases that follow and
                     the artifacts, the probable cause (`suspects` of the phase) and the reference are written in the report

An entry of `expected` is pinned to the reference it was declared against: it records the `reference_run` (a run_id of the store) and counts only while that round
is the reference of the country (`reference_run: latest` resolves to the last accepted round). When `latest` moves on, the entry is expired: it explains nothing,
the gate warns, and `scripts/list_expired_expected.py` lists what can be removed from the file.

The report is `outputs/<ISO>/deferred_check.json`, kept between runs: a phase that has a verdict other than DIFERENTE is settled and is not compared
again (a later change of data or code is not an error of this check); one that has DIFERENTE is compared again at its next execution. The overall
verdict is DIFERENTE, PENDENTE (a listed phase has not run yet), REVISAR, EQUIVALENTE or IDENTICO. Removing a country from the file retires its check.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from geofrea.core.reference_store import ReferenceStore, StoreConfig

logger = logging.getLogger(__name__)

REPORT_NAME = "deferred_check.json"
SETTLED = ("IDENTICO", "EQUIVALENTE", "EXPLICADO", "EXPLICADO_REVISAR")
MAX_LISTED = 8


def content_of(entry: dict) -> str:
    """The canonical content hash of a manifest artifact entry (the hash of the bytes where it has none)."""
    return entry.get("content_sha256") or entry["sha256"]


def compare_artifacts(before: dict, after: dict, phases: list[str] | None = None) -> dict:
    """Per artifact of `phases`: IDENTICO, DIFERENTE, AUSENTE_ANTES or AUSENTE_DEPOIS, and whether the phase's configuration changed.

    `before` and `after` are manifests as dictionaries (`artifacts` and `phases`).
    """
    wanted = set(phases) if phases is not None else None
    keys = sorted(k for k, e in {**before["artifacts"], **after["artifacts"]}.items() if wanted is None or e["phase"] in wanted)
    rows = {}
    for key in keys:
        old, new = before["artifacts"].get(key), after["artifacts"].get(key)
        phase = (new or old)["phase"]
        if old is None:
            status = "AUSENTE_ANTES"
        elif new is None:
            status = "AUSENTE_DEPOIS"
        else:
            status = "IDENTICO" if content_of(old) == content_of(new) else "DIFERENTE"
        rows[key] = {"phase": phase, "status": status, "before": old and content_of(old), "after": new and content_of(new)}
    config_changed = {
        p: before["phases"][p].get("config_fingerprint") != after["phases"][p].get("config_fingerprint")
        for p in {r["phase"] for r in rows.values()}
        if p in before["phases"] and p in after["phases"]
    }
    for row in rows.values():
        row["config_changed"] = bool(config_changed.get(row["phase"]))
    return rows


@dataclass(frozen=True)
class CountryCheck:
    """The check of one country, as `config/deferred_checks.yaml` states it."""

    iso: str
    baseline: Path | None  # the manifest of the reference, or None when it is the round `reference_run` of the store (`baseline: latest` in the yaml)
    baseline_label: str
    phases: tuple[str, ...]
    expected: dict[str, str] = field(default_factory=dict)  # artifact key -> why its difference is accepted
    expected_pins: dict[str, str] = field(default_factory=dict)  # artifact key -> the run_id of the reference it was declared against
    suspects: dict[str, str] = field(default_factory=dict)  # phase -> probable cause of an unexplained difference
    reference_run: str = "latest"  # the round of the reference store whose files the rasters are compared with: a run_id, or `latest` (the last accepted)


def parse_expected(iso: str, spec: dict) -> tuple[dict[str, str], dict[str, str]]:
    """`(reasons, pins)` of the `expected` block of a country.

    An entry is a text (the reason; its pin is the country's `expected_reference_run`) or a mapping `{reason, reference_run}`. An entry with no pin is refused: it
    would hold for every later reference.
    """
    default = spec.get("expected_reference_run")
    reasons: dict[str, str] = {}
    pins: dict[str, str] = {}
    for key, value in (spec.get("expected") or {}).items():
        if isinstance(value, dict):
            reason, pin = value.get("reason"), value.get("reference_run", default)
        else:
            reason, pin = value, default
        if not reason or not pin:
            raise ValueError(f"{iso}: the `expected` entry {key!r} needs a reason and the reference_run it was declared against (expected_reference_run)")
        reasons[str(key)] = str(reason)
        pins[str(key)] = str(pin)
    return reasons, pins


def load_checks(yaml_path: Path, data_root: Path) -> dict[str, CountryCheck]:
    """The checks of `yaml_path` (none when the file is absent); the baseline paths are relative to the data root."""
    if not Path(yaml_path).is_file():
        return {}
    raw = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8")) or {}
    suspects = {str(k): str(v) for k, v in (raw.get("suspects") or {}).items()}
    checks = {}
    for iso, spec in (raw.get("countries") or {}).items():
        from_store = str(spec["baseline"]) == "latest"
        reasons, pins = parse_expected(str(iso).upper(), spec)
        checks[str(iso).upper()] = CountryCheck(
            iso=str(iso).upper(),
            baseline=None if from_store else Path(data_root) / str(spec["baseline"]),
            baseline_label=str(spec.get("label", "references/" + str(spec.get("reference_run", "latest")) if from_store else spec["baseline"])),
            phases=tuple(spec["phases"]),
            expected=reasons,
            expected_pins=pins,
            suspects=suspects,
            reference_run=str(spec.get("reference_run", "latest")),
        )
    return checks


def load_store(yaml_path: Path, data_root: Path) -> ReferenceStore:
    """The reference store of `data_root`, configured by the `reference_store` block of `yaml_path` (what to keep; defaults when the block is absent)."""
    raw = {}
    if Path(yaml_path).is_file():
        raw = (yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8")) or {}).get("reference_store") or {}
    defaults = StoreConfig()
    config = StoreConfig(
        suffixes=tuple(raw.get("suffixes", defaults.suffixes)),
        raster_phases=tuple(raw.get("raster_phases", defaults.raster_phases)),
    )
    return ReferenceStore(Path(data_root) / str(raw.get("root", "references")), config)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, path)


_WIND_LAYER = re.compile(r"(weibull_a|weibull_k|air_density)_\d+m")


def reference_names(key: str, after: Path, iso: str) -> list[str]:
    """The file names under which the reference of artifact `key` (the raster `after`) can be kept, in order.

    The same name (the aligned layers `<ISO>_<layer>_aligned.tif`) and, for the resource layers of F2b, the aligned layer they are a copy of
    (M-F2b-04: the values are kept, only the missing pixels take the F2b nodata): `pvout_kwh_kwp_day` is `<ISO>_solar_aligned.tif` and
    `weibull_a_100m` is `<ISO>_wind_weibull_a_100m_aligned.tif`.
    """
    names = [after.name]
    layer = key.split("/", 1)[1] if key.startswith("siting/") else None
    if layer == "pvout_kwh_kwp_day":
        names.append(f"{iso}_solar_aligned.tif")
    elif layer is not None and _WIND_LAYER.fullmatch(layer):
        names.append(f"{iso}_wind_{layer}_aligned.tif")
    return names


def reference_file(key: str, after: Path, iso: str, find: Callable[[str], Path | None]) -> Path | None:
    """The kept file that `after` (the raster of artifact `key`) is to be compared with, or None; `find(name)` looks a file name up in the store."""
    for name in reference_names(key, after, iso):
        found = find(name)
        if found is not None:
            return found
    return None


class DeferredCheck:
    """The check of one country; `Orchestrator` calls `after_phase` each time a phase has been executed."""

    def __init__(self, check: CountryCheck, report_path: Path, store: ReferenceStore | None = None) -> None:
        self.check = check
        self.report_path = Path(report_path)
        self.store = store
        self._baseline: dict | None = None

    def _load_report(self) -> dict:
        if self.report_path.is_file():
            try:
                report = json.loads(self.report_path.read_text(encoding="utf-8"))
                if report.get("baseline") == self.check.baseline_label:
                    return report
                logger.info("%s was made against %s, not %s; the check starts again", self.report_path, report.get("baseline"), self.check.baseline_label)
            except (OSError, ValueError):
                logger.warning("%s is unreadable; the check starts again", self.report_path)
        return {"country": self.check.iso, "baseline": self.check.baseline_label, "phases": {}}

    def reference_run_id(self) -> str | None:
        """The run_id the check compares with now (`latest` resolved), or None when the baseline is a manifest outside the store or there is no store."""
        if self.check.baseline is not None or self.store is None:
            return None
        return self.store.resolve(self.check.iso, self.check.reference_run)

    def expired_expected(self) -> dict[str, str]:
        """The entries of `expected` declared against a reference that is no longer the one compared with: key -> the run_id they were declared against."""
        current = self.reference_run_id()
        if self.check.baseline is not None or self.store is None:
            return {}
        return {k: pin for k, pin in self.check.expected_pins.items() if pin != current}

    def active_expected(self) -> dict[str, str]:
        """The entries of `expected` that count now: key -> reason."""
        expired = self.expired_expected()
        return {k: v for k, v in self.check.expected.items() if k not in expired}

    def _baseline_path(self) -> Path | None:
        if self.check.baseline is not None:
            return self.check.baseline
        return None if self.store is None else self.store.manifest_path(self.check.iso, self.check.reference_run)

    def _baseline_manifest(self) -> dict | None:
        path = self._baseline_path()
        if self._baseline is None and path is not None and path.is_file():
            self._baseline = json.loads(path.read_text(encoding="utf-8"))
        return self._baseline

    @staticmethod
    def _after_view(manifest: Any, phase: str) -> dict:
        """The artifacts and the configuration fingerprint of `phase` in the manifest of the run, in the shape `compare_artifacts` reads."""
        artifacts = {
            key: {"phase": e.phase, "content_sha256": e.content_sha256, "sha256": e.sha256, "path": e.path}
            for key, e in manifest.artifacts.items()
            if e.phase == phase
        }
        return {"artifacts": artifacts, "phases": {phase: {"config_fingerprint": manifest.phases[phase].config_fingerprint}}}

    def _by_tolerance(self, manifest: Any, keys: list[str]) -> tuple[dict[str, dict], dict[str, dict]]:
        """Compare the rasters among `keys` that have a reference file with it by tolerance: (the equivalent ones, every comparison made).

        An artifact with no reference file, or that is not a raster, is not decided here and stays among the differences nobody explained.
        """
        equivalent: dict[str, dict] = {}
        compared: dict[str, dict] = {}
        if self.store is None or self.store.resolve(self.check.iso, self.check.reference_run) is None:
            return equivalent, compared
        from geofrea.core.equivalence import compare_rasters

        for key in keys:
            entry = manifest.artifacts.get(key)
            if entry is None:
                continue
            after = Path(entry.path.resolve())
            if after.suffix.lower() not in (".tif", ".tiff"):
                continue
            reference = reference_file(key, after, self.check.iso, lambda name: self.store.find(self.check.iso, self.check.reference_run, name))
            if reference is None:
                continue
            result = compare_rasters(reference, after).as_dict()
            result["reference"] = reference.name
            compared[key] = result
            if result["equivalent"]:
                equivalent[key] = result
        return equivalent, compared

    def verdicts(self) -> dict[str, str]:
        """The verdict of each listed phase in the report on disk (a phase not yet compared is absent)."""
        phases = self._load_report()["phases"]
        return {p: phases[p]["verdict"] for p in self.check.phases if p in phases}

    def blocked_phases(self) -> list[str]:
        """The listed phases whose verdict is DIFERENTE: a round with one of them is not accepted."""
        return [p for p, v in self.verdicts().items() if v == "DIFERENTE"]

    def after_phase(self, manifest: Any, phase: str) -> str | None:
        """Compare the artifacts of the phase that has just been executed with the reference; the message of an unexplained difference, else None."""
        if phase not in self.check.phases:
            return None
        report = self._load_report()
        if report["phases"].get(phase, {}).get("verdict") in SETTLED:
            return None
        baseline = self._baseline_manifest()
        if baseline is None:
            report["phases"][phase] = {"verdict": "SEM_REFERENCIA", "checked_at": _now(), "note": f"the reference {self.check.baseline_label} does not exist"}
            logger.warning("deferred check %s/%s: the reference manifest %s does not exist; nothing compared", self.check.iso, phase, self.check.baseline_label)
            self._finish(report)
            return None
        if phase not in baseline["phases"]:
            report["phases"][phase] = {"verdict": "SEM_REFERENCIA", "checked_at": _now(), "note": "the phase is not in the reference manifest"}
            self._finish(report)
            return None

        expected = self.active_expected()
        expired = {k: p for k, p in self.expired_expected().items()}
        rows = compare_artifacts(baseline, self._after_view(manifest, phase), [phase])
        different = {k: r for k, r in rows.items() if r["status"] in ("DIFERENTE", "AUSENTE_DEPOIS")}
        with_config = sorted(k for k, r in different.items() if r["config_changed"])
        accepted = sorted(k for k, r in different.items() if not r["config_changed"] and k in expected)
        unexplained = sorted(k for k, r in different.items() if not r["config_changed"] and k not in expected)
        equivalent, compared = self._by_tolerance(manifest, unexplained)
        unexplained = [k for k in unexplained if k not in equivalent]
        verdict = (
            "DIFERENTE" if unexplained else "EXPLICADO_REVISAR" if accepted else "EXPLICADO" if with_config else "EQUIVALENTE" if equivalent else "IDENTICO"
        )
        entry = {
            "verdict": verdict,
            "checked_at": _now(),
            "code_fingerprint": manifest.phases[phase].code_fingerprint,
            "n_artifacts": len(rows),
            "n_identico": sum(r["status"] == "IDENTICO" for r in rows.values()),
            "different_with_config_change": with_config,
            "different_expected": {k: expected[k] for k in accepted},
            "expired_expected": sorted(k for k in expired if k in different),  # differences that an expired entry would have explained
            "different_equivalent": equivalent,
            "different_unexplained": {
                k: {"before": rows[k]["before"], "after": rows[k]["after"], "status": rows[k]["status"], **({"comparison": compared[k]} if k in compared else {})}
                for k in unexplained
            },
            "new": sorted(k for k, r in rows.items() if r["status"] == "AUSENTE_ANTES"),
        }
        if expired:
            logger.warning(
                "deferred check %s/%s: %d entries of `expected` were declared against an earlier reference and no longer count (the reference is now %s): %s. "
                "Run scripts/list_expired_expected.py; remove them from config/deferred_checks.yaml.",
                self.check.iso, phase, len(expired), self.reference_run_id(), ", ".join(sorted(expired)[:MAX_LISTED]) + (" ..." if len(expired) > MAX_LISTED else ""),
            )
        message = None
        if unexplained:
            cause = self.check.suspects.get(phase, "not listed in config/deferred_checks.yaml: compare the code of the phase with the reference revision")
            entry["probable_cause"] = cause
            listed = ", ".join(unexplained[:MAX_LISTED]) + (f" (and {len(unexplained) - MAX_LISTED} more)" if len(unexplained) > MAX_LISTED else "")
            message = (
                f"deferred check {self.check.iso}/{phase}: {len(unexplained)} of {len(rows)} artifacts differ from the reference "
                f"{self.check.baseline_label} with no change of configuration to explain them: {listed}. Probable cause: {cause}. "
                f"The phases after {phase} did not run; the report is {self.report_path}."
            )
            stale = sorted(set(unexplained) & set(expired))
            if stale:
                message += f" {len(stale)} of them have an entry in `expected` declared against an earlier reference, which no longer counts: {', '.join(stale[:MAX_LISTED])}."
        report["phases"][phase] = entry
        self._finish(report)
        return message

    def _finish(self, report: dict) -> None:
        verdicts = [report["phases"].get(p, {}).get("verdict") for p in self.check.phases]
        if "DIFERENTE" in verdicts:
            overall = "DIFERENTE"
        elif any(v not in SETTLED for v in verdicts):
            overall = "PENDENTE"
        elif "EXPLICADO_REVISAR" in verdicts:
            overall = "REVISAR"
        elif "EQUIVALENTE" in verdicts:
            overall = "EQUIVALENTE"
        else:
            overall = "IDENTICO"
        report["verdict"] = overall
        report["updated_at"] = _now()
        report["pending"] = [p for p, v in zip(self.check.phases, verdicts) if v not in SETTLED]
        _write_json(self.report_path, report)
        logger.info("deferred check %s: %s (pending: %s)", self.check.iso, overall, ", ".join(report["pending"]) or "none")


def seed_from_comparison(check: CountryCheck, report_path: Path, comparison: dict, manifest: dict, source: str) -> list[str]:
    """Record as settled the phases that an earlier comparison with the same reference found IDENTICO, so the pipeline does not compare them again.

    `comparison` is an `unattended_check.json` (`artifacts` with `phase` and `status`, `phases` with `status`) made against the reference of `check`;
    `manifest` is the manifest of the country after that comparison (it holds the code fingerprint the phase ran with). A phase is recorded only if
    it is listed in `check`, ended `success` and every one of its artifacts was IDENTICO; the others stay pending. Returns the phases recorded.
    """
    guard = DeferredCheck(check, report_path)
    report = guard._load_report()
    recorded = []
    for row in comparison.get("phases", []):
        phase = row["phase"]
        if phase not in check.phases or row.get("status") != "success":
            continue
        rows = [a for a in comparison["artifacts"].values() if a["phase"] == phase]
        if not rows or any(a["status"] != "IDENTICO" for a in rows):
            continue
        if report["phases"].get(phase, {}).get("verdict") in SETTLED:
            continue
        report["phases"][phase] = {
            "verdict": "IDENTICO",
            "checked_at": _now(),
            "code_fingerprint": manifest["phases"][phase].get("code_fingerprint"),
            "n_artifacts": len(rows),
            "n_identico": len(rows),
            "different_with_config_change": [],
            "different_expected": {},
            "different_unexplained": {},
            "new": [],
            "source": source,
        }
        recorded.append(phase)
    guard._finish(report)
    return recorded


def for_country(iso: str, yaml_path: Path, data_root: Path, outputs_dir: Path) -> DeferredCheck | None:
    """The check of `iso` when `yaml_path` lists it, None otherwise; it reads the reference rasters from the store of `data_root`."""
    check = load_checks(yaml_path, data_root).get(iso.upper())
    if check is None:
        return None
    return DeferredCheck(check, Path(outputs_dir) / iso.upper() / REPORT_NAME, load_store(yaml_path, data_root))
