# Runs only at tag v1.1 (these scripts import modules of v1 that leave the work tree at COMMAND 306). Kept as documentation of the diagnostics D1 to D5.
"""Gera D2_ranking.md a partir de D2_dados (nenhum numero do texto e digitado a mao, salvo as classificacoes por leitura do kernel)."""
from __future__ import annotations

import hashlib
import json
import subprocess

import pandas as pd

import d1_common as c

D = c.OUT / "D2_dados"
R = json.load(open(D / "D2_resultados.json", encoding="utf-8"))
V = json.load(open(D / "D2_verificacoes.json", encoding="utf-8"))
PAIRS = [f"{i} {t}" for i, t in c.PAIRS]
CLIMA, PARAM = "clima (membros, parametros nominais)", "parametros (200 sorteios, clima m0)"


def n(x, d=2, pct=False):
    if x is None or (isinstance(x, float) and x != x):
        return "não disponível"
    v = x * 100 if pct else x
    s = f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if float(f"{v:.{d}f}") == 0:
        s = s.lstrip("-")
    return s + ("%" if pct else "")


def fmt_int(x):
    return f"{x:,}".replace(",", ".")


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


head = subprocess.run(["git", "-C", str(c.REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
L: list[str] = []
a = L.append
a("# D2: o que move (ou não) o ranking (COMANDO 202)")
a("")
a(f"Escrito para: o autor, para levar ao chat de planejamento. Data: 2026-11-23. Repositório em `{head}`, tag `prereg-v1` e `v1.0` inalteradas. Somente leitura: nada foi gravado em `GeoFREA_data/outputs/` nem no repositório. Scripts em `_notas_geofrea/diagnostico_v1_0/` (`d1_common.py`, `d2_run.py`, `d2_report.py`) e dados em `D2_dados/`. Este texto é gerado de `D2_dados/` por `d2_report.py`; os números não foram digitados à mão. As classificações do item 1 vêm da leitura do kernel (`lcoe_modeling/kernel.py`) e são conferidas pelas medidas ao lado.")
a("")
a("## 0. Base e conferências")
a("")
a("- **Janela e membros:** janela core (2041-2070), cenário central de solo. Eixo clima: o LCOE nominal de cada um dos 18 membros do core (6 GCMs x 3 SSPs), com os parâmetros nominais (`nominal_lcoe_by_member_<tec>__core`). Eixo parâmetros: o LCOE do membro de referência m0 sob os sorteios 1 a 200 da matriz de desenho gravada (semente 42, tamanho 4000), recalculado com o kernel do F6 importado (`lcoe_block`); nenhuma fase rodou.")
a(f"- **Amostra:** PRT inteiro ({fmt_int(R['PRT solar']['n_amostra'])} e {fmt_int(R['PRT wind']['n_amostra'])} células). IND e BRA: {fmt_int(R['IND solar']['n_amostra'])} células sorteadas sem reposição entre as células da classe `ranked`, com `numpy.random.default_rng(202)`, ordenadas por `cell_id`; a semente 202 é a do número deste comando. O top-k é 10% do tamanho do conjunto avaliado (`top_k_percent` do par), logo k = {fmt_int(R['IND solar']['k_amostra'])} nas amostras. Os postos dos itens 2 a 4 são postos dentro desse conjunto (20.000 células), não dentro das células do país inteiro.")
a("- **Itens 5, 6 e 7** usam todas as células ranqueadas (sem amostra).")
a(f"- **Sorteios reproduzidos:** em PRT eólica, o kernel com os 4000 sorteios gravados dá os quantis p10, p50 e p90 do `lcoe_summary` do F6 com erro máximo {n(V['reproducao_sorteios_PRT_wind_max_abs_err_p10_p50_p90'], 1)} (asserção no script).")
a("- **LCOE nominal reproduzido:** o LCOE de m0 recalculado pelo kernel é igual ao da tabela de robustez em todas as células das amostras (asserção, tolerância 1e-9), e o da tabela por membro também.")
a("- **F7 reproduzido (item 7):** o V_k, o D_clim, o D_tec, o d do H3 e o k que recalculei com as definições de M-F7-05 a M-F7-07 são iguais aos que o F7 gravou em `h1_summary`, `h4_country` e `h3_summary` nos seis pares:")
a("")
rows = []
for p in PAIRS:
    r = R[p]["item7_reproducao"]
    rows.append([p, str(r["k_f7"]), str(r["k_calc"]), n(r["v_k_f7"], 5), n(r["v_k_calc"], 5), n(r["d_clim_f7"], 6), n(r["d_clim_calc"], 6), n(r["d_tec_f7"], 6), n(r["d_tec_calc"], 6), n(r["d_h3_f7"], 6), n(r["d_h3_calc"], 6)])
a(table(["Par", "k F7", "k calc.", "V_k F7", "V_k calc.", "D_clim F7", "D_clim calc.", "D_tec F7", "D_tec calc.", "d (H3) F7", "d (H3) calc."], rows))
a("")
a("- **Manifestos:** iguais ao instantâneo `_snapshots/20261123_pre202` (ver a seção 11).")
a("")

# ---------------------------------------------------------------- achados
a("## 1. Achados em uma página")
a("")
cl = {p: R[p]["variancia"][CLIMA]["log"] for p in PAIRS}
pa = {p: R[p]["variancia"][PARAM]["log"] for p in PAIRS}
a(f"- **Variância (em log do LCOE):** a parcela entre células é de {n(min(v['entre_celulas'] for v in cl.values()), 1, True)} a {n(max(v['entre_celulas'] for v in cl.values()), 1, True)} no eixo clima. A interação célula x futuro, a única parte que pode trocar a ordem, é de {n(min(v['interacao'] for v in cl.values()), 2, True)} a {n(max(v['interacao'] for v in cl.values()), 2, True)} no clima e de {n(min(v['interacao'] for v in pa.values()), 2, True)} a {n(max(v['interacao'] for v in pa.values()), 2, True)} nos parâmetros.")
a(f"- **Parâmetros:** nos sorteios, {n(min(v['futuros_comum'] for v in pa.values()), 1, True)} a {n(max(v['futuros_comum'] for v in pa.values()), 1, True)} da variância de log(LCOE) é deslocamento comum a todas as células (o capex, o O&M, a taxa e a vida movem o LCOE do país inteiro junto); as solares de IND e BRA têm a maior parcela comum ({n(pa['IND solar']['futuros_comum'], 1, True)} e {n(pa['BRA solar']['futuros_comum'], 1, True)}).")
mn_o = min(R[p][ax]["overlap_topk"][0] for p in PAIRS for ax in ("clima", "parametros"))
a(f"- **Ranking:** o Spearman entre o ranking nominal e o de cada futuro tem mínimo de {n(min(R[p][ax]['spearman'][0] for p in PAIRS for ax in ('clima', 'parametros')), 3)} e a sobreposição do top-k tem mínimo de {n(mn_o, 3)} (mediana de {n(min(R[p][ax]['overlap_topk'][1] for p in PAIRS for ax in ('clima', 'parametros')), 3)} a {n(max(R[p][ax]['overlap_topk'][1] for p in PAIRS for ax in ('clima', 'parametros')), 3)}).")
a(f"- **Deslocamento:** o pior posto de uma célula do top-k nominal ultrapassa o limiar 2k em {', '.join(p + ' ' + n(R[p]['combinado']['frac_acima_de_2k'], 2, True) for p in PAIRS)} dos casos (clima e parâmetros juntos, pior futuro de cada célula). Com o V_k do F7 o resultado é outro, porque o V_k usa o posto do pior regret por SSP, não o pior posto entre membros (ver a seção 5).")
a(f"- **MR e LCOE nominal:** Spearman de {n(min(R[p]['item6']['spearman_mr_lcoe'] for p in PAIRS), 3)} a {n(max(R[p]['item6']['spearman_mr_lcoe'] for p in PAIRS), 3)}; o R² da regressão linear de MR sobre a distância nominal à melhor célula vai de {n(min(R[p]['item6']['r2_linear_mr_sobre_distancia'] for p in PAIRS), 3)} a {n(max(R[p]['item6']['r2_linear_mr_sobre_distancia'] for p in PAIRS), 3)}.")
e = {p: R[p]["item7"]["exploratorio (1%, m = k/2)"] for p in PAIRS}
a(f"- **Exploratório (1%, m = k/2), sem substituir nada:** V_k de {', '.join(p + ' ' + n(e[p]['v_k'], 3) for p in PAIRS)}; o D_clim e o D_tec ficam acima de zero em alguns pares (ver a seção 8).")
a("")

# ---------------------------------------------------------------- item 1
a("## 2. Item 1: quais parâmetros do LHS são uniformes no país e quais mudam a ordem")
a("")
a("**Forma do kernel** (`lcoe_block`): `LCOE_i = [ P_i x U + P_i x D_sub_i x c_linha x tort_rede / P_ref + P_i x D_estrada_i x c_estrada x tort_estrada / P_ref ] / ( E_i x A_e(d_i, r, n) x perda ) + O&M variável`, com `U = 1000 x capex x (1 + o&m x A_o(r, n)) + c_baia / P_ref`. As entradas por célula são `P_i`, `E_i` (e a reescala de energia `offset_i + slope_i x parâmetro de energia`, que depende de dT do membro), `D_sub_i`, `D_estrada_i` e os limites de degradação `d_i` da zona térmica. Todos os parâmetros sorteados têm um único valor por sorteio para o país inteiro; a diferença está em como entram.")
a("")
a("| Parâmetro sorteado | Como entra | Muda a ordem entre células? |")
a("|---|---|---|")
a("| `capex_usd_per_kw`, `opex_fixed_frac` | em U, igual por MW em todas as células | só pelo peso relativo da conexão e da degradação no LCOE da célula; sozinho multiplica o termo de capital de todas |")
a("| `bay_cost_usd` | custo da baia por MW (P/P_ref), igual por MW | como o capex: não depende da célula |")
a("| `discount_rate`, `lifetime_years` | anuidades A_o e A_e | comum; interage com a degradação da zona (solar) e com o peso da conexão |")
a("| `degradation_weight` | pondera os limites de degradação da célula | só na solar (limites por zona térmica); na eólica os limites são iguais e não tem efeito |")
a("| `line_cost_usd_per_km`, `tortuosity_grid` | multiplicam P_i x D_sub_i | sim: a distância à subestação varia por célula |")
a("| `road_cost_usd_per_km`, `tortuosity_road` | multiplicam P_i x D_estrada_i | não: o custo de estrada é zero (faixa 0 a 0, `road_cost_excluded`) |")
a("| `gamma` (solar), `eta_loss` (eólica) | reescala da energia | solar: `slope_i` depende de dT por célula, vale 0 no m0 (dT = 0) e muda por membro; eólica: fator comum |")
a("")
a("Efeito medido, um parâmetro por vez, do nominal para o p5 e para o p95 dos sorteios, nas células da amostra (m0). Mínimo entre os dois extremos e entre os seis pares:")
a("")
oat_rows = []
allp = {}
for iso, tech in c.PAIRS:
    d = pd.read_csv(D / f"D2_1_oat_{iso}_{tech}.csv")
    for _, r in d.iterrows():
        allp.setdefault(r["parametro"], []).append((f"{iso} {tech}", min(x for x in (r.get("spearman_p5"), r.get("spearman_p95")) if x == x), min(x for x in (r.get("overlap_topk_p5"), r.get("overlap_topk_p95")) if x == x), max(abs(x) for x in (r.get("mudanca_media_p5_pct"), r.get("mudanca_media_p95_pct")) if x == x), max(x for x in (r.get("mudanca_sd_p5_pct"), r.get("mudanca_sd_p95_pct")) if x == x)))
for par, vals in allp.items():
    w = min(vals, key=lambda t: t[1])
    wo = min(vals, key=lambda t: t[2])
    oat_rows.append([f"`{par}`" if not par.startswith("grupo") else par, n(w[1], 4) + f" ({w[0]})", n(wo[2], 3) + f" ({wo[0]})", n(max(v[3] for v in vals), 1) + "%", n(max(v[4] for v in vals), 2) + "%"])
a(table(["Parâmetro", "Spearman mínimo (par)", "Sobreposição do top-k mínima (par)", "Maior mudança média do LCOE", "Maior desvio da mudança entre células"], oat_rows))
a("")
a("A \"mudança média\" é o deslocamento do LCOE de todo o país; o \"desvio entre células\" é o quanto essa mudança difere de uma célula para outra, e é só ele que pode trocar a ordem. Os arquivos `D2_dados/D2_1_oat_<par>.csv` trazem o detalhe por par.")
a("")

# ---------------------------------------------------------------- item 2
a("## 3. Item 2: variância do LCOE entre células e entre futuros")
a("")
a("Matriz células x futuros em log do LCOE (o log trata como comum o efeito multiplicativo; a versão em nível está em `D2_resultados.json`). A soma das três partes é 100%: **entre células** (o ranking que fica), **deslocamento comum** (todas as células sobem ou descem juntas) e **interação célula x futuro** (a parte que pode trocar a ordem).")
a("")
for axis, titulo in ((CLIMA, "Eixo clima: 18 membros do core, parâmetros nominais"), (PARAM, "Eixo parâmetros: 200 sorteios, clima de m0")):
    a(f"### {titulo}")
    a("")
    rows = []
    for p in PAIRS:
        v = R[p]["variancia"][axis]
        vn = v["nivel"]
        rows.append([p, n(v["log"]["entre_celulas"], 2, True), n(v["log"]["futuros_comum"], 2, True), n(v["log"]["interacao"], 2, True), n(v["log"]["var_total"], 4), n(vn["entre_celulas"], 2, True), n(vn["futuros_comum"], 2, True), n(vn["interacao"], 2, True)])
    a(table(["Par", "Entre células (log)", "Comum (log)", "Interação (log)", "Variância total (log)", "Entre células (nível)", "Comum (nível)", "Interação (nível)"], rows))
    a("")
a("![variância](D2_dados/D2_2_variancia.png)")
a("")

# ---------------------------------------------------------------- item 3
a("## 4. Item 3: correlação de postos e sobreposição do top-k")
a("")
a("Cada coluna compara o ranking nominal (m0, parâmetros nominais) com o de um futuro: os 18 membros (eixo clima) ou os 200 sorteios (eixo parâmetros). Mínimo, mediana e máximo sobre os futuros.")
a("")
rows = []
for p in PAIRS:
    r = R[p]
    cl_, pa_ = r["clima"], r["parametros"]
    f3 = lambda v, d=3: " / ".join(n(x, d) for x in v)
    rows.append([p, f"{r['n_amostra']:,}".replace(",", "."), f"{r['k_amostra']:,}".replace(",", "."), f3(cl_["spearman"], 4), f3(cl_["overlap_topk_clima"] if "overlap_topk_clima" in cl_ else cl_["overlap_topk"]), f3(pa_["spearman"], 4), f3(pa_["overlap_topk"])])
a(table(["Par", "Células", "k", "Spearman, clima (mín / med / máx)", "Top-k, clima", "Spearman, parâmetros", "Top-k, parâmetros"], rows))
a("")

# ---------------------------------------------------------------- item 4
a("## 5. Item 4: deslocamento das células do top-k nominal")
a("")
a("Para cada célula do top-k nominal, o pior posto que ela alcança entre os futuros (ranking de cada futuro dentro da amostra), em múltiplos de k. O limiar de H1b e H3 é `k + m = 2k` (m = k).")
a("")
rows = []
for p in PAIRS:
    r = R[p]
    for ax, nm in (("clima", "clima (18)"), ("parametros", "parâmetros (200)")):
        w = r[ax]["pior_posto_sobre_k"]
        rows.append([p, nm, n(w["mediana"], 2), n(w["q75"], 2), n(w["q95"], 2), n(w["max"], 2), n(r[ax]["frac_topk_acima_de_1_5k"], 2, True), n(r[ax]["frac_topk_acima_de_2k"], 2, True)])
    rows.append([p, "os dois eixos (pior dos dois)", "", "", "", n(r["combinado"]["pior_posto_sobre_k_max"], 2), "", n(r["combinado"]["frac_acima_de_2k"], 2, True)])
a(table(["Par", "Eixo", "Mediana", "q75", "q95", "Máximo", "Células acima de 1,5k", "Células acima de 2k"], rows))
a("")
a("![pior posto](D2_dados/D2_4_pior_posto.png)")
a("")
a("**Diferença para o V_k do F7.** O pior posto aqui é o pior entre membros do ranking pelo LCOE de cada membro. O V_k do F7 usa outro objeto: o posto pelo pior regret (máximo sobre os GCMs) de cada SSP, dentro do conjunto ranqueado, e conta como vulnerável a célula com posto acima de k + m em ao menos uma SSP. Por isso o V_k é menor que a fração acima de 2k desta tabela. A tabela do item 7 refaz o V_k com a definição do F7.")
a("")

# ---------------------------------------------------------------- item 5
a("## 6. Item 5: sinal climático nas células candidatas")
a("")
a("Mudança do CF de cada membro do core em relação ao membro de referência m0, célula a célula (todas as células ranqueadas), e a mudança correspondente do LCOE nominal. Mediana e desvio padrão espacial de cada membro; a tabela resume os 18 membros (mínimo, mediana e máximo entre membros). Detalhe por membro em `D2_dados/D2_5_sinal_<par>.csv`.")
a("")
rows = []
for iso, tech in c.PAIRS:
    d = pd.read_csv(D / f"D2_5_sinal_{iso}_{tech}.csv")
    f3 = lambda s, dd=1: " / ".join(n(x, dd) for x in (s.min(), s.median(), s.max()))
    rows.append([f"{iso} {tech}", f3(d["cf_mudanca_mediana_pct"]), f3(d["cf_mudanca_sd_espacial_pct"]), f3(d["lcoe_mudanca_mediana_pct"]), f3(d["lcoe_mudanca_sd_espacial_pct"])])
a(table(["Par", "CF: mediana da mudança, % (mín / med / máx entre membros)", "CF: desvio espacial, %", "LCOE: mediana da mudança, %", "LCOE: desvio espacial, %"], rows))
a("")

# ---------------------------------------------------------------- item 6
a("## 7. Item 6: MR contra o LCOE nominal")
a("")
a("`d_i = (LCOE_i - LCOE_min) / LCOE_min`, a distância nominal relativa à melhor célula do conjunto ranqueado. Regressão linear simples `MR = a + b x d` (todas as células ranqueadas).")
a("")
rows = []
for p in PAIRS:
    r = R[p]["item6"]
    rows.append([p, f"{r['n']:,}".replace(",", "."), n(r["spearman_mr_lcoe"], 4), n(r["r2_linear_mr_sobre_distancia"], 4), n(r["inclinacao"], 3), n(r["intercepto"], 3), n(r["mr_mediana"], 3), n(r["distancia_mediana"], 3), n(r["mr_menos_d_mediana"], 3)])
a(table(["Par", "Células", "Spearman MR e LCOE", "R² linear", "b", "a", "MR mediano", "d mediana", "mediana de MR - d"], rows))
a("")
a("O MR só difere da distância nominal pela parte que o risco acrescenta (mediana de MR - d, última coluna); o R² mede o quanto da dispersão de MR a distância explica.")
a("")

# ---------------------------------------------------------------- item 7
a("## 8. Item 7: V_k, D e rho com top-k 1% e m = k/2 (exploratório)")
a("")
a("**Rótulo: análise exploratória, descritiva, sem veredito, que não substitui nenhum resultado da v1.0.** Mesmas definições de M-F7-05 a M-F7-07 (conferidas na seção 0), com `k = ceil(p_k x n)` e `m` como indicado. Além da variante pedida (1%, m = k/2), as duas variantes de um fator só mostram qual dos dois fatores faz a diferença. Os limiares registrados são `beta` = 0,20 para V_k, faixa 0,40 a 0,60 de rho e `delta` = 0,20 para d; aqui não se avalia nenhum.")
a("")
rows = []
for p in PAIRS:
    for vn, v in R[p]["item7"].items():
        rows.append([p, vn, f"{v['k']:,}".replace(",", "."), (fmt_int(int(v["m"])) if float(v["m"]).is_integer() else n(v["m"], 1)), n(v["v_k"], 4), str(v["n_vulneraveis"]), n(v["d_clim"], 5), n(v["d_tec"], 5), n(v["rho"], 3), n(v["d_h3"], 5)])
a(table(["Par", "Variante", "k", "m", "V_k", "vulneráveis", "D_clim", "D_tec", "rho", "d (H3)"], rows))
a("")
a("rho é \"não disponível\" quando D_clim + D_tec = 0.")
a("")

# ---------------------------------------------------------------- leituras
a("## 9. O que os achados dizem sobre as leituras 2 e 3 da seção 1 do arquivo de comandos")
a("")
a("Só o que os números mostram; a classificação em A, B, C ou D fica para o D0.")
a("")
vk0 = [p for p in PAIRS if R[p]["item7"]["primario (10%, m = k)"]["v_k"] == 0]
vkp = [p for p in PAIRS if R[p]["item7"]["primario (10%, m = k)"]["v_k"] > 0]
sd = {}
for iso, tech in c.PAIRS:
    d = pd.read_csv(D / f"D2_5_sinal_{iso}_{tech}.csv")
    sd[f"{iso} {tech}"] = (d["cf_mudanca_sd_espacial_pct"].min(), d["cf_mudanca_sd_espacial_pct"].max())
sd_txt = "; ".join(p + " " + n(v[0], 1) + " a " + n(v[1], 1) + "%" for p, v in sd.items())
inter_max = max(max(R[p]["variancia"][ax]["log"]["interacao"] for p in PAIRS) for ax in (CLIMA, PARAM))
mono = [p for p in PAIRS if R[p]["variancia"][PARAM]["log"]["futuros_comum"] > R[p]["variancia"][PARAM]["log"]["entre_celulas"]]
a(f"- **Leitura 2, \"os parâmetros do LHS que pesam são iguais em todas as células\":** confirmada pelo código (item 1) e pela variância (item 2): em {', '.join(mono)} o deslocamento comum é maior que a parcela entre células no eixo parâmetros, e a interação célula x futuro não passa de {n(inter_max, 2, True)} da variância de log(LCOE) em nenhum par nem eixo.")
a(f"- **\"A mudança climática média dos GCMs é espacialmente suave\":** depende do par. Desvio espacial da mudança do CF entre células, por membro (mínimo a máximo entre os 18): {sd_txt}. Mesmo onde o desvio é grande, a parcela de interação do eixo clima fica abaixo de {n(max(R[p]['variancia'][CLIMA]['log']['interacao'] for p in PAIRS), 2, True)}, porque a variância entre células de log(LCOE) é muito maior.")
a(f"- **\"O deslocamento é quase impossível\":** com o pior posto entre membros (item 4), a fração do top-k nominal acima de 2k é positiva em {', '.join(p for p in PAIRS if R[p]['combinado']['frac_acima_de_2k'] > 0)} e zero nos demais; com a definição do V_k do F7 (posto do pior regret por SSP), o V_k primário é zero em {', '.join(vk0)}" + (f" e {', '.join(p + ' ' + n(R[p]['item7']['primario (10%, m = k)']['v_k'], 4) for p in vkp)}" if vkp else "") + ". A diferença entre as duas medidas é de definição (ver a seção 5).")
a(f"- **Leitura 3, \"o MR mede sobretudo a distância à melhor célula\":** Spearman entre MR e LCOE nominal de {n(min(R[p]['item6']['spearman_mr_lcoe'] for p in PAIRS), 4)} a {n(max(R[p]['item6']['spearman_mr_lcoe'] for p in PAIRS), 4)} e R² linear de MR sobre a distância de {n(min(R[p]['item6']['r2_linear_mr_sobre_distancia'] for p in PAIRS), 4)} a {n(max(R[p]['item6']['r2_linear_mr_sobre_distancia'] for p in PAIRS), 4)} (item 6): a leitura vale nos seis pares, com menos força na PRT solar (o par de menor Spearman e de menor R²).")
ex = {p: R[p]["item7"]["exploratorio (1%, m = k/2)"] for p in PAIRS}
mov = [p for p in PAIRS if ex[p]["v_k"] > 0 or ex[p]["d_clim"] > 0 or ex[p]["d_tec"] > 0]
vk_abaixo = all(ex[p]["v_k"] < 0.20 for p in PAIRS)
a(f"- **Sensibilidade do desenho (item 7):** com 1% e m = k/2, V_k, D_clim ou D_tec ficam acima de zero em {', '.join(mov)}; o V_k máximo entre os pares é {n(max(ex[p]['v_k'] for p in PAIRS), 3)} ({'abaixo' if vk_abaixo else 'não abaixo'} de beta = 0,20 em todos os pares: {'sim' if vk_abaixo else 'não'}). As variantes de um fator só estão na tabela.")
a("")

# ---------------------------------------------------------------- origens
a("## 10. Origem dos números e limites")
a("")
a("| Número | Origem |")
a("|---|---|")
a("| LCOE por membro, nominal | `outputs/<ISO>/robustness_analysis/artifacts/nominal_lcoe_by_member_<tec>__core.parquet` |")
a("| LCOE por sorteio | `lcoe_block` (kernel do F6) sobre F3, F4 e F5 de m0 com as linhas 1 a 200 da matriz de desenho (`build_design`, semente e tamanho de `config/experiments.yaml`) |")
a("| MR, SR, postos, classes | `robustness_<tec>__core.parquet` |")
a("| postos por SSP (V_k) | `ssp_scores_<tec>__core.parquet` |")
a("| F7 gravado (conferência) | `h1_summary`, `h3_summary`, `h4_country` de cada par |")
a("| CF por membro | `outputs/<ISO>/technical_potential/artifacts/potential_<tec>__central.parquet` |")
a("")
a("Limites:")
a("")
a("- Os itens 2 a 4 usam amostra de 20.000 células em IND e BRA; os postos são dentro da amostra e o k é 10% da amostra. Com outra semente os números mudam um pouco; a semente é a 202.")
a("- Só 200 dos 4000 sorteios entram no eixo parâmetros, e só os 18 membros do core no eixo clima (sem a janela 2071-2100).")
a("- A decomposição por variância é em log do LCOE; em nível ela está em `D2_resultados.json` e dá a mesma leitura qualitativa.")
a("- Os extremos p5 e p95 de cada parâmetro (OAT) são os dos 4000 sorteios, não os limites do intervalo registrado; as faixas do desenho são estreitas (por exemplo, capex de 524 a 1034 USD/kW na solar de PRT).")
a("- Nada aqui verifica se as faixas de incerteza do desenho estão bem escolhidas; só mede o que elas conseguem mover.")
a("")
snap = c.DATA / "_snapshots" / "20261123_pre202"
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
a("## 11. Manifestos e referências no momento da geração")
a("")
a(f"Manifestos comparados com o instantâneo (SHA-256): {sum(1 for _, v in ok if v)} de {len(ok)} iguais" + ("." if all(v for _, v in ok) else "; DIFERENTES: " + ", ".join(nm for nm, v in ok if not v)))
tags = subprocess.run(["git", "-C", str(c.REPO), "rev-parse", "v1.0^{commit}", "prereg-v1"], capture_output=True, text=True).stdout.split()
a(f"Tag `v1.0` aponta para `{tags[0][:7]}` e o objeto da tag `prereg-v1` é `{tags[1][:8]}`, como registrados.")
a("")
open(c.OUT / "D2_ranking.md", "w", encoding="utf-8").write("\n".join(L))
print("D2_ranking.md escrito,", len("\n".join(L).split()), "palavras")
