# Runs only at tag v1.1 (these scripts import modules of v1 that leave the work tree at COMMAND 306). Kept as documentation of the diagnostics D1 to D5.
"""COMANDO 205, D5 item 3 (complemento): borda da mascara (area da celula dentro do pais sobre a area nominal) e capacidade minima. Somente leitura."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

import d1_common as c

OUT = c.OUT / "D5_dados"
R = 6371.0088
t3 = pd.read_csv(OUT / "D5_item3_menores.csv")
out_rows, pair = [], {}
for iso, tech in c.PAIRS:
    P = c.paths(iso)
    cand = pd.read_parquet(P["candidates"] / f"candidates_{tech}__central.parquet", columns=["cell_id", "lat_c", "cell_area_km2", "eligible_area_km2"])
    lat = cand["lat_c"].to_numpy()
    nom = R**2 * np.deg2rad(0.05) * (np.sin(np.deg2rad(lat + 0.025)) - np.sin(np.deg2rad(lat - 0.025)))
    cand["razao_area"] = cand["cell_area_km2"].to_numpy() / nom
    df, *_ = c.load_cells(iso, tech)
    df = df.merge(cand[["cell_id", "razao_area", "eligible_area_km2", "cell_area_km2"]], on="cell_id", how="left")
    rb = c.f7_cells(iso, tech).set_index("cell_id")
    df["topk_robust"] = df["cell_id"].map(rb["topk_robust"]).fillna(False).astype(bool)
    df["topk_nominal"] = df["cell_id"].map(rb["topk_nominal"]).fillna(False).astype(bool)
    pair[f"{iso} {tech}"] = {
        "razao_area_mediana": float(df["razao_area"].median()), "n_celulas_borda_lt_0_98": int((df["razao_area"] < 0.98).sum()), "frac_celulas_borda": float((df["razao_area"] < 0.98).mean()),
        "n_p_lt_1mw": int((df["P_MW"] < 1).sum()), "n_p_lt_0_1mw": int((df["P_MW"] < 0.1).sum()), "p_min_mw": float(df["P_MW"].min()), "p_mediana_mw": float(df["P_MW"].median()),
        "topk_nominal_n": int(df["topk_nominal"].sum()), "topk_nominal_p_lt_1mw": int((df["topk_nominal"] & (df["P_MW"] < 1)).sum()), "topk_nominal_p_lt_0_1mw": int((df["topk_nominal"] & (df["P_MW"] < 0.1)).sum()),
        "topk_robust_n": int(df["topk_robust"].sum()), "topk_robust_p_lt_1mw": int((df["topk_robust"] & (df["P_MW"] < 1)).sum()),
        "topk_nominal_capacidade_mw": float(df.loc[df["topk_nominal"], "P_MW"].sum()), "capacidade_total_mw": float(df["P_MW"].sum()),
        "topk_nominal_mediana_p_mw": float(df.loc[df["topk_nominal"], "P_MW"].median()),
    }
    m = t3[t3["par"] == f"{iso} {tech}"].merge(df[["cell_id", "razao_area"]], on="cell_id", how="left")
    out_rows.append(m[["par", "posicao", "cell_id", "razao_area"]])
pd.concat(out_rows).to_csv(OUT / "D5_item3_borda.csv", index=False)
json.dump(pair, open(OUT / "D5_item3_borda_pares.json", "w", encoding="utf-8"), indent=1)
print(pd.concat(out_rows).to_string())
print(json.dumps(pair, indent=1))
