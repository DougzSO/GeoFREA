"""COMANDO 201, D1: o tau e o dominio economico. Somente leitura; grava so em _notas_geofrea/diagnostico_v1_0/D1_dados/.

    python d1_run.py            # os seis pares, escreve CSV/JSON/PNG
"""
from __future__ import annotations

import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from scipy.stats import spearmanr

import d1_common as c

DADOS = c.OUT / "D1_dados"
DADOS.mkdir(parents=True, exist_ok=True)
IRENA = yaml.safe_load(open(c.REPO / "config" / "irena_reference.yaml", encoding="utf-8"))
ED = IRENA["editions"]["irena_rpgc_2024"]
LIFE_IRENA = float(ED["life_years"]["value"])
XS = np.arange(20, 201, 5, dtype=float)


def wq(values: np.ndarray, weights: np.ndarray, qs) -> list[float]:
    """Quantis ponderados (inversa da distribuicao acumulada)."""
    o = np.argsort(values)
    v, w = values[o], weights[o]
    cw = np.cumsum(w) / w.sum()
    return [float(v[min(np.searchsorted(cw, q), len(v) - 1)]) for q in qs]


def groups_of(l: np.ndarray) -> dict[str, np.ndarray]:
    p = np.percentile(l, [8, 10, 12, 45, 55, 90])
    return {
        "decil 1 (<= p10)": l <= p[1],
        "banda do p10 (p8 a p12)": (l >= p[0]) & (l <= p[2]),
        "mediana (p45 a p55)": (l >= p[3]) & (l <= p[4]),
        "decil 10 (>= p90)": l >= p[5],
    }


results: dict = {}
cfs_store: dict = {}
curve_rows, cf_rows, dec_rows, abs_rows, sr_rows, h5_rows, h5var_rows = [], [], [], [], [], [], []

for iso, tech in c.PAIRS:
    key = f"{iso} {tech}"
    print(key, flush=True)
    df, res, nom, cells = c.load_cells(iso, tech)
    rob = c.f7_cells(iso, tech)
    ranked = rob[rob["lcoe_nominal"].notna()][["cell_id", "lcoe_nominal", "mr", "sr", "cell_class", "p_mw"]]
    w = df.merge(ranked[["cell_id", "mr", "sr", "cell_class"]], on="cell_id", how="inner")
    n_f6, n_w = len(df), len(w)
    assert (w["lcoe_recon"] - w["lcoe_stored"]).abs().max() == 0.0
    tau = c.tau_of(iso, tech)
    tau_v, t_min, t_max = float(tau["value"]), float(tau["range"]["min"]), float(tau["range"]["max"])
    ir = IRENA["editions"]["irena_rpgc_2024"]["pairs"][iso][tech]
    tic, cf_ref, om_ref, pub = (float(ir[k]["value"]) for k in ("tic_usd_per_kw", "cf", "om_usd_per_kw_yr", "lcoe_usd_per_mwh"))
    pub_p5, pub_p95 = float(ir["lcoe_usd_per_mwh"]["p5"]), float(ir["lcoe_usd_per_mwh"]["p95"])
    rate = float(nom.discount_rate[0])
    L = w["lcoe_recon"].to_numpy()
    P = w["P_MW"].to_numpy()
    info = {
        "n_cells_f6_m0": n_f6, "n_cells_conjunto_f7": n_w, "tau": tau_v, "tau_min": t_min, "tau_max": t_max,
        "irena_lcoe_publicado": pub, "irena_p5": pub_p5, "irena_p95": pub_p95, "cf_referencia": cf_ref,
        "tic_irena": tic, "om_irena": om_ref, "vida_irena": LIFE_IRENA, "vida_modelo": float(nom.lifetime_years[0]),
        "capex_modelo": float(nom.capex_usd_per_kw[0]), "om_modelo_frac": float(nom.opex_fixed_frac[0]),
        "taxa_central": rate, "cf_ref_proxy": bool(ir["cf"].get("regional_proxy", False)),
    }

    # ---- 1. CF da planta de referencia contra o CF das celulas
    for base, col in (("cf_efetivo (energia nominal do kernel)", "cf_eff"), ("cf_F5 (CF gravado no F5, m0)", "cf_f5")):
        v = w[col].to_numpy()
        pc = float((v < cf_ref).mean() * 100)
        pcw = float(P[v < cf_ref].sum() / P.sum() * 100)
        q = np.percentile(v, [10, 50, 90])
        qw = wq(v, P, [0.1, 0.5, 0.9])
        cf_rows.append({
            "par": key, "base": base, "cf_referencia": cf_ref, "percentil_do_cf_ref (celulas)": pc,
            "frac_celulas_cf_maior_igual": float((v >= cf_ref).mean()), "frac_capacidade_cf_maior_igual": float(P[v >= cf_ref].sum() / P.sum()),
            "p10": q[0], "p50": q[1], "p90": q[2], "p10_pond": qw[0], "p50_pond": qw[1], "p90_pond": qw[2], "n": n_w,
        })
    # ---- 2. decomposicao
    cap, om_f = float(nom.capex_usd_per_kw[0]), float(nom.opex_fixed_frac[0])
    life = float(nom.lifetime_years[0])
    base_kw = dict(capex=tic, opex_frac=om_ref / tic, life=LIFE_IRENA, rate=rate, cf=cf_ref, connection=False, degradation=False, loss=False)
    s0 = c.components(w, nom, **base_kw)
    assert np.allclose(s0, s0[0]), "a planta de referencia nao depende da celula"
    info["tau_recalculado"] = float(s0[0])
    steps = [("tau (planta de referencia IRENA)", s0)]
    kw = dict(base_kw)
    kw.update(capex=cap, opex_frac=om_f)
    steps.append(("capex e O&M do modelo", c.components(w, nom, **kw)))
    kw.update(life=life)
    steps.append(("vida util do modelo", c.components(w, nom, **kw)))
    kw.update(cf=None)
    steps.append(("energia da celula (CF)", c.components(w, nom, **kw)))
    kw.update(connection=True, road=False)
    steps.append(("conexao (subestacao)", c.components(w, nom, **kw)))
    kw.update(road=True)
    steps.append(("acesso (estrada)", c.components(w, nom, **kw)))
    kw.update(degradation=True)
    steps.append(("degradacao", c.components(w, nom, **kw)))
    kw.update(loss=True)
    steps.append(("perda de transmissao", c.components(w, nom, **kw)))
    assert np.allclose(steps[-1][1], L, atol=1e-9), "a soma dos passos nao fecha com o LCOE nominal"
    for gname, mask in groups_of(L).items():
        row = {"par": key, "grupo": gname, "n_celulas": int(mask.sum()), "lcoe_medio": float(L[mask].mean()), "tau": float(s0[0])}
        prev = steps[0][1][mask]
        for name, arr in steps[1:]:
            cur = arr[mask]
            row[name] = float((cur - prev).mean())
            prev = cur
        row["diferenca_total"] = float(L[mask].mean() - s0[0])
        row["cf_medio"] = float(w.loc[mask, "cf_eff"].mean())
        row["dist_subestacao_km_media"] = float(w.loc[mask, "dist_sub_km"].mean())
        row["p_mw_media"] = float(w.loc[mask, "P_MW"].mean())
        dec_rows.append(row)
        # termos absolutos do LCOE final (soma = LCOE): capex, O&M fixo, conexao, estrada
        p_ = w["P_MW"].to_numpy()[mask]
        pref = float(nom.reference_project_mw[0])
        a_o = float(c.annuity_factor(rate, life))
        wgt = float(nom.degradation_weight[0])
        d = w["d_low"].to_numpy()[mask] + wgt * (w["d_high"].to_numpy()[mask] - w["d_low"].to_numpy()[mask])
        a_e = c.energy_annuity_factor(rate, d, life)
        den = w["e_nominal_mwh"].to_numpy()[mask] * a_e
        t_capex = 1000 * cap * p_ / den
        t_om = 1000 * cap * om_f * a_o * p_ / den
        t_con = (float(nom.bay_cost_usd[0]) * p_ / pref + w["dist_sub_km"].to_numpy()[mask] * p_ * float(nom.line_cost_usd_per_km[0]) * float(nom.tortuosity_grid[0]) / pref) / den
        t_road = w["dist_road_km"].to_numpy()[mask] * p_ * float(nom.road_cost_usd_per_km[0]) * float(nom.tortuosity_road[0]) / pref / den
        tot = t_capex + t_om + t_con + t_road + float(nom.opex_var_usd_per_mwh[0])
        assert np.allclose(tot, L[mask], atol=1e-9)
        abs_rows.append({"par": key, "grupo": gname, "capex": float(t_capex.mean()), "om_fixo": float(t_om.mean()), "conexao": float(t_con.mean()), "estrada": float(t_road.mean()), "o&m_variavel": float(nom.opex_var_usd_per_mwh[0]), "total": float(tot.mean())})
    # ---- 3. SR
    r = w[w["sr"].notna()]
    sr_, mr_ = r["sr"].to_numpy(), r["mr"].to_numpy()
    both = r["mr"].notna().to_numpy()
    rho_mr = spearmanr(sr_[both], mr_[both])[0] if both.sum() > 2 and sr_[both].std() > 0 else float("nan")
    rho_l = spearmanr(sr_, r["lcoe_recon"].to_numpy())[0] if len(r) > 2 and sr_.std() > 0 else float("nan")
    q = np.percentile(sr_, [25, 50, 75, 90, 99])
    sr_rows.append({
        "par": key, "n_ranqueadas": int(len(r)), "n_com_sr_e_mr": int(both.sum()), "n_sr_nan": int(w["sr"].isna().sum()), "n_conjunto_f7": n_w, "frac_sr_zero": float((sr_ == 0).mean()), "frac_sr_um": float((sr_ == 1).mean()),
        "q25": q[0], "q50": q[1], "q75": q[2], "q90": q[3], "q99": q[4], "max": float(sr_.max()), "media": float(sr_.mean()),
        "spearman_sr_mr": float(rho_mr), "spearman_sr_lcoe_nominal": float(rho_l),
        "frac_celulas_lcoe_nominal_<=_tau": float((L <= tau_v).mean()), "frac_capacidade_lcoe_nominal_<=_tau": float(P[L <= tau_v].sum() / P.sum()),
        "frac_celulas_com_sr_>0": float((sr_ > 0).mean()), "lcoe_p10_celulas": float(np.percentile(L, 10)), "lcoe_p50_celulas": float(np.percentile(L, 50)), "tau": tau_v,
    })
    # ---- 4. curva da fracao de capacidade
    for x in XS:
        curve_rows.append({"par": key, "x_usd_mwh": x, "frac_capacidade": float(P[L <= x].sum() / P.sum()), "frac_celulas": float((L <= x).mean())})
    info["capacidade_total_gw"] = float(P.sum() / 1000)
    for lab, v in (("tau", tau_v), ("tau_min", t_min), ("tau_max", t_max), ("irena_publicado", pub), ("irena_p5", pub_p5), ("irena_p95", pub_p95)):
        info[f"frac_cap_<= {lab}"] = float(P[L <= v].sum() / P.sum())
        info[f"frac_cel_<= {lab}"] = float((L <= v).mean())
    # ---- 5. H5
    h5 = pd.read_parquet(c.paths(iso)["rob"] / f"h5_summary_{tech}__core.parquet")
    h5var = h5[["variant", "tau_usd_per_mwh", "status", "n_domain_cells", "domain_capacity_gw", "e0_twh", "g_twh", "h0_twh"]].copy()
    h5var.insert(0, "par", key)
    h5var_rows.append(h5var)
    prim = h5[h5["primary"]].iloc[0]
    order = np.argsort(L, kind="stable")
    Ls, Ps = L[order], P[order] / 1000.0  # GW
    Es = w["E_MWh"].to_numpy()[order] / 1e6  # TWh
    CFs = w["cf_f5"].to_numpy()[order]
    cumE, cumP = np.cumsum(Es), np.cumsum(Ps)
    k_tau = int((Ls <= tau_v).sum())
    h5_info = {"par": key, "tau": tau_v, "n_dominio_calculado": k_tau, "n_dominio_f7": int(prim["n_domain_cells"]), "e0_calculado_twh": float(cumE[k_tau - 1]) if k_tau else 0.0,
               "e0_f7_twh": float(prim["e0_twh"]), "cap_dominio_calculada_gw": float(cumP[k_tau - 1]) if k_tau else 0.0, "cap_dominio_f7_gw": float(prim["domain_capacity_gw"]),
               "status_f7": prim["status"], "alvo": float(prim["target_value"]) if pd.notna(prim["target_value"]) else None, "unidade_alvo": prim["target_unit"], "g_f7_twh": float(prim["g_twh"]) if pd.notna(prim["g_twh"]) else None,
               "h0_f7_twh": float(prim["h0_twh"]) if pd.notna(prim["h0_twh"]) else None}
    if h5_info["alvo"] is not None and h5_info["unidade_alvo"] == "GW":
        gcap = h5_info["alvo"]

        cumPC = np.cumsum(Ps * CFs)
        j_g = int(np.searchsorted(cumP, gcap))  # primeira posicao em que a capacidade acumulada alcanca o alvo
        if cumP[-1] <= gcap:
            g_arr = 8.76 * gcap * cumPC / cumP  # o alvo excede o dominio inteiro: CFbar do dominio todo, que cresce com k
        else:
            g_arr = 8.76 * gcap * cumPC / cumP
            take_last = gcap - (cumP[j_g - 1] if j_g > 0 else 0.0)
            pc_j = (cumPC[j_g - 1] if j_g > 0 else 0.0) + take_last * CFs[j_g]
            g_const = 8.76 * gcap * pc_j / gcap
            g_arr[j_g:] = g_const  # a partir da celula j_g o CFbar usa so as primeiras gcap GW

        def g_of(k: int) -> float:
            """G = 8,76 x G_cap x CFbar com o dominio das k primeiras celulas em ordem de LCOE (CFbar ponderado pela capacidade ate G_cap GW; ultima celula fracionada)."""
            return float(g_arr[k - 1]) if k else float("nan")

        g_calc = g_of(k_tau)
        h5_info["g_calculado_twh"] = g_calc
        h5_info["h0_calculado_twh"] = float(cumE[k_tau - 1] - g_calc)
        h0 = cumE - g_arr  # H_0 de cada dominio possivel (as k celulas de menor LCOE); o dominio so muda nos LCOE das celulas
        ok = np.flatnonzero(h0 >= 0)
        if len(ok):
            kstar = int(ok[0]) + 1
            h5_info.update({"tau_estrela": float(Ls[kstar - 1]), "n_dominio_tau_estrela": kstar, "cap_dominio_tau_estrela_gw": float(cumP[kstar - 1]), "e0_tau_estrela_twh": float(cumE[kstar - 1]), "g_tau_estrela_twh": g_of(kstar)})
        else:
            h5_info.update({"tau_estrela": None, "nota": "H_0 < 0 mesmo com todas as celulas do conjunto"})
        # H_0(tau) numa grade para a figura
        grade = np.arange(20, 201, 5.0)
        h5_info["h0_grade"] = {str(int(g)): (float(h0[int((Ls <= g).sum()) - 1]) if (Ls <= g).sum() else None) for g in grade}
    h5_rows.append(h5_info)
    results[key] = info
    cfs_store[key] = w["cf_eff"].to_numpy()

pd.DataFrame(curve_rows).to_csv(DADOS / "D1_4_curva_capacidade.csv", index=False)
pd.DataFrame(cf_rows).to_csv(DADOS / "D1_1_cf.csv", index=False)
pd.DataFrame(dec_rows).to_csv(DADOS / "D1_2_decomposicao_passos.csv", index=False)
pd.DataFrame(abs_rows).to_csv(DADOS / "D1_2_termos_absolutos.csv", index=False)
pd.DataFrame(sr_rows).to_csv(DADOS / "D1_3_sr.csv", index=False)
pd.concat(h5var_rows).to_csv(DADOS / "D1_5_h5_variantes_f7.csv", index=False)
json.dump(h5_rows, open(DADOS / "D1_5_h5.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
json.dump(results, open(DADOS / "D1_pares.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)

# ---- figuras
curve = pd.DataFrame(curve_rows)
fig, axs = plt.subplots(2, 3, figsize=(14, 7.5), sharex=True, sharey=True)
for ax, (iso, tech) in zip(axs.flat, c.PAIRS):
    k = f"{iso} {tech}"
    d = curve[curve.par == k]
    ax.plot(d.x_usd_mwh, d.frac_capacidade * 100, color="#1f4e79", lw=2)
    i = results[k]
    ax.axvline(i["tau"], color="#c00000", lw=1.6, label=f"tau primario {i['tau']:.1f}")
    ax.axvspan(i["tau_min"], i["tau_max"], color="#c00000", alpha=0.10, label=f"faixa registrada {i['tau_min']:.1f} a {i['tau_max']:.1f}")
    ax.axvline(i["irena_lcoe_publicado"], color="#2e7d32", lw=1.6, ls="--", label=f"IRENA publicado {i['irena_lcoe_publicado']:.0f}")
    ax.set_title(k)
    ax.set_xlim(20, 200)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, loc="lower right")
for ax in axs[1]:
    ax.set_xlabel("LCOE nominal, m0, USD/MWh")
for ax in axs[:, 0]:
    ax.set_ylabel("% da capacidade com LCOE <= x")
fig.suptitle("D1.4: fracao da capacidade candidata com LCOE nominal <= x (conjunto F7, cenario central)")
fig.tight_layout()
fig.savefig(DADOS / "D1_4_curva_capacidade.png", dpi=130)
plt.close(fig)

fig, axs = plt.subplots(2, 3, figsize=(14, 7.5))
for ax, (iso, tech) in zip(axs.flat, c.PAIRS):
    k = f"{iso} {tech}"
    ax.hist(cfs_store[k], bins=60, color="#7f9fbf")
    ax.axvline(results[k]["cf_referencia"], color="#c00000", lw=1.8, label=f"CF da planta de referencia {results[k]['cf_referencia']:.2f}")
    ax.set_title(k)
    ax.set_xlabel("CF efetivo das celulas (m0)")
    ax.legend(fontsize=8)
fig.suptitle("D1.1: CF da planta de referencia do tau contra o CF das celulas")
fig.tight_layout()
fig.savefig(DADOS / "D1_1_cf.png", dpi=130)
plt.close(fig)
print("ok")
