# D0: síntese do diagnóstico da v1.0 (COMANDO 206)

Escrito para: o autor, para levar ao chat de planejamento. Data: 2026-11-23. Somente leitura: este texto junta os relatórios D1 a D5 (`_notas_geofrea/diagnostico_v1_0/`), não recalcula nada e não propõe valor novo nem mudança. Repositório em `2ae1654`, tags `prereg-v1` e `v1.0` inalteradas. Os números vêm dos relatórios, com a seção de origem na coluna de evidência. Esta síntese foi escrita à mão a partir deles (os D1 a D5 são gerados por script a partir de `D*_dados/`).

## 0. Como ler

**Classes** (as do COMANDO 206):

- **(A)** defeito de código: o código faz algo diferente do que a especificação diz.
- **(B)** propriedade do desenho a declarar: o código faz o que a especificação diz, e o resultado decorre do desenho; a ação é declarar (limite, texto da tese), não rodar de novo.
- **(C)** escolha de calibração ou de limiar a rever: um valor escolhido pelo autor determina o resultado e outro valor daria outro resultado.
- **(D)** efeito do dado de entrada: o resultado carrega uma propriedade do dado (cobertura do solo, coordenada do GEM, camada de vento), não do código nem de um parâmetro.

Onde um achado tem duas faces, ele aparece com duas linhas (por exemplo B e C).

**Custo em horas** (seção 3): tempo de parede a frio, da última rodada de produção, lido de `manifest.json` dos três países (campo `cold_wall_s`), somado em sequência. Não inclui revisão, commit nem o tempo de decidir. Estimativa para uma fase que escala com o número de sorteios ou de células é dita como tal.

**Subconjunto pré-registrado** (`core/preregistration.py`): o digest cobre, por país e tecnologia, `tau_lcoe_usd_per_mwh`, `cf_min`, `top_k_percent`, a faixa de `discount_rate` e três sensibilidades; e, em `experiments.yaml`, `thresholds.regret_quantile`, `prim.outcome_threshold`, `prim.sensitivity`, `hypothesis_rules.H5.sensitivity_lambda`, `windows.sensitivity` e `national_targets`. **Não cobre**, pelos seletores do módulo, γ do H2, o m do H1/H3/H4, os parâmetros de elegibilidade, as camadas de entrada, o tamanho do LHS nem a lista p_k em {5, 10, 20} (essas constantes ficam fixadas pelo commit do registro, segundo o docstring do módulo). Quando digo "toca o subconjunto" é o digest. Se uma mudança fora do digest ainda é desvio do pré-registro é decisão do autor (seção 1 do arquivo de comandos).

## 1. Quadro de achados

| Id | Achado | Classe | Evidência | Hipóteses afetadas |
|---|---|---|---|---|
| N1 | O τ vem da planta de referência do IRENA, com CF de 0,53 na BRA eólica; as células têm CF mediano de 0,118 (percentil 99,9 para o CF de referência). Em quatro dos seis pares o CF de referência cai entre os percentis 91 e 99,9 das células. O domínio econômico (capacidade com LCOE <= τ) é 0,075% na BRA solar, 0,103% na BRA eólica, 6,3% na IND eólica, 8,9% na PRT eólica; na PRT solar é 99,3% | C | D1 §1, §2, §5 | H5, SR/satisficing, potencial econômico |
| N2 | Entre o τ e as células há três diferenças de base: a vida (25 contra 30 anos: de -1,40 a -3,63 USD/MWh nas células), o O&M (difere em 4 pares) e a degradação (fora do τ, L-247). Na eólica da BRA, 96% da diferença na banda do p10 vem do CF, não destes termos | C (menor; mesma raiz de N1) | D1 §1, §3 | H5, SR |
| N3 | SR = 0 em 83,4% das células da BRA eólica e 79,7% da IND eólica: o satisficing não discrimina nesses pares. Na BRA solar o SR é positivo em 96,3% das células apesar de 0,075% da capacidade abaixo de τ | C (derivado de N1) | D1 §1, §4, §7 | SR, H5 |
| N4 | H5 na borda: na IND solar E_0 excede G em 12,3 TWh (1,62% de G) e o menor τ com H_0 >= 0 fica 0,13% abaixo do primário; na BRA solar fica 1,95% acima; com `tau_min` o domínio da BRA solar tem 0 células | B | D1 §1, §6 | H5 |
| N5 | Os parâmetros do LHS que mais pesam (capex, O&M, taxa, vida) deslocam todas as células do país juntas. A interação célula x futuro é de 0,13% a 1,75% da variância de log(LCOE) no eixo clima e de 0,00% a 0,52% no eixo parâmetros. O Spearman do ranking nominal com o de cada futuro tem mínimo de 0,892 | B | D2 §1, §2, §3, §4 | H1b (V_k), H3, H4 |
| N6 | O MR acompanha o LCOE nominal: Spearman de 0,930 a 0,999 e R² de 0,875 a 0,999 da regressão de MR sobre a distância à melhor célula | B | D2 §1, §7 | H3, H1 |
| N7 | Duas medidas de deslocamento dão respostas diferentes: o V_k do F7 (posto do pior regret por SSP) é 0 em cinco pares e 0,0029 na BRA solar; o pior posto entre membros passa de 2k em 0,00% a 3,55% do top-k nominal | B (definição a declarar) | D2 §1, §5, §9 | H1b, H4 |
| N8 | Sensibilidade exploratória com top-k de 1% e m = k/2: V_k vai de 0 a 0,138 (IND solar), abaixo de β = 0,20 em todos os pares; D_clim e D_tec ficam acima de zero em alguns pares | C | D2 §1, §8 | H1b, H3, H4 |
| N9 | O do H2 fica entre 0,320 e 0,510 nos seis pares, acima de γ = 0,30, e O_ref entre 0,064 e 0,247. O é puxado por 1 a 3 regiões Admin1: a maior contribui com 51,6% a 82,1% de O e as três maiores com 89,5% ou mais. Na IND solar duas regiões guardam 97,7% da seleção por célula | B | D3 §1, §3, §5 | H2 |
| N10 | O veredito do H2 muda com γ: em PRT solar, IND eólica e BRA solar muda já em γ = 0,35 (O está a menos de 0,05 de γ); nos outros, entre 0,45 e 0,55. A grade e a partição Admin1 (de 18 a 37 regiões, N efetivo de capacidade de 5,1 a 13,5) são escolhas; o veredito primário não muda com a janela nem com a escala | C | D3 §1, §4, §5 | H2 |
| N11 | E5 artefato posterior à usina (a1) nas solares: a parcela de "construído" (WorldCover 2020) nas usinas de localização exata iniciadas até 2019 contra as de 2021 em diante é 0,100 contra 0,011 na PRT, 0,164 contra 0,019 na IND, 0,048 contra 0,005 na BRA (fundo da PRT: 0,027). Nas eólicas não aparece | D | D4 §2, §6 | elegibilidade e tudo a jusante (F3 a F7b) |
| N12 | E5 por escolha do cenário central (classes que o cenário exclui: lavoura na solar, árvores nas duas tecnologias): E5 exato de 0,23 a 0,56 em PRT solar, PRT eólica, IND solar e BRA solar, com 82% a 95% vindo dessas classes | C | D4 §2, §6 | elegibilidade, potencial, ranking |
| N13 | A localização do GEM é aproximada na maior parte das unidades: na IND eólica só 58 de 679 unidades (9,4% da capacidade) são exatas; na BRA solar 601 de 3.946. A capacidade em pixel de assentamento passa de 64,7% (todas) para 5,9% (exatas) na IND eólica e de 11,3% para 0,5% na BRA solar. O filtro `excluded_location_accuracy` do F7b está nulo | D | D4 §1, §4, §6 | F7b (validação e enriquecimento) |
| N14 | E4: a declividade média no pixel das usinas passa do limite central na PRT solar (3,9 graus contra 2,9) e na PRT eólica (12,7 contra 11,3); na BRA solar 14% da capacidade tem E4 >= 0,5. O motor já usa o FABDEM | C | D4 §3, §6 | elegibilidade, potencial |
| N15 | E6: a capacidade das usinas dentro do setback central é 35,0% na IND solar e 38,9% na IND eólica (com todas as unidades); o artefato da coordenada (N13) pesa no resultado. Artefato de safra só na IND solar (23,1% contra 12,6%) | C (e D por N13) | D4 §4, §6 | elegibilidade, potencial |
| N16 | E1: em cinco dos seis pares há 8% a 28% da capacidade das usinas dentro de área protegida e 97% a 100% dela em categoria não estrita; o cenário central exclui todas as categorias do WDPA. Nenhuma designação estrita passa de 3,3% da capacidade | C | D4 §5, §6 | elegibilidade, potencial |
| N17 | A classe "usina antiga em área hoje restrita" (c) não é avaliável: WorldCover e GHS-SMOD são fotografias de 2020 e o WDPA do projeto não traz `STATUS_YR`. Falta dado | D | D4 §6, §8 | leitura de N11 a N16 |
| N18 | O pixel (0,01 grau, cerca de 1,1 km) mistura a pegada da usina com o entorno: as parcelas E1 a E6 são do pixel, não da usina | B | D4 §0, §8 | leitura de N11 a N16 |
| N19 | A convergência (`sample_size_convergence`) chama `build_cell_set` sem as células `incomplete_ensemble`, e o F7 as exclui: na BRA eólica a convergência ranqueia 178.285 células com k = 17.829 e o F7 171.181 com k = 17.119 (a diferença de 7.104 é a contagem `incomplete_ensemble`). Nos outros cinco pares os conjuntos coincidem | A | D5 §2.4 | tamanho do LHS (U-04), L-252 |
| N20 | PRT solar, L-252: 1 − Jaccard de 0,0116, 0,0231 e 0,0116 em 500 a 4000. Com k = 342 a tolerância de 0,01 admite no máximo 1 troca; cada passo tem 2 ou 4. Há 16 células com MR a menos de 1% do corte. Em 8000 e 16000 sorteios há 1 troca por passo (0,0058, abaixo de 0,01) | B (e C pelo teto de 4000) | D5 §2 | tamanho do LHS (U-04), H1 a H4 da PRT solar |
| N21 | BRA eólica, 35,0% das células (62.437) e 24,8% da capacidade têm LCOE acima de 200 USD/MWh, por CF baixo (mediana 0,055). Nenhuma está no top-k, nem define L*, nem tem SR > 0. O efeito é no tamanho do top-k: k = 17.119 com elas e 11.444 sem elas, porque k é 10% da contagem de células. 80,1% das `incomplete_ensemble` estão entre elas | B | D5 §1 | H1 a H4, meta de capacidade (via k) |
| N22 | O top-k é por contagem de células, não de capacidade: a parcela do top-k nominal com menos de 1 MW vai de 0,6% (BRA solar) a 33,5% (PRT eólica); as 5 células de menor LCOE da PRT eólica, da IND solar e da IND eólica têm menos de 1 MW | B | D5 §3.2 | H1 a H4 |
| N23 | As 5 células de menor LCOE da BRA eólica têm CF de 0,642 a 0,691 (máximo do par), valores que o CF do F5 reproduz do Global Wind Atlas (OQ-114); estão num bloco de 0,15 grau de longitude. A faixa 0,60 usada para sinalizar é referência do diagnóstico, não do pipeline | D (informativo) | D5 §3.1 | ranking nominal do topo, L* |

Achados sem nada a corrigir (testes que passaram): LCOE reconstruído igual ao F6 com diferença 0 nos seis pares (D1 a D5); τ recalculado igual ao registrado (D1 §0); O, D_TV, Δz e T do H2, e V_k, D_clim, D_tec e d do H3 reproduzidos (D2 §0, D3 §0); E5 e E4 recalculados com erro 0 contra o F7b (D4 §0); nenhuma das 30 células de menor LCOE tem distância zero (D5 §3.1); 5 das 30 estão em borda de máscara sem pico de LCOE em relação às vizinhas (D5 §3.1).

## 2. Hipóteses afetadas, por achado

| Hipótese | Achados | Observação |
|---|---|---|
| H1 (H1a, H1b) | N5, N6, N7, N8, N19 a N22 | V_k = 0 em cinco pares decorre do desenho (N5) e da definição da medida (N7); com top-k de 1% e m = k/2 sobe, sem passar de β |
| H2 | N9, N10, N21 | O depende da partição e de γ; um terço dos pares muda de veredito com um passo da grade |
| H3 | N5, N6, N8, N21, N22 | MR quase igual ao LCOE nominal |
| H4 | N5, N7, N8, N21, N22 | D_clim e D_tec são zero em quase todos os pares |
| H5 | N1 a N4 | "meta não atingida na referência" na BRA solar e na IND eólica vem do domínio quase vazio (N1) |
| PRIM | nenhum diagnosticado | o D1 a D5 não testaram o PRIM; a hipótese do arquivo de comandos (`no_cases`) fica por verificar |
| F7b (validação) | N11 a N18 | a elegibilidade exclui o que o mapa de 2020 e as coordenadas aproximadas mostram, não só o que a usina ocupa |
| Convergência (U-04) | N19, N20 | N19 é a única correção de código |

## 3. Achados (C) e (D): o que mudaria, fases, custo, subconjunto

Sem valores novos: descrevo o que seria revisto e onde. Custos pela seção 4.

### 3.1 τ e domínio econômico (N1, N2, N3; N4 por consequência)

- **O que mudaria.** A calibração do τ (CF da planta de referência, vida de 25 anos, O&M do IRENA) ou o critério que define o domínio econômico para o H5 e o SR. N4 (borda) é só declaração e não muda.
- **Fases que rodariam de novo.** O τ só entra no F7 (SR, H5, potencial econômico) e, como desempate, na convergência. Rodariam `robustness_analysis`, `robustness_maps` e `results_synthesis` nos três países; a convergência só se o desempate importar.
- **Custo.** 11,3 h (F7, mapas e síntese: PRT 0,1 h, IND 2,6 h, BRA 8,5 h), 11,8 h com a convergência. Fora do pipeline, uma recomputação de SR e H5 a partir das tabelas gravadas, como o D1 fez, leva minutos por par.
- **Subconjunto pré-registrado.** Toca: `tau_lcoe_usd_per_mwh` e a faixa dele estão no digest. É desvio do pré-registro, ou análise exploratória rotulada, ou `prereg-v2` (seção 1 do arquivo de comandos).

### 3.2 Top-k e m (N8)

- **O que mudaria.** O percentual do top-k e a tolerância m do deslocamento. O D2 §8 já tem a variante exploratória fora do pipeline (1% e m = k/2).
- **Fases.** `robustness_analysis` e a jusante.
- **Custo.** 11,3 h formal; a variante exploratória já foi calculada fora do pipeline.
- **Subconjunto.** `top_k_percent` está no digest; m e a lista p_k = {5, 10, 20} não estão (a lista é constante fixada pelo commit do registro). As variantes de 5 e 20 já fazem parte da v1.0.

### 3.3 γ e partição do H2 (N10; N9 só declara)

- **O que mudaria.** O limiar γ e a partição das regiões (hoje Admin1).
- **Fases.** `robustness_analysis` e a jusante, se formal; o D3 recalculou o perfil de γ sem fase.
- **Custo.** 11,3 h formal; recomputação fora do pipeline em minutos por par.
- **Subconjunto.** Não toca o digest (γ está em `experiments.yaml`, mas fora dos seletores); `GAMMA_PROFILE` é constante. Se mudar γ é desvio do pré-registro é decisão do autor.

### 3.4 Elegibilidade (N11, N12, N14, N15, N16; N13 e N17 são dado)

- **O que mudaria.** Para N12, N14, N15 e N16 (classe C), as classes excluídas, os limites de declividade e de setback e as categorias do WDPA do cenário central (os cenários restritivo e permissivo já existem). Para N11 (classe D), nada que o código tenha errado: o mapa de cobertura do solo de 2020 contém obras de usinas posteriores; a decisão é se e como lidar com isso (outra camada ou outra data é dado novo).
- **Fases.** `land_eligibility`, `technical_potential`, `lcoe_modeling`, `sample_size_convergence`, `robustness_analysis`, mapas, síntese e `external_validation`: tudo a jusante do F3.
- **Custo.** 13,5 h (F3 e F5 somam 0,4 h; F6 em diante 13,1 h: PRT 0,2 h, IND 3,1 h, BRA 9,8 h), mais F7b em cerca de 2 min; F2b só se as camadas de custo mudarem.
- **Subconjunto.** Os parâmetros de elegibilidade não estão no digest e as camadas também não. O resultado da v1.0 mudaria por inteiro (potencial, ranking, todas as hipóteses), com o digest idêntico: se isso é desvio do pré-registro é decisão do autor.

### 3.5 Dado de localização e de ano de restrição (N13, N17)

- **O que mudaria.** N13: o filtro de precisão da localização do GEM (`excluded_location_accuracy`, hoje nulo) na validação do F7b, que existe como parâmetro. N17: obter o `STATUS_YR` do WDPA e o ano de mudança de uso para avaliar a classe (c); isso é download de dado novo e não foi medido.
- **Fases.** N13: só `external_validation` (F7b) e as fases de mapas e síntese que a leem.
- **Custo.** N13: cerca de 2 min de F7b (IND 0,5 min, BRA 1,2 min) mais mapas e síntese, na ordem de minutos; N17: o download não foi medido.
- **Subconjunto.** Os filtros do `external_validation` estão fora do digest (docstring de `preregistration.py`).

### 3.6 Convergência: teto de 4000 (N20, face C)

- **O que mudaria.** `sampler.max_size_for_convergence` e o `sampler.adopted_size` que vale para todos os pares (L-252). A F6 e a F7 escalam com o número de sorteios.
- **Fases.** `lcoe_modeling`, convergência, `robustness_analysis` e a jusante, nos três países.
- **Custo.** Na ordem do dobro de 13,1 h (estimativa por escala, não medida); tomar o teto só para a PRT solar não é possível enquanto o tamanho adotado for um só.
- **Subconjunto.** Não toca o digest (o tamanho do LHS não está nos seletores).

### 3.7 CF extremo da BRA eólica (N23, classe D, informativo)

Sem ação associada que o diagnóstico sustente: o CF do F5 reproduz o do Global Wind Atlas (OQ-114) e a frota ABEEólica tem CF menor que o do F5 nos sítios das usinas (OQ-114). Fica registrado para a leitura do topo do ranking nominal.

## 4. Custos de referência (tempo de parede a frio, minutos, `manifest.json`)

| Fase | PRT | IND | BRA |
|---|---|---|---|
| `land_eligibility` | 0,3 | 4,6 | 15,7 |
| `technical_potential` | 0,1 | 1,3 | 3,8 |
| `lcoe_modeling` | 1,5 | 22,8 | 52,2 |
| `sample_size_convergence` | 1,2 | 8,8 | 20,6 |
| `robustness_analysis` | 7,6 | 154,5 | 510,4 |
| `lcoe_maps` + `robustness_maps` | 0,5 | 1,2 | 1,0 |
| `results_synthesis` | 0,4 | 0,7 | 1,3 |
| `external_validation` | 0,0 | 0,5 | 1,2 |

Somas usadas na seção 3: F7, mapas e síntese = PRT 8,4 + IND 155,8 + BRA 512,2 min (11,3 h). F6 a síntese = 11,2 + 188,0 + 585,5 min (13,1 h). Com F3 e F5 mais 25,8 min (13,5 h). Convergência nos três = 30,6 min. As rodadas de 0,1 grau não entram.

## 5. Achados (A) e (B): ação

- **N19 (A).** Corrigir a chamada em `convergence.py` (passar as células `incomplete_ensemble` para `build_cell_set`, como o F7 faz) mudaria a impressão digital de código da fase `sample_size_convergence`. Só a BRA eólica muda de conjunto. Rodar de novo a convergência custa 0,5 h nos três países (0,34 h só a BRA), como na 200B; não toca o digest. O tamanho adotado, 4000, não depende dela.
- **N4, N5, N6, N7, N9, N18, N20, N21, N22 (B).** Declarar na tese e em `docs/LIMITATIONS.md` (L-252 já cobre N20): o desenho da incerteza quase não move o ranking (N5, N6), o veredito do H5 e o do H2 dependem de poucas células e de poucas regiões (N4, N9), as duas medidas de deslocamento (N7), o top-k é por contagem de células (N21, N22) e a escala do pixel (N18).

## 6. Limites desta síntese

- O PRIM não foi diagnosticado.
- Os custos são do tempo de parede da última rodada na máquina do autor; a variação entre rodadas não foi medida.
- A classe de cada achado é uma leitura minha; a de N7 (B contra C) e a de N20 (B contra C) são as mais discutíveis.
- N2 e N3 são tratados com N1 porque vêm da mesma calibração; poderiam ser decididos em separado.
- Nenhum valor novo de parâmetro é proposto aqui, de acordo com o COMANDO 206.
