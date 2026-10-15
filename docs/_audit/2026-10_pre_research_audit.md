# Pre-research audit of GeoFREA (repository and GeoFREA_data)

Date: 2026-10-14. Scope: the repository at commit `f8e140b` plus the data directory `D:\Douglas\DOUTORADO\GeoFREA_data`, read-only, before real values enter. Nothing but this report and the two audit scripts in `docs/_audit/2026-10_pre_research_audit_scripts/` was added; no file of the pipeline, no configuration and no datum was changed or deleted. METHODOLOGY 13.0.1, 1,283 tests, CI green on both workflows at the audited head.

Method in one paragraph. The 134 identifiers of METHODOLOGY were extracted by script and every `file:line` that cites each one in `src/`, `tests/`, `scripts/` and the phase records was collected (section 1). Numbers in the thesis texts, METHODOLOGY, configuration and phase records were compared by script (section 2). Numeric literals of `src/` were listed by AST and read one by one (section 3). Dead code was searched with `vulture`, test strength with an AST scan, and test coverage was measured by running the unit tests and the synthetic tests separately under `coverage` (section 4). The DAG was built from the phase specifications and compared with the manifests and with the imports (section 5). Disk usage was measured per folder and every file above 10 MB was matched to the code that reads it (section 6). A full ZZZ run from the empty directory was made, and one value per phase was recomputed by an independent script that imports nothing from `geofrea` (section 7). The real F1 to F4 outputs were summarised per country by a second script (section 8).

## 0. Summary

1. **The method is implemented and, where it can be checked, correct.** Of 122 items with a status, 105 are implemented, 10 partial, 3 absent (two conditional on OQ-007, the explorer E1) and 1 contradicts (M-F2a-06, unchanged). On 08/10 the counts were 36 implemented, 19 partial, 3 contradicts, 35 absent for 93 items; 48 items changed status: 46 towards implemented and 2 (M-F1-04, M-F4-05) read more strictly as partial because the 2071-2100 hazard data are not acquired; no code regressed (section 1.2).
2. **The hand validation passes: 55 of 55 checks** (40 for wind, 15 for solar): eligible area, `delta_rsds`, `dT`, `delta_wind`, solar and wind capacity factor, LCOE of a cell and its draw statistics, MR of every ranked cell, SR, the top-k sets, `C_k`, `V_k`, `O`, `D`, `D_clim`, `D_tec`, `R_loss`, `G` and a PRIM box agree with independent implementations to between 1e-16 and 1e-9. The only residual differences are the single-precision rounding of the change factors (up to 7e-5 K, 1e-7 relative). The limit of this evidence is stated in 7.3: the ZZZ world never reorders its cells, so `V_k`, `D`, `D_clim`, `D_tec` and the real PRIM outcome are all zero there.
3. **Nothing in F5 to F8 has run on a real country.** BRA, PRT and IND stop at F4 (and F3). The first real F5 run will refuse for known reasons (power curves, the IEC class rule and the decision parameters are null: OQ-004, OQ-005, OQ-008, OQ-010, OQ-021). Time and disk of F5 to F8 for BRA are not measured anywhere; section 5.4 gives an estimate and a way to measure it before the research values arrive.
4. **Five results-affecting findings in the real F1 to F4 data** (section 8 and 9): the validity mask removes 1.4% of the BRA cell-members and touches 24% of BRA cells, almost all of it MIROC6 (71% of the masked cell-members; up to 78 times the reference wind), with a range 0.5 to 1.5 that has no source; 1,041 Indian wind candidate cells lie where the air density is below 0.8 kg/m3 (about 4,000 m and higher); the Weibull shape `k` is below 1 in 0.35% of the Indian candidate cells; the heat indicator of BRA doubles the median days above 35 C between the reference and 2041-2070 (30 to 110 days); and the cells with a masked member become `climate_data_invalid` in F7, so a quarter of Brazil is not ranked.
5. **The registers have drifted.** Eleven statements in phase records, PROGRESS.json and one configuration comment describe a state that code and tests have overtaken (section 2.2). METHODOLOGY M-F7-04 says "futures" where the code (D-F7-010) and its record say "draws s >= 1".
6. **Data directory: 134 GB; about 60 GB of the 134 are read by no code path of the current pipeline or are duplicates** (section 6): 38.7 GB of ERA5 hourly files (the pipeline reads the 2 MB annual maxima), 8.4 GB of CMIP6 files of nine models that were not selected, 9.4 GB of ISIMIP3b files of a variable or of models not used, 1.4 GB of the retired legacy baseline, about 4 GB of zip and extracted pairs and duplicate clip caches. The DEM tiles (47 GB) are inputs only of a slope cache that exists, and are kept. The regeneration cost of each is in the table.
7. **Dead code is small**: 15 functions are used only by tests (three are deliberate test oracles that live in `src/`), 4 are unused anywhere, one schema (`BiomassParams`) belongs to a retired technology. Five import edges violate the phase DAG (section 4.4).

## 1. Conformance of METHODOLOGY items to the code

Status definitions as on 08/10: *implemented* = code and at least one piece of evidence match the text; *partial*; *absent*; *contradicts*. `T-IDs` are `implemented (ZZZ only)`: a script writes them on the synthetic country. `Tests citing the ID` is the number of test lines that name the identifier; zero does not mean untested (many items are tested through the phase, see the phase records). The 12 roadmap lines MS-0 to MS-11 are not code items and are listed in 1.3.

The hypotheses H1 to H5 are not identifiers in METHODOLOGY; they are the blocks of M-F7-07 and the thesis texts:

| Hypothesis | Status | Evidence (file:line) | Note |
|---|---|---|---|
| H1 | implemented | `robustness_analysis/h1_rank_robustness.py:214` (`verdict_of`), `:224` (`evaluate_variant`); `config/experiments.yaml` `hypothesis_rules.H1` | alpha 0.60, beta 0.20, m = k; `C_k`, `V_k` recomputed by hand (7.2) |
| H2 | implemented | `h2_aggregation.py:71` (`verdict_of`) | gamma 0.30; `O`, `O_ref` recomputed by hand |
| H3 | implemented | `h3_robust_vs_nominal.py:98` (`verdict_of`) | delta 0.20; `D` recomputed by hand (zero on ZZZ) |
| H4 | implemented | `h4_axis_dominance.py:278` (`technology_verdict`); support phase `cross_country.py` | 0.40 / 0.60; `D_clim`, `D_tec` by hand (zero on ZZZ) |
| H5 | implemented | `h5_climate_pressure.py` (`evaluate_variant`, `build_exposure`) | lambda 0.20; `E_0`, `G`, `Delta E`, `R_loss` by hand; H5b over the channels that have a threshold (13.0.1) |

### 1.1 Table

| ID | Line | Status | Evidence (file:line) | Tests citing the ID | Note and change since 08/10 |
|---|---|---|---|---|---|
| S-01 | 82 | n/a (scope) | - | 0 | Scope statement; BRA, PRT, IND have F1 to F4 outputs, F5 onward `not_run`. |
| S-02 | 83 | implemented | `core/schemas.py:334`; `data_quality_audit/audit.py:75` | 2 |  |
| S-03 | 84 | n/a (scope) | - | 0 | Three SSPs used throughout. |
| S-04 | 85 | implemented | `data_acquisition/fetchers/cmip6.py:10`; `data_acquisition/fetchers/cmip6.py:34` | 0 |  |
| S-05 | 86 | implemented | `climate_forcing/hazards.py:36`; `data_acquisition/fetchers/cmip6.py:46` | 1 |  |
| S-06 | 87 | implemented | `core/constants.py:27`; `core/scale.py:3` | 1 |  |
| S-07 | 88 | implemented | `core/constants.py:63`; `core/schemas.py:140` | 2 |  |
| S-08 | 89 | implemented | `core/orchestrator.py:128`; `main.py:343` | 0 |  |
| S-09 | 90 | n/a (scope) | - | 0 | Repository boundary. |
| M-F1-01 | 175 | implemented | - | 0 | Registry with provenance; `src` does not cite the ID, evidence `data_acquisition/schemas.py`. |
| M-F1-02 | 176 | implemented | - | 0 | Active layer set; the phase record's old `fail` row (biomass-only inputs still in `CountryCriteriaParams`) is out of scope of the item. |
| M-F1-03 | 177 | implemented | `data_acquisition/adapter.py:135`; `data_acquisition/phase.py:162` | 8 |  |
| M-F1-04 | 178 | partial | `data_acquisition/cmip6_registry.py:1`; `data_acquisition/cmip6_registry.py:8` | 0 | Resource channel acquired for the 6 GCMs; the daily hazard data exist only for the 2041-2070 window (S-05, L-021). **Changed: implemented -> partial.** |
| M-F1-05 | 179 | implemented | `climate_forcing/hazards.py:159`; `data_acquisition/era5_registry.py:1` | 0 |  |
| M-F1-06 | 180 | implemented | `data_acquisition/fetchers/gem_trackers.py:1`; `external_validation/inventory.py:1` | 1 |  |
| M-F1-07 | 181 | implemented | `data_acquisition/schemas.py:221`; `data_acquisition/fetchers/gadm.py:76` | 2 |  |
| M-F1b-01 | 185 | implemented | `data_quality_audit/audit.py:16`; `data_quality_audit/audit.py:77` | 1 |  |
| M-F1b-02 | 186 | partial | - | 0 | Findings never stop a run, but `siting_layers`, `land_eligibility` and `climate_forcing` require `audit_report`, so an audit that fails to run does stop them (unchanged since 08/10). |
| M-F2a-01 | 190 | implemented | `core/constants.py:29`; `core/schemas.py:432` | 0 |  |
| M-F2a-02 | 191 | implemented | `grid_alignment/raster_alignment.py:211`; `land_eligibility/cells.py:18` | 1 |  |
| M-F2a-03 | 192 | implemented | `core/schemas.py:449`; `grid_alignment/adapter.py:125` | 2 |  |
| M-F2a-04 | 193 | implemented | `grid_alignment/alignment.py:278`; `grid_alignment/alignment.py:421` | 1 |  |
| M-F2a-05 | 194 | implemented | - | 0 | Population summed (D-F2a-014); no `file:line` cites the ID, evidence is `grid_alignment/alignment.py` (population branch). |
| M-F2a-06 | 195 | contradicts | `grid_alignment/raster_alignment.py:500`; `grid_alignment/raster_alignment.py:554` | 1 | Text: "anything else is an error"; code has a second counting mode (by sample centre) for IND tiles (D-F2a-015 addendum). Unchanged since 08/10. |
| M-F2a-07 | 196 | implemented | - | 0 | 30 m slope bins from Copernicus GLO-30; no ID cited in code, evidence `grid_alignment/raster_alignment.py` (slope bins). |
| M-F2b-01 | 200 | implemented | `land_eligibility/eligibility.py:1`; `land_eligibility/parameters.py:1` | 0 | Text was rewritten in 6.0.0 to shares; code and text now agree (was `contradicts` on 08/10). **Changed: contradicts -> implemented.** |
| M-F2b-02 | 208 | implemented | `siting_layers/physical_layers.py:1`; `siting_layers/physical_layers.py:101` | 1 |  |
| M-F2b-03 | 209 | implemented | `siting_layers/physical_layers.py:1`; `siting_layers/physical_layers.py:103` | 0 |  |
| M-F2b-04 | 210 | implemented | `siting_layers/physical_layers.py:1`; `siting_layers/physical_layers.py:4` | 0 |  |
| M-F2b-05 | 211 | implemented | `land_eligibility/pipeline.py:93`; `land_eligibility/pipeline.py:205` | 1 | An absent protected-area, lake or river layer raises (`land_eligibility/pipeline.py:93,212`); no `assumed_free` path exists (was `partial`). **Changed: partial -> implemented.** |
| M-F2b-06 | 212 | partial | - | 0 | Ranges feed the three named scenarios (U-06); the full-factorial range report is not built (same gap as M-F3-02). |
| M-F3-01 | 216 | implemented | `land_eligibility/cells.py:1`; `land_eligibility/cells.py:171` | 1 |  |
| M-F3-02 | 217 | partial | `land_eligibility/scenarios.py:1` | 0 | Three scenarios computed and written; the full factorial of ranged land parameters is not built (F3 record D-F3-007). |
| M-F3-03 | 218 | implemented | `core/constants.py:27`; `land_eligibility/admin1.py:1` | 1 |  |
| M-F3-04 | 226 | implemented | `land_eligibility/cells.py:272`; `land_eligibility/parameters.py:1` | 0 |  |
| M-F3-05 | 227 | partial | `land_eligibility/pipeline.py:345` | 0 | Outputs exist with schema versions now; rasters are tiled GeoTIFF, not Cloud Optimized (A-07). |
| M-F3-06 | 228 | implemented | `core/scale.py:1`; `land_eligibility/pipeline.py:1` | 2 |  |
| M-F4-01 | 232 | implemented | `climate_forcing/members.py:1`; `data_acquisition/isimip3b_registry.py:9` | 1 |  |
| M-F4-02 | 233 | implemented | `data_acquisition/fetchers/cmip6.py:11` | 0 | Protocol run once (`scripts/gcm_selection_spread.py`); result in `experiments.yaml` `gcm_ensemble`. |
| M-F4-03 | 239 | implemented | `climate_forcing/change_factors.py:1`; `climate_forcing/change_factors.py:8` | 2 |  |
| M-F4-04 | 244 | implemented | `climate_forcing/change_factors.py:1`; `climate_forcing/change_factors.py:15` | 2 |  |
| M-F4-05 | 245 | partial | `climate_forcing/hazards.py:1`; `climate_forcing/hazards.py:71` | 1 | Hazard indicators for the 9 members with a hazard channel, window 2041-2070 only; loss functions wait for OQ-007. **Changed: implemented -> partial.** |
| M-F4-06 | 249 | implemented | `climate_forcing/forcing.py:1`; `climate_forcing/hazards.py:1` | 1 |  |
| M-F4-07 | 250 | implemented | `climate_forcing/table_schemas.py:23`; `results_synthesis/climate_change.py:6` | 3 | Works as specified. Plausibility flag: the mask removes 1.4% of BRA cell-members and touches 24% of BRA cells (section 8). |
| M-F5-01 | 254 | implemented | `core/production.py:74`; `core/schemas.py:287` | 8 | **Changed: absent -> implemented.** |
| M-F5-02 | 255 | implemented | `core/constants.py:60`; `core/schemas.py:289` | 3 | **Changed: absent -> implemented.** |
| M-F5-03 | 258 | implemented | `core/config_schemas.py:20`; `core/constants.py:55` | 6 | **Changed: absent -> implemented.** |
| M-F5-04 | 264 | absent | - | 3 | Conditional on OQ-007 (a C2 loss function); correctly inactive. No code, no stub. |
| M-F5-05 | 265 | implemented | `core/constants.py:58`; `technical_potential/capacity.py:1` | 2 | **Changed: absent -> implemented.** |
| M-F5-06 | 266 | implemented | `results_synthesis/potential_and_cost.py:20`; `technical_potential/aggregates.py:1` | 0 | Tables and aggregates in two series; absent cell-members declared. **Changed: absent -> implemented.** |
| M-F6-01 | 270 | implemented | `core/schemas.py:206`; `core/schemas.py:290` | 6 | **Changed: absent -> implemented.** |
| M-F6-02 | 277 | implemented | `core/config_schemas.py:84`; `lcoe_modeling/design.py:1` | 1 | **Changed: absent -> implemented.** |
| M-F6-03 | 278 | absent | - | 0 | Conditional on OQ-007 (a C3 loss function); correctly inactive. |
| M-F6-04 | 279 | implemented | `lcoe_modeling/pipeline.py:6`; `lcoe_modeling/pipeline.py:110` | 0 | **Changed: absent -> implemented.** |
| M-F6-05 | 280 | implemented | `lcoe_modeling/kernel.py:1`; `lcoe_modeling/kernel.py:3` | 2 | **Changed: absent -> implemented.** |
| M-F6-06 | 281 | implemented | `lcoe_modeling/pipeline.py:7`; `lcoe_modeling/pipeline.py:8` | 1 | **Changed: absent -> implemented.** |
| M-F7-01 | 287 | implemented | `core/schemas.py:294`; `core/schemas.py:321` | 4 | **Changed: absent -> implemented.** |
| M-F7-02 | 288 | implemented | `robustness_analysis/decision.py:69`; `robustness_analysis/evaluator.py:11` | 2 | **Changed: absent -> implemented.** |
| M-F7-03 | 289 | implemented | `robustness_analysis/evaluator.py:37`; `robustness_analysis/evaluator.py:255` | 2 | **Changed: absent -> implemented.** |
| M-F7-04 | 290 | implemented | `core/schemas.py:295`; `core/schemas.py:322` | 2 | SR is the share of the draws s >= 1 (D-F7-010). The text says "share of futures" and defines f0 = (m0, s0) as a future: the wording should say "draws s >= 1" (hand check, section 7). **Changed: absent -> implemented.** |
| M-F7-05 | 291 | implemented | `core/schemas.py:296`; `core/schemas.py:323` | 2 | **Changed: absent -> implemented.** |
| M-F7-06 | 292 | implemented | `robustness_analysis/assemble.py:1`; `robustness_analysis/assemble.py:64` | 3 | Record row still says `partial (Jaccard comparison and H4 follow)`; both are built. **Changed: absent -> implemented.** |
| M-F7-07 | 293 | implemented | `core/config_schemas.py:98`; `core/config_schemas.py:108` | 9 | H1 to H5 built with the pre-registered rules; recomputed by hand on ZZZ (section 7). ZZZ is degenerate for H1, H3 and H4 (rankings never change). **Changed: absent -> implemented.** |
| M-F7-08 | 327 | implemented | `core/config_schemas.py:234`; `core/config_schemas.py:251` | 6 | PRIM per the pre-registered rule; no real outcome on ZZZ (`V_f` = 0), the box of the ZZZ run comes from a test-only rule (D-F7-057, D-F7-060). **Changed: absent -> implemented.** |
| M-F7-09 | 328 | implemented | `robustness_analysis/decision.py:173`; `robustness_analysis/hypotheses.py:772` | 0 | **Changed: absent -> implemented.** |
| M-F7-10 | 329 | implemented | `robustness_analysis/evaluator.py:3`; `robustness_analysis/evaluator.py:255` | 0 | **Changed: absent -> implemented.** |
| M-F7-11 | 330 | implemented | `robustness_analysis/assemble.py:1`; `robustness_analysis/assemble.py:121` | 1 | **Changed: absent -> implemented.** |
| M-F7b-01 | 334 | implemented | `core/config_schemas.py:337`; `external_validation/exclusion.py:1` | 1 | **Changed: absent -> implemented.** |
| M-F7b-02 | 335 | implemented | `external_validation/enrichment.py:1`; `external_validation/enrichment.py:44` | 0 | **Changed: absent -> implemented.** |
| M-F7b-03 | 336 | implemented | `core/config_schemas.py:337`; `external_validation/pipeline.py:8` | 0 | **Changed: absent -> implemented.** |
| M-F7b-04 | 337 | implemented | `external_validation/pipeline.py:1`; `external_validation/pipeline.py:11` | 2 | **Changed: absent -> implemented.** |
| M-F8-01 | 341 | implemented | `core/artifact_reader.py:1`; `results_synthesis/climate_change.py:3` | 3 | **Changed: absent -> implemented.** |
| M-F8-02 | 342 | implemented | `core/config_schemas.py:328`; `results_synthesis/maps.py:1` | 2 | **Changed: absent -> implemented.** |
| M-F8-03 | 343 | implemented | `core/config_schemas.py:285`; `results_synthesis/synthesis.py:2` | 1 | Profiles, summary, labels; one country on ZZZ gives `not assessable`. |
| M-E1-01 | 347 | absent | - | 0 | E1 explorer not started (PROGRESS.json). |
| U-01 | 353 | implemented | - | 0 | Full factorial members x samples in the F6/F7 passes; both axis identifiers kept (futures table has `member` and `sample`). **Changed: absent -> implemented.** |
| U-02 | 354 | implemented | `core/config_schemas.py:84`; `lcoe_modeling/sampling.py:1` | 1 | **Changed: absent -> implemented.** |
| U-03 | 355 | implemented | `core/config_schemas.py:1`; `core/config_schemas.py:76` | 0 | Loader exists (`core/config_loader.py:88`); the 08/10 and the `core.md` rows ("no loader") are stale. **Changed: partial -> implemented.** |
| U-04 | 356 | implemented | `core/config_schemas.py:84`; `core/config_schemas.py:91` | 2 | `sample_size_convergence` phase; not run on a real country (needs OQ-008/OQ-021). **Changed: absent -> implemented.** |
| U-05 | 357 | implemented | `core/config_schemas.py:76`; `core/constants.py:54` | 3 | **Changed: partial -> implemented.** |
| U-06 | 381 | implemented | `land_eligibility/pipeline.py:97`; `land_eligibility/scenarios.py:1` | 1 | Three scenarios declared and run for the three countries; the old `contradicts` (strict/lenient) is gone. **Changed: contradicts -> implemented.** |
| U-07 | 382 | implemented | `core/production.py:13`; `core/production.py:97` | 1 | `tier` and `synthetic` enforced by the schemas; production refuses test values (`core/production.py`). **Changed: partial -> implemented.** |
| U-08 | 386 | partial | `results_synthesis/robustness_tables.py:537`; `robustness_analysis/assemble.py:274` | 0 | Land interval reported by T-R2, T-R12 and H5 land variants; F7 ranks use the central scenario only (V1), so "every main result with its range" holds for potential and LCOE, not for the rankings. |
| A-01 | 392 | implemented | `core/orchestrator.py:3`; `main.py:406` | 0 |  |
| A-02 | 393 | implemented | `core/artifact_json.py:4`; `core/orchestrator.py:3` | 5 |  |
| A-03 | 394 | implemented | `core/orchestrator.py:3`; `core/schemas.py:375` | 0 | Run targeting by `settings.yaml`; `run.countries` empty means every thesis country. **Changed: partial -> implemented.** |
| A-04 | 395 | implemented | `core/config_loader.py:79`; `core/config_schemas.py:1` | 7 | Loader exists (`config_loader.py:78`); `power_curves` and `iec_class_rule` are null until OQ-005 (a real F5 run refuses). **Changed: partial -> implemented.** |
| A-05 | 396 | implemented | `core/config_loader.py:22`; `data_acquisition/fetchers/cmip6.py:59` | 6 |  |
| A-06 | 397 | implemented | `core/paths.py:131`; `core/schemas.py:121` | 5 | ZZZ runs F1 to F8 in CI; the `core.md` / PROGRESS wording ("covers F1 and F2a") is stale. **Changed: partial -> implemented.** |
| A-07 | 398 | partial | `climate_forcing/table_schemas.py:1`; `core/artifact_reader.py:110` | 2 | Parquet tables carry `schema_version` (the old gap is closed); rasters are tiled GeoTIFF named COG (`write_cog` uses driver GTiff), no overview pyramids. |
| A-08 | 399 | implemented | `climate_forcing/maps.py:1`; `climate_forcing/pipeline.py:241` | 7 |  |
| A-09 | 409 | implemented | `climate_forcing/change_factors.py:38`; `climate_forcing/external_inputs.py:1` | 14 |  |
| A-10 | 410 | implemented | `core/schemas.py:461`; `core/schemas.py:485` | 3 | Batches under `memory.max_batch_gb` in F6, F7 and the sample-major pass (was `absent`). **Changed: absent -> implemented.** |
| A-11 | 411 | implemented | `climate_forcing/change_factors.py:5`; `climate_forcing/hazards.py:13` | 0 |  |
| A-12 | 412 | implemented | `core/config_schemas.py:84`; `core/orchestrator.py:330` | 3 | Seeds recorded in the manifest (`seeds`), PRIM bootstrap seed derived and recorded; run id is deterministic. **Changed: partial -> implemented.** |
| A-13 | 413 | partial | `technical_potential/__init__.py:3` | 0 | `Implements:` lines in 114 docstrings (103 distinct items) against 1 on 08/10; not complete (24 items have no src citation). |
| V-01 | 419 | implemented | - | 7 | Frozen parity of F1, F2a and E1-E3 on ZZZ in CI (`tests/regression`, 2 tests); the legacy BRA/PRT baseline is retired. |
| V-02 | 420 | implemented | `lcoe_modeling/kernel.py:65`; `lcoe_modeling/kernel.py:82` | 8 | CRF and LCOE closed forms, Weibull CF against quadrature, rescale closed forms (tests use `lcoe_direct`, `rescale_cf_*` as oracles). **Changed: partial -> implemented.** |
| V-03 | 421 | implemented | `land_eligibility/pipeline.py:89`; `land_eligibility/pipeline.py:649` | 13 | Invariants asserted inside the pipelines (`r >= 0`, `MR >= 0`, `0 <= SR <= 1`, s0 column equals F6). **Changed: partial -> implemented.** |
| V-04 | 422 | implemented | `core/constants.py:66`; `data_quality_audit/schemas.py:44` | 4 | F1b reports and F5 validates its inputs against `audit.yaml` (D-F5-019); the old `partial` (F5 half not started) is closed. **Changed: partial -> implemented.** |
| V-05 | 423 | implemented | `lcoe_modeling/convergence.py:1`; `lcoe_modeling/convergence.py:128` | 1 | Convergence protocol built (`lcoe_modeling/convergence.py`); not run on real data. **Changed: absent -> implemented.** |
| V-06 | 424 | implemented | `climate_forcing/external_inputs.py:12`; `data_acquisition/fetchers/gem_trackers.py:1` | 4 |  |
| V-07 | 425 | partial | `core/constants.py:34`; `core/scale.py:1` | 7 | F3 to F8 rerun at 0.1 degree on ZZZ through the `scale` parameter; not run on a real country. |
| V-08 | 426 | implemented | `core/schemas.py:121` | 2 | ZZZ end to end through F8 in CI (103 synthetic tests). **Changed: partial -> implemented.** |
| T-M1 | 450 | implemented (ZZZ only) | `core/config_schemas.py:319`; `core/orchestrator.py:506` | 5 | A script in `results_synthesis` writes it on the synthetic country; the real build needs the real runs. |
| T-M2 | 451 | implemented (ZZZ only) | `results_synthesis/method_tables.py:1`; `results_synthesis/method_tables.py:17` | 2 | A script in `results_synthesis` writes it on the synthetic country; the real build needs the real runs. |
| T-M3 | 452 | implemented (ZZZ only) | `results_synthesis/method_tables.py:1`; `results_synthesis/method_tables.py:17` | 3 | A script in `results_synthesis` writes it on the synthetic country; the real build needs the real runs. |
| T-R1 | 453 | implemented (ZZZ only) | `results_synthesis/maps.py:1`; `results_synthesis/names.py:14` | 8 | A script in `results_synthesis` writes it on the synthetic country; the real build needs the real runs. |
| T-R2 | 454 | implemented (ZZZ only) | `results_synthesis/names.py:14`; `results_synthesis/potential_and_cost.py:1` | 14 | A script in `results_synthesis` writes it on the synthetic country; the real build needs the real runs. |
| T-R3 | 455 | implemented (ZZZ only) | `core/config_schemas.py:297`; `results_synthesis/climate_change.py:1` | 5 | A script in `results_synthesis` writes it on the synthetic country; the real build needs the real runs. |
| T-R4 | 456 | implemented (ZZZ only) | `results_synthesis/maps.py:1`; `results_synthesis/names.py:3` | 5 | A script in `results_synthesis` writes it on the synthetic country; the real build needs the real runs. |
| T-R5 | 457 | implemented (ZZZ only) | `results_synthesis/names.py:14`; `results_synthesis/ranking_figures.py:1` | 2 | A script in `results_synthesis` writes it on the synthetic country; the real build needs the real runs. |
| T-R6 | 458 | implemented (ZZZ only) | `results_synthesis/names.py:14`; `results_synthesis/robustness_tables.py:1` | 14 | A script in `results_synthesis` writes it on the synthetic country; the real build needs the real runs. |
| T-R7 | 459 | implemented (ZZZ only) | `results_synthesis/names.py:14`; `results_synthesis/robustness_tables.py:22` | 8 | A script in `results_synthesis` writes it on the synthetic country; the real build needs the real runs. |
| T-R8 | 460 | implemented (ZZZ only) | `core/config_schemas.py:275`; `results_synthesis/names.py:14` | 20 | A script in `results_synthesis` writes it on the synthetic country; the real build needs the real runs. |
| T-R9 | 461 | implemented (ZZZ only) | `external_validation/table_schemas.py:86`; `results_synthesis/names.py:14` | 7 | A script in `results_synthesis` writes it on the synthetic country; the real build needs the real runs. |
| T-R10 | 462 | implemented (ZZZ only) | `core/config_schemas.py:223`; `results_synthesis/names.py:14` | 9 | A script in `results_synthesis` writes it on the synthetic country; the real build needs the real runs. |
| T-R11 | 463 | implemented (ZZZ only) | `lcoe_modeling/maps.py:1`; `lcoe_modeling/maps.py:9` | 3 | A script in `results_synthesis` writes it on the synthetic country; the real build needs the real runs. |
| T-R12 | 464 | implemented (ZZZ only) | `results_synthesis/names.py:14`; `results_synthesis/robustness_tables.py:1` | 8 | A script in `results_synthesis` writes it on the synthetic country; the real build needs the real runs. |
| T-O1 | 465 | implemented (ZZZ only) | `results_synthesis/names.py:15`; `results_synthesis/names.py:17` | 5 | A script in `results_synthesis` writes it on the synthetic country; the real build needs the real runs. |
| T-O2 | 466 | implemented (ZZZ only) | `results_synthesis/names.py:15`; `results_synthesis/names.py:17` | 4 | A script in `results_synthesis` writes it on the synthetic country; the real build needs the real runs. |
| T-O3 | 467 | implemented (ZZZ only) | `results_synthesis/names.py:15`; `results_synthesis/potential_and_cost.py:1` | 2 | A script in `results_synthesis` writes it on the synthetic country; the real build needs the real runs. |

### 1.2 What changed since the review of 2026-10-08

- Counts on 08/10 (93 identifiers): implemented 36, partial 19, contradicts 3, absent 35. Today (122 identifiers with a status, among them the 29 that did not exist or were not extracted then: T-IDs, S-IDs, M-F7b, M-F8 and U-08): implemented 105, partial 10, contradicts 1, absent 3, scope 3.
- 32 items went from absent to implemented (F5, F6, F7, F7b, F8, U-01, U-02, U-04, V-05, A-10); 12 from partial and 2 (`M-F2b-01`, `U-06`) from contradicts to implemented. Two items read as `implemented` on 08/10 are `partial` now, `M-F1-04` and `M-F4-05`: the code did not regress, the hazard data of the 2071-2100 window were never acquired and the item is judged on that. Each change is named on its row.
- Still contradicting: `M-F2a-06` (a second counting mode for tiles that are not a whole fraction of the pixel). Still partial: `M-F1b-02`, `M-F2b-06`, `M-F3-02`, `M-F3-05`, `M-F4-05`, `A-07`, `A-13`, `U-08`, `V-07`, `M-F1-04`.
- Absent by design: `M-F5-04` and `M-F6-03` (loss functions, only if OQ-007 passes a hazard), `M-E1-01` (explorer).
- No item regressed.

### 1.3 Roadmap (Section 12)

| Line | Milestone | In PROGRESS.json | Reality |
|---|---|---|---|
| MS-0 to MS-3, MS-5 | done | done | agrees |
| MS-4 | F2b rebuild as `siting_layers` | in_progress | the phase runs for three countries; open only for OQ-053 (Weibull ranges) |
| MS-6 | Parameter research | in_progress | correct (open OQs below) |
| MS-7 | F4 | in_progress | F4 ran for three countries with 36 members; open: 2071-2100 hazard data, OQ-007 |
| MS-8, MS-9, MS-10 | F5, F6, F7 and F7b | in_progress | built and green on ZZZ, never run on a real country |
| MS-11 | F8 and E1 | **not_started** | F8 has every T-ID on ZZZ; E1 not started: the line is stale for F8 |

## 2. Coherence of the texts

### 2.1 Numbers: the same everywhere

A script extracted every decimal number of each thesis text and of the H block of METHODOLOGY. The pre-registered values agree in the four places that carry them (thesis text, METHODOLOGY, `config/experiments.yaml`, phase record F7): H1 alpha 0.60, beta 0.20, m = k; H2 gamma 0.30; H3 delta 0.20; H4 0.40 and 0.60, sensitivities 0.30/0.70 and 0.45/0.55; H5 lambda 0.20 and 0.10, 8.76 TWh per GW; PRIM theta 0.20 (0.10, 0.30), peel 0.05, support 0.05 (0.02, 0.10), coverage 0.50 (0.40, 0.60), 3 descriptors, 200 replicates; synthesis minimum of two testable cases. The numbers that appear only in the tex files (0.0025, 0.22, 0.72, 0.25, 0.42, 0.84 and similar) are worked examples. The thesis files compile together with no undefined reference; overfull boxes: H5 at most 4.2 pt, the synthesis text at most 8.2 pt (the 34.6 pt equation was replaced); H4 line 254 is 15.9 pt, outside the scope of the last task.

### 2.2 Divergences found

| # | Where | What diverges | Direction |
|---|---|---|---|
| C-1 | M-F7-04 against `evaluator.py` and D-F7-010 | The text defines SR as the "share of futures" and a future as `f = (m, s)` with `f0 = (m0, s0)`; code and record use the draws `s >= 1` only. Hand check: 182/306 against 164/288 for the same cell. | METHODOLOGY wording |
| C-2 | `docs/phases/core.md` rows A-04 and U-03, section "Unowned findings" | "has no loader" (technologies.yaml, experiments.yaml): `load_technologies` and `load_experiments` exist (`config_loader.py:78,88`) | record stale |
| C-3 | `docs/PROGRESS.json` phase `core` | "A-12 partial, no seeds recorded: no sampler exists"; "parquet tables carry no schema_version"; "A-06 covers F1 and F2a" | record stale |
| C-4 | `docs/PROGRESS.json` milestone MS-11 and phases F1, F1b, F2a, F3, F5 | `not_started` for F8; `built_pending_conformance` for phases whose conformance tables are green | record stale |
| C-5 | `config/experiments.yaml:74` | "No loader enforces this yet": a comment that asserts state, forbidden by CONVENTIONS | comment |
| C-6 | `docs/phases/F1_data_acquisition.md` M-F1-02 row | status `fail` for biomass-only inputs that the item does not cover | record |
| C-7 | `docs/phases/F2a_grid_alignment.md` V-01 row | `fail`, "fixtures to refreeze after M-F2a-02"; PROGRESS says refrozen 2026-10-06 | record stale |
| C-8 | `docs/phases/F7_robustness_analysis.md` M-F7-06 row | `partial (the Jaccard comparison and H4 follow)`; both are built | record stale |
| C-9 | `docs/phases/core.md` A-13 row | 1 `Implements:` line; there are 114 | record stale |
| C-10 | `docs/PROGRESS.json` regression | "Legacy PRT/BRA baseline retired"; the 1.4 GB legacy baseline is still in `GeoFREA_data/reference` | data not cleaned |
| C-11 | M-F2a-06 | "anything else is an error"; the code counts by sample centre when the tile pixel is not a whole fraction of the grid pixel (IND) | code against text (documented) |
| C-12 | Reference period 1995-2014 | defined three times: `experiments.yaml` `windows.reference`, `climate_forcing/members.py:21` and `hazards.py:36` | duplication, no divergence today |
| C-13 | `docs/audits/` and `docs/_audit/` | two audit folders | layout |
| C-14 | `config/technologies.yaml` header | "skeleton ... values null with the OQ in a comment" | comment, harmless |

### 2.3 Notation

Differences between the LaTeX of the thesis and the ASCII of METHODOLOGY that are not typography: the regions are `A_m` (tex) and "region m" with `Q_m` (METHODOLOGY); the shortlist of axis `a` is `S^a_k` and `D_a` (tex) against `D_clim`, `D_tec` (METHODOLOGY); the reference LCOE is `L^*_f` (tex, H1, H3, H4) and "the `q_ref` quantile `L*_f`" (M-F7-02); the pairwise overlap is `J_k(sigma, sigma')` (tex) and "Jaccard of every pair of `S^sigma_k`" (METHODOLOGY). None changes a value; a notation table in the thesis would settle it.

## 3. Premises: numbers that influence results and are not in parameters.json, experiments.yaml or constants.py with a source

The scan listed 303 non-trivial numeric literals in `src/`; most are tolerances, chunk sizes, unit conversions (1e6, 8.76) and display values. The ones that can move a result:

| # | Number | Where | Influence | Source or justification today | Recommendation |
|---|---|---|---|---|---|
| P-1 | `wind_factor_valid_range` 0.5 to 1.5 | `experiments.yaml` | masks 1.4% of BRA cell-members, 24% of BRA cells have at least one masked member | "plausibility bound with no source" (M-F4-07, OQ-042 option C) | source or replace; see B-1 |
| P-2 | `wind_ratio_neighbourhood_cells` = 3 | `experiments.yaml` | size of the denominator of `delta_wind` | OQ-042 | acceptable, decided |
| P-3 | Heat thresholds 35 and 40 C, wet-day percentile 95, `REFERENCE_YEARS` | `climate_forcing/hazards.py:32-36` | the hazard indicators of T-R10 and H5b (exposure thresholds themselves are in `hazard_thresholds`, OQ-051) | names of the indicators; S-05 | move to configuration with the indicator names |
| P-4 | `ISIMIP_MAX_DISTANCE_DEG` = 0.4 | `climate_forcing/pipeline.py:39` | the cells farther than this from an ISIMIP 0.5 degree node get no hazard value | comment (half the diagonal plus margin) | acceptable; record in M-F4-05 |
| P-5 | Sensitivity grids: `SENSITIVITY_TOP_K_PERCENT` (5, 10, 20) in four modules, `GAMMA_PROFILE`, `SENSITIVITY_BOUNDARIES` of H4 | `h1`, `h2`, `h3`, `h4` modules | the sensitivity rows | METHODOLOGY text (M-F7-07) | one definition in `experiments.yaml` (duplicated four times) |
| P-6 | `P90`, `QUANTILES` (0.1, 0.5, 0.9) | `evaluator.py:37`, `summary.py:15`, `hypotheses.py`, `thesis_tables.py` | MR and every quantile | METHODOLOGY (M-F7-03, M-F6-04) | acceptable; one constant |
| P-7 | `WIND_HEIGHTS_M` (100, 150, 200) | `land_eligibility/pipeline.py:81`, `siting_layers/physical_layers.py:22` | which GWA heights exist | data product | duplicated, one place |
| P-8 | `_SIMPLIFY_TOLERANCE_DEG` 0.001, `buffer_deg` 0.01, `detect_island_nation` 0.60 | `core/geo_utils.py`, `grid_alignment/vector_alignment.py`, `core/geo_utils.py:306` | clipping geometry (about 110 m) and the island rule | none | document; effect small |
| P-9 | `sampler.seed` 42, `initial_size` 500, `convergence_tolerance` 0.01 | `experiments.yaml` | the draws and the adopted sample size | U-04 protocol | acceptable, decided |
| P-10 | `distance_cap_km` 100 | `settings.yaml` | only the flag raster (M-F2a-03), not a result | M-F2a-03 | acceptable |
| P-11 | `cf_min`, `tau`, `top_k_percent`, targets, thresholds | parameters.json / experiments.yaml | null on the real countries | OQ-008, 010, 021, 051 | the author's values |

`core/constants.py` carries its own sources (ISA values, 1.225 kg/m3, 8760 h, class codes). No result-influencing number was found in the cost kernel, the Weibull integral or the regret code that is not a parameter.

## 4. Code

### 4.1 Dead and orphan

`vulture` at 60% confidence over `src`, `main.py` and `scripts`, with and without the tests as users:

- **Used nowhere** (4 functions and classes): `core/orchestrator.py` `PhaseExecutionError`; `core/run_logging.py` `periodic_progress`; two cdsapi callback methods of `fetchers/era5.py` (`_posttask`, `_start_state`; may be called by name by the library, check before removing). The `dsk`, `worker_id` variables of `era5.py:298,307` are unused.
- **Used only by tests** (15): the oracles `lcoe_modeling/kernel.py` `lcoe_direct` and `capital_recovery_factor`, `technical_potential/rescale.py` `rescale_cf_solar` and `rescale_cf_wind` (reference implementations that the tests compare with; they belong in `tests/` or a `testing` module); `technical_potential/weibull_cf.py` `member_cf_ratio`, `wind_cf_reference`; `lcoe_modeling/sampling.py` `specs_from_parameters`; `land_eligibility/cells.py` `pixel_eligibility`; `core/paths.py` `ensure_writable`; `core/schemas.py` `BiomassParams` (technology removed by S-02/S-08); four download helpers of `fetchers/era5.py` and `cmip6.py` that only the tests call (the scripts call others).
- The other vulture hits are pydantic validators (false positives).
- **Config keys without a reader**: `settings.yaml`, `experiments.yaml` and `technologies.yaml` are validated by strict schemas (`extra="forbid"`), so a key that no model declares fails the load; a declared key that no code reads was not searched key by key. Known remnants: the commented-out `satisficing_lcoe_usd_per_mwh` and `capacity_factor_min` blocks of `experiments.yaml` (decision parameters live in parameters.json).

### 4.2 Duplicated calculations between phases

- The relative-regret and top-k logic of F7 is reused by `lcoe_modeling/convergence.py` (F6 imports F7: 4 imports); no second implementation exists.
- The energy of a cell-member is computed in F5 and read by F6 and F7; H5 recomputes nothing (checked against T-R10 and T-R12 by `_check_h5_against_*`).
- Duplicated constants, not calculations: P-5 to P-7 above.
- `thesis_tables.py` (F7) and `results_synthesis` both format H-tables; they share the F7 tables, no formula is repeated.

### 4.3 Paths exercised only by the synthetic country and tests that cannot fail

Coverage was measured over `src/geofrea` (13,351 statements): the unit tests execute 87.5%, the synthetic tests 79.9%; **877 statements are executed only by the synthetic tests, 786 by no test**.

- Only by the synthetic country: most of F8 (`robustness_tables.py` 220 statements, `synthesis.py` 108, `external_validation/pipeline.py` 84, the figure scripts), the F4 pipeline and hazards on miniature files (`climate_forcing/pipeline.py` 40, `hazards.py` 29) and the F8 runner. These are the places a real-data defect would first appear.
- Executed by no test (786): the acquisition fetchers that talk to the network (`era5.py` 185 statements, `copernicus_dem30.py` 49, `gem_trackers.py` 46, `esa_worldcover.py` 41), `robustness_analysis/pipeline.py` 29 (error branches), `core/orchestrator.py` 26, `run_logging.py` 15. The fetchers are run by hand against real servers.
- A scan of the 1,105 test functions found **7 with no assertion at all** (all are "must not raise" tests: `test_audit.py:432`, `test_core_raster_io.py:171`, `test_fetchers_cmip6.py:64`, `test_fetchers_era5.py:49`, `test_grid_alignment_alignment.py:120`, `test_iso3_literals.py:48`, `test_paths.py:128`) and **6 whose only assertions are existence or non-emptiness** (`test_cache_key.py:135`, `test_fetchers_protected_planet.py:72`, `test_grid_alignment_alignment.py:400,512`, `test_grid_alignment_raster_alignment.py:260`, `test_raster_inspection.py:138`). Seven of the thirteen are guards for a crash and are legitimate; `test_an_aligned_layer_without_a_key_sidecar_is_recomputed` and the clip-cache reuse test should assert that the recompute or reuse happened.
- The structural weakness is not the test strength but the data: ZZZ never reorders its cells, so its end-to-end values for `V_k`, `D`, `D_clim`, `D_tec` and the PRIM outcome are zero. Those quantities are covered by unit tests on constructed cases (brute-force definitions in `test_robustness_futures.py`, `test_scenario_discovery.py`, `test_h*_*.py`), not by the pipeline test.

### 4.4 Imports that cross the DAG

Package-to-package edges derived by AST; the phase order is data_acquisition, data_quality_audit, grid_alignment, siting_layers, land_eligibility, climate_forcing, technical_potential, lcoe_modeling, robustness_analysis, external_validation, results_synthesis.

| Edge | File:line | Why it matters |
|---|---|---|
| `lcoe_modeling` -> `robustness_analysis` (F6 imports F7) | `lcoe_modeling/convergence.py:42-45` | the convergence phase (U-04) needs the definitive MR; the phase `sample_size_convergence` lives in F6's package but is downstream of F7's code. A cycle at package level; none at phase level. |
| `core` -> `data_quality_audit`, `land_eligibility` | `core/config_loader.py:16`, `core/config_schemas.py:16` | `core` should not import phase packages (schemas of `AuditConfig`, `LandAvailability`) |
| `data_acquisition` -> `data_quality_audit` | `data_acquisition/adapter.py:67` | F1 imports the F1b input schema |
| `data_quality_audit` -> `land_eligibility` | `data_quality_audit/audit.py:67` | F1b imports F3 parameters |
| `technical_potential` -> `data_quality_audit` | `input_ranges.py:27`, `pipeline.py:35` | the sanity ranges (V-04), intended |
| `results_synthesis` -> `land_eligibility`, `overview` | `method_tables.py:13`, `style.py:21` | parameter schemas and the map style; allowed by the F8 import test |

No F-phase imports a later phase's computation except F6 -> F7 above. A `schemas` package at the root that holds the shared configuration models would remove the first four edges.

## 5. Workflow

### 5.1 The DAG for a country from zero

`phase_graph` (new in this session) over the specifications gives 19 phases and a valid topological order; `Orchestrator._validate_and_order` rejects missing producers, duplicates and cycles (3 unit tests). The ZZZ run from an empty directory in this audit passed in 96 s of phase time; the order observed in the manifest is the topological one.

```
data_acquisition -> data_quality_audit, grid_alignment
grid_alignment + data_quality_audit -> siting_layers -> land_eligibility
external_inputs + grid_alignment + data_quality_audit -> climate_forcing -> hazard_context, climate_maps
climate_forcing + land_eligibility -> technical_potential -> lcoe_modeling -> sample_size_convergence
lcoe_modeling + hazard_context + technical_potential + climate_forcing + land_eligibility -> robustness_analysis -> external_validation (also reads F3, F5, F6, F1)
maps: potential_maps, lcoe_maps, robustness_maps; overview; results_synthesis (8 upstream phases)
```

### 5.2 Declared reads and writes

- `produces` is enforced exactly: the orchestrator fails a phase that registers more or fewer keys than declared. The produced keys of the real manifests equal the current `produces` for every phase of BRA, PRT and IND (compared by script: 30 of 30 match).
- `requires` is the declared read set. Reads not declared: (a) `results_synthesis` reads the manifest of the support phase `cross_country_h4` (`ctx.cross_country`) and, for T-R8, the JSON profile files that its own earlier runs wrote in `outputs/thesis`; neither is a registered artifact, so a rerun of F7 or of `cross_country_h4` does not mark F8 stale, and the provenance of the T-R8 country tables does not list the profile files it read (hash). (b) The F5, F6 and F7 pipelines locate their inputs by the default phase directory when the path is not passed (`core_paths.phase_dir(...)`), while declaring the producing phase in `requires`; consistent, but the file-level contract is the directory convention. (c) The shared raw directory (`GEOFREA_SHARED_RAW_DIR`) is a read set outside the manifest: see 6.2.
- A phase cannot read a later phase: the import analysis above found only the F6 -> F7 package edge.

### 5.3 Invalidation and resume

The orchestrator hashes artifacts and invalidates consumers by content (D-core-025). 20 unit tests cover resume, stale upstream, rerun scopes, crash between phases, schema-version mismatch and removed fields. The real manifests resume cleanly under the current specifications (keys equal). Two facts: the manifests record `methodology_version` 7.2.2, 7.0.1 or none, against 13.0.1 now, and a methodology change alone does not invalidate a phase (`test_cross_run_id_resume_warns_without_failing`); this is by design, but the thesis outputs would carry the version of the F8 run only. And `clip_cache_is_current` keys the vector clip caches by the absolute path, size and mtime of the source plus the polygon: a move of the data directory invalidates all of them (the content-addressed `.cachekey` of OQ-026 does not have that limit).

### 5.4 Time and disk per phase

From the manifests and logs of the real runs (wall clock between `started_at` and `finished_at`):

| Phase | BRA | PRT | IND | Disk (outputs + interim), BRA |
|---|---|---|---|---|
| data_quality_audit | 58 min | 2 min | 4 min | 0.2 MB (+ 0.6 GB `processed` caches) |
| grid_alignment | 3 h 45 min | 5 min | 1 h 28 min | 0.95 GB outputs + 0.68 GB interim |
| siting_layers | 53 s | 2 s | 21 s | 0.40 GB |
| land_eligibility | 10 min | 11 s | 2 min | 0.33 GB + 0.28 GB interim |
| climate_forcing | 3 min | 2 min | 7 h 43 min | 0.17 GB |
| hazard_context, climate_maps | 3 min + 1 min | 33 s + 25 s | 2 min + 35 s | in the line above |
| overview | 3 min | 1 min | 2 min | 7.5 MB |
| F5 to F8 | never run | never run | never run | ZZZ: 96 s, 5.3 MB |

The IND climate_forcing time (7 h 43 min against 2 to 3 min for BRA and PRT) is not explained by the logs read in this audit; if it is the cost of a first computation, the BRA and PRT runs reused a cache.

Estimate for BRA F5 to F8 (not measured). Size: 181,277 wind and 180,041 solar candidates, 36 projection members (18 in the core window), 500 draws. The number of LCOE evaluations of the F6 sample-major pass is about 181k x 18 x 500 = 1.6e9 per technology for the core window; at the memory budget of 1 GB per block this is minutes of matrix products, not hours. F7 adds two passes over blocks and a futures pass that ranks all cells in each of 9,000 futures (181k log 181k each, about 3e10 operations); expect tens of minutes to a few hours per technology and window. **These numbers should be measured before research values arrive**: run F5 to F8 for BRA with the ZZZ test parameters in a scratch data directory (the parameters exist; only the power curves must be the test curve), which gives the time and the disk of the real size without a single real value.

## 6. GeoFREA_data

### 6.1 Inventory

`GeoFREA_data` is 134 GB: raw 130 GB (DEM 47, ERA5 37, ISIMIP3b 15, CMIP6 14, GWA 7, WorldCover 6.5, HydroSHEDS 3.4, GADM 0.7, WDPA 0.1, GEM 0.03), outputs 3.6 GB, interim 1.6 GB, reference 1.4 GB, logs 4 MB, fixtures 1 MB. 1,792 files exceed 10 MB. The table groups them (one row per pattern); "orphan" means no code path of the current pipeline reads it.

| Folder or pattern | Files >10 MB | Size | Who reads it | Duplicate or stale? | Regeneration cost if deleted |
|---|---|---|---|---|---|
| `raw/copernicus_dem30/BRA/*.tif` | 786 | 34.8 GB | `grid_alignment` `derive_slope_from_dem` (`raster_alignment.py`) through the 815 inputs hashed in `interim/BRA/grid_alignment/input_sha256.json` | no | `scripts/acquire_dem30.py`, hours; only needed when the slope cache (`interim/BRA/grid_alignment/BRA_slope_native.tif`) is invalid |
| `raw/copernicus_dem30/IND`, `/PRT` | 315, 15 | 13.1, 0.6 GB | same | no | same |
| `raw/era5/BRA/BRA_fg10_hourly.nc` | 1 | 17.0 GB | **orphan** (read by `scripts/era5_status.py` only; the pipeline reads `BRA_fg10_annual_max.nc`, 2 MB) | concatenation of the yearly files | CDS download of 20 years of hourly gusts: days |
| `raw/era5/_global/{BRA,IND,PRT}_fg10_hourly_bbox_<year>.nc` | 60 | 19.1 GB | **orphan** after the annual maxima exist (read by `fetchers/era5.py` when building them) | yes (they are the source of the concatenated file) | same |
| `raw/era5/PRT/PRT_fg10_hourly.nc`, `_global/PRT_fg10_hourly_bbox.nc` | 2 | 2.6 GB (0.3 + 2.3) | **orphan** | duplicates | same |
| `raw/cmip6/_global/` of the 6 selected GCMs (access_cm2, cnrm_cm6_1, gfdl_esm4, ipsl_cm6a_lr, miroc6, mri_esm2_0) | 72 files | 4.1 GB | `climate_forcing` (`cmip6_registry`, `forcing.py`) | no | CDS monthly request, hours |
| `raw/cmip6/_global/` of 9 other models (awi_cm_1_1_mr 2.0 GB, bcc_csm2_mr 1.5, fgoals_f3_l 1.5, cesm2 1.0, cmcc_cm2_sr5 1.0, cnrm_esm2_1 0.6, fgoals_g3 0.4, mpi_esm1_2_lr 0.3, miroc_es2l 0.2) | 108 files | 8.4 GB | **orphan** after the selection (read once by `scripts/gcm_selection_spread.py`, D-F4-012) | candidates that were not selected | CDS download, hours; the selection is recorded (`docs/_audit/2026-10_gcm_selection_*.md`) |
| `raw/isimip3b/{BRA,IND,PRT}/*_tasmax_*`, `*_pr_*` of gfdl-esm4, ipsl-cm6a-lr, mri-esm2-0 | 24 per country | 3.6 + 1.9 + 0.6 GB | `climate_forcing/hazards.py` (`HAZARD_VARIABLES = (tasmax, pr)`) | no | ISIMIP server |
| `raw/isimip3b/*/*_tasmin_*` (all five models) | 20 per country | 3.0 + 1.8 + 0.5 GB | **orphan** (no code reads `tasmin`; only `isimip3b_registry.py` names it) | variable not used | ISIMIP server |
| `raw/isimip3b/*/mpi-esm1-2-hr_*`, `ukesm1-0-ll_*` (tasmax and pr; their tasmin is in the row above) | 16 per country | 2.4 + 1.3 + 0.4 GB | **orphan** (not in the ensemble; hazard channel only for gfdl, ipsl, mri) | models not used | ISIMIP server |
| `raw/gwa/{BRA,IND,PRT}/*.tif` | 12 + 12 + 9 | 5.3 + 2.1 + 0.15 GB | `grid_alignment` (wind per height), 12 inputs per country | no | GWA download |
| `raw/esa_worldcover/IND/*.tif` | 76 | 6.9 GB | `grid_alignment` land-cover counts (91 inputs) | the shared `database/raw/land_cover/India` has the same 91 tile names at 97 MB in total (reduced) | `scripts/acquire_worldcover10m.py`, hours |
| `raw/hydrosheds/_global/HydroLAKES_polys_v10_shp.zip` and the extracted `.shp`/`.dbf` | 1 + 2 | 0.8 + 1.5 GB | `fetchers/hydrosheds.py`, `data_quality_audit`, `grid_alignment` (lakes) read the extracted `.shp` | **zip and extracted copy** | re-extract the zip (minutes); the zip is the downloaded source |
| `raw/hydrosheds/{BRA,IND,PRT}/HydroRIVERS_*` (`.shp`, `.dbf`, `.zip`) | 4 + 2 + 2 | 0.5 + 0.5 + 0.3 GB | rivers clip (`clip_cache_key`) | zip and extracted | minutes |
| `raw/gadm/BRA/gadm41_BRA_shp(.zip)` | 2 | 0.5 GB | `fetchers/gadm.py` (country polygon, Admin1) | zip and extracted | minutes |
| `raw/wdpa/IND/*.geojson` | 1 | 0.09 GB | `fetchers/protected_planet.py`, `land_eligibility` | no | WDPA token download |
| `interim/BRA/grid_alignment/BRA_slope_native.tif` (+ IND, PRT) | 3 | 0.32 + 0.15 + 0.05 GB | `grid_alignment/alignment.py:399` | **cache**; valid by key (`input_sha256.json`) | recompute from DEM: ~1 h BRA |
| `outputs/{BRA,IND,PRT}/processed/*.tif`, `*.gpkg` | 3 + 7 | BRA 0.6, IND 0.32, PRT 0.06 GB | `data_quality_audit/audit.py:265` writes the vector clips here (A-08 deviation) | **`BRA_slope_native.tif` (242 MB, 27 Sep) is stale** and read by no code (the live copy is in `interim`); the `*_clipped.gpkg` are the audit's own cache, **duplicated** in `interim/*/grid_alignment` and `interim/*/land_eligibility` (three copies of the 229 MB rivers clip, same cache key, different bytes) | minutes to ~10 min per clip |
| `interim/BRA/land_eligibility/*.npz`, `*.gpkg` | 3 | 0.28 GB | `land_eligibility` fraction caches | cache | ~10 min |
| `outputs/{BRA,IND}/grid_alignment/artifacts/*.tif` | 20 + 18 | 0.99 + 0.35 GB | `siting_layers`, `land_eligibility` (aligned layers, registered) | no | 3 h 45 min BRA |
| `outputs/{BRA,IND}/siting_layers/artifacts/*.tif` | 12 + 10 | 0.42 + 0.14 GB | `land_eligibility` cells table; `overview` | no | 1 min |
| `outputs/{BRA,IND}/land_eligibility/artifacts/*.parquet`, `*.tif` | 14 + 5 | 0.32 + 0.06 GB | F5 (`candidates_`, `cells_`), F6, F7 | no | 10 min |
| `outputs/{BRA,IND,PRT}/climate_forcing/artifacts/forcing.parquet` | 1 each | 0.17, 0.07, 0.005 GB | F5, F7, F8 | no | 3 min (cached) to 8 h |
| `outputs/PRT/suitability_criteria/`, `outputs/ZZZ/suitability_criteria/` | - | 9.5 MB, 1.7 MB | **orphan** (phase retired, D-F2b-005) | stale | n/a |
| `reference/legacy_baseline_fc7b43d/{BRA,PRT}` | 20 | 1.4 GB (`criteria_builder/result.pkl` 0.9 GB) | **orphan** (`core/paths.py` and `artifact_json.py` name the path; the regression test uses in-repo fixtures, V-01 refrozen) | retired baseline | legacy commit `fc7b43d` and its pipeline: not reproducible in practice |
| `logs/`, `fixtures/` | - | 4 MB, 0.8 MB | `run_logging`, ZZZ generator | no | - |
| `outputs/_global` | 0 | 0 | empty folder | - | - |

Invalid caches under the new key: none identified, by reasoning rather than by recomputing every key. The content-addressed `.cachekey` files of OQ-026 sit beside the aligned layers (`outputs/*/grid_alignment/artifacts/*.cachekey`, 30 files per country) and the algorithm constants (`ALIGNMENT_ALGORITHM_VERSION` 1, `LAND_COVER_TILE_ALGORITHM_VERSION` 1) did not change after the last real runs; the `.key` sidecars of the clip caches (path, size, mtime, polygon) are valid while the raw files stay where they are. The legacy `.key` caches in `outputs/*/processed/` were written on 7 October by the previous layout and are read only if the audit phase finds them current; they are valid by their key but duplicate the interim copies.

Candidates to delete, by saving and cost: (1) the yearly and concatenated ERA5 hourly files, 38.7 GB, regenerable only by days of CDS time: **move to cold storage rather than delete** unless the annual maxima are final; (2) the nine unselected CMIP6 models, 8.4 GB, hours; (3) ISIMIP3b `tasmin` and the two unused models, 9.4 GB; (4) the extracted HydroLAKES (1.5 GB) or the zip (0.8 GB) and the other zip/extracted pairs, ~1.2 GB, minutes; (5) `outputs/*/processed` stale slope and duplicated clips, ~1.2 GB, minutes; (6) `reference/legacy_baseline_fc7b43d`, 1.4 GB; (7) the retired `suitability_criteria` folders, 11 MB.

### 6.2 What lives outside the data directory

The pipeline also reads the shared raw directory `D:\Douglas\DOUTORADO\database\raw` (67 GB; `GEOFREA_SHARED_RAW_DIR`, read-only): population (28 GB), infrastructure (12), wind potential (11), land cover (11: BRA 8.3, PRT 0.9), hydrology (3.6), elevation, solar potential, borders, protected areas. The BRA and PRT 10 m land cover, the population, grid and roads layers, the PVOUT raster and the country polygons are inputs of the real runs and are recorded in `input_sha256.json` by absolute path. `GeoFREA_data` is therefore not self-contained, A-08 ("all data in GEOFREA_DATA_DIR") has this declared exception in `core/paths.py`, and the same "10 m product for the three countries" (M-F2a-06) is stored in two places (IND in `GeoFREA_data/raw/esa_worldcover`, BRA and PRT in the shared directory). Moving the data directory invalidates the vector clip caches (5.3).

## 7. Numerical validation on ZZZ

### 7.1 Method

A full F1 to F8 run on the synthetic country was made from an empty directory (the ZZZ fixture of the test suite, `pytest --basetemp`, 128 s including the build), and `docs/_audit/2026-10_pre_research_audit_scripts/validate_zzz_by_hand.py` recomputed one or more values per phase. The script imports nothing from `geofrea`; every expected value comes from the formula of METHODOLOGY with numpy, scipy and xarray (ellipsoidal area by quadrature, bilinear interpolation by `RegularGridInterpolator`, Weibull integrals by `scipy.integrate.quad`, LCOE by an explicit loop over the years, ranks and regrets by sorting). To repeat: run the ZZZ test with `--basetemp=<dir>` and call the script with `<dir>/zzz_data0`.

### 7.2 Results (wind: 40 checks, solar: 15 checks, all pass)

Wind (the F7 and F8 rows exist for wind only):

| Check | Expected (by hand) | Obtained (artifact) | Difference | Tolerance | Result |
|---|---|---|---|---|---|
| F3 cell 13655201: cell_area_km2 (sum of 25 geodesic pixel areas) | 30.66653347 | 30.66652344 | 1e-05 | 0.0001 | PASS |
| F3 cell 13655201: eligible_area_km2 (sum fraction x pixel area) | 30.66653347 | 30.66652344 | 1e-05 | 0.0001 | PASS |
| F4 m_gfdl_esm4_ssp370_2041_2070 cell 13655201: delta_rsds (ratio of window and reference means, bilinear) | 0.9919999897 | 0.992000103 | 1.13e-07 | 5e-07 | PASS |
| F4 same: dT (difference of means, K; single-precision tolerance 2e-4 K) | 1 | 0.9999281764 | 7.18e-05 | 0.0002 | PASS |
| F4 same: delta_wind (3x3 neighbourhood ratio, bilinear) | 1 | 1 | 0 | 1e-09 | PASS |
| F5 wind cell 13655201 m0: CF (Weibull x power curve, numerical quadrature) | 0.3985476827 | 0.3985476827 | 3.89e-16 | 1e-06 | PASS |
| F5 wind cell 13655201 m0: P_MW = eligible_area x LUF x PD | 153.3326172 | 153.3326172 | 0 | 1e-09 | PASS |
| F5 wind cell 13655201 m0: E_MWh = P x CF x 8760 | 535326.7473 | 535326.7473 | 0 | 1e-09 | PASS |
| F5 wind cell 13655201 m_gfdl_esm4_ssp370_2041_2070: CF (Weibull x power curve, numerical quadrature) | 0.3985476827 | 0.3985476827 | 3.89e-16 | 1e-06 | PASS |
| F5 wind cell 13655201 m_gfdl_esm4_ssp370_2041_2070: P_MW = eligible_area x LUF x PD | 153.3326172 | 153.3326172 | 0 | 1e-09 | PASS |
| F5 wind cell 13655201 m_gfdl_esm4_ssp370_2041_2070: E_MWh = P x CF x 8760 | 535326.7473 | 535326.7473 | 0 | 1e-09 | PASS |
| F6 wind cell 13655201 m0: nominal LCOE (textbook loop over the years) | 41.58255469 | 41.58255469 | 0 | 1e-09 | PASS |
| F6 wind cell 13655201 m_gfdl_esm4_ssp370_2041_2070: nominal LCOE (textbook loop over the years) | 41.58255469 | 41.58255469 | 0 | 1e-09 | PASS |
| F6 cell 13655201 m_gfdl_esm4_ssp370_2041_2070: mean over the 16 draws | 43.97273367 | 43.97273367 | 7.11e-15 | 1e-09 | PASS |
| F6 same: variance over the draws (ddof=1) | 44.92176355 | 44.92176355 | 0 | 1e-08 | PASS |
| F6 same: p10 (linear interpolation of order statistics) | 36.05856073 | 36.05856073 | 0 | 1e-09 | PASS |
| F6 same: p90 | 52.40417387 | 52.40417387 | 2.84e-14 | 1e-09 | PASS |
| F7 MR of cell 13662403 (max over 18 members of the P90 over 16 draws of the relative regret) | 5.725126976e-05 | 5.725126976e-05 | 2.74e-16 | 1e-09 | PASS |
| F7 MR of all 17 ranked cells: largest absolute difference | 0 | 5.204170428e-16 | 5.2e-16 | 1e-10 | PASS |
| F7 SR of cell 13662403 (share of 288 futures with LCOE <= tau) | 0.5694444444 | 0.5694444444 | 0 | 1e-12 | PASS |
| F7 nominal top-5 cells | [13655202, 13655203, 13662402, 13662403, 13669603] | [13655202, 13655203, 13662402, 13662403, 13669603] | 0 | 0 | PASS |
| F7 robust top-5 cells | [13655202, 13655203, 13662402, 13662403, 13669603] | [13655202, 13655203, 13662402, 13662403, 13669603] | 0 | 0 | PASS |
| H1 C_k (|intersection of the three SSP top-k sets| / k) | 1 | 1 | 0 | 1e-12 | PASS |
| H1 V_k (share of the nominal top-k outside the top k+m of the climate-only ranking in some SSP) | 0 | 0 | 0 | 1e-12 | PASS |
| H1 reference p_k^2 | 0.08650519031 | 0.08650519031 | 0 | 1e-12 | PASS |
| H2 O (share of T selected by both procedures) | 0.3221296653 | 0.3221296653 | 5.55e-17 | 1e-12 | PASS |
| H2 O_ref = T / Q_max | 0.3149300354 | 0.3149300354 | 1.11e-16 | 1e-12 | PASS |
| H3 D (capacity share of the robust top-k whose nominal rank exceeds k+m) | 0 | 0 | 0 | 1e-12 | PASS |
| H4 D_clim | 0 | 0 | 0 | 1e-12 | PASS |
| H4 D_tec | 0 | 0 | 0 | 1e-12 | PASS |
| H4 profile when D_sum = 0 | no_displacement | no_displacement | 0 | 0 | PASS |
| H5 E_0 (TWh/year of the fixed domain at m0) | 7.172967084 | 7.172967084 | 1.78e-15 | 1e-09 | PASS |
| H5 G (TWh/year; 8.76 x G_cap x capacity-weighted reference CF of the cheapest cells) | 0.00034912777 | 0.00034912777 | 0 | 1e-09 | PASS |
| H5 Delta E = max(0, E_0 - min over the core members E_m) | 0.5658845789 | 0.5658845789 | 1.78e-15 | 1e-09 | PASS |
| H5 R_loss = Delta E / H_0 | 0.07889512342 | 0.07889512342 | 2.22e-16 | 1e-09 | PASS |
| PRIM density of the stored box, recomputed on the stored futures | 1 | 1 | 0 | 1e-12 | PASS |
| PRIM coverage of the stored box, recomputed on the stored futures | 1 | 1 | 0 | 1e-12 | PASS |
| PRIM coverage of the stored box is at least the pre-registered 0.50 | 1 | 1 | 0 | 0 | PASS |
| PRIM outcome V_f by hand: the largest value over the 288 futures (ZZZ keeps the order of its cells) | 0 | 0 | 0 | 1e-12 | PASS |
| PRIM stored outcome in this run (test rule on the GCM, tests/synthetic only) | [0.05, 0.5] | [0.05, 0.5] | 0 | 0 | PASS |

Solar (F3 to F6):

| Check | Expected (by hand) | Obtained (artifact) | Difference | Tolerance | Result |
|---|---|---|---|---|---|
| F3 cell 13669600: cell_area_km2 (sum of 25 geodesic pixel areas) | 30.66209012 | 30.66208009 | 1e-05 | 0.0001 | PASS |
| F3 cell 13669600: eligible_area_km2 (sum fraction x pixel area) | 15.33122479 | 15.33121978 | 5.01e-06 | 0.0001 | PASS |
| F4 m_gfdl_esm4_ssp370_2041_2070 cell 13669600: delta_rsds (ratio of window and reference means, bilinear) | 0.9919999895 | 0.992000103 | 1.13e-07 | 5e-07 | PASS |
| F4 same: dT (difference of means, K; single-precision tolerance 2e-4 K) | 1 | 0.9999254346 | 7.46e-05 | 0.0002 | PASS |
| F4 same: delta_wind (3x3 neighbourhood ratio, bilinear) | 1 | 1 | 0 | 1e-09 | PASS |
| F5 solar cell 13669600 m0: CF = PVOUT/24 x delta_rsds x (1 + gamma dT) | 0.1875 | 0.1875 | 0 | 1e-09 | PASS |
| F5 solar cell 13669600 m0: E_MWh = P x CF x 8760 | 125907.6425 | 125907.6425 | 0 | 1e-09 | PASS |
| F5 solar cell 13669600 m_gfdl_esm4_ssp370_2041_2070: CF = PVOUT/24 x delta_rsds x (1 + gamma dT) | 0.1850700886 | 0.1850700886 | 0 | 1e-09 | PASS |
| F5 solar cell 13669600 m_gfdl_esm4_ssp370_2041_2070: E_MWh = P x CF x 8760 | 124275.9389 | 124275.9389 | 0 | 1e-09 | PASS |
| F6 solar cell 13669600 m0: nominal LCOE (textbook loop over the years) | 86.74787467 | 86.74787467 | 1.42e-14 | 1e-09 | PASS |
| F6 solar cell 13669600 m_gfdl_esm4_ssp370_2041_2070: nominal LCOE (textbook loop over the years) | 87.86058732 | 87.86058732 | 4.26e-14 | 1e-09 | PASS |
| F6 cell 13669600 m_gfdl_esm4_ssp370_2041_2070: mean over the 16 draws | 90.25359634 | 90.25359634 | 1.42e-14 | 1e-09 | PASS |
| F6 same: variance over the draws (ddof=1) | 150.5759798 | 150.5759798 | 5.68e-13 | 1e-08 | PASS |
| F6 same: p10 (linear interpolation of order statistics) | 77.37086101 | 77.37086101 | 0 | 1e-09 | PASS |
| F6 same: p90 | 105.7630967 | 105.7630967 | 5.68e-14 | 1e-09 | PASS |

### 7.3 What the validation does and does not show

- It shows that the formulas of METHODOLOGY are what the code computes, to double precision, for the eligible area, change factors, both capacity factors, the LCOE and its draw statistics, the regret and `MR` of all 17 ranked cells, the rankings, `C_k`, `O`, `R_loss` and the PRIM bookkeeping.
- The change factors differ from the double-precision expectation by up to 7e-5 K (`dT`) and 1.1e-7 (ratios): the phase averages float32 fields in float32. Harmless against a 0.3 K spread between GCMs, but a cast to float64 costs one line (section 9, M-3).
- **ZZZ cannot tell a correct ranking from a wrong one**: the 17 wind cells keep their order in every future, so the nominal, robust, climate-only and techno-only shortlists coincide and `V_k`, `D`, `D_clim`, `D_tec` and the real `V_f` are all zero (the checks on them pass for the right reason, but they would also pass for a function that returns zero). `H2`'s `O`, `H5`'s `R_loss` and `C_k` are the only non-trivial statistics. The brute-force unit tests cover the non-trivial cases for each hypothesis (section 4.3); an end-to-end synthetic world in which the climate factor reorders cells would close the gap (M-1).
- PRIM: the box of the ZZZ run isolates one GCM by construction of the test rule; the script checks density 1.0 and coverage 1.0 on the stored futures, the coverage requirement 0.50, and that the real outcome by hand is zero (which is why the pipeline test replaces it, D-F7-057, and why no code in `src/` does, D-F7-060).

## 8. Plausibility of the real F1 to F4 data

Produced by `plausibility_real_data.py` (full tables in its output; the lines below are the ones that look implausible or notable). Layers pass the sanity ranges of `audit.yaml`; the findings are about what the ranges do not catch.

### 8.1 What is plausible

- **Resource layers** (siting layers, F2b): PVOUT 2.8 to 5.2 kWh/kWp/day (BRA), 3.5 to 4.8 (PRT), 2.1 to 5.8 (IND), medians 4.2 to 4.3; Weibull A at 100 m median 4.2 (BRA), 6.5 (PRT), 5.0 (IND) m/s; `k` medians 2.0 to 2.2; distances to the grid median 24 km (BRA), 2 km (PRT), 10 km (IND) with uncapped maxima 951, 34 and 384 km; cell areas 22 to 31 km2 inland, down to 1 km2 at coasts. The share of valid pixels (BRA 46%, PRT 52%, IND 36%) is the mainland polygon on its bounding box.
- **Change factors, medians of the 2041-2070 window** (6 GCMs per SSP): `dT` BRA 1.2 K (SSP1-2.6), 1.9 (SSP3-7.0), 2.3 (SSP5-8.5); PRT 1.0, 1.5, 1.9; IND 1.3, 1.7, 2.2 K, ordered by scenario and growing to 2071-2100 (BRA SSP5-8.5 4.4 K, p99 7.1 K). `delta_rsds` between 0.83 and 1.19 (IND the widest). The reference member is exactly 1, 0, 1.
- **Hazard context**: `gust_mean_annual_max_ms` 10 to 28 m/s (BRA), 23 to 32 (PRT), 11 to 32 (IND); `rx5day_mm` maxima 382 (BRA), 189 (PRT) and 1,090 mm (IND, Western Ghats and Meghalaya); the share of days above the 95th percentile of wet days (`wet_p95_exceed_freq`) 0.02 to 0.13.
- **Candidate sets**: BRA 180,041 solar and 181,277 wind candidates of 285,999 cells (eligible area 1.5 and 2.2 million km2 on 8.5 million km2); PRT 3,446 and 3,496 of 3,937; IND 54,182 and 62,718 of 105,952.

### 8.2 What looks implausible or needs a decision

| # | Finding | Evidence | Why it matters |
|---|---|---|---|
| 8-1 | **Wind factor out of range for MIROC6** | `forcing_masked.parquet` BRA: 146,811 cell-members (1.4% of rows), 68,276 of 285,999 cells (24%) have at least one masked member; 71% of them belong to MIROC6 (`m_miroc6_ssp370_2071_2100` 34,874, `m_miroc6_ssp370_2041_2070` 32,505, `m_miroc6_ssp585_2041_2070` 14,507); the rejected `delta_wind` has median 1.95 and maximum 78.2. Accepted values stop at 1.4999 (the range edge). PRT and IND: none masked. | A ratio of 78 means a reference wind near zero in the 3 x 3 neighbourhood of a native cell over land. The range 0.5 to 1.5 has no source (P-1). In F7 these cells are `climate_data_invalid` and are not ranked: B-1 |
| 8-2 | **Cooling in a warming scenario** | BRA `dT` < 0 in 6,264 rows: MIROC6 SSP1-2.6 2041-2070 (4,534 rows), MRI SSP1-2.6 (1,730); the minimum is -0.97 K (SSP1-2.6, 2071-2100). | Small (0.1% of rows) and possible as a 30-year mean at the edge of a coarse GCM cell, but a negative `dT` is read by `(1 + gamma dT)` as a gain in PV efficiency. Review with 8-1 |
| 8-3 | **Heat days double in the median cell of Brazil** | `tx35_days` median 30 days per year in the reference, 110 in 2041-2070 (maximum 296 days against 180 in the reference); `tx40_days` p99 4 days against 46. IND: 112 to 141 (median), PRT 5.6 to 20.8. | The 9 hazard members include the warm IPSL-CM6A-LR; the indicators are counts on the ISIMIP3b bias-adjusted `tasmax`. A median rise of +80 days for +2 K is large but arithmetically consistent with a steep daily distribution near 35 C; the reference values (BRA median 30, maximum 180 days) are high for Brazil (Caatinga is about 100 to 150). Check the reference counts against ISIMIP or ERA5 before they feed an exposure threshold (OQ-051) |
| 8-4 | **High-altitude wind candidates in India** | `air_density_100m`: minimum 0.517 kg/m3 in the layer, 0.629 among IND wind candidates, p1 0.744; 1,041 candidate cells (1,713 km2) below 0.8 (about 4,000 m and up, Ladakh and the Himalaya). | Utility-scale wind at those altitudes is not realistic; no exclusion or sanity check removes them: B-3 |
| 8-5 | **Weibull shape below 1** | IND wind candidates: `k` < 1 in 0.35% (minimum 0.78); BRA 0.01% (minimum 0.85); raster minima 0.56 (IND), 0.81 (BRA). | `k` < 1 is a heavy-tailed, almost always windy-or-calm distribution; real sites have `k` of 1.2 to 3.5. Probably river valleys at the edge of the GWA product; flag |
| 8-6 | **Extreme Weibull scale** | BRA raster `weibull_a_100m` maximum 15.5 m/s (p99 8.5); 4 candidate cells with A > 12 at 100 m, 75 at 200 m. IND maximum 20.4 (candidates 11.4). | Mountain summits and coastal pixels; negligible in area, but the highest cells are the cheapest in the ranking and enter the top-k |
| 8-7 | **Air density minimum in the raster** | the layers are stated against ISA at the elevation of the DEM with 5% tolerance (D-F1b-015) and 0 pixels fall outside; so 8-4 is consistent with the sanity rule: the range is too wide to catch it | The sanity range cannot protect against unrealistic altitude |

## 9. Prioritised list

Effort: S under an hour, M half a day, L several days. "Result" means it changes a number of the thesis.

### 9.1 Blockers (error a result or stop the real run)

| # | Finding | Effect | Effort | Recommendation |
|---|---|---|---|---|
| B-1 | The wind-factor validity range 0.5 to 1.5 has no source and the factor of MIROC6 (up to 78 times the reference wind, mostly SSP3-7.0 and SSP5-8.5) is the cause of 71% of the 146,811 masked BRA cell-members; 24% (68,276) of BRA cells lose at least one member and become `climate_data_invalid` in F7, so a quarter of the country is not ranked and the removal is concentrated in the GCM that S-04 makes mandatory | Result | M | Inspect the MIROC6 `sfcWind` historical field over Brazil (near-zero reference over land?); decide between a source for the range, a larger neighbourhood (OQ-042), or excluding the wind channel of that GCM; the author's decision, then rerun F4 BRA |
| B-2 | The real F5 cannot start: `config/power_curves/` does not exist, `iec_class_rule` and `power_curves` are null, and every decision parameter is pending (OQ-004, 005, 008, 010, 021, plus OQ-001, 016 to 019, 022 for F6) | Gate | the author's research | Expected; the refusal lists the missing items. Check that it also names the absent `config/power_curves/` directory |
| B-3 | Wind candidates at altitude: 1,041 Indian candidate cells (1,713 km2) have air density below 0.8 kg/m3 (about 4,000 m and above); no exclusion or sanity check removes a high-altitude cell, and 0.35% of IND candidates have Weibull `k` < 1 (BRA 0.01%) | Result (small) | S | Decide a rule (altitude ceiling, or accept and report); if kept, a `k` < 1 cell should be flagged because the closed-form integral is defined but physically unusual |
| B-4 | `results_synthesis` T-R8 reads profile JSON files from `outputs/thesis` (its own earlier outputs) that are not registered artifacts and not hashed in the provenance | Reproducibility | S | Record the SHA-256 of each profile file read in the provenance of the T-R8 tables; consider registering the profiles as artifacts of F7 |
| B-5 | `cross_country_h4` runs outside the orchestrator; a rerun of one country's F7 does not mark the H4 verdict, T-R6, T-R7 or T-R8 stale | Staleness | M | Make it a phase over the countries' manifests, or have F8 refuse when the cross-country manifest is older than a country's F7 |

### 9.2 Inconsistencies (text or register diverges)

| # | Finding | Effort | Recommendation |
|---|---|---|---|
| I-1 | C-1: M-F7-04 "share of futures" against the draws-only SR | S | One-word change to METHODOLOGY (PATCH), needs the author |
| I-2 | C-2 to C-10 (eleven stale statements in `core.md`, PROGRESS.json, F1/F2a/F7 records, `experiments.yaml:74`); MS-11 `not_started` | S | One sweep of the registers, as done for 7.2.2; no METHODOLOGY change |
| I-3 | C-11, M-F2a-06 text against the sample-centre mode | S | Amend the item (PATCH) to describe both modes, or remove the second |
| I-4 | C-12: reference period in three places; P-5 to P-7 constants duplicated | S | One definition each in `experiments.yaml` |
| I-5 | C-13: `docs/audits` and `docs/_audit` | S | Merge, update the README of `docs` |
| I-6 | Notation differences 2.3 | S | A notation table in the thesis front matter |
| I-7 | `core.md` A-13: `Implements:` in 103 of 127 identifiers | M | Add the lines for the 24 uncited items (or accept) |

### 9.3 Cleanup (dead, orphan, cache)

| # | Item | Saves | Effort | Recommendation |
|---|---|---|---|---|
| L-1 | ERA5 hourly yearly and concatenated files | 38.7 GB | S | Cold storage; keep the annual maxima (2 MB) |
| L-2 | Nine unselected CMIP6 models | 8.4 GB | S | Delete; the selection record keeps the decision |
| L-3 | ISIMIP3b tasmin and unused models | 9.4 GB | S | Delete |
| L-4 | Zip and extracted pairs (HydroLAKES, HydroRIVERS, GADM) | ~3 GB | S | Keep the zip (source of truth), delete the extraction or the reverse |
| L-5 | `outputs/*/processed` stale slope and duplicate clips; make the audit write into `interim` like the other phases | ~1.2 GB | S | Delete the stale slope; move the audit's clips to `interim` (A-08 deviation) |
| L-6 | `reference/legacy_baseline_fc7b43d` | 1.4 GB | S | Cold storage |
| L-7 | Retired `suitability_criteria` outputs | 11 MB | S | Delete |
| L-8 | Dead code: `PhaseExecutionError`, `periodic_progress`, `BiomassParams`, `ensure_writable`, `pixel_eligibility`, `specs_from_parameters`; oracles `lcoe_direct`, `rescale_cf_*`, `member_cf_ratio`, `wind_cf_reference` to `tests/` | - | M | Remove or move; run the suite |
| L-9 | Five DAG-crossing imports (4.4) | - | M | Shared `schemas` package |

### 9.4 Improvements (not urgent)

| # | Item | Effort | Recommendation |
|---|---|---|---|
| M-1 | A second synthetic world (ZZZ2) in which `delta_wind` reorders the cells, so that `V_k`, `D`, `D_clim`, `D_tec`, `V_f` and the PRIM box are non-trivial end to end | M | Highest value for the tests |
| M-2 | Measure F5 to F8 time and disk at the BRA size with test parameters (5.4) | M | Before research values arrive |
| M-3 | Cast the change factors to float64 before averaging | S | One line in `change_factors.py` |
| M-4 | Make the audit's hand validation a CI job (the script exists; CI would run the ZZZ and then the script) | S | Yes |
| M-5 | Inputs of the real runs under the data directory (shared raw) or recorded with a content hash | M | Reproducibility off this machine |
| M-6 | Tests that assert recompute / reuse instead of "does not crash" (4.3) | S | Six tests |
| M-7 | Coverage gates for the fetchers (0 to 50%) through recorded HTTP responses | L | Optional |
| M-8 | Hazard indicators: heat thresholds 35/40 C and 95th percentile to configuration (P-3) | S | With OQ-051 |

## 10. What was not done

The numeric validation covers wind through F7 and solar through F6 (the regret recomputation needs the energy to scale with `eta_loss`; for solar it scales with `gamma` and the hand code is not written). The real F5 to F8 were not run. The plausibility of hazard indicators was judged against general knowledge of the regions, not against an external dataset. The shared database directory was inventoried by folder, not file by file. Nothing was deleted.

## 11. Follow-up of the improvements M-1, M-2 and M-4 (COMMAND 39, 2026-10-15)

- **M-1, done.** The second synthetic world ZZZ2 (`scripts/zzz2_world.py`, `scripts/generate_zzz2_fixture.py`, `tests/synthetic/test_zzz2_end_to_end.py`) reorders the cells between members and between draws. Its end-to-end values are non-trivial and were known before the run, from the closed-form fields and the plain-numpy hand validation: wind `V_k` 0.6, `D` = `D_clim` = `D_tec` = 0.387 (`rho` 0.5, mixed); solar `V_k` 0.6, `D` 0.193, `D_clim` 0.193, `D_tec` 0.190; the PRIM outcome is the real one (no rule replaces it) and the box restricts the climate model in both technologies (density 0.984 and 0.586, coverage 0.892 and 0.918). The gap of section 7.3 (a function that returns zero would also pass) is closed for these quantities.
- **M-4, done.** The hand validation is a CI job (`hand-validation` in `.github/workflows/synthetic_fixture.yml`) on ZZZ and ZZZ2, wind and solar. The part that was missing, the regret recomputation of F7 for solar (energy scaled by `(1 + gamma dT)`), is written: 40 checks (wind) and 38 (solar) pass on both worlds.
- **M-2, done.** F5 to F8 at the size of BRA (181,277 wind and 180,041 solar candidates, 36 members, 500 draws), test parameters, synthetic curve, a scratch data directory that held a copy of the real F3 and F4 outputs and was removed; the 178 files of the real `outputs/BRA` kept their hashes. Wall clock, peak working set and disk growth per phase (not a result; `scripts/size_f5_to_f8.py`):

| Phase | Wind: time / peak / disk | Solar: time / peak / disk |
|---|---|---|
| F5 technical potential | 228 s / 1.6 GB / +396 MB | 85 s / 1.7 GB / +465 MB |
| F5 maps | 32 s / 1.4 GB / +3 MB | 22 s / 1.5 GB / +3 MB |
| F6 LCOE | 259 s / 1.5 GB / +791 MB | 260 s / 1.5 GB / +720 MB |
| F6 sample-size convergence | 172 s / 1.5 GB / 0 | 200 s / 1.6 GB / 0 |
| F6 maps | 50 s / 1.7 GB / +9 MB | 39 s / 2.2 GB / +9 MB |
| F7 robustness (core and sensitivities) | 2,477 s / 2.2 GB / +169 MB | 1,780 s / 2.4 GB / +121 MB |
| F7 maps | 43 s / 0.5 GB / +11 MB | 43 s / 0.5 GB / +13 MB |
| F7b external validation | 163 s / 2.8 GB / +0.1 MB | 113 s / 2.7 GB / +0.1 MB |
| F8 results synthesis (one technology) | 79 s / 1.9 GB / 0 | 65 s / 2.4 GB / 0 |
| **F5 to F8** | **58 min / 2.8 GB / +1.38 GB** | **44 min / 2.7 GB / +1.33 GB** |

  The estimate of section 5.4 ("tens of minutes to a few hours per technology and window") is at its low end: F7 is 41 min (wind) and 30 min (solar), about two thirds of the chain. The highest peak is F7b (2.8 GB), not F7. The inputs copied from F3 and F4 are 3.2 GB. Conditions that make the numbers an upper bound for the same size: `cf_min` 0.01, so every candidate is in the F7 set.
