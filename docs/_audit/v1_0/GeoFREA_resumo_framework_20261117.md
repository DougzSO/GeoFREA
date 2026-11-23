# GeoFREA: resumo do framework (2026-11-17)

Gerado pelo COMANDO 165A, somente leitura. Caminhos de origem: `GeoFREA/...` e o repositorio (D:/Douglas/DOUTORADO/GeoFREA), `GeoFREA_data/...` e o diretorio de dados (D:/Douglas/DOUTORADO/GeoFREA_data). Todo numero traz o caminho de onde foi lido; o que nao foi encontrado esta escrito como 'nao encontrado'. Estado do repositorio: HEAD 8206cec, tag prereg-v1 em ccf764f.

## (a) Objetivo e pergunta de pesquisa

GeoFREA e um framework espacial e de dados abertos que estima o potencial tecnico e o LCOE em nivel de celula (0,05 grau) de solar fotovoltaica e eolica terrestre de grande porte em Brasil, Portugal e India, e ordena as celulas pela robustez do ranking economico frente a futuros climaticos e a incerteza tecnoeconomica (`GeoFREA/docs/PROJECT_SUMMARY.md`; `GeoFREA/docs/METHODOLOGY.md`, secao 1).

- **RQ0 (central):** como um framework computacional espacialmente explicito, que integra potencial tecnico, viabilidade tecnoeconomica e mudanca climatica multi-cenario, identifica prioridades de localizacao que permanecem robustas entre futuros climaticos, e como medir essa robustez de forma defensavel tratando juntas a incerteza fisico-climatica e a tecnoeconomica (`GeoFREA/docs/METHODOLOGY.md`, 1.1).
- RQ1: potencial tecnico espacial comparavel entre paises. RQ2: restricoes territoriais e custos dependentes do territorio numa metrica unica de viabilidade por local. RQ3: como as projecoes multi-SSP mudam o potencial e a viabilidade futura de locais ainda nao construidos. RQ4: qual abordagem de robustez de decisao trata melhor a incerteza climatica profunda e a parametrica juntas. RQ5: se o framework generaliza entre os tres paises.

## (b) Grupos 1 a 7 e hipoteses H1 a H5

| Grupo | Tema | Onde esta | Fases que usam |
|---|---|---|---|
| 1 | Potencial tecnico (LUF, densidade de potencia, curvas de potencia, Weibull, temperatura) | `GeoFREA/docs/thesis/methods/group1_technical_potential.tex` | F5 |
| 2 | Custos centrais (CAPEX, OPEX, vida util, taxa de desconto) | `GeoFREA/docs/thesis/methods/group2_core_costs.tex` | F6 |
| 3 | Conexao e degradacao (subestacao, linha, estrada, perdas, degradacao por zona) | `GeoFREA/docs/thesis/methods/group3_connection_degradation.tex` | F2a, F6 |
| 4 | Parametros de decisao pre-registrados (tau, cf_min, top_k, q_ref, metas, moeda) | `GeoFREA/docs/thesis/methods/grupo4.tex` | F7 |
| 5 | Exposicao a perigos climaticos (sem perda), faixa do fator de vento | `GeoFREA/docs/thesis/methods/grupo5.tex` | F4, F7 (H5b) |
| 6 | Elegibilidade do solo (E1 a E6, declividade, rios, setbacks) | `GeoFREA/docs/thesis/methods/group6_land_eligibility.tex` | F2b, F3 |
| 7 | Potenciais publicados, validacao externa (F7b) e ranking robusto | `GeoFREA/docs/thesis/methods/grupo7.tex`, `synthesis_and_scenario_discovery.tex` | F7, F7b, F8 |

Hipoteses (`GeoFREA/docs/METHODOLOGY.md`, 1.3; textos em `GeoFREA/docs/thesis/hypotheses/`):
- **H1:** o ranking de locais se mantem entre futuros climaticos, em dois sentidos: H1a (estabilidade do nucleo: a maioria dos locais robustos sob um SSP e robusta sob os tres) e H1b (vulnerabilidade climatica: ao menos um em cada cinco dos top-k nominais sai do top k+m do ranking so climatico em algum SSP).
- **H2:** avaliar a expansao por regiao administrativa (Admin1) em vez de por celula seleciona capacidade diferente e menos robusta (Indice de Sobreposicao de Capacidade).
- **H3:** planejar pela robustez muda onde a capacidade seria construida: uma parcela material da capacidade robusta fica fora do alcance de um plano baseado em condicoes presentes.
- **H4:** o eixo de incerteza que domina o deslocamento do ranking (clima ou tecnoeconomico) nao e o mesmo em todos os paises.
- **H5 (RQ3):** a mudanca climatica pressiona materialmente o potencial economico renovavel que sustenta uma meta nacional (dominio economico definido por LCOE <= tau).

## (c) Sequencia das fases, entrada, saida, modulo e estado por pais

Ordem de execucao do DAG (`GeoFREA/main.py`, linhas 992 a 1355; `GeoFREA/docs/METHODOLOGY.md`, 4.2). O estado vem de `GeoFREA_data/outputs/<ISO>/manifest.json` (campo `phases.<fase>.status` e `finished_at`, lidos em 2026-11-17). 'nao rodada' = a fase nao esta no manifesto.

| Fase | Entrada | Saida | Modulo (`GeoFREA/src/geofrea/`) | PRT | IND | BRA |
|---|---|---|---|---|---|---|
| F1 data_acquisition | fontes brutas (`GeoFREA_data/raw`, `external`) | registro de camadas com proveniencia | `data_acquisition` | success (2026-11-12) | success (2026-11-12) | success (2026-11-12) |
| F1b data_quality_audit | registro de camadas | relatorio de auditoria | `data_quality_audit` | success (2026-11-05) | success (2026-11-06) | success (2026-11-06) |
| F2a grid_alignment | registro de camadas | rasters alinhados na grade de 0,01 grau | `grid_alignment` | success (2026-11-12) | success (2026-11-12) | success (2026-11-12) |
| external_inputs | arquivos CMIP6, ISIMIP3b, ERA5 | relatorio de entradas externas | `climate_forcing` | success (2026-11-06) | success (2026-11-06) | success (2026-11-06) |
| F2b siting_layers | rasters alinhados | camadas de exclusao, custo e recurso por tecnologia | `siting_layers` | success (2026-11-09) | success (2026-11-09) | success (2026-11-09) |
| F3 land_eligibility | camadas do F2b | tabela de candidatos, rasters de elegibilidade (3 cenarios de solo) | `land_eligibility` | success (2026-11-12) | success (2026-11-12) | success (2026-11-12) |
| F4 climate_forcing | grade de referencia, auditoria, entradas externas | fatores de mudanca por celula e membro | `climate_forcing` | success (2026-11-12) | success (2026-11-12) | success (2026-11-12) |
| hazard_context | membros, grade | tabela de indicadores de perigo | `climate_forcing` | success (2026-11-12) | success (2026-11-12) | success (2026-11-12) |
| climate_maps | forcing | mapas diagnosticos | `climate_forcing` | success (2026-11-12) | success (2026-11-12) | success (2026-11-12) |
| overview | camadas de F2a a F4 | figuras e tabela de visao geral por pais | `overview` | success (2026-11-12) | success (2026-11-12) | success (2026-11-12) |
| F5 technical_potential | elegibilidade, F2b, forcing, membros | capacidade, CF e energia por celula e membro (3 cenarios de solo) | `technical_potential` | success (2026-11-17) | success (2026-11-17) | success (2026-11-17) |
| potential_maps | F5 | COG e mapas de densidade de potencial e CF | `technical_potential` | success (2026-11-17) | success (2026-11-17) | success (2026-11-17) |
| F6 lcoe_modeling | elegibilidade, F5, parametros | LCOE por celula, amostras LHS, matriz de desenho | `lcoe_modeling` | nao rodada | nao rodada | nao rodada |
| sample_size_convergence | F6 | convergencia do tamanho da amostra | `lcoe_modeling` | nao rodada | nao rodada | nao rodada |
| F7 robustness_analysis | F6, metas, parametros pre-registrados | regret, satisficing, decomposicao por eixo, PRIM, H1 a H5 | `robustness_analysis` | nao rodada | nao rodada | nao rodada |
| F7b external_validation | F5, GEM trackers, `config/published_potential.yaml` | tabelas de plausibilidade contra usinas existentes e potenciais publicados | `external_validation` | nao rodada | nao rodada | nao rodada |
| lcoe_maps | F6 | mapas de LCOE | `lcoe_modeling` | nao rodada | nao rodada | nao rodada |
| robustness_maps | F7 | mapas de robustez | `robustness_analysis` | nao rodada | nao rodada | nao rodada |
| F8 results_synthesis | F5, F6, F7, F7b | figuras e tabelas da tese | `results_synthesis` | nao rodada | nao rodada | nao rodada |
| E1 explorer | F8 | site estatico pre-calculado | `explorer` | nao rodada | nao rodada | nao rodada |

Fonte do estado: `GeoFREA_data/outputs/PRT/manifest.json`, `GeoFREA_data/outputs/IND/manifest.json`, `GeoFREA_data/outputs/BRA/manifest.json`. Fases guardadas pelo pre-registro (so rodam com a tag `prereg-v1` e o subconjunto igual): `lcoe_modeling`, `sample_size_convergence` e `robustness_analysis` (`GeoFREA/src/geofrea/core/orchestrator.py`, linha 524; guarda na linha 1322). Nenhuma delas rodou em producao.

## (d) Principais premissas, por tema (uma linha cada, com a DEC ou o D-)

**Escopo e grade**
- Tres paises (BRA, IND, PRT), solar PV e eolica terrestre, grade de 0,05 grau para a analise e 0,01 grau para o alinhamento (METHODOLOGY S-01, S-02, S-06; D-F3-013).
- Climate change entra como mudanca da media do recurso, de 6 GCMs CMIP6 sob SSP1-2.6, SSP3-7.0 e SSP5-8.5, 2041-2070 (nucleo) e 2071-2100 (sensibilidade) contra 1995-2014 (METHODOLOGY S-03 a S-05, M-F4-01 a M-F4-03).
- Perigos climaticos entram so como exposicao, nunca como perda no LCOE, e a rajada e canal de contexto (DEC-065; D-F4-001).

**Solo e elegibilidade**
- Tres cenarios de solo (restritivo, central, permissivo) variando declividade, recuo de assentamentos, expoente de largura de rio e area minima de cluster; o solo sai dos futuros do F7 e aparece como faixa (D-F3-007; METHODOLOGY U-06).
- O limite de 3000 m e celulas sem elevacao nao sao candidatas (D-F3-017, D-F3-018); declividade vem do FABDEM (D-F3-029) e a cobertura da India de WorldCover 10 m (D-F3-008).

**Potencial tecnico (F5)**
- Eolica: curva de potencia IEC e integral de Weibull por celula (D-F5-001, D-F5-003, D-F5-004, D-F5-038, D-F5-039); altura do cubo e sensibilidade de 150 m (D-F5-012, D-F5-027).
- Solar: PVOUT com correcao de temperatura (coeficiente -0,003 /C), LUF e densidade de potencia por cenario (D-F5-009; `GeoFREA_data/outputs/PRT/manifest.json`, parametros do F5).
- Celulas com membro mascarado ou ensemble incompleto ficam no F5 marcadas (D-F5-006, D-F5-041); fator de vento fora de [0,5; 1,5] e mascarado (OQ-043, sem fonte).

**Custos e moeda**
- Todo valor monetario entra em USD constantes de 2024; USD 2025 e multiplicado por 0,97275 (deflator do PIB dos EUA) (DEC-062, DEC-071).
- Faixa de WACC por pais e tecnologia, regional do IRENA 2024 mais ou menos 1 ponto percentual unida ao valor do pais (Tier 3 na largura) (DEC-072).
- Base do IRENA: TIC solar por kW DC e CF solar AC-DC, eolica AC-AC; o F6 trabalha em capacidade DC (DEC-079, DEC-086, DEC-087).
- Parametros de decisao ficam fora do LHS: tau, cf_min, top_k, q_ref (DEC-061).

**Parametros pre-registrados (F7)**
- tau primario e o LCOE do kernel F6 da planta de referencia do IRENA 2024, grau de degradacao 0; o publicado do IRENA fica dentro do range, que e a sensibilidade do H5 (DEC-085 a, DEC-090).
- Range do tau e o p5 a p95 do IRENA estendido ate incluir o primario; PRT usa a linha da Europa sem teto (DEC-078, DEC-085 c, DEC-089 a).
- cf_min solar 0,115 (p5 global do IRENA 2024) e cf_min eolico 0, sem piso (DEC-088).
- top_k primario de 10 por cento, com 5 e 20 como sensibilidades (DEC-085 d); q_ref = 0 (DEC-074).
- Metas: BRA solar 90 GW (2050), IND solar 447 GW e eolica 138 GW (2035); BRA eolica, PRT solar e PRT eolica sem meta registrada (DEC-063, DEC-070, DEC-075, DEC-083, DEC-084).
- Subconjunto congelado por digest SHA-256 em tag anotada; mudar depois da tag e desvio e o F7 recusa (DEC-081).

**Robustez (F7)**
- Regret relativo ao minimo de LCOE (q_ref = 0) como metrica primaria, satisficing como secundaria e PRIM para vulnerabilidades (METHODOLOGY M-F7-02, M-F7-03, M-F7-08; DEC-074).
- O clima e um conjunto discreto, sem pesos, de membros (METHODOLOGY U-01, U-02); a amostragem tecnoeconomica e LHS no F6 (M-F6-02).

**Validacao externa (F7b) e potenciais publicados**
- O F7b poe o potencial publicado ao lado do F5 e nao calcula razao nem veredito; so `status: registered` tem valor (M-F7b-03; OQ-057).
- Metas e potenciais de escopos diferentes: toda comparacao cita a L-246 (DEC-083).

**Processo**
- O estado de execucao vive so em `GeoFREA/docs/PROGRESS.json`; decisoes em `GeoFREA/docs/DECISIONS.md` (append-only) (DEC-059, DEC-069).
- Fases com fingerprint de configuracao ou de codigo diferente sao reexecutadas sozinhas; nada rodou em producao do F6 em diante (`GeoFREA/src/geofrea/core/orchestrator.py`).

## (e) Subconjunto pre-registrado

Tag anotada `prereg-v1`: objeto `685a29cc46e184ca148c233920f1c692d2218fe3`, aponta para o commit `ccf764f1fb675f961d7c4d92ff0a66fb3d5fc326` (`git rev-parse prereg-v1`; `git ls-remote --tags origin prereg-v1`). Digest agregado `1bce505f3315fa34948cf842612a2eee4c7ec1ff9c15e919f08cc631d8f08235`; por pais: BRA `b51ee7d55d940684b524166ac17bfcde4f2c5381dd6e65d0b97188bf514c2c48`; IND `51381bfcd1c1a6a1d1ea43fa7a86dc82ad1b37425c32d6b2900008611533fac6`; PRT `50b617071b83f60a5a3ee9e722cd1bd2fc4cb3126b05ca0cd3cdeda21bf4df99` (saida de `GeoFREA/scripts/preregistration_digest.py`, que nao cria nada).

| Par | tau primario (USD/MWh) | range do tau | cf_min | top_k (%) | Meta (GW, horizonte) | Fonte |
|---|---:|---|---:|---:|---|---|
| PRT solar | 54.53 | 41.0 a 103.0 | 0.115 | 10 | sem meta registrada (no_target) | `GeoFREA/config/parameters.json`; `GeoFREA/config/experiments.yaml` (`national_targets.PRT.solar`) |
| PRT wind | 49.64 | 34.0 a 75.0 | 0 | 10 | sem meta registrada (no_target) | `GeoFREA/config/parameters.json`; `GeoFREA/config/experiments.yaml` (`national_targets.PRT.wind`) |
| IND solar | 28.26 | 28.26 a 59.0 | 0.115 | 10 | 447 GW, 2035 | `GeoFREA/config/parameters.json`; `GeoFREA/config/experiments.yaml` (`national_targets.IND.solar`) |
| IND wind | 36.43 | 36.43 a 53.0 | 0 | 10 | 138 GW, 2035 | `GeoFREA/config/parameters.json`; `GeoFREA/config/experiments.yaml` (`national_targets.IND.wind`) |
| BRA solar | 43.97 | 36.0 a 77.0 | 0.115 | 10 | 90 GW, 2050 | `GeoFREA/config/parameters.json`; `GeoFREA/config/experiments.yaml` (`national_targets.BRA.solar`) |
| BRA wind | 31.95 | 24.0 a 37.0 | 0 | 10 | sem meta registrada (no_target) | `GeoFREA/config/parameters.json`; `GeoFREA/config/experiments.yaml` (`national_targets.BRA.wind`) |

Outras chaves do subconjunto (valores em `GeoFREA/config/experiments.yaml`): `thresholds.regret_quantile` = 0; `prim.outcome_threshold` = 0.2; `hypothesis_rules.H5.sensitivity_lambda`; `windows.sensitivity`; mais, por pais, `degradation_by_zone.hot_zone_sensitivity` (so solar), `transmission_loss_per_km_sensitivity` e `poi_sensitivity_threshold_kv`. Nao ha nulo pendente nas chaves nao estruturais.

## (f) Resultados que existem hoje

Todos vem de `GeoFREA_data/outputs/<ISO>/manifest.json` (saida de cada fase) e dos arquivos que ele cita; nenhum foi recalculado aqui. 'GW' e 'TWh/ano' no cenario de solo e no membro de referencia (`p_gw_reference`, `e_twh_reference`).

### Potencial tecnico (F5)

| Pais | Tec. | Cenario de solo | Capacidade (GW) | Energia (TWh/ano) | Celulas candidatas | Origem |
|---|---|---|---:|---:|---:|---|
| PRT | solar | restrictive | 32.0 | 51.7 | 3290 | `GeoFREA_data/outputs/PRT/manifest.json` (`phases.technical_potential.output.technologies.solar.scenarios.restrictive`); tabela em `GeoFREA_data/outputs/PRT/technical_potential/artifacts/potential_solar__restrictive.parquet` |
| PRT | solar | central | 153.3 | 247.3 | 3415 | `GeoFREA_data/outputs/PRT/manifest.json` (`phases.technical_potential.output.technologies.solar.scenarios.central`); tabela em `GeoFREA_data/outputs/PRT/technical_potential/artifacts/potential_solar__central.parquet` |
| PRT | solar | permissive | 563.8 | 906.3 | 3640 | `GeoFREA_data/outputs/PRT/manifest.json` (`phases.technical_potential.output.technologies.solar.scenarios.permissive`); tabela em `GeoFREA_data/outputs/PRT/technical_potential/artifacts/potential_solar__permissive.parquet` |
| PRT | wind | restrictive | 3.4 | 7.8 | 2426 | `GeoFREA_data/outputs/PRT/manifest.json` (`phases.technical_potential.output.technologies.wind.scenarios.restrictive`); tabela em `GeoFREA_data/outputs/PRT/technical_potential/artifacts/potential_wind__restrictive.parquet` |
| PRT | wind | central | 22.8 | 52.2 | 3332 | `GeoFREA_data/outputs/PRT/manifest.json` (`phases.technical_potential.output.technologies.wind.scenarios.central`); tabela em `GeoFREA_data/outputs/PRT/technical_potential/artifacts/potential_wind__central.parquet` |
| PRT | wind | permissive | 77.0 | 175.2 | 3638 | `GeoFREA_data/outputs/PRT/manifest.json` (`phases.technical_potential.output.technologies.wind.scenarios.permissive`); tabela em `GeoFREA_data/outputs/PRT/technical_potential/artifacts/potential_wind__permissive.parquet` |
| IND | solar | restrictive | 211.6 | 353.5 | 72731 | `GeoFREA_data/outputs/IND/manifest.json` (`phases.technical_potential.output.technologies.solar.scenarios.restrictive`); tabela em `GeoFREA_data/outputs/IND/technical_potential/artifacts/potential_solar__restrictive.parquet` |
| IND | solar | central | 806.1 | 1331.6 | 93701 | `GeoFREA_data/outputs/IND/manifest.json` (`phases.technical_potential.output.technologies.solar.scenarios.central`); tabela em `GeoFREA_data/outputs/IND/technical_potential/artifacts/potential_solar__central.parquet` |
| IND | solar | permissive | 4890.8 | 8000.8 | 107919 | `GeoFREA_data/outputs/IND/manifest.json` (`phases.technical_potential.output.technologies.solar.scenarios.permissive`); tabela em `GeoFREA_data/outputs/IND/technical_potential/artifacts/potential_solar__permissive.parquet` |
| IND | wind | restrictive | 60.1 | 99.3 | 38433 | `GeoFREA_data/outputs/IND/manifest.json` (`phases.technical_potential.output.technologies.wind.scenarios.restrictive`); tabela em `GeoFREA_data/outputs/IND/technical_potential/artifacts/potential_wind__restrictive.parquet` |
| IND | wind | central | 214.1 | 331.5 | 75535 | `GeoFREA_data/outputs/IND/manifest.json` (`phases.technical_potential.output.technologies.wind.scenarios.central`); tabela em `GeoFREA_data/outputs/IND/technical_potential/artifacts/potential_wind__central.parquet` |
| IND | wind | permissive | 879.6 | 1297.3 | 99793 | `GeoFREA_data/outputs/IND/manifest.json` (`phases.technical_potential.output.technologies.wind.scenarios.permissive`); tabela em `GeoFREA_data/outputs/IND/technical_potential/artifacts/potential_wind__permissive.parquet` |
| BRA | solar | restrictive | 4183.0 | 6789.5 | 188719 | `GeoFREA_data/outputs/BRA/manifest.json` (`phases.technical_potential.output.technologies.solar.scenarios.restrictive`); tabela em `GeoFREA_data/outputs/BRA/technical_potential/artifacts/potential_solar__restrictive.parquet` |
| BRA | solar | central | 16489.5 | 26741.6 | 190521 | `GeoFREA_data/outputs/BRA/manifest.json` (`phases.technical_potential.output.technologies.solar.scenarios.central`); tabela em `GeoFREA_data/outputs/BRA/technical_potential/artifacts/potential_solar__central.parquet` |
| BRA | solar | permissive | 47080.7 | 76202.8 | 200075 | `GeoFREA_data/outputs/BRA/manifest.json` (`phases.technical_potential.output.technologies.solar.scenarios.permissive`); tabela em `GeoFREA_data/outputs/BRA/technical_potential/artifacts/potential_solar__permissive.parquet` |
| BRA | wind | restrictive | 372.2 | 506.5 | 158178 | `GeoFREA_data/outputs/BRA/manifest.json` (`phases.technical_potential.output.technologies.wind.scenarios.restrictive`); tabela em `GeoFREA_data/outputs/BRA/technical_potential/artifacts/potential_wind__restrictive.parquet` |
| BRA | wind | central | 1990.7 | 2712.2 | 178289 | `GeoFREA_data/outputs/BRA/manifest.json` (`phases.technical_potential.output.technologies.wind.scenarios.central`); tabela em `GeoFREA_data/outputs/BRA/technical_potential/artifacts/potential_wind__central.parquet` |
| BRA | wind | permissive | 6071.5 | 8251.1 | 200035 | `GeoFREA_data/outputs/BRA/manifest.json` (`phases.technical_potential.output.technologies.wind.scenarios.permissive`); tabela em `GeoFREA_data/outputs/BRA/technical_potential/artifacts/potential_wind__permissive.parquet` |

### Areas elegiveis (F3)

| Pais | Tec. | Cenario de solo | Area elegivel (km2) | Celulas candidatas | Origem |
|---|---|---|---:|---:|---|
| PRT | solar | restrictive | 7113 | 3290 | `GeoFREA_data/outputs/PRT/manifest.json` (`phases.land_eligibility.output.technologies.solar.scenarios.restrictive`) |
| PRT | solar | central | 12262 | 3415 | `GeoFREA_data/outputs/PRT/manifest.json` (`phases.land_eligibility.output.technologies.solar.scenarios.central`) |
| PRT | solar | permissive | 21480 | 3640 | `GeoFREA_data/outputs/PRT/manifest.json` (`phases.land_eligibility.output.technologies.solar.scenarios.permissive`) |
| PRT | wind | restrictive | 20300 | 2426 | `GeoFREA_data/outputs/PRT/manifest.json` (`phases.land_eligibility.output.technologies.wind.scenarios.restrictive`) |
| PRT | wind | central | 30452 | 3332 | `GeoFREA_data/outputs/PRT/manifest.json` (`phases.land_eligibility.output.technologies.wind.scenarios.central`) |
| PRT | wind | permissive | 36067 | 3638 | `GeoFREA_data/outputs/PRT/manifest.json` (`phases.land_eligibility.output.technologies.wind.scenarios.permissive`) |
| IND | solar | restrictive | 94039 | 72731 | `GeoFREA_data/outputs/IND/manifest.json` (`phases.land_eligibility.output.technologies.solar.scenarios.restrictive`) |
| IND | solar | central | 161224 | 93701 | `GeoFREA_data/outputs/IND/manifest.json` (`phases.land_eligibility.output.technologies.solar.scenarios.central`) |
| IND | solar | permissive | 260840 | 107919 | `GeoFREA_data/outputs/IND/manifest.json` (`phases.land_eligibility.output.technologies.solar.scenarios.permissive`) |
| IND | wind | restrictive | 362215 | 38433 | `GeoFREA_data/outputs/IND/manifest.json` (`phases.land_eligibility.output.technologies.wind.scenarios.restrictive`) |
| IND | wind | central | 573072 | 75535 | `GeoFREA_data/outputs/IND/manifest.json` (`phases.land_eligibility.output.technologies.wind.scenarios.central`) |
| IND | wind | permissive | 823559 | 99793 | `GeoFREA_data/outputs/IND/manifest.json` (`phases.land_eligibility.output.technologies.wind.scenarios.permissive`) |
| BRA | solar | restrictive | 929547 | 188719 | `GeoFREA_data/outputs/BRA/manifest.json` (`phases.land_eligibility.output.technologies.solar.scenarios.restrictive`) |
| BRA | solar | central | 1319158 | 190521 | `GeoFREA_data/outputs/BRA/manifest.json` (`phases.land_eligibility.output.technologies.solar.scenarios.central`) |
| BRA | solar | permissive | 1793549 | 200075 | `GeoFREA_data/outputs/BRA/manifest.json` (`phases.land_eligibility.output.technologies.solar.scenarios.permissive`) |
| BRA | wind | restrictive | 2242028 | 158178 | `GeoFREA_data/outputs/BRA/manifest.json` (`phases.land_eligibility.output.technologies.wind.scenarios.restrictive`) |
| BRA | wind | central | 2659551 | 178289 | `GeoFREA_data/outputs/BRA/manifest.json` (`phases.land_eligibility.output.technologies.wind.scenarios.central`) |
| BRA | wind | permissive | 2842441 | 200035 | `GeoFREA_data/outputs/BRA/manifest.json` (`phases.land_eligibility.output.technologies.wind.scenarios.permissive`) |

### Indices e contexto climatico (F4, hazard_context)

| Pais | Celulas | Membros de clima | Linhas do forcing | Celula-membros mascarados | Linhas de hazard_context | Origem |
|---|---:|---:|---:|---:|---:|---|
| PRT | 3939 | 37 | 145743 | 0 | 35451 (9 membros) | `GeoFREA_data/outputs/PRT/manifest.json` (`phases.climate_forcing.output`, `phases.hazard_context.output`); `GeoFREA_data/outputs/PRT/climate_forcing/artifacts/` |
| IND | 112948 | 37 | 4179076 | 0 | 1016532 (9 membros) | `GeoFREA_data/outputs/IND/manifest.json` (`phases.climate_forcing.output`, `phases.hazard_context.output`); `GeoFREA_data/outputs/IND/climate_forcing/artifacts/` |
| BRA | 286043 | 37 | 10583591 | 42947 | 2574387 (9 membros) | `GeoFREA_data/outputs/BRA/manifest.json` (`phases.climate_forcing.output`, `phases.hazard_context.output`); `GeoFREA_data/outputs/BRA/climate_forcing/artifacts/` |

### Aquisicao de dados (F1)

| Pais | Camadas resolvidas | Com proveniencia de busca | So local | Falhas | Origem |
|---|---:|---:|---:|---:|---|
| PRT | 22 de 22 | 17 | 5 | 0 | `GeoFREA_data/outputs/PRT/manifest.json` (`phases.data_acquisition.output.summary`) |
| IND | 22 de 22 | 17 | 5 | 0 | `GeoFREA_data/outputs/IND/manifest.json` (`phases.data_acquisition.output.summary`) |
| BRA | 22 de 22 | 17 | 5 | 0 | `GeoFREA_data/outputs/BRA/manifest.json` (`phases.data_acquisition.output.summary`) |

### Linha de base do que o 162F confirmou

`technical_potential` e `potential_maps` dos tres paises foram refeitos em 2026-11-17 e os 69 artefatos sairam identicos (SHA-256 dos bytes) aos da linha de base `GeoFREA_data/_baselines/prereg_162F_baseline_20261117.json`; isso confirma que essas fases nao leem as chaves do subconjunto (DEC-081 h).

### Publicados (F7b, entrada)

`GeoFREA/config/published_potential.yaml` tem 13 entradas: 4 `registered` (BRA wind 143 GW, Amarante, Odilon A, 2001; BRA wind 14580 GW, Eurek, Kelly Et Al, 2017; BRA solar 307 GW, Empresa De Pesquisa Energetica, 2018; BRA solar 28519 GW, Empresa De Pesquisa Energetica, 2018) e 9 `pending` sem valor. `registered` quer dizer que a linha da tabela do grupo 7 nao tem marca de verificacao, nao que o autor conferiu a fonte (OQ-057).

### O que ainda nao existe

- **F6 lcoe_modeling**: nao rodada em nenhum pais (nao esta nos manifestos). Nao ha LCOE por celula nem amostras LHS.
- **sample_size_convergence**: nao rodada.
- **F7 robustness_analysis**: nao rodada. Nao ha regret, satisficing, PRIM nem veredito de H1 a H5.
- **external_validation (F7b)**: nao rodada em pais real (so no mundo sintetico ZZZ). A comparacao com usinas existentes e com os potenciais publicados nao foi gerada.
- **lcoe_maps e robustness_maps**: nao rodadas.
- **F8 results_synthesis**: nao rodada; as figuras e tabelas da tese de F6 em diante nao existem.
- **E1 explorer**: nao implementado como fase do manifesto.
- Resultados de LCOE, de robustez e de exposicao a perigo por limiar (H5b): nao encontrados.

## (g) Limitacoes e perguntas abertas

Fonte: `GeoFREA/docs/OPEN_QUESTIONS.md` (29 perguntas listadas, todas `open` ou `awaiting_verdict`) e `GeoFREA/docs/LIMITATIONS.md` (123 linhas L-nnn). Criterio de classificacao: **bloqueia a tese** se a pergunta impede um resultado da tese de existir ou de ser interpretado (fases F6 em diante, valores absolutos do eolico, textos com marca de verificacao); **nao bloqueia** se e infraestrutura, teste, fases F1 a F5 ja rodadas ou refinamento opcional. A classificacao e minha, a partir do campo 'Blocks' e do que as fases ja entregaram; o autor revisa.

| OQ | Bloqueia | Classe | Resumo |
|---|---|---|---|
| OQ-007 | F5, F6 | nao bloqueia | Loss functions for C2 (extreme heat on PV and inverters, extreme wind cut-out and tracker stow) and  (open) |
| OQ-008 | F7 | nao bloqueia | Satisficing threshold tau (LCOE) per country and technology, and CF_min per technology. tau is also  (open) |
| OQ-010 | F7 | bloqueia a tese (metas das comparacoes do H5 (inclui a conferencia dos valores da India)) | National expansion targets, the only definition of the target (national_targets, GW or TWh/year with (open) |
| OQ-013 | E1 | nao bloqueia (explorer) | Explorer technology stack and hosting. (open) |
| OQ-014 | Thesis Ch. 2 | bloqueia a tese (justificativa de literatura do capitulo 2) | Literature justification of min-max regret as primary metric with satisficing and PRIM, answering RQ (open) |
| OQ-020 | F7 | nao bloqueia | Regret reference q_ref. Reference choice closed by DEC-074: q_ref = 0 (minimum). (open) |
| OQ-043 | F5 | nao bloqueia | Source for wind_factor_valid_range (0.5-1.5, config/experiments.yaml). The bound that masks a cell-m (open) |
| OQ-051 | F4, F7 | bloqueia a tese (H5b precisa dos limiares de exposicao) | Hazard exposure thresholds (T-R10, H5, M-F7-07). Per hazard indicator (tx35_days, tx40_days, rx5day_ (open) |
| OQ-057 | F7b | bloqueia a tese (o F7b so compara com potenciais publicados conferidos) | Published national technical-potential estimates for M-F7b-03. config/published_potential.yaml holds (open) |
| OQ-064 | F2a to F5, thesis limitations | nao bloqueia | Sensitivity of the results to the resolution of the analysis grid (spec v2 T-06, decision 4 of the a (open) |
| OQ-068 | F7b | nao bloqueia | F7b reuses prepare_shared_layers and holds the shared F3 layers whole (COMMAND 91). COMMAND 138 (dec (open) |
| OQ-071 | Synthetic world (ZZZ2) | nao bloqueia | Retune ZZZ2 solar so that its PRIM box is free of the climate model and has margin in coverage. Afte (open) |
| OQ-072 | F2a, thesis, any publication or platform | nao bloqueia | FABDEM is licensed CC BY-NC-SA 4.0 (non-commercial, share-alike): is that compatible with where the  (open) |
| OQ-078 | F1, CI (ERA5 fetcher) | nao bloqueia | write_annual_maxima_from_hourly hangs under the fork start method of Linux. In the unit job of CI (c (open) |
| OQ-084 | Library versions of a run (partly resolved 2026-11-10, COMMAND 128) | nao bloqueia | COMMAND 133: in the clean round the two F5 aggregates (potential_aggregates_solar, _wind) were recor (open) |
| OQ-094 | F7 | bloqueia a tese (regra das sensibilidades de tau, cf_min e q_ref) | Rule of the sensitivity axes of tau, CF_min and q_ref. The decision of 2026-11-13 (DEC-061) keeps th (awaiting_verdict) |
| OQ-095 | F1 | nao bloqueia | Why the rivers and roads of BRA run about 1.8x slower in the full pipeline than in isolation (DEC-05 (open) |
| OQ-096 | F1b | nao bloqueia | Location of the audit report. _save_report in data_quality_audit/audit.py writes the report to outpu (awaiting_verdict) |
| OQ-097 | F3 | nao bloqueia | Layer names of the resources. land_eligibility/pipeline.py::_required_resources fixes the names of t (open) |
| OQ-098 | F8 | bloqueia a tese (tabelas e figuras do F8 nao compiladas) | The LaTeX tables and the PDF figures of F8 have not been compiled with a TeX engine. Origin: Known i (open) |
| OQ-099 | core | nao bloqueia | Technologies of F1b. data_quality_audit/audit.py keeps its own tuple _TECHNOLOGIES = ("solar", "wind (open) |
| OQ-100 | core | nao bloqueia | Default list of countries. main.py derives default_countries from config/parameters.json (parameters (open) |
| OQ-101 | core | nao bloqueia | Schema versions of the outputs. Only the phases F1 and F1b declare produces_schema_versions (in main (open) |
| OQ-102 | core | nao bloqueia | Aligned raster keys of F2a. main.py fixes _ALIGNED_RASTER_LAYER_KEYS in the produces of grid_alignme (open) |
| OQ-103 | F2a | nao bloqueia | Expectation for the slope layer. F1b removed its slope entry from config/audit.yaml (D-F1b-004) beca (open) |
| OQ-106 | ZZZ | nao bloqueia | ZZZ has no versioned baseline of fingerprints. The synthetic world is generated at each run and has  (awaiting_verdict) |
| OQ-109 | core | nao bloqueia | The rebaseline has no proof for a change that is only a note. scripts/rebaseline_config_fingerprint. (awaiting_verdict) |
| OQ-114 | F7 | bloqueia a tese (validacao do CF eolico das celulas contra a frota) | Validation of the wind cell CF against the fleet CF by country. The model CF is far below the fleet  (open) |
| OQ-115 | Group 5 text | bloqueia a tese (texto do grupo 5) | tab:g5-ind tier labeling and rx5day. The .tex tiers are those of the exposure threshold and the conf (open) |

Limitacoes relevantes para a tese (`GeoFREA/docs/LIMITATIONS.md`): L-028, L-032 e L-033 (CF do eolico e do solar contra a frota), L-209 (largura do range de WACC, Tier 3), L-213 (perda de transmissao, Tier 3), L-241 a L-247 (base do IRENA, tau, cf_min e escopo das metas), L-248 (valores Tier 3 do subconjunto: top_k 10 e cf_min eolico 0). As demais (L-nnn) sao do F1 a F5 e das fases de infraestrutura; nao bloqueiam a tese.

Itens que **bloqueiam a tese** alem das OQs: execucao de producao de F6, F7, F7b, F8 e dos mapas de LCOE e de robustez; marcas `\vfy` e `% verify` dos `.tex` (grupo4: 5 `\vfy` e 7 `% verify`; grupo5: 8 `% verify` e 1 `% open`; grupo7: 5 `\vfy` e 3 `% verify`); entradas do `.bib` com `% verify` ou `% agent`. **Nao bloqueiam**: OQ-106, OQ-109, OQ-020, os itens 3 e 9 da lista window_list_131.

## (h) Como rodar

Ambiente: `GeoFREA/.venv` (Python 3.11), variaveis em `GeoFREA/.env` (caminhos de dados e chaves; nao versionado). Comandos a partir de `GeoFREA/`:

```
python main.py PRT IND BRA                                  # todas as fases alvo de settings.yaml, em ordem de dependencia
python main.py PRT --phases technical_potential,potential_maps   # fases alvo; as anteriores entram sozinhas
python main.py PRT --production                             # recusa proxy ou parametro incerto sem valor ou faixa
python main.py PRT --rerun grid_alignment                   # reexecuta mesmo com success no manifesto
python main.py BRA --scale 0p1deg                           # verificacao de escala (V-07)
python -m pytest -q tests/unit                              # suite unitaria (o total de testes muda a cada commit: nao ha arquivo de origem)
python scripts/lint_docs.py                                 # lint dos documentos
python scripts/preregistration_digest.py                    # imprime os digests do subconjunto; nao cria a tag
```
- **Escopo por fase:** cada fase declara de que chaves de configuracao depende (`GeoFREA/src/geofrea/core/config_fingerprint.py`, tabela `SCOPES`); mudar uma chave fora do escopo nao reabre a fase, e foi isso que o COMANDO 162F confirmou para technical_potential e potential_maps.
- **Retomada:** o orquestrador compara o fingerprint de configuracao e o de codigo de cada fase com o do manifesto; fase com fingerprint diferente e reexecutada sozinha, as demais sao puladas (`GeoFREA/src/geofrea/core/orchestrator.py`, retomada).
- **Guarda do pre-registro:** `lcoe_modeling`, `sample_size_convergence` e `robustness_analysis` so rodam em dados reais se a tag anotada `prereg-v1` existir e o digest do subconjunto for igual ao da tag (`GeoFREA/src/geofrea/core/preregistration.py`); o rebaseline recusa mudanca do subconjunto.
- **Manifesto:** `GeoFREA_data/outputs/<ISO>/manifest.json` registra, por fase, status, fingerprints, artefatos com SHA-256 e o digest do pre-registro; o instantaneo antes de qualquer comando que toque os dados vai para `GeoFREA_data/_snapshots/`.
- **Referencia:** `GeoFREA_data/references/` guarda as rodadas aceitas (hard links para `objects/`); so a publicacao explicita (`--publish-reference`) a move.

## (i) Glossario

- **tau (τ)**: limiar de LCOE (USD/MWh) abaixo do qual uma celula e considerada viavel (satisficing) e que tambem define o dominio do potencial economico no H5.
- **cf_min**: fator de capacidade minimo para uma celula contar como viavel (fracao).
- **top_k**: fracao das celulas elegiveis que formam a lista dos melhores locais (10 por cento, com 5 e 20 como sensibilidade).
- **regret**: perda relativa de uma celula em um futuro frente ao melhor LCOE desse futuro (q_ref = 0, o minimo); o regret maximo mede a robustez.
- **q_ref**: quantil de referencia do regret.
- **satisficing**: robustez por suficiencia: a fracao de futuros em que a celula atende ao limiar (LCOE <= tau, geracao minima).
- **PRIM**: Patient Rule Induction Method: descoberta de cenarios que acha caixas no espaco dos fatores incertos onde o desfecho de interesse se concentra.
- **LHS**: Latin Hypercube Sampling: amostragem estratificada dos parametros tecnoeconomicos no F6.
- **CF**: capacity factor: fator de capacidade (energia gerada sobre a que a capacidade geraria o ano todo).
- **TIC**: total installed cost: custo total instalado (USD/kW).
- **WACC**: weighted average cost of capital: taxa de desconto real apos impostos.
- **LCOE**: levelized cost of energy: custo nivelado da energia (USD/MWh).
- **LUF**: land-use factor: fracao da area elegivel que de fato recebe capacidade.
- **GCM, SSP, CMIP6, ISIMIP3b**: modelo climatico global; trajetoria socioeconomica compartilhada; fase 6 do projeto de intercomparacao de modelos; protocolo de impacto com correcao de vies.
- **DEM, FABDEM, GLO-30**: modelo digital de elevacao; versao do GLO-30 sem vegetacao e construcoes; DEM Copernicus de 30 m.
- **GWA, PVOUT**: Global Wind Atlas; producao fotovoltaica especifica em kWh/kWp.
- **WDPA, GADM, GHSL, GEM**: base mundial de areas protegidas; limites administrativos; camada global de assentamentos; Global Energy Monitor (usinas existentes).
- **DC/AC**: razao entre a capacidade em corrente continua dos modulos e a em corrente alternada do inversor.
- **F1 a F8, F2a, F2b, F7b, E1**: fases do pipeline (secao c); E1 e o explorer.
- **MR**: regret relativo maximo (metrica primaria do F7).
- **Tier 1, 2, 3**: nivel de evidencia: 1 = fonte primaria do pais e da tecnologia ou norma fisica; 2 = fonte primaria transferida com justificativa; 3 = julgamento do autor, listado em LIMITATIONS.
- **DEC, OQ, L, M-, D-**: decisao registrada; pergunta aberta; limitacao; regra da METHODOLOGY; decisao de fase.
- **prereg-v1**: tag anotada que congela o digest do subconjunto pre-registrado.
- **ZZZ**: pais sintetico usado nos testes e na fixture.
