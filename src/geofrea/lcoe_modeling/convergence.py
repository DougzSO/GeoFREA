"""Support phase `sample_size_convergence`: the U-04 protocol for the size of the Latin hypercube (V-05; D-F6-004, D-F7-027).

Start at `sampler.initial_size` draws and double. For each size compute the max-regret `MR` of F7 (`robustness_analysis.evaluator`, the same
function the F7 phase runs: feasibility by `CF_min` on `CF(m, s0)`, `q_ref = 0`, the exact P90 over the draws, the maximum over the core
members) for the cells of the F7 set, take the robust top-k (the best `p_k` percent by `MR`, ties by `SR` when `tau` is set and then by
`cell_id`, M-F7-05) and compare it with the top-k set of the previous size: the size is adopted when `1 - Jaccard` of the two sets is below
`sampler.convergence_tolerance`. A ceiling, `sampler.max_size_for_convergence`, stops a case that does not converge, and the result then says
so. The draws of different sizes are independent, not nested, so the Jaccard distance between two sizes includes sampling noise.

The phase reads no table the F6 phase writes; it calls the same kernel on the same inputs. In the real countries it runs once their
parameters have ranges, `cf_min` (OQ-008) and `top_k_percent` (OQ-021, both per country and technology in `parameters.json`) and the ceiling
have values; before that it raises, listing what is missing.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict

from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID
from geofrea.core import paths as core_paths
from geofrea.core.config_schemas import SamplerConfig, TechnologiesFile
from geofrea.core.schemas import CountryParams
from geofrea.core.tables import write_table
from geofrea.lcoe_modeling.design import build_design, samples_from_design
from geofrea.lcoe_modeling.inputs import (
    LcoeInputError,
    MemberCells,
    ResolvedLcoe,
    cells_per_block,
    read_member_inputs,
    resolve_all,
)
from geofrea.lcoe_modeling.table_schemas import LCOE_TABLE_SCHEMA_VERSION
from geofrea.robustness_analysis.assemble import compute_rankings
from geofrea.robustness_analysis.cell_set import build_cell_set
from geofrea.robustness_analysis.decision import TechDecision, check_ranges, decision_values
from geofrea.robustness_analysis.evaluator import evaluate

logger = logging.getLogger("geofrea.lcoe_modeling.convergence")

PROVENANCE_KEY = "geofrea_convergence_provenance"
MR_FUNCTION = "f7"


class ConvergenceConfigError(RuntimeError):
    """The protocol cannot start because a value only the author can set is missing (A-09); the message lists them all."""

    def __init__(self, missing: Sequence[str]) -> None:
        self.missing = list(missing)
        super().__init__(
            f"sample_size_convergence cannot run: {len(self.missing)} missing item(s): "
            + "; ".join(self.missing)
        )


class ConvergenceRow(BaseModel):
    """One sample size of the protocol (U-04)."""

    model_config = ConfigDict(extra="forbid")

    n_samples: int
    n_cells: int
    k: int
    jaccard_with_previous: float | None
    jaccard_distance_with_previous: float | None
    meets_tolerance: bool


class TechConvergence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    technology: str
    mr_function: str
    cf_min: float
    converged: bool
    adopted_size: int | None
    tolerance: float
    top_k_percent: float
    n_cells: int
    n_members: int
    sizes: list[int]
    table: Path


class ConvergenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    technologies: dict[str, TechConvergence]


def convergence_dir(iso: str) -> Path:
    path = core_paths.phase_dir(iso, "sample_size_convergence", "artifacts")
    path.mkdir(parents=True, exist_ok=True)
    return path


def jaccard(a: np.ndarray, b: np.ndarray) -> float:
    """`|A and B| / |A or B|` of two sets of cell identifiers; 1 for two empty sets."""
    sa, sb = set(a.tolist()), set(b.tolist())
    union = sa | sb
    return len(sa & sb) / len(union) if union else 1.0


def run_protocol(
    resolved: ResolvedLcoe,
    members: Mapping[str, MemberCells],
    core_members: Sequence[str],
    candidate_ids: np.ndarray,
    decision: TechDecision,
    *,
    initial_size: int,
    max_size: int,
    seed: int,
    tolerance: float,
    max_batch_gb: float,
) -> tuple[list[ConvergenceRow], int | None, int, np.ndarray, np.ndarray]:
    """Double the sample size from `initial_size` to at most `max_size` until the top-k sets agree within `tolerance`.

    Implements: U-04, V-05.

    Args:
        resolved: The resolved F6 inputs of the technology.
        members: The cells of each member that has an F5 row (`read_member_inputs`), the reference member and the core members included.
        core_members: The members of the core window.
        candidate_ids: Cell identifiers of the candidates of the central scenario.
        decision: `cf_min` and `top_k_percent` (and `tau`, which only breaks ties of `MR`) of the technology.

    Returns:
        The rows, the adopted size (None if the ceiling came first), the number of cells of the F7 set, their identifiers and the identifiers
        of the top-k set of the last size.

    Raises:
        LcoeInputError: the reference member is missing, or no cell is in the F7 set.
    """
    if REFERENCE_MEMBER_ID not in members:
        raise LcoeInputError(f"member {REFERENCE_MEMBER_ID} has no F5 rows")
    assert decision.cf_min is not None and decision.top_k_percent is not None
    cell_set = build_cell_set(
        candidate_ids, members, REFERENCE_MEMBER_ID, list(core_members), decision.cf_min
    )
    if cell_set.n_f7 == 0:
        raise LcoeInputError(
            "the F7 set is empty: no cell is present in m0 and every core member and feasible at m0"
        )
    rows: list[ConvergenceRow] = []
    previous: np.ndarray | None = None
    adopted: int | None = None
    size = initial_size
    while size <= max_size:
        design = build_design(resolved.specs, size, seed)
        samples = samples_from_design(design, resolved.nominal, resolved.energy_key)
        evaluation = evaluate(
            cell_set.reference,
            cell_set.core,
            samples,
            tau=decision.tau,
            block_cells=cells_per_block(max_batch_gb, size),
        )
        ranking = compute_rankings(cell_set, evaluation, decision)
        assert ranking.top_robust is not None
        top = cell_set.f7_ids[ranking.top_robust.mask]
        overlap = None if previous is None else jaccard(previous, top)
        meets = overlap is not None and 1.0 - overlap < tolerance
        rows.append(
            ConvergenceRow(
                n_samples=size,
                n_cells=cell_set.n_f7,
                k=int(top.size),
                jaccard_with_previous=overlap,
                jaccard_distance_with_previous=None if overlap is None else 1.0 - overlap,
                meets_tolerance=meets,
            )
        )
        logger.info(
            "sample size %d: top-k %d of %d cells, Jaccard with the previous size %s",
            size,
            top.size,
            cell_set.n_f7,
            overlap,
        )
        previous = top
        if meets:
            adopted = size
            break
        size *= 2
    assert previous is not None
    return rows, adopted, cell_set.n_f7, cell_set.f7_ids, previous


def _core_members(members_file: Path, core_window: str) -> tuple[list[str], list[str]]:
    """All member identifiers of `members.yaml`, and the ones of the core window."""
    entries = yaml.safe_load(members_file.read_text(encoding="utf-8"))["members"]
    return [e["member"] for e in entries], [
        e["member"] for e in entries if e.get("window") == core_window
    ]


def build_convergence(
    iso: str,
    technologies: TechnologiesFile,
    country_params: CountryParams,
    run_technologies: Sequence[str],
    *,
    sampler: SamplerConfig,
    thresholds: Mapping[str, object],
    core_window: str,
    max_batch_gb: float,
    potential_dir: Path | None = None,
    candidates_dir: Path | None = None,
    climate_dir: Path | None = None,
    out_dir: Path | None = None,
) -> ConvergenceSummary:
    """The U-04 protocol for `iso` and the technologies of the run.

    Implements: U-04, V-05.

    Raises:
        LcoeMissingInputError: a parameter, range or price year is absent (listed first, before any file is read).
        ConvergenceConfigError: `cf_min` or `top_k_percent` of a technology, the ceiling, or `regret_quantile = 0` is not available.
        FileNotFoundError: an F3, F4 or F5 input is absent.
    """
    resolved = resolve_all(iso, technologies, country_params, run_technologies)
    missing = []
    decisions: dict[str, TechDecision] = {}
    for tech in resolved:
        decision = decision_values(getattr(country_params.technologies, tech), tech)
        decisions[tech] = decision
        if decision.cf_min is None:
            missing.append(f"{tech}: cf_min is null (OQ-008)")
        if decision.top_k_percent is None:
            missing.append(f"{tech}: top_k_percent is null (OQ-021)")
        missing += [f"{tech}: {item}" for item in check_ranges(decision)]
    if sampler.max_size_for_convergence is None:
        missing.append("sampler.max_size_for_convergence is null (the author's ceiling, D-F6-004)")
    if thresholds.get("regret_quantile") != 0:
        missing.append(
            "thresholds.regret_quantile must be 0: the regret supports only q_ref = 0 (OQ-020)"
        )
    if missing:
        raise ConvergenceConfigError(missing)
    assert sampler.max_size_for_convergence is not None
    potential_dir = potential_dir or core_paths.phase_dir(iso, "technical_potential", "artifacts")
    candidates_dir = candidates_dir or core_paths.phase_dir(iso, "land_eligibility", "artifacts")
    climate_dir = climate_dir or core_paths.phase_dir(iso, "climate_forcing", "artifacts")
    out_dir = out_dir or convergence_dir(iso)
    members_file = Path(climate_dir) / "members.yaml"
    forcing_path = Path(climate_dir) / "forcing.parquet"
    needed = [members_file, forcing_path]
    for tech in resolved:
        needed.append(Path(potential_dir) / f"potential_{tech}__central.parquet")
        needed.append(Path(candidates_dir) / f"candidates_{tech}__central.parquet")
    absent = [str(p) for p in needed if not p.is_file()]
    if absent:
        raise FileNotFoundError(
            f"sample_size_convergence input missing (F3, F4 and F5 must have run): {absent}"
        )
    all_members, core = _core_members(members_file, core_window)
    if not core:
        raise LcoeInputError(f"members.yaml has no member of the core window {core_window}")
    result: dict[str, TechConvergence] = {}
    for tech, res in resolved.items():
        decision = decisions[tech]
        x_values = [s for s in res.specs if s.name == res.energy_key]
        x_range = (
            (x_values[0].low, x_values[0].high) if x_values else (res.nominal[res.energy_key],) * 2
        )
        members = {
            item.member: item
            for item in read_member_inputs(
                res,
                potential_path=Path(potential_dir) / f"potential_{tech}__central.parquet",
                candidates_path=Path(candidates_dir) / f"candidates_{tech}__central.parquet",
                forcing_path=forcing_path,
                members=[REFERENCE_MEMBER_ID, *core],
                x_range=x_range,
                known_members=all_members,
            )
        }
        candidate_ids = pd.read_parquet(
            Path(candidates_dir) / f"candidates_{tech}__central.parquet", columns=["cell_id"]
        )["cell_id"].to_numpy()
        rows, adopted, n_cells, _ids, _top = run_protocol(
            res,
            members,
            core,
            candidate_ids,
            decision,
            initial_size=sampler.initial_size,
            max_size=sampler.max_size_for_convergence,
            seed=sampler.seed,
            tolerance=sampler.convergence_tolerance,
            max_batch_gb=max_batch_gb,
        )
        if adopted is None:
            logger.warning(
                "%s %s: the top-k sets did not agree within %s up to %d samples; no size is adopted",
                iso,
                tech,
                sampler.convergence_tolerance,
                rows[-1].n_samples,
            )
        provenance = {
            PROVENANCE_KEY: json.dumps(
                {
                    "technology": tech,
                    "mr_function": MR_FUNCTION,
                    "provisional": False,
                    "criterion": "1 - Jaccard of the top-k sets of consecutive sizes below the tolerance",
                    "tolerance": sampler.convergence_tolerance,
                    "top_k_percent": decision.top_k_percent,
                    "cf_min": decision.cf_min,
                    "tau_lcoe_usd_per_mwh": decision.tau,
                    "seed": sampler.seed,
                    "adopted_size": adopted,
                    "feasibility": "CF(m, s0) >= cf_min, as an energy floor in the kernel (D-F7-007)",
                    "q_ref": 0,
                    "core_window": core_window,
                },
                sort_keys=True,
            )
        }
        path = write_table(
            pd.DataFrame([r.model_dump() for r in rows]),
            Path(out_dir) / f"sample_size_convergence_{tech}.parquet",
            schema_version=LCOE_TABLE_SCHEMA_VERSION,
            row_model=ConvergenceRow,
            extra_metadata=provenance,
        )
        result[tech] = TechConvergence(
            technology=tech,
            mr_function=MR_FUNCTION,
            cf_min=float(decision.cf_min),
            converged=adopted is not None,
            adopted_size=adopted,
            tolerance=sampler.convergence_tolerance,
            top_k_percent=float(decision.top_k_percent),
            n_cells=n_cells,
            n_members=len(core),
            sizes=[r.n_samples for r in rows],
            table=path,
        )
    return ConvergenceSummary(country_code=iso, technologies=result)
