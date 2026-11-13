# 04 — METHODOLOGY.md contra o código, F1 a F5 (COMANDO 147-D)

Gerado por script (`meth_map.py`, `meth_nums.py`, `meth_report.py`) e por conferências dirigidas; somente leitura. Nenhum arquivo de docs ou código foi alterado. Pasta mantida não rastreada até o 147-H.

Escopo: as regras `M-F1-*`, `M-F1b-*`, `M-F2a-*`, `M-F2b-*`, `M-F3-*`, `M-F4-*`, `M-F5-*` de `docs/METHODOLOGY.md` (seção 5): **47 regras**. **`core` não tem regras `M-*`**: a arquitetura está em `A-01` a `A-nn` (seção 7) e não entrou aqui. Nada em `M-F5-*` além de `M-F5-07` e nada de `M-F6` em diante foi lido.

**Como o script liga regra, código e teste** (cada ligação é evidência textual, não prova de que o código faz o que a regra diz): código = o ID aparece no docstring de uma função, classe ou módulo de `src/`, ou na coluna de implementação da tabela de conformidade de `docs/phases/*.md` (e então confirmo que o arquivo e o símbolo existem); teste = o ID aparece no docstring ou no começo de uma função `test_*`, ou a coluna de testes da tabela cita um teste que existe. `indireto` = quantos arquivos de teste importam o módulo do código, sem citar a regra. Estados: **ok** (código e teste), **sem teste** (código, nenhum teste direto), **sem código** (nenhum rastro), **divergente** (um número da regra não bate; o item 2 mostra o resultado).

## Contagem por estado

| estado | regras |
|---|---|
| ok | 30 |
| sem código | 1 |
| sem teste | 16 |

Divergentes por número (item 2): **0** de 32 conferências.


## 1. Uma linha por regra

| regra | linha | resumo (até 12 palavras) | arquivo:função | como achei | teste | indireto | estado |
|---|---|---|---|---|---|---|---|
| M-F1-01 | 175 | Layer registry with provenance per layer: provenance in {fetched, local_only} and computed | data_acquisition/schemas.py:AcquiredLayer | tema: `provenance`, `fetch_status` (sem o ID em docstring) | test_data_selfcontained.py::<module> | 5 | ok |
| M-F1-02 | 176 | Active layers: country borders and admin1 (GADM 4.1), protected areas (WDPA via | data_acquisition/ (registro de camadas, `_LAYER_REGISTRY`) | tema: nomes das camadas ativas (sem o ID) | — | 0 | sem teste |
| M-F1-03 | 177 | Global Wind Atlas products at hub-relevant heights 100, 150, 200 m: combined-Weibull-A, | config_models/audit.py:AuditConfig | docstring (5) | test_data_acquisition_phase.py::test_run_acquisition_phase_every_layer_path_is_none_when_fetchers_fail (+2) | 5 | ok |
| M-F1-04 | 178 | CMIP6 from Copernicus CDS: monthly rsds, tas, sfcWind for historical and the | config_models/audit.py:AuditInputs | docstring (7) | — | 5 | sem teste |
| M-F1-05 | 179 | ERA5 gust reanalysis (scenario-invariant extreme-wind indicator), built fresh (CRAEI's own D12 decided | climate_forcing/hazards.py:era5_gust_mean_annual_max | docstring (6) | — | 2 | sem teste |
| M-F1-06 | 180 | Existing solar and wind plants from Global Energy Monitor trackers, used only | external_validation/inventory.py:load_inventory | docstring (3) | test_gem_trackers.py::<module> | 1 | ok (tabela cita código que existe) |
| M-F1-07 | 181 | GADM borders resolve local-first with checksum; network download is a fallback. | data_acquisition/fetchers/gadm.py:GadmChecksumMismatchError | docstring (5) | — | 4 | sem teste |
| M-F1b-01 | 185 | Audit every active layer: coverage, nodata share, value ranges, resolution, CRS. Expected | config_models/audit.py:AuditLayerConfig | docstring (6) | — | 5 | sem teste |
| M-F1b-02 | 186 | The audit's findings never block execution: an anomaly is reported, not enforced. | data_quality_audit/raster_inspection.py:inspect_raster_cached | docstring (1) | — | 3 | sem teste |
| M-F2a-01 | 190 | Analysis grid: EPSG:4326, fixed 0.01 degree resolution, snapped so that 0.05 degree | core/geo_utils.py:contiguous_mainland_report | docstring (6) | — | 4 | sem teste |
| M-F2a-02 | 191 | All distances and areas are geodesic (core/geodesy.py), including slope derivation from the | grid_alignment/raster_alignment.py:derive_slope_from_dem | docstring (3) | test_grid_alignment_slope_derivation.py::test_derive_slope_uses_geodesic_spacing_at_high_latitude | 7 | ok |
| M-F2a-03 | 192 | Distance rasters to the transmission grid, roads, rivers and substations store the | core/schemas.py:GeospatialConfig | docstring (10) | test_grid_alignment_vector_alignment.py::test_rasterize_linear_distance_stores_the_raw_distance_and_flags_beyond_the_cap | 15 | ok |
| M-F2a-04 | 193 | Wind products are aligned per height; no combination across heights happens in | grid_alignment/layers.py:gwa_crs_for | docstring (3) | test_grid_alignment_alignment.py::test_run_grid_alignment_phase_aligns_each_wind_height_on_its_own_without_combining | 3 | ok |
| M-F2a-05 | 194 | Layers that hold counts (population) are brought to the analysis grid by | grid_alignment/raster_alignment.py:reproject_to_grid | docstring (2) | — | 7 | sem teste |
| M-F2a-06 | 195 | Land cover enters F3 as class counts, not as one class per | grid_alignment/raster_alignment.py:LandCoverCountNotExactError | docstring (2) | test_grid_alignment_raster_alignment.py::test_land_cover_counts_exact_or_raise | 7 | ok |
| M-F2a-07 | 196 | Slope enters F3 as a distribution, not a pixel mean: the FABDEM | grid_alignment/fabdem_slope.py:fabdem_slope_outputs | docstring (3) | — | 1 | sem teste |
| M-F2a-08 | 197 | The aligned elevation is the mean of the 30 m Copernicus GLO-30 | grid_alignment/raster_alignment.py:glo30_aligned_outputs | docstring (2) | — | 7 | sem teste |
| M-F2a-09 | 199 | Point of interconnection (Group 3, docs/thesis/methods/group3_connection_degradation.tex). poi is the uncapped geodesic distance | grid_alignment/poi.py:parse_voltage_kv | docstring (4) | test_grid_alignment_poi.py::<module> | 3 | ok |
| M-F2a-10 | 200 | Road classes. The distance to the road (roads) is the distance to | grid_alignment/vector_alignment.py:filter_road_classes | docstring (1) | — | 2 | sem teste |
| M-F2a-11 | 202 | Settlements (Group 6, docs/thesis/methods/group6_land_eligibility.tex). settlements is the class of the GHS settlement | data_acquisition/fetchers/ghsl.py | tema: GHS-SMOD (sem o ID em docstring) | test_adopt_aligned_cache_keys.py::test_the_cache_code_of_a_revision_is_that_of_its_tree | 0 | ok |
| M-F2b-01 | 206 | Exclusion terms per technology, each the excluded share of a pixel in | land_eligibility/eligibility.py:exclusion_fractions | docstring (3) | — | 4 | sem teste |
| M-F2b-02 | 214 | Cost-driver layers: distance to transmission grid (km; every OSM line and substation, | siting_layers/physical_layers.py:build_physical_layers | docstring (2) | test_siting_layers_physical_layers.py::<module> | 4 | ok |
| M-F2b-03 | 215 | Resource layers: solar PVOUT (kWh/kWp/day); wind Weibull A (m/s), Weibull k (-), | siting_layers/physical_layers.py:build_physical_layers | docstring (2) | — | 4 | sem teste |
| M-F2b-04 | 216 | No normalization, weighting, or scoring of any layer. Values keep physical units. | core/deferred_check.py:reference_names | docstring (3) | — | 3 | sem teste |
| M-F2b-05 | 217 | Fail-loud on integrity failures of present files (corrupted tiles, invalid WDPA files). | land_eligibility/errors.py:MissingRequiredLayerError | docstring (2) | test_land_eligibility_pipeline.py::test_missing_required_layer_raises | 0 | ok |
| M-F2b-06 | 218 | The parameters of E1-E6 and the minimum eligible area are declared in | config_models/land_availability.py | tema: bloco `land_availability` (teste `test_elevation_cap.py` cita o ID) | test_elevation_cap.py::<module> | 8 | ok |
| M-F3-01 | 222 | Pixel eligibility per technology: the eligible share of a pixel is valid | land_eligibility/eligibility.py:eligible_fraction | docstring (5) | test_land_eligibility_cells.py::<module> | 4 | ok (tabela cita código que existe) |
| M-F3-02 | 223 | Eligibility is computed for the three named land-availability scenarios of U-06 (central, | land_eligibility/scenarios.py:scenario_sets | docstring (3) | test_land_eligibility_group6_values.py (+1) | 7 | ok (tabela cita código que existe) |
| M-F3-03 | 224 | Cell aggregation to 0.05 degree (5 x 5 pixels). Per cell and | land_eligibility/admin1.py:assign_admin1 | docstring (4) | test_land_eligibility_admin1.py::<module> | 1 | ok (tabela cita código que existe) |
| M-F3-04 | 232 | A cell enters the candidate set if eligible_area_km2 > 0, it has | land_eligibility/cells.py:candidate_cells | docstring (6) | — | 17 | sem teste (tabela cita código que existe) |
| M-F3-05 | 233 | Outputs: candidates_<tech>.parquet (one row per candidate cell, stable cell_id, with admin1_id), pixel | land_eligibility/pipeline.py:prepare_shared_layers | docstring (2) | test_land_eligibility_pipeline.py | 6 | ok (tabela cita código que existe) |
| M-F3-06 | 234 | The cell size is a parameter of the run, scale (0.05 degree, | core/scale.py:use_scale | docstring (4) | test_main.py::test_the_scale_is_a_command_line_option_with_the_default_scale_as_default (+1) | 6 | ok (tabela cita código que existe) |
| M-F3-07 | 236 | Minimum eligible area (Group 6). Eligible pixels (fraction above 0) are grouped | land_eligibility/windows.py:ScenarioStripes | tabela da fase | test_land_eligibility_min_area.py (+1) | 2 | ok (tabela cita código que existe) |
| M-F4-01 | 240 | Climate members m = (gcm, ssp, window), plus the reference member m0 | climate_forcing/members.py:resolve_members | docstring (3) | test_climate_forcing_forcing.py::<module> | 4 | ok (tabela cita código que existe) |
| M-F4-02 | 241 | GCM selection protocol, executed once at F4 implementation and recorded in the | climate_forcing/forcing.py:member_factor_fields | docstring (5) | test_climate_forcing_forcing.py::test_load_ensemble_reads_the_real_experiments_yaml (+1) | 5 | ok |
| M-F4-03 | 248 | Change factors (delta-change), computed on each GCM's native grid from monthly climatologies: | climate_forcing/change_factors.py:compute_change_factor | docstring (3) | test_climate_forcing_change_factors.py::<module> (+1) | 2 | ok (tabela cita código que existe) |
| M-F4-04 | 253 | Change factors are bilinearly interpolated to the cell centers of the run | climate_forcing/change_factors.py:bilinear_to_points | docstring (5) | test_climate_forcing_change_factors.py::<module> (+1) | 2 | ok (tabela cita código que existe) |
| M-F4-05 | 254 | Hazard channels (D15 rule): | climate_forcing/hazards.py:mean_annual_hot_days | docstring (9) | test_climate_forcing_hazards.py::<module> | 2 | ok (tabela cita código que existe) |
| M-F4-06 | 258 | Outputs: forcing.parquet (cell_id, member, delta_rsds, dT, delta_wind, dT_isolated_native_cell; one row for every | climate_forcing/forcing.py:isolated_native_cells | docstring (12) | test_climate_forcing_forcing.py::<module> | 5 | ok (tabela cita código que existe) |
| M-F4-07 | 259 | Validity mask for the wind factor: a cell-member whose delta_wind lies outside | climate_forcing/forcing.py:assert_forcing_usable | docstring (9) | test_zzz_end_to_end.py::test_the_forcing_comes_from_the_miniature_cmip6_files_and_declares_its_masked_cell_members (+5) | 5 | ok (tabela cita código que existe) |
| M-F5-01 | 263 | Capacity per cell: P_MW = eligible_area_km2 * LUF[tech, scenario] * PD[tech, scenario], | core/production.py:audit_parameters | docstring (9) | test_groups12_parameters.py::<module> (+3) | 3 | ok (tabela cita código que existe) |
| M-F5-02 | 264 | Solar capacity factor: | technical_potential/cf_models.py:PvoutWithTemperature | docstring (6) | rescale.py::<module> (+1) | 4 | ok (tabela cita código que existe) |
| M-F5-03 | 267 | Wind capacity factor: | core/config_schemas.py:ClassFlagRule | docstring (27) | rescale.py::<module> (+10) | 11 | ok (tabela cita código que existe) |
| M-F5-04 | 275 | If a C2 loss function passes OQ-007: CF_m <- CF_m * (1 | — | — | test_methodology_changelog.py::test_changed_ids_include_sub_bullets_rows_and_removed_lines | 0 | sem código (condicional: só vale se uma função de perda C2 passar OQ-007 (OQ-007 aberta); nada a implementar hoje) |
| M-F5-05 | 276 | Annual energy: E_m = P_MW * CF_m * 8760 (MWh/yr; the hours | technical_potential/capacity.py:annual_energy_mwh | docstring (2) | test_technical_potential_functions.py::<module> | 1 | ok (tabela cita código que existe) |
| M-F5-06 | 277 | Outputs, one file per technology and land-availability scenario: potential_<tech>__<scenario>.parquet (cell_id, member, P_MW, | technical_potential/aggregates.py:like_for_like_mask | docstring (11) | test_zzz_produces_the_potential_files_for_three_scenarios_and_the_aggregates (+2) | 1 | ok (tabela cita código que existe) |
| M-F5-07 | 278 | Maps of the potential, drawn by the phase potential_maps at the reference | technical_potential/maps.py:build_potential_maps | docstring (1) | — | 1 | sem teste |

Observação: quando a ligação é por docstring de módulo, a coluna mostra `<module>` ou a função escolhida entre as que citam o ID; a regra pode ter mais de um implementador (o número entre parênteses é a contagem de docstrings).

**Sem código (1):** M-F5-04 (condicional: só vale se uma função de perda C2 passar OQ-007 (OQ-007 aberta); nada a implementar hoje).

**Sem teste direto (16):** M-F1-02, M-F1-04, M-F1-05, M-F1-07, M-F1b-01, M-F1b-02, M-F2a-01, M-F2a-05, M-F2a-07, M-F2a-08, M-F2a-10, M-F2b-01, M-F2b-03, M-F2b-04, M-F3-04, M-F5-07.

## 2. Números das regras contra config e código

Método: extraí 151 números do texto das 47 regras (sem IDs); os que são limiares, unidades, resoluções, anos e contagens fixas com contrapartida em config ou código foram conferidos um a um abaixo (leitura do valor vivo em `config/*.yaml|json` e nas constantes do código). Os demais são citações de dados de uma execução, de literatura, de datas de decisão ou de resultados de auditoria, e estão no item 4. Cobertura: 151 números, dos quais os de conferência direta estão abaixo; não conferi anos de decisão (`2026-10-06`, `V-B1`) nem versões de produto.

| regra | o que o texto diz | onde está no código ou na config | valor lido | resultado |
|---|---|---|---|---|
| M-F2a-01 | pixel 0,01 grau | settings.yaml geospatial.resolutions.suitability | 0.01 | bate |
| M-F2a-01 | célula 0,05 = 5 x 5 pixels | 0,05 / 0,01 | 5 | bate |
| M-F2a-01 | ilhas a menos de 1 km do território contíguo | core/geo_utils.py MAINLAND_MAX_GAP_KM | MAINLAND_MAX_GAP_KM = 1.0 | bate |
| M-F2a-03 | 20.000 feições por bloco | grid_alignment/vector_alignment.py _FEATURE_CHUNK | _FEATURE_CHUNK = 20_000 | bate |
| M-F2a-03 | 6 milhões de alvos por bloco | grid_alignment/vector_alignment.py _BLOCK_VERTICES | _BLOCK_VERTICES = 6_000_000 | bate |
| M-F2a-03 | 2 milhões por bloco nos rios | grid_alignment/vector_alignment.py _RIVER_BLOCK_VERTICES | _RIVER_BLOCK_VERTICES = 2_000_000 | bate |
| M-F2a-03 | linha densificada a 100 m | grid_alignment/vector_alignment.py | 100.0  # the longest stretch between two vertices of a line, in m | bate |
| M-F2a-03 | limite superior por um vértice real a cada 32 | grid_alignment/vector_alignment.py | 32 | bate |
| M-F2a-09 | BRA 138 kV | parameters.json BRA.connection.poi_voltage_threshold_kv | 138.0 | bate |
| M-F2a-09 | IND 220 kV | parameters.json IND.connection.poi_voltage_threshold_kv | 220.0 | bate |
| M-F2a-09 | PRT 150 kV | parameters.json PRT.connection.poi_voltage_threshold_kv | 150.0 | bate |
| M-F2a-09 | IND sensibilidade 132 kV | parameters.json IND.connection.poi_sensitivity_threshold_kv | 132.0 | bate |
| M-F2a-09 | tolerância de linha 50 m | settings.yaml geospatial.poi_line_tolerance_m | 50.0 | bate |
| M-F2a-10 | GRIP4 GP_RTP 1, 2, 3 | settings.yaml geospatial.road_classes.grip4_gp_rtp | [1, 2, 3] | bate |
| M-F2a-10 | OSM motorway, trunk, primary, secondary | settings.yaml geospatial.road_classes.osm_highway | ['motorway', 'trunk', 'primary', 'secondary'] | bate |
| M-F1b-01 | alerta abaixo de 99% | data_quality_audit/raster_inspection.py MASK_COVERAGE_WARN_PCT | MASK_COVERAGE_WARN_PCT = 99.0 | bate |
| M-F1-03 | completar a camada se menos de 99% da máscara | data_acquisition/fetchers/wind.py GWA_COVERAGE_MIN_PCT | GWA_COVERAGE_MIN_PCT = 99.0 | bate |
| M-F1-05 | período de referência 1995-2014 | data_acquisition/fetchers/era5.py | 1995-2014 | bate |
| M-F2b-06 | elevation_max_m 2.000 (restritivo) | experiments.yaml land_availability.technologies.wind.elevation_max_m | 2000.0 | bate |
| M-F2b-06 | elevation_max_m 3.000 (central) | idem | 3000.0 | bate |
| M-F2b-06 | elevation_max_m sem limite (permissivo) | idem | None | bate |
| M-F3-07 | PV: 1 km2 (central) | experiments.yaml solar.min_area.cluster_km2.central | 1.0 | bate |
| M-F3-07 | PV: sem mínimo (permissivo) | idem .permissive | None | bate |
| M-F3-07 | PV restritivo: P_ref / PD_PV | idem .restrictive | project_area | bate |
| M-F3-07 | eólica: piso de 10 % do pixel (central) | experiments.yaml wind.min_area.pixel_fraction.central | 0.1 | bate |
| M-F3-07 | eólica: mesmo piso no restritivo | idem .restrictive | 0.1 | bate |
| M-F3-07 | eólica: sem piso no permissivo | idem .permissive | None | bate |
| M-F3-07 | eólica restritiva: aglomerado P_ref / PD_wind | idem cluster_km2.restrictive | project_area | bate |
| M-F4-07 | faixa do fator de vento 0,5-1,5 | experiments.yaml gcm_ensemble.wind_factor_valid_range | [0.5, 1.5] | bate |
| M-F5-05 | E = P * CF * 8760 | core/constants.py HOURS_PER_YEAR | HOURS_PER_YEAR: float = 8760.0 | bate |
| M-F5-07 | tolerância de 0,1% entre células, estados e total | technical_potential/absolute_maps.py | 1e-3  # 0.1% | bate |
| M-F5-07 | 6 classes de Fisher-Jenks | technical_potential/absolute_maps.py (docstring; valor em código não verificado) | 6 classes by Fisher | bate |

**Divergentes: 0** de 32.

Limite: a conferência é de valor, não de uso. Por exemplo, ela mostra que `poi_voltage_threshold_kv` de BRA vale 138 kV; não mostra que F2a lê essa chave. 

## 3. Código com lógica própria sem regra M-* de F1 a F5

Heurística (candidatos, não confirmados por leitura): funções e classes públicas de nível de módulo com 25 linhas ou mais, nos pacotes de F1 a F5, sem `M-F*` no docstring da função nem no do módulo. "só D-/A-/OQ-" quer dizer que há outro tipo de ID (a decisão está numa fase, não no METHODOLOGY); "nenhum ID" quer dizer que não há rastro.

| fase | pacote | públicas no nível do módulo | grandes sem M-F* | dessas, sem nenhum ID |
|---|---|---|---|---|
| F1 | data_acquisition | 112 | 13 | 8 |
| F1b | data_quality_audit | 24 | 10 | 8 |
| F2a | grid_alignment | 55 | 5 | 5 |
| F2b | siting_layers | 16 | 3 | 0 |
| F3 | land_eligibility | 92 | 8 | 3 |
| F4 | climate_forcing | 71 | 4 | 2 |
| F5 | technical_potential | 127 | 23 | 10 |

Exemplos sem nenhum ID (até 10, os maiores):

| arquivo | função ou classe | linhas |
|---|---|---|
| grid_alignment/alignment.py | run_grid_alignment_phase | 384 |
| data_quality_audit/vector_inspection.py | inspect_vector_layer | 142 |
| data_acquisition/fetchers/protected_planet.py | fetch_protected_areas | 123 |
| data_quality_audit/raster_inspection.py | inspect_land_cover_tiles | 113 |
| land_eligibility/windows.py | ScenarioStripes | 105 |
| technical_potential/question_figures.py | comparison_sheet | 96 |
| data_acquisition/local_layers.py | resolve_land_cover_tiles | 84 |
| climate_forcing/pipeline.py | build_forcing | 81 |
| technical_potential/question_figures.py | change_sheet | 70 |
| data_acquisition/adapter.py | acquisition_result_to_audit_inputs | 57 |

Lista completa: `04b_code_without_mf_rule.tsv`.

## 4. Afirmações que dependem de dado

Varredura das linhas 1 a 576 de `METHODOLOGY.md` (o changelog, seção 14, é datado por construção e ficou de fora). Padrões: contagens de dados, percentuais, valores por país com unidade, percentis. Muitos acertos são parâmetros de método (ex.: 99% do alerta, 10 % do piso de pixel) e não dado; a coluna *com data ou auditoria* diz se a linha já cita uma data, um COMMAND ou um arquivo de `docs/_audit`.

| padrão | acertos | com data ou auditoria | linhas distintas |
|---|---|---|---|
| percentil ou desvio medido | 6 | 1 | 6 |
| contagem de dados (células, candidatos, pixels, feições, amostras, membros, arquivos) | 13 | 2 | 10 |
| percentual medido | 18 | 12 | 10 |
| valor por país com unidade | 1 | 0 | 1 |

Linhas com acerto: 25; acertos sem data nem auditoria na mesma linha: **23**.

Os acertos sem data são, na maioria, parâmetros de método (`5 x 5`, `2 x 2`, `P99`, `99%`) e não dado de execução: a varredura tem muitos falsos positivos (lista completa no `.tsv`). Os que são dado de execução, por leitura (BRA, IND, PRT, milhões), com a marcação sugerida:

| linha | trecho | marcação sugerida |
|---|---|---|
| L218 | the highest wind candidate is 1356 m in PRT and 1922 m in BRA). `sensitivity` is nul | nota "valor de data X" |

Casos que encontrei na leitura, além da varredura:

| onde | afirmação | marcação sugerida |
|---|---|---|
| M-F2a-03 (linha 192) | "off by up to 18 % (P95 8 to 15 %...)", "up to 0.78 km", "26.5 million" vértices dos rios de BRA | nota com data e fonte (`docs/_audit/dist_sub_scale_audit.md`); o 26,5 milhões é dado de BRA |
| M-F2b-06 (linha 218) | "the highest wind candidate is 1356 m in PRT and 1922 m in BRA" | tabela gerada ou "valor de data X" (muda a cada rodada do F3) |
| M-F2a-05 (linha 194) | "Sampling had left 1/144 of the population" | nota com data (D-F2a-014) |

Lista completa: `04c_data_dependent_statements.tsv`.

## 5. Trechos que contradizem DECISIONS.md, OPEN_QUESTIONS.md ou LIMITATIONS.md

**(a) OQ citadas nas 47 regras e o estado delas em `OPEN_QUESTIONS.md`:**

11 citações de 10 OQ. Por estado: {'open': 3, 'fora da tabela (resolvida e apagada, ou nunca aberta)': 8}.

Exemplos (até 10), todos que a regra descreve como pendente mas que estão fora da tabela, ou que a regra descreve como resolvida mas estão `open`:

| regra | OQ | estado na tabela | trecho da regra |
|---|---|---|---|
| M-F2a-08 | OQ-061 | fora da tabela (resolvida e apagada, ou nunca aberta) | nst GLO-30 in IND and BRA and had seam lines without value, OQ-061). The F1 registry still locates it and F1b still  |

Total por palavra-chave: 1 (candidatos).

**(b) Linhas de `LIMITATIONS.md` e `OPEN_QUESTIONS.md` que citam regra M-F1 a M-F5 que não existe no METHODOLOGY.md: 0** .

**(c) Contradições entre regra e registro, achadas por leitura** (cada uma foi conferida no texto das duas fontes):

| trecho do METHODOLOGY | registro | conflito |
|---|---|---|
| M-F2b-06 (linha 218): categorias IUCN são "níveis nomeados, com um nível central" | DECISIONS.md #1 (2026-08-19) | #1 fixa a exclusão uniforme das categorias Ia, Ib e II; a regra e `experiments.yaml` usam `all_designated` como nominal. A regra está certa com a config; o DECISIONS.md está desatualizado (já em `03_decisions_audit.md`). |
| M-F2b-01 (linha 212): E4 usa `slope_max_pct[tech]` de `land_availability` | DECISIONS.md #11 (2026-08-20) | #11 põe `slope_threshold_deg` por tecnologia e país em `parameters.json`; hoje não existe lá (já em `03`). |
| M-F2a-04: alturas do vento alinhadas uma a uma, sem combinação | DECISIONS.md #34 (2026-09-09, item 4) | #34 mantém a matriz AHP que combinava alturas; a regra e D-F2a-005 a removem (já em `03`). |

Conferi também: M-F2b-06 diz que o limite de 3.000 m é "Tier 3, sem fonte: LIMITATIONS"; `grep elevation_max_m docs/LIMITATIONS.md` encontra a linha correspondente. A regra M-F2a-03 chama o limiar de 100 km de "provisório, sem fonte (L-019)"; L-019 existe em LIMITATIONS.md.

Não comparei as 47 regras com as 66 entradas do DECISIONS.md uma a uma além dos três casos acima e do que o `03` já listava; tampouco li cada linha de `LIMITATIONS.md` contra as regras.

