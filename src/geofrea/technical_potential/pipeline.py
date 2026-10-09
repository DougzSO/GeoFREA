"""F5 technical_potential end to end for one country: capacity, capacity factor and energy per cell, member and land scenario.

Reads, per technology and land scenario, `candidates_<tech>__<scenario>.parquet` (F3), and `forcing.parquet`,
`forcing_masked.parquet` and `members.yaml` (F4); writes under `outputs/<ISO3>/technical_potential/artifacts/`:

  - `potential_<tech>__<scenario>.parquet`: `cell_id`, `member`, `P_MW`, `CF`, `E_MWh` (M-F5-06); a cell-member declared
    masked (M-F4-07) has no row;
  - `potential_aggregates_<tech>.parquet`: one row per scenario and member, all-present and like-for-like series (D-F5-006).

Nothing is computed before every input is checked: the parameters, curves and registry rules the technologies need (a missing
one raises `MissingParameterError` listing all of them), and for each scenario the forcing contract
(`assert_forcing_usable`, M-F4-07). See docs/phases/F5_technical_potential.md D-F5-001 to D-F5-016.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict

from geofrea.climate_forcing.forcing import assert_forcing_usable
from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID, load_ensemble
from geofrea.core import paths as core_paths
from geofrea.core.config_schemas import TechnologiesFile, TechnologyConfig
from geofrea.core.constants import HOURS_PER_DAY, HOURS_PER_YEAR, RHO0_KG_M3
from geofrea.core.schemas import CountryParams
from geofrea.core.tables import write_table
from geofrea.data_quality_audit.schemas import AuditConfig
from geofrea.land_eligibility.scenarios import LAND_SCENARIOS
from geofrea.siting_layers.sanity import CountryGeometry, load_country_geometry
from geofrea.technical_potential.aggregates import aggregate_scenario
from geofrea.technical_potential.capacity import annual_energy_mwh, capacity_mw
from geofrea.technical_potential.cf_models import (
    CfModel,
    CfModelError,
    CfSettings,
    MissingParameterError,
    get_cf_model,
)
from geofrea.technical_potential.input_ranges import (
    DISTANCE_COLUMNS,
    InputRange,
    resolve_input_ranges,
    validate_candidates,
    warn_unranged,
)
from geofrea.technical_potential.power_curve import (
    PowerCurve,
    PowerCurveError,
    assert_curve_usable,
    curve_file_sha256,
    load_power_curve,
)
from geofrea.technical_potential.table_schemas import (
    POTENTIAL_TABLE_SCHEMA_VERSION,
    PotentialAggregateRow,
    PotentialRow,
)

logger = logging.getLogger("geofrea.technical_potential.pipeline")

INTEGRATION_METHOD = "exact_piecewise_linear_regularized_incomplete_gamma"  # D-F5-001
PROVENANCE_KEY = "geofrea_potential_provenance"
# parameters every technology needs (M-F5-01), on top of the ones its CF model reads
CAPACITY_PARAMETER_KEYS = ("luf", "power_density_mw_per_km2")


class ScenarioPotential(BaseModel):
    """One land scenario of one technology: its table and totals of the reference member."""

    model_config = ConfigDict(extra="forbid")

    scenario: str
    path: Path
    n_rows: int
    n_candidate_cells: int
    n_absent_cell_members: int
    p_gw_reference: float
    e_twh_reference: float


class TechPotential(BaseModel):
    model_config = ConfigDict(extra="forbid")

    technology: str
    cf_model: str
    parameters: dict[str, float]
    curve_sha256: dict[str, str]
    scenarios: dict[str, ScenarioPotential]
    aggregates: Path


class PotentialSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    technologies: dict[str, TechPotential]


@dataclass(frozen=True)
class ResolvedTechnology:
    """A technology whose parameters, curves and rules were all found: ready to compute."""

    technology: str
    cf_model_name: str
    model: CfModel
    settings: CfSettings
    parameters: Mapping[str, float]
    curve_sha256: Mapping[str, str]


def potential_dir(iso: str) -> Path:
    path = core_paths.phase_dir(iso, "technical_potential", "artifacts")
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_technology(
    iso: str,
    technology: str,
    tech_cfg: TechnologyConfig,
    tech_params: object,
    curves_dir: Path,
    production: bool,
) -> ResolvedTechnology:
    """Check every input of a technology and gather them; raise `MissingParameterError` listing what is absent.

    Implements: M-F5-01, M-F5-02, M-F5-03.

    Args:
        iso: Country code.
        technology: Technology key of the registry.
        tech_cfg: Its registry entry.
        tech_params: Its parameters in `parameters.json` for the country (attributes are `VerifiedValue`).
        curves_dir: Directory of the power-curve files.
        production: A production run refuses a synthetic curve.

    Raises:
        MissingParameterError: a required parameter has no value, or the curves or the class rule are absent.
        CfModelError: the registry is inconsistent (unknown model, a parameter the model reads is not declared required).
        PowerCurveError: a curve file is invalid, or its class differs from the registry mapping.
    """
    model = get_cf_model(tech_cfg.cf_model)
    needed = (*CAPACITY_PARAMETER_KEYS, *model.parameter_keys)
    undeclared = [k for k in needed if k not in tech_cfg.required_parameters]
    if undeclared:
        raise CfModelError(
            f"registry entry {technology!r}: model {tech_cfg.cf_model!r} reads {undeclared}, "
            "which are not in required_parameters"
        )
    missing: list[str] = []
    values: dict[str, float] = {}
    for key in dict.fromkeys(tech_cfg.required_parameters):
        entry = getattr(tech_params, key, None)
        if entry is None:
            missing.append(f"{key} (no entry in parameters.json)")
        elif entry.value is None:
            missing.append(f"{key} ({entry.status or 'no value'})")
        else:
            values[key] = float(entry.value)

    curves: dict[str, PowerCurve] = {}
    hashes: dict[str, str] = {}
    if model.needs_curves:
        if tech_cfg.power_curves is None:
            missing.append(
                "power curve (technologies.yaml power_curves maps no IEC class to a curve)"
            )
        if tech_cfg.iec_class_rule is None:
            missing.append("iec_class_rule (technologies.yaml)")
        if tech_cfg.power_curves is not None and tech_cfg.iec_class_rule is not None:
            for iec_class, curve_id in tech_cfg.power_curves.items():
                path = Path(curves_dir) / f"{curve_id}.yaml"
                if not path.is_file():
                    missing.append(f"power curve file {path.name} for IEC class {iec_class}")
                    continue
                curve = load_power_curve(path)
                if curve.iec_class != iec_class:
                    raise PowerCurveError(
                        f"{path.name}: iec_class {curve.iec_class!r} differs from the registry class {iec_class!r}"
                    )
                assert_curve_usable(curve, production)
                curves[iec_class] = curve
                hashes[curve_id] = curve_file_sha256(path)
    if missing:
        raise MissingParameterError(iso, technology, missing)
    return ResolvedTechnology(
        technology=technology,
        cf_model_name=tech_cfg.cf_model,
        model=model,
        settings=CfSettings(
            parameters=values,
            curves=curves,
            iec_class_rule=tech_cfg.iec_class_rule,
            resource_layers=tuple(tech_cfg.resource_layers),
            rho0=RHO0_KG_M3,
            hours_per_day=HOURS_PER_DAY,
        ),
        parameters=values,
        curve_sha256=hashes,
    )


def _check_cf(cf: np.ndarray, member: str, cell_ids: np.ndarray) -> None:
    bad = ~np.isfinite(cf) | (cf < 0.0) | (cf > 1.0)
    if bad.any():
        raise CfModelError(
            f"{int(bad.sum())} capacity factors outside [0, 1] or not finite in member {member} "
            f"(e.g. cell {int(cell_ids[bad][0])}: {cf[bad][0]}); V-03"
        )


def _provenance(
    resolved: ResolvedTechnology,
    scenario: str,
    absent_by_member: Mapping[str, int],
    production: bool,
) -> dict[str, str]:
    payload = {
        "technology": resolved.technology,
        "scenario": scenario,
        "cf_model": resolved.cf_model_name,
        "parameters": dict(resolved.parameters),
        "curve_sha256": dict(resolved.curve_sha256),
        "rho0_kg_m3": RHO0_KG_M3,
        "hours_per_year": HOURS_PER_YEAR,
        "integration": INTEGRATION_METHOD,
        "c2_applied": False,
        "production": production,
        "absent_cell_members": {m: n for m, n in absent_by_member.items() if n},
    }
    return {PROVENANCE_KEY: json.dumps(payload, sort_keys=True)}


def build_technology_potential(
    iso: str,
    resolved: ResolvedTechnology,
    *,
    candidates_paths: Mapping[str, Path],
    forcing_path: Path,
    forcing_masked_path: Path,
    members: Sequence[str],
    wind_valid_range: tuple[float, float],
    out_dir: Path,
    input_ranges: Mapping[str, InputRange],
    production: bool = False,
) -> TechPotential:
    """Tables and aggregates of one technology for the given land scenarios.

    Implements: M-F5-01 to M-F5-06, M-F4-07.

    Raises:
        InputRangeError: a resource or distance value of a candidate cell is outside its sanity range (V-04); raised before any output.
        ForcingContractError: a candidate cell-member is neither in the forcing nor declared masked, or a factor is out of range.
        CfModelError: a capacity factor outside [0, 1], or a forcing member not listed in `members.yaml`.
    """
    tech = resolved.technology
    if REFERENCE_MEMBER_ID not in members:
        raise CfModelError(f"the member list has no reference member {REFERENCE_MEMBER_ID!r}")
    forcing = pd.read_parquet(forcing_path)
    forcing["member"] = forcing["member"].astype(str)
    masked = pd.read_parquet(forcing_masked_path)
    unknown = sorted(set(forcing["member"]) - set(members))
    if unknown:
        raise CfModelError(f"forcing.parquet has members not listed in members.yaml: {unknown}")

    candidates: dict[str, pd.DataFrame] = {}
    warn_unranged(iso, tech, input_ranges)
    for scenario, path in candidates_paths.items():
        frame = pd.read_parquet(path).sort_values("cell_id", ignore_index=True)
        if frame["cell_id"].duplicated().any():
            raise CfModelError(f"{path.name}: duplicated cell_id")
        validate_candidates(iso, tech, scenario, frame, input_ranges)
        # the forcing guard comes first: nothing is computed on a forcing that breaks the contract (M-F4-07)
        assert_forcing_usable(
            forcing, masked, frame["cell_id"].to_numpy(), list(members), wind_valid_range
        )
        candidates[scenario] = frame

    by_member: dict[str, pd.DataFrame] = {}
    for member, group in forcing.groupby("member", sort=False):
        if group["cell_id"].duplicated().any():
            raise CfModelError(f"forcing.parquet: duplicated cell_id in member {member}")
        by_member[str(member)] = group.set_index("cell_id")

    luf = resolved.parameters["luf"]
    power_density = resolved.parameters["power_density_mw_per_km2"]
    scenario_results: dict[str, ScenarioPotential] = {}
    aggregate_frames: list[pd.DataFrame] = []
    for scenario, frame in candidates.items():
        cell_ids = frame["cell_id"].to_numpy()
        area = frame["eligible_area_km2"].to_numpy(dtype="float64")
        p_mw = capacity_mw(area, luf, power_density)
        prepared = resolved.model.prepare(frame, resolved.settings)
        energy_by_member: dict[str, np.ndarray] = {}
        absent_by_member: dict[str, int] = {}
        pieces: list[pd.DataFrame] = []
        for member in members:
            energy = np.full(len(frame), np.nan)
            factors = by_member.get(member)
            if factors is None:
                position = np.full(len(frame), -1)
            else:
                position = factors.index.get_indexer(cell_ids)
            rows = np.flatnonzero(position >= 0)
            if len(rows):
                taken = factors.iloc[position[rows]]
                cf = prepared.member(
                    rows,
                    taken["delta_rsds"].to_numpy(dtype="float64"),
                    taken["dT"].to_numpy(dtype="float64"),
                    taken["delta_wind"].to_numpy(dtype="float64"),
                )
                _check_cf(cf, member, cell_ids[rows])
                e_mwh = annual_energy_mwh(p_mw[rows], cf, HOURS_PER_YEAR)
                energy[rows] = e_mwh
                pieces.append(
                    pd.DataFrame(
                        {
                            "cell_id": cell_ids[rows].astype("int64"),
                            "member": pd.Categorical(
                                [member] * len(rows), categories=list(members)
                            ),
                            "P_MW": p_mw[rows],
                            "CF": cf,
                            "E_MWh": e_mwh,
                        }
                    )
                )
            energy_by_member[member] = energy
            absent_by_member[member] = int(len(frame) - len(rows))
        if pieces:
            table = pd.concat(pieces, ignore_index=True)
        else:  # a scenario without candidate cells has no rows: zero potential, written as an empty table
            logger.warning(
                "%s %s [%s]: no candidate cells, the potential is zero", iso, tech, scenario
            )
            table = pd.DataFrame(
                {
                    "cell_id": pd.Series(dtype="int64"),
                    "member": pd.Categorical([], categories=list(members)),
                    "P_MW": pd.Series(dtype="float64"),
                    "CF": pd.Series(dtype="float64"),
                    "E_MWh": pd.Series(dtype="float64"),
                }
            )
        path = Path(out_dir) / f"potential_{tech}__{scenario}.parquet"
        write_table(
            table,
            path,
            schema_version=POTENTIAL_TABLE_SCHEMA_VERSION,
            row_model=PotentialRow,
            compression="zstd",
            extra_metadata=_provenance(resolved, scenario, absent_by_member, production),
        )
        aggregate = aggregate_scenario(
            scenario,
            list(members),
            p_mw,
            area,
            energy_by_member,
            REFERENCE_MEMBER_ID,
            HOURS_PER_YEAR,
        )
        aggregate_frames.append(aggregate)
        ref = aggregate[aggregate["member"] == REFERENCE_MEMBER_ID].iloc[0]
        scenario_results[scenario] = ScenarioPotential(
            scenario=scenario,
            path=path,
            n_rows=len(table),
            n_candidate_cells=len(frame),
            n_absent_cell_members=int(sum(absent_by_member.values())),
            p_gw_reference=float(ref["P_GW"]),
            e_twh_reference=float(ref["E_TWh"]),
        )
        logger.info(
            "%s %s [%s]: %d cells x %d members, %d rows, %d absent cell-members, %.3f GW and %.3f TWh at m0",
            iso,
            tech,
            scenario,
            len(frame),
            len(members),
            len(table),
            sum(absent_by_member.values()),
            ref["P_GW"],
            ref["E_TWh"],
        )
    aggregates_path = Path(out_dir) / f"potential_aggregates_{tech}.parquet"
    write_table(
        pd.concat(aggregate_frames, ignore_index=True),
        aggregates_path,
        schema_version=POTENTIAL_TABLE_SCHEMA_VERSION,
        row_model=PotentialAggregateRow,
    )
    return TechPotential(
        technology=tech,
        cf_model=resolved.cf_model_name,
        parameters=dict(resolved.parameters),
        curve_sha256=dict(resolved.curve_sha256),
        scenarios=scenario_results,
        aggregates=aggregates_path,
    )


def build_potential(
    iso: str,
    technologies: TechnologiesFile,
    country_params: CountryParams,
    run_technologies: Sequence[str],
    experiments_yaml: Path,
    curves_dir: Path,
    *,
    audit_config: AuditConfig,
    production: bool = False,
    geometry: CountryGeometry | None = None,
    candidates_dir: Path | None = None,
    climate_dir: Path | None = None,
    out_dir: Path | None = None,
) -> PotentialSummary:
    """F5 for `iso` and the technologies of the run, in the three land scenarios.

    Implements: M-F5-01 to M-F5-06.

    Raises:
        MissingParameterError: any technology lacks a parameter, curve or rule; raised before any input is read.
        InputRangeError: a candidate-cell input is outside its sanity range in `audit_config` (V-04), or a layer has no declared range.
        SanityError: the country geometry the derived ranges need cannot be read.
    """
    failures: list[str] = []
    resolved: dict[str, ResolvedTechnology] = {}
    for tech in run_technologies:
        try:
            resolved[tech] = resolve_technology(
                iso,
                tech,
                technologies.technologies[tech],
                getattr(country_params.technologies, tech),
                curves_dir,
                production,
            )
        except MissingParameterError as exc:
            failures.extend(f"{tech}: {item}" for item in exc.missing)
    if failures:
        raise MissingParameterError(iso, ", ".join(run_technologies), failures)

    ensemble = load_ensemble(experiments_yaml)
    if ensemble.wind_factor_valid_range is None:
        raise CfModelError("experiments.yaml has no wind_factor_valid_range (M-F4-07)")
    candidates_dir = candidates_dir or core_paths.phase_dir(iso, "land_eligibility", "artifacts")
    climate_dir = climate_dir or core_paths.phase_dir(iso, "climate_forcing", "artifacts")
    out_dir = out_dir or potential_dir(iso)
    members_file = Path(climate_dir) / "members.yaml"
    for needed in (
        members_file,
        Path(climate_dir) / "forcing.parquet",
        Path(climate_dir) / "forcing_masked.parquet",
    ):
        if not needed.is_file():
            raise FileNotFoundError(f"F5 input missing (F4 must have run): {needed}")
    members = [
        m["member"] for m in yaml.safe_load(members_file.read_text(encoding="utf-8"))["members"]
    ]

    geometry = geometry if geometry is not None else load_country_geometry(iso)
    result: dict[str, TechPotential] = {}
    for tech, res in resolved.items():
        ranges = resolve_input_ranges(
            iso,
            audit_config,
            geometry,
            [*technologies.technologies[tech].resource_layers, *DISTANCE_COLUMNS],
        )
        paths = {
            s: Path(candidates_dir) / f"candidates_{tech}__{s}.parquet" for s in LAND_SCENARIOS
        }
        absent = [p.name for p in paths.values() if not p.is_file()]
        if absent:
            raise FileNotFoundError(f"F5 input missing (F3 must have run): {absent}")
        result[tech] = build_technology_potential(
            iso,
            res,
            candidates_paths=paths,
            forcing_path=Path(climate_dir) / "forcing.parquet",
            forcing_masked_path=Path(climate_dir) / "forcing_masked.parquet",
            members=members,
            wind_valid_range=ensemble.wind_factor_valid_range,
            out_dir=Path(out_dir),
            input_ranges=ranges,
            production=production,
        )
    return PotentialSummary(country_code=iso, technologies=result)
