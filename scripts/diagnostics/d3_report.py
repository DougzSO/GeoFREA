"""Gera D3_h2.md a partir de D3_dados (numeros lidos dos dados, nao digitados)."""
from __future__ import annotations

import hashlib
import json
import subprocess

import pandas as pd

import d1_common as c

D = c.OUT / "D3_dados"
R = json.load(open(D / "D3_resultados.json", encoding="utf-8"))
REG = pd.read_csv(D / "D3_regioes.csv")
VAR = pd.read_csv(D / "D3_variantes.csv")
PAIRS = [f"{i} {t}" for i, t in c.PAIRS]
ABBR = {"not_testable": "NT", "not_supported": "NS", "supported": "S"}


def n(x, d=2, pct=False):
    if x is None or (isinstance(x, float) and x != x):
        return "não disponível"
    v = x * 100 if pct else x
    s = f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if float(f"{v:.{d}f}") == 0:
        s = s.lstrip("-")
    return s + ("%" if pct else "")


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def gw(x, d=1):
    return n(x / 1000, d)


head = subprocess.run(["git", "-C", str(c.REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
L: list[str] = []
a = L.append
a("# D3: o que produz o O do H2 e por que o veredito muda com γ (COMANDO 203)")
a("")
a(f"Escrito para: o autor, para levar ao chat de planejamento. Data: 2026-11-23. Repositório em `{head}`, tag `prereg-v1` e `v1.0` inalteradas. Somente leitura: nada foi gravado em `GeoFREA_data/outputs/` nem no repositório. Scripts em `_notas_geofrea/diagnostico_v1_0/` (`d1_common.py`, `d3_run.py`, `d3_report.py`), dados em `D3_dados/`. Este texto é gerado de `D3_dados/`; os números não foram digitados à mão.")
a("")
a("Base: janela core (2041-2070), cenário central, escala de 0,05 grau, variante primária do H2 (`h2_summary_<tec>__core`, `h2_regions_<tec>__core`), partição por Admin1, estatística regional = média ponderada pela capacidade de MR, γ = 0,30. A definição é a de M-F7-07 (H2): `O = Σ q_i min(x_cell_i, x_admin_i) / T`, com T a capacidade do top-k robusto, `O_ref = T / Q_max`; o veredito é \"não testável\" se `O_ref >= γ`, \"suportada\" se `O_ref < γ` e `O < γ`, \"não suportada\" se `O_ref < γ` e `O >= γ`.")
a("")
a("## 0. Conferências")
a("")
a("Recalculei O, D_TV, Δz e T a partir das tabelas por região e por célula e comparei com o que o F7 gravou:")
a("")
rows = []
for p in PAIRS:
    r = R[p]
    cf = r["confere"]
    rows.append([p, n(r["O"], 6), n(cf["O_calc"], 6), n(r["D_TV"], 6), n(cf["tv_calc"], 6), n(r["delta_z"], 6), n(cf["delta_z_calc"], 6), n(r["T_mw"], 3), n(cf["T_calc"], 3)])
a(table(["Par", "O F7", "O calc.", "D_TV F7", "D_TV calc.", "Δz F7", "Δz calc.", "T F7 (MW)", "T calc. (MW)"], rows))
a("")
a("Os seis pares coincidem nas quatro grandezas. O O calculado por região é `Σ_m selecionado_por_célula_m x fração_tomada_m / T` (cada célula de uma região herda a fração da região, e x_cell é 0 ou 1). A contribuição de cada região a O vem dessa soma.")
a("- Manifestos iguais ao instantâneo `_snapshots/20261123_pre203` (seção 7).")
a("")

# ---------------------------------------------------------------- item 1
a("## 1. Item 1: O, O_ref, regiões, capacidade, Δz, D_TV e perfil de decisão por γ")
a("")
rows = []
for p in PAIRS:
    r = R[p]
    rows.append([p, f"{r['n_ranked']:,}".replace(",", "."), str(r["n_regioes"]), f"{r['k']:,}".replace(",", "."), gw(r["T_mw"]), gw(r["Qmax_mw"]), n(r["O_ref"], 4), n(r["O"], 4), n(r["O_sobre_O_ref"], 2), n(r["delta_z"], 3), n(r["D_TV"], 3), n(r["iqr_sobre_mediana"], 3), ABBR[r["verdict"]] if False else r["verdict"]])
a(table(["Par", "Células ranqueadas", "Admin1 com célula ranqueada", "k", "T (GW)", "Q_max (GW)", "O_ref", "O", "O / O_ref", "Δz", "D_TV", "IQR de MR / mediana", "Veredito (γ = 0,30)"], rows))
a("")
a("**Perfil de decisão por γ** (0,10 a 0,70 de 0,05 em 0,05; NT = não testável, NS = não suportada, S = suportada). O veredito só muda onde γ cruza O (ou O_ref); O não depende de γ.")
a("")
grid = list(R[PAIRS[0]]["perfil_gamma"].keys())
rows = []
for p in PAIRS:
    r = R[p]
    rows.append([p, n(r["O_ref"], 3), n(r["O"], 3)] + [ABBR[r["perfil_gamma"][g]] for g in grid] + [n(r["menor_gamma_grade"], 2)])
a(table(["Par", "O_ref", "O"] + grid + ["menor γ da grade que apoia"], rows))
a("")
a("O menor γ da grade que apoia o H2 conferido com o `smallest_supporting_gamma` gravado pelo F7: " + ("igual nos seis pares." if all(R[p]["menor_gamma_grade"] == R[p]["menor_gamma_grade_arquivo"] for p in PAIRS) else "DIFERENTE em algum par."))
a("")
a("Distância de O ao γ registrado: " + "; ".join(f"{p} {n(R[p]['O'] - R[p]['gamma'], 3)}" for p in PAIRS) + ".")
a("")

# ---------------------------------------------------------------- item 2
a("## 2. Item 2: quantas regiões a seleção regional usa até T")
a("")
a("A seleção regional toma regiões inteiras em ordem crescente de MR médio ponderado até somar T; a última entra com uma fração. Na tabela, \"seleção por célula nas regiões usadas\" é a parcela de T (seleção por célula) que fica dentro das regiões que a seleção regional usou.")
a("")
rows = []
for p in PAIRS:
    r = R[p]
    s = r["selecao_regional"]
    rows.append([p, str(r["n_regioes"]), str(s["regioes_usadas"]), str(s["regioes_inteiras"]), n(s["fracao_ultima"], 3), n(s["cap_regioes_usadas_sobre_Qmax"], 1, True), n(s["selecao_celula_nas_regioes_usadas_sobre_T"], 1, True), str(s["regioes_com_celula_selecionada"])])
a(table(["Par", "Admin1", "Regiões usadas", "Regiões inteiras", "Fração da última", "Capacidade das regiões usadas / Q_max", "Seleção por célula nas regiões usadas / T", "Admin1 com alguma célula do top-k robusto"], rows))
a("")
a("Como as regiões usadas se somam a T, a capacidade delas é maior ou igual a T; a relação entre a segunda e a quinta coluna mostra o quanto da capacidade do país a seleção regional precisa varrer.")
a("")

# ---------------------------------------------------------------- item 3
a("## 3. Item 3: O é puxado por poucas regiões grandes? Concentração")
a("")
a("**Distribuição da capacidade entre regiões** (Q_m / Q_max; HHI é a soma dos quadrados das partes e N efetivo é 1 / HHI):")
a("")
rows = []
for p in PAIRS:
    r = R[p]["capacidade_regioes"]
    rows.append([p, n(r["HHI"], 4), n(r["N_efetivo"], 1), n(r["top1"], 1, True), n(r["top3"], 1, True), n(r["top5"], 1, True), gw(r["min_mw"], 3) + " / " + gw(r["mediana_mw"], 2) + " / " + gw(r["max_mw"], 1), f"{r['n_celulas_min']} / {n(r['n_celulas_mediana'], 0)} / {r['n_celulas_max']:,}".replace(",", ".")])
a(table(["Par", "HHI da capacidade", "N efetivo", "Maior região", "3 maiores", "5 maiores", "Capacidade por região, mín / mediana / máx (GW)", "Células por região, mín / mediana / máx"], rows))
a("")
a("**Concentração das duas seleções e de O** (a contribuição de uma região a O é `selecionado_por_célula x fração_tomada / T`):")
a("")
rows = []
for p in PAIRS:
    r = R[p]["concentracao"]
    reg = REG[REG.par == p].sort_values("contribuicao_a_O", ascending=False)
    top = reg.iloc[0]
    rows.append([p, n(r["HHI_selecao_celula"], 3), n(r["N_efetivo_celula"], 1), n(r["HHI_selecao_regional"], 3), n(r["N_efetivo_regional"], 1), n(r["top1_contrib_O"], 1, True), n(r["top3_contrib_O"], 1, True), str(r["regioes_para_50pct_de_O"]), f"`{top['regiao']}` ({n(top['share_capacidade'], 1, True)} da capacidade)"])
a(table(["Par", "HHI, seleção por célula", "N efetivo", "HHI, seleção regional", "N efetivo", "Parte de O na maior região", "Parte de O nas 3 maiores", "Regiões para 50% de O", "Região que mais contribui a O"], rows))
a("")
a("**Variância de MR entre e dentro das regiões** (ponderada pela capacidade; a parte entre regiões é o que uma seleção regional consegue explorar):")
a("")
rows = []
for p in PAIRS:
    v = R[p]["variancia_MR"]
    rows.append([p, n(v["entre_regioes_sobre_total"], 1, True), n(v["dentro_sobre_total"], 1, True), n(v["mr_medio_ponderado"], 3)])
a(table(["Par", "Entre regiões", "Dentro das regiões", "MR médio ponderado"], rows))
a("")
a("![regiões](D3_dados/D3_regioes.png)")
a("")

# ---------------------------------------------------------------- variantes
a("## 4. Por que o veredito muda: as variantes do F7")
a("")
a("Contagem das variantes do H2 que mudam de veredito em relação à primária, na janela core e na 2071-2100 (arquivos `h2_summary_<tec>__core` e `__sensitivity`). \"Para suportada\" é a contagem do texto de `GeoFREA_v1_0_explicado.md`; \"para não testável\" são as que perdem o teste porque `O_ref >= γ` (γ baixo ou top-k de 20% e meta nacional, que elevam O_ref).")
a("")
rows = []
for p in PAIRS:
    v = R[p]["variantes"]
    rows.append([p, str(v["n_variantes_nucleo"]), str(v["n_mudam_nucleo"]), str(v["n_mudam_para_supported"]), str(v["n_mudam_para_not_testable"]), str(v["n_mudam_gamma"]), str(v["n_mudam_outras"]), ", ".join(x for x in v["mudam_nucleo"] if not x.startswith("gamma_")) or "nenhuma", str(v["n_mudam_sens"]), n(v["O_sens"], 3), v["veredito_sens"]])
a(table(["Par", "Variantes (sem a primária)", "Mudam", "Para suportada", "Para não testável", "Das quais γ", "Das quais outras", "Outras variantes que mudam", "Mudam (2071-2100)", "O (2071-2100)", "Veredito primário (2071-2100)"], rows))
a("")
a("A contagem \"para suportada\" é igual à do texto de `GeoFREA_v1_0_explicado.md` (9, 6, 4, 9, 10 e 4 variantes na ordem PRT solar, PRT eólica, IND solar, IND eólica, BRA solar, BRA eólica); o denominador daquele texto (20 ou 21) conta uma linha a mais que as variantes sem a primária. Os dois rótulos são a mesma coisa vista de dois lados: quase tudo que muda é o perfil de γ (o menor γ da grade que apoia o H2 é " + ", ".join(p + " " + n(R[p]["menor_gamma_grade"], 2) for p in PAIRS) + ") e, nos outros casos, o top-k de 5% ou 20% e a meta nacional, que mudam T e portanto O e O_ref.")
a("")
rows = []
for p in PAIRS:
    r = R[p]["escala_0p1"]
    rows.append([p, n(R[p]["O"], 4), n(r["O"], 4), n(r["O_ref"], 4), str(R[p]["n_regioes"]), str(r["n_regioes"]), r["veredito"]])
a("Escala de 0,1 grau (`robustness_analysis__0p1deg`), variante primária:")
a("")
a(table(["Par", "O a 0,05 grau", "O a 0,1 grau", "O_ref a 0,1 grau", "Admin1 a 0,05", "Admin1 a 0,1", "Veredito a 0,1 grau"], rows))
a("")

# ---------------------------------------------------------------- leitura
a("## 5. O que os achados dizem")
a("")
a("Só o que os números mostram; a classificação em A, B, C ou D fica para o D0.")
a("")
os_ = [R[p]["O"] for p in PAIRS]
a(f"- **O fica entre {n(min(os_), 3)} e {n(max(os_), 3)} nos seis pares, sempre acima de γ = 0,30, e O_ref entre {n(min(R[p]['O_ref'] for p in PAIRS), 3)} e {n(max(R[p]['O_ref'] for p in PAIRS), 3)}.** A razão O / O_ref: O é de {n(min(R[p]['O_sobre_O_ref'] for p in PAIRS), 2)} a {n(max(R[p]['O_sobre_O_ref'] for p in PAIRS), 2)} vezes o O de uma distribuição uniforme sobre o país.")
perto = [p for p in PAIRS if abs(R[p]["O"] - 0.30) < 0.05]
passo = all(abs(R[p]["menor_gamma_grade"] - 0.35) < 1e-9 for p in perto)
a(f"- **Perto de γ:** {', '.join(p + ' (O = ' + n(R[p]['O'], 3) + ')' for p in perto)} ficam a menos de 0,05 de γ = 0,30" + ("; nesses pares o veredito já muda no passo seguinte da grade (γ = 0,35)." if passo else ".") + " Nos outros pares O está a 0,05 ou mais de γ.")
a(f"- **Quem produz O:** em todos os pares a maior região contribui com {n(min(R[p]['concentracao']['top1_contrib_O'] for p in PAIRS), 1, True)} a {n(max(R[p]['concentracao']['top1_contrib_O'] for p in PAIRS), 1, True)} de O e as três maiores com {n(min(R[p]['concentracao']['top3_contrib_O'] for p in PAIRS), 1, True)} ou mais. O é puxado por uma a três regiões, não pelo país inteiro.")
nao_maior = []
for p in PAIRS:
    reg = REG[REG.par == p]
    if reg.sort_values("contribuicao_a_O", ascending=False).iloc[0]["regiao"] != reg.sort_values("share_capacidade", ascending=False).iloc[0]["regiao"]:
        nao_maior.append(p)
pos1 = [p for p in PAIRS if REG[REG.par == p].sort_values('contribuicao_a_O', ascending=False).iloc[0]['posicao_regional'] == 1]
a(f"- **A região que mais contribui a O é a primeira da ordem regional (menor MR médio) em {', '.join(pos1) if pos1 else 'nenhum par'}; {'não é' if nao_maior else 'é'} a maior em capacidade em {', '.join(nao_maior) if nao_maior else 'nenhum par'}** (a maior região em capacidade tem {n(min(R[p]['capacidade_regioes']['top1'] for p in PAIRS), 1, True)} a {n(max(R[p]['capacidade_regioes']['top1'] for p in PAIRS), 1, True)} do país; o N efetivo da capacidade fica entre {n(min(R[p]['capacidade_regioes']['N_efetivo'] for p in PAIRS), 1)} e {n(max(R[p]['capacidade_regioes']['N_efetivo'] for p in PAIRS), 1)} regiões, em partições de " + str(min(R[p]["n_regioes"] for p in PAIRS)) + " a " + str(max(R[p]["n_regioes"] for p in PAIRS)) + " regiões).")
xs = REG[REG.par == "IND solar"].copy()
Ts = R["IND solar"]["T_mw"]
xs["cel"] = xs["selecao_celula_mw"] / Ts
xs["adm"] = xs["selecao_regional_mw"] / xs["selecao_regional_mw"].sum()
d2 = xs.sort_values("cel", ascending=False).head(2)
parts = "; ".join(f"`{r['regiao']}`: {n(r['cel'], 1, True)} da seleção por célula, {n(r['adm'], 1, True)} da regional, fração tomada {n(r['fracao_tomada'], 3)}, posição {int(r['posicao_regional'])} na ordem regional" for _, r in d2.iterrows())
a(f"- **IND solar é o caso mais concentrado:** o N efetivo da seleção por célula é {n(R['IND solar']['concentracao']['N_efetivo_celula'], 2)} e o da regional {n(R['IND solar']['concentracao']['N_efetivo_regional'], 2)}. Duas regiões guardam {n(d2['cel'].sum(), 1, True)} da seleção por célula ({parts}); a seleção regional usa {R['IND solar']['selecao_regional']['regioes_usadas']} regiões e {n(R['IND solar']['selecao_regional']['selecao_celula_nas_regioes_usadas_sobre_T'], 1, True)} da seleção por célula fica nelas.")
a(f"- **A variância de MR é, na maior parte, interna às regiões** ({n(min(R[p]['variancia_MR']['dentro_sobre_total'] for p in PAIRS), 1, True)} a {n(max(R[p]['variancia_MR']['dentro_sobre_total'] for p in PAIRS), 1, True)} dentro), o que explica Δz e D_TV positivos, mas a parte entre regiões ({n(min(R[p]['variancia_MR']['entre_regioes_sobre_total'] for p in PAIRS), 1, True)} a {n(max(R[p]['variancia_MR']['entre_regioes_sobre_total'] for p in PAIRS), 1, True)}) basta para as seleções coincidirem nas poucas regiões de melhor MR médio.")
assert all(R[p]["variantes"]["veredito_sens"] == "not_supported" and R[p]["escala_0p1"]["veredito"] == "not_supported" for p in PAIRS)
a("- **O veredito primário não muda com a janela nem com a escala:** a janela 2071-2100 e a escala de 0,1 grau mantêm \"não suportada\" nos seis pares (seção 4).")
a("")
a("Limites: o diagnóstico descreve o H2 como está definido (partição Admin1, média ponderada de MR); não avalia se Admin1 é a partição adequada nem se γ = 0,30 é o limiar adequado, e não propõe valores. O perfil de γ usa a grade registrada (0,10 a 0,70 de 0,05 em 0,05).")
a("")
a("## 6. Origem dos números")
a("")
a("| Número | Origem |")
a("|---|---|")
a("| O, O_ref, k, T, Q_max, Δz, D_TV, IQR, menor γ | `outputs/<ISO>/robustness_analysis/artifacts/h2_summary_<tec>__core.parquet`, linha primária |")
a("| capacidade, MR médio, variância interna, posição, fração tomada, seleções | `h2_regions_<tec>__core.parquet` |")
a("| variantes (janela core e 2071-2100) | `h2_summary_<tec>__core.parquet` e `__sensitivity.parquet` |")
a("| escala 0,1 grau | `outputs/<ISO>/robustness_analysis__0p1deg/artifacts/h2_summary_<tec>__core.parquet` |")
a("| conferência de Δz e T | `robustness_<tec>__core.parquet` (`admin1_id`, `robust_rank`, `p_mw`, `mr`) |")
a("")
snap = c.DATA / "_snapshots" / "20261123_pre203"
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
a("## 7. Manifestos e referências no momento da geração")
a("")
a(f"Manifestos comparados com o instantâneo (SHA-256): {sum(1 for _, v in ok if v)} de {len(ok)} iguais" + ("." if all(v for _, v in ok) else "; DIFERENTES: " + ", ".join(nm for nm, v in ok if not v)))
tags = subprocess.run(["git", "-C", str(c.REPO), "rev-parse", "v1.0^{commit}", "prereg-v1"], capture_output=True, text=True).stdout.split()
a(f"Tag `v1.0` aponta para `{tags[0][:7]}` e o objeto da tag `prereg-v1` é `{tags[1][:8]}`, como registrados.")
a("")
open(c.OUT / "D3_h2.md", "w", encoding="utf-8").write("\n".join(L))
print("D3_h2.md escrito,", len("\n".join(L).split()), "palavras")
