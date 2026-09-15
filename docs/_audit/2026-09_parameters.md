# Auditoria de fatos de código — Inventário de parâmetros (Fase 1/2a/2b)

Data: 2026-09-15. Escopo: leitura somente (`src/`, `config/`, `tests/`), sem alterações de código. Objetivo: base factual para fechar o schema de faixas na próxima troca. Nenhuma faixa ou valor novo é proposto aqui — apenas inventário. Nenhum commit foi feito.

Anexos consultados: `CLAUDE.md`, `config/parameters.json`, `config/settings.yaml`, `docs/_audit/2026-09_F1-F2b.md` (auditoria anterior desta mesma sessão de trabalho).

## Contagens (topo, conforme critério de conclusão)

- **Total de parâmetros em `config/parameters.json`** (folhas com bloco `value`/`source`/`verified`, tabelas contadas como uma folha cada, conforme convenção "whole-table verification block" de `docs/CONVENTIONS.md`): **78**
- **Parâmetros sem fonte declarada** (`"source": null`): **4**
- **Hardcodes numéricos em `src/` com papel de parâmetro científico**: **11**

---

## 1. `config/parameters.json` — parâmetros por país/tecnologia (não-biomassa)

Estrutura: `countries.<ISO3>.technologies.<tech>.<campo>` (26 folhas por país: 8 campos × 3 tecnologias + 2 em `criteria`) e `criteria.<campo>` global (26 folhas, cross-country). Biomassa tratada à parte na Seção 2.

### 1.1 `solar` e `wind` — por país

| Caminho | País | Tecnologia | Valor | Unidade | Fonte declarada | Módulo que lê (grep) | Fase consumidora |
|---|---|---|---|---|---|---|---|
| `countries.PRT.technologies.solar.capex_usd_per_kw` | PRT | solar | 823 | USD/kW | Sim — IRENA 2025, Table 3.1 (proxy Europa) | `core/schemas.py` (validação apenas) | Nenhuma (Fase 5/`lcoe_modeling` não construída) |
| `countries.PRT.technologies.solar.opex_fixed_pct_of_capex` | PRT | solar | 0.0092 | fração de CAPEX/ano | Sim — IRENA 2025, Fig 3.5 | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.solar.opex_variable_usd_per_kwh` | PRT | solar | null | USD/kWh | **Não** (`source: null`, `status: pending_research`) | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.solar.capacity_factor` | PRT | solar | 0.12 | fração | Sim — IRENA 2025 narrativa, Europa 11-14% | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.solar.lifetime_years` | PRT | solar | 25 | anos | Sim — IRENA lifetime table | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.solar.discount_rate` | PRT | solar | 0.042 | fração | Sim — IRENA benchmark tool, Europa | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.solar.discount_rate_increment` | PRT | solar | 0.0 | fração | Sim — IRENA 2024 metodologia | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.solar.slope_threshold_deg` | PRT | solar | 5.0 | graus | Sim — MDPI Ikorodu (Nigéria), estudo de caso único | `data_quality_audit/audit.py:213-219` (via `context.country_params.technologies.<tech>.slope_threshold_deg`) | Fase 1 (`data_quality_audit`, diagnóstico de inatividade de slope apenas — não é o gate de exclusão da Fase 2b) |
| `countries.PRT.technologies.wind.capex_usd_per_kw` | PRT | wind | 976 | USD/kW | Sim — IRENA 2025, figura global | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.wind.opex_fixed_pct_of_capex` | PRT | wind | 0.0348 | fração de CAPEX/ano | Sim — IRENA 2025, Fig 2.9 (leitura aproximada de gráfico) | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.wind.opex_variable_usd_per_kwh` | PRT | wind | null | USD/kWh | **Não** (`source: null`, `status: pending_research`) | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.wind.capacity_factor` | PRT | wind | 0.34 | fração | Sim — IRENA 2025, Table 2.2, Europa | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.wind.lifetime_years` | PRT | wind | 25 | anos | Sim — IRENA lifetime table | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.wind.discount_rate` | PRT | wind | 0.037 | fração | Sim — IRENA benchmark tool, Europa | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.wind.discount_rate_increment` | PRT | wind | 0.0 | fração | Sim — IRENA 2024 metodologia | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.wind.slope_threshold_deg` | PRT | wind | 8.5 | graus | Sim, mas reaproveitado — "sem fonte eólica específica, reusa proxy de biomassa" | `data_quality_audit/audit.py:213-219` | Fase 1 (diagnóstico) |
| `countries.BRA.technologies.solar.capex_usd_per_kw` | BRA | solar | 672 | USD/kW | Sim — IRENA 2025, Table 3.1, específico do Brasil | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.solar.opex_fixed_pct_of_capex` | BRA | solar | 0.0112 | fração de CAPEX/ano | Sim — IRENA 2025, Fig 3.5 (média global ÷ CAPEX local) | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.solar.opex_variable_usd_per_kwh` | BRA | solar | null | USD/kWh | **Não** (`source: null`, `status: pending_research`) | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.solar.capacity_factor` | BRA | solar | 0.17 | fração | Sim — IRENA 2025 narrativa, média global 16-18% | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.solar.lifetime_years` | BRA | solar | 25 | anos | Sim — IRENA lifetime table | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.solar.discount_rate` | BRA | solar | 0.077 | fração | Sim — IRENA benchmark tool, América do Sul | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.solar.discount_rate_increment` | BRA | solar | 0.0 | fração | Sim — IRENA 2024 metodologia | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.solar.slope_threshold_deg` | BRA | solar | 5.0 | graus | Sim — mesmo estudo de caso MDPI usado para PRT | `data_quality_audit/audit.py:213-219` | Fase 1 (diagnóstico) |
| `countries.BRA.technologies.wind.capex_usd_per_kw` | BRA | wind | 976 | USD/kW | Sim — mesma figura global de PRT | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.wind.opex_fixed_pct_of_capex` | BRA | wind | 0.0077 | fração de CAPEX/ano | Sim, mas marcada "PROXY QUALITY: WEAK" — usa O&M global de SOLAR como stand-in ÷ CAPEX de wind | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.wind.opex_variable_usd_per_kwh` | BRA | wind | null | USD/kWh | **Não** (`source: null`, `status: pending_research`) | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.wind.capacity_factor` | BRA | wind | 0.50 | fração | Sim — IRENA 2025, Table 2.2, específico do Brasil | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.wind.lifetime_years` | BRA | wind | 25 | anos | Sim — IRENA lifetime table | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.wind.discount_rate` | BRA | wind | 0.077 | fração | Sim — IRENA benchmark tool, América do Sul | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.wind.discount_rate_increment` | BRA | wind | 0.0 | fração | Sim — IRENA 2024 metodologia | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.wind.slope_threshold_deg` | BRA | wind | 8.5 | graus | Sim, reaproveitado — mesmo proxy de biomassa de PRT | `data_quality_audit/audit.py:213-219` | Fase 1 (diagnóstico) |

**Nota importante sobre "módulo que lê" / "fase consumidora" para o bloco `technologies.<tech>.*` (economia)**: `capex_usd_per_kw`, `opex_fixed_pct_of_capex`, `opex_variable_usd_per_kwh`, `capacity_factor`, `lifetime_years`, `discount_rate`, `discount_rate_increment` **só aparecem em `src/geofrea/core/schemas.py`** (confirmado por grep dedicado em `src/` excluindo `__pycache__`) — ou seja, são validados pelo schema Pydantic mas **nenhum módulo de fase os lê ou consome hoje**. Isso é esperado: são os inputs econômicos de `lcoe_modeling` (Fase 5), que é `documentado_nao_construido` (`docs/PROGRESS.json`). Só `slope_threshold_deg` (por tecnologia) tem um consumidor real, e é um diagnóstico da Fase 1, não um cálculo científico downstream.

### 1.2 `terrain_slope_threshold_deg` — por país

| Caminho | País | Valor | Unidade | Fonte declarada | Módulo que lê | Fase consumidora |
|---|---|---|---|---|---|---|
| `countries.PRT.criteria.terrain_slope_threshold_deg` | PRT | 10.0 | graus | Sim — legado @ fc7b43d, confirmado pixel-exato vs. baseline (automated, 2026-09-10) | `suitability_criteria/criteria_functions.py:281-376` (`compute_terrain_score`, denominador do sub-score de slope) via `suitability_criteria/adapter.py:101` | Fase 2b (`suitability_criteria`) |
| `countries.BRA.criteria.terrain_slope_threshold_deg` | BRA | 12.0 | graus | Sim — legado @ fc7b43d, confirmado pixel-exato (automated, 2026-09-10) | idem | Fase 2b |

### 1.3 Parâmetros globais (`criteria.*`, cross-country) — não-biomassa

| Caminho | Valor | Unidade | Fonte declarada | `verified` | Módulo que lê | Fase consumidora |
|---|---|---|---|---|---|---|
| `criteria.slope_threshold_deg_solar` | 5.0 | graus | Sim — `DECISIONS.md` 2026-09-10 (literatura GIS, busca não sistemática) | false | `core/schemas.py` (campo `CriteriaParams.slope_threshold_deg_solar`) | **Nenhum consumidor em `src/` fora do schema** — grep não encontra uso em `criteria_functions.py`/`phase.py`; corresponde ao gate de exclusão da Fase 3 (`suitability_builder`, não construída), não usado na Fase 2b |
| `criteria.slope_threshold_deg_wind` | 25.0 | graus | Sim — `DECISIONS.md` 2026-09-10 | false | idem | idem (Fase 3, não construída) |
| `criteria.slope_threshold_deg_biomass` | 15.0 | graus | Sim, mas interpolado sem fonte direta — `DECISIONS.md` 2026-09-10 | false | idem | idem (Fase 3, não construída) |
| `criteria.river_safety_buffer_km` | 0.5 | km | Sim — `DECISIONS.md` 2026-09-10 (Código Florestal BR, Lei 12.651/2012 Art.4, limite superior) | false | `suitability_criteria/criteria_functions.py:224-263` (`compute_river_suitability`, tech="solar"/"wind") | Fase 2b (`river_solar`, `river_wind`) |
| `criteria.pop_density_threshold` | 200.0 | pessoas/km² | Sim — `DECISIONS.md` 2026-09-10 (proxy US solar-siting, ~193/km²) | false | `suitability_criteria/criteria_functions.py:457-486` (`compute_population_suitability`) | Fase 2b (`pop_suitability`) |
| `criteria.road_max_dist_km` | 15.0 | km | Sim — `DECISIONS.md` 2026-09-10, confirmado pixel-exato (automated) | true | `suitability_criteria/criteria_functions.py:172-185` (`compute_road_suitability`) | Fase 2b (`road_suitability`) |
| `criteria.river_max_dist_biomass_km` | 30.0 | km | Sim — `DECISIONS.md` 2026-09-10, confirmado pixel-exato (automated) | true | `suitability_criteria/criteria_functions.py:224-263` (tech="biomass") | Fase 2b (`river_biomass`) |
| `criteria.grid_max_dist_km` | 20.0 | km | Sim — legado @ fc7b43d, inherited unchanged | false | `suitability_criteria/criteria_functions.py:188-200` (`compute_grid_suitability`) | Fase 2b (`grid_suitability`) |
| `criteria.normalization_min_percentile` | 5.0 | percentil | Sim — legado @ fc7b43d (M7) | false | `suitability_criteria/criteria_functions.py` (`compute_solar_resource`, `compute_wind_resource`, `compute_biomass_resource`) via `normalization.py::normalize_percentile` | Fase 2b (`solar_resource`, `wind_resource`, `biomass_resource`) |
| `criteria.normalization_max_percentile` | 95.0 | percentil | Sim — legado @ fc7b43d (M7) | false | idem | idem |
| `criteria.seismic_percentile_low` | 2.0 | percentil | Sim — legado @ fc7b43d (M8) | false | `suitability_criteria/criteria_functions.py:489-508` (`compute_seismic_suitability`) | Fase 2b (`seismic_suitability`) |
| `criteria.seismic_percentile_high` | 98.0 | percentil | Sim — legado @ fc7b43d (M8) | false | idem | idem |
| `criteria.linear_proximity_percentile_low` | 5.0 | percentil | Sim — legado @ fc7b43d (M7) | false | `criteria_functions.py:150-169` (`compute_linear_proximity_suitability`) | Fase 2b (`road_suitability`, `grid_suitability`) |
| `criteria.linear_proximity_percentile_high` | 95.0 | percentil | Sim — legado @ fc7b43d (M7) | false | idem | idem |
| `criteria.terrain_slope_weight` | 0.6 | fração (soma=1 com `terrain_tri_weight`) | Sim, mas sem fonte — `DECISIONS.md` 2026-09-10 (M1, "author calibration") | false | `criteria_functions.py:281-376` (`compute_terrain_score`) | Fase 2b (`terrain_score`) |
| `criteria.terrain_tri_weight` | 0.4 | fração | Sim, mas sem fonte — `DECISIONS.md` 2026-09-10 (M1, "author calibration") | false | idem | idem |
| `criteria.tri_threshold_m` | 50.0 | metros | Sim, mas sem fonte — `DECISIONS.md` 2026-09-10 (M2, "author calibration") | false | idem | idem |
| `criteria.proximity_decay_sigma_km` | 10.0 | km | Sim, mas sem fonte — `DECISIONS.md` 2026-09-10 (M5, "author calibration") | false | **Nenhum consumidor encontrado** em `criteria_functions.py`/`phase.py` (grep não retorna uso do campo `proximity_decay_sigma_km` fora de `core/schemas.py`) | Nenhuma — campo validado, não lido pela Fase 2b atual |
| `criteria.proximity_smooth_sigma_px` | 2.0 | pixels | Sim, mas sem fonte — `DECISIONS.md` 2026-09-10 (M6, "author calibration") | false | **Nenhum consumidor encontrado** (mesma situação) | Nenhuma |
| `criteria.proximity_plants_neutral_score` | 0.3 | score [0,1] | Sim, mas sem fonte — `DECISIONS.md` 2026-09-10 (M4, "author calibration") | false | **Nenhum consumidor encontrado** em `criteria_functions.py` (não há critério de proximidade a usinas implementado nos 14 atuais) | Nenhuma — provável input futuro (Fase 3?) |
| `criteria.solar_pvout_weight` | 1.0 | multiplicador | Sim — legado @ fc7b43d, no-op por padrão | false | `criteria_functions.py:105-131` (`compute_solar_resource`) | Fase 2b (`solar_resource`) |
| `criteria.renewable_fuel_labels` | ["solar","wind","biomass","waste"] | lista | Sim, mas sem fonte — `DECISIONS.md` 2026-09-10 (M17) | false | **Nenhum consumidor encontrado** em `suitability_criteria/` (grep não retorna uso do campo fora de `core/schemas.py`) | Nenhuma — provável Fase 6/7 (`results_synthesis`/`ghg_abatement`, não construídas) |
| `criteria.protected_as_exclusion` | true | booleano | Sim — legado @ fc7b43d, inherited unchanged | false | **Nenhum consumidor encontrado** em `criteria_functions.py::compute_protected_areas` (a função usa `strict_categories`/`iucn_strict_categories` diretamente, não este flag — ver Seção 3 abaixo) | Nenhuma — campo validado mas não lido pela implementação atual de `protected_areas` |
| `criteria.iucn_strict_categories` | ["ia","ib","ii"] | lista de códigos | Sim — `DECISIONS.md` 2026-08-19 (decisão do autor, sem citação externa) | true | `suitability_criteria/criteria_functions.py:534-724` (`compute_protected_areas`, parâmetro `strict_categories`) via `phase.py:242` | Fase 2b (`protected_areas`) |
| `criteria.land_suitability` | tabela (11 classes ESA × {solar,wind,biomass,description}) | score [0,1] por classe | Sim — legado @ fc7b43d, inherited verbatim (tabela inteira) | false | `criteria_functions.py:387-409` (`compute_lc_biomass`) via `phase.py:100` | Fase 2b (`lc_biomass`) |

---

## 2. Biomassa — seção própria

### 2.1 `technologies.biomass.*` — por país (economia, não consumida por nenhuma fase construída — mesma nota da Seção 1.1)

| Caminho | País | Valor | Unidade | Fonte declarada | Módulo que lê | Fase consumidora |
|---|---|---|---|---|---|---|
| `countries.PRT.technologies.biomass.capex_usd_per_kw` | PRT | 3606 | USD/kW | Sim — IRENA 2025 | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.biomass.opex_fixed_pct_of_capex` | PRT | 0.04 | fração de CAPEX/ano | Sim — IRENA 2025 (midpoint da faixa 2-6%) | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.biomass.opex_variable_usd_per_kwh` | PRT | 0.004 | USD/kWh | Sim — IRENA 2025 | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.biomass.capacity_factor` | PRT | 0.81 | fração | Sim — IRENA 2025, Fig 8.7, proxy regional Europa | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.biomass.lifetime_years` | PRT | 20 | anos | Sim — IRENA 2025 | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.biomass.discount_rate` | PRT | 0.05 | fração | Sim — IRENA 2024, Table A1 (default OECD) | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.biomass.discount_rate_increment` | PRT | 0.0 | fração | Sim — IRENA 2024 metodologia | `core/schemas.py` | Nenhuma |
| `countries.PRT.technologies.biomass.slope_threshold_deg` | PRT | 8.5 | graus | Sim — literatura agrivoltaica (proxy, ~15% slope) | `data_quality_audit/audit.py:213-219` | Fase 1 (diagnóstico) |
| `countries.BRA.technologies.biomass.capex_usd_per_kw` | BRA | 3606 | USD/kW | Sim — IRENA 2025 (mesma figura de PRT) | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.biomass.opex_fixed_pct_of_capex` | BRA | 0.04 | fração de CAPEX/ano | Sim — IRENA 2025 (mesma figura) | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.biomass.opex_variable_usd_per_kwh` | BRA | 0.004 | USD/kWh | Sim — IRENA 2025 (mesma figura) | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.biomass.capacity_factor` | BRA | 0.63 | fração | Sim — IRENA 2025, Fig 8.7, específico do Brasil | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.biomass.lifetime_years` | BRA | 20 | anos | Sim — IRENA 2025 | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.biomass.discount_rate` | BRA | 0.075 | fração | Sim — IRENA 2024, Table A1 (default rest-of-world); nota no JSON deixa explícito que o "floor override" de países de alto risco **não foi calculado/verificado**, só o valor-padrão | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.biomass.discount_rate_increment` | BRA | 0.0 | fração | Sim — IRENA 2024 metodologia | `core/schemas.py` | Nenhuma |
| `countries.BRA.technologies.biomass.slope_threshold_deg` | BRA | 8.5 | graus | Sim — mesmo proxy agrivoltaico de PRT | `data_quality_audit/audit.py:213-219` | Fase 1 (diagnóstico) |

### 2.2 `criteria.yield_by_land_cover` — por país (tabela, consumida pela Fase 2b)

| Caminho | País | Valor (classe ESA → yield) | Unidade | Fonte declarada | `verified` | Módulo que lê | Fase consumidora |
|---|---|---|---|---|---|---|---|
| `countries.PRT.criteria.yield_by_land_cover` | PRT | `{10:8.0, 20:3.0, 30:5.0, 40:6.0, 90:0.0, 95:0.0}` | adimensional (unidade própria do legado, não documentada) | Sim — legado @ fc7b43d, inherited verbatim (tabela inteira) | false | `suitability_criteria/criteria_functions.py:412-454` (`compute_biomass_resource`) via `adapter.py:100` | Fase 2b (`biomass_resource`) |
| `countries.BRA.criteria.yield_by_land_cover` | BRA | `{10:8.0, 20:4.0, 30:6.0, 40:7.0, 90:0.0, 95:0.0}` | idem | Sim — legado @ fc7b43d, inherited verbatim | false | idem | Fase 2b (`biomass_resource`) |

### 2.3 `criteria.biomass_smooth_sigma` — global

| Caminho | Valor | Unidade | Fonte declarada | `verified` | Módulo que lê | Fase consumidora |
|---|---|---|---|---|---|---|
| `criteria.biomass_smooth_sigma` | 1.0 | sigma do filtro gaussiano (pixels) | Sim, mas sem fonte — `DECISIONS.md` 2026-09-10 (M16, "author calibration") | false | `suitability_criteria/criteria_functions.py:412-454` (`compute_biomass_resource`, `gaussian_filter`) | Fase 2b (`biomass_resource`) |

**Nota**: `land_suitability` (Seção 1.3, tabela global ESA→{solar,wind,biomass}) também alimenta biomassa via a coluna `biomass` de cada classe, consumida por `compute_lc_biomass` (`lc_biomass`, critério #6 da Fase 2b) — listada na Seção 1.3 por ser global/cross-tecnologia, não repetida aqui.

---

## 3. `config/settings.yaml` — inventário

`settings.yaml` não segue o formato `value`/`source`/`verified` de `parameters.json` (por design — `docs/CONVENTIONS.md`: escopo operacional, não científico). Tabela abaixo lista cada folha efetiva.

| Caminho | Valor | Unidade | Fonte declarada | Módulo que lê | Fase consumidora |
|---|---|---|---|---|---|
| `run.countries` | `[]` (vazio = todos os países de `parameters.json`) | lista de ISO3 | N/A (config operacional, não científica) | `main.py:318` (`load_settings`, `core/config_loader.py`) | Todas (controla quais países rodam) |
| `run.phases.data_acquisition` | `false` | booleano | N/A | `main.py:334`/`Orchestrator.phases_enabled` | Fase 1 |
| `run.phases.data_quality_audit` | `false` | booleano | N/A | idem | Fase 1 |
| `run.phases.grid_alignment` | `false` | booleano | N/A | idem | Fase 2a |
| `run.phases.suitability_criteria` | `false` | booleano | N/A | idem | Fase 2b |
| `run.phases.suitability_analysis` | `false` | booleano | N/A | idem (fase não construída — toggle sem efeito hoje) | Fase 3 |
| `run.phases.potential_analysis` | `false` | booleano | N/A | idem (não construída) | Fase 4 |
| `run.phases.lcoe_modeling` | `false` | booleano | N/A | idem (não construída) | Fase 5 |
| `run.phases.results_synthesis` | `false` | booleano | N/A | idem (não construída) | Fase 6 |
| `run.phases.ghg_abatement` | `false` | booleano | N/A | idem (não construída) | Fase 7 |
| `run.phases.sensitivity_analysis` | `false` | booleano | N/A | idem (não construída) | Fase 8 |
| `geospatial.resolutions.suitability` | `0.01` | graus (ou literal `"adaptive"`) | Sim, indireta — comentário no próprio arquivo: "matches legacy's own actual configured value ... generated the frozen PRT/BRA baseline" | `grid_alignment/alignment.py:292-301` via `core/schemas.py::ResolutionsConfig` | Fase 2a (`grid_alignment`) |
| `geospatial.resolutions.adaptive.target_pixels` | `50000` | pixels | Não — comentário: "no documented calibration" | `grid_alignment/alignment.py:300-301` (só se `suitability: "adaptive"`, não é o valor de produção) | Fase 2a (inerte na config atual) |
| `geospatial.resolutions.adaptive.min_deg` | `0.001` | graus | Não (herdado do legado sem calibração documentada) | idem | Fase 2a (inerte) |
| `geospatial.resolutions.adaptive.max_deg` | `0.05` | graus | Não (idem) | idem | Fase 2a (inerte) |

**Observação**: todas as 10 chaves de `run.phases` estão `false` por padrão neste arquivo — nenhuma fase roda automaticamente sem alteração manual desta config (confirmado também na auditoria anterior, `docs/_audit/2026-09_F1-F2b.md` seção 8).

---

## 4. Hardcodes numéricos em `src/` com papel de parâmetro científico

Valores numéricos escritos diretamente no código-fonte (não lidos de `parameters.json`/`settings.yaml`) que influenciam um cálculo ou limiar científico/geoespacial. Constantes puramente de engenharia (buffers de I/O, thresholds de memória, tamanhos de lote) foram excluídas.

| # | Arquivo:linha | Valor | Uso |
|---|---|---|---|
| 1 | `src/geofrea/core/constants.py:35` | `LINEAR_FEATURE_MAX_DIST_KM = 100.0` | Distância máxima (km) codificada nos rasters de distância a roads/grid/rivers antes do clip, em `grid_alignment` (default de `GridAlignmentInputs.max_dist_km`, `grid_alignment/schemas.py:145`). Unificado do legado (que divergia 100.0 vs. 50.0 para rivers), confirmado funcionalmente inerte pois os limiares reais da Fase 2b (`road_max_dist_km`=15, `river_max_dist_biomass_km`=30, `grid_max_dist_km`=20) ficam bem abaixo. |
| 2 | `src/geofrea/core/constants.py:45` | `KM_PER_DEG_LAT = 111.32` | Fator fixo km/grau de latitude, usado **apenas** em `derive_slope_from_dem()` (`grid_alignment/raster_alignment.py:204,239`) para paridade STRUCTURAL_PRESERVE com o cálculo de slope do legado — deliberadamente NÃO usa `core.geodesy.wgs84_km_per_degree()` (a função geodésica real usada em todo o resto do código). |
| 3 | `src/geofrea/core/constants.py:70-74` | `WIND_AHP_MATRIX = [[1.0,3.0,5.0],[1/3,1.0,3.0],[1/5,1/3,1.0]]` | Matriz de comparação pareada de Saaty para ponderar alturas de vento (200m/100m/50m) em `_combine_wind_layers()`/`compute_ahp_weights()` (`grid_alignment/raster_alignment.py:261-341`). Julgamentos pareados (200m 3x sobre 100m, 5x sobre 50m) **sem fonte citada** no repositório (comentário do próprio arquivo, `constants.py:52-58`). Na prática inerte hoje — só uma altura de vento é buscada (ver `docs/_audit/2026-09_F1-F2b.md` seção 4). |
| 4 | `src/geofrea/core/constants.py:83-99` | `AHP_RANDOM_INDEX = {1:0.00, 2:0.00, 3:0.58, ..., 15:1.59}` | Tabela de Random Index de Saaty (1980), usada para calcular a Razão de Consistência (RC=CI/RI) que decide se os pesos AHP calculados são aceitos (`compute_ahp_weights()`, `raster_alignment.py:261-282`). Literatura-padrão segundo comentário do código, mas hardcoded (não em `parameters.json`). |
| 5 | `src/geofrea/grid_alignment/raster_alignment.py:278` | `ri = AHP_RANDOM_INDEX.get(n, 1.12)` | Valor de fallback (1.12, RI para n=5) quando o tamanho da matriz AHP não está na tabela — nunca exercitado hoje (matriz é sempre 3x3, `n=3`, presente na tabela). |
| 6 | `src/geofrea/core/geo_utils.py:260` | `_SIMPLIFY_TOLERANCE_DEG = 0.001` | Tolerância de simplificação de geometria (graus) aplicada ao polígono do país antes do `.intersection()` em `clip_vector_to_country()`, para CRS geográfico. Documentado como causando "0.0005% area distortion on real Brazil data" (`geo_utils.py:259`). |
| 7 | `src/geofrea/core/geo_utils.py:261` | `_SIMPLIFY_TOLERANCE_M = 100.0` | Mesma tolerância de simplificação, em metros, para CRS projetado. |
| 8 | `src/geofrea/data_quality_audit/audit.py:62-68` | `_EXPECTED_RESOLUTIONS_DEG = {"land_cover":0.0001, "solar":0.0083, "wind":0.0083, "elevation":0.005, "slope":0.005}` | Resoluções esperadas (graus) usadas por `diagnose_consistency()` (`audit.py:201`) para emitir alertas de resolução inesperada. O próprio código rotula estes valores como "diagnostic-gate defaults... Not scientific parameters, so not sourced from parameters.json/settings.yaml" (`audit.py:60-61`) — listados aqui porque ainda assim carregam um valor científico de referência (resolução nativa esperada por fonte de dado), mesmo que o autor os trate como não-formais. |
| 9 | `src/geofrea/data_quality_audit/audit.py:69` | `_RESOLUTION_TOLERANCE = 0.5` | Tolerância relativa (50%) usada junto com `_EXPECTED_RESOLUTIONS_DEG` para decidir quando emitir o alerta "UNEXPECTED RESOLUTION" (ver achado não resolvido para `wind`, `docs/_audit/2026-09_F1-F2b.md`). |
| 10 | `src/geofrea/data_quality_audit/audit.py:70` | `_SOLAR_PVOUT_SANITY_RANGE = (1.0, 10.0)  # kWh/m2/day` | Faixa de sanidade para o valor médio de PVOUT solar (`audit.py:124-127`); fora da faixa, emite alerta de possível erro de unidade. Mesma faixa citada na auditoria de fetch de solar (achado histórico do padrão de URL do Global Solar Atlas). |
| 11 | `src/geofrea/suitability_criteria/criteria_functions.py:95` | `_IUCN_FREE_SCORE = 1.0` | Único valor emitido pela máscara binária de `protected_areas` para pixels não-restritos ("legacy IUCN_FREE_SCORE"). Substitui a tabela graduada de scores IUCN do legado (descartada por decisão registrada em `DECISIONS.md` 2026-09-10/2026-09-11). |

**Excluídos deliberadamente da lista acima** (avaliados e descartados por não terem papel científico/calibrável):
- `suitability_criteria/cartography.py:304,311` (`label_headroom=0.85`, `width_in=0.55`) — parâmetros de layout de figura, não de ciência.
- `grid_alignment/vector_alignment.py:82` (`buffer_deg: float = 0.01`) — margem de bbox para pré-filtro de leitura de arquivo, engenharia de I/O, não um limiar científico.
- `grid_alignment/schemas.py:141,143-145` / `core/schemas.py:528-529,554` (`resolution_deg=0.01`, `adaptive_min_deg=0.001`, `adaptive_max_deg=0.05`, `max_dist_km=LINEAR_FEATURE_MAX_DIST_KM`) — são *defaults* de schema Python que espelham `settings.yaml`/`core/constants.py`, não uma segunda fonte independente de verdade; sempre substituídos pelo valor de `settings.yaml`/`constants.py` quando o config real é carregado. Risco de duplicação registrado aqui, mas não contado como hardcode adicional.

---

**Critério de conclusão**: contagens no topo ✓ (78 parâmetros totais, 4 sem fonte, 11 hardcodes); único arquivo criado é este (`docs/_audit/2026-09_parameters.md`); nenhum arquivo de `src/`, `config/` ou `tests/` foi modificado.
