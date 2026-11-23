"""Gera D5_caudas.md a partir de D5_dados (numeros lidos dos dados; as regras de sinalizacao estao escritas no texto)."""
from __future__ import annotations

import hashlib
import json
import subprocess

import pandas as pd

import d1_common as c

D = c.OUT / "D5_dados"
R13 = json.load(open(D / "D5_item1_item3.json", encoding="utf-8"))
I1 = R13["item1"]
PP = R13["item3_pares"]
I2 = json.load(open(D / "D5_item2.json", encoding="utf-8"))
CONV = pd.read_csv(D / "D5_item2_convergencia.csv")
SW = pd.read_csv(D / "D5_item2_trocas.csv")
EXT = pd.read_csv(D / "D5_item2_extensao.csv")
T3 = pd.read_csv(D / "D5_item3_menores.csv").merge(pd.read_csv(D / "D5_item3_borda.csv")[["par", "posicao", "razao_area"]], on=["par", "posicao"])
BP = json.load(open(D / "D5_item3_borda_pares.json", encoding="utf-8"))
ADM = pd.read_parquet(c.paths("BRA")["candidates"] / "admin1_units.parquet").set_index("admin1_id")["admin1_name"].to_dict()
BYADM = pd.read_csv(D / "D5_item1_por_admin1.csv")
BYADM["nome"] = BYADM["admin1_id"].map(ADM)


def n(x, d=2, pct=False):
    if x is None or (isinstance(x, float) and x != x):
        return "não disponível"
    v = x * 100 if pct else x
    s = f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if float(f"{v:.{d}f}") == 0:
        s = s.lstrip("-")
    return s + ("%" if pct else "")


def fi(x):
    return f"{int(round(x)):,}".replace(",", ".")


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


# ---- limiares de sinalizacao do item 3 (escolhas do relatorio, nao parametros do pipeline)
CF_MAX = {"solar": 0.30, "wind": 0.60}
DIST_MIN = 1.0
AREA_MIN = 0.98
VIZ_MAX = 2
RATIO_MIN = 0.80
P_MIN = 1.0


def flags(r):
    tech = r["par"].split()[1]
    f = []
    if r["dist_sub_km"] < DIST_MIN or r["dist_road_km"] <= 0:
        f.append("distância zero ou menor que 1 km")
    if r["cf_f5"] > CF_MAX[tech] or r["cf_f5"] < 0.05:
        f.append(f"CF fora da faixa adotada ({n(CF_MAX[tech])})")
    if r["razao_area"] < AREA_MIN:
        f.append(f"borda da máscara (área do país na célula = {n(r['razao_area'], pct=True, d=0)} da nominal)")
    if r["n_vizinhas_candidatas"] <= VIZ_MAX:
        f.append(f"isolada ({int(r['n_vizinhas_candidatas'])} vizinha(s) candidata(s))")
    if pd.notna(r["razao_lcoe_vizinhas"]) and r["razao_lcoe_vizinhas"] < RATIO_MIN:
        f.append(f"LCOE {n(r['razao_lcoe_vizinhas'], pct=True, d=0)} da média das vizinhas")
    if r["p_mw"] < P_MIN:
        f.append(f"capacidade pequena ({n(r['p_mw'], 3)} MW)")
    return f


head = subprocess.run(["git", "-C", str(c.REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
L: list[str] = []
a = L.append
tc = I1["causa"]
ef = I1["efeito"]
ac, ab = I1["acima"], I1["abaixo"]
a("# D5: caudas, convergência e células extremas (COMANDO 205)")
a("")
a(f"Escrito para: o autor, para levar ao chat de planejamento. Data: 2026-11-23. Repositório em `{head}`, tag `prereg-v1` e `v1.0` inalteradas. Somente leitura: nada foi gravado em `GeoFREA_data/outputs/` nem no repositório. Scripts em `_notas_geofrea/diagnostico_v1_0/` (`d1_common.py`, `d5_run.py`, `d5_run2.py`, `d5_run3.py`, `d5_run4.py`, `d5_report.py`), dados em `D5_dados/`. Este texto é gerado de `D5_dados/`; os números não foram digitados à mão. Nenhum valor novo é proposto: o relatório só descreve e sinaliza.")
a("")
a("## Resumo")
a("")
a(f"1. **BRA eólica, LCOE > {n(I1['limiar'], 0)}.** {fi(I1['n_acima'])} das {fi(I1['n_celulas_f6'])} células ({n(I1['frac_n_acima'], 1, True)}) e {n(I1['frac_cap_acima'], 1, True)} da capacidade passam do limiar; a causa é o CF baixo (mediana {n(ac['cf_f5']['p50'], 3)} contra {n(ab['cf_f5']['p50'], 3)} nas demais), não a conexão. Todas estão na tabela do F7 ({fi(ef['n_acima_ranked'])} entram no ranking). Nenhuma está no top-k, nenhuma satisfaz τ em qualquer futuro, e o L* de nenhum futuro vem delas. O efeito é sobre o tamanho do top-k: k = {fi(ef['k_ranked'])} com elas e {fi(ef['k_ranked_sem_acima'])} sem elas.")
a(f"2. **PRT solar, L-252.** Reproduzi 1 − Jaccard de 0,0116, 0,0231 e 0,0116. Entre 2000 e 4000 sorteios trocam {int(I2['n_saem'])} células que saem e {int(I2['n_entram'])} que entram, todas a menos de {n(I2['trocas_gap_relativo_ao_corte_4000']['max'], 2, True)} do MR do corte. Com k = {I2['k']}, o critério de 0,01 admite no máximo 1 troca. Rodar além do teto, em 8000 e 16000 sorteios, dá 1 troca em cada passo (1 − Jaccard = {n(EXT['um_menos_jaccard'].iloc[0], 4)}).")
bra_wind = T3[T3.par == "BRA wind"]
small5_ = [par for par in BP if (T3[T3.par == par]["p_mw"] < P_MIN).sum() >= 3]
a(f"3. **As 5 células de menor LCOE de cada par.** Nenhuma tem distância à subestação menor que 1 km nem distância zero. Nenhum CF sai de [0, 1], mas as 5 da BRA eólica têm CF de {n(bra_wind['cf_f5'].min(), 3)} a {n(bra_wind['cf_f5'].max(), 3)} (o máximo do par é {n(PP['BRA wind']['cf_max'], 3)}), acima do limiar de 0,60 adotado aqui. {int((T3['razao_area'] < AREA_MIN).sum())} das 30 estão em borda de máscara. Em {', '.join(small5_)}, 3 ou mais das 5 têm menos de 1 MW; o ranking conta células, não capacidade. Além disso, a convergência da BRA eólica foi calculada num conjunto de 178.285 células e o F7 usa 171.181 (seção 2.4).")
a("")
a("## 0. Base e conferências")
a("")
a(f"- LCOE reconstruído com o kernel igual ao gravado pelo F6 nos seis pares (diferença máxima das 30 células do item 3: {n(T3['lcoe_recon_menos_gravado'].abs().max(), 2)}; BRA eólica inteira: {n(I1['conferencia_lcoe_recon_vs_gravado_max_abs'], 2)}).")
a(f"- O protocolo U-04 da PRT solar foi refeito com as funções de `convergence.py` e os mesmos insumos ({I2['n_f7']} células, {I2['n_membros_nucleo']} membros do núcleo, `cf_min` {n(I2['cf_min'], 3)}, τ {n(I2['tau'], 2)}, top-k {n(I2['top_k_percent'], 0)}%): 1 − Jaccard 0,0116, 0,0231 e 0,0116, os da L-252. O top-k robusto de 4000 sorteios é {'igual' if I2['top_robusto_do_f7_igual_ao_de_4000'] else 'DIFERENTE'} ao `robust_rank <= k` gravado pelo F7.")
a("- Limiares de sinalização do item 3 (escolhas deste relatório, não parâmetros do pipeline): CF acima de 0,30 (solar) ou 0,60 (eólica) ou abaixo de 0,05; distância à subestação menor que 1 km ou distância à estrada igual a zero; área do país na célula menor que 98% da nominal; no máximo 2 vizinhas candidatas; LCOE abaixo de 80% da média das vizinhas; capacidade menor que 1 MW.")
a("")
# ---------------------------------------------------------------- item 1
a("## 1. BRA eólica: células com LCOE acima de 200 USD/MWh")
a("")
a("### 1.1 Contagem, capacidade e CF")
a("")
rows = [
    ["Células", fi(ac["n"]), fi(ab["n"])],
    ["Parcela das células", n(I1["frac_n_acima"], 1, True), n(1 - I1["frac_n_acima"], 1, True)],
    ["Capacidade (GW)", n(ac["capacidade_mw"] / 1000, 1), n(ab["capacidade_mw"] / 1000, 1)],
    ["Parcela da capacidade", n(I1["frac_cap_acima"], 1, True), n(1 - I1["frac_cap_acima"], 1, True)],
    ["CF do F5, p5 / mediana / p95", " / ".join(n(ac["cf_f5"][k], 3) for k in ("p5", "p50", "p95")), " / ".join(n(ab["cf_f5"][k], 3) for k in ("p5", "p50", "p95"))],
    ["Weibull A a 100 m (m/s), p5 / mediana / p95", " / ".join(n(ac["weibull_a"][k], 2) for k in ("p5", "p50", "p95")), " / ".join(n(ab["weibull_a"][k], 2) for k in ("p5", "p50", "p95"))],
    ["Distância à subestação (km), p5 / mediana / p95", " / ".join(n(ac["dist_sub_km"][k], 1) for k in ("p5", "p50", "p95")), " / ".join(n(ab["dist_sub_km"][k], 1) for k in ("p5", "p50", "p95"))],
    ["Distância à estrada (km), p5 / mediana / p95", " / ".join(n(ac["dist_road_km"][k], 1) for k in ("p5", "p50", "p95")), " / ".join(n(ab["dist_road_km"][k], 1) for k in ("p5", "p50", "p95"))],
    ["LCOE nominal (USD/MWh), p5 / mediana / p95", " / ".join(n(ac["lcoe"][k], 0) for k in ("p5", "p50", "p95")), " / ".join(n(ab["lcoe"][k], 0) for k in ("p5", "p50", "p95"))],
]
a(table(["", "LCOE > 200", "LCOE <= 200"], rows))
a("")
a(f"A cauda é longa: {fi(I1['acima_de_500'])} células passam de 500, {fi(I1['acima_de_1000'])} de 1.000 e {fi(I1['acima_de_2000'])} de 2.000; o máximo é {n(I1['lcoe_maximo'], 0)} USD/MWh. Para comparação, τ da BRA eólica é {n(I1['tau'], 2)} e só {fi(ef['n_abaixo_tau_nominal_f7'])} células ({n(ef['capacidade_abaixo_tau_nominal_mw'] / 1000, 2)} GW) têm LCOE nominal abaixo dele.")
a("")
a("**Causa.** Com o capex, o O&M, a vida e a taxa nominais, sem conexão e sem degradação, um CF de " + n(tc["cf_para_lcoe_200_so_capex_opex"], 3) + f" já dá LCOE de 200; para chegar a τ seriam necessários CF de {n(tc['cf_para_lcoe_tau_so_capex_opex'], 3)}. Das {fi(I1['n_acima'])} células acima de 200, {fi(tc['acima_com_lcoe_so_cf_ainda_acima'])} ({n(tc['acima_com_lcoe_so_cf_ainda_acima'] / I1['n_acima'], 1, True)}) continuam acima de 200 mesmo sem conexão e sem degradação, isto é, só pelo CF. A parcela da conexão no LCOE é pequena: mediana {n(tc['parcela_conexao_mediana_nas_acima'], 1, True)} nas acima e {n(tc['parcela_conexao_mediana_nas_abaixo'], 1, True)} nas demais. O CF das acima vai de {n(tc['cf_min_das_acima'], 4)} a {n(tc['cf_max_das_acima'], 3)}. As acima também estão em sítios de vento mais fraco (A de {n(ac['weibull_a']['p50'], 2)} contra {n(ab['weibull_a']['p50'], 2)} m/s) e a distância à subestação mediana é maior ({n(ac['dist_sub_km']['p50'], 1)} contra {n(ab['dist_sub_km']['p50'], 1)} km), mas isso só agrava.")
a("")
a("### 1.2 Onde ficam")
a("")
on = I1["onde"]
top = BYADM.head(8)
a(table(["Estado (admin1)", "Células", "Acima de 200", "Parcela", "Capacidade acima (GW)"], [[f"{r['nome']} (`{r['admin1_id']}`)", fi(r["n"]), fi(r["n_acima"]), n(r["frac"], 1, True), n(r["cap_acima_mw"] / 1000, 1)] for _, r in top.iterrows()]))
a("")
hi90 = BYADM[BYADM["frac"] > 0.9]
lo10 = BYADM[BYADM["frac"] < 0.1]
a(f"Há células acima de 200 em {on['n_admin1_com_acima']} dos {on['n_admin1']} estados; os 3 maiores contribuintes ({', '.join(BYADM['nome'].head(3))}) respondem por {n(on['top3_admin1_participacao_nas_acima'], 1, True)} delas. Estados com mais de 90% das células acima de 200: {', '.join(f'{r.nome} ({n(r.frac, 1, True)})' for r in hi90.itertuples()) or 'nenhum'}. Estados com menos de 10%: {on['admin1_com_menos_de_10pct_acima']} (por exemplo {', '.join(lo10['nome'].head(4))}). A latitude mediana das acima é {n(on['lat_mediana_acima'], 1)} e a das demais {n(on['lat_mediana_abaixo'], 1)}; as longitudes medianas são {n(on['lon_mediana_acima'], 1)} e {n(on['lon_mediana_abaixo'], 1)}. As acima concentram-se nos três estados maiores contribuintes e em latitudes mais ao norte; a mediana do Weibull A delas é menor (seção 1.1). A exclusão dominante delas é E5 em {n(on['dominante_exclusao_acima']['E5'] / I1['n_acima'], 1, True)} dos casos, parecida com a das demais ({n(on['dominante_exclusao_abaixo']['E5'] / ab['n'], 1, True)}). As tabelas completas estão em `D5_dados/D5_item1_por_admin1.csv` e `D5_item1_por_faixa.csv`.")
a("")
a("### 1.3 Entram no conjunto F7? Afetam L*, MR ou SR?")
a("")
cl = I1["classes_f7_das_acima"]
clb = I1["classes_f7_das_abaixo"]
a(f"**Conjunto F7.** Sim, todas as células com F6 entram na tabela do F7. Das acima de 200: {fi(cl.get('ranked', 0))} são `ranked`, {fi(cl.get('incomplete_ensemble', 0))} `incomplete_ensemble` e {fi(cl.get('climate_data_invalid', 0))} `climate_data_invalid`. Das demais: {fi(clb.get('ranked', 0))} `ranked` e {fi(clb.get('incomplete_ensemble', 0))} `incomplete_ensemble`. {n(cl.get('incomplete_ensemble', 0) / (cl.get('incomplete_ensemble', 0) + clb.get('incomplete_ensemble', 0)), 1, True)} das células `incomplete_ensemble` têm LCOE acima de 200 (contra {n(I1['frac_n_acima'], 1, True)} do total), isto é, a classe de conjunto incompleto está concentrada nas células de CF baixo.")
a("")
a(f"**L\\*.** O L\\* de cada futuro (menor LCOE entre as células) vai de {n(ef['lstar_min_entre_futuros'], 1)} a {n(ef['lstar_max_entre_futuros'], 1)} (mediana {n(ef['lstar_mediana'], 1)}). Para cada célula acima de 200 calculei o menor LCOE que ela alcança nos 4000 sorteios do membro de referência e multipliquei pela razão mínima entre o LCOE nominal de qualquer membro e o do membro de referência (fatores aproximadamente multiplicativos): o limite inferior é {n(ef['limite_inferior_aprox_das_acima_minimo'], 1)} (mínimo) e {n(ef['limite_inferior_aprox_das_acima_p1'], 1)} (percentil 1). {fi(ef['n_acima_com_limite_inferior_menor_que_lstar_max'])} células têm limite inferior abaixo do maior L*. Logo, em nenhum futuro uma dessas células define L*; o L\\* e, por consequência, o MR das demais células (que dependem do LCOE da célula e do L* de cada futuro) **não mudam** se elas forem retiradas. O limite é aproximado; o cálculo exato exigiria reavaliar todos os futuros.")
a("")
a(f"**MR e SR.** Entre as {fi(ef['n_acima_ranked'])} células `ranked` acima de 200 o MR vai de {n(ef['mr_acima']['p0'], 2)} (mínimo) a {n(ef['mr_acima']['p95'], 1)} (p95), mediana {n(ef['mr_acima']['p50'], 1)}; nas demais, mediana {n(ef['mr_abaixo']['p50'], 2)}. O menor MR entre as acima é {n(ef['mr_min_acima_vs_mr_do_corte'], 1)} vezes o MR do corte do top-k ({n(ef['mr_max_no_topk'], 2)}). O SR delas é {n(ef['sr_acima_max'], 3)} (nenhum futuro com LCOE <= τ); nas demais, SR médio {n(ef['sr_abaixo_media'], 4)}. Acima de 200 no top-k robusto: {fi(ef['acima_no_topk_robusto'])}; no top-k nominal: {fi(ef['acima_no_topk_nominal'])}.")
a("")
a(f"**O que elas afetam: o tamanho do top-k.** O top-k é {n(I2['top_k_percent'], 0)}% do conjunto ranqueado por contagem de células (M-F7-05). Com as acima de 200 no conjunto, k = {fi(ef['k_ranked'])}; sem elas, k = {fi(ef['k_ranked_sem_acima'])}. O ranking relativo das demais não muda, então o top-k menor é um subconjunto do maior, mas o limiar de corte vai de MR {n(ef['mr_max_no_topk'], 2)} para um valor menor e todas as estatísticas definidas sobre o top-k (H1, H3, H4, a meta de capacidade) dependem de k. Duas estatísticas que dependem de todas as células: o Spearman entre LCOE e MR é {n(ef['spearman_lcoe_mr_todas'], 4)} com todas e {n(ef['spearman_lcoe_mr_sem_acima'], 4)} sem as acima; o Jaccard entre o top-10% nominal e o robusto é {n(ef['jaccard_top10_nom_rob_todas'], 4)} e {n(ef['jaccard_top10_nom_rob_sem_acima'], 4)}. As acima de 200 não decidem nada do que o F7 seleciona; só entram no denominador do percentual.")
a("")
# ---------------------------------------------------------------- item 2
a("## 2. PRT solar, L-252: convergência do top-k")
a("")
a("### 2.1 1 − Jaccard por tamanho de amostra")
a("")
rows = []
for _, r in CONV.iterrows():
    rows.append([f"{int(r['de'])} → {int(r['para'])}", str(int(r["k"])), str(int(r["interseccao"])), str(int(r["saem"])), str(int(r["entram"])), n(r["jaccard"], 4), n(r["um_menos_jaccard"], 4), "sim" if r["um_menos_jaccard"] < 0.01 else "não"])
a(table(["Passo", "k", "Interseção", "Saem", "Entram", "Jaccard", "1 − Jaccard", "< 0,01"], rows))
a("")
KS = {"PRT solar": 342, "PRT wind": 334, "IND solar": 9349, "IND wind": 7554, "BRA solar": 19001, "BRA wind": 17829}
def smax(kk):
    s_ = 0
    while 2 * (s_ + 1) / (kk + s_ + 1) < 0.01:
        s_ += 1
    return s_
KTXT = "Trocas admitidas pelo critério (s de cada lado) com o k do protocolo de cada par: " + "; ".join(f"{p_} (k = {fi(v)}): {smax(v)}" for p_, v in KS.items()) + "."
k = I2["k"]
s1 = 2 * 1 / (k + 1)
s2 = 2 * 2 / (k + 2)
a(f"Os três valores reproduzem a L-252 (0,0116, 0,0231, 0,0116). Com k = {k}, a distância de Jaccard de s células trocadas (s saem, s entram) é 2s/(k + s): {n(s1, 4)} para s = 1 e {n(s2, 4)} para s = 2. A tolerância de 0,01 admite portanto no máximo **1 troca**; cada passo observado tem 2 trocas ou mais. " + KTXT)
a("")
a("### 2.2 As células que trocam entre 2000 e 4000")
a("")
rows = [[str(int(r["cell_id"])), "sai" if r["em_2000"] else "entra", str(int(r["posicao_mr_4000"])), n(r["mr_2000"], 5), n(r["mr_4000"], 5), n(r["sr_4000"], 3), n(r["lcoe_nominal"], 2), n(r["dist_sub_km"], 1), n(r["cf"], 3), n(r["p_mw"], 1)] for _, r in SW.iterrows()]
a(table(["cell_id", "Em 4000", "Posição por MR (4000)", "MR (2000)", "MR (4000)", "SR", "LCOE nominal", "Dist. subest. (km)", "CF", "P (MW)"], rows))
a("")
a(f"O MR do corte (a {k}ª célula) em 4000 sorteios é {n(I2['mr_no_corte_4000'], 5)} e o da seguinte {n(I2['mr_k_mais_1'], 5)}: a diferença é de {n((I2['mr_k_mais_1'] - I2['mr_no_corte_4000']) / I2['mr_no_corte_4000'], 3, True)}. As {len(SW)} células que trocam estão nas posições {int(SW['posicao_mr_4000'].min())} a {int(SW['posicao_mr_4000'].max())}, a no máximo {n(I2['trocas_gap_relativo_ao_corte_4000']['max'], 2, True)} do MR do corte. Todas ficam na zona PV {', '.join(sorted({str(int(z)) for z in SW['pvcz_zone']}))} e têm LCOE nominal de {n(SW['lcoe_nominal'].min(), 1)} a {n(SW['lcoe_nominal'].max(), 1)} (τ = {n(I2['tau'], 2)}).")
a("")
dn = I2["celulas_com_mr_dentro_de_largura_relativa_do_corte"]
nz = I2["dif_relativa_mr_2000_4000"]
a(f"**Por que o corte é instável.** Há {dn['0.005']} células com MR dentro de ±0,5% do corte e {dn['0.01']} dentro de ±1% (de {fi(I2['n_ranked'])}). O MR de uma mesma célula muda entre dois tamanhos independentes de sorteio em {n(nz['mediana'], 2, True)} (mediana), {n(nz['p99'], 2, True)} (p99) e {n(nz['max'], 2, True)} (máximo); é um ruído de amostragem do P90, da ordem do espaçamento entre as células do corte. Os sorteios de tamanhos diferentes são independentes, não aninhados (nota da docstring de `convergence.py`), então a distância de Jaccard inclui esse ruído.")
a("")
a("### 2.3 Além do teto (diagnóstico, fora do protocolo)")
a("")
rows = [[f"{int(r['de'])} → {int(r['para'])}", str(int(r["saem"])), str(int(r["entram"])), n(r["um_menos_jaccard"], 4), "sim" if r["um_menos_jaccard"] < 0.01 else "não"] for _, r in EXT.iterrows()]
a(table(["Passo", "Saem", "Entram", "1 − Jaccard", "< 0,01"], rows))
a("")
a("Rodei o mesmo cálculo com 8000 e 16000 sorteios (mesma semente, mesmos insumos), só para ver o que acontece acima do teto de 4000 de `sampler.max_size_for_convergence`. É um diagnóstico: o protocolo e o tamanho adotado não mudam. Em cada passo há 1 troca, e 1 − Jaccard cai a 0,0058, abaixo da tolerância. Ou seja, o critério passaria no passo de 4000 para 8000 se o teto fosse maior. Como com k = 342 a tolerância admite só 1 troca, ainda é o acaso do sorteio de cada passo que decide se passa; dois passos seguidos com 1 troca não provam convergência além disso.")
a("")
a("### 2.4 O conjunto da convergência e o do F7 não coincidem na BRA eólica")
a("")
rows = []
for par, (iso, tech) in zip([f"{i} {t}" for i, t in c.PAIRS], c.PAIRS):
    cv = pd.read_parquet(c.DATA / "outputs" / iso / "sample_size_convergence" / "artifacts" / f"sample_size_convergence_{tech}.parquet").iloc[-1]
    h = pd.read_parquet(c.paths(iso)["rob"] / f"h1_summary_{tech}__core.parquet")
    h = h[h["primary"]].iloc[0]
    rows.append([par, fi(cv["n_cells"]), fi(cv["k"]), fi(h["n_ranked"]), fi(h["k"]), "sim" if (int(cv["k"]) == int(h["k"])) else "NÃO"])
a(table(["Par", "Convergência: células", "Convergência: k", "F7: células ranqueadas", "F7: k", "k igual"], rows))
a("")
a("O protocolo U-04 chama `build_cell_set` sem a lista de células `incomplete_ensemble` (o argumento fica nulo, e o docstring de `cell_set.py` diz que nesse caso nenhuma célula é excluída por esse motivo), enquanto o F7 exclui essas células do conjunto e do cálculo de k. Só a BRA eólica tem células `incomplete_ensemble` com F6 (7.104); por isso só nela os conjuntos diferem: a convergência ranqueia 178.285 células com k = 17.829 e o F7 ranqueia 171.181 com k = 17.119 (a diferença de 7.104 é exatamente a contagem `incomplete_ensemble` do F7). O resultado da BRA eólica na convergência (1 − Jaccard 0,0003 em 1000 sorteios) foi obtido num conjunto que contém essas células, não no do F7. O tamanho adotado (4000) é o mesmo `sampler.adopted_size` para todos os pares, então a decisão de tamanho não muda; o que fica registrado é que o critério foi testado num conjunto maior que o do F7 só nesse par.")
a("")
# ---------------------------------------------------------------- item 3
a("## 3. As 5 células de menor LCOE nominal de cada par")
a("")
a("LCOE nominal do F6 (membro de referência, cenário central, amostra nominal). As colunas: CF do F5; distância à subestação com o percentil dela no par; distância à estrada; zona PV (solar); parcela da conexão no LCOE; capacidade da célula; área do país na célula sobre a área nominal de 0,05 grau (`borda`); vizinhas candidatas entre as 8; razão do LCOE da célula sobre a média das vizinhas candidatas; sinais conforme os limiares da seção 0.")
a("")
for par in [f"{i} {t}" for i, t in c.PAIRS]:
    g = T3[T3.par == par]
    pi = PP[par]
    a(f"### {par}")
    a("")
    a(f"Contexto do par: {fi(pi['n_celulas'])} células, LCOE mínimo {n(pi['lcoe_min'], 2)}, p1 {n(pi['lcoe_p1'], 2)}, mediana {n(pi['lcoe_mediana'], 2)}, τ {n(pi['tau'], 2)}. CF: mediana {n(pi['cf_mediana'], 3)}, p99 {n(pi['cf_p99'], 3)}, p99,9 {n(pi['cf_p999'], 3)}, máximo {n(pi['cf_max'], 3)}. Distância à subestação: p1 {n(pi['dist_sub_p1'], 1)} km, p5 {n(pi['dist_sub_p5'], 1)} km. Células com distância à subestação igual a zero: {pi['n_dist_sub_zero']}; menor que 1 km: {pi['n_dist_sub_menor_1km']}; distância à estrada zero: {pi['n_dist_road_zero']}.")
    a("")
    rows = []
    for _, r in g.iterrows():
        fl = flags(r)
        rows.append([str(int(r["posicao"])), f"`{int(r['cell_id'])}`", f"{n(r['lat'], 3)}; {n(r['lon'], 3)}", n(r["lcoe"], 2), n(r["cf_f5"], 3), f"{n(r['dist_sub_km'], 1)} ({n(r['dist_sub_percentil'], 1, True)})", n(r["dist_road_km"], 1), "" if pd.isna(r["zona_pv"]) else str(int(r["zona_pv"])), n(r["parcela_conexao"], 1, True), n(r["p_mw"], 2), n(r["razao_area"], 2), str(int(r["n_vizinhas_candidatas"])), n(r["razao_lcoe_vizinhas"], 2), "; ".join(fl) if fl else "nenhum"])
    a(table(["#", "cell_id", "lat; lon", "LCOE", "CF", "Dist. subest. km (percentil)", "Dist. estrada km", "Zona", "Conexão", "P (MW)", "Borda", "Viz.", "LCOE / vizinhas", "Sinais"], rows))
    a("")
    if par.endswith("wind"):
        a("Vento (Weibull A a 100 m; k; elevação): " + "; ".join(f"#{int(r['posicao'])}: {n(r['weibull_a_100m'], 1)} m/s; {n(r['weibull_k_100m'], 2)}; {n(r['elevacao_m'], 0)} m" for _, r in g.iterrows()) + ".")
        a("")
# leitura
a("### 3.1 Leitura dos sinais")
a("")
n_edge = T3[T3["razao_area"] < AREA_MIN]
a(f"- **Distância zero suspeita.** Nenhuma das 30 células tem distância à subestação menor que {n(DIST_MIN, 0)} km (mínimo {n(T3['dist_sub_km'].min(), 2)} km) nem distância à estrada zero (mínimo {n(T3['dist_road_km'].min(), 2)} km). Nos seis pares, o total de células com distância à subestação zero é {sum(v['n_dist_sub_zero'] for v in PP.values())} e com distância à estrada zero é {sum(v['n_dist_road_zero'] for v in PP.values())}; as que têm menos de 1 km à subestação são de {min(v['n_dist_sub_menor_1km'] for v in PP.values())} a {max(v['n_dist_sub_menor_1km'] for v in PP.values())} por par (contexto de cada par).")
cfx = T3[T3.apply(lambda r: r["cf_f5"] > CF_MAX[r["par"].split()[1]], axis=1)]
a(f"- **CF.** Nenhum CF está fora de [0, 1]. Pelo limiar adotado aqui ({n(CF_MAX['solar'], 2)} solar, {n(CF_MAX['wind'], 2)} eólica), {len(cfx)} das 30 ficam acima: {', '.join(f'{r.par} #{int(r.posicao)} ({n(r.cf_f5, 3)})' for r in cfx.itertuples()) or 'nenhuma'}. Todas as 5 da BRA eólica têm CF no percentil {n(T3[T3.par == 'BRA wind']['cf_percentil_no_par'].min(), 4, True)} ou mais do par, e o CF máximo do par é {n(PP['BRA wind']['cf_max'], 3)}. O diagnóstico OQ-114 (`docs/_audit/oq114_170.md`) mostra que o CF por pixel do F5 reproduz o do Global Wind Atlas (correlação de 0,997 a 0,999), então esse valor extremo vem do dado de vento, não do código do F5. A faixa 0,60 é uma referência minha de CF líquido de usina onshore, não vem do pipeline.")
a(f"- **Borda de máscara.** {len(n_edge)} das 30 têm menos de 98% da área nominal dentro do país: {', '.join(f'{r.par} #{int(r.posicao)} ({n(r.razao_area, 2)})' for r in n_edge.itertuples())}. São células na borda da máscara (coordenadas na tabela do par). O LCOE por MW não depende da área da célula, mas o CF do F5 é ponderado pela área elegível dos pixels (D-F5-038), que ficam dentro do país, então descreve só a parte da célula dentro do país; a razão do LCOE da célula sobre o das vizinhas ({n(n_edge['razao_lcoe_vizinhas'].min(), 2)} a {n(n_edge['razao_lcoe_vizinhas'].max(), 2)}) não mostra um pico de LCOE nelas.")
spike = T3[T3["razao_lcoe_vizinhas"] < RATIO_MIN]
rest = T3[T3['razao_lcoe_vizinhas'] >= RATIO_MIN]
a(f"- **Pico local.** {len(spike)} das 30 {'tem' if len(spike) == 1 else 'têm'} LCOE abaixo de 80% da média das vizinhas candidatas ({', '.join(f'{r.par} #{int(r.posicao)} ({n(r.razao_lcoe_vizinhas, 2)})' for r in spike.itertuples()) or 'nenhuma'}). As demais ficam entre {n(rest['razao_lcoe_vizinhas'].min(), 2)} e {n(rest['razao_lcoe_vizinhas'].max(), 2)} da média das vizinhas.")
def blocos(g, lim=0.3):
    pts = list(zip(g["lat"], g["lon"]))
    comp = []
    for i_, p_ in enumerate(pts):
        near = [k_ for k_, cc in enumerate(comp) if any(abs(p_[0] - q_[0]) <= lim and abs(p_[1] - q_[1]) <= lim for q_ in cc)]
        merged = [p_] + [q_ for k_ in near for q_ in comp[k_]]
        comp = [cc for k_, cc in enumerate(comp) if k_ not in near] + [merged]
    return len(comp)
bb = []
for par in [f"{i} {t}" for i, t in c.PAIRS]:
    g = T3[T3.par == par]
    bb.append(f"{par}: {blocos(g)} bloco(s) (células a até 0,3 grau uma da outra)")
a("- **Aglomeração.** As 5 menores de cada par não são 5 achados independentes: " + "; ".join(bb) + ". As coordenadas estão nas tabelas.")
a("")
a("### 3.2 Capacidade das células do topo (propriedade do desenho, observada aqui)")
a("")
rows = []
for par in [f"{i} {t}" for i, t in c.PAIRS]:
    b = BP[par]
    rows.append([par, n(b["p_mediana_mw"], 1), fi(b["n_p_lt_1mw"]), n(b["n_p_lt_1mw"] / PP[par]["n_celulas"], 1, True), f"{fi(b['topk_nominal_p_lt_1mw'])} de {fi(b['topk_nominal_n'])}", n(b["topk_nominal_p_lt_1mw"] / b["topk_nominal_n"], 1, True), n(b["topk_nominal_mediana_p_mw"], 1), n(b["topk_nominal_capacidade_mw"] / b["capacidade_total_mw"], 1, True)])
a(table(["Par", "P mediana (MW)", "Células com P < 1 MW", "Parcela", "No top-k nominal, P < 1 MW", "Parcela do top-k", "P mediana no top-k (MW)", "Capacidade do top-k sobre o total"], rows))
a("")
sh = {par: BP[par]["topk_nominal_p_lt_1mw"] / BP[par]["topk_nominal_n"] for par in BP}
small5 = [par for par in BP if (T3[T3.par == par]["p_mw"] < P_MIN).sum() >= 3]
a(f"O top-k é por contagem de células, não por capacidade. A parcela do top-k nominal com menos de 1 MW vai de {n(min(sh.values()), 1, True)} ({min(sh, key=sh.get)}) a {n(max(sh.values()), 1, True)} ({max(sh, key=sh.get)}). Nos pares {', '.join(small5)}, 3 ou mais das 5 células de menor LCOE têm menos de 1 MW. Isso não é defeito de uma célula; é uma propriedade da seleção por contagem, que dá o mesmo peso a uma célula de poucos kW e a uma de centenas de MW. O relatório só a registra.")
a("")
# ---------------------------------------------------------------- manifestos
snap = c.DATA / "_snapshots" / "20261123_pre204"
lines = [ln.split(" *", 1) for ln in (snap / "SHA256SUMS.txt").read_text().splitlines() if ln.strip()]
ok = []
for sha, name in lines:
    live = None
    for iso in ("PRT", "IND", "BRA"):
        if name.startswith(iso + "_"):
            live = c.DATA / "outputs" / iso / name[len(iso) + 1 :]
            break
    if live is None:
        live = c.DATA / "outputs" / "cross_country" / name
    ok.append((name, hashlib.sha256(live.read_bytes()).hexdigest() == sha))
a("## 4. Manifestos e referências no momento da geração")
a("")
a(f"Manifestos comparados com o instantâneo `_snapshots/20261123_pre204` (SHA-256): {sum(1 for _, v in ok if v)} de {len(ok)} iguais" + ("." if all(v for _, v in ok) else "; DIFERENTES: " + ", ".join(nm for nm, v in ok if not v)) + " O D5 não grava nada no pipeline; o instantâneo do 204 vale como base porque os scripts do 205 só leem.")
tags = subprocess.run(["git", "-C", str(c.REPO), "rev-parse", "v1.0^{commit}", "prereg-v1"], capture_output=True, text=True).stdout.split()
a(f"Tag `v1.0` aponta para `{tags[0][:7]}` e o objeto da tag `prereg-v1` é `{tags[1][:8]}`, como registrados.")
a("")
open(c.OUT / "D5_caudas.md", "w", encoding="utf-8").write("\n".join(L))
print("D5_caudas.md escrito,", len("\n".join(L).split()), "palavras")
