Não corresponde a uma fase específica — âncora de rastreabilidade entre o GeoWorld legado e o GeoFREA, mantida conforme novos módulos forem definidos.

# Module Mapping — GeoWorld (legado) ↔ GeoFREA

Fonte dos itens BLOCKER/REFACTOR/QI/INVAR/Campaign/GAP/DOC: `$GEOWORLD_BASELINE_DIR/docs/TASKS.md` (rastreador vivo) + `$GEOWORLD_BASELINE_DIR/docs/archive/backlog-full-2026-08.md` (evidência completa) — **não** `docs/refactoring-roadmap.md`, que não existe mais sob esse nome (reorganizado em `TASKS.md`/`archive/`, ver nota no início da Fase 0). Status "confirmado" nas colunas abaixo reflete a leitura de código feita em 2026-08-19 (HEAD `fc7b43d`) para produzir os documentos de arquitetura desta pasta, não apenas o que `TASKS.md` já registrava.

---

## Tabela principal — as 9 fases

| Fase legado (GeoWorld) | Módulo/arquivo legado | Documento GeoFREA | Itens relacionados (`TASKS.md`) | Status resumido |
|---|---|---|---|---|
| Fase 1 — Audit | `src/processors/data_auditor.py` | [`data_quality_audit.md`](data_quality_audit.md) | BLOCKER-015 (open), INVAR-001 (✅ closed), INVAR-002 (✅ closed) | Diagnóstico read-only; BLOCKER-015 é bug no *chamador* (`main.py`), não neste módulo |
| Fase 2a — Grid Alignment | `src/processors/grid_aligner.py` | [`grid_alignment.md`](grid_alignment.md) | INVAR-003 (open) | Confirmado ainda aberto; achado novo: 3 variantes truncadas da mesma fórmula geodésica (não rastreado em `TASKS.md`) |
| Fase 2b — Criteria | `src/processors/criteria_builder.py` | [`suitability_criteria.md`](suitability_criteria.md) | BLOCKER-020/INVAR-004 (open), Campaign-02, Campaign-05, Campaign-09, Campaign-10, Campaign-11 (todos open), GAP-004 (open) | Nenhum destes foi corrigido nesta auditoria (só leitura); ⚠️ contradição código×doc encontrada (categorias IUCN, ver §e.1 do documento) |
| Fase 3 — Suitability (MCDA) | `src/processors/suitability_builder.py` | [`suitability_analysis.md`](suitability_analysis.md) | BLOCKER-006 (✅ closed, não aplicável diretamente — produtor), DUP_21_suitability (✅ closed) | Dupla persistência verificada nesta auditoria: **não lossy** (resolve parte de `archive/00-project-state-and-reorg-plan.md` §4a) |
| Fase 4 — Potential | `src/processors/potential_calculator.py` | [`potential_analysis.md`](potential_analysis.md) | BLOCKER-003 (✅ closed), BLOCKER-006 (✅ closed), REFACTOR-005 (✅ closed), fix "dup_geo_area" (✅ closed) | Módulo mais limpo das 9 fases — nenhum achado novo de peso |
| Fase 5 — LCOE | `src/processors/lcoe_calculator.py` | [`lcoe_modeling.md`](lcoe_modeling.md) | BLOCKER-001 (✅ closed), BLOCKER-002 (✅ closed), BLOCKER-005 (⚠️ partial — metade de validação schema segue não confirmada), BLOCKER-006 (✅ closed), GAP-001/`mask_source` (open) | Achado novo: bounds de CF (`compute_cf_bounds`) hardcoded sem justificativa documentada |
| Fase 6 — Results | `src/processors/results_writer.py` | [`results_synthesis.md`](results_synthesis.md) | **BLOCKER-010 (🔴 open, confirmado via `main.py`)**, BLOCKER-011 (✅ closed), BLOCKER-006 (✅ closed), REFACTOR-007 (✅ closed), GAP-002 (blocked by BLOCKER-010), GAP-004 (open) | BLOCKER-010 é o item de maior prioridade arquitetural de todo o legado (D8/D9 em `DECISIONS.md`) — pré-requisito antes de portar a lógica de agregação |
| Fase 7 — GHG Abatement | `src/processors/ghg_abatement_calculator.py` | [`ghg_abatement.md`](ghg_abatement.md) | BLOCKER-014 (open, confirmado) | Achado novo: World Bank API (não só OWID) também não-determinística, não coberta pelo texto original do BLOCKER-014; dupla persistência verificada **não lossy** (impossível ser lossy por construção — mesmo objeto) |
| Fase 8 — Sensitivity | `src/processors/sensitivity_analyzer.py` | [`sensitivity_analysis.md`](sensitivity_analysis.md) | BLOCKER-016 (✅ closed), BLOCKER-017 (✅ closed), BLOCKER-018 (✅ closed), REFACTOR-004 (⚠️ partial), REFACTOR-006 residual (open), Campaign-12/13 (open, desbloqueados) | Achado novo: terceira tabela de fallback CAPEX/OPEX (`_SA4_DEFAULTS`) diverge numericamente de `DEFAULT_LCOE_PARAMS` (Fase 5) — mesma classe de bug já corrigida uma vez para CF; dupla persistência verificada **não lossy** |

---

## Itens cross-cutting (não específicos de uma única fase)

| Item | Descrição | Fases afetadas | Status |
|---|---|---|---|
| QI-001 (gap) | `src/utils/exclusion.py` e `src/utils/normalization.py` sem nenhum teste | Fase 2b, Fase 3 (usam ambos) | open |
| QI-002 | Teste de integração end-to-end com país sintético | Todas | open |
| QI-003 | Validação de schema/config no startup | Todas (config compartilhada) | open |
| QI-004 | Testes para `params_helpers.py` | Fase 6 principalmente | open |
| REFACTOR-003 | Dividir `data_fetcher.py` por dataset | Fase 0 (fora das 9 fases documentadas) | open |
| REFACTOR-008 | Separar compositing PIL/decorações de `map_styling.py` | Todas as fases com mapas | open |
| REFACTOR-009 | Extrair siting de hubs de `transport_decarbonization_calculator.py` | Fase 9/Transport (dormante, fora das 9 fases) | open |
| REFACTOR-010 | Mover valores hardcoded remanescentes das Fases 3-6 | Fases 3, 4, 5, 6 | open — parcialmente detalhado nos documentos individuais (§c de cada um) |
| DOC-001…008 | Diversos (versão CITATION.cff, `__init__.py` ausente em `visualization/`, tags de changelog não documentadas, LICENSE ausente, etc.) | Não específico de fase | open |
| BLOCKER-012 | Transport (Fase 9) — mesmo bug de dupla persistência do BLOCKER-011 | Fase 9 (dormante, fora das 9 fases) | open |
| BLOCKER-019 | Transport (Fase 9) crasha em `country_params.solar_capacity_factor` | Fase 9 (dormante, fora das 9 fases) | open |
| GAP-003 | Transport escreve GeoDataFrame como CSV puro, perde fidelidade espacial | Fase 9 (dormante) | open |
| GAP-005 | `concentration` (SA-2) tem sensibilidade heterogênea PRT×BRA, decisão pendente | Fase 8 | pending-decision |

**Nota sobre Transport (Fase 9)**: dormante (`skip_transport: true`), fora do escopo das "9 fases" documentadas nesta Fase 0 por instrução explícita do Douglas — listado aqui só para rastreabilidade, caso seja reativado no futuro.

---

## Achados novos desta auditoria (não presentes em nenhum item de `TASKS.md`)

Para referência rápida — todos detalhados na seção "e. Pontos de incerteza" do documento correspondente:

1. Três variantes truncadas da mesma fórmula geodésica Bowring, em `data_auditor.py` e `grid_aligner.py` (×2) — `grid_alignment.md` §b.
2. Contradição código×documentação: categorias IUCN de exclusão estrita — código exclui `Ia/Ib/II`, `docs/memory/03-pipeline.md` documenta só `Ia/Ib` — `suitability_criteria.md` §e.1.
3. `compute_cf_bounds()`'s bounds relativos de CF (0.40×/1.80×, 0.70×/0.95×) sem justificativa documentada — `lcoe_modeling.md` §e.3.
4. `abatement_dir` sempre `None` na chamada real da Fase 6 — Fase 7 nunca alimenta o dashboard/relatório da Fase 6 na prática, apesar do código estar pronto para isso — `results_synthesis.md` §e.1.
5. World Bank API (além de OWID) também não-determinística, mesma classe de risco do BLOCKER-014 — `ghg_abatement.md` §d.
6. `_SA4_DEFAULTS` (Fase 8) diverge numericamente de `DEFAULT_LCOE_PARAMS` (Fase 5) — terceira ocorrência da mesma classe de bug já corrigida uma vez (a antiga `_irena_defaults` de CF) — `sensitivity_analysis.md` §c.
7. Dupla persistência de artefatos nas Fases 3, 7 e 8 **verificada nesta auditoria como não-lossy** (resolve as 3 verificações que `archive/00-project-state-and-reorg-plan.md` §4a havia deixado explicitamente em aberto) — cada documento correspondente, seção "d".
8. Divergência de commit gerador do baseline PRT (`52a9a0f`/`153a1cc`, não `fc7b43d`) — `baseline-manifest.md`.
9. Ausência de `BRA_baseline/` em `outputs_baseline/` — `baseline-manifest.md`.

---

## Como manter esta tabela atualizada

Conforme novos módulos forem definidos para o GeoFREA em conversas futuras (Fase 1+ do projeto), adicionar uma linha nova aqui vinculando: nome do módulo GeoFREA ↔ fase(s) legado(s) de origem ↔ itens de `TASKS.md` herdados ↔ decisão (STRUCTURAL_PRESERVE ou METHODOLOGY_REVISION, ver `DECISIONS.md`). Não editar as linhas da tabela principal acima após a Fase 0 — elas documentam o estado do legado no momento da auditoria; mudanças de rastreabilidade subsequentes vão em novas linhas/seções, não em edições retroativas (mesma convenção "append-only" usada em `DECISIONS.md` do legado).
