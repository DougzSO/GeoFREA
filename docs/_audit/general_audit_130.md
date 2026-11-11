# General audit, read-only (COMMAND 130)

Written for: the author. Nothing in the repository, the data or the manifests was changed; the measurements were made on `main` at `e0b2cbf` (after COMMAND 129) with tools installed in a scratch environment (radon 6.0.1, vulture 2.16, mypy 2.4.1) and a coverage run of the whole suite. The coverage run is the only long measurement (55 min); the rest is reading and counting. Where a number is an estimate by arithmetic it says so.

## Summary

| section | in one line |
|---|---|
| A | 26 open or partly open OQ: 7 to resolve now, 8 are the author's decision, 11 wait for the F6 to F8 inputs and the thesis, none is dropped; 93 L (accepted limits), 359 D- identifiers, no open D. |
| B | No import cycle between packages and none core -> phase or src -> tests; one two-module cycle (`robustness_analysis.assemble` <-> `hypotheses`); three modules above 1,500 lines and 13 functions above 200; 36 blocks of complexity D or worse (8 of rank F); duplication is low (7 pairs); dead code is small (about 6 callables and 5 variables); 340 mypy errors on `src`, 21 in the core; the phase contract is uniform in shape, with exceptions listed. |
| C | 162 test files, 2,508 tests, 3,260 s of test time (55 min under coverage, 41 min plain), line coverage 95%; 39 files add no line that no other file covers; nothing is proposed for removal; 3 files go to a nightly or manual run, none is a decision, V-01 or ZZZ test. |
| D | 50 scripts (2 referenced from nowhere), 87 audit documents, 2 local-only unmerged branches, 7 merged branches and 3 worktrees; `GeoFREA_data` holds 106 GB of `raw`, 25 GB `external`, 7.1 GB `work` (5.2 GB of it `pre116`), 7.7 GB of `backup_*` and `_f3_*` folders, 3.5 GB of references (10 rounds). |
| E | Real countries, 12 phases ran: 5.6 min (PRT), 25 min (IND), 40 min (BRA) cold. Five consumers: grid_alignment, land_eligibility, data_acquisition, the test suite and the BRA memory of three phases above 2 GB. |
| F | A clean clone does not run ZZZ end to end by the README: 5 steps fail or are missing. The three real countries have 22 layers each, all with a SHA-256. |
| G | One window of changes touches the fingerprint of at most 15 phases; a clean round of the 12 phases that ran costs 71 min for the three countries (F6 to F8 have not run on real data). |

---

## A. Open OQ, L and D

Classes: (1) resolve now, (2) the author's decision, (3) depends on Groups 4, 5 and 7 (the F6 to F8 inputs and the thesis; this mapping of groups to phases is my reading of the OQ text, not something the repository states), (4) accepted limit.

| OQ | subject | class | what to do (class 1) or why |
|---|---|---|---|
| OQ-073 | nine lint suppressions kept for the fingerprints | 1 | Apply the proper forms (`Self`, etc.) inside the single window of section G, where a recompute is already planned. |
| OQ-074 | geopandas 1.2.0 breaks 52 figure tests | 1 | Run the 52 tests under 1.1.2 and 1.2.0, compare the figures, fix the code or regenerate the goldens; a clean clone installs 1.2.0 today (section F). |
| OQ-075 | Pillow 13 changes the golden hashes | 1 | Regenerate the goldens under Pillow 13 after looking at them and record the version in the test. |
| OQ-078 | ERA5 `write_annual_maxima_from_hourly` hangs under `fork` on Linux | 1 | Set the `spawn` start method explicitly in `_run_worker_with_watchdog`; changes `data_acquisition` (window of G). |
| OQ-079 | basis of `P_ref` for PV (DC) | 1 | State the DC basis in the unit and note of `reference_project_mw` and in M-F6-08: text only. |
| OQ-083 | obsolete sidecars and GLO30 slope layers | 1 | Delete or re-key the 6 clip `.key` per country and the unregistered GLO30 slope layers; list in section D. |
| OQ-071 | retune the ZZZ2 solar world | 1 | Move cost spreads or cell areas in `scripts/zzz2_world.py` until the PRIM box is free of the climate model. |
| OQ-084 | content hash includes the Arrow type | 2 | Choose logical-type hash (new prefix `parquet2:`), write with the declared schema, or both. |
| OQ-080 | deferred gate publishes before comparing | 2 | The author decides; COMMAND 129 worked around it by not publishing. |
| OQ-082 | no official way to run a phase on fixed inputs | 2 | The author decides. |
| OQ-063 | provenance of the global `grid.gpkg` | 2 | The author completes `docs/data/grid_provenance.md`. |
| OQ-072 | FABDEM CC BY-NC-SA | 2 | The author decides where the results go; GLO-30 fallback exists. |
| OQ-070 | 250 persons/km2 of CEEW cited second-hand | 2 | The author reads the report or drops the figure. |
| OQ-043 | source of `wind_factor_valid_range` | 2 | The author finds a published bound. |
| OQ-011 | grid source and voltage per country | 2 | Largely answered by Group 3 (`vth_evidence_85`); the author closes or restates it. |
| OQ-007, OQ-008, OQ-010, OQ-020, OQ-021, OQ-051, OQ-057 | hazard loss functions, `tau` and `CF_min`, targets, `q_ref`, `p_k`, hazard thresholds, published potentials | 3 | F6 to F8 inputs. |
| OQ-064, OQ-068, OQ-013, OQ-014 | resolution sensitivity, F7b stripes, explorer stack, thesis literature | 3 | After F7 and F7b exist (OQ-068 before F7b runs at scale on BRA). |

Closed in this period: OQ-081, OQ-085. L (93 rows): all are accepted limits (class 4); 27 mention F6, F7 or F8 and are provisional until those phases run on real data; the most cited OQ in them is OQ-001 (6). D: 359 decision identifiers in `docs/phases/`, none marked open.

---

## B. Structure

**Import graph** (`ast`, 183 modules, 668 edges, module-level and inside functions): no cycle between packages. One cycle between two modules: `robustness_analysis.assemble` and `robustness_analysis.hypotheses`. No module of `core` or `config_models` imports a phase; no module of `src` imports `tests` (`viz/examples.py` reads the fixtures of `tests/` by path, an item of the COMMAND 125 audit). `tests/unit/test_import_dag.py` orders packages, not modules, so the module cycle is not caught.

**Size and complexity** (radon): average complexity A (3.9) over 2,071 blocks; 36 blocks of rank D or worse (21 D, 7 E, 8 F). The worst:

| block | complexity | lines |
|---|---:|---:|
| `robustness_analysis/pipeline.py::run_window` | 176 | 862 |
| `main.py::_build_phase_specs` | 87 | 829 |
| `core/orchestrator.py::Orchestrator.run` | 78 | 436 |
| `robustness_analysis/h5_climate_pressure.py::evaluate_h5` | 54 | |
| `data_quality_audit/audit.py::_format_report` | 53 | 219 |
| `main.py::_main` | 52 | |
| `viz/panels.py::new_panels` | 44 | 314 |

Modules above 1,500 lines: `viz/mapstyle.py` (2,479), `main.py` (1,815), `robustness_analysis/pipeline.py` (1,811); above 1,000: seven. Functions above 200 lines: 13; above 100: 50 (of 1,722).

**Duplication** (structurally identical bodies of 10 lines or more): 7 pairs. The only one that matters is `_load_countries_config` in `data_acquisition/local_layers.py` and `fetchers/hydrosheds.py` (18 lines); the rest are `core/paths.py` helpers, two loaders in `config_loader.py` and report rows.

**Dead code** (vulture): 5 unused variables at 100% confidence (`core/raster_io.py:147`, `era5.py:275,284`, `lcoe_modeling/connection.py:161`); of 108 unused callables at 60%, 78 are used by tests or scripts, and of the other 30 about 25 are pydantic validators (false positives); the real candidates are `land_eligibility/pipeline.py::_pixel_raster`, `overview/style.py::draw_backdrop` and `draw_overlay`, and `era5.py::_start_state` and `_posttask`. `overview/style.py` is also the least covered module (31%).

**Config keys no phase reads:** none in `settings.yaml`; in `experiments.yaml` 15 keys are named nowhere in the code outside the schema, 14 of them level labels of the land-availability scenarios and `D-F4-018` (documentation), and `prim.box_choice` is the one that may be unread; in `audit.yaml` `derived_ranges.air_density.tolerance_justification` (documentation).

**Phase contract** (the 19 `PhaseSpec` of `_build_phase_specs`). Uniform: every phase declares `requires`, `produces`, a `summarize`, a config fingerprint and a code fingerprint, and writes a manifest entry with wall, CPU, peak, both fingerprints and (since 2.10) the environment. Exceptions: only `data_acquisition` and `data_quality_audit` declare `produces_schema_versions`; only `robustness_analysis` has optional products (80); the memory is recorded but not enforced per phase (the 1,536 MB cap is applied inside F3 and by the per-layer processes); only 12 of the 19 phases have an entry in the real manifests (F6 to F8 and the support phases have not run on PRT, IND or BRA).

**Orchestrator against METHODOLOGY** (A-01, A-02, A-03, A-12). The flow matches A-01 to A-03 (DAG validated at start, topological order, `rerun_phases` exact, downstream marked stale). Divergences: (1) A-02 describes manifest schemas up to 2.8; 2.9 (`config_rebaselines`) and 2.10 (`environment`) are not in it, and neither are the pre-phase country guard (COMMAND 126), the scope recorder or the rebaseline script; the METHODOLOGY version (19.0.1) was not raised for COMMANDS 126 to 129; (2) A-12 says reruns "reproduce identical artifacts on the same platform", which is false for parquet bytes across pyarrow versions (OQ-084); (3) A-01 says the import order is enforced, and it is, for packages only (cycle above); (4) the reference store publishes at the end of the run, before any content comparison (OQ-080).

**Type coverage** (mypy 2.4.1, `--ignore-missing-imports`): `src` and `main.py` 340 errors in 54 of 198 files; `core` and `config_models` 21 errors in 6 files (mostly `Optional` narrowing); 380 of 394 functions of `core` are fully annotated. No type check runs in CI.

---

## C. Tests

Measured by one run of the whole suite under coverage with one context per test function (2,507 passed, 1 skipped, 55 min, 3,301 s of test time; plain run 41 min). Line coverage of `src`: 95% (22,570 statements, 1,173 missed; branch coverage not measured). "Unique lines" is the number of source lines that only that file covers: it is the loss of coverage if the file goes (an exact "total minus without it" for 162 files would need 162 full runs). Type is a heuristic on name and content; references are the D-, L- and OQ- identifiers and the words V-01 and ZZZ found in the file text.

Counts by type (files / seconds): unit 143 / 1,817; synthetic ZZZ 3 / 1,174; equivalence oracle against old code 12 / 126; golden 2 / 113; V-01 frozen 1 / 29; one-off proof 1 / 1.

Findings:
- 39 files have no unique line; 10 of them carry a D-, L- or OQ- reference or are the V-01 or ZZZ tests, and stay. The other 29 are the first place to look for merging, because they protect no line by themselves.
- Files of 6 tests or fewer: 40. Natural merges: the three `test_grid_alignment_*` files (reference grid, reference-grid artifact, schemas).
- The 12 equivalence oracles (the old function kept in the test: `test_f5_memory_equivalence`, `test_land_eligibility_stripes`, and the like) all have unique lines or a reference, so none is proposed for archiving as a proof; the rule used: archive only when the file is an oracle or a one-off proof, adds no unique line and cites no D-, L- or OQ-. No file meets it today.
- Slow files that are not synthetic and not a decision: `test_robustness_pipeline.py` (210 s, 43 tests, cites D-F7-023, D-F7-064, OQ-001: it protects decisions, so it stays in the suite and is only a candidate for the nightly run if the CI budget demands it), `test_memory_budget.py` (191 s, 2 tests), `test_absolute_maps.py` (104 s). Proposed class "manual or nightly": the first two only if the suite time is reduced by `-n` first (section E).
- Never proposed for removal: anything that cites a D-, L- or OQ-, `tests/regression/test_v01_frozen.py`, the three synthetic ZZZ files.

Per-file inventory (action: keep, archive as proof, merge, nightly):

| file | tests | s | type | references | unique lines | action |
|---|---:|---:|---|---|---:|---|
| regression/test_v01_frozen.py | 2 | 29 | congelado (V-01) |  | 0 | manter |
| synthetic/test_deferred_check_zzz.py | 1 | 118 | sintético (ZZZ) | D-core-050 | 256 | manter |
| synthetic/test_zzz2_end_to_end.py | 14 | 293 | sintético (ZZZ) | D-F3-025,D-F5-029 | 0 | manter |
| synthetic/test_zzz_end_to_end.py | 115 | 763 | sintético (ZZZ) | D-F3-012,D-F3-013,L-021,OQ-050,OQ-051 | 1390 | manter |
| unit/test_absolute_maps.py | 18 | 104 | unitário | D-F5-029 | 366 | manter (cita D-F5-029) |
| unit/test_acquire_era5_gust.py | 13 | 2 | oráculo de equivalência | D-F1-018,D-core-016,OQ-038 | 1 | manter |
| unit/test_acquisition_area.py | 13 | 2 | unitário |  | 70 | manter |
| unit/test_adopt_aligned_cache_keys.py | 13 | 26 | unitário | D-F2a-028 | 1 | manter |
| unit/test_affected_tests.py | 3 | 1 | unitário |  | 1 | manter |
| unit/test_artifact_json.py | 4 | 0 | unitário |  | 2 | manter |
| unit/test_atomic_io.py | 15 | 29 | unitário |  | 9 | manter |
| unit/test_audit.py | 16 | 6 | unitário |  | 26 | manter |
| unit/test_audit_slope_canopy_99.py | 1 | 0 | unitário |  | 0 | manter |
| unit/test_cache_integrity.py | 11 | 2 | unitário |  | 160 | manter |
| unit/test_cache_key.py | 16 | 3 | unitário | D-F2a-021,OQ-026 | 0 | manter |
| unit/test_cf_table.py | 13 | 54 | unitário | D-F5-039 | 51 | manter |
| unit/test_charts.py | 2 | 0 | unitário |  | 0 | manter |
| unit/test_checkpoint.py | 32 | 9 | unitário |  | 62 | manter |
| unit/test_checkpoint_f7.py | 8 | 10 | unitário |  | 26 | manter |
| unit/test_climate_forcing_change_factors.py | 12 | 1 | unitário |  | 5 | manter |
| unit/test_climate_forcing_external_inputs.py | 4 | 0 | unitário |  | 18 | manter |
| unit/test_climate_forcing_figures.py | 11 | 40 | unitário |  | 1 | manter |
| unit/test_climate_forcing_forcing.py | 13 | 35 | unitário |  | 9 | manter |
| unit/test_climate_forcing_hazards.py | 13 | 13 | unitário |  | 4 | manter |
| unit/test_climate_forcing_qc.py | 2 | 1 | unitário |  | 0 | manter |
| unit/test_cmip6_registry.py | 7 | 0 | unitário |  | 13 | manter |
| unit/test_code_fingerprint.py | 15 | 56 | unitário |  | 40 | manter |
| unit/test_code_fingerprint_f5_split.py | 4 | 23 | unitário |  | 0 | manter |
| unit/test_config_fingerprint.py | 17 | 24 | unitário |  | 13 | manter |
| unit/test_config_loader.py | 3 | 0 | unitário | D-core-001,D-core-018,OQ-032 | 2 | manter |
| unit/test_config_rebaseline.py | 16 | 18 | congelado (golden) |  | 102 | manter |
| unit/test_config_trace.py | 13 | 1 | unitário |  | 0 | manter |
| unit/test_content_hash.py | 9 | 1 | unitário |  | 9 | manter |
| unit/test_core_constants.py | 3 | 0 | unitário |  | 0 | manter |
| unit/test_core_downloads.py | 1 | 0 | unitário |  | 5 | manter |
| unit/test_core_geodesy.py | 9 | 0 | unitário |  | 0 | manter |
| unit/test_core_memory_guard.py | 13 | 1 | unitário |  | 50 | manter |
| unit/test_core_peak_memory.py | 5 | 0 | unitário |  | 0 | manter |
| unit/test_core_power.py | 8 | 0 | unitário | D-core-027 | 4 | manter |
| unit/test_core_raster_io.py | 10 | 0 | unitário |  | 5 | manter |
| unit/test_core_run_logging.py | 8 | 0 | unitário |  | 19 | manter |
| unit/test_core_tables.py | 3 | 0 | unitário |  | 4 | manter |
| unit/test_country_config_guard.py | 25 | 5 | unitário |  | 37 | manter |
| unit/test_cross_country.py | 6 | 2 | unitário | D-F7-049,OQ-050 | 6 | manter |
| unit/test_data_acquisition_adapter.py | 16 | 0 | unitário |  | 9 | manter |
| unit/test_data_acquisition_local_layers.py | 21 | 0 | unitário |  | 15 | manter |
| unit/test_data_acquisition_phase.py | 36 | 7 | unitário | D-F2a-021,D-core-016,OQ-024,OQ-062 | 35 | manter |
| unit/test_data_acquisition_schemas.py | 24 | 0 | unitário |  | 2 | manter |
| unit/test_data_selfcontained.py | 4 | 0 | unitário |  | 5 | manter |
| unit/test_deferred_check.py | 26 | 4 | unitário | D-core-050 | 43 | manter |
| unit/test_density_check.py | 10 | 0 | unitário |  | 0 | manter |
| unit/test_display_resolution.py | 48 | 50 | unitário | D-F5-038 | 24 | manter |
| unit/test_elevation_cap.py | 3 | 0 | unitário | OQ-058 | 1 | manter |
| unit/test_env_loading.py | 2 | 0 | unitário |  | 0 | manter |
| unit/test_equivalence_and_clipped_cache.py | 11 | 1 | prova pontual |  | 13 | manter |
| unit/test_era5_dask_scheduler.py | 3 | 1 | unitário |  | 34 | manter |
| unit/test_external_validation.py | 17 | 3 | unitário |  | 171 | manter |
| unit/test_f5_member_codes.py | 19 | 8 | oráculo de equivalência |  | 5 | manter |
| unit/test_f5_memory_equivalence.py | 22 | 28 | oráculo de equivalência |  | 17 | manter |
| unit/test_f6_parameters.py | 7 | 0 | unitário | D-F6-009,D-F6-014,OQ-001,OQ-066 | 0 | manter |
| unit/test_f7_parameters.py | 13 | 3 | unitário | D-F7-029,OQ-010,OQ-050 | 8 | manter |
| unit/test_fabdem_slope_layer.py | 14 | 15 | unitário | D-F2a-028 | 155 | manter |
| unit/test_fetchers_cmip6.py | 14 | 4 | unitário |  | 130 | manter |
| unit/test_fetchers_era5.py | 17 | 24 | unitário | OQ-078 | 127 | manter |
| unit/test_fetchers_gadm.py | 22 | 1 | unitário | OQ-039 | 143 | manter |
| unit/test_fetchers_hydrosheds.py | 11 | 0 | unitário |  | 51 | manter |
| unit/test_fetchers_protected_planet.py | 13 | 0 | unitário |  | 64 | manter |
| unit/test_fetchers_wind.py | 18 | 1 | unitário | OQ-062 | 189 | manter |
| unit/test_figures_setting.py | 2 | 60 | unitário |  | 95 | manter |
| unit/test_fingerprint_algorithm.py | 10 | 11 | unitário | OQ-077 | 0 | manter |
| unit/test_fingerprint_exempt_registry.py | 7 | 0 | unitário |  | 0 | manter |
| unit/test_fingerprint_granularity.py | 11 | 63 | unitário |  | 2 | manter |
| unit/test_function_fingerprint.py | 8 | 28 | unitário | D-F2a-028 | 1 | manter |
| unit/test_gcm_selection_spread.py | 2 | 0 | unitário |  | 0 | manter |
| unit/test_gem_trackers.py | 5 | 1 | unitário | D-F7b-005 | 18 | manter |
| unit/test_geo_utils.py | 35 | 7 | unitário |  | 18 | manter |
| unit/test_grid_alignment_adapter.py | 8 | 0 | unitário |  | 0 | manter |
| unit/test_grid_alignment_alignment.py | 30 | 8 | unitário | D-F2a-028,OQ-026,OQ-040 | 44 | manter |
| unit/test_grid_alignment_poi.py | 27 | 1 | unitário |  | 39 | manter |
| unit/test_grid_alignment_raster_alignment.py | 32 | 17 | unitário |  | 70 | manter |
| unit/test_grid_alignment_reference_grid.py | 5 | 0 | unitário |  | 0 | manter |
| unit/test_grid_alignment_reference_grid_artifact.py | 2 | 0 | unitário |  | 0 | manter |
| unit/test_grid_alignment_schemas.py | 6 | 0 | unitário | D-F2a-021 | 0 | manter |
| unit/test_grid_alignment_slope_derivation.py | 8 | 1 | unitário |  | 45 | manter |
| unit/test_grid_alignment_vector_alignment.py | 40 | 4 | unitário | OQ-040 | 63 | manter |
| unit/test_groups12_parameters.py | 41 | 2 | unitário | D-F6-010 | 3 | manter |
| unit/test_h1_rank_robustness.py | 16 | 0 | unitário |  | 5 | manter |
| unit/test_h2_aggregation.py | 11 | 0 | unitário |  | 4 | manter |
| unit/test_h3_robust_vs_nominal.py | 10 | 0 | unitário |  | 4 | manter |
| unit/test_h4_axis_dominance.py | 12 | 0 | oráculo de equivalência |  | 2 | manter |
| unit/test_h5_climate_pressure.py | 21 | 0 | unitário | D-F7-050,D-F7-053 | 4 | manter |
| unit/test_h5_pipeline.py | 11 | 48 | unitário | D-F7-050,D-F7-053,OQ-008,OQ-050 | 12 | manter |
| unit/test_http_retry.py | 7 | 0 | unitário |  | 32 | manter |
| unit/test_import_dag.py | 3 | 2 | unitário | L-9 | 0 | manter |
| unit/test_internal_caches.py | 16 | 17 | unitário |  | 2 | manter |
| unit/test_iso3_literals.py | 1 | 4 | unitário |  | 0 | manter |
| unit/test_land_eligibility_admin1.py | 8 | 9 | unitário | D-F3-012 | 5 | manter |
| unit/test_land_eligibility_cells.py | 18 | 1 | oráculo de equivalência |  | 4 | manter |
| unit/test_land_eligibility_figures.py | 9 | 30 | unitário |  | 36 | manter |
| unit/test_land_eligibility_fractions.py | 25 | 3 | unitário | OQ-045 | 7 | manter |
| unit/test_land_eligibility_group6_values.py | 20 | 0 | unitário |  | 7 | manter |
| unit/test_land_eligibility_min_area.py | 11 | 0 | unitário |  | 1 | manter |
| unit/test_land_eligibility_pipeline.py | 34 | 28 | unitário | OQ-058,OQ-060 | 18 | manter |
| unit/test_land_eligibility_stripes.py | 14 | 50 | oráculo de equivalência |  | 28 | manter |
| unit/test_layer_process.py | 8 | 5 | unitário |  | 28 | manter |
| unit/test_lcoe_connection.py | 17 | 1 | unitário | OQ-001 | 35 | manter |
| unit/test_lcoe_kernel.py | 42 | 1 | oráculo de equivalência | D-F7-007 | 20 | manter |
| unit/test_lcoe_pipeline.py | 47 | 25 | oráculo de equivalência | D-F6-002,D-F6-005,OQ-001,OQ-058 | 72 | manter |
| unit/test_lcoe_robustness_maps.py | 12 | 41 | unitário | D-F6-015,D-F7-024 | 192 | manter |
| unit/test_lcoe_sampling.py | 5 | 0 | unitário |  | 5 | manter |
| unit/test_main.py | 29 | 21 | unitário | D-F1b-007,D-F6-004,OQ-012,OQ-058 | 0 | manter |
| unit/test_manifest_environment.py | 3 | 0 | unitário | OQ-084 | 0 | manter |
| unit/test_mapstyle.py | 54 | 64 | unitário |  | 13 | manter |
| unit/test_mapstyle_archetypes.py | 39 | 94 | congelado (golden) |  | 0 | manter |
| unit/test_mapstyle_classed.py | 23 | 11 | unitário |  | 6 | manter |
| unit/test_mapstyle_files.py | 13 | 2 | oráculo de equivalência |  | 9 | manter |
| unit/test_mapstyle_geo.py | 18 | 14 | unitário |  | 41 | manter |
| unit/test_mapstyle_palette.py | 22 | 3 | unitário |  | 16 | manter |
| unit/test_mapstyle_panels.py | 41 | 79 | unitário | OQ-12 | 15 | manter |
| unit/test_mapstyle_quiet_figure.py | 1 | 1 | unitário |  | 0 | manter |
| unit/test_mapstyle_titles.py | 34 | 7 | unitário | D-F5-031,L-047,OQ-046,OQ-049 | 14 | manter |
| unit/test_memory_budget.py | 2 | 191 | unitário |  | 1 | mover para execução manual/noturna |
| unit/test_methodology_changelog.py | 5 | 4 | unitário |  | 0 | manter |
| unit/test_no_maps_outside_mapfigure.py | 1 | 7 | unitário |  | 0 | manter |
| unit/test_orchestrator.py | 52 | 5 | oráculo de equivalência | D-F7-064,D-core-003 | 99 | manter |
| unit/test_orchestrator_manifest_write.py | 2 | 0 | unitário |  | 0 | manter |
| unit/test_overview_figures.py | 7 | 47 | unitário |  | 6 | manter |
| unit/test_parameter_contract.py | 12 | 10 | unitário | D-F5-011,L-203 | 15 | manter |
| unit/test_paths.py | 9 | 0 | unitário |  | 0 | manter |
| unit/test_prim_pipeline.py | 6 | 33 | unitário | D-F7-054,D-F7-057,OQ-021,OQ-056 | 0 | manter |
| unit/test_pv_zones.py | 22 | 2 | unitário |  | 45 | manter |
| unit/test_question_figures.py | 11 | 14 | unitário |  | 166 | manter |
| unit/test_raster_inspection.py | 56 | 3 | unitário | D-F1b-005,OQ-062 | 197 | manter |
| unit/test_reference_store.py | 14 | 2 | unitário | D-core-051 | 22 | manter |
| unit/test_report_group6_decomposition.py | 9 | 0 | unitário |  | 0 | manter |
| unit/test_results_synthesis.py | 11 | 17 | unitário |  | 8 | manter |
| unit/test_resumable_download.py | 14 | 6 | unitário |  | 89 | manter |
| unit/test_robustness_convergence.py | 13 | 10 | unitário | D-F6-004,D-F7-027,OQ-001,OQ-008 | 162 | manter |
| unit/test_robustness_evaluator.py | 13 | 1 | oráculo de equivalência |  | 7 | manter |
| unit/test_robustness_futures.py | 11 | 1 | unitário | D-F7-019,D-F7-020 | 6 | manter |
| unit/test_robustness_pipeline.py | 43 | 210 | unitário | D-F7-023,D-F7-064,OQ-001,OQ-007 | 132 | manter (candidato a noturno só se o orçamento do CI exigir) |
| unit/test_robustness_prim.py | 15 | 1 | unitário | D-F7-021 | 9 | manter |
| unit/test_robustness_rankings.py | 16 | 0 | unitário | D-F7-007,D-F7-012,OQ-069 | 11 | manter |
| unit/test_scale.py | 8 | 1 | unitário | D-F3-013,D-F4-020 | 2 | manter |
| unit/test_scenario_discovery.py | 10 | 3 | unitário | D-F7-054,D-F7-057 | 2 | manter |
| unit/test_schemas.py | 50 | 2 | unitário | D-core-018,OQ-032 | 1 | manter |
| unit/test_siting_layers_physical_layers.py | 4 | 2 | unitário |  | 1 | manter |
| unit/test_siting_sanity.py | 14 | 0 | unitário | OQ-053 | 10 | manter |
| unit/test_slope_dem_test_100.py | 7 | 3 | unitário |  | 0 | manter |
| unit/test_stamp_manifest_hashes.py | 3 | 12 | unitário |  | 0 | manter |
| unit/test_state_figures.py | 6 | 5 | unitário |  | 2 | manter |
| unit/test_status_lives_only_in_progress.py | 4 | 0 | unitário |  | 0 | manter |
| unit/test_synthesis.py | 12 | 1 | unitário |  | 7 | manter |
| unit/test_synthetic_value_separation.py | 4 | 0 | unitário | D-core-018,OQ-032 | 0 | manter |
| unit/test_technical_potential_functions.py | 49 | 2 | oráculo de equivalência | D-F5-002,D-F5-003 | 26 | manter |
| unit/test_technical_potential_maps.py | 9 | 21 | unitário | D-F5-015 | 38 | manter |
| unit/test_technical_potential_pipeline.py | 63 | 37 | unitário | D-F5-006,D-F5-009,OQ-053,OQ-058 | 49 | manter |
| unit/test_technical_potential_pixels.py | 11 | 2 | unitário | D-F5-038 | 1 | manter |
| unit/test_thesis_figures.py | 7 | 4 | unitário | D-F8-018,D-F8-019 | 5 | manter |
| unit/test_unattended_check.py | 8 | 0 | unitário |  | 0 | manter |
| unit/test_unattended_resume.py | 8 | 0 | unitário |  | 0 | manter |
| unit/test_vector_inspection.py | 22 | 4 | unitário |  | 12 | manter |


---

## D. Obsolete items (listing only, with sizes)

**Scripts** (50 files plus `profiling/` and `proofs/`): 30 name PRT, IND or BRA in code or text (class a labels in 99 of 126 occurrences, `docs/_audit/generality_audit.md`). Referenced from nowhere else in the repository (docs, src, tests, workflows, other scripts): `report_pv_zone_shares.py`, `seed_deferred_check.py`. One-country or resolved-task scripts, by name: `derive_bra_bay_cost_bpr.py`, `report_poi_counts.py`, `report_road_distance.py`, `report_group6_decomposition.py`, `audit_slope_bin_error_97.py`, `audit_slope_canopy_99.py`, `audit_slope_dem_test_100.py`, `acquire_fabdem_test_100.py`, `adopt_aligned_cache_keys.py` (COMMAND 123 adopted them), `stamp_manifest_hashes.py`, the nine `scripts/proofs/check_*` and `diagnose_clip_shortcut.py` (proofs of COMMANDS 75 to 100).

**`docs/_audit`** (87 entries, 2.5 MB): the `2026-09_*` files (16) and `2026-10_*` (17) are superseded by the phase records and are listed in the README of the folder; candidates for `docs/_archive`: `2026-09_legacy_F3-F8.md`, `2026-09_repo_cleanup.md`, `2026-10_pipeline_state.md`, `2026-10_F5_design.md` to `2026-10_F8_design.md`, `cleanup_72.md`, `cleanup_82.md`, `dist_scale_prototype.md`, `awaiting_content_check_post_77.md`. `docs/_archive` is 549 KB.

**Docstrings out of date** (COMMAND 125, item 10, still true): `data_acquisition/local_layers.py` (lines 44, 45, 47, 77, 100) and `fetchers/hydrosheds.py` (line 26) and `phase.py:141` describe the tables `_ELEVATION_COUNTRY_DIRS`, `_LAND_COVER_COUNTRY_DIRS`, `_ROADS_COUNTRY_REGION_DIRS` and `_COUNTRY_TO_REGION`, which no longer exist; `viz/examples.py:86` reads `tests/fixtures/archetypes` from `src`. No `TODO`, `FIXME` or `HACK` in `src`; 39 `noqa` and 4 `type: ignore`.

**Branches.** Merged and still present (local and remote): `ast-normalize`, `ci-env-pins`, `ci-linux-fix`, `config-scope-fix`, `country-config-guard`, `f5-memory`, `feat/83-group3-connection-degradation`. Local only, not merged: `backup-before-split` (2026-10-06), `feat/cache-restamp` (2026-10-22). Worktrees on disk: `GeoFREA_cswt`, `GeoFREA_envwt`, `GeoFREA_f5wt` (all merged).

**Workflows** (3): `unit`, `synthetic_fixture` and `regression` all run on push, pull request and dispatch, so a branch with an open pull request runs each twice; `regression` takes about 1 min and runs on every push. None is redundant in content.

**PROGRESS.json**: `last_updated` 2026-11-09, `methodology_version` 19.0.0 (the METHODOLOGY says 19.0.1); `current_milestone` MS-6; milestones MS-6 to MS-11 `in_progress`; phases F2a, F5, F6, F7, F7b, F8 `conformant`, F2b `ran_clean`, the others `built_pending_conformance`, E1 `not_started`. It does not mention COMMANDS 120 to 129. Closed OQ still cited in L rows: OQ-001 (6 rows), OQ-058, OQ-060, OQ-053, OQ-047, OQ-042 (resolved in `OPEN_QUESTIONS.md`).

**`GeoFREA_data`** (by directory):

| directory | size | note |
|---|---:|---|
| `raw` | 106 GB | `copernicus_dem30` 47, `gwa` 16, `land_cover` 6.5, `esa_worldcover` 6.5, `era5` 6.1, `isimip3b` 6.0 |
| `external` | 25 GB | `fabdem` 25 (1,195 tiles) |
| `work` | 7.1 GB | `pre116` 5.2, `snapshot_129` 1.9 (made by COMMAND 129), `val117_BRA` 0.04 |
| `cache` | 6.8 GB | `clipped` 7.2 |
| `outputs` | 5.4 GB | BRA 3.8, IND 1.6, PRT 0.11 |
| `interim` | 3.8 GB | BRA 2.2, IND 1.4, PRT 0.13, `_mainland_cache` 0.08 |
| `references` | 3.5 GB | 10 rounds (hard links; `1d34ab23` is `latest`), `objects` 0.76 |
| `backup_before_89`, `_f3_new_BRA`, `_f3_cold_BRA`, `_f3_97_BRA`, `_f3_profile_BRA`, `backup_before_91` | 7.7 GB | drafts and backups of COMMANDS 89 to 97 |

Files of `outputs/<ISO>` and `interim/<ISO>` that the current manifest does not register (these include working files and figures that are not artifacts, so "not referenced" is not "obsolete"): PRT 0.2 of 0.25 GB; IND 1.9 of 3.1 GB (`interim/land_eligibility` 0.86); BRA 3.1 of 6.3 GB (`interim/land_eligibility` 1.6, `outputs/technical_potential` 0.44, `interim/data_quality_audit` 0.39). The OQ-083 sidecars (6 clip `.key` per country and the unregistered GLO30 slope layers) are inside these. The stray `interim/_code_digest_cache.json.13848.tmp` (336 KB) is a leftover of a stopped process.

---

## E. Time and cost

**Per phase and country** (manifests; seconds of the cold execution and peak MB; F6 to F8 have no real execution):

| phase | PRT | IND | BRA |
|---|---|---|---|
| data_acquisition | 19 s, 322 | 422 s, 1,004 | 272 s, 782 |
| data_quality_audit | 23, 535 | 142, 1,186 | 160, 1,152 |
| grid_alignment | 40, 283 | 246, 360 | 604, 437 |
| climate_forcing | 88, 281 | 121, 488 | 129, 565 |
| climate_maps | 29, 645 | 82, 1,501 | 58, 2,333 |
| hazard_context | 31, 931 | 119, 2,003 | 171, 2,728 |
| siting_layers | 40, 274 | 62, 275 | 99, 272 |
| external_inputs | 1, 250 | 1, 311 | 0, 303 |
| overview | 15, 743 | 39, 1,568 | 35, 2,041 |
| land_eligibility | 29, 347 | 190, 864 | 602, 1,481 |
| technical_potential | 9, 338 | 74, 1,018 | 218, 1,579 |
| potential_maps | 12, 657 | 27, 1,207 | 47, 1,676 |
| **sum / highest peak** | **335 s, 931** | **1,525 s, 2,003** | **2,395 s, 2,728** |

**Suite and CI.** Whole suite 2,507 tests: 41 min 14 s plain (COMMAND 128), 55 min under coverage; unit suite 27 min 19 s (2,302 tests, COMMAND 127). CI on `main`: unit 533 to 596 s per run (two Python versions in parallel), synthetic 297 to 347 s, regression 48 to 67 s.

**The five largest consumers** and the lever for each (estimates by arithmetic, not measured; the constraint is the 6 GB of RAM and bit-for-bit equality unless a tolerance is declared):

| # | consumer | lever | constraint | estimate |
|---|---|---|---|---|
| 1 | `grid_alignment`, 890 s in three countries (BRA 604 s) | run the independent distance layers (grid, roads, rivers, lakes, substations) in parallel processes (`core/layer_process.py` already isolates them) | each layer process stays under the cap; layers are pixel-wise independent, so bit-equal | if the layers are 70% of the time and 3 run at once: BRA 604 -> about 300 s, all countries about 890 -> 450 s. The share is not measured: time the layers first. Fingerprint: `grid_alignment` only. |
| 2 | `land_eligibility`, 821 s (BRA 602 s) | run the row stripes (`windows.py`) in 2 to 3 processes | 1,536 MB per stripe process: 3 x 1.5 = 4.5 GB, tight with 6 GB | with 20% serial: BRA 602 -> about 280 s (3 workers) or 360 s (2). Bit-equal (per-cell sums). Fingerprint: `land_eligibility`, `external_validation`. |
| 3 | `data_acquisition`, 713 s (IND 422 s) | reuse the SHA-256 of a large file when size and mtime are unchanged (the orchestrator already does it for artifacts), and skip re-clipping on a current cache key | none on values | not decomposed in the manifest: profile per layer first. If hashing is half of it, about 350 s saved. Fingerprint: `data_acquisition`. |
| 4 | the test suite, 41 min (CI unit 9.5 min) | `pytest-xdist` (already in the dev dependencies) with `-n 3`; keep the module-scoped ZZZ fixture in one worker | RAM: the ZZZ fixture and the BRA-sized synthetic tests; a test that writes a shared path must be isolated | 41 -> about 15 to 17 min locally; CI unit 9.5 -> about 4 to 5 min on 4 cores. No fingerprint. |
| 5 | BRA memory: `hazard_context` 2,728 MB, `climate_maps` 2,333, `overview` 2,041 (above the 1,536 MB cap used for F3 and F5; the 6 GB machine is not at risk) | read by row windows and release between technologies, as done for F5 (item a, b, d); dtype float32 only with a declared tolerance | windows keep bit equality; float32 does not | windows alone: F5 went from 3,410 to 1,579 MB (-54%) with the same method; for these three phases a similar cut would give about 1.2 to 1.5 GB, unmeasured. Fingerprint: the phase and its dependents (see G). |

Also worth knowing: F5 of BRA is now 1,579 MB, 43 MB above the cap, and `potential_maps` of BRA 1,676 MB.

---

## F. Reproducibility

**Clean clone, README steps, new directory** (`git clone` of `main` at `e0b2cbf`, new venv, Python 3.11.9, scratch data directory):

| step | result |
|---|---|
| `git clone` | works |
| `pip install -e ".[dev]"` (README step 2) | works, but installs unpinned versions: pandas 3.1.1, pyarrow 26.0.1, geopandas 1.2.0 (the version OQ-074 says breaks 52 figure tests), numpy 2.4.6, rasterio 1.4.4. The README does not use `-c ci/constraints.txt`, so a clean clone is not the CI environment. |
| copy `.env.example` to `.env`, set `GEOFREA_DATA_DIR` | works |
| ZZZ fixture | **fails**: `scripts/generate_zzz_fixture.py` raises `KeyError: 'GEOFREA_DATA_DIR'` because it reads `os.environ` and ignores `.env`; the README does not mention the generator or ZZZ at all. With the variable exported it works. |
| `python main.py ZZZ` (default phases) | 8 phases succeed (data_acquisition, data_quality_audit, external_inputs, grid_alignment, climate_forcing, hazard_context, siting_layers, land_eligibility, in about 3 min); **`climate_maps` and `overview` fail**: "no name for 'ZZZ': give `country=` or add it to COUNTRY_NAMES". |
| `--phases technical_potential,lcoe_modeling,sample_size_convergence` | F5 and F6 succeed; **`sample_size_convergence` fails**: `sampler.max_size_for_convergence` is null (the author's ceiling, D-F6-004). F7 and later cannot be reached from the README; only `pytest tests/synthetic` does it (it copies `experiments.yaml` with test values and a synthetic power curve), which is what the CI job does. |
| README step 4, `pytest` | not run in the clone (41 min); the CI job runs it on 3.11 and 3.12 with the pins. |

So: one command sequence gets a clean clone to F5/F6 of ZZZ with two missing steps; to F8 only through the test suite.

**Provenance and checksums.** The layer registry of each real country has 22 layers (17 fetched, 5 `local_only`), all with a recorded `source_sha256`; `config/countries.yaml` pins the GADM level-0 checksum of PRT, IND and BRA; the synthetic country has none by design. Not checked here: checksums of `external/` (FABDEM 25 GB, GHSL, EPE, VTH, OSM substations, PVCZ), which are placed by hand. `docs/data/` has two files (`grid_provenance.md` with source, version and licence of the grid: CC BY 4.0 for the Zenodo record, ODbL for the OSM lines; `coverage_audit_59.md`). The only open licence question is OQ-072 (FABDEM, CC BY-NC-SA 4.0); no table of the licences of the other sources (GADM, ERA5, CMIP6, ISIMIP3b, GWA, ESA WorldCover, Copernicus DEM, GHSL, WDPA) exists in the repository: that is a gap to fill before any publication.

---

## G. Single-window plan

Which modules sit in which phase closures was computed with `closure_modules` (19 phases). A change to a module changes the code fingerprint of every phase that contains it, and that phase runs again at the next round; downstream phases only run again if the content hash of an input changed.

| change | modules | phases whose fingerprint changes | cold cost, 3 countries |
|---|---|---|---:|
| Greenwich in the forcing (section 3 of COMMAND 127) | `climate_forcing/forcing.py`, `change_factors.py` | climate_forcing, hazard_context, climate_maps, technical_potential, lcoe_modeling, sample_size_convergence, robustness_analysis | 19 min |
| the same, F1 crop | `data_acquisition/fetchers/cmip6.py` | data_acquisition | 12 min (713 s) |
| ERA5 `spawn` (OQ-078) | `data_acquisition/fetchers/era5.py` | data_acquisition | (same) |
| F5 memory floor (retained pixels between scenarios) | `technical_potential/pipeline.py`, `pixel_inputs.py`, `cf_table.py` | technical_potential, lcoe_modeling, sample_size_convergence, robustness_analysis, potential_maps | 6 min |
| F3 stripes in parallel, `_pixel_raster` removal | `land_eligibility/pipeline.py`, `windows.py` | land_eligibility, external_validation | 14 min |
| F2a layers in parallel | `grid_alignment/*` | grid_alignment | 15 min |
| lint forms of OQ-073 | `core/raster_io.py` (9 phases), `technical_potential/cf_table.py` (5), a F3 function (2) | the union of those | up to 52 min if `raster_io` is touched |
| mapstyle refactors | `viz/mapstyle.py` | 10 phases | 30 min |
| `core/geo_utils.py`, `core/tables.py`, `core/paths.py` | | 14, 10 and all 19 phases | 63 min, 52 min, all: avoid |
| `main.py` refactors (`_build_phase_specs`, `_main`) | outside every closure | none | 0 |
| docs, tests, scripts, `README`, `config_rebaseline`, orchestrator, `code_fingerprint`, `config_fingerprint`, `content_hash` (infrastructure modules) | outside the closures | none | 0 |

Config changes act on the config fingerprint instead: the two scopes closed in COMMAND 128 changed 12 entries (6 rebaselined by proof, 6 run again anyway).

**One clean round after all of the above:** the union touches data_acquisition, climate_forcing, hazard_context, climate_maps, technical_potential, potential_maps, land_eligibility, grid_alignment and, through the closures, lcoe_modeling, sample_size_convergence, robustness_analysis, external_validation: 12 of the 19 phases. If the window includes `core` modules all 12 phases that have run on real data rerun; without them (the list above minus the `core/*` and `viz` rows) the rerun is data_acquisition, grid_alignment, climate_forcing, hazard_context, climate_maps, land_eligibility, technical_potential, potential_maps: 3,638 s summed from the manifests, about **61 min** for the three countries (PRT 4.3, IND 21, BRA 35); with everything in the window, the cost of the whole chain is **71 min** (4,255 s). F6 to F8 have not run on real data, so their share is unknown and is added when Groups 4, 5 and 7 are ready; planning the window after those groups, instead of before, avoids a second round for them.

Order inside the window, to keep the proofs cheap: (1) the changes that keep bit equality, each with its own equivalence test on PRT; (2) Greenwich last, since it is the only one that cannot be proved against the old output on the three countries (none crosses 0 degrees), only on ZZZ3b; (3) one round, one comparison against the COMMAND 129 snapshot with the three levels of equality.

---

## Recommendations by return on effort

1. **Fix the README** (`pip install -c ci/constraints.txt -e ".[dev]"`, how to run ZZZ, the fixture generator reading `.env`): minutes, no fingerprint, removes the geopandas 1.2.0 trap of a clean clone.
2. **Add ZZZ to `country_names.yaml`** and say in the README that F6 onwards runs through `pytest tests/synthetic`: minutes, makes `climate_maps` and `overview` run on ZZZ.
3. **`pytest -n 3` in CI and locally**: one line; suite 41 -> about 16 min, CI unit 9.5 -> about 4.5 min.
4. **Bring METHODOLOGY A-02, A-12 and PROGRESS.json up to date** (manifest 2.9 and 2.10, guard, scope recorder, `last_updated`, version 19.0.1): an hour of text, no fingerprint.
5. **Clean `GeoFREA_data/`** after the author reads section D: 7.7 GB of drafts and backups plus `work/pre116` 5.2 GB, listed, none touched; and the OQ-083 sidecars.
6. **Decide OQ-084**: the logical-type content hash removes the false "stale" on two F5 files and lets a pyarrow update stop being an event.
7. **Resolve OQ-078** (spawn context) and **OQ-079** (DC basis, text only): a line each; the first changes `data_acquisition` and goes into the window.
8. **Profile `data_acquisition` and the layers of `grid_alignment` per step** before touching them: 713 s and 890 s are the two largest times of the real countries and neither is decomposed in the manifest.
9. **Run the layers of `grid_alignment` and the stripes of `land_eligibility` in parallel**: about 1,700 s -> about 800 s over the three countries, bit-equal, two phases rerun.
10. **Delete the 6 dead callables and 5 variables, fix the 5 stale docstrings, merge the 29 test files that cover nothing alone**: a half day, small fingerprint cost (`_pixel_raster` touches F3 and F7b only), best done inside the window of section G.
