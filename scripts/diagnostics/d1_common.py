"""Funcoes comuns dos diagnosticos D1 a D5 (COMANDO 201). Somente leitura: nada e gravado em GeoFREA_data/outputs.

Reconstroi, para um par pais-tecnologia, a tabela por celula do F6 (membro de referencia m0, cenario central, amostra nominal) com os
insumos do kernel e confere que o LCOE reconstruido e o gravado pelo F6 (lcoe_summary). Importa o kernel e os leitores do F6; nenhuma fase roda.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

REPO = Path(r"D:\Douglas\DOUTORADO\GeoFREA")
DATA = Path(r"D:\Douglas\DOUTORADO\GeoFREA_data")
OUT = Path(r"D:\Douglas\DOUTORADO\_notas_geofrea\diagnostico_v1_0")
sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("GEOFREA_DATA_DIR", str(DATA))

from geofrea.core.config_loader import load_experiments, load_parameters, load_technologies  # noqa: E402
from geofrea.lcoe_modeling.design import build_design, samples_from_design  # noqa: E402
from geofrea.lcoe_modeling.inputs import resolve_all  # noqa: E402
from geofrea.lcoe_modeling.kernel import (  # noqa: E402
    CellInputs,
    SampleInputs,
    annuity_factor,
    energy_annuity_factor,
    lcoe_block,
)

PAIRS = [("PRT", "solar"), ("PRT", "wind"), ("IND", "solar"), ("IND", "wind"), ("BRA", "solar"), ("BRA", "wind")]
HOURS = 8760.0


def paths(iso: str) -> dict[str, Path]:
    o = DATA / "outputs" / iso
    return {
        "potential": o / "technical_potential" / "artifacts",
        "candidates": o / "land_eligibility" / "artifacts",
        "climate": o / "climate_forcing" / "artifacts",
        "lcoe": o / "lcoe_modeling" / "artifacts",
        "rob": o / "robustness_analysis" / "artifacts",
    }


def config(iso: str, tech: str):
    """`resolved`, the design matrix and the nominal sample of the pair, as F6 builds them."""
    params = load_parameters(REPO / "config" / "parameters.json")
    techs = load_technologies(REPO / "config" / "technologies.yaml")
    sampler = load_experiments(REPO / "config" / "experiments.yaml").sampler
    resolved = resolve_all(iso, techs, params.countries[iso], [tech])[tech]
    design = build_design(resolved.specs, sampler.adopted_size, sampler.seed)
    samples = samples_from_design(design, resolved.nominal, resolved.energy_key)
    return resolved, design, samples, params.countries[iso], sampler


def tau_of(iso: str, tech: str) -> dict:
    """tau primario e a faixa registrada (config/parameters.json)."""
    import json

    p = json.load(open(REPO / "config" / "parameters.json", encoding="utf-8"))
    return p["countries"][iso]["technologies"][tech]["tau_lcoe_usd_per_mwh"]


def load_cells(iso: str, tech: str, member: str = "m0") -> tuple[pd.DataFrame, object, object, object]:
    """Tabela por celula do membro `member` (cenario central): insumos do kernel, CF do F5 e o LCOE nominal reconstruido e gravado."""
    resolved, design, samples, cparams, sampler = config(iso, tech)
    P = paths(iso)
    pot = pq.read_table(
        P["potential"] / f"potential_{tech}__central.parquet",
        columns=["cell_id", "member", "P_MW", "CF", "E_MWh"],
        filters=[("member", "=", member)],
    ).to_pandas()
    pot["member"] = pot["member"].astype(str)
    pot = pot.sort_values("cell_id", kind="stable").reset_index(drop=True)
    cand_cols = ["cell_id", "dist_sub_km", "dist_road_km"]
    names = pq.read_schema(P["candidates"] / f"candidates_{tech}__central.parquet").names
    if "pvcz_zone" in names:
        cand_cols.append("pvcz_zone")
    cand = pd.read_parquet(P["candidates"] / f"candidates_{tech}__central.parquet", columns=cand_cols)
    d_low, d_high, has = resolved.group3.degradation.bounds_for_cells(
        cand["pvcz_zone"].to_numpy() if "pvcz_zone" in cand else None, len(cand)
    )
    cand["d_low"], cand["d_high"], cand["has_bounds"] = d_low, d_high, has
    forc = pq.read_table(
        P["climate"] / "forcing.parquet", columns=["cell_id", "member", "dT"], filters=[("member", "=", member)]
    ).to_pandas()
    df = pot.merge(cand, on="cell_id", how="inner").merge(forc[["cell_id", "dT"]], on="cell_id", how="inner")
    usable = np.isfinite(df["dist_sub_km"]) & np.isfinite(df["dist_road_km"]) & df["has_bounds"]
    df = df[usable].reset_index(drop=True)
    x0 = resolved.nominal[resolved.energy_key]
    offset, slope = resolved.model.rescale_terms(x0, df["dT"].to_numpy(dtype="float64"))
    df["offset"], df["slope"] = offset, slope
    cells = CellInputs(
        p_mw=df["P_MW"].to_numpy("float64"),
        dist_sub_km=df["dist_sub_km"].to_numpy("float64"),
        dist_road_km=df["dist_road_km"].to_numpy("float64"),
        energy_mwh=df["E_MWh"].to_numpy("float64"),
        energy_offset=offset,
        energy_slope=slope,
        degradation_low=df["d_low"].to_numpy("float64"),
        degradation_high=df["d_high"].to_numpy("float64"),
    )
    nominal = samples.take(slice(0, 1))
    df["lcoe_recon"] = lcoe_block(cells, nominal)[:, 0]
    stored = pq.read_table(
        P["lcoe"] / f"lcoe_summary_{tech}.parquet", columns=["cell_id", "member", "lcoe_nominal"], filters=[("member", "=", member)]
    ).to_pandas()[["cell_id", "lcoe_nominal"]].rename(columns={"lcoe_nominal": "lcoe_stored"})
    df = df.merge(stored, on="cell_id", how="left")
    df["e_nominal_mwh"] = df["E_MWh"] * (df["offset"] + df["slope"] * x0)
    df["cf_eff"] = df["e_nominal_mwh"] / (df["P_MW"] * HOURS)
    df["cf_f5"] = df["CF"]
    return df, resolved, nominal, cells


def components(
    df: pd.DataFrame,
    nom: SampleInputs,
    *,
    capex: float,
    opex_frac: float,
    life: float,
    rate: float,
    cf: np.ndarray | float | None,
    connection: bool,
    degradation: bool,
    loss: bool,
    road: bool | None = None,
) -> np.ndarray:
    """LCOE (USD/MWh) of each cell for an explicit state of the terms; with every term at the nominal state it equals `lcoe_block`.

    `cf` None keeps the cell energy (nominal); a number or array replaces it by `cf * 8760 * P` (the reference plant energy).
    """
    p = df["P_MW"].to_numpy("float64")
    a_o = float(annuity_factor(rate, life))
    pref = float(nom.reference_project_mw[0])
    num = 1000.0 * capex * (1.0 + opex_frac * a_o) * p
    if connection:
        num = num + float(nom.bay_cost_usd[0]) * p / pref
        num = num + df["dist_sub_km"].to_numpy("float64") * p * float(nom.line_cost_usd_per_km[0]) * float(nom.tortuosity_grid[0]) / pref
    if road is None:
        road = connection
    if road:
        num = num + df["dist_road_km"].to_numpy("float64") * p * float(nom.road_cost_usd_per_km[0]) * float(nom.tortuosity_road[0]) / pref
    energy = df["e_nominal_mwh"].to_numpy("float64") if cf is None else np.asarray(cf, dtype="float64") * HOURS * p
    if degradation:
        w = float(nom.degradation_weight[0])
        d = df["d_low"].to_numpy("float64") + w * (df["d_high"].to_numpy("float64") - df["d_low"].to_numpy("float64"))
        a_e = energy_annuity_factor(rate, d, life)
    else:
        a_e = np.full(len(df), a_o)
    eta = np.ones(len(df))
    alpha = float(nom.transmission_loss_per_km[0])
    if loss and alpha != 0.0:
        eta = np.maximum(1.0 - df["dist_sub_km"].to_numpy("float64") * alpha * float(nom.tortuosity_grid[0]), 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = num / (energy * a_e * eta)
    return out + float(nom.opex_var_usd_per_mwh[0])


def f7_cells(iso: str, tech: str) -> pd.DataFrame:
    """Colunas por celula do F7 (MR, SR, LCOE nominal) do conjunto F7 do par, janela core."""
    return pd.read_parquet(paths(iso)["rob"] / f"robustness_{tech}__core.parquet")
