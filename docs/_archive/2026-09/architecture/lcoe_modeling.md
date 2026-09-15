Corresponde à Fase 5 — LCOE do GeoWorld legado.

# LCOE Modeling — Architecture Notes

**Fonte legada**: `$GEOWORLD_BASELINE_DIR/src/processors/lcoe_calculator.py` (`LCOECalculator`, 1495 linhas, lidas por completo em 2026-08-19) + `$GEOWORLD_BASELINE_DIR/src/utils/economics.py` (359 linhas, lidas por completo — math compartilhada por Fases 4/5/8). Cross-referenciado com `docs/analysis/analysis-lcoe_calculator.md` (congelado 2026-08-11, HEAD `6d59120`) e `docs/TASKS.md`/`docs/archive/backlog-full-2026-08.md` (estado 2026-08-19, HEAD `fc7b43d`).

---

## a. Propósito e I/O

**Propósito**: calcular o Custo Nivelado de Energia (LCOE, USD/MWh) espacialmente distribuído por tecnologia, usando o raster de suitability da Fase 3 (para definir a população de pixels aptos) e um raster de recurso da Fase 2b (para modular o fator de capacidade localmente); produz também a curva de oferta (merit order) por tecnologia.

**Inputs**:
- GeoTIFF de suitability (Fase 3), localizado via `find_suitability_tif(suitability_dir, tech, country_code)` — **aqui, ao contrário da Fase 4, sem `allow_owa_fallback=False`**, ou seja, pode cair para OWA se TOPSIS não existir (L591).
- Máscara de pixels aptos da Fase 4 (`outputs/{ISO3}/potential/tifs/{ISO3}_{tech}_suitable_balanced.tif`), localizada via `_find_potential_suitable_tif()` (L262-299) e carregada em `_load_potential_suitable_mask()` (L301-371) — **preferida** sobre o corte por threshold quando disponível (fix "Grupo C").
- Raster de recurso normalizado da Fase 2b (`{stem}.tif`, ex. `wind_resource.tif`), localizado via `_find_resource_tif()` (L377-417).
- `country_params: CountryParams | None` → `self.tech_params` (financeiro: CAPEX/OPEX/lifetime/discount_rate, via `_load_tech_params()`) e `self.pot_params` (físico: CF/LUF/densidade/thresholds, via `_load_pot_params()` → `build_tech_params()`, **exclusivamente de `parameters.json`**, `settings.yaml` nunca consultado — módulo docstring L10).
- CRS/shape validados contra o raster de suitability de referência (`validate_raster_crs`/`validate_raster_shape`, L616-618).

**Outputs** (por tecnologia, `stats` dict, L1072-1105):
- `base_lcoe`, `mean`, `p10`, `p25`, `median`, `p75`, `p90` (USD/MWh), `n_pixels`, `crf`, `base_cf`, `source` (`"resource_tif"` | `"suitability_proxy"` | `"suitability_proxy (resource constant)"`).
- GeoTIFF de LCOE por pixel: `outputs/{ISO3}/lcoe/tif/{ISO3}_{tech}_lcoe_usd_mwh.tif` (float32, nodata=`NODATA_FLOAT`).
- CSV zonal (`lcoe_mean` por admin region, sem percentis): `outputs/{ISO3}/lcoe/data/{ISO3}_{tech}_lcoe_zonal.csv`.
- **Curva de oferta completa persistida em Parquet** (BLOCKER-001, confirmado presente): `outputs/{ISO3}/lcoe/data/{ISO3}_{tech}_supply_curve.parquet` (L1148-1152) — colunas `lcoe_usd_mwh`, `capacity_mw`, `cum_capacity_gw`.
- Retorno serializado ao orquestrador (L731-772): `tech`, `label`, `params`, `stats`, `transform`, `crs`, `supply_curve_summary` (`n_points`, `min_lcoe`, `max_lcoe`, `max_capacity_gw`) — **a curva completa e `mask_source` não vão para o `result.pkl`**, só o resumo de 4 números (ver §e.1).

---

## b. Fórmulas e localização exata

Núcleo econômico vive em `src/utils/economics.py`, chamado por `_prepare_financials()`/`_compute_cf_and_lcoe()` em `lcoe_calculator.py`:

| # | Fórmula | Localização |
|---|---|---|
| 1 | **CRF** = `r(1+r)^n / [(1+r)^n − 1]`; se `r ≤ 0`, `CRF = 1/n` | `economics.py::capital_recovery_factor()`, L34-67 |
| 2 | **LCOE base** (nacional, CF média) = `(CAPEX×CRF + OPEX) / (CF × 8760)) × 1000` [USD/MWh] | `economics.py::compute_lcoe()`, L70-117; chamado em `lcoe_calculator.py:909-911` |
| 3 | **Modulação espacial do CF**: `CF_local = clamp(CF_base × (recurso_local / recurso_médio), CF_floor, CF_ceiling)` | `economics.py::modulate_capacity_factor()`, L125-183 |
| 4 | **Bounds do CF** (clamping): `floor = CF_base × 0.40` (solar/wind) ou `CF_base × 0.70` (biomass); `ceiling = min(CF_base × 1.80, 0.95)` (solar/wind) ou `min(CF_base × 0.95, 0.95)` (biomass) — overrides de `parameters.json` (`cf_floor`/`cf_ceiling`) têm precedência | `economics.py::compute_cf_bounds()`, L186-237 |
| 5 | **LCOE por pixel** = `((CAPEX×CRF + OPEX) / (CF_local × 8760)) × 1000`, só para `apt_mask` | `lcoe_calculator.py::_compute_cf_and_lcoe()`, L1061-1067 |
| 6 | **Mapa de capacidade** (MW/pixel) = `área_pixel_km² × land_use_factor × power_density_mw_km2` | `lcoe_calculator.py::_run_technology()`, L840-845 (mesma fórmula do item 8 de `potential_analysis.md`, computada independentemente aqui — ver §e.4) |
| 7 | **Curva de oferta** (merit order): ordena pixels válidos por LCOE crescente, acumula capacidade em GW | `economics.py::compute_supply_curve()`, L245-317 |
| 8 | **CV do recurso** (gate de fallback biomassa) = `std(recurso_apt) / mean(recurso_apt)`; se `< 0.01` e `tech == "biomass"`, troca a fonte de modulação para o proxy de suitability | `lcoe_calculator.py::_compute_cf_and_lcoe()`, L1009-1010, L1022 |

Unidades: LCOE em USD/MWh; CAPEX em USD/kW; OPEX em USD/kW/ano; CF adimensional [0,1]; capacidade em MW/GW; 8760 h/ano fixo (não `hours_year` variável — diferente da Fase 4, que usa `params["hours_year"]`; aqui `economics.compute_lcoe()`'s default `hours_year=8760` é usado implicitamente já que `lcoe_calculator.py` não passa esse argumento explicitamente — **verificar se isso é intencional ou uma divergência com a Fase 4**, ver §e.5).

---

## c. Parâmetros hardcoded

### Já migrados para `parameters.json` (confirmado)
- CAPEX, OPEX, lifetime, discount_rate por país/tecnologia (via `cfg.get_lcoe_params()`).
- `capacity_factor`, `land_use_factor`, `power_density_mw_km2`, `thresholds` por cenário (via `build_tech_params()`).
- `cf_ceiling`/`cf_floor` **quando presentes** em `parameters.json` (override de `compute_cf_bounds()`).

### Ainda hardcoded no código

| # | Local | Valor | O que controla |
|---|---|---|---|
| 1 | `lcoe_calculator.py::DEFAULT_LCOE_PARAMS` (L81-109) | CAPEX/OPEX/lifetime/discount_rate por tech (ex. solar 760 USD/kW, 13 USD/kW/ano, 25 anos, 6%) | Fallback Tier-3 (IRENA 2024) se `parameters.json` não tiver bloco `lcoe` do país — **tabela hardcoded intencional**, mas duplicada conceitualmente com o que deveria vir de `parameters.json`; risco de desalinhar se IRENA atualizar valores de referência e só um dos dois lugares for atualizado |
| 2 | `_MIN_RESOURCE_COVERAGE = 0.05` (L113) | Fração mínima de pixels finitos para confiar num raster de recurso | Ainda não migrado — candidato a `settings.yaml` (gate de qualidade de dado, não científico), per `code-duplication.md` #6 |
| 3 | `src_cv < 0.01` inline (L1022) | Threshold de CV abaixo do qual o recurso de biomassa é tratado como "constante/não confiável" | Ainda não migrado — candidato a constante nomeada, per `code-duplication.md` #7 |
| 4 | `economics.py::compute_cf_bounds()` — `relative_range=(0.40, 1.80)` (L192), biomassa `0.70`/`0.95` (L226,233), `cf_absolute_ceiling` default `0.95` | Bounds de clamping do CF local quando `parameters.json` não define `cf_floor`/`cf_ceiling` explícitos | **Não documentado em nenhum BLOCKER/REFACTOR do legado** — achado novo desta leitura (não estava em `code-duplication.md`). É uma regra científica implícita (por que 0.40×/1.80× para solar/wind e 0.70×/0.95× para biomassa?) hardcoded em `src/utils/economics.py`, não em `parameters.json` |
| 5 | `economics.py::extract_supply_curve_thresholds()` — `lcoe_thresholds=[40,50,60,70,80,100,120,150]` default (L344) | Quais níveis de LCOE aparecem no relatório de texto ("capacidade disponível abaixo de X USD/MWh") | Cosmético/relatório, não afeta cálculo científico |
| 6 | `hours_year=8760` default em `compute_lcoe()` (economics.py:75), usado implicitamente pela Fase 5 (nunca passa `pp["hours_year"]` explicitamente) | Horas/ano para converter CF em energia | Ver §e.5 — possível divergência com a Fase 4, que usa `params["hours_year"]` de `parameters.json` |

---

## d. Cross-check de BLOCKERs já resolvidos

| BLOCKER/Fix | Confirmado presente? | Evidência |
|---|---|---|
| BLOCKER-001 (persistir curva de oferta real em Parquet) | **Sim** | L1148-1152: `supply_curve.to_parquet(out_data / f"{country_code}_{tech}_supply_curve.parquet", index=False)`, comentário cita BLOCKER-001. |
| BLOCKER-002 (percentis completos p25/median/p75) | **Sim** | L1076-1082: `mean`, `p10`, `p25`, `median`, `p75`, `p90` todos computados via `np.percentile` na mesma passada. |
| BLOCKER-006 (resolução centralizada de TIF de suitability) | **Sim** | L591, `find_suitability_tif(suitability_dir, tech, country_code)` (sem `allow_owa_fallback=False` — Fase 5 aceita fallback OWA, diferente da Fase 4). |
| Fix "Grupo C" (usar máscara de pixels aptos da Fase 4, não recomputar por threshold) | **Sim** | L813-823: `_load_potential_suitable_mask()` chamado, resultado passado a `_prepare_modulation_source()`, que prioriza `phase4_apt_mask` sobre o corte por threshold (L950-957). |
| Remoção de `_irena_defaults` (tabela de CF divergente de `constants.DEFAULT_TECH_PARAMS`) | **Sim** | Busca completa no arquivo não encontra `_irena_defaults` — `_resolve_base_cf()` (L499-525) cai direto para `DEFAULT_TECH_PARAMS.get(tech, {}).get("capacity_factor", 0.25)` quando `parameters.json` retorna CF=0. |
| BUG_08 (masking de nodata dentro do context manager) | **Sim** | `_load_input_rasters()` (L881-897): masking ocorre dentro do `with safe_raster_open(...)`, comentário cita BUG_08 explicitamente. |
| REFACTOR-005 (escrita GeoTIFF via `safe_raster_write`) | **Sim** | L1194-1195. |

---

## e. Pontos de incerteza / perguntas abertas para Douglas

1. **`mask_source` computado mas nunca persistido** (GAP-001, confirmado ainda aberto): `_prepare_modulation_source()` retorna `mask_source` (`"phase4_potential_mask"` ou `"suitability_threshold_{thr}"`, L950-957) — mas ao rastrear seu uso, ele é capturado em `_run_technology()` (L821) e **nunca** propagado para `stats` (L1072-1105 não inclui essa chave) nem para o dict serializado (L754-772). Hoje não há como auditar, a partir do output persistido, se uma dada tecnologia/país usou a máscara precisa da Fase 4 ou caiu para o threshold degradado. **Pergunta**: no GeoFREA, esse campo deve ser sempre persistido no contrato de saída da fase?
2. **`DEFAULT_LCOE_PARAMS` duplica conceitualmente `parameters.json`**: os valores de CAPEX/OPEX/lifetime/discount_rate "IRENA 2024 Tier-3" estão hardcoded no módulo (L81-109) como fallback. **Pergunta**: esses valores de referência devem migrar para um arquivo de config versionado (ex. `configs/lcoe_defaults.json`) para facilitar atualização quando a IRENA publicar novos números, ou o hardcode é intencional (valores "congelados" de uma edição específica do relatório)?
3. **`compute_cf_bounds()`'s bounds relativos (0.40×/1.80×, 0.70×/0.95×) não têm justificativa documentada** em nenhum BLOCKER/REFACTOR/DECISIONS existente — achado novo desta auditoria, não presente em `code-duplication.md` nem em `TASKS.md`. **Pergunta**: qual a base metodológica/literatura para esses multiplicadores? Devem ser parametrizados por país/tecnologia em `parameters.json` em vez de constantes globais em `economics.py`?
4. **Fórmula de capacidade (área × LUF × densidade) duplicada entre Fase 4 e Fase 5**: ambas calculam `cap_map` de forma estruturalmente idêntica (Fase 4: `potential_calculator.py:481-486`; Fase 5: `lcoe_calculator.py:840-845`), mas independentemente — nenhuma BLOCKER existente documenta isso como duplicação (o `code-duplication.md` e `write-points-inventory.md` documentam a duplicação da **área geodésica**, não da fórmula de capacidade completa). **Pergunta**: vale unificar num único helper compartilhado no GeoFREA?
5. **`hours_year` possivelmente inconsistente entre fases**: a Fase 4 usa `params["hours_year"]` (de `parameters.json`, via `build_tech_params()`) explicitamente na fórmula de geração (`potential_calculator.py:466-469`). A Fase 5, ao computar LCOE por pixel, chama a fórmula inline (`lcoe_calculator.py:1061-1067`) usando o literal `8760.0` diretamente, **sem** passar por `pp["hours_year"]` — e `economics.compute_lcoe()` (usado só para o `base_lcoe` nacional, não para o mapa por pixel) tem `hours_year=8760` como default, também nunca sobrescrito pela Fase 5. **Não confirmado se isso é uma divergência real** (isto é, se `parameters.json`'s `hours_year` já é sempre 8760 para todos os países/técnicas, o que tornaria isso inofensivo) ou um bug latente. **Pergunta para Douglas**: `hours_year` varia por país/tecnologia em `parameters.json` hoje? Se sim, a Fase 5 está ignorando essa variação.
