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


class TechnologyConfig(BaseModel):
    """One entry of `technologies.yaml`: resources, capacity-factor model, exclusions, cost drivers, uncertain-parameter keys."""

    model_config = ConfigDict(extra="forbid")

    resource_layers: list[str]
    cf_model: str
    exclusions: list[str]
    cost_drivers: list[str]
    uncertain_parameters: list[str]
    hub_heights: dict[str, float | None] | None = None  # wind only (OQ-005)
    iec_class_rule: str | None = None  # wind only (OQ-005)


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
