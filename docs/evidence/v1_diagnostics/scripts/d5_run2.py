# Runs only at tag v1.1 (these scripts import modules of v1 that leave the work tree at COMMAND 306). Kept as documentation of the diagnostics D1 to D5.
"""COMANDO 205, D5 itens 1 e 3: BRA eolica com LCOE > 200; as 5 celulas de menor LCOE de cada par. Somente leitura; grava so em D5_dados/."""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.stats import spearmanr

import d1_common as c
from geofrea.lcoe_modeling.kernel import CellInputs, lcoe_block

OUT = c.OUT / "D5_dados"
OUT.mkdir(parents=True, exist_ok=True)
LIM = 200.0
res = {}

# ======================= ITEM 1: BRA eolica LCOE > 200 =======================
iso, tech = "BRA", "wind"
df, resolved, nominal, cells = c.load_cells(iso, tech)
_, design, samples, cparams, sampler = c.config(iso, tech)
P = c.paths(iso)
rob = c.f7_cells(iso, tech)
cand = pd.read_parquet(P["candidates"] / f"candidates_{tech}__central.parquet", columns=["cell_id", "row", "col", "lat_c", "lon_c", "admin1_id", "eligible_area_km2", "dominant_exclusion", "weibull_a_100m", "weibull_k_100m", "elevation_m"])
df = df.merge(cand, on="cell_id", how="left")
df["lcoe"] = df["lcoe_stored"]
chk = float(np.nanmax(np.abs(df["lcoe_recon"] - df["lcoe_stored"])))
hi = df["lcoe"] > LIM
tau = float(c.tau_of(iso, tech)["value"])
# decomposicao: LCOE sem conexao (so capex, opex, CF)
d0 = c.components(df, nominal, capex=float(nominal.capex_usd_per_kw[0]), opex_frac=float(nominal.opex_fixed_frac[0]), life=float(nominal.lifetime_years[0]), rate=float(nominal.discount_rate[0]), cf=None, connection=False, degradation=True, loss=False)
df["lcoe_sem_conexao"] = d0
df["lcoe_so_cf"] = c.components(df, nominal, capex=float(nominal.capex_usd_per_kw[0]), opex_frac=float(nominal.opex_fixed_frac[0]), life=float(nominal.lifetime_years[0]), rate=float(nominal.discount_rate[0]), cf=None, connection=False, degradation=False, loss=False)
# classes F7
cls = rob.set_index("cell_id")["cell_class"]
df["classe_f7"] = df["cell_id"].map(cls).fillna("fora_do_conjunto_f7")
rb = rob.set_index("cell_id")
df["mr"] = df["cell_id"].map(rb["mr"])
df["sr"] = df["cell_id"].map(rb["sr"])
df["robust_rank"] = df["cell_id"].map(rb["robust_rank"])
df["nominal_rank"] = df["cell_id"].map(rb["nominal_rank"])
df["topk_robust"] = df["cell_id"].map(rb["topk_robust"])
df["topk_nominal"] = df["cell_id"].map(rb["topk_nominal"])


def q(s, ps=(0.05, 0.5, 0.95)):
    return {f"p{int(p*100)}": float(s.quantile(p)) for p in ps}


def grp(d):
    return {"n": int(len(d)), "capacidade_mw": float(d["P_MW"].sum()), "cf_f5": q(d["cf_f5"]), "cf_eff": q(d["cf_eff"]), "dist_sub_km": q(d["dist_sub_km"]), "dist_road_km": q(d["dist_road_km"]),
            "lcoe": q(d["lcoe"], (0.05, 0.5, 0.95, 0.99)), "weibull_a": q(d["weibull_a_100m"]), "area_elegivel_km2": q(d["eligible_area_km2"]), "elevacao_m": q(d["elevation_m"])}


all_n, all_mw = len(df), float(df["P_MW"].sum())
res["item1"] = {
    "conferencia_lcoe_recon_vs_gravado_max_abs": chk, "limiar": LIM, "tau": tau, "n_celulas_f6": all_n, "capacidade_f6_mw": all_mw,
    "acima": grp(df[hi]), "abaixo": grp(df[~hi]),
    "n_acima": int(hi.sum()), "frac_n_acima": float(hi.mean()), "frac_cap_acima": float(df.loc[hi, "P_MW"].sum() / all_mw),
    "lcoe_maximo": float(df["lcoe"].max()), "acima_de_500": int((df["lcoe"] > 500).sum()), "acima_de_1000": int((df["lcoe"] > 1000).sum()), "acima_de_2000": int((df["lcoe"] > 2000).sum()),
    "classes_f7_das_acima": df.loc[hi, "classe_f7"].value_counts().to_dict(),
    "classes_f7_das_abaixo": df.loc[~hi, "classe_f7"].value_counts().to_dict(),
    "causa": {
        "acima_com_lcoe_sem_conexao_ainda_acima": int((hi & (df["lcoe_sem_conexao"] > LIM)).sum()),
        "acima_com_lcoe_so_cf_ainda_acima": int((hi & (df["lcoe_so_cf"] > LIM)).sum()),
        "parcela_conexao_mediana_nas_acima": float(((df["lcoe"] - df["lcoe_sem_conexao"]) / df["lcoe"])[hi].median()),
        "parcela_conexao_mediana_nas_abaixo": float(((df["lcoe"] - df["lcoe_sem_conexao"]) / df["lcoe"])[~hi].median()),
        "cf_min_das_acima": float(df.loc[hi, "cf_f5"].min()), "cf_max_das_acima": float(df.loc[hi, "cf_f5"].max()),
        "cf_necessario_p_200_sem_conexao_mediana": None,
    },
}
# CF de corte: que CF produziria LCOE = 200 sem conexao, para a celula mediana (capex, opex, vida nominais)
a_o = float(__import__("geofrea.lcoe_modeling.kernel", fromlist=["annuity_factor"]).annuity_factor(float(nominal.discount_rate[0]), float(nominal.lifetime_years[0])))
cap_per_mwh_at_cf1 = 1000.0 * float(nominal.capex_usd_per_kw[0]) * (1 + float(nominal.opex_fixed_frac[0]) * a_o) / (a_o * 8760.0)
res["item1"]["causa"]["cf_para_lcoe_200_so_capex_opex"] = cap_per_mwh_at_cf1 / LIM
res["item1"]["causa"]["cf_para_lcoe_tau_so_capex_opex"] = cap_per_mwh_at_cf1 / tau
# onde
df["faixa_lat"] = (np.floor(df["lat_c"] / 5) * 5).astype(int)
df["faixa_lon"] = (np.floor(df["lon_c"] / 5) * 5).astype(int)
byadm = df.groupby("admin1_id").agg(n=("cell_id", "size"), n_acima=("lcoe", lambda s: int((s > LIM).sum())), cap_mw=("P_MW", "sum")).assign(frac=lambda t: t["n_acima"] / t["n"]).sort_values("n_acima", ascending=False)
byadm["cap_acima_mw"] = df[hi].groupby("admin1_id")["P_MW"].sum().reindex(byadm.index).fillna(0.0)
byadm.to_csv(OUT / "D5_item1_por_admin1.csv")
bylat = df.groupby(["faixa_lat", "faixa_lon"]).agg(n=("cell_id", "size"), n_acima=("lcoe", lambda s: int((s > LIM).sum()))).assign(frac=lambda t: t["n_acima"] / t["n"])
bylat.to_csv(OUT / "D5_item1_por_faixa.csv")
res["item1"]["onde"] = {"n_admin1": int(len(byadm)), "n_admin1_com_acima": int((byadm["n_acima"] > 0).sum()), "top5_admin1_por_n_acima": byadm.head(5)[["n", "n_acima", "frac"]].reset_index().to_dict("records"),
                        "top3_admin1_participacao_nas_acima": float(byadm["n_acima"].head(3).sum() / byadm["n_acima"].sum()),
                        "admin1_com_mais_de_90pct_acima": int((byadm["frac"] > 0.9).sum()), "admin1_com_menos_de_10pct_acima": int((byadm["frac"] < 0.1).sum()),
                        "dominante_exclusao_acima": df.loc[hi, "dominant_exclusion"].value_counts().to_dict(), "dominante_exclusao_abaixo": df.loc[~hi, "dominant_exclusion"].value_counts().to_dict()}
# lat/lon medianas
res["item1"]["onde"]["lat_mediana_acima"] = float(df.loc[hi, "lat_c"].median())
res["item1"]["onde"]["lat_mediana_abaixo"] = float(df.loc[~hi, "lat_c"].median())
res["item1"]["onde"]["lon_mediana_acima"] = float(df.loc[hi, "lon_c"].median())
res["item1"]["onde"]["lon_mediana_abaixo"] = float(df.loc[~hi, "lon_c"].median())

# efeito em L*, MR, SR, k
f7 = df[df["classe_f7"] != "fora_do_conjunto_f7"]
rk = f7[f7["classe_f7"] == "ranked"]
hi_rk = rk["lcoe"] > LIM
fut = pd.read_parquet(P["rob"] / "futures_wind__core.parquet", columns=["member", "sample", "lowest_lcoe"])
lstar_max, lstar_min = float(fut["lowest_lcoe"].max()), float(fut["lowest_lcoe"].min())
# limite inferior do LCOE de cada celula acima: minimo, nos 4000 sorteios, do LCOE do membro m0 e razao minima entre membros
ids_hi = df.loc[hi, "cell_id"].to_numpy()
sub = df[hi].reset_index(drop=True)
mins = np.empty(len(sub))
BL = 2000
for i in range(0, len(sub), BL):
    s = sub.iloc[i:i + BL]
    ci = CellInputs(p_mw=s["P_MW"].to_numpy(), dist_sub_km=s["dist_sub_km"].to_numpy(), dist_road_km=s["dist_road_km"].to_numpy(), energy_mwh=s["E_MWh"].to_numpy(), energy_offset=s["offset"].to_numpy(), energy_slope=s["slope"].to_numpy(),
                    degradation_low=s["d_low"].to_numpy(), degradation_high=s["d_high"].to_numpy())
    mins[i:i + BL] = np.nanmin(lcoe_block(ci, samples), axis=1)
sub["min_sorteios_m0"] = mins
nm = pd.read_parquet(P["rob"] / "nominal_lcoe_by_member_wind__core.parquet")
nm = nm[nm["cell_id"].isin(ids_hi)]
piv = nm.groupby("cell_id")["lcoe_nominal"].agg(["min", "max", "count"])
m0n = nm[nm["member"] == "m0"].set_index("cell_id")["lcoe_nominal"]
ratio_min = (piv["min"] / m0n.reindex(piv.index)).reindex(sub["cell_id"]).to_numpy()
sub["razao_min_membro"] = ratio_min
sub["limite_inferior_aprox"] = sub["min_sorteios_m0"] * np.where(np.isfinite(ratio_min), ratio_min, 1.0)
res["item1"]["efeito"] = {
    "n_f7": int(len(f7)), "n_ranked": int(len(rk)), "n_acima_no_f7": int((f7["lcoe"] > LIM).sum()), "n_acima_ranked": int(hi_rk.sum()), "cap_acima_ranked_mw": float(rk.loc[hi_rk, "P_MW"].sum()),
    "lstar_min_entre_futuros": lstar_min, "lstar_max_entre_futuros": lstar_max, "lstar_mediana": float(fut["lowest_lcoe"].median()),
    "limite_inferior_aprox_das_acima_minimo": float(sub["limite_inferior_aprox"].min()), "limite_inferior_aprox_das_acima_p1": float(sub["limite_inferior_aprox"].quantile(0.01)),
    "razao_min_sorteios_sobre_nominal_min_das_acima": float((sub["min_sorteios_m0"] / sub["lcoe"]).min()),
    "razao_min_membro_min_das_acima": float(np.nanmin(ratio_min)),
    "n_acima_com_limite_inferior_menor_que_lstar_max": int((sub["limite_inferior_aprox"] < lstar_max).sum()),
    "mr_acima": q(rk.loc[hi_rk, "mr"], (0.0, 0.05, 0.5, 0.95)), "mr_abaixo": q(rk.loc[~hi_rk, "mr"], (0.0, 0.05, 0.5, 0.95)),
    "sr_acima_max": float(rk.loc[hi_rk, "sr"].max()), "sr_acima_media": float(rk.loc[hi_rk, "sr"].mean()), "sr_abaixo_media": float(rk.loc[~hi_rk, "sr"].mean()),
    "acima_no_topk_robusto": int((rk.loc[hi_rk, "topk_robust"]).sum()), "acima_no_topk_nominal": int((rk.loc[hi_rk, "topk_nominal"]).sum()),
    "mr_min_acima_vs_mr_do_corte": None,
}
k_full = int(rk["topk_robust"].sum())
k_nom_full = int(rk["topk_nominal"].sum())
kn = len(f7)
res["item1"]["efeito"]["k_robusto_no_f7"] = k_full
k_exc = math.ceil(0.10 * (len(f7) - int((f7["lcoe"] > LIM).sum())))
res["item1"]["efeito"]["k_se_excluisse_as_acima"] = k_exc
# o conjunto top-k robusto e aninhado: maior corte de MR entre as top-k
cut_full = float(rk.loc[rk["topk_robust"], "mr"].max())
res["item1"]["efeito"]["mr_max_no_topk"] = cut_full
res["item1"]["efeito"]["mr_min_acima_vs_mr_do_corte"] = float(rk.loc[hi_rk, "mr"].min() / cut_full) if cut_full > 0 else None
# Spearman (LCOE, MR) e Jaccard nominal x robusto, completo vs sem as acima
rho_all = float(spearmanr(rk["lcoe"], rk["mr"]).statistic)
sub_rk = rk[~hi_rk]
rho_low = float(spearmanr(sub_rk["lcoe"], sub_rk["mr"]).statistic)
def topk_set(d, col, k):
    return set(d.nsmallest(k, col)["cell_id"].tolist())
k_all = math.ceil(0.10 * len(rk))
j_all = len(topk_set(rk, "lcoe", k_all) & topk_set(rk, "mr", k_all)) / len(topk_set(rk, "lcoe", k_all) | topk_set(rk, "mr", k_all))
k_low = math.ceil(0.10 * len(sub_rk))
j_low = len(topk_set(sub_rk, "lcoe", k_low) & topk_set(sub_rk, "mr", k_low)) / len(topk_set(sub_rk, "lcoe", k_low) | topk_set(sub_rk, "mr", k_low))
res["item1"]["efeito"].update({"spearman_lcoe_mr_todas": rho_all, "spearman_lcoe_mr_sem_acima": rho_low, "jaccard_top10_nom_rob_todas": j_all, "jaccard_top10_nom_rob_sem_acima": j_low, "k_ranked": k_all, "k_ranked_sem_acima": k_low})
# celulas tau: quantas abaixo de tau no nominal
res["item1"]["efeito"]["n_abaixo_tau_nominal_f7"] = int((f7["lcoe"] <= tau).sum())
res["item1"]["efeito"]["capacidade_abaixo_tau_nominal_mw"] = float(f7.loc[f7["lcoe"] <= tau, "P_MW"].sum())
df[["cell_id", "lat_c", "lon_c", "admin1_id", "P_MW", "cf_f5", "dist_sub_km", "dist_road_km", "lcoe", "lcoe_sem_conexao", "classe_f7", "mr", "sr", "robust_rank"]].assign(acima=hi).to_parquet(OUT / "D5_item1_celulas.parquet", index=False)

# ======================= ITEM 3: as 5 celulas de menor LCOE de cada par =======================
rows = []
pairs_info = {}
for iso, tech in c.PAIRS:
    d, resolved, nominal, cells = c.load_cells(iso, tech)
    P = c.paths(iso)
    candc = ["cell_id", "row", "col", "lat_c", "lon_c", "cell_area_km2", "eligible_area_km2", "dominant_exclusion", "dist_grid_km", "dist_sub_capped_share", "dist_road_capped_share", "admin1_id"]
    if tech == "wind":
        candc += ["weibull_a_100m", "weibull_k_100m", "elevation_m"]
    cand_all = pd.read_parquet(P["candidates"] / f"candidates_{tech}__central.parquet", columns=candc)
    d = d.merge(cand_all, on="cell_id", how="left")
    rb = c.f7_cells(iso, tech).set_index("cell_id")
    d["classe_f7"] = d["cell_id"].map(rb["cell_class"]).fillna("fora_do_conjunto_f7")
    d["mr"] = d["cell_id"].map(rb["mr"])
    d["robust_rank"] = d["cell_id"].map(rb["robust_rank"])
    d["nominal_rank"] = d["cell_id"].map(rb["nominal_rank"])
    d["lcoe"] = d["lcoe_stored"]
    tau_p = float(c.tau_of(iso, tech)["value"])
    # vizinhanca: 8 vizinhos na tabela de candidatas (todas as celulas com area elegivel > 0 no cenario central)
    key = set(zip(cand_all["row"].tolist(), cand_all["col"].tolist()))
    def nb(r, cc):
        return sum(((r + a, cc + b) in key) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0))
    d["n_vizinhas_candidatas"] = [nb(r, cc) for r, cc in zip(d["row"].to_numpy(), d["col"].to_numpy())]
    dd = d.set_index(["row", "col"])["lcoe"]
    def nbmean(r, cc):
        v = [dd.get((r + a, cc + b), np.nan) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
        v = [x for x in v if np.isfinite(x)]
        return float(np.mean(v)) if v else np.nan
    low5 = d.nsmallest(5, "lcoe").copy()
    low5["lcoe_vizinhas_media"] = [nbmean(r, cc) for r, cc in zip(low5["row"], low5["col"])]
    # contexto do par
    cfq = d["cf_f5"].quantile([0.5, 0.99, 0.999]).to_dict()
    dsq = d["dist_sub_km"].quantile([0.01, 0.05, 0.5]).to_dict()
    pairs_info[f"{iso} {tech}"] = {"n_celulas": int(len(d)), "tau": tau_p, "lcoe_min": float(d["lcoe"].min()), "lcoe_p1": float(d["lcoe"].quantile(0.01)), "lcoe_mediana": float(d["lcoe"].median()),
                                   "cf_mediana": float(cfq[0.5]), "cf_p99": float(cfq[0.99]), "cf_p999": float(cfq[0.999]), "cf_max": float(d["cf_f5"].max()),
                                   "dist_sub_p1": float(dsq[0.01]), "dist_sub_p5": float(dsq[0.05]), "dist_sub_mediana": float(dsq[0.5]),
                                   "n_dist_sub_zero": int((d["dist_sub_km"] <= 0).sum()), "n_dist_sub_menor_1km": int((d["dist_sub_km"] < 1).sum()), "n_dist_road_zero": int((d["dist_road_km"] <= 0).sum()),
                                   "n_vizinhas_mediana": float(d["n_vizinhas_candidatas"].median()), "n_celulas_com_menos_de_8_vizinhas": int((d["n_vizinhas_candidatas"] < 8).sum())}
    for rank, (_, r) in enumerate(low5.iterrows(), start=1):
        base = c.components(d.loc[[r.name]].reset_index(drop=True), nominal, capex=float(nominal.capex_usd_per_kw[0]), opex_frac=float(nominal.opex_fixed_frac[0]), life=float(nominal.lifetime_years[0]), rate=float(nominal.discount_rate[0]), cf=None, connection=False, degradation=True, loss=False)[0]
        rows.append({
            "par": f"{iso} {tech}", "posicao": rank, "cell_id": int(r["cell_id"]), "lat": float(r["lat_c"]), "lon": float(r["lon_c"]), "admin1": r["admin1_id"], "lcoe": float(r["lcoe"]), "lcoe_sem_conexao": float(base),
            "parcela_conexao": float((r["lcoe"] - base) / r["lcoe"]), "cf_f5": float(r["cf_f5"]), "cf_efetivo": float(r["cf_eff"]), "cf_percentil_no_par": float((d["cf_f5"] < r["cf_f5"]).mean()),
            "dist_sub_km": float(r["dist_sub_km"]), "dist_sub_percentil": float((d["dist_sub_km"] < r["dist_sub_km"]).mean()), "dist_road_km": float(r["dist_road_km"]), "dist_grid_km": float(r["dist_grid_km"]),
            "dist_sub_capped_share": float(r["dist_sub_capped_share"]), "dist_road_capped_share": float(r["dist_road_capped_share"]),
            "zona_pv": None if "pvcz_zone" not in d.columns else (None if pd.isna(r.get("pvcz_zone")) else int(r["pvcz_zone"])),
            "p_mw": float(r["P_MW"]), "area_elegivel_km2": float(r["eligible_area_km2"]), "area_celula_km2": float(r["cell_area_km2"]), "frac_elegivel": float(r["eligible_area_km2"] / r["cell_area_km2"]),
            "n_vizinhas_candidatas": int(r["n_vizinhas_candidatas"]), "lcoe_vizinhas_media": float(r["lcoe_vizinhas_media"]), "razao_lcoe_vizinhas": float(r["lcoe"] / r["lcoe_vizinhas_media"]) if np.isfinite(r["lcoe_vizinhas_media"]) else None,
            "dominante_exclusao": r["dominant_exclusion"], "classe_f7": r["classe_f7"], "nominal_rank_f7": None if pd.isna(r["nominal_rank"]) else int(r["nominal_rank"]), "robust_rank_f7": None if pd.isna(r["robust_rank"]) else int(r["robust_rank"]), "mr": None if pd.isna(r["mr"]) else float(r["mr"]),
            "weibull_a_100m": None if tech != "wind" else float(r["weibull_a_100m"]), "weibull_k_100m": None if tech != "wind" else float(r["weibull_k_100m"]), "elevacao_m": None if tech != "wind" else float(r["elevation_m"]),
            "lcoe_recon_menos_gravado": float(r["lcoe_recon"] - r["lcoe_stored"]),
        })
    print(iso, tech, "ok")
t3 = pd.DataFrame(rows)
t3.to_csv(OUT / "D5_item3_menores.csv", index=False)
res["item3_pares"] = pairs_info
json.dump(res, open(OUT / "D5_item1_item3.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
print(json.dumps(res["item1"], indent=1, default=str)[:6000])
pd.set_option("display.width", 300)
pd.set_option("display.max_columns", 60)
print(t3.to_string())
print(json.dumps(pairs_info, indent=1))
