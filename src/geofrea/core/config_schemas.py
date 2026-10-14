"""Pydantic schemas of `config/technologies.yaml` and `config/experiments.yaml` (A-04, Section 9, U-03).

Both files forbid unexpected keys: a misspelled key must raise, not be dropped. `experiments.yaml` keeps the blocks that other loaders
own (`gcm_ensemble`, `members`, `windows`, `thresholds`) as plain mappings here and types the rest. Consistency between the two
files and `parameters.json` (that every uncertain parameter has a range) is checked by `geofrea.core.production`, which is only
mandatory in a production run so research gaps (MS-6) do not block development.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from geofrea.land_eligibility.parameters import LandAvailability


class IecClassBound(BaseModel):
    """One class of the siting rule `iec_class_rule` (M-F5-03, D-F5-017): the class is taken by a cell whose annual mean wind
    speed at hub height is at most `mean_speed_upper_ms`; `null` marks the highest class (no upper limit)."""

    model_config = ConfigDict(extra="forbid")

    iec_class: str
    mean_speed_upper_ms: float | None
    source: str | None


class TechnologyConfig(BaseModel):
    """One entry of `technologies.yaml`: resources, capacity-factor model, exclusions, cost drivers, uncertain-parameter keys."""

    model_config = ConfigDict(extra="forbid")

    resource_layers: list[str]
    cf_model: str
    exclusions: list[str]
    cost_drivers: list[str]
    uncertain_parameters: list[str]
    required_parameters: list[str] = Field(
        default_factory=list
    )  # F5 inputs a production run must find (D-F5-011)
    power_curves: dict[str, str] | None = (
        None  # wind only: IEC class -> curve id in config/power_curves/ (OQ-005, D-F5-004)
    )
    iec_class_rule: list[IecClassBound] | None = (
        None  # wind only: lowest class first, last bound null (OQ-005, D-F5-017)
    )

    @model_validator(mode="after")
    def _curves_match_the_class_rule(self) -> TechnologyConfig:
        if self.iec_class_rule is not None and self.power_curves is not None:
            classes = [b.iec_class for b in self.iec_class_rule]
            if len(set(classes)) != len(classes) or set(classes) != set(self.power_curves):
                raise ValueError(
                    f"iec_class_rule classes {classes} must be the same distinct classes as power_curves {sorted(self.power_curves)}"
                )
        return self


class TechnologiesFile(BaseModel):
    """Root of `technologies.yaml`: technology name -> its configuration."""

    model_config = ConfigDict(extra="forbid")

    technologies: dict[str, TechnologyConfig]

    @model_validator(mode="after")
    def _not_empty(self) -> TechnologiesFile:
        if not self.technologies:
            raise ValueError("technologies.yaml declares no technology")
        return self


class UncertainParameterSpec(BaseModel):
    """An uncertain parameter of `experiments.yaml` (U-03); its values and range live in `parameters.json` (U-05)."""

    model_config = ConfigDict(extra="forbid")

    description: str


class SamplerConfig(BaseModel):
    """Parameter sampler (U-02, U-04, M-F6-02, A-12)."""

    model_config = ConfigDict(extra="forbid")

    method: Literal["latin_hypercube"]
    seed: int
    initial_size: int = Field(gt=0)
    # ceiling of the doubling of the sample size (U-04, D-F6-004); null until the author sets it
    max_size_for_convergence: int | None
    # the Jaccard distance between the top-k sets of consecutive sizes below which the size is adopted (U-04)
    convergence_tolerance: float = Field(gt=0)


class HypothesisRule(BaseModel):
    """One pre-registered decision rule (M-F7-07, OQ-050): the rule is met when `statistic <comparison> threshold`."""

    model_config = ConfigDict(extra="forbid")

    statistic: str
    comparison: Literal["ge", "gt", "le", "lt"]
    threshold: float


class H1Rule(BaseModel):
    """The pre-registered decision rule of H1 (M-F7-07, OQ-050): `C_k >= alpha` (H1a) and `V_k >= beta` (H1b) with the tolerance `m`.

    `tolerance_multiple_of_k` is `m / k`. `rbo_p` is the persistence of the descriptive rank-biased overlap, written as the formula the
    code evaluates (`1 - 1/k`); no other form is accepted. `source` is the citation of the pre-registration.
    """

    model_config = ConfigDict(extra="forbid")

    alpha: float = Field(gt=0, le=1)
    beta: float = Field(gt=0, le=1)
    tolerance_multiple_of_k: float = Field(gt=0)
    rbo_p: Literal["1 - 1/k"]
    source: str = Field(min_length=1)


class H2Rule(BaseModel):
    """The pre-registered decision rule of H2 (M-F7-07, OQ-050): `O` is the Capacity Overlap Index of the cell selection and the regional one.

    H2 is not testable when `O_ref = T / Q_max` is at least `gamma`, supported when `O < gamma` and not supported when `O >= gamma`. The
    partition, the regional ranking statistic and the target are named so that no other form is read by accident. `source` is the citation
    of the pre-registration.
    """

    model_config = ConfigDict(extra="forbid")

    gamma: float = Field(gt=0, le=1)
    partition: Literal["admin1"]
    region_statistic: Literal["capacity_weighted_mean"]
    target: Literal["top_k_capacity"]
    source: str = Field(min_length=1)


class H3Rule(BaseModel):
    """The pre-registered decision rule of H3 (M-F7-07, OQ-050): `D` is the share of the robust capacity outside the reach of the nominal plan.

    H3 is not testable when `D_ref = 1 - (k + m) / |I|` is below `delta`, supported when `D >= delta` and not supported when `D < delta`, with
    the tolerance `m = tolerance_multiple_of_k * k`. The domain of both rankings and the weight are named so that no other form is read by
    accident. `source` is the citation of the pre-registration.
    """

    model_config = ConfigDict(extra="forbid")

    delta: float = Field(gt=0, le=1)
    tolerance_multiple_of_k: float = Field(gt=0)
    domain: Literal["I"]
    weight: Literal["capacity"]
    source: str = Field(min_length=1)


class H4Rule(BaseModel):
    """The pre-registered decision rule of H4 (M-F7-07, OQ-050): the dominance ratio `rho = D_clim / (D_clim + D_tec)` and its profile.

    A country and technology is Climate-Dominated when `rho > upper`, Techno-Economic-Dominated when `rho < lower`, Mixed when
    `lower <= rho <= upper` and has No Displacement when `D_clim + D_tec = 0`. The verdict of a technology is `strict_per_technology`: supported
    only if one country is Climate-Dominated and another Techno-Economic-Dominated. `source` is the citation of the pre-registration.
    """

    model_config = ConfigDict(extra="forbid")

    lower: float = Field(gt=0, lt=1)
    upper: float = Field(gt=0, lt=1)
    rule: Literal["strict_per_technology"]
    tolerance_multiple_of_k: float = Field(gt=0)
    source: str = Field(min_length=1)

    @model_validator(mode="after")
    def _lower_is_below_upper(self) -> H4Rule:
        if not self.lower < self.upper:
            raise ValueError(f"H4 lower {self.lower} must be below upper {self.upper}")
        return self


class H5Rule(BaseModel):
    """The pre-registered decision rule of H5 (M-F7-07, OQ-050): the pressure of climate change on the margin of the economic potential over the target.

    H5a (resource) holds when `R_loss >= lambda` and H5b (exposure) when `R_exp >= lambda`, with `lambda` in the YAML key `lambda`.
    `sensitivity_lambda` is the second materiality threshold that is reported beside the primary one. `domain` (the economic domain is
    fixed at `f0`), `members` (the core window) and `hazard_members` (the members that carry the hazard channel) are named so that no other
    form is read by accident. `source` is the citation of the pre-registration.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    lambda_: float = Field(alias="lambda", gt=0, le=1)
    sensitivity_lambda: float = Field(gt=0, le=1)
    domain: Literal["fixed_at_f0"]
    members: Literal["core_window"]
    hazard_members: Literal["hazard_channel"]
    source: str = Field(min_length=1)


class TargetValue(BaseModel):
    """One national target of a technology: a value, its unit, its source and the year it refers to (OQ-010)."""

    model_config = ConfigDict(extra="forbid")

    value: float | None = Field(ge=0)
    unit: Literal["GW", "TWh/year"] | None
    source: str | None
    horizon: int | None = Field(ge=1900, le=2200)

    @model_validator(mode="after")
    def _a_value_has_unit_source_and_horizon(self) -> TargetValue:
        if self.value is not None and (not self.unit or not self.source or self.horizon is None):
            raise ValueError("a national target value needs its unit, source and horizon (OQ-010)")
        return self


class NationalTarget(TargetValue):
    """The national target of one country and technology for H5, and the alternative official targets or horizons for the sensitivity."""

    alternatives: list[TargetValue] = Field(default_factory=list)


class HazardThreshold(BaseModel):
    """The exposure threshold of one hazard indicator (T-R10, OQ-051); `threshold` is null until the author sources it."""

    model_config = ConfigDict(extra="forbid")

    threshold: float | None
    unit: str
    source: str | None
    tier: int | None


class PrimConfig(BaseModel):
    """PRIM peeling settings (M-F7-08, D-F7-023); null until the author records them with their source."""

    model_config = ConfigDict(extra="forbid")

    peel_alpha: float | None = Field(gt=0, lt=1)
    mass_min: float | None = Field(gt=0, lt=1)
    source: str | None


class ExternalValidationConfig(BaseModel):
    """F7b settings (M-F7b-01 to M-F7b-03, D-F7b-004)."""

    model_config = ConfigDict(extra="forbid")

    enrichment_lowest_deciles: list[int]
    vintage_min_start_year: int | None
    vintage_reason: str | None
    excluded_location_accuracy: list[str] | None

    @model_validator(mode="after")
    def _deciles_and_reasons(self) -> ExternalValidationConfig:
        if not self.enrichment_lowest_deciles or any(
            d < 1 or d > 10 for d in self.enrichment_lowest_deciles
        ):
            raise ValueError(
                "enrichment_lowest_deciles must be a non-empty list of integers in 1..10"
            )
        if self.vintage_min_start_year is not None and not self.vintage_reason:
            raise ValueError("vintage_min_start_year needs vintage_reason")
        return self


class ExperimentsFile(BaseModel):
    """Root of `experiments.yaml`."""

    model_config = ConfigDict(extra="forbid")

    members: dict[str, Any]
    gcm_ensemble: dict[str, Any]
    windows: dict[str, Any]
    uncertain_parameters: dict[str, UncertainParameterSpec]
    sampler: SamplerConfig
    land_availability: LandAvailability
    thresholds: dict[str, Any]
    hypothesis_rules: dict[
        str, list[HypothesisRule] | H1Rule | H2Rule | H3Rule | H4Rule | H5Rule | None
    ]
    national_targets: dict[str, dict[str, NationalTarget]] = Field(default_factory=dict)
    hazard_thresholds: dict[str, HazardThreshold]
    prim: PrimConfig
    external_validation: ExternalValidationConfig

    @model_validator(mode="after")
    def _h1_to_h5_have_their_own_form(self) -> ExperimentsFile:
        """H1 to H5 are pre-registered `H1Rule` to `H5Rule` (or null); the other hypotheses are lists of rules (or null)."""
        own = {"H1": H1Rule, "H2": H2Rule, "H3": H3Rule, "H4": H4Rule, "H5": H5Rule}
        owner = {form: name for name, form in own.items()}
        for name, rule in self.hypothesis_rules.items():
            form = own.get(name)
            if form is not None and rule is not None and not isinstance(rule, form):
                raise ValueError(
                    f"hypothesis_rules.{name} is a {form.__name__} mapping, not a list or another form"
                )
            if form is None and isinstance(rule, H1Rule | H2Rule | H3Rule | H4Rule | H5Rule):
                raise ValueError(
                    f"hypothesis_rules.{name}: the {type(rule).__name__} form belongs to {owner[type(rule)]}"
                )
        return self
