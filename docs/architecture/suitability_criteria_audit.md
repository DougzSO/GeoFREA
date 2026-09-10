# Suitability Criteria (Fase 2b) — Auditoria do legado + contrato revisado

**Alvo:** `$GEOWORLD_BASELINE_DIR/src/processors/criteria_builder.py` @ `fc7b43d` (1087 linhas, lido integralmente, read-only).
**Suporte:** `src/core/constants.py`, `src/core/schemas.py` (`AlignedLayers`, `CountryParams`, `CriteriaResult`), `src/utils/normalization.py`, `src/utils/reporting.py`, `src/utils/exclusion.py`, `src/processors/suitability_builder.py`, `src/processors/grid_aligner.py`, `main.py` L680-740, baseline `criteria_summary_PRT.txt`.
**Cross-check GeoFREA:** `docs/architecture/suitability_criteria.md`, `docs/DECISIONS.md` (IUCN / protected / GRIP4 / 2026-09-10 parameter calibration), `src/geofrea/grid_alignment/schemas.py`, `src/geofrea/core/schemas.py`, `src/geofrea/data_acquisition/schemas.py`.

Este documento é o resultado da auditoria de leitura feita antes de projetar `suitability_criteria`. Complementa `suitability_criteria.md` (notas de arquitetura originais, 2026-08-19) — não o substitui. A §8 (contrato) já reflete as decisões registradas em `docs/DECISIONS.md` 2026-09-10 "suitability_criteria parameter calibration".

---

## 1. Inputs

### 1a. De `grid_alignment` (Fase 2a) — via `aligned: AlignedLayers`

`CriteriaBuilder.run()` recebe `aligned` e normaliza para `AlignedLayers` (L847-850). São **12 rasters**, todos na mesma grade (CRS/transform/shape idênticos, `EPSG:4326`, resolução `0.01°` fixo — ver `DECISIONS.md` 2026-09-09 item 3):

| campo `AlignedLayers` | consumido por | formato esperado | obrigatório? |
|---|---|---|---|
| `elevation` | `compute_terrain_score` (TRI) | float32, metros | **sim** (L853) |
| `slope` | `compute_terrain_score`, `compute_slope_degrees` | float32, graus | **sim** |
| `solar` | `compute_solar_resource` | float32, PVOUT kWh/kWp | **sim** |
| `land_cover` | `compute_land_cover_scores`, `compute_biomass_resource` | uint8, códigos ESA WorldCover | **sim** |
| `wind` | `compute_wind_resource` | float32, velocidade/densidade | não (skip se ausente) |
| `population` | `compute_population_suitability` | float32, hab/km² | não |
| `roads` | `compute_road_suitability` | float32, **distância-a-estrada em km** (raster já calculado na Fase 2a) | não |
| `grid` | `compute_grid_suitability` | float32, distância-a-rede km | não |
| `lakes` | `compute_lakes_exclusion` | uint8 (`0`=lago, `1`=terra, `255`=fora do país) | não |
| `rivers` | `compute_river_suitability` (×3 techs) | float32, distância-a-rio km | não |
| `seismic` | `compute_seismic_suitability` | float32, PGA (hazard) | não |
| `plants` | `compute_proximity_plants` | uint8 (`1`=usina, `255`=fora, `0`=terra) | não (warning se ausente) |

Validação: `validate_aligned_layers(aligned, required_layers=["elevation","slope","solar","land_cover"], expected_shape, expected_crs, check_values=False)` (L864). Grade de referência (`ref_path`) = **primeiro path existente em `aligned.to_dict().values()`** (L854-856) — heurística frágil, ver §7 (D5).

### 1b. Inputs que **NÃO** vêm de `grid_alignment` — acoplamento multi-fase

Além de `aligned`, `run()` (L825-838) recebe:

| arg | origem no `main.py` legado (L693-706) | natureza |
|---|---|---|
| `mainland_gdf` | bootstrap (borders GADM) | GeoDataFrame — `compute_protected_areas` rasteriza a máscara mainland; toda a cartografia |
| `country_params` | `ConfigLoader.get_country()` → `CountryParams` | config |
| `land_suit` | `cfg.land_suitability` (tabela ESA→score) | config |
| `wdpa_path` | `status.get("Protected")` — path do shapefile WDPA **bruto, não alinhado** | vetor cru (acquisition) |
| `plants_df` | `status.get("Plants")` — DataFrame WRI/GPPD | tabular cru |
| `context_gdf` | países vizinhos, bootstrap | só cartografia |
| `rivers_path`, `lakes_path`, `seismic_path` | `status.get(...)` | **DEAD PARAMS** — declarados em `run()` L836-838, nunca referenciados no corpo (o corpo usa `validated.rivers/lakes/seismic`). Ver §7 (D1). |

**Conclusão p/ GeoFREA:** a Fase 2b consome **dois** `prior_results` — `grid_alignment` (12 rasters) **e** `data_acquisition` (path do WDPA + `plants_df` + `mainland_gdf`/borders). Não é fase de input único.

---

## 2. Outputs

### 2a. Artefatos em disco

Base: `outputs/{ISO3}/criteria_builder/` (L888), três subdirs sempre criados (L892-893):

- **`tif/{nome}.tif`** — um GeoTIFF por critério. Perfil (`_save_criterion` L94-112): `driver=GTiff`, `dtype=float32`, `count=1`, `nodata=-9999.0`, `compress=lzw`, `tiled=True`, `blockxsize/ysize=256`.
- **`figures/{nome}.png`** — um mapa por critério (Matplotlib Agg, `ThreadPoolExecutor`, `render_workers=4`). Pulável via `pipeline.skip_criteria_maps`.
- **`reports/criteria_summary_{ISO3}.txt`** — `write_criteria_summary()` (`reporting.py` L299): texto bespoke (histograma 5-bin, P10/P50/P90, mean±std). **Não** usa `build_phase_report()` genérico (GAP-004).

### 2b. Nomenclatura — **14 critérios "esperados"** (L1067-1072, bate com baseline PRT):

```
solar_resource   wind_resource   terrain_score   lc_biomass   biomass_resource
protected_areas  pop_suitability road_suitability lakes_exclusion
river_solar      river_wind      river_biomass   seismic_suitability  grid_suitability
```

Mais **`slope_degrees.tif`/`.png`** (L946-947): escrito em disco mas **fora** do dict `criteria` e da lista "esperada" — insumo cartográfico, não critério MCDA.

Convenção: `snake_case`, sem código de país no filename (país está no path). `river_*` explode a camada `rivers` em 3 saídas. Nomes de disco = chaves do dict em memória.

### 2c. Retorno em memória (L1079-1087)

```python
{"country_code": str, "criteria": Dict[str, np.ndarray], "tif_dir": Path,
 "fig_dir": Path, "report_dir": Path, "n_criteria": int, "timestamp": str}
```

Validado por `CriteriaResult` (`schemas.py` L516). Invariante `n_criteria == len(criteria)` (L547). **`criteria` carrega arrays numpy inteiros, persistido via pickle** — artefato pesado, redundante com os `.tif`. Ver §7 (D6).

---

## 3. Lógica de exclusão vs. aptidão contínua

**Ponto arquitetural:** a Fase 2b legada **quase não decide exclusão**. Produz scores `[0,1]` fuzzy. O *gating* binário real acontece na **Fase 3** (`suitability_builder.py` → `apply_hard_exclusions`, `exclusion.py` L88). A Fase 2b só *codifica* semântica binária em 3 critérios; o resto é contínuo.

### 3a. Critérios de exclusão binária

| # | Origem | O que produz | Onde vira exclusão de fato |
|---|---|---|---|
| E1 | `compute_lakes_exclusion` (L536) | estritamente `{0.0, 1.0}` (0=lago) | Fase 3: `hard_exclusions["lakes_exclusion"] = 0.5` → pixel `< 0.5` excluído. `CountryParams` deliberadamente sem campo (L392-395). |
| E2 | `compute_protected_areas` (L435), `as_exclusion=True` | IUCN Ia/Ib/II → `0.0`; demais categorias → `IUCN_SCORES[cat]` (0.10–0.55); território livre → `1.0` | Fase 3: `hard_exclusions["protected_areas"] = protected_areas_threshold` (**default `0.99`**) → **tudo abaixo de 0.99 é excluído**. Como o único valor `≥ 0.99` que a função emite é `1.0`, na prática **toda feição WDPA (qualquer categoria) é hard-excluída** — os scores fracionários e a tabela `IUCN_SCORES` são valores mortos sob o default. **→ RESOLVIDO** (DECISIONS 2026-09-10): GeoFREA usa máscara binária, tabela graduada descartada. |
| E3 | `compute_river_suitability`, ramo `else` → `river_solar`, `river_wind` (L573-576) | setback ripário: `d < river_safety_buffer_km (0.5)` → `0.0`; senão `1.0` | Legado: **não** estão em `hard_exclusions` — entram só no `priority_order` do AHP como score `{0,1}` degenerado. **→ RESOLVIDO** (DECISIONS 2026-09-10): promovidos a hard exclusion (adicionados a `common_exclusions` na Fase 3), pois representam setback de segurança, não preferência. |

Exclusões **puramente da Fase 3** (herdam parâmetros da família de params, mas o gate é lá, não na 2b):
- `proximity_plants < proximity_plants_threshold (0.01)` — exclui pixel *em cima* de usina existente.
- `slope > slope_max` — usa o raster `slope` alinhado **diretamente**, não `terrain_score`. Legado: `slope_threshold_deg` (país) `+ slope_offset_{tech}_deg` (5/10/20). **→ RESOLVIDO** (DECISIONS 2026-09-10): constantes fixas cross-country solar=5, wind=25, biomass=15; offset aditivo removido.
- `land_cover ∈ {50,70,80,90,95}` (+`{10}` se `forest_as_exclusion`) — usa `land_cover` alinhado diretamente.

### 3b. Critérios de aptidão contínua (alimentam AHP/TOPSIS na Fase 3)

| critério | fórmula (linha) | parâmetros |
|---|---|---|
| `solar_resource` | `normalize_percentile(data, valid, p_low, p_high)`; opcional `× solar_pvout_weight` (L135-144) | percentis (5/95), `solar_pvout_weight` (1.0) |
| `wind_resource` | `normalize_percentile` (L157-163) | percentis |
| `terrain_score` | `0.6·slope_score + 0.4·TRI_score` (L216); `slope_score = clip(1 − slope/thr, 0,1)`; `TRI = sqrt(Σ_8viz (E_c − E_i)²)`; `TRI_score = clip(1 − TRI/TRI_THRESHOLD, 0,1)` | `slope_threshold_deg` (fallback 7.0 na função, L176), `TRI_THRESHOLD = 50.0`, pesos `0.6/0.4` |
| `road_suitability` | `compute_linear_proximity_suitability`: `raw = clip(1 − d/d_max, 0,1)` → `normalize_percentile(5, 95)` hardcoded (L258) | `road_max_dist_km` — **15.0** (ver §6, confirmado bit-exato contra baseline PRT 2026-09-10) |
| `grid_suitability` | idem `compute_linear_proximity_suitability` | `grid_max_dist_km` (20.0) |
| `proximity_plants` | `S_ren = 1 − exp(−d/σ)`; `S_therm = exp(−d/σ)`; `max(...)`; suaviza gaussiana `σ_px = max(0.5, PROXIMITY_SMOOTH_SIGMA_PX/res_km)`; `normalize_percentile(5,95)` hardcoded; `raw[usina] = 0.0`; **país sem usinas: `raw[terra] = 0.3`** (L346) | `PROXIMITY_DECAY_SIGMA_KM = 10.0`, `PROXIMITY_SMOOTH_SIGMA_PX = 2.0`, fallback `0.3` |
| `lc_biomass` | lookup direto: `score = land_suit["biomass"][classe_ESA]` (L377-384) | tabela `land_suitability` |
| `biomass_resource` | lookup yield por classe → suaviza gaussiana (`biomass_smooth_sigma`) → `normalize_percentile` (L400-431) | `biomass_smooth_sigma` (1.0), percentis, `_biomass_yields` |
| `pop_suitability` | `clip(1 − log1p(clip(pop,0,thr)) / log1p(thr), 0,1)` (L526-529) | `pop_density_threshold` — **200.0** (DECISIONS 2026-09-10, era 300.0) |
| `river_biomass` | acesso linear: `clip(1 − d/max_dist, 0,1)` (L569-571) | `river_max_dist_biomass_km` — **30.0** (ver §6, confirmado bit-exato) |
| `seismic_suitability` | `normalize_percentile(p_low=2, p_high=98)` hardcoded (L589) → `score = clip(1 − normalized, 0,1)` | percentis 2/98 |

`terrain_score` degrada para só `slope_score` se `elevation` ausente/TRI falha (L212-219). `lc_biomass` sempre se `land_cover` presente; `biomass_resource` só se `yield_raw` não-vazio (L965).

---

## 4. `roads` em critério de exclusão espacial? — **NÃO**

- `compute_road_suitability` → `compute_linear_proximity_suitability` (L263-269): score **contínuo** `[0,1]` (decaimento linear + `normalize_percentile`). Não binário, não gate.
- `exclusion.py` `common_exclusions` (`suitability_builder.py` L181-191) = `{lakes_exclusion, protected_areas, proximity_plants}`. **`road_suitability` não está lá.**
- `road_suitability` só no `priority_order` do AHP das 3 techs — peso contínuo, nunca `hard_exclusion`.

**FLAG — dependência transitiva do bug GRIP4:** `road_suitability` consome o raster `roads` alinhado, que no GeoFREA vem de `local_layers.py::resolve_roads_path()` → GRIP4, com `_ROADS_COUNTRY_REGION_DIRS` cobrindo **só BRA/PRT** (DECISIONS 2026-09-08 Fase 2). Logo `suitability_criteria` fica implicitamente **restrita a BRA/PRT** enquanto `road_suitability` for computado. Impacto **suave** (score AHP distorcido), não **binário** (nenhum pixel incluído/excluído por roads). Pré-condição, não blocker de design.

---

## 5. Exclusão IUCN de `protected` — como o legado implementa (e o que o GeoFREA faz)

`compute_protected_areas(wdpa_path, mainland_gdf, transform, width, height, crs, as_exclusion=True)` (L435-515):

1. Rasteriza `mainland_gdf.unary_union` → `mainland_mask` (L449-455).
2. **Se `wdpa_path` None / inexistente / dir sem `.shp`:** `score[mainland] = 1.0`, retorna (L458-472). **Sem WDPA a fase não falha — assume tudo livre.**
3. Se dir: escolhe candidato por glob `*polygon*.shp` → `*_0.shp` → primeiro `.shp` sem "point" (L463-472).
4. `read_file → to_crs → intersects(mainland_union) → intersection(mainland_union)` → descarta vazios (L475-482).
5. Detecta coluna IUCN entre `["IUCN_CAT","iucn_cat","IUCN","DESIGNATION"]` (L484-487).
6. `_score = map(IUCN_SCORES.get(cat, IUCN_SCORE_DEFAULT))` (L489-492).
7. **Se `as_exclusion`:** `_score = 0.0` onde categoria ∈ `{"ia","ib","ii"}` (L493-495).
8. Sem coluna IUCN → `_score = 0.25` para todos (L497).
9. Ordena por `_score desc`, rasteriza sobre base `1.0` (L499-509).
10. `score[mainland] = temp[mainland]`. Exceção → fallback `1.0` + warning (L511-514).

**`IUCN_SCORES` (`constants.py` L179-193):** `ia`/`ib`=0.00, `ii`=0.10, `iii`=0.25, `iv`=0.30, `v`=0.45, `vi`=0.55, `not reported`/`not assigned`=0.25, `not applicable`=0.45. `IUCN_SCORE_DEFAULT`=0.25, `IUCN_FREE_SCORE`=1.00.

**Decisão GeoFREA (DECISIONS 2026-09-10):** máscara binária — `categoria ∈ {ia,ib,ii} → 0.0`, resto → `1.0`. `iucn_category_scores` descartado como código morto (o threshold `0.99` da Fase 3 já o tornava inerte no legado). `protected` continua `provenance='local_only'`, gated por `PROTECTED_PLANET_API_TOKEN` manual → o contrato trata `protected` como **opcional** e replica o comportamento "sem WDPA → tudo livre (1.0)" do legado (L458-459), para que a ausência do token não mude resultado científico silenciosamente. Detalhe já em `data_quality_audit`: o `attribute_breakdown` por categoria IUCN já existe; `IUCN_SCORES` nunca foi portado (pertencia a esta fase — e agora foi descartado).

---

## 6. Decisões metodológicas — status pós-calibração 2026-09-10

Convenção do Passo 4 de `grid_alignment` (cada item = um veredito em `DECISIONS.md`). Todas resolvidas na entrada `DECISIONS.md` 2026-09-10 "suitability_criteria parameter calibration".

| # | Item | Local | Veredito 2026-09-10 |
|---|---|---|---|
| M1 | Pesos `terrain_score` slope/TRI `0.6/0.4` | L216 | STRUCTURAL_PRESERVE — sem fonte, calibração do autor |
| M2 | `TRI_THRESHOLD = 50.0` | constants L202 | STRUCTURAL_PRESERVE — sem fonte |
| M3 | Fallback `slope_threshold_deg` `7.0°` na função | L176 | não portado — GeoFREA usa constantes fixas (M18), sem fallback literal |
| M4 | `proximity_plants` score neutro `0.3` sem usinas | L346 | STRUCTURAL_PRESERVE — sem fonte |
| M5 | `PROXIMITY_DECAY_SIGMA_KM = 10.0` | constants L172 | STRUCTURAL_PRESERVE — sem fonte |
| M6 | `PROXIMITY_SMOOTH_SIGMA_PX = 2.0` | constants L173 | STRUCTURAL_PRESERVE — sem fonte |
| M7 | Percentis roads/grid/plants `5/95` hardcoded | L258, L349 | mantido `5/95` — parametrizado no contrato (§8a) |
| M8 | Percentis seismic `2/98` hardcoded | L589 | mantido `2/98` — parametrizado no contrato (§8a) |
| M9 | `IUCN_SCORES` — mapa categoria→score | constants L179 | **descartado** (código morto, ver §5 / M10) |
| M10 | `protected_areas_threshold = 0.99` torna M9 inócuo | schemas L396 | **resolvido** — máscara binária, sem tabela graduada |
| M11 | Conjunto exclusão estrita IUCN `{ia,ib,ii}` | L494 | **ratificado** (DECISIONS 2026-08-19, decisão de Douglas) |
| M12 | `river_safety_buffer_km = 0.5` (setback solar/wind) | L574 | **resolvido** — fixo `0.5` (500m), referência explícita: teto do Código Florestal BR (Lei 12.651/2012, Art. 4); promovido a hard exclusion |
| M13 | `river_max_dist_biomass_km` divergência default (10 função / 30 schema) | L569 vs schemas L387 | **resolvido — `30.0`**, confirmado bit-exato contra baseline PRT (2026-09-10) |
| M14 | `road_max_dist_km` divergência default (5 função / 15 schema) | L269 vs schemas L388 | **resolvido — `15.0`**, confirmado bit-exato contra baseline PRT (2026-09-10) |
| M15 | `pop_density_threshold` + forma `log1p` | L525-529 | **resolvido — `200.0`** (era 300; ~193/km² é o comparável de exclusão US solar). Forma `log1p` mantida sem fonte, não sinalizada como problemática |
| M16 | `biomass_smooth_sigma = 1.0` | L417 | STRUCTURAL_PRESERVE — sem fonte |
| M17 | `ren_fuels = ["solar","wind","biomass","waste"]` | L316 | mantido — `waste` conta como renovável no `proximity_plants` (sem fonte, mas sem impacto de exclusão) |
| M18 | `slope_offset_{tech}_deg` `5/10/20` | schemas L398-400 | **resolvido** — substituído por constantes fixas cross-country: **solar `5.0`, wind `25.0`, biomass `15.0`** (exclusão acima). Fonte: cutoff solar 5° e faixa favorável de vento 15–25° / inapto >25° na literatura de GIS siting suitability (busca 2026-09-10, não revisão sistemática); biomassa `15.0` interpolado, sem fonte direta. Offset aditivo do legado (`base + 5/10/20`) sem citação, descartado |
| M19 | Interpolação/vmax condicional por critério na cartografia | L703-710 | STRUCTURAL_PRESERVE trivial — sem impacto científico |

### 6a. Verificação empírica M13/M14 (2026-09-10)

Reimplementação linha-a-linha de `compute_road_suitability` / `compute_river_suitability(tech="biomass")` / `normalize_percentile`, inputs `$GEOWORLD_BASELINE_DIR/geoworld_framework/data/processed/PRT/PRT_{roads,rivers}_aligned.tif` (518×333, 93 149 px válidos, casando exatamente com o output congelado), comparação pixel-a-pixel contra `outputs_baseline_fc7b43d/PRT/criteria_builder/tif/{road_suitability,river_biomass}.tif`:

- **`river_max_dist_biomass_km`:** `30.0` → `max|Δ|=0`, RMSE `0`, 93 149/93 149 pixels bit-idênticos. `10.0` → `max|Δ|=0.470`, RMSE `0.102` (grosseiro). Confirmação direta: `river_biomass.tif` congelado tem `min = 0.7652`; distância máxima a rio em PRT = 7.0434 km; `1 − 7.0434/30 = 0.7652` exato, `1 − 7.0434/10 = 0.296`.
- **`road_max_dist_km`:** estatísticas de resumo idênticas para `5.0` e `15.0` (a `normalize_percentile` pós-decaimento mascara o efeito no relatório de texto). Pixel-a-pixel: **só `15.0` dá `max|Δ|=0` em todos os 93 149 pixels**; `5.0` deixa metade dos pixels com desvio ~1e-7 (assinatura de fórmula diferente, não de mesma computação). Varridos 10 valores (2/5/7/10/12/15/20/25/50/100) — só `15.0` bit-exato.

Ambos: o valor que gerou o baseline é o **default do schema `CountryParams`** (`15.0` / `30.0`), **não** o fallback literal da assinatura das funções (`5.0` / `10.0`). Os fallbacks de assinatura são código morto divergente — não portados.

---

## 7. Débito técnico e acoplamento

| # | Item | Evidência | Ação no contrato GeoFREA |
|---|---|---|---|
| D1 | **Dead params em `run()`** | `rivers_path`, `lakes_path`, `seismic_path` (L836-838) declarados, `main.py` os passa (L701-703), nunca usados | Não portar. O contrato recebe só o que usa. |
| D2 | **Input de 2 fases anteriores** | `aligned` (grid_alignment) + `wdpa_path`/`plants_df`/`mainland_gdf` (acquisition/bootstrap) | Contrato declara dupla dependência: `prior_results["grid_alignment"].output` **e** `prior_results["data_acquisition"].output`. Precedente: `data_quality_audit` já lê `prior_results["data_acquisition"]`. |
| D3 | **`ParamsLike = Union[CountryParams, dict]` + `_param()`** | L70, L115-117, ~12 call sites | Cruft de migração. GeoFREA usa `CountryParams` tipado direto. Não portar. |
| D4 | **`aligned` aceito como `AlignedLayers` OU dict** | L847-850 | GeoFREA recebe `GridAlignmentResult` tipado. |
| D5 | **`ref_path` = "primeiro path que existe"** | L854-856 | Usar `GridAlignmentResult.grid_metadata` (`GridMetadata`, CRS/transform/shape canônicos), não redescobrir de um raster arbitrário. |
| D6 | **`criteria: Dict[str, np.ndarray]` persistido via pickle** | `CriteriaResult` L538 | Retornar **só paths** (`tif/`); a Fase 3 relê do disco (já é o que `suitability_builder.py` L314-316 faz). |
| D7 | **`_plot_criterion_map` não migrado para `render_raster_map`** | `KNOWN DEBT (DUP_22_pending)` L624-639 | **Decisão 2026-09-10:** a cartografia da Fase 2b fica **isolada** por ora — `_plot_criterion_map` é reimplementado no próprio módulo, **sem** estender o renderer genérico para os 3 casos especiais (overlay protected, vmax condicional, stats strip). Reavaliar apenas se/quando um segundo consumidor precisar do mesmo comportamento. |
| D8 | **`write_criteria_summary` bespoke** | `reporting.py` L299 | GAP-004 — usar a convenção de report por fase do GeoFREA. |
| D9 | **`compute_protected_areas` rasteriza vetor em runtime** | L449-455, L475 | Reaproveitar `read_clipped_to_country()` + cache por país/camada (convenção de large-file), não reimplementar o clip. |
| D10 | **`os.environ` mutado em import-time** | L64-65 | Mover para setup explícito / context manager. |
| D11 | **`slope` e `land_cover` usados cru na Fase 3** | `exclusion.py` L100-110 | Não é débito da 2b, mas o contrato deixa claro: `terrain_score`/`lc_biomass` **não** são os gates de slope/LC — a Fase 3 relê os rasters alinhados. |
| D12 | **Escrita direta em `outputs/` sem artifact manager tipado** | `_save_criterion` L103 | Canonizar via convenção de path de saída por fase. |

Nenhum caso de **escrita** em `prior_results` ou mutação de output de fase anterior. O acoplamento é de *leitura multi-fase* (D2), não de violação read-only.

---

## 8. Contrato de schema proposto (Pydantic) — revisado 2026-09-10

> **NÃO implementado.** Este é o contrato-alvo. Reflete `DECISIONS.md` 2026-09-10 "suitability_criteria parameter calibration". Aguardando autorização para implementar.

Segue o padrão de `GridAlignmentResult` / `AuditResult` (`ConfigDict(extra="forbid")`; só paths, sem arrays numpy no output).

### 8a. Parâmetros

Todos os parâmetros desta fase moram em `config/parameters.json`, validados por schema Pydantic em `src/geofrea/core/` (`CONVENTIONS.md` §Parameters). **Nenhum valor fixo em `core/constants.py`** — a proposta anterior de constantes cross-country foi descartada (decisão de Douglas, 2026-09-10): um valor fixo cross-country continua sendo um *parâmetro*, apenas não aninhado por país.

**Novo bloco top-level `criteria` em `parameters.json`** — schema `CriteriaParams` novo, **paralelo a `countries`** em `ParametersFile` (não dentro de `CountryParams`, não por país). Resolve a pendência §9.2. Cada valor carrega o bloco de verificação padrão (`CONVENTIONS.md` §Parameter verification metadata).

Os 7 valores de calibração cross-country da entrada `DECISIONS.md` 2026-09-10:

```json
{
  "criteria": {
    "slope_threshold_deg_solar": {
      "value": 5.0,
      "source": "DECISIONS.md 2026-09-10 - suitability_criteria parameter calibration (GIS siting suitability literature: solar 5 deg cutoff; search 2026-09-10, not systematic review)",
      "verified": false, "verified_by": null, "verified_date": null,
      "verification_method": "unverified"
    },
    "slope_threshold_deg_wind": {
      "value": 25.0,
      "source": "DECISIONS.md 2026-09-10 - suitability_criteria parameter calibration (GIS siting suitability literature: wind 15-25 deg favorable, >25 deg unsuitable)",
      "verified": false, "verified_by": null, "verified_date": null,
      "verification_method": "unverified"
    },
    "slope_threshold_deg_biomass": {
      "value": 15.0,
      "source": "DECISIONS.md 2026-09-10 - suitability_criteria parameter calibration (interpolated between solar/wind, no direct source)",
      "verified": false, "verified_by": null, "verified_date": null,
      "verification_method": "unverified"
    },
    "river_safety_buffer_km": {
      "value": 0.5,
      "source": "DECISIONS.md 2026-09-10 - suitability_criteria parameter calibration (upper bound of Brazil Codigo Florestal, Lei 12.651/2012 Art. 4, riparian buffer scale; no consistent cross-country standard, checked BR/PT/IN/PH/US)",
      "verified": false, "verified_by": null, "verified_date": null,
      "verification_method": "unverified"
    },
    "pop_density_threshold": {
      "value": 200.0,
      "source": "DECISIONS.md 2026-09-10 - suitability_criteria parameter calibration (~193/km2 comparable US solar-siting exclusion threshold)",
      "verified": false, "verified_by": null, "verified_date": null,
      "verification_method": "unverified"
    },
    "road_max_dist_km": {
      "value": 15.0,
      "source": "DECISIONS.md 2026-09-10 - suitability_criteria parameter calibration; pixel-exact regression vs outputs_baseline_fc7b43d/PRT",
      "verified": true, "verified_by": "Douglas", "verified_date": "2026-09-10",
      "verification_method": "automated"
    },
    "river_max_dist_biomass_km": {
      "value": 30.0,
      "source": "DECISIONS.md 2026-09-10 - suitability_criteria parameter calibration; pixel-exact regression vs outputs_baseline_fc7b43d/PRT",
      "verified": true, "verified_by": "Douglas", "verified_date": "2026-09-10",
      "verification_method": "automated"
    }
  }
}
```

Demais parâmetros da fase — **no mesmo bloco `criteria`**, herdados do legado sem disputa ou marcados STRUCTURAL_PRESERVE em §6 (todos `verified: false`, `verification_method: "unverified"`, `source` apontando para `DECISIONS.md` 2026-09-10 ou "legacy criteria_builder.py, inherited unchanged"):

| campo | value | nota |
|---|---|---|
| `normalization_min_percentile` / `_max_percentile` | 5.0 / 95.0 | M7 — solar/wind/biomass resource |
| `seismic_percentile_low` / `_high` | 2.0 / 98.0 | M8 |
| `linear_proximity_percentile_low` / `_high` | 5.0 / 95.0 | M7 — roads/grid/plants |
| `grid_max_dist_km` | 20.0 | legado, não disputado |
| `terrain_slope_weight` / `terrain_tri_weight` | 0.6 / 0.4 | M1 |
| `tri_threshold_m` | 50.0 | M2 |
| `proximity_decay_sigma_km` | 10.0 | M5 |
| `proximity_smooth_sigma_px` | 2.0 | M6 |
| `proximity_plants_neutral_score` | 0.3 | M4 — país sem usinas |
| `renewable_fuel_labels` | `["solar","wind","biomass","waste"]` | M17 |
| `biomass_smooth_sigma` | 1.0 | M16 |
| `solar_pvout_weight` | 1.0 | legado |
| `protected_as_exclusion` | `true` | legado — liga/desliga a zeragem das 3 categorias estritas |
| `iucn_strict_categories` | `["ia","ib","ii"]` | M11 — `verified: true`, `verification_method: "manual_cross_check"`, `verified_by: "Douglas"`, `verified_date: "2026-08-19"`, `source: "DECISIONS.md 2026-08-19 - protected_areas / IUCN exclusion categories (author decision, no external citation)"` |

`iucn_category_scores` — **REMOVIDO** (código morto, ver §5 / M9 / M10).
`slope_offset_solar_deg` / `slope_offset_wind_deg` / `slope_offset_biomass_deg` (5/10/20) — **REMOVIDOS** do schema (substituídos por `slope_threshold_deg_{solar,wind,biomass}` fixos acima).

**Tabelas de critério** (dois campos, ambos tabela — não escalares):

| campo | onde | tipo | natureza |
|---|---|---|---|
| `land_suitability` | bloco global `CriteriaParams` | `dict[int, LandCoverSuitability]` — classe ESA → `{solar, wind, biomass}` scores | **lógica de siting, não dado geográfico** — mesma tabela para todo país (ex. `Grassland → biomass 0.9` vale em PRT e BRA). Feed direto de `lc_biomass` (só a coluna `biomass` é lida na Fase 2b; `solar`/`wind` usados na Fase 3). |
| `yield_by_land_cover` | **campo direto em `CountryParams`** (não em `technologies.biomass`, não em sub-model `criteria`) | `dict[int, float]` — classe ESA → yield de biomassa | **dado geográfico real por país** — confirmado divergente nos 5 países do legado (PRT/BRA/EGY/IND/RUS): produtividade por bioma/clima. Feed direto de `biomass_resource`. |

`LandCoverSuitability`: `{solar: float, wind: float, biomass: float}` (+ `description: str` opcional, cartográfico). Colunas em `[0, 1]`.

**Verificação de tabela** (nota de schema): o bloco de verificação (`CONVENTIONS.md` §Parameter verification metadata) é **agregado — a tabela inteira é uma unidade**, não uma célula. Um único `{source, verified, verification_method, ...}` cobre `land_suitability` como um todo, e um por país cobre cada `yield_by_land_cover`. Reabrir granularidade célula-a-célula só se algum valor específico virar prioridade de recalibração.

- `land_suitability`: `verified: false`, `verification_method: "unverified"`, `verified_by: null`, `verified_date: null`, `source: "legacy geoworld_framework @ fc7b43d — configs/parameters.json land_suitability (top-level, global; inherited unchanged)"`.
- `yield_by_land_cover` (por país): `verified: false`, `verification_method: "unverified"`, `verified_by: null`, `verified_date: null`, `source: "legacy geoworld_framework @ fc7b43d — configs/parameters.json countries.{ISO3}.biomass.yield_by_land_cover (inherited unchanged; 5 countries confirmed: PRT/BRA/EGY/IND/RUS)"`.

Sub-model `CountryParams.criteria` **não é criado agora** — `yield_by_land_cover` é o único parâmetro de critério per-country, e um campo só não justifica o wrapper. O nome `CountryParams.criteria` fica **reservado** para quando aparecer um segundo parâmetro per-country de critério.

`compute_protected_areas` (contrato revisado): `categoria.lower().strip() ∈ criteria.iucn_strict_categories → 0.0`; qualquer outra feição WDPA → `1.0`; território livre → `1.0`; sem WDPA → `1.0` em todo o mainland (comportamento do legado L458-459 preservado). Sem `IUCN_SCORES`, sem ordenação por score, sem ramo `as_exclusion=False` com tabela graduada (`as_exclusion` só liga/desliga a zeragem das categorias estritas).

### 8b. Output — `SuitabilityCriteriaResult`

```python
class CriterionLayer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str                       # ∈ os 14 nomes canônicos
    tif_path: Path                  # outputs/{ISO3}/suitability_criteria/tif/{name}.tif
    figure_path: Path | None        # None se skip_maps
    # (campo `kind` REMOVIDO — DECISIONS.md 2026-09-10 ponto 6)
    valid_pixels: int
    mean: float
    std: float
    p10: float
    p50: float
    p90: float
    frac_ge_0_6: float              # fração com score >= 0.6 (métrica do log legado)

class SuitabilityCriteriaSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n_criteria: int
    missing_expected: list[str]     # dos 14 esperados, os não gerados
    protected_source: Literal["wdpa", "assumed_free"]   # replica L458-459
    grid_metadata: GridMetadata     # ecoado de grid_alignment, prova de mesma grade

class SuitabilityCriteriaResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    country_code: str
    timestamp: str
    tif_dir: Path
    figure_dir: Path
    report_path: Path
    criteria: dict[str, CriterionLayer]   # keyed por name; SEM arrays numpy (D6)
    slope_degrees_tif: Path | None        # artefato cartográfico à parte, fora de `criteria`
    summary: SuitabilityCriteriaSummary

    @model_validator(mode="after")
    def _summary_consistent(self):
        if self.summary.n_criteria != len(self.criteria):
            raise ValueError(...)
        return self
```

**14 nomes canônicos** (Literal/Enum): `solar_resource, wind_resource, terrain_score, lc_biomass, biomass_resource, protected_areas, pop_suitability, road_suitability, lakes_exclusion, river_solar, river_wind, river_biomass, seismic_suitability, grid_suitability`.

### 8c. Dependências de fase declaradas (D2)

```
suitability_criteria consome:
  prior_results["grid_alignment"].output   -> GridAlignmentResult (12 rasters + grid_metadata)
  prior_results["data_acquisition"].output -> path do WDPA (opcional, gated por token),
                                              registry de power_plants, borders/mainland
  config: parameters.json bloco global `criteria` (CriteriaParams, novo — §8a),
          incluindo a tabela `land_suitability` (lógica de siting, global)
          CountryParams.yield_by_land_cover (campo direto, tabela por país —
            único param per-country desta fase; SEM sub-model CountryParams.criteria)
```

### 8d. `common_exclusions` da Fase 3 (documentado aqui, implementar só em `suitability_builder`)

`DECISIONS.md` 2026-09-10 ponto 7: adicionar `river_solar` e `river_wind` à lista existente. Lista-alvo da Fase 3:

```
common_exclusions = {
    "lakes_exclusion":   0.5,     # legado (inerte, critério já {0,1})
    "protected_areas":   0.99,    # legado — com máscara binária, exclui toda feição WDPA
    "proximity_plants":  0.01,    # legado
    "river_solar":       0.5,     # NOVO — setback de segurança, era só priority_order
    "river_wind":        0.5,     # NOVO — idem
}
```

`river_biomass` **não** entra em `common_exclusions` (continua critério contínuo — acesso, não setback). O gate de slope na Fase 3 passa a usar `SLOPE_MAX_DEG_{SOLAR,WIND,BIOMASS}` direto (sem `base + offset`).

---

## 9. Pendências antes de implementar

Nenhuma pendência de design em aberto — as 4 originais foram resolvidas:

1. **Placement dos valores fixos cross-country** — resolvido: bloco top-level `criteria` em `parameters.json` (schema `CriteriaParams`, paralelo a `countries`), não `core/constants.py`. Ver §8a.
2. **`_TechnologyCriteriaParams` vs. bloco `criteria`** — resolvido: bloco `criteria` global (não per-country, não em `CountryParams`). Ver §8a.
3. **D7 (renderer genérico)** — resolvido: cartografia da 2b fica isolada, sem estender `render_raster_map`. Ver §7 linha D7.
4. **Baseline de regressão pixel-a-pixel da 2b no CI** — registrado como **débito técnico em aberto** em `DECISIONS.md` 2026-09-10 ("open tech debt: suitability_criteria pixel-exact regression harness"). **Não** bloqueia a implementação desta fase — o harness pode ser adicionado depois.
