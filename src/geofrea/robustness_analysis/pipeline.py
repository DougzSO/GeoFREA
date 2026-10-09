"""F7 robustness_analysis end to end for one country: regret, satisficing, rankings, hypotheses and scenario discovery (M-F7-01 to M-F7-11).

Reads, per technology, the F5 potential tables, the F3 candidates (the central scenario), `forcing.parquet`, `members.yaml` (F4) and the
parameters of F6; computes the LCOE of every future with the pure F6 kernel (nothing sample-level is persisted, M-F7-10) and writes under
`outputs/<ISO3>/robustness_analysis/artifacts/`, per technology and window role (`core`, `sensitivity`):

  - `robustness_<tech>__<role>.parquet`: one row per candidate cell (M-F7-11, D-F7-025);
  - `nominal_lcoe_by_member_<tech>__<role>.parquet`: the nominal LCOE of the F7 set in `m0` and each member of the window.

Nothing is read before the F6 inputs and the feasibility rule are checked: `RobustnessMissingInputError` lists every missing item (A-09).
Any other decision parameter that is null skips the outputs that need it, each listed with the open question that blocks it (D-F7-023).
See docs/phases/F7_robustness_analysis.md D-F7-006 to D-F7-029.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict

from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID
from geofrea.core import paths as core_paths
from geofrea.core.config_schemas import ExperimentsFile, TechnologiesFile
from geofrea.core.run_logging import PeriodicProgress
from geofrea.core.schemas import CountryParams
from geofrea.core.tables import write_table
from geofrea.lcoe_modeling.design import build_design, samples_from_design
from geofrea.lcoe_modeling.inputs import (
    LcoeMissingInputError,
    ResolvedLcoe,
    cells_per_block,
    read_member_inputs,
    resolve_all,
)
from geofrea.lcoe_modeling.kernel import KERNEL_VERSION
from geofrea.robustness_analysis.assemble import (
    Rankings,
    classes_only_frame,
    compute_rankings,
    empty_nominal_frame,
    nominal_by_member_frame,
    robustness_frame,
)
from geofrea.robustness_analysis.cell_set import CellSet, build_cell_set
from geofrea.robustness_analysis.decision import (
    RobustnessMissingInputError,
    SkippedOutput,
    TechDecision,
    check_ranges,
    decision_values,
    refusals,
    regret_quantile,
    skipped_outputs,
)
from geofrea.robustness_analysis.evaluator import evaluate
from geofrea.robustness_analysis.table_schemas import (
    ROBUSTNESS_TABLE_SCHEMA_VERSION,
    NominalByMemberRow,
    RobustnessRow,
)

logger = logging.getLogger("geofrea.robustness_analysis.pipeline")

PROVENANCE_KEY = "geofrea_robustness_provenance"
WINDOW_ROLES = ("core", "sensitivity")


class RobustnessInputError(RuntimeError):
    """An input table of F7 breaks its contract (A-09)."""


class WindowResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    window: str
    n_candidates: int
    n_f7_set: int
    class_counts: dict[str, int]
    k: int | None
    top_k_truncated: bool
    target_unreachable: bool | None
    robustness: Path
    nominal_by_member: Path


class TechRobustness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    technology: str
    n_samples: int
    seed: int
    provisional: bool
    windows: dict[str, WindowResult]
    skipped: list[dict[str, str]]


class RobustnessSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    technologies: dict[str, TechRobustness]


@dataclass(frozen=True)
class MemberEntry:
    """A member of `members.yaml`: identifier, window and, for a climate member, GCM and SSP."""

    member: str
    window: str
    gcm: str | None
    ssp: str | None
    hazard: bool


def robustness_dir(iso: str) -> Path:
    path = core_paths.phase_dir(iso, "robustness_analysis", "artifacts")
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_member_entries(members_file: Path) -> list[MemberEntry]:
    """The members of `members.yaml`, in its order."""
    entries = yaml.safe_load(Path(members_file).read_text(encoding="utf-8"))["members"]
    return [
        MemberEntry(
            member=e["member"],
            window=str(e["window"]),
            gcm=e.get("gcm"),
            ssp=e.get("ssp"),
            hazard=bool(e.get("channels", {}).get("hazard", False)),
        )
        for e in entries
    ]


def window_name(experiments: ExperimentsFile, role: str) -> str:
    """`start-end` of the `core` or `sensitivity` window of `experiments.yaml`."""
    window = experiments.windows[role]
    return f"{window['start_year']}-{window['end_year']}"


def check_start(
    iso: str,
    technologies: TechnologiesFile,
    country_params: CountryParams,
    run_technologies: Sequence[str],
    experiments: ExperimentsFile,
) -> tuple[dict[str, ResolvedLcoe], dict[str, TechDecision]]:
    """Check everything F7 needs before any input is read; list all that is missing.

    Implements: A-09, D-F7-023.

    Raises:
        RobustnessConfigError: `q_ref` is not 0.
        RobustnessMissingInputError: an F6 parameter, range or price year, or `CF_min`, is missing, or a decision value is outside its domain.
    """
    regret_quantile(experiments)
    failures: list[str] = []
    try:
        resolved = resolve_all(iso, technologies, country_params, run_technologies)
    except LcoeMissingInputError as exc:
        resolved = {}
        failures.extend(exc.missing)
    decisions: dict[str, TechDecision] = {}
    for tech in run_technologies:
        params = getattr(country_params.technologies, tech)
        failures.extend(f"{tech}: {item}" for item in refusals(params))
        decision = decision_values(params, tech)
        failures.extend(f"{tech}: {item}" for item in check_ranges(decision))
        decisions[tech] = decision
    if failures:
        raise RobustnessMissingInputError(iso, ", ".join(run_technologies), failures)
    return resolved, decisions


def _read_candidates(path: Path) -> pd.DataFrame:
    """The candidates of the central scenario: identifier, centre, admin1 unit, sorted by `cell_id`."""
    table = pd.read_parquet(
        path, columns=["cell_id", "lat_c", "lon_c", "admin1_id", "cell_area_km2"]
    ).sort_values("cell_id")
    if table["cell_id"].duplicated().any():
        raise RobustnessInputError(f"{Path(path).name}: duplicated cell_id")
    return table.reset_index(drop=True)


def _skipped_dicts(skipped: Sequence[SkippedOutput]) -> list[dict[str, str]]:
    return [
        {"output": s.output, "reason": s.reason, "open_question": s.open_question} for s in skipped
    ]


def _provenance(
    resolved: ResolvedLcoe,
    decision: TechDecision,
    experiments: ExperimentsFile,
    *,
    role: str,
    window: str,
    n_samples: int,
    seed: int,
    n_members: int,
    cell_set: CellSet,
    ranking: Rankings | None,
    skipped: Sequence[SkippedOutput],
    scale_id: str,
    production: bool,
) -> dict[str, str]:
    payload = {
        "technology": resolved.technology,
        "window_role": role,
        "window": window,
        "scale": scale_id,
        "n_samples": n_samples,
        "seed": seed,
        "n_core_members": n_members,
        "kernel_version": KERNEL_VERSION,
        "nominal_parameters": dict(resolved.nominal),
        "uncertain_parameters": [s.name for s in resolved.specs],
        "decision": {
            "cf_min": decision.cf_min,
            "tau_lcoe_usd_per_mwh": decision.tau,
            "capacity_target_gw": decision.capacity_target_gw,
            "top_k_percent": decision.top_k_percent,
            "prim_outcome_share": decision.prim_outcome_share,
            "q_ref": regret_quantile(experiments),
        },
        "feasibility": "CF(m, s0) stored by F5 against cf_min, handed to the kernel as an energy floor (D-F7-007)",
        "statistics_over": "draws s >= 1 of the core members; the nominal vector s0 is f0 and the central value",
        "class_counts": cell_set.counts(),
        "k": None if ranking is None else ranking.k,
        "top_k_truncated": False if ranking is None else ranking.top_k_truncated,
        "target_unreachable": None
        if ranking is None or ranking.target_reached is None
        else not ranking.target_reached,
        "empty_f7_set": ranking is None,
        "skipped_outputs": _skipped_dicts(skipped),
        "provisional": False,
        "production": production,
    }
    return {PROVENANCE_KEY: json.dumps(payload, sort_keys=True)}


def run_window(
    iso: str,
    role: str,
    window: str,
    resolved: ResolvedLcoe,
    decision: TechDecision,
    experiments: ExperimentsFile,
    entries: Sequence[MemberEntry],
    skipped: Sequence[SkippedOutput],
    *,
    potential_path: Path,
    candidates_path: Path,
    forcing_path: Path,
    out_dir: Path,
    n_samples: int,
    seed: int,
    max_batch_gb: float,
    scale_id: str,
    production: bool,
) -> WindowResult:
    """One window of one technology: the F7 set, the evaluation, the rankings and the per-cell tables.

    Implements: M-F7-01 to M-F7-06, M-F7-10, M-F7-11.

    An empty F7 set is not an error: the classes are written, every result column is null and a warning says so.

    Raises:
        RobustnessInputError: the window has no member.
        EvaluationError: a future has no feasible cell.
    """
    tech = resolved.technology
    member_ids = [
        e.member for e in entries if e.window == window and e.member != REFERENCE_MEMBER_ID
    ]
    if not member_ids:
        raise RobustnessInputError(f"members.yaml has no member of the {role} window {window}")
    assert decision.cf_min is not None  # refused before any input is read otherwise
    design = build_design(resolved.specs, n_samples, seed)
    samples = samples_from_design(design, resolved.nominal, resolved.energy_key)
    x = samples.energy_parameter
    data = {
        item.member: item
        for item in read_member_inputs(
            resolved,
            potential_path=potential_path,
            candidates_path=candidates_path,
            forcing_path=forcing_path,
            members=[REFERENCE_MEMBER_ID, *member_ids],
            x_range=(float(x.min()), float(x.max())),
            known_members=[e.member for e in entries],
        )
    }
    candidates = _read_candidates(candidates_path)
    cell_set = build_cell_set(
        candidates["cell_id"].to_numpy(), data, REFERENCE_MEMBER_ID, member_ids, decision.cf_min
    )
    logger.info("%s %s [%s]: %s", iso, tech, role, cell_set.counts())
    if cell_set.n_f7 == 0:
        logger.warning(
            "%s %s [%s]: the F7 set is empty (no candidate is present in m0 and in every member of the window and feasible at f0); only the classes are written",
            iso,
            tech,
            role,
        )
        return _write_window(
            tech,
            role,
            window,
            cell_set,
            None,
            classes_only_frame(cell_set, candidates),
            empty_nominal_frame(),
            _provenance(
                resolved,
                decision,
                experiments,
                role=role,
                window=window,
                n_samples=n_samples,
                seed=seed,
                n_members=len(member_ids),
                cell_set=cell_set,
                ranking=None,
                skipped=skipped,
                scale_id=scale_id,
                production=production,
            ),
            out_dir,
        )
    progress = PeriodicProgress(
        logger, len(member_ids) + 1, f"{iso} {tech} {role} members", every=5
    )
    evaluation = evaluate(
        cell_set.reference,
        cell_set.core,
        samples,
        tau=decision.tau,
        block_cells=cells_per_block(max_batch_gb, n_samples),
        progress=progress.step,
    )
    ranking = compute_rankings(cell_set, evaluation, decision)
    provenance = _provenance(
        resolved,
        decision,
        experiments,
        role=role,
        window=window,
        n_samples=n_samples,
        seed=seed,
        n_members=len(member_ids),
        cell_set=cell_set,
        ranking=ranking,
        skipped=skipped,
        scale_id=scale_id,
        production=production,
    )
    return _write_window(
        tech,
        role,
        window,
        cell_set,
        ranking,
        robustness_frame(cell_set, evaluation, ranking, candidates),
        nominal_by_member_frame(cell_set, evaluation),
        provenance,
        out_dir,
    )


def _write_window(
    tech: str,
    role: str,
    window: str,
    cell_set: CellSet,
    ranking: Rankings | None,
    robustness: pd.DataFrame,
    nominal: pd.DataFrame,
    provenance: dict[str, str],
    out_dir: Path,
) -> WindowResult:
    """Write the two per-window tables and describe them."""
    robustness_path = write_table(
        robustness,
        out_dir / f"robustness_{tech}__{role}.parquet",
        schema_version=ROBUSTNESS_TABLE_SCHEMA_VERSION,
        row_model=RobustnessRow,
        compression="zstd",
        extra_metadata=provenance,
    )
    nominal_path = write_table(
        nominal,
        out_dir / f"nominal_lcoe_by_member_{tech}__{role}.parquet",
        schema_version=ROBUSTNESS_TABLE_SCHEMA_VERSION,
        row_model=NominalByMemberRow,
        compression="zstd",
        extra_metadata=provenance,
    )
    return WindowResult(
        role=role,
        window=window,
        n_candidates=int(cell_set.candidate_ids.size),
        n_f7_set=cell_set.n_f7,
        class_counts=cell_set.counts(),
        k=None if ranking is None else ranking.k,
        top_k_truncated=False if ranking is None else ranking.top_k_truncated,
        target_unreachable=None
        if ranking is None or ranking.target_reached is None
        else not ranking.target_reached,
        robustness=robustness_path,
        nominal_by_member=nominal_path,
    )


def build_robustness(
    iso: str,
    technologies: TechnologiesFile,
    country_params: CountryParams,
    run_technologies: Sequence[str],
    experiments: ExperimentsFile,
    *,
    max_batch_gb: float,
    scale_id: str,
    production: bool = False,
    potential_dir: Path | None = None,
    candidates_dir: Path | None = None,
    climate_dir: Path | None = None,
    out_dir: Path | None = None,
) -> RobustnessSummary:
    """F7 for `iso` and the technologies of the run, on the central land scenario, the core window and the sensitivity window.

    Implements: M-F7-01 to M-F7-11.

    Raises:
        RobustnessConfigError: `q_ref` is not 0 (OQ-020).
        RobustnessMissingInputError: an F6 parameter or `CF_min` is missing; raised before any input is read.
        FileNotFoundError: an F3, F4 or F5 input is absent.
    """
    resolved, decisions = check_start(
        iso, technologies, country_params, run_technologies, experiments
    )
    potential_dir = Path(
        potential_dir or core_paths.phase_dir(iso, "technical_potential", "artifacts")
    )
    candidates_dir = Path(
        candidates_dir or core_paths.phase_dir(iso, "land_eligibility", "artifacts")
    )
    climate_dir = Path(climate_dir or core_paths.phase_dir(iso, "climate_forcing", "artifacts"))
    out_dir = Path(out_dir or robustness_dir(iso))
    members_file = climate_dir / "members.yaml"
    forcing_path = climate_dir / "forcing.parquet"
    needed = [members_file, forcing_path]
    for tech in resolved:
        needed.append(potential_dir / f"potential_{tech}__central.parquet")
        needed.append(candidates_dir / f"candidates_{tech}__central.parquet")
    absent = [str(p) for p in needed if not p.is_file()]
    if absent:
        raise FileNotFoundError(f"F7 input missing (F3, F4 and F5 must have run): {absent}")
    entries = read_member_entries(members_file)
    has_hazard = any(e.hazard for e in entries)
    result: dict[str, TechRobustness] = {}
    for tech, res in resolved.items():
        decision = decisions[tech]
        skipped = skipped_outputs(decision, experiments, has_hazard_members=has_hazard)
        for item in skipped:
            logger.warning(
                "%s %s: skipped %s (%s; %s)",
                iso,
                tech,
                item.output,
                item.reason,
                item.open_question,
            )
        windows = {
            role: run_window(
                iso,
                role,
                window_name(experiments, role),
                res,
                decision,
                experiments,
                entries,
                skipped,
                potential_path=potential_dir / f"potential_{tech}__central.parquet",
                candidates_path=candidates_dir / f"candidates_{tech}__central.parquet",
                forcing_path=forcing_path,
                out_dir=out_dir,
                n_samples=experiments.sampler.initial_size,
                seed=experiments.sampler.seed,
                max_batch_gb=max_batch_gb,
                scale_id=scale_id,
                production=production,
            )
            for role in WINDOW_ROLES
        }
        result[tech] = TechRobustness(
            technology=tech,
            n_samples=experiments.sampler.initial_size,
            seed=experiments.sampler.seed,
            provisional=False,
            windows=windows,
            skipped=_skipped_dicts(skipped),
        )
    return RobustnessSummary(country_code=iso, technologies=result)
