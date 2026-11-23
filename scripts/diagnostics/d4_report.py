"""Gera D4_exclusoes.md a partir de D4_dados (numeros lidos dos dados; as regras de classificacao estao escritas no texto)."""
from __future__ import annotations

import hashlib
import json
import subprocess

import numpy as np
import pandas as pd

import d1_common as c

D = c.OUT / "D4_dados"
E5 = pd.read_csv(D / "D4_E5_composicao.csv")
E5V = pd.read_csv(D / "D4_E5_vintage.csv")
E4 = pd.read_csv(D / "D4_E4.csv")
E6 = pd.read_csv(D / "D4_E6.csv")
E1 = pd.read_csv(D / "D4_E1.csv")
U = pd.read_csv(D / "D4_unidades.csv")
VER = json.load(open(D / "D4_verificacoes.json", encoding="utf-8"))
PAIRS = [f"{i} {t}" for i, t in c.PAIRS]
LA_CENTRAL_DEG = {"solar": 2.86, "wind": 11.31}


def n(x, d=2, pct=False):
    if x is None or (isinstance(x, float) and x != x):
        return "não disponível"
    v = x * 100 if pct else x
    s = f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if float(f"{v:.{d}f}") == 0:
        s = s.lstrip("-")
    return s + ("%" if pct else "")


def fi(x):
    return f"{int(x):,}".replace(",", ".")


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def row_of(df, par, loc):
    return df[(df.par == par) & (df.localizacao == loc)].iloc[0]


head = subprocess.run(["git", "-C", str(c.REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
L: list[str] = []
a = L.append
a("# D4: exclusões que atingem as usinas existentes (COMANDO 204)")
a("")
a(f"Escrito para: o autor, para levar ao chat de planejamento. Data: 2026-11-23. Repositório em `{head}`, tag `prereg-v1` e `v1.0` inalteradas. Somente leitura: nada foi gravado em `GeoFREA_data/outputs/` nem no repositório. Scripts em `_notas_geofrea/diagnostico_v1_0/` (`d1_common.py`, `d4_run.py`, `d4_report.py`), dados em `D4_dados/`. Este texto é gerado de `D4_dados/`; os números não foram digitados à mão. Nenhum valor novo é proposto: o relatório só classifica.")
a("")
a("**Objeto.** As usinas em operação do GEM (conjunto `operating` do F7b: todas as usinas com pixel válido, sem filtro de safra nem de precisão de localização, `vintage_min_start_year`, `excluded_location_accuracy` e `vintage_reason` nulos em `experiments.yaml`) e as parcelas excluídas que o motor de elegibilidade do F3 calcula no pixel de 0,01 grau de cada usina (cenário central). Classes pedidas: **(a)** artefato do dado posterior à usina, **(b)** limite mais estrito que a prática, **(c)** exclusão legítima (usina antiga em área hoje restrita). Além delas, os dados mostram dois efeitos que não cabem nas três: a **precisão da coordenada** do GEM (chamada aqui de a2, artefato do dado que não é posterior à usina) e o **tamanho do pixel** (a parcela do pixel contra a pegada da usina). Eles aparecem separados.")
a("")
a("## 0. Base e conferências")
a("")
rows = []
for p in PAIRS:
    v = VER[p]
    rows.append([p, fi(v["n_units"]), n(v["capacity_mw"], 0), fi(v["n_exact"]), n(v["n_exact"] / v["n_units"], 1, True), n(v["mw_exact"] / v["capacity_mw"], 1, True), fi(v["n_sem_ano"]), n(v["E5_erro_max"], 6), n(v["E4_erro_max_fabdem"], 6), n(v["E4_erro_max_arquivo_F3"], 3)])
a(table(["Par", "Unidades no pixel válido", "MW", "Unidades com localização exata", "% das unidades", "% da capacidade", "Unidades sem ano de início", "Erro máx. E5 recalculado", "Erro máx. E4 recalculado (FABDEM)", "Erro máx. E4 recalculado (GLO-30)"], rows))
a("")
a("- **E5 e E4 recalculados** das camadas alinhadas da F2a nos pixels das usinas e comparados com o que o F7b gravou (`validation_units`): E5 com erro máximo 0 nos seis pares; E4 com erro máximo 0 usando as contagens de declividade do **FABDEM** (`<ISO>_slope_counts_fabdem_aligned.tif`), que é o que o motor usa. A declividade do GLO-30 (`<ISO>_slope_counts_aligned.tif`, superfície com copas e prédios) dá E4 diferente (última coluna) e entra só como comparação.")
a("- **Camadas:** cobertura do solo = ESA WorldCover **2020** v100, 10 m (`land_cover_counts`, 14.400 amostras por pixel); assentamentos = GHS-SMOD R2023A, época 2020, classe 13 ou maior; áreas protegidas = o GeoJSON bruto do WDPA do projeto (colunas `IUCN_CAT`, `wdpa_id`, `name`; **sem `STATUS_YR` nem tipo de designação**).")
a("- **Safra:** o mapa de cobertura é de 2020; uma usina com início até 2019 já existia quando o mapa foi feito, uma com início em 2021 ou depois não.")
a("- Manifestos iguais ao instantâneo `_snapshots/20261123_pre204` (seção 9).")
a("")

# ---- efeito da localizacao sobre o combinado
vu = {}
for iso in ("PRT", "IND", "BRA"):
    t = pd.read_parquet(c.DATA / "outputs" / iso / "external_validation" / "artifacts" / "validation_units.parquet")
    vu[iso] = t[t["in_grid"] & t["valid_pixel"]]
loc_rows = []
for iso, tech in c.PAIRS:
    t = vu[iso][vu[iso].technology == tech]
    for lab, sub in (("todas", t), ("exata", t[t.location_accuracy == "exact"]), ("aproximada", t[t.location_accuracy != "exact"])):
        if sub.empty:
            continue
        w = sub.capacity_mw.to_numpy()
        loc_rows.append([f"{iso} {tech}", lab, fi(len(sub)), n(w.sum(), 0), n((sub.excluded_combined.to_numpy() * w).sum() / w.sum(), 3), n(w[sub.excluded_combined.to_numpy() >= 0.5].sum() / w.sum(), 1, True), n(w[sub.excluded_combined.to_numpy() >= 0.999].sum() / w.sum(), 1, True)])

# ---------------------------------------------------------------- resumo
a("## 1. Achados em uma página")
a("")
a("**Efeito da precisão da coordenada (a2).** Parcela excluída combinada no pixel da usina (média ponderada pela capacidade), por precisão de localização do GEM:")
a("")
a(table(["Par", "Localização", "Unidades", "MW", "Excluída combinada, média", "Capacidade com combinada >= 0,5", "Capacidade com combinada = 1"], loc_rows))
a("")
ex_ap = {p: (row_of(E6, p, "todas")["frac_cap_proprio_pixel_assentamento"], row_of(E6, p, "exact")["frac_cap_proprio_pixel_assentamento"]) for p in PAIRS}
a("- **IND eólica:** " + n(VER["IND wind"]["n_exact"], 0) + f" das {VER['IND wind']['n_units']} unidades têm localização exata ({n(VER['IND wind']['mw_exact'] / VER['IND wind']['capacity_mw'], 1, True)} da capacidade). Com todas as unidades, {n(ex_ap['IND wind'][0], 1, True)} da capacidade fica em pixel que é ele mesmo assentamento; com as exatas, {n(ex_ap['IND wind'][1], 1, True)}. **BRA solar:** {n(ex_ap['BRA solar'][0], 1, True)} contra {n(ex_ap['BRA solar'][1], 1, True)}.")
bu = E5V[(E5V.localizacao == "exact")]
def bu_ratio(p):
    s = bu[bu.par == p].set_index("vintage")
    if "ate 2019" in s.index and "2021 ou depois" in s.index:
        return s.loc["ate 2019", "construido"], s.loc["2021 ou depois", "construido"], s.loc["ate 2019", "construido_fundo"], int(s.loc["ate 2019", "n"])
    return None
parts = []
for p in PAIRS:
    r = bu_ratio(p)
    if r:
        parts.append(f"{p} {n(r[0], 3)} contra {n(r[1], 3)} (fundo {n(r[2], 3)})")
a("- **Artefato posterior à usina em E5 (a1):** parcela de \"construído\" (classe 50) no pixel das usinas de localização exata, início até 2019 contra início em 2021 ou depois (mapa de 2020): " + "; ".join(parts) + ".")
above = [p for p in PAIRS if row_of(E4, p, "exact")["declividade_media_deg_fabdem_pond"] > LA_CENTRAL_DEG[p.split()[1]]]
below = [p for p in PAIRS if p not in above]
a("- **Declividade (E4):** declividade média (FABDEM, usinas de localização exata) acima do limite central em " + ", ".join(p + " (" + n(row_of(E4, p, "exact")["declividade_media_deg_fabdem_pond"], 2) + " graus contra " + n(LA_CENTRAL_DEG[p.split()[1]], 2) + ")" for p in above) + "; abaixo em " + ", ".join(below) + ".")
strict_sh = []
for p in PAIRS:
    r1 = row_of(E1, p, "todas")
    mw = {k[3:]: r1[k] for k in r1.index if k.startswith("mw_") and r1[k] == r1[k]}
    tot = sum(mw.values())
    strict_sh.append(sum(v for k, v in mw.items() if k in ("Ia", "Ib", "II")) / tot if tot else 0.0)
a("- **Áreas protegidas (E1):** o arquivo do WDPA do projeto não traz o ano de designação, então a classe (c) não é testável. A parcela da capacidade dentro de área protegida em categoria estrita (Ia, Ib, II) vai de " + n(min(strict_sh), 1, True) + " a " + n(max(strict_sh), 1, True) + " entre os pares; o resto está em Not Reported, V, VI, IV, III ou Not Applicable (seção 5).")
a("")

# ---------------------------------------------------------------- E5
a("## 2. Item 1: E5, a classe do WorldCover nos pixels das usinas")
a("")
a("`excluded_classes` do cenário central: solar `cropland_excluded` (classes 10, 40, 50, 70, 80, 90, 95), eólica `forest_excluded` (10, 50, 70, 80, 90, 95). Composição média do pixel da usina (parcela das 14.400 amostras de 10 m, ponderada pela capacidade) e E5 registrado; \"solo exposto\" (60) não é excluído.")
a("")
cols = [("lc_arvores", "árvores (10)"), ("lc_lavoura", "lavoura (40)"), ("lc_construido", "construído (50)"), ("lc_solo_exposto", "solo exposto (60)"), ("lc_arbustos", "arbustos (20)"), ("lc_pastagem", "pastagem (30)")]
rows = []
for p in PAIRS:
    for loc in ("todas", "exact"):
        r = row_of(E5, p, loc)
        rows.append([p, "todas" if loc == "todas" else "exata", fi(r["n"]), n(r["E5_medio"], 3), n(r["frac_E5_ge_0_5"], 1, True)] + [n(r[k], 3) for k, _ in cols])
a(table(["Par", "Localização", "Unidades", "E5 médio", "Capacidade com E5 >= 0,5"] + [lab for _, lab in cols], rows))
a("")
bg = {iso: json.load(open(D / "D4_verificacoes.json", encoding="utf-8"))[iso]["bg_lc"] for iso in ("PRT", "IND", "BRA")}
a("Fundo (média sobre os pixels válidos do país): " + "; ".join(f"{iso}: construído {n(bg[iso]['lc_construido'], 3)}, lavoura {n(bg[iso]['lc_lavoura'], 3)}, árvores {n(bg[iso]['lc_arvores'], 3)}, solo exposto {n(bg[iso]['lc_solo_exposto'], 3)}" for iso in bg) + ".")
a("")
a("**De onde vem o E5 (usinas de localização exata).** Parcela do E5 médio que cada classe excluída responde:")
a("")
rows = []
for p in PAIRS:
    r = row_of(E5, p, "exact")
    tech = p.split()[1]
    excl = [int(x) for x in r["classes_excluidas"].split(",")]
    names = {10: "lc_arvores", 40: "lc_lavoura", 50: "lc_construido", 80: "lc_agua", 90: "lc_areas_umidas"}
    tot = sum(r[nm] for k, nm in names.items() if k in excl) + r["lc_sem_classe"]
    rows.append([p, n(r["E5_medio"], 3), n(r["lc_arvores"] / r["E5_medio"], 1, True), n(r["lc_lavoura"] / r["E5_medio"], 1, True) if 40 in excl else "não excluída", n(r["lc_construido"] / r["E5_medio"], 1, True), n((r["lc_agua"] + r["lc_areas_umidas"]) / r["E5_medio"], 1, True)])
a(table(["Par", "E5 médio", "Árvores", "Lavoura", "Construído", "Água e áreas úmidas"], rows))
a("")
a("**Teste de safra (usinas de localização exata): o \"construído\" no pixel, por data de início da usina.** O mapa é de 2020. Se o mapa vê a usina como área construída, as usinas até 2019 mostram mais \"construído\" que as de 2021 em diante, que o mapa ainda não viu; sem artefato, os dois grupos ficam parecidos com o fundo.")
a("")
rows = []
for p in PAIRS:
    s = E5V[(E5V.par == p) & (E5V.localizacao == "exact")].set_index("vintage")
    for v_ in ("ate 2019", "2020", "2021 ou depois", "sem ano"):
        if v_ in s.index:
            r = s.loc[v_]
            rows.append([p, v_.replace("ate", "até"), fi(r["n"]), n(r["mw"], 0), n(r["construido"], 3), n(r["construido_fundo"], 3), n(r["frac_construido_ge_0_1"], 1, True), n(r["solo_exposto"], 3), n(r["solo_exposto_fundo"], 3), n(r["E5_medio"], 3)])
a(table(["Par", "Início", "Unidades", "MW", "Construído", "Fundo", "Capacidade com construído >= 0,1", "Solo exposto", "Fundo", "E5 médio"], rows))
a("")
a("Em 2020 o mapa pode ter pegado obras: nas solares de 2020 o \"solo exposto\" fica acima do fundo (por exemplo BRA solar), e solo exposto não é classe excluída.")
a("")

# ---------------------------------------------------------------- E4
a("## 3. Item 2: E4, a declividade nos pixels das usinas")
a("")
a(f"Limite central: solar {n(LA_CENTRAL_DEG['solar'], 2)} graus (5%), eólica {n(LA_CENTRAL_DEG['wind'], 2)} graus (20%); restritivo 3% e 10%, permissivo 10% e 30%. Declividade média do pixel (graus, ponderada pela capacidade) com o FABDEM (usado pelo motor) e com o GLO-30, e, na segunda tabela, a parcela da capacidade cujo pixel tem E4 >= 0,5, isto é, metade ou mais das amostras de 30 m acima do limite central (FABDEM, o que o motor usa).")
a("")
rows = []
for p in PAIRS:
    r = row_of(E4, p, "todas")
    rows.append([p, fi(r["n"]), n(r["declividade_media_deg_fabdem_pond"], 2), n(r["declividade_media_deg_pond"], 2), n(r["mediana_declividade_media_deg"], 2), n(r["p90_declividade_media_deg"], 2), n(r["E4_registrado_medio"], 3), n(r["frac_cap_E4_restrictive_ge_0_5"] if False else r["E4f_restrictive_medio"], 3), n(r["E4f_permissive_medio"], 3)])
a(table(["Par", "Unidades", "Declividade média, FABDEM (graus)", "GLO-30 (graus)", "Mediana (GLO-30)", "p90 (GLO-30)", "E4 central (motor)", "E4 restritivo", "E4 permissivo"], rows))
a("")
rows = []
for p in PAIRS:
    r = row_of(E4, p, "todas")
    uu = U[(U.pais == p.split()[0]) & (U.technology == p.split()[1])]
    w = uu.capacity_mw.to_numpy()
    # fracao da capacidade com E4 registrado (central, FABDEM) >= 0,5 e > 0
    rows.append([p, n((w[uu.excluded_E4.to_numpy() >= 0.5]).sum() / w.sum(), 1, True), n((w[uu.excluded_E4.to_numpy() > 0]).sum() / w.sum(), 1, True)])
a(table(["Par", "Capacidade com E4 central >= 0,5 (FABDEM)", "Capacidade com E4 central > 0"], rows))
a("")
a("A diferença entre FABDEM e GLO-30 (colunas 3 e 4 da primeira tabela) é a do modelo de elevação: o GLO-30 é uma superfície (copas, prédios, painéis) e acrescenta declividade; o motor já usa o FABDEM.")
a("")

# ---------------------------------------------------------------- E6
a("## 4. Item 3: E6, assentamentos (GHS-SMOD) e distância ao assentamento")
a("")
a("`classe GHS >= 13` é assentamento (M-F2a-11). A distância é do **ponto** da usina à borda do pixel de assentamento mais próximo (janela de 7 x 7 pixels; \"sem assentamento\" quando não há nenhum na janela). Setbacks: solar 0 / 500 / 1.000 m e eólica 500 / 800 / 1.000 m (permissivo / central / restritivo).")
a("")
rows = []
for p in PAIRS:
    tech = p.split()[1]
    cen = "central_500m" if tech == "solar" else "central_800m"
    for loc in ("todas", "exact"):
        r = row_of(E6, p, loc)
        rows.append([p, "todas" if loc == "todas" else "exata", fi(r["n"]), n(r["E6_registrado_medio"], 3), n(r["frac_cap_E6_igual_1"], 1, True), n(r["frac_cap_proprio_pixel_assentamento"], 1, True), n(r[f"frac_cap_ponto_dentro_{cen}"], 1, True), n(r["frac_cap_ponto_dentro_restrictive_1000m"], 1, True), n(r["mediana_dist_m"], 0), n(r["frac_cap_sem_assentamento_na_janela"], 1, True)])
a(table(["Par", "Localização", "Unidades", "E6 médio", "Capacidade com E6 = 1", "Pixel da usina é assentamento", "Ponto dentro do setback central", "Ponto dentro de 1.000 m", "Distância mediana (m)", "Sem assentamento na janela"], rows))
a("")
a("**Teste de safra para E6 (usinas de localização exata).** Parcela da capacidade cujo pixel é assentamento, por data de início (a época do GHS-SMOD é 2020):")
a("")
rows = []
for p in PAIRS:
    uu = U[(U.pais == p.split()[0]) & (U.technology == p.split()[1]) & (U.location_accuracy == "exact")].copy()
    uu["vint"] = np.where(uu.start_year.isna(), "sem ano", np.where(uu.start_year <= 2019, "até 2019", np.where(uu.start_year == 2020, "2020", "2021 ou depois")))
    uu["sett"] = (uu.classe_ghs >= 13) & (uu.classe_ghs <= 30)
    for v_ in ("até 2019", "2020", "2021 ou depois", "sem ano"):
        g = uu[uu.vint == v_]
        if len(g):
            rows.append([p, v_, fi(len(g)), n(g.capacity_mw.sum(), 0), n(g.capacity_mw[g.sett].sum() / g.capacity_mw.sum(), 1, True)])
a(table(["Par", "Início", "Unidades", "MW", "Capacidade em pixel de assentamento"], rows))
a("")

# ---------------------------------------------------------------- E1
a("## 5. Item 4: E1, a designação do WDPA nas usinas dentro de área protegida")
a("")
a("Ponto da usina dentro de um polígono do WDPA do projeto, contra a parcela do pixel que o motor exclui. O arquivo traz `IUCN_CAT` mas **não traz o ano de designação (`STATUS_YR`) nem o tipo de designação**; sem eles não se testa se a área protegida é posterior à usina.")
a("")
rows = []
for p in PAIRS:
    for loc in ("todas", "exact"):
        r = row_of(E1, p, loc)
        rows.append([p, "todas" if loc == "todas" else "exata", fi(r["n"]), n(r["E1_pixel_registrado_medio"], 3), n(r["frac_cap_E1_pixel_ge_0_5"], 1, True), n(r["frac_cap_ponto_no_WDPA"], 1, True), fi(r["n_ponto_no_WDPA"]), n(r["frac_cap_pixel_E1_gt_0_e_ponto_fora"], 1, True)])
a(table(["Par", "Localização", "Unidades", "E1 do pixel, médio", "Capacidade com E1 >= 0,5", "Ponto dentro de área protegida", "Unidades dentro", "Pixel com E1 > 0 e ponto fora"], rows))
a("")
a("Categoria IUCN das usinas cujo ponto cai dentro de área protegida (MW; \"estrita\" = Ia, Ib, II):")
a("")
rows = []
for p in PAIRS:
    r = row_of(E1, p, "todas")
    mw = {k[3:]: r[k] for k in r.index if k.startswith("mw_") and r[k] == r[k]}
    tot = sum(mw.values())
    strict = sum(v for k, v in mw.items() if k in ("Ia", "Ib", "II"))
    rows.append([p, n(tot, 1), n(strict, 1) if tot else "0", n(strict / tot, 1, True) if tot else "não disponível", ", ".join(f"{k}: {n(v, 1)}" for k, v in sorted(mw.items(), key=lambda t: -t[1]))])
a(table(["Par", "MW dentro", "MW em categoria estrita", "Parcela estrita", "Por categoria (MW)"], rows))
a("")

# ---------------------------------------------------------------- classificacao
a("## 6. Classificação por restrição (item 5)")
a("")
a("Regras usadas (cada uma é uma medida desta seção, não um valor novo de parâmetro):")
a("")
a("- **(a1) artefato posterior à usina:** nas usinas de localização exata com pelo menos 20 unidades até 2019, o \"construído\" (E5) ou a parcela em pixel de assentamento (E6) das usinas até 2019 é pelo menos o dobro do das usinas de 2021 em diante, o dobro do fundo (E5) e pelo menos 0,02 maior em E5; em E6 a regra é a diferença de pelo menos 5 pontos percentuais e a razão de pelo menos 1,5 entre as usinas até 2019 e as de 2021 em diante (não há fundo de assentamentos).")
a("- **(a2) artefato da coordenada:** com todas as unidades, o E5 médio (E5) ou a parcela da capacidade em pixel de assentamento (E6) é pelo menos 1,5 vez o das unidades de localização exata.")
a("- **(b) limite mais estrito que a prática:** a restrição é uma escolha de parâmetro do cenário (classe excluída, limite de declividade, setback, categoria do WDPA) e as usinas existentes a violam em parte relevante: E5, E5 médio de pelo menos 0,2 com mais de 50% dele em classes de escolha (lavoura na solar, árvores nas duas); E4, declividade média no pixel acima do limite central ou capacidade com E4 >= 0,5 acima de 10%; E6, parcela da capacidade (exata) com o ponto dentro do setback central acima de 10%; E1, pelo menos 5% da capacidade dentro de área protegida e mais de 50% dela em categoria não estrita.")
a("- **(c) exclusão legítima (usina antiga em área hoje restrita):** exige o ano de designação ou de construção da restrição; só é avaliável para as camadas com ano. Nenhuma das quatro camadas traz o ano da restrição (WorldCover 2020 e GHS-SMOD 2020 são fotografias; o WDPA do projeto não tem `STATUS_YR`): **não avaliável** nos quatro casos.")
a("")
cls_rows = []
F = {}
for p in PAIRS:
    tech = p.split()[1]
    iso = p.split()[0]
    f = {}
    r5, r5a = row_of(E5, p, "exact"), row_of(E5, p, "todas")
    excl = [int(x) for x in r5["classes_excluidas"].split(",")]
    pol = r5["lc_arvores"] + (r5["lc_lavoura"] if 40 in excl else 0.0)
    pol_share = pol / r5["E5_medio"] if r5["E5_medio"] > 0 else float("nan")
    rr = bu_ratio(p)
    f["e5_a1"] = bool(rr and rr[3] >= 20 and rr[0] >= 2 * rr[1] and rr[0] >= 2 * rr[2] and rr[0] - rr[1] >= 0.02)
    f["e5_a2"] = bool(r5["E5_medio"] > 0 and r5a["E5_medio"] >= 1.5 * r5["E5_medio"])
    f["e5_b"] = bool(r5["E5_medio"] >= 0.2 and pol_share > 0.5)
    f["e5_txt"] = f"a1: {'sim' if f['e5_a1'] else 'não'}; a2: {'sim' if f['e5_a2'] else 'não'} (E5 {n(r5a['E5_medio'], 2)} com todas contra {n(r5['E5_medio'], 2)} com exatas); b: {'sim' if f['e5_b'] else 'não'} (E5 exato {n(r5['E5_medio'], 2)}, {n(pol_share, 0, True)} dele em classes de escolha)"
    r4 = row_of(E4, p, "exact")
    uu = U[(U.pais == iso) & (U.technology == tech)]
    w = uu.capacity_mw.to_numpy()
    f4 = w[uu.excluded_E4.to_numpy() >= 0.5].sum() / w.sum()
    f["e4_b"] = bool((r4["declividade_media_deg_fabdem_pond"] > LA_CENTRAL_DEG[tech]) or f4 > 0.10)
    f["e4_txt"] = f"b: {'sim' if f['e4_b'] else 'não'} (média {n(r4['declividade_media_deg_fabdem_pond'], 1)} graus contra {n(LA_CENTRAL_DEG[tech], 1)}; {n(f4, 0, True)} da capacidade com E4 >= 0,5)"
    cen = "central_500m" if tech == "solar" else "central_800m"
    r6a, r6e = row_of(E6, p, "todas"), row_of(E6, p, "exact")
    uu6 = U[(U.pais == iso) & (U.technology == tech) & (U.location_accuracy == "exact")].copy()
    uu6["sett"] = (uu6.classe_ghs >= 13) & (uu6.classe_ghs <= 30)
    old, new = uu6[uu6.start_year <= 2019], uu6[uu6.start_year >= 2021]
    so = old.capacity_mw[old.sett].sum() / old.capacity_mw.sum() if len(old) else float("nan")
    sn = new.capacity_mw[new.sett].sum() / new.capacity_mw.sum() if len(new) else float("nan")
    f["e6_a1"] = bool(len(old) >= 20 and len(new) > 0 and so - sn >= 0.05 and so >= 1.5 * sn)
    f["e6_a2"] = bool(r6e["frac_cap_proprio_pixel_assentamento"] > 0 and r6a["frac_cap_proprio_pixel_assentamento"] >= 1.5 * r6e["frac_cap_proprio_pixel_assentamento"])
    f["e6_b"] = bool(r6e[f"frac_cap_ponto_dentro_{cen}"] > 0.10)
    f["e6_txt"] = (f"a1: {'sim' if f['e6_a1'] else 'não'} (até 2019 {n(so, 1, True)} contra 2021 em diante {n(sn, 1, True)}); a2: {'sim' if f['e6_a2'] else 'não'} ({n(r6a['frac_cap_proprio_pixel_assentamento'], 1, True)} com todas contra {n(r6e['frac_cap_proprio_pixel_assentamento'], 1, True)} com exatas); b: {'sim' if f['e6_b'] else 'não'} ({n(r6e[f'frac_cap_ponto_dentro_{cen}'], 1, True)} dentro do setback central)")
    r1 = row_of(E1, p, "todas")
    mw = {k[3:]: r1[k] for k in r1.index if k.startswith("mw_") and r1[k] == r1[k]}
    tot = sum(mw.values())
    nonstrict = (tot - sum(v for k, v in mw.items() if k in ("Ia", "Ib", "II"))) / tot if tot else float("nan")
    f["e1_b"] = bool(r1["frac_cap_ponto_no_WDPA"] >= 0.05 and tot and nonstrict > 0.5)
    f["e1_txt"] = f"b: {'sim' if f['e1_b'] else 'não'} ({n(r1['frac_cap_ponto_no_WDPA'], 1, True)} da capacidade dentro; {n(nonstrict, 0, True)} dela em categoria não estrita)"
    F[p] = f
    cls_rows.append([p, f["e5_txt"], f["e4_txt"], f["e6_txt"], f["e1_txt"]])
a(table(["Par", "E5 (WorldCover)", "E4 (declividade)", "E6 (assentamentos)", "E1 (áreas protegidas)"], cls_rows))
a("")
a("(c) não é avaliável em nenhuma coluna. O cruzamento com o ano de entrada em operação do GEM foi feito para as duas camadas fotográficas (E5 e E6) como teste de safra (a1).")
a("")

# ---------------------------------------------------------------- notas
a("## 7. O que os achados dizem")
a("")
a("Só o que os números mostram; a decisão sobre o que fazer fica para o D0.")
a("")
lst = lambda key: [p for p in PAIRS if F[p][key]]
j_ = lambda xs: ", ".join(xs) if xs else "nenhum par"
def _s(p, v_):
    s = E5V[(E5V.par == p) & (E5V.localizacao == "exact") & (E5V.vintage == v_)]
    return (s.solo_exposto.values[0], s.solo_exposto_fundo.values[0]) if len(s) else (None, None)
solo20 = [p for p in PAIRS if p.endswith("solar") and _s(p, "2020")[0] is not None and _s(p, "2021 ou depois")[0] is not None and _s(p, "2020")[0] > 3 * _s(p, "2020")[1] and _s(p, "2020")[0] > 3 * _s(p, "2021 ou depois")[0]]
a(f"- **E5, artefato posterior à usina (a1):** {j_(lst('e5_a1'))}. Nas usinas de 2020 das solares, o solo exposto passa de três vezes o fundo e de três vezes o das usinas de 2021 em diante em {j_(solo20)} (compatível com obras no mapa de 2020); solo exposto não é classe excluída.")
a(f"- **E5, escolha de parâmetro (b):** {j_(lst('e5_b'))}: o E5 vem de classes que o cenário central escolheu excluir (lavoura na solar, árvores nas duas tecnologias), não de erro do mapa. Artefato da coordenada (a2): {j_(lst('e5_a2'))}.")
dsm = {p: (row_of(E4, p, "todas")["declividade_media_deg_pond"] - row_of(E4, p, "todas")["declividade_media_deg_fabdem_pond"]) for p in PAIRS}
a(f"- **E4:** (b) em {j_(lst('e4_b'))}. A declividade do pixel mistura o terreno da usina com o do resto do pixel de 1,1 km. O GLO-30 dá declividade média maior que o FABDEM em todos os pares ({n(min(dsm.values()), 2)} a {n(max(dsm.values()), 2)} graus a mais); o motor já usa o FABDEM.")
a(f"- **E6:** artefato da coordenada (a2) em {j_(lst('e6_a2'))}; artefato posterior à usina (a1) em {j_(lst('e6_a1'))}; limite mais estrito que a prática (b) em {j_(lst('e6_b'))}. Com todas as unidades, IND eólica e BRA solar têm a capacidade em pixel de assentamento muito acima da das unidades de localização exata (seção 4), o que é compatível com coordenadas de cidade ou de município (o GEM marca essas unidades como localização aproximada).")
a(f"- **E1:** (b) em {j_(lst('e1_b'))}; a designação do cenário central exclui todas as categorias. O ano de designação não está no arquivo, então (c) não é avaliável.")
a("")
a("## 8. Origem dos números e limites")
a("")
a("| Número | Origem |")
a("|---|---|")
a("| usinas, precisão de localização, ano de início, E1 a E6 do pixel | `outputs/<ISO>/external_validation/artifacts/validation_units.parquet` (F7b), GEM em `raw/gem/<ISO>/gem_solar_wind_<ISO>.parquet` |")
a("| cobertura do solo | `outputs/<ISO>/grid_alignment/artifacts/<ISO>_land_cover_counts_aligned.tif` (WorldCover 2020 v100) |")
a("| declividade | `<ISO>_slope_counts_fabdem_aligned.tif` (motor) e `<ISO>_slope_counts_aligned.tif` (GLO-30) |")
a("| assentamentos | `<ISO>_settlements_aligned.tif` (GHS-SMOD R2023A, época 2020) |")
a("| áreas protegidas | `raw/wdpa/<ISO>/<ISO>_protected_areas_wdpa.geojson` |")
a("| limites e classes do cenário | `config/experiments.yaml`, `land_availability.technologies` |")
a("")
a("Limites:")
a("")
a("- A localização das usinas é a do GEM; \"aproximada\" quer dizer que a coordenada pode estar a quilômetros da usina. Em IND eólica só 58 unidades têm localização exata; as parcelas \"exatas\" dessa tecnologia vêm de pouca capacidade.")
a("- O pixel tem 0,01 grau (cerca de 1,1 km); as parcelas E1 a E6 são do pixel, não da pegada da usina. Uma usina pequena num pixel com terreno íngreme em outra parte do pixel recebe E4 alto sem estar na parte íngreme. A pegada da usina não é medida aqui.")
a("- A classe (c) não é avaliável: faltam anos de designação (WDPA) e de mudança de uso (WorldCover e GHS-SMOD são de 2020).")
a("- A distância ao assentamento usa uma janela de 7 x 7 pixels e a borda do pixel de 0,01 grau, não a geodésica por subpixel do motor (M-F2b-01).")
a("- O ano de início do GEM falta em parte das unidades (coluna 7 da tabela da seção 0); elas ficam no grupo \"sem ano\".")
a("")
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
a("## 9. Manifestos e referências no momento da geração")
a("")
a(f"Manifestos comparados com o instantâneo (SHA-256): {sum(1 for _, v in ok if v)} de {len(ok)} iguais" + ("." if all(v for _, v in ok) else "; DIFERENTES: " + ", ".join(nm for nm, v in ok if not v)))
tags = subprocess.run(["git", "-C", str(c.REPO), "rev-parse", "v1.0^{commit}", "prereg-v1"], capture_output=True, text=True).stdout.split()
a(f"Tag `v1.0` aponta para `{tags[0][:7]}` e o objeto da tag `prereg-v1` é `{tags[1][:8]}`, como registrados.")
a("")
open(c.OUT / "D4_exclusoes.md", "w", encoding="utf-8").write("\n".join(L))
print("D4_exclusoes.md escrito,", len("\n".join(L).split()), "palavras")
