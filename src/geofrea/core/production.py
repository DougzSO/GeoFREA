"""Consistency of the parameter contract across `parameters.json`, `technologies.yaml` and `experiments.yaml` (U-05, V6).

`audit_parameters` lists what a run would consume and what is wrong with it. In development the findings are warnings, so the
research still open (MS-6) does not block work; in a production run (`python main.py --production`) the errors stop the run before
any phase starts (A-09):

- an uncertain parameter (U-03, listed per technology in `technologies.yaml`) has no entry, no value or no range in `parameters.json`
  for a country and technology being run (U-05);
- a required parameter (`required_parameters` per technology in `technologies.yaml`: the F5 inputs that are not uncertain, such as
  `luf`, `power_density_mw_per_km2` and `hub_height_m`; D-F5-011) has no entry or no value;
- a consumed parameter has `proxy = true` (V6: a value of a different quantity or technology).

Tier 3 values and ranges (U-07) and `synthetic` values only ever produce warnings. No value or range is created here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from geofrea.core.config_schemas import ExperimentsFile, TechnologiesFile
from geofrea.core.schemas import ParametersFile, VerifiedValue


class ConfigConsistencyError(ValueError):
    """The configuration files contradict each other (A-04, A-09)."""


class ProductionRunError(RuntimeError):
    """A production run was requested but the parameter contract is not met (U-05, V6); lists every violation."""


@dataclass
class ParameterAudit:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_run_technologies(run_technologies: list[str], technologies: TechnologiesFile) -> None:
    """`run.technologies` must be keys of `technologies.yaml` (A-04).

    Raises:
        ConfigConsistencyError: a run technology is not declared in the registry.
    """
    unknown = [t for t in run_technologies if t not in technologies.technologies]
    if unknown:
        raise ConfigConsistencyError(
            f"run.technologies {unknown} are not declared in config/technologies.yaml (known: {sorted(technologies.technologies)})"
        )


def validate_registry(technologies: TechnologiesFile, experiments: ExperimentsFile) -> None:
    """Every uncertain-parameter key of a technology must be declared in `experiments.yaml` `uncertain_parameters` (U-03).

    Raises:
        ConfigConsistencyError: a technology lists a key that experiments.yaml does not declare.
    """
    declared = set(experiments.uncertain_parameters)
    for tech, cfg in technologies.technologies.items():
        undeclared = [k for k in cfg.uncertain_parameters if k not in declared]
        if undeclared:
            raise ConfigConsistencyError(
                f"technologies.yaml {tech}: uncertain parameters {undeclared} are not declared in experiments.yaml"
            )


def audit_parameters(
    parameters: ParametersFile,
    technologies: TechnologiesFile,
    countries: list[str],
    run_technologies: list[str],
) -> ParameterAudit:
    """Findings for the parameters consumed by a run of `countries` x `run_technologies`.

    Implements: U-05, V6, M-F5-01 (required parameters).
    """
    audit = ParameterAudit()
    for iso in countries:
        country = parameters.countries.get(iso)
        if country is None:
            audit.errors.append(f"{iso}: no entry in parameters.json")
            continue
        for tech in run_technologies:
            params = getattr(country.technologies, tech, None)
            if params is None:
                audit.errors.append(f"{iso} {tech}: no technology entry in parameters.json")
                continue
            fields: dict[str, VerifiedValue] = {
                k: v for k, v in params.__dict__.items() if isinstance(v, VerifiedValue)
            }
            for key, vv in fields.items():
                where = f"{iso} {tech} {key}"
                if vv.proxy:
                    audit.errors.append(
                        f"{where}: proxy value consumed (a different quantity or technology, V6)"
                    )
                if vv.tier == 3 and not vv.synthetic:
                    audit.warnings.append(f"{where}: Tier 3 value (U-07)")
                if vv.range is not None and vv.range.tier == 3:
                    audit.warnings.append(f"{where}: Tier 3 range (U-07)")
            for key in technologies.technologies[tech].uncertain_parameters:
                where = f"{iso} {tech} {key}"
                vv = fields.get(key)
                if vv is None:
                    audit.errors.append(
                        f"{where}: uncertain parameter has no entry in parameters.json"
                    )
                elif vv.value is None:
                    audit.errors.append(f"{where}: uncertain parameter has no value")
                elif vv.range is None:
                    audit.errors.append(f"{where}: uncertain parameter has no range (U-05)")
            for key in technologies.technologies[tech].required_parameters:
                where = f"{iso} {tech} {key}"
                vv = fields.get(key)
                if vv is None:
                    audit.errors.append(
                        f"{where}: required parameter has no entry in parameters.json"
                    )
                elif vv.value is None:
                    audit.errors.append(f"{where}: required parameter has no value")
    return audit


def enforce_production(audit: ParameterAudit) -> None:
    """Raise `ProductionRunError` listing every error of the audit.

    Raises:
        ProductionRunError: the audit has at least one error.
    """
    if audit.errors:
        listing = "\n  - ".join(audit.errors)
        raise ProductionRunError(
            f"production run refused: {len(audit.errors)} violation(s) of the parameter contract:\n  - {listing}"
        )
