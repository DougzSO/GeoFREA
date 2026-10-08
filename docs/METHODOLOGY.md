# GeoFREA Methodology Specification

| Field | Value |
|---|---|
| Document | `docs/METHODOLOGY.md` |
| Version | 7.0.0 |
| Adopted | 2026-09-15 |
| Updated | 2026-10-08 |
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

- **H1.** The robustness ranking is stable across the three SSPs for a substantial share of top-ranked sites, while a non-trivial share of sites that are optimal under current conditions lose robustness under at least one climate scenario.
- **H2.** Within-country spatial heterogeneity in eligibility and viability is large enough that country-aggregated assessments misrepresent site-level robustness.
- **H3.** Sites that are robust under combined uncertainty differ materially, in location and ranking, from sites that are optimal under current conditions.
- **H4.** The relative robustness ranking is sensitive to which uncertainty axis (climate or techno-economic) dominates in each country; there is no country-independent robustness ordering.
- **H5 (RQ3).** Climate change alters national economic potential (TWh below the cost threshold, OQ-052) and the share of potential exposed to hazards (OQ-051) by a margin that matters relative to the gap between potential and national target (OQ-010). Stated as a test; the decision rule (statistic and threshold) is fixed before the results in OQ-050, as for H1 to H4.

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
F1 ──> F2a grid_alignment
F2a + F1b ──> F2b siting_layers
F1 + F2a + F2b + F1b ──> F3 land_eligibility
external_inputs (CMIP6, ISIMIP3b, ERA5 registered) ──> F4 climate_forcing
F2a + F1b + external_inputs ──> F4 climate_forcing ──> hazard_context, climate_maps
F2a + F2b + F3 + F4 + hazard_context ──> overview
F3 + F4 ──> F5 technical_potential ──> F6 lcoe_modeling ──> F7 robustness_analysis
F3 + F6 (nominal) + F1 (existing plants) ──> F7b external_validation
F5 + F6 + F7 + F7b ──> F8 results_synthesis ──> E1 explorer
```

The phases external_inputs, hazard_context, climate_maps and overview are support phases with no F-identifier; they are named by phase name and registered in `main.py` with the same `requires` and `produces` contract as the F-phases (A-01). The legacy phase `suitability_criteria` is outside this specification.

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
| overview | `overview` | Country overview maps and table over F2a to F4 outputs | Overview figures | Section 11 |
| F5 | `technical_potential` | Capacity, CF, and energy per cell and member | Potential table | RO1, RO3, RQ1, RQ3 |
| F6 | `lcoe_modeling` | LCOE kernel, parameter sampling, per-member LCOE summaries | LCOE summaries, design matrix | RO2, RQ2 |
| F7 | `robustness_analysis` | Regret, satisficing, decomposition, scenario discovery, hypothesis tests | Robustness tables | RO4, RQ0, RQ4, H1-H5 |
| F7b | `external_validation` | Plausibility checks against existing plants and published estimates | Validation tables | RO5 |
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
- **M-F3-04.** A cell enters the candidate set if `eligible_area_km2 >= min_eligible_area_km2[tech]`. The candidate set of the central scenario is the set F7 uses (V1). The same rule applied to the other scenarios gives, per cell, the share of the named scenarios in which it is a candidate (candidate-set stability), reported beside the F7 results and not used by F7.
- **M-F3-05.** Outputs: `candidates_<tech>.parquet` (one row per candidate cell, stable `cell_id`), pixel and cell eligibility COGs, dominant-exclusion COG.
- **M-F3-06.** A 0.1 degree aggregation of the same pixels is produced for the scale check (V-07).

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
- **M-F4-04.** Change factors are bilinearly interpolated to 0.05 degree cell centers.
- **M-F4-05.** Hazard channels (D15 rule):
  - C1 (mean resource) always enters F5 through M-F4-03.
  - C2 (operational extremes: extreme heat, extreme wind) and C3 (damage and cost: extreme precipitation) enter F5 or F6 quantitatively only with a loss function of evidence Tier 1 or 2 (resolved in OQ-007). Otherwise they are computed as per-cell context indicators per member and reported in T-R10, never entering regret or satisficing.
  - Hazard indicator processors adapted from CRAEI per A-11.
- **M-F4-06.** Outputs: `forcing.parquet` (`cell_id`, `member`, `delta_rsds`, `dT`, `delta_wind`), `forcing_masked.parquet` (the cell-members removed by M-F4-07, with the rejected `delta_wind`), `hazard_context.parquet` (context indicators per cell and member that carries the hazard channel: `tx35_days`, `tx40_days`, `rx5day_mm`, `wet_p95_exceed_freq`, their reference values, and the scenario-invariant ERA5 `gust_mean_annual_max_ms`), `members.yaml` (resolved member list with provenance, channels per member and window, masked counts).
- **M-F4-07.** Validity mask for the wind factor: a cell-member whose `delta_wind` lies outside `wind_factor_valid_range` (`config/experiments.yaml`, 0.5-1.5, plausibility bound with no source) is masked: it has no row in `forcing.parquet`, the member is absent in that cell, and the cell-member is listed in `forcing_masked.parquet`. Nothing is replaced by another value. Any consumer of the forcing (F5) must verify that every candidate cell and member is either in `forcing.parquet` or declared in `forcing_masked.parquet`, and that no factor is out of range (`climate_forcing/forcing.py::assert_forcing_usable`); otherwise it fails (OQ-042 option C, Douglas 2026-10-06).

### F5 technical_potential

- **M-F5-01.** Capacity per cell: `P_MW = eligible_area_km2 * LUF[tech] * PD[tech]`, where `PD` is power density on project footprint (MW/km²) and `LUF` is the land-utilization factor (share of eligible land plausibly developed).
- **M-F5-02.** Solar capacity factor:
  - Reference: `CF0 = pvout_kwh_kwp_day / 24`.
  - Member: `CF_m = CF0 * delta_rsds_m * (1 + gamma * dT_m)`, with `gamma` the module power temperature coefficient (1/K, negative). PVOUT already includes reference-climate thermal losses; the member correction is relative.
- **M-F5-03.** Wind capacity factor:
  - Hub height `H[tech, country]`. Weibull A at `H` by power-law interpolation between the two bracketing heights, `alpha = ln(A2/A1) / ln(z2/z1)`, `A_H = A1 * (H/z1)^alpha`; `k_H` linear in height; air density linear in height.
  - Equivalent wind speed with air-density correction `v_eq = v * (rho/rho0)^(1/3)` (IEC 61400-12-1 convention).
  - Reference turbine power curve per IEC class, class chosen per cell by the rule in `technologies.yaml` (OQ-005).
  - `CF0 = eta_loss * integral( P_curve(v_eq) / P_rated * weibull_pdf(v; A_H, k_H) dv )`, with `eta_loss` covering wake and availability losses.
  - Member: `CF_m = CF0 * CF(A_H * delta_wind_m, k_H) / CF(A_H, k_H)`, evaluated at cell values; `k_H` unchanged.
- **M-F5-04.** If a C2 loss function passes OQ-007: `CF_m <- CF_m * (1 - L_C2_m)`.
- **M-F5-05.** Annual energy: `E_m = P_MW * CF_m * 8760` (MWh/yr).
- **M-F5-06.** Outputs: `potential_<tech>.parquet` (`cell_id`, `member`, `P_MW`, `CF`, `E_MWh`), country aggregates per member and land-availability scenario. F5 is evaluated at the central land set; climate effects on potential are computed at that fixed land, and the land range is reported beside them, so the two are not confounded (U-08).

### F6 lcoe_modeling

- **M-F6-01.** LCOE kernel, vectorized over cells, for member `m` and parameter vector `theta`:
  - `CAPEX_total = P_MW*1000*capex_usd_per_kw + P_MW*dist_grid_km*grid_cost_usd_per_mw_km + P_MW*substation_cost_usd_per_mw + dist_road_km*road_cost_usd_per_km`
  - `OPEX_t = opex_fixed_frac * P_MW*1000*capex_usd_per_kw + opex_var_usd_per_mwh * E_t`
  - `E_t = E_m * (1 - d)^(t-1)`, `t = 1..n`
  - `LCOE = [CAPEX_total + sum_t OPEX_t/(1+r)^t] / [sum_t E_t/(1+r)^t]` (USD2024/MWh, real terms)
  - Climate of the member window is held constant over the asset lifetime.
  - `dist_grid_km` and `dist_road_km` are the real (uncapped) distances from F3. The linear distance terms are a first-order approximation of connection cost, declared in `LIMITATIONS.md` (L-019); the direction for a richer connection-cost model (voltage, technology, capacity, route, losses) is tracked in OQ-041.
- **M-F6-02.** Parameter samples `s` drawn by Latin hypercube over the uncertain parameters declared in `experiments.yaml` (U-03), with recorded seed. Sample `s0` is the nominal vector.
- **M-F6-03.** If a C3 loss function passes OQ-007, it enters as an OPEX adder per member.
- **M-F6-04.** Streaming: per member, samples are processed in batches. Persisted per (`cell_id`, `member`): nominal LCOE, mean, variance, p10, p50, p90 over samples. The design matrix is persisted. The full sample-level array is not.
- **M-F6-05.** The kernel is a pure function importable by F7.
- **M-F6-06.** Outputs: `lcoe_summary_<tech>.parquet`, `design_matrix.parquet`, supply curves per member at nominal parameters.

### F7 robustness_analysis

Definitions for one country and technology. `C` = candidate cells of the central land scenario (V1); land is not a factor of the futures. Futures `f = (m, s)` over climate members of the core window and samples; `f0 = (m0, s0)` is the nominal present future.

- **M-F7-01. Feasibility.** `feasible(i, f) = CF_i,m >= CF_min[tech]` (OQ-008). A cell with `CF` below `CF_min` in the nominal future `f0` leaves the F7 set. A cell feasible in `f0` and infeasible in some member forms the class *climate-fragile*: it is reported separately, with the members in which it fails, and is not ranked with an infinite MR.
- **M-F7-02. Relative regret.** `L*_f` = the `q_ref` quantile of LCOE over feasible cells in `f` (default `q_ref = 0`, the minimum; OQ-020). `r_i,f = (LCOE_i,f - L*_f) / L*_f` for feasible cells.
- **M-F7-03. Primary metric.** `MR_i = max over members m of ( P90 over parameter samples s of r_i,(m,s) )`. Order of operations: `r` per future `(m, s)`; P90 over samples for each member; maximum over members. Secondary: SR (M-F7-04).
- **M-F7-04. Satisficing robustness.** `SR_i` = share of futures with `feasible(i, f)` and `LCOE_i,f <= tau[country, tech]` (OQ-008).
- **M-F7-05. Rankings.** Nominal rank by `LCOE_i,f0`; robust rank by `MR_i` (ties broken by `SR_i`), over the cells that are not climate-fragile. Top-k is the best `p_k` percent of candidate cells by count (OQ-021). Sensitivity, the strategy-level reading: top-k as the minimum cell set reaching a national capacity target (OQ-010).
- **M-F7-06. Axis comparison (H4).** Primary: Jaccard(top-k nominal, top-k under climate-only futures `(m, s0)`) versus Jaccard(top-k nominal, top-k under techno-only futures `(m0, s)`). Secondary: per cell, law of total variance over futures, `Var(X) = E_m[Var_s(X)] + Var_m[E_s(X)]` (techno-economic part, climate part), computed from F6 summaries on the relative LCOE `X = LCOE / L*_f`.
- **M-F7-07. Hypothesis tests.**
  - H1: Spearman correlation of cell LCOE rankings between SSP pairs (per GCM and ensemble median); Jaccard of top-k between SSPs; share of nominal top-k cells leaving top-k under at least one member. Repeated for the 2071-2100 window as sensitivity. Decision rules (statistic and threshold) for H1 to H5 are pre-registered in OQ-050.
  - H2: within-country dispersion of `MR` (IQR relative to median; range across admin1 units) against the capacity-weighted national aggregate; repeated at 0.1 degree (V-07).
  - H3: Jaccard(top-k nominal, top-k robust); share of robust top-k capacity outside nominal top-k; capacity-weighted distance between the two sets' centroids.
  - H4: country ordering of the climate-only versus techno-only Jaccard comparison of M-F7-06 (primary), with the variance shares as secondary.
  - H5: per member, national potential (GW, TWh) below the cost threshold (OQ-052) and the share of potential in cells above the hazard exposure thresholds (OQ-051), each compared with the national target (OQ-010) at fixed central land; the land range is reported beside them (U-08). The decision rule is OQ-050.
- **M-F7-08. Scenario discovery.** PRIM over future descriptors (parameter values, member change factors, SSP, GCM) with outcome "nominal top-k cell leaves top-k", per country and technology.
- **M-F7-09. Method agreement.** Kendall correlation between `MR` and `SR` rankings, supporting the RQ4 discussion.
- **M-F7-10. Streaming.** One future at a time, vectorized over cells, updating running maxima and counters; a full evaluation of all futures is never held in memory.
- **M-F7-11.** Outputs: `robustness_<tech>.parquet` (per cell: nominal LCOE and rank, MR, SR, climate-fragile flag and failing members, variance shares, top-k flags), hypothesis test tables, PRIM boxes.

### F7b external_validation

- **M-F7b-01.** Share of existing plant capacity (GEM trackers) located in excluded pixels, per exclusion constraint. Tests the exclusion set.
- **M-F7b-02.** Enrichment ratio: share of existing capacity in the lowest nominal-LCOE deciles divided by the share of eligible area in those deciles.
- **M-F7b-03.** Comparison of national technical potential with published estimates, as a table with source and definition notes.
- **M-F7b-04.** Existing plants reflect past auctions, policy, and grid access. Results are plausibility evidence, not accuracy.

### F8 results_synthesis

- **M-F8-01.** F8 reads persisted artifacts and never recomputes a scientific quantity.
- **M-F8-02.** F8 produces every output of Section 10 into `outputs/thesis/`, with a fixed style and one script per output.

### E1 explorer

- **M-E1-01.** Static, precomputed explorer by country, technology, window, SSP, GCM, and land-availability scenario, with per-cell query. Eligibility thresholds are adjustable only across the precomputed scenarios. Technology stack in OQ-013.

---

## 6. Uncertainty and futures design

- **U-01. Futures.** Full factorial of climate members (F4) and techno-economic samples (F6). Both axis identifiers are preserved in every F6 and F7 artifact. No probability is assigned across SSPs or GCMs. Land availability is not a factor of the futures (V1): its ranges are reported through U-06 and U-08.
- **U-02. Monte Carlo scope.** Sampling happens only within the parameter axis. Climate uncertainty is represented only by the discrete member set.
- **U-03. Uncertain parameters.** Declared in `config/experiments.yaml`. Default set: `capex_usd_per_kw`, `opex_fixed_frac`, `discount_rate`, `lifetime_years`, `degradation_rate`, `grid_cost_usd_per_mw_km`, `substation_cost_usd_per_mw`, `road_cost_usd_per_km`, `gamma` (solar), `eta_loss` (wind). `LUF` and `PD` affect capacity and are handled in a sensitivity outside the regret ensemble (OQ-004). `opex_fixed_frac` is the fixed O&M as a fraction of CAPEX per year. Parameters are sampled independently (L-012); no correlation is imposed without a sourced coefficient.
- **U-04. Sample size.** Protocol: start at 500 samples, double until the Jaccard of top-k by `MR` between consecutive sizes changes by less than 0.01 for all countries and technologies; the adopted size is recorded in the F6 phase record.
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
- **A-02. Artifact registry.** The per-country manifest records, for each artifact: path, content hash, schema version, producing phase, run ID; and, for each phase entry, the METHODOLOGY version. A phase whose upstream is not part of the current run loads upstream artifacts from the manifest. In-memory coupling between phases is not allowed.
- **A-03. Run targeting.** `settings.yaml` declares `run.target_phases`, `run.countries`, `run.technologies`, and `run.rerun_phases`; dependencies are resolved from the DAG. `rerun_phases` re-executes exactly the phases it names; every phase downstream of a named phase that currently holds a successful manifest entry is marked stale and recomputed automatically the next time a run needs it, rather than being re-executed in the same pass (see `docs/phases/core.md` D-core-012). Per-phase boolean toggles are not used.
- **A-04. Technology registry.** `config/technologies.yaml` declares per technology: resource layers, capacity-factor model, exclusion set, cost structure, uncertain-parameter keys. F5-F7 code contains no technology names.
- **A-05. Country agnosticism.** All country-specific mappings (data-source regions, file names, GRIP4 regions, HydroSHEDS regions) live in `config/countries.yaml`. A test fails if an ISO3 code literal appears in `src/` outside comments and docstrings.
- **A-06. Synthetic country.** A small synthetic country fixture runs every built phase in CI and is extended in the same change that builds a phase; a phase does not close its milestone (Section 12) until it runs on the fixture. The fixture provides the protected-area, lake and river layers (M-F2b-05).
- **A-07. Formats.** Rasters are Cloud Optimized GeoTIFF, EPSG:4326. Tables are parquet with a Pydantic schema and a `schema_version`. Run ID = hash of configuration, methodology version, and code commit.
- **A-08. Outputs layout.** All data stored in GEOFREA_DATA_DIR (environment variable, never under repository root). Structure:
  - `raw/<source>/<ISO3|_global>/`: fetched raw data (GADM, HydroSHEDS, GEM trackers, WDPA, GWA)
  - `interim/<ISO3>/<layer>/`: intermediate processing caches
  - `outputs/<ISO3>/manifest.json`: run manifest per country
  - `outputs/<ISO3>/<phase>/<kind>/`: phase outputs (artifacts, figures, reports)
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
- **V-07. Scale check.** F5-F7 rerun at 0.1 degree; H1 to H3 statistics reported side by side (MAUP).
- **V-08. Synthetic end-to-end.** A-06 in CI, through the last built phase; the test is extended with each phase built.

---

## 9. Configuration files

| File | Content |
|---|---|
| `config/parameters.json` | Scientific parameters per country and technology, schema U-05 |
| `config/technologies.yaml` | Technology registry, A-04 |
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
| T-R3 | Figure | F4, F5 | CF change by SSP, core window, with GCM agreement marking | RQ3 | Essential |
| T-R4 | Figure | F7 | Max-regret map per country, with intra-country distribution panel against the national aggregate | RQ4, H2 | Essential |
| T-R5 | Figure | F7 | Nominal versus robust rank, top-k stability across SSPs | H1, H3 | Essential |
| T-R6 | Table | F7 | H1 and H3 statistics; rows for 2071-2100 and 0.1 degree | H1, H3, H2 | Essential |
| T-R7 | Figure | F7 | Climate versus techno-economic shares by country | H4 | Essential |
| T-R8 | Table | F8 | Cross-country synthesis with verdict on H1-H5 | RQ5 | Essential |
| T-R9 | Table | F7b | External validation | RO5 | Essential |
| T-R10 | Table | F4, F5, F7 | Hazard context exposure of nominal and robust top-k cells and of all eligible potential (GW and TWh in cells above the hazard exposure thresholds, OQ-051), by SSP and window; the wording is "exposed", and "lost" only for a hazard whose loss function passed OQ-007 | RQ3, H4, H5 | Essential |
| T-R11 | Figure | F6 | LCOE map at reference | RQ2 | Essential |
| T-R12 | Table | F5, F6 | Potential (GW, TWh) below the cost threshold (OQ-052) per member, compared with the national targets (OQ-010) | RQ3, H5 | Essential |
| T-O1 | Figure | F7 | PRIM scenario discovery boxes | RQ4 | Optional |
| T-O2 | Figure | F7 | Agreement between MR and SR rankings | RQ4 | Optional |
| T-O3 | Figure | F6 | Supply curves at nominal parameters, by SSP and window | RQ2 | Essential |

Reporting rule for the climate outputs: climate effects on potential are computed at the fixed central land set, and the land range is reported beside them (U-08).

---

## 11. Diagnostic figures

Per-phase maps are diagnostics for inspection and for the future platform, generated under A-08. Minimum set per country and technology: F2b exclusion layers and cost-driver layers; F3 eligible fraction and dominant exclusion; F4 change factors per member; F5 CF and capacity per member; F6 nominal and median LCOE; F7 MR, SR, top-k flags.

---

## 12. Implementation roadmap

Sequenced by dependency; each milestone closes before the next opens, except where marked parallel. State as of 2026-10-08.

| Milestone | Content | State | Gate |
|---|---|---|---|
| MS-0 | Planning adopted; records migrated; repository restructured | done | This document committed |
| MS-1 | Core: A-01 to A-03, A-05, configuration schemas (U-05, Section 9) | done | Tests for DAG validation and ISO3 literal check pass |
| MS-2 | F1 and F1b conformance, including India wiring and new wind and CMIP6 products | done | F1-F2a run for BRA, PRT, IND |
| MS-3 | F2a conformance | done | V-01 fixtures refrozen and passing |
| MS-4 | F2b rebuild as `siting_layers` | in progress | Exclusion parity E1-E3; sanity ranges pass for three countries |
| MS-5 | F3 | built, pending conformance | Closes with the three named scenarios of U-06 (V2), the 10 m land cover for IND (M-F2a-06, V19) and a clean rerun in BRA, PRT and IND; candidate tables for three countries and two technologies |
| MS-6 | Parameter research, in parallel with MS-4 and MS-5, by priority: F5 first (OQ-004, OQ-005, OQ-023), then F6 (OQ-001, OQ-016 to OQ-019, OQ-022), then F7 (OQ-008, OQ-010, OQ-020, OQ-021, OQ-050); also OQ-051 and OQ-052 | in progress (OQ-002, OQ-003, OQ-015, OQ-044, OQ-045 resolved) | Every uncertain parameter has range and tier |
| MS-7 | F4, including GCM selection | in progress | Forcing tables for the selected ensemble |
| MS-8 | F5: code and tests on the synthetic country before real values; real execution only with parameter values recorded under MS-6 | not started | V-02, V-03 pass |
| MS-9 | F6, including sampling (U-02), convergence (U-04) and batches (A-10) | not started | U-04 convergence recorded |
| MS-10 | F7 and F7b | not started | H1-H5 tables for three countries |
| MS-11 | F8 and E1 | not started | All essential outputs generated |

A-06 and V-08 are extended with every phase built: no milestone from MS-5 on closes without its phase running on the synthetic country.

---

## 13. References to verify

Full bibliographic details must be confirmed during the literature review before citation in the thesis.

- Bryant, B. P., and Lempert, R. J. (2010). Scenario discovery (Technological Forecasting and Social Change).
- Deshmukh, R., et al. (2019). Geospatial and techno-economic analysis of wind and solar resources in India (Renewable Energy).
- Hausfather, Z., et al. (2022). Climate simulations: recognize the hot model problem (Nature).
- Herman, J. D., et al. (2015). How should robustness be defined for water systems planning under change? (Journal of Water Resources Planning and Management).
- IEC 61400-1 and IEC 61400-12-1.
- IPCC AR6 WGI (2021), reference period 1995-2014.
- Jordan, D. C., and Kurtz, S. R. (2013). Photovoltaic degradation rates (Progress in Photovoltaics).
- Lempert, R. J., Popper, S. W., and Bankes, S. C. (2003). Shaping the Next One Hundred Years (RAND).
- Lopez, A., et al. (2012). U.S. Renewable Energy Technical Potentials (NREL).
- Maclaurin, G., et al. (2019). The Renewable Energy Potential (reV) Model (NREL).
- McKay, M. D., et al. (1979). Latin hypercube sampling (Technometrics).
- McKenna, R., et al. (2022). High-resolution large-scale onshore wind energy assessments: a review (Renewable Energy).
- McPhail, C., et al. (2018). Robustness metrics (Earth's Future).
- Ryberg, D. S., et al. (2018). Evaluating land eligibility constraints of renewable energy sources in Europe (Energies).
- Savage, L. J. (1951). The theory of statistical decision (Journal of the American Statistical Association).
- Solargis / World Bank ESMAP. Global Solar Atlas PVOUT metadata (2025).
- Staffell, I., and Green, R. (2014). How does wind farm performance decline with age? (Renewable Energy).
- Wu, G. C., et al. (2017). Strategic siting and regional grid interconnections (PNAS).

---

## 14. Changelog

| Version | Date | Change |
|---|---|---|
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
