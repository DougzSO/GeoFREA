# 08 — Plano de limpeza de docs/phases (COMANDO 151)

Escrito para o autor. Nada foi alterado em `docs/phases`: este arquivo só propõe. Cada linha tem a classe (a a e) e a proposta. As linhas de History e Known issues são os itens de nível superior de cada seção (um marcador `- ` e as linhas que o continuam contam como um item).

Classe **x** (fora de a a e): o item é a única definição de um D-ID citado; antes de apagar a linha o texto vira a definição em Active implementation decisions.

Classes: **a** já coberta por DEC, D-, M-, L- ou OQ (citada); **b** só existe aqui e é limitação (texto de L proposto); **c** só existe aqui e é pendência (texto de OQ proposto); **d** só histórico, recuperável no git (commit); **e** obsoleta.

## 0. Contagens e limites

| bloco | itens | a | b | c | d | e | x |
|---|---|---|---|---|---|---|---|
| History | 135 | 111 | 0 | 0 | 16 | 5 | 3 |
| Known issues | 61 | 14 | 5 | 9 | 8 | 25 | 0 |
| Conformance (linhas de dado, 13 tabelas) | 161 + 13 do F2b | | | | | | |

D-* definidos mais de uma vez: **16**. Bullets `- **D-` fora do formato: **62** de 364. Citações de teste inexistente nas tabelas de verificação: **15** (mais 1 citação abreviada, seção 6).

Limites desta passagem (leitura sem inferir):
- A classe (a) de History vem da regra: o item cita um D-, OQ, L, M- ou versão de METHODOLOGY que existe (conferido nos arquivos); não li que o D-ID resume o item inteiro. Item sem referência que existe é (d), com o commit que introduziu a linha (`git blame` no HEAD).
- Known issues foram classificados um a um por leitura e por grep em `src`, `config` e nos registros; onde não consegui confirmar o estado atual, a linha diz 'não verifiquei'.
- Na Conformance, 'ok' quer dizer que o arquivo e o símbolo citados existem em `src` (ou o teste existe em `tests`); não quer dizer que o teste prova a regra.
- Os 174 itens de Conformance foram conferidos por script; a coluna Status proposta usa só pass, partial, fail e n/a. `pass?` marca 'built' sem teste citado de execução real: o autor decide entre pass e partial.
- `git status` não ficará só com este arquivo: há alterações sem commit de lotes anteriores (lotes 6, DECISIONS, METHODOLOGY, OQ/L, CONVENTIONS). Este comando só acrescenta `08_phases_plan.md`.

## 1. History e Known issues, uma linha por item

### E1_explorer

| local | seção | item | classe | proposta |
|---|---|---|---|---|
| E1:20 | Known issues | None yet. | e: obsoleta | remover: a fase não começou, o registro vazio é o padrão; 'None yet.' repete o estado do PROGRESS |
| E1:24 | History | None. | e: obsoleta | remover: 'None.' não registra nada |

### E5b

| local | seção | item | classe | proposta |
|---|---|---|---|---|
| E5b:65 | History | - 2026-09-21: D-E5b-001 recorded, closing the count asymmetry as a confirmed, justif… | a: coberta | remover da History; permanece em D-E5b-001 |
| E5b:67 | History | - 2026-09-27: Scope correction recorded above (playbook COMMAND F2-5) — the `StoredP… | d: só histórico | remover; histórico recuperável no git (commit d7a80ccf, 2026-09-27) |
| E5b:68 | History | - 2026-09-27: Completion status made specific (playbook COMMAND ADJ-8b), per-half ta… | d: só histórico | remover; histórico recuperável no git (commit d7a80ccf, 2026-09-27) |

### F1_data_acquisition

| local | seção | item | classe | proposta |
|---|---|---|---|---|
| F1:203 | Known issues | - **OQ-024 resolved (2026-09-23) — `AcquiredLayer` now carries `source_sha256`.** Se… | a: coberta | cobre D-core-016; remover (OQ-024 já resolvida) [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-024] |
| F1:205 | Known issues | - BRA rivers and roads run about 1.8x slower in full pipeline than in isolation; roo… | c: pendência só aqui | DEC-054 registra a investigação parcial e não há OQ aberta: proposta de OQ-095 (F1, Douglas, open): 'Causa do 1,8x de rivers e roads de BRA em produção frente ao isolado (DEC-054); protocolo: reproduzir o clip completo de rivers/BRA com a medição de CPU de DEC-054' |
| F1:206 | Known issues | - Six corrupted BRA land-cover tiles in the local database; handled per tile. | b: limitação só aqui | nenhuma L cobre; texto de L proposto (origem F1, D-F1-* de land_cover e DEC-046): 'Seis tiles de land cover de BRA no banco local estão corrompidos; o pipeline os trata um a um (fail-loud quando sobrepõem o país, DEC-046).' Número de tiles: não verificado |
| F1:207 | Known issues | - **Per-layer isolation implemented (2026-09-24, F2-4 Part A).** `run_acquisition_ph… | d: só histórico | implementado; remover (D-ID próprio não encontrado no texto: ver o commit) (commit 7379ce2a, 2026-09-23) |
| F1:208 | Known issues | - **OQ-012 closed 2026-09-24 (F2-5) — IND wired into `config/countries.yaml`, `data_… | d: só histórico | resolvida (OQ-012 fora da tabela); detalhes da execução de IND são histórico do commit; remover (commit 7379ce2a, 2026-09-23) [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-012] |
| F1:214 | Known issues | - GWA API redirects without validating product or height; existence must be checked … | b: limitação só aqui | nenhuma L cobre (grep em LIMITATIONS: 0); texto de L proposto (origem F1, M-F1-03): 'A API do Global Wind Atlas redireciona sem validar produto ou altura; a existência do arquivo é checada na resposta do CDN.' |
| F1:215 | Known issues | - **Unfiltered land_cover registry for BRA and PRT — resolved 2026-09-22 (FD4c rerun… | d: só histórico | resolvida em 2026-09-22; remover (commit 04c70d9b, 2026-09-22) |
| F1:219 | History | - 2026-10-09: ERA5 merge deadlock found and fixed (D-F1-028). | a: coberta | remover da History; permanece em D-F1-028 |
| F1:220 | History | - 2026-10-15 (D-F1-029, V-83): `raw/w5e5/<ISO3>/tasmax_W5E5v2.0_<ISO3>_19950101-2014… | a: coberta | remover da History; permanece em D-F1-029 |
| F1:221 | History | - 2026-10-19: contiguous territory for `mainland_only` (D-F1-027). | a: coberta | remover da History; permanece em D-F1-027 |
| F1:222 | History | - 2026-10-20 (D-F1-030, COMMAND 58): GWA completed from the neighbours to the countr… | a: coberta | remover da History; permanece em D-F1-030 [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-062] |
| F1:223 | History | - 2026-10-25 (D-F1-031, COMMANDS 62b-65): ERA5 gust of IND extended (box, 1995 and t… | a: coberta | remover da History; permanece em D-F1-031 |

### F1b_data_quality_audit

| local | seção | item | classe | proposta |
|---|---|---|---|---|
| F1b:84 | Known issues | - `audit_report`'s artifact `schema_version` was bumped to `"2.1"` 2026-09-22 (main.… | a: coberta | cobre A-02, A-09 e D-F1b-002; o número da versão do schema é valor: remover |
| F1b:85 | Known issues | - `population` has no configured `expected_resolution_deg` in `config/audit.yaml` an… | e: obsoleta | obsoleta: `config/audit.yaml` hoje tem `population.expected_resolution_deg` (verificado); remover |
| F1b:86 | Known issues | - Land-cover inspection for BRA takes about 37-55 minutes **on a cold or invalidated… | a: coberta | cobre D-F1b-003 e D-F1b-018 (a causa do tempo está em D-F1b-018); tempos são dado de execução: remover |
| F1b:87 | Known issues | - **BRA F1b total runtime, corrected (task F1-3, 2026-09-23) — a prior report confla… | d: só histórico | correção de um relatório antigo; só histórico; remover (commit 240c9708, 2026-09-23) |
| F1b:88 | Known issues | - `audit_report`'s artifact `schema_version` was bumped to `"2.0"` 2026-09-21 (main.… | a: coberta | cobre A-02 e A-09; remover (versão de schema é valor) |
| F1b:89 | Known issues | - The 2026-09-22 FD4c `force_rerun` audited the corrected, geometry-filtered `land_c… | d: só histórico | rodada FD4c de 2026-09-22; só histórico; remover (commit 04c70d9b, 2026-09-22) |
| F1b:90 | Known issues | - **IND `data_quality_audit` not yet run — blocked on `parameters.json`, not a data_… | e: obsoleta | obsoleta: IND F1b está `ran_clean` em PROGRESS; remover [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-012, OQ-002] |
| F1b:92 | Known issues | - **A-08 output-location redirect owned here (2026-09-27, playbook COMMAND ADJ-8b).*… | c: pendência só aqui | o código ainda grava em `outputs/<ISO3>/audit/` (`_save_report` em `audit.py`), e A-08 pede outro local: divergência aberta; proposta de OQ-096 (F1b, Douglas, awaiting_verdict): 'Local do relatório de F1b: manter outputs/<ISO3>/audit/ e atualizar A-08, ou mover para outputs/<ISO3>/data_quality_audit/reports/ (muda o fingerprint de código de F1b)'. A conferência contra o texto exato de A-08 não foi feita aqui |
| F1b:96 | History | - WDPA "[ERROR] found (unreadable)" for PRT (`TopologyException: side location confl… | e: obsoleta | obsoleta: o erro do WDPA de PRT foi resolvido por D-F1b-001 (o texto diz); remover |
| F1b:98 | History | - **D-F1b-014 — The slope-inactivity check reads the land-availability range (2026-1… | a: coberta | a linha é a definição de D-F1b-014 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| F1b:100 | History | - **D-F1b-015 — The air-density sanity range carries a 5% quality-control tolerance … | a: coberta | a linha é a definição de D-F1b-015 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| F1b:101 | History | - **D-F1b-017 — The audit records the share of the country mask with valid data for … | a: coberta | a linha é a definição de D-F1b-017 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| F1b:102 | History | - **D-F1b-018 — Cause of the 63 s and 3,325 s of the land-cover audit of BRA; the au… | a: coberta | a linha é a definição de D-F1b-018 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| F1b:103 | History | - **D-F1b-019 — Less time and memory in the audit, with the same numbers (2026-10-30… | a: coberta | a linha é a definição de D-F1b-019 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| F1b:104 | History | - 2026-10-15 (D-F1b-016): the clip caches of the audit (`<layer>_clipped.gpkg`, the … | x: definição só aqui | D-F1b-016 só existe nesta linha (nenhuma definição em docs/phases): mover o texto para Active implementation decisions como a definição de D-F1b-016 antes de apagar a linha [D-ID citado sem definição: D-F1b-016] |
| F1b:105 | History | - 2026-10-20 (D-F1b-017, COMMAND 58): `mask_coverage_pct` for the GWA layers, alert … | a: coberta | remover da History; permanece em D-F1b-017 |
| F1b:106 | History | - 2026-10-30 (D-F1b-019, COMMANDS 75 to 79): row-block raster statistics, clip short… | a: coberta | remover da History; permanece em D-F1b-019 |

### F2a_grid_alignment

| local | seção | item | classe | proposta |
|---|---|---|---|---|
| F2a:86 | Known issues | - **M-F2a-01 resolved (G-3, 2026-10-06).** `build_reference_grid()` used to snap onl… | a: coberta | cobre M-F2a-01 e a decisão G-3; remover |
| F2a:88 | Known issues | - **Memory known issue resolved (G-5, 2026-10-06).** `reproject_to_grid()` used to c… | d: só histórico | resolvida em G-5 (2026-10-06); remover (commit 4a315566, 2026-10-06) |
| F2a:89 | Known issues | - **PRT's current `grid_alignment` output is provisional (2026-09-22).** Produced by… | e: obsoleta | obsoleta: PRT está `ran_clean` em PROGRESS; remover |
| F2a:90 | Known issues | - **PRT's `grid_alignment` manifest entry now reads `stale_upstream`, correcting a f… | e: obsoleta | obsoleta: a entrada de manifest foi refeita nas rodadas seguintes; remover |
| F2a:91 | Known issues | - **PRT's on-disk `grid_alignment` manifest entry still carries the removed `seismic… | e: obsoleta | obsoleta: campo `seismic` removido e o manifest de PRT refeito; remover |
| F2a:92 | Known issues | - **Prior finding, superseded by the entry above (kept for context — this is F-6 res… | e: obsoleta | a própria linha diz que foi superada pela anterior; remover |
| F2a:93 | Known issues | - **slope's expected-resolution expectation is now unowned (2026-09-23, see `docs/ph… | c: pendência só aqui | pendência não confirmada: a expectativa de resolução do slope não tem dono em F2a depois que F1b a retirou (D-F1b-004). Não verifiquei se existe expectativa na config de F2a; proposta de OQ-097 só se a verificação confirmar a lacuna |
| F2a:94 | Known issues | - **Slope: derived here from the DEM, not an acquired layer — confirmed 2026-09-24 (… | e: obsoleta | obsoleta: `KM_PER_DEG_LAT` não existe mais em `src` (grep) e a distância é geodésica (M-F2a-03, D-F2a-029); remover |
| F2a:98 | History | None. | e: obsoleta | remover: 'None.' não registra nada |
| F2a:99 | History | - 2026-11-06 (D-F2a-028, COMMAND 101): the slope source of D-F2a-016 and the 'one DE… | a: coberta | remover da History; permanece em D-F2a-028, D-F2a-016, D-F2a-021 |
| F2a:100 | History | - 2026-10-09: V-01 refrozen for the ZZZ land-cover bands (D-F2a-018). | a: coberta | remover da History; permanece em D-F2a-018 |
| F2a:101 | History | - 2026-10-19: contiguous mask and GLO-30 elevation (D-F2a-021); V-01 refrozen for th… | a: coberta | remover da History; permanece em D-F2a-021 |
| F2a:102 | History | - 2026-11-03 (D-F2a-026, COMMAND 89): population summed exactly by area, replacing G… | a: coberta | remover da History; permanece em D-F2a-026, D-F2a-014 |
| F2a:103 | History | - 2026-10-30 (D-F2a-022, COMMANDS 75 and 77): one pass over the GLO-30 tiles with th… | a: coberta | remover da History; permanece em D-F2a-022, D-core-044 |
| F2a:104 | History | - 2026-11-12 (D-F2a-030, COMMANDS 132 and 135): the 12 GLO30 slope rasters (`<ISO>_s… | x: definição só aqui | D-F2a-030 só existe nesta linha (nenhuma definição em docs/phases): mover o texto para Active implementation decisions como a definição de D-F2a-030 antes de apagar a linha [D-ID citado sem definição: D-F2a-030] |

### F2b_siting_layers

| local | seção | item | classe | proposta |
|---|---|---|---|---|
| F2b:48 | Known issues | - **population unit is counts per pixel, not density (confirmed 2026-09-24, ADJ-2) —… | e: obsoleta | obsoleta: o E6 passou a ser o afastamento de assentamentos GHS-SMOD (OPEN_QUESTIONS, Recently resolved: OQ-047, METHODOLOGY 17.0.0); remover [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-003, OQ-002] |
| F2b:57 | Known issues | - **Regression fixtures refrozen (G-4, 2026-10-06).** The 14-criterion legacy suite … | a: coberta | cobre D-F2a-010 e DEC-055/DEC-067; remover |
| F2b:58 | Known issues | - Parameters retired in H-2 (tier: null): criteria.slope_threshold_deg_solar, criter… | e: obsoleta | obsoleta: nenhuma das chaves `criteria.*` está em `config/parameters.json` (0 ocorrências de `slope_threshold_deg`, 0 de `normalization_min_percentile`); remover |
| F2b:59 | Known issues | - **`BiomassParams` (`core/schemas.py::BiomassParams`) added to H-2's retirement lis… | e: obsoleta | obsoleta: `BiomassParams` não existe mais em `src` (grep) e biomassa está em S-08; remover |
| F2b:60 | Known issues | - **Percentile normalization is still executing today, not removed — status correcte… | e: obsoleta | obsoleta: `normalization_min_percentile` não existe em `config/parameters.json`; remover |
| F2b:61 | Known issues | - **PRT's current `suitability_criteria` output is provisional (2026-09-22).** Produ… | e: obsoleta | obsoleta: o módulo `suitability_criteria` não existe em `src`; remover |
| F2b:62 | Known issues | - **PRT's `suitability_criteria` manifest entry now reads `stale_upstream`, correcti… | e: obsoleta | obsoleta: o módulo `suitability_criteria` não existe em `src`; remover |
| F2b:63 | Known issues | - **A-08 output-location redirect owned here, under H-2 (2026-09-27, playbook COMMAN… | e: obsoleta | obsoleta: o módulo `suitability_criteria` não existe em `src`; remover |
| F2b:67 | History | - "Still pending migration: WDPA invalid-geometry repair before clip" (2026-09-11 no… | e: obsoleta | obsoleta: a pendência foi resolvida por D-F2b-004 (o texto diz); remover |
| F2b:68 | History | - 2026-10-08: H-5 maps and H-6 statistics (D-F2b-006). | a: coberta | remover da History; permanece em D-F2b-006 |

### F3_land_eligibility

| local | seção | item | classe | proposta |
|---|---|---|---|---|
| F3:212 | Known issues | - E1-E5 are shares (E5 from 10 m class counts for the three countries, E4 from 30 m … | a: coberta | cobre D-F3-003 e D-F3-005, D-F2a-015, D-F2a-016; remover |
| F3:215 | Known issues | - Open and affecting the results: L-057 (the width of a reach is a global bankfull e… | a: coberta | cobre L-057 a L-062 e OQ-070; é lista de ponteiros, remover [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-048] |
| F3:218 | Known issues | - The IND climate_forcing, hazard_context and climate_maps entries that the grid_ali… | a: coberta | cobre D-core-024 e D-F3-010; remover |
| F3:221 | Known issues | - The V-07 table is built; the scale-check analysis is part of F7. | d: só histórico | histórico de construção da tabela V-07; sem ID próprio: remover (commit abaixo) (commit 8e4cd6dc, 2026-10-26) |
| F3:233 | History | - 2026-10-08: clean rerun of the three countries with the three scenarios and the 10… | a: coberta | remover da History; permanece em D-F3-009 |
| F3:236 | History | - 2026-10-08: scenarios and IND land-cover decisions recorded (D-F3-007, D-F3-008); … | a: coberta | remover da History; permanece em D-F3-007, D-F3-008, METHODOLOGY 7.0.0 |
| F3:239 | History | - 2026-10-07: engine built and run for PRT, IND and BRA with the central parameters … | a: coberta | remover da History; permanece em D-F3-002, METHODOLOGY 5.0.0 [D-ID citado sem definição: D-F3-004] |
| F3:242 | History | - 2026-10-08: F3 runs end to end on the synthetic country (D-F3-011); MS-5 gate met … | a: coberta | remover da History; permanece em D-F3-011 |
| F3:245 | History | - 2026-10-09: `admin1_id` added to the cell and candidate tables and `admin1_units.p… | a: coberta | remover da History; permanece em D-F3-012, METHODOLOGY 7.2.0 |
| F3:247 | History | - 2026-10-09: `pipeline.py` exposes `prepare_shared_layers` and `technology_layers` … | a: coberta | remover da History; permanece em M-F3-05, M-F7b-01 |
| F3:249 | History | - 2026-10-12: F1b, F2a, F2b and F3 rerun for PRT, IND and BRA after the content-addr… | a: coberta | remover da History; permanece em OQ-026 |
| F3:251 | History | - 2026-10-18 (D-F3-018, COMMAND 51): a cell without elevation is not a candidate (re… | a: coberta | remover da History; permanece em D-F3-018 [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-060] |
| F3:252 | History | - 2026-10-19: F3 run again on the contiguous territory and the GLO-30 elevation (D-F… | a: coberta | remover da History; permanece em D-F3-019 |
| F3:253 | History | - 2026-10-20 (D-F3-020, COMMAND 58): E1 of IND no longer depends on the grid origin. | a: coberta | remover da History; permanece em D-F3-020 |
| F3:254 | History | - 2026-10-20 (D-F3-021, COMMAND 59): the share caches follow the code of the algorit… | a: coberta | remover da History; permanece em D-F3-021 |
| F3:256 | History | - **D-F3-022 — Eligibility figures in the MapFigure standard (2026-10-26, COMMAND 68… | a: coberta | a linha é a definição de D-F3-022 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| F3:257 | History | - 2026-11-04 (D-F3-024, COMMAND 91): F3 by stripes of rows, peak of BRA from 3.6 GB … | a: coberta | remover da History; permanece em D-F3-024 |
| F3:258 | History | - 2026-11-05 (D-F3-025, COMMAND 97): the land rules of Group 6 replace the parameter… | a: coberta | remover da History; permanece em D-F3-025, D-F3-002, D-F3-007, OQ-046 (+3) [D-ID citado sem definição: D-F3-004, D-F3-006, D-F3-014] |

### F4_climate_forcing

| local | seção | item | classe | proposta |
|---|---|---|---|---|
| F4:57 | Known issues | - **ERA5 gust acquired and audited (resolved 2026-10-06, COMMAND F4-6).** BRA, IND a… | a: coberta | cobre D-F1-022 e D-F1-023; remover |
| F4:61 | History | - 2026-10-08: F4 runs on the synthetic country from miniature CMIP6 files (D-F4-019). | a: coberta | remover da History; permanece em D-F4-019 |
| F4:62 | History | - 2026-10-09: forcing and hazard cells follow the run scale (D-F4-020): `country_cel… | a: coberta | remover da History; permanece em D-F4-020 |
| F4:63 | History | - 2026-10-15 (D-F4-027, V-83): the reference of the temperature check is W5E5 v2.0, … | x: definição só aqui | D-F4-027 só existe nesta linha (nenhuma definição em docs/phases): mover o texto para Active implementation decisions como a definição de D-F4-027 antes de apagar a linha [D-ID citado sem definição: D-F4-027] |
| F4:65 | History | - **D-F4-028 — Figures in the MapFigure standard (2026-10-26, COMMAND 68).** `climat… | a: coberta | a linha é a definição de D-F4-028 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |

### F5_technical_potential

| local | seção | item | classe | proposta |
|---|---|---|---|---|
| F5:77 | Known issues | - The registry names and comments of `technologies.yaml` were wrong (Weibull A and k… | c: pendência só aqui | parte corrigida (histórico); resta que F3 ainda fixa os nomes de camada em `land_eligibility/pipeline.py::_required_resources` (verificado em `src`): pendência de código sem OQ; proposta de OQ-098 (F3, Douglas, open): 'F3 lê os nomes de camada de recurso de um dicionário próprio em vez do registro `technologies.yaml` (A-04)' |
| F5:78 | Known issues | - The METHODOLOGY section 4.1 list of support phases does not name `potential_maps` … | e: obsoleta | obsoleta: METHODOLOGY nomeia `potential_maps` (diagrama da Seção 4) e o changelog 7.2.1 registrou as fases de suporte; remover |
| F5:79 | Known issues | - F5 is registered but not in `run.target_phases`; with Group 1 recorded (D-F5-023) … | e: obsoleta | redundante: o fato está em `config/settings.yaml` (`run.target_phases` não lista `technical_potential`) e o estado de execução em PROGRESS; remover |
| F5:80 | Known issues | - OQ-060 (cells with no elevation) is closed by D-F3-018 and D-F5-028. OQ-059 is clo… | a: coberta | cobre D-F3-018, D-F5-028, D-F5-025; OQ-059 e OQ-060 resolvidas; remover [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-060, OQ-059] |
| F5:84 | History | - 2026-10-08: design report and verdicts D1 to D16; METHODOLOGY 7.1.0; `parameters.j… | a: coberta | remover da History; permanece em METHODOLOGY 7.1.0 |
| F5:85 | History | - 2026-10-08: pipeline, CF models, aggregates, table schemas and `PhaseSpec` `techni… | d: só histórico | remover; histórico recuperável no git (commit 39616b41, 2026-10-08) |
| F5:86 | History | - 2026-10-08: `potential_maps` (COG and figure) and `settings.yaml` `figures`. | d: só histórico | remover; histórico recuperável no git (commit 0be7629f, 2026-10-08) |
| F5:87 | History | - 2026-10-08: F5 on ZZZ with the real F3 and F4 output (D-F5-018); `figures` honoure… | a: coberta | remover da History; permanece em D-F5-018 |
| F5:88 | History | - 2026-10-09: F5 validates its candidate-cell inputs against the `audit.yaml` sanity… | a: coberta | remover da History; permanece em D-F5-019 |
| F5:89 | History | - **D-F5-022 — Size at BRA (2026-10-15, audit M-2).** Measured on BRA at its real si… | a: coberta | a linha é a definição de D-F5-022 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| F5:90 | History | - 2026-10-16 (D-F5-023): Group 1 values, the IEA 3.4-130 curve, the class flag, the … | a: coberta | remover da History; permanece em D-F5-023 |
| F5:91 | History | - 2026-10-16 (D-F5-024): first real run, PRT clean and IND with one failed check (OQ… | a: coberta | remover da History; permanece em D-F5-024 [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-059] |
| F5:92 | History | - 2026-10-16 (D-F5-026): OQ-053 closed with Weibull validity limits; METHODOLOGY 15.… | a: coberta | remover da History; permanece em D-F5-026, METHODOLOGY 15.0.1 [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-053] |
| F5:93 | History | - 2026-10-16 (D-F5-025): fix round; density at every altitude with an ISA consistenc… | a: coberta | remover da History; permanece em D-F5-025, METHODOLOGY 15.0.0 |
| F5:94 | History | - 2026-10-17 (D-F5-027): first complete real round, PRT, IND and BRA `ran_clean`. | a: coberta | remover da History; permanece em D-F5-027 |
| F5:95 | History | - 2026-10-18 (D-F5-028): F3 and F5 again for OQ-060; PRT identical, solar of IND and… | a: coberta | remover da History; permanece em D-F5-028 [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-060] |
| F5:96 | History | - 2026-10-19 (D-F5-029, COMMAND 52): maps of capacity and energy per cell and per st… | a: coberta | remover da History; permanece em D-F5-029 |
| F5:97 | History | - 2026-10-19 (D-F5-030, COMMAND 54): per-state limits from the central scenario, las… | a: coberta | remover da History; permanece em D-F5-030 |
| F5:98 | History | - 2026-10-19: F1 to F5 run again in PRT, IND and BRA with the contiguous mask and th… | a: coberta | remover da History; permanece em D-F5-031 |
| F5:99 | History | - 2026-10-20 (D-F5-032, COMMAND 60): maps of `potential_maps` in the common style, d… | a: coberta | remover da History; permanece em D-F5-032 |
| F5:101 | History | - **D-F5-033 — Figures in the MapFigure standard (2026-10-26, COMMAND 68).** The sta… | a: coberta | a linha é a definição de D-F5-033 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| F5:103 | History | - **D-F5-034 — The figures that answer the questions of the thesis (2026-10-26, COMM… | a: coberta | a linha é a definição de D-F5-034 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| F5:105 | History | - **D-F5-036 — The code fingerprint of F5 holds the modules that write the potential… | a: coberta | a linha é a definição de D-F5-036 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| F5:106 | History | - **D-F5-037 — The 0.01 degree display layers are COG (2026-10-27, COMMAND 73; audit… | a: coberta | a linha é a definição de D-F5-037 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| F5:107 | History | - **D-F5-035 — The 0.01° display layers are built by `potential_maps` (2026-10-27, C… | a: coberta | a linha é a definição de D-F5-035 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| F5:109 | History | - **D-F5-038 — The wind capacity factor is evaluated per 0.01 degree pixel and aggre… | a: coberta | a linha é a definição de D-F5-038 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| F5:110 | History | - **D-F5-039 — The wind capacity-factor integral is read from a table (2026-10-30, C… | a: coberta | a linha é a definição de D-F5-039 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| F5:111 | History | - 2026-10-30 (D-F5-039, COMMAND 75): wind CF integral by table with the exact mode k… | a: coberta | remover da History; permanece em D-F5-039, METHODOLOGY 15.3.1 |
| F5:112 | History | - 2026-11-04 (D-F5-040, COMMAND 95): the identity check of the display layers follow… | a: coberta | remover da History; permanece em D-F5-040 |

### F6_lcoe_modeling

| local | seção | item | classe | proposta |
|---|---|---|---|---|
| F6:72 | Known issues | - OQ-001 (grid, substation and road costs) and OQ-019 (degradation) keep F6 from a f… | e: obsoleta | obsoleta: OQ-001 fechada com proxies (COMANDO 86), as chaves citadas foram renomeadas (M-F6-08); remover [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-019] |
| F6:73 | Known issues | - **For Group 3 (OQ-001): does the IRENA 2024 total installed cost include grid conn… | a: coberta | cobre M-F6-08 e L-051; remover |
| F6:74 | Known issues | - `sample_size_convergence` uses F7's definitive MR. The synthetic run proves the me… | d: só histórico | dado de uma execução sintética (32 amostras); só histórico; remover (commit 87e0d037, 2026-10-09) |
| F6:75 | Known issues | - The draws of different sizes are independent, not nested, so the Jaccard distance … | b: limitação só aqui | nenhuma L cobre (grep 'nested' em LIMITATIONS: 0); texto de L proposto (origem U-04, F6 `sample_size_convergence`): 'Os sorteios de tamanhos diferentes são independentes, não aninhados; a distância de Jaccard de U-04 inclui ruído de amostragem.' |
| F6:79 | History | - 2026-10-09: design report, verdicts D1 to D16, METHODOLOGY 7.1.2, parameter keys a… | a: coberta | remover da History; permanece em METHODOLOGY 7.1.2 |
| F6:80 | History | - 2026-10-09: commit A, the pure LCOE kernel with its V-02 closed-form tests. | d: só histórico | remover; histórico recuperável no git (commit e3554bad, 2026-10-09) |
| F6:81 | History | - 2026-10-09: commit B, summaries, design matrix, supply curves, `PhaseSpec` `lcoe_m… | d: só histórico | remover; histórico recuperável no git (commit 5dd96b32, 2026-10-09) |
| F6:82 | History | - 2026-10-09: METHODOLOGY 7.1.3 (M-F7-03 draws only, U-04 criterion approved, OQ-055… | a: coberta | remover da History; permanece em METHODOLOGY 7.1.3, M-F7-03 [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-055, OQ-054] |
| F6:83 | History | - 2026-10-09: commit C, support phase `sample_size_convergence` (U-04) with a provis… | d: só histórico | remover; histórico recuperável no git (commit ef55c9f8, 2026-10-09) |
| F6:84 | History | - 2026-10-09: `lcoe_nominal_<tech>__<scenario>` for the restrictive and permissive l… | a: coberta | remover da History; permanece em D-F6-018 |
| F6:85 | History | - 2026-10-09: `lcoe_maps` support phase (T-R11 diagnostic), METHODOLOGY 7.2.1; the s… | a: coberta | remover da History; permanece em METHODOLOGY 7.2.1 |
| F6:86 | History | - 2026-10-09: `sample_size_convergence` runs on F7's `MR`; `provisional_regret.py` d… | d: só histórico | remover; histórico recuperável no git (commit 87e0d037, 2026-10-09) |
| F6:87 | History | - **D-F6-020 — Size at BRA (2026-10-15, audit M-2).** Measured on BRA at its real si… | a: coberta | a linha é a definição de D-F6-020 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| F6:88 | History | - 2026-10-16 (D-F6-021): Group 2 values recorded (CAPEX, fixed and variable O&M, lif… | a: coberta | remover da History; permanece em D-F6-021 |
| F6:89 | History | - 2026-10-16 (D-F6-022): discount rate recorded (OQ-022 closed), t_ref 2024, discret… | a: coberta | remover da History; permanece em D-F6-022, METHODOLOGY 15.0.0 [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-022] |
| F6:91 | History | - **D-F6-029 — A country with no eligible substation is refused by name; there is no… | a: coberta | a linha é a definição de D-F6-029 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| F6:93 | History | - **Figures (2026-10-26, COMMAND 68).** The LCOE maps and the supply curve use the c… | d: só histórico | remover; histórico recuperável no git (commit 8e4cd6dc, 2026-10-26) |

### F7_robustness_analysis

| local | seção | item | classe | proposta |
|---|---|---|---|---|
| F7:113 | Known issues | - Nothing in F7 runs on a real country until the F5 and F6 values exist (OQ-004, OQ-… | e: obsoleta | estado de execução; vive em PROGRESS; as OQ citadas estão no OPEN_QUESTIONS; remover [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-004, OQ-005, OQ-023] |
| F7:114 | Known issues | - The synthetic world is spatially uniform in resource and forcing (only the distanc… | b: limitação só aqui | nenhuma L cobre (grep 'uniform' só acha L de outros temas); texto de L proposto (origem F7, mundo ZZZ): 'O mundo sintético é espacialmente uniforme em recurso e forçante; os testes exercitam o mecanismo, não os resultados espaciais.' |
| F7:118 | History | - 2026-10-09: F7-A: the kernel energy floor, the neutral `lcoe_modeling/inputs.py`, … | d: só histórico | remover; histórico recuperável no git (commit e55d6158, 2026-10-09) |
| F7:119 | History | - 2026-10-09: design report, verdicts D1 to D28, METHODOLOGY 7.2.0, decision paramet… | a: coberta | remover da History; permanece em METHODOLOGY 7.2.0, OQ-057 [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-056] |
| F7:120 | History | - 2026-10-09: F7-B: the sample-major pass, the H1 to H5 statistics with the rules re… | d: só histórico | remover; histórico recuperável no git (commit 365830a8, 2026-10-09) |
| F7:121 | History | - 2026-10-09: F7-C: own PRIM with the stored `ema_workbench` reference, `prim_boxes`… | d: só histórico | remover; histórico recuperável no git (commit fb09eb7e, 2026-10-09) |
| F7:122 | History | - 2026-10-09: `robustness_maps` support phase (T-R4 diagnostic), METHODOLOGY 7.2.1. | a: coberta | remover da History; permanece em METHODOLOGY 7.2.1 |
| F7:123 | History | - 2026-10-09: `sample_size_convergence` uses the definitive `MR` (D-F7-027); the pro… | a: coberta | remover da History; permanece em D-F7-027 |
| F7:124 | History | - 2026-10-13: H1 pre-registered (OQ-050, part H1), METHODOLOGY 8.0.0; `h1_rank_robus… | a: coberta | remover da History; permanece em METHODOLOGY 8.0.0 [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-050] |
| F7:125 | History | - 2026-10-13: H2 pre-registered (OQ-050, part H2), METHODOLOGY 9.0.0; `h2_aggregatio… | a: coberta | remover da History; permanece em METHODOLOGY 9.0.0, D-F7-042 [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-050] |
| F7:126 | History | - 2026-10-13: D-F7-042 closed: `N = \|I_0\|` in the H1 and H2 texts and in M-F7-07 (… | a: coberta | remover da History; permanece em D-F7-042, M-F7-07, METHODOLOGY 9.0.1 |
| F7:127 | History | - 2026-10-13: H3 pre-registered (OQ-050, part H3), METHODOLOGY 10.0.0; `h3_robust_vs… | a: coberta | remover da History; permanece em METHODOLOGY 10.0.0 [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-050] |
| F7:128 | History | - 2026-10-13: H4 pre-registered (OQ-050, part H4), METHODOLOGY 11.0.0; `h4_axis_domi… | a: coberta | remover da History; permanece em METHODOLOGY 11.0.0 [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-050] |
| F7:129 | History | - 2026-10-14: H5 pre-registered (OQ-050, part H5), METHODOLOGY 12.0.0; `h5_climate_p… | a: coberta | remover da History; permanece em METHODOLOGY 12.0.0 [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-050] |
| F7:130 | History | - 2026-10-14: scenario discovery pre-registered (OQ-056), METHODOLOGY 13.0.0: the ou… | a: coberta | remover da History; permanece em METHODOLOGY 13.0.0 [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-056] |
| F7:131 | History | - 2026-10-14: METHODOLOGY 13.0.1: H5b over the channels that have a threshold (D-F7-… | a: coberta | remover da History; permanece em METHODOLOGY 13.0.1, D-F7-058, D-F7-059, D-F7-060 |
| F7:132 | History | - **D-F7-063 — Size at BRA (2026-10-15, audit M-2).** Measured on BRA at its real si… | a: coberta | a linha é a definição de D-F7-063 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| F7:134 | History | - **Figures (2026-10-26, COMMAND 68).** The robustness maps use the common style (`<… | d: só histórico | remover; histórico recuperável no git (commit 8e4cd6dc, 2026-10-26) |

### F7b_external_validation

| local | seção | item | classe | proposta |
|---|---|---|---|---|
| F7b:36 | Known issues | - Published estimates for M-F7b-03 have no source yet (OQ-057). | a: coberta | cobre OQ-057; remover |
| F7b:37 | Known issues | - Nothing in F7b runs on a real country until the real plant inventory is acquired (… | e: obsoleta | estado de execução; vive em PROGRESS; remover |
| F7b:38 | Known issues | - The ZZZ pixels are uniform in slope and almost so in the other layers: the hand co… | b: limitação só aqui | mesma limitação de F7:114 (mundo ZZZ quase uniforme); uma L só para as duas, com origem F7 e F7b |
| F7b:42 | History | - 2026-10-09: verdicts D18 to D22 of the F7 design report recorded; no phase code. | d: só histórico | remover; histórico recuperável no git (commit 212b31bb, 2026-10-09) |
| F7b:43 | History | - 2026-10-09: F7b built on the synthetic country: exclusion shares at the plant pixe… | d: só histórico | remover; histórico recuperável no git (commit bd2bf485, 2026-10-09) |
| F7b:44 | History | - **D-F7b-007 — Size at BRA (2026-10-15, audit M-2).** Measured on BRA at its real s… | a: coberta | a linha é a definição de D-F7b-007 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |

### F8_results_synthesis

| local | seção | item | classe | proposta |
|---|---|---|---|---|
| F8:61 | Known issues | - The LaTeX tables and the PDF figures have not been compiled in an environment with… | c: pendência só aqui | nenhuma OQ nem L cobre (grep em OPEN_QUESTIONS, LIMITATIONS e PROGRESS: 0); proposta de OQ-099 (F8, Douglas, open): 'As tabelas LaTeX e as figuras PDF não foram compiladas com um motor TeX' |
| F8:62 | Known issues | - Needs real values (the scripts run on ZZZ): T-R1, T-R3, T-R4, T-R5 and T-R11 and e… | e: obsoleta | estado de execução; as OQ citadas estão no OPEN_QUESTIONS; remover [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-004, OQ-005, OQ-023] |
| F8:63 | Known issues | - The real thesis build needs the real F5 to F7b runs, the national targets of OQ-01… | a: coberta | cobre OQ-010 e OQ-051; remover |
| F8:67 | History | - 2026-10-13: design report verdicts D1, D4, D5, D7, D8, D9, D10 accepted as recomme… | d: só histórico | remover; histórico recuperável no git (commit 5fce6418, 2026-10-13) |
| F8:68 | History | - 2026-10-13: T-R6 reads the H1, H2 and H3 summaries and adds the verdict table (D-F… | a: coberta | remover da History; permanece em D-F8-011 |
| F8:69 | History | - 2026-10-13: T-R6 gains the H4 row, T-R7 is built from the tables of `cross_country… | a: coberta | remover da History; permanece em D-F8-012 |
| F8:70 | History | - 2026-10-14: T-R6 gains the H5 row (two statistics, as H1), T-R10 and T-R12 are che… | a: coberta | remover da History; permanece em D-F8-013 |
| F8:71 | History | - 2026-10-14: T-R8 (profiles, summary and readable country summary) and T-O1 built; … | a: coberta | remover da History; permanece em D-F8-014, D-F8-017 |
| F8:72 | History | - 2026-10-14: T-R1, T-R3, T-R4, T-R5, T-R11 and T-M1 built; D2 closed (D-F8-018 to D… | a: coberta | remover da History; permanece em D-F8-018, D-F8-021 |
| F8:73 | History | - **D-F8-025 — Size at BRA (2026-10-15, audit M-2).** Measured on BRA at its real si… | a: coberta | a linha é a definição de D-F8-025 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |

### core

| local | seção | item | classe | proposta |
|---|---|---|---|---|
| core:130 | Known issues | - **`data_quality_audit/audit.py` keeps its own tuple of technologies (`_TECHNOLOGIE… | c: pendência só aqui | verificado: `_TECHNOLOGIES = ("solar", "wind")` ainda está em `data_quality_audit/audit.py`; pendência de código sem OQ; proposta de OQ-100 (core, Douglas, open): 'F1b lê as tecnologias de uma tupla própria em vez do registro (A-04, S-02)' |
| core:131 | Known issues | - **The default country-run expansion still derives from `config/parameters.json`, n… | c: pendência só aqui | verificado: `main.py` ainda deriva `default_countries` de `parameters.countries`; pendência sem OQ; proposta de OQ-101 (core, Douglas, open): 'A expansão padrão de países deve vir de `config/countries.yaml`, não de `parameters.json`' |
| core:133 | Known issues | - **`build_reference_grid()`'s floor/ceil snapping is not robust to floating-point n… | e: obsoleta | obsoleta: resolvida por G-3 (F2a_grid_alignment:86, M-F2a-01); remover |
| core:135 | Known issues | - **Deferred to playbook task G-3 (Douglas, 2026-09-21):** Remove duplicated Pydanti… | e: obsoleta | obsoleta: o modo `adaptive` foi removido em G-3 (comentário em `core/schemas.py`); remover |
| core:136 | Known issues | - Five `criteria.*` parameters are validated but never read. | e: obsoleta | obsoleta: `criteria.*` não está em `config/parameters.json`; remover |
| core:137 | Known issues | - F2b (`suitability_criteria`) registers only one artifact for its whole output mode… | e: obsoleta | obsoleta: o módulo `suitability_criteria` não existe em `src`; F2b é `siting_layers`; remover |
| core:138 | Known issues | - F2a's `produces` hardcodes 11 raster keys (`main.py::_ALIGNED_RASTER_LAYER_KEYS`, … | c: pendência só aqui | `_ALIGNED_RASTER_LAYER_KEYS` ainda existe em `main.py` (com a tupla de opcionais); a premissa do texto (IND, seismic, OQ-012) está resolvida; não verifiquei se um país sem uma das 11 entradas ainda falha: pendência não confirmada, sem OQ proposta [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-012] |
| core:139 | Known issues | - `StaleManifestEntryError`/`consumed_run_ids` lineage only cover phases registered … | c: pendência só aqui | `produces_schema_versions` é declarado só em `main.py` para o registro de camadas e o relatório de F1b (verificado por grep); as outras fases não declaram: pendência sem OQ; proposta de OQ-102 (core, Douglas, open): 'Fases além de F1 e F1b não declaram `produces_schema_versions`; uma mudança de schema de saída exige bump manual' |
| core:147 | History | - **D-core-017 — Synthetic country fixture generated for A-06/V-08 (2026-09-24, play… | a: coberta | a linha é a definição de D-core-017 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-032] |
| core:148 | History | - **D-core-049 — Performance of the pipeline without a change of result: what the in… | a: coberta | a linha é a definição de D-core-049 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| core:149 | History | - **D-core-050 — Deferred content check of IND and BRA against a reference manifest … | a: coberta | a linha é a definição de D-core-050 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| core:150 | History | - **D-core-051 — The reference store, and the check by tolerance (2026-11-04, COMMAN… | a: coberta | a linha é a definição de D-core-051 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| core:151 | History | - **D-core-052 — Resume after an interruption, and the write mechanics outside the f… | a: coberta | a linha é a definição de D-core-052 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| core:152 | History | - **D-core-053 — The code fingerprints hash a text that does not depend on the Pytho… | a: coberta | a linha é a definição de D-core-053 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| core:153 | History | - **D-core-054 — The reference moves only by an explicit publication that gates ever… | a: coberta | a linha é a definição de D-core-054 dentro de History; mover para Active implementation decisions (ou apagar se a definição já está lá) |
| core:155 | History | - D-core-005 (E2 draft design for A-01/A-02/A-03/A-09, "awaiting verdict") — approve… | a: coberta | cobre D-core-005 (o texto diz 'approved'); remover |
| core:156 | History | - "Draft decision — force_rerun semantics (awaiting verdict, 2026-09-22)" — approved… | a: coberta | cobre a decisão de `force_rerun` implementada (a linha cita o D-ID); remover |
| core:157 | History | - WDPA "[ERROR] found (unreadable)" for PRT (`TopologyException: side location confl… | e: obsoleta | obsoleta: mesmo caso de F1b:96, resolvido por D-F1b-001; duplicata entre registros; remover |
| core:158 | History | - 2026-10-09: the cell scale of a run (`core/scale.py`, D-F3-013): `run_geofrea(scal… | a: coberta | remover da History; permanece em D-F3-013, METHODOLOGY 7.2.0 |
| core:159 | History | - 2026-10-18 (D-core-041, COMMAND 51): manifest 2.5 and the configuration fingerprin… | a: coberta | remover da History; permanece em D-core-041 |
| core:160 | History | - 2026-10-18 (D-core-041, COMMAND 51): the fingerprint was applied to the real manif… | a: coberta | remover da History; permanece em D-core-041 |
| core:161 | History | - 2026-10-19 (COMMAND 54): diagnostics of the coverage of the outline and of the ali… | a: coberta | remover da History; permanece em L-045, L-046 [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-061] |
| core:162 | History | - 2026-10-19 (COMMAND 55): contiguous mask and GLO-30 elevation, `docs/phases/core/g… | a: coberta | remover da History; permanece em L-045, L-046, L-047 [OQ fora do OPEN_QUESTIONS (resolvida e removida): OQ-061] |
| core:163 | History | - 2026-10-20 (D-core-042, COMMAND 58): manifest 2.6, code fingerprint per phase and … | a: coberta | remover da History; permanece em D-core-042 |
| core:164 | History | - 2026-10-21 (D-core-043, COMMAND 61): fingerprint granularity and the code in every… | a: coberta | remover da History; permanece em D-core-043 |
| core:165 | History | - 2026-10-22 (D-core-044, COMMAND 64): restamp of internal caches rejected; branch `… | a: coberta | remover da History; permanece em D-core-044 |
| core:166 | History | - 2026-10-26 (D-core-045, COMMAND 66): `mapstyle.py` becomes `MapFigure`: fixed layo… | a: coberta | remover da History; permanece em D-core-045 |
| core:167 | History | - 2026-10-26 (D-core-047, COMMAND 67b): display resolution: the display layers at 0.… | a: coberta | remover da History; permanece em D-core-047 |
| core:168 | History | - 2026-10-26 (D-core-046, COMMAND 67): `MapFigure` in LAEA with a clipped raster, co… | a: coberta | remover da History; permanece em D-core-046 |
| core:169 | History | - 2026-10-30 (D-core-049, COMMANDS 75, 77, 79): performance without a change of resu… | a: coberta | remover da History; permanece em D-core-049 |
| core:170 | History | - 2026-10-30 (D-core-050, COMMAND 80): deferred content check of IND and BRA against… | a: coberta | remover da History; permanece em D-core-050 |
| core:171 | History | - 2026-10-30 (D-core-044, D-core-050, COMMAND 81): the revision under which the alig… | a: coberta | remover da History; permanece em D-core-044, D-core-050 |
| core:172 | History | - 2026-11-04 (D-core-051, COMMAND 91): the reference store of accepted rounds; the d… | a: coberta | remover da History; permanece em D-core-051 |
| core:173 | History | - 2026-11-05 (D-core-052, COMMAND 98): resume after an interruption: `core/checkpoin… | a: coberta | remover da History; permanece em D-core-052 |

## 2. Conformance: colunas propostas e linha a linha

Colunas propostas para todas as tabelas: **Item | Requirement | Implementation (module:function) | Test | Status (pass, partial, fail, n/a)**. As tabelas de F3, F4, F5, F6, F7, F7b, F8 e E1 já têm essas colunas; F1, F1b, F2a e core têm 'Current state' no lugar de Implementation e Test e precisam ser convertidas; F2b tem outro formato (seção 3). E5b não tem tabela de Conformance.

### F1_data_acquisition

| local | Item | Requirement | Implementation | Test | Status proposto | ação |
|---|---|---|---|---|---|---|
| F1:13 | M-F1-01 | Registry with provenance | proposto: data_acquisition/schemas.py::AcquiredLayer.fetch_status; data_acquisition/phase.py::run_acquisition… | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| F1:14 | M-F1-02 | Active layer set | proposto: AuditInputs; GridAlignmentInputs | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| F1:15 | M-F1-03 | GWA Weibull A/k, air density, wind speed at 100/150/200 m | proposto: fetchers/wind.py::fetch_gwa_product() | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| F1:16 | M-F1-04 | CMIP6 monthly rsds/tas/sfcWind and daily tasmax/pr | proposto: fetchers/cmip6.py; cmip6_registry.py; AcquiredLayer | não encontrado | partial | converter a coluna 'Current state' em Implementation e Test |
| F1:17 | M-F1-05 | ERA5 gust, annual max of `fg10`, 1995-2014 | proposto: fetchers/era5.py; era5_registry.py; scripts/acquire_era5_gust.py | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| F1:18 | M-F1-06 | GEM solar and wind trackers | ok | ok | pass — acquired and clipped; the consumer is F7b `external_validat… | manter colunas |
| F1:19 | M-F1-07 | GADM local-first with checksum | proposto: fetchers/gadm.py::_local_database_level0(); GadmChecksumMismatchError \| citação sem símbolo no cód… | proposto: test_fetchers_gadm.py::test_fetch_borders_local_database_hit_performs_no_network_call; test_fetch_b… | pass | converter a coluna 'Current state' em Implementation e Test |
| F1:20 | A-05 | Country mappings in config | proposto: local_layers.py::_load_countries_config(); fetchers/hydrosheds.py::_get_hydrosheds_region() | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |

### F1b_data_quality_audit

| local | Item | Requirement | Implementation | Test | Status proposto | ação |
|---|---|---|---|---|---|---|
| F1b:13 | M-F1b-01 | Expected resolutions and sanity ranges in configuration | proposto: audit.py; AuditConfig; run_audit_phase(..., audit_config=...) | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| F1b:14 | M-F1b-01 | PVOUT unit reported as kWh/kWp/day | proposto: solar.unit | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| F1b:15 | M-F1b-01 | Wind expected resolution matches GWA native grid | não encontrado | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| F1b:16 | M-F1b-01 | Audit covers new layers (Weibull, air density, CMIP6, ERA5, GEM) | não encontrado | não encontrado | partial | converter a coluna 'Current state' em Implementation e Test |
| F1b:17 | M-F1b-01 | Audit runs for every acquired country | proposto: run_audit_phase | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| F1b:18 | M-F1b-02 | Reports, never blocks | proposto: data_quality_audit/audit.py:run_audit_phase; AuditInputs | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| F1b:19 | A-02 (vector clip path) | Invalid-geometry repair unconditional for every clip-path caller, not… | proposto: vector_inspection.py::_read_clipped_with_cache; core/geo_utils.py::read_clipped_to_country; inspect… | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |

### F2a_grid_alignment

| local | Item | Requirement | Implementation | Test | Status proposto | ação |
|---|---|---|---|---|---|---|
| F2a:13 | M-F2a-07 | Slope as a distribution of 1 degree bins from the 30 m samples of FAB… | proposto: fetchers/fabdem.py; grid_alignment/fabdem_slope.py; layers.build_fabdem_slope \| citação sem símbol… | proposto: test_fabdem_slope_layer.py | partial — built, awaiting the round of PRT, IND and BRA (COMMAND 101,… | converter a coluna 'Current state' em Implementation e Test |
| F2a:14 | M-F2a-08 | The aligned elevation is GLO-30 and does not depend on the slope sour… | proposto: layers.build_glo30 | proposto: test_the_code_fingerprint_in_the_key_of_the_elevation_layer_is_the_one_it_had_before_command_101 | pass | converter a coluna 'Current state' em Implementation e Test |
| F2a:15 | M-F2a-01 | 0.01 degree grid snapped for exact 5 x 5 nesting | proposto: reference_grid.py:build_reference_grid(..., nesting_pixels=5) \| citação sem símbolo no código: tes… | proposto: test_grid_alignment_reference_grid.py | pass | converter a coluna 'Current state' em Implementation e Test |
| F2a:16 | M-F2a-02 | Geodesic distances, areas, and slope | proposto: derive_slope_from_dem(); core.geodesy.wgs84_km_per_degree() | proposto: test_derive_slope_uses_geodesic_spacing_at_high_latitude | pass | converter a coluna 'Current state' em Implementation e Test |
| F2a:17 | M-F2a-03 | Raw geodesic distances to the exact features; `distance_cap_km` only … | proposto: vector_alignment.py:rasterize_linear_distance; align_rivers; feature_vertices \| citação sem símbol… | proposto: test_grid_alignment_vector_alignment.py | pass | converter a coluna 'Current state' em Implementation e Test |
| F2a:18 | M-F2a-04 | Per-height wind alignment, no cross-height combination | proposto: alignment.py; reproject_to_grid() \| citação sem símbolo no código: main.py::_WIND_LAYER_KEYS | proposto: test_run_grid_alignment_phase_aligns_each_wind_height_on_its_own_without_combining | pass | converter a coluna 'Current state' em Implementation e Test |
| F2a:19 | V-01 | Frozen parity for aligned rasters | não encontrado \| citação sem símbolo no código: tests/regression/test_v01_frozen.py | proposto: test_v01_frozen.py | pass | converter a coluna 'Current state' em Implementation e Test |
| F2a:20 | CONVENTIONS | no duplicated defaults | não encontrado | proposto: test_geospatial_values_have_no_schema_defaults_and_adaptive_mode_is_gone | pass | converter a coluna 'Current state' em Implementation e Test |
| F2a:21 | M-F2a-09 | Point of interconnection: nearest OSM substation at or above the coun… | proposto: grid_alignment/poi.py:select_poi; alignment.py \| citação sem símbolo no código: tests/unit/test_gr… | proposto: test_grid_alignment_poi.py | pass? — built with the polygon substations (D-F2a-024), not run on … | converter a coluna 'Current state' em Implementation e Test |
| F2a:22 | M-F2a-11 | Settlement class of each pixel from GHS-SMOD R2023A (2020, 1 km, Moll… | proposto: grid_alignment/layers.py:build_settlements; alignment.py; adapter.py:_settlements_path \| citação s… | proposto: test_land_eligibility_pipeline.py | pass? — built and measured on PRT and BRA (peak 315 MB, 4.1 s on BR… | converter a coluna 'Current state' em Implementation e Test |
| F2a:23 | M-F2a-10 | Distance to the road counts primary and secondary classes | proposto: vector_alignment.py:filter_road_classes \| citação sem símbolo no código: tests/unit/test_grid_alig… | proposto: test_grid_alignment_vector_alignment.py | partial — built, not run | converter a coluna 'Current state' em Implementation e Test |

### F3_land_eligibility

| local | Item | Requirement | Implementation | Test | Status proposto | ação |
|---|---|---|---|---|---|---|
| F3:37 | M-F3-01 | Eligible share of a pixel = valid x (1-E1)...(1-E6), no missing value… | ok | ok | pass | manter colunas |
| F3:40 | M-F3-02 | Three named scenarios (central, restrictive, permissive) with one exp… | ok | ok | pass — on ZZZ and ZZZ2 (synthetic); IND and BRA rerun (D-F3-028), … | manter colunas |
| F3:43 | M-F3-03 | 5 x 5 aggregation: areas, excluded area per constraint, dominant excl… | ok | ok | pass | manter colunas |
| F3:46 | M-F3-03, D-F3-012 | `admin1_id` per cell: the GADM level-1 unit with the largest overlap,… | ok | ok | pass | manter colunas |
| F3:49 | M-F3-04 | A cell is a candidate with any eligible area, an elevation and, for w… | ok | não encontrado (a célula não cita teste) | pass | manter colunas |
| F3:50 | M-F3-07 | Minimum eligible area: pixel floor, then clusters of 8-connected pixe… | ok | ok | pass | manter colunas |
| F3:53 | M-F3-05 | `candidates_<tech>.parquet`, pixel and cell eligibility rasters, domi… | ok | ok | pass — `table_schemas.py:CellRow` and `write_table`, A-07 | manter colunas |
| F3:56 | M-F3-06, D-F3-013 | The cell size is the run's `scale`: the same aggregation at 0.05 and … | ok | ok | pass — the scale-check analysis itself is F7 | manter colunas |
| F3:59 | V-03 | eligible area <= cell area; cell total = pixel total | ok | ok | pass | manter colunas |

### F4_climate_forcing

| local | Item | Requirement | Implementation | Test | Status proposto | ação |
|---|---|---|---|---|---|---|
| F4:13 | M-F4-03 | Delta-change factors from monthly climatologies (ratio rsds/sfcWind, … | ok | ok | pass — PRT built; IND, BRA see D-F4-013 | manter colunas |
| F4:14 | M-F4-04, D-F4-020 | Bilinear interpolation of the factors to the cell centers of the run … | ok | não encontrado (a célula não cita teste) | pass — PRT built | manter colunas |
| F4:15 | M-F4-01 | Members `(gcm, ssp, window)` plus the reference member | ok | ok | pass | manter colunas |
| F4:16 | M-F4-05 | Hazard context indicators per cell and member | ok | ok | partial — core window only; 2071-2100 data not acquired; loss functio… | manter colunas |
| F4:17 | M-F4-06 | `forcing.parquet`, `forcing_masked.parquet`, `hazard_context.parquet`… | ok | não encontrado (a célula não cita teste) | pass — core window | manter colunas |
| F4:18 | M-F4-07 | Validity mask for `delta_wind` | ok | ok | pass | manter colunas |

### F5_technical_potential

| local | Item | Requirement | Implementation | Test | Status proposto | ação |
|---|---|---|---|---|---|---|
| F5:13 | M-F5-01 | `P_MW = eligible_area_km2 * LUF * PD` | ok | ok | pass | manter colunas |
| F5:14 | M-F5-02 | Solar `CF0 = pvout / 24`; member `CF0 * delta_rsds * (1 + gamma * dT)` | ok | ok | pass | manter colunas |
| F5:15 | M-F5-03 | Power-law `A_H`, linear `k_H` and `rho_H`; no extrapolation | ok | ok | pass | manter colunas |
| F5:16 | M-F5-03 | Density folded into the scale; exact piecewise-linear Weibull integra… | ok | ok | pass | manter colunas |
| F5:17 | M-F5-03 | Power curve file, validation, hash, synthetic refused in production (… | ok | ok | pass | manter colunas |
| F5:18 | M-F5-05 | `E = P_MW * CF * 8760` | não encontrado: core/constants.py:HOURS_PER_YEAR | ok | pass — the value 8760 awaits the author's check in the diff, D-F5-… | manter colunas |
| F5:19 | D-F5-008 | Rescale of the stored CF to another `gamma` or `eta_loss` | não encontrado: rescale.py:rescale_cf_wind | não encontrado (a célula não cita teste) | pass | manter colunas |
| F5:20 | V-02 | Weibull CF against integration; PVOUT units; power-law interpolation | sem símbolo citado (conferir) | ok | pass | manter colunas |
| F5:21 | M-F5-03 | IEC class per cell from the mean speed at hub height in the reference… | não encontrado: iec_class.py:assign_by_mean_speed, config_schemas.py:IecClassBound | não encontrado: test_class_follows_the_mean_speed_with_the_last_class_unbounded, test_class_rule_rejects_malf… | pass | manter colunas |
| F5:22 | A-04 | CF model chosen by the registry string; resource columns and required… | não encontrado: cf_models.py:CF_MODELS | ok | pass | manter colunas |
| F5:23 | M-F4-07 | `assert_forcing_usable` before any computation; a declared masked cel… | ok | não encontrado: test_declared_masked_cell_member_has_no_row_and_is_counted, test_wind_factor_out_of_range_in_… | pass | manter colunas |
| F5:24 | M-F5-06 | `potential_<tech>__<scenario>.parquet` for the three land scenarios; … | ok | ok | pass | manter colunas |
| F5:25 | V-03 | `0 <= CF <= 1`; `P_MW` equal across members; country capacity equals … | ok | ok | pass | manter colunas |
| F5:26 | A-09 | Absent parameters, curves or class rule raise `MissingParameterError`… | ok | não encontrado: test_real_countries_fail_loud_listing_the_missing_parameters_and_write_nothing | pass | manter colunas |
| F5:27 | A-02, D-F5-009, D-F5-010 | Parameters, curve hash, `rho0`, hours, integration method and `c2_app… | ok | ok | pass | manter colunas |
| F5:28 | A-01, A-03 | `PhaseSpec` `technical_potential` (requires `land_eligibility`, `forc… | ok | ok | pass | manter colunas |
| F5:29 | A-06, V-08 | Synthetic country runs F5 end to end (D-F5-013: candidate tables and … | não encontrado: tests/unit/test_technical_potential_pipeline.py | ok | pass — candidate tables and forcing built in the test; the real F3… | manter colunas |
| F5:30 | T-R1, D-F5-015 | COG of `P_MW / cell_area_km2` and of `CF` at `m0` (central scenario) … | ok | ok | pass | manter colunas |
| F5:31 | A-06, V-08 | F1 to F5 on the synthetic country with F3 and F4 run for real (D-F5-0… | não encontrado: tests/synthetic/test_zzz_end_to_end.py | ok | pass | manter colunas |

### F6_lcoe_modeling

| local | Item | Requirement | Implementation | Test | Status proposto | ação |
|---|---|---|---|---|---|---|
| F6:13 | M-F6-01 | LCOE per cell and sample from CAPEX (plant, grid, substation, road), … | ok | ok | pass | manter colunas |
| F6:14 | V-02 | Closed forms: without degradation and with constant OPEX the LCOE is … | não encontrado: kernel.py:lcoe_direct | ok | pass | manter colunas |
| F6:15 | D-F6-007 | Zero energy gives `+inf`, not an error; a negative or non-finite ener… | ok | ok | pass | manter colunas |
| F6:16 | D-F6-010 | Integer lifetime; zero discount rate by the limit, with no division b… | ok | ok | pass | manter colunas |
| F6:17 | M-F6-05 | The kernel is a pure function importable by F7: arrays in, arrays out… | ok | ok | pass | manter colunas |
| F6:18 | M-F6-04 | Per member, cells in blocks with all samples of a block in memory; ex… | ok | ok | pass | manter colunas |
| F6:19 | A-10, D-F6-005 | Cells per block from `memory.max_batch_gb`; the allocations of the lo… | não encontrado: pipeline.py:cells_per_block | ok | pass | manter colunas |
| F6:20 | D-F6-007 | Zero energy: `+inf`, quantiles kept, mean and variance over the finit… | ok | ok | pass | manter colunas |
| F6:21 | M-F6-02, D-F6-010 | Latin hypercube design with the recorded seed, sample 0 the nominal v… | ok | ok | pass | manter colunas |
| F6:22 | M-F6-01, V-03 | At `s0` the rescale factor is 1 and the LCOE is that of the stored F5… | não encontrado: pipeline.py:read_member_inputs | ok | pass | manter colunas |
| F6:23 | M-F6-06, D-F6-013 | `lcoe_summary_<tech>`, `design_matrix_<tech>`, `supply_curve_<tech>`;… | ok | ok | pass | manter colunas |
| F6:24 | A-09, D-F6-008 | Missing values, ranges, price years, ranges outside the kernel domain… | não encontrado: pipeline.py:resolve_technology_costs | não encontrado: test_real_countries_fail_loud_listing_the_missing_parameters_ranges_and_price_years | pass | manter colunas |
| F6:25 | M-F6-06, D-F6-018 | `lcoe_nominal_<tech>__<scenario>` for the restrictive and permissive … | ok | ok | pass | manter colunas |
| F6:26 | M-F7-01, D-F7-007 | The kernel takes an optional energy floor per cell (`min_energy_mwh`)… | ok | ok | pass | manter colunas |
| F6:27 | D-F7-026 | The resolution of parameters and the readers of the F3, F4 and F5 tab… | ok | não encontrado: test_lcoe_convergence.py | pass | manter colunas |
| F6:28 | A-04 | No technology name in the package; the energy rescale comes from the … | não encontrado: cf_models.py:CfModel.sampled_parameter_key | ok | pass | manter colunas |
| F6:29 | A-01, A-02 | `PhaseSpec` `lcoe_modeling` (requires `land_eligibility`, `forcing`, … | ok | não encontrado: test_main.py::test_lcoe_modeling_reads_the_central_potential_forcing_and_members_and_produces… | pass | manter colunas |
| F6:30 | A-06, V-08 | F1 to F6 on the synthetic country; ZZZ gives `lcoe_summary` and `desi… | não encontrado: tests/synthetic/test_zzz_end_to_end.py | ok | pass | manter colunas |
| F6:31 | U-04, V-05, D-F6-004 | Sample size: start at `sampler.initial_size`, double until `1 - Jacca… | ok | não encontrado: test_lcoe_convergence.py::test_the_protocol_doubles_the_size_and_adopts_the_larger_of_the_fir… | pass — mechanism only, on the synthetic country | manter colunas |
| F6:32 | M-F7-02, M-F7-03, D-F7-027 | The protocol's `MR` is F7's `evaluate` (feasibility by `CF_min` on `C… | ok | não encontrado: test_lcoe_convergence.py::test_the_top_k_of_the_protocol_is_the_robust_top_k_that_f7_writes_a… | pass | manter colunas |
| F6:33 | A-09 | The protocol lists what only the author can set (`thresholds.top_k_pe… | ok | não encontrado: test_the_real_experiments_file_has_no_ceiling_and_no_top_k_yet | pass | manter colunas |
| F6:34 | M-F6-08, D-F6-023 | External connection cost per project over `P_ref`, converted to 2024 … | ok | ok | partial — built; real countries refused (OQ-001, OQ-066) | manter colunas |
| F6:35 | M-F6-09, D-F6-023 | Degradation by PV thermal zone and wind vintage as a weight between b… | ok | ok | pass? — built | manter colunas |
| F6:36 | M-F6-10, D-F6-023 | Losses as a named sensitivity; a missing distance is excluded and cou… | ok | ok | pass? — built; sensitivities defined, not run | manter colunas |

### F7_robustness_analysis

| local | Item | Requirement | Implementation | Test | Status proposto | ação |
|---|---|---|---|---|---|---|
| F7:13 | M-F7-01, D-F7-007 | Feasibility on the `CF(m, s0)` that F5 stores, handed to the kernel a… | ok | ok | pass | manter colunas |
| F7:14 | M-F7-02, D-F7-006 | `L*` over the feasible cells of the F7 set (`q_ref = 0`), relative re… | ok | ok | pass | manter colunas |
| F7:15 | M-F7-03, D-F7-008, D-F7-010 | `MR` = maximum over core members of the exact P90 over the draws `s >… | ok | ok | pass | manter colunas |
| F7:16 | M-F7-04 | `SR` = share of the core futures that are feasible with LCOE at most … | ok | ok | pass | manter colunas |
| F7:17 | M-F7-05, D-F7-012, D-F7-013 | Nominal and robust ranks, ties (exact float, `SR`, `cell_id`), `k` fr… | ok | ok | pass | manter colunas |
| F7:18 | M-F7-06, D-F7-010 | `MR_clim`, `MR_tech`, their rankings and top-k sets; the variance of … | ok | ok | pass — the Jaccard of the top-k sets is in `futures.py` and `assem… | manter colunas |
| F7:19 | M-F7-10, A-10 | One member at a time, cell blocks with all samples, nothing sample-le… | ok | ok | pass | manter colunas |
| F7:20 | M-F7-11, D-F7-025 | `robustness_<tech>__<window>` per candidate and `nominal_lcoe_by_memb… | ok | ok | pass | manter colunas |
| F7:21 | M-F7-01, D-F7-064 | The F7 set is the complete ensemble: the class `incomplete_ensemble` … | ok | não encontrado: test_robustness_rankings.py::test_a_cell_flagged_incomplete_leaves_the_f7_set | partial — implemented, not run on a real country | manter colunas |
| F7:22 | M-F7-07, D-F7-014, D-F7-015 | H1 to H5 statistics with the pre-registered rule of `experiments.yaml… | ok | ok | pass | manter colunas |
| F7:23 | M-F7-07, D-F7-035 to D-F7-0… | H1 per the pre-registered rule: `MR_i,sigma` and `R^clim_i,sigma` per… | ok | ok | pass | manter colunas |
| F7:24 | M-F7-07, D-F7-039 to D-F7-0… | H2 per the pre-registered rule: the cell and the Admin1 selections of… | ok | ok | pass | manter colunas |
| F7:25 | M-F7-07, D-F7-043 to D-F7-0… | H3 per the pre-registered rule: the robust and the nominal shortlists… | ok | ok | pass | manter colunas |
| F7:26 | M-F7-06, M-F7-07, D-F7-046 … | H4 per the pre-registered rule: `Z_clim` and `Z_tec`, the axis shortl… | ok | ok | pass | manter colunas |
| F7:27 | M-F7-07, D-F7-050 to D-F7-0… | H5 per the pre-registered rule: the fixed economic domain `Omega_econ… | ok | ok | pass | manter colunas |
| F7:28 | M-F7-07, M-F7-08, D-F7-008 | Sample-major pass: per draw and member the rank positions, the share … | ok | ok | pass | manter colunas |
| F7:29 | T-R12, D-F7-020, D-F7-052 | Potential below `tau` per member in the three land scenarios (nominal… | ok | ok | pass | manter colunas |
| F7:30 | T-R10, D-F7-019, D-F7-052, … | Potential in cells whose hazard indicator is at least its threshold, … | ok | ok | pass | manter colunas |
| F7:31 | M-F7-08, D-F7-021, D-F7-034 | Own PRIM (peeling and pasting, real and categorical descriptors); the… | ok | ok | pass | manter colunas |
| F7:32 | M-F7-08, D-F7-054 to D-F7-0… | Scenario discovery per the pre-registered rule: the outcome `V_f` (ca… | ok | ok | pass | manter colunas |
| F7:33 | M-F7-09, D-F7-022 | Kendall tau-b between `MR` and `-SR` over the ranked set, with the pa… | ok | ok | pass — written in the `hypothesis` table as hypothesis `RQ4` | manter colunas |
| F7:34 | V-03 | `r >= 0`, `MR >= 0`, `0 <= SR <= 1`, every F7 cell ranked or fragile,… | ok | ok | pass | manter colunas |
| F7:35 | A-09, D-F7-023 | Missing F6 inputs, `CF_min` or a price year: `RobustnessMissingInputE… | ok | ok | pass | manter colunas |
| F7:36 | A-04 | No technology name in the package | sem símbolo citado (conferir) | ok | pass | manter colunas |
| F7:37 | A-01, A-02, D-F7-028 | `PhaseSpec` `robustness_analysis` | ok | ok | pass | manter colunas |
| F7:38 | A-06, V-08 | F1 to F7 on the synthetic country at 0.05 and at 0.1 degree | não encontrado: tests/synthetic/test_zzz_end_to_end.py | não encontrado: test_f7_runs_at_the_coarse_scale_with_the_same_code_and_the_masked_wind_removes_the_solar_cel… | pass | manter colunas |

### F7b_external_validation

| local | Item | Requirement | Implementation | Test | Status proposto | ação |
|---|---|---|---|---|---|---|
| F7b:13 | M-F7b-01, D-F7b-002 | Excluded share per constraint (E1 to E6 and combined) at the pixels o… | ok | ok | pass | manter colunas |
| F7b:14 | M-F7b-02, D-F7b-003 | Eligible-area-weighted deciles of the nominal LCOE at `m0`; capacity … | ok | ok | pass | manter colunas |
| F7b:15 | M-F7b-03, D-F7b-004 | Published estimates beside F5's potential at `m0` (central, restricti… | ok | ok | pass — no entry yet | manter colunas |
| F7b:16 | M-F7b-04 | Interpretation (plausibility evidence, not accuracy) in the provenanc… | ok | ok | pass | manter colunas |
| F7b:17 | V-06, D-F7b-005 | Only `external_validation/inventory.py` reads the inventory; F7b is a… | ok | ok | pass | manter colunas |
| F7b:18 | D-F7b-006, A-06 | Synthetic inventory in ZZZ with `synthetic: true`; a production run r… | ok | ok | pass | manter colunas |
| F7b:19 | D-F7b-002, A-09 | BRA, PRT and IND fail loud before anything is read or written, listin… | ok | ok | pass | manter colunas |
| F7b:20 | V-07, A-08 | Runs at 0.05 and 0.1 degree with the same code; the pixel-level exclu… | ok | ok | pass | manter colunas |

### F8_results_synthesis

| local | Item | Requirement | Implementation | Test | Status proposto | ação |
|---|---|---|---|---|---|---|
| F8:13 | M-F8-01, D-F8-001 | F8 reads persisted artifacts through the manifest and never recompute… | não encontrado: inputs.py:ArtifactReader | ok | pass | manter colunas |
| F8:14 | M-F8-02, D-F8-002, D-F8-003 | One style, one script per T-ID, thesis names | não encontrado: runner.py:SCRIPTS | ok | pass | manter colunas |
| F8:15 | T-M2, T-M3, D-F8-007 | Method tables from configuration; proxy and test values refused in a … | ok | ok | pass | manter colunas |
| F8:16 | T-R2, T-O3 | Potential and its ranges from F5; supply curves from F6 | ok | ok | pass | manter colunas |
| F8:17 | T-R6, T-R9, T-R10, T-R12, T… | The F7 and F7b tables, a skipped table shown as empty with its reason | ok | ok | pass | manter colunas |
| F8:18 | T-R7, D-F8-012 | `D_clim`, `D_tec` and `rho` by country and technology from the tables… | ok | ok | pass | manter colunas |
| F8:19 | T-R6, D-F8-011, D-F8-013 | The statistics of H1 to H5; one verdict row per hypothesis (primary s… | ok | ok | pass | manter colunas |
| F8:20 | T-R8, D-F8-014 to D-F8-016 | The structured `hypothesis_profiles` (one record per country and tech… | ok | não encontrado: test_f8_t_r8_reads_the_profiles_of_the_other_countries_of_the_thesis_directory | pass | manter colunas |
| F8:21 | T-O1, D-F8-017 | The PRIM box chosen for the core window: its limits on the position w… | ok | ok | pass | manter colunas |
| F8:22 | T-R1, T-R11, D-F8-020 | The technical potential density (T-R1) and the nominal LCOE (T-R11) a… | ok | ok | pass | manter colunas |
| F8:23 | T-R3, D-F8-018 | The change of the capacity factor of the core window by SSP (median o… | ok | ok | pass | manter colunas |
| F8:24 | T-R4, T-R5, D-F8-021 | The max-regret map with the distribution of MR within each Admin1 reg… | ok | não encontrado (a célula não cita teste) | pass | manter colunas |
| F8:25 | T-M1, D-F8-019 | The framework DAG drawn from the graph of the orchestrator (`phase_gr… | ok | ok | pass | manter colunas |
| F8:26 | T-R10, T-R12, D-F8-013 | The exposed energy of the union of the channels over the economic dom… | ok | ok | pass | manter colunas |
| F8:27 | D-F8-008 | Provenance file per output, no time, no machine path, same inputs giv… | ok | ok | pass | manter colunas |

### core

| local | Item | Requirement | Implementation | Test | Status proposto | ação |
|---|---|---|---|---|---|---|
| core:13 | A-01 | `requires`/`produces`, topological order, startup validation | proposto: core/orchestrator.py::PhaseSpec; core/orchestrator.py::_validate_and_order(); Orchestrator.run() \|… | proposto: test_orchestrator.py::test_shuffled_spec_list_produces_the_same_order; test_missing_producer_raises | pass | converter a coluna 'Current state' em Implementation e Test |
| core:14 | A-02 | Artifact registry with paths, hashes, schema versions; upstream loade… | proposto: core/orchestrator.py; main.py::_register_json_artifact(); main.py::_register_aligned_rasters() \| c… | proposto: test_orchestrator.py::test_declared_artifact_not_registered_raises; test_undeclared_artifact_regist… | pass | converter a coluna 'Current state' em Implementation e Test |
| core:15 | A-03 | Run targeting | proposto: core/schemas.py; Orchestrator.run() \| citação sem símbolo no código: tests/unit/test_schemas.py, t… | proposto: test_schemas.py::test_run_config_accepts_valid_payload; test_orchestrator.py::test_rerun_phases_ree… | pass | converter a coluna 'Current state' em Implementation e Test |
| core:16 | A-04 | Technology registry | proposto: core/schemas.py; core/config_schemas.py; core/production.py \| citação sem símbolo no código: core/… | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| core:17 | A-05 | Country mappings in `config/countries.yaml`; ISO3 literal test | proposto: data_acquisition/local_layers.py::_load_countries_config(); data_acquisition/fetchers/hydrosheds.py… | proposto: test_iso3_literals.py; test_iso3_literals.py::test_no_iso3_literals_in_src | pass | converter a coluna 'Current state' em Implementation e Test |
| core:18 | A-06 | Synthetic country fixture | proposto: scripts/generate_zzz_fixture.py \| citação sem símbolo no código: tests/synthetic/test_zzz_end_to_e… | proposto: test_zzz_end_to_end.py | pass | converter a coluna 'Current state' em Implementation e Test |
| core:19 | A-07 | Formats: COG rasters, parquet with schema_version, run ID = hash of c… | proposto: core/tables.py; core/artifact_reader.py; core/raster_io.py | não encontrado | partial | converter a coluna 'Current state' em Implementation e Test |
| core:20 | A-08 | Outputs layout: `raw/<source>/<ISO3\ | não encontrado | não encontrado | partial | converter a coluna 'Current state' em Implementation e Test (a linha tem 6 células e o cabeçalho 4: corrigir a linha) |
| core:21 | A-09 | Failure stops dependents only | proposto: main.py::run_geofrea(); Orchestrator.run(); PhaseResult(status="failed") \| citação sem símbolo no … | proposto: test_orchestrator.py::test_failure_in_one_branch_does_not_block_an_independent_branch; test_main.py… | pass | converter a coluna 'Current state' em Implementation e Test |
| core:22 | A-10 | F6/F7 batch processing under `memory.max_batch_gb` | proposto: core/schemas.py::MemoryConfig; lcoe_modeling/pipeline.py; robustness_analysis/evaluator.py | proposto: test_the_streaming_evaluation_equals_the_brute_force_definition_whatever_the_block_size | pass | converter a coluna 'Current state' em Implementation e Test |
| core:23 | A-11 | Reuse from reference repositories (CRAEI copy-and-adapt, provenance h… | proposto: climate_forcing/hazards.py; change_factors.py; paths.py | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| core:24 | A-12 | Determinism: env vars declared in `.env.example`, loaded at startup, … | proposto: main.py; paths.py; compute_run_id() | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| core:25 | A-13 | Traceability: `Implements: M-<item>.` in docstrings of functions impl… | não encontrado | não encontrado | partial | converter a coluna 'Current state' em Implementation e Test |
| core:26 | U-01 | Futures: full factorial of climate members and techno-economic sample… | proposto: member | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| core:27 | U-02 | Monte Carlo scope: sampling only within the parameter axis | proposto: lcoe_modeling/sampling.py; core/config_schemas.py | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| core:28 | U-03 | Uncertain parameters declared in `config/experiments.yaml` | proposto: core/production.py::validate_registry; load_experiments \| citação sem símbolo no código: core/conf… | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| core:29 | U-04 | Sample size convergence protocol | proposto: robustness_analysis/convergence.py | não encontrado | pass — not run on a real country | converter a coluna 'Current state' em Implementation e Test |
| core:30 | U-06 | Land-availability variants (`central`/`strict`/`lenient`) in `config/… | proposto: land_eligibility/scenarios.py | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| core:31 | U-07 | Evidence tiers 1-3, Tier 3 listed in `docs/LIMITATIONS.md` | proposto: core/schemas.py | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| core:32 | U-05 | Parameter schema with `unit`, `tier`, `range` | proposto: ParameterRange \| citação sem símbolo no código: tests/unit/test_schemas.py | proposto: test_schemas.py::test_verified_value_accepts_valid_payload | pass | converter a coluna 'Current state' em Implementation e Test |
| core:33 | V-02 | Analytical tests: CRF/LCOE closed forms, Weibull CF, PVOUT-to-CF, geo… | proposto: lcoe_modeling/kernel.py; technical_potential/rescale.py; technical_potential/weibull_cf.py | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| core:34 | V-03 | Invariants: `R_i,f >= 0`, `0 <= SR <= 1`, `0 <= CF <= 1`, `eligible_a… | não encontrado | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| core:35 | V-04 | Sanity ranges per resource layer, F1b reports violations, F5 raises o… | proposto: technical_potential/input_ranges.py | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| core:36 | V-05 | Convergence (U-04) | proposto: robustness_analysis/convergence.py | não encontrado | pass — not run on a real country | converter a coluna 'Current state' em Implementation e Test |
| core:37 | V-06 | No calibration on validation data | não encontrado \| citação sem símbolo no código: tests/unit/test_external_validation.py | proposto: test_external_validation.py | pass | converter a coluna 'Current state' em Implementation e Test |
| core:38 | V-07 | Scale check: F5-F7 rerun at 0.1 degree | proposto: core/scale.py; scale | não encontrado | pass — ZZZ only | converter a coluna 'Current state' em Implementation e Test |
| core:39 | V-08 | Synthetic end-to-end (A-06 in CI) | não encontrado | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |
| core:40 | Section 9 | `experiments.yaml`, `technologies.yaml`, `countries.yaml` | proposto: core/config_loader.py; load_countries; load_technologies | não encontrado | pass | converter a coluna 'Current state' em Implementation e Test |

## 3. F2b: 'Current criterion / Rebuild role / Status'

**Veredito.** A tabela descreve a reconstrução do módulo legado `suitability_criteria` em `siting_layers`. Essa reconstrução está concluída: o módulo `suitability_criteria` não existe em `src` (ls de `src/geofrea`), `siting_layers` tem `physical_layers.py` e `sanity.py`, os termos E1 a E6 vivem em `land_eligibility` (M-F2b-01, M-F3-01) e biomassa e sísmica estão fora do escopo (S-08, DEC-067). A frase 'The current module `suitability_criteria` implements 14 normalized criteria' já não é verdadeira. **Proposta: remover a tabela e a frase e substituí-la por uma tabela de Conformance nas colunas padrão** (M-F2b-01 a M-F2b-06), com as linhas abaixo.

| local | critério legado | papel na reconstrução | status escrito | situação hoje | destino |
|---|---|---|---|---|---|
| F2b:15 | `protected_areas` | E1 protected | reuse (binary IUCN strict categories, WDPA geometry repair) | obsoleta (reconstrução feita) | E1 vive em `land_eligibility` (M-F2b-01 E1, D-F3-020); virar linha M-F2b-01 |
| F2b:16 | `lakes_exclusion` | E2 water | reuse | obsoleta (reconstrução feita) | E2 em `land_eligibility`; linha M-F2b-01 |
| F2b:17 | `river_solar`, `river_wind` | E3 riparian | reuse, parameter per technology | obsoleta (reconstrução feita) | E3 em `land_eligibility` (Group 6, D-F3-025); linha M-F2b-01 |
| F2b:18 | `terrain_score` | E4 slope (TRI term removed) | rework | obsoleta (reconstrução feita) | E4 por faixas de declividade (D-F2a-015/016, D-F3-005); linha M-F2b-01 |
| F2b:19 | (legacy F3 land-cover exclusions) | E5 land cover | new | obsoleta (reconstrução feita) | E5 em `land_eligibility` (M-F2b-01 E5); linha M-F2b-01 |
| F2b:20 | `pop_suitability` | E6 population (binary threshold) | rework | obsoleta (reconstrução feita) | E6 hoje é GHS-SMOD (Group 6, OPEN_QUESTIONS 'Recently resolved'); linha M-F2b-01 |
| F2b:21 | `grid_suitability` | Cost-driver distance, no normalization | **built (H-4)**: `dist_grid_km` in `physical_layers.py`; the legacy f… | obsoleta (reconstrução feita) | `dist_grid_km` em `siting_layers/physical_layers.py`; linha M-F2b-02 |
| F2b:22 | `road_suitability` | Cost-driver distance, no normalization | **built (H-4)**: `dist_road_km` in `physical_layers.py` | obsoleta (reconstrução feita) | `dist_road_km` em `siting_layers/physical_layers.py`; linha M-F2b-02 |
| F2b:23 | `solar_resource` | PVOUT passthrough in kWh/kWp/day | **built (H-4)**: `pvout_kwh_kwp_day` | obsoleta (reconstrução feita) | `pvout_kwh_kwp_day` em `physical_layers.py`; linha M-F2b-03 |
| F2b:24 | `wind_resource` | Weibull A/k and air density passthrough per height | **built (H-4)**: `weibull_a/k_<h>m`, `air_density_<h>m` for 100/150/2… | obsoleta (reconstrução feita) | `weibull_a/k_<h>m`, `air_density_<h>m` em `physical_layers.py`; linha M-F2b-03 |
| F2b:25 | `river_biomass`, `lc_biomass`, `biomass_resource` | Removed (S-02), but see Known issues — regression test… | remove | obsoleta (reconstrução feita) | n/a: biomassa fora do escopo (S-08, DEC-067); sem linha |
| F2b:26 | `seismic_suitability` | Removed (S-08) | remove | obsoleta (reconstrução feita) | n/a: sísmica fora do escopo (S-08); sem linha |
| F2b:27 | Percentile normalization per country | **Still executing today — status corrected 2026-09-24 … | rework (owned by H-2) | obsoleta (reconstrução feita) | n/a: normalização removida (M-F2b-04); chave ausente em `parameters.json`; sem linha |

## 4. D-* definidos duas vezes

A regra de definição é a do 147-B (linha que começa com o ID: bullet, linha de tabela ou título). **Continuação**: a segunda linha é o mesmo assunto (linha de tabela de Conformance que cobre a decisão, parágrafo que acrescenta) e fica como está ou passa a citar o ID sem abrir com ele. **Distinta**: o ID foi reutilizado para outro assunto; a proposta é dar um ID novo (o próximo livre da série) à definição menos citada, sem renumerar o resto, depois de um grep das citações (`scripts/find_decision.py`).

| D-ID | definições (arquivo:linha [seção] começo) | veredito | proposta |
|---|---|---|---|
| D-F1-016 | F1_data_acquisition.md:52 [Active implem…] D-F1-016 — M-F1-05 acquisition rate measured, product selected (task … <br> F1_data_acquisition.md:53 [Active implem…] D-F1-016 also records F3-1's own measured rate, supplied by Douglas s… | continuação | a segunda linha diz 'also records': é o mesmo registro; juntar no mesmo bullet |
| D-F1-027 | F1_data_acquisition.md:81 [Active implem…] D-F1-027 — WRI GPPD withdrawn from the pipeline; GEM is the only exis… <br> F1_data_acquisition.md:83 [Active implem…] D-F1-027 — `mainland_only` keeps the contiguous territory, not the la… <br> F1_data_acquisition.md:89 [Active implem…] D-F1-027 — The local-only layers live in `GEOFREA_DATA_DIR/raw` and t… | distinta (3 definições: WRI GPPD retirado, `mainland_only`, camadas locais em `GEOFREA_DATA_DIR/raw`) | manter o ID na definição mais citada (grep) e dar às outras duas D-F1-032 e D-F1-033 |
| D-F1b-008 | F1b_data_quality_audit.md:23 [Active implem…] D-F1b-008 — CMIP6 resource channel wired into raster inspection, one … <br> F1b_data_quality_audit.md:43 [Active implem…] D-F1b-008 — `_effective_crs()`'s two error paths confirmed reachable … | distinta (canal CMIP6 na inspeção de raster; caminhos de erro de `_effective_crs`) | a segunda recebe D-F1b-020 |
| D-F1b-015 | F1b_data_quality_audit.md:47 [Active implem…] D-F1b-015 — OQ-026 (instance 2) resolved: the land-cover tile cache k… <br> F1b_data_quality_audit.md:100 [History] D-F1b-015 — The air-density sanity range carries a 5% quality-control… | distinta (chave de cache do land cover, OQ-026; tolerância de 5% da faixa de densidade do ar). A segunda está em History | a da History recebe D-F1b-020 e vai para Active implementation decisions |
| D-F2a-018 | F2a_grid_alignment.md:70 [Active implem…] D-F2a-018 — V-01 refrozen after the ZZZ land cover gained a grassland… <br> F2a_grid_alignment.md:75 [Active implem…] D-F2a-018 — Checked 2026-10-14: no sample-centre counting mode exists… | distinta (V-01 recongelado com a faixa de pastagem; checagem de que não há modo de contagem pelo centro) | a segunda recebe D-F2a-030 |
| D-F2a-027 | F2a_grid_alignment.md:29 [Active implem…] D-F2a-027 — Settlement layer from GHS-SMOD R2023A (2026-11-05, COMMAN… <br> F2a_grid_alignment.md:82 [Active implem…] D-F2a-027 — The 180 land-cover pixels are nearest-neighbour ties (202… | distinta (camada de assentamentos GHS-SMOD; os 180 pixels de land cover são empates) | a segunda recebe D-F2a-030 |
| D-F4-019 | F4_climate_forcing.md:44 [Active implem…] D-F4-019 — `external_inputs` phase and the audit gate (2026-10-07).**… <br> F4_climate_forcing.md:46 [Active implem…] D-F4-019 — F4 on the synthetic country with miniature CMIP6 files (D1… | distinta (fase `external_inputs`; F4 no país sintético com arquivos miniatura). A History de F4 cita o ID para o segundo assunto | a primeira recebe D-F4-029 (conferir citações de `external_inputs`) |
| D-F5-008 | F5_technical_potential.md:19 [Conformance] D-F5-008 \| Rescale of the stored CF to another `gamma` or `eta_loss`… <br> F5_technical_potential.md:45 [Active implem…] D-F5-008 — Uncertain parameters in F6 (D8; U-03).** The potential tab… | continuação: a primeira linha é uma linha da tabela de Conformance que cobre a decisão | escrever a Item da tabela como 'M-F5-nn, D-F5-008' (não abrir a linha com o D-ID) |
| D-F5-030 | F5_technical_potential.md:67 [Active implem…] D-F5-030 — Classes of the per-state maps: limits of the central scena… <br> coverage_alignment_54.md:141 [3. Classes of…] D-F5-030, METHODOLOGY 15.1.1: Fisher-Jenks limits of the central scen… | continuação: a segunda linha é um relatório (`coverage_alignment_54.md`) que cita a decisão | nada; o relatório cita, o bullet de F5 define |
| D-F6-007 | F6_lcoe_modeling.md:15 [Conformance] D-F6-007 \| Zero energy gives `+inf`, not an error; a negative or non… <br> F6_lcoe_modeling.md:20 [Conformance] D-F6-007 \| Zero energy: `+inf`, quantiles kept, mean and variance ov… <br> F6_lcoe_modeling.md:48 [Active implem…] D-F6-007 — Zero energy (D7; M-F6-01).** `E = 0` gives `LCOE = +inf`, … | continuação (3 linhas: duas de Conformance e o bullet; mesmo assunto, energia zero) | as duas linhas de tabela passam a citar o ID sem abrir com ele |
| D-F6-010 | F6_lcoe_modeling.md:16 [Conformance] D-F6-010 \| Integer lifetime; zero discount rate by the limit, with n… <br> F6_lcoe_modeling.md:51 [Active implem…] D-F6-010 — Lifetime and degenerate rates (D10; M-F6-01).** The sample… | continuação: linha de Conformance que cobre o bullet | a linha de tabela passa a citar o ID sem abrir com ele |
| D-F7-026 | F6_lcoe_modeling.md:27 [Conformance] D-F7-026 \| The resolution of parameters and the readers of the F3, F… <br> F7_robustness_analysis.md:72 [Active implem…] D-F7-026 — Modules (D26; A-04).** `robustness_analysis` imports the k… | continuação: linha da tabela de F6 sobre o `inputs.py` neutro, que é o assunto do bullet de F7 | a linha de F6 cita 'D-F7-026' sem abrir com ele |
| D-F7b-002 | F7b_external_validation.md:19 [Conformance] D-F7b-002, A-09 \| BRA, PRT and IND fail loud before anything is read… <br> F7b_external_validation.md:28 [Active implem…] D-F7b-002 — Exclusion test (D18; M-F7b-01).** F3 persists no per-pixe… | continuação: linha de Conformance (falha antes de ler, A-09) e bullet 'Exclusion test'. O bullet não menciona a falha antes de ler: conferir | a linha de tabela passa a citar o ID sem abrir com ele; se o bullet não cobre a falha, acrescentar uma frase ao bullet |
| D-F7b-006 | F7b_external_validation.md:18 [Conformance] D-F7b-006, A-06 \| Synthetic inventory in ZZZ with `synthetic: true`;… <br> F7b_external_validation.md:32 [Active implem…] D-F7b-006 — Synthetic inventory (D22; A-06).** `raw/gem/ZZZ/gem_solar… | continuação: linha de Conformance e bullet do inventário sintético | a linha de tabela passa a citar o ID sem abrir com ele |
| D-F8-008 | F8_results_synthesis.md:27 [Conformance] D-F8-008 \| Provenance file per output, no time, no machine path, sam… <br> F8_results_synthesis.md:40 [Active implem…] D-F8-008 — D10(a): formats (recommended, accepted 2026-10-13).** Tabl… | continuação: linha de Conformance (arquivo de proveniência) e bullet 'D10(a): formats' que traz a proveniência por saída | a linha de tabela passa a citar o ID sem abrir com ele |
| D-core-005 | core.md:53 [Active implem…] D-core-005 — Portable path resolution via `StoredPath` (E5b). Manifes… <br> core.md:155 [History] D-core-005 (E2 draft design for A-01/A-02/A-03/A-09, "awaiting verdic… <br> E5b.md:8 [Contract] D-core-005 (`paths.py`, `StoredPath`, manifest schema 2.1) for the co… | distinta: `core.md:53` define o D-core-005 de `StoredPath` e a linha de History (155) usa o mesmo ID para o rascunho de E2, 'superseded by D-core-003' | a linha da History é obsoleta (classe e na seção 1): remover; o ID fica com `StoredPath` |

## 5. Bullets `- **D-` fora do formato (`- **D-<fase>-<n> — Título (data, comando).**`): 62

| local | ID | o que falta | começo da linha |
|---|---|---|---|
| E5b.md:13 | D-E5b-001 | o título em negrito não fecha | - **D-E5b-001 — BRA (8) vs PRT (6) manifest-backup count asymmetry is real |
| F1_data_acquisition.md:24 | D-F1-001 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F1-001 — Acquisition contract before real fetch.** The layer-acquisition … |
| F1_data_acquisition.md:26 | D-F1-002 | sem parênteses de data/comando | - **D-F1-002 — Equal audit depth for vector layers.** The data-quality audit re… |
| F1_data_acquisition.md:28 | D-F1-003 | sem parênteses de data/comando | - **D-F1-003 — Single source of truth for path vs paths.** `MULTI_FILE_LAYER_NA… |
| F1_data_acquisition.md:30 | D-F1-004 | sem parênteses de data/comando | - **D-F1-004 — IUCN category case normalization.** WDPA `IUCN_CAT` values are n… |
| F1_data_acquisition.md:32 | D-F1-005 | sem parênteses de data/comando | - **D-F1-005 — Layer-keyed audit summary.** `AuditSummary` is a discriminated, … |
| F1_data_acquisition.md:34 | D-F1-006 | sem parênteses de data/comando | - **D-F1-006 — Real fetchers replace acquisition skeleton.** Power plants, wind… |
| F1_data_acquisition.md:36 | D-F1-007 | sem parênteses de data/comando | - **D-F1-007 — Acquisition activation.** `data_acquisition` genuinely feeds `da… |
| F1_data_acquisition.md:38 | D-F1-008 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F1-008 — Spatial-index clip for large countries.** Country clipping (`cli… |
| F1_data_acquisition.md:40 | D-F1-009 | sem parênteses de data/comando | - **D-F1-009 — Guard against clip-less country processing.** `ClipRequiresCount… |
| F1_data_acquisition.md:42 | D-F1-010 | sem parênteses de data/comando | - **D-F1-010 — Real GADM fetcher for borders and admin1.** Country borders and … |
| F1_data_acquisition.md:44 | D-F1-011 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F1-011 — Local-database resolution for pre-placed layers.** Elevation, po… |
| F1_data_acquisition.md:46 | D-F1-012 | sem parênteses de data/comando | - **D-F1-012 — GRIP4 replaces per-country OSM roads.** Roads resolve from a sin… |
| F1_data_acquisition.md:50 | D-F1-015 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F1-015 — M-F1-04 resource channel implemented (task F-3, COMMAND F3-2, 20… |
| F1_data_acquisition.md:53 | D-F1-016 | sem ' — ' depois do ID; sem parênteses de data/comando | - **D-F1-016 also records F3-1's own measured rate, supplied by Douglas since i… |
| F1_data_acquisition.md:55 | D-F1-017 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F1-017 — M-F1-05 dataset switched from the CDS derived daily-statistics p… |
| F1_data_acquisition.md:73 | D-F1-020 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F1-020 — Three F4-5 gaps closed before real acquisition resumed (COMMAND … |
| F1b_data_quality_audit.md:39 | D-F1b-003 | sem parênteses de data/comando | - **D-F1b-003 — land_cover tile cache: sha256 content check added; hit conditio… |
| F1b_data_quality_audit.md:40 | D-F1b-002 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F1b-002 — M-F1b-01 expectations moved to config/audit.yaml, sourced from … |
| F1b_data_quality_audit.md:41 | D-F1b-001 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F1b-001 — Vector inspection distinguishes read_error from processing_erro… |
| F2a_grid_alignment.md:31 | D-F2a-001 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F2a-001 — Legacy grid_alignment ported with targeted revisions.** `grid_a… |
| F2a_grid_alignment.md:33 | D-F2a-002 | sem parênteses de data/comando | - **D-F2a-002 — Bowring centralization, unified distance cap, fixed resolution.… |
| F2a_grid_alignment.md:35 | D-F2a-003 | sem parênteses de data/comando | - **D-F2a-003 — Fail-loud on corrupted land-cover tiles.** `mosaic_land_cover` … |
| F2b_siting_layers.md:31 | D-F2b-001 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F2b-001 — Riparian setback mechanism split across phases.** The riparian … |
| F2b_siting_layers.md:33 | D-F2b-002 | sem parênteses de data/comando | - **D-F2b-002 — WDPA absent versus corrupted.** `E1 protected` fails loudly on … |
| F2b_siting_layers.md:35 | D-F2b-003 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F2b-003 — Nodata-safe terrain handling.** A pixel adjacent to nodata/NaN … |
| F2b_siting_layers.md:37 | D-F2b-004 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F2b-004 — WDPA invalid-geometry repair moved to the shared clip path.** `… |
| F3_land_eligibility.md:80 | D-F3-002 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F3-002 — Engine and parameters (2026-10-07, Douglas's approval of `docs/_… |
| F4_climate_forcing.md:22 | D-F4-001 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F4-001 — Resource and hazard channels use different products by design, n… |
| F4_climate_forcing.md:23 | D-F4-002 | sem parênteses de data/comando | - **D-F4-002 — 2071-2100 hazard data is ISIMIP3b, same product as the core wind… |
| F4_climate_forcing.md:24 | D-F4-003 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F4-003 — A member may carry a resource row with no hazard row.** MIROC6 s… |
| F4_climate_forcing.md:25 | D-F4-004 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F4-004 — Member contract: channel presence is declared, never inferred fr… |
| F4_climate_forcing.md:26 | D-F4-005 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F4-005 — Member contract needs no METHODOLOGY change.** M-F4-01 defines `… |
| F4_climate_forcing.md:48 | D-F4-021 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F4-021 — Status: decided 2026-10-14 (Douglas, V-B1) — the wind channel of… |
| F5_technical_potential.md:61 | D-F5-024 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F5-024 — First real run: PRT and IND (2026-10-16, METHODOLOGY 14.2.0, rep… |
| F5_technical_potential.md:64 | D-F5-027 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F5-027 — First complete real round: PRT, IND and BRA clean (2026-10-17, M… |
| F7_robustness_analysis.md:81 | D-F7-037 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F7-037 — H1 sensitivities.** `h1_summary` has one row per setting, the fi… |
| F7_robustness_analysis.md:82 | D-F7-038 | sem parênteses de data/comando | - **D-F7-038 — H1 outputs and skips.** `ssp_scores_<tech>__<window>`, `h1_sites… |
| F7_robustness_analysis.md:85 | D-F7-040 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F7-040 — H2 outputs: `h2_summary` and `h2_regions`.** `h2_summary_<tech>_… |
| F7_robustness_analysis.md:89 | D-F7-044 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F7-044 — H3 outputs: `h3_summary` and `h3_sites`.** `h3_summary_<tech>__<… |
| F7_robustness_analysis.md:92 | D-F7-047 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F7-047 — H4 outputs: `h4_country`.** `h4_country_<tech>__<window role>` h… |
| F7_robustness_analysis.md:94 | D-F7-049 | sem parênteses de data/comando | - **D-F7-049 — Where the verdict is computed: the support phase `cross_country_… |
| F7_robustness_analysis.md:96 | D-F7-051 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F7-051 — H5 outputs: `h5_summary` and `h5_members`.** `h5_summary_<tech>_… |
| F7_robustness_analysis.md:98 | D-F7-053 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F7-053 — Cases the text leaves open.** (i) H5b uses the channels that hav… |
| F7_robustness_analysis.md:100 | D-F7-055 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F7-055 — Scenario discovery: the box and its variants.** `scenario_discov… |
| F7_robustness_analysis.md:101 | D-F7-056 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F7-056 — Scenario discovery: bootstrap.** `scenario_discovery.py:bootstra… |
| F7_robustness_analysis.md:102 | D-F7-057 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F7-057 — Cost and tests.** The bootstrap repeats a PRIM search 200 times … |
| F7_robustness_analysis.md:103 | D-F7-058 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F7-058 — H5b channels: those with a threshold (METHODOLOGY 13.0.1; supers… |
| F7_robustness_analysis.md:104 | D-F7-059 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F7-059 — One source for the national target (METHODOLOGY 13.0.1; supersed… |
| F7_robustness_analysis.md:105 | D-F7-060 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F7-060 — The outcome of PRIM is never replaced in src.** The rule on the … |
| F7b_external_validation.md:24 | D-F7b-001 | sem ' — ' depois do ID | - **D-F7b-001 (2026-10-07, from F5-1):** the plant inventory is `raw/gem/<ISO3>… |
| F8_results_synthesis.md:42 | D-F8-010 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F8-010 — Outputs not built here and the decision that blocks each.** Ever… |
| F8_results_synthesis.md:47 | D-F8-015 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F8-015 — Profiles: content, ranges and classes.** A record per country an… |
| F8_results_synthesis.md:48 | D-F8-016 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F8-016 — The summary and the labels.** `synthesis` in `experiments.yaml` … |
| F8_results_synthesis.md:49 | D-F8-017 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F8-017 — T-O1.** One table and one figure per technology from `prim_box`,… |
| F8_results_synthesis.md:52 | D-F8-019 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F8-019 — T-M1: the graph is the orchestrator's.** `orchestrator.py:phase_… |
| F8_results_synthesis.md:53 | D-F8-020 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F8-020 — T-R1 and T-R11 read the diagnostic COGs.** The maps of F5 and F6… |
| F8_results_synthesis.md:54 | D-F8-021 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-F8-021 — T-R4 and T-R5.** T-R4 reads the raster `max_regret_<tech>__core`… |
| core.md:44 | D-core-001 | sem parênteses de data/comando | - **D-core-001 — Technology-level discount rate.** IRENA reports genuinely diff… |
| core.md:46 | D-core-002 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-core-002 — Solar and wind parameters from IRENA.** Solar and wind cost/pe… |
| core.md:50 | D-core-004 | sem parênteses de data/comando | - **D-core-004 — Slope threshold as a technology parameter.** Terrain slope tol… |
| core.md:53 | D-core-005 | fecha o negrito depois dos parênteses ou sem o ponto final esperado | - **D-core-005 — Portable path resolution via `StoredPath` (E5b). Manifest sche… |

## 6. Citações de teste que não existem: teste equivalente

| local | citação | proposta |
|---|---|---|
| F5:21 | `test_class_follows_the_mean_speed_with_the_last_class_unbounded` | n/a: a regra de classe por velocidade média foi removida (D-F5-023); o teste existente `test_technical_potential_pipeline.py::test_the_registry_names_one_turbine_and_one_flag_and_the_old_class_rule_is_gone` confirma a remoção e `test_the_flag_is_strictly_above_the_class_limit` cobre o limite da bandeira |
| F5:21 | `test_class_rule_rejects_malformed_rules` | n/a: mesma razão (regra de classe removida, D-F5-023) |
| F5:21 | `test_registry_rule_and_curves_must_name_the_same_classes` | n/a: mesma razão (regra de classe removida, D-F5-023); o par `test_technical_potential_pipeline.py::test_registry_resource_layers_are_the_columns_f3_writes` é de outro tema (colunas de F3), não equivalente |
| F5:23 | `test_declared_masked_cell_member_has_no_row_and_is_counted` | `test_technical_potential_pipeline.py::test_a_wind_ratio_masked_cell_member_is_absent_for_wind_only_and_solar_keeps_it` e `tests/synthetic/test_zzz_end_to_end.py::test_wind_potential_has_no_row_for_a_declared_masked_cell_member_and_a_row_for_every_other` (a contagem do membro mascarado não foi conferida) |
| F5:23 | `test_wind_factor_out_of_range_in_a_candidate_cell_raises` | `test_technical_potential_pipeline.py::test_wind_factor_out_of_range_in_a_candidate_cell_raises_for_wind_and_not_for_solar` (nome estendido) |
| F5:26 | `test_real_countries_fail_loud_listing_the_missing_parameters_and_write_nothing` | `test_technical_potential_pipeline.py::test_missing_parameters_fail_loud_listing_every_item_and_write_nothing`. A linha diz que BRA, PRT e IND falham assim 'hoje'; D-F5-023 (Group 1 registrado) e F5 Known issues dizem que não falham mais: a frase também está velha |
| F6:24 | `test_real_countries_fail_loud_listing_the_missing_parameters_ranges_and_price_years` | `test_lcoe_pipeline.py::test_real_countries_fail_loud_listing_only_the_group_3_costs_and_citing_oq_001` (o nome cita OQ-001, hoje fechada: conferir o que o teste afirma) |
| F6:27 | `test_lcoe_convergence.py` | `test_robustness_convergence.py` (o arquivo foi renomeado: o conteúdo citado está nele) |
| F6:29 | `test_main.py::test_lcoe_modeling_reads_the_central_potential_forcing_and_members_and_produces_three_tables_per_technology` | `test_main.py::test_lcoe_modeling_reads_the_potential_of_every_land_scenario_forcing_and_members_and_produces_its_tables` (nome estendido: F6 lê todos os cenários de terra) |
| F6:31 | `test_lcoe_convergence.py::test_the_protocol_doubles_the_size_and_adopts_the_larger_of_the_first_pair_that_agrees` | `test_robustness_convergence.py::test_the_protocol_doubles_the_size_and_adopts_the_larger_of_the_first_pair_that_agrees` |
| F6:31 | `test_the_f7_set_keeps_cells_present_in_every_core_member_and_feasible_at_m0` | sem equivalente por nome. O mais próximo é `test_robustness_rankings.py::test_the_four_classes_follow_the_definitions_of_m_f7_01` (classes de M-F7-01); que ele cobre 'presente em todo membro do núcleo e viável em m0' não foi conferido: n/a até conferir |
| F6:32 | `test_lcoe_convergence.py::test_the_top_k_of_the_protocol_is_the_robust_top_k_that_f7_writes_at_the_same_size` | `test_robustness_convergence.py::test_the_top_k_of_the_protocol_is_the_robust_top_k_that_f7_writes_at_the_same_size` |
| F6:33 | `test_the_real_experiments_file_has_no_ceiling_and_no_top_k_yet` | `test_robustness_convergence.py::test_the_real_experiments_file_has_no_ceiling_and_the_top_k_lives_in_the_country_parameters` (o nome mudou com a decisão sobre o top-k) |
| F7:38 | `test_f7_runs_at_the_coarse_scale_with_the_same_code_and_the_masked_wind_removes_the_solar_cells` | `tests/synthetic/test_zzz_end_to_end.py::test_f7_runs_at_the_coarse_scale_with_the_same_code_and_the_masked_wind_removes_only_wind_cells` (o nome diz 'only wind cells', a citação dizia 'the solar cells': o conteúdo mudou) |
| F7:21 | `test_robustness_rankings.py::test_a_cell_flagged_incomplete_leaves_the_f7_set...` | citação abreviada com reticências (não é um nome completo): `test_robustness_rankings.py::test_a_cell_flagged_incomplete_leaves_the_f7_set_and_is_neither_ranked_nor_invalid` existe; escrever o nome inteiro ou citar só o arquivo |
| F8:20 | `test_f8_t_r8_reads_the_profiles_of_the_other_countries_of_the_thesis_directory` | `tests/synthetic/test_zzz_end_to_end.py::test_f8_t_r8_reads_the_registered_profiles_of_the_other_countries_and_records_their_hashes` |

As 15 citações de nome inexistente (07, achado b) estão em 11 linhas das tabelas de verificação; a 16ª linha desta tabela (F7:21) é uma citação abreviada com reticências, que o 07 não contou: o nome completo existe.

Conferência cruzada: as tabelas de Conformance da seção 2 listam como 'não encontrado' exatamente estas citações, e o script não achou outra além delas nas 14 tabelas lidas (ver abaixo).

Citações sem teste encontradas pelo script da seção 2 que não estão nas 16 acima: 0.

## 7. Ordem sugerida para aplicar (nada foi aplicado)

1. Registrar OQ-095 a OQ-102 (classe c) e L-237 a L-240 (classe b: F1:206, F1:214, F6:75 e uma só para F7:114 e F7b:38), com autorização, com autorização, antes de apagar qualquer linha (as classes b e c só podem sair de docs/phases depois de existirem no OPEN_QUESTIONS ou no LIMITATIONS).
2. Apagar as linhas das classes a, d e e das seções History e Known issues, registro a registro, começando pelos de menor risco (E1, E5b, F4, F7b), com `git diff` por registro.
3. Converter as tabelas de Conformance de F1, F1b, F2a e core, e trocar a de F2b (seção 3).
4. Corrigir as 15 citações de teste (seção 6) e os bullets fora do formato (seção 5).
5. Resolver os D-* duplicados (seção 4): onde é continuação, juntar; onde é distinta, dar ID novo.

