# F3 land_eligibility





Methodology items: M-F3-01 to M-F3-07, M-F2b-01, M-F2b-06, M-F2a-11, U-06, U-08, V-07





## Contract





Requires: `siting_layers`, `aligned_rasters` (with `aligned/settlements`), `layer_registry`, `audit_report`, the parameters of the country (`connection.reference_project_mw` and `power_density_mw_per_km2`: the area of the reference project), `land_availability` (one value per scenario). Produces: `candidates_<tech>.parquet`, pixel and cell eligibility COGs, dominant-exclusion COG, 0.1 degree aggregation for V-07.





## Conformance





| Item | Requirement | Implementation (module:function) | Test | Status |


|---|---|---|---|---|


| M-F3-01 | Eligible share of a pixel = valid x (1-E1)...(1-E6), no missing value read as free; E3 is the river corridor net of the land-cover water, E6 the settlement setback (Group 6), and the share written is the one after the minimum area (M-F3-07) | `eligibility.py:eligible_fraction`, `exclusion_fractions`, `valid_pixels` | `test_land_eligibility_pipeline.py` | pass |


| M-F3-02 | Three named scenarios (central, restrictive, permissive) with one explicit value per parameter (D-F3-025); the full-factorial range report is retired with the ranges | `config_models/land_availability.py` (`ScenarioValue`), `scenarios.py:scenario_set`, `scenario_sets`, `check_scenario_order` | `test_land_eligibility_group6_values.py` (every value of the specification, per country, technology and scenario), `test_land_eligibility_pipeline.py` | pass on ZZZ and ZZZ2 (synthetic); IND and BRA rerun (D-F3-028), PRT not rerun |


| M-F3-03 | 5 x 5 aggregation: areas, excluded area per constraint, dominant exclusion, weighted resources and distances, capped share | `cells.py:aggregate_to_cells` (now accepts shares), `pipeline.py:build_eligibility` | `test_land_eligibility_cells.py`, `test_land_eligibility_pipeline.py` | pass |


| M-F3-03, D-F3-012 | `admin1_id` per cell: the GADM level-1 unit with the largest overlap, by geometry (a cell inside one unit takes it without an intersection), ties to the smallest identifier, a cell with no unit raises; `admin1_units.parquet` lists the units with their cell counts | `admin1.py:read_units`, `assign_admin1`; `pipeline.py:build_eligibility`, `_admin1_units` | `test_land_eligibility_admin1.py`, `test_zzz_end_to_end.py::test_every_cell_carries_the_admin1_unit_of_its_half_of_the_country` | pass |


| M-F3-04 | A cell is a candidate with any eligible area, an elevation and, for wind, not above the limit of the scenario (2,000 / 3,000 m / none) | `cells.py:candidate_cells`, `scenarios.py:candidate_exclusion_reasons`, `candidate_stability` | same | pass |
| M-F3-07 | Minimum eligible area: pixel floor, then clusters of 8-connected pixels labelled on the whole grid, by scenario | `min_area.py:label_clusters`, `cluster_areas`, `apply_minimum_area`, `write_minimum_area`; `pipeline.py:_eligible_after_minimum_area` (first pass by windows, labelling, second pass); `windows.py:ScenarioStripes.pass_eligible` | `test_land_eligibility_min_area.py` (labels against a flood fill, area, floors, a ribbon across all stripes), `test_land_eligibility_stripes.py` (stripe heights 200, 1,000 and the whole grid against the whole-grid oracle, bit for bit) | pass |


| M-F3-05 | `candidates_<tech>.parquet`, pixel and cell eligibility rasters, dominant exclusion | `pipeline.py` (`cells_<tech>`, `candidates_<tech>`, `eligible_fraction_<tech>.tif`, `eligible_area_km2_<tech>.tif`, `dominant_exclusion_<tech>.tif`) | `test_land_eligibility_pipeline.py` | pass (`table_schemas.py:CellRow` and `write_table`, A-07) |


| M-F3-06, D-F3-013 | The cell size is the run's `scale`: the same aggregation at 0.05 and 0.1 degree (a grid that starts inside a 0.1 degree cell is padded, the padding has no land); the default run also writes `cells_0p1deg_<tech>` (exact 2 x 2 sum) | `core/scale.py`; `cells.py:lattice_window`, `pad_to_window`, `aggregate_to_cells`; `pipeline.py:build_eligibility`, `_coarse` | `test_scale.py`, `test_zzz_end_to_end.py::test_the_coarse_cells_hold_the_same_land_and_eligible_area_as_the_fine_cells` | pass (the scale-check analysis itself is F7) |


| V-03 | eligible area <= cell area; cell total = pixel total | `pipeline.py:_check_invariants` (raises) | `test_land_eligibility_pipeline.py` | pass |





## Active implementation decisions





- **D-F3-025 — Group 6: the land rules of the specification (2026-11-05, COMMAND 97; METHODOLOGY 17.0.0; resolves OQ-046, OQ-047, OQ-049 and OQ-058; audit `docs/_audit/group6_audit_97.md`).** (a) E3: HydroRIVERS reach excluded within `W/2 + B_c(W)`, `W = 7.2 Q^b` from `DIS_AV_CMS`, `b` 0.48 / 0.50 / 0.52; `B_c` BRA the five Forest Code classes (equal in the scenarios), PRT 10 / 10-or-30 / 30 m, IND 30 / 100 / 200 m; corridors burnt once (union); merged with the land-cover water (class 80) as the corridor share net of the water, `max(0, (c - w) / (1 - w))` (decision C1, Douglas: `max`). (b) E6: setback around the GHS-SMOD classes of 13 or more (PV 0 / 500 / 1,000 m, wind 500 / 800 / 1,000 m), measured from the edge of the 0.01 degree settlement pixels on 10 x 10 sub-pixels; the density threshold is the named sensitivity `population_density_200`, defined and not run. (c) E4 in percent (PV 3 / 5 / 10, wind 10 / 20 / 30), read from the existing 1 degree bins (error of the slope-eligible area at most 0.33 %, audit section 3.1: no finer bins); wind altitude limit 2,000 / 3,000 m / none on the candidate set. (d) Minimum area (M-F3-07) on pixels: PV none / cluster 1 km2 / `P_ref / PD_PV`, wind none / pixel 10 % / pixel 10 % and `P_ref / PD_wind`, `P_ref` and `PD` of the scenario read from `parameters.json` by `main.py`; the 0.1 km2 cell filter is removed (Douglas): a candidate has any eligible area. (e) Whole-grid labelling fits the cap: the labels are one `int32` array of the grid (61 MB for BRA); a scenario with a rule is two passes (`pass_eligible` writes the fraction by windows, `write_minimum_area` labels and writes the result, the stripes of the cells read it); the stripe engine of D-F3-024 is unchanged and tested against the whole-grid oracle with the rules on. (f) The values live in `config/experiments.yaml` `land_availability` (where F3 already read them), not in `parameters.json`; only `P_ref` and `PD` come from `parameters.json`. (g) Nesting (Douglas, 2026-11-05): for `Q` below 1 m3/s `Q^b` falls as `b` grows, so the extreme exponents would not nest the corridors; the width is taken at the extremes of the range reach by reach, `W_perm = 7.2 min(Q^0.48, Q^0.52)`, `W_restr = 7.2 max(Q^0.48, Q^0.52)`, `W_central = 7.2 Q^0.50` (`river_widths_m(..., exponent_range)`), the corridors are nested by construction and the scenario order check has no tolerance beyond float noise (the earlier 0.5 % tolerance and its limitation are removed; tests with `Q` below and above 1 m3/s). (h) The settlement layer is `aligned/settlements` (D-F2a-027). V-01 (`e3_river_corridor_share`, `e6_settlement_share`, `f2a/ZZZ_settlements_aligned`) and the ZZZ and ZZZ2 hand values were rederived with Douglas's authorization: the 30 earlier V-01 layers are bit-identical, the new ones checked by hand (corridor 30.0 share-pixels, setback ring 4.6 beyond the 4 pixels); the independent validator passes 42 of 42 (wind) and 40 of 40 (solar) on ZZZ2.
- **D-F3-026 — Memory and results of Group 6 (2026-11-05).** F3 of BRA, scratch directory, cold shares, `scratchpad/f3_profile_97.py`: peak 1,375 MB (cap 1,536), 1,501 (cold shares) s; the settlement layer of F2a peaks at 315 MB. PRT (scratch, indicative only, not a round): central eligible area solar 9,151 km2 and wind 29,831 km2 (before: 21,169 and 28,136), restrictive 4,355 and 18,276, permissive 19,527 and 35,810. BRA, scratch, central eligible area solar 1,130,465 km2 and wind 2,640,018 km2 (before: 1,535,473 and 2,196,099), restrictive 694,056 and 2,150,819, permissive 1,717,531 and 2,836,254; the cluster floor removed 305 km2 of solar (central) and the pixel floor 27,728 km2 of wind. Real countries are not rerun here (PIPELINE_GUIDE, Group 6 round); the estimate on the synthetic world ZZZ2 is in `docs/_audit/group6_audit_97.md` section 10.
- **D-F3-027 — ZZZ2 after Group 6: why the PRIM assertion of solar changed (2026-11-05, Douglas's request).** The land rules changed the eligible area of the 17 candidate cells of ZZZ2 (solar central 410.9 -> 470.3 km2, wind 410.9 -> 467.1 km2), so the shortlist margins and the displaced-capacity outcome of the futures changed. Wind: the PRIM box is the same as before (`discount_rate|line_cost_usd_per_km|gcm`, 119 cases, density 1.0, coverage 0.655). Solar: the box before was `opex_fixed_frac|bay_cost_usd|delta_rsds_mean` (213 cases, density 0.875, coverage 0.920, base rate 0.740, displaced-share quartiles 0 / 0.21 / 0.42); after it is `capex_usd_per_kw|delta_rsds_mean|gcm` (205 cases, density 0.929, coverage 0.571, base rate 0.712, quartiles 0.15 / 0.35 / 0.35). The old assertion `gcm` not in the box no longer holds, because PRIM (greedy peeling) reaches another local optimum on the changed outcome and the climate model enters it. The test now pins the exact set of restricted inputs as observed and keeps the validator's numbers for cases, density and coverage (42/42 and 40/40 hand checks do not cover the identity of the restricted inputs). Open for Douglas: ZZZ2 solar was designed techno-economic-dominated; whether to re-tune its parameters so that the box is free of the climate model again is registered as OQ-071 and not implemented.
- **D-F3-028 — Group 6 on the real countries IND and BRA; slope under canopy (2026-11-06, COMMAND 99).** (a) F3 to `potential_maps` ran for IND and BRA on the 17.0.0 rules and was published to the reference store as round `74931e0a`; PRT is not rerun. The four `potential_maps` rasters (`capacity_factor_*`, `potential_density_*`) differ from the 16.3.0 state because `technical_potential` and `potential_maps` were `stale_upstream` and were rebuilt on the new cells; they are declared in `expected` of `config/deferred_checks.yaml` (reason "células do Grupo 6", pinned to `74931e0a`). (b) Change of the eligible area by criterion, with the old and the new limit of each criterion, per technology and scenario: `docs/_audit/group6_decomposition/{PRT,IND,BRA}.md` (BRA central: solar -26.4 %, wind +20.2 %; IND central: solar -4.5 %, wind +12.2 %). (c) Slope under canopy, diagnostic only (`docs/_audit/slope_canopy_99.md`): GLO-30 is a DSM; 59 to 74 % of the E4 cut (independent reading; bounds 49 to 88 %) lies in classes the land cover already excludes, and the mean E4 of pixels with at least 90 % trees is 1.5 to 3.4 times (BRA) and 3.3 to 35 times (IND) that of open-vegetation pixels. In IND trees and hills overlap, so this is consistent with a canopy effect, not proof. Nothing in the pipeline changed.
- **D-F3-001 — `cell_id` is a global lattice index, with `row`, `col` and the cell center stored beside it (2026-10-06, Douglas's verdict).** The decision unit is a 0.05 degree cell (S-06, 5 x 5 pixels of the 0.01 degree grid, M-F2a-01). Cells live on one global lattice anchored at the north-west corner (90 N, 180 W): `row` counts southward, `col` eastward, `cell_id = row * 7200 + col` (3600 x 7200 = 25,920,000 ids, fits int32). Output tables carry `cell_id`, `row`, `col`, `lat_c`, `lon_c` (M-F3-05 only requires the id; the other columns are for joins and human reading). Why this and not another indexing: (a) the id is an identifier only and changes no number in any result; what it governs is joins between phases, reruns, the order used to break ties, and traceability. (b) A country-bounding-box index would renumber a country whenever its polygon or extent changes (the PRT `mainland_only` change of 2026-10-06 would have renumbered every PRT cell) and would not be comparable across countries. (c) A string of center coordinates is stable but heavy and fragile as a join key. (d) A Morton/Z-order code adds spatial locality that nothing here needs. (e) The anchor (90, -180) is an exact multiple of 0.05 (1800 and -3600 steps), so the 0.01 pixels nest 5 x 5 and the 0.1 degree V-07 cells nest 2 x 2 in the same index (`coarse_cell_id`). All arithmetic is on integers (rounded step counts), never on compared float coordinates. A cell on a border has the same id in both countries; the key is (country, `cell_id`), and each country's `cell_area_km2` is its own land area inside the cell. Implementation: `src/geofrea/land_eligibility/cells.py`. The grid it aggregates must be the F2a grid snapped to the 0.05 lattice (`GridNotOnLatticeError` otherwise).


- **D-F3-002 — Engine and parameters (2026-10-07, Douglas's approval of `docs/_audit/2026-10_f3_parameter_research.md`; resolves OQ-002, OQ-003, OQ-015, OQ-044 and OQ-045). The parameter values below are superseded by D-F3-025; the engine and the land-cover classes stand.** Central values in `config/experiments.yaml` `land_availability`: solar slope 10 deg, wind slope 16.7 deg (30%), population density 100 persons/km2, riparian setback 0.5 km, IUCN Ia/Ib/II, `min_eligible_area_km2` 0.1, solar excludes tree cover and cropland (conservative: land in use, Douglas), wind excludes tree cover only; ranges where sourced (wind slope 10.2-30 deg, density 100-200, setback 0.25-1.0 km), the rest held at the central value and declared (OQ-049). Land-cover classes follow ESA WorldCover (10 tree, 40 crop, 50 built-up, 70 snow, 80 water, 90 wetland, 95 mangrove excluded as listed per technology). Phase `land_eligibility` in `main.py` (requires aligned rasters, siting layers, layer registry and the F1b audit report); engine: `land_eligibility/{parameters,fractions,eligibility,pipeline}.py`.


- **D-F3-003 — Sub-pixel shares for E1-E3, independence rule, conservative direction (2026-10-07).** Protected areas, lakes and the riparian setback are measured on 10 x 10 sub-pixels per 0.01 degree pixel (`fractions.py`; riparian by geodesic distance transform, shares kept for the setbacks 0.25, 0.5 and 1.0 km and interpolated in between, never extrapolated), so a 0.5 km setback no longer means "the pixel contains a river" (OQ-045 option c). Shares of different constraints are multiplied as independent; overlaps (a lake inside a setback) are counted twice, so the eligible area is understated. Population density = aligned count / geodesic pixel area (D-F2a-014); a pixel without a population, slope, land-cover or required resource value is not eligible (PRT 0.0%, IND 1.1%, BRA 0.7% of pixels). Shares are cached in `interim/<ISO3>/land_eligibility/` keyed by the source file, grid and thresholds.




- **D-F3-005 — E5 from class counts and the riparian discharge parameter (2026-10-07, M-F2a-06, commit 228f42b; Douglas approved both).** (a) E5 is the share of the pixel's 10 m samples outside an allowed class (F2a counts, D-F2a-015); samples of no class (open sea) count as not allowed; a pixel with no sample at all is invalid. PRT country totals do not move (solar 31.2%, wind 34.9% before and after) while the candidate cells change (3,381 to 3,505 solar, 3,421 to 3,520 wind), as expected: the totals were unbiased, the cells were noisy. (b) (superseded by D-F3-025) New parameter `riparian_min_discharge_m3s` (central 0, range 0-10, `range_set_by_douglas_unsourced`): a stream counts for E3 only if its HydroRIVERS `DIS_AV_CMS` is at least the threshold. Shares are prepared on the grid `riparian_discharge_grid_m3s` = 0, 1, 5, 10 times the setbacks 0.25, 0.5, 1.0 km and interpolated bilinearly; outside the grid is an error. PRT E3 excluded share (share of the land): 12.7 / 24.5 / 45.9% at 0.25 / 0.5 / 1.0 km for every stream, 9.2% at 0.5 km and 1 m3/s, 3.8% at 5, 2.5% at 10. (c) E4 is now the share of the pixel's 30 m samples above the slope maximum, from Copernicus GLO-30 (D-F2a-016): the DEM F1 holds is a 550 m resample, so the earlier E4 understated the exclusion. PRT: solar 31.2% to 23.9% eligible, wind 34.9% to 31.7%; E4 excludes 31.7% (solar, 10 deg) and 14.0% (wind, 16.7 deg). The literature thresholds' DEM resolution is unknown, so this is the stricter reading and the slope range is where that uncertainty lives (OQ-049).




- **D-F3-007 — Land stays in every output and leaves the futures of F7; three named scenarios (2026-10-08, Douglas's verdicts V1 and V2, METHODOLOGY 7.0.0).** (a) Land is in the pipeline and in every potential output (eligible area, GW, TWh, LCOE, supply curves); it is removed only from the set of futures over which F7 computes regret: the F7 candidates are the central-set candidates (basis: `docs/_audit/2026-10_systematic_review.md` Appendix A, candidate-set Jaccard 0.96 or more in BRA and PRT, about 0.90 in IND, while the eligible area moves -38% to +25%). (b) The full factorial of the land parameters that have a range is used only to report ranges. (c) (superseded by D-F3-025) Scenarios, replacing strict/lenient: `central`; `restrictive` (every range with status `sourced` at its restrictive end); `permissive` (every sourced range at its permissive end). Composition today (`config/experiments.yaml` `land_availability`): solar, riparian setback 1.0 km (restrictive) and 0.25 km (permissive), central 0.5 km; wind, riparian setback 1.0 and 0.25 km, slope maximum 10.2 and 30 degrees, central 16.7 degrees. Held at central in all three, and listed as such: solar slope (10-15, literature lead), population density (150-300, unsourced), minimum discharge (0-10, unsourced), `min_eligible_area_km2` (no range), and the categorical `excluded_classes` and `iucn_categories` (one central level each). A parameter joins the scenarios when its source is recorded (OQ-049). (d) Land ranges are reported as the interval of the potential outputs and as candidate-set stability (share of the named scenarios in which a cell is a candidate, M-F3-04), with the axis stated (U-08). (e) Limit: IND stability rests on the Tier 3 density value (L-020). Implemented 2026-10-08: `land_eligibility/scenarios.py`; F3 writes `cells_<tech>__<scenario>.parquet`, `candidates_<tech>__<scenario>.parquet` for the three scenarios and `candidate_stability_<tech>.parquet`; rasters, the 0.1 degree table and F4-F7 stay on central. The full factorial range report is not built. Not yet run on real data.


- **D-F3-008 — IND land cover from the 10 m WorldCover tiles (2026-10-08, Douglas's verdict V19, METHODOLOGY 7.0.0).** IND switches from the 100 m tiles to the 10 m ESA WorldCover tiles already downloaded (`raw/esa_worldcover/IND`); the centre-count mode of M-F2a-06 is removed and the text "anything else is an error" stands (D-F2a-017). If the 10 m tiles do not block-count exactly on the 0.01 degree grid, work stops and is reported instead of keeping the centre mode. MS-5 closes only with a clean rerun of F2a to F3 in the three countries; applied on 2026-10-08: the IND numbers hardly changed (D-F3-009).





- **D-F3-009 — Clean rerun of the three countries with the 7.0.0 code and the three named scenarios (2026-10-08).** The three countries were executed on a clean tree at commit eb82aef (`dirty` false); commit eb82aef included the orchestrator change that drops unregistered phases from the manifest. One more fix followed (commit 30363aa: the manifest's own `run_id` and `dirty` describe the latest run, which the manifests had kept from their first run), without touching the F3 code. PRT and BRA: `python main.py PRT BRA --phases land_eligibility,overview --rerun land_eligibility,overview`. IND: the old `IND_land_cover_counts_aligned.tif` (100 m tiles, centre-count mode) was deleted and `python main.py IND --phases land_eligibility --rerun grid_alignment,land_eligibility` counted the 91 tiles of 10 m exactly (D-F3-008, D-F2a-017; 1,763 s), then F2b and F3 ran. A final `python main.py PRT BRA IND --phases land_eligibility` resumed everything and wrote one run id into the three manifests. Per cell, restrictive <= central <= permissive eligible area was asserted for the six country-technology pairs and holds. Candidate and area figures below come from the stored tables (`cells_<tech>__<scenario>.parquet`, `candidates_<tech>__<scenario>.parquet`); the Jaccard compares each scenario's candidate set with the central one.





| Country | Tech | Scenario | Candidates | Eligible area (km2) | Share of land | Jaccard vs central |


|---|---|---|---|---|---|---|


| PRT | solar | central | 3,446 | 21,169 | 23.9% | 1.000 |


| PRT | solar | restrictive | 3,356 | 15,704 | 17.7% | 0.974 |


| PRT | solar | permissive | 3,486 | 24,052 | 27.1% | 0.989 |


| PRT | wind | central | 3,496 | 28,136 | 31.7% | 1.000 |


| PRT | wind | restrictive | 3,369 | 17,562 | 19.8% | 0.964 |


| PRT | wind | permissive | 3,558 | 35,247 | 39.7% | 0.983 |


| BRA | solar | central | 180,041 | 1,535,473 | 18.0% | 1.000 |


| BRA | solar | restrictive | 173,840 | 1,067,692 | 12.6% | 0.966 |


| BRA | solar | permissive | 181,897 | 1,767,638 | 20.8% | 0.990 |


| BRA | wind | central | 181,277 | 2,196,099 | 25.8% | 1.000 |


| BRA | wind | restrictive | 175,154 | 1,437,182 | 16.9% | 0.966 |


| BRA | wind | permissive | 183,324 | 2,626,748 | 30.9% | 0.989 |


| IND | solar | central | 54,182 | 146,180 | 4.9% | 1.000 |


| IND | solar | restrictive | 48,486 | 105,179 | 3.5% | 0.895 |


| IND | solar | permissive | 56,057 | 166,164 | 5.6% | 0.967 |


| IND | wind | central | 62,718 | 509,287 | 17.2% | 1.000 |


| IND | wind | restrictive | 56,190 | 354,688 | 12.0% | 0.896 |


| IND | wind | permissive | 65,454 | 598,110 | 20.2% | 0.958 |





  Central results are those of D-F3-006 (PRT 23.9 / 31.7%, IND 4.9 / 17.2%, BRA 18.0 / 25.8% for solar / wind) and the PRT and BRA scenario figures equal the in-memory sweep of Appendix A of `docs/_audit/2026-10_systematic_review.md`. IND against the previous round (about 100 m land cover): solar candidates 54,071 to 54,182 (+111), eligible area 146,152 to 146,180 km2 (+0.0%), Jaccard of the central candidate sets 0.987; wind candidates 62,696 to 62,718 (+22), eligible area 509,298 to 509,287 km2 (-0.0%), Jaccard 0.997. Per-cell area change: median 0.000, 5th to 95th percentile about -0.07 to +0.07 km2 (solar) and -0.04 to +0.04 km2 (wind). The 100 m tiles, then, were already a good description of the 10 m product at the 0.01 degree pixel; the IND numbers of Appendix A stand. The IND restrictive scenario drops 10.5% (solar) and 10.4% (wind) of the central candidates; with the unsourced ranges the stability would fall further (L-020).





  Manifests (all three): `dirty` false, one `run_id`, schema 2.3, seed `sampler` 42, no `suitability_criteria` entry or artifact (dropped by the orchestrator at this run, V16). Phase entries executed in this run carry `methodology_version` 7.0.0 (PRT and BRA: land_eligibility, overview; IND: grid_alignment, siting_layers, land_eligibility); entries resumed from earlier runs carry none, because they were produced before manifest 2.3. In IND, climate_forcing, hazard_context, climate_maps and overview are `stale_upstream`: the orchestrator marks every consumer of `aligned_rasters` stale after the grid_alignment rerun, although F4 reads only the grid, which is unchanged; recomputing them is the 7.5 hour F4 run, not done here (core.md D-core-012, OQ-031). Resolved the same day by verdict E: see D-F3-010 and core.md D-core-024.


- **D-F3-010 — Verdicts A to G of 2026-10-08: V-01 refrozen on the shares, old F3 files deleted, DAG narrowed (METHODOLOGY 7.0.1).** (a) V-01 (verdict G, Douglas's authorization of 2026-10-08): the frozen E1, E2 and E3 of `tests/fixtures/v01/zzz.npz` are now the excluded shares F3 computes on the ZZZ country (`e1_protected_share`, `e2_water_share`, `e3_riparian_share`: sub-pixel coverage by `polygon_coverage_fraction` and `river_fractions`, every protected designation, central setback and discharge threshold) instead of the binary masks of the retired legacy phase; the 26 F1/F2a layers are bit-identical to the previous fixture, the file `tests/regression/frozen_binary_masks.py` was removed, the new layers hold 25 (E1), 4 (E2) and 27.0 (E3) in total share-pixels, E3 with 60 fractional pixels. (b) Verdict F: the F3 outputs without a scenario suffix were deleted for the three countries (outputs/<ISO3>/land_eligibility/artifacts/): PRT cells_solar, candidates_solar, cells_wind, candidates_wind; BRA cells_solar, candidates_solar, cells_wind, candidates_wind; IND cells_solar, candidates_solar, cells_wind, candidates_wind (12 files, all `.parquet`, written 2026-10-07; their values live on in the `__central` tables). (c) Verdict E: F3 now requires the named aligned layers it reads and F4 requires the `reference_grid` artifact (core.md D-core-024); F3 and siting_layers were rerun for the three countries to record the new lineage, with identical results (same candidates and areas as D-F3-009). (d) Verdict D: the run status of the last F3 run of each country has no warning or error in its log, so F3 is `ran_clean` in the three countries; the source quality that D-F3-009 listed is in LIMITATIONS (L-020) and OPEN_QUESTIONS (OQ-047, OQ-049).





- **D-F3-011 — F3 on the synthetic country, I-4 and A-06 (COMMAND 16, 2026-10-08).** `tests/synthetic/test_zzz_end_to_end.py` runs F1 to F3 (and F4, F5) on ZZZ with no network: eligible area never above the cell area for both technologies and the three scenarios, the sum of cell eligible areas equal to the pixel total computed independently from `eligible_fraction_<tech>.tif` weighted by the geodesic pixel area (rtol 1e-6), and the scenarios ordered by eligible area. The ZZZ land cover has three bands of whole decision-cell rows (verdict 16b, 2026-10-09): cropland in the north (excluded for solar, allowed for wind), grassland in the middle (allowed for both) and tree cover in the south (excluded for both), so both technologies have candidates: solar 6 cells (12.0% of the land eligible in the central scenario, 9.7% restrictive, 12.9% permissive), wind 17 cells (55.8%, 51.0%, 57.8%). The generator also gained the river attribute `DIS_AV_CMS` = 50 (a test value above every discharge threshold), which F3 needs for the riparian discharge parameter (M-F3-02, D-F3-005). The land-cover change moves the two land-cover layers of V-01 (see D-F2a-018).


- **D-F3-012 — `admin1_id` in the cell table (2026-10-09, D13 of the F7 design report; M-F3-03).** Each cell carries the GADM admin1 unit that covers the largest area of its in-country part, by geometry intersection (never a bounding box); ties go to the smallest unit identifier; the units are written beside the table with their names. A cell with no overlap with a unit is an error, not a null.


- **D-F3-013 — Scale as a run parameter (2026-10-09, D11 of the F7 design report; M-F3-06, V-07).** The cell size is `scale` (0.05 degree, 5 x 5 pixels, the default; 0.1 degree, 10 x 10 pixels). The same aggregation function runs for both, the cell lattice is global and its identifiers depend on the scale, and the files of a non-default scale go under `land_eligibility__<scale>` (A-08). The 0.05 degree run still writes `cells_0p1deg_<tech>` as the exact 2 x 2 sum, which the 0.1 degree run must reproduce for the areas.


- **D-F3-017 — The limit of 3000 m also removes the cells with no elevation (2026-10-17, real round, OQ-060).** F3 ran again in PRT, IND and BRA (`--rerun land_eligibility`; the manifest resume did not see the change of `experiments.yaml`). PRT is identical in content in all 23 files; IND changes in the wind candidates and cells (central 62,718 to 61,366 cells, 509,050 to 507,112 km2; highest elevation 6,218 to 2,992 m); BRA, expected identical, loses one wind candidate (cell 14287116, no DEM elevation) in the central and the permissive scenarios. The rule `elevation <= limit` is false for NaN, so 36 central cells of IND (35.7 km2) and that cell of BRA are out although not above 3000 m. Left as implemented by the author's decision to go on; the question is OQ-060 and the numbers are in L-044. F3 of BRA needs about 4.4 GB resident (peak 4.39 GB, 574 s) and failed twice with `MemoryError` when only 3.2 GB of commit memory was free.
- **D-F3-018 — A cell without elevation is not a candidate, with a reason of its own (2026-10-18, COMMAND 51; METHODOLOGY 15.0.2; OQ-060 closed; supersedes the open question of D-F3-017).** The diagnosis (read only, from the F3 tables of 2026-10-17): the elevation of a cell is the eligible-area-weighted mean of the aligned DEM, so it is NaN when no eligible pixel of the cell has a DEM value; it is also NaN in every cell with no eligible area (not a candidate anyway). Cells with enough eligible area and NaN elevation, central scenario: IND 36 for wind and 14 for solar (35.7 and 4.5 km2), BRA 1 and 1 (0.128 and 0.115 km2), PRT 0 (restrictive/permissive: IND 26/38 wind and 12/16 solar, BRA 0/1 and 0/1). How each criterion treated them: slope (E4) acts on the pixel shares of `slope_counts` and a pixel without slope is invalid (`valid_pixels`), so these cells have valid slope, land cover and population but no DEM value in their eligible pixels of the aligned elevation raster (why the two rasters disagree there was not investigated); E1-E3, E5, E6 are shares of the pixel and do not use the elevation; the altitude limit of wind was `elevation <= limit`, false for NaN, so wind dropped them silently and counted them nowhere (`n_cells_excluded_by_elevation` counts `> limit`); solar has no altitude limit and kept them (IND 14 central candidates, BRA 1); the stability table used `elevation > limit`, so it kept the NaN cells of wind that the candidate tables dropped. The rule now: `land_availability.missing_elevation: ineligible` in `config/experiments.yaml` (the only value the model accepts) makes a cell without elevation not a candidate for every technology and scenario; the limit is evaluated only on cells that have an elevation; `candidate_exclusion_reasons` (`scenarios.py`) returns `missing_elevation` or `elevation_max` for a cell with enough eligible area, and the candidate filter, the stability table and the counts use it. `TechSummary.candidate_exclusions` holds the counts of the central scenario (IND wind: 1316 `elevation_max`, 36 `missing_elevation`; IND solar: 14; BRA solar and wind: 1 each; PRT: 0). The eligible area of the cell tables is unchanged. Because the rule is a configuration key, the fingerprint of F3, F5, F6, F7, F7b and F8 changed and the manifest ran F3 and F5 again by itself (no `--rerun`). Result of the run of 2026-10-18 (`docs/phases/core/revalidation_52.md`): PRT identical in content (only the F3 summary JSON gained the counts); IND and BRA: the solar candidate, cell and stability tables, the stability table of wind and the solar potential tables changed by those cells, wind candidates and wind potential did not. The tests are in `tests/unit/test_land_eligibility_pipeline.py` (`missing_elevation` for both technologies, 3100 m only for wind as `elevation_max`).
- **D-F3-019 — F3 on the contiguous territory and the GLO-30 elevation (2026-10-19, COMMAND 55; METHODOLOGY 15.2.0).** No rule of F3 changed. IND has 112,948 cells (were 105,952; 6,996 new, none lost), PRT 3,939 and BRA 286,043; the admin1 units are the clipped units of D-F1-027 (every cell has a unit). The elevation of a cell is the eligible-area-weighted mean of the GLO-30 mean per pixel: no cell has an elevation missing while the slope is present (OQ-060's `missing_elevation` rule stays and now finds only cells without eligible area). The eligible area of the cells that existed changed by less than 0.1% in each country (`geometry_dem_55.md` section 3).
- **D-F3-020 — The protected-area and lake shares no longer depend on the origin of the grid; riparian strips anchored on the absolute lattice (2026-10-20, COMMAND 58).** Diagnosis of the E1 of IND (the protected share of 'any' differed by more than 1e-6 in 19,527 of 95,127 interior cells, more than 20 km from the border, between the round of 2026-10-18 and the current one): the mask is not the cause (clipping the WDPA with the old or the new mask gives the same fractions inside the old territory: 465 of 2,610,287 pixels differ, 464 of them within 5 km of its border), and F3 is deterministic (two runs identical). The cause is the grid: the WDPA vertices of IND lie on a 0.001 degree lattice, finer than the sub-pixel of the rasteriser, so a diagonal edge passes exactly through sub-pixel centres and the rasteriser's tie is decided by the floating-point noise of the grid origin, which changed when the mask grew. Fix (`land_eligibility/fractions.py`): the sampling points of the polygon coverage are shifted by `TIE_BREAK_DEG = 1e-7` degree east and by `TIE_BREAK_SOUTH_RATIO = 0.618...` of that south (an irrational ratio, so no edge of any slope keeps a tie); the river strips, which are lines buffered by a width, are anchored on the absolute row lattice (`_anchored_strips`, `lat_mid` of the absolute lattice) and are not shifted. On the real IND, the shares of the grid of 2026-10-18 and of the current grid are identical pixel by pixel on the overlap (0 pixels differ above 1e-6; before the fix, 4,216), and F3 run twice gives identical arrays. Results: `docs/phases/core/resume_integrity_58.md`. Tests: `tests/unit/test_land_eligibility_fractions.py` (an edge through sub-pixel centres gives the same shares on every float noise of the origin; the same polygons give the same shares on two grids of the same lattice; the anchored strips and the riparian shares do not depend on where the grid begins).
- **D-F3-021 — The caches of the sub-pixel shares are keyed by the code that computes them (2026-10-20, COMMAND 58 follow-up; found in COMMAND 59).** `interim/<ISO3>/land_eligibility/{lakes_fraction,protected_fraction_*,riparian_fraction}.npz` (since COMMAND 91 a folder of `.npy` files of the same name, with the key in `_key.txt`) were valid for the same input file, modification time, grid and categories, and not for the same algorithm: the real runs of 2026-10-20 reused the shares of 2026-10-19, so the tie-break of D-F3-020 reached no real result (found when the second run of the protected share, made outside the pipeline, differed from the saved file in 219,688 pixels). The key now holds the SHA-256 of the normalised source of `land_eligibility/fractions.py` (comments, docstrings and formatting do not change it; `_fractions_code_hash`). After the rerun the shares of IND are identical pixel by pixel between the pipeline file and two new computations. Test: `tests/unit/test_land_eligibility_pipeline.py::test_the_share_caches_are_keyed_by_the_code_that_computes_them`. Consequence for the results: PRT, IND and BRA change by 0.1% or less (`docs/phases/F5/potential_maps_v2.md`, section 5).
- **D-F3-015 — New baseline of land_eligibility and overview for BRA, PRT and IND with the schema of 2026-10-14 (elevation_m and the count of Weibull k below 1).** Rerun on the clean tree of commit b1aefb3 plus the records after it. Wind candidates above the 3000 m of the sensitivity: PRT 0, IND 1,316, BRA 0. Candidates with k below 1 (100, 150, 200 m): PRT 0, 0, 2; IND 220, 211, 205; BRA 20, 21, 22. Time: land_eligibility 12 s, 200 s and 658 s. The sha256 of every registered artifact of the three countries is in `docs/_audit/2026-10_f3_baseline_hashes.json`; the equivalence proof of the move of the shared inputs (COMMAND 37) compares with it.


- **D-F3-023 — Group 3 columns (2026-11-02, COMMAND 83; M-F2b-02, M-F6-09).** Table schema 1.2: `dist_sub_km` (eligible-area mean of the distance to the nearest eligible substation, NaN where the cell has no valid value), `dist_sub_capped_share` (share of the eligible area beyond `distance_cap_km` of a substation) and `pvcz_zone` (PVCZ-2019 thermal zone 1 to 10 of the cell centre, 0 when no land point lies within `geospatial.pvcz_max_distance_km`; the phase raises if the PVCZ file is absent). Built, not run on a real country; F3 of the three countries must run again after F2a and F2b.
- **D-F3-024 — F3 runs by stripes of rows inside the 1,536 MB cap; no result changes (2026-11-04, COMMAND 91; `docs/_audit/f3_memory_90.md`).** F3 of BRA held 2.3 GB between calls and peaked at 3.3 to 3.6 GB because every input and every exclusion of the grid was a whole array. `land_eligibility/windows.py` reads each input by a window of rows (`RasterRows`, `ClassCountRows`, `NpyRows`), computes the six exclusions of a window with the same `eligible_fraction` and sums the cells with the same `aggregate_to_cells` (a cell takes its pixels from one stripe), and writes `eligible_fraction_*.tif` window by window; the slope bins are reduced once to the E4 share of each maximum and to their validity (`prepare_slope_shares`). The share caches are `.npy` folders (`interim/<ISO3>/land_eligibility/<name>/`, key in `_key.txt`; an `.npz` of the same key is converted, not rebuilt) read through memory maps opened per window; the riparian grid is built one discharge at a time; the clipped vectors are read only when their shares are built. The distance transform of the riparian strips is taken in blocks of 8,000 sub-pixel columns with a margin of the largest setback (`fractions.RIVER_BLOCK_SUBCOLUMNS`), which leaves `dist <= t` unchanged; because `fractions.py` changed, the share caches of every country are rebuilt once. The stripe height is `stripe_pixels` of `build_eligibility`, else `GEOFREA_F3_STRIPE_PIXELS`, else 1,000,000 pixels; it sets the memory and nothing else. The whole-grid functions (`prepare_shared_layers`, `technology_layers`) stay, for F7b (OQ-068) and as the oracle of the tests. The V-03 pixel total is now summed by stripes (the check has a 1e-6 tolerance). Proof: `tests/unit/test_land_eligibility_stripes.py` (the stripe engine against the whole-grid functions, bit for bit, for stripes of 1, 5 and 7 cell rows, the last two not dividing the 12 rows of cells, and for the whole grid in one stripe) and `test_land_eligibility_fractions.py` (blocks against the whole strip, at 0 and 45 degrees); BRA, 27 artifacts (the admin1 units, per technology the stability and coarse-cell tables, the cells and candidates tables of three scenarios, the dominant-exclusion and eligible-area rasters, and the eligible-fraction raster of each scenario), tolerance 0 against the output of the round of 2026-11-03: identical with the caches converted and with the caches rebuilt. Peak resident memory of F3 on BRA: 3,631 MB before (profile; 3,337 MB in the round), 1,260 MB with the caches current and 1,218 MB with them rebuilt; wall time 1,215 s before, 606 s with the caches current.

## Known issues





- E1-E5 are shares (E5 from 10 m class counts for the three countries, E4 from 30 m slope bins, D-F3-005, D-F2a-015, D-F2a-016) and are combined as independent, which is conservative (D-F3-003).


- Open and affecting the results: L-057 (the width of a reach is a global bankfull estimate), L-058 (the union with the water is the corridor net of the water), L-059 to L-062 (settlements, slope bins, minimum area, sub-pixel noise) and OQ-070 (a second-hand number behind a sensitivity). OQ-046, OQ-047, OQ-049 and OQ-058 are resolved (D-F3-025); OQ-048 is resolved.


- The IND climate_forcing, hazard_context and climate_maps entries that the grid_alignment rerun had marked `stale_upstream` (D-F3-009) were revalidated without recomputation once F4 required only the `reference_grid` (core.md D-core-024, D-F3-010); the IND manifest has no stale entry.


- The V-07 table is built; the scale-check analysis is part of F7.





## History





- 2026-10-08: clean rerun of the three countries with the three scenarios and the 10 m IND land cover (D-F3-009).


- 2026-10-08: scenarios and IND land-cover decisions recorded (D-F3-007, D-F3-008); METHODOLOGY 7.0.0.


- 2026-10-07: engine built and run for PRT, IND and BRA with the central parameters (D-F3-002 to D-F3-004); METHODOLOGY 5.0.0.


- 2026-10-08: F3 runs end to end on the synthetic country (D-F3-011); MS-5 gate met item by item (see `docs/PROGRESS.json`).


- 2026-10-09: `admin1_id` added to the cell and candidate tables and `admin1_units.parquet` written (D-F3-012, METHODOLOGY 7.2.0; table schema 1.1). The tables of BRA, PRT and IND on disk predate the column: F3 must be rerun for them before F7 reads them.

- 2026-10-09: `pipeline.py` exposes `prepare_shared_layers` and `technology_layers` (the aligned layers, sub-pixel shares and per-technology `EligibilityLayers`), so that F7b evaluates the same pure engine at the pixels of existing plants (M-F3-05, M-F7b-01); `build_eligibility` uses them and its outputs are unchanged.

- 2026-10-12: F1b, F2a, F2b and F3 rerun for PRT, IND and BRA after the content-addressed cache keys (OQ-026; every aligned layer recomputed once). Cell and candidate tables carry `admin1_id`, complete. Against the tables of the 2026-10-08 run: row counts, every column except `admin1_id`, the eligible areas of the three scenarios and the six rasters of each country are identical (22 files per country compared).

- 2026-10-18 (D-F3-018, COMMAND 51): a cell without elevation is not a candidate (reason `missing_elevation`); the altitude limit is evaluated only on cells with an elevation; OQ-060 closed.
- 2026-10-19: F3 run again on the contiguous territory and the GLO-30 elevation (D-F3-019).
- 2026-10-20 (D-F3-020, COMMAND 58): E1 of IND no longer depends on the grid origin.
- 2026-10-20 (D-F3-021, COMMAND 59): the share caches follow the code of the algorithm.

- **D-F3-022 — Eligibility figures in the MapFigure standard (2026-10-26, COMMAND 68).** `land_eligibility/figures.py` draws one sheet per technology (classes E1-E6 plus eligible, the "dominant" exclusion defined by `DOMINANT_RULE`, the denominator declared) and a stacked-bar chart of the contribution of each exclusion; the maps per rule are diagnostics under `overview/figures/layers/`. The F3 tables did not change.
- 2026-11-04 (D-F3-024, COMMAND 91): F3 by stripes of rows, peak of BRA from 3.6 GB to 1.2 GB, results unchanged.
- 2026-11-05 (D-F3-025, COMMAND 97): the land rules of Group 6 replace the parameters of D-F3-002 and D-F3-007(c); D-F3-004 and D-F3-006 (the results of the first central parameters: PRT 23.9 / 31.7 %, IND 4.9 / 17.2 %, BRA 18.0 / 25.8 % solar / wind) and D-F3-014 and D-F3-016 (the altitude limit as a sensitivity, then 3,000 m in every scenario) are superseded: the limit is 2,000 / 3,000 m / none per scenario. OQ-046, OQ-047, OQ-049 and OQ-058 are resolved.
