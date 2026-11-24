# D5: caudas, convergência e células extremas (COMANDO 205)

Escrito para: o autor, para levar ao chat de planejamento. Data: 2026-11-23. Repositório em `2ae1654`, tag `prereg-v1` e `v1.0` inalteradas. Somente leitura: nada foi gravado em `GeoFREA_data/outputs/` nem no repositório. Scripts em `_notas_geofrea/diagnostico_v1_0/` (`d1_common.py`, `d5_run.py`, `d5_run2.py`, `d5_run3.py`, `d5_run4.py`, `d5_report.py`), dados em `D5_dados/`. Este texto é gerado de `D5_dados/`; os números não foram digitados à mão. Nenhum valor novo é proposto: o relatório só descreve e sinaliza.

## Resumo

1. **BRA eólica, LCOE > 200.** 62.437 das 178.289 células (35,0%) e 24,8% da capacidade passam do limiar; a causa é o CF baixo (mediana 0,055 contra 0,160 nas demais), não a conexão. Todas estão na tabela do F7 (56.742 entram no ranking). Nenhuma está no top-k, nenhuma satisfaz τ em qualquer futuro, e o L* de nenhum futuro vem delas. O efeito é sobre o tamanho do top-k: k = 17.119 com elas e 11.444 sem elas.
2. **PRT solar, L-252.** Reproduzi 1 − Jaccard de 0,0116, 0,0231 e 0,0116. Entre 2000 e 4000 sorteios trocam 2 células que saem e 2 que entram, todas a menos de 0,32% do MR do corte. Com k = 342, o critério de 0,01 admite no máximo 1 troca. Rodar além do teto, em 8000 e 16000 sorteios, dá 1 troca em cada passo (1 − Jaccard = 0,0058).
3. **As 5 células de menor LCOE de cada par.** Nenhuma tem distância à subestação menor que 1 km nem distância zero. Nenhum CF sai de [0, 1], mas as 5 da BRA eólica têm CF de 0,642 a 0,691 (o máximo do par é 0,691), acima do limiar de 0,60 adotado aqui. 5 das 30 estão em borda de máscara. Em PRT wind, IND solar, IND wind, 3 ou mais das 5 têm menos de 1 MW; o ranking conta células, não capacidade. Além disso, a convergência da BRA eólica foi calculada num conjunto de 178.285 células e o F7 usa 171.181 (seção 2.4).

## 0. Base e conferências

- LCOE reconstruído com o kernel igual ao gravado pelo F6 nos seis pares (diferença máxima das 30 células do item 3: 0,00; BRA eólica inteira: 0,00).
- O protocolo U-04 da PRT solar foi refeito com as funções de `convergence.py` e os mesmos insumos (3414 células, 18 membros do núcleo, `cf_min` 0,115, τ 54,53, top-k 10%): 1 − Jaccard 0,0116, 0,0231 e 0,0116, os da L-252. O top-k robusto de 4000 sorteios é igual ao `robust_rank <= k` gravado pelo F7.
- Limiares de sinalização do item 3 (escolhas deste relatório, não parâmetros do pipeline): CF acima de 0,30 (solar) ou 0,60 (eólica) ou abaixo de 0,05; distância à subestação menor que 1 km ou distância à estrada igual a zero; área do país na célula menor que 98% da nominal; no máximo 2 vizinhas candidatas; LCOE abaixo de 80% da média das vizinhas; capacidade menor que 1 MW.

## 1. BRA eólica: células com LCOE acima de 200 USD/MWh

### 1.1 Contagem, capacidade e CF

|  | LCOE > 200 | LCOE <= 200 |
|---|---|---|
| Células | 62.437 | 115.852 |
| Parcela das células | 35,0% | 65,0% |
| Capacidade (GW) | 494,2 | 1.496,5 |
| Parcela da capacidade | 24,8% | 75,2% |
| CF do F5, p5 / mediana / p95 | 0,016 / 0,055 / 0,082 | 0,091 / 0,160 / 0,348 |
| Weibull A a 100 m (m/s), p5 / mediana / p95 | 2,75 / 3,83 / 4,49 | 4,48 / 5,65 / 7,76 |
| Distância à subestação (km), p5 / mediana / p95 | 9,3 / 45,5 / 165,3 | 5,6 / 27,8 / 92,9 |
| Distância à estrada (km), p5 / mediana / p95 | 1,2 / 9,0 / 53,5 | 1,2 / 5,1 / 24,0 |
| LCOE nominal (USD/MWh), p5 / mediana / p95 | 208 / 312 / 1.156 | 49 / 106 / 187 |

A cauda é longa: 13.335 células passam de 500, 4.251 de 1.000 e 568 de 2.000; o máximo é 8.077 USD/MWh. Para comparação, τ da BRA eólica é 31,95 e só 137 células (2,01 GW) têm LCOE nominal abaixo dele.

**Causa.** Com o capex, o O&M, a vida e a taxa nominais, sem conexão e sem degradação, um CF de 0,081 já dá LCOE de 200; para chegar a τ seriam necessários CF de 0,507. Das 62.437 células acima de 200, 57.785 (92,5%) continuam acima de 200 mesmo sem conexão e sem degradação, isto é, só pelo CF. A parcela da conexão no LCOE é pequena: mediana 4,0% nas acima e 2,6% nas demais. O CF das acima vai de 0,0023 a 0,105. As acima também estão em sítios de vento mais fraco (A de 3,83 contra 5,65 m/s) e a distância à subestação mediana é maior (45,5 contra 27,8 km), mas isso só agrava.

### 1.2 Onde ficam

| Estado (admin1) | Células | Acima de 200 | Parcela | Capacidade acima (GW) |
|---|---|---|---|---|
| Mato Grosso (`BRA.12_1`) | 23.190 | 14.477 | 62,4% | 134,6 |
| Pará (`BRA.14_1`) | 14.990 | 13.092 | 87,3% | 92,4 |
| Amazonas (`BRA.4_1`) | 5.919 | 5.911 | 99,9% | 13,1 |
| Minas Gerais (`BRA.13_1`) | 19.117 | 4.646 | 24,3% | 38,0 |
| Maranhão (`BRA.10_1`) | 8.434 | 4.374 | 51,9% | 33,8 |
| Rondônia (`BRA.22_1`) | 4.901 | 4.245 | 86,6% | 41,3 |
| Tocantins (`BRA.27_1`) | 7.605 | 3.442 | 45,3% | 41,4 |
| Goiás (`BRA.9_1`) | 10.933 | 2.482 | 22,7% | 33,2 |

Há células acima de 200 em 24 dos 27 estados; os 3 maiores contribuintes (Mato Grosso, Pará, Amazonas) respondem por 53,6% delas. Estados com mais de 90% das células acima de 200: Amazonas (99,9%), Acre (97,2%). Estados com menos de 10%: 12 (por exemplo Paraná, Mato Grosso do Sul, São Paulo, Ceará). A latitude mediana das acima é -9,6 e a das demais -16,2; as longitudes medianas são -52,1 e -47,7. As acima concentram-se nos três estados maiores contribuintes e em latitudes mais ao norte; a mediana do Weibull A delas é menor (seção 1.1). A exclusão dominante delas é E5 em 91,8% dos casos, parecida com a das demais (69,0%). As tabelas completas estão em `D5_dados/D5_item1_por_admin1.csv` e `D5_item1_por_faixa.csv`.

### 1.3 Entram no conjunto F7? Afetam L*, MR ou SR?

**Conjunto F7.** Sim, todas as células com F6 entram na tabela do F7. Das acima de 200: 56.742 são `ranked`, 5.691 `incomplete_ensemble` e 4 `climate_data_invalid`. Das demais: 114.439 `ranked` e 1.413 `incomplete_ensemble`. 80,1% das células `incomplete_ensemble` têm LCOE acima de 200 (contra 35,0% do total), isto é, a classe de conjunto incompleto está concentrada nas células de CF baixo.

**L\*.** O L\* de cada futuro (menor LCOE entre as células) vai de 13,8 a 35,2 (mediana 22,8). Para cada célula acima de 200 calculei o menor LCOE que ela alcança nos 4000 sorteios do membro de referência e multipliquei pela razão mínima entre o LCOE nominal de qualquer membro e o do membro de referência (fatores aproximadamente multiplicativos): o limite inferior é 44,2 (mínimo) e 56,9 (percentil 1). 0 células têm limite inferior abaixo do maior L*. Logo, em nenhum futuro uma dessas células define L*; o L\* e, por consequência, o MR das demais células (que dependem do LCOE da célula e do L* de cada futuro) **não mudam** se elas forem retiradas. O limite é aproximado; o cálculo exato exigiria reavaliar todos os futuros.

**MR e SR.** Entre as 56.742 células `ranked` acima de 200 o MR vai de 6,93 (mínimo) a 52,2 (p95), mediana 12,1; nas demais, mediana 3,55. O menor MR entre as acima é 4,0 vezes o MR do corte do top-k (1,72). O SR delas é 0,000 (nenhum futuro com LCOE <= τ); nas demais, SR médio 0,0098. Acima de 200 no top-k robusto: 0; no top-k nominal: 0.

**O que elas afetam: o tamanho do top-k.** O top-k é 10% do conjunto ranqueado por contagem de células (M-F7-05). Com as acima de 200 no conjunto, k = 17.119; sem elas, k = 11.444. O ranking relativo das demais não muda, então o top-k menor é um subconjunto do maior, mas o limiar de corte vai de MR 1,72 para um valor menor e todas as estatísticas definidas sobre o top-k (H1, H3, H4, a meta de capacidade) dependem de k. Duas estatísticas que dependem de todas as células: o Spearman entre LCOE e MR é 0,9987 com todas e 0,9973 sem as acima; o Jaccard entre o top-10% nominal e o robusto é 0,9558 e 0,9579. As acima de 200 não decidem nada do que o F7 seleciona; só entram no denominador do percentual.

## 2. PRT solar, L-252: convergência do top-k

### 2.1 1 − Jaccard por tamanho de amostra

| Passo | k | Interseção | Saem | Entram | Jaccard | 1 − Jaccard | < 0,01 |
|---|---|---|---|---|---|---|---|
| 500 → 1000 | 342 | 340 | 2 | 2 | 0,9884 | 0,0116 | não |
| 1000 → 2000 | 342 | 338 | 4 | 4 | 0,9769 | 0,0231 | não |
| 2000 → 4000 | 342 | 340 | 2 | 2 | 0,9884 | 0,0116 | não |

Os três valores reproduzem a L-252 (0,0116, 0,0231, 0,0116). Com k = 342, a distância de Jaccard de s células trocadas (s saem, s entram) é 2s/(k + s): 0,0058 para s = 1 e 0,0116 para s = 2. A tolerância de 0,01 admite portanto no máximo **1 troca**; cada passo observado tem 2 trocas ou mais. Trocas admitidas pelo critério (s de cada lado) com o k do protocolo de cada par: PRT solar (k = 342): 1; PRT wind (k = 334): 1; IND solar (k = 9.349): 46; IND wind (k = 7.554): 37; BRA solar (k = 19.001): 95; BRA wind (k = 17.829): 89.

### 2.2 As células que trocam entre 2000 e 4000

| cell_id | Em 4000 | Posição por MR (4000) | MR (2000) | MR (4000) | SR | LCOE nominal | Dist. subest. (km) | CF | P (MW) |
|---|---|---|---|---|---|---|---|---|---|
| 7102652 | sai | 343 | 0,09292 | 0,09286 | 0,704 | 48,37 | 3,0 | 0,178 | 57,6 |
| 7160252 | entra | 340 | 0,09335 | 0,09271 | 0,735 | 47,36 | 9,7 | 0,187 | 67,7 |
| 7347421 | sai | 346 | 0,09320 | 0,09312 | 0,706 | 47,38 | 3,4 | 0,182 | 19,2 |
| 7354652 | entra | 342 | 0,09340 | 0,09282 | 0,734 | 46,90 | 9,1 | 0,188 | 122,7 |

O MR do corte (a 342ª célula) em 4000 sorteios é 0,09282 e o da seguinte 0,09286: a diferença é de 0,040%. As 4 células que trocam estão nas posições 340 a 346, a no máximo 0,32% do MR do corte. Todas ficam na zona PV 5 e têm LCOE nominal de 46,9 a 48,4 (τ = 54,53).

**Por que o corte é instável.** Há 10 células com MR dentro de ±0,5% do corte e 16 dentro de ±1% (de 3.414). O MR de uma mesma célula muda entre dois tamanhos independentes de sorteio em 0,48% (mediana), 1,05% (p99) e 1,67% (máximo); é um ruído de amostragem do P90, da ordem do espaçamento entre as células do corte. Os sorteios de tamanhos diferentes são independentes, não aninhados (nota da docstring de `convergence.py`), então a distância de Jaccard inclui esse ruído.

### 2.3 Além do teto (diagnóstico, fora do protocolo)

| Passo | Saem | Entram | 1 − Jaccard | < 0,01 |
|---|---|---|---|---|
| 4000 → 8000 | 1 | 1 | 0,0058 | sim |
| 8000 → 16000 | 1 | 1 | 0,0058 | sim |

Rodei o mesmo cálculo com 8000 e 16000 sorteios (mesma semente, mesmos insumos), só para ver o que acontece acima do teto de 4000 de `sampler.max_size_for_convergence`. É um diagnóstico: o protocolo e o tamanho adotado não mudam. Em cada passo há 1 troca, e 1 − Jaccard cai a 0,0058, abaixo da tolerância. Ou seja, o critério passaria no passo de 4000 para 8000 se o teto fosse maior. Como com k = 342 a tolerância admite só 1 troca, ainda é o acaso do sorteio de cada passo que decide se passa; dois passos seguidos com 1 troca não provam convergência além disso.

### 2.4 O conjunto da convergência e o do F7 não coincidem na BRA eólica

| Par | Convergência: células | Convergência: k | F7: células ranqueadas | F7: k | k igual |
|---|---|---|---|---|---|
| PRT solar | 3.414 | 342 | 3.414 | 342 | sim |
| PRT wind | 3.332 | 334 | 3.332 | 334 | sim |
| IND solar | 93.490 | 9.349 | 93.159 | 9.349 | sim |
| IND wind | 75.535 | 7.554 | 75.535 | 7.554 | sim |
| BRA solar | 190.001 | 19.001 | 190.001 | 19.001 | sim |
| BRA wind | 178.285 | 17.829 | 171.181 | 17.119 | NÃO |

O protocolo U-04 chama `build_cell_set` sem a lista de células `incomplete_ensemble` (o argumento fica nulo, e o docstring de `cell_set.py` diz que nesse caso nenhuma célula é excluída por esse motivo), enquanto o F7 exclui essas células do conjunto e do cálculo de k. Só a BRA eólica tem células `incomplete_ensemble` com F6 (7.104); por isso só nela os conjuntos diferem: a convergência ranqueia 178.285 células com k = 17.829 e o F7 ranqueia 171.181 com k = 17.119 (a diferença de 7.104 é exatamente a contagem `incomplete_ensemble` do F7). O resultado da BRA eólica na convergência (1 − Jaccard 0,0003 em 1000 sorteios) foi obtido num conjunto que contém essas células, não no do F7. O tamanho adotado (4000) é o mesmo `sampler.adopted_size` para todos os pares, então a decisão de tamanho não muda; o que fica registrado é que o critério foi testado num conjunto maior que o do F7 só nesse par.

## 3. As 5 células de menor LCOE nominal de cada par

LCOE nominal do F6 (membro de referência, cenário central, amostra nominal). As colunas: CF do F5; distância à subestação com o percentil dela no par; distância à estrada; zona PV (solar); parcela da conexão no LCOE; capacidade da célula; área do país na célula sobre a área nominal de 0,05 grau (`borda`); vizinhas candidatas entre as 8; razão do LCOE da célula sobre a média das vizinhas candidatas; sinais conforme os limiares da seção 0.

### PRT solar

Contexto do par: 3.414 células, LCOE mínimo 43,52, p1 44,97, mediana 50,38, τ 54,53. CF: mediana 0,180, p99 0,195, p99,9 0,199, máximo 0,201. Distância à subestação: p1 1,6 km, p5 2,8 km. Células com distância à subestação igual a zero: 0; menor que 1 km: 10; distância à estrada zero: 0.

| # | cell_id | lat; lon | LCOE | CF | Dist. subest. km (percentil) | Dist. estrada km | Zona | Conexão | P (MW) | Borda | Viz. | LCOE / vizinhas | Sinais |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `7621042` | 37,075; -7,875 | 43,52 | 0,197 | 2,4 (3,5%) | 1,9 | 5 | 3,8% | 89,83 | 1,00 | 8 | 0,98 | nenhum |
| 2 | `7621043` | 37,075; -7,825 | 43,65 | 0,197 | 3,0 (5,5%) | 1,0 | 5 | 4,1% | 104,63 | 1,00 | 8 | 0,98 | nenhum |
| 3 | `7628242` | 37,025; -7,875 | 43,67 | 0,199 | 5,9 (17,4%) | 1,0 | 5 | 5,3% | 15,25 | 1,00 | 8 | 0,99 | nenhum |
| 4 | `7613834` | 37,125; -8,275 | 43,84 | 0,198 | 5,0 (13,4%) | 0,5 | 5 | 4,9% | 84,30 | 1,00 | 7 | 0,99 | nenhum |
| 5 | `7628241` | 37,025; -7,925 | 43,87 | 0,200 | 7,5 (24,6%) | 0,6 | 5 | 6,0% | 9,76 | 1,00 | 6 | 0,99 | nenhum |

### PRT wind

Contexto do par: 3.332 células, LCOE mínimo 32,21, p1 38,52, mediana 63,65, τ 49,64. CF: mediana 0,256, p99 0,423, p99,9 0,477, máximo 0,536. Distância à subestação: p1 1,7 km, p5 3,1 km. Células com distância à subestação igual a zero: 0; menor que 1 km: 5; distância à estrada zero: 0.

| # | cell_id | lat; lon | LCOE | CF | Dist. subest. km (percentil) | Dist. estrada km | Zona | Conexão | P (MW) | Borda | Viz. | LCOE / vizinhas | Sinais |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `7628220` | 37,025; -8,975 | 32,21 | 0,536 | 45,7 (99,5%) | 0,5 | 5 | 10,0% | 0,27 | 0,40 | 1 | 0,95 | borda da máscara (área do país na célula = 40% da nominal); isolada (1 vizinha(s) candidata(s)); capacidade pequena (0,270 MW) |
| 2 | `7361818` | 38,875; -9,075 | 33,43 | 0,473 | 2,1 (1,7%) | 0,9 | 5 | 1,7% | 0,18 | 1,00 | 4 | 0,90 | capacidade pequena (0,181 MW) |
| 3 | `7628221` | 37,025; -8,925 | 33,96 | 0,503 | 40,4 (98,7%) | 1,9 | 5 | 9,1% | 0,12 | 0,68 | 3 | 0,99 | borda da máscara (área do país na célula = 68% da nominal); capacidade pequena (0,117 MW) |
| 4 | `7361816` | 38,875; -9,175 | 33,97 | 0,467 | 3,4 (6,0%) | 0,2 | 5 | 2,0% | 1,11 | 1,00 | 5 | 0,95 | nenhum |
| 5 | `7361817` | 38,875; -9,125 | 34,37 | 0,460 | 1,6 (0,8%) | 0,7 | 5 | 1,6% | 1,13 | 1,00 | 5 | 0,99 | nenhum |

Vento (Weibull A a 100 m; k; elevação): #1: 10,1 m/s; 2,49; 31 m; #2: 9,6 m/s; 2,01; 246 m; #3: 9,6 m/s; 2,54; 23 m; #4: 9,2 m/s; 2,35; 288 m; #5: 9,2 m/s; 2,15; 191 m.

### IND solar

Contexto do par: 93.617 células, LCOE mínimo 21,37, p1 25,26, mediana 29,03, τ 28,26. CF: mediana 0,181, p99 0,212, p99,9 0,233, máximo 0,246. Distância à subestação: p1 2,5 km, p5 4,8 km. Células com distância à subestação igual a zero: 0; menor que 1 km: 20; distância à estrada zero: 0.

| # | cell_id | lat; lon | LCOE | CF | Dist. subest. km (percentil) | Dist. estrada km | Zona | Conexão | P (MW) | Borda | Viz. | LCOE / vizinhas | Sinais |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `8033149` | 34,225; 77,475 | 21,37 | 0,225 | 6,9 (10,1%) | 4,6 | 3 | 2,2% | 0,07 | 1,00 | 8 | 0,94 | capacidade pequena (0,066 MW) |
| 2 | `7975525` | 34,625; 76,275 | 21,74 | 0,224 | 12,5 (26,9%) | 10,8 | 2 | 3,4% | 0,02 | 1,00 | 7 | 0,87 | capacidade pequena (0,025 MW) |
| 3 | `8040351` | 34,175; 77,575 | 21,79 | 0,223 | 12,0 (25,4%) | 1,8 | 2 | 3,3% | 0,14 | 1,00 | 8 | 0,96 | capacidade pequena (0,137 MW) |
| 4 | `8061946` | 34,025; 77,325 | 21,79 | 0,227 | 18,9 (46,1%) | 14,3 | 3 | 4,8% | 0,08 | 1,00 | 8 | 0,92 | capacidade pequena (0,083 MW) |
| 5 | `8033150` | 34,225; 77,525 | 21,82 | 0,221 | 8,7 (15,2%) | 4,7 | 2 | 2,6% | 0,12 | 1,00 | 8 | 0,97 | capacidade pequena (0,120 MW) |

### IND wind

Contexto do par: 75.535 células, LCOE mínimo 17,52, p1 31,55, mediana 71,79, τ 36,43. CF: mediana 0,142, p99 0,323, p99,9 0,402, máximo 0,577. Distância à subestação: p1 2,6 km, p5 4,7 km. Células com distância à subestação igual a zero: 0; menor que 1 km: 17; distância à estrada zero: 0.

| # | cell_id | lat; lon | LCOE | CF | Dist. subest. km (percentil) | Dist. estrada km | Zona | Conexão | P (MW) | Borda | Viz. | LCOE / vizinhas | Sinais |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `11777151` | 8,225; 77,575 | 17,52 | 0,576 | 8,3 (15,2%) | 1,6 | 7 | 1,1% | 0,85 | 1,00 | 2 | 0,91 | isolada (2 vizinha(s) candidata(s)); capacidade pequena (0,846 MW) |
| 2 | `11769951` | 8,275; 77,575 | 17,53 | 0,577 | 10,8 (23,8%) | 0,6 | 7 | 1,4% | 0,59 | 1,00 | 5 | 0,82 | capacidade pequena (0,587 MW) |
| 3 | `11777153` | 8,225; 77,675 | 19,54 | 0,514 | 4,0 (3,4%) | 1,1 | 7 | 0,7% | 0,33 | 1,00 | 3 | 0,85 | capacidade pequena (0,335 MW) |
| 4 | `11762750` | 8,325; 77,525 | 19,93 | 0,507 | 10,8 (23,7%) | 2,4 | 7 | 1,4% | 0,78 | 1,00 | 4 | 0,97 | capacidade pequena (0,781 MW) |
| 5 | `11762751` | 8,325; 77,575 | 19,94 | 0,508 | 12,8 (30,8%) | 1,0 | 7 | 1,6% | 0,28 | 1,00 | 7 | 0,84 | capacidade pequena (0,283 MW) |

Vento (Weibull A a 100 m; k; elevação): #1: 10,6 m/s; 2,87; 79 m; #2: 11,1 m/s; 2,49; 67 m; #3: 9,8 m/s; 2,70; 47 m; #4: 10,3 m/s; 2,11; 136 m; #5: 10,5 m/s; 1,99; 92 m.

### BRA solar

Contexto do par: 190.001 células, LCOE mínimo 42,56, p1 45,58, mediana 52,30, τ 43,97. CF: mediana 0,182, p99 0,202, p99,9 0,206, máximo 0,211. Distância à subestação: p1 2,9 km, p5 6,4 km. Células com distância à subestação igual a zero: 0; menor que 1 km: 40; distância à estrada zero: 0.

| # | cell_id | lat; lon | LCOE | CF | Dist. subest. km (percentil) | Dist. estrada km | Zona | Conexão | P (MW) | Borda | Viz. | LCOE / vizinhas | Sinais |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `14539549` | -10,975; -42,525 | 42,56 | 0,210 | 2,8 (0,9%) | 6,4 | 7 | 1,1% | 107,85 | 1,00 | 8 | 0,99 | nenhum |
| 2 | `13646854` | -4,775; -37,275 | 42,60 | 0,210 | 2,8 (0,8%) | 0,8 | 6 | 1,1% | 158,18 | 0,52 | 6 | 0,99 | borda da máscara (área do país na célula = 52% da nominal) |
| 3 | `13603645` | -4,475; -37,725 | 42,75 | 0,209 | 2,7 (0,8%) | 6,6 | 6 | 1,1% | 63,03 | 0,24 | 5 | 0,98 | borda da máscara (área do país na célula = 24% da nominal) |
| 4 | `13639654` | -4,725; -37,275 | 42,75 | 0,210 | 5,3 (3,5%) | 1,5 | 6 | 1,6% | 25,73 | 0,08 | 4 | 1,00 | borda da máscara (área do país na célula = 8% da nominal) |
| 5 | `14532349` | -10,925; -42,525 | 42,80 | 0,209 | 4,2 (2,2%) | 1,9 | 7 | 1,4% | 317,43 | 1,00 | 8 | 0,99 | nenhum |

### BRA wind

Contexto do par: 178.289 células, LCOE mínimo 23,96, p1 40,00, mediana 148,79, τ 31,95. CF: mediana 0,115, p99 0,422, p99,9 0,516, máximo 0,691. Distância à subestação: p1 3,1 km, p5 6,4 km. Células com distância à subestação igual a zero: 0; menor que 1 km: 28; distância à estrada zero: 0.

| # | cell_id | lat; lon | LCOE | CF | Dist. subest. km (percentil) | Dist. estrada km | Zona | Conexão | P (MW) | Borda | Viz. | LCOE / vizinhas | Sinais |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `13826869` | -6,025; -36,525 | 23,96 | 0,691 | 3,8 (1,7%) | 5,8 | 6 | 0,7% | 14,49 | 1,00 | 8 | 0,87 | CF fora da faixa adotada (0,60) |
| 2 | `13819670` | -5,975; -36,475 | 24,39 | 0,683 | 11,2 (13,0%) | 1,9 | 6 | 1,3% | 12,46 | 1,00 | 8 | 0,89 | CF fora da faixa adotada (0,60) |
| 3 | `13826870` | -6,025; -36,475 | 24,39 | 0,681 | 7,2 (6,2%) | 5,6 | 6 | 0,9% | 20,38 | 1,00 | 8 | 0,82 | CF fora da faixa adotada (0,60) |
| 4 | `13834067` | -6,075; -36,625 | 25,52 | 0,649 | 4,4 (2,3%) | 1,3 | 6 | 0,7% | 14,63 | 1,00 | 8 | 0,75 | CF fora da faixa adotada (0,60); LCOE 75% da média das vizinhas |
| 5 | `13826868` | -6,025; -36,575 | 25,88 | 0,642 | 6,8 (5,6%) | 5,8 | 6 | 0,9% | 12,36 | 1,00 | 8 | 0,89 | CF fora da faixa adotada (0,60) |

Vento (Weibull A a 100 m; k; elevação): #1: 12,6 m/s; 3,39; 614 m; #2: 12,7 m/s; 3,22; 458 m; #3: 11,8 m/s; 4,00; 659 m; #4: 11,8 m/s; 3,26; 634 m; #5: 12,4 m/s; 2,73; 439 m.

### 3.1 Leitura dos sinais

- **Distância zero suspeita.** Nenhuma das 30 células tem distância à subestação menor que 1 km (mínimo 1,61 km) nem distância à estrada zero (mínimo 0,20 km). Nos seis pares, o total de células com distância à subestação zero é 0 e com distância à estrada zero é 0; as que têm menos de 1 km à subestação são de 5 a 40 por par (contexto de cada par).
- **CF.** Nenhum CF está fora de [0, 1]. Pelo limiar adotado aqui (0,30 solar, 0,60 eólica), 5 das 30 ficam acima: BRA wind #1 (0,691), BRA wind #2 (0,683), BRA wind #3 (0,681), BRA wind #4 (0,649), BRA wind #5 (0,642). Todas as 5 da BRA eólica têm CF no percentil 99,9972% ou mais do par, e o CF máximo do par é 0,691. O diagnóstico OQ-114 (`docs/evidence/land_and_potential/oq114_170.md`) mostra que o CF por pixel do F5 reproduz o do Global Wind Atlas (correlação de 0,997 a 0,999), então esse valor extremo vem do dado de vento, não do código do F5. A faixa 0,60 é uma referência minha de CF líquido de usina onshore, não vem do pipeline.
- **Borda de máscara.** 5 das 30 têm menos de 98% da área nominal dentro do país: PRT wind #1 (0,40), PRT wind #3 (0,68), BRA solar #2 (0,52), BRA solar #3 (0,24), BRA solar #4 (0,08). São células na borda da máscara (coordenadas na tabela do par). O LCOE por MW não depende da área da célula, mas o CF do F5 é ponderado pela área elegível dos pixels (D-F5-038), que ficam dentro do país, então descreve só a parte da célula dentro do país; a razão do LCOE da célula sobre o das vizinhas (0,95 a 1,00) não mostra um pico de LCOE nelas.
- **Pico local.** 1 das 30 tem LCOE abaixo de 80% da média das vizinhas candidatas (BRA wind #4 (0,75)). As demais ficam entre 0,82 e 1,00 da média das vizinhas.
- **Aglomeração.** As 5 menores de cada par não são 5 achados independentes: PRT solar: 2 bloco(s) (células a até 0,3 grau uma da outra); PRT wind: 2 bloco(s) (células a até 0,3 grau uma da outra); IND solar: 2 bloco(s) (células a até 0,3 grau uma da outra); IND wind: 1 bloco(s) (células a até 0,3 grau uma da outra); BRA solar: 3 bloco(s) (células a até 0,3 grau uma da outra); BRA wind: 1 bloco(s) (células a até 0,3 grau uma da outra). As coordenadas estão nas tabelas.

### 3.2 Capacidade das células do topo (propriedade do desenho, observada aqui)

| Par | P mediana (MW) | Células com P < 1 MW | Parcela | No top-k nominal, P < 1 MW | Parcela do top-k | P mediana no top-k (MW) | Capacidade do top-k sobre o total |
|---|---|---|---|---|---|---|---|
| PRT solar | 23,1 | 237 | 6,9% | 10 de 342 | 2,9% | 53,2 | 14,2% |
| PRT wind | 6,0 | 574 | 17,2% | 112 de 334 | 33,5% | 2,7 | 6,5% |
| IND solar | 3,0 | 26.520 | 28,3% | 1.423 de 9.349 | 15,2% | 10,2 | 25,2% |
| IND wind | 1,9 | 25.944 | 34,3% | 1.365 de 7.554 | 18,1% | 4,6 | 17,5% |
| BRA solar | 55,8 | 9.565 | 5,0% | 123 de 19.001 | 0,6% | 84,5 | 13,6% |
| BRA wind | 11,8 | 14.101 | 7,9% | 645 de 17.119 | 3,8% | 15,6 | 12,1% |

O top-k é por contagem de células, não por capacidade. A parcela do top-k nominal com menos de 1 MW vai de 0,6% (BRA solar) a 33,5% (PRT wind). Nos pares PRT wind, IND solar, IND wind, 3 ou mais das 5 células de menor LCOE têm menos de 1 MW. Isso não é defeito de uma célula; é uma propriedade da seleção por contagem, que dá o mesmo peso a uma célula de poucos kW e a uma de centenas de MW. O relatório só a registra.

## 4. Manifestos e referências no momento da geração

Manifestos comparados com o instantâneo `_snapshots/20261123_pre204` (SHA-256): 8 de 8 iguais. O D5 não grava nada no pipeline; o instantâneo do 204 vale como base porque os scripts do 205 só leem.
Tag `v1.0` aponta para `107d1b8` e o objeto da tag `prereg-v1` é `685a29cc`, como registrados.
