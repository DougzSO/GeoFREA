Corresponde à Fase 6 — Results do GeoWorld legado.

# Results Synthesis — Architecture Notes

**Fonte legada**: `$GEOWORLD_BASELINE_DIR/src/processors/results_writer.py` (`ResultsWriter`, 1072 linhas, lidas por completo em 2026-08-19) + `$GEOWORLD_BASELINE_DIR/main.py` (linhas 802-826, orquestração da Fase 6, lidas para resolver BLOCKER-010 — ver §d). Cross-referenciado com `docs/analysis/analysis-results_writer.md` (congelado 2026-08-11/18, então 1108 linhas) e `docs/TASKS.md`/`docs/DECISIONS.md` (estado 2026-08-19, HEAD `fc7b43d`).

**Nota importante**: este módulo mudou substancialmente desde o congelamento da análise (1108→1072 linhas, mas com reescrita interna significativa) — várias das funções que a análise descrevia como "candidatas a BLOCKER" (recomputação de área/estatísticas LCOE) **já não existem mais neste formato**; ver §d para o que foi de fato corrigido vs. o que persiste.

---

## a. Propósito e I/O

**Propósito**: sintetizar os resultados das Fases 3-5 (e opcionalmente 7) em mapas de "dominância tecnológica" (qual tecnologia vence em cada pixel, por suitability e por LCOE), um dashboard executivo e um relatório de texto integrado. Não é fonte primária de nenhum dado científico — deveria apenas agregar (D8 em `DECISIONS.md`).

**Inputs** (`run()`, `results_writer.py:254-264`):
- `suitability_dir` → GeoTIFFs TOPSIS/OWA da Fase 3, via `find_suitability_tif(..., _DEFAULT_OWA_SCENARIO="balanced")` (com fallback OWA permitido, diferente da Fase 4).
- `potential_dir: Any` — **na prática sempre um `Path`** (`main.py:820`, `country_out / "potential"`), nunca o objeto `PotentialResult` vivo — ver §d, BLOCKER-010.
- `lcoe_dir: Any` — **idem, sempre um `Path`** (`main.py:810,821`, comentário `BUG_07 (fix)` explícito no próprio código legado admitindo essa decisão).
- `abatement_dir: Optional[Any] = None` — **sempre `None`** na chamada real (`main.py:823`); `_normalize_abatement(None, ...)` retorna `{"available": False}` (L232) — ou seja, **a Fase 7 nunca alimenta o dashboard/relatório da Fase 6 na prática**, apesar do parâmetro existir (achado novo, não documentado em nenhum BLOCKER/GAP existente — ver §e.1).
- `mainland_gdf`, `context_gdf`, admin boundaries.

**Outputs** (`results`, dict retornado por `run()`, L334-422):
- `country`, `timestamp`, `timings`, `exported_tifs`, `dominance_suitability_counts`, `dominance_lcoe_counts` (por tecnologia, contagem de pixels), `elapsed_total`. **Este é o dict completo persistido em `result.pkl`** — não há mais persistência manual via `ArtifactManager` neste módulo (ver §d, BLOCKER-011).
- 2 GeoTIFFs de dominância (`{ISO3}_dominance_suitability.tif`, `{ISO3}_dominance_lcoe.tif`, uint8, `0=None,1=Solar,2=Wind,3=Biomass`).
- 3 PNGs (`dominance_suitability.png`, `dominance_lcoe.png`, `executive_dashboard.png`).
- Relatório de texto (`outputs/{ISO3}/results/reports/{ISO3}_results_{timestamp}.txt`) via `build_phase_report()`.

---

## b. Fórmulas e localização exata

### Dominância por suitability (`_build_suitability_dominance`, L594-619)
| # | Fórmula | Linha |
|---|---|---|
| 1 | `dom_idx = argmax(stack, axis=0)` sobre as 3 tecnologias (score TOPSIS/OWA) | L607 |
| 2 | `no_tech = max_score < min_score` (min_score=0.30) | L611 |
| 3 | `competition = (max_score − second_score) < competition_delta` (0.10) `& ~no_tech` | L618 |

### Dominância por LCOE (`_build_lcoe_dominance`, L621-655)
| # | Fórmula | Linha |
|---|---|---|
| 4 | `dom_idx = argmin(stack, axis=0)` sobre LCOE das 3 tecnologias (menor custo vence) | L635 |
| 5 | `competition = (second_lcoe − min_lcoe) < competition_delta_usd` (10.0 USD/MWh) `& ~no_tech` | L648-653 |

### Overlay RGBA (`_build_rgba`, L661-710)
| # | Fórmula | Linha |
|---|---|---|
| 6 | `lo,hi = percentile(scores, [5,95])`; alpha por modo — suitability: `clip(score×0.85+0.15, 0.45, 0.92)`; LCOE: `clip(1 − (score−lo)/(hi−lo)×0.55, 0.45, 0.92)` | L675-703 |

Unidades: dominância é categórica (índice de tecnologia); scores de suitability em [0,1] (TOPSIS/OWA adimensional); LCOE em USD/MWh.

---

## c. Parâmetros hardcoded

| # | Local | Valor | Status |
|---|---|---|---|
| 1 | `_build_suitability_dominance`, `competition_delta` (L598) | `0.10` | Ainda hardcoded (default de argumento) — candidato `settings.yaml` per `code-duplication.md` #8 |
| 2 | idem, `min_score` (L599) | `0.30` | Ainda hardcoded — candidato `settings.yaml` per `code-duplication.md` #9 |
| 3 | `_build_lcoe_dominance`, `competition_delta_usd` (L625) | `10.0` USD/MWh | Ainda hardcoded — candidato `settings.yaml` per `code-duplication.md` #10 |
| 4 | Legenda de texto, `"Competition Zone (ΔTOPSIS < 0.10)"` (L776) / `"(ΔLCOE < 10 $/MWh)"` (L778) | strings duplicando os valores de #1/#3 | **Risco de duplicação confirmado ainda presente**: se `competition_delta`/`competition_delta_usd` mudarem, essas strings não acompanham automaticamente (per `code-duplication.md` #11) |
| 5 | `Q1_RGB` dict (L679-683) | cores RGB por tecnologia para o overlay | Cosmético, não candidato a migração científica |

Nenhum parâmetro científico (CF/LUF/densidade/LCOE) é computado ou hardcoded neste módulo — ele só lê valores já persistidos por Fases 4/5 (quando não caindo no caminho de reconstrução, ver §d).

---

## d. Cross-check de BLOCKERs já resolvidos

| BLOCKER | Confirmado presente? | Evidência |
|---|---|---|
| **BLOCKER-011** (double persistence descartando `dominance_*_counts`) | **Sim, corrigido** | Módulo **não tem mais nenhuma chamada a `ArtifactManager`** — confirmado por leitura completa do arquivo. `dominance_suitability_counts`/`dominance_lcoe_counts` são escritos diretamente em `results` (L391-398, comentário cita BLOCKER-011 explicitamente) — o dict retornado por `run()` é a única fonte de persistência, feita pelo `PipelineOrchestrator`. |
| BLOCKER-006 (TOPSIS/OWA centralizado) | **Sim** | L436-438, `find_suitability_tif(suitability_dir, tech, country_code, _DEFAULT_OWA_SCENARIO)`. |
| BLOCKER-003 (área lida de Phase 4, não recomputada) | **Sim** | L982, `get_scenario_data(potential_results, tech, "balanced")`, depois L993 `area = sc.get("area_km2", 0.0)` com comentário "agora bate com Fase 4". `_compute_integrated_area` **não existe mais** no arquivo (busca confirma). |
| Recomputação de estatísticas LCOE (`_enrich_lcoe_stats`, antigo) | **Removida** | `_format_report` lê `lcoe_results...stats.get("mean")` diretamente (L995) — `_enrich_lcoe_stats` não existe mais no arquivo. |
| Aproximação de curva de oferta (`_recover_supply_curve_from_tif`, antigo, proxy "1 MW/pixel") | **Removida** | Substituída por `_recover_supply_curve()` (L238-248), que chama `recover_supply_curve_from_disk()` — lê o Parquet real persistido pela Fase 5 (BLOCKER-001). Função antiga não existe mais no arquivo. |
| REFACTOR-007 (dashboard extraído para `DashboardPanels`) | **Sim** | L119, `self.panels = DashboardPanels(self.styler)`; `run()` chama `self.panels.draw_executive_dashboard(...)` (L366) em vez de método interno. `_draw_dominance_on_ax` permanece neste módulo deliberadamente (precisa de `self._admin_gdf` e renderização raster/GDF específica). |
| **BLOCKER-010** (padrão "sempre reconstrói do disco, nunca usa objeto vivo") | **Confirmado AINDA ABERTO** — ver detalhe abaixo | — |

### Detalhe BLOCKER-010 (verificado contra `main.py`, não apenas `results_writer.py`)

`_normalize_potential`/`_normalize_lcoe` (L162-211) mantêm o branch dual: `if isinstance(data, dict) and "techs" in data: return data` (usaria o objeto vivo) senão reconstrói via `recover_potential_from_disk()`/`recover_lcoe_from_disk()`. Verifiquei diretamente em `main.py:802-826` (chamada real à Fase 6): `potential_dir` recebe `country_out / "potential"` (L820, sempre um `Path`) e `lcoe_dir` recebe `lcoe_dir_for_results = country_out / "lcoe"` (L810, também sempre um `Path` — comentário do próprio código, "BUG_07 (fix)", admite que essa foi a correção aplicada: resolver sempre para o diretório, nunca passar o objeto `LCOEResult`/`PotentialResult` vivo). **Confirma exatamente o que `TASKS.md`/`DECISIONS.md` (D8/D9) descrevem**: o branch "usa objeto vivo" é código morto em produção hoje; Phase 6 sempre reconstrói do disco. BLOCKER-010 continua listado como 🔴 alta prioridade em `TASKS.md`, sem implementação.

**Achado adicional não documentado em nenhum BLOCKER/GAP existente**: `abatement_dir` também é sempre `None` na chamada real (`main.py:823`) — ou seja, a Fase 7 (GHG Abatement) nunca é lida pela Fase 6 na prática, mesmo existindo `_normalize_abatement()` pronto para isso. Ver §e.1.

---

## e. Pontos de incerteza / perguntas abertas para Douglas

1. **`abatement_dir` sempre `None` na chamada real** (achado novo desta auditoria, sem BLOCKER/GAP correspondente em `TASKS.md`): `_normalize_abatement()` (L213-232) está pronto para aceitar dados da Fase 7, mas `main.py:823` nunca passa nada além de `None`. O dashboard executivo (`draw_executive_dashboard`, chamado com `abatement_results` sempre `{"available": False}`) nunca mostra dados de abatimento de GEE. **Pergunta**: isso é intencional (a Fase 6 nunca deveria mostrar abatimento) ou uma integração pendente/esquecida?
2. **BLOCKER-010 é pré-requisito arquitetural documentado (D8/D9)** mas segue sem implementação — no GeoFREA, isso deveria ser resolvido *antes* de portar a lógica de agregação da Fase 6, para não reproduzir o mesmo padrão frágil desde o início? A decisão D8 ("Fase 6 = agregador, nunca recomputa") parece uma boa base de design para o GeoFREA — mas exige que o pipeline novo sempre tenha acesso ao objeto vivo da fase anterior (não recriar via disco) por construção.
3. **Strings de legenda duplicando os limiares de competição** (`competition_delta`/`competition_delta_usd`, item c.4): risco de drift silencioso ainda presente — no GeoFREA, vale a pena construir essas strings via f-string referenciando a mesma constante, em vez de literal duplicado?
4. **`_build_integrated_summary_section`** (L1044-1072, módulo-level) continua sendo uma tabela ASCII de largura fixa feita à mão, não usando a maquinaria genérica de `reporting.py`. Não é um bug, só uma inconsistência estrutural conhecida (mesma observação de `arch-misalignments.md`). **Pergunta**: no GeoFREA, todo relatório de texto deveria usar 100% do mesmo builder genérico, sem exceções "especiais" como esta?
