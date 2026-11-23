# D2: o que move (ou não) o ranking (COMANDO 202)

Escrito para: o autor, para levar ao chat de planejamento. Data: 2026-11-23. Repositório em `2c94752`, tag `prereg-v1` e `v1.0` inalteradas. Somente leitura: nada foi gravado em `GeoFREA_data/outputs/` nem no repositório. Scripts em `_notas_geofrea/diagnostico_v1_0/` (`d1_common.py`, `d2_run.py`, `d2_report.py`) e dados em `D2_dados/`. Este texto é gerado de `D2_dados/` por `d2_report.py`; os números não foram digitados à mão. As classificações do item 1 vêm da leitura do kernel (`lcoe_modeling/kernel.py`) e são conferidas pelas medidas ao lado.

## 0. Base e conferências

- **Janela e membros:** janela core (2041-2070), cenário central de solo. Eixo clima: o LCOE nominal de cada um dos 18 membros do core (6 GCMs x 3 SSPs), com os parâmetros nominais (`nominal_lcoe_by_member_<tec>__core`). Eixo parâmetros: o LCOE do membro de referência m0 sob os sorteios 1 a 200 da matriz de desenho gravada (semente 42, tamanho 4000), recalculado com o kernel do F6 importado (`lcoe_block`); nenhuma fase rodou.
- **Amostra:** PRT inteiro (3.414 e 3.332 células). IND e BRA: 20.000 células sorteadas sem reposição entre as células da classe `ranked`, com `numpy.random.default_rng(202)`, ordenadas por `cell_id`; a semente 202 é a do número deste comando. O top-k é 10% do tamanho do conjunto avaliado (`top_k_percent` do par), logo k = 2.000 nas amostras. Os postos dos itens 2 a 4 são postos dentro desse conjunto (20.000 células), não dentro das células do país inteiro.
- **Itens 5, 6 e 7** usam todas as células ranqueadas (sem amostra).
- **Sorteios reproduzidos:** em PRT eólica, o kernel com os 4000 sorteios gravados dá os quantis p10, p50 e p90 do `lcoe_summary` do F6 com erro máximo 0,0 (asserção no script).
- **LCOE nominal reproduzido:** o LCOE de m0 recalculado pelo kernel é igual ao da tabela de robustez em todas as células das amostras (asserção, tolerância 1e-9), e o da tabela por membro também.
- **F7 reproduzido (item 7):** o V_k, o D_clim, o D_tec, o d do H3 e o k que recalculei com as definições de M-F7-05 a M-F7-07 são iguais aos que o F7 gravou em `h1_summary`, `h4_country` e `h3_summary` nos seis pares:

| Par | k F7 | k calc. | V_k F7 | V_k calc. | D_clim F7 | D_clim calc. | D_tec F7 | D_tec calc. | d (H3) F7 | d (H3) calc. |
|---|---|---|---|---|---|---|---|---|---|---|
| PRT solar | 342 | 342 | 0,00000 | 0,00000 | 0,000000 | 0,000000 | 0,000000 | 0,000000 | 0,009224 | 0,009224 |
| PRT wind | 334 | 334 | 0,00000 | 0,00000 | 0,000000 | 0,000000 | 0,000000 | 0,000000 | 0,000000 | 0,000000 |
| IND solar | 9349 | 9349 | 0,00000 | 0,00000 | 0,001533 | 0,001533 | 0,000000 | 0,000000 | 0,000037 | 0,000037 |
| IND wind | 7554 | 7554 | 0,00000 | 0,00000 | 0,000000 | 0,000000 | 0,000000 | 0,000000 | 0,000000 | 0,000000 |
| BRA solar | 19001 | 19001 | 0,00295 | 0,00295 | 0,000000 | 0,000000 | 0,000000 | 0,000000 | 0,000281 | 0,000281 |
| BRA wind | 17119 | 17119 | 0,00000 | 0,00000 | 0,000000 | 0,000000 | 0,000000 | 0,000000 | 0,000000 | 0,000000 |

- **Manifestos:** iguais ao instantâneo `_snapshots/20261123_pre202` (ver a seção 11).

## 1. Achados em uma página

- **Variância (em log do LCOE):** a parcela entre células é de 88,8% a 98,9% no eixo clima. A interação célula x futuro, a única parte que pode trocar a ordem, é de 0,13% a 1,75% no clima e de 0,00% a 0,52% nos parâmetros.
- **Parâmetros:** nos sorteios, 3,2% a 90,8% da variância de log(LCOE) é deslocamento comum a todas as células (o capex, o O&M, a taxa e a vida movem o LCOE do país inteiro junto); as solares de IND e BRA têm a maior parcela comum (62,5% e 62,3%).
- **Ranking:** o Spearman entre o ranking nominal e o de cada futuro tem mínimo de 0,892 e a sobreposição do top-k tem mínimo de 0,664 (mediana de 0,890 a 0,998).
- **Deslocamento:** o pior posto de uma célula do top-k nominal ultrapassa o limiar 2k em PRT solar 0,88%, PRT wind 0,00%, IND solar 3,00%, IND wind 0,00%, BRA solar 2,55%, BRA wind 3,55% dos casos (clima e parâmetros juntos, pior futuro de cada célula). Com o V_k do F7 o resultado é outro, porque o V_k usa o posto do pior regret por SSP, não o pior posto entre membros (ver a seção 5).
- **MR e LCOE nominal:** Spearman de 0,930 a 0,999; o R² da regressão linear de MR sobre a distância nominal à melhor célula vai de 0,875 a 0,999.
- **Exploratório (1%, m = k/2), sem substituir nada:** V_k de PRT solar 0,000, PRT wind 0,000, IND solar 0,138, IND wind 0,015, BRA solar 0,075, BRA wind 0,001; o D_clim e o D_tec ficam acima de zero em alguns pares (ver a seção 8).

## 2. Item 1: quais parâmetros do LHS são uniformes no país e quais mudam a ordem

**Forma do kernel** (`lcoe_block`): `LCOE_i = [ P_i x U + P_i x D_sub_i x c_linha x tort_rede / P_ref + P_i x D_estrada_i x c_estrada x tort_estrada / P_ref ] / ( E_i x A_e(d_i, r, n) x perda ) + O&M variável`, com `U = 1000 x capex x (1 + o&m x A_o(r, n)) + c_baia / P_ref`. As entradas por célula são `P_i`, `E_i` (e a reescala de energia `offset_i + slope_i x parâmetro de energia`, que depende de dT do membro), `D_sub_i`, `D_estrada_i` e os limites de degradação `d_i` da zona térmica. Todos os parâmetros sorteados têm um único valor por sorteio para o país inteiro; a diferença está em como entram.

| Parâmetro sorteado | Como entra | Muda a ordem entre células? |
|---|---|---|
| `capex_usd_per_kw`, `opex_fixed_frac` | em U, igual por MW em todas as células | só pelo peso relativo da conexão e da degradação no LCOE da célula; sozinho multiplica o termo de capital de todas |
| `bay_cost_usd` | custo da baia por MW (P/P_ref), igual por MW | como o capex: não depende da célula |
| `discount_rate`, `lifetime_years` | anuidades A_o e A_e | comum; interage com a degradação da zona (solar) e com o peso da conexão |
| `degradation_weight` | pondera os limites de degradação da célula | só na solar (limites por zona térmica); na eólica os limites são iguais e não tem efeito |
| `line_cost_usd_per_km`, `tortuosity_grid` | multiplicam P_i x D_sub_i | sim: a distância à subestação varia por célula |
| `road_cost_usd_per_km`, `tortuosity_road` | multiplicam P_i x D_estrada_i | não: o custo de estrada é zero (faixa 0 a 0, `road_cost_excluded`) |
| `gamma` (solar), `eta_loss` (eólica) | reescala da energia | solar: `slope_i` depende de dT por célula, vale 0 no m0 (dT = 0) e muda por membro; eólica: fator comum |

Efeito medido, um parâmetro por vez, do nominal para o p5 e para o p95 dos sorteios, nas células da amostra (m0). Mínimo entre os dois extremos e entre os seis pares:

| Parâmetro | Spearman mínimo (par) | Sobreposição do top-k mínima (par) | Maior mudança média do LCOE | Maior desvio da mudança entre células |
|---|---|---|---|---|
| `capex_usd_per_kw` | 0,9748 (PRT solar) | 0,908 (BRA solar) | 26,9% | 1,96% |
| `opex_fixed_frac` | 0,9989 (IND solar) | 0,983 (IND solar) | 9,1% | 0,44% |
| `discount_rate` | 0,9994 (IND solar) | 0,989 (IND solar) | 19,0% | 0,32% |
| `lifetime_years` | 0,9996 (IND solar) | 0,988 (IND solar) | 7,9% | 0,24% |
| `degradation_weight` | 0,9962 (PRT solar) | 0,924 (PRT solar) | 4,1% | 0,42% |
| `line_cost_usd_per_km` | 0,9678 (PRT solar) | 0,924 (PRT solar) | 2,8% | 1,58% |
| `bay_cost_usd` | 1,0000 (PRT solar) | 0,997 (PRT solar) | 1,3% | 0,05% |
| `road_cost_usd_per_km` | 1,0000 (PRT solar) | 1,000 (PRT solar) | 0,0% | 0,00% |
| `tortuosity_grid` | 0,9997 (PRT solar) | 0,989 (BRA solar) | 0,3% | 0,26% |
| `tortuosity_road` | 1,0000 (PRT solar) | 1,000 (PRT solar) | 0,0% | 0,00% |
| `gamma` | 1,0000 (PRT solar) | 1,000 (PRT solar) | 0,0% | 0,00% |
| grupo comum (capex, O&M, taxa, vida) todos no p95 | 0,9885 (PRT solar) | 0,921 (BRA solar) | 47,8% | 2,50% |
| grupo com termo da celula (conexao, degradacao, energia) todos no p95 | 0,9734 (PRT solar) | 0,895 (PRT solar) | 5,3% | 1,61% |
| `eta_loss` | 1,0000 (PRT wind) | 1,000 (PRT wind) | 7,0% | 0,00% |

A "mudança média" é o deslocamento do LCOE de todo o país; o "desvio entre células" é o quanto essa mudança difere de uma célula para outra, e é só ele que pode trocar a ordem. Os arquivos `D2_dados/D2_1_oat_<par>.csv` trazem o detalhe por par.

## 3. Item 2: variância do LCOE entre células e entre futuros

Matriz células x futuros em log do LCOE (o log trata como comum o efeito multiplicativo; a versão em nível está em `D2_resultados.json`). A soma das três partes é 100%: **entre células** (o ranking que fica), **deslocamento comum** (todas as células sobem ou descem juntas) e **interação célula x futuro** (a parte que pode trocar a ordem).

### Eixo clima: 18 membros do core, parâmetros nominais

| Par | Entre células (log) | Comum (log) | Interação (log) | Variância total (log) | Entre células (nível) | Comum (nível) | Interação (nível) |
|---|---|---|---|---|---|---|---|
| PRT solar | 92,71% | 6,69% | 0,61% | 0,0022 | 92,64% | 6,73% | 0,63% |
| PRT wind | 98,28% | 1,59% | 0,13% | 0,0737 | 98,40% | 1,26% | 0,34% |
| IND solar | 88,85% | 9,54% | 1,61% | 0,0093 | 90,60% | 7,67% | 1,74% |
| IND wind | 98,89% | 0,53% | 0,59% | 0,3070 | 95,30% | 0,01% | 4,69% |
| BRA solar | 98,57% | 0,77% | 0,66% | 0,0148 | 99,01% | 0,50% | 0,49% |
| BRA wind | 96,72% | 1,53% | 1,75% | 0,5148 | 94,80% | 0,66% | 4,53% |

### Eixo parâmetros: 200 sorteios, clima de m0

| Par | Entre células (log) | Comum (log) | Interação (log) | Variância total (log) | Entre células (nível) | Comum (nível) | Interação (nível) |
|---|---|---|---|---|---|---|---|
| PRT solar | 8,87% | 90,79% | 0,34% | 0,0322 | 9,17% | 90,43% | 0,40% |
| PRT wind | 74,72% | 25,25% | 0,03% | 0,0977 | 78,92% | 19,20% | 1,89% |
| IND solar | 37,37% | 62,46% | 0,17% | 0,0252 | 44,21% | 55,27% | 0,51% |
| IND wind | 96,80% | 3,20% | 0,00% | 0,3061 | 98,95% | 0,07% | 0,98% |
| BRA solar | 37,21% | 62,27% | 0,52% | 0,0428 | 48,29% | 51,17% | 0,54% |
| BRA wind | 96,32% | 3,68% | 0,01% | 0,5502 | 96,84% | 1,45% | 1,70% |

![variância](D2_dados/D2_2_variancia.png)

## 4. Item 3: correlação de postos e sobreposição do top-k

Cada coluna compara o ranking nominal (m0, parâmetros nominais) com o de um futuro: os 18 membros (eixo clima) ou os 200 sorteios (eixo parâmetros). Mínimo, mediana e máximo sobre os futuros.

| Par | Células | k | Spearman, clima (mín / med / máx) | Top-k, clima | Spearman, parâmetros | Top-k, parâmetros |
|---|---|---|---|---|---|---|
| PRT solar | 3.414 | 342 | 0,9524 / 0,9743 / 0,9919 | 0,836 / 0,890 / 0,933 | 0,8922 / 0,9906 / 0,9999 | 0,836 / 0,942 / 0,994 |
| PRT wind | 3.332 | 334 | 0,9963 / 0,9986 / 0,9998 | 0,943 / 0,952 / 0,979 | 0,9969 / 0,9998 / 1,0000 | 0,946 / 0,985 / 1,000 |
| IND solar | 20.000 | 2.000 | 0,9632 / 0,9877 / 0,9968 | 0,893 / 0,953 / 0,977 | 0,9789 / 0,9979 / 0,9999 | 0,907 / 0,975 / 0,997 |
| IND wind | 20.000 | 2.000 | 0,9867 / 0,9972 / 0,9991 | 0,874 / 0,944 / 0,979 | 1,0000 / 1,0000 / 1,0000 | 0,994 / 0,998 / 1,000 |
| BRA solar | 20.000 | 2.000 | 0,9798 / 0,9888 / 0,9973 | 0,841 / 0,913 / 0,945 | 0,9809 / 0,9981 / 1,0000 | 0,854 / 0,951 / 0,998 |
| BRA wind | 20.000 | 2.000 | 0,9468 / 0,9954 / 0,9987 | 0,664 / 0,930 / 0,973 | 0,9998 / 1,0000 / 1,0000 | 0,984 / 0,996 / 1,000 |

## 5. Item 4: deslocamento das células do top-k nominal

Para cada célula do top-k nominal, o pior posto que ela alcança entre os futuros (ranking de cada futuro dentro da amostra), em múltiplos de k. O limiar de H1b e H3 é `k + m = 2k` (m = k).

| Par | Eixo | Mediana | q75 | q95 | Máximo | Células acima de 1,5k | Células acima de 2k |
|---|---|---|---|---|---|---|---|
| PRT solar | clima (18) | 0,61 | 0,90 | 1,26 | 1,59 | 0,29% | 0,00% |
| PRT solar | parâmetros (200) | 0,71 | 0,99 | 1,46 | 2,27 | 4,09% | 0,88% |
| PRT solar | os dois eixos (pior dos dois) |  |  |  | 2,27 |  | 0,88% |
| PRT wind | clima (18) | 0,56 | 0,84 | 1,10 | 1,28 | 0,00% | 0,00% |
| PRT wind | parâmetros (200) | 0,53 | 0,81 | 1,02 | 1,34 | 0,00% | 0,00% |
| PRT wind | os dois eixos (pior dos dois) |  |  |  | 1,34 |  | 0,00% |
| IND solar | clima (18) | 0,68 | 0,95 | 1,27 | 2,53 | 2,15% | 0,60% |
| IND solar | parâmetros (200) | 0,61 | 0,88 | 1,30 | 5,46 | 4,05% | 2,70% |
| IND solar | os dois eixos (pior dos dois) |  |  |  | 5,46 |  | 3,00% |
| IND wind | clima (18) | 0,75 | 1,07 | 1,36 | 1,67 | 1,10% | 0,00% |
| IND wind | parâmetros (200) | 0,51 | 0,76 | 0,96 | 1,07 | 0,00% | 0,00% |
| IND wind | os dois eixos (pior dos dois) |  |  |  | 1,67 |  | 0,00% |
| BRA solar | clima (18) | 0,83 | 1,18 | 1,75 | 2,77 | 9,55% | 2,20% |
| BRA solar | parâmetros (200) | 0,67 | 0,97 | 1,36 | 2,31 | 3,05% | 0,35% |
| BRA solar | os dois eixos (pior dos dois) |  |  |  | 2,77 |  | 2,55% |
| BRA wind | clima (18) | 0,90 | 1,25 | 1,92 | 2,54 | 15,25% | 3,55% |
| BRA wind | parâmetros (200) | 0,51 | 0,77 | 0,97 | 1,11 | 0,00% | 0,00% |
| BRA wind | os dois eixos (pior dos dois) |  |  |  | 2,54 |  | 3,55% |

![pior posto](D2_dados/D2_4_pior_posto.png)

**Diferença para o V_k do F7.** O pior posto aqui é o pior entre membros do ranking pelo LCOE de cada membro. O V_k do F7 usa outro objeto: o posto pelo pior regret (máximo sobre os GCMs) de cada SSP, dentro do conjunto ranqueado, e conta como vulnerável a célula com posto acima de k + m em ao menos uma SSP. Por isso o V_k é menor que a fração acima de 2k desta tabela. A tabela do item 7 refaz o V_k com a definição do F7.

## 6. Item 5: sinal climático nas células candidatas

Mudança do CF de cada membro do core em relação ao membro de referência m0, célula a célula (todas as células ranqueadas), e a mudança correspondente do LCOE nominal. Mediana e desvio padrão espacial de cada membro; a tabela resume os 18 membros (mínimo, mediana e máximo entre membros). Detalhe por membro em `D2_dados/D2_5_sinal_<par>.csv`.

| Par | CF: mediana da mudança, % (mín / med / máx entre membros) | CF: desvio espacial, % | LCOE: mediana da mudança, % | LCOE: desvio espacial, % |
|---|---|---|---|---|
| PRT solar | -0,3 / 2,9 / 4,3 | 0,7 / 1,1 / 1,5 | -4,1 / -2,9 / 0,3 | 0,6 / 1,1 / 1,4 |
| PRT wind | -7,3 / -2,3 / 4,9 | 0,7 / 1,2 / 2,0 | -4,7 / 2,3 / 7,8 | 0,8 / 1,3 / 2,2 |
| IND solar | -7,0 / -1,8 / 2,7 | 0,6 / 1,2 / 2,4 | -2,6 / 1,8 / 7,5 | 0,6 / 1,2 / 2,7 |
| IND wind | -6,7 / -1,6 / 5,3 | 2,0 / 4,2 / 8,2 | -5,0 / 1,6 / 7,2 | 2,1 / 4,6 / 8,6 |
| BRA solar | -1,8 / 0,8 / 3,0 | 0,6 / 1,2 / 1,8 | -2,9 / -0,8 / 1,8 | 0,6 / 1,2 / 1,8 |
| BRA wind | -0,6 / 6,9 / 28,8 | 3,9 / 8,4 / 34,6 | -22,4 / -6,5 / 0,6 | 3,8 / 6,6 / 16,5 |

## 7. Item 6: MR contra o LCOE nominal

`d_i = (LCOE_i - LCOE_min) / LCOE_min`, a distância nominal relativa à melhor célula do conjunto ranqueado. Regressão linear simples `MR = a + b x d` (todas as células ranqueadas).

| Par | Células | Spearman MR e LCOE | R² linear | b | a | MR mediano | d mediana | mediana de MR - d |
|---|---|---|---|---|---|---|---|---|
| PRT solar | 3.414 | 0,9296 | 0,8750 | 1,166 | 0,001 | 0,181 | 0,158 | 0,023 |
| PRT wind | 3.332 | 0,9994 | 0,9991 | 1,082 | 0,018 | 1,075 | 0,976 | 0,099 |
| IND solar | 93.159 | 0,9776 | 0,9695 | 1,136 | 0,044 | 0,445 | 0,358 | 0,083 |
| IND wind | 75.535 | 0,9965 | 0,9571 | 1,942 | -3,169 | 3,606 | 3,098 | 0,475 |
| BRA solar | 190.001 | 0,9891 | 0,9926 | 1,363 | -0,022 | 0,287 | 0,229 | 0,058 |
| BRA wind | 171.181 | 0,9987 | 0,9929 | 1,178 | -0,755 | 5,211 | 5,025 | 0,142 |

O MR só difere da distância nominal pela parte que o risco acrescenta (mediana de MR - d, última coluna); o R² mede o quanto da dispersão de MR a distância explica.

## 8. Item 7: V_k, D e rho com top-k 1% e m = k/2 (exploratório)

**Rótulo: análise exploratória, descritiva, sem veredito, que não substitui nenhum resultado da v1.0.** Mesmas definições de M-F7-05 a M-F7-07 (conferidas na seção 0), com `k = ceil(p_k x n)` e `m` como indicado. Além da variante pedida (1%, m = k/2), as duas variantes de um fator só mostram qual dos dois fatores faz a diferença. Os limiares registrados são `beta` = 0,20 para V_k, faixa 0,40 a 0,60 de rho e `delta` = 0,20 para d; aqui não se avalia nenhum.

| Par | Variante | k | m | V_k | vulneráveis | D_clim | D_tec | rho | d (H3) |
|---|---|---|---|---|---|---|---|---|---|
| PRT solar | primario (10%, m = k) | 342 | 342 | 0,0000 | 0 | 0,00000 | 0,00000 | não disponível | 0,00922 |
| PRT solar | exploratorio (1%, m = k/2) | 35 | 17,5 | 0,0000 | 0 | 0,00000 | 0,10532 | 0,000 | 0,27850 |
| PRT solar | exploratorio (1%, m = k) | 35 | 35 | 0,0000 | 0 | 0,00000 | 0,00000 | não disponível | 0,13496 |
| PRT solar | exploratorio (10%, m = k/2) | 342 | 171 | 0,0000 | 0 | 0,00395 | 0,00019 | 0,954 | 0,02362 |
| PRT wind | primario (10%, m = k) | 334 | 334 | 0,0000 | 0 | 0,00000 | 0,00000 | não disponível | 0,00000 |
| PRT wind | exploratorio (1%, m = k/2) | 34 | 17 | 0,0000 | 0 | 0,00000 | 0,00000 | não disponível | 0,00000 |
| PRT wind | exploratorio (1%, m = k) | 34 | 34 | 0,0000 | 0 | 0,00000 | 0,00000 | não disponível | 0,00000 |
| PRT wind | exploratorio (10%, m = k/2) | 334 | 167 | 0,0000 | 0 | 0,00000 | 0,00000 | não disponível | 0,00000 |
| IND solar | primario (10%, m = k) | 9.349 | 9.349 | 0,0000 | 0 | 0,00153 | 0,00000 | 1,000 | 0,00004 |
| IND solar | exploratorio (1%, m = k/2) | 935 | 467,5 | 0,1380 | 129 | 0,09241 | 0,00000 | 1,000 | 0,00475 |
| IND solar | exploratorio (1%, m = k) | 935 | 935 | 0,0021 | 2 | 0,07420 | 0,00000 | 1,000 | 0,00418 |
| IND solar | exploratorio (10%, m = k/2) | 9.349 | 4.674,5 | 0,0000 | 0 | 0,00678 | 0,00000 | 1,000 | 0,00086 |
| IND wind | primario (10%, m = k) | 7.554 | 7.554 | 0,0000 | 0 | 0,00000 | 0,00000 | não disponível | 0,00000 |
| IND wind | exploratorio (1%, m = k/2) | 756 | 378 | 0,0146 | 11 | 0,00733 | 0,00000 | 1,000 | 0,01073 |
| IND wind | exploratorio (1%, m = k) | 756 | 756 | 0,0000 | 0 | 0,00000 | 0,00000 | não disponível | 0,00000 |
| IND wind | exploratorio (10%, m = k/2) | 7.554 | 3.777 | 0,0000 | 0 | 0,00000 | 0,00000 | não disponível | 0,00000 |
| BRA solar | primario (10%, m = k) | 19.001 | 19.001 | 0,0029 | 56 | 0,00000 | 0,00000 | não disponível | 0,00028 |
| BRA solar | exploratorio (1%, m = k/2) | 1.901 | 950,5 | 0,0747 | 142 | 0,00155 | 0,00000 | 1,000 | 0,00494 |
| BRA solar | exploratorio (1%, m = k) | 1.901 | 1.901 | 0,0347 | 66 | 0,00000 | 0,00000 | não disponível | 0,00000 |
| BRA solar | exploratorio (10%, m = k/2) | 19.001 | 9.500,5 | 0,0176 | 335 | 0,00061 | 0,00000 | 1,000 | 0,00683 |
| BRA wind | primario (10%, m = k) | 17.119 | 17.119 | 0,0000 | 0 | 0,00000 | 0,00000 | não disponível | 0,00000 |
| BRA wind | exploratorio (1%, m = k/2) | 1.712 | 856 | 0,0006 | 1 | 0,00000 | 0,00000 | não disponível | 0,00000 |
| BRA wind | exploratorio (1%, m = k) | 1.712 | 1.712 | 0,0000 | 0 | 0,00000 | 0,00000 | não disponível | 0,00000 |
| BRA wind | exploratorio (10%, m = k/2) | 17.119 | 8.559,5 | 0,0000 | 0 | 0,00000 | 0,00000 | não disponível | 0,00000 |

rho é "não disponível" quando D_clim + D_tec = 0.

## 9. O que os achados dizem sobre as leituras 2 e 3 da seção 1 do arquivo de comandos

Só o que os números mostram; a classificação em A, B, C ou D fica para o D0.

- **Leitura 2, "os parâmetros do LHS que pesam são iguais em todas as células":** confirmada pelo código (item 1) e pela variância (item 2): em PRT solar, IND solar, BRA solar o deslocamento comum é maior que a parcela entre células no eixo parâmetros, e a interação célula x futuro não passa de 1,75% da variância de log(LCOE) em nenhum par nem eixo.
- **"A mudança climática média dos GCMs é espacialmente suave":** depende do par. Desvio espacial da mudança do CF entre células, por membro (mínimo a máximo entre os 18): PRT solar 0,7 a 1,5%; PRT wind 0,7 a 2,0%; IND solar 0,6 a 2,4%; IND wind 2,0 a 8,2%; BRA solar 0,6 a 1,8%; BRA wind 3,9 a 34,6%. Mesmo onde o desvio é grande, a parcela de interação do eixo clima fica abaixo de 1,75%, porque a variância entre células de log(LCOE) é muito maior.
- **"O deslocamento é quase impossível":** com o pior posto entre membros (item 4), a fração do top-k nominal acima de 2k é positiva em PRT solar, IND solar, BRA solar, BRA wind e zero nos demais; com a definição do V_k do F7 (posto do pior regret por SSP), o V_k primário é zero em PRT solar, PRT wind, IND solar, IND wind, BRA wind e BRA solar 0,0029. A diferença entre as duas medidas é de definição (ver a seção 5).
- **Leitura 3, "o MR mede sobretudo a distância à melhor célula":** Spearman entre MR e LCOE nominal de 0,9296 a 0,9994 e R² linear de MR sobre a distância de 0,8750 a 0,9991 (item 6): a leitura vale nos seis pares, com menos força na PRT solar (o par de menor Spearman e de menor R²).
- **Sensibilidade do desenho (item 7):** com 1% e m = k/2, V_k, D_clim ou D_tec ficam acima de zero em PRT solar, IND solar, IND wind, BRA solar, BRA wind; o V_k máximo entre os pares é 0,138 (abaixo de beta = 0,20 em todos os pares: sim). As variantes de um fator só estão na tabela.

## 10. Origem dos números e limites

| Número | Origem |
|---|---|
| LCOE por membro, nominal | `outputs/<ISO>/robustness_analysis/artifacts/nominal_lcoe_by_member_<tec>__core.parquet` |
| LCOE por sorteio | `lcoe_block` (kernel do F6) sobre F3, F4 e F5 de m0 com as linhas 1 a 200 da matriz de desenho (`build_design`, semente e tamanho de `config/experiments.yaml`) |
| MR, SR, postos, classes | `robustness_<tec>__core.parquet` |
| postos por SSP (V_k) | `ssp_scores_<tec>__core.parquet` |
| F7 gravado (conferência) | `h1_summary`, `h3_summary`, `h4_country` de cada par |
| CF por membro | `outputs/<ISO>/technical_potential/artifacts/potential_<tec>__central.parquet` |

Limites:

- Os itens 2 a 4 usam amostra de 20.000 células em IND e BRA; os postos são dentro da amostra e o k é 10% da amostra. Com outra semente os números mudam um pouco; a semente é a 202.
- Só 200 dos 4000 sorteios entram no eixo parâmetros, e só os 18 membros do core no eixo clima (sem a janela 2071-2100).
- A decomposição por variância é em log do LCOE; em nível ela está em `D2_resultados.json` e dá a mesma leitura qualitativa.
- Os extremos p5 e p95 de cada parâmetro (OAT) são os dos 4000 sorteios, não os limites do intervalo registrado; as faixas do desenho são estreitas (por exemplo, capex de 524 a 1034 USD/kW na solar de PRT).
- Nada aqui verifica se as faixas de incerteza do desenho estão bem escolhidas; só mede o que elas conseguem mover.

## 11. Manifestos e referências no momento da geração

Manifestos comparados com o instantâneo (SHA-256): 8 de 8 iguais.
Tag `v1.0` aponta para `107d1b8` e o objeto da tag `prereg-v1` é `685a29cc`, como registrados.
