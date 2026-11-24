# Runs only at tag v1.1 (these scripts import modules of v1 that leave the work tree at COMMAND 306). Kept as documentation of the diagnostics D1 to D5.
"""COMANDO 203, D3: o que produz o O do H2 e por que o veredito muda com gamma. Somente leitura; grava so em D3_dados/."""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import d1_common as c

OUT = c.OUT / "D3_dados"
OUT.mkdir(parents=True, exist_ok=True)
GRID = np.round(np.arange(0.10, 0.7001, 0.05), 2)


def verdict(o: float, o_ref: float, g: float) -> str:
    """Regra de M-F7-07 (H2): nao testavel se O_ref >= gamma; apoiada se O < gamma; nao apoiada se O >= gamma."""
    if o_ref >= g:
        return "not_testable"
    return "supported" if o < g else "not_supported"


def hhi(x: np.ndarray) -> float:
    s = x / x.sum()
    return float((s**2).sum())


res: dict = {}
vrows, rrows = [], []
fig, axs = plt.subplots(2, 3, figsize=(15, 8))
for ax, (iso, tech) in zip(axs.flat, c.PAIRS):
    key = f"{iso} {tech}"
    P = c.paths(iso)["rob"]
    s_all = pd.read_parquet(P / f"h2_summary_{tech}__core.parquet")
    s = s_all[s_all["primary"]].iloc[0]
    reg = pd.read_parquet(P / f"h2_regions_{tech}__core.parquet").sort_values("position").reset_index(drop=True)
    rob = c.f7_cells(iso, tech)
    T, qmax = float(s["target_mw"]), float(s["q_max_mw"])
    O, O_ref = float(s["overlap"]), float(s["overlap_ref"])
    # ---- conferencias: O e D_TV das regioes; delta_z das celulas
    contrib = reg["selected_cell_mw"] * reg["fraction_taken"] / T  # parte de O de cada regiao (x_cell e 0/1, x_admin e a fracao da regiao)
    o_calc = float(contrib.sum())
    tv_calc = float(0.5 * (reg["share_cell"] - reg["share_admin"]).abs().sum())
    ranked = rob[rob["cell_class"] == "ranked"].copy()
    k = int(s["k"])
    frac = reg.set_index("region")["fraction_taken"]
    ranked["x_admin"] = ranked["admin1_id"].map(frac).fillna(0.0)
    ranked["x_cell"] = (ranked["robust_rank"] <= k).astype(float)
    q = ranked["p_mw"]
    dz_calc = float(((q * ranked["x_admin"] * ranked["mr"]).sum() - (q * ranked["x_cell"] * ranked["mr"]).sum()) / T)
    t_calc = float((q * ranked["x_cell"]).sum())
    # ---- distribuicao da capacidade entre regioes
    cap = reg["capacity_mw"].to_numpy()
    cap_sorted = np.sort(cap)[::-1]
    shares = cap_sorted / cap_sorted.sum()
    # ---- selecao regional
    taken = reg[reg["fraction_taken"] > 0]
    full = reg[reg["fraction_taken"] >= 1.0]
    last = taken.iloc[-1]
    cell_in_taken = float(taken["selected_cell_mw"].sum() / T)
    # ---- concentracao do O
    c_sorted = np.sort(contrib.to_numpy())[::-1]
    cum = np.cumsum(c_sorted) / c_sorted.sum() if c_sorted.sum() > 0 else c_sorted
    n50 = int(np.searchsorted(cum, 0.5) + 1) if c_sorted.sum() > 0 else 0
    # ---- variancia de MR entre e dentro das regioes (ponderada pela capacidade)
    zbar = float((reg["capacity_mw"] * reg["mean_z"]).sum() / reg["capacity_mw"].sum())
    between = float((reg["capacity_mw"] * (reg["mean_z"] - zbar) ** 2).sum())
    within = float((reg["capacity_mw"] * reg["within_variance"]).sum())
    # ---- perfil de decisao por gamma
    prof = {f"{g:.2f}": verdict(O, O_ref, g) for g in GRID}
    supp = [g for g in GRID if verdict(O, O_ref, g) == "supported"]
    smallest = float(min(supp)) if supp else None
    # ---- variantes do F7 (nucleo, janela sensivel e escala 0,1)
    var = s_all.copy()
    var["_grp"] = np.where(var["variant"].str.startswith("gamma_"), "gamma", "outras")
    prim_v = s["verdict"]
    chg = var[(~var["primary"]) & (var["verdict"] != prim_v)]
    sens = pd.read_parquet(P / f"h2_summary_{tech}__sensitivity.parquet")
    sp_ = sens[sens["primary"]].iloc[0]
    chg_s = sens[(~sens["primary"]) & (sens["verdict"] != sp_["verdict"])]
    p01 = pd.read_parquet(c.DATA / "outputs" / iso / "robustness_analysis__0p1deg" / "artifacts" / f"h2_summary_{tech}__core.parquet")
    p01 = p01[p01["primary"]].iloc[0]
    for _, v in var.iterrows():
        vrows.append({"par": key, "janela": "2041-2070", "variante": v["variant"], "k": v["k"], "T_mw": v["target_mw"], "O": v["overlap"], "O_ref": v["overlap_ref"], "veredito": v["verdict"], "menor_gamma_que_apoia": v["smallest_supporting_gamma"], "muda_contra_primario": bool(v["verdict"] != prim_v and not v["primary"])})
    for _, v in sens.iterrows():
        vrows.append({"par": key, "janela": "2071-2100", "variante": v["variant"], "k": v["k"], "T_mw": v["target_mw"], "O": v["overlap"], "O_ref": v["overlap_ref"], "veredito": v["verdict"], "menor_gamma_que_apoia": v["smallest_supporting_gamma"], "muda_contra_primario": bool(v["verdict"] != sp_["verdict"] and not v["primary"])})
    res[key] = {
        "n_ranked": int(s["n_ranked"]), "n_regioes": int(s["n_regions"]), "k": k, "T_mw": T, "Qmax_mw": qmax, "O": O, "O_ref": O_ref, "O_sobre_O_ref": O / O_ref, "verdict": prim_v, "gamma": float(s["gamma"]),
        "delta_z": float(s["robustness_penalty"]), "D_TV": float(s["tv_distance"]), "iqr_sobre_mediana": float(s["iqr_over_median"]), "menor_gamma_grade_arquivo": None if pd.isna(s["smallest_supporting_gamma"]) else float(s["smallest_supporting_gamma"]),
        "confere": {"O_calc": o_calc, "tv_calc": tv_calc, "delta_z_calc": dz_calc, "T_calc": t_calc},
        "capacidade_regioes": {"HHI": hhi(cap), "N_efetivo": 1 / hhi(cap), "top1": float(shares[0]), "top3": float(shares[:3].sum()), "top5": float(shares[:5].sum()), "min_mw": float(cap.min()), "mediana_mw": float(np.median(cap)), "max_mw": float(cap.max()),
                               "n_celulas_mediana": float(reg["n_cells"].median()), "n_celulas_min": int(reg["n_cells"].min()), "n_celulas_max": int(reg["n_cells"].max())},
        "selecao_regional": {"regioes_usadas": int(len(taken)), "regioes_inteiras": int(len(full)), "fracao_ultima": float(last["fraction_taken"]), "cap_regioes_usadas_sobre_Qmax": float(taken["capacity_mw"].sum() / qmax),
                             "selecao_celula_nas_regioes_usadas_sobre_T": cell_in_taken, "regioes_com_celula_selecionada": int((reg["selected_cell_mw"] > 0).sum())},
        "concentracao": {"HHI_selecao_celula": hhi(reg["selected_cell_mw"].to_numpy()), "HHI_selecao_regional": hhi(reg["selected_admin_mw"].to_numpy()), "N_efetivo_celula": 1 / hhi(reg["selected_cell_mw"].to_numpy()), "N_efetivo_regional": 1 / hhi(reg["selected_admin_mw"].to_numpy()),
                         "top1_contrib_O": float(c_sorted[0] / c_sorted.sum()) if c_sorted.sum() else None, "top3_contrib_O": float(c_sorted[:3].sum() / c_sorted.sum()) if c_sorted.sum() else None, "regioes_para_50pct_de_O": n50,
                         "top1_share_celula": float(reg["share_cell"].max()), "top1_share_regional": float(reg["share_admin"].max())},
        "variancia_MR": {"entre_regioes_sobre_total": between / (between + within), "dentro_sobre_total": within / (between + within), "mr_medio_ponderado": zbar},
        "perfil_gamma": prof, "menor_gamma_grade": smallest,
        "variantes": {"n_variantes_nucleo": int(len(var) - 1), "n_mudam_nucleo": int(len(chg)), "mudam_nucleo": chg["variant"].tolist(), "n_gamma": int(var["variant"].str.startswith("gamma_").sum()), "n_mudam_gamma": int(chg["variant"].str.startswith("gamma_").sum()),
                      "n_mudam_outras": int((~chg["variant"].str.startswith("gamma_")).sum()), "n_mudam_para_supported": int((chg["verdict"] == "supported").sum()), "n_mudam_para_not_testable": int((chg["verdict"] == "not_testable").sum()), "n_linhas_com_primario": int(len(var)),
                      "n_mudam_sens_para_supported": int((chg_s["verdict"] == "supported").sum()), "n_mudam_sens_para_not_testable": int((chg_s["verdict"] == "not_testable").sum()), "n_variantes_sens": int(len(sens) - 1), "n_mudam_sens": int(len(chg_s)), "veredito_sens": sp_["verdict"], "O_sens": float(sp_["overlap"]), "O_ref_sens": float(sp_["overlap_ref"])},
        "escala_0p1": {"O": float(p01["overlap"]), "O_ref": float(p01["overlap_ref"]), "veredito": p01["verdict"], "n_regioes": int(p01["n_regions"])},
    }
    for _, r in reg.iterrows():
        rrows.append({"par": key, "regiao": r["region"], "posicao_regional": int(r["position"]), "n_celulas": int(r["n_cells"]), "capacidade_mw": float(r["capacity_mw"]), "share_capacidade": float(r["capacity_mw"] / reg["capacity_mw"].sum()), "mr_medio": float(r["mean_z"]),
                      "var_dentro": float(r["within_variance"]), "fracao_tomada": float(r["fraction_taken"]), "selecao_celula_mw": float(r["selected_cell_mw"]), "selecao_regional_mw": float(r["selected_admin_mw"]), "contribuicao_a_O": float(r["selected_cell_mw"] * r["fraction_taken"] / T)})
    top = reg.assign(sh=reg["capacity_mw"] / reg["capacity_mw"].sum()).sort_values("sh", ascending=False).head(8)
    x = np.arange(len(top))
    ax.bar(x - 0.27, top["sh"] * 100, 0.27, color="#7f7f7f", label="capacidade da região (% de Q_max)")
    ax.bar(x, top["selected_cell_mw"] / T * 100, 0.27, color="#1f4e79", label="seleção por célula (% de T)")
    ax.bar(x + 0.27, top["selected_admin_mw"] / T * 100, 0.27, color="#c9a227", label="seleção regional (% de T)")
    ax.set_xticks(x, [r.split("_")[0] for r in top["region"]], rotation=45, fontsize=7)
    ax.set_title(f"{key}: O = {O:.3f}, O_ref = {O_ref:.3f}")
axs[0, 0].legend(fontsize=7)
fig.suptitle("D3: as 8 maiores regiões (Admin1) de cada par")
fig.tight_layout()
fig.savefig(OUT / "D3_regioes.png", dpi=130)
plt.close(fig)

json.dump(res, open(OUT / "D3_resultados.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
pd.DataFrame(vrows).to_csv(OUT / "D3_variantes.csv", index=False)
pd.DataFrame(rrows).to_csv(OUT / "D3_regioes.csv", index=False)
for k_, v in res.items():
    cf = v["confere"]
    print(k_, "O", round(v["O"], 6), round(cf["O_calc"], 6), "TV", round(v["D_TV"], 6), round(cf["tv_calc"], 6), "dz", round(v["delta_z"], 6), round(cf["delta_z_calc"], 6), "T", round(v["T_mw"], 3), round(cf["T_calc"], 3))
