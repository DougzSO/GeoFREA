# Runs only at tag v1.1 (these scripts import modules of v1 that leave the work tree at COMMAND 306). Kept as documentation of the diagnostics D1 to D5.
"""COMANDO 202, D2: o que move (ou nao) o ranking. Somente leitura; grava so em D2_dados/.

    python d2_run.py
"""
from __future__ import annotations

import dataclasses
import json
import math
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.stats import rankdata, spearmanr

import d1_common as c
from geofrea.lcoe_modeling.kernel import lcoe_block

SEED = 202
N_SAMPLE = 20000
N_DRAWS = 200
OUT = c.OUT / "D2_dados"
OUT.mkdir(parents=True, exist_ok=True)


def ordinal_rank(x: np.ndarray) -> np.ndarray:
    """Posto 1..n em ordem crescente; empate pela posicao (cell_id crescente nas tabelas ordenadas)."""
    o = np.lexsort((np.arange(len(x)), x))
    r = np.empty(len(x), dtype=np.int64)
    r[o] = np.arange(1, len(x) + 1)
    return r


def variance_split(a: np.ndarray) -> dict:
    """Partes da variancia de uma matriz celulas x futuros: entre celulas, deslocamento comum dos futuros, interacao celula x futuro."""
    n, f = a.shape
    mu = a.mean()
    rows, cols = a.mean(1), a.mean(0)
    ss_c = f * ((rows - mu) ** 2).sum()
    ss_f = n * ((cols - mu) ** 2).sum()
    ss_t = ((a - mu) ** 2).sum()
    ss_i = ss_t - ss_c - ss_f
    return {"entre_celulas": ss_c / ss_t, "futuros_comum": ss_f / ss_t, "interacao": ss_i / ss_t, "var_total": ss_t / a.size}


def topk_overlap(r0: np.ndarray, rf: np.ndarray, k: int) -> float:
    return float(((r0 <= k) & (rf <= k)).sum() / k)


def stats_axis(L0: np.ndarray, F: np.ndarray, k: int) -> dict:
    """Spearman e sobreposicao do top-k entre o ranking nominal e o de cada coluna de F; pior posto do top-k nominal."""
    r0 = ordinal_rank(L0)
    rho = np.array([spearmanr(L0, F[:, j])[0] for j in range(F.shape[1])])
    ranks = np.column_stack([ordinal_rank(F[:, j]) for j in range(F.shape[1])])
    ov = np.array([topk_overlap(r0, ranks[:, j], k) for j in range(F.shape[1])])
    top = r0 <= k
    worst = ranks[top].max(axis=1) / k  # em multiplos de k
    return {
        "spearman": [float(rho.min()), float(np.median(rho)), float(rho.max())],
        "overlap_topk": [float(ov.min()), float(np.median(ov)), float(ov.max())],
        "pior_posto_sobre_k": {"min": float(worst.min()), "q25": float(np.quantile(worst, 0.25)), "mediana": float(np.median(worst)), "q75": float(np.quantile(worst, 0.75)), "q95": float(np.quantile(worst, 0.95)), "max": float(worst.max())},
        "frac_topk_acima_de_2k": float((worst > 2.0).mean()),
        "frac_topk_acima_de_1_5k": float((worst > 1.5).mean()),
        "n_topk": int(top.sum()),
        "_worst": worst,
        "_ranks": ranks,
        "_r0": r0,
    }


def hyp_stats(rob: pd.DataFrame, ssp: pd.DataFrame, pk: float, m_mult: float) -> dict:
    """V_k (H1b), D_clim, D_tec, rho (H4) e d (H3) com top-k `pk` por cento e tolerancia m = m_mult x k; as definicoes de M-F7-05, 06 e 07."""
    i0 = rob[rob["cell_class"].isin(["ranked", "climate_fragile"])].sort_values("cell_id")
    n0 = len(i0)
    k = max(1, math.ceil(pk / 100.0 * n0))
    m = m_mult * k
    ranked = rob[rob["cell_class"] == "ranked"].sort_values("cell_id").reset_index(drop=True)
    # posto nominal dentro de I_0 (para S^nom_k) e dentro de I (para r^nom)
    nom0 = pd.Series(ordinal_rank(i0["lcoe_nominal"].to_numpy()), index=i0["cell_id"].to_numpy())
    nomI = ordinal_rank(ranked["lcoe_nominal"].to_numpy())
    # H1b
    top_nom = nom0[nom0 <= k].index
    s = ssp.groupby("cell_id")["r_clim_ssp_rank"].max()
    worst_ssp = s.reindex(top_nom)
    vulnerable = worst_ssp.isna() | (worst_ssp > k + m)  # celula fragil (sem posto) conta como vulneravel
    v_k = float(vulnerable.sum() / k)
    q = ranked["p_mw"].to_numpy()
    out = {"n_i0": n0, "n_ranked": len(ranked), "k": k, "m": m, "v_k": v_k, "n_vulneraveis": int(vulnerable.sum())}
    for axis, col in (("clim", "climate_only_rank"), ("tec", "techno_only_rank")):
        sel = ranked[col].to_numpy() <= k
        beyond = sel & (nomI > k + m)
        out[f"d_{axis}"] = float(q[beyond].sum() / q[sel].sum()) if q[sel].sum() > 0 else float("nan")
    ds = out["d_clim"] + out["d_tec"]
    out["rho"] = float(out["d_clim"] / ds) if ds > 0 else float("nan")
    sel = ranked["robust_rank"].to_numpy() <= k
    out["d_h3"] = float(q[sel & (nomI > k + m)].sum() / q[sel].sum())
    return out


results: dict = {}
files: dict = {}
for iso, tech in c.PAIRS:
    key = f"{iso} {tech}"
    print(key, flush=True)
    P = c.paths(iso)
    rob = c.f7_cells(iso, tech)
    ranked = rob[rob["cell_class"] == "ranked"].sort_values("cell_id").reset_index(drop=True)
    nm = pd.read_parquet(P["rob"] / f"nominal_lcoe_by_member_{tech}__core.parquet")
    members = sorted(m for m in nm["member"].unique() if m != "m0")
    pk = float(json.load(open(c.REPO / "config" / "parameters.json", encoding="utf-8"))["countries"][iso]["technologies"][tech]["top_k_percent"]["value"])
    cf_min = float(json.load(open(c.REPO / "config" / "parameters.json", encoding="utf-8"))["countries"][iso]["technologies"][tech]["cf_min"]["value"])
    # ---- amostra
    ids_all = ranked["cell_id"].to_numpy()
    if len(ids_all) > N_SAMPLE:
        rng = np.random.default_rng(SEED)
        ids = np.sort(rng.choice(ids_all, size=N_SAMPLE, replace=False))
    else:
        ids = ids_all
    n = len(ids)
    k = math.ceil(pk / 100.0 * n)
    nm_s = nm[nm["cell_id"].isin(ids)]
    piv = nm_s.pivot(index="cell_id", columns="member", values="lcoe_nominal").reindex(ids)
    L0 = piv["m0"].to_numpy("float64")
    Lc = piv[members].to_numpy("float64")
    assert np.isfinite(L0).all() and np.isfinite(Lc).all()
    base = ranked.set_index("cell_id").loc[ids, "lcoe_nominal"].to_numpy("float64")
    assert np.allclose(L0, base, rtol=0, atol=0), "o nominal de m0 da tabela por membro difere do da tabela de robustez"
    # ---- kernel nos mesmos insumos
    df, resolved, nom, cells_all = c.load_cells(iso, tech)
    pos = pd.Index(df["cell_id"].to_numpy()).get_indexer(ids)
    assert (pos >= 0).all()
    cells = cells_all.take(pos)
    _, design, samples, _, _ = c.config(iso, tech)
    nominal1 = samples.take(slice(0, 1))
    recon = lcoe_block(cells, nominal1)[:, 0]
    assert np.allclose(recon, L0, rtol=0, atol=1e-9), "o kernel nao reproduz o LCOE nominal da amostra"
    Lp = lcoe_block(cells, samples.take(slice(1, 1 + N_DRAWS)))
    assert np.isfinite(Lp).all()
    # verificacao de reproducao dos sorteios: PRT eolica, 4000 sorteios, p10/p50/p90 contra o lcoe_summary
    if (iso, tech) == ("PRT", "wind"):
        allp = lcoe_block(cells_all, samples.take(slice(1, 4001)))
        q = np.percentile(allp, [10, 50, 90], axis=1)
        st = pd.read_parquet(P["lcoe"] / f"lcoe_summary_{tech}.parquet")
        st = st[st["member"] == "m0"].set_index("cell_id").loc[df["cell_id"].to_numpy()]
        err = max(np.abs(q[0] - st["lcoe_p10"].to_numpy()).max(), np.abs(q[1] - st["lcoe_p50"].to_numpy()).max(), np.abs(q[2] - st["lcoe_p90"].to_numpy()).max())
        files["reproducao_sorteios_PRT_wind_max_abs_err_p10_p50_p90"] = float(err)
        assert err < 1e-6, err
    # ---- item 1: efeito de cada parametro sobre a ordem (um por vez, p5 e p95 do desenho)
    r0 = ordinal_rank(L0)
    oat = []
    cols = [col for col in design.columns if col != "sample"]
    fld = {col: ("energy_parameter" if col == resolved.energy_key else col) for col in cols}

    def with_values(**kv):
        return dataclasses.replace(nominal1, **{f: np.array([v]) for f, v in kv.items()})

    for col in cols:
        lo, hi = float(np.quantile(design[col].iloc[1:], 0.05)), float(np.quantile(design[col].iloc[1:], 0.95))
        row = {"parametro": col, "nominal": float(design[col].iloc[0]), "p5": lo, "p95": hi}
        for lab, v in (("p5", lo), ("p95", hi)):
            L = lcoe_block(cells, with_values(**{fld[col]: v}))[:, 0]
            row[f"spearman_{lab}"] = float(spearmanr(L0, L)[0])
            row[f"overlap_topk_{lab}"] = topk_overlap(r0, ordinal_rank(L), k)
            row[f"mudanca_media_{lab}_pct"] = float((L / L0 - 1).mean() * 100)
            row[f"mudanca_sd_{lab}_pct"] = float((L / L0 - 1).std() * 100)
        oat.append(row)
    comum = [x for x in ("capex_usd_per_kw", "opex_fixed_frac", "discount_rate", "lifetime_years") if x in cols]
    celula = [x for x in cols if x not in comum]
    for lab, grp in (("grupo comum (capex, O&M, taxa, vida) todos no p95", comum), ("grupo com termo da celula (conexao, degradacao, energia) todos no p95", celula)):
        kv = {fld[g]: float(np.quantile(design[g].iloc[1:], 0.95)) for g in grp}
        L = lcoe_block(cells, with_values(**kv))[:, 0]
        oat.append({"parametro": lab, "spearman_p95": float(spearmanr(L0, L)[0]), "overlap_topk_p95": topk_overlap(r0, ordinal_rank(L), k), "mudanca_media_p95_pct": float((L / L0 - 1).mean() * 100), "mudanca_sd_p95_pct": float((L / L0 - 1).std() * 100)})
    pd.DataFrame(oat).to_csv(OUT / f"D2_1_oat_{iso}_{tech}.csv", index=False)
    # ---- item 2: variancia
    split = {}
    for axis, M in (("clima (membros, parametros nominais)", Lc), ("parametros (200 sorteios, clima m0)", Lp)):
        split[axis] = {"nivel": variance_split(M), "log": variance_split(np.log(M))}
    # ---- itens 3 e 4
    sc = stats_axis(L0, Lc, k)
    sp = stats_axis(L0, Lp, k)
    both = np.maximum(sc["_worst"], sp["_worst"])
    comb = {"pior_posto_sobre_k_max": float(both.max()), "frac_acima_de_2k": float((both > 2.0).mean())}
    np.save(OUT / f"_worst_{iso}_{tech}_clima.npy", sc["_worst"])
    np.save(OUT / f"_worst_{iso}_{tech}_param.npy", sp["_worst"])
    # ---- item 5: sinal climatico (todas as celulas ranqueadas, membros do core)
    pot = pq.read_table(P["potential"] / f"potential_{tech}__central.parquet", columns=["cell_id", "member", "CF"], filters=[("member", "in", ["m0"] + members)]).to_pandas()
    pot["member"] = pot["member"].astype(str)
    pot = pot[pot["cell_id"].isin(ids_all)]
    cfp = pot.pivot(index="cell_id", columns="member", values="CF").reindex(ids_all)
    sig = []
    nm_r = nm[nm["cell_id"].isin(ids_all)].pivot(index="cell_id", columns="member", values="lcoe_nominal").reindex(ids_all)
    for mname in members:
        dcf = (cfp[mname] / cfp["m0"] - 1) * 100
        dl = (nm_r[mname] / nm_r["m0"] - 1) * 100
        sig.append({"membro": mname, "cf_mudanca_mediana_pct": float(dcf.median()), "cf_mudanca_sd_espacial_pct": float(dcf.std()), "lcoe_mudanca_mediana_pct": float(dl.median()), "lcoe_mudanca_sd_espacial_pct": float(dl.std())})
    pd.DataFrame(sig).to_csv(OUT / f"D2_5_sinal_{iso}_{tech}.csv", index=False)
    # ---- item 6: MR contra LCOE nominal (todas as celulas ranqueadas)
    r = ranked.dropna(subset=["mr", "lcoe_nominal"])
    lmin = r["lcoe_nominal"].min()
    d = ((r["lcoe_nominal"] - lmin) / lmin).to_numpy()
    mr = r["mr"].to_numpy()
    slope, icpt = np.polyfit(d, mr, 1)
    r2 = float(np.corrcoef(d, mr)[0, 1] ** 2)
    rho_mr = float(spearmanr(r["lcoe_nominal"], mr)[0])
    item6 = {"n": int(len(r)), "spearman_mr_lcoe": rho_mr, "r2_linear_mr_sobre_distancia": r2, "inclinacao": float(slope), "intercepto": float(icpt), "r2_ranks": rho_mr**2,
             "mr_mediana": float(np.median(mr)), "distancia_mediana": float(np.median(d)), "mr_menos_d_mediana": float(np.median(mr - d)),
             "mr_menos_d_q25": float(np.quantile(mr - d, 0.25)), "mr_menos_d_q75": float(np.quantile(mr - d, 0.75))}
    # ---- item 7: V_k, D, rho (reproducao do primario e variante exploratoria)
    ssp = pd.read_parquet(P["rob"] / f"ssp_scores_{tech}__core.parquet", columns=["cell_id", "ssp", "r_clim_ssp_rank"])
    prim = hyp_stats(rob, ssp, pk, 1.0)
    h1 = pd.read_parquet(P["rob"] / f"h1_summary_{tech}__core.parquet").query("primary").iloc[0]
    h4 = pd.read_parquet(P["rob"] / f"h4_country_{tech}__core.parquet").query("primary").iloc[0]
    h3 = pd.read_parquet(P["rob"] / f"h3_summary_{tech}__core.parquet").query("primary").iloc[0]
    repro = {"v_k_f7": float(h1["v_k"]), "v_k_calc": prim["v_k"], "d_clim_f7": float(h4["d_clim"]), "d_clim_calc": prim["d_clim"], "d_tec_f7": float(h4["d_tec"]), "d_tec_calc": prim["d_tec"],
             "d_h3_f7": float(h3["d"]), "d_h3_calc": prim["d_h3"], "k_f7": int(h1["k"]), "k_calc": prim["k"]}
    variants = {"primario (10%, m = k)": prim, "exploratorio (1%, m = k/2)": hyp_stats(rob, ssp, 1.0, 0.5), "exploratorio (1%, m = k)": hyp_stats(rob, ssp, 1.0, 1.0), "exploratorio (10%, m = k/2)": hyp_stats(rob, ssp, pk, 0.5)}
    results[key] = {
        "n_amostra": n, "k_amostra": k, "pk": pk, "cf_min": cf_min, "membros": members, "n_membros_clima": len(members), "n_sorteios": N_DRAWS,
        "variancia": split, "clima": {a: b for a, b in sc.items() if not a.startswith("_")}, "parametros": {a: b for a, b in sp.items() if not a.startswith("_")}, "combinado": comb,
        "item6": item6, "item7_reproducao": repro, "item7": variants, "n_ranked_total": int(len(ranked)),
    }
    json.dump(results, open(OUT / "D2_resultados.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)

json.dump(files, open(OUT / "D2_verificacoes.json", "w", encoding="utf-8"), indent=1)

# ---- figuras
fig, axs = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
names = [f"{i} {t}" for i, t in c.PAIRS]
for ax, (axis, lab) in zip(axs, (("clima (membros, parametros nominais)", "eixo clima"), ("parametros (200 sorteios, clima m0)", "eixo parametros"))):
    cell = [results[p]["variancia"][axis]["log"]["entre_celulas"] * 100 for p in names]
    com = [results[p]["variancia"][axis]["log"]["futuros_comum"] * 100 for p in names]
    inter = [results[p]["variancia"][axis]["log"]["interacao"] * 100 for p in names]
    x = np.arange(len(names))
    ax.bar(x, cell, color="#1f4e79", label="entre celulas")
    ax.bar(x, com, bottom=cell, color="#c9a227", label="deslocamento comum dos futuros")
    ax.bar(x, inter, bottom=np.array(cell) + np.array(com), color="#c00000", label="interacao celula x futuro")
    ax.set_xticks(x, names, rotation=30)
    ax.set_title(f"D2.2, {lab}: partes da variancia de log(LCOE)")
    ax.set_ylabel("% da variancia total")
axs[0].legend(fontsize=8, loc="lower left")
fig.tight_layout()
fig.savefig(OUT / "D2_2_variancia.png", dpi=130)
plt.close(fig)

fig, axs = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
for ax, (tag, lab) in zip(axs, (("clima", "eixo clima"), ("param", "eixo parametros"))):
    data = [np.load(OUT / f"_worst_{p.split()[0]}_{p.split()[1]}_{tag}.npy") for p in names]
    ax.boxplot(data, tick_labels=names, showfliers=True, flierprops={"markersize": 2})
    ax.axhline(2.0, color="#c00000", ls="--", label="limiar k + m = 2k")
    ax.set_yscale("log")
    ax.set_title(f"D2.4, {lab}: pior posto do top-k nominal, em multiplos de k")
    ax.tick_params(axis="x", rotation=30)
axs[0].set_ylabel("pior posto / k (escala log)")
axs[0].legend(fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "D2_4_pior_posto.png", dpi=130)
plt.close(fig)
for p in c.PAIRS:
    for tag in ("clima", "param"):
        (OUT / f"_worst_{p[0]}_{p[1]}_{tag}.npy").unlink()
print("ok")
