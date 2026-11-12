"""Inputs of the LCOE kernel: the resolution of parameters, ranges and price years, and the readers of the F3, F4 and F5 tables.

Shared by F6 (`pipeline.py`) and F7 (`pipeline.py`, `convergence.py`): neither phase imports the other's pipeline (D-F7-026). Nothing here writes a table.

Implements: M-F6-01, M-F6-02, A-09, A-10. See docs/phases/F6_lcoe_modeling.md D-F6-005, D-F6-008, D-F6-010, D-F6-016.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import yaml

from geofrea.core.config_schemas import TechnologiesFile, TechnologyConfig
from geofrea.core.constants import PRICE_BASE_YEAR_USD
from geofrea.core.paths import data_root
from geofrea.core.schemas import ConnectionParams, CountryParams
from geofrea.core.tables import require_schema_version
from geofrea.lcoe_modeling.connection import (
    SAMPLED_KEYS,
    ConversionError,
    Group3,
    group3_problems,
    load_conversion_indices,
    resolve_group3,
)
from geofrea.lcoe_modeling.kernel import KERNEL_PARAMETER_KEYS, CellInputs
from geofrea.lcoe_modeling.sampling import UncertainSpec
from geofrea.technical_potential.cf_models import CfModel, CfModelError, get_cf_model
from geofrea.technical_potential.pipeline import PROVENANCE_KEY as POTENTIAL_PROVENANCE_KEY
from geofrea.technical_potential.table_schemas import POTENTIAL_TABLE_SCHEMA_VERSION

LIVE_BLOCKS = 4  # live cell-by-sample arrays at the peak (D-F6-005)


BYTES_PER_VALUE = 8


CF_MAX = 1.0 + 1e-9  # V-03: a sampled capacity factor may not exceed 1 (rounding slack only)


# the parameters of M-F6-01 that are costs in USD and so carry a price year (S-07, D-F6-008)
COST_PRICE_KEYS = (
    "capex_usd_per_kw",
    "opex_var_usd_per_mwh",
)
# the parameters of M-F6-01 that come from the technology block of parameters.json; Group 3 provides the others (`connection.py`)
TECHNOLOGY_KEYS = (
    "capex_usd_per_kw",
    "opex_fixed_frac",
    "opex_var_usd_per_mwh",
    "lifetime_years",
    "discount_rate",
)
GROUP3_FIXED_KEYS = ("reference_project_mw", "transmission_loss_per_km")


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


@dataclass(frozen=True)
class ResolvedLcoe:
    """A technology whose F6 parameters, ranges and price years were all found: ready to compute."""

    technology: str
    cf_model_name: str
    model: CfModel
    energy_key: str
    nominal: Mapping[str, float]  # every kernel key and the energy key
    specs: tuple[UncertainSpec, ...]  # the uncertain parameters, in registry order
    group3: Group3 | None = None  # the connection and degradation values of Group 3, with the costs in 2024 USD


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
    if key == "degradation_weight" and (low < 0 or high > 1):
        return "degradation weight outside [0, 1]"
    if (
        key in COST_PRICE_KEYS
        or key in ("opex_fixed_frac", "line_cost_usd_per_km", "bay_cost_usd", "road_cost_usd_per_km")
    ) and low < 0:
        return "negative cost"
    return None


def resolve_technology_costs(
    iso: str,
    technology: str,
    tech_cfg: TechnologyConfig,
    tech_params: object,
    connection: ConnectionParams | None = None,
) -> ResolvedLcoe:
    """Check every F6 input of a technology and gather them; raise `LcoeMissingInputError` listing what is absent.

    Implements: M-F6-01, M-F6-02, M-F6-08, D-F6-008, D-F6-010, D-F6-016.

    A parameter is missing when it has no entry or no value, an uncertain one also when it has no range or a range outside the
    domain of the kernel, and a cost when its price year is not the base year (S-07). The Group 3 values (connection costs, tortuosity,
    degradation) come from `connection` and the technology block, and are checked by `group3_problems`: a cost still `to_be_sourced`
    (OQ-001), a null price year, a missing conversion index or a missing zone table each refuse the run.

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
    for key in (*TECHNOLOGY_KEYS, energy_key):
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

    group3: Group3 | None = None
    problems = group3_problems(iso, technology, connection, tech_params)
    missing.extend(problems)
    if not problems:
        try:
            try:
                indices = load_conversion_indices(
                    data_root() / connection.conversion_indices_path, iso
                )
            except ConversionError:
                indices = None  # needed only by a cost that is not 2024 USD: `resolve_group3` then names what is missing
            group3 = resolve_group3(iso, technology, connection, tech_params, indices)
        except ConversionError as exc:
            missing.append(f"conversion to 2024 USD ({exc})")
    if group3 is not None:
        for key in (*SAMPLED_KEYS, *GROUP3_FIXED_KEYS):
            nominal[key] = group3.nominal[key]
        for key in SAMPLED_KEYS:
            if key not in uncertain:
                continue
            low, high, distribution = group3.ranges[key]
            problem = _range_problem(key, low, high)
            if problem is not None:
                missing.append(f"{key} range [{low}, {high}] ({problem})")
            else:
                specs[key] = UncertainSpec(key, group3.nominal[key], low, high, distribution)
    if missing:
        raise LcoeMissingInputError(iso, technology, missing)
    return ResolvedLcoe(
        technology=technology,
        cf_model_name=tech_cfg.cf_model,
        model=model,
        energy_key=energy_key,
        nominal=nominal,
        specs=tuple(specs[k] for k in tech_cfg.uncertain_parameters),
        group3=group3,
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
    n_excluded: int = 0  # cell-members left out because the distance or the thermal zone is missing (Group 3)


def _no_substation_note(candidates_path: Path) -> str | None:
    """Why `dist_sub_km` cannot exist when the cause is a country with no eligible substation (`poi_counts.json` of F2a), else None (OQ-086, L-069)."""
    for parent in candidates_path.parents:
        counts_file = parent / "grid_alignment" / "artifacts" / "poi_counts.json"
        if not counts_file.is_file():
            continue
        try:
            counts = json.loads(counts_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if counts.get("eligible") != 0:
            return None
        return (
            f"the country has no eligible substation (poi_counts.json: {counts.get('total', '?')} found, {counts.get('excluded_no_voltage', '?')} without a voltage, "
            "0 eligible), so the layer `poi` and the distance `dist_sub_km` do not exist and the connection cost has no substation to be measured to; "
            "this is not a stale table: a country with no eligible substation is refused by design, with no fallback (OQ-086, L-069)"
        )
    return None


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
    available = set(pq.read_schema(candidates_path).names)
    absent = [c for c in ("dist_sub_km", "dist_road_km") if c not in available]
    if absent:
        no_substation = _no_substation_note(candidates_path)
        if no_substation is not None:
            raise LcoeInputError(f"{candidates_path.name} lacks {absent}: {no_substation}")
        raise LcoeInputError(
            f"{candidates_path.name} lacks {absent}: F2a, F2b and F3 must run again with the Group 3 layers (COMMAND 83)"
        )
    candidates = pd.read_parquet(
        candidates_path,
        columns=["cell_id", "dist_sub_km", "dist_road_km"]
        + (["pvcz_zone"] if "pvcz_zone" in available else []),
    )
    if candidates["cell_id"].duplicated().any():
        raise LcoeInputError(f"{candidates_path.name}: duplicated cell_id")
    candidate_index = pd.Index(candidates["cell_id"].to_numpy())
    dist_sub = candidates["dist_sub_km"].to_numpy(dtype="float64")
    dist_road = candidates["dist_road_km"].to_numpy(dtype="float64")
    # a cell with no distance, or (PV) no thermal zone, has no LCOE: it is left out and counted, never given a zero cost (Group 3)
    d_low, d_high, has_bounds = resolved.group3.degradation.bounds_for_cells(
        candidates["pvcz_zone"].to_numpy() if "pvcz_zone" in candidates else None, len(candidates)
    )
    usable = np.isfinite(dist_sub) & np.isfinite(dist_road) & has_bounds
    forcing = pd.read_parquet(forcing_path, columns=["cell_id", "member", "dT"])
    p_codes, p_names = _member_codes(potential)
    f_codes, f_names = _member_codes(forcing)
    observed = {
        p_names[code] for code in np.unique(p_codes)
    }  # a category with no row (a member of another technology) is not a member of the table
    unknown = sorted(observed - set(known_members if known_members is not None else members))
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
        if (at >= 0).any() and not usable[at[at >= 0]].all():
            keep = (at < 0) | usable[np.where(at < 0, 0, at)]
            n_excluded = int((~keep).sum())
            rows, ids, at = rows[keep], ids[keep], at[keep]
        else:
            n_excluded = 0
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
            dist_sub_km=dist_sub[at],
            dist_road_km=dist_road[at],
            energy_mwh=e_mwh[rows],
            energy_offset=offset,
            energy_slope=slope,
            degradation_low=d_low[at],
            degradation_high=d_high[at],
        )
        factor_max = np.maximum(offset + slope * x_range[0], offset + slope * x_range[1])
        if (cf[rows] * factor_max > CF_MAX).any():
            raise LcoeInputError(
                f"member {member}: a capacity factor above 1 under the sampled {resolved.energy_key} (V-03)"
            )
        yield MemberCells(
            member=member, cell_id=ids, cells=cells, cf=cf[rows], n_excluded=n_excluded
        )


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
                country_params.connection,
            )
        except LcoeMissingInputError as exc:
            failures.extend(f"{tech}: {item}" for item in exc.missing)
    if failures:
        raise LcoeMissingInputError(iso, ", ".join(run_technologies), failures)
    return resolved


def read_member_ids(members_file: Path, required_channels: Sequence[str] = ()) -> list[str]:
    """Member identifiers of `members.yaml`, in its order; with `required_channels` only the members that declare every one of them.

    A member whose entry declares no channels carries every channel (an old `members.yaml`). Implements: M-F4-06.
    """
    return [
        m["member"]
        for m in yaml.safe_load(members_file.read_text(encoding="utf-8"))["members"]
        if all(m.get("channels", {}).get(c, True) for c in required_channels)
    ]
