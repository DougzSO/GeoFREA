"""F7 robustness_analysis end to end for one country: regret, satisficing, rankings, hypotheses and scenario discovery (M-F7-01 to M-F7-11).

Reads, per technology, the F5 potential tables, the F3 candidates (the central scenario), `forcing.parquet`, `hazard_context.parquet`, `members.yaml` (F4) and the
F5 and F6 tables; computes the LCOE of every future with the pure F6 kernel (nothing sample-level is persisted, M-F7-10) and writes under
`outputs/<ISO3>/robustness_analysis/artifacts/`, per technology and window role (`core`, `sensitivity`):

  - `robustness_<tech>__<role>.parquet`: one row per candidate cell (M-F7-11, D-F7-025);
  - `nominal_lcoe_by_member_<tech>__<role>.parquet`: the nominal LCOE of the F7 set in `m0` and each member of the window;
  - `futures_`, `draw_statistics_`, `hypothesis_`, `potential_below_tau_` and `hazard_exposure_<tech>__<role>.parquet`: the futures, the H1 to H5
    statistics with their pre-registered rule, T-R12 and T-R10. An output whose decision parameter is null is written empty and says why in
    its metadata (`geofrea_robustness_skipped`), because the DAG fixes the files.

Nothing is read before the F6 inputs and the feasibility rule are checked: `RobustnessMissingInputError` lists every missing item (A-09).
Any other decision parameter that is null skips the outputs that need it, each listed with the open question that blocks it (D-F7-023).
See docs/phases/F7_robustness_analysis.md D-F7-006 to D-F7-029.
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

from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID
from geofrea.core import paths as core_paths
from geofrea.core.config_schemas import ExperimentsFile, TechnologiesFile
from geofrea.core.run_logging import PeriodicProgress
from geofrea.core.schemas import CountryParams
from geofrea.core.tables import write_table
from geofrea.land_eligibility.scenarios import LAND_SCENARIOS
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
    draw_statistics_frame,
    empty_nominal_frame,
    futures_frame,
    hypothesis_frame,
    nominal_by_member_frame,
    prim_frame,
    prim_input,
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
    rules_for,
    skipped_outputs,
)
from geofrea.robustness_analysis.evaluator import evaluate
from geofrea.robustness_analysis.futures import MemberLabel, futures_pass
from geofrea.robustness_analysis.hypotheses import agreement, evaluate_rules, h1, h2, h3, h4, h5
from geofrea.robustness_analysis.prim import run_prim
from geofrea.robustness_analysis.table_schemas import (
    ROBUSTNESS_TABLE_SCHEMA_VERSION,
    DrawStatisticRow,
    ExposureRow,
    FutureRow,
    HypothesisRow,
    NominalByMemberRow,
    PotentialBelowTauRow,
    PrimBoxRow,
    RobustnessRow,
)
from geofrea.robustness_analysis.thesis_tables import (
    HazardMember,
    exposure_rows,
    potential_below_tau_draws,
    potential_below_tau_nominal,
)

logger = logging.getLogger("geofrea.robustness_analysis.pipeline")

CENTRAL_SCENARIO = LAND_SCENARIOS[0]

PROVENANCE_KEY = "geofrea_robustness_provenance"
SKIPPED_KEY = "geofrea_robustness_skipped"
WINDOW_ROLES = ("core", "sensitivity")
ROW_MODELS: dict[str, type[BaseModel]] = {
    "robustness": RobustnessRow,
    "nominal_lcoe_by_member": NominalByMemberRow,
    "futures": FutureRow,
    "draw_statistics": DrawStatisticRow,
    "hypothesis": HypothesisRow,
    "potential_below_tau": PotentialBelowTauRow,
    "hazard_exposure": ExposureRow,
    "prim_boxes": PrimBoxRow,
}
WINDOW_TABLES = tuple(ROW_MODELS)  # the files written per technology and window role


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
    tables: dict[str, Path]


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


def member_factor_means(
    forcing_path: Path, cell_ids: np.ndarray, members: Sequence[str]
) -> pd.DataFrame:
    """The country-mean change factors of each member over the cells of the F7 set (descriptors of the futures, M-F7-08)."""
    forcing = pd.read_parquet(
        forcing_path,
        columns=["cell_id", "member", "delta_rsds", "dT", "delta_wind"],
        filters=[("member", "in", list(members))],
    )
    forcing = forcing[forcing["cell_id"].isin(cell_ids)]
    forcing = forcing.assign(member=forcing["member"].astype(str))
    means = forcing.groupby("member")[["delta_rsds", "dT", "delta_wind"]].mean()
    missing = sorted(set(members) - set(means.index))
    if missing:
        raise RobustnessInputError(f"forcing.parquet has no rows of the F7 set for {missing}")
    return means.astype("float64")


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


def _empty_frame(row_model: type[BaseModel]) -> pd.DataFrame:
    """A zero-row frame with the columns of `row_model`: the table of an output that was skipped."""
    return pd.DataFrame({name: pd.Series(dtype="object") for name in row_model.model_fields})


@dataclass(frozen=True)
class WindowPaths:
    """Where the inputs of one technology are."""

    potential_dir: Path
    candidates_dir: Path
    climate_dir: Path
    lcoe_dir: Path
    out_dir: Path


def _write_tables(
    tech: str,
    role: str,
    frames: Mapping[str, pd.DataFrame | None],
    skips: Mapping[str, SkippedOutput],
    provenance: dict[str, str],
    out_dir: Path,
) -> dict[str, Path]:
    """Write every table of the window; one that was skipped is written empty and says why in its metadata (the DAG fixes the files)."""
    paths: dict[str, Path] = {}
    for kind in WINDOW_TABLES:
        frame = frames.get(kind)
        meta = dict(provenance)
        if frame is None:
            skip = skips[kind]
            frame = _empty_frame(ROW_MODELS[kind])
            meta[SKIPPED_KEY] = json.dumps(
                {"output": skip.output, "reason": skip.reason, "open_question": skip.open_question}
            )
        paths[kind] = write_table(
            frame,
            out_dir / f"{kind}_{tech}__{role}.parquet",
            schema_version=ROBUSTNESS_TABLE_SCHEMA_VERSION,
            row_model=ROW_MODELS[kind],
            compression="zstd",
            extra_metadata=meta,
        )
    return paths


def _scenario_tables(
    scenario: str, tech: str, paths: WindowPaths
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The F5 rows and the F6 nominal LCOE of a land scenario."""
    potential = pd.read_parquet(
        paths.potential_dir / f"potential_{tech}__{scenario}.parquet",
        columns=["cell_id", "member", "P_MW", "CF", "E_MWh"],
    )
    if scenario == CENTRAL_SCENARIO:
        lcoe = pd.read_parquet(
            paths.lcoe_dir / f"lcoe_summary_{tech}.parquet",
            columns=["cell_id", "member", "lcoe_nominal"],
        )
    else:
        lcoe = pd.read_parquet(paths.lcoe_dir / f"lcoe_nominal_{tech}__{scenario}.parquet")
    return potential, lcoe


def run_window(
    iso: str,
    role: str,
    window: str,
    resolved: ResolvedLcoe,
    decision: TechDecision,
    experiments: ExperimentsFile,
    entries: Sequence[MemberEntry],
    skipped: Sequence[SkippedOutput],
    paths: WindowPaths,
    *,
    n_samples: int,
    seed: int,
    max_batch_gb: float,
    scale_id: str,
    production: bool,
) -> WindowResult:
    """One window of one technology: the F7 set, the evaluation, the rankings, the hypotheses and the tables.

    Implements: M-F7-01 to M-F7-07, M-F7-10, M-F7-11, T-R10, T-R12.

    An empty F7 set is not an error: the classes are written, every result column is null and a warning says so.

    Raises:
        RobustnessInputError: the window has no member.
        EvaluationError: a future has no feasible cell.
        HypothesisRuleError: a pre-registered rule names a statistic that is not written.
    """
    tech = resolved.technology
    member_ids = [
        e.member for e in entries if e.window == window and e.member != REFERENCE_MEMBER_ID
    ]
    if not member_ids:
        raise RobustnessInputError(f"members.yaml has no member of the {role} window {window}")
    assert decision.cf_min is not None  # refused before any input is read otherwise
    by_member = {e.member: e for e in entries}
    design = build_design(resolved.specs, n_samples, seed)
    samples = samples_from_design(design, resolved.nominal, resolved.energy_key)
    x = samples.energy_parameter
    data = {
        item.member: item
        for item in read_member_inputs(
            resolved,
            potential_path=paths.potential_dir / f"potential_{tech}__{CENTRAL_SCENARIO}.parquet",
            candidates_path=paths.candidates_dir / f"candidates_{tech}__{CENTRAL_SCENARIO}.parquet",
            forcing_path=paths.climate_dir / "forcing.parquet",
            members=[REFERENCE_MEMBER_ID, *member_ids],
            x_range=(float(x.min()), float(x.max())),
            known_members=[e.member for e in entries],
        )
    }
    candidates = _read_candidates(
        paths.candidates_dir / f"candidates_{tech}__{CENTRAL_SCENARIO}.parquet"
    )
    cell_set = build_cell_set(
        candidates["cell_id"].to_numpy(), data, REFERENCE_MEMBER_ID, member_ids, decision.cf_min
    )
    logger.info("%s %s [%s]: %s", iso, tech, role, cell_set.counts())

    def provenance_for(ranking: Rankings | None) -> dict[str, str]:
        return _provenance(
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

    if cell_set.n_f7 == 0:
        logger.warning(
            "%s %s [%s]: the F7 set is empty (no candidate is present in m0 and in every member of the window and feasible at f0); only the classes are written",
            iso,
            tech,
            role,
        )
        empty_skip = SkippedOutput("every result", "the F7 set is empty", "OQ-008")
        frames = {
            "robustness": classes_only_frame(cell_set, candidates),
            "nominal_lcoe_by_member": empty_nominal_frame(),
        }
        tables = _write_tables(
            tech,
            role,
            frames,
            dict.fromkeys(WINDOW_TABLES, empty_skip),
            provenance_for(None),
            paths.out_dir,
        )
        return _window_result(role, window, cell_set, None, tables)

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
    frames: dict[str, pd.DataFrame | None] = {
        "robustness": robustness_frame(cell_set, evaluation, ranking, candidates),
        "nominal_lcoe_by_member": nominal_by_member_frame(cell_set, evaluation),
    }
    skips: dict[str, SkippedOutput] = {}
    admin1 = candidates["admin1_id"].to_numpy()[np.isin(cell_set.candidate_ids, cell_set.f7_ids)]
    lat = candidates["lat_c"].to_numpy()[np.isin(cell_set.candidate_ids, cell_set.f7_ids)]
    lon = candidates["lon_c"].to_numpy()[np.isin(cell_set.candidate_ids, cell_set.f7_ids)]

    # the sample-major pass (H1, H3, the PRIM input, the ranges over the draws)
    futures = None
    if ranking.top_nominal is not None and ranking.k is not None:
        labels = [
            MemberLabel(m, by_member[m].gcm or "", by_member[m].ssp or "") for m in member_ids
        ]
        futures = futures_pass(
            cell_set.core,
            labels,
            samples,
            ranking.top_nominal.mask,
            ranking.k,
            max_batch_gb=max_batch_gb,
            progress=PeriodicProgress(
                logger, 1, f"{iso} {tech} {role} sample-major pass", every=1
            ).step,
        )
        frames["futures"] = futures_frame(
            cell_set,
            evaluation,
            futures,
            labels,
            design,
            [s.name for s in resolved.specs],
            member_factor_means(paths.climate_dir / "forcing.parquet", cell_set.f7_ids, member_ids),
        )
        frames["draw_statistics"] = draw_statistics_frame(futures)
        prim_settings = experiments.prim
        if (
            decision.prim_outcome_share is None
            or prim_settings.peel_alpha is None
            or prim_settings.mass_min is None
        ):
            skips["prim_boxes"] = SkippedOutput(
                "PRIM boxes (M-F7-08)",
                "prim_outcome_share, prim.peel_alpha or prim.mass_min is null",
                "OQ-056",
            )
        else:
            x, y = prim_input(
                frames["futures"], [s.name for s in resolved.specs], decision.prim_outcome_share
            )
            outcome = run_prim(
                x, y, alpha=prim_settings.peel_alpha, mass_min=prim_settings.mass_min
            )
            frames["prim_boxes"] = prim_frame(outcome, decision.prim_outcome_share)
    else:
        why = SkippedOutput(
            "futures and per-draw statistics (H1, H3, PRIM input)",
            "top_k_percent is null",
            "OQ-021",
        )
        skips["futures"] = skips["draw_statistics"] = why
        skips["prim_boxes"] = SkippedOutput(
            "PRIM boxes (M-F7-08)", "top_k_percent is null", "OQ-021"
        )

    # T-R12: the potential below tau in the three land scenarios, and the draws of the central one
    land_range: dict[str, tuple[float, float]] = {}
    if decision.tau is not None and evaluation.potential_gw is not None:
        assert evaluation.potential_twh is not None
        rows: list[dict] = []
        for scenario in LAND_SCENARIOS:
            potential, lcoe = _scenario_tables(scenario, tech, paths)
            scenario_rows = potential_below_tau_nominal(
                potential,
                lcoe,
                member_ids,
                REFERENCE_MEMBER_ID,
                decision.cf_min,
                decision.tau,
                decision.capacity_target_gw,
                scenario,
            )
            rows += scenario_rows
            like = [r for r in scenario_rows if r["series"] == "like_for_like"]
            reference_gw = next(
                r["potential_gw"] for r in like if r["member"] == REFERENCE_MEMBER_ID
            )
            land_range[scenario] = (
                reference_gw,
                float(
                    np.median(
                        [r["potential_gw"] for r in like if r["member"] != REFERENCE_MEMBER_ID]
                    )
                ),
            )
        rows += potential_below_tau_draws(
            member_ids,
            REFERENCE_MEMBER_ID,
            evaluation.potential_gw,
            evaluation.potential_twh,
            decision.capacity_target_gw,
        )
        central_like = {
            r["member"]: r["potential_gw"]
            for r in rows
            if r["land_scenario"] == CENTRAL_SCENARIO
            and r["series"] == "like_for_like"
            and r["basis"] == "nominal"
        }
        for slot, member in enumerate([REFERENCE_MEMBER_ID, *member_ids]):
            if abs(central_like[member] - float(evaluation.potential_gw[slot, 0])) > 1e-9 * max(
                1.0, abs(central_like[member])
            ):
                raise RobustnessInputError(
                    f"{member}: the potential below tau of the tables and of the evaluation differ (V-03)"
                )
        frames["potential_below_tau"] = pd.DataFrame(rows)
    else:
        skips["potential_below_tau"] = SkippedOutput(
            "potential below tau per member (T-R12)", "tau_lcoe_usd_per_mwh is null", "OQ-008"
        )

    # T-R10: exposure of potential to the hazard indicators, members with the hazard channel only
    exposure_shares: dict[str, float] = {}
    hazard_members = [e for e in entries if e.window == window and e.hazard]
    thresholds = {k: v.threshold for k, v in experiments.hazard_thresholds.items()}
    hazard_path = paths.climate_dir / "hazard_context.parquet"
    if hazard_members and any(v is not None for v in thresholds.values()):
        groups = {"f7_set": np.ones(cell_set.n_f7, dtype=bool)}
        if ranking.top_nominal is not None and ranking.top_robust is not None:
            groups["nominal_top_k"] = ranking.top_nominal.mask
            groups["robust_top_k"] = ranking.top_robust.mask
        members = []
        for e in hazard_members:
            item = data[e.member]
            at = np.searchsorted(item.cell_id, cell_set.f7_ids)
            members.append(
                HazardMember(
                    e.member,
                    e.gcm or "",
                    e.ssp or "",
                    item.cells.p_mw[at],
                    item.cells.energy_mwh[at],
                )
            )
        rows, exposure_shares = exposure_rows(
            pd.read_parquet(hazard_path), members, thresholds, cell_set.f7_ids, groups
        )
        frames["hazard_exposure"] = pd.DataFrame(rows)
    elif not hazard_members:
        skips["hazard_exposure"] = SkippedOutput(
            "hazard exposure (T-R10)",
            f"no member of the {window} window carries the hazard channel (S-05, L-021)",
            "OQ-007",
        )
    else:
        skips["hazard_exposure"] = SkippedOutput(
            "hazard exposure (T-R10)", "every hazard_thresholds entry is null", "OQ-051"
        )

    # H1 to H5 and the pre-registered rules
    statistics = (
        h2(cell_set, evaluation, admin1)
        + h4(cell_set, evaluation, ranking)
        + agreement(cell_set, evaluation)
    )
    if futures is not None:
        statistics += h1(futures, cell_set, ranking) + h3(cell_set, ranking, futures, lat, lon)
    if evaluation.potential_gw is not None:
        statistics += h5(
            evaluation, cell_set.n_f7, decision.capacity_target_gw, exposure_shares, land_range
        )
    _, without_rule = rules_for(experiments)
    for hypothesis in without_rule:
        logger.warning(
            "%s %s [%s]: %s has no pre-registered rule (OQ-050); its statistics carry no verdict",
            iso,
            tech,
            role,
            hypothesis,
        )
    frames["hypothesis"] = hypothesis_frame(
        statistics, evaluate_rules(statistics, experiments.hypothesis_rules), window
    )
    tables = _write_tables(tech, role, frames, skips, provenance_for(ranking), paths.out_dir)
    return _window_result(role, window, cell_set, ranking, tables)


def _window_result(
    role: str,
    window: str,
    cell_set: CellSet,
    ranking: Rankings | None,
    tables: Mapping[str, Path],
) -> WindowResult:
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
        tables=dict(tables),
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
    lcoe_dir: Path | None = None,
    out_dir: Path | None = None,
) -> RobustnessSummary:
    """F7 for `iso` and the technologies of the run, on the central land scenario, the core window and the sensitivity window.

    Implements: M-F7-01 to M-F7-11.

    Raises:
        RobustnessConfigError: `q_ref` is not 0 (OQ-020).
        RobustnessMissingInputError: an F6 parameter or `CF_min` is missing; raised before any input is read.
        FileNotFoundError: an F3, F4, F5 or F6 input is absent.
    """
    resolved, decisions = check_start(
        iso, technologies, country_params, run_technologies, experiments
    )
    paths = WindowPaths(
        potential_dir=Path(
            potential_dir or core_paths.phase_dir(iso, "technical_potential", "artifacts")
        ),
        candidates_dir=Path(
            candidates_dir or core_paths.phase_dir(iso, "land_eligibility", "artifacts")
        ),
        climate_dir=Path(climate_dir or core_paths.phase_dir(iso, "climate_forcing", "artifacts")),
        lcoe_dir=Path(lcoe_dir or core_paths.phase_dir(iso, "lcoe_modeling", "artifacts")),
        out_dir=Path(out_dir)
        if out_dir
        else core_paths.phase_dir(iso, "robustness_analysis", "artifacts"),
    )
    needed = [
        paths.climate_dir / "members.yaml",
        paths.climate_dir / "forcing.parquet",
        paths.climate_dir / "hazard_context.parquet",
    ]
    for tech in resolved:
        needed.append(paths.lcoe_dir / f"lcoe_summary_{tech}.parquet")
        for scenario in LAND_SCENARIOS:
            needed.append(paths.potential_dir / f"potential_{tech}__{scenario}.parquet")
            needed.append(paths.candidates_dir / f"candidates_{tech}__{scenario}.parquet")
            if scenario != CENTRAL_SCENARIO:
                needed.append(paths.lcoe_dir / f"lcoe_nominal_{tech}__{scenario}.parquet")
    absent = [str(p) for p in needed if not p.is_file()]
    if absent:
        raise FileNotFoundError(f"F7 input missing (F3, F4, F5 and F6 must have run): {absent}")
    paths.out_dir.mkdir(parents=True, exist_ok=True)  # created only once every input is there
    entries = read_member_entries(paths.climate_dir / "members.yaml")
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
                paths,
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
