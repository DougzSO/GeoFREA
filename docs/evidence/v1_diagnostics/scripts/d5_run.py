# Runs only at tag v1.1 (these scripts import modules of v1 that leave the work tree at COMMAND 306). Kept as documentation of the diagnostics D1 to D5.
"""COMANDO 205, D5 (itens 2 e parte do 1): convergencia do top-k da PRT solar (L-252). Somente leitura; grava so em D5_dados/.

Refaz o protocolo U-04 (mesmas funcoes de convergence.py, mesmos insumos) e guarda o conjunto top-k e o MR de cada tamanho.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
import yaml

import d1_common as c  # noqa: F401  (ajusta sys.path e ambiente)
from pathlib import Path

from geofrea.climate_forcing.members import REFERENCE_MEMBER_ID, required_channels
from geofrea.core.config_loader import load_experiments, load_parameters, load_technologies
from geofrea.lcoe_modeling.design import build_design, samples_from_design
from geofrea.lcoe_modeling.inputs import cells_per_block, read_member_inputs, resolve_all
from geofrea.robustness_analysis.assemble import compute_rankings
from geofrea.robustness_analysis.cell_set import build_cell_set
from geofrea.robustness_analysis.convergence import _core_members, jaccard
from geofrea.robustness_analysis.decision import decision_values
from geofrea.robustness_analysis.evaluator import evaluate

OUT = c.OUT / "D5_dados"
OUT.mkdir(parents=True, exist_ok=True)

iso, tech = "PRT", "solar"
SIZES = [500, 1000, 2000, 4000]
params = load_parameters(c.REPO / "config" / "parameters.json")
techs = load_technologies(c.REPO / "config" / "technologies.yaml")
exps = load_experiments(c.REPO / "config" / "experiments.yaml")
sampler = exps.sampler
core_win = f"{exps.windows['core']['start_year']}-{exps.windows['core']['end_year']}"
cp = params.countries[iso]
resolved = resolve_all(iso, techs, cp, [tech])[tech]
decision = decision_values(getattr(cp.technologies, tech), tech)
P = c.paths(iso)
members_file = P["climate"] / "members.yaml"
all_members, _ = _core_members(members_file, core_win)
_, core = _core_members(members_file, core_win, required_channels(techs.technologies[tech].cf_model))
xs = [s for s in resolved.specs if s.name == resolved.energy_key]
x_range = (xs[0].low, xs[0].high) if xs else (resolved.nominal[resolved.energy_key],) * 2
members = {
    m.member: m
    for m in read_member_inputs(
        resolved,
        potential_path=P["potential"] / f"potential_{tech}__central.parquet",
        candidates_path=P["candidates"] / f"candidates_{tech}__central.parquet",
        forcing_path=P["climate"] / "forcing.parquet",
        members=[REFERENCE_MEMBER_ID, *core],
        x_range=x_range,
        known_members=all_members,
    )
}
cand_ids = pd.read_parquet(P["candidates"] / f"candidates_{tech}__central.parquet", columns=["cell_id"])["cell_id"].to_numpy()
cs = build_cell_set(cand_ids, members, REFERENCE_MEMBER_ID, list(core), decision.cf_min)
print("n_f7", cs.n_f7, "core members", len(core), "cf_min", decision.cf_min, "k%", decision.top_k_percent, "tau", decision.tau)

res = {}
tops, mrs, srs = {}, {}, {}
for n in SIZES:
    design = build_design(resolved.specs, n, sampler.seed)
    samples = samples_from_design(design, resolved.nominal, resolved.energy_key)
    ev = evaluate(cs.reference, cs.core, samples, tau=decision.tau, block_cells=cells_per_block(0.5, n))
    rk = compute_rankings(cs, ev, decision)
    top = cs.f7_ids[rk.top_robust.mask]
    tops[n] = set(top.tolist())
    mrs[n] = pd.Series(ev.mr, index=cs.f7_ids)
    srs[n] = pd.Series(ev.sr, index=cs.f7_ids)
    res[n] = {"k": int(top.size), "mr_min": float(np.nanmin(ev.mr)), "mr_max": float(np.nanmax(ev.mr))}
    print(n, top.size)

ids = cs.f7_ids
rows = []
prev = None
for n in SIZES:
    if prev is not None:
        a, b = tops[prev], tops[n]
        rows.append({"de": prev, "para": n, "k": len(b), "interseccao": len(a & b), "saem": len(a - b), "entram": len(b - a), "jaccard": jaccard(np.array(sorted(a)), np.array(sorted(b))), "um_menos_jaccard": 1 - jaccard(np.array(sorted(a)), np.array(sorted(b)))})
    prev = n
conv = pd.DataFrame(rows)
conv.to_csv(OUT / "D5_item2_convergencia.csv", index=False)
print(conv.to_string())

# ---- comparacao com o F7 gravado (top-k robusto do F7, 4000 sorteios, mesma semente)
rob = c.f7_cells(iso, tech)
k = len(tops[4000])
f7_top = set(rob.loc[rob["robust_rank"] <= k, "cell_id"].tolist())
same_f7 = f7_top == tops[4000]

# ---- as celulas que trocam entre 2000 e 4000, onde ficam em relacao ao corte
a, b = tops[2000], tops[4000]
swap = sorted((a ^ b))
mr4 = mrs[4000].sort_values(kind="stable")
ranked_mask = pd.Series(cs.ranked, index=ids)  # booleana: celula ranqueada
order = mr4[ranked_mask.reindex(mr4.index).fillna(False)].dropna()
cut_idx = k  # posicao k (base 1) = k-esima menor MR
mr_k = float(order.iloc[k - 1])
mr_k1 = float(order.iloc[k])
sw = pd.DataFrame({"cell_id": swap})
sw["em_2000"] = sw["cell_id"].isin(a)
sw["em_4000"] = sw["cell_id"].isin(b)
for n in SIZES:
    sw[f"mr_{n}"] = sw["cell_id"].map(mrs[n])
sw["posicao_mr_4000"] = sw["cell_id"].map(pd.Series(np.arange(1, len(order) + 1), index=order.index))
sw["sr_4000"] = sw["cell_id"].map(srs[4000])
cells, *_ = c.load_cells(iso, tech)
cells = cells.set_index("cell_id")
sw["lcoe_nominal"] = sw["cell_id"].map(cells["lcoe_stored"])
sw["dist_sub_km"] = sw["cell_id"].map(cells["dist_sub_km"])
sw["cf"] = sw["cell_id"].map(cells["cf_f5"])
sw["p_mw"] = sw["cell_id"].map(cells["P_MW"])
sw["pvcz_zone"] = sw["cell_id"].map(cells["pvcz_zone"])
sw.to_csv(OUT / "D5_item2_trocas.csv", index=False)

# densidade de MR em torno do corte (largura relativa do corte)
v = order.to_numpy()
dens = {}
for w in (0.001, 0.002, 0.005, 0.01):
    dens[str(w)] = int(((v >= mr_k * (1 - w)) & (v <= mr_k * (1 + w))).sum())
# variacao do MR de cada celula entre 2000 e 4000, relativa
d = (mrs[4000] - mrs[2000]).dropna()
rel = (d / mrs[2000].reindex(d.index)).abs()
# ruido de amostragem: MR de uma mesma celula entre dois tamanhos vs. folga ao corte
gap = (mrs[4000].reindex(order.index) - mr_k).abs()
noise = rel.reindex(order.index).dropna()
res_out = {
    "n_f7": int(cs.n_f7), "n_ranked": int(len(order)), "k": k, "tau": decision.tau, "cf_min": decision.cf_min, "top_k_percent": decision.top_k_percent,
    "n_membros_nucleo": len(core),
    "top_robusto_do_f7_igual_ao_de_4000": bool(same_f7),
    "mr_no_corte_4000": mr_k, "mr_k_mais_1": mr_k1, "mr_min": float(order.iloc[0]), "mr_mediana": float(np.median(v)), "mr_max": float(order.iloc[-1]),
    "celulas_com_mr_dentro_de_largura_relativa_do_corte": dens,
    "dif_relativa_mr_2000_4000": {"mediana": float(noise.median()), "p90": float(noise.quantile(0.9)), "p99": float(noise.quantile(0.99)), "max": float(noise.max())},
    "n_trocam_2000_4000": len(swap), "n_saem": int(len(a - b)), "n_entram": int(len(b - a)),
    "trocas_gap_relativo_ao_corte_4000": {"mediana": float((sw["mr_4000"].sub(mr_k).abs() / mr_k).median()), "max": float((sw["mr_4000"].sub(mr_k).abs() / mr_k).max())},
    "tamanhos": res,
}
json.dump(res_out, open(OUT / "D5_item2.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(json.dumps(res_out, indent=1)[:3000])
print(sw.to_string())
