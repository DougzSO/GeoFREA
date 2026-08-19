Corresponde à Fase 8 — Sensitivity Analysis do GeoWorld legado.

# Sensitivity Analysis — Architecture Notes

**Fonte legada**: `$GEOWORLD_BASELINE_DIR/src/processors/sensitivity_analyzer.py` (`SensitivityAnalyzer`, 1095 linhas, lidas por completo em 2026-08-19 — bem menor que os "2150 LOC" registrados em `arch-misalignments.md` 2026-08-06, confirmando a extração já concluída para `src/utils/sensitivity_math.py`/`sensitivity_plots.py`). **A matemática pura de SA-1 a SA-6 vive em `src/utils/sensitivity_math.py`, não lida em detalhe nesta passada** — ver §e.3. Cross-referenciado com `docs/memory/04-algorithms.md`, `docs/TASKS.md`/`docs/archive/backlog-full-2026-08.md` (estado 2026-08-19, HEAD `fc7b43d`).

---

## a. Propósito e I/O

**Propósito**: 6 sub-análises de sensibilidade independentes (ativáveis individualmente) sobre os resultados de Suitability/Potential/LCOE/Abatement, visando robustez metodológica para publicação (Saltelli et al. 2008/2010, Malczewski 1999).

**Inputs**: `suitability_results` (Fase 3, ou recarregado do disco se ausente em memória — `_load_suitability_from_disk()`), `criteria_dir` (Fase 2b), `country_params`, `pot_results` (Fase 4, usado só para o threshold "balanced" real via `_balanced_threshold()`), `abat_result` (Fase 7, opcional, usado só para SA-5).

**Outputs por tecnologia**: `results_sa[tech]["sa1".."sa6"]` (estatísticas resumo + `_df` DataFrame completo em memória, removido antes da persistência), CSVs por sub-análise, PNGs (tornado/heatmap SA-1, distribuição SA-2, curva SA-3, histograma SA-4, Sobol SA-5, OAT SA-6, dashboard por tecnologia), relatório de texto único (`{ISO3}_sensitivity_report.txt`, via `build_phase_report()` com `subsections` aninhadas por sub-análise).

---

## b. As 6 sub-análises

| ID | Método | O que varia | Métrica-alvo | Linha (orquestração) |
|---|---|---|---|---|
| SA-1 | OAT (um-de-cada-vez) nos pesos AHP | Perturbação ±10-30% por critério | Correlação de Spearman ρ do ranking de suitability | L631-664 |
| SA-2 | Monte Carlo (Dirichlet) nos pesos AHP | 1000 amostras de vetores de peso | `decisive_fraction`/`boundary_fraction`/`moderate_fraction` — fração de pixels aptos-na-base cujo status apt/não-apt muda ao cruzar o threshold real sob reamostragem (métrica corrigida, ver §d, BLOCKER-016) | L666-710 |
| SA-3 | Varredura de threshold de suitability | Corte de área suitable | Elasticidade da área vs. threshold | L712-757 |
| SA-4 | Monte Carlo triangular | CAPEX/OPEX/CF | Incerteza de LCOE (P50, CI90, std) | L759-797 |
| SA-5 | Sobol (SALib), 1a ordem (S1) e total (ST) | Parâmetros do modelo de abatimento GEE | Índices de sensibilidade global | L861-886 (roda uma vez, cross-tecnologia, **desligado por padrão**, `run_sa5=False`) |
| SA-6 | Elasticidade paramétrica | Densidade de potência, CF | Sensibilidade do cálculo de potencial (GW/TWh base) | L799-843 |

**Threshold real usado por SA-2/SA-3/SA-6**: sempre `_balanced_threshold(tech, pot_results)` — lê o threshold "balanced" persistido pela Fase 4, **não** um valor hardcoded (ver §d, BLOCKER-017).

---

## c. Parâmetros hardcoded

### ⚠️ Achado novo — terceira tabela de fallback CAPEX/OPEX divergente

`_SA4_DEFAULTS` (L123-127, usado só se `CountryParams` não tiver bloco LCOE) **diverge numericamente** de `lcoe_calculator.py::DEFAULT_LCOE_PARAMS` (ver `lcoe_modeling.md` §c.1) — a mesma categoria de bug que já foi corrigida uma vez (a antiga `_irena_defaults` de CF, removida de `lcoe_calculator.py`), mas aqui para parâmetros financeiros, **nunca detectada/registrada em nenhum BLOCKER**:

| Tech | `_SA4_DEFAULTS` (aqui) | `DEFAULT_LCOE_PARAMS` (Fase 5) | Divergência |
|---|---|---|---|
| solar | CAPEX=850, OPEX=15, life=25, dr=6% | CAPEX=760, OPEX=13, life=25, dr=6% | CAPEX +11.8%, OPEX +15.4% |
| wind | CAPEX=1400, OPEX=40, life=25, dr=6% | CAPEX=1360, OPEX=44, life=25, dr=6% | CAPEX +2.9%, OPEX −9.1% |
| biomass | CAPEX=2500, OPEX=100, life=**30**, dr=7% | CAPEX=2720, OPEX=109, life=**20**, dr=7% | CAPEX −8.1%, OPEX −8.3%, **lifetime diverge 30 vs 20 anos** |

Este fallback só é usado quando `CountryParams` não tem LCOE configurado para o país (`_lcoe_params_for_tech()`, L158-224) — baixo risco na prática (todos os países atualmente em `parameters.json` têm bloco LCOE), mas é exatamente o tipo de divergência silenciosa que já causou um bug real uma vez neste codebase.

### Outros hardcoded
| # | Local | Valor | Uso |
|---|---|---|---|
| 1 | `_resolve_tech_params()` fallback (L243-245) | `power_density=30.0 MW/km², land_use_factor=0.20, capacity_factor_max=0.22` | Fallback se nem `settings.yaml` nem `CountryParams` tiverem o valor — **um quarto conjunto de defaults físicos**, distinto de `constants.DEFAULT_TECH_PARAMS` (Fases 4/5) |
| 2 | SA-1 corte "robusto", `rho >= 0.95` (L644) | Limiar de correlação de Spearman | **Campaign-13** em `TASKS.md`, desbloqueado (BLOCKER-017/018 done) mas ainda sem decisão de valor final |
| 3 | SA-4, `n_samples = max(n_mc_samples, 10_000)` (L777) | Piso de 10.000 amostras Monte Carlo, ignora `n_mc_samples` se menor | Não documentado em `TASKS.md` |
| 4 | SA-5, `n_samples=1024` hardcoded (L864) | Tamanho da amostra Sobol | Não usa o parâmetro `n_mc_samples` do `run()` — inconsistente com SA-2/SA-4 |
| 5 | `run_sa5: bool = False` default (L459) | SA-5 desligado por padrão | Único dos 6 desligado por padrão; motivo não documentado no código |

Variações específicas de SA-4 (`capex=±15%, opex=±15%, cf=±10%`, Campaign-12 em `TASKS.md`) **não estão mais neste arquivo** — vivem agora em `src/utils/sensitivity_math.py::sa4_lcoe_uncertainty()`, não lido em detalhe nesta passada (a referência de linha antiga em `TASKS.md`, `sensitivity_analyzer.py:573-575`, está desatualizada pós-refatoração).

---

## d. Cross-check de BLOCKERs já resolvidos

| BLOCKER | Confirmado presente? | Evidência |
|---|---|---|
| **BLOCKER-016** (métrica SA-2 substituída, `decisive_fraction`/`boundary_fraction`/`moderate_fraction`) | **Sim** | L684-695, campos exatos presentes, `stable_fraction` não existe mais no arquivo (busca confirma). |
| **BLOCKER-017** (`_resolve_tech_params()` usa `_balanced_threshold()` real, não fallback hardcoded 0.60) | **Sim** | L254 e L278 (ambos os pontos de retorno de `_resolve_tech_params()`) chamam `_balanced_threshold(tech, pot_results)`; docstring do método (L232-240) documenta o fix explicitamente. |
| **BLOCKER-018** (subsections do relatório renderizadas) | **Sim, estruturalmente** | `_format_report()` (L980-1095) constrói `ReportSection` com `.subsections.append(...)` por sub-análise (L1016 etc.) — consistente com a correção em `build_phase_report()` (não lida em detalhe aqui, mas confirmada em `results_synthesis.md`/backlog). |
| BUG_02 (matching exato de tecnologia por stem, não substring) | **Sim** | `_match_tech_from_stem()`, L280-304, comparação exata `stem == f"{code}_{tech}_weights"`. |
| BUG_05 (`_lcoe_params_for_tech` usa atributos tipados, não `country_params.lcoe` inexistente) | **Sim** | L158-224, acesso via `_LCOE_ATTR` map (`lcoe_solar`/`lcoe_wind`/`lcoe_biomass`). |
| BUG_06 (`_load_suitability_from_disk` usa `find_suitability_tif()` centralizado, não wildcard ambíguo) | **Sim** | L343-345, `allow_owa_fallback=False`, comentário cita explicitamente a classe de bug (mesma do BUG_02). |
| REFACTOR-004 (`run()` dividido em `_run_sa1()`...`_run_sa6()`) | **Confirmado ainda "partial"** (extração das funções SA1-6 feita, mas `run()` continua monolítico) | `run()` (L446-974, ~530 linhas) ainda contém os 6 blocos SA-1...SA-6 inline como `try/except`, não delegados a métodos privados separados — bate exatamente com o status "partial" de `TASKS.md`. |
| REFACTOR-006 residual (Fase 8 sem `output_model` Pydantic) | **Confirmado ainda ABERTO** | `artifact_mgr.save_result(phase_dir, serializable, serializer="pickle")` (L944) persiste um dict puro, sem nenhuma validação Pydantic — nenhum `SensitivityResult` model encontrado no arquivo nem importado. |
| **Dupla persistência** (`sensitivity_analyzer.py:2006,2011` no doc congelado — "unconfirmed", Parte 4a de `archive/00-project-state-and-reorg-plan.md`) | **Verificado nesta auditoria: dupla persistência confirmada, mas SEM perda de dado** | `serializable` (L923-942, persistido manualmente) é estritamente um subconjunto empobrecido (remove `_df` DataFrames e chaves privadas) de `results_sa` (retornado por `run()`, L974, persistido automaticamente pelo orquestrador depois). O segundo write é sempre um superconjunto do primeiro — mesma conclusão que Suitability e Abatement (ver `suitability_analysis.md`/`ghg_abatement.md`). Isso fecha as 3 verificações que `archive/00-project-state-and-reorg-plan.md` §4a havia deixado em aberto: **nenhuma das 3 fases (Suitability/Abatement/Sensitivity) perde dado por dupla persistência** — é redundância de I/O, não um BLOCKER de correção numérica. |

---

## e. Pontos de incerteza / perguntas abertas para Douglas

1. **Terceira tabela de fallback CAPEX/OPEX divergente** (`_SA4_DEFAULTS` vs. `DEFAULT_LCOE_PARAMS`, §c) — achado novo, mesma classe de risco que a antiga `_irena_defaults` (já corrigida uma vez). **Pergunta**: consolidar num único lugar (`DEFAULT_LCOE_PARAMS` reusado por ambos os módulos) no GeoFREA?
2. **`run_sa5` desligado por padrão**, diferente das outras 5 sub-análises — sem explicação documentada. **Pergunta**: SA-5 (Sobol GHG) é mais caro computacionalmente, ou há outra razão (ex. depende da Fase 7, que pode não ter rodado)?
3. **SA-5 usa `n_samples=1024` hardcoded, ignorando `n_mc_samples`** — inconsistente com SA-2/SA-4, que usam (ou têm piso sobre) `n_mc_samples`. **Pergunta**: isso é intencional (Sobol precisa de um tamanho de amostra específico, tipicamente potência de 2, por razões do método) ou deveria ser parametrizado como os outros?
4. **`_resolve_tech_params()` tem um quarto conjunto de defaults físicos** (`power_density=30.0, land_use_factor=0.20, capacity_factor_max=0.22`, L243-245), distinto de `constants.DEFAULT_TECH_PARAMS` usado pelas Fases 4/5. **Pergunta**: vale unificar todas as tabelas de fallback físico/financeiro num único módulo canônico no GeoFREA, eliminando o padrão recorrente de "cada fase tem sua própria cópia"?
5. **Matemática pura de SA-1 a SA-6 não foi lida em detalhe** (`src/utils/sensitivity_math.py`) — as fórmulas exatas (ex. as variações triangulares de SA-4, o método de amostragem Dirichlet de SA-2) precisam de uma leitura dedicada antes de portar a lógica científica ao GeoFREA. Mesma recomendação que para `ahp.py`/`topsis.py`/`owa.py`/`exclusion.py` (ver `suitability_analysis.md` §e.3).
