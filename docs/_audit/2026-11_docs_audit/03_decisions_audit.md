# 03 — Auditoria do DECISIONS.md (COMANDO 147-C)

Gerado por script (`dec_audit.py`) e por leitura dirigida; somente leitura. Nenhum arquivo de docs ou código foi alterado. Pasta mantida não rastreada até o 147-H.

Base: `docs/DECISIONS.md` no commit `d4382c0` — 1644 linhas, 66 entradas (cabeçalho `## [data] - nome`): 58 de 2026-08-19 a 2026-09-14 (o log antigo, restaurado) e 8 de 2026-11-13 (COMANDO 144). O cabeçalho-modelo `## [data] - [nome do módulo]` não é entrada e não foi contado.

## 1. Contagens e campos obrigatórios

**Por mês:**

| mês | entradas |
|---|---|
| 2026-08 | 27 |
| 2026-09 | 31 |
| 2026-11 | 8 |

**Por Tipo** (valor padrão do modelo: STRUCTURAL_PRESERVE, METHODOLOGY_REVISION, VERIFICATION_UPDATE; entradas com mais de um aparecem combinadas):

| Tipo | entradas |
|---|---|
| METHODOLOGY_REVISION | 29 |
| STRUCTURAL_PRESERVE | 16 |
| VERIFICATION_UPDATE | 13 |
| sem Tipo padrão | 5 |
| METHODOLOGY_REVISION+STRUCTURAL_PRESERVE | 2 |
| METHODOLOGY_REVISION+VERIFICATION_UPDATE | 1 |

Entradas cujo campo Tipo não traz nenhum dos três valores padrão: **5** (#42 2026-09-11 grid_alignment: slope não herda contaminação de nodata (corr → «correção de integridade de dado (mesma c»; #44 2026-09-11 grid_alignment: reproject_to_grid sanitiza NaN literal antes → «correção de integridade de dado (mesma c»; #47 2026-09-11 data_acquisition: AcquiredLayer.fetch_status quebrava resume → «correção de bug — NÃO é mudança metodoló»; #50 2026-09-11 protected_areas: repara geometria WDPA inválida antes do cli → «correção de bug/robustez — distinta da d»; #56 2026-09-14 pop_suitability: divergencia CI-only vs baseline congelado,  → «correção de robustez (mesma classe de co»).

**Campos obrigatórios** (a regra do modelo: `Justificativa (se METHODOLOGY_REVISION)`, `Referência (literatura/discussão, se aplicável)`; contei como ausente o campo que não aparece como rótulo no início de linha):

| campo | entradas sem o campo |
|---|---|
| Tipo | 0 |
| Descrição | 2 |
| Justificativa | 13 |
| Referência | 3 |

Entradas sem pelo menos um dos quatro: **16** de 66. Entradas METHODOLOGY_REVISION sem Justificativa (a única exigência que o modelo faz de forma condicional): **2**.

- sem **Descrição** (2): #51 2026-09-14 cartografia D7 (cartography.py::plot_criterion_map): ajustes; #52 2026-09-14 compass rose fix + backlog: mapa de densidade agregada (rive
- sem **Justificativa** (13): #38 2026-09-10 suitability_criteria: pacote 4 fecha os 14 critérios; protec; #39 2026-09-11 suitability_builder (Fase 3): mecanismo final do buffer de s; #40 2026-09-11 data_acquisition: solar (PVOUT) ganha resolver local; #42 2026-09-11 grid_alignment: slope não herda contaminação de nodata (corr; #43 2026-09-11 suitability_criteria: protected_areas distingue WDPA ausente; #44 2026-09-11 grid_alignment: reproject_to_grid sanitiza NaN literal antes; #46 2026-09-11 grid_alignment: mosaic_land_cover fail-loud em tile corrompi; #47 2026-09-11 data_acquisition: AcquiredLayer.fetch_status quebrava resume; #48 2026-09-11 slope não herda contaminação de nodata: correção de escopo (; #49 2026-09-11 data_acquisition: protected_planet API activation ...
- sem **Referência** (3): #2 2026-08-19 biomass CAPEX/OPEX/lifetime fallback values; #3 2026-08-20 biomass CAPEX/OPEX/lifetime — verificação da fonte primária; #5 2026-08-20 biomass discount_rate e discount_rate_increment — resolução 

Observação: os dois addenda de rotulagem de 2026-09-14 (#57 e #58) registram justamente a ausência do rótulo `Justificativa:` em #43 e #46.

## 2. IDs estáveis

| verificação | entradas |
|---|---|
| entradas com algum ID `D-Fx-nnn` ou `D-core-nnn` no texto | 1 |
| entradas sem nenhum `D-*` | 65 |
| entradas com algum ID (D-, M-, OQ-, L-, U-, V-, A-, S-, T-) | 6 |
| entradas sem nenhum ID | 60 |
| entradas cujo próprio cabeçalho tem ID | 0 |

Esquema atual de identificação: data + nome no cabeçalho; não há número de série, e duas entradas do mesmo dia só se distinguem pelo nome.

Dias com mais de uma entrada: 11 de 11 (maior: 12 em 2026-09-11).

IDs `D-*` definidos em `docs/phases/**`: **356**; citados em algum lugar do DECISIONS.md: **1**; **definidos só nas fases e ausentes do DECISIONS.md: 355**. IDs `D-*` citados no DECISIONS.md e sem definição nas fases: 0 (nenhum).

| série | definidos só em docs/phases |
|---|---|
| E5b | 1 |
| F1 | 31 |
| F1b | 18 |
| F2a | 29 |
| F2b | 8 |
| F3 | 26 |
| F4 | 27 |
| F5 | 41 |
| F6 | 28 |
| F7 | 60 |
| F7b | 7 |
| F8 | 25 |
| core | 54 |

Exemplos (até 10): D-E5b-001, D-F1-001, D-F1-002, D-F1-003, D-F1-004, D-F1-005, D-F1-006, D-F1-007, D-F1-008, D-F1-009. Lista completa: `03b_d_ids_only_in_phases.txt`.

## 3. Repetições, reversões e contradições

Método: (i) por script, pares de entradas que compartilham 3 ou mais símbolos entre crases (identificador de 8 caracteres ou mais) ou o mesmo `OQ-`; (ii) leitura dirigida das entradas desses pares e de cada entrada cujo tema tem registro em `docs/phases/`, `config/`, `src/` ou `METHODOLOGY.md`, comparando com o estado atual. O tipo de achado é: **explícita** (a entrada nova diz que corrige ou supera a antiga), **sem aviso** (o estado atual contradiz a entrada e o DECISIONS.md não traz entrada que a supere), **repetida** (mesma decisão registrada duas vezes), **pendência não fechada**.

**(i) Pares com símbolos em comum: 151** (mostrados os 10 maiores; muitos são o mesmo módulo tratado em dias seguidos, não conflito):

| entrada A | entrada B | símbolos comuns | exemplos |
|---|---|---|---|
| #28 2026-09-08 wire das 5 camadas restantes a partir do banco local, Fase 1 | #49 2026-09-11 data_acquisition: protected_planet API activation | 13 | AcquiredLayer, GEOFREA_RAW_DATA_DIR, IMPLEMENTED_FETCH_LAYER_NAMES |
| #18 2026-08-25 real fetchers for power_plants/wind/lakes/rivers | #49 2026-09-11 data_acquisition: protected_planet API activation | 12 | AcquiredLayer, PROTECTED_PLANET_API_TOKEN, PhaseExecutionError |
| #12 2026-08-24 data_acquisition skeleton | #27 2026-08-26 real fetcher for borders/admin1 (GADM 4.1) + validação real  | 11 | Orchestrator, _LAYER_REGISTRY, audit.py |
| #12 2026-08-24 data_acquisition skeleton | #32 2026-09-08 grid_alignment orchestrator wiring — adapter + terceiro Phas | 11 | AcquiredLayer, AcquiredLayer.path, AcquisitionResult |
| #10 2026-08-20 orchestrator + data_quality_audit phase | #12 2026-08-24 data_acquisition skeleton | 10 | AuditResult, DataAuditor, DataFetcher |
| #18 2026-08-25 real fetchers for power_plants/wind/lakes/rivers | #28 2026-09-08 wire das 5 camadas restantes a partir do banco local, Fase 1 | 10 | AcquiredLayer, KeyError, MULTI_FILE_LAYER_NAMES |
| #12 2026-08-24 data_acquisition skeleton | #28 2026-09-08 wire das 5 camadas restantes a partir do banco local, Fase 1 | 9 | AcquiredLayer, DataFetcher, country_code |
| #18 2026-08-25 real fetchers for power_plants/wind/lakes/rivers | #27 2026-08-26 real fetcher for borders/admin1 (GADM 4.1) + validação real  | 9 | Orchestrator, _FETCHED_LAYER_HANDLERS, _LAYER_REGISTRY |
| #27 2026-08-26 real fetcher for borders/admin1 (GADM 4.1) + validação real  | #29 2026-09-08 wire das 5 camadas restantes a partir do banco local, Fase 2 | 9 | ClipRequiresCountryGdfError, IMPLEMENTED_FETCH_LAYER_NAMES, Orchestrator |
| #47 2026-09-11 data_acquisition: AcquiredLayer.fetch_status quebrava resume | #49 2026-09-11 data_acquisition: protected_planet API activation | 9 | AcquiredLayer, ProtectedPlanetTokenMissingError, _no_network_fetchers |

**(ii) Achados por leitura** (cada linha cita a entrada, o outro lado e o conflito):

| tipo | entrada (data e nome) | o outro lado | conflito em uma frase |
|---|---|---|---|
| sem aviso | #11 2026-08-20 slope_threshold_deg movido para parameters.json | estado atual (`src/geofrea/core/schemas.py:463`, `config/parameters.json`) | A entrada manda `slope_threshold_deg` por tecnologia e país em `parameters.json`; hoje a chave não existe no JSON (0 ocorrências) e o `schemas.py:463` diz que o máximo de declividade vem de `land_availability` em `experiments.yaml`, faixa comum a todos os países (2026-10-08, Douglas). Não há entrada no DECISIONS.md para essa troca. |
| sem aviso | #1 2026-08-19 protected_areas / IUCN exclusion categories | estado atual (`config/experiments.yaml:276-285`) | A entrada fixa a exclusão uniforme das categorias IUCN Ia, Ib e II; hoje o nominal é `all_designated` (todo polígono WDPA) e `ia_ib_ii` e `ia_ib` são só níveis de sensibilidade. A mudança não está no DECISIONS.md, e `all_designated`/`ia_ib` também não aparecem em `METHODOLOGY.md`, `docs/phases/F3_land_eligibility.md` nem em `LIMITATIONS.md` (grep; não verifiquei `group6_land_eligibility.tex`). |
| sem aviso | #34 2026-09-09 Passo 4: os 4 vereditos metodológicos de grid_alig | `docs/phases/F2a_grid_alignment.md` D-F2a-005 (2026-10-06) | #34 registra a decisão de Douglas de manter a matriz AHP da combinação de alturas de vento (STRUCTURAL_PRESERVE, item 4); D-F2a-005 diz que a combinação AHP foi removida (G-2, 2026-10-06). A reversão está só no registro de fase. |
| sem aviso | #55 2026-09-14 regression fixtures storage: GitHub Release (opcao | `.github/workflows/regression.yml:6` e D-F2a-010 (2026-10-06) | #55 decide guardar os 380 MB de fixtures num GitHub Release e fazer o CI falhar sem eles; o workflow atual diz que o baseline foi aposentado em 2026-10-06 (G-4, D-F2a-010) e que não há download externo. |
| sem aviso | #8 2026-08-20 settings.yaml phase toggles | `config/settings.yaml:24-30` (`run.target_phases`), METHODOLOGY A-03 | #8 cria `run.phases` com um booleano por módulo (suitability_criteria, suitability_analysis, potential_analysis, ghg_abatement e outros); `settings.yaml` hoje usa `run.target_phases` e o comentário diz "unlike the old per-phase boolean toggle map"; esses nomes de módulo não existem em `src/geofrea/`. |
| sem aviso | #2, 3, 4, 5, 6 | `docs/METHODOLOGY.md` S-08 (linha 89) | Cinco entradas de 2026-08-19/20 registram os parâmetros de biomassa (CAPEX, OPEX, vida útil, WACC); S-08 declara biomassa fora do escopo e `parameters.json` não tem a chave `biomass`. O DECISIONS.md não registra a retirada. Dentro do mesmo arquivo #9 e #24 tratam a exclusão do Transport, e #24 diz que não reabre. |
| pendência não fechada | #13 2026-08-24 protected (WDPA): decisão de onde entra no GeoFREA | #43, #49, #50 | #13 deixa em aberto onde `protected` entra, a ser revisitado quando `suitability_criteria` for desenhada; #43, #49 e #50 tratam `protected_areas` dentro de `suitability_criteria` e nenhuma entrada fecha #13. O módulo `suitability_criteria` não existe mais em `src/geofrea/`. |
| pendência não fechada | #30 2026-09-08 `infrastructure/grid/grid.gpkg`: fonte de grid pos | `docs/data/grid_provenance.md` e OQ-063 (fechada em 2026-11-12) | #30 deixa a troca de `{ISO3}_grid_osm.geojson` por `grid.gpkg` como pendência NÃO aplicada; a proveniência do `grid.gpkg` foi fechada em OQ-063, mas nenhuma entrada diz se a troca foi decidida. |
| pendência não fechada | #54 2026-09-14 rivers/roads BRA (1.8x producao vs isolado): inves | (nenhuma entrada posterior) | #54 termina com "causa ainda não confirmada" (rivers e roads de BRA, 1,8x); o DECISIONS.md não traz entrada que a feche. |
| explícita | #26 → 25 | — | #26 corrige retroativamente #25 (a guarda `ClipRequiresCountryGdfError` e a correção do fast path); o próprio nome da entrada diz isso. |
| explícita | #3 → 2 | — | #3 diz que #2 "permanece no log mas está superada quanto a este ponto" (status de verificação dos valores de biomassa). |
| explícita | #5 → 4 | — | #5 resolve as duas pendências de #4 (taxa de desconto e incremento) no mesmo dia. |
| explícita | #48 → 41 e 42 | — | #48 cita #41 e #42 e corrige o escopo (PRT contra BRA) da contaminação de nodata no slope, segundo o próprio nome. |
| explícita | #57 → 43; 58 → 46 | — | Addenda de rotulagem de 2026-09-14: dizem que a decisão não mudou, só que faltava o rótulo `Justificativa:`. |

Contagem: {'sem aviso': 6, 'pendência não fechada': 3, 'explícita': 5}. **Decisões repetidas: nenhuma confirmada por leitura** (os 151 pares do item i são o mesmo módulo tratado em dias diferentes). Nenhum desses casos foi corrigido. O conflito mais claro entre duas fontes é o do AHP (#34 contra D-F2a-005), porque as duas dizem o oposto sobre a mesma coisa.

Pares de entradas novas (2026-11-13) contra as antigas: nenhum conflito encontrado. As novas citam OQ-008, OQ-010, OQ-051, L-033, D-F6-008, que existem. Não comparei as entradas novas com o texto de `OPEN_QUESTIONS.md` além disso.

## 4. Entradas que não são decisões

Regra de classificação do script (palavra-chave e Tipo; **não confirmada por leitura de cada entrada**), em ordem de prioridade: 1) *pergunta aberta, pendência ou ideia*: o nome ou o campo Tipo trazem pendente, pendência, "NÃO aplicada", "ainda nao confirmada", backlog ou ideia (a Descrição não entra, porque quase toda entrada cita uma pendência de passagem); 2) *fato de verificação*: Tipo VERIFICATION_UPDATE (inclui os addenda); 3) *registro de implementação ou de sessão*: Tipo só STRUCTURAL_PRESERVE, ou nome com skeleton, activation, wire, portado, wiring, fetcher, refactor, resolver, fix, cartografia ou compass; 4) *decisão do autor de 2026-11-13*; 5) *decisão ou regra metodológica*: o resto (Tipo METHODOLOGY_REVISION), candidata a ter regra no METHODOLOGY.md.

| categoria | entradas |
|---|---|
| registro de implementação ou de sessão | 23 |
| decisão ou regra metodológica (candidata ao METHODOLOGY.md) | 19 |
| fato de verificação | 10 |
| decisão do autor de 2026-11-13 (inclui a restauração e o fato sobre curtailment) | 8 |
| pergunta aberta, pendência ou ideia | 6 |

- **registro de implementação ou de sessão** (23): #1 2026-08-19 protected_areas / IUCN exclusion categories; #6 2026-08-20 discount_rate architecture fix; #8 2026-08-20 settings.yaml phase toggles; #9 2026-08-20 Transport Decarbonisation phase - exclusão permanente; #12 2026-08-24 data_acquisition skeleton; #16 2026-08-24 IUCN category normalization fix; #17 2026-08-24 AuditSummary refactor to layer-keyed dict; #18 2026-08-25 real fetchers for power_plants/wind/lakes/rivers; #19 2026-08-25 data_acquisition activation; #26 2026-08-26 country_gdf=None + clip=True: incidente real de quase-OOM, g ...

- **decisão ou regra metodológica (candidata ao METHODOLOGY.md)** (19): #2 2026-08-19 biomass CAPEX/OPEX/lifetime fallback values; #4 2026-08-20 biomass parameters restructure (IRENA 2025); #7 2026-08-20 solar and wind parameters populated (IRENA 2024/2025); #10 2026-08-20 orchestrator + data_quality_audit phase; #11 2026-08-20 slope_threshold_deg movido para parameters.json; #14 2026-08-24 vector layer audit depth; #15 2026-08-24 path/paths source-of-truth consolidation; #22 2026-08-25 seismic: fetch automatizado descartado por restrição de lice; #25 2026-08-25 clip_vector_to_country() exact-intersection bottleneck (STRt; #34 2026-09-09 Passo 4: os 4 vereditos metodológicos de grid_alignment (Bow ...

- **fato de verificação** (10): #3 2026-08-20 biomass CAPEX/OPEX/lifetime — verificação da fonte primária; #5 2026-08-20 biomass discount_rate e discount_rate_increment — resolução ; #20 2026-08-25 solar (Global Solar Atlas): padrão de URL per-country decifr; #21 2026-08-25 seismic: fonte identificada (GEM Global Seismic Hazard Map v; #23 2026-08-25 solar: unidade do PVOUT — arquivo já em uso confere, achado ; #38 2026-09-10 suitability_criteria: pacote 4 fecha os 14 critérios; protec; #48 2026-09-11 slope não herda contaminação de nodata: correção de escopo (; #53 2026-09-14 grid (data_acquisition): verificação de estado, sem mudança ; #57 2026-09-14 addendum de rotulagem: Justificativa ausente em "protected_a; #58 2026-09-14 addendum de rotulagem: Justificativa ausente em "grid_alignm

- **decisão do autor de 2026-11-13 (inclui a restauração e o fato sobre curtailment)** (8): #59 2026-11-13 restauração do DECISIONS.md como arquivo vivo; #60 2026-11-13 F7: τ ancorado no IRENA; #61 2026-11-13 F6/F7: parâmetros de decisão fora do LHS; #62 2026-11-13 valores monetários na configuração; #63 2026-11-13 metas nacionais de H5; #64 2026-11-13 preços de leilão; #65 2026-11-13 Group 5: exposição sem perda; canal de rajada; #66 2026-11-13 fato registrado: curtailment e CF_min

- **pergunta aberta, pendência ou ideia** (6): #13 2026-08-24 protected (WDPA): decisão de onde entra no GeoFREA fica pend; #24 2026-08-25 biomassa como mitigação de CO2 para transporte e resposta a ; #30 2026-09-08 `infrastructure/grid/grid.gpkg`: fonte de grid possivelmente; #40 2026-09-11 data_acquisition: solar (PVOUT) ganha resolver local; #52 2026-09-14 compass rose fix + backlog: mapa de densidade agregada (rive; #54 2026-09-14 rivers/roads BRA (1.8x producao vs isolado): investigacao pa

Registros de comando (entradas que relatam um COMANDO numerado): as entradas que citam `COMANDO n` no texto são: #59, #61. O log antigo não numera comandos; ele relata sessões e passos ("Passo 4", "Passo 6").

## 5. A Referência aponta para algo que existe hoje?

Campo analisado: `Referência (…)` de cada entrada (o texto até o próximo rótulo). Itens verificados: caminhos, `arquivo:linha` (arquivo e linha existem), IDs (definidos hoje), entradas do próprio DECISIONS.md citadas por data e nome, e nomes de teste. Resolução de caminho como no 147-B; nomes de arquivo sem pasta que existam em qualquer lugar do repositório contam como existentes. Limites: arquivos do repositório legado (GeoWorld) e `docs/architecture/*` (movidos para `_archive`) aparecem como mortos.

| resultado | contagem |
|---|---|
| Referência com itens verificáveis, todos existem | 29 |
| Referência com pelo menos um item que não existe | 28 |
| Referência declara não haver referência | 1 |
| Referência só em prosa (nada verificável por script) | 5 |
| itens mortos: caminho | 57 |
| itens mortos: teste | 5 |
| itens verificados: ID | 6 |
| itens verificados: caminho | 129 |
| itens verificados: teste | 7 |
| sem campo Referência | 3 |

Entradas com pelo menos um item morto na Referência: **28** de 66; itens mortos: **62**.

Exemplos (até 10):

| entrada | tipo | item que não existe |
|---|---|---|
| #8 2026-08-20 settings.yaml phase toggles | caminho | geoworld_framework/configs/settings.yaml |
| #9 2026-08-20 Transport Decarbonisation phase - exclusão permanente | caminho | geoworld_framework/main.py |
| #10 2026-08-20 orchestrator + data_quality_audit phase | caminho | geoworld_framework/main.py |
| #10 2026-08-20 orchestrator + data_quality_audit phase | caminho | src/core/pipeline_orchestrator.py |
| #10 2026-08-20 orchestrator + data_quality_audit phase | caminho | src/processors/data_auditor.py |
| #10 2026-08-20 orchestrator + data_quality_audit phase | caminho | docs/architecture/data_quality_audit.md |
| #11 2026-08-20 slope_threshold_deg movido para parameters.json | caminho | docs/architecture/data_quality_audit.md |
| #12 2026-08-24 data_acquisition skeleton | caminho | geoworld_framework/src/io/data_orchestrator.py |
| #12 2026-08-24 data_acquisition skeleton | caminho | data_fetcher.py |
| #12 2026-08-24 data_acquisition skeleton | caminho | data_manager.py |

Lista completa: `03c_dead_refs_in_decisions.tsv`.

## 6. Proposta (não aplicada)

**(a) ID estável.** `DEC-AAAA-MM-DD-nn`, `nn` = ordem no dia (01, 02, ...), escrito no cabeçalho: `## [2026-11-13] DEC-2026-11-13-02 - nome`. As 58 entradas antigas recebem o ID num índice (item c), não por edição. Quando a decisão já tem `D-Fx-nnn` numa fase, o campo `Fase:` lista esse ID; o `D-Fx-nnn` continua sendo o ID da decisão de implementação e o `DEC-` o da decisão do autor, sem tentar unificar os dois.
**(b) Estado.** Campo novo `Estado:` com um destes valores: `vigente`, `superada por DEC-...`, `pendente (OQ-nnn)`, `fato` (para VERIFICATION_UPDATE e addenda). O estado das entradas antigas fica no índice (c), não na entrada.
**(c) Índice por script.** `docs/DECISIONS_INDEX.md`, gerado por `scripts/build_decisions_index.py`, nunca editado à mão: tabelas por fase (módulo no nome), por tema (OQ e símbolos em comum) e por estado. Lê o DECISIONS.md e uma tabela de estados `docs/decisions_status.csv` (colunas: id, estado, superada_por, fonte). Um teste verifica que todo cabeçalho tem linha no CSV, que `superada_por` existe e que o índice está atualizado.
**(d) Superação sem editar a antiga.** A entrada nova traz `Substitui: DEC-... (motivo em uma frase)`; a antiga não muda. O estado dela passa a `superada por DEC-...` só em `decisions_status.csv`. Um teste falha se uma entrada vigente citar em `Substitui:` um ID inexistente, e se dois estados vigentes disserem o oposto sobre a mesma chave de configuração (lista curada de chaves).
**(e) Fronteira com as fases (decisão do autor de 2026-11-13: o DECISIONS registra decisões tomadas, e `docs/phases` só se ajusta quando preciso).** Sugiro uma linha em cada entrada nova: `Fase:` com o registro de fase afetado, para a reversão registrada só numa fase (casos AHP e regression do item 3) aparecer também no índice.
**(f) Passivo.** Preencher o CSV para as 58 entradas antigas exige uma leitura por entrada (os 14 achados do item 3 são o ponto de partida) e é decisão do autor; o script só sugere o estado.
