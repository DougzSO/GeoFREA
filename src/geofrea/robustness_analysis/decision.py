"""The decision parameters F7 reads and the outputs each one gates (A-09; D-F7-009, D-F7-023, D-F7-029).

`CF_min` is the feasibility rule: without it the evaluator has no meaning, so F7 refuses to start (listing it with the F6 inputs). Every other
decision parameter gates outputs: when one is null F7 writes the outputs that do not need it and lists the others as skipped, each with the
open question that blocks it. A production run refuses any null before it starts (`required_parameters` of `technologies.yaml`).
No value is ever created here.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from geofrea.core.config_schemas import ExperimentsFile
from geofrea.core.constants import PRICE_BASE_YEAR_USD

logger = logging.getLogger("geofrea.robustness_analysis.decision")


class RobustnessConfigError(RuntimeError):
    """A setting F7 cannot honor (for example a reference quantile other than 0, OQ-020) (A-09)."""


class RobustnessMissingInputError(RuntimeError):
    """F7 cannot start: the F6 inputs or the feasibility rule are absent; the message lists every missing item (A-09)."""

    def __init__(self, country: str, technology: str, missing: Sequence[str]) -> None:
        self.country = country
        self.technology = technology
        self.missing = list(missing)
        super().__init__(
            f"F7 cannot run for {country} {technology}: {len(self.missing)} missing item(s): "
            + "; ".join(self.missing)
        )


@dataclass(frozen=True)
class TechDecision:
    """The decision parameters of one technology in one country; `None` is a value the author has not given."""

    technology: str
    cf_min: float | None
    tau: float | None
    capacity_target_gw: float | None
    top_k_percent: float | None
    prim_outcome_share: float | None


@dataclass(frozen=True)
class SkippedOutput:
    """An output F7 did not write, and why."""

    output: str
    reason: str
    open_question: str


def regret_quantile(experiments: ExperimentsFile) -> float:
    """`q_ref` of M-F7-02; only 0 is built (D-F7-009).

    Raises:
        RobustnessConfigError: any other value.
    """
    q_ref = experiments.thresholds.get("regret_quantile")
    if q_ref != 0:
        raise RobustnessConfigError(
            f"thresholds.regret_quantile is {q_ref!r}: only q_ref = 0 is built, the sample-blocked quantile for q_ref > 0 waits for the author (OQ-020)"
        )
    return 0.0


def _value(entry: object) -> float | None:
    value = getattr(entry, "value", None)
    return None if value is None else float(value)


def decision_values(tech_params: object, technology: str) -> TechDecision:
    """Read the five decision parameters from a country's technology block of `parameters.json`."""
    return TechDecision(
        technology=technology,
        cf_min=_value(getattr(tech_params, "cf_min", None)),
        tau=_value(getattr(tech_params, "tau_lcoe_usd_per_mwh", None)),
        capacity_target_gw=_value(getattr(tech_params, "capacity_target_gw", None)),
        top_k_percent=_value(getattr(tech_params, "top_k_percent", None)),
        prim_outcome_share=_value(getattr(tech_params, "prim_outcome_share", None)),
    )


def refusals(tech_params: object) -> list[str]:
    """What makes F7 refuse a technology: the feasibility rule, and a threshold whose price year is not the base year (S-07)."""
    items: list[str] = []
    entry = getattr(tech_params, "cf_min", None)
    if entry is None:
        items.append("cf_min (no entry in parameters.json)")
    elif entry.value is None:
        items.append(f"cf_min ({entry.status or 'no value'}, OQ-008)")
    tau = getattr(tech_params, "tau_lcoe_usd_per_mwh", None)
    if tau is not None and tau.value is not None and tau.price_year != PRICE_BASE_YEAR_USD:
        items.append(
            f"tau_lcoe_usd_per_mwh price_year (is {tau.price_year}, S-07 needs {PRICE_BASE_YEAR_USD})"
        )
    return items


def check_ranges(decision: TechDecision) -> list[str]:
    """Values outside their domain (a value the author gave that cannot be used)."""
    items: list[str] = []
    if decision.cf_min is not None and not 0 <= decision.cf_min < 1:
        items.append(f"cf_min {decision.cf_min} outside [0, 1)")
    if decision.tau is not None and decision.tau <= 0:
        items.append(f"tau {decision.tau} is not positive")
    if decision.top_k_percent is not None and not 0 < decision.top_k_percent <= 100:
        items.append(f"top_k_percent {decision.top_k_percent} outside (0, 100]")
    if decision.prim_outcome_share is not None and not 0 < decision.prim_outcome_share <= 1:
        items.append(f"prim_outcome_share {decision.prim_outcome_share} outside (0, 1]")
    if decision.capacity_target_gw is not None and decision.capacity_target_gw < 0:
        items.append(f"capacity_target_gw {decision.capacity_target_gw} is negative")
    return items


def skipped_outputs(
    decision: TechDecision,
    experiments: ExperimentsFile,
    *,
    has_hazard_members: bool,
) -> list[SkippedOutput]:
    """The outputs that a null decision parameter or setting keeps F7 from writing (D-F7-023)."""
    skipped: list[SkippedOutput] = []
    if decision.tau is None:
        for output in (
            "SR, the satisficing tie-break, the MR-SR agreement (M-F7-04, M-F7-09)",
            "potential below tau per future (T-R12, H5)",
        ):
            skipped.append(SkippedOutput(output, "tau_lcoe_usd_per_mwh is null", "OQ-008"))
    if decision.top_k_percent is None:
        skipped.append(
            SkippedOutput(
                "top-k sets, H1, H3, H4, the futures table, PRIM (M-F7-05 to M-F7-08)",
                "top_k_percent is null",
                "OQ-021",
            )
        )
    if decision.capacity_target_gw is None:
        skipped.append(
            SkippedOutput(
                "capacity-target top-k and the gap to the target (M-F7-05, H5)",
                "capacity_target_gw is null",
                "OQ-010",
            )
        )
    prim = experiments.prim
    if decision.prim_outcome_share is None or prim.peel_alpha is None or prim.mass_min is None:
        reasons = [
            name
            for name, missing in (
                ("prim_outcome_share", decision.prim_outcome_share is None),
                ("prim.peel_alpha", prim.peel_alpha is None),
                ("prim.mass_min", prim.mass_min is None),
            )
            if missing
        ]
        skipped.append(
            SkippedOutput("PRIM boxes (M-F7-08)", f"{', '.join(reasons)} is null", "OQ-056")
        )
    if has_hazard_members:
        for indicator, threshold in experiments.hazard_thresholds.items():
            if threshold.threshold is None:
                skipped.append(
                    SkippedOutput(
                        f"exposure to {indicator} (T-R10, H5)",
                        f"hazard_thresholds.{indicator} is null",
                        "OQ-051",
                    )
                )
    else:
        skipped.append(
            SkippedOutput(
                "hazard exposure (T-R10, H5)", "no member carries the hazard channel", "OQ-007"
            )
        )
    return skipped


def rules_for(experiments: ExperimentsFile) -> tuple[Mapping[str, list], list[str]]:
    """The pre-registered rules per hypothesis and the hypotheses that have none (OQ-050)."""
    rules = {h: r for h, r in experiments.hypothesis_rules.items() if r}
    missing = [h for h, r in experiments.hypothesis_rules.items() if not r]
    return rules, missing
