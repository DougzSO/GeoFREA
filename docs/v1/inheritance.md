# GeoFREA v1 to v2: inheritance table

One row per item of the v1 registers that holds in v2 (classes a: valid as it was, b: valid with revision). Items that only describe v1 (class c, historical) and the items that the double check of COMMAND 304 demoted are listed by ID at the end. Destination is the v2 document that now carries the item. The text of v1 is in the tags `v1.0`, `v1.1` and `v1-final` (`git show v1.1:<path>`).

The classification was made by rule and then checked by two automatic passes: (1) every item `a` or `b` was scanned for retired terms (tau, satisficing, SR, regret, MR, PRIM, top-k, LHS, 4000, CMIP6, CDS, GCM selection, MIROC6, ACCESS, CNRM, cf_min, q_ref) and the ones that only describe v1 were demoted to `c`; (2) the decisions DEC-035 to DEC-041 (v1 numbering, by position of the header) were checked one by one against the current code (Section 5).

How to read the decision table: a v1 decision is implemented in code and recorded in the phase record of its area (`docs/phases/`, D- items with their original IDs) and in the METHODOLOGY item of the same area; the area is the v2 module or group.

## 1. Method items (M-)

| v1 ID | Summary | Destination in v2 | What changed |
|---|---|---|---|
| M-F1-01 | Layer registry with provenance per layer: provenance in {fetched, local_only} and compute | METHODOLOGY M-F1-01 | F1 fica; entra ISIMIP3b (305); CMIP6 do CDS sai com o F4 da v1 |
| M-F1-02 | Active layers: country borders and admin1 (GADM 4.1), protected areas (WDPA via Protected… | METHODOLOGY M-F1-02 | F1 fica; entra ISIMIP3b (305); CMIP6 do CDS sai com o F4 da v1 |
| M-F1-03 | Global Wind Atlas products at hub-relevant heights 100, 150, 200 m: combined-Weibull-A, c… | METHODOLOGY M-F1-03 | F1 fica; entra ISIMIP3b (305); CMIP6 do CDS sai com o F4 da v1 |
| M-F1-05 | ERA5 gust reanalysis (scenario-invariant extreme-wind indicator), built fresh (CRAEI's ow… | METHODOLOGY M-F1-05 | unchanged in substance (wording condensed) |
| M-F1-06 | Existing solar and wind plants from Global Energy Monitor trackers, used only in F7b. Nev… | METHODOLOGY M-F1-06 | GEM: passa de validação (só F7b) a insumo da frota (M1); regra V-06 muda |
| M-F1-07 | GADM borders resolve local-first with checksum; network download is a fallback. | METHODOLOGY M-F1-07 | F1 fica; entra ISIMIP3b (305); CMIP6 do CDS sai com o F4 da v1 |
| M-F1b-01 | Audit every active layer: coverage, nodata share, value ranges, resolution, CRS. Expected… | METHODOLOGY M-F1b-01 | unchanged in substance (wording condensed) |
| M-F1b-02 | The audit's findings never block execution: an anomaly is reported, not enforced. The aud… | METHODOLOGY M-F1b-02 | unchanged in substance (wording condensed) |
| M-F2a-01 | Analysis grid: EPSG:4326, fixed 0.01 degree resolution, snapped so that 0.05 degree cells… | METHODOLOGY M-F2a-01 | unchanged in substance (wording condensed) |
| M-F2a-02 | All distances and areas are geodesic (core/geodesy.py), including slope derivation from t… | METHODOLOGY M-F2a-02 | unchanged in substance (wording condensed) |
| M-F2a-03 | Distance rasters to the transmission grid, roads, rivers and substations store the uncapp… | METHODOLOGY M-F2a-03 | unchanged in substance (wording condensed) |
| M-F2a-04 | Wind products are aligned per height; no combination across heights happens in F2a. | METHODOLOGY M-F2a-04 | unchanged in substance (wording condensed) |
| M-F2a-05 | Layers that hold counts (population) are brought to the analysis grid by summing the sour… | METHODOLOGY M-F2a-05 | unchanged in substance (wording condensed) |
| M-F2a-06 | Land cover enters F3 as class counts, not as one class per pixel: for every grid pixel, t… | METHODOLOGY M-F2a-06 | unchanged in substance (wording condensed) |
| M-F2a-07 | Slope enters F3 as a distribution, not a pixel mean: the FABDEM V1-2 tiles (30 m; Coperni… | METHODOLOGY M-F2a-07 | unchanged in substance (wording condensed) |
| M-F2a-08 | The aligned elevation is the mean of the 30 m Copernicus GLO-30 samples inside each grid… | METHODOLOGY M-F2a-08 | unchanged in substance (wording condensed) |
| M-F2a-09 | Point of interconnection (Group 3, docs/thesis/methods/group3_connection_degradation.tex). | METHODOLOGY M-F2a-09 | unchanged in substance (wording condensed) |
| M-F2a-10 | Road classes. The distance to the road (roads) is the distance to a primary or secondary… | METHODOLOGY M-F2a-10 | unchanged in substance (wording condensed) |
| M-F2a-11 | Settlements (Group 6, docs/thesis/methods/group6_land_eligibility.tex). settlements is the | METHODOLOGY M-F2a-11 | unchanged in substance (wording condensed) |
| M-F2b-01 | Exclusion terms per technology, each the excluded share of a pixel in [0, 1] (1 = fully e… | METHODOLOGY M-F2b-01 | unchanged in substance (wording condensed) |
| M-F2b-02 | Cost-driver layers: distance to transmission grid (km; every OSM line and substation, any… | METHODOLOGY M-F2b-02 | unchanged in substance (wording condensed) |
| M-F2b-03 | Resource layers: solar PVOUT (kWh/kWp/day); wind Weibull A (m/s), Weibull k (-), and air… | METHODOLOGY M-F2b-03 | unchanged in substance (wording condensed) |
| M-F2b-04 | No normalization, weighting, or scoring of any layer. Values keep physical units. | METHODOLOGY M-F2b-04 | unchanged in substance (wording condensed) |
| M-F2b-05 | Fail-loud on integrity failures of present files (corrupted tiles, invalid WDPA files). A… | METHODOLOGY M-F2b-05 | unchanged in substance (wording condensed) |
| M-F2b-06 | The parameters of E1-E6 and the minimum eligible area are declared in config/experiments.… | METHODOLOGY M-F2b-06 | unchanged in substance (wording condensed) |
| M-F3-01 | Pixel eligibility per technology: the eligible share of a pixel is valid * (1 - E1) * (1… | METHODOLOGY M-F3-01 | unchanged in substance (wording condensed) |
| M-F3-02 | Eligibility is computed for the three named land-availability scenarios of U-06 (central,… | METHODOLOGY M-F3-02 | unchanged in substance (wording condensed) |
| M-F3-03 | Cell aggregation to 0.05 degree (5 x 5 pixels). Per cell and technology: | METHODOLOGY M-F3-03 | unchanged in substance (wording condensed) |
| M-F3-04 | A cell enters the candidate set if eligible_area_km2 > 0, it has an elevation and, for a… | METHODOLOGY M-F3-04 | unchanged in substance (wording condensed) |
| M-F3-05 | Outputs: candidates_<tech>.parquet (one row per candidate cell, stable cell_id, with admin | METHODOLOGY M-F3-05 | unchanged in substance (wording condensed) |
| M-F3-06 | The cell size is a parameter of the run, scale (0.05 degree, 5 x 5 pixels, the default; o… | METHODOLOGY M-F3-06 | unchanged in substance (wording condensed) |
| M-F3-07 | Minimum eligible area (Group 6). Eligible pixels (fraction above 0) are grouped into clus… | METHODOLOGY M-F3-07 | unchanged in substance (wording condensed) |
| M-F4-01 | Climate members m = (gcm, ssp, window), plus the reference member m0 with no change. | METHODOLOGY M-F4-01 | membros viram 15 (5 modelos x 3 SSP) por janela |
| M-F4-03 | Change factors (delta-change), computed on each GCM's native grid from monthly climatolog… | METHODOLOGY M-F4-03 | delta-change: conceito fica, entra a mudança relativa da vazão |
| M-F4-04 | Change factors are bilinearly interpolated to the cell centers of the run scale (0.05 deg… | METHODOLOGY M-F4-04 | unchanged in substance (wording condensed) |
| M-F4-05 | Hazard channels (D15 rule): | METHODOLOGY M-F4-05 | canais de extremos: exposição a extremos entra no M3 |
| M-F4-06 | Outputs: forcing.parquet (cell_id, member, delta_rsds, dT, delta_wind, dT_isolated | METHODOLOGY M-F4-06 | forcing.parquet muda de esquema (membros, vazão) |
| M-F4-07 | Validity mask for the wind factor: a cell-member whose delta_wind lies outside wind_facto… | METHODOLOGY M-F4-07 | máscara de validade do vento: faixa sem fonte (OQ-043), revisar |
| M-F5-01 | Capacity per cell: P_MW = eligible_area_km2 * LUF[tech, scenario] * PD[tech, scenario], w… | METHODOLOGY M-F5-01 | potencial fica; CF por membro climático novo |
| M-F5-02 | Solar capacity factor: | METHODOLOGY M-F5-02 | potencial fica; CF por membro climático novo |
| M-F5-03 | Wind capacity factor: | METHODOLOGY M-F5-03 | potencial fica; CF por membro climático novo |
| M-F5-05 | Annual energy: E_m = P_MW * CF_m * 8760 (MWh/yr; the hours per year are a constant in geo… | METHODOLOGY M-F5-05 | potencial fica; CF por membro climático novo |
| M-F5-06 | Outputs, one file per technology and land-availability scenario: potential_<tech>__<scena… | METHODOLOGY M-F5-06 | potencial fica; CF por membro climático novo |
| M-F5-07 | Maps of the potential, drawn by the phase potential_maps at the reference climate (member… | METHODOLOGY M-F5-07 | potencial fica; CF por membro climático novo |
| M-F6-01 | LCOE kernel, vectorized over cells, for member m and parameter vector theta: | METHODOLOGY M-F6-01 | kernel do LCOE fica; só nominal e faixas; sem LHS de 4000 |
| M-F6-05 | The kernel is a pure function importable by F7. | METHODOLOGY M-F6-05 | unchanged in substance (wording condensed) |
| M-F6-06 | Outputs: lcoe_summary_<tech>.parquet, design_matrix_<tech>.parquet, supply curves per mem… | METHODOLOGY M-F6-06 | kernel do LCOE fica; só nominal e faixas; sem LHS de 4000 |
| M-F6-07 | Technology vintage and cost parameters. The reference commissioning year is t_ref = 2024… | METHODOLOGY M-F6-07 | kernel do LCOE fica; só nominal e faixas; sem LHS de 4000 |
| M-F6-08 | External connection cost (Group 3). The plant capital cost covers everything inside the p… | METHODOLOGY M-F6-08 | kernel do LCOE fica; só nominal e faixas; sem LHS de 4000 |
| M-F6-09 | Degradation (Group 3). Energy declines geometrically (M-F6-01). The rate of a cell and sa… | METHODOLOGY M-F6-09 | kernel do LCOE fica; só nominal e faixas; sem LHS de 4000 |
| M-F6-10 | Losses, failure rules and sensitivities (Group 3). Transmission losses are not modelled i… | METHODOLOGY M-F6-10 | kernel do LCOE fica; só nominal e faixas; sem LHS de 4000 |
| M-F6-11 | Range of the discount rate (DEC-072, DEC-082 a). For each country and technology the rang… | METHODOLOGY M-F6-11 | faixa de WACC fica como faixa dos totais; calibração ao IRENA para τ sai |
| M-F6-12 | Basis of the IRENA values (DEC-087). The IRENA 2024 solar TIC is per kW DC and its solar… | METHODOLOGY M-F6-12 | base IRENA DC/AC fica para as faixas de custo |
| M-F7-13 | Pre-registration guard (DEC-081 g, D-F7-065, L-244). lcoe_modeling, sample_size_convergen… | METHODOLOGY M-F7-13 | guarda de pré-registro: generaliza para prereg-v2 |
| M-F7b-01 | Share of existing plant capacity (GEM trackers) located in excluded pixels, per exclusion… | METHODOLOGY M-F7b-01 | unchanged in substance (wording condensed) |
| M-F7b-02 | Enrichment ratio: share of existing capacity in the lowest nominal-LCOE deciles divided b… | METHODOLOGY M-F7b-02 | unchanged in substance (wording condensed) |
| M-F7b-03 | Comparison of national technical potential with published estimates, as a table with sour… | METHODOLOGY M-F7b-03 | unchanged in substance (wording condensed) |
| M-F7b-04 | Existing plants reflect past auctions, policy, and grid access. Results are plausibility… | METHODOLOGY M-F7b-04 | unchanged in substance (wording condensed) |
| M-F8-01 | F8 reads persisted artifacts and never recomputes a scientific quantity. The one derived… | METHODOLOGY M-F8-01 | F8 só lê artefatos; o número H1 p_k^2 sai |
| M-F8-02 | F8 produces every output of Section 10 into outputs/thesis/, with a fixed style and one s… | METHODOLOGY M-F8-02 | síntese fica; tabelas T-R da v1 saem |
| M-X-01 | Cost-to-target, H5c. Per country, technology and window; domain: the F7 set of the centra… | METHODOLOGY M-X-01 | H5c vira o custo de cobrir a lacuna (A6) |

## 2. Decisions (v1 DEC, numbered by the position of the header)

| v1 ID | Title | Area in v2 | What changed |
|---|---|---|---|
| DEC-001 | protected_areas / IUCN exclusion categories | M3 | unchanged |
| DEC-006 | discount_rate architecture fix | M3 | arquitetura de taxa de desconto e parâmetros IRENA de solar e eólica (kernel F6) |
| DEC-007 | solar and wind parameters populated (IRENA 2024/2025) | M3 | arquitetura de taxa de desconto e parâmetros IRENA de solar e eólica (kernel F6) |
| DEC-008 | settings.yaml phase toggles | INFRA | chaves de fase em settings.yaml: refletir fases da v2 |
| DEC-010 | orchestrator + data_quality_audit phase | INFRA | unchanged |
| DEC-011 | slope_threshold_deg movido para parameters.json | M3 | unchanged |
| DEC-012 | data_acquisition skeleton | DADOS | unchanged |
| DEC-013 | protected (WDPA): decisão de onde entra no GeoFREA fica pendente | DADOS | unchanged |
| DEC-014 | vector layer audit depth | DADOS | unchanged |
| DEC-015 | path/paths source-of-truth consolidation | DADOS | unchanged |
| DEC-016 | IUCN category normalization fix | DADOS | unchanged |
| DEC-017 | AuditSummary refactor to layer-keyed dict | DADOS | unchanged |
| DEC-018 | real fetchers for power_plants/wind/lakes/rivers | DADOS | unchanged |
| DEC-019 | data_acquisition activation | DADOS | unchanged |
| DEC-020 | solar (Global Solar Atlas): padrão de URL per-country decifrado | DADOS | unchanged |
| DEC-021 | seismic: fonte identificada (GEM Global Seismic Hazard Map v2023.1) | DADOS | unchanged |
| DEC-022 | seismic: fetch automatizado descartado por restrição de licença | DADOS | unchanged |
| DEC-023 | solar: unidade do PVOUT — arquivo já em uso confere, achado de risco para fetch futuro | DADOS | unchanged |
| DEC-025 | clip_vector_to_country() exact-intersection bottleneck (STRtree + simplify + threading) | DADOS | unchanged |
| DEC-026 | country_gdf=None + clip=True: incidente real de quase-OOM, guarda ClipRequiresCountryGdfE… | DADOS | unchanged |
| DEC-027 | real fetcher for borders/admin1 (GADM 4.1) + validação real end-to-end (PRT/BRA) | DADOS | unchanged |
| DEC-028 | wire das 5 camadas restantes a partir do banco local, Fase 1 (elevation/population/grid/l… | DADOS | unchanged |
| DEC-029 | wire das 5 camadas restantes a partir do banco local, Fase 2 (roads/GRIP4) + achados reai… | DADOS | unchanged |
| DEC-030 | infrastructure/grid/grid.gpkg: fonte de grid possivelmente mais completa que {ISO3}_grid_… | DADOS | unchanged |
| DEC-031 | grid_alignment (Fase 2a) portado do legado — schema, lógica, testes | M3 | unchanged |
| DEC-032 | grid_alignment orchestrator wiring — adapter + terceiro PhaseSpec | M3 | unchanged |
| DEC-033 | Passo 6: validação real PRT/BRA + correção do mismatch de land_cover (achado do Passo 3) | M3 | unchanged |
| DEC-034 | Passo 4: os 4 vereditos metodológicos de grid_alignment (Bowring, raios de busca, resoluç… | M3 | unchanged |
| DEC-040 | data_acquisition: solar (PVOUT) ganha resolver local | M3 | unchanged: resolve_solar_path in data_acquisition/local_layers.py still resolves the Global Solar Atlas file (M-F1-02) |
| DEC-042 | grid_alignment: slope não herda contaminação de nodata (correção de integridade) | M3 | unchanged |
| DEC-043 | suitability_criteria: protected_areas distingue WDPA ausente de WDPA corrompido | M3 | unchanged |
| DEC-044 | grid_alignment: reproject_to_grid sanitiza NaN literal antes do warp | M3 | unchanged |
| DEC-045 | suitability_criteria: TRI (terrain_score) não herda contaminação de NaN/nodata | M3 | unchanged |
| DEC-046 | grid_alignment: mosaic_land_cover fail-loud em tile corrompido que sobrepõe o país | M3 | unchanged |
| DEC-047 | data_acquisition: AcquiredLayer.fetch_status quebrava resume a partir de manifest.json (c… | M3 | unchanged |
| DEC-048 | slope não herda contaminação de nodata: correção de escopo (PRT vs BRA) | M3 | unchanged |
| DEC-049 | data_acquisition: protected_planet API activation | M3 | unchanged |
| DEC-050 | protected_areas: repara geometria WDPA inválida antes do clip (correção separada do fail-… | M3 | unchanged |
| DEC-051 | cartografia D7 (cartography.py::plot_criterion_map): ajustes visuais + investigação de ri… | M3 | unchanged |
| DEC-054 | rivers/roads BRA (1.8x producao vs isolado): investigacao parcial, causa ainda nao confir… | DADOS | unchanged |
| DEC-055 | regression fixtures storage: GitHub Release (opcao 1) + CI skip->fail | INFRA | investigação aberta de desempenho (rios e estradas BRA); OQ-095 |
| DEC-056 | pop_suitability: divergencia CI-only vs baseline congelado, causa raiz confirmada (ruido… | INFRA | unchanged |
| DEC-057 | addendum de rotulagem: Justificativa ausente em "protected_areas distingue WDPA ausente d… | INFRA | unchanged |
| DEC-062 | valores monetários na configuração | M3 | valores monetários na configuração |
| DEC-064 | preços de leilão | VALID | preços de leilão como referência de custo |
| DEC-065 | Group 5: exposição sem perda; canal de rajada | M3 | exposição sem perda e canal de rajada: contexto de extremos |
| DEC-066 | fato registrado: curtailment e CF_min | M3 | curtailment e CF_min: curtailment entra como item de custo espacial |
| DEC-068 | PV-77 fechada pelo autor | VALID | PV-77 fechada pelo autor |
| DEC-071 | F6: índice dos EUA para converter USD 2025 em USD 2024 (OQ-093) | M3 | unchanged |
| DEC-072 | F6/F7: faixa de WACC por país e tecnologia (OQ-089) | M3 | faixa de WACC por país e tecnologia (faixa dos totais) |
| DEC-081 | F6/F7: schema and registered subset of the pre-registration (COMMANDS 153, 154) | INFRA | esquema e subconjunto do pré-registro: base do prereg-v2 |
| DEC-084 | Pre-registration conventions derived from the field inventory (COMMAND 161B) | INFRA | convenções de pré-registro: valem para o prereg-v2 |
| DEC-091 | Verdict on the wind cell CF, branch B (closes OQ-114) (COMMANDS 170, 171) | M1/M3 | CF eólico da célula, ramo B: vale para o CF por membro |
| DEC-092 | Fleet wind CF of India derived from published statistics (complements DEC-091) | VALID | CF eólico da frota da Índia por estatística publicada |
| DEC-093 | No sourced exposure threshold: the H5b channel set of v1.0 is empty (closes OQ-051 and OQ… | M3 | sem limiar de exposição com fonte: canal H5b vazio |
| DEC-098 | Exploratory analyses after v1.0: cost-to-target (H5c) and own vulnerability (VUL) (COMMAN… | M3 | H5c e VUL: H5c redefinido na v2 |
| DEC-099 | Verdicts on the v1.0 diagnostics (D0) (COMMAND 209) | INFRA | vereditos dos diagnósticos D0: motivam a v2, resumem-se no v1_record |

## 3. Open questions (OQ-)

| v1 ID | Question | Destination | What changed |
|---|---|---|---|
| OQ-007 | Loss functions for C2 (extreme heat on PV and inverters, extreme wind cut-out and tracker… | OPEN_QUESTIONS OQ-007 | funções de perda C2 e C3: pode virar exposição a extremos no M3 |
| OQ-013 | Explorer technology stack and hosting. | OPEN_QUESTIONS OQ-013 | stack do explorer: plataforma depois da v2.0 |
| OQ-043 | Source for wind_factor_valid_range (0.5-1.5, config/experiments.yaml). The bound that mas… | OPEN_QUESTIONS OQ-043 | faixa válida do fator de vento, sem fonte; segue na v2 |
| OQ-057 | Published national technical-potential estimates for M-F7b-03. config/published_potential… | OPEN_QUESTIONS OQ-057 | unchanged |
| OQ-064 | Sensitivity of the results to the resolution of the analysis grid (spec v2 T-06, decision… | OPEN_QUESTIONS OQ-064 | sensibilidade à resolução: 0,1° vira sensibilidade documentada |
| OQ-072 | FABDEM is licensed CC BY-NC-SA 4.0 (non-commercial, share-alike): is that compatible with… | OPEN_QUESTIONS OQ-072 | unchanged |
| OQ-078 | write_annual_maxima_from_hourly hangs under the fork start method of Linux. In the unit j… | OPEN_QUESTIONS OQ-078 | unchanged |
| OQ-095 | Why the rivers and roads of BRA run about 1.8x slower in the full pipeline than in isolat… | OPEN_QUESTIONS OQ-095 | lentidão de rios e estradas na BRA |
| OQ-096 | Location of the audit report. _save_report in data_quality_audit/audit.py writes the repo… | OPEN_QUESTIONS OQ-096 | unchanged |
| OQ-097 | Layer names of the resources. land_eligibility/pipeline.py::_required_resources fixes the… | OPEN_QUESTIONS OQ-097 | unchanged |
| OQ-099 | Technologies of F1b. data_quality_audit/audit.py keeps its own tuple _TECHNOLOGIES = ("so… | OPEN_QUESTIONS OQ-099 | unchanged |
| OQ-100 | Default list of countries. main.py derives default_countries from config/parameters.json… | OPEN_QUESTIONS OQ-100 | unchanged |
| OQ-101 | Schema versions of the outputs. Only the phases F1 and F1b declare produces_schema_versio… | OPEN_QUESTIONS OQ-101 | unchanged |
| OQ-102 | Aligned raster keys of F2a. main.py fixes _ALIGNED_RASTER_LAYER_KEYS in the produces of g… | OPEN_QUESTIONS OQ-102 | unchanged |
| OQ-103 | Expectation for the slope layer. F1b removed its slope entry from config/audit.yaml (D-F1… | OPEN_QUESTIONS OQ-103 | unchanged |
| OQ-106 | ZZZ has no versioned baseline of fingerprints. The synthetic world is generated at each r… | OPEN_QUESTIONS OQ-106 | unchanged |
| OQ-117 | Flaky test: test_mapstyle_geo.py::test_neighbours_are_drawn_in_light_grey_within_the_buff… | OPEN_QUESTIONS OQ-117 | unchanged |

## 4. Limitations (L-)

| v1 ID | Statement | Destination | What changed |
|---|---|---|---|
| L-001 | Solar potential assumes free-standing plants with c-Si modules at fixed optimum tilt (Glo… | LIMITATIONS L-001 | unchanged |
| L-002 | Climate change enters through annual-mean delta-change factors; seasonal redistribution o… | LIMITATIONS L-002 | rewritten for the ISIMIP3b data or without the v1 outputs it cited |
| L-003 | Wind change factors from near-surface (10 m) sfcWind are applied at hub height, and Weibu… | LIMITATIONS L-003 | unchanged |
| L-004 | The wind capacity factor is evaluated per 0.01 degree pixel and aggregated to the cell by… | LIMITATIONS L-004 | rewritten for the ISIMIP3b data or without the v1 outputs it cited |
| L-005 | Each GCM contributes a single realization; internal variability is not sampled. | LIMITATIONS L-005 | rewritten for the ISIMIP3b data or without the v1 outputs it cited |
| L-006 | Climate of each window is held constant over the asset lifetime. | LIMITATIONS L-006 | unchanged |
| L-008 | The reference climatology (1995-2014) does not coincide with the atlas reference periods… | LIMITATIONS L-008 | rewritten for the ISIMIP3b data or without the v1 outputs it cited |
| L-009 | The transmission grid layer represents line location, not available connection capacity o… | LIMITATIONS L-009 | unchanged |
| L-010 | Exclusions E1 to E5 are shares of each pixel and E6 is binary; social acceptance and othe… | LIMITATIONS L-010 | unchanged |
| L-011 | Grid connection is costed per cell from eligible-area-weighted mean distance; shared conn… | LIMITATIONS L-011 | unchanged |
| L-012 | Uncertain parameters are sampled independently; correlations (for example between CAPEX a… | LIMITATIONS L-012 | unchanged |
| L-013 | Results depend on the 0.05 degree aggregation (modifiable areal unit problem). | LIMITATIONS L-013 | unchanged |
| L-014 | Extreme-wind context comes from ERA5 historical reanalysis and does not vary by SSP. | LIMITATIONS L-014 | rewritten for the ISIMIP3b data or without the v1 outputs it cited |
| L-015 | Hazards without Tier 1-2 loss functions are reported as context and do not affect robustn… | LIMITATIONS L-015 | rewritten for the ISIMIP3b data or without the v1 outputs it cited |
| L-016 | External validation against existing plants measures plausibility, not accuracy, because… | LIMITATIONS L-016 | unchanged |
| L-017 | The gust indicator (fg10, annual maximum, 1995-2014) is raw ERA5 reanalysis with no bias… | LIMITATIONS L-017 | rewritten for the ISIMIP3b data or without the v1 outputs it cited |
| L-018 | The grid layer is OpenStreetMap power infrastructure of any voltage (lines and points), s… | LIMITATIONS L-018 | unchanged |
| L-019 | Connection CAPEX is linear in the distance to the nearest eligible substation (c_line x t… | LIMITATIONS L-019 | rewritten for the ISIMIP3b data or without the v1 outputs it cited |
| L-048 | The connection cost is that of the radial spur, the works at the receiving substation and… | LIMITATIONS L-048 | unchanged |
| L-049 | The point of interconnection comes from OSM tags, which are incomplete. The raw extracts… | LIMITATIONS L-049 | unchanged |
| L-050 | Tortuosity is one uniform factor (1.25, range 1.2 to 1.3) for the line and for the road,… | LIMITATIONS L-050 | unchanged |
| L-051 | The unit costs exclude right of way in India and come from a higher voltage class in Port… | LIMITATIONS L-051 | unchanged |
| L-052 | Degradation rates are transferred from United States fleets (PV: Jordan et al. 2022, the… | LIMITATIONS L-052 | rewritten for the ISIMIP3b data or without the v1 outputs it cited |
| L-056 | The BRA line cost is the ANEEL modular (reference) cost per km applied in three EPE studi… | LIMITATIONS L-056 | unchanged |
| L-054 | The access road is not billed in any country in the central scenario (road_cost_excluded)… | LIMITATIONS L-054 | unchanged |
| L-055 | The BRA bay is the ANEEL BPR module Entrada de Linha 138 kV BPT: items carry their own re… | LIMITATIONS L-055 | unchanged |
| L-053 | Transmission losses are not modelled in the central case (eta_trans = 1); only the sensit… | LIMITATIONS L-053 | unchanged |
| L-020 | RETIRED 2026-11-05 (COMMAND 97): it described a candidate set that rested on a Tier 3 pop… | LIMITATIONS L-020 | unchanged |
| L-025 | Wind candidates above the altitude limit of the scenario (elevation_max_m of land_availab… | LIMITATIONS L-025 | unchanged |
| L-026 | dT is kept as the GCM gives it: three of the 36 members have cells with a negative dT ove… | LIMITATIONS L-026 | rewritten for the ISIMIP3b data or without the v1 outputs it cited |
| L-027 | The reference density of the IEA 3.4-130 power table (rho0 = 1.225 kg/m3, verified = fals… | LIMITATIONS L-027 | unchanged |
| L-028 | One class III turbine (3.37 MW, rotor about 130 m, specific power about 254 W/m2) is appl… | LIMITATIONS L-028 | unchanged |
| L-029 | The residual land-utilization factor has no primary source in any country and dominates t… | LIMITATIONS L-029 | unchanged |
| L-030 | PV power density (45 / 50 / 75 MW_dc/km2) is transferred from United States plants of 201… | LIMITATIONS L-030 | unchanged |
| L-031 | The PV yield is the fixed-tilt PVOUT baseline perturbed with annual means (CF0 delta_rsds… | LIMITATIONS L-031 | unchanged |
| L-032 | Wind air density uses one annual mean per cell and so ignores the covariance between dens… | LIMITATIONS L-032 | rewritten for the ISIMIP3b data or without the v1 outputs it cited |
| L-033 | Inverter clipping and curtailment are not modeled; wind retention covers wake, availabili… | LIMITATIONS L-033 | unchanged |
| L-034 | RETIRED 2026-10-16: it described a 2026-vintage plant (t_ref = 2026). The vintage is now… | LIMITATIONS L-034 | unchanged |
| L-035 | RETIRED 2026-10-16: it described the transfer of the IRENA 2024 costs to a 2026 vintage.… | LIMITATIONS L-035 | unchanged |
| L-036 | Portugal uses the European regional values of IRENA for CAPEX (a Tier 2 transfer of the s… | LIMITATIONS L-036 | unchanged |
| L-037 | The upper tail of the capital-cost distribution beyond 2 mean - P5 is excluded, which rem… | LIMITATIONS L-037 | unchanged |
| L-038 | Fixed O&M is a fraction of the sampled capital cost, so absolute O&M scales with it; vari… | LIMITATIONS L-038 | unchanged |
| L-039 | The lifetime is a discrete uniform on the integers 25 to 30, each year with probability 1… | LIMITATIONS L-039 | unchanged |
| L-040 | The discount rate is the real after-tax regional WACC of IRENA 2024 (South America for Br… | LIMITATIONS L-040 | unchanged |
| L-041 | The scope of the IRENA total installed cost with respect to grid connection is known only… | LIMITATIONS L-041 | unchanged |
| L-042 | The plant is a 2024-vintage counterfactual (t_ref = 2024, the cohort of the IRENA 2024 co… | LIMITATIONS L-042 | unchanged |
| L-043 | RETIRED 2026-10-16: it described the Tier 3 flag range of the Weibull layers (A in [1, 15… | LIMITATIONS L-043 | unchanged |
| L-044 | A cell whose elevation is missing in the DEM (no eligible pixel has a value) is not a can… | LIMITATIONS L-044 | unchanged |
| L-045 | RETIRED 2026-10-19 (COMMAND 55): it described 174,049 km2 of IND (the north block and Aru… | LIMITATIONS L-045 | unchanged |
| L-046 | RETIRED 2026-10-19 (COMMAND 55): it described the displaced elevation files of IND and BR… | LIMITATIONS L-046 | unchanged |
| L-047 | The country territory is GADM 4.1 level 0 as published, reduced to its contiguous part (M… | LIMITATIONS L-047 | unchanged |
| L-057 | The width of a river reach is estimated from its long-term mean discharge with the global… | LIMITATIONS L-057 | unchanged |
| L-058 | The river corridor is merged with the land-cover water classes by union, but the land cov… | LIMITATIONS L-058 | unchanged |
| L-059 | Settlement setbacks come from studies in other countries, since none of the three countri… | LIMITATIONS L-059 | unchanged |
| L-060 | Slope thresholds are percent values defined on elevation models of other resolutions; her… | LIMITATIONS L-060 | unchanged |
| L-061 | Clusters of the minimum area are formed from pixels with any eligible fraction, so a clus… | LIMITATIONS L-061 | unchanged |
| L-062 | River corridors and settlement setbacks are measured on 10 x 10 sub-pixels per pixel (abo… | LIMITATIONS L-062 | unchanged |
| L-063 | The vector clip of a large source layer (F1b clip_vector_to_country) is one step per laye… | LIMITATIONS L-063 | unchanged |
| L-064 | The slope comes from FABDEM V1-2, a DEM in which a machine-learning model removed the hei… | LIMITATIONS L-064 | unchanged |
| L-065 | The restrictive scenario of PRT does not apply the Reserva Ecologica Nacional (REN), a le… | LIMITATIONS L-065 | unchanged |
| L-066 | A country whose polygon crosses the 180 degree meridian is not supported and is refused b… | LIMITATIONS L-066 | rewritten for the ISIMIP3b data or without the v1 outputs it cited |
| L-067 | The pipeline has been run to completion only for countries up to the size of BRA (PRT, IN… | LIMITATIONS L-067 | unchanged |
| L-068 | Rebuilding the cache era5_reduction (the annual maxima of the ERA5 gust, M-F1-05) is a lo… | LIMITATIONS L-068 | rewritten for the ISIMIP3b data or without the v1 outputs it cited |
| L-069 | The data contract of the connection cost (Group 3) requires at least one eligible substat… | LIMITATIONS L-069 | unchanged |
| L-070 | The dependencies of the tests are pinned in ci/constraints.txt (geopandas 1.1.2, Pillow 1… | LIMITATIONS L-070 | unchanged |
| L-071 | The orchestrator has no official way to run a phase over fixed inputs (OQ-082, accepted a… | LIMITATIONS L-071 | unchanged |
| L-072 | One lint suppression in src exists to preserve the code fingerprints (OQ-073, accepted as… | LIMITATIONS L-072 | unchanged |
| L-101 | Biomass is outside the thesis core; the technology registry allows later addition. | LIMITATIONS L-101 | unchanged |
| L-102 | GHG abatement is outside the thesis. | LIMITATIONS L-102 | unchanged |
| L-103 | Seismic hazard is not modeled. | LIMITATIONS L-103 | unchanged |
| L-104 | Sea-level rise and wildfire are not modeled (data limitations inherited from GEAR). | LIMITATIONS L-104 | unchanged |
| L-105 | Transport decarbonisation is permanently excluded. | LIMITATIONS L-105 | unchanged |
| L-203 | RETIRED 2026-10-16: countries.BRA.technologies.wind.opex_fixed_frac was a proxy (solar O&… | LIMITATIONS L-203 | unchanged |
| L-204 | countries.{BRA,PRT,IND}.technologies.solar.luf | LIMITATIONS L-204 | unchanged |
| L-205 | countries.{BRA,PRT,IND}.technologies.wind.luf | LIMITATIONS L-205 | unchanged |
| L-206 | countries.{BRA,PRT,IND}.technologies.wind.eta_loss | LIMITATIONS L-206 | unchanged |
| L-207 | countries.{BRA,PRT,IND}.technologies.{solar,wind}.lifetime_years | LIMITATIONS L-207 | unchanged |
| L-208 | countries.{BRA,IND}.technologies.wind.opex_fixed_frac (range) | LIMITATIONS L-208 | unchanged |
| L-209 | countries.{BRA,PRT,IND}.technologies.{solar,wind}.discount_rate (range) | LIMITATIONS L-209 | unchanged |
| L-210 | land_availability.technologies.wind.elevation_max_m | LIMITATIONS L-210 | unchanged |
| L-212 | countries.{BRA,PRT,IND}.connection.tortuosity_grid and tortuosity_road | LIMITATIONS L-212 | unchanged |
| L-213 | countries.{BRA,PRT,IND}.connection.transmission_loss_per_km(_sensitivity) | LIMITATIONS L-213 | unchanged |
| L-214 | countries.{BRA,PRT,IND}.connection.reference_project_mw | LIMITATIONS L-214 | unchanged |
| L-215 | countries.{BRA,PRT,IND}.connection.long_distance_flag_km and geospatial.distance_cap_km | LIMITATIONS L-215 | unchanged |
| L-216 | geospatial.pvcz_max_distance_km and geospatial.poi_line_tolerance_m | LIMITATIONS L-216 | unchanged |
| L-217 | countries.IND.connection.bay_cost | LIMITATIONS L-217 | unchanged |
| L-218 | countries.{BRA,IND,PRT}.connection.road_cost_per_km_high | LIMITATIONS L-218 | unchanged |
| L-220 | land_availability.riparian.countries.IND (buffer from the channel edge) | LIMITATIONS L-220 | unchanged |
| L-221 | land_availability.riparian.countries.PRT.central (navigability proxy) | LIMITATIONS L-221 | unchanged |
| L-222 | land_availability.technologies.solar.settlement_setback_m (restrictive) | LIMITATIONS L-222 | unchanged |
| L-223 | land_availability.sensitivities.population_density_200 | LIMITATIONS L-223 | unchanged |
| L-211 | audit.derived_ranges.weibull_a and weibull_k (validity_range) | LIMITATIONS L-211 | unchanged |
| L-224 | The width of the cost-of-capital range ($\pm 1$ percentage point) is Tier~3. | LIMITATIONS L-224 | unchanged |
| L-228 | Several 2025 values come from secondary compilations and are marked for verification. | LIMITATIONS L-228 | unchanged |
| L-229 | Exposure is not converted into loss; hazard and economic results are read together. | LIMITATIONS L-229 | unchanged |
| L-230 | The 35 and $40\,^{\circ}\mathrm{C}$ thresholds are simple counts; only the latter has a p… | LIMITATIONS L-230 | unchanged |
| L-231 | The wind-factor range is a Tier~3 guard; no CMIP6 per-cell ratio was found for the study… | LIMITATIONS L-231 | rewritten for the ISIMIP3b data or without the v1 outputs it cited |
| L-232 | Gust exposure is context only and is not comparable with design wind speeds. | LIMITATIONS L-232 | unchanged |
| L-233 | Published potentials differ in hub height, density and exclusions, so ratios are indicati… | LIMITATIONS L-233 | unchanged |
| L-234 | No area-based potential was found for Portugal. | LIMITATIONS L-234 | unchanged |
| L-235 | The 143~GW value belongs to the 2001 atlas at 50~m and is not a value of the 2013 simulat… | LIMITATIONS L-235 | unchanged |
| L-236 | The reduction to $n+1$ scenarios is not available for discrete cell ranking; the full sce… | LIMITATIONS L-236 | unchanged |
| L-237 | Six land-cover tiles of BRA in the local database are corrupted; they are handled tile by… | LIMITATIONS L-237 | unchanged |
| L-238 | The Global Wind Atlas API redirects without validating the product or the height; the exi… | LIMITATIONS L-238 | unchanged |
| L-240 | The synthetic country ZZZ is spatially uniform in resource and forcing (only distances an… | LIMITATIONS L-240 | unchanged |
| L-241 | The IRENA solar TIC is per kW DC and the solar CF is AC energy over DC capacity (DEC-087)… | LIMITATIONS L-241 | unchanged |
| L-243 | Orchestrator: a producer that fails before registering any artifact does not invalidate i… | LIMITATIONS L-243 | unchanged |
| L-249 | The wind cell CF is not calibrated to, and not validated as an absolute value against, th… | LIMITATIONS L-249 | unchanged |
| L-253 | F6 leaves out a candidate cell whose PV zone or distance is missing (n_excluded_cell_memb… | LIMITATIONS L-253 | unchanged |
| L-254 | Memory of the execution machine (about 6 GB of RAM): in BRA, robustness_analysis (3,174 M… | LIMITATIONS L-254 | unchanged |
| L-259 | The 2020 land cover marks a plant as built. The share of "built" (WorldCover 2020) in the… | LIMITATIONS L-259 | unchanged |
| L-260 | The central scenario is stricter than the practice of the plants that exist, in four crit… | LIMITATIONS L-260 | unchanged |
| L-261 | The GEM location is approximate for most units: in IND wind only 58 of 679 units (9.4% of… | LIMITATIONS L-261 | unchanged |
| L-262 | The class "old plant in an area that is restricted today" is not assessable: WorldCover a… | LIMITATIONS L-262 | unchanged |

## 5. Double check of COMMAND 304

**(a) Retired-term scan.** The items below were `a` or `b` and only describe v1; they are demoted to historical (Section 6). The items `b` that cited CMIP6, the T- outputs or H1 to H5 and still hold were rewritten (the tables above say so).

**(b) DEC-035 to DEC-041** against the current code:

| v1 ID | Verdict |
|---|---|
| DEC-035 | historical: the legacy `suitability_criteria` package (guard of `solar_pvout_weight`) is not in the code |
| DEC-036 | historical: same package (`terrain_score`) |
| DEC-037 | historical: same package (`compute_biomass_resource`) |
| DEC-038 | historical: same package (14 criteria, `protected_areas`) |
| DEC-039 | historical: the river buffer of 0.5 km is replaced by the corridor widths of M-F2b-01 (E3) |
| DEC-040 | holds: `resolve_solar_path` is in `data_acquisition/local_layers.py` and registered in `_LOCAL_PATH_HANDLERS` |
| DEC-041 | historical: `derive_slope_from_dem` exists in `grid_alignment/raster_alignment.py` but nothing calls it; the slope is the FABDEM distribution with geodesic spacing (M-F2a-07, M-F2a-08); the function leaves with COMMAND 306 |

## 6. Items that are historical or were demoted (ID only)

**M (32):** historical. M-E1-01, M-F1-04, M-F4-02, M-F5-04, M-F6-02, M-F6-03, M-F6-04, M-F7-01, M-F7-02, M-F7-03, M-F7-04, M-F7-05, M-F7-06, M-F7-07, M-F7-08, M-F7-09, M-F7-10, M-F7-11, M-F7-12, M-F7-14, M-F7-15, M-F7-16, M-F7-17, M-F7-18, M-F7-19, M-F7-20, M-F7-21, M-F8-03, M-X-02, M-X-03, M-X-04, M-X-05

**DEC (43):** historical. DEC-002, DEC-003, DEC-004, DEC-005, DEC-009, DEC-024, DEC-035, DEC-036, DEC-037, DEC-038, DEC-039, DEC-041, DEC-052, DEC-053, DEC-058, DEC-059, DEC-060, DEC-061, DEC-063, DEC-067, DEC-069, DEC-070, DEC-073, DEC-074, DEC-075, DEC-076, DEC-077, DEC-078, DEC-079, DEC-080, DEC-082, DEC-083, DEC-085, DEC-086, DEC-087, DEC-088, DEC-089, DEC-090, DEC-094, DEC-095, DEC-096, DEC-097, DEC-100

**OQ (4):** historical. OQ-014, OQ-020, OQ-071, OQ-116

**L (25):** historical. L-007, L-021, L-022, L-023, L-024, L-219, L-225, L-226, L-227, L-239, L-242, L-244, L-245, L-246, L-247, L-248, L-250, L-251, L-252, L-255, L-256, L-257, L-258, L-263, L-264

**Phase-record items D- (148):** historical (decisions of removed or rebuilt phases and of v1-only machinery; the records of F4 and F7 start empty in v2). D-E5b-001, D-F1-015, D-F1-016, D-F1-024, D-F1b-002, D-F1b-008, D-F1b-011, D-F3-007, D-F3-027, D-F4-001, D-F4-002, D-F4-003, D-F4-004, D-F4-005, D-F4-006, D-F4-007, D-F4-008, D-F4-009, D-F4-010, D-F4-011, D-F4-012, D-F4-013, D-F4-014, D-F4-015, D-F4-016, D-F4-017, D-F4-018, D-F4-019, D-F4-020, D-F4-021, D-F4-022, D-F4-023, D-F4-024, D-F4-025, D-F4-026, D-F4-027, D-F4-028, D-F4-029, D-F5-006, D-F5-010, D-F5-013, D-F5-018, D-F5-022, D-F5-023, D-F6-001, D-F6-002, D-F6-003, D-F6-004, D-F6-006, D-F6-017, D-F6-020, D-F6-028, D-F6-032, D-F6-033, D-F6-034, D-F7-001, D-F7-002, D-F7-003, D-F7-004, D-F7-005, D-F7-006, D-F7-007, D-F7-008, D-F7-009, D-F7-010, D-F7-011, D-F7-012, D-F7-013, D-F7-014, D-F7-015, D-F7-016, D-F7-017, D-F7-018, D-F7-019, D-F7-020, D-F7-021, D-F7-022, D-F7-023, D-F7-024, D-F7-025, D-F7-026, D-F7-027, D-F7-028, D-F7-029, D-F7-034, D-F7-035, D-F7-036, D-F7-037, D-F7-038, D-F7-039, D-F7-040, D-F7-041, D-F7-042, D-F7-043, D-F7-044, D-F7-045, D-F7-046, D-F7-047, D-F7-048, D-F7-049, D-F7-050, D-F7-051, D-F7-052, D-F7-053, D-F7-054, D-F7-055, D-F7-056, D-F7-057, D-F7-058, D-F7-059, D-F7-060, D-F7-061, D-F7-062, D-F7-063, D-F7-064, D-F7-065, D-F7b-007, D-F8-004, D-F8-005, D-F8-006, D-F8-009, D-F8-010, D-F8-011, D-F8-012, D-F8-013, D-F8-014, D-F8-015, D-F8-016, D-F8-021, D-F8-022, D-F8-023, D-F8-024, D-F8-025, D-X-001, D-X-002, D-X-003, D-X-004, D-X-005, D-core-010, D-core-023, D-core-028, D-core-029, D-core-033, D-core-038, D-core-039, D-core-055, D-core-056, D-core-057

