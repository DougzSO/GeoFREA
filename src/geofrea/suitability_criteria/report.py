"""Bespoke text summary for suitability_criteria (Fase 2b).

Mirrors data_quality_audit/audit.py's `_format_report` / `_save_report`
pattern (bespoke string builder, saved under
outputs/<code>/<phase>/reports/). A generic build_phase_report() is NOT
built here: it would be an abstraction with a single real consumer and
no second use case to design its API against (GAP-004, still open — see
docs/architecture/suitability_criteria_audit.md sec 2a and the
DECISIONS.md 2026-09-10 decision to defer it).

Report filename matches the legacy's: criteria_summary_<ISO3>.txt.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from geofrea.suitability_criteria.schemas import CriterionLayer


def format_criteria_report(
    country_code: str,
    timestamp: str,
    criteria: Mapping[str, CriterionLayer],
    missing_expected: list[str],
    not_implemented: list[str],
    protected_source: str,
    timings: Mapping[str, float] | None = None,
) -> str:
    """Build the criteria-summary text.

    Args:
        country_code: ISO-3166-alpha-3 code.
        timestamp: ISO-8601 timestamp of the run.
        criteria: Produced CriterionLayers, keyed by name.
        missing_expected: Wired criteria whose input layer was absent
            this run.
        not_implemented: Criteria with no compute function in this build
            yet.
        protected_source: "wdpa" or "assumed_free".
        timings: Optional per-criterion wall-clock seconds.

    Returns:
        The report as a single string.
    """
    timings = timings or {}
    lines: list[str] = []
    width = 64

    def sep(ch: str = "=") -> None:
        lines.append(ch * width)

    sep()
    lines.append("  SUITABILITY CRITERIA SUMMARY (Fase 2b)")
    lines.append(f"  {country_code}")
    lines.append(f"  {timestamp[:19].replace('T', ' ')}")
    sep()
    lines.append("")
    lines.append(f"  Criteria produced : {len(criteria)}")
    lines.append(f"  Protected source  : {protected_source}")
    if missing_expected:
        lines.append(f"  Input absent      : {', '.join(sorted(missing_expected))}")
    if not_implemented:
        lines.append(f"  Not implemented   : {', '.join(sorted(not_implemented))}")
    lines.append("")
    sep("-")

    for name in sorted(criteria):
        layer = criteria[name]
        t = timings.get(name)
        header = f"  [OK] {name}" + (f"  [{t:.1f}s]" if t is not None else "")
        lines.append(header)
        lines.append(f"      Valid pixels : {layer.valid_pixels:>10,}")
        lines.append(f"      Mean +/- Std : {layer.mean:.4f} +/- {layer.std:.4f}")
        lines.append(
            f"      P10/P50/P90  : {layer.p10:.3f} / {layer.p50:.3f} / {layer.p90:.3f}"
        )
        lines.append(f"      Score >= 0.6 : {100 * layer.frac_ge_0_6:.1f}%")
        lines.append("")

    sep()
    lines.append("")
    return "\n".join(lines)


def save_criteria_report(text: str, country_code: str, outputs_dir: Path) -> Path:
    """Write the report to outputs/<code>/suitability_criteria/reports/.

    Args:
        text: The report body.
        country_code: ISO-3166-alpha-3 code.
        outputs_dir: Run-level outputs directory.

    Returns:
        The path written.
    """
    reports_dir = outputs_dir / country_code / "suitability_criteria" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"criteria_summary_{country_code}.txt"
    path.write_text(text, encoding="utf-8")
    return path
