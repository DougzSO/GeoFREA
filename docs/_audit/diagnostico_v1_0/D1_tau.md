# D1: o τ e o domínio econômico (COMANDO 201)

Escrito para: o autor, para levar ao chat de planejamento. Data: 2026-11-23. Repositório em `2c94752`, tag `prereg-v1` e `v1.0` inalteradas. Somente leitura: nada foi gravado em `GeoFREA_data/outputs/` nem no repositório. Os scripts estão em `_notas_geofrea/diagnostico_v1_0/` (`d1_common.py`, `d1_run.py`, `d1_report.py`) e os dados de cada tabela e figura em `D1_dados/`. Este texto é gerado de `D1_dados/` por `d1_report.py`: nenhum número foi digitado à mão.

Base de todas as medidas: janela core, cenário central de solo, membro de referência m0, amostra nominal (linha 0 da matriz de desenho). O "conjunto" é o conjunto F7 do par (células com LCOE nominal finito e presentes na tabela de robustez), e a capacidade é o `P_MW` do F5. Nenhum valor novo de τ é proposto.

## 0. Como os números foram conferidos

1. O LCOE nominal de cada célula foi recalculado com o kernel do F6 (`lcoe_block`, importado) a partir de F3, F4 e F5. Diferença máxima contra o `lcoe_summary` gravado pelo F6: **0,0** nos seis pares (todas as células, m0).
2. A decomposição por termos fecha com o LCOE nominal de cada célula com tolerância de 1e-9 (asserção no `d1_run.py`, em todas as células de cada par); o erro máximo observado foi 3,6e-12 (`d1_check.py`).
3. O τ foi recalculado do mesmo modo que `scripts/calibrate_tau_irena.py` (planta de referência do IRENA 2024 pelo kernel, taxa central, vida de 25 anos): PRT solar: 54,5319 contra 54,53, PRT wind: 49,6425 contra 49,64, IND solar: 28,2574 contra 28,26, IND wind: 36,4349 contra 36,43, BRA solar: 43,9748 contra 43,97, BRA wind: 31,9454 contra 31,95. As diferenças são de arredondamento (o τ da configuração tem duas casas).
4. O domínio econômico do H5 (número de células, capacidade e E_0 no τ primário) foi reproduzido a partir das tabelas do F5 e do F6 e coincide com `h5_summary` do F7 nos seis pares (ver 5).
5. Os manifestos de PRT, IND, BRA e do `cross_country` têm o mesmo SHA-256 do instantâneo `_snapshots/20261123_pre201` (verificado na hora de gerar este texto; ver a seção 10).

## 1. Achados em uma página

- **BRA eólica:** o CF da planta de referência do τ é 0,53; as células ficam abaixo dele em 99,93% dos casos (p50 0,118, p90 0,267). Na banda do p10 das células (LCOE médio 63,38), a diferença para o τ (31,95) é de 31,43 USD/MWh, dos quais 30,03 vêm da energia da célula (CF), 1,80 da conexão, -1,40 da vida útil (sinal negativo: reduz) e 0,00 do capex e O&M.
- **Vida útil:** o τ usa a vida de 25 anos do IRENA e as células usam 30 anos (`parameters.json`). Isso reduz o LCOE das células em 1,40 a 3,63 USD/MWh em relação à base do τ (valor por par; é o mesmo em todas as células de um par). O capex do modelo é igual ao TIC do IRENA nos seis pares; o O&M do modelo difere do IRENA em quatro pares (ver 2).
- **Domínio econômico:** a fração da capacidade do conjunto com LCOE nominal <= τ é PRT solar 99,336%, PRT wind 8,918%, IND solar 56,499%, IND wind 6,342%, BRA solar 0,075%, BRA wind 0,103%.
- **SR:** a fração de células com SR = 0 é PRT solar 0,0%, PRT wind 18,3%, IND solar 2,1%, IND wind 79,7%, BRA solar 3,7%, BRA wind 83,4%. A hipótese de que o SR é zero em quase todas as células vale para a eólica do BRA e da Índia, e não para a solar do BRA.
- **H5 na borda:** na solar da Índia, E_0 excede G em 12,3 TWh (1,62% de G); o menor τ com H_0 >= 0 é 28,22, a 0,04 USD/MWh do primário (0,13%). Na solar do BRA o menor τ com H_0 >= 0 é 44,83, 2,0% acima do primário (43,97); na eólica da Índia é 68,95, 1,89 vez o primário e acima do fim da faixa registrada (53,00).

## 2. Item 1: CF da planta de referência do τ contra o CF das células

O CF efetivo é a energia nominal que o kernel usa (`E_MWh` do F5 vezes o fator de reescala no valor nominal do parâmetro de energia) dividida por `8760 x P_MW`. Ele é igual ao CF gravado no F5 (`CF`) nos seis pares (as duas bases dão as mesmas colunas em `D1_dados/D1_1_cf.csv`), porque o fator de reescala vale 1 no valor nominal. "Ponderado" usa `P_MW` como peso.

| Par | CF da referência | Percentil do CF de ref. entre as células | Células com CF >= ref. | Capacidade com CF >= ref. | CF p10 | CF p50 | CF p90 | CF p50 pond. | Células |
|---|---|---|---|---|---|---|---|---|---|
| PRT solar | 0,150 (proxy regional) | 0,0% | 100,0% | 100,0% | 0,168 | 0,180 | 0,189 | 0,186 | 3.414 |
| PRT wind | 0,340 | 91,4% | 8,6% | 5,1% | 0,175 | 0,256 | 0,335 | 0,263 | 3.332 |
| IND solar | 0,180 | 45,3% | 54,7% | 80,5% | 0,168 | 0,181 | 0,196 | 0,188 | 93.490 |
| IND wind | 0,290 | 97,2% | 2,8% | 5,0% | 0,072 | 0,142 | 0,239 | 0,171 | 75.535 |
| BRA solar | 0,200 | 97,5% | 2,5% | 5,5% | 0,166 | 0,182 | 0,194 | 0,186 | 190.001 |
| BRA wind | 0,530 | 99,9% | 0,1% | 0,1% | 0,045 | 0,118 | 0,267 | 0,137 | 171.181 |

Figura: `D1_dados/D1_1_cf.png` (histograma do CF efetivo com a linha do CF de referência).

![CF](D1_dados/D1_1_cf.png)

Fatos: em PRT solar nenhuma célula tem CF abaixo do da referência (o CF da referência é o proxy da média da UE, L-242); em IND solar o CF de referência fica no percentil 45; nos outros quatro pares fica entre os percentis 91 e 99,9 das células.

## 3. Item 2: decomposição do LCOE nominal da planta de referência do τ às células

**Método.** Parte-se da planta de referência (a que dá o τ: TIC, O&M, CF e vida de 25 anos do IRENA 2024, taxa central do par, sem conexão, sem degradação) e troca-se um termo por vez pelo valor do kernel para a célula, na ordem abaixo. Cada linha é a variação do LCOE nesse passo, em USD/MWh, média das células do grupo. A soma dos passos é a diferença entre o LCOE médio do grupo e o τ. A ordem dos passos afeta a divisão entre termos que interagem (energia e custos de capital, por exemplo); a ordem usada é a da tabela.

1. capex e O&M do modelo no lugar do TIC e do O&M do IRENA; 2. vida útil do modelo (30 anos) no lugar de 25; 3. energia da célula (CF) no lugar do CF de referência; 4. conexão (baia e linha até a subestação); 5. acesso (estrada); 6. degradação; 7. perda de transmissão.

Os passos 5 e 7 valem 0 nos seis pares: o custo de estrada não é cobrado (`road_cost_excluded`, aviso do F6) e a perda de transmissão do modelo é 0 (`transmission_loss_per_km`).

Capex e O&M do IRENA contra os do modelo (USD/kW e fração do capex ao ano):

| Par | TIC IRENA | capex do modelo | O&M IRENA / TIC | O&M do modelo (fração) | vida IRENA | vida do modelo | taxa central |
|---|---|---|---|---|---|---|---|
| PRT solar | 779 | 779 | 0,0266 | 0,0250 | 25 | 30 | 4,200% |
| PRT wind | 1.659 | 1.659 | 0,0271 | 0,0247 | 25 | 30 | 3,700% |
| IND solar | 525 | 525 | 0,0209 | 0,0171 | 25 | 30 | 4,000% |
| IND wind | 1.110 | 1.110 | 0,0207 | 0,0207 | 25 | 30 | 3,800% |
| BRA solar | 724 | 724 | 0,0151 | 0,0124 | 25 | 30 | 7,700% |
| BRA wind | 1.307 | 1.307 | 0,0222 | 0,0222 | 25 | 30 | 7,700% |

### Banda do p10 das células (p8 a p12): o que separa o p10 do τ

| Par | LCOE médio | τ | Δ total | capex e O&M | vida útil | energia (CF) | conexão | degradação | CF médio | dist. subest. média (km) |
|---|---|---|---|---|---|---|---|---|---|---|
| PRT solar | 47,03 | 54,53 | -7,50 | -0,96 | -3,63 | -9,97 | 2,76 | 4,29 | 0,187 | 8,8 |
| PRT wind | 48,34 | 49,64 | -1,30 | -1,34 | -3,48 | 0,73 | 1,84 | 0,96 | 0,335 | 12,8 |
| IND solar | 26,70 | 28,26 | -1,56 | -1,25 | -2,06 | -1,92 | 1,31 | 2,36 | 0,195 | 22,0 |
| IND wind | 42,65 | 36,43 | 6,22 | -0,01 | -2,72 | 7,19 | 0,92 | 0,84 | 0,239 | 18,7 |
| BRA solar | 47,71 | 43,97 | 3,74 | -1,13 | -2,05 | 1,59 | 1,74 | 3,59 | 0,193 | 20,6 |
| BRA wind | 63,38 | 31,95 | 31,43 | 0,00 | -1,40 | 30,03 | 1,80 | 1,00 | 0,268 | 31,6 |

### Decil 1 (as 10% de menor LCOE)

| Par | LCOE médio | τ | Δ total | capex e O&M | vida útil | energia (CF) | conexão | degradação | CF médio | dist. subest. média (km) |
|---|---|---|---|---|---|---|---|---|---|---|
| PRT solar | 46,09 | 54,53 | -8,44 | -0,96 | -3,63 | -10,43 | 2,37 | 4,21 | 0,190 | 6,8 |
| PRT wind | 44,11 | 49,64 | -5,53 | -1,34 | -3,48 | -3,26 | 1,68 | 0,87 | 0,370 | 12,9 |
| IND solar | 25,93 | 28,26 | -2,32 | -1,25 | -2,06 | -2,34 | 1,09 | 2,24 | 0,199 | 18,2 |
| IND wind | 37,25 | 36,43 | 0,82 | -0,01 | -2,72 | 1,98 | 0,83 | 0,73 | 0,278 | 19,6 |
| BRA solar | 46,73 | 43,97 | 2,76 | -1,13 | -2,05 | 0,96 | 1,46 | 3,51 | 0,195 | 16,9 |
| BRA wind | 51,59 | 31,95 | 19,65 | 0,00 | -1,40 | 18,83 | 1,40 | 0,81 | 0,337 | 29,4 |

### Mediana (p45 a p55)

| Par | LCOE médio | τ | Δ total | capex e O&M | vida útil | energia (CF) | conexão | degradação | CF médio | dist. subest. média (km) |
|---|---|---|---|---|---|---|---|---|---|---|
| PRT solar | 50,39 | 54,53 | -4,14 | -0,96 | -3,63 | -8,12 | 3,93 | 4,64 | 0,179 | 14,4 |
| PRT wind | 63,67 | 49,64 | 14,03 | -1,34 | -3,48 | 14,71 | 2,88 | 1,26 | 0,256 | 16,6 |
| IND solar | 29,03 | 28,26 | 0,77 | -1,25 | -2,06 | 0,02 | 1,40 | 2,66 | 0,180 | 21,6 |
| IND wind | 71,87 | 36,43 | 35,44 | -0,01 | -2,72 | 35,06 | 1,69 | 1,42 | 0,142 | 20,8 |
| BRA solar | 52,30 | 43,97 | 8,33 | -1,13 | -2,05 | 4,43 | 3,14 | 3,93 | 0,181 | 38,0 |
| BRA wind | 144,66 | 31,95 | 112,72 | 0,00 | -1,40 | 106,87 | 4,96 | 2,27 | 0,118 | 39,3 |

### Decil 10 (as 10% de maior LCOE)

| Par | LCOE médio | τ | Δ total | capex e O&M | vida útil | energia (CF) | conexão | degradação | CF médio | dist. subest. média (km) |
|---|---|---|---|---|---|---|---|---|---|---|
| PRT solar | 54,81 | 54,53 | 0,27 | -0,96 | -3,63 | -5,77 | 5,60 | 5,03 | 0,170 | 21,6 |
| PRT wind | 116,41 | 49,64 | 66,77 | -1,34 | -3,48 | 64,25 | 5,04 | 2,31 | 0,145 | 15,2 |
| IND solar | 37,18 | 28,26 | 8,93 | -1,25 | -2,06 | 4,20 | 4,91 | 3,12 | 0,156 | 66,2 |
| IND wind | 323,44 | 36,43 | 287,00 | -0,01 | -2,72 | 270,46 | 12,90 | 6,38 | 0,049 | 31,6 |
| BRA solar | 70,75 | 43,97 | 26,77 | -1,13 | -2,05 | 8,61 | 16,01 | 5,33 | 0,166 | 190,4 |
| BRA wind | 734,70 | 31,95 | 702,75 | 0,00 | -1,40 | 614,93 | 77,68 | 11,54 | 0,030 | 104,9 |

### Parcela de cada termo na diferença entre a banda do p10 e o τ

| Par | Δ total (USD/MWh) | capex e O&M | vida útil | energia (CF) | conexão | degradação |
|---|---|---|---|---|---|---|
| PRT solar | -7,50 | 13% | 48% | 133% | -37% | -57% |
| PRT wind | -1,30 | 103% | 268% | -56% | -141% | -74% |
| IND solar | -1,56 | 80% | 132% | 123% | -84% | -151% |
| IND wind | 6,22 | 0% | -44% | 116% | 15% | 14% |
| BRA solar | 3,74 | -30% | -55% | 42% | 47% | 96% |
| BRA wind | 31,43 | 0% | -4% | 96% | 6% | 3% |

Quando os termos têm sinais opostos as parcelas passam de 100% ou ficam negativas; a soma das cinco colunas é 100%.

### Termos absolutos do LCOE final (soma = LCOE médio do grupo, USD/MWh)

Capital (capex), O&M fixo e conexão, com a energia e a degradação da célula no denominador. Estrada e O&M variável valem 0.

| Par | Grupo | capex | O&M fixo | conexão | LCOE médio |
|---|---|---|---|---|---|
| PRT solar | decil 1 (<= p10) | 30,58 | 12,90 | 2,61 | 46,09 |
| PRT solar | mediana (p45 a p55) | 32,40 | 13,67 | 4,33 | 50,39 |
| PRT solar | decil 10 (>= p90) | 34,20 | 14,43 | 6,17 | 54,81 |
| PRT wind | decil 1 (<= p10) | 29,37 | 13,02 | 1,72 | 44,11 |
| PRT wind | mediana (p45 a p55) | 42,07 | 18,65 | 2,94 | 63,67 |
| PRT wind | decil 10 (>= p90) | 77,09 | 34,18 | 5,14 | 116,41 |
| IND solar | decil 1 (<= p10) | 19,11 | 5,65 | 1,18 | 25,93 |
| IND solar | mediana (p45 a p55) | 21,21 | 6,27 | 1,54 | 29,03 |
| IND solar | decil 10 (>= p90) | 24,58 | 7,27 | 5,33 | 37,18 |
| IND wind | decil 1 (<= p10) | 26,64 | 9,77 | 0,85 | 37,25 |
| IND wind | mediana (p45 a p55) | 51,32 | 18,83 | 1,73 | 71,87 |
| IND wind | decil 10 (>= p90) | 227,01 | 83,27 | 13,16 | 323,44 |
| BRA solar | decil 1 (<= p10) | 39,48 | 5,67 | 1,58 | 46,73 |
| BRA solar | mediana (p45 a p55) | 42,76 | 6,14 | 3,40 | 52,30 |
| BRA solar | decil 10 (>= p90) | 46,72 | 6,71 | 17,32 | 70,75 |
| BRA wind | decil 1 (<= p10) | 39,90 | 10,26 | 1,43 | 51,59 |
| BRA wind | mediana (p45 a p55) | 111,06 | 28,56 | 5,04 | 144,66 |
| BRA wind | decil 10 (>= p90) | 521,63 | 134,15 | 78,92 | 734,70 |

## 4. Item 3: SR

Células do conjunto com SR e MR calculados na tabela `robustness_<tec>__core` (as classes `climate_data_invalid`, `incomplete_ensemble` e as sem LCOE ficam sem SR e MR). SR é a parcela dos futuros (membros do core, amostras s >= 1 do desenho) em que a célula é viável e o LCOE não excede o τ primário (M-F7-04).

| Par | Células com SR | SR = 0 | SR = 1 | q25 | q50 | q75 | q90 | máx. | Spearman SR e MR | Spearman SR e LCOE nominal |
|---|---|---|---|---|---|---|---|---|---|---|
| PRT solar | 3.414 | 0,0% | 0,0000% | 0,554 | 0,608 | 0,669 | 0,725 | 0,854 | -0,972 | -0,973 |
| PRT wind | 3.332 | 18,3% | 0,0000% | 0,001 | 0,034 | 0,198 | 0,414 | 0,996 | -0,995 | -0,995 |
| IND solar | 93.490 | 2,1% | 0,0000% | 0,128 | 0,196 | 0,274 | 0,369 | 0,856 | -0,969 | -0,994 |
| IND wind | 75.535 | 79,7% | 0,0212% | 0,000 | 0,000 | 0,000 | 0,014 | 1,000 | -0,699 | -0,701 |
| BRA solar | 190.001 | 3,7% | 0,0000% | 0,104 | 0,196 | 0,290 | 0,348 | 0,530 | -0,996 | -0,991 |
| BRA wind | 171.181 | 83,4% | 0,0000% | 0,000 | 0,000 | 0,000 | 0,002 | 0,991 | -0,618 | -0,615 |

| Par | τ | LCOE p10 das células | LCOE p50 das células | Células com LCOE nominal <= τ | Capacidade com LCOE nominal <= τ | Células com SR > 0 |
|---|---|---|---|---|---|---|
| PRT solar | 54,53 | 47,04 | 50,38 | 95,43% | 99,34% | 100,0% |
| PRT wind | 49,64 | 48,38 | 63,65 | 12,67% | 8,92% | 81,7% |
| IND solar | 28,26 | 26,69 | 29,03 | 32,00% | 56,50% | 97,9% |
| IND wind | 36,43 | 42,68 | 71,79 | 3,62% | 6,34% | 20,3% |
| BRA solar | 43,97 | 47,71 | 52,30 | 0,05% | 0,08% | 96,3% |
| BRA wind | 31,95 | 63,44 | 144,37 | 0,08% | 0,10% | 16,6% |

Fatos: células com SR = 1: PRT solar 0, PRT wind 0, IND solar 0, IND wind 16, BRA solar 0, BRA wind 0. Nos quatro pares fora as eólicas de IND e BRA o SR é quase uma função monótona do LCOE nominal e do MR (módulo do Spearman de 0,969 ou mais); nas duas eólicas, com mais de três quartos das células em SR = 0, o módulo fica entre 0,615 e 0,701 (empates no zero).

## 5. Item 4: fração da capacidade com LCOE nominal <= x

Curva descritiva, x de 20 a 200 USD/MWh (passo 5; tabela completa em `D1_dados/D1_4_curva_capacidade.csv`). Marcas: o τ primário, as pontas da faixa registrada (`tau_min`, `tau_max`) e o LCOE nacional publicado do IRENA 2024 (com p5 e p95).

![curva](D1_dados/D1_4_curva_capacidade.png)

| Par | x=20 | x=30 | x=40 | x=50 | x=60 | x=80 | x=100 | x=150 | x=200 |
|---|---|---|---|---|---|---|---|---|---|
| PRT solar | 0,0% | 0,0% | 0,0% | 57,7% | 100,0% | 100,0% | 100,0% | 100,0% | 100,0% |
| PRT wind | 0,0% | 0,0% | 0,5% | 9,5% | 44,0% | 88,4% | 96,1% | 99,1% | 99,7% |
| IND solar | 0,0% | 88,0% | 99,9% | 100,0% | 100,0% | 100,0% | 100,0% | 100,0% | 100,0% |
| IND wind | 0,0% | 0,7% | 12,2% | 31,7% | 50,7% | 75,6% | 89,2% | 97,3% | 98,8% |
| BRA solar | 0,0% | 0,0% | 0,0% | 36,2% | 97,0% | 99,8% | 100,0% | 100,0% | 100,0% |
| BRA wind | 0,0% | 0,0% | 1,2% | 4,7% | 10,3% | 23,5% | 36,9% | 60,5% | 75,8% |

| Par | Capacidade do conjunto (GW) | τ primário | Cap. com LCOE <= τ | τ min / τ max | Cap. com LCOE <= τ min / τ max | IRENA publicado (p5 a p95) | Cap. com LCOE <= publicado |
|---|---|---|---|---|---|---|---|
| PRT solar | 153,3 | 54,53 | 99,34% | 41,00 / 103,00 | 0,00% / 100,00% | 60 (41 a 103) | 100,00% |
| PRT wind | 22,8 | 49,64 | 8,92% | 34,00 / 75,00 | 0,01% / 81,82% | 51 (34 a 75) | 11,91% |
| IND solar | 804,6 | 28,26 | 56,50% | 28,26 / 59,00 | 56,50% / 100,00% | 38 (32 a 59) | 99,85% |
| IND wind | 214,1 | 36,43 | 6,34% | 36,43 / 53,00 | 6,34% / 37,64% | 48 (43 a 53) | 27,90% |
| BRA solar | 16.457,9 | 43,97 | 0,08% | 36,00 / 77,00 | 0,00% / 99,65% | 48 (36 a 77) | 16,13% |
| BRA wind | 1.951,3 | 31,95 | 0,10% | 24,00 / 37,00 | 0,00% / 0,62% | 30 (24 a 37) | 0,04% |

## 6. Item 5: H5, de onde vem E_0 e qual τ daria H_0 = 0

O H5 tem meta registrada em três pares (solar da Índia, eólica da Índia, solar do Brasil). `H_0 = E_0 - G` (M-F7-07). E_0 é a energia (membro m0) das células do domínio econômico (LCOE nominal <= τ, conjunto F7, cenário central). Para metas em GW, `G = 8,76 x G_cap x CFbar`, com CFbar o CF de referência ponderado pela capacidade das células de menor LCOE até somar G_cap (última célula fracionada; meta acima do domínio usa o domínio todo). "τ*" é o menor LCOE de célula tal que o domínio das células com LCOE <= τ* dá H_0 >= 0 (o domínio só muda nos valores de LCOE das células). As colunas "calculado" são do script e batem com as do F7.

| Par | τ primário | Células no domínio | Capacidade do domínio (GW) | E_0 (TWh) | Meta | G (TWh) | H_0 calculado | H_0 do F7 | Estado no F7 |
|---|---|---|---|---|---|---|---|---|---|
| IND solar | 28,26 | 29.914 | 454,6 | 771,67 | 447 GW | 759,38 | 12,29 | 12,29 | tested |
| IND wind | 36,43 | 2.734 | 13,6 | 36,94 | 138 GW | 375,48 | -338,54 | -338,54 | target_not_met_at_reference |
| BRA solar | 43,97 | 89 | 12,3 | 22,30 | 90 GW | 162,58 | -140,28 | -140,28 | target_not_met_at_reference |

| Par | τ primário | τ* (H_0 = 0) | τ* contra o primário | Células em τ* | Capacidade em τ* (GW) | E_0 em τ* | G em τ* | Faixa registrada | IRENA publicado |
|---|---|---|---|---|---|---|---|---|---|
| IND solar | 28,26 | 28,22 | -0,13% | 29.099 | 447,0 | 759,38 | 759,38 | 28,26 a 59,00 | 38 |
| IND wind | 36,43 | 68,95 | 89,25% | 35.093 | 138,0 | 257,25 | 257,24 | 36,43 a 53,00 | 48 |
| BRA solar | 43,97 | 44,83 | 1,95% | 554 | 90,1 | 160,41 | 160,31 | 36,00 a 77,00 | 48 |

Variantes de τ já calculadas pelo F7 nesses pares (`h5_summary`, `D1_dados/D1_5_h5_variantes_f7.csv`):

| Par | Variante | τ | Estado | Células | Capacidade (GW) | E_0 | G | H_0 |
|---|---|---|---|---|---|---|---|---|
| IND solar | primary | 28,26 | tested | 29.914 | 454,6 | 771,67 | 759,38 | 12,29 |
| IND solar | tau_min | 28,26 | tested | 29.914 | 454,6 | 771,67 | 759,38 | 12,29 |
| IND solar | tau_max | 59,00 | tested | 93.483 | 804,6 | 1.328,91 | 759,38 | 569,54 |
| IND wind | primary | 36,43 | target_not_met_at_reference | 2.734 | 13,6 | 36,94 | 375,48 | -338,54 |
| IND wind | tau_min | 36,43 | target_not_met_at_reference | 2.734 | 13,6 | 36,94 | 375,48 | -338,54 |
| IND wind | tau_max | 53,00 | target_not_met_at_reference | 18.263 | 80,6 | 171,76 | 294,14 | -122,38 |
| BRA solar | primary | 43,97 | target_not_met_at_reference | 89 | 12,3 | 22,30 | 162,58 | -140,28 |
| BRA solar | tau_min | 36,00 | target_not_met_at_reference | 0 | 0,0 | 0,00 | não disponível | não disponível |
| BRA solar | tau_max | 77,00 | tested | 185.410 | 16.399,9 | 26.608,87 | 160,31 | 26.448,56 |

Em BRA solar, `tau_min` (36,00) deixa o domínio com 0 células: `G` e `H_0` não existem. Na solar e na eólica da Índia `tau_min` coincide com o primário, porque a faixa foi estendida para baixo até ele (DEC-089 a).

## 7. O que os achados dizem sobre as leituras da seção 1 do arquivo de comandos

Só o que os números mostram; a classificação em A, B, C ou D fica para o D0.

- **Item 1, "o domínio econômico quase some no BRA":** confirmado. 0,075% da capacidade solar e 0,103% da eólica têm LCOE <= τ (89 e 137 células).
- **"O τ foi calibrado com o CF de 53%":** confirmado e quantificado: na banda do p10 da eólica do BRA, 96% da diferença para o τ vem do CF das células (0,268 contra 0,53).
- **"O SR é provavelmente zero em quase todas as células desses pares":** vale para a eólica do BRA e da Índia; não vale para a solar do BRA, em que o SR é positivo em 96,3% das células mesmo com 0,075% da capacidade abaixo do τ no cenário nominal.
- **"O satisficing não discrimina":** na eólica de BRA e IND o SR é zero em 83,4% e 79,7% das células. Nos outros quatro pares ele é quase monótono no LCOE nominal (ver 4).
- **Base comum entre τ e LCOE das células (pergunta do comando):** o capex coincide com o TIC do IRENA e a taxa é a mesma; a vida útil (25 contra 30 anos) e o O&M (quatro pares) diferem e baixam o LCOE das células em relação à base do τ; o CF é o termo que mais separa o τ do p10 das células na eólica do BRA e da Índia; na banda do p10 a conexão soma de 0,92 a 2,76 USD/MWh e a degradação, que não entra no τ (L-247), soma de 0,84 a 4,29.

## 8. Origem dos números

| Número | Origem |
|---|---|
| LCOE nominal por célula, m0 | `outputs/<ISO>/lcoe_modeling/artifacts/lcoe_summary_<tec>.parquet`, recalculado com `geofrea.lcoe_modeling.kernel.lcoe_block` |
| P_MW, CF, E_MWh | `outputs/<ISO>/technical_potential/artifacts/potential_<tec>__central.parquet`, membro m0 |
| distâncias, zona térmica | `outputs/<ISO>/land_eligibility/artifacts/candidates_<tec>__central.parquet` |
| dT do membro | `outputs/<ISO>/climate_forcing/artifacts/forcing.parquet` |
| amostra nominal | `build_design` com `sampler.seed` e `sampler.adopted_size` de `config/experiments.yaml` (linha 0) |
| τ, faixa | `config/parameters.json`, `tau_lcoe_usd_per_mwh` |
| TIC, O&M, CF, LCOE publicado, vida de 25 anos | `config/irena_reference.yaml`, edição `irena_rpgc_2024` |
| MR, SR, classe da célula | `outputs/<ISO>/robustness_analysis/artifacts/robustness_<tec>__core.parquet` |
| meta, estado e H_0 do F7 | `outputs/<ISO>/robustness_analysis/artifacts/h5_summary_<tec>__core.parquet` |

## 9. Limites deste diagnóstico

- A decomposição é sequencial: a divisão entre energia e custos de capital depende da ordem dos passos.
- "Células" são as do conjunto F7 no cenário central; células de classes sem MR e SR (por exemplo `incomplete_ensemble` na eólica do BRA, 7.104) não entram nas tabelas de SR e nas demais.
- O CF de referência do IRENA da solar de PT é um proxy regional (L-242).
- O diagnóstico não verifica se o CF das células eólicas está correto (OQ-114); ele só mostra o quanto da diferença vem dele.

## 10. Manifestos e referências no momento da geração

Manifestos comparados com o instantâneo (SHA-256): 8 de 8 iguais.
Tag `v1.0` aponta para `107d1b8` e o objeto da tag `prereg-v1` é `685a29cc`, como registrados.
