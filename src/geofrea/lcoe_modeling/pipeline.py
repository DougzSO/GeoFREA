"""F6 lcoe_modeling end to end for one country: LCOE summaries, design matrix and nominal supply curves per technology.

Reads, per technology, `potential_<tech>__central.parquet` (F5), `candidates_<tech>__central.parquet` (F3: the real distances),
`forcing.parquet` and `members.yaml` (F4); writes under `outputs/<ISO3>/lcoe_modeling/artifacts/`:

  - `lcoe_summary_<tech>.parquet`: per (cell, member), the nominal LCOE and the mean, variance, p10, p50 and p90 over the draws (M-F6-04);
  - `design_matrix_<tech>.parquet`: the Latin hypercube design, sample 0 the nominal vector (M-F6-02, M-F6-06);
  - `supply_curve_<tech>.parquet`: per member, the cells in increasing nominal LCOE with cumulative capacity and energy (M-F6-06);
  - `lcoe_nominal_<tech>__<scenario>.parquet`, for the restrictive and permissive land scenarios: the nominal LCOE per cell and member, no
    draws (M-F6-06, D-F6-018).

Nothing is read before every parameter, range and price year is checked: a missing one raises `LcoeMissingInputError` listing all of them
(A-09). Members are the outer loop and cells are processed in blocks that hold every sample, so the quantiles are exact and the memory
stays under `memory.max_batch_gb` (A-10, D-F6-002, D-F6-005). No sample-level array is ever written. See docs/phases/F6_lcoe_modeling.md
D-F6-001 to D-F6-016.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID
from geofrea.core import paths as core_paths
from geofrea.core.config_schemas import TechnologiesFile
from geofrea.core.constants import PRICE_BASE_YEAR_USD
from geofrea.core.run_logging import PeriodicProgress
from geofrea.core.schemas import CountryParams
from geofrea.core.tables import TableWriter, write_table
from geofrea.land_eligibility.scenarios import LAND_SCENARIOS
from geofrea.lcoe_modeling.design import build_design, samples_from_design
from geofrea.lcoe_modeling.inputs import (
    LcoeInputError,
    ResolvedLcoe,
    cells_per_block,
    read_member_ids,
    read_member_inputs,
    resolve_all,
)
from geofrea.lcoe_modeling.kernel import (
    KERNEL_VERSION,
    CellInputs,
    SampleInputs,
    lcoe_block,
)
from geofrea.lcoe_modeling.summary import QUANTILES, BlockSummary, summarize_draws
from geofrea.lcoe_modeling.supply_curve import supply_curve
from geofrea.lcoe_modeling.table_schemas import (
    LCOE_TABLE_SCHEMA_VERSION,
    DesignMatrixRow,
    LcoeNominalRow,
    LcoeSummaryRow,
    SupplyCurveRow,
)

logger = logging.getLogger("geofrea.lcoe_modeling.pipeline")

PROVENANCE_KEY = "geofrea_lcoe_provenance"
CENTRAL_SCENARIO = LAND_SCENARIOS[0]
OTHER_SCENARIOS = LAND_SCENARIOS[1:]  # nominal LCOE only (D-F6-018)


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
    lcoe_nominal_scenarios: dict[str, Path]


class LcoeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    technologies: dict[str, TechLcoe]


def lcoe_dir(iso: str) -> Path:
    path = core_paths.phase_dir(iso, "lcoe_modeling", "artifacts")
    path.mkdir(parents=True, exist_ok=True)
    return path


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


def build_scenario_nominal(
    resolved: ResolvedLcoe,
    nominal_samples: SampleInputs,
    x_range: tuple[float, float],
    *,
    potential_path: Path,
    candidates_path: Path,
    forcing_path: Path,
    members: Sequence[str],
    out_path: Path,
    provenance: dict[str, str],
) -> Path:
    """The nominal LCOE per cell and member of one land scenario, with no draws.

    Implements: M-F6-06, D-F6-018.

    Raises:
        LcoeInputError: an input table breaks its contract (as for the central scenario).
    """
    with TableWriter(
        out_path,
        schema_version=LCOE_TABLE_SCHEMA_VERSION,
        row_model=LcoeNominalRow,
        compression="zstd",
        extra_metadata=provenance,
        empty_frame=pd.DataFrame(
            {
                "cell_id": pd.Series(dtype="int64"),
                "member": pd.Series(dtype="object"),
                "lcoe_nominal": pd.Series(dtype="float64"),
            }
        ),
    ) as writer:
        for item in read_member_inputs(
            resolved,
            potential_path=potential_path,
            candidates_path=candidates_path,
            forcing_path=forcing_path,
            members=members,
            x_range=x_range,
        ):
            writer.write(
                pd.DataFrame(
                    {
                        "cell_id": item.cell_id,
                        "member": np.full(len(item.cell_id), item.member, dtype=object),
                        "lcoe_nominal": lcoe_block(item.cells, nominal_samples)[:, 0],
                    }
                )
            )
    return out_path


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
    other_scenarios: Mapping[str, tuple[Path, Path]] | None = None,
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
    scenario_tables = {
        scenario: build_scenario_nominal(
            resolved,
            nominal_samples,
            x_range,
            potential_path=potential,
            candidates_path=candidates,
            forcing_path=forcing_path,
            members=members,
            out_path=out_dir / f"lcoe_nominal_{tech}__{scenario}.parquet",
            provenance=provenance,
        )
        for scenario, (potential, candidates) in (other_scenarios or {}).items()
    }
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
        lcoe_nominal_scenarios=scenario_tables,
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
        for scenario in (CENTRAL_SCENARIO, *OTHER_SCENARIOS):
            needed.append(Path(potential_dir) / f"potential_{tech}__{scenario}.parquet")
            needed.append(Path(candidates_dir) / f"candidates_{tech}__{scenario}.parquet")
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
            other_scenarios={
                scenario: (
                    Path(potential_dir) / f"potential_{tech}__{scenario}.parquet",
                    Path(candidates_dir) / f"candidates_{tech}__{scenario}.parquet",
                )
                for scenario in OTHER_SCENARIOS
            },
        )
        for tech, res in resolved.items()
    }
    return LcoeSummary(country_code=iso, technologies=result)
