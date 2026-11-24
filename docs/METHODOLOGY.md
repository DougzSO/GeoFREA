# GeoFREA Methodology Specification

| Field | Value |
|---|---|
| Document | `docs/METHODOLOGY.md` |
| Version | 2.0.0 |
| Adopted | 2026-11-24 |
| Updated | 2026-11-24 |
| Owner | Douglas |
| Status | Adopted as the specification of GeoFREA v2. Items marked *awaiting author verdict* are not implemented until Douglas decides them. |

## 0. Document control

This document is the single source of truth for the scientific method and architecture of GeoFREA v2. It describes the method as it is.

Change protocol:

1. This file is edited only with explicit authorization from Douglas.
2. Every change bumps the version (MAJOR: changes a result definition or a phase contract; MINOR: adds an item without changing existing results; PATCH: wording or reference fixes) and records the reason in `docs/DECISIONS.md`.
3. Implementation that needs to deviate from an item opens an entry in `docs/OPEN_QUESTIONS.md` and stops until Douglas gives a verdict. Deviations are never implemented first and documented later.
4. Item IDs are stable and never reused. The M-, U-, A-, V-, S- and D- items keep the identifier they had in v1 when their content still holds, so that `docs/v1/inheritance.md` maps one to the other.

ID scheme:

| Prefix | Meaning | Example |
|---|---|---|
| `S-nn` | Scope item | `S-03` |
| `M-<phase>-nn` | Method item of a phase | `M-F5-05` |
| `M-<module>-nn` | Method item of a v2 module (`M1`, `M2`, `M3`) | `M-M1-01` |
| `U-nn` | Uncertainty and futures design item | `U-02` |
| `A-nn` | Architecture requirement | `A-01` |
| `V-nn` | Validation and testing item | `V-03` |
| `T-<id>` | Thesis output | `T-R4` |
| `H<n>` | Hypothesis of v2 | `H3` |
| `OQ-nnn` | Open question (lives in `OPEN_QUESTIONS.md`) | `OQ-007` |
| `L-nnn` | Declared limitation (lives in `LIMITATIONS.md`) | `L-004` |
| `DEC-nnn` | Decision of v2 (lives in `DECISIONS.md`) | `DEC-001` |

Phase IDs: `F1`, `F1b`, `F2a`, `F2b`, `F3`, `F4`, `F5`, `F6`, `F7`, `F7b`, `F8`; module IDs: `M1`, `M2`, `M3`. Never write an unqualified `F2` or `F7`.

The results of v1 (tags `v1.0`, `v1.1`, `v1-final`) are a development stage and the diagnosis that motivated v2: `docs/v1/record.md`.

---

## 1. Scientific anchor

All architecture and output decisions are subordinate to this section.

### 1.1 Research questions

- **RQ0 (central).** Climate change does not only remove generation, it redistributes it in space. How much does it redistribute the generation of the existing and planned fleet of a country, what supply gap does that create, and where should solar and wind be added, at the lowest cost and risk, to compensate for it?
- **RQ1.** How can technical potential be quantified spatially in a way that is comparable across countries?
- **RQ2.** How can territorial constraints and territory-dependent costs be integrated with techno-economic parameters into one site-level cost metric?
- **RQ3.** How do multi-SSP climate projections change the generation of the fleet (M1), the national supply (M2) and the potential and cost of new sites (F5, F6)?
- **RQ4.** What decision-robustness rule is adequate to treat deep climate uncertainty without collapsing it into an arbitrary score?
- **RQ5.** Does the framework generalize across Brazil, Portugal and India, or is the result context-specific?

### 1.2 Research objectives

- **RO1.** Quantify spatially the technical solar and wind potential (F3, F5).
- **RO2.** Integrate land-eligibility constraints and spatially explicit cost drivers into site-level LCOE (F2b, F3, F6).
- **RO3.** Quantify how SSP1-2.6, SSP3-7.0 and SSP5-8.5 projections of five ISIMIP3b models change solar and wind resource, runoff and the generation of each plant of the fleet (F4, M1).
- **RO4.** Quantify the national supply gap per climate future and its regional distribution (M2), and plan the expansion that covers it (M3), with robustness defined in U-09.
- **RO5.** Validate against existing plants and published estimates (F7b) and deliver a synthesis (F8) and a publication layer.

### 1.3 Hypotheses

The decision rules, thresholds and statistics of H1 to H5 are pre-registered in `prereg-v2` before any real run of F7, M1, M2 or M3 (A-14). The statements below are the v2 hypotheses; they replace the hypotheses of v1.

- **H1, heterogeneous effect.** The change in the generation of the fleet has a different sign in different regions, and the net national effect is smaller than the sum of regional losses and gains.
- **H2, loss hotspots.** The losses with a robust sign are concentrated in few regions and plants.
- **H3, adaptive compensation.** The favoured or low-risk regions hold enough cheap solar and wind potential to compensate for the losses, at a cost slightly above choosing by cost alone.
- **H4, cost of adaptation.** The cost of compensating the loss (and the demand, where there is a projection) rises in the climate futures relative to the reference.
- **H5, context.** The dominant channel and the balance between losses and gains change between countries.

### 1.4 Declared contributions

1. A spatially explicit pipeline in which the climate redistribution of generation of the fleet is a first-order input to expansion planning.
2. A robustness rule based on agreement across climate members, with cost uncertainty reported as ranges (U-09).
3. Empirical validation in three climatically and structurally distinct national contexts.
4. A configuration-driven architecture designed for extension to any country with data (A-04, A-05).

---

## 2. Scope

| ID | Item | Decision |
|---|---|---|
| S-01 | Countries | Brazil (BRA), Portugal (PRT), India (IND) as test cases; the code serves any country with data. |
| S-02 | Technologies | Fleet: hydro, solar, wind. Expansion: utility-scale ground-mounted solar PV and onshore wind. Thermal plants are v2.1 (they need cooling data that GEM does not hold). |
| S-03 | Climate scenarios | SSP1-2.6, SSP3-7.0, SSP5-8.5. |
| S-04 | Climate models | Five ISIMIP3b models, bias adjusted: GFDL-ESM4, IPSL-CM6A-LR, MPI-ESM1-2-HR, MRI-ESM2-0, UKESM1-0-LL, one set for every channel (M-F4-02). |
| S-05 | Time windows | Main window 2041-2070; reference 1995-2014. The 2071-2100 window is not part of v2.0 (OQ-118). |
| S-06 | Decision unit | 0.05 degree cell, exactly 5 x 5 pixels of the 0.01 degree analysis grid (M-F3-03); 0.1 degree is a documented sensitivity (V-07). |
| S-07 | Currency | Constant 2024 USD. |
| S-08 | Excluded from scope | GHG abatement; biomass; thermal plants (v2.1); seismic hazard layer; transport decarbonisation; sea-level rise; wildfire. |
| S-09 | Repository boundary | GeoFREA and CRAEI remain separate repositories. GeoFREA copies and adapts any needed CRAEI code (A-11); CRAEI is never modified from GeoFREA work. |

---

## 3. Conceptual framework

GeoFREA follows the hierarchy of renewable potentials used in large-scale assessments and adds the fleet and the gap:

| Level | Question | GeoFREA output | Unit |
|---|---|---|---|
| Geographic potential | Where is construction allowed? | Eligible area per cell | km2 |
| Technical potential | How much capacity fits and how much energy does it produce? | Capacity, capacity factor, annual energy per cell | MW, -, MWh/yr |
| Economic potential | What does it cost? | Site-level LCOE including grid connection and access | USD2024/MWh |
| Fleet risk (M1) | How much does each existing or planned plant gain or lose per climate future? | Relative change of generation per plant and member | %, MWh/yr |
| Supply gap (M2) | How much does the country gain or lose, and where? | Net and regional change of generation per member | MWh/yr |
| Adaptive expansion (M3) | Where to build to cover the gap at lowest cost and risk? | Portfolio of cells per member and robustness class | MW, USD |

Territory enters through two channels only: hard exclusions (legal and physical constraints) and monetized cost drivers (distance to grid, distance to roads). Weighted overlay of normalized criteria (GIS-MCDA) is not part of the method.

---

## 4. Pipeline

### 4.1 DAG

```
F1  data_acquisition ──> F1b data_quality_audit            (audit_report; findings never block, M-F1b-02)
F1 ──> F2a grid_alignment                                  (aligned layers, and reference_grid)
F2a (named layers) + F1b ──> F2b siting_layers
F2a (named layers) + F2b + F1b ──> F3 land_eligibility
external_inputs (ISIMIP3b, ERA5 registered) ──> F4 climate_forcing
F2a (reference_grid) + F1b + external_inputs ──> F4 climate_forcing ──> climate_maps
F3 + F4 ──> F5 technical_potential ──> F6 lcoe_modeling
F1 (fleet) + F4 ──> M1 fleet_risk ──> M2 supply_gap ──> M3 adaptive_expansion   (F5, F6 enter M3)
F3 + F6 (nominal) + F1 (existing plants) ──> F7b external_validation
F4 + F5 + F6 + M1 + M2 + M3 ──> F7 climate_evaluation ──> F8 results_synthesis
```

Phases of the v1 chain that v2 keeps (F1 to F3, F5, F6, F7b, F8, the support phases) are implemented; F4, F7 and the modules M1 to M3 are specified here and built in later commands. Each phase requires the named artifacts it reads, not the producing phase as a whole: F4 requires the `reference_grid` artifact (CRS, transform, shape and a hash of the in-country mask) and no aligned layer; F2b and F3 require the aligned layers they read. A rerun of a phase invalidates a consumer only when the content hash of an artifact the consumer requires changed (A-02).

Critical transitions:

1. **End of F3: raster to table.** From F4 onward every phase works on candidate-cell tables (parquet) or plant tables, never on full rasters.
2. **F4 creates the climate-member axis** `m`. F5 is evaluated once per member.
3. **F7 evaluates the 15 members of a window with nominal parameters**, jointly across cells and plants, one member at a time.

### 4.2 Phase table

| Phase | Name | Module (`src/geofrea/<module>/`) | Purpose | Main outputs |
|---|---|---|---|---|
| F1 | Data acquisition | `data_acquisition` | Resolve raw layers with provenance | Layer registry |
| F1b | Data audit | `data_quality_audit` | Audit raw layers, report anomalies | Audit report |
| F2a | Grid alignment | `grid_alignment` | Align all layers to the 0.01 degree grid | Aligned rasters |
| F2b | Siting layers | `siting_layers` | Exclusion, cost-driver and resource layers per technology | Pixel layers |
| F3 | Land eligibility | `land_eligibility` | Combine exclusions, aggregate to cells, export candidate table | Candidate table, eligibility rasters |
| external_inputs | Climate inputs registry | `climate_forcing` | Verify and register the ISIMIP3b and ERA5 files F4 consumes | External-inputs report |
| F4 | Climate signal | `climate_forcing` | Climate change factors and relative runoff change per member | Forcing table, member list |
| climate_maps | Climate maps | `climate_forcing` | Diagnostic maps of the change factors | Climate maps |
| F5 | Technical potential | `technical_potential` | Capacity, CF and energy per cell and member | Potential table |
| potential_maps | Potential maps | `technical_potential` | Maps of potential density and capacity factor | Potential rasters, maps |
| F6 | Levelized cost | `lcoe_modeling` | LCOE kernel, nominal LCOE per cell and member, cost ranges | LCOE tables |
| lcoe_maps | Cost maps | `lcoe_modeling` | Maps of the LCOE at the reference member | LCOE rasters, maps |
| F7b | External validation | `external_validation` | Plausibility checks against existing plants and published estimates | Validation tables |
| overview | Country overview | `overview` | Overview maps and table over F2a to F4 outputs | Overview figures |
| F8 | Results synthesis | `results_synthesis` | Aggregate only; produce thesis outputs | Thesis figures and tables |

The modules M1, M2 and M3 and the rebuilt F7 are specified in Section 5 and enter the registry of phases when they are built. The modules M1, M2 and M3 and the rebuilt F7 are specified in Section 5 and enter the registry of phases when they are built. The modules M1, M2 and M3 and the rebuilt F7 are specified in Section 5 and enter the registry of phases when they are built. The modules M1, M2 and M3 and the rebuilt F7 are specified in Section 5 and enter the registry of phases when they are built. The modules M1, M2 and M3 and the rebuilt F7 are specified in Section 5 and enter the registry of phases when they are built. The phase table that `docs/PIPELINE_GUIDE.md` prints is generated from `config/phases.yaml` by `scripts/render_phase_tables.py`; the code still holds the v1 phases F4 to F8 until they are rebuilt.

---

## 5. Phase specifications

### F1 data_acquisition

- **M-F1-01.** Layer registry with provenance per layer: `provenance` in {`fetched`, `local_only`} and computed `fetch_status`. Layers without automated fetch resolve from `GEOFREA_DATA_DIR/raw/<source>/<ISO3|_global>/` (A-08), resolved through `paths.py`; `raw/_shared_origin/manifest.json` records the origin, size and SHA-256 of each copied file. The pipeline reads nothing outside `GEOFREA_DATA_DIR`.
- **M-F1-02.** Active layers: country borders and admin1 (GADM 4.1), protected areas (WDPA via Protected Planet API v4), lakes and rivers (HydroSHEDS), land cover, elevation (Copernicus GLO-30 tiles, M-F2a-08, and FABDEM tiles for the slope only, M-F2a-07; neither is a layer of the registry or of the audit), population, transmission grid, roads (GRIP4), solar PVOUT (Global Solar Atlas, long-term average daily totals, kWh/kWp/day), wind (M-F1-03), ISIMIP3b climate (M-F1-04), ERA5 gust (M-F1-05), existing plants (M-F1-06). The seismic layer is not part of GeoFREA.
- **M-F1-03.** Global Wind Atlas products at 100, 150 and 200 m: `combined-Weibull-A`, `combined-Weibull-k`, `air-density`, and `wind-speed` (quality check only). Product existence is confirmed on the CDN response after redirect. Each product is checked against the country mask (M-F2a-01): when the country file holds a valid value in fewer than 99% of the mask pixels, F1 completes it from the files of the same product and height of the countries listed under `gwa_neighbours` in `config/countries.yaml`, in that order, where the country file has no value, without resampling (a file not on the same lattice is skipped). The country file stays as fetched, the completed file is derived beside it, and the registry points to the file later phases read. The code names no country.
- **M-F1-04.** ISIMIP3b bias-adjusted climate data for the five models of S-04, SSP1-2.6, SSP3-7.0 and SSP5-8.5 and the historical period: the variables `rsds`, `tas` and `sfcWind`, and the discharge of the global hydrological models (`dis`, `qtot`; cwatm, h08, miroc-integ-land, watergap2-2e). Reference 1995-2014, window 2041-2070. Acquisition and processing are adapted from CRAEI per A-11 (COMMAND 305): local files copied to `raw/isimip3b/` with checked hash, the rest downloaded with manifest, hash, access date and an alternative source if the URL fails. *Awaiting author verdict:* the daily variables of the hazard channel (M-F4-05).
- **M-F1-05.** ERA5 gust reanalysis (scenario-invariant extreme-wind indicator), built fresh. Reduction: annual maximum of `fg10`. Reference period 1995-2014.
- **M-F1-06.** Existing and planned plants from the Global Energy Monitor (GEM) trackers (operating, under construction, pre-construction, announced). GEM has two separate uses: as the input of the fleet (M1) and as external validation (F7b, M-F7b-01 to M-F7b-04). No parameter is fitted to plants without a spatial train and test split (V-06). The WRI Global Power Plant Database is not used.
- **M-F1-07.** GADM borders resolve local-first with checksum; network download is a fallback.

### F1b data_quality_audit

- **M-F1b-01.** Audit every active layer: coverage, nodata share, value ranges, resolution, CRS. Expected native resolutions and sanity ranges are configuration, not code. For each Global Wind Atlas layer the audit records the share of country-mask pixels with a valid value (`mask_coverage_pct`) and raises an alert below 99%.
- **M-F1b-02.** The audit's findings never block execution: an anomaly is reported, not enforced. The audit report is a declared input (`audit_report`) of F2b, F3 and F4; a failure to produce the report stops those phases (A-09), a finding in it does not.

### F2a grid_alignment

- **M-F2a-01.** Analysis grid: EPSG:4326, fixed 0.01 degree resolution, snapped so that 0.05 degree cells nest exactly (5 x 5 pixels). The country mask is the contiguous territory of GADM 4.1 level 0: the largest polygon plus every polygon that touches a kept polygon or lies less than 1 km from one (transitively); farther islands and exclaves are discarded (`mainland_only`, `core/geo_utils.get_contiguous_mainland_gdf`, `MAINLAND_MAX_GAP_KM`). The mask, the drawn outline and the admin1 units are one geometry: admin1 units that touch the territory are clipped to it. The boundary is GADM 4.1 as published (L-047). (D-F2a-021, D-F1-032.)
- **M-F2a-02.** All distances and areas are geodesic (`core/geodesy.py`), including slope derivation from the DEM.
- **M-F2a-03.** Distance rasters to the transmission grid, roads, rivers and substations store the uncapped WGS84 geodesic distance from the centre of each pixel to the nearest feature, measured to the exact feature and not to a rasterized copy: a point at its coordinates, a line densified to vertices at most 100 m apart (`shapely.segmentize`), a polygon by the vertices of its rings. The nearest target comes from a nearest-neighbour search in Earth-centred coordinates (`scipy.spatial.cKDTree`, in blocks when a layer has more than 6 million targets, with the result of a single tree) and the distance is the geodesic (`pyproj.Geod`) to that target alone. A target counts when its pixel is on the grid and, for the grid, roads and substations, in the country mask. Rows are computed in strips of 64, each in a checkpoint (`core/checkpoint.py`) so an interrupted run resumes. `distance_cap_km` (`geospatial.distance_cap_km`) only sets a `distance_capped` flag raster beside each distance raster; no stored distance is truncated, because the connection-cost model bills the real distance (M-F6-01, OQ-040). Error bounds and the replaced Euclidean method: `docs/evidence/land_and_potential/dist_sub_scale_audit.md`, `docs/evidence/land_and_potential/dist_scale_prototype.md` and `docs/evidence/land_and_potential/2026-10_distance_connection_cost_evidence.md`.
- **M-F2a-04.** Wind products are aligned per height; no combination across heights happens in F2a.
- **M-F2a-05.** Layers that hold counts (population) are brought to the analysis grid by summing the source pixels under each target pixel, each weighted by the fraction of its area inside the target pixel, never by sampling or interpolating; population density is the count over the geodesic pixel area. (D-F2a-014.)
- **M-F2a-06.** Land cover enters F3 as class counts, not one class per pixel: for every grid pixel, the number of 10 m ESA WorldCover samples in each class, block-counted from the native tiles. The same 10 m product is used for the three countries. The point-sample mosaic stays as a display layer. (D-F2a-015.)
- **M-F2a-07.** Slope enters F3 as a distribution, not a pixel mean: FABDEM V1-2 tiles (30 m) acquired per country (`scripts/acquire_fabdem.py`, pinned by sha256 in `external/fabdem/fabdem_manifest.json`), slope computed on the native samples (central differences, WGS84 geodesic spacing), each sample counted into the 1 degree slope bin of the grid pixel that contains its centre (41 bands, the last open ended). The share of a pixel above any slope maximum is read from the bins, so the maximum can be a range. A 1 degree square that FABDEM does not hold is read from GLO-30, and the squares that fall back and the area they cover are recorded in the F2a output (`slope_source`) and in the log. (D-F2a-016, D-F2a-028.)
- **M-F2a-08.** The aligned elevation is the mean of the 30 m Copernicus GLO-30 samples inside each grid pixel (a sample belongs to the pixel that holds its centre, an edge going below and east). The aligned slope raster is the mean of the slope of its samples with the same rule; elevation does not depend on the slope source. A pixel with at least one valid sample has an elevation; the slope also needs the stencil of its neighbours; a pixel with no sample, and every pixel outside the mask, has no value. The bundled `raw/elevation/<ISO3>/<ISO3>_elevation.tif` is read by no computation (OQ-061). (D-F2a-021, D-F2a-028.)
- **M-F2a-09.** Point of interconnection (`docs/thesis/methods/costs.tex`). `poi` is the uncapped geodesic distance (M-F2a-03) from each pixel centre to the exact point of the nearest OSM substation whose nominal voltage is at least `poi_voltage_threshold_kv` of `config/parameters.json` (BRA 138 kV, IND 220 kV, PRT 150 kV; Tier 2, OQ-065). The voltage of a substation is the highest value of its `voltage` tag (volts converted to kV; lists split on `;`, `_`, `/`, `,` or `|`; a bare number below 1000, a zero and non-numeric text are absent, never guessed). Substations are read as nodes, closed ways and relations (`scripts/fetch_osm_substations.py`); a node inside a polygon is dropped and a polygon is represented by its `representative_point`. A substation without a voltage takes the highest voltage of the OSM lines that touch it or pass within `geospatial.poi_line_tolerance_m` (50 m); one with no inferable voltage is excluded. Only substations whose pixel is in the country mask count. The counts per country are written beside the raster (`poi_counts.json`). A country with `connection.poi_sensitivity_threshold_kv` (IND, 132 kV) also gets the layer at that threshold; no phase reads it unless the sensitivity is run.
- **M-F2a-10.** Road classes. The distance to the road (`roads`) is the distance to a primary or secondary road: `geospatial.road_classes` lists the GRIP4 `GP_RTP` values (1 highways, 2 primary, 3 secondary) and the OSM `highway` values (motorway, trunk, primary, secondary) that count. A source with neither attribute is used whole.
- **M-F2a-11.** Settlements (`docs/thesis/methods/land_eligibility.tex`). `settlements` is the class of GHS-SMOD R2023A, epoch 2020, 1 km, one global file under `GEOFREA_DATA_DIR/external/ghsl/` (`scripts/acquire_ghsl_smod.py`; the SHA-256 of the archive and of the raster are pinned in `data_acquisition/fetchers/ghsl.py` and the raster hash enters the layer key). Each grid pixel takes, by nearest neighbour, the class of the 1 km cell that holds its centre (uint8 codes 10 to 30; 255 where the source has no value), built in its own child process under `geospatial.warp_mem_limit_mb`. A settlement is class 13 (rural cluster, village) or above (`land_availability.settlements.min_class`). A pixel with no class is not valid (A-09); a missing file is an error, never a country without settlements.

### F2b siting_layers

- **M-F2b-01.** Exclusion terms per technology, each the excluded share of a pixel in [0, 1]:
  - `E1 protected`: WDPA areas, every designation in the central case; the IUCN category list is a named-level parameter.
  - `E2 water`: lakes.
  - `E3 river corridor`: each HydroRIVERS reach is excluded within `W/2 + B_c(W)` of its centre line. `W = a Q^b` is the channel width from the long-term mean discharge `Q` (`DIS_AV_CMS`), `a = 7.2`; the central width is `7.2 Q^0.50`, and the permissive and restrictive widths are taken at the extremes of the exponent range 0.48 to 0.52, reach by reach, `7.2 min(Q^0.48, Q^0.52)` and `7.2 max(Q^0.48, Q^0.52)` (Andreadis et al. 2013), so that the corridors of the three scenarios are nested on every reach. `B_c` is the buffer from the channel edge in country `c`: Brazil, the five classes of the Forest Code, 30 / 50 / 100 / 200 / 500 m for `W` below 10, 10 to 50, 50 to 200, 200 to 600 and 600 m or more (the same in the three scenarios); Portugal, 10 m (permissive), 30 m (restrictive) and, central, 10 m for `W` below 10 m and 30 m beyond (Tier 3); India, 30 / 100 / 200 m (Tier 3). Overlapping corridors are a union. The corridor is merged with the water classes of the land cover by union, not by sum: `E3 = max(0, (c - w) / (1 - w))` for a corridor share `c` and a water share `w`.
  - `E4 slope`: the share of the pixel's 30 m slope samples above `slope_max_pct[tech]` (M-F2a-07), in percent (3 / 5 / 10 % PV and 10 / 20 / 30 % wind in the restrictive / central / permissive scenarios), read from the 1 degree bins with the share inside the bin that holds the threshold taken in proportion (error at most 0.33 % of the slope-eligible area, `docs/evidence/land_and_potential/group6_audit_97.md`).
  - `E5 land_cover`: the share of the pixel's 10 m land-cover samples outside the allowed classes (M-F2a-06). `excluded_classes[tech]` is a parameter of named levels with one central level, as in M-F2b-06.
  - `E6 settlements`: the share of the pixel within a geodesic setback of the settlement pixels of M-F2a-11, measured from their edge: PV 0 / 500 / 1,000 m and wind 500 / 800 / 1,000 m in the permissive / central / restrictive scenarios. The population-density threshold is the named sensitivity `population_density_200` (defined, not run).
  - E1, E2, E3 and E6 are measured on 10 x 10 sub-pixels per pixel (about 110 m): polygons by the centre of each sub-pixel, the corridors as buffers burnt on that grid, the settlement setback as a geodesic distance on it (OQ-045).
- **M-F2b-02.** Cost-driver layers: distance to the transmission grid (km; descriptive), distance to the nearest eligible substation `dist_sub_km` (km; M-F2a-09, the distance F6 bills), distance to roads (km; M-F2a-10). F3 averages each over the eligible area of the cell.
- **M-F2b-03.** Resource layers: solar PVOUT (kWh/kWp/day); wind Weibull A (m/s), Weibull k (-) and air density (kg/m3) at 100, 150 and 200 m.
- **M-F2b-04.** No normalization, weighting or scoring of any layer. Values keep physical units.
- **M-F2b-05.** Fail-loud on integrity failures of present files. An absent protected-area, lake or river layer for a configured country raises; a zero share is never assumed silently. The synthetic country fixture (A-06) provides these layers. Any other genuinely optional layer may be absent only if the absence is recorded in the artifact metadata (`assumed_free`).
- **M-F2b-06.** The parameters of E1-E6 and the minimum eligible area are declared in `config/experiments.yaml` under `land_availability`, each with one explicit value per land scenario (restrictive, central, permissive), its unit, source, tier and status (`verify` where the source needs checking); a null value is "no limit" in that scenario. Where the law leaves no choice (the Brazilian riparian classes) the three scenarios carry the same rule and vary the uncertain estimate it is applied to. Categorical parameters are named levels with one central level in all three scenarios. The scenarios feed U-06 and U-08. The residual land-use factor `luf` of `parameters.json` represents only what these exclusions do not map. Wind has one more parameter, `elevation_max_m` (D-F3-025): 2,000 m (restrictive), 3,000 m (central, Tier 3 without source, L-210) and none (permissive); a wind cell above the limit is not a candidate (M-F3-04). A cell without elevation is not a candidate for either technology (`land_availability.missing_elevation`, M-F3-04); only India has such cells. The altitude of a cell is the eligible-area-weighted mean of the aligned DEM (`elevation_m` of the F3 cell tables); F3 also counts the candidates with Weibull `k` below 1 at each height and excludes none.

### F3 land_eligibility

- **M-F3-01.** Pixel eligibility per technology: the eligible share of a pixel is `valid * (1 - E1) * (1 - E2) * (1 - E3) * (1 - E4) * (1 - E5) * (1 - E6)`, where `valid` is 1 only if all required layers have a value. Shares of different constraints are combined as independent, which counts overlapping constraints twice and understates the eligible area (conservative). A missing value is never read as free land. The eligible fraction in the cell tables and in `eligible_fraction_<tech>__<scenario>.tif` is the one after the minimum-area rules of M-F3-07.
- **M-F3-02.** Eligibility is computed for the three named land-availability scenarios of U-06 (central, restrictive, permissive), whose values are those of `land_availability` (M-F2b-06). Every potential output keeps land and is reported as the interval over the scenarios (U-08). The scenario compositions are in `docs/phases/F3_land_eligibility.md`.
- **M-F3-03.** Cell aggregation to 0.05 degree (5 x 5 pixels). Per cell and technology: `cell_area_km2` (geodesic land area inside the country); `eligible_area_km2` (geodesic sum of eligible pixel areas); `excluded_area_km2_<Ek>` (area excluded by each constraint, overlapping); `dominant_exclusion`; resource attributes as eligible-area-weighted means (`pvout_kwh_kwp_day`; `weibull_A_<h>`, `weibull_k_<h>`, `air_density_<h>`); `dist_grid_km`, `dist_road_km` (eligible-area-weighted mean of the uncapped distance) plus the `distance_capped` share; `admin1_id`, the GADM admin1 unit that covers the largest area of the cell inside the country, by geometry intersection (ties to the smallest identifier).
- **M-F3-04.** A cell enters the candidate set if `eligible_area_km2 > 0`, it has an elevation and, for a technology with an altitude limit in the scenario, its elevation is not above it; the minimum project size acts on the pixels (M-F3-07), not on the cell. A cell without elevation is not a candidate, for every technology and land scenario (`land_availability.missing_elevation: ineligible`, OQ-060). F3 counts, for the central scenario, the cells with eligible area that are not candidates, by reason (`missing_elevation`, `elevation_max`). The central candidate set is the set the later phases use (V1). The same rule applied to the other scenarios gives, per cell, the share of the named scenarios in which it is a candidate (candidate-set stability), reported and not used downstream.
- **M-F3-05.** Outputs: `candidates_<tech>.parquet` (one row per candidate cell, stable `cell_id`, with `admin1_id`), pixel and cell eligibility COGs (`eligible_fraction_<tech>.tif` of the central scenario and `eligible_fraction_<tech>__<scenario>.tif` of the others, which F5 reads to weight the pixels), dominant-exclusion COG. The per-constraint excluded shares of pixels are not persisted: F7b evaluates the pure eligibility engine of M-F3-01 at the pixels it needs. Files of a run at another scale (M-F3-06) are written under the scale-suffixed phase directory (A-08).
- **M-F3-06.** The cell size is a parameter of the run, `scale` (0.05 degree, 5 x 5 pixels, the default; or 0.1 degree, 10 x 10 pixels). F3 aggregates the same pixels with the same code (V-07). A run at 0.05 degree also writes `cells_0p1deg_<tech>.parquet`, the exact sum of the 2 x 2 cells, as an area check.
- **M-F3-07.** Minimum eligible area. Eligible pixels (fraction above 0) are grouped into clusters of 8-connected 0.01 degree pixels, labelled on the whole grid (D-F3-024), and a cluster is kept only if its eligible area (sum of eligible fraction x geodesic pixel area) reaches the minimum of the scenario. PV: none (permissive), 1 km2 (central), `P_ref / PD_PV` (restrictive). Wind: none (permissive); central, pixels with an eligible fraction below 10 % are dropped (one turbine per square kilometre); restrictive, the same pixel floor and a cluster of at least `P_ref / PD_wind`. The pixel floor acts before the clusters are formed. `P_ref` is `connection.reference_project_mw` and `PD` is the `power_density_mw_per_km2` of the scenario, read from `parameters.json`. F3 records, per technology and scenario, the clusters and the area the rules removed.

### F4 climate_forcing (v2; to be rebuilt)

The v1 code of F4 reads CMIP6; the rules below are those of v2 and are implemented when the code is rebuilt.

- **M-F4-01.** Climate members `m = (model, ssp)` for the window 2041-2070: 5 models x 3 SSPs = 15, plus the reference member `m0` with no change. The hydrological members are `(model, hydrological model, ssp)` (M-F4-03). *Awaiting author verdict:* the schema of the `member` key of the tables.
- **M-F4-02.** One climate set for every channel (S-04), chosen by the author in the v2 design (the five models span the ISIMIP3b range and have the hydrological simulations; evidence: `docs/evidence/climate/AR6.md`). No model is dropped by a channel rule until the data are inspected; any exception is recorded as a decision with its evidence.
- **M-F4-03.** Change factors, computed on the native grid of each model from monthly climatologies of the bias-adjusted data:
  - `delta_rsds = mean_window(rsds) / mean_ref(rsds)` (multiplicative);
  - `delta_wind = nbhd_mean(mean_window(sfcWind)) / nbhd_mean(mean_ref(sfcWind))` (multiplicative), with `nbhd_mean` the mean over the `wind_ratio_neighbourhood_cells` square of native cells centred on each cell (3 x 3, `config/experiments.yaml`), which keeps the ratio from exploding where a reference wind is near zero (OQ-042);
  - `dT = mean_window(tas) - mean_ref(tas)` (additive, K);
  - `delta_dis = mean_window(dis) / mean_ref(dis)` per hydrological model, the relative change of discharge (never the absolute discharge, because global hydrological models tend to overestimate it), reported as median and range over the combinations; the sign agreement rule is U-09.
  Reference period 1995-2014; annual means of the monthly climatology; means and factors computed in float64 from float32 files.
- **M-F4-04.** Change factors are bilinearly interpolated to the cell centres of the run scale (0.05 degree by default, 0.1 degree in V-07), and to the plant coordinates for M1.
- **M-F4-05.** Hazard channels. Mean resource (C1) enters F5 through M-F4-03. Operational extremes (C2: extreme heat and wind) and damage (C3: extreme precipitation) enter F5, F6 or M3 quantitatively only with a loss function of evidence Tier 1 or 2 (OQ-007); otherwise they are per-cell context indicators per member, reported as exposure and never entering the decision rules. The indicator definitions are `hazard_indicators` of `config/experiments.yaml`; the exposure thresholds are `hazard_thresholds` (OQ-051). `rx5day_mm` is the ETCCDI Rx5day (Zhang et al. 2011).
- **M-F4-06.** Outputs: `forcing.parquet` (`cell_id`, `member`, `delta_rsds`, `dT`, `delta_wind`, `dT_isolated_native_cell`), `forcing_masked.parquet`, `hazard_context.parquet`, `members.yaml` (resolved member list with provenance and channels), and the plant-level table of M1 (`delta_dis` per plant and member). A cell is flagged `dT_isolated_native_cell` when its native-cell `dT` departs from the median of its eight neighbours by more than `dt_isolated_native_cell_threshold_k` (1 K); flagged values are kept. *Awaiting author verdict:* the final schema when M1 is designed.
- **M-F4-07.** Validity mask for the wind factor: a cell-member whose `delta_wind` lies outside `wind_factor_valid_range` (`config/experiments.yaml`, 0.5-1.5, a plausibility bound with no source, OQ-043) is masked: `delta_wind` is NaN in `forcing.parquet`, the cell-member is absent for wind, and it is listed in `forcing_masked.parquet` with the rejected value. Solar never loses a cell-member for a wind reason. Nothing is replaced. Any consumer (F5) verifies, for the channels its technology reads, that every candidate cell and member has a row, that a NaN is declared in `forcing_masked.parquet` and that no factor is out of range (`climate_forcing/forcing.py::assert_forcing_usable`). *Awaiting author verdict:* whether the bound stays for bias-adjusted ISIMIP3b data.

### F5 technical_potential

- **M-F5-01.** Capacity per cell: `P_MW = eligible_area_km2 * LUF[tech, scenario] * PD[tech, scenario]`, with `PD` the power density on project footprint (MW/km2) and `LUF` the land-utilization factor. `luf` and `power_density_mw_per_km2` in `config/parameters.json` are required parameters of the technology (A-04, D-F5-011), each with three values, `scenario_values` (restrictive, central, permissive), paired with the land scenarios of U-06; `value` is the central one. LUF and PD scale every cell of a country and technology alike, so they change GW and TWh but not the LCOE of a cell.
- **M-F5-02.** Solar capacity factor: reference `CF0 = pvout_kwh_kwp_day / 24`; member `CF_m = CF0 * delta_rsds_m * (1 + gamma * dT_m)`, with `gamma` the module power temperature coefficient (1/K, negative; `gamma` in `config/parameters.json`). PVOUT already includes reference-climate thermal losses; the member correction is relative.
- **M-F5-03.** Wind capacity factor:
  - Hub height `H[tech, country]` is `hub_height_m` in `config/parameters.json` and must lie within the data heights, 100 to 200 m: outside them F5 raises, it does not extrapolate (D-F5-012). Weibull A at `H` by power-law interpolation between the bracketing heights, `A_H = A1 * (H/z1)^alpha` with `alpha = ln(A2/A1) / ln(z2/z1)`; `k_H` and air density linear in height. The reference run uses the 100 m layer; the 150 m layer is a sensitivity.
  - Reference turbine: the IEA 3.4-130 reference turbine (3.37 MW, rotor 129.82 m, hub 110 m, class IIIA) in every cell, country and member, with its power curve in `config/turbines/<curve_id>.csv` (provenance, licence Apache-2.0, `synthetic` flag and `reference_density_kg_m3` in the header). Power is zero below cut-in and above cut-out and linear between nodes; nothing is extrapolated. A curve with `synthetic = true` is refused in a production run (D-F5-003). A cell whose `V_ave = A * Gamma(1 + 1/k)` of the 100 m layer exceeds 7.5 m/s is flagged (`class_flag`); the flag changes neither `CF` nor eligibility.
  - Air density: `rho_ref` is the GWA layer at hub height; for member `c`, `rho_c = rho_ref * T* / (T* + dT_c)`, `T* = 288.15 K` (`ISA_T0_K`). The curve is evaluated at `v_eq = v * (rho_c / rho0)^(1/3)` (IEC 61400-12-1), and because a Weibull speed is a scale family, `A_eq,m = delta_wind_m * A_H * (rho_c / rho0)^(1/3)`. F5 reports per candidate cell `rho_ref / rho_ISA(z + H)` (ISO 2533) and counts cells outside 0.90 to 1.10; the check removes nothing.
  - The model is evaluated on every eligible 0.01 degree pixel, not on cell means (D-F5-038): `CF_p,m = eta_loss * I(A_eq,p,m, k_H,p)` with `I(A, k) = integral( P_curve(v) / P_rated * weibull_pdf(v; A, k) dv )` and `eta_loss` (`parameters.json`) the retention factor for wake, availability, electrical and soiling losses, applied once. The integral is closed form per linear segment with the regularized incomplete gamma function (the test reference is numerical quadrature, tolerance 1e-6, V-02), tabulated on a fixed `(A, k)` grid and read with a cubic spline in a run (`technical_potential.wind_cf_integral: table`; a point outside the grid is evaluated in closed form; error at most 6.5e-9 in CF, D-F5-039). `dT` and `delta_wind` are those of the cell of the pixel.
  - Aggregation to the cell: `CF_m = sum_p w_p CF_p,m / sum_p w_p` over the pixels with eligible area and every resource layer, `w_p` the eligible area of the pixel in the land scenario. Solar keeps the cell mean because `CF` is linear in `PVOUT`.
- **M-F5-05.** Annual energy: `E_m = P_MW * CF_m * 8760` (MWh/yr; the hours per year are a constant in `geofrea.core.constants`, D-F5-009).
- **M-F5-06.** Outputs, one file per technology and land scenario: `potential_<tech>__<scenario>.parquet` (`cell_id`, `member`, `P_MW`, `CF`, `E_MWh`); later phases read only the central one (V1). A cell-member declared in `forcing_masked.parquet` has no row. Wind also writes `class_flag_wind__<scenario>.parquet` and `weibull_distribution_wind.csv` (information only). Country aggregates, `potential_aggregates_<tech>.parquet`, one row per scenario and member, in two series: all present cells, and like-for-like over the cells present in every member. The climate effect on potential is computed on the like-for-like series inside each scenario, never across scenarios; the land range is reported beside it (U-08). `ensemble_<tech>__<scenario>.parquet` (`n_members`, `n_expected`, `incomplete_ensemble`) says how many members each candidate has (D-F5-041). The members of a technology are those that carry the channels of its CF model.
- **M-F5-07.** Maps of the potential, drawn by `potential_maps` at the reference climate in the common style (`docs/figures/style_guide.md`). The analysis cell (0.05 degree) is the finest unit: one pixel per cell, nothing smoothed. Per cell, central scenario: capacity density (MW/km2) and energy density (GWh/km2/yr), with robust colour limits (2nd and 98th percentiles); the capacity factor has its own map. Per state (admin1), in each land scenario: the same densities over the land area of the state, as a choropleth in 6 Fisher-Jenks classes of the central scenario (the same classes in the three scenarios, last class open, limits to 2 significant figures), with circles proportional to the state totals. The sum of cells and the sum of states must equal the F5 national total of `m0` within 0.1% in each scenario or the phase fails. Settings are `absolute_maps` of `config/experiments.yaml`; limits and totals are in `potential_breaks_<tech>.json`.

### F6 lcoe_modeling

- **M-F6-01.** LCOE kernel, vectorized over cells, for member `m` and parameter vector `theta`:
  - `C_inter = (line_cost_usd_per_km*tau_grid*dist_sub_km + bay_cost_usd + road_cost_usd_per_km*tau_road*dist_road_km) / P_ref` (USD/MW; M-F6-08) and `CAPEX_total = P_MW*(1000*capex_usd_per_kw + C_inter)`;
  - `OPEX_t = opex_fixed_frac * P_MW*1000*capex_usd_per_kw + opex_var_usd_per_mwh * E_t`;
  - `E_t = E_m * (1 - d)^(t-1) * eta_trans`, `t = 1..n`, with `d` the degradation of the cell (M-F6-09) and `eta_trans = max(0, 1 - alpha_loss*tau_grid*dist_sub_km)` (`alpha_loss = 0` in the central case, so `eta_trans = 1`, M-F6-10);
  - `LCOE = [CAPEX_total + sum_t OPEX_t/(1+r)^t] / [sum_t E_t/(1+r)^t]` (USD2024/MWh, real);
  - the climate of the member window is held constant over the asset lifetime;
  - `dist_sub_km` and `dist_road_km` are the real (uncapped) distances from F3; a linear cost in distance is a first-order approximation (L-019).
- **M-F6-05.** The kernel is a pure function importable by later phases (F7, M3).
- **M-F6-06.** Outputs: the nominal LCOE per cell and member at the central parameter vector, the cost ranges of M-F6-11 (the LCOE at the low and the high end of each range, reported as a range of the totals and not as futures, U-09), the supply curves per member at nominal parameters, and `lcoe_nominal_<tech>__<scenario>.parquet` for the restrictive and permissive land scenarios, which gives the land range of the potential. The central scenario is the one later phases use (V1). A technology whose `elevation_max_m` declares a reporting `sensitivity` (M-F2b-06) also has the supply curves without the cells above it (`supply_curve_<tech>__below_<N>m.parquet`). *Awaiting author verdict:* the exact table schema, which changes with the removal of the draw machinery (COMMAND 306).
- **M-F6-07.** Technology vintage and cost parameters. The reference commissioning year is `t_ref = 2024` (`commissioning_year` in `config/parameters.json`); costs are those of IRENA's report on 2024, in constant 2024 USD (S-07). PV capital cost is per kW DC (as IRENA states it) and no AC conversion is applied. The central `capex_usd_per_kw` is the weighted IRENA mean and its range runs from the P5 to `2 * mean - P5`. Fixed O&M is `opex_fixed_frac`, a fraction of the capital cost per year; variable O&M `opex_var_usd_per_mwh` is zero. `discount_rate` is the real after-tax regional WACC of IRENA 2024 (Figure 1.13: South America for BRA, Asia for IND, Europe for PRT; per technology), constant over the plant life, with the range of M-F6-11 (Tier 3); a real rate in constant USD needs no nominal conversion (OQ-054). `lifetime_years` has the central value 30 and the range of integers 25 to 30.
- **M-F6-08.** External connection cost. The plant capital cost covers everything inside the plant boundary (stated by IRENA for PV, assumed for onshore wind, L-051). Outside it F6 adds `C_inter` (M-F6-01) at year 0: the line length is `L_grid = tau_grid * dist_sub_km`, the road length `L_road = tau_road * dist_road_km`, and per-project costs (a line in USD/km, a bay at the receiving substation, a road in USD/km) are spread over a reference project `P_ref = 100 MW` for both technologies, a modelling convention applied identically in every cell (for PV a DC capacity, D-F6-028). Upstream reinforcement is not included: the result is the radial connection only. Unit costs are stored per country in the currency and price year of their source (`connection.line_cost_per_km`, `bay_cost`, `road_cost_per_km`: `value`, `low`, `high`, `currency`, `price_year`, `source`, `status`) and converted by F6 to constant 2024 USD with the national GDP deflator (World Bank `NY.GDP.DEFL.ZS`) and the 2024 average exchange rate (`PA.NUS.FCRF`), indices in `GEOFREA_DATA_DIR/external/world_bank/`. `tau_grid` and `tau_road` (tortuosity, 1.2 to 1.3, central 1.25, Tier 3) belong to the cost ranges. `P_ref`, the long-distance flag (100 km, Tier 3) and the losses are fixed. The IND bay and the BRA line and bay are proxies (status in `parameters.json`); the access road has no source and `connection.road_cost_excluded` is true (M-F6-10).
- **M-F6-09.** Degradation. Energy declines geometrically (M-F6-01). The rate of a cell is `d = d_low + w*(d_high - d_low)`, with `w` at the central value in the nominal case and on [0, 1] in the range. PV: the thermal zone of the cell (PVCZ-2019, Karin et al. 2019: nearest 0.25 degree land point within `geospatial.pvcz_max_distance_km`; fixed across members; zones above T7 take T7) picks `d_low` (median) and `d_high` (mean, never below the median) of the fleet of Jordan et al. 2022 (`scripts/derive_pv_degradation_by_zone.py`; crystalline silicon, ground mounting, zones with fewer than 20 systems pooled with the nearest). Wind: `d_low` 0.17 %/yr, `d_high` 0.53 %/yr (Hamilton et al. 2020, Tier 2); the complex-terrain rate of Kim and Kim (0.72 %/yr) is a deterministic sensitivity. In the central case T7 takes the rate of T6 (L-025); the sensitivity `pv_hot_zone_degradation` replaces the rate of T7 or above by 0.94 %/yr (Straub and Mueck 2025; zone shares in `docs/evidence/costs/pv_zone_shares_84.md`). All rates are transferred from United States fleets (Tier 2).
- **M-F6-10.** Losses, failure rules and sensitivities. Transmission losses are not modelled in the central case. A cell with a missing distance (or, for PV, a missing thermal zone) is excluded from the LCOE and counted, never given a zero cost. A cell beyond the long-distance flag keeps the same formula, is flagged `long_distance` and its potential share is reported. F6 refuses to run (`LcoeMissingInputError`, listing every item) while `group3_problems` is not empty: the `connection` block is absent, a cost has no value or a null price year, or the degradation entry is missing or out of range; a missing conversion index stops it too (`ConversionError`). Named sensitivities (not run by the central F6): `transmission_losses` (`alpha_loss` 0.03 to 0.05 %/km), `wind_complex_terrain_degradation`, `pv_hot_zone_degradation` and `road_cost_high` (the road billed at `road_cost_per_km_high`, the DNIT 2016 paved-highway cost converted to 2024 USD). Where no road cost has a source, `connection.road_cost_excluded` is true, the road term of `C_inter` is zero, F6 logs a warning and records it in the provenance: the LCOE is then a lower bound. A unit cost has the status `sourced`, `verify`, `proxy`, `provisional` or `to_be_sourced`; only `to_be_sourced` stops F6.
- **M-F6-11.** Range of the discount rate (DEC-072, DEC-082 a of v1; `docs/v1/inheritance.md`). For each country and technology the range of `discount_rate` is the union of the regional 2024 value of IRENA (2025), Figure 1.13, plus or minus one percentage point, and the 2021 country point of IRENA (2023), Figure A1. The ranges (Tier 3: the width is author judgment) are BRA solar [6.30%; 8.70%], BRA wind [4.90%; 8.70%], PRT solar [3.20%; 5.20%], PRT wind [2.70%; 4.70%], IND solar [3.00%; 5.90%] and IND wind [2.80%; 5.90%]. A range built by union is not centred on the central value (the central value, M-F6-07, stays the nominal).
- **M-F6-12.** Basis of the IRENA values. The IRENA 2024 solar TIC is per kW DC and its solar capacity factor is AC energy over DC module capacity (p. 92, footnote 27; p. 99, footnote 32); other technologies are AC to AC. The F6 capex per kW DC and the F6 cell CF per kWp are on the same basis as the IRENA solar values, so no DC/AC conversion applies. The residual difference is inverter efficiency and clipping, which F6 does not model (L-033, L-241). Source: International Renewable Energy Agency, *Renewable Power Generation Costs in 2024*, Abu Dhabi: IRENA, 2025, ISBN 978-92-9260-669-5.

### M1 fleet_risk (new; awaiting author verdict)

Question: how much does each existing and planned plant gain or lose in generation in each climate future?

- **M-M1-01.** Input: the GEM plants of hydro, solar and wind in operation, under construction, pre-construction and announced (M-F1-06), as a canonical table with coordinates, capacity, status and start year. The table of 145,781 plants already reconciled in `shared-data-sources` is the candidate source; it enters GeoFREA with provenance in the M1 design command (`GEOFREA_DATA_DIR/raw/gem_canonical/`). The part of the solar and wind data under a non-commercial licence stays marked and separable.
- **M-M1-02.** Output per plant and member: the relative change of generation. Solar and wind: the F4 and F5 change of the capacity factor at the plant coordinates (M-F5-02, M-F5-03). Hydro: the relative change of discharge `delta_dis` (M-F4-03) applied to the reference generation of the plant, never the absolute discharge. The product is the change in MWh/yr and in percent.
- **M-M1-03.** *Awaiting author verdict:* the function that links relative discharge change to generation (proportional, with a cap by installed capacity, run-of-river against reservoir) and its source. The command that designs M1 states the options and the evidence.
- **M-M1-04.** Hydrological members are `(climate model, hydrological model, ssp)`: the four hydrological models (cwatm, h08, miroc-integ-land, watergap2-2e) are an ensemble. M1 reports the median and the range over the combinations; a sign is robust when at least 2/3 of the combinations agree (U-09).
- **M-M1-05.** The plant table is an input of M1 and of the validation of F7b. M1 fits no parameter to plants (V-06).

### M2 supply_gap (new; awaiting author verdict)

Question: how much does the country gain or lose in total per climate future, and how is it distributed among regions?

- **M-M2-01.** The national net change of generation per member is the sum of the M1 change over all plants; the regional distribution is the sum by admin1 unit. The official demand is only an additional scenario, never the base.
- **M-M2-02.** M2 reports, per member, the net change, the sum of losses, the sum of gains and the shares by technology and region; the robust reading follows U-09.
- **M-M2-03.** *Awaiting author verdict:* the demand scenario source, the treatment of planned plants that may not be built, and the reference year of the fleet.

### M3 adaptive_expansion (new; awaiting author verdict)

Question: where should solar and wind be installed to cover the gap, at the lowest cost and risk?

- **M-M3-01.** Inputs: F1 to F6 (territory, potential, LCOE), the climate signal per cell and member, the exposure to extremes (M-F4-05) and the gap of M2.
- **M-M3-02.** The output is a portfolio of cells per member that covers the gap, with no arbitrary top-k fraction, and its cost range (U-09). Choosing the cheapest cells first is the reference; the risk-adjusted portfolio is compared with it (H3, H4).
- **M-M3-03.** *Awaiting author verdict:* the selection rule (cost and risk objective), the treatment of the gap that no cell can cover, and the use of the hazard exposure.

### F7 climate_evaluation (v2; to be rebuilt)

- **M-F7-01.** F7 evaluates the 15 climate members of the window with nominal parameters (U-09): the candidate-set metrics of F5 and F6, and M1 to M3, one member at a time, vectorized over cells and plants. There are no parameter draws and no per-future sampling; the run takes minutes.
- **M-F7-13.** Pre-registration guard (generalised from the guard of v1; ). The phases that take decisions with real data, F7, M1, M2 and M3, run on a real country only if the annotated git tag `prereg-v2` exists in the local repository and the digest of the country in its message equals the digest of the pre-registered subset computed from the live configuration (the selectors are widened in `prereg-v2`). A lightweight tag is refused. A country marked `synthetic: true` is ignored. The manifest records both digests. The error names the keys that differ. The guard runs in the orchestrator before the phase executes and does not cover a phase resumed from the manifest, a direct call of the build functions or an orchestrator built without it (L-244). Until `prereg-v2` exists these phases refuse real data. The flag `--real-run` stays required from F6 onwards on a real country.
- **M-F7-14.** *Awaiting author verdict:* the decision rules and thresholds of H1 to H5, entered in `prereg-v2` before any real run.

### F7b external_validation

- **M-F7b-01.** Share of existing plant capacity (GEM) located in excluded pixels, per exclusion constraint. Tests the exclusion set. The excluded share of each constraint at the pixel of a plant is evaluated by the pure eligibility engine of M-F3-01 on the aligned layers, not read from a stored layer.
- **M-F7b-02.** Enrichment ratio: share of existing capacity in the lowest nominal-LCOE deciles divided by the share of eligible area in those deciles.
- **M-F7b-03.** Comparison of national technical potential with published estimates, as a table with source and definition notes.
- **M-F7b-04.** Existing plants reflect past auctions, policy and grid access. Results are plausibility evidence, not accuracy.

### F8 results_synthesis

- **M-F8-01.** F8 reads persisted artifacts and never recomputes a scientific quantity.
- **M-F8-02.** F8 produces every output of Section 10 into `outputs/thesis/`, with a fixed style and one script per output, and the publication layer defined in the commands of the outputs sequence (216 to 223, adapted to v2).
- **M-X-01.** Cost to cover the gap (the v1 exploratory H5c redefined for v2; *awaiting author verdict*): per country and technology, the cost of the M3 portfolio against the cost in the reference, per member, reported as a range (H4).

---

## 6. Uncertainty and futures design

- **U-01. Futures.** The climate members of F4: 5 models x 3 SSPs per window, plus hydrological members for runoff (M-F4-03). Both identifiers are kept in every artifact. No probability is assigned across SSPs or models. Land availability and cost are not futures: their ranges are reported (U-06, U-03, U-08).
- **U-03. Cost uncertainty.** Cost parameters (`capex_usd_per_kw`, `opex_fixed_frac`, `discount_rate`, `lifetime_years`, `degradation_rate`, the connection unit costs, `tau_grid`, `tau_road`) have a central value and a range in `config/parameters.json` (U-05). The result is reported as a range of the totals at the low and high ends, not as an axis of futures: the diagnosis of v1 showed that cost uncertainty shifts every cell together and does not change the order among cells. `LUF` and `PD` change capacity and are paired with the land scenarios (M-F5-01). `gamma` (solar) and `eta_loss` (wind) enter the CF at their central value, with the range as a sensitivity.
- **U-05. Parameter schema.** Every scientific parameter in `config/parameters.json` is an object:

```json
{
  "value": "<nominal value>",
  "unit": "<unit>",
  "source": "<primary source>",
  "tier": 1,
  "range": {"min": "<min>", "max": "<max>", "distribution": "uniform", "source": "<source of the range>", "tier": 2},
  "proxy": false,
  "verified": false,
  "verified_by": null,
  "verified_date": null,
  "verification_method": "unverified"
}
```

  `range` is `null` for parameters that are not uncertain. A parameter paired with the land scenarios (`luf`, `power_density_mw_per_km2`) also carries `scenario_values` (`restrictive`, `central`, `permissive`), whose `central` equals `value`. `proxy` is true only when the value is of a different quantity or a different technology (for example, wind fixed O&M taken from solar O&M for BRA and IND, OQ-016); regional or global transfers of the same quantity and technology are Tier 2 (U-07). A production run fails if a consumed parameter has `proxy = true`; Tier 3 values and unsourced ranges raise a warning only.
- **U-06. Land-availability scenarios.** Three named scenarios declared in `experiments.yaml` and composed in `docs/phases/F3_land_eligibility.md`: `central`; `restrictive` (every range with status `sourced` at its restrictive end); `permissive` (every sourced range at its permissive end). Parameters without a sourced range stay central in all three (OQ-049). `central` feeds F4 onwards. Land stays in every potential output (eligible area, GW, TWh, LCOE, supply curves) and is reported as a range (V2).
- **U-07. Evidence tiers.** Tier 1: primary source specific to the country and technology, or a physical standard or constant. Tier 2: primary source transferred from another region or a global value, with the transfer rationale recorded. Tier 3: author judgment or no source; every Tier 3 value is listed in `docs/LIMITATIONS.md`.
- **U-08. Reporting rule.** Every main result is reported as a central value with its range, stating which axis the range comes from: land scenarios (U-06), cost ranges (U-03) or climate members (U-01).
- **U-09. Robustness rule.** The axis of the decision is the climate: 15 members per window. A result is robust when it holds in most futures: sign agreement in at least 2/3 of the models (the convention of the IPCC AR6 Atlas, Gutiérrez et al. 2021), reported with the worst case and the median over members. For hydrology the unit of agreement is the combination (climate model, hydrological model, SSP). The numeric thresholds of each hypothesis are pre-registered (M-F7-14).

---

## 7. Architecture requirements

- **A-01. DAG orchestration.** Each `PhaseSpec` declares `requires` and `produces` artifact keys. The orchestrator validates the graph at startup (missing producers, cycles) and orders phases topologically. Phases exchange data only through declared artifacts. A package imports only packages that come before it in the order configuration models (`config_models`), `core`, the phases in DAG order, the support packages; `tests/unit/test_import_dag.py` fails on any import against the order and on any cycle.
- **A-02. Artifact registry and fingerprints.** The per-country manifest records, for each artifact, its path, content hash, schema version, producing phase and run ID, and for each phase entry the METHODOLOGY version, wall and CPU time, peak memory, the memory cap and its excess (A-10), the environment versions and the fingerprints below. The reader accepts manifest schemas 2.1 to 2.14; the manifest is written to a temporary file and replaced, so an interrupted run leaves the manifest it had.
  - *Configuration fingerprint* (`config_fingerprint`, `core/config_fingerprint.py`): the parsed values, with defaults resolved, of the sections of `experiments.yaml`, `parameters.json`, `audit.yaml`, `technologies.yaml`, `settings.yaml` and `countries.yaml` that the phase reads (`PHASE_CONFIG_SCOPE`), and the power-curve files. A phase resumes only while its current fingerprint equals the recorded one, so a change of an unrelated section stales no phase.
  - *Code fingerprint* (`code_fingerprint`, `core/code_fingerprint.py`): the SHA-256 of the normalised syntax tree (`ast.dump` of Python 3.11, `FINGERPRINT_ALGO_VERSION` 1) of every module of the phase's package, or of its named modules, and of every `geofrea` module they import, transitively. Comments, docstrings, formatting, the manifest infrastructure, `main.py`, the configuration and third-party packages are not in it; string literals are. A test requires every module of a package to belong to exactly one fingerprint group (F5: the modules that write the potential tables, and the figure code). The caches outside the manifest hold the code fingerprint of the modules that compute them in their key (`core/cache_code.py`).
  - *Artifact hashes:* `sha256` of the bytes (integrity) and `content_sha256`, the canonical content hash without file metadata (`core/content_hash.py`: parquet by column names, types and values; GeoTIFF by data, CRS, transform and nodata; JSON and YAML by the parsed document; PNG by pixels). A re-registered artifact with an unchanged content hash keeps its run ID, and a consumer is marked stale only by a changed canonical content hash. The files of F2b (`siting/<layer>`) and F3 (`eligibility/<file>`) are registered one by one.
  - *Rebaselines:* `config_rebaselines` and `code_rebaselines` record the proofs under which a fingerprint was rewritten without running the phase again, when a change provably does not alter the result (`core/config_rebaseline.py`, `core/code_rebaseline.py`, `scripts/rebaseline_config_fingerprint.py`, `scripts/rebaseline_code_fingerprint.py`; D-core-057). The scripts refuse on any failed check; the orchestrator never writes these fields.
  - A phase whose upstream is not part of the current run loads upstream artifacts from the manifest; in-memory coupling between phases is not allowed.
- **A-03. Run targeting.** `settings.yaml` declares `run.target_phases`, `run.countries`, `run.technologies` and `run.rerun_phases`; dependencies are resolved from the DAG. `rerun_phases` re-executes exactly the phases it names; every downstream phase with a successful manifest entry is marked stale and recomputed the next time a run needs it (D-core-012). `main.py ... --plan` prints what the invocation would do (execute, resume, stale with the reason) and writes nothing.
- **A-04. Technology registry.** `config/technologies.yaml` declares per technology: resource layers, capacity-factor model, exclusion set, cost structure, required-parameter keys (the F5 inputs whose absence a production run refuses), and for wind the class flag and the power-curve id. Phase code contains no technology names.
- **A-05. Country agnosticism.** All country-specific mappings live in `config/countries.yaml`. A test fails if an ISO3 code literal appears in `src/` outside comments and docstrings.
- **A-06. Synthetic country.** A small synthetic country fixture runs every built phase in CI and is extended in the same change that builds a phase; a phase does not close its milestone until it runs on the fixture.
- **A-07. Formats.** Rasters are Cloud Optimized GeoTIFF, EPSG:4326. Tables are parquet with a Pydantic schema and a `schema_version`. Run ID = hash of configuration, methodology version and code commit.
- **A-08. Outputs layout.** All data live in `GEOFREA_DATA_DIR` (environment variable, never under the repository root): `raw/<source>/<ISO3|_global>/` (fetched or placed from the local database); `interim/<ISO3>/<layer>/` (caches); `outputs/<ISO3>/manifest.json` (and `manifest__<scale>.json` at a scale other than 0.05 degree); `outputs/<ISO3>/artifacts/<key>.json` (the summary of each phase, the artifact the manifest hashes, D-core-055); `outputs/<ISO3>/<phase>/<kind>/` (a run at another scale writes the phases that depend on cell size under `<phase>__<scale>`); `outputs/thesis/` (F8 only); `logs/<ISO3>/`. One map per file. `settings.yaml` `figures: all | summary | none`.
- **A-09. Failure policy.** Fail-loud; no silent fallback. A failure stops the phases that depend on it; independent branches may complete.
- **A-10. Memory.** Heavy phases process in batches under `settings.yaml` `memory.max_batch_gb` and in the per-phase caps of `config/memory_budget.json`: ceil(1.25 x the peak measured on the largest country) rounded up to 64 MB, 1,536 MB for a phase with no measurement; a phase goes on up to 25 % above its cap while the free memory covers the excess plus a reserve, and is stopped above cap x 1.25 or when it does not. The cap binds the runs of `main.py`, not the tests.
- **A-11. Reuse from reference repositories.** CRAEI (the climate-risk codebase, source of climate data acquisition and hazard processing) is the only reuse source under the copy-and-adapt rule: code may be copied into GeoFREA and adapted with a provenance header (repository, commit SHA, original path, adaptation summary). No imports from reference repositories, no shared package, no edits to CRAEI. `CRAEI_BASELINE_DIR` is read-only. geoworld_framework is consulted for logic only, never ported line by line.
- **A-12. Determinism.** Seeds are recorded in the manifest; reruns with the same run ID reproduce every artifact by value on the same platform: the canonical content hash (A-02) is equal, which is the guarantee; the bytes of a Parquet file are not, and a figure (PNG) is not part of the guarantee. The run environment (`GEOFREA_DATA_DIR` and the other location variables) is declared in `.env.example` and loaded at startup.
- **A-13. Traceability.** Functions implementing a method item cite it in the docstring (`Implements: M-F5-03.`).
- **A-14. Pre-registration.** The rules of H1 to H5 and the selectors of the digest are recorded in the annotated tag `prereg-v2` before any real run of F7, M1, M2 or M3 (M-F7-13).

---

## 8. Validation and testing

- **V-01. Frozen regression.** Binary and float parity against frozen fixtures for F1 outputs, F2a aligned rasters and exclusion layers E1-E3 (tag `regression-fixtures-v1`). Integer, categorical and binary layers: exact parity. Float rasters: `|new - ref| <= 1e-6 * |ref| + 1e-9` at every pixel, a missing value missing in both, unless a documented platform difference requires a larger bound. Fixtures are refrozen only with Douglas's authorization.
- **V-02. Analytical tests.** CRF and LCOE closed forms; Weibull CF against numerical integration; PVOUT to CF units; geodesic areas against reference values; power-law height interpolation.
- **V-03. Invariants.** `0 <= CF <= 1`; `eligible_area <= cell_area`; country capacity equals the sum of cell capacities; the generation change of the fleet equals the sum of the plant changes (M2).
- **V-04. Sanity ranges.** Configured physical ranges for every resource layer and derived quantity; violations are reported by F1b and raise in F5. The Weibull scale A and shape k have a Tier 3 validity limit at every height, A in (0, 25] m/s and k in (0, 10] (`validity_range` in `config/audit.yaml`): a candidate cell outside, or not finite, stops F5 with the layer, the number of cells and their coordinates. k below 1 and above 4 are physical and are only reported (M-F5-06).
- **V-06. No calibration on validation data.** No parameter is fitted to existing plants. A fit would require a spatial train and test split. GEM serves M1 as input and F7b as validation, two separate uses.
- **V-07. Scale check.** The chain from F3 reruns at 0.1 degree through the `scale` parameter (M-F3-06), with the same code and no scale-specific branch, and the statistics are reported side by side (MAUP).
- **V-08. Synthetic end-to-end.** A-06 in CI, through the last built phase; extended with each phase built.

---

## 9. Configuration files

| File | Content |
|---|---|
| `config/parameters.json` | Scientific parameters per country and technology, schema U-05 |
| `config/technologies.yaml` | Technology registry, A-04 |
| `config/turbines/<curve_id>.csv` | One reference turbine power curve per file, with provenance in the header (M-F5-03) |
| `config/countries.yaml` | Country-specific data mappings, A-05 |
| `config/experiments.yaml` | Climate members, windows, land-availability scenarios, hazard definitions, map settings; the sections of the v1 decision machinery leave with COMMAND 306 |
| `config/settings.yaml` | Operational settings: run targeting, grid resolution, figures, memory, paths |
| `config/audit.yaml` | Diagnostic-gate configuration of F1b: expected native resolution, sanity range and unit per layer (M-F1b-01) |
| `config/phases.yaml` | Display names of the phases (in no fingerprint) |
| `config/memory_budget.json` | Per-phase memory caps (A-10) |

---

## 10. Thesis outputs

Only these outputs belong to the dissertation. Every other file is a pipeline artifact. The outputs of M1 to M3 and F7 are defined in the commands that design them.

| ID | Type | Phase | Content | Answers |
|---|---|---|---|---|
| T-M1 | Figure | none | Framework DAG with the climate-member axis and the modules M1 to M3 | RQ0 |
| T-M2 | Table | config | Exclusion constraints, cost drivers, resource models, parameters with sources and tiers | RQ2 |
| T-M3 | Table | config | Climate members, cost ranges (nominal, range, source, tier, per country) | RQ4 |
| T-R1 | Figure | F5 | Technical potential maps (MW/km2 of cell) at reference climate, country by technology | RQ1 |
| T-R2 | Table | F5 | Eligible area, GW, TWh/yr at reference; range across members; interval across land scenarios | RQ1, RQ3 |
| T-R3 | Figure | F4, F5 | CF change by SSP, main window (median over the models of the SSP), with agreement marking: a cell is marked when at least two thirds of the models agree on the sign of the change of the CF (IPCC AR6 Atlas convention; a zero change agrees with no sign) | RQ3 |
| T-R9 | Table | F7b | External validation | RO5 |
| T-R11 | Figure | F6 | LCOE map at reference | RQ2 |
| T-O3 | Figure | F6 | Supply curves at nominal parameters, by SSP | RQ2 |

Reporting rule for the climate outputs: climate effects on potential are computed at the fixed central land set, and the land range is reported beside them (U-08).

---

## 11. Diagnostic figures

Per-phase maps are diagnostics for inspection and for the platform, generated under A-08. Minimum set per country and technology: F2b exclusion and cost-driver layers; F3 eligible fraction and dominant exclusion; F4 change factors per member; F5 CF and capacity per member; F6 nominal LCOE.

**Display resolution.** What a map draws is never what the analysis computes. Above 4 image pixels per cell of the analysis grid, a map draws the display layer of the same descriptive quantity on the 0.01 degree grid of F2a (capacity factor by the F5 model itself, eligible fraction, capacity and energy density), written by `potential_maps` as `display_*` artifacts with their own fingerprint and checked against the analysis (the CF aggregated to the cell, weighted by eligible area, equals the analysis value: to 1e-9 for wind, 1e-6 for solar). A continuous field that is still a block, or that comes from a climate model, is interpolated bilinearly with its mask and clipped by the country polygon; the subtitle says `display smoothing` and the source resolution (`absolute_maps.display_smoothing`: `auto` or `off`). Classes, categories and per-state maps are never smoothed. No total, LCOE, ranking or analysis artifact reads a display layer.

---

## 12. Milestones

The state of each milestone, phase and country lives only in `docs/PROGRESS.json`.

| Milestone | Content |
|---|---|
| V2-0 | Audit, cleanup and retirement of v1 records (COMMANDS 301 to 304) |
| V2-1 | ISIMIP3b acquisition integrated (305); v1-only code removed (306) |
| V2-2 | Design commands, with author verdict, of M1 (function from discharge to generation, source), M2 and M3; then code of each with tests and synthetic world |
| V2-3 | Publication layer and map standard (commands 216 to 223, adapted) |
| V2-4 | `prereg-v2` |
| V2-5 | Single run in the three countries and comparison with v1.1 |

---

## 13. References to verify

Full bibliographic details must be confirmed during the literature review before citation in the thesis.

- Andreadis, K. M., Schumann, G. J.-P., and Pavelsky, T. (2013). A simple global river bankfull width and depth database (Water Resources Research 49).
- Gutiérrez, J. M., et al. (2021). Atlas. In: Climate Change 2021: The Physical Science Basis, WGI AR6 (Cambridge University Press).
- Hamilton, S. D., et al. (2020). Wind plant performance degradation with age. Verify.
- IEC 61400-1 and IEC 61400-12-1; IPCC AR6 WGI (2021), reference period 1995-2014.
- Jordan, D. C., et al. (2022). Photovoltaic fleet degradation insights. Verify.
- Karin, T., Jones, C. B., and Jain, A. (2019). Photovoltaic degradation climate zones. Verify.
- Lopez, A., et al. (2012). U.S. Renewable Energy Technical Potentials (NREL); Maclaurin, G., et al. (2019). The Renewable Energy Potential (reV) Model (NREL); McKenna, R., et al. (2022). High-resolution large-scale onshore wind energy assessments: a review (Renewable Energy); Ryberg, D. S., et al. (2018). Evaluating land eligibility constraints of renewable energy sources in Europe (Energies); Wu, G. C., et al. (2017). Strategic siting and regional grid interconnections (PNAS); Deshmukh, R., et al. (2019). Geospatial and techno-economic analysis of wind and solar resources in India (Renewable Energy).
- Openshaw, S. (1984). The Modifiable Areal Unit Problem (CATMOG 38).
- Solargis / World Bank ESMAP. Global Solar Atlas PVOUT metadata (2025); International Renewable Energy Agency (2025). Renewable Power Generation Costs in 2024.
- Zhang, X., et al. (2011). Indices for monitoring changes in extremes based on daily temperature and precipitation data (WIREs Climate Change).
- Frieler, K., et al. (2024). Scenario set-up and forcing data for impact model evaluation and impact attribution within ISIMIP3a and ISIMIP3b (Geoscientific Model Development). Verify.

---

## 14. Changelog

| Version | Date | Change |
|---|---|---|
| 2.0.0 | 2026-11-24 | MAJOR (COMMAND 304): the specification of GeoFREA v2 replaces that of v1 (19.4.19): new question, modules M1 to M3, ISIMIP3b climate, robustness rule U-09, cost ranges, prereg-v2 guard; the F7 rules of v1, the satisficing, PRIM, regret and draw rules, the hypotheses of v1 and the changelog of v1 leave (`docs/v1/inheritance.md`, DEC-001). Items altered: A-01, A-02, A-03, A-04, A-05, A-06, A-07, A-08, A-10, A-11, A-12, A-14, M-E1-01, M-F1-01, M-F1-02, M-F1-03, M-F1-04, M-F1-05, M-F1-06, M-F1b-01, M-F2a-01, M-F2a-03, M-F2a-05, M-F2a-06, M-F2a-07, M-F2a-08, M-F2a-09, M-F2a-10, M-F2a-11, M-F2b-01, M-F2b-02, M-F2b-03, M-F2b-04, M-F2b-05, M-F2b-06, M-F3-01, M-F3-02, M-F3-03, M-F3-04, M-F3-05, M-F3-06, M-F3-07, M-F4-01, M-F4-02, M-F4-03, M-F4-04, M-F4-05, M-F4-06, M-F4-07, M-F5-01, M-F5-02, M-F5-03, M-F5-04, M-F5-06, M-F5-07, M-F6-01, M-F6-02, M-F6-03, M-F6-04, M-F6-05, M-F6-06, M-F6-07, M-F6-08, M-F6-09, M-F6-10, M-F6-11, M-F6-12, M-F7-01, M-F7-02, M-F7-03, M-F7-04, M-F7-05, M-F7-06, M-F7-07, M-F7-08, M-F7-09, M-F7-10, M-F7-11, M-F7-12, M-F7-13, M-F7-14, M-F7-15, M-F7-16, M-F7-17, M-F7-18, M-F7-19, M-F7-20, M-F7-21, M-F7b-01, M-F7b-04, M-F8-01, M-F8-02, M-F8-03, M-M1-01, M-M1-02, M-M1-03, M-M1-04, M-M1-05, M-M2-01, M-M2-02, M-M2-03, M-M3-01, M-M3-02, M-M3-03, M-X-01, M-X-02, M-X-03, M-X-04, M-X-05, MS-0, MS-1, MS-10, MS-11, MS-2, MS-3, MS-4, MS-5, MS-6, MS-7, MS-8, MS-9, S-01, S-02, S-04, S-05, S-06, S-08, T-M1, T-M2, T-M3, T-O1, T-O2, T-O3, T-R1, T-R10, T-R11, T-R12, T-R2, T-R3, T-R4, T-R5, T-R6, T-R7, T-R8, T-R9, U-01, U-02, U-03, U-04, U-05, U-06, U-07, U-08, U-09, V-01, V-03, V-04, V-05, V-06, V-07, V-08. <!-- lint: skip --> |
