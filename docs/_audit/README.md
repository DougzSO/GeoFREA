# docs/_audit: index by theme

Audit, measurement and phase reports. Each file is a dated record of what was true when it was written; it is not kept up to date. Files are cited by path from code comments, scripts and active docs, so they are not renamed. Files that nothing cited were moved on 2026-11-13 to `docs/_archive/2026-11/` (see its README). The audit of the documents of 2026-11-13 is in `2026-11_docs_audit/` (reports 01 to 08 and their tables).

## General audits and repository state

| File | What it is |
|---|---|
| `consistency-2026-09-14.md` | consistency check of the records of 2026-09-14 |
| `2026-09_records.md` | sizing of the migration of `DECISIONS.md`, `CONVENTIONS.md` and `PROGRESS.json` |
| `2026-10_pre_research_audit.md` | pre-research audit of the repository and of `GeoFREA_data` |
| `2026-10_pre_research_audit_scripts/` | the two scripts of that audit (plausibility on real data, the ZZZ check by hand) |
| `2026-10_systematic_review.md` | review of code, artifacts and documents against METHODOLOGY 6.0.0 |
| `2026-10_pipeline_state.md` | what exists, what runs and what is missing in `main.py` |
| `2026-10_general_audit_71.md` | general audit before Group 3 (COMMAND 71) |
| `generality_audit.md` | how general the code is across countries (COMMAND 125) |
| `ci_red_audit.md` | why CI was red (COMMAND 105) |

## Phase 1 to 2b: facts of the code and data (2026-09)

| File | What it is |
|---|---|
| `2026-09_F1-F2b.md` | facts of the code of F1, F2a and F2b |
| `2026-09_parameters.md` | inventory of the parameters of F1, F2a and F2b |
| `2026-09_embedded_values.md` | sweep of values embedded in code (ADJ-6) |
| `2026-09_layer_quantities.md` | quantities, units and ranges of the layers (ADJ-1) |
| `2026-09_resource_products.md` | the GWA and GSA products, network check and local metadata |
| `2026-09_data_coverage.md` | coverage of the data, 2026-09-22 |
| `2026-09_data_state_pre_G.md` | state of the data before stage G (ADJ-4) |
| `2026-09_geofrea_data_inventory.md` | inventory of `GeoFREA_data` |
| `2026-09_legacy_F3-F8.md` | facts about the legacy logic of F3 to F8 |
| `2026-10_f2b_sanity.md` | F2b layers against their sanity ranges (H-6, V-04) |
| `coverage_alignment_54.md` | coverage of the outline and alignment of elevation and slope (COMMAND 54) |
| `geometry_dem_55.md` | contiguous country mask and one DEM; F1 to F5 run again (COMMAND 55) |

## F4: climate forcing

| File | What it is |
|---|---|
| `2026-09_craei_climate_reuse.md` | decision on reusing the CRAEI ISIMIP3b climate (ADJ-6) |
| `2026-09_cds_stability_diagnosis.md` | CDS instability (F4-3) |
| `2026-09_arco_era5_validation.md` | ARCO-ERA5 validation: equivalence, cost, hash prototype (F4-4) |
| `2026-10_gcm_selection_j1.md` | GCM selection, evidence for OQ-009 (J-1) |
| `2026-10_gcm_selection_spread.md` | spread of change factors, criterion 3 of M-F4-02 |
| `2026-10_data_diagnostics.md` | MIROC6 wind (B-1), wind at altitude and with k < 1 |

## F3 and its groups

| File | What it is |
|---|---|
| `2026-10_f3_parameter_research.md` | exclusion parameters, sources and four findings (H-3) |
| `2026-10_f3_baseline_hashes.json` | content hashes of F3 before the changes of October |
| `audit_groups1-2.md` | Groups 1 and 2: F3, F5 and F6 against the .tex |
| `groups1-2_implementation_report.md` | implementation report of Groups 1 and 2 |
| `group3_audit_83.md` | Group 3 audit (COMMAND 83) |
| `group3_costs_85.md` | pending costs of Group 3 (OQ-001, OQ-065, OQ-066) |
| `group6_audit_97.md` | Group 6 audit: land eligibility in F3 (COMMAND 97) |
| `group6_decomposition/` | the change of the eligible area of BRA, IND and PRT, as `.md` and `.csv` |
| `ind_population_effect_89.md` | effect of the exact population sum on F3 of IND (COMMANDS 89, 91) |
| `slope_canopy_99.md` | slope against canopy (COMMAND 99) |
| `slope_dem_test_100.md` | slope test with GLO-30, FABDEM and a 90 m support (COMMAND 100) |
| `slope_dem_test_100_e4.csv`, `slope_dem_test_100_eligible.csv` | tables of that test |

## F5 to F8: design and reports

| File | What it is |
|---|---|
| `2026-10_F5_design.md` | F5 inputs and design for the verdicts |
| `2026-10_F6_design.md` | F6 CRAEI check, inputs and design |
| `2026-10_F7_design.md` | F7 and F7b inventory and design |
| `2026-10_F8_design.md` | F8 inventory and design |
| `run_report_real.md` | F5 on real data, PRT, IND and BRA in one round |
| `fix_round_46.md` | fix round after the first real run (COMMAND 46) |
| `oq053_report.md` | validity limits of the Weibull layers (OQ-053, COMMAND 48) |
| `audit_potential_65.md`, `audit_potential_65/` | numerical audit of the technical potential and its JSON per country (COMMAND 65) |
| `potential_maps_absolute.md` | maps of the potential in capacity and energy (D-F5-029, D-F5-030) |
| `potential_maps_v2.md` | maps of the potential, version 2 (D-F5-032) |
| `wind_cf_pixel_74.md` | wind capacity factor from the 0.01 degree pixels (COMMAND 74) |
| `members_per_cell_95.md` | members per cell and technology, and the wind members BRA lacks |
| `pv_degradation_zones_83.md` | PV degradation by thermal zone |
| `pv_zone_shares_84.md` | PV potential and eligible area by thermal zone |
| `ren_source_audit.md` | audit of the REN source |

## Grid, roads, costs and distances

| File | What it is |
|---|---|
| `2026-10_distance_connection_cost_evidence.md` | literature on distance to grid and roads and the connection-cost model |
| `2026-10_plants_vs_osm_grid.md` | existing plants against the OSM grid layer (L-025 context) |
| `bra_line_138_86.md` | cost per km of a 138 kV line in BRA (OQ-001) |
| `dist_scale_prototype.md` | distance-to-substation layer: consumers and a prototype of the scale |
| `dist_sub_scale_audit.md` | error of the isotropic scale of the distance to the substation (COMMAND 111) |
| `poi_counts_84.md` | substations of the POI layer by country (OQ-067) |
| `road_distance_86.md` | distance to the road of the eligible area |
| `vth_evidence_85.md` | evidence for the voltage thresholds of the POI (OQ-065) |

## Performance, memory and proofs of equivalence

| File | What it is |
|---|---|
| `profile_76.md`, `profile_76_tables/` | where time and memory are (COMMAND 76); the tables come from `scripts/profiling/parse_logs.py`, and `bench/*/bench_log.jsonl` are the benchmark logs (the JSON of each measure is in the archive) |
| `performance_75.md` | what the pipeline costs and the proof that results did not change |
| `optimizations_77.md` | optimizations item by item, with proof and gain |
| `optimization_gain_82.md` | before and after COMMANDS 75 and 77, from logs and manifests |
| `proofs_75_77/` | JSON proofs of equivalence of COMMANDS 75 to 80 (produced by `scripts/proofs/`) |
| `memory_budget_88.md` | memory budget of F2a and F2b |
| `population_memory_87.md` | memory of the population warp of BRA |
| `f3_memory_90.md` | memory of F3 on BRA |
| `f3_peak_118.md` | why the F3 peak of BRA differed between two rounds |
| `checkpoint_98.md` | resume after an interruption (inventory) |
| `cache_keys_123.md` | stored cache keys against recomputed keys (OQ-081) |
| `config_scope_127.md` | configuration scope of F2a and F3 and the rebaseline by proof |
| `fingerprint_algo_120.md` | fingerprint algorithm independent of the Python version |
| `manifest_config_fix.md` | manifest resume and configuration changes |
| `resume_integrity_58.md` | resume integrity, GWA coverage and E1 of IND |
| `revalidation_52.md` | revalidation of the real manifests and OQ-060 |

## Rounds and what a round changed

| File | What it is |
|---|---|
| `round_133.md` | the clean round after the merge of `window-132` (2026-11-12) |
| `compare_9c2dc3c8_vs_1d34ab23.md` | content comparison of two rounds (COMMAND 118) |
| `window_list_131.md` | changes held back because they change the fingerprint of a phase that ran |
