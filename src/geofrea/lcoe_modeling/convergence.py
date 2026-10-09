"""Support phase `sample_size_convergence`: the U-04 protocol for the size of the Latin hypercube (V-05; D-F6-004).

Start at `sampler.initial_size` draws and double. For each size compute the max-regret `MR` of the cells of the F7 set (the cells of the
central scenario with an F5 row in `m0` and in every member of the core window, feasible in the nominal present future), take the best
`p_k` percent by `MR` as the top-k set, and compare it with the top-k set of the previous size: the size is adopted when
`1 - Jaccard` of the two sets is below `sampler.convergence_tolerance`. A ceiling, `sampler.max_size_for_convergence`, stops a case that
does not converge, and the result then says so.

`MR` comes from `provisional_regret`, a stand-in for the F7 function (no `CF_min`, `q_ref = 0`); the result and the table metadata carry
`mr_function = "provisional"`, and the F7 function replaces it when F7 exists. The draws of different sizes are independent, not nested,
so the Jaccard distance between two sizes includes sampling noise. The ties of the ranking are broken by `cell_id`.

The phase reads no table the F6 phase writes; it calls the same kernel on the same inputs. In the real countries it runs once their
parameters have ranges, `thresholds.top_k_percent` (OQ-021) and the ceiling have values; before that it raises, listing what is missing.
"""

from __future__ import annotations

import json
import logging
import math
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
from geofrea.lcoe_modeling.kernel import CellInputs, lcoe_block
from geofrea.lcoe_modeling.pipeline import (
    LcoeInputError,
    ResolvedLcoe,
    cells_per_block,
    read_member_inputs,
    resolve_all,
)
from geofrea.lcoe_modeling.provisional_regret import PROVISIONAL, provisional_max_regret
from geofrea.lcoe_modeling.table_schemas import LCOE_TABLE_SCHEMA_VERSION

logger = logging.getLogger("geofrea.lcoe_modeling.convergence")

PROVENANCE_KEY = "geofrea_convergence_provenance"
MR_FUNCTION = "provisional"


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


def top_k_cells(mr: np.ndarray, cell_id: np.ndarray, top_k_percent: float) -> np.ndarray:
    """The `ceil(p_k / 100 * C)` cells (at least one) with the lowest `MR`, ties broken by `cell_id` (M-F7-05, provisional)."""
    if not 0 < top_k_percent <= 100:
        raise ConvergenceConfigError([f"thresholds.top_k_percent {top_k_percent} outside (0, 100]"])
    k = max(1, math.ceil(top_k_percent / 100.0 * len(cell_id)))
    order = np.lexsort((cell_id, mr))
    return cell_id[order[:k]]


def f7_set(
    members_data: Mapping[str, tuple[np.ndarray, CellInputs]],
    core_members: Sequence[str],
    nominal_energy_positive: np.ndarray,
    reference_ids: np.ndarray,
) -> np.ndarray:
    """Cell identifiers of the F7 set: present in `m0` and every core member, with positive energy in the nominal present future."""
    common = set(reference_ids.tolist())
    for member in core_members:
        ids = members_data.get(member)
        common &= set(ids[0].tolist()) if ids is not None else set()
    keep = np.array(sorted(common), dtype="int64")
    return keep[np.isin(keep, reference_ids[nominal_energy_positive])]


def run_protocol(
    resolved: ResolvedLcoe,
    members_data: Mapping[str, tuple[np.ndarray, CellInputs]],
    core_members: Sequence[str],
    *,
    initial_size: int,
    max_size: int,
    seed: int,
    tolerance: float,
    top_k_percent: float,
    max_batch_gb: float,
) -> tuple[list[ConvergenceRow], int | None, int, np.ndarray]:
    """Double the sample size from `initial_size` to at most `max_size` until the top-k sets agree within `tolerance`.

    Implements: U-04, V-05.

    Returns:
        The rows, the adopted size (None if the ceiling came first), the number of cells of the F7 set and their identifiers.

    Raises:
        LcoeInputError: the reference member is missing, or no cell is in the F7 set.
    """
    if REFERENCE_MEMBER_ID not in members_data:
        raise LcoeInputError(f"member {REFERENCE_MEMBER_ID} has no F5 rows")
    ref_ids, ref_cells = members_data[REFERENCE_MEMBER_ID]
    nominal_design = build_design(resolved.specs, 1, seed).iloc[:1]
    nominal_samples = samples_from_design(nominal_design, resolved.nominal, resolved.energy_key)
    nominal_lcoe = lcoe_block(ref_cells, nominal_samples)[:, 0]
    keep_ids = f7_set(members_data, core_members, np.isfinite(nominal_lcoe), ref_ids)
    if keep_ids.size == 0:
        raise LcoeInputError(
            "the F7 set is empty: no cell is present in every core member and feasible at m0"
        )
    per_member: list[CellInputs] = []
    for member in core_members:
        ids, cells = members_data[member]
        per_member.append(cells.take(np.searchsorted(ids, keep_ids)))
    rows: list[ConvergenceRow] = []
    previous: np.ndarray | None = None
    adopted: int | None = None
    size = initial_size
    while size <= max_size:
        design = build_design(resolved.specs, size, seed)
        samples = samples_from_design(design, resolved.nominal, resolved.energy_key)
        mr = provisional_max_regret(
            per_member, samples.take(slice(1, None)), cells_per_block(max_batch_gb, size)
        )
        top = top_k_cells(mr, keep_ids, top_k_percent)
        overlap = None if previous is None else jaccard(previous, top)
        meets = overlap is not None and 1.0 - overlap < tolerance
        rows.append(
            ConvergenceRow(
                n_samples=size,
                n_cells=int(keep_ids.size),
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
            keep_ids.size,
            overlap,
        )
        previous = top
        if meets:
            adopted = size
            break
        size *= 2
    return rows, adopted, int(keep_ids.size), keep_ids


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
        ConvergenceConfigError: `thresholds.top_k_percent`, the ceiling, or `regret_quantile = 0` is not available.
        FileNotFoundError: an F3, F4 or F5 input is absent.
    """
    resolved = resolve_all(iso, technologies, country_params, run_technologies)
    missing = []
    top_k_percent = thresholds.get("top_k_percent")
    if top_k_percent is None:
        missing.append("thresholds.top_k_percent is null (OQ-021)")
    if sampler.max_size_for_convergence is None:
        missing.append("sampler.max_size_for_convergence is null (the author's ceiling, D-F6-004)")
    if thresholds.get("regret_quantile") != 0:
        missing.append(
            "thresholds.regret_quantile must be 0: the provisional MR supports only q_ref = 0 (OQ-020)"
        )
    if missing:
        raise ConvergenceConfigError(missing)
    assert top_k_percent is not None and sampler.max_size_for_convergence is not None
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
        x_values = [s for s in res.specs if s.name == res.energy_key]
        x_range = (
            (x_values[0].low, x_values[0].high) if x_values else (res.nominal[res.energy_key],) * 2
        )
        members_data = {
            item.member: (item.cell_id, item.cells)
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
        rows, adopted, n_cells, _ids = run_protocol(
            res,
            members_data,
            core,
            initial_size=sampler.initial_size,
            max_size=sampler.max_size_for_convergence,
            seed=sampler.seed,
            tolerance=sampler.convergence_tolerance,
            top_k_percent=float(top_k_percent),
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
                    "provisional": PROVISIONAL,
                    "criterion": "1 - Jaccard of the top-k sets of consecutive sizes below the tolerance",
                    "tolerance": sampler.convergence_tolerance,
                    "top_k_percent": float(top_k_percent),
                    "seed": sampler.seed,
                    "adopted_size": adopted,
                    "feasibility": "positive energy (no CF_min, OQ-008)",
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
            converged=adopted is not None,
            adopted_size=adopted,
            tolerance=sampler.convergence_tolerance,
            top_k_percent=float(top_k_percent),
            n_cells=n_cells,
            n_members=len(core),
            sizes=[r.n_samples for r in rows],
            table=path,
        )
    return ConvergenceSummary(country_code=iso, technologies=result)
