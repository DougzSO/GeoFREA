# Closing what does not change a fingerprint (COMMAND 131)

Written for: the author. Every code change was checked with `closure_fingerprint` (19 phases) and `function_fingerprint` (13 caches, the aligned-layer set and the 9 cache closures) against the values before the command (`fp131.py`, kept in the scratchpad): **the 12 phases that have run on PRT, IND and BRA, the 9 caches and the 13 function fingerprints are identical after every step.** The only fingerprints that moved are `robustness_analysis` and `sample_size_convergence` (F7, never run on real data, which the command allows) and they moved only because of item 4.

## 1a. Where the memory cap was applied before this command

`config/memory_budget.json` held one cap, 1,536 MB (`cap_mb`), and the measured peak of each layer kind. At run time:

| place | what it does | does it use the 1,536 MB? |
|---|---|---|
| layers of F2a (`grid_alignment/alignment.py:308`) and F2b (`siting_layers/physical_layers.py:126`), through `core/layer_process.run_layer` | each layer runs in its own child process; before it starts, `memory_guard.wait_for_memory` waits until the free memory covers the measured peak of that layer kind plus 300 MB (timeout 1,800 s, then the layer is not started); while it runs the parent ends the child if the commit charge of the system passes 95 % | no: it uses the measured peak of the layer, not the cap |
| `main.py` at the start of a country (`memory_guard.cold_start_shortfall`) | refuses to start a cold `data_quality_audit` or `grid_alignment` with less than 1.5 GB available | no |
| `land_eligibility` (F3) and F5 | kept under the cap by construction (stripes of rows; the windowed read of COMMANDS 91 and 126), nothing checks it while they run | no |
| every phase (`core/peak_memory.PhasePeak`) | measures the peak and writes `peak_rss_mb` in the manifest | measures only |
| `tests/unit/test_memory_budget.py` | the only code that compares a figure with `cap_mb()` (the heaviest layers on BRA-sized rasters) | yes, in a test |

So the 1,536 MB was never enforced on a phase. **`climate_maps`, `hazard_context` and `overview` do not pass through any guard:** they run in the main process (not in a layer process), they are not F2a/F2b, and the only thing that touches them is the peak measurement. Their BRA peaks (2,333, 2,798 and 2,041 MB) were above 1,536 MB with nothing noticing.

## 1b and 1c. The per-phase cap

`core/memory_cap.py` (new), `core/peak_memory.py`, `core/orchestrator.py` (manifest 2.11), `main.py`, `config/memory_budget.json` (`phase_caps`).

- Cap of a phase = ceil(1.25 x peak measured on BRA) rounded up to a multiple of 64 MB; written with its date; 1,536 MB for a phase with no measurement (the seven that have never run on real data: F6 to F8, `sample_size_convergence` and the support phases of F7).
- Up to 25 % above the cap the phase goes on while the free memory covers the excess plus a reserve (`phase_caps.over_cap_reserve_mb`, 300 MB); above cap x 1.25, or when the free memory does not cover it, `MemoryCapExceeded` is raised in the phase thread by the peak sampler and the orchestrator records the phase as failed. The excess goes to the manifest as `peak_over_cap` (with `memory_cap_mb`).
- It binds `main.py` runs; `GEOFREA_MEMORY_CAPS=0` switches it off, and the tests have it off.

Caps written (MB; the peak is the larger of `peak_rss_mb` and `cold_peak_rss_mb` of the BRA manifest; dates in the file):

| phase | BRA peak | cap | hard limit | IND peak | PRT peak |
|---|---:|---:|---:|---:|---:|
| data_acquisition | 782 | 1,024 | 1,280 | 1,004 | 322 |
| data_quality_audit | 1,152 | 1,472 | 1,840 | 1,186 | 535 |
| grid_alignment | 437 | 576 | 720 | 360 | 283 |
| climate_forcing | 565 | 768 | 960 | 514 | 281 |
| climate_maps | 2,333 | 2,944 | 3,680 | 1,513 | 645 |
| hazard_context | 2,798 | 3,520 | 4,400 | 2,003 | 931 |
| siting_layers | 888 | 1,152 | 1,440 | 275 | 274 |
| external_inputs | 303 | 384 | 480 | 311 | 275 |
| overview | 2,041 | 2,560 | 3,200 | 1,568 | 743 |
| land_eligibility | 1,481 | 1,856 | 2,320 | 864 | 562 |
| **technical_potential** | **1,579** (COMMAND 129) | **1,984** | 2,480 | 1,018 | 338 |
| **potential_maps** | **1,676** (COMMAND 129) | **2,112** | 2,640 | 1,207 | 665 |

You listed the peaks of COMMAND 129 only. I wrote caps for the other nine phases that have run too, from the peaks in the manifests, because a phase with a measurement does not fall under "no measurement = 1,536 MB", and with that default a BRA `hazard_context` (2,798 MB) would have been stopped at 1,920 MB on the next run. **These nine caps record what the phases hold today; they do not reduce it.** OQ-068 and L-067 say so.

Two things to know before the next BRA round:
1. **The figure is the working set of the whole process.** A phase that starts in a process that earlier phases of the same run have grown carries their memory. The peaks above come from manifests of mixed history (BRA `technical_potential` was 3,410 MB inside the full round of 2026-11-09 and 1,579 MB alone in COMMAND 129). The first full BRA chain in one process is the real test: if `technical_potential` starts at more than 2,480 MB it is stopped at once. Set `GEOFREA_MEMORY_CAPS=0` for a run to take the caps out; `peak_rss_mb` is still recorded.
2. **The stop is delivered at the next Python instruction of the phase**, so a long call into C code (a warp, a Parquet write) ends first, and a phase that ends before the stop arrives is not failed (its result is complete, it carries `peak_over_cap` and a warning).

Tests: `tests/unit/test_memory_cap.py` (26 tests: the formula, the file, the rule, the sampler with a stop, the orchestrator writing the manifest).

## 2. OQ-084, the content hash by logical type

The function is `core/content_hash.py::_parquet_hash` (`core.content_hash` is in `INFRASTRUCTURE_MODULES`). It is imported by `core/orchestrator.py` (infrastructure), `core/cache_integrity.py` (in `FINGERPRINT_EXEMPT_MODULES`) and by scripts. No phase closure and no function fingerprint reaches it: **it does not change the fingerprint of any phase that has run**, and the fingerprints recomputed after the change are identical. So it was implemented.

- `parquet2:` (the default now) hashes the logical type of each column (`large_string` is `string`, `large_binary` is `binary`, `large_list<T>` is `list<T>`, walked inside structs, lists and maps); for a column of lists or structs, which falls to the Arrow stream, the batch is cast to the logical schema first, or a `large_list` would still differ. `parquet:` is kept unchanged.
- Coexistence: `content_hash_like(path, recorded)` hashes a file in the kind of a recorded value (used by `cache_integrity` and `scripts/check_manifests.py`); the orchestrator keeps the kind of an artifact that already has a hash when it is registered again, so the comparison of the old and the new registration is always like with like; a new artifact gets `parquet2:`. The 37 `parquet:` hashes of the PRT manifest still verify.
- Without a wide type the two kinds have the same digest (tested), so only the prefix differs.
- **What this does not do yet:** the 2 F5 tables written by pandas 3 with pyarrow 25 keep the recorded `parquet:` hash of the official files and still read as changed, until their entries are restamped (a restamp is safe only where the byte hash `sha256` equals the file's). That and correction (2) of the OQ (write with the declared schema, which changes the F5 writer) are in `window_list_131.md`. OQ-084 stays partly resolved.

## 3. Texts and records

Done: README (`-c ci/constraints.txt`, how to build ZZZ with the generator reading `.env`, F6 onwards by `pytest tests/synthetic`, tests and memory); `scripts/generate_zzz_fixture.py` loads `.env` as `main.py` does (code in `scripts/`, outside every closure); ZZZ in `config/country_names.yaml` (`climate_maps` and `overview` of ZZZ no longer fail for the name; not part of the config fingerprint); METHODOLOGY 19.1.0 (A-01, A-02 with the schemas 2.9 to 2.11, A-12 by value and not by bytes, M-F6-08); PROGRESS.json (F5 and `potential_maps` rerun, the rebaselines of COMMAND 128, methodology version); OQ-079 closed with "`P_ref` is DC, declared" (D-F6-028, METHODOLOGY M-F6-08), its two leftovers (the note in `parameters.json`, the sourced DC/AC review) are in the window list because the first moves a configuration fingerprint.

OQ-073, 074, 075 and 078: one line of action each in `docs/OPEN_QUESTIONS.md`. Of these only **OQ-075** (Pillow 13 goldens, tests only) is free of fingerprints and can be done at any time; OQ-073 and OQ-078 move closures and are on the window list; OQ-074 depends on where the fix is (the 52 tests under both versions can be compared at any time, nothing in `src` changes by that). The README and `ci/constraints.txt` now keep a clean clone on geopandas 1.1.2.

**OQ-071 (retune ZZZ2), report only, nothing changed.** Retuning `scripts/zzz2_world.py` (cost spreads or cell areas) would change, in the frozen material: (a) `tests/synthetic/test_zzz2_end_to_end.py`: the `EXPECTED` table of both technologies (`c_k`, `v_k`, `overlap`, `d`, `d_clim`, `d_tec`, `r_loss`, `cases`, `futures`, `box_density`, `box_coverage`; solar now 13/14 and 117/205), the assertion of the PRIM test (the pinned set of restricted descriptors of solar, to be replaced by "`gcm` is not restricted") and `GROUP6_AREAS` if a cell area moves; (b) `tests/fixtures/group6_decomposition/zzz2_pre_group6.json`: it is the snapshot of this world on the tree before Group 6 (commit `2bb1161`), so a new world needs a new snapshot made on that old tree, or the decomposition test narrowed; (c) the values the hand validator recomputes (`validate_zzz_by_hand.py` reads the run, so it needs no edit, but its 42 and 40 checks have to be run again to re-derive `EXPECTED`). **Not affected:** the V-01 frozen fixtures and the ZZZ (first) world, `tests/fixtures/prim_reference.json` (cases of `ema_workbench`, not this world), and every real country. `test_deferred_check_zzz.py` imports the world's `PARAMETER_OVERRIDES` and would need a run, not an edit.

## 4. The cycle `assemble` <-> `hypotheses`

`hypotheses.py` imported `Rankings` from `assemble.py` (under `TYPE_CHECKING`) and `assemble.py` imported `Statistic` from `hypotheses.py`. `Rankings` now lives in `rankings.py` (where `TopK` is); `assemble` and `pipeline` import it from there (`from ...assemble import Rankings` still works). `tests/unit/test_import_dag.py` gains a module graph (every import, inside functions and under `TYPE_CHECKING` too) and a Tarjan check for cycles of two or more modules, with a planted cycle of two, one of three and a chain as the test of the check; run on the tree before the change it reports exactly `assemble` and `hypotheses`. Fingerprints: `robustness_analysis` and `sample_size_convergence` change (F7, never run for real).

## 5. `pytest -n 3`

| | tests | time | peak of the summed RSS of the process tree | lowest free memory |
|---|---|---:|---:|---:|
| serial, COMMAND 128 (before this command's tests) | 2,507 passed, 1 skipped | 41 min 14 s | not recorded | not recorded |
| `-n 3`, run 1 (code at `5d97fcd`) | 2,539 passed, 1 skipped, **1 failed** | 23 min 9 s | 2,673 MB | **8 MB** |
| `-n 3`, run 2 (code at `eab2b33`) | **2,541 passed, 1 skipped** | 23 min 59 s | 2,335 MB | 77 MB |
| serial, same code as run 2 | 2,541 passed, 1 skipped | 45 min 52 s | 2,183 MB | 117 MB |

The count rose from 2,508 to 2,542 because this command added 34 tests. **Run 1 failure:** `tests/unit/test_layer_process.py::test_the_commit_limit_ends_the_child_and_says_so`. The test got the exception it expects (`CommitLimitExceeded`) and then died in the removal of its temporary folder: `PermissionError [WinError 32]` on `child.log`, because the child it had just killed still held the file. With three workers and 8 MB of free memory the killed process took longer to go. It is a race in `core/layer_process.kill_tree`, not an effect of the parallel run on the results; `kill_tree` now waits for the processes it killed (`psutil.wait_procs`, 10 s). Run 2, with the fix, had no failure.

The parallel run takes half the time of the serial run of the same session (about 24 min against 46; the 41 min of COMMAND 128 was a quieter machine), and its summed memory is only 150 MB above the serial one (2,335 against 2,183 MB), because the single process of the serial run keeps what every test left. Verdict: the two runs have the same tests and results except that race, so the parallel run is stable in what it computes; the margin of memory on this machine is not: **three workers brought the free memory to 8 MB in run 1 and 77 MB in run 2 on a machine with 5.9 GB where the browser and the editor were open.** Enabled in `.github/workflows/unit.yml` (`-n 3`, the unit job has 4 cores and 16 GB on the hosted runner; the run of `bcfd601` on `main` passed: unit 5 min 23 s against 9 min 26 s before, synthetic 6 min 7 s, regression 46 s) and documented in `CLAUDE.md` and the README with the advice to close other applications or to use `-n 2` locally.

## 6. Repository cleanup

Removed: the worktrees `GeoFREA_f5wt`, `GeoFREA_cswt`, `GeoFREA_envwt` (all clean) and the seven local branches that were merged into `main` (`ast-normalize`, `ci-env-pins`, `ci-linux-fix`, `config-scope-fix`, `country-config-guard`, `f5-memory`, `feat/83-group3-connection-degradation`; `git branch -d`, which refuses an unmerged branch). Not deleted, as asked:

- remote branches merged into `origin/main`: `origin/ast-normalize`, `origin/ci-env-pins`, `origin/ci-linux-fix`, `origin/config-scope-fix`, `origin/country-config-guard`, `origin/f5-memory`, `origin/feat/83-group3-connection-degradation`;
- the two not merged are **local only** (neither exists on `origin`): `backup-before-split` (`f9e8d55`, 2026-10-06) and `feat/cache-restamp` (`8fe3df9`, 2026-10-22). There is no unmerged remote branch.

## 7. Time by layer (read only)

**`grid_alignment`**: the ledger `interim/<ISO>/grid_alignment/layers.json` has a row per layer. In the current manifest the phase ran cold under the current code only for the four distance layers (the others were cached and show 0 s), so the decomposition of that cold execution is complete:

| layer | PRT | IND | BRA | share of BRA |
|---|---:|---:|---:|---:|
| grid (`dist_grid`) | 7.7 s | 59.1 s | 278.0 s | 47 % |
| rivers | 5.6 s | 41.9 s | 158.5 s | 27 % |
| roads | 9.2 s | 45.4 s | 105.9 s | 18 % |
| poi (and `poi_sensitivity` in IND) | 13.3 s | 44.9 s (+44.3 s) | 49.4 s | 8 % |
| sum of the layers | 36 s | 236 s | 592 s | |
| phase wall (manifest) | 40 s | 246 s | 604 s | the 12 s of BRA outside the layers |

The layers that are cached took long when they were built: `memory_budget.json` records for BRA the whole run of `elevation` at 11,117 s, `slope_fabdem` 4,177 s (IND 1,911 s, PRT 42 s), `land_cover_counts` 2,482 s; those are in earlier rounds whose ledgers were overwritten, so a per-layer figure for a fully cold F2a of today does not exist in any manifest. It would need one cold run with the caches of F2a emptied.

**`data_acquisition`**: **no per-layer record exists.** The manifest holds one figure for the phase (PRT 19 s, IND 422 s, BRA 272 s; 713 s together), the run log has only the start line and the completion line of the phase, and the `layer_registry` holds provenance and SHA-256 per layer but no time. What the logs do say: in the cold executions of IND and BRA the CPU time is 93 to 99 % of the wall time (IND 411 s wall, 391 s CPU; BRA 424 s wall, 409 s CPU, 2026-10-29), so the phase is compute-bound in one thread and not waiting on the network; the hashing of the source files is the first suspect, not proved. To decompose it, one of: (a) a `wall_s` per layer in `LayerResult` and a log line per layer (a code change in the closure of `data_acquisition`, so it goes with the window), or (b) one run of the phase on IND under `cProfile` (about 7 min) now, with no change to the code.

## 8. `GeoFREA_data`

Listing only, nothing deleted: `docs/_audit/data_cleanup_list_131.md`. Summary: (i) drafts and `work` 12.043 GB (of which `work/pre116` 5.164, `work/snapshot_129` 1.886, `_f3_new_BRA` 1.526, `_f3_cold_BRA` 1.487, `_f3_97_BRA` 1.198, `_f3_profile_BRA` 0.727); (ii) by your rule, one round (`references/9c2dc3c8...`, the only one whose full hash is in `docs/_audit`) and it frees about 1 MB because its files are hard links, so it is listed and not recommended; `backup_before_89` (1.978 GB) and `backup_before_91` (0.619 GB) have no hash in `docs/_audit` and are listed apart; (iii) the 18 clip `.key` (1,152 bytes) and the 12 GLO30 slope rasters with their 12 sidecars (0.373 GB, under `outputs/`, named by OQ-083). No current manifest references any of it. Sum of (i), (iii) and the two backups: 15.013 GB.

## Fingerprint verdict

| step | code touched | 12 phases that ran | 9 caches, 13 function fingerprints | phases that moved |
|---|---|---|---|---|
| 1 | `core/memory_cap.py` (new), `peak_memory.py`, `orchestrator.py`, `main.py`, `config/memory_budget.json` | identical | identical | none |
| 1 (first try) | `core/code_fingerprint.py` `INFRASTRUCTURE_MODULES` | identical | **changed** (`aligned_layer.lakes`, `.rivers`, `.roads`, `aligned_layers`) | reverted; the module is outside the closures anyway |
| 2 | `core/content_hash.py`, `cache_integrity.py`, `orchestrator.py`, `scripts/check_manifests.py` | identical | identical | none |
| 4 | `robustness_analysis/{assemble,hypotheses,rankings}.py` | identical | identical | `robustness_analysis`, `sample_size_convergence` (never run on real data) |
| 5 | `core/layer_process.py` (`kill_tree`) | identical | identical | none |
| 3, 6, 7, 8 | texts, `scripts/generate_zzz_fixture.py`, `config/country_names.yaml`, workflows, `tests/` | identical | identical | none |
