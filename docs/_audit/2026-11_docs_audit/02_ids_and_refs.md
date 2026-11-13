# 02 — IDs e referências de docs/ (COMANDO 147-B)

Gerado por script (scratchpad `ids148.py`, `corpus148.py`); somente leitura. Nenhum arquivo de docs ou código foi alterado. Pasta mantida não rastreada até o 147-H.

Corpus: 710 arquivos de texto de docs/, src/, tests/, config/ e scripts/ (rastreados e não rastreados, JSON de docs acima de 400 KB e a pasta de auditoria deste comando excluídos). IDs distintos encontrados: 776 (D 365, M-F 78, OQ 94, L 122, U 8, V 10, A 13, S 10, T 35, R71/R73 33).

**Definição de "definido"** (regra do script, sem julgamento): a linha começa com o ID (após `- `, `#`, `|` ou `**`) em
`docs/phases/**` para `D-*`; em `docs/METHODOLOGY.md` para `M-*`, `U-`, `V-`, `A-`, `S-`, `T-`; em `docs/OPEN_QUESTIONS.md` (linha de tabela) para `OQ-`;
em `docs/LIMITATIONS.md` (linha de tabela) para `L-`; em `docs/_audit/**` para `R71-`/`R73-`. Qualquer outra aparição é **citação**. Padrões de ID procurados:
`OQ-n`, `L-n`, `D-F*|E*|core-n`, `M-F*|E*-n`, `U-`, `V-`, `A-`, `S-`, `M-`, `T-Xn`, `R71-n`, `R73-n`. Outros padrões vistos e **não** tratados como ID por serem nomes de modelo, hash, SSP ou rótulo de comando: `GLO-`, `SSP1-2.6`, `SHA-256`, `MS-`, `ADJ-7`, `MRI-ESM2-`, `CNRM-CM6-`, `INVAR`, `GAP`. `H1` a `H5` não têm hífen e não entram nesta tabela (hipóteses em `docs/thesis/hypotheses/`). Os IDs do tipo `V1`..`V7` sem hífen (variantes de decisão nos registros de fase) também não.


## 2a. Citado e não definido

**Total: 110 IDs.**

| família | IDs | exemplos (até 10) |
|---|---|---|
| D | 9 | D-F1b-016, D-F2a-030, D-F3-004, D-F3-006, D-F3-014, D-F3-016, D-F4-027, D-F7-030, D-F7-033 |
| M-F | 2 | M-F4-0x, M-F5-010 |
| OQ | 68 | OQ-002, OQ-003, OQ-004, OQ-005, OQ-006, OQ-009, OQ-011, OQ-012, OQ-015, OQ-016 |
| L | 11 | L-1, L-2, L-201, L-202, L-3, L-4, L-5, L-6, L-7, L-8 |
| U | 0 |  |
| V | 2 | V-82, V-83 |
| A | 0 |  |
| S | 1 | S-33 |
| T | 17 | T-01, T-02, T-03, T-04, T-05, T-06, T-07, T-08, T-09, T-10 |
| R71/R73 | 0 |  |

Nota: `OPEN_QUESTIONS.md` diz que a pergunta resolvida é apagada da tabela, então um `OQ-n` citado e ausente da tabela pode ser uma pergunta resolvida e não um erro. O script não distingue os dois casos. Dos OQ nesta lista, os que aparecem em prosa de `OPEN_QUESTIONS.md` (por exemplo, no parágrafo "Recently resolved") estão abaixo.

OQ citados e ausentes da tabela, mas mencionados em prosa de `OPEN_QUESTIONS.md`: **24** (OQ-011, OQ-026, OQ-031, OQ-033, OQ-041, OQ-042, OQ-046, OQ-047, OQ-049, OQ-052).

Caso `OQ-086`: definido = não; citações: 8 em 6 arquivos (docs/METHODOLOGY.md, docs/OPEN_QUESTIONS.md, docs/_audit/window_132.md, docs/phases/F6_lco).

Exemplos com o arquivo da primeira citação:

| ID | primeira citação | citações |
|---|---|---|
| D-F1b-016 | docs/_audit/2026-10_general_audit_71.md:123 | 2 |
| D-F2a-030 | docs/OPEN_QUESTIONS.md:7 | 2 |
| D-F3-004 | docs/_audit/2026-10_pipeline_state.md:54 | 5 |
| M-F4-0x | docs/phases/F4_climate_forcing.md:32 | 2 |
| M-F5-010 | tests/unit/test_methodology_changelog.py:142 | 3 |
| OQ-002 | docs/METHODOLOGY.md:629 | 14 |
| OQ-003 | docs/METHODOLOGY.md:629 | 11 |
| OQ-004 | config/technologies.yaml:39 | 40 |
| L-1 | docs/LIMITATIONS.md:78 | 6 |
| L-2 | docs/_audit/2026-10_F6_design.md:36 | 4 |

## 2b. Definido mais de uma vez

**Total: 36 IDs.**

| família | IDs com mais de uma definição |
|---|---|
| D | 16 |
| M-F | 0 |
| OQ | 0 |
| L | 0 |
| U | 0 |
| V | 0 |
| A | 1 |
| S | 0 |
| T | 0 |
| R71/R73 | 19 |

Exemplos (até 10):

| ID | definições (arquivo:linha) |
|---|---|
| D-F1-016 | docs/phases/F1_data_acquisition.md:52; docs/phases/F1_data_acquisition.md:53 |
| D-F1-027 | docs/phases/F1_data_acquisition.md:81; docs/phases/F1_data_acquisition.md:83; docs/phases/F1_data_acquisition.md:89 |
| D-F1b-008 | docs/phases/F1b_data_quality_audit.md:23; docs/phases/F1b_data_quality_audit.md:43 |
| D-F1b-015 | docs/phases/F1b_data_quality_audit.md:47; docs/phases/F1b_data_quality_audit.md:100 |
| D-F2a-018 | docs/phases/F2a_grid_alignment.md:70; docs/phases/F2a_grid_alignment.md:75 |
| D-F2a-027 | docs/phases/F2a_grid_alignment.md:29; docs/phases/F2a_grid_alignment.md:82 |
| D-F4-019 | docs/phases/F4_climate_forcing.md:44; docs/phases/F4_climate_forcing.md:46 |
| D-F5-008 | docs/phases/F5_technical_potential.md:19; docs/phases/F5_technical_potential.md:45 |
| D-F5-030 | docs/phases/F5_technical_potential.md:67; docs/phases/core/coverage_alignment_54.md:141 |
| D-F6-007 | docs/phases/F6_lcoe_modeling.md:15; docs/phases/F6_lcoe_modeling.md:20; docs/phases/F6_lcoe_modeling.md:48 |

## 2c. Definido e nunca citado

Citado = aparece em alguma linha que não é a própria linha de definição (em qualquer arquivo do corpus, inclusive no mesmo arquivo).

**Total: 127 IDs.**

| família | IDs | exemplos (até 10) |
|---|---|---|
| D | 72 | D-F1-002, D-F1-004, D-F1-005, D-F1-007, D-F1-008, D-F1-009, D-F1-011, D-F1-012, D-F1-021, D-F1b-009 |
| M-F | 0 |  |
| OQ | 2 | OQ-089, OQ-091 |
| L | 40 | L-007, L-009, L-010, L-011, L-013, L-014, L-017, L-031, L-032, L-036 |
| U | 0 |  |
| V | 0 |  |
| A | 0 |  |
| S | 0 |  |
| T | 0 |  |
| R71/R73 | 13 | R71-03, R71-10, R71-11, R71-12, R71-13, R71-17, R71-18, R71-19, R71-20, R71-23 |

## 2d. Status de OQ contra o modo como é citado

Tabela de `OPEN_QUESTIONS.md`: 22 linhas; status: {'open': 20, 'closed_with_proxies': 1, 'closed': 1}. Método: palavras-chave na linha da citação, fora de `OPEN_QUESTIONS.md` e de `_archive`. **São candidatos por palavra-chave, não confirmados.**

| verificação | citações |
|---|---|
| OQ `closed` citado com palavra de pendência (pending, open, aberto, awaiting, not yet, until OQ, ...) | 1 |
| OQ não `closed` (open, awaiting_verdict, research_in_progress) citado com palavra de resolução (closed, resolved, decided, ...) | 48 |
| OQ ausente da tabela citado com palavra de pendência e sem palavra de resolução | 104 |

Exemplos — closed citado como pendente (até 10, de 1):

| OQ | onde | linha |
|---|---|---|
| OQ-085 | docs/_audit/general_audit_130.md:43 | Closed in this period: OQ-081, OQ-085. L (93 rows): all are accepted limits (class 4); 27 mention F6, F7 or F8 |

Exemplos — não closed citado como resolvido (até 10, de 48):

| OQ | onde | linha |
|---|---|---|
| OQ-001 | docs/LIMITATIONS.md:28 | / L-018 / The `grid` layer is OpenStreetMap power infrastructure of any voltage (lines and points), so distanc |
| OQ-001 | docs/METHODOLOGY.md:593 | / 16.2.0 / 2026-11-02 / MINOR (COMMAND 86; no result existed, so no result changes; `docs/_audit/group3_costs_ |
| OQ-001 | docs/METHODOLOGY.md:595 | / 16.0.0 / 2026-11-02 / MAJOR (changes the result definition of F6, M-F6-01: the CAPEX terms (`C_inter` per pr |
| OQ-001 | docs/METHODOLOGY.md:630 | / 7.0.0 / 2026-10-08 / MAJOR (changes a result definition and phase contracts): applies verdicts V1 to V6, V8  |
| OQ-001 | docs/PIPELINE_GUIDE.md:310 | 3. **Estimated awake time**, cold F2a, from the profiles above: PRT about 3 minutes (F2a 139 s, F3 17 s); IND  |
| OQ-001 | docs/_audit/2026-10_general_audit_71.md:118 | / R71-10b / OQ-041 lists "Depends on OQ-001 and OQ-040"; OQ-040 is closed (not in the table) / P2 / |
| OQ-001 | docs/_audit/2026-10_systematic_review.md:225 | - `docs/PROGRESS.json:13`: {"id": "MS-6", "title": "Parameter research (OQ-001 to OQ-023)", "status": "not_sta |
| OQ-001 | docs/_audit/2026-10_systematic_review.md:225 | - `docs/PROGRESS.json:13`: {"id": "MS-6", "title": "Parameter research (OQ-001 to OQ-023)", "status": "not_sta |
| OQ-001 | docs/_audit/general_audit_130.md:43 | Closed in this period: OQ-081, OQ-085. L (93 rows): all are accepted limits (class 4); 27 mention F6, F7 or F8 |
| OQ-001 | docs/_audit/general_audit_130.md:274 | **PROGRESS.json**: `last_updated` 2026-11-09, `methodology_version` 19.0.0 (the METHODOLOGY says 19.0.1); `cur |

Exemplos — ausente da tabela citado como pendente (até 10, de 104):

| OQ | onde | linha |
|---|---|---|
| OQ-002 | docs/_audit/2026-10_systematic_review.md:216 | / L-205 (`docs/LIMITATIONS.md:49`) / \/ L-205 \/ countries.PRT.technologies.solar.slope_threshold_deg \/ 5.0 d |
| OQ-004 | docs/_audit/2026-10_pre_research_audit.md:468 | / B-2 / The real F5 cannot start: `config/power_curves/` does not exist, `iec_class_rule` and `power_curves` a |
| OQ-004 | docs/phases/F8_results_synthesis.md:62 | - Needs real values (the scripts run on ZZZ): T-R1, T-R3, T-R4, T-R5 and T-R11 and every table need the F5 to  |
| OQ-004 | src/geofrea/core/schemas.py:509 | The F5 parameters (M-F5-01, M-F5-03) are null with `status = "pending_research"` until OQ-004 and OQ-005 give  |
| OQ-005 | docs/_audit/2026-10_F5_design.md:139 | - `config/technologies.yaml` wind block: `power_curves: {<iec_class>: <curve_id>}` and `iec_class_rule`, both  |
| OQ-005 | docs/_audit/2026-10_F5_design.md:141 | - Until OQ-005 closes there is **no curve for a real country**: wind F5 raises `MissingParameterError` for BRA |
| OQ-005 | docs/_audit/2026-10_F5_design.md:183 | ### D3. Representation of the IEC curve while OQ-005 is open |
| OQ-005 | docs/_audit/2026-10_F5_design.md:300 | Open follow-ups created by the verdicts: METHODOLOGY changelog lines for D5 and D6 (before the code), and the  |
| OQ-005 | docs/_audit/2026-10_pre_research_audit.md:121 | / A-04 / 395 / implemented / `core/config_loader.py:79`; `core/config_schemas.py:1` / 7 / Loader exists (`conf |
| OQ-005 | docs/phases/F5_technical_potential.md:40 | - **D-F5-003 — IEC curve while OQ-005 is open (D3; M-F5-03, A-09).** The `PowerCurve` schema and its loader ex |

## 2e. IDs citados em docs/_archive

Citações em arquivos de `docs/_archive/` de IDs que hoje têm definição ativa: **0** (em 0 arquivos). Citações de IDs sem definição em lugar nenhum: **0** (em 0 arquivos). O script não decide se a citação trata o ID "como ativo"; só mostra que o ID existe hoje.

(nenhum)

Exemplos (até 10):

(nenhum)

## 3. Caminhos, links, testes e funções citados em docs/ que não existem

Verificado só em `docs/` (245 arquivos de texto do corpus). Resolução de caminho: relativo à raiz, a `docs/`, `src/geofrea/`, `src/`, `tests/`, `tests/unit/`, `tests/synthetic/`, `scripts/`, `config/`, `docs/phases/`, `.github/workflows/`, à pasta do próprio arquivo, e por nome de arquivo único no repositório. Extensões checadas por caminho solto: `.py .md .tex .yaml .yml .bib .toml .sh`; `.json` e `.csv` só quando o caminho começa por `config/ docs/ tests/ scripts/ src/ .github/`. Ignorados: caminhos com `<` `{` `*` `$`, os de dados fora do repositório (`outputs/`, `raw/`, `interim/`, `external/`, `logs/`, URLs, discos). Nomes de teste: `def test_*` em `tests/` e `scripts/`. Funções: `arquivo.py:nome` ou `arquivo.py::nome` (símbolo no arquivo) e `` `nome_com_underscore()` `` (definido em qualquer `.py` do corpus). Limites: citações de código do repositório legado (GeoWorld) e nomes de arquivos gerados por execuções aparecem como mortos; o script não separa.

**Total de referências mortas: 1519.**

| tipo | checadas | mortas | em docs ativos | em _audit | em _archive | em DECISIONS.md |
|---|---|---|---|---|---|---|
| caminho | 6987 | 1193 | 153 | 702 | 225 | 113 |
| link relativo | 35 | 8 | 0 | 0 | 0 | 0 |
| nome de teste | 395 | 64 | 23 | 16 | 1 | 24 |
| nome de função | 1074 | 254 | 56 | 59 | 114 | 25 |

Exemplos (até 10 por tipo; `arquivo:linha`), apenas em docs ativos quando houver:


**caminho** (1193 mortas):

| onde | citado |
|---|---|
| docs/CONVENTIONS.md:179 | src/craei/acquire/auxiliary.py |
| docs/LIMITATIONS.md:78 | scripts/archive_geofrea_data.py |
| docs/LIMITATIONS.md:81 | patch_manifest_118.py |
| docs/METHODOLOGY.md:246 | members.yaml |
| docs/METHODOLOGY.md:247 | members.yaml |
| docs/METHODOLOGY.md:258 | members.yaml |
| docs/METHODOLOGY.md:612 | members.yaml |
| docs/METHODOLOGY.md:612 | members.yaml |
| docs/OPEN_QUESTIONS.md:22 | scratchpad/f3_profile2.py |
| docs/PIPELINE_GUIDE.md:150 | members.yaml |

**link relativo** (8 mortas):

| onde | citado |
|---|---|
| docs/phases/core/coverage_alignment_54.md:60 | coverage_alignment_54/coverage_IND_layer_land_cover_tiles.png |
| docs/phases/core/coverage_alignment_54.md:60 | coverage_alignment_54/coverage_IND_layer_elevation_raw.png |
| docs/phases/core/coverage_alignment_54.md:60 | coverage_alignment_54/coverage_IND_layer_slope_glo30_tiles.png |
| docs/phases/core/coverage_alignment_54.md:60 | coverage_alignment_54/coverage_IND_layer_population.png |
| docs/phases/core/coverage_alignment_54.md:60 | coverage_alignment_54/coverage_IND_layer_protected.png |
| docs/phases/core/coverage_alignment_54.md:60 | coverage_alignment_54/coverage_IND_layer_wind_gwa.png |
| docs/phases/core/coverage_alignment_54.md:109 | coverage_alignment_54/elevation_gaps_IND.png |
| docs/phases/core/coverage_alignment_54.md:109 | coverage_alignment_54/elevation_gaps_BRA.png |

**teste** (64 mortas):

| onde | citado |
|---|---|
| docs/CONVENTIONS.md:195 | test_regret_is_non_negative |
| docs/phases/F2b_siting_layers.md:37 | test_protected_areas_footprint_matches_frozen |
| docs/phases/F3_land_eligibility.md:199 | test_the_share_caches_are_keyed_by_the_code_that_computes_them |
| docs/phases/F5/oq053_report.md:77 | test_siting_sanity |
| docs/phases/F5_technical_potential.md:21 | test_class_follows_the_mean_speed_with_the_last_class_unbounded |
| docs/phases/F5_technical_potential.md:21 | test_class_rule_rejects_malformed_rules |
| docs/phases/F5_technical_potential.md:21 | test_registry_rule_and_curves_must_name_the_same_classes |
| docs/phases/F5_technical_potential.md:23 | test_declared_masked_cell_member_has_no_row_and_is_counted |
| docs/phases/F5_technical_potential.md:23 | test_wind_factor_out_of_range_in_a_candidate_cell_raises |
| docs/phases/F5_technical_potential.md:26 | test_real_countries_fail_loud_listing_the_missing_parameters_and_write_nothing |

**função** (254 mortas):

| onde | citado |
|---|---|
| docs/CONVENTIONS.md:154 | periodic_progress() |
| docs/figures/inventory.md:12 | overview/figures.py:plot_aligned_layers |
| docs/figures/inventory.md:13 | overview/figures.py:plot_eligibility |
| docs/figures/inventory.md:14 | overview/figures.py:plot_hazard_context |
| docs/figures/inventory.md:17 | land_eligibility/map_raster.py:plot_grid |
| docs/figures/inventory.md:18 | technical_potential/absolute_maps.py:_plot_cells |
| docs/figures/inventory.md:19 | technical_potential/absolute_maps.py:_plot_states |
| docs/phases/F1_data_acquisition.md:171 | phase.py:_HASH_BUDGET_S |
| docs/phases/F1_data_acquisition.md:175 | phase.py:_HASH_CHUNK_BYTES |
| docs/phases/F1_data_acquisition.md:175 | fetchers/gadm.py:_HASH_CHUNK_SIZE |

Lista completa com arquivo e linha: `02b_dead_refs_full.tsv` (1519 linhas).


## 4. Citações `arquivo:linha`

Verificação: o arquivo existe; a linha (ou o intervalo) existe; e, quando a linha que cita traz um nome entre crases (4 caracteres ou mais, sem ponto nem barra), esse nome aparece no alvo a até 5 linhas da linha citada. Sem nome entre crases, só se verifica a existência da linha.

**Total de citações com linha: 1550; com problema: 889.**

| resultado | citações |
|---|---|
| arquivo não encontrado | 486 |
| linha fora do arquivo | 47 |
| símbolo achado a até 5 linhas | 162 |
| símbolo NÃO achado a até 5 linhas | 356 |
| linha existe, sem símbolo citado para verificar | 496 |
| alvo não lido (grande ou binário) | 3 |

Problemas por classe do arquivo que cita:

| quem cita | arquivo não encontrado | linha fora do arquivo | símbolo não achado |
|---|---|---|---|
| DECISIONS | 1 | 1 | 2 |
| _archive | 14 | 0 | 3 |
| _audit | 465 | 44 | 313 |
| ativo | 4 | 2 | 38 |
| código (src, tests, scripts, config) | 2 | 0 | 0 |

Exemplos — arquivo não encontrado (até 10, de 486):

| onde | citação |
|---|---|
| docs/CONVENTIONS.md:179 | src/craei/acquire/auxiliary.py:57 |
| docs/DECISIONS.md:1498 | criteria_functions.py:457-486 |
| docs/_archive/2026-09/architecture/ghg_abatement.md:62 | ghg_abatement_calculator.py:912 |
| docs/_archive/2026-09/architecture/grid_alignment.md:69 | grid_aligner.py:910 |
| docs/_archive/2026-09/architecture/lcoe_modeling.md:36 | lcoe_calculator.py:909-911 |
| docs/_archive/2026-09/architecture/lcoe_modeling.md:64 | economics.py:75 |
| docs/_archive/2026-09/architecture/lcoe_modeling.md:87 | potential_calculator.py:481-486 |
| docs/_archive/2026-09/architecture/lcoe_modeling.md:87 | lcoe_calculator.py:840-845 |
| docs/_archive/2026-09/architecture/lcoe_modeling.md:88 | potential_calculator.py:466-469 |
| docs/_archive/2026-09/architecture/lcoe_modeling.md:88 | lcoe_calculator.py:1061-1067 |

Exemplos — linha fora do arquivo (até 10, de 47):

| onde | citação |
|---|---|
| docs/DECISIONS.md:268 | core/constants.py:179-193 (arquivo tem 91 linhas) |
| docs/_audit/2026-09_arco_era5_validation.md:153 | era5_registry.py:179 (arquivo tem 162 linhas) |
| docs/_audit/2026-09_conformance_check.md:45 | schemas.py:319-321 (arquivo tem 301 linhas) |
| docs/_audit/2026-09_conformance_check.md:45 | schemas.py:319 (arquivo tem 301 linhas) |
| docs/_audit/2026-09_parameters.md:172 | src/geofrea/core/constants.py:83-99 (arquivo tem 91 linhas) |
| docs/_audit/2026-09_repo_cleanup.md:52 | src/geofrea/core/paths.py:302 (arquivo tem 272 linhas) |
| docs/_audit/2026-10_pre_research_audit.md:250 | test_paths.py:128 (arquivo tem 108 linhas) |
| docs/_audit/checkpoint_98.md:45 | pipeline.py:648-935 (arquivo tem 394 linhas) |
| docs/_audit/checkpoint_98.md:53 | pipeline.py:870-940 (arquivo tem 394 linhas) |
| docs/_audit/checkpoint_98.md:67 | core/raster_io.py:168 (arquivo tem 153 linhas) |

Exemplos — símbolo NÃO achado a até 5 linhas (até 10, de 356):

| onde | citação |
|---|---|
| docs/DECISIONS.md:1456 | audit.py:163-164; símbolos: data_quality_audit, grid_alignment, cache_path |
| docs/DECISIONS.md:1456 | alignment.py:286; símbolos: data_quality_audit, grid_alignment, cache_path |
| docs/OPEN_QUESTIONS.md:41 | evaluator.py:343; símbolos: q_ref, q_ref |
| docs/_archive/2026-09/architecture/results_synthesis.md:17 | main.py:820; símbolos: Path, PotentialResult |
| docs/_archive/2026-09/architecture/results_synthesis.md:18 | main.py:810; símbolos: Path |
| docs/_archive/2026-09/architecture/results_synthesis.md:82 | main.py:802-826; símbolos: _normalize_potential, _normalize_lcoe, recover_potential_from_disk |
| docs/_audit/2026-09_F1-F2b.md:17 | src/geofrea/core/schemas.py:406-431; símbolos: _CRITERION_SPECS, _SPECIAL_CRITERIA, CriteriaParams |
| docs/_audit/2026-09_F1-F2b.md:21 | config/parameters.json:494; símbolos: solar_resource, solar, compute_solar_resource |
| docs/_audit/2026-09_F1-F2b.md:23 | core/schemas.py:411; símbolos: road_suitability, roads, compute_road_suitability |
| docs/_audit/2026-09_F1-F2b.md:23 | config/parameters.json:535; símbolos: road_suitability, roads, compute_road_suitability |

## 5. Numeração

| série | linhas na tabela | maior ID na tabela | próximo livre (acima de todo ID citado) | maior ID citado em qualquer lugar | lacunas na tabela | lacunas citadas em outro lugar | lacunas nunca vistas | duplicatas na tabela |
|---|---|---|---|---|---|---|---|---|
| OQ | 26 | OQ-093 | OQ-094 | OQ-093 | 67 | 67 | 0 | 0 |
| L | 111 | L-236 | L-237 | L-236 | 125 | 2 | 123 | 0 |

- Próximo ID depois do maior da tabela: OQ-094 e L-237. O "próximo livre" acima considera também os IDs citados fora da tabela (OQ resolvidos são apagados, então o número não pode ser reutilizado sem colisão).
- Lacunas da tabela de OQ (67): 2, 3, 4, 5, 6, 9, 11, 12, 15, 16, 17, 18, 19, 22, 23 .... Citadas em outro lugar: 67; nunca vistas: 0 ().
- Lacunas da tabela de L (125): 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87 .... Citadas em outro lugar: 2; nunca vistas: 123 (73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87 ...).
- Duplicatas OQ: nenhuma; duplicatas L: nenhuma.
- Seções de `LIMITATIONS.md`: linha 7: ## Method limitations; linha 84: ## Scope boundaries; linha 94: ## Tier 3 values; linha 120: ## Limitations specific to Groups 4, 5 and 7.
- IDs de L fora de ordem crescente na tabela: 4 (L-56 antes de L-54, L-55 antes de L-53, L-53 antes de L-20, L-223 antes de L-211).

Lacunas por série de `D-*` e `M-F*` (definições):

| série | definidos | maior | lacunas | números ausentes (até 8) |
|---|---|---|---|---|
| D-E5b | 1 | 1 | 0 |  |
| D-F1 | 31 | 31 | 0 |  |
| D-F1b | 18 | 19 | 1 | 16 |
| D-F2a | 29 | 29 | 0 |  |
| D-F2b | 8 | 8 | 0 |  |
| D-F3 | 26 | 30 | 4 | 4, 6, 14, 16 |
| D-F4 | 27 | 28 | 1 | 27 |
| D-F5 | 41 | 41 | 0 |  |
| D-F6 | 29 | 29 | 0 |  |
| D-F7 | 60 | 64 | 4 | 30, 31, 32, 33 |
| D-F7b | 7 | 7 | 0 |  |
| D-F8 | 25 | 25 | 0 |  |
| D-core | 54 | 54 | 0 |  |
| M-E1 | 1 | 1 | 0 |  |
| M-F1 | 7 | 7 | 0 |  |
| M-F1b | 2 | 2 | 0 |  |
| M-F2a | 11 | 11 | 0 |  |
| M-F2b | 6 | 6 | 0 |  |
| M-F3 | 7 | 7 | 0 |  |
| M-F4 | 7 | 7 | 0 |  |
| M-F5 | 7 | 7 | 0 |  |
| M-F6 | 10 | 10 | 0 |  |
| M-F7 | 11 | 11 | 0 |  |
| M-F7b | 4 | 4 | 0 |  |
| M-F8 | 3 | 3 | 0 |  |
