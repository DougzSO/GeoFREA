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
  DIFERENTE          some differ with no change of configuration and no entry in `expected`: the run stops before the phases that follow and
                     the artifacts, the probable cause (`suspects` of the phase) and the reference are written in the report

The report is `outputs/<ISO>/deferred_check.json`, kept between runs: a phase that has a verdict other than DIFERENTE is settled and is not compared
again (a later change of data or code is not an error of this check); one that has DIFERENTE is compared again at its next execution. The overall
verdict is DIFERENTE, PENDENTE (a listed phase has not run yet), REVISAR or IDENTICO. Removing a country from the file retires its check.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

REPORT_NAME = "deferred_check.json"
SETTLED = ("IDENTICO", "EXPLICADO", "EXPLICADO_REVISAR")
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
    baseline: Path
    baseline_label: str
    phases: tuple[str, ...]
    expected: dict[str, str] = field(default_factory=dict)  # artifact key -> why its difference is accepted
    suspects: dict[str, str] = field(default_factory=dict)  # phase -> probable cause of an unexplained difference


def load_checks(yaml_path: Path, data_root: Path) -> dict[str, CountryCheck]:
    """The checks of `yaml_path` (none when the file is absent); the baseline paths are relative to the data root."""
    if not Path(yaml_path).is_file():
        return {}
    raw = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8")) or {}
    suspects = {str(k): str(v) for k, v in (raw.get("suspects") or {}).items()}
    checks = {}
    for iso, spec in (raw.get("countries") or {}).items():
        checks[str(iso).upper()] = CountryCheck(
            iso=str(iso).upper(),
            baseline=Path(data_root) / str(spec["baseline"]),
            baseline_label=str(spec.get("label", spec["baseline"])),
            phases=tuple(spec["phases"]),
            expected={str(k): str(v) for k, v in (spec.get("expected") or {}).items()},
            suspects=suspects,
        )
    return checks


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, path)


class DeferredCheck:
    """The check of one country; `Orchestrator` calls `after_phase` each time a phase has been executed."""

    def __init__(self, check: CountryCheck, report_path: Path) -> None:
        self.check = check
        self.report_path = Path(report_path)
        self._baseline: dict | None = None

    def _load_report(self) -> dict:
        if self.report_path.is_file():
            try:
                return json.loads(self.report_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                logger.warning("%s is unreadable; the check starts again", self.report_path)
        return {"country": self.check.iso, "baseline": self.check.baseline_label, "phases": {}}

    def _baseline_manifest(self) -> dict | None:
        if self._baseline is None and self.check.baseline.is_file():
            self._baseline = json.loads(self.check.baseline.read_text(encoding="utf-8"))
        return self._baseline

    @staticmethod
    def _after_view(manifest: Any, phase: str) -> dict:
        """The artifacts and the configuration fingerprint of `phase` in the manifest of the run, in the shape `compare_artifacts` reads."""
        artifacts = {
            key: {"phase": e.phase, "content_sha256": e.content_sha256, "sha256": e.sha256}
            for key, e in manifest.artifacts.items()
            if e.phase == phase
        }
        return {"artifacts": artifacts, "phases": {phase: {"config_fingerprint": manifest.phases[phase].config_fingerprint}}}

    def after_phase(self, manifest: Any, phase: str) -> str | None:
        """Compare the artifacts of the phase that has just been executed with the reference; the message of an unexplained difference, else None."""
        if phase not in self.check.phases:
            return None
        report = self._load_report()
        if report["phases"].get(phase, {}).get("verdict") in SETTLED:
            return None
        baseline = self._baseline_manifest()
        if baseline is None:
            report["phases"][phase] = {"verdict": "SEM_REFERENCIA", "checked_at": _now(), "note": f"the reference {self.check.baseline} does not exist"}
            logger.warning("deferred check %s/%s: the reference manifest %s does not exist; nothing compared", self.check.iso, phase, self.check.baseline)
            self._finish(report)
            return None
        if phase not in baseline["phases"]:
            report["phases"][phase] = {"verdict": "SEM_REFERENCIA", "checked_at": _now(), "note": "the phase is not in the reference manifest"}
            self._finish(report)
            return None

        rows = compare_artifacts(baseline, self._after_view(manifest, phase), [phase])
        different = {k: r for k, r in rows.items() if r["status"] in ("DIFERENTE", "AUSENTE_DEPOIS")}
        with_config = sorted(k for k, r in different.items() if r["config_changed"])
        accepted = sorted(k for k, r in different.items() if not r["config_changed"] and k in self.check.expected)
        unexplained = sorted(k for k, r in different.items() if not r["config_changed"] and k not in self.check.expected)
        verdict = "DIFERENTE" if unexplained else "EXPLICADO_REVISAR" if accepted else "EXPLICADO" if with_config else "IDENTICO"
        entry = {
            "verdict": verdict,
            "checked_at": _now(),
            "code_fingerprint": manifest.phases[phase].code_fingerprint,
            "n_artifacts": len(rows),
            "n_identico": sum(r["status"] == "IDENTICO" for r in rows.values()),
            "different_with_config_change": with_config,
            "different_expected": {k: self.check.expected[k] for k in accepted},
            "different_unexplained": {k: {"before": rows[k]["before"], "after": rows[k]["after"], "status": rows[k]["status"]} for k in unexplained},
            "new": sorted(k for k, r in rows.items() if r["status"] == "AUSENTE_ANTES"),
        }
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
    """The check of `iso` when `yaml_path` lists it, None otherwise."""
    check = load_checks(yaml_path, data_root).get(iso.upper())
    if check is None:
        return None
    return DeferredCheck(check, Path(outputs_dir) / iso.upper() / REPORT_NAME)
