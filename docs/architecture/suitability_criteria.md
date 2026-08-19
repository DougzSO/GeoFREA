Corresponde à Fase 2b — Criteria do GeoWorld legado.

# Suitability Criteria — Architecture Notes

**Fonte legada**: `$GEOWORLD_BASELINE_DIR/src/processors/criteria_builder.py` (`CriteriaBuilder` + ~14 funções module-level de cômputo por critério, 1087 linhas, lidas por completo em 2026-08-19). Cross-referenciado com `docs/memory/03-pipeline.md`, `docs/TASKS.md` (estado 2026-08-19, HEAD `fc7b43d`).

---

## a. Propósito e I/O

**Propósito**: converter camadas físicas alinhadas (Fase 2a) em ~14 critérios de suitability normalizados [0,1] (fuzzy scores) para agregação AHP-TOPSIS na Fase 3. Cada critério é computado por uma função pura module-level (`compute_*`), depois orquestrado por `CriteriaBuilder.run()`.

**Inputs**: `aligned: AlignedLayers` (rasters da Fase 2a: elevation, slope, solar, wind, land_cover, population, roads, grid, lakes, rivers, seismic, plants), `country_params: ParamsLike` (`CountryParams` ou dict legado, via `_param()` accessor unificado), `land_suit` (tabela de suitability por classe de land cover), `wdpa_path` (shapefile de áreas protegidas), `plants_df`.

**Outputs**: um GeoTIFF float32 por critério em `outputs/{ISO3}/criteria_builder/tif/{criterio}.tif`, um PNG por critério em `.../figures/`, relatório de texto via `write_criteria_summary()` (bespoke, não usa `build_phase_report()` genérico — GAP-004 em `TASKS.md`). CRS/shape herdados do primeiro raster alinhado válido (`ref_path`).

**14 critérios esperados** (L1067-1072): `solar_resource`, `wind_resource`, `terrain_score`, `lc_biomass`, `biomass_resource`, `protected_areas`, `pop_suitability`, `road_suitability`, `lakes_exclusion`, `river_solar`, `river_wind`, `river_biomass`, `seismic_suitability`, `grid_suitability` (+ `slope_degrees`, cartográfico apenas, fora da lista de "esperados" pois não é usado por MCDA).

---

## b. Fórmulas e localização exata

| Critério | Fórmula | Linha |
|---|---|---|
| `solar_resource`/`wind_resource` | `normalize_percentile(data, valid, p_low, p_high)` (percentis configuráveis via `parameters.json`, default 5/95); solar tem multiplicador opcional `solar_pvout_weight` | `compute_solar_resource()` L125-145, `compute_wind_resource()` L148-164 |
| `terrain_score` | `0.6 × slope_score + 0.4 × TRI_score`; `slope_score = clip(1 − slope/threshold, 0, 1)`; `TRI = sqrt(Σ_8vizinhos (E_centro − E_i)²)`; `TRI_score = clip(1 − TRI/TRI_THRESHOLD, 0, 1)` | `compute_terrain_score()` L167-220 (pesos 0.6/0.4 em L216) |
| `road_suitability`/`grid_suitability` | Decaimento linear: `S(d) = clip(1 − d/d_max, 0, 1)`, depois `normalize_percentile(p_low=5, p_high=95)` **hardcoded inline** (não configurável) | `compute_linear_proximity_suitability()` L234-260 |
| `proximity_plants` | `S_renovável = 1 − exp(−d/σ)`; `S_térmica = exp(−d/σ)`; `combinado = max(S_ren, S_term)`; suavização gaussiana `σ_px = max(0.5, PROXIMITY_SMOOTH_SIGMA_PX/res_km)`; depois `normalize_percentile(p_low=5, p_high=95)` **hardcoded inline** | `compute_proximity_plants()` L281-352 |
| `lc_biomass` | Lookup direto: score do pixel = valor de suitability da classe ESA correspondente na tabela `land_suitability["biomass"]` | `compute_land_cover_scores()` L355-385 |
| `biomass_resource` | Lookup de yield por classe de land cover, suavização gaussiana (`sigma=biomass_smooth_sigma`, default 1.0), depois `normalize_percentile` (percentis configuráveis) | `compute_biomass_resource()` L388-432 |
| `protected_areas` | Pixels fora de WDPA = `IUCN_FREE_SCORE` (1.0); dentro, score = `IUCN_SCORES[categoria]`; categorias **`Ia`, `Ib`, `II`** (⚠️ ver §e.1) recebem `0.0` se `as_exclusion=True` | `compute_protected_areas()` L435-515 (categorias estritas: L494) |
| `pop_suitability` | `score = clip(1 − log1p(clip(pop,0,threshold)) / log1p(threshold), 0, 1)`, `threshold` default `pop_density_threshold=300.0` | `compute_population_suitability()` L518-533 |
| `lakes_exclusion` | Binário: `0`=lago, `1`=terra | `compute_lakes_exclusion()` L536-547 |
| `river_biomass` | Decaimento linear: `clip(1 − d/max_dist, 0, 1)`, `max_dist` default `river_max_dist_biomass_km=10.0` | `compute_river_suitability()` L550-577 |
| `river_solar`/`river_wind` | Faixa de segurança ripária: `0` se `d < buffer_km` (default `river_safety_buffer_km=0.5`), senão `1.0` | idem, ramo `else` |
| `seismic_suitability` | `normalize_percentile(p_low=2, p_high=98)` **hardcoded inline**, depois `score = clip(1 − normalized, 0, 1)` (inverte: baixo risco = alta suitability) | `compute_seismic_suitability()` L580-593 |

Unidades: todos os scores finais são adimensionais [0,1] (exceto `slope_degrees`, mantido em graus para cartografia). Distâncias em km. CRS herdado da grade da Fase 2a (`EPSG:4326`).

---

## c. Parâmetros hardcoded

### Configuráveis via `parameters.json` (já migrados)
`normalization_min/max_percentile` (solar/wind/biomass resource), `slope_threshold_deg`, `road_max_dist_km`, `grid_max_dist_km`, `pop_density_threshold`, `biomass_smooth_sigma`, `river_max_dist_biomass_km`, `river_safety_buffer_km`, `protected_as_exclusion`, `solar_pvout_weight`.

### Ainda hardcoded (Campaign-11 em `TASKS.md`, confirmado presente)
| # | Local | Valor | Critério afetado |
|---|---|---|---|
| 1 | `compute_linear_proximity_suitability()`, L258 | `p_low=5.0, p_high=95.0` | roads, grid |
| 2 | `compute_proximity_plants()`, L349 | `p_low=5.0, p_high=95.0` | proximity_plants |
| 3 | `compute_seismic_suitability()`, L589 | `p_low=2.0, p_high=98.0` | seismic |

### Outros hardcoded, sem item de `TASKS.md` dedicado além dos já registrados
| # | Local | Valor | Status na campanha |
|---|---|---|---|
| 4 | `compute_terrain_score()`, pesos `0.6`/`0.4` (L216) | Peso slope vs. TRI | **Campaign-09**, confirmado ainda aberto |
| 5 | `TRI_THRESHOLD` (constants.py, referenciado L206) | usado como denominador do score de rugosidade | **Campaign-10**, acoplado ao item 4 |
| 6 | `threshold=7.0°` default de `compute_terrain_score()` (L176) | Fallback se `parameters.json` não tiver `slope_threshold_deg` | Não registrado em nenhuma campanha — **divergência de fallback**, ver §e.2 |
| 7 | `raw[continent_mask] = 0.3` (L346) | Score neutro de `proximity_plants` quando o país não tem nenhuma usina cadastrada | Achado novo, não documentado |
| 8 | `PROXIMITY_DECAY_SIGMA_KM`, `PROXIMITY_SMOOTH_SIGMA_PX` (constants.py) | Parâmetros de decaimento/suavização de `proximity_plants` | **Campaign-02** (`proximity_plants migrado sem justificativa externa documentada`) |
| 9 | `IUCN_SCORES` mapping (constants.py) | Score por categoria IUCN | **Campaign-05**, bloqueia decisão final de `protected_areas` |

---

## d. Cross-check de BLOCKERs/INVARs já resolvidos

| Item | Confirmado presente? | Evidência |
|---|---|---|
| **BLOCKER-020 / INVAR-004** (`ParamsLike` + `_param()`, ~12 call sites) | **Sim, ainda aberto conforme `TASKS.md`** (registrado, não corrigido — INVAR-004 é item de auditoria, não de fix) | `ParamsLike = Union[CountryParams, Dict[str, Any]]` (L70), `_param()` (L115-117), usado em praticamente toda função `compute_*` que precisa de parâmetros de país (contei 12+ usos de `_param(...)` no arquivo, batendo com a descrição "~12 call sites" de `TASKS.md`). |
| Thread-safety (Figure/Axes OO, nunca `pyplot` stateful) | **Sim** | Módulo inteiro usa `fig, ax = self.styler.create_figure(...)`; nenhuma chamada a `plt.plot`/`plt.imshow` direta encontrada — consistente com `docs/memory/08-conventions.md`. |
| `write_criteria_summary()` não usa `build_phase_report()` genérico | **Confirmado ainda presente** (GAP-004 em `TASKS.md`) | L1051, chama `write_criteria_summary(criteria, ...)` — função separada e bespoke em `reporting.py`, não `build_phase_report()`. |

---

## e. Pontos de incerteza / contradições / perguntas abertas para Douglas

1. **⚠️ CONTRADIÇÃO entre código e documentação — categorias IUCN de exclusão estrita**: `docs/memory/03-pipeline.md` (seção "Hard exclusions applied before MCDA") afirma: *"Protected areas with IUCN score < 0.01 (categories **Ia/Ib**)"*. O código real (`compute_protected_areas()`, L494) exclui **três** categorias, não duas: `["ia", "ib", "ii"]` — ou seja, inclui também a categoria **II** (Parques Nacionais). Não tentei decidir qual versão está certa — **sinalizando a divergência explicitamente, conforme instruído**. **Pergunta para Douglas**: a documentação está desatualizada (código correto inclui categoria II deliberadamente) ou o código tem uma categoria a mais por engano?
2. **Fallback de `slope_threshold_deg` diverge entre módulos**: `compute_terrain_score()` usa fallback `7.0°` (L176) se `parameters.json` não tiver o valor; `data_auditor.py`'s checagem de inatividade de slope (Fase 1) usa fallback `15.0°` (ver `data_quality_audit.md` §c.4) para o mesmo conceito nominal (`slope_threshold_deg`). **Pergunta**: os dois fallbacks deveriam ser o mesmo valor, ou são contextualmente diferentes de propósito (um é científico/exclusão real, outro é só para um alerta de diagnóstico) e por isso legitimamente distintos?
3. **`raw[continent_mask] = 0.3` — score neutro arbitrário para `proximity_plants` sem nenhuma usina** (L346, achado novo): por que `0.3` especificamente (não `0.5`, não `0.0`)? Não há comentário explicando a escolha. **Pergunta**: esse valor tem alguma base, ou é um "valor de bom senso" que deveria ser parametrizado/documentado no GeoFREA?
4. **Percentis hardcoded (Campaign-11) usam valores diferentes por critério sem explicação centralizada**: roads/grid/proximity_plants usam `5/95`, seismic usa `2/98` — mais estreito. **Pergunta**: essa diferença é proposital (seismic precisa de uma faixa mais ampla de outliers preservados?) ou apenas nunca foi padronizado?
5. **`_plot_criterion_map()` tem débito técnico documentado no próprio código** (`KNOWN DEBT (DUP_22_pending)`, L624-639): não foi migrado para `GeoWorldStyler.render_raster_map()` por ter comportamento específico (overlay de `protected_areas`, vmax condicional, stats strip). **Pergunta para o GeoFREA**: vale estender a API do renderer genérico desde o início para cobrir esses casos, evitando essa duplicação de lógica de plotagem por design?
