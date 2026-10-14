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

from geofrea.core.config_schemas import (
    ExperimentsFile,
    H1Rule,
    H2Rule,
    H3Rule,
    H4Rule,
    H5Rule,
    HypothesisRule,
)
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
    tau_range: tuple[float, float] | None = None
    capacity_target_note: str | None = None


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


def _range(entry: object) -> tuple[float, float] | None:
    bounds = getattr(entry, "range", None)
    if (
        bounds is None
        or getattr(bounds, "min", None) is None
        or getattr(bounds, "max", None) is None
    ):
        return None
    return float(bounds.min), float(bounds.max)


def capacity_target_gw(target: object | None) -> tuple[float | None, str | None]:
    """The target of the top-k sensitivity in GW, derived from the national target of `experiments.yaml` (the one source of the target).

    Implements: M-F7-05, M-F7-07 (OQ-010). A target in GW is used as it is; one in TWh/year has no registered conversion to capacity and
    the capacity-target top-k is then not testable, with the reason.

    Returns:
        `(value in GW or None, why there is none or None)`.
    """
    value = getattr(target, "value", None)
    if value is None:
        return None, "national_targets has no value"
    unit = getattr(target, "unit", None)
    if unit == "GW":
        return float(value), None
    return None, f"the national target is in {unit}, with no registered conversion to GW"


def decision_values(
    tech_params: object, technology: str, national_target: object | None = None
) -> TechDecision:
    """Read the decision parameters from a country's technology block of `parameters.json`, the sourced range of `tau` (H5) and the capacity target
    derived from the national target (`national_targets` of `experiments.yaml`, the only definition of the target)."""
    target_gw, note = capacity_target_gw(national_target)
    return TechDecision(
        technology=technology,
        cf_min=_value(getattr(tech_params, "cf_min", None)),
        tau=_value(getattr(tech_params, "tau_lcoe_usd_per_mwh", None)),
        capacity_target_gw=target_gw,
        capacity_target_note=note,
        top_k_percent=_value(getattr(tech_params, "top_k_percent", None)),
        tau_range=_range(getattr(tech_params, "tau_lcoe_usd_per_mwh", None)),
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
                decision.capacity_target_note or "national_targets has no value",
                "OQ-010",
            )
        )
    if h1_rule(experiments) is None:
        skipped.append(
            SkippedOutput(
                "H1 scores per SSP, C_k, V_k, the verdict and the sensitivities (M-F7-07)",
                "hypothesis_rules.H1 is null",
                "OQ-050",
            )
        )
    if h2_rule(experiments) is None:
        skipped.append(
            SkippedOutput(
                "H2 selections, the Capacity Overlap Index, the verdict and the sensitivities (M-F7-07)",
                "hypothesis_rules.H2 is null",
                "OQ-050",
            )
        )
    if h3_rule(experiments) is None:
        skipped.append(
            SkippedOutput(
                "H3 shortlists, the robust capacity outside the nominal plan, the verdict and the sensitivities (M-F7-07)",
                "hypothesis_rules.H3 is null",
                "OQ-050",
            )
        )
    if h4_rule(experiments) is None:
        skipped.append(
            SkippedOutput(
                "H4 axis displacements, the dominance ratio, the profile and the sensitivities (M-F7-06, M-F7-07)",
                "hypothesis_rules.H4 is null",
                "OQ-050",
            )
        )
    if h5_rule(experiments) is None:
        skipped.append(
            SkippedOutput(
                "H5 energy loss, exposure, the verdict and the sensitivities (M-F7-07)",
                "hypothesis_rules.H5 is null",
                "OQ-050",
            )
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


H1_PRIMARY_STATISTICS = (
    "h1a_core_share",
    "h1b_vulnerable_share",
)  # H1a and H1b, in the order of alpha and beta


def h1_rule(experiments: ExperimentsFile) -> H1Rule | None:
    """The pre-registered rule of H1 (OQ-050), or None while it is null."""
    rule = experiments.hypothesis_rules.get("H1")
    return rule if isinstance(rule, H1Rule) else None


def h2_rule(experiments: ExperimentsFile) -> H2Rule | None:
    """The pre-registered rule of H2 (OQ-050), or None while it is null."""
    rule = experiments.hypothesis_rules.get("H2")
    return rule if isinstance(rule, H2Rule) else None


def h3_rule(experiments: ExperimentsFile) -> H3Rule | None:
    """The pre-registered rule of H3 (OQ-050), or None while it is null."""
    rule = experiments.hypothesis_rules.get("H3")
    return rule if isinstance(rule, H3Rule) else None


def h4_rule(experiments: ExperimentsFile) -> H4Rule | None:
    """The pre-registered rule of H4 (OQ-050), or None while it is null."""
    rule = experiments.hypothesis_rules.get("H4")
    return rule if isinstance(rule, H4Rule) else None


def h5_rule(experiments: ExperimentsFile) -> H5Rule | None:
    """The pre-registered rule of H5 (OQ-050), or None while it is null."""
    rule = experiments.hypothesis_rules.get("H5")
    return rule if isinstance(rule, H5Rule) else None


def expanded_rules(experiments: ExperimentsFile) -> dict[str, list[HypothesisRule] | None]:
    """The rules as lists of (statistic, comparison, threshold): the H1 rule becomes `C_k >= alpha` and `V_k >= beta` (OQ-050)."""
    out: dict[str, list[HypothesisRule] | None] = {}
    for hypothesis, rule in experiments.hypothesis_rules.items():
        if isinstance(rule, H1Rule):
            out[hypothesis] = [
                HypothesisRule(
                    statistic=H1_PRIMARY_STATISTICS[0], comparison="ge", threshold=rule.alpha
                ),
                HypothesisRule(
                    statistic=H1_PRIMARY_STATISTICS[1], comparison="ge", threshold=rule.beta
                ),
            ]
        elif isinstance(rule, H2Rule | H3Rule | H4Rule | H5Rule):
            out[hypothesis] = (
                None  # the verdict depends on testability, so the module of the hypothesis gives it (h2_aggregation, h3_robust_vs_nominal)
            )
        else:
            out[hypothesis] = rule
    return out


def rules_for(experiments: ExperimentsFile) -> tuple[Mapping[str, list], list[str]]:
    """The pre-registered rules per hypothesis and the hypotheses that have none (OQ-050)."""
    expanded = expanded_rules(experiments)
    own_form = {
        h
        for h, r in experiments.hypothesis_rules.items()
        if isinstance(r, H2Rule | H3Rule | H4Rule | H5Rule)
    }
    rules = {h: r for h, r in expanded.items() if r}
    missing = [h for h, r in expanded.items() if not r and h not in own_form]
    return rules, missing
