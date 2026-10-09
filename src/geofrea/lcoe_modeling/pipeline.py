"""F6 lcoe_modeling end to end for one country: LCOE summaries, design matrix and nominal supply curves per technology.

Reads, per technology, `potential_<tech>__central.parquet` (F5), `candidates_<tech>__central.parquet` (F3: the real distances),
`forcing.parquet` and `members.yaml` (F4); writes under `outputs/<ISO3>/lcoe_modeling/artifacts/`:

  - `lcoe_summary_<tech>.parquet`: per (cell, member), the nominal LCOE and the mean, variance, p10, p50 and p90 over the draws (M-F6-04);
  - `design_matrix_<tech>.parquet`: the Latin hypercube design, sample 0 the nominal vector (M-F6-02, M-F6-06);
  - `supply_curve_<tech>.parquet`: per member, the cells in increasing nominal LCOE with cumulative capacity and energy (M-F6-06).

Nothing is read before every parameter, range and price year is checked: a missing one raises `LcoeMissingInputError` listing all of them
(A-09). Members are the outer loop and cells are processed in blocks that hold every sample, so the quantiles are exact and the memory
stays under `memory.max_batch_gb` (A-10, D-F6-002, D-F6-005). No sample-level array is ever written. See docs/phases/F6_lcoe_modeling.md
D-F6-001 to D-F6-016.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import yaml
from pydantic import BaseModel, ConfigDict

from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID
from geofrea.core import paths as core_paths
from geofrea.core.config_schemas import TechnologiesFile, TechnologyConfig
from geofrea.core.constants import PRICE_BASE_YEAR_USD
from geofrea.core.run_logging import PeriodicProgress
from geofrea.core.schemas import CountryParams
from geofrea.core.tables import TableWriter, require_schema_version, write_table
from geofrea.lcoe_modeling.design import build_design, samples_from_design
from geofrea.lcoe_modeling.kernel import (
    KERNEL_PARAMETER_KEYS,
    KERNEL_VERSION,
    CellInputs,
    SampleInputs,
    lcoe_block,
)
from geofrea.lcoe_modeling.sampling import UncertainSpec
from geofrea.lcoe_modeling.summary import QUANTILES, BlockSummary, summarize_draws
from geofrea.lcoe_modeling.supply_curve import supply_curve
from geofrea.lcoe_modeling.table_schemas import (
    LCOE_TABLE_SCHEMA_VERSION,
    DesignMatrixRow,
    LcoeSummaryRow,
    SupplyCurveRow,
)
from geofrea.technical_potential.cf_models import CfModel, CfModelError, get_cf_model
from geofrea.technical_potential.pipeline import PROVENANCE_KEY as POTENTIAL_PROVENANCE_KEY
from geofrea.technical_potential.table_schemas import POTENTIAL_TABLE_SCHEMA_VERSION

logger = logging.getLogger("geofrea.lcoe_modeling.pipeline")

PROVENANCE_KEY = "geofrea_lcoe_provenance"
# the parameters of M-F6-01 that are costs in USD and so carry a price year (S-07, D-F6-008)
COST_PRICE_KEYS = (
    "capex_usd_per_kw",
    "opex_var_usd_per_mwh",
    "grid_cost_usd_per_mw_km",
    "substation_cost_usd_per_mw",
    "road_cost_usd_per_km",
)
LIVE_BLOCKS = 4  # live cell-by-sample arrays at the peak (D-F6-005)
BYTES_PER_VALUE = 8
CF_MAX = 1.0 + 1e-9  # V-03: a sampled capacity factor may not exceed 1 (rounding slack only)


class LcoeMissingInputError(RuntimeError):
    """F6 cannot start because parameters, ranges or price years are absent; the message lists every missing item (A-09)."""

    def __init__(self, country: str, technology: str, missing: Sequence[str]) -> None:
        self.country = country
        self.technology = technology
        self.missing = list(missing)
        super().__init__(
            f"F6 cannot run for {country} {technology}: {len(self.missing)} missing item(s): "
            + "; ".join(self.missing)
        )


class LcoeInputError(RuntimeError):
    """An input table of F6 breaks its contract (A-09)."""


class TechLcoe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    technology: str
    n_samples: int
    seed: int
    cells_per_block: int
    n_cells: int
    n_members: int
    n_rows: int
    n_nonfinite_nominal: int
    n_draw_nonfinite: int
    lcoe_nominal_m0_min: float | None
    lcoe_nominal_m0_median: float | None
    lcoe_summary: Path
    design_matrix: Path
    supply_curve: Path


class LcoeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    technologies: dict[str, TechLcoe]


@dataclass(frozen=True)
class ResolvedLcoe:
    """A technology whose F6 parameters, ranges and price years were all found: ready to compute."""

    technology: str
    cf_model_name: str
    model: CfModel
    energy_key: str
    nominal: Mapping[str, float]  # every kernel key and the energy key
    specs: tuple[UncertainSpec, ...]  # the uncertain parameters, in registry order


def lcoe_dir(iso: str) -> Path:
    path = core_paths.phase_dir(iso, "lcoe_modeling", "artifacts")
    path.mkdir(parents=True, exist_ok=True)
    return path


def cells_per_block(max_batch_gb: float, n_samples: int) -> int:
    """Cells per block so that `LIVE_BLOCKS` cell-by-sample float64 arrays of `n_samples + 1` samples fit in `max_batch_gb`.

    Implements: A-10, D-F6-005.
    """
    if max_batch_gb <= 0:
        raise LcoeInputError("memory.max_batch_gb must be positive")
    return max(1, int(max_batch_gb * 1.0e9 // (LIVE_BLOCKS * BYTES_PER_VALUE * (n_samples + 1))))


def _range_problem(key: str, low: float, high: float) -> str | None:
    """Why the range `[low, high]` of `key` lies outside the domain of the kernel (D-F6-010), or None."""
    if key == "lifetime_years" and low < 1:
        return "lifetime below one year"
    if key == "discount_rate" and low < 0:
        return "negative discount rate"
    if key == "degradation_rate" and (low < 0 or high >= 1):
        return "degradation outside [0, 1)"
    if (key in COST_PRICE_KEYS or key == "opex_fixed_frac") and low < 0:
        return "negative cost"
    return None


def resolve_technology_costs(
    iso: str, technology: str, tech_cfg: TechnologyConfig, tech_params: object
) -> ResolvedLcoe:
    """Check every F6 input of a technology and gather them; raise `LcoeMissingInputError` listing what is absent.

    Implements: M-F6-01, M-F6-02, D-F6-008, D-F6-010, D-F6-016.

    A parameter is missing when it has no entry or no value, an uncertain one also when it has no range or a range outside the
    domain of the kernel, and a cost when its price year is not the base year (S-07).

    Raises:
        LcoeMissingInputError: any of the above, all listed.
        CfModelError: the registry is inconsistent (unknown model, an uncertain key F6 does not use).
    """
    model = get_cf_model(tech_cfg.cf_model)
    energy_key = model.sampled_parameter_key
    needed = (*KERNEL_PARAMETER_KEYS, energy_key)
    unused = [k for k in tech_cfg.uncertain_parameters if k not in needed]
    if unused:
        raise CfModelError(
            f"registry entry {technology!r}: uncertain parameters {unused} are not used by F6 (known: {list(needed)})"
        )
    uncertain = set(tech_cfg.uncertain_parameters)
    missing: list[str] = []
    nominal: dict[str, float] = {}
    specs: dict[str, UncertainSpec] = {}
    for key in needed:
        entry = getattr(tech_params, key, None)
        if entry is None:
            missing.append(f"{key} (no entry in parameters.json)")
            continue
        if entry.value is None:
            missing.append(f"{key} ({entry.status or 'no value'})")
        else:
            nominal[key] = float(entry.value)
            if key in COST_PRICE_KEYS and entry.price_year != PRICE_BASE_YEAR_USD:
                missing.append(
                    f"{key} price_year (is {entry.price_year}, S-07 needs {PRICE_BASE_YEAR_USD})"
                )
        if key in uncertain:
            if entry.range is None:
                missing.append(f"{key} range (no range in parameters.json, U-05)")
            elif entry.value is not None:
                problem = _range_problem(key, entry.range.min, entry.range.max)
                if problem is not None:
                    missing.append(
                        f"{key} range [{entry.range.min}, {entry.range.max}] ({problem})"
                    )
                else:
                    specs[key] = UncertainSpec(
                        key,
                        float(entry.value),
                        entry.range.min,
                        entry.range.max,
                        entry.range.distribution,
                    )
    if missing:
        raise LcoeMissingInputError(iso, technology, missing)
    return ResolvedLcoe(
        technology=technology,
        cf_model_name=tech_cfg.cf_model,
        model=model,
        energy_key=energy_key,
        nominal=nominal,
        specs=tuple(specs[k] for k in tech_cfg.uncertain_parameters),
    )


def _member_codes(frame: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """Integer code and category list of the `member` column, without turning millions of rows into strings."""
    column = frame["member"]
    if isinstance(column.dtype, pd.CategoricalDtype):
        return column.cat.codes.to_numpy(), [str(c) for c in column.cat.categories]
    codes, categories = pd.factorize(column.astype(str))
    return codes, [str(c) for c in categories]


def _assert_potential_matches(path: Path, resolved: ResolvedLcoe) -> None:
    """The energy F5 stored was computed at the nominal energy parameter F6 rescales from; a mismatch means a stale F5 table."""
    require_schema_version(path, POTENTIAL_TABLE_SCHEMA_VERSION)
    meta = pq.read_schema(path).metadata or {}
    raw = meta.get(POTENTIAL_PROVENANCE_KEY.encode())
    if raw is None:
        raise LcoeInputError(f"{path.name}: no F5 provenance in the table metadata")
    stored = json.loads(raw.decode())["parameters"].get(resolved.energy_key)
    if stored is None or float(stored) != resolved.nominal[resolved.energy_key]:
        raise LcoeInputError(
            f"{path.name}: F5 computed the energy at {resolved.energy_key} = {stored}, parameters.json now has "
            f"{resolved.nominal[resolved.energy_key]}; rerun F5 (A-02)"
        )


@dataclass(frozen=True)
class MemberCells:
    """The cells of one member that have an F5 row, with the inputs the kernel needs."""

    member: str
    cell_id: np.ndarray
    cells: CellInputs
    cf: np.ndarray


def iter_member_summaries(
    cells: CellInputs,
    nominal_samples: SampleInputs,
    draw_samples: SampleInputs,
    block_cells: int,
) -> Iterator[tuple[slice, np.ndarray, BlockSummary]]:
    """For each block of at most `block_cells` cells: the slice, the nominal LCOE and the summary of the draws.

    Implements: M-F6-04, A-10.

    Only one block of draws is alive at a time, so the peak is bounded by the block size and not by the number of cells.
    """
    for start in range(0, len(cells), block_cells):
        window = slice(start, min(start + block_cells, len(cells)))
        part = cells.take(window)
        nominal = lcoe_block(part, nominal_samples)[:, 0]
        draws = lcoe_block(part, draw_samples)
        yield window, nominal, summarize_draws(draws)


def _check_summary(summary: BlockSummary, nominal: np.ndarray, member: str) -> None:
    """V-03: positive costs, ordered quantiles, non-negative variance."""
    finite_var = summary.var[np.isfinite(summary.var)]
    if (
        (nominal < 0).any()
        or (summary.p10 > summary.p50).any()
        or (summary.p50 > summary.p90).any()
        or (finite_var < 0).any()
    ):
        raise LcoeInputError(f"member {member}: a summary breaks its invariants (V-03)")


def _provenance(
    resolved: ResolvedLcoe,
    n_samples: int,
    seed: int,
    block_cells: int,
    max_batch_gb: float,
    production: bool,
) -> dict[str, str]:
    payload = {
        "technology": resolved.technology,
        "cf_model": resolved.cf_model_name,
        "nominal_parameters": dict(resolved.nominal),
        "uncertain_parameters": [s.name for s in resolved.specs],
        "distributions": {s.name: s.distribution for s in resolved.specs},
        "energy_parameter": resolved.energy_key,
        "n_samples": n_samples,
        "seed": seed,
        "kernel_version": KERNEL_VERSION,
        "price_base_year_usd": PRICE_BASE_YEAR_USD,
        "summary_samples": "draws s >= 1; the nominal vector s0 is lcoe_nominal and enters no statistic",
        "quantiles": list(QUANTILES),
        "quantile_method": "linear interpolation (Hyndman-Fan type 7)",
        "variance_ddof": 1,
        "cells_per_block": block_cells,
        "max_batch_gb": max_batch_gb,
        "c3_applied": False,
        "production": production,
    }
    return {PROVENANCE_KEY: json.dumps(payload, sort_keys=True)}


def _empty_summary_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cell_id": pd.Series(dtype="int64"),
            "member": pd.Series(dtype="object"),
            "lcoe_nominal": pd.Series(dtype="float64"),
            "lcoe_mean": pd.Series(dtype="float64"),
            "lcoe_var": pd.Series(dtype="float64"),
            "lcoe_p10": pd.Series(dtype="float64"),
            "lcoe_p50": pd.Series(dtype="float64"),
            "lcoe_p90": pd.Series(dtype="float64"),
            "n_nonfinite": pd.Series(dtype="int64"),
        }
    )


def _empty_supply_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "member": pd.Series(dtype="object"),
            "rank": pd.Series(dtype="int64"),
            "cell_id": pd.Series(dtype="int64"),
            "lcoe_nominal": pd.Series(dtype="float64"),
            "cum_P_GW": pd.Series(dtype="float64"),
            "cum_E_TWh": pd.Series(dtype="float64"),
        }
    )


def read_member_inputs(
    resolved: ResolvedLcoe,
    *,
    potential_path: Path,
    candidates_path: Path,
    forcing_path: Path,
    members: Sequence[str],
    x_range: tuple[float, float],
    known_members: Sequence[str] | None = None,
) -> Iterator[MemberCells]:
    """Per member of `members`, in order, the cells with an F5 row and the kernel inputs of each.

    Implements: M-F6-01.

    `known_members` (default `members`) is the full list of `members.yaml`: the F5 table may only hold members of it, whether or not
    this call asks for all of them.

    Raises:
        LcoeInputError: the F5 table is stale or has members the member list lacks, a cell is missing from the candidates or the
            forcing, or a sampled capacity factor would exceed 1 (V-03).
    """
    _assert_potential_matches(potential_path, resolved)
    potential = pd.read_parquet(
        potential_path, columns=["cell_id", "member", "P_MW", "CF", "E_MWh"]
    )
    candidates = pd.read_parquet(
        candidates_path, columns=["cell_id", "dist_grid_km", "dist_road_km"]
    )
    if candidates["cell_id"].duplicated().any():
        raise LcoeInputError(f"{candidates_path.name}: duplicated cell_id")
    candidate_index = pd.Index(candidates["cell_id"].to_numpy())
    dist_grid = candidates["dist_grid_km"].to_numpy(dtype="float64")
    dist_road = candidates["dist_road_km"].to_numpy(dtype="float64")
    forcing = pd.read_parquet(forcing_path, columns=["cell_id", "member", "dT"])
    p_codes, p_names = _member_codes(potential)
    f_codes, f_names = _member_codes(forcing)
    unknown = sorted(set(p_names) - set(known_members if known_members is not None else members))
    if unknown:
        raise LcoeInputError(
            f"{potential_path.name} has members not listed in members.yaml: {unknown}"
        )
    cell_id = potential["cell_id"].to_numpy(dtype="int64")
    p_mw = potential["P_MW"].to_numpy(dtype="float64")
    cf = potential["CF"].to_numpy(dtype="float64")
    e_mwh = potential["E_MWh"].to_numpy(dtype="float64")
    f_cell = forcing["cell_id"].to_numpy(dtype="int64")
    f_dt = forcing["dT"].to_numpy(dtype="float64")
    nominal_x = resolved.nominal[resolved.energy_key]
    for member in members:
        if member not in p_names:
            continue
        rows = np.flatnonzero(p_codes == p_names.index(member))
        rows = rows[np.argsort(cell_id[rows], kind="stable")]
        ids = cell_id[rows]
        if (np.diff(ids) == 0).any():
            raise LcoeInputError(f"{potential_path.name}: duplicated cell_id in member {member}")
        at = candidate_index.get_indexer(ids)
        if (at < 0).any():
            raise LcoeInputError(
                f"{potential_path.name}: {int((at < 0).sum())} cells of member {member} are not in {candidates_path.name}"
            )
        if member in f_names:
            f_rows = np.flatnonzero(f_codes == f_names.index(member))
            f_at = pd.Index(f_cell[f_rows]).get_indexer(ids)
        else:
            f_at = np.full(len(ids), -1)
        if (f_at < 0).any():
            raise LcoeInputError(
                f"forcing.parquet lacks {int((f_at < 0).sum())} cells of member {member} that F5 has rows for"
            )
        d_t = f_dt[f_rows][f_at]
        offset, slope = resolved.model.rescale_terms(nominal_x, d_t)
        cells = CellInputs(
            p_mw=p_mw[rows],
            dist_grid_km=dist_grid[at],
            dist_road_km=dist_road[at],
            energy_mwh=e_mwh[rows],
            energy_offset=offset,
            energy_slope=slope,
        )
        factor_max = np.maximum(offset + slope * x_range[0], offset + slope * x_range[1])
        if (cf[rows] * factor_max > CF_MAX).any():
            raise LcoeInputError(
                f"member {member}: a capacity factor above 1 under the sampled {resolved.energy_key} (V-03)"
            )
        yield MemberCells(member=member, cell_id=ids, cells=cells, cf=cf[rows])


def build_technology_lcoe(
    iso: str,
    resolved: ResolvedLcoe,
    *,
    potential_path: Path,
    candidates_path: Path,
    forcing_path: Path,
    members: Sequence[str],
    out_dir: Path,
    n_samples: int,
    seed: int,
    max_batch_gb: float,
    production: bool = False,
) -> TechLcoe:
    """Summary, design matrix and supply curve of one technology.

    Implements: M-F6-01, M-F6-02, M-F6-04, M-F6-05, M-F6-06.

    Raises:
        LcoeInputError: an input table breaks its contract.
        KernelInputError: a sample or cell is outside the domain of the kernel.
    """
    tech = resolved.technology
    design = build_design(resolved.specs, n_samples, seed)
    samples = samples_from_design(design, resolved.nominal, resolved.energy_key)
    nominal_samples, draw_samples = samples.take(slice(0, 1)), samples.take(slice(1, None))
    block_cells = cells_per_block(max_batch_gb, n_samples)
    x = samples.energy_parameter
    x_range = (float(x.min()), float(x.max()))
    out_dir = Path(out_dir)
    provenance = _provenance(resolved, n_samples, seed, block_cells, max_batch_gb, production)

    summary_path = out_dir / f"lcoe_summary_{tech}.parquet"
    supply_path = out_dir / f"supply_curve_{tech}.parquet"
    design_path = out_dir / f"design_matrix_{tech}.parquet"
    progress = PeriodicProgress(logger, len(members), f"{iso} {tech} LCOE members", every=5)
    n_rows = n_nonfinite_nominal = n_draw_nonfinite = 0
    seen_cells: set[int] = set()
    m0_nominal: np.ndarray | None = None
    with (
        TableWriter(
            summary_path,
            schema_version=LCOE_TABLE_SCHEMA_VERSION,
            row_model=LcoeSummaryRow,
            compression="zstd",
            extra_metadata=provenance,
            empty_frame=_empty_summary_frame(),
        ) as summary_writer,
        TableWriter(
            supply_path,
            schema_version=LCOE_TABLE_SCHEMA_VERSION,
            row_model=SupplyCurveRow,
            compression="zstd",
            extra_metadata=provenance,
            empty_frame=_empty_supply_frame(),
        ) as supply_writer,
    ):
        member_inputs = read_member_inputs(
            resolved,
            potential_path=potential_path,
            candidates_path=candidates_path,
            forcing_path=forcing_path,
            members=members,
            x_range=x_range,
        )
        for item in member_inputs:
            nominal_all = np.empty(len(item.cells))
            for window, nominal, stats in iter_member_summaries(
                item.cells, nominal_samples, draw_samples, block_cells
            ):
                _check_summary(stats, nominal, item.member)
                nominal_all[window] = nominal
                n_nonfinite_nominal += int((~np.isfinite(nominal)).sum())
                n_draw_nonfinite += int(stats.n_nonfinite.sum())
                summary_writer.write(
                    pd.DataFrame(
                        {
                            "cell_id": item.cell_id[window],
                            "member": np.full(
                                window.stop - window.start, item.member, dtype=object
                            ),
                            "lcoe_nominal": nominal,
                            "lcoe_mean": stats.mean,
                            "lcoe_var": stats.var,
                            "lcoe_p10": stats.p10,
                            "lcoe_p50": stats.p50,
                            "lcoe_p90": stats.p90,
                            "n_nonfinite": stats.n_nonfinite,
                        }
                    )
                )
            n_rows += len(item.cells)
            seen_cells.update(item.cell_id.tolist())
            supply_writer.write(
                supply_curve(
                    item.member,
                    item.cell_id,
                    nominal_all,
                    item.cells.p_mw,
                    item.cells.energy_mwh,
                )
            )
            if item.member == REFERENCE_MEMBER_ID:
                m0_nominal = nominal_all
            progress.step()
    write_table(
        design.reset_index(),
        design_path,
        schema_version=LCOE_TABLE_SCHEMA_VERSION,
        row_model=DesignMatrixRow,
        extra_metadata=provenance,
    )
    finite_m0 = m0_nominal[np.isfinite(m0_nominal)] if m0_nominal is not None else np.array([])
    result = TechLcoe(
        technology=tech,
        n_samples=n_samples,
        seed=seed,
        cells_per_block=block_cells,
        n_cells=len(seen_cells),
        n_members=len(members),
        n_rows=n_rows,
        n_nonfinite_nominal=n_nonfinite_nominal,
        n_draw_nonfinite=n_draw_nonfinite,
        lcoe_nominal_m0_min=float(finite_m0.min()) if finite_m0.size else None,
        lcoe_nominal_m0_median=float(np.median(finite_m0)) if finite_m0.size else None,
        lcoe_summary=summary_path,
        design_matrix=design_path,
        supply_curve=supply_path,
    )
    logger.info(
        "%s %s: %d cell-members, %d samples, %d cells per block, nominal LCOE at m0 min %s median %s USD/MWh, %d non-finite draws",
        iso,
        tech,
        n_rows,
        n_samples,
        block_cells,
        result.lcoe_nominal_m0_min,
        result.lcoe_nominal_m0_median,
        n_draw_nonfinite,
    )
    return result


def resolve_all(
    iso: str,
    technologies: TechnologiesFile,
    country_params: CountryParams,
    run_technologies: Sequence[str],
) -> dict[str, ResolvedLcoe]:
    """`resolve_technology_costs` for every technology of the run; one error lists the missing items of all of them."""
    failures: list[str] = []
    resolved: dict[str, ResolvedLcoe] = {}
    for tech in run_technologies:
        try:
            resolved[tech] = resolve_technology_costs(
                iso,
                tech,
                technologies.technologies[tech],
                getattr(country_params.technologies, tech),
            )
        except LcoeMissingInputError as exc:
            failures.extend(f"{tech}: {item}" for item in exc.missing)
    if failures:
        raise LcoeMissingInputError(iso, ", ".join(run_technologies), failures)
    return resolved


def read_member_ids(members_file: Path) -> list[str]:
    """Member identifiers of `members.yaml`, in its order."""
    return [
        m["member"] for m in yaml.safe_load(members_file.read_text(encoding="utf-8"))["members"]
    ]


def build_lcoe(
    iso: str,
    technologies: TechnologiesFile,
    country_params: CountryParams,
    run_technologies: Sequence[str],
    *,
    sampler_seed: int,
    sampler_size: int,
    max_batch_gb: float,
    production: bool = False,
    potential_dir: Path | None = None,
    candidates_dir: Path | None = None,
    climate_dir: Path | None = None,
    out_dir: Path | None = None,
) -> LcoeSummary:
    """F6 for `iso` and the technologies of the run, on the central land scenario and every member.

    Implements: M-F6-01 to M-F6-06.

    Raises:
        LcoeMissingInputError: any technology lacks a parameter, range or price year; raised before any input is read.
        FileNotFoundError: an F3, F4 or F5 input is absent.
    """
    resolved = resolve_all(iso, technologies, country_params, run_technologies)
    potential_dir = potential_dir or core_paths.phase_dir(iso, "technical_potential", "artifacts")
    candidates_dir = candidates_dir or core_paths.phase_dir(iso, "land_eligibility", "artifacts")
    climate_dir = climate_dir or core_paths.phase_dir(iso, "climate_forcing", "artifacts")
    out_dir = out_dir or lcoe_dir(iso)
    members_file = Path(climate_dir) / "members.yaml"
    forcing_path = Path(climate_dir) / "forcing.parquet"
    needed = [members_file, forcing_path]
    for tech in resolved:
        needed.append(Path(potential_dir) / f"potential_{tech}__central.parquet")
        needed.append(Path(candidates_dir) / f"candidates_{tech}__central.parquet")
    absent = [str(p) for p in needed if not p.is_file()]
    if absent:
        raise FileNotFoundError(f"F6 input missing (F3, F4 and F5 must have run): {absent}")
    members = read_member_ids(members_file)
    result = {
        tech: build_technology_lcoe(
            iso,
            res,
            potential_path=Path(potential_dir) / f"potential_{tech}__central.parquet",
            candidates_path=Path(candidates_dir) / f"candidates_{tech}__central.parquet",
            forcing_path=forcing_path,
            members=members,
            out_dir=Path(out_dir),
            n_samples=sampler_size,
            seed=sampler_seed,
            max_batch_gb=max_batch_gb,
            production=production,
        )
        for tech, res in resolved.items()
    }
    return LcoeSummary(country_code=iso, technologies=result)
