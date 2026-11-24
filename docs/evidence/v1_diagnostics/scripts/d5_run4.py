# Runs only at tag v1.1 (these scripts import modules of v1 that leave the work tree at COMMAND 306). Kept as documentation of the diagnostics D1 to D5.
"""COMANDO 205, D5 item 2 (extensao): o top-k de 8000 e 16000 sorteios, alem do teto do protocolo (4000). Somente diagnostico; nada e gravado no pipeline."""

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
SIZES = [4000, 8000, 16000]
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

tops = {}
for n in SIZES:
    design = build_design(resolved.specs, n, sampler.seed)
    samples = samples_from_design(design, resolved.nominal, resolved.energy_key)
    ev = evaluate(cs.reference, cs.core, samples, tau=decision.tau, block_cells=cells_per_block(0.5, n))
    rk = compute_rankings(cs, ev, decision)
    tops[n] = set(cs.f7_ids[rk.top_robust.mask].tolist())
    print(n, len(tops[n]), flush=True)
rows = []
for a, b in zip(SIZES[:-1], SIZES[1:]):
    j = len(tops[a] & tops[b]) / len(tops[a] | tops[b])
    rows.append({"de": a, "para": b, "k": len(tops[b]), "saem": len(tops[a] - tops[b]), "entram": len(tops[b] - tops[a]), "um_menos_jaccard": 1 - j})
pd.DataFrame(rows).to_csv(OUT / "D5_item2_extensao.csv", index=False)
print(pd.DataFrame(rows).to_string())
