"""The exploratory phase: H5c, VUL, the V_f diagnostic and tau on the cell basis, from persisted artifacts (M-X-01 to M-X-05; DEC-098).

EXPLORATORY. It reads the tables of F5, F6 and F7 that the manifests register and nothing else: it imports no module of `lcoe_modeling` or
`robustness_analysis` (their code fingerprints do not move) and no kernel; every quantity it needs is already persisted (the nominal LCOE and the P90
of F6 per cell and member, the energy of F5, the classes, the V_f of each future and the target conversion of F7). The pre-registered results are not
touched and the tables it writes never feed T-R1 to T-R12.

Outputs, in `outputs/<ISO>/exploratory_analysis/artifacts/`, with `"exploratory": true` in the provenance of every table:
`h5c_curves_<tec>__<role>`, `h5c_summary_<tec>__<role>`, `vulnerability_<tec>__<role>`, `vulnerability_summary_<tec>__<role>` for the windows `core` and
`sensitivity`; `prim_vf_<tec>` (the core window, the one of PRIM) and `tau_cell_basis_<tec>`.
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

from geofrea.core import paths as core_paths
from geofrea.core.scale import active_scale
from geofrea.core.tables import write_table
from geofrea.exploratory_analysis import h5c, vulnerability
from geofrea.exploratory_analysis.table_schemas import (
    EXPLORATORY_TABLE_SCHEMA_VERSION,
    PROVENANCE_KEY,
    H5cCurveRow,
    H5cSummaryRow,
    StatisticRow,
    TauCellRow,
    VulnerabilityRow,
)

logger = logging.getLogger("geofrea.exploratory_analysis")

DECISION = "DEC-098"
IRENA_EDITION = "irena_rpgc_2024"
F7_SET = ("ranked", "climate_fragile")  # M-F7-01: the cells of the F7 set (H5's Omega keeps the climate-fragile ones)
PHASE = "exploratory_analysis"
BASES = ("nominal", "p90_envelope")
TABLE_KINDS = ("h5c_curves", "h5c_summary", "vulnerability", "vulnerability_summary")


class SkippedOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output: str
    reason: str


class TechExploratory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    technology: str
    tables: dict[str, Path]  # key (`h5c_curves__core`, `prim_vf`, ...) -> file
    skipped: list[SkippedOutput]


class ExploratorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    exploratory: bool = True
    technologies: dict[str, TechExploratory]


class ExploratoryInputError(RuntimeError):
    """An input artifact is missing or breaks its contract."""


def exploratory_dir(iso: str) -> Path:
    """`outputs/<ISO>/exploratory_analysis/artifacts`, and `exploratory_analysis__<scale id>` at another scale (A-08).

    The suffix is written here and not in `core.scale.SCALE_DEPENDENT_PHASES`: an edit of that module changes the code fingerprint of every phase
    (COMMAND 210 must not move any fingerprint of F1 to F7b); `phase_directory_name` leaves the name it is given as it is.
    """
    scale = active_scale()
    name = PHASE if scale.is_default else f"{PHASE}__{scale.scale_id}"
    path = core_paths.phase_dir(iso, name, "artifacts")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read(path: Path, columns: Sequence[str] | None = None) -> pd.DataFrame:
    if not Path(path).is_file():
        raise ExploratoryInputError(f"input artifact missing: {path}")
    return pd.read_parquet(path, columns=list(columns) if columns is not None else None)


def _provenance(tech: str, role: str | None, window: str | None, extra: Mapping[str, object]) -> dict[str, str]:
    body = {
        "exploratory": True,
        "decision": DECISION,
        "status": "exploratory: the pre-registered results of v1.0 are unchanged and are the primary results",
        "technology": tech,
        "window_role": role,
        "window": window,
        **extra,
    }
    return {PROVENANCE_KEY: json.dumps(body, sort_keys=True, default=str)}


def _round_json(value: Mapping[str, float]) -> str:
    return json.dumps({k: (None if not np.isfinite(v) else v) for k, v in value.items()}, sort_keys=True)


def _none(x: float | None) -> float | None:
    return None if x is None or not np.isfinite(x) else float(x)


class _Window:
    """The inputs of one technology and window role, over the F7 set: wide `(cells, members)` matrices with the reference member first."""

    def __init__(self, tech: str, role: str, robustness_dir: Path, lcoe_dir: Path, potential_dir: Path) -> None:
        rob_path = robustness_dir / f"robustness_{tech}__{role}.parquet"
        robustness = _read(rob_path)
        import pyarrow.parquet as pq

        meta = pq.read_schema(rob_path).metadata or {}
        provenance = json.loads(meta[b"geofrea_robustness_provenance"]) if b"geofrea_robustness_provenance" in meta else {}
        decision = provenance.get("decision", {})
        self.cf_min = decision.get("cf_min")
        self.tau_registered = decision.get("tau_lcoe_usd_per_mwh")
        if self.cf_min is None:
            raise ExploratoryInputError(f"{rob_path}: the provenance of F7 has no cf_min")
        self.robustness = robustness
        members = _read(robustness_dir / f"h5_members_{tech}__{role}.parquet", ["member", "gcm", "ssp"]).drop_duplicates("member").sort_values("member")
        self.core = list(members["member"])
        self.gcm_of = dict(zip(members["member"], members["gcm"], strict=True))
        self.ssp_of = dict(zip(members["member"], members["ssp"], strict=True))
        omega = robustness[robustness["cell_class"].isin(F7_SET)].sort_values("cell_id")
        self.omega = omega
        ids = omega["cell_id"].to_numpy("int64")
        self.cell_id = ids
        wanted = [h5c.REFERENCE_MEMBER, *self.core]
        nominal = _read(robustness_dir / f"nominal_lcoe_by_member_{tech}__{role}.parquet", ["cell_id", "member", "lcoe_nominal"])
        potential = _read(potential_dir / f"potential_{tech}__central.parquet", ["cell_id", "member", "CF", "E_MWh"])
        summary = _read(lcoe_dir / f"lcoe_summary_{tech}.parquet", ["cell_id", "member", "lcoe_p90"])

        def wide(frame: pd.DataFrame, column: str) -> np.ndarray:
            frame = frame[frame["cell_id"].isin(ids) & frame["member"].astype(str).isin(wanted)]
            frame = frame.assign(member=frame["member"].astype(str))
            return frame.pivot(index="cell_id", columns="member", values=column).reindex(index=ids, columns=wanted).to_numpy("float64")

        self.members = wanted
        cf = wide(potential, "CF")
        self.energy_twh = wide(potential, "E_MWh") / 1.0e6
        feasible = np.isfinite(cf) & (cf >= self.cf_min)
        self.nominal = np.where(feasible, wide(nominal, "lcoe_nominal"), np.nan)
        self.p90 = np.where(feasible, wide(summary, "lcoe_p90"), np.nan)
        # the cell-members of a cell that is feasible at f0 but not in a member: the climate-fragile class, NaN above
        self.total_m0_twh = float(np.nansum(self.energy_twh[:, 0]))


def _h5c_tables(win: _Window, g_target: float | None, g_target_h5: float | None = None, above_capacity: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    inventory = h5c.levels(g_target, win.total_m0_twh)
    curve_rows: list[pd.DataFrame] = []
    summary_rows: list[dict] = []
    for basis, matrix in (("nominal", win.nominal), ("p90_envelope", win.p90)):
        curves = {
            member: h5c.cost_curve(win.cell_id, matrix[:, j], win.energy_twh[:, j]) for j, member in enumerate(win.members)
        }
        for level, g in inventory:
            rows = h5c.member_rows(curves, win.gcm_of, win.ssp_of, g)
            reference = {
                "member": h5c.REFERENCE_MEMBER,
                "gcm": None,
                "ssp": None,
                "mc": h5c.marginal_cost(curves[h5c.REFERENCE_MEMBER], g),
                "ac": h5c.average_cost(curves[h5c.REFERENCE_MEMBER], g),
            }
            unreachable_reference = not np.isfinite(reference["mc"])
            reference.update({"d_mc": 0.0 if not unreachable_reference else float("nan"), "d_ac": 0.0 if not unreachable_reference else float("nan"), "level_unreachable": unreachable_reference})
            block = pd.concat([pd.DataFrame([reference]), rows], ignore_index=True)
            block.insert(0, "g_twh", g)
            block.insert(0, "level", level)
            block.insert(0, "basis", basis)
            curve_rows.append(block)
            mc = h5c.pressure(rows, "mc")
            ac = h5c.pressure(rows, "ac")
            summary_rows.append(
                {
                    "basis": basis,
                    "level": level,
                    "g_twh": g,
                    "g_share_of_total_m0": _none(g / win.total_m0_twh) if win.total_m0_twh > 0 else None,
                    "g_target_h5_twh": g_target_h5 if level == h5c.LEVEL_TARGET else None,
                    "target_above_set_capacity": bool(above_capacity) if level == h5c.LEVEL_TARGET else False,
                    "mc_m0": _none(reference["mc"]),
                    "ac_m0": _none(reference["ac"]),
                    "reference_unreachable": bool(unreachable_reference),
                    "n_core_members": len(rows),
                    "n_unreachable_members": int(rows["level_unreachable"].sum()),
                    "delta_mc_max": _none(mc["delta_mc_max"]),
                    "delta_mc_member": mc["delta_mc_member"],
                    "delta_mc_ssp": mc["delta_mc_ssp"],
                    "delta_mc_median": _none(mc["delta_mc_median"]),
                    "delta_mc_by_ssp": _round_json(mc["delta_mc_by_ssp"]),
                    "delta_ac_max": _none(ac["delta_ac_max"]),
                    "delta_ac_member": ac["delta_ac_member"],
                    "delta_ac_ssp": ac["delta_ac_ssp"],
                    "delta_ac_median": _none(ac["delta_ac_median"]),
                    "delta_ac_by_ssp": _round_json(ac["delta_ac_by_ssp"]),
                    "label": h5c.label_for(level, mc["delta_mc_max"]) if basis == "nominal" else None,
                }
            )
    curves_frame = pd.concat(curve_rows, ignore_index=True) if curve_rows else pd.DataFrame(columns=list(H5cCurveRow.model_fields))
    for column in ("mc", "ac", "d_mc", "d_ac"):
        curves_frame[column] = curves_frame[column].astype("float64")
    return curves_frame, pd.DataFrame(summary_rows, columns=list(H5cSummaryRow.model_fields))


def _vulnerability_tables(win: _Window) -> tuple[pd.DataFrame, pd.DataFrame]:
    omega = win.omega.reset_index(drop=True)
    core_columns = list(range(1, len(win.members)))
    index = vulnerability.vul_indices(
        win.nominal[:, 0], win.nominal[:, core_columns], win.p90[:, 0], win.p90[:, core_columns]
    )
    ranked = (omega["cell_class"] == "ranked").to_numpy()
    for name in index:  # the climate-fragile cells are reported apart: no index
        index[name] = np.where(ranked, index[name], np.nan)
    vul_clim = index["vul_clim"]
    finite = np.isfinite(vul_clim)
    cut = float(np.quantile(vul_clim[finite], vulnerability.QUARTILE)) if finite.any() else float("nan")
    upper = np.where(finite, vul_clim >= cut, False)
    quadrants = vulnerability.quadrant_capacity(win.nominal[:, 0], vul_clim, omega["p_mw"].to_numpy("float64"))
    label = np.full(len(omega), None, dtype=object)
    if "median_lcoe" in quadrants:
        high_l = win.nominal[:, 0] > quadrants["median_lcoe"]
        high_v = vul_clim > quadrants["median_vul_clim"]
        label = np.where(finite, np.char.add(np.where(high_l, "high", "low").astype(str), np.char.add("_lcoe_", np.char.add(np.where(high_v, "high", "low").astype(str), "_vul"))), None)
    table = pd.DataFrame(
        {
            "cell_id": omega["cell_id"].astype("int64"),
            "cell_class": omega["cell_class"],
            "lat_c": omega["lat_c"],
            "lon_c": omega["lon_c"],
            "p_mw": omega["p_mw"],
            "lcoe_f0": win.nominal[:, 0],
            "mr": omega["mr"],
            "topk_nominal": omega["topk_nominal"],
            "n_failing_members": omega["n_failing_members"].astype("int64"),
            "vul_clim": vul_clim,
            "vul_tec": index["vul_tec"],
            "vul": index["vul"],
            "vul_clim_upper_quartile": pd.array(np.where(finite, upper, None), dtype="boolean"),
            "quadrant": label,
        }
    )
    rows: list[dict] = []

    def add(group: str, statistic: str, value: float | None, text: str | None = None) -> None:
        rows.append({"group": group, "statistic": statistic, "value": _none(value), "text": text})

    p_mw = omega["p_mw"].to_numpy("float64")
    mr = omega["mr"].to_numpy("float64")
    f0 = win.nominal[:, 0]
    for name, values in index.items():
        for statistic, value in vulnerability.distribution(values[ranked]).items():
            add(f"distribution_{name}", statistic, value)
        add("spearman", f"{name}_with_lcoe_f0", vulnerability.spearman(values[ranked], f0[ranked]))
        add("spearman", f"{name}_with_mr", vulnerability.spearman(values[ranked], mr[ranked]))
    topk = omega["topk_nominal"].fillna(False).to_numpy(dtype=bool) & ranked
    share, n_top = vulnerability.top_share_in_upper_quartile(vul_clim, topk)
    add("top_k_nominal", "share_in_upper_quartile_of_vul_clim", share)
    add("top_k_nominal", "n_cells_with_vul_clim", float(n_top))
    add("upper_quartile", "vul_clim_cut", cut)
    for name, value in quadrants.items():
        add("quadrant_capacity_mw" if name.endswith("_vul") else "quadrant_medians", name, value)
    fragile = ~ranked
    add("climate_fragile", "n_cells", float(fragile.sum()))
    add("climate_fragile", "capacity_mw", float(np.nansum(p_mw[fragile])))
    add("note", "vul_tec_is_mostly_common_to_the_country", None, "VUL_tec varies little between cells (COMMAND 202); read its spread in distribution_vul_tec")
    return table, pd.DataFrame(rows, columns=list(StatisticRow.model_fields))


def _target_energy(robustness_dir: Path, tech: str, role: str, win: _Window) -> tuple[float | None, float | None, bool]:
    """`(G_target, G_target_h5, target_above_set_capacity)`; `G_target` has no cost threshold (DEC-100), `G_target_h5` is the conversion of H5 (M-F7-07), for comparison.

    Both are None when the primary H5 variant has no target in GW (a target in another unit has no registered conversion to capacity).
    """
    table = _read(robustness_dir / f"h5_summary_{tech}__{role}.parquet", ["primary", "g_twh", "target_value", "target_unit"])
    primary = table[table["primary"].astype(bool)]
    if primary.empty or pd.isna(primary["g_twh"].iloc[0]) or str(primary["target_unit"].iloc[0]) != "GW" or pd.isna(primary["target_value"].iloc[0]):
        return None, None, False
    g, above = h5c.target_energy(win.cell_id, win.nominal[:, 0], win.energy_twh[:, 0], win.omega["p_mw"].to_numpy("float64"), float(primary["target_value"].iloc[0]))
    return g, float(primary["g_twh"].iloc[0]), above


def _prim_table(robustness_dir: Path, tech: str, theta: float) -> pd.DataFrame:
    futures = _read(robustness_dir / f"futures_{tech}__core.parquet", ["displaced_capacity_share"])
    stats = vulnerability.vf_distribution(futures["displaced_capacity_share"].to_numpy("float64"), theta)
    return pd.DataFrame(
        [{"group": "v_f", "statistic": k, "value": _none(v), "text": None} for k, v in stats.items()], columns=list(StatisticRow.model_fields)
    )


def _tau_table(
    iso: str, tech: str, irena_yaml: Path, lcoe_dir: Path, win: _Window
) -> pd.DataFrame:
    document = yaml.safe_load(Path(irena_yaml).read_text(encoding="utf-8"))
    edition = document["editions"][IRENA_EDITION]
    pair = edition["pairs"][iso][tech]
    life_irena = (edition.get("life_years") or {}).get("value")
    fields = {k: (pair.get(k) or {}).get("value") for k in ("tic_usd_per_kw", "cf", "om_usd_per_kw_yr")}
    absent = [k for k, v in {**fields, "life_years": life_irena}.items() if v is None]
    if absent:
        raise ExploratoryInputError(f"irena_reference: {iso} {tech} has null fields {absent}")
    design = _read(lcoe_dir / f"design_matrix_{tech}.parquet")
    s0 = design[design["sample"] == 0].iloc[0]
    values = vulnerability.tau_cell_basis(
        float(fields["tic_usd_per_kw"]),
        float(fields["cf"]),
        float(fields["om_usd_per_kw_yr"]),
        float(life_irena),
        float(s0["capex_usd_per_kw"]),
        float(s0["opex_fixed_frac"]),
        float(s0["lifetime_years"]),
        float(s0["discount_rate"]),
    )
    f0 = win.nominal[:, 0]
    p_mw = win.omega["p_mw"].to_numpy("float64")
    n_cell, cap_cell = vulnerability.capacity_at_or_below(f0, p_mw, values["tau_cell_basis"])
    registered = None if win.tau_registered is None else float(win.tau_registered)
    n_reg, cap_reg = (None, None) if registered is None else vulnerability.capacity_at_or_below(f0, p_mw, registered)
    row = {
        "tau_registered": registered,
        "tau_reference": values["tau_reference"],
        "tau_life_only": values["tau_life_only"],
        "tau_om_only": values["tau_om_only"],
        "tau_cell_basis": values["tau_cell_basis"],
        "tau_difference_reference": None if registered is None else values["tau_reference"] - registered,
        "tic_usd_per_kw": float(fields["tic_usd_per_kw"]),
        "cf_reference": float(fields["cf"]),
        "om_irena_usd_per_kw_yr": values["om_irena_usd_per_kw_yr"],
        "om_f6_usd_per_kw_yr": values["om_f6_usd_per_kw_yr"],
        "life_irena_years": float(life_irena),
        "life_f6_years": float(s0["lifetime_years"]),
        "discount_rate": float(s0["discount_rate"]),
        "capex_f6_usd_per_kw": float(s0["capex_usd_per_kw"]),
        "opex_fixed_frac_f6": float(s0["opex_fixed_frac"]),
        "n_cells_f7_set": len(f0),
        "capacity_gw_f7_set": float(np.nansum(p_mw) / 1000.0),
        "n_cells_below_registered": n_reg,
        "capacity_gw_below_registered": None if cap_reg is None else cap_reg / 1000.0,
        "n_cells_below_cell_basis": n_cell,
        "capacity_gw_below_cell_basis": cap_cell / 1000.0,
    }
    return pd.DataFrame([row], columns=list(TauCellRow.model_fields))


def build_exploratory(
    iso: str,
    technologies: Sequence[str],
    windows: Mapping[str, str],
    *,
    irena_reference_yaml: Path,
    outcome_threshold: float | None,
    potential_dir: Path | None = None,
    lcoe_dir: Path | None = None,
    robustness_dir: Path | None = None,
    out_dir: Path | None = None,
) -> ExploratorySummary:
    """Write the exploratory tables of `iso` for each technology and window role (`windows`: role -> label, `core` and `sensitivity`).

    Implements: M-X-01 to M-X-05 (DEC-098).

    Raises:
        ExploratoryInputError: an input artifact is missing.
    """
    potential_dir = Path(potential_dir) if potential_dir else core_paths.phase_dir(iso, "technical_potential", "artifacts")
    lcoe_dir = Path(lcoe_dir) if lcoe_dir else core_paths.phase_dir(iso, "lcoe_modeling", "artifacts")
    robustness_dir = Path(robustness_dir) if robustness_dir else core_paths.phase_dir(iso, "robustness_analysis", "artifacts")
    out = Path(out_dir) if out_dir else exploratory_dir(iso)
    out.mkdir(parents=True, exist_ok=True)
    result: dict[str, TechExploratory] = {}
    for tech in technologies:
        tables: dict[str, Path] = {}
        skipped: list[SkippedOutput] = []
        core_window: _Window | None = None
        for role, label in windows.items():
            win = _Window(tech, role, robustness_dir, lcoe_dir, potential_dir)
            if role == "core":
                core_window = win
            g_target, g_target_h5, above = _target_energy(robustness_dir, tech, role, win)
            extra = {
                "cf_min": win.cf_min,
                "n_cells_f7_set": len(win.cell_id),
                "energy_total_m0_twh": win.total_m0_twh,
                "g_target_twh": g_target,
                "g_target_h5_twh": g_target_h5,
                "target_above_set_capacity": above,
                "p_levels": list(h5c.P_LEVELS),
                "domain": "F7 set of the central land scenario (ranked and climate-fragile cells)",
            }
            curves, summary = _h5c_tables(win, g_target, g_target_h5, above)
            vul, vul_summary = _vulnerability_tables(win)
            for kind, frame, model in (
                ("h5c_curves", curves, H5cCurveRow),
                ("h5c_summary", summary, H5cSummaryRow),
                ("vulnerability", vul, VulnerabilityRow),
                ("vulnerability_summary", vul_summary, StatisticRow),
            ):
                path = out / f"{kind}_{tech}__{role}.parquet"
                write_table(
                    frame, path, schema_version=EXPLORATORY_TABLE_SCHEMA_VERSION, row_model=model,
                    extra_metadata=_provenance(tech, role, label, {**extra, "table": kind}),
                )  # fmt: skip
                tables[f"{kind}__{role}"] = path
            if g_target is None:
                skipped.append(SkippedOutput(output=f"h5c level target [{role}]", reason="the primary H5 variant of F7 has no national target in GW"))
        if outcome_threshold is None:
            skipped.append(SkippedOutput(output="prim_vf", reason="prim.outcome_threshold is null"))
        else:
            path = out / f"prim_vf_{tech}.parquet"
            write_table(
                _prim_table(robustness_dir, tech, outcome_threshold), path, schema_version=EXPLORATORY_TABLE_SCHEMA_VERSION, row_model=StatisticRow,
                extra_metadata=_provenance(tech, "core", windows.get("core"), {"theta": outcome_threshold, "table": "prim_vf"}),
            )  # fmt: skip
            tables["prim_vf"] = path
        try:
            assert core_window is not None
            tau = _tau_table(iso, tech, irena_reference_yaml, lcoe_dir, core_window)
        except (ExploratoryInputError, KeyError, AssertionError) as exc:
            skipped.append(SkippedOutput(output="tau_cell_basis", reason=str(exc) or "no core window"))
        else:
            path = out / f"tau_cell_basis_{tech}.parquet"
            write_table(
                tau, path, schema_version=EXPLORATORY_TABLE_SCHEMA_VERSION, row_model=TauCellRow,
                extra_metadata=_provenance(tech, "core", windows.get("core"), {"table": "tau_cell_basis", "irena_edition": IRENA_EDITION}),
            )  # fmt: skip
            tables["tau_cell_basis"] = path
        for item in skipped:
            logger.warning("%s %s: skipped %s: %s", iso, tech, item.output, item.reason)
        result[tech] = TechExploratory(technology=tech, tables=tables, skipped=skipped)
    return ExploratorySummary(country_code=iso, technologies=result)
