# GeoFREA Methodology Specification

| Field | Value |
|---|---|
| Document | `docs/METHODOLOGY.md` |
| Version | 13.0.1 |
| Adopted | 2026-09-15 |
| Updated | 2026-10-14 |
| Owner | Douglas |
| Status | Adopted for implementation. Static document. |

## 0. Document control

This document is the single source of truth for the scientific method and architecture of GeoFREA. It describes the method as it is, not how it evolved.

Change protocol:

1. This file is edited only with explicit authorization from Douglas.
2. Every change bumps the version (MAJOR: changes a result definition or phase contract; MINOR: adds an item without changing existing results; PATCH: wording or reference fixes) and adds one line to the changelog in Section 14.
3. Implementation that needs to deviate from an item opens an entry in `docs/OPEN_QUESTIONS.md` and stops until Douglas gives a verdict. Deviations are never implemented first and documented later.
4. Item IDs are stable. A removed item keeps its ID, marked `RETIRED` in the changelog; IDs are never reused.

ID scheme:

| Prefix | Meaning | Example |
|---|---|---|
| `S-nn` | Scope item | `S-03` |
| `M-<phase>-nn` | Method item of a phase | `M-F5-04` |
| `U-nn` | Uncertainty and futures design item | `U-02` |
| `A-nn` | Architecture requirement | `A-01` |
| `V-nn` | Validation and testing item | `V-03` |
| `T-<id>` | Thesis output | `T-R4` |
| `OQ-nnn` | Open question (lives in `OPEN_QUESTIONS.md`) | `OQ-007` |
| `L-nnn` | Declared limitation (lives in `LIMITATIONS.md`) | `L-004` |

Phase IDs: `F1`, `F1b`, `F2a`, `F2b`, `F3`, `F4`, `F5`, `F6`, `F7`, `F7b`, `F8`, `E1`. Never write an unqualified `F2` or `F7`.

---

## 1. Scientific anchor

All architecture and output decisions are subordinate to this section.

### 1.1 Research questions

- **RQ0 (central).** How can a spatially explicit computational framework, integrating technical renewable potential, techno-economic viability, and multi-scenario climate change, identify siting priorities (S-06) that remain robust across climate futures, and how can that robustness be measured defensibly while treating physical-climate and techno-economic uncertainty jointly?
- **RQ1.** How can technical potential be quantified spatially in a way that is comparable across countries?
- **RQ2.** How can territorial constraints and territory-dependent costs be integrated with techno-economic parameters into a single, physically interpretable site-level viability metric?
- **RQ3.** How do multi-SSP climate projections change the potential and future viability of sites not yet built?
- **RQ4.** Which decision-robustness approach is most adequate to treat deep climate uncertainty and techno-economic parametric uncertainty jointly, without collapsing them into an arbitrary single score?
- **RQ5.** Does the framework generalize across Brazil, Portugal, and India, or does it produce context-specific results?

### 1.2 Research objectives

- **RO1.** Quantify spatially the technical solar and wind potential in the three core countries. Served by F3 and F5.
- **RO2.** Integrate land-eligibility constraints and spatially explicit cost drivers (grid connection, site access) into site-level LCOE. Served by F2b, F3, F6.
- **RO3.** Quantify how SSP1-2.6, SSP3-7.0, and SSP5-8.5 projections from a CMIP6 GCM ensemble change resource, technical potential, and LCOE of candidate sites in 2041-2070 (core) and 2071-2100 (sensitivity), reusing and adapting the CRAEI climate data layer. Climate hazards enter quantitatively only where a Tier 1-2 loss function exists. Served by F4, F5, F6.
- **RO4.** Develop a site-level robustness assessment over a full-factorial ensemble of climate members and techno-economic parameter samples, with relative regret on LCOE as primary metric (MR, M-F7-03), satisficing robustness under a minimum-generation constraint as secondary metric, and PRIM scenario discovery for vulnerabilities. Land availability is reported as a range and is not a factor of the futures (U-06). Served by F7.
- **RO5.** Validate the framework in Brazil, Portugal, and India through cross-country comparison and external plausibility checks against existing plants, and deliver a lightweight precomputed explorer as a demonstration artifact. Served by F7b, F8, E1.

### 1.3 Hypotheses

- **H1.** The ranking of candidate sites holds across climate futures in two independent senses (M-F7-07; text in `docs/thesis/hypotheses/H1_climate_rank_robustness.tex`). H1a, core stability: a majority of the sites that are robust under one SSP are robust under all three (the core share `C_k` is at least `alpha`). H1b, climate vulnerability: at least one in five of the nominal top-k sites falls outside the top `k + m` of the climate-only ranking in at least one SSP (the vulnerable share `V_k` is at least `beta`). The verdict per country and technology is supported (H1a and H1b hold), partially supported (exactly one holds) or not supported (neither). The thresholds are pre-registered in OQ-050 (H1).
- **H2.** Assessing renewable expansion by first-level administrative region instead of by cell selects different and less robust capacity (M-F7-07; text in `docs/thesis/hypotheses/H2_spatial_aggregation_bias.tex`). Two procedures select the same capacity `T`, that of the robust top-k set of H1: one ranks cells by `MR`, the other ranks Admin1 regions by their capacity-weighted mean `MR`. The Capacity Overlap Index `O` is the share of `T` that both select. The verdict per country and technology is not testable when `O_ref = T / Q_max` is at least `gamma`, supported when `O < gamma` and not supported when `O >= gamma`, with `gamma = 0.30`, pre-registered in OQ-050 (H2).
- **H3.** Planning for robustness changes where renewable capacity would be built: a material share of the robust capacity lies outside the reach of a plan based on present conditions (M-F7-07; text in `docs/thesis/hypotheses/H3_robust_versus_nominal.tex`). Two shortlists of the same size `k` are drawn from the same set `I`: the robust one `S_k` (the same as the target of H2, ranked by `MR`) and the nominal one (ranked by `LCOE_i,f0`). The statistic `D` is the share of the capacity of `S_k` in cells whose nominal rank exceeds `k + m`, with `m = k`. The verdict per country and technology is not testable when `D_ref = 1 - (k + m) / |I|` is below `delta`, supported when `D >= delta` and not supported when `D < delta`, with `delta = 0.20`, pre-registered in OQ-050 (H3). The price `Pi` and the benefit `B` of robustness are reported without a verdict.
- **H4.** The uncertainty axis that dominates the displacement of the site ranking is not the same in every country (M-F7-06, M-F7-07; text in `docs/thesis/hypotheses/H4_axis_dominance.tex`). For each country and technology, each axis is introduced alone and the displacement it produces is the statistic `D` of H3 applied to the shortlist of that axis: `D_clim` (scores `Z_clim = max over members of r at s0`) and `D_tec` (`Z_tec = P90 over s >= 1 of r at m0`). The dominance ratio `rho = D_clim / (D_clim + D_tec)` gives the profile No Displacement (`D_clim + D_tec = 0`), Climate-Dominated (`rho > 0.60`), Techno-Economic-Dominated (`rho < 0.40`) or Mixed (`0.40 <= rho <= 0.60`). H4 is supported for a technology if at least one country is Climate-Dominated and another Techno-Economic-Dominated (strict rule); the verdict is per technology and is issued across countries. The thresholds are pre-registered in OQ-050 (H4).
- **H5 (RQ3).** Climate change puts material pressure on the economic renewable potential that supports a national target (M-F7-07; text in `docs/thesis/hypotheses/H5_climate_threat_to_targets.tex`). For one country and technology, the economic domain `Omega_econ` is the set of candidate cells of the central land scenario with a valid forcing in every member of the core window and `LCOE_i,f0 <= tau` (`tau`, OQ-008), held fixed across members; `E_0` is its annual energy at the reference member, `G` the national target in TWh/year (OQ-010), and the slack is `H_0 = E_0 - G`. H5a (resource): `Delta E = max(0, E_0 - min over members of E_m)` and `R_loss = Delta E / H_0`. H5b (exposure): `E_exp` is the largest, over the members that carry the hazard channel, of the energy of the cells where at least one hazard indicator that has a threshold reaches it (OQ-051; a channel without a threshold is excluded and declared), and `R_exp = E_exp / H_0`. H5a holds when `R_loss >= lambda` and H5b when `R_exp >= lambda`, with `lambda = 0.20`. The verdict per country and technology is supported (both hold), partially supported (resource), partially supported (exposure) or not supported; it is not testable without a target and reads target not met at reference when `H_0 <= 0`. The threshold is pre-registered in OQ-050 (H5).

### 1.4 Declared contributions

1. A spatially explicit pipeline in which climate-scenario impact is a first-order input to site ranking, not a post-hoc sensitivity check.
2. A site-level decision-robustness assessment that treats climate and techno-economic uncertainty jointly and keeps the two axes separable.
3. Empirical validation in three climatically and structurally distinct national contexts.
4. A configuration-driven architecture (YAML/JSON per country and technology) designed for extension without code changes, exercised on the three validated cases and enforced by tests (A-05, A-06).

---

## 2. Scope

| ID | Item | Decision |
|---|---|---|
| S-01 | Countries | Brazil (BRA), Portugal (PRT), India (IND). Other countries only after all three are complete. |
| S-02 | Technologies | Utility-scale ground-mounted solar PV and onshore wind. Other technologies are added later through the technology registry (A-04) without changes to F5-F7 code. |
| S-03 | Climate scenarios | SSP1-2.6, SSP3-7.0, SSP5-8.5. |
| S-04 | Climate models | CMIP6 GCM ensemble of six models selected by protocol M-F4-02 (D-F4-012): GFDL-ESM4, MIROC6, ACCESS-CM2, IPSL-CM6A-LR, CNRM-CM6-1, MRI-ESM2-0. |
| S-05 | Time windows | Core window 2041-2070. Sensitivity window 2071-2100, interpreted as repowering or second-generation assets. Reference climatology 1995-2014. The 2071-2100 members have resource rows (M-F4-03) and no hazard rows: the daily hazard data of that window are acquired only when OQ-007 says a hazard enters LCOE (M-F4-05, M-F1-04). |
| S-06 | Decision unit | 0.05 degree cell, exactly 5 x 5 pixels of the 0.01 degree analysis grid (M-F3-03). |
| S-07 | Currency | Constant 2024 USD. |
| S-08 | Excluded from scope | GHG abatement; biomass; seismic hazard layer; transport decarbonisation; sea-level rise; wildfire. |
| S-09 | Repository boundary | GeoFREA and CRAEI remain separate repositories. GeoFREA copies and adapts any needed CRAEI code (A-11); CRAEI is never modified from GeoFREA work. |

---

## 3. Conceptual framework

GeoFREA follows the hierarchy of renewable potentials used in large-scale assessments, with one layer added:

| Level | Question | GeoFREA output | Unit |
|---|---|---|---|
| Geographic potential | Where is construction allowed? | Eligible area per cell | km² |
| Technical potential | How much capacity fits and how much energy does it produce? | Capacity, capacity factor, annual energy per cell | MW, -, MWh/yr |
| Economic potential | What does it cost? | Site-level LCOE including grid connection and access | USD2024/MWh |
| Robustness (thesis contribution) | How well does a site's ranking hold across futures? | Relative regret (MR), satisficing robustness, vulnerability regions | -, -, - |

Territory enters through two channels only: hard exclusions (legal and physical constraints) and monetized cost drivers (distance to grid, distance to roads). Weighted overlay of normalized criteria (GIS-MCDA) is not part of the method. A composite MCDA layer may be added in a future major version as a separate branch; it must not feed F7.

Literature anchors (verify full references during the literature review): McKenna et al. (2022) on potential definitions; Lopez et al. (2012, NREL) on exclusion-based technical potential; Maclaurin et al. (2019, NREL reV) on supply curves with transmission cost; Ryberg et al. (2018) on land-eligibility constraints; Wu et al. (2017) and Deshmukh et al. (2019, India) on site LCOE including transmission and road costs (MapRE); Lempert et al. (2003) on RDM; Savage (1951) on minimax regret; Bryant and Lempert (2010) on scenario discovery; Herman et al. (2015) and McPhail et al. (2018) on robustness metric definitions.

---

## 4. Pipeline

### 4.1 DAG

```
F1  data_acquisition ──> F1b data_quality_audit            (audit_report; findings never block, M-F1b-02)
F1 ──> F2a grid_alignment                                  (aligned layers, and reference_grid: the grid definition)
F2a (named layers) + F1b ──> F2b siting_layers
F2a (named layers) + F2b + F1b ──> F3 land_eligibility
external_inputs (CMIP6, ISIMIP3b, ERA5 registered) ──> F4 climate_forcing
F2a (reference_grid) + F1b + external_inputs ──> F4 climate_forcing ──> climate_maps
F2a (reference_grid) + F4 members ──> hazard_context
F2a + F2b + F3 + F4 + hazard_context ──> overview
F3 + F4 ──> F5 technical_potential ──> F6 lcoe_modeling ──> F7 robustness_analysis
F5 (central scenario) ──> potential_maps
F6 ──> lcoe_maps
F7 ──> robustness_maps
F3 + F6 (nominal) + F1 (existing plants) ──> F7b external_validation
F7 (every country) ──> cross_country_h4                    (the H4 verdict: needs the profiles of all the countries)
F5 + F6 + F7 + F7b (+ cross_country_h4) ──> F8 results_synthesis ──> E1 explorer
```

Each phase requires the named artifacts it reads, not the producing phase as a whole: F4 requires the `reference_grid` artifact (CRS, transform, shape and a hash of the in-country mask of the analysis grid) and no aligned layer, F2b and F3 require the aligned layers they read. A rerun of a phase invalidates a consumer only when the content hash of an artifact the consumer requires changed (A-02).

The phase cross_country_h4 is a support phase of a different kind: it takes the list of countries as its input, reads the `h4_country` table that F7 registered in the manifest of each of them and writes the `h4_verdict` tables and a manifest of its own under `outputs/cross_country/`, because the manifest of a country cannot hold an artifact that depends on the other countries. `main.py` runs it once after the country runs; F8 reads it when it exists. The phases external_inputs, hazard_context, climate_maps, potential_maps, lcoe_maps, robustness_maps and overview are support phases with no F-identifier; they are named by phase name and registered in `main.py` with the same `requires` and `produces` contract as the F-phases (A-01). The legacy phase `suitability_criteria` is outside this specification.

Critical transitions:

1. **End of F3: raster to table.** From F4 onward, every phase operates on candidate-cell tables (parquet), never on full rasters.
2. **F4 creates the climate-member axis** `m`. F5 is evaluated once per member (tens of evaluations).
3. **F6 introduces the parameter-sample axis** `s` in streaming mode. No phase stores the full `cells x members x samples` array.
4. **F7 evaluates futures `f = (m, s)` jointly across cells**, one future at a time, vectorized over cells.

### 4.2 Phase table

| Phase | Module (`src/geofrea/<module>/`) | Purpose | Main outputs | Serves |
|---|---|---|---|---|
| F1 | `data_acquisition` | Resolve raw layers with provenance | Layer registry | RO1-RO3 infrastructure |
| F1b | `data_quality_audit` | Audit raw layers, report anomalies | Audit report (required by F2b, F3 and F4) | V-04 |
| F2a | `grid_alignment` | Align all layers to the 0.01 degree grid | Aligned rasters | RQ1 |
| F2b | `siting_layers` | Build exclusion, cost-driver and resource layers per technology | Pixel layers | RO2, RQ2 |
| F3 | `land_eligibility` | Combine exclusions, aggregate to cells, export candidate table | Candidate table, eligibility rasters | RO1, RO2, RQ1, RQ2 |
| external_inputs | `climate_forcing` | Verify and register the CMIP6, ISIMIP3b and ERA5 files F4 consumes | External-inputs report | RO3 |
| F4 | `climate_forcing` | Compute per-cell climate change factors per member | Forcing table, masked-cell table, member list | RO3, RQ3 |
| hazard_context | `climate_forcing` | Compute hazard context indicators per cell and member | Hazard table | RO3, RQ3 |
| climate_maps | `climate_forcing` | Diagnostic maps of the change factors | Climate maps | Section 11 |
| potential_maps | `technical_potential` | COG and diagnostic maps of potential density and capacity factor at the reference climate, central land scenario | Potential rasters, potential maps | T-R1 (F8 draws the thesis figure), Section 11 |
| lcoe_maps | `lcoe_modeling` | COG and diagnostic maps of the LCOE at the reference member (nominal, p10, p50, p90), the nominal LCOE of the core window by SSP, and the nominal supply curve | LCOE rasters, LCOE maps | T-R11 (F8 draws the thesis figure), Section 11 |
| robustness_maps | `robustness_analysis` | COG and diagnostic maps of the max regret, satisficing, top-k flags, classes and the sub-family regrets, per window | Robustness rasters, robustness maps | T-R4 (F8 draws the thesis figure), Section 11 |
| overview | `overview` | Country overview maps and table over F2a to F4 outputs | Overview figures | Section 11 |
| F5 | `technical_potential` | Capacity, CF, and energy per cell and member | Potential table | RO1, RO3, RQ1, RQ3 |
| F6 | `lcoe_modeling` | LCOE kernel, parameter sampling, per-member LCOE summaries | LCOE summaries, design matrix | RO2, RQ2 |
| F7 | `robustness_analysis` | Regret, satisficing, decomposition, scenario discovery, hypothesis tests | Robustness tables | RO4, RQ0, RQ4, H1-H5 |
| F7b | `external_validation` | Plausibility checks against existing plants and published estimates | Validation tables | RO5 |
| cross_country_h4 | `robustness_analysis` | Verdict of H4 per technology from the profiles of all the countries | `h4_verdict` tables, manifest of its own | RQ4, RQ5, H4 |
| F8 | `results_synthesis` | Aggregate only; produce thesis outputs | Thesis figures and tables | RO5, RQ5 |
| E1 | `explorer` | Precomputed static explorer | Static site bundle | RO5 |

---

## 5. Phase specifications

### F1 data_acquisition

- **M-F1-01.** Layer registry with provenance per layer: `provenance` in {`fetched`, `local_only`} and computed `fetch_status`. Layers without automated fetch resolve from the local database (`GEOFREA_SHARED_RAW_DIR`, resolved through `paths.py`).
- **M-F1-02.** Active layers: country borders and admin1 (GADM 4.1), protected areas (WDPA via Protected Planet API v4), lakes and rivers (HydroSHEDS), land cover, elevation, population, transmission grid, roads (GRIP4), solar PVOUT (Global Solar Atlas, long-term average daily totals, kWh/kWp/day), wind (M-F1-03), CMIP6 (M-F1-04), ERA5 gust (M-F1-05), existing plants (M-F1-06). The seismic layer is not part of GeoFREA.
- **M-F1-03.** Global Wind Atlas products at hub-relevant heights 100, 150, 200 m: `combined-Weibull-A`, `combined-Weibull-k`, `air-density`, and `wind-speed` (quality check only). Product existence is confirmed on the CDN response after redirect, never on the API redirect alone.
- **M-F1-04.** CMIP6 from Copernicus CDS: monthly `rsds`, `tas`, `sfcWind` for `historical` and the three SSPs; daily `tasmax` and `pr` for the historical reference and the core window (hazard indicators); the daily data of the 2071-2100 window are acquired only when OQ-007 says a hazard enters LCOE (M-F4-05). One realization per model, identical across variables and experiments (default `r1i1p1f1`, verified at download). Acquisition and processing adapted from CRAEI per A-11.
- **M-F1-05.** ERA5 gust reanalysis (scenario-invariant extreme-wind indicator), built fresh (CRAEI's own D12 decided against ERA5 gust, so there is no A-11 source to adapt). Reduction: annual maximum of `fg10` (10 m wind gust since previous post-processing). Reference period: 1995-2014, for coherence with S-05, since the indicator is declared scenario-invariant.
- **M-F1-06.** Existing solar and wind plants from Global Energy Monitor trackers, used only in F7b. Never used to fit any parameter (V-06). GEM is the only existing-plant source: the WRI Global Power Plant Database (records to 2020) is not acquired, aligned or audited, and no rasterized plant layer exists in F2a.
- **M-F1-07.** GADM borders resolve local-first with checksum; network download is a fallback.

### F1b data_quality_audit

- **M-F1b-01.** Audit every active layer: coverage, nodata share, value ranges, resolution, CRS. Expected native resolutions and sanity ranges are configuration, not code.
- **M-F1b-02.** The audit's findings never block execution: an anomaly is reported, not enforced. The audit report is a declared input (`audit_report`) of F2b, F3 and F4; a failure to produce the report stops those phases (A-09), a finding in it does not.

### F2a grid_alignment

- **M-F2a-01.** Analysis grid: EPSG:4326, fixed 0.01 degree resolution, snapped so that 0.05 degree cells nest exactly (5 x 5 pixels).
- **M-F2a-02.** All distances and areas are geodesic (`core/geodesy.py`), including slope derivation from the DEM.
- **M-F2a-03.** Distance rasters to transmission grid, roads, and rivers store the **uncapped geodesic distance**. `distance_cap_km` (parameter, `geospatial.distance_cap_km` in `settings.yaml`) is only the threshold of a `distance_capped` flag raster written beside each distance raster (uint8, 1 where the distance exceeds the threshold): a quality indicator. No stored distance is truncated, because the connection-cost model (M-F6-01) bills the real distance (OQ-040; evidence in `docs/_audit/2026-10_distance_connection_cost_evidence.md`).
- **M-F2a-04.** Wind products are aligned per height; no combination across heights happens in F2a.
- **M-F2a-05.** Layers that hold counts (population) are brought to the analysis grid by summing the source pixels under each target pixel, never by sampling or interpolating; population density is the count over the geodesic pixel area. (Sampling had left 1/144 of the population, D-F2a-014.)
- **M-F2a-06.** Land cover enters F3 as class counts, not as one class per pixel: for every grid pixel, the number of 10 m ESA WorldCover samples in each class, block-counted from the native tiles (exact when the grid is a whole multiple of the tile pixel and on its edges; anything else is an error). The same 10 m product is used for the three countries. The point-sample mosaic stays as a display layer. (D-F2a-015.)
- **M-F2a-07.** Slope enters F3 as a distribution, not a pixel mean: Copernicus DEM GLO-30 (30 m) tiles are acquired per country (`scripts/acquire_dem30.py`, pinned by sha256 in `raw/copernicus_dem30/<ISO3>/manifest.json`), slope is computed on the native samples (central differences, WGS84 geodesic spacing) and each sample is counted into the 1 degree slope bin of the grid pixel that contains its centre (41 bands, the last open ended). The share of a pixel above any slope maximum is read from the bins, so the maximum can be a range. The 0.005 degree DEM of F1 stays for elevation and display. (D-F2a-016.)

### F2b siting_layers

- **M-F2b-01.** Exclusion terms per technology, each the excluded share of a pixel in [0, 1] (1 = fully excluded):
  - `E1 protected`: WDPA areas, every designation in the central case; the IUCN category list is a named-level parameter.
  - `E2 water`: lakes.
  - `E3 riparian`: distance to rivers below `riparian_setback_km`, for rivers above `riparian_min_discharge_m3s`.
  - E1, E2 and E3 are measured on 10 x 10 sub-pixels per pixel (about 110 m); the setback is a geodesic distance on that finer grid. At the 0.01 degree pixel size a setback below about 1.1 km would otherwise mean only "the pixel contains a river" (OQ-045).
  - `E4 slope`: the share of the pixel's 30 m slope samples above `slope_max_deg[tech]` (M-F2a-07), read from the slope bins, so the maximum can be a range.
  - `E5 land_cover`: the share of the pixel's 10 m land-cover samples outside the allowed classes (M-F2a-06). `excluded_classes[tech]` is a parameter of named levels with one central level (for example cropland excluded or allowed for solar, forest excluded or allowed for wind), as in M-F2b-06.
  - `E6 population`: 0 or 1 per pixel, population density above `pop_density_max[tech]`.
- **M-F2b-02.** Cost-driver layers: distance to transmission grid (km), distance to roads (km).
- **M-F2b-03.** Resource layers: solar PVOUT (kWh/kWp/day); wind Weibull A (m/s), Weibull k (-), and air density (kg/m³) at 100, 150, 200 m.
- **M-F2b-04.** No normalization, weighting, or scoring of any layer. Values keep physical units.
- **M-F2b-05.** Fail-loud on integrity failures of present files (corrupted tiles, invalid WDPA files). An absent protected-area, lake or river layer for a configured country raises; a zero share is never assumed silently. The synthetic country fixture (A-06) provides these layers. Any other genuinely optional layer may be absent only if the absence is recorded in the artifact metadata (`assumed_free`).
- **M-F2b-06.** The parameters of E1-E6 and the minimum eligible area are declared as ranges in `config/experiments.yaml` under `land_availability`: a central value (feeds F4-F7) and, where a source gives one, a `low`-`high` range; a parameter without a sourced range is held at its central value and declared so. Categorical parameters (excluded land-cover classes, IUCN categories) are named levels with one central level. The ranges feed the named land-availability scenarios and the full-factorial range report of U-06 (V1, V2); they are not sampled in F7. A range without a recorded source is flagged `unsourced` in the configuration and stays central in the scenarios (OQ-049).

### F3 land_eligibility

- **M-F3-01.** Pixel eligibility per technology: the eligible share of a pixel is `valid * (1 - E1) * (1 - E2) * (1 - E3) * (1 - E4) * (1 - E5) * (1 - E6)`, where `valid` is 1 only if all required layers have a value and the E-terms are the excluded shares of M-F2b-01; E4 is the share of the pixel's 30 m samples steeper than the slope maximum (M-F2a-07); E5 is the share of the pixel's 10 m land-cover samples that lie outside an allowed class (samples of no class, such as open sea, count as not allowed). Shares of different constraints are combined as independent, which counts overlapping constraints twice and so understates the eligible area (conservative). A missing value is never read as free land.
- **M-F3-02.** Eligibility is computed for the three named land-availability scenarios of U-06 (central, restrictive, permissive) and, to report ranges, over the full factorial of the land parameters that have a range (V2). Every potential output keeps land (eligible area, GW, TWh, LCOE, supply curves) and is reported as the interval over the scenarios (U-08). The scenario compositions are recorded in `docs/phases/F3_land_eligibility.md`.
- **M-F3-03.** Cell aggregation to 0.05 degree (5 x 5 pixels). Per cell and technology:
  - `cell_area_km2`: geodesic land area inside the country.
  - `eligible_area_km2`: geodesic sum of eligible pixel areas.
  - `excluded_area_km2_<Ek>`: area excluded by each constraint (overlapping, any-cause).
  - `dominant_exclusion`: constraint with the largest excluded area.
  - Resource attributes as eligible-area-weighted means: `pvout_kwh_kwp_day` (solar); `weibull_A_<h>`, `weibull_k_<h>`, `air_density_<h>` for each height (wind).
  - `dist_grid_km`, `dist_road_km`: eligible-area-weighted mean of the uncapped distance, plus `distance_capped` share (eligible-area share beyond the `distance_cap_km` threshold; a quality indicator, not a cost input).
  - `admin1_id`: the GADM admin1 unit (first administrative level) that covers the largest area of the cell inside the country, by geometry intersection and never by bounding box (ties to the smallest unit identifier); the unit identifiers and names are written beside the cell table. H2 groups cells by it.
- **M-F3-04.** A cell enters the candidate set if `eligible_area_km2 >= min_eligible_area_km2[tech]`. The candidate set of the central scenario is the set F7 uses (V1). The same rule applied to the other scenarios gives, per cell, the share of the named scenarios in which it is a candidate (candidate-set stability), reported beside the F7 results and not used by F7.
- **M-F3-05.** Outputs: `candidates_<tech>.parquet` (one row per candidate cell, stable `cell_id`, with `admin1_id`), pixel and cell eligibility COGs, dominant-exclusion COG. The per-constraint excluded shares of the pixels are not persisted: F7b evaluates the pure eligibility engine of M-F3-01 at the pixels it needs (M-F7b-01). The files of a run at another scale (M-F3-06) are written under the scale-suffixed phase directory of A-08.
- **M-F3-06.** The cell size is a parameter of the run, `scale` (0.05 degree, 5 x 5 pixels, the default; or 0.1 degree, 10 x 10 pixels). F3 aggregates the same pixels to the cells of that size with the same code (V-07). A run at 0.05 degree also writes `cells_0p1deg_<tech>.parquet`, the exact sum of the 2 x 2 cells, as an area check of the 0.1 degree run.

### F4 climate_forcing

- **M-F4-01.** Climate members `m = (gcm, ssp, window)`, plus the reference member `m0` with no change.
- **M-F4-02.** GCM selection protocol, executed once at F4 implementation and recorded in the phase record:
  1. Availability of all M-F1-04 variables for all experiments with one common realization.
  2. Transient climate response within the IPCC AR6 likely range (screening for the hot-model problem; Hausfather et al. 2022).
  3. Spread of annual-mean change factors for `rsds`, `tas`, `sfcWind` over each country in 2041-2070 under SSP3-7.0, selecting models that span the ensemble range.
  4. GFDL-ESM4 and MIROC6 are included unless they fail criterion 1 or 2.
  5. Recorded exception (OQ-009, 2026-10-06): IPSL-CM6A-LR (AR6 TCR 2.32 K, 0.12 K above the likely range 1.4-2.2 K, inside the very-likely range 1.2-2.4 K) is kept because it is one of three models with an ISIMIP3b counterpart for the hazard channel (D-F4-003) and it widens the change-factor spread (J-1 audit). It is flagged in `members.yaml` as `tcr_exception: true` so results can be shown with and without it.
- **M-F4-03.** Change factors (delta-change), computed on each GCM's native grid from monthly climatologies:
  - `delta_rsds = mean_window(rsds) / mean_ref(rsds)` (multiplicative)
  - `delta_wind = nbhd_mean(mean_window(sfcWind)) / nbhd_mean(mean_ref(sfcWind))` (multiplicative), where `nbhd_mean` is the mean over the `wind_ratio_neighbourhood_cells` x `wind_ratio_neighbourhood_cells` native cells centred on each cell (3 x 3, `config/experiments.yaml`). The neighbourhood keeps the ratio from exploding where a GCM's reference wind is near zero in a single cell (OQ-042); `delta_rsds` and `dT` stay per cell.
  - `dT = mean_window(tas) - mean_ref(tas)` (additive, K)
  - Reference period 1995-2014; annual means of the monthly climatology.
- **M-F4-04.** Change factors are bilinearly interpolated to the cell centers of the run scale (0.05 degree by default, 0.1 degree in the scale check of V-07).
- **M-F4-05.** Hazard channels (D15 rule):
  - C1 (mean resource) always enters F5 through M-F4-03.
  - C2 (operational extremes: extreme heat, extreme wind) and C3 (damage and cost: extreme precipitation) enter F5 or F6 quantitatively only with a loss function of evidence Tier 1 or 2 (resolved in OQ-007). Otherwise they are computed as per-cell context indicators per member and reported in T-R10, never entering regret or satisficing.
  - Hazard indicator processors adapted from CRAEI per A-11.
- **M-F4-06.** Outputs: `forcing.parquet` (`cell_id`, `member`, `delta_rsds`, `dT`, `delta_wind`), `forcing_masked.parquet` (the cell-members removed by M-F4-07, with the rejected `delta_wind`), `hazard_context.parquet` (context indicators per cell and member that carries the hazard channel: `tx35_days`, `tx40_days`, `rx5day_mm`, `wet_p95_exceed_freq`, their reference values, and the scenario-invariant ERA5 `gust_mean_annual_max_ms`), `members.yaml` (resolved member list with provenance, channels per member and window, masked counts).
- **M-F4-07.** Validity mask for the wind factor: a cell-member whose `delta_wind` lies outside `wind_factor_valid_range` (`config/experiments.yaml`, 0.5-1.5, plausibility bound with no source) is masked: it has no row in `forcing.parquet`, the member is absent in that cell, and the cell-member is listed in `forcing_masked.parquet`. Nothing is replaced by another value. Any consumer of the forcing (F5) must verify that every candidate cell and member is either in `forcing.parquet` or declared in `forcing_masked.parquet`, and that no factor is out of range (`climate_forcing/forcing.py::assert_forcing_usable`); otherwise it fails (OQ-042 option C, Douglas 2026-10-06).

### F5 technical_potential

- **M-F5-01.** Capacity per cell: `P_MW = eligible_area_km2 * LUF[tech] * PD[tech]`, where `PD` is power density on project footprint (MW/km²) and `LUF` is the land-utilization factor (share of eligible land plausibly developed). `LUF` and `PD` are `luf` and `power_density_mw_per_km2` in `config/parameters.json` and are required parameters of the technology (A-04, D-F5-011).
- **M-F5-02.** Solar capacity factor:
  - Reference: `CF0 = pvout_kwh_kwp_day / 24`.
  - Member: `CF_m = CF0 * delta_rsds_m * (1 + gamma * dT_m)`, with `gamma` the module power temperature coefficient (1/K, negative; `gamma` in `config/parameters.json`, required parameter and uncertain parameter). PVOUT already includes reference-climate thermal losses; the member correction is relative.
- **M-F5-03.** Wind capacity factor:
  - Hub height `H[tech, country]` is `hub_height_m` in `config/parameters.json` (U-05 provenance; required parameter) and must lie within the data heights, 100 to 200 m: outside them F5 raises, it does not extrapolate (D-F5-012). Weibull A at `H` by power-law interpolation between the two bracketing heights, `alpha = ln(A2/A1) / ln(z2/z1)`, `A_H = A1 * (H/z1)^alpha`; `k_H` linear in height; air density linear in height.
  - Equivalent wind speed with air-density correction `v_eq = v * (rho/rho0)^(1/3)` (IEC 61400-12-1 convention; `rho0` is a physical constant in `geofrea.core.constants`, with the standard cited, D-F5-009). Because a Weibull speed is a scale family, the correction folds into the scale: `A_eq = A_H * (rho_H/rho0)^(1/3)`, and the climate factor multiplies it too, `A_eq,m = delta_wind_m * A_eq`; no second integral and no shifted curve are needed.
  - Reference turbine power curve per IEC class, stored one file per curve in `config/power_curves/<curve_id>.yaml` with its provenance (U-05 fields, `synthetic` flag); `technologies.yaml` maps each IEC class to a curve id (`power_curves`). The class is chosen per cell from the mean wind speed at hub height in the reference climate (rule in `iec_class_rule`, thresholds OQ-005) and is fixed across members: a turbine is chosen for the site climate, not re-chosen per future (D-F5-004). A curve with `synthetic = true` is refused in a production run (D-F5-003).
  - `CF0 = eta_loss * integral( P_curve(v_eq) / P_rated * weibull_pdf(v; A_H, k_H) dv )`, with `eta_loss` (`eta_loss` in `config/parameters.json`, required and uncertain parameter) covering wake and availability losses. The integral treats the tabulated curve as piecewise linear and is evaluated in closed form per segment with the regularized incomplete gamma function; numerical quadrature is only the test reference, with a relative tolerance of 1e-6 (V-02, D-F5-001, D-F5-002).
  - Member: `CF_m = CF0 * CF(A_H * delta_wind_m, k_H) / CF(A_H, k_H)`, evaluated at cell values; `k_H` unchanged. `eta_loss` cancels in the ratio, so `CF_m = eta_loss * I(delta_wind_m * A_eq, k_H)`, where `I` is the integral above.
- **M-F5-04.** If a C2 loss function passes OQ-007: `CF_m <- CF_m * (1 - L_C2_m)`.
- **M-F5-05.** Annual energy: `E_m = P_MW * CF_m * 8760` (MWh/yr; the hours per year are a constant in `geofrea.core.constants`, D-F5-009).
- **M-F5-06.** Outputs, one file per technology and land-availability scenario: `potential_<tech>__<scenario>.parquet` (`cell_id`, `member`, `P_MW`, `CF`, `E_MWh`), for the scenarios central, restrictive and permissive (U-06); F6 and F7 read only the central one (V1). A cell-member declared in `forcing_masked.parquet` (M-F4-07) has no row. Country aggregates, `potential_aggregates_<tech>.parquet`, one row per scenario and member, in two series: *all present cells*, and *like-for-like*, over the cells present in every member. The climate effect on potential (member against `m0`) is computed on the like-for-like series and inside each scenario, never across scenarios; the land range is reported beside it, so the two are not confounded (U-08). The counts of absent cell-members are reported with the aggregates (D-F5-005, D-F5-006).

### F6 lcoe_modeling

- **M-F6-01.** LCOE kernel, vectorized over cells, for member `m` and parameter vector `theta`:
  - `CAPEX_total = P_MW*1000*capex_usd_per_kw + P_MW*dist_grid_km*grid_cost_usd_per_mw_km + P_MW*substation_cost_usd_per_mw + dist_road_km*road_cost_usd_per_km`
  - `OPEX_t = opex_fixed_frac * P_MW*1000*capex_usd_per_kw + opex_var_usd_per_mwh * E_t`, with `opex_var_usd_per_mwh` the variable O&M in USD/MWh, under that key in `config/parameters.json`
  - `E_t = E_m * (1 - d)^(t-1)`, `t = 1..n`
  - `LCOE = [CAPEX_total + sum_t OPEX_t/(1+r)^t] / [sum_t E_t/(1+r)^t]` (USD2024/MWh, real terms)
  - Climate of the member window is held constant over the asset lifetime.
  - `dist_grid_km` and `dist_road_km` are the real (uncapped) distances from F3. The linear distance terms are a first-order approximation of connection cost, declared in `LIMITATIONS.md` (L-019); the direction for a richer connection-cost model (voltage, technology, capacity, route, losses) is tracked in OQ-041.
- **M-F6-02.** Parameter samples `s` drawn by Latin hypercube over the uncertain parameters declared in `experiments.yaml` (U-03), with recorded seed. Sample `s0` is the nominal vector.
- **M-F6-03.** If a C3 loss function passes OQ-007, it enters as an OPEX adder per member.
- **M-F6-04.** Streaming: per member, cells are processed in blocks with all samples of a block in memory, so that the quantiles are exact (A-10). Persisted per (`cell_id`, `member`): the nominal LCOE (sample `s0`), the mean, variance, p10, p50 and p90 over the draws `s >= 1` (the nominal vector is not among them), and the count of non-finite values. The design matrix is persisted. The full sample-level array is not.
- **M-F6-05.** The kernel is a pure function importable by F7.
- **M-F6-06.** Outputs: `lcoe_summary_<tech>.parquet`, `design_matrix_<tech>.parquet`, supply curves per member at nominal parameters, and `lcoe_nominal_<tech>__<scenario>.parquet` for the restrictive and permissive land scenarios: the nominal LCOE (sample `s0`, no draws) per cell and member, which gives the land range of the potential below `tau` (U-08, T-R12, H5). Draws are taken for the central scenario only (V1).

### F7 robustness_analysis

Definitions for one country and technology. `C` = candidate cells of the central land scenario (V1); land is not a factor of the futures. Futures `f = (m, s)` over climate members of the core window and samples; `f0 = (m0, s0)` is the nominal present future.

- **M-F7-01. Feasibility.** `feasible(i, f) = CF_i,m >= CF_min[tech]` (OQ-008), evaluated on the capacity factor `CF(m, s0)` that F5 stores for the member at the nominal parameters, not on the parameter draws; the LCOE kernel receives it as an energy floor per cell, and for a feasible cell-member a draw is infeasible only when its energy is zero (infinite LCOE, M-F6-01). A cell with `CF` below `CF_min` in the nominal future `f0 = (m0, s0)` leaves the F7 set. A cell feasible in `f0` and with `CF(m, s0) < CF_min` in at least one member `m` forms the class *climate-fragile*: the class is defined at the nominal parameters `s0` of each member, it is reported separately with the members in which it fails, and it is not ranked with an infinite MR. Infeasibility that arises only from the parameter samples (`CF(m, s0) >= CF_min` but `CF(m, s) < CF_min`) does not create the class (M-F7-02 gives it a finite regret). The set `C` of F7 is the candidates of the central land scenario that are present in every member of the core window. A cell for which at least one member is masked (M-F4-07) forms the class *climate-data-invalid*: it is reported with its count and a map, and it is neither ranked nor assigned a regret (D-F5-006).
- **M-F7-02. Relative regret.** `L*_f` = the `q_ref` quantile of LCOE over the feasible cells in `f` of the F7 set (the candidates of M-F7-01 that are feasible in `f0`, climate-fragile cells included where they are feasible in `f`; climate-data-invalid cells and cells infeasible in `f0` are outside it; default `q_ref = 0`, the minimum; OQ-020). `r_i,f = (LCOE_i,f - L*_f) / L*_f` for feasible cells. A cell that is not climate-fragile and is infeasible in a future `f = (m, s)` receives the regret of the feasible cell with the highest LCOE in `f` (the finite worst case), so no ranked cell has an infinite regret.
- **M-F7-03. Primary metric.** `MR_i = max over members m of ( P90 over parameter samples s of r_i,(m,s) )`, the P90 taken over the draws `s >= 1` only; the nominal vector `s0` enters only the nominal ranking (M-F7-05) and the nominal future `f0`. Order of operations: `r` per future `(m, s)`; P90 over samples for each member; maximum over members. Secondary: SR (M-F7-04).
- **M-F7-04. Satisficing robustness.** `SR_i` = share of futures with `feasible(i, f)` and `LCOE_i,f <= tau[country, tech]` (OQ-008).
- **M-F7-05. Rankings.** Nominal rank by `LCOE_i,f0` over the F7 set; robust rank by `MR_i` (ties broken by `SR_i`, higher first) over the F7 set without the climate-fragile cells. Ties are exact equality of the float, then the next key, and finally ascending `cell_id` (A-12); no tolerance. Top-k is the best `k = ceil(p_k / 100 * n)` cells by count, at least 1, where `n` is the size of the F7 set (OQ-021): the nominal top-k is cut from the F7 set and the robust top-k from the ranked set, both with the same `k`, and a climate-fragile cell in the nominal top-k leaves it in every comparison. If the ranked set has fewer than `k` cells the robust top-k is the whole ranked set and the outputs flag `top_k_truncated`. Sensitivity, the strategy-level reading: top-k as the minimum cell set reaching the national capacity target of the technology (OQ-010; the only definition of the target is `national_targets` of `experiments.yaml`, and this sensitivity uses it when it is in GW and is not testable when it is in TWh/year, for which no conversion to capacity is registered), taking cells along the robust rank and adding their capacity until the target is met; a target above the capacity of the ranked set takes the whole set and the outputs flag `target_unreachable`.
- **M-F7-06. Axis comparison (H4).** Per country and technology, over the ranked set `I`. Axis scores on the relative regret `r` of M-F7-02: the climate axis `Z_clim_i = max over the members m of the core window of r_i,(m,s0)` (`MR_clim`; the parameters at their nominal values) and the techno-economic axis `Z_tec_i = P90 over draws s >= 1 of r_i,(m0,s)` (`MR_tec`; the climate at the reference member), each with the reference level, the feasibility and the ranked set of `MR` (M-F7-02, M-F7-03) and the tie rule of M-F7-05. `S^a_k` is the `k` cells of `I` with the lowest `Z^a_i`, `a` in {clim, tec}, with the `k` of M-F7-05. Primary: the displacement of axis `a` is the statistic of H3 on its shortlist, `D_a = (sum of q_i over the cells i of S^a_k with r^nom_i > k + m) / (sum of q_i over S^a_k)`, `m = k`, `r^nom_i` the nominal rank within `I` by `LCOE_i,f0` (M-F7-07, H3); `D_sum = D_clim + D_tec`, `rho = D_clim / D_sum` and the profile of H4 (M-F7-07). Descriptive, no verdict: the variance decomposition over futures of the relative regret (`X = LCOE / L*_f`, so `Var(r) = Var(X)`), `Var(X) = E_m[Var_s(X)] + Var_m[E_s(X)]` (techno-economic part, climate part), accumulated by F7 in its own pass (`L*_f` depends on the future, so the moments of `X` are not a function of the F6 summaries), with the caveat that a common increasing transformation of the cost of all sites changes the variance and not the ranking (the reason it is not the primary statistic); and the Jaccard overlap of the nominal top-k with the climate-only and with the techno-only top-k (the earlier primary statistic).
- **M-F7-07. Hypothesis tests.**
  - H1: scores per SSP `sigma` and cell `i` of the ranked set, on the relative regret `r` of M-F7-02: `MR_i,sigma = max over GCMs g of ( P90 over draws s >= 1 of r_i,(g,sigma,w_core),s )` (M-F7-03 restricted to one SSP) and `R^clim_i,sigma = max over GCMs g of r_i,((g,sigma,w_core),s0)` (the climate-only score, parameters at `s0`; the maximum over SSPs of `R^clim` is `MR_clim` of M-F7-06). Ranks ascend (rank 1 is best) with the tie rule of M-F7-05; `k` is that of M-F7-05, computed on `N = |I_0|`, the size of the F7 set, so that the same shortlist size applies to H1a, H1b and H2 whatever the number of climate-fragile cells; `S^sigma_k` is the top-k by `MR_i,sigma`, `S^nom_k` the nominal top-k, drawn from `I_0`, the F7 set (the ranked set together with the climate-fragile cells: the cells feasible in the nominal future), so that a present-optimal site that becomes infeasible under climate change is retained in H1b, and `r^clim_i,sigma` the rank by `R^clim_i,sigma`. A climate-fragile cell has no rank and leaves the top-k in every comparison (M-F7-05): a climate-fragile site in `S^nom_k` has no climate-only rank and is counted as vulnerable.
    - H1a, primary statistic `C_k = |intersection over the three SSPs of S^sigma_k| / k`; rule `C_k >= alpha`, `alpha = 0.60`. Reference value, reported with every result: `p_k^2` with `p_k = k / n` (the expected `C_k` if the three rankings were independent).
    - H1b, `I_i = 1` if the nominal top-k cell `i` has `r^clim_i,sigma > k + m` in at least one SSP, `m = k` (`tolerance_multiple_of_k = 1.0`); primary statistic `V_k = (sum over S^nom_k of I_i) / k`; rule `V_k >= beta`, `beta = 0.20`. The magnitude is reported per vulnerable cell and has no threshold: the worst displacement `max over sigma of (r^clim_i,sigma - nominal rank)`, the SSP and the GCM responsible, and the largest `R^clim`.
    - Verdict: supported, partially supported or not supported (see 1.3). A null in `hypothesis_rules.H1` gives no verdict and a warning.
    - Descriptive, no verdict: Jaccard of every pair of `S^sigma_k`; rank-biased overlap (RBO) between the SSP rankings, `p = 1 - 1/k`, truncated finite estimator over the ranked set; displacement, median rank and interquartile range of the nominal top-k cells across SSPs; the draw-level statistics of the sample-major pass (Spearman of the rankings and Jaccard between SSPs of the same GCM and of the per-SSP medians; share of the nominal top-k leaving under at least one member).
    - Sensitivities, reported beside the primary result, never changing the verdict: without the GCM that carries the TCR exception (M-F4-02 item 5); the 2071-2100 window (the sensitivity-window run); the 0.1 degree scale (V-07); `p_k` in {0.05, 0.10, 0.20} and `m` in {k/2, k, 2k}, `C_k` and `V_k` in each case. A change of verdict in a sensitivity is reported as a fragility.
  - H2: per cell `i` of the ranked set, the score `z_i = MR_i` (lower is better) and the capacity `q_i` of the central land scenario (M-F5-01). The partition is the Admin1 unit of each cell (`admin1_id`, M-F3-05); a region without a ranked cell does not enter; `Q_m = sum of q_i over region m` and `Q_max = sum of q_i`. The target `T` is the capacity of the robust top-k set of H1 (M-F7-05), with `k` computed on `N = |I_0|`, the size of the F7 set, as in H1. The cell selection is that set (`x_cell_i = 1` for its cells, 0 otherwise). The regional selection gives each region the capacity-weighted mean `zbar_m = sum(q_i z_i) / Q_m` and takes regions whole in ascending order of `zbar_m` (ties by region identifier) until `T` is reached; the last region enters with the fraction `y = (T - capacity of the regions taken before) / Q_last`, `0 < y <= 1`, and every cell of a region inherits its fraction (`x_admin_i`), so that both selections total `T`.
    - Primary statistic: `O = sum of q_i min(x_cell_i, x_admin_i) / T`. Reference value, reported with every result: `O_ref = T / Q_max`, the overlap of a uniform spread over the country (Admin0).
    - Verdict, `gamma = 0.30`: not testable if `O_ref >= gamma`; supported if `O_ref < gamma` and `O < gamma`; not supported if `O_ref < gamma` and `O >= gamma` (a deterministic rule on a computed index, not a test of significance).
    - Diagnostics, no verdict: the robustness penalty `Delta_z = (sum of q_i x_admin_i z_i - sum of q_i x_cell_i z_i) / T` (at least 0 up to ties); the within-region variance `sigma2_m = sum over region m of q_i (z_i - zbar_m)^2 / Q_m`; the interquartile range of `z_i` over the country relative to its median; the total variation distance `D_TV = 0.5 * sum over m of |P_cell_m - P_admin_m|`, `P` being the share of `T` that each procedure selects in region `m`. The earlier dispersion statistics of H2 (median, IQR over median, capacity-weighted national `MR`, number of Admin1 units, range of the Admin1 medians) stay as descriptive rows.
    - Sensitivities, reported beside the primary result and never changing the verdict: the decision profile (the verdict for `gamma` from 0.10 to 0.70 in steps of 0.05, with the smallest `gamma` that would still support H2; `O` does not depend on `gamma`); `T` recomputed for `p_k` in {0.05, 0.10, 0.20} and, where the technology has a national capacity target (OQ-010), for that target (the cell selection then takes cells in ascending order of `z_i` with a fractional last cell; a target above `Q_max` is flagged `target_unreachable` and capped at `Q_max`); regions ranked by the capacity-weighted median of `z_i`; `z_i` recomputed without the GCM that carries the TCR exception (M-F4-02 item 5); the 2071-2100 window and the 0.1 degree scale (the sensitivity-window run and the run at the other scale).
    - The decision rule of H5 is pre-registered in OQ-050 (H5, below); the aggregation rule of T-R8 is M-F8-03.
  - H3: the domain is `I`, the ranked set, for both rankings, so that a difference between them reflects the criterion and not the candidate set; `q_i` is the capacity of the central land scenario (M-F5-01) and `z_i = MR_i`. `k` is that of M-F7-05, computed on `N = |I_0|` as in H1 and H2, and `m = k` (`tolerance_multiple_of_k = 1.0`). `S_k` is the robust top-k set of H1 and H2 (ties by higher `SR`, then `cell_id`; M-F7-05). `r^nom_i` is the rank of cell `i` within `I` by `LCOE_i,f0` (rank 1 is the lowest; ties by ascending `cell_id`, A-12) and `S^nom_k` is the `k` cells of `I` with the lowest `LCOE_i,f0`.
    - Primary statistic: `D = (sum of q_i over the cells i of S_k with r^nom_i > k + m) / (sum of q_i over S_k)`. A cell of `S_k` with `k < r^nom_i <= k + m` is not counted. Reference value, reported with every result: `D_ref = 1 - (k + m) / |I|`, the expected `D` if the two rankings were unrelated.
    - Verdict, `delta = 0.20`: not testable if `D_ref < delta`; supported if `D_ref >= delta` and `D >= delta`; not supported if `D_ref >= delta` and `D < delta` (a deterministic rule on a computed share, not a test of significance).
    - Magnitudes, no verdict, with `Xbar(S) = sum of q_i X_i over S / sum of q_i over S`: the price of robustness `Pi = (LCOEbar_f0(S_k) - LCOEbar_f0(S^nom_k)) / LCOEbar_f0(S^nom_k)` (relative, at `f0` only) and the benefit of robustness `B = MRbar(S^nom_k) - MRbar(S_k)`; the capacities of the two shortlists are reported beside them.
    - Diagnostics, no verdict: the geodesic distance (WGS84) between the capacity-weighted centroids of `S_k` and `S^nom_k`; the total variation distance `D_TV` between their distributions of capacity across Admin1 units, defined as in H2; the Spearman rank correlation between `LCOE_i,f0` and `MR_i` over `I`; the Jaccard overlap of `S_k` and `S^nom_k` by cell count. The statistics of the earlier H3 (Jaccard of the top-k sets, share of robust capacity outside the nominal top-k, distance between centroids over the F7 set, and the per-future statistics of the sample-major pass) stay as descriptive rows.
    - Sensitivities, reported beside the primary result and never changing the verdict: without the GCM that carries the TCR exception (M-F4-02 item 5); the 2071-2100 window (the sensitivity-window run); the 0.1 degree scale (V-07); `p_k` in {0.05, 0.10, 0.20}; `m` in {k/2, 2k}. A change of verdict in a sensitivity is reported as a dependence of the result on that choice.
    - The attribution of the difference to the climate axis or to the techno-economic axis is H4.
  - H4: per country, technology and window, the domain is `I` and the capacity `q_i` that of the central land scenario (M-F5-01); `k = ceil(p_k N)` with `N = |I_0|` (M-F7-05), `m = k` (`tolerance_multiple_of_k = 1.0`); the shortlists, the displacements `D_clim` and `D_tec` and the nominal rank are those of M-F7-06 and H3.
    - Primary statistics: `D_clim`, `D_tec`, `D_sum = D_clim + D_tec` (all reported with every profile) and the dominance ratio `rho = D_clim / D_sum` (defined for `D_sum > 0`).
    - Profile of a country and technology (boundaries `0.40` and `0.60`, `lower` and `upper` of `hypothesis_rules.H4`): No Displacement if `D_sum = 0`; Climate-Dominated if `rho > 0.60`; Techno-Economic-Dominated if `rho < 0.40`; Mixed if `0.40 <= rho <= 0.60` (both boundaries inclusive). A country whose inputs do not allow both displacements to be computed (the F7 tables are empty or absent for a null decision parameter, or the technology has no F7 result) is `unavailable` and has no profile.
    - Verdict, per technology, across countries (strict rule): H4 is supported if at least one country with a profile is Climate-Dominated and another is Techno-Economic-Dominated; not testable if fewer than two countries have a profile, since a single national context cannot show a difference between contexts; not supported if at least two countries have a profile and no such pair exists (a Mixed or No Displacement country does not support it). The verdict across the two technologies is descriptive. It is a deterministic rule, not a significance test.
    - Complementary, no verdict: the displacement `D` of the joint shortlist (H3) beside `D_clim` and `D_tec` (interaction); the variance shares of M-F7-06; `D_clim` recomputed with the members of each SSP separately (and `rho` with it); the distances `|rho - 0.40|` and `|rho - 0.60|`.
    - Sensitivities, reported beside the primary result and never changing the verdict: without the GCM that carries the TCR exception (M-F4-02 item 5) in the climate axis; the 2071-2100 window (the sensitivity-window run); the 0.1 degree scale (V-07); `p_k` in {0.05, 0.10, 0.20} and `m` in {k/2, 2k}; the boundaries {0.30, 0.70} and {0.45, 0.55}, descriptive variants only. A change of profile or verdict in a sensitivity is reported as a dependence on that choice.
    - Computation: F7 writes the per-country profile (`h4_country`); the verdict needs the profiles of all the countries and is written by the support phase `cross_country_h4` (4.1, 4.2).
  - H5: per country, technology and window. `Omega` is the F7 set (the candidates of the central land scenario with a valid forcing in every member of the window, the like-for-like series of F5; climate-fragile cells are kept, because a loss of yield there is part of what H5a measures). `Omega_econ = { i in Omega : LCOE_i,f0 <= tau }` with `f0 = (m0, s0)` and `tau` that of satisficing robustness (OQ-008); it is defined once and held fixed across members in the primary analysis. `E_i,m` is the annual energy of cell `i` under member `m` in TWh/year, from the capacity `P_MW` of the central land scenario and the capacity factor of the member that F5 stores (`m0` is the reference member): `E_0 = sum over Omega_econ of E_i,m0`, `E_m = sum over Omega_econ of E_i,m`.
    - Target and slack: `G` is the national target of the technology in TWh/year (OQ-010), matched to the horizon of the core window and read from `experiments.yaml` `national_targets` (value, unit, source, horizon; null until OQ-010 closes). A target in GW, `G_cap`, is converted by `G = 8.76 * G_cap * CFbar`, where `CFbar` is the capacity-weighted reference capacity factor of the cells of `Omega_econ` taken in ascending order of `LCOE_i,f0` (ties by ascending `cell_id`, A-12) until their capacity reaches `G_cap` (a fractional last cell; a target above the capacity of `Omega_econ` takes all of it). The original unit and the conversion are reported with every result. `H_0 = E_0 - G`; the slack is a screening margin, because national targets usually count the total installed capacity including existing plants and the potential removes no cell occupied by a plant (L-023).
    - H5a, resource: `Delta E = max(0, E_0 - min over the core members m of E_m)` and `R_loss = Delta E / H_0`. The truncation makes the test one-sided (gains in some members do not offset losses in others); gains, the median over members and the member values are descriptive.
    - H5b, exposure: for each hazard channel `h` that has a threshold `theta_h` (`hazard_thresholds`, sourced in OQ-051), with indicator `Z_i,h,m`, a cell is exposed under member `m` when `Z_i,h,m >= theta_h` for at least one channel (union of channels: a cell with several channels above their thresholds counts once). `E_exp = max over the members m that carry the hazard channel of ( sum over Omega_econ of E_i,m * X_i,m )`, `R_exp = E_exp / H_0`. The same statistic with the reference values of the indicators (`*_ref`; the extreme-gust indicator does not vary between members and is its own reference) and the difference between the two are reported, to separate present exposure from the part added by climate change. Exposure is not damage: no cell is assumed to lose generation. A channel without a threshold is excluded from H5b and declared in the output (the list of the channels used and of the channels excluded); it does not block the others. The set of channels is fixed when OQ-051 is resolved, before any result. H5b is `not available` only when a member carries no hazard channel in the window (2071-2100, L-021) or no channel has a threshold.
    - Decision rule, `lambda = 0.20` (`hypothesis_rules.H5`): not testable if no target `G` is available (`E_0`, `Delta E` and `E_exp` are reported without ratios); target not met at reference if `H_0 <= 0` (`Delta E / G` and `E_exp / G` are reported as descriptive ratios, without verdict); otherwise H5a holds if `R_loss >= lambda`, H5b holds if `R_exp >= lambda`, and the verdict is supported (both), partially supported (resource) (only H5a), partially supported (exposure) (only H5b) or not supported (neither). A deterministic rule on computed shares, not a test of significance. The ratios measure materiality, not the probability of missing the target.
    - Sensitivities, reported beside the primary result and never changing the verdict (a change of verdict is a dependence on that choice): `lambda = 0.10`, with the continuous ratios; `tau` at the ends of its sourced range; the dynamic economic domain `Omega_econ,m = { i : LCOE_i,(m,s0) <= tau }` (the potential below `tau` of T-R12, reported separately from the fixed-domain loss); the restrictive and the permissive land scenarios, which change the capacity of every cell and so `E_0` and `H_0`; without the GCM that carries the TCR exception (M-F4-02 item 5); the 2071-2100 window for H5a (H5b `not available`); the hazard channels one by one, without summing overlapping cells; alternative official targets or horizons where they exist, and the alternative conversion of a capacity target by the capacity-weighted capacity factor of the whole of `Omega_econ`; the 0.1 degree scale (V-07). The member values and the identity of the members that attain the maxima are reported.
    - Computation: the energy of a member over `Omega_econ` and the potential below `tau` of T-R12 are the same calculation (T-R12 gains the series `fixed_domain`, the cells of `Omega_econ` evaluated in each member), and the exposed indicator of T-R10 is the one of H5b (`>=` the threshold, OQ-051): T-R10 and T-R12 use the calculations of H5, and F7 writes the tables `h5_summary` and `h5_members`.
- **M-F7-08. Scenario discovery.** PRIM, per country and technology, in the core window (text in `docs/thesis/methods/synthesis_and_scenario_discovery.tex`). The unit is the future `f = (m, s)` of the core window (every member times the draws `s >= 1`), not the cell. Outcome: with the nominal shortlist `S^nom_k` of H3 (the `k` cells of the ranked set `I` with the lowest `LCOE_i,f0`, `k` that of M-F7-05), `m = k` and `r^rank_i,f` the rank of cell `i` within `I` by relative regret in `f`, `V_f = ( sum of q_i over the cells i of S^nom_k with r^rank_i,f > k + m ) / ( sum of q_i over S^nom_k )`, `q_i` the capacity of the central land scenario. Within one future the reference level `L*_f` is common to all cells, so the order by relative regret is the order by `LCOE_i,f`, an infeasible cell last (ties by `cell_id`). A future is a case of interest when `V_f >= theta`, `theta = 0.20` (`prim.outcome_threshold`; the threshold and the tolerance are those of H1b and H3). Descriptors: the sampled techno-economic parameters of the draw, the GCM and the SSP as categorical variables, and the capacity-weighted means over `S^nom_k` of the change factors `delta_rsds`, `dT` and `delta_wind` of the member; land parameters are not descriptors. Settings (`prim`, Bryant and Lempert 2010; Friedman and Fisher 1999): peeling and pasting fraction `alpha = 0.05`, minimum support `0.05` of all futures, at most 3 restricted descriptors. Each box of the trajectory has `density = (cases in the box) / (futures in the box)` and `coverage = (cases in the box) / (all cases)`. Box choice, fixed before the results: `box* = argmax density` among the boxes of the trajectory with `coverage >= 0.50` and at most 3 restricted descriptors (ties: the larger support, then the earlier box). Special cases are reported as such and no box is chosen: `no_cases` (no future is a case of interest: no vulnerability under the futures evaluated), `all_cases` (every future is: a general property of the shortlist, not of particular conditions) and `no_eligible_box` (no box meets the coverage requirement: no simple explanation). Robustness: `B = 200` bootstrap replicates resample the futures with replacement and repeat the search with the same settings and rule; the seed is derived from the sampler seed and recorded in the provenance, so the same seed gives the same replicates. For the primary box F7 reports the 5th to 95th percentile over replicates of each bound, of density and of coverage, the share of replicates in which each descriptor is restricted (and of the categories kept), and the count of replicates in each special case. Sensitivities, reported beside the primary result: `theta` in {0.10, 0.30}, minimum coverage in {0.40, 0.60} and minimum support in {0.02, 0.10}. The PRIM of GeoFREA is checked against `ema_workbench` on stored cases (L-022). The box describes the futures evaluated, not the space of possible futures; boxes are axis-aligned; with six climate models a restricted GCM may reflect one model.
- **M-F7-09. Method agreement.** Kendall correlation between `MR` and `SR` rankings, supporting the RQ4 discussion.
- **M-F7-10. Streaming.** One future at a time, vectorized over cells, updating running maxima and counters; a full evaluation of all futures is never held in memory.
- **M-F7-11.** Outputs: `robustness_<tech>.parquet` (per cell: nominal LCOE and rank, MR, SR, climate-fragile flag and failing members, variance shares, top-k flags), `ssp_scores_<tech>.parquet` (per cell and SSP: `MR_i,sigma`, `R^clim_i,sigma`, their ranks, the top-k flag, the GCM responsible for `R^clim`), `h1_sites_<tech>.parquet` (per nominal top-k cell: vulnerable flag, displacement, SSP and GCM responsible, largest `R^clim`), `h1_summary_<tech>.parquet` (primary result and sensitivities: `C_k`, `V_k`, reference, verdict), `h2_summary_<tech>.parquet` (primary result and sensitivities: `O`, `O_ref`, `Delta_z`, `D_TV`, verdict, the decision profile), `h2_regions_<tech>.parquet` (per Admin1 region: capacity, mean and median `z`, within-region variance, fraction taken, share of `T` selected by each procedure), `h3_summary_<tech>.parquet` (primary result and sensitivities: `D`, `D_ref`, `Pi`, `B`, the capacities of the two shortlists, the diagnostics, verdict), `h3_sites_<tech>.parquet` (per cell of the union of the two shortlists: capacity, `LCOE_i,f0`, `MR_i`, nominal rank, robust rank, membership of each shortlist, whether the capacity counts in `D`), `h4_country_<tech>.parquet` (per setting: `D_clim`, `D_tec`, `D_sum`, `rho`, the profile, the joint `D`, the distances to the boundaries; the primary result, the climate axis by SSP and the sensitivities), `h4_verdict_<tech>.parquet` (written by `cross_country_h4`, one table per technology: per country the profile and its statistics, the count of countries by profile and the verdict), `h5_summary_<tech>.parquet` (per setting: `E_0`, `G` and its unit and conversion, `H_0`, `Delta E`, `R_loss`, `E_exp`, `R_exp`, the reference exposure and the increment, the status and the verdict; the primary result and the sensitivities), `h5_members_<tech>.parquet` (per member: `E_m`, the change against `E_0`, the exposed energy with the absolute and the reference indicators, and the exposed energy of each channel), hypothesis test tables, `prim_boxes_<tech>.parquet` (the peeling and pasting trajectory of the primary run, with the box chosen marked), `prim_box_<tech>.parquet` (per setting, the primary one and the sensitivities: the status, the box chosen with its density, coverage and support, and the limits of every descriptor) and `prim_bootstrap_<tech>.parquet` (the percentiles over replicates of the bounds, density and coverage, the restriction frequencies and the special cases), all for the core window.

### F7b external_validation

- **M-F7b-01.** Share of existing plant capacity (GEM trackers) located in excluded pixels, per exclusion constraint. Tests the exclusion set. The excluded share of each constraint at the pixel of a plant is evaluated by the pure eligibility engine of M-F3-01 on the aligned layers, not read from a stored layer.
- **M-F7b-02.** Enrichment ratio: share of existing capacity in the lowest nominal-LCOE deciles divided by the share of eligible area in those deciles.
- **M-F7b-03.** Comparison of national technical potential with published estimates, as a table with source and definition notes.
- **M-F7b-04.** Existing plants reflect past auctions, policy, and grid access. Results are plausibility evidence, not accuracy.

### F8 results_synthesis

- **M-F8-01.** F8 reads persisted artifacts and never recomputes a scientific quantity.
- **M-F8-02.** F8 produces every output of Section 10 into `outputs/thesis/`, with a fixed style and one script per output.
- **M-F8-03. Cross-country synthesis (T-R8).** Text in `docs/thesis/methods/synthesis_and_scenario_discovery.tex`. The synthesis reports what was observed and issues no aggregate verdict and no score (decision D6 of the F8 design report, closed): with three countries and two technologies a majority rule would present a few cases as a general conclusion and the threshold would weigh more than the evidence. It produces, from the persisted results (M-F8-01): (i) the profile of each country and technology (`hypothesis_profiles`, a structured JSON with a `schema_version`, one record per country and technology, the unit from which the thesis, the articles and a per-country platform page are built): the verdict of each hypothesis and its numbers (H1 `C_k`, `V_k` and `p_k^2`; H2 `O`, `O_ref` and `Delta_z`; H3 `D`, `D_ref`, `Pi` and `B`; H4 `D_clim`, `D_tec`, `rho` and the profile, with the verdict of the technology; H5 `E_0`, `G`, `H_0`, `R_loss` and `R_exp`), the size of the candidate set, `k`, and for every number its range across the sensitivity variants of its hypothesis (including the 2071-2100 window and the other cell scale where they exist) and the count of variants whose verdict differs from the primary one; (ii) the summary by hypothesis and technology: the number of countries in each verdict class (supported, partially supported, not supported, not testable and the special statuses of H5) and the label `consistent` (every testable case has the same verdict), `context-dependent` (the testable cases differ) or `not assessable` (fewer than two cases are testable). The partial classes of H1 and of H5 are kept distinct; a case without a verdict (no target, target not met at reference, no exposure) is not testable and is never a disagreement; H4 is shown as the verdict per technology with the three country profiles. A context-dependent pattern is a result: the conclusion does not transfer between national contexts without evidence from the context. The labels and the minimum number of testable cases are `synthesis` in `experiments.yaml` (pre-registered in OQ-050, T-R8, 2026-10-14). F8 also writes a readable summary per country (Markdown and LaTeX) with the numbers of H1 to H5 and their ranges.

### E1 explorer

- **M-E1-01.** Static, precomputed explorer by country, technology, window, SSP, GCM, and land-availability scenario, with per-cell query. Eligibility thresholds are adjustable only across the precomputed scenarios. Technology stack in OQ-013.

---

## 6. Uncertainty and futures design

- **U-01. Futures.** Full factorial of climate members (F4) and techno-economic samples (F6). Both axis identifiers are preserved in every F6 and F7 artifact. No probability is assigned across SSPs or GCMs. Land availability is not a factor of the futures (V1): its ranges are reported through U-06 and U-08.
- **U-02. Monte Carlo scope.** Sampling happens only within the parameter axis. Climate uncertainty is represented only by the discrete member set.
- **U-03. Uncertain parameters.** Declared in `config/experiments.yaml`. Default set: `capex_usd_per_kw`, `opex_fixed_frac`, `discount_rate`, `lifetime_years`, `degradation_rate`, `grid_cost_usd_per_mw_km`, `substation_cost_usd_per_mw`, `road_cost_usd_per_km`, `gamma` (solar), `eta_loss` (wind). `LUF` and `PD` affect capacity and are handled in a sensitivity outside the regret ensemble (OQ-004). `opex_fixed_frac` is the fixed O&M as a fraction of CAPEX per year. Parameters are sampled independently (L-012); no correlation is imposed without a sourced coefficient.
- **U-04. Sample size.** Protocol: start at 500 samples, double until `1 - Jaccard` of the top-k sets by `MR` between consecutive sizes is below 0.01 for all countries and technologies; the adopted size is the larger size of the first pair that agrees, and is recorded in the F6 phase record. `MR` is the definitive relative max-regret of F7 (M-F7-02, M-F7-03).
- **U-05. Parameter schema.** Every scientific parameter in `config/parameters.json` is an object:

```json
{
  "value": "<nominal value>",
  "unit": "<unit>",
  "source": "<primary source>",
  "tier": 1,
  "range": {
    "min": "<min>",
    "max": "<max>",
    "distribution": "uniform",
    "source": "<source of the range>",
    "tier": 2
  },
  "proxy": false,
  "verified": false,
  "verified_by": null,
  "verified_date": null,
  "verification_method": "unverified"
}
```

  `range` is `null` for parameters that are not uncertain. Every parameter listed in `experiments.yaml` must have a non-null `range`, enforced by schema validation. `proxy` is true only when the value is of a different quantity or a different technology (for example, wind fixed O&M taken from solar O&M for BRA and IND, OQ-016); regional or global transfers of the same quantity and technology are Tier 2 (U-07), not proxies. A production run fails if a consumed parameter has `proxy = true`; Tier 3 values and unsourced ranges raise a warning only.
- **U-06. Land-availability scenarios.** Three named scenarios, declared in `experiments.yaml` and composed in `docs/phases/F3_land_eligibility.md`: `central`; `restrictive` (every range with status `sourced` at its restrictive end); `permissive` (every sourced range at its permissive end). Parameters without a sourced range stay central in all three and are listed as such; they join the scenarios when a source is recorded (OQ-049). `central` feeds F4-F7. Land stays in every potential output (eligible area, GW, TWh, LCOE, supply curves) and is removed only from the set of futures over which F7 computes regret (V1). The full factorial of the land parameters that have a range is used only to report ranges (V2). Land ranges are reported as the interval of the potential outputs and as candidate-set stability (M-F3-04).
- **U-07. Evidence tiers.**
  - Tier 1: primary source specific to the country and technology, or a physical standard or constant.
  - Tier 2: primary source transferred from another region or a global value, with the transfer rationale recorded.
  - Tier 3: author judgment or no source. Every Tier 3 value is listed in `docs/LIMITATIONS.md`.
- **U-08. Reporting rule.** Every main result is reported as a central value with its range, stating which axis the range comes from: land scenarios (U-06), parameter samples (U-03) or climate members (U-01).

---

## 7. Architecture requirements

- **A-01. DAG orchestration.** Each `PhaseSpec` declares `requires` and `produces` artifact keys. The orchestrator validates the graph at startup (missing producers, cycles) and orders phases topologically. Phases exchange data only through declared artifacts.
- **A-02. Artifact registry.** The per-country manifest records, for each artifact: path, content hash, schema version, producing phase, run ID; and, for each phase entry, the METHODOLOGY version. A re-registered artifact with an unchanged content hash keeps the run ID that first produced it, and a consumer is marked stale only by an artifact whose content hash changed. A phase whose upstream is not part of the current run loads upstream artifacts from the manifest. In-memory coupling between phases is not allowed.
- **A-03. Run targeting.** `settings.yaml` declares `run.target_phases`, `run.countries`, `run.technologies`, and `run.rerun_phases`; dependencies are resolved from the DAG. `rerun_phases` re-executes exactly the phases it names; every phase downstream of a named phase that currently holds a successful manifest entry is marked stale and recomputed automatically the next time a run needs it, rather than being re-executed in the same pass (see `docs/phases/core.md` D-core-012). Per-phase boolean toggles are not used.
- **A-04. Technology registry.** `config/technologies.yaml` declares per technology: resource layers, capacity-factor model, exclusion set, cost structure, uncertain-parameter keys, required-parameter keys (the F5 inputs that are not uncertain, whose absence a production run refuses), and for wind the IEC class rule and the map from class to power-curve id. F5-F7 code contains no technology names.
- **A-05. Country agnosticism.** All country-specific mappings (data-source regions, file names, GRIP4 regions, HydroSHEDS regions) live in `config/countries.yaml`. A test fails if an ISO3 code literal appears in `src/` outside comments and docstrings.
- **A-06. Synthetic country.** A small synthetic country fixture runs every built phase in CI and is extended in the same change that builds a phase; a phase does not close its milestone (Section 12) until it runs on the fixture. The fixture provides the protected-area, lake and river layers (M-F2b-05).
- **A-07. Formats.** Rasters are Cloud Optimized GeoTIFF, EPSG:4326. Tables are parquet with a Pydantic schema and a `schema_version`. Run ID = hash of configuration, methodology version, and code commit.
- **A-08. Outputs layout.** All data stored in GEOFREA_DATA_DIR (environment variable, never under repository root). Structure:
  - `raw/<source>/<ISO3|_global>/`: fetched raw data (GADM, HydroSHEDS, GEM trackers, WDPA, GWA)
  - `interim/<ISO3>/<layer>/`: intermediate processing caches
  - `outputs/<ISO3>/manifest.json`: run manifest per country
  - `outputs/<ISO3>/<phase>/<kind>/`: phase outputs (artifacts, figures, reports); a run at a scale other than 0.05 degree (M-F3-06) writes the phases that depend on the cell size (F3 onward, `overview`) under `<phase>__<scale>` (for example `land_eligibility__0p1deg`) and its manifest as `manifest__<scale>.json`
  - `outputs/thesis/`: F8 only
  - `reference/legacy_baseline_fc7b43d/`: frozen legacy results (read-only)
  - `logs/<ISO3>/`: per-country run logs

  One map per file. `settings.yaml` `figures: all | summary | none`. Member-level maps exist only for F4 and F5; F6 and F7 maps show summaries (nominal, median, p10, p90, MR, SR).
- **A-09. Failure policy.** Fail-loud; no silent fallback. A failure stops the phases that depend on it; independent branches may complete.
- **A-10. Memory.** F6 and F7 process in batches under `settings.yaml` `memory.max_batch_gb`.
- **A-11. Reuse from reference repositories.** CRAEI (primary climate-risk codebase, source for climate data acquisition and hazard processing) is the only reuse source under the copy-and-adapt rule: code may be copied into GeoFREA and adapted with a provenance header (repository, commit SHA, original path, adaptation summary). No imports from reference repositories, no shared package, no edits to CRAEI. `CRAEI_BASELINE_DIR` is read-only. geoworld_framework is consulted for logic only, never ported line by line.
- **A-12. Determinism.** Seeds are recorded in the manifest; reruns with identical run ID reproduce identical artifacts on the same platform. The run environment (`GEOFREA_DATA_DIR`, `GEOFREA_SHARED_RAW_DIR`, and the other location variables) is declared in `.env.example` and loaded at startup, not assumed from an undocumented shell state.
- **A-13. Traceability.** Functions implementing a method item cite it in the docstring (`Implements: M-F5-03.`).

---

## 8. Validation and testing

- **V-01. Frozen regression.** Binary and float parity against frozen GeoFREA fixtures for F1 outputs, F2a aligned rasters, and exclusion layers E1-E3. Binary layers: exact parity. Float rasters: `rtol = 1e-6` unless a documented platform difference requires a larger bound. Fixtures are refrozen only with Douglas's authorization, recorded in the phase record.
- **V-02. Analytical tests.** CRF and LCOE closed forms; Weibull CF against numerical integration; PVOUT to CF units; geodesic areas against reference values; power-law height interpolation.
- **V-03. Invariants.** `r_i,f >= 0`; `MR_i >= 0`; at least one feasible cell with `r = 0` per future when `q_ref = 0`; every cell of the F7 set is either ranked or in the climate-fragile class, and no ranked cell has an infinite MR; `0 <= SR <= 1`; `0 <= CF <= 1`; `eligible_area <= cell_area`; country capacity equals the sum of cell capacities.
- **V-04. Sanity ranges.** Configured physical ranges for every resource layer and derived quantity; violations are reported by F1b and raise in F5.
- **V-05. Convergence.** U-04.
- **V-06. No calibration on validation data.** No parameter is fitted to existing plants. If a future version fits any parameter to plants, a spatial train and test split becomes mandatory for that parameter.
- **V-07. Scale check.** F3 to F7 rerun at 0.1 degree through the `scale` parameter of the run (M-F3-06), with the same code and no scale-specific branch; H1 to H3 statistics reported side by side (MAUP).
- **V-08. Synthetic end-to-end.** A-06 in CI, through the last built phase; the test is extended with each phase built.

---

## 9. Configuration files

| File | Content |
|---|---|
| `config/parameters.json` | Scientific parameters per country and technology, schema U-05 |
| `config/technologies.yaml` | Technology registry, A-04 |
| `config/power_curves/<curve_id>.yaml` | One reference power curve per file, with provenance (M-F5-03); no real curve until OQ-005 closes |
| `config/countries.yaml` | Country-specific data mappings, A-05 |
| `config/experiments.yaml` | Members, windows, uncertain parameters, sampler, seed, sample size, land-availability scenarios, top-k, thresholds |
| `config/settings.yaml` | Operational settings: run targeting, grid resolution, figures, memory, paths |
| `config/audit.yaml` | data_quality_audit (F1b) diagnostic-gate configuration: expected native resolution, sanity range and unit per layer, each with a primary source or null with an open question (M-F1b-01) |

---

## 10. Thesis outputs

Only these outputs belong to the dissertation. Every other file is a pipeline artifact.

| ID | Type | Phase | Content | Answers | Status |
|---|---|---|---|---|---|
| T-M1 | Figure | none | Framework DAG with the member and sample axes | RQ0 | Essential |
| T-M2 | Table | config | Exclusion constraints, cost drivers, resource models, parameters with sources and tiers | RQ2 | Essential |
| T-M3 | Table | config | Futures design: members, uncertain parameters with nominal, range, source, tier, per country | RQ4 | Essential |
| T-R1 | Figure | F5 | Technical potential maps (MW/km² of cell) at reference climate, country by technology | RQ1 | Essential |
| T-R2 | Table | F5 | Eligible area, GW, TWh/yr at reference; range across members; interval across the land-availability scenarios | RQ1, RQ3 | Essential |
| T-R3 | Figure | F4, F5 | CF change by SSP, core window (median over the GCMs of the SSP), with GCM agreement marking: a cell is marked when at least two thirds of the GCMs agree on the sign of the change of the capacity factor (the convention of the IPCC AR6 WGI Atlas, Section 13; a zero change agrees with no sign) | RQ3 | Essential |
| T-R4 | Figure | F7 | Max-regret map per country, with intra-country distribution panel against the national aggregate | RQ4, H2 | Essential |
| T-R5 | Figure | F7 | Nominal versus robust rank, top-k stability across SSPs | H1, H3 | Essential |
| T-R6 | Table | F7 | H1 to H5 statistics and verdicts, one row per hypothesis (H5 with its two statistics, `R_loss` and `R_exp`, as H1 has `C_k` and `V_k`); rows for 2071-2100 and 0.1 degree | H1, H2, H3, H4, H5 | Essential |
| T-R7 | Figure | F7 | Climate and techno-economic displacement (`D_clim`, `D_tec`) and the dominance ratio `rho` by country and technology, boundaries 0.40 and 0.60 marked | H4 | Essential |
| T-R8 | Table | F8 | Cross-country synthesis (M-F8-03): country and technology profiles with verdicts, numbers and ranges over the sensitivity variants (from the structured `hypothesis_profiles`), and the summary by hypothesis and technology with the count by verdict class and the label consistent, context-dependent or not assessable; no aggregate verdict | RQ5 | Essential |
| T-R9 | Table | F7b | External validation | RO5 | Essential |
| T-R10 | Table | F4, F5, F7 | Hazard context exposure of nominal and robust top-k cells and of all eligible potential (GW and TWh in cells above the hazard exposure thresholds, OQ-051), by SSP and window; the wording is "exposed", and "lost" only for a hazard whose loss function passed OQ-007; the exposed indicator is the one of H5b (M-F7-07) | RQ3, H4, H5 | Essential |
| T-R11 | Figure | F6 | LCOE map at reference | RQ2 | Essential |
| T-R12 | Table | F5, F6 | Potential (GW, TWh) below the cost threshold `tau` (OQ-008) per member, compared with the national targets (OQ-010); the energy of the fixed economic domain is the one of H5a (M-F7-07) | RQ3, H5 | Essential |
| T-O1 | Figure | F7 | PRIM scenario discovery box (M-F7-08): the limits of the descriptors of the box chosen, with the 5th to 95th percentile over the bootstrap replicates and the share of replicates that restrict each descriptor | RQ4 | Optional |
| T-O2 | Figure | F7 | Agreement between MR and SR rankings | RQ4 | Optional |
| T-O3 | Figure | F6 | Supply curves at nominal parameters, by SSP and window | RQ2 | Essential |

Reporting rule for the climate outputs: climate effects on potential are computed at the fixed central land set, and the land range is reported beside them (U-08).

---

## 11. Diagnostic figures

Per-phase maps are diagnostics for inspection and for the future platform, generated under A-08. Minimum set per country and technology: F2b exclusion layers and cost-driver layers; F3 eligible fraction and dominant exclusion; F4 change factors per member; F5 CF and capacity per member; F6 nominal and median LCOE; F7 MR, SR, top-k flags.

---

## 12. Implementation roadmap

Sequenced by dependency; each milestone closes before the next opens, except where marked parallel. The state of each milestone, phase and country lives only in `docs/PROGRESS.json` (CONVENTIONS, "Where status lives").

| Milestone | Content | Gate |
|---|---|---|
| MS-0 | Planning adopted; records migrated; repository restructured | This document committed |
| MS-1 | Core: A-01 to A-03, A-05, configuration schemas (U-05, Section 9) | Tests for DAG validation and ISO3 literal check pass |
| MS-2 | F1 and F1b conformance, including India wiring and new wind and CMIP6 products | F1-F2a run for BRA, PRT, IND |
| MS-3 | F2a conformance | V-01 fixtures refrozen and passing |
| MS-4 | F2b rebuild as `siting_layers` | Exclusion parity E1-E3; sanity ranges pass for three countries |
| MS-5 | F3 | Closes with the three named scenarios of U-06 (V2), the 10 m land cover for IND (M-F2a-06, V19) and a clean rerun in BRA, PRT and IND; candidate tables for three countries and two technologies |
| MS-6 | Parameter research, in parallel with MS-4 and MS-5, by priority: F5 first (OQ-004, OQ-005, OQ-023), then F6 (OQ-001, OQ-016 to OQ-019, OQ-022), then F7 (OQ-008, OQ-010, OQ-020, OQ-021); also OQ-051 | Every uncertain parameter has range and tier |
| MS-7 | F4, including GCM selection | Forcing tables for the selected ensemble |
| MS-8 | F5: code and tests on the synthetic country before real values; real execution only with parameter values recorded under MS-6 | V-02, V-03 pass |
| MS-9 | F6, including sampling (U-02), convergence (U-04) and batches (A-10) | U-04 convergence recorded |
| MS-10 | F7 and F7b | H1-H5 tables for three countries |
| MS-11 | F8 and E1 | All essential outputs generated |

A-06 and V-08 are extended with every phase that exists: no milestone from MS-5 on closes without its phase running on the synthetic country.

---

## 13. References to verify

Full bibliographic details must be confirmed during the literature review before citation in the thesis.

- Bertsimas, D., and Sim, M. (2004). The price of robustness (Operations Research 52(1):35-53). doi:10.1287/opre.1030.0065
- Birge, J. R. (1982). The value of the stochastic solution in stochastic linear programs with fixed recourse (Mathematical Programming 24(1):314-325). doi:10.1007/BF01585113
- Brown, A., Beiter, P., Heimiller, D., Davidson, C., Denholm, P., Melius, J., Lopez, A., Hettinger, D., Mulcahy, D., and Porro, G. (2015). Estimating renewable energy economic potential in the United States: methodology and initial results (NREL/TP-6A20-64503). Verify.
- Bryant, B. P., and Lempert, R. J. (2010). Thinking inside the box: a participatory, computer-assisted approach to scenario discovery (Technological Forecasting and Social Change 77(1): 34-49). Verify.
- Corsi, M., et al. (2024). Ranking with near-ties (title and venue to be confirmed). Verify.
- DeCarolis, J. F. (2011). Using modeling to generate alternatives (MGA) to expand our thinking on energy futures (Energy Economics). Verify.
- Deshmukh, R., et al. (2019). Geospatial and techno-economic analysis of wind and solar resources in India (Renewable Energy).
- Fagin, R., Kumar, R., and Sivakumar, D. (2003). Comparing top k lists (SIAM Journal on Discrete Mathematics). Verify.
- Friedman, J. H., and Fisher, N. I. (1999). Bump hunting in high-dimensional data (Statistics and Computing 9: 123-143). Verify.
- Frysztacki, M. M., Hörsch, J., Hagenmeyer, V., and Brown, T. (2021). The strong effect of network resolution on electricity system models with high shares of wind and solar (Applied Energy). Verify.
- Gotway, C. A., and Young, L. J. (2002). Combining incompatible spatial data (Journal of the American Statistical Association). Verify.
- Gutiérrez, J. M., Jones, R. G., Narisma, G. T., et al. (2021). Atlas. In: Climate Change 2021: The Physical Science Basis, Contribution of Working Group I to the Sixth Assessment Report of the IPCC (Cambridge University Press). Verify.
- Hausfather, Z., et al. (2022). Climate simulations: recognize the hot model problem (Nature).
- Hawkins, E., and Sutton, R. (2009). The potential to narrow uncertainty in regional climate predictions (Bulletin of the American Meteorological Society 90(8):1095-1107). doi:10.1175/2009BAMS2607.1. Verify pages.
- Herman, J. D., et al. (2015). How should robustness be defined for water systems planning under change? (Journal of Water Resources Planning and Management).
- Hörsch, J., and Brown, T. (2017). The role of spatial scale in joint optimisations of generation and transmission for European highly renewable scenarios (International Conference on the European Energy Market). Verify.
- IAEA (2019). Adapting the energy sector to climate change (IAEA; title and series number to be confirmed). Verify.
- IEC 61400-1 and IEC 61400-12-1.
- IPCC AR6 WGI (2021), reference period 1995-2014.
- IPCC (2022). Climate Change 2022: Impacts, Adaptation and Vulnerability. Contribution of Working Group II to the Sixth Assessment Report (Cambridge University Press). Verify.
- Jerez, S., et al. (2015). The impact of climate change on photovoltaic power generation in Europe (Nature Communications 6:10014). Verify.
- Javanmardi, E., et al. (2025). Spatial representation in energy system models (title and venue to be confirmed). Verify.
- Jordan, D. C., and Kurtz, S. R. (2013). Photovoltaic degradation rates (Progress in Photovoltaics).
- Kwakkel, J. H., Walker, W. E., and Haasnoot, M. (2016). Coping with the wickedness of public policy problems: approaches for decision making under deep uncertainty (Journal of Water Resources Planning and Management). Verify.
- Lempert, R. J., and Collins, M. T. (2007). Managing the risk of uncertain threshold responses: comparison of robust, optimum, and precautionary approaches (Risk Analysis 27(4):1009-1026). doi:10.1111/j.1539-6924.2007.00940.x
- Lempert, R. J., Popper, S. W., and Bankes, S. C. (2003). Shaping the Next One Hundred Years (RAND).
- Lopez, A., et al. (2012). U.S. Renewable Energy Technical Potentials (NREL).
- Maclaurin, G., et al. (2019). The Renewable Energy Potential (reV) Model (NREL).
- Marchau, V. A. W. J., Walker, W. E., Bloemen, P. J. T. M., and Popper, S. W. (eds.) (2019). Decision Making under Deep Uncertainty: From Theory to Practice (Springer). Verify.
- McKay, M. D., et al. (1979). Latin hypercube sampling (Technometrics).
- McKenna, R., et al. (2022). High-resolution large-scale onshore wind energy assessments: a review (Renewable Energy).
- McPhail, C., et al. (2018). Robustness metrics (Earth's Future).
- Mercure, J.-F., and Salas, P. (2012). An assessment of global energy resource economic potentials (Energy 46(1):322-336). Verify.
- Neumann, F., and Brown, T. (2021). The near-optimal feasible space of a renewable power system model (Electric Power Systems Research 190:106690).
- Openshaw, S. (1984). The Modifiable Areal Unit Problem (CATMOG 38, Geo Books). Verify.
- Pryor, S. C., and Barthelmie, R. J. (2010). Climate change impacts on wind energy: a review (Renewable and Sustainable Energy Reviews 14(1):430-437). Verify.
- Pfenninger, S., Hawkes, A., and Keirstead, J. (2014). Energy systems modeling for twenty-first century energy challenges (Renewable and Sustainable Energy Reviews). Verify.
- Robinson, W. S. (1950). Ecological correlations and the behavior of individuals (American Sociological Review). Verify.
- Ryberg, D. S., et al. (2018). Evaluating land eligibility constraints of renewable energy sources in Europe (Energies).
- Pianosi, F., Beven, K., Freer, J., Hall, J. W., Rougier, J., Stephenson, D. B., and Wagener, T. (2016). Sensitivity analysis of environmental models: A systematic review with practical workflow (Environmental Modelling & Software 79:214-232). doi:10.1016/j.envsoft.2016.02.008
- Saltelli, A., et al. (2008). Global Sensitivity Analysis: The Primer (Wiley). Verify.
- Savage, L. J. (1951). The theory of statistical decision (Journal of the American Statistical Association).
- Skoplaki, E., and Palyvos, J. A. (2009). On the temperature dependence of photovoltaic module electrical performance: a review of efficiency/power correlations (Solar Energy 83(5):614-624). Verify.
- Solargis / World Bank ESMAP. Global Solar Atlas PVOUT metadata (2025).
- Staffell, I., and Green, R. (2014). How does wind farm performance decline with age? (Renewable Energy).
- Tröndle, T., Lilliestam, J., Marelli, S., and Pfenninger, S. (2020). Trade-offs between geographic scale, cost, and infrastructure requirements for fully renewable electricity in Europe (Joule). Verify.
- Ueckerdt, F., Hirth, L., Luderer, G., and Edenhofer, O. (2013). System LCOE: what are the costs of variable renewables? (Energy 63:61-75). Verify.
- Webber, W., Moffat, A., and Zobel, J. (2010). A similarity measure for indefinite rankings (ACM Transactions on Information Systems). Verify.
- Wu, G. C., et al. (2017). Strategic siting and regional grid interconnections (PNAS).

---

## 14. Changelog

| Version | Date | Change |
|---|---|---|
| 13.0.1 | 2026-10-14 | PATCH (closes the open points of 13.0.0 and of the H5 rule; no pre-registered threshold changes): (1) H5b uses the hazard channels that have a threshold sourced in OQ-051; a channel without a threshold is excluded and declared in the output (channels used and excluded) and does not block the others; H5b is not available only when no channel has a threshold or no member carries the hazard channel; the set of channels is fixed when OQ-051 is resolved, before the results (M-F7-07, H5 block). (2) The national target has one source, `national_targets` of `experiments.yaml`; the target of the top-k sensitivity is derived from it when its unit is GW and is not testable when it is in TWh/year; `capacity_target_gw` leaves `parameters.json` (M-F7-05). (3) The roadmap line MS-6 no longer cites OQ-050, which is closed. (4) T-R3 fixes its agreement marking: a cell is marked when at least two thirds of the GCMs agree on the sign of the change of the capacity factor (D2 of the F8 design report); Section 13 gains the IPCC AR6 WGI Atlas, marked verify. IDs altered: M-F7-05, M-F7-07, MS-6, T-R3. |
| 13.0.0 | 2026-10-14 | MAJOR (changes a result definition): the synthesis of T-R8 and the scenario discovery are pre-registered (OQ-050, aggregation rule of T-R8; OQ-056). New M-F8-03 and T-R8: the synthesis issues no aggregate verdict; it produces the profile of each country and technology (verdict and numbers of H1 to H5, the range over the sensitivity variants and the count of variants that change the verdict) as the structured `hypothesis_profiles`, and the summary by hypothesis and technology with the count by verdict class and the label consistent, context-dependent or not assessable (fewer than two testable cases), with the partial classes of H1 and H5 kept apart, a case without a verdict never a disagreement and H4 shown as the verdict per technology with the three profiles; D6 of the F8 design report is closed. M-F7-08 is rewritten: the unit is the future of the core window, the outcome is the capacity share `V_f` of the nominal shortlist `S^nom_k` (over the ranked set, as in H3) whose rank by relative regret in the future exceeds `k + m`, `m = k`, a case of interest being `V_f >= 0.20`; the descriptors are the sampled parameters, the GCM and the SSP and the capacity-weighted change factors over `S^nom_k`; `alpha = 0.05`, minimum support 0.05, at most 3 restricted descriptors; the box is the one of highest density with coverage of at least 0.50; the special cases no_cases, all_cases and no_eligible_box; a bootstrap of 200 replicates with a seed derived from the sampler seed (percentile ranges of bounds, density and coverage, restriction frequencies); sensitivities `theta` {0.10, 0.30}, coverage {0.40, 0.60}, support {0.02, 0.10}. M-F7-11 gains `prim_box` and `prim_bootstrap` and the trajectory table marks the box chosen. T-R8 and T-O1 are reworded. Section 13 gains Friedman and Fisher (1999) and the full details of Bryant and Lempert (2010), marked verify. The sentence of M-F7-07 on the aggregation rule now points to M-F8-03. IDs cited and not altered: M-F7-05, M-F8-01, M-F8-02, H1, H3, L-022, OQ-050, OQ-056. |
| 12.0.0 | 2026-10-14 | MAJOR (changes a result definition): the decision rule of H5 is pre-registered (OQ-050, part H5). H5 in 1.3 and the H5 block of M-F7-07 now define the domain `Omega` (the F7 set, like-for-like, climate-fragile cells kept), the fixed economic domain `Omega_econ` (`LCOE_i,f0 <= tau`, OQ-008), the annual energy per cell and member, `E_0`, the target `G` in TWh/year (OQ-010) with the conversion of a capacity target by the capacity-weighted capacity factor of the cheapest cells, the slack `H_0 = E_0 - G`, H5a (`Delta E = max(0, E_0 - min E_m)`, `R_loss = Delta E / H_0`), H5b (exposure by the union of the hazard channels, OQ-051, `E_exp` as the maximum over the hazard members, `R_exp = E_exp / H_0`, the reference exposure and the increment), the threshold `lambda = 0.20`, the statuses not testable (no target) and target not met at reference (`H_0 <= 0`, descriptive ratios on `G`), the verdict supported, partially supported (resource), partially supported (exposure) or not supported, and the sensitivities (`lambda` 0.10, the ends of the range of `tau`, the dynamic domain, the land scenarios, without the TCR-exception GCM, 2071-2100 for H5a only, the channels one by one, alternative targets and conversions, 0.1 degree). T-R10 and T-R12 are stated to use the calculations of H5, with `>=` as the comparison of the exposure threshold and the series `fixed_domain` in T-R12. M-F7-11 gains `h5_summary` and `h5_members`. T-R6 gains the H5 row. Section 13 gains Ueckerdt et al. (2013), Skoplaki and Palyvos (2009), Mercure and Salas (2012), Brown et al. (2015), IAEA (2019), IPCC (2022), Jerez et al. (2015) and Pryor and Barthelmie (2010), marked verify. IDs cited and not altered: M-F4-02, M-F7-02, M-F7-05, V-07, A-12, L-021, L-023, OQ-007, OQ-008, OQ-010, OQ-050, OQ-051. |
| 11.0.1 | 2026-10-13 | PATCH (closes the open points of 11.0.0, no result definition changes): the verdict `not testable` of H4 (fewer than two countries with a profile, otherwise not supported) is now in the text of the hypothesis (`H4_axis_dominance.tex`, after `eq:h4_rule`) and in the H4 block of M-F7-07, which closes D-F7-048; the equation `eq:h4_rule` is broken in an `aligned` block to fit the margin (same statement). Section 13: Bertsimas and Sim (2004), Birge (1982), Hawkins and Sutton (2009), Lempert and Collins (2007) and Pianosi et al. (2016) carry the DOI, and Pianosi et al. the full author list; Neumann and Brown (2021) confirmed; all lose the verify mark except the pages of Hawkins and Sutton. IDs cited and not altered: M-F7-07, OQ-050. |
| 11.0.0 | 2026-10-13 | MAJOR (changes a result definition and the phase list): the decision rule of H4 is pre-registered (OQ-050, part H4). H4 in 1.3 and the H4 block of M-F7-07 now define the profile of a country and technology from the dominance ratio `rho = D_clim / (D_clim + D_tec)` (No Displacement, Climate-Dominated above 0.60, Techno-Economic-Dominated below 0.40, Mixed between, inclusive) and the strict verdict per technology across countries (supported, not supported, not testable), with the complementary evidence (joint `D`, `D_clim` by SSP, distances to the boundaries) and the sensitivities (without the TCR-exception GCM, 2071-2100, 0.1 degree, `p_k`, `m`, the boundaries {0.30, 0.70} and {0.45, 0.55} as descriptive variants). M-F7-06 is rewritten: the primary statistics are the displacements `D_clim` and `D_tec`, the H3 statistic on the shortlists of `Z_clim` and `Z_tec`; the variance decomposition and the Jaccard overlap become descriptive. M-F7-11 gains `h4_country` and `h4_verdict`. The support phase `cross_country_h4`, which takes the list of countries, is added to 4.1 and 4.2. T-R6 and T-R7 are reworded to the H1 to H4 verdicts and to the displacements and `rho` by country. Section 13 gains Hawkins and Sutton (2009), Pianosi et al. (2016) and Saltelli et al. (2008), marked verify. IDs cited and not altered: M-F4-02, M-F5-01, M-F7-02, M-F7-03, M-F7-05, V-07, OQ-050. |
| 10.0.0 | 2026-10-13 | MAJOR (changes a result definition): the decision rule of H3 is pre-registered (OQ-050, part H3). H3 in 1.3 and the H3 block of M-F7-07 now define the domain `I` for both rankings, the robust shortlist `S_k` (the same as the target of H2), the nominal rank `r^nom` by `LCOE_i,f0` within `I`, the statistic `D` (share of the capacity of `S_k` with `r^nom > k + m`, `m = k`), the reference `D_ref = 1 - (k + m) / |I|`, the verdict not testable, supported or not supported with `delta = 0.20`, the magnitudes `Pi` (price of robustness, relative, at `f0`) and `B` (reduction of the capacity-weighted `MR`) without verdict, the diagnostics (geodesic distance between centroids, `D_TV` by Admin1, Spearman of `LCOE_i,f0` against `MR_i`, Jaccard by count) and the sensitivities (without the TCR-exception GCM, 2071-2100, 0.1 degree, `p_k` in {0.05, 0.10, 0.20}, `m` in {k/2, 2k}). The statistics of the earlier H3 become descriptive rows. M-F7-11 gains the tables `h3_summary` and `h3_sites`. Section 13 gains Bertsimas and Sim (2004), Birge (1982), DeCarolis (2011, verify), Lempert and Collins (2007) and Neumann and Brown (2021). IDs cited and not altered: M-F4-02, M-F5-01, M-F7-05, V-07, OQ-050. |
| 9.0.1 | 2026-10-13 | PATCH (wording; closes D-F7-042): the H1 and H2 blocks of M-F7-07 state that `k` is computed on `N = |I_0|`, the size of the F7 set including the climate-fragile cells, which is what M-F7-05 and the code already did; the thesis texts of H1 and H2 say the same. No result changes. IDs cited and not altered: M-F7-05. |
| 9.0.0 | 2026-10-13 | MAJOR (changes a result definition): the decision rule of H2 is pre-registered (OQ-050, part H2). H2 in 1.3 and the H2 block of M-F7-07 now define the score `z_i = MR_i`, the capacity `q_i`, the target `T` of the H1 top-k set, the cell and the Admin1 selections (capacity-weighted mean, fractional last region), the Capacity Overlap Index `O`, the reference `O_ref = T / Q_max`, the verdict not testable, supported or not supported with `gamma = 0.30`, the diagnostics without verdict (`Delta_z`, within-region variance, IQR over median, `D_TV`; the old dispersion statistics become descriptive) and the sensitivities. The H1 block of M-F7-07 draws the nominal set from the F7 set `I_0` so that a climate-fragile site of the nominal top-k counts as vulnerable. M-F7-11 gains the tables `h2_summary` and `h2_regions`. Section 13 gains the references of the H1 and H2 texts, marked verify. IDs cited and not altered: M-F3-05, M-F4-02, M-F5-01, M-F7-05, OQ-010, OQ-050. |
| 8.0.0 | 2026-10-13 | MAJOR (changes a result definition): the decision rule of H1 is pre-registered (OQ-050, part H1) and replaces the statistics of the old text. H1 in 1.3 and the H1 block of M-F7-07 now define the scores per SSP (`MR_i,sigma`, `R^clim_i,sigma`), H1a with `C_k >= alpha` (0.60) and the reference `p_k^2`, H1b with `V_k >= beta` (0.20) and `m = k`, the verdict supported, partially supported or not supported, the descriptive metrics without verdict (pairwise Jaccard, RBO with `p = 1 - 1/k`, displacement, median and IQR; the old Spearman and member-leaving statistics move here) and the mandatory sensitivities. M-F7-11 gains the tables `ssp_scores`, `h1_sites` and `h1_summary`. The thesis text is stored in `docs/thesis/hypotheses/`. IDs cited and not altered: M-F7-02, M-F7-03, M-F7-05, M-F7-06, M-F4-02, V-07, OQ-050, OQ-021. |
| 7.2.2 | 2026-10-12 | PATCH (status leaves the roadmap): Section 12 loses the State column and the dated state sentence and points to `docs/PROGRESS.json`, the only place where status lives (CONVENTIONS, "Where status lives"); the MS-6 row loses its list of resolved questions. Content and gates are unchanged. IDs cited and not altered: MS-0, MS-1, MS-2, MS-3, MS-4, MS-5, MS-6, MS-7, MS-8, MS-9, MS-10, MS-11, A-06, V-08. |
| 7.2.1 | 2026-10-09 | PATCH (two registered support phases had no mention): Sections 4.1 and 4.2 list `lcoe_maps` (after F6; COG and maps of the LCOE at the reference member, by SSP, and the supply curve) and `robustness_maps` (after F7; COG and maps of the F7 results per window) as support phases, drawn as `settings.yaml` `figures` allows, rasters always written (A-08). IDs cited and not altered: A-01, A-07, A-08, T-R4, T-R11. |
| 7.2.0 | 2026-10-09 | MINOR (verdicts of 2026-10-09 on `docs/_audit/2026-10_F7_design.md`, recorded as D-F7-006 to D-F7-033 in `docs/phases/F7_robustness_analysis.md` and D-F7b-002 to D-F7b-007; no existing result is redefined, F7 and F7b are not built yet): M-F7-01 evaluates feasibility on `CF(m, s0)` through an energy floor in the kernel; M-F7-02 fixes the set of `L*`; M-F7-05 fixes the base of `k`, the ties, the truncation and the capacity-target reading; M-F7-06 defines the two criteria of the primary comparison; M-F7-08 gives the PRIM outcome per future; M-F3-03 adds `admin1_id`; M-F3-05 and M-F7b-01 state that the excluded shares of the pixels are not persisted and F7b evaluates the eligibility engine at the plant pixels; M-F3-06, M-F4-04, V-07 and A-08 make the cell size a run parameter (`scale`) of F3 to F7; M-F6-06 adds the nominal LCOE of the restrictive and permissive scenarios. IDs cited and not altered: M-F3-01, M-F6-01, M-F7-03, M-F7-07, OQ-008, OQ-010, OQ-020, OQ-021, OQ-056, U-08, V1, A-12. |
| 7.1.3 | 2026-10-09 | PATCH (verdicts of 2026-10-09 on the F6 commits): M-F7-03 states that the P90 over parameter samples uses only the draws `s >= 1`, the nominal vector entering only the nominal ranking (D-F6-003); U-04 states the convergence criterion as `1 - Jaccard` of the top-k sets of consecutive sizes below 0.01, adopting the larger size of the first pair that agrees, with the definitive F7 `MR` as the metric (D-F6-004; OQ-055 closed). IDs cited and not altered: M-F7-05, M-F7-02, M-F6-04. |
| 7.1.2 | 2026-10-09 | PATCH (verdicts of 2026-10-09 on `docs/_audit/2026-10_F6_design.md`, recorded as D-F6-001 to D-F6-016 in `docs/phases/F6_lcoe_modeling.md`; no result is redefined): M-F6-01 names the variable O&M key and unit (`opex_var_usd_per_mwh`, USD/MWh); M-F6-04 batches along cells with all samples in memory, and the summaries are taken over the draws `s >= 1`, with the nominal vector reported on its own and the count of non-finite values persisted (D2, D3, D7); M-F6-06 names the design matrix per technology (D13); M-F7-06 states that the secondary statistic is accumulated by F7, not read from the F6 summaries. IDs cited and not altered: A-10, U-03, M-F6-02, M-F7-03. |
| 7.1.1 | 2026-10-08 | PATCH (a registered support phase had no mention): Sections 4.1 and 4.2 list `potential_maps` as a support phase of F5 (requires the central potential table, produces the potential-density and capacity-factor rasters and the maps, drawn as `settings.yaml` `figures` allows, A-08). IDs cited and not altered: A-01, A-07, A-08, T-R1. |
| 7.1.0 | 2026-10-08 | MINOR (registers verdicts D1 to D16 of `docs/_audit/2026-10_F5_design.md`, recorded as D-F5-001 to D-F5-016 in `docs/phases/F5_technical_potential.md`; no existing result is redefined): M-F5-03 gains the hub height in `parameters.json` (D-F5-012), the folded form `A_eq` (Section 2.3 of the design report), the exact piecewise-linear integral (D-F5-001, D-F5-002), the curve storage and the IEC class rule fixed across members (D-F5-003, D-F5-004), and `rho0` in `core/constants` (D-F5-009); M-F5-06 names the output per land scenario, the F6 and F7 reading of the central file and the two aggregate series (D-F5-005, D-F5-006); M-F7-01 defines the climate-data-invalid class and the F7 set (D-F5-006); M-F5-01 and M-F5-02 name the parameters as required parameters (D-F5-011); M-F5-05 cites the hours-per-year constant (D-F5-009); A-04 and Section 9 add the required-parameter keys, the IEC class rule, the class-to-curve map and `config/power_curves/`. IDs cited by the rewritten lines and not altered: M-F4-07, U-05, U-06, U-08, V1, V-02, V-03, OQ-005, OQ-004, OQ-023. |
| 7.0.1 | 2026-10-08 | PATCH (verdicts A to G of 2026-10-08): OQ-052 is merged into OQ-008, so the cost threshold of economic potential (T-R12, H5) is the satisficing threshold `tau` (H5, M-F7-07, T-R12, MS-6 in Section 12). Climate-fragile is defined at the nominal parameters `s0` of each member and parametric-only infeasibility gets the finite worst-case regret (M-F7-01, M-F7-02; V9, V3). Section 4.1: F4 requires the `reference_grid` artifact and no aligned layer, F2b and F3 require named layers, and staleness follows artifact content (4.1, 4.2, A-02, A-01). The V-01 fixtures are refrozen with E1 to E3 as the shares F3 computes (V-01, M-F3-01). IDs cited by the rewritten lines and not altered: M-F7-03, M-F7-07, H5, T-R12, OQ-010, OQ-020, OQ-050, OQ-051, OQ-052, V-03, M-F4-07, M-F2b-01, M-F2b-05, A-06, A-09, F4, H1, H4, RQ3, U-08, and the OQ list of the MS-6 row: OQ-001, OQ-002, OQ-003, OQ-004, OQ-005, OQ-015, OQ-016, OQ-019, OQ-021, OQ-022, OQ-023, OQ-044, OQ-045. |
| 7.0.0 | 2026-10-08 | MAJOR (changes a result definition and phase contracts): applies verdicts V1 to V6, V8 to V10, V12 to V15 and V17 to V19 of `docs/_audit/2026-10_systematic_review.md` (V7, V11, V16 and V20 act outside this document). Land stays in every potential output and leaves only the set of futures of F7 (V1): U-01, U-06 (three named scenarios central, restrictive, permissive replacing the strict and lenient variants; full factorial only to report ranges, V2), M-F2b-06, M-F3-02, M-F3-04, M-F5-06, M-E1-01, T-R2, Section 9. Relative regret and primary metric MR as max over members of the P90 over samples (V3): M-F7-02, M-F7-03, M-F7-05, M-F7-11, V-03, RO4, Section 3; M-F7-01 (cells below CF_min leave the set, climate-fragile class, V9); M-F7-06 (Jaccard primary, variance on relative LCOE secondary, V4); M-F7-07 (H4 per V4, new H5 test, rules in OQ-050). Independent sampling without sourced correlation (V5): U-03, L-012; U-05 gains the `proxy` field with a narrow definition (V6), L-203 stays; new U-08 reporting rule (V14); A-02 records the METHODOLOGY version per phase entry (V15). S-05, M-F1-04 and M-F4-05: the 2071-2100 window has no hazard rows until OQ-007 admits a hazard to LCOE (V8). RQ0 'siting priorities' (V10, S-06, OQ-010 in M-F7-05). New H5 (RQ3, V13) and thesis outputs T-R10 (extended), T-O3 (now essential), new T-R11 and T-R12, T-R8 (H1-H5), with the rule for climate outputs at fixed central land (V12), OQ-050, OQ-051, OQ-052 (to be registered in `docs/OPEN_QUESTIONS.md`). M-F2b-05 raises on an absent protected-area, lake or river layer (V17) with A-06 providing them; A-06 and V-08 extended with every built phase. Sections 4.1 and 4.2 match `main.py` (F1b `audit_report` required by F2b, F3, F4; support phases external_inputs, hazard_context, climate_maps, overview) and M-F1b-02 is rewritten (V18); A-01 referenced. M-F2a-06 keeps its text (anything but an exact block count is an error) and is now met by IND with the 10 m tiles (V19, D-F2a-015). Corrections of the systematic review: M-F2b-01 rewritten for shares, 30 m slope samples and named-level `excluded_classes` (M-F2a-06, M-F2a-07, M-F3-01); M-F2a-06 and M-F2a-07 moved to the F2a block; M-F2b-05 ordered before M-F2b-06; S-04 names the six GCMs (D-F4-012); U-03 names `opex_fixed_frac` (V7 name). Section 12 rewritten with the real state: MS-5 (V2, V19), MS-6 (OQ-004, OQ-005, OQ-023, OQ-001, OQ-016, OQ-017, OQ-018, OQ-019, OQ-022, OQ-008, OQ-010, OQ-020, OQ-021, OQ-050, OQ-051, OQ-052; OQ-002, OQ-003, OQ-015, OQ-044, OQ-045 resolved), MS-8, MS-9 (U-02, U-04, A-10). IDs cited by rewritten lines without a change of their own content: A-03, A-05, A-11, D-F2a-016, OQ-013, RO3, RQ1, RQ2, RQ4, RQ5, U-07, V-01, V-02, V-04, M-F3-01, M-F4-02, M-F4-03, M-F7-04, M-F7-08, M-F7-10, M-F2b-04, OQ-004, OQ-007, OQ-016, OQ-045, OQ-049, A-09. |
| 6.0.0 | 2026-10-07 | MAJOR (changes a result definition): E5 of M-F3-01 becomes a share of the pixel from per-class sample counts instead of the class of one sample, and E4 of M-F3-01 becomes the share of 30 m samples above the slope maximum (new M-F2a-07, D-F2a-016); new M-F2a-06 (D-F2a-015); new riparian discharge parameter (`riparian_min_discharge_m3s`, D-F3-005). The land-cover change leaves country totals nearly unchanged and moves cell values; the slope change lowers the eligible land (PRT solar 31.2% to 23.9%). The planned sampled land-availability ranges (OQ-049) will be the next MAJOR. |
| 5.0.0 | 2026-10-07 | MAJOR (changes a result definition): M-F3-01 eligibility becomes an eligible share per pixel; E1-E3 are excluded shares measured on sub-pixels (M-F2b-01, OQ-045 option c); new M-F2a-05 (counts are summed, which corrects the aligned population layer, D-F2a-014); new M-F2b-06 (land-availability parameters as ranges in `land_availability`); parameter values proposed in `docs/_audit/2026-10_f3_parameter_research.md` and approved by Douglas on 2026-10-07 (cropland excluded for solar). |
| 4.1.0 | 2026-10-07 | MINOR (removes an unused input, no result definition changes): the WRI GPPD layer is withdrawn from F1, F1b and F2a (no `power_plants` acquisition, no `plants` aligned raster, no plant statistics in the audit); M-F1-06 states that GEM is the only existing-plant source (D-F1-027). The F2a outputs lose the `aligned/plants` artifact and the V-01 frozen fixture drops `f2a/ZZZ_plants_aligned` (every other frozen layer is identical). |
| 4.0.0 | 2026-10-07 | MAJOR (changes a result definition): new M-F4-07 masks cell-members whose `delta_wind` is outside `wind_factor_valid_range` (OQ-042 option C, Douglas's verdict), so `forcing.parquet` no longer holds a row for them and `forcing_masked.parquet` declares the absence; M-F4-06 lists the masked-cell file, the hazard-context indicators and the per-window hazard-channel declaration (2071-2100 hazard data not acquired). |
| 3.0.0 | 2026-10-06 | MAJOR (changes a result definition): M-F4-03 `delta_wind` becomes the ratio of 3 x 3 native-cell neighbourhood means of the window and reference annual means instead of a per-cell ratio (Douglas's verdict, option A of OQ-042). `delta_rsds` and `dT` unchanged. Residual noted: MIROC6 over Brazil still gives extreme factors in part of the Amazon (OQ-042 stays open for that residual). |
| 2.1.0 | 2026-10-06 | MINOR: M-F4-02 gains item 5, a recorded exception keeping IPSL-CM6A-LR (TCR 2.32 K, above the likely range) with a `tcr_exception` flag, per Douglas's verdict on OQ-009 (option C: GFDL-ESM4, MIROC6, ACCESS-CM2, IPSL-CM6A-LR, CNRM-CM6-1, MRI-ESM2-0). No existing result changes. |
| 2.0.0 | 2026-10-06 | MAJOR (changes a result definition): M-F2a-03 stores the uncapped geodesic distance and `distance_cap_km` becomes only the threshold of a `distance_capped` flag raster; M-F3-03 weights the uncapped distance and reports the flag share as a quality indicator; M-F6-01 gains a note that it bills the real distance and that its linear form is a first-order approximation (L-019). Resolves OQ-040 (Douglas's authorization, 2026-10-06). Header version and date brought in line with the changelog (the header still read 1.2.3). |
| 1.3.0 | 2026-09-28 | M-F1-05 loses its CRAEI/A-11 attribution (CRAEI's own D12 decided against ERA5 gust — nothing to adapt, built fresh, task F4-1/F4-2) and gains its reduction (annual maximum of `fg10`) and reference period (1995-2014, coherent with S-05); no result changes since M-F1-05 was not yet implemented. |
| 1.2.3 | 2026-09-23 | A-03 wording updated: `run.force_rerun` replaced by `run.rerun_phases` (exact re-execute scope; downstream consumers are marked stale and recomputed lazily, not re-executed eagerly — R-1, `docs/phases/core.md` D-core-012). |
| 1.2.2 | 2026-09-22 | Section 9 adds `config/audit.yaml` (data_quality_audit diagnostic-gate configuration, M-F1b-01). |
| 1.2.0 | 2026-09-22 | GEAR removed as an active reference repository (A-11, S-08, S-09, M-F1-04, M-F1-05, M-F4-05 now cite CRAEI only); M-F1-01's local-database variable renamed to its current name, `GEOFREA_SHARED_RAW_DIR`; A-12 adds that the run environment is declared in `.env.example` and loaded at startup. |
| 1.1.0 | 2026-09-21 | A-11 adds CRAEI as primary reference repository; A-08 adopts external data layout; M-F1-04, M-F1-05, M-F4-05 reference A-11. |
| 1.0.0 | 2026-09-15 | Initial adoption. |
