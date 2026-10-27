# General audit of the pipeline before Group 3 (COMMAND 71, 2026-10-27)

Read-only audit of the repository (`D:\Douglas\DOUTORADO\GeoFREA`, main at `e2dae55`), of `GeoFREA_data` and of `database\raw`. Nothing was changed except this file. Every statement carries its evidence (file:line, command or count). Severity: **P0** result possibly wrong; **P1** inconsistency or risk; **P2** cleanup or optimization. "Verdict" = the finding needs a decision of the author before anything is done.

How the evidence was gathered (limits stated once, here):

- Static analysis of `src/` (148 modules, 45,450 lines), `tests/` (119 files), `scripts/` (34), `config/`, `docs/` (178 tracked files). Dead code by `vulture` 2.16 at confidence 60, then each candidate searched in `src/`, `tests/`, `scripts/` and `main.py`.
- Specification traceability by ID tag (`M-`, `A-`, `U-`, `V-`) found in `src/`, `scripts/`, `config/` and `tests/`. A missing tag is a **traceability** gap, not proof of a missing implementation; where the text of the item shows it is implemented under another label, the table says so.
- Run facts from the three manifests (`outputs/<ISO>/manifest.json`, schema 2.6) and from `GeoFREA_data/logs/<ISO>/*.log`. The pipeline records wall and CPU time per phase. **It does not record peak memory anywhere** (finding R71-08): peak memory below is only the measured sizing of F5 to F8 at BRA size recorded in the phase records (D-F5-022, D-F6-020, D-F7-063, D-F7b-007, D-F8-025).
- Disk figures come from `du` and `os.stat`; duplicates were searched by size, then by SHA-256 of the first and last MB, over all 3,816 files of `GeoFREA_data` (112.4 GB).
- Large rasters were not loaded. The wind bias check (section G) reads 5 x 5 pixel windows per cell.
- The full test suite was run once, sequentially, in this session (result in section C.5). Sizes are binary (MiB, GiB) unless bytes are quoted; the tarball is 363 MiB = 380,498,564 bytes.

---

## 0. Summary (one page)

**State.** F1, F1b, F2a, F2b, F3, F4, hazard_context, overview, F5 and potential_maps are built and ran in PRT, IND and BRA with `success` in all three manifests (last runs 2026-10-21 to 2026-10-27). F6, F7, F7b and F8 are built and tested on the synthetic countries ZZZ and ZZZ2 only; they have **never run on real data** and are blocked by 7 null parameters per country and technology (`degradation_rate`, `grid_cost_usd_per_mw_km`, `substation_cost_usd_per_mw`, `road_cost_usd_per_km` for F6; `cf_min`, `tau_lcoe_usd_per_mwh`, `top_k_percent` for F7), by OQ-010, OQ-051, OQ-057 and by the missing F6 and F7 real inputs. E1 (platform) is `not_started`. Suite: 1,849 passed and 1 failed (MemoryError) in the COMMAND 70 run; **1,850 passed, 0 failed in 28 min 00 s in this session** (peak working set of the process tree 2.23 GB, measured with `psutil`).

**P0 (result possibly wrong): none found.** The closest candidate is R71-01: the F5 wind capacity factor of a cell, computed on the eligible-area-weighted *mean* of A, k and air density (M-F5-03, L-004), is lower than the mean of the 0.01 degree pixel capacity factors. Measured: PRT (all 3,500 wind cells) median -0.003%, P5 -0.24%, P95 +0.26%, national energy +0.0006%; IND (2,000 of 61,464 cells) median -0.013%, P5 -1.53%, 6.5% of cells beyond -1%, maximum 21.6%, energy -0.024% (95% interval -0.028 to -0.020); BRA (2,000 of 181,306 cells) median -0.16%, P5 -1.13%, 6.6% beyond -1%, maximum 10.5%, energy -0.13% (-0.15 to -0.11). The national totals are safe; individual cells in rugged terrain are not, and F7 ranks cells. L-004 calls the error "second order": true for the median, false in the tail. It needs the author's verdict (keep and declare the numbers, or aggregate pixel capacity factors).

**P1 (the ones that matter before Group 3):**

| ID | Finding | Verdict |
|---|---|---|
| R71-01 | Wind CF at cell-mean Weibull parameters: tail bias in IND/BRA (above) | yes |
| R71-02 | `docs/DECISIONS.md` and `docs/architecture/*` are cited 201 times in 48 files (42 in `src/`, `tests/`, `main.py`, `config/`) but do not exist since commit `2726333` | no |
| R71-03 | `README.md` still describes a 9-phase legacy port, `GEOWORLD_BASELINE_DIR` and regression "against frozen legacy baselines" | no |
| R71-04 | `PROGRESS.json` is stale in 4 places (MS-4 held open by closed OQ-053; F3 summary quotes IND 4.9/17.2% against 4.8/16.2% now; regression note says `GeoFREA_data/reference` exists, it does not; A-07 note says rasters are not COG, they are) | MS-4 closure: yes |
| R71-05 | `docs/phases/F5/run_real_hashes.json`: 11 of 24 PRT files differ by bytes (totals identical); byte hashes of Parquet are fragile | no |
| R71-06 | The code fingerprint of F5 includes the figure modules (55 modules), and at HEAD five phases of all three countries carry an older fingerprint: the next run re-executes climate_maps, hazard_context, overview, F5 and potential_maps (BRA: about 25 min). PRT manifest is `dirty: true` | no |
| R71-07 | F2b and F3 outputs (12 and 23 files; BRA 401 MB and 351 MB) are not registered file by file in the manifest, so the canonical content hash of D-core-042 does not cover them | yes |
| R71-08 | Peak memory is not recorded by the pipeline; the requested memory column cannot be filled for F1 to F4 | no |
| R71-09 | `test_no_legacy_opex_names` walks the whole repository folder, including the 363 MiB `regression-fixtures.tar.gz`: the MemoryError of COMMAND 70 (passes when memory is free: 20.6 s here) | no |
| R71-10 to R71-14 | Documentation hygiene: OQ table (OQ-048 resolved but listed; non-standard statuses), retired L- IDs cited as live, two formats of D- records, 6 METHODOLOGY items with no tag anywhere, state sentences in config comments | no |

**P2 (cleanup and optimization)**: 10 bottlenecks with proposals (section D), about 2.1 GB recoverable (0.5 GB of data and 0.47 GB of repository folder without any scientific decision; section F.5 and the final list), 5 worktrees and 23 branches to retire, 6 dead symbols plus 8 only used by tests, 11 one-shot scripts.

**Author's verdicts requested (consolidated):** R71-01 (wind CF at pixel or cell), R71-04 (close MS-4), R71-07 (hash coverage of F2b/F3), the 1% display tolerance of COMMAND 70 (same subject as R71-01), and the cleanup list of section "Proposed cleanup actions" (nothing executed).

---

## A. State of the pipeline, phase by phase

Times are wall seconds of the **last** run recorded in the manifest (`phases.<name>.wall_s`); the cold cost, where a cache made the last run short, is in section D. Peak memory: "n/r" = not recorded. Tests: the suite has 1,466 test functions in 119 files (1,393 unit, 71 synthetic, 2 regression), 1,850 collected items; per-phase counts are approximate (by file name).

| Phase | Built | Conforms (PROGRESS, `docs/PROGRESS.json`) | Tests (ZZZ / ZZZ2) | Real run PRT / IND / BRA (last run; wall s; peak memory) | Produces (per country) | Blocked by |
|---|---|---|---|---|---|---|
| F1 `data_acquisition` | yes | built_pending_conformance | about 216 unit; ZZZ end to end | ran_clean x3; 2026-10-21; 168 / 1,004 / 647 s; n/r | layer registry (22 layers), raw layers under `raw/` | nothing; OQ-011 and OQ-063 (grid source) open |
| F1b `data_quality_audit` | yes | built_pending_conformance | about 80 | ran_clean x3; 2026-10-21/22; 237 / 4,096 / 3,861 s; n/r | `audit_report.json`, `audit/*.txt` (22 / 17 / 23 files), interim cache | nothing |
| F2a `grid_alignment` | yes | conformant | about 134; V-01 frozen on ZZZ | ran_clean x3; 2026-10-21/22; 355 / 9,678 / 42,176 s (cold) ; n/r | 26 rasters at 0.01 degree (PRT 14 MB, IND 367 MB, BRA 952 MB) | nothing |
| F2b `siting_layers` | yes | in_progress (R71-04) | about 20 + sanity tests | ran_clean x3; 2026-10-21/22; 3 / 24 / 58 s | 12 physical-unit layers (5.3 / 146.5 / 400.9 MB) | MS-4 formally open (closed OQ-053); E1-E6 exclusions are F3's |
| F3 `land_eligibility` | yes | built_pending_conformance | about 67 | ran_clean x3; 2026-10-26/27; 20 / 213 / 632 s; n/r | 23 files: 3 land scenarios x 2 technologies, candidates, cells, stability, shares (6.9 / 134.9 / 350.9 MB) | unsourced ranges (OQ-046, OQ-047, OQ-049, OQ-058) hold the restrictive/permissive values at central |
| F4 `climate_forcing` | yes | built_pending_conformance | about 44 + hazards, change factors | ran_clean x3; 2026-10-26/27; 106 / 128 / 181 s; n/r | `forcing.parquet` (36 members), `members.yaml`, 45 member maps (23.8 / 89.6 / 179.6 MB) | OQ-007, OQ-051; ISIMIP3b 2071-2100 hazard not acquired |
| hazard_context | yes | (inside F4) | in the F4 files | success x3; 2026-10-26; 33 / 98 / 231 s | `hazard_context.parquet` | OQ-051 thresholds |
| climate_maps | yes | (support) | figure tests | success x3; 2026-10-26; 291 / 678 / 614 s | 45 PNG per country | nothing |
| overview | yes | (support) | figure tests | success x3; 2026-10-26; 79 / 108 / 106 s | 22 PNG + tables per country | nothing |
| F5 `technical_potential` | yes | conformant | about 143; ZZZ and ZZZ2 hand validation | ran_clean x3; 2026-10-26/27; 14 / 234 / 669 s; peak 1.6-1.7 GB at BRA (D-F5-022, synthetic parameters) | potential tables x 3 scenarios x 2 technologies, aggregates, class flags, sensitivity 150 m (and IND 3000 m): 31.0 / 463.1 / 1,291.2 MB | OQ-007 (C2 losses) only for M-F5-04 |
| potential_maps | yes | (support) | in the F5 files + display tests | success x3; 92 / 265 / 313 s (IND and BRA by the code of COMMAND 69; PRT by COMMAND 70) | 22 PNG, COG rasters, display layers (PRT only), question figures | nothing |
| F6 `lcoe_modeling` | yes | conformant (synthetic only) | about 67 | not_run; sizing at BRA: wind 259 s, solar 260 s, peak 1.5 GB (D-F6-020) | LCOE summary, design matrix, supply curve, nominal LCOE of the other scenarios | OQ-001, OQ-019 (4 null parameters x 6 combinations) |
| F7 `robustness_analysis` | yes | conformant (synthetic only) | about 166 + H2, H3, PRIM tests; ZZZ2 for H4 | not_run; sizing at BRA: wind 2,477 s, solar 1,780 s, peak 2.2-2.4 GB (D-F7-063) | classes, rankings, H1-H5 tables, PRIM, T-R10, T-R12, maps | OQ-008, OQ-021 (3 null parameters), OQ-010, OQ-020, OQ-051 |
| F7b `external_validation` | yes | conformant (synthetic only) | about 15 | not_run; sizing: wind 163 s, solar 113 s, **peak 2.8 GB** (D-F7b-007) | exclusion at plant pixels, enrichment by decile, published-estimate table | OQ-057 (`published_potential.yaml` is empty); needs F6 |
| F8 `results_synthesis` | yes | conformant (synthetic only) | about 23 + 8 ZZZ tests | not_run; sizing: 79 / 65 s, peak 1.9-2.4 GB (D-F8-025) | thesis tables and figures T-ID (test build on ZZZ) | needs real F5-F7b; figures not yet through `viz` (COMMAND 70 pending) |
| E1 platform (`explorer`) | no | not_started | none | - | - | OQ-013 (stack), F7 artifacts |

Support phases registered in `main.py` but not in PROGRESS: `lcoe_maps`, `robustness_maps`, `sample_size_convergence`, `external_inputs`, `climate_maps`, `hazard_context`, `overview`, `potential_maps` (METHODOLOGY 4.2 lists them); PROGRESS has 13 phase entries (R71-04).

**Artifacts and figures per country** (counted on disk): PRT 261 files / 99 MB / 89 PNG; IND 248 files / 1,246 MB / 89 PNG; BRA 250 files / 3,270 MB / 89 PNG; `outputs/comparison` 5 files (4 PNG, 664 KB); ZZZ output folder is a September leftover (R71-21). Internal caches (`interim/`): BRA 1.30 GB, IND 0.88 GB, PRT 0.12 GB.

**Fingerprints.** The recorded code fingerprint of five phases differs from the one computed at HEAD in all three countries (R71-06); the table above shows the run that exists on disk, not a run of HEAD.

---

## B. Coherence of the documentation

### B.1 METHODOLOGY items against code and tests

Scan of the 99 IDs of METHODOLOGY (69 `M-`, 13 `A-`, 8 `U-`, 9 `V-`) for the tag in `src/`, `scripts/`, `config/` (implementation) and `tests/`:

| Class | M | A | U | V | Total |
|---|---|---|---|---|---|
| tag in code and in tests | 42 | 10 | 5 | 9 | 66 |
| tag in code only | 17 | 3 | 3 | 0 | 23 |
| tag in tests only | 4 | 0 | 0 | 0 | 4 |
| tag nowhere | 6 | 0 | 0 | 0 | 6 |

Items with **no tag anywhere** (what the item says; verdict on the gap):

| Item | Text (METHODOLOGY line) | Reading |
|---|---|---|
| M-E1-01 (352) | static explorer | E1 `not_started`: expected |
| M-F6-03 (281) | C3 loss function as OPEX adder | blocked by OQ-007: expected |
| M-F5-04 (266) | C2 loss on CF | blocked by OQ-007; only a test mentions it (`test_methodology_changelog.py`): expected |
| M-F2a-05 (194) | counts summed to the grid, not sampled | **implemented** (`population` is summed: D-F2a-014/015) but not tagged: traceability gap |
| M-F2a-07 (196), M-F2a-08 (197) | slope as distribution, one DEM (GLO-30) | **implemented** (`raster_alignment.elevation_and_slope_from_glo30`, `land_cover_counts`, `slope_counts`; PROGRESS F2a) but carried by D-IDs, not by M-IDs |
| M-F5-07 (269) | maps of the potential | **implemented** (`technical_potential/maps.py`, D-F5-029/032) but not tagged |

Items implemented (tag in code) with **no test carrying the tag** (23, the weaker group; the behavior may still be tested under another label): A-03, A-11, A-13, M-F1-02, M-F1-04, M-F1-05, M-F1b-02, M-F2a-01, M-F2b-01, M-F2b-03, M-F2b-04, M-F3-02, M-F3-04, M-F3-05, M-F5-06, M-F6-04, M-F7-09, M-F7-10, M-F7b-02, M-F7b-03, U-01, U-03, U-08. Of these the ones that matter for a result are M-F3-02/M-F3-04 (scenarios and candidate set), M-F5-06 (aggregates), M-F6-04 (batching, exact quantiles) and M-F7b-02/03 (enrichment; published table). The behavior of M-F6-04 is covered by name in `test_lcoe_pipeline.py` (`test_summary_equals_numpy_on_the_full_block`), so the gap is the tag, not the test.

Items implemented differently from the text: none found in the spot checks made for this report, which were limited to the items cited in it (M-F5-03 hub height 100 m with the IEA 3.4-130 curve whose own hub is 110 m is declared in the text; METHODOLOGY A-07 says COG; PROGRESS `core` says "tiled GTiff, not true COG", which the files contradict: R71-25).

**R71-13 (P2).** Add the missing M- tags (M-F2a-05, -07, -08, M-F5-07) in `Implements:` lines, and a tagged test for the 23 items above; nothing to verdict.

### B.2 `config/parameters.json` against the thesis texts and the schemas

- Group 2 (`docs/thesis/methods/group2_core_costs.tex`): CAPEX central and interval (6 country-technology rows), fixed O&M in USD/kW/yr and fraction (central and range, 6 rows), real WACC (central and range, 6 rows), lifetime U{25..30} with central 30, `t_ref` 2024: **every number and every tier equals `parameters.json`** (checked row by row; for example PRT solar CAPEX 779 and 524-1034, PRT wind O&M 0.024714 and 0.01748-0.031947).
- Group 1 (`group1_technical_potential.tex`): LUF 0.10/0.25/0.35 and 0.05/0.15/0.30 (BRA, PRT), 0.05/0.10/0.25 and 0.05/0.075/0.15 (IND); PV power density 45/50/75; wind power density 3.32/4.99/7.12; `eta_loss` 0.866 [0.803, 0.932] (the three component products 0.8031, 0.8661, 0.9317 recomputed); `gamma` -0.0030 [-0.0032, -0.0028]; hub height 100 m: **all equal** the central value and the `scenario_values` of `parameters.json`.
- Not compared: the numbers inside the synthesis, hypothesis and theory `.tex` files (they quote no parameter value), the `\cite` keys against `references_stage_r.bib`.
- Schemas: `tests/unit/test_parameter_contract.py` and `test_groups12_parameters.py` pass (1,849 passed, COMMAND 70). Null values per country and technology (identical in the six real combinations): `degradation_rate`, `grid_cost_usd_per_mw_km`, `substation_cost_usd_per_mw`, `road_cost_usd_per_km`, `cf_min`, `tau_lcoe_usd_per_mwh`, `top_k_percent`; all other entries have `verified: false` except one per combination; tiers per combination: Tier 1: 1 to 2, Tier 2: 7 to 9, Tier 3: 1 to 2.
- ZZZ carries values with `synthetic: true` for every one of the 7 null ones (`degradation_rate` 0.005, `cf_min` 0.15/0.30, `tau` 95/45, `top_k_percent` 25), which is what lets F6 and F7 run on ZZZ: correct by V-08 and tested by `test_synthetic_value_separation.py`.
- **R71-17 (P2):** the header comments of the two thesis files say `docs/thesis/methods/parameters/group1_technical_potential.tex` and `.../group2_core_costs.tex`; the files are in `docs/thesis/methods/`. The same wrong path appears in `ch2_renewable_potential_foundations.tex:8-9`. Fix: edit the comments.

### B.3 OPEN_QUESTIONS, LIMITATIONS and D- records

| ID | Evidence | Sev. |
|---|---|---|
| R71-10a | `docs/OPEN_QUESTIONS.md` says "unresolved items only" but **OQ-048 has status `resolved`** (line 26 of the table); OQ-046 uses status `range_unsourced`, not in the vocabulary `open / research_in_progress / awaiting_verdict` (line 3); the status cells of OQ-043 and OQ-051 hold the text "open **Update 2026-10-14 ...**"; the "recently resolved, kept one cycle" paragraph (line 5) carries items of 2026-10-08 to 10-12 | P1 |
| R71-10b | OQ-041 lists "Depends on OQ-001 and OQ-040"; OQ-040 is closed (not in the table) | P2 |
| R71-10c | `PROGRESS.json` F2b summary and MS-4 (`in_progress`) say MS-4 "stays open only for OQ-053"; OQ-053 was closed on 2026-10-16 (`docs/phases/F5/oq053_report.md:1`, `:72` states PROGRESS no longer says it). MS-4's gate (METHODOLOGY 12: exclusion parity E1-E3, sanity ranges for three countries) is met by the same PROGRESS text ("0 pixels outside in PRT, BRA and IND"). **Proposal: close MS-4 (author's verdict).** | P1 |
| R71-10d | 42 OQs are cited and not open; for 5 of them (OQ-009, OQ-025, OQ-034, OQ-035, OQ-040) no closure sentence was found by search in the phase records or METHODOLOGY (the closure may be worded otherwise). OQ numbers 1 to 64 are all cited somewhere: no gap and no duplicate | P2 |
| R71-10e | Closed OQs cited in present tense as blocking: `config/settings.yaml:35-36` ("fails loudly ... (OQ-004, OQ-005, OQ-023)", all three closed 2026-10-16, D-F5-023); `src/geofrea/core/schemas.py:273` ("null until the author fixes the rate (OQ-022)"; OQ-022 closed) | P2 |
| R71-11 | RETIRED limitations cited as if live: L-045 and L-046 in `docs/METHODOLOGY.md:190` and `docs/phases/core.md:153-154`; L-203 in `docs/METHODOLOGY.md:598` and `tests/unit/test_parameter_contract.py:74`; L-034/L-035 in `docs/phases/F6_lcoe_modeling.md:58-59`. Most are in dated history lines (acceptable), METHODOLOGY:190 is the one in a live spec sentence. 61 L- IDs defined, 6 RETIRED (L-034, L-035, L-043, L-045, L-046, L-203), no L- cited but undefined; 21 non-retired L- are cited nowhere outside LIMITATIONS (L-006, -007, -009, -010, -011, -013, -014, -017, -031, -032, -033, -036, -037, -038, L-101 to -105, L-205, L-208), i.e. the thesis-section column cannot be traced | P2 |
| R71-12 | D- records: 309 IDs defined. Two formats coexist: heading/table entries and dated bullets. IDs defined only in the dated-bullet form are invisible to a search for the heading format: D-core-017, -037 to -040, D-F5-022, D-F6-020, D-F7-063, D-F7b-007, D-F8-025 (`docs/phases/core.md:142,147-150`; `F5_technical_potential.md:85`). 13 IDs appear as the head of two entries (D-F1-016, D-F1-027, D-F1b-008, D-F1b-015, D-F2a-018, D-F4-019, D-F5-008, D-F6-007, D-F6-010, D-F7-026, D-F7b-002, D-F7b-006, D-F8-008: a table row plus the bullet). Gaps in the sequence, never defined: D-F1b-016, D-F4-027, D-F6-020 (bullet only), D-F7-030 to -033 (a range in METHODOLOGY 7.2.0 "D-F7-006 to D-F7-033"), D-core-017 (bullet only). D-core-044, -045, -046 are in descending order in `core.md:119-121` | P2 |
| R71-12b | `D-F7-063` is the highest F7 ID defined only as a bullet; the next free ID is therefore D-F7-064 | info |

### B.4 PROGRESS.json against the manifests

| Item | PROGRESS | Reality | Evidence |
|---|---|---|---|
| Country status F1 to F5 | `ran_clean` x3 | manifests: every phase `success`; the quality of "clean" (no warning) was not re-verified from logs | `outputs/<ISO>/manifest.json` |
| ZZZ F2a, F5, F7, F7b | `ran_with_issues` | `outputs/ZZZ/manifest.json` is schema 2.2 of 2026-09-24/27, with `grid_alignment: stale_upstream`; the real ZZZ runs now happen in temporary folders (tests) | `outputs/ZZZ/manifest.json` |
| F2a pixels | PRT 93,215, IND 2.78M, BRA 7.10M | `reference_grid.json`: 93,215 / 2,779,362 / 7,100,454 | **ok** |
| F3 central eligible share | "PRT 23.9 / 31.7%, IND 4.9 / 17.2%, BRA 18.0 / 25.8%" | cells tables now: PRT 23.84 / 31.69, IND **4.81 / 16.22**, BRA 18.05 / 25.81; `audit_potential_65.md:176,179` has IND 4.8% / 16.2% (61,464 wind cells; the 17.2% and 62,718 cells are from 2026-10-07, before OQ-060 and the contiguous mask) | `cells_*__central.parquet` |
| IND central solar | "728.4 to 753.3 GW" | aggregates: 753.37 GW | **ok** |
| `regression.status` | "its 1.4 GB copy is still on disk under GeoFREA_data/reference" | `GeoFREA_data` has no `reference/` folder (`ls`) | stale |
| F5 `run_real_hashes.json` | cited as the hash record | 11 of 24 PRT files differ by bytes, IND 32/32 and BRA 24/24 match (R71-05) | hash check |
| `last_updated`, `methodology_version` | 2026-10-27, 15.2.4 | METHODOLOGY header 15.2.4, updated 2026-10-26 | **ok** |
| `core` summary | "A-13 partial (143 Implements lines)" | 140 `Implements:` lines now (`grep -c`) | minor |
| `phases` list | 13 entries | the DAG has 8 more registered support phases (above) | info |

**R71-04 (P1).** PROGRESS needs four edits (MS-4 and the F2b summary; the F3 numbers; the regression note; the hashes pointer). The author decides MS-4.

**R71-05 (P1).** `docs/phases/F5/run_real_hashes.json` (git commit 735188f, methodology 15.2.2) records SHA-256 of the **bytes**; PRT F5 was re-executed on 2026-10-27, bytes differ in 11 of 24 files (`class_flag_wind__*.parquet`, `potential_aggregates_*`, `potential_solar__central.parquet` ...) while the totals are the same as in `docs/phases/F5/audit_potential_65.md:109,132,146,170,173` (PRT solar 264.46 GW / 424.63 TWh, wind 21.05 GW / 49.00 TWh). Cause: Parquet bytes carry writer metadata that change with the code revision. The manifest already keeps the canonical content hash (D-core-042). Proposal: replace the file by content hashes (or delete it and point to the manifest). Risk: none.

### B.5 CONVENTIONS violations

| Rule | Finding | Evidence | Sev. |
|---|---|---|---|
| US English everywhere | Portuguese quotes inside docstrings (`config_models/audit.py:183`, `core/geodesy.py:17`, `data_acquisition/adapter.py:19`, `data_quality_audit/vector_inspection.py:43`, `grid_alignment/alignment.py:236`) and hard-coded Portuguese figure labels in code (`viz/mapstyle.py:1325-1326`: "FC médio", "área elegível"); `config/country_names.yaml` `pt:` is intentional (bilingual titles) | grep | P2 |
| No state sentences in config comments and docstrings ("Where status lives") | `config/settings.yaml:35-36` ("F5 is registered but not listed below: it fails loudly ... once those values are entered"), `config/experiments.yaml:149` ("Literature range still to be found"), `:170` and `:223` (`status: range_pending`), `core/schemas.py:273`, `grid_alignment/schemas.py:131` ("pending methodological") | grep | P2 |
| No ISO3 literal in `src/` | **none** outside docstrings (`hydrosheds.py:108`, `local_layers.py:226` are docstring examples); `tests/unit/test_iso3_literals.py` enforces it | grep | ok |
| Docstrings with `Args/Returns/Raises` | 719 public top-level functions, 658 with docstring (91.6%), 109 with an `Args:` section (15%), 132 with `Implements:` | AST count | P2 |
| COG, EPSG:4326 | measured with `rasterio` (`IMAGE_STRUCTURE LAYOUT`): **48 of 48 rasters of IND and of BRA and 48 of 54 of PRT are COG** (tiled 256 x 256, overviews 2 and 4); the 6 PRT `display_*.tif` of COMMAND 70 (`technical_potential/display_layers.py::write_display_layers`) are plain GeoTIFF, not tiled, no overviews; PROGRESS `core` still says "rasters are tiled GTiff, not true COG" | `outputs/PRT/technical_potential/artifacts/display_*.tif` | P2 (R71-25) |
| Phase record has no status line | holds | `docs/phases/*.md` | ok |
| Figures: `{ISO3}_{phase}_...png`, no `na` | new figures follow; the older layer figures keep `__na__na__na` (declared in CONVENTIONS) | `docs/figures/inventory.md:15,17,18` | ok |
| `pytest` and `ruff` clean | `ruff check`: all checks passed; `ruff format --check`: **17 of 331 files would be reformatted** (e.g. `core/schemas.py:273`, `data_acquisition/phase.py:150`) | `ruff` 0.16.8 | P2 |

**R71-02 (P1).** `docs/DECISIONS.md` and `docs/architecture/` were deleted in commit `2726333` ("adopt METHODOLOGY v1.0.0 ... archive 2026-09 records"), but 201 mentions in 48 files point to them (`git grep -c DECISIONS.md`): `src/geofrea/data_acquisition/phase.py` 18, `schemas.py` 16, `docs/phases/F1_data_acquisition.md` 12, `tests/unit/test_data_acquisition_phase.py` 11, `README.md:8,44`, and `config/settings.yaml:80`, `grid_alignment/alignment.py:51` (`docs/architecture/baseline-manifest.md`), `tests/unit/test_config_loader.py:16` (`module-mapping.md`). `docs/_archive/2026-09/` still holds `DECISIONS.md` and `architecture/` (`ls`), so the target exists. Proposal: replace the citation with `docs/_archive/2026-09/DECISIONS.md` (or the phase record) in one mechanical commit. Docstrings and `#` comments are outside the code fingerprint (`core/code_fingerprint.py::normalised_source` strips docstrings and `ast.parse` drops comments), so those edits trigger no rerun; the **string literals** that quote it (`data_acquisition/phase.py:387,406,438` and similar) are inside the F1 fingerprint and would re-execute F1 (about 3 to 17 min per country) unless left alone. Risk: none for results.

**R71-03 (P1).** `README.md:5-9` ("9-phase geospatial pipeline", "reconstruction of the GeoWorld Framework"), `:11-16` (`GEOWORLD_BASELINE_DIR`), `:30-33` (regression "against the frozen legacy baselines documented in `docs/architecture/baseline-manifest.md`", retired on 2026-10-06, `.github/workflows/regression.yml:3-6`). Rewrite in 20 lines. `docs/PROJECT_SUMMARY.md` says "Summarizes METHODOLOGY version 7.0.0" (current 15.2.4), last edit 2026-10-08 (R71-16, P2).

---

## C. Code

### C.1 Dead code and unused registry entries

`vulture` at confidence 60: 304 findings in `src/` and `main.py`, of which 229 are Pydantic fields and validators (false positives by nature), 42 unused-function/class candidates. After searching callers in `src/`, `scripts/`, `tests/`, `main.py` by AST:

- **Called nowhere (6 symbols, safe to delete):** `land_eligibility/figures.py:126 _resolution`; `overview/style.py:43 country_outline`, `:49 major_rivers`, `:130 load_relief`; `technical_potential/absolute_maps.py:204 CountryUnits`; `core/run_logging.py:149 PeriodicProgress.track`.
- **Called only by tests (production never calls them), left from retired designs:** `core/geo_utils.py:286 get_mainland_gdf` (superseded by the contiguous mask of M-F2a-01), `grid_alignment/raster_alignment.py:195 derive_slope_from_dem` (superseded by GLO-30, M-F2a-08; its name is still quoted in 5 comments), `data_acquisition/acquisition_area.py:59 native_grid_covers` and `:73 missing_parts`, `fetchers/era5.py:408 merge_yearly_files` and `:820 write_annual_maxima_from_hourly`, `viz/mapstyle.py:176 geographic_aspect` and `:187 legend_position`.
- **Registry entries without use:** the `<ISO>_elevation.tif` is not in the layer registry of the current run (22 layers, no `elevation`; `outputs/PRT/artifacts/layer_registry.json`) and `config/audit.yaml:52-53` says no phase reads it; what remains is the file itself (`raw/elevation/<ISO>/`, 0.32 GB), the generator of the synthetic one (`scripts/generate_zzz_fixture.py:97-105`), and the V-01 fixture. The `thresholds:` block of `config/experiments.yaml:256-266` (`satisficing_lcoe_usd_per_mwh`, `capacity_factor_min`) is read by nothing (`tau` and `CF_min` moved to `parameters.json`, D-F7-029) — **R71-15 (P2)**. `config/experiments.yaml` key `gcm_ensemble.D-F4-018` is a note-as-key. `config/settings.yaml` `geospatial.resolutions.suitability: 0.01` (legacy key name) is labeled "analysis-grid resolution" while the analysis cell is 0.05 degree and 0.01 is the F2a pixel (R71-26, P2; same wording issue as OQ-064).
- **Legacy figure modules** still draw with matplotlib outside `viz` (F8 `results_synthesis/*`, `scripts/audit_potential.py`): this is the pending migration recorded in PROGRESS `pending_figures`, not dead code.

### C.2 Duplicated logic

Function-level search (AST, normalized bodies, ratio above 0.8): identical `is_complete_download` in `fetchers/cmip6.py:210` and `fetchers/era5.py:182` (14 lines); `_load_countries_config` in `local_layers.py:202` and `fetchers/hydrosheds.py:84` (0.93); `fetch_country` in `fetchers/copernicus_dem30.py:94` and `fetchers/esa_worldcover.py:99` (0.85). The three registries (`cmip6_registry.py`, `era5_registry.py`, `isimip3b_registry.py`) share the names `save` and `_check_status_consistency` but are only 0.02 to 0.30 similar: no refactor needed. The older overview and results_synthesis `style.py` files are thin (0.03 similar). Overall duplication is low (P2, three small merges).

### C.3 TODO, FIXME, XXX and temporary notes

`grep -i "TODO\|FIXME\|HACK\|temporar\|workaround\|for now\|placeholder"` over `src/`, `main.py`, `scripts/`, `config/`: **no TODO, FIXME or HACK**. Hits are legitimate words ("placeholder" for the unpopulated `opex_var` in `core/schemas.py:254,305`, `data_acquisition/schemas.py:117,153` "empty for now", `technical_potential/power_curve.py:105`). The `XXX` hits in `tests/` are the test ISO code.

### C.4 Scripts

34 scripts, 6,358 lines. Used by tests or by the pipeline documentation: `generate_zzz_fixture.py`, `generate_zzz2_fixture.py`, `zzz2_world.py`, `zzz_climate_fixture.py`, `freeze_v01_fixtures.py`, `generate_prim_reference.py`, `gcm_selection_spread.py`, `stamp_manifest_hashes.py`, `acquire_*` (6), `audit_potential.py`, `size_f5_to_f8.py`, `coverage_audit_59.py`, `f2b_sanity_report.py`, `make_archetype_fixtures.py`, `make_style_guide_examples.py`, `archive_figures.py`. **One-shot candidates** (zero test references, one or zero documentation references, task finished): `archive_geofrea_data.py` (287 lines, 0 references, writes to `database\archive`), `migrate_clip_cache_keys.py` (75), `patch_era5_cells.py` (151), `place_local_inputs.py` (121; the only code that still names `D:\Douglas\DOUTORADO\database\raw`, line 17, read-only), `place_w5e5_tasmax.py` (91), `register_isimip3b_from_copy_log.py` (69), `qc_plants_vs_grid.py` (118), `plot_plants_over_grid.py` (88), `extend_era5_gust.py` (279), `era5_status.py` (134), `era5_ext_queue.py` (456; 8 tests). Candidate to **become part of the pipeline**: `audit_potential.py` (632 lines, the audit charts: pending migration to `viz`), `coverage_audit_59.py`, `f2b_sanity_report.py` (already F2b's sanity). Documents point to scripts that no longer exist on main: `scripts/archive_potential_figures.py` (`F5_technical_potential.md:69`, `potential_maps_v2.md:86`; deleted in `54eb3d0`), `scripts/build_forcing.py` (`F4_climate_forcing.md:36`; deleted in `923ae1b`), `scripts/migrate_manifest_2_0_to_2_1.py` (`core.md:53,55`), `scripts/restamp_caches.py` (`core.md:121`; exists only on `feat/cache-restamp`, rejected by D-core-044).

### C.5 Tests

- 1,466 test functions, 119 files; none skipped or xfailed (`grep` for `skip|xfail`: 1 `importorskip`-type call); 7 test functions have no `assert` or `raises` (they check "does not raise"): `test_zzz2_end_to_end.py::test_potential_maps_of_the_second_synthetic_world_add_up_to_the_f5_totals`, `test_audit.py::test_vector_coverage_check_leaves_...`, `test_core_raster_io.py::test_gdal_quiet_is_a_safe_noop_context_manager`, `test_fetchers_cmip6.py` and `test_fetchers_era5.py::test_validate_downloaded_netcdf_passes_on_a_real_file`, `test_grid_alignment_alignment.py::test_verify_alignment_passes_...`, `test_iso3_literals.py::test_no_iso3_literals_in_src` (99 lines, asserts through a helper).
- Modules that no test imports (10 of 148; some run in the ZZZ end-to-end indirectly): `overview/diagnostic.py` (495 lines), `results_synthesis/potential_and_cost.py` (240), `core/run_logging.py` (190), `results_synthesis/ranking_figures.py` (189), `fetchers/copernicus_dem30.py` (138), `results_synthesis/maps.py` (82), `land_eligibility/table_schemas.py` (71), `technical_potential/weibull_report.py` (69), `climate_forcing/table_schemas.py` (42), `results_synthesis/members.py` (24). `core/run_logging.py` is the module of CONVENTIONS "Run legibility" and has no direct test. No coverage measurement was run (it would double the 30-minute suite).
- ZZZ and ZZZ2: `test_zzz_end_to_end.py` 63 tests (F1 to F8, scale 0.1, F7b, F8, V-06 guards), `test_zzz2_end_to_end.py` 8 tests (the world where F7's H4 gives distinct profiles; hand validation). F6 to F8 conformance rests on these two only.
- CI (`.github/workflows/`): runs `tests/regression` and `tests/synthetic` plus two guard tests, on Python 3.12; the local environment is 3.11.9 and **the 1,393 unit tests and `ruff` are not in CI** (R71-27, P2).
- **R71-09 (P1) The MemoryError of COMMAND 70.** `tests/unit/test_parameter_contract.py:161-188` (`test_no_legacy_opex_names`) walks `REPO_ROOT` with `os.walk` and calls `read_text(errors="ignore")` on every file whose name does not end in `.pyc .tif .parquet .npz .png .gpkg`. The repository folder holds `regression-fixtures.tar.gz` (380,498,564 bytes = 363 MiB, ignored by git) and `.env`, `logs/`: the 363 MiB archive is decoded to a Python string (up to 4 bytes per character) on a machine with 5.9 GB of which 78-82% was in use during this audit (`psutil.virtual_memory()`). Run alone it passes, and it passed in this session's full run in 20.6 s, with the whole suite at a 2.23 GB peak: the failure needs memory pressure from the other applications of the machine, which is exactly the risk. Proposal: iterate over `git ls-files` or add `.gz`, `.tar` and `.nc` to the skipped suffixes. Risk: none (same assertion, fewer bytes).
- **Full run of this session: 1,850 passed, 0 failed, 28 min 00 s, peak 2.23 GB.** Slowest tests: D.3.
- Giant functions (maintainability, P2): `robustness_analysis/pipeline.py:run_window` 826 lines, `main.py:_build_phase_specs` 765 lines, `core/orchestrator.py:run` 400, `viz/panels.py:new_panels` 312; `viz/mapstyle.py` 2,462 lines in one module.

---

## D. Performance

### D.1 Time and memory per phase and country

Wall seconds of the last run (manifest) and of the **cold** run (maximum recorded in `GeoFREA_data/logs/<ISO>/*.log` for the same phase; the cold figure is what a first run on a new country costs).

| Phase | PRT last / cold | IND last / cold | BRA last / cold | Peak memory |
|---|---|---|---|---|
| data_acquisition | 168 / 168 | 1,004 / 2,382 | 647 / 647 | n/r |
| data_quality_audit | 237 / 404 | 4,096 / 4,334 | 3,861 / 6,563 | n/r |
| grid_alignment | 355 / 648 | 9,678 / 9,923 | 42,176 / 42,176 | n/r (G-5 "memory known issue resolved", `F2a_grid_alignment.md:72`) |
| siting_layers | 3 | 24 | 58 | n/r |
| land_eligibility | 20 | 213 / 3,437 | 632 / 4,134 | n/r |
| climate_forcing | 106 / 226 | 128 / 153 | 181 / 205 | n/r |
| climate_maps | 291 | 678 | 614 | n/r |
| hazard_context | 33 | 98 | 231 | n/r |
| overview | 79 | 108 / 273 | 106 / 247 | n/r |
| technical_potential (F5) | 14 | 234 / 422 | 669 / 1,293 | 1.6-1.7 GB at BRA (D-F5-022, synthetic values) |
| potential_maps | 92 / 462 | 265 / 2,634 | 313 / 1,258 | n/r (22-32 s and +3 MB in the sizing) |
| F6 | not run | not run | sizing 259 s | 1.5 GB (D-F6-020) |
| F7 | not run | not run | sizing 2,477 s wind, 1,780 s solar | 2.2-2.4 GB (D-F7-063) |
| F7b | not run | not run | sizing 163 s / 113 s | **2.8 GB** (D-F7b-007), the highest of the chain |
| F8 | not run | not run | sizing 79 s / 65 s | 1.9-2.4 GB (D-F8-025) |
| full test suite | 28 min 00 s (this session; 29 min 45 s in COMMAND 70) | | | 2.23 GB peak (process tree) |

CPU time is also recorded (`cpu_s`): BRA grid_alignment 42,176 s wall against 21,048 s CPU (half of the time is waiting: I/O or contention); IND 9,678 s wall against 12,413 s CPU (multi-threaded GDAL); climate_maps, F3 and F5 have CPU equal to wall in all three countries (single-threaded compute: BRA F5 669 s wall, 640 s CPU). **Nothing records peak memory for F1 to F4 or the maps (R71-08, P1).** `core/run_logging.py` logs time and CPU only (no `psutil`, no `resource`). Proposal: add `psutil.Process().memory_info().peak_wset` (Windows) or `resource.getrusage` to the same `completed in ...s (CPU ...s)` line and to the manifest entry (`peak_rss_mb`); risk none, but it changes the manifest schema (2.6 to 2.7) and the orchestrator fingerprint, so do it with the next schema change.

### D.2 The ten largest bottlenecks, with proposals (nothing implemented)

Gains are estimates from the logged step times, not measurements; "risk" is the risk to the result.

| # | Bottleneck (evidence) | Proposal | Gain | Risk to the result |
|---|---|---|---|---|
| 1 | BRA `grid_alignment` land cover: step `land_cover` 26,534 s of 42,176 s (63%); IND 1,938 s (logs, `alignment.py:445-463`). The step runs `mosaic_land_cover` (point-sample reprojection of every tile) **and** `land_cover_class_counts` (block counts, M-F2a-06). F3 reads only the counts (`land_eligibility/pipeline.py:394`) | Measure first on PRT which of the two passes dominates; if the mosaic does, derive the displayed land-cover raster from the counts (dominant class) and drop the second pass over the 111 tiles; process tiles in 2 worker processes (memory allows 2 of 5.9 GB) | 2x to 4x on 26.5 ks | Low for numbers (F3 uses counts, which stay byte-identical, testable on PRT); the land-cover figure and `V-01` frozen layer change if the mosaic is dropped (needs a re-freeze: author) |
| 2 | BRA `slope_counts` 5,736 s and `elevation` 4,385 s (IND 3,198 s and 2,305 s): GLO-30 at 30 m, `elevation_and_slope_from_glo30` (`raster_alignment.py:449`) writes the elevation and the slope in one pass and `slope_class_counts` (`:521`) is a second read of the same GLO-30 tiles | Check whether the second step re-reads the 33 GB of BRA tiles; read each tile once, strip by strip, into both outputs; float32 arithmetic where float64 is used | up to 2x on about 10 ks | None if counts are integer-exact and elevation mean is tested to the existing rasters on PRT (bit identity test) |
| 3 | BRA `rivers` 3,525 s, `roads` 1,178 s, `population` 2,325 s (IND 879 s, 1,644 s, 872 s): clip, rasterize and distance at 0.01 degree | The clipped vectors are already cached (`interim/*_clipped.gpkg`); rasterize with an STRtree-windowed loop; compute the distance transform by block with a halo | 1.5x to 3x on about 7 ks | Distances change in the last digit if the algorithm changes (EDT vs geodesic): must keep the geodesic rule of M-F2a-03; test against the current rasters with tolerance |
| 4 | `data_quality_audit` BRA 3,861 s and IND 4,096 s: the land-cover audit alone took **3,325 s** on 2026-10-22 against **63 s** for the same 111 tiles on 2026-10-14 (logs `1ab203b9...log` and `fc515236...log`) | Find the cause of the 50x difference first (disk contention with a parallel run is the likely one; or a changed audit); then skip the audit of an input whose content hash is unchanged (the audit is a report and never blocks, M-F1b-02) | 90% on reruns | None (report only); cache must be keyed by content |
| 5 | BRA `land_eligibility` cold 4,134 s (warm 632 s), IND 3,437 s (213 s): the share caches (`interim/<ISO>/land_eligibility`) make reruns short | Keep; the cold cost is the first run per country: parallelize the per-class share computation by tile | 1.5x on cold | None (shares are exact fractions, test equality) |
| 6 | `potential_maps` cold: IND 2,634 s, BRA 1,258 s (now 265 s and 313 s); `climate_maps` 291 / 678 / 614 s for 45 PNG per country; `overview` about 100 s | Draw with `figures: summary` in development runs (`settings.yaml` `figures`; A-08); the thesis build uses `all`. Optionally render the 45 member maps in 2 processes | 10x in development runs | None (figures only) |
| 7 | F5 BRA 669 s (cold 1,293 s): re-executed whenever **any figure module** changes, because the F5 fingerprint closure has 55 modules including `technical_potential.maps`, `question_figures`, `display_layers` and `viz.mapstyle` (`phase_modules('technical_potential')`) | Split the fingerprint of the numeric part of F5 (tables) from the figure code of `potential_maps` (R71-06) | avoids 11 min (BRA) to 4 min (IND) per style change | Must not hide a real change: keep every module that writes the potential tables in the numeric closure |
| 8 | F7 (not yet run): BRA wind 2,477 s, solar 1,780 s, peak 2.4 GB (D-F7-063); two thirds of the F5-F8 chain | Nothing before the first real run; then profile `run_window` (826 lines) | unknown | Numerical: do not change precision before the real inputs exist |
| 9 | F7b peak 2.8 GB (D-F7b-007): reads the pixel-level exclusion rasters of the whole country | Read the plant windows only (the plants are a few thousand points) | 2.8 GB to under 1 GB | None (same pixels) |
| 10 | Test suite 29 min 45 s: the synthetic ZZZ builds (63 + 8 tests) and 1,393 unit tests, serial; one test reads 363 MiB (R71-09) | Session-scoped fixture for the ZZZ world; mark the 71 synthetic tests `slow` and run the 1,393 unit tests in about 6 min (`tests/unit` alone was 359 s in D-core-040); `pytest-xdist` is not installed | 2x to 4x | None |

The BRA cold cost of F1 to F5 and the maps adds up to about 16 hours (F1 0.2 h, F1b 1.8 h, F2a 11.7 h, F2b 0.02 h, F3 1.1 h, F4 with its maps and overview 0.4 h, F5 0.4 h, potential_maps 0.3 h); rows 1 to 4 are 83% of it.

### D.3 Slowest tests of this session's full run

`pytest --durations=40` of this session (seconds). The three synthetic worlds' setup is 542 s of the 1,680 s:

| s | Phase | Test |
|---|---|---|
| 199.2 | setup | `synthetic/test_zzz2_end_to_end.py::test_every_phase_from_f1_to_f8_runs_and_succeeds` |
| 185.2 | setup | `synthetic/test_zzz_end_to_end.py::test_every_phase_from_f1_to_f6_runs_and_succeeds` |
| 157.4 | setup | `synthetic/test_zzz_end_to_end.py::test_the_scale_check_runs_every_phase_and_leaves_the_default_scale_untouched` |
| 44.0 | call | `unit/test_figures_setting.py::test_overview_none_writes_the_table_only_and_all_adds_the_diagnostic_maps` |
| 43.9 | call | `synthetic/test_zzz_end_to_end.py::test_a_rerun_of_the_f7_of_a_country_makes_f8_refuse_t_r6_t_r7_and_t_r8_until_cross_country_h4_runs_again` |
| 34.5 | call | `synthetic/test_zzz_end_to_end.py::test_f8_is_deterministic_and_needs_only_the_registered_artifacts` |
| 29.1 | setup | `unit/test_climate_forcing_figures.py::test_the_ensemble_sheets_the_grids_and_the_members_are_written_with_standard_names` |
| 29.0 | call | `unit/test_overview_figures.py::test_eligibility_figure_is_added_when_f3_cell_tables_exist` |
| 26.2 | setup | `unit/test_land_eligibility_figures.py::test_one_sheet_per_technology_a_chart_and_a_map_of_each_exclusion_are_written` |
| 20.6 | call | `unit/test_parameter_contract.py::test_no_legacy_opex_names` |
| 19.3 | call | `synthetic/test_zzz_end_to_end.py::test_cross_country_h4_gives_not_testable_for_one_country_and_a_verdict_for_three` |
| 16.8 | call | `unit/test_mapstyle_archetypes.py::test_the_furniture_has_the_same_place_in_every_country` |
| 16.2 | call | `unit/test_figures_setting.py::test_climate_maps_are_the_ensemble_sheets_and_the_members_only_with_all` |
| 14.8 | call | `unit/test_climate_forcing_forcing.py::test_forcing_gives_the_known_factors_for_every_cell_and_member_and_identity_for_m0` |
| 13.4 | setup | `regression/test_v01_frozen.py::test_the_same_layers_are_produced` |
| 11.7 | call | `unit/test_mapstyle_archetypes.py::test_every_figure_is_clean_and_matches_its_golden[CHL-capacity_factor]` |
| 11.6 | call | `unit/test_display_resolution.py::test_a_cell_is_at_most_four_pixels_or_the_subtitle_declares_the_smoothing[capacity_factor-CHL]` |
| 11.0 | call | `synthetic/test_zzz2_end_to_end.py::test_the_hand_validation_agrees_with_every_phase_of_the_run[wind]` |
| 10.8 | call | `synthetic/test_zzz_end_to_end.py::test_v06_f5_to_f7_do_not_change_when_the_plant_inventory_is_absent` |
| 10.3 | call | `unit/test_mapstyle_archetypes.py::test_every_figure_is_clean_and_matches_its_golden[CHL-density]` |

Figure drawing dominates the unit tests.

---

## E. Repository

**Size.** `.git` 27 MB (pack 19.8 MiB, 375 commits on main); working tree without `.venv` 405 MB of which the ignored `regression-fixtures.tar.gz` is 363 MiB; tracked: 545 files (`src` 166, `tests` 147, `docs` 178, `scripts` 34, `config` 9). `docs/` 17 MB, `tests/` 17 MB, `src/` 5.2 MB, `scripts/` 516 KB. `.venv` 854 MB (ignored).

**Largest tracked files** (`git ls-files | du`): all PNG, 832 KB at most (`docs/figures/examples/BRA_example_capacity-factor_wind_central_ref.png`); 52 tracked PNG total 13.9 MB; the largest non-image is `tests/fixtures/prim_reference.json` (268 KB). No binary or data file above 1 MB is tracked: the repository is lean.

**Image folders created in `docs/` by COMMANDS 56 to 70** (all tracked; none removed here; sizes `du -sk`):

| Folder | Files | KB | Report that cites it |
|---|---|---|---|
| `docs/_audit/2026-10_data_diagnostics_figures` | 9 | 2,048 | `docs/_audit/2026-10_data_diagnostics.md` |
| `docs/phases/core/coverage_alignment_54` | 12 | 1,040 | `coverage_alignment_54.md` |
| `docs/phases/F5/potential_maps_v2` | 8 | 2,248 | `potential_maps_v2.md` |
| `docs/phases/F5/potential_maps_absolute` | 2 | 712 | `potential_maps_absolute.md` |
| `docs/phases/F5/audit_potential_65` | 3 | 628 | `audit_potential_65.md` |
| `docs/figures/examples` | 6 | 2,464 | style guide |
| `docs/figures/migration_68` | 8 | 2,820 | `migration_68.md` |
| `docs/figures/display_layers_70` | 4 | 2,184 | `display_layers_70.md` |
| total | 52 | 14,144 | |

`docs/figures/display_resolution_67b` no longer exists (archived in COMMAND 70). Dated audit records under `docs/_audit` (36 files and 3 sub-folders, 59 tracked files, 0.9 MB) are versioned history; `docs/_archive/2026-09` keeps the old `DECISIONS.md`, `architecture/`, `README.md`, `CLAUDE.md`, `CONVENTIONS.md`, `PROGRESS.json`.

**`.gitignore`.** Correct for data (`GeoFREA_data/`, `outputs/`, `.env`, `logs/`, `*.log`). Observations: the pattern `data/` ignores any folder named `data` at any depth, handled by the exception `!/docs/data/` (works today; a future `tests/data` or `src/.../data` would be silently ignored); the comment cites `docs/DECISIONS.md` (R71-02); `regression-fixtures.tar.gz` is in the ignore list and is 363 MiB on disk although the workflow that used it was retired on 2026-10-06 (`.github/workflows/regression.yml:3-6`). `.pytest_cache` in the repository folder is not readable by the current user (`du`: "Permission denied"), which also breaks `du` and `git status --ignored` listing; likely created by a different account or an elevated shell (P2).

**Branches, worktrees, untracked.**

| Item | State | Proposal |
|---|---|---|
| `git status` | clean (no modified, no untracked file; ignored: `.env`, `.ruff_cache`, `.venv`, `__pycache__` x many, `logs/`, `regression-fixtures.tar.gz`, `src/geofrea.egg-info`) | - |
| Local branches | 24 local (`main`, 2 unmerged and) 21 merged into `main` (`docs/coverage-54`, `docs/geometry-dem-55`, `feat/display-layers-wiring`, `feat/display-resolution`, `feat/final-round-62`, `feat/fingerprint-granularity`, `feat/mapfigure`, `feat/mapfigure-geo`, `feat/mapstyle`, `feat/potential-maps-absolute`, `feat/potential-maps-v2`, `fix/coverage-59`, `fix/era5-first-year`, `fix/geometry-dem`, `fix/manifest-config`, `fix/oq060`, `fix/resume-integrity`, `fix/state-classes`, `stage-r/fix-46`, `stage-r/groups1-2`, `stage-r/oq053`); only `origin/main` exists on the remote | delete the 21 merged branches (no loss: `git branch -d` refuses unmerged; `feat/potential-maps-v2` is checked out in `wt60`, remove that worktree first) |
| `feat/cache-restamp` | 2 commits not in main (`git cherry`: both `+`), checked out in `GeoFREA_wt63`; **rejected** by D-core-044 (`docs/phases/core.md:119`) | after the author's confirmation: remove the worktree, keep the branch tag or delete |
| `backup-before-split` | 5 commits, 4 patch-equivalent in main (`git cherry`: `-`), 1 not (`d510f66`, `mainland_only` PRT flag, replaced by the contiguous mask of M-F2a-01) | author's verdict; probably delete |
| Worktrees | `GeoFREA_wt58c` (20.1 MB, detached `1ea2d9e`), `wt59` (20.2 MB, detached), `wt60` (15.7 MB, `feat/potential-maps-v2`, merged), `wt61` (22.7 MB, detached), `wt63` (15.8 MB, `feat/cache-restamp`); all clean (`git -C ... status`), all from 2026-10-20/22 | `git worktree remove` x5: 94.5 MB |
| Stash | none (`git stash list` empty) | - |
| CI | 2 workflows (regression, synthetic fixture), Python 3.12 | R71-27 |

---

## F. GeoFREA_data

### F.1 Size by folder (`du -sk`, GB)

| Folder | GB | Notes |
|---|---|---|
| `raw/` (own raw inputs) | 105.6 | `copernicus_dem30` 46.3 (BRA 33, IND 14, PRT 0.6), `gwa` 15.0 (BRA 5.0, CHN 6.1, IND 3.4, PAK 0.5, PRT 0.15), `esa_worldcover` 6.5 (IND), `land_cover` 6.4 (BRA 6.1), `era5` 6.0, `isimip3b` 5.9, `population` 5.9, `infrastructure_roads` 5.5, `cmip6` 4.2 (4.0 `_global`), `hydrosheds` 2.4, `gadm` 0.46, `solar_potential` 0.34, `elevation` 0.32, `w5e5` 0.18, `wdpa` 0.09, `infrastructure_grid` 0.07, `gem` 0.03 |
| `outputs/` | 4.5 | BRA 3.12, IND 1.19, PRT 0.09, `comparison` 0.001; the manifests are the only per-run state |
| `interim/` (caches) | 2.3 | BRA 1.30, IND 0.88, PRT 0.12, `coverage_audit_59` |
| `archive/` | 0.08 | `figures_20261020` 20 MB, `figures_20261026` 54 MB, `figures_run_report_20261022` 3.9 MB, `docs_figures_67b` 3.2 MB |
| `logs/` | 0.005 | 52 run logs for BRA; `legacy_manifests`, `legacy_runs` |
| `fixtures/` | 0.001 | |
| total | 112.4 GB in 3,816 files | |

CHN and PAK under `raw/gwa` are **not orphans**: they are the neighbours that complete the IND wind layers to the mask (`config/countries.yaml:140`, D-F1-030).

### F.2 Orphans and old caches

| ID | Item | Evidence | Size |
|---|---|---|---|
| R71-23a | `interim/{BRA,IND,PRT}/grid_alignment/<ISO>_slope_native.tif` | dated 2026-10-12, before the GLO-30 slope (COMMAND 55, 2026-10-19); the name `slope_native` occurs nowhere in `src/`, `scripts/` or `main.py` (`grep`) | 308.3 + 141.0 + 3.4 = 452.7 MB |
| R71-23b | `raw/gadm/{BRA,IND,PRT}/superseded_largest_polygon_v1/` | the folder name says superseded (METHODOLOGY 15.2.0: contiguous mask replaced the largest polygon); one byte-identical pair with the live shapefile (`gadm41_BRA_1.shp` = `superseded.../gadm41_BRA_1_mainland.shp`, 15.9 MB) | 42.1 MB |
| R71-23c | `raw/era5/IND/IND_fg10_annual_max.before_cell_patch.nc`, `...before_extension.nc` | backups of the patch and extension of D-F1-031 | 1.9 MB |
| R71-23d | `outputs/<ISO>/manifest.json.before_stamp` x3 | backup of `scripts/stamp_manifest_hashes.py` | 0.3 MB |
| R71-21 | `outputs/ZZZ` (manifest schema 2.2, `grid_alignment: stale_upstream`, 2026-09), `interim/ZZZ` | the synthetic country now runs in temporary folders | 0.4 MB |
| R71-23e | `raw/elevation/<ISO>/<ISO>_elevation.tif` | read by no phase (`config/audit.yaml:52-53`; `alignment.py:394`); the synthetic equivalent is only written by the fixture script | 0.32 GB (author's verdict: it is the "bundled" DEM of the original database) |
| R71-23f | `interim/<ISO>/data_quality_audit/` (BRA 381 MB, 119 files incl. `land_cover_tile_cache`; IND 337 MB; PRT 58 MB) | F1b audit caches; regenerable (audit rerun 1 to 1.8 h) | 0.78 GB (author's verdict) |
| R71-23g | `outputs/<ISO>/audit/audit_*.txt` | 22 / 17 / 23 historical audit text reports per country | 0.9 MB |
| info | `raw/w5e5` 0.18 GB | not referenced by `src/` or `config/`; planned input for OQ-051 (tasmax comparison; `scripts/place_w5e5_tasmax.py`): keep | - |
| info | `raw/cmip6/_global` 4.0 GB | global NetCDF of the six GCMs, the source of the national crops; all six GCMs of `experiments.yaml:50-55` are used: keep (re-downloadable only through CDS) | - |
| info | `outputs/BRA/technical_potential/sensitivity_150m` 406 MB (and IND, PRT) | results of the 150 m wind sensitivity (D-F5-027): keep | - |

Stale keys, not files: `interim/_clip_source_sha256.json` (15 of 49 keys) and `interim/<ISO>/grid_alignment/input_sha256.json` (116 of 1,063 in BRA, 58 of 602 in IND, 10 of 53 in PRT) still hold the paths of `D:\Douglas\DOUTORADO\database\raw\...`. They are content-hash memos; the stale keys are never looked up and could be pruned (cosmetic, P2).

Caches with an old code key: the `*.cachekey` files in `outputs/<ISO>/` (23 per country) and `*.key` in `interim/` were **not** compared with the current code; at HEAD five phases carry an older code fingerprint in all three manifests (R71-06), so every cache derived from them is "old" in that sense and valid by content.

### F.3 Duplicates

Search by size (files of 2 MB or more, 3,816 files, 112.4 GB), then SHA-256 of the first and last MB: **one duplicate group** (the GADM pair of R71-23b, 15.9 MB). There are no duplicate rasters, tables or caches. The 106 GB of `raw/` overlap by design with `database\raw` (67 GB): the copy made the project self-contained; the overlap was not measured file by file.

### F.4 Self-containment

- Code and configuration: `database` appears in `src/` only in a docstring (`data_acquisition/fetchers/esa_worldcover.py:3`, "held in `database/raw/land_cover/India`"); in `scripts/` in two files: `scripts/place_local_inputs.py:17` (`SHARED = Path(r"D:\Douglas\DOUTORADO\database\raw")`, the one-shot importer that **reads** it) and `scripts/archive_geofrea_data.py:5,38` (writes to `database\archive\geofrea_2026-10`, "nothing under `database\raw` is touched"). No phase reads `database\raw`: **confirmed**. No test, config or `main.py` mentions it.
- Manifests (`outputs/*/manifest.json`): no occurrence of `database\raw` (`grep -l` over the three manifests and the artifacts folders: none). The only data files that contain the path are the hash memos above and the legacy manifests under `logs/*/legacy_manifests` (dated 2026-09-11/21, historical).
- Writes: `find database/raw -type f -newermt 2026-09-15` returns **0 files and 0 folders**: nothing was written to `database\raw` since the project was adopted (METHODOLOGY adopted 2026-09-15). `database\archive` exists beside it.

### F.5 Recoverable space (estimate, nothing deleted)

| Category | GB | Condition |
|---|---|---|
| Orphans with no reader (R71-23a to d, R71-21) | 0.50 | none (derived or backups) |
| Unused bundled DEM (R71-23e) | 0.32 | verdict |
| F1b audit caches (R71-23f) | 0.78 | verdict; costs 1 to 1.8 h to rebuild |
| Repository side: `regression-fixtures.tar.gz` 0.38, five worktrees 0.09 | 0.47 | verdict (worktrees) / none (tarball: workflow retired) |
| Total | 2.07 | of which 0.50 + 0.38 + 0.09 without any scientific decision |

The raw inputs (105.6 GB) are not reclaimable without re-acquisition: the DEM alone is 46.3 GB (44% of raw).

---

## G. Scientific checks pending

### G.1 Wind capacity factor: cell-mean parameters against the mean of the pixel capacity factors (the effect seen in COMMAND 70)

**What is compared.** F5 computes the wind CF of a cell by applying the power curve to the **eligible-area-weighted mean** of the Weibull A, k and air density of the cell's 0.01 degree pixels (M-F5-03; L-004). The display layers of COMMAND 70 apply the same model pixel by pixel. For every cell, `bias = (CF_cell - CF_pixel_mean) / CF_pixel_mean`, where `CF_pixel_mean` is the mean of the pixel CFs weighted by the eligible area of each pixel (F3 `eligible_fraction` times the geodesic pixel area). Negative = the cell CF is lower than the pixel mean. Same code path as F5 (`resolve_technology`, `fine_capacity_factor`, reference member `m0`, central scenario, 100 m layer). Script: `scratchpad/bias.py` (read-only; reads 5 x 5 pixel windows of `siting_layers/artifacts/{weibull_a_100m,weibull_k_100m,air_density_100m}.tif` and `land_eligibility/artifacts/eligible_fraction_wind.tif`; nothing else is loaded). Sample: PRT all 3,500 candidate cells; IND and BRA 2,000 cells drawn at random (`random_state` 42) from the 61,464 and 181,306 central candidates. Solar was run on PRT as a check of the method.

| Country | Cells | Median | P5 | P95 | Mean | Share < -1% | Share > +1% | Largest | Energy effect on the sample (cell vs pixel) |
|---|---|---|---|---|---|---|---|---|---|
| PRT wind (all) | 3,500 | -0.0035% | -0.244% | +0.257% | -0.0026% | 0.46% beyond 1% in either direction | | 2.0% | +0.0006% (48.9997 vs 48.9995 TWh) |
| IND wind (sample) | 2,000 of 61,464 | -0.013% [-0.015, -0.012] | -1.53% | +0.004% | -0.32% | 6.5% | 0.05% | 21.6% | **-0.024%** [95% bootstrap -0.028, -0.020] (9.7420 vs 9.7443 TWh) |
| BRA wind (sample) | 2,000 of 181,306 | -0.156% [-0.170, -0.146] | -1.13% | +0.045% | -0.31% | 6.6% | 0.2% | 10.5% | **-0.129%** [-0.149, -0.107] (24.849 vs 24.881 TWh) |
| PRT solar (check) | 3,449 | 0 | -3e-16 | +3e-16 | 0 | 0 | 0 | 7e-16 | 0 (the solar model is linear in the resource) |

(The 2.0% largest value of PRT is the one that failed the 1% check of COMMAND 70, 1.96% there; the small difference is the weighting.)

**Reading.**
1. The sign is systematic outside PRT: the cell CF is lower than the pixel mean in 88.5% (IND) and 89.9% (BRA) of the sampled cells, as expected from the shape of the power curve on a spread of wind speeds; in PRT it is symmetric.
2. **National totals are not at risk.** Applying the sample ratio to the central scenario of F5: BRA wind 2,297.2 TWh/yr would be about +3.0 TWh (+0.13%), IND wind 299.5 TWh about +0.07 TWh (+0.02%), PRT +0.0006%. These are one-line estimates: the sample is 1.1% of the BRA cells and 3.3% of the IND cells; the bootstrap interval covers sampling only.
3. **Individual cells are affected**: 6.5% to 6.6% of the sampled IND and BRA cells are more than 1% too low, a few by 10% to 22% (rugged terrain: IND maximum 21.6%). F7 ranks cells by LCOE, and LCOE is inversely proportional to the energy of the cell, so the ranking of these cells and the T-R6/T-R12 supply curves by CF band can move; H1 and H2 use top-k sets by cell. L-004's wording "second order" holds for the typical cell and not for this tail.
4. This is the same effect that made 16 of 3,500 PRT wind cells fail the 1% tolerance of the display layers (COMMAND 70). The decision on that tolerance and on this bias is one decision.

**R71-01 (P1, verdict).** Options: (a) keep F5 as is and make L-004 quantitative (the table above, sample-based for IND and BRA); (b) compute the CF per 0.01 degree pixel and aggregate by eligible area (exact aggregation, F5 cost multiplied by about 25 in the model step; BRA wind has 181,306 cells x 25 pixels; memory fits in blocks); (c) keep (a) and flag the cells whose pixel CF differs by more than 1% in a column of the F5 table. Risk of (b): changes every F5 number (small at national level, as above) and re-opens the F5 conformance and V-02 tests; do not decide before F6/F7 values exist. A full-country measurement for IND and BRA (not a sample) is possible with the same windowed script; extrapolating the sample run, 0.5 to 1.5 hours per country (not timed).

### G.2 Other numerical inconsistencies found in A to F

| ID | Finding | Evidence | Sev. |
|---|---|---|---|
| R71-04b | IND eligible share quoted as 4.9 / 17.2% (PROGRESS F3 summary, `F3_land_eligibility.md:166`) vs 4.81 / 16.22% in the current cells tables | section B.4 | P1 |
| R71-30a | `L-025` quotes "1,316 of 62,718 central cells" for IND wind candidates above 3000 m; the central candidate count is now 61,464 (`audit_potential_65.md:179`). The statement is a dated sensitivity (2026-10-16) and says so; the denominator is from before OQ-060 | `LIMITATIONS.md:35` | P2 |
| R71-30b | `docs/phases/F5/potential_maps_absolute.md:78` quotes PRT solar 264.6 GW / 424.9 TWh (round of 2026-10-19); the final round is 264.46 GW / 424.63 TWh (-0.05% / -0.07%), as in `audit_potential_65.md:132` | grep | P2 |
| R71-05 | `run_real_hashes.json` PRT: 11 of 24 byte hashes differ, totals equal | B.4 | P1 |
| R71-26 | `settings.yaml` calls `resolutions.suitability: 0.01` the "analysis-grid resolution" while OQ-064 says the analysis grid is fixed at 0.05 degree | `config/settings.yaml:66-71`; `OPEN_QUESTIONS.md` OQ-064 | P2 |
| R71-06b | The three countries carry different code fingerprints for the same phase: F5 PRT `59f47b` vs IND and BRA `2a6650`; potential_maps PRT `2dd9c6` vs `d49d3b`; the PRT run is the only one made after COMMAND 70 | manifests | P2 |
| R71-22 | The same input (111 BRA land-cover tiles) took 63 s and 3,325 s in the audit of two runs | D.2 row 4 | P2 |

No numeric inconsistency was found between `parameters.json` and the thesis tables (B.2), between the F2a pixel counts and PROGRESS, or between the F5 totals of the three countries and `audit_potential_65.md` (BRA solar 19,188.34 GW and 31,068.30 TWh; IND solar 753.37 GW; PRT 264.46 GW: all equal the aggregates files).

---

## H. Pending items and roadmap

### H.1 Open questions by research group

The repository defines only Groups 1 and 2 (`docs/thesis/methods/group1_*.tex`, `group2_*.tex`) and names Group 3 (`F6_lcoe_modeling.md:64`, OQ-001; `PROGRESS.json:59`). **Groups 4 to 7 below are my grouping by blocking phase; the author's own numbering may differ.**

| Group | OQs | What each blocks | Today |
|---|---|---|---|
| 3: connection costs and degradation (F6) | OQ-001 (`grid_cost_usd_per_mw_km`, `substation_cost_usd_per_mw`, `road_cost_usd_per_km`), OQ-019 (`degradation_rate`); related: OQ-041 (cost vs distance model), OQ-011 (grid layer, voltage), OQ-063 (provenance of `grid.gpkg`, awaiting verdict) | F6 on real data (four null parameters x six country-technologies), and through it F7, F7b, F8 | open; IND grid layer incomplete (OQ-041, `2026-10_plants_vs_osm_grid.md`) |
| 4: F7 decision parameters | OQ-008 (`tau`, `cf_min`), OQ-021 (`top_k_percent`), OQ-020 (`q_ref`), OQ-010 (national targets) | `sample_size_convergence` (needs `cf_min` and `top_k_percent`), F7 satisficing and top-k, H3, H5, T-R12 | open; 3 null parameters per combination |
| 5: hazards and loss functions | OQ-051 (exposure thresholds; heat after the ISIMIP3b/ERA5 comparison), OQ-007 (C2/C3 loss functions), OQ-043 (source of the 0.5-1.5 wind factor bound, BRA only) | T-R10, H5b exposure, M-F5-04 and M-F6-03 (not implementable until OQ-007 passes), L-021 | open; ISIMIP3b 2071-2100 hazard data not acquired |
| 6: land-availability ranges (F3) | OQ-046 (riparian discharge), OQ-047 (population density), OQ-049 (unsourced ranges), OQ-058 (3000 m limit); OQ-048 is resolved but still listed | sourced restrictive/permissive scenarios (held at central today), L-020 (IND candidate set), U-06 and U-08 | open |
| 7: validation, thesis and platform | OQ-057 (published estimates), OQ-014 (min-max regret literature), OQ-013 (explorer stack), OQ-064 (grid-resolution sensitivity, after F7) | F7b published-estimate table, Chapter 2, E1, a limitation entry | open, partly "for later" |

### H.2 What is missing until the final results, in dependency order

1. **Decisions already waiting for the author** (cheap, unblock cleanup): R71-01, MS-4 closure, R71-07, the 1% display tolerance, the cleanup list.
2. **Group 3 values and the connection-cost model (OQ-001, OQ-019, OQ-041, OQ-011)** -> first **F6 real run** per country and technology (BRA sizing 259 s, 1.5 GB), then LCOE maps, the supply curve against LCOE (pending figure) and the sample-size convergence phase. Expect first-real-run corrections: F6 conformance is synthetic only.
3. **Group 4 values (OQ-008, OQ-021, OQ-020, OQ-010)** -> `sample_size_convergence`, then **F7 real run** (BRA wind 41 min and solar 30 min per the sizing; peak 2.2 to 2.4 GB), H1 to H5 tables, T-R12, PRIM.
4. **Group 5 (OQ-051; heat threshold needs the ISIMIP3b tasmax against ERA5 comparison on `raw/w5e5`)** -> T-R10 and H5b. OQ-007 may stay Tier 3 context (L-015).
5. **F7b real run**: needs F3, F5, F6 and `published_potential.yaml` (OQ-057); peak 2.8 GB, the largest of the chain.
6. **F8 real build**: after F5 to F7b; first migrate the F8 figures and the audit charts to `viz` (PROGRESS `pending_figures`), and check the F6/F7 figures on the first real run.
7. **Group 6 (OQ-046, OQ-047, OQ-049, OQ-058)** can run in parallel with 2 to 5; it changes F3 and everything downstream, so it should close **before** the real F6 run if possible (each F3 change re-executes F3, F5, F6, F7: BRA about 22 min for F3 and F5, plus F6/F7 hours).
8. **OQ-064** (grid-resolution sensitivity) after F7; **E1 platform** (OQ-013) after F7 artifacts exist.
9. **Engineering before the real chain:** R71-07 (hash coverage of F2b/F3), R71-08 (peak memory log), R71-06 (fingerprint granularity), R71-09 (test memory), PROGRESS and README repairs.

Order of the cost to the author's time, not of CPU: Groups 3 and 4 first (they alone unlock F6 and F7), then Group 5, with Group 6 settled before the first real F6.

---

## Findings register

Evidence is in the section named in the second column. "Verdict" = needs the author's decision before any action. Risk = risk of the proposed action.

| ID | Sev. | Section | Finding | Proposed action | Risk of the action | Verdict |
|---|---|---|---|---|---|---|
| R71-01 | P1 | G.1 | Wind CF at cell-mean Weibull parameters is below the pixel mean in 88-90% of IND/BRA cells; 6.5% of the cells beyond -1%, up to -21.6% (IND); national energy -0.024% IND, -0.13% BRA, +0.0006% PRT | (a) quantify in L-004, or (b) aggregate pixel CFs, or (c) flag the cells; settle with the display tolerance of COMMAND 70 | (b) changes every F5 number and the conformance tests | yes |
| R71-02 | P1 | B.5 | 201 mentions in 48 files of `docs/DECISIONS.md` and `docs/architecture/*`, deleted in `2726333` (kept in `docs/_archive/2026-09/`) | one mechanical commit pointing to the archive; comments and docstrings are outside the code fingerprint, string literals in `data_acquisition/phase.py` are not | editing literals re-executes F1 | no |
| R71-03 | P1 | B.5 | `README.md` describes the retired 9-phase legacy port and legacy-baseline regression | rewrite (20 lines) | none | no |
| R71-04 | P1 | B.3, B.4 | PROGRESS stale in 4 places; MS-4 held open by closed OQ-053 although its gate is met | edit PROGRESS; close MS-4 | none | MS-4: yes |
| R71-05 | P1 | B.4 | `run_real_hashes.json` records byte hashes; 11 of 24 PRT files differ with identical totals | content hashes or point to the manifest | none | no |
| R71-06 | P1 | D.2 row 7, F.2 | F5 code fingerprint has 55 modules including figure code; at HEAD five phases of three countries are stale (climate_maps, hazard_context, overview, F5, potential_maps: next run re-executes about 25 min in BRA); PRT manifest `dirty: true`; F5 fingerprints differ between PRT and IND/BRA | split numeric and figure closures; rerun PRT on a clean tree | a split must not hide a real change | no |
| R71-07 | P1 | A, below | F2b and F3 files are not registered one by one in the manifest: BRA manifest has 78 artifacts, none of the 12 `siting_layers/artifacts` files (401 MB) or 23 `land_eligibility/artifacts` files (351 MB); `land_eligibility.json` has no hash (0 occurrences of `sha256`), `technical_potential.json` has 2 | register each artifact with its canonical hash as F5 does | schema bump 2.6 to 2.7, one rerun | yes |
| R71-08 | P1 | D.1 | The pipeline records no peak memory (no `psutil` or `resource` in `core/`); the machine has 5.9 GB | add `peak_rss_mb` to the phase line and the manifest | schema bump | no |
| R71-09 | P1 | C.5 | `test_no_legacy_opex_names` reads the 363 MiB `regression-fixtures.tar.gz`: the MemoryError of COMMAND 70 (passed in this session's run, 20.6 s) | iterate `git ls-files` or skip `.gz .tar .nc` | none | no |
| R71-10 | P1 | B.3 | OQ table: OQ-048 resolved but listed; non-standard statuses (OQ-046, OQ-043, OQ-051); OQ-040 cited as open dependency; closed OQs cited as blocking in comments; 5 closed OQs without a closure sentence found | clean the table; edit the comments | none | no |
| R71-11 | P2 | B.3 | Retired L- IDs cited as live (L-045 in METHODOLOGY:190); 21 L- never cited | fix METHODOLOGY:190 (PATCH); fill the thesis-section column when the chapters exist | METHODOLOGY needs the author's authorization to edit | yes (authorization) |
| R71-12 | P2 | B.3 | Two D- formats; 13 IDs defined twice; unordered D-core-044 to -046 | one format, lookup script | none | no |
| R71-13 | P2 | B.1 | 6 METHODOLOGY items without any tag (4 implemented: M-F2a-05, -07, -08, M-F5-07); 23 implemented items with no test carrying the tag | add `Implements:` and tags | none | no |
| R71-14 | P2 | B.5 | State sentences in config comments and docstrings; Portuguese quotes in 5 docstrings; `Args:` in 15% of public functions | edit comments | none | no |
| R71-15 | P2 | C.1 | `thresholds:` block of `config/experiments.yaml:256-266` read by nothing | delete the block | none (test: `test_parameter_contract`) | no |
| R71-16 | P2 | B.5 | `docs/PROJECT_SUMMARY.md` says METHODOLOGY 7.0.0 | update | none | no |
| R71-17 | P2 | B.2 | Header comments of the two Group tex files name `methods/parameters/...`; `ch2...tex:8-9` too | fix the path | none | no |
| R71-18 | P2 | C.1 | 6 symbols called nowhere; 8 only by tests (`get_mainland_gdf`, `derive_slope_from_dem`, ...) | delete the 6; decide on the 8 | none for the 6 | no |
| R71-19 | P2 | C.2 | `is_complete_download` identical in two fetchers; two near-duplicates of 0.85-0.93 | merge in one helper | none | no |
| R71-20 | P2 | C.4 | 11 one-shot scripts (1,869 lines); 4 documents cite scripts that do not exist on main | archive the scripts; fix the citations | none | no |
| R71-21 | P2 | F.2 | `outputs/ZZZ` and `interim/ZZZ` are September leftovers (0.5 MB) | delete | none | no |
| R71-22 | P2 | D.2 row 4 | Audit of the same 111 BRA tiles: 63 s on 2026-10-14, 3,325 s on 2026-10-22 | find the cause (contention or code); content-keyed skip | none | no |
| R71-23 | P2 | F.2 | Orphans: 3 `slope_native.tif` (452.7 MB), `superseded_largest_polygon_v1` x3 (42.1 MB), 2 ERA5 backups, 3 `.before_stamp`; 0.32 GB DEM and 0.78 GB audit caches by verdict | delete the first group | none | the last two: yes |
| R71-24 | P2 | E | `regression-fixtures.tar.gz` 363 MiB, 5 worktrees (94.5 MB), 21 merged branches, `feat/cache-restamp` (rejected), `backup-before-split` | remove | none (`git branch -d` is safe) | the last two: yes |
| R71-25 | P2 | B.5 | A-07 and CONVENTIONS say COG: 48 of 48 rasters of IND and BRA and 48 of 54 of PRT are COG, but the 6 display layers written in COMMAND 70 are plain GeoTIFF; PROGRESS `core` still says the rasters are not COG | write the display layers with the COG writer of the other rasters; correct PROGRESS | none (derived layers; they enter no total) | no |
| R71-26 | P2 | G.2 | `resolutions.suitability: 0.01` called "analysis-grid resolution" | rename the comment | none | no |
| R71-27 | P2 | C.5 | CI does not run the 1,393 unit tests or ruff; Python 3.12 in CI, 3.11 locally | add a unit job and a 3.11 job | none | no |
| R71-28 | P2 | C.5 | 10 modules no test imports; 7 tests without assertion; 17 files not `ruff format`; functions of 826 and 765 lines | tests first for `core/run_logging.py`; split later | none | no |
| R71-29 | P2 | E | `.pytest_cache` unreadable (permissions); `.gitignore` pattern `data/` matches any folder named `data` | fix the ACL; anchor the pattern | none | no |
| R71-30 | P2 | G.2 | Dated numbers in `LIMITATIONS.md:35` and `potential_maps_absolute.md:78` differ from the final round | add the date or update | none | no |

**P0: none.** (R71-01 is the closest.)

---

## Proposed cleanup actions (none executed)

Sizes from `du -sk`, `os.stat` and `git`.

### Repository (`D:\Douglas\DOUTORADO\GeoFREA`)

| # | Action | Size | Condition |
|---|---|---|---|
| 1 | Delete `regression-fixtures.tar.gz` (ignored, retired workflow `.github/workflows/regression.yml:3-6`) | 363 MiB (380,498,564 B) | none |
| 2 | `git worktree remove` `D:\Douglas\DOUTORADO\GeoFREA_wt58c`, `..._wt59`, `..._wt60`, `..._wt61`, `..._wt63` | 94.5 MB | `wt63` holds the rejected `feat/cache-restamp` |
| 3 | Delete 21 merged branches (`docs/coverage-54`, `docs/geometry-dem-55`, `feat/display-layers-wiring`, `feat/display-resolution`, `feat/final-round-62`, `feat/fingerprint-granularity`, `feat/mapfigure`, `feat/mapfigure-geo`, `feat/mapstyle`, `feat/potential-maps-absolute`, `feat/potential-maps-v2`, `fix/coverage-59`, `fix/era5-first-year`, `fix/geometry-dem`, `fix/manifest-config`, `fix/oq060`, `fix/resume-integrity`, `fix/state-classes`, `stage-r/fix-46`, `stage-r/groups1-2`, `stage-r/oq053`) | negligible | after action 2 |
| 4 | Delete `feat/cache-restamp` and `backup-before-split` | negligible | author's verdict |
| 5 | Delete dead symbols: `land_eligibility/figures.py:_resolution`, `overview/style.py:country_outline`, `major_rivers`, `load_relief`, `technical_potential/absolute_maps.py:CountryUnits`, `core/run_logging.py:PeriodicProgress.track` | about 120 lines | `ruff` and suite after |
| 6 | Delete the `thresholds:` block of `config/experiments.yaml:255-266` | 12 lines | none |
| 7 | Archive or delete the 11 one-shot scripts: `archive_geofrea_data.py` (287 lines), `migrate_clip_cache_keys.py` (75), `patch_era5_cells.py` (151), `place_local_inputs.py` (121), `register_isimip3b_from_copy_log.py` (69), `qc_plants_vs_grid.py` (118), `plot_plants_over_grid.py` (88), `extend_era5_gust.py` (279), `era5_status.py` (134), `era5_ext_queue.py` (456, 8 tests), `place_w5e5_tasmax.py` (91, keep until OQ-051) | 1,869 lines | author's verdict |
| 8 | Move the older report images to `GeoFREA_data/archive/` as done for 67b: `docs/_audit/2026-10_data_diagnostics_figures` (2,048 KB), `docs/phases/core/coverage_alignment_54` (1,040 KB), `docs/phases/F5/potential_maps_v2` (2,248 KB), `docs/phases/F5/potential_maps_absolute` (712 KB), `docs/phases/F5/audit_potential_65` (628 KB) and the links of their reports | 6.7 MB | author's verdict; `docs/figures/{examples,migration_68,display_layers_70}` (7.5 MB) are style-guide references: keep |
| 9 | Fix the ACL of `.pytest_cache` and delete it | small | none |

### Data (`D:\Douglas\DOUTORADO\GeoFREA_data`)

| # | Action | Size | Condition |
|---|---|---|---|
| 10 | Delete `interim/BRA/grid_alignment/BRA_slope_native.tif`, `interim/IND/grid_alignment/IND_slope_native.tif`, `interim/PRT/grid_alignment/PRT_slope_native.tif` | 308.3 + 141.0 + 3.4 MB | none (no reader) |
| 11 | Delete `raw/gadm/{BRA,IND,PRT}/superseded_largest_polygon_v1/` | 41.1 MB (21,163 + 12,931 + 8,039 KB) | none |
| 12 | Delete `raw/era5/IND/IND_fg10_annual_max.before_cell_patch.nc` and `...before_extension.nc` | 1.9 MB | none |
| 13 | Delete `outputs/{PRT,IND,BRA}/manifest.json.before_stamp` | 460 KB | none |
| 14 | Delete `outputs/ZZZ` and `interim/ZZZ` | 537 KB | none |
| 15 | Delete `raw/elevation/` (bundled DEMs read by no phase) | 0.32 GB | author's verdict |
| 16 | Delete `interim/{BRA,IND,PRT}/data_quality_audit/` | 381 + 337 + 58 MB | author's verdict; the audit takes 1 to 1.8 h to rebuild |
| 17 | Archive `logs/*/legacy_manifests`, `legacy_runs`, `logs/_snapshots` (1.4 MB), `logs/_moves` (0.4 MB) | 2.4 MB | author's verdict |
| 18 | Prune the stale `database\raw` keys of the hash memos (`interim/_clip_source_sha256.json`, `interim/<ISO>/grid_alignment/input_sha256.json`) | KB | none |

Total if everything is accepted: about 2.1 GB (0.5 GB data and 0.47 GB repository folder without any scientific decision). `GeoFREA_data/raw` (105.6 GB) is not touched by any proposal.
