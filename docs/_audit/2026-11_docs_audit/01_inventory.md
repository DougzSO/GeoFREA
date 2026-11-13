# 01 — Inventário de docs/ (COMANDO 147-A)

Gerado em 2026-11-13 por script (scratchpad `inv147.py`); somente leitura. Nenhum arquivo de docs ou código foi alterado. Este diretório fica não rastreado até o 147-H.

**Total: 277 arquivos em docs/ (19 binários, sem contagem de linhas) e 48,672 linhas.** Contado com os rastreados (`git ls-files`) mais os não rastreados que não são deste diretório de auditoria.

## Contagem por pasta (dois níveis)

| pasta | arquivos | linhas |
|---|---|---|
| docs | 8 | 3,140 |
| docs/_archive | 16 | 2,218 |
| docs/_audit | 174 | 26,347 |
| docs/data | 2 | 385 |
| docs/figures | 26 | 845 |
| docs/phases | 31 | 11,044 |
| docs/thesis | 20 | 4,693 |

## Contagem por pasta (três níveis)

| pasta | arquivos | linhas |
|---|---|---|
| docs | 8 | 3,140 |
| docs/_archive/2026-09 | 16 | 2,218 |
| docs/_audit | 88 | 13,516 |
| docs/_audit/2026-10_data_diagnostics_scripts | 12 | 1,760 |
| docs/_audit/2026-10_pre_research_audit_scripts | 2 | 1,133 |
| docs/_audit/group6_decomposition | 6 | 90 |
| docs/_audit/profile_76_tables | 50 | 7,485 |
| docs/_audit/proofs_75_77 | 12 | 1,590 |
| docs/_audit/proofs_98 | 4 | 773 |
| docs/data | 2 | 385 |
| docs/figures | 7 | 695 |
| docs/figures/display_layers_70 | 4 | 0 |
| docs/figures/examples | 7 | 150 |
| docs/figures/migration_68 | 8 | 0 |
| docs/phases | 14 | 1,545 |
| docs/phases/F5 | 12 | 8,405 |
| docs/phases/core | 5 | 1,094 |
| docs/thesis | 4 | 609 |
| docs/thesis/hypotheses | 5 | 1,611 |
| docs/thesis/methods | 8 | 1,754 |
| docs/thesis/theory | 3 | 719 |

## Contagem por classificação (um arquivo pode ter mais de uma)

| classe | arquivos |
|---|---|
| ativo | 142 |
| arquivado | 16 |
| sem referência de entrada | 60 |
| referência só por nome | 62 |
| duplicado | 0 |
| grande | 11 |

Critérios (só evidência, sem julgamento):
- **ativo:** último commit nos últimos 60 dias (janela de 2026-09-14 a 2026-11-13) E pelo menos uma referência por caminho vinda de outro arquivo; fora de `_archive`.
- **arquivado:** o caminho contém `/_archive/`.
- **sem referência de entrada:** nenhum outro arquivo do repositório (docs, src, tests, scripts, .github, config, raiz) contém o caminho nem o nome do arquivo. **referência só por nome:** só o nome aparece, não o caminho (pode ser coincidência com nomes comuns).
- **duplicado:** conteúdo idêntico, mesmo título (md e tex) ou conjunto de linhas com Jaccard de pelo menos 0,8 (arquivos com 10 linhas ou mais).
- **grande:** mais de 500 linhas.
- Referência = a string do caminho (relativo a docs/ ou com `docs/`) aparece no texto de outro arquivo de texto rastreado ou não rastreado. Não verifiquei se a referência é um link válido ou só uma citação. Binários (png) não são lidos como corpus, então não aparecem como referenciadores.
- Último commit: `git log --name-only` na pasta docs; renomeações aparecem pelo nome novo.
- Título: primeira linha não vazia do arquivo (sem os `#`), até 70 caracteres; as 5 primeiras linhas não foram transcritas para manter o relatório compacto.

## Onde cada tipo de registro está hoje

| tipo | arquivo | IDs usados |
|---|---|---|
| decisões do autor | `docs/DECISIONS.md` (66 entradas datadas `## [AAAA-MM-DD] - nome`, de 2026-08-19 a 2026-11-13); sem esquema de IDs numéricos | data + nome |
| decisões de implementação por fase | `docs/phases/*.md` (31 arquivos, incl. `core/` e `F5/`) | `D-F*-NNN`, `D-core-NNN`: 362 IDs distintos, sufixo numérico de 1 a 64 (D-F1-001, D-F1-002, D-F1-003, D-F1-004 ...) |
| regras de método | `docs/METHODOLOGY.md` | `M-F*-NN`: 75 IDs distintos, sufixo numérico de 1 a 11; outros prefixos de uma letra (`U-`, `T-`, `V-`, `A-`, `S-`, `L-`): 64 IDs |
| perguntas abertas | `docs/OPEN_QUESTIONS.md` | `OQ-NNN`: 26 IDs distintos, sufixo numérico de 1 a 93 (só as linhas de tabela presentes; as resolvidas são apagadas, então a lista não é contígua) |
| limitações | `docs/LIMITATIONS.md` | `L-NNN`: 111 IDs distintos, sufixo numérico de 1 a 236 |
| estado de progresso | `docs/PROGRESS.json` (existe); arquivado em `docs/_archive/2026-09/PROGRESS.json` | não encontrado (JSON, sem esquema de IDs lido aqui) |
| convenções | `docs/CONVENTIONS.md`; `CLAUDE.md` na raiz (existe) | não encontrado (texto, sem IDs) |
| resultados de auditoria | `docs/_audit/` (174 arquivos, 88 `.md`; também `docs/phases/F5/audit_potential_65/`) | nomes por data e tema (`AAAA-MM_*.md`, `round_NNN.md`, `window_NNN.md`); IDs próprios não encontrados |

## Inventário por arquivo

Colunas de referências por caminho: docs / src / tests / scripts / workflows / config / raiz. `nome` = outros arquivos que citam só o nome.

| arquivo | linhas | último commit | título | refs d/s/t/sc/w/c/r | nome | classes |
|---|---|---|---|---|---|---|
| CONVENTIONS.md | 198 | 2026-11-06 | CONVENTIONS.md: GeoFREA | 16/4/1/1/0/1/2 | 0 | ativo |
| DECISIONS.md | 1643 | 2026-11-13 | DECISIONS.md — GeoFREA | 18/16/8/0/0/1/1 | 23 | ativo, grande |
| LIMITATIONS.md | 138 | 2026-11-13 | LIMITATIONS.md: GeoFREA | 21/2/0/0/0/2/3 | 0 | ativo |
| METHODOLOGY.md | 643 | 2026-11-12 | GeoFREA Methodology Specification | 31/1/3/0/0/0/3 | 0 | ativo, grande |
| OPEN_QUESTIONS.md | 43 | 2026-11-13 | OPEN_QUESTIONS.md: GeoFREA | 30/2/0/0/0/0/4 | 0 | ativo |
| PIPELINE_GUIDE.md | 328 | 2026-11-06 | GeoFREA pipeline guide | 2/0/0/0/0/0/1 | 0 | ativo |
| PROGRESS.json | 106 | 2026-11-12 | (JSON) | 33/0/1/0/0/1/3 | 0 | ativo |
| PROJECT_SUMMARY.md | 41 | 2026-10-29 | GeoFREA: project summary | 2/0/0/0/0/0/1 | 0 | ativo |
| _archive/2026-09/CLAUDE.md | 51 | 2026-09-15 | CLAUDE.md — GeoFREA | 0/0/0/0/0/0/0 | 31 | arquivado, referência só por nome |
| _archive/2026-09/CONVENTIONS.md | 195 | 2026-09-15 | CONVENTIONS.md — GeoFREA | 1/0/0/0/0/0/0 | 24 | arquivado |
| _archive/2026-09/PROGRESS.json | 114 | 2026-09-15 | (JSON) | 0/0/0/0/0/0/0 | 38 | arquivado, referência só por nome |
| _archive/2026-09/README.md | 3 | 2026-09-15 | Archived on 2026-09-15. | 0/0/0/0/0/0/0 | 5 | arquivado, referência só por nome |
| _archive/2026-09/architecture/baseline-manifest.md | 644 | 2026-09-15 | Não corresponde a uma fase específica — inventário do baseline de regr | 0/1/0/0/0/1/0 | 5 | arquivado, grande |
| _archive/2026-09/architecture/data_quality_audit.md | 62 | 2026-09-15 | Corresponde à Fase 1 — Audit do GeoWorld legado. | 0/4/0/0/0/0/0 | 3 | arquivado |
| _archive/2026-09/architecture/ghg_abatement.md | 72 | 2026-09-15 | Corresponde à Fase 7 — GHG Abatement do GeoWorld legado. | 2/0/0/0/0/0/0 | 4 | arquivado |
| _archive/2026-09/architecture/grid_alignment.md | 88 | 2026-09-15 | Corresponde à Fase 2a — Grid Alignment do GeoWorld legado. | 0/1/0/0/0/0/0 | 3 | arquivado |
| _archive/2026-09/architecture/lcoe_modeling.md | 88 | 2026-09-15 | Corresponde à Fase 5 — LCOE do GeoWorld legado. | 1/0/0/0/0/0/0 | 5 | arquivado |
| _archive/2026-09/architecture/module-mapping.md | 65 | 2026-09-15 | Não corresponde a uma fase específica — âncora de rastreabilidade entr | 0/0/1/0/0/0/0 | 4 | arquivado |
| _archive/2026-09/architecture/potential_analysis.md | 80 | 2026-09-15 | Corresponde à Fase 4 — Potential do GeoWorld legado. | 1/0/0/0/0/0/0 | 4 | arquivado |
| _archive/2026-09/architecture/results_synthesis.md | 93 | 2026-09-15 | Corresponde à Fase 6 — Results do GeoWorld legado. | 1/0/0/0/0/0/0 | 2 | arquivado |
| _archive/2026-09/architecture/sensitivity_analysis.md | 83 | 2026-09-15 | Corresponde à Fase 8 — Sensitivity Analysis do GeoWorld legado. | 1/0/0/0/0/0/0 | 5 | arquivado |
| _archive/2026-09/architecture/suitability_analysis.md | 76 | 2026-09-15 | Corresponde à Fase 3 — Suitability do GeoWorld legado. | 1/0/0/0/0/0/0 | 2 | arquivado |
| _archive/2026-09/architecture/suitability_criteria.md | 82 | 2026-09-15 | Corresponde à Fase 2b — Criteria do GeoWorld legado. | 1/0/0/0/0/0/0 | 4 | arquivado |
| _archive/2026-09/architecture/suitability_criteria_audit.md | 422 | 2026-10-08 | Suitability Criteria (Fase 2b) — Auditoria do legado + contrato revisa | 1/0/0/0/0/0/0 | 1 | arquivado |
| _audit/2026-09_F1-F2b.md | 143 | 2026-10-27 | Auditoria de fatos de código — Fase 1 / Fase 2a / Fase 2b | 6/0/0/0/0/0/0 | 0 | ativo |
| _audit/2026-09_arco_era5_validation.md | 218 | 2026-09-29 | F4-4: ARCO-ERA5 validation — numeric equivalence, real cost, hash prot | 1/0/0/1/0/0/0 | 0 | ativo |
| _audit/2026-09_cds_stability_diagnosis.md | 214 | 2026-09-29 | F4-3: CDS instability diagnosis (2026-09-28) | 2/0/0/1/0/0/0 | 0 | ativo |
| _audit/2026-09_conformance_check.md | 213 | 2026-09-24 | 2026-09 conformance check (COMMAND ADJ-3b) | 2/0/0/0/0/0/0 | 0 | ativo |
| _audit/2026-09_craei_climate_reuse.md | 187 | 2026-10-27 | CRAEI ISIMIP3b climate reuse decision (ADJ-6) | 2/0/0/0/0/0/0 | 0 | ativo |
| _audit/2026-09_data_coverage.md | 173 | 2026-09-22 | Data Coverage Audit — 2026-09-22 | 1/0/0/0/0/0/0 | 1 | ativo |
| _audit/2026-09_data_state_pre_G.md | 207 | 2026-09-27 | GeoFREA Data State Audit — Pre-Stage-G (ADJ-4) | 4/0/0/0/0/0/0 | 0 | ativo |
| _audit/2026-09_embedded_values.md | 164 | 2026-10-08 | 2026-09 embedded-value sweep (COMMAND ADJ-6) | 3/1/0/0/0/0/0 | 0 | ativo |
| _audit/2026-09_geofrea_data_inventory.md | 305 | 2026-09-22 | GeoFREA Data Inventory Audit | 2/0/0/0/0/0/0 | 1 | ativo |
| _audit/2026-09_layer_quantities.md | 270 | 2026-09-24 | Layer quantities, units and ranges — read-only verification (ADJ-1) | 2/0/0/0/0/1/0 | 1 | ativo |
| _audit/2026-09_legacy_F3-F8.md | 203 | 2026-10-27 | Auditoria de fatos — lógica legada de Aptidão/Potencial/LCOE/Síntese/S | 2/0/0/0/0/0/0 | 1 | ativo |
| _audit/2026-09_parameters.md | 188 | 2026-09-15 | Auditoria de fatos de código — Inventário de parâmetros (Fase 1/2a/2b) | 3/0/0/0/0/0/0 | 0 | ativo |
| _audit/2026-09_pipeline_provenance_map.md | 264 | 2026-10-27 | GeoFREA Pipeline Provenance and Conformance Audit | 1/0/0/0/0/0/0 | 0 | ativo |
| _audit/2026-09_raw_data_inventory.md | 288 | 2026-09-22 | E6 Raw Data Inventory Audit — 2026-09-22 | 1/0/0/0/0/0/0 | 0 | ativo |
| _audit/2026-09_records.md | 183 | 2026-10-27 | Auditoria de fatos — dimensionamento da migração de `DECISIONS.md`/`CO | 3/0/0/0/0/0/0 | 0 | ativo |
| _audit/2026-09_repo_cleanup.md | 377 | 2026-09-24 | 2026-09 repository cleanup audit (COMMAND ADJ-3) | 4/0/0/0/0/0/0 | 1 | ativo |
| _audit/2026-09_resource_products.md | 68 | 2026-10-27 | Auditoria de fatos — produtos GWA/GSA (vento e solar), verificação de  | 3/0/0/0/0/0/0 | 0 | ativo |
| _audit/2026-10_F5_design.md | 300 | 2026-10-08 | F5 technical_potential: input inventory and design for the author's ve | 2/0/0/0/0/0/0 | 1 | ativo |
| _audit/2026-10_F6_design.md | 342 | 2026-10-27 | F6 lcoe_modeling: CRAEI check, input inventory and design for the auth | 4/0/0/0/0/0/0 | 1 | ativo |
| _audit/2026-10_F7_design.md | 429 | 2026-10-09 | F7 robustness_analysis and F7b external_validation: inventory and desi | 3/0/0/0/0/0/0 | 1 | ativo |
| _audit/2026-10_F8_design.md | 205 | 2026-10-13 | F8 results_synthesis: inventory and design for the author's verdicts | 2/0/0/0/0/1/0 | 1 | ativo |
| _audit/2026-10_data_diagnostics.md | 376 | 2026-10-27 | Data diagnostics, October 2026: MIROC6 wind (B-1), wind candidates at  | 5/1/0/1/0/1/0 | 0 | ativo |
| _audit/2026-10_data_diagnostics_scripts/altitude_k.py | 315 | 2026-10-15 | ruff: noqa | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/2026-10_data_diagnostics_scripts/b1_compute.py | 56 | 2026-10-15 | ruff: noqa | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/2026-10_data_diagnostics_scripts/b1_miroc6_accepted.py | 144 | 2026-10-15 | ruff: noqa | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/2026-10_data_diagnostics_scripts/b1_options.py | 194 | 2026-10-15 | ruff: noqa | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/2026-10_data_diagnostics_scripts/b1_reference.py | 289 | 2026-10-15 | ruff: noqa | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/2026-10_data_diagnostics_scripts/common.py | 109 | 2026-10-15 | ruff: noqa | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/2026-10_data_diagnostics_scripts/dT_isolated_cells.py | 53 | 2026-10-15 | ruff: noqa | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/2026-10_data_diagnostics_scripts/dT_negative.py | 163 | 2026-10-15 | ruff: noqa | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/2026-10_data_diagnostics_scripts/era5_gust_mean.py | 37 | 2026-10-15 | ruff: noqa | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/2026-10_data_diagnostics_scripts/era5_heat_days.py | 140 | 2026-10-15 | ruff: noqa | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/2026-10_data_diagnostics_scripts/heat_days.py | 146 | 2026-10-15 | ruff: noqa | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/2026-10_data_diagnostics_scripts/w5e5_heat_days.py | 114 | 2026-10-15 | ruff: noqa | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/2026-10_disk_and_data_inventory.md | 74 | 2026-10-07 | Disk and data inventory — what GeoFREA holds, what can go, what exists | 1/0/0/0/0/0/0 | 0 | ativo |
| _audit/2026-10_distance_connection_cost_evidence.md | 104 | 2026-10-06 | Distance to grid/roads and the connection-cost model — literature evid | 4/0/0/0/0/0/0 | 0 | ativo |
| _audit/2026-10_f2b_sanity.md | 83 | 2026-10-09 | F2b physical layers: statistics against their sanity ranges (H-6, V-04 | 2/0/0/1/0/0/0 | 0 | ativo |
| _audit/2026-10_f3_baseline_hashes.json | 593 | 2026-10-14 | (JSON) | 1/0/0/0/0/0/0 | 0 | ativo, grande |
| _audit/2026-10_f3_parameter_research.md | 116 | 2026-10-08 | F3 / H-3 parameter research — proposed exclusion parameters, sources,  | 3/1/0/0/0/0/0 | 0 | ativo |
| _audit/2026-10_gcm_selection_j1.md | 141 | 2026-10-06 | J-1 — GCM selection (M-F4-02), evidence for OQ-009 | 1/0/0/0/0/1/0 | 0 | ativo |
| _audit/2026-10_gcm_selection_spread.md | 71 | 2026-10-06 | M-F4-02 criterion 3 — change-factor spread (selection diagnostic) | 2/0/0/0/0/0/0 | 1 | ativo |
| _audit/2026-10_general_audit_71.md | 516 | 2026-10-27 | General audit of the pipeline before Group 3 (COMMAND 71, 2026-10-27) | 3/0/0/0/0/0/0 | 1 | ativo, grande |
| _audit/2026-10_land_availability_ranges_design.md | 61 | 2026-10-07 | Design note — land-availability parameters as ranges, sampled instead  | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/2026-10_parameter_inventory_for_ranges.md | 44 | 2026-10-08 | Inventory of numeric parameters in `config/` and what should become a  | 1/0/0/0/0/0/0 | 0 | ativo |
| _audit/2026-10_pipeline_state.md | 88 | 2026-10-07 | Pipeline state and `main.py` wiring — what exists, what runs, what is  | 1/0/0/0/0/0/0 | 1 | ativo |
| _audit/2026-10_plants_vs_osm_grid.md | 147 | 2026-10-07 | Existing power plants against the OSM grid layer — is a large `dist_gr | 4/0/0/0/0/0/0 | 1 | ativo |
| _audit/2026-10_pre_research_audit.md | 536 | 2026-10-15 | Pre-research audit of GeoFREA (repository and GeoFREA_data) | 3/0/0/0/0/0/0 | 1 | ativo, grande |
| _audit/2026-10_pre_research_audit_scripts/plausibility_real_data.py | 149 | 2026-10-14 | ruff: noqa | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/2026-10_pre_research_audit_scripts/validate_zzz_by_hand.py | 984 | 2026-11-09 | ruff: noqa | 4/0/1/0/1/0/1 | 4 | ativo, grande |
| _audit/2026-10_systematic_review.md | 409 | 2026-10-08 | Systematic review of code, artifacts and documents against METHODOLOGY | 3/0/0/0/0/0/0 | 0 | ativo |
| _audit/README.md | 14 | 2026-10-30 | docs/_audit: index | 1/0/0/0/0/0/0 | 4 | ativo |
| _audit/awaiting_content_check_post_77.md | 18 | 2026-11-09 | Entries still in `awaiting_content_check_post_77` (COMMAND 118, 2026-1 | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/bra_line_138_86.md | 27 | 2026-11-02 | BRA: cost per km of a 138 kV single-circuit line (COMMAND 86, OQ-001) | 1/0/0/0/0/1/0 | 3 | ativo |
| _audit/bra_wind_members_map.png | bin | 2026-11-04 | (binary) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/cache_keys_123.md | 51 | 2026-11-10 | Stored cache keys against recomputed keys (COMMANDS 123 and 124; close | 2/0/0/0/0/0/0 | 1 | ativo |
| _audit/checkpoint_98.md | 131 | 2026-11-06 | COMMAND 98 audit: resume after an interruption (inventory, step 0) | 3/0/0/0/0/0/0 | 0 | ativo |
| _audit/ci_red_audit.md | 194 | 2026-11-09 | CI red audit (COMMAND 105) | 0/0/0/0/0/0/1 | 1 | ativo |
| _audit/cleanup_72.md | 53 | 2026-10-27 | Cleanup of audit 71 (COMMAND 72), log | 0/0/0/0/0/0/0 | 2 | referência só por nome |
| _audit/cleanup_82.md | 96 | 2026-10-30 | Cleanup 82: organization of GeoFREA, GeoFREA_data and the sibling fold | 0/0/0/0/0/0/0 | 2 | referência só por nome |
| _audit/closing_131.md | 123 | 2026-11-12 | Closing what does not change a fingerprint (COMMAND 131) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/compare_9c2dc3c8_vs_1d34ab23.md | 105 | 2026-11-09 | Content comparison: round 1d34ab23 against the state of 9c2dc3c8 (COMM | 1/0/0/0/0/0/0 | 1 | ativo |
| _audit/config_scope_127.md | 52 | 2026-11-10 | Configuration scope of F2a and F3, the recorder of reads and the rebas | 1/0/0/0/0/0/0 | 0 | ativo |
| _audit/consistency-2026-09-14.md | 54 | 2026-10-27 | Relatório de Auditoria Documental — GeoFREA | 0/0/0/0/0/0/0 | 3 | referência só por nome |
| _audit/data_cleanup_list_131.md | 57 | 2026-11-12 | What `GeoFREA_data` holds that no current manifest references (COMMAND | 1/0/0/0/0/0/0 | 0 | ativo |
| _audit/dist_scale_prototype.md | 89 | 2026-11-09 | Distance-to-substation layer: consumers, other single-latitude convers | 2/0/0/0/0/0/0 | 1 | ativo |
| _audit/dist_sub_scale_audit.md | 281 | 2026-11-09 | Distance to the nearest substation: error of the isotropic scale (COMM | 2/0/0/0/0/0/0 | 0 | ativo |
| _audit/engineering_73.md | 89 | 2026-10-27 | Engineering findings of audit 71 closed (COMMAND 73) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/f3_memory_90.md | 74 | 2026-11-04 | F3 (`land_eligibility`) memory on BRA: measurement and proposal (COMMA | 4/1/0/0/0/0/0 | 1 | ativo |
| _audit/f3_peak_118.md | 48 | 2026-11-09 | Why the F3 peak of BRA was 1,481 MB in the round 1d34ab23 and 1,243 MB | 3/0/0/0/0/0/0 | 1 | ativo |
| _audit/f5_member_codes_127.md | 37 | 2026-11-10 | F5: the members of the forcing from the codes, without `astype(str)` ( | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/f5_memory_126.md | 72 | 2026-11-10 | F5 memory reduction, items a, b and d (COMMAND 126, step 1; step 6 of  | 1/0/0/0/0/0/0 | 0 | ativo |
| _audit/f5_peak_map.md | 56 | 2026-11-09 | Map of the memory peak of F5 (`technical_potential`) and `potential_ma | 1/0/0/0/0/0/0 | 0 | ativo |
| _audit/f5_peak_measured.md | 105 | 2026-11-10 | Measured memory of F5 (`technical_potential`) on BRA, step by step (CO | 1/0/0/0/0/0/0 | 2 | ativo |
| _audit/fingerprint_algo_120.md | 66 | 2026-11-10 | Fingerprint algorithm independent of the Python version (COMMAND 120,  | 3/0/0/0/0/0/0 | 0 | ativo |
| _audit/general_audit_130.md | 386 | 2026-11-10 | General audit, read-only (COMMAND 130) | 0/0/0/0/0/0/0 | 2 | referência só por nome |
| _audit/generality_audit.md | 205 | 2026-11-10 | Audit of the generality of the code (COMMAND 125) | 3/1/1/0/0/0/0 | 0 | ativo |
| _audit/group3_audit_83.md | 77 | 2026-11-02 | Group 3 audit (COMMAND 83) | 2/0/0/0/0/0/0 | 0 | ativo |
| _audit/group3_costs_85.md | 72 | 2026-11-02 | Group 3 pending costs: what was found and what was not (COMMAND 85, OQ | 4/0/0/0/0/1/0 | 0 | ativo |
| _audit/group3_stats_139.md | 91 | 2026-11-13 | Group 3 statistics from the outputs of round 133 (COMMAND 139) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/group6_audit_97.md | 150 | 2026-11-05 | Group 6 audit (COMMAND 97): land eligibility in F3 | 4/3/0/0/0/1/0 | 0 | ativo |
| _audit/group6_decomposition/BRA.csv | 7 | 2026-11-07 | country,technology,scenario,area_old_km2,area_before_min_area_km2,area | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/group6_decomposition/BRA.md | 23 | 2026-11-07 | Group 6: change of the eligible area, BRA | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/group6_decomposition/IND.csv | 7 | 2026-11-07 | country,technology,scenario,area_old_km2,area_before_min_area_km2,area | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/group6_decomposition/IND.md | 23 | 2026-11-07 | Group 6: change of the eligible area, IND | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/group6_decomposition/PRT.csv | 7 | 2026-11-07 | country,technology,scenario,area_old_km2,area_before_min_area_km2,area | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/group6_decomposition/PRT.md | 23 | 2026-11-07 | Group 6: change of the eligible area, PRT | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/ind_population_effect_89.md | 24 | 2026-11-04 | Effect of the exact population sum on the F3 results of IND (COMMANDS  | 1/0/0/0/0/0/0 | 1 | ativo |
| _audit/members_per_cell_95.md | 58 | 2026-11-04 | Members per cell and technology, and the wind members that BRA lacks ( | 4/0/0/0/0/0/0 | 0 | ativo |
| _audit/memory_budget_88.md | 115 | 2026-11-04 | Memory budget of F2a and F2b (COMMANDS 88 and 89) | 7/2/0/0/0/1/0 | 0 | ativo |
| _audit/optimization_gain_82.md | 133 | 2026-10-30 | Optimization gain 82: before and after COMMANDS 75 and 77, from the lo | 2/0/0/0/0/0/0 | 1 | ativo |
| _audit/optimizations_77.md | 47 | 2026-10-30 | Optimizations 77: item by item, with the proof and the gain | 3/1/0/0/0/0/0 | 3 | ativo |
| _audit/performance_75.md | 108 | 2026-10-30 | Performance 75: what the pipeline costs now, and the proof that its re | 5/1/0/1/0/1/0 | 4 | ativo |
| _audit/poi_counts_84.md | 10 | 2026-11-02 | Substations of the POI layer by country (COMMAND 84, OQ-067) | 4/0/0/1/0/0/0 | 1 | ativo |
| _audit/population_memory_87.md | 35 | 2026-11-02 | Memory of the population warp of BRA (COMMAND 87) | 0/2/0/0/0/1/0 | 1 | ativo |
| _audit/profile_76.md | 223 | 2026-10-29 | Profile 76: where the time and the memory are | 2/3/0/0/0/0/0 | 3 | ativo |
| _audit/profile_76_tables/bench/q1/bench_log.jsonl | 10 | 2026-10-29 | {"name": "vec_PRT_roads", "when": "2026-10-29T07:56:05", "cap_mb": 500 | 0/0/0/0/0/0/0 | 2 | referência só por nome |
| _audit/profile_76_tables/bench/q1/vec_BRA_rivers.json | 179 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q1/vec_BRA_roads.json | 179 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q1/vec_IND_rivers.json | 179 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q1/vec_IND_roads.json | 179 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q1/vec_PRT_lakes.json | 141 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q1/vec_PRT_rivers.json | 179 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q1/vec_PRT_roads.json | 179 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q1b/bench_log.jsonl | 5 | 2026-10-29 | {"name": "vecb_IND_roads", "when": "2026-10-29T08:36:20", "cap_mb": 50 | 0/0/0/0/0/0/0 | 2 | referência só por nome |
| _audit/profile_76_tables/bench/q1b/vecb_BRA_lakes.json | 203 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q1b/vecb_BRA_rivers.json | 241 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q1b/vecb_BRA_roads.json | 241 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q1b/vecb_IND_rivers.json | 241 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q1b/vecb_IND_roads.json | 241 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q1c/bench_log.jsonl | 3 | 2026-10-29 | {"name": "vecc_PRT_rivers", "when": "2026-10-29T08:42:48", "cap_mb": 5 | 0/0/0/0/0/0/0 | 2 | referência só por nome |
| _audit/profile_76_tables/bench/q1c/vecc_PRT_lakes.json | 203 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q1c/vecc_PRT_rivers.json | 241 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q1c/vecc_PRT_roads.json | 241 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q2/bench_log.jsonl | 40 | 2026-10-29 | {"name": "ras_PRT_population", "when": "2026-10-29T09:25:40", "cap_mb" | 0/0/0/0/0/0/0 | 2 | referência só por nome |
| _audit/profile_76_tables/bench/q2/ras_BRA_glo30.json | 54 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q2/ras_BRA_lc_counts.json | 55 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q2/ras_BRA_population.json | 94 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q2/ras_IND_glo30.json | 55 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q2/ras_IND_lc_counts.json | 55 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q2/ras_IND_population.json | 94 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q2/ras_PRT_glo30.json | 54 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q2/ras_PRT_lc_counts.json | 53 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q2/ras_PRT_lc_mosaic.json | 53 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q2/ras_PRT_population.json | 94 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q2/ras_PRT_solar.json | 48 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q3/bench_log.jsonl | 11 | 2026-10-29 | {"name": "ph_PRT_land_eligibility", "when": "2026-10-29T10:46:26", "ca | 0/0/0/0/0/0/0 | 2 | referência só por nome |
| _audit/profile_76_tables/bench/q3/ph_PRT_climate_maps.json | 225 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q3/ph_PRT_data_quality_audit.json | 225 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q3/ph_PRT_land_eligibility.json | 236 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q3/ph_PRT_overview.json | 236 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q3/ph_PRT_potential_maps.json | 236 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q3/ph_PRT_technical_potential.json | 236 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q4/bench_log.jsonl | 9 | 2026-10-29 | {"name": "fp_PRT_lakes", "when": "2026-10-29T08:46:23", "cap_mb": 500, | 0/0/0/0/0/0/0 | 2 | referência só por nome |
| _audit/profile_76_tables/bench/q4/fp_BRA_lakes.json | 28 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q4/fp_BRA_rivers.json | 28 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q4/fp_BRA_roads.json | 28 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q4/fp_IND_rivers.json | 28 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q4/fp_IND_roads.json | 28 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q4/fp_PRT_lakes.json | 28 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q4/fp_PRT_rivers.json | 28 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/bench/q4/fp_PRT_roads.json | 28 | 2026-10-29 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/profile_76_tables/phases.csv | 435 | 2026-10-29 | country,date,run,phase,reason,status,wall_s,slept_s,awake_s,cpu_s,rati | 0/0/0/0/0/0/0 | 2 | referência só por nome |
| _audit/profile_76_tables/power_events.json | 214 | 2026-10-29 | ﻿{ | 1/0/0/0/0/0/0 | 2 | ativo |
| _audit/profile_76_tables/steps.csv | 1246 | 2026-10-29 | country,date,run,phase,step,kind,wall_s,slept_s,awake_s,temperature,cl | 0/0/0/0/0/0/0 | 2 | referência só por nome, grande |
| _audit/profile_76_tables/summary.md | 118 | 2026-10-29 | Phases by country, temperature and class | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/proofs_75_77/aligned_equivalence_PRT.json | 152 | 2026-10-30 | (JSON) | 1/0/0/1/0/0/0 | 1 | ativo |
| _audit/proofs_75_77/clip_equivalence_1a_PRT.json | 52 | 2026-10-30 | (JSON) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/proofs_75_77/clip_layers_equivalence_IND.json | 44 | 2026-10-30 | (JSON) | 1/0/0/0/0/0/0 | 2 | ativo |
| _audit/proofs_75_77/clip_shortcut_diagnosis_IND.json | 70 | 2026-10-30 | (JSON) | 0/0/0/0/0/0/0 | 2 | referência só por nome |
| _audit/proofs_75_77/cumulative_equivalence_77_PRT.json | 482 | 2026-10-30 | (JSON) | 4/0/0/0/0/0/0 | 1 | ativo |
| _audit/proofs_75_77/figures_pixel_equivalence_itemh_PRT.json | 6 | 2026-10-30 | (JSON) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/proofs_75_77/glo30_equivalence_item8.json | 82 | 2026-10-30 | (JSON) | 1/0/0/0/0/0/0 | 2 | ativo |
| _audit/proofs_75_77/mainland_equivalence_item4.json | 69 | 2026-10-30 | (JSON) | 0/0/0/0/0/0/0 | 2 | referência só por nome |
| _audit/proofs_75_77/polygon_derived_equivalence_item3.json | 108 | 2026-10-30 | (JSON) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/proofs_75_77/polygon_fastpath_equivalence_item3_PRT.json | 297 | 2026-10-30 | (JSON) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/proofs_75_77/population_strips_itemi.json | 71 | 2026-10-30 | (JSON) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/proofs_75_77/shared_clip_equivalence_item2_PRT.json | 157 | 2026-10-30 | (JSON) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/proofs_98/adopt_base_75_to_current_PRT.json | 211 | 2026-11-06 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/proofs_98/cumulative_equivalence_98_PRT.json | 170 | 2026-11-06 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/proofs_98/isolate_group3_PRT.json | 182 | 2026-11-06 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/proofs_98/vs_adopt_base_75_PRT.json | 210 | 2026-11-06 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/pv_degradation_zones_83.md | 35 | 2026-11-02 | PV degradation by thermal zone (COMMAND 83) | 1/0/0/1/0/0/0 | 0 | ativo |
| _audit/pv_zone_shares_84.md | 35 | 2026-11-02 | PV potential and eligible area by thermal zone (COMMAND 84) | 3/0/0/1/0/0/0 | 0 | ativo |
| _audit/ren_source_audit.md | 297 | 2026-11-08 | REN source audit (command after 101) | 3/0/0/0/0/0/0 | 1 | ativo |
| _audit/road_distance_86.md | 14 | 2026-11-04 | Distance to the road D_road of the eligible area (COMMAND 86) | 1/0/0/1/0/0/0 | 3 | ativo |
| _audit/round_133.md | 77 | 2026-11-12 | Round 133: the clean round after the merge of window-132 (2026-11-12) | 3/0/1/0/0/0/0 | 0 | ativo |
| _audit/slope_canopy_99.md | 91 | 2026-11-06 | Slope x canopy (COMMAND 99, step 2) | 3/0/0/1/0/0/0 | 0 | ativo |
| _audit/slope_dem_test_100.md | 481 | 2026-11-06 | Slope test: GLO-30, FABDEM and a 90 m support (COMMAND 100) | 5/0/0/1/0/0/0 | 1 | ativo |
| _audit/slope_dem_test_100_e4.csv | 141 | 2026-11-06 | tile,iso,slope_pct,group,pixels,area_km2,E4_glo30,E4_fabdem,E4_smooth9 | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/slope_dem_test_100_eligible.csv | 169 | 2026-11-06 | tile,iso,technology,scenario,slope_pct,group,eligible_km2_glo30,eligib | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| _audit/stats_116.md | 112 | 2026-11-09 | Distance statistics of the round 1d34ab23 (COMMAND 116, item 6) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/vth_evidence_85.md | 33 | 2026-11-02 | Evidence for the voltage thresholds V_th of the point of interconnecti | 3/0/1/0/0/1/0 | 0 | ativo |
| _audit/window_132.md | 84 | 2026-11-12 | Window 132: what the branch `window-132` changes and what it moves (CO | 0/0/0/0/0/0/0 | 0 | sem referência de entrada |
| _audit/window_list_131.md | 21 | 2026-11-12 | Window list: changes held back because they change the fingerprint of  | 1/0/0/0/0/0/0 | 1 | ativo |
| data/coverage_audit_59.md | 286 | 2026-10-25 | Coverage of the spatial inputs against the country mask (COMMAND 59) | 2/0/0/0/0/0/0 | 1 | ativo |
| data/grid_provenance.md | 99 | 2026-11-12 | Provenance of the transmission-grid data (OQ-063) | 4/0/0/0/0/0/0 | 0 | ativo |
| figures/GEOFREA_figuras_spec_v2.md | 227 | 2026-10-22 | GeoFREA: especificação de correções e padronização de figuras (v2, par | 1/0/0/1/0/0/0 | 0 | ativo |
| figures/display_layers_70.md | 54 | 2026-10-27 | Display layers of the real maps (COMMAND 70) | 4/0/0/0/0/0/0 | 1 | ativo |
| figures/display_layers_70/PRT_F5_capacity-density_solar_central_ref.png | bin | 2026-10-27 | (binary) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| figures/display_layers_70/PRT_F5_capacity-density_wind_central_ref.png | bin | 2026-10-27 | (binary) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| figures/display_layers_70/PRT_F5_capacity-factor_solar_central_ref.png | bin | 2026-10-27 | (binary) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| figures/display_layers_70/PRT_F5_capacity-factor_wind_central_ref.png | bin | 2026-10-27 | (binary) | 0/0/0/0/0/0/0 | 5 | referência só por nome |
| figures/display_resolution_67b.md | 48 | 2026-10-27 | Display resolution of the maps (COMMAND 67b) | 1/0/0/0/0/0/0 | 6 | ativo |
| figures/examples/BRA_example_capacity-factor_wind_central_ref.png | bin | 2026-10-26 | (binary) | 1/0/0/0/0/0/0 | 2 | ativo |
| figures/examples/CHE_example_forcing_solar_SSP3-7.0_2071-2100.png | bin | 2026-10-26 | (binary) | 0/0/0/0/0/0/0 | 2 | referência só por nome |
| figures/examples/CHL_example_dominant-exclusion_solar_central.png | bin | 2026-10-26 | (binary) | 0/0/0/0/0/0/0 | 2 | referência só por nome |
| figures/examples/IDN_example_capacity-density-state_wind_central.png | bin | 2026-10-26 | (binary) | 0/0/0/0/0/0/0 | 2 | referência só por nome |
| figures/examples/LUX_example_capacity-density_solar_central_ref.png | bin | 2026-10-26 | (binary) | 0/0/0/0/0/0/0 | 2 | referência só por nome |
| figures/examples/PRT_example_capacity-density_solar_central_ref.png | bin | 2026-10-26 | (binary) | 0/0/0/0/0/0/0 | 2 | referência só por nome |
| figures/examples/figures_index.json | 150 | 2026-10-26 | (JSON) | 0/0/0/0/0/0/0 | 11 | referência só por nome |
| figures/inventory.md | 73 | 2026-10-27 | Figure inventory (COMMAND 56) | 3/0/0/0/0/0/0 | 0 | ativo |
| figures/migration_68.md | 112 | 2026-10-27 | Figure migration to MapFigure (COMMAND 68) | 3/0/0/0/0/0/0 | 1 | ativo |
| figures/migration_68/BRA_F2a_after.png | bin | 2026-10-26 | (binary) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| figures/migration_68/BRA_F2a_before.png | bin | 2026-10-26 | (binary) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| figures/migration_68/BRA_F3_after.png | bin | 2026-10-26 | (binary) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| figures/migration_68/BRA_F3_before.png | bin | 2026-10-26 | (binary) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| figures/migration_68/BRA_F4_after.png | bin | 2026-10-26 | (binary) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| figures/migration_68/BRA_F4_before.png | bin | 2026-10-26 | (binary) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| figures/migration_68/BRA_F5_after.png | bin | 2026-10-26 | (binary) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| figures/migration_68/BRA_F5_before.png | bin | 2026-10-26 | (binary) | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| figures/questions_69.md | 36 | 2026-10-27 | Figures for the questions of the thesis (COMMAND 69) | 1/0/0/0/0/0/0 | 0 | ativo |
| figures/style_guide.md | 145 | 2026-10-26 | Map style guide (COMMANDS 56 and 66) | 7/1/0/1/0/0/0 | 0 | ativo |
| phases/E1_explorer.md | 24 | 2026-10-13 | E1 explorer | 3/0/0/0/0/0/0 | 0 | ativo |
| phases/E5b.md | 68 | 2026-09-27 | E5b: data layout migration (GEOFREA_DATA_DIR, GEOFREA_SHARED_RAW_DIR) | 4/0/0/0/0/0/0 | 0 | ativo |
| phases/F1_data_acquisition.md | 223 | 2026-10-25 | F1 data_acquisition | 15/5/2/1/0/0/0 | 2 | ativo |
| phases/F1b_data_quality_audit.md | 106 | 2026-10-30 | F1b data_quality_audit | 13/4/1/0/0/1/1 | 4 | ativo |
| phases/F2a_grid_alignment.md | 104 | 2026-11-12 | F2a grid_alignment | 15/2/2/0/0/1/0 | 2 | ativo |
| phases/F2b_siting_layers.md | 68 | 2026-11-09 | F2b siting_layers | 11/0/0/0/0/0/0 | 1 | ativo |
| phases/F3_land_eligibility.md | 258 | 2026-11-08 | F3 land_eligibility | 10/0/0/0/0/0/0 | 2 | ativo |
| phases/F4_climate_forcing.md | 65 | 2026-10-26 | F4 climate_forcing | 8/3/0/0/0/0/0 | 2 | ativo |
| phases/F5/audit_groups1-2.md | 209 | 2026-10-16 | Audit of Groups 1 and 2: what F3, F5 and F6 implement against the .tex | 4/0/1/0/0/0/0 | 0 | ativo |
| phases/F5/audit_potential_65.md | 339 | 2026-10-27 | Numerical audit of the technical potential (T-14, COMMAND 65) | 1/0/0/1/0/0/0 | 1 | ativo |
| phases/F5/audit_potential_65/BRA.json | 2289 | 2026-10-23 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada, grande |
| phases/F5/audit_potential_65/IND.json | 2289 | 2026-10-23 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada, grande |
| phases/F5/audit_potential_65/PRT.json | 2289 | 2026-10-23 | (JSON) | 0/0/0/0/0/0/0 | 0 | sem referência de entrada, grande |
| phases/F5/fix_round_46.md | 123 | 2026-10-16 | Fix round of COMMAND 46 (2026-10-16) | 3/1/0/0/0/0/0 | 0 | ativo |
| phases/F5/groups1-2_implementation_report.md | 132 | 2026-10-16 | Groups 1 and 2: implementation report | 2/0/0/0/0/1/0 | 0 | ativo |
| phases/F5/oq053_report.md | 113 | 2026-10-16 | OQ-053 closed: validity limits for the Weibull layers (COMMAND 48, 202 | 2/0/0/0/0/0/0 | 0 | ativo |
| phases/F5/potential_maps_absolute.md | 107 | 2026-10-27 | Maps of the technical potential in capacity and energy (D-F5-029 and D | 4/0/0/0/0/0/0 | 2 | ativo |
| phases/F5/potential_maps_v2.md | 107 | 2026-10-27 | Maps of the technical potential, version 2 (D-F5-032, COMMAND 60) | 3/0/0/0/0/0/0 | 2 | ativo |
| phases/F5/run_report_real.md | 311 | 2026-10-27 | F5 on real data: run report (PRT, IND and BRA in one round) | 6/0/0/0/0/0/0 | 0 | ativo |
| phases/F5/wind_cf_pixel_74.md | 97 | 2026-10-28 | Wind capacity factor aggregated from the 0.01 degree pixels (COMMAND 7 | 4/0/0/0/0/0/0 | 0 | ativo |
| phases/F5_technical_potential.md | 112 | 2026-11-04 | F5 technical_potential | 7/1/0/0/0/0/0 | 1 | ativo |
| phases/F6_lcoe_modeling.md | 93 | 2026-11-12 | F6 lcoe_modeling | 10/2/0/0/0/0/0 | 0 | ativo |
| phases/F7_robustness_analysis.md | 134 | 2026-11-04 | F7 robustness_analysis | 8/1/0/0/0/0/0 | 1 | ativo |
| phases/F7b_external_validation.md | 44 | 2026-10-27 | F7b external_validation | 5/1/0/0/0/0/0 | 1 | ativo |
| phases/F8_results_synthesis.md | 73 | 2026-10-27 | F8 results_synthesis | 4/0/0/0/0/0/0 | 0 | ativo |
| phases/core.md | 173 | 2026-11-12 | core: orchestration, configuration, shared utilities | 22/6/8/0/1/3/2 | 4 | ativo |
| phases/core/coverage_alignment_54.md | 147 | 2026-10-27 | Coverage of the outline and alignment of elevation and slope (COMMAND  | 3/0/0/0/0/0/0 | 1 | ativo |
| phases/core/geometry_dem_55.md | 275 | 2026-10-19 | Contiguous country mask and one DEM; F1 to F5 run again (COMMAND 55, 2 | 4/0/0/0/0/0/0 | 1 | ativo |
| phases/core/manifest_config_fix.md | 418 | 2026-10-18 | Manifest resume and configuration changes (branch `fix/manifest-config | 2/0/0/0/0/0/0 | 0 | ativo |
| phases/core/resume_integrity_58.md | 161 | 2026-10-25 | Resume integrity, GWA coverage and E1 of IND (COMMAND 58) | 5/1/0/0/0/0/0 | 0 | ativo |
| phases/core/revalidation_52.md | 93 | 2026-10-18 | Revalidation of the real manifests and closing of OQ-060 (COMMAND 51,  | 4/0/0/0/0/0/0 | 1 | ativo |
| thesis/README.md | 11 | 2026-10-14 | docs/thesis | 0/0/0/0/0/0/0 | 5 | referência só por nome |
| thesis/cap1_introduction.tex | 214 | 2026-11-08 | \chapter{Introduction} | 1/0/0/0/0/0/1 | 0 | ativo |
| thesis/hypotheses/H1_climate_rank_robustness.tex | 333 | 2026-10-14 | \section{Hypothesis H1: Climate Robustness of the Site Ranking} | 2/0/1/0/0/1/0 | 2 | ativo |
| thesis/hypotheses/H2_spatial_aggregation_bias.tex | 369 | 2026-10-13 | \section{Hypothesis H2: Spatial Aggregation Bias in Robust Site Select | 2/0/1/0/0/1/0 | 0 | ativo |
| thesis/hypotheses/H3_robust_versus_nominal.tex | 277 | 2026-10-13 | \section{Hypothesis H3: Robust Versus Nominal Site Selection} | 2/0/1/0/0/1/0 | 0 | ativo |
| thesis/hypotheses/H4_axis_dominance.tex | 317 | 2026-10-13 | \section{Hypothesis H4: Context-Dependent Dominance of Climate and | 2/0/1/0/0/1/0 | 0 | ativo |
| thesis/hypotheses/H5_climate_threat_to_targets.tex | 315 | 2026-10-14 | \section{Hypothesis H5: Climate-Induced Pressure on Economic Potential | 2/1/1/0/0/1/0 | 1 | ativo |
| thesis/methods/group1_technical_potential.tex | 476 | 2026-11-05 | \section{Technical-Potential Parameters (Stage F5)} | 4/0/0/0/0/1/0 | 2 | ativo |
| thesis/methods/group2_core_costs.tex | 236 | 2026-10-27 | \section{Core Cost Parameters (Stage F6)} | 3/0/0/0/0/1/0 | 0 | ativo |
| thesis/methods/group3_connection_degradation.tex | 327 | 2026-11-13 | \section{Grid Connection and Degradation (Stage F6)} | 5/5/0/0/0/1/0 | 0 | ativo |
| thesis/methods/group6_land_eligibility.tex | 222 | 2026-11-08 | \section{Land Eligibility Parameters (Stage F3)} | 3/1/1/0/0/1/0 | 0 | ativo |
| thesis/methods/grupo4.tex | 148 | 2026-11-13 | \section{Literature Review: Thresholds and Reference Points in Robustn | 2/0/0/0/0/0/0 | 0 | ativo |
| thesis/methods/grupo5.tex | 65 | 2026-11-13 | \section{Literature Review: Climate Hazards for Photovoltaic and Wind  | 1/0/0/0/0/0/0 | 1 | ativo |
| thesis/methods/grupo7.tex | 74 | 2026-11-13 | \section{Literature Review: Potentials, Spatial Scale and Robust Decis | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| thesis/methods/synthesis_and_scenario_discovery.tex | 206 | 2026-10-14 | \section{Cross-Country Synthesis of the Hypotheses} | 2/0/0/0/0/1/0 | 1 | ativo |
| thesis/notation.tex | 93 | 2026-10-14 | \section*{Notation} | 0/0/0/0/0/0/0 | 1 | referência só por nome |
| thesis/references_stage_r.bib | 291 | 2026-11-12 | % Stage R references: the entries cited by docs/thesis/methods/*.tex ( | 4/0/0/0/0/0/0 | 2 | ativo |
| thesis/theory/ch2_grid_access_degradation.tex | 135 | 2026-11-02 | \section{Grid Access and External Infrastructure Costs} | 1/0/0/0/0/0/0 | 0 | ativo |
| thesis/theory/ch2_land_eligibility_constraints.tex | 136 | 2026-11-12 | \section{Land Eligibility Constraints} | 2/0/0/0/0/1/0 | 1 | ativo |
| thesis/theory/ch2_renewable_potential_foundations.tex | 448 | 2026-10-27 | \section{Spatially Explicit Renewable-Energy Potential} | 2/0/0/0/0/0/0 | 2 | ativo |

## Duplicados (máx. 10 exemplos)

0 arquivos com algum sinal de duplicação.

| arquivo | sinal |
|---|---|
