# Resultados exploratórios da v1.1: H5c, vulnerabilidade própria, V_f e τ na base das células

Escrito para: o autor, para levar ao chat de planejamento. Repositório com a fase `exploratory_analysis` (DEC-098, COMANDOS 210 a 212; conversão da meta corrigida pela DEC-100, COMANDO 213A). Somente leitura: nada foi gravado em `GeoFREA_data/outputs/` nem no repositório. Este texto é gerado por `exploratorio_v1_1/gerar_213.py` a partir dos artefatos; cada número passa por uma função que o grava no livro-razão `ledger_213.json` com o artefato e a coluna de origem, e `conferir_213.py` exige que nenhum número do texto fique fora dele. Os números não foram digitados à mão. O relatório descreve e não interpreta além do que os artefatos mostram.

**Estatuto.** Tudo aqui é exploratório (DEC-098). Os resultados pré-registrados (T-R1 a T-R12, F1 a F7b) não mudaram: a conferência de hashes está no registro do COMANDO 211. Janela principal 2041-2070 (`core`); a janela de sensibilidade existe nos artefatos e não entra neste texto.

## 1. H5c: custo de atingir a meta

MC é o LCOE da célula em que a energia acumulada (da mais barata para a mais cara) atinge o nível G; AC é o LCOE médio das células até G. Níveis: `target` (a meta nacional em GW convertida em TWh/ano **sem τ**, pela DEC-100 do COMANDO 213A: a energia em `m0` das células do conjunto F7 mais baratas em f0 até a capacidade acumulada atingir a meta, com célula fracionária, quando a meta existe em GW) e 5, 10, 25 por cento da energia total do conjunto F7 no membro de referência `m0` (G_p). Delta_MC e Delta_AC são o maior aumento relativo sobre os membros do conjunto central (o membro e o SSP que o atingem), com a mediana entre membros. Base `nominal`: LCOE nos parâmetros nominais; base `p90_envelope`: o P90 por célula e membro (envelope superior, não um sorteio conjunto). O rótulo descritivo só existe no nível `target` da base nominal: Delta_MC de 0,05 ou mais é "material climate pressure on the cost of the target".

- PRT solar: sem meta nacional registrada em GW; só os níveis G_p (`experiments.yaml`, `national_targets.PRT.solar`).
- PRT eólica: sem meta nacional registrada em GW; só os níveis G_p (`experiments.yaml`, `national_targets.PRT.wind`).
- IND solar: meta de 447 GW em 2035.
- IND eólica: meta de 138 GW em 2035.
- BRA solar: meta de 90 GW em 2050.
- BRA eólica: sem meta nacional registrada em GW; só os níveis G_p (`experiments.yaml`, `national_targets.BRA.wind`).

### 1.1 PRT solar

| base | nível | G (TWh/ano) | G / energia total | MC_m0 (USD/MWh) | AC_m0 | Delta_MC máx. | membro (SSP) | Delta_MC mediana | Delta_AC máx. | Delta_AC mediana | membros inalcançáveis | referência inalcançável | rótulo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nominal | G_p p05 | 12,4 | 5,000% | 46,01 | 45,33 | 0,9332% | mri_esm2_0_ssp370 (SSP3-7.0) | -2,4188% | 1,1212% | -2,1552% | 0 | não | — |
| nominal | G_p p10 | 24,7 | 10,000% | 46,60 | 45,81 | 0,8970% | mri_esm2_0_ssp370 (SSP3-7.0) | -2,6185% | 1,0230% | -2,3108% | 0 | não | — |
| nominal | G_p p25 | 61,8 | 25,000% | 47,88 | 46,68 | 0,7374% | mri_esm2_0_ssp370 (SSP3-7.0) | -2,6223% | 0,9244% | -2,4635% | 0 | não | — |
| p90_envelope | G_p p05 | 12,4 | 5,000% | 59,96 | 59,09 | 0,9515% | mri_esm2_0_ssp370 (SSP3-7.0) | -2,4360% | 1,1310% | -2,1551% | 0 | não | — |
| p90_envelope | G_p p10 | 24,7 | 10,000% | 60,63 | 59,69 | 1,0421% | mri_esm2_0_ssp370 (SSP3-7.0) | -2,4895% | 1,0433% | -2,2906% | 0 | não | — |
| p90_envelope | G_p p25 | 61,8 | 25,000% | 62,31 | 60,79 | 0,7866% | mri_esm2_0_ssp370 (SSP3-7.0) | -2,6110% | 0,9440% | -2,4535% | 0 | não | — |

Delta_MC por SSP (base nominal): G_p p05: SSP1-2.6 -0,8702%, SSP3-7.0 0,9332%, SSP5-8.5 -0,1014%; G_p p10: SSP1-2.6 -0,9660%, SSP3-7.0 0,8970%, SSP5-8.5 -0,1297%; G_p p25: SSP1-2.6 -1,1513%, SSP3-7.0 0,7374%, SSP5-8.5 -0,3220%.

### 1.2 PRT eólica

| base | nível | G (TWh/ano) | G / energia total | MC_m0 (USD/MWh) | AC_m0 | Delta_MC máx. | membro (SSP) | Delta_MC mediana | Delta_AC máx. | Delta_AC mediana | membros inalcançáveis | referência inalcançável | rótulo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nominal | G_p p05 | 2,6 | 5,000% | 46,34 | 43,11 | 6,7169% | ipsl_cm6a_lr_ssp370 (SSP3-7.0) | 2,3053% | 6,3304% | 2,1428% | 0 | não | — |
| nominal | G_p p10 | 5,2 | 10,000% | 48,88 | 45,37 | 7,0517% | ipsl_cm6a_lr_ssp370 (SSP3-7.0) | 2,3572% | 6,6981% | 2,2430% | 0 | não | — |
| nominal | G_p p25 | 13,0 | 25,000% | 53,72 | 49,04 | 8,2324% | ipsl_cm6a_lr_ssp370 (SSP3-7.0) | 2,8217% | 7,3780% | 2,4747% | 0 | não | — |
| p90_envelope | G_p p05 | 2,6 | 5,000% | 60,97 | 56,69 | 6,6884% | ipsl_cm6a_lr_ssp370 (SSP3-7.0) | 2,2030% | 6,3302% | 2,1437% | 0 | não | — |
| p90_envelope | G_p p10 | 5,2 | 10,000% | 64,31 | 59,66 | 7,0050% | ipsl_cm6a_lr_ssp370 (SSP3-7.0) | 2,3095% | 6,6988% | 2,2434% | 0 | não | — |
| p90_envelope | G_p p25 | 13,0 | 25,000% | 70,68 | 64,49 | 8,2006% | ipsl_cm6a_lr_ssp370 (SSP3-7.0) | 2,8041% | 7,3789% | 2,4752% | 0 | não | — |

Delta_MC por SSP (base nominal): G_p p05: SSP1-2.6 4,6472%, SSP3-7.0 6,7169%, SSP5-8.5 5,9648%; G_p p10: SSP1-2.6 4,8032%, SSP3-7.0 7,0517%, SSP5-8.5 5,7082%; G_p p25: SSP1-2.6 5,5577%, SSP3-7.0 8,2324%, SSP5-8.5 6,4367%.

### 1.3 IND solar

| base | nível | G (TWh/ano) | G / energia total | MC_m0 (USD/MWh) | AC_m0 | Delta_MC máx. | membro (SSP) | Delta_MC mediana | Delta_AC máx. | Delta_AC mediana | membros inalcançáveis | referência inalcançável | rótulo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nominal | target | 759,4 | 57,142% | 28,22 | 26,76 | 7,8173% | gfdl_esm4_ssp370 (SSP3-7.0) | 2,1175% | 6,8006% | 2,1363% | 0 | não | material climate pressure on the cost of the target |
| nominal | G_p p05 | 66,4 | 5,000% | 25,42 | 25,13 | 5,7264% | gfdl_esm4_ssp370 (SSP3-7.0) | 2,0356% | 5,4470% | 1,9358% | 0 | não | — |
| nominal | G_p p10 | 132,9 | 10,000% | 25,77 | 25,36 | 6,0632% | gfdl_esm4_ssp370 (SSP3-7.0) | 2,1544% | 5,6916% | 2,0264% | 0 | não | — |
| nominal | G_p p25 | 332,2 | 25,000% | 26,61 | 25,86 | 6,5838% | gfdl_esm4_ssp370 (SSP3-7.0) | 2,2064% | 6,1099% | 2,1422% | 0 | não | — |
| p90_envelope | target | 759,4 | 57,142% | 37,04 | 35,14 | 7,7852% | gfdl_esm4_ssp370 (SSP3-7.0) | 2,1040% | 6,7679% | 2,1309% | 0 | não | — |
| p90_envelope | G_p p05 | 66,4 | 5,000% | 33,44 | 33,08 | 5,6873% | gfdl_esm4_ssp370 (SSP3-7.0) | 2,0058% | 5,4215% | 1,9214% | 0 | não | — |
| p90_envelope | G_p p10 | 132,9 | 10,000% | 33,88 | 33,37 | 6,0439% | gfdl_esm4_ssp370 (SSP3-7.0) | 2,1570% | 5,6635% | 2,0122% | 0 | não | — |
| p90_envelope | G_p p25 | 332,2 | 25,000% | 34,92 | 33,99 | 6,6135% | gfdl_esm4_ssp370 (SSP3-7.0) | 2,2532% | 6,0872% | 2,1365% | 0 | não | — |

Delta_MC por SSP (base nominal): target: SSP1-2.6 0,0374%, SSP3-7.0 7,8173%, SSP5-8.5 4,1255%; G_p p05: SSP1-2.6 -0,2399%, SSP3-7.0 5,7264%, SSP5-8.5 3,2208%; G_p p10: SSP1-2.6 -0,1204%, SSP3-7.0 6,0632%, SSP5-8.5 3,1870%; G_p p25: SSP1-2.6 -0,0212%, SSP3-7.0 6,5838%, SSP5-8.5 3,3448%.

### 1.4 IND eólica

| base | nível | G (TWh/ano) | G / energia total | MC_m0 (USD/MWh) | AC_m0 | Delta_MC máx. | membro (SSP) | Delta_MC mediana | Delta_AC máx. | Delta_AC mediana | membros inalcançáveis | referência inalcançável | rótulo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nominal | target | 257,2 | 77,596% | 68,95 | 48,00 | 18,9843% | ipsl_cm6a_lr_ssp126 (SSP1-2.6) | 3,1697% | 11,1873% | 1,7996% | 0 | não | material climate pressure on the cost of the target |
| nominal | G_p p05 | 16,6 | 5,000% | 33,15 | 30,64 | 8,4373% | ipsl_cm6a_lr_ssp126 (SSP1-2.6) | 0,0682% | 7,6003% | 0,4431% | 0 | não | — |
| nominal | G_p p10 | 33,2 | 10,000% | 35,91 | 32,60 | 7,9408% | ipsl_cm6a_lr_ssp126 (SSP1-2.6) | -0,3576% | 7,9314% | -0,0043% | 0 | não | — |
| nominal | G_p p25 | 82,9 | 25,000% | 41,80 | 36,45 | 8,3684% | ipsl_cm6a_lr_ssp126 (SSP1-2.6) | 0,9194% | 8,1069% | 0,2453% | 0 | não | — |
| p90_envelope | target | 257,2 | 77,596% | 88,29 | 61,47 | 18,9745% | ipsl_cm6a_lr_ssp126 (SSP1-2.6) | 3,1587% | 11,1878% | 1,7996% | 0 | não | — |
| p90_envelope | G_p p05 | 16,6 | 5,000% | 42,45 | 39,23 | 8,4177% | ipsl_cm6a_lr_ssp126 (SSP1-2.6) | 0,0138% | 7,5996% | 0,4438% | 0 | não | — |
| p90_envelope | G_p p10 | 33,2 | 10,000% | 45,98 | 41,74 | 7,9344% | ipsl_cm6a_lr_ssp126 (SSP1-2.6) | -0,3647% | 7,9289% | -0,0050% | 0 | não | — |
| p90_envelope | G_p p25 | 82,9 | 25,000% | 53,52 | 46,67 | 8,3701% | ipsl_cm6a_lr_ssp126 (SSP1-2.6) | 0,9105% | 8,1057% | 0,2471% | 0 | não | — |

Delta_MC por SSP (base nominal): target: SSP1-2.6 18,9843%, SSP3-7.0 9,8350%, SSP5-8.5 13,7187%; G_p p05: SSP1-2.6 8,4373%, SSP3-7.0 2,7270%, SSP5-8.5 5,5950%; G_p p10: SSP1-2.6 7,9408%, SSP3-7.0 2,8216%, SSP5-8.5 5,0635%; G_p p25: SSP1-2.6 8,3684%, SSP3-7.0 2,9135%, SSP5-8.5 4,9902%.

### 1.5 BRA solar

| base | nível | G (TWh/ano) | G / energia total | MC_m0 (USD/MWh) | AC_m0 | Delta_MC máx. | membro (SSP) | Delta_MC mediana | Delta_AC máx. | Delta_AC mediana | membros inalcançáveis | referência inalcançável | rótulo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nominal | target | 160,3 | 0,601% | 44,83 | 44,38 | 2,2045% | mri_esm2_0_ssp370 (SSP3-7.0) | -0,5680% | 2,2092% | -0,5430% | 0 | não | no material climate pressure on the cost of the target |
| nominal | G_p p05 | 1.334,7 | 5,000% | 46,36 | 45,59 | 2,0186% | mri_esm2_0_ssp370 (SSP3-7.0) | -0,6154% | 2,1116% | -0,5880% | 0 | não | — |
| nominal | G_p p10 | 2.669,3 | 10,000% | 47,18 | 46,19 | 1,9830% | mri_esm2_0_ssp370 (SSP3-7.0) | -0,5793% | 2,0525% | -0,5864% | 0 | não | — |
| nominal | G_p p25 | 6.673,4 | 25,000% | 48,79 | 47,29 | 2,1152% | mri_esm2_0_ssp370 (SSP3-7.0) | -0,3903% | 2,0456% | -0,5468% | 0 | não | — |
| p90_envelope | target | 160,3 | 0,601% | 56,95 | 56,38 | 2,2082% | mri_esm2_0_ssp370 (SSP3-7.0) | -0,5780% | 2,2301% | -0,5286% | 0 | não | — |
| p90_envelope | G_p p05 | 1.334,7 | 5,000% | 58,82 | 57,87 | 2,0334% | mri_esm2_0_ssp370 (SSP3-7.0) | -0,6136% | 2,1172% | -0,5951% | 0 | não | — |
| p90_envelope | G_p p10 | 2.669,3 | 10,000% | 59,84 | 58,62 | 1,9928% | mri_esm2_0_ssp370 (SSP3-7.0) | -0,5891% | 2,0577% | -0,5875% | 0 | não | — |
| p90_envelope | G_p p25 | 6.673,4 | 25,000% | 61,81 | 59,97 | 2,1180% | mri_esm2_0_ssp370 (SSP3-7.0) | -0,3639% | 2,0436% | -0,5433% | 0 | não | — |

Delta_MC por SSP (base nominal): target: SSP1-2.6 0,1678%, SSP3-7.0 2,2045%, SSP5-8.5 0,8945%; G_p p05: SSP1-2.6 0,0693%, SSP3-7.0 2,0186%, SSP5-8.5 0,6962%; G_p p10: SSP1-2.6 0,0396%, SSP3-7.0 1,9830%, SSP5-8.5 0,6469%; G_p p25: SSP1-2.6 -0,0001%, SSP3-7.0 2,1152%, SSP5-8.5 0,6554%.

### 1.6 BRA eólica

| base | nível | G (TWh/ano) | G / energia total | MC_m0 (USD/MWh) | AC_m0 | Delta_MC máx. | membro (SSP) | Delta_MC mediana | Delta_AC máx. | Delta_AC mediana | membros inalcançáveis | referência inalcançável | rótulo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nominal | G_p p05 | 134,0 | 5,000% | 41,94 | 37,41 | 3,2611% | mri_esm2_0_ssp370 (SSP3-7.0) | -5,4117% | 3,0471% | -4,1701% | 0 | não | — |
| nominal | G_p p10 | 268,0 | 10,000% | 47,92 | 41,24 | 3,0707% | mri_esm2_0_ssp370 (SSP3-7.0) | -6,9095% | 3,1123% | -5,8989% | 0 | não | — |
| nominal | G_p p25 | 670,1 | 25,000% | 62,05 | 49,50 | 2,4342% | mri_esm2_0_ssp370 (SSP3-7.0) | -9,3686% | 2,8727% | -7,3921% | 0 | não | — |
| p90_envelope | G_p p05 | 134,0 | 5,000% | 49,77 | 44,40 | 3,2334% | mri_esm2_0_ssp370 (SSP3-7.0) | -5,4244% | 3,0459% | -4,1690% | 0 | não | — |
| p90_envelope | G_p p10 | 268,0 | 10,000% | 56,86 | 48,93 | 3,0553% | mri_esm2_0_ssp370 (SSP3-7.0) | -6,9069% | 3,1129% | -5,8952% | 0 | não | — |
| p90_envelope | G_p p25 | 670,1 | 25,000% | 73,62 | 58,73 | 2,4261% | mri_esm2_0_ssp370 (SSP3-7.0) | -9,3533% | 2,8731% | -7,3956% | 0 | não | — |

Delta_MC por SSP (base nominal): G_p p05: SSP1-2.6 0,1652%, SSP3-7.0 3,2611%, SSP5-8.5 -0,1907%; G_p p10: SSP1-2.6 -0,1908%, SSP3-7.0 3,0707%, SSP5-8.5 -0,7681%; G_p p25: SSP1-2.6 -0,9220%, SSP3-7.0 2,4342%, SSP5-8.5 -2,5791%.

### 1.7 A conversão da meta: nova (sem τ) e antiga (regra do H5), lado a lado

A conversão do H5 usa o CF das células do domínio econômico (depende de τ); quando a meta passa da capacidade desse domínio, o CF das melhores células é estendido à meta inteira. A nova (DEC-100) não usa τ. As colunas `antiga` são recalculadas aqui com o mesmo código do H5c e G = `g_target_h5_twh` (a conversão do H5, gravada nos artefatos só para comparação); as `nova` são as linhas gravadas.

| par | meta (GW) | capacidade do conjunto F7 (GW) | capacidade de Omega_econ (GW) | energia do conjunto F7 em m0 (TWh/ano) | G antiga | antiga / energia total | G nova | nova / energia total | meta acima do conjunto | MC_m0 antiga | MC_m0 nova | Delta_MC antiga | Delta_MC nova | rótulo antigo | rótulo novo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| IND solar | 447 | 804,6 | 454,6 | 1.328,9 | 759,4 | 57,142% | 759,4 | 57,142% | não | 28,22 | 28,22 | 7,8173% | 7,8173% | material climate pressure on the cost of the target | material climate pressure on the cost of the target |
| IND eólica | 138 | 214,1 | 13,6 | 331,5 | 375,5 | 113,261% | 257,2 | 77,596% | não | n/d | 68,95 | n/d | 18,9843% | target level not reached by the reference member | material climate pressure on the cost of the target |
| BRA solar | 90 | 16.457,9 | 12,3 | 26.693,4 | 162,6 | 0,609% | 160,3 | 0,601% | não | 44,83 | 44,83 | 2,2052% | 2,2045% | no material climate pressure on the cost of the target | no material climate pressure on the cost of the target |

## 2. Vulnerabilidade própria (VUL)

`VUL_clim` é o maior aumento relativo do LCOE da célula sobre os membros do conjunto central, nos parâmetros nominais; `VUL_tec`, o P90 sobre os sorteios no membro de referência contra o LCOE em f0; `VUL`, o máximo sobre os membros do P90 sobre os sorteios. O membro `m0` não está entre os membros do conjunto central, então `VUL_clim` pode ser negativo (L-264): uma célula cujo LCOE cai em todos os membros futuros. As células `climate_fragile` não têm valor e são contadas à parte.

### 2.1 PRT solar

| índice | células | mín. | p10 | p25 | mediana | p75 | p90 | máx. | média |
|---|---|---|---|---|---|---|---|---|---|
| VUL_clim | 3.414 | -2,5595% | -1,6368% | -0,7480% | 0,2918% | 0,8685% | 1,2219% | 1,5691% | 0,0046% |
| VUL_tec | 3.414 | 29,3191% | 29,5517% | 30,1253% | 30,2864% | 30,4497% | 30,4872% | 30,6618% | 30,2027% |
| VUL | 3.414 | 26,6433% | 28,2127% | 29,3068% | 30,5788% | 31,0773% | 31,6670% | 32,5654% | 30,2110% |

- Células com `VUL_clim` negativo: 1.401 de 3.414 com valor. Células `climate_fragile`: 0, com 0,0 MW.
- Spearman de `VUL_clim` com o LCOE em f0: -0,618; com MR: -0,351. `VUL_tec` com LCOE: -0,140; com MR: -0,394. `VUL` com LCOE: -0,684; com MR: -0,463.
- Parcela do top-k nominal (342 células) no quartil superior de `VUL_clim` (corte 0,8685%): 74,0%.
- Capacidade por quadrante (LCOE em f0 e `VUL_clim` contra suas medianas, 50,38 USD/MWh e 0,2918%), em GW: LCOE baixo, VUL baixo 14,2 (9,2%); LCOE baixo, VUL alto 85,4 (55,7%); LCOE alto, VUL baixo 21,8 (14,2%); LCOE alto, VUL alto 31,9 (20,8%).

### 2.2 PRT eólica

| índice | células | mín. | p10 | p25 | mediana | p75 | p90 | máx. | média |
|---|---|---|---|---|---|---|---|---|---|
| VUL_clim | 3.332 | 3,6000% | 6,2140% | 7,1520% | 7,9024% | 8,5096% | 9,2305% | 13,7295% | 7,8451% |
| VUL_tec | 3.332 | 31,3782% | 31,4407% | 31,4805% | 31,5187% | 31,5419% | 31,5555% | 31,5684% | 31,5080% |
| VUL | 3.332 | 36,2601% | 39,6765% | 40,9068% | 41,9005% | 42,6936% | 43,6509% | 49,4814% | 41,8250% |

- Células com `VUL_clim` negativo: 0 de 3.332 com valor. Células `climate_fragile`: 0, com 0,0 MW.
- Spearman de `VUL_clim` com o LCOE em f0: 0,690; com MR: 0,708. `VUL_tec` com LCOE: 0,023; com MR: 0,024. `VUL` com LCOE: 0,690; com MR: 0,709.
- Parcela do top-k nominal (334 células) no quartil superior de `VUL_clim` (corte 8,5096%): 0,0%.
- Capacidade por quadrante (LCOE em f0 e `VUL_clim` contra suas medianas, 63,65 USD/MWh e 7,9024%), em GW: LCOE baixo, VUL baixo 8,9 (38,9%); LCOE baixo, VUL alto 3,7 (16,1%); LCOE alto, VUL baixo 1,8 (8,1%); LCOE alto, VUL alto 8,4 (36,9%).

### 2.3 IND solar

| índice | células | mín. | p10 | p25 | mediana | p75 | p90 | máx. | média |
|---|---|---|---|---|---|---|---|---|---|
| VUL_clim | 93.159 | 4,0468% | 5,8168% | 7,1881% | 8,1499% | 8,7887% | 9,9405% | 16,7249% | 8,0797% |
| VUL_tec | 93.159 | 27,9961% | 30,7067% | 31,0950% | 31,2659% | 31,5085% | 31,6624% | 33,3985% | 31,2445% |
| VUL | 93.159 | 35,3111% | 38,8975% | 40,6636% | 41,9074% | 42,7447% | 44,3404% | 53,4019% | 41,8486% |

- Células com `VUL_clim` negativo: 0 de 93.159 com valor. Células `climate_fragile`: 331, com 29,3 MW.
- Spearman de `VUL_clim` com o LCOE em f0: 0,322; com MR: 0,430. `VUL_tec` com LCOE: -0,522; com MR: -0,503. `VUL` com LCOE: 0,173; com MR: 0,281.
- Parcela do top-k nominal (9.349 células) no quartil superior de `VUL_clim` (corte 8,7887%): 0,2%.
- Capacidade por quadrante (LCOE em f0 e `VUL_clim` contra suas medianas, 29,02 USD/MWh e 8,1499%), em GW: LCOE baixo, VUL baixo 453,8 (56,4%); LCOE baixo, VUL alto 132,6 (16,5%); LCOE alto, VUL baixo 113,5 (14,1%); LCOE alto, VUL alto 104,6 (13,0%).

### 2.4 IND eólica

| índice | células | mín. | p10 | p25 | mediana | p75 | p90 | máx. | média |
|---|---|---|---|---|---|---|---|---|---|
| VUL_clim | 75.535 | 2,1993% | 6,7678% | 8,7201% | 11,5527% | 15,4543% | 18,5757% | 318,7327% | 12,6841% |
| VUL_tec | 75.535 | 27,9679% | 27,9749% | 27,9955% | 28,0426% | 28,0848% | 28,1293% | 28,4595% | 28,0477% |
| VUL | 75.535 | 30,9026% | 36,7312% | 39,2107% | 42,8478% | 47,8376% | 51,8322% | 437,1643% | 44,2895% |

- Células com `VUL_clim` negativo: 0 de 75.535 com valor. Células `climate_fragile`: 0, com 0,0 MW.
- Spearman de `VUL_clim` com o LCOE em f0: 0,239; com MR: 0,304. `VUL_tec` com LCOE: 0,206; com MR: 0,202. `VUL` com LCOE: 0,241; com MR: 0,306.
- Parcela do top-k nominal (7.554 células) no quartil superior de `VUL_clim` (corte 15,4543%): 1,0%.
- Capacidade por quadrante (LCOE em f0 e `VUL_clim` contra suas medianas, 71,79 USD/MWh e 11,5527%), em GW: LCOE baixo, VUL baixo 80,3 (37,5%); LCOE baixo, VUL alto 64,8 (30,3%); LCOE alto, VUL baixo 28,2 (13,2%); LCOE alto, VUL alto 40,8 (19,0%).

### 2.5 BRA solar

| índice | células | mín. | p10 | p25 | mediana | p75 | p90 | máx. | média |
|---|---|---|---|---|---|---|---|---|---|
| VUL_clim | 190.001 | -0,0766% | 0,8669% | 1,4923% | 1,9758% | 2,7658% | 3,9192% | 5,6056% | 2,2080% |
| VUL_tec | 190.001 | 20,0297% | 25,2848% | 26,2301% | 26,6884% | 26,9579% | 27,2266% | 27,9822% | 26,4100% |
| VUL | 190.001 | 20,0101% | 27,1295% | 28,3343% | 29,1641% | 30,3189% | 31,5930% | 35,0013% | 29,2028% |

- Células com `VUL_clim` negativo: 14 de 190.001 com valor. Células `climate_fragile`: 0, com 0,0 MW.
- Spearman de `VUL_clim` com o LCOE em f0: -0,047; com MR: 0,016. `VUL_tec` com LCOE: -0,484; com MR: -0,507. `VUL` com LCOE: -0,230; com MR: -0,185.
- Parcela do top-k nominal (19.001 células) no quartil superior de `VUL_clim` (corte 2,7658%): 15,8%.
- Capacidade por quadrante (LCOE em f0 e `VUL_clim` contra suas medianas, 52,30 USD/MWh e 1,9758%), em GW: LCOE baixo, VUL baixo 4.401,1 (26,7%); LCOE baixo, VUL alto 5.444,6 (33,1%); LCOE alto, VUL baixo 2.799,8 (17,0%); LCOE alto, VUL alto 3.812,4 (23,2%).

### 2.6 BRA eólica

| índice | células | mín. | p10 | p25 | mediana | p75 | p90 | máx. | média |
|---|---|---|---|---|---|---|---|---|---|
| VUL_clim | 171.181 | -8,6283% | -1,9179% | -0,2170% | 2,1538% | 5,1621% | 8,9414% | 75,5855% | 3,0295% |
| VUL_tec | 171.181 | 17,5875% | 18,4391% | 18,5655% | 18,6739% | 18,6918% | 18,7081% | 18,7178% | 18,6075% |
| VUL | 171.181 | 8,3047% | 16,3467% | 18,4056% | 21,1867% | 24,7259% | 29,1256% | 107,7500% | 22,1987% |

- Células com `VUL_clim` negativo: 46.934 de 171.181 com valor. Células `climate_fragile`: 0, com 0,0 MW.
- Spearman de `VUL_clim` com o LCOE em f0: 0,217; com MR: 0,253. `VUL_tec` com LCOE: -0,287; com MR: -0,297. `VUL` com LCOE: 0,212; com MR: 0,248.
- Parcela do top-k nominal (17.119 células) no quartil superior de `VUL_clim` (corte 5,1621%): 8,9%.
- Capacidade por quadrante (LCOE em f0 e `VUL_clim` contra suas medianas, 144,37 USD/MWh e 2,1538%), em GW: LCOE baixo, VUL baixo 586,7 (30,1%); LCOE baixo, VUL alto 553,8 (28,4%); LCOE alto, VUL baixo 354,8 (18,2%); LCOE alto, VUL alto 455,9 (23,4%).

## 3. V_f: distância ao limiar do PRIM

`V_f` é a parcela da capacidade deslocada em cada futuro (membro e sorteio), de `futures.displaced_capacity_share` da F7. O limiar do PRIM é `prim.outcome_threshold` = 0,20. A tabela dá a distribuição de `V_f` sobre os futuros, o número de futuros com `V_f` de pelo menos o limiar e a distância do máximo ao limiar.

| par | futuros | mediana | p95 | p99 | máximo | limiar | futuros com V_f ≥ limiar | limiar − máximo (pontos) | máximo / limiar |
|---|---|---|---|---|---|---|---|---|---|
| PRT solar | 72.018 | 0,0000% | 1,011% | 1,989% | 3,002% | 0,20 | 0 | 16,998% | 0,150 |
| PRT eólica | 60.015 | 0,0000% | 0,000% | 0,000% | 0,000% | 0,20 | 0 | 20,000% | 0,000 |
| IND solar | 72.018 | 0,0000% | 0,513% | 0,788% | 1,029% | 0,20 | 0 | 18,971% | 0,051 |
| IND eólica | 60.015 | 0,0000% | 0,000% | 0,000% | 0,000% | 0,20 | 0 | 20,000% | 0,000 |
| BRA solar | 72.018 | 0,0000% | 2,137% | 3,067% | 4,215% | 0,20 | 0 | 15,785% | 0,211 |
| BRA eólica | 60.015 | 0,0000% | 3,004% | 3,432% | 3,898% | 0,20 | 0 | 16,102% | 0,195 |

## 4. τ na base das células

τ é o LCOE da usina de referência da IRENA (TIC, fator de capacidade e taxa central da referência). `τ registrado` é o valor da configuração; `τ referência` é recalculado da usina como a IRENA a descreve (confere o registrado); `τ base das células` usa a vida útil e o O&M que a F6 aplica às células (O&M = `opex_fixed_frac` × capex nominal da F6); `só vida` e `só O&M` mudam um dos dois termos. A capacidade abaixo de cada τ é a do conjunto F7 (células `ranked` e `climate_fragile`) com LCOE em f0 menor ou igual a τ.

| par | τ registrado | τ referência | só vida | só O&M | τ base das células | diferença | células F7 | células abaixo do registrado | GW abaixo do registrado | células abaixo da base das células | GW abaixo da base das células | GW do conjunto F7 | GW da base das células / GW do registrado |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PRT solar | 54,53 | 54,532 | 50,90 | 53,58 | 49,94 | -8,4% | 3.414 | 3.258 | 152,3 | 1.459 | 87,1 | 153,3 | 57,2% |
| PRT eólica | 49,64 | 49,643 | 46,16 | 48,30 | 44,81 | -9,7% | 3.332 | 422 | 2,0 | 158 | 0,5 | 22,8 | 24,6% |
| IND solar | 28,26 | 28,257 | 26,20 | 27,01 | 24,95 | -11,7% | 93.490 | 29.914 | 454,6 | 434 | 7,0 | 804,6 | 1,5% |
| IND eólica | 36,43 | 36,435 | 33,71 | 36,43 | 33,70 | -7,5% | 75.535 | 2.734 | 13,6 | 1.462 | 6,9 | 214,1 | 50,5% |
| BRA solar | 43,97 | 43,975 | 41,92 | 42,85 | 40,80 | -7,2% | 190.001 | 89 | 12,3 | 0 | 0,0 | 16.457,9 | 0,0% |
| BRA eólica | 31,95 | 31,945 | 30,55 | 31,95 | 30,55 | -4,4% | 171.181 | 137 | 2,0 | 66 | 1,0 | 1.951,3 | 49,6% |

Entradas do cálculo (USD/kW; USD/kW/ano; anos):

| par | TIC | capex F6 | fator de capacidade | taxa | vida IRENA | vida F6 | O&M IRENA | O&M F6 | opex_fixed_frac |
|---|---|---|---|---|---|---|---|---|---|
| PRT solar | 779 | 779 | 0,150 | 4,200% | 25 | 30 | 20,73 | 19,48 | 2,500% |
| PRT eólica | 1.659 | 1.659 | 0,340 | 3,700% | 25 | 30 | 45,00 | 41,00 | 2,471% |
| IND solar | 525 | 525 | 0,180 | 4,000% | 25 | 30 | 10,95 | 8,98 | 1,710% |
| IND eólica | 1.110 | 1.110 | 0,290 | 3,800% | 25 | 30 | 23,00 | 22,98 | 2,070% |
| BRA solar | 724 | 724 | 0,200 | 7,700% | 25 | 30 | 10,95 | 8,98 | 1,240% |
| BRA eólica | 1.307 | 1.307 | 0,530 | 7,700% | 25 | 30 | 29,00 | 29,02 | 2,220% |

## 5. F7b: primária contra `exact_location_only`

A primária (`operating`) usa todas as unidades em operação do GEM; a variante (`exact_location_only`, D-F7b-010) só as de localização exata. Parcela excluída combinada (média ponderada pela capacidade), parcela da capacidade com parcela excluída de pelo menos meia (`share_at_least_half`), razão de enriquecimento nos três decis de menor LCOE e parcela da capacidade fora de células candidatas.

| par | conjunto | unidades | MW | unidades avaliadas | parcela excluída média | capacidade com parcela ≥ 50% | enriquecimento (3 decis) | capacidade fora de candidatas |
|---|---|---|---|---|---|---|---|---|
| PRT solar | primária | 169 | 3.532 | 168 | 0,739 | 83,552% | 2,64 | 2,350% |
| PRT solar | variante | 165 | 3.453 | 164 | 0,745 | 84,596% | 2,64 | 2,404% |
| PRT eólica | primária | 361 | 5.730 | 361 | 0,747 | 79,531% | 2,42 | 19,858% |
| PRT eólica | variante | 359 | 5.700 | 359 | 0,746 | 79,423% | 2,43 | 19,963% |
| IND solar | primária | 3.727 | 99.280 | 3.724 | 0,769 | 80,231% | 1,58 | 10,897% |
| IND solar | variante | 3.290 | 52.817 | 3.287 | 0,736 | 79,838% | 1,39 | 3,627% |
| IND eólica | primária | 679 | 38.937 | 679 | 0,837 | 83,557% | 2,62 | 24,920% |
| IND eólica | variante | 58 | 3.653 | 58 | 0,535 | 54,699% | 3,05 | 7,392% |
| BRA solar | primária | 3.947 | 24.897 | 3.946 | 0,513 | 48,747% | 3,06 | 4,726% |
| BRA solar | variante | 601 | 19.775 | 601 | 0,409 | 36,951% | 3,31 | 4,375% |
| BRA eólica | primária | 1.144 | 36.042 | 1.135 | 0,332 | 28,839% | 3,33 | 9,827% |
| BRA eólica | variante | 1.138 | 35.701 | 1.129 | 0,332 | 28,698% | 3,33 | 9,922% |

## 6. O que os números mostram, sem extrapolar

- **H5c no alvo (conversão sem τ).** IND solar: material climate pressure on the cost of the target (Delta_MC 7,82%); IND eólica: material climate pressure on the cost of the target (Delta_MC 18,98%); BRA solar: no material climate pressure on the cost of the target (Delta_MC 2,20%).
- **Efeito da correção da conversão (seção 1.7).** Na IND eólica a meta antiga correspondia a 113,261% da energia do conjunto F7 e a nova corresponde a 77,596%; nenhuma meta nova passa da energia do conjunto.
- **Delta_MC nos níveis G_p e no alvo.** O maior valor entre os seis pares é 18,98% (IND eólica) e o menor dos máximos é 0,93% (PRT solar).
- **Sinal do Spearman de `VUL_clim` com o LCOE.** Negativo em PRT solar (-0,618), BRA solar (-0,047); positivo nos demais pares. O sinal difere entre países e tecnologias.
- **V_f.** O máximo de `V_f` entre os seis pares é 4,215% (BRA solar), contra o limiar de 0,20; futuros com `V_f` de pelo menos o limiar, somados: 0.
- **τ na base das células.** É menor que o τ registrado nos seis pares, de -11,7% a -4,4%, e a capacidade abaixo dele cai em proporção maior que o τ (seção 4).
- **F7b.** A variante muda pouco a parcela excluída em PRT e na BRA eólica e muda muito na IND eólica e na BRA solar, onde a maior parte das unidades tem localização aproximada (seção 5).

Limites desta leitura: números de células e de capacidade são do conjunto F7 (`ranked` e `climate_fragile`) do cenário central de solo; o `VUL_clim` negativo é um resultado e não um erro (L-264); nada aqui entra em T-R1 a T-R12; a janela de sensibilidade e o cenário de escala alternativa não foram lidos neste relatório.

## PARAR

Fim do COMANDO 213. O autor leva este texto ao chat de planejamento. O COMANDO 214 só começa por pedido do autor.
