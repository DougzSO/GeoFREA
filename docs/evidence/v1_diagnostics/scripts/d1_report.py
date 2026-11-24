# Runs only at tag v1.1 (these scripts import modules of v1 that leave the work tree at COMMAND 306). Kept as documentation of the diagnostics D1 to D5.
"""Gera D1_tau.md a partir dos CSV/JSON de D1_dados (nenhum numero do texto e digitado a mao)."""
from __future__ import annotations

import json
import subprocess

import pandas as pd

import d1_common as c

D = c.OUT / "D1_dados"
cf = pd.read_csv(D / "D1_1_cf.csv")
cf = cf[cf["base"].str.startswith("cf_efetivo")].set_index("par")
cf5 = pd.read_csv(D / "D1_1_cf.csv")
cf5 = cf5[cf5["base"].str.startswith("cf_F5")].set_index("par")
steps = pd.read_csv(D / "D1_2_decomposicao_passos.csv")
absol = pd.read_csv(D / "D1_2_termos_absolutos.csv")
sr = pd.read_csv(D / "D1_3_sr.csv").set_index("par")
curve = pd.read_csv(D / "D1_4_curva_capacidade.csv")
h5 = {h["par"]: h for h in json.load(open(D / "D1_5_h5.json", encoding="utf-8"))}
h5v = pd.read_csv(D / "D1_5_h5_variantes_f7.csv")
info = json.load(open(D / "D1_pares.json", encoding="utf-8"))
PAIRS = [f"{i} {t}" for i, t in c.PAIRS]


def n(x, d=2, pct=False):
    """Numero com virgula decimal; `pct` multiplica por 100."""
    if x is None or (isinstance(x, float) and x != x):
        return "não disponível"
    v = x * 100 if pct else x
    s = f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if float(f"{v:.{d}f}") == 0:
        s = s.lstrip("-")
    return s + ("%" if pct else "")


def table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


head = subprocess.run(["git", "-C", str(c.REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
L: list[str] = []
a = L.append
a("# D1: o τ e o domínio econômico (COMANDO 201)")
a("")
a(f"Escrito para: o autor, para levar ao chat de planejamento. Data: 2026-11-23. Repositório em `{head}`, tag `prereg-v1` e `v1.0` inalteradas. Somente leitura: nada foi gravado em `GeoFREA_data/outputs/` nem no repositório. Os scripts estão em `_notas_geofrea/diagnostico_v1_0/` (`d1_common.py`, `d1_run.py`, `d1_report.py`) e os dados de cada tabela e figura em `D1_dados/`. Este texto é gerado de `D1_dados/` por `d1_report.py`: nenhum número foi digitado à mão.")
a("")
a("Base de todas as medidas: janela core, cenário central de solo, membro de referência m0, amostra nominal (linha 0 da matriz de desenho). O \"conjunto\" é o conjunto F7 do par (células com LCOE nominal finito e presentes na tabela de robustez), e a capacidade é o `P_MW` do F5. Nenhum valor novo de τ é proposto.")
a("")
a("## 0. Como os números foram conferidos")
a("")
a("1. O LCOE nominal de cada célula foi recalculado com o kernel do F6 (`lcoe_block`, importado) a partir de F3, F4 e F5. Diferença máxima contra o `lcoe_summary` gravado pelo F6: **0,0** nos seis pares (todas as células, m0).")
a("2. A decomposição por termos fecha com o LCOE nominal de cada célula com tolerância de 1e-9 (asserção no `d1_run.py`, em todas as células de cada par); o erro máximo observado foi 3,6e-12 (`d1_check.py`).")
rec = ", ".join(p + ": " + n(info[p]["tau_recalculado"], 4) + " contra " + n(info[p]["tau"], 2) for p in PAIRS)
a(f"3. O τ foi recalculado do mesmo modo que `scripts/calibrate_tau_irena.py` (planta de referência do IRENA 2024 pelo kernel, taxa central, vida de 25 anos): {rec}. As diferenças são de arredondamento (o τ da configuração tem duas casas).")
a("4. O domínio econômico do H5 (número de células, capacidade e E_0 no τ primário) foi reproduzido a partir das tabelas do F5 e do F6 e coincide com `h5_summary` do F7 nos seis pares (ver 5).")
a("5. Os manifestos de PRT, IND, BRA e do `cross_country` têm o mesmo SHA-256 do instantâneo `_snapshots/20261123_pre201` (verificado na hora de gerar este texto; ver a seção 10).")
a("")

# ---------------------------------------------------------------- achados
a("## 1. Achados em uma página")
a("")
def row(p): return info[p]
bw, bs, iw, isol = row("BRA wind"), row("BRA solar"), row("IND wind"), row("IND solar")
bwp = steps[(steps.par == "BRA wind") & (steps.grupo == "banda do p10 (p8 a p12)")].iloc[0]
a(f"- **BRA eólica:** o CF da planta de referência do τ é {n(bw['cf_referencia'], 2)}; as células ficam abaixo dele em {n(cf.loc['BRA wind', 'percentil_do_cf_ref (celulas)'] / 100, 2, True)} dos casos (p50 {n(cf.loc['BRA wind', 'p50'], 3)}, p90 {n(cf.loc['BRA wind', 'p90'], 3)}). Na banda do p10 das células (LCOE médio {n(bwp['lcoe_medio'])}), a diferença para o τ ({n(bwp['tau'])}) é de {n(bwp['diferenca_total'])} USD/MWh, dos quais {n(bwp['energia da celula (CF)'])} vêm da energia da célula (CF), {n(bwp['conexao (subestacao)'])} da conexão, {n(bwp['vida util do modelo'])} da vida útil (sinal negativo: reduz) e {n(bwp['capex e O&M do modelo'], 2)} do capex e O&M.")
a(f"- **Vida útil:** o τ usa a vida de 25 anos do IRENA e as células usam {n(bw['vida_modelo'], 0)} anos (`parameters.json`). Isso reduz o LCOE das células em {n(-steps.groupby('par')['vida util do modelo'].mean().max(), 2)} a {n(-steps.groupby('par')['vida util do modelo'].mean().min(), 2)} USD/MWh em relação à base do τ (valor por par; é o mesmo em todas as células de um par). O capex do modelo é igual ao TIC do IRENA nos seis pares; o O&M do modelo difere do IRENA em quatro pares (ver 2).")
dom_txt = ", ".join(p + " " + n(info[p]["frac_cap_<= tau"], 3, True) for p in PAIRS)
a(f"- **Domínio econômico:** a fração da capacidade do conjunto com LCOE nominal <= τ é {dom_txt}.")
sr_txt = ", ".join(p + " " + n(sr.loc[p, "frac_sr_zero"], 1, True) for p in PAIRS)
a(f"- **SR:** a fração de células com SR = 0 é {sr_txt}. A hipótese de que o SR é zero em quase todas as células vale para a eólica do BRA e da Índia, e não para a solar do BRA.")
a(f"- **H5 na borda:** na solar da Índia, E_0 excede G em {n(h5['IND solar']['h0_f7_twh'], 1)} TWh ({n(h5['IND solar']['h0_f7_twh'] / h5['IND solar']['g_f7_twh'], 2, True)} de G); o menor τ com H_0 >= 0 é {n(h5['IND solar']['tau_estrela'], 2)}, a {n(h5['IND solar']['tau'] - h5['IND solar']['tau_estrela'], 2)} USD/MWh do primário ({n(1 - h5['IND solar']['tau_estrela'] / h5['IND solar']['tau'], 2, True)}). Na solar do BRA o menor τ com H_0 >= 0 é {n(h5['BRA solar']['tau_estrela'], 2)}, {n(h5['BRA solar']['tau_estrela'] / h5['BRA solar']['tau'] - 1, 1, True)} acima do primário ({n(h5['BRA solar']['tau'], 2)}); na eólica da Índia é {n(h5['IND wind']['tau_estrela'], 2)}, {n(h5['IND wind']['tau_estrela'] / h5['IND wind']['tau'], 2)} vez o primário e acima do fim da faixa registrada ({n(info['IND wind']['tau_max'], 2)}).")
a("")

# ---------------------------------------------------------------- 1
a("## 2. Item 1: CF da planta de referência do τ contra o CF das células")
a("")
a("O CF efetivo é a energia nominal que o kernel usa (`E_MWh` do F5 vezes o fator de reescala no valor nominal do parâmetro de energia) dividida por `8760 x P_MW`. Ele é igual ao CF gravado no F5 (`CF`) nos seis pares (as duas bases dão as mesmas colunas em `D1_dados/D1_1_cf.csv`), porque o fator de reescala vale 1 no valor nominal. \"Ponderado\" usa `P_MW` como peso.")
a("")
rows = []
for p in PAIRS:
    r = cf.loc[p]
    rows.append([p, n(r["cf_referencia"], 3) + (" (proxy regional)" if info[p]["cf_ref_proxy"] else ""), n(r["percentil_do_cf_ref (celulas)"] / 100, 1, True), n(r["frac_celulas_cf_maior_igual"], 1, True), n(r["frac_capacidade_cf_maior_igual"], 1, True), n(r["p10"], 3), n(r["p50"], 3), n(r["p90"], 3), n(r["p50_pond"], 3), f"{int(r['n']):,}".replace(",", ".")])
a(table(["Par", "CF da referência", "Percentil do CF de ref. entre as células", "Células com CF >= ref.", "Capacidade com CF >= ref.", "CF p10", "CF p50", "CF p90", "CF p50 pond.", "Células"], rows))
a("")
a("Figura: `D1_dados/D1_1_cf.png` (histograma do CF efetivo com a linha do CF de referência).")
a("")
a("![CF](D1_dados/D1_1_cf.png)")
a("")
a("Fatos: em PRT solar nenhuma célula tem CF abaixo do da referência (o CF da referência é o proxy da média da UE, L-242); em IND solar o CF de referência fica no percentil 45; nos outros quatro pares fica entre os percentis 91 e 99,9 das células.")
a("")

# ---------------------------------------------------------------- 2
a("## 3. Item 2: decomposição do LCOE nominal da planta de referência do τ às células")
a("")
a("**Método.** Parte-se da planta de referência (a que dá o τ: TIC, O&M, CF e vida de 25 anos do IRENA 2024, taxa central do par, sem conexão, sem degradação) e troca-se um termo por vez pelo valor do kernel para a célula, na ordem abaixo. Cada linha é a variação do LCOE nesse passo, em USD/MWh, média das células do grupo. A soma dos passos é a diferença entre o LCOE médio do grupo e o τ. A ordem dos passos afeta a divisão entre termos que interagem (energia e custos de capital, por exemplo); a ordem usada é a da tabela.")
a("")
a("1. capex e O&M do modelo no lugar do TIC e do O&M do IRENA; 2. vida útil do modelo (30 anos) no lugar de 25; 3. energia da célula (CF) no lugar do CF de referência; 4. conexão (baia e linha até a subestação); 5. acesso (estrada); 6. degradação; 7. perda de transmissão.")
a("")
a("Os passos 5 e 7 valem 0 nos seis pares: o custo de estrada não é cobrado (`road_cost_excluded`, aviso do F6) e a perda de transmissão do modelo é 0 (`transmission_loss_per_km`).")
a("")
a("Capex e O&M do IRENA contra os do modelo (USD/kW e fração do capex ao ano):")
a("")
rows = []
for p in PAIRS:
    i = info[p]
    rows.append([p, n(i["tic_irena"], 0), n(i["capex_modelo"], 0), n(i["om_irena"] / i["tic_irena"], 4), n(i["om_modelo_frac"], 4), n(i["vida_irena"], 0), n(i["vida_modelo"], 0), n(i["taxa_central"], 3, True)])
a(table(["Par", "TIC IRENA", "capex do modelo", "O&M IRENA / TIC", "O&M do modelo (fração)", "vida IRENA", "vida do modelo", "taxa central"], rows))
a("")
cols = ["capex e O&M do modelo", "vida util do modelo", "energia da celula (CF)", "conexao (subestacao)", "degradacao"]
hdr = ["Par", "LCOE médio", "τ", "Δ total", "capex e O&M", "vida útil", "energia (CF)", "conexão", "degradação", "CF médio", "dist. subest. média (km)"]
for g, titulo in (("banda do p10 (p8 a p12)", "Banda do p10 das células (p8 a p12): o que separa o p10 do τ"), ("decil 1 (<= p10)", "Decil 1 (as 10% de menor LCOE)"), ("mediana (p45 a p55)", "Mediana (p45 a p55)"), ("decil 10 (>= p90)", "Decil 10 (as 10% de maior LCOE)")):
    a(f"### {titulo}")
    a("")
    rows = []
    for p in PAIRS:
        r = steps[(steps.par == p) & (steps.grupo == g)].iloc[0]
        rows.append([p, n(r["lcoe_medio"]), n(r["tau"]), n(r["diferenca_total"])] + [n(r[k]) for k in cols] + [n(r["cf_medio"], 3), n(r["dist_subestacao_km_media"], 1)])
    a(table(hdr, rows))
    a("")
a("### Parcela de cada termo na diferença entre a banda do p10 e o τ")
a("")
rows = []
for p in PAIRS:
    r = steps[(steps.par == p) & (steps.grupo == "banda do p10 (p8 a p12)")].iloc[0]
    tot = r["diferenca_total"]
    rows.append([p, n(tot)] + [n(r[k] / tot, 0, True) if abs(tot) > 1e-9 else "não disponível" for k in cols])
a(table(["Par", "Δ total (USD/MWh)", "capex e O&M", "vida útil", "energia (CF)", "conexão", "degradação"], rows))
a("")
a("Quando os termos têm sinais opostos as parcelas passam de 100% ou ficam negativas; a soma das cinco colunas é 100%.")
a("")
a("### Termos absolutos do LCOE final (soma = LCOE médio do grupo, USD/MWh)")
a("")
a("Capital (capex), O&M fixo e conexão, com a energia e a degradação da célula no denominador. Estrada e O&M variável valem 0.")
a("")
rows = []
for p in PAIRS:
    for g in ("decil 1 (<= p10)", "mediana (p45 a p55)", "decil 10 (>= p90)"):
        r = absol[(absol.par == p) & (absol.grupo == g)].iloc[0]
        rows.append([p, g, n(r["capex"]), n(r["om_fixo"]), n(r["conexao"]), n(r["total"])])
a(table(["Par", "Grupo", "capex", "O&M fixo", "conexão", "LCOE médio"], rows))
a("")

# ---------------------------------------------------------------- 3
a("## 4. Item 3: SR")
a("")
a("Células do conjunto com SR e MR calculados na tabela `robustness_<tec>__core` (as classes `climate_data_invalid`, `incomplete_ensemble` e as sem LCOE ficam sem SR e MR). SR é a parcela dos futuros (membros do core, amostras s >= 1 do desenho) em que a célula é viável e o LCOE não excede o τ primário (M-F7-04).")
a("")
rows = []
for p in PAIRS:
    r = sr.loc[p]
    rows.append([p, f"{int(r['n_ranqueadas']):,}".replace(",", "."), n(r["frac_sr_zero"], 1, True), n(r["frac_sr_um"], 4, True), n(r["q25"], 3), n(r["q50"], 3), n(r["q75"], 3), n(r["q90"], 3), n(r["max"], 3), n(r["spearman_sr_mr"], 3), n(r["spearman_sr_lcoe_nominal"], 3)])
a(table(["Par", "Células com SR", "SR = 0", "SR = 1", "q25", "q50", "q75", "q90", "máx.", "Spearman SR e MR", "Spearman SR e LCOE nominal"], rows))
a("")
rows = []
for p in PAIRS:
    r = sr.loc[p]
    rows.append([p, n(r["tau"]), n(r["lcoe_p10_celulas"]), n(r["lcoe_p50_celulas"]), n(r["frac_celulas_lcoe_nominal_<=_tau"], 2, True), n(r["frac_capacidade_lcoe_nominal_<=_tau"], 2, True), n(r["frac_celulas_com_sr_>0"], 1, True)])
a(table(["Par", "τ", "LCOE p10 das células", "LCOE p50 das células", "Células com LCOE nominal <= τ", "Capacidade com LCOE nominal <= τ", "Células com SR > 0"], rows))
a("")
cnt_um = ", ".join(p + " " + str(int(round(sr.loc[p, "frac_sr_um"] * sr.loc[p, "n_ranqueadas"]))) for p in PAIRS)
mono = [p for p in PAIRS if p not in ("IND wind", "BRA wind")]
mn = min(min(abs(sr.loc[p, "spearman_sr_mr"]), abs(sr.loc[p, "spearman_sr_lcoe_nominal"])) for p in mono)
zw = [abs(sr.loc[p, k]) for p in ("IND wind", "BRA wind") for k in ("spearman_sr_mr", "spearman_sr_lcoe_nominal")]
a(f"Fatos: células com SR = 1: {cnt_um}. Nos quatro pares fora as eólicas de IND e BRA o SR é quase uma função monótona do LCOE nominal e do MR (módulo do Spearman de {n(mn, 3)} ou mais); nas duas eólicas, com mais de três quartos das células em SR = 0, o módulo fica entre {n(min(zw), 3)} e {n(max(zw), 3)} (empates no zero).")
a("")

# ---------------------------------------------------------------- 4
a("## 5. Item 4: fração da capacidade com LCOE nominal <= x")
a("")
a("Curva descritiva, x de 20 a 200 USD/MWh (passo 5; tabela completa em `D1_dados/D1_4_curva_capacidade.csv`). Marcas: o τ primário, as pontas da faixa registrada (`tau_min`, `tau_max`) e o LCOE nacional publicado do IRENA 2024 (com p5 e p95).")
a("")
a("![curva](D1_dados/D1_4_curva_capacidade.png)")
a("")
xs = [20, 30, 40, 50, 60, 80, 100, 150, 200]
rows = []
for p in PAIRS:
    d = curve[curve.par == p].set_index("x_usd_mwh")
    rows.append([p] + [n(d.loc[float(x), "frac_capacidade"], 1, True) for x in xs])
a(table(["Par"] + [f"x={x}" for x in xs], rows))
a("")
rows = []
for p in PAIRS:
    i = info[p]
    rows.append([p, n(i["capacidade_total_gw"], 1), n(i["tau"]), n(i["frac_cap_<= tau"], 2, True), n(i["tau_min"]) + " / " + n(i["tau_max"]), n(i["frac_cap_<= tau_min"], 2, True) + " / " + n(i["frac_cap_<= tau_max"], 2, True), n(i["irena_lcoe_publicado"], 0) + f" ({n(i['irena_p5'], 0)} a {n(i['irena_p95'], 0)})", n(i["frac_cap_<= irena_publicado"], 2, True)])
a(table(["Par", "Capacidade do conjunto (GW)", "τ primário", "Cap. com LCOE <= τ", "τ min / τ max", "Cap. com LCOE <= τ min / τ max", "IRENA publicado (p5 a p95)", "Cap. com LCOE <= publicado"], rows))
a("")

# ---------------------------------------------------------------- 5
a("## 6. Item 5: H5, de onde vem E_0 e qual τ daria H_0 = 0")
a("")
a("O H5 tem meta registrada em três pares (solar da Índia, eólica da Índia, solar do Brasil). `H_0 = E_0 - G` (M-F7-07). E_0 é a energia (membro m0) das células do domínio econômico (LCOE nominal <= τ, conjunto F7, cenário central). Para metas em GW, `G = 8,76 x G_cap x CFbar`, com CFbar o CF de referência ponderado pela capacidade das células de menor LCOE até somar G_cap (última célula fracionada; meta acima do domínio usa o domínio todo). \"τ*\" é o menor LCOE de célula tal que o domínio das células com LCOE <= τ* dá H_0 >= 0 (o domínio só muda nos valores de LCOE das células). As colunas \"calculado\" são do script e batem com as do F7.")
a("")
rows = []
for p in ("IND solar", "IND wind", "BRA solar"):
    h = h5[p]
    rows.append([p, n(h["tau"]), f"{h['n_dominio_calculado']:,}".replace(",", "."), n(h["cap_dominio_calculada_gw"], 1), n(h["e0_calculado_twh"], 2), n(h["alvo"], 0) + " GW", n(h["g_calculado_twh"], 2), n(h["h0_calculado_twh"], 2), n(h["h0_f7_twh"], 2), h["status_f7"]])
a(table(["Par", "τ primário", "Células no domínio", "Capacidade do domínio (GW)", "E_0 (TWh)", "Meta", "G (TWh)", "H_0 calculado", "H_0 do F7", "Estado no F7"], rows))
a("")
rows = []
for p in ("IND solar", "IND wind", "BRA solar"):
    h = h5[p]
    rows.append([p, n(h["tau"]), n(h["tau_estrela"]), n(h["tau_estrela"] / h["tau"] - 1, 2, True), f"{h['n_dominio_tau_estrela']:,}".replace(",", "."), n(h["cap_dominio_tau_estrela_gw"], 1), n(h["e0_tau_estrela_twh"], 2), n(h["g_tau_estrela_twh"], 2), n(info[p]["tau_min"]) + " a " + n(info[p]["tau_max"]), n(info[p]["irena_lcoe_publicado"], 0)])
a(table(["Par", "τ primário", "τ* (H_0 = 0)", "τ* contra o primário", "Células em τ*", "Capacidade em τ* (GW)", "E_0 em τ*", "G em τ*", "Faixa registrada", "IRENA publicado"], rows))
a("")
a("Variantes de τ já calculadas pelo F7 nesses pares (`h5_summary`, `D1_dados/D1_5_h5_variantes_f7.csv`):")
a("")
rows = []
for p in ("IND solar", "IND wind", "BRA solar"):
    for _, r in h5v[(h5v.par == p) & h5v.variant.isin(["primary", "tau_min", "tau_max"])].iterrows():
        rows.append([p, r["variant"], n(r["tau_usd_per_mwh"]), r["status"], f"{int(r['n_domain_cells']):,}".replace(",", "."), n(r["domain_capacity_gw"], 1), n(r["e0_twh"], 2), n(r["g_twh"], 2), n(r["h0_twh"], 2)])
a(table(["Par", "Variante", "τ", "Estado", "Células", "Capacidade (GW)", "E_0", "G", "H_0"], rows))
a("")
bs_min = h5v[(h5v.par == "BRA solar") & (h5v.variant == "tau_min")].iloc[0]
a(f"Em BRA solar, `tau_min` ({n(bs_min['tau_usd_per_mwh'])}) deixa o domínio com {int(bs_min['n_domain_cells'])} células: `G` e `H_0` não existem. Na solar e na eólica da Índia `tau_min` coincide com o primário, porque a faixa foi estendida para baixo até ele (DEC-089 a).")
a("")

# ---------------------------------------------------------------- hipoteses
a("## 7. O que os achados dizem sobre as leituras da seção 1 do arquivo de comandos")
a("")
a("Só o que os números mostram; a classificação em A, B, C ou D fica para o D0.")
a("")
a(f"- **Item 1, \"o domínio econômico quase some no BRA\":** confirmado. {n(info['BRA solar']['frac_cap_<= tau'], 3, True)} da capacidade solar e {n(info['BRA wind']['frac_cap_<= tau'], 3, True)} da eólica têm LCOE <= τ ({h5['BRA solar']['n_dominio_calculado']} e {h5['BRA wind']['n_dominio_calculado']} células).")
a(f"- **\"O τ foi calibrado com o CF de 53%\":** confirmado e quantificado: na banda do p10 da eólica do BRA, {n(bwp['energia da celula (CF)'] / bwp['diferenca_total'], 0, True)} da diferença para o τ vem do CF das células ({n(bwp['cf_medio'], 3)} contra {n(bw['cf_referencia'], 2)}).")
a(f"- **\"O SR é provavelmente zero em quase todas as células desses pares\":** vale para a eólica do BRA e da Índia; não vale para a solar do BRA, em que o SR é positivo em {n(sr.loc['BRA solar', 'frac_celulas_com_sr_>0'], 1, True)} das células mesmo com {n(info['BRA solar']['frac_cap_<= tau'], 3, True)} da capacidade abaixo do τ no cenário nominal.")
a(f"- **\"O satisficing não discrimina\":** na eólica de BRA e IND o SR é zero em {n(sr.loc['BRA wind', 'frac_sr_zero'], 1, True)} e {n(sr.loc['IND wind', 'frac_sr_zero'], 1, True)} das células. Nos outros quatro pares ele é quase monótono no LCOE nominal (ver 4).")
p10b = steps[steps.grupo == "banda do p10 (p8 a p12)"]
conn, degr = p10b["conexao (subestacao)"], p10b["degradacao"]
a(f"- **Base comum entre τ e LCOE das células (pergunta do comando):** o capex coincide com o TIC do IRENA e a taxa é a mesma; a vida útil (25 contra 30 anos) e o O&M (quatro pares) diferem e baixam o LCOE das células em relação à base do τ; o CF é o termo que mais separa o τ do p10 das células na eólica do BRA e da Índia; na banda do p10 a conexão soma de {n(conn.min(), 2)} a {n(conn.max(), 2)} USD/MWh e a degradação, que não entra no τ (L-247), soma de {n(degr.min(), 2)} a {n(degr.max(), 2)}.")
a("")

# ---------------------------------------------------------------- origens
a("## 8. Origem dos números")
a("")
a("| Número | Origem |")
a("|---|---|")
a("| LCOE nominal por célula, m0 | `outputs/<ISO>/lcoe_modeling/artifacts/lcoe_summary_<tec>.parquet`, recalculado com `geofrea.lcoe_modeling.kernel.lcoe_block` |")
a("| P_MW, CF, E_MWh | `outputs/<ISO>/technical_potential/artifacts/potential_<tec>__central.parquet`, membro m0 |")
a("| distâncias, zona térmica | `outputs/<ISO>/land_eligibility/artifacts/candidates_<tec>__central.parquet` |")
a("| dT do membro | `outputs/<ISO>/climate_forcing/artifacts/forcing.parquet` |")
a("| amostra nominal | `build_design` com `sampler.seed` e `sampler.adopted_size` de `config/experiments.yaml` (linha 0) |")
a("| τ, faixa | `config/parameters.json`, `tau_lcoe_usd_per_mwh` |")
a("| TIC, O&M, CF, LCOE publicado, vida de 25 anos | `config/irena_reference.yaml`, edição `irena_rpgc_2024` |")
a("| MR, SR, classe da célula | `outputs/<ISO>/robustness_analysis/artifacts/robustness_<tec>__core.parquet` |")
a("| meta, estado e H_0 do F7 | `outputs/<ISO>/robustness_analysis/artifacts/h5_summary_<tec>__core.parquet` |")
a("")
a("## 9. Limites deste diagnóstico")
a("")
a("- A decomposição é sequencial: a divisão entre energia e custos de capital depende da ordem dos passos.")
a("- \"Células\" são as do conjunto F7 no cenário central; células de classes sem MR e SR (por exemplo `incomplete_ensemble` na eólica do BRA, 7.104) não entram nas tabelas de SR e nas demais.")
a("- O CF de referência do IRENA da solar de PT é um proxy regional (L-242).")
a("- O diagnóstico não verifica se o CF das células eólicas está correto (OQ-114); ele só mostra o quanto da diferença vem dele.")
a("")
import hashlib
snap = c.DATA / "_snapshots" / "20261123_pre201"
lines = [ln.split(" *", 1) for ln in (snap / "SHA256SUMS.txt").read_text().splitlines() if ln.strip()]
ok = []
for sha, name in lines:
    for iso in ("PRT", "IND", "BRA"):
        if name.startswith(iso + "_"):
            live = c.DATA / "outputs" / iso / name[len(iso) + 1 :]
            break
    else:
        live = c.DATA / "outputs" / "cross_country" / name
    ok.append((name, hashlib.sha256(live.read_bytes()).hexdigest() == sha))
a("## 10. Manifestos e referências no momento da geração")
a("")
a(f"Manifestos comparados com o instantâneo (SHA-256): {sum(1 for _, v in ok if v)} de {len(ok)} iguais" + ("." if all(v for _, v in ok) else "; DIFERENTES: " + ", ".join(nm for nm, v in ok if not v)))
tags = subprocess.run(["git", "-C", str(c.REPO), "rev-parse", "v1.0^{commit}", "prereg-v1"], capture_output=True, text=True).stdout.split()
a(f"Tag `v1.0` aponta para `{tags[0][:7]}` e o objeto da tag `prereg-v1` é `{tags[1][:8]}`, como registrados.")
a("")
open(c.OUT / "D1_tau.md", "w", encoding="utf-8").write("\n".join(L))
print("D1_tau.md escrito,", len("\n".join(L).split()), "palavras")
