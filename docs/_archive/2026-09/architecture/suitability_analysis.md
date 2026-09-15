Corresponde à Fase 3 — Suitability do GeoWorld legado.

# Suitability Analysis (MCDA) — Architecture Notes

**Fonte legada**: `$GEOWORLD_BASELINE_DIR/src/processors/suitability_builder.py` (`SuitabilityBuilder` + funções module-level, 1010 linhas, lidas por completo em 2026-08-19). A matemática central (AHP/TOPSIS/OWA/exclusão) vive em `src/utils/{ahp,topsis,owa,exclusion}.py` — **não lidos em detalhe nesta passada** (só a orquestração que os chama); ver §e.4. Cross-referenciado com `docs/memory/03-pipeline.md`, `docs/memory/04-algorithms.md`, `docs/TASKS.md`/`docs/archive/00-project-state-and-reorg-plan.md` (estado 2026-08-19, HEAD `fc7b43d`).

---

## a. Propósito e I/O

**Propósito**: Análise Multi-Critério de Decisão (MCDA) espacial — combina os ~14 critérios normalizados da Fase 2b em um único score de suitability [0,1] por tecnologia, via AHP (pesos) + TOPSIS (agregação primária) + OWA (agregação secundária, 3 cenários).

**Inputs**: todos os GeoTIFFs de critério da Fase 2b (`load_all_criteria()`), rasters auxiliares de land cover e slope alinhados (para exclusões), `country_params` (pesos OWA, thresholds de exclusão, `forest_as_exclusion`).

**Outputs por tecnologia**:
- 1 GeoTIFF TOPSIS: `outputs/{ISO3}/suitability/tif/{ISO3}_{tech}_suitability.tif` — **superfície primária**, usada por todas as fases seguintes.
- 3 GeoTIFFs OWA (`_owa_optimistic`/`_owa_balanced`/`_owa_conservative`) — secundários, não usados por padrão pela Fase 4 (ver `03-pipeline.md`, decisão D4).
- JSON de pesos AHP por tecnologia (`{ISO3}_{tech}_weights.json`: λmax, CI, CR, pesos por critério).
- `scenario_thresholds` — offsets de cenário (de `settings.yaml`), **encaminhados para a Fase 4, não aplicados aqui** (Fase 3 produz superfícies contínuas, nunca corta por threshold).
- Estatísticas por tecnologia (n_total, n_excluded, n_valid, mean/std/p10/p50/p90, `pct_high`, CR).

**CRS/shape**: herdados da grade de referência (`load_reference_meta()`), consistente com Fases 2a/2b.

---

## b. Fórmulas e localização exata

| # | Fórmula/processo | Linha |
|---|---|---|
| 1 | **Slope máximo por tecnologia**: `slope_max_deg = country.slope_threshold_deg + slope_offset_{tech}_deg` (offset de `parameters.json`, fallback `_SLOPE_OFFSET_DEG={solar:5,wind:10,biomass:20}`) | `get_technology_configs()`, L120-178 |
| 2 | **Exclusões rígidas de land cover**: classes ESA `{50,70,80,90,95}` sempre excluídas (built-up/snow-ice/water/wetland/mangroves); classe `10` (floresta) excluída também se `forest_as_exclusion=True` (default) | `get_technology_configs()`, L143-159 |
| 3 | **Thresholds de exclusão global** (não por país): `lakes_exclusion=0.5` (matematicamente inerte — qualquer valor em (0,1) é equivalente, critério binário), `protected_areas_threshold` default `0.99`, `proximity_plants_threshold` default `0.01` (ambos de `parameters.json`'s `exclusion_thresholds`, Bloco 1) | `get_technology_configs()`, L181-192 |
| 4 | **Pesos AHP** (método do autovetor/geométrico, Saaty 1980) — cálculo real vive em `src/utils/ahp.py::compute_ahp_weights()`, **não lido em detalhe nesta passada** | Chamado em `_process_technology_topology()`, L611-613 |
| 5 | **TOPSIS** (distância euclidiana a soluções ideal/anti-ideal ponderadas) — cálculo real em `src/utils/topsis.py::topsis_spatial()`, **não lido em detalhe** | L674 |
| 6 | **OWA** (Ordered Weighted Averaging, pesos aplicados à sequência ordenada de valores) — cálculo real em `src/utils/owa.py::owa_spatial()`/`prepare_owa_weights()`, **não lido em detalhe** | L688-703 |
| 7 | **Exclusões rígidas aplicadas** (slope + land cover + protected areas + proximity + lakes, combinadas) — cálculo real em `src/utils/exclusion.py::apply_hard_exclusions()`, **não lido em detalhe** | L647-663 |

Unidades: scores finais adimensionais [0,1]; pixels excluídos recebem `TOPSIS_EXCLUSION_SCORE` (sentinela, valor exato definido em `topsis.py`, não lido).

**Nota de escopo**: esta auditoria leu por completo a *orquestração* da Fase 3 (`suitability_builder.py`), mas não os 4 módulos de matemática pura que ela chama (`ahp.py`, `topsis.py`, `owa.py`, `exclusion.py`, todos em `src/utils/`). As fórmulas exatas de AHP/TOPSIS/OWA/exclusão precisam de uma leitura dedicada desses arquivos antes de portar a lógica científica ao GeoFREA — ver §e.4.

---

## c. Parâmetros hardcoded

### Já migrados para `parameters.json` (Bloco 1, confirmado)
`_SLOPE_OFFSET_DEG` (fallback apenas — valor real vem de `CountryParams.slope_offset_{tech}_deg`), `protected_areas_threshold`, `proximity_plants_threshold` (`exclusion_thresholds`, global).

### Ainda hardcoded
| # | Local | Valor | Status |
|---|---|---|---|
| 1 | `lakes_exclusion=0.5` (L189) | Threshold de exclusão de lagos | **Intencionalmente não migrado** — comentário no código (L182-188) explica que é matematicamente inerte (critério já binário {0,1}), confirmado empiricamente para 0.3/0.5/0.7 |
| 2 | Cores de colormap por tecnologia (L800-804) | `solar=YlOrRd, wind=Blues, biomass=YlGn` | Cosmético |
| 3 | `exclude_color=(170,170,170,191)` (L818) | Cor cinza do overlay de exclusão no mapa | Cosmético |

Nenhum novo achado de parâmetro hardcoded além do já registrado em `TASKS.md`/`memory/07-configuration.md` — este módulo é majoritariamente orquestração, a maior parte dos parâmetros científicos vive em `parameters.json` ou nos módulos `src/utils/{ahp,topsis,owa,exclusion}.py` não lidos em detalhe.

---

## d. Cross-check de BLOCKERs já resolvidos

| Item | Confirmado presente? | Evidência |
|---|---|---|
| BLOCKER-006 (não aplicável diretamente — Fase 3 é a *produtora* dos TIFs que `find_suitability_tif()` localiza, não consumidora) | N/A | — |
| Migração Bloco 1 (`common_exclusions`/`_SLOPE_OFFSET_DEG` → `parameters.json`) | **Sim** | L162-192, comentários explícitos citando "Bloco 1 (docs/BACKLOG.md)"; leitura de `CountryParams.slope_offset_{tech}_deg` com fallback só para os literais. |
| REFACTOR (DUP_21_suitability — relatório de texto centralizado) | **Sim** | `_format_report()` (L905-1009), comentário no código confirma a migração de ~100 linhas de formatação manual para `build_phase_report()`/`ReportSection`. |
| **Dupla persistência de artefatos** (Suitability, `suitability_builder.py:529,537` no doc congelado — "unconfirmed whether data loss occurs", Parte 4a de `archive/00-project-state-and-reorg-plan.md`) | **Verificado nesta auditoria: dupla persistência CONFIRMADA ainda presente, mas SEM perda de dados** — ver detalhe abaixo | `run()` ainda chama `artifact_mgr.save_result()`/`save_manifest()` manualmente (L513-568) **além** da persistência automática do orquestrador. Comparando os dois dicts persistidos: `serializable_results["techs"][tech]` usa exatamente as mesmas chaves que `results["techs"][tech]` já contém (`_SERIALISABLE_KEYS`, L516-534, batem 1:1 com os campos do dict `stats` retornado por `_process_technology_topology()`). A única diferença é que `serializable_results` (persistido manualmente, primeiro) **não inclui `"timings"`**, enquanto `results` (persistido depois, automaticamente pelo orquestrador) **inclui**. Como a escrita automática do orquestrador ocorre por último e sobrescreve a manual, o resultado final em `result.pkl` é um superconjunto — **nenhum dado é perdido**, ao contrário do que ocorria em `results_writer.py` antes do BLOCKER-011. Isso resolve a verificação recomendada em `archive/00-project-state-and-reorg-plan.md` §4a para o caso da Suitability: pode ser rebaixado para limpeza de I/O redundante (mesma categoria do REFACTOR-006 residual), não é um BLOCKER de perda de dado. |

---

## e. Pontos de incerteza / perguntas abertas para Douglas

1. **AHP sem correção automática de inconsistência**, ao contrário do padrão usado na Fase 2a: em `grid_aligner.py::_combine_wind_layers()` (ver `grid_alignment.md` §b.2), se `RC > 0.10` o código automaticamente cai para pesos uniformes. Em `suitability_builder.py`, o CR é calculado e reportado (`stats["cr_ok"] = cr <= AHP_CR_THRESHOLD`), mas **nenhuma correção automática ocorre** se a matriz for inconsistente — os pesos (possivelmente de uma comparação pareada inconsistente) são usados mesmo assim, só sinalizado como `[WARNING] INCONSISTENT` no relatório de texto. **Pergunta para Douglas**: essa assimetria entre as duas fases (uma corrige automaticamente, outra só alerta) é intencional? No GeoFREA, o comportamento deveria ser padronizado?
2. **Dupla persistência de artefatos ainda existe em 4 das 5 fases originalmente flagged** (Suitability confirmada não-lossy nesta auditoria; Abatement e Sensitivity ainda não verificadas — ver `ghg_abatement.md`/`sensitivity_analysis.md` quando produzidos). **Pergunta**: vale a pena, mesmo sem risco de perda de dado, eliminar a redundância de I/O no GeoFREA desde o design inicial (só uma camada de persistência por fase)?
3. **Módulos de matemática pura (`ahp.py`, `topsis.py`, `owa.py`, `exclusion.py`) não foram lidos em detalhe nesta auditoria** — as fórmulas documentadas em §b para AHP/TOPSIS/OWA/exclusão são descrições de alto nível (do docstring do módulo e de `memory/04-algorithms.md`), não confirmadas linha a linha. **Ação recomendada antes de portar a lógica científica ao GeoFREA**: uma leitura dedicada desses 4 arquivos, produzindo (ou estendendo) um documento de arquitetura específico para a matemática MCDA compartilhada (usada também pela Fase 8/Sensitivity).
4. **Assimetria entre TOPSIS (sempre calculado) e OWA (sempre calculado mas raramente usado)**: as 3 superfícies OWA são computadas e persistidas em todo run, mas — conforme D4 em `DECISIONS.md` — nunca efetivamente consumidas por nenhuma fase downstream hoje (`use_owa=True` nunca é passado). **Pergunta**: no GeoFREA, vale manter esse custo computacional/de armazenamento "por precaução", ou o cálculo de OWA deveria ser opcional/lazy até que uma decisão real sobre seu uso seja tomada?
