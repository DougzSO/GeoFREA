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
    hypothesis_rules: dict[str, list[HypothesisRule] | None]
    hazard_thresholds: dict[str, HazardThreshold]
    prim: PrimConfig
    external_validation: ExternalValidationConfig
